import pandas as pd
import streamlit as st

from data_source import get_workbook, sidebar_refresh_control
from parsers import parse_area, parse_money, parse_real_estate

sidebar_refresh_control()

st.title("🏠 Портфолио объектов недвижимости")

wb = get_workbook()
if wb is None:
    st.info("Нажми «Обновить данные» в боковой панели, чтобы загрузить таблицу.")
    st.stop()

df = parse_real_estate(wb)

if df.empty:
    st.warning("Лист «Real Estate» пуст или не найден.")
    st.stop()

TYPE_COL = "Тип"
AREA_COL = "Площадь"
PURCHASE_COL = "Сумма покупки в $"
MARKET_COL = "Примерная рыночная стоимость в $"
LIABILITIES_COL = "Обязательства"
GROWTH_COL = "% прироста"


def _fmt_money(v):
    if pd.isna(v):
        return ""
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.0f}".replace(",", " ")


purchase = df[PURCHASE_COL].apply(parse_money) if PURCHASE_COL in df.columns else pd.Series(dtype=float)
market = df[MARKET_COL].apply(parse_money) if MARKET_COL in df.columns else pd.Series(dtype=float)
liabilities = df[LIABILITIES_COL].apply(parse_money) if LIABILITIES_COL in df.columns else pd.Series(dtype=float)

growth_pct = (market - purchase) / purchase.replace(0, pd.NA) * 100

def _fmt_plain(v):
    if pd.isna(v):
        return ""
    if isinstance(v, float):
        if v == int(v):
            return f"{int(v):,}".replace(",", " ")
        return f"{v:,.2f}".replace(",", " ")
    return str(v)


display = df.copy()
special_cols = {PURCHASE_COL, MARKET_COL, LIABILITIES_COL}
for col in display.columns:
    if col not in special_cols:
        display[col] = display[col].apply(_fmt_plain)
if PURCHASE_COL in display.columns:
    display[PURCHASE_COL] = purchase.apply(_fmt_money)
if MARKET_COL in display.columns:
    display[MARKET_COL] = market.apply(_fmt_money)
if LIABILITIES_COL in display.columns:
    display[LIABILITIES_COL] = liabilities.apply(_fmt_money)
display[GROWTH_COL] = growth_pct.apply(lambda v: f"{v:+.1f}%" if pd.notna(v) else "—")

# Столбец % прироста сразу после "Обязательства"
cols = [c for c in display.columns if c != GROWTH_COL]
insert_at = cols.index(LIABILITIES_COL) + 1 if LIABILITIES_COL in cols else len(cols)
cols.insert(insert_at, GROWTH_COL)
display = display[cols]

# Итоговая строка
areas = df[AREA_COL].apply(parse_area) if AREA_COL in df.columns else pd.Series(dtype=object)
total_hectares = sum(a["value"] for a in areas if a and a["unit"] == "Га")
total_concrete = sum(a["value"] for a in areas if a and a["unit"] == "м²")
area_parts = []
if total_hectares > 0:
    area_parts.append(f"{total_hectares:.1f} Га земли")
if total_concrete > 0:
    area_parts.append(f"{total_concrete:,.0f} м² бетона".replace(",", " "))
area_summary = " + ".join(area_parts) if area_parts else "—"

total_purchase = purchase.sum(skipna=True)
total_market = market.sum(skipna=True)
total_liabilities = liabilities.sum(skipna=True)
total_growth = (total_market - total_purchase) / total_purchase * 100 if total_purchase else None

totals_row = {c: "" for c in display.columns}
if TYPE_COL in totals_row:
    totals_row[TYPE_COL] = "ИТОГО"
if AREA_COL in totals_row:
    totals_row[AREA_COL] = area_summary
if PURCHASE_COL in totals_row:
    totals_row[PURCHASE_COL] = _fmt_money(total_purchase)
if MARKET_COL in totals_row:
    totals_row[MARKET_COL] = _fmt_money(total_market)
if LIABILITIES_COL in totals_row:
    totals_row[LIABILITIES_COL] = _fmt_money(total_liabilities)
totals_row[GROWTH_COL] = f"{total_growth:+.1f}%" if total_growth is not None else "—"

display_with_totals = pd.concat([display, pd.DataFrame([totals_row])], ignore_index=True)

st.caption(f"Объектов: {len(df)}")
st.dataframe(display_with_totals, width="stretch", hide_index=True)

for _, row in df.iterrows():
    title = row.get(TYPE_COL, "Объект")
    location = row.get("Локация", "")
    with st.expander(f"{title} — {location}"):
        for col in df.columns:
            value = row.get(col)
            if value is not None and str(value).strip() not in ("", "None", "nan"):
                st.write(f"**{col}:** {value}")
