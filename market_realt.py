"""Загрузка и разбор объявлений realt.by по отслеживаемым адресам.

realt.by — главный ресурс по коммерческой недвижимости. Данные берём из их
внутреннего GraphQL-API (/bff/graphql, тот же, что использует сайт; логин не
нужен, объявления публичные).

Логика:
  1. multiGeoReferenceAgg — по названию улицы находим её streetUuid в Минске
     (гео возвращает совпадения по всей стране — фильтруем по townName == «Минск»
     и по вхождению фамилии в название, чтобы отсечь парки/тёзки).
  2. searchObjectsV2 — тянем объекты по этим streetUuid (с пагинацией) и
     оставляем только наш дом (houseNumber).

Категории realt (по данным разведки нашими адресами):
  objectType == null  -> квартира/апартаменты (category 5 — продажа, 2 — аренда)
  objectType == 14    -> машиноместо/гараж (нам не интересно)
  прочие objectType   -> коммерция; офис/торговое/другое различаем по заголовку
Тип сделки: аренда, если задан termOfLease или leasePeriod, иначе продажа.

Цены приходят в валюте объекта (840=USD, 933=BYN, 978=EUR, 643=RUB). В ответе
есть блок rates с курсами — переводим всё в доллары. Схема результата та же,
что у market_kufar, чтобы источники объединялись на странице «Рынок».
"""
import time

import requests

ENDPOINT = "https://realt.by/bff/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://realt.by",
    "Referer": "https://realt.by/sale/flats/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "apollographql-client-name": "realt-web",
}

USD = 840  # ISO-код доллара в API realt
PAGE_SIZE = 500
MAX_PAGES = 6
PAGE_PAUSE_SEC = 1.0

GEO_QUERY = (
    "query multiGeoReferenceAgg($data: GetMultiGeoReferenceAggInput!) {\n"
    "  multiGeoReferenceAgg(data: $data) {\n"
    "    body {\n"
    "      streets { uuid type title townName townUuid __typename }\n"
    "      __typename\n"
    "    }\n"
    "    success\n"
    "    errors { code message field __typename }\n"
    "    __typename\n"
    "  }\n"
    "}"
)

SEARCH_QUERY = (
    "query searchObjectsV2($data: GetObjectsByAddressInputV2!) {\n"
    "  searchObjectsV2(data: $data) {\n"
    "    success\n"
    "    errors { code message field __typename }\n"
    "    body {\n"
    "      pagination { page pageSize totalCount __typename }\n"
    "      results {\n"
    "        uuid code category objectType houseNumber streetName streetUuid townName\n"
    "        price priceCurrency pricePerM2 areaTotal rooms termOfLease leasePeriod\n"
    "        title headline createdAt updatedAt raiseDate __typename\n"
    "      }\n"
    "      rates { from to rate __typename }\n"
    "      __typename\n"
    "    }\n"
    "    __typename\n"
    "  }\n"
    "}"
)

GEO_TYPES = [1, 2, 3, 4, 5, 6, 7]  # тип «улица» — один из этих; лишние безвредны


