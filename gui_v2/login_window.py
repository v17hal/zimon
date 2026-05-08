"""Login window — matches PPT mockup: left logo panel, right form, bottom status bar."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from db.database import login


class LoginWindow(QWidget):
    """Shown before MainWindow; emits login_success(user_dict) on success."""

    login_success = pyqtSignal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ZIMON — Login")
        self.setFixedSize(900, 560)
        self.setObjectName("LoginRoot")
        self._build()

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left: branding panel ──────────────────────────────────────────
        left = QFrame()
        left.setObjectName("LoginBrand")
        left.setFixedWidth(360)
        left_lay = QVBoxLayout(left)
        left_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_lay.setSpacing(12)

        logo_lbl = QLabel("ZIMON")
        logo_lbl.setObjectName("LoginLogo")
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tagline = QLabel("Zebrafish Integrated Motion\n& Optical Neuroanalysis Chamber")
        tagline.setObjectName("LoginTagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)

        left_lay.addStretch(2)
        left_lay.addWidget(logo_lbl)
        left_lay.addWidget(tagline)
        left_lay.addStretch(3)

        # ── Right: form panel ─────────────────────────────────────────────
        right_wrap = QVBoxLayout()
        right_wrap.setContentsMargins(0, 0, 0, 0)
        right_wrap.setSpacing(0)

        right = QWidget()
        right.setObjectName("LoginForm")
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(56, 48, 56, 32)
        right_lay.setSpacing(0)

        welcome = QLabel("Welcome to ZIMON")
        welcome.setObjectName("LoginWelcome")
        sub = QLabel("Zebrafish Integrated Motion & Optical\nNeuroanalysis Chamber")
        sub.setObjectName("LoginSub")

        right_lay.addWidget(welcome)
        right_lay.addSpacing(4)
        right_lay.addWidget(sub)
        right_lay.addSpacing(28)

        # Email/username
        right_lay.addWidget(self._field_label("Email or Username"))
        self._email = QLineEdit()
        self._email.setObjectName("LoginInput")
        self._email.setPlaceholderText("Enter your email or username")
        right_lay.addWidget(self._email)
        right_lay.addSpacing(14)

        # Password
        right_lay.addWidget(self._field_label("Password"))
        pw_row = QHBoxLayout()
        pw_row.setSpacing(0)
        self._pw = QLineEdit()
        self._pw.setObjectName("LoginInput")
        self._pw.setPlaceholderText("Enter your password")
        self._pw.setEchoMode(QLineEdit.EchoMode.Password)
        pw_row.addWidget(self._pw)
        right_lay.addLayout(pw_row)
        right_lay.addSpacing(12)

        # Remember me + forgot
        opts = QHBoxLayout()
        self._remember = QCheckBox("Remember me")
        self._remember.setObjectName("LoginCheck")
        self._forgot = QPushButton("Forgot Password?")
        self._forgot.setObjectName("LinkButton")
        self._forgot.setFlat(True)
        self._forgot.clicked.connect(self._on_forgot)
        opts.addWidget(self._remember)
        opts.addStretch(1)
        opts.addWidget(self._forgot)
        right_lay.addLayout(opts)
        right_lay.addSpacing(22)

        # Login button
        self._btn_login = QPushButton("Login  →")
        self._btn_login.setObjectName("LoginButton")
        self._btn_login.setFixedHeight(44)
        self._btn_login.clicked.connect(self._on_login)
        self._pw.returnPressed.connect(self._on_login)
        self._email.returnPressed.connect(lambda: self._pw.setFocus())
        right_lay.addWidget(self._btn_login)
        right_lay.addSpacing(20)

        # Info note: no self-registration
        note = QLabel("New to ZIMON? Contact your administrator to create an account.")
        note.setObjectName("LoginNote")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setWordWrap(True)
        right_lay.addWidget(note)
        right_lay.addStretch(1)

        # Error label (hidden by default)
        self._err = QLabel("")
        self._err.setObjectName("LoginError")
        self._err.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._err.hide()
        right_lay.addWidget(self._err)

        right_wrap.addWidget(right, 1)

        # ── Bottom status bar ─────────────────────────────────────────────
        status_bar = QFrame()
        status_bar.setObjectName("LoginStatusBar")
        status_bar.setFixedHeight(36)
        sb_lay = QHBoxLayout(status_bar)
        sb_lay.setContentsMargins(20, 0, 20, 0)
        sb_lay.setSpacing(32)

        self._cam_status = self._status_chip("Camera", "Connecting…")
        self._chamber_status = self._status_chip("Chamber", "Idle")
        self._temp_status = self._status_chip("Temperature", "—")

        sb_lay.addWidget(self._cam_status)
        sb_lay.addWidget(self._chamber_status)
        sb_lay.addWidget(self._temp_status)
        sb_lay.addStretch(1)

        right_wrap.addWidget(status_bar)

        root.addWidget(left)
        right_container = QWidget()
        right_container.setObjectName("LoginRight")
        right_container.setLayout(right_wrap)
        root.addWidget(right_container, 1)

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("LoginFieldLabel")
        return lbl

    def _status_chip(self, name: str, value: str) -> QLabel:
        lbl = QLabel(f"● {name}: {value}")
        lbl.setObjectName("StatusChipBar")
        return lbl

    def _on_login(self) -> None:
        email = self._email.text().strip()
        pw = self._pw.text()
        if not email or not pw:
            self._show_error("Please enter your email/username and password.")
            return

        self._btn_login.setEnabled(False)
        self._btn_login.setText("Logging in…")
        user = login(email, pw)
        self._btn_login.setEnabled(True)
        self._btn_login.setText("Login  →")

        if user:
            self._err.hide()
            self.login_success.emit(user)
        else:
            self._show_error("Incorrect email/username or password.")

    def _on_forgot(self) -> None:
        QMessageBox.information(
            self, "Forgot Password",
            "Please contact your ZIMON administrator to reset your password."
        )

    def _show_error(self, msg: str) -> None:
        self._err.setText(msg)
        self._err.show()
