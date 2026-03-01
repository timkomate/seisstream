import logging
from datetime import datetime, timezone

import numpy as np

from .geometry import azimuth, azimuthal_gap, compute_travel_time, haversine_distance
from .models import ArrivalResidual, Event, OriginEstimate, Pick, Station

logger = logging.getLogger(__name__)


def estimate_origin(
    event: Event,
    stations: dict[tuple[str, str, str], Station],
    vp_km_s: float,
    min_stations: int = 4,
    max_depth_km: float = 80.0,
    max_iterations: int = 30,
) -> OriginEstimate | None:
    logger.info(
        "Starting origin estimation: association_key=%s picks=%d min_stations=%d vp_km_s=%.3f",
        event.association_key,
        len(event.picks),
        min_stations,
        vp_km_s,
    )
    if vp_km_s <= 0:
        raise ValueError("vp_km_s must be > 0")
    if min_stations < 3:
        raise ValueError("min_stations must be >= 3")

    picks: list[Pick] = []
    station_list: list[Station] = []
    pick_epochs: list[float] = []
    for pick in event.picks:
        station = stations.get(pick.station_key)
        if station is None:
            logger.warning(
                "Skipping pick with missing station metadata: pick_id=%s station=%s.%s.%s",
                pick.id,
                pick.net,
                pick.sta,
                pick.loc,
            )
            continue
        picks.append(pick)
        station_list.append(station)
        pick_epochs.append(pick.ts.timestamp())

    if len(picks) < min_stations:
        logger.info(
            "Origin estimation skipped: usable_picks=%d required=%d",
            len(picks),
            min_stations,
        )
        return None

    # Picks should be sorted at this point...
    first_pick = picks[0]
    first_station = stations[first_pick.station_key]
    lat0 = float(first_station.lat)
    lon0 = float(first_station.lon)

    depth0 = 10.0
    origin0 = float(min(pick_epochs) - 2.0)
    x = np.array([lat0, lon0, depth0, origin0], dtype=float)

    min_epoch = min(pick_epochs) - 300.0
    max_epoch = max(pick_epochs) + 300.0
    lower = np.array([-90.0, -180.0, 0.0, min_epoch], dtype=float)
    upper = np.array([90.0, 180.0, max_depth_km, max_epoch], dtype=float)

    def residuals(params: np.ndarray) -> np.ndarray:
        lat, lon, depth_km, origin_epoch = params
        out: list[float] = []
        for station, observed_epoch in zip(station_list, pick_epochs):
            distance_km = haversine_distance(lat, lon, station.lat, station.lon)
            tt_pred = compute_travel_time(distance_km, depth_km, vp_km_s)
            out.append(observed_epoch - (origin_epoch + tt_pred))
        return np.asarray(out, dtype=float)

    for _ in range(max_iterations):
        r = residuals(x)
        rms0 = float(np.sqrt(np.mean(r * r)))
        logger.debug(
            "Iteration: association_key=%s rms=%.6f lat=%.5f lon=%.5f depth=%.3f",
            event.association_key,
            rms0,
            x[0],
            x[1],
            x[2],
        )
        jac = _finite_difference_jacobian(residuals, x)
        try:
            dx, *_ = np.linalg.lstsq(jac, -r, rcond=None)
        except np.linalg.LinAlgError:
            logger.exception(
                "Linear solve failed for association_key=%s",
                event.association_key,
            )
            return None

        improved = False
        alpha = 1.0
        for _ in range(8):
            x_try = np.clip(x + alpha * dx, lower, upper)
            r_try = residuals(x_try)
            rms_try = float(np.sqrt(np.mean(r_try * r_try)))
            if rms_try < rms0:
                x = x_try
                improved = True
                break
            alpha *= 0.5
        if not improved or np.linalg.norm(alpha * dx) < 1e-5:
            logger.debug(
                "Stopping iterations: association_key=%s improved=%s step_norm=%.8f",
                event.association_key,
                improved,
                float(np.linalg.norm(alpha * dx)),
            )
            break

    lat, lon, depth_km, origin_epoch = x
    final_residuals = residuals(x)
    rms = float(np.sqrt(np.mean(final_residuals * final_residuals)))

    arrivals: list[ArrivalResidual] = []
    azimuths: list[float] = []
    for pick, station, residual in zip(picks, station_list, final_residuals):
        distance_km = haversine_distance(lat, lon, station.lat, station.lon)
        az = azimuth(lat, lon, station.lat, station.lon)
        tt_pred = compute_travel_time(distance_km, depth_km, vp_km_s)
        arrivals.append(
            ArrivalResidual(
                pick=pick,
                distance_km=float(distance_km),
                azimuth_deg=float(az),
                predicted_tt_seconds=float(tt_pred),
                residual_seconds=float(residual),
            )
        )
        azimuths.append(float(az))

    result = OriginEstimate(
        association_key=event.association_key,
        origin_ts=datetime.fromtimestamp(float(origin_epoch), tz=timezone.utc),
        lat=float(lat),
        lon=float(lon),
        depth_km=float(depth_km),
        rms_seconds=rms,
        azimuthal_gap_deg=float(azimuthal_gap(azimuths)),
        used_stations=len(arrivals),
        arrivals=arrivals,
    )
    logger.info(
        "Origin estimated: association_key=%s origin_ts=%s lat=%.5f lon=%.5f depth_km=%.3f rms=%.4f stations=%d",
        result.association_key,
        result.origin_ts.isoformat(),
        result.lat,
        result.lon,
        result.depth_km,
        result.rms_seconds,
        result.used_stations,
    )
    return result


def _finite_difference_jacobian(
    residual_fn,
    x: np.ndarray,
) -> np.ndarray:
    base = residual_fn(x)
    jac = np.zeros((base.size, x.size), dtype=float)
    steps = np.array([1e-4, 1e-4, 1e-3, 1e-3], dtype=float)
    for i in range(x.size):
        x2 = x.copy()
        x2[i] += steps[i]
        jac[:, i] = (residual_fn(x2) - base) / steps[i]
    return jac
