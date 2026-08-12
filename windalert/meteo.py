"""Open-Meteo Abfrage (Standardbibliothek, kein API-Key)."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"

# Alles, was wir fuer Warnung UND Treiber-Analyse brauchen.
HOURLY_VARS = [
    "wind_speed_10m",       # mittlerer Wind 10 m ueber Boden  <-- Warn-Groesse
    "wind_direction_10m",
    "wind_gusts_10m",       # Boeen (nur zur Info)
    "surface_pressure",
    "pressure_msl",
    "temperature_2m",
    "cloud_cover",
    "shortwave_radiation",  # Sonneneinstrahlung -> Thermik-Proxy
]


def fetch(points, timezone: str, forecast_days: int, model: str, timeout: int = 30):
    """points: Liste von (lat, lon). Gibt eine Liste von Dicts zurueck (ein Eintrag pro Punkt)."""
    lats = ",".join(f"{lat:.4f}" for lat, lon in points)
    lons = ",".join(f"{lon:.4f}" for lat, lon in points)
    params = {
        "latitude": lats,
        "longitude": lons,
        "hourly": ",".join(HOURLY_VARS),
        "wind_speed_unit": "ms",
        "timezone": timezone,
        "forecast_days": str(forecast_days),
        "models": model,
    }
    url = OPEN_METEO + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "windalert/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    # Bei einem einzelnen Punkt liefert die API ein Dict statt einer Liste.
    if isinstance(data, dict):
        data = [data]
    return data
