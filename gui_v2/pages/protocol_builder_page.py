"""Protocol Builder — matches PPT mockup.

Layout:
  Left: protocol meta + step list + Add step buttons
  Center: automated protocol timeline (visual horizontal bars)
  Right: protocol summary + total runtime + Test/Run buttons
"""

from __future__ import annotations

import os
import time
import threading
from typing import Callable

from PyQt6.QtCore import Qt, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from db import database as db


# ── Step type configs ───────────────────────────────────────────────────────

STEP_TYPES = {
    "baseline": {"label": "Baseline Stage", "color": "#3b5bdb", "fields": []},
    "light":    {"label": "Light",          "color": "#f59f00",
                 "fields": [
                     ("flash_type",   "Flash Type",  "combo", ["IR", "White", "RGB"]),
                     ("intensity",    "Intensity %", "int",   (0, 100, 80)),
                     ("pulse_width",  "Pulse Width ms", "int", (1, 5000, 50)),
                     ("duration_ms",  "Duration ms", "int",  (1, 60000, 100)),
                 ]},
    "buzzer":   {"label": "Buzzer",         "color": "#ae3ec9",
                 "fields": [
                     ("tone",      "Tone",       "combo", ["Tone", "Noise", "File"]),
                     ("amplitude", "Amplitude",  "int",   (0, 255, 100)),
                     ("duration_ms","Duration ms","int",  (1, 60000, 200)),
                 ]},
    "vibration":{"label": "Vibration",      "color": "#2f9e44",
                 "fields": [
                     ("frequency",  "Frequency Hz", "float", (0.1, 200.0, 5.0)),
                     ("duration_ms","Duration ms",  "int",   (1, 60000, 200)),
                 ]},
    "water_flow":{"label": "Water Flow",   "color": "#1098ad",
                 "fields": [
                     ("duration_ms","Duration ms", "int", (1, 60000, 500)),
                 ]},
}


def _make_step(step_type: str, duration_sec: float = 10.0, params: dict | None = None) -> dict:
    return {
        "type": step_type,
        "label": STEP_TYPES[step_type]["label"],
        "duration_sec": duration_sec,
        "params": params or {},
    }


# ── Timeline widget ─────────────────────────────────────────────────────────

