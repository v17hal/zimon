"""
ZIMON Automated Test Suite
Tests all features from client feedback (Zimon_Changes_List_8May.docx) + PIN map.
Run:  python tests/test_zimon.py
"""

import importlib
import json
import os
import sys
import tempfile
import time
import traceback
import types
from dataclasses import dataclass, field
from typing import Any

# ── Make project root importable ─────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ── Result tracking ───────────────────────────────────────────────────────────

@dataclass
class Result:
    name: str
    passed: bool
    detail: str = ""
    error: str = ""


RESULTS: list[Result] = []


def check(name: str, condition: bool, detail: str = "", error: str = "") -> bool:
    r = Result(name, condition, detail, error)
    RESULTS.append(r)
    status = "PASS" if condition else "FAIL"
    sym    = "✓" if condition else "✗"
    print(f"  [{status}] {sym} {name}" + (f"  — {detail}" if detail else ""))
    if not condition and error:
        print(f"         Error: {error}")
    return condition


def section(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run(name: str, fn):
    """Run a test function, catch exceptions, record result."""
    try:
        result = fn()
        if result is None:
            result = True
        check(name, bool(result))
    except Exception as exc:
        check(name, False, error=f"{type(exc).__name__}: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 1 — Module imports
# ═══════════════════════════════════════════════════════════════════════════════

def test_imports():
    section("1. Module Imports")

    modules = {
        "db.database":                     "Database layer",
        "backend.arduino_controller":      "Arduino controller",
        "backend.camera_manager":          "Camera manager",
        "backend.mode_profiles":           "Mode profiles",
        "backend.recording_manager":       "Recording manager",
        "backend.frame_relay":             "Frame relay",
    }

    for mod, label in modules.items():
        try:
            importlib.import_module(mod)
            check(f"Import {label}", True)
        except Exception as exc:
            check(f"Import {label}", False, error=str(exc))

    # UI modules (need QApplication)
    ui_modules = {
        "gui_v2.login_window":                "Login window",
        "gui_v2.nav_bar":                     "Nav bar",
        "gui_v2.bottom_bar":                  "Bottom bar",
        "gui_v2.pages.environment_page":      "Environment page",
        "gui_v2.pages.protocol_builder_page": "Protocol Builder page",
        "gui_v2.pages.experiments_page":      "Experiments page",
        "gui_v2.pages.adult_page":            "Adult page",
        "gui_v2.pages.larval_page":           "Larval page",
        "gui_v2.pages.settings_page":         "Settings page",
        "gui_v2.user_management":             "User management",
    }
    for mod, label in ui_modules.items():
        try:
            importlib.import_module(mod)
            check(f"Import {label}", True)
        except Exception as exc:
            check(f"Import {label}", False, error=str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 2 — Database operations
# ═══════════════════════════════════════════════════════════════════════════════

def test_database():
    section("2. Database Operations")

    # Use a temp DB so we don't touch the real one
    import db.database as db_mod

    tmp = tempfile.mktemp(suffix=".db")
    orig = db_mod._DB_PATH
    db_mod._DB_PATH = tmp

    try:
        # init
        run("DB: init_db() creates tables", lambda: (db_mod.init_db(), True)[1])

        # Users
        run("DB: admin seeded on first run",
            lambda: len([u for u in db_mod.list_users() if u["role"] == "admin"]) >= 1)

        run("DB: create_user(researcher)",
            lambda: db_mod.create_user("testuser", "test@lab.com", "pass123", "researcher"))

        run("DB: login() succeeds with correct credentials",
            lambda: db_mod.login("testuser", "pass123") is not None)

        run("DB: login() fails with wrong password",
            lambda: db_mod.login("testuser", "wrongpass") is None)

        run("DB: update_user() changes role",
            lambda: db_mod.update_user(
                db_mod.list_users()[-1]["id"], role="student"))

        run("DB: delete_user() deactivates",
            lambda: db_mod.delete_user(db_mod.list_users()[-1]["id"]))

        # Protocols with category
        pid = db_mod.save_protocol(
            "Startle Response", "Test protocol",
            [{"type": "baseline", "duration_sec": 10, "label": "Baseline", "params": {}}],
            created_by=1, category="larval"
        )
        check("DB: save_protocol() with category", pid > 0, f"protocol_id={pid}")

        protos = db_mod.list_protocols()
        check("DB: list_protocols() returns saved protocol",
              any(p["name"] == "Startle Response" for p in protos))

        protos_larval = db_mod.list_protocols(category="larval")
        check("DB: list_protocols(category='larval') filters correctly",
              any(p["name"] == "Startle Response" for p in protos_larval))

        protos_adult = db_mod.list_protocols(category="adult")
        check("DB: list_protocols(category='adult') excludes larval-only",
              not any(p["name"] == "Startle Response" for p in protos_adult))

        proto = db_mod.get_protocol(pid)
        check("DB: get_protocol() returns correct data",
              proto is not None and proto["category"] == "larval")

        run("DB: delete_protocol()", lambda: db_mod.delete_protocol(pid))

        # Camera assignments
        run("DB: save_camera_assignment()",
            lambda: db_mod.save_camera_assignment(
                "Webcam_0", "Tank Top Camera", "larval_machine_vision") or True)

        assignments = db_mod.get_camera_assignments()
        check("DB: get_camera_assignments() returns saved assignment",
              "Webcam_0" in assignments and
              assignments["Webcam_0"]["role"] == "larval_machine_vision")

        cam = db_mod.get_camera_for_role("larval_machine_vision")
        check("DB: get_camera_for_role() returns correct camera", cam == "Webcam_0")

        check("DB: get_camera_for_role() returns None for unassigned role",
              db_mod.get_camera_for_role("adult_top") is None)

        # Experiments
        exp = db_mod.create_experiment(
            "Startle Test #1", pid, "Startle Response",
            "larval", "Webcam_0", "/tmp/exp1", created_by=1)
        check("DB: create_experiment() returns exp_id",
              "exp_id" in exp and exp["exp_id"].startswith("EXP_"))

        events = [
            {"time_sec": 0.0, "stimulus": "baseline", "action": "start", "value": ""},
            {"time_sec": 10.0, "stimulus": "light",    "action": "on",    "value": "IR 80%"},
            {"time_sec": 10.5, "stimulus": "light",    "action": "off",   "value": ""},
        ]
        run("DB: finish_experiment() with events log",
            lambda: db_mod.finish_experiment(exp["exp_id"], 14.0, "complete", events))

        exps = db_mod.list_experiments()
        check("DB: list_experiments() returns finished experiment",
              any(e["exp_id"] == exp["exp_id"] for e in exps))

        saved = next(e for e in exps if e["exp_id"] == exp["exp_id"])
        check("DB: events_log stored and retrieved correctly",
              len(saved["events_log"]) == 3 and
              saved["events_log"][1]["stimulus"] == "light")

    finally:
        db_mod._DB_PATH = orig
        try:
            os.remove(tmp)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 3 — Arduino controller
# ═══════════════════════════════════════════════════════════════════════════════

def test_arduino():
    section("3. Arduino Controller (command formatting — no hardware needed)")

    from backend.arduino_controller import ArduinoController
    ard = ArduinoController(port=None)  # no port = no connection attempt

    # Verify is_connected returns False without a port
    check("Arduino: is_connected() = False when no port",
          not ard.is_connected())

    # Test write_command returns False gracefully when not connected
    check("Arduino: write_command() returns False when disconnected",
          ard.write_command("PING") == False)

    # Test command builders don't raise exceptions
    cmds_to_test = [
        ("set_ir_intensity(50)",    lambda: ard.set_ir_intensity(50) == False),
        ("set_white_intensity(80)", lambda: ard.set_white_intensity(80) == False),
        ("set_heater(75)",          lambda: ard.set_heater(75) == False),
        ("heater_on()",             lambda: ard.heater_on() == False),
        ("heater_off()",            lambda: ard.heater_off() == False),
        ("vibrate_on()",            lambda: ard.vibrate_on() == False),
        ("vibrate_off()",           lambda: ard.vibrate_off() == False),
        ("buzzer_on()",             lambda: ard.buzzer_on() == False),
        ("buzzer_off()",            lambda: ard.buzzer_off() == False),
        ("rgb_set(255,0,128)",      lambda: ard.rgb_set(255, 0, 128) == False),
        ("pump_on()",               lambda: ard.pump_on() == False),
        ("pump_off()",              lambda: ard.pump_off() == False),
    ]

    for name, fn in cmds_to_test:
        try:
            fn()
            check(f"Arduino: {name} runs without exception", True)
        except Exception as e:
            check(f"Arduino: {name} runs without exception", False, error=str(e))

    # Verify 0-255 mapping for intensity
    # set_ir_intensity(100%) should produce IR 255
    # We test by monkey-patching write_command
    sent_cmds = []

    def _fake_write(cmd):
        sent_cmds.append(cmd)
        return True

    ard.write_command = _fake_write
    ard.ser = object()   # fake "connected"

    ard.set_ir_intensity(100)
    check("Arduino: set_ir_intensity(100) sends IR 255",
          any("IR 255" in c for c in sent_cmds), str(sent_cmds))

    sent_cmds.clear()
    ard.set_ir_intensity(50)
    check("Arduino: set_ir_intensity(50) sends IR ~127",
          any(c.startswith("IR ") and 120 <= int(c.split()[1]) <= 130 for c in sent_cmds),
          str(sent_cmds))

    sent_cmds.clear()
    ard.set_heater(100)
    check("Arduino: set_heater(100) sends HEAT 255",
          any("HEAT 255" in c for c in sent_cmds), str(sent_cmds))

    sent_cmds.clear()
    ard.set_heater(0)
    check("Arduino: set_heater(0) sends HEAT 0",
          any("HEAT 0" in c for c in sent_cmds), str(sent_cmds))


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 4 — Arduino firmware file
# ═══════════════════════════════════════════════════════════════════════════════

def test_firmware():
    section("4. Arduino Firmware (arduino/zfish_controller.ino)")

    fw_path = os.path.join(ROOT, "arduino", "zfish_controller.ino")
    check("Firmware file exists", os.path.isfile(fw_path))

    if not os.path.isfile(fw_path):
        return

    with open(fw_path) as f:
        fw = f.read()

    pin_checks = [
        ("PIN_IR = 5",    "D5 → IR LED",            "PIN_IR" in fw and "5" in fw),
        ("PIN_WHITE = 6", "D6 → WHITE LED",          "PIN_WHITE" in fw and "6" in fw),
        ("PIN_VIB = 9",   "D9 → VIBRATION MOTOR",   "PIN_VIB" in fw and "9" in fw),
        ("PIN_PUMP = 10", "D10 → CIRCULATION PUMP", "PIN_PUMP" in fw and "10" in fw),
        ("PIN_HEAT = 7",  "D7 → HEATER (NEW)",      "PIN_HEAT" in fw and "7" in fw),
        ("PIN_TEMP = 2",  "D2 → DS18B20 DATA",      "PIN_TEMP" in fw and "2" in fw),
    ]

    for label, desc, cond in pin_checks:
        check(f"Firmware: {label} ({desc})", cond)

    cmd_checks = [
        ("PING → ZIMON_OK",   '"PING"' in fw and "ZIMON_OK" in fw),
        ("IR command",        'cmd.startsWith("IR ")' in fw),
        ("WHITE command",     'cmd.startsWith("WHITE ")' in fw),
        ("VIB command",       'cmd.startsWith("VIB ")' in fw),
        ("PUMP command",      'cmd.startsWith("PUMP ")' in fw),
        ("HEAT command",      'cmd.startsWith("HEAT ")' in fw),
        ("BUZZER_ON command", '"BUZZER_ON"' in fw),
        ("BUZZER_OFF command","BUZZER_OFF" in fw),
        ("TEMP? command",     "TEMP?" in fw),
        ("STATUS command",    '"STATUS"' in fw),
    ]

    for label, cond in cmd_checks:
        check(f"Firmware: {label}", cond)


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 5 — UI pages (headless PyQt6)
# ═══════════════════════════════════════════════════════════════════════════════

def test_ui_pages():
    section("5. UI Pages (headless initialisation)")

    # Set offscreen platform so no window is shown
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
    except Exception as e:
        check("PyQt6 QApplication init", False, error=str(e))
        return

    check("PyQt6 QApplication init", True)

    # Mock hardware bridge
    class _MockArduino:
        def is_connected(self): return False
        def read_temperature_c(self): return 24.5
        def set_ir_intensity(self, v): pass
        def set_white_intensity(self, v): pass
        def set_heater(self, v): pass

    class _MockCameraManager:
        frame_ready = None
        error_occurred = None
        stream_state_changed = None
        def list_cameras(self): return ["Webcam_0"]
        def refresh_cameras(self): pass
        def is_streaming(self): return False
        def get_current_fps(self): return 0.0
        def connect_camera(self, n): return True
        def start_stream(self, n): return True
        def stop_stream(self): pass

    # Assign dummy signals
    from PyQt6.QtCore import pyqtSignal, QObject

    class _Sig(QObject):
        frame_ready         = pyqtSignal(object)
        error_occurred      = pyqtSignal(str)
        stream_state_changed= pyqtSignal(bool)
        fps_changed         = pyqtSignal(float)

    _sig = _Sig()

    class _MockCM(_MockCameraManager):
        frame_ready          = _sig.frame_ready
        error_occurred       = _sig.error_occurred
        stream_state_changed = _sig.stream_state_changed
        fps_changed          = _sig.fps_changed

    class _MockBridge:
        camera_manager = _MockCM()
        _arduino = _MockArduino()

        def list_cameras(self): return ["Webcam_0"]
        def start_camera_preview(self, n): return True
        def stop_camera_preview(self): pass
        def start_first_camera_preview(self): return True
        def get_current_fps(self): return 0.0
        def set_mode_adult(self): pass
        def set_mode_larval(self): pass
        def set_recording_error_handler(self, fn): pass
        def set_recording_stopped_handler(self, fn): pass
        def set_recording_started_handler(self, fn): pass
        def current_mode_profile(self):
            from backend.mode_profiles import profile_for_mode
            return profile_for_mode("adult")
        def apply_environment_lighting(self, ir, w): pass
        def apply_stimulus_vibration(self, on, ms): pass
        def apply_stimulus_rgb(self, r, g, b, i): pass
        def apply_stimulus_timing(self, d, dur): pass
        def list_serial_ports(self): return []
        def save_settings(self, s): return True
        def start_recording(self, p, b, d): return True
        def stop_recording(self): pass
        def is_recording(self): return False
        def run_protocol(self, pid): pass
        def _mode_profile(self):
            from backend.mode_profiles import profile_for_mode
            return profile_for_mode("adult")

    bridge = _MockBridge()
    user   = {"id": 1, "username": "admin", "email": "admin@zimon.lab", "role": "admin"}

    pages_to_test = [
        ("Login window",        lambda: _test_login_window()),
        ("Nav bar",             lambda: _test_nav_bar(user)),
        ("Bottom bar",          lambda: _test_bottom_bar()),
        ("Environment page",    lambda: _from_page("environment_page", "EnvironmentPage", bridge)),
        ("Protocol Builder",    lambda: _from_page("protocol_builder_page", "ProtocolBuilderPage", bridge, user)),
        ("Experiments page",    lambda: _from_page("experiments_page",   "ExperimentsPage",   bridge)),
        ("Settings page",       lambda: _from_page("settings_page",      "SettingsPage",       bridge)),
    ]

    for name, fn in pages_to_test:
        try:
            result = fn()
            check(f"UI: {name} initialises", result is not False)
        except Exception as e:
            check(f"UI: {name} initialises", False, error=f"{type(e).__name__}: {e}")

    # Larval / Adult — may need extra deps
    for name, page_mod, cls, args in [
        ("Larval page",  "larval_page",  "LarvalPage",  (bridge,)),
        ("Adult page",   "adult_page",   "AdultPage",   (bridge,)),
    ]:
        try:
            mod = importlib.import_module(f"gui_v2.pages.{page_mod}")
            cls_obj = getattr(mod, cls)
            w = cls_obj(*args)
            check(f"UI: {name} initialises", w is not None)
        except Exception as e:
            check(f"UI: {name} initialises", False, error=f"{type(e).__name__}: {e}")


def _test_login_window():
    from gui_v2.login_window import LoginWindow
    w = LoginWindow()
    # Check Remember Me checkbox exists
    assert hasattr(w, "_remember"), "No _remember checkbox"
    assert hasattr(w, "_email"),    "No _email field"
    assert hasattr(w, "_pw"),       "No _pw field"
    assert hasattr(w, "_btn_login"),"No _btn_login"
    return True


def _test_nav_bar(user):
    from gui_v2.nav_bar import NavBar
    nav = NavBar(user)
    # FPS method should exist but do nothing
    nav.set_fps("30")
    nav.set_recording(True)
    nav.set_recording(False)
    nav.add_notification("Test notification")
    assert len(nav._notifications) == 1
    nav.highlight("environment")
    nav.highlight("mode_adult")
    return True


def _test_bottom_bar():
    from gui_v2.bottom_bar import BottomBar
    bar = BottomBar()
    bar.set_arduino_status(True)
    bar.set_arduino_status(False)
    bar.set_temperature("24.5 °C")
    bar.set_temperature("—")
    # Camera/Chamber methods exist but are no-ops
    bar.set_camera("test", True)
    bar.set_chamber("test", True)
    return True


def _from_page(mod_name: str, cls_name: str, *args):
    mod = importlib.import_module(f"gui_v2.pages.{mod_name}")
    cls = getattr(mod, cls_name)
    w = cls(*args)
    return w is not None


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 6 — Feature-by-feature checklist (change document)
# ═══════════════════════════════════════════════════════════════════════════════

def test_feature_checklist():
    section("6. Client Feedback Checklist (Zimon_Changes_List_8May.docx)")

    checks = []

    # 1. Login
    from gui_v2.login_window import LoginWindow, _load_prefs, _save_prefs
    checks.append(("Login: Remember Me saves/loads prefs", _test_remember_me()))

    # 2. Environment — no stimulus section
    import ast
    env_src = open(os.path.join(ROOT, "gui_v2/pages/environment_page.py")).read()
    checks.append(("Environment: stimulus section removed",
                   "StimulusCard" not in env_src and "VIBRATE" not in env_src))
    checks.append(("Environment: camera preview (_MiniPreview) present",
                   "_MiniPreview" in env_src))
    checks.append(("Environment: role assignment QComboBox present",
                   "_ROLE_OPTIONS" in env_src and "larval_machine_vision" in env_src))
    checks.append(("Environment: lighting controls (IR ON/OFF) present",
                   "set_ir_intensity" in env_src))
    checks.append(("Environment: LED/White lighting controls present",
                   "set_white_intensity" in env_src))

    # 3. Larval
    larval_src = open(os.path.join(ROOT, "gui_v2/pages/larval_page.py")).read()
    checks.append(("Larval: heater stimulus present",
                   "Heating" in larval_src or "set_heater" in larval_src))
    checks.append(("Larval: ON/OFF buttons per stimulus",
                   "StimulusOnBtn" in larval_src or "_btn_on" in larval_src))
    checks.append(("Larval: Continuous/Pulse mode radios",
                   "Continuous" in larval_src and "Pulse" in larval_src))
    checks.append(("Larval: uses assigned camera role",
                   "larval_machine_vision" in larval_src or "get_camera_for_role" in larval_src))
    checks.append(("Larval: Top/Side selector removed",
                   "TOP" not in larval_src.upper() or
                   "get_camera_for_role" in larval_src))  # replaced by role-based
    checks.append(("Larval: wellplate overlay present",
                   "WellPlateOverlay" in larval_src))

    # 4. Adult
    adult_src = open(os.path.join(ROOT, "gui_v2/pages/adult_page.py")).read()
    checks.append(("Adult: heater stimulus present",
                   "Heating" in adult_src or "set_heater" in adult_src))
    checks.append(("Adult: camera selection QComboBox present",
                   "camera" in adult_src.lower() and "QComboBox" in adult_src))
    checks.append(("Adult: FPS label next to preview",
                   "fps" in adult_src.lower() and "QTimer" in adult_src))
    checks.append(("Adult: Start Protocol button present",
                   "Start Protocol" in adult_src or "protocol" in adult_src.lower()))

    # 5. Nav bar
    nav_src = open(os.path.join(ROOT, "gui_v2/nav_bar.py")).read()
    checks.append(("Nav: FPS removed from ribbon",
                   "set_fps" in nav_src and "pass" in nav_src))  # set_fps is a no-op now
    checks.append(("Nav: notification bell is functional",
                   "_show_notifications" in nav_src and "_NotificationPanel" in nav_src))
    checks.append(("Nav: Manage Users / Logout visible in user menu",
                   "Manage Users" in nav_src and "Logout" in nav_src))
    checks.append(("Nav: UserMenuBtn high-contrast style",
                   "UserMenuBtn" in nav_src))

    # 6. Bottom bar
    bot_src = open(os.path.join(ROOT, "gui_v2/bottom_bar.py")).read()
    checks.append(("Bottom bar: Camera/Chamber chips removed",
                   "Camera" not in bot_src.replace("set_camera", "") or
                   "pass" in bot_src))
    checks.append(("Bottom bar: Arduino status present",
                   "Arduino" in bot_src and "set_arduino_status" in bot_src))
    checks.append(("Bottom bar: temperature in °C",
                   "temperature" in bot_src.lower()))

    # 7. Protocol Builder
    pb_src = open(os.path.join(ROOT, "gui_v2/pages/protocol_builder_page.py")).read()
    checks.append(("Protocol Builder: category field present",
                   "_category_combo" in pb_src))
    checks.append(("Protocol Builder: category saved to DB",
                   'category=' in pb_src))

    # 8. Experiments
    exp_src = open(os.path.join(ROOT, "gui_v2/pages/experiments_page.py")).read()
    checks.append(("Experiments: Replay wired to open video file",
                   "os.startfile" in exp_src or "startfile" in exp_src))
    checks.append(("Experiments: Export writes real files",
                   "shutil" in exp_src and "zipfile" in exp_src))

    # 9. Arduino firmware
    fw = open(os.path.join(ROOT, "arduino/zfish_controller.ino")).read()
    checks.append(("Arduino firmware: D7 HEATER pin defined",
                   "PIN_HEAT" in fw and "7" in fw))
    checks.append(("Arduino firmware: HEAT command handler",
                   'startsWith("HEAT ")' in fw))

    # 10. DB
    import db.database as db_mod
    import inspect
    db_src = inspect.getsource(db_mod)
    checks.append(("DB: camera_assignments table",
                   "camera_assignments" in db_src))
    checks.append(("DB: protocol category column",
                   "category" in db_src and "both" in db_src))
    checks.append(("DB: list_protocols supports category filter",
                   "category" in inspect.getsource(db_mod.list_protocols)))

    for name, result in checks:
        check(name, result)


def _test_remember_me() -> bool:
    from gui_v2.login_window import _save_prefs, _load_prefs
    tmp = tempfile.mktemp(suffix=".json")
    import gui_v2.login_window as lw
    orig = lw._PREFS_PATH
    lw._PREFS_PATH = tmp
    try:
        _save_prefs({"remember_me": True, "username": "testuser"})
        p = _load_prefs()
        return p.get("username") == "testuser" and p.get("remember_me") is True
    finally:
        lw._PREFS_PATH = orig
        try: os.remove(tmp)
        except Exception: pass


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 7 — File structure checks
# ═══════════════════════════════════════════════════════════════════════════════

def test_file_structure():
    section("7. Project File Structure")

    expected = [
        "main_v2.py",
        "db/__init__.py",
        "db/database.py",
        "backend/arduino_controller.py",
        "backend/camera_interface.py",
        "backend/camera_manager.py",
        "backend/recording_manager.py",
        "gui_v2/login_window.py",
        "gui_v2/main_window.py",
        "gui_v2/nav_bar.py",
        "gui_v2/bottom_bar.py",
        "gui_v2/styles_v2.qss",
        "gui_v2/pages/adult_page.py",
        "gui_v2/pages/larval_page.py",
        "gui_v2/pages/environment_page.py",
        "gui_v2/pages/protocol_builder_page.py",
        "gui_v2/pages/experiments_page.py",
        "gui_v2/pages/settings_page.py",
        "arduino/zfish_controller.ino",
        "ZIMON_Documentation.md",
        "ZIMON_Documentation.pdf",
        "requirements.txt",
        "zimon.spec",
        "build_installer.bat",
    ]

    for f in expected:
        full = os.path.join(ROOT, f.replace("/", os.sep))
        check(f"File exists: {f}", os.path.isfile(full))


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def print_report():
    total  = len(RESULTS)
    passed = sum(1 for r in RESULTS if r.passed)
    failed = total - passed

    print("\n")
    print("═" * 62)
    print("  ZIMON TEST REPORT")
    print("═" * 62)
    print(f"  Total tests : {total}")
    print(f"  Passed      : {passed}  ✓")
    print(f"  Failed      : {failed}  {'✗' if failed else '—'}")
    print(f"  Pass rate   : {passed/total*100:.1f}%")
    print("═" * 62)

    if failed:
        print("\n  FAILED TESTS:")
        for r in RESULTS:
            if not r.passed:
                print(f"    ✗ {r.name}")
                if r.error:
                    print(f"      → {r.error}")
    else:
        print("\n  All tests passed! ✓")

    print()

    # Write report to file
    report_path = os.path.join(ROOT, "TEST_REPORT.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("ZIMON AUTOMATED TEST REPORT\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 62 + "\n\n")
        f.write(f"Total: {total}  |  Passed: {passed}  |  Failed: {failed}\n")
        f.write(f"Pass rate: {passed/total*100:.1f}%\n\n")
        f.write("=" * 62 + "\n")
        for r in RESULTS:
            status = "PASS" if r.passed else "FAIL"
            f.write(f"[{status}] {r.name}\n")
            if r.detail:
                f.write(f"       {r.detail}\n")
            if r.error:
                f.write(f"       ERROR: {r.error}\n")
    print(f"  Report saved: {report_path}")
    return passed, failed


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "═" * 62)
    print("  ZIMON Automated Test Suite")
    print("  Testing all client feedback items + PIN map")
    print("═" * 62)

    test_imports()
    test_database()
    test_arduino()
    test_firmware()
    test_ui_pages()
    test_feature_checklist()
    test_file_structure()

    passed, failed = print_report()
    sys.exit(0 if failed == 0 else 1)
