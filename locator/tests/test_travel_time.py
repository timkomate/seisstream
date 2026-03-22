from __future__ import annotations

from pathlib import Path

import pytest

from locator.models import Station
from locator.travel_time import ConstantVelocityTravelTime, TauPTravelTime


def _station() -> Station:
    return Station("XX", "TEST", "", 47.60, 19.20, 0.0)


def test_constant_velocity_predict_p() -> None:
    model = ConstantVelocityTravelTime(vp_km_s=6.0, vs_km_s=3.5)

    tt = model.predict(47.50, 19.05, _station(), depth_km=8.0, phase="P")

    assert tt > 0.0


def test_constant_velocity_predict_s_is_slower_than_p() -> None:
    model = ConstantVelocityTravelTime(vp_km_s=6.0, vs_km_s=3.5)
    station = _station()

    tt_p = model.predict(47.50, 19.05, station, depth_km=8.0, phase="P")
    tt_s = model.predict(47.50, 19.05, station, depth_km=8.0, phase="S")

    assert tt_s > tt_p


def test_constant_velocity_rejects_unknown_phase() -> None:
    model = ConstantVelocityTravelTime(vp_km_s=6.0, vs_km_s=3.5)

    with pytest.raises(ValueError, match="Unsupported phase"):
        model.predict(47.50, 19.05, _station(), depth_km=8.0, phase="X")


def test_taup_builtin_model_predicts_p_and_s() -> None:
    model = TauPTravelTime(
        model="iasp91",
        p_phases=["P", "p"],
        s_phases=["S", "s"],
    )
    station = _station()

    tt_p = model.predict(47.50, 19.05, station, depth_km=8.0, phase="P")
    tt_s = model.predict(47.50, 19.05, station, depth_km=8.0, phase="S")

    assert tt_p > 0.0
    assert tt_s > tt_p


def test_taup_custom_model_predicts_p() -> None:
    model_path = (
        Path(__file__).resolve().parents[1] / "models" / "graczer_weber_prem_hybrid.npz"
    )
    model = TauPTravelTime(
        model=str(model_path),
        p_phases=["P", "p"],
        s_phases=["S", "s"],
    )

    tt = model.predict(47.50, 19.05, _station(), depth_km=8.0, phase="P")

    assert tt > 0.0


def test_taup_rejects_unknown_phase() -> None:
    model = TauPTravelTime(
        model="iasp91",
        p_phases=["P", "p"],
        s_phases=["S", "s"],
    )

    with pytest.raises(ValueError, match="Unsupported phase"):
        model.predict(47.50, 19.05, _station(), depth_km=8.0, phase="X")
