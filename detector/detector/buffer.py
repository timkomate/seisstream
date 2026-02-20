from typing import Dict, List, Tuple

import numpy as np

from .utils import parse_sid


class RollingTraceBuffer:
    """In-memory ring buffer of miniSEED samples keyed by source id."""

    def __init__(self, max_seconds: float):
        self.max_seconds = max_seconds
        self._buffers: Dict[str, dict] = {}

    def add_segment(
        self, sourceid: str, start: float, samprate: float, samples: np.ndarray
    ) -> None:
        if samprate <= 0:
            raise ValueError("samprate must be > 0")

        sample_count = int(samples.size)
        end = start if sample_count <= 0 else start + ((sample_count - 1) / samprate)
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

    def get(self, sourceid: str) -> Dict:
        return self._buffers.get(sourceid, {})

    def get_segment_length(self, sourceid: str) -> int:
        return self._buffers[sourceid]["samples"].size

    def get_samplerate(self, sourceid: str) -> float:
        return self._buffers[sourceid]["samprate"]

    def get_station_buffers(
        self, net: str, sta: str, loc: str
    ) -> List[Tuple[str, Dict]]:
        matches: List[Tuple[str, Dict]] = []
        for sid, seg in self._buffers.items():
            parsed = parse_sid(sid)
            if not parsed:
                continue
            p_net, p_sta, p_loc, _chan = parsed
            if p_net == net and p_sta == sta and p_loc == loc:
                matches.append((sid, seg))
        return matches
