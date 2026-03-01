import numpy as np


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great circle distance in km using haversine formula."""
    R = 6371.0
    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
    )
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c


def azimuth(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate azimuth from point 1 to point 2 in degrees (0-360)."""
    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)
    dlon = np.radians(lon2 - lon1)
    x = np.sin(dlon) * np.cos(lat2_rad)
    y = np.cos(lat1_rad) * np.sin(lat2_rad) - np.sin(lat1_rad) * np.cos(
        lat2_rad
    ) * np.cos(dlon)
    az = np.degrees(np.arctan2(x, y))
    return (az + 360) % 360


def compute_travel_time(distance_km: float, depth_km: float, vp_km_s: float) -> float:
    """Compute P-wave travel time in seconds using straight-line path."""
    hypocentral_distance = np.sqrt(distance_km**2 + depth_km**2)
    return hypocentral_distance / vp_km_s


def compute_travel_time_s(distance_km: float, depth_km: float, vs_km_s: float) -> float:
    """Compute S-wave travel time in seconds using straight-line path."""
    hypocentral_distance = np.sqrt(distance_km**2 + depth_km**2)
    return hypocentral_distance / vs_km_s


def azimuthal_gap(station_azimuths: list[float]) -> float:
    """Calculate largest azimuthal gap."""
    if len(station_azimuths) < 2:
        return 360.0
    sorted_az = sorted(station_azimuths)
    gaps = [sorted_az[i + 1] - sorted_az[i] for i in range(len(sorted_az) - 1)]
    gaps.append(360.0 + sorted_az[0] - sorted_az[-1])
    return max(gaps)


def secondary_azimuthal_gap(station_azimuths: list[float]) -> float:
    """Calculate secondary azimuthal gap."""
    if len(station_azimuths) < 3:
        return 360.0
    sorted_az = sorted(station_azimuths)
    gaps = []
    for i in range(len(sorted_az)):
        next_i = (i + 2) % len(sorted_az)
        if next_i > i:
            gap = sorted_az[next_i] - sorted_az[i]
        else:
            gap = 360.0 + sorted_az[next_i] - sorted_az[i]
        gaps.append(gap)
    return max(gaps)
