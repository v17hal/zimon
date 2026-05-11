"""Larval mode page — Well/ROI grid overlay on live video.

Three-column layout:
  Left  (~240px) — Stimulus Control (scrollable)
  Center (expand) — Live video (max 300px tall) + Well plate overlay + controls
  Right (~210px)  — Well/ROI config + protocol + assay select
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
    QGroupBox,
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setObjectName("SectionSeparator")
    return line


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("SectionLabel")
    font = lbl.font()
    font.setBold(True)
    lbl.setFont(font)
    return lbl


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
        self._selected: set[tuple[int, int]] = set()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMinimumSize(100, 80)

    def set_plate(self, label: str) -> None:
        rows, cols = self.PLATES.get(label, (4, 6))
        self._rows = rows
        self._cols = cols
        self._selected.clear()
        self.update()

    def mousePressEvent(self, event) -> None:
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

                if selected:
                    p.setBrush(QBrush(QColor(99, 102, 241, 100)))
                else:
                    p.setBrush(QBrush(QColor(255, 255, 255, 30)))

                pad = 2
                p.setPen(QPen(QColor(255, 255, 255, 160), 1.2))
                p.drawEllipse(QRectF(x + pad, y + pad, cw - pad * 2, ch - pad * 2))

                p.setPen(QPen(QColor(255, 255, 255, 200)))
                font = QFont("Segoe UI", max(6, int(min(cw, ch) * 0.22)))
                p.setFont(font)
                p.drawText(
                    QRectF(x, y, cw, ch),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{chr(ord('A') + row)}{col + 1}"
                )
        p.end()


# ── Stimulus section builder ───────────────────────────────────────────────────

class _StimulusSection(QWidget):
    """
    Generic stimulus section with:
      - Section header
      - ON / OFF buttons
      - Intensity slider (0-100 %)
      - Continuous / Pulse mode radios
      - Delay + Duration spinboxes (visible in Pulse mode only)
    """

    def __init__(
        self,
        title: str,
        on_callback,
        off_callback,
        parent=None,
        extra_widgets_fn=None,
    ) -> None:
        super().__init__(parent)
        self._on_callback = on_callback
        self._off_callback = off_callback

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 4)
        root.setSpacing(5)

        # Header
        hdr = _section_label(title)
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

        # Optional extra widgets (e.g. RGB sliders)
        if extra_widgets_fn:
            extra_widgets_fn(root)

        # Intensity slider
        int_row = QHBoxLayout()
        int_row.addWidget(QLabel("Intensity"))
        self._intensity_lbl = QLabel("50%")
        self._intensity_lbl.setObjectName("ValueLabel")
        int_row.addStretch()
        int_row.addWidget(self._intensity_lbl)
        root.addLayout(int_row)

        self._intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self._intensity_slider.setRange(0, 100)
        self._intensity_slider.setValue(50)
        self._intensity_slider.valueChanged.connect(
            lambda v: self._intensity_lbl.setText(f"{v}%")
        )
        root.addWidget(self._intensity_slider)

        # Mode row
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode"))
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
        pulse_lay.setSpacing(6)
        pulse_lay.addWidget(QLabel("Delay"))
        self._spin_delay = QSpinBox()
        self._spin_delay.setRange(0, 99999)
        self._spin_delay.setValue(100)
        self._spin_delay.setSuffix(" ms")
        pulse_lay.addWidget(self._spin_delay)
        pulse_lay.addWidget(QLabel("Duration"))
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
        root.setContentsMargins(12, 14, 12, 14)
        root.setSpacing(8)

        title = QLabel("Stimulus Control")
        title.setObjectName("PageTitle")
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
        # RGB has R/G/B sliders instead of a single intensity slider
        self._rgb_r_lbl = QLabel("R: 128")
        self._rgb_r_lbl.setObjectName("ValueLabel")
        self._rgb_g_lbl = QLabel("G: 128")
        self._rgb_g_lbl.setObjectName("ValueLabel")
        self._rgb_b_lbl = QLabel("B: 128")
        self._rgb_b_lbl.setObjectName("ValueLabel")
        self._rgb_r_slider = QSlider(Qt.Orientation.Horizontal)
        self._rgb_r_slider.setRange(0, 255)
        self._rgb_r_slider.setValue(128)
        self._rgb_g_slider = QSlider(Qt.Orientation.Horizontal)
        self._rgb_g_slider.setRange(0, 255)
        self._rgb_g_slider.setValue(128)
        self._rgb_b_slider = QSlider(Qt.Orientation.Horizontal)
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
        )
        # Hide the generic intensity slider for RGB (use R/G/B sliders instead)
        self._rgb._intensity_slider.hide()
        self._rgb._intensity_lbl.hide()
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
        self.setWidget(inner)

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


# ── Right ROI config panel ────────────────────────────────────────────────────

class _LarvalROIPanel(QWidget):

    def __init__(self, bridge, overlay: WellPlateOverlay, navigate_to, parent=None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._overlay = overlay
        self._navigate_to = navigate_to
        self.setObjectName("AssayPanel")
        self.setFixedWidth(210)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 16, 14, 16)
        root.setSpacing(12)

        title = QLabel("Well / ROI")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        plate_lbl = _section_label("Plate Format")
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

        root.addWidget(_separator())

        assay_lbl = _section_label("Assay Select")
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

        root.addWidget(_separator())

        for label in ["Escape Response ›", "Light/Dark Test ›", "Load Assay ›"]:
            btn = QPushButton(label)
            btn.setObjectName("AssayRow")
            root.addWidget(btn)

        root.addWidget(_separator())

        # Protocol section
        proto_lbl = _section_label("Protocol")
        root.addWidget(proto_lbl)

        self._proto_combo = QComboBox()
        self._proto_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._proto_combo.addItem("(no protocols)")
        root.addWidget(self._proto_combo)

        btn_start_proto = QPushButton("Start Protocol")
        btn_start_proto.setObjectName("StartBtn")
        btn_start_proto.clicked.connect(self._on_start_protocol)
        root.addWidget(btn_start_proto)

        btn_proto = QPushButton("Create New → Protocol Builder")
        btn_proto.setObjectName("SmallButton")
        btn_proto.clicked.connect(lambda: navigate_to("protocol_builder"))
        root.addWidget(btn_proto)

        root.addStretch(1)

        # Load protocols and trigger initial plate setup
        self._load_protocols()
        self._on_plate_changed(self._plate_combo.currentText())

    def _load_protocols(self) -> None:
        try:
            from db.database import list_protocols
            protocols = list_protocols()
            self._proto_combo.clear()
            if protocols:
                for p in protocols:
                    self._proto_combo.addItem(p.get("name", "Unnamed"), userData=p.get("id"))
            else:
                self._proto_combo.addItem("(no protocols)")
        except Exception:
            pass

    def _on_start_protocol(self) -> None:
        try:
            proto_id = self._proto_combo.currentData()
            if proto_id is not None:
                self._bridge.run_protocol(proto_id)
        except Exception:
            pass

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
        video_stack.setMaximumHeight(300)
        stack_lay = QVBoxLayout(video_stack)
        stack_lay.setContentsMargins(0, 0, 0, 0)

        self._video = VideoPanel()
        self._video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        stack_lay.addWidget(self._video)

        self._overlay = WellPlateOverlay(video_stack)
        self._overlay.setGeometry(0, 0, 100, 100)
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        video_stack.resizeEvent = self._on_video_resize
        root.addWidget(video_stack)  # no stretch — max height caps it

        # FPS label next to video
        fps_row = QHBoxLayout()
        self._fps_lbl = QLabel("FPS: --")
        self._fps_lbl.setObjectName("FpsLabel")
        fps_row.addWidget(self._fps_lbl)
        fps_row.addStretch()
        root.addLayout(fps_row)

        # Wellplate grid (standalone, max 320px wide)
        plate_lbl = _section_label("Well Plate Grid")
        root.addWidget(plate_lbl)

        plate_wrapper = QHBoxLayout()
        self._plate_grid = WellPlateOverlay()
        self._plate_grid.setObjectName("WellPlateGrid")
        self._plate_grid.setMaximumWidth(320)
        self._plate_grid.setMinimumHeight(100)
        self._plate_grid.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        plate_wrapper.addWidget(self._plate_grid)
        plate_wrapper.addStretch()
        root.addLayout(plate_wrapper)

        # Transport controls
        ctrl = QHBoxLayout()
        self._btn_start = QPushButton("▶  Start")
        self._btn_start.setObjectName("StartBtn")
        self._btn_start.setFixedHeight(34)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_stop = QPushButton("■  Stop")
        self._btn_stop.setObjectName("StopBtn")
        self._btn_stop.setFixedHeight(34)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)
        self._dur_lbl = QLabel("00:00")
        self._dur_lbl.setObjectName("TimeDisplay")
        ctrl.addWidget(self._btn_start)
        ctrl.addWidget(self._btn_stop)
        ctrl.addStretch(1)
        ctrl.addWidget(QLabel("Duration:"))
        ctrl.addWidget(self._dur_lbl)
        root.addLayout(ctrl)

        root.addStretch(1)

        # Elapsed timer
        self._run_timer = QTimer(self)
        self._run_timer.timeout.connect(self._tick)
        self._elapsed = 0

        # FPS poll timer (500 ms)
        self._fps_timer = QTimer(self)
        self._fps_timer.timeout.connect(self._update_fps)
        self._fps_timer.start(500)

        # Connect camera frames — use role-assigned camera for larval
        self._connect_camera()

    def _connect_camera(self) -> None:
        try:
            from db.database import get_camera_for_role
            cam_id = get_camera_for_role("larval_machine_vision")
            if cam_id:
                self._bridge.camera_manager.set_active_camera(cam_id)
            else:
                # Fallback: first available camera
                cams = self._bridge.camera_manager.list_cameras()
                if cams:
                    self._bridge.camera_manager.set_active_camera(cams[0])
        except Exception:
            pass
        try:
            self._bridge.camera_manager.frame_ready.connect(self._on_frame)
        except Exception:
            pass

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

    def _update_fps(self) -> None:
        try:
            fps = self._bridge.get_current_fps()
            self._fps_lbl.setText(f"FPS: {fps:.1f}")
        except Exception:
            pass

    def _on_start(self) -> None:
        self._elapsed = 0
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._run_timer.start(1000)

    def _on_stop(self) -> None:
        self._run_timer.stop()
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)

    def _tick(self) -> None:
        self._elapsed += 1
        m, s = divmod(self._elapsed, 60)
        self._dur_lbl.setText(f"{m:02d}:{s:02d}")

    def get_overlay(self) -> WellPlateOverlay:
        """Return the video-stack overlay (used by ROI panel)."""
        return self._overlay

    def get_plate_grid(self) -> WellPlateOverlay:
        """Return the standalone plate grid widget."""
        return self._plate_grid


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

        left_div = QFrame()
        left_div.setFrameShape(QFrame.Shape.VLine)
        left_div.setObjectName("PanelDivider")
        root.addWidget(left_div)

        # Center video + overlay
        self._center = _LarvalCenterPanel(self._bridge)
        center_wrap = QWidget()
        center_wrap.setObjectName("CenterWrap")
        cw_lay = QVBoxLayout(center_wrap)
        cw_lay.setContentsMargins(14, 12, 14, 10)
        cw_lay.setSpacing(0)
        cw_lay.addWidget(self._center)
        root.addWidget(center_wrap, 1)

        right_div = QFrame()
        right_div.setFrameShape(QFrame.Shape.VLine)
        right_div.setObjectName("PanelDivider")
        root.addWidget(right_div)

        # Right ROI panel — binds both plate grid and overlay
        self._roi = _LarvalROIPanel(
            self._bridge,
            self._center.get_overlay(),
            navigate_to=self.navigate_to.emit,
        )
        # Mirror plate changes to standalone grid too
        orig_plate_changed = self._roi._on_plate_changed

        def _mirror_plate(label: str) -> None:
            orig_plate_changed(label)
            self._center.get_plate_grid().set_plate(label)

        self._roi._plate_combo.currentTextChanged.disconnect(self._roi._on_plate_changed)
        self._roi._plate_combo.currentTextChanged.connect(_mirror_plate)
        _mirror_plate(self._roi._plate_combo.currentText())

        root.addWidget(self._roi)
