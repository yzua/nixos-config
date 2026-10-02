#!/usr/bin/env python3
"""Caller-owned, local mitmdump capture. Never inspect or disclose flow contents.

Status reads metadata only; a recorded lease is not proof of a live process.
Linux PID/start/session/boot identity plus pidfd guards every stop signal.
"""

import contextlib
import fcntl
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import uuid
from pathlib import Path

from android import Backend as ProcessBackend
from android import LabError, safe_path

VERSION = "12.2.3"
START_SECONDS = 15
STOP_SECONDS = 5


def host_name(value):
    # Exact DNS hosts only, not wildcards, URLs, ports, suffix rules or IP ranges.
    if not isinstance(value, str) or len(value) > 253:
        raise LabError("Invalid traffic host allowlist")
    value = value.lower()
    if not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", s) for s in value.split(".")):
        raise LabError("Invalid traffic host allowlist")
    return value


def check_entry(path, directory=False):
    safe_path(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(info.st_mode) or info.st_uid != os.getuid():
        raise LabError("Traffic state must be caller-owned directories/regular files")
    if not directory and info.st_nlink != 1:
        raise LabError("Traffic files must be single-link (no hardlinks)")
    if info.st_mode & 0o077:
        raise LabError("Traffic state must be private to the caller")
    return True


def read_json(path):
    if not check_entry(path):
        raise LabError("Missing traffic metadata")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or info.st_mode & 0o077
            or info.st_size > 16384
        ):
            raise LabError("Invalid traffic metadata")
        try:
            value = json.load(stream)
        except (ValueError, UnicodeError) as exc:
            raise LabError("Invalid traffic metadata") from exc
    if not isinstance(value, dict):
        raise LabError("Invalid traffic metadata")
    return value


def write_file(path, content, mode=0o600):
    # Exclusive writes: never truncate a foreign file or reuse a mutable run config.
    safe_path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "wb") as stream:
        os.fchmod(stream.fileno(), mode)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def write_json(path, value, mode=0o600):
    check_entry(path)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex)
    try:
        write_file(temp, json.dumps(value, sort_keys=True).encode(), mode)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class Backend(ProcessBackend):
    """Injectable process seam. No HTTP requests or TLS verification shortcuts."""

    def __init__(self):
        self.children = {}

    def spawn(self, argv, env, log):
        child = subprocess.Popen(
            argv,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            umask=0o077,
        )
        self.children[child.pid] = child
        return child.pid

    def reap(self, pid):
        child = self.children.get(pid)
        if child is not None:
            try:
                child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                raise LabError("Owned traffic child did not exit", timeout=True)
            self.children.pop(pid, None)

    def listening(self, pid, port):
        # Check socket inodes owned by *this* process, not just a foreign listener
        # that won the preflight race. No connect probes, including to upstreams.
        try:
            inodes = set()
            for path in Path(f"/proc/{pid}/fd").iterdir():
                try:
                    target = os.readlink(path)
                except FileNotFoundError:
                    continue
                if target.startswith("socket:["):
                    inodes.add(target[8:-1])
            lines = Path(f"/proc/{pid}/net/tcp").read_text().splitlines()[1:]
            address = f"0100007F:{port:04X}"
            return any(
                (fields := line.split())[1] == address and fields[3] == "0A" and fields[9] in inodes
                for line in lines
            )
        except FileNotFoundError:
            return False
        except (OSError, IndexError) as exc:
            raise LabError("Cannot verify owned traffic listener") from exc


