import pandas as pd
import streamlit as st

from data_source import load_deals, sidebar_refresh_control

sidebar_refresh_control()

st.title("📈 Реестр сделок")

df = load_deals()
if df is None:
    st.info("Нажми «Обновить данные» в боковой панели, чтобы загрузить таблицу.")
    st.stop()

if df.empty:
    st.warning("Лист «Сделки» пуст или не найден.")
    st.stop()

DEAL_TYPE_COL = "Тип сделки"
PROFIT_COL = "Чистая прибыль по сделке"
ASSET_COL = "Вид актива"

# Категории (сущности): Инвестиции (отток), Продажа, Дивиденды (притоки-возвраты)
INVEST, SALE, DIVIDEND, OTHER = "Инвестиции", "Продажа", "Дивиденды", "Прочее"
ENTITY_ORDER = [INVEST, SALE, DIVIDEND, OTHER]

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


# ============================ Период ============================
years = sorted(df["Дата"].dt.year.dropna().unique().astype(int)) if "Дата" in df.columns else []
period_options = ["Все время"] + [str(y) for y in years]
if st.session_state.get("deals_period") not in period_options:
    st.session_state["deals_period"] = "Все время"

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

# ============================ Метрики ============================
def _cat_sum(cat):
    return filtered.loc[filtered["Категория"] == cat, "Сумма"].abs().sum() if "Сумма" in filtered.columns else 0


m1, m2, m3, m4 = st.columns(4)
m1.metric("📉 Инвестировано", _fmt_pos(_cat_sum(INVEST)))
m2.metric("💰 Продажи", _fmt_pos(_cat_sum(SALE)))
m3.metric("💵 Дивиденды", _fmt_pos(_cat_sum(DIVIDEND)))
profit_total = filtered[PROFIT_COL].sum() if PROFIT_COL in filtered.columns else 0
m4.metric("🧮 Чистая прибыль по сделкам", _fmt_signed(profit_total))

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

st.dataframe(display, width="stretch", hide_index=True)

# ============================ По годам ============================
st.divider()
st.subheader("По годам")


def _yearly_table(entity):
    """Годовая сводка по категории (все годы, с учётом фильтра «Вид актива»)."""
    src = df[df["Категория"] == entity]
    if selected_types and ASSET_COL in src.columns:
        src = src[src[ASSET_COL].isin(selected_types)]
    if src.empty or "Дата" not in src.columns:
        return pd.DataFrame({"Год": [], "Сумма": []})
    g = (src.assign(Год=src["Дата"].dt.year)
         .groupby("Год", as_index=False)["Сумма"].sum())
    g["Сумма"] = g["Сумма"].abs()
    total = g["Сумма"].sum()
    g["Год"] = g["Год"].astype(int).astype(str)
    g["Сумма"] = g["Сумма"].apply(_fmt_pos)
    g = pd.concat([g, pd.DataFrame([{"Год": "Итого", "Сумма": _fmt_pos(total)}])], ignore_index=True)
    return g


yc1, yc2 = st.columns(2)
with yc1:
    st.markdown("**📉 Инвестировано по годам**")
    st.dataframe(_yearly_table(INVEST), width="stretch", hide_index=True)
with yc2:
    st.markdown("**💵 Дивиденды по годам**")
    st.dataframe(_yearly_table(DIVIDEND), width="stretch", hide_index=True)
