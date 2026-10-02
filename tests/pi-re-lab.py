#!/usr/bin/env python3
"""Offline CA/proxy/child-session regression tests; no real devices or providers."""

import contextlib
import hashlib
import importlib.util
import shlex
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1] / "home-manager/modules/ai/pi-re"
for name in (
    "initialize",
    "android",
    "runtime",
    "traffic",
    "system_ca",
    "lab",
    "launcher",
    "verify_lab",
):
    spec = importlib.util.spec_from_file_location(name, SOURCE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
from android import LabError  # noqa: E402
from lab import Lab  # noqa: E402
from launcher import child_sessions  # noqa: E402
from system_ca import CERTS, SystemCA  # noqa: E402


class Guest:
    def __init__(self, state, digest):
        self.state = state
        self.digest = digest
        self.calls = []
        self.uid = "0"
        self.api = "35"
        self.boot = "12345678-1234-1234-1234-123456789abc"
        self.token = "a" * 32
        self.proxy = "null"

    def owner(self, required=True):
        return {"token": self.token}

    def device_identity(self):
        return None

    def adb(self, args, timeout=10):
        self.calls.append((args, timeout))
        if args[0] == "push":
            return 0, ""
        args = args[1:]
        if len(args) == 1:
            args = shlex.split(args[0])
        if args == ["id", "-u"]:
            return 0, self.uid
        if args == ["getprop", "ro.build.version.sdk"]:
            return 0, self.api
        if args[:1] == ["cat"]:
            return 0, self.boot
        if args[:1] == ["test"]:
            return 1, ""
        if args[:1] == ["pidof"]:
            return 0, "123 124"
        if "sha256sum" in args:
            return 0, self.digest + "  public.pem"
        if args[:3] == ["settings", "get", "global"]:
            return 0, self.proxy
        if args[:3] == ["settings", "put", "global"]:
            self.proxy = args[4]
        if args[:3] == ["settings", "delete", "global"]:
            self.proxy = "null"
        return 0, ""


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.public = self.root / "public.pem"
        self.public.write_bytes(
            b"-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----\n"
        )
        self.guest = Guest(self.root, hashlib.sha256(self.public.read_bytes()).hexdigest())
        self.ca = SystemCA(self.guest, "/never/execute/openssl")
        self.openssl = mock.patch(
            "system_ca.subprocess.run", return_value=types.SimpleNamespace(stdout="abcdef12\n")
        )
        self.openssl.start()
        self.addCleanup(self.openssl.stop)
        sleep = mock.patch("lab.time.sleep")
        sleep.start()
        self.addCleanup(sleep.stop)
        self.lab = object.__new__(Lab)
        self.lab.android = self.guest
        self.lab.proxy_record = self.root / "proxy.json"

    def test_ca_install_is_namespace_scoped_and_reused(self):
        first = self.ca.install(self.public)
        self.assertFalse(first["reused"])
        calls = self.guest.calls.copy()
        mounts = [args for args, _ in calls if args[:2] == ["shell", "nsenter"]]
        self.assertEqual(len(mounts), 2)
        self.assertTrue(all(args[-1] == CERTS for args in mounts))
        self.assertFalse(
            any("setenforce" in str(args) or "remount" in str(args) for args, _ in calls)
        )
        self.assertTrue(self.ca.install(self.public)["reused"])
        self.assertEqual(len([args for args, _ in self.guest.calls if "push" in args]), 1)

    def test_ca_refuses_nonroot_unsupported_api_and_private_key(self):
        for field, value in (("uid", "2000"), ("api", "34")):
            old = getattr(self.guest, field)
            setattr(self.guest, field, value)
            with self.assertRaises(LabError):
                self.ca.install(self.public)
            setattr(self.guest, field, old)
        self.public.write_bytes(b"-----BEGIN PRIVATE KEY-----\nfixture\n")
        with self.assertRaises(LabError):
            self.ca.install(self.public)
        self.assertFalse(self.ca.metadata.exists())

    def test_ca_changed_or_modified_overlay_refused_in_same_boot(self):
        self.ca.install(self.public)
        self.public.write_bytes(self.public.read_bytes() + b"different")
        with self.assertRaisesRegex(LabError, "CA changed"):
            self.ca.install(self.public)
        self.public.write_bytes(self.public.read_bytes().removesuffix(b"different"))
        self.guest.digest = "0" * 64
        with self.assertRaisesRegex(LabError, "overlay changed"):
            self.ca.install(self.public)

    def test_proxy_restore_only_owned_assignment(self):
        self.guest.proxy = "other.example:8888"
        self.lab.configure_proxy(8089)
        self.lab.configure_proxy(8089)
        self.lab.restore_proxy()
        self.assertEqual(self.guest.proxy, "other.example:8888")
        self.lab.configure_proxy(8089)
        self.guest.proxy = "external.example:9999"
        with self.assertRaisesRegex(LabError, "externally"):
            self.lab.restore_proxy()
        self.assertEqual(self.guest.proxy, "external.example:9999")

    def test_restored_proxy_record_recovers_unflushed_guest_setting(self):
        self.lab.configure_proxy(8089)
        self.lab.restore_proxy()
        self.assertTrue(self.lab.proxy_record.exists())
        # An abrupt VM exit can precede SettingsProvider's persistent write.
        self.guest.proxy = "10.0.2.2:8089"
        self.lab.configure_proxy(8089)
        self.lab.restore_proxy()
        self.assertEqual(self.guest.proxy, "null")

    def test_proxy_value_is_one_quoted_shell_argument(self):
        previous = "localhost:8888; touch /not/an/instruction"
        self.guest.proxy = previous
        self.lab.configure_proxy(8089)
        self.lab.restore_proxy()
        last = self.guest.calls[-1][0]
        self.assertEqual(shlex.split(last[1])[-1], previous)
        self.assertEqual(len(last), 2)

    def test_stop_attempts_traffic_under_lock_after_guest_failure(self):
        held = []

        @contextlib.contextmanager
        def lock():
            held.append(True)
            yield
            held.pop()

        guest = mock.Mock()
        guest.lock = lock
        guest.state = self.root
        guest.owner.return_value = {"token": "a" * 32}
        guest.lease.return_value = ({}, {"pid": 123})
        guest.backend.now.return_value = 0
        guest.timeout = 10
        guest.root_device.return_value = {"status": "ok"}
        guest.stop.side_effect = LabError("Guest stop deadline", True)
        guest.status.return_value = {"state": "running"}
        self.lab.android = guest
        self.lab.config = {}
        self.lab.restore_proxy = mock.Mock()
        self.lab.traffic = mock.Mock()

        def capture_stop():
            self.assertTrue(held)
            return {"status": "ok", "state": "stopped"}

        self.lab.traffic.stop.side_effect = capture_stop
        with mock.patch("lab.Frida"):
            result = self.lab.stop()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["systemCA"], "uninspected")
        self.lab.traffic.stop.assert_called_once()
        guest.stop.side_effect = KeyboardInterrupt()
        with mock.patch("lab.Frida"):
            result = self.lab.stop()
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(self.lab.traffic.stop.call_count, 2)

    def test_owned_device_close_and_daemon_stop_share_exact_private_route(self):
        (self.root / "device").mkdir(mode=0o700)
        self.guest.name = "fixture-avd"
        self.guest.serial = "emulator-5520"
        self.guest.env = {"PATH": "/controlled", "AGENT_DEVICE_REMOTE_CONFIG": "untrusted"}
        self.guest.tools = {"adb": "/pinned/adb"}
        self.lab.config = {"agentDevice": "/pinned/agent-device"}
        with mock.patch("lab.bounded_run", return_value={"status": "ok"}) as run:
            self.lab.retire_device()
        self.assertEqual(len(run.call_args_list), 2)
        close, stop = [call.args for call in run.call_args_list]
        self.assertEqual(close[0][-2:], ["close", "--json"])
        self.assertEqual(stop[0][-3:], ["daemon", "stop", "--json"])
        self.assertNotIn("--serial", stop[0])
        self.assertNotIn("--session", stop[0])
        self.assertEqual(stop[0][stop[0].index("--state-dir") + 1], str(self.root / "device"))
        self.assertEqual(close[0][close[0].index("--state-dir") + 1], str(self.root / "device"))
        self.assertNotIn("AGENT_DEVICE_REMOTE_CONFIG", close[1])
        self.assertEqual(close[3], 15)
        self.assertNotIn("--shutdown", close[0])
        with mock.patch(
            "lab.bounded_run", side_effect=[LabError("close deadline", True), {"status": "ok"}]
        ) as run:
            with self.assertRaises(LabError):
                self.lab.retire_device()
        self.assertEqual(run.call_count, 2)

    def test_failed_qualification_cleanup_restores_whole_lab_independently(self):
        from verify_lab import cleanup

        lab, session, server = mock.Mock(), mock.Mock(), mock.Mock()
        lab.stop.return_value = {"status": "ok"}
        session.detach.side_effect = OSError("detach failed")
        with self.assertRaises(LabError):
            cleanup(lab, session, server, True)
        server.shutdown.assert_called_once()
        server.server_close.assert_called_once()
        lab.stop.assert_called_once()
        lab.traffic.stop.assert_not_called()

    def test_early_certificate_failure_and_cancel_cleanup_existing_lab(self):
        from verify_lab import verify

        for error in (LabError("certificate failed"), KeyboardInterrupt()):
            original = mock.Mock()
            original.traffic.status.return_value = {"state": "running"}
            original.stop.return_value = {"status": "ok"}
            config = {"traffic": {"openssl": "/never/execute"}}
            with (
                mock.patch.dict(
                    sys.modules,
                    {
                        "frida": types.ModuleType("frida"),
                        "mitmproxy": types.SimpleNamespace(io=mock.Mock()),
                    },
                ),
                mock.patch("verify_lab.Lab", return_value=original),
                mock.patch("verify_lab.command", side_effect=error),
            ):
                with self.assertRaises(type(error)):
                    verify(config, self.root)
            original.traffic.start.assert_called_once_with(["pi-re.fixture.test"])
            original.traffic.stop.assert_called_once()
            original.stop.assert_called_once()

    def test_foreign_capture_scope_failure_does_not_stop_existing_lab(self):
        from verify_lab import verify

        original = mock.Mock()
        original.traffic.status.return_value = {"state": "running"}
        original.traffic.start.side_effect = LabError("scope mismatch")
        with (
            mock.patch.dict(
                sys.modules,
                {
                    "frida": types.ModuleType("frida"),
                    "mitmproxy": types.SimpleNamespace(io=mock.Mock()),
                },
            ),
            mock.patch("verify_lab.Lab", return_value=original),
        ):
            with self.assertRaises(LabError):
                verify({}, self.root)
        original.stop.assert_not_called()
        original.traffic.stop.assert_not_called()

    def test_child_sessions_validate_owner_private_path_and_no_symlinks(self):
        state = self.root / "state"
        job = state / "subagents/jobs/12345678-1234-1234-1234-123456789abc/sessions"
        job.mkdir(mode=0o700, parents=True)
        for directory in (state, state / "subagents", state / "subagents/jobs", job.parent):
            directory.chmod(0o700)
        locations = {"state": state, "sessions": state / "sessions"}
        environment = {"PI_RE_CHILD": "1", "PI_RE_CHILD_SESSION_DIR": str(job)}
        child_sessions(locations, environment)
        self.assertEqual(locations["sessions"], job)
        with self.assertRaises(ValueError):
            child_sessions(locations, {"PI_RE_CHILD_SESSION_DIR": str(job)})
        job.chmod(0o755)
        with self.assertRaises(ValueError):
            child_sessions(locations, environment)
        job.chmod(0o700)
        job.rmdir()
        job.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            child_sessions(locations, environment)


if __name__ == "__main__":
    unittest.main()
