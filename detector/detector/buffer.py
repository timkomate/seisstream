from __future__ import annotations

import logging
from typing import Dict

import numpy as np


class RollingTraceBuffer:
    """In-memory ring buffer of miniSEED samples keyed by source id."""

    def __init__(self, max_seconds: float):
        self.max_seconds = max_seconds
        self._buffers: Dict[str, dict] = {}

    def add_segment(self, sourceid: str, start: float, end: float,
                    samprate: float, samples: np.ndarray) -> None:
        buf = self._buffers.get(sourceid)

        if buf is None:
            buf = {"start": start, "end": end, "samprate": samprate, "samples": samples}
            self._buffers[sourceid] = buf
        else:
            buf["samples"] = np.concatenate((buf["samples"], samples))
            buf["end"] = end

        cutoff = end - self.max_seconds
        if buf["start"] < cutoff:
            trim_samples = int(np.ceil((cutoff - buf["start"]) * buf["samprate"]))
            if trim_samples > 0:
                trim_samples = min(trim_samples, max(len(buf["samples"]) - 1, 0))
                if trim_samples:
                    buf["samples"] = buf["samples"][trim_samples:]
                    buf["start"] += trim_samples / buf["samprate"]

            if buf["start"] < cutoff:
                buf["start"] = cutoff

    def get(self, sourceid: str) -> Dict:
        buf = self._buffers.get(sourceid)
        return buf if buf else {}

    def get_segment_length(self, sourceid: str) -> int:
        return self._buffers[sourceid]["samples"].size

    def get_samplerate(self, sourceid: str) -> float:
        return self._buffers[sourceid]["samprate"]
