"""Локальное хранилище юрлиц (ООО/ИП).

Хранится вне папки проекта, чтобы записи не терялись при обновлении кода."""
import json

from local_store import APP_DATA_DIR

ENTITIES_PATH = APP_DATA_DIR / "entities.json"


def load_entities():
    if ENTITIES_PATH.exists():
        try:
            data = json.loads(ENTITIES_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:  # noqa: BLE001
            return []
    return []


def save_entities(entities):
    ENTITIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENTITIES_PATH.write_text(json.dumps(entities, ensure_ascii=False, indent=2), encoding="utf-8")
