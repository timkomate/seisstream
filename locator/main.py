import logging
import time

from locator.associator import associate_picks
from locator.db import (
    connect,
    fetch_recent_picks,
    fetch_stations,
    replace_origin_arrivals,
    upsert_origin,
)
from locator.settings import parse_args
from locator.solver import estimate_origin


def run_cycle(conn, settings, stations: dict, logger: logging.Logger):
    picks = fetch_recent_picks(conn, lookback_seconds=settings.lookback_seconds)

    if picks and any(pick.station_key not in stations for pick in picks):
        logger.info("Refreshing station cache due to unknown station in picks")
        stations = fetch_stations(conn)

    events = associate_picks(
        picks,
        window_seconds=settings.association_window_seconds,
        min_stations=settings.min_stations,
        min_phases=settings.min_stations,
        min_score=settings.min_pick_score,
    )

    solved = 0
    for event in events:
        estimate = estimate_origin(
            event,
            stations=stations,
            vp_km_s=settings.vp_km_s,
            min_stations=settings.min_stations,
        )
        if estimate is None:
            continue
        if estimate.rms_seconds > settings.max_residual_seconds:
            logger.info(
                "Skipping origin due to RMS: association_key=%s rms=%.4f threshold=%.4f",
                estimate.association_key,
                estimate.rms_seconds,
                settings.max_residual_seconds,
            )
            continue
        origin_id = upsert_origin(conn, estimate)
        replace_origin_arrivals(conn, origin_id, estimate)
        solved += 1

    logger.info(
        "Cycle complete: stations=%d picks=%d events=%d solved=%d",
        len(stations),
        len(picks),
        len(events),
        solved,
    )
    return stations, {
        "stations": len(stations),
        "picks": len(picks),
        "events": len(events),
        "solved": solved,
    }


def main() -> None:
    settings = parse_args()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("locator.main")
    logger.info("Starting locator service")

    try:
        conn = connect(settings)
    except Exception:
        logger.exception("Failed to connect to PostgreSQL")
        return

    try:
        stations = fetch_stations(conn)
        logger.info("Loaded stations: count=%d", len(stations))
    except Exception:
        logger.exception("Failed to load stations")
        return

    try:
        while True:
            try:
                stations, _metrics = run_cycle(conn, settings, stations, logger)
            except Exception:
                logger.exception("Locator cycle failed")
            time.sleep(settings.poll_seconds)
    except KeyboardInterrupt:
        logger.info("Stopping locator service")


if __name__ == "__main__":
    main()
