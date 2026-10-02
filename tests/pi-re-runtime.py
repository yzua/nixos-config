#!/usr/bin/env python3
"""Offline runtime routing, private output, server ownership and reboot tests."""

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "home-manager/modules/ai/pi-re"))
import runtime  # noqa: E402

spec = importlib.util.spec_from_file_location("android_fixture", ROOT / "tests/pi-re-android.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class RuntimeTests(unittest.TestCase):
    setUp = fixture.RunnerTests.setUp
    create = fixture.RunnerTests.create
    start = fixture.RunnerTests.start

    def prepare(self):
        self.start()
        # Use a caller-owned offline fake backend, never the real ADB executable.
        self.lab = runtime.Android(self.config, self.runner.state, self.backend)
        server = self.base / "frida-server"
        server.write_text("official fixture binary")
        helper = self.base / "signal-helper"
        helper.write_text("owned helper fixture")
        self.runtime_config = {
            "agentDevice": "/fixture/agent-device",
            "python": sys.executable,
            "frida": {
                "version": "17.5.1",
                "abi": "x86_64",
                "server": str(server),
                "signalHelper": str(helper),
            },
        }
        self.frida = runtime.Frida(self.runtime_config, self.lab)
        self.guest_boot = "guest-boot-1"
        self.guest_ticks = "300"
        self.guest_alive = False
        self.port_busy = False
        self.helper_conflict = False
        self.guest_calls = []
        original = self.backend.run

        def run(argv, env, timeout, input=None):
            if Path(argv[0]).name == "adb":
                args = argv[3:]
                self.guest_calls.append(args)
                if args[:1] == ["push"]:
                    return 0, ""
                if args[:2] == ["shell", "chmod"]:
                    return 0, ""
                if args == ["shell", "cat", "/proc/sys/kernel/random/boot_id"]:
                    return 0, self.guest_boot
                if args[:3] == ["shell", "cat", "/proc/net/tcp"]:
                    return (
                        0,
                        " 0: 0100007F:69A2 00000000:0000 0A 00000000:00000000 "
                        if self.port_busy
                        else "",
                    )
                if args == ["shell", "cat", "/proc/800/cmdline"]:
                    return (
                        (0, self.frida.remote + "\x00-l\x00127.0.0.1:27042")
                        if self.guest_alive
                        else (1, "")
                    )
                if args == ["shell", "cat", "/proc/800/stat"]:
                    return 0, "800 (server) " + " ".join(["S"] + ["0"] * 18 + [self.guest_ticks])
                if args[:3] == ["shell", "sh", "-c"]:
                    self.guest_alive = True
                    return 0, "800"
                if args[:1] == ["shell"] and args[1].startswith("/data/local/tmp/pi-re-signal-"):
                    if self.helper_conflict:
                        return 4, ""
                    self.guest_alive = False
                    return 0, ""
            return original(argv, env, timeout, input)

        self.backend.run = run

    def test_transport_routing_cannot_be_overridden(self):
        self.prepare()
        for flag in (
            "--serial",
            "--session",
            "--config",
            "--daemon-base-url",
            "--daemon-auth-token",
            "--daemon-server-mode",
            "--platform",
            "--provider",
            "--aws-region",
            "--shutdown",
            "--launch-args",
        ):
            for args in (["snapshot", flag, "foreign"], ["snapshot", flag + "=foreign"]):
                with self.subTest(args=args), self.assertRaises(runtime.LabError):
                    runtime.device_arguments(self.runtime_config, self.lab, args, self.lab.owner())

    def test_infrastructure_and_nested_commands_not_enabled(self):
        self.prepare()
        for command in (
            "connect",
            "daemon",
            "proxy",
            "boot",
            "batch",
            "replay",
            "test",
            "mcp",
            "install-from-source",
            "metro",
            "takeover",
            "session",
        ):
            with self.subTest(command=command), self.assertRaises(runtime.LabError):
                runtime.device_arguments(self.runtime_config, self.lab, [command], self.lab.owner())

    def test_private_config_explicit_transport_and_session_lock(self):
        self.prepare()
        args = runtime.device_arguments(
            self.runtime_config, self.lab, ["snapshot", "-i"], self.lab.owner()
        )
        expected = {
            "--platform": "android",
            "--serial": self.lab.serial,
            "--daemon-transport": "socket",
            "--daemon-server-mode": "socket",
            "--session-lock": "reject",
            "--android-device-allowlist": self.lab.serial,
        }
        for flag, value in expected.items():
            self.assertEqual(args[args.index(flag) + 1], value)
        config = Path(args[args.index("--config") + 1])
        self.assertEqual(json.loads(config.read_text()), {})
        self.assertIn(self.lab.owner()["token"][:12], args[args.index("--session") + 1])

    def test_separator_cannot_swallow_controlled_routing_flags(self):
        self.prepare()
        args = runtime.device_arguments(
            self.runtime_config, self.lab, ["type", "--", "hello", "--config"], self.lab.owner()
        )
        separator = args.index("--")
        for flag in (
            "--platform",
            "--serial",
            "--session",
            "--config",
            "--state-dir",
            "--daemon-transport",
        ):
            self.assertLess(args.index(flag), separator)
        self.assertEqual(args[separator + 1 :], ["hello", "--config"])

    def test_metadata_publication_failure_rolls_back_guest_server(self):
        self.prepare()
        with patch.object(
            runtime, "write_json", side_effect=OSError("fixture publication failure")
        ):
            with self.assertRaises(OSError):
                self.frida.setup()
        self.assertFalse(self.guest_alive)
        self.assertFalse(self.frida.metadata.exists())
        self.assertIsNotNone(self.backend.process(self.backend.pid))

    def test_cancelled_metadata_publication_rolls_back_guest_server(self):
        self.prepare()
        with patch.object(runtime, "write_json", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.frida.setup()
        self.assertFalse(self.guest_alive)

    def test_ambiguous_start_identity_stops_only_owned_vm(self):
        self.prepare()
        with patch.object(
            self.frida, "start_ticks", side_effect=runtime.LabError("unknown launch")
        ):
            with self.assertRaises(runtime.LabError):
                self.frida.setup()
        self.assertIsNone(self.backend.process(self.backend.pid))
        self.assertFalse(any(call[:2] == ["shell", "kill"] for call in self.guest_calls))

    def test_environment_clears_remote_defaults(self):
        self.prepare()
        self.lab.env["AGENT_DEVICE_DAEMON_BASE_URL"] = "https://foreign.invalid"
        self.lab.env["AGENT_DEVICE_CONFIG"] = "/foreign/config"
        env = runtime.local_environment(self.lab)
        self.assertNotIn("AGENT_DEVICE_CONFIG", env)
        self.assertNotIn("AGENT_DEVICE_DAEMON_BASE_URL", env)
        self.assertEqual(env["AGENT_DEVICE_NO_UPDATE_NOTIFIER"], "1")
        home = Path(env["HOME"])
        self.assertEqual(home, self.lab.state / "device-home")
        self.assertTrue(home.is_dir())
        self.assertEqual(home.stat().st_mode & 0o777, 0o700)
        self.assertEqual(home.stat().st_uid, os.getuid())

    def test_private_device_home_rejects_symlink(self):
        self.prepare()
        home = self.lab.state / "device-home"
        home.symlink_to(self.lab.state, target_is_directory=True)
        with self.assertRaises(runtime.LabError):
            runtime.local_environment(self.lab)

    def test_offline_help_does_not_contact_device(self):
        self.prepare()
        before = len(self.guest_calls)
        with patch.object(runtime, "bounded_run", return_value={"status": "ok"}):
            runtime.device(self.runtime_config, self.lab, ["help", "snapshot"])
        self.assertEqual(len(self.guest_calls), before)

    def test_setup_records_start_boot_owner_and_is_idempotent(self):
        self.prepare()
        self.frida.setup()
        record = runtime.read_json(self.frida.metadata)
        self.assertEqual(record["start"], "300")
        self.assertEqual(record["boot"], self.guest_boot)
        self.assertEqual(record["owner"], self.lab.owner()["token"])
        pushes = sum(call[0] == "push" for call in self.guest_calls)
        self.frida.setup()
        self.assertEqual(sum(call[0] == "push" for call in self.guest_calls), pushes)

    def test_same_executable_pid_reuse_never_signaled(self):
        self.prepare()
        self.frida.setup()
        self.guest_ticks = "301"
        with self.assertRaisesRegex(runtime.LabError, "reused"):
            self.frida.stop()
        self.assertFalse(
            any(
                call[1].startswith("/data/local/tmp/pi-re-signal-")
                for call in self.guest_calls
                if call[0] == "shell"
            )
        )
        self.assertTrue(self.frida.metadata.exists())

    def test_stop_uses_identity_bound_helper_and_never_bare_kill(self):
        self.prepare()
        self.frida.setup()
        self.frida.stop()
        self.assertFalse(self.guest_alive)
        self.assertFalse(self.frida.metadata.exists())
        self.assertFalse(any(call[:2] == ["shell", "kill"] for call in self.guest_calls))
        invocation = next(
            call
            for call in self.guest_calls
            if call[0] == "shell" and call[1].startswith("/data/local/tmp/pi-re-signal-")
        )
        self.assertEqual(invocation[2:], ["800", "300", self.guest_boot, self.frida.remote])

    def test_signal_identity_conflict_retains_metadata(self):
        self.prepare()
        self.frida.setup()
        self.helper_conflict = True
        with self.assertRaises(runtime.LabError):
            self.frida.stop()
        self.assertTrue(self.guest_alive)
        self.assertTrue(self.frida.metadata.exists())

    def test_reboot_retires_stale_record_without_signaling_old_pid(self):
        self.prepare()
        self.frida.setup()
        self.guest_boot = "guest-boot-2"
        self.guest_alive = False
        self.frida.setup()
        self.assertEqual(runtime.read_json(self.frida.metadata)["boot"], self.guest_boot)
        self.assertEqual(len(list(self.lab.state.glob("frida-stale-*.json"))), 1)
        self.assertFalse(any(call[:2] == ["shell", "kill"] for call in self.guest_calls))

    def test_stop_after_reboot_only_retires_metadata(self):
        self.prepare()
        self.frida.setup()
        self.guest_boot = "guest-boot-2"
        self.guest_alive = False
        self.assertTrue(self.frida.stop()["staleRecordRetired"])
        self.assertFalse(self.frida.metadata.exists())

    def test_absent_server_cannot_attach_to_foreign_server(self):
        self.prepare()
        with patch.object(runtime, "bounded_run", side_effect=AssertionError):
            with self.assertRaisesRegex(runtime.LabError, "owned matched"):
                self.frida.run(["--package", "fixture"])

    def test_existing_listener_never_taken_over(self):
        self.prepare()
        self.port_busy = True
        with self.assertRaisesRegex(runtime.LabError, "occupied"):
            self.frida.setup()
        self.assertFalse(any(call[0] == "push" for call in self.guest_calls))

    def test_bounded_output_files_and_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            result = runtime.bounded_run(
                [sys.executable, "-c", "print('x'*20000)"], os.environ, directory
            )
            self.assertEqual(result["status"], "partial")
            self.assertEqual(Path(result["artifact"]).stat().st_mode & 0o777, 0o600)
            with self.assertRaises(runtime.LabError) as error:
                runtime.bounded_run(
                    [sys.executable, "-c", "import time; time.sleep(5)"],
                    os.environ,
                    directory,
                    timeout=0.01,
                )
            self.assertTrue(error.exception.timeout)


class ProcessSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "probe_fixture", ROOT / "home-manager/modules/ai/pi-re/frida_probe.py"
        )
        cls.probe = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"frida": types.SimpleNamespace()}):
            spec.loader.exec_module(cls.probe)

    def test_package_identifier_not_display_label(self):
        app = types.SimpleNamespace(identifier="org.pi.re.fixture", name="Pi RE Fixture", pid=3318)
        device = types.SimpleNamespace(enumerate_applications=lambda: [app])
        self.assertEqual(self.probe.selected_pid(device, "org.pi.re.fixture"), 3318)
        with self.assertRaises(ValueError):
            self.probe.selected_pid(device, "Pi RE Fixture")

    def test_nonrunning_or_ambiguous_application_never_attached(self):
        for pids in ([], [0], [12, 13]):
            apps = [types.SimpleNamespace(identifier="org.pi.re.fixture", pid=pid) for pid in pids]
            device = types.SimpleNamespace(enumerate_applications=lambda: apps)
            with self.assertRaises(ValueError):
                self.probe.selected_pid(device, "org.pi.re.fixture")


if __name__ == "__main__":
    unittest.main()
