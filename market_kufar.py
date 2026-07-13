"""Загрузка и разбор объявлений kufar.by по отслеживаемым адресам.

Использует внутренний поисковый API куфара (тот же, что и их сайт).
Поиск текстом по адресу + строгий фильтр по геотегу дома
(address_tags_yandex), чтобы отсечь мусорные совпадения и соседние дома.
Цены в price_usd приходят в центах — делим на 100.
"""
import time

import requests

API_URL = "https://api.kufar.by/search-api/v2/search/rendered-paginated"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
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
    """Категория для сводки. None — категория нам не интересна."""
    cat = str(ad.get("category") or "")
    if cat == CATEGORY_FLATS:
        return "Квартиры и апартаменты"
    if cat == CATEGORY_COMMERCIAL:
        label = str((params.get("property_type") or {}).get("vl") or "")
        if "офис" in label.lower():
            return "Офисы"
        if "торгов" in label.lower() or "магазин" in label.lower():
            return "Торговые помещения"
        return "Другая коммерческая"
    return None


def _parse_ad(ad, house_tag, address_label):
    params = _param_map(ad)
    tags = (params.get("address_tags_yandex") or {}).get("v") or []
    if not any(house_tag in str(t) for t in tags):
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
        "link": ad.get("ad_link") or "",
        "listed_at": (ad.get("list_time") or "")[:10],
    }


def fetch_address(query, house_tag, address_label):
    """Собирает все объявления по одному адресу (с пагинацией).

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
            parsed = _parse_ad(ad, house_tag, address_label)
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
        listings, warnings = fetch_address(addr["query"], addr["house_tag"], addr["label"])
        all_listings.extend(listings)
        all_warnings.extend(warnings)
        time.sleep(PAGE_PAUSE_SEC)
    # дедупликация (одно объявление может найтись по двум запросам)
    unique = {}
    for l in all_listings:
        unique[l["id"]] = l
    return list(unique.values()), all_warnings
