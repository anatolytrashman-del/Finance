import pandas as pd
import plotly.express as px
import streamlit as st

from data_source import load_deals, sidebar_refresh_control

sidebar_refresh_control()

st.title("📈 Реестр сделок")

df = load_deals()
if df is None:
    st.info("Нажми «Обновить данные» в боковой панели, чтобы загрузить таблицу.")
    st.stop()

if df.empty:
    st.warning("Лист «Сделки» пуст или не найден.")
    st.stop()

DEAL_TYPE_COL = "Тип сделки"
PROFIT_COL = "Чистая прибыль по сделке"

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


def _signed_amount(row):
    """Покупки — со знаком минус (отток), продажи и займы — с плюсом (приток)."""
    amt = row.get("Сумма")
    if pd.isna(amt):
        return amt
    if DEAL_TYPE_COL in row and row[DEAL_TYPE_COL] == "Покупка":
        return -abs(amt)
    return abs(amt)


def _fmt_signed(v):
    if pd.isna(v):
        return ""
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.0f}".replace(",", " ")


display = filtered.copy()
if "Дата" in display.columns:
    display["Дата"] = display["Дата"].dt.strftime("%d.%m.%Y")
if "Сумма" in filtered.columns:
    signed = filtered.apply(_signed_amount, axis=1) if len(filtered) else filtered["Сумма"]
    display["Сумма"] = signed.apply(_fmt_signed)
# "Чистая прибыль по сделке" — технический столбец (только для счётчика), в таблице не показываем
if PROFIT_COL in display.columns:
    display = display.drop(columns=[PROFIT_COL])

st.dataframe(display, width="stretch", hide_index=True)


def _fmt_pos(v):
    return f"${v:,.0f}".replace(",", " ")


def _sum_by_type(deal_type):
    if DEAL_TYPE_COL in filtered.columns and "Сумма" in filtered.columns:
        return filtered.loc[filtered[DEAL_TYPE_COL] == deal_type, "Сумма"].sum()
    return 0


if DEAL_TYPE_COL in filtered.columns and "Сумма" in filtered.columns:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Итого проинвестировано", _fmt_pos(_sum_by_type("Покупка")))
    m2.metric("Итого продано", _fmt_pos(_sum_by_type("Продажа")))
    m3.metric("Итого выдано в займ", _fmt_pos(_sum_by_type("Выдача займа")))
    profit_total = filtered[PROFIT_COL].sum() if PROFIT_COL in filtered.columns else 0
    m4.metric("Чистая прибыль по сделкам", _fmt_signed(profit_total))
elif "Сумма" in filtered.columns:
    st.metric("Сумма по фильтру", _fmt_pos(filtered["Сумма"].sum()))
