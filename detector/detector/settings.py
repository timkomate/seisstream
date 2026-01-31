from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import List


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 5672
    user: str = "guest"
    password: str = "guest"
    vhost: str = "/"
    exchange: str = "stations"
    queue: str = ""
    binding_keys: List[str] = field(default_factory=lambda: ["#"])
    prefetch: int = 50
    buffer_seconds: float = 120.0
    detect_every_seconds: float = 15.0
    pick_filter_seconds: float = 2.0
    log_level: str = "INFO"
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_user: str = "seis"
    pg_password: str = "seis"
    pg_dbname: str = "seismic"


def parse_args() -> Settings:
    parser = argparse.ArgumentParser(description="STA/LTA detection consumer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5672)
    parser.add_argument("--user", default="guest")
    parser.add_argument("--password", default="guest")
    parser.add_argument("--vhost", default="/")
    parser.add_argument("--exchange", default="stations",
                        help="Topic exchange that carries miniSEED messages")
    parser.add_argument("--queue", default="",
                        help="Queue name; leave empty for an exclusive, auto-delete queue")
    parser.add_argument("--binding-key", action="append", dest="binding_keys",
                        help="Binding key to subscribe (topic syntax). Repeatable.",
                        default=None)
    parser.add_argument("--prefetch", type=int, default=50,
                        help="QoS prefetch count")
    parser.add_argument("--buffer-seconds", type=float, default=120.0,
                        help="Seconds of data to keep per source id")
    parser.add_argument("--detect-every-seconds", type=float, default=15.0,
                        help="Run detector every N seconds per source id once the buffer is full")
    parser.add_argument("--pick-filter-seconds", type=float, default=2.0,
                        help="Filter picks within N seconds of the previous pick")
    parser.add_argument("--log-level", default="INFO",
                        help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--pg-host", default="localhost",
                        help="PostgreSQL host")
    parser.add_argument("--pg-port", type=int, default=5432,
                        help="PostgreSQL port")
    parser.add_argument("--pg-user", default="seis",
                        help="PostgreSQL user")
    parser.add_argument("--pg-password", default="seis",
                        help="PostgreSQL password")
    parser.add_argument("--pg-db", default="seismic",
                        help="PostgreSQL database name")
    args = parser.parse_args()

    binding_keys = args.binding_keys if args.binding_keys else ["#"]
    return Settings(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        vhost=args.vhost,
        exchange=args.exchange,
        queue=args.queue,
        binding_keys=binding_keys,
        prefetch=args.prefetch,
        buffer_seconds=args.buffer_seconds,
        detect_every_seconds=args.detect_every_seconds,
        pick_filter_seconds=args.pick_filter_seconds,
        log_level=args.log_level.upper(),
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
        pg_dbname=args.pg_db,
    )
