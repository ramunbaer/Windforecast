"""Live-Messwerte von MeteoSchweiz Open Data (SMN, 10-Minuten-Werte).

Quelle: https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/<abbr>/ogd-smn_<abbr>_t_now.csv
Relevante Spalten (10-min):
  reference_timestamp  Zeit in UTC ("DD.MM.YYYY HH:MM")
  fkl010z0             Windgeschwindigkeit skalar, Zehnminutenmittel [m/s]   <- Warn-/Messgroesse
  fkl010z1             Boeenspitze [m/s]
  dkl010z0             Windrichtung, Zehnminutenmittel [Grad]

CORS ist auf data.geo.admin.ch nicht gesetzt -> Abruf erfolgt hier serverseitig
(im GitHub-Actions-Job) und landet in data/measurements.json fuers Dashboard.
"""
from __future__ import annotations

import csv
import io
import urllib.request
from datetime import datetime, timedelta

_URL = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/{a}/ogd-smn_{a}_t_now.csv"


def _num(row: dict, key: str):
    v = (row.get(key) or "").strip()
    try:
        return float(v)
    except ValueError:
        return None


def station_series(abbr: str, hours: int, offset_seconds: int, timeout: int = 40):
    """Messreihe der letzten `hours` Stunden, aufsteigend. Zeiten -> Lokalzeit (naiv)."""
    a = abbr.lower()
    req = urllib.request.Request(_URL.format(a=a), headers={"User-Agent": "windalert/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        rows = list(csv.DictReader(io.StringIO(r.read().decode("utf-8", "replace")), delimiter=";"))

    parsed = []
    for row in rows:
        ts = (row.get("reference_timestamp") or "").strip()
        if not ts:
            continue
        try:
            dt = datetime.strptime(ts, "%d.%m.%Y %H:%M")  # UTC
        except ValueError:
            continue
        parsed.append((dt, _num(row, "fkl010z0"), _num(row, "fkl010z1"), _num(row, "dkl010z0")))

    if not parsed:
        return []
    parsed.sort(key=lambda x: x[0])
    cutoff = parsed[-1][0] - timedelta(hours=hours)
    off = timedelta(seconds=offset_seconds)
    series = []
    for dt, wind, gust, wdir in parsed:
        if dt < cutoff:
            continue
        loc = dt + off
        series.append({
            "t": loc.strftime("%Y-%m-%dT%H:%M"),
            "wind": None if wind is None else round(wind, 1),
            "gust": None if gust is None else round(gust, 1),
            "dir": None if wdir is None else round(wdir),
        })
    return series


def build(spots, offset_seconds: int, hours: int = 6):
    """Pro Spot die Messreihe seiner Station (mit Cache je Stations-Kuerzel)."""
    cache: dict[str, list] = {}
    out = []
    for spot in spots:
        if not spot.station:
            continue
        if spot.station not in cache:
            try:
                cache[spot.station] = station_series(spot.station, hours, offset_seconds)
            except Exception as exc:  # noqa: BLE001 - Ausfall einer Station nicht fatal
                print(f"  Station {spot.station} nicht abrufbar: {exc}")
                cache[spot.station] = []
        series = cache[spot.station]
        current = next((e for e in reversed(series) if e["wind"] is not None), None)
        out.append({
            "name": spot.name,
            "station": spot.station,
            "station_name": spot.station_name,
            "current": current,
            "series": series,
        })
    return out
