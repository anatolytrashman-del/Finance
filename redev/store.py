"""Единая точка получения датафрейма проектов для вьюх."""
import streamlit as st

from data_source import get_workbook, is_configured
from parsers import demo_projects, parse_projects


def load_projects():
    """Возвращает (df, is_demo). В демо-режиме или при пустой таблице отдаёт пример."""
    if not is_configured():
        return demo_projects(), True
    wb = get_workbook()
    if wb is None:
        return demo_projects(), True
    df = parse_projects(wb)
    if df.empty:
        return demo_projects(), True
    return df, False


def demo_banner(is_demo: bool):
    if is_demo:
        st.info(
            "Демо-режим: показан пример проектов. Создай лист **«Проекты»** в Google-таблице "
            "и впиши её ID в `config.py`, чтобы видеть реальные данные.",
            icon="🧪",
        )
