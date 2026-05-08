from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGroupBox, QPushButton,
    QCheckBox, QSlider, QSpinBox, QColorDialog, QComboBox, QMessageBox,
    QStackedWidget, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
import logging
import time
import cv2
import numpy as np
from gui.settings_dialog import SettingsDialog
from gui.analysis_tab import AnalysisTab
from backend.camera_interface import CameraType


class MainWindow(QMainWindow):
    def __init__(self, runner=None, arduino=None, camera=None):
        super().__init__()
        self.runner = runner
        self.arduino = arduino
        self.camera = camera
        self.logger = logging.getLogger("main_window")
        
        # Initialize ZebraZoom integration
        try:
            from backend.zebrazoom_integration import ZebraZoomIntegration
            self.zebrazoom = ZebraZoomIntegration()
        except Exception as e:
            self.logger.warning(f"ZebraZoom integration not available: {e}")
            self.zebrazoom = None

        # Widget references for backend integration
        self.ir_slider = None
        self.ir_enable = None
        self.white_slider = None
        self.white_enable = None
        self.pump_slider = None
        self.pump_enable = None
        self.temp_label = None
        self.arduino_status_label = None
        
        self.vib_slider = None
        self.vib_enable = None
        self.vib_duration = None
        self.vib_delay = None
        self.vib_continuous = None
        self.buzzer_slider = None
        self.buzzer_enable = None
        self.buzzer_duration = None
        self.buzzer_delay = None
        self.buzzer_continuous = None
        self.heater_slider = None
        self.heater_enable = None
        self.heater_duration = None
        self.heater_delay = None
        self.heater_continuous = None
        
        # Temperature update timer
        self.temp_timer = QTimer()
        self.temp_timer.timeout.connect(self._update_temperature)
        self.temp_timer.start(2000)  # Update every 2 seconds
        
        # Experiment timer
        self.experiment_timer = None
        self.experiment_start_time = None
        
        # Camera-related variables
        self.current_camera = None
        self.camera_preview_labels = []  # List of all preview labels (one per tab)
        self.camera_preview_widget = None  # Shared preview widget
        self.camera_settings_widget = None  # Shared settings widget
        self.camera_combo = None  # Main camera combo box (first one created)
        self.camera_combos = []  # List of all camera combo boxes for syncing
        self.camera_status_label = None
        self.camera_fps_label = None
        self.camera_resolution_label = None
        self.camera_zoom_label = None
        self.camera_settings_timer = QTimer()
        self.camera_settings_timer.timeout.connect(self._update_camera_settings_display)
        self.camera_settings_timer.start(500)  # Update every 500ms
        
        # FPS counter variables
        self.fps_frame_times = []  # List of frame timestamps
        self.fps_counter_label = None  # FPS overlay label
        self.current_fps = 0.0

        try:
            from version import __version__ as _app_version
        except ImportError:
            _app_version = "?"
        self.setWindowTitle(f"ZIMON v{_app_version} — Behaviour Tracking System")
        self.resize(1400, 900)
        self._build_ui()
        # Start maximized for best experience
        self.showMaximized()
        # Optimize loading - start timers after UI is ready
        QTimer.singleShot(100, self._connect_backend)
        QTimer.singleShot(200, self._init_camera_list)
        QTimer.singleShot(300, self._optimize_performance)

    def closeEvent(self, event):
        """Ensure camera threads stop before widgets are destroyed."""
        try:
            if self.camera and self.current_camera:
                try:
                    self.camera.stop_preview(self.current_camera)
                except Exception:
                    pass
            if self.camera:
                try:
                    self.camera.cleanup()
                except Exception:
                    pass
        finally:
            # Avoid callbacks trying to paint into deleted widgets
            try:
                self.camera_preview_labels.clear()
            except Exception:
                pass
            event.accept()

    def _optimize_performance(self):
        """Optimize performance after UI is loaded"""
        try:
            # Reduce camera settings update frequency for better performance
            if hasattr(self, 'camera_settings_timer'):
                self.camera_settings_timer.setInterval(1000)  # Update every 1 second instead of 500ms
            
            # Optimize temperature update frequency
            if hasattr(self, 'temp_timer'):
                self.temp_timer.setInterval(3000)  # Update every 3 seconds instead of 2 seconds
            
            # Enable hardware acceleration for better rendering
            self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            
            self.logger.info("Performance optimizations applied")
        except Exception as e:
            self.logger.error(f"Error applying performance optimizations: {e}")

    def _update_camera_settings_display(self):
        """Update camera settings display labels"""
        if not self.camera or not self.current_camera:
            if self.camera_status_label:
                self.camera_status_label.setText("Not connected")
            if self.camera_fps_label:
                self.camera_fps_label.setText("FPS: —")
            if self.camera_resolution_label:
                self.camera_resolution_label.setText("Resolution: —")
            if self.camera_zoom_label:
                self.camera_zoom_label.setText("Zoom: —")
            return
        
        try:
            # Update status
            if self.camera_status_label:
                self.camera_status_label.setText("Connected")
            
            # Update FPS
            if self.camera_fps_label:
                current_fps = self.camera.get_current_fps(self.current_camera)
                if current_fps:
                    self.camera_fps_label.setText(f"FPS: {current_fps:.1f}")
                else:
                    self.camera_fps_label.setText("FPS: —")
            
            # Update Resolution
            if self.camera_resolution_label:
                resolution = self.camera.get_resolution(self.current_camera)
                if resolution:
                    w, h = resolution
                    self.camera_resolution_label.setText(f"Resolution: {w}x{h}")
                else:
                    self.camera_resolution_label.setText("Resolution: —")
            
            # Update Zoom
            if self.camera_zoom_label:
                zoom = self.camera.get_setting(self.current_camera, "zoom")
                if zoom:
                    self.camera_zoom_label.setText(f"Zoom: {zoom:.1f}x")
                else:
                    self.camera_zoom_label.setText("Zoom: —")
                    
        except Exception as e:
            self.logger.error(f"Error updating camera settings display: {e}")

    def _restart_preview_with_new_resolution(self, camera_name: str):
        """Restart camera preview with new resolution - non-blocking"""
        try:
            if self.camera.start_preview(camera_name, self._update_camera_frame):
                self.logger.info(f"Restarted preview for {camera_name} with new resolution")
            else:
                self.logger.error(f"Failed to restart preview for {camera_name}")
        except Exception as e:
            self.logger.error(f"Error restarting preview: {e}")

    # ---------- UI ROOT ----------
    def _build_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left sidebar
        root.addWidget(self._build_sidebar())
        
        # Main content area
        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)
        
        # Small top header
        main_layout.addLayout(self._build_header())
        
        # Stacked widget for pages (instead of tabs)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._environment_tab())
        self.pages.addWidget(self._experiment_tab())
        self.pages.addWidget(self._placeholder_tab("Presets"))
        self.analysis_tab = AnalysisTab(self.zebrazoom)
        self.pages.addWidget(self.analysis_tab)
        
        main_layout.addWidget(self.pages, 1)
        root.addWidget(main_area, 1)

        self.setCentralWidget(central)

    # ---------- SIDEBAR ----------
    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(80)  # Increased width for better layout
        sidebar.setStyleSheet("""
            QFrame#Sidebar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1d23, stop:1 #0d0f13);
                border-right: 2px solid #2a2d36;
            }
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(12)
        
        # Logo section at top
        logo_container = QFrame()
        logo_container.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
        """)
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(8)
        
        # Modern logo with better icon
        logo = QLabel("🧬")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("""
            QLabel {
                font-size: 36px;
                padding: 12px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #6366f1, stop:1 #8b5cf6);
                border-radius: 20px;
                color: white;
                font-weight: bold;
            }
        """)
        logo_layout.addWidget(logo)
        
        # App name with better styling
        app_name = QLabel("ZIMON")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_name.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: 700;
                padding: 8px 4px;
                background: rgba(99, 102, 241, 0.15);
                border-radius: 8px;
                border: 1px solid rgba(99, 102, 241, 0.3);
                letter-spacing: 2px;
            }
        """)
        logo_layout.addWidget(app_name)
        
        layout.addWidget(logo_container)
        
        # Separator with better styling
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 transparent, stop:0.5 #2a2d36, stop:1 transparent);
                max-height: 2px;
                border: none;
            }
        """)
        layout.addWidget(sep)
        
        layout.addSpacing(16)
        
        # Navigation buttons with better design
        self.nav_buttons = []
        nav_items = [
            ("🏠", "Home", "Environment", 0),
            ("🧪", "Lab", "Experiment", 1),
            ("💾", "Save", "Presets", 2),
            ("📊", "Data", "Analysis", 3),
        ]
        
        for icon, short_name, tooltip, page_idx in nav_items:
            # Create button container for better layout
            btn_container = QFrame()
            btn_container.setStyleSheet("QFrame { background: transparent; border: none; }")
            btn_layout = QVBoxLayout(btn_container)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setSpacing(4)
            
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            btn.setFixedSize(56, 56)  # Larger, more touch-friendly
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.05);
                    border: 2px solid rgba(255, 255, 255, 0.1);
                    border-radius: 14px;
                    font-size: 24px;
                    color: #b8bcc8;
                    font-family: "Segoe UI Emoji", "Apple Color Emoji", sans-serif;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: rgba(99, 102, 241, 0.15);
                    border: 2px solid rgba(99, 102, 241, 0.4);
                    color: #ffffff;
                }
                QPushButton:checked {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                        stop:0 #6366f1, stop:1 #8b5cf6);
                    border: 2px solid #6366f1;
                    color: #ffffff;
                    font-weight: bold;
                }
                QPushButton:pressed {
                    background: rgba(79, 70, 229, 0.8);
                    border: 2px solid #4f46e5;
                }
            """)
            btn.clicked.connect(lambda checked, idx=page_idx: self._switch_page(idx))
            btn_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)
            
            # Add label below icon
            label = QLabel(short_name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("""
                QLabel {
                    color: #7a7d85;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 2px;
                }
            """)
            btn_layout.addWidget(label)
            
            layout.addWidget(btn_container, 0, Qt.AlignmentFlag.AlignCenter)
            self.nav_buttons.append(btn)
        
        # Select first button by default
        if self.nav_buttons:
            self.nav_buttons[0].setChecked(True)
        
        layout.addStretch()
        
        # Bottom section with settings
        bottom_container = QFrame()
        bottom_container.setStyleSheet("QFrame { background: transparent; border: none; }")
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(12)
        
        # Settings button with better design
        settings_btn = QPushButton("⚙️")
        settings_btn.setToolTip("Settings")
        settings_btn.setFixedSize(56, 56)
        settings_btn.setStyleSheet("""
            QPushButton {
                background: rgba(148, 163, 184, 0.1);
                border: 2px solid rgba(148, 163, 184, 0.2);
                border-radius: 14px;
                font-size: 22px;
                color: #94a3b8;
                font-family: "Segoe UI Emoji", "Apple Color Emoji", sans-serif;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(99, 102, 241, 0.15);
                border: 2px solid rgba(99, 102, 241, 0.4);
                color: #ffffff;
            }
            QPushButton:pressed {
                background: rgba(79, 70, 229, 0.3);
                border: 2px solid #4f46e5;
            }
        """)
        settings_btn.clicked.connect(self._show_settings)
        bottom_layout.addWidget(settings_btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        # Settings label
        settings_label = QLabel("Settings")
        settings_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_label.setStyleSheet("""
            QLabel {
                color: #7a7d85;
                font-size: 10px;
                font-weight: 600;
                padding: 2px;
            }
        """)
        bottom_layout.addWidget(settings_label)
        
        layout.addWidget(bottom_container)
        
        return sidebar
    
    def _switch_page(self, index):
        """Switch to a page and update nav button states"""
        self.pages.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        
        # Update page title
        titles = ["Environment", "Experiment", "Presets", "Analysis"]
        if hasattr(self, 'page_title') and index < len(titles):
            self.page_title.setText(titles[index])

    # ---------- HEADER ----------
    def _build_header(self):
        layout = QHBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 8)

        # Page title (changes based on current page)
        self.page_title = QLabel("Environment")
        self.page_title.setStyleSheet("""
            QLabel {
                font-size: 22px;
                font-weight: 700;
                color: #ffffff;
                padding: 8px 12px;
                background: rgba(99, 102, 241, 0.1);
                border-radius: 8px;
                border-left: 3px solid #6366f1;
            }
        """)
        layout.addWidget(self.page_title)
        
        layout.addStretch()
        
        # Arduino connection status
        status_label = QLabel("🔌 Arduino: Checking...")
        status_label.setObjectName("ArduinoStatus")
        status_label.setStyleSheet("""
            QLabel {
                color: #94a3b8;
                font-size: 11px;
                padding: 6px 12px;
                background: rgba(148, 163, 184, 0.1);
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 6px;
            }
        """)
        self.arduino_status_label = status_label
        layout.addWidget(status_label)

        return layout

    # ---------- ENVIRONMENT TAB ----------
    def _environment_tab(self):
        from PyQt6.QtWidgets import QSizePolicy, QScrollArea
        
        # Create scroll area for the entire tab
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(10)

        # Top row: Camera preview and settings side by side
        top = QHBoxLayout()
        top.setSpacing(14)
        
        # Create camera widgets for this tab
        camera_preview = self._camera_preview_box()
        camera_settings = self._camera_settings_box()
        
        # Set maximum height for camera preview to leave room for controls
        camera_preview.setMaximumHeight(450)
        
        top.addWidget(camera_preview, 3)
        top.addWidget(camera_settings, 2)

        layout.addLayout(top)
        layout.addWidget(self._environment_controls())

        scroll.setWidget(page)
        return scroll

    # ---------- EXPERIMENT TAB ----------
    def _experiment_tab(self):
        from PyQt6.QtWidgets import QSizePolicy, QScrollArea
        
        # Create scroll area for the entire tab
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(10)

        # Top section: Camera and experiment status side by side
        top_section = QHBoxLayout()
        top_section.setSpacing(14)
        
        # Create camera preview widget (shares preview label reference)
        camera_preview = self._camera_preview_box()
        experiment_status = self._experiment_status_box()
        
        # Set maximum height for camera preview
        camera_preview.setMaximumHeight(400)
        
        top_section.addWidget(camera_preview, 3)
        top_section.addWidget(experiment_status, 2)

        layout.addLayout(top_section)
        layout.addWidget(self._stimuli_controls())

        # Action buttons with experiment info
        actions_container = QGroupBox("Experiment Control")
        actions_layout = QVBoxLayout(actions_container)
        actions_layout.setContentsMargins(16, 20, 16, 16)
        actions_layout.setSpacing(12)

        # Experiment timer/info
        timer_layout = QHBoxLayout()
        timer_layout.setSpacing(10)
        self.experiment_timer_label = QLabel("Duration: 00:00")
        self.experiment_timer_label.setStyleSheet("color: #a0a4ac; font-size: 13px;")
        timer_layout.addWidget(self.experiment_timer_label)
        timer_layout.addStretch()
        actions_layout.addLayout(timer_layout)

        # Buttons
        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addStretch()
        start_btn = QPushButton("▶ Start Experiment")
        start_btn.setMinimumWidth(160)
        start_btn.clicked.connect(self._on_start_experiment)
        actions.addWidget(start_btn)
        stop = QPushButton("⏹ Stop")
        stop.setObjectName("Danger")
        stop.setMinimumWidth(100)
        stop.clicked.connect(self._on_stop_experiment)
        stop.setEnabled(False)
        actions.addWidget(stop)
        
        # Store button references
        self.start_btn = start_btn
        self.stop_btn = stop

        actions_layout.addLayout(actions)
        layout.addWidget(actions_container)

        scroll.setWidget(page)
        return scroll

    # ---------- CAMERA ----------
    def _camera_preview_box(self):
        from PyQt6.QtWidgets import QSizePolicy
        box = QGroupBox("Camera Preview")
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(8)

        # Camera selection - always create new combo for this widget (Qt limitation)
        # But sync selection across all combos
        camera_select_layout = QHBoxLayout()
        camera_select_label = QLabel("Camera:")
        camera_select_label.setStyleSheet("color: #e8e9ea;")
        
        # Create combo box for this widget - use simple native style
        camera_combo = QComboBox()
        camera_combo.setMinimumWidth(250)
        camera_combo.setMinimumHeight(30)
        camera_combo.setMaxVisibleItems(10)
        camera_combo.setEditable(False)
        camera_combo.currentIndexChanged.connect(lambda idx: self._on_camera_selected(camera_combo.currentText()) if idx >= 0 else None)
        
        # Store reference to main combo (first one created) and add to list
        self.camera_combos.append(camera_combo)
        if self.camera_combo is None:
            self.camera_combo = camera_combo
            self.logger.info(f"Set main camera_combo reference")
        
        # Sync with existing cameras if available
        if self.camera and self.camera.list_cameras():
            cameras = self.camera.list_cameras()
            camera_combo.blockSignals(True)
            camera_combo.clear()
            camera_combo.addItems(cameras)
            if self.current_camera and self.current_camera in cameras:
                index = camera_combo.findText(self.current_camera)
                if index >= 0:
                    camera_combo.setCurrentIndex(index)
            camera_combo.blockSignals(False)
            self.logger.info(f"Synced new combo with {len(cameras)} cameras")
        
        # Refresh button
        refresh_btn = QPushButton("🔄")
        refresh_btn.setToolTip("Refresh camera list")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #1a1c21;
                border: 1px solid #2a2d36;
                border-radius: 4px;
                padding: 4px 8px;
                color: #e8e9ea;
                min-width: 30px;
                max-width: 30px;
            }
            QPushButton:hover {
                background: #24262c;
                border-color: #6366f1;
                color: #ffffff;
            }
        """)
        refresh_btn.clicked.connect(self._refresh_camera_list)
        
        camera_select_layout.addWidget(camera_select_label)
        camera_select_layout.addWidget(camera_combo, 1)
        camera_select_layout.addWidget(refresh_btn)
        layout.addLayout(camera_select_layout)

        # Preview container with FPS overlay
        preview_container = QWidget()
        preview_container.setObjectName("CameraPreviewContainer")
        preview_container.setStyleSheet("""
            QWidget#CameraPreviewContainer {
                background: #0d0f13;
                border: 1px solid #2a2d36;
                border-radius: 12px;
            }
        """)
        preview_container_layout = QVBoxLayout(preview_container)
        preview_container_layout.setContentsMargins(0, 0, 0, 0)
        preview_container_layout.setSpacing(0)
        
        # Preview label - create new and add to list
        preview = QLabel("No camera selected")
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setObjectName("CameraPlaceholder")
        preview.setMinimumHeight(250)
        preview.setScaledContents(False)  # We handle scaling manually
        # Add to list of preview labels so we can update all of them
        self.camera_preview_labels.append(preview)
        preview_container_layout.addWidget(preview, 1)
        
        # FPS counter overlay (positioned absolutely over preview)
        if not self.fps_counter_label:
            fps_counter = QLabel("FPS: 0.0", preview_container)
            fps_counter.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
            fps_counter.setStyleSheet("""
                QLabel {
                    color: #22d3ee;
                    font-weight: bold;
                    font-size: 12px;
                    padding: 2px 6px;
                    background: rgba(0, 0, 0, 180);
                    border-radius: 4px;
                }
            """)
            fps_counter.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.fps_counter_label = fps_counter
        
        layout.addWidget(preview_container, 1)
        
        return box

    def _camera_settings_box(self):
        from PyQt6.QtWidgets import QSizePolicy
        box = QGroupBox("Camera Settings")
        # Use Preferred vertical policy so it doesn't stretch excessively
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(8)  # Reduced spacing

        # Camera status indicator
        status_layout = QHBoxLayout()
        status_indicator = QLabel("●")
        status_indicator.setStyleSheet("color: #22d3ee; font-size: 12px;")
        status_text = QLabel("Not connected")
        status_text.setStyleSheet("color: #e8e9ea; font-weight: 500;")
        self.camera_status_label = status_text
        status_layout.addWidget(status_indicator)
        status_layout.addWidget(status_text)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        # Separator
        separator = QLabel("")
        separator.setStyleSheet("background: #2a2d36; min-height: 1px; max-height: 1px;")
        layout.addWidget(separator)

        # Current settings display (hide exposure/gain since using auto mode)
        self.camera_fps_label = QLabel("FPS: —")
        self.camera_resolution_label = QLabel("Resolution: —")
        self.camera_zoom_label = QLabel("Zoom: —")
        
        for label in [self.camera_fps_label, self.camera_resolution_label, self.camera_zoom_label]:
            label.setStyleSheet("padding: 6px 0px; color: #e8e9ea; font-size: 11px;")
        
        layout.addWidget(self.camera_fps_label)
        layout.addWidget(self.camera_resolution_label)
        layout.addWidget(self.camera_zoom_label)
        
        # Separator
        separator2 = QLabel("")
        separator2.setStyleSheet("background: #2a2d36; min-height: 1px; max-height: 1px; margin-top: 8px;")
        layout.addWidget(separator2)

        # Controls
        controls_label = QLabel("Controls:")
        controls_label.setStyleSheet("color: #e8e9ea; font-weight: 500; margin-top: 8px;")
        layout.addWidget(controls_label)

        # Acquisition controls (needed for FLIR resolution changes)
        acq_layout = QHBoxLayout()
        self.camera_start_btn = QPushButton("Start")
        self.camera_start_btn.setObjectName("AcqButton")
        self.camera_start_btn.setFixedSize(76, 24)
        self.camera_start_btn.setEnabled(False)
        self.camera_start_btn.clicked.connect(self._start_camera_acquisition)
        self.camera_stop_btn = QPushButton("Stop")
        self.camera_stop_btn.setObjectName("AcqButton")
        self.camera_stop_btn.setFixedSize(76, 24)
        self.camera_stop_btn.setEnabled(False)
        self.camera_stop_btn.clicked.connect(self._stop_camera_acquisition)
        acq_layout.addWidget(self.camera_start_btn)
        acq_layout.addWidget(self.camera_stop_btn)
        acq_layout.addStretch()
        layout.addLayout(acq_layout)

        # FPS control
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("FPS:"))
        self.fps_spinbox = QSpinBox()
        # Allow high FPS for FLIR/Basler; webcam may clamp internally
        # 0 means "unlimited" (free-run) for supported cameras
        self.fps_spinbox.setRange(0, 10000)
        self.fps_spinbox.setSpecialValueText("∞")
        self.fps_spinbox.setValue(60)  # Default
        # Make typing responsive (not just arrow clicks)
        self.fps_spinbox.setKeyboardTracking(False)
        self.fps_spinbox.setAccelerated(True)
        # Also allow mouse wheel increments while focused
        self.fps_spinbox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Allow typing "I" / "i" to set unlimited
        try:
            self.fps_spinbox.lineEdit().installEventFilter(self)
        except Exception:
            pass
        self.fps_spinbox.setEnabled(False)
        self.fps_spinbox.valueChanged.connect(self._on_fps_changed)
        fps_layout.addWidget(self.fps_spinbox)
        layout.addLayout(fps_layout)

        # FPS presets
        presets_layout = QHBoxLayout()
        presets_layout.setContentsMargins(0, 6, 0, 0)
        presets_layout.setSpacing(6)
        self._fps_preset_buttons = []
        for preset in (60, 120, 180, 240):
            btn = QPushButton(str(preset))
            btn.setFixedSize(52, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("FpsPresetButton")
            btn.clicked.connect(lambda _=False, v=preset: self._set_fps_preset(v))
            self._fps_preset_buttons.append(btn)
            presets_layout.addWidget(btn)

        inf_btn = QPushButton("∞")
        inf_btn.setFixedSize(52, 24)
        inf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        inf_btn.setObjectName("FpsPresetButton")
        inf_btn.clicked.connect(self._set_fps_unlimited)
        presets_layout.addWidget(inf_btn)
        layout.addLayout(presets_layout)

        # Zoom control
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(50, 200)  # 0.5x to 2.0x zoom
        self.zoom_slider.setValue(100)  # 1.0x default
        self.zoom_slider.setEnabled(False)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        zoom_layout.addWidget(self.zoom_slider)
        self.zoom_label = QLabel("1.0x")
        zoom_layout.addWidget(self.zoom_label)
        layout.addLayout(zoom_layout)

        # Resolution control
        resolution_layout = QHBoxLayout()
        resolution_layout.addWidget(QLabel("Resolution:"))
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems([
            "640x480",
            "800x600",
            "1024x768",
            "1280x720",
            "1280x1024",
            "1920x1080",
            "2048x1536"
        ])
        self.resolution_combo.setEnabled(False)
        self.resolution_combo.currentTextChanged.connect(self._on_resolution_changed)
        self.resolution_combo.setMaxVisibleItems(10)  # Show up to 10 items in dropdown
        resolution_layout.addWidget(self.resolution_combo)
        layout.addLayout(resolution_layout)

        # No stretch - content should stay compact at top
        return box
    
    def _experiment_status_box(self):
        """Create experiment status/info panel"""
        from PyQt6.QtWidgets import QSizePolicy
        box = QGroupBox("Experiment Status")
        # Preferred vertical so it doesn't stretch excessively
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(10)

        # Status indicator
        status_layout = QHBoxLayout()
        self.experiment_status_indicator = QLabel("●")
        self.experiment_status_indicator.setStyleSheet("color: #a0a4ac; font-size: 14px;")
        self.experiment_status_text = QLabel("Not Running")
        self.experiment_status_text.setStyleSheet("color: #e8e9ea; font-weight: 600; font-size: 13px;")
        status_layout.addWidget(self.experiment_status_indicator)
        status_layout.addWidget(self.experiment_status_text)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        # Separator
        separator = QLabel("")
        separator.setStyleSheet("background: #2a2d36; min-height: 1px; max-height: 1px;")
        layout.addWidget(separator)

        # Active stimuli
        stimuli_label = QLabel("Active Stimuli:")
        stimuli_label.setStyleSheet("color: #a0a4ac; font-size: 12px; padding-top: 4px;")
        layout.addWidget(stimuli_label)
        
        self.active_stimuli_list = QLabel("None")
        self.active_stimuli_list.setStyleSheet("color: #e8e9ea; font-size: 11px; padding-left: 8px;")
        self.active_stimuli_list.setWordWrap(True)
        layout.addWidget(self.active_stimuli_list)

        # Recording status
        recording_layout = QHBoxLayout()
        recording_label = QLabel("Recording:")
        recording_label.setStyleSheet("color: #a0a4ac; font-size: 12px;")
        self.recording_status = QLabel("● Not Recording")
        self.recording_status.setStyleSheet("color: #dc2626; font-size: 11px;")
        recording_layout.addWidget(recording_label)
        recording_layout.addWidget(self.recording_status)
        recording_layout.addStretch()
        layout.addLayout(recording_layout)

        # No vertical stretch - content stays compact at top
        return box

    # ---------- ENVIRONMENT CONTROLS ----------
    def _environment_controls(self):
        box = QGroupBox("Environment Variables")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(14)

        # Add a quick info header
        info_header = QLabel("Control environmental conditions for consistent experiments")
        info_header.setStyleSheet("color: #a0a4ac; font-size: 11px; padding-bottom: 8px;")
        layout.addWidget(info_header)

        layout.addLayout(self._slider_row("IR Light"))
        layout.addLayout(self._slider_row("White Light"))
        layout.addLayout(self._slider_row("Pump"))

        # Separator before temperature
        separator = QLabel("")
        separator.setStyleSheet("background: #2a2d36; min-height: 1px; max-height: 1px; margin: 8px 0;")
        layout.addWidget(separator)

        # Temperature display with icon-like styling
        temp_container = QHBoxLayout()
        temp_container.setContentsMargins(0, 4, 0, 0)
        temp_icon = QLabel("🌡")
        temp_icon.setStyleSheet("font-size: 16px; padding-right: 4px;")
        temp = QLabel("Temperature:")
        temp.setStyleSheet("color: #e8e9ea; font-weight: 500;")
        temp_value = QLabel("-- °C")
        temp_value.setObjectName("Temperature")
        temp_container.addWidget(temp_icon)
        temp_container.addWidget(temp)
        temp_container.addWidget(temp_value)
        temp_container.addStretch()
        layout.addLayout(temp_container)
        
        # Store temperature label reference
        self.temp_label = temp_value

        return box

    # ---------- STIMULI ----------
    def _stimuli_controls(self):
        box = QGroupBox("Stimuli Control")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(14)

        # Add info header
        info_header = QLabel("Configure stimuli parameters for behavioral experiments")
        info_header.setStyleSheet("color: #9aa0aa; font-size: 11px; padding-bottom: 4px;")
        layout.addWidget(info_header)

        layout.addLayout(self._stimulus_row("Vibration"))
        layout.addLayout(self._stimulus_row("Buzzer"))
        layout.addLayout(self._stimulus_row("Heater"))
        layout.addLayout(self._rgb_row())

        return box

    # ---------- HELPERS ----------
    def _slider_row(self, name):
        row = QHBoxLayout()
        row.setSpacing(12)
        row.setContentsMargins(0, 0, 0, 0)

        label = QLabel(name)
        label.setMinimumWidth(80)
        enable = QCheckBox("Enable")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(0)
        slider.setEnabled(False)  # Disabled until enable checkbox is checked

        # Store references based on name
        if name == "IR Light":
            self.ir_slider = slider
            self.ir_enable = enable
        elif name == "White Light":
            self.white_slider = slider
            self.white_enable = enable
        elif name == "Pump":
            self.pump_slider = slider
            self.pump_enable = enable

        # Connect enable checkbox to slider
        enable.toggled.connect(lambda checked, s=slider: s.setEnabled(checked))
        enable.toggled.connect(lambda checked, s=slider, n=name: self._on_enable_toggled(checked, s, n))
        
        # Connect slider to backend
        slider.valueChanged.connect(lambda val, n=name: self._on_slider_changed(val, n))

        row.addWidget(label)
        row.addWidget(enable)
        row.addWidget(slider, 1)

        return row

    def _stimulus_row(self, name):
        row = QHBoxLayout()
        row.setSpacing(10)
        row.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel(name)
        name_label.setMinimumWidth(80)
        row.addWidget(name_label)
        
        enable_cb = QCheckBox("Enable")
        row.addWidget(enable_cb)

        intensity_label = QLabel("Intensity")
        intensity_label.setMinimumWidth(60)
        row.addWidget(intensity_label)
        
        intensity_slider = QSlider(Qt.Orientation.Horizontal)
        intensity_slider.setRange(0, 100)
        intensity_slider.setValue(0)
        intensity_slider.setEnabled(False)
        row.addWidget(intensity_slider, 1)

        duration_label = QLabel("Duration")
        duration_label.setMinimumWidth(60)
        row.addWidget(duration_label)
        
        duration_spin = QSpinBox()
        duration_spin.setRange(0, 9999)
        duration_spin.setSuffix(" ms")
        duration_spin.setValue(0)
        row.addWidget(duration_spin)

        delay_label = QLabel("Delay")
        delay_label.setMinimumWidth(50)
        row.addWidget(delay_label)
        
        delay_spin = QSpinBox()
        delay_spin.setRange(0, 9999)
        delay_spin.setSuffix(" ms")
        delay_spin.setValue(0)
        row.addWidget(delay_spin)

        continuous_cb = QCheckBox("Continuous")
        row.addWidget(continuous_cb)

        # Store references for each stimulus
        if name == "Vibration":
            self.vib_slider = intensity_slider
            self.vib_enable = enable_cb
            self.vib_duration = duration_spin
            self.vib_delay = delay_spin
            self.vib_continuous = continuous_cb
        elif name == "Buzzer":
            self.buzzer_slider = intensity_slider
            self.buzzer_enable = enable_cb
            self.buzzer_duration = duration_spin
            self.buzzer_delay = delay_spin
            self.buzzer_continuous = continuous_cb
        elif name == "Heater":
            self.heater_slider = intensity_slider
            self.heater_enable = enable_cb
            self.heater_duration = duration_spin
            self.heater_delay = delay_spin
            self.heater_continuous = continuous_cb

        # Connect enable checkbox
        enable_cb.toggled.connect(lambda checked, s=intensity_slider: s.setEnabled(checked))
        enable_cb.toggled.connect(lambda checked, s=intensity_slider, n=name: self._on_stimulus_enable_toggled(checked, s, n))
        
        # Connect slider
        intensity_slider.valueChanged.connect(lambda val, n=name: self._on_stimulus_slider_changed(val, n))

        # Connect continuous checkbox to disable/enable duration and delay
        def on_continuous_toggled(checked):
            duration_spin.setEnabled(not checked)
            delay_spin.setEnabled(not checked)
            duration_label.setEnabled(not checked)
            delay_label.setEnabled(not checked)
            if checked:
                duration_spin.setValue(0)
                delay_spin.setValue(0)
        
        continuous_cb.toggled.connect(on_continuous_toggled)
        
        return row

    def _rgb_row(self):
        row = QHBoxLayout()
        row.setSpacing(10)
        row.setContentsMargins(0, 0, 0, 0)

        rgb_label = QLabel("RGB Light")
        rgb_label.setMinimumWidth(80)
        row.addWidget(rgb_label)
        
        enable_cb = QCheckBox("Enable")
        row.addWidget(enable_cb)

        pick = QPushButton("Pick Color")
        pick.setMinimumWidth(100)
        pick.clicked.connect(lambda: QColorDialog.getColor())
        row.addWidget(pick)

        row.addStretch()
        return row

    def _placeholder_tab(self, name):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        label = QLabel(f"{name} — Coming soon")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #9aa0aa; font-size: 14px;")
        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()
        return page

    # ---------- BACKEND INTEGRATION ----------
    def _connect_backend(self):
        """Connect UI controls to backend Arduino controller"""
        if not self.arduino:
            self.logger.warning("Arduino controller not available")
            self._update_arduino_status(False, "Not initialized")
            return
        
        # Check if already connected (non-blocking check only)
        if self.arduino.is_connected():
            port = getattr(self.arduino, 'port', 'Unknown')
            self.logger.info("Arduino already connected")
            self._update_arduino_status(True, f"Connected ({port})")
        else:
            # Don't auto-connect on startup to avoid blocking UI
            # User can connect manually via Settings
            self.logger.info("Arduino not connected - use Settings to connect")
            self._update_arduino_status(False, "Not connected")
    
    def _show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self.arduino, self, self.zebrazoom)
        dialog.exec()
        # Update status after settings dialog closes
        self._update_connection_status()
        # Update zebrazoom reference if it was changed
        if hasattr(dialog, 'zebrazoom') and dialog.zebrazoom:
            self.zebrazoom = dialog.zebrazoom
            # Update analysis tab if it exists
            self._update_zebrazoom_in_analysis()
    
    def _update_zebrazoom_in_analysis(self):
        """Update ZebraZoom reference in analysis tab"""
        # Update the analysis tab's zebrazoom reference
        if hasattr(self, 'analysis_tab'):
            self.analysis_tab.zebrazoom = self.zebrazoom
            # Remove warning if ZebraZoom is now available
            if self.zebrazoom and self.zebrazoom.is_available():
                # Remove warning label if exists
                layout = self.analysis_tab.layout()
                if layout:
                    for j in range(layout.count()):
                        item = layout.itemAt(j)
                        if item and item.widget():
                            widget_item = item.widget()
                            if isinstance(widget_item, QLabel) and "⚠️" in widget_item.text():
                                widget_item.deleteLater()
    
    def _update_connection_status(self):
        """Update connection status by testing actual connection"""
        if not self.arduino:
            self._update_arduino_status(False, "Not initialized")
            return
            
        # Test if actually connected
        try:
            if self.arduino.is_connected():
                port = getattr(self.arduino, 'port', 'Unknown')
                self._update_arduino_status(True, f"Connected ({port})")
            else:
                # Try to reconnect if we have a port
                port = getattr(self.arduino, 'port', None)
                if port:
                    try:
                        if self.arduino.connect(port):
                            self._update_arduino_status(True, f"Connected ({port})")
                        else:
                            self._update_arduino_status(False, "Not connected")
                    except:
                        self._update_arduino_status(False, "Not connected")
                else:
                    self._update_arduino_status(False, "Not connected")
        except Exception as e:
            self.logger.error(f"Error checking connection: {e}")
            self._update_arduino_status(False, "Error")
    
    def _update_arduino_status(self, connected, message):
        """Update Arduino connection status label"""
        if self.arduino_status_label:
            if connected:
                self.arduino_status_label.setText(f"Arduino: {message}")
                self.arduino_status_label.setStyleSheet("color: #4fc3f7; font-size: 11px; padding: 4px 8px;")
            else:
                self.arduino_status_label.setText(f"Arduino: {message}")
                self.arduino_status_label.setStyleSheet("color: #d04f4f; font-size: 11px; padding: 4px 8px;")

    def _map_to_pwm(self, value_0_100):
        """Map slider value (0-100) to PWM value (0-255)"""
        return int((value_0_100 / 100.0) * 255)

    def _on_enable_toggled(self, checked, slider, name):
        """Handle enable checkbox toggle for environment controls"""
        if not checked:
            # Disable slider and set value to 0
            slider.setValue(0)
            self._send_arduino_command(name, 0)
        else:
            # Send current slider value
            self._send_arduino_command(name, slider.value())

    def _on_slider_changed(self, value, name):
        """Handle slider value change for environment controls"""
        if not self.arduino or not self.arduino.is_connected():
            return
        
        # Check if enabled
        enable_cb = None
        if name == "IR Light":
            enable_cb = self.ir_enable
        elif name == "White Light":
            enable_cb = self.white_enable
        elif name == "Pump":
            enable_cb = self.pump_enable
        
        if enable_cb and enable_cb.isChecked():
            self._send_arduino_command(name, value)

    def _on_stimulus_enable_toggled(self, checked, slider, name):
        """Handle enable checkbox toggle for stimulus controls"""
        if not checked:
            slider.setValue(0)
            self._send_stimulus_command(name, 0)
        else:
            self._send_stimulus_command(name, slider.value())

    def _on_stimulus_slider_changed(self, value, name):
        """Handle slider value change for stimulus controls"""
        if not self.arduino or not self.arduino.is_connected():
            return
        
        enable_cb = None
        if name == "Vibration":
            enable_cb = self.vib_enable
        elif name == "Buzzer":
            enable_cb = self.buzzer_enable
        elif name == "Heater":
            enable_cb = self.heater_enable
        
        if enable_cb and enable_cb.isChecked():
            self._send_stimulus_command(name, value)

    def _send_arduino_command(self, name, value_0_100):
        """Send command to Arduino for environment controls"""
        if not self.arduino:
            self.logger.warning("Arduino controller not available")
            return
            
        if not self.arduino.is_connected():
            self.logger.warning("Arduino not connected - please connect via Settings")
            # Update status to show user needs to connect
            self._update_arduino_status(False, "Not connected - use Settings")
            return
        
        pwm_value = self._map_to_pwm(value_0_100)
        
        cmd_map = {
            "IR Light": f"IR {pwm_value}",
            "White Light": f"WHITE {pwm_value}",
            "Pump": f"PUMP {pwm_value}"
        }
        
        cmd = cmd_map.get(name)
        if cmd:
            try:
                reply = self.arduino.send(cmd)
                self.logger.info(f"Arduino command: {cmd} -> {reply}")
            except Exception as e:
                self.logger.error(f"Failed to send Arduino command {cmd}: {e}", exc_info=True)

    def _send_stimulus_command(self, name, value_0_100):
        """Send command to Arduino for stimulus controls"""
        if not self.arduino:
            self.logger.warning("Arduino controller not available")
            return
            
        if not self.arduino.is_connected():
            self.logger.warning("Arduino not connected")
            return
        
        pwm_value = self._map_to_pwm(value_0_100)
        
        # Map stimulus names to Arduino commands
        # Note: Buzzer and Heater may not be implemented in Arduino yet
        cmd_map = {
            "Vibration": f"VIB {pwm_value}",
            "Buzzer": None,  # Not implemented in Arduino firmware
            "Heater": None   # Not implemented in Arduino firmware
        }
        
        cmd = cmd_map.get(name)
        if cmd:
            try:
                reply = self.arduino.send(cmd)
                self.logger.info(f"Arduino command: {cmd} -> {reply}")
            except Exception as e:
                self.logger.error(f"Failed to send Arduino command {cmd}: {e}", exc_info=True)
        elif cmd is None:
            self.logger.warning(f"Stimulus '{name}' not implemented in Arduino firmware")

    def _update_temperature(self):
        """Update temperature display from Arduino"""
        if not self.arduino:
            if self.temp_label:
                self.temp_label.setText("-- °C")
            return
            
        # Check connection more reliably
        is_connected = False
        try:
            if self.arduino.is_connected():
                # Try a quick test to see if actually working
                is_connected = True
        except:
            pass
            
        if not is_connected:
            if self.temp_label:
                self.temp_label.setText("-- °C")
            # Only update status if we're sure it's disconnected
            # Don't update on every temp check to avoid flickering
            return
        
        try:
            temp = self.arduino.read_temperature_c()
            if temp is not None:
                if self.temp_label:
                    self.temp_label.setText(f"{temp:.1f} °C")
            else:
                if self.temp_label:
                    self.temp_label.setText("-- °C")
        except Exception as e:
            self.logger.error(f"Failed to read temperature: {e}")
            if self.temp_label:
                self.temp_label.setText("ERR °C")

    def _on_start_experiment(self):
        """Handle start experiment button click"""
        if not self.runner:
            self.logger.warning("Experiment runner not available")
            return
        
        # Build experiment config from UI state
        # Collect active stimuli with their parameters
        stimuli_config = {}
        
        # Vibration
        if hasattr(self, 'vib_enable') and self.vib_enable and self.vib_enable.isChecked():
            intensity = self.vib_slider.value() if self.vib_slider else 0
            continuous = self.vib_continuous.isChecked() if self.vib_continuous else False
            stimuli_config["VIB"] = {
                "level": self._map_to_pwm(intensity),
                "continuous": continuous,
                "duration_ms": 0 if continuous else (self.vib_duration.value() if self.vib_duration else 0),
                "delay_ms": 0 if continuous else (self.vib_delay.value() if self.vib_delay else 0)
            }
        
        # Buzzer
        if hasattr(self, 'buzzer_enable') and self.buzzer_enable and self.buzzer_enable.isChecked():
            intensity = self.buzzer_slider.value() if self.buzzer_slider else 0
            continuous = self.buzzer_continuous.isChecked() if self.buzzer_continuous else False
            stimuli_config["BUZZER"] = {
                "level": self._map_to_pwm(intensity),
                "continuous": continuous,
                "duration_ms": 0 if continuous else (self.buzzer_duration.value() if self.buzzer_duration else 0),
                "delay_ms": 0 if continuous else (self.buzzer_delay.value() if self.buzzer_delay else 0)
            }
        
        # Heater
        if hasattr(self, 'heater_enable') and self.heater_enable and self.heater_enable.isChecked():
            intensity = self.heater_slider.value() if self.heater_slider else 0
            continuous = self.heater_continuous.isChecked() if self.heater_continuous else False
            stimuli_config["HEATER"] = {
                "level": self._map_to_pwm(intensity),
                "continuous": continuous,
                "duration_ms": 0 if continuous else (self.heater_duration.value() if self.heater_duration else 0),
                "delay_ms": 0 if continuous else (self.heater_delay.value() if self.heater_delay else 0)
            }
        
        # Calculate experiment duration (long enough for all stimuli)
        max_duration = 60  # Default 60 seconds
        if stimuli_config:
            # For now, use a reasonable default, could calculate from stimuli
            max_duration = 300  # 5 minutes default
        
        config = {
            "duration_s": max_duration,
            "stimuli": stimuli_config
        }
        
        try:
            if self.runner.start(config):
                self.start_btn.setEnabled(False)
                self.stop_btn.setEnabled(True)
                
                # Update status
                if hasattr(self, 'experiment_status_indicator'):
                    self.experiment_status_indicator.setStyleSheet("color: #4fc3f7; font-size: 14px;")
                    self.experiment_status_text.setText("Running")
                
                # Update active stimuli display
                if hasattr(self, 'active_stimuli_list'):
                    active_stimuli_names = list(stimuli_config.keys())
                    if active_stimuli_names:
                        self.active_stimuli_list.setText(", ".join(active_stimuli_names))
                    else:
                        self.active_stimuli_list.setText("None")
                
                # Start timer
                self.experiment_start_time = time.time()
                if not self.experiment_timer:
                    self.experiment_timer = QTimer()
                    self.experiment_timer.timeout.connect(self._update_experiment_timer)
                self.experiment_timer.start(1000)  # Update every second
                
                # Update recording status
                if hasattr(self, 'recording_status'):
                    self.recording_status.setText("● Recording")
                    self.recording_status.setStyleSheet("color: #4fc3f7; font-size: 11px;")
                
                self.logger.info("Experiment started")
            else:
                self.logger.warning("Failed to start experiment (already running?)")
        except Exception as e:
            self.logger.error(f"Error starting experiment: {e}")

    def _on_stop_experiment(self):
        """Handle stop experiment button click"""
        if not self.runner:
            return
        
        try:
            self.runner.stop()
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            
            # Update status
            if hasattr(self, 'experiment_status_indicator'):
                self.experiment_status_indicator.setStyleSheet("color: #9aa0aa; font-size: 14px;")
                self.experiment_status_text.setText("Not Running")
            
            # Stop timer
            if self.experiment_timer:
                self.experiment_timer.stop()
            if hasattr(self, 'experiment_timer_label'):
                self.experiment_timer_label.setText("Duration: 00:00")
            self.experiment_start_time = None
            
            # Update recording status
            if hasattr(self, 'recording_status'):
                self.recording_status.setText("● Not Recording")
                self.recording_status.setStyleSheet("color: #d04f4f; font-size: 11px;")
            
            # Clear active stimuli
            if hasattr(self, 'active_stimuli_list'):
                self.active_stimuli_list.setText("None")
            
            self.logger.info("Experiment stopped")
        except Exception as e:
            self.logger.error(f"Error stopping experiment: {e}")
    
    def _update_experiment_timer(self):
        """Update experiment timer display"""
        if self.experiment_start_time and hasattr(self, 'experiment_timer_label'):
            elapsed = time.time() - self.experiment_start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            self.experiment_timer_label.setText(f"Duration: {minutes:02d}:{seconds:02d}")
    
    # ---------- CAMERA METHODS ----------
    def _init_camera_list(self):
        """Initialize camera list in combo box"""
        self.logger.info("_init_camera_list called")
        self.logger.info(f"camera_combos list has {len(self.camera_combos)} items")
        
        if not self.camera:
            self.logger.warning("Camera controller not available")
            for combo in self.camera_combos:
                if combo:
                    combo.clear()
                    combo.addItem("Camera controller not available")
            return
        
        # Use camera_combos list instead of single camera_combo reference
        if not self.camera_combos:
            self.logger.warning("No camera combo boxes found")
            return
        
        cameras = self.camera.list_cameras()
        self.logger.info(f"Cameras found: {cameras}")
        
        # Update ALL camera combo boxes
        for combo in self.camera_combos:
            if combo:
                combo.blockSignals(True)
                combo.clear()
                if cameras:
                    combo.addItems(cameras)
                else:
                    combo.addItem("No cameras found")
                combo.blockSignals(False)
        
        if cameras:
            self.logger.info(f"Added {len(cameras)} cameras to {len(self.camera_combos)} combo boxes")
            
            # Set main reference if not set
            if not self.camera_combo and self.camera_combos:
                self.camera_combo = self.camera_combos[0]
            
            # Auto-select first camera
            for combo in self.camera_combos:
                if combo:
                    combo.setCurrentIndex(0)
            
            self._on_camera_selected(cameras[0])
        else:
            self.logger.warning("No cameras detected. Make sure your webcam is connected and not in use by another application.")
    
    def _refresh_camera_list(self):
        """Refresh camera list"""
        if not self.camera or not self.camera_combo:
            return
        
        self.logger.info("Refreshing camera list...")
        
        # Stop current preview
        if self.current_camera:
            self.camera.stop_preview(self.current_camera)
            self.current_camera = None
        
        # Refresh camera detection
        self.camera.refresh_cameras()
        
        # Update all combo boxes
        cameras = self.camera.list_cameras()
        for combo in self.camera_combos:
            if combo:
                combo.blockSignals(True)
                combo.clear()
                if cameras:
                    combo.addItems(cameras)
                else:
                    combo.addItem("No cameras found")
                combo.blockSignals(False)
        
        if cameras:
            self.logger.info(f"Found {len(cameras)} cameras: {cameras}")
            # Auto-select first camera
            if self.camera_combo:
                self.camera_combo.setCurrentIndex(0)
                self._on_camera_selected(cameras[0])
        else:
            self.logger.warning("No cameras found after refresh")
    
    def _sync_all_camera_combos(self):
        """Sync all camera combo boxes with main combo"""
        if not self.camera_combo:
            return
        
        cameras = [self.camera_combo.itemText(i) for i in range(self.camera_combo.count())]
        current_text = self.camera_combo.currentText()
        
        for combo in self.camera_combos:
            if combo and combo != self.camera_combo:
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(cameras)
                index = combo.findText(current_text)
                if index >= 0:
                    combo.setCurrentIndex(index)
                combo.blockSignals(False)
    
    def _on_camera_selected(self, camera_name: str):
        """Handle camera selection"""
        if not self.camera or not camera_name or camera_name == "No cameras found" or camera_name == "Camera controller not available":
            return

        # Stop previous preview cleanly
        if self.current_camera and self.current_camera != camera_name:
            self.camera.stop_preview(self.current_camera)
            time.sleep(0.2)

        self.current_camera = camera_name
        resolutions = []
        # Dynamically check resolutions for webcam
        cam_info = self.camera.cameras.get(camera_name)
        if cam_info and cam_info["type"] == CameraType.WEBCAM:
            resolutions = self.camera.get_supported_resolutions(camera_name)
            resolutions = [f"{w}x{h}" for (w, h) in resolutions]
        elif cam_info and cam_info["type"] == CameraType.BASLER:
            # Just use the known safe presets for basler
            resolutions = [
                "640x480", "800x600", "1024x768", "1280x720", "1280x960",
                "1280x1024", "1600x1200", "1920x1080", "2048x1536"
            ]
        elif cam_info and cam_info["type"] == CameraType.FLIR:
            # Offer a few safe FLIR modes; apply only when acquisition is stopped.
            # (Exact availability can vary by PixelFormat/decimation/ROI; we keep it simple.)
            resolutions = ["640x480", "800x600", "1024x768", "1280x720", "1440x1080"]

        # Update the combo box
        if hasattr(self, 'resolution_combo'):
            self.resolution_combo.blockSignals(True)
            self.resolution_combo.clear()
            if resolutions:
                for r in resolutions:
                    self.resolution_combo.addItem(r)
                # Default to 1280x1024 for Basler, highest for webcam
                if cam_info and cam_info["type"] == CameraType.BASLER:
                    default_index = resolutions.index("1280x1024") if "1280x1024" in resolutions else 0
                else:
                    default_index = 0  # Highest resolution for webcam
                self.resolution_combo.setCurrentIndex(default_index)
            else:
                self.resolution_combo.addItem("1280x1024")
                self.resolution_combo.setCurrentIndex(0)
            # FLIR resolution changes are restricted while streaming (Stop to change)
            is_streaming = False
            try:
                is_streaming = bool(self.camera and hasattr(self.camera, "workers") and camera_name in self.camera.workers)
            except Exception:
                is_streaming = False
            self.resolution_combo.setEnabled(not (cam_info and cam_info.get("type") == CameraType.FLIR and is_streaming))
            self.resolution_combo.blockSignals(False)

        # Set and store resolution before preview (webcams only; FLIR nodes are often read-only)
        try:
            cam_info = self.camera.cameras.get(camera_name) if self.camera else None
        except Exception:
            cam_info = None

        if cam_info and cam_info.get("type") == CameraType.WEBCAM:
            if hasattr(self, 'resolution_combo') and self.resolution_combo.count() > 0:
                default_res = self.resolution_combo.currentText()
                if default_res:
                    parts = default_res.split('x')
                    if len(parts) == 2:
                        w, h = int(parts[0]), int(parts[1])
                        self.camera.set_setting(camera_name, "resolution", (w, h))

        # Apply desired FPS before starting preview (best-effort; backend may clamp)
        try:
            if hasattr(self, "fps_spinbox"):
                self.camera.set_setting(camera_name, "fps", int(self.fps_spinbox.value()))
        except Exception:
            pass

        # Start preview
        # Disable UI controls during start
        if hasattr(self, 'resolution_combo'):
            self.resolution_combo.setEnabled(False)
        if hasattr(self, 'fps_spinbox'):
            self.fps_spinbox.setEnabled(False)
        if hasattr(self, 'zoom_slider'):
            self.zoom_slider.setEnabled(False)
        
        # Start preview first, then disable controller controls
        if self.camera.start_preview(camera_name, self._update_camera_frame):
            self.logger.info(f"Started preview for {camera_name}")
            # Enable controls after successful start
            self.fps_spinbox.setEnabled(True)
            self.zoom_slider.setEnabled(True)
            self.resolution_combo.setEnabled(True)
            if hasattr(self, "camera_start_btn") and hasattr(self, "camera_stop_btn"):
                self.camera_start_btn.setEnabled(False)
                self.camera_stop_btn.setEnabled(True)

            # Load current settings
            if self.camera:
                fps = self.camera.get_setting(camera_name, "fps") or 180
                zoom = self.camera.get_setting(camera_name, "zoom") or 1.0
                self.fps_spinbox.setValue(int(fps))
                self.zoom_slider.setValue(int(zoom * 100))
        else:
            self.logger.error(f"Failed to start preview for {camera_name}")
            # Re-enable controls on failure
            if hasattr(self, 'resolution_combo'):
                self.resolution_combo.setEnabled(True)
            if hasattr(self, 'fps_spinbox'):
                self.fps_spinbox.setEnabled(True)
            if hasattr(self, 'zoom_slider'):
                self.zoom_slider.setEnabled(True)
            if hasattr(self, "camera_start_btn") and hasattr(self, "camera_stop_btn"):
                self.camera_start_btn.setEnabled(True)
                self.camera_stop_btn.setEnabled(False)

    def _stop_camera_acquisition(self):
        """Stop camera streaming/acquisition so settings like resolution can change."""
        if not self.current_camera or not self.camera:
            return
        try:
            self.camera.stop_preview(self.current_camera)
        except Exception:
            pass

        # When stopped, allow resolution changes (including FLIR)
        try:
            cam_info = self.camera.cameras.get(self.current_camera)
        except Exception:
            cam_info = None
        if hasattr(self, "resolution_combo"):
            self.resolution_combo.setEnabled(True)
        if hasattr(self, "camera_start_btn") and hasattr(self, "camera_stop_btn"):
            self.camera_start_btn.setEnabled(True)
            self.camera_stop_btn.setEnabled(False)

    def _start_camera_acquisition(self):
        """Start camera streaming/acquisition after settings changes."""
        if not self.current_camera or not self.camera:
            return
        # Start preview again
        if self.camera.start_preview(self.current_camera, self._update_camera_frame):
            if hasattr(self, "camera_start_btn") and hasattr(self, "camera_stop_btn"):
                self.camera_start_btn.setEnabled(False)
                self.camera_stop_btn.setEnabled(True)
            # If streaming, lock FLIR resolution changes again
            try:
                cam_info = self.camera.cameras.get(self.current_camera)
            except Exception:
                cam_info = None
            if cam_info and cam_info.get("type") == CameraType.FLIR:
                if hasattr(self, "resolution_combo"):
                    self.resolution_combo.setEnabled(False)
        else:
            if hasattr(self, "camera_start_btn") and hasattr(self, "camera_stop_btn"):
                self.camera_start_btn.setEnabled(True)
                self.camera_stop_btn.setEnabled(False)

    
    def _update_camera_frame(self, frame: np.ndarray):
        """Update camera preview with new frame - optimized for performance"""
        if not self.camera_preview_labels:
            return
        
        try:
            # Limit UI updates to ~60 FPS for smooth performance
            current_time = time.time()
            if not hasattr(self, '_last_ui_update'):
                self._last_ui_update = 0
            
            if current_time - self._last_ui_update < 0.016:  # ~60 FPS UI update
                return
            self._last_ui_update = current_time
            
            # Update FPS label (prefer capture FPS from worker over UI repaint rate)
            if self.fps_counter_label:
                capture_fps = None
                try:
                    if self.camera and self.current_camera:
                        capture_fps = self.camera.get_current_fps(self.current_camera)
                except Exception:
                    capture_fps = None

                if capture_fps is None:
                    # Fallback: UI repaint rate approximation
                    self.fps_frame_times.append(current_time)
                    self.fps_frame_times = [t for t in self.fps_frame_times[-60:] if current_time - t < 1.0]
                    if len(self.fps_frame_times) > 1:
                        time_span = self.fps_frame_times[-1] - self.fps_frame_times[0]
                        self.current_fps = len(self.fps_frame_times) / time_span if time_span > 0 else 0
                    self.fps_counter_label.setText(f"FPS: {self.current_fps:.1f}")
                else:
                    self.fps_counter_label.setText(f"FPS: {float(capture_fps):.1f}")
            
            # Convert frame to RGB - handle different camera formats
            try:
                if frame is None:
                    return
                    
                # Handle different frame formats from different cameras
                if len(frame.shape) == 2:
                    # Grayscale frame - convert to RGB
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
                elif len(frame.shape) == 3:
                    if frame.shape[2] == 3:
                        # BGR frame - convert to RGB
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    elif frame.shape[2] == 4:
                        # BGRA frame - convert to RGB
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                    else:
                        # Unknown format, use as-is
                        rgb_frame = frame
                else:
                    # Unknown format, use as-is
                    rgb_frame = frame
                    
            except Exception as e:
                self.logger.error(f"Error converting frame format: {e}, frame shape: {frame.shape if frame is not None else 'None'}")
                return
            
            # Get first visible preview label
            preview_label = None
            # Drop any deleted labels to avoid runtime errors
            for label in list(self.camera_preview_labels):
                if label is None:
                    continue
                try:
                    if label.isVisible():
                        preview_label = label
                        break
                except RuntimeError:
                    # Wrapped C++ object deleted
                    try:
                        self.camera_preview_labels.remove(label)
                    except ValueError:
                        pass
            
            if preview_label is None:
                return
            
            # Cache label dimensions to avoid repeated calls
            if not hasattr(self, '_cached_label_size') or self._cached_label_size != (preview_label.width(), preview_label.height()):
                self._cached_label_size = (preview_label.width(), preview_label.height())
                self._cached_scaled_size = (
                    max(preview_label.width(), 320),
                    max(preview_label.height(), 240)
                )
            
            # Create QImage directly from numpy array - robust error handling
            try:
                h, w = rgb_frame.shape[:2]
                
                # Determine bytes per line based on frame format
                if len(rgb_frame.shape) == 3:
                    bytes_per_line = w * rgb_frame.shape[2]
                else:
                    bytes_per_line = w * 3  # Default to 3 channels
                
                # Use ascontiguousarray to ensure memory layout
                rgb_frame_contiguous = np.ascontiguousarray(rgb_frame)
                
                # Create QImage with error checking
                if len(rgb_frame_contiguous.shape) == 3 and rgb_frame_contiguous.shape[2] == 3:
                    qt_image = QImage(rgb_frame_contiguous.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                elif len(rgb_frame_contiguous.shape) == 2:
                    # Grayscale
                    qt_image = QImage(rgb_frame_contiguous.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
                else:
                    # Fallback format
                    qt_image = QImage(rgb_frame_contiguous.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                
                if qt_image.isNull():
                    self.logger.warning(f"Failed to create QImage from frame shape: {rgb_frame_contiguous.shape}")
                    return
                
                # Scale pixmap once using cached size and zoom
                # Get current zoom setting
                zoom = self.camera.get_setting(self.current_camera, "zoom") if self.camera and self.current_camera else 1.0
                zoom = zoom if zoom is not None else 1.0
                
                # Apply zoom to scaling
                scaled_width = int(self._cached_scaled_size[0] * zoom)
                scaled_height = int(self._cached_scaled_size[1] * zoom)
                
                scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                    scaled_width,
                    scaled_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation
                )
                
                # Update label
                preview_label.setPixmap(scaled_pixmap)
                
            except Exception as e:
                self.logger.error(f"Error creating QImage from frame: {e}, frame shape: {rgb_frame.shape if rgb_frame is not None else 'None'}")
                return
            
        except Exception as e:
            self.logger.error(f"Error updating camera frame: {e}")
    
    def _on_fps_changed(self, value: int):
        """Handle FPS change - uses CameraController safety"""
        if not self.current_camera or not self.camera:
            return
        
        # Check if controls are disabled at controller level
        if self.camera.are_ui_controls_disabled():
            return
        
        # Debounce changes so typing and arrow-holding doesn't "fight" the UI.
        if not hasattr(self, "_fps_apply_timer"):
            self._fps_apply_timer = QTimer(self)
            self._fps_apply_timer.setSingleShot(True)
            self._fps_apply_timer.timeout.connect(self._apply_fps_change)

        self._pending_fps_value = int(value)
        self._fps_apply_timer.start(120)

    def _apply_fps_change(self):
        """Apply pending FPS value to the active camera"""
        if not self.current_camera or not self.camera:
            return
        value = int(getattr(self, "_pending_fps_value", self.fps_spinbox.value()))
        # Set setting through controller (will check safety)
        if self.camera.set_setting(self.current_camera, "fps", value):
            self.logger.info(f"FPS changed to {value}")

    def _set_fps_preset(self, value: int):
        """Set FPS from preset buttons"""
        if hasattr(self, "fps_spinbox") and self.fps_spinbox:
            self.fps_spinbox.setValue(int(value))

    def _set_fps_unlimited(self):
        """Set FPS to unlimited (free-run)"""
        if hasattr(self, "fps_spinbox") and self.fps_spinbox:
            self.fps_spinbox.setValue(0)

    def eventFilter(self, obj, event):
        """Allow 'I' key to set FPS unlimited."""
        try:
            if obj == getattr(self, "fps_spinbox", None).lineEdit():
                if event.type() == event.Type.KeyPress:
                    text = event.text()
                    if text in ("i", "I"):
                        self._set_fps_unlimited()
                        return True
        except Exception:
            pass
        return super().eventFilter(obj, event)
    
    def _on_zoom_changed(self, value: int):
        """Handle zoom change - uses CameraController safety"""
        zoom_value = value / 100.0
        if hasattr(self, 'zoom_value_label') and self.zoom_value_label:
            self.zoom_value_label.setText(f"{zoom_value:.1f}x")
        
        if not self.current_camera or not self.camera:
            return
        
        # Check if controls are disabled at controller level
        if self.camera.are_ui_controls_disabled():
            return
        
        # Disable control during operation
        self.zoom_slider.setEnabled(False)
        
        # Set setting through controller (will check safety)
        if self.camera.set_setting(self.current_camera, "zoom", zoom_value):
            self.logger.info(f"Zoom changed to {zoom_value}")
        self.zoom_slider.setEnabled(True)

    def _on_resolution_changed(self, resolution_str: str):
        """Handle resolution change - now supports Basler cameras"""
        if not self.current_camera or not self.camera:
            return
        
        # Check if controls are disabled at controller level
        if self.camera.are_ui_controls_disabled():
            return
        
        # Check camera type
        camera_name = self.current_camera
        cam_info = self.camera.cameras.get(camera_name)

        is_streaming = False
        try:
            is_streaming = bool(self.camera and hasattr(self.camera, "workers") and camera_name in self.camera.workers)
        except Exception:
            is_streaming = False
        
        # For Basler cameras, log that we're attempting resolution change
        if cam_info and cam_info.get("type") == CameraType.BASLER:
            self.logger.info(f"Attempting Basler resolution change to {resolution_str}")
        elif cam_info and cam_info.get("type") == CameraType.WEBCAM:
            self.logger.info(f"Setting webcam resolution to {resolution_str}")
        
        # Disable control during operation to prevent rapid changes
        self.resolution_combo.setEnabled(False)
        
        try:
            # Parse resolution string (e.g., "1920x1080")
            parts = resolution_str.split("x")
            if len(parts) != 2:
                return
                
            width = int(parts[0])
            height = int(parts[1])
            
            # FLIR: do NOT auto-restart. User must Stop -> change -> Start.
            if cam_info and cam_info.get("type") == CameraType.FLIR:
                if is_streaming:
                    self.logger.warning("Stop acquisition before changing FLIR resolution")
                    return

                if self.camera.set_setting(camera_name, "resolution", (width, height)):
                    self.logger.info(f"FLIR resolution staged to {width}x{height} (press Start)")
                    if hasattr(self, "camera_start_btn") and hasattr(self, "camera_stop_btn"):
                        self.camera_start_btn.setEnabled(True)
                        self.camera_stop_btn.setEnabled(False)
                else:
                    self.logger.warning("FLIR resolution change rejected by CameraController")
                return

            # Webcam/Basler: keep existing auto-restart behavior
            if self.camera.set_setting(camera_name, "resolution", (width, height)):
                self.logger.info(f"Resolution changed to {width}x{height}")
                self.camera.stop_preview(camera_name)
                QTimer.singleShot(100, lambda: self._restart_preview_with_new_resolution(camera_name))
            else:
                self.logger.warning("Resolution change rejected by CameraController")
            
        except Exception as e:
            self.logger.error(f"Error changing resolution: {e}")
        finally:
            # Re-enable control after operation (FLIR stays disabled while streaming)
            def _reenable():
                try:
                    cam_info2 = self.camera.cameras.get(self.current_camera) if self.camera and self.current_camera else None
                    streaming2 = bool(self.camera and hasattr(self.camera, "workers") and self.current_camera in self.camera.workers)
                    if cam_info2 and cam_info2.get("type") == CameraType.FLIR and streaming2:
                        self.resolution_combo.setEnabled(False)
                    else:
                        self.resolution_combo.setEnabled(True)
                except Exception:
                    self.resolution_combo.setEnabled(True)

            QTimer.singleShot(250, _reenable)
