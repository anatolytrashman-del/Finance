"""Локальное хранилище событий-комментариев к графикам дашборда.

Хранится вне папки проекта (в домашней директории), чтобы события не терялись
при обновлении кода. Каждое событие: {id, date, comment, charts:[ключи графиков]}."""
import json
from pathlib import Path

EVENTS_PATH = Path.home() / ".trashman_family_office" / "events.json"


def load_events():
    if EVENTS_PATH.exists():
        try:
            data = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:  # noqa: BLE001
            return []
    return []


def save_events(events):
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVENTS_PATH.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
