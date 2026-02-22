import numpy as np

from detector import detection as detection_mod


def test_decode_mseed_calls_add_buffer(monkeypatch):
    calls = {}

    class FakeTraceList:
        def add_buffer(self, data, record_list, skip_not_data, validate_crc):
            calls["args"] = (data, record_list, skip_not_data, validate_crc)

    monkeypatch.setattr(detection_mod.pymseed, "MS3TraceList", lambda: FakeTraceList())

    result = detection_mod.decode_mseed(b"abc")

    assert isinstance(result, FakeTraceList)
    assert calls["args"] == (b"abc", True, True, True)


def test_detect_sta_lta_no_triggers(monkeypatch):
    segment = {"samples": np.array([1.0, 2.0]), "samprate": 10.0, "start": 100.0}

    monkeypatch.setattr(detection_mod, "preprocess_trace", lambda *args, **kwargs: np.array([0.0]))
    monkeypatch.setattr(detection_mod, "classic_sta_lta", lambda *args, **kwargs: np.array([0.0]))
    monkeypatch.setattr(detection_mod, "trigger_onset", lambda *args, **kwargs: [])

    picks = detection_mod.detect_sta_lta(segment, "XX.TEST..BHZ", 0.1, 10.0, 6.0, 20.0, 2.5, 0.5)

    assert picks == []


def test_detect_sta_lta_triggers(monkeypatch):
    segment = {"samples": np.array([1.0, 2.0]), "samprate": 10.0, "start": 100.0}

    monkeypatch.setattr(detection_mod, "preprocess_trace", lambda *args, **kwargs: np.array([0.0]))
    monkeypatch.setattr(detection_mod, "classic_sta_lta", lambda *args, **kwargs: np.array([0.0]))
    monkeypatch.setattr(detection_mod, "trigger_onset", lambda *args, **kwargs: [(10, 20), (25, 30)])

    picks = detection_mod.detect_sta_lta(segment, "XX.TEST..BHZ", 0.1, 10.0, 6.0, 20.0, 2.5, 0.5)

    assert picks == [(101.0, 102.0), (102.5, 103.0)]
