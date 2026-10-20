"""Restore the experimentally validated MSI GPU's white lighting, never save it."""

import ctypes
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

I2C_SLAVE = 0x0703
I2C_SMBUS = 0x0720
I2C_SMBUS_READ = 1
I2C_SMBUS_BYTE_DATA = 2
MODES = {
    0x01,
    0x08,
    0x13,
    0x1A,
    0x07,
    0x05,
    0x06,
    0x15,
    0x1F,
    0x16,
    0x0D,
    0x0B,
    0x09,
    0x0F,
    0x11,
    0x1D,
    0x14,
    0x04,
    0x02,
    0x03,
}


class Data(ctypes.Union):
    _fields_ = [("byte", ctypes.c_uint8), ("word", ctypes.c_uint16), ("block", ctypes.c_uint8 * 34)]


class Request(ctypes.Structure):
    _fields_ = [
        ("read_write", ctypes.c_uint8),
        ("command", ctypes.c_uint8),
        ("size", ctypes.c_uint32),
        ("data", ctypes.POINTER(Data)),
    ]


def read_state(node):
    libc = ctypes.CDLL(None, use_errno=True)
    fd = os.open(node, os.O_RDWR | os.O_CLOEXEC)
    try:
        # Do not force an endpoint claimed by a kernel driver.
        if libc.ioctl(fd, I2C_SLAVE, 0x68) < 0:
            raise OSError(ctypes.get_errno(), "Cannot select MSI lighting address without force")

        def read(register):
            data = Data()
            request = Request(I2C_SMBUS_READ, register, I2C_SMBUS_BYTE_DATA, ctypes.pointer(data))
            if libc.ioctl(fd, I2C_SMBUS, ctypes.byref(request)) < 0:
                raise OSError(ctypes.get_errno(), f"GPU register 0x{register:02x} read failed")
            return data.byte

        mode = read(0x22)
        if mode not in MODES:
            raise RuntimeError("Unexpected MSI mode; no lighting write attempted")
        brightness = read(0x36)
        if brightness not in {0, 20, 40, 60, 80, 100}:
            raise RuntimeError("Unexpected MSI brightness; no lighting write attempted")
        speed = read(0x38)
        if speed not in {1, 2, 4}:
            raise RuntimeError("Unexpected MSI speed; no lighting write attempted")
        return {
            "mode": mode,
            "brightness": brightness,
            "speed": speed,
            "rgb1": [read(r) for r in (0x30, 0x31, 0x32)],
            "rgb2": [read(r) for r in (0x27, 0x28, 0x29)],
            "rgb3": [read(r) for r in (0x2A, 0x2B, 0x2C)],
        }
    finally:
        os.close(fd)


def adapter_node(
    settings,
    devices=Path("/sys/bus/i2c/devices"),
    dev=Path("/dev"),
    devclass=Path("/sys/class/i2c-dev"),
):
    matches = []
    for adapter in devices.glob("i2c-*"):
        if not (adapter / "name").read_text().strip().startswith(settings["adapterNamePrefix"]):
            continue
        for parent in adapter.resolve().parents:
            if (parent / "vendor").exists() and (parent / "device").exists():
                identity = tuple(
                    (parent / key).read_text().strip()
                    for key in ("vendor", "device", "subsystem_vendor", "subsystem_device")
                )
                expected = tuple(
                    settings[key]
                    for key in (
                        "pciVendor",
                        "pciDevice",
                        "pciSubsystemVendor",
                        "pciSubsystemDevice",
                    )
                )
                if (
                    identity == expected
                    and (parent / "driver").resolve().name == settings["driver"]
                ):
                    matches.append(dev / adapter.name)
                break
    if len(matches) != 1:
        raise RuntimeError(f"Expected one exact GPU port-1 adapter; found {len(matches)}")
    node = matches[0]
    if not node.is_char_device():
        raise RuntimeError("GPU adapter character device is not ready")
    major, minor = map(int, (devclass / node.name / "dev").read_text().strip().split(":"))
    if node.stat().st_rdev != os.makedev(major, minor):
        raise RuntimeError("GPU device number differs from verified sysfs adapter")
    return node


def restrict_registry(config, detector):
    names = config.get("Detectors", {}).get("detectors", {})
    if (
        not isinstance(names, dict)
        or detector not in names
        or not all(isinstance(v, bool) for v in names.values())
    ):
        raise RuntimeError("Experimental detector registry is invalid")
    return {"Detectors": {"detectors": {name: name == detector for name in names}}}


def is_white(state, brightness):
    return (
        state["mode"] == 0x13
        and state["brightness"] == brightness
        and state["rgb1"] == [255, 255, 255]
    )


def apply_white(settings, read, rgb):
    before = read()
    if is_white(before, settings["brightness"]):
        return False
    rgb(
        "--device",
        settings["detectorName"],
        "--mode",
        "Direct",
        "--color",
        "FFFFFF",
        "--brightness",
        str(settings["brightness"]),
    )
    after = read()
    if not is_white(after, settings["brightness"]):
        raise RuntimeError(
            "GPU readback differs from white; hardware may be partially changed; no automatic retry"
        )
    if any(after[key] != before[key] for key in ("speed", "rgb2", "rgb3")):
        raise RuntimeError("Unrequested lighting registers changed; no automatic retry")
    return True


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--state":
        print(json.dumps(read_state(sys.argv[2])))
        return
    settings_file, binary, bwrap, modprobe, common_path = sys.argv[1:]
    spec = importlib.util.spec_from_file_location("ram_lighting_common", common_path)
    common = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(common)
    signal.signal(signal.SIGTERM, common.interrupted)
    runtime = Path(os.environ["RUNTIME_DIRECTORY"])
    settings = json.loads(Path(settings_file).read_text())
    try:
        if not Path("/sys/module/i2c_dev").exists():
            (runtime / "loaded-i2c-dev").touch(mode=0o600)
        subprocess.run([modprobe, "i2c-dev"], check=True, timeout=15)
        deadline = time.monotonic() + 45
        while True:
            try:
                node = adapter_node(settings)
                break
            except (OSError, RuntimeError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(2)
        with tempfile.TemporaryDirectory(prefix="config-", dir=runtime) as temp:
            directory = Path(temp)

            def run(device, command):
                result = subprocess.run(
                    common.sandbox(bwrap, directory, device) + ["--"] + command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode:
                    raise RuntimeError(f"GPU lighting sandbox failed: {result.stderr.strip()}")
                return result.stdout

            def rgb(device, *args):
                return run(device, [binary, "--config", temp, "--noautoconnect", *args])

            # The same immutable binary generates and then verifies its complete
            # allowlist with no raw device nodes. GUI settings are never inherited.
            rgb(None, "--list-devices")
            config_path = directory / "OpenRGB.json"
            registry = restrict_registry(
                json.loads(config_path.read_text()), settings["detectorName"]
            )
            config_path.write_text(json.dumps(registry))
            rgb(None, "--list-devices")
            if (
                json.loads(config_path.read_text())["Detectors"]["detectors"]
                != registry["Detectors"]["detectors"]
            ):
                raise RuntimeError("GPU detector allowlist changed; no hardware write attempted")

            def read():
                return json.loads(
                    run(node, [sys.executable, str(Path(__file__).resolve()), "--state", str(node)])
                )

            changed = apply_white(settings, read, lambda *args: rgb(node, *args))
            print(
                "GPU static white verified at configured brightness; "
                + ("restored." if changed else "already correct.")
            )
    finally:
        common.cleanup_module(modprobe, runtime)


if __name__ == "__main__":
    main()
