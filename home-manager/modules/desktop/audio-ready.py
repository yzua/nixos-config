#!/usr/bin/env python3
"""Wait briefly for WirePlumber's real default output and its playback ports."""

import json
import subprocess
import sys
import time


def output_ready(graph):
    """Inspect a pw-dump snapshot without changing defaults, volume, or links."""
    default = None
    for obj in graph:
        if obj.get("props", {}).get("metadata.name") == "default":
            for entry in obj.get("metadata", []):
                if entry.get("subject") == 0 and entry.get("key") == "default.audio.sink":
                    value = entry.get("value", {})
                    if isinstance(value, str):
                        value = json.loads(value)
                    default = value.get("name")
    if not default:
        return False
    for obj in graph:
        if obj.get("type") != "PipeWire:Interface:Node":
            continue
        props = obj.get("info", {}).get("props", {})
        if props.get("node.name") != default or props.get("media.class") != "Audio/Sink":
            continue
        # Never accept EasyEffects (or another virtual sink) as hardware readiness.
        if "device.id" not in props or props.get("node.virtual") in (True, "true"):
            return False
        ports = [
            port
            for port in graph
            if port.get("type") == "PipeWire:Interface:Port"
            and str(port.get("info", {}).get("props", {}).get("node.id")) == str(obj["id"])
            and port.get("info", {}).get("props", {}).get("port.direction") == "in"
        ]
        return len(ports) >= max(1, int(props.get("audio.channels", 2)))
    return False


def probe():
    result = subprocess.run(["pw-dump"], capture_output=True, text=True, check=True, timeout=2)
    return output_ready(json.loads(result.stdout))


def wait_for_output(check=probe, timeout=20, interval=0.25):
    deadline = time.monotonic() + timeout
    while True:
        try:
            if check():
                return True
        except (subprocess.SubprocessError, OSError, ValueError, TypeError, KeyError):
            pass  # The server or its device metadata may not be ready yet.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(interval, remaining))


def main():
    if wait_for_output():
        return 0
    print(
        "Timed out waiting for a physical default audio output and playback ports", file=sys.stderr
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
