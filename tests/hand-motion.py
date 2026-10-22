#!/usr/bin/env python3
"""Offline hand geometry/association/output tests; no camera, models, or desktop actions."""

import importlib.util
import io
import json
import math
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1] / "packages/room-camera"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SOURCE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load("firmware")
load("runtime")
data = load("hand_data")
tracking = load("hand_tracking")
hands_module = load("hands")


def detection(dx=0, dy=0, pose="open"):
    points = [
        (400, 700),
        (360, 650),
        (320, 600),
        (280, 550),
        (240, 500),
        (360, 500),
        (360, 400),
        (360, 300),
        (360, 200),
        (420, 490),
        (420, 380),
        (420, 270),
        (420, 160),
        (480, 500),
        (480, 400),
        (480, 300),
        (480, 200),
        (540, 530),
        (540, 440),
        (540, 350),
        (540, 260),
    ]
    if pose == "fist":
        points[4] = (300, 630)
        for tip in (8, 12, 16, 20):
            points[tip] = (points[tip][0], 560)
    if pose == "pinch":
        points[4] = (points[8][0] + 4, points[8][1])
    return {
        "landmarks_image_xyz": [[float(x + dx), float(y + dy), 0.0] for x, y in points],
        "hand_presence_score": 0.98,
        "palm_score": 0.95,
        "handedness_right_score_raw": 0.7,
        "bbox_xyxy_px": [200 + dx, 100 + dy, 580 + dx, 750 + dy],
    }


class FakeFrame:
    shape = (1080, 1920, 3)

    def __getitem__(self, key):
        frame = FakeFrame()
        rows, columns = key
        frame.shape = (rows.stop - rows.start, columns.stop - columns.start, 3)
        return frame


class PipelineTests(unittest.TestCase):
    def pipeline(self):
        row = tracking.palm_from_hand(detection())
        locate = Mock(side_effect=lambda frame: [row] if frame.shape == FakeFrame.shape else [])
        pose = Mock(return_value=detection())
        return tracking.TrackingPipeline(locate, pose), locate, pose

    def test_fist_survives_palm_detector_loss_via_fresh_pose(self):
        pipeline, locate, pose = self.pipeline()
        self.assertEqual(len(pipeline.infer(FakeFrame(), 0)), 1)
        locate.return_value, locate.side_effect = [], None
        pose.return_value = detection(pose="fist")
        second = pipeline.infer(FakeFrame(), 0.05)
        self.assertEqual(len(second), 1)
        self.assertTrue(pose.call_args.args[2])
        self.assertEqual(locate.call_count, 2)  # full frame and one tile only at acquisition

    def test_pose_failure_does_not_emit_stale_hand(self):
        pipeline, locate, pose = self.pipeline()
        pipeline.infer(FakeFrame(), 0)
        pose.return_value = None
        locate.return_value, locate.side_effect = [], None
        self.assertEqual(pipeline.infer(FakeFrame(), 0.05), [])
        self.assertEqual(pipeline.previous, [])

    def test_long_gap_discards_crop(self):
        pipeline, locate, pose = self.pipeline()
        pipeline.infer(FakeFrame(), 0)
        locate.return_value, locate.side_effect = [], None
        pose.reset_mock()
        self.assertEqual(pipeline.infer(FakeFrame(), 0.5), [])
        pose.assert_not_called()

    def test_feedback_drift_is_rejected(self):
        pipeline, locate, pose = self.pipeline()
        pipeline.infer(FakeFrame(), 0)
        locate.return_value, locate.side_effect = [], None
        pose.return_value = detection(dx=800)
        self.assertEqual(pipeline.infer(FakeFrame(), 0.05), [])

    def test_tile_translates_box_and_all_seven_landmarks(self):
        row = tracking.palm_from_hand(detection())
        locate = Mock(side_effect=[[], [], [], [row]])
        pose = Mock(return_value=detection(dx=576))
        pipeline = tracking.TrackingPipeline(locate, pose)
        self.assertEqual(pipeline.infer(FakeFrame(), 0), [])
        self.assertEqual(len(pipeline.infer(FakeFrame(), 0.05)), 1)
        received = pose.call_args.args[1]
        for index in range(0, 18, 2):
            self.assertEqual(received[index], row[index] + 576)
            self.assertEqual(received[index + 1], row[index + 1])
        self.assertEqual(received[18], row[18])

    def test_duplicate_full_frame_and_tile_detections_merge(self):
        row = tracking.palm_from_hand(detection())
        pipeline = tracking.TrackingPipeline(
            Mock(return_value=[row]), Mock(return_value=detection())
        )
        self.assertEqual(len(pipeline.infer(FakeFrame(), 0)), 1)

    def test_two_tracking_crops_cannot_emit_the_same_remaining_hand(self):
        first, second = detection(), detection(dx=240)
        pipeline = tracking.TrackingPipeline(
            Mock(return_value=[]), Mock(return_value=detection(dx=120))
        )
        pipeline.previous = [first, second]
        pipeline.last_time, pipeline.last_scan = 0, 0
        self.assertEqual(len(pipeline.infer(FakeFrame(), 0.05)), 1)

    def test_synthetic_palm_has_correct_landmark_order(self):
        hand = detection()
        row = tracking.palm_from_hand(hand)
        for offset, index in enumerate((0, 5, 9, 13, 17, 1, 2)):
            self.assertEqual(
                row[4 + offset * 2 : 6 + offset * 2], hand["landmarks_image_xyz"][index][:2]
            )

    def test_expired_inference_crop_and_clock_reversal_reacquire(self):
        for timestamp in (0.5, -0.1):
            pipeline, locate, pose = self.pipeline()
            pipeline.infer(FakeFrame(), 0)
            locate.return_value, locate.side_effect = [], None
            pose.reset_mock()
            pipeline.infer(FakeFrame(), timestamp)
            pose.assert_not_called()


