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
CATEGORY_ICONS = {INVEST: "🏠", SALE: "💰", DIVIDEND: "💵", OTHER: "📄"}

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
    """HTML-экранирование для значений, вставляемых в сырые HTML-блоки (карточки) —
    это блочный HTML, а не markdown-текст, так что $ там не читается как LaTeX,
    а вот < и & — небезопасны."""
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


def _deal_label(row):
    """Заголовок строки в списке «Сделки» — «Покупка»/«Продажа» сами по себе не
    говорят, о какой сделке речь, поэтому дополняем конкретикой: объект,
    назначение или вид актива, что найдётся первым."""
    deal_type = str(row.get(DEAL_TYPE_COL) or "").strip()
    detail = None
    for col in ("Объект", "Назначение", ASSET_COL):
        v = row.get(col)
        if v is not None and str(v).strip() and str(v).strip().lower() != "nan":
            detail = str(v).strip()
            break
    if deal_type and detail and detail.lower() != deal_type.lower():
        return f"{deal_type} · {detail}"
    return detail or deal_type or "Сделка"


# ============================ Coinaco-style дизайн (финальный стиль платформы) ============================
# Самостоятельная вёрстка (тот же приём, что и в views/dashboard.py) — своя
# CSS-палитра токенов под ключом страницы, без завязки на общий theme.py.
COINACO_CSS = """
<style>
.st-key-deals_coinaco{background:#EFEDE8;border-radius:28px;padding:26px 26px 24px}
.st-key-deals_coinaco .cn-hero-title{font-size:1.9rem;font-weight:700;color:#17171C;letter-spacing:-.01em}
.st-key-deals_coinaco .cn-hero-sub{color:#8b8d98;font-size:.88rem;margin-top:2px}

.st-key-deals_coinaco_period div[data-testid="stHorizontalBlock"]{
  background:#fff;border-radius:999px;padding:5px;gap:4px !important;
}
.st-key-deals_coinaco_period [data-testid="stBaseButton-secondary"]{
  border:none !important;background:transparent !important;color:#6b6f7a !important;
  border-radius:999px !important;font-weight:600 !important;box-shadow:none !important;
}
.st-key-deals_coinaco_period [data-testid="stBaseButton-primary"]{
  border:none !important;background:#17171C !important;color:#fff !important;
  border-radius:999px !important;font-weight:700 !important;
}

.st-key-deals_coinaco_filters{
  background:rgba(255,255,255,.6);border-radius:20px;padding:14px 18px 2px;margin:14px 0 6px;
}

.cn-card{background:#fff;border-radius:20px;padding:22px;height:100%;box-sizing:border-box}
.cn-label{font-size:.72rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#9a9ca6}
.cn-big-number{font-size:2.1rem;font-weight:800;color:#17171C;letter-spacing:-.02em;margin-top:8px}
.cn-card-amt{color:#9a9ca6;font-size:.78rem;margin-top:2px}

.cn-section-title{font-weight:700;font-size:1rem;color:#17171C;margin-bottom:4px}

.cn-tx-row{display:flex;align-items:center;justify-content:space-between;padding:9px 0;border-bottom:1px solid #F1EFEA}
.cn-tx-row:last-child{border-bottom:none}
.cn-tx-left{display:flex;align-items:center;gap:11px;min-width:0}
.cn-tx-icon{width:36px;height:36px;border-radius:50%;background:#F1EFEA;display:flex;align-items:center;
  justify-content:center;font-size:16px;flex-shrink:0}
.cn-tx-text{min-width:0}
.cn-tx-name{font-weight:700;color:#17171C;font-size:.85rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px}
.cn-tx-date{color:#9a9ca6;font-size:.72rem}
.cn-tx-amount{font-weight:700;font-size:.85rem;flex-shrink:0;padding-left:10px;text-align:right}
.cn-tx-amount.pos{color:#1DBF73}
.cn-tx-amount.neg{color:#17171C}

.cn-minibar-row{display:flex;align-items:flex-end;gap:7px;height:96px;margin-top:16px}
.cn-minibar{flex:1;border-radius:8px 8px 3px 3px;background:#F1EFEA;min-height:4px}
.cn-minibar.active{background:#1DBF73}
.cn-minibar-labels{display:flex;gap:7px;margin-top:7px}
.cn-minibar-labels span{flex:1;text-align:center;font-size:.7rem;color:#6b6f7a;font-weight:600}

.st-key-deals_coinaco_table{background:#fff;border-radius:20px;padding:20px}
</style>
"""

