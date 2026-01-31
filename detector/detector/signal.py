from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfiltfilt


def taper_cosine(y, frac=0.05):
    y = np.asarray(y, dtype=float)
    n = y.size
    if n == 0:
        return y
    frac = float(frac)
    if frac <= 0:
        return y.copy()

    m = int(np.floor(frac * n))
    if m == 0:
        return y.copy()

    w = np.ones(n, dtype=float)
    k = np.arange(m)

    w[:m] = 0.5 * (1 - np.cos(np.pi * (k + 1) / m))
    w[-m:] = 0.5 * (1 - np.cos(np.pi * (m - k) / m))

    return y * w


def bandpass_filter(y, fs, fmin, fmax, order=4, zero_phase=True, demean=True):
    """
    Butterworth bandpass. Uses SOS for numerical stability.
    fmin/fmax in Hz.
    """
    y = np.asarray(y, dtype=float)

    if demean:
        y = y - np.nanmean(y)

    nyq = 0.5 * float(fs)
    if not (0 < fmin < fmax < nyq):
        raise ValueError(f"Require 0 < fmin < fmax < fs/2. Got fmin={fmin}, fmax={fmax}, fs={fs}.")

    sos = butter(order, [fmin / nyq, fmax / nyq], btype="bandpass", output="sos")

    if zero_phase:
        return sosfiltfilt(sos, y)
    else:
        from scipy.signal import sosfilt
        return sosfilt(sos, y)


def preprocess_trace(y, fs, fmin, fmax, taper_frac=0.05, order=4, zero_phase=True, demean=True):
    y_t = taper_cosine(y, frac=taper_frac)
    y_f = bandpass_filter(y_t, fs, fmin, fmax, order=order, zero_phase=zero_phase, demean=demean)
    return y_f
