"""Telegram-Push (Standardbibliothek). Ohne Token/Chat-ID -> Dry-Run (nur Konsole)."""
from __future__ import annotations

import json
import urllib.request


def send_telegram(token: str, chat_id: str, text: str, timeout: int = 20) -> bool:
    """Sendet eine Nachricht. Gibt True bei Erfolg zurueck.

    Ohne Zugangsdaten wird nur auf die Konsole geschrieben (Dry-Run) -> False.
    """
    if not token or not chat_id:
        print("[DRY-RUN] (kein Telegram-Token/Chat-ID gesetzt) Nachricht waere:\n" + text + "\n")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.load(resp)
        if not body.get("ok"):
            print(f"[Telegram] Fehler: {body}")
            return False
        return True
    except Exception as exc:  # noqa: BLE001 - Netzwerkfehler nicht fatal machen
        print(f"[Telegram] Ausnahme: {exc}")
        return False
