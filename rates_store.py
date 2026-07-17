"""Локальное хранилище курса валют (bnb.by).

Файл лежит в домашней директории — переживает обновление кода."""
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path.home() / ".trashman_family_office"
RATES_PATH = BASE_DIR / "bnb_rates.json"


def load_rates():
    """Возвращает dict {'fetched_at': str, 'rates': {...}} или None."""
    if RATES_PATH.exists():
        try:
            return json.loads(RATES_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
    return None


def save_rates(rates):
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "rates": rates,
    }
    RATES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return payload