with st.container(key="deals_coinaco"):
    st.markdown(COINACO_CSS, unsafe_allow_html=True)

    st.markdown(
        "<div class='cn-hero-title'>Реестр сделок</div>"
        "<div class='cn-hero-sub'>Инвестиции, продажи и дивиденды — в одном месте</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    # ============================ Период ============================
    years = sorted(df["Дата"].dt.year.dropna().unique().astype(int)) if "Дата" in df.columns else []
    period_options = ["Все время"] + [str(y) for y in years]
    if st.session_state.get("deals_period") not in period_options:
        st.session_state["deals_period"] = "Все время"

    with st.container(key="deals_coinaco_period"):
        pcols = st.columns(len(period_options))
        for i, opt in enumerate(period_options):
            is_sel = st.session_state["deals_period"] == opt
            if pcols[i].button(opt, key=f"cn_period_{opt}", width="stretch",
                               type="primary" if is_sel else "secondary"):
                st.session_state["deals_period"] = opt
                st.rerun()
    period = st.session_state["deals_period"]

    # ============================ Фильтры ============================
    with st.container(key="deals_coinaco_filters"):
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

    st.markdown(
        f"<div style='color:#9a9ca6;font-size:.85rem;margin:14px 0 16px'>Найдено сделок: {len(filtered)}</div>",
        unsafe_allow_html=True,
    )

    def _cat_sum(cat):
        return filtered.loc[filtered["Категория"] == cat, "Сумма"].abs().sum() if "Сумма" in filtered.columns else 0

    invested = _cat_sum(INVEST)
    sold_sum = _cat_sum(SALE)
    profit_total = filtered[PROFIT_COL].sum() if PROFIT_COL in filtered.columns else 0

    # ---------------- Row 1: три отдельные карточки-цифры ----------------
    period_label = "за всё время" if period == "Все время" else f"за {period}"
    profit_color = "#1DBF73" if profit_total >= 0 else "#E5484D"

    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        st.markdown(
            "<div class='cn-card'>"
            "<div class='cn-label'>Чистая прибыль</div>"
            f"<div class='cn-big-number' style='color:{profit_color}'>{_esc(_fmt_signed(profit_total))}</div>"
            f"<div class='cn-card-amt'>{_esc(period_label)}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with r1c2:
        st.markdown(
            "<div class='cn-card'>"
            "<div class='cn-label'>Инвестировано</div>"
            f"<div class='cn-big-number'>{_esc(_fmt_pos(invested))}</div>"
            f"<div class='cn-card-amt'>{_esc(period_label)}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with r1c3:
        st.markdown(
            "<div class='cn-card'>"
            "<div class='cn-label'>Продано</div>"
            f"<div class='cn-big-number'>{_esc(_fmt_pos(sold_sum))}</div>"
            f"<div class='cn-card-amt'>{_esc(period_label)}</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ---------------- Row 2: Инвестировано по годам / Сделки ----------------
    def _year_rows(entity, src_df):
        src = src_df[src_df["Категория"] == entity]
        if selected_types and ASSET_COL in src.columns:
            src = src[src[ASSET_COL].isin(selected_types)]
        if src.empty or "Дата" not in src.columns:
            return []
        g = (src.assign(Год=src["Дата"].dt.year)
             .groupby("Год", as_index=False)["Сумма"].sum())
        g["Сумма"] = g["Сумма"].abs()
        g["Год"] = g["Год"].astype(int)
        return g.sort_values("Год").to_dict("records")

    r2c1, r2c2 = st.columns([1, 1.2])

    with r2c1:
        inv_years = _year_rows(INVEST, df)
        max_v = max((r["Сумма"] for r in inv_years), default=0) or 1
        bars_html = "".join(
            f"<div class='cn-minibar{' active' if r['Год'] == inv_years[-1]['Год'] else ''}' "
            f"style='height:{max(r['Сумма'] / max_v * 100, 4):.0f}%'></div>"
            for r in inv_years
        )
        labels_html = "".join(f"<span>{r['Год']}</span>" for r in inv_years)
        total_invested_all = sum(r["Сумма"] for r in inv_years)
        no_bars_html = "<div style='color:#9a9ca6;font-size:.8rem'>Нет данных</div>"
        st.markdown(
            "<div class='cn-card'>"
            "<div class='cn-section-title'>Инвестировано по годам</div>"
            f"<div class='cn-card-amt'>{_esc(_fmt_pos(total_invested_all))} всего</div>"
            f"<div class='cn-minibar-row'>{bars_html or no_bars_html}</div>"
            f"<div class='cn-minibar-labels'>{labels_html}</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    with r2c2:
        recent = filtered.sort_values("Дата", ascending=False).head(5) if "Дата" in filtered.columns else filtered.head(5)
        rows_html = []
        for _, row in recent.iterrows():
            cat = row.get("Категория", OTHER)
            icon = CATEGORY_ICONS.get(cat, "📄")
            name = _deal_label(row)
            date_str = row["Дата"].strftime("%d.%m.%Y") if pd.notna(row.get("Дата")) else ""
            signed = _signed_amount(row)
            amount_str = _fmt_signed(signed) if pd.notna(signed) else "—"
            cls = "pos" if (pd.notna(signed) and signed >= 0) else "neg"
            rows_html.append(
                "<div class='cn-tx-row'>"
                "<div class='cn-tx-left'>"
                f"<div class='cn-tx-icon'>{icon}</div>"
                f"<div class='cn-tx-text'><div class='cn-tx-name'>{_esc(name)}</div>"
                f"<div class='cn-tx-date'>{_esc(date_str)}</div></div>"
                "</div>"
                f"<div class='cn-tx-amount {cls}'>{_esc(amount_str)}</div>"
                "</div>"
            )
        rows_joined = "".join(rows_html)
        no_rows_html = "<div style='color:#9a9ca6;font-size:.85rem;margin-top:10px'>Нет сделок</div>"
        st.markdown(
            "<div class='cn-card'>"
            "<div class='cn-section-title'>Сделки</div>"
            f"{rows_joined or no_rows_html}"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

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

    with st.container(key="deals_coinaco_table"):
        st.markdown("<div class='cn-section-title' style='margin-bottom:12px'>Все сделки</div>", unsafe_allow_html=True)
        st.dataframe(display.style.apply(_style_row, axis=1), width="stretch", hide_index=True)
