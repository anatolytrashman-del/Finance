"""Локальное хранилище архива документов (JSON в домашней директории).

Хранится вне папки проекта, чтобы записи не терялись при обновлении кода.
Сами файлы лежат на Google Диске — тут храним только ссылки и метаданные.
Документ: {id, object, object_label, type, date, number, amount, summary, link}."""
import json

from local_store import APP_DATA_DIR

DOCS_PATH = APP_DATA_DIR / "documents.json"


def load_documents():
    if DOCS_PATH.exists():
        try:
            data = json.loads(DOCS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:  # noqa: BLE001
            return []
    return []


def save_documents(documents):
    DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_PATH.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")