class WorkerTests(unittest.TestCase):
    def test_preview_snapshot_does_not_wait_for_inference(self):
        entered, release = threading.Event(), threading.Event()
        camera = Mock()
        camera.sample.return_value = (FakeFrame(), 1.0)
        detector = Mock()

        def infer(*args):
            entered.set()
            release.wait(2)
            return []

        detector.infer.side_effect = infer
        worker = hands_module.HandInference(detector, camera)
        try:
            self.assertTrue(entered.wait(1))
            self.assertIsNone(worker.snapshot())
        finally:
            release.set()
            worker.close()
        self.assertEqual(worker.snapshot()["hands"], [])
        self.assertEqual(detector.infer.call_count, 1)


class GeometryTests(unittest.TestCase):
    def test_open_and_closed_fingers(self):
        for pose, count, gesture in [("open", 5, "open_palm"), ("fist", 0, "fist")]:
            features = data.geometry(detection(pose=pose)["landmarks_image_xyz"], 1920, 1080)
            self.assertEqual(features["finger_count"], count)
            self.assertEqual(data.gesture(features, False), gesture)

    def test_scale_translation_and_rotation_invariance(self):
        points = detection()["landmarks_image_xyz"]
        first = data.geometry(points, 1920, 1080)
        for altered in (
            [[x * 2 + 100, y * 2 - 30, z] for x, y, z in points],
            [[-y + 1000, x, z] for x, y, z in points],
        ):
            second = data.geometry(altered, 1920, 1080)
            self.assertAlmostEqual(first["pinch_ratio"], second["pinch_ratio"])
            self.assertEqual(first["fingers_extended"], second["fingers_extended"])

    def test_coordinate_semantics_and_unbounded_predictions(self):
        features = data.geometry(detection(dx=-500)["landmarks_image_xyz"], 1920, 1080)
        self.assertLess(features["landmarks_norm"][0][0], 0)
        self.assertAlmostEqual(features["landmarks_norm"][0][1], 700 / 1080)

    def test_nonfinite_and_degenerate_points_rejected(self):
        for points in ([[0, 0, 0]] * 21, [[math.nan, 1, 0]] * 21, [[1, 2, 3]] * 20):
            with self.assertRaises(ValueError):
                data.geometry(points, 1920, 1080)


