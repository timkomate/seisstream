from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np
import pytest

from detector.seisbench_backend import SeisBenchConfig, SeisBenchPredictor


class _FakeModel:
    def __init__(self, in_samples: int = 4, classify_result=None):
        self.in_samples = in_samples
        self.classify_result = classify_result or SimpleNamespace(
            picks=[], detections=[]
        )
        self.device = None
        self.eval_called = False
        self.classify_calls = 0

    def to(self, device: str):
        self.device = device

    def eval(self):
        self.eval_called = True

    def classify(self, *args, **kwargs):
        self.classify_calls += 1
        return self.classify_result


def _install_fake_seisbench(monkeypatch, model: _FakeModel):
    models_module = SimpleNamespace(
        EQTransformer=SimpleNamespace(from_pretrained=lambda _name: model)
    )
    seisbench_module = SimpleNamespace(models=models_module)
    monkeypatch.setitem(sys.modules, "seisbench", seisbench_module)
    monkeypatch.setitem(sys.modules, "seisbench.models", models_module)


def test_init_rejects_unsupported_model_class(monkeypatch):
    model = _FakeModel(in_samples=4)
    _install_fake_seisbench(monkeypatch, model)
    with pytest.raises(ValueError, match="Unsupported SeisBench model_class"):
        SeisBenchPredictor(SeisBenchConfig(model_class="unknown"))


def test_init_rejects_invalid_in_samples(monkeypatch):
    model = _FakeModel(in_samples=0)
    _install_fake_seisbench(monkeypatch, model)

    with pytest.raises(ValueError, match="in_samples"):
        SeisBenchPredictor(SeisBenchConfig())


def test_init_falls_back_to_cpu_when_cuda_unavailable(monkeypatch):
    model = _FakeModel(in_samples=8)
    _install_fake_seisbench(monkeypatch, model)
    fake_torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    predictor = SeisBenchPredictor(SeisBenchConfig(device="cuda"))

    assert predictor.device == "cpu"
    assert model.device == "cpu"
    assert model.eval_called is True


def test_build_multichannel_window_empty_segments(monkeypatch):
    model = _FakeModel(in_samples=4)
    _install_fake_seisbench(monkeypatch, model)
    predictor = SeisBenchPredictor(SeisBenchConfig())

    assert predictor._build_multichannel_window([], [], 100.0) is None


def test_build_multichannel_window_alignment_padding(monkeypatch):
    model = _FakeModel(in_samples=4)
    _install_fake_seisbench(monkeypatch, model)
    predictor = SeisBenchPredictor(SeisBenchConfig())

    segments = [
        {"samples": np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32), "end": 4.0},
        {"samples": np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float32), "end": 5.0},
    ]
    channels = ["XX.STA..HHZ", "XX.STA..HHN"]
    window, common_end = predictor._build_multichannel_window(segments, channels, 1.0)

    assert common_end == 4.0
    assert window.shape == (2, 4)
    np.testing.assert_array_equal(
        window[0], np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
    )
    np.testing.assert_array_equal(
        window[1], np.array([0.0, 10.0, 20.0, 30.0], dtype=np.float32)
    )


def test_build_stream_sets_trace_metadata(monkeypatch):
    model = _FakeModel(in_samples=2)
    _install_fake_seisbench(monkeypatch, model)
    predictor = SeisBenchPredictor(SeisBenchConfig())

    window = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    channels = ["XX.STA..HHZ", "XX.STA..HHN"]
    stream = predictor._build_stream(window, channels, window_end=10.0, samprate=1.0)

    assert len(stream) == 2
    assert stream[0].stats.network == "XX"
    assert stream[0].stats.station == "STA"
    assert stream[0].stats.location == ""
    assert stream[0].stats.channel == "HHZ"
    assert float(stream[0].stats.starttime.timestamp) == 8.0
    assert stream[1].stats.channel == "HHN"


def test_predict_multichannel_no_segments_returns_empty(monkeypatch):
    model = _FakeModel(in_samples=4)
    _install_fake_seisbench(monkeypatch, model)
    predictor = SeisBenchPredictor(SeisBenchConfig())

    picks, detections = predictor.predict_multichannel([], [], samprate=100.0)

    assert picks == []
    assert detections == []
    assert model.classify_calls == 0


def test_predict_multichannel_filters_and_sorts_results(monkeypatch):
    pick_valid_s = SimpleNamespace(
        phase="s",
        peak_time=SimpleNamespace(timestamp=30.0),
        peak_value=0.2,
    )
    pick_invalid_phase = SimpleNamespace(
        phase="X",
        peak_time=SimpleNamespace(timestamp=20.0),
        peak_value=0.9,
    )
    pick_valid_p = SimpleNamespace(
        phase="P",
        start_time=SimpleNamespace(timestamp=10.0),
        peak_value=None,
    )
    pick_missing_time = SimpleNamespace(phase="P", peak_value=0.5)

    det_valid_late = SimpleNamespace(
        start_time=SimpleNamespace(timestamp=15.0),
        end_time=SimpleNamespace(timestamp=16.0),
    )
    det_invalid = SimpleNamespace(
        start_time=SimpleNamespace(timestamp=9.0), end_time=None
    )
    det_valid_early = SimpleNamespace(
        start_time=SimpleNamespace(timestamp=5.0),
        end_time=SimpleNamespace(timestamp=6.0),
    )

    result = SimpleNamespace(
        picks=[pick_valid_s, pick_invalid_phase, pick_valid_p, pick_missing_time],
        detections=[det_valid_late, det_invalid, det_valid_early],
    )
    model = _FakeModel(in_samples=4, classify_result=result)
    _install_fake_seisbench(monkeypatch, model)
    predictor = SeisBenchPredictor(SeisBenchConfig())

    segments = [
        {"samples": np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32), "end": 4.0}
    ]
    channels = ["XX.STA..HHZ"]

    picks, detections = predictor.predict_multichannel(segments, channels, samprate=1.0)

    assert picks == [(10.0, "P", None), (30.0, "S", 0.2)]
    assert detections == [(5.0, 6.0), (15.0, 16.0)]
    assert model.classify_calls == 1
