import pandas as pd
import plotly.express as px
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

DEAL_TYPE_COL = "Тип сделки"

if DEAL_TYPE_COL in df.columns and "Дата" in df.columns and "Сумма" in df.columns:
    purchases = df[df[DEAL_TYPE_COL] == "Покупка"]
    if not purchases.empty:
        yearly = (
            purchases.assign(Год=purchases["Дата"].dt.year)
            .groupby("Год", as_index=False)["Сумма"]
            .sum()
        )
        st.subheader("Инвестировано по годам, $")
        fig = px.bar(yearly, x="Год", y="Сумма")
        fig.update_traces(marker_color="#2E7D32")
        fig.update_xaxes(type="category")
        fig.update_layout(
            xaxis_title=None,
            yaxis_title="USD",
            margin=dict(l=10, r=10, t=10, b=10),
            height=320,
        )
        st.plotly_chart(fig, use_container_width=True)

col1, col2, col3 = st.columns(3)
with col1:
    asset_types = sorted(df["Вид актива"].dropna().unique()) if "Вид актива" in df.columns else []
    selected_types = st.multiselect("Вид актива", asset_types, default=asset_types)
with col2:
    if DEAL_TYPE_COL in df.columns:
        deal_types = sorted(df[DEAL_TYPE_COL].dropna().unique())
        selected_deal_types = st.multiselect(DEAL_TYPE_COL, deal_types, default=deal_types)
    else:
        selected_deal_types = []
with col3:
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
if DEAL_TYPE_COL in filtered.columns and selected_deal_types:
    filtered = filtered[filtered[DEAL_TYPE_COL].isin(selected_deal_types)]
if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    filtered = filtered[
        (filtered["Дата"].dt.date >= start) & (filtered["Дата"].dt.date <= end)
    ]

st.caption(f"Найдено сделок: {len(filtered)}")

display = filtered.copy()
if "Дата" in display.columns:
    display["Дата"] = display["Дата"].dt.strftime("%d.%m.%Y")
if "Сумма" in display.columns:
    display["Сумма"] = display["Сумма"].apply(
        lambda v: f"${v:,.0f}".replace(",", " ") if pd.notna(v) else ""
    )

st.dataframe(display, width="stretch", hide_index=True)

if "Сумма" in filtered.columns:
    st.metric("Сумма по фильтру", f"${filtered['Сумма'].sum():,.0f}".replace(",", " "))
