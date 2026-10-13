#!/usr/bin/env python3
"""Bind REA ADB transport to the verified owned rooted lab, including MCP calls."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from android import Android, LabError


def owned_run(argv, *, env=None, capture_output=False, text=False, check=False, timeout=600):
    """Reap the directly owned ADB client before releasing any lifecycle lock."""

    def cancelled(signum, _frame):
        raise SystemExit(128 + signum)

    handlers = {sig: signal.signal(sig, cancelled) for sig in (signal.SIGTERM, signal.SIGINT)}
    process = None
    try:
        process = subprocess.Popen(
            argv,
            env=env,
            text=text,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
        )
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    except BaseException:
        # Repeated cancellation must not interrupt reaping and release the lock early.
        for sig in handlers:
            signal.signal(sig, signal.SIG_IGN)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                # REA kills this owner after five seconds: escalate/reap sooner.
                process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=1)
        raise
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def run(config, state, args, backend=None, execute=owned_run):
    lab = Android(config, state, backend=backend)
    if args == ["version"]:
        return execute(
            [config["android"]["adb"], *args], env=lab.env, check=False, timeout=15
        ).returncode
    if args == ["devices", "-l"]:
        # Enumeration is read-only; do not expose unrelated attached devices.
        result = execute(
            [config["android"]["adb"], *args],
            env=lab.env,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        print("List of devices attached")
        for line in result.stdout.splitlines():
            if line.split()[:1] == [lab.serial]:
                print(line)
        return result.returncode
    if len(args) < 3 or args[:2] != ["-s", lab.serial]:
        raise LabError("REA ADB requires the setup-selected owned emulator serial")
    # Hold the same lifecycle lock across verification and the actual operation.
    # Do not implicitly start/root a guest or change CA/proxy/Frida state here.
    with lab.lock():
        lab.device_identity()
        code, uid = lab.adb(["shell", "id", "-u"])
        if code or uid.strip() != "0":
            raise LabError("REA ADB requires an already rooted owned lab; use pi-re lab start")
        return execute(
            [config["android"]["adb"], *args],
            env=lab.env,
            check=False,
            timeout=600,
        ).returncode


def main():
    try:
        config = json.loads(Path(os.environ["PI_RE_CONFIG"]).read_text())
        state = Path(os.environ["PI_RE_STATE_DIR"])
        if not state.is_absolute():
            raise LabError("REA ADB state must be absolute")
        return run(config, state, sys.argv[1:])
    except (LabError, ValueError, OSError, KeyError, subprocess.TimeoutExpired) as error:
        print(f"pi-re REA ADB: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
