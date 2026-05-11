"""Adult experiment screen — main experiment page for Adult mode.

Three-column layout:
  Left  (~240px)  — Stimulus Control panel (scrollable)
  Center (expand) — Camera selector + Video feed + FPS + controls + timeline
  Right (~200px)  — Assay selection + protocol + system status
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


# ── Stimulus section builder ──────────────────────────────────────────────────

class _StimulusSection(QWidget):
    """
    Reusable stimulus section:
      - Section header
      - ON / OFF buttons side by side
      - Intensity slider (0-100 %)
      - Continuous / Pulse mode radios
      - Pulse: Delay (ms) + Duration (ms) spinboxes
    Optional extra_widgets_fn inserts additional rows before the intensity slider.
    """

    def __init__(
        self,
        title: str,
        on_callback,
        off_callback,
        parent=None,
        extra_widgets_fn=None,
        show_intensity: bool = True,
    ) -> None:
        super().__init__(parent)
        self._on_callback = on_callback
        self._off_callback = off_callback

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 4)
        root.setSpacing(5)

        # Header
        hdr = _label(title)
        font = hdr.font()
        font.setBold(True)
        hdr.setFont(font)
        root.addWidget(hdr)

        # ON / OFF row
        btn_row = QHBoxLayout()
        self._btn_on = QPushButton("ON")
        self._btn_on.setObjectName("StimulusOnBtn")
        self._btn_on.setFixedHeight(28)
        self._btn_off = QPushButton("OFF")
        self._btn_off.setObjectName("StimulusOffBtn")
        self._btn_off.setFixedHeight(28)
        self._btn_on.clicked.connect(self._handle_on)
        self._btn_off.clicked.connect(self._handle_off)
        btn_row.addWidget(self._btn_on)
        btn_row.addWidget(self._btn_off)
        root.addLayout(btn_row)

        # Optional extra widgets (e.g. R/G/B sliders)
        if extra_widgets_fn:
            extra_widgets_fn(root)

        # Intensity slider
        self._intensity_widget = QWidget()
        int_lay = QVBoxLayout(self._intensity_widget)
        int_lay.setContentsMargins(0, 0, 0, 0)
        int_lay.setSpacing(3)
        int_row = QHBoxLayout()
        int_row.addWidget(_label("Intensity"))
        self._intensity_lbl = QLabel("50%")
        self._intensity_lbl.setObjectName("ValueLabel")
        int_row.addStretch()
        int_row.addWidget(self._intensity_lbl)
        int_lay.addLayout(int_row)
        self._intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self._intensity_slider.setObjectName("StimSlider")
        self._intensity_slider.setRange(0, 100)
        self._intensity_slider.setValue(50)
        self._intensity_slider.valueChanged.connect(
            lambda v: self._intensity_lbl.setText(f"{v}%")
        )
        int_lay.addWidget(self._intensity_slider)
        self._intensity_widget.setVisible(show_intensity)
        root.addWidget(self._intensity_widget)

        # Mode row
        mode_row = QHBoxLayout()
        mode_row.addWidget(_label("Mode"))
        self._rb_continuous = QRadioButton("Continuous")
        self._rb_continuous.setChecked(True)
        self._rb_pulse = QRadioButton("Pulse")
        self._rb_continuous.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self._rb_continuous)
        mode_row.addWidget(self._rb_pulse)
        mode_row.addStretch()
        root.addLayout(mode_row)

        # Pulse params (hidden by default)
        self._pulse_widget = QWidget()
        pulse_lay = QHBoxLayout(self._pulse_widget)
        pulse_lay.setContentsMargins(0, 0, 0, 0)
        pulse_lay.setSpacing(4)
        pulse_lay.addWidget(_label("Delay"))
        self._spin_delay = QSpinBox()
        self._spin_delay.setRange(0, 99999)
        self._spin_delay.setValue(100)
        self._spin_delay.setSuffix(" ms")
        pulse_lay.addWidget(self._spin_delay)
        pulse_lay.addWidget(_label("Dur"))
        self._spin_duration = QSpinBox()
        self._spin_duration.setRange(1, 99999)
        self._spin_duration.setValue(500)
        self._spin_duration.setSuffix(" ms")
        pulse_lay.addWidget(self._spin_duration)
        self._pulse_widget.setVisible(False)
        root.addWidget(self._pulse_widget)

    # ---- internal ----

    def _on_mode_changed(self, continuous: bool) -> None:
        self._pulse_widget.setVisible(not continuous)

    def _handle_on(self) -> None:
        try:
            if self._rb_pulse.isChecked():
                self._on_callback(
                    intensity=self._intensity_slider.value(),
                    pulse=True,
                    delay_ms=self._spin_delay.value(),
                    duration_ms=self._spin_duration.value(),
                )
            else:
                self._on_callback(intensity=self._intensity_slider.value())
        except Exception:
            pass

    def _handle_off(self) -> None:
        try:
            self._off_callback()
        except Exception:
            pass

    # ---- public ----

    def intensity(self) -> int:
        return self._intensity_slider.value()


# ── Timeline widget ───────────────────────────────────────────────────────────

class TimelineBar(QWidget):
    """Paints the experiment timeline with coloured segment bars."""

    _PHASES = ["Baseline", "Light Pulse", "Recovery"]
    _PHASE_WEIGHTS = [0.25, 0.35, 0.40]

    _ROWS = [
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

        p.fillRect(0, 0, W, H, QColor("#f8f8ff"))

        # Phase headers
        x = bar_left
        for i, (ph, weight) in enumerate(zip(self._PHASES, self._PHASE_WEIGHTS)):
            pw = int(bar_w * weight)
            bg = QColor("#e8e8f8") if i % 2 == 0 else QColor("#f0f0ff")
            p.fillRect(x, 0, pw, header_h - 2, bg)
            p.setPen(QColor("#5c5c8a"))
            p.setFont(QFont("", 8, QFont.Weight.Bold))
            p.drawText(x, 0, pw, header_h - 2, Qt.AlignmentFlag.AlignCenter, ph)
            x += pw

        # Row bars
        for ri, (row_label, segments) in enumerate(self._ROWS):
            y = header_h + ri * (row_h + gap)

            p.setPen(QColor("#333366"))
            p.setFont(QFont("", 8))
            p.drawText(
                0, y, row_label_w, row_h,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                row_label + "  "
            )

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
                    p.drawText(
                        int(rect.x()), int(rect.y()),
                        int(rect.width()), int(rect.height()),
                        Qt.AlignmentFlag.AlignCenter, seg_label
                    )
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
    """Left scrollable panel with vibration, buzzer, RGB LED and heating controls."""

    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self.setObjectName("StimulusControlPanel")
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 14, 12, 14)
        root.setSpacing(8)

        title = _section_title("Stimulus Control")
        title.setObjectName("PanelTitle")
        root.addWidget(title)

        root.addWidget(_separator())

        # ---- Vibration ----
        self._vib = _StimulusSection(
            "Vibration",
            on_callback=self._vib_on,
            off_callback=self._vib_off,
        )
        root.addWidget(self._vib)
        root.addWidget(_separator())

        # ---- Buzzer ----
        self._buzz = _StimulusSection(
            "Buzzer",
            on_callback=self._buzz_on,
            off_callback=self._buzz_off,
        )
        root.addWidget(self._buzz)
        root.addWidget(_separator())

        # ---- RGB LED ----
        # R/G/B sliders stored at panel level so callbacks can read them
        self._rgb_r_lbl = QLabel("R: 128")
        self._rgb_r_lbl.setObjectName("ValueLabel")
        self._rgb_g_lbl = QLabel("G: 128")
        self._rgb_g_lbl.setObjectName("ValueLabel")
        self._rgb_b_lbl = QLabel("B: 128")
        self._rgb_b_lbl.setObjectName("ValueLabel")

        self._rgb_r_slider = QSlider(Qt.Orientation.Horizontal)
        self._rgb_r_slider.setObjectName("StimSlider")
        self._rgb_r_slider.setRange(0, 255)
        self._rgb_r_slider.setValue(128)
        self._rgb_g_slider = QSlider(Qt.Orientation.Horizontal)
        self._rgb_g_slider.setObjectName("StimSlider")
        self._rgb_g_slider.setRange(0, 255)
        self._rgb_g_slider.setValue(128)
        self._rgb_b_slider = QSlider(Qt.Orientation.Horizontal)
        self._rgb_b_slider.setObjectName("StimSlider")
        self._rgb_b_slider.setRange(0, 255)
        self._rgb_b_slider.setValue(128)

        self._rgb_r_slider.valueChanged.connect(
            lambda v: self._rgb_r_lbl.setText(f"R: {v}"))
        self._rgb_g_slider.valueChanged.connect(
            lambda v: self._rgb_g_lbl.setText(f"G: {v}"))
        self._rgb_b_slider.valueChanged.connect(
            lambda v: self._rgb_b_lbl.setText(f"B: {v}"))

        def _rgb_extra(lay: QVBoxLayout) -> None:
            for lbl, slider in [
                (self._rgb_r_lbl, self._rgb_r_slider),
                (self._rgb_g_lbl, self._rgb_g_slider),
                (self._rgb_b_lbl, self._rgb_b_slider),
            ]:
                row = QHBoxLayout()
                row.addWidget(lbl)
                row.addWidget(slider)
                lay.addLayout(row)

        self._rgb = _StimulusSection(
            "RGB LED",
            on_callback=self._rgb_on,
            off_callback=self._rgb_off,
            extra_widgets_fn=_rgb_extra,
            show_intensity=False,  # R/G/B sliders replace generic intensity
        )
        root.addWidget(self._rgb)
        root.addWidget(_separator())

        # ---- Heating (D7) ----
        self._heat = _StimulusSection(
            "Heating",
            on_callback=self._heat_on,
            off_callback=self._heat_off,
        )
        root.addWidget(self._heat)

        root.addStretch(1)

    # ---- Vibration callbacks ----

    def _vib_on(self, intensity: int = 50, pulse: bool = False,
                delay_ms: int = 0, duration_ms: int = 500) -> None:
        arduino = self._bridge._arduino
        if pulse:
            arduino.vibrate_timed(duration_ms)
        else:
            arduino.vibrate_on()

    def _vib_off(self) -> None:
        self._bridge._arduino.vibrate_off()

    # ---- Buzzer callbacks ----

    def _buzz_on(self, intensity: int = 50, pulse: bool = False,
                 delay_ms: int = 0, duration_ms: int = 500) -> None:
        self._bridge._arduino.write_command("BUZZER_ON")

    def _buzz_off(self) -> None:
        self._bridge._arduino.write_command("BUZZER_OFF")

    # ---- RGB callbacks ----

    def _rgb_on(self, intensity: int = 50, pulse: bool = False,
                delay_ms: int = 0, duration_ms: int = 500) -> None:
        r = self._rgb_r_slider.value()
        g = self._rgb_g_slider.value()
        b = self._rgb_b_slider.value()
        self._bridge._arduino.rgb_set(r, g, b)

    def _rgb_off(self) -> None:
        self._bridge._arduino.rgb_set(0, 0, 0)

    # ---- Heating callbacks ----

    def _heat_on(self, intensity: int = 50, pulse: bool = False,
                 delay_ms: int = 0, duration_ms: int = 500) -> None:
        pwm_val = int(intensity / 100.0 * 255)
        self._bridge._arduino.write_command(f"HEAT {pwm_val}")

    def _heat_off(self) -> None:
        self._bridge._arduino.write_command("HEAT 0")


# ── Center: video + controls + timeline ───────────────────────────────────────

class CenterPanel(QWidget):
    """Center panel: camera selector, video feed, FPS, transport controls and timeline."""

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

        # FPS poll timer (500 ms)
        self._fps_timer = QTimer(self)
        self._fps_timer.timeout.connect(self._update_fps)
        self._fps_timer.start(500)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # Camera selector row
        cam_row = QHBoxLayout()
        cam_row.setSpacing(8)
        cam_row.addWidget(_label("Camera:"))
        self._cam_combo = QComboBox()
        self._cam_combo.setObjectName("CameraCombo")
        self._cam_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._cam_combo.currentTextChanged.connect(self._on_camera_changed)
        cam_row.addWidget(self._cam_combo)
        root.addLayout(cam_row)

        # Video panel
        self._video = VideoPanel()
        self._video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._video, 3)

        # FPS label (next to video, below it)
        fps_row = QHBoxLayout()
        self._fps_lbl = QLabel("FPS: --")
        self._fps_lbl.setObjectName("FpsLabel")
        fps_row.addWidget(self._fps_lbl)
        fps_row.addStretch()
        root.addLayout(fps_row)

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

        self._lbl_duration = _label("Duration:")
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

        ctrl_row2.addWidget(self._rb_manual)
        ctrl_row2.addWidget(self._rb_protocol)
        ctrl_row2.addStretch()
        root.addLayout(ctrl_row2)

        # Timeline section
        tl_header = QHBoxLayout()
        tl_lbl = _section_title("Timeline")
        tl_header.addWidget(tl_lbl)
        tl_header.addStretch()
        root.addLayout(tl_header)

        self._timeline = TimelineBar()
        root.addWidget(self._timeline)

    def _populate_cameras(self) -> None:
        try:
            cams = self._bridge.camera_manager.list_cameras()
            self._cam_combo.blockSignals(True)
            self._cam_combo.clear()
            for cam in cams:
                self._cam_combo.addItem(str(cam))
            self._cam_combo.blockSignals(False)
        except Exception:
            pass

    def _connect_camera(self) -> None:
        self._populate_cameras()
        try:
            cm = self._bridge.camera_manager
            cm.frame_ready.connect(self._on_frame)
        except Exception:
            pass

    def _on_camera_changed(self, cam_id: str) -> None:
        try:
            if cam_id:
                self._bridge.camera_manager.set_active_camera(cam_id)
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

    def _update_fps(self) -> None:
        try:
            fps = self._bridge.get_current_fps()
            self._fps_lbl.setText(f"FPS: {fps:.1f}")
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


# ── Right panel: Assay Select ─────────────────────────────────────────────────

class AssayPanel(QWidget):
    """Right panel for assay / view selection, protocols and system status."""

    navigate_to = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AssayPanel")
        self.setFixedWidth(200)
        self._bridge_ref = None
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 14, 12, 14)
        root.setSpacing(10)

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

        root.addWidget(_separator())

        # Protocol section
        root.addWidget(_section_title("Protocol"))

        self._proto_combo = QComboBox()
        self._proto_combo.setObjectName("ProtocolCombo")
        self._proto_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._proto_combo.addItem("(no protocols)")
        root.addWidget(self._proto_combo)

        btn_start_proto = QPushButton("Start Protocol")
        btn_start_proto.setObjectName("StartBtn")
        btn_start_proto.clicked.connect(self._on_start_protocol)
        root.addWidget(btn_start_proto)

        root.addStretch(1)

        self._btn_create = QPushButton("Create New → Protocol Builder")
        self._btn_create.setObjectName("CreateProtocolBtn")
        self._btn_create.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_create.clicked.connect(lambda: self.navigate_to.emit("protocol_builder"))
        root.addWidget(self._btn_create)

    def _on_assay(self, assay_id: str) -> None:
        pass  # future: load preset protocol for assay

    def _on_start_protocol(self) -> None:
        try:
            proto_id = self._proto_combo.currentData()
            if proto_id is not None and self._bridge_ref is not None:
                self._bridge_ref.run_protocol(proto_id)
        except Exception:
            pass

    def load_protocols(self, protocols: list[dict]) -> None:
        self._proto_combo.clear()
        if protocols:
            for p in protocols:
                self._proto_combo.addItem(
                    p.get("name", "Unnamed"), userData=p.get("id")
                )
        else:
            self._proto_combo.addItem("(no protocols)")

    def set_system_ready(self, ready: bool) -> None:
        self._status_dot.setObjectName("StatusDotGreen" if ready else "StatusDotRed")
        self._status_lbl.setText(f"System Ready: {'YES' if ready else 'NO'}")
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

        right_div = QFrame()
        right_div.setFrameShape(QFrame.Shape.VLine)
        right_div.setObjectName("PanelDivider")
        body.addWidget(right_div)

        # RIGHT panel
        self._assay_panel = AssayPanel()
        self._assay_panel._bridge_ref = self._bridge
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
            self._assay_panel.load_protocols(protocols)
        except Exception:
            pass

    def _start_system_check(self) -> None:
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
