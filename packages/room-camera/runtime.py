"""Shared fresh-frame capture and bounded local preview transport for Room Cam."""

import os
import selectors
import subprocess
import threading
import time

from firmware import DEVICE


def player_command(monitor=False, title=None, fps=15):
    base = [os.environ["CAMERA_FFPLAY"], "-hide_banner", "-loglevel", "warning"]
    if monitor:
        return base + [
            "-f",
            "rawvideo",
            "-pixel_format",
            "bgr24",
            "-video_size",
            "1920x1080",
            "-framerate",
            str(fps),
            "-probesize",
            "32",
            "-analyzeduration",
            "0",
            "-i",
            "pipe:0",
            "-window_title",
            title or "Room Person Monitor — local only, no recording (Q: quit, F: fullscreen)",
            "-an",
        ]
    return base + [
        "-f",
        "v4l2",
        "-input_format",
        "yuyv422",
        "-framerate",
        "30",
        "-video_size",
        "1920x1080",
        "-i",
        DEVICE,
        "-window_title",
        "Room Cam — 1080p (Q: quit, F: fullscreen)",
        "-an",
    ]


class LiveCamera:
    """Continuously drain capture buffers so slower inference sees fresh frames."""

    def __init__(self, cv):
        self.frame = None
        self.updated = time.monotonic()
        self.error = None
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.capture = cv.VideoCapture(DEVICE, cv.CAP_V4L2)
        if not self.capture.isOpened():
            raise RuntimeError("Camera is unavailable; close OBS or another camera viewer first.")
        self.capture.set(cv.CAP_PROP_FOURCC, cv.VideoWriter_fourcc(*"YUYV"))
        self.capture.set(cv.CAP_PROP_FRAME_WIDTH, 1920)
        self.capture.set(cv.CAP_PROP_FRAME_HEIGHT, 1080)
        self.capture.set(cv.CAP_PROP_FPS, 30)
        self.capture.set(cv.CAP_PROP_BUFFERSIZE, 2)
        self.thread = threading.Thread(target=self.read, daemon=True)
        self.thread.start()

    def read(self):
        try:
            while not self.stop.is_set():
                ok, frame = self.capture.read()
                if not ok:
                    raise RuntimeError("Camera disconnected or stopped delivering frames.")
                if frame.shape[:2] != (1080, 1920):
                    raise RuntimeError("Camera did not accept the tested 1920×1080 capture mode.")
                with self.lock:
                    self.frame, self.updated = frame, time.monotonic()
        except Exception as error:
            self.error = error
        finally:
            self.capture.release()

    def sample(self):
        """Return the latest frame and its monotonic receive timestamp atomically."""
        if self.error:
            raise self.error
        with self.lock:
            if time.monotonic() - self.updated > 10:
                raise RuntimeError("No camera frames for 10 seconds; unplug and retry.")
            return (None if self.frame is None else self.frame.copy()), self.updated

    def latest(self):
        return self.sample()[0]

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)


class PreviewClosed(Exception):
    """The user closed the preview normally."""


def preview_closed(player):
    try:
        code = player.wait(timeout=1)
    except subprocess.TimeoutExpired:
        raise RuntimeError("The preview stopped accepting frames. Close it and retry.") from None
    if code:
        raise RuntimeError(f"The camera preview exited unsuccessfully (status {code}).")
    raise PreviewClosed


def deliver_frame(player, frame, timeout=3):
    """Bound pipe backpressure so a paused or dead player cannot freeze supervision."""
    os.set_blocking(player.stdin.fileno(), False)
    pending = memoryview(frame)
    deadline = time.monotonic() + timeout
    with selectors.DefaultSelector() as selector:
        selector.register(player.stdin, selectors.EVENT_WRITE)
        while pending:
            if player.poll() is not None:
                preview_closed(player)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("The preview is paused or unresponsive. Reopen it to resume.")
            if not selector.select(min(remaining, 0.1)):
                continue
            try:
                count = os.write(player.stdin.fileno(), pending)
            except BlockingIOError:
                continue
            except BrokenPipeError:
                preview_closed(player)
            pending = pending[count:]


class Preview:
    """A local ffplay window; show returns False after normal user closure."""

    def __init__(self, title, fps=15):
        self.player = subprocess.Popen(
            player_command(monitor=True, title=title, fps=fps), stdin=subprocess.PIPE, bufsize=0
        )

    def show(self, frame):
        try:
            deliver_frame(self.player, frame.tobytes())
            return True
        except PreviewClosed:
            return False

    def close(self):
        try:
            self.player.stdin.close()
        except BrokenPipeError:
            pass
        if self.player.poll() is None:
            self.player.terminate()
        try:
            self.player.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.player.kill()
            self.player.wait()
