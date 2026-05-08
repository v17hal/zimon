"""Adult experiment screen — main experiment page for Adult mode.

Three-column layout:
  Left  (~240px)  — Stimulus Control panel (scrollable)
  Center (expand) — Video feed + controls + timeline
  Right (~200px)  — Assay selection + system status
Bottom — status bar + Run Protocol button
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from PyQt6.QtCore import (
    Qt,
    QRectF,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPen,
    QBrush,
)
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

from gui_v2.video_panel import VideoPanel
from gui_v2.frame_utils import numpy_to_qimage


# ── Helpers ──────────────────────────────────────────────────────────────────

def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    line.setObjectName("SectionSeparator")
    return line


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("SectionTitle")
    font = lbl.font()
    font.setBold(True)
    font.setPointSize(font.pointSize() + 1)
    lbl.setFont(font)
    return lbl


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("ControlLabel")
    return lbl


# ── Timeline widget ───────────────────────────────────────────────────────────

class TimelineBar(QWidget):
    """Paints the experiment timeline with coloured segment bars."""

    # Each segment: (label, color hex, relative width 0..1)
    _PHASES = ["Baseline", "Light Pulse", "Recovery"]
    _PHASE_WEIGHTS = [0.25, 0.35, 0.40]

    _ROWS = [
        # row label, list of (segment label, colour, phase_fraction)
        ("Light",     [("", "#c8c8d8", 1.0)]),
        ("Buzzer",    [("ON", "#4caf50", 0.3), ("PULSE 70 ms", "#2196f3", 0.4), ("OFF", "#c8c8d8", 0.3)]),
        ("Vibration", [("OFF", "#c8c8d8", 0.4), ("7", "#9c27b0", 0.2), ("OFF", "#c8c8d8", 0.4)]),
    ]
    _TIME_MARKS = [0, 10, 20, 40, 60, 80, 100, 120, 140]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TimelineBar")
        self.setMinimumHeight(130)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W = self.width()
        H = self.height()

        row_label_w = 68
        bar_left = row_label_w + 4
        bar_w = W - bar_left - 4

        header_h = 24
        row_h = 26
        gap = 4
        footer_h = 18

        total_rows = len(self._ROWS)
        content_h = header_h + total_rows * (row_h + gap) + footer_h

        # Background
        p.fillRect(0, 0, W, H, QColor("#f8f8ff"))

        # Phase headers
        x = bar_left
        for i, (ph, weight) in enumerate(zip(self._PHASES, self._PHASE_WEIGHTS)):
            pw = int(bar_w * weight)
            # light alternating header background
            bg = QColor("#e8e8f8") if i % 2 == 0 else QColor("#f0f0ff")
            p.fillRect(x, 0, pw, header_h - 2, bg)
            p.setPen(QColor("#5c5c8a"))
            p.setFont(QFont("", 8, QFont.Weight.Bold))
            p.drawText(x, 0, pw, header_h - 2, Qt.AlignmentFlag.AlignCenter, ph)
            x += pw

        # Row bars
        for ri, (row_label, segments) in enumerate(self._ROWS):
            y = header_h + ri * (row_h + gap)

            # Row label
            p.setPen(QColor("#333366"))
            p.setFont(QFont("", 8))
            p.drawText(0, y, row_label_w, row_h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, row_label + "  ")

            # Segments
            sx = bar_left
            for seg_label, seg_color, frac in segments:
                sw = int(bar_w * frac)
                rect = QRectF(sx + 1, y + 3, sw - 2, row_h - 6)
                p.setBrush(QBrush(QColor(seg_color)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(rect, 3, 3)
                if seg_label:
                    p.setPen(QColor("#ffffff"))
                    p.setFont(QFont("", 7, QFont.Weight.Bold))
                    p.drawText(int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()),
                               Qt.AlignmentFlag.AlignCenter, seg_label)
                sx += sw

        # Time axis
        y_foot = header_h + total_rows * (row_h + gap) + 2
        p.setPen(QColor("#888888"))
        p.setFont(QFont("", 7))
        total_time = self._TIME_MARKS[-1]
        for t in self._TIME_MARKS:
            tx = bar_left + int(bar_w * t / total_time)
            p.drawText(tx - 12, y_foot, 24, footer_h, Qt.AlignmentFlag.AlignCenter, str(t))

        p.end()


# ── Left panel: Stimulus Control ──────────────────────────────────────────────

class StimulusControlPanel(QWidget):
    """Left scrollable panel with light, buzzer and vibration controls."""

    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self.setObjectName("StimulusControlPanel")
        self._build()

    # ---- build ----

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 14, 12, 14)
        root.setSpacing(10)

        # Title
        title = _section_title("Stimulus Control")
        title.setObjectName("PanelTitle")
        root.addWidget(title)

        root.addWidget(_separator())

        # ---- Light section ----
        root.addWidget(_label("Light"))

        # IR / White / RGB toggle buttons (exclusive)
        light_toggle_row = QHBoxLayout()
        light_toggle_row.setSpacing(4)
        self._btn_ir = QPushButton("IR")
        self._btn_ir.setObjectName("LightToggleBtn")
        self._btn_ir.setCheckable(True)
        self._btn_ir.setChecked(True)
        self._btn_white = QPushButton("White")
        self._btn_white.setObjectName("LightToggleBtn")
        self._btn_white.setCheckable(True)
        self._btn_rgb = QPushButton("RGB")
        self._btn_rgb.setObjectName("LightToggleBtn")
        self._btn_rgb.setCheckable(True)

        self._light_group = QButtonGroup(self)
        self._light_group.setExclusive(True)
        self._light_group.addButton(self._btn_ir, 0)
        self._light_group.addButton(self._btn_white, 1)
        self._light_group.addButton(self._btn_rgb, 2)
        self._light_group.idClicked.connect(self._on_light_type_changed)

        for btn in (self._btn_ir, self._btn_white, self._btn_rgb):
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            light_toggle_row.addWidget(btn)
        root.addLayout(light_toggle_row)

        # Intensity
        intensity_row = QHBoxLayout()
        intensity_row.setSpacing(6)
        intensity_row.addWidget(_label("Intensity"))
        self._intensity_val_lbl = QLabel("80%")
        self._intensity_val_lbl.setObjectName("ValueLabel")
        intensity_row.addStretch()
        intensity_row.addWidget(self._intensity_val_lbl)
        root.addLayout(intensity_row)

        self._intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self._intensity_slider.setObjectName("StimSlider")
        self._intensity_slider.setRange(0, 100)
        self._intensity_slider.setValue(80)
        self._intensity_slider.valueChanged.connect(self._on_intensity_changed)
        root.addWidget(self._intensity_slider)

        # Mode: Continuous / Pulse
        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        mode_row.addWidget(_label("Mode"))
        self._rb_continuous = QRadioButton("Continuous")
        self._rb_continuous.setObjectName("ModeRadio")
        self._rb_continuous.setChecked(True)
        self._rb_pulse = QRadioButton("Pulse")
        self._rb_pulse.setObjectName("ModeRadio")
        mode_row.addWidget(self._rb_continuous)
        mode_row.addWidget(self._rb_pulse)
        mode_row.addStretch()
        root.addLayout(mode_row)

        # Frequency
        freq_row = QHBoxLayout()
        freq_row.setSpacing(6)
        freq_row.addWidget(_label("Frequency"))
        self._freq_lbl = QLabel("5 Hz")
        self._freq_lbl.setObjectName("ValueLabel")
        freq_row.addStretch()
        freq_row.addWidget(self._freq_lbl)
        root.addLayout(freq_row)
        self._freq_slider = QSlider(Qt.Orientation.Horizontal)
        self._freq_slider.setObjectName("StimSlider")
        self._freq_slider.setRange(1, 50)
        self._freq_slider.setValue(5)
        self._freq_slider.valueChanged.connect(lambda v: self._freq_lbl.setText(f"{v} Hz"))
        root.addWidget(self._freq_slider)

        # Pulse Width
        pw_row = QHBoxLayout()
        pw_row.setSpacing(6)
        pw_row.addWidget(_label("Pulse Width"))
        self._pw_lbl = QLabel("50 ms")
        self._pw_lbl.setObjectName("ValueLabel")
        pw_row.addStretch()
        pw_row.addWidget(self._pw_lbl)
        root.addLayout(pw_row)
        self._pw_slider = QSlider(Qt.Orientation.Horizontal)
        self._pw_slider.setObjectName("StimSlider")
        self._pw_slider.setRange(1, 500)
        self._pw_slider.setValue(50)
        self._pw_slider.valueChanged.connect(lambda v: self._pw_lbl.setText(f"{v} ms"))
        root.addWidget(self._pw_slider)

        # Duration
        dur_row = QHBoxLayout()
        dur_row.setSpacing(6)
        dur_row.addWidget(_label("Duration"))
        self._dur_lbl = QLabel("1 sec")
        self._dur_lbl.setObjectName("ValueLabel")
        dur_row.addStretch()
        dur_row.addWidget(self._dur_lbl)
        root.addLayout(dur_row)
        self._dur_slider = QSlider(Qt.Orientation.Horizontal)
        self._dur_slider.setObjectName("StimSlider")
        self._dur_slider.setRange(1, 60)
        self._dur_slider.setValue(1)
        self._dur_slider.valueChanged.connect(lambda v: self._dur_lbl.setText(f"{v} sec"))
        root.addWidget(self._dur_slider)

        root.addWidget(_separator())

        # ---- Buzzer section ----
        root.addWidget(_label("Buzzer"))

        buzz_type_row = QHBoxLayout()
        buzz_type_row.setSpacing(8)
        self._rb_tone = QRadioButton("Tone")
        self._rb_noise = QRadioButton("Noise")
        self._rb_file = QRadioButton("File")
        self._rb_tone.setChecked(True)
        for rb in (self._rb_tone, self._rb_noise, self._rb_file):
            rb.setObjectName("BuzzRadio")
            buzz_type_row.addWidget(rb)
        buzz_type_row.addStretch()
        root.addLayout(buzz_type_row)

        # Amplitude row
        amp_row = QHBoxLayout()
        amp_row.setSpacing(6)
        self._chk_amplitude = QCheckBox("Amplitude")
        self._chk_amplitude.setObjectName("BuzzCheck")
        self._spin_amplitude = QSpinBox()
        self._spin_amplitude.setObjectName("BuzzSpin")
        self._spin_amplitude.setRange(0, 255)
        self._spin_amplitude.setValue(70)
        self._spin_amplitude.setSuffix(" ms")
        self._lbl_amp_z = QLabel("Z")
        self._lbl_amp_z.setObjectName("ZLabel")
        amp_row.addWidget(self._chk_amplitude)
        amp_row.addWidget(self._spin_amplitude)
        amp_row.addWidget(self._lbl_amp_z)
        amp_row.addStretch()
        root.addLayout(amp_row)

        # Duration row
        bdur_row = QHBoxLayout()
        bdur_row.setSpacing(6)
        self._chk_bdur = QCheckBox("Duration")
        self._chk_bdur.setObjectName("BuzzCheck")
        self._spin_bdur = QSpinBox()
        self._spin_bdur.setObjectName("BuzzSpin")
        self._spin_bdur.setRange(1, 60000)
        self._spin_bdur.setValue(1)
        self._spin_bdur.setSuffix(" sec")
        self._btn_bdur_arrow = QPushButton("›")
        self._btn_bdur_arrow.setObjectName("ArrowBtn")
        self._btn_bdur_arrow.setFixedWidth(28)
        bdur_row.addWidget(self._chk_bdur)
        bdur_row.addWidget(self._spin_bdur)
        bdur_row.addWidget(self._btn_bdur_arrow)
        bdur_row.addStretch()
        root.addLayout(bdur_row)

        root.addStretch(1)

    # ---- slots ----

    def _on_intensity_changed(self, value: int) -> None:
        self._intensity_val_lbl.setText(f"{value}%")
        self._apply_light()

    def _on_light_type_changed(self, btn_id: int) -> None:
        self._apply_light()

    def _apply_light(self) -> None:
        intensity = self._intensity_slider.value() / 100.0
        btn_id = self._light_group.checkedId()
        if btn_id == 0:   # IR
            self._bridge.apply_environment_lighting(intensity * 100.0, 0.0)
        elif btn_id == 1:  # White
            self._bridge.apply_environment_lighting(0.0, intensity * 100.0)
        elif btn_id == 2:  # RGB
            # Default purple tint for RGB mode
            self._bridge.apply_stimulus_rgb(180, 0, 255, intensity)


# ── Center: video + controls + timeline ───────────────────────────────────────

class CenterPanel(QWidget):
    """Center panel: video feed, transport controls and timeline."""

    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._elapsed_sec = 0
        self._running = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._last_frame_mono = 0.0
        self._build()
        self._connect_camera()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # Video panel
        self._video = VideoPanel()
        self._video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._video, 3)

        # Transport controls row 1
        ctrl_row1 = QHBoxLayout()
        ctrl_row1.setSpacing(8)

        self._btn_start = QPushButton("▶  Start")
        self._btn_start.setObjectName("StartBtn")
        self._btn_start.setFixedHeight(34)
        self._btn_start.clicked.connect(self._on_start)

        self._btn_stop = QPushButton("■  Stop")
        self._btn_stop.setObjectName("StopBtn")
        self._btn_stop.setFixedHeight(34)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)

        self._lbl_duration = QLabel("Duration:")
        self._lbl_duration.setObjectName("ControlLabel")

        self._lbl_time = QLabel("00:00")
        self._lbl_time.setObjectName("TimeDisplay")
        font = self._lbl_time.font()
        font.setFamily("Consolas")
        font.setPointSize(12)
        self._lbl_time.setFont(font)

        ctrl_row1.addWidget(self._btn_start)
        ctrl_row1.addWidget(self._btn_stop)
        ctrl_row1.addStretch()
        ctrl_row1.addWidget(self._lbl_duration)
        ctrl_row1.addWidget(self._lbl_time)
        root.addLayout(ctrl_row1)

        # Transport controls row 2
        ctrl_row2 = QHBoxLayout()
        ctrl_row2.setSpacing(12)

        self._rb_manual = QRadioButton("Manual")
        self._rb_manual.setObjectName("ModeRadio")
        self._rb_manual.setChecked(True)
        self._rb_protocol = QRadioButton("Protocol")
        self._rb_protocol.setObjectName("ModeRadio")

        self._fps_combo = QComboBox()
        self._fps_combo.setObjectName("FpsCombo")
        self._fps_combo.addItems(["FPS: 15", "FPS: 30", "FPS: 60", "FPS: 120"])
        self._fps_combo.setCurrentIndex(1)
        self._fps_combo.setFixedWidth(100)

        ctrl_row2.addWidget(self._rb_manual)
        ctrl_row2.addWidget(self._rb_protocol)
        ctrl_row2.addStretch()
        ctrl_row2.addWidget(self._fps_combo)
        root.addLayout(ctrl_row2)

        # Timeline section
        tl_header = QHBoxLayout()
        tl_lbl = _section_title("Timeline")
        tl_header.addWidget(tl_lbl)
        tl_header.addStretch()
        root.addLayout(tl_header)

        self._timeline = TimelineBar()
        root.addWidget(self._timeline)

        # Protocol row
        proto_row = QHBoxLayout()
        proto_row.setSpacing(8)
        proto_row.addWidget(_label("Protocol:"))
        self._proto_combo = QComboBox()
        self._proto_combo.setObjectName("ProtocolCombo")
        self._proto_combo.addItem("Protocol: Startle Response")
        self._proto_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        proto_row.addWidget(self._proto_combo)
        root.addLayout(proto_row)

    def _connect_camera(self) -> None:
        try:
            cm = self._bridge.camera_manager
            cm.frame_ready.connect(self._on_frame)
        except Exception:
            pass

    def _on_frame(self, frame) -> None:
        now = time.monotonic()
        if now - self._last_frame_mono < (1.0 / 60.0):
            return
        self._last_frame_mono = now
        try:
            qimg = numpy_to_qimage(frame)
            self._video.set_frame(qimg)
        except Exception:
            pass

    def _on_start(self) -> None:
        self._running = True
        self._elapsed_sec = 0
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._timer.start(1000)

    def _on_stop(self) -> None:
        self._running = False
        self._timer.stop()
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)

    def _tick(self) -> None:
        self._elapsed_sec += 1
        m = self._elapsed_sec // 60
        s = self._elapsed_sec % 60
        self._lbl_time.setText(f"{m:02d}:{s:02d}")

    def load_protocols(self, protocols: list[dict]) -> None:
        self._proto_combo.clear()
        for p in protocols:
            self._proto_combo.addItem(f"Protocol: {p.get('name', 'Unknown')}")
        if self._proto_combo.count() == 0:
            self._proto_combo.addItem("Protocol: Startle Response")


# ── Right panel: Assay Select ─────────────────────────────────────────────────

class AssayPanel(QWidget):
    """Right panel for assay / view selection and system status."""

    navigate_to = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AssayPanel")
        self.setFixedWidth(200)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 14, 12, 14)
        root.setSpacing(10)

        # Title
        root.addWidget(_section_title("Assay Select"))

        # TOP / SIDE view radios
        view_group = QButtonGroup(self)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        self._rb_top = QRadioButton("TOP")
        self._rb_top.setObjectName("ViewRadio")
        self._rb_top.setChecked(True)
        self._lbl_top_badge = QLabel("TOP")
        self._lbl_top_badge.setObjectName("ViewBadge")
        self._lbl_top_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_top_badge.setFixedSize(40, 22)
        top_row.addWidget(self._rb_top)
        top_row.addWidget(self._lbl_top_badge)
        top_row.addStretch()
        root.addLayout(top_row)
        view_group.addButton(self._rb_top)

        self._rb_side = QRadioButton("SIDE")
        self._rb_side.setObjectName("ViewRadio")
        view_group.addButton(self._rb_side)
        root.addWidget(self._rb_side)

        # System status
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self._status_dot = QLabel("●")
        self._status_dot.setObjectName("StatusDotGreen")
        self._status_lbl = QLabel("System Ready: YES")
        self._status_lbl.setObjectName("StatusLabel")
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_lbl)
        status_row.addStretch()
        root.addLayout(status_row)

        root.addWidget(_separator())

        root.addWidget(_section_title("Assay Select"))

        # Assay rows
        for label, assay_id in [
            ("Startle Response ›", "startle"),
            ("Light/Dark Test ›", "light_dark"),
            ("Load Assay ›", "load"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("AssayRowBtn")
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, a=assay_id: self._on_assay(a))
            root.addWidget(btn)

        root.addStretch(1)

        # Create New / Protocol Builder
        self._btn_create = QPushButton("Create New → Protocol Builder")
        self._btn_create.setObjectName("CreateProtocolBtn")
        self._btn_create.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_create.clicked.connect(lambda: self.navigate_to.emit("protocol_builder"))
        root.addWidget(self._btn_create)

    def _on_assay(self, assay_id: str) -> None:
        pass  # future: load preset protocol for assay

    def set_system_ready(self, ready: bool) -> None:
        self._status_dot.setObjectName("StatusDotGreen" if ready else "StatusDotRed")
        self._status_lbl.setText(f"System Ready: {'YES' if ready else 'NO'}")
        # Force style refresh
        self._status_dot.style().unpolish(self._status_dot)
        self._status_dot.style().polish(self._status_dot)


# ── Bottom status bar ─────────────────────────────────────────────────────────

class AdultStatusBar(QWidget):
    run_protocol = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AdultStatusBar")
        self.setFixedHeight(46)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 6, 16, 6)
        lay.setSpacing(12)

        self._msg_lbl = QLabel("All devices connected and ready. You're good to begin.")
        self._msg_lbl.setObjectName("StatusBarMsg")

        self._btn_run = QPushButton("▶  Run Protocol")
        self._btn_run.setObjectName("RunProtocolBtn")
        self._btn_run.setFixedHeight(32)
        self._btn_run.clicked.connect(self.run_protocol.emit)

        lay.addWidget(self._msg_lbl, 1)
        lay.addWidget(self._btn_run)

    def set_message(self, msg: str) -> None:
        self._msg_lbl.setText(msg)


# ── Main AdultPage ────────────────────────────────────────────────────────────

class AdultPage(QWidget):
    """Full adult experiment screen — three columns + status bar."""

    navigate_to = pyqtSignal(str)

    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self.setObjectName("AdultPage")
        self._build()
        self._load_protocols()
        self._start_system_check()

    # ---- build ----

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Body row
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # LEFT panel (scrollable)
        self._stim_panel = StimulusControlPanel(self._bridge)
        left_scroll = QScrollArea()
        left_scroll.setObjectName("LeftScrollArea")
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setWidget(self._stim_panel)
        left_scroll.setFixedWidth(240)
        body.addWidget(left_scroll)

        # Left divider
        left_div = QFrame()
        left_div.setFrameShape(QFrame.Shape.VLine)
        left_div.setObjectName("PanelDivider")
        body.addWidget(left_div)

        # CENTER panel
        self._center = CenterPanel(self._bridge)
        center_wrap = QWidget()
        center_wrap.setObjectName("CenterWrap")
        cw_lay = QVBoxLayout(center_wrap)
        cw_lay.setContentsMargins(16, 14, 16, 10)
        cw_lay.setSpacing(0)
        cw_lay.addWidget(self._center)
        body.addWidget(center_wrap, 1)

        # Right divider
        right_div = QFrame()
        right_div.setFrameShape(QFrame.Shape.VLine)
        right_div.setObjectName("PanelDivider")
        body.addWidget(right_div)

        # RIGHT panel
        self._assay_panel = AssayPanel()
        self._assay_panel.navigate_to.connect(self.navigate_to)
        body.addWidget(self._assay_panel)

        root.addLayout(body, 1)

        # Bottom status bar
        self._status_bar = AdultStatusBar()
        self._status_bar.run_protocol.connect(self._on_run_protocol)
        status_sep = _separator()
        root.addWidget(status_sep)
        root.addWidget(self._status_bar)

    # ---- helpers ----

    def _load_protocols(self) -> None:
        try:
            from db import database as db
            protocols = db.list_protocols()
            self._center.load_protocols(protocols)
        except Exception:
            pass

    def _start_system_check(self) -> None:
        """Periodic system readiness check."""
        self._sys_timer = QTimer(self)
        self._sys_timer.timeout.connect(self._check_system)
        self._sys_timer.start(2000)
        self._check_system()

    def _check_system(self) -> None:
        arduino_ok = False
        camera_ok = False
        try:
            arduino_ok = self._bridge._arduino.is_connected()
        except Exception:
            pass
        try:
            camera_ok = self._bridge.camera_manager.is_streaming()
        except Exception:
            pass

        if arduino_ok and camera_ok:
            self._status_bar.set_message(
                "All devices connected and ready. You're good to begin."
            )
            self._assay_panel.set_system_ready(True)
        elif camera_ok:
            self._status_bar.set_message(
                "Camera ready. Arduino not connected — stimulus controls disabled."
            )
            self._assay_panel.set_system_ready(False)
        else:
            self._status_bar.set_message(
                "No camera detected. Connect hardware to begin."
            )
            self._assay_panel.set_system_ready(False)

    def _on_run_protocol(self) -> None:
        self._center._on_start()
