"""Top bar: mode, camera, status, FPS, recording controls."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


class TopBar(QFrame):
    mode_changed = pyqtSignal(str)  # "adult" | "larval"
    camera_changed = pyqtSignal(str)
    record_start_clicked = pyqtSignal()
    record_stop_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TopBar")
        self._build()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(24)

        # Left group: mode + camera
        left = QHBoxLayout()
        left.setSpacing(8)
        lbl_mode = QLabel("Mode:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Adult", "Larval"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_text)
        left.addWidget(lbl_mode)
        left.addWidget(self.mode_combo)

        lbl_cam = QLabel("Camera:")
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(200)
        self.camera_combo.addItems(["— select —"])
        self.camera_combo.currentTextChanged.connect(self.camera_changed.emit)
        left.addSpacing(8)
        left.addWidget(lbl_cam)
        left.addWidget(self.camera_combo)
        layout.addLayout(left)

        # Center group: status + FPS
        center = QHBoxLayout()
        center.setSpacing(10)
        center.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("StatusChip")
        center.addWidget(self.status_label)
        lbl_fps = QLabel("FPS:")
        self.fps_label = QLabel("—")
        self.fps_label.setObjectName("FpsReadout")
        center.addSpacing(8)
        center.addWidget(lbl_fps)
        center.addWidget(self.fps_label)
        layout.addLayout(center, 1)

        # Right group: recording controls
        right = QHBoxLayout()
        right.setSpacing(8)
        self.btn_rec_start = QPushButton("Start Recording")
        self.btn_rec_start.setObjectName("PrimaryButton")
        self.btn_rec_start.clicked.connect(self.record_start_clicked.emit)
        self.btn_rec_stop = QPushButton("Stop")
        self.btn_rec_stop.setObjectName("DangerButton")
        self.btn_rec_stop.setEnabled(False)
        self.btn_rec_stop.clicked.connect(self.record_stop_clicked.emit)
        right.addWidget(self.btn_rec_start)
        right.addWidget(self.btn_rec_stop)
        layout.addLayout(right)

    def _on_mode_text(self, text: str) -> None:
        self.mode_changed.emit(text.lower())

    def set_cameras(self, names: list[str]) -> None:
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        self.camera_combo.addItems(names if names else ["— none —"])
        self.camera_combo.blockSignals(False)

    def set_fps_text(self, text: str) -> None:
        self.fps_label.setText(text)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_recording_ui(self, active: bool) -> None:
        self.btn_rec_start.setEnabled(not active)
        self.btn_rec_stop.setEnabled(active)
