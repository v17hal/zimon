"""Bottom status bar — Temperature + Arduino status + tip message."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget


class BottomBar(QFrame):
    run_protocol_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("BottomBar")
        self.setFixedHeight(36)
        self._build()

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(24)

        # Arduino connection status
        self._arduino_lbl = QLabel("● Arduino: Disconnected")
        self._arduino_lbl.setObjectName("BottomChipRed")
        lay.addWidget(self._arduino_lbl)

        # Temperature
        self._temp_lbl = QLabel("🌡 Temperature: —")
        self._temp_lbl.setObjectName("BottomChip")
        lay.addWidget(self._temp_lbl)

        # Tip / context message
        self._tip = QLabel("All devices connected and ready. You're good to begin.")
        self._tip.setObjectName("BottomTip")
        lay.addWidget(self._tip)

        lay.addStretch(1)

        # Run Protocol button (shown contextually)
        self._run_btn = QPushButton("▶  Run Protocol")
        self._run_btn.setObjectName("RunProtocolBtn")
        self._run_btn.setFixedHeight(28)
        self._run_btn.clicked.connect(self.run_protocol_clicked.emit)
        self._run_btn.hide()
        lay.addWidget(self._run_btn)

    def set_camera(self, status: str, connected: bool) -> None:
        pass  # Camera/Chamber chips removed per client request

    def set_chamber(self, status: str, connected: bool = False) -> None:
        pass

    def set_temperature(self, temp_str: str) -> None:
        self._temp_lbl.setText(f"🌡 {temp_str}")

    def set_arduino_status(self, connected: bool) -> None:
        if connected:
            self._arduino_lbl.setText("● Arduino: Connected")
            self._arduino_lbl.setObjectName("BottomChipGreen")
        else:
            self._arduino_lbl.setText("● Arduino: Disconnected")
            self._arduino_lbl.setObjectName("BottomChipRed")
        self._arduino_lbl.style().unpolish(self._arduino_lbl)
        self._arduino_lbl.style().polish(self._arduino_lbl)

    def set_tip(self, msg: str) -> None:
        self._tip.setText(msg)

    def show_run_protocol(self, visible: bool) -> None:
        self._run_btn.setVisible(visible)
