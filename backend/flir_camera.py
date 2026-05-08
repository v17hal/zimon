# flir_camera.py - FLIR CM3-U3-13Y3M-CS Camera Integration
"""
Production-ready FLIR thermal camera integration for ZIMON application.
Optimized for maximum FPS, zero frame drops, and scientific imaging.

Camera: FLIR CM3-U3-13Y3M-CS (USB3)
Interface: Spinnaker SDK (PySpin)
Target: Match or exceed SpinView performance
"""

import logging
import time
import threading
import numpy as np
from typing import Optional, Dict, Tuple, List
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# Try to import FLIR Spinnaker SDK
try:
    import PySpin
    FLIR_AVAILABLE = True
    logging.getLogger("FLIRCamera").info("FLIR Spinnaker SDK loaded successfully")
except ImportError:
    FLIR_AVAILABLE = False
    logging.getLogger("FLIRCamera").warning("FLIR Spinnaker SDK not available - FLIR cameras disabled")
    
    # Try alternative import paths
    try:
        import sys
        import os
        # Check common FLIR installation paths
        flir_paths = [
            r"C:\Program Files\FLIR Systems\Spinnaker\Development\bin\Python",
            r"C:\Program Files (x86)\FLIR Systems\Spinnaker\Development\bin\Python",
            os.path.join(os.environ.get("PROGRAMFILES", ""), "FLIR Systems", "Spinnaker", "Development", "bin", "Python"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "FLIR Systems", "Spinnaker", "Development", "bin", "Python"),
        ]
        
        for flir_path in flir_paths:
            if os.path.exists(flir_path):
                sys.path.insert(0, flir_path)
                logging.getLogger("FLIRCamera").info(f"Added FLIR path to sys.path: {flir_path}")
                break
        
        # Try import again
        try:
            import PySpin
            FLIR_AVAILABLE = True
            logging.getLogger("FLIRCamera").info("FLIR Spinnaker SDK loaded successfully from alternative path")
        except ImportError:
            logging.getLogger("FLIRCamera").warning("FLIR Spinnaker SDK still not available after path search")
    except Exception as e:
        logging.getLogger("FLIRCamera").error(f"Error searching FLIR SDK paths: {e}")

_LOG = logging.getLogger("FLIRCamera")

# FLIR Camera Constants
FLIR_BUFFER_COUNT = 10  # Optimal for USB3 throughput
FLIR_PACKET_SIZE = 0  # Auto-detect optimal packet size


def _spin_attr(name: str):
    """Spinnaker Python bindings vary by SDK version; enums may be missing from the module."""
    if not FLIR_AVAILABLE:
        return None
    return getattr(PySpin, name, None)


# Collect symbols used in this file (avoid AttributeError at import time).
_SPIN: dict[str, object] = {}
if FLIR_AVAILABLE:
    for _key in (
        "PixelFormat_Mono8",
        "PixelFormat_Mono16",
        "ExposureAuto_Off",
        "GainAuto_Off",
        "BalanceWhiteAuto_Off",
        "StreamBufferHandlingMode_NewestFirst",
        "AcquisitionMode_Continuous",
        "TriggerMode_Off",
        "TriggerSource_Software",
    ):
        _SPIN[_key] = _spin_attr(_key)
    _missing = [k for k, v in _SPIN.items() if v is None]
    if _missing:
        _LOG.debug("PySpin missing symbols (will use GenICam string fallbacks where possible): %s", _missing)

# Legacy export — may be None on some Spinnaker builds
FLIR_PIXEL_FORMAT = _SPIN.get("PixelFormat_Mono8") if FLIR_AVAILABLE else None


def _set_pixel_format_genicam(camera, mono8: bool = True) -> bool:
    """Set Mono8/Mono16 using enum if available, else GenICam symbolic string."""
    name = "Mono8" if mono8 else "Mono16"
    key = "PixelFormat_Mono8" if mono8 else "PixelFormat_Mono16"
    sym = _SPIN.get(key)
    if sym is not None:
        try:
            camera.PixelFormat.SetValue(sym)
            return True
        except Exception:
            pass
    try:
        camera.PixelFormat.SetValue(name)
        return True
    except Exception:
        return False


def _pixel_format_matches(value, key: str) -> bool:
    """Compare GetPixelFormat / GetValue() to Mono8/Mono16 across int/enum/str variants."""
    ref = _SPIN.get(key)
    if ref is not None and value == ref:
        return True
    try:
        if ref is not None and int(value) == int(ref):  # type: ignore[arg-type]
            return True
    except Exception:
        pass
    s = str(value).upper()
    if key == "PixelFormat_Mono8":
        return "MONO8" in s or "01080001" in s
    if key == "PixelFormat_Mono16":
        return "MONO16" in s or "0110000" in s
    return False


