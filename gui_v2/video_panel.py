"""Live preview — QLabel with scaled pixmap; optional FPS overlay."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class VideoPanel(QFrame):
    """QLabel preview with aspect-ratio scaling; future overlay stack."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("VideoPanel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(0)

        self._video = QLabel()
        self._video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video.setObjectName("VideoPlaceholder")
        self._video.setMinimumSize(640, 400)
        self._video.setScaledContents(False)
        self._video.setText("No signal")

        # Top-left badge: Live feed
        self._badge = QLabel("LIVE FEED")
        self._badge.setParent(self._video)
        self._badge.setObjectName("VideoBadge")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._badge.move(12, 10)

        # Top-right badge: FPS
        self._overlay = QLabel(self._video)
        self._overlay.setObjectName("VideoFpsOverlay")
        self._overlay.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self._overlay.hide()

        lay.addWidget(self._video, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_overlay()

    def _position_overlay(self) -> None:
        m = 8
        self._overlay.move(self._video.width() - self._overlay.width() - m, m)

    def set_frame(self, image: QImage) -> None:
        """Display frame; scales to label size while keeping aspect ratio."""
        if image.isNull():
            return
        pix = QPixmap.fromImage(image)
        scaled = pix.scaled(
            self._video.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._video.setPixmap(scaled)
        self._video.setText("")
        self._position_overlay()

    def clear_frame(self, message: str = "No signal") -> None:
        self._video.clear()
        self._video.setText(message)

    def set_fps_overlay(self, text: str) -> None:
        self._overlay.setText(text)
        self._overlay.adjustSize()
        self._overlay.show()
        self._position_overlay()
