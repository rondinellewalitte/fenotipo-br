"""GPU memory readings through nvidia-smi: device info and the peak memory used while a
block of code runs (whole GPU, so it includes the display and every process)."""

from __future__ import annotations

import subprocess
import threading


def _query(fields: str) -> list[str] | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    first = out.strip().splitlines()[0] if out.strip() else ""
    return [x.strip() for x in first.split(",")] if first else None


def info() -> dict:
    row = _query("name,memory.total,memory.used,driver_version")
    if row is None:
        return {"available": False}
    name, total, used, driver = row
    return {
        "available": True,
        "name": name,
        "memory_total_mib": int(total),
        "memory_used_mib_at_start": int(used),
        "driver": driver,
    }


def used_mib() -> int | None:
    row = _query("memory.used")
    return int(row[0]) if row else None


class PeakMemory:
    """Context manager: polls memory.used every `interval` seconds; `.peak_mib` afterwards."""

    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self.peak_mib: int | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            v = used_mib()
            if v is not None and (self.peak_mib is None or v > self.peak_mib):
                self.peak_mib = v
            self._stop.wait(self.interval)

    def __enter__(self) -> PeakMemory:
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join()