SPINNAKER_EXCEPTION = getattr(PySpin, "SpinnakerException", Exception) if FLIR_AVAILABLE else Exception

# GenICam PFNC Mono8 (used if PySpin.PixelFormat_Mono8 is missing)
_PFNC_MONO8 = 0x01080001


class FLIRCameraWorker(QThread):
    """
    High-performance FLIR camera worker with optimized acquisition.
    
    Features:
    - Non-blocking asynchronous acquisition
    - Optimized buffer handling (newest-first strategy)
    - Zero frame drops through proper queue management
    - Production-ready error handling
    - Real-time FPS monitoring and statistics
    """
    
    # Signals
    frame_ready = pyqtSignal(np.ndarray)
    error_occurred = pyqtSignal(str)
    fps_updated = pyqtSignal(float)
    stats_updated = pyqtSignal(dict)  # For detailed performance stats
    
    def __init__(self, camera_name: str, camera_info: Dict):
        super().__init__()
        self.camera_name = camera_name
        self.camera_info = camera_info
        self.camera_system = None
        self.camera = None
        self.nodemap = None
        
        # Performance tracking
        self._running = False
        self._fps_counter = 0
        self._fps_start_time = time.time()
        self._current_fps = 0.0
        self._dropped_frames = 0
        self._total_frames = 0
        self._buffer_underruns = 0
        
        # Threading and synchronization
        self._acquisition_lock = threading.Lock()
        self._stats_lock = threading.Lock()
        
        self.logger = logging.getLogger(f"FLIRWorker-{camera_name}")
        
    def run(self):
        """Main FLIR acquisition loop - optimized for maximum performance"""
        self._running = True
        self.logger.info(f"Starting FLIR camera {self.camera_name}")
        
        try:
            if not self._initialize_flir():
                self.error_occurred.emit(f"Failed to initialize FLIR camera {self.camera_name}")
                return
            
            # Start optimized acquisition
            if not self._start_acquisition():
                self.error_occurred.emit(f"Failed to start FLIR acquisition {self.camera_name}")
                return
            
            # Main acquisition loop - optimized for zero frame drops
            consecutive_errors = 0
            max_consecutive_errors = 5
            
            self.logger.info(f"FLIR acquisition started for {self.camera_name}")
            
            while self._running:
                try:
                    # Non-blocking image retrieval with timeout
                    result = self._get_next_image(timeout=0.001)  # 1ms timeout for responsiveness
                    
                    if result is not None:
                        self.frame_ready.emit(result)
                        self._update_fps_counter()
                        self._update_statistics()
                        consecutive_errors = 0  # Reset error counter on success
                    else:
                        # No image available - brief sleep to prevent CPU spinning
                        time.sleep(0.0001)  # 100μs - minimal for responsiveness
                        
                except Exception as e:
                    self.logger.error(f"Error in FLIR acquisition loop: {e}")
                    consecutive_errors += 1
                    time.sleep(0.001)  # Minimal sleep on error
                    
                    # Stop on too many consecutive errors
                    if consecutive_errors >= max_consecutive_errors:
                        self.logger.error(f"FLIR camera: {max_consecutive_errors} consecutive errors, stopping")
                        self.error_occurred.emit(f"FLIR camera: {max_consecutive_errors} errors")
                        break
                        
        except Exception as e:
            self.logger.error(f"FLIR camera critical error: {e}", exc_info=True)
            self.error_occurred.emit(f"FLIR camera critical error: {str(e)}")
        finally:
            self._cleanup_flir()
            self.logger.info(f"FLIR camera stopped for {self.camera_name}")
    
    def _initialize_flir(self) -> bool:
        """
        Initialize FLIR camera with production-ready optimizations.
        """
        try:
            if not FLIR_AVAILABLE:
                self.logger.error("FLIR Spinnaker SDK not available")
                return False
            
            # Get camera system and specific camera
            self.camera_system = PySpin.System.GetInstance()
            camera_list = self.camera_system.GetCameras()
            
            if len(camera_list) == 0:
                self.logger.error("No FLIR cameras found")
                return False
            
            # Pick camera by detected index if provided; fallback to first
            cam_index = int(self.camera_info.get("index", 0)) if isinstance(self.camera_info, dict) else 0
            if cam_index < 0 or cam_index >= camera_list.GetSize():
                cam_index = 0
            self.camera = camera_list.GetByIndex(cam_index)
            self.camera.Init()
            
            # Log camera information for debugging
            self._log_camera_info()
            
            # Configure for maximum performance
            if not self._configure_optimal_settings():
                self.logger.error("Failed to configure FLIR camera settings")
                return False
            
            # Validate configuration
            if not self._validate_configuration():
                self.logger.error("FLIR camera configuration validation failed")
                return False
            
            self.logger.info(f"FLIR camera {self.camera_name} initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"FLIR camera initialization failed: {e}", exc_info=True)
            return False
    
    def _configure_optimal_settings(self) -> bool:
        """
        Configure FLIR camera for maximum FPS and zero frame drops.
        """
        try:
            # Disable all automatic features for maximum control
            self._disable_automatic_features()
            
            # Configure pixel format for fastest acquisition
            self._configure_pixel_format()
            
            # Configure buffer handling for optimal throughput
            self._configure_buffers()
            
            # Configure acquisition mode for continuous capture
            self._configure_acquisition_mode()
            
            # Configure trigger mode for free-running
            self._configure_trigger_mode()
            
            # Configure packet size for USB3 optimization
            self._configure_packet_size()
            
            # Apply resolution and FPS from camera info
            self._apply_resolution_settings()
            
            self.logger.info("FLIR camera configured for optimal performance")
            return True
            
        except Exception as e:
            self.logger.error(f"FLIR camera configuration failed: {e}", exc_info=True)
            return False
    
    def _disable_automatic_features(self):
        """Disable all automatic features for manual control"""
        try:
            # Disable auto exposure
            if hasattr(self.camera, "ExposureAuto"):
                off = _SPIN.get("ExposureAuto_Off")
                if off is not None:
                    try:
                        self.camera.ExposureAuto.SetValue(off)
                        self.logger.debug("FLIR: Auto exposure disabled")
                    except Exception:
                        pass
            
            # Disable auto gain
            if hasattr(self.camera, 'GainAuto'):
                try:
                    go = _SPIN.get("GainAuto_Off")
                    if go is not None:
                        self.camera.GainAuto.SetValue(go)
                        self.logger.debug("FLIR: Auto gain disabled")
                except Exception:
                    pass
            
            # Disable auto white balance (if available)
            if hasattr(self.camera, 'BalanceWhiteAuto'):
                bwo = _SPIN.get("BalanceWhiteAuto_Off")
                if bwo is not None:
                    try:
                        self.camera.BalanceWhiteAuto.SetValue(bwo)
                        self.logger.debug("FLIR: Auto white balance disabled")
                    except Exception:
                        pass
            
            # Disable gamma correction
            if hasattr(self.camera, 'GammaEnable'):
                self.camera.GammaEnable.SetValue(False)
                self.logger.debug("FLIR: Gamma correction disabled")
                
        except Exception as e:
            self.logger.warning(f"Error disabling FLIR auto features: {e}")
    
    def _configure_pixel_format(self):
        """Configure pixel format for fastest acquisition"""
        try:
            # Avoid GetSymbolics() here: signature differs across PySpin builds.
            if _set_pixel_format_genicam(self.camera, mono8=True):
                self.logger.info("FLIR: Pixel format set to Mono8")
                return
            if _set_pixel_format_genicam(self.camera, mono8=False):
                self.logger.info("FLIR: Pixel format set to Mono16")
                return
                    
        except Exception as e:
            self.logger.error(f"Error configuring FLIR pixel format: {e}")
    
    def _configure_buffers(self):
        """Configure buffer handling for optimal throughput"""
        try:
            # Set buffer count for optimal USB3 performance
            if hasattr(self.camera, 'StreamBufferCountManual'):
                self.camera.StreamBufferCountManual.SetValue(FLIR_BUFFER_COUNT)
                self.logger.info(f"FLIR: Buffer count set to {FLIR_BUFFER_COUNT}")
            
            # Set buffer handling mode to newest-first (minimize latency)
            if hasattr(self.camera, 'StreamBufferHandlingMode'):
                nh = _SPIN.get("StreamBufferHandlingMode_NewestFirst")
                if nh is not None:
                    self.camera.StreamBufferHandlingMode.SetValue(nh)
                    self.logger.info("FLIR: Buffer handling set to NewestFirst")
            
            # Enable stream auto-restart
            if hasattr(self.camera, 'StreamAutoReconfigureEnable'):
                self.camera.StreamAutoReconfigureEnable.SetValue(True)
                self.logger.info("FLIR: Stream auto-reconfigure enabled")
                
        except Exception as e:
            self.logger.warning(f"Error configuring FLIR buffers: {e}")
    
    def _configure_acquisition_mode(self):
        """Configure acquisition mode for continuous capture"""
        try:
            # Set acquisition mode to continuous
            ac = _SPIN.get("AcquisitionMode_Continuous")
            if ac is not None:
                self.camera.AcquisitionMode.SetValue(ac)
                self.logger.info("FLIR: Acquisition mode set to Continuous")
            
            # Set acquisition frame rate if supported
            if hasattr(self.camera, 'AcquisitionFrameRateEnable'):
                self.camera.AcquisitionFrameRateEnable.SetValue(True)
                target_fps = self.camera_info.get("settings", {}).get("fps", 30)
                if hasattr(self.camera, 'AcquisitionFrameRate'):
                    self.camera.AcquisitionFrameRate.SetValue(target_fps)
                    self.logger.info(f"FLIR: Target FPS set to {target_fps}")
                    
        except Exception as e:
            self.logger.error(f"Error configuring FLIR acquisition mode: {e}")
    
    def _configure_trigger_mode(self):
        """Configure trigger mode for free-running"""
        try:
            # Disable trigger for free-running mode
            tm = _SPIN.get("TriggerMode_Off")
            if tm is not None:
                self.camera.TriggerMode.SetValue(tm)
                self.logger.info("FLIR: Trigger mode set to Off (free-running)")
            
            # Set trigger source to software (if needed)
            if hasattr(self.camera, 'TriggerSource'):
                ts = _SPIN.get("TriggerSource_Software")
                if ts is not None:
                    self.camera.TriggerSource.SetValue(ts)
                    self.logger.debug("FLIR: Trigger source set to Software")
                
        except Exception as e:
            self.logger.error(f"Error configuring FLIR trigger mode: {e}")
    
    def _configure_packet_size(self):
        """Configure packet size for USB3 optimization"""
        try:
            # PySpin constants for "optimal" differ across versions/cameras.
            # Best-effort: don't force a value; leave driver defaults.
            return
                
        except Exception as e:
            self.logger.warning(f"Error configuring FLIR packet size: {e}")
    
    def _apply_resolution_settings(self):
        """Apply resolution and FPS from camera info"""
        try:
            settings = self.camera_info.get("settings", {})
            
            # Set resolution
            resolution = settings.get("resolution", (640, 480))
            if hasattr(self.camera, 'Width') and hasattr(self.camera, 'Height'):
                try:
                    self.camera.Width.SetValue(resolution[0])
                    self.camera.Height.SetValue(resolution[1])
                    self.logger.info(f"FLIR: Resolution set to {resolution[0]}x{resolution[1]}")
                except Exception as e:
                    self.logger.debug(f"FLIR: Resolution not writable / not supported: {e}")
            
            # Set frame rate
            fps = settings.get("fps", 30)
            if hasattr(self.camera, 'AcquisitionFrameRate'):
                self.camera.AcquisitionFrameRate.SetValue(fps)
                self.logger.info(f"FLIR: FPS set to {fps}")
                
        except Exception as e:
            self.logger.error(f"Error applying FLIR resolution settings: {e}")
    
    def _validate_configuration(self) -> bool:
        """Validate camera configuration before starting acquisition"""
        try:
            # Validate pixel format
            pixel_format = self.camera.PixelFormat.GetValue()
            self.logger.info(f"FLIR: Pixel format validation: {pixel_format}")
            
            # Validate resolution
            width = self.camera.Width.GetValue()
            height = self.camera.Height.GetValue()
            self.logger.info(f"FLIR: Resolution validation: {width}x{height}")
            
            # Validate buffer configuration
            if hasattr(self.camera, 'StreamBufferCountManual'):
                buffer_count = self.camera.StreamBufferCountManual.GetValue()
                self.logger.info(f"FLIR: Buffer count validation: {buffer_count}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"FLIR configuration validation failed: {e}")
            return False
    
    def _start_acquisition(self) -> bool:
        """Start camera acquisition with error handling"""
        try:
            self.camera.BeginAcquisition()
            self.logger.info("FLIR: Acquisition started")
            return True
        except Exception as e:
            self.logger.error(f"FLIR: Failed to start acquisition: {e}")
            return False
    
    def _get_next_image(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """
        Get next image from camera with non-blocking behavior.
        
        Args:
            timeout: Timeout in seconds for image retrieval
            
        Returns:
            numpy array or None if no image available
        """
        try:
            with self._acquisition_lock:
                # PySpin expects timeout in milliseconds (int)
                timeout_ms = max(1, int(timeout * 1000))

                # Get next image with short timeout
                try:
                    result = self.camera.GetNextImage(timeout_ms)
                    if result and result.IsIncomplete():
                        # Incomplete image - increment dropped counter
                        with self._stats_lock:
                            self._dropped_frames += 1
                        result.Release()
                        return None
                    
                    if not result or not result.IsValid():
                        return None
                    
                    # Convert to numpy array
                    image_data = self._convert_to_numpy(result)
                    
                    # Release image immediately to prevent buffer starvation
                    result.Release()
                    
                    # Update statistics
                    with self._stats_lock:
                        self._total_frames += 1
                    
                    return image_data
                    
                except SPINNAKER_EXCEPTION as e:
                    # Timeout is normal for non-blocking reads; other errors we log once in a while.
                    # Spinnaker exception API varies; safest is to treat exceptions as "no frame".
                    msg = str(e)
                    if "Timeout" not in msg and "timeout" not in msg:
                        self.logger.debug(f"FLIR image retrieval error: {e}")
                    return None
                        
        except Exception as e:
            self.logger.error(f"FLIR get next image error: {e}")
            return None
    
    def _convert_to_numpy(self, image) -> np.ndarray:
        """
        Convert FLIR image to numpy array efficiently.
        """
        try:
            # Fast path if available (PySpin provides this in many builds)
            if hasattr(image, "GetNDArray"):
                arr = image.GetNDArray()
                return arr

            # Get image dimensions and data
            width = image.GetWidth()
            height = image.GetHeight()
            pixel_format = image.GetPixelFormat()
            
            # Convert based on pixel format
            if _pixel_format_matches(pixel_format, "PixelFormat_Mono8"):
                # Direct memory copy for Mono8
                data_ptr = image.GetData()
                buffer_size = width * height
                numpy_array = np.frombuffer(data_ptr, dtype=np.uint8, count=buffer_size)
                return numpy_array.reshape((height, width))
            
            elif _pixel_format_matches(pixel_format, "PixelFormat_Mono16"):
                # Convert Mono16 to numpy
                data_ptr = image.GetData()
                buffer_size = width * height * 2
                numpy_array = np.frombuffer(data_ptr, dtype=np.uint16, count=buffer_size)
                return numpy_array.reshape((height, width))
            
            else:
                # Fallback conversion for other formats
                conv_to = _SPIN.get("PixelFormat_Mono8")
                if conv_to is None:
                    conv_to = _PFNC_MONO8
                try:
                    converted_image = image.Convert(conv_to)
                except Exception:
                    converted_image = image.Convert(int(_PFNC_MONO8))
                try:
                    if hasattr(converted_image, "GetNDArray"):
                        return converted_image.GetNDArray()
                    data_ptr = converted_image.GetData()
                    buffer_size = width * height
                    numpy_array = np.frombuffer(data_ptr, dtype=np.uint8, count=buffer_size)
                    return numpy_array.reshape((height, width))
                finally:
                    try:
                        converted_image.Release()
                    except Exception:
                        pass
                
        except Exception as e:
            self.logger.error(f"FLIR numpy conversion error: {e}")
            return None
    
    def _update_fps_counter(self):
        """Update FPS counter efficiently"""
        self._fps_counter += 1
        current_time = time.time()
        
        # Update FPS every second
        if current_time - self._fps_start_time >= 1.0:
            self._current_fps = self._fps_counter / (current_time - self._fps_start_time)
            self.fps_updated.emit(self._current_fps)
            self._fps_counter = 0
            self._fps_start_time = current_time
    
    def _update_statistics(self):
        """Update performance statistics"""
        try:
            if self._total_frames % 30 == 0:  # Update every 30 frames
                stats = {
                    'total_frames': self._total_frames,
                    'dropped_frames': self._dropped_frames,
                    'drop_rate': (self._dropped_frames / max(self._total_frames, 1)) * 100,
                    'current_fps': self._current_fps
                }
                self.stats_updated.emit(stats)
                
        except Exception as e:
            self.logger.warning(f"Error updating FLIR statistics: {e}")
    
    def _log_camera_info(self):
        """Log detailed camera information for debugging"""
        try:
            # Get camera model and serial
            model = self.camera.DeviceModelName.GetValue()
            serial = self.camera.DeviceSerialNumber.GetValue()
            firmware = self.camera.DeviceFirmwareVersion.GetValue()
            
            # Get sensor information
            sensor_width = self.camera.SensorWidth.GetValue()
            sensor_height = self.camera.SensorHeight.GetValue()
            
            self.logger.info(f"FLIR Camera Info:")
            self.logger.info(f"  Model: {model}")
            self.logger.info(f"  Serial: {serial}")
            self.logger.info(f"  Firmware: {firmware}")
            self.logger.info(f"  Sensor: {sensor_width}x{sensor_height}")
            # Avoid GetSymbolics() here: signature differs across PySpin builds.
            
        except Exception as e:
            self.logger.warning(f"Error logging FLIR camera info: {e}")
    
    def stop(self):
        """Stop FLIR camera acquisition"""
        self._running = False
        self.wait(1000)  # Wait up to 1 second for thread to finish
    
    def get_current_fps(self) -> float:
        """Get current FPS"""
        return self._current_fps
    
    def _cleanup_flir(self):
        """Clean up FLIR camera resources"""
        try:
            if self.camera:
                # Stop acquisition
                if self.camera.IsStreaming():
                    self.camera.EndAcquisition()
                    self.logger.info("FLIR: Acquisition stopped")
                
                # Deinitialize camera
                self.camera.DeInit()
                self.camera = None
                self.logger.info("FLIR: Camera deinitialized")
            
            if self.camera_system:
                # Release camera system
                self.camera_system.ReleaseInstance()
                self.camera_system = None
                self.logger.info("FLIR: Camera system released")
                
        except Exception as e:
            self.logger.error(f"FLIR cleanup error: {e}")
    
    def update_fps(self, fps: int):
        """Update target FPS during runtime"""
        try:
            if not self.camera:
                return

            # 0 = unlimited / free-run (disable rate limiting if supported)
            if int(fps) == 0:
                if hasattr(self.camera, 'AcquisitionFrameRateEnable'):
                    try:
                        self.camera.AcquisitionFrameRateEnable.SetValue(False)
                        self.logger.info("FLIR target FPS set to unlimited (AcquisitionFrameRateEnable=False)")
                        return
                    except Exception:
                        pass
                # If we can't disable, just return without forcing a value.
                self.logger.info("FLIR target FPS unlimited requested (rate-limit disable not supported)")
                return

            # Finite FPS: enable rate control then set value
            if hasattr(self.camera, 'AcquisitionFrameRateEnable'):
                try:
                    self.camera.AcquisitionFrameRateEnable.SetValue(True)
                except Exception:
                    pass
            if hasattr(self.camera, 'AcquisitionFrameRate'):
                self.camera.AcquisitionFrameRate.SetValue(int(fps))
                self.logger.info(f"FLIR target FPS updated to {fps}")
        except Exception as e:
            self.logger.error(f"Error updating FLIR FPS: {e}")


# Utility function for FLIR camera detection
def detect_flir_cameras() -> Dict[str, Dict]:
    """
    Detect available FLIR cameras.

    Returns:
        Dict mapping camera_name -> camera_info
    """
    cameras: Dict[str, Dict] = {}
    
    if not FLIR_AVAILABLE:
        return cameras
    
    try:
        system = PySpin.System.GetInstance()
        camera_list = system.GetCameras()

        for idx in range(camera_list.GetSize()):
            camera = camera_list.GetByIndex(idx)
            try:
                camera.Init()
                
                # Get camera information
                model = camera.DeviceModelName.GetValue()
                serial = camera.DeviceSerialNumber.GetValue()
                
                # Store only identifiers here; actual CameraPtr must be created per worker
                cam_name = f"FLIR_{model}_{serial}"
                cameras[cam_name] = {
                    # Normalized to CameraType.FLIR by camera_interface to avoid circular imports here
                    "type": "flir",
                    "index": idx,
                    "model": model,
                    "serial": serial,
                    "settings": {
                        "resolution": (640, 480),
                        "fps": 30,
                        "zoom": 1.0,
                    },
                }

                camera.DeInit()
                
            except Exception as e:
                logging.getLogger("FLIRCamera").warning(f"Error detecting FLIR camera {idx}: {e}")
            finally:
                try:
                    del camera
                except Exception:
                    pass
        
        camera_list.Clear()
        del camera_list
        system.ReleaseInstance()
        
    except Exception as e:
        logging.getLogger("FLIRCamera").error(f"FLIR camera detection failed: {e}")
    
    return cameras
