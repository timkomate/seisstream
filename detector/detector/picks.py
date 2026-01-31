from __future__ import annotations

from typing import Iterable, List, Optional, Tuple


def filter_picks(
    picks: Iterable[Tuple[float, float]],
    last_ts_on: Optional[float],
    window_seconds: float,
) -> Tuple[List[Tuple[float, float]], Optional[float]]:
    picks_list = sorted(picks, key=lambda item: item[0])
    if window_seconds <= 0:
        if picks_list:
            latest = picks_list[-1][0]
            if last_ts_on is not None and last_ts_on > latest:
                latest = last_ts_on
            return picks_list, latest
        return [], last_ts_on

    accepted: List[Tuple[float, float]] = []
    latest = last_ts_on

    for t_on, t_off in picks_list:
        if latest is None or (t_on - latest) > window_seconds:
            accepted.append((t_on, t_off))
            latest = t_on

    return accepted, latest
