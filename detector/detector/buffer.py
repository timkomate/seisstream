from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

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

    def parse_sid(self, sid: str) -> Optional[Tuple[str, str, str, str]]:
        if not sid:
            return None
        cleaned = sid
        if cleaned.startswith("FDSN:"):
            cleaned = cleaned[5:]
        # FDSN source IDs can appear as NET_STA_LOC_CHA or with channel split as
        # NET_STA_LOC_C_H_A (e.g. FDSN:XX_TEST__H_H_Z).
        if "_" in cleaned:
            parts = cleaned.split("_")
            if len(parts) < 4:
                return None
            net, sta, loc = parts[0], parts[1], parts[2]
            chan = "".join(parts[3:])
            if not chan:
                return None
            return net, sta, loc, chan
        if "." in cleaned:
            parts = cleaned.split(".")
            if len(parts) < 4:
                return None
            net, sta, loc, chan = parts[0], parts[1], parts[2], parts[3]
            if not chan:
                return None
            return net, sta, loc, chan
        return None

    def get_station_buffers(
        self, net: str, sta: str, loc: str
    ) -> List[Tuple[str, Dict]]:
        matches: List[Tuple[str, Dict]] = []
        for sid, seg in self._buffers.items():
            parsed = self.parse_sid(sid)
            if not parsed:
                continue
            p_net, p_sta, p_loc, _chan = parsed
            if p_net == net and p_sta == sta and p_loc == loc:
                matches.append((sid, seg))
        return matches
