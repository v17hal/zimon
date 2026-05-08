"""Camera settings — Apply only on button (no auto-apply)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDoubleSpinBox,
    QSpinBox,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from backend.mode_profiles import ModeProfile
from gui_v2.hardware_bridge import CameraSnapshot


class CameraSettingsPage(QWidget):
    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("Camera Settings")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        form = QGroupBox("Acquisition")
        fl = QFormLayout(form)

        self.exposure = QDoubleSpinBox()
        self.exposure.setRange(1, 1_000_000)
        self.exposure.setValue(10000)
        self.exposure.setSuffix(" µs")

        self.gain = QSlider(Qt.Orientation.Horizontal)
        self.gain.setRange(0, 240)
        gain_row = QHBoxLayout()
        gain_row.addWidget(self.gain)
        self.gain_val = QLabel("0")
        gain_row.addWidget(self.gain_val)
        self.gain.valueChanged.connect(lambda v: self.gain_val.setText(str(v)))

        self.fps = QDoubleSpinBox()
        self.fps.setRange(0, 1000)
        self.fps.setValue(60)

        self.w_res = QSpinBox()
        self.w_res.setRange(1, 8192)
        self.w_res.setValue(1440)
        self.h_res = QSpinBox()
        self.h_res.setRange(1, 8192)
        self.h_res.setValue(1080)

        self.pixel_fmt = QComboBox()
        self.pixel_fmt.addItems(["Mono8", "Mono16", "RGB8", "BayerRG8"])

        fl.addRow("Exposure", self.exposure)
        fl.addRow("Gain", gain_row)
        fl.addRow("Target FPS", self.fps)
        fl.addRow("Width", self.w_res)
        fl.addRow("Height", self.h_res)
        fl.addRow("Pixel format", self.pixel_fmt)

        root.addWidget(form)

        self.current_label = QLabel("Current: (not read from device — placeholder)")
        self.current_label.setWordWrap(True)
        root.addWidget(self.current_label)

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setObjectName("PrimaryButton")
        self.apply_btn.clicked.connect(self._apply)
        root.addWidget(self.apply_btn)
        root.addStretch(1)

    def _apply(self) -> None:
        snap = CameraSnapshot(
            exposure_us=float(self.exposure.value()),
            gain_db=float(self.gain.value()),
            fps=float(self.fps.value()),
            width=int(self.w_res.value()),
            height=int(self.h_res.value()),
            pixel_format=self.pixel_fmt.currentText(),
        )
        self._bridge.apply_camera_settings(snap)
        self.current_label.setText(
            f"Current (staged): {snap.width}x{snap.height} @ {snap.fps} FPS, {snap.pixel_format}"
        )

    def apply_mode_profile(self, profile: ModeProfile) -> None:
        """Adult/larval: refresh default spinbox values (Apply still required for device)."""
        self.fps.setValue(profile.default_fps)
        self.exposure.setValue(profile.default_exposure_us)
        self.gain.setValue(int(profile.default_gain))
        w, h = profile.resolution_hint
        self.w_res.setValue(w)
        self.h_res.setValue(h)
