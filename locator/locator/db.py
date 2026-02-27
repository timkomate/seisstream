from datetime import datetime, timedelta, timezone

from .models import Pick, Station
from .settings import Settings


def connect(settings: Settings):
    import psycopg2

    conn = psycopg2.connect(
        host=settings.pg_host,
        port=settings.pg_port,
        user=settings.pg_user,
        password=settings.pg_password,
        dbname=settings.pg_dbname,
    )
    conn.autocommit = True
    return conn


def fetch_stations(conn) -> dict[tuple[str, str, str], Station]:
    with conn.cursor() as cur:
        cur.execute("SELECT net, sta, loc, lat, lon, elev_m FROM stations")
        rows = cur.fetchall()

    out: dict[tuple[str, str, str], Station] = {}
    for net, sta, loc, lat, lon, elev_m in rows:
        station = Station(net=net, sta=sta, loc=loc, lat=lat, lon=lon, elev_m=elev_m)
        out[station.station_key] = station
    return out


def fetch_recent_picks(
    conn,
    lookback_seconds: int,
) -> list[Pick]:
    now = datetime.now(tz=timezone.utc)
    start_ts = now - timedelta(seconds=lookback_seconds)

    query = """
        SELECT p.id, p.ts, p.phase, p.net, p.sta, p.loc, p.chan, p.score
        FROM phase_picks p
        WHERE p.ts >= %s
          AND UPPER(p.phase) = 'P'
        ORDER BY p.ts ASC
    """

    with conn.cursor() as cur:
        cur.execute(query, (start_ts,))
        rows = cur.fetchall()

    return _rows_to_picks(rows)


def fetch_picks_since(
    conn,
    since_ts: datetime,
) -> list[Pick]:
    if since_ts.tzinfo is None:
        raise ValueError("since_ts must be timezone-aware (UTC)")

    query = """
        SELECT p.id, p.ts, p.phase, p.net, p.sta, p.loc, p.chan, p.score
        FROM phase_picks p
        WHERE p.ts > %s
          AND UPPER(p.phase) = 'P'
        ORDER BY p.ts ASC
    """

    with conn.cursor() as cur:
        cur.execute(query, (since_ts,))
        rows = cur.fetchall()

    return _rows_to_picks(rows)


def _rows_to_picks(rows) -> list[Pick]:
    picks: list[Pick] = []
    for row in rows:
        pick = Pick(
            id=row[0],
            ts=row[1],
            phase=row[2],
            net=row[3],
            sta=row[4],
            loc=row[5],
            chan=row[6],
            score=row[7],
        )
        picks.append(pick)
    return picks
