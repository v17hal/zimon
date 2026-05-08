"""Larval mode — well plate / ROI configuration (placeholder)."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class WellRoiPage(QWidget):
    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        lay = QVBoxLayout(self)
        t = QLabel("Well / ROI configuration")
        t.setObjectName("PageTitle")
        lay.addWidget(t)
        lay.addWidget(
            QLabel(
                "Placeholder: define wells, ROI masks, and per-well tracking regions. "
                "Future integration with tracker overlays on the live preview."
            )
        )
        lay.addStretch(1)
