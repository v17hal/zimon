# camera_interface.py - Complete rewrite for clean, thread-safe camera handling
import logging
import threading
import time
import os
from typing import List, Optional, Dict, Tuple, Callable, Union
from enum import Enum

# Suppress OpenCV warnings during camera detection
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"

import cv2
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# Try to import Basler pypylon
try:
    from pypylon import pylon
    BASLER_AVAILABLE = True
except ImportError:
    BASLER_AVAILABLE = False
    logging.getLogger("CameraController").warning("pypylon not available - Basler cameras disabled")

# Try to import FLIR Spinnaker SDK
try:
    from backend import flir_camera
    FLIR_AVAILABLE = flir_camera.FLIR_AVAILABLE
except ImportError:
    FLIR_AVAILABLE = False
    logging.getLogger("CameraController").warning("FLIR Spinnaker SDK not available - FLIR cameras disabled")


class CameraType(Enum):
    BASLER = "basler"
    WEBCAM = "webcam"
    FLIR = "flir"


class WebcamCameraWorker(QThread):
    """Dedicated worker thread for webcam capture - OpenCV only"""
    frame_ready = pyqtSignal(np.ndarray)
    error_occurred = pyqtSignal(str)
    fps_updated = pyqtSignal(float)
    
    def __init__(self, camera_name: str, camera_info: Dict):
        super().__init__()
        self.camera_name = camera_name
        self.camera_info = camera_info
        self.cap = None
        self._running = False
        self._fps_counter = 0
        self._fps_start_time = time.time()
        self._current_fps = 0.0
        self.logger = logging.getLogger(f"WebcamWorker-{camera_name}")
        
    def run(self):
        """Main webcam capture loop"""
        self._running = True
        self.logger.info(f"Starting webcam capture for {self.camera_name}")
        
        try:
            if not self._initialize_webcam():
                self.error_occurred.emit(f"Failed to initialize webcam {self.camera_name}")
                return
            
            # Main capture loop
            while self._running:
                try:
                    frame = self._capture_frame()
                    if frame is not None:
                        self.frame_ready.emit(frame)
                        self._update_fps_counter()
                    else:
                        time.sleep(0.001)
                        
                except Exception as e:
                    self.logger.error(f"Error in webcam capture loop: {e}")
                    time.sleep(0.01)
                    
        except Exception as e:
            self.error_occurred.emit(f"Webcam capture failed: {e}")
        finally:
            self._cleanup_webcam()
            self.logger.info(f"Webcam capture stopped for {self.camera_name}")
    
    def _initialize_webcam(self) -> bool:
        """Initialize webcam with automatic settings"""
        try:
            backend_id = self.camera_info.get("backend_id", cv2.CAP_ANY)
            cap = cv2.VideoCapture(self.camera_info["index"], backend_id)
            
            if not cap.isOpened():
                cap = cv2.VideoCapture(self.camera_info["index"])
                if not cap.isOpened():
                    return False
            
            # Optimize for performance
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Set resolution if specified
            if self.camera_info["settings"].get("resolution"):
                w, h = self.camera_info["settings"]["resolution"]
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            
            # FORCE AUTOMATIC MODE
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
            cap.set(cv2.CAP_PROP_AUTO_WB, 1)
            
            # Set FPS
            fps = self.camera_info["settings"].get("fps", 30)
            cap.set(cv2.CAP_PROP_FPS, fps)
            
            # Verify camera is working
            ret, test_frame = cap.read()
            if not ret or test_frame is None:
                cap.release()
                return False
            
            self.cap = cap
            self.logger.info(f"Webcam initialized successfully with automatic mode")
            return True
            
        except Exception as e:
            self.logger.error(f"Webcam initialization failed: {e}")
            return False
    
    def _capture_frame(self) -> Optional[np.ndarray]:
        """Capture frame from webcam"""
        try:
            if self.cap is None:
                return None
            ret, frame = self.cap.read()
            if ret and frame is not None:
                return frame
            return None
        except Exception as e:
            self.logger.debug(f"Webcam frame capture error: {e}")
            return None
    
    def _update_fps_counter(self):
        """Update FPS counter"""
        self._fps_counter += 1
        current_time = time.time()
        elapsed = current_time - self._fps_start_time
        
        if elapsed >= 1.0:
            fps = self._fps_counter / elapsed
            self._current_fps = fps
            self.fps_updated.emit(fps)
            self._fps_counter = 0
            self._fps_start_time = current_time
    
    def _cleanup_webcam(self):
        """Clean up webcam resources"""
        try:
            if self.cap:
                self.cap.release()
                self.cap = None
        except Exception as e:
            self.logger.error(f"Webcam cleanup error: {e}")
    
    def stop(self):
        """Stop the capture thread"""
        self._running = False
        self.wait(1000)

    def update_fps(self, fps: int):
        """Update webcam FPS (best-effort; many webcams clamp)"""
        try:
            if self.cap is not None:
                self.cap.set(cv2.CAP_PROP_FPS, int(fps))
        except Exception:
            pass
    
    def get_current_fps(self) -> float:
        """Get current FPS"""
        return self._current_fps


