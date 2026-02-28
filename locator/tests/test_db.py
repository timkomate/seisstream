from datetime import datetime, timezone

from locator.db import (
    fetch_picks_since,
    fetch_recent_picks,
    fetch_stations,
    replace_origin_arrivals,
    set_origin_final,
    upsert_origin,
)
from locator.models import ArrivalResidual, OriginEstimate, Pick


class _FakeCursor:
    def __init__(self, fetchall_rows=None, fetchone_rows=None):
        self._fetchall_rows = fetchall_rows if fetchall_rows is not None else []
        self._fetchone_rows = fetchone_rows if fetchone_rows is not None else []
        self.last_query = None
        self.last_params = None
        self.executed: list[tuple[str, tuple | None]] = []

    def execute(self, query, params=None):
        self.last_query = query
        self.last_params = params
        self.executed.append((query, params))

    def fetchall(self):
        return self._fetchall_rows

    def fetchone(self):
        if not self._fetchone_rows:
            return None
        return self._fetchone_rows.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, fetchall_rows=None, fetchone_rows=None):
        self.cursor_obj = _FakeCursor(fetchall_rows, fetchone_rows)

    def cursor(self):
        return self.cursor_obj


def test_fetch_stations_maps_by_station_key() -> None:
    conn = _FakeConn(
        fetchall_rows=[
            ("AA", "STA1", "", 47.5, 19.0, 120.0),
            ("AA", "STA2", "01", 47.6, 19.2, 150.0),
        ]
    )
    stations = fetch_stations(conn)
    assert len(stations) == 2
    assert ("AA", "STA1", "") in stations
    assert stations[("AA", "STA2", "01")].lat == 47.6


def test_fetch_recent_picks_maps_rows() -> None:
    now = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    conn = _FakeConn(
        fetchall_rows=[
            (1, now, "P", "AA", "STA1", "", "HHZ", 0.8),
            (2, now, "P", "AA", "STA2", "", "EHZ", None),
        ]
    )

    picks = fetch_recent_picks(conn, lookback_seconds=600)

    assert len(picks) == 2
    assert picks[0].id == 1
    assert picks[1].chan == "EHZ"
    assert picks[1].score is None
    assert len(conn.cursor_obj.last_params) == 1
    assert isinstance(conn.cursor_obj.last_params[0], datetime)
    assert conn.cursor_obj.last_params[0].tzinfo is not None
    assert "UPPER(p.phase) = 'P'" in conn.cursor_obj.last_query


def test_fetch_picks_since_uses_strictly_newer_timestamp() -> None:
    since_ts = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    conn = _FakeConn(fetchall_rows=[(3, since_ts, "P", "AA", "STA3", "", "HHZ", 0.6)])

    picks = fetch_picks_since(conn, since_ts=since_ts)

    assert len(picks) == 1
    assert picks[0].id == 3
    assert conn.cursor_obj.last_params == (since_ts,)
    assert "p.ts > %s" in conn.cursor_obj.last_query


def test_upsert_origin_returns_origin_id() -> None:
    now = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    pick = Pick(1, now, "P", "AA", "STA1", "", "HHZ", 0.9)
    estimate = OriginEstimate(
        association_key="abc123",
        origin_ts=now,
        lat=47.5,
        lon=19.0,
        depth_km=8.0,
        rms_seconds=0.25,
        azimuthal_gap_deg=180.0,
        used_stations=1,
        arrivals=[
            ArrivalResidual(
                pick=pick,
                distance_km=10.0,
                azimuth_deg=90.0,
                predicted_tt_seconds=2.0,
                residual_seconds=0.1,
            )
        ],
    )
    conn = _FakeConn(fetchone_rows=[(42,)])

    origin_id = upsert_origin(conn, estimate)

    assert origin_id == 42
    assert "ON CONFLICT (association_key)" in conn.cursor_obj.last_query
    assert conn.cursor_obj.last_params[-1] == "abc123"


def test_replace_origin_arrivals_deletes_then_inserts() -> None:
    now = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    pick1 = Pick(1, now, "P", "AA", "STA1", "", "HHZ", 0.9)
    pick2 = Pick(2, now, "P", "AA", "STA2", "", "HHZ", 0.8)
    estimate = OriginEstimate(
        association_key="abc123",
        origin_ts=now,
        lat=47.5,
        lon=19.0,
        depth_km=8.0,
        rms_seconds=0.25,
        azimuthal_gap_deg=180.0,
        used_stations=2,
        arrivals=[
            ArrivalResidual(
                pick=pick1,
                distance_km=10.0,
                azimuth_deg=90.0,
                predicted_tt_seconds=2.0,
                residual_seconds=0.1,
            ),
            ArrivalResidual(
                pick=pick2,
                distance_km=12.0,
                azimuth_deg=120.0,
                predicted_tt_seconds=2.3,
                residual_seconds=-0.2,
            ),
        ],
    )
    conn = _FakeConn()

    replace_origin_arrivals(conn, origin_id=7, estimate=estimate)

    assert len(conn.cursor_obj.executed) == 3
    assert "DELETE FROM origin_arrivals" in conn.cursor_obj.executed[0][0]
    assert conn.cursor_obj.executed[0][1] == (7,)
    assert "INSERT INTO origin_arrivals" in conn.cursor_obj.executed[1][0]
    assert conn.cursor_obj.executed[1][1][0] == 7
    assert conn.cursor_obj.executed[1][1][1] == 1
    assert conn.cursor_obj.executed[2][1][1] == 2


def test_set_origin_final_returns_true_when_row_updated() -> None:
    conn = _FakeConn(fetchone_rows=[(7,)])

    ok = set_origin_final(conn, origin_id=7)

    assert ok is True
    assert "SET status = 'final'" in conn.cursor_obj.last_query
    assert conn.cursor_obj.last_params == (7,)


def test_set_origin_final_returns_false_when_origin_missing() -> None:
    conn = _FakeConn(fetchone_rows=[])

    ok = set_origin_final(conn, origin_id=9999)

    assert ok is False
