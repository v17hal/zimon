#!/usr/bin/env python3
"""ZIMON — unified entry point with login -> main window flow."""

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


def main() -> int:
    from db.database import init_db
    init_db()

    from PyQt6.QtWidgets import QApplication
    from gui_v2.main_window import load_styles

    app = QApplication(sys.argv)
    app.setApplicationName("ZIMON")
    load_styles(app)

    while True:
        app.setProperty("logout_requested", False)

        # Show login
        from gui_v2.login_window import LoginWindow
        login_win = LoginWindow()
        logged_in_user: dict | None = None

        def _on_success(user: dict) -> None:
            nonlocal logged_in_user
            logged_in_user = user
            login_win.close()

        login_win.login_success.connect(_on_success)
        login_win.show()
        app.exec()

        if logged_in_user is None:
            break   # Closed login without logging in

        # Show main window
        from gui_v2.main_window import MainWindowV2
        win = MainWindowV2(logged_in_user)
        win.show()
        app.exec()

        if not app.property("logout_requested"):
            break   # Normal close

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
