#!/usr/bin/env python3
"""Hardware-free regressions for startup lighting targets and isolation."""

import ctypes
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Stub only the dependency boundary, not the lighting operation under test.
liquidctl = types.ModuleType("liquidctl")
liquidctl.find_liquidctl_devices = lambda **_: []
sys.modules["liquidctl"] = liquidctl
usb = load_module("usb_lighting", "home-manager/modules/desktop-apps/usb-lighting.py")
ram = load_module("ram_lighting", "modules/nixos/desktop/ram-lighting.py")
gpu = load_module("gpu_lighting", "modules/nixos/desktop/gpu-lighting.py")


class Controller:
    def __init__(self, leds=24):
        self.calls = []
        self._led_count = leds
        self._data = types.SimpleNamespace(store=lambda *args: self.calls.append(("cache", *args)))

    def connect(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def set_color(self, *args):
        self.calls.append(("color", *args))


class USBTests(unittest.TestCase):
    def test_login_waits_for_interactive_lock_before_applying(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = Path(temp) / "settings.json"
            settings.write_text("{}")
            with (
                patch.object(usb.sys, "argv", ["restore-usb-lighting", str(settings)]),
                patch.dict(usb.os.environ, {"XDG_RUNTIME_DIR": temp}),
                patch.object(usb.fcntl, "flock", side_effect=[BlockingIOError(), None]) as lock,
                patch.object(usb.time, "sleep") as wait,
                patch.object(usb, "apply") as apply,
            ):
                usb.main()
                self.assertEqual(lock.call_count, 2)
                wait.assert_called_once_with(2)
                apply.assert_called_once_with({})

    def test_exact_targets_and_colors_without_cooling(self):
        header, cooler = Controller(), Controller()
        settings = {
            "lighting": {"vendorId": "1234", "productId": "5678"},
            "cooler": {
                "vendorId": "abcd",
                "productId": "ef01",
                "pumpLedCount": 16,
                "fanLedCount": 8,
                "pumpColor": [8, 8, 255],
            },
        }
        lookups = []

        def discover(**ids):
            lookups.append(ids)
            return [header] if ids["vendor"] == 0x1234 else [cooler]

        usb.apply(settings, discover)
        self.assertEqual(
            lookups, [{"vendor": 0x1234, "product": 0x5678}, {"vendor": 0xABCD, "product": 0xEF01}]
        )
        self.assertEqual(header.calls, [("color", "sync", "fixed", [[255, 255, 255]])])
        self.assertEqual(
            cooler.calls,
            [
                ("cache", "leds_enabled", 0),
                ("color", "led", "super-fixed", [[8, 8, 255]] * 16 + [[255, 255, 255]] * 8),
            ],
        )
        # The fake has no initialize(), fan-speed or pump-mode API. An accidental
        # call to any such operation would fail this real caller-path test.

    def test_missing_or_ambiguous_controller_fails(self):
        settings = {"lighting": {"vendorId": "1234", "productId": "5678"}}
        for matches in ([], [Controller(), Controller()]):
            with self.assertRaises(RuntimeError):
                usb.apply(settings, lambda matches=matches, **_: matches)

    def test_wrong_led_count_never_writes_cooler_lighting(self):
        settings = {
            "lighting": {"vendorId": "1234", "productId": "5678"},
            "cooler": {
                "vendorId": "abcd",
                "productId": "ef01",
                "pumpLedCount": 16,
                "fanLedCount": 8,
                "pumpColor": [8, 8, 255],
            },
        }
        cooler = Controller(48)
        with self.assertRaises(RuntimeError):
            usb.apply(
                settings, lambda **ids: [Controller()] if ids["vendor"] == 0x1234 else [cooler]
            )
        self.assertEqual(cooler.calls, [])


class RAMTests(unittest.TestCase):
    def test_only_ene_enabled_and_save_disabled(self):
        registry = {
            "Detectors": {
                "detectors": {"ENE SMBus DRAM": True, "SPD detector": True, "Future device": True}
            },
            "AutoStart": {"profile": "unsafe"},
        }
        restricted = ram.restrict_registry(registry)
        self.assertEqual(
            restricted,
            {
                "Detectors": {
                    "detectors": {
                        "ENE SMBus DRAM": True,
                        "SPD detector": False,
                        "Future device": False,
                    }
                },
                "ENESMBusSettings": {"enable_save": False},
            },
        )
        self.assertNotIn("AutoStart", restricted)

    def test_invalid_registry_fails_closed(self):
        for config in (
            {},
            {"Detectors": {"detectors": []}},
            {"Detectors": {"detectors": {"ENE SMBus DRAM": "true"}}},
        ):
            with self.assertRaises(RuntimeError):
                ram.restrict_registry(config)

    @staticmethod
    def listing(count=4, node="/dev/i2c-7", name="ENE DRAM", kind="DRAM", mode="Static"):
        return "".join(
            f"{i}: {name}\n  Type: {kind}\n  Location: I2C: verified adapter ({node}), address {hex(0x70 + i)}\n  Modes: Direct Off {mode}\n"
            for i in range(count)
        )

    def test_four_expected_controllers(self):
        ram.verify_controllers(self.listing(), 4, Path("/dev/i2c-7"))
        for output in (
            self.listing(3),
            self.listing(node="/dev/i2c-1"),
            self.listing(name="GPU"),
            self.listing(kind="Motherboard"),
            self.listing(mode="Rainbow"),
        ):
            with self.assertRaises(RuntimeError):
                ram.verify_controllers(output, 4, Path("/dev/i2c-7"))

    def test_sandbox_has_no_devices_during_seeding(self):
        command = ram.sandbox("bwrap", Path("/run/example"))
        self.assertNotIn("--dev-bind", command)
        for option in ("--dev", "--proc", "--unshare-all", "--ro-bind"):
            self.assertIn(option, command)
        command = ram.sandbox("bwrap", Path("/run/example"), Path("/dev/i2c-7"))
        self.assertEqual(command[-3:], ["--dev-bind", "/dev/i2c-7", "/dev/i2c-7"])
        self.assertEqual(command.count("--dev-bind"), 1)

    def test_adapter_selection_uses_facts_not_bus_number(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            devices = root / "bus"
            devices.mkdir()
            pci = root / "pci"
            pci.mkdir()
            (pci / "vendor").write_text("0x1111")
            (pci / "device").write_text("0x2222")
            (pci / "driver").symlink_to(root / "test_driver")
            adapter = pci / "i2c-7"
            adapter.mkdir()
            (adapter / "name").write_text("Verified RAM adapter at arbitrary location")
            (devices / "i2c-7").symlink_to(adapter)
            settings = {
                "pciVendor": "0x1111",
                "pciDevice": "0x2222",
                "driver": "test_driver",
                "adapterNamePrefix": "Verified RAM adapter at ",
            }
            self.assertEqual(ram.adapter_node(settings, devices), Path("/dev/i2c-7"))
            settings["pciDevice"] = "0x3333"
            with self.assertRaises(RuntimeError):
                ram.adapter_node(settings, devices)


class GPUTests(unittest.TestCase):
    @staticmethod
    def state(mode=0x08, brightness=80, color=None):
        return {
            "mode": mode,
            "brightness": brightness,
            "speed": 2,
            "rgb1": color or [255, 255, 255],
            "rgb2": [0, 0, 224],
            "rgb3": [0, 224, 0],
        }

    def test_apply_white_preserves_brightness_speed_and_other_colors(self):
        before, after = self.state(), self.state(mode=0x13)
        with patch.object(gpu, "read_state", side_effect=[before, after]) as read:
            calls = []
            self.assertTrue(
                gpu.apply_white(
                    {"brightness": 80, "detectorName": "Exact card"},
                    lambda: read("/dev/fake"),
                    lambda *args: calls.append(args),
                )
            )
        self.assertEqual(
            calls,
            [
                (
                    "--device",
                    "Exact card",
                    "--mode",
                    "Direct",
                    "--color",
                    "FFFFFF",
                    "--brightness",
                    "80",
                )
            ],
        )

    def test_already_correct_state_skips_all_writes(self):
        calls = []
        self.assertFalse(
            gpu.apply_white(
                {"brightness": 80}, lambda: self.state(mode=0x13), lambda *args: calls.append(args)
            )
        )
        self.assertEqual(calls, [])

    def test_readback_mismatch_or_unrequested_change_fails(self):
        for after in (
            self.state(mode=0x08),
            self.state(mode=0x13, brightness=100),
            self.state(mode=0x13, color=[0, 0, 0]),
            {**self.state(mode=0x13), "speed": 1},
        ):
            states = iter([self.state(), after])
            with self.assertRaises(RuntimeError):
                gpu.apply_white(
                    {"brightness": 80, "detectorName": "Exact card"},
                    lambda: next(states),
                    lambda *_: None,
                )

    def test_registry_only_enables_exact_gpu(self):
        restricted = gpu.restrict_registry(
            {
                "Detectors": {"detectors": {"Exact card": True, "Other GPU": True}},
                "AutoStart": {"profile": "unsafe"},
            },
            "Exact card",
        )
        self.assertEqual(
            restricted, {"Detectors": {"detectors": {"Exact card": True, "Other GPU": False}}}
        )
        with self.assertRaises(RuntimeError):
            gpu.restrict_registry({}, "Exact card")

    def test_only_normal_addressed_reads_and_failed_reads_remain_signed(self):
        registers = {0x22: 0x08, 0x36: 80, 0x38: 2}
        requests = []

        def ioctl(_fd, operation, arg):
            if operation == gpu.I2C_SLAVE:
                self.assertEqual(arg, 0x68)
                return 0
            self.assertEqual(operation, gpu.I2C_SMBUS)
            request = ctypes.cast(arg, ctypes.POINTER(gpu.Request)).contents
            self.assertEqual((request.read_write, request.size), (1, 2))
            requests.append(request.command)
            request.data.contents.byte = registers.get(request.command, 255)
            return 0

        fake = types.SimpleNamespace(ioctl=ioctl)
        with (
            patch.object(gpu.ctypes, "CDLL", return_value=fake),
            patch.object(gpu.os, "open", return_value=42),
            patch.object(gpu.os, "close"),
        ):
            self.assertEqual(gpu.read_state("/dev/fake")["brightness"], 80)
            self.assertEqual(len(requests), 12)
            registers[0x38] = 4
            self.assertEqual(gpu.read_state("/dev/fake")["speed"], 4)
            registers[0x38] = 0
            with self.assertRaises(RuntimeError):
                gpu.read_state("/dev/fake")
            registers[0x38] = 2
            requests.clear()
            registers[0x22] = 255
            with self.assertRaises(RuntimeError):
                gpu.read_state("/dev/fake")
            self.assertEqual(requests, [0x22])
        fake.ioctl = lambda *_: -1
        with (
            patch.object(gpu.ctypes, "CDLL", return_value=fake),
            patch.object(gpu.os, "open", return_value=42),
            patch.object(gpu.os, "close"),
        ):
            with self.assertRaises(OSError):
                gpu.read_state("/dev/fake")

    def test_exact_subsystem_driver_port_and_node_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            devices, dev, devclass, pci = (root / name for name in ("bus", "dev", "class", "pci"))
            for p in (devices, dev, devclass, pci):
                p.mkdir()
            facts = {
                "vendor": "0x10de",
                "device": "0x1f07",
                "subsystem_vendor": "0x1462",
                "subsystem_device": "0x3733",
            }
            for name, value in facts.items():
                (pci / name).write_text(value)
            (pci / "driver").symlink_to(root / "nvidia")
            adapter = pci / "i2c-7"
            adapter.mkdir()
            (adapter / "name").write_text("NVIDIA i2c adapter 1 at arbitrary GPU")
            (devices / "i2c-7").symlink_to(adapter)
            (dev / "i2c-7").symlink_to("/dev/null")
            (devclass / "i2c-7").mkdir()
            (devclass / "i2c-7/dev").write_text("1:3")
            settings = {
                "pciVendor": "0x10de",
                "pciDevice": "0x1f07",
                "pciSubsystemVendor": "0x1462",
                "pciSubsystemDevice": "0x3733",
                "driver": "nvidia",
                "adapterNamePrefix": "NVIDIA i2c adapter 1 at ",
            }
            self.assertEqual(gpu.adapter_node(settings, devices, dev, devclass), dev / "i2c-7")
            for key, value in (
                ("pciSubsystemDevice", "0x3732"),
                ("driver", "nouveau"),
                ("adapterNamePrefix", "NVIDIA i2c adapter 2 at "),
            ):
                with self.assertRaises(RuntimeError):
                    gpu.adapter_node({**settings, key: value}, devices, dev, devclass)
            (devclass / "i2c-7/dev").write_text("1:5")
            with self.assertRaises(RuntimeError):
                gpu.adapter_node(settings, devices, dev, devclass)


if __name__ == "__main__":
    unittest.main()
