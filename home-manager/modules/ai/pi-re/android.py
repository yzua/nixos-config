#!/usr/bin/env python3
"""Owned, rooted Android AVD lifecycle; never installs SDK packages or uses sudo.

Exit codes: 0 success, 1 error/blocked, 2 timeout. Status is process-only and never
invokes ADB. State belongs to the invoking uid, not a security boundary against it.
"""

import argparse
import contextlib
import fcntl
import json
import os
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path


class LabError(Exception):
    def __init__(self, message, timeout=False):
        super().__init__(message)
        self.timeout = timeout


def safe_path(path):
    """Reject symlinks at every existing component, including dangling links."""
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        if item.is_symlink():
            raise LabError("State paths must not contain symlinks")
    return path


def read_json(path):
    safe_path(path)
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise LabError("State metadata must be a caller-owned regular file")
        if info.st_size > 16384:
            raise LabError("State metadata is too large")
        with path.open() as stream:
            value = json.load(stream)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (OSError, ValueError) as exc:
        raise LabError("Invalid or inaccessible state metadata") from exc


def write_json(path, value):
    safe_path(path)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex)
    try:
        with open(temp, "x", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class Backend:
    """Small injectable Linux process/subprocess seam for offline tests."""

    now = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)

    def run(self, argv, env, timeout, input=None):
        # Tool output remains private; diagnostics never echo arbitrary subprocess text.
        with tempfile_output() as output:
            try:
                result = subprocess.run(
                    argv,
                    env=env,
                    input=input,
                    text=True,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise LabError("Android tool deadline exceeded", timeout=True) from exc
            output.seek(0)
            return result.returncode, output.read(16384)

    def spawn(self, argv, env, log):
        return subprocess.Popen(
            argv,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        ).pid

    def host_boot(self):
        try:
            boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
            if not boot:
                raise ValueError()
            return boot
        except (OSError, ValueError) as exc:
            raise LabError("Cannot verify host boot identity") from exc

    def process(self, pid):
        try:
            proc = Path(f"/proc/{pid}")
            fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
            if fields[0] == "Z":
                return None
            return {
                "start": fields[19],
                "session": int(fields[3]),
                "uid": proc.stat().st_uid,
                "boot": self.host_boot(),
            }
        except FileNotFoundError:
            return None
        except (OSError, ValueError, IndexError) as exc:
            raise LabError("Cannot verify emulator process identity") from exc

    def port_free(self, port):
        # Probe both families: an IPv6-only console must not evade preflight.
        for family, address in ((socket.AF_INET, "0.0.0.0"), (socket.AF_INET6, "::")):
            try:
                with socket.socket(family) as sock:
                    # Stopped emulators leave TIME_WAIT connections. Reuse addresses,
                    # not ports: live listeners must still fail this wildcard bind.
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    if family == socket.AF_INET6:
                        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                    sock.bind((address, port))
            except OSError as exc:
                import errno

                if family == socket.AF_INET6 and exc.errno in (errno.EAFNOSUPPORT, errno.ENODEV):
                    continue
                return False
        return True

    def terminate(self, pid, identity, sig):
        # pidfd prevents signaling a recycled PID between verification and kill.
        try:
            fd = os.pidfd_open(pid)
        except ProcessLookupError:
            return
        try:
            if self.process(pid) != identity:
                raise LabError("Emulator process identity changed; refusing signal")
            signal.pidfd_send_signal(fd, sig)
        finally:
            os.close(fd)


@contextlib.contextmanager
def tempfile_output():
    # Anonymous file avoids unbounded RAM capture and is deleted when closed.
    import tempfile

    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as stream:
        yield stream


class Android:
    def __init__(self, config, state_dir, backend=None):
        self.backend = backend or Backend()
        self.config = config.get("android", config)
        c = self.config
        try:
            self.name = c["avdName"]
            if not isinstance(self.name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", self.name):
                raise ValueError()
            if (str(c["apiLevel"]), c["imageType"], c["abi"]) != ("35", "google_apis", "x86_64"):
                raise LabError("Only rooted API 35 google_apis x86_64 is supported")
            self.port = self.integer("port", 1024, 65534)
            if self.port % 2:
                raise ValueError()
            self.memory = self.integer("memoryMiB", 512, 32768)
            self.cores = self.integer("cores", 1, 64)
            self.timeout = self.integer("bootTimeoutSeconds", 1, 1800)
            self.gpu_mode = c.get("gpuMode")
            if self.gpu_mode is not None and self.gpu_mode not in (
                "swiftshader",
                "swiftshader_indirect",
                "swangle",
                "software",
                "lavapipe",
            ):
                raise ValueError()
            self.hardware_decoder = c.get("hardwareVideoDecoder", True)
            if type(self.hardware_decoder) is not bool:
                raise ValueError()
            self.display = None
            if "display" in c:
                display = c["display"]
                bounds = {"width": (240, 4096), "height": (240, 4096), "density": (72, 640)}
                if not isinstance(display, dict) or display.keys() != bounds.keys():
                    raise ValueError()
                for key, (lower, upper) in bounds.items():
                    if type(display[key]) is not int or not lower <= display[key] <= upper:
                        raise ValueError()
                self.display = display.copy()
            self.sdk = Path(c["sdkRoot"])
            self.tools = {key: str(Path(c[key])) for key in ("adb", "emulator", "avdmanager")}
            if not self.sdk.is_absolute() or any(
                not Path(tool).is_absolute() for tool in self.tools.values()
            ):
                raise ValueError()
        except (KeyError, TypeError, ValueError) as exc:
            raise LabError("Invalid Android configuration") from exc
        self.state = safe_path(state_dir)
        self.root = self.state / "android"
        safe_path(self.root)
        sdk = self.sdk.resolve()
        if self.root.resolve().is_relative_to(sdk) or sdk.is_relative_to(self.root.resolve()):
            raise LabError("SDK and mutable Android state must be separate")
        self.user = self.root / "user"
        self.avds = self.root / "avd"
        self.avd = self.avds / f"{self.name}.avd"
        self.ini = self.avds / f"{self.name}.ini"
        self.owner_file = self.root / "owner.json"
        self.lease_file = self.root / "lease.json"
        self.serial = f"emulator-{self.port}"
        self.package = "system-images;android-35;google_apis;x86_64"
        self.identity = {
            "version": 1,
            "uid": os.getuid(),
            "state": str(self.state),
            "avdName": self.name,
            "package": self.package,
            "serial": self.serial,
        }
        self.env = os.environ.copy()
        # Do not inherit alternate emulator homes or remote/shared ADB endpoints.
        for key in (
            "ANDROID_SDK_HOME",
            "ANDROID_EMULATOR_HOME",
            "ADB_SERVER_SOCKET",
            "ANDROID_ADB_SERVER_PORT",
            "ANDROID_SERIAL",
            "ADB_SERVER_PORT",
        ):
            self.env.pop(key, None)
        self.env.update(
            {
                "ANDROID_HOME": str(self.sdk),
                "ANDROID_SDK_ROOT": str(self.sdk),
                "ANDROID_USER_HOME": str(self.user),
                "ANDROID_AVD_HOME": str(self.avds),
                "ANDROID_EMULATOR_HOME": str(self.user),
            }
        )

    def integer(self, key, lower, upper):
        value = self.config[key]
        if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
            raise ValueError()
        return value

    def check_paths(self):
        for path in (
            self.root,
            self.user,
            self.avds,
            self.avd,
            self.ini,
            self.owner_file,
            self.lease_file,
            self.root / "emulator.log",
        ):
            safe_path(path)
        if self.root.exists() and (
            not self.root.is_dir() or self.root.stat().st_uid != os.getuid()
        ):
            raise LabError("Android state is not owned by the caller")
        log = self.root / "emulator.log"
        if log.exists():
            info = log.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
                raise LabError("Emulator log must be a single-link caller-owned regular file")

    @contextlib.contextmanager
    def lock(self, readonly=False):
        self.check_paths()
        path = self.root / "lock"
        safe_path(path)
        if readonly and not path.exists():
            yield
            return
        if not readonly:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_RDONLY if readonly else os.O_RDWR | os.O_CREAT
        fd = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
                raise LabError("Invalid Android lock ownership")
            try:
                fcntl.flock(fd, (fcntl.LOCK_SH if readonly else fcntl.LOCK_EX) | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise LabError("Another Android lifecycle operation holds the lock") from exc
            self.check_paths()
            yield
        finally:
            os.close(fd)

    def owner(self, required=True):
        if not self.owner_file.exists():
            if required:
                raise LabError("AVD is not owned; run create first")
            return None
        owner = read_json(self.owner_file)
        if any(owner.get(k) != v for k, v in self.identity.items()) or not isinstance(
            owner.get("token"), str
        ):
            raise LabError("AVD owner/configuration mismatch")
        return owner

    def lease(self):
        owner = self.owner()
        if not self.lease_file.exists():
            return None, None
        lease = read_json(self.lease_file)
        if lease.get("token") != owner["token"] or lease.get("serial") != self.serial:
            raise LabError("Foreign emulator lease")
        pid = lease.get("pid")
        expected = lease.get("process")
        if type(pid) is not int or pid <= 1 or not isinstance(expected, dict):
            raise LabError("Invalid emulator lease")
        if (
            type(expected.get("uid")) is not int
            or expected["uid"] != os.getuid()
            or type(expected.get("session")) is not int
            or expected["session"] != pid
        ):
            raise LabError("Foreign emulator session")
        if (
            not isinstance(expected.get("start"), str)
            or not expected["start"].isdigit()
            or not isinstance(expected.get("boot"), str)
            or not expected["boot"].strip()
        ):
            raise LabError("Invalid emulator process identity lease")
        # A verified lease from an earlier host boot cannot name a live process.
        # Do not inspect its PID: that number may now belong to an unrelated owner.
        if expected["boot"] != self.backend.host_boot():
            return lease, None
        process = self.backend.process(pid)
        if process is not None and process != expected:
            raise LabError("Stale lease/PID reuse; refusing emulator operation")
        return lease, process

    def tool(self, name, args, timeout=15, input=None):
        tool = self.tools[name]
        if not os.path.isfile(tool) or not os.access(tool, os.X_OK):
            raise LabError(f"Configured {name} executable is unavailable")
        return self.backend.run([tool, *args], self.env, timeout, input)

    def adb(self, args, timeout=10):
        return self.tool("adb", ["-s", self.serial, *args], timeout)

    def create(self):
        owner = self.owner(required=False)
        if owner:
            lease, process = self.lease()
            if process:
                return self.result("running", rooted="uninspected")
            if self.avd.is_dir() and self.ini.is_file():
                self.check_avd()
                return self.result("created")
            if lease:
                raise LabError("Incomplete AVD with a stale lease; reset first")
            # A failed create can be retried only after an explicit reset.
            raise LabError("Owned AVD is incomplete; reset then create")
        if any(item.name != "lock" for item in self.root.iterdir()):
            raise LabError("Refusing to claim foreign Android state/AVD")
        image = self.sdk / "system-images" / "android-35" / "google_apis" / "x86_64"
        if not (image / "package.xml").is_file() or not (image / "system.img").is_file():
            raise LabError("Pinned system image is absent; SDK downloads are not permitted")
        self.user.mkdir(mode=0o700)
        self.avds.mkdir(mode=0o700)
        write_json(self.owner_file, {**self.identity, "token": uuid.uuid4().hex})
        code, _ = self.tool(
            "avdmanager",
            [
                "create",
                "avd",
                "--name",
                self.name,
                "--package",
                self.package,
                "--path",
                str(self.avd),
            ],
            timeout=90,
            input="no\n",
        )
        if code:
            raise LabError("AVD creation failed; private tool diagnostics were not exposed")
        self.check_paths()
        self.check_avd()
        return self.result("created")

    def check_avd(self):
        self.owner()
        if not self.avd.is_dir() or not self.ini.is_file():
            raise LabError("Owned AVD is missing/incomplete")
        safe_path(self.avd / "config.ini")
        # avdmanager's index must refer exactly to our private AVD directory.
        lines = self.ini.read_text().splitlines()
        if f"path={self.avd}" not in lines:
            raise LabError("AVD index refers to a foreign directory")
        for path in self.avd.rglob("*"):
            safe_path(path)

    def configure_display(self):
        """Update only display properties in a stopped, owned private AVD."""
        self.owner()
        path = safe_path(self.avd / "config.ini")
        for directory in (self.root, self.avds, self.avd):
            info = directory.stat()
            if (
                not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o022
                or (directory == self.root and info.st_mode & 0o077)
            ):
                raise LabError("Display configuration requires an owned private AVD directory")
        limit = 64 * 1024
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or info.st_nlink != 1
                    or info.st_mode & 0o022
                    or info.st_size > limit
                ):
                    raise LabError(
                        "AVD config must be a bounded single-link caller-owned regular file"
                    )
                data = stream.read(limit + 1)
                if len(data) > limit:
                    raise LabError("AVD config is too large")
        except OSError as exc:
            raise LabError("Cannot safely read owned AVD config") from exc
        settings = {
            f"hw.lcd.{key}".encode(): str(value).encode() for key, value in self.display.items()
        }
        lines, seen = [], set()
        for line in data.splitlines(keepends=True):
            key, separator, _ = line.partition(b"=")
            key = key.strip()
            if separator and key in settings:
                ending = b"\r\n" if line.endswith(b"\r\n") else b"\n"
                line = key + b"=" + settings[key] + ending
                seen.add(key)
            lines.append(line)
        updated = b"".join(lines)
        for key, value in settings.items():
            if key not in seen:
                if updated and not updated.endswith(b"\n"):
                    updated += b"\n"
                updated += key + b"=" + value + b"\n"
        if len(updated) > limit:
            raise LabError("Updated AVD config would be too large")
        if updated == data and stat.S_IMODE(info.st_mode) == 0o600:
            return
        temp = path.with_name(path.name + "." + uuid.uuid4().hex)
        try:
            with open(temp, "xb", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(updated)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def device_identity(self, timeout=10):
        lease, process = self.lease()
        if not process:
            raise LabError("No verified owned emulator is running")
        code, output = self.adb(["emu", "avd", "name"], timeout)
        if code or output.splitlines()[:1] != [self.name]:
            raise LabError("Selected serial does not identify the owned AVD")
        # Check again after ADB to avoid stale/reused PID mutation.
        if self.backend.process(lease["pid"]) != process:
            raise LabError("Emulator identity changed during inspection")
        return lease, process

    def remaining(self, deadline):
        remaining = deadline - self.backend.now()
        if remaining <= 0:
            raise LabError("Emulator boot/root deadline exceeded", timeout=True)
        return min(10, remaining)

    def root_device(self, deadline):
        self.device_identity(self.remaining(deadline))
        # adb root restarts adbd. Serial-scoped shell retries wait for reconnect without
        # an unbounded wait-for-device or a global reconnect/server restart.
        rooted = False
        while True:
            if not self.lease()[1]:
                raise LabError("Owned emulator exited during root verification")
            try:
                if not rooted:
                    code, _ = self.adb(["root"], self.remaining(deadline))
                    rooted = code == 0
                code, output = self.adb(["shell", "id", "-u"], self.remaining(deadline))
                if code == 0 and output.strip() == "0":
                    self.device_identity(self.remaining(deadline))
                    return self.result("running", rooted=True)
                rooted = False
            except LabError as exc:
                if not exc.timeout:
                    raise
            self.backend.sleep(min(1, self.remaining(deadline)))

    def start(self, visible=False):
        self.check_avd()
        lease, process = self.lease()
        if process:
            return self.root_device(self.backend.now() + self.timeout)
        if not all(self.backend.port_free(p) for p in (self.port, self.port + 1)):
            raise LabError("Emulator console/ADB port collision")
        code, output = self.adb(["devices"])
        if code or any(line.split()[:1] == [self.serial] for line in output.splitlines()):
            raise LabError("ADB preflight failed or selected serial is already claimed")
        code, output = self.tool("emulator", ["-help-gpu"])
        if code:
            raise LabError("Cannot inspect emulator software rendering support")
        modes = set(re.findall(r"\b[a-z_]+\b", output))
        if self.gpu_mode is not None:
            gpu = self.gpu_mode if self.gpu_mode in modes else None
        else:
            gpu = next(
                (mode for mode in ("swiftshader", "swiftshader_indirect") if mode in modes), None
            )
        if gpu is None:
            raise LabError("Emulator does not advertise the selected supported software GPU mode")
        argv = [
            self.tools["emulator"],
            "-avd",
            self.name,
            "-port",
            str(self.port),
            "-memory",
            str(self.memory),
            "-cores",
            str(self.cores),
            "-gpu",
            gpu,
            "-no-snapshot",
            "-no-boot-anim",
            "-writable-system",
        ]
        if not self.hardware_decoder:
            argv += ["-feature", "-HardwareDecoder"]
        if not visible:
            argv += ["-no-window", "-no-audio"]
        self.check_paths()
        if self.display is not None:
            self.configure_display()
            argv += ["-skin", f"{self.display['width']}x{self.display['height']}"]
        fd = os.open(
            self.root / "emulator.log", os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600
        )
        with os.fdopen(fd, "w") as log:
            os.fchmod(log.fileno(), 0o600)
            pid = self.backend.spawn(argv, self.env, log)
        process = self.backend.process(pid)
        if not process or process["session"] != pid or process["uid"] != os.getuid():
            raise LabError("Emulator exited or could not establish an owned session")
        try:
            write_json(
                self.lease_file,
                {
                    "token": self.owner()["token"],
                    "serial": self.serial,
                    "pid": pid,
                    "process": process,
                },
            )
        except (OSError, LabError, KeyboardInterrupt):
            self.backend.terminate(pid, process, signal.SIGKILL)
            raise
        deadline = self.backend.now() + self.timeout
        try:
            while True:
                _, process = self.lease()
                if not process:
                    raise LabError("Emulator exited before boot completed")
                code, output = self.adb(
                    ["shell", "getprop", "sys.boot_completed"], self.remaining(deadline)
                )
                if code == 0 and output.strip() == "1":
                    return self.root_device(deadline)
                self.backend.sleep(min(1, self.remaining(deadline)))
        except (LabError, OSError, KeyboardInterrupt):
            # Boot failure/cancellation must not strand a newly launched owned emulator.
            self.stop(graceful=False)
            raise

    def root_command(self):
        self.check_avd()
        return self.root_device(self.backend.now() + self.timeout)

    def status(self):
        if not self.owner(required=False):
            if self.lease_file.exists():
                raise LabError("Emulator lease is not owned")
            return self.result("absent")
        lease, process = self.lease()
        return self.result(
            "running" if process else "stopped",
            rooted="uninspected",
            inspection="process-only",
            staleLease=bool(lease and not process),
        )

    def stop(self, graceful=True):
        lease, process = self.lease()
        if not process:
            return self.result("stopped", staleLease=bool(lease))
        if graceful:
            try:
                code, output = self.adb(["emu", "avd", "name"], timeout=5)
                if code == 0:
                    if output.splitlines()[:1] != [self.name]:
                        raise LabError("Selected serial identifies a foreign AVD")
                    if self.backend.process(lease["pid"]) != process:
                        raise LabError("Emulator identity changed before stop")
                    self.adb(["emu", "kill"], timeout=5)
                    self.wait_stopped(lease, 5)
            except LabError as exc:
                if not exc.timeout:
                    raise
        _, process = self.lease()
        if process:
            self.backend.terminate(lease["pid"], process, signal.SIGTERM)
            self.wait_stopped(lease, 5)
        _, process = self.lease()
        if process:
            self.backend.terminate(lease["pid"], process, signal.SIGKILL)
            self.wait_stopped(lease, 3)
        if self.lease()[1]:
            raise LabError("Owned emulator did not stop", timeout=True)
        self.lease_file.unlink(missing_ok=True)
        return self.result("stopped")

    def wait_stopped(self, lease, seconds):
        deadline = self.backend.now() + seconds
        while self.lease()[1] and self.backend.now() < deadline:
            self.backend.sleep(0.2)

    def reset(self):
        self.owner()
        if self.lease()[1]:
            raise LabError("Stop the owned emulator before reset")
        self.check_paths()
        if not all(self.backend.port_free(p) for p in (self.port, self.port + 1)):
            raise LabError("Selected emulator ports are occupied; refusing reset")
        if self.avds.exists() and any(
            path not in (self.avd, self.ini) for path in self.avds.iterdir()
        ):
            raise LabError("Unrelated AVD paths preserved; ownership metadata retained")
        # Never remove the lab root or unrelated metadata; only our explicit resources.
        for directory in (self.avd, self.user):
            if directory.exists():
                for path in directory.rglob("*"):
                    safe_path(path)
        for directory in (self.avd, self.user):
            if directory.exists():
                shutil.rmtree(directory)
        for path in (self.ini, self.lease_file, self.root / "emulator.log"):
            path.unlink(missing_ok=True)
        if self.avds.exists():
            self.avds.rmdir()
        self.owner_file.unlink()
        return self.result("reset")

    def result(self, state, **extra):
        return {
            "status": "ok",
            "state": state,
            "serial": self.serial,
            "avdName": self.name,
            **extra,
        }

    def execute(self, command, visible=False):
        with self.lock(readonly=command == "status"):
            if command == "start":
                return self.start(visible)
            if command == "root":
                return self.root_command()
            return getattr(self, command)()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("command", choices=("create", "start", "status", "root", "stop", "reset"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--visible", action="store_true", help="Show emulator window (start only)")
    args = parser.parse_args(argv)
    try:
        if args.visible and args.command != "start":
            raise LabError("--visible is only valid with start")
        # Config is a read-only generated file and may itself be a Nix-store symlink.
        with Path(args.config).open() as stream:
            config = json.load(stream)
        result = Android(config, args.state_dir).execute(args.command, args.visible)
        code = 0
    except LabError as exc:
        result = {"status": "timeout" if exc.timeout else "blocked", "error": str(exc)}
        code = 2 if exc.timeout else 1
    except (OSError, ValueError, TypeError, AttributeError):
        result = {"status": "error", "error": "Invalid config or inaccessible Android resource"}
        code = 1
    except KeyboardInterrupt:
        result = {"status": "blocked", "error": "Android operation cancelled"}
        code = 1
    if args.json:
        print(json.dumps(result))
    else:
        print(result.get("error", f"{args.command}: {result.get('state')}"))
    return code


if __name__ == "__main__":
    sys.exit(main())
