from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QGroupBox, QMessageBox, QFileDialog, QLineEdit
)
from PyQt6.QtCore import Qt
import serial.tools.list_ports
import logging
import os


class SettingsDialog(QDialog):
    def __init__(self, arduino_controller, parent=None, zebrazoom_integration=None):
        super().__init__(parent)
        self.arduino = arduino_controller
        self.zebrazoom = zebrazoom_integration
        self.logger = logging.getLogger("settings_dialog")
        
        self.setWindowTitle("Settings")
        self.setMinimumWidth(550)
        self.setMinimumHeight(450)
        
        # Apply dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #0a0b0f;
                color: #e8e9ea;
            }
            QGroupBox {
                border: 1px solid #2a2d36;
                background: #14161a;
                border-radius: 12px;
                padding: 16px;
                margin-top: 8px;
                font-weight: 600;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 18px;
                padding: 0 8px;
                color: #b8bcc8;
                background-color: #14161a;
            }
            QLabel {
                color: #e8e9ea;
            }
            QComboBox {
                background: #1a1c21;
                border: 1px solid #2a2d36;
                border-radius: 6px;
                padding: 6px 10px;
                color: #e8e9ea;
                min-height: 28px;
            }
            QComboBox:hover {
                border-color: #3a3d46;
            }
            QComboBox:focus {
                border-color: #6366f1;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #b8bcc8;
            }
            QPushButton {
                background: #6366f1;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-weight: 500;
                min-height: 36px;
            }
            QPushButton:hover {
                background: #818cf8;
            }
            QPushButton:pressed {
                background: #4f46e5;
            }
            QPushButton:disabled {
                background: #2a2d36;
                color: #7a7d85;
            }
            QLineEdit {
                background: #1a1c21;
                border: 1px solid #2a2d36;
                border-radius: 6px;
                padding: 6px 10px;
                color: #e8e9ea;
                min-height: 28px;
            }
            QLineEdit:hover {
                border-color: #3a3d46;
            }
            QLineEdit:focus {
                border-color: #6366f1;
                background: #24262c;
            }
            QLineEdit:disabled {
                background: #16181c;
                border-color: #16181c;
                color: #7a7d85;
            }
        """)
        
        self._build_ui()
        self._refresh_ports()
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Arduino Settings Group
        arduino_group = QGroupBox("Arduino Settings")
        arduino_layout = QVBoxLayout(arduino_group)
        arduino_layout.setSpacing(12)
        arduino_layout.setContentsMargins(16, 20, 16, 16)
        
        # Connection Status
        status_layout = QHBoxLayout()
        status_layout.setSpacing(10)
        
        status_label = QLabel("Connection Status:")
        status_label.setMinimumWidth(120)
        self.status_value = QLabel("Checking...")
        self.status_value.setStyleSheet("font-weight: 600;")
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.status_value)
        status_layout.addStretch()
        
        arduino_layout.addLayout(status_layout)
        
        # Port Selection
        port_layout = QHBoxLayout()
        port_layout.setSpacing(10)
        
        port_label = QLabel("Serial Port:")
        port_label.setMinimumWidth(120)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(200)
        self.port_combo.setEditable(False)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setMinimumWidth(80)
        refresh_btn.clicked.connect(self._refresh_ports)
        
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_combo, 1)
        port_layout.addWidget(refresh_btn)
        
        arduino_layout.addLayout(port_layout)
        
        # Connection Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setMinimumWidth(100)
        self.connect_btn.clicked.connect(self._connect_arduino)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setMinimumWidth(100)
        self.disconnect_btn.clicked.connect(self._disconnect_arduino)
        self.disconnect_btn.setEnabled(False)
        
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setMinimumWidth(120)
        self.test_btn.clicked.connect(self._test_connection)
        
        button_layout.addWidget(self.connect_btn)
        button_layout.addWidget(self.disconnect_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.test_btn)
        
        arduino_layout.addLayout(button_layout)
        
        # Current Port Info
        info_layout = QHBoxLayout()
        info_label = QLabel("Current Port:")
        info_label.setMinimumWidth(120)
        self.current_port_label = QLabel("None")
        self.current_port_label.setStyleSheet("color: #9aa0aa;")
        info_layout.addWidget(info_label)
        info_layout.addWidget(self.current_port_label)
        info_layout.addStretch()
        
        arduino_layout.addLayout(info_layout)
        
        layout.addWidget(arduino_group)
        
        # ZebraZoom Settings Group - Always show
        zebrazoom_group = QGroupBox("ZebraZoom Settings")
        zz_layout = QVBoxLayout(zebrazoom_group)
        zz_layout.setContentsMargins(16, 20, 16, 16)
        zz_layout.setSpacing(12)
        
        # Info label
        info_label = QLabel("Specify the path to ZebraZoom.exe file (not the folder)")
        info_label.setStyleSheet("color: #9aa0aa; font-size: 11px; padding-bottom: 8px;")
        info_label.setWordWrap(True)
        zz_layout.addWidget(info_label)
        
        # Status
        zz_status_layout = QHBoxLayout()
        zz_status_layout.setSpacing(10)
        
        zz_status_label = QLabel("Status:")
        zz_status_label.setMinimumWidth(120)
        self.zz_status_value = QLabel("Checking...")
        self.zz_status_value.setStyleSheet("font-weight: 600;")
        zz_status_layout.addWidget(zz_status_label)
        zz_status_layout.addWidget(self.zz_status_value)
        zz_status_layout.addStretch()
        zz_layout.addLayout(zz_status_layout)
        
        # Path selection
        zz_path_layout = QHBoxLayout()
        zz_path_layout.setSpacing(10)
        
        zz_path_label = QLabel("ZebraZoom.exe:")
        zz_path_label.setMinimumWidth(120)
        self.zz_path_edit = QLineEdit()
        self.zz_path_edit.setPlaceholderText("C:\\path\\to\\ZebraZoom.exe")
        
        # Initialize path if zebrazoom exists
        if self.zebrazoom:
            if self.zebrazoom.zebrazoom_exe:
                self.zz_path_edit.setText(self.zebrazoom.zebrazoom_exe)
            elif self.zebrazoom.zebrazoom_lib:
                self.zz_path_edit.setText("Library (imported)")
                self.zz_path_edit.setEnabled(False)
            else:
                # Try to find default path
                default_path = r"C:\Users\{}\Downloads\ZebraZoom-Windows\ZebraZoom.exe".format(os.getenv("USERNAME", ""))
                if os.path.exists(default_path):
                    self.zz_path_edit.setText(default_path)
        
        zz_browse_btn = QPushButton("Browse")
        zz_browse_btn.setMinimumWidth(80)
        zz_browse_btn.clicked.connect(self._browse_zebrazoom_path)
        
        zz_path_layout.addWidget(zz_path_label)
        zz_path_layout.addWidget(self.zz_path_edit, 1)
        zz_path_layout.addWidget(zz_browse_btn)
        
        zz_layout.addLayout(zz_path_layout)
        
        # Test button
        zz_test_btn = QPushButton("Test & Save")
        zz_test_btn.setMinimumWidth(120)
        zz_test_btn.clicked.connect(self._test_zebrazoom)
        zz_layout.addWidget(zz_test_btn)
        
        layout.addWidget(zebrazoom_group)
        
        # Initialize ZebraZoom if not exists
        if not self.zebrazoom:
            try:
                from backend.zebrazoom_integration import ZebraZoomIntegration
                self.zebrazoom = ZebraZoomIntegration()
            except Exception as e:
                self.logger.warning(f"Could not initialize ZebraZoom: {e}")
                self.zebrazoom = None
        
        self._update_zebrazoom_status()
        
        layout.addStretch()
        
        # Dialog Buttons
        dialog_buttons = QHBoxLayout()
        dialog_buttons.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self.accept)
        dialog_buttons.addWidget(close_btn)
        
        layout.addLayout(dialog_buttons)
        
        # Update UI state
        self._update_ui_state()
        
    def _refresh_ports(self):
        """Refresh the list of available serial ports"""
        self.port_combo.clear()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        
        if ports:
            self.port_combo.addItems(ports)
            # Select current port if connected
            if self.arduino and self.arduino.is_connected():
                current_port = getattr(self.arduino, 'port', None)
                if current_port and current_port in ports:
                    index = self.port_combo.findText(current_port)
                    if index >= 0:
                        self.port_combo.setCurrentIndex(index)
        else:
            self.port_combo.addItem("No ports available")
            self.port_combo.setEnabled(False)
            
    def _update_ui_state(self):
        """Update UI based on connection state"""
        if not self.arduino:
            self.status_value.setText("Not Available")
            self.status_value.setStyleSheet("color: #d04f4f; font-weight: 600;")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(False)
            self.current_port_label.setText("None")
            return
            
        is_connected = self.arduino.is_connected()
        
        if is_connected:
            port = getattr(self.arduino, 'port', 'Unknown')
            self.status_value.setText("Connected")
            self.status_value.setStyleSheet("color: #4fc3f7; font-weight: 600;")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.current_port_label.setText(port)
        else:
            self.status_value.setText("Disconnected")
            self.status_value.setStyleSheet("color: #d04f4f; font-weight: 600;")
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.current_port_label.setText("None")
            
    def _connect_arduino(self):
        """Connect to selected Arduino port"""
        if not self.arduino:
            QMessageBox.warning(self, "Error", "Arduino controller not available")
            return
            
        selected_port = self.port_combo.currentText()
        if not selected_port or selected_port == "No ports available":
            QMessageBox.warning(self, "Error", "Please select a valid serial port")
            return
            
        try:
            self.status_value.setText("Connecting...")
            self.status_value.setStyleSheet("color: #f5c542; font-weight: 600;")
            self.connect_btn.setEnabled(False)
            
            if self.arduino.connect(selected_port):
                QMessageBox.information(self, "Success", f"Connected to {selected_port}")
                self._update_ui_state()
                # Notify parent to update status
                if self.parent():
                    if hasattr(self.parent(), '_update_arduino_status'):
                        port = getattr(self.arduino, 'port', 'Unknown')
                        self.parent()._update_arduino_status(True, f"Connected ({port})")
            else:
                QMessageBox.warning(self, "Error", f"Failed to connect to {selected_port}\n\nMake sure:\n- Arduino is connected\n- Firmware is loaded\n- Port is not in use by another program")
                self._update_ui_state()
        except Exception as e:
            self.logger.error(f"Connection error: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Connection error: {str(e)}")
            self._update_ui_state()
            
    def _disconnect_arduino(self):
        """Disconnect from Arduino"""
        if not self.arduino:
            return
            
        try:
            self.arduino.close()
            self._update_ui_state()
            # Notify parent to update status
            if self.parent():
                if hasattr(self.parent(), '_update_arduino_status'):
                    self.parent()._update_arduino_status(False, "Disconnected")
            QMessageBox.information(self, "Disconnected", "Arduino disconnected successfully")
        except Exception as e:
            self.logger.error(f"Disconnect error: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Error disconnecting: {str(e)}")
            
    def _test_connection(self):
        """Test the Arduino connection"""
        if not self.arduino:
            QMessageBox.warning(self, "Error", "Arduino controller not available")
            return
            
        if not self.arduino.is_connected():
            QMessageBox.warning(self, "Not Connected", "Arduino is not connected. Please connect first.")
            return
            
        try:
            # Try sending STATUS command
            reply = self.arduino.send("STATUS")
            if reply:
                QMessageBox.information(self, "Test Successful", f"Arduino responded:\n{reply}")
            else:
                QMessageBox.warning(self, "Test Failed", "Arduino did not respond to STATUS command")
        except Exception as e:
            self.logger.error(f"Test error: {e}", exc_info=True)
            QMessageBox.critical(self, "Test Error", f"Error testing connection: {str(e)}")
            
    def _browse_zebrazoom_path(self):
        """Browse for ZebraZoom executable"""
        # Start from common location if exists
        start_dir = r"C:\Users\{}\Downloads\ZebraZoom-Windows".format(os.getenv("USERNAME", ""))
        if not os.path.exists(start_dir):
            start_dir = ""
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select ZebraZoom.exe File",
            start_dir,
            "Executable Files (*.exe);;All Files (*)"
        )
        
        if file_path:
            # Verify it's actually ZebraZoom.exe
            if not file_path.lower().endswith('.exe'):
                QMessageBox.warning(self, "Invalid File", "Please select the ZebraZoom.exe file")
                return
            
            self.zz_path_edit.setText(file_path)
            # Update ZebraZoom integration
            if self.zebrazoom:
                self.zebrazoom.zebrazoom_exe = file_path
                self.zebrazoom.zebrazoom_lib = None
            else:
                # Create new integration if doesn't exist
                try:
                    from backend.zebrazoom_integration import ZebraZoomIntegration
                    self.zebrazoom = ZebraZoomIntegration(zebrazoom_path=file_path)
                except Exception as e:
                    self.logger.error(f"Error creating ZebraZoom integration: {e}")
            
            self._update_zebrazoom_status()
    
    def _test_zebrazoom(self):
        """Test ZebraZoom connection and save path"""
        # Get path from text field
        path = self.zz_path_edit.text().strip()
        
        if not path or path == "Library (imported)":
            QMessageBox.warning(self, "No Path", "Please specify the path to ZebraZoom.exe")
            return
        
        # Verify file exists
        if not os.path.exists(path):
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The file does not exist:\n{path}\n\nPlease check the path and try again."
            )
            return
        
        # Verify it's an .exe file
        if not path.lower().endswith('.exe'):
            QMessageBox.warning(
                self,
                "Invalid File",
                "Please select the ZebraZoom.exe file, not a folder.\n\n"
                "The path should end with: ZebraZoom.exe"
            )
            return
        
        # Create or update ZebraZoom integration
        try:
            if not self.zebrazoom:
                from backend.zebrazoom_integration import ZebraZoomIntegration
                self.zebrazoom = ZebraZoomIntegration(zebrazoom_path=path)
            else:
                self.zebrazoom.zebrazoom_exe = path
                self.zebrazoom.zebrazoom_lib = None
            
            # Test if available
            if self.zebrazoom.is_available():
                # Check for optional dependencies using the same method as the integration module
                missing_deps = []
                
                # Check pandas
                try:
                    import pandas
                except ImportError:
                    missing_deps.append("pandas")
                
                # Check numpy
                try:
                    import numpy
                except ImportError:
                    missing_deps.append("numpy")
                
                # Check scipy
                try:
                    import scipy
                except ImportError:
                    missing_deps.append("scipy")
                
                # Check scikit-learn
                try:
                    import sklearn
                except ImportError:
                    missing_deps.append("scikit-learn")
                
                # Check h5py
                try:
                    import h5py
                except ImportError:
                    missing_deps.append("h5py")
                
                if missing_deps:
                    import sys
                    dep_list = ", ".join(missing_deps)
                    python_exe = sys.executable
                    
                    # Create install command
                    install_cmd = f"{python_exe} -m pip install {dep_list}"
                    
                    msg = QMessageBox(self)
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.setWindowTitle("Dependencies Missing")
                    msg.setText(
                        f"ZebraZoom path is set, but some optional dependencies are missing:\n\n"
                        f"Missing: {dep_list}\n\n"
                        f"To install, run this command in a terminal:\n\n"
                        f"{install_cmd}\n\n"
                        f"Or run the install_dependencies.py script:\n"
                        f"{python_exe} install_dependencies.py\n\n"
                        f"Note: Make sure you're using the same Python that runs ZIMON:\n"
                        f"{python_exe}"
                    )
                    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                    msg.exec()
                else:
                    QMessageBox.information(
                        self,
                        "Success",
                        f"ZebraZoom found and ready to use!\n\nPath: {path}\n\n"
                        "All dependencies are installed.\n"
                        "You can now use the Analysis tab to analyze videos."
                    )
                
                self._update_zebrazoom_status()
                
                # Update parent window's zebrazoom reference
                if self.parent() and hasattr(self.parent(), 'zebrazoom'):
                    self.parent().zebrazoom = self.zebrazoom
                    # Update analysis tab if it exists
                    if hasattr(self.parent(), '_update_zebrazoom_in_analysis'):
                        self.parent()._update_zebrazoom_in_analysis()
            else:
                QMessageBox.warning(
                    self,
                    "Not Available",
                    "ZebraZoom path was set but could not be verified.\n\n"
                    "Please ensure:\n"
                    "1. The file is ZebraZoom.exe\n"
                    "2. The file is not corrupted\n"
                    "3. You have permission to access it"
                )
        except Exception as e:
            self.logger.error(f"Error testing ZebraZoom: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error setting up ZebraZoom:\n{str(e)}"
            )
    
    def _update_zebrazoom_status(self):
        """Update ZebraZoom status display"""
        if not self.zebrazoom:
            return
        
        if self.zebrazoom.is_available():
            if self.zebrazoom.zebrazoom_exe:
                self.zz_status_value.setText("Available (Executable)")
                self.zz_status_value.setStyleSheet("color: #4fc3f7; font-weight: 600;")
            elif self.zebrazoom.zebrazoom_lib:
                self.zz_status_value.setText("Available (Library)")
                self.zz_status_value.setStyleSheet("color: #4fc3f7; font-weight: 600;")
        else:
            self.zz_status_value.setText("Not Available")
            self.zz_status_value.setStyleSheet("color: #d04f4f; font-weight: 600;")
    
    def showEvent(self, event):
        """Update UI when dialog is shown"""
        super().showEvent(event)
        self._refresh_ports()
        self._update_ui_state()
        if self.zebrazoom:
            self._update_zebrazoom_status()

