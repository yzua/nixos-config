#!/usr/bin/env python3
"""Stateful external-command adapter; never contacts Voxtype, Pi, or D-Bus."""

import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

root = Path(os.environ["VOICE_FAKE_DIR"])
name = Path(sys.argv[0]).name
args = sys.argv[1:]
# Match the pinned Config::runtime_dir, independently of wrapper implementation.
voxtype_runtime = Path(os.environ["XDG_RUNTIME_DIR"]) / "voxtype"
voxtype_runtime.mkdir(mode=0o700, exist_ok=True)
cancel_trigger = voxtype_runtime / "cancel"


def emit(kind, **data):
    with (root / "events.jsonl").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(json.dumps({"kind": kind, **data}) + "\n")


def gate(name):
    (root / (name + "-ready")).touch()
    deadline = time.monotonic() + 10
    while (root / ("hold-" + name)).exists():
        if time.monotonic() > deadline:
            raise RuntimeError("test did not release " + name)
        time.sleep(0.01)


if args == ["--complete-cancel"]:
    gate("cancel")
    with (root / "daemon.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        (root / "daemon.json").write_text('{"state":"idle","target":null}')
        cancel_trigger.unlink(missing_ok=True)
        emit("cancelled")
    sys.exit(0)

if name == "notify-send":
    emit("notification", args=args)
    sys.exit(0)

if name == "pi":
    session = args[args.index("--session") + 1]
    transcript = Path(args[-1].removeprefix("@"))
    emit("submitted", session=session, args=args)
    gate("pi")  # Deliberately read the attachment late: reset must preserve it.
    emit("request", session=session, text=transcript.read_text())
    if (root / "fail-pi").exists():
        sys.exit(1)
    print("Done")
    (root / "pi-completion-ready").touch()
    sys.exit(0)

if name != "voxtype":
    raise RuntimeError("unexpected fake command " + name)

with (root / "daemon.lock").open("a") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    state_path = root / "daemon.json"
    state = json.loads(state_path.read_text())
    if args == ["status"]:
        print(state["state"])
        sys.exit(0)
    assert args[0] == "record", args
    operation = args[1]
    if (root / ("fail-" + operation)).exists():
        sys.exit(1)
    if operation == "start" or (operation == "toggle" and state["state"] == "idle"):
        assert state["state"] == "idle", state
        target = next((a[7:] for a in args if a.startswith("--file=")), None)
        state = {"state": "recording", "target": target}
        emit("recording", target=target)
        # The pinned daemon clears leftover cancel triggers at every capture
        # start (#606); do not invent a stale-trigger cancellation failure.
        if cancel_trigger.exists():
            cancel_trigger.unlink()
            emit("cancel-trigger-cleared-at-start")
    elif operation == "cancel":
        if (root / "race-cancel-completion").exists():
            # Complete the daemon's decode between the wrapper's status read
            # and the CLI trigger write. The separate stop waiter can still live.
            if state["target"]:
                target = Path(state["target"])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text((root / "transcript").read_text())
            state_path.write_text('{"state":"idle","target":null}')
            cancel_trigger.touch()
            # The idle sweep may be starved. Capture start, not idle polling,
            # is the pinned daemon's reliable cleanup of this leftover trigger.
            emit("cancel-after-completion")
            sys.exit(0)
        cancel_trigger.touch()
        if (root / "hold-cancel").exists():
            # Like the real CLI, return after issuing the command, before the
            # daemon changes state. The test controls acknowledgement separately.
            subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--complete-cancel"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            sys.exit(0)
        state = {"state": "idle", "target": None}
        cancel_trigger.unlink()
        emit("cancelled")
    elif operation == "toggle":
        assert state["target"] is None, "ordinary toggle must not stop action output"
        state = {"state": "idle", "target": None}
        emit("paste", text="Ordinary dictation")
    elif operation == "stop":
        assert state["target"] is not None, "action must not stop ordinary dictation"
        target = Path(state["target"])
        state["state"] = "transcribing"
    else:
        raise RuntimeError(args)
    state_path.write_text(json.dumps(state))

if operation == "stop":
    gate("transcription")
    text = (root / "transcript").read_text()
    with (root / "daemon.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(state_path.read_text())
        if state["state"] != "transcribing" or state["target"] != str(target):
            sys.exit(1)  # The daemon cancelled/completed this output while we waited.
        target.write_text(text)
        state_path.write_text(json.dumps({"state": "idle", "target": None}))
    if (root / "fail-transcription").exists():
        sys.exit(1)
    print(text)
