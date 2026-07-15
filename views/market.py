from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from config import MONITORED_ADDRESSES
from market_kufar import fetch_all as fetch_kufar
from market_realt import fetch_all as fetch_realt
from market_store import (
    append_archive,
    append_history_snapshot,
    load_archive,
    load_comments,
    load_history,
    load_listings,
    load_seen,
    save_comments,
    save_listings,
    save_seen,
)

st.title("🏷️ Анализ рынка")
st.caption("Источники: kufar.by, realt.by · " + " · ".join(a["label"] for a in MONITORED_ADDRESSES))

DEAL_ORDER = ["Продажа", "Аренда"]
CATEGORY_ORDER = ["Квартиры и апартаменты", "Торговые помещения", "Офисы", "Другая коммерческая"]


def _fmt_money(v):
    if v is None or pd.isna(v):
        return "—"
    return f"${v:,.0f}".replace(",", " ")


def _fmt_floor(row):
    floor, total = row.get("floor"), row.get("floors_total")
    floor_ok = floor is not None and not pd.isna(floor)
    total_ok = total is not None and not pd.isna(total)
    if not floor_ok:
        return "—"
    floor_str = str(int(floor))
    return f"{floor_str}/{int(total)}" if total_ok else floor_str


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
    listings, warnings = [], []
    with st.spinner("Собираю объявления с kufar.by (10–30 секунд)..."):
        k_listings, k_warnings = fetch_kufar(MONITORED_ADDRESSES)
    for l in k_listings:
        l["source"] = "kufar.by"
    listings += k_listings
    warnings += k_warnings

    with st.spinner("Собираю объявления с realt.by (10–30 секунд)..."):
        r_listings, r_warnings = fetch_realt(MONITORED_ADDRESSES)
    for l in r_listings:
        l["source"] = "realt.by"
    listings += r_listings
    warnings += r_warnings

    if not listings:
        st.session_state["market_error"] = (
            "Не удалось получить объявления. " + "; ".join(warnings) if warnings else
            "Не удалось получить объявления (пустой ответ)."
        )
        return

    today_iso = date.today().isoformat()
    old_cache = load_listings()
    old_by_id = {l["id"]: l for l in (old_cache or {}).get("listings", [])} if old_cache else {}
    seen = load_seen()

    def _archive_entry(item, reason, first_seen):
        try:
            exposure_days = (date.today() - date.fromisoformat(first_seen[:10])).days
        except Exception:  # noqa: BLE001
            exposure_days = None
        return {
            "id": item.get("id"),
            "address": item.get("address"),
            "deal": item.get("deal"),
            "category": item.get("category"),
            "title": item.get("title"),
            "area": item.get("area"),
            "price_usd": item.get("price_usd"),
            "ppm": item.get("ppm"),
            "source": item.get("source"),
            "reason": reason,
            "first_seen": first_seen,
            "removed_at": today_iso,
            "exposure_days": exposure_days,
        }

    is_first_run = len(seen) == 0
    for l in listings:
        if l["id"] not in seen:
            seen[l["id"]] = today_iso
            l["is_new"] = not is_first_run
        else:
            l["is_new"] = False

    # объявления, которые были в прошлой выдаче, но пропали из новой — в архив
    current_ids = {l["id"] for l in listings}
    archived_ids = set(old_by_id) - current_ids
    archive_records = []
    for aid in archived_ids:
        old = old_by_id[aid]
        first_seen = seen.pop(aid, old.get("listed_at") or today_iso)
        archive_records.append(_archive_entry(old, "Ушло с сайта", first_seen))

    if archive_records:
        append_archive(archive_records)
    save_seen(seen)

    cache = save_listings(listings, warnings)
    append_history_snapshot(_summary_rows(pd.DataFrame(listings)))
    st.session_state["market_cache"] = cache


if st.button("🔄 Обновить объявления (kufar.by + realt.by)", type="primary"):
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
if "is_new" not in df.columns:
    df["is_new"] = False
df["is_new"] = df["is_new"].fillna(False)
if "source" not in df.columns:
    df["source"] = "kufar.by"
for col in ("floor", "floors_total"):
    if col not in df.columns:
        df[col] = None

