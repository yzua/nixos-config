#!/usr/bin/env python3
"""Offline lifecycle/ownership tests: no SDK downloads, ADB server, or real devices."""

import contextlib
import errno
import importlib.util
import io
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1] / "home-manager/modules/ai/pi-re/android.py"
SPEC = importlib.util.spec_from_file_location("pi_re_android", SOURCE)
android = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(android)


class FakeBackend:
    def __init__(self):
        self.clock = 0
        self.calls = []
        self.processes = {}
        self.signals = []
        self.busy_ports = set()
        self.pid = 4200
        self.uids = ["0"]
        self.boots = ["1"]
        self.foreign_serial = False
        self.avd_name = "lab"
        self.kill_works = True
        self.adb_available = True
        self.gpu = "swiftshader swiftshader_indirect"
        self.root_code = 0
        self.root_calls = 0
        self.create_code = 0
        self.spawn_count = 0
        self.boot = "test-boot"
        self.process_reads = []

    def host_boot(self):
        return self.boot

    def now(self):
        return self.clock

    def sleep(self, seconds):
        self.clock += seconds

    def process(self, pid):
        self.process_reads.append(pid)
        value = self.processes.get(pid)
        return value.copy() if value else None

    def port_free(self, port):
        return port not in self.busy_ports

    def run(self, argv, env, timeout, input=None):
        self.calls.append((argv, env, timeout, input))
        tool = Path(argv[0]).name
        if tool == "avdmanager":
            if not self.create_code:
                avd = Path(argv[argv.index("--path") + 1])
                avd.mkdir()
                (avd / "config.ini").write_text("image.sysdir.1=read-only-sdk\n")
                (avd.parent / "lab.ini").write_text(f"path={avd}\n")
            return self.create_code, "private diagnostics canary"
        if tool == "emulator":
            return 0, self.gpu
        assert tool == "adb", argv
        assert argv[1:3] == ["-s", "emulator-5580"], argv
        command = argv[3:]
        if command == ["devices"]:
            return 0, "emulator-5580 offline\n" if self.foreign_serial else "List of devices\n"
        if not self.adb_available:
            return 1, "transport unavailable"
        if command == ["emu", "avd", "name"]:
            return 0, f"{self.avd_name}\nOK\n"
        if command == ["root"]:
            self.root_calls += 1
            return self.root_code, "private diagnostics canary"
        if command == ["shell", "id", "-u"]:
            value = self.uids.pop(0) if len(self.uids) > 1 else self.uids[0]
            return (1, "offline") if value is None else (0, value)
        if command == ["shell", "getprop", "sys.boot_completed"]:
            value = self.boots.pop(0) if len(self.boots) > 1 else self.boots[0]
            return 0, value
        if command == ["emu", "kill"]:
            if self.kill_works:
                self.processes.pop(self.pid, None)
            return 0, "OK"
        raise AssertionError(argv)

    def spawn(self, argv, env, log):
        self.calls.append((argv, env, None, None))
        self.spawn_count += 1
        self.processes[self.pid] = {
            "start": "100",
            "session": self.pid,
            "uid": os.getuid(),
            "boot": self.host_boot(),
        }
        return self.pid

    def terminate(self, pid, identity, sig):
        assert self.process(pid) == identity
        self.signals.append((pid, sig))
        self.processes.pop(pid, None)


class HostBootTests(unittest.TestCase):
    def test_host_boot_reads_and_strips_current_kernel_identity(self):
        with mock.patch.object(Path, "read_text", return_value="current-host-boot\n") as read:
            self.assertEqual(android.Backend().host_boot(), "current-host-boot")
        read.assert_called_once_with()

    def test_blank_host_boot_fails_closed(self):
        for value in ("", " \n\t"):
            with self.subTest(value=value):
                with mock.patch.object(Path, "read_text", return_value=value):
                    with self.assertRaisesRegex(android.LabError, "host boot identity"):
                        android.Backend().host_boot()

    def test_inaccessible_host_boot_fails_closed_without_exposing_details(self):
        for error in (FileNotFoundError("private canary"), PermissionError("private canary")):
            with self.subTest(error=type(error).__name__):
                with mock.patch.object(Path, "read_text", side_effect=error):
                    with self.assertRaisesRegex(android.LabError, "host boot identity") as caught:
                        android.Backend().host_boot()
            self.assertNotIn("canary", str(caught.exception))


