"""Change password dialog — shown on first login if default password is still set."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox,
    QMessageBox, QFormLayout, QWidget
)
from PyQt6.QtCore import Qt


class ChangePasswordDialog(QDialog):
    def __init__(self, user: dict, force: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self._force = force
        self._user = user
        self.setWindowTitle("Change Password")
        self.setFixedWidth(380)
        if force:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        self._build(force)

    def _build(self, force: bool) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(24, 20, 24, 20)

        if force:
            warn = QLabel(
                "Security Notice\n\n"
                "You are using the default password. You must set a new password before continuing."
            )
            warn.setObjectName("WarningLabel")
            warn.setWordWrap(True)
            warn.setStyleSheet(
                "background:#fef3c7; border:1px solid #f59e0b; border-radius:8px;"
                " padding:12px; color:#92400e; font-weight:500;"
            )
            lay.addWidget(warn)

        form = QFormLayout()
        form.setSpacing(10)

        if not force:
            self._current = QLineEdit()
            self._current.setEchoMode(QLineEdit.EchoMode.Password)
            self._current.setPlaceholderText("Current password")
            form.addRow("Current Password:", self._current)
        else:
            self._current = None

        self._new_pw = QLineEdit()
        self._new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_pw.setPlaceholderText("At least 8 characters")
        form.addRow("New Password:", self._new_pw)

        self._confirm = QLineEdit()
        self._confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm.setPlaceholderText("Repeat new password")
        form.addRow("Confirm Password:", self._confirm)
        lay.addLayout(form)

        label = "Set Password" if force else "Change Password"
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(label)
        if force:
            btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Logout")
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _validate(self) -> None:
        new_pw = self._new_pw.text()
        confirm = self._confirm.text()
        if len(new_pw) < 8:
            QMessageBox.warning(self, "Too Short", "Password must be at least 8 characters.")
            return
        if new_pw != confirm:
            QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
            return
        if not self._force and self._current:
            from db.database import login
            if not login(self._user.get("email", ""), self._current.text()):
                QMessageBox.warning(self, "Wrong Password", "Current password is incorrect.")
                return
        self.accept()

    def new_password(self) -> str:
        return self._new_pw.text()
