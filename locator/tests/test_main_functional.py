import logging
from datetime import datetime, timedelta, timezone

import main as locator_main
from locator.models import Pick, Station
from locator.settings import Settings


class _DummyConn:
    pass


def test_run_cycle_persists_a_solved_event(monkeypatch) -> None:
    conn = _DummyConn()
    settings = Settings(
        lookback_seconds=600,
        association_window_seconds=5.0,
        min_stations=4,
        min_pick_score=0.0,
        vp_km_s=6.0,
        max_residual_seconds=5.0,
    )
    logger = logging.getLogger("test.locator.main")

    origin_t = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    origin_lat = 47.5
    origin_lon = 19.05
    origin_depth = 8.0

    stations = {
        ("AA", "STA1", ""): Station("AA", "STA1", "", 47.60, 19.05, 0.0),
        ("AA", "STA2", ""): Station("AA", "STA2", "", 47.50, 19.20, 0.0),
        ("AA", "STA3", ""): Station("AA", "STA3", "", 47.38, 18.98, 0.0),
        ("AA", "STA4", ""): Station("AA", "STA4", "", 47.57, 18.90, 0.0),
    }

    def _make_pick(pid: int, net: str, sta: str, ts: datetime) -> Pick:
        return Pick(
            id=pid,
            ts=ts,
            phase="P",
            net=net,
            sta=sta,
            loc="",
            chan="HHZ",
            score=0.9,
        )

    # Synthetic arrivals computed from the same model used by solver.
    from locator.geometry import compute_travel_time, haversine_distance

    picks: list[Pick] = []
    for i, (key, station) in enumerate(stations.items(), start=1):
        dist = haversine_distance(origin_lat, origin_lon, station.lat, station.lon)
        tt = compute_travel_time(dist, origin_depth, settings.vp_km_s)
        picks.append(_make_pick(i, key[0], key[1], origin_t + timedelta(seconds=tt)))

    persisted = {"origin_ids": [], "estimates": []}

    def _fake_fetch_recent_picks(_conn, lookback_seconds: int):
        assert lookback_seconds == 600
        return picks

    def _fake_upsert_origin(_conn, estimate):
        persisted["origin_ids"].append(101)
        persisted["estimates"].append(estimate)
        return 101

    def _fake_replace_origin_arrivals(_conn, origin_id: int, estimate):
        assert origin_id == 101
        assert len(estimate.arrivals) == 4

    monkeypatch.setattr("main.fetch_recent_picks", _fake_fetch_recent_picks)
    monkeypatch.setattr("main.upsert_origin", _fake_upsert_origin)
    monkeypatch.setattr(
        "main.replace_origin_arrivals",
        _fake_replace_origin_arrivals,
    )

    updated_stations, metrics = locator_main.run_cycle(conn, settings, stations, logger)

    assert updated_stations == stations
    assert metrics["picks"] == 4
    assert metrics["events"] == 1
    assert metrics["solved"] == 1
    assert persisted["origin_ids"] == [101]
    assert len(persisted["estimates"]) == 1
