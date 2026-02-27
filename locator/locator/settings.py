from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass
class Settings:
    poll_seconds: float = 5.0
    lookback_minutes: int = 10
    batch_size: int = 500
    association_window_seconds: float = 8.0
    min_stations: int = 4
    vp_km_s: float = 6.0
    max_residual_seconds: float = 3.0
    log_level: str = "INFO"
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_user: str = "seis"
    pg_password: str = "seis"
    pg_dbname: str = "seismic"


def parse_args() -> Settings:
    parser = argparse.ArgumentParser(description="Locator")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--lookback-minutes", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--association-window-seconds", type=float, default=8.0)
    parser.add_argument("--min-stations", type=int, default=4)
    parser.add_argument("--vp-km-s", type=float, default=6.0)
    parser.add_argument("--max-residual-seconds", type=float, default=3.0)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-user", default="seis")
    parser.add_argument("--pg-password", default="seis")
    parser.add_argument("--pg-db", default="seismic")
    args = parser.parse_args()

    return Settings(
        poll_seconds=args.poll_seconds,
        lookback_minutes=args.lookback_minutes,
        batch_size=args.batch_size,
        association_window_seconds=args.association_window_seconds,
        min_stations=args.min_stations,
        vp_km_s=args.vp_km_s,
        max_residual_seconds=args.max_residual_seconds,
        log_level=args.log_level.upper(),
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
        pg_dbname=args.pg_db,
    )

