from abc import ABC, abstractmethod

from .geometry import (
    compute_travel_time,
    compute_travel_time_s,
    delta_degrees,
    haversine_distance,
)
from .models import Station


class TravelTimeModel(ABC):
    name: str

    @abstractmethod
    def predict(
        self,
        source_lat: float,
        source_lon: float,
        station: Station,
        depth_km: float,
        phase: str,
    ) -> float:
        """Predict travel time in seconds."""


class ConstantVelocityTravelTime(TravelTimeModel):
    name = "constant"

    def __init__(self, vp_km_s: float, vs_km_s: float) -> None:
        self.vp_km_s = vp_km_s
        self.vs_km_s = vs_km_s

    def predict(
        self,
        source_lat: float,
        source_lon: float,
        station: Station,
        depth_km: float,
        phase: str,
    ) -> float:
        distance_km = haversine_distance(
            source_lat, source_lon, station.lat, station.lon
        )
        phase_upper = phase.upper()
        if phase_upper == "P":
            return float(compute_travel_time(distance_km, depth_km, self.vp_km_s))
        if phase_upper == "S":
            return float(compute_travel_time_s(distance_km, depth_km, self.vs_km_s))
        raise ValueError(f"Unsupported phase for constant travel time: {phase}")


class TauPTravelTime(TravelTimeModel):
    name = "taup"

    def __init__(
        self,
        model: str,
        p_phases: list[str] | tuple[str, ...],
        s_phases: list[str] | tuple[str, ...],
    ) -> None:
        from obspy.taup import TauPyModel

        self.model = model
        self.p_phases = list(p_phases)
        self.s_phases = list(s_phases)
        self._model = TauPyModel(model=self.model)

    def predict(
        self,
        source_lat: float,
        source_lon: float,
        station: Station,
        depth_km: float,
        phase: str,
    ) -> float:
        distance_deg = delta_degrees(source_lat, source_lon, station.lat, station.lon)
        phase_upper = phase.upper()
        if phase_upper == "P":
            phase_list = self.p_phases
        elif phase_upper == "S":
            phase_list = self.s_phases
        else:
            raise ValueError(f"Unsupported phase for TauP travel time: {phase}")

        arrivals = self._model.get_travel_times(
            source_depth_in_km=float(depth_km),
            distance_in_degree=distance_deg,
            phase_list=phase_list,
        )
        if not arrivals:
            raise ValueError(
                "No TauP arrival for depth_km="
                f"{depth_km} distance_deg={distance_deg:.6f} phases={phase_list}"
            )

        return float(arrivals[0].time)


def build_travel_time_model(
    travel_time_model: str,
    vp_km_s: float,
    vs_km_s: float,
    taup_model: str,
    taup_p_phases: list[str] | tuple[str, ...],
    taup_s_phases: list[str] | tuple[str, ...],
) -> TravelTimeModel:
    if travel_time_model == "constant":
        return ConstantVelocityTravelTime(vp_km_s=vp_km_s, vs_km_s=vs_km_s)
    if travel_time_model == "taup":
        return TauPTravelTime(
            model=taup_model,
            p_phases=taup_p_phases,
            s_phases=taup_s_phases,
        )
    raise ValueError(f"Unsupported travel time model: {travel_time_model}")
