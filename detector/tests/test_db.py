from datetime import datetime, timezone
from types import SimpleNamespace

from detector import db as db_mod


class _FakeCursor:
    def __init__(self):
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True


class _FakeConn:
    def __init__(self):
        self.cursor_obj = _FakeCursor()

    def cursor(self):
        return self.cursor_obj


def test_connect_returns_connections(monkeypatch):
    captured = {}

    def fake_connect(host, port, user, password, dbname):
        captured.update(
            {
                "host": host,
                "port": port,
                "user": user,
                "password": password,
                "dbname": dbname,
            }
        )
        return _FakeConn()

    def fake_settings():
        return SimpleNamespace(
            pg_host="db.local",
            pg_port=15432,
            pg_user="tester",
            pg_password="secret",
            pg_dbname="events",
        )

    monkeypatch.setattr(db_mod, "Settings", fake_settings)
    monkeypatch.setattr(db_mod.psycopg2, "connect", fake_connect)
    conn = db_mod.connect(db_mod.Settings())
    assert isinstance(conn, _FakeConn)
    assert captured == {
        "host": "db.local",
        "port": 15432,
        "user": "tester",
        "password": "secret",
        "dbname": "events",
    }
    assert conn.autocommit is True


def test_insert_picks_calls_execute_values(monkeypatch):
    calls = {}

    def fake_execute_values(cur, sql, rows):
        calls["sql"] = sql
        calls["rows"] = rows

    monkeypatch.setattr(db_mod, "execute_values", fake_execute_values)

    conn = _FakeConn()
    picks = [(100.0, 101.0), (200.0, 201.0)]
    db_mod.insert_event_detections(conn, "XX.STA..HHZ", picks)

    assert "INSERT INTO event_detections" in calls["sql"]
    assert "ON CONFLICT" in calls["sql"]
    assert len(calls["rows"]) == 2
    ts_on, ts_off, net, sta, loc, chan = calls["rows"][0]
    assert net == "XX"
    assert sta == "STA"
    assert loc == ""
    assert chan == "HHZ"
    assert isinstance(ts_on, datetime)
    assert isinstance(ts_off, datetime)
    assert ts_on.tzinfo == timezone.utc


def test_insert_event_detections_leaves_duplicates_for_db(monkeypatch):
    calls = {}

    def fake_execute_values(cur, sql, rows):
        calls["sql"] = sql
        calls["rows"] = rows

    monkeypatch.setattr(db_mod, "execute_values", fake_execute_values)

    conn = _FakeConn()
    detections = [(100.0, 101.0), (100.0, 101.0)]
    db_mod.insert_event_detections(conn, "XX.STA..HHZ", detections)

    assert "ON CONFLICT DO NOTHING" in calls["sql"]
    assert len(calls["rows"]) == 2


def test_insert_event_detections_invalid_sid_no_call(monkeypatch):
    called = False

    def fake_execute_values(cur, sql, rows):
        nonlocal called
        called = True

    monkeypatch.setattr(db_mod, "execute_values", fake_execute_values)

    conn = _FakeConn()
    db_mod.insert_event_detections(conn, "BAD", [(100.0, 101.0)])

    assert called is False


def test_insert_event_detections_empty_no_call(monkeypatch):
    called = False

    def fake_execute_values(cur, sql, rows):
        nonlocal called
        called = True

    monkeypatch.setattr(db_mod, "execute_values", fake_execute_values)

    conn = _FakeConn()
    db_mod.insert_event_detections(conn, "XX.STA..HHZ", [])

    assert called is False


def test_insert_phase_picks_calls_execute_values(monkeypatch):
    calls = {}

    def fake_execute_values(cur, sql, rows):
        calls["sql"] = sql
        calls["rows"] = rows

    monkeypatch.setattr(db_mod, "execute_values", fake_execute_values)

    conn = _FakeConn()
    picks = [(100.0, "P", 0.9), (101.0, "S", None)]
    db_mod.insert_phase_picks(conn, "XX.STA..HHZ", picks)

    assert "INSERT INTO phase_picks" in calls["sql"]
    assert "ON CONFLICT DO NOTHING" in calls["sql"]
    assert len(calls["rows"]) == 2
    ts, phase, score, net, sta, loc, chan = calls["rows"][0]
    assert isinstance(ts, datetime)
    assert ts.tzinfo == timezone.utc
    assert phase == "P"
    assert score == 0.9
    assert (net, sta, loc, chan) == ("XX", "STA", "", "HHZ")


def test_insert_phase_picks_without_score_sets_none(monkeypatch):
    calls = {}

    def fake_execute_values(cur, sql, rows):
        calls["rows"] = rows

    monkeypatch.setattr(db_mod, "execute_values", fake_execute_values)

    conn = _FakeConn()
    db_mod.insert_phase_picks(conn, "XX.STA..HHZ", [(100.0, "P")])

    assert len(calls["rows"]) == 1
    _ts, _phase, score, _net, _sta, _loc, _chan = calls["rows"][0]
    assert score is None


def test_insert_empty_phase_picks(monkeypatch):
    called = False

    def fake_execute_values(cur, sql, rows):
        nonlocal called
        called = True

    monkeypatch.setattr(db_mod, "execute_values", fake_execute_values)

    conn = _FakeConn()
    db_mod.insert_phase_picks(conn, "XX.STA..HHZ", [])

    assert called is False


def test_insert_phase_picks_invalid_sid_no_call(monkeypatch):
    called = False

    def fake_execute_values(cur, sql, rows):
        nonlocal called
        called = True

    monkeypatch.setattr(db_mod, "execute_values", fake_execute_values)

    conn = _FakeConn()
    db_mod.insert_phase_picks(conn, "BAD", [(100.0, "P", 0.9)])

    assert called is False