class Traffic:
    def __init__(self, config, lab, backend=None):
        self.backend = backend or Backend()
        self.config = config.get("traffic", config)
        try:
            c = self.config
            self.port = c["port"]
            if type(self.port) is not int or not 1024 <= self.port <= 65535:
                raise ValueError()
            self.tools = {key: str(Path(c[key])) for key in ("mitmdump", "openssl")}
            self.cacert = Path(c["cacert"])
            if not self.cacert.is_absolute() or any(
                not Path(p).is_absolute() for p in self.tools.values()
            ):
                raise ValueError()
            self.fixture = None
            if c.get("fixture") is not None:
                f = c["fixture"]
                port = f["port"]
                if type(port) is not int or not 1024 <= port <= 65535:
                    raise ValueError()
                cert = Path(f["caCertificate"])
                if not cert.is_absolute():
                    raise ValueError()
                self.fixture = {
                    "host": host_name(f["host"]),
                    "port": port,
                    "caCertificate": str(cert),
                }
        except (KeyError, TypeError, ValueError) as exc:
            raise LabError("Invalid traffic configuration") from exc
        self.state = safe_path(lab.state)
        self.root = self.state / "traffic"
        self.owner_file = self.root / "owner.json"
        self.lease_file = self.root / "lease.json"
        self.lock_file = self.root / "lock"
        self.identity = {"version": 1, "uid": os.getuid(), "state": str(self.state)}
        # No inherited Python overrides, proxy credentials, mitm config, client
        # certificates, or user home. The Nix wrappers supply their dependencies.
        self.env = {"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", "HOME": str(self.root)}
        self.check_paths()

    def check_paths(self):
        safe_path(self.state)
        if self.state.exists() and (
            not self.state.is_dir() or self.state.stat().st_uid != os.getuid()
        ):
            raise LabError("Lab state is not owned by the caller")
        if check_entry(self.root, directory=True):
            for path in self.root.rglob("*"):
                check_entry(path, directory=path.is_dir())

    @contextlib.contextmanager
    def lock(self, readonly=False):
        self.check_paths()
        if readonly and not self.lock_file.exists():
            yield
            return
        if not readonly:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        check_entry(self.lock_file)
        flags = os.O_RDONLY if readonly else os.O_RDWR | os.O_CREAT
        fd = os.open(self.lock_file, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_nlink != 1
                or info.st_mode & 0o077
            ):
                raise LabError("Invalid traffic lock ownership")
            try:
                fcntl.flock(fd, (fcntl.LOCK_SH if readonly else fcntl.LOCK_EX) | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise LabError("Another traffic operation holds the lock") from exc
            self.check_paths()
            yield
        finally:
            os.close(fd)

    def owner(self, create=False):
        if not self.owner_file.exists():
            if not create:
                if self.root.exists() and any(p.name != "lock" for p in self.root.iterdir()):
                    raise LabError("Unowned traffic state")
                return None
            if any(p.name != "lock" for p in self.root.iterdir()):
                raise LabError("Refusing to claim foreign traffic state")
            write_json(self.owner_file, {**self.identity, "token": uuid.uuid4().hex})
        owner = read_json(self.owner_file)
        if any(owner.get(k) != v for k, v in self.identity.items()) or not re.fullmatch(
            r"[0-9a-f]{32}", str(owner.get("token", ""))
        ):
            raise LabError("Traffic owner mismatch")
        return owner

    def lease(self):
        owner = self.owner()
        if not self.lease_file.exists():
            return None
        lease = read_json(self.lease_file)
        if not owner or lease.get("token") != owner["token"]:
            raise LabError("Foreign traffic lease")
        pid, process = lease.get("pid"), lease.get("process")
        if type(pid) is not int or pid <= 1 or not isinstance(process, dict):
            raise LabError("Invalid traffic process lease")
        if (
            type(process.get("uid")) is not int
            or process["uid"] != os.getuid()
            or type(process.get("session")) is not int
            or process["session"] != pid
            or not isinstance(process.get("start"), str)
            or not process["start"].isdigit()
            or not isinstance(process.get("boot"), str)
            or not process["boot"].strip()
        ):
            raise LabError("Foreign traffic process/session lease")
        run = lease.get("run")
        if not isinstance(run, str) or not re.fullmatch(r"run-[0-9a-f]{32}", run):
            raise LabError("Invalid traffic run lease")
        if type(lease.get("proxyPort")) is not int or not 1024 <= lease["proxyPort"] <= 65535:
            raise LabError("Invalid traffic port lease")
        return lease

    def live(self, lease):
        if not lease:
            return None
        # lease() validates ownership and identity fields before this boot check.
        # An earlier host boot proves death without inspecting a possibly reused PID.
        if lease["process"]["boot"] != self.backend.host_boot():
            return None
        process = self.backend.process(lease["pid"])
        if process is not None and process != lease["process"]:
            raise LabError("Traffic PID reuse/identity mismatch; refusing operation")
        return process

    def tool(self, name, args):
        executable = self.tools[name]
        if not os.path.isfile(executable) or not os.access(executable, os.X_OK):
            raise LabError(f"Configured {name} executable is unavailable")
        return self.backend.run([executable, *args], self.env, timeout=5)

    def public_certificates(self, path):
        # Explicit public inputs only; never put a private key into the trust bundle.
        try:
            # Public bundles may be Nix-store symlinks, but never pipes/devices.
            # Nonblocking open plus fstat keeps malformed config finite as well.
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 8 * 1024 * 1024:
                    raise LabError("Public upstream CA bundle must be a bounded regular file")
                value = stream.read(8 * 1024 * 1024 + 1)
        except OSError as exc:
            raise LabError("Public upstream CA bundle is unavailable") from exc
        if (
            len(value) > 8 * 1024 * 1024
            or b"PRIVATE KEY" in value
            or b"-----BEGIN CERTIFICATE-----" not in value
        ):
            raise LabError("Expected a public certificate-only upstream CA bundle")
        return value

    def result(self, state, lease=None, **extra):
        result = {"status": "ok", "state": state, **extra}
        if lease:
            run = self.root / lease["run"]
            result.update(
                {
                    "proxyPort": lease["proxyPort"],
                    "captureMode": lease.get("captureMode", "exact-hosts"),
                    "allowedHosts": lease.get("allowedHosts", []),
                    "caCertificate": str(run / "caCertificate.pem"),
                    "captureArtifact": str(run / "capture.flows"),
                }
            )
        return result

    def status(self):
        # Intentionally do not call live(), tools, clock, port probes, or chmod.
        with self.lock(readonly=True):
            lease = self.lease()
            stale = bool(lease and lease["process"]["boot"] != self.backend.host_boot())
            return self.result(
                "stopped"
                if stale
                else ("uninspected" if lease else ("stopped" if self.owner() else "absent")),
                lease,
                inspection="lease-only",
                processVerified=False,
                staleLease=stale,
            )

    def start(self, allowed_hosts=None):
        capture_all = allowed_hosts is None
        if not capture_all and (
            not isinstance(allowed_hosts, list) or not allowed_hosts or len(allowed_hosts) > 128
        ):
            raise LabError("Select capture-all or a nonempty exact traffic host list")
        hosts = [] if capture_all else sorted(set(host_name(host) for host in allowed_hosts))
        if self.fixture and not capture_all and self.fixture["host"] not in hosts:
            raise LabError("Fixture host must be explicitly allowed")
        with self.lock():
            bundle = self.public_certificates(self.cacert)
            if self.fixture:
                bundle += b"\n" + self.public_certificates(self.fixture["caCertificate"])
            settings = {
                "version": VERSION,
                "tools": self.tools,
                "port": self.port,
                "cacert": str(self.cacert),
                "fixture": self.fixture,
                "allowedHosts": hosts,
                "captureAll": capture_all,
                "bundleDigest": hashlib.sha256(bundle).hexdigest(),
            }
            fingerprint = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
            lease = self.lease()
            if self.live(lease):
                if lease.get("configuration") != fingerprint:
                    raise LabError("Live traffic configuration/allowlist mismatch; stop first")
                if not self.backend.listening(lease["pid"], self.port):
                    raise LabError("Owned traffic process has no verified local listener")
                self.validate_run(lease, hosts, capture_all)
                return self.result("running", lease, reused=True)
            if lease:
                self.backend.reap(lease["pid"])
            if not self.backend.port_free(self.port):
                raise LabError("Traffic proxy port already occupied; refusing foreign listener")
            code, output = self.tool("mitmdump", ["--version"])
            if code or not re.search(r"(?m)^Mitmproxy:\s*12\.2\.3\s*$", output):
                raise LabError("Only pinned mitmdump 12.2.3 is supported")
            owner = self.owner(create=True)
            run = self.root / ("run-" + uuid.uuid4().hex)
            run.mkdir(mode=0o700)
            # Keep one private CA per lab rather than trusting a growing set of
            # fresh authorities after each capture restart.
            confdir = self.root / "ca"
            confdir.mkdir(mode=0o700, exist_ok=True)
            write_file(run / "upstream-ca.pem", bundle)
            code, _ = self.tool(
                "openssl",
                [
                    "crl2pkcs7",
                    "-nocrl",
                    "-certfile",
                    str(run / "upstream-ca.pem"),
                    "-out",
                    os.devnull,
                ],
            )
            if code:
                raise LabError("Invalid public upstream certificate bundle")
            write_file(run / "capture.flows", b"")
            run_config = {
                "captureAll": capture_all,
                "allowedHosts": hosts,
                "fixture": self.fixture,
                "readyFile": str(run / "ready.json"),
            }
            write_file(run / "config.json", json.dumps(run_config, sort_keys=True).encode(), 0o400)
            argv = [
                self.tools["mitmdump"],
                "--mode",
                "regular",
                "--listen-host",
                "127.0.0.1",
                "--listen-port",
                str(self.port),
                "--set",
                f"confdir={confdir}",
                "--set",
                "connection_strategy=lazy",
                "--set",
                "upstream_cert=false",
                "--set",
                "ssl_insecure=false",
                "--set",
                f"ssl_verify_upstream_trusted_ca={run / 'upstream-ca.pem'}",
                "--set",
                "termlog_verbosity=error",
                "--set",
                "flow_detail=0",
                "-q",
                "-s",
                str(Path(__file__).with_name("capture_addon.py")),
                "-w",
                str(run / "capture.flows"),
            ]
            env = {**self.env, "PI_RE_TRAFFIC_CONFIG": str(run / "config.json")}
            write_file(run / "mitmdump.log", b"")
            fd = os.open(run / "mitmdump.log", os.O_WRONLY | os.O_NOFOLLOW)
            launched = None
            try:
                # Defer Ctrl-C across spawn/identity/publication, so cancellation
                # never lands in the gap before the owned lease is available.
                mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
                try:
                    with os.fdopen(fd, "w") as log:
                        pid = self.backend.spawn(argv, env, log)
                    process = self.backend.process(pid)
                    if (
                        not process
                        or process.get("session") != pid
                        or process.get("uid") != os.getuid()
                    ):
                        raise LabError(
                            "Traffic process exited or could not establish an owned session"
                        )
                    launched = {
                        "token": owner["token"],
                        "pid": pid,
                        "process": process,
                        "run": run.name,
                        "configuration": fingerprint,
                        "proxyPort": self.port,
                        "captureMode": "all" if capture_all else "exact-hosts",
                        "allowedHosts": hosts,
                    }
                    write_json(self.lease_file, launched)
                finally:
                    signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                lease = launched
                deadline = self.backend.now() + START_SECONDS
                while True:
                    self.check_paths()
                    if not self.live(lease):
                        raise LabError("Owned traffic process exited during startup")
                    if (
                        self.backend.listening(pid, self.port)
                        and (run / "ready.json").exists()
                        and (confdir / "mitmproxy-ca-cert.pem").exists()
                    ):
                        if read_json(run / "ready.json") != {"configured": True, "version": 1}:
                            raise LabError("Traffic scope initialization failed")
                        # mitmdump's umask keeps private CA/key/p12/DH material 0600.
                        # Enforce that explicitly after checking every generated path.
                        for path in confdir.rglob("*"):
                            if path.is_file():
                                path.chmod(0o600)
                        public = confdir / "mitmproxy-ca-cert.pem"
                        self.verify_ca(public)
                        write_file(run / "caCertificate.pem", self.public_certificates(public))
                        if not self.live(lease):
                            raise LabError("Owned traffic process exited during startup")
                        return self.result("running", lease, reused=False)
                    if self.backend.now() >= deadline:
                        raise LabError("Traffic startup deadline exceeded", timeout=True)
                    self.backend.sleep(0.1)
            except BaseException:
                # Includes failed lease publication and cancellation. Use the captured
                # verified identity, not untrusted/stale metadata or a global kill.
                if launched:
                    self.stop_process(launched, force=True)
                    if self.lease_file.exists() and read_json(self.lease_file) == launched:
                        self.lease_file.unlink()
                raise

    def validate_run(self, lease, hosts, capture_all):
        if (
            lease.get("captureMode") != ("all" if capture_all else "exact-hosts")
            or lease.get("allowedHosts") != hosts
        ):
            raise LabError("Owned traffic lease scope metadata mismatch")
        run = self.root / lease["run"]
        if not check_entry(run, directory=True) or not check_entry(
            self.root / "ca", directory=True
        ):
            raise LabError("Owned traffic run is incomplete")
        for name in ("capture.flows", "upstream-ca.pem", "mitmdump.log"):
            if not check_entry(run / name):
                raise LabError("Owned traffic run is incomplete")
        config = run / "config.json"
        if (
            read_json(config)
            != {
                "captureAll": capture_all,
                "allowedHosts": hosts,
                "fixture": self.fixture,
                "readyFile": str(run / "ready.json"),
            }
            or stat.S_IMODE(config.stat().st_mode) != 0o400
        ):
            raise LabError("Owned traffic run configuration mismatch")
        if read_json(run / "ready.json") != {"configured": True, "version": 1}:
            raise LabError("Owned traffic scope initialization mismatch")
        self.verify_ca(run / "caCertificate.pem")

    def verify_ca(self, path):
        if not check_entry(path):
            raise LabError("Owned public MITM CA certificate is missing")
        self.public_certificates(path)
        code, _ = self.tool("openssl", ["x509", "-in", str(path), "-checkend", "0", "-noout"])
        if code:
            raise LabError("Owned MITM CA certificate is invalid or expired")

    def wait_stopped(self, lease, seconds):
        deadline = self.backend.now() + seconds
        while self.live(lease) and self.backend.now() < deadline:
            self.backend.sleep(0.1)

    def stop_process(self, lease, force=False):
        process = self.live(lease)
        if process:
            try:
                self.backend.terminate(
                    lease["pid"], process, signal.SIGKILL if force else signal.SIGTERM
                )
                self.wait_stopped(lease, STOP_SECONDS)
            except KeyboardInterrupt:
                process = self.live(lease)
                if process:
                    self.backend.terminate(lease["pid"], process, signal.SIGKILL)
                    self.wait_stopped(lease, 2)
                self.backend.reap(lease["pid"])
                raise
            process = self.live(lease)
            if process:
                self.backend.terminate(lease["pid"], process, signal.SIGKILL)
                self.wait_stopped(lease, 2)
            if self.live(lease):
                raise LabError("Owned traffic process did not stop", timeout=True)
        self.backend.reap(lease["pid"])

    def stop(self):
        with self.lock():
            lease = self.lease()
            if lease:
                self.stop_process(lease)
                self.lease_file.unlink()
            return self.result("stopped", lease)
