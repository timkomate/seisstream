import numpy as np
import pytest

from detector.signal import bandpass_filter, preprocess_trace, taper_cosine


def test_taper_cosine_empty_input():
    out = taper_cosine([], frac=0.1)
    assert isinstance(out, np.ndarray)
    assert out.size == 0


def test_taper_cosine_nonpositive_frac_returns_copy():
    y = np.array([1.0, 2.0, 3.0])
    out = taper_cosine(y, frac=0.0)
    np.testing.assert_array_equal(out, y)
    assert out is not y


def test_taper_cosine_tiny_frac_no_taper_returns_copy():
    y = np.array([1.0, 2.0, 3.0])
    out = taper_cosine(y, frac=0.01)
    np.testing.assert_array_equal(out, y)
    assert out is not y


def test_bandpass_filter_invalid_frequencies_raise():
    y = np.ones(100, dtype=float)
    with pytest.raises(ValueError):
        bandpass_filter(y, fs=20.0, fmin=0.1, fmax=10.0)


def test_bandpass_filter_non_zero_phase_path():
    fs = 50.0
    t = np.arange(0, 4, 1 / fs)
    y = np.sin(2 * np.pi * 2.0 * t)
    out = bandpass_filter(y, fs=fs, fmin=0.5, fmax=8.0, zero_phase=False)
    assert out.shape == y.shape
    assert np.isfinite(out).all()


def test_preprocess_trace_end_to_end_shape():
    fs = 50.0
    t = np.arange(0, 4, 1 / fs)
    y = np.sin(2 * np.pi * 2.0 * t) + 0.1 * np.sin(2 * np.pi * 15.0 * t)
    out = preprocess_trace(y, fs=fs, fmin=0.5, fmax=8.0, taper_frac=0.1)
    assert out.shape == y.shape
    assert np.isfinite(out).all()
