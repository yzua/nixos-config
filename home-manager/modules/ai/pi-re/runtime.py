#!/usr/bin/env python3
"""Selected rooted-lab agent-device and matched Frida operations."""

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

from android import Android, LabError, read_json, safe_path, write_json
from initialize import private_directory

LIMIT = 16384
DEVICE_COMMANDS = {
    "open",
    "close",
    "snapshot",
    "click",
    "press",
    "fill",
    "type",
    "scroll",
    "swipe",
    "back",
    "get",
    "find",
    "is",
    "wait",
    "screenshot",
    "keyboard",
}
PROTECTED = {
    "--platform",
    "--serial",
    "--device",
    "--udid",
    "--session",
    "--state-dir",
    "--remote",
    "--remote-config",
    "--tenant",
    "--session-lock",
    "--android-device-allowlist",
    "--config",
    "--host",
    "--port",
    "--target",
    "--shutdown",
    "--launch-args",
    "--run-id",
    "--lease-id",
    "--lease-backend",
    "--session-isolation",
}


def device_arguments(config, lab, args, owner):
    if not args or args[0] not in DEVICE_COMMANDS:
        raise LabError("Select a local agent-device command; remote/cloud/MCP are not enabled")
    for arg in args:
        if arg == "--":
            break  # Text after the separator is positional, never a routing option.
        flag = arg.split("=", 1)[0]
        if flag in PROTECTED or flag.startswith(("--daemon-", "--provider", "--aws-")):
            raise LabError("Device identity/state flags are controlled by the lab wrapper")
    state = safe_path(lab.state / "device")
    session = f"pi-re-{lab.name}-{owner['token'][:12]}"
    return [
        config["agentDevice"],
        "--platform",
        "android",
        "--serial",
        lab.serial,
        "--session",
        session,
        "--state-dir",
        str(state),
        "--config",
        str(Path(__file__).parent / "agent-device.json"),
        "--session-lock",
        "reject",
        "--android-device-allowlist",
        lab.serial,
        "--daemon-transport",
        "socket",
        "--daemon-server-mode",
        "socket",
        *args,
    ]


def local_environment(lab):
    env = lab.env.copy()
    for key in list(env):
        if key.startswith("AGENT_DEVICE_"):
            del env[key]
    home = safe_path(lab.state / "device-home")
    private_directory(home)
    env["HOME"] = str(home)
    env["AGENT_DEVICE_NO_UPDATE_NOTIFIER"] = "1"
    env["PATH"] = str(Path(lab.tools["adb"]).parent) + os.pathsep + env.get("PATH", "")
    return env


