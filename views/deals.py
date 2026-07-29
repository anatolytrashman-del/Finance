import html

import pandas as pd
import plotly.express as px
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


def _table_html(columns, rows, badge_cols=None, color_cols=None, right_cols=None):
    """Кастомная HTML-таблица вместо st.dataframe — та же идея, что в
    theme.table() для страниц на общем модуле, но своя копия под cn-*
    палитру: эта страница самостоятельная и theme.py не импортирует.

    badge_cols: {col_key: {value: (bg, color)}} — скруглённая цветная плашка.
    color_cols: {col_key: fn(value) -> color_or_None} — просто красит текст.
    right_cols: набор col_key для выравнивания по правому краю.
    """
    badge_cols = badge_cols or {}
    color_cols = color_cols or {}
    right_cols = right_cols or set()
    head = "".join(
        f"<th class='cn-table-right'>{_esc(label)}</th>" if key in right_cols else f"<th>{_esc(label)}</th>"
        for key, label in columns
    )
    body = []
    for row in rows:
        cells = []
        for key, _label in columns:
            val = row.get(key, "")
            cls = " class='cn-table-right'" if key in right_cols else ""
            if key in badge_cols:
                bg, color = badge_cols[key].get(val, ("#F1EFEA", "#6b6f7a"))
                safe = _esc(val).replace("$", r"\$")
                cells.append(
                    f"<td{cls}><span style='display:inline-block;background:{bg};color:{color};"
                    "padding:4px 14px;border-radius:16px;font-size:.8rem;font-weight:700'>"
                    f"{safe}</span></td>"
                )
            elif key in color_cols:
                color = color_cols[key](val)
                style = f" style='color:{color};font-weight:600'" if color else ""
                cells.append(f"<td{cls}{style}>{_esc(val)}</td>")
            else:
                cells.append(f"<td{cls}>{_esc(val)}</td>")
        body.append(f"<tr>{''.join(cells)}</tr>")
    st.markdown(
        "<div class='cn-table-wrap'><table class='cn-table'>"
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>",
        unsafe_allow_html=True,
    )


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
/* Теги мультиселектов (Вид актива / Категория) — нейтральный цвет интерфейса
вместо тревожно-красного/акцентного, чтобы не выбивались из общей палитры. */
.st-key-deals_coinaco_filters [data-baseweb="tag"]{
  background-color:#E3E0D8 !important;color:#17171C !important;
}
.st-key-deals_coinaco_filters [data-baseweb="tag"] svg{fill:#17171C !important}

.cn-card{background:#fff;border-radius:20px;padding:22px;height:100%;box-sizing:border-box}
.cn-label{font-size:.72rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#9a9ca6}
.cn-big-number{font-size:2.1rem;font-weight:800;color:#17171C;letter-spacing:-.02em;margin-top:8px}
.cn-card-amt{color:#9a9ca6;font-size:.78rem;margin-top:2px}

.cn-section-title{font-weight:700;font-size:1rem;color:#17171C;margin-bottom:4px}

.st-key-deals_coinaco [class*="st-key-deals_coinaco_chart_"]{background:#fff;border-radius:20px;padding:20px 20px 6px;height:100%;box-sizing:border-box}
.st-key-deals_coinaco_table{background:#fff;border-radius:20px;padding:20px}

.cn-table-wrap{overflow-x:auto}
.cn-table{width:100%;border-collapse:collapse}
.cn-table th{
  text-align:left;font-size:.68rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.05em;color:#9a9ca6;padding:0 14px 10px;white-space:nowrap;
}
.cn-table td{padding:12px 14px;font-size:.87rem;color:#17171C;border-top:1px solid #F1EFEA;white-space:nowrap}
.cn-table tr:first-child td{border-top:none}
.cn-table th.cn-table-right, .cn-table td.cn-table-right{text-align:right}
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
    dividends_sum = _cat_sum(DIVIDEND)
    profit_total = filtered[PROFIT_COL].sum() if PROFIT_COL in filtered.columns else 0

    # ---------------- Row 1: четыре отдельные карточки-цифры ----------------
    period_label = "за всё время" if period == "Все время" else f"за {period}"
    profit_color = "#1DBF73" if profit_total >= 0 else "#E5484D"

    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
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
    with r1c4:
        st.markdown(
            "<div class='cn-card'>"
            "<div class='cn-label'>Дивиденды</div>"
            f"<div class='cn-big-number'>{_esc(_fmt_pos(dividends_sum))}</div>"
            f"<div class='cn-card-amt'>{_esc(period_label)}</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ---------------- Row 2: Инвестировано / Дивиденды по годам ----------------
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

    def _year_bar_chart(container_key, title, entity, bar_color):
        with st.container(key=container_key):
            st.markdown(f"<div class='cn-section-title'>{_esc(title)}</div>", unsafe_allow_html=True)
            rows = _year_rows(entity, df)
            if not rows:
                st.markdown("<div style='color:#9a9ca6;font-size:.85rem'>Нет данных</div>", unsafe_allow_html=True)
                return
            year_df = pd.DataFrame(rows)
            total_all = year_df["Сумма"].sum()
            st.markdown(
                f"<div class='cn-card-amt' style='margin-bottom:6px'>{_esc(_fmt_pos(total_all))} всего</div>",
                unsafe_allow_html=True,
            )
            latest_year = year_df["Год"].max()
            bar_colors = [bar_color if y == latest_year else "#E3E0D8" for y in year_df["Год"]]
            fig = px.bar(year_df, x="Год", y="Сумма")
            fig.update_traces(
                marker_color=bar_colors,
                customdata=year_df["Сумма"].apply(_fmt_pos),
                hovertemplate="<b>%{x}</b><br>%{customdata}<extra></extra>",
            )
            fig.update_xaxes(type="category", title=None)
            fig.update_yaxes(title="$")
            fig.update_layout(
                margin=dict(l=10, r=10, t=10, b=10), height=280,
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    r2c1, r2c2 = st.columns(2)
    with r2c1:
        _year_bar_chart("deals_coinaco_chart_invested", "Инвестировано по годам", INVEST, "#1DBF73")
    with r2c2:
        _year_bar_chart("deals_coinaco_chart_dividends", "Дивиденды по годам", DIVIDEND, "#3B82F6")

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

    _category_badge_colors = {cat: (bg, color) for cat, (color, bg) in CATEGORY_COLORS.items()}

    def _amount_color(val):
        val = str(val).strip()
        if val.startswith("-"):
            return "#E5484D"
        if val.startswith("$"):
            return "#1DBF73"
        return None

    with st.container(key="deals_coinaco_table"):
        st.markdown("<div class='cn-section-title' style='margin-bottom:12px'>Все сделки</div>", unsafe_allow_html=True)
        _table_html(
            [(c, c) for c in display.columns],
            display.to_dict("records"),
            badge_cols={"Категория": _category_badge_colors},
            color_cols={"Сумма": _amount_color},
            right_cols={"Сумма"},
        )
