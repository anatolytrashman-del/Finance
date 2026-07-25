import pandas as pd
import streamlit as st

from data_source import load_deals, sidebar_refresh_control
from rates_widget import render_sidebar_rates
from theme import card, esc, kpi_card, kpi_row, page, section_title

sidebar_refresh_control()
render_sidebar_rates()

df = load_deals()
if df is None:
    st.title("📈 Реестр сделок")
    st.info("Нажми «Обновить данные» в боковой панели, чтобы загрузить таблицу.")
    st.stop()

if df.empty:
    st.title("📈 Реестр сделок")
    st.warning("Лист «Сделки» пуст или не найден.")
    st.stop()

DEAL_TYPE_COL = "Тип сделки"
PROFIT_COL = "Чистая прибыль по сделке"
ASSET_COL = "Вид актива"

# Категории (сущности): Инвестиции (отток), Продажа, Дивиденды (притоки-возвраты)
INVEST, SALE, DIVIDEND, OTHER = "Инвестиции", "Продажа", "Дивиденды", "Прочее"
ENTITY_ORDER = [INVEST, SALE, DIVIDEND, OTHER]
CATEGORY_COLORS = {
    INVEST: ("#f59e0b", "#fff7ed"),
    SALE: ("#3b82f6", "#eff6ff"),
    DIVIDEND: ("#10b981", "#ecfdf5"),
    OTHER: ("#6b7280", "#f3f4f6"),
}

RENT_MONTHLY = 375.0
RENT_START = pd.Timestamp(2025, 2, 1)
RENT_LABEL = "Аренда квартиры"


def _entity(deal_type):
    t = str(deal_type or "").lower()
    if "возврат" in t or "аренда" in t or "дивиденд" in t:
        return DIVIDEND
    if t == "покупка" or "выдача займа" in t:
        return INVEST
    if "продажа" in t:
        return SALE
    return OTHER


def _generate_rent_rows(columns):
    """Аренда квартиры: $375 первого числа каждого месяца с фев-2025 по текущий.
    Генерится на стороне приложения (в таблицу не вносится), обновляется сама."""
    if "Дата" not in columns or "Сумма" not in columns:
        return pd.DataFrame(columns=columns)
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(start=RENT_START, end=today, freq="MS")
    rows = []
    for d in dates:
        row = {c: None for c in columns}
        row["Дата"] = d
        row["Сумма"] = RENT_MONTHLY
        if DEAL_TYPE_COL in row:
            row[DEAL_TYPE_COL] = RENT_LABEL
        if ASSET_COL in row:
            row[ASSET_COL] = "Недвижимость"
        if PROFIT_COL in row:
            row[PROFIT_COL] = RENT_MONTHLY
        if "Назначение" in row:
            row["Назначение"] = "Аренда квартиры в Новой Боровой"
        if "Контрагент" in row:
            row["Контрагент"] = "Рита"
        if "Объект" in row:
            row["Объект"] = "Новая Боровая"
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


# --- добавляем сгенерированную аренду и категорию ---
if "Дата" in df.columns:
    rent = _generate_rent_rows(list(df.columns))
    if not rent.empty:
        df = pd.concat([df, rent], ignore_index=True)
    df = df.sort_values("Дата", ascending=False).reset_index(drop=True)
df["Категория"] = df[DEAL_TYPE_COL].apply(_entity) if DEAL_TYPE_COL in df.columns else OTHER


def _fmt_pos(v):
    return f"${v:,.0f}".replace(",", " ")


def _fmt_signed(v):
    if pd.isna(v):
        return ""
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.0f}".replace(",", " ")


def _signed_amount(row):
    """Инвестиции — минус (отток), продажи и дивиденды — плюс (приток)."""
    amt = row.get("Сумма")
    if pd.isna(amt):
        return amt
    return -abs(amt) if row.get("Категория") == INVEST else abs(amt)


