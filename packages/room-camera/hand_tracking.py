"""Temporal hand crop tracking and tiled small-hand acquisition, independent of models."""

import math

PALM_IDS = (0, 5, 9, 13, 17, 1, 2)


def palm_from_hand(hand):
    """Reconstruct the seven palm points expected by OpenCV Zoo's pose wrapper."""
    points = [hand["landmarks_image_xyz"][index][:2] for index in PALM_IDS]
    xs, ys = zip(*points, strict=True)
    width, height = max(xs) - min(xs), max(ys) - min(ys)
    if min(width, height) < 3 or math.dist(points[0], points[2]) < 5:
        return None
    return [min(xs), min(ys), max(xs), max(ys), *(v for p in points for v in p), 1.0]


def search_regions(width, height):
    """Six overlapping 768px crops give a small hand ~2.5× detector sampling."""
    crop_w, crop_h = min(width, 768), min(height, 768)
    xs = sorted({0, (width - crop_w) // 2, width - crop_w})
    ys = sorted({0, height - crop_h})
    return [(x, y, x + crop_w, y + crop_h) for y in ys for x in xs]


def translate_palm(palm, x, y):
    shifted = list(palm)
    for index in range(0, 18, 2):
        shifted[index] += x
        shifted[index + 1] += y
    return shifted


def plausible_update(previous, current, frame_shape):
    """Conservative feedback guards; confidence alone does not prove a crop is valid."""
    height, width = frame_shape[:2]
    points = current["landmarks_image_xyz"]
    if len(points) != 21 or not all(math.isfinite(v) for point in points for v in point):
        return False
    palm = palm_from_hand(current)
    if palm is None:
        return False
    if min(palm[2], width) - max(palm[0], 0) < 5 or min(palm[3], height) - max(palm[1], 0) < 5:
        return False
    old = previous["landmarks_image_xyz"]
    old_span = math.dist(old[5][:2], old[17][:2])
    span = math.dist(points[5][:2], points[17][:2])
    if old_span < 5 or not 0.5 < span / old_span < 2:
        return False
    old_center = [sum(old[i][axis] for i in PALM_IDS[:5]) / 5 for axis in (0, 1)]
    center = [sum(points[i][axis] for i in PALM_IDS[:5]) / 5 for axis in (0, 1)]
    return math.dist(old_center, center) < max(40, old_span * 1.5)


def same_hand(first, second):
    a, b = first["landmarks_image_xyz"], second["landmarks_image_xyz"]
    # Compare palm centers rather than full boxes: a closed fist changes its box.
    centers = [
        [sum(points[i][axis] for i in PALM_IDS[:5]) / 5 for axis in (0, 1)] for points in (a, b)
    ]
    span = max(math.dist(points[5][:2], points[17][:2]) for points in (a, b))
    return math.dist(*centers) < max(20, span * 1.2)


class TrackingPipeline:
    """Pose-track previous hands; reacquire via full frame and one rotating crop.

    locate(frame) returns palm rows; pose(frame, palm, tracking) returns a fresh
    hand detection or None. No old landmarks are returned as current detections.
    """

    def __init__(self, locate, pose):
        self.locate, self.pose = locate, pose
        self.previous = []
        self.last_time = None
        self.last_scan = float("-inf")
        self.tile = 0

    def infer(self, frame, timestamp):
        if self.last_time is None or not 0 < timestamp - self.last_time <= 0.35:
            self.previous = []
        self.last_time = timestamp
        hands = []
        for previous in self.previous:
            palm = palm_from_hand(previous)
            if palm is None:
                continue
            current = self.pose(frame, palm, True)
            if (
                current is not None
                and plausible_update(previous, current, frame.shape)
                and not any(same_hand(current, hand) for hand in hands)
            ):
                hands.append(current)
        if not hands or timestamp - self.last_scan >= 0.8:
            self.last_scan = timestamp
            height, width = frame.shape[:2]
            palms = list(self.locate(frame))
            # Spread small-hand search over frames rather than paying for all
            # tiles every frame. Original pixel coordinates are restored first.
            if len(hands) < 2:
                regions = search_regions(width, height)
                x1, y1, x2, y2 = regions[self.tile % len(regions)]
                self.tile += 1
                palms += [translate_palm(p, x1, y1) for p in self.locate(frame[y1:y2, x1:x2])]
            for palm in sorted(palms, key=lambda p: -p[18])[:6]:
                if len(hands) >= 2:
                    break
                candidate = self.pose(frame, palm, False)
                if candidate is not None and not any(same_hand(candidate, hand) for hand in hands):
                    hands.append(candidate)
        self.previous = hands[:2]
        return self.previous
