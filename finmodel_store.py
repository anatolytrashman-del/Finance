"""Локальное хранилище финмоделей (JSON в домашней директории пользователя).

Хранится вне папки проекта, чтобы модели не терялись при обновлении кода."""
import json
from pathlib import Path

FINMODELS_PATH = Path.home() / ".trashman_family_office" / "finmodels.json"
SALE_FINMODELS_PATH = Path.home() / ".trashman_family_office" / "sale_finmodels.json"


def _load(path):
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:  # noqa: BLE001
            return []
    return []


def _save(path, models):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(models, ensure_ascii=False, indent=2), encoding="utf-8")


def load_finmodels():
    return _load(FINMODELS_PATH)


def save_finmodels(models):
    _save(FINMODELS_PATH, models)


def load_sale_finmodels():
    return _load(SALE_FINMODELS_PATH)


def save_sale_finmodels(models):
    _save(SALE_FINMODELS_PATH, models)