class PortProbeTests(unittest.TestCase):
    def test_time_wait_does_not_block_restart(self):
        # Active-close the server side so TIME_WAIT belongs to the emulator's port,
        # not the client's ephemeral port. No real SDK/ADB process is involved.
        with contextlib.ExitStack() as stack:
            listener = stack.enter_context(socket.socket())
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.settimeout(2)
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            listener.listen(1)
            client = stack.enter_context(socket.socket())
            client.settimeout(2)
            client.connect(("127.0.0.1", port))
            connection, _ = listener.accept()
            stack.enter_context(connection)
            connection.settimeout(2)
            connection.shutdown(socket.SHUT_WR)
            self.assertEqual(client.recv(1), b"")
            client.shutdown(socket.SHUT_WR)
            self.assertEqual(connection.recv(1), b"")
        # Prove that the fixture retained TIME_WAIT and catches the original probe.
        with socket.socket() as without_reuse:
            with self.assertRaises(OSError) as caught:
                without_reuse.bind(("0.0.0.0", port))
            self.assertEqual(caught.exception.errno, errno.EADDRINUSE)
        self.assertTrue(android.Backend().port_free(port))

    def test_live_reusable_listener_still_blocks_start(self):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            self.assertFalse(android.Backend().port_free(listener.getsockname()[1]))


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.sdk = self.base / "sdk"
        image = self.sdk / "system-images/android-35/google_apis/x86_64"
        image.mkdir(parents=True)
        (image / "package.xml").write_text("fixture")
        (image / "system.img").write_text("fixture")
        self.config = {
            "sdkRoot": str(self.sdk),
            "avdName": "lab",
            "apiLevel": "35",
            "imageType": "google_apis",
            "abi": "x86_64",
            "port": 5580,
            "memoryMiB": 4096,
            "cores": 4,
            "bootTimeoutSeconds": 4,
        }
        for tool in ("adb", "emulator", "avdmanager"):
            path = self.sdk / "bin" / tool
            path.parent.mkdir(exist_ok=True)
            path.write_text("#!/bin/sh\nexit 99\n")
            path.chmod(0o755)
            self.config[tool] = str(path)
        self.backend = FakeBackend()
        self.runner = android.Android({"android": self.config}, self.base / "lab", self.backend)

    def create(self):
        return self.runner.execute("create")

    def start(self):
        self.create()
        return self.runner.execute("start")

    def assertBlocked(self, command, text):
        with self.assertRaisesRegex(android.LabError, text):
            self.runner.execute(command)

    def test_create_idempotent_and_private_paths(self):
        self.assertEqual(self.create()["state"], "created")
        self.create()
        creates = [call for call in self.backend.calls if Path(call[0][0]).name == "avdmanager"]
        self.assertEqual(len(creates), 1)
        argv, env, timeout, input = creates[0]
        self.assertEqual(input, "no\n")
        self.assertEqual(argv[argv.index("--package") + 1], self.runner.package)
        self.assertEqual(env["ANDROID_USER_HOME"], str(self.runner.user))
        self.assertEqual(env["ANDROID_AVD_HOME"], str(self.runner.avds))
        self.assertNotIn("--force", argv)
        self.assertGreater(timeout, 0)

    def test_no_sdk_mutation_or_downloads(self):
        before = {
            str(p.relative_to(self.sdk)): p.read_bytes() for p in self.sdk.rglob("*") if p.is_file()
        }
        self.start()
        self.runner.execute("stop")
        self.runner.execute("reset")
        after = {
            str(p.relative_to(self.sdk)): p.read_bytes() for p in self.sdk.rglob("*") if p.is_file()
        }
        self.assertEqual(before, after)
        self.assertFalse(any("sdkmanager" in str(call[0]) for call in self.backend.calls))

    def test_missing_image_blocks_before_avdmanager(self):
        (self.sdk / "system-images/android-35/google_apis/x86_64/system.img").unlink()
        self.assertBlocked("create", "image is absent")
        self.assertFalse(self.backend.calls)

    def test_foreign_avd_not_claimed(self):
        self.runner.avd.mkdir(parents=True)
        self.assertBlocked("create", "foreign")
        self.assertFalse(self.runner.owner_file.exists())
        self.assertFalse(self.backend.calls)

    def test_start_root_verified_headless_and_serial_scoped(self):
        self.runner.timeout = 8
        self.backend.boots = ["", "0", "1"]
        self.backend.uids = [None, "2000", "0"]
        result = self.start()
        self.assertIs(result["rooted"], True)
        self.assertGreaterEqual(self.backend.root_calls, 3)
        spawn = next(c[0] for c in self.backend.calls if "-avd" in c[0])
        for flag in ("-no-window", "-no-audio", "-writable-system", "-no-snapshot"):
            self.assertIn(flag, spawn)
        self.assertEqual(spawn[spawn.index("-gpu") + 1], "swiftshader")
        self.assertEqual(spawn[spawn.index("-port") + 1], "5580")
        self.assertEqual(self.runner.lease()[0]["process"]["start"], "100")
        for argv, _, timeout, _ in self.backend.calls:
            if Path(argv[0]).name == "adb":
                self.assertEqual(argv[1:3], ["-s", self.runner.serial])
                self.assertGreater(timeout, 0)

    def test_visible_and_older_swiftshader(self):
        self.create()
        self.backend.gpu = "Modes: host swiftshader_indirect"
        self.runner.execute("start", visible=True)
        spawn = next(c[0] for c in self.backend.calls if "-avd" in c[0])
        self.assertNotIn("-no-window", spawn)
        self.assertIn("swiftshader_indirect", spawn)

    def test_selected_swangle_and_software_decoder_are_explicit(self):
        self.config.update(gpuMode="swangle", hardwareVideoDecoder=False)
        self.backend.gpu = "Modes: swiftshader swangle software lavapipe"
        self.runner = android.Android({"android": self.config}, self.base / "lab", self.backend)
        self.start()
        spawn = next(c[0] for c in self.backend.calls if "-avd" in c[0])
        self.assertEqual(spawn[spawn.index("-gpu") + 1], "swangle")
        self.assertEqual(spawn[spawn.index("-feature") + 1], "-HardwareDecoder")

    def test_configured_gpu_does_not_silently_fallback(self):
        self.config["gpuMode"] = "swangle"
        self.runner = android.Android({"android": self.config}, self.base / "lab", self.backend)
        self.create()
        self.assertBlocked("start", "selected supported software GPU")
        self.assertEqual(self.backend.spawn_count, 0)

    def test_invalid_graphics_configuration_rejected(self):
        for values in (
            {"gpuMode": "host"},
            {"gpuMode": "--arbitrary-option"},
            {"hardwareVideoDecoder": "false"},
        ):
            with self.subTest(values=values), self.assertRaises(android.LabError):
                android.Android(
                    {"android": {**self.config, **values}}, self.base / "lab", self.backend
                )

    def test_unsupported_gpu_blocks_without_launch(self):
        self.create()
        self.backend.gpu = "host only"
        self.assertBlocked("start", "supported software GPU")
        self.assertEqual(self.backend.spawn_count, 0)

    def test_root_timeout_never_reports_success_and_cleans_start(self):
        self.create()
        self.backend.uids = ["2000"]
        with self.assertRaises(android.LabError) as caught:
            self.runner.execute("start")
        self.assertTrue(caught.exception.timeout)
        self.assertLessEqual(self.backend.clock, 5)
        self.assertFalse(self.backend.processes)
        self.assertEqual(self.backend.signals, [(4200, signal.SIGTERM)])

    def test_root_failure_retries_until_finite_timeout(self):
        self.create()
        self.backend.root_code = 1
        self.backend.uids = ["2000"]
        with self.assertRaises(android.LabError) as caught:
            self.runner.execute("start")
        self.assertTrue(caught.exception.timeout)
        self.assertGreater(self.backend.root_calls, 1)
        self.assertFalse(self.backend.processes)

    def test_cancelled_start_cleans_only_owned_process(self):
        self.create()
        original = self.backend.run

        def interrupted(argv, env, timeout, input=None):
            if argv[3:] == ["shell", "getprop", "sys.boot_completed"]:
                raise KeyboardInterrupt()
            return original(argv, env, timeout, input)

        with mock.patch.object(self.backend, "run", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.runner.execute("start")
        self.assertFalse(self.backend.processes)
        self.assertEqual(self.backend.signals, [(4200, signal.SIGTERM)])

    def test_adb_exec_failure_cleans_launched_process(self):
        self.create()
        original = self.backend.run

        def failed(argv, env, timeout, input=None):
            if argv[3:] == ["shell", "getprop", "sys.boot_completed"]:
                raise OSError("fixture exec failure")
            return original(argv, env, timeout, input)

        with mock.patch.object(self.backend, "run", side_effect=failed):
            with self.assertRaises(OSError):
                self.runner.execute("start")
        self.assertFalse(self.backend.processes)
        self.assertEqual(self.backend.signals, [(4200, signal.SIGTERM)])

    def test_boot_timeout_cleans_start(self):
        self.create()
        self.backend.boots = ["0"]
        with self.assertRaises(android.LabError) as caught:
            self.runner.execute("start")
        self.assertTrue(caught.exception.timeout)
        self.assertFalse(self.backend.processes)

    def test_already_running_rechecks_root_without_spawn(self):
        self.start()
        self.backend.uids = ["2000", "0"]
        self.assertTrue(self.runner.execute("start")["rooted"])
        self.assertEqual(self.backend.spawn_count, 1)

    def test_root_command_timeout_leaves_existing_emulator(self):
        self.start()
        self.backend.uids = ["2000"]
        with self.assertRaises(android.LabError) as caught:
            self.runner.execute("root")
        self.assertTrue(caught.exception.timeout)
        self.assertTrue(self.backend.processes)

    def test_root_rejects_foreign_serial(self):
        self.start()
        self.backend.avd_name = "personal"
        calls = self.backend.root_calls
        self.assertBlocked("root", "does not identify")
        self.assertEqual(self.backend.root_calls, calls)
        self.assertFalse(self.backend.signals)

    def test_root_rejects_unowned_running_serial(self):
        self.create()
        self.backend.foreign_serial = True
        self.assertBlocked("root", "No verified owned")
        self.assertFalse(any(c[0][3:] == ["root"] for c in self.backend.calls))

    def test_port_and_offline_serial_collisions(self):
        self.create()
        for port in (5580, 5581):
            self.backend.busy_ports = {port}
            self.assertBlocked("start", "port collision")
        self.backend.busy_ports.clear()
        self.backend.foreign_serial = True
        self.assertBlocked("start", "already claimed")
        self.assertEqual(self.backend.spawn_count, 0)

    def test_status_does_not_create_or_call_adb(self):
        self.assertEqual(self.runner.execute("status")["state"], "absent")
        self.assertFalse(self.runner.state.exists())
        self.start()
        calls = len(self.backend.calls)
        result = self.runner.execute("status")
        self.assertEqual(result["inspection"], "process-only")
        self.assertEqual(result["rooted"], "uninspected")
        self.assertEqual(len(self.backend.calls), calls)

    def test_owner_mismatch_rejected(self):
        self.create()
        data = android.read_json(self.runner.owner_file)
        data["uid"] += 1
        android.write_json(self.runner.owner_file, data)
        for command in ("status", "create", "start", "root", "stop", "reset"):
            self.assertBlocked(command, "owner/configuration mismatch")

    def test_pid_reuse_rejected_without_adb_or_signal(self):
        self.start()
        self.backend.processes[4200]["start"] = "101"
        calls = len(self.backend.calls)
        for command in ("status", "start", "root", "stop", "reset"):
            self.assertBlocked(command, "PID reuse")
        self.assertEqual(len(self.backend.calls), calls)
        self.assertFalse(self.backend.signals)

    def reboot_with_reused_pid(self):
        self.start()
        old_pid = self.backend.pid
        self.backend.boot = "next-host-boot"
        foreign = {
            "start": "900",
            "session": old_pid,
            "uid": os.getuid() + 1,
            "boot": self.backend.host_boot(),
        }
        self.backend.processes[old_pid] = foreign
        self.backend.process_reads.clear()
        self.backend.calls.clear()
        return old_pid, foreign

    def test_previous_host_boot_status_does_not_inspect_reused_pid_or_adb(self):
        old_pid, foreign = self.reboot_with_reused_pid()
        before = self.runner.lease_file.read_bytes()
        result = self.runner.execute("status")
        self.assertEqual(result["state"], "stopped")
        self.assertTrue(result["staleLease"])
        self.assertEqual(result["inspection"], "process-only")
        self.assertEqual(result["rooted"], "uninspected")
        self.assertEqual(self.runner.lease_file.read_bytes(), before)
        self.assertFalse(self.backend.process_reads)
        self.assertFalse(self.backend.calls)
        self.assertFalse(self.backend.signals)
        self.assertEqual(self.backend.processes[old_pid], foreign)

    def test_previous_host_boot_stop_does_not_inspect_reused_pid_or_adb(self):
        old_pid, foreign = self.reboot_with_reused_pid()
        result = self.runner.execute("stop")
        self.assertEqual(result["state"], "stopped")
        self.assertTrue(result["staleLease"])
        self.assertFalse(self.backend.process_reads)
        self.assertFalse(self.backend.calls)
        self.assertFalse(self.backend.signals)
        self.assertEqual(self.backend.processes[old_pid], foreign)

    def test_previous_host_boot_start_creates_new_lease_without_inspecting_reused_pid(self):
        old_pid, foreign = self.reboot_with_reused_pid()
        self.backend.pid += 1
        self.assertTrue(self.runner.execute("start")["rooted"])
        self.assertEqual(self.backend.spawn_count, 2)
        lease = android.read_json(self.runner.lease_file)
        self.assertEqual(lease["pid"], self.backend.pid)
        self.assertEqual(lease["process"]["boot"], self.backend.host_boot())
        self.assertNotIn(old_pid, self.backend.process_reads)
        self.assertFalse(self.backend.signals)
        self.assertEqual(self.backend.processes[old_pid], foreign)

    def test_previous_host_boot_does_not_bypass_lease_validation(self):
        self.reboot_with_reused_pid()
        lease = android.read_json(self.runner.lease_file)
        for changed in (
            {**lease, "token": "foreign"},
            {**lease, "serial": "foreign"},
            {**lease, "pid": True},
            {**lease, "process": None},
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
            android.write_json(self.runner.lease_file, changed)
            for command in ("status", "start", "stop"):
                with self.subTest(changed=changed, command=command):
                    with self.assertRaises(android.LabError):
                        self.runner.execute(command)
        self.assertFalse(self.backend.process_reads)
        self.assertFalse(self.backend.calls)
        self.assertFalse(self.backend.signals)

    def test_previous_host_boot_does_not_bypass_owner_validation(self):
        self.reboot_with_reused_pid()
        owner = android.read_json(self.runner.owner_file)
        for changed in ({**owner, "uid": os.getuid() + 1}, {**owner, "version": 99}, None):
            if changed is None:
                self.runner.owner_file.unlink()
            else:
                android.write_json(self.runner.owner_file, changed)
            for command in ("status", "start", "stop"):
                with self.subTest(changed=changed, command=command):
                    with self.assertRaises(android.LabError):
                        self.runner.execute(command)
        self.assertFalse(self.backend.process_reads)
        self.assertFalse(self.backend.calls)
        self.assertFalse(self.backend.signals)

    def test_same_host_boot_identity_mismatches_fail_closed(self):
        self.start()
        original = self.backend.processes[self.backend.pid].copy()
        for field, value in (
            ("start", "999"),
            ("boot", "unexpected-process-boot"),
            ("uid", os.getuid() + 1),
            ("session", 5000),
        ):
            self.backend.processes[self.backend.pid] = {**original, field: value}
            calls = len(self.backend.calls)
            for command in ("status", "start", "stop"):
                with self.subTest(field=field, command=command):
                    self.assertBlocked(command, "PID reuse")
            self.assertEqual(len(self.backend.calls), calls)
        self.assertFalse(self.backend.signals)

    def test_foreign_lease_and_session_rejected(self):
        self.start()
        lease = android.read_json(self.runner.lease_file)
        lease["token"] = "foreign"
        android.write_json(self.runner.lease_file, lease)
        self.assertBlocked("stop", "Foreign emulator lease")
        lease["token"] = self.runner.owner()["token"]
        lease["process"]["session"] = 99
        self.backend.processes[4200]["session"] = 99
        android.write_json(self.runner.lease_file, lease)
        self.assertBlocked("stop", "Foreign emulator session")

    def test_stale_dead_lease_safe_status_stop_reset(self):
        self.start()
        self.backend.processes.clear()
        self.assertTrue(self.runner.execute("status")["staleLease"])
        self.assertEqual(self.runner.execute("stop")["state"], "stopped")
        self.assertFalse(self.backend.signals)
        self.assertEqual(self.runner.execute("reset")["state"], "reset")

    def test_stop_graceful_then_fallback_only_owned_pid(self):
        self.start()
        self.backend.processes[5000] = {"start": "foreign"}
        self.backend.kill_works = False
        self.runner.execute("stop")
        self.assertEqual(self.backend.signals, [(4200, signal.SIGTERM)])
        self.assertIn(5000, self.backend.processes)
        self.assertFalse(self.runner.lease_file.exists())
        self.assertTrue(any(c[0][3:] == ["emu", "kill"] for c in self.backend.calls))
        self.assertFalse(any("kill-server" in c[0] for c in self.backend.calls))

    def test_stop_transport_unavailable_uses_verified_pid_only(self):
        self.start()
        self.backend.adb_available = False
        self.runner.execute("stop")
        self.assertEqual(self.backend.signals, [(4200, signal.SIGTERM)])

    def test_stop_foreign_device_never_kills(self):
        self.start()
        self.backend.avd_name = "foreign"
        self.assertBlocked("stop", "foreign AVD")
        self.assertFalse(self.backend.signals)
        self.assertFalse(any(c[0][3:] == ["emu", "kill"] for c in self.backend.calls))

    def test_reset_refuses_running_and_preserves_unrelated_paths(self):
        self.start()
        self.assertBlocked("reset", "Stop the owned")
        self.runner.execute("stop")
        unrelated = self.runner.state / "metadata.json"
        unrelated.write_text("keep")
        self.runner.execute("reset")
        self.assertEqual(unrelated.read_text(), "keep")
        self.assertTrue((self.runner.root / "lock").exists())
        self.create()

    def test_reset_rejects_occupied_ports_without_deleting_avd(self):
        self.create()
        self.backend.busy_ports = {5580}
        self.assertBlocked("reset", "ports are occupied")
        self.assertTrue(self.runner.avd.exists())
        self.assertTrue(self.runner.owner_file.exists())

    def test_reset_preserves_foreign_avd(self):
        self.create()
        foreign = self.runner.avds / "other.avd"
        foreign.mkdir()
        (foreign / "data").write_text("keep")
        self.assertBlocked("reset", "Unrelated AVD")
        self.assertEqual((foreign / "data").read_text(), "keep")
        self.assertTrue(self.runner.owner_file.exists())
        self.assertTrue(self.runner.avd.exists())

    def test_symlinks_rejected_without_target_deletion(self):
        self.create()
        target = self.base / "unrelated"
        target.write_text("keep")
        link = self.runner.avd / "userdata.img"
        link.symlink_to(target)
        self.assertBlocked("start", "symlinks")
        self.assertBlocked("reset", "symlinks")
        self.assertEqual(target.read_text(), "keep")
        link.unlink()
        self.runner.lease_file.symlink_to(self.base / "missing")
        self.assertBlocked("status", "symlinks")

    def test_special_metadata_rejected_without_blocking(self):
        self.create()
        self.runner.owner_file.unlink()
        os.mkfifo(self.runner.owner_file)
        self.assertBlocked("status", "regular file")
        self.runner.owner_file.unlink()

    def test_hardlinked_log_never_truncates_unrelated_file(self):
        self.create()
        target = self.base / "unrelated-log"
        target.write_text("keep")
        os.link(target, self.runner.root / "emulator.log")
        self.assertBlocked("start", "single-link")
        self.assertEqual(target.read_text(), "keep")
        self.assertEqual(self.backend.spawn_count, 0)

    def test_failed_lease_write_cleans_launched_process(self):
        self.create()
        with mock.patch.object(android, "write_json", side_effect=OSError("fixture")):
            with self.assertRaises(OSError):
                self.runner.execute("start")
        self.assertFalse(self.backend.processes)
        self.assertEqual(self.backend.signals, [(4200, signal.SIGKILL)])

    def test_symlink_state_or_lock_rejected(self):
        link = self.base / "alias"
        link.symlink_to(self.base, target_is_directory=True)
        with self.assertRaisesRegex(android.LabError, "symlinks"):
            android.Android(self.config, link / "state", self.backend)
        self.runner.root.mkdir(parents=True)
        (self.runner.root / "lock").symlink_to(self.base / "missing")
        self.assertBlocked("create", "symlinks")

    def test_avd_index_foreign_path_rejected(self):
        self.create()
        self.runner.ini.write_text("path=/unrelated/avd\n")
        self.assertBlocked("start", "foreign directory")

    def test_lock_is_nonblocking_and_not_reentrant(self):
        self.create()
        with self.runner.lock():
            self.assertBlocked("start", "holds the lock")
            self.assertBlocked("status", "holds the lock")

    def test_invalid_configuration_and_sdk_overlap(self):
        for key, value in (
            ("port", 5581),
            ("avdName", "../escape"),
            ("bootTimeoutSeconds", 0),
            ("cores", True),
            ("imageType", "google_apis_playstore"),
        ):
            with self.assertRaises(android.LabError):
                android.Android({**self.config, key: value}, self.base / "lab", self.backend)
        with self.assertRaisesRegex(android.LabError, "separate"):
            android.Android(self.config, self.sdk / "mutable", self.backend)

    def test_create_failure_output_not_exposed_and_reset_recovers(self):
        self.backend.create_code = 1
        with self.assertRaises(android.LabError) as caught:
            self.create()
        self.assertNotIn("canary", str(caught.exception))
        self.assertBlocked("create", "incomplete")
        self.runner.execute("reset")
        self.backend.create_code = 0
        self.create()

    def test_cli_visible_rejected_except_for_start_without_side_effects(self):
        for command in ("create", "status", "root", "stop", "reset"):
            with self.subTest(command=command):
                output = io.StringIO()
                with mock.patch.object(Path, "open") as opened:
                    with mock.patch.object(android.Android, "execute") as execute:
                        with contextlib.redirect_stdout(output):
                            code = android.main(
                                [
                                    "--config",
                                    str(self.base / "missing-config.json"),
                                    "--state-dir",
                                    str(self.runner.state),
                                    command,
                                    "--visible",
                                    "--json",
                                ]
                            )
                self.assertEqual(code, 1)
                result = json.loads(output.getvalue())
                self.assertEqual(result["status"], "blocked")
                self.assertIn("--visible", result["error"])
                self.assertIn("start", result["error"])
                opened.assert_not_called()
                execute.assert_not_called()
                self.assertFalse(self.runner.state.exists())

    def test_cli_visible_start_passes_to_runner(self):
        config = self.base / "config.json"
        config.write_text(json.dumps(self.config))
        output = io.StringIO()
        with mock.patch.object(
            android.Android, "execute", return_value={"state": "running"}
        ) as run:
            with contextlib.redirect_stdout(output):
                code = android.main(
                    [
                        "--config",
                        str(config),
                        "--state-dir",
                        str(self.runner.state),
                        "start",
                        "--visible",
                        "--json",
                    ]
                )
        self.assertEqual(code, 0)
        run.assert_called_once_with("start", True)

    def test_cli_timeout_json_exit_code(self):
        config = self.base / "config.json"
        config.write_text(json.dumps(self.config))
        output = io.StringIO()
        error = android.LabError("Emulator boot/root deadline exceeded", timeout=True)
        with mock.patch.object(android.Android, "execute", side_effect=error):
            with contextlib.redirect_stdout(output):
                code = android.main(
                    [
                        "--config",
                        str(config),
                        "--state-dir",
                        str(self.runner.state),
                        "start",
                        "--json",
                    ]
                )
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "timeout")

    def test_cli_json_readonly_and_bounded_config_error(self):
        config = self.base / "config.json"
        config.write_text(json.dumps({"android": self.config}))
        result = subprocess.run(
            [
                sys.executable,
                str(SOURCE),
                "--config",
                str(config),
                "--state-dir",
                str(self.runner.state),
                "status",
                "--json",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["state"], "absent")
        self.assertFalse(self.runner.state.exists())
        config.write_text("private malformed config canary")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = android.main(
                ["--config", str(config), "--state-dir", str(self.runner.state), "status", "--json"]
            )
        self.assertEqual(code, 1)
        self.assertNotIn("canary", output.getvalue())
        self.assertLess(len(output.getvalue()), 1000)


class DisplayTests(unittest.TestCase):
    setUp = RunnerTests.setUp
    create = RunnerTests.create
    start = RunnerTests.start
    assertBlocked = RunnerTests.assertBlocked

    def select_display(self, **values):
        self.config["display"] = {"width": 720, "height": 1600, "density": 320, **values}
        self.runner = android.Android({"android": self.config}, self.base / "lab", self.backend)

    def test_display_exact_new_launch_and_config_preserve_owner_and_userdata(self):
        self.select_display()
        self.create()
        config = self.runner.avd / "config.ini"
        original = (
            b"image.sysdir.1=read-only-sdk\r\n# keep comment\r\n"
            b"hw.lcd.width = 1080\r\nhw.lcd.height=1920\r\nhw.lcd.density=420\r\n"
            b"disk.dataPartition.size=6G\r\nunrelated = value with spaces\r\n"
        )
        config.write_bytes(original)
        inode = config.stat().st_ino
        owner = self.runner.owner_file.read_bytes()
        userdata = self.runner.avd / "userdata.img"
        userdata.write_bytes(b"owned user data must survive")
        observed = {}
        spawn = self.backend.spawn

        def observe(argv, env, log):
            observed["argv"] = argv
            observed["config"] = config.read_bytes()
            observed["mode"] = config.stat().st_mode & 0o777
            return spawn(argv, env, log)

        with mock.patch.object(self.backend, "spawn", side_effect=observe):
            self.assertTrue(self.runner.execute("start", visible=True)["rooted"])
        expected = original.replace(b"hw.lcd.width = 1080", b"hw.lcd.width=720")
        expected = expected.replace(b"hw.lcd.height=1920", b"hw.lcd.height=1600")
        expected = expected.replace(b"hw.lcd.density=420", b"hw.lcd.density=320")
        self.assertEqual(observed["config"], expected)
        self.assertEqual(config.read_bytes(), expected)
        self.assertEqual(observed["mode"], 0o600)
        self.assertNotEqual(inode, config.stat().st_ino)
        argv = observed["argv"]
        self.assertEqual(argv.count("-skin"), 1)
        self.assertEqual(argv[argv.index("-skin") + 1], "720x1600")
        self.assertNotIn("-dpi-device", argv)
        self.assertNotIn("-dpi", argv)
        self.assertEqual(self.runner.owner_file.read_bytes(), owner)
        self.assertEqual(userdata.read_bytes(), b"owned user data must survive")

    def test_display_missing_keys_append_without_losing_unrelated_last_line(self):
        self.select_display()
        self.create()
        config = self.runner.avd / "config.ini"
        config.write_bytes(b"image.sysdir.1=read-only-sdk\nother=no final newline")
        self.runner.execute("start")
        self.assertEqual(
            config.read_bytes(),
            b"image.sysdir.1=read-only-sdk\nother=no final newline\n"
            b"hw.lcd.width=720\nhw.lcd.height=1600\nhw.lcd.density=320\n",
        )
        argv = next(call[0] for call in self.backend.calls if "-avd" in call[0])
        self.assertIn("-no-window", argv)
        self.assertEqual(argv[argv.index("-skin") + 1], "720x1600")

    def test_display_duplicate_target_keys_all_updated_and_restarts_idempotent(self):
        self.select_display()
        self.create()
        config = self.runner.avd / "config.ini"
        config.write_bytes(b"other=keep\nhw.lcd.width=1080\nhw.lcd.width=480\n")
        self.runner.execute("start")
        data = config.read_bytes()
        self.assertEqual(data.count(b"hw.lcd.width=720\n"), 2)
        identity = (config.stat().st_ino, config.stat().st_mtime_ns)
        self.runner.execute("stop")
        self.create()
        self.runner.execute("start")
        self.assertEqual(config.read_bytes(), data)
        self.assertEqual((config.stat().st_ino, config.stat().st_mtime_ns), identity)
        self.assertEqual(self.backend.spawn_count, 2)

    def test_display_running_reuse_and_status_never_mutate_config_or_resize(self):
        self.start()
        config = self.runner.avd / "config.ini"
        before = (config.read_bytes(), config.stat().st_ino, config.stat().st_mtime_ns)
        lease = self.runner.lease_file.read_bytes()
        owner = self.runner.owner_file.read_bytes()
        self.select_display()
        self.assertTrue(self.runner.execute("start")["rooted"])
        calls = len(self.backend.calls)
        self.assertEqual(self.runner.execute("status")["state"], "running")
        self.assertEqual(len(self.backend.calls), calls)
        self.assertEqual(self.backend.spawn_count, 1)
        self.assertEqual(
            (config.read_bytes(), config.stat().st_ino, config.stat().st_mtime_ns), before
        )
        self.assertEqual(self.runner.lease_file.read_bytes(), lease)
        self.assertEqual(self.runner.owner_file.read_bytes(), owner)
        self.assertFalse(any("wm" in call[0] for call in self.backend.calls))

    def test_display_absent_preserves_optional_old_config_and_argv(self):
        self.create()
        config = self.runner.avd / "config.ini"
        config.write_bytes(b"image.sysdir.1=read-only-sdk\nhw.lcd.width=1080\n")
        before = (config.read_bytes(), config.stat().st_ino, config.stat().st_mode)
        self.runner.execute("start")
        self.assertEqual((config.read_bytes(), config.stat().st_ino, config.stat().st_mode), before)
        argv = next(call[0] for call in self.backend.calls if "-avd" in call[0])
        self.assertNotIn("-skin", argv)
        self.assertNotIn("-dpi-device", argv)

    def test_display_strict_object_schema_rejected_before_mutation(self):
        for display in (
            None,
            [],
            "720x1600",
            {},
            {"width": 720, "height": 1600},
            {"width": 720, "height": 1600, "density": 320, "unknown": 1},
        ):
            with self.subTest(display=display):
                with self.assertRaises(android.LabError):
                    android.Android(
                        {"android": {**self.config, "display": display}},
                        self.runner.state,
                        self.backend,
                    )
        self.assertFalse(self.runner.state.exists())
        self.assertFalse(self.backend.calls)

    def test_display_strict_integer_ranges_and_boundaries(self):
        defaults = {"width": 720, "height": 1600, "density": 320}
        for field, (lower, upper) in {
            "width": (240, 4096),
            "height": (240, 4096),
            "density": (72, 640),
        }.items():
            for value in (True, False, "720", 720.0, None, -1, lower - 1, upper + 1, float("inf")):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(android.LabError):
                        android.Android(
                            {**self.config, "display": {**defaults, field: value}},
                            self.runner.state,
                            self.backend,
                        )
            for value in (lower, upper):
                with self.subTest(field=field, boundary=value):
                    android.Android(
                        {**self.config, "display": {**defaults, field: value}},
                        self.runner.state,
                        self.backend,
                    )
        self.assertFalse(self.runner.state.exists())
        self.assertFalse(self.backend.calls)

    def test_display_symlink_config_preserves_foreign_target(self):
        self.select_display()
        self.create()
        config = self.runner.avd / "config.ini"
        target = self.base / "foreign-config"
        target.write_bytes(config.read_bytes())
        config.unlink()
        config.symlink_to(target)
        self.assertBlocked("start", "symlinks")
        self.assertEqual(target.read_bytes(), b"image.sysdir.1=read-only-sdk\n")
        self.assertEqual(self.backend.spawn_count, 0)

    def test_display_hardlinked_config_preserves_external_file(self):
        self.select_display()
        self.create()
        config = self.runner.avd / "config.ini"
        target = self.base / "external-config"
        os.link(config, target)
        before = target.read_bytes()
        with self.assertRaises(android.LabError):
            self.runner.execute("start")
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(config.stat().st_nlink, 2)
        self.assertEqual(self.backend.spawn_count, 0)

    def test_display_foreign_config_file_owner_rejected(self):
        self.select_display()
        self.create()
        config = self.runner.avd / "config.ini"
        before = config.read_bytes()
        inode = config.stat().st_ino
        fstat = os.fstat

        def foreign(fd):
            info = fstat(fd)
            if info.st_ino == inode:
                return mock.Mock(
                    st_mode=info.st_mode,
                    st_uid=os.getuid() + 1,
                    st_nlink=info.st_nlink,
                    st_size=info.st_size,
                )
            return info

        with mock.patch.object(android.os, "fstat", side_effect=foreign):
            with self.assertRaises(android.LabError):
                self.runner.execute("start")
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(self.backend.spawn_count, 0)

    def test_display_foreign_avd_owner_rejected_before_config_mutation(self):
        self.select_display()
        self.create()
        config = self.runner.avd / "config.ini"
        before = config.read_bytes()
        owner = android.read_json(self.runner.owner_file)
        android.write_json(self.runner.owner_file, {**owner, "uid": os.getuid() + 1})
        self.backend.calls.clear()
        self.assertBlocked("start", "owner/configuration mismatch")
        self.assertEqual(config.read_bytes(), before)
        self.assertFalse(self.backend.calls)
        self.assertEqual(self.backend.spawn_count, 0)

    def test_display_unsafe_config_modes_and_avd_paths_rejected(self):
        self.select_display()
        self.create()
        config = self.runner.avd / "config.ini"
        before = config.read_bytes()
        for path in (config, self.runner.avd, self.runner.avds, self.runner.root):
            mode = path.stat().st_mode & 0o777
            path.chmod(0o777)
            try:
                with self.subTest(path=path):
                    with self.assertRaises(android.LabError):
                        self.runner.execute("start")
                self.assertEqual(config.read_bytes(), before)
            finally:
                path.chmod(mode)
        self.assertEqual(self.backend.spawn_count, 0)

    def test_display_update_cannot_exceed_config_bound(self):
        self.select_display()
        self.create()
        config = self.runner.avd / "config.ini"
        before = b"#" + b"x" * (64 * 1024 - 1)
        config.write_bytes(before)
        with self.assertRaises(android.LabError):
            self.runner.execute("start")
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(self.backend.spawn_count, 0)

    def test_display_unbounded_missing_or_special_config_rejected(self):
        self.select_display()
        self.create()
        config = self.runner.avd / "config.ini"
        config.write_bytes(b"x" * (64 * 1024 + 1))
        with self.assertRaises(android.LabError):
            self.runner.execute("start")
        self.assertEqual(config.stat().st_size, 64 * 1024 + 1)
        config.unlink()
        with self.assertRaises(android.LabError):
            self.runner.execute("start")
        os.mkfifo(config, 0o600)
        with self.assertRaises(android.LabError):
            self.runner.execute("start")
        config.unlink()
        config.mkdir()
        with self.assertRaises(android.LabError):
            self.runner.execute("start")
        self.assertEqual(self.backend.spawn_count, 0)

    def test_display_failed_atomic_update_preserves_original_and_never_spawns(self):
        self.select_display()
        self.create()
        config = self.runner.avd / "config.ini"
        before = config.read_bytes()
        entries = set(self.runner.avd.iterdir())
        with mock.patch.object(android.os, "replace", side_effect=OSError("fixture")):
            with self.assertRaises(OSError):
                self.runner.execute("start")
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(set(self.runner.avd.iterdir()), entries)
        self.assertEqual(self.backend.spawn_count, 0)


if __name__ == "__main__":
    unittest.main()
