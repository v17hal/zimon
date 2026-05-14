#!/usr/bin/env python3
"""ZIMON — unified entry point with login -> main window flow."""

import json
import logging
import os
import sys
import traceback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_PREFS_PATH = os.path.join(os.path.expanduser("~"), ".zimon", "prefs.json")


def _load_prefs() -> dict:
    try:
        with open(_PREFS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_prefs(prefs: dict) -> None:
    os.makedirs(os.path.dirname(_PREFS_PATH), exist_ok=True)
    with open(_PREFS_PATH, "w") as f:
        json.dump(prefs, f)


def main() -> int:
    from db.database import init_db
    init_db()

    from PyQt6.QtWidgets import QApplication, QDialog
    from gui_v2.main_window import load_styles

    app = QApplication(sys.argv)
    app.setApplicationName("ZIMON")
    load_styles(app)

    while True:
        app.setProperty("logout_requested", False)

        logged_in_user: dict | None = None
        active_session_token: str | None = None

        # ── Try auto-login via saved session token ────────────────────────
        prefs = _load_prefs()
        saved_token = prefs.get("session_token")
        if saved_token:
            from db.database import validate_session
            user = validate_session(saved_token)
            if user:
                logged_in_user = user
                active_session_token = saved_token
                logging.info("Auto-login via session token for user %s", user.get("username"))

        # ── Show login window if no valid session ─────────────────────────
        if logged_in_user is None:
            from gui_v2.login_window import LoginWindow
            login_win = LoginWindow()

            def _on_success(user: dict, token: str | None) -> None:
                nonlocal logged_in_user, active_session_token
                logged_in_user = user
                active_session_token = token
                login_win.close()

            login_win.login_success.connect(_on_success)
            login_win.show()
            app.exec()

            if logged_in_user is None:
                break   # Closed login without logging in

        # ── Force password change if still using default ──────────────────
        from db.database import is_default_password, update_user
        if is_default_password(logged_in_user["id"]):
            from gui_v2.change_password_dialog import ChangePasswordDialog
            dlg = ChangePasswordDialog(logged_in_user, force=True)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                # User cancelled / chose Logout — clear session and loop back
                if active_session_token:
                    from db.database import delete_session
                    delete_session(active_session_token)
                    prefs = _load_prefs()
                    prefs.pop("session_token", None)
                    _save_prefs(prefs)
                    active_session_token = None
                logged_in_user = None
                continue
            update_user(logged_in_user["id"], password=dlg.new_password())

        # ── Show main window ──────────────────────────────────────────────
        from gui_v2.main_window import MainWindowV2
        win = MainWindowV2(logged_in_user)
        win.show()
        app.exec()

        # ── Handle logout ─────────────────────────────────────────────────
        if not app.property("logout_requested"):
            break   # Normal window close — end the app

        # Logout was requested — clear session so login screen appears
        if active_session_token:
            from db.database import delete_session
            delete_session(active_session_token)
            prefs = _load_prefs()
            prefs.pop("session_token", None)
            _save_prefs(prefs)
            active_session_token = None

    return 0


if __name__ == "__main__":
    try:
        code = main()
        sys.exit(code)
    except Exception:
        logging.exception("ZIMON failed to start")
        traceback.print_exc()
        print(
            "\n---\n"
            "If the window never appeared, common causes:\n"
            "  * Missing package:  pip install PyQt6 opencv-python numpy pyserial\n"
            "  * FLIR/PySpin is optional unless you use a FLIR camera.\n",
            file=sys.stderr,
        )
        if sys.platform == "win32":
            try:
                input("\nPress Enter to close this window... ")
            except EOFError:
                pass
        sys.exit(1)
