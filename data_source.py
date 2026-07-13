"""Загрузка книги гугл-таблицы по публичной ссылке-экспорту.

Разобранные данные кэшируются и пересчитываются только при нажатии
«Обновить данные» — переходы между вкладками и фильтры работают мгновенно."""
from io import BytesIO

import openpyxl
import requests
import streamlit as st

import parsers
from config import GOOGLE_SHEET_ID

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


# version (лёгкий ключ кэша) хэшируется, _raw (тяжёлые байты) — нет.
@st.cache_resource(show_spinner="Читаю таблицу...")
def _workbook(version: int, _raw: bytes):
    return openpyxl.load_workbook(BytesIO(_raw), data_only=True)


@st.cache_data(show_spinner=False)
def _progress(version, _raw):
    return parsers.parse_progress(_workbook(version, _raw))


@st.cache_data(show_spinner=False)
def _deals(version, _raw):
    return parsers.parse_deals(_workbook(version, _raw))


@st.cache_data(show_spinner=False)
def _real_estate(version, _raw):
    return parsers.parse_real_estate(_workbook(version, _raw))


@st.cache_data(show_spinner=False)
def _real_estate_sold(version, _raw):
    return parsers.parse_real_estate_sold(_workbook(version, _raw))


@st.cache_data(show_spinner=False)
def _asset_allocation(version, _raw):
    return parsers.parse_asset_allocation(_workbook(version, _raw))


def _ensure_loaded(force_refresh: bool = False):
    """Гарантирует, что байты таблицы загружены. Возвращает (version, raw)."""
    if force_refresh or "workbook_bytes" not in st.session_state:
        try:
            st.session_state["workbook_bytes"] = _fetch_bytes()
            st.session_state["data_version"] = st.session_state.get("data_version", 0) + 1
            st.session_state["load_error"] = None
        except Exception as exc:  # noqa: BLE001
            st.session_state["load_error"] = str(exc)

    if st.session_state.get("load_error"):
        st.error(st.session_state["load_error"])

    return st.session_state.get("data_version", 0), st.session_state.get("workbook_bytes")


def load_progress():
    version, raw = _ensure_loaded()
    return _progress(version, raw) if raw is not None else None


def load_deals():
    version, raw = _ensure_loaded()
    return _deals(version, raw) if raw is not None else None


def load_real_estate():
    version, raw = _ensure_loaded()
    return _real_estate(version, raw) if raw is not None else None


def load_real_estate_sold():
    version, raw = _ensure_loaded()
    return _real_estate_sold(version, raw) if raw is not None else None


def load_asset_allocation():
    version, raw = _ensure_loaded()
    return _asset_allocation(version, raw) if raw is not None else None


def sidebar_refresh_control():
    with st.sidebar:
        st.markdown("### Данные")
        if st.button("🔄 Обновить данные", width="stretch"):
            st.cache_data.clear()
            st.cache_resource.clear()
            _ensure_loaded(force_refresh=True)
            st.rerun()
        if "workbook_bytes" in st.session_state and not st.session_state.get("load_error"):
            st.caption("Данные загружены из Google Таблицы")
