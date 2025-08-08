"""
Thread‑safe polling loop + state store.
"""

from __future__ import annotations
import threading
import time
from typing import Callable, Dict, Any, Optional
from ..devices.base import BaseDevice
from ..utils.logger import CsvLogger

_CALLBACK = Callable[[Dict[str, Any]], None]


class MeasurementModel:
    """
    Owns the device instance, polling thread, and CSV logger.
    """

    def __init__(
        self,
        device: BaseDevice,
        poll_interval: float = 0.15,
        log_prefix: str = "real",
        unit: str = "mbar",
    ) -> None:
        self.device = device
        self.poll_interval = poll_interval
        self._callbacks: list[_CALLBACK] = []
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.logger = CsvLogger(prefix=log_prefix, unit=unit)

    # -------- Public API -------- #

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.device.connect()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()
        self.device.disconnect()

    def subscribe(self, cb: _CALLBACK) -> None:
        """Register a callback executed on every new measurement dict."""
        self._callbacks.append(cb)

    # -------- Internal -------- #

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                data = self.device.query()
            except Exception as ex:
                for cb in self._callbacks:
                    cb({"error": f"{type(ex).__name__}: {ex}"})
                break  # terminate polling thread

            for cb in self._callbacks:
                cb(data)
            # Persist to disk
            self.logger.append(
                [
                    time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                    self.logger._file_path.stem.split("_")[1],  # the unit part of the filename
                    data["pressure"],
                    data["temperature"],
                    "",  # placeholder for setpoint status
                ]
            )
            time.sleep(self.poll_interval)
