"""Загрузка объявлений о земельных участках с avito.ru по нарисованной области.

В отличие от kufar/realt, тут нет адреса — есть произвольная область на
карте (полигон координат). Схема (вскрыта через avito_scout.py и реальный
дамп сетевых запросов):

  1. POST /web/1/saveDrawArea   {"drawArea": base64(json{"coordinates":[[[lon,lat],...]],"type":"Polygon"})}
     -> {"drawId": "..."}
     Полигон каждый раз отправляется заново (не полагаемся на то, что
     сохранённый ранее drawId ещё жив — TTL неизвестен).
  2. GET /js/1/map/items?categoryId=...&locationId=...&drawId=...&...
     -> {"totalCount": N, "items": [...]}

ВАЖНО: Avito жёстче защищён от ботов, чем kufar/realt — простые запросы
через requests с браузерными заголовками получают 403 (проверено на живом
запуске). Поэтому здесь запросы идут не через requests, а через настоящий
headless-браузер (Playwright), причём сами HTTP-вызовы делаются функцией
fetch() ИЗНУТРИ открытой страницы avito.ru — так автоматически совпадают
все cookies/заголовки/TLS-отпечаток с тем, что видел бы обычный браузер
(именно так работала разведка avito_scout.py, и там блокировок не было).
Требует: python3 -m playwright install chromium (один раз на машине).
"""
import base64
import json
import re
import time
import urllib.parse

PAGE_SIZE = 10  # у Avito лимит объектов на страницу карты — 10 (limit=10 в наблюдённом запросе)
MAX_PAGES = 20
PAGE_PAUSE_SEC = 1.0

ENDPOINT_SAVE_AREA = "https://www.avito.ru/web/1/saveDrawArea"
ENDPOINT_ITEMS = "https://www.avito.ru/js/1/map/items"

_AREA_RE = re.compile(r"(\d[\d.,]*)\s*(сот|га)", re.IGNORECASE)
_TYPE_RE = re.compile(r"\(([^)]+)\)\s*$")

_FETCH_JS = """
async ({method, url, body}) => {
    const opts = {method, credentials: "include"};
    if (body !== null) {
        opts.headers = {"Content-Type": "application/json"};
        opts.body = JSON.stringify(body);
    }
    const resp = await fetch(url, opts);
    const text = await resp.text();
    return {status: resp.status, text};
}
"""


def _pw_fetch_json(page, method, url, body=None):
    """fetch() внутри открытой страницы браузера — не голый requests, чтобы
    антибот не отличал нас от настоящего пользователя (см. докстринг модуля)."""
    result = page.evaluate(_FETCH_JS, {"method": method, "url": url, "body": body})
    status, text = result["status"], result["text"]
    if status >= 400:
        # «too-many-requests» — это не блокировка бота, а временный лимит по
        # IP (антиспам-фаервол Avito). Распознаём отдельно и даём понятное
        # сообщение вместо сырого JSON — тут не нужно чинить код, нужно подождать.
        if "too-many-requests" in text:
            raise RuntimeError(
                "Avito временно ограничил доступ с твоего IP (антиспам-фаервол, "
                "не блокировка бота как таковая). Обычно снимается само через "
                "какое-то время — от нескольких минут до пары часов. Не пробуй "
                "обновлять сразу повторно, это может продлить ограничение."
            )
        raise RuntimeError(f"{method} {url.split('?')[0]} -> HTTP {status}: {text[:200]!r}")
    try:
        return json.loads(text)
    except ValueError as exc:
        raise RuntimeError(
            f"{method} {url.split('?')[0]}: сервер вернул не JSON "
            f"(возможно, антибот-защита/капча): {text[:200]!r}"
        ) from exc


def _save_draw_area(page, polygon):
    """polygon: [[lon, lat], ...] — замкнутый контур. Возвращает drawId."""
    # separators без пробелов — как JSON.stringify в браузере, откуда взят формат
    inner = json.dumps({"coordinates": [polygon], "type": "Polygon"}, ensure_ascii=False, separators=(",", ":"))
    draw_area_b64 = base64.b64encode(inner.encode("utf-8")).decode("ascii")
    data = _pw_fetch_json(page, "POST", ENDPOINT_SAVE_AREA, {"drawArea": draw_area_b64})
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


def _fetch_area(page, area_config):
    """Собирает все объявления в нарисованной области. Возвращает (listings, warnings)."""
    name = area_config["name"]
    try:
        draw_id = _save_draw_area(page, area_config["polygon"])
    except Exception as exc:  # noqa: BLE001
        return [], [f"avito «{name}»: не удалось сохранить область ({exc})"]

    listings, seen_ids = [], set()
    for page_num in range(1, MAX_PAGES + 1):
        params = {
            "categoryId": area_config["category_id"],
            "locationId": area_config["location_id"],
            "correctorMode": 0,
            "page": page_num,
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
        url = f"{ENDPOINT_ITEMS}?{urllib.parse.urlencode(params)}"

        try:
            data = _pw_fetch_json(page, "GET", url)
        except Exception as exc:  # noqa: BLE001
            warnings_msg = f"avito «{name}»: страница {page_num} не загрузилась ({exc})"
            return listings, [warnings_msg]

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

    return listings, []


# Скрываем самый распространённый признак автоматизации — navigator.webdriver
# (в обычном Chrome его нет, headless/Playwright по умолчанию его выставляет).
_STEALTH_INIT_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
"""


def _launch_browser(p, headless):
    """Пробуем запустить настоящий установленный Chrome (channel='chrome') —
    он неотличим от браузера обычного пользователя, в отличие от бандла
    Playwright, который некоторые антибот-системы умеют узнавать по сборке.
    Если Chrome не установлен — используем чистый Chromium как запасной."""
    try:
        return p.chromium.launch(channel="chrome", headless=headless)
    except Exception:  # noqa: BLE001
        return p.chromium.launch(headless=headless)


def fetch_all(areas, headless=False):
    """Собирает объявления по всем настроенным областям через настоящий браузер.

    headless=False по умолчанию: у разведчика (avito_scout.py) именно видимый
    браузер прошёл без единой блокировки, а headless-режим при живом прогоне
    словил «too-many-requests» — похоже, антибот отличает headless по тонким
    техническим признакам, а не считает буквально количество запросов.
    На экране на время обновления появится окно браузера — это ожидаемо."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [], [
            "avito: не установлен playwright. Выполни: pip install playwright && "
            "python3 -m playwright install chromium"
        ]

    all_listings, all_warnings = [], []
    try:
        with sync_playwright() as p:
            browser = _launch_browser(p, headless)
            page = browser.new_page(
                viewport={"width": 1440, "height": 1000},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
            )
            page.add_init_script(_STEALTH_INIT_JS)
            try:
                page.goto("https://www.avito.ru/", wait_until="domcontentloaded", timeout=30000)
                time.sleep(2.0)  # даём странице «осесть», как у живого пользователя
            except Exception as exc:  # noqa: BLE001
                browser.close()
                return [], [f"avito: не удалось открыть сайт для получения cookies ({exc})"]

            for area in areas:
                listings, warnings = _fetch_area(page, area)
                all_listings.extend(listings)
                all_warnings.extend(warnings)
                time.sleep(PAGE_PAUSE_SEC)

            browser.close()
    except Exception as exc:  # noqa: BLE001
        return [], [
            f"avito: браузер не запустился ({exc}). Проверь: "
            f"python3 -m playwright install chromium"
        ]

    unique = {l["id"]: l for l in all_listings}
    return list(unique.values()), all_warnings
