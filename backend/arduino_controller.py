# backend/arduino_controller.py
import serial
import serial.tools.list_ports
import time
import logging
from typing import Optional

LOG = logging.getLogger("arduino_controller")
LOG.addHandler(logging.NullHandler())


class ArduinoController:
    """
    Robust Arduino serial controller.
    - connect(port) -> bool
    - auto_connect() -> bool
    - close()
    - send(cmd) -> reply str or None
    - read_temperature_c() -> Optional[float]
    """

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200, timeout: float = 0.6):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None
        self._connecting = False  # Prevent concurrent connection attempts

        if self.port:
            try:
                ok = self.connect(self.port)
                if not ok:
                    LOG.info("Initial connect failed for %s", self.port)
            except Exception as e:
                LOG.warning("Initial connect attempt raised: %s", e)

    def is_connected(self) -> bool:
        """Check if Arduino is connected. More robust check."""
        if self.ser is None:
            return False
        try:
            # Check if port is open
            if not getattr(self.ser, "is_open", False):
                return False
            # Additional check: try to get port info
            port = getattr(self.ser, "port", None)
            if port:
                return True
            return False
        except Exception:
            return False

    # -----------------------
    # low-level connect/open
    # -----------------------
    def _open_for_probe(self, port: str) -> Optional[serial.Serial]:
        """
        Try to open serial and return Serial object or None.
        This function never attaches to self.ser; it's only for probing.
        """
        try:
            # Open with longer timeout for initial connection
            # If reset_arduino is False, we can try to connect without resetting
            s = serial.Serial(port, self.baudrate, timeout=1.0)
            
            # Arduino resets when DTR toggles (happens on open)
            # Wait shorter for Arduino to boot and send startup messages
            time.sleep(0.8)  # Reduced from 1.5
            
            try:
                # Clear input buffer first
                s.reset_input_buffer()
                # Read and discard all startup messages (ZIMON_MEGA_READY, etc.)
                deadline = time.time() + 0.8  # Reduced from 1.0
                startup_lines = []
                while time.time() < deadline:
                    try:
                        if s.in_waiting > 0:
                            line = s.readline().decode(errors="ignore").strip()
                            if line:
                                startup_lines.append(line)
                                LOG.debug("Startup message from %s: %r", port, line)
                                # If we see ZIMON_MEGA_READY, Arduino is ready
                                if "ZIMON_MEGA" in line.upper():
                                    # Read one more line (the commands list)
                                    time.sleep(0.05)  # Reduced from 0.1
                                    try:
                                        s.readline()
                                    except:
                                        pass
                                    break
                            else:
                                time.sleep(0.02)  # Reduced from 0.05
                        else:
                            time.sleep(0.02)  # Reduced from 0.05
                    except Exception as e:
                        LOG.debug("Error reading startup: %s", e)
                        break
                
                if startup_lines:
                    LOG.debug("Cleared %d startup lines from %s", len(startup_lines), port)
            except Exception as e:
                LOG.debug("Error clearing startup messages: %s", e)
            return s
        except PermissionError as pe:
            LOG.warning("Permission denied opening %s: %s", port, pe)
            return None
        except serial.SerialException as se:
            LOG.debug("SerialException opening %s: %s", port, se)
            return None
        except Exception as e:
            LOG.debug("Unexpected error opening %s: %s", port, e)
            return None

    def connect(self, port: str) -> bool:
        """
        Open and attach to port; perform handshake (PING).
        If handshake succeeds then Serial is attached to self.ser and self.port set.
        
        Args:
            port: Serial port name (e.g., 'COM4')
        """
        # Prevent concurrent connection attempts
        if self._connecting:
            LOG.warning("Connection already in progress, ignoring request")
            return False
            
        # If already connected to this port, return success
        if self.is_connected() and self.port == port:
            LOG.info("Already connected to %s", port)
            return True
            
        # If connected to different port, disconnect first
        if self.is_connected():
            LOG.info("Disconnecting from current port before connecting to %s", port)
            self.close()
        
        self._connecting = True
        try:
            LOG.info("Opening serial %s @ %d (connect)", port, self.baudrate)

            # try a few times for reliability
            attempts = 3
            for attempt in range(1, attempts + 1):
                s = self._open_for_probe(port)
                if s is None:
                    time.sleep(0.05)
                    continue

                try:
                    # Make sure buffer is clear
                    s.reset_input_buffer()
                    time.sleep(0.1)  # Reduced from 0.2
                    
                    # Send PING command
                    s.write(b"PING\n")
                    s.flush()
                    LOG.debug("Sent PING to %s", port)
                except Exception as e:
                    LOG.debug("Write during handshake failed on %s: %s", port, e)
                    try:
                        s.close()
                    except Exception:
                        pass
                    time.sleep(0.1)
                    continue

                # Wait for reply - Arduino should respond with ZIMON_OK
                deadline = time.time() + 1.5  # Reduced from 2.0
                reply_lines = []
                while time.time() < deadline:
                    try:
                        if s.in_waiting > 0:
                            line = s.readline().decode(errors="ignore").strip()
                            if line:
                                reply_lines.append(line)
                                LOG.debug("Handshake reply from %s: %r", port, line)
                                # Accept if contains ZIMON_OK (PING response) or ZIMON_MEGA (startup)
                                if "ZIMON_OK" in line.upper() or "ZIMON_MEGA" in line.upper() or "ZEB" in line.upper():
                                    LOG.info("Found ZIMON device on %s", port)
                                    break
                        else:
                            time.sleep(0.05)  # Wait for data
                    except Exception as e:
                        LOG.debug("Error reading handshake reply: %s", e)
                        time.sleep(0.05)

                # evaluate replies
                if reply_lines:
                    # Check if we got a valid ZIMON response
                    has_zimon = any("ZIMON_OK" in line.upper() or "ZIMON_MEGA" in line.upper() for line in reply_lines)
                    if has_zimon:
                        LOG.info("Handshake reply from %s: %s", port, reply_lines)
                        # attach serial to controller
                        self.ser = s
                        self.port = port
                        LOG.info("Connected and attached to %s", port)
                        self._connecting = False
                        return True
                    else:
                        LOG.debug("Got reply but not ZIMON device: %s", reply_lines)
                
                # no valid reply - close and retry
                try:
                    s.close()
                except Exception:
                    pass
                LOG.info("No handshake reply on %s (attempt %d/%d)", port, attempt, attempts)
                time.sleep(0.1)  # Reduced from 0.2

            LOG.error("Failed to open serial %s after %d attempts", port, attempts)
            self._connecting = False
            return False
            
        except Exception as e:
            LOG.error("Connection error: %s", e, exc_info=True)
            self._connecting = False
            return False

    def auto_connect(self) -> bool:
        """
        Scan available serial ports and try to attach to the Arduino by sending PING.
        Returns True if a device was found and attached.
        """
        ports = [p.device for p in serial.tools.list_ports.comports()]
        LOG.info("Auto-detect scanning ports: %s", ports)

        for p in ports:
            LOG.debug("Probing %s", p)
            s = self._open_for_probe(p)
            if s is None:
                continue

            try:
                s.reset_input_buffer()
                time.sleep(0.1)
            except Exception:
                pass

            # Send PING command
            try:
                s.reset_input_buffer()
                time.sleep(0.2)
                s.write(b"PING\n")
                s.flush()
                LOG.debug("Sent PING to probe %s", p)
            except Exception as e:
                LOG.debug("Write failed on %s: %s", p, e)
                try:
                    s.close()
                except Exception:
                    pass
                continue

            # Collect replies - wait longer for response
            deadline = time.time() + 2.0
            reply_lines = []
            while time.time() < deadline:
                try:
                    if s.in_waiting > 0:
                        line = s.readline().decode(errors="ignore").strip()
                        if line:
                            reply_lines.append(line)
                            LOG.debug("Probe %s got line: %r", p, line)
                            # Check for ZIMON_OK (PING response) or ZIMON_MEGA_READY (startup)
                            if "ZIMON_OK" in line.upper() or "ZIMON_MEGA" in line.upper() or "ZEB" in line.upper():
                                LOG.info("Found ZIMON device on probe %s", p)
                                break
                    else:
                        time.sleep(0.05)
                except Exception as e:
                    LOG.debug("Error reading probe reply: %s", e)
                    time.sleep(0.05)

            LOG.info("Probe %s reply: %r", p, reply_lines)

            if reply_lines:
                # attach this serial and return success
                self.ser = s
                self.port = p
                LOG.info("Auto-detect found device at %s (reply lines: %s)", p, reply_lines)
                return True
            else:
                try:
                    s.close()
                except Exception:
                    pass
                continue

        LOG.info("Auto-detect found no matching device.")
        return False

    def close(self):
        self._connecting = False  # Reset connection state
        try:
            if self.ser:
                try:
                    self.ser.close()
                except Exception:
                    pass
                self.ser = None
                LOG.info("Serial closed")
        except Exception as e:
            LOG.warning("Error closing serial: %s", e)

    def send(self, cmd: str, read_reply: bool = True) -> Optional[str]:
        """
        Send a command string (without trailing newline) and optionally read a single-line reply.
        Returns the reply string (stripped) or None on failure / no reply.
        """
        if not self.is_connected():
            LOG.warning("send() called but serial is not open")
            return None

        payload = (cmd.strip() + "\n").encode("utf-8")

        try:
            # Clear input buffer before sending
            self.ser.reset_input_buffer()
        except Exception:
            pass

        try:
            self.ser.write(payload)
            self.ser.flush()
        except Exception as e:
            LOG.warning("Failed to write to serial: %s", e)
            return None

        if not read_reply:
            return None

        try:
            # Wait for reply with timeout
            deadline = time.time() + 1.0
            reply = None
            while time.time() < deadline:
                if self.ser.in_waiting > 0:
                    reply = self.ser.readline().decode(errors="ignore").strip()
                    if reply:
                        LOG.debug("send(%s) reply=%r", cmd, reply)
                        return reply
                else:
                    time.sleep(0.01)
            
            # If no reply, try one more read
            if reply is None:
                try:
                    reply = self.ser.readline().decode(errors="ignore").strip()
                    if reply:
                        LOG.debug("send(%s) reply=%r (late)", cmd, reply)
                        return reply
                except:
                    pass
            
            LOG.debug("send(%s) no reply", cmd)
            return None
        except Exception as e:
            LOG.warning("Failed reading reply: %s", e)
            return None

    def read_temperature_c(self) -> Optional[float]:
        """
        Ask the device for temperature with 'TEMP?' command.
        Returns float Celsius or None.
        """
        if not self.is_connected():
            return None

        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass

        try:
            self.ser.write(b"TEMP?\n")
            self.ser.flush()
        except Exception as e:
            LOG.warning("TEMP? write failed: %s", e)
            return None

        # read up to 1 second, collect the first line with a float token
        deadline = time.time() + 1.0
        reply = None
        while time.time() < deadline:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
            except Exception:
                line = ""
            if line:
                reply = line
                break
            time.sleep(0.02)

        if not reply:
            return None

        LOG.debug("TEMP? raw reply: %r", reply)
        # parse numeric token
        parts = reply.split()
        for tok in reversed(parts):
            try:
                return float(tok)
            except Exception:
                continue
        return None

    # --- ZIMON / ZEBB stimulus & environment (serial; I2C DAC handled on device) ---

    def write_command(self, cmd: str) -> bool:
        """
        Send a line without waiting for a reply (non-blocking for UI).
        Returns True if bytes were written.
        """
        if not self.is_connected():
            LOG.warning("write_command: not connected")
            return False
        payload = (cmd.strip() + "\n").encode("utf-8")
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass
        try:
            self.ser.write(payload)
            self.ser.flush()
            return True
        except Exception as e:
            LOG.warning("write_command failed: %s", e)
            return False

    def set_ir_intensity(self, percent: float) -> bool:
        v = max(0, min(100, int(round(percent))))
        return self.write_command(f"ENV_IR {v}")

    def set_white_intensity(self, percent: float) -> bool:
        v = max(0, min(100, int(round(percent))))
        return self.write_command(f"ENV_WHITE {v}")

    def vibrate_on(self) -> bool:
        return self.write_command("VIBRATE_ON")

    def vibrate_off(self) -> bool:
        return self.write_command("VIBRATE_OFF")

    def vibrate_timed(self, duration_ms: int) -> bool:
        d = max(0, int(duration_ms))
        return self.write_command(f"VIBRATE_TIMED {d}")

    def rgb_set(self, r: int, g: int, b: int) -> bool:
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        return self.write_command(f"RGB_SET {r} {g} {b}")

    def timed_stimulus(self, delay_ms: int, duration_ms: int) -> bool:
        return self.write_command(
            f"TIMED_STIMULUS {max(0, int(delay_ms))} {max(0, int(duration_ms))}"
        )
