# main.py
import sys
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("zimon_app")

from version import __version__

# imports
from gui.loading_screen import LoadingScreen
from gui.main_window import MainWindow

from backend.arduino_controller import ArduinoController
from backend.camera_interface import CameraController
from backend.experiment_runner import ExperimentRunner

# 🔴 IMPORTANT: global reference
MAIN_WINDOW = None


def main():
    logger.info("Starting ZIMON application v%s (Version 2 development tree)", __version__)

    app = QApplication(sys.argv)

    # =========================
    # LOAD GLOBAL STYLESHEET
    # =========================
    try:
        # Get the directory where main.py is located
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        stylesheet_path = os.path.join(script_dir, "gui", "styles.qss")
        
        with open(stylesheet_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
        logger.info(f"Stylesheet loaded from: {stylesheet_path}")
    except Exception as e:
        logger.warning(f"Failed to load stylesheet: {e}")

    # =========================
    # SHOW LOADING SCREEN
    # =========================
    loading = LoadingScreen()
    loading.show()

    # Delay backend init
    QTimer.singleShot(1200, lambda: init_backend(loading))

    sys.exit(app.exec())


def init_backend(loading):
    logger.info("Initializing backend")

    arduino = ArduinoController()
    camera = CameraController()
    runner = ExperimentRunner(
        arduino_controller=arduino,
        camera_controller=camera,
        logger=logger
    )

    QTimer.singleShot(
        300,
        lambda: launch_main(loading, arduino, camera, runner)
    )


def launch_main(loading, arduino, camera, runner):
    global MAIN_WINDOW  # 🔴 THIS IS THE FIX

    logger.info("Opening main dashboard")

    MAIN_WINDOW = MainWindow(
        arduino=arduino,
        camera=camera,
        runner=runner
    )

    loading.close()
    MAIN_WINDOW.show()
    MAIN_WINDOW.raise_()
    MAIN_WINDOW.activateWindow()


if __name__ == "__main__":
    main()
