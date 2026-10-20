"""One-shot ENE RAM lighting with a fresh registry and one verified adapter."""

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def adapter_node(settings, devices=Path("/sys/bus/i2c/devices"), dev=Path("/dev")):
    matches = []
    for adapter in devices.glob("i2c-*"):
        name = (adapter / "name").read_text().strip()
        for parent in adapter.resolve().parents:
            if (parent / "vendor").exists() and (parent / "device").exists():
                identity = (
                    (parent / "vendor").read_text().strip(),
                    (parent / "device").read_text().strip(),
                    (parent / "driver").resolve().name,
                )
                expected = (settings["pciVendor"], settings["pciDevice"], settings["driver"])
                if identity == expected and name.startswith(settings["adapterNamePrefix"]):
                    matches.append(dev / adapter.name)
                break
    if len(matches) != 1:
        raise RuntimeError(f"Expected one configured RAM adapter, found {len(matches)}")
    return matches[0]


def restrict_registry(config):
    detectors = config.get("Detectors", {}).get("detectors", {})
    if (
        not isinstance(detectors, dict)
        or "ENE SMBus DRAM" not in detectors
        or not all(isinstance(v, bool) for v in detectors.values())
    ):
        raise RuntimeError("OpenRGB did not generate its complete detector registry")
    # Discard every other setting: no profiles, calibration or saved mode writes.
    return {
        "Detectors": {"detectors": {name: name == "ENE SMBus DRAM" for name in detectors}},
        "ENESMBusSettings": {"enable_save": False},
    }


def verify_controllers(output, expected, node):
    blocks = re.split(r"(?m)^(\d+): ", output)
    controllers = list(zip(blocks[1::2], blocks[2::2], strict=True))
    if len(controllers) != expected:
        raise RuntimeError(f"Expected {expected} ENE RAM controllers, found {len(controllers)}")
    addresses = set()
    for _, info in controllers:
        if info.splitlines()[0] != "ENE DRAM":
            raise RuntimeError("Unexpected controller family; no colors applied")
        if not re.search(r"^\s*Type:\s+DRAM\s*$", info, re.MULTILINE):
            raise RuntimeError("Non-DRAM controller found; no colors applied")
        modes = next((line for line in info.splitlines() if line.strip().startswith("Modes:")), "")
        if not re.search(r"\bStatic\b", modes):
            raise RuntimeError("Static RAM mode not available")
        location = next(
            (line for line in info.splitlines() if line.strip().startswith("Location:")), ""
        )
        match = re.search(r"\(" + re.escape(str(node)) + r"\), address (0x[0-9a-f]+)$", location)
        if not match or match[1] in addresses:
            raise RuntimeError("RAM location is unexpected or duplicated")
        addresses.add(match[1])


def sandbox(bwrap, directory, node=None):
    command = [
        bwrap,
        "--ro-bind",
        "/",
        "/",
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--tmpfs",
        "/tmp",
        "--bind",
        str(directory),
        str(directory),
        "--chdir",
        str(directory),
        "--setenv",
        "HOME",
        str(directory),
    ]
    if node is not None:
        command += ["--dev-bind", str(node), str(node)]
    return command


def cleanup_module(modprobe, runtime):
    marker = runtime / "loaded-i2c-dev"
    if not marker.exists():
        return
    if Path("/sys/module/i2c_dev").exists():
        result = subprocess.run([modprobe, "-r", "i2c-dev"], timeout=15, check=False)
        if result.returncode:
            print("i2c-dev remains in use; no user ACLs were granted.", file=sys.stderr)
            return
    marker.unlink(missing_ok=True)


def interrupted(signum, _frame):
    # subprocess.run unwinds by killing/reaping its direct child; bwrap's
    # --die-with-parent terminates the contained process as well.
    raise SystemExit(128 + signum)


def main():
    runtime = Path(os.environ["RUNTIME_DIRECTORY"])
    if sys.argv[1] == "--cleanup":
        cleanup_module(sys.argv[2], runtime)
        return
    signal.signal(signal.SIGTERM, interrupted)
    settings_file, openrgb, bwrap, modprobe = sys.argv[1:]
    settings = json.loads(Path(settings_file).read_text())
    try:
        if not Path("/sys/module/i2c_dev").exists():
            # Written before loading so ExecStopPost can clean up if killed.
            (runtime / "loaded-i2c-dev").touch(mode=0o600)
        subprocess.run([modprobe, "i2c-dev"], check=True, timeout=15)
        deadline = time.monotonic() + 45
        while True:
            try:
                node = adapter_node(settings)
                if not node.is_char_device():
                    raise RuntimeError("RAM adapter device node is not ready")
                device_number = Path("/sys/class/i2c-dev") / node.name / "dev"
                major, minor = map(int, device_number.read_text().strip().split(":"))
                if node.stat().st_rdev != os.makedev(major, minor):
                    raise RuntimeError("RAM adapter node differs from its sysfs device number")
                break
            except (OSError, RuntimeError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(2)
        with tempfile.TemporaryDirectory(prefix="config-", dir=runtime) as temp:
            directory = Path(temp)
            invocation = [openrgb, "--config", temp, "--noautoconnect"]

            def run(node=None, *args):
                result = subprocess.run(
                    sandbox(bwrap, directory, node) + ["--"] + invocation + list(args),
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode:
                    # Do not dump device inventory (which can contain serials).
                    raise RuntimeError(f"OpenRGB sandbox failed: {result.stderr.strip()}")
                return result.stdout

            # Same pinned binary, no raw hardware devices: generate all defaults
            # before disabling all but ENE. Missing detector keys default TRUE.
            run(None, "--list-devices")
            config_path = directory / "OpenRGB.json"
            registry = restrict_registry(json.loads(config_path.read_text()))
            config_path.write_text(json.dumps(registry))
            # Verify missing defaults cannot silently expand the allowlist.
            run(None, "--list-devices")
            current = json.loads(config_path.read_text())["Detectors"]["detectors"]
            if current != registry["Detectors"]["detectors"]:
                raise RuntimeError("Detector registry changed after restricting it")
            scan = run(node, "--list-devices")
            verify_controllers(scan, settings["moduleCount"], node)
            # RAM discovery itself remaps ENE controller addresses. No SPD
            # detectors are enabled; no persistent SaveMode operation is used.
            run(node, "--mode", "Static", "--color", "FFFFFF")
            print(
                f"Static white command completed for {settings['moduleCount']} ENE DRAM controllers."
            )
    finally:
        cleanup_module(modprobe, runtime)


if __name__ == "__main__":
    main()
