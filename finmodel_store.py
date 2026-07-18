"""Локальное хранилище финмоделей (JSON в домашней директории пользователя).

Хранится вне папки проекта, чтобы модели не терялись при обновлении кода."""
import json

from local_store import APP_DATA_DIR

FINMODELS_PATH = APP_DATA_DIR / "finmodels.json"
SALE_FINMODELS_PATH = APP_DATA_DIR / "sale_finmodels.json"
BUYRENT_FINMODELS_PATH = APP_DATA_DIR / "buyrent_finmodels.json"


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


def load_buyrent_finmodels():
    return _load(BUYRENT_FINMODELS_PATH)


def save_buyrent_finmodels(models):
    _save(BUYRENT_FINMODELS_PATH, models)
