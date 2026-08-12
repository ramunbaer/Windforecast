"""Zustand fuer De-Duplizierung der Warnungen (data/state.json)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


class State:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = {"notified": {}, "last_log_hour": None}
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass

    # --- Warnungen ----------------------------------------------------------
    def already_notified(self, key: str) -> bool:
        return key in self.data["notified"]

    def mark_notified(self, key: str, when_iso: str) -> None:
        self.data["notified"][key] = when_iso

    def prune(self, now: datetime, keep_days: int = 4) -> None:
        cutoff = now - timedelta(days=keep_days)
        keep = {}
        for k, v in self.data["notified"].items():
            try:
                if datetime.fromisoformat(v) >= cutoff:
                    keep[k] = v
            except ValueError:
                keep[k] = v
        self.data["notified"] = keep

    # --- Logbuch-Takt -------------------------------------------------------
    @property
    def last_log_hour(self):
        return self.data.get("last_log_hour")

    @last_log_hour.setter
    def last_log_hour(self, value: str):
        self.data["last_log_hour"] = value

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
