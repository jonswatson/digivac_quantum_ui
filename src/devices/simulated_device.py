"""
Deterministic but configurable fake device for UI & controller testing.
"""

from __future__ import annotations
import math
import time
import random
from typing import Optional
from .base import BaseDevice

class SimulatedDevice(BaseDevice):
    """
    Generates a slow logarithmic decay with noise, approximating pump‑down.
    """

    def __init__(
        self,
        start_pressure: float = 1.0e-1,
        temp_c: float = 22.0,
        noise: float = 0.05,
    ) -> None:
        self.start_time: Optional[float] = None
        self.start_pressure = start_pressure
        self.temp = temp_c
        self.noise = noise
        self._connected = False

    # ---- Lifecycle ---- #

    def connect(self) -> None:
        self.start_time = time.time()
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    # ---- Behaviour ---- #

    def _elapsed(self) -> float:
        return max(0.0, time.time() - (self.start_time or time.time()))

    def read_pressure(self) -> float:
        """
        Log‑decay: P(t) = P0 * 10^-(t/120)  plus small random noise.
        """
        if not self._connected:
            raise RuntimeError("Not connected (simulation mode).")
        base = self.start_pressure * 10 ** (-(self._elapsed() / 120.0))
        jitter = base * self.noise * (random.random() - 0.5)
        return max(base + jitter, 1e-9)

    def read_temperature(self) -> float:
        """Return a gently oscillating board temperature."""
        if not self._connected:
            raise RuntimeError("Not connected (simulation mode).")
        delta = 0.5 * math.sin(self._elapsed() / 60.0)
        return self.temp + delta

    def send_command(self, cmd: str) -> str:
        """Echo back a plausible, well‑formed response."""
        if "P?" in cmd:
            return f"ACK{self.read_pressure():.3e}"
        if "T?" in cmd:
            return f"ACK{self.read_temperature():.2f}"
        return "ACKOK"
