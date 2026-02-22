from detector.picks import filter_phase_picks, filter_picks


def test_filter_empty_picks():
    last_ts_on = 100.0
    picks = []
    filtered, new_last = filter_picks(picks, last_ts_on, 0.0)
    assert filtered == []
    assert new_last == 100.0


def test_filter_picks_discards_nearby():
    last_ts_on = 100.0
    picks = [(100.4, 110.0), (103.0, 104.0)]
    filtered, new_last = filter_picks(picks, last_ts_on, 0.5)
    assert filtered == [(103.0, 104.0)]
    assert new_last == 103.0


def test_filter_picks_keeps_distinct():
    last_ts_on = 100.0
    picks = [(101.0, 102.0)]
    filtered, _ = filter_picks(picks, last_ts_on, 0.5)
    assert filtered == [(101.0, 102.0)]


def test_filter_picks_ignores_ts_off():
    last_ts_on = 100.0
    picks = [(101.0, 1000.0)]
    filtered, _ = filter_picks(picks, last_ts_on, 0.5)
    assert filtered == [(101.0, 1000.0)]


def test_filter_picks_zero_window():
    last_ts_on = 100.0
    picks = [(100.0, 101.0), (101.0, 102.0)]
    filtered, _ = filter_picks(picks, last_ts_on, 0.0)
    assert filtered == picks


def test_filter_picks_zero_window_keeps_newer_last_ts_on():
    last_ts_on = 200.0
    picks = [(100.0, 101.0), (150.0, 151.0)]
    filtered, new_last = filter_picks(picks, last_ts_on, 0.0)
    assert filtered == picks
    assert new_last == 200.0


def test_filter_picks_updates_latest():
    filtered, new_last = filter_picks([(200.0, 201.0)], None, 0.5)
    assert filtered == [(200.0, 201.0)]
    assert new_last == 200.0


def test_filter_picks_out_of_order():
    last_ts_on = 100.0
    picks = [(103.0, 104.0), (100.2, 101.0)]
    filtered, new_last = filter_picks(picks, last_ts_on, 0.5)
    assert filtered == [(103.0, 104.0)]
    assert new_last == 103.0


def test_filter_phase_picks_discards_nearby():
    last_ts_on = 100.0
    picks = [(100.3, "P", 0.9), (103.0, "S", 0.7)]
    filtered, new_last = filter_phase_picks(picks, last_ts_on, 0.5)
    assert filtered == [(103.0, "S", 0.7)]
    assert new_last == 103.0


def test_filter_phase_picks_zero_window_keeps_all_sorted():
    last_ts_on = 100.0
    picks = [(101.0, "S", 0.8), (100.5, "P", 0.9)]
    filtered, new_last = filter_phase_picks(picks, last_ts_on, 0.0)
    assert filtered == [(100.5, "P", 0.9), (101.0, "S", 0.8)]
    assert new_last == 101.0


def test_filter_phase_picks_empty_returns_last():
    filtered, new_last = filter_phase_picks([], 200.0, 1.0)
    assert filtered == []
    assert new_last == 200.0
