"""Pure hand geometry and short-lived association; never performs desktop actions."""

import itertools
import math

FINGERS = ("thumb", "index", "middle", "ring", "little")
CONNECTIONS = tuple(
    edge
    for base in (1, 5, 9, 13, 17)
    for edge in ((0, base), (base, base + 1), (base + 1, base + 2), (base + 2, base + 3))
) + ((5, 9), (9, 13), (13, 17))


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def angle(a, joint, b):
    first = (a[0] - joint[0], a[1] - joint[1])
    second = (b[0] - joint[0], b[1] - joint[1])
    size = math.hypot(*first) * math.hypot(*second)
    if size < 1e-8:
        return 0.0
    cosine = (first[0] * second[0] + first[1] * second[1]) / size
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def geometry(points, width, height):
    """Input screen x/y and wrist-relative pixel-like z; output scale-free features."""
    if len(points) != 21 or any(
        len(p) != 3 or not all(math.isfinite(v) for v in p) for p in points
    ):
        raise ValueError("Expected 21 finite xyz landmarks.")
    span = distance(points[5], points[17])
    if span < 5:
        raise ValueError("Palm is too small or degenerate for gesture measurements.")
    extended = {}
    extended["thumb"] = (
        angle(points[1], points[2], points[4]) > 145
        and distance(points[4], points[17]) > distance(points[3], points[17]) * 1.05
    )
    for name, base in zip(FINGERS[1:], (5, 9, 13, 17), strict=True):
        extended[name] = (
            angle(points[base], points[base + 1], points[base + 3]) > 150
            and distance(points[base + 3], points[0]) > distance(points[base + 1], points[0]) * 1.1
        )
    center = [sum(points[i][axis] for i in (0, 5, 9, 13, 17)) / 5 for axis in (0, 1)]
    return {
        "center_norm": [center[0] / width, center[1] / height],
        "palm_width_px": span,
        "pinch_ratio": distance(points[4], points[8]) / span,
        "fingers_extended": extended,
        "finger_count": sum(extended.values()),
        "landmarks_norm": [[p[0] / width, p[1] / height, p[2] / width] for p in points],
    }


def gesture(features, pinching):
    if pinching:
        return "pinch"
    fingers = features["fingers_extended"]
    other = [fingers[name] for name in FINGERS[1:]]
    if all(fingers.values()):
        return "open_palm"
    if not any(fingers.values()):
        return "fist"
    if other == [True, False, False, False]:
        return "pointing"
    if other == [True, True, False, False]:
        return "victory"
    return "unknown"


