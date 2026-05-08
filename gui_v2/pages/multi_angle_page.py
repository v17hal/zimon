"""Adult mode — multi-angle / camera switching (placeholder)."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class MultiAnglePage(QWidget):
    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        lay = QVBoxLayout(self)
        t = QLabel("Multi-angle / camera switching")
        t.setObjectName("PageTitle")
        lay.addWidget(t)
        lay.addWidget(
            QLabel(
                "Placeholder: assign multiple camera angles, switch views, "
                "and sync with recording. Wire to HardwareBridge when hardware is ready."
            )
        )
        lay.addStretch(1)
