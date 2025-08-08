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

try:
    from serial.tools.list_ports import comports
except ImportError:  # pyserial not installed yet
    comports = lambda: []  # noqa: E731

from ..controller.controller import Controller


# --------------------------------------------------------------------------- #
# ------------------------------  HELPERS  ---------------------------------- #
# --------------------------------------------------------------------------- #
def _discover_ports() -> List[str]:
    return [p.device for p in comports()]


def _drain_queue(ctrl: Controller) -> None:
    """Pull ALL queued updates into session‑level DataFrame."""
    df: pd.DataFrame = st.session_state.data
    while True:
        try:
            item = ctrl.queue.get_nowait()
            if "error" in item:  # device error sent by Model
                st.session_state.error_msg = item["error"]
                ctrl.stop()
                break
            df.loc[len(df)] = {
                "timestamp": pd.Timestamp.utcnow(),
                "pressure": item["pressure"],
                "temperature": item["temperature"],
            }
        except Empty:
            break


def _reset_data() -> None:
    st.session_state.data = pd.DataFrame(
        columns=["timestamp", "pressure", "temperature"]
    )
    st.session_state.error_msg = ""


# --------------------------------------------------------------------------- #
# ------------------------------  MAIN UI  ---------------------------------- #
# --------------------------------------------------------------------------- #
def render() -> None:
    st.set_page_config(page_title="Quantum Sensor Logger", layout="wide")
    st.title("DigiVac Quantum Sensor Logger")

    # ---------- Session state bootstrapping ---------- #
    if "controller" not in st.session_state:
        st.session_state.controller = Controller()  # type: ignore
    if "data" not in st.session_state:
        _reset_data()
    if "mode" not in st.session_state:
        st.session_state.mode = "Simulation"
    if "error_msg" not in st.session_state:
        st.session_state.error_msg = ""

    ctrl: Controller = st.session_state.controller  # type: ignore

    # ---------------- Sidebar controls --------------- #
    st.sidebar.header("Connection")

    mode = st.sidebar.radio("Mode", ["Real Device (RS‑232)", "Simulation"])
    poll_int = st.sidebar.slider("Poll interval (s)", 0.1, 2.0, 0.5, 0.1)

    unit = st.sidebar.selectbox(
        "Pressure unit",
        ["mbar", "torr", "pascal"],
        index=1,  # default = 'torr'
        help="Select the pressure unit for both UI display and log files.",
    )

    # Detect dropdown change AFTER a connection is active
    if "current_unit" not in st.session_state:
        st.session_state.current_unit = unit
    if ctrl.queue.qsize() and unit != st.session_state.current_unit:
        # clear DF & charts
        st.session_state.data = pd.DataFrame(
            columns=["timestamp", "pressure", "temperature"]
        )
        ctrl.change_unit(unit, poll_int)
        st.session_state.current_unit = unit

    # ---- Detect mode change -> stop & clear ---- #
    if mode != st.session_state.mode:
        ctrl.stop()
        _reset_data()
        st.session_state.mode = mode

    if mode.startswith("Real"):
        port = st.sidebar.selectbox("Serial port", _discover_ports())
        baud = st.sidebar.selectbox(
            "Baud rate",
            [4800, 9600, 19200, 38400, 57600, 115200],
            index=1,
        )
        address = st.sidebar.number_input(
            "Device address", 1, 253, value=253
        )  # 253 = factory default
        if st.sidebar.button("Connect"):
            ctrl.start_real(port, baudrate=baud, address=address, poll=poll_int, unit=unit)

    else:  # Simulation
        if st.sidebar.button("Start Simulation"):
            ctrl.start_simulated(poll=poll_int, unit=unit)

    if st.sidebar.button("Stop"):
        ctrl.stop()
        _reset_data()

    st.sidebar.write("---")
    st.sidebar.markdown("Logs saved in **`logs/`** folder.")

    # -------------------- Error banner ---------------- #
    if st.session_state.error_msg:
        with st.container():
            st.error(st.session_state.error_msg)
            if st.button("Dismiss error 🗙", key="dismiss_err"):
                st.session_state.error_msg = ""

    # ------------------ Main dashboard ---------------- #
    _drain_queue(ctrl)
    df: pd.DataFrame = st.session_state.data

    col_metric_p, col_metric_t = st.columns(2)
    col_chart_p, col_chart_t = st.columns(2)

    # Metrics
    if not df.empty:
        col_metric_p.metric(
            f"Current Pressure ({unit})", f"{df.pressure.iloc[-1]:.3e}"
        )
        col_metric_t.metric(
            "Current Temperature (°C)", f"{df.temperature.iloc[-1]:.2f}"
        )
    else:
        col_metric_p.metric("Current Pressure (mbar)", "—")
        col_metric_t.metric("Current Temperature (°C)", "—")

    # Charts
    with col_chart_p:
        st.subheader("Pressure vs. Time")
        st.line_chart(
            df.set_index("timestamp")["pressure"]
            if not df.empty
            else pd.Series(dtype=float)
        )
    with col_chart_t:
        st.subheader("Temperature vs. Time")
        st.line_chart(
            df.set_index("timestamp")["temperature"]
            if not df.empty
            else pd.Series(dtype=float)
        )

    # --------------- Auto‑refresh tick --------------- #
    if ctrl.queue.qsize() or getattr(ctrl, "_model", None):
        time.sleep(0.2)
        # streamlit 1.4 has experimental_rerun; >=1.29 has rerun
        (st.rerun if hasattr(st, "rerun") else st.experimental_rerun)()
