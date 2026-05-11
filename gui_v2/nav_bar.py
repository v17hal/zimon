"""Top navigation bar.

Layout: [Logo] [Adult|Larval] [|] [Environment|Protocol Builder|Experiments] [stretch] [Bell] [Avatar] [User ▾]
FPS removed from ribbon — displayed next to camera preview on Adult/Larval pages.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _NotificationPanel(QDialog):
    """Simple notification drop-down panel."""

    def __init__(self, notifications: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Notifications")
        self.setFixedWidth(320)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        header = QLabel("  Notifications")
        header.setObjectName("NotifHeader")
        header.setFixedHeight(36)
        lay.addWidget(header)
        lst = QListWidget()
        lst.setObjectName("NotifList")
        if notifications:
            for n in notifications:
                lst.addItem(n)
        else:
            lst.addItem("No new notifications")
        lay.addWidget(lst)


class NavBar(QFrame):
    page_requested        = pyqtSignal(str)
    mode_changed          = pyqtSignal(str)   # "adult" | "larval"
    logout_clicked        = pyqtSignal()
    manage_users_clicked  = pyqtSignal()

    def __init__(self, user: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user = user
        self._mode = "adult"
        self._notifications: list[str] = []
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

        logo_col = QWidget()
        from PyQt6.QtWidgets import QVBoxLayout as VL
        lc = VL(logo_col)
        lc.setContentsMargins(8, 0, 0, 0)
        lc.setSpacing(0)
        logo_name = QLabel("ZIMON")
        logo_name.setObjectName("NavLogoText")
        logo_sub = QLabel("Zebrafish Integrated Motion & Optical Neuroanalysis Chamber")
        logo_sub.setObjectName("NavLogoSub")
        lc.addWidget(logo_name)
        lc.addWidget(logo_sub)

        lay.addWidget(logo_circle)
        lay.addWidget(logo_col)
        lay.addSpacing(28)

        # ── Adult / Larval mode tabs ──────────────────────────────────────
        mode_grp = QButtonGroup(self)
        mode_grp.setExclusive(True)
        self._btn_adult  = self._mode_tab("Adult",  True)
        self._btn_larval = self._mode_tab("Larval", False)
        mode_grp.addButton(self._btn_adult)
        mode_grp.addButton(self._btn_larval)
        self._btn_adult.clicked.connect(lambda: self._on_mode("adult"))
        self._btn_larval.clicked.connect(lambda: self._on_mode("larval"))
        lay.addWidget(self._btn_adult)
        lay.addSpacing(4)
        lay.addWidget(self._btn_larval)
        lay.addSpacing(16)

        # ── Separator ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setObjectName("NavSep")
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setFixedHeight(28)
        lay.addWidget(sep)
        lay.addSpacing(16)

        # ── Page nav tabs ─────────────────────────────────────────────────
        self._nav_grp = QButtonGroup(self)
        self._nav_grp.setExclusive(True)
        self._nav_btns: dict[str, QPushButton] = {}
        for page_id, label in [
            ("environment",      "Environment"),
            ("protocol_builder", "Protocol Builder"),
            ("experiments",      "Experiments"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("NavTab")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, pid=page_id: self._on_nav(pid))
            self._nav_grp.addButton(btn)
            self._nav_btns[page_id] = btn
            lay.addWidget(btn)
            lay.addSpacing(2)

        lay.addStretch(1)

        # ── Recording indicator ───────────────────────────────────────────
        self._rec_dot = QLabel("● REC")
        self._rec_dot.setObjectName("RecDot")
        self._rec_dot.hide()
        lay.addWidget(self._rec_dot)
        lay.addSpacing(16)

        # ── Notification bell ─────────────────────────────────────────────
        self._bell_btn = QPushButton("🔔")
        self._bell_btn.setObjectName("BellBtn")
        self._bell_btn.setFixedSize(34, 34)
        self._bell_btn.setToolTip("Notifications")
        self._bell_btn.clicked.connect(self._show_notifications)
        lay.addWidget(self._bell_btn)
        lay.addSpacing(8)

        # ── User avatar ───────────────────────────────────────────────────
        initial = self._user.get("username", "U")[0].upper()
        avatar = QLabel(initial)
        avatar.setObjectName("UserAvatar")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(avatar)
        lay.addSpacing(6)

        # ── User menu button (clear, high-contrast) ───────────────────────
        role  = self._user.get("role", "researcher").capitalize()
        uname = self._user.get("username", "User")
        self._user_btn = QPushButton(f"{uname}  ({role})  ▾")
        self._user_btn.setObjectName("UserMenuBtn")
        self._user_btn.clicked.connect(self._show_user_menu)
        lay.addWidget(self._user_btn)

        self._nav_btns["environment"].setChecked(True)

    def _mode_tab(self, label: str, checked: bool) -> QPushButton:
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
        self.page_requested.emit(f"mode_{mode}")

    def _on_nav(self, page_id: str) -> None:
        self.page_requested.emit(page_id)

    def _show_notifications(self) -> None:
        panel = _NotificationPanel(self._notifications, self)
        pos = self._bell_btn.mapToGlobal(self._bell_btn.rect().bottomRight())
        panel.move(pos.x() - panel.width(), pos.y())
        panel.exec()

    def _show_user_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:4px; }
            QMenu::item { padding:8px 20px; color:#1e293b; font-size:13px; }
            QMenu::item:selected { background:#eef2ff; color:#4f46e5; border-radius:6px; }
            QMenu::separator { height:1px; background:#e2e8f0; margin:4px 0; }
        """)
        if self._user.get("role") == "admin":
            act_users = menu.addAction("👥  Manage Users")
            act_users.triggered.connect(self.manage_users_clicked.emit)
            menu.addSeparator()
        act_logout = menu.addAction("🚪  Logout")
        act_logout.triggered.connect(self.logout_clicked.emit)
        menu.exec(self._user_btn.mapToGlobal(self._user_btn.rect().bottomLeft()))

    def highlight(self, page_id: str) -> None:
        if page_id in ("mode_adult", "mode_larval"):
            for btn in self._nav_btns.values():
                btn.setChecked(False)
            (self._btn_adult if page_id == "mode_adult" else self._btn_larval).setChecked(True)
        elif page_id in self._nav_btns:
            self._btn_adult.setChecked(False)
            self._btn_larval.setChecked(False)
            self._nav_btns[page_id].setChecked(True)

    def add_notification(self, msg: str) -> None:
        self._notifications.insert(0, msg)
        if len(self._notifications) > 50:
            self._notifications.pop()
        self._bell_btn.setToolTip(f"Notifications ({len(self._notifications)})")

    def set_fps(self, text: str) -> None:
        pass  # FPS now shown next to camera preview, not in nav

    def set_recording(self, active: bool) -> None:
        self._rec_dot.setVisible(active)
