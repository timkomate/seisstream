from contextlib import closing
from datetime import datetime, timedelta, timezone

import numpy as np
from obspy import Stream, Trace, UTCDateTime
import psycopg2

from viewer.models import Origin, PhasePick, Station
from viewer.settings import SETTINGS, ViewerSettings


def connect(settings: ViewerSettings = SETTINGS):
    return psycopg2.connect(
        host=settings.pg_host,
        port=settings.pg_port,
        user=settings.pg_user,
        password=settings.pg_password,
        dbname=settings.pg_dbname,
    )


def parse_station_key(value: str) -> tuple[str, str, str]:
    return tuple(value.split(".", 2))


def latest_sample_ts(settings: ViewerSettings = SETTINGS) -> datetime | None:
    with closing(connect(settings)) as conn, conn.cursor() as cur:
        cur.execute("SELECT max(ts) FROM seismic_samples")
        row = cur.fetchone()
    return row[0] if row and row[0] else None


def default_window(settings: ViewerSettings = SETTINGS) -> dict[str, str] | None:
    latest = latest_sample_ts(settings)
    if latest is None:
        return None
    start = latest - timedelta(seconds=settings.default_window_seconds)
    return {
        "start_ts": start.astimezone(timezone.utc).isoformat(),
        "end_ts": latest.astimezone(timezone.utc).isoformat(),
    }


def list_stations(settings: ViewerSettings = SETTINGS) -> list[Station]:
    query = """
        SELECT DISTINCT net, sta, loc
        FROM seismic_samples
        ORDER BY net, sta, loc
    """
    with closing(connect(settings)) as conn, conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
    return [Station(net=net, sta=sta, loc=loc) for net, sta, loc in rows]


def station_options(settings: ViewerSettings = SETTINGS) -> list[dict[str, str]]:
    return [{"label": station.key, "value": station.key} for station in list_stations(settings)]


def list_channels(settings: ViewerSettings = SETTINGS) -> list[str]:
    query = """
        SELECT DISTINCT chan
        FROM seismic_samples
        ORDER BY chan
    """
    with closing(connect(settings)) as conn, conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
    return [chan for (chan,) in rows]


def channel_options(settings: ViewerSettings = SETTINGS) -> list[dict[str, str]]:
    return [{"label": chan, "value": chan} for chan in list_channels(settings)]


def fetch_waveforms(
    station_keys: list[str],
    channels: list[str],
    start_ts: datetime,
    end_ts: datetime,
    settings: ViewerSettings = SETTINGS,
) -> Stream:
    stream = Stream()
    if not station_keys or not channels:
        return stream

    query = """
        SELECT ts, value, sample_rate
        FROM seismic_samples
        WHERE net = %s
          AND sta = %s
          AND loc = %s
          AND chan = %s
          AND ts BETWEEN %s AND %s
        ORDER BY ts ASC
    """
    with closing(connect(settings)) as conn, conn.cursor() as cur:
        for key in station_keys:
            net, sta, loc = parse_station_key(key)
            for chan in channels:
                cur.execute(query, (net, sta, loc, chan, start_ts, end_ts))
                rows = cur.fetchall()
                if not rows:
                    continue
                trace = Trace(
                    data=np.asarray([row[1] for row in rows]),
                    header={
                        "network": net,
                        "station": sta,
                        "location": loc,
                        "channel": chan,
                        "starttime": UTCDateTime(rows[0][0]),
                        "sampling_rate": float(rows[0][2]),
                    },
                )
                stream.append(trace)
    return stream


def fetch_phase_picks(
    station_keys: list[str],
    channels: list[str],
    start_ts: datetime,
    end_ts: datetime,
    settings: ViewerSettings = SETTINGS,
 ) -> list[PhasePick]:
    picks: list[PhasePick] = []
    if not station_keys or not channels:
        return picks

    query = """
        SELECT id, ts, phase, net, sta, loc, chan, method
        FROM phase_picks
        WHERE net = %s
          AND sta = %s
          AND loc = %s
          AND chan = ANY(%s)
          AND ts BETWEEN %s AND %s
        ORDER BY ts ASC
    """
    with closing(connect(settings)) as conn, conn.cursor() as cur:
        for key in station_keys:
            net, sta, loc = parse_station_key(key)
            cur.execute(query, (net, sta, loc, channels, start_ts, end_ts))
            for row in cur.fetchall():
                picks.append(
                    PhasePick(
                        id=row[0],
                        ts=row[1],
                        phase=row[2],
                        net=row[3],
                        sta=row[4],
                        loc=row[5],
                        chan=row[6],
                        method=row[7],
                    )
                )
    return picks


def fetch_origins(
    start_ts: datetime,
    end_ts: datetime,
    settings: ViewerSettings = SETTINGS,
) -> list[Origin]:
    query = """
        SELECT id, origin_ts, lat, lon, depth_km, rms_seconds, status, method, n_picks, n_stations
        FROM origins
        WHERE origin_ts BETWEEN %s AND %s
        ORDER BY origin_ts DESC
    """
    with closing(connect(settings)) as conn, conn.cursor() as cur:
        cur.execute(query, (start_ts, end_ts))
        rows = cur.fetchall()
    return [
        Origin(
            id=row[0],
            origin_ts=row[1],
            lat=row[2],
            lon=row[3],
            depth_km=row[4],
            rms_seconds=row[5],
            status=row[6],
            method=row[7],
            n_picks=row[8],
            n_stations=row[9],
        )
        for row in rows
    ]
