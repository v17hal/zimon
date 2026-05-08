# backend/experiment_runner.py
"""
ExperimentRunner

This class runs experiments described by a config dictionary (cfg).
It is designed to be used by the GUI. It runs in a background thread,
schedules stimuli (IR, WHITE, VIB, PUMP, RGB, BUZZER) and interfaces
with an Arduino controller and a camera_controller (if present).

This version accepts either:
  - app (object with .arduino attribute), or
  - arduino_controller (direct controller instance),
and camera_controller as a separate argument.

Save this file as backend/experiment_runner.py (overwrite existing).
"""
import threading
import time
import json
from typing import Dict, Any, Optional, Callable, List


class ExperimentRunner:
    def __init__(self, app: Optional[object] = None, camera_controller: Optional[object] = None,
                 storage_manager: Optional[object] = None, logger: Optional[Callable] = None,
                 arduino_controller: Optional[object] = None):
        """
        Create a runner.

        - app: main application object (optional). If provided, runner will prefer app.arduino.
        - camera_controller: optional controller exposing start_recording(camera_list, prefix) and stop_recording()
        - storage_manager: optional (not used heavily here)
        - logger: optional callable for logs (e.g., app.append_log)
        - arduino_controller: optional direct Arduino controller (fallback if app.arduino missing)
        """
        self.app = app
        self.camera_controller = camera_controller
        self.storage_manager = storage_manager
        self.arduino_controller = arduino_controller
        # prefer explicit logger, then app.append_log, then print
        if logger:
            self._log = logger
        else:
            self._log = (getattr(app, "append_log", print) if app else print)

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running_lock = threading.Lock()
        self._is_running = False
        self._active_timers: List[threading.Timer] = []

        self.log("ExperimentRunner initialized (arduino_controller provided={})".format(bool(self.arduino_controller)))

    def log(self, *args):
        try:
            self._log(" ".join(map(str, args)))
        except Exception:
            print(*args)

    # -------------------------
    # Public API
    # -------------------------
    def start(self, cfg: Dict[str, Any]):
        """Start an experiment with the given configuration.
        If a run is already active, logs and returns False."""
        with self._running_lock:
            if self._is_running:
                self.log("ExperimentRunner: already running")
                return False
            self._is_running = True
            self._stop_event.clear()

        self.log("ExperimentRunner: starting with cfg:", json.dumps(cfg))
        self._thread = threading.Thread(target=self._run_thread, args=(cfg,), daemon=True)
        self._thread.start()
        return True

    def stop(self):
        """Request a stop. Cancels timers, turns off actuators, stops camera recording."""
        self.log("ExperimentRunner: stop requested")
        self._stop_event.set()

        # cancel timers
        for t in list(self._active_timers):
            try:
                t.cancel()
            except Exception:
                pass
        self._active_timers.clear()

        # attempt to turn off all outputs
        try:
            self._cmd_off_all()
        except Exception as e:
            self.log("ExperimentRunner: error turning off stimuli:", e)

        # stop camera
        try:
            if self.camera_controller and hasattr(self.camera_controller, "stop_recording"):
                self.camera_controller.stop_recording()
        except Exception as e:
            self.log("ExperimentRunner: error stopping camera recording:", e)

        # join thread briefly
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        with self._running_lock:
            self._is_running = False

        self.log("ExperimentRunner: stopped")
        return True

    # -------------------------
    # Internal worker
    # -------------------------
    def _run_thread(self, cfg: Dict[str, Any]):
        try:
            start_time = time.time()
            duration_s = int(cfg.get("duration_s", 0) or 0)
            if duration_s <= 0:
                self.log("ExperimentRunner: warning - duration_s <= 0")

            # Start camera recording if available
            cameras = cfg.get("camera_list", []) or []
            prefix = cfg.get("filename_prefix", "exp")
            try:
                if self.camera_controller and hasattr(self.camera_controller, "start_recording"):
                    self.log("ExperimentRunner: starting recording for cameras:", cameras, "prefix:", prefix)
                    self.camera_controller.start_recording(cameras, prefix)
                else:
                    self.log("ExperimentRunner: no camera_controller.start_recording available")
            except Exception as e:
                self.log("ExperimentRunner: camera start_recording error:", e)

            # Schedule stimuli
            stimuli = cfg.get("stimuli", {}) or {}
            self._schedule_stimuli(stimuli, base_time=start_time)

            # Wait until duration or stop
            if duration_s > 0:
                end_time = start_time + duration_s
                while not self._stop_event.is_set() and time.time() < end_time:
                    time.sleep(0.1)
            else:
                while not self._stop_event.is_set():
                    time.sleep(0.2)

            # cleanup
            self.log("ExperimentRunner: experiment finished/stop; cleaning up")
            self._cmd_off_all()
            try:
                if self.camera_controller and hasattr(self.camera_controller, "stop_recording"):
                    self.camera_controller.stop_recording()
            except Exception as e:
                self.log("ExperimentRunner: camera stop_recording error:", e)

        except Exception as e:
            self.log("ExperimentRunner: unexpected error in _run_thread:", e)
        finally:
            for t in list(self._active_timers):
                try:
                    t.cancel()
                except Exception:
                    pass
            self._active_timers.clear()
            with self._running_lock:
                self._is_running = False

    # -------------------------
    # Scheduling
    # -------------------------
    def _schedule_stimuli(self, stimuli: Dict[str, Any], base_time: float):
        for name, params in stimuli.items():
            if params is None:
                continue
            name_u = name.upper()
            delay_ms = int(params.get("delay_ms", params.get("delay", 0) or 0))
            duration_ms = int(params.get("duration_ms", params.get("duration", 0) or 0))
            level = params.get("level", params.get("lvl", None))

            if name_u == "IR":
                level = int(params.get("level", 255))
                self._schedule_cmd_at(delay_ms, lambda lv=level: self._cmd_ir_set(lv))
                if duration_ms > 0:
                    self._schedule_cmd_at(delay_ms + duration_ms, lambda: self._cmd_ir_set(0))
                self.log("Scheduled IR:", delay_ms, "ms ->", duration_ms, "ms at level", level)

            elif name_u == "WHITE":
                level = int(params.get("level", 255))
                self._schedule_cmd_at(delay_ms, lambda lv=level: self._cmd_white_set(lv))
                if duration_ms > 0:
                    self._schedule_cmd_at(delay_ms + duration_ms, lambda: self._cmd_white_set(0))
                self.log("Scheduled WHITE:", delay_ms, "ms ->", duration_ms, "ms at level", level)

            elif name_u == "VIB":
                level = int(params.get("level", 200))
                continuous = params.get("continuous", False)
                delay_ms = int(params.get("delay_ms", 0))
                duration_ms = int(params.get("duration_ms", 0))
                
                if continuous:
                    # Continuous mode: turn on immediately and keep on
                    self._schedule_cmd_at(0, lambda lv=level: self._cmd_vib_set(lv))
                    self.log("Scheduled VIB: Continuous at level", level)
                elif duration_ms > 0:
                    # Pulsed mode: duration -> delay -> duration -> delay...
                    self._schedule_repeating_stimulus(
                        "VIB", level, delay_ms, duration_ms, base_time
                    )
                    self.log("Scheduled VIB: Repeating pattern, duration", duration_ms, "ms, delay", delay_ms, "ms at level", level)
                else:
                    # Single pulse
                    self._schedule_cmd_at(delay_ms, lambda lv=level: self._cmd_vib_set(lv))
                    self.log("Scheduled VIB: Single pulse at", delay_ms, "ms, level", level)

            elif name_u == "PUMP":
                if level is not None:
                    self._schedule_cmd_at(delay_ms, lambda lv=level: self._cmd_pump_set(lv))
                    if duration_ms > 0:
                        self._schedule_cmd_at(delay_ms + duration_ms, lambda: self._cmd_pump_set(0))
                    self.log("Scheduled PUMP:", delay_ms, "ms ->", duration_ms, "ms at level", level)

            elif name_u == "RGB":
                r = int(params.get("r", 0))
                g = int(params.get("g", 0))
                b = int(params.get("b", 0))
                self._schedule_cmd_at(delay_ms, lambda rr=r, gg=g, bb=b: self._cmd_rgb_set(rr, gg, bb))
                if duration_ms > 0:
                    self._schedule_cmd_at(delay_ms + duration_ms, lambda: self._cmd_rgb_set(0, 0, 0))
                self.log("Scheduled RGB:", r, g, b, "delay", delay_ms, "dur", duration_ms)

            elif name_u == "BUZZER":
                continuous = params.get("continuous", False)
                delay_ms = int(params.get("delay_ms", 0))
                duration_ms = int(params.get("duration_ms", 0))
                level = int(params.get("level", 200))
                
                if continuous:
                    # Continuous mode: turn on immediately and keep on
                    self._schedule_cmd_at(0, self._cmd_buzzer_on)
                    self.log("Scheduled BUZZER: Continuous")
                elif duration_ms > 0:
                    # Pulsed mode: duration -> delay -> duration -> delay...
                    self._schedule_repeating_stimulus(
                        "BUZZER", level, delay_ms, duration_ms, base_time
                    )
                    self.log("Scheduled BUZZER: Repeating pattern, duration", duration_ms, "ms, delay", delay_ms, "ms")
                else:
                    # Single pulse
                    self._schedule_cmd_at(delay_ms, self._cmd_buzzer_on)
                    if duration_ms > 0:
                        self._schedule_cmd_at(delay_ms + duration_ms, self._cmd_buzzer_off)
                    self.log("Scheduled BUZZER: Single pulse at", delay_ms, "ms")

            elif name_u == "HEATER":
                level = int(params.get("level", 200))
                continuous = params.get("continuous", False)
                delay_ms = int(params.get("delay_ms", 0))
                duration_ms = int(params.get("duration_ms", 0))
                
                if continuous:
                    # Continuous mode: turn on immediately and keep on
                    self._schedule_cmd_at(0, lambda lv=level: self._cmd_heater_set(lv))
                    self.log("Scheduled HEATER: Continuous at level", level)
                elif duration_ms > 0:
                    # Pulsed mode: duration -> delay -> duration -> delay...
                    self._schedule_repeating_stimulus(
                        "HEATER", level, delay_ms, duration_ms, base_time
                    )
                    self.log("Scheduled HEATER: Repeating pattern, duration", duration_ms, "ms, delay", delay_ms, "ms at level", level)
                else:
                    # Single pulse
                    self._schedule_cmd_at(delay_ms, lambda lv=level: self._cmd_heater_set(lv))
                    self.log("Scheduled HEATER: Single pulse at", delay_ms, "ms, level", level)

            else:
                self.log("ExperimentRunner: unknown stimulus:", name)

    def _schedule_cmd_at(self, delay_ms: int, fn: Callable):
        if self._stop_event.is_set():
            return
        t = threading.Timer(delay_ms / 1000.0, self._timed_fn_wrapper, args=(fn,))
        t.daemon = True
        t.start()
        self._active_timers.append(t)
    
    def _schedule_repeating_stimulus(self, stimulus_name: str, level: int, 
                                     delay_ms: int, duration_ms: int, base_time: float):
        """
        Schedule a repeating stimulus pattern: ON for duration_ms, OFF for delay_ms, repeat.
        Pattern: ON (duration) -> OFF (delay) -> ON (duration) -> OFF (delay) -> ...
        """
        if duration_ms <= 0:
            return
        
        cycle_time = duration_ms + delay_ms  # Total time for one cycle
        
        def schedule_cycle(cycle_start_ms: int):
            """Schedule a single cycle, then schedule the next one"""
            if self._stop_event.is_set():
                return
            
            # Turn ON at cycle start
            if stimulus_name == "VIB":
                self._schedule_cmd_at(cycle_start_ms, lambda: self._cmd_vib_set(level))
            elif stimulus_name == "BUZZER":
                self._schedule_cmd_at(cycle_start_ms, self._cmd_buzzer_on)
            elif stimulus_name == "HEATER":
                self._schedule_cmd_at(cycle_start_ms, lambda: self._cmd_heater_set(level))
            
            # Turn OFF after duration
            turn_off_ms = cycle_start_ms + duration_ms
            if stimulus_name == "VIB":
                self._schedule_cmd_at(turn_off_ms, lambda: self._cmd_vib_set(0))
            elif stimulus_name == "BUZZER":
                self._schedule_cmd_at(turn_off_ms, self._cmd_buzzer_off)
            elif stimulus_name == "HEATER":
                self._schedule_cmd_at(turn_off_ms, lambda: self._cmd_heater_set(0))
            
            # Schedule next cycle if delay > 0 (otherwise it's just one pulse)
            if delay_ms > 0:
                next_cycle_start = cycle_start_ms + cycle_time
                # Limit to reasonable number of cycles (10 minutes max)
                if next_cycle_start < 600000:  # 10 minutes = 600,000 ms
                    # Schedule the next cycle
                    self._schedule_cmd_at(next_cycle_start, lambda: schedule_cycle(next_cycle_start))
        
        # Start first cycle immediately (at time 0)
        schedule_cycle(0)

    def _timed_fn_wrapper(self, fn: Callable):
        if self._stop_event.is_set():
            return
        try:
            fn()
        except Exception as e:
            self.log("ExperimentRunner: scheduled function error:", e)

    # -------------------------
    # Stimulus commands
    # -------------------------
    def _cmd_ir_set(self, level: int):
        level = int(max(0, min(255, level)))
        self._send_arduino_command(f"IR {level}")

    def _cmd_white_set(self, level: int):
        level = int(max(0, min(255, level)))
        self._send_arduino_command(f"WHITE {level}")

    def _cmd_vib_set(self, level: int):
        level = int(max(0, min(255, level)))
        self._send_arduino_command(f"VIB {level}")

    def _cmd_pump_set(self, level: int):
        level = int(max(0, min(255, level)))
        self._send_arduino_command(f"PUMP {level}")

    def _cmd_rgb_set(self, r: int, g: int, b: int):
        r = int(max(0, min(255, r)))
        g = int(max(0, min(255, g)))
        b = int(max(0, min(255, b)))
        self._send_arduino_command(f"RGB {r} {g} {b}")

    def _cmd_heater_set(self, level: int):
        level = int(max(0, min(255, level)))
        self._send_arduino_command(f"HEATER {level}")  # Note: HEATER may not be implemented in Arduino yet

    def _cmd_buzzer_on(self):
        self._send_arduino_command("BUZZER ON")

    def _cmd_buzzer_off(self):
        self._send_arduino_command("BUZZER OFF")

    def _cmd_off_all(self):
        try:
            self._cmd_ir_set(0)
            self._cmd_white_set(0)
            self._cmd_vib_set(0)
            self._cmd_pump_set(0)
            self._cmd_rgb_set(0, 0, 0)
            self._cmd_buzzer_off()
        except Exception as e:
            self.log("ExperimentRunner: error in _cmd_off_all:", e)

    # -------------------------
    # Arduino communication helper
    # -------------------------
    def _get_arduino(self):
        """
        Resolve Arduino controller to use (order of preference):
         1) self.app.arduino if app provided
         2) self.arduino_controller passed explicitly
         3) self.app (if it itself behaves like controller)
        """
        if self.app:
            try:
                ar = getattr(self.app, "arduino", None)
                if ar:
                    return ar
            except Exception:
                pass
        if self.arduino_controller:
            return self.arduino_controller
        # last resort: maybe self.app is the controller object
        if self.app and (hasattr(self.app, "send") or hasattr(self.app, "ser")):
            return self.app
        return None

    def _send_arduino_command(self, cmd: str) -> Optional[str]:
        """
        Send a textual command to the Arduino controller.
        Tries controller.send(cmd) first; falls back to raw serial writes to .ser.
        Returns any reply or None.
        """
        ar = self._get_arduino()
        if ar is None:
            self.log("ExperimentRunner: no arduino available for command:", cmd)
            return None

        # prefer high-level send()
        try:
            if hasattr(ar, "send"):
                try:
                    reply = ar.send(cmd)
                    self.log(f"ARDUINO <- {cmd}  (via ar.send) -> {reply}")
                    return reply
                except Exception as e:
                    self.log("ExperimentRunner: ar.send failed:", e)
        except Exception:
            pass

        # fallback: write to ar.ser if present
        ser = getattr(ar, "ser", None)
        if ser is None:
            self.log("ExperimentRunner: arduino has no send() or ser to send:", cmd)
            return None

        try:
            try:
                ser.reset_input_buffer()
            except Exception:
                pass
            ser.write((cmd.strip() + "\n").encode("utf-8"))
            ser.flush()
        except Exception as e:
            self.log("ExperimentRunner: raw serial write failed:", e)
            return None

        # attempt to read a line reply (non-blocking-ish)
        try:
            deadline = time.time() + 0.6
            while time.time() < deadline:
                line = ser.readline().decode(errors="ignore").strip()
                if line:
                    self.log("ARDUINO raw reply:", line)
                    return line
        except Exception:
            pass
        return None