class BaslerCameraWorker(QThread):
    """Dedicated worker thread for Basler camera capture - pypylon only"""
    frame_ready = pyqtSignal(np.ndarray)
    error_occurred = pyqtSignal(str)
    fps_updated = pyqtSignal(float)
    
    def __init__(self, camera_name: str, camera_info: Dict):
        super().__init__()
        self.camera_name = camera_name
        self.camera_info = camera_info
        self.camera = None
        self._running = False
        self._fps_counter = 0
        self._fps_start_time = time.time()
        self._current_fps = 0.0
        self._target_fps = 60  # Default target FPS
        self._last_frame_time = 0
        self._frame_interval = 1.0 / self._target_fps
        self.logger = logging.getLogger(f"BaslerWorker-{camera_name}")
        
    def run(self):
        """Main Basler capture loop"""
        self._running = True
        self.logger.info(f"Starting Basler capture for {self.camera_name}")
        
        try:
            if not self._initialize_basler():
                self.error_occurred.emit(f"Failed to initialize Basler camera {self.camera_name}")
                return
            
            # Main capture loop
            consecutive_errors = 0
            max_consecutive_errors = 10
            
            # Update target FPS from settings
            self._target_fps = self.camera_info.get("settings", {}).get("fps", 60)
            self._frame_interval = 1.0 / self._target_fps
            self.logger.info(f"Basler target FPS set to {self._target_fps}")
            
            while self._running:
                try:
                    current_time = time.time()
                    
                    # Frame rate limiting - only process frames at target interval
                    if current_time - self._last_frame_time >= self._frame_interval:
                        frame = self._capture_frame()
                        if frame is not None:
                            self.frame_ready.emit(frame)
                            self._update_fps_counter()
                            self._last_frame_time = current_time
                            consecutive_errors = 0  # Reset error counter on success
                        else:
                            time.sleep(0.001)
                            consecutive_errors += 1
                    else:
                        # Sleep briefly to avoid CPU spinning
                        time.sleep(0.001)
                        
                        # If too many consecutive errors, stop the camera
                        if consecutive_errors >= max_consecutive_errors:
                            self.logger.error(f"Basler camera: {max_consecutive_errors} consecutive frame errors, stopping")
                            self.error_occurred.emit(f"Basler camera: {max_consecutive_errors} consecutive errors")
                            break
                        
                except Exception as e:
                    self.logger.error(f"Error in Basler capture loop: {e}")
                    consecutive_errors += 1
                    time.sleep(0.01)
                    
                    # Stop on too many errors
                    if consecutive_errors >= max_consecutive_errors:
                        self.logger.error(f"Basler camera: {max_consecutive_errors} consecutive exceptions, stopping")
                        self.error_occurred.emit(f"Basler camera: {max_consecutive_errors} exceptions")
                        break
                    
        except Exception as e:
            self.error_occurred.emit(f"Basler capture failed: {e}")
        finally:
            self._cleanup_basler()
            self.logger.info(f"Basler capture stopped for {self.camera_name}")
    
    def update_fps(self, fps: int):
        """Update target FPS during runtime"""
        self._target_fps = fps
        self._frame_interval = 1.0 / self._target_fps
        self.logger.info(f"Basler target FPS updated to {self._target_fps}")
    
    def _initialize_basler(self) -> bool:
        """Initialize Basler camera with Pylon Viewer-like settings"""
        if not BASLER_AVAILABLE:
            self.error_occurred.emit("Basler pypylon not available")
            return False
            
        try:
            # Create camera instance ONCE
            self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(self.camera_info["device"]))
            self.camera.Open()
            
            # Configure similar to Pylon Viewer for optimal performance
            try:
                # Log available camera properties for debugging
                self.logger.info("Basler camera available properties:")
                try:
                    # Try to get camera properties
                    for attr_name in dir(self.camera):
                        if not attr_name.startswith('_') and not callable(getattr(self.camera, attr_name)):
                            try:
                                attr = getattr(self.camera, attr_name)
                                if hasattr(attr, 'GetDescription'):
                                    desc = attr.GetDescription()
                                    self.logger.info(f"  {attr_name}: {desc}")
                                elif hasattr(attr, 'GetValue'):
                                    try:
                                        value = attr.GetValue()
                                        self.logger.info(f"  {attr_name}: {value}")
                                    except:
                                        self.logger.info(f"  {attr_name}: (readable)")
                            except:
                                pass
                except Exception as e:
                    self.logger.debug(f"Could not enumerate camera properties: {e}")
                
                # Get stored resolution setting
                resolution = self.camera_info.get("settings", {}).get("resolution", (1280, 1024))
                width, height = resolution
                
                # Log what we're trying to set
                self.logger.info(f"Basler camera requested resolution: {width}x{height}")
                
                # Configure Basler for maximum performance
                try:
                    # Set resolution first
                    if hasattr(self.camera, 'Width'):
                        self.camera.Width.SetValue(width)
                        self.logger.info(f"Set Basler width to {width}")
                    
                    if hasattr(self.camera, 'Height') and height:
                        self.camera.Height.SetValue(height)
                        self.logger.info(f"Set Basler height to {height}")
                    
                    # Verify the actual resolution
                    actual_width = self.camera.Width.GetValue() if hasattr(self.camera, 'Width') else None
                    actual_height = self.camera.Height.GetValue() if hasattr(self.camera, 'Height') else None
                    self.logger.info(f"Basler camera actual resolution: {actual_width}x{actual_height}")
                    
                    # Update stored resolution to actual
                    if actual_width and actual_height:
                        self.camera_info["settings"]["resolution"] = (actual_width, actual_height)
                    
                    # Configure for maximum FPS (like Pylon Viewer)
                    # 1. Set FPS from stored settings
                    try:
                        # Get stored FPS setting
                        stored_fps = self.camera_info.get("settings", {}).get("fps", 60)
                        
                        # Try different FPS control methods for Basler cameras
                        fps_set = False
                        
                        # Method 1: AcquisitionFrameRate (most common)
                        if hasattr(self.camera, 'AcquisitionFrameRateEnable'):
                            self.camera.AcquisitionFrameRateEnable.SetValue(True)
                            self.logger.info("Enabled Basler frame rate control")
                        
                        if hasattr(self.camera, 'AcquisitionFrameRate'):
                            self.camera.AcquisitionFrameRate.SetValue(float(stored_fps))
                            self.logger.info(f"Set Basler target FPS to {stored_fps} via AcquisitionFrameRate")
                            fps_set = True
                        
                        # Method 2: ResultingFrameRate (alternative)
                        elif hasattr(self.camera, 'ResultingFrameRate'):
                            self.camera.ResultingFrameRate.SetValue(float(stored_fps))
                            self.logger.info(f"Set Basler target FPS to {stored_fps} via ResultingFrameRate")
                            fps_set = True
                        
                        # Method 3: AcquisitionFrameRateAbs (older Basler models)
                        elif hasattr(self.camera, 'AcquisitionFrameRateAbs'):
                            self.camera.AcquisitionFrameRateAbs.SetValue(float(stored_fps))
                            self.logger.info(f"Set Basler target FPS to {stored_fps} via AcquisitionFrameRateAbs")
                            fps_set = True
                        
                        # Method 4: Use exposure time to control FPS (inverse relationship)
                        elif hasattr(self.camera, 'ExposureTime') and hasattr(self.camera, 'ExposureAuto'):
                            # Calculate exposure time for target FPS (exposure_time <= 1/fps)
                            target_exposure = min(1000000.0 / stored_fps, 50000.0)  # Max 50ms for safety
                            self.camera.ExposureAuto.SetValue('Off')
                            self.camera.ExposureTime.SetValue(target_exposure)
                            self.logger.info(f"Set Basler exposure to {target_exposure:.1f}us for ~{stored_fps} FPS")
                            fps_set = True
                        
                        if not fps_set:
                            self.logger.warning(f"Could not set Basler FPS - no compatible FPS control found")
                            
                    except Exception as e:
                        self.logger.warning(f"Could not set Basler FPS: {e}")
                    
                    # 2. Optimize for high-speed capture
                    try:
                        if hasattr(self.camera, 'TriggerMode'):
                            self.camera.TriggerMode.SetValue('Off')  # Free running mode
                            self.logger.info("Set Basler trigger mode to Off (free running)")
                    except Exception as e:
                        self.logger.warning(f"Could not set Basler trigger mode: {e}")
                    
                    # 3. Use fastest pixel format
                    try:
                        if hasattr(self.camera, 'PixelFormat'):
                            # Try to use Mono8 for fastest performance
                            try:
                                self.camera.PixelFormat.SetValue('Mono8')
                                self.logger.info("Set Basler pixel format to Mono8 (fastest)")
                            except:
                                # Fallback to other formats
                                try:
                                    self.camera.PixelFormat.SetValue('Mono12')
                                    self.logger.info("Set Basler pixel format to Mono12")
                                except:
                                    self.logger.info("Using default pixel format")
                    except Exception as e:
                        self.logger.warning(f"Could not set Basler pixel format: {e}")
                    
                    # 4. Disable auto features for maximum speed
                    try:
                        if hasattr(self.camera, 'ExposureAuto'):
                            self.camera.ExposureAuto.SetValue('Off')
                            if hasattr(self.camera, 'ExposureTime'):
                                self.camera.ExposureTime.SetValue(10000.0)  # 10ms exposure for good speed
                                self.logger.info("Set Basler exposure to 10ms (manual)")
                    except Exception as e:
                        self.logger.warning(f"Could not set Basler exposure: {e}")
                    
                    try:
                        if hasattr(self.camera, 'GainAuto'):
                            self.camera.GainAuto.SetValue('Off')
                            if hasattr(self.camera, 'Gain'):
                                self.camera.Gain.SetValue(1.0)
                                self.logger.info("Set Basler gain to 1.0 (manual)")
                    except Exception as e:
                        self.logger.warning(f"Could not set Basler gain: {e}")
                    
                    # 5. Optimize buffer handling
                    try:
                        if hasattr(self.camera, 'MaxNumBuffer'):
                            self.camera.MaxNumBuffer.SetValue(10)  # Optimize buffer count
                            self.logger.info("Set Basler buffer count to 10")
                    except Exception as e:
                        self.logger.warning(f"Could not set Basler buffer count: {e}")
                    
                    # 6. Use fastest transport layer settings
                    try:
                        if hasattr(self.camera, 'TransportLayer') and hasattr(self.camera.TransportLayer, 'GevSCPSPacketSize'):
                            # Set maximum packet size for best performance
                            max_packet_size = self.camera.TransportLayer.GevSCPSPacketSize.GetMax()
                            self.camera.TransportLayer.GevSCPSPacketSize.SetValue(max_packet_size)
                            self.logger.info(f"Set Basler packet size to maximum: {max_packet_size}")
                    except Exception as e:
                        self.logger.warning(f"Could not set Basler packet size: {e}")
                    
                    self.logger.info("Basler camera configured for maximum performance")
                    
                except Exception as e:
                    self.logger.warning(f"Basler performance configuration failed: {e}")
                    # Fallback to basic configuration
                    if hasattr(self.camera, 'ExposureAuto') and self.camera.ExposureAuto.IsWritable():
                        self.camera.ExposureAuto.SetValue('Continuous')
                    if hasattr(self.camera, 'GainAuto') and self.camera.GainAuto.IsWritable():
                        self.camera.GainAuto.SetValue('Continuous')
                
                # Auto white balance (keep this for color accuracy)
                if hasattr(self.camera, 'BalanceWhiteAuto') and self.camera.BalanceWhiteAuto.IsWritable():
                    self.camera.BalanceWhiteAuto.SetValue('Continuous')
                    
            except Exception as e:
                self.logger.debug(f"Some Basler settings not available: {e}")
            
            # Start continuous acquisition ONCE
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            
            self.logger.info(f"Basler camera initialized successfully with continuous acquisition")
            return True
            
        except Exception as e:
            self.logger.error(f"Basler initialization failed: {e}")
            self.error_occurred.emit(f"Basler camera initialization failed: {str(e)}")
            return False
    
    def _capture_frame(self) -> Optional[np.ndarray]:
        """Capture frame from Basler camera - robust error handling"""
        try:
            if self.camera is None or not self.camera.IsGrabbing():
                return None
                
            # Use shorter timeout and better error handling
            try:
                grab_result = self.camera.RetrieveResult(1000, pylon.TimeoutHandling_Return)
                if grab_result and grab_result.GrabSucceeded():
                    frame = grab_result.Array
                    grab_result.Release()
                    
                    # Log actual frame size on first capture
                    if not hasattr(self, '_logged_frame_size'):
                        self.logger.info(f"Basler frame size: {frame.shape}")
                        self._logged_frame_size = True
                    
                    return frame
                elif grab_result:
                    grab_result.Release()
                    return None
                else:
                    # No result available
                    return None
            except pylon.TimeoutException:
                # Timeout is normal, just return None
                return None
            except pylon.RuntimeException as e:
                self.logger.warning(f"Basler runtime error: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"Basler frame capture error: {e}")
            # Emit error for critical issues
            self.error_occurred.emit(f"Basler capture error: {str(e)}")
            return None
    
    def _update_fps_counter(self):
        """Update FPS counter"""
        self._fps_counter += 1
        current_time = time.time()
        elapsed = current_time - self._fps_start_time
        
        if elapsed >= 1.0:
            fps = self._fps_counter / elapsed
            self._current_fps = fps
            self.fps_updated.emit(fps)
            self._fps_counter = 0
            self._fps_start_time = current_time
    
    def _cleanup_basler(self):
        """Clean up Basler camera resources - more robust"""
        try:
            if self.camera:
                self.logger.info("Cleaning up Basler camera resources")
                try:
                    if self.camera.IsGrabbing():
                        self.camera.StopGrabbing()
                        self.logger.info("Basler grabbing stopped")
                except Exception as e:
                    self.logger.warning(f"Error stopping Basler grab: {e}")
                try:
                    if self.camera.IsOpen():
                        self.camera.Close()
                        self.logger.info("Basler camera closed")
                except Exception as e:
                    self.logger.warning(f"Error closing Basler camera: {e}")
                try:
                    self.camera.DestroyDevice()
                    self.logger.info("Basler device destroyed")
                except Exception as e:
                    self.logger.warning(f"Error destroying Basler device: {e}")
                self.camera = None
                self.logger.info("Basler cleanup completed")
        except Exception as e:
            self.logger.error(f"Basler cleanup error: {e}")
    
    def stop(self):
        """Stop the capture thread"""
        self._running = False
        self.wait(1000)
    
    def get_current_fps(self) -> float:
        """Get current FPS"""
        return self._current_fps


class CameraController(QObject):
    """Stabilized camera controller with hard-separated camera types"""
    camera_detected = pyqtSignal(str)
    camera_lost = pyqtSignal(str)
    worker_error = pyqtSignal(str)
    worker_fps_updated = pyqtSignal(float)
    
    def __init__(self):
        super().__init__()
        self.cameras: Dict[str, Dict] = {}
        self.workers: Dict[str, Union[WebcamCameraWorker, BaslerCameraWorker]] = {}
        self._lock = threading.Lock()
        self._ui_controls_disabled = False
        self.logger = logging.getLogger("CameraController")
        
        # Auto-detect cameras on init
        self._detect_cameras()
    
    def _detect_cameras(self):
        """Detect available cameras"""
        detected = []
        
        # Detect FLIR cameras first (highest priority)
        if FLIR_AVAILABLE:
            try:
                flir_cameras = flir_camera.detect_flir_cameras()
                for cam_name, cam_info in flir_cameras.items():
                    # Avoid circular imports: normalize to CameraType.FLIR here
                    try:
                        cam_info["type"] = CameraType.FLIR
                    except Exception:
                        pass
                    self.cameras[cam_name] = cam_info
                    detected.append(cam_name)
                    self.logger.info(f"Found FLIR camera: {cam_name}")
            except Exception as e:
                self.logger.warning(f"Error detecting FLIR cameras: {e}")
        
        # Detect Basler cameras
        if BASLER_AVAILABLE:
            try:
                tl_factory = pylon.TlFactory.GetInstance()
                devices = tl_factory.EnumerateDevices()
                for idx, device in enumerate(devices):
                    cam_name = f"Basler_{device.GetModelName()}_{idx}"
                    self.cameras[cam_name] = {
                        "type": CameraType.BASLER,
                        "device": device,
                        "settings": {
                            "resolution": (1280, 1024),  # Changed to 1280x1024 default
                            "fps": 60,  # Changed from 30 to 60
                            "zoom": 1.0
                        }
                    }
                    detected.append(cam_name)
                    self.logger.info(f"Found Basler camera: {cam_name}")
            except Exception as e:
                self.logger.warning(f"Error detecting Basler cameras: {e}")
        
        # Detect webcams
        self.logger.info("Scanning for webcams...")
        found_indices = set()
        
        # Try different backends in order of preference
        backends = [
            (cv2.CAP_DSHOW, "DirectShow"),
            (cv2.CAP_MSMF, "MediaFoundation"),
            (cv2.CAP_ANY, "Any"),
        ]
        
        for backend_id, backend_name in backends:
            # Scan a small set for fast boot; use Refresh to rescan if needed
            for idx in range(5):
                if idx in found_indices:
                    continue
                
                cap = None
                try:
                    cap = cv2.VideoCapture(idx, backend_id)
                    if cap.isOpened():
                        # Test camera with minimal settings
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        ret, frame = cap.read()
                        
                        if ret and frame is not None:
                            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            
                            # Use stable name; resolution can change at runtime
                            cam_name = f"Webcam_{idx}"
                            
                            self.cameras[cam_name] = {
                                "type": CameraType.WEBCAM,
                                "index": idx,
                                "backend": backend_name,
                                "backend_id": backend_id,
                                "settings": {
                                    "resolution": (width, height),
                                    "fps": 60,  # Changed from 30 to 60
                                    "zoom": 1.0
                                }
                            }
                            detected.append(cam_name)
                            found_indices.add(idx)
                            self.logger.info(f"Found webcam: {cam_name} ({width}x{height}) via {backend_name}")
                            # Fast boot: stop scanning after first working webcam.
                            break
                        
                        cap.release()
                    else:
                        if cap:
                            cap.release()
                except Exception as e:
                    if cap:
                        try:
                            cap.release()
                        except:
                            pass
            
            if found_indices:
                break
        
        if not detected:
            self.logger.warning("No cameras detected")
        else:
            self.logger.info(f"Detected {len(detected)} cameras: {detected}")
    
    def list_cameras(self) -> List[str]:
        """List available camera names"""
        return list(self.cameras.keys())
    
    def start_preview(self, camera_name: str, frame_callback: Callable) -> bool:
        """Start camera preview with dedicated worker thread - UI SAFE"""
        if self._ui_controls_disabled:
            self.logger.warning("UI controls are disabled - ignoring start request")
            return False
            
        if camera_name not in self.cameras:
            self.logger.error(f"Camera '{camera_name}' not found")
            return False
        
        # Stop existing preview first
        self.stop_preview(camera_name)
        
        try:
            # Create appropriate worker based on camera type
            cam_info = self.cameras[camera_name]
            if cam_info["type"] == CameraType.BASLER:
                worker = BaslerCameraWorker(camera_name, cam_info)
            elif cam_info["type"] == CameraType.FLIR:
                worker = flir_camera.FLIRCameraWorker(camera_name, cam_info)
            elif cam_info["type"] == CameraType.WEBCAM:
                worker = WebcamCameraWorker(camera_name, cam_info)
            else:
                self.logger.error(f"Unknown camera type: {cam_info['type']}")
                return False
            
            # Connect signals
            worker.frame_ready.connect(frame_callback)
            worker.error_occurred.connect(self._on_worker_error)
            worker.fps_updated.connect(self._on_fps_updated)
            
            # Start worker thread
            worker.start()
            self.workers[camera_name] = worker
            
            self.logger.info(f"Started preview for {camera_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start preview for {camera_name}: {e}")
            return False
    
    def stop_preview(self, camera_name: str):
        """Stop camera preview - UI SAFE"""
        if camera_name in self.workers:
            worker = self.workers[camera_name]
            worker.stop()
            del self.workers[camera_name]
            self.logger.info(f"Stopped preview for {camera_name}")
    
    def disable_ui_controls(self):
        """Disable all UI camera controls - CRITICAL SAFETY"""
        self._ui_controls_disabled = True
        self.logger.info("UI camera controls disabled")
    
    def enable_ui_controls(self):
        """Enable all UI camera controls"""
        self._ui_controls_disabled = False
        self.logger.info("UI camera controls enabled")
    
    def are_ui_controls_disabled(self) -> bool:
        """Check if UI controls are disabled"""
        return self._ui_controls_disabled
    
    def set_setting(self, camera_name: str, setting: str, value) -> bool:
        """Set camera setting - UI SAFE"""
        if self._ui_controls_disabled:
            self.logger.warning("UI controls are disabled - ignoring setting change")
            return False
            
        if camera_name not in self.cameras:
            return False
        
        cam_info = self.cameras[camera_name]
        
        # Only allow these settings - exposure/gain are NOT supported
        if setting not in ["resolution", "fps", "zoom"]:
            self.logger.warning(f"Setting '{setting}' is not supported (auto mode only)")
            return False
        
        # For Basler, allow resolution changes but require restart
        if cam_info["type"] == CameraType.BASLER and setting == "resolution":
            if camera_name in self.workers:
                self.logger.info(f"Stopping Basler camera for resolution change")
                self.stop_preview(camera_name)
                # Note: Resolution will be applied on next start

        # For FLIR, require stop before changing resolution (nodes usually non-writable while streaming)
        if cam_info["type"] == CameraType.FLIR and setting == "resolution":
            if camera_name in self.workers:
                self.logger.warning("Stop acquisition before changing FLIR resolution")
                return False
        
        # For Basler, update FPS in real-time
        if cam_info["type"] == CameraType.BASLER and setting == "fps":
            if camera_name in self.workers:
                worker = self.workers[camera_name]
                if hasattr(worker, 'update_fps'):
                    worker.update_fps(int(value))
                    self.logger.info(f"Updated Basler FPS to {value}")

        # For Webcam, attempt FPS update in real-time
        if cam_info["type"] == CameraType.WEBCAM and setting == "fps":
            if camera_name in self.workers:
                worker = self.workers[camera_name]
                if hasattr(worker, "update_fps"):
                    try:
                        worker.update_fps(int(value))
                    except Exception:
                        pass

        # For FLIR, update FPS in real-time (Spinnaker AcquisitionFrameRate)
        if cam_info["type"] == CameraType.FLIR and setting == "fps":
            if camera_name in self.workers:
                worker = self.workers[camera_name]
                if hasattr(worker, "update_fps"):
                    try:
                        worker.update_fps(int(value))
                    except Exception:
                        pass
        
        cam_info["settings"][setting] = value
        
        # Apply to active camera if it's a setting change that requires restart
        if setting in ["resolution"] and camera_name in self.workers:
            # Restart camera with new resolution
            self.stop_preview(camera_name)
            # Note: The calling code should restart preview if needed
        
        self.logger.info(f"Set {camera_name}.{setting} = {value}")
        return True
    
    def get_setting(self, camera_name: str, setting: str):
        """Get camera setting value"""
        if camera_name not in self.cameras:
            return None
        return self.cameras[camera_name]["settings"].get(setting)
    
    def get_current_fps(self, camera_name: str) -> Optional[float]:
        """Get current FPS from worker thread"""
        if camera_name in self.workers:
            return self.workers[camera_name].get_current_fps()
        return self.cameras[camera_name]["settings"].get("fps")
    
    def get_resolution(self, camera_name: str) -> Optional[Tuple[int, int]]:
        """Get current resolution"""
        if camera_name not in self.cameras:
            return None
        return self.cameras[camera_name]["settings"].get("resolution")
    
    def get_supported_resolutions(self, camera_name: str) -> List[Tuple[int, int]]:
        """Get supported resolutions for webcam"""
        if camera_name not in self.cameras or self.cameras[camera_name]["type"] != CameraType.WEBCAM:
            return []
        
        cam_info = self.cameras[camera_name]
        idx = cam_info["index"]
        backend_id = cam_info.get("backend_id", cv2.CAP_ANY)
        
        # Standard resolutions to test
        resolutions = [
            (3840, 2160), (2560, 1440), (1920, 1080), (1600, 1200),
            (1280, 1024), (1280, 960), (1280, 720), (1024, 768),
            (800, 600), (640, 480), (320, 240)
        ]
        
        supported = []
        cap = cv2.VideoCapture(idx, backend_id)
        if cap.isOpened():
            for w, h in resolutions:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                time.sleep(0.05)  # Brief delay for setting to apply
                
                actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                if abs(actual_w - w) <= 32 and abs(actual_h - h) <= 32:
                    supported.append((actual_w, actual_h))
            cap.release()
        
        # Remove duplicates and sort highest first
        unique = []
        for r in sorted(set(supported), reverse=True):
            if r not in unique:
                unique.append(r)
        return unique
    
    def refresh_cameras(self):
        """Refresh camera list - PROTECTS BASLER from reinitialization"""
        if self._ui_controls_disabled:
            self.logger.warning("UI controls are disabled - ignoring refresh request")
            return
            
        # Disable UI controls during refresh
        self.disable_ui_controls()
        
        try:
            # Stop all previews except Basler (Basler protection)
            for cam_name, worker in list(self.workers.items()):
                cam_info = self.cameras.get(cam_name, {})
                if cam_info.get("type") == CameraType.WEBCAM:
                    self.stop_preview(cam_name)
                elif cam_info.get("type") == CameraType.FLIR:
                    # FLIR must be stopped before re-detecting to release SystemPtr
                    self.stop_preview(cam_name)
                elif cam_info.get("type") == CameraType.BASLER:
                    self.logger.warning(f"NOT stopping Basler camera {cam_name} during refresh")
            
            # Re-detect webcams + FLIR (Basler protected)
            self.logger.info("Refreshing cameras (Basler protected)")
            old_basler = {}
            for cam_name, cam_info in list(self.cameras.items()):
                if cam_info.get("type") == CameraType.BASLER:
                    old_basler[cam_name] = cam_info
            
            # Clear and re-detect
            self.cameras.clear()
            self._detect_cameras()
            
            # Restore Basler cameras
            self.cameras.update(old_basler)
            
            self.logger.info(f"Camera list refreshed. Found {len(self.cameras)} cameras (Basler protected)")
            
        finally:
            # Re-enable UI controls after refresh
            self.enable_ui_controls()
    
    def _on_worker_error(self, error_msg: str):
        """Handle worker thread errors"""
        self.logger.error(f"Camera worker error: {error_msg}")
        self.worker_error.emit(error_msg)
    
    def _on_fps_updated(self, fps: float):
        """Handle FPS updates from workers"""
        self.worker_fps_updated.emit(fps)
    
    def cleanup(self):
        """Clean up all camera resources"""
        for cam_name in list(self.workers.keys()):
            self.stop_preview(cam_name)
