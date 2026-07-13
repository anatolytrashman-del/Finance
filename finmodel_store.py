"""Локальное хранилище финмоделей (JSON в домашней директории пользователя).

Хранится вне папки проекта, чтобы модели не терялись при обновлении кода."""
import json
from pathlib import Path

FINMODELS_PATH = Path.home() / ".trashman_family_office" / "finmodels.json"


def load_finmodels():
    if FINMODELS_PATH.exists():
        try:
            data = json.loads(FINMODELS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:  # noqa: BLE001
            return []
    return []


def save_finmodels(models):
    FINMODELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    FINMODELS_PATH.write_text(json.dumps(models, ensure_ascii=False, indent=2), encoding="utf-8")
