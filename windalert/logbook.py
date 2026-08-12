"""Logbuch: pro Lauf eine Zeile je Spot fuer die aktuelle Stunde (data/history.csv).

Baut ueber die Zeit den Datensatz auf, mit dem sich spaeter herausfinden laesst,
bei welchen Bedingungen (Druck, Richtung, Lage, Sonne) es an einem Spot Wind gab.
"""
from __future__ import annotations

import csv
from pathlib import Path

HEADER = [
    "time_local", "spot",
    "wind_ms", "gust_ms", "dir_deg", "sector", "beaufort",
    "p_msl_hpa", "surface_p_hpa", "temp_c", "cloud_pct", "radiation_wm2",
    "foehn_dp_hpa", "regime",
]


def append_rows(path: str | Path, rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADER)
        if new_file:
            writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in HEADER})
