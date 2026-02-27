from __future__ import annotations

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

