"""Room Cam: local live viewing, person alerts, and hand telemetry; no recording."""

import argparse
import fcntl
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from detector import ArrivalGate, PersonDetector
from firmware import DEVICE, upload
from runtime import LiveCamera, Preview, player_command


def notify(message, *, error=False):
    try:
        subprocess.run(
            [
                os.environ["CAMERA_NOTIFY"],
                "--app-name=Room Cam",
                "--icon=camera-video",
                "--urgency=" + ("critical" if error else "normal"),
                "--expire-time=10000",
                "Room Cam",
                message,
            ],
            check=False,
            timeout=3,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def ensure_camera():
    if Path(DEVICE).exists():
        return
    upload(os.environ["CAMERA_FIRMWARE"], os.environ["CAMERA_LIBUSB"])
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if Path(DEVICE).exists() and os.access(DEVICE, os.R_OK | os.W_OK):
            return
        time.sleep(0.1)
    raise RuntimeError("Firmware uploaded, but no accessible webcam appeared. Unplug and retry.")


def monitor(args):
    import cv2

    cv2.setNumThreads(2)
    detector = PersonDetector(os.environ["CAMERA_MODEL"], args.confidence)
    gate = ArrivalGate(cooldown=args.cooldown)
    camera = LiveCamera(cv2)
    stopped = threading.Event()
    state_lock = threading.Lock()
    state = {"boxes": [], "updated": time.monotonic(), "error": None, "samples": 0}

    def detect():
        try:
            while not stopped.is_set():
                started = time.monotonic()
                frame = camera.latest()
                if frame is None:
                    stopped.wait(0.05)
                    continue
                boxes = detector.infer(frame)
                now = time.monotonic()
                with state_lock:
                    state.update(boxes=boxes, updated=now, samples=state["samples"] + 1)
                if gate.update(bool(boxes), now) and not args.test_frames:
                    notify("Person detected. The local monitor is running; no video is saved.")
                stopped.wait(max(0, 0.5 - (time.monotonic() - started)))
        except Exception as error:
            with state_lock:
                state["error"] = error

    worker = threading.Thread(target=detect, daemon=True)
    preview = None
    shown = 0
    try:
        worker.start()
        if not args.test_frames:
            preview = Preview("Room Person Monitor — local only (Q: quit, F: fullscreen)")
        while True:
            started = time.monotonic()
            frame = camera.latest()
            with state_lock:
                snapshot = state.copy()
            if snapshot["error"]:
                raise snapshot["error"]
            if frame is None:
                stopped.wait(0.02)
                continue
            age = time.monotonic() - snapshot["updated"]
            if age > 15:
                raise RuntimeError("Person detection has stopped responding.")
            boxes = snapshot["boxes"] if age < 2 else []
            for left, top, right, bottom, score in boxes:
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 3)
                cv2.putText(
                    frame,
                    f"Person {score:.0%}",
                    (left, max(25, top - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2,
                )
            label = "Local person detection | no recording | Q: quit | F: fullscreen"
            if not snapshot["samples"]:
                label = "Starting person detection... | no recording"
            cv2.putText(frame, label, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            if preview and not preview.show(frame):
                break
            shown += 1
            if args.test_frames and shown >= args.test_frames and snapshot["samples"]:
                print(
                    f"Live check: {shown} frames, {snapshot['samples']} inferences, "
                    f"{len(boxes)} person(s) in latest result; no frames saved."
                )
                break
            stopped.wait(max(0, 1 / 15 - (time.monotonic() - started)))
    finally:
        stopped.set()
        if preview:
            preview.close()
        worker.join(timeout=3)
        camera.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--monitor", action="store_true", help="Person boxes and desktop alerts")
    modes.add_argument(
        "--hands", action="store_true", help="Hand landmarks and terminal telemetry; no actions"
    )
    parser.add_argument(
        "--json", action="store_true", help="With --hands: versioned JSON Lines on stdout"
    )
    parser.add_argument(
        "--no-preview", action="store_true", help="With --hands: terminal/data only"
    )
    parser.add_argument("--confidence", type=float, default=0.5, help="Person detection confidence")
    parser.add_argument("--cooldown", type=float, default=60)
    parser.add_argument(
        "--test-frames", type=int, default=0, help="Finite headless live check; no alerts"
    )
    parser.add_argument(
        "--check-model", action="store_true", help="Check selected models on synthetic input"
    )
    args = parser.parse_args()
    if not 0 < args.confidence < 1 or args.cooldown < 0 or args.test_frames < 0:
        parser.error("Use confidence between 0 and 1, and nonnegative cooldown/test frames.")
    if (args.json or args.no_preview) and not args.hands:
        parser.error("--json and --no-preview require --hands.")
    if args.check_model:
        import cv2
        import numpy as np

        cv2.setNumThreads(2)
        if args.hands:
            from hands import HandDetector

            HandDetector().check()
            print("Pinned palm/hand models loaded; synthetic inference passed.")
        else:
            detector = PersonDetector(os.environ["CAMERA_MODEL"], args.confidence)
            assert detector.infer(np.zeros((1080, 1920, 3), dtype=np.uint8)) == []
            print("Pinned YOLOX model loaded; synthetic-frame inference passed.")
        return
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime:
        raise RuntimeError("Open Room Cam from your logged-in graphical desktop session.")
    with open(Path(runtime) / "room-camera.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Room Cam is already open. Close its other view first.") from None
        ensure_camera()
        if args.hands:
            from hands import run

            run(args)
        elif args.monitor or args.test_frames:
            monitor(args)
        else:
            result = subprocess.run(player_command(), check=False)
            if result.returncode:
                raise RuntimeError("Cannot display camera. Close other camera apps and retry.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    except Exception as error:
        print(f"Room Cam: {error}", file=sys.stderr)
        notify(str(error), error=True)
        sys.exit(1)
