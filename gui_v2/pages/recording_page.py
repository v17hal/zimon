"""Recording page — path, name, duration, status."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class RecordingPage(QWidget):
    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("Recording")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        form = QGroupBox("Output")
        fl = QFormLayout(form)
        self.basename = QLineEdit("experiment_run")
        self.path = QLineEdit(str(Path.home() / "Videos" / "ZIMON"))
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse)
        path_row = QVBoxLayout()
        path_row.addWidget(self.path)
        path_row.addWidget(btn_browse)
        fl.addRow("Base name", self.basename)
        fl.addRow("Save folder", path_row)

        self.duration = QSpinBox()
        self.duration.setRange(0, 86400)
        self.duration.setValue(0)
        self.duration.setSuffix(" s")
        fl.addRow("Duration (0 = until stop)", self.duration)

        root.addWidget(form)

        self.status = QLabel("Status: idle")
        root.addWidget(self.status)

        row = QVBoxLayout()
        self.btn_start = QPushButton("Start recording")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_stop = QPushButton("Stop recording")
        self.btn_stop.setObjectName("DangerButton")
        self.btn_stop.setEnabled(False)
        self.btn_start.clicked.connect(self._start)
        self.btn_stop.clicked.connect(self._stop)
        row.addWidget(self.btn_start)
        row.addWidget(self.btn_stop)
        root.addLayout(row)
        root.addStretch(1)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select save folder", self.path.text())
        if d:
            self.path.setText(d)

    def _start(self) -> None:
        dur = None if self.duration.value() == 0 else int(self.duration.value())
        ok = self._bridge.start_recording(self.path.text(), self.basename.text(), dur)
        if ok:
            self.status.setText("Status: recording")
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)

    def _stop(self) -> None:
        self._bridge.stop_recording()
        self.sync_idle_state()

    def sync_idle_state(self) -> None:
        """Called when recording ends (manual stop, error, or duration)."""
        self.status.setText("Status: idle")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
