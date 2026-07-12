import json
import re

import pandas as pd
import requests
import streamlit as st

from config import YANDEX_GEOCODER_API_KEY, YANDEX_MAPS_API_KEY
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
PAID_COL = "Оплачено %"


COORDS_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


@st.cache_data(show_spinner=False)
def _geocode_address(address: str, api_key: str):
    """Возвращает [lat, lon] через HTTP Geocoder API Яндекса или None, если не нашёл."""
    try:
        resp = requests.get(
            "https://geocode-maps.yandex.ru/1.x/",
            params={
                "apikey": api_key,
                "format": "json",
                "geocode": address,
                "lang": "ru_RU",
                "results": 1,
            },
            timeout=10,
        )
        resp.raise_for_status()
        members = resp.json()["response"]["GeoObjectCollection"]["featureMember"]
        if not members:
            return None
        pos = members[0]["GeoObject"]["Point"]["pos"]  # "lon lat"
        lon_str, lat_str = pos.split()
        return [float(lat_str), float(lon_str)]
    except Exception:
        return None


def _build_map_objects(df, geocoder_key):
    objects, failed = [], []
    for _, row in df.iterrows():
        addr_raw = str(row.get("Точный адрес") or "").strip()
        location = str(row.get("Локация") or "").strip()
        title = str(row.get("Тип") or "Объект")
        coords_match = COORDS_RE.match(addr_raw)
        query = ", ".join(p for p in [location, addr_raw] if p)
        if coords_match:
            coords = [float(coords_match.group(1)), float(coords_match.group(2))]
        elif query and geocoder_key:
            coords = _geocode_address(query, geocoder_key)
        else:
            coords = None
        if coords is None:
            failed.append(f"{title} — {query or 'адрес не указан'}")
            continue
        info_parts = [p for p in [location, addr_raw, str(row.get("Статус") or "").strip()] if p]
        objects.append({"title": title, "coords": coords, "info": "<br>".join(info_parts)})
    return objects, failed


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

map_objects, failed_addresses = _build_map_objects(df, YANDEX_GEOCODER_API_KEY)
if map_objects and YANDEX_MAPS_API_KEY:
    st.components.v1.html(_build_map_html(map_objects, YANDEX_MAPS_API_KEY), height=530)
if failed_addresses:
    st.warning("Не нашёл на карте:\n" + "\n".join(f"- {a}" for a in failed_addresses))

st.dataframe(
    display_with_totals,
    width="stretch",
    hide_index=True,
    column_config={
        PAID_COL: st.column_config.ProgressColumn("Оплачено", format="%.0f%%", min_value=0, max_value=100)
    },
)

for _, row in df.iterrows():
    title = row.get(TYPE_COL, "Объект")
    location = row.get("Локация", "")
    with st.expander(f"{title} — {location}"):
        for col in df.columns:
            value = row.get(col)
            if value is not None and str(value).strip() not in ("", "None", "nan"):
                safe_col = str(col).replace("$", r"\$")
                safe_value = str(value).replace("$", r"\$")
                st.write(f"**{safe_col}:** {safe_value}")
