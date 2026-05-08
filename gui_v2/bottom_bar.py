"""Bottom status bar — matches PPT: icons + Camera/Chamber/Temperature + tip + Run Protocol."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget


class BottomBar(QFrame):
    run_protocol_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("BottomBar")
        self.setFixedHeight(40)
        self._build()

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(0)

        # Nav arrows
        btn_left = QPushButton("‹")
        btn_left.setObjectName("SmallButton")
        btn_left.setFixedSize(24, 24)
        lay.addWidget(btn_left)
        lay.addSpacing(10)

        # Status chips
        self._cam_lbl  = self._chip("📷", "Camera",      "Idle",  False)
        self._cham_lbl = self._chip("⚙",  "Chamber",     "Idle",  False)
        self._temp_lbl = self._chip("🌡", "Temperature", "—",     False)

        lay.addWidget(self._cam_lbl)
        lay.addSpacing(20)
        lay.addWidget(self._cham_lbl)
        lay.addSpacing(20)
        lay.addWidget(self._temp_lbl)
        lay.addSpacing(10)

        # Tip message
        self._tip = QLabel("All devices connected and ready. You're good to begin.")
        self._tip.setObjectName("BottomTip")
        lay.addWidget(self._tip)
        lay.addStretch(1)

        btn_right = QPushButton("›")
        btn_right.setObjectName("SmallButton")
        btn_right.setFixedSize(24, 24)
        lay.addWidget(btn_right)
        lay.addSpacing(12)

        self._run_btn = QPushButton("▶  Run Protocol")
        self._run_btn.setObjectName("RunProtocolBtn")
        self._run_btn.setFixedHeight(30)
        self._run_btn.clicked.connect(self.run_protocol_clicked.emit)
        self._run_btn.hide()
        lay.addWidget(self._run_btn)

    def _chip(self, icon: str, name: str, value: str, connected: bool) -> QLabel:
        lbl = QLabel(f"{icon} {name}  {'Connected' if connected else value}")
        lbl.setObjectName("BottomChip")
        return lbl

    def set_camera(self, status: str, connected: bool) -> None:
        self._cam_lbl.setText(f"📷 Camera  {status}")

    def set_chamber(self, status: str, connected: bool = False) -> None:
        self._cham_lbl.setText(f"⚙ Chamber  {status}")

    def set_temperature(self, temp_str: str) -> None:
        self._temp_lbl.setText(f"🌡 Temperature  {temp_str}")

    def set_tip(self, msg: str) -> None:
        self._tip.setText(msg)

    def show_run_protocol(self, visible: bool) -> None:
        self._run_btn.setVisible(visible)
