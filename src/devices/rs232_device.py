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
        with self._lock:
            self._ser.write(msg.encode("ascii"))
            self._ser.flush()

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
        if self._ser:
            self._ser.reset_input_buffer()
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
        Ensure the gauge is in the requested pressure unit.

        unit: 'mbar', 'torr', or 'pascal'  (case-insensitive).

        Strategy
        --------
        1. If already in that unit → return.
        2. Send U!P,<UNIT>\ .
           • Firmware may reply ACK<UNIT>
           • Older builds sometimes send *nothing* or echo a pressure line first.
        3. After write, re-query the unit; if it now matches, treat as success.
           Otherwise raise DeviceError.
        """
        target = unit.upper()

        # 1. Skip if already correct
        try:
            if self.get_pressure_unit() == target:
                return
        except DeviceError:
            # ignore transient query failure; we'll verify after write
            pass

        cmd = self._format(f"U!P,{target}")

        # 2. Write command
        self._write(cmd)
        sleep(0.25)            # give firmware ample time

        # 3. Drain up to two reply lines (ignore content)
        for _ in range(2):
            try:
                _ = self._readline()
            except DeviceError:
                break          # no more data

        # 4. Verify by querying
        try:
            if self.get_pressure_unit() != target:
                raise DeviceError(
                    f"Device on port {self.port}: Gauge did not switch to {target}"
                )
        except DeviceError as ex:
            # propagate with port info
            raise DeviceError(
                f"Device on port {self.port}: {ex}"
            ) from ex


    def get_pressure_unit(self) -> str:
        """
        Query current pressure unit.
        Returns 'MBAR', 'TORR', or 'PASCAL'.
        Accepts replies that include the @<addr> prefix.
        """
        cmd = self._format("U?P")
        resp = self.send_command(cmd)            # e.g. '@253ACKMBAR\\'
        resp = self._clean_response(resp)        # <-- strip @addr + trailing '\'

        if not resp.startswith("ACK"):
            raise DeviceError(f"Failed to query pressure unit: {resp}")

        return resp[3:].strip().upper()
