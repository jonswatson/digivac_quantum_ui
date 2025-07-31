import time
from queue import Queue

from src.devices.simulated_device import SimulatedDevice
from src.model.model import MeasurementModel

def test_model_loop():
    q: "Queue[dict]" = Queue()
    model = MeasurementModel(SimulatedDevice(), poll_interval=0.2)
    model.subscribe(q.put)
    model.start()
    time.sleep(0.6)
    model.stop()
    assert not q.empty()
