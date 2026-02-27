from __future__ import annotations

import sys

from locator.settings import parse_args


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["locator"])
    settings = parse_args()
    assert settings.poll_seconds == 5.0
    assert settings.lookback_seconds == 600
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
    assert settings.log_level == "DEBUG"
    assert settings.pg_dbname == "customdb"
