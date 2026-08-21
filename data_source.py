"""Скачивание книги Google Таблицы по публичной ссылке-экспорту.

Используется только migrate_from_sheet.py (разовый перенос истории в
db.py) — сам app.py больше не читает Google Таблицу, все views/*.py берут
данные из db.py."""
from config import GOOGLE_SHEET_ID

import requests

EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=xlsx"

ACCESS_HINT = (
    "Не удалось скачать таблицу. Проверь настройки доступа: "
    "«Доступ по ссылке» -> «Все, у кого есть ссылка» -> Читатель."
)


def _fetch_bytes() -> bytes:
    resp = requests.get(EXPORT_URL, timeout=30)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "")
    if "spreadsheet" not in content_type and "octet-stream" not in content_type:
        raise RuntimeError(ACCESS_HINT)
    return resp.content
