"""Main window: NavBar + full-width stacked pages + BottomBar.

Video is embedded inside Adult/Larval pages — no persistent video panel.
"""

from __future__ import annotations

import os
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QMainWindow,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui_v2.hardware_bridge import HardwareBridge
from gui_v2.nav_bar import NavBar
from gui_v2.bottom_bar import BottomBar
from gui_v2.user_management import UserManagementDialog
from gui_v2.pages import (
    EnvironmentPage,
    StimulusPage,
    RecordingPage,
    SettingsPage,
    MultiAnglePage,
    WellRoiPage,
)
from gui_v2.pages.protocol_builder_page import ProtocolBuilderPage


def _wrap(w: QWidget) -> QScrollArea:
    s = QScrollArea()
    s.setWidgetResizable(True)
    s.setFrameShape(QFrame.Shape.NoFrame)
    s.setWidget(w)
    return s


class MainWindowV2(QMainWindow):
    def __init__(self, user: dict) -> None:
        super().__init__()
        self._user = user
        try:
            from version import __version__ as ver
        except ImportError:
            ver = "2.0.0"
        self.setWindowTitle(f"ZIMON v{ver}")
        self.resize(1280, 820)

        self._bridge = HardwareBridge()
        self._bridge.set_recording_error_handler(self._on_recording_error)
        self._bridge.set_recording_stopped_handler(self._on_recording_stopped)
        self._bridge.set_recording_started_handler(self._on_recording_started)
        self._recording_page: RecordingPage | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._nav = NavBar(user)
        root.addWidget(self._nav)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        self._bottom = BottomBar()
        root.addWidget(self._bottom)

        self._build_pages()
        self._wire()

        self._fps_timer = QTimer(self)
        self._fps_timer.timeout.connect(self._tick_fps)
        self._fps_timer.start(500)

        self._temp_timer = QTimer(self)
        self._temp_timer.timeout.connect(self._tick_temp)
        self._temp_timer.start(4000)

        QTimer.singleShot(600, self._start_default_camera)

        self._show_page("mode_adult")
        self._nav.highlight("mode_adult")

    # ── Page building ────────────────────────────────────────────────────────

    def _build_pages(self) -> None:
        self._recording_page = RecordingPage(self._bridge)

        # Try to import Adult/Experiments pages — fall back to stubs if not yet built
        adult_widget   = self._try_adult_page()
        exp_widget     = self._try_experiments_page()

        larval_widget  = self._try_larval_page()

        pages: list[tuple[str, QWidget]] = [
            ("mode_adult",       adult_widget),
            ("mode_larval",      larval_widget),
            ("environment",      EnvironmentPage(self._bridge)),
            ("protocol_builder", ProtocolBuilderPage(self._bridge, self._user)),
            ("experiments",      exp_widget),
            ("stimulus",         StimulusPage(self._bridge)),
            ("recording",        self._recording_page),
            ("settings",         SettingsPage(self._bridge)),
            ("multi_angle",      MultiAnglePage(self._bridge)),
            ("well_roi",         WellRoiPage(self._bridge)),
        ]

        self._page_map: dict[str, int] = {}
        for i, (key, w) in enumerate(pages):
            self._page_map[key] = i
            # Adult/Larval/Experiments pages are full-width — don't wrap in scroll
            if key in ("mode_adult", "mode_larval", "experiments"):
                self._stack.addWidget(w)
            else:
                self._stack.addWidget(_wrap(w))

    def _try_adult_page(self) -> QWidget:
        try:
            from gui_v2.pages.adult_page import AdultPage
            p = AdultPage(self._bridge)
            p.navigate_to.connect(self._show_page)
            return p
        except Exception as e:
            return self._make_stub("Adult Mode", f"Adult page loading… ({e})")

    def _try_larval_page(self) -> QWidget:
        try:
            from gui_v2.pages.larval_page import LarvalPage
            p = LarvalPage(self._bridge)
            p.navigate_to.connect(self._show_page)
            return p
        except Exception as e:
            return self._make_stub("Larval Mode", f"Larval page loading… ({e})")

    def _try_experiments_page(self) -> QWidget:
        try:
            from gui_v2.pages.experiments_page import ExperimentsPage
            return ExperimentsPage(self._bridge)
        except Exception as e:
            return self._make_stub("Experiments", f"Experiments page loading… ({e})")

    def _make_stub(self, title: str, subtitle: str = "") -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("DeviceSub")
            s.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(s)
        return w

    # ── Wiring ───────────────────────────────────────────────────────────────

    def _wire(self) -> None:
        self._nav.page_requested.connect(self._show_page)
        self._nav.mode_changed.connect(self._on_mode)
        self._nav.logout_clicked.connect(self._on_logout)
        self._nav.manage_users_clicked.connect(self._on_manage_users)

    def _start_default_camera(self) -> None:
        cameras = self._bridge.camera_manager.list_cameras()
        if cameras:
            self._bridge.start_camera_preview(cameras[0])
            self._bottom.set_camera(cameras[0], True)

    # ── Page navigation ──────────────────────────────────────────────────────

    def _show_page(self, page_id: str) -> None:
        idx = self._page_map.get(page_id)
        if idx is None:
            return
        self._stack.setCurrentIndex(idx)
        self._nav.highlight(page_id)

    # ── Mode ─────────────────────────────────────────────────────────────────

    def _on_mode(self, mode: str) -> None:
        if mode == "adult":
            self._bridge.set_mode_adult()
        else:
            self._bridge.set_mode_larval()

    # ── Camera / recording callbacks ─────────────────────────────────────────

    def _on_recording_error(self, message: str) -> None:
        self._nav.set_recording(False)
        if self._recording_page:
            self._recording_page.sync_idle_state()

    def _on_recording_stopped(self, _path: str) -> None:
        self._nav.set_recording(False)
        if self._recording_page:
            self._recording_page.sync_idle_state()

    def _on_recording_started(self) -> None:
        self._nav.set_recording(True)

    # ── Timers ───────────────────────────────────────────────────────────────

    def _tick_fps(self) -> None:
        # FPS now shown next to camera preview on Adult/Larval pages, not in nav
        pass

    def _tick_temp(self) -> None:
        ard = getattr(self._bridge, "_arduino", None)
        connected = ard is not None and ard.is_connected()
        self._bottom.set_arduino_status(connected)
        if connected:
            try:
                t = ard.read_temperature_c()
                if t is not None:
                    self._bottom.set_temperature(f"{t:.1f} °C")
                    return
            except Exception:
                pass
        self._bottom.set_temperature("—")

    # ── User actions ─────────────────────────────────────────────────────────

    def _on_logout(self) -> None:
        from PyQt6.QtWidgets import QMessageBox
        if QMessageBox.question(self, "Logout", "Log out of ZIMON?") == QMessageBox.StandardButton.Yes:
            self._bridge.stop_camera_preview()
            self._bridge.stop_recording()
            self.close()
            app = QApplication.instance()
            app.setProperty("logout_requested", True)
            app.quit()

    def _on_manage_users(self) -> None:
        dlg = UserManagementDialog(self)
        dlg.exec()


def load_styles(app: QApplication) -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    qss = os.path.join(here, "styles_v2.qss")
    if os.path.isfile(qss):
        with open(qss, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
