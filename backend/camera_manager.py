"""
Unified camera API over existing FLIR / Basler / Webcam stack (CameraController).
Streams run on QThread workers — UI receives frames via signals on the main thread.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

import numpy as np
from PyQt6.QtCore import QObject, Qt, pyqtSignal, pyqtSlot

from backend.camera_interface import CameraController
from backend.frame_relay import FrameRelay

LOG = logging.getLogger("CameraManager")


class CameraManager(QObject):
    """
    High-level camera API:
    - connect_camera() / start_stream() / stop_stream()
    - frame_ready (main thread) — numpy array (BGR or mono)
    - error_occurred, fps_changed
    """

    frame_ready = pyqtSignal(object)  # np.ndarray — after optional overlay hook
    error_occurred = pyqtSignal(str)
    fps_changed = pyqtSignal(float)
    stream_state_changed = pyqtSignal(bool)

    def __init__(self, overlay_hook: Optional[Callable[[np.ndarray], np.ndarray]] = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._controller = CameraController()
        self._controller.worker_error.connect(self.error_occurred.emit)
        self._controller.worker_fps_updated.connect(self.fps_changed.emit)
        self._relay = FrameRelay()
        self._relay.frame_ready.connect(self._on_frame_main)
        self._overlay_hook = overlay_hook
        self._camera_name: Optional[str] = None
        self._streaming = False
        self._latest_lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None

    def list_cameras(self) -> list[str]:
        return self._controller.list_cameras()

    def refresh_cameras(self) -> None:
        self._controller.refresh_cameras()

    def connect_camera(self, camera_name: str) -> bool:
        """Select active camera (must exist after detection)."""
        if camera_name not in self._controller.list_cameras():
            LOG.warning("Camera %s not in list", camera_name)
            return False
        self._camera_name = camera_name
        return True

    def start_stream(self, camera_name: Optional[str] = None) -> bool:
        name = camera_name or self._camera_name
        if not name or name not in self._controller.cameras:
            self.error_occurred.emit("No camera selected")
            return False

        self.stop_stream()

        # Critical: pass relay.push so Qt queues slot to main thread
        ok = self._controller.start_preview(name, self._relay.push)
        if ok:
            self._camera_name = name
            self._streaming = True
            self.stream_state_changed.emit(True)
        return ok

    def stop_stream(self) -> None:
        if self._camera_name:
            self._controller.stop_preview(self._camera_name)
        self._streaming = False
        self.stream_state_changed.emit(False)

    @pyqtSlot(object)
    def _on_frame_main(self, frame: np.ndarray) -> None:
        """Runs in GUI thread."""
        try:
            if self._overlay_hook is not None:
                frame = self._overlay_hook(frame)
            with self._latest_lock:
                self._latest_frame = frame
            self.frame_ready.emit(frame)
        except Exception as e:
            LOG.exception("Frame handling error: %s", e)

    def get_frame(self) -> Optional[np.ndarray]:
        """Latest frame for recording thread (copy under lock)."""
        with self._latest_lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def get_current_fps(self) -> float:
        if not self._camera_name:
            return 0.0
        return self._controller.get_current_fps(self._camera_name) or 0.0

    def set_setting(self, setting: str, value) -> bool:
        if not self._camera_name:
            return False
        return self._controller.set_setting(self._camera_name, setting, value)

    def is_streaming(self) -> bool:
        return self._streaming

    def current_camera_name(self) -> Optional[str]:
        return self._camera_name
