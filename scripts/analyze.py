"""Auswertung von data/history.csv: bei welchen Bedingungen gab es je Spot Wind?

Aufruf:
    python scripts/analyze.py                # Schwelle 3.4 m/s
    python scripts/analyze.py --min-ms 1.6   # eigene Schwelle
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


def load(path: Path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="data/history.csv")
    ap.add_argument("--min-ms", type=float, default=3.4, help="Wind-Schwelle fuer 'foilbar'")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"Keine Daten: {path} (laeuft der stuendliche Job schon?)")
        return

    rows = load(path)
    by_spot = defaultdict(list)
    for r in rows:
        by_spot[r["spot"]].append(r)

    print(f"Datensatz: {len(rows)} Zeilen, {len(by_spot)} Spots, Schwelle >= {args.min_ms} m/s\n")

    for spot, rs in by_spot.items():
        good = [r for r in rs if (num(r["wind_ms"]) or 0) >= args.min_ms]
        share = 100 * len(good) / len(rs) if rs else 0
        print(f"== {spot} ==")
        print(f"   Stunden gesamt: {len(rs)} | foilbar: {len(good)} ({share:.0f}%)")
        if not good:
            print("   (noch keine foilbaren Stunden erfasst)\n")
            continue

        regimes = Counter(r["regime"].split(" (")[0] for r in good)
        sectors = Counter(r["sector"] for r in good if r["sector"])
        hours = Counter(int(r["time_local"][11:13]) for r in good)
        ps = [num(r["p_msl_hpa"]) for r in good if num(r["p_msl_hpa"]) is not None]
        dps = [num(r["foehn_dp_hpa"]) for r in good if num(r["foehn_dp_hpa"]) is not None]
        rads = [num(r["radiation_wm2"]) for r in good if num(r["radiation_wm2"]) is not None]

        def top(counter, k=3):
            return ", ".join(f"{v}×{name}" for name, v in counter.most_common(k))

        print(f"   Lagen:        {top(regimes)}")
        print(f"   Richtungen:   {top(sectors)}")
        print(f"   Beste Stunden:{top(hours)}")
        if ps:
            print(f"   Luftdruck:    Ø {sum(ps)/len(ps):.0f} hPa  ({min(ps):.0f}–{max(ps):.0f})")
        if dps:
            print(f"   Foehn-dp:     Ø {sum(dps)/len(dps):+.1f} hPa (Sued−Nord)")
        if rads:
            print(f"   Einstrahlung: Ø {sum(rads)/len(rads):.0f} W/m² (Thermik-Indikator)")
        print()


if __name__ == "__main__":
    main()
