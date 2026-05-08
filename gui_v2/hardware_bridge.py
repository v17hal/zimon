"""
Integrated hardware bridge: CameraManager (FLIR/Basler/webcam), Arduino serial,
OpenCV recording thread, mode profiles.
Camera acquisition stays on QThread workers; UI receives frames via Qt signals.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import serial.tools.list_ports

from backend.arduino_controller import ArduinoController
from backend.camera_manager import CameraManager
from backend.mode_profiles import ModeProfile, profile_for_mode
from backend.recording_manager import RecordingManager
from gui_v2.tracking_overlay import draw_tracking_overlay

LOG = logging.getLogger("HardwareBridge")


@dataclass
class CameraSnapshot:
    exposure_us: float = 0.0
    gain_db: float = 0.0
    fps: float = 60.0
    width: int = 1440
    height: int = 1080
    pixel_format: str = "Mono8"


class HardwareBridge:
    """Central integration point — UI calls only this class for device I/O."""

    def __init__(self) -> None:
        self.camera_manager = CameraManager(overlay_hook=draw_tracking_overlay)
        self._recording = RecordingManager(self.camera_manager)
        self._arduino = ArduinoController(port=None)
        self._mode_profile: ModeProfile = profile_for_mode("adult")
        self._saved_settings: dict[str, Any] = {}
        self._ir_percent = 0.0
        self._white_percent = 0.0
        self._recording_error_handler: Optional[Callable[[str], None]] = None
        self._recording_stopped_handler: Optional[Callable[[str], None]] = None
        self._recording_started_handler: Optional[Callable[[], None]] = None

    # --- Mode (Adult / Larval) ---
    def set_mode_adult(self) -> None:
        self._apply_mode("adult")

    def set_mode_larval(self) -> None:
        self._apply_mode("larval")

    def _apply_mode(self, mode: str) -> None:
        self._mode_profile = profile_for_mode(mode)
        LOG.info("Mode profile: %s (fps hint %s)", self._mode_profile.label, self._mode_profile.default_fps)

    def current_mode_profile(self) -> ModeProfile:
        return self._mode_profile

    # --- Camera ---
    def start_camera_preview(self, camera_id: str) -> bool:
        if not camera_id or camera_id.startswith("—"):
            return False
        # Only refresh if no cameras are known yet; refresh_cameras() stops active streams.
        names = self.camera_manager.list_cameras()
        if not names:
            self.camera_manager.refresh_cameras()
            names = self.camera_manager.list_cameras()
        if camera_id == "default" and names:
            camera_id = names[0]
        if camera_id not in names and names:
            LOG.warning("Camera %r not found, using first available", camera_id)
            camera_id = names[0]
        if not names:
            LOG.warning("No cameras detected")
            return False
        if not self.camera_manager.connect_camera(camera_id):
            return False
        ok = self.camera_manager.start_stream(camera_id)
        if not ok:
            LOG.error("Failed to start stream for %s", camera_id)
        return ok

    def start_first_camera_preview(self) -> bool:
        """Dashboard quick action: first detected camera."""
        self.camera_manager.refresh_cameras()
        names = self.camera_manager.list_cameras()
        if not names:
            return False
        return self.start_camera_preview(names[0])

    def stop_camera_preview(self) -> bool:
        self.camera_manager.stop_stream()
        return True

    def list_cameras(self) -> list[str]:
        # Refresh only if no cameras known yet; avoids stopping active streams.
        names = self.camera_manager.list_cameras()
        if not names:
            self.camera_manager.refresh_cameras()
            names = self.camera_manager.list_cameras()
        return names

    def get_current_fps(self) -> float:
        return float(self.camera_manager.get_current_fps())

    def apply_camera_settings(self, snapshot: CameraSnapshot) -> bool:
        """Apply resolution/FPS to active camera (stops stream when required)."""
        name = self.camera_manager.current_camera_name()
        if not name:
            LOG.warning("apply_camera_settings: no active camera")
            return False
        was = self.camera_manager.is_streaming()
        self.camera_manager.stop_stream()
        ok = True
        ok = self.camera_manager.set_setting("resolution", (snapshot.width, snapshot.height)) and ok
        ok = self.camera_manager.set_setting("fps", int(snapshot.fps)) and ok
        if snapshot.pixel_format or snapshot.exposure_us or snapshot.gain_db:
            LOG.info(
                "Exposure/gain/pixel format staging not applied via CameraController (%s, %s, %s)",
                snapshot.exposure_us,
                snapshot.gain_db,
                snapshot.pixel_format,
            )
        if was:
            ok = self.camera_manager.start_stream(name) and ok
        return ok

    # --- Environment (DAC via Arduino / I2C on device) ---
    def get_lighting_state(self) -> tuple[float, float]:
        return self._ir_percent, self._white_percent

    def apply_environment_lighting(self, ir_percent: float, white_percent: float) -> bool:
        self._ir_percent = ir_percent
        self._white_percent = white_percent
        if not self._arduino.is_connected():
            LOG.warning("Arduino not connected — lighting values not sent")
            return False
        a = self._arduino.set_ir_intensity(ir_percent)
        b = self._arduino.set_white_intensity(white_percent)
        return a and b

    # --- Stimulus ---
    def apply_stimulus_vibration(self, on: bool, duration_ms: int) -> bool:
        if not self._arduino.is_connected():
            return False
        if on and duration_ms > 0:
            return self._arduino.vibrate_timed(duration_ms)
        return self._arduino.vibrate_on() if on else self._arduino.vibrate_off()

    def apply_stimulus_rgb(self, r: int, g: int, b: int, intensity: float) -> bool:
        if not self._arduino.is_connected():
            return False
        # Scale RGB by intensity 0..1 (firmware may also use global PWM)
        k = max(0.0, min(1.0, float(intensity)))
        r2 = int(r * k)
        g2 = int(g * k)
        b2 = int(b * k)
        return self._arduino.rgb_set(r2, g2, b2)

    def apply_stimulus_timing(self, delay_ms: int, duration_ms: int) -> bool:
        if not self._arduino.is_connected():
            return False
        return self._arduino.timed_stimulus(delay_ms, duration_ms)

    # --- Recording ---
    def set_recording_error_handler(self, fn: Optional[Callable[[str], None]]) -> None:
        self._recording_error_handler = fn

    def set_recording_stopped_handler(self, fn: Optional[Callable[[str], None]]) -> None:
        """Called when file is finalized (manual stop or duration reached)."""
        self._recording_stopped_handler = fn

    def set_recording_started_handler(self, fn: Optional[Callable[[], None]]) -> None:
        """Called after recording thread starts successfully."""
        self._recording_started_handler = fn

    def start_recording(self, path: str, basename: str, duration_s: Optional[float]) -> bool:
        if self._recording.is_recording:
            return False
        os.makedirs(path, exist_ok=True)
        fname = f"{basename}_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
        out = os.path.join(path, fname)
        fps = self.get_current_fps()
        if fps < 1.0:
            fps = self._mode_profile.default_fps
        ok = self._recording.start(
            out,
            fps_hint=fps,
            duration_s=duration_s,
            on_error=self._on_recording_error,
            on_stopped=self._on_recording_stopped_path,
        )
        if ok and self._recording_started_handler:
            self._recording_started_handler()
        return ok

    def _on_recording_stopped_path(self, path: str) -> None:
        if self._recording_stopped_handler:
            self._recording_stopped_handler(path)

    def _on_recording_error(self, msg: str) -> None:
        LOG.error("Recording: %s", msg)
        if self._recording_error_handler:
            self._recording_error_handler(msg)

    def stop_recording(self) -> bool:
        self._recording.stop()
        return True

    def is_recording(self) -> bool:
        return self._recording.is_recording

    # --- Settings ---
    def list_serial_ports(self) -> list[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    def save_settings(self, settings: dict[str, Any]) -> bool:
        self._saved_settings = dict(settings)
        com = settings.get("com") or settings.get("serial_port")
        if com and str(com).strip() and not str(com).startswith("—"):
            ok = self._arduino.connect(str(com).strip())
            if not ok:
                LOG.error("Could not open Arduino on %s", com)
                return False
        return True

