from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ViewerSettings:
    pg_host: str = os.getenv("PGHOST", "timescaledb")
    pg_port: int = int(os.getenv("PGPORT", "5432"))
    pg_user: str = os.getenv("PGUSER", "seis")
    pg_password: str = os.getenv("PGPASSWORD", "seis")
    pg_dbname: str = os.getenv("PGDATABASE", "seismic")
    default_window_seconds: int = int(os.getenv("VIEWER_DEFAULT_WINDOW_SECONDS", "60"))
    max_samples_per_trace: int = int(os.getenv("VIEWER_MAX_SAMPLES_PER_TRACE", "3000"))


SETTINGS = ViewerSettings()