# Сегментированный pill-переключатель периода и лёгкая карточка фильтров —
# специфичны для этой страницы, остального (hero/kpi/card/section) хватает из theme.
EXTRA_CSS = """
<style>
.st-key-deals_period_bar [data-testid="stCaptionContainer"]{
  text-transform:uppercase;letter-spacing:.06em;font-weight:700;font-size:.68rem;color:#9ca3af;margin-bottom:6px;
}
.st-key-deals_period_bar div[data-testid="stHorizontalBlock"]{
  background:#f1f3f9;border-radius:14px;padding:5px;gap:4px !important;
}
.st-key-deals_period_bar [data-testid="stBaseButton-secondary"]{
  border:none !important;background:transparent !important;color:#6b7280 !important;
  border-radius:10px !important;font-weight:600 !important;box-shadow:none !important;
}
.st-key-deals_period_bar [data-testid="stBaseButton-primary"]{
  border:none !important;background:var(--grad) !important;color:#fff !important;
  border-radius:10px !important;font-weight:700 !important;
  box-shadow:0 6px 16px -6px rgba(34,197,94,.55) !important;
}
.st-key-deals_filters{background:#fafbff;border:1px solid #eef0f7;border-radius:16px;padding:16px 18px 2px;margin:18px 0 22px}
.tfo-yearcard{background:#fff;border:1px solid #eef0f7;border-radius:16px;padding:18px}
.tfo-yearcard-title{font-weight:700;font-size:.92rem;margin-bottom:14px;color:#374151}
.tfo-bar-row{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.tfo-bar-label{width:52px;flex-shrink:0;font-size:.82rem;color:#6b7280;font-weight:600}
.tfo-bar-track{flex:1;height:10px;background:#f1f3f9;border-radius:6px;overflow:hidden}
.tfo-bar-fill{height:100%;border-radius:6px}
.tfo-bar-value{width:92px;flex-shrink:0;text-align:right;font-size:.85rem;font-weight:700;color:#111827}
.tfo-yearcard-total{
  margin-top:6px;padding-top:10px;border-top:1px solid #eef0f7;
  display:flex;justify-content:space-between;font-weight:700;color:#111827;
}
</style>
"""

