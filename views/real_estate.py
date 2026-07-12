import json
import re

import pandas as pd
import streamlit as st

from config import YANDEX_MAPS_API_KEY
from data_source import get_workbook, sidebar_refresh_control
from parsers import parse_area, parse_money, parse_real_estate, parse_real_estate_sold

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
PAID_COL = "Оплачено %"
COORDS_COL = "Координаты"


COORDS_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


def _build_map_objects(df):
    """Строит метки карты из технической колонки COORDS_COL (формат 'lat, lon').

    Объекты с одинаковыми координатами (например, несколько объектов в одном доме)
    объединяются в одну метку со списком внутри."""
    missing = []
    groups = {}
    for _, row in df.iterrows():
        title = str(row.get("Тип") or "Объект")
        location = str(row.get("Локация") or "").strip()
        raw_coords = str(row.get(COORDS_COL) or "").strip()
        match = COORDS_RE.match(raw_coords)
        if not match:
            missing.append(f"{title} — {location or 'без локации'}")
            continue
        key = (round(float(match.group(1)), 6), round(float(match.group(2)), 6))
        status = str(row.get("Статус") or "").strip()
        address = str(row.get("Точный адрес") or "").strip()
        group = groups.setdefault(key, {"location": location, "address": address, "items": []})
        group["items"].append({"title": title, "status": status})

    objects = []
    for (lat, lon), group in groups.items():
        items = group["items"]
        header = items[0]["title"] if len(items) == 1 else f"{len(items)} объекта на одном адресе"
        lines = [p for p in [group["location"], group["address"]] if p]
        for item in items:
            line = f"<b>{item['title']}</b>"
            if item["status"]:
                line += f" — {item['status']}"
            lines.append(line)
        objects.append({"title": header, "coords": [lat, lon], "info": "<br>".join(lines)})
    return objects, missing


def _build_map_html(objects, api_key):
    data_json = json.dumps(objects, ensure_ascii=False)
    return f"""
<div id="realty-map" style="width:100%;height:520px;border-radius:8px;overflow:hidden;"></div>
<script src="https://api-maps.yandex.ru/2.1/?apikey={api_key}&lang=ru_RU"></script>
<script>
  var objects = {data_json};
  ymaps.ready(function () {{
    var map = new ymaps.Map("realty-map", {{
      center: [53.9, 27.5667],
      zoom: 10,
      controls: ["zoomControl", "fullscreenControl"]
    }});
    objects.forEach(function (obj) {{
      var placemark = new ymaps.Placemark(obj.coords, {{
        balloonContentHeader: obj.title,
        balloonContentBody: obj.info
      }}, {{
        preset: "islands#blueHomeIcon"
      }});
      map.geoObjects.add(placemark);
    }});
    if (map.geoObjects.getLength() > 0) {{
      map.setBounds(map.geoObjects.getBounds(), {{checkZoomRange: true, zoomMargin: 40}});
    }}
  }});
</script>
"""


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
if COORDS_COL in display.columns:
    display = display.drop(columns=[COORDS_COL])
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

paid_pct = ((purchase - liabilities.abs()) / purchase.replace(0, pd.NA) * 100).clip(lower=0, upper=100)
display[PAID_COL] = paid_pct

# Столбцы "% прироста" и "Оплачено %" сразу после "Обязательства"
cols = [c for c in display.columns if c not in (GROWTH_COL, PAID_COL)]
insert_at = cols.index(LIABILITIES_COL) + 1 if LIABILITIES_COL in cols else len(cols)
cols.insert(insert_at, GROWTH_COL)
cols.insert(insert_at + 1, PAID_COL)
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

total_paid_pct = float("nan")
if total_purchase:
    total_paid_pct = max(0.0, min(100.0, (total_purchase - abs(total_liabilities)) / total_purchase * 100))
totals_row[PAID_COL] = total_paid_pct

display_with_totals = pd.concat([display, pd.DataFrame([totals_row])], ignore_index=True)

st.caption(f"Объектов: {len(df)}")

