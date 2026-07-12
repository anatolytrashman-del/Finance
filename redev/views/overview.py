import pandas as pd
import plotly.express as px
import streamlit as st

from config import STAGES
from data_source import sidebar_refresh_control
from store import demo_banner, load_projects

sidebar_refresh_control()

st.title("🏗️ Реестр проектов редевелопмента")

df, is_demo = load_projects()
demo_banner(is_demo)

if df.empty:
    st.warning("Проектов пока нет. Добавь строки на лист «Проекты».")
    st.stop()


def _money(v):
    return "—" if pd.isna(v) else f"${v:,.0f}".replace(",", " ")


# ---- Фильтры ----
with st.sidebar:
    st.markdown("### Фильтры")
    stages = [s for s in STAGES if s in set(df["Стадия"].dropna())]
    extra = sorted(set(df["Стадия"].dropna()) - set(STAGES))
    stage_options = stages + extra
    picked_stages = st.multiselect("Стадия", stage_options, default=stage_options)
    status_options = sorted(df["Статус"].dropna().unique().tolist())
    picked_statuses = st.multiselect("Статус", status_options, default=status_options)

f = df[df["Стадия"].isin(picked_stages) & df["Статус"].isin(picked_statuses)]

# ---- KPI ----
budget = f["Бюджет CAPEX $"].sum(skipna=True)
invested = f["Вложено $"].sum(skipna=True)
avg_ready = f["Готовность %"].mean(skipna=True)
active = (f["Статус"] == "Активен").sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Проектов", f"{len(f)}", f"{active} активных")
c2.metric("Суммарный бюджет", _money(budget))
c3.metric(
    "Вложено",
    _money(invested),
    f"{invested / budget * 100:.0f}% бюджета" if budget else None,
)
c4.metric("Средняя готовность", "—" if pd.isna(avg_ready) else f"{avg_ready:.0f}%")

st.divider()

# ---- Воронка по стадиям + бюджет по проектам ----
left, right = st.columns(2)

with left:
    st.subheader("Проекты по стадиям")
    counts = (
        f["Стадия"]
        .value_counts()
        .reindex(stage_options)
        .dropna()
        .rename_axis("Стадия")
        .reset_index(name="Кол-во")
    )
    if not counts.empty:
        fig = px.bar(counts, x="Кол-во", y="Стадия", orientation="h", text="Кол-во")
        fig.update_layout(
            yaxis={"categoryorder": "array", "categoryarray": stage_options[::-1]},
            height=340,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig, width='stretch')

with right:
    st.subheader("Бюджет vs вложено")
    bd = f[["Проект", "Бюджет CAPEX $", "Вложено $"]].copy()
    if not bd.empty:
        melted = bd.melt(id_vars="Проект", var_name="Показатель", value_name="Сумма")
        fig2 = px.bar(melted, x="Сумма", y="Проект", color="Показатель", barmode="group")
        fig2.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0), legend_title="")
        st.plotly_chart(fig2, width='stretch')

st.divider()

# ---- Реестр ----
st.subheader("Реестр")
table = f[
    [
        "Проект",
        "Город",
        "Целевое назначение",
        "Стадия",
        "Статус",
        "Готовность %",
        "Бюджет CAPEX $",
        "Вложено $",
        "План ввода",
        "Ответственный",
    ]
].copy()

st.dataframe(
    table,
    width='stretch',
    hide_index=True,
    column_config={
        "Готовность %": st.column_config.ProgressColumn(
            "Готовность", min_value=0, max_value=100, format="%d%%"
        ),
        "Бюджет CAPEX $": st.column_config.NumberColumn("Бюджет", format="$%d"),
        "Вложено $": st.column_config.NumberColumn("Вложено", format="$%d"),
    },
)

st.caption("Карточка проекта — на вкладке «Карточка проекта».")
