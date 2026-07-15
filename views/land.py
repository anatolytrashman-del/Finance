import pandas as pd
import streamlit as st

from avito_land import fetch_all
from config import MONITORED_LAND_AREAS
from land_store import load_listings, save_listings

st.title("🌾 Земельные участки")
st.caption(
    "Источник: avito.ru, поиск по нарисованной области на карте · "
    + " · ".join(a["name"] for a in MONITORED_LAND_AREAS)
)
st.caption(
    "⚠️ Первый прогон: Avito жёстче защищён от ботов, чем kufar/realt — если "
    "после обновления ниже появится предупреждение про «не JSON»/капчу, пришли "
    "мне текст ошибки, разберёмся."
)


def _fmt_rub(v):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.0f} ₽".replace(",", " ")


def _refresh():
    with st.spinner("Собираю объявления с avito.ru (может занять минуту)..."):
        listings, warnings = fetch_all(MONITORED_LAND_AREAS)
    if listings:
        cache = save_listings(listings, warnings)
        st.session_state["land_cache"] = cache
    else:
        st.session_state["land_error"] = (
            "Не удалось получить объявления. " + "; ".join(warnings) if warnings else
            "Не удалось получить объявления (пустой ответ)."
        )


if st.button("🔄 Обновить участки с avito.ru", type="primary"):
    st.session_state.pop("land_error", None)
    _refresh()
    st.rerun()

if st.session_state.get("land_error"):
    st.error(st.session_state["land_error"])

cache = st.session_state.get("land_cache") or load_listings()

if not cache or not cache.get("listings"):
    st.info("Объявления ещё не загружались. Нажми «Обновить участки» выше.")
    st.stop()

st.caption(f"Обновлено: {cache['fetched_at']} · участков: {len(cache['listings'])}")
for w in cache.get("warnings") or []:
    st.warning(w)

df = pd.DataFrame(cache["listings"])

for area in MONITORED_LAND_AREAS:
    name = area["name"]
    sub = df[df["area_name"] == name] if "area_name" in df.columns else df
    st.header(f"📍 {name}")
    if sub.empty:
        st.caption("Участков не найдено.")
        continue

    ppm = sub["price_per_sotka"].dropna()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Участков", len(sub))
    m2.metric("Средняя цена за сотку", _fmt_rub(ppm.mean()) if len(ppm) else "—")
    m3.metric("Медиана", _fmt_rub(ppm.median()) if len(ppm) else "—")
    m4.metric("Диапазон", f"{_fmt_rub(ppm.min())} – {_fmt_rub(ppm.max())}" if len(ppm) else "—")

    table = sub.copy().sort_values("price_per_sotka")
    table["Цена"] = table["price_rub"].apply(_fmt_rub)
    table["Цена за сотку"] = table["price_per_sotka"].apply(lambda v: _fmt_rub(v) if pd.notna(v) else "—")
    table = table.rename(
        columns={
            "title": "Заголовок",
            "land_type": "Тип земли",
            "area_sotok": "Площадь, сот",
            "address": "Адрес",
            "link": "Ссылка",
        }
    )
    st.dataframe(
        table[["Заголовок", "Тип земли", "Площадь, сот", "Цена", "Цена за сотку", "Адрес", "Ссылка"]],
        width="stretch",
        hide_index=True,
        column_config={"Ссылка": st.column_config.LinkColumn("Ссылка", display_text="Открыть")},
    )