class TimelineWidget(QWidget):
    """Draws horizontal colored bars per step (like the PPT mockup timeline)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._steps: list[dict] = []
        self.setMinimumHeight(90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_steps(self, steps: list[dict]) -> None:
        self._steps = steps
        self.update()

    def paintEvent(self, event) -> None:
        if not self._steps:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        total = sum(s["duration_sec"] for s in self._steps) or 1.0
        w, h = self.width(), self.height()
        bar_h = 28
        bar_y = (h - bar_h) / 2
        label_y = bar_y - 6

        x = 0.0
        for step in self._steps:
            frac = step["duration_sec"] / total
            bw = frac * w
            color = QColor(STEP_TYPES.get(step["type"], {}).get("color", "#555"))
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(x + 1, bar_y, bw - 2, bar_h), 4, 4)

            # label
            p.setPen(QPen(QColor("#ffffff")))
            font = QFont("Segoe UI", 9)
            p.setFont(font)
            p.drawText(QRectF(x + 4, bar_y, bw - 8, bar_h),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       step["label"])

            # duration tick
            p.setPen(QPen(QColor("#aaaaaa")))
            font2 = QFont("Segoe UI", 8)
            p.setFont(font2)
            p.drawText(QRectF(x + 4, bar_y + bar_h + 2, bw - 8, 16),
                       Qt.AlignmentFlag.AlignLeft,
                       f"{step['duration_sec']}s")
            x += bw

        p.end()


# ── Step row widget ─────────────────────────────────────────────────────────

class StepRow(QFrame):
    delete_requested = pyqtSignal(int)
    edit_requested   = pyqtSignal(int)

    def __init__(self, idx: int, step: dict, parent=None) -> None:
        super().__init__(parent)
        self._idx = idx
        self.setObjectName("StepRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)

        color = STEP_TYPES.get(step["type"], {}).get("color", "#555")
        dot = QLabel("■")
        dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        dot.setFixedWidth(18)
        lay.addWidget(dot)

        num = QLabel(f"Step {idx + 1}")
        num.setObjectName("StepNum")
        num.setFixedWidth(52)
        lay.addWidget(num)

        label = QLabel(step["label"])
        label.setObjectName("StepLabel")
        lay.addWidget(label, 1)

        dur = QLabel(f"{step['duration_sec']}s")
        dur.setObjectName("StepDur")
        dur.setFixedWidth(44)
        lay.addWidget(dur)

        btn_edit = QPushButton("Edit")
        btn_edit.setObjectName("SmallButton")
        btn_edit.setFixedWidth(48)
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(self._idx))
        lay.addWidget(btn_edit)

        btn_del = QPushButton("✕")
        btn_del.setObjectName("SmallDangerButton")
        btn_del.setFixedWidth(32)
        btn_del.clicked.connect(lambda: self.delete_requested.emit(self._idx))
        lay.addWidget(btn_del)


# ── Step editor dialog ──────────────────────────────────────────────────────

class StepEditorDialog(QDialog):
    def __init__(self, step: dict, parent=None) -> None:
        super().__init__(parent)
        self._step = dict(step)
        self.setWindowTitle(f"Edit Step: {step['label']}")
        self.setMinimumWidth(380)
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._dur = QDoubleSpinBox()
        self._dur.setRange(0.1, 3600.0)
        self._dur.setSingleStep(0.5)
        self._dur.setSuffix(" sec")
        self._dur.setValue(self._step["duration_sec"])
        form.addRow("Duration:", self._dur)

        self._param_widgets: dict[str, QWidget] = {}
        cfg = STEP_TYPES.get(self._step["type"], {})
        params = self._step.get("params", {})

        for key, label, wtype, options in cfg.get("fields", []):
            if wtype == "combo":
                w = QComboBox()
                w.addItems(options)
                if key in params:
                    idx = w.findText(str(params[key]))
                    if idx >= 0:
                        w.setCurrentIndex(idx)
            elif wtype == "int":
                w = QSpinBox()
                mn, mx, default = options
                w.setRange(mn, mx)
                w.setValue(int(params.get(key, default)))
            elif wtype == "float":
                w = QDoubleSpinBox()
                mn, mx, default = options
                w.setRange(mn, mx)
                w.setValue(float(params.get(key, default)))
            else:
                w = QLineEdit(str(params.get(key, "")))
            self._param_widgets[key] = w
            form.addRow(f"{label}:", w)

        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def result_step(self) -> dict:
        self._step["duration_sec"] = self._dur.value()
        params = {}
        for key, w in self._param_widgets.items():
            if isinstance(w, QComboBox):
                params[key] = w.currentText()
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                params[key] = w.value()
            else:
                params[key] = w.text()
        self._step["params"] = params
        return self._step


# ── Main Protocol Builder page ──────────────────────────────────────────────

class ProtocolBuilderPage(QWidget):
    def __init__(self, bridge, user: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._user = user
        self._steps: list[dict] = []
        self._current_protocol_id: int | None = None
        self._run_thread: threading.Thread | None = None
        self._running = False
        self._current_exp_id: str | None = None
        self._events_log: list[dict] = []
        self._run_start_time: float = 0.0
        self._build()

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── LEFT PANEL: meta + steps ──────────────────────────────────
        left = QWidget()
        left.setObjectName("PBLeft")
        left.setMinimumWidth(340)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(20, 20, 16, 20)
        left_lay.setSpacing(14)

        title = QLabel("Protocol Builder")
        title.setObjectName("PageTitle")
        left_lay.addWidget(title)

        # Meta fields
        meta_box = QGroupBox("New Protocol")
        meta_lay = QFormLayout(meta_box)
        meta_lay.setSpacing(8)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Startle Response")
        self._desc_edit = QLineEdit()
        self._desc_edit.setPlaceholderText("Brief description")
        meta_lay.addRow("Name:", self._name_edit)
        meta_lay.addRow("Description:", self._desc_edit)
        left_lay.addWidget(meta_box)

        # Add step buttons
        add_box = QGroupBox("Add Steps")
        add_lay = QHBoxLayout(add_box)
        add_lay.setSpacing(6)
        for stype, cfg in STEP_TYPES.items():
            if stype == "baseline":
                continue
            btn = QPushButton(cfg["label"])
            btn.setObjectName("AddStepBtn")
            btn.clicked.connect(lambda _, t=stype: self._add_step(t))
            add_lay.addWidget(btn)
        # Baseline always goes first
        btn_base = QPushButton("+ Baseline")
        btn_base.setObjectName("SmallButton")
        btn_base.clicked.connect(lambda: self._insert_baseline())
        add_lay.addWidget(btn_base)
        left_lay.addWidget(add_box)

        # Step list
        steps_label = QLabel("Automated Protocol Timeline")
        steps_label.setObjectName("SectionLabel")
        left_lay.addWidget(steps_label)

        self._steps_scroll = QScrollArea()
        self._steps_scroll.setWidgetResizable(True)
        self._steps_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._steps_container = QWidget()
        self._steps_layout = QVBoxLayout(self._steps_container)
        self._steps_layout.setSpacing(6)
        self._steps_layout.setContentsMargins(0, 0, 0, 0)
        self._steps_layout.addStretch(1)
        self._steps_scroll.setWidget(self._steps_container)
        left_lay.addWidget(self._steps_scroll, 1)

        # Timeline visual
        self._timeline = TimelineWidget()
        left_lay.addWidget(self._timeline)

        # ── RIGHT PANEL: summary + actions ───────────────────────────
        right = QWidget()
        right.setObjectName("PBRight")
        right.setMinimumWidth(260)
        right.setMaximumWidth(340)
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(16, 20, 20, 20)
        right_lay.setSpacing(14)

        sum_title = QLabel("Protocol Summary")
        sum_title.setObjectName("SectionLabel")
        right_lay.addWidget(sum_title)

        self._summary_scroll = QScrollArea()
        self._summary_scroll.setWidgetResizable(True)
        self._summary_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._summary_container = QWidget()
        self._summary_layout = QVBoxLayout(self._summary_container)
        self._summary_layout.setSpacing(4)
        self._summary_layout.setContentsMargins(0, 0, 0, 0)
        self._summary_layout.addStretch(1)
        self._summary_scroll.setWidget(self._summary_container)
        right_lay.addWidget(self._summary_scroll, 1)

        self._runtime_lbl = QLabel("Total Runtime: 0 sec")
        self._runtime_lbl.setObjectName("RuntimeLabel")
        right_lay.addWidget(self._runtime_lbl)

        # Load existing protocol
        load_row = QHBoxLayout()
        self._proto_combo = QComboBox()
        self._proto_combo.setMinimumWidth(150)
        self._refresh_protocol_list()
        btn_load = QPushButton("Load")
        btn_load.setObjectName("SmallButton")
        btn_load.clicked.connect(self._load_protocol)
        load_row.addWidget(self._proto_combo, 1)
        load_row.addWidget(btn_load)
        right_lay.addLayout(load_row)

        # Action buttons
        btn_save = QPushButton("Save Protocol")
        btn_save.setObjectName("PrimaryButton")
        btn_save.clicked.connect(self._save_protocol)
        right_lay.addWidget(btn_save)

        self._btn_test = QPushButton("Test Run")
        self._btn_test.setObjectName("SmallButton")
        self._btn_test.clicked.connect(self._test_run)
        right_lay.addWidget(self._btn_test)

        self._btn_run = QPushButton("▶  Run Protocol")
        self._btn_run.setObjectName("RunButton")
        self._btn_run.clicked.connect(self._run_protocol)
        right_lay.addWidget(self._btn_run)

        self._btn_stop = QPushButton("■  Stop")
        self._btn_stop.setObjectName("DangerButton")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop_protocol)
        right_lay.addWidget(self._btn_stop)

        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("RunStatus")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_lay.addWidget(self._status_lbl)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

        # Start with one baseline step
        self._steps.append(_make_step("baseline", 10.0))
        self._rebuild_step_ui()

    # ── Step management ─────────────────────────────────────────────────────

    def _add_step(self, step_type: str) -> None:
        step = _make_step(step_type, 2.0)
        dlg = StepEditorDialog(step, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._steps.append(dlg.result_step())
            self._rebuild_step_ui()

    def _insert_baseline(self) -> None:
        self._steps.insert(0, _make_step("baseline", 10.0))
        self._rebuild_step_ui()

    def _edit_step(self, idx: int) -> None:
        if idx >= len(self._steps):
            return
        dlg = StepEditorDialog(self._steps[idx], self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._steps[idx] = dlg.result_step()
            self._rebuild_step_ui()

    def _delete_step(self, idx: int) -> None:
        if idx < len(self._steps):
            self._steps.pop(idx)
            self._rebuild_step_ui()

    def _rebuild_step_ui(self) -> None:
        # Clear existing rows
        while self._steps_layout.count() > 1:
            item = self._steps_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for i, step in enumerate(self._steps):
            row = StepRow(i, step)
            row.delete_requested.connect(self._delete_step)
            row.edit_requested.connect(self._edit_step)
            self._steps_layout.insertWidget(i, row)

        self._timeline.set_steps(self._steps)
        self._rebuild_summary()

    def _rebuild_summary(self) -> None:
        while self._summary_layout.count() > 1:
            item = self._summary_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        total = 0.0
        for i, step in enumerate(self._steps):
            total += step["duration_sec"]
            lbl = QLabel(f"Step {i+1}  ·  {step['label']}  ·  {step['duration_sec']}s")
            lbl.setObjectName("SummaryRow")
            self._summary_layout.insertWidget(i, lbl)

        self._runtime_lbl.setText(f"Total Runtime: {total:.1f} sec")

    # ── Save / Load ──────────────────────────────────────────────────────────

    def _save_protocol(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Required", "Please enter a protocol name.")
            return
        desc = self._desc_edit.text().strip()
        uid = self._user.get("id", 0)
        pid = db.save_protocol(name, desc, self._steps, uid, self._current_protocol_id)
        self._current_protocol_id = pid
        self._refresh_protocol_list()
        QMessageBox.information(self, "Saved", f"Protocol '{name}' saved.")

    def _refresh_protocol_list(self) -> None:
        self._proto_combo.blockSignals(True)
        self._proto_combo.clear()
        self._proto_combo.addItem("— select —", None)
        for p in db.list_protocols():
            self._proto_combo.addItem(p["name"], p["id"])
        self._proto_combo.blockSignals(False)

    def _load_protocol(self) -> None:
        pid = self._proto_combo.currentData()
        if pid is None:
            return
        proto = db.get_protocol(pid)
        if not proto:
            return
        self._current_protocol_id = pid
        self._name_edit.setText(proto["name"])
        self._desc_edit.setText(proto.get("description") or "")
        self._steps = proto["steps"]
        self._rebuild_step_ui()

    # ── Run / Test ───────────────────────────────────────────────────────────

    def _test_run(self) -> None:
        if not self._steps:
            QMessageBox.information(self, "Empty", "Add at least one step first.")
            return
        total = sum(s["duration_sec"] for s in self._steps)
        QMessageBox.information(
            self, "Test Run",
            f"Protocol: {self._name_edit.text() or 'Untitled'}\n"
            f"Steps: {len(self._steps)}\n"
            f"Total runtime: {total:.1f} sec\n\n"
            "Hardware is NOT activated during a test run."
        )

    def _run_protocol(self) -> None:
        if not self._steps:
            QMessageBox.warning(self, "Empty", "Add at least one step first.")
            return
        if self._running:
            return
        self._running = True
        self._events_log = []
        self._run_start_time = time.time()

        # Create experiment record in DB
        try:
            proto_name = self._name_edit.text().strip() or "Untitled"
            cameras = self._bridge.camera_manager.list_cameras()
            camera = cameras[0] if cameras else "unknown"
            storage = os.path.join(os.path.expanduser("~"), "Videos", "ZIMON")
            rec = db.create_experiment(
                name=f"{proto_name} Run",
                protocol_id=self._current_protocol_id,
                protocol_name=proto_name,
                mode=getattr(self._bridge, "_mode_profile", None) and
                     self._bridge._mode_profile.label or "adult",
                camera=camera,
                storage_path=storage,
                created_by=self._user.get("id", 0),
            )
            self._current_exp_id = rec["exp_id"]
        except Exception:
            self._current_exp_id = None

        self._btn_run.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._status_lbl.setText("Running…")
        self._run_thread = threading.Thread(target=self._execute_protocol, daemon=True)
        self._run_thread.start()

    def _stop_protocol(self) -> None:
        self._running = False
        self._btn_stop.setEnabled(False)
        self._btn_run.setEnabled(True)
        self._status_lbl.setText("Stopped.")
        self._finish_experiment("stopped")

    def _log_event(self, stimulus: str, action: str, value: str = "") -> None:
        elapsed = round(time.time() - self._run_start_time, 3)
        self._events_log.append({
            "time_sec": elapsed,
            "stimulus": stimulus,
            "action": action,
            "value": value,
        })

    def _execute_protocol(self) -> None:
        ard = getattr(self._bridge, "_arduino", None)
        for i, step in enumerate(self._steps):
            if not self._running:
                break
            stype = step["type"]
            dur = step["duration_sec"]
            params = step.get("params", {})

            QTimer.singleShot(0, lambda s=i, l=step["label"]:
                              self._status_lbl.setText(f"Step {s+1}: {l}"))
            self._log_event(stype, "start", step["label"])

            if ard and ard.is_connected():
                if stype == "light":
                    ft = params.get("flash_type", "IR")
                    intensity = int(params.get("intensity", 80))
                    if ft == "IR":
                        ard.set_ir_intensity(intensity)
                    elif ft == "White":
                        ard.set_white_intensity(intensity)
                    elif ft == "RGB":
                        pct = intensity / 100.0
                        v = int(pct * 255)
                        ard.rgb_set(v, v, v)
                    self._log_event("light", "on", f"{ft} {intensity}%")

                elif stype == "buzzer":
                    ard.write_command("BUZZER_ON")
                    self._log_event("buzzer", "on")

                elif stype == "vibration":
                    dur_ms = int(params.get("duration_ms", 200))
                    ard.vibrate_timed(dur_ms)
                    self._log_event("vibration", "on", f"{dur_ms}ms")

                elif stype == "water_flow":
                    ard.write_command("PUMP_ON")
                    self._log_event("water_flow", "on")

            time.sleep(dur)

            # Turn off after step
            if ard and ard.is_connected():
                if stype == "light":
                    ard.set_ir_intensity(0)
                    ard.set_white_intensity(0)
                    ard.rgb_set(0, 0, 0)
                    self._log_event("light", "off")
                elif stype == "buzzer":
                    ard.write_command("BUZZER_OFF")
                    self._log_event("buzzer", "off")
                elif stype == "water_flow":
                    ard.write_command("PUMP_OFF")
                    self._log_event("water_flow", "off")

        self._running = False
        QTimer.singleShot(0, self._on_run_finished)

    def _finish_experiment(self, status: str = "complete") -> None:
        if not self._current_exp_id:
            return
        try:
            duration = round(time.time() - self._run_start_time, 1)
            db.finish_experiment(self._current_exp_id, duration, status, self._events_log)
        except Exception:
            pass
        self._current_exp_id = None

    def _on_run_finished(self) -> None:
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._status_lbl.setText("Protocol complete ✓")
        self._finish_experiment("complete")
