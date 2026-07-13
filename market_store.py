"""Локальное хранилище объявлений рынка и истории средних цен.

Файлы лежат в домашней директории — переживают обновление кода."""
import json
from datetime import date, datetime
from pathlib import Path

BASE_DIR = Path.home() / ".trashman_family_office"
LISTINGS_PATH = BASE_DIR / "market_listings.json"
HISTORY_PATH = BASE_DIR / "market_history.json"


def load_listings():
    """Возвращает dict {'fetched_at': str, 'listings': [...], 'warnings': [...]} или None."""
    if LISTINGS_PATH.exists():
        try:
            return json.loads(LISTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
    return None


def save_listings(listings, warnings):
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "listings": listings,
        "warnings": warnings,
    }
    LISTINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return payload


def load_history():
    if HISTORY_PATH.exists():
        try:
            data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:  # noqa: BLE001
            return []
    return []


def append_history_snapshot(rows):
    """rows: [{'address':…, 'deal':…, 'category':…, 'avg_ppm':…, 'count':…}, …].
    Снапшот за сегодня заменяется, за прошлые даты — остаётся как есть."""
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    history = [s for s in load_history() if s.get("date") != today]
    history.append({"date": today, "rows": rows})
    history.sort(key=lambda s: s.get("date", ""))
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
    return history
