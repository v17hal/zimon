"""
Non-blocking video recording using OpenCV VideoWriter on a QThread.
Pulls newest frame from CameraManager (newest-only semantics).
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Callable, Optional

import cv2
from PyQt6.QtCore import QObject, QThread, pyqtSignal

if TYPE_CHECKING:
    from backend.camera_manager import CameraManager

LOG = logging.getLogger("RecordingManager")


class RecordingWorker(QThread):
    """Writes video in background; start/stop safely."""

    error_occurred = pyqtSignal(str)
    started = pyqtSignal()
    stopped = pyqtSignal(str)

    def __init__(self, camera_manager: "CameraManager", parent=None) -> None:
        super().__init__(parent)
        self._cam = camera_manager
        self._running = False
        self._path = ""
        self._fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._fps_hint = 60.0
        self._duration_s: Optional[float] = None

    def configure(
        self, output_path: str, fps_hint: float = 60.0, duration_s: Optional[float] = None
    ) -> None:
        self._path = output_path
        self._fps_hint = max(1.0, float(fps_hint))
        self._duration_s = float(duration_s) if duration_s is not None and float(duration_s) > 0 else None

    def run(self) -> None:
        writer: Optional[cv2.VideoWriter] = None
        self._running = True
        t0 = time.time()
        try:
            out_dir = os.path.dirname(os.path.abspath(self._path))
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            self.started.emit()
            last_t = time.time()
            while self._running:
                if self._duration_s is not None and (time.time() - t0) >= self._duration_s:
                    break
                frame = self._cam.get_frame()
                if frame is None:
                    self.msleep(2)
                    continue
                if writer is None:
                    h, w = frame.shape[:2]
                    frame_size = (w, h)
                    is_color = frame.ndim == 3 and frame.shape[2] >= 3
                    writer = cv2.VideoWriter(
                        self._path,
                        self._fourcc,
                        self._fps_hint,
                        frame_size,
                        isColor=is_color,
                    )
                    if not writer.isOpened():
                        self.error_occurred.emit(f"Could not open VideoWriter for {self._path}")
                        break
                if frame.ndim == 2:
                    bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                elif frame.shape[2] == 4:
                    bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                else:
                    bgr = frame
                writer.write(bgr)
                now = time.time()
                if now - last_t < 0.001:
                    self.msleep(1)
                last_t = now
        except Exception as e:
            LOG.exception("Recording error")
            self.error_occurred.emit(str(e))
        finally:
            if writer is not None:
                writer.release()
            self.stopped.emit(self._path)

    def stop_safe(self) -> None:
        self._running = False
        self.wait(8000)


class RecordingManager:
    """High-level start/stop around RecordingWorker."""

    def __init__(self, camera_manager: "CameraManager") -> None:
        self._cam = camera_manager
        self._worker: Optional[RecordingWorker] = None

    @property
    def is_recording(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start(
        self,
        output_path: str,
        fps_hint: float = 60.0,
        duration_s: Optional[float] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_stopped: Optional[Callable[[str], None]] = None,
    ) -> bool:
        if self.is_recording:
            return False
        w = RecordingWorker(self._cam)
        w.configure(output_path, fps_hint, duration_s)
        if on_error is not None:
            w.error_occurred.connect(on_error)
        if on_stopped is not None:
            w.stopped.connect(on_stopped)
        w.finished.connect(self._on_worker_finished)
        self._worker = w
        w.start()
        return True

    def _on_worker_finished(self) -> None:
        w = QObject.sender()
        if w is self._worker:
            self._worker = None

    def stop(self) -> None:
        if self._worker is None:
            return
        self._worker.stop_safe()
        self._worker = None
