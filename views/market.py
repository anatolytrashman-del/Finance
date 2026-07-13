import pandas as pd
import plotly.express as px
import streamlit as st

from config import MONITORED_ADDRESSES
from market_kufar import fetch_all
from market_store import append_history_snapshot, load_history, load_listings, save_listings

st.title("🏷️ Рынок: объявления по моим адресам")
st.caption("Источник: kufar.by · " + " · ".join(a["label"] for a in MONITORED_ADDRESSES))


def _fmt_money(v):
    if v is None or pd.isna(v):
        return "—"
    return f"${v:,.0f}".replace(",", " ")


def _summary_rows(df):
    rows = []
    for (address, deal, category), g in df.groupby(["address", "deal", "category"]):
        ppm = g["ppm"].dropna()
        rows.append(
            {
                "address": address,
                "deal": deal,
                "category": category,
                "count": len(g),
                "avg_ppm": float(ppm.mean()) if len(ppm) else None,
                "median_ppm": float(ppm.median()) if len(ppm) else None,
                "min_ppm": float(ppm.min()) if len(ppm) else None,
                "max_ppm": float(ppm.max()) if len(ppm) else None,
            }
        )
    return rows


def _refresh():
    with st.spinner("Собираю объявления с kufar.by (10–30 секунд)..."):
        listings, warnings = fetch_all(MONITORED_ADDRESSES)
    if listings:
        cache = save_listings(listings, warnings)
        append_history_snapshot(_summary_rows(pd.DataFrame(listings)))
        st.session_state["market_cache"] = cache
    else:
        st.session_state["market_error"] = (
            "Не удалось получить объявления. " + "; ".join(warnings) if warnings else
            "Не удалось получить объявления (пустой ответ)."
        )


if st.button("🔄 Обновить объявления с kufar.by", type="primary"):
    st.session_state.pop("market_error", None)
    _refresh()
    st.rerun()

if st.session_state.get("market_error"):
    st.error(st.session_state["market_error"])

cache = st.session_state.get("market_cache") or load_listings()

if not cache or not cache.get("listings"):
    st.info("Объявления ещё не загружались. Нажми «Обновить объявления» выше.")
    st.stop()

st.caption(f"Обновлено: {cache['fetched_at']} · объявлений: {len(cache['listings'])}")
for w in cache.get("warnings") or []:
    st.warning(w)

df = pd.DataFrame(cache["listings"])

DEAL_ORDER = ["Продажа", "Аренда"]
CATEGORY_ORDER = ["Квартиры и апартаменты", "Торговые помещения", "Офисы", "Другая коммерческая"]

for addr in MONITORED_ADDRESSES:
    label = addr["label"]
    sub = df[df["address"] == label]
    st.header(f"🏠 {label}")
    if sub.empty:
        st.caption("Объявлений не найдено.")
        continue

    # Сводка: средняя цена метра по категориям и типам сделки
    summary = []
    for deal in DEAL_ORDER:
        for category in CATEGORY_ORDER:
            g = sub[(sub["deal"] == deal) & (sub["category"] == category)]
            if g.empty:
                continue
            ppm = g["ppm"].dropna()
            suffix = "/мес" if deal == "Аренда" else ""

            def fmt(v, _s=suffix):
                return (_fmt_money(v) + _s) if pd.notna(v) else "—"

            summary.append(
                {
                    "Сделка": deal,
                    "Категория": category,
                    "Объявлений": len(g),
                    "Средняя цена метра": fmt(ppm.mean()) if len(ppm) else "—",
                    "Медиана": fmt(ppm.median()) if len(ppm) else "—",
                    "Мин": fmt(ppm.min()) if len(ppm) else "—",
                    "Макс": fmt(ppm.max()) if len(ppm) else "—",
                }
            )
    if summary:
        st.dataframe(pd.DataFrame(summary), width="stretch", hide_index=True)

    with st.expander(f"Все объявления — {label} ({len(sub)})"):
        table = sub.copy()
        table = table.sort_values(["deal", "category", "ppm"])
        table["Цена"] = table["price_usd"].apply(_fmt_money)
        table["Цена метра"] = table["ppm"].apply(lambda v: _fmt_money(v) if pd.notna(v) else "—")
        table = table.rename(
            columns={
                "deal": "Сделка",
                "category": "Категория",
                "title": "Заголовок",
                "area": "Площадь, м²",
                "listed_at": "Размещено",
                "link": "Ссылка",
            }
        )[["Сделка", "Категория", "Заголовок", "Площадь, м²", "Цена", "Цена метра", "Размещено", "Ссылка"]]
        st.dataframe(
            table,
            width="stretch",
            hide_index=True,
            column_config={"Ссылка": st.column_config.LinkColumn("Ссылка", display_text="Открыть")},
        )

# --- История средней цены метра ---
history = load_history()
if len(history) >= 2:
    st.divider()
    st.subheader("📈 Динамика средней цены метра (продажа)")
    records = []
    for snap in history:
        for row in snap.get("rows", []):
            if row.get("deal") == "Продажа" and row.get("avg_ppm"):
                records.append(
                    {
                        "Дата": snap["date"],
                        "Серия": f"{row['address']} · {row['category']}",
                        "Средняя $/м²": row["avg_ppm"],
                    }
                )
    if records:
        hist_df = pd.DataFrame(records)
        fig = px.line(hist_df, x="Дата", y="Средняя $/м²", color="Серия", markers=True)
        fig.update_layout(
            xaxis_title=None,
            legend_title=None,
            margin=dict(l=10, r=10, t=10, b=10),
            height=360,
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("📈 График динамики цены метра появится после нескольких обновлений в разные дни.")
