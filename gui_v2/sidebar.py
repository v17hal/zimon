"""Dynamic left navigation — items depend on Adult vs Larval mode."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget, QButtonGroup


# page_id -> display label
COMMON_ITEMS = [
    ("dashboard", "Dashboard"),
    ("camera", "Camera Settings"),
    ("environment", "Environment"),
    ("stimulus", "Stimulus Control"),
    ("recording", "Recording"),
    ("settings", "Settings"),
]
ADULT_EXTRA = [("multi_angle", "Multi-angle / Cameras")]
LARVAL_EXTRA = [("well_roi", "Well / ROI")]


class Sidebar(QFrame):
    page_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 16, 10, 16)
        self._layout.setSpacing(6)
        self._mode = "adult"
        self._rebuild("adult")

    def set_mode(self, mode: str) -> None:
        mode = mode.lower()
        if mode not in ("adult", "larval"):
            return
        if mode == self._mode:
            return
        self._mode = mode
        current = self.current_page_id()
        self._rebuild(mode)
        if current in self._buttons:
            self._buttons[current].setChecked(True)
        elif "dashboard" in self._buttons:
            self._buttons["dashboard"].setChecked(True)
            self.page_requested.emit("dashboard")

    def current_page_id(self) -> str | None:
        for pid, btn in self._buttons.items():
            if btn.isChecked():
                return pid
        return None

    def _rebuild(self, mode: str) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._buttons.clear()
        for b in self._group.buttons():
            self._group.removeButton(b)

        items = list(COMMON_ITEMS)
        if mode == "adult":
            items = items[:4] + ADULT_EXTRA + items[4:]
        else:
            items = items[:4] + LARVAL_EXTRA + items[4:]

        for page_id, label in items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("NavButton")
            btn.clicked.connect(lambda _=False, pid=page_id: self._on_nav(pid))
            self._group.addButton(btn)
            self._layout.addWidget(btn)
            self._buttons[page_id] = btn

        self._layout.addStretch(1)

        if "dashboard" in self._buttons:
            self._buttons["dashboard"].setChecked(True)

    def _on_nav(self, page_id: str) -> None:
        self.page_requested.emit(page_id)

    def highlight(self, page_id: str) -> None:
        btn = self._buttons.get(page_id)
        if btn:
            btn.setChecked(True)
