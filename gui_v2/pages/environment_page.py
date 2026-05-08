"""Environment page — Camera Devices + Stimulus Devices, each with status and Test button.

Matches PPT mockup: cards with Connected/Ready badges and individual Test buttons.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _DeviceCard(QFrame):
    """Single device row card with status badge and test button."""

    def __init__(self, name: str, sub: str = "", connected: bool = False,
                 on_test=None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DeviceCard")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        self._dot = QLabel("●")
        self._dot.setObjectName("DotGreen" if connected else "DotGray")
        self._dot.setFixedWidth(18)
        lay.addWidget(self._dot)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name_lbl = QLabel(name)
        name_lbl.setObjectName("DeviceName")
        text_col.addWidget(name_lbl)
        if sub:
            sub_lbl = QLabel(sub)
            sub_lbl.setObjectName("DeviceSub")
            text_col.addWidget(sub_lbl)
        lay.addLayout(text_col, 1)

        self._badge = QLabel("Connected" if connected else "Disconnected")
        self._badge.setObjectName("BadgeGreen" if connected else "BadgeGray")
        self._badge.setFixedWidth(110)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._badge)

        if on_test:
            btn = QPushButton("Test ›")
            btn.setObjectName("SmallButton")
            btn.setFixedWidth(72)
            btn.clicked.connect(on_test)
            lay.addWidget(btn)

    def set_connected(self, connected: bool) -> None:
        self._dot.setObjectName("DotGreen" if connected else "DotGray")
        self._badge.setText("Connected" if connected else "Disconnected")
        self._badge.setObjectName("BadgeGreen" if connected else "BadgeGray")
        self._dot.style().unpolish(self._dot)
        self._dot.style().polish(self._dot)
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)


class _StimulusCard(QFrame):
    def __init__(self, name: str, on_test=None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DeviceCard")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        self._dot = QLabel("●")
        self._dot.setObjectName("DotGreen")
        self._dot.setFixedWidth(18)
        lay.addWidget(self._dot)

        name_lbl = QLabel(name)
        name_lbl.setObjectName("DeviceName")
        lay.addWidget(name_lbl, 1)

        self._badge = QLabel("Ready")
        self._badge.setObjectName("BadgeBlue")
        self._badge.setFixedWidth(80)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._badge)

        if on_test:
            btn = QPushButton(f"Test {name}")
            btn.setObjectName("SmallButton")
            btn.setFixedWidth(120)
            btn.clicked.connect(on_test)
            lay.addWidget(btn)

    def set_status(self, text: str, obj_name: str = "BadgeBlue") -> None:
        self._badge.setText(text)
        self._badge.setObjectName(obj_name)
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)


class EnvironmentPage(QWidget):
    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_camera_status)
        self._timer.start(2000)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(20)

        title = QLabel("Environment")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        # ── Camera Devices ──────────────────────────────────────────────
        cam_group = QGroupBox("Camera Devices")
        cam_lay = QVBoxLayout(cam_group)
        cam_lay.setSpacing(8)

        self._cam_machine = _DeviceCard(
            "Machine Vision (Larval)", "High-speed scientific camera",
            connected=False, on_test=lambda: self._test_camera(0)
        )
        self._cam_adult_top = _DeviceCard(
            "USB Camera (Adult Top)", "Top-down view",
            connected=False, on_test=lambda: self._test_camera(1)
        )
        self._cam_adult_side = _DeviceCard(
            "USB Camera (Adult Side)", "Side view",
            connected=False, on_test=lambda: self._test_camera(2)
        )

        cam_lay.addWidget(self._cam_machine)
        cam_lay.addWidget(self._cam_adult_top)
        cam_lay.addWidget(self._cam_adult_side)

        self._cam_ready_lbl = QLabel("System Ready: Checking…")
        self._cam_ready_lbl.setObjectName("ReadyLabel")
        cam_lay.addWidget(self._cam_ready_lbl)
        root.addWidget(cam_group)

        # ── Stimulus Devices ────────────────────────────────────────────
        stim_group = QGroupBox("Stimulus Devices")
        stim_lay = QGridLayout(stim_group)
        stim_lay.setSpacing(8)
        stim_lay.setColumnStretch(0, 1)
        stim_lay.setColumnStretch(1, 1)

        self._stim_light = _StimulusCard("Light",     on_test=self._test_light)
        self._stim_vib   = _StimulusCard("Vibration", on_test=self._test_vibration)
        self._stim_buzz  = _StimulusCard("Buzzer",    on_test=self._test_buzzer)
        self._stim_water = _StimulusCard("Water Flow",on_test=self._test_water)

        stim_lay.addWidget(self._stim_light, 0, 0)
        stim_lay.addWidget(self._stim_vib,   0, 1)
        stim_lay.addWidget(self._stim_buzz,  1, 0)
        stim_lay.addWidget(self._stim_water, 1, 1)

        self._stim_ready_lbl = QLabel("System Ready: YES ✓")
        self._stim_ready_lbl.setObjectName("ReadyLabelGreen")
        stim_lay.addWidget(self._stim_ready_lbl, 2, 0, 1, 2)
        root.addWidget(stim_group)

        root.addStretch(1)

    def _refresh_camera_status(self) -> None:
        # Use list_cameras() on the manager directly (no refresh scan) to avoid
        # stopping any active stream — refresh_cameras() kills webcam streams.
        cameras = self._bridge.camera_manager.list_cameras()
        streaming = self._bridge.camera_manager.is_streaming()
        has_any = bool(cameras)
        self._cam_machine.set_connected(streaming)
        self._cam_adult_top.set_connected(len(cameras) > 1 and streaming)
        self._cam_adult_side.set_connected(False)
        ready = streaming or has_any
        self._cam_ready_lbl.setText(
            "System Ready: YES ✓" if ready else "System Ready: NO — connect a camera"
        )
        self._cam_ready_lbl.setObjectName("ReadyLabelGreen" if ready else "ReadyLabel")

    def _test_camera(self, idx: int) -> None:
        cameras = self._bridge.camera_manager.list_cameras()
        if cameras and idx < len(cameras):
            self._bridge.start_camera_preview(cameras[idx])

    def _test_light(self) -> None:
        ard = getattr(self._bridge, "_arduino", None)
        if ard and ard.is_connected():
            ard.set_ir_intensity(50)
            QTimer.singleShot(1000, lambda: ard.set_ir_intensity(0))
        self._stim_light.set_status("Testing…", "BadgeYellow")
        QTimer.singleShot(1200, lambda: self._stim_light.set_status("Ready", "BadgeBlue"))

    def _test_vibration(self) -> None:
        ard = getattr(self._bridge, "_arduino", None)
        if ard and ard.is_connected():
            ard.vibrate_timed(500)
        self._stim_vib.set_status("Testing…", "BadgeYellow")
        QTimer.singleShot(700, lambda: self._stim_vib.set_status("Ready", "BadgeBlue"))

    def _test_buzzer(self) -> None:
        ard = getattr(self._bridge, "_arduino", None)
        if ard and ard.is_connected():
            ard.write_command("BUZZER_ON")
            QTimer.singleShot(500, lambda: ard.write_command("BUZZER_OFF"))
        self._stim_buzz.set_status("Testing…", "BadgeYellow")
        QTimer.singleShot(700, lambda: self._stim_buzz.set_status("Ready", "BadgeBlue"))

    def _test_water(self) -> None:
        ard = getattr(self._bridge, "_arduino", None)
        if ard and ard.is_connected():
            ard.write_command("PUMP_ON")
            QTimer.singleShot(300, lambda: ard.write_command("PUMP_OFF"))
        self._stim_water.set_status("Testing…", "BadgeYellow")
        QTimer.singleShot(500, lambda: self._stim_water.set_status("Ready", "BadgeBlue"))
