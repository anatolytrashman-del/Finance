"""Загрузка и разбор объявлений kufar.by по отслеживаемым адресам.

Использует внутренний поисковый API куфара (тот же, что и их сайт).
Поиск текстом по адресу + фильтр по дому — двумя способами (см. _parse_ad):
основной, точный — геотег дома (address_tags_yandex); запасной — по обычному
тексту объявления, для улиц, чью транслитерацию kufar мы не проверяли живьём.
Цены в price_usd приходят в центах — делим на 100.
"""
import re
import time

import requests

from web_common import DESKTOP_USER_AGENT

API_URL = "https://api.kufar.by/search-api/v2/search/rendered-paginated"
HEADERS = {
    "User-Agent": DESKTOP_USER_AGENT,
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9",
}
MAX_PAGES = 10  # страховка от бесконечной пагинации
PAGE_PAUSE_SEC = 1.2  # вежливая пауза между запросами

CATEGORY_FLATS = "1010"
CATEGORY_COMMERCIAL = "1050"


def _param_map(ad):
    return {p.get("p"): p for p in ad.get("ad_parameters", []) if p.get("p")}


def _category_label(ad, params):
    """Категория для сводки. None — категория нам не интересна.

    Машиноместа/гаражи (re.kufar.by/l/minsk/kupit/garazh) — отдельная
    категория на kufar с неизвестным нам числовым кодом (в отличие от
    квартир/коммерции, где код проверен). Поэтому здесь не сверяем cat с
    константой, а ловим по тексту property_type — тем же способом, каким
    уже отличаются офис/торговое внутри коммерции ниже."""
    cat = str(ad.get("category") or "")
    label = str((params.get("property_type") or {}).get("vl") or "").lower()
    if "гараж" in label or "машино-место" in label or "машиноместо" in label:
        return "Машиноместа"
    if cat == CATEGORY_FLATS:
        return "Квартиры и апартаменты"
    if cat == CATEGORY_COMMERCIAL:
        if "офис" in label:
            return "Офисы"
        if "торгов" in label or "магазин" in label:
            return "Торговые помещения"
        return "Другая коммерческая"
    return None


def _first_val(param_entry):
    """Первое значение параметра kufar (структура {'v': [...]})."""
    try:
        vals = (param_entry or {}).get("v") or []
        return vals[0] if vals else None
    except (TypeError, AttributeError):
        return None


def _text_match(ad, street, house):
    """Запасное сопоставление по обычному тексту объявления (заголовок +
    описание) — на случай, если геотег дома не задан или не совпал (неверная
    транслитерация непроверенной улицы). Требует, чтобы рядом с названием
    улицы (в пределах ~25 символов дальше) встретился номер дома отдельным
    числом — иначе легко словить, например, дом 2 внутри дома 20."""
    if not street or not house:
        return False
    text = f"{ad.get('subject') or ''} {ad.get('body') or ''}".lower()
    idx = text.find(street.lower())
    if idx == -1:
        return False
    window = text[idx : idx + len(street) + 25]
    return bool(re.search(rf"(?<!\d){re.escape(str(house))}(?!\d)", window))


def _parse_ad(ad, house_tag, address_label, street=None, house=None):
    params = _param_map(ad)
    tags = (params.get("address_tags_yandex") or {}).get("v") or []
    tag_match = bool(house_tag) and any(house_tag in str(t) for t in tags)
    if not tag_match and not _text_match(ad, street, house):
        return None  # объявление не про наш дом
    category = _category_label(ad, params)
    if category is None:
        return None

    try:
        price_usd = float(ad.get("price_usd") or 0) / 100.0
    except (TypeError, ValueError):
        price_usd = 0.0
    try:
        area = float((params.get("size") or {}).get("v"))
    except (TypeError, ValueError):
        area = None

    deal = "Продажа" if ad.get("type") == "sell" else "Аренда"
    ppm = price_usd / area if price_usd > 0 and area else None
    # Фильтр правдоподобия: «договорная» цена (0/копейки) или цена, указанная
    # за м² вместо всего объекта, не должна попадать в средние. Само объявление
    # остаётся в таблице, просто без цены метра.
    if deal == "Продажа" and (price_usd < 5000 or (ppm is not None and ppm < 300)):
        ppm = None
    if deal == "Аренда" and (price_usd < 50 or (ppm is not None and ppm < 3)):
        ppm = None

    return {
        "id": str(ad.get("ad_id")),
        "address": address_label,
        "deal": deal,
        "category": category,
        "title": ad.get("subject") or "",
        "area": area,
        "price_usd": price_usd,
        "ppm": ppm,
        "rooms": (params.get("rooms") or {}).get("v"),
        "floor": _first_val(params.get("floor")),
        "floors_total": _first_val(params.get("re_number_floors")),
        "link": ad.get("ad_link") or "",
        "listed_at": (ad.get("list_time") or "")[:10],
    }


def fetch_address(query, house_tag, address_label, street=None, house=None):
    """Собирает все объявления по одному адресу (с пагинацией).

    street/house — для запасного текстового сопоставления, см. _text_match.
    Возвращает (listings, warnings)."""
    listings, warnings = [], []
    seen_ids = set()
    params = {"lang": "ru", "size": "30", "query": query}

    for page in range(1, MAX_PAGES + 1):
        try:
            resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=25)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"kufar «{address_label}»: страница {page} не загрузилась ({exc})")
            break

        ads = data.get("ads") or []
        new_ids = {str(a.get("ad_id")) for a in ads}
        if not ads or new_ids <= seen_ids:
            break  # пусто или пагинация зациклилась
        for ad in ads:
            ad_id = str(ad.get("ad_id"))
            if ad_id in seen_ids:
                continue
            seen_ids.add(ad_id)
            parsed = _parse_ad(ad, house_tag, address_label, street=street, house=house)
            if parsed:
                listings.append(parsed)

        token = None
        for p in (data.get("pagination") or {}).get("pages", []):
            if p.get("label") == "next":
                token = p.get("token")
        if not token:
            break
        params = {"lang": "ru", "size": "30", "query": query, "cursor": token}
        time.sleep(PAGE_PAUSE_SEC)

    return listings, warnings


def fetch_all(addresses):
    """Собирает объявления по всем адресам из конфига."""
    all_listings, all_warnings = [], []
    for addr in addresses:
        listings, warnings = fetch_address(
            addr["query"], addr["house_tag"], addr["label"],
            street=addr.get("realt_street"), house=addr.get("house"),
        )
        all_listings.extend(listings)
        all_warnings.extend(warnings)
        time.sleep(PAGE_PAUSE_SEC)
    # дедупликация (одно объявление может найтись по двум запросам)
    unique = {}
    for l in all_listings:
        unique[l["id"]] = l
    return list(unique.values()), all_warnings
