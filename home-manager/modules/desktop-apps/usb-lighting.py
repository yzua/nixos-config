"""Restore selected USB lighting only; never initialize or configure cooling."""

import fcntl
import json
import os
import sys
import time
from pathlib import Path

from liquidctl import find_liquidctl_devices


def apply(settings, discover=find_liquidctl_devices):
    for name in ("lighting", "cooler"):
        device = settings[name]
        matches = list(
            discover(vendor=int(device["vendorId"], 16), product=int(device["productId"], 16))
        )
        if len(matches) != 1:
            raise RuntimeError(f"Expected one configured {name} controller; found {len(matches)}")
        with matches[0].connect() as controller:
            if name == "lighting":
                controller.set_color("sync", "fixed", [[255, 255, 255]])
            else:
                pump_color = device["pumpColor"]
                if len(pump_color) != 3 or any(
                    type(value) is not int or not 0 <= value <= 255 for value in pump_color
                ):
                    raise RuntimeError("Invalid configured pump RGB balance")
                colors = [pump_color] * device["pumpLedCount"]
                colors += [[255, 255, 255]] * device["fanLedCount"]
                if controller._led_count != len(colors):
                    raise RuntimeError("Cooler LED count differs from the configured pump/fans")
                # OpenRGB shutdown can invalidate this software-only flag.
                # Force the pinned driver's lighting enable, NOT initialize().
                controller._data.store("leds_enabled", 0)
                controller.set_color("led", "super-fixed", colors)


def main():
    settings = json.loads(Path(sys.argv[1]).read_text())
    runtime = Path(os.environ["XDG_RUNTIME_DIR"])
    with (runtime / "usb-lighting.lock").open("w") as lock:
        deadline = time.monotonic() + 45
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                apply(settings)
                print(
                    "USB lighting restored: headers/fans white, configured block balance; cooling unchanged."
                )
                return
            except (OSError, RuntimeError) as error:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        "USB lighting unavailable after waiting for active-seat permissions"
                    ) from error
                time.sleep(2)


if __name__ == "__main__":
    main()
