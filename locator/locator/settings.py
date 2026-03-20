import argparse
from dataclasses import dataclass


@dataclass
class Settings:
    poll_seconds: float = 5.0
    lookback_seconds: int = 600
    association_window_seconds: float = 45
    min_stations: int = 4
    min_pick_score: float = 0.0
    vp_km_s: float = 6.0
    vs_km_s: float = 3.5
    travel_time_model: str = "constant"
    taup_model: str = "iasp91"
    taup_p_phases: tuple[str, ...] = ("P", "p")
    taup_s_phases: tuple[str, ...] = ("S", "s")
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
    parser.add_argument("--lookback-seconds", type=int, default=600)
    parser.add_argument("--association-window-seconds", type=float, default=8.0)
    parser.add_argument("--min-stations", type=int, default=4)
    parser.add_argument("--min-pick-score", type=float, default=0.0)
    parser.add_argument("--vp-km-s", type=float, default=6.0)
    parser.add_argument("--vs-km-s", type=float, default=3.5)
    parser.add_argument(
        "--travel-time-model",
        choices=("constant", "taup"),
        default="constant",
    )
    parser.add_argument("--taup-model", default="iasp91")
    parser.add_argument("--taup-p-phases", default="P,p")
    parser.add_argument("--taup-s-phases", default="S,s")
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
        lookback_seconds=args.lookback_seconds,
        association_window_seconds=args.association_window_seconds,
        min_stations=args.min_stations,
        min_pick_score=args.min_pick_score,
        vp_km_s=args.vp_km_s,
        vs_km_s=args.vs_km_s,
        travel_time_model=args.travel_time_model,
        taup_model=args.taup_model,
        taup_p_phases=_parse_phase_list(args.taup_p_phases),
        taup_s_phases=_parse_phase_list(args.taup_s_phases),
        max_residual_seconds=args.max_residual_seconds,
        log_level=args.log_level.upper(),
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
        pg_dbname=args.pg_db,
    )


def _parse_phase_list(value: str) -> tuple[str, ...]:
    phases = tuple(item.strip() for item in value.split(",") if item.strip())
    if not phases:
        raise ValueError("Phase list must contain at least one phase")
    return phases
