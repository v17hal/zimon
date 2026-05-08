"""Admin-only user management dialog — create / edit / deactivate users."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from db import database as db


class UserManagementDialog(QDialog):
    """Full CRUD for users — only admin can open this."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("User Management — Admin")
        self.setMinimumSize(720, 480)
        self._build()
        self._load()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Users")
        title.setObjectName("PageTitle")
        btn_new = QPushButton("+ Create User")
        btn_new.setObjectName("PrimaryButton")
        btn_new.clicked.connect(self._create_user)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(btn_new)
        lay.addLayout(header)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["ID", "Username", "Email", "Role", "Actions"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lay.addWidget(self._table)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        lay.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def _load(self) -> None:
        users = db.list_users()
        self._table.setRowCount(len(users))
        for row, u in enumerate(users):
            self._table.setItem(row, 0, QTableWidgetItem(str(u["id"])))
            self._table.setItem(row, 1, QTableWidgetItem(u["username"]))
            self._table.setItem(row, 2, QTableWidgetItem(u["email"]))
            role_lbl = QTableWidgetItem(u["role"].capitalize())
            if u["role"] == "admin":
                role_lbl.setForeground(Qt.GlobalColor.cyan)
            self._table.setItem(row, 3, role_lbl)

            act = QWidget()
            act_lay = QHBoxLayout(act)
            act_lay.setContentsMargins(4, 2, 4, 2)
            act_lay.setSpacing(6)

            uid = u["id"]
            btn_edit = QPushButton("Edit")
            btn_edit.setObjectName("SmallButton")
            btn_edit.clicked.connect(lambda _, i=uid: self._edit_user(i))
            act_lay.addWidget(btn_edit)

            if u["active"]:
                btn_deact = QPushButton("Deactivate")
                btn_deact.setObjectName("SmallDangerButton")
                btn_deact.clicked.connect(lambda _, i=uid: self._deactivate(i))
                act_lay.addWidget(btn_deact)

            self._table.setCellWidget(row, 4, act)

    def _create_user(self) -> None:
        dlg = _UserFormDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.data()
            try:
                db.create_user(data["username"], data["email"], data["password"], data["role"])
                self._load()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _edit_user(self, uid: int) -> None:
        users = {u["id"]: u for u in db.list_users()}
        u = users.get(uid)
        if not u:
            return
        dlg = _UserFormDialog(self, user=u)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.data()
            try:
                db.update_user(uid, email=data["email"], role=data["role"],
                               password=data["password"] or None)
                self._load()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _deactivate(self, uid: int) -> None:
        if QMessageBox.question(self, "Confirm", "Deactivate this user?") == QMessageBox.StandardButton.Yes:
            db.delete_user(uid)
            self._load()


class _UserFormDialog(QDialog):
    def __init__(self, parent=None, user: dict | None = None) -> None:
        super().__init__(parent)
        self._user = user
        self.setWindowTitle("Edit User" if user else "Create User")
        self.setFixedSize(400, 300)
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._username = QLineEdit(self._user["username"] if self._user else "")
        self._username.setReadOnly(bool(self._user))
        self._email = QLineEdit(self._user["email"] if self._user else "")
        self._pw = QLineEdit()
        self._pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw.setPlaceholderText("Leave blank to keep current" if self._user else "Required")
        self._role = QComboBox()
        self._role.addItems(["researcher", "student", "admin"])
        if self._user:
            idx = self._role.findText(self._user["role"])
            if idx >= 0:
                self._role.setCurrentIndex(idx)

        form.addRow("Username:", self._username)
        form.addRow("Email:", self._email)
        form.addRow("Password:", self._pw)
        form.addRow("Role:", self._role)
        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def data(self) -> dict:
        return {
            "username": self._username.text().strip(),
            "email": self._email.text().strip(),
            "password": self._pw.text(),
            "role": self._role.currentText(),
        }
