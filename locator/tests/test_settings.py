from __future__ import annotations

import sys

from locator.settings import parse_args


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["locator"])
    settings = parse_args()
    assert settings.poll_seconds == 5.0
    assert settings.lookback_seconds == 600
    assert settings.min_pick_score == 0.0
    assert settings.vs_km_s == 3.5
    assert settings.travel_time_model == "constant"
    assert settings.taup_model == "iasp91"
    assert settings.taup_p_phases == ("P", "p")
    assert settings.taup_s_phases == ("S", "s")
    assert settings.log_level == "INFO"
    assert settings.pg_dbname == "seismic"


def test_parse_args_overrides(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "locator",
            "--poll-seconds",
            "2.5",
            "--lookback-seconds",
            "300",
            "--min-stations",
            "3",
            "--min-pick-score",
            "0.7",
            "--vs-km-s",
            "3.2",
            "--travel-time-model",
            "taup",
            "--taup-model",
            "ak135",
            "--taup-p-phases",
            "P,p,Pn",
            "--taup-s-phases",
            "S,s,Sn",
            "--log-level",
            "debug",
            "--pg-db",
            "customdb",
        ],
    )
    settings = parse_args()
    assert settings.poll_seconds == 2.5
    assert settings.lookback_seconds == 300
    assert settings.min_stations == 3
    assert settings.min_pick_score == 0.7
    assert settings.vs_km_s == 3.2
    assert settings.travel_time_model == "taup"
    assert settings.taup_model == "ak135"
    assert settings.taup_p_phases == ("P", "p", "Pn")
    assert settings.taup_s_phases == ("S", "s", "Sn")
    assert settings.log_level == "DEBUG"
    assert settings.pg_dbname == "customdb"
