import pandas as pd
import streamlit as st

from config import STAGES
from data_source import sidebar_refresh_control
from store import demo_banner, load_projects

sidebar_refresh_control()

st.title("📇 Карточка проекта")

df, is_demo = load_projects()
demo_banner(is_demo)

if df.empty:
    st.warning("Проектов пока нет. Добавь строки на лист «Проекты».")
    st.stop()


def _money(v):
    return "—" if pd.isna(v) else f"${v:,.0f}".replace(",", " ")


def _num(v, suffix=""):
    return "—" if pd.isna(v) else f"{v:,.0f}{suffix}".replace(",", " ")


def _text(v):
    return "—" if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "" else str(v)


name = st.selectbox("Проект", df["Проект"].tolist())
row = df[df["Проект"] == name].iloc[0]

st.header(_text(row["Проект"]))
st.caption(f"{_text(row['Город'])} · {_text(row['Адрес'])}")

# ---- KPI карточки ----
c1, c2, c3, c4 = st.columns(4)
c1.metric("Стадия", _text(row["Стадия"]))
c2.metric("Статус", _text(row["Статус"]))
c3.metric("Готовность", _num(row["Готовность %"], "%"))
budget = row["Бюджет CAPEX $"]
invested = row["Вложено $"]
c4.metric(
    "Освоено бюджета",
    f"{invested / budget * 100:.0f}%" if pd.notna(budget) and budget and pd.notna(invested) else "—",
)

# ---- Прогресс по стадиям ----
stage = _text(row["Стадия"])
if stage in STAGES:
    idx = STAGES.index(stage)
    st.progress((idx + 1) / len(STAGES), text=f"Стадия {idx + 1} из {len(STAGES)}: {stage}")

st.divider()

# ---- Назначение и площади ----
left, right = st.columns(2)
with left:
    st.subheader("Назначение")
    st.markdown(f"**Сейчас:** {_text(row['Текущее назначение'])}")
    st.markdown(f"**Цель:** {_text(row['Целевое назначение'])}")

    st.subheader("Площади")
    st.markdown(f"- Участок: **{_num(row['Площадь участка (сот)'], ' сот.')}**")
    st.markdown(f"- Здание (GBA): **{_num(row['Площадь здания (м²)'], ' м²')}**")
    st.markdown(f"- Арендопригодная (GLA): **{_num(row['Аренд. площадь (м²)'], ' м²')}**")

with right:
    st.subheader("Экономика")
    st.markdown(f"- Бюджет CAPEX: **{_money(budget)}**")
    st.markdown(f"- Вложено: **{_money(invested)}**")
    remaining = (budget - invested) if pd.notna(budget) and pd.notna(invested) else None
    st.markdown(f"- Осталось профинансировать: **{_money(remaining) if remaining is not None else '—'}**")

    st.subheader("Сроки")
    st.markdown(f"- Старт: **{_text(row['Дата старта'])}**")
    st.markdown(f"- План ввода: **{_text(row['План ввода'])}**")
    st.markdown(f"- Ответственный: **{_text(row['Ответственный'])}**")

comment = _text(row["Комментарий"])
if comment != "—":
    st.divider()
    st.subheader("Комментарий")
    st.write(comment)
