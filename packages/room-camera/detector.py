"""CPU-only YOLOX person detection and debounced arrival notifications.

Pre/postprocessing follows OpenCV Zoo's Apache-2.0 YOLOX example:
https://github.com/opencv/opencv_zoo/tree/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/object_detection_yolox
"""


class ArrivalGate:
    """Confirm sustained presence, rearm after absence, and rate-limit alerts."""

    def __init__(self, confirmation=1.0, absence=5.0, cooldown=60.0):
        self.confirmation = confirmation
        self.absence = absence
        self.cooldown = cooldown
        self.first_seen = None
        self.last_seen = None
        self.last_alert = float("-inf")
        self.present = False

    def update(self, detected, now):
        if not detected:
            self.first_seen = None
            if self.last_seen is not None and now - self.last_seen >= self.absence:
                self.present = False
            return False
        if self.last_seen is not None and now - self.last_seen >= self.absence:
            self.present = False
            self.first_seen = None
        self.last_seen = now
        if self.first_seen is None:
            self.first_seen = now
        if self.present or now - self.first_seen < self.confirmation:
            return False
        if now - self.last_alert < self.cooldown:
            return False
        self.present = True
        self.last_alert = now
        return True


class PersonDetector:
    def __init__(self, model, confidence=0.5):
        import cv2
        import numpy as np

        self.cv = cv2
        self.np = np
        self.confidence = confidence
        self.net = cv2.dnn.readNet(str(model))
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        grids, strides = [], []
        for stride in (8, 16, 32):
            x, y = np.meshgrid(np.arange(640 // stride), np.arange(640 // stride))
            grid = np.stack((x, y), axis=2).reshape(-1, 2)
            grids.append(grid)
            strides.append(np.full((len(grid), 1), stride))
        self.grids = np.concatenate(grids)
        self.strides = np.concatenate(strides)

    def infer(self, frame):
        cv, np = self.cv, self.np
        height, width = frame.shape[:2]
        ratio = min(640 / width, 640 / height)
        resized = cv.resize(frame, (int(width * ratio), int(height * ratio)))
        rgb = cv.cvtColor(resized, cv.COLOR_BGR2RGB)
        padded = np.full((640, 640, 3), 114, dtype=np.float32)
        padded[: rgb.shape[0], : rgb.shape[1]] = rgb
        self.net.setInput(padded.transpose(2, 0, 1)[None])
        predictions = self.net.forward()[0]
        # Class 0 is COCO person; require it to be the most likely class too.
        scores = predictions[:, 4] * predictions[:, 5]
        selected = (scores >= self.confidence) & (predictions[:, 5:].argmax(axis=1) == 0)
        dets = predictions[selected]
        scores = scores[selected]
        if not len(dets):
            return []
        centers = (dets[:, :2] + self.grids[selected]) * self.strides[selected]
        sizes = np.exp(dets[:, 2:4]) * self.strides[selected]
        boxes = np.concatenate((centers - sizes / 2, sizes), axis=1) / ratio
        keep = cv.dnn.NMSBoxes(boxes.tolist(), scores.tolist(), self.confidence, 0.5)
        result = []
        for index in np.asarray(keep).reshape(-1):
            x, y, w, h = boxes[index]
            left, top = max(0, int(x)), max(0, int(y))
            right, bottom = min(width, int(x + w)), min(height, int(y + h))
            if right > left and bottom > top:
                result.append((left, top, right, bottom, float(scores[index])))
        return result
