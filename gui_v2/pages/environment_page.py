"""Environment page — Camera Devices + Lighting Controls.

Sections:
  A. Camera Devices: per-camera cards with preview, role assignment, save.
  B. Lighting Controls: IR and LED intensity sliders with ON/OFF toggles.
"""

from __future__ import annotations

import numpy as np

import db.database as db
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)


# Role values stored in DB (internal keys)
_ROLE_OPTIONS = [
    ("Unassigned",              "unassigned"),
    ("Machine Vision (Larval)", "larval_machine_vision"),
    ("Top Webcam (Adult)",      "adult_top"),
    ("Side Webcam (Adult)",     "adult_side"),
]
_LABEL_TO_ROLE = {lbl: key for lbl, key in _ROLE_OPTIONS}
_ROLE_TO_LABEL = {key: lbl for lbl, key in _ROLE_OPTIONS}


class _MiniPreview(QLabel):
    """Small 200×150 camera preview label."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(200, 150)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName("MiniPreview")
        self.setText("No signal")
        self.setStyleSheet(
            "QLabel#MiniPreview { background:#111; color:#aaa; border:1px solid #555; "
            "border-radius:4px; font-size:11px; }"
        )

    def update_frame(self, frame: np.ndarray) -> None:
        """Accepts a BGR numpy frame and displays it scaled."""
        try:
            import cv2
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            pix = img.scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            from PyQt6.QtGui import QPixmap
            self.setPixmap(QPixmap.fromImage(pix))
        except Exception:
            pass


class _CameraCard(QFrame):
    """Card for a single detected camera with preview + role assignment."""

    def __init__(self, camera_id: str, bridge, saved_label: str = "",
                 saved_role: str = "unassigned", parent=None) -> None:
        super().__init__(parent)
        self._camera_id = camera_id
        self._bridge = bridge
        self._previewing = False
        self.setObjectName("DeviceCard")
        self.setStyleSheet(
            "QFrame#DeviceCard { background:#ffffff; border:1px solid #dde; "
            "border-radius:8px; padding:4px; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ── Header row ──────────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setObjectName("DotGray")
        self._dot.setFixedWidth(18)
        hdr.addWidget(self._dot)

        name_lbl = QLabel(camera_id)
        name_lbl.setObjectName("DeviceName")
        hdr.addWidget(name_lbl, 1)

        self._status_badge = QLabel("Idle")
        self._status_badge.setObjectName("BadgeGray")
        self._status_badge.setFixedWidth(80)
        self._status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.addWidget(self._status_badge)

        root.addLayout(hdr)

        # ── Body row: preview + controls ────────────────────────────────
        body = QHBoxLayout()
        body.setSpacing(12)

        self._preview = _MiniPreview()
        body.addWidget(self._preview)

        controls = QVBoxLayout()
        controls.setSpacing(6)

        role_row = QHBoxLayout()
        role_lbl = QLabel("Role:")
        role_lbl.setObjectName("DeviceSub")
        role_row.addWidget(role_lbl)
        self._role_combo = QComboBox()
        for lbl, _ in _ROLE_OPTIONS:
            self._role_combo.addItem(lbl)
        # Set saved role
        saved_display = _ROLE_TO_LABEL.get(saved_role, "Unassigned")
        idx = self._role_combo.findText(saved_display)
        if idx >= 0:
            self._role_combo.setCurrentIndex(idx)
        role_row.addWidget(self._role_combo, 1)
        controls.addLayout(role_row)

        label_row = QHBoxLayout()
        label_lbl = QLabel("Label:")
        label_lbl.setObjectName("DeviceSub")
        label_row.addWidget(label_lbl)
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("e.g. Tank 1 camera")
        self._label_edit.setText(saved_label if saved_label != "unassigned" else "")
        label_row.addWidget(self._label_edit, 1)
        controls.addLayout(label_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._save_btn = QPushButton("Save Assignment")
        self._save_btn.setObjectName("SmallButton")
        self._save_btn.clicked.connect(self._save_assignment)
        btn_row.addWidget(self._save_btn)

        self._preview_btn = QPushButton("Preview")
        self._preview_btn.setObjectName("SmallButton")
        self._preview_btn.clicked.connect(self._toggle_preview)
        btn_row.addWidget(self._preview_btn)
        controls.addLayout(btn_row)

        controls.addStretch(1)
        body.addLayout(controls, 1)
        root.addLayout(body)

    # ── Slots ────────────────────────────────────────────────────────────

    def _save_assignment(self) -> None:
        role_label = self._role_combo.currentText()
        role_key = _LABEL_TO_ROLE.get(role_label, "unassigned")
        label_text = self._label_edit.text().strip() or "unassigned"
        try:
            db.save_camera_assignment(self._camera_id, label_text, role_key)
            self._status_badge.setText("Saved")
            self._status_badge.setObjectName("BadgeBlue")
            self._status_badge.style().unpolish(self._status_badge)
            self._status_badge.style().polish(self._status_badge)
            QTimer.singleShot(2000, self._reset_badge)
        except Exception as exc:
            self._status_badge.setText("Error")
            self._status_badge.setObjectName("BadgeRed")
            self._status_badge.style().unpolish(self._status_badge)
            self._status_badge.style().polish(self._status_badge)

    def _reset_badge(self) -> None:
        text = "Live" if self._previewing else "Idle"
        obj = "BadgeGreen" if self._previewing else "BadgeGray"
        self._status_badge.setText(text)
        self._status_badge.setObjectName(obj)
        self._status_badge.style().unpolish(self._status_badge)
        self._status_badge.style().polish(self._status_badge)

    def _toggle_preview(self) -> None:
        if self._previewing:
            self._stop_preview()
        else:
            self._start_preview()

    def _start_preview(self) -> None:
        try:
            ok = self._bridge.camera_manager.start_preview(
                self._camera_id, self._on_frame
            )
            if ok:
                self._previewing = True
                self._preview_btn.setText("Stop Preview")
                self._dot.setObjectName("DotGreen")
                self._dot.style().unpolish(self._dot)
                self._dot.style().polish(self._dot)
                self._status_badge.setText("Live")
                self._status_badge.setObjectName("BadgeGreen")
                self._status_badge.style().unpolish(self._status_badge)
                self._status_badge.style().polish(self._status_badge)
        except Exception:
            pass

    def _stop_preview(self) -> None:
        try:
            self._bridge.camera_manager.stop_preview(self._camera_id)
        except Exception:
            pass
        self._previewing = False
        self._preview_btn.setText("Preview")
        self._preview.clear()
        self._preview.setText("No signal")
        self._dot.setObjectName("DotGray")
        self._dot.style().unpolish(self._dot)
        self._dot.style().polish(self._dot)
        self._status_badge.setText("Idle")
        self._status_badge.setObjectName("BadgeGray")
        self._status_badge.style().unpolish(self._status_badge)
        self._status_badge.style().polish(self._status_badge)

    def _on_frame(self, frame: np.ndarray) -> None:
        self._preview.update_frame(frame)

    def stop_preview_if_active(self) -> None:
        if self._previewing:
            self._stop_preview()


class _LightingRow(QWidget):
    """Single lighting channel row: label + ON/OFF + slider + value label + Apply."""

    def __init__(self, title: str, apply_fn, parent=None) -> None:
        super().__init__(parent)
        self._apply_fn = apply_fn
        self._last_value = 50  # remember last non-zero value

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        lbl = QLabel(title)
        lbl.setObjectName("DeviceName")
        lbl.setFixedWidth(160)
        lay.addWidget(lbl)

        self._on_btn = QPushButton("ON")
        self._on_btn.setObjectName("SmallButton")
        self._on_btn.setFixedWidth(50)
        self._on_btn.clicked.connect(self._turn_on)
        lay.addWidget(self._on_btn)

        self._off_btn = QPushButton("OFF")
        self._off_btn.setObjectName("SmallButton")
        self._off_btn.setFixedWidth(50)
        self._off_btn.clicked.connect(self._turn_off)
        lay.addWidget(self._off_btn)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(self._last_value)
        self._slider.setFixedWidth(200)
        self._slider.valueChanged.connect(self._on_slider_changed)
        lay.addWidget(self._slider)

        self._val_lbl = QLabel(f"{self._last_value}%")
        self._val_lbl.setObjectName("DeviceSub")
        self._val_lbl.setFixedWidth(40)
        lay.addWidget(self._val_lbl)

        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("SmallButton")
        apply_btn.setFixedWidth(60)
        apply_btn.clicked.connect(self._apply)
        lay.addWidget(apply_btn)

        lay.addStretch(1)

    def _on_slider_changed(self, value: int) -> None:
        self._val_lbl.setText(f"{value}%")
        if value > 0:
            self._last_value = value

    def _turn_on(self) -> None:
        self._slider.setValue(self._last_value)
        self._apply()

    def _turn_off(self) -> None:
        self._slider.setValue(0)
        self._do_apply(0)

    def _apply(self) -> None:
        self._do_apply(self._slider.value())

    def _do_apply(self, value: int) -> None:
        try:
            self._apply_fn(value)
        except Exception:
            pass


class EnvironmentPage(QWidget):
    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._camera_cards: dict[str, _CameraCard] = {}
        self.setStyleSheet("EnvironmentPage { background: #f0f0ff; }")
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        content.setStyleSheet("background: #f0f0ff;")
        scroll.setWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(20)

        title = QLabel("Environment")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        # ── Section A: Camera Devices ────────────────────────────────────
        self._cam_group = QGroupBox("Camera Devices")
        self._cam_outer_lay = QVBoxLayout(self._cam_group)
        self._cam_outer_lay.setSpacing(8)

        # Top toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self._cam_count_lbl = QLabel("Scanning…")
        self._cam_count_lbl.setObjectName("DeviceSub")
        toolbar.addWidget(self._cam_count_lbl)
        toolbar.addStretch(1)
        refresh_btn = QPushButton("Refresh Cameras")
        refresh_btn.setObjectName("SmallButton")
        refresh_btn.clicked.connect(self._refresh_cameras)
        toolbar.addWidget(refresh_btn)
        self._cam_outer_lay.addLayout(toolbar)

        # Container for cards
        self._cards_container = QWidget()
        self._cards_lay = QVBoxLayout(self._cards_container)
        self._cards_lay.setContentsMargins(0, 0, 0, 0)
        self._cards_lay.setSpacing(8)
        self._cam_outer_lay.addWidget(self._cards_container)

        root.addWidget(self._cam_group)

        # ── Section B: Lighting Controls ─────────────────────────────────
        light_group = QGroupBox("Lighting Controls")
        light_lay = QVBoxLayout(light_group)
        light_lay.setSpacing(10)

        self._ir_row = _LightingRow(
            "IR Backlight",
            lambda val: self._apply_ir(val),
        )
        light_lay.addWidget(self._ir_row)

        self._led_row = _LightingRow(
            "LED (White) Backlight",
            lambda val: self._apply_white(val),
        )
        light_lay.addWidget(self._led_row)

        root.addWidget(light_group)
        root.addStretch(1)

        # Populate cameras
        self._populate_camera_cards()

    # ── Camera helpers ────────────────────────────────────────────────────────

    def _populate_camera_cards(self) -> None:
        """Build one card per detected camera, restoring saved assignments."""
        # Remove old cards
        for card in self._camera_cards.values():
            card.stop_preview_if_active()
            self._cards_lay.removeWidget(card)
            card.deleteLater()
        self._camera_cards.clear()

        cameras = self._bridge.camera_manager.list_cameras()
        assignments = {}
        try:
            assignments = db.get_camera_assignments()
        except Exception:
            pass

        for cam_id in cameras:
            saved = assignments.get(cam_id, {})
            card = _CameraCard(
                camera_id=cam_id,
                bridge=self._bridge,
                saved_label=saved.get("label", ""),
                saved_role=saved.get("role", "unassigned"),
            )
            self._cards_lay.addWidget(card)
            self._camera_cards[cam_id] = card

        count = len(cameras)
        self._cam_count_lbl.setText(
            f"{count} camera{'s' if count != 1 else ''} detected"
        )

    def _refresh_cameras(self) -> None:
        """Re-scan cameras without killing Basler streams."""
        try:
            self._bridge.camera_manager.refresh_cameras()
        except Exception:
            pass
        self._populate_camera_cards()

    # ── Lighting helpers ──────────────────────────────────────────────────────

    def _apply_ir(self, value: int) -> None:
        ard = getattr(self._bridge, "_arduino", None)
        if ard and ard.is_connected():
            ard.set_ir_intensity(value)

    def _apply_white(self, value: int) -> None:
        ard = getattr(self._bridge, "_arduino", None)
        if ard and ard.is_connected():
            ard.set_white_intensity(value)
