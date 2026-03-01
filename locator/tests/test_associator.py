import hashlib
from dataclasses import replace
from datetime import datetime, timedelta, timezone, UTC

from locator.associator import associate_picks
from locator.models import Pick


def _pick(
    pid: int, ts: datetime, sta: str, phase: str = "P", score: float = 0.9
) -> Pick:
    return Pick(
        id=pid,
        ts=ts,
        phase=phase,
        net="AA",
        sta=sta,
        loc="",
        chan="HHZ",
        score=score,
    )


def test_associate_picks_single_event() -> None:
    t0 = datetime.now(UTC)
    picks = [
        _pick(1, t0 + timedelta(seconds=0.0), "STA1"),
        _pick(2, t0 + timedelta(seconds=1.0), "STA2"),
        _pick(3, t0 + timedelta(seconds=2.0), "STA3"),
        _pick(4, t0 + timedelta(seconds=3.0), "STA4"),
    ]

    events = associate_picks(picks, window_seconds=5.0, min_stations=4, min_phases=4)

    assert len(events) == 1
    assert [p.id for p in events[0].picks] == [1, 2, 3, 4]
    assert events[0].earliest_pick_time == t0
    expected = hashlib.sha256("1_2_3_4".encode("utf-8")).hexdigest()
    assert events[0].association_key == expected


def test_associate_picks_multiple_events() -> None:
    t0 = datetime.now(UTC)
    picks = [
        _pick(1, t0 + timedelta(seconds=0.0), "STA1"),
        _pick(2, t0 + timedelta(seconds=1.0), "STA2"),
        _pick(3, t0 + timedelta(seconds=2.0), "STA3"),
        _pick(4, t0 + timedelta(seconds=3.0), "STA4"),
        _pick(5, t0 + timedelta(seconds=20.0), "STA1"),
        _pick(6, t0 + timedelta(seconds=21.0), "STA2"),
        _pick(7, t0 + timedelta(seconds=22.0), "STA3"),
        _pick(8, t0 + timedelta(seconds=23.0), "STA4"),
    ]

    events = associate_picks(picks, window_seconds=5.0, min_stations=4, min_phases=4)

    assert len(events) == 2
    assert [p.id for p in events[0].picks] == [1, 2, 3, 4]
    assert [p.id for p in events[1].picks] == [5, 6, 7, 8]


def test_associate_picks_uses_first_pick_per_station() -> None:
    t0 = datetime.now(UTC)
    picks = [
        _pick(1, t0 + timedelta(seconds=0.0), "STA1"),
        _pick(2, t0 + timedelta(seconds=0.5), "STA1"),
        _pick(3, t0 + timedelta(seconds=1.0), "STA2"),
        _pick(4, t0 + timedelta(seconds=2.0), "STA3"),
        _pick(5, t0 + timedelta(seconds=3.0), "STA4"),
    ]

    events = associate_picks(picks, window_seconds=5.0, min_stations=4, min_phases=4)

    assert len(events) == 1
    assert [p.id for p in events[0].picks] == [1, 3, 4, 5]


def test_associate_picks_requires_min_phases() -> None:
    t0 = datetime.now(UTC)
    picks = [
        _pick(1, t0 + timedelta(seconds=0.0), "STA1"),
        _pick(2, t0 + timedelta(seconds=1.0), "STA2"),
        _pick(3, t0 + timedelta(seconds=2.0), "STA3"),
        _pick(4, t0 + timedelta(seconds=3.0), "STA4"),
    ]

    events = associate_picks(picks, window_seconds=5.0, min_stations=4, min_phases=5)
    assert events == []


def test_associate_picks_accepts_non_p_when_counts_match() -> None:
    t0 = datetime.now(UTC)
    picks = [
        _pick(1, t0 + timedelta(seconds=0.0), "STA1", phase="S"),
        _pick(2, t0 + timedelta(seconds=1.0), "STA2", phase="S"),
        _pick(3, t0 + timedelta(seconds=2.0), "STA3", phase="S"),
        _pick(4, t0 + timedelta(seconds=3.0), "STA4", phase="S"),
    ]

    events = associate_picks(picks, window_seconds=5.0, min_stations=4, min_phases=4)
    assert len(events) == 1


def test_associate_picks_filters_by_min_score() -> None:
    t0 = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    picks = [
        _pick(1, t0 + timedelta(seconds=0.0), "STA1", "P", 0.95),
        _pick(2, t0 + timedelta(seconds=1.0), "STA2", "P", 0.50),
        _pick(3, t0 + timedelta(seconds=2.0), "STA3", "P", 0.75),
        _pick(4, t0 + timedelta(seconds=3.0), "STA4", "P", 0.20),
    ]

    events = associate_picks(
        picks,
        window_seconds=5.0,
        min_stations=3,
        min_phases=3,
        min_score=0.4,
    )

    assert len(events) == 1
    assert [p.id for p in events[0].picks] == [1, 2, 3]


def test_associate_picks_accepts_missing_score_with_warning(caplog) -> None:
    t0 = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    picks = [
        _pick(1, t0 + timedelta(seconds=0.0), "STA1", "P", 0.95),
        _pick(2, t0 + timedelta(seconds=1.0), "STA2", "P", 0.50),
        _pick(3, t0 + timedelta(seconds=2.0), "STA3", "P", 0.75),
        _pick(4, t0 + timedelta(seconds=3.0), "STA4", "P", None),
    ]

    with caplog.at_level("WARNING"):
        events = associate_picks(
            picks,
            window_seconds=5.0,
            min_stations=3,
            min_phases=3,
            min_score=0.4,
        )

    assert len(events) == 1
    assert [p.id for p in events[0].picks] == [1, 2, 3, 4]
    assert "has no score; accepting pick despite score filter" in caplog.text
