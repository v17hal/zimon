"""
Analysis Tab for ZIMON

Provides behavioral analysis capabilities using ZebraZoom integration.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QGroupBox, QTableWidget, QTableWidgetItem,
    QTextEdit, QProgressBar, QComboBox, QSpinBox, QMessageBox,
    QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import logging
import os
from pathlib import Path

logger = logging.getLogger("analysis_tab")


class AnalysisWorker(QThread):
    """Worker thread for running analysis"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, zebrazoom_integration, video_path, config_path=None):
        super().__init__()
        self.zebrazoom = zebrazoom_integration
        self.video_path = video_path
        self.config_path = config_path
        self._should_stop = False
    
    def stop(self):
        """Stop the analysis"""
        self._should_stop = True
    
    def run(self):
        try:
            self.status.emit("Starting analysis...")
            self.progress.emit(10)
            
            if self._should_stop:
                return
            
            self.status.emit("Validating configuration...")
            self.progress.emit(20)
            
            if self._should_stop:
                return
            
            self.status.emit("Running ZebraZoom analysis...")
            self.progress.emit(30)
            
            # Run analysis with progress callback
            result = self.zebrazoom.analyze_video(
                self.video_path,
                self.config_path,
                progress_callback=lambda p: self._update_progress(p)
            )
            
            if self._should_stop:
                return
            
            self.progress.emit(90)
            self.status.emit("Finalizing results...")
            
            # Simulate final processing
            import time
            for i in range(10):
                if self._should_stop:
                    return
                time.sleep(0.1)
                self.progress.emit(90 + i)
            
            self.progress.emit(100)
            self.status.emit("Analysis complete")
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))
    
    def _update_progress(self, progress):
        """Update progress if not stopped"""
        if not self._should_stop:
            self.progress.emit(min(progress, 95))  # Cap at 95% for final processing


