import logging
from typing import List, Tuple

import pymseed
from obspy.signal.trigger import classic_sta_lta, trigger_onset

from .signal import preprocess_trace


def decode_mseed(body: bytes) -> pymseed.MS3TraceList:
    logging.debug("Decoding miniSEED buffer length=%d", len(body))
    traces = pymseed.MS3TraceList()
    traces.add_buffer(body, record_list=True, skip_not_data=True, validate_crc=True)
    return traces


def detect_sta_lta(
    _segment: dict,
    sid: str,
    fmin: float,
    fmax: float,
    sta_seconds: float,
    lta_seconds: float,
    trigger_on: float,
    trigger_off: float,
) -> List[Tuple[float, float]]:
    y_f = preprocess_trace(_segment["samples"], _segment["samprate"], fmin, fmax)
    cfg = classic_sta_lta(
        y_f,
        int(_segment["samprate"] * sta_seconds),
        int(_segment["samprate"] * lta_seconds),
    )
    pick = trigger_onset(cfg, trigger_on, trigger_off)
    logging.info("%d events are found.", len(pick))
    if len(pick):
        picks: List[Tuple[float, float]] = []
        start = _segment["start"]
        samprate = _segment["samprate"]
        for start_idx, end_idx in pick:
            picks.append((start + (start_idx / samprate),
                          start + (end_idx / samprate)))
        logging.info("picks for %s: %s", sid, picks)
        return picks
    return []
