"""
RS‑232 implementation for the DigiVac Quantum DPP series.
"""

from __future__ import annotations
import serial
from time import sleep
from typing import Optional
from .base import BaseDevice, DeviceError

_TERMINATOR = "\r\n"  # DigiVac default
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
        if self._ser and self._ser.is_open:
            self._ser.close()

    def is_connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def send_command(self, cmd: str) -> str:
        """
        Send raw (already formatted) command and return raw response.
        Intended for advanced/diagnostic use.
        """
        self._write(cmd)
        sleep(_POLL_DELAY)
        return self._readline()

    # --- High‑level measurement helpers --- #

    def _query_numeric(self, mnemonic: str) -> float:
        """
        Send `@addr<mnemonic>?` and parse `ACK<value>` payload.
        """
        raw = self._format(f"{mnemonic}?")
        self._write(raw)
        sleep(_POLL_DELAY)
        response = self._readline()
        if not response.startswith("ACK"):
            raise DeviceError(f"Unexpected response: {response}")
        try:
            return float(response[3:])
        except ValueError as ex:
            raise DeviceError(f"Malformed numeric value: {response}") from ex

    def read_pressure(self) -> float:
        return self._query_numeric("P")

    def read_temperature(self) -> float:
        return self._query_numeric("T")
