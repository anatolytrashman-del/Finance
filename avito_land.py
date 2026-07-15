"""Загрузка объявлений о земельных участках с avito.ru по нарисованной области.

В отличие от kufar/realt, тут нет адреса — есть произвольная область на
карте (полигон координат). Схема (вскрыта через avito_scout.py и реальный
дамп сетевых запросов):

  1. POST /web/1/saveDrawArea   {"drawArea": base64(json{"coordinates":[[[lon,lat],...]]})}
     -> {"drawId": "..."}
     Полигон каждый раз отправляется заново (не полагаемся на то, что
     сохранённый ранее drawId ещё жив — TTL неизвестен).
  2. GET /js/1/map/items?categoryId=...&locationId=...&drawId=...&...
     -> {"totalCount": N, "items": [...]}

ВАЖНО: Avito крупнее и обычно жёстче защищён от ботов, чем kufar/realt.
Разведка (avito_scout.py) ходила настоящим браузером, поэтому антибот не
успели проверить против обычных requests-запросов — если сайт начнёт
возвращать не JSON, а капчу/HTML — сразу увидим это по ошибке разбора
ответа (see _get_json) и вернём внятное предупреждение, а не упадём молча.
"""
import base64
import json
import re
import time

import requests

ENDPOINT_SAVE_AREA = "https://www.avito.ru/web/1/saveDrawArea"
ENDPOINT_ITEMS = "https://www.avito.ru/js/1/map/items"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://www.avito.ru",
    "Referer": "https://www.avito.ru/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}

PAGE_SIZE = 10  # у Avito лимит объектов на страницу карты —10 (limit=10 в наблюдённом запросе)
MAX_PAGES = 20
PAGE_PAUSE_SEC = 1.0

_AREA_RE = re.compile(r"(\d[\d.,]*)\s*(сот|га)", re.IGNORECASE)
_TYPE_RE = re.compile(r"\(([^)]+)\)\s*$")


def _get_json(resp, context):
    """Разбирает JSON-ответ; если пришёл не JSON (капча/блокировка) —
    кидает понятную ошибку вместо непонятного JSONDecodeError глубоко внутри."""
    try:
        return resp.json()
    except ValueError as exc:
        snippet = resp.text[:200].replace("\n", " ")
        raise RuntimeError(
            f"{context}: сервер вернул не JSON (возможно, антибот-защита/капча). "
            f"HTTP {resp.status_code}, начало ответа: {snippet!r}"
        ) from exc


def save_draw_area(polygon):
    """polygon: [[lon, lat], ...] — замкнутый контур. Возвращает drawId."""
    # separators без пробелов — как JSON.stringify в браузере, откуда взят формат
    inner = json.dumps({"coordinates": [polygon], "type": "Polygon"}, ensure_ascii=False, separators=(",", ":"))
    draw_area_b64 = base64.b64encode(inner.encode("utf-8")).decode("ascii")
    resp = requests.post(
        ENDPOINT_SAVE_AREA,
        headers=HEADERS,
        json={"drawArea": draw_area_b64},
        timeout=20,
    )
    resp.raise_for_status()
    data = _get_json(resp, "saveDrawArea")
    draw_id = data.get("drawId")
    if not draw_id:
        raise RuntimeError(f"saveDrawArea: в ответе нет drawId: {data}")
    return draw_id


def _parse_area_and_type(title):
    """«Участок 2,3 га (СНТ, ДНП)» -> (площадь в сотках, «СНТ, ДНП»)."""
    area_sotok = None
    m = _AREA_RE.search(title or "")
    if m:
        try:
            value = float(m.group(1).replace(",", "."))
            unit = m.group(2).lower()
            area_sotok = round(value * 100, 2) if unit == "га" else value
        except ValueError:
            area_sotok = None
    land_type = None
    m2 = _TYPE_RE.search(title or "")
    if m2:
        land_type = m2.group(1).strip()
    return area_sotok, land_type


def _parse_item(item):
    price = ((item.get("priceDetailed") or {}).get("value"))
    title = item.get("title") or ""
    area_sotok, land_type = _parse_area_and_type(title)
    ppm = (price / area_sotok) if (price and area_sotok) else None
    coords = item.get("coords") or {}
    url_path = item.get("urlPath") or ""
    return {
        "id": f"avito-{item.get('id')}",
        "title": title,
        "land_type": land_type,
        "area_sotok": area_sotok,
        "price_rub": price,
        "price_per_sotka": ppm,
        "address": coords.get("address_user") or (item.get("location") or {}).get("name") or "",
        "lat": coords.get("lat"),
        "lng": coords.get("lng"),
        "link": f"https://www.avito.ru{url_path}" if url_path.startswith("/") else url_path,
    }


def fetch_area(area_config):
    """Собирает все объявления в нарисованной области. Возвращает (listings, warnings)."""
    name = area_config["name"]
    warnings = []
    try:
        draw_id = save_draw_area(area_config["polygon"])
    except Exception as exc:  # noqa: BLE001
        return [], [f"avito «{name}»: не удалось сохранить область ({exc})"]

    listings, seen_ids = [], set()
    for page in range(1, MAX_PAGES + 1):
        params = {
            "categoryId": area_config["category_id"],
            "locationId": area_config["location_id"],
            "correctorMode": 0,
            "page": page,
            "map": "e30=",  # {} — пустой viewport-параметр; фильтрует drawId, не map
            "verticalCategoryId": area_config["vertical_category_id"],
            "rootCategoryId": area_config["root_category_id"],
            "localPriority": 0,
            "drawId": draw_id,
            "limit": PAGE_SIZE,
            "countAndItemsOnly": 1,
        }
        for key, value in (area_config.get("extra_params") or {}).items():
            params[f"params[{key}]"] = value

        try:
            resp = requests.get(ENDPOINT_ITEMS, headers=HEADERS, params=params, timeout=20)
            resp.raise_for_status()
            data = _get_json(resp, f"map/items стр.{page}")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"avito «{name}»: страница {page} не загрузилась ({exc})")
            break

        items = data.get("items") or []
        new_items = [it for it in items if str(it.get("id")) not in seen_ids]
        if not new_items:
            break
        for it in new_items:
            seen_ids.add(str(it.get("id")))
            parsed = _parse_item(it)
            parsed["area_name"] = name
            listings.append(parsed)

        total = data.get("totalCount") or 0
        if len(seen_ids) >= total or len(items) < PAGE_SIZE:
            break
        time.sleep(PAGE_PAUSE_SEC)

    return listings, warnings


def fetch_all(areas):
    """Собирает объявления по всем настроенным областям."""
    all_listings, all_warnings = [], []
    for area in areas:
        listings, warnings = fetch_area(area)
        all_listings.extend(listings)
        all_warnings.extend(warnings)
        time.sleep(PAGE_PAUSE_SEC)
    unique = {l["id"]: l for l in all_listings}
    return list(unique.values()), all_warnings
