"""Settings page — hardware connection, camera defaults, recording, application."""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QFrame,
    QMessageBox,
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _row_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("RowLabel")
    lbl.setMinimumWidth(160)
    return lbl


def _h_rule() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    line.setObjectName("SectionSeparator")
    return line


def _small_btn(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("SmallButton")
    btn.setFixedHeight(28)
    return btn


def _primary_btn(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("PrimaryButton")
    btn.setFixedHeight(36)
    return btn


# ── Status dot widget ─────────────────────────────────────────────────────────

class _StatusDot(QLabel):
    """Small coloured circle: green = connected, red = not connected."""

    _CSS_BASE = (
        "border-radius:7px; min-width:14px; max-width:14px;"
        " min-height:14px; max-height:14px;"
    )

    def __init__(self, connected: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusDot")
        self.set_connected(connected)

    def set_connected(self, connected: bool) -> None:
        color = "#4caf50" if connected else "#f44336"
        self.setStyleSheet(f"background:{color}; {self._CSS_BASE}")
        self.setToolTip("Connected" if connected else "Not connected")


# ── Section card (styled QGroupBox) ──────────────────────────────────────────

def _card(title: str) -> QGroupBox:
    box = QGroupBox(title)
    box.setObjectName("Card")
    return box


# ── Settings page ─────────────────────────────────────────────────────────────

class SettingsPage(QWidget):
    """Clean, card-based settings page with light lavender background."""

    def __init__(self, bridge=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self.setObjectName("SettingsPage")
        self.setStyleSheet("SettingsPage { background: #f0f0ff; }")
        self._build()
        self._load_current_settings()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Outer scroll area so the page is usable at any window height
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("SettingsContent")
        content.setStyleSheet("QWidget#SettingsContent { background: #f0f0ff; }")
        scroll.setWidget(content)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        inner = QVBoxLayout(content)
        inner.setContentsMargins(28, 24, 28, 28)
        inner.setSpacing(18)

        # Page title
        page_title = QLabel("Settings")
        page_title.setObjectName("PageTitle")
        title_font = page_title.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 4)
        page_title.setFont(title_font)
        inner.addWidget(page_title)

        inner.addWidget(self._build_hardware_section())
        inner.addWidget(self._build_camera_section())
        inner.addWidget(self._build_recording_section())
        inner.addWidget(self._build_application_section())

        inner.addSpacing(8)

        self._save_btn = _primary_btn("Save Settings")
        self._save_btn.setFixedWidth(160)
        self._save_btn.clicked.connect(self._save)
        inner.addWidget(self._save_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        inner.addStretch(1)

    # ── Hardware Connection section ───────────────────────────────────────────

    def _build_hardware_section(self) -> QGroupBox:
        card = _card("Hardware Connection")
        lay = QVBoxLayout(card)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        # Arduino port row
        port_row = QHBoxLayout()
        port_row.setSpacing(8)
        port_row.addWidget(_row_label("Arduino Port:"))

        self._port_combo = QComboBox()
        self._port_combo.setObjectName("SettingsCombo")
        self._port_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        port_row.addWidget(self._port_combo, 1)

        self._refresh_btn = _small_btn("Refresh")
        self._refresh_btn.setObjectName("SmallButton")
        self._refresh_btn.clicked.connect(self._refresh_ports)
        port_row.addWidget(self._refresh_btn)

        self._connect_btn = _small_btn("Connect")
        self._connect_btn.setObjectName("SmallButton")
        self._connect_btn.clicked.connect(self._connect_arduino)
        port_row.addWidget(self._connect_btn)

        self._status_dot = _StatusDot(connected=False)
        port_row.addWidget(self._status_dot)
        lay.addLayout(port_row)

        # Baud rate row
        baud_row = QHBoxLayout()
        baud_row.setSpacing(8)
        baud_row.addWidget(_row_label("Baud Rate:"))
        self._baud_combo = QComboBox()
        self._baud_combo.setObjectName("SettingsCombo")
        self._baud_combo.addItems(["9600", "57600", "115200"])
        self._baud_combo.setCurrentText("115200")
        self._baud_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        baud_row.addWidget(self._baud_combo, 1)
        lay.addLayout(baud_row)

        # Populate ports
        self._refresh_ports()

        return card

    # ── Camera Defaults section ───────────────────────────────────────────────

    def _build_camera_section(self) -> QGroupBox:
        card = _card("Camera Defaults")
        lay = QVBoxLayout(card)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        # Default FPS
        fps_row = QHBoxLayout()
        fps_row.setSpacing(8)
        fps_row.addWidget(_row_label("Default FPS:"))
        self._fps_spin = QSpinBox()
        self._fps_spin.setObjectName("SettingsSpin")
        self._fps_spin.setRange(1, 240)
        self._fps_spin.setValue(30)
        self._fps_spin.setSuffix(" fps")
        fps_row.addWidget(self._fps_spin)
        fps_row.addStretch()
        lay.addLayout(fps_row)

        # Default Resolution
        res_row = QHBoxLayout()
        res_row.setSpacing(8)
        res_row.addWidget(_row_label("Default Resolution:"))
        self._res_w_spin = QSpinBox()
        self._res_w_spin.setObjectName("SettingsSpin")
        self._res_w_spin.setRange(1, 7680)
        self._res_w_spin.setValue(1920)
        self._res_w_spin.setPrefix("W: ")
        self._res_w_spin.setMinimumWidth(90)

        self._res_h_spin = QSpinBox()
        self._res_h_spin.setObjectName("SettingsSpin")
        self._res_h_spin.setRange(1, 4320)
        self._res_h_spin.setValue(1080)
        self._res_h_spin.setPrefix("H: ")
        self._res_h_spin.setMinimumWidth(90)

        res_row.addWidget(self._res_w_spin)
        res_row.addWidget(QLabel("×"))
        res_row.addWidget(self._res_h_spin)
        res_row.addStretch()
        lay.addLayout(res_row)

        # Auto-start camera
        autostart_row = QHBoxLayout()
        autostart_row.setSpacing(8)
        autostart_row.addWidget(_row_label("Auto-start camera on launch:"))
        self._autostart_chk = QCheckBox()
        self._autostart_chk.setObjectName("SettingsCheck")
        self._autostart_chk.setChecked(False)
        autostart_row.addWidget(self._autostart_chk)
        autostart_row.addStretch()
        lay.addLayout(autostart_row)

        return card

    # ── Recording section ─────────────────────────────────────────────────────

    def _build_recording_section(self) -> QGroupBox:
        card = _card("Recording")
        lay = QVBoxLayout(card)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        # Default output folder
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_row.addWidget(_row_label("Default Output Folder:"))
        self._output_folder_edit = QLineEdit()
        self._output_folder_edit.setObjectName("SettingsLineEdit")
        self._output_folder_edit.setPlaceholderText("Select folder...")
        self._output_folder_edit.setText(os.path.expanduser("~"))
        self._output_folder_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        folder_row.addWidget(self._output_folder_edit, 1)
        self._browse_btn = _small_btn("Browse")
        self._browse_btn.setObjectName("SmallButton")
        self._browse_btn.clicked.connect(self._browse_output_folder)
        folder_row.addWidget(self._browse_btn)
        lay.addLayout(folder_row)

        # Default filename prefix
        prefix_row = QHBoxLayout()
        prefix_row.setSpacing(8)
        prefix_row.addWidget(_row_label("Default Filename Prefix:"))
        self._prefix_edit = QLineEdit()
        self._prefix_edit.setObjectName("SettingsLineEdit")
        self._prefix_edit.setPlaceholderText("e.g. zebrafish_exp")
        self._prefix_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        prefix_row.addWidget(self._prefix_edit, 1)
        lay.addLayout(prefix_row)

        return card

    # ── Application section ───────────────────────────────────────────────────

    def _build_application_section(self) -> QGroupBox:
        card = _card("Application")
        lay = QVBoxLayout(card)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        # Theme
        theme_row = QHBoxLayout()
        theme_row.setSpacing(8)
        theme_row.addWidget(_row_label("Theme:"))
        self._theme_combo = QComboBox()
        self._theme_combo.setObjectName("SettingsCombo")
        self._theme_combo.addItems(["Light", "Dark"])
        self._theme_combo.setCurrentText("Light")
        self._theme_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        theme_row.addWidget(self._theme_combo, 1)
        theme_row.addStretch()
        lay.addLayout(theme_row)

        # Auto-save protocols
        autosave_row = QHBoxLayout()
        autosave_row.setSpacing(8)
        autosave_row.addWidget(_row_label("Auto-save protocols:"))
        self._autosave_chk = QCheckBox()
        self._autosave_chk.setObjectName("SettingsCheck")
        self._autosave_chk.setChecked(True)
        autosave_row.addWidget(self._autosave_chk)
        autosave_row.addStretch()
        lay.addLayout(autosave_row)

        return card

    # ── Slots / logic ─────────────────────────────────────────────────────────

    def _refresh_ports(self) -> None:
        """Re-populate the port combo from the bridge."""
        self._port_combo.clear()
        if self._bridge is not None:
            try:
                ports = self._bridge.list_serial_ports()
            except Exception:
                ports = []
        else:
            ports = []

        if ports:
            self._port_combo.addItems(ports)
        else:
            self._port_combo.addItem("— No ports found —")

    def _connect_arduino(self) -> None:
        """Attempt to connect to the selected Arduino port."""
        port = self._port_combo.currentText().strip()
        if not port or port.startswith("—"):
            QMessageBox.warning(self, "No Port", "Please select a valid serial port.")
            return

        if self._bridge is None:
            QMessageBox.warning(self, "No Bridge", "Hardware bridge is not available.")
            return

        try:
            ok = self._bridge._arduino.connect(port)
        except Exception as exc:
            ok = False

        self._status_dot.set_connected(ok)
        if ok:
            self._connect_btn.setText("Connected")
            self._connect_btn.setEnabled(False)
            QMessageBox.information(self, "Arduino", f"Connected to {port}.")
        else:
            QMessageBox.warning(self, "Arduino", f"Could not connect to {port}.\nCheck cable and port selection.")

    def _browse_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Default Output Folder",
            self._output_folder_edit.text(),
        )
        if folder:
            self._output_folder_edit.setText(folder)

    def _load_current_settings(self) -> None:
        """Pre-populate widgets from bridge saved settings (if available)."""
        if self._bridge is None:
            return
        settings: dict = getattr(self._bridge, "_saved_settings", {}) or {}

        com = settings.get("com") or settings.get("serial_port") or ""
        if com:
            idx = self._port_combo.findText(com)
            if idx >= 0:
                self._port_combo.setCurrentIndex(idx)

        theme = settings.get("theme") or "Light"
        idx = self._theme_combo.findText(theme)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)

        fps = settings.get("default_fps")
        if fps is not None:
            try:
                self._fps_spin.setValue(int(fps))
            except (TypeError, ValueError):
                pass

        res_w = settings.get("resolution_width")
        res_h = settings.get("resolution_height")
        if res_w is not None:
            try:
                self._res_w_spin.setValue(int(res_w))
            except (TypeError, ValueError):
                pass
        if res_h is not None:
            try:
                self._res_h_spin.setValue(int(res_h))
            except (TypeError, ValueError):
                pass

        folder = settings.get("output_folder") or ""
        if folder:
            self._output_folder_edit.setText(folder)

        prefix = settings.get("filename_prefix") or ""
        if prefix:
            self._prefix_edit.setText(prefix)

        autostart = settings.get("autostart_camera", False)
        self._autostart_chk.setChecked(bool(autostart))

        autosave = settings.get("autosave_protocols", True)
        self._autosave_chk.setChecked(bool(autosave))

        # Reflect Arduino connection state
        if self._bridge is not None:
            try:
                connected = self._bridge._arduino.is_connected()
                self._status_dot.set_connected(connected)
                if connected:
                    self._connect_btn.setText("Connected")
                    self._connect_btn.setEnabled(False)
            except Exception:
                pass

    def _save(self) -> None:
        """Collect all widget values and persist via bridge.save_settings()."""
        data = {
            "com": self._port_combo.currentText(),
            "baud_rate": int(self._baud_combo.currentText()),
            "default_fps": self._fps_spin.value(),
            "resolution_width": self._res_w_spin.value(),
            "resolution_height": self._res_h_spin.value(),
            "autostart_camera": self._autostart_chk.isChecked(),
            "output_folder": self._output_folder_edit.text().strip(),
            "filename_prefix": self._prefix_edit.text().strip(),
            "theme": self._theme_combo.currentText(),
            "autosave_protocols": self._autosave_chk.isChecked(),
        }

        if self._bridge is not None:
            try:
                ok = self._bridge.save_settings(data)
            except Exception as exc:
                QMessageBox.critical(self, "Save Failed", str(exc))
                return
            if not ok:
                QMessageBox.warning(
                    self,
                    "Partial Save",
                    "Settings saved but Arduino connection failed.\n"
                    "Check the selected port and try reconnecting.",
                )
                return

        QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully.")
