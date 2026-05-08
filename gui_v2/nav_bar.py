"""Top navigation bar — matches PPT mockup exactly.

Layout: [Logo] [Adult|Larval mode tabs] [|] [Environment|Protocol Builder|Experiments] [stretch] [FPS] [Bell] [Avatar] [User▾]
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QWidget,
)


class NavBar(QFrame):
    page_requested        = pyqtSignal(str)   # page_id
    mode_changed          = pyqtSignal(str)   # "adult" | "larval"
    logout_clicked        = pyqtSignal()
    manage_users_clicked  = pyqtSignal()

    def __init__(self, user: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user = user
        self._mode = "adult"
        self.setObjectName("NavBar")
        self.setFixedHeight(60)
        self._build()

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(0)

        # ── Logo ─────────────────────────────────────────────────────────
        logo_circle = QLabel("Z")
        logo_circle.setObjectName("NavLogoCircle")
        logo_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_text_col = QWidget()
        ltc = QHBoxLayout(logo_text_col)
        ltc.setContentsMargins(8, 0, 0, 0)
        ltc.setSpacing(0)
        text_stack = QWidget()
        from PyQt6.QtWidgets import QVBoxLayout
        ts = QVBoxLayout(text_stack)
        ts.setContentsMargins(0, 0, 0, 0)
        ts.setSpacing(0)
        logo_name = QLabel("ZIMON")
        logo_name.setObjectName("NavLogoText")
        logo_sub  = QLabel("Zebrafish Integrated Motion &\nOptical Neuroanalysis Chamber")
        logo_sub.setObjectName("NavLogoSub")
        ts.addWidget(logo_name)
        ts.addWidget(logo_sub)
        ltc.addWidget(text_stack)

        lay.addWidget(logo_circle)
        lay.addWidget(logo_text_col)
        lay.addSpacing(28)

        # ── Adult / Larval mode tabs ──────────────────────────────────────
        mode_group = QButtonGroup(self)
        mode_group.setExclusive(True)

        self._btn_adult  = self._mode_tab("Adult",  "adult",  True)
        self._btn_larval = self._mode_tab("Larval", "larval", False)
        mode_group.addButton(self._btn_adult)
        mode_group.addButton(self._btn_larval)
        self._btn_adult.clicked.connect(lambda: self._on_mode("adult"))
        self._btn_larval.clicked.connect(lambda: self._on_mode("larval"))

        lay.addWidget(self._btn_adult)
        lay.addSpacing(4)
        lay.addWidget(self._btn_larval)
        lay.addSpacing(16)

        # Vertical separator
        sep = QFrame()
        sep.setObjectName("NavSep")
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setFixedHeight(28)
        lay.addWidget(sep)
        lay.addSpacing(16)

        # ── Page nav tabs ─────────────────────────────────────────────────
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_btns: dict[str, QPushButton] = {}

        nav_items = [
            ("environment",      "Environment"),
            ("protocol_builder", "Protocol Builder"),
            ("experiments",      "Experiments"),
        ]

        for page_id, label in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("NavTab")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, pid=page_id: self._on_nav(pid))
            self._nav_group.addButton(btn)
            self._nav_btns[page_id] = btn
            lay.addWidget(btn)
            lay.addSpacing(2)

        lay.addStretch(1)

        # ── Right side ────────────────────────────────────────────────────
        self._rec_dot = QLabel("● REC")
        self._rec_dot.setObjectName("RecDot")
        self._rec_dot.hide()
        lay.addWidget(self._rec_dot)
        lay.addSpacing(12)

        self._fps_lbl = QLabel("")
        self._fps_lbl.setObjectName("NavFps")
        lay.addWidget(self._fps_lbl)
        lay.addSpacing(12)

        # Bell
        bell = QPushButton("🔔")
        bell.setObjectName("BellBtn")
        bell.setFixedSize(32, 32)
        lay.addWidget(bell)
        lay.addSpacing(8)

        # Avatar circle
        initial = self._user.get("username", "U")[0].upper()
        avatar = QLabel(initial)
        avatar.setObjectName("UserAvatar")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(avatar)
        lay.addSpacing(6)

        # User name + role
        role  = self._user.get("role", "researcher").capitalize()
        uname = self._user.get("username", "User")
        self._user_btn = QPushButton(f"{role}  ▾")
        self._user_btn.setObjectName("UserChip")
        self._user_btn.clicked.connect(self._show_user_menu)
        lay.addWidget(self._user_btn)

        # Activate environment tab by default
        self._nav_btns["environment"].setChecked(True)

    def _mode_tab(self, label: str, mode: str, checked: bool) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("ModeTab")
        btn.setCheckable(True)
        btn.setChecked(checked)
        return btn

    def _on_mode(self, mode: str) -> None:
        if mode == self._mode:
            return
        self._mode = mode
        self.mode_changed.emit(mode)
        # Mode tabs show the Adult/Larval experiment page
        self.page_requested.emit(f"mode_{mode}")

    def _on_nav(self, page_id: str) -> None:
        self.page_requested.emit(page_id)

    def _show_user_menu(self) -> None:
        menu = QMenu(self)
        if self._user.get("role") == "admin":
            menu.addAction("Manage Users", self.manage_users_clicked.emit)
            menu.addSeparator()
        menu.addAction("Logout", self.logout_clicked.emit)
        menu.exec(self._user_btn.mapToGlobal(self._user_btn.rect().bottomLeft()))

    def highlight(self, page_id: str) -> None:
        if page_id in ("mode_adult", "mode_larval"):
            # Deselect nav tabs, select mode tab
            for btn in self._nav_btns.values():
                btn.setChecked(False)
            if page_id == "mode_adult":
                self._btn_adult.setChecked(True)
            else:
                self._btn_larval.setChecked(True)
        elif page_id in self._nav_btns:
            self._btn_adult.setChecked(False)
            self._btn_larval.setChecked(False)
            self._nav_btns[page_id].setChecked(True)

    def set_fps(self, text: str) -> None:
        self._fps_lbl.setText(f"FPS {text}" if text != "—" else "")

    def set_recording(self, active: bool) -> None:
        self._rec_dot.setVisible(active)
