#!/usr/bin/env python3
"""
scan_addresses.py

1) Lists all available serial ports.
2) Prompts you to select one.
3) Probes addresses 1–253 with a 'P?' query and reports any responders,
   showing progress as it goes.
"""

import serial
import sys
from time import sleep
from serial.tools import list_ports

TERMINATOR = "\r\n"
BAUDRATE = 9600
TIMEOUT  = 0.5


def pick_port() -> str:
    """List all ports, let the user pick one by number."""
    ports = list(list_ports.comports())
    if not ports:
        print("❌ No serial ports detected.")
        sys.exit(1)

    print("Available serial ports:")
    for i, p in enumerate(ports, start=1):
        print(f"  {i}. {p.device} — {p.description}")

    while True:
        choice = input(f"Select port [1-{len(ports)}]: ").strip()
        if not choice.isdigit():
            print("▶️  Please enter a number.")
            continue
        idx = int(choice)
        if 1 <= idx <= len(ports):
            return ports[idx - 1].device
        print(f"▶️  Invalid choice, must be between 1 and {len(ports)}.")


def scan(port: str) -> None:
    """
    Open the serial port once, then probe each address,
    printing progress and any responders.
    """
    try:
        ser = serial.Serial(port, BAUDRATE, timeout=TIMEOUT)
    except serial.SerialException as e:
        print(f"❌ Error opening {port}: {e}")
        sys.exit(1)

    print(f"🔍 Scanning addresses 1–253 on {port} at {BAUDRATE} bps…")
    found = []

    for addr in range(1, 254):
        # Progress update
        print(f"  Probing address {addr:3d} …", end="\r", flush=True)

        cmd = f"@{addr}P?{TERMINATOR}"
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write(cmd.encode("ascii"))
        sleep(0.1)
        resp = ser.readline().decode("ascii", errors="ignore").strip()
        if resp.startswith("ACK"):
            found.append((addr, resp))
            print(f"[+] Addr {addr:3d}: {resp}")

    ser.close()
    print(" " * 40, end="\r")  # clear the last progress line

    if found:
        print("\n✅ Responders found:")
        for addr, resp in found:
            print(f" • {addr:3d} → {resp}")
    else:
        print("\n❌ No devices replied on any address 1–253.")


if __name__ == "__main__":
    port = pick_port()
    scan(port)