class AnalysisTab(QWidget):
    """Analysis tab widget"""
    
    def __init__(self, zebrazoom_integration=None):
        super().__init__()
        self.zebrazoom = zebrazoom_integration
        self.current_data = None
        self.bouts = []
        self.video_path = None
        self.config_path = None
        
        self._build_ui()
        
        # Show warning if ZebraZoom not available
        if not self.zebrazoom or not self.zebrazoom.is_available():
            self._show_zebrazoom_warning()
    
    def _show_zebrazoom_warning(self):
        """Show warning that ZebraZoom is not available"""
        warning_label = QLabel(
            "⚠️ ZebraZoom is not available.\n"
            "Please install ZebraZoom or specify its path in Settings (⚙ icon)."
        )
        warning_label.setStyleSheet("""
            color: #fbbf24;
            font-size: 12px;
            padding: 12px;
            background: #2a2d36;
            border-radius: 8px;
            border: 1px solid #fbbf24;
        """)
        warning_label.setWordWrap(True)
        
        # Insert at the top
        layout = self.layout()
        layout.insertWidget(0, warning_label)
    
    def _build_ui(self):
        # Create main layout with scroll area for responsive design
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 8, 0, 0)
        main_layout.setSpacing(0)
        
        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: #1a1d23;
            }
        """)
        
        # Create content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)
        
        # Header
        header = QLabel("Behavioral Analysis")
        header.setStyleSheet("font-size: 18px; font-weight: 600; color: #e8e9ea; padding: 8px 0px;")
        content_layout.addWidget(header)
        
        # File selection section
        file_section = QGroupBox("Video Analysis")
        file_section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        file_layout = QVBoxLayout(file_section)
        file_layout.setContentsMargins(16, 20, 16, 16)
        file_layout.setSpacing(12)
        
        # Video file selection
        video_layout = QHBoxLayout()
        video_layout.setSpacing(10)
        
        video_label = QLabel("Video:")
        video_label.setMinimumWidth(50)
        video_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        
        self.video_path_label = QLabel("No video selected")
        self.video_path_label.setStyleSheet("color: #a0a4ac; padding: 4px;")
        self.video_path_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.video_path_label.setWordWrap(True)
        
        video_btn = QPushButton("Select Video")
        video_btn.clicked.connect(self._select_video)
        video_btn.setMinimumWidth(120)
        video_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        
        video_layout.addWidget(video_label)
        video_layout.addWidget(self.video_path_label, 1)
        video_layout.addWidget(video_btn)
        
        file_layout.addLayout(video_layout)
        
        # Config file selection
        config_layout = QHBoxLayout()
        config_layout.setSpacing(10)
        
        config_label = QLabel("Config:")
        config_label.setMinimumWidth(50)
        config_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        
        self.config_path_label = QLabel("Using default config")
        self.config_path_label.setStyleSheet("color: #a0a4ac; padding: 4px;")
        self.config_path_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.config_path_label.setWordWrap(True)
        
        config_btn = QPushButton("Select Config")
        config_btn.clicked.connect(self._select_config)
        config_btn.setMinimumWidth(120)
        config_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        
        config_layout.addWidget(config_label)
        config_layout.addWidget(self.config_path_label, 1)
        config_layout.addWidget(config_btn)
        
        file_layout.addLayout(config_layout)
        
        # Analyze button - spans full width
        self.analyze_btn = QPushButton("▶ Run Analysis")
        self.analyze_btn.setMinimumHeight(40)
        self.analyze_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.analyze_btn.clicked.connect(self._run_analysis)
        file_layout.addWidget(self.analyze_btn)
        
        # Cancel button - initially hidden
        self.cancel_btn = QPushButton("✖ Cancel Analysis")
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.cancel_btn.clicked.connect(self._cancel_analysis)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        file_layout.addWidget(self.cancel_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        file_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #a0a4ac; font-size: 11px;")
        self.status_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.status_label.setWordWrap(True)
        file_layout.addWidget(self.status_label)
        
        content_layout.addWidget(file_section)
        
        # Results section
        results_section = QGroupBox("Analysis Results")
        results_section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        results_layout = QVBoxLayout(results_section)
        results_layout.setContentsMargins(16, 20, 16, 16)
        results_layout.setSpacing(12)
        
        # Results table with proper sizing
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Parameter", "Value", "Unit", "Notes"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.results_table.setMinimumHeight(200)
        results_layout.addWidget(self.results_table)
        
        content_layout.addWidget(results_section)
        
        # Bout detection section
        bout_section = QGroupBox("Bout Detection")
        bout_section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bout_layout = QVBoxLayout(bout_section)
        bout_layout.setContentsMargins(16, 20, 16, 16)
        bout_layout.setSpacing(12)
        
        # Parameters with proper alignment
        params_layout = QHBoxLayout()
        params_layout.setSpacing(10)
        
        min_distance_label = QLabel("Min Distance:")
        min_distance_label.setMinimumWidth(100)
        min_distance_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        
        self.min_distance_spin = QSpinBox()
        self.min_distance_spin.setRange(1, 100)
        self.min_distance_spin.setValue(5)
        self.min_distance_spin.setSuffix(" px")
        self.min_distance_spin.setMinimumWidth(80)
        self.min_distance_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        
        min_frames_label = QLabel("Min Frames:")
        min_frames_label.setMinimumWidth(80)
        min_frames_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        
        self.min_frames_spin = QSpinBox()
        self.min_frames_spin.setRange(1, 100)
        self.min_frames_spin.setValue(10)
        self.min_frames_spin.setMinimumWidth(80)
        self.min_frames_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        
        detect_btn = QPushButton("Detect Bouts")
        detect_btn.clicked.connect(self._detect_bouts)
        detect_btn.setMinimumWidth(120)
        detect_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        
        params_layout.addWidget(min_distance_label)
        params_layout.addWidget(self.min_distance_spin)
        params_layout.addWidget(min_frames_label)
        params_layout.addWidget(self.min_frames_spin)
        params_layout.addStretch()
        params_layout.addWidget(detect_btn)
        
        bout_layout.addLayout(params_layout)
        
        # Bout results
        self.bout_count_label = QLabel("Bouts detected: 0")
        self.bout_count_label.setStyleSheet("color: #4fc3f7; font-weight: 600;")
        self.bout_count_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bout_layout.addWidget(self.bout_count_label)
        
        content_layout.addWidget(bout_section)
        
        # Clustering section
        cluster_section = QGroupBox("Behavioral Clustering")
        cluster_section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        cluster_layout = QVBoxLayout(cluster_section)
        cluster_layout.setContentsMargins(16, 20, 16, 16)
        cluster_layout.setSpacing(12)
        
        cluster_params = QHBoxLayout()
        cluster_params.setSpacing(10)
        
        clusters_label = QLabel("Number of Clusters:")
        clusters_label.setMinimumWidth(140)
        clusters_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        
        self.n_clusters_spin = QSpinBox()
        self.n_clusters_spin.setRange(2, 20)
        self.n_clusters_spin.setValue(5)
        self.n_clusters_spin.setMinimumWidth(80)
        self.n_clusters_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        
        cluster_btn = QPushButton("Cluster Bouts")
        cluster_btn.clicked.connect(self._cluster_bouts)
        cluster_btn.setMinimumWidth(120)
        cluster_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        
        cluster_params.addWidget(clusters_label)
        cluster_params.addWidget(self.n_clusters_spin)
        cluster_params.addStretch()
        cluster_params.addWidget(cluster_btn)
        
        cluster_layout.addLayout(cluster_params)
        
        self.cluster_results_label = QLabel("")
        self.cluster_results_label.setStyleSheet("color: #9aa0aa;")
        self.cluster_results_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.cluster_results_label.setWordWrap(True)
        cluster_layout.addWidget(self.cluster_results_label)
        
        content_layout.addWidget(cluster_section)
        
        # Add stretch at bottom for proper spacing
        content_layout.addStretch()
        
        # Set scroll area content
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
    
    def _select_video(self):
        """Select video file for analysis"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.avi *.mp4 *.mov *.mkv);;All Files (*)"
        )
        
        if file_path:
            self.video_path_label.setText(os.path.basename(file_path))
            self.video_path_label.setToolTip(file_path)
            self.video_path = file_path
    
    def _select_config(self):
        """Select ZebraZoom config file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Config File",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            self.config_path_label.setText(os.path.basename(file_path))
            self.config_path_label.setToolTip(file_path)
            self.config_path = file_path
        else:
            self.config_path = None
            self.config_path_label.setText("Using default config")
    
    def _run_analysis(self):
        """Run ZebraZoom analysis on selected video"""
        if not hasattr(self, 'video_path') or not self.video_path:
            QMessageBox.warning(self, "No Video", "Please select a video file first")
            return
        
        if not self.zebrazoom or not self.zebrazoom.is_available():
            QMessageBox.warning(
                self,
                "ZebraZoom Not Available",
                "ZebraZoom is not installed or not found.\n\n"
                "Please install ZebraZoom or specify its path in settings."
            )
            return
        
        # Update button visibility
        self.analyze_btn.setVisible(False)
        self.cancel_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Preparing analysis...")
        
        # Create worker thread
        self.worker = AnalysisWorker(
            self.zebrazoom,
            self.video_path,
            getattr(self, 'config_path', None)
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(self.status_label.setText)
        self.worker.finished.connect(self._on_analysis_finished)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.start()
    
    def _cancel_analysis(self):
        """Cancel the running analysis"""
        if hasattr(self, 'worker') and self.worker:
            self.worker.stop()
            self.worker.wait(1000)  # Wait up to 1 second for thread to finish
        
        # Reset UI
        self.analyze_btn.setVisible(True)
        self.cancel_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Analysis cancelled")
    
    def _on_analysis_finished(self, result):
        """Handle analysis completion"""
        self.analyze_btn.setVisible(True)
        self.cancel_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Analysis completed successfully")
        
        # Display results
        self._display_results(result)
        
        QMessageBox.information(self, "Analysis Complete", "Video analysis completed successfully!")
    
    def _on_analysis_error(self, error_msg):
        """Handle analysis error"""
        self.analyze_btn.setVisible(True)
        self.cancel_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Error: {error_msg}")
        
        QMessageBox.critical(self, "Analysis Error", f"Analysis failed:\n{error_msg}")
    
    def _display_results(self, result):
        """Display analysis results in table"""
        # Clear existing results
        self.results_table.setRowCount(0)
        
        # Add result rows (simplified - would parse actual ZebraZoom output)
        if isinstance(result, dict):
            row = 0
            for key, value in result.items():
                if key not in ['status', 'video', 'output']:
                    self.results_table.insertRow(row)
                    self.results_table.setItem(row, 0, QTableWidgetItem(str(key)))
                    self.results_table.setItem(row, 1, QTableWidgetItem(str(value)))
                    self.results_table.setItem(row, 2, QTableWidgetItem(""))
                    self.results_table.setItem(row, 3, QTableWidgetItem(""))
                    row += 1
    
    def _detect_bouts(self):
        """Detect movement bouts from tracking data"""
        if self.current_data is None:
            QMessageBox.warning(self, "No Data", "Please run analysis first")
            return
        
        try:
            min_distance = self.min_distance_spin.value()
            min_frames = self.min_frames_spin.value()
            
            self.bouts = self.zebrazoom.detect_bouts(
                self.current_data,
                min_distance=min_distance,
                min_frames=min_frames
            )
            
            self.bout_count_label.setText(f"Bouts detected: {len(self.bouts)}")
            self.status_label.setText(f"Detected {len(self.bouts)} movement bouts")
            
        except Exception as e:
            logger.error(f"Error detecting bouts: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Bout detection failed:\n{str(e)}")
    
    def _cluster_bouts(self):
        """Cluster detected bouts"""
        if not self.bouts:
            QMessageBox.warning(self, "No Bouts", "Please detect bouts first")
            return
        
        try:
            n_clusters = self.n_clusters_spin.value()
            
            cluster_result = self.zebrazoom.cluster_bouts(
                self.bouts,
                n_clusters=n_clusters
            )
            
            # Display cluster results
            cluster_info = f"Clustered {len(self.bouts)} bouts into {n_clusters} clusters"
            self.cluster_results_label.setText(cluster_info)
            self.status_label.setText(cluster_info)
            
        except Exception as e:
            logger.error(f"Error clustering bouts: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Clustering failed:\n{str(e)}")

