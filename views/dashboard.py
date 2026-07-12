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


def capital_stats(df):
    """Последнее значение + изменение за месяц и за год (сумма и %)."""
    if df is None or df.empty:
        return None
    latest_row = df.iloc[-1]
    latest_val, latest_date = latest_row["value"], latest_row["date"]
    stats = {"latest": latest_val, "month_delta": None, "month_pct": None, "year_delta": None, "year_pct": None}

    if len(df) > 1:
        prev_val = df.iloc[-2]["value"]
        stats["month_delta"] = latest_val - prev_val
        if prev_val:
            stats["month_pct"] = (latest_val - prev_val) / abs(prev_val) * 100

    past = df[df["date"] <= latest_date - pd.DateOffset(years=1)]
    if not past.empty:
        past_val = past.iloc[-1]["value"]
        stats["year_delta"] = latest_val - past_val
        if past_val:
            stats["year_pct"] = (latest_val - past_val) / abs(past_val) * 100

    return stats


def fmt_pct(v):
    return f"{v:+.1f}%" if v is not None else None


def render_capital_kpi(label, df, fmt_value, fmt_delta):
    stats = capital_stats(df)
    if stats is None:
        return
    st.metric(label, fmt_value(stats["latest"]))
    sub1, sub2 = st.columns(2)
    with sub1:
        if stats["month_delta"] is not None:
            st.metric("За месяц", fmt_delta(stats["month_delta"]), delta=fmt_pct(stats["month_pct"]))
        else:
            st.caption("За месяц: недостаточно данных")
    with sub2:
        if stats["year_delta"] is not None:
            st.metric("За год", fmt_delta(stats["year_delta"]), delta=fmt_pct(stats["year_pct"]))
        else:
            st.caption("За год: недостаточно данных")


def fmt_usd(v):
    sign = "+" if v >= 0 else "-"
    return f"{sign}${abs(v):,.0f}".replace(",", " ")


def fmt_rub_millions(v):
    return f"{v / 1_000_000:+.1f} млн"


# --- KPI-карточки ---
kpi1, kpi2 = st.columns(2)
with kpi1:
    render_capital_kpi(
        "Капитал, $", capital_usd,
        fmt_value=lambda v: f"${v:,.0f}".replace(",", " "),
        fmt_delta=fmt_usd,
    )
with kpi2:
    render_capital_kpi(
        "Капитал, ₽", capital_rub,
        fmt_value=lambda v: f"{v / 1_000_000:.1f} млн",
        fmt_delta=fmt_rub_millions,
    )

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
