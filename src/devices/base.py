"""
Abstract base classes for device adapters.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any

class DeviceError(Exception):
    """Raised when the device returns an unexpected response or times out."""


class BaseDevice(ABC):
    """Common interface for real and simulated devices."""

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def read_pressure(self) -> float:
        """Returns pressure in the current unit (mbar by default)."""

    @abstractmethod
    def read_temperature(self) -> float:
        """Returns board or ambient temperature (°C)."""

    @abstractmethod
    def send_command(self, cmd: str) -> str:
        """Low‑level raw write/ read (optional for higher‑level control)."""

    # -------- Convenience helpers -------- #

    def query(self) -> Dict[str, Any]:
        """Return both pressure & temperature as a dict."""
        return {
            "pressure": self.read_pressure(),
            "temperature": self.read_temperature(),
        }

    # Context‑manager sugar
    def __enter__(self) -> "BaseDevice":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()