# Сначала общая таблица
st.dataframe(
    display_with_totals,
    width="stretch",
    hide_index=True,
    column_config={
        PAID_COL: st.column_config.ProgressColumn("Оплачено", format="%.0f%%", min_value=0, max_value=100)
    },
)

# Затем карта
st.subheader("Карта объектов")
map_objects, missing_coords = _build_map_objects(df)
if map_objects and YANDEX_MAPS_API_KEY:
    st.components.v1.html(_build_map_html(map_objects, YANDEX_MAPS_API_KEY), height=530)
if missing_coords:
    st.warning(
        "Нет координат (заполни столбец «Координаты» в формате lat, lon):\n"
        + "\n".join(f"- {a}" for a in missing_coords)
    )

for _, row in df.iterrows():
    title = row.get(TYPE_COL, "Объект")
    location = row.get("Локация", "")
    with st.expander(f"{title} — {location}"):
        for col in df.columns:
            if col == COORDS_COL:
                continue
            value = row.get(col)
            if value is not None and str(value).strip() not in ("", "None", "nan"):
                safe_col = str(col).replace("$", r"\$")
                safe_value = str(value).replace("$", r"\$")
                st.write(f"**{safe_col}:** {safe_value}")

# Проданные объекты — внизу страницы
sold = parse_real_estate_sold(wb)
if not sold.empty:
    SALE_COL = "Цена продажи"
    PROFIT_COL = "Прибыль"
    YIELD_COL = "Доходность"

    s_purchase = sold[PURCHASE_COL].apply(parse_money) if PURCHASE_COL in sold.columns else pd.Series(dtype=float)
    s_sale = sold[SALE_COL].apply(parse_money) if SALE_COL in sold.columns else pd.Series(dtype=float)
    s_profit = sold[PROFIT_COL].apply(parse_money) if PROFIT_COL in sold.columns else pd.Series(dtype=float)
    s_yield = s_profit / s_purchase.replace(0, pd.NA) * 100

    sdisp = sold.copy()
    if COORDS_COL in sdisp.columns:
        sdisp = sdisp.drop(columns=[COORDS_COL])
    money_cols = {PURCHASE_COL, SALE_COL, PROFIT_COL}
    for col in sdisp.columns:
        if col not in money_cols:
            sdisp[col] = sdisp[col].apply(_fmt_plain)
    if PURCHASE_COL in sdisp.columns:
        sdisp[PURCHASE_COL] = s_purchase.apply(_fmt_money)
    if SALE_COL in sdisp.columns:
        sdisp[SALE_COL] = s_sale.apply(_fmt_money)
    if PROFIT_COL in sdisp.columns:
        sdisp[PROFIT_COL] = s_profit.apply(_fmt_money)
    sdisp[YIELD_COL] = s_yield.apply(lambda v: f"{v:+.1f}%" if pd.notna(v) else "—")

    # Доходность сразу после "Прибыль"
    scols = [c for c in sdisp.columns if c != YIELD_COL]
    s_insert = scols.index(PROFIT_COL) + 1 if PROFIT_COL in scols else len(scols)
    scols.insert(s_insert, YIELD_COL)
    sdisp = sdisp[scols]

    # Итоговая строка
    st_purchase = s_purchase.sum(skipna=True)
    st_sale = s_sale.sum(skipna=True)
    st_profit = s_profit.sum(skipna=True)
    st_yield = st_profit / st_purchase * 100 if st_purchase else None
    s_totals = {c: "" for c in sdisp.columns}
    s_totals[TYPE_COL] = "ИТОГО"
    s_totals[PURCHASE_COL] = _fmt_money(st_purchase)
    s_totals[SALE_COL] = _fmt_money(st_sale)
    s_totals[PROFIT_COL] = _fmt_money(st_profit)
    s_totals[YIELD_COL] = f"{st_yield:+.1f}%" if st_yield is not None else "—"
    sdisp_totals = pd.concat([sdisp, pd.DataFrame([s_totals])], ignore_index=True)

    st.divider()
    st.subheader("💰 Проданные объекты")
    st.dataframe(sdisp_totals, width="stretch", hide_index=True)
