"""Experiments screen — three-column layout.

Left  (~220px)  : Experiments log / list with filters
Center (expand) : Experiment playback + timeline + summary
Right (~220px)  : Experiment details + export actions
"""

from __future__ import annotations

import os
import time
from typing import Optional

from PyQt6.QtCore import (
    Qt,
    QRectF,
    QSize,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QBrush,
    QPen,
    QIcon,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    line.setObjectName("SectionSeparator")
    return line


def _label(text: str, object_name: str = "ControlLabel") -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName(object_name)
    return lbl


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("SectionTitle")
    font = lbl.font()
    font.setBold(True)
    font.setPointSize(font.pointSize() + 1)
    lbl.setFont(font)
    return lbl


def _fmt_timestamp(ts: float) -> tuple[str, str, str]:
    """Return (date_str, time_str, date_short_str) from unix timestamp."""
    if not ts:
        return "—", "—", "—"
    t = time.localtime(ts)
    date_str = time.strftime("%d %b %Y", t)
    time_str = time.strftime("%H:%M:%S", t)
    date_short = time.strftime("%d %b", t)
    return date_str, time_str, date_short


def _fmt_duration(sec: Optional[float]) -> str:
    if not sec:
        return "—"
    m = int(sec) // 60
    s = int(sec) % 60
    return f"{m:02d}:{s:02d}"


def _status_color(status: str) -> str:
    status = (status or "").lower()
    if status in ("complete", "completed"):
        return "#2979ff"
    if status in ("failed", "error"):
        return "#f44336"
    if status in ("running",):
        return "#ff9800"
    return "#9e9e9e"


# ── Timeline widget (playback view) ───────────────────────────────────────────

class PlaybackTimelineWidget(QWidget):
    """Painted timeline for playback view with Baseline / Stimulus / Recovery."""

    _PHASES = ["Baseline", "Stimulus", "Recovery"]
    _PHASE_WEIGHTS = [0.25, 0.40, 0.35]

    _ROWS = [
        ("Light",     [("", "#b0b0d0", 0.25), ("PULSE", "#f59f00", 0.40), ("", "#b0b0d0", 0.35)]),
        ("Buzzer",    [("ON", "#4caf50", 0.25), ("PULSE", "#2196f3", 0.40), ("OFF", "#b0b0d0", 0.35)]),
        ("Vibration", [("OFF", "#b0b0d0", 0.25), ("ON", "#9c27b0", 0.40), ("OFF", "#b0b0d0", 0.35)]),
    ]
    _TIME_MARKS = [0, 10, 30, 50, 60, 90, 100, 120]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PlaybackTimeline")
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W = self.width()

        row_label_w = 68
        bar_left = row_label_w + 4
        bar_w = W - bar_left - 4

        header_h = 22
        row_h = 24
        gap = 4
        footer_h = 18

        p.fillRect(0, 0, W, self.height(), QColor("#f8f8ff"))

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

        for ri, (row_label, segments) in enumerate(self._ROWS):
            y = header_h + ri * (row_h + gap)
            p.setPen(QColor("#333366"))
            p.setFont(QFont("", 8))
            p.drawText(0, y, row_label_w, row_h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, row_label + "  ")

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

        y_foot = header_h + len(self._ROWS) * (row_h + gap) + 2
        p.setPen(QColor("#888888"))
        p.setFont(QFont("", 7))
        total_time = self._TIME_MARKS[-1]
        for t in self._TIME_MARKS:
            tx = bar_left + int(bar_w * t / total_time)
            p.drawText(tx - 12, y_foot, 24, footer_h, Qt.AlignmentFlag.AlignCenter, str(t))

        p.end()


# ── Status badge ──────────────────────────────────────────────────────────────

class StatusBadge(QLabel):
    """Coloured pill badge for experiment status."""

    def __init__(self, status: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusBadge")
        self.setText(status.capitalize())
        color = _status_color(status)
        self.setStyleSheet(
            f"background:{color}; color:#fff; border-radius:9px;"
            f" padding:1px 8px; font-size:10px; font-weight:bold;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(20)


# ── Experiment row item widget ─────────────────────────────────────────────────

class ExperimentRowWidget(QWidget):
    """Compact row: date | name | status badge."""

    def __init__(self, exp: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.exp = exp
        self.setObjectName("ExperimentRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(6)

        _, _, date_short = _fmt_timestamp(exp.get("started", 0))
        date_lbl = QLabel(date_short)
        date_lbl.setObjectName("ExpDate")
        date_lbl.setFixedWidth(40)
        date_lbl.setFont(QFont("", 8))

        name_lbl = QLabel(exp.get("name", "—"))
        name_lbl.setObjectName("ExpName")
        name_lbl.setFont(QFont("", 9))
        name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        badge = StatusBadge(exp.get("status", "—"))

        lay.addWidget(date_lbl)
        lay.addWidget(name_lbl, 1)
        lay.addWidget(badge)


# ── Export dialog ─────────────────────────────────────────────────────────────

class ExportDialog(QDialog):
    """Export experiment data dialog."""

    def __init__(self, exp: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._exp = exp
        self.setObjectName("ExportDialog")
        self.setWindowTitle("Export Experiment Data")
        self.setMinimumWidth(420)
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 16, 20, 16)

        # Title
        title = QLabel("Export Experiment Data")
        title.setObjectName("DialogTitle")
        font = title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)
        title.setFont(font)
        lay.addWidget(title)

        # Exp ID
        exp_id_lbl = QLabel(f"Experiment: {self._exp.get('exp_id', '—')}")
        exp_id_lbl.setObjectName("DialogSubtitle")
        lay.addWidget(exp_id_lbl)

        lay.addWidget(_separator())

        # Checkboxes
        self._chk_video = QCheckBox("Raw Video (.mp4)")
        self._chk_video.setChecked(True)
        self._chk_events = QCheckBox("Events Log (.csv)")
        self._chk_events.setChecked(True)
        self._chk_meta = QCheckBox("Experiment Metadata (.json)")
        self._chk_meta.setChecked(True)
        self._chk_proto = QCheckBox("Protocol File (.json)")
        self._chk_proto.setChecked(True)
        self._chk_zip = QCheckBox("All Files as ZIP Archive")
        self._chk_zip.setChecked(True)

        for chk in (self._chk_video, self._chk_events, self._chk_meta,
                    self._chk_proto, self._chk_zip):
            chk.setObjectName("ExportCheck")
            lay.addWidget(chk)

        lay.addWidget(_separator())

        # Path row
        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        path_lbl = QLabel("Output Path:")
        path_lbl.setObjectName("ControlLabel")
        self._path_edit = QLineEdit()
        self._path_edit.setObjectName("PathEdit")
        self._path_edit.setPlaceholderText("Select output folder...")
        default_path = self._exp.get("storage_path") or os.path.expanduser("~")
        self._path_edit.setText(default_path)
        self._btn_browse = QPushButton("📁")
        self._btn_browse.setObjectName("BrowseBtn")
        self._btn_browse.setFixedWidth(32)
        self._btn_browse.clicked.connect(self._browse)
        path_row.addWidget(path_lbl)
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(self._btn_browse)
        lay.addLayout(path_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setObjectName("CancelBtn")
        self._btn_cancel.setFixedHeight(32)
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_export = QPushButton("Export")
        self._btn_export.setObjectName("PrimaryButton")
        self._btn_export.setFixedHeight(32)
        self._btn_export.clicked.connect(self._do_export)
        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_export)
        lay.addLayout(btn_row)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder",
                                                   self._path_edit.text())
        if folder:
            self._path_edit.setText(folder)

    def _do_export(self) -> None:
        import shutil
        import zipfile
        import json
        import csv
        from PyQt6.QtWidgets import QMessageBox

        out_dir = self._path_edit.text().strip()
        if not out_dir:
            QMessageBox.warning(self, "No Path", "Please select an output folder.")
            return
        os.makedirs(out_dir, exist_ok=True)

        exp = self._exp
        exported = []

        # Raw Video
        if self._chk_video.isChecked():
            src = exp.get("storage_path", "")
            if src and os.path.isfile(src):
                dst = os.path.join(out_dir, os.path.basename(src))
                shutil.copy2(src, dst)
                exported.append(dst)

        # Events Log (CSV)
        if self._chk_events.isChecked():
            events = exp.get("events_log") or []
            csv_path = os.path.join(out_dir, f"{exp.get('exp_id', 'exp')}_events.csv")
            with open(csv_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["time_sec", "stimulus", "action", "value"])
                w.writeheader()
                if isinstance(events, list):
                    for ev in events:
                        if isinstance(ev, dict):
                            w.writerow(ev)
            exported.append(csv_path)

        # Experiment Metadata (JSON)
        if self._chk_meta.isChecked():
            meta_path = os.path.join(out_dir, f"{exp.get('exp_id', 'exp')}_metadata.json")
            meta = {k: v for k, v in exp.items() if k != "events_log"}
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2, default=str)
            exported.append(meta_path)

        # Protocol File (JSON)
        if self._chk_proto.isChecked() and exp.get("protocol_id"):
            from db.database import get_protocol
            proto = get_protocol(exp["protocol_id"])
            if proto:
                proto_path = os.path.join(out_dir, f"{exp.get('exp_id', 'exp')}_protocol.json")
                with open(proto_path, "w") as f:
                    json.dump(proto, f, indent=2, default=str)
                exported.append(proto_path)

        # ZIP archive
        if self._chk_zip.isChecked() and exported:
            zip_path = os.path.join(out_dir, f"{exp.get('exp_id', 'exp')}.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for fp in exported:
                    if os.path.isfile(fp):
                        zf.write(fp, os.path.basename(fp))

        QMessageBox.information(
            self,
            "Export Complete",
            f"Exported {len(exported)} file(s) to:\n{out_dir}",
        )
        self.accept()


# ── Left panel: experiments log ───────────────────────────────────────────────

class ExperimentsLogPanel(QWidget):
    """Left panel: filter dropdowns, search, list of experiments."""

    experiment_selected = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ExperimentsLogPanel")
        self._experiments: list[dict] = []
        self._filtered: list[dict] = []
        self._page = 0
        self._page_size = 20
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 14, 12, 8)
        root.setSpacing(8)

        root.addWidget(_section_title("Experiments Log"))

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self._combo_period = QComboBox()
        self._combo_period.setObjectName("FilterCombo")
        self._combo_period.addItems(["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"])
        self._combo_proto = QComboBox()
        self._combo_proto.setObjectName("FilterCombo")
        self._combo_proto.addItem("(All Protocols)")
        self._combo_period.currentIndexChanged.connect(self._apply_filters)
        self._combo_proto.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self._combo_period)
        filter_row.addWidget(self._combo_proto)
        root.addLayout(filter_row)

        # Search
        self._search = QLineEdit()
        self._search.setObjectName("SearchEdit")
        self._search.setPlaceholderText("🔍  Search experiments...")
        self._search.textChanged.connect(self._apply_filters)
        root.addWidget(self._search)

        # Table header
        header = QWidget()
        header.setObjectName("TableHeader")
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(8, 2, 8, 2)
        header_lay.setSpacing(6)
        h_date = QLabel("Date")
        h_date.setObjectName("TableHeaderCell")
        h_date.setFixedWidth(40)
        h_name = QLabel("Experiment Name")
        h_name.setObjectName("TableHeaderCell")
        h_name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        h_status = QLabel("Status")
        h_status.setObjectName("TableHeaderCell")
        h_status.setFixedWidth(64)
        header_lay.addWidget(h_date)
        header_lay.addWidget(h_name, 1)
        header_lay.addWidget(h_status)
        root.addWidget(header)

        # List
        self._list = QListWidget()
        self._list.setObjectName("ExperimentList")
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setSpacing(1)
        self._list.itemClicked.connect(self._on_item_clicked)
        root.addWidget(self._list, 1)

        # Pagination
        page_row = QHBoxLayout()
        page_row.setSpacing(4)
        self._btn_prev = QPushButton("‹")
        self._btn_prev.setObjectName("PageBtn")
        self._btn_prev.setFixedWidth(28)
        self._btn_prev.clicked.connect(self._prev_page)
        self._page_lbl = QLabel("—")
        self._page_lbl.setObjectName("PageLabel")
        self._page_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._btn_next = QPushButton("›")
        self._btn_next.setObjectName("PageBtn")
        self._btn_next.setFixedWidth(28)
        self._btn_next.clicked.connect(self._next_page)
        page_row.addStretch()
        page_row.addWidget(self._btn_prev)
        page_row.addWidget(self._page_lbl)
        page_row.addWidget(self._btn_next)
        page_row.addStretch()
        root.addLayout(page_row)

    def load_experiments(self, experiments: list[dict]) -> None:
        self._experiments = experiments

        # Populate protocol filter
        proto_names = sorted({e.get("protocol_name") or "" for e in experiments if e.get("protocol_name")})
        self._combo_proto.blockSignals(True)
        self._combo_proto.clear()
        self._combo_proto.addItem("(All Protocols)")
        for pn in proto_names:
            self._combo_proto.addItem(pn)
        self._combo_proto.blockSignals(False)

        self._page = 0
        self._apply_filters()

    def _apply_filters(self) -> None:
        period_idx = self._combo_period.currentIndex()
        now = time.time()
        cutoffs = [now - 7 * 86400, now - 30 * 86400, now - 90 * 86400, 0]
        cutoff = cutoffs[period_idx]

        proto_filter = self._combo_proto.currentText()
        search_text = self._search.text().lower().strip()

        filtered = []
        for e in self._experiments:
            if cutoff and (e.get("started") or 0) < cutoff:
                continue
            if proto_filter and proto_filter != "(All Protocols)":
                if (e.get("protocol_name") or "") != proto_filter:
                    continue
            if search_text:
                if search_text not in (e.get("name") or "").lower():
                    if search_text not in (e.get("exp_id") or "").lower():
                        continue
            filtered.append(e)

        self._filtered = filtered
        self._page = 0
        self._render_page()

    def _render_page(self) -> None:
        self._list.clear()
        start = self._page * self._page_size
        end = start + self._page_size
        page_items = self._filtered[start:end]

        for exp in page_items:
            item = QListWidgetItem()
            row_widget = ExperimentRowWidget(exp)
            item.setSizeHint(QSize(0, 36))
            item.setData(Qt.ItemDataRole.UserRole, exp)
            self._list.addItem(item)
            self._list.setItemWidget(item, row_widget)

        total = len(self._filtered)
        if total == 0:
            self._page_lbl.setText("0-0")
        else:
            a = start + 1
            b = min(start + len(page_items), total)
            self._page_lbl.setText(f"{a}-{b}")

        self._btn_prev.setEnabled(self._page > 0)
        self._btn_next.setEnabled(end < total)

    def _prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._render_page()

    def _next_page(self) -> None:
        if (self._page + 1) * self._page_size < len(self._filtered):
            self._page += 1
            self._render_page()

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        exp = item.data(Qt.ItemDataRole.UserRole)
        if exp:
            self.experiment_selected.emit(exp)


# ── Center panel: playback ───────────────────────────────────────────────────

class PlaybackPanel(QWidget):
    """Center panel: video placeholder + controls + timeline/summary tabs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PlaybackPanel")
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 10)
        root.setSpacing(10)

        # Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = _section_title("Experiment Playback")
        title_row.addWidget(title)
        title_row.addStretch()

        # Icon buttons (placeholder)
        for icon_text in ("⚙", "↗"):
            btn = QPushButton(icon_text)
            btn.setObjectName("IconBtn")
            btn.setFixedSize(28, 28)
            title_row.addWidget(btn)
        root.addLayout(title_row)

        # Video placeholder
        self._video_area = QLabel()
        self._video_area.setObjectName("VideoPlaceholder")
        self._video_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_area.setText("No experiment selected\nSelect an experiment from the list to view playback")
        self._video_area.setStyleSheet(
            "background:#1a1a2e; color:#888; border-radius:8px;"
            " font-size:13px;"
        )
        # 16:9 ratio approximation
        self._video_area.setMinimumHeight(240)
        self._video_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._video_area, 3)

        # Playback controls
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)

        for btn_text, btn_id in [("▶", "play"), ("⏸", "pause"), ("⏭", "skip")]:
            btn = QPushButton(btn_text)
            btn.setObjectName("PlaybackBtn")
            btn.setFixedSize(32, 32)
            ctrl_row.addWidget(btn)

        vol_btn = QPushButton("🔊")
        vol_btn.setObjectName("PlaybackBtn")
        vol_btn.setFixedSize(32, 32)
        ctrl_row.addWidget(vol_btn)

        ctrl_row.addWidget(QFrame())  # spacer

        self._time_lbl = QLabel("00:00 / 00:00")
        self._time_lbl.setObjectName("PlaybackTime")
        font = self._time_lbl.font()
        font.setFamily("Consolas")
        self._time_lbl.setFont(font)
        ctrl_row.addStretch()
        ctrl_row.addWidget(self._time_lbl)
        root.addLayout(ctrl_row)

        # Tabs: Timeline / Summary
        self._tabs = QTabWidget()
        self._tabs.setObjectName("PlaybackTabs")

        # Timeline tab
        tl_widget = QWidget()
        tl_lay = QVBoxLayout(tl_widget)
        tl_lay.setContentsMargins(4, 8, 4, 4)
        self._timeline = PlaybackTimelineWidget()
        tl_lay.addWidget(self._timeline)
        tl_lay.addStretch()
        self._tabs.addTab(tl_widget, "Timeline")

        # Summary tab
        self._summary_widget = QWidget()
        sum_lay = QVBoxLayout(self._summary_widget)
        sum_lay.setContentsMargins(8, 8, 8, 4)
        self._summary_lbl = QLabel("Select an experiment to view summary.")
        self._summary_lbl.setObjectName("SummaryText")
        self._summary_lbl.setWordWrap(True)
        sum_lay.addWidget(self._summary_lbl)
        sum_lay.addStretch()
        self._tabs.addTab(self._summary_widget, "Summary")

        root.addWidget(self._tabs, 2)

    def load_experiment(self, exp: dict) -> None:
        """Update playback panel with selected experiment."""
        dur = exp.get("duration_sec") or 0
        self._time_lbl.setText(f"00:00 / {_fmt_duration(dur)}")

        name = exp.get("name", "—")
        status = (exp.get("status") or "—").capitalize()
        proto = exp.get("protocol_name") or "—"
        date_str, time_str, _ = _fmt_timestamp(exp.get("started", 0))
        self._video_area.setText(
            f"[{status}]  {name}\n{date_str}  {time_str}\nProtocol: {proto}"
        )

        # Summary
        dur_str = _fmt_duration(exp.get("duration_sec"))
        fps = exp.get("fps") or "—"
        self._summary_lbl.setText(
            f"Experiment: {name}\n"
            f"Status: {status}\n"
            f"Protocol: {proto}\n"
            f"Duration: {dur_str}\n"
            f"Date: {date_str} {time_str}"
        )


# ── Right panel: experiment details ──────────────────────────────────────────

class ExperimentDetailsPanel(QWidget):
    """Right panel: detail key-values, replay and export actions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ExperimentDetailsPanel")
        self.setFixedWidth(220)
        self._current_exp: Optional[dict] = None
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 14, 12, 12)
        root.setSpacing(8)

        root.addWidget(_section_title("Experiment Details"))
        root.addWidget(_separator())

        # Detail key-value section
        self._detail_widget = QWidget()
        self._detail_lay = QVBoxLayout(self._detail_widget)
        self._detail_lay.setContentsMargins(0, 0, 0, 0)
        self._detail_lay.setSpacing(4)

        self._fields: dict[str, QLabel] = {}
        field_defs = [
            ("exp_id",      "Experiment ID:"),
            ("date",        "Date:"),
            ("time",        "Time:"),
            ("protocol",    "Protocol:"),
            ("duration",    "Duration:"),
            ("camera",      "Camera:"),
            ("fps",         "FPS:"),
            ("path",        "Storage Path:"),
        ]
        for field_id, label_text in field_defs:
            row = QHBoxLayout()
            row.setSpacing(4)
            key_lbl = QLabel(label_text)
            key_lbl.setObjectName("DetailKey")
            key_lbl.setFixedWidth(90)
            key_font = key_lbl.font()
            key_font.setBold(True)
            key_font.setPointSize(key_font.pointSize() - 1)
            key_lbl.setFont(key_font)
            key_lbl.setWordWrap(True)

            val_lbl = QLabel("—")
            val_lbl.setObjectName("DetailValue")
            val_font = val_lbl.font()
            if field_id == "path":
                val_font.setPointSize(val_font.pointSize() - 2)
            val_lbl.setFont(val_font)
            val_lbl.setWordWrap(True)
            val_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            row.addWidget(key_lbl)
            row.addWidget(val_lbl, 1)
            self._detail_lay.addLayout(row)
            self._fields[field_id] = val_lbl

        root.addWidget(self._detail_widget)

        # Folder / copy path row
        folder_row = QHBoxLayout()
        folder_row.setSpacing(6)
        self._btn_open_folder = QPushButton("Open Folder")
        self._btn_open_folder.setObjectName("SmallBtn")
        self._btn_open_folder.setFixedHeight(26)
        self._btn_open_folder.clicked.connect(self._on_open_folder)
        self._btn_copy_path = QPushButton("Copy Path")
        self._btn_copy_path.setObjectName("SmallBtn")
        self._btn_copy_path.setFixedHeight(26)
        self._btn_copy_path.clicked.connect(self._on_copy_path)
        folder_row.addWidget(self._btn_open_folder)
        folder_row.addWidget(self._btn_copy_path)
        root.addLayout(folder_row)

        root.addWidget(_separator())

        # Replay button
        self._btn_replay = QPushButton("↺  Replay")
        self._btn_replay.setObjectName("ReplayBtn")
        self._btn_replay.setFixedHeight(36)
        self._btn_replay.clicked.connect(self._on_replay)
        root.addWidget(self._btn_replay)

        # Export rows
        for label, export_type in [
            ("Export...  ›", "export"),
            ("Export CSV  ›", "csv"),
            ("Export All (ZIP)  ›", "zip"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("ExportRowBtn")
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, et=export_type: self._on_export(et))
            root.addWidget(btn)

        root.addStretch(1)

    def load_experiment(self, exp: dict) -> None:
        self._current_exp = exp
        date_str, time_str, _ = _fmt_timestamp(exp.get("started", 0))
        dur_str = _fmt_duration(exp.get("duration_sec"))
        path = exp.get("storage_path") or "—"

        self._fields["exp_id"].setText(exp.get("exp_id") or "—")
        self._fields["date"].setText(date_str)
        self._fields["time"].setText(time_str)
        self._fields["protocol"].setText(exp.get("protocol_name") or "—")
        self._fields["duration"].setText(dur_str)
        self._fields["camera"].setText(exp.get("camera") or "—")
        self._fields["fps"].setText(str(exp.get("fps") or "—"))
        self._fields["path"].setText(path)

    def _on_open_folder(self) -> None:
        if not self._current_exp:
            return
        path = self._current_exp.get("storage_path") or ""
        if os.path.isdir(path):
            import subprocess
            try:
                subprocess.Popen(["explorer", path])
            except Exception:
                pass

    def _on_copy_path(self) -> None:
        if not self._current_exp:
            return
        path = self._current_exp.get("storage_path") or ""
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(path)

    def _on_replay(self) -> None:
        pass  # future: trigger video playback in center panel

    def _on_export(self, export_type: str) -> None:
        if not self._current_exp:
            return
        dlg = ExportDialog(self._current_exp, self)
        dlg.exec()


# ── Main ExperimentsPage ──────────────────────────────────────────────────────

class ExperimentsPage(QWidget):
    """Full three-column experiments screen."""

    def __init__(self, bridge=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self.setObjectName("ExperimentsPage")
        self._build()
        self._load_data()

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # LEFT panel
        self._log_panel = ExperimentsLogPanel()
        self._log_panel.experiment_selected.connect(self._on_experiment_selected)
        left_scroll = QScrollArea()
        left_scroll.setObjectName("LeftScrollArea")
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setWidget(self._log_panel)
        left_scroll.setFixedWidth(220)
        root.addWidget(left_scroll)

        left_div = QFrame()
        left_div.setFrameShape(QFrame.Shape.VLine)
        left_div.setObjectName("PanelDivider")
        root.addWidget(left_div)

        # CENTER panel
        self._playback = PlaybackPanel()
        root.addWidget(self._playback, 1)

        right_div = QFrame()
        right_div.setFrameShape(QFrame.Shape.VLine)
        right_div.setObjectName("PanelDivider")
        root.addWidget(right_div)

        # RIGHT panel
        self._details = ExperimentDetailsPanel()
        root.addWidget(self._details)

    def _load_data(self) -> None:
        try:
            from db import database as db
            experiments = db.list_experiments(limit=100)
            self._log_panel.load_experiments(experiments)
        except Exception:
            self._log_panel.load_experiments([])

    def _on_experiment_selected(self, exp: dict) -> None:
        self._playback.load_experiment(exp)
        self._details.load_experiment(exp)

    def refresh(self) -> None:
        """Reload experiments from the database."""
        self._load_data()
