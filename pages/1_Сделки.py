import streamlit as st

from data_source import get_workbook, sidebar_refresh_control
from parsers import parse_deals

st.set_page_config(page_title="Сделки", page_icon="📈", layout="wide")

sidebar_refresh_control()

st.title("📈 Реестр сделок")

wb = get_workbook()
if wb is None:
    st.info("Нажми «Обновить данные» в боковой панели, чтобы загрузить таблицу.")
    st.stop()

df = parse_deals(wb)

if df.empty:
    st.warning("Лист «Сделки» пуст или не найден.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    asset_types = sorted(df["Вид актива"].dropna().unique()) if "Вид актива" in df.columns else []
    selected_types = st.multiselect("Вид актива", asset_types, default=asset_types)
with col2:
    if "Дата" in df.columns:
        min_date, max_date = df["Дата"].min(), df["Дата"].max()
        date_range = st.date_input(
            "Период", value=(min_date, max_date), min_value=min_date, max_value=max_date
        )
    else:
        date_range = None

filtered = df.copy()
if selected_types:
    filtered = filtered[filtered["Вид актива"].isin(selected_types)]
if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    filtered = filtered[
        (filtered["Дата"].dt.date >= start) & (filtered["Дата"].dt.date <= end)
    ]

st.caption(f"Найдено сделок: {len(filtered)}")
st.dataframe(filtered, width='stretch', hide_index=True)

if "Сумма" in filtered.columns:
    st.metric("Сумма по фильтру, $", f"{filtered['Сумма'].sum():,.0f}".replace(",", " "))
