"""
Relays camera frames from QThread workers to the main thread via QueuedConnection.
"""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


class FrameRelay(QObject):
    """Receives ndarray in worker thread; forwards to main thread."""

    frame_ready = pyqtSignal(object)

    @pyqtSlot(object)
    def push(self, frame) -> None:
        self.frame_ready.emit(frame)
