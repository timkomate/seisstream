from datetime import datetime, timezone

from locator.db import fetch_picks_since, fetch_recent_picks, fetch_stations


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.last_query = None
        self.last_params = None

    def execute(self, query, params=None):
        self.last_query = query
        self.last_params = params

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, rows):
        self.cursor_obj = _FakeCursor(rows)

    def cursor(self):
        return self.cursor_obj


def test_fetch_stations_maps_by_station_key() -> None:
    conn = _FakeConn(
        [
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
        [
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
    conn = _FakeConn([(3, since_ts, "P", "AA", "STA3", "", "HHZ", 0.6)])

    picks = fetch_picks_since(conn, since_ts=since_ts)

    assert len(picks) == 1
    assert picks[0].id == 3
    assert conn.cursor_obj.last_params == (since_ts,)
    assert "p.ts > %s" in conn.cursor_obj.last_query
