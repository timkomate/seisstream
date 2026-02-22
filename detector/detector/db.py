from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Tuple

import psycopg2
from psycopg2.extras import execute_values

from .settings import Settings
from .utils import parse_sid


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


def insert_phase_picks(
    conn,
    sid: str,
    picks: Iterable[Tuple[float, str] | Tuple[float, str, Optional[float]]],
) -> None:
    parsed = parse_sid(sid)
    if not parsed:
        logging.warning("Unable to parse source id for phase picks: %s", sid)
        return
    net, sta, loc, chan = parsed

    rows: List[Tuple[datetime, str, Optional[float], str, str, str, str]] = []
    for pick in picks:
        t_on = pick[0]
        phase = pick[1]
        score = float(pick[2]) if len(pick) >= 3 and pick[2] is not None else None
        ts_on = datetime.fromtimestamp(t_on, tz=timezone.utc)
        row = (ts_on, phase, score, net, sta, loc, chan)
        rows.append(row)

    if not rows:
        logging.debug("No phase picks to be inserted into DB.")
        return

    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO phase_picks (ts, phase, score, net, sta, loc, chan) VALUES %s "
            "ON CONFLICT DO NOTHING",
            rows,
        )


def insert_event_detections(
    conn,
    sid: str,
    detections: Iterable[Tuple[float, float]],
) -> None:
    sql = (
        "INSERT INTO event_detections (ts_on, ts_off, net, sta, loc, chan) VALUES %s "
        "ON CONFLICT DO NOTHING"
    )

    parsed = parse_sid(sid)
    if not parsed:
        logging.warning("Unable to parse source id for event detections: %s", sid)
        return
    net, sta, loc, chan = parsed

    rows: List[Tuple[datetime, datetime, str, str, str, str]] = []
    for t_on, t_off in detections:
        ts_on = datetime.fromtimestamp(t_on, tz=timezone.utc)
        ts_off = datetime.fromtimestamp(t_off, tz=timezone.utc)
        row = (ts_on, ts_off, net, sta, loc, chan)
        rows.append(row)

    if not rows:
        logging.debug("No event detections to be inserted into DB.")
        return

    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
