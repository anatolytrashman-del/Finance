"""Загрузка книги гугл-таблицы с проектами редевелопмента по публичной ссылке-экспорту.

Если ID таблицы не задан в config.py, приложение работает на демо-данных —
загрузчик просто возвращает None, а вьюхи подставляют пример проекта.
"""
from io import BytesIO

import openpyxl
import requests
import streamlit as st

from config import GOOGLE_SHEET_ID

ACCESS_HINT = (
    "Не удалось скачать таблицу. Проверь настройки доступа: "
    "«Доступ по ссылке» -> «Все, у кого есть ссылка» -> Читатель."
)


def _export_url() -> str:
    return f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=xlsx"


def _fetch_bytes() -> bytes:
    resp = requests.get(_export_url(), timeout=30)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "")
    if "spreadsheet" not in content_type and "octet-stream" not in content_type:
        raise RuntimeError(ACCESS_HINT)
    return resp.content


@st.cache_resource(show_spinner="Читаю таблицу...")
def _parse_workbook(raw: bytes):
    return openpyxl.load_workbook(BytesIO(raw), data_only=True)


def is_configured() -> bool:
    return bool(GOOGLE_SHEET_ID.strip())


def get_workbook(force_refresh: bool = False):
    """Возвращает openpyxl Workbook или None (если таблица не настроена / не скачалась)."""
    if not is_configured():
        return None

    if force_refresh or "workbook_bytes" not in st.session_state:
        try:
            st.session_state["workbook_bytes"] = _fetch_bytes()
            st.session_state["load_error"] = None
        except Exception as exc:  # noqa: BLE001
            st.session_state["load_error"] = str(exc)

    error = st.session_state.get("load_error")
    if error:
        st.error(error)

    raw = st.session_state.get("workbook_bytes")
    if raw is None:
        return None
    return _parse_workbook(raw)


def sidebar_refresh_control():
    with st.sidebar:
        st.markdown("### Данные")
        if not is_configured():
            st.caption("Демо-режим. Впиши ID таблицы в `config.py`, чтобы читать реальные проекты.")
            return
        if st.button("🔄 Обновить данные", width="stretch"):
            get_workbook(force_refresh=True)
            st.rerun()
        if "workbook_bytes" in st.session_state and not st.session_state.get("load_error"):
            st.caption("Данные загружены из Google Таблицы")
