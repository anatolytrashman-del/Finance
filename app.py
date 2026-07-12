import plotly.express as px
import streamlit as st

from data_source import get_workbook, sidebar_refresh_control
from parsers import parse_progress

st.set_page_config(page_title="Капитал — Дашборд", page_icon="📊", layout="wide")

sidebar_refresh_control()

st.title("📊 Дашборд капитала")

wb = get_workbook()
if wb is None:
    st.info("Нажми «Обновить данные» в боковой панели, чтобы загрузить таблицу.")
    st.stop()

data = parse_progress(wb)


def line_chart(df, y_label, color):
    if df.empty:
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
    st.plotly_chart(fig, width='stretch')


col1, col2 = st.columns(2)
with col1:
    st.subheader("Капитал, $")
    line_chart(data.get("capital_usd"), "USD", "#2E7D32")
with col2:
    st.subheader("Капитал, ₽")
    line_chart(data.get("capital_rub"), "RUB", "#1565C0")

col3, col4 = st.columns(2)
with col3:
    st.subheader("Долговая нагрузка, $")
    st.caption("Значения без даты в исходной таблице пропущены")
    line_chart(data.get("debt"), "USD", "#C62828")
with col4:
    st.subheader("Активный и пассивный доход, $")
    active = data.get("active_income")
    passive = data.get("passive_income")
    if active.empty and passive.empty:
        st.warning("Нет данных для отображения.")
    else:
        import pandas as pd

        combined = pd.concat(
            [
                active.assign(тип="Активный доход") if not active.empty else active,
                passive.assign(тип="Пассивный доход") if not passive.empty else passive,
            ]
        )
        fig = px.line(combined, x="date", y="value", color="тип", markers=True)
        fig.update_layout(
            xaxis_title=None,
            yaxis_title="USD",
            legend_title=None,
            margin=dict(l=10, r=10, t=10, b=10),
            height=320,
        )
        st.plotly_chart(fig, width='stretch')
