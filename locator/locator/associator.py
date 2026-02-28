import hashlib
import logging
from datetime import timedelta

from .models import Event, Pick

logger = logging.getLogger(__name__)


def _calculate_association_key(picks: list[Pick]) -> str:
    canonical = "_".join(str(pick.id) for pick in sorted(picks, key=lambda p: p.id))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def associate_picks(
    picks: list[Pick],
    window_seconds: float,
    min_stations: int,
    min_phases: int,
    min_score: float = 0.0,
) -> list[Event]:
    logger.info(
        "Starting pick association: total_picks=%s window_seconds=%.3f min_stations=%s min_phases=%s min_score=%.3f",
        len(picks),
        window_seconds,
        min_stations,
        min_phases,
        min_score,
    )
    if not picks:
        logger.info("No picks provided; skipping association")
        return []

    filtered: list[Pick] = []
    dropped_by_score = 0
    for pick in picks:
        if pick.score is None:
            logger.warning(
                "Pick id=%s has no score; accepting pick despite score filter", pick.id
            )
            filtered.append(pick)
            continue
        if pick.score >= min_score:
            filtered.append(pick)
            continue
        dropped_by_score += 1

    logger.debug(
        "Score filtering complete: kept=%s dropped_by_score=%s",
        len(filtered),
        dropped_by_score,
    )

    ordered = sorted(filtered, key=lambda pick: pick.ts)

    window = timedelta(seconds=window_seconds)
    events: list[Event] = []
    used_pick_ids: set[int] = set()
    i = 0
    while i < len(ordered):
        seed_pick = ordered[i]

        start_ts = ordered[i].ts
        per_station: dict[tuple[str, str, str], Pick] = {}
        window_pick_ids: set[int] = set()
        j = i
        while j < len(ordered) and ordered[j].ts - start_ts <= window:
            pick = ordered[j]
            if pick.id not in used_pick_ids:
                window_pick_ids.add(pick.id)
                per_station.setdefault(pick.station_key, pick)
            j += 1

        event_picks = sorted(per_station.values(), key=lambda p: p.ts)
        station_count = len({pick.station_key for pick in event_picks})
        phase_count = len(event_picks)
        logger.debug(
            "Evaluated window seed_pick_id=%s start_ts=%s candidate_picks=%s stations=%s phases=%s",
            seed_pick.id,
            start_ts.isoformat(),
            len(window_pick_ids),
            station_count,
            phase_count,
        )
        if (
            station_count >= min_stations
            and phase_count >= min_phases
        ):
            association_key = _calculate_association_key(event_picks)
            events.append(
                Event(
                    picks=event_picks,
                    earliest_pick_time=event_picks[0].ts,
                    association_key=association_key,
                )
            )
            used_pick_ids.update(window_pick_ids)
            logger.info(
                "Created event: seed_pick_id=%s picks=%s stations=%s earliest_pick_time=%s association_key=%s",
                seed_pick.id,
                phase_count,
                station_count,
                event_picks[0].ts.isoformat(),
                association_key,
            )
            i = j
            continue

        logger.debug(
            "Rejected window seed_pick_id=%s: stations=%s/%s phases=%s/%s",
            seed_pick.id,
            station_count,
            min_stations,
            phase_count,
            min_phases,
        )
        i += 1

    logger.info("Association complete: events=%s used_picks=%s", len(events), len(used_pick_ids))
    return events
