# Wind-Alarm 🌬️ – Wingfoil-Push für Schweizer Seen

Meldet **im Voraus** per Telegram, wenn der **mittlere Wind 10 m über Boden**
(nicht Böen, nicht Höhenwind) an deinen Spots einen Grenzwert erreicht – und
protokolliert nebenbei die Bedingungen (Druck, Windrichtung, Föhn/Bise, Sonne),
damit du mit der Zeit erkennst, welche Wetterlage an welchem Spot Wind bringt.

**Spots:** Greifensee · Untersee (Steckborn) · Urnersee (Flüelen) ·
Urnersee (Sisikon) · Walensee (Tiefenwinkel)

**Datenquelle:** [Open-Meteo](https://open-meteo.com) mit den MeteoSwiss-Modellen
ICON-CH1/CH2. Gratis, kein API-Key. **Betrieb:** GitHub Actions (stündlich, gratis).
**Kein `pip install` nötig** – reine Python-Standardbibliothek (Python ≥ 3.11).

---

## Wie es funktioniert

1. Stündlich holt der Job die Vorhersage (nächste `forecast_days` Tage) für alle Spots.
2. Er sucht **zusammenhängende Tagesstunden** mit Wind ≥ Grenzwert und schickt für
   jedes **neue** Fenster eine Telegram-Nachricht (Dedup verhindert Spam).
3. Er hängt pro Lauf je Spot eine Zeile ans **Logbuch** `data/history.csv` an.
4. GitHub Actions committet `data/` zurück ins Repo → dein Verlauf wächst automatisch.

Beispiel-Push:

```
🌬️ Urnersee (Flüelen)
Morgen 13–17 Uhr
Wind Ø 4.2–5.1 m/s (8–10 kt, Bft 3)
Boeen bis 8 m/s · Richtung SSO (168°)
Lage: Suedfoehn (dp +6 hPa)
```

---

## Einrichtung (einmalig, ~10 Min)

### 1. Telegram-Bot erstellen
1. In Telegram `@BotFather` öffnen → `/newbot` → Namen vergeben.
   Du erhältst einen **Token** wie `123456789:AAG...`.
2. Deinem neuen Bot **eine Nachricht schicken** (z.B. „hallo"), sonst darf er dir
   nicht antworten.
3. **Chat-ID herausfinden:** im Browser öffnen (Token einsetzen):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   → im JSON steht `"chat":{"id":123456789,...}`. Diese Zahl ist deine `chat_id`.

### 2. Lokal testen (optional, empfohlen)
```bash
cd Windforecast
# Zugangsdaten temporär als Umgebungsvariablen (PowerShell):
$env:TELEGRAM_TOKEN="123456789:AAG..."; $env:TELEGRAM_CHAT_ID="123456789"
python -m windalert.main            # sendet echte Testnachricht bei Wind
python -m windalert.main --dry-run  # sendet nichts, zeigt nur Konsole
```

### 3. Auf GitHub deployen (24/7-Betrieb, auch wenn dein PC aus ist)
1. Neues **GitHub-Repo** anlegen und diesen Ordner hochladen:
   ```bash
   cd Windforecast
   git init && git add . && git commit -m "Wind-Alarm"
   git branch -M main
   git remote add origin https://github.com/<user>/<repo>.git
   git push -u origin main
   ```
2. Im Repo → **Settings → Secrets and variables → Actions → New repository secret**:
   - `TELEGRAM_TOKEN` = dein Bot-Token
   - `TELEGRAM_CHAT_ID` = deine Chat-ID
3. Reiter **Actions** öffnen, Workflow *wind-alert* aktivieren und einmal
   **„Run workflow"** klicken (Test). Danach läuft er stündlich automatisch.

> **Hinweis GitHub-Cron:** Geplante Läufe starten in UTC und können unter Last ein
> paar Minuten verspätet sein – für stündliche Wind-Warnungen unkritisch.

---

## Grenzwert einstellen

In [`config.toml`](config.toml), Abschnitt `[alert]`:

| Beaufort | mittlerer Wind |
|---|---|
| Bft 2 | 1.6–3.3 m/s |
| Bft 3 | 3.4–5.4 m/s |
| Bft 4 | 5.5–7.9 m/s |

- **Standard `min_ms = 3.4`** = ab Bft 3 („es wird foilbar").
- Für Warnungen schon **ab Bft 2**: `min_ms = 1.6` setzen.
- `min_run_hours` = wie viele Stunden am Stück über der Schwelle liegen müssen.
- Grenzwert **pro Spot** überschreibbar (Zeile `min_ms = …` unter dem Spot).

---

## Logbuch & Auswertung

`data/history.csv` sammelt pro Stunde je Spot:
`wind_ms, gust_ms, dir_deg, sector, beaufort, p_msl_hpa, surface_p_hpa,
temp_c, cloud_pct, radiation_wm2, foehn_dp_hpa, regime`.

Auswertung, welche Bedingungen Wind brachten:
```bash
python scripts/analyze.py                # Schwelle 3.4 m/s
python scripts/analyze.py --min-ms 1.6   # eigene Schwelle
```
Ausgabe je Spot: Anteil foilbarer Stunden, häufigste **Wetterlagen**,
**Windrichtungen**, beste **Tageszeiten**, mittlerer **Luftdruck**,
**Föhn-Δp** (Lugano−Zürich) und **Einstrahlung** (Thermik-Indikator).

### Web-Dashboard (grafischer Verlauf)

[`dashboard.html`](dashboard.html) zeigt je Spot den **Windverlauf mit Luftdruck**
(Punkte nach Wetterlage eingefärbt), die **foilbaren Stunden pro Lage** und ein
**Treiber-Streudiagramm** (Wind gegen Luftdruck / Föhn-Δp / Sonneneinstrahlung /
Bewölkung) – so siehst du auf einen Blick, bei welchen Bedingungen es Wind gab.

**Lokal ansehen** (das Dashboard lädt `data/history.csv` per `fetch`, braucht also
einen kleinen Server – Doppelklick auf die Datei genügt wegen Browser-Sicherheit nicht):
```bash
python -m http.server 8000
# dann im Browser: http://localhost:8000/dashboard.html
```
Alternativ im Dashboard direkt eine CSV-Datei auswählen (Fallback ohne Server).

**Online via GitHub Pages** (optional): Repo → Settings → Pages → Branch `main` / `/root`.
Danach ist das Dashboard unter `https://<user>.github.io/<repo>/dashboard.html`
erreichbar und liest automatisch die vom Job aktualisierte `data/history.csv`.

### Treiber / Wetterlagen (heuristisch)
- **Südföhn:** Δp(Süd−Nord) ≥ +4 hPa **und** Wind aus S-Sektor → v.a. am Urnersee.
- **Nordlage:** Δp ≤ −3 hPa und Wind aus N.
- **Bise:** Hochdruck (≥ 1020 hPa) und Wind aus NO.
- **Thermik:** viel Sonne (≥ 450 W/m²), schwacher Gradient, Nachmittag.
- sonst **Gradient <Sektor>**.

Die Föhn-Δp wird aus zwei Zusatzpunkten (Lugano/Zürich) berechnet – konfigurierbar
unter `[foehn.south]` / `[foehn.north]`.

---

## Grenzen / Feintuning
- **Modellauflösung** ~1–2 km: Bei **Untersee (Steckborn)** liegt die Gitterzelle
  auf ~498 m (hügeliges Gelände, keine reine Wasserzelle) → Wind evtl. leicht erhöht;
  der *relative* Verlauf bleibt aussagekräftig. Koordinaten in `config.toml` frei anpassbar.
- Für einen längeren Horizont ggf. `model = "meteoswiss_icon_ch2"` und `forecast_days`
  erhöhen.
- Später möglich: Ist-Wert-Abgleich mit MeteoSwiss-Messstationen (SwissMetNet).

## Projektstruktur
```
Windforecast/
├─ config.toml              # Spots, Grenzwerte, Föhn-Punkte
├─ windalert/
│  ├─ main.py               # Ablauf: fetch → Fenster → Push → Logbuch
│  ├─ meteo.py              # Open-Meteo-Abfrage
│  ├─ drivers.py            # Beaufort, Sektor, Wetterlage
│  ├─ notify.py             # Telegram
│  ├─ state.py              # Dedup-Zustand
│  ├─ logbook.py            # CSV-Logbuch
│  └─ config.py             # Konfiguration laden
├─ scripts/analyze.py       # Auswertung des Logbuchs (Konsole)
├─ dashboard.html           # grafisches Web-Dashboard (Chart.js)
├─ .github/workflows/wind.yml
├─ .claude/launch.json      # lokaler Server für das Dashboard
└─ data/                    # history.csv + state.json (vom Job erzeugt)
```
