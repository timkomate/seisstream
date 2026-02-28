from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Station:
    net: str
    sta: str
    loc: str
    lat: float
    lon: float
    elev_m: float = 0.0

    @property
    def station_key(self) -> tuple[str, str, str]:
        return (self.net, self.sta, self.loc)


@dataclass(frozen=True)
class Pick:
    id: int
    ts: datetime
    phase: str
    net: str
    sta: str
    loc: str
    chan: str
    score: float | None = None

    @property
    def station_key(self) -> tuple[str, str, str]:
        return (self.net, self.sta, self.loc)


@dataclass(frozen=True)
class Event:
    picks: list[Pick]
    earliest_pick_time: datetime
    association_key: str


@dataclass(frozen=True)
class ArrivalResidual:
    pick: Pick
    distance_km: float
    azimuth_deg: float
    predicted_tt_seconds: float
    residual_seconds: float


@dataclass(frozen=True)
class OriginEstimate:
    association_key: str
    origin_ts: datetime
    lat: float
    lon: float
    depth_km: float
    rms_seconds: float
    azimuthal_gap_deg: float
    used_stations: int
    arrivals: list[ArrivalResidual]