with page("deals", "📈", "Реестр сделок", "Инвестиции, продажи и дивиденды — в одном месте"):
    st.markdown(EXTRA_CSS, unsafe_allow_html=True)

    # ============================ Период ============================
    years = sorted(df["Дата"].dt.year.dropna().unique().astype(int)) if "Дата" in df.columns else []
    period_options = ["Все время"] + [str(y) for y in years]
    if st.session_state.get("deals_period") not in period_options:
        st.session_state["deals_period"] = "Все время"

    with st.container(key="deals_period_bar"):
        st.caption("Период")
        pcols = st.columns(len(period_options))
        for i, opt in enumerate(period_options):
            is_sel = st.session_state["deals_period"] == opt
            if pcols[i].button(opt, key=f"deals_period_{opt}", width="stretch",
                               type="primary" if is_sel else "secondary"):
                st.session_state["deals_period"] = opt
                st.rerun()
    period = st.session_state["deals_period"]

    # ============================ Фильтры ============================
    with st.container(key="deals_filters"):
        fc1, fc2 = st.columns(2)
        with fc1:
            asset_types = sorted(df[ASSET_COL].dropna().unique()) if ASSET_COL in df.columns else []
            selected_types = st.multiselect(ASSET_COL, asset_types, default=asset_types)
        with fc2:
            cats_present = [c for c in ENTITY_ORDER if c in set(df["Категория"])]
            selected_cats = st.multiselect("Категория", cats_present, default=cats_present)

    filtered = df.copy()
    if selected_types and ASSET_COL in filtered.columns:
        filtered = filtered[filtered[ASSET_COL].isin(selected_types)]
    if selected_cats:
        filtered = filtered[filtered["Категория"].isin(selected_cats)]
    if period != "Все время" and "Дата" in filtered.columns:
        filtered = filtered[filtered["Дата"].dt.year == int(period)]

    st.caption(f"Найдено сделок: {len(filtered)}")

    # ============================ KPI ============================
    def _cat_sum(cat):
        return filtered.loc[filtered["Категория"] == cat, "Сумма"].abs().sum() if "Сумма" in filtered.columns else 0

    profit_total = filtered[PROFIT_COL].sum() if PROFIT_COL in filtered.columns else 0
    profit_color = "#10b981" if profit_total >= 0 else "#ef4444"
    kpi_row([
        kpi_card("📉", "Инвестировано", _fmt_pos(_cat_sum(INVEST)), icon_bg="#fff7ed"),
        kpi_card("💰", "Продажи", _fmt_pos(_cat_sum(SALE)), icon_bg="#eff6ff"),
        kpi_card("💵", "Дивиденды", _fmt_pos(_cat_sum(DIVIDEND)), icon_bg="#ecfdf5"),
        kpi_card("🧮", "Чистая прибыль", _fmt_signed(profit_total), value_color=profit_color, icon_bg="#f5f3ff"),
    ])

    # ============================ Таблица ============================
    display = filtered.copy()
    if "Дата" in display.columns:
        display["Дата"] = display["Дата"].dt.strftime("%d.%m.%Y")
    if "Сумма" in filtered.columns:
        display["Сумма"] = filtered.apply(_signed_amount, axis=1).apply(_fmt_signed) if len(filtered) else filtered["Сумма"]
    if PROFIT_COL in display.columns:
        display = display.drop(columns=[PROFIT_COL])
    # «Категория» — вперёд, сразу после «Тип сделки»
    cols = list(display.columns)
    if "Категория" in cols:
        cols.remove("Категория")
        insert_at = cols.index(DEAL_TYPE_COL) + 1 if DEAL_TYPE_COL in cols else 0
        cols.insert(insert_at, "Категория")
        display = display[cols]

    def _style_row(row):
        styles = [""] * len(row)
        if "Категория" in row.index:
            color, bg = CATEGORY_COLORS.get(row["Категория"], CATEGORY_COLORS[OTHER])
            styles[row.index.get_loc("Категория")] = f"background-color:{bg};color:{color};font-weight:600"
        if "Сумма" in row.index:
            val = str(row["Сумма"]).strip()
            if val.startswith("-"):
                styles[row.index.get_loc("Сумма")] = "color:#ef4444;font-weight:600"
            elif val.startswith("$"):
                styles[row.index.get_loc("Сумма")] = "color:#10b981;font-weight:600"
        return styles

    with card("deals", "table"):
        st.dataframe(display.style.apply(_style_row, axis=1), width="stretch", hide_index=True)

    # ============================ По годам ============================
    st.divider()
    section_title("📊 По годам")

    def _year_rows(entity):
        src = df[df["Категория"] == entity]
        if selected_types and ASSET_COL in src.columns:
            src = src[src[ASSET_COL].isin(selected_types)]
        if src.empty or "Дата" not in src.columns:
            return []
        g = (src.assign(Год=src["Дата"].dt.year)
             .groupby("Год", as_index=False)["Сумма"].sum())
        g["Сумма"] = g["Сумма"].abs()
        g["Год"] = g["Год"].astype(int)
        return g.sort_values("Год").to_dict("records")

    def _year_bars_html(title, entity, color):
        rows = _year_rows(entity)
        if not rows:
            return (
                f"<div class='tfo-yearcard'><div class='tfo-yearcard-title'>{esc(title)}</div>"
                "<div style='color:#9ca3af;font-size:.85rem'>Нет данных</div></div>"
            )
        max_v = max(r["Сумма"] for r in rows) or 1
        total = sum(r["Сумма"] for r in rows)
        bars = "".join(
            "<div class='tfo-bar-row'>"
            f"<div class='tfo-bar-label'>{r['Год']}</div>"
            f"<div class='tfo-bar-track'><div class='tfo-bar-fill' "
            f"style='width:{r['Сумма'] / max_v * 100:.1f}%;background:{color}'></div></div>"
            f"<div class='tfo-bar-value'>{esc(_fmt_pos(r['Сумма']))}</div>"
            "</div>"
            for r in rows
        )
        return (
            f"<div class='tfo-yearcard'><div class='tfo-yearcard-title'>{esc(title)}</div>"
            f"{bars}"
            f"<div class='tfo-yearcard-total'><span>Итого</span><span>{esc(_fmt_pos(total))}</span></div>"
            "</div>"
        )

    yc1, yc2 = st.columns(2)
    with yc1:
        st.markdown(_year_bars_html("📉 Инвестировано по годам", INVEST, "#f59e0b"), unsafe_allow_html=True)
    with yc2:
        st.markdown(_year_bars_html("💵 Дивиденды по годам", DIVIDEND, "#10b981"), unsafe_allow_html=True)
