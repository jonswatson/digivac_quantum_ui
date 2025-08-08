"""
Receives UI intents, instantiates Model & Device, relays updates up.
"""

from __future__ import annotations
from queue import Queue
from typing import Dict, Any, Optional

from ..devices.rs232_device import RS232Device
from ..devices.simulated_device import SimulatedDevice
from ..model.model import MeasurementModel
from ..utils.logger import CsvLogger

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
        unit: str = "torr",
    ) -> None:
        device = RS232Device(port=port, baudrate=baudrate, address=address)
        # set hardware unit once, before polling thread starts
        try:
            device.connect()
            device.set_pressure_unit(unit)
        finally:
            device.disconnect()

        self._pending_unit = None
        self._start_model(device, poll, log_prefix="real")

    def start_simulated(self, poll: float = 0.5, unit: str = "torr") -> None:
        device = SimulatedDevice()
        self._pending_unit = None
        self._start_model(device, poll, log_prefix="sim", unit=unit)

    def stop(self) -> None:
        if self._model:
            self._model.stop()
            self._model = None

    def set_unit(self, unit: str) -> None:
        """
        Apply a pressure-unit change to the active model/device.
        Must be called after start_real or start_simulated.
        """
        # store for passing into a new model on connect
        self._pending_unit = unit
        # if already running, apply directly to device and logger
        if self._model:
            # tell the hardware
            if hasattr(self._model.device, "set_pressure_unit"):
                self._model.device.set_pressure_unit(unit)
            # recreate the logger with new unit (optional: you could reopen a new file)
            self._model.logger = CsvLogger(prefix="real" if isinstance(self._model.device, RS232Device) else "sim", unit=unit)
    
    # ------------------------------------------------------------------ #
    #  Change pressure unit mid-run: stop → reconnect → set → restart    #
    # ------------------------------------------------------------------ #
    def change_unit(self, unit: str, poll: float = 0.5) -> None:
        """
        Stop current model, send U!P,<unit>\ on a fresh connection,
        clear logger/dataframe, then restart polling.
        """
        if not self._model:
            return  # nothing running, ignore

        # 1) Grab the existing device instance and stop polling.
        device = self._model.device
        self._model.stop()
        self._model = None           # avoid double-close

        # 2) Re-open the serial port (real device only) and set unit.
        if isinstance(device, RS232Device):
            device.connect()
            try:
                device.set_pressure_unit(unit)
            finally:
                device.disconnect()

        # 3) Start a new MeasurementModel (fresh logger/dataframe).
        self._model = MeasurementModel(
            device,
            poll_interval=poll,
            log_prefix="real" if isinstance(device, RS232Device) else "sim",
            unit=unit,
        )
        self._model.subscribe(self._queue.put)
        self._model.start()

    
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
