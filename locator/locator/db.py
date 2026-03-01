from datetime import datetime, timedelta, timezone

from .models import OriginEstimate, Pick, Station
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


def upsert_origin(conn, estimate: OriginEstimate) -> int:
    query = """
        INSERT INTO origins (
            origin_ts,
            lat,
            lon,
            depth_km,
            rms_seconds,
            gap_deg,
            n_picks,
            n_stations,
            status,
            association_key
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'preliminary', %s)
        ON CONFLICT (association_key)
        DO UPDATE SET
            origin_ts = EXCLUDED.origin_ts,
            lat = EXCLUDED.lat,
            lon = EXCLUDED.lon,
            depth_km = EXCLUDED.depth_km,
            rms_seconds = EXCLUDED.rms_seconds,
            gap_deg = EXCLUDED.gap_deg,
            n_picks = EXCLUDED.n_picks,
            n_stations = EXCLUDED.n_stations,
            updated_at = now()
        RETURNING id
    """
    params = (
        estimate.origin_ts,
        estimate.lat,
        estimate.lon,
        estimate.depth_km,
        estimate.rms_seconds,
        estimate.azimuthal_gap_deg,
        len(estimate.arrivals),
        estimate.used_stations,
        estimate.association_key,
    )
    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
    return int(row[0])


def replace_origin_arrivals(conn, origin_id: int, estimate: OriginEstimate) -> None:
    delete_query = "DELETE FROM origin_arrivals WHERE origin_id = %s"
    insert_query = """
        INSERT INTO origin_arrivals (
            origin_id,
            phase_pick_id,
            phase,
            ts,
            net,
            sta,
            loc,
            chan,
            tt_pred_seconds,
            residual_seconds,
            distance_km,
            azimuth_deg
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    with conn.cursor() as cur:
        cur.execute(delete_query, (origin_id,))
        for arr in estimate.arrivals:
            cur.execute(
                insert_query,
                (
                    origin_id,
                    arr.pick.id,
                    arr.pick.phase,
                    arr.pick.ts,
                    arr.pick.net,
                    arr.pick.sta,
                    arr.pick.loc,
                    arr.pick.chan,
                    arr.predicted_tt_seconds,
                    arr.residual_seconds,
                    arr.distance_km,
                    arr.azimuth_deg,
                ),
            )


def set_origin_final(conn, origin_id: int) -> bool:
    query = """
        UPDATE origins
        SET status = 'final',
            updated_at = now()
        WHERE id = %s
        RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(query, (origin_id,))
        row = cur.fetchone()
    return row is not None


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
