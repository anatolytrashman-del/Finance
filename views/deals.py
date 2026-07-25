import html

import pandas as pd
import streamlit as st

from data_source import load_deals, sidebar_refresh_control
from rates_widget import render_sidebar_rates

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


def _esc(text):
    """HTML-экранирование для значений, которые вставляются в сырые HTML-блоки
    (карточки KPI, годовые бары) — это блочный HTML, а не markdown-текст, так что
    $ там не читается как LaTeX и трюк с «\\$» не нужен, а вот < и & — небезопасны."""
    return html.escape(str(text))


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


# ============================ Дизайн-система страницы ============================
PAGE_CSS = """
<style>
.st-key-deals_futuristic{ --grad: linear-gradient(135deg, #6D5DF6 0%, #3B82F6 55%, #14B8A6 100%); }

.st-key-deals_futuristic .tfo-hero{display:flex;align-items:center;gap:16px;margin:2px 0 26px}
.st-key-deals_futuristic .tfo-hero-icon{
  width:56px;height:56px;border-radius:16px;background:var(--grad);
  display:flex;align-items:center;justify-content:center;font-size:26px;
  box-shadow:0 10px 28px -10px rgba(59,130,246,.55);
}
.st-key-deals_futuristic .tfo-hero-title{
  font-size:2.1rem;font-weight:800;letter-spacing:-.02em;line-height:1.1;
  background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent;
}
.st-key-deals_futuristic .tfo-hero-sub{color:#6b7280;font-size:.92rem;margin-top:3px}

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
  box-shadow:0 6px 16px -6px rgba(59,130,246,.55) !important;
}

.st-key-deals_filters{background:#fafbff;border:1px solid #eef0f7;border-radius:16px;padding:16px 18px 2px;margin:18px 0 22px}

.tfo-kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:26px}
.tfo-kpi{
  position:relative;background:#fff;border:1px solid #eef0f7;border-radius:16px;
  padding:18px 18px 16px;box-shadow:0 2px 10px -4px rgba(15,23,42,.06);overflow:hidden;
}
.tfo-kpi::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--kpi-color)}
.tfo-kpi-icon{
  width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;
  background:var(--kpi-bg);font-size:16px;margin-bottom:10px;
}
.tfo-kpi-label{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#9ca3af;margin-bottom:4px}
.tfo-kpi-value{font-size:1.5rem;font-weight:800;color:#111827;letter-spacing:-.01em}

.st-key-deals_table_card{background:#fff;border:1px solid #eef0f7;border-radius:16px;padding:6px;box-shadow:0 2px 10px -4px rgba(15,23,42,.05)}
.st-key-deals_table_card [data-testid="stDataFrame"]{border-radius:12px;overflow:hidden}

.tfo-section-title{font-size:1.05rem;font-weight:800;color:#111827;margin:6px 0 14px}

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

with st.container(key="deals_futuristic"):
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
    st.markdown(
        "<div class='tfo-hero'>"
        "<div class='tfo-hero-icon'>📈</div>"
        "<div><div class='tfo-hero-title'>Реестр сделок</div>"
        "<div class='tfo-hero-sub'>Инвестиции, продажи и дивиденды — в одном месте</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )

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

    def _kpi(icon, label, value, color, bg, value_color=None):
        vc = f"color:{value_color};" if value_color else ""
        return (
            f"<div class='tfo-kpi' style='--kpi-color:{color};--kpi-bg:{bg}'>"
            f"<div class='tfo-kpi-icon'>{icon}</div>"
            f"<div class='tfo-kpi-label'>{label}</div>"
            f"<div class='tfo-kpi-value' style='{vc}'>{_esc(value)}</div>"
            "</div>"
        )

    profit_total = filtered[PROFIT_COL].sum() if PROFIT_COL in filtered.columns else 0
    profit_color = "#10b981" if profit_total >= 0 else "#ef4444"
    kpi_html = "<div class='tfo-kpi-row'>" + "".join([
        _kpi("📉", "Инвестировано", _fmt_pos(_cat_sum(INVEST)), "#f59e0b", "#fff7ed"),
        _kpi("💰", "Продажи", _fmt_pos(_cat_sum(SALE)), "#3b82f6", "#eff6ff"),
        _kpi("💵", "Дивиденды", _fmt_pos(_cat_sum(DIVIDEND)), "#10b981", "#ecfdf5"),
        _kpi("🧮", "Чистая прибыль", _fmt_signed(profit_total), "#8b5cf6", "#f5f3ff", value_color=profit_color),
    ]) + "</div>"
    st.markdown(kpi_html, unsafe_allow_html=True)

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

    with st.container(key="deals_table_card"):
        st.dataframe(display.style.apply(_style_row, axis=1), width="stretch", hide_index=True)

    # ============================ По годам ============================
    st.divider()
    st.markdown("<div class='tfo-section-title'>📊 По годам</div>", unsafe_allow_html=True)

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
                f"<div class='tfo-yearcard'><div class='tfo-yearcard-title'>{_esc(title)}</div>"
                "<div style='color:#9ca3af;font-size:.85rem'>Нет данных</div></div>"
            )
        max_v = max(r["Сумма"] for r in rows) or 1
        total = sum(r["Сумма"] for r in rows)
        bars = "".join(
            "<div class='tfo-bar-row'>"
            f"<div class='tfo-bar-label'>{r['Год']}</div>"
            f"<div class='tfo-bar-track'><div class='tfo-bar-fill' "
            f"style='width:{r['Сумма'] / max_v * 100:.1f}%;background:{color}'></div></div>"
            f"<div class='tfo-bar-value'>{_esc(_fmt_pos(r['Сумма']))}</div>"
            "</div>"
            for r in rows
        )
        return (
            f"<div class='tfo-yearcard'><div class='tfo-yearcard-title'>{_esc(title)}</div>"
            f"{bars}"
            f"<div class='tfo-yearcard-total'><span>Итого</span><span>{_esc(_fmt_pos(total))}</span></div>"
            "</div>"
        )

    yc1, yc2 = st.columns(2)
    with yc1:
        st.markdown(_year_bars_html("📉 Инвестировано по годам", INVEST, "#f59e0b"), unsafe_allow_html=True)
    with yc2:
        st.markdown(_year_bars_html("💵 Дивиденды по годам", DIVIDEND, "#10b981"), unsafe_allow_html=True)
