"""Stimulus control — vibration, RGB, timing; sequence placeholder."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QColorDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class StimulusPage(QWidget):
    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._color = (200, 200, 255)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("Stimulus Control")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        vib = QGroupBox("Vibration")
        vf = QFormLayout(vib)
        self.vib_on = QPushButton("Trigger vibration (placeholder)")
        self.vib_on.clicked.connect(
            lambda: self._bridge.apply_stimulus_vibration(True, self.vib_dur.value())
        )
        self.vib_dur = QSpinBox()
        self.vib_dur.setRange(1, 600_000)
        self.vib_dur.setValue(500)
        self.vib_dur.setSuffix(" ms")
        vf.addRow("Duration", self.vib_dur)
        vf.addRow(self.vib_on)
        root.addWidget(vib)

        rgb = QGroupBox("RGB light")
        rg = QFormLayout(rgb)
        self.btn_color = QPushButton("Pick color…")
        self.btn_color.clicked.connect(self._pick_color)
        self.r = QSpinBox()
        self.g = QSpinBox()
        self.b = QSpinBox()
        for s in (self.r, self.g, self.b):
            s.setRange(0, 255)
        self.r.setValue(self._color[0])
        self.g.setValue(self._color[1])
        self.b.setValue(self._color[2])
        self.intensity = QSlider(Qt.Orientation.Horizontal)
        self.intensity.setRange(0, 100)
        self.intensity.setValue(80)
        rg.addRow("R", self.r)
        rg.addRow("G", self.g)
        rg.addRow("B", self.b)
        rg.addRow("Intensity %", self.intensity)
        rg.addRow(self.btn_color)
        root.addWidget(rgb)

        tim = QGroupBox("Timing")
        tf = QFormLayout(tim)
        self.delay_ms = QSpinBox()
        self.delay_ms.setRange(0, 600_000)
        self.delay_ms.setSuffix(" ms")
        self.stim_dur = QSpinBox()
        self.stim_dur.setRange(1, 600_000)
        self.stim_dur.setSuffix(" ms")
        tf.addRow("Delay", self.delay_ms)
        tf.addRow("Duration", self.stim_dur)
        root.addWidget(tim)

        seq = QGroupBox("Sequences")
        seq_l = QVBoxLayout(seq)
        seq_l.addWidget(QLabel("Future: stimulus sequence programming (placeholder)."))
        root.addWidget(seq)

        row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply stimulus")
        self.apply_btn.setObjectName("PrimaryButton")
        self.apply_btn.clicked.connect(self._apply)
        row.addWidget(self.apply_btn)
        root.addLayout(row)
        root.addStretch(1)

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(parent=self)
        if c.isValid():
            self.r.setValue(c.red())
            self.g.setValue(c.green())
            self.b.setValue(c.blue())

    def _apply(self) -> None:
        self._bridge.apply_stimulus_vibration(True, self.vib_dur.value())
        self._bridge.apply_stimulus_rgb(
            self.r.value(), self.g.value(), self.b.value(), self.intensity.value() / 100.0
        )
        self._bridge.apply_stimulus_timing(self.delay_ms.value(), self.stim_dur.value())
