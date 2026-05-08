"""Larval mode page — Well/ROI grid overlay on live video.

Three-column layout matching Adult page:
  Left  (~240px) — Stimulus Control (same as Adult)
  Center (expand) — Live video + Well plate overlay + controls
  Right (~200px)  — Well/ROI config + assay select
"""

from __future__ import annotations

import time

import numpy as np

from PyQt6.QtCore import Qt, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui_v2.frame_utils import numpy_to_qimage
from gui_v2.video_panel import VideoPanel


# ── Well plate overlay widget ─────────────────────────────────────────────────

class WellPlateOverlay(QWidget):
    """Draws a well-plate grid on top of the video frame."""

    PLATES = {
        "96-well":  (8, 12),
        "48-well":  (6, 8),
        "24-well":  (4, 6),
        "12-well":  (3, 4),
        "6-well":   (2, 3),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows = 4
        self._cols = 6
        self._selected: set[tuple[int,int]] = set()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMinimumSize(200, 150)

    def set_plate(self, label: str) -> None:
        rows, cols = self.PLATES.get(label, (4, 6))
        self._rows = rows
        self._cols = cols
        self._selected.clear()
        self.update()

    def mousePressEvent(self, event) -> None:
        # Toggle well selection
        w, h = self.width(), self.height()
        cw, ch = w / self._cols, h / self._rows
        col = int(event.position().x() / cw)
        row = int(event.position().y() / ch)
        if 0 <= row < self._rows and 0 <= col < self._cols:
            key = (row, col)
            if key in self._selected:
                self._selected.discard(key)
            else:
                self._selected.add(key)
            self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cw, ch = w / self._cols, h / self._rows

        for row in range(self._rows):
            for col in range(self._cols):
                x, y = col * cw, row * ch
                selected = (row, col) in self._selected

                # Fill
                if selected:
                    p.setBrush(QBrush(QColor(99, 102, 241, 100)))
                else:
                    p.setBrush(QBrush(QColor(255, 255, 255, 30)))

                p.setPen(QPen(QColor(255, 255, 255, 160), 1.5))
                p.drawEllipse(QRectF(x + 3, y + 3, cw - 6, ch - 6))

                # Well label
                p.setPen(QPen(QColor(255, 255, 255, 200)))
                font = QFont("Segoe UI", max(7, int(min(cw, ch) * 0.25)))
                p.setFont(font)
                col_label = chr(ord('A') + col) if self._rows <= self._cols else str(col + 1)
                row_label = str(row + 1)
                p.drawText(
                    QRectF(x, y, cw, ch),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{chr(ord('A')+row)}{col+1}"
                )
        p.end()


# ── Left stimulus panel ────────────────────────────────────────────────────────

class _LarvalStimulusPanel(QScrollArea):
    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self.setObjectName("StimulusPanel")
        self.setFixedWidth(240)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setContentsMargins(14, 16, 14, 16)
        root.setSpacing(14)

        title = QLabel("Stimulus Control")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        # Light section
        light_lbl = QLabel("Light")
        light_lbl.setObjectName("SectionLabel")
        root.addWidget(light_lbl)

        type_row = QHBoxLayout()
        type_group = QButtonGroup(inner)
        type_group.setExclusive(True)
        for label in ["IR", "White", "RGB"]:
            btn = QPushButton(label)
            btn.setObjectName("TypeBtn")
            btn.setCheckable(True)
            type_group.addButton(btn)
            type_row.addWidget(btn)
        type_group.buttons()[0].setChecked(True)
        root.addLayout(type_row)

        self._intensity_lbl = QLabel("Intensity   80%")
        root.addWidget(self._intensity_lbl)
        self._intensity = QSlider(Qt.Orientation.Horizontal)
        self._intensity.setRange(0, 100)
        self._intensity.setValue(80)
        self._intensity.valueChanged.connect(
            lambda v: self._intensity_lbl.setText(f"Intensity   {v}%"))
        root.addWidget(self._intensity)

        dur_row = QHBoxLayout()
        dur_lbl = QLabel("Duration")
        self._dur = QSpinBox()
        self._dur.setRange(1, 3600)
        self._dur.setValue(1)
        self._dur.setSuffix(" sec")
        dur_row.addWidget(dur_lbl)
        dur_row.addWidget(self._dur)
        root.addLayout(dur_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        # Buzzer section
        buzz_lbl = QLabel("Buzzer")
        buzz_lbl.setObjectName("SectionLabel")
        root.addWidget(buzz_lbl)

        tone_row = QHBoxLayout()
        tone_group = QButtonGroup(inner)
        tone_group.setExclusive(True)
        for t in ["Tone", "Noise"]:
            r = QRadioButton(t)
            tone_group.addButton(r)
            tone_row.addWidget(r)
        tone_group.buttons()[0].setChecked(True)
        root.addLayout(tone_row)

        amp_row = QHBoxLayout()
        amp_lbl = QLabel("Amplitude")
        self._amp = QSpinBox()
        self._amp.setRange(0, 255)
        self._amp.setValue(100)
        amp_row.addWidget(amp_lbl)
        amp_row.addWidget(self._amp)
        root.addLayout(amp_row)

        root.addStretch(1)
        self.setWidget(inner)


# ── Right ROI config panel ────────────────────────────────────────────────────

class _LarvalROIPanel(QWidget):
    def __init__(self, bridge, overlay: WellPlateOverlay, navigate_to, parent=None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._overlay = overlay
        self.setObjectName("AssayPanel")
        self.setFixedWidth(210)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 16, 14, 16)
        root.setSpacing(14)

        title = QLabel("Well / ROI")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        plate_lbl = QLabel("Plate Format")
        plate_lbl.setObjectName("SectionLabel")
        root.addWidget(plate_lbl)

        self._plate_combo = QComboBox()
        self._plate_combo.addItems(["96-well", "48-well", "24-well", "12-well", "6-well"])
        self._plate_combo.setCurrentText("24-well")
        self._plate_combo.currentTextChanged.connect(self._on_plate_changed)
        root.addWidget(self._plate_combo)

        # Select all / clear
        btn_row = QHBoxLayout()
        btn_all = QPushButton("Select All")
        btn_all.setObjectName("SmallButton")
        btn_clear = QPushButton("Clear")
        btn_clear.setObjectName("SmallButton")
        btn_all.clicked.connect(self._select_all)
        btn_clear.clicked.connect(self._clear_all)
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_clear)
        root.addLayout(btn_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        assay_lbl = QLabel("Assay Select")
        assay_lbl.setObjectName("SectionLabel")
        root.addWidget(assay_lbl)

        self._assay_group = QButtonGroup(self)
        self._assay_group.setExclusive(True)
        for assay in ["TOP", "SIDE"]:
            r = QRadioButton(assay)
            self._assay_group.addButton(r)
            root.addWidget(r)
        self._assay_group.buttons()[0].setChecked(True)

        self._ready_lbl = QLabel("● System Ready: YES")
        self._ready_lbl.setObjectName("ReadyLabelGreen")
        root.addWidget(self._ready_lbl)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep2)

        for label in ["Escape Response ›", "Light/Dark Test ›", "Load Assay ›"]:
            btn = QPushButton(label)
            btn.setObjectName("AssayRow")
            root.addWidget(btn)

        btn_proto = QPushButton("Create New → Protocol Builder")
        btn_proto.setObjectName("SmallButton")
        btn_proto.clicked.connect(lambda: navigate_to("protocol_builder"))
        root.addWidget(btn_proto)

        root.addStretch(1)

        # Trigger initial plate setup
        self._on_plate_changed(self._plate_combo.currentText())

    def _on_plate_changed(self, label: str) -> None:
        self._overlay.set_plate(label)

    def _select_all(self) -> None:
        rows, cols = self._overlay._rows, self._overlay._cols
        self._overlay._selected = {(r, c) for r in range(rows) for c in range(cols)}
        self._overlay.update()

    def _clear_all(self) -> None:
        self._overlay._selected.clear()
        self._overlay.update()


# ── Center panel ──────────────────────────────────────────────────────────────

class _LarvalCenterPanel(QWidget):
    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._last_frame_time = 0.0
        self.setObjectName("VideoArea")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Video + overlay stack
        video_stack = QWidget()
        video_stack.setObjectName("VideoArea")
        stack_lay = QVBoxLayout(video_stack)
        stack_lay.setContentsMargins(0, 0, 0, 0)

        self._video = VideoPanel()
        stack_lay.addWidget(self._video)

        self._overlay = WellPlateOverlay(video_stack)
        self._overlay.setGeometry(0, 0, 100, 100)
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        video_stack.resizeEvent = self._on_video_resize
        root.addWidget(video_stack, 1)

        # Controls
        ctrl = QHBoxLayout()
        self._btn_start = QPushButton("▶  Start")
        self._btn_start.setObjectName("StartBtn")
        self._btn_start.clicked.connect(self._on_start)
        self._btn_stop = QPushButton("■  Stop")
        self._btn_stop.setObjectName("StopBtn")
        self._btn_stop.clicked.connect(self._on_stop)
        self._dur_lbl = QLabel("00:00")
        ctrl.addWidget(self._btn_start)
        ctrl.addWidget(self._btn_stop)
        ctrl.addStretch(1)
        ctrl.addWidget(QLabel("Duration:"))
        ctrl.addWidget(self._dur_lbl)
        root.addLayout(ctrl)

        # Timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._elapsed = 0

        # Connect camera frames
        bridge.camera_manager.frame_ready.connect(self._on_frame)

    def _on_video_resize(self, event) -> None:
        self._overlay.setGeometry(self._video.geometry())

    def _on_frame(self, frame) -> None:
        now = time.monotonic()
        if now - self._last_frame_time < 1.0 / 60.0:
            return
        self._last_frame_time = now
        try:
            self._video.set_frame(numpy_to_qimage(frame))
        except Exception:
            pass

    def _on_start(self) -> None:
        self._elapsed = 0
        self._timer.start(1000)

    def _on_stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._elapsed += 1
        m, s = divmod(self._elapsed, 60)
        self._dur_lbl.setText(f"{m:02d}:{s:02d}")

    def get_overlay(self) -> WellPlateOverlay:
        return self._overlay


# ── Main Larval page ──────────────────────────────────────────────────────────

class LarvalPage(QWidget):
    navigate_to = pyqtSignal(str)

    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._build()

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left stimulus panel
        self._stimulus = _LarvalStimulusPanel(self._bridge)
        root.addWidget(self._stimulus)

        # Center video + overlay
        self._center = _LarvalCenterPanel(self._bridge)
        root.addWidget(self._center, 1)

        # Right ROI panel
        self._roi = _LarvalROIPanel(
            self._bridge,
            self._center.get_overlay(),
            navigate_to=self.navigate_to.emit,
        )
        root.addWidget(self._roi)
