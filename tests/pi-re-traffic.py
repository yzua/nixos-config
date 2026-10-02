#!/usr/bin/env python3
"""Offline traffic adapter tests. No mitmdump servers, devices or downloads."""

import importlib.util
import json
import os
import signal
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1] / "home-manager/modules/ai/pi-re"
sys.path.insert(0, str(SOURCE))
import traffic  # noqa: E402

PUBLIC = b"-----BEGIN CERTIFICATE-----\npublic-fixture\n-----END CERTIFICATE-----\n"


class FakeBackend:
    def __init__(self):
        self.clock = 0
        self.calls = []
        self.spawns = []
        self.processes = {}
        self.signals = []
        self.reaped = []
        self.pid = 4100
        self.free = True
        self.ready = True
        self.listens = True
        self.term_works = True
        self.kill_works = True
        self.version = "Mitmproxy: 12.2.3\nPython: 3.13\n"
        self.openssl_code = 0
        self.process_reads = 0
        self.process_pids = []
        self.probes = 0
        self.boot = "test-boot"

    def host_boot(self):
        return self.boot

    def now(self):
        return self.clock

    def sleep(self, seconds):
        self.clock += seconds

    def process(self, pid):
        self.process_reads += 1
        self.process_pids.append(pid)
        value = self.processes.get(pid)
        return value.copy() if value else None

    def port_free(self, port):
        self.probes += 1
        return self.free

    def listening(self, pid, port):
        self.probes += 1
        return self.listens and pid in self.processes

    def run(self, argv, env, timeout, input=None):
        self.calls.append((argv, env, timeout))
        assert 0 < timeout <= 5
        if Path(argv[0]).name == "mitmdump":
            assert argv[1:] == ["--version"]
            return 0, self.version
        assert Path(argv[0]).name == "openssl"
        return self.openssl_code, "private-auth-body-canary"

    def spawn(self, argv, env, log):
        self.spawns.append((argv, env))
        self.processes[self.pid] = {
            "start": "123",
            "session": self.pid,
            "uid": os.getuid(),
            "boot": self.host_boot(),
        }
        path = Path(env["PI_RE_TRAFFIC_CONFIG"])
        config = json.loads(path.read_text())
        if self.ready:
            traffic.write_json(Path(config["readyFile"]), {"configured": True, "version": 1})
        confdir = Path(
            next(arg.removeprefix("confdir=") for arg in argv if arg.startswith("confdir="))
        )
        if not (confdir / "mitmproxy-ca-cert.pem").exists():
            traffic.write_file(confdir / "mitmproxy-ca-cert.pem", PUBLIC)
            traffic.write_file(
                confdir / "mitmproxy-ca.pem", b"private material - never read by adapter"
            )
        return self.pid

    def terminate(self, pid, identity, sig):
        assert self.process(pid) == identity
        self.signals.append((pid, sig))
        if (sig == signal.SIGTERM and self.term_works) or (
            sig == signal.SIGKILL and self.kill_works
        ):
            self.processes.pop(pid, None)

    def reap(self, pid):
        self.reaped.append(pid)


class TrafficTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.lab = types.SimpleNamespace(state=self.base / "lab")
        self.config = {"port": 8089, "cacert": str(self.base / "public.pem")}
        (self.base / "public.pem").write_bytes(PUBLIC)
        for tool in ("mitmdump", "openssl"):
            path = self.base / tool
            path.write_text("never execute offline fixture\n")
            path.chmod(0o700)
            self.config[tool] = str(path)
        self.backend = FakeBackend()
        self.runner = traffic.Traffic({"traffic": self.config}, self.lab, self.backend)
        self.hosts = ["pi-re.fixture.test"]

    def start(self, hosts=None):
        return self.runner.start(self.hosts if hosts is None else hosts)

    def snapshot(self):
        if not self.lab.state.exists():
            return None
        return {
            str(p.relative_to(self.lab.state)): (
                p.stat().st_mode,
                p.stat().st_mtime_ns,
                p.read_bytes() if p.is_file() else None,
            )
            for p in self.lab.state.rglob("*")
        }

    def test_start_returns_locations_not_content_and_private_material(self):
        result = self.start()
        self.assertEqual(result["state"], "running")
        self.assertEqual(result["proxyPort"], 8089)
        self.assertEqual(Path(result["caCertificate"]).read_bytes(), PUBLIC)
        self.assertTrue(result["captureArtifact"].endswith(".flows"))
        self.assertNotIn("private", json.dumps(result))
        for path in self.runner.root.rglob("*"):
            self.assertEqual(path.stat().st_mode & 0o077, 0)
        run = Path(result["caCertificate"]).parent
        self.assertEqual(
            stat.S_IMODE((self.runner.root / "ca/mitmproxy-ca.pem").stat().st_mode), 0o600
        )
        self.assertEqual(stat.S_IMODE((run / "config.json").stat().st_mode), 0o400)
        argv, env = self.backend.spawns[0]
        self.assertIn("127.0.0.1", argv)
        self.assertIn("regular", argv)
        self.assertIn("connection_strategy=lazy", argv)
        self.assertIn("upstream_cert=false", argv)
        self.assertIn("ssl_insecure=false", argv)
        self.assertNotIn("ssl_insecure=true", argv)
        self.assertIn("-w", argv)
        self.assertEqual(argv[argv.index("-w") + 1], result["captureArtifact"])
        self.assertEqual(
            json.loads(Path(env["PI_RE_TRAFFIC_CONFIG"]).read_text())["allowedHosts"], self.hosts
        )
        self.assertNotIn("PYTHONPATH", env)
        self.assertEqual(env["HOME"], str(self.runner.root))

    def test_capture_all_default_is_explicit_in_config_and_reuse(self):
        result = self.runner.start()
        self.assertEqual(result["captureMode"], "all")
        argv, env = self.backend.spawns[0]
        policy = json.loads(Path(env["PI_RE_TRAFFIC_CONFIG"]).read_text())
        self.assertTrue(policy["captureAll"])
        self.assertEqual(policy["allowedHosts"], [])
        self.assertIn("ssl_insecure=false", argv)
        self.assertTrue(self.runner.start()["reused"])
        with self.assertRaisesRegex(traffic.LabError, "mismatch"):
            self.runner.start(self.hosts)
        self.runner.stop()
        restricted = self.runner.start(self.hosts)
        self.assertEqual(restricted["captureMode"], "exact-hosts")
        with self.assertRaisesRegex(traffic.LabError, "mismatch"):
            self.runner.start()

    def test_reuse_refuses_lease_scope_that_disagrees_with_actual_policy(self):
        self.runner.start()
        lease = traffic.read_json(self.runner.lease_file)
        traffic.write_json(
            self.runner.lease_file,
            {**lease, "captureMode": "exact-hosts", "allowedHosts": self.hosts},
        )
        with self.assertRaisesRegex(traffic.LabError, "scope metadata mismatch"):
            self.runner.start()
        # Wrong descriptive scope must not prevent identity-bound cleanup.
        self.runner.stop()
        self.assertFalse(self.backend.processes)

    def test_ca_is_stable_across_capture_restarts(self):
        first = self.start()
        certificate = Path(first["caCertificate"]).read_bytes()
        key = self.runner.root / "ca/mitmproxy-ca.pem"
        identity = key.stat().st_ino
        self.runner.stop()
        second = self.start()
        self.assertEqual(Path(second["caCertificate"]).read_bytes(), certificate)
        self.assertEqual(key.stat().st_ino, identity)
        self.assertNotEqual(first["captureArtifact"], second["captureArtifact"])

    def test_valid_live_lease_reused_only_same_config_and_scope(self):
        first = self.start()
        second = self.start(["PI-RE.FIXTURE.TEST", "pi-re.fixture.test"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["captureArtifact"], second["captureArtifact"])
        self.assertEqual(len(self.backend.spawns), 1)
        with self.assertRaisesRegex(traffic.LabError, "mismatch"):
            self.start(["other.fixture.test"])
        self.config["port"] = 8090
        changed = traffic.Traffic(self.config, self.lab, self.backend)
        with self.assertRaisesRegex(traffic.LabError, "mismatch"):
            changed.start(self.hosts)
        (self.base / "public.pem").write_bytes(PUBLIC + b"\nchanged public trust\n")
        with self.assertRaisesRegex(traffic.LabError, "mismatch"):
            self.start()
        self.assertFalse(self.backend.signals)

    def test_status_is_strictly_readonly_and_lease_only(self):
        self.assertEqual(self.runner.status()["state"], "absent")
        self.assertFalse(self.lab.state.exists())
        self.assertFalse(self.backend.calls)
        self.start()
        before = self.snapshot()
        reads, probes, calls = (
            self.backend.process_reads,
            self.backend.probes,
            list(self.backend.calls),
        )
        # No process inspection even if the lease's process has exited/reused PID.
        self.backend.processes[self.backend.pid]["start"] = "999"
        result = self.runner.status()
        self.assertEqual(result["state"], "uninspected")
        self.assertEqual(result["inspection"], "lease-only")
        self.assertFalse(result["processVerified"])
        self.assertEqual(reads, self.backend.process_reads)
        self.assertEqual(probes, self.backend.probes)
        self.assertEqual(calls, self.backend.calls)
        self.assertEqual(before, self.snapshot())

    def test_foreign_port_rejected_without_spawn_or_claim(self):
        self.backend.free = False
        with self.assertRaisesRegex(traffic.LabError, "foreign listener"):
            self.start()
        self.assertFalse(self.backend.spawns)
        self.assertFalse(self.backend.calls)
        self.assertFalse(self.runner.owner_file.exists())
        self.assertFalse(self.backend.signals)

    def test_start_does_not_mistake_foreign_listener_for_owned(self):
        self.backend.listens = False
        with self.assertRaises(traffic.LabError) as caught:
            self.start()
        self.assertTrue(caught.exception.timeout)
        self.assertLess(self.backend.clock, traffic.START_SECONDS + 1)
        self.assertEqual(self.backend.signals, [(4100, signal.SIGKILL)])
        self.assertFalse(self.runner.lease_file.exists())

    def test_addon_acknowledgement_required(self):
        self.backend.ready = False
        with self.assertRaises(traffic.LabError) as caught:
            self.start()
        self.assertTrue(caught.exception.timeout)
        self.assertFalse(self.backend.processes)

    def test_wrong_version_and_invalid_trust_fail_without_launch(self):
        self.backend.version = "Mitmproxy: 12.2.4\n"
        with self.assertRaisesRegex(traffic.LabError, "12.2.3"):
            self.start()
        self.assertFalse(self.backend.spawns)
        self.backend.version = "Mitmproxy: 12.2.3\n"
        self.backend.openssl_code = 1
        with self.assertRaisesRegex(traffic.LabError, "certificate bundle") as caught:
            self.start()
        self.assertNotIn("canary", str(caught.exception))
        self.assertFalse(self.backend.spawns)

    def test_start_expired_ca_cleans_owned_process(self):
        original = self.backend.run

        def run(argv, env, timeout, input=None):
            if "-checkend" in argv:
                return 1, "private-auth-body-canary"
            return original(argv, env, timeout, input)

        with mock.patch.object(self.backend, "run", side_effect=run):
            with self.assertRaisesRegex(traffic.LabError, "expired"):
                self.start()
        self.assertEqual(self.backend.signals, [(4100, signal.SIGKILL)])

    def test_failed_lease_publication_cleans_own_process(self):
        original = traffic.write_json

        def write(path, value, mode=0o600):
            if path == self.runner.lease_file:
                raise OSError("offline publication failure")
            return original(path, value, mode)

        with mock.patch.object(traffic, "write_json", side_effect=write):
            with self.assertRaises(OSError):
                self.start()
        self.assertFalse(self.backend.processes)
        self.assertEqual(self.backend.signals, [(4100, signal.SIGKILL)])

    def test_cancelled_start_cleans_only_own_process(self):
        self.backend.ready = False
        self.backend.processes[5000] = {"foreign": True}
        with mock.patch.object(self.backend, "sleep", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.start()
        self.assertEqual(self.backend.signals, [(4100, signal.SIGKILL)])
        self.assertIn(5000, self.backend.processes)
        self.assertFalse(self.runner.lease_file.exists())

    def test_ctrl_c_during_spawn_is_deferred_until_owned_lease(self):
        original = self.backend.spawn

        def spawn(argv, env, log):
            pid = original(argv, env, log)
            signal.raise_signal(signal.SIGINT)
            return pid

        with mock.patch.object(self.backend, "spawn", side_effect=spawn):
            with self.assertRaises(KeyboardInterrupt):
                self.start()
        self.assertEqual(self.backend.signals, [(4100, signal.SIGKILL)])
        self.assertFalse(self.backend.processes)
        self.assertFalse(self.runner.lease_file.exists())

    def reboot_with_reused_pid(self):
        result = self.start()
        old_pid = self.backend.pid
        self.backend.boot = "next-host-boot"
        foreign = {
            "start": "900",
            "session": old_pid,
            "uid": os.getuid() + 1,
            "boot": self.backend.host_boot(),
        }
        self.backend.processes[old_pid] = foreign
        self.backend.process_reads = 0
        self.backend.process_pids.clear()
        self.backend.calls.clear()
        return result, old_pid, foreign

    def test_previous_host_boot_status_is_stopped_without_process_inspection(self):
        _, old_pid, foreign = self.reboot_with_reused_pid()
        before = self.snapshot()
        probes = self.backend.probes
        result = self.runner.status()
        self.assertEqual(result["state"], "stopped")
        self.assertTrue(result["staleLease"])
        self.assertEqual(result["inspection"], "lease-only")
        self.assertFalse(result["processVerified"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.backend.probes, probes)
        self.assertEqual(self.backend.process_reads, 0)
        self.assertFalse(self.backend.calls)
        self.assertFalse(self.backend.signals)
        self.assertEqual(self.backend.processes[old_pid], foreign)

    def test_previous_host_boot_stop_does_not_inspect_or_signal_reused_pid(self):
        first, old_pid, foreign = self.reboot_with_reused_pid()
        result = self.runner.stop()
        self.assertEqual(result["state"], "stopped")
        self.assertFalse(self.runner.lease_file.exists())
        self.assertTrue(Path(first["captureArtifact"]).exists())
        self.assertEqual(self.backend.process_reads, 0)
        self.assertFalse(self.backend.calls)
        self.assertFalse(self.backend.signals)
        self.assertEqual(self.backend.processes[old_pid], foreign)

    def test_previous_host_boot_start_preserves_foreign_pid_and_old_capture(self):
        first, old_pid, foreign = self.reboot_with_reused_pid()
        capture = Path(first["captureArtifact"])
        capture.write_bytes(b"private capture canary")
        self.backend.pid += 1
        second = self.start()
        self.assertEqual(second["state"], "running")
        self.assertNotEqual(first["captureArtifact"], second["captureArtifact"])
        self.assertEqual(capture.read_bytes(), b"private capture canary")
        self.assertEqual(len(self.backend.spawns), 2)
        lease = traffic.read_json(self.runner.lease_file)
        self.assertEqual(lease["pid"], self.backend.pid)
        self.assertEqual(lease["process"]["boot"], self.backend.host_boot())
        self.assertNotIn(old_pid, self.backend.process_pids)
        self.assertFalse(self.backend.signals)
        self.assertEqual(self.backend.processes[old_pid], foreign)

    def test_previous_host_boot_does_not_bypass_lease_validation(self):
        self.reboot_with_reused_pid()
        lease = traffic.read_json(self.runner.lease_file)
        for changed in (
            {**lease, "token": "foreign"},
            {**lease, "pid": True},
            {**lease, "process": None},
            {**lease, "run": "foreign"},
            {**lease, "proxyPort": True},
            *(
                {**lease, "process": {**lease["process"], field: value}}
                for field, value in (
                    ("uid", os.getuid() + 1),
                    ("uid", float(os.getuid())),
                    ("uid", False),
                    ("session", 99),
                    ("session", float(lease["pid"])),
                    ("session", True),
                    ("start", None),
                    ("start", "invalid"),
                    ("boot", None),
                    ("boot", ""),
                    ("boot", " \n\t"),
                )
            ),
        ):
            traffic.write_json(self.runner.lease_file, changed)
            for action in (self.runner.status, self.start, self.runner.stop):
                with self.subTest(changed=changed, action=action.__name__):
                    with self.assertRaises(traffic.LabError):
                        action()
        self.assertEqual(self.backend.process_reads, 0)
        self.assertFalse(self.backend.calls)
        self.assertFalse(self.backend.signals)

    def test_previous_host_boot_does_not_bypass_owner_validation(self):
        self.reboot_with_reused_pid()
        owner = traffic.read_json(self.runner.owner_file)
        for changed in ({**owner, "uid": os.getuid() + 1}, {**owner, "version": 99}, None):
            if changed is None:
                self.runner.owner_file.unlink()
            else:
                traffic.write_json(self.runner.owner_file, changed)
            for action in (self.runner.status, self.start, self.runner.stop):
                with self.subTest(changed=changed, action=action.__name__):
                    with self.assertRaises(traffic.LabError):
                        action()
        self.assertEqual(self.backend.process_reads, 0)
        self.assertFalse(self.backend.calls)
        self.assertFalse(self.backend.signals)

    def test_same_host_boot_process_identity_tampering_refuses_signals(self):
        self.start()
        for field, value in (
            ("start", "999"),
            ("boot", "other-boot"),
            ("uid", os.getuid() + 1),
            ("session", 5000),
        ):
            original = self.backend.processes[4100][field]
            self.backend.processes[4100][field] = value
            for action in (self.start, self.runner.stop):
                with self.assertRaisesRegex(traffic.LabError, "PID reuse/identity"):
                    action()
            self.backend.processes[4100][field] = original
        self.assertFalse(self.backend.signals)

    def test_foreign_token_or_session_lease_refused(self):
        self.start()
        lease = traffic.read_json(self.runner.lease_file)
        for changed in (
            {**lease, "token": "foreign"},
            {**lease, "process": {**lease["process"], "session": 1}},
        ):
            traffic.write_json(self.runner.lease_file, changed)
            with self.assertRaisesRegex(traffic.LabError, "Foreign"):
                self.runner.stop()
        self.assertFalse(self.backend.signals)

    def test_stop_term_then_kill_never_global_and_preserves_capture(self):
        result = self.start()
        self.backend.term_works = False
        self.backend.processes[5000] = {"foreign": True}
        self.assertEqual(self.runner.stop()["state"], "stopped")
        self.assertEqual(self.backend.signals, [(4100, signal.SIGTERM), (4100, signal.SIGKILL)])
        self.assertEqual(self.backend.reaped, [4100])
        self.assertIn(5000, self.backend.processes)
        self.assertFalse(self.runner.lease_file.exists())
        self.assertTrue(Path(result["captureArtifact"]).exists())
        self.assertTrue(Path(result["caCertificate"]).exists())
        self.assertEqual(self.runner.status()["state"], "stopped")

    def test_stop_timeout_finite_and_keeps_lease(self):
        self.start()
        self.backend.term_works = self.backend.kill_works = False
        with self.assertRaises(traffic.LabError) as caught:
            self.runner.stop()
        self.assertTrue(caught.exception.timeout)
        self.assertLess(self.backend.clock, traffic.STOP_SECONDS + 3)
        self.assertTrue(self.runner.lease_file.exists())

    def test_cancelled_stop_escalates_only_owned_pid(self):
        self.start()
        self.backend.term_works = False
        with mock.patch.object(self.backend, "sleep", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.runner.stop()
        self.assertEqual(self.backend.signals, [(4100, signal.SIGTERM), (4100, signal.SIGKILL)])
        self.assertFalse(self.backend.processes)

    def test_dead_lease_stop_safe_and_new_capture_not_truncated(self):
        first = self.start()
        Path(first["captureArtifact"]).write_bytes(b"body/auth canary: not returned to model")
        self.backend.processes.clear()
        self.runner.stop()
        self.assertFalse(self.backend.signals)
        second = self.start()
        self.assertNotEqual(first["captureArtifact"], second["captureArtifact"])
        self.assertIn(b"canary", Path(first["captureArtifact"]).read_bytes())
        self.assertNotIn("canary", json.dumps(second))

    def test_dead_lease_start_reaps_old_child_and_preserves_old_capture(self):
        first = self.start()
        self.backend.processes.clear()
        second = self.start()
        self.assertNotEqual(first["captureArtifact"], second["captureArtifact"])
        self.assertEqual(self.backend.reaped, [4100])
        self.assertFalse(self.backend.signals)

    def test_incomplete_live_run_not_reused(self):
        result = self.start()
        Path(result["captureArtifact"]).unlink()
        with self.assertRaisesRegex(traffic.LabError, "incomplete"):
            self.start()
        self.assertEqual(len(self.backend.spawns), 1)
        self.assertFalse(self.backend.signals)
        self.runner.stop()

    def test_nonblocking_separate_lock(self):
        self.start()
        android_lock = self.lab.state / "android-lock"
        with android_lock.open("w") as stream:
            import fcntl

            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.runner.status()
        with self.runner.lock():
            for action in (self.start, self.runner.status, self.runner.stop):
                with self.assertRaisesRegex(traffic.LabError, "holds the lock"):
                    action()

    def test_state_symlink_and_dangling_link_rejected(self):
        alias = self.base / "alias"
        alias.symlink_to(self.base, target_is_directory=True)
        with self.assertRaisesRegex(traffic.LabError, "symlinks"):
            traffic.Traffic(self.config, types.SimpleNamespace(state=alias / "lab"), self.backend)
        self.lab.state.mkdir()
        self.runner.root.symlink_to(self.base / "missing")
        with self.assertRaisesRegex(traffic.LabError, "symlinks"):
            self.start()

    def test_any_state_symlink_hardlink_or_fifo_rejected_without_mutation(self):
        self.start()
        target = self.base / "unrelated"
        target.write_text("keep")
        target.chmod(0o600)
        for kind in ("symlink", "hardlink", "fifo"):
            path = self.runner.root / "foreign"
            if kind == "symlink":
                path.symlink_to(target)
            elif kind == "hardlink":
                os.link(target, path)
            else:
                os.mkfifo(path, 0o600)
            for action in (self.start, self.runner.status, self.runner.stop):
                with self.assertRaises(traffic.LabError):
                    action()
            self.assertEqual(target.read_text(), "keep")
            path.unlink()
        self.assertFalse(self.backend.signals)

    def test_hardlinked_metadata_and_lock_rejected(self):
        self.start()
        for path in (self.runner.owner_file, self.runner.lease_file, self.runner.lock_file):
            link = self.base / "external-link"
            os.link(path, link)
            with self.assertRaisesRegex(traffic.LabError, "hardlinks"):
                self.runner.stop()
            link.unlink()
        self.assertFalse(self.backend.signals)

    def test_foreign_owner_and_publicly_writable_state_refused(self):
        self.start()
        owner = traffic.read_json(self.runner.owner_file)
        traffic.write_json(self.runner.owner_file, {**owner, "uid": os.getuid() + 1})
        with self.assertRaisesRegex(traffic.LabError, "owner mismatch"):
            self.runner.stop()
        traffic.write_json(self.runner.owner_file, owner)
        self.runner.root.chmod(0o755)
        with self.assertRaisesRegex(traffic.LabError, "private"):
            self.runner.status()

    def test_unowned_state_not_claimed(self):
        self.runner.root.mkdir(parents=True, mode=0o700)
        traffic.write_file(self.runner.root / "unknown", b"keep")
        with self.assertRaisesRegex(traffic.LabError, "Unowned"):
            self.start()
        self.assertFalse(self.runner.owner_file.exists())
        self.assertFalse(self.backend.spawns)

    def test_invalid_allowlists_rejected_before_mutation(self):
        for hosts in (
            [],
            "pi-re.fixture.test",
            ["*.test"],
            ["host:443"],
            ["https://host"],
            ["trailing.test."],
            ["-host"],
            [None],
        ):
            with self.subTest(hosts=hosts):
                with self.assertRaises(traffic.LabError):
                    self.runner.start(hosts)
                self.assertFalse(self.lab.state.exists())

    def test_fixture_trust_bundle_and_only_explicit_host(self):
        fixture_cert = self.base / "fixture.pem"
        fixture_cert.write_bytes(PUBLIC.replace(b"public-fixture", b"fixture-public-only"))
        self.config["fixture"] = {
            "host": self.hosts[0],
            "port": 9443,
            "caCertificate": str(fixture_cert),
        }
        self.runner = traffic.Traffic(self.config, self.lab, self.backend)
        with self.assertRaisesRegex(traffic.LabError, "explicitly allowed"):
            self.start(["other.test"])
        result = self.start()
        run = Path(result["caCertificate"]).parent
        trust = (run / "upstream-ca.pem").read_bytes()
        self.assertIn(b"public-fixture", trust)
        self.assertIn(b"fixture-public-only", trust)
        argv, _ = self.backend.spawns[0]
        self.assertIn(f"ssl_verify_upstream_trusted_ca={run / 'upstream-ca.pem'}", argv)
        self.assertFalse(any("ssl_insecure=true" in arg or arg == "-k" for arg in argv))

    def test_private_key_rejected_as_public_trust_input(self):
        (self.base / "public.pem").write_bytes(PUBLIC + b"-----BEGIN PRIVATE KEY-----\nsecret\n")
        with self.assertRaisesRegex(traffic.LabError, "public certificate-only"):
            self.start()
        self.assertFalse(self.backend.spawns)
        self.assertFalse(self.runner.owner_file.exists())

    def test_public_certificate_fifo_rejected_without_blocking(self):
        public = self.base / "public.pem"
        public.unlink()
        os.mkfifo(public, 0o600)
        with self.assertRaisesRegex(traffic.LabError, "regular file"):
            self.start()
        self.assertFalse(self.backend.spawns)

    def test_invalid_configuration(self):
        for key, value in (
            ("port", True),
            ("port", 0),
            ("mitmdump", "relative"),
            ("openssl", "relative"),
            ("cacert", "relative"),
            ("fixture", {"host": "*.test", "port": 9443, "caCertificate": "/public"}),
        ):
            with self.assertRaises(traffic.LabError):
                traffic.Traffic({**self.config, key: value}, self.lab, self.backend)


class PidfdTests(unittest.TestCase):
    def test_only_verified_pidfd_signaled_and_always_closed(self):
        backend = traffic.Backend()
        identity = {"start": "1", "session": 4200, "uid": os.getuid(), "boot": "boot"}
        with (
            mock.patch.object(traffic.os, "pidfd_open", return_value=44) as opened,
            mock.patch.object(traffic.os, "close") as closed,
            mock.patch.object(signal, "pidfd_send_signal") as sent,
        ):
            with mock.patch.object(backend, "process", return_value=identity):
                backend.terminate(4200, identity, signal.SIGTERM)
            opened.assert_called_once_with(4200)
            sent.assert_called_once_with(44, signal.SIGTERM)
            closed.assert_called_once_with(44)
            sent.reset_mock()
            closed.reset_mock()
            with mock.patch.object(backend, "process", return_value={**identity, "start": "2"}):
                with self.assertRaisesRegex(traffic.LabError, "identity changed"):
                    backend.terminate(4200, identity, signal.SIGKILL)
            sent.assert_not_called()
            closed.assert_called_once_with(44)

    def test_missing_process_never_signaled(self):
        with (
            mock.patch.object(traffic.os, "pidfd_open", side_effect=ProcessLookupError),
            mock.patch.object(signal, "pidfd_send_signal") as sent,
        ):
            traffic.Backend().terminate(4200, {}, signal.SIGTERM)
        sent.assert_not_called()

    def test_spawn_has_private_umask_and_owned_session(self):
        backend = traffic.Backend()
        with mock.patch.object(traffic.subprocess, "Popen") as popen:
            popen.return_value.pid = 4200
            self.assertEqual(backend.spawn(["/tool"], {"HOME": "/private"}, object()), 4200)
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertEqual(popen.call_args.kwargs["umask"], 0o077)

    def test_readiness_requires_own_loopback_listener_inode(self):
        backend = traffic.Backend()
        fields = "0: 0100007F:1F99 00000000:0000 0A 0 0 0 0 0 111\n"
        with (
            mock.patch.object(Path, "iterdir", return_value=iter([Path("/proc/4200/fd/5")])),
            mock.patch.object(os, "readlink", return_value="socket:[111]"),
            mock.patch.object(Path, "read_text", return_value="header\n" + fields),
        ):
            self.assertTrue(backend.listening(4200, 8089))
        with (
            mock.patch.object(Path, "iterdir", return_value=iter([Path("/proc/4200/fd/5")])),
            mock.patch.object(os, "readlink", return_value="socket:[222]"),
            mock.patch.object(Path, "read_text", return_value="header\n" + fields),
        ):
            self.assertFalse(backend.listening(4200, 8089))


# Import the real addon with a tiny mitmproxy event seam; tests stay dependency-
# free and exercise its actual denial/mapping hooks, never a live proxy server.
mitm = types.ModuleType("mitmproxy")
mitm.ctx = types.SimpleNamespace(
    options=types.SimpleNamespace(
        connection_strategy="lazy", upstream_cert=False, ssl_insecure=False
    )
)
mitm.exceptions = types.SimpleNamespace(OptionsError=ValueError)
mitm.http = types.SimpleNamespace(
    Response=types.SimpleNamespace(
        make=lambda code, body, headers: types.SimpleNamespace(
            status_code=code, content=body, headers=headers
        )
    )
)
with mock.patch.dict(sys.modules, {"mitmproxy": mitm}):
    spec = importlib.util.spec_from_file_location(
        "pi_re_capture_addon", SOURCE / "capture_addon.py"
    )
    addon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(addon)


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name) / ("run-" + "a" * 32)
        self.run.mkdir(mode=0o700)
        self.config = {
            "allowedHosts": ["pi-re.fixture.test"],
            "fixture": {
                "host": "pi-re.fixture.test",
                "port": 9443,
                "caCertificate": "/public-fixture.pem",
            },
            "readyFile": str(self.run / "ready.json"),
        }
        self.path = self.run / "config.json"
        traffic.write_file(self.path, json.dumps(self.config).encode(), 0o400)
        self.scope = addon.CaptureScope()
        with mock.patch.dict(os.environ, {"PI_RE_TRAFFIC_CONFIG": str(self.path)}):
            self.scope.load(None)
        mitm.ctx.options = types.SimpleNamespace(
            connection_strategy="lazy", upstream_cert=False, ssl_insecure=False
        )

    def flow(self, host, authority=None):
        return types.SimpleNamespace(
            request=types.SimpleNamespace(host=host, host_header=authority), response=None
        )

    def connection(self, host, sni=None):
        return types.SimpleNamespace(
            server=types.SimpleNamespace(address=(host, 443), sni=sni, error=None)
        )

    def all_scope(self):
        self.path.chmod(0o600)
        self.path.write_text(json.dumps({**self.config, "captureAll": True, "allowedHosts": []}))
        self.path.chmod(0o400)
        scope = addon.CaptureScope()
        with mock.patch.dict(os.environ, {"PI_RE_TRAFFIC_CONFIG": str(self.path)}):
            scope.load(None)
        return scope

    def test_capture_all_discovers_domains_and_ip_without_disabling_tls(self):
        scope = self.all_scope()
        for host in ("unknown.test", "127.0.0.1", "2001:db8::1"):
            flow = self.flow(host, host)
            scope.http_connect(flow)
            scope.requestheaders(flow)
            self.assertIsNone(flow.response)
            data = self.connection(host, "cdn.test")
            scope.server_connect(data)
            self.assertIsNone(data.server.error)
            self.assertEqual(data.server.address, (host, 443))
        fixture = self.connection("pi-re.fixture.test")
        scope.server_connect(fixture)
        self.assertEqual(fixture.server.address, ("127.0.0.1", 9443))
        self.assertFalse(mitm.ctx.options.ssl_insecure)

    def test_capture_all_still_fails_closed_on_invalid_upstream_options(self):
        scope = self.all_scope()
        mitm.ctx.options.ssl_insecure = True
        with self.assertRaises(ValueError):
            scope.running()
        flow = self.flow("unknown.test")
        scope.http_connect(flow)
        self.assertEqual(flow.response.status_code, 403)

    def test_capture_all_policy_must_be_boolean_and_unambiguous(self):
        for policy in (
            {"captureAll": "true", "allowedHosts": []},
            {"captureAll": True, "allowedHosts": ["host.test"]},
            {"captureAll": False, "allowedHosts": []},
        ):
            self.path.chmod(0o600)
            self.path.write_text(json.dumps({**self.config, **policy}))
            self.path.chmod(0o400)
            with mock.patch.dict(os.environ, {"PI_RE_TRAFFIC_CONFIG": str(self.path)}):
                with self.assertRaises(ValueError):
                    addon.CaptureScope().load(None)

    def test_connect_and_plain_http_scope_denied_exactly(self):
        for host in (
            "foreign.test",
            "evil.pi-re.fixture.test",
            "pi-re.fixture.test.evil",
            "127.0.0.1",
            "pi-re.fixture.test.",
            "*.test",
        ):
            for hook in (self.scope.http_connect, self.scope.requestheaders):
                flow = self.flow(host, host)
                hook(flow)
                self.assertEqual(flow.response.status_code, 403)
                self.assertNotIn(host.encode(), flow.response.content)
            data = self.connection(host)
            self.scope.server_connect(data)
            self.assertEqual(data.server.error, addon.DENIED)
            self.assertEqual(data.server.address, (host, 443))

    def test_allowed_connect_and_https_request_not_rewritten(self):
        flow = self.flow("PI-RE.FIXTURE.TEST", "pi-re.fixture.test:443")
        self.scope.http_connect(flow)
        self.scope.requestheaders(flow)
        self.assertIsNone(flow.response)
        self.assertEqual(flow.request.host, "PI-RE.FIXTURE.TEST")

    def test_unapproved_virtual_host_header_denied(self):
        flow = self.flow("pi-re.fixture.test", "other.test:443")
        self.scope.requestheaders(flow)
        self.assertEqual(flow.response.status_code, 403)

    def test_only_fixture_routes_loopback_preserving_tls_name(self):
        self.scope.allowed = frozenset({"pi-re.fixture.test", "approved.test"})
        data = self.connection("pi-re.fixture.test")
        self.scope.server_connect(data)
        self.assertEqual(data.server.address, ("127.0.0.1", 9443))
        self.assertEqual(data.server.sni, "pi-re.fixture.test")
        self.assertIsNone(data.server.error)
        data = self.connection("approved.test", "approved.test")
        self.scope.server_connect(data)
        self.assertEqual(data.server.address, ("approved.test", 443))
        self.assertEqual(data.server.sni, "approved.test")
        self.assertIsNone(data.server.error)
        data = self.connection("pi-re.fixture.test", "foreign.test")
        self.scope.server_connect(data)
        self.assertEqual(data.server.error, addon.DENIED)
        self.assertEqual(data.server.address, ("pi-re.fixture.test", 443))
        self.assertFalse(mitm.ctx.options.ssl_insecure)

    def test_run_config_loaded_once_and_ready_private(self):
        self.path.chmod(0o600)
        self.path.write_text(json.dumps({**self.config, "allowedHosts": ["foreign.test"]}))
        flow = self.flow("foreign.test")
        self.scope.http_connect(flow)
        self.assertEqual(flow.response.status_code, 403)
        self.scope.running()
        self.assertEqual(
            traffic.read_json(self.run / "ready.json"), {"configured": True, "version": 1}
        )
        self.assertEqual(stat.S_IMODE((self.run / "ready.json").stat().st_mode), 0o600)

    def test_unsafe_upstream_options_never_acknowledged(self):
        for key, value in (
            ("connection_strategy", "eager"),
            ("upstream_cert", True),
            ("ssl_insecure", True),
        ):
            with self.subTest(key=key):
                mitm.ctx.options = types.SimpleNamespace(
                    connection_strategy="lazy", upstream_cert=False, ssl_insecure=False
                )
                setattr(mitm.ctx.options, key, value)
                with self.assertRaises(ValueError):
                    self.scope.running()
                self.assertFalse((self.run / "ready.json").exists())
                flow = self.flow("pi-re.fixture.test")
                self.scope.http_connect(flow)
                self.assertEqual(flow.response.status_code, 403)

    def test_unloaded_addon_fails_closed(self):
        scope = addon.CaptureScope()
        flow = self.flow("pi-re.fixture.test")
        scope.http_connect(flow)
        self.assertEqual(flow.response.status_code, 403)
        data = self.connection("pi-re.fixture.test")
        scope.server_connect(data)
        self.assertEqual(data.server.error, addon.DENIED)

    def test_unapproved_fixture_and_mutable_config_rejected(self):
        for config in (
            {**self.config, "allowedHosts": ["other.test"]},
            {**self.config, "allowedHosts": ["*.test"]},
            {**self.config, "readyFile": str(self.run.parent / "outside")},
            {**self.config, "fixture": {"host": "pi-re.fixture.test", "port": True}},
        ):
            self.path.chmod(0o600)
            self.path.write_text(json.dumps(config))
            self.path.chmod(0o400)
            with mock.patch.dict(os.environ, {"PI_RE_TRAFFIC_CONFIG": str(self.path)}):
                with self.assertRaises(ValueError):
                    addon.CaptureScope().load(None)
        self.path.chmod(0o600)
        with mock.patch.dict(os.environ, {"PI_RE_TRAFFIC_CONFIG": str(self.path)}):
            with self.assertRaises(ValueError):
                addon.CaptureScope().load(None)

    def test_linked_scope_config_rejected(self):
        alias = self.run / "linked.json"
        alias.symlink_to(self.path)
        with mock.patch.dict(os.environ, {"PI_RE_TRAFFIC_CONFIG": str(alias)}):
            with self.assertRaises(ValueError):
                addon.CaptureScope().load(None)
        alias.unlink()
        os.link(self.path, alias)
        with mock.patch.dict(os.environ, {"PI_RE_TRAFFIC_CONFIG": str(self.path)}):
            with self.assertRaises(ValueError):
                addon.CaptureScope().load(None)


if __name__ == "__main__":
    unittest.main()