# ---------------- Общий фильтр ----------------
with st.expander("🔍 Фильтры", expanded=False):
    fc1, fc2, fc3 = st.columns(3)
    deals_present = [d for d in DEAL_ORDER if d in set(df["deal"])]
    with fc1:
        sel_deal = st.multiselect("Сделка", deals_present, default=deals_present)
    categories_present = [c for c in CATEGORY_ORDER if c in set(df["category"])]
    with fc2:
        sel_category = st.multiselect("Категория", categories_present, default=categories_present)
    sources_present = sorted(df["source"].dropna().unique())
    with fc3:
        sel_source = st.multiselect("Источник", sources_present, default=sources_present)

if sel_deal:
    df = df[df["deal"].isin(sel_deal)]
if sel_category:
    df = df[df["category"].isin(sel_category)]
if sel_source:
    df = df[df["source"].isin(sel_source)]

comments = load_comments()

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

    new_count = int(sub["is_new"].sum())
    badge = f" · 🆕 новых: {new_count}" if new_count else ""
    with st.expander(f"Все объявления — {label} ({len(sub)}){badge}"):
        table = sub.copy()
        table = table.sort_values(["is_new", "deal", "category", "ppm"], ascending=[False, True, True, True])
        table["Цена"] = table["price_usd"].apply(_fmt_money)
        table["Цена метра"] = table["ppm"].apply(lambda v: _fmt_money(v) if pd.notna(v) else "—")
        table["Статус"] = table["is_new"].apply(lambda v: "🆕 Новое" if v else "")
        table["Комментарий"] = table["id"].apply(lambda i: comments.get(i, ""))
        table["Этаж"] = table.apply(_fmt_floor, axis=1)
        table = table.rename(
            columns={
                "deal": "Сделка",
                "category": "Категория",
                "source": "Источник",
                "title": "Заголовок",
                "area": "Площадь, м²",
                "listed_at": "Размещено",
                "link": "Ссылка",
            }
        )
        visible_cols = ["Статус", "Сделка", "Категория", "Источник", "Заголовок", "Площадь, м²",
                         "Этаж", "Цена", "Цена метра", "Размещено", "Ссылка", "Комментарий"]
        edited = st.data_editor(
            table[["id", *visible_cols]],
            key=f"listings_editor_{label}",
            width="stretch",
            hide_index=True,
            column_order=visible_cols,
            disabled=[c for c in visible_cols if c != "Комментарий"],
            column_config={
                "Ссылка": st.column_config.LinkColumn("Ссылка", display_text="Открыть"),
                "Комментарий": st.column_config.TextColumn("Комментарий", width="medium"),
            },
        )
        changed = False
        for _, row in edited.iterrows():
            rid = row["id"]
            new_comment = (row.get("Комментарий") or "").strip()
            if comments.get(rid, "") != new_comment:
                if new_comment:
                    comments[rid] = new_comment
                else:
                    comments.pop(rid, None)
                changed = True
        if changed:
            save_comments(comments)
            st.rerun()

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

# --- Архив: объявления, ушедшие с сайтов ---
st.divider()
archive = load_archive()
with st.expander(f"📦 Архив ушедших объявлений ({len(archive)})"):
    if not archive:
        st.caption(
            "Пока пусто. Как только объявление пропадёт из выдачи при следующем "
            "обновлении, оно попадёт сюда — с площадью, типом, ценой и сроком экспозиции."
        )
    else:
        adf = pd.DataFrame(archive)
        if "reason" not in adf.columns:
            adf["reason"] = "Ушло с сайта"
        adf["reason"] = adf["reason"].fillna("Ушло с сайта")
        adf["Цена"] = adf["price_usd"].apply(_fmt_money)
        adf["Цена метра"] = adf["ppm"].apply(lambda v: _fmt_money(v) if pd.notna(v) else "—")
        adf = adf.rename(
            columns={
                "address": "Адрес",
                "deal": "Сделка",
                "category": "Категория",
                "title": "Заголовок",
                "area": "Площадь, м²",
                "reason": "Причина",
                "first_seen": "Появилось",
                "removed_at": "Ушло в архив",
                "exposure_days": "Срок экспозиции, дней",
            }
        )
        adf = adf.sort_values("Ушло в архив", ascending=False)
        st.dataframe(
            adf[["Адрес", "Сделка", "Категория", "Заголовок", "Площадь, м²", "Цена", "Цена метра",
                 "Причина", "Появилось", "Ушло в архив", "Срок экспозиции, дней"]],
            width="stretch",
            hide_index=True,
        )
