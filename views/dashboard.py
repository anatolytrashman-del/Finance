import pandas as pd
import plotly.express as px
import streamlit as st

from data_source import get_workbook, sidebar_refresh_control
from parsers import parse_asset_allocation, parse_progress

sidebar_refresh_control()

st.title("📊 Дашборд капитала")

wb = get_workbook()
if wb is None:
    st.info("Нажми «Обновить данные» в боковой панели, чтобы загрузить таблицу.")
    st.stop()

data = parse_progress(wb)
capital_usd = data.get("capital_usd", pd.DataFrame())
capital_rub = data.get("capital_rub", pd.DataFrame())
debt = data.get("debt", pd.DataFrame())


def line_chart(df, y_label, color):
    if df is None or df.empty:
        st.warning("Нет данных для отображения.")
        return
    fig = px.line(df, x="date", y="value", markers=True)
    fig.update_traces(line_color=color)
    fig.update_layout(
        xaxis_title=None,
        yaxis_title=y_label,
        margin=dict(l=10, r=10, t=10, b=10),
        height=320,
    )
    st.plotly_chart(fig, use_container_width=True)


def latest_and_delta(df):
    if df is None or df.empty:
        return None, None
    latest = df.iloc[-1]["value"]
    delta = df.iloc[-1]["value"] - df.iloc[-2]["value"] if len(df) > 1 else None
    return latest, delta


# --- KPI-карточки ---
usd_latest, usd_delta = latest_and_delta(capital_usd)
rub_latest, rub_delta = latest_and_delta(capital_rub)

kpi1, kpi2 = st.columns(2)
with kpi1:
    if usd_latest is not None:
        delta_str = None
        if usd_delta is not None:
            sign = "+" if usd_delta >= 0 else "-"
            delta_str = f"{sign}${abs(usd_delta):,.0f}".replace(",", " ")
        st.metric("Капитал, $", f"${usd_latest:,.0f}".replace(",", " "), delta=delta_str)
with kpi2:
    if rub_latest is not None:
        delta_str = f"{rub_delta / 1_000_000:+.1f} млн" if rub_delta is not None else None
        st.metric("Капитал, ₽", f"{rub_latest / 1_000_000:.1f} млн", delta=delta_str)

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("Капитал, $")
    line_chart(capital_usd, "USD", "#2E7D32")
with col2:
    st.subheader("Капитал, ₽")
    line_chart(capital_rub, "RUB", "#1565C0")

col3, col4 = st.columns(2)
with col3:
    st.subheader("Прирост капитала по годам")
    if not capital_usd.empty:
        yearly = (
            capital_usd.assign(Год=capital_usd["date"].dt.year)
            .groupby("Год", as_index=False)["value"]
            .last()
        )
        yearly["Прирост"] = yearly["value"].diff()
        yearly = yearly.dropna(subset=["Прирост"])
        if yearly.empty:
            st.warning("Недостаточно данных для расчёта прироста.")
        else:
            fig = px.bar(yearly, x="Год", y="Прирост")
            fig.update_traces(
                marker_color=["#2E7D32" if v >= 0 else "#C62828" for v in yearly["Прирост"]]
            )
            fig.update_xaxes(type="category")
            fig.update_layout(
                xaxis_title=None,
                yaxis_title="USD",
                margin=dict(l=10, r=10, t=10, b=10),
                height=320,
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Нет данных для отображения.")
with col4:
    st.subheader("Долг / капитал, %")
    if not debt.empty and not capital_usd.empty:
        merged = pd.merge(
            capital_usd.assign(ym=capital_usd["date"].dt.to_period("M")),
            debt.assign(ym=debt["date"].dt.to_period("M")),
            on="ym",
            suffixes=("_cap", "_debt"),
        )
        if merged.empty:
            st.warning("Нет пересекающихся месяцев для расчёта.")
        else:
            merged["leverage"] = -merged["value_debt"] / merged["value_cap"] * 100
            fig = px.line(merged, x="date_cap", y="leverage", markers=True)
            fig.update_traces(line_color="#EF6C00")
            fig.update_layout(
                xaxis_title=None,
                yaxis_title="%",
                margin=dict(l=10, r=10, t=10, b=10),
                height=320,
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Нет данных для отображения.")

col5, col6 = st.columns(2)
with col5:
    st.subheader("Долговая нагрузка, $")
    st.caption("Значения без даты в исходной таблице пропущены")
    line_chart(debt, "USD", "#C62828")
with col6:
    st.subheader("Структура капитала по классам активов")
    allocation = parse_asset_allocation(wb)
    if allocation.empty:
        st.warning("Не нашёл помесячный срез с разбивкой по активам.")
    else:
        fig = px.pie(allocation, names="Категория", values="Сумма", hole=0.4)
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=320)
        st.plotly_chart(fig, use_container_width=True)

st.divider()

col7, col8 = st.columns(2)
with col7:
    st.subheader("Активный доход, $")
    line_chart(data.get("active_income"), "USD", "#1565C0")
with col8:
    st.subheader("Пассивный доход, $")
    line_chart(data.get("passive_income"), "USD", "#6A1B9A")
