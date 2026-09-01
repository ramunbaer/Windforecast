"""Ein Durchlauf: Vorhersage holen -> Wind-Fenster finden -> pushen -> Logbuch."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# UTF-8-Ausgabe erzwingen (Windows-Konsole ist sonst cp1252 und wirft bei Emojis/Umlauten).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from . import config as cfg
from . import drivers, logbook, measurements, meteo
from .notify import send_telegram
from .state import State

DATA_DIR = Path("data")


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def _now_local(utc_offset_seconds: int) -> datetime:
    """Aktuelle lokale (naive) Zeit, abgeleitet aus dem API-Offset.

    Vermeidet die Abhaengigkeit von IANA-Zeitzonen (zoneinfo) auf Windows.
    """
    return (datetime.now(timezone.utc) + timedelta(seconds=utc_offset_seconds)).replace(tzinfo=None)


def _parse(t: str) -> datetime:
    return datetime.fromisoformat(t)  # z.B. "2026-08-12T13:00"


def _now_index(times: list[str], now_local: datetime) -> int:
    stamp = now_local.strftime("%Y-%m-%dT%H")
    for i, t in enumerate(times):
        if t.startswith(stamp):
            return i
    return 0


def find_windows(times, winds, day_start, day_end, min_ms, max_ms, min_run, start_from):
    """Zusammenhaengende Tagesstunden mit Wind >= min_ms (optional <= max_ms)."""
    n = len(times)

    def ok(k: int) -> bool:
        h = int(times[k][11:13])
        if not (day_start <= h < day_end):
            return False
        w = winds[k]
        if w is None or w < min_ms:
            return False
        if max_ms and w > max_ms:
            return False
        return True

    windows = []
    i = 0
    while i < n:
        if ok(i):
            j = i
            while j + 1 < n and ok(j + 1):
                j += 1
            if (j - i + 1) >= min_run and _parse(times[j]) >= start_from:
                windows.append((i, j))
            i = j + 1
        else:
            i += 1
    return windows


# ---------------------------------------------------------------------------
# Formatierung
# ---------------------------------------------------------------------------
def _fmt_day(dt: datetime, now: datetime) -> str:
    delta = (dt.date() - now.date()).days
    if delta == 0:
        return "Heute"
    if delta == 1:
        return "Morgen"
    if delta == 2:
        return "Uebermorgen"
    return ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][dt.weekday()] + dt.strftime(" %d.%m.")


def build_message(spot_name, times, winds, gusts, dirs, foehn_dp, window, now):
    i, j = window
    seg_w = [w for w in winds[i:j + 1] if w is not None]
    seg_g = [g for g in gusts[i:j + 1] if g is not None]
    start, end = _parse(times[i]), _parse(times[j])
    dir_mean = drivers.circ_mean_deg(dirs[i:j + 1])
    mid = (i + j) // 2
    dp = foehn_dp[mid] if foehn_dp else None
    regime = drivers.classify_regime(dir_mean, dp, None, None, start.hour)

    w_min, w_max = min(seg_w), max(seg_w)
    bft_lo, bft_hi = drivers.beaufort(w_min), drivers.beaufort(w_max)
    bft = f"Bft {bft_lo}" if bft_lo == bft_hi else f"Bft {bft_lo}-{bft_hi}"
    gust = max(seg_g) if seg_g else 0.0
    kt_lo, kt_hi = w_min * 1.94384, w_max * 1.94384

    day = _fmt_day(start, now)
    return (
        f"\U0001F32C️ <b>{spot_name}</b>\n"
        f"{day} {start:%H}–{end:%H} Uhr\n"
        f"Wind Ø {w_min:.1f}–{w_max:.1f} m/s ({kt_lo:.0f}–{kt_hi:.0f} kt, {bft})\n"
        f"Boeen bis {gust:.0f} m/s · Richtung {drivers.wind_sector(dir_mean)} ({dir_mean:.0f}°)\n"
        f"Lage: {regime}"
    )


# ---------------------------------------------------------------------------
# Hauptlauf
# ---------------------------------------------------------------------------
def _targets(conf) -> list:
    """Alle konfigurierten Empfaenger: persoenliche chat_id und/oder Kanal."""
    return [t for t in (conf.telegram_chat_id, conf.telegram_channel) if t]


def _broadcast(conf, text: str, dry_run: bool) -> int:
    """Sendet an ALLE Ziele (kein Kurzschluss!). Gibt die Anzahl erfolgreicher Sendungen zurueck."""
    tgts = _targets(conf)
    if dry_run or not conf.telegram_token or not tgts:
        send_telegram("", "", text)  # Dry-Run-Ausgabe auf Konsole
        return 0
    # sum() ueber Liste -> jeder Versand wird ausgefuehrt (any() wuerde nach dem 1. Erfolg abbrechen).
    return sum(send_telegram(conf.telegram_token, t, text) for t in tgts)


def run(config_path: str = "config.toml", dry_run: bool = False) -> int:
    conf = cfg.load(config_path)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state = State(DATA_DIR / "state.json")

    points = [(s.lat, s.lon) for s in conf.spots]
    points.append((conf.foehn_south.lat, conf.foehn_south.lon))
    points.append((conf.foehn_north.lat, conf.foehn_north.lon))

    data = meteo.fetch(points, conf.timezone, conf.forecast_days, conf.model)
    spot_data = data[: len(conf.spots)]
    south_data, north_data = data[-2], data[-1]

    # Foehn-Druckdifferenz je Zeitschritt (Sued - Nord)
    south_p = south_data["hourly"]["pressure_msl"]
    north_p = north_data["hourly"]["pressure_msl"]
    foehn_dp = [
        (s - n) if (s is not None and n is not None) else None
        for s, n in zip(south_p, north_p)
    ]

    offset = spot_data[0].get("utc_offset_seconds", 0)
    now = _now_local(offset)
    state.prune(now)

    n_alerts = 0
    for spot, d in zip(conf.spots, spot_data):
        h = d["hourly"]
        times = h["time"]
        winds = h["wind_speed_10m"]
        gusts = h["wind_gusts_10m"]
        dirs = h["wind_direction_10m"]

        windows = find_windows(
            times, winds,
            conf.day_start_hour, conf.day_end_hour,
            spot.min_ms, spot.max_ms, spot.min_run_hours,
            start_from=now - timedelta(hours=1),
        )
        for win in windows:
            key = f"{spot.name}|{times[win[0]]}"
            if state.already_notified(key):
                continue
            msg = build_message(spot.name, times, winds, gusts, dirs, foehn_dp, win, now)
            sent = _broadcast(conf, msg, dry_run)
            if sent or dry_run or not conf.telegram_token or not _targets(conf):
                # Auch im Dry-Run/ohne Ziel als "gesehen" merken, sonst Spam beim naechsten Lauf.
                state.mark_notified(key, now.isoformat(timespec="minutes"))
            if sent:
                n_alerts += 1

    # --- Logbuch: eine Zeile je Spot fuer die aktuelle Stunde -------------
    cur_hour = now.strftime("%Y-%m-%dT%H")
    if state.last_log_hour != cur_hour:
        rows = []
        idx = _now_index(spot_data[0]["hourly"]["time"], now)
        dp_now = foehn_dp[idx] if idx < len(foehn_dp) else None
        for spot, d in zip(conf.spots, spot_data):
            h = d["hourly"]
            if idx >= len(h["time"]):
                continue
            wd = h["wind_direction_10m"][idx]
            ws = h["wind_speed_10m"][idx]
            rad = h["shortwave_radiation"][idx]
            pmsl = h["pressure_msl"][idx]
            rows.append({
                "time_local": h["time"][idx],
                "spot": spot.name,
                "wind_ms": None if ws is None else round(ws, 1),
                "gust_ms": None if h["wind_gusts_10m"][idx] is None else round(h["wind_gusts_10m"][idx], 1),
                "dir_deg": None if wd is None else round(wd),
                "sector": "" if wd is None else drivers.wind_sector(wd),
                "beaufort": None if ws is None else drivers.beaufort(ws),
                "p_msl_hpa": None if pmsl is None else round(pmsl, 1),
                "surface_p_hpa": None if h["surface_pressure"][idx] is None else round(h["surface_pressure"][idx], 1),
                "temp_c": h["temperature_2m"][idx],
                "cloud_pct": h["cloud_cover"][idx],
                "radiation_wm2": rad,
                "foehn_dp_hpa": None if dp_now is None else round(dp_now, 1),
                "regime": drivers.classify_regime(wd, dp_now, pmsl, rad, _parse(h["time"][idx]).hour),
            })
        logbook.append_rows(DATA_DIR / "history.csv", rows)
        state.last_log_hour = cur_hour
        print(f"Logbuch: {len(rows)} Zeilen fuer {cur_hour} ergaenzt.")

    # --- Prognose (naechste ~48 h) je Spot fuers Dashboard schreiben --------
    fc_times = spot_data[0]["hourly"]["time"]
    idx0 = _now_index(fc_times, now)
    HORIZON = 48
    fc_spots = []
    for spot, d in zip(conf.spots, spot_data):
        h = d["hourly"]
        series = []
        for k in range(idx0, min(idx0 + HORIZON, len(h["time"]))):
            ws = h["wind_speed_10m"][k]
            wd = h["wind_direction_10m"][k]
            pmsl = h["pressure_msl"][k]
            rad = h["shortwave_radiation"][k]
            dp = foehn_dp[k] if k < len(foehn_dp) else None
            series.append({
                "t": h["time"][k],
                "wind": None if ws is None else round(ws, 1),
                "gust": None if h["wind_gusts_10m"][k] is None else round(h["wind_gusts_10m"][k], 1),
                "dir": None if wd is None else round(wd),
                "sector": "" if wd is None else drivers.wind_sector(wd),
                "bft": None if ws is None else drivers.beaufort(ws),
                "p_msl": None if pmsl is None else round(pmsl, 1),
                "rad": rad,
                "cloud": h["cloud_cover"][k],
                "regime": drivers.classify_regime(wd, dp, pmsl, rad, _parse(h["time"][k]).hour),
            })
        fc_spots.append({"name": spot.name, "min_ms": spot.min_ms,
                         "webcam": spot.webcam, "lat": spot.lat, "lon": spot.lon,
                         "series": series})
    forecast = {
        "generated": now.isoformat(timespec="minutes"),
        "day_start": conf.day_start_hour, "day_end": conf.day_end_hour,
        # Koordinaten fuer den clientseitigen Live-Abruf (Dashboard holt Open-Meteo direkt)
        "foehn": {"south": {"lat": conf.foehn_south.lat, "lon": conf.foehn_south.lon},
                  "north": {"lat": conf.foehn_north.lat, "lon": conf.foehn_north.lon}},
        "spots": fc_spots,
    }
    (DATA_DIR / "forecast.json").write_text(
        json.dumps(forecast, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Prognose geschrieben: {len(fc_spots)} Spots x bis {HORIZON} h.")

    # --- Live-Messwerte (MeteoSchweiz OGD) + 6h-Verlauf fuers Dashboard -----
    try:
        meas = measurements.build(conf.spots, offset, hours=6)
        (DATA_DIR / "measurements.json").write_text(
            json.dumps({"generated": now.isoformat(timespec="minutes"), "hours": 6, "spots": meas},
                       ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        n_ok = sum(1 for m in meas if m["current"])
        print(f"Messwerte geschrieben: {n_ok}/{len(meas)} Stationen mit aktuellem Wert.")
    except Exception as exc:  # noqa: BLE001 - Messnetz-Ausfall darf den Lauf nicht killen
        print(f"Messwerte uebersprungen: {exc}")

    state.save()
    print(f"Fertig. {n_alerts} neue Warnung(en) gesendet. Lokalzeit: {now:%Y-%m-%d %H:%M}")
    return n_alerts


def main() -> None:
    ap = argparse.ArgumentParser(description="Wind-Alarm fuer Schweizer Seen (Wingfoil)")
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--dry-run", action="store_true", help="nichts senden, nur Konsole")
    ap.add_argument("--test", action="store_true",
                    help="einmalige Telegram-Testnachricht senden und beenden")
    args = ap.parse_args()

    if args.test:
        conf = cfg.load(args.config)
        sent = _broadcast(
            conf,
            "✅ <b>Wind-Alarm</b> Test — Verbindung steht. "
            "Sobald der Wind an einem Spot den Grenzwert erreicht, kommt hier die Warnung.",
            dry_run=False,
        )
        print(f"Testnachricht an {sent} Ziel(e) gesendet." if sent else
              "Nicht gesendet (Token/Ziel fehlen oder falsch — siehe Ausgabe oben).")
        return

    run(args.config, args.dry_run)


if __name__ == "__main__":
    main()
