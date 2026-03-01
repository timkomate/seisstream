import pytest
from locator.geometry import (
    azimuth,
    azimuthal_gap,
    compute_travel_time,
    compute_travel_time_s,
    haversine_distance,
    secondary_azimuthal_gap,
)


def test_haversine_distance():
    d = haversine_distance(47.4979, 19.0402, 48.2082, 16.3738)
    assert 210 < d < 220

    d = haversine_distance(47.0, 19.0, 47.0, 19.0)
    assert d == pytest.approx(0.0)


def test_azimuth():
    # North
    az = azimuth(0.0, 0.0, 1.0, 0.0)
    assert az == pytest.approx(0.0, abs=1.0)

    # East
    az = azimuth(0.0, 0.0, 0.0, 1.0)
    assert az == pytest.approx(90.0, abs=1.0)

    # South
    az = azimuth(0.0, 0.0, -1.0, 0.0)
    assert az == pytest.approx(180.0, abs=1.0)

    # West
    az = azimuth(0.0, 0.0, 0.0, -1.0)
    assert az == pytest.approx(270.0, abs=1.0)


def test_compute_travel_time():
    # Hypocentral distance = sqrt(100^2 + 10^2) = 100.5 km
    # Travel time = 100.5 / 6 = 16.75 seconds
    tt = compute_travel_time(100.0, 10.0, 6.0)
    assert tt == pytest.approx(16.75, abs=0.1)


def test_compute_travel_time_s():
    # 100 km epicentral distance, 10 km depth, 3.5 km/s velocity
    tt = compute_travel_time_s(100.0, 10.0, 3.5)
    assert tt == pytest.approx(28.71, abs=0.1)


def test_azimuthal_gap_single_station():
    gap = azimuthal_gap([45.0])
    assert gap == 360.0


def test_azimuthal_gap_two_stations():
    gap = azimuthal_gap([0.0, 180.0])
    assert gap == 180.0


def test_azimuthal_gap_evenly_distributed():
    gap = azimuthal_gap([0.0, 90.0, 180.0, 270.0])
    assert gap == 90.0


def test_azimuthal_gap_clustered():
    gap = azimuthal_gap([10.0, 20.0, 30.0])
    assert gap == pytest.approx(340.0, abs=1.0)


def test_secondary_azimuthal_gap_single_station():
    gap = secondary_azimuthal_gap([45.0])
    assert gap == 360.0


def test_secondary_azimuthal_gap_two_stations():
    gap = secondary_azimuthal_gap([0.0, 180.0])
    assert gap == 360.0


def test_secondary_azimuthal_gap_three_stations():
    gap = secondary_azimuthal_gap([0.0, 120.0, 240.0])
    assert gap == 240.0


def test_secondary_azimuthal_gap_four_stations():
    gap = secondary_azimuthal_gap([0.0, 90.0, 180.0, 270.0])
    assert gap == 180.0


def test_secondary_azimuthal_gap_clustered():
    gap = secondary_azimuthal_gap([10.0, 20.0, 30.0, 200.0])
    assert gap == pytest.approx(340.0, abs=1.0)
