#!/usr/bin/env python3
"""Offline camera protocol/arrival/launcher regressions; no hardware or model needed."""

import ctypes
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/room-camera"
sys.dont_write_bytecode = True


def load(name):
    spec = importlib.util.spec_from_file_location(name, SOURCE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


detector = load("detector")
firmware = load("firmware")
runtime = load("runtime")
camera = load("camera")


class GateTests(unittest.TestCase):
    def test_noise_is_not_an_arrival(self):
        gate = detector.ArrivalGate()
        for now, found in [(0, True), (0.5, False), (1, True), (1.5, False)]:
            self.assertFalse(gate.update(found, now))

    def test_sustained_presence_alerts_once(self):
        gate = detector.ArrivalGate()
        alerts = [t for t in range(121) if gate.update(True, t)]
        self.assertEqual(alerts, [1])

    def test_short_detection_miss_does_not_rearm(self):
        gate = detector.ArrivalGate(cooldown=0)
        gate.update(True, 0)
        self.assertTrue(gate.update(True, 1))
        gate.update(False, 2)
        self.assertFalse(gate.update(True, 3))
        self.assertFalse(gate.update(True, 4))

    def test_new_arrival_and_cooldown(self):
        gate = detector.ArrivalGate()
        gate.update(True, 0)
        self.assertTrue(gate.update(True, 1))
        gate.update(False, 6)
        self.assertFalse(gate.update(True, 10))
        self.assertFalse(gate.update(True, 11))
        for t in range(12, 61):
            self.assertFalse(gate.update(True, t))
        self.assertTrue(gate.update(True, 61))
        gate.update(False, 70)
        gate.update(True, 130)
        self.assertTrue(gate.update(True, 131))


class Function:
    def __init__(self, function):
        self.function = function

    def __call__(self, *args):
        return self.function(*args)


class FakeUSB:
    def __init__(self, fail_at=None, result=None):
        self.calls = []
        self.fail_at, self.result = fail_at, result
        self.closed = False
        self.exited = False
        for name, function in {
            "init": lambda _: 0,
            "exit": lambda _: setattr(self, "exited", True),
            "open_device_with_vid_pid": lambda *_: 123,
            "close": lambda _: setattr(self, "closed", True),
            "kernel_driver_active": lambda *_: 0,
            "claim_interface": lambda *_: 0,
            "detach_kernel_driver": lambda *_: 0,
            "release_interface": lambda *_: 0,
            "control_transfer": self.transfer,
            "error_name": lambda _: b"TEST_ERROR",
        }.items():
            setattr(self, "libusb_" + name, Function(function))

    def transfer(self, handle, kind, request, value, index, data, size, timeout):
        self.calls.append((kind, request, value, index, ctypes.string_at(data, size), timeout))
        return self.result if len(self.calls) == self.fail_at else size


class UploadTests(unittest.TestCase):
    payload = bytes((i % 256 for i in range(68948)))

    def run_upload(self, usb):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(firmware.C, "CDLL", return_value=usb),
            patch.object(firmware.hashlib, "sha256") as digest,
        ):
            digest.return_value.hexdigest.return_value = firmware.FIRMWARE_SHA256
            path = Path(tmp) / "firmware.bin"
            path.write_bytes(self.payload)
            firmware.upload(path, "test-library")

    def test_exact_protocol_and_rollover(self):
        usb = FakeUSB()
        self.run_upload(usb)
        self.assertEqual(len(usb.calls), 136)
        self.assertEqual(usb.calls[0][:4], (0x40, 0, 0, 0x14))
        self.assertEqual(usb.calls[128][:4], (0x40, 0, 0, 0x15))
        self.assertEqual(usb.calls[-2][2:5], (0xC00, 0x15, self.payload[-340:]))
        self.assertEqual(usb.calls[-1][2:5], (0x2200, 0x8018, b"\x5b"))
        self.assertEqual(b"".join(call[4] for call in usb.calls[:-1]), self.payload)
        self.assertTrue(usb.closed and usb.exited)

    def test_data_disconnect_aborts_before_activation(self):
        usb = FakeUSB(fail_at=2, result=-4)
        with self.assertRaisesRegex(RuntimeError, "TEST_ERROR"):
            self.run_upload(usb)
        self.assertEqual(len(usb.calls), 2)
        self.assertTrue(usb.closed and usb.exited)

    def test_short_write_aborts(self):
        usb = FakeUSB(fail_at=1, result=1)
        with self.assertRaisesRegex(RuntimeError, "Incomplete"):
            self.run_upload(usb)
        self.assertEqual(len(usb.calls), 1)

    def test_final_activation_disconnect_is_expected(self):
        self.run_upload(FakeUSB(fail_at=136, result=-4))

    def test_unrecognized_firmware_never_opens_usb(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(firmware.C, "CDLL") as library:
            path = Path(tmp) / "firmware.bin"
            path.write_bytes(b"untrusted")
            with self.assertRaisesRegex(RuntimeError, "unrecognized"):
                firmware.upload(path, "test-library")
            library.assert_not_called()


class PlayerTests(unittest.TestCase):
    def child(self, program):
        child = subprocess.Popen([sys.executable, "-c", program], stdin=subprocess.PIPE, bufsize=0)

        def cleanup():
            if child.poll() is None:
                child.kill()
            child.wait(timeout=2)
            child.stdin.close()

        self.addCleanup(cleanup)
        return child

    def test_failed_player_is_not_silent_success(self):
        child = self.child("raise SystemExit(23)")
        child.wait(timeout=2)
        with self.assertRaisesRegex(RuntimeError, "status 23"):
            runtime.deliver_frame(child, b"frame")

    def test_broken_pipe_race_checks_final_status(self):
        child = self.child("raise SystemExit(23)")
        child.wait(timeout=2)
        with patch.object(child, "poll", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "status 23"):
                runtime.deliver_frame(child, b"frame")

    def test_closed_player_is_normal_exit(self):
        child = self.child("pass")
        child.wait(timeout=2)
        with self.assertRaises(runtime.PreviewClosed):
            runtime.deliver_frame(child, b"frame")

    def test_paused_consumer_cannot_block_forever(self):
        child = self.child("import time; time.sleep(10)")
        with self.assertRaisesRegex(RuntimeError, "paused or unresponsive"):
            runtime.deliver_frame(child, b"x" * 1000000, timeout=0.1)


class ViewerTests(unittest.TestCase):
    def test_explicit_tested_mode_and_no_downscaling(self):
        with patch.dict(os.environ, CAMERA_FFPLAY="/tools/ffplay"):
            command = camera.player_command()
            self.assertEqual(command[command.index("-framerate") + 1], "30")
            self.assertEqual(command[command.index("-video_size") + 1], "1920x1080")
            self.assertIn(firmware.DEVICE, command)
            self.assertNotIn("-vf", command)
            self.assertEqual(camera.player_command(True)[-1], "-an")

    def test_existing_camera_does_not_upload_again(self):
        with (
            patch.object(camera.Path, "exists", return_value=True),
            patch.object(camera, "upload") as upload,
        ):
            camera.ensure_camera()
            upload.assert_not_called()

    def test_no_automatic_recording_or_network_service(self):
        module = (ROOT / "modules/nixos/desktop/ps5-camera.nix").read_text()
        self.assertIn('ATTR{idProduct}=="0580"', module)
        self.assertIn('TAG+="uaccess"', module)
        self.assertNotIn('MODE="0666"', module)
        self.assertNotIn("RUN+=", module)
        self.assertNotIn("systemd.services", module)
        source = (SOURCE / "camera.py").read_text()
        for forbidden in ("VideoWriter(", "imwrite(", "requests.", "http.server"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
