"""Local hand landmarks, a terminal dashboard/JSON stream, and a preview; no actions."""

import importlib.util
import json
import os
import sys
import threading
import time

from hand_data import CONNECTIONS, HandTelemetry, make_event, terminal_text
from hand_tracking import TrackingPipeline
from runtime import LiveCamera, Preview


def load_upstream(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HandDetector:
    """Pinned OpenCV Zoo palm/pose wrappers, explicitly CPU-only, at most two hands."""

    def __init__(self):
        import cv2

        palm = load_upstream("room_cam_palmdet", os.environ["CAMERA_PALM_CODE"])
        pose = load_upstream("room_cam_handpose", os.environ["CAMERA_HAND_CODE"])
        self.palm = palm.MPPalmDet(
            os.environ["CAMERA_PALM_MODEL"],
            scoreThreshold=0.6,
            backendId=cv2.dnn.DNN_BACKEND_OPENCV,
            targetId=cv2.dnn.DNN_TARGET_CPU,
        )
        self.pose = pose.MPHandPose(
            os.environ["CAMERA_HAND_MODEL"],
            confThreshold=0.65,
            backendId=cv2.dnn.DNN_BACKEND_OPENCV,
            targetId=cv2.dnn.DNN_TARGET_CPU,
        )

        self.pipeline = TrackingPipeline(self.palm.infer, self.estimate)

    def estimate(self, frame, palm, tracking):
        import numpy as np

        if not np.isfinite(palm).all():
            return None
        x1, y1, x2, y2 = palm[:4]
        height, width = frame.shape[:2]
        if min(x2, width) - max(x1, 0) < 5 or min(y2, height) - max(y1, 0) < 5:
            return None
        result = self.pose.infer(frame, np.asarray(palm, dtype=np.float64))
        if result is None or not np.isfinite(result).all():
            return None
        # Slightly lower presence threshold for a previously acquired hand,
        # never for a new detection. A failed pose yields no hand, not old points.
        if float(result[131]) < (0.65 if tracking else 0.8):
            return None
        return {
            "palm_score": None if tracking else float(palm[18]),
            "hand_presence_score": float(result[131]),
            "handedness_right_score_raw": float(result[130]),
            "bbox_xyxy_px": result[:4].tolist(),
            "landmarks_image_xyz": result[4:67].reshape(21, 3).tolist(),
            "source": "tracked_pose" if tracking else "palm_acquisition",
        }

    def infer(self, frame, timestamp=None):
        return self.pipeline.infer(frame, time.monotonic() if timestamp is None else timestamp)

    def check(self):
        import numpy as np

        assert self.infer(np.zeros((1080, 1920, 3), dtype=np.uint8)) == []
        self.pose.model.setInput(np.zeros((1, 224, 224, 3), dtype=np.float32))
        output = self.pose.model.forward(self.pose.model.getUnconnectedOutLayersNames())
        assert [value.size for value in output] == [63, 1, 1, 63]
        assert all(np.isfinite(value).all() for value in output)


def draw(frame, event, cv):
    height, width = frame.shape[:2]
    cv.putText(
        frame,
        "Room Hand Tracker | DATA ONLY | no actions | Q: quit",
        (20, 35),
        cv.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2,
    )
    for hand in event["hands"]:
        points = hand["landmarks_image_xyz"]
        for start, end in CONNECTIONS:
            a, b = points[start], points[end]
            if all(-10000 < value < 10000 for value in (*a[:2], *b[:2])):
                cv.line(frame, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (0, 255, 0), 3)
        for point in points:
            if 0 <= point[0] < width and 0 <= point[1] < height:
                cv.circle(frame, (int(point[0]), int(point[1])), 5, (0, 128, 255), -1)
        x, y = hand["center_norm"]
        label = f"#{hand['track_id']} {hand['gesture']} | fingers {hand['finger_count']} | pinch {hand['pinch_ratio']:.2f}"
        cv.putText(
            frame,
            label,
            (max(0, min(width - 750, int(x * width))), max(70, min(height - 20, int(y * height)))),
            cv.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2,
        )
    return frame


def fresh_event(event, now):
    """Expire data equally for drawing, terminal, and downstream JSON consumers."""
    age = max(0, now - event["capture_monotonic_ns"] / 1e9)
    stale = age > 0.35
    return {
        **event,
        "hands": [] if stale else event["hands"],
        "tracking_stale": stale,
        "sample_age_ms": age * 1000,
    }


def emit(event, json_mode, stream):
    if json_mode:
        stream.write(json.dumps(event, allow_nan=False, separators=(",", ":")) + "\n")
    elif stream.isatty():
        stream.write("\x1b[H\x1b[J" + terminal_text(event) + "\n")
    else:
        stream.write(terminal_text(event) + "\n")
    stream.flush()


class HandInference:
    """Latest-result worker: the preview never waits for neural inference."""

    def __init__(self, detector, camera):
        self.detector, self.camera = detector, camera
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.event = None
        self.error = None
        self.completed = time.monotonic()
        self.thread = threading.Thread(target=self.work, daemon=True)
        self.thread.start()

    def work(self):
        telemetry = HandTelemetry()
        previous_capture = None
        sequence = 0
        try:
            while not self.stop.is_set():
                started = time.monotonic()
                frame, captured = self.camera.sample()
                if frame is None or captured == previous_capture:
                    self.stop.wait(0.005)
                    continue
                previous_capture = captured
                detections = self.detector.infer(frame, captured)
                inference_ms = (time.monotonic() - started) * 1000
                hands = telemetry.update(detections, captured)
                event = make_event(sequence, captured, hands, inference_ms)
                with self.lock:
                    self.event, self.completed = event, time.monotonic()
                sequence += 1
                self.stop.wait(max(0, 0.05 - (time.monotonic() - started)))
        except Exception as error:
            with self.lock:
                self.error = error

    def snapshot(self):
        with self.lock:
            if self.error:
                raise self.error
            if time.monotonic() - self.completed > 10:
                raise RuntimeError("Hand inference stopped responding.")
            return self.event

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)


def run(args):
    import cv2

    cv2.setNumThreads(2)
    detector = HandDetector()
    camera = LiveCamera(cv2)
    inference = HandInference(detector, camera)
    preview = None
    sequence = 0
    previous_key = None
    interactive = sys.stdout.isatty() and not args.json
    try:
        if interactive:
            sys.stdout.write("\x1b[?1049h\x1b[?25l")
            sys.stdout.flush()
        if not args.no_preview and not args.test_frames:
            preview = Preview("Room Hand Tracker — data only (Q: quit, F: fullscreen)", fps=30)
        while True:
            started = time.monotonic()
            frame, captured = camera.sample()
            event = inference.snapshot()
            if frame is None:
                time.sleep(0.005)
                continue
            display = fresh_event(event or make_event(0, captured, [], 0), time.monotonic())
            if event is not None:
                key = (event["sequence"], display["tracking_stale"])
                if key != previous_key:
                    message = {
                        **display,
                        "inference_sequence": event["sequence"],
                        "sequence": sequence,
                    }
                    emit(message, args.json, sys.stdout)
                    previous_key = key
                    sequence += 1
            if preview and not preview.show(draw(frame, display, cv2)):
                break
            if args.test_frames and sequence >= args.test_frames:
                break
            time.sleep(max(0, 1 / 30 - (time.monotonic() - started)))
    finally:
        if preview:
            preview.close()
        inference.close()
        camera.close()
        if interactive:
            sys.stdout.write("\x1b[?25h\x1b[?1049l")
            sys.stdout.flush()
