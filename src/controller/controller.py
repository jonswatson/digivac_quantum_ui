"""
Receives UI intents, instantiates Model & Device, relays updates up.
"""

from __future__ import annotations
from queue import Queue
from typing import Dict, Any, Optional

from ..devices.rs232_device import RS232Device
from ..devices.simulated_device import SimulatedDevice
from ..model.model import MeasurementModel

Update = Dict[str, Any]


class Controller:
    """
    The Controller is intentionally very thin; it marshals config
    from the UI into model/device objects and publishes a thread‑safe
    message queue back to the UI.
    """

    def __init__(self) -> None:
        self._queue: "Queue[Update]" = Queue()
        self._model: Optional[MeasurementModel] = None

    # -------- Lifecycle -------- #

    def start_real(
        self,
        port: str,
        baudrate: int = 9600,
        address: int = 1,
        poll: float = 0.5,
    ) -> None:
        device = RS232Device(port=port, baudrate=baudrate, address=address)
        self._start_model(device, poll, log_prefix="real")

    def start_simulated(self, poll: float = 0.5) -> None:
        device = SimulatedDevice()
        self._start_model(device, poll, log_prefix="sim")

    def stop(self) -> None:
        if self._model:
            self._model.stop()

    # -------- Public getters -------- #

    @property
    def queue(self) -> "Queue[Update]":
        return self._queue

    # -------- Private helpers -------- #

    def _start_model(self, device, poll, log_prefix: str) -> None:
        if self._model:
            self.stop()
        self._model = MeasurementModel(
            device, poll_interval=poll, log_prefix=log_prefix
        )        
        self._model.subscribe(self._queue.put)
        self._model.start()
