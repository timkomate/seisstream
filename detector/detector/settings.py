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
    preprocess_fmin: float = 0.1
    preprocess_fmax: float = 10.0
    sta_seconds: float = 6.0
    lta_seconds: float = 20.0
    trigger_on: float = 2.5
    trigger_off: float = 0.5
    pick_filter_seconds: float = 2.0
    detector_mode: str = "sta_lta"
    eqt_model_path: str = ""
    eqt_detection_threshold: float = 0.3
    eqt_norm_mode: str = "std"
    eqt_window_samples: int = 6000
    log_level: str = "INFO"
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_user: str = "seis"
    pg_password: str = "seis"
    pg_dbname: str = "seismic"


def parse_args() -> Settings:
    parser = argparse.ArgumentParser(description="Detection consumer")
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
    parser.add_argument("--preprocess-fmin", type=float, default=0.1,
                        help="Preprocess bandpass low corner frequency (Hz)")
    parser.add_argument("--preprocess-fmax", type=float, default=10.0,
                        help="Preprocess bandpass high corner frequency (Hz)")
    parser.add_argument("--sta-seconds", type=float, default=6.0,
                        help="STA window length in seconds")
    parser.add_argument("--lta-seconds", type=float, default=20.0,
                        help="LTA window length in seconds")
    parser.add_argument("--trigger-on", type=float, default=2.5,
                        help="Trigger-on threshold for STA/LTA")
    parser.add_argument("--trigger-off", type=float, default=0.5,
                        help="Trigger-off threshold for STA/LTA")
    parser.add_argument("--pick-filter-seconds", type=float, default=2.0,
                        help="Filter picks within N seconds of the previous pick")
    parser.add_argument("--detector-mode", default="sta_lta",
                        help="Detector mode: sta_lta or eqt")
    parser.add_argument("--eqt-model-path", default="",
                        help="Path to EQTransformer .h5 model")
    parser.add_argument("--eqt-detection-threshold", type=float, default=0.3,
                        help="EQT detection threshold")
    parser.add_argument("--eqt-norm-mode", default="std",
                        help="EQT normalization mode: std or max")
    parser.add_argument("--eqt-window-samples", type=int, default=6000,
                        help="EQT window length in samples")
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
        preprocess_fmin=args.preprocess_fmin,
        preprocess_fmax=args.preprocess_fmax,
        sta_seconds=args.sta_seconds,
        lta_seconds=args.lta_seconds,
        trigger_on=args.trigger_on,
        trigger_off=args.trigger_off,
        pick_filter_seconds=args.pick_filter_seconds,
        detector_mode=args.detector_mode,
        eqt_model_path=args.eqt_model_path,
        eqt_detection_threshold=args.eqt_detection_threshold,
        eqt_norm_mode=args.eqt_norm_mode,
        eqt_window_samples=args.eqt_window_samples,
        log_level=args.log_level.upper(),
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
        pg_dbname=args.pg_db,
    )
