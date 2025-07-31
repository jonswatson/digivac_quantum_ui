"""
Light‑weight CSV logger for measurement records.
"""

from __future__ import annotations
from pathlib import Path
from datetime import datetime
import csv
from typing import Iterable


class CsvLogger:
    """
    Appends measurement rows to a CSV file.
    Filename prefix indicates 'real' or 'sim'.
    """

    def __init__(self, prefix: str, directory: str | Path = "logs") -> None:
        self._base_dir = Path(directory)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self._file_path = self._base_dir / f"{prefix}_measurements_{timestamp}.csv"

        with self._file_path.open("w", newline="") as f:
            csv.writer(f).writerow(
                ["timestamp_utc", "pressure", "temperature", "setpoint_status"]
            )

    @property
    def file_path(self) -> Path:
        return self._file_path

    def append(self, row: Iterable) -> None:
        with self._file_path.open("a", newline="") as f:
            csv.writer(f).writerow(row)
