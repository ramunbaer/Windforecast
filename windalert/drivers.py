"""Ableitungen: Beaufort, Windsektor, Wetterlage/Treiber-Klassifikation.

Die Regime-Erkennung ist heuristisch (kein amtlicher Foehn-Index), reicht aber
fuer die Zuordnung 'welche Grosswetterlage brachte den Wind' im Logbuch.
"""
from __future__ import annotations

import math

# Obergrenzen (m/s) je Beaufort-Stufe (10-min-Mittelwind)
_BFT_UPPER = [0.2, 1.5, 3.3, 5.4, 7.9, 10.7, 13.8, 17.1, 20.7, 24.4, 28.4, 32.6]

_SECTORS = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def beaufort(ms: float) -> int:
    for i, upper in enumerate(_BFT_UPPER):
        if ms <= upper:
            return i
    return 12


def wind_sector(deg: float) -> str:
    return _SECTORS[int((deg % 360) / 22.5 + 0.5) % 16]


def circ_mean_deg(degs) -> float:
    xs = [d for d in degs if d is not None]
    if not xs:
        return 0.0
    s = sum(math.sin(math.radians(d)) for d in xs)
    c = sum(math.cos(math.radians(d)) for d in xs)
    return math.degrees(math.atan2(s, c)) % 360


def classify_regime(dir_deg, foehn_dp, p_msl, radiation, hour) -> str:
    """Grobe Zuordnung der wahrscheinlichen Wetterlage/Antrieb."""
    d = dir_deg if dir_deg is not None else -1

    # Suedfoehn: grosse positive Druckdifferenz Sued-Nord + Wind aus S-Sektor
    if foehn_dp is not None and foehn_dp >= 4 and 135 <= d <= 225:
        return f"Suedfoehn (dp +{foehn_dp:.0f} hPa)"

    # Nordlage / Nordfoehn: negative Differenz + Wind aus N-Sektor
    if foehn_dp is not None and foehn_dp <= -3 and (d <= 45 or d >= 315):
        return f"Nordlage (dp {foehn_dp:.0f} hPa)"

    # Bise: Hochdruck + Nordost-Stroemung
    if p_msl is not None and p_msl >= 1020 and 20 <= d <= 90:
        return "Bise (NO, Hochdruck)"

    # Thermik: viel Sonne, schwacher Gradient, Nachmittag
    if (radiation is not None and radiation >= 450 and 11 <= hour <= 19
            and (foehn_dp is None or abs(foehn_dp) < 3)):
        return "Thermik (Sonne)"

    if d < 0:
        return "unbestimmt"
    return f"Gradient {wind_sector(d)}"