def bounded_run(argv, env, directory, timeout=30):
    directory = safe_path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = str(time.time_ns())
    output = directory / f"{stamp}.stdout"
    diagnostics = directory / f"{stamp}.stderr"
    for path in (output, diagnostics):
        safe_path(path)
    with output.open("x") as out, diagnostics.open("x") as err:
        os.chmod(output, 0o600)
        os.chmod(diagnostics, 0o600)
        try:
            result = subprocess.run(
                argv,
                env=env,
                stdout=out,
                stderr=err,
                stdin=subprocess.DEVNULL,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise LabError(
                f"Runtime deadline exceeded; private diagnostics: {diagnostics}", True
            ) from error
    if result.returncode:
        raise LabError(
            f"Runtime command failed; private stdout: {output}; private stderr: {diagnostics}"
        )
    if output.stat().st_size > LIMIT:
        return {"status": "partial", "truncated": True, "artifact": str(output)}
    text = output.read_text(errors="replace")
    try:
        value = json.loads(text)
    except ValueError:
        value = text
    return {"status": "ok", "result": value, "artifact": str(output)}


def device(config, lab, args):
    # Matching-version help is offline; it must not root, launch or contact a device.
    if args and args[0] in ("help", "--help", "--version"):
        return bounded_run(
            [config["agentDevice"], *args], local_environment(lab), lab.state / "device-help"
        )
    with lab.lock():
        lab.root_device(lab.backend.now() + lab.timeout)
        argv = device_arguments(config, lab, args, lab.owner())
        return bounded_run(argv, local_environment(lab), lab.state / "device-commands", 90)


class Frida:
    def __init__(self, config, lab):
        self.config = config
        self.lab = lab
        self.spec = config["frida"]
        if self.spec["abi"] != lab.config["abi"]:
            raise LabError("Frida server ABI does not match the selected lab")
        self.metadata = lab.state / "frida.json"
        self.remote = f"/data/local/tmp/pi-re-frida-{self.spec['version']}"

    def shell(self, args, timeout=10):
        try:
            code, output = self.lab.adb(["shell", *args], timeout)
        except LabError as error:
            raise LabError(f"Frida guest command {args[0]}: {error}", error.timeout) from error
        if code:
            raise LabError("Selected-device Frida command failed")
        return output.strip()

    def boot(self):
        return self.shell(["cat", "/proc/sys/kernel/random/boot_id"])

    def owned(self, metadata, require_running=True):
        if (
            metadata.get("owner") != self.lab.owner()["token"]
            or metadata.get("serial") != self.lab.serial
            or metadata.get("version") != self.spec["version"]
            or metadata.get("boot") != self.boot()
        ):
            raise LabError(
                "Frida ownership/boot/version changed; refusing process reuse or cleanup"
            )
        pid = metadata.get("pid")
        if not isinstance(pid, int) or pid < 2:
            raise LabError("Invalid Frida process ownership")
        code, command = self.lab.adb(["shell", "cat", f"/proc/{pid}/cmdline"])
        if code:
            if require_running:
                raise LabError("Owned Frida server is not running")
            return False
        if not command:
            if require_running:
                raise LabError("Owned Frida server is not running")
            return False
        if command.split("\x00")[0] != self.remote or metadata.get("start") != self.start_ticks(
            pid
        ):
            raise LabError("Frida PID was reused; refusing operation")
        return True

    def start_ticks(self, pid):
        try:
            return self.shell(["cat", f"/proc/{pid}/stat"]).rsplit(")", 1)[1].split()[19]
        except (IndexError, ValueError) as error:
            raise LabError("Cannot establish Frida process start identity") from error

    def retire_stale(self, record):
        if record.get("serial") != self.lab.serial:
            raise LabError("Foreign Frida serial metadata")
        if record.get("owner") == self.lab.owner()["token"] and record.get("boot") == self.boot():
            return False
        # A previous guest boot/generation cannot own any current guest PID. Keep
        # the evidence but never signal its numerical PID on this new guest.
        archive = safe_path(self.lab.state / f"frida-stale-{time.time_ns()}.json")
        self.metadata.rename(archive)
        return True

    def setup(self):
        if self.metadata.exists():
            old = read_json(self.metadata)
            if not self.retire_stale(old) and self.owned(old, require_running=False):
                return {"status": "ok", "server": "running", "version": self.spec["version"]}
        # Do not replace another listener. /proc/net/tcp uses hex 69A2 for port 27042.
        network = self.shell(["cat", "/proc/net/tcp", "/proc/net/tcp6"])
        rows = [line.split() for line in network.splitlines()]
        if any(
            len(row) > 3 and row[1].rsplit(":", 1)[-1] == "69A2" and row[3] == "0A" for row in rows
        ):
            raise LabError("Device Frida port is occupied; refusing takeover")
        source = Path(self.spec["server"])
        if not source.is_file():
            raise LabError("Pinned Frida server is unavailable; runtime downloads are disabled")
        try:
            code, _ = self.lab.adb(["push", str(source), self.remote], timeout=60)
        except LabError as error:
            raise LabError(f"Frida server push: {error}", error.timeout) from error
        if code:
            raise LabError("Frida server deployment failed")
        self.shell(["chmod", "755", self.remote])
        command = (
            f"nohup {shlex.quote(self.remote)} -l 127.0.0.1:27042 "
            ">/data/local/tmp/pi-re-frida.log 2>&1 </dev/null & echo $!"
        )
        record = None
        try:
            pid_text = self.shell(["sh", "-c", shlex.quote(command)])
            pid = int(pid_text)
            record = {
                "owner": self.lab.owner()["token"],
                "serial": self.lab.serial,
                "version": self.spec["version"],
                "boot": self.boot(),
                "pid": pid,
                "start": self.start_ticks(pid),
            }
            write_json(self.metadata, record)
        except (Exception, KeyboardInterrupt):
            try:
                if record is None:
                    # An ambiguous launch cannot be cleaned up by a guessed guest
                    # PID. Stop only this verified owned VM to prevent stranding it.
                    self.lab.stop(graceful=False)
                else:
                    self.signal_owned(record)
            except (Exception, KeyboardInterrupt):
                self.lab.stop(graceful=False)
            raise
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                self.owned(record)
                return {"status": "ok", "server": "running", "version": self.spec["version"]}
            except LabError:
                time.sleep(0.2)
        raise LabError("Frida server did not become ready; owned metadata retained", True)

    def status(self):
        if not self.metadata.exists():
            return {"status": "ok", "server": "absent"}
        self.owned(read_json(self.metadata))
        return {"status": "ok", "server": "running", "version": self.spec["version"]}

    def stop(self):
        if not self.metadata.exists():
            return {"status": "ok", "server": "absent"}
        record = read_json(self.metadata)
        if self.retire_stale(record):
            return {"status": "ok", "server": "stopped", "staleRecordRetired": True}
        self.signal_owned(record)
        self.metadata.unlink()
        return {"status": "ok", "server": "stopped"}

    def signal_owned(self, record):
        if not self.owned(record, require_running=False):
            return
        helper = f"/data/local/tmp/pi-re-signal-{record['owner'][:12]}"
        source = Path(self.spec["signalHelper"])
        code, _ = self.lab.adb(["push", str(source), helper], timeout=30)
        if code:
            raise LabError("Owned guest signal helper deployment failed")
        self.shell(["chmod", "755", helper])
        # The helper opens a pidfd first, checks boot/exe/start identity, then
        # signals that fd. No race-prone kill(pid) fallback is allowed.
        self.shell([helper, str(record["pid"]), record["start"], record["boot"], self.remote])
        deadline = time.monotonic() + 10
        while self.owned(record, require_running=False):
            if time.monotonic() >= deadline:
                raise LabError("Owned Frida server did not stop; metadata retained", True)
            time.sleep(0.2)

    def run(self, args):
        if self.status()["server"] != "running":
            raise LabError("Set up the owned matched Frida server before attaching")
        parser = argparse.ArgumentParser(prog="pi-re frida run")
        parser.add_argument("--package", required=True)
        parser.add_argument("--script", type=Path)
        options = parser.parse_args(args)
        command = [
            self.config["python"],
            str(Path(__file__).parent / "frida_probe.py"),
            "--serial",
            self.lab.serial,
            "--package",
            options.package,
        ]
        if options.script:
            command += ["--script", str(options.script.resolve(strict=True))]
        return bounded_run(command, local_environment(self.lab), self.lab.state / "frida-runs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("kind", choices=("device", "frida"))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    try:
        config = json.loads(options.config.read_text())
        lab = Android(config, options.state_dir)
        if options.kind == "device":
            result = device(config, lab, options.args)
        else:
            if not options.args or options.args[0] not in ("setup", "status", "stop", "run"):
                raise LabError("Frida supports setup, status, stop or run --package <identity>")
            with lab.lock():
                lab.root_device(lab.backend.now() + lab.timeout)
                runtime = Frida(config, lab)
                if options.args[0] == "run":
                    result = runtime.run(options.args[1:])
                else:
                    result = getattr(runtime, options.args[0])()
        print(json.dumps(result))
        return 0
    except (LabError, OSError, ValueError, KeyError) as error:
        timeout = isinstance(error, LabError) and error.timeout
        print(json.dumps({"status": "timeout" if timeout else "blocked", "error": str(error)}))
        return 2 if timeout else 1


if __name__ == "__main__":
    sys.exit(main())
