"""Konfiguration laden (TOML) + Umgebungsvariablen-Overrides."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Spot:
    name: str
    lat: float
    lon: float
    min_ms: float
    max_ms: float
    min_run_hours: int
    webcam: str = ""
    station: str = ""
    station_name: str = ""


@dataclass
class Point:
    name: str
    lat: float
    lon: float


@dataclass
class Config:
    timezone: str
    forecast_days: int
    model: str
    day_start_hour: int
    day_end_hour: int
    telegram_token: str
    telegram_chat_id: str
    foehn_south: Point
    foehn_north: Point
    spots: list[Spot] = field(default_factory=list)


def load(path: str | Path = "config.toml") -> Config:
    path = Path(path)
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    g = raw.get("general", {})
    a = raw.get("alert", {})
    t = raw.get("telegram", {})
    fo = raw.get("foehn", {})

    # Defaults aus [alert] fuer die Spots
    d_min = float(a.get("min_ms", 3.4))
    d_max = float(a.get("max_ms", 0.0))
    d_run = int(a.get("min_run_hours", 2))

    spots: list[Spot] = []
    for s in raw.get("spots", []):
        spots.append(
            Spot(
                name=s["name"],
                lat=float(s["lat"]),
                lon=float(s["lon"]),
                min_ms=float(s.get("min_ms", d_min)),
                max_ms=float(s.get("max_ms", d_max)),
                min_run_hours=int(s.get("min_run_hours", d_run)),
                webcam=str(s.get("webcam", "")).strip(),
                station=str(s.get("station", "")).strip(),
                station_name=str(s.get("station_name", "")).strip(),
            )
        )

    def _point(key: str, dname: str, dlat: float, dlon: float) -> Point:
        p = fo.get(key, {})
        return Point(p.get("name", dname), float(p.get("lat", dlat)), float(p.get("lon", dlon)))

    return Config(
        timezone=g.get("timezone", "Europe/Zurich"),
        forecast_days=int(g.get("forecast_days", 3)),
        model=g.get("model", "best_match"),
        day_start_hour=int(g.get("day_start_hour", 7)),
        day_end_hour=int(g.get("day_end_hour", 21)),
        # Umgebungsvariablen haben Vorrang (GitHub Secrets).
        # 'or' statt get(default): eine LEER gesetzte Env-Var (z.B. fehlendes Secret ->
        # GitHub setzt "") faellt korrekt auf den Config-Wert zurueck.
        telegram_token=(os.environ.get("TELEGRAM_TOKEN") or t.get("token", "")).strip(),
        telegram_chat_id=(os.environ.get("TELEGRAM_CHAT_ID") or str(t.get("chat_id", ""))).strip(),
        foehn_south=_point("south", "Lugano", 46.004, 8.951),
        foehn_north=_point("north", "Zuerich", 47.378, 8.540),
        spots=spots,
    )
