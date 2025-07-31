from src.devices.simulated_device import SimulatedDevice

def test_simulated_device_basic():
    dev = SimulatedDevice()
    dev.connect()
    p1 = dev.read_pressure()
    t1 = dev.read_temperature()
    assert p1 > 0.0
    assert 0.0 < t1 < 100.0
    dev.disconnect()
