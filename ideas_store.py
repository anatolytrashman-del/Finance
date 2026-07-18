"""Локальное хранилище инвест-идей (JSON в домашней директории пользователя).

Хранится вне папки проекта, чтобы идеи не терялись при обновлении кода
(скачивании свежего архива и замене папки)."""
import json

from local_store import APP_DATA_DIR

IDEAS_PATH = APP_DATA_DIR / "invest_ideas.json"


def load_ideas():
    if IDEAS_PATH.exists():
        try:
            data = json.loads(IDEAS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:  # noqa: BLE001
            return []
    return []


def save_ideas(ideas):
    IDEAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    IDEAS_PATH.write_text(json.dumps(ideas, ensure_ascii=False, indent=2), encoding="utf-8")
