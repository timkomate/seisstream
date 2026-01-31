from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Tuple

import psycopg2
from psycopg2.extras import execute_values

from .settings import Settings


def connect(settings: Settings):
    conn = psycopg2.connect(
        host=settings.pg_host,
        port=settings.pg_port,
        user=settings.pg_user,
        password=settings.pg_password,
        dbname=settings.pg_dbname,
    )
    conn.autocommit = True
    return conn


def parse_sid(sid: str) -> Optional[Tuple[str, str, str, str]]:
    if not sid:
        return None
    cleaned = sid
    if cleaned.startswith("FDSN:"):
        cleaned = cleaned[5:]
    if "_" in cleaned:
        parts = cleaned.split("_")
    elif "." in cleaned:
        parts = cleaned.split(".")
    else:
        return None
    if len(parts) < 4:
        return None
    return parts[0], parts[1], parts[2], parts[3]


def insert_picks(conn, sid: str, picks: Iterable[Tuple[float, float]]) -> None:
    parsed = parse_sid(sid)
    if not parsed:
        logging.warning("Unable to parse source id for picks: %s", sid)
        return
    net, sta, loc, chan = parsed

    rows: List[Tuple[datetime, datetime, str, str, str, str]] = []
    for t_on, t_off in picks:
        ts_on = datetime.fromtimestamp(t_on, tz=timezone.utc)
        ts_off = datetime.fromtimestamp(t_off, tz=timezone.utc)
        rows.append((ts_on, ts_off, net, sta, loc, chan))

    if not rows:
        return

    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO picks (ts_on, ts_off, net, sta, loc, chan) VALUES %s",
            rows,
        )
