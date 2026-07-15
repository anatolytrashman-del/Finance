"""Локальное хранилище объявлений о земельных участках (avito.ru).

Файл лежит в домашней директории — переживает обновление кода."""
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path.home() / ".trashman_family_office"
LISTINGS_PATH = BASE_DIR / "land_listings.json"


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