class HandTelemetry:
    """Associate nearby detections, reset stale motion, and debounce gesture labels."""

    def __init__(self):
        self.tracks = {}
        self.next_id = 1

    def update(self, detections, timestamp, width=1920, height=1080):
        if not math.isfinite(timestamp):
            raise ValueError("Capture timestamp must be finite.")
        self.tracks = {
            key: value
            for key, value in self.tracks.items()
            if 0 <= timestamp - value["time"] <= 0.75
        }
        prepared = []
        for detection in detections:
            try:
                features = geometry(detection["landmarks_image_xyz"], width, height)
            except ValueError:
                continue
            prepared.append((detection, features))
            if len(prepared) == 2:
                break
        # At most two detections: preserve the maximum number of viable tracks
        # before minimizing distance, instead of allowing greedy ID stealing.
        best_score = (1, float("inf"))
        matches = {}
        for assignment in itertools.product([None, *self.tracks], repeat=len(prepared)):
            assigned = [key for key in assignment if key is not None]
            if len(assigned) != len(set(assigned)):
                continue
            distances = [
                distance(prepared[index][1]["center_norm"], self.tracks[key]["center"])
                for index, key in enumerate(assignment)
                if key is not None
            ]
            if any(separation > 0.2 for separation in distances):
                continue
            score = (-len(assigned), sum(distances))
            if score < best_score:
                best_score = score
                matches = {index: key for index, key in enumerate(assignment) if key is not None}
        hands = []
        for index, (detection, features) in enumerate(prepared):
            key = matches.get(index)
            if key is None:
                key = self.next_id
                self.next_id += 1
            previous = self.tracks.get(key)
            delta = timestamp - previous["time"] if previous else 0
            # A lost hand/reacquisition must never look like a swipe.
            gesture_continuous = (
                previous is not None and 0 < delta <= 0.75 and not previous.get("missing", False)
            )
            continuous = gesture_continuous and delta <= 0.25
            center = features["center_norm"]
            velocity = (
                [(center[i] - previous["center"][i]) / delta for i in (0, 1)]
                if continuous
                else [0.0, 0.0]
            )
            was_pinching = bool(previous and gesture_continuous and previous["pinching"])
            pinching = features["pinch_ratio"] < (0.4 if was_pinching else 0.25)
            raw = gesture(features, pinching)
            same_candidate = gesture_continuous and previous["candidate"] == raw
            since = previous["since"] if same_candidate else timestamp
            stable = previous["stable"] if gesture_continuous else "unknown"
            changed = False
            if timestamp - since >= 0.2 and raw != stable:
                stable, changed = raw, True
            self.tracks[key] = {
                "time": timestamp,
                "center": center,
                "pinching": pinching,
                "candidate": raw,
                "since": since,
                "stable": stable,
                "missing": False,
            }
            hands.append(
                {
                    **detection,
                    **features,
                    "track_id": key,
                    "velocity_norm_per_s": velocity,
                    "motion_valid": continuous,
                    "pinch_active": pinching,
                    "gesture_raw": raw,
                    "gesture": stable,
                    "gesture_changed": changed,
                }
            )
        present = {hand["track_id"] for hand in hands}
        for key, track in self.tracks.items():
            if key not in present:
                track["missing"] = True
        return hands


def make_event(sequence, timestamp, hands, inference_ms):
    return {
        "schema_version": 1,
        "type": "hand_frame",
        "sequence": sequence,
        "capture_monotonic_ns": round(timestamp * 1_000_000_000),
        "image": {"width": 1920, "height": 1080, "mirrored": False},
        "inference_ms": inference_ms,
        "hands": hands,
    }


def terminal_text(event):
    lines = [
        "ROOM HAND TRACKER | DATA ONLY — no mute, volume, or keyboard actions",
        f"Sample {event['sequence']} | inference {event['inference_ms']:.0f} ms | Ctrl+C or close preview to stop",
        "Coordinates: image x→right, y→down | pinch ratio: smaller = closer",
        "",
    ]
    if event.get("tracking_stale"):
        lines.append("Tracking expired — old gestures cleared; waiting for fresh inference.")
    elif not event["hands"]:
        lines.append("No hand detected. Hold an open hand in view with good lighting.")
    for hand in event["hands"]:
        x, y = hand["center_norm"]
        vx, vy = hand["velocity_norm_per_s"]
        fingers = (
            ", ".join(name for name, extended in hand["fingers_extended"].items() if extended)
            or "none"
        )
        lines.extend(
            [
                f"Hand #{hand['track_id']} | presence {hand['hand_presence_score']:.0%} | {hand.get('source', 'acquired')}",
                f"  Palm width: {hand['palm_width_px']:.0f}px"
                + (" — small: more light / move closer" if hand["palm_width_px"] < 35 else ""),
                f"  Gesture: {hand['gesture']} (raw: {hand['gesture_raw']})",
                f"  Fingers: {hand['finger_count']} [{fingers}]",
                f"  Position: x={x:.3f} y={y:.3f} | velocity: x={vx:+.3f} y={vy:+.3f} frame/s",
                f"  Pinch: ratio={hand['pinch_ratio']:.3f} active={hand['pinch_active']}",
                "",
            ]
        )
    return "\n".join(lines)
