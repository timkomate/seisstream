from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from locator.geometry import compute_travel_time, haversine_distance
from locator.models import Event, Pick, Station
from locator.solver import estimate_origin


def _make_pick(pid: int, ts: datetime, net: str, sta: str, loc: str = "") -> Pick:
    return Pick(
        id=pid,
        ts=ts,
        phase="P",
        net=net,
        sta=sta,
        loc=loc,
        chan="HHZ",
        score=0.9,
    )


def test_estimate_origin_recovers_synthetic_solution() -> None:
    origin_t = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    origin_lat = 47.5
    origin_lon = 19.05
    origin_depth = 8.0
    vp = 6.0
    stations = {
        ("AA", "STA1", ""): Station("AA", "STA1", "", 47.60, 19.05, 0.0),
        ("AA", "STA2", ""): Station("AA", "STA2", "", 47.50, 19.20, 0.0),
        ("AA", "STA3", ""): Station("AA", "STA3", "", 47.38, 18.98, 0.0),
        ("AA", "STA4", ""): Station("AA", "STA4", "", 47.57, 18.90, 0.0),
    }

    picks: list[Pick] = []
    for i, (key, station) in enumerate(stations.items(), start=1):
        dist = haversine_distance(origin_lat, origin_lon, station.lat, station.lon)
        tt = compute_travel_time(dist, origin_depth, vp)
        picks.append(_make_pick(i, origin_t + timedelta(seconds=tt), key[0], key[1]))

    event = Event(
        picks=picks,
        earliest_pick_time=min(p.ts for p in picks),
        association_key="event-1",
    )

    result = estimate_origin(event, stations, vp_km_s=vp, min_stations=4)
    assert result is not None
    assert result.lat == pytest.approx(origin_lat, abs=0.03)
    assert result.lon == pytest.approx(origin_lon, abs=0.03)
    assert result.depth_km == pytest.approx(origin_depth, abs=1.5)
    assert result.origin_ts.timestamp() == pytest.approx(origin_t.timestamp(), abs=0.3)
    assert result.rms_seconds < 0.4
    assert result.used_stations == 4
    assert result.association_key == "event-1"


def test_estimate_origin_returns_none_for_insufficient_stations() -> None:
    t0 = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    stations = {
        ("AA", "STA1", ""): Station("AA", "STA1", "", 47.60, 19.05, 0.0),
        ("AA", "STA2", ""): Station("AA", "STA2", "", 47.50, 19.20, 0.0),
        ("AA", "STA3", ""): Station("AA", "STA3", "", 47.38, 18.98, 0.0),
    }
    event = Event(
        picks=[
            _make_pick(1, t0 + timedelta(seconds=1.0), "AA", "STA1"),
            _make_pick(2, t0 + timedelta(seconds=2.0), "AA", "STA2"),
            _make_pick(3, t0 + timedelta(seconds=3.0), "AA", "STA3"),
        ],
        earliest_pick_time=t0 + timedelta(seconds=1.0),
        association_key="event-2",
    )
    assert estimate_origin(event, stations, vp_km_s=6.0, min_stations=4) is None


def test_estimate_origin_returns_none_if_station_metadata_missing() -> None:
    t0 = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    stations = {
        ("AA", "STA1", ""): Station("AA", "STA1", "", 47.60, 19.05, 0.0),
        ("AA", "STA2", ""): Station("AA", "STA2", "", 47.50, 19.20, 0.0),
        ("AA", "STA3", ""): Station("AA", "STA3", "", 47.38, 18.98, 0.0),
    }
    event = Event(
        picks=[
            _make_pick(1, t0 + timedelta(seconds=1.0), "AA", "STA1"),
            _make_pick(2, t0 + timedelta(seconds=2.0), "AA", "STA2"),
            _make_pick(3, t0 + timedelta(seconds=3.0), "AA", "STA3"),
            _make_pick(4, t0 + timedelta(seconds=4.0), "AA", "STA4"),
        ],
        earliest_pick_time=t0 + timedelta(seconds=1.0),
        association_key="event-3",
    )
    assert estimate_origin(event, stations, vp_km_s=6.0, min_stations=4) is None