def _gql(operation, query, variables):
    payload = [{"operationName": operation, "variables": variables, "query": query}]
    resp = requests.post(ENDPOINT, headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    item = data[0] if isinstance(data, list) else data
    return (item or {}).get("data") or {}


def _rate_map(rates):
    return {(r.get("from"), r.get("to")): r.get("rate") for r in rates or []}


def _to_usd(value, currency, rates):
    if not value:
        return 0.0
    if currency == USD:
        return float(value)
    rate = rates.get((currency, USD))
    return float(value) * rate if rate else 0.0


def resolve_street_uuids(street_query):
    """Находит минские streetUuid по названию улицы. Возвращает (uuids, warnings)."""
    key = street_query.split()[-1].lower()  # «савицкого» / «алфёрова»
    try:
        data = _gql(
            "multiGeoReferenceAgg", GEO_QUERY,
            {"data": {"where": {"title": street_query, "types": GEO_TYPES}, "pageSize": 15}},
        )
    except Exception as exc:  # noqa: BLE001
        return [], [f"realt «{street_query}»: гео-поиск не отработал ({exc})"]

    streets = (((data.get("multiGeoReferenceAgg") or {}).get("body") or {}).get("streets")) or []
    uuids = []
    for s in streets:
        if (s.get("townName") or "") != "Минск":
            continue
        if key not in (s.get("title") or "").lower():
            continue  # отсекаем парки/тёзки (напр. «имени Михаила Павлова парк»)
        if s.get("uuid") and s["uuid"] not in uuids:
            uuids.append(s["uuid"])
    if not uuids:
        return [], [f"realt «{street_query}»: улица в Минске не найдена в гео-справочнике"]
    return uuids, []


def _category_label(obj):
    """Категория для сводки. None — объект нам не интересен (напр. машиноместо)."""
    object_type = obj.get("objectType")
    if object_type is None:
        return "Квартиры и апартаменты"
    if object_type == 14:  # машиноместо / гараж
        return None
    title = (obj.get("title") or obj.get("headline") or "").lower()
    if "офис" in title:
        return "Офисы"
    if "торг" in title or "магазин" in title or "ритейл" in title:
        return "Торговые помещения"
    return "Другая коммерческая"


def _object_link(deal, category, code):
    section_type = {
        "Квартиры и апартаменты": "flats",
        "Офисы": "offices",
        "Торговые помещения": "shops",
        "Другая коммерческая": "commercial",
    }.get(category, "commercial")
    section_deal = "rent" if deal == "Аренда" else "sale"
    return f"https://realt.by/{section_deal}-{section_type}/object/{code}/"


def _parse_object(obj, house, address_label, rates):
    if str(obj.get("houseNumber")) != str(house):
        return None
    category = _category_label(obj)
    if category is None:
        return None

    deal = "Аренда" if (obj.get("termOfLease") is not None or obj.get("leasePeriod") is not None) else "Продажа"
    price_usd = _to_usd(obj.get("price"), obj.get("priceCurrency"), rates)
    try:
        area = float(obj.get("areaTotal")) if obj.get("areaTotal") else None
    except (TypeError, ValueError):
        area = None

    # $/м²: сначала из полной цены и площади, иначе — из готового pricePerM2
    # (у коммерции аренда часто «договорная»: price = 0, но pricePerM2 указан).
    if price_usd > 0 and area:
        ppm = price_usd / area
    else:
        ppm = _to_usd(obj.get("pricePerM2"), obj.get("priceCurrency"), rates) or None

    # Фильтр правдоподобия — как в market_kufar: явные единицы измерения не те /
    # «договорная» цена не должны портить средние. Само объявление остаётся.
    if deal == "Продажа" and ppm is not None and not (200 <= ppm <= 30000):
        ppm = None
    if deal == "Аренда" and ppm is not None and not (2 <= ppm <= 400):
        ppm = None

    code = obj.get("code")
    listed_at = (obj.get("updatedAt") or obj.get("createdAt") or obj.get("raiseDate") or "")[:10]
    return {
        "id": f"realt-{code}",
        "address": address_label,
        "deal": deal,
        "category": category,
        "title": obj.get("title") or obj.get("headline") or "",
        "area": area,
        "price_usd": price_usd,
        "ppm": ppm,
        "rooms": obj.get("rooms"),
        "link": _object_link(deal, category, code),
        "listed_at": listed_at,
    }


def fetch_address(street_query, house, address_label):
    """Собирает объявления realt по одному адресу. Возвращает (listings, warnings)."""
    uuids, warnings = resolve_street_uuids(street_query)
    if not uuids:
        return [], warnings

    listings, seen = [], set()
    address_filter = [{"streetUuid": u} for u in uuids]
    for page in range(1, MAX_PAGES + 1):
        variables = {"data": {"where": {"addressV2": address_filter}, "pageSize": PAGE_SIZE, "page": page}}
        try:
            data = _gql("searchObjectsV2", SEARCH_QUERY, variables)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"realt «{address_label}»: страница {page} не загрузилась ({exc})")
            break

        body = ((data.get("searchObjectsV2") or {}).get("body")) or {}
        results = body.get("results") or []
        if not results:
            break
        rates = _rate_map(body.get("rates"))

        new_uuids = {r.get("uuid") for r in results} - seen
        if not new_uuids:
            break  # пагинация зациклилась (сервер игнорит page) — выходим
        for obj in results:
            uuid = obj.get("uuid")
            if uuid in seen:
                continue
            seen.add(uuid)
            parsed = _parse_object(obj, house, address_label, rates)
            if parsed:
                listings.append(parsed)

        total = (body.get("pagination") or {}).get("totalCount") or 0
        if len(seen) >= total:
            break
        time.sleep(PAGE_PAUSE_SEC)

    return listings, warnings


def fetch_all(addresses):
    """Собирает объявления realt по всем адресам из конфига.

    Ожидает в каждом адресе ключи realt_street (название улицы для поиска) и
    house (номер дома); при их отсутствии берёт query/label."""
    all_listings, all_warnings = [], []
    for addr in addresses:
        street = addr.get("realt_street") or addr.get("query") or addr.get("label")
        house = addr.get("house")
        if house is None:  # вытащим номер дома из query/label как запасной вариант
            tail = (addr.get("query") or addr.get("label") or "").replace(",", " ").split()
            house = tail[-1] if tail else ""
        listings, warnings = fetch_address(street, house, addr["label"])
        all_listings.extend(listings)
        all_warnings.extend(warnings)
        time.sleep(PAGE_PAUSE_SEC)

    unique = {l["id"]: l for l in all_listings}
    return list(unique.values()), all_warnings
