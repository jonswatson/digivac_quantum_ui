"""
RS‑232 implementation for the DigiVac Quantum DPP series.
"""

from __future__ import annotations
import serial
import threading
from time import sleep
from typing import Optional
from .base import BaseDevice, DeviceError

_TERMINATOR = "\\r\n"  # DigiVac default
_POLL_DELAY = 0.05    # seconds between command & response

class RS232Device(BaseDevice):
    """
    A very thin synchronous wrapper over pySerial,
    matching the BaseDevice interface.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        address: int = 253,
        timeout: float = 1.0,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.address = address
        self.timeout = timeout
        self._ser: Optional[serial.Serial] = None
        self._lock = threading.Lock()

    # ---------- Private helpers ---------- #

    def _format(self, payload: str) -> str:
        """Prepend address & append CR‑LF terminator."""
        return f"@{self.address}{payload}{_TERMINATOR}"

    def _write(self, msg: str) -> None:
        if not self._ser:
            raise DeviceError("Serial port not open.")
        self._ser.write(msg.encode("ascii"))

    def _readline(self) -> str:
        if not self._ser:
            raise DeviceError("Serial port not open.")
        line = self._ser.readline().decode("ascii").strip()
        if not line:
            raise DeviceError("No response from device.")
        return line

    # ---------- Public API ---------- #

    def connect(self) -> None:
        self._ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
        )

    def disconnect(self) -> None:
        if self._ser:
            if self._ser.is_open:
                try:
                    self._ser.close()
                except (OSError, serial.SerialException):
                    # Port was yanked (USB unplug / power-cycle) – ignore.
                    pass
            self._ser = None

    def is_connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def send_command(self, cmd: str) -> str:
        """
        Send raw (already formatted) command and return raw response.
        Intended for advanced/diagnostic use.
        """
        with self._lock:
            self._write(cmd)
            sleep(_POLL_DELAY)
            return self._readline()

    # --- High‑level measurement helpers --- #

# --- High-level measurement helpers --- #

    def _clean_response(self, line: str) -> str:
        """
        Trim '@<addr>' prefix *and* trailing '\' if present,
        then return the piece that starts with 'ACK'.
        """
        line = line.rstrip("\\")            # remove terminator back-slash
        if line.startswith("@"):
            # remove '@' + decimal digits
            i = 1
            while i < len(line) and line[i].isdigit():
                i += 1
            line = line[i:]
        return line

    def _query_numeric(self, mnemonic: str) -> float:
        """
        Send `@addr<MN>?` and parse `ACK<value>` (with or without @addr prefix).
        """
        raw_cmd = self._format(f"{mnemonic}?")
        self._write(raw_cmd)
        sleep(_POLL_DELAY)
        resp = self._clean_response(self._readline())

        if not resp.startswith("ACK"):
            raise DeviceError(f"Unexpected response: {resp}")

        try:
            return float(resp[3:])           # handles 7.4601E+02 just fine
        except ValueError as ex:
            raise DeviceError(f"Bad numeric value: {resp}") from ex


    def read_pressure(self) -> float:
        return self._query_numeric("P")

    def read_temperature(self) -> float:
        return self._query_numeric("T")

    def set_pressure_unit(self, unit: str) -> None:
        """
        Change the gauge’s pressure unit. 
        unit: one of 'mbar', 'torr', 'pascal' (case-insensitive).
        """
        cmd = self._format(f"U!P,{unit.upper()}")
        resp = self.send_command(cmd)
        if not resp.startswith("ACK"):
            raise DeviceError(f"Failed to set pressure unit: {resp}")

    def get_pressure_unit(self) -> str:
        """
        Query the current pressure unit. Returns 'MBAR', 'TORR', or 'PASCAL'.
        """
        cmd = self._format("U?P")
        resp = self.send_command(cmd)
        if not resp.startswith("ACK"):
            raise DeviceError(f"Failed to query pressure unit: {resp}")
        return resp[3:].strip()