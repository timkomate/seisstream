from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Station:
    net: str
    sta: str
    loc: str

    @property
    def key(self) -> str:
        return f"{self.net}.{self.sta}.{self.loc or ''}"


@dataclass(frozen=True)
class PhasePick:
    id: int
    ts: datetime
    phase: str
    net: str
    sta: str
    loc: str
    chan: str
    method: str


@dataclass(frozen=True)
class Origin:
    id: int
    origin_ts: datetime
    lat: float
    lon: float
    depth_km: float
    rms_seconds: float
    status: str
    method: str
    n_picks: int
    n_stations: int