class TrackingTests(unittest.TestCase):
    def test_first_sample_has_no_motion_and_stable_gesture_is_debounced(self):
        tracker = data.HandTelemetry()
        first = tracker.update([detection()], 0)[0]
        self.assertFalse(first["motion_valid"])
        self.assertEqual(first["gesture_raw"], "open_palm")
        self.assertEqual(first["gesture"], "unknown")
        tracker.update([detection()], 0.1)
        stable = tracker.update([detection()], 0.21)[0]
        self.assertEqual(stable["gesture"], "open_palm")
        self.assertTrue(stable["gesture_changed"])
        self.assertFalse(tracker.update([detection()], 0.3)[0]["gesture_changed"])

    def test_motion_and_identity_survive_detection_order_change(self):
        tracker = data.HandTelemetry()
        first = tracker.update([detection(), detection(dx=800)], 1)
        second = tracker.update([detection(dx=780), detection(dx=20)], 1.1)
        self.assertEqual(
            [h["track_id"] for h in second], [first[1]["track_id"], first[0]["track_id"]]
        )
        self.assertAlmostEqual(second[1]["velocity_norm_per_s"][0], (20 / 1920) / 0.1)
        self.assertTrue(second[1]["motion_valid"])

    def test_two_hands_do_not_steal_ids_when_both_move_right(self):
        tracker = data.HandTelemetry()
        first = tracker.update([detection(), detection(dx=384)], 0)
        second = tracker.update([detection(dx=230), detection(dx=672)], 0.2)
        self.assertEqual([h["track_id"] for h in second], [h["track_id"] for h in first])
        self.assertTrue(all(hand["velocity_norm_per_s"][0] > 0 for hand in second))

    def test_slow_inference_can_confirm_gestures_without_claiming_valid_motion(self):
        tracker = data.HandTelemetry()
        tracker.update([detection()], 0)
        for timestamp in (0.3, 0.6, 0.9, 1.2):
            hand = tracker.update([detection()], timestamp)[0]
            self.assertEqual(hand["gesture"], "open_palm")
            self.assertFalse(hand["motion_valid"])

    def test_missing_hand_does_not_create_false_swipe_on_reacquisition(self):
        tracker = data.HandTelemetry()
        first = tracker.update([detection()], 0)[0]
        self.assertEqual(tracker.update([], 0.1), [])
        returned = tracker.update([detection(dx=100)], 0.2)[0]
        self.assertEqual(returned["track_id"], first["track_id"])
        self.assertFalse(returned["motion_valid"])
        self.assertEqual(returned["velocity_norm_per_s"], [0.0, 0.0])
        self.assertEqual(returned["gesture"], "unknown")

    def test_expired_track_gets_new_id(self):
        tracker = data.HandTelemetry()
        first = tracker.update([detection()], 0)[0]
        second = tracker.update([detection()], 0.8)[0]
        self.assertNotEqual(first["track_id"], second["track_id"])
        self.assertFalse(second["motion_valid"])

    def test_clock_reversal_or_long_gap_resets_motion(self):
        tracker = data.HandTelemetry()
        tracker.update([detection()], 2)
        for timestamp in (1, 1.4):
            self.assertFalse(tracker.update([detection()], timestamp)[0]["motion_valid"])

    def test_pinch_has_hysteresis(self):
        tracker = data.HandTelemetry()
        self.assertTrue(tracker.update([detection(pose="pinch")], 0)[0]["pinch_active"])
        almost = detection(pose="pinch")
        points = almost["landmarks_image_xyz"]
        span = data.distance(points[5], points[17])
        points[4][0] = points[8][0] + 0.32 * span
        self.assertTrue(tracker.update([almost], 0.1)[0]["pinch_active"])
        tracker.update([], 0.15)
        self.assertFalse(tracker.update([almost], 0.2)[0]["pinch_active"])


class OutputTests(unittest.TestCase):
    def test_json_line_is_versioned_complete_and_has_no_terminal_escapes(self):
        hand = data.HandTelemetry().update([detection()], 123.25)
        event = data.make_event(7, 123.25, hand, 12.5)
        output = io.StringIO()
        hands_module.emit(event, True, output)
        raw = output.getvalue()
        parsed = json.loads(raw)
        self.assertEqual(len(raw.splitlines()), 1)
        self.assertNotIn("\x1b", raw)
        self.assertEqual(parsed["schema_version"], 1)
        self.assertEqual(parsed["capture_monotonic_ns"], 123250000000)
        self.assertEqual(len(parsed["hands"][0]["landmarks_norm"]), 21)
        self.assertFalse(parsed["image"]["mirrored"])

    def test_absence_event_and_human_readout(self):
        event = data.make_event(0, 1, [], 10)
        output = io.StringIO()
        hands_module.emit(event, True, output)
        self.assertEqual(json.loads(output.getvalue())["hands"], [])
        self.assertIn("No hand detected", data.terminal_text(event))
        self.assertIn("no mute, volume, or keyboard actions", data.terminal_text(event))

    def test_slow_result_expires_before_terminal_and_json_output(self):
        hand = data.HandTelemetry().update([detection()], 1)
        original = data.make_event(0, 1, hand, 1000)
        expired = hands_module.fresh_event(original, 2)
        self.assertEqual(expired["hands"], [])
        self.assertTrue(expired["tracking_stale"])
        self.assertIn("Tracking expired", data.terminal_text(expired))
        output = io.StringIO()
        hands_module.emit(expired, True, output)
        self.assertEqual(json.loads(output.getvalue())["hands"], [])
        self.assertEqual(len(original["hands"]), 1)

    def test_stalled_result_changes_freshness_without_a_new_inference(self):
        event = data.make_event(0, 1, [detection()], 20)
        fresh = hands_module.fresh_event(event, 1.1)
        expired = hands_module.fresh_event(event, 1.36)
        self.assertFalse(fresh["tracking_stale"])
        self.assertTrue(expired["tracking_stale"])
        self.assertEqual(fresh["sequence"], expired["sequence"])
        self.assertEqual(expired["hands"], [])

    def test_strict_json_rejects_nan(self):
        with self.assertRaises(ValueError):
            hands_module.emit(data.make_event(0, 1, [], math.nan), True, io.StringIO())


if __name__ == "__main__":
    unittest.main()
