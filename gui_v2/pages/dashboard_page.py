"""Dashboard — summary cards + quick actions (context panel, ~30%)."""

from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class DashboardPage(QWidget):
    def __init__(self, bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        cards = QGridLayout()
        cards.setHorizontalSpacing(12)
        cards.setVerticalSpacing(12)

        def stat_card(r: int, c: int, title: str, value: str) -> None:
            box = QFrame()
            box.setFrameShape(QFrame.Shape.NoFrame)
            box.setObjectName("StatCard")
            lay = QVBoxLayout(box)
            lay.setContentsMargins(12, 10, 12, 10)
            lay.setSpacing(4)
            title_lbl = QLabel(title)
            title_lbl.setObjectName("StatCardTitle")
            value_lbl = QLabel(value)
            value_lbl.setObjectName("StatCardValue")
            lay.addWidget(title_lbl)
            lay.addWidget(value_lbl)
            cards.addWidget(box, r, c)

        stat_card(0, 0, "Camera", "Status: —")
        stat_card(0, 1, "FPS", "—")
        stat_card(1, 0, "Recording", "Not recording")
        stat_card(1, 1, "Mode", "Adult / Larval")
        root.addLayout(cards)

        quick = QGroupBox("Quick controls")
        q_lay = QHBoxLayout(quick)
        self.btn_cam = QPushButton("Start camera")
        self.btn_cam_stop = QPushButton("Stop camera")
        self.btn_rec = QPushButton("Start recording")
        self.btn_rec_stop = QPushButton("Stop recording")
        q_lay.addWidget(self.btn_cam)
        q_lay.addWidget(self.btn_cam_stop)
        q_lay.addWidget(self.btn_rec)
        q_lay.addWidget(self.btn_rec_stop)
        root.addWidget(quick)

        root.addStretch(1)

        # Wire to placeholder handlers (MainWindow may reconnect)
        self.btn_cam.clicked.connect(self._bridge.start_first_camera_preview)
        self.btn_cam_stop.clicked.connect(self._bridge.stop_camera_preview)
