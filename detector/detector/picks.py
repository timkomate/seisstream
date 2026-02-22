from __future__ import annotations

from typing import Iterable, List, Optional, Tuple


def _keep_all_picks(
    picks_list: List[Tuple],
    last_ts_on: Optional[float],
) -> Tuple[List[Tuple], Optional[float]]:
    if not picks_list:
        return [], last_ts_on

    latest = picks_list[-1][0]
    if last_ts_on is not None and last_ts_on > latest:
        latest = last_ts_on
    return picks_list, latest


def filter_picks(
    picks: Iterable[Tuple[float, float]],
    last_ts_on: Optional[float],
    window_seconds: float,
) -> Tuple[List[Tuple[float, float]], Optional[float]]:
    picks_list = sorted(picks, key=lambda item: item[0])
    if window_seconds <= 0:
        return _keep_all_picks(picks_list, last_ts_on)

    accepted: List[Tuple[float, float]] = []
    latest = last_ts_on

    for t_on, t_off in picks_list:
        if latest is None or (t_on - latest) > window_seconds:
            accepted.append((t_on, t_off))
            latest = t_on

    return accepted, latest


def filter_phase_picks(
    picks: Iterable[Tuple],
    last_ts_on: Optional[float],
    window_seconds: float,
) -> Tuple[List[Tuple], Optional[float]]:
    picks_list = sorted(picks, key=lambda item: item[0])
    if window_seconds <= 0:
        return _keep_all_picks(picks_list, last_ts_on)

    accepted: List[Tuple] = []
    latest = last_ts_on

    for pick in picks_list:
        t_on = pick[0]
        if latest is None or (t_on - latest) > window_seconds:
            accepted.append(pick)
            latest = t_on

    return accepted, latest
