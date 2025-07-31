"""
Streamlit presentation layer.
Run `streamlit run app.py`
"""

from __future__ import annotations

import time
from queue import Empty
from typing import List

import pandas as pd
import streamlit as st
from serial.tools import list_ports

from ..controller.controller import Controller

# --------------------------------------------------------------------------- #
# -----------------------------  HELPER FUNCTIONS  -------------------------- #
# --------------------------------------------------------------------------- #
def _discover_ports() -> List[str]:
    """Return available serial ports, e.g. ['COM3', '/dev/ttyUSB0']."""
    return [p.device for p in list_ports.comports()]


def _drain_queue(ctrl: Controller) -> None:
    """
    Pull everything that is currently queued by the Model thread and
    append it to the session‑state DataFrame.
    """
    df: pd.DataFrame = st.session_state.data
    while True:
        try:
            update = ctrl.queue.get_nowait()  # {'pressure': …, 'temperature': …}
            df.loc[len(df)] = {
                "timestamp": pd.Timestamp.utcnow(),
                "pressure": update["pressure"],
                "temperature": update["temperature"],
            }
        except Empty:
            break


# --------------------------------------------------------------------------- #
# ------------------------------  MAIN RENDER  ------------------------------ #
# --------------------------------------------------------------------------- #
def render() -> None:
    st.set_page_config(page_title="Quantum Sensor Logger", layout="wide")
    st.title("DigiVac Quantum Sensor Logger")

    # -------------------------------- Session state ------------------------ #
    if "controller" not in st.session_state:
        st.session_state.controller = Controller()  # type: ignore
    if "data" not in st.session_state:
        st.session_state.data = pd.DataFrame(
            columns=["timestamp", "pressure", "temperature"]
        )

    ctrl: Controller = st.session_state.controller  # type: ignore

    # ------------------------------ Sidebar -------------------------------- #
    st.sidebar.header("Connection")

    mode = st.sidebar.radio("Mode", ["Real Device (RS‑232)", "Simulation"])

    poll_int = st.sidebar.slider("Poll interval (s)", 0.2, 2.0, 0.5, 0.1)

    if mode.startswith("Real"):
        port = st.sidebar.selectbox(
            "Serial port", _discover_ports(), help="Detected COM/tty ports"
        )
        baud = st.sidebar.selectbox(
            "Baud rate", [4800, 9600, 19200, 38400, 57600, 115200], index=1
        )
        address = st.sidebar.number_input(
            "Device address", min_value=1, max_value=253, value=253
        )  # 253 is factory default :contentReference[oaicite:2]{index=2}
        if st.sidebar.button("Connect"):
            ctrl.start_real(port, baudrate=baud, address=address, poll=poll_int)
    else:
        if st.sidebar.button("Start Simulation"):
            ctrl.start_simulated(poll=poll_int)

    if st.sidebar.button("Stop"):
        ctrl.stop()

    st.sidebar.write("---")
    st.sidebar.markdown("CSV logs are saved in the **`logs/`** folder.")

    # ------------------------------ Main area ------------------------------ #
    # Drain any queued measurements **every rerun** and append to DF
    if ctrl.queue:
        _drain_queue(ctrl)

    df: pd.DataFrame = st.session_state.data

    col_metric_p, col_metric_t = st.columns(2)
    col_chart_p, col_chart_t = st.columns(2)

    # ---- Current values (metrics) ---- #
    if not df.empty:
        col_metric_p.metric(
            "Current Pressure (mbar)", f"{df['pressure'].iloc[-1]:.3e}"
        )
        col_metric_t.metric(
            "Current Temperature (°C)", f"{df['temperature'].iloc[-1]:.2f}"
        )
    else:
        col_metric_p.metric("Current Pressure (mbar)", "N/A")
        col_metric_t.metric("Current Temperature (°C)", "N/A")

    # ---- Live plots ---- #
    with col_chart_p:
        st.subheader("Pressure vs. Time")
        st.line_chart(
            df.set_index("timestamp")["pressure"] if not df.empty else pd.Series(dtype=float)
        )

    with col_chart_t:
        st.subheader("Temperature vs. Time")
        st.line_chart(
            df.set_index("timestamp")["temperature"] if not df.empty else pd.Series(dtype=float)
        )

    # --------------------------- Auto‑refresh logic ------------------------ #
    # Streamlit re‑executes the script from top on every user interaction.
    # To keep charts live without blocking, schedule a lightweight rerun.
    if ctrl.queue.qsize() or ctrl._model:  # type: ignore (polling active?)
        time.sleep(0.2)  # small pause to avoid hammering the event loop
        st.rerun()
