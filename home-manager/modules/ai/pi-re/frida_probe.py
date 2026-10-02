#!/usr/bin/env python3
"""Bounded Frida Python attach, messages and RPC probe (parent enforces identity)."""

import argparse
import json
import sys
import threading
from pathlib import Path

import frida

DEFAULT_AGENT = """
rpc.exports = {
  probe() { return {pid: Process.id, arch: Process.arch,
    modules: Process.enumerateModules().slice(0, 3).map(m => ({name: m.name, size: m.size}))}; }
};
send({event: 'ready', pid: Process.id, arch: Process.arch});
"""


def selected_pid(device, package):
    # Frida Android process names can be display labels, not package IDs. Bind
    # the running application by its immutable identifier instead of guessing.
    matches = [
        app.pid
        for app in device.enumerate_applications()
        if app.identifier == package and app.pid != 0
    ]
    if len(matches) != 1:
        raise ValueError("Selected application must have exactly one running process")
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--script", type=Path)
    options = parser.parse_args()
    messages = []
    ready = threading.Event()
    failed = threading.Event()

    def on_message(message, data):
        if message.get("type") == "error":
            failed.set()
        if len(messages) < 25:
            encoded = json.dumps(message)
            messages.append(
                message
                if len(encoded) <= 2048
                else {"type": message.get("type"), "truncated": True}
            )
        if data is not None and len(messages) < 25:
            messages.append({"type": "binary", "bytes": len(data), "retained": False})
        ready.set()

    device = frida.get_device(options.serial, timeout=5)
    # No implicit spawning, takeover or reconnect to a different Android transport.
    pid = selected_pid(device, options.package)
    session = device.attach(pid)
    try:
        source = options.script.read_text() if options.script else DEFAULT_AGENT
        script = session.create_script(source)
        script.on("message", on_message)
        script.load()
        rpc = None if options.script else script.exports_sync.probe()
        ready.wait(3)
        if failed.is_set():
            print(json.dumps({"status": "error", "messages": messages}))
            return 1
        print(json.dumps({"status": "ok", "pid": pid, "rpc": rpc, "messages": messages}))
        return 0
    finally:
        session.detach()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({"status": "error", "errorType": type(error).__name__}))
        sys.exit(1)
