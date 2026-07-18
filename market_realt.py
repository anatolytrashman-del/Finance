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
  objectType == 14    -> машиноместо/гараж
  прочие objectType   -> коммерция; офис/торговое/другое различаем по заголовку
Тип сделки: аренда, если задан termOfLease или leasePeriod, иначе продажа.

Цены приходят в валюте объекта (840=USD, 933=BYN, 978=EUR, 643=RUB). В ответе
есть блок rates с курсами — переводим всё в доллары. Схема результата та же,
что у market_kufar, чтобы источники объединялись на странице «Рынок».
"""
import concurrent.futures
import time

import requests

from web_common import DESKTOP_USER_AGENT

ENDPOINT = "https://realt.by/bff/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://realt.by",
    "Referer": "https://realt.by/sale/flats/",
    "User-Agent": DESKTOP_USER_AGENT,
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
    "        storey storeys title headline createdAt updatedAt raiseDate __typename\n"
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
    """Возвращает (data, errors). errors — список строк-описаний, если есть."""
    payload = [{"operationName": operation, "variables": variables, "query": query}]
    resp = requests.post(ENDPOINT, headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    item = (data[0] if isinstance(data, list) else data) or {}
    errors = [
        (e.get("message") or str(e)) for e in (item.get("errors") or [])
    ]
    return item.get("data") or {}, errors


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
        data, errors = _gql(
            "multiGeoReferenceAgg", GEO_QUERY,
            {"data": {"where": {"title": street_query, "types": GEO_TYPES}, "pageSize": 15}},
        )
    except Exception as exc:  # noqa: BLE001
        return [], [f"realt «{street_query}»: гео-поиск не отработал ({exc})"]
    if errors:
        return [], [f"realt «{street_query}»: гео-поиск вернул ошибку ({'; '.join(errors)})"]

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
        return "Машиноместа"
    title = (obj.get("title") or obj.get("headline") or "").lower()
    if "офис" in title:
        return "Офисы"
    if "торг" in title or "магазин" in title or "ритейл" in title:
        return "Торговые помещения"
    return "Другая коммерческая"


def _object_link(deal, category, code):
    """Статическая ссылка на объект — раздел URL берём из категории.

    Слаги подтверждены реальными ссылками объектов realt.by (проверено для
    обеих сделок — продажи и аренды):
      sale-flats, rent-flats       — Квартиры и апартаменты
      sale-offices, rent-offices   — Офисы
      sale-shops, rent-shops       — Торговые помещения
      sale-pomeschenie, rent-pomeschenie — Другая коммерческая
                                      (realt: «Помещения свободного назначения», ПСН)

    sale-garage — Машиноместа: слаг НЕ подтверждён реальной ссылкой на
    объект, это предположение по аналогии с shops/offices (там слаг
    категории и слаг объекта совпадают). У «Другая коммерческая» так не
    сработало — там страница категории «storages», а объект оказался на
    «pomeschenie», подтвердилось только по реальной ссылке от пользователя.
    Если после обновления ссылки на машиноместа не открываются —
    verify_links() уже сама уводит их в архив с пометкой «Битая ссылка»,
    ничего не сломается, но точный слаг лучше подтвердить так же — прислать
    ссылку на конкретное объявление.

    ВАЖНО: раньше здесь была живая проверка ссылки (HTTP-запрос на каждый
    вариант при каждом объявлении) — из-за неё обновление зависало на
    десятки минут. Больше так не делаем — только статический маппинг."""
    section_type = {
        "Квартиры и апартаменты": "flats",
        "Офисы": "offices",
        "Торговые помещения": "shops",
        "Другая коммерческая": "pomeschenie",
        "Машиноместа": "garage",
    }.get(category, "pomeschenie")
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
        "floor": obj.get("storey"),
        "floors_total": obj.get("storeys"),
        "link": _object_link(deal, category, code),
        "listed_at": listed_at,
    }


# Точный формат пагинации у searchObjectsV2 заранее неизвестен, а лишнее поле
# во входных данных валит весь GraphQL-запрос (data=null). Поэтому перебираем
# несколько вариантов и берём тот, что сервер принимает. page-aware варианты
# идут первыми, «plain» (дефолтная выдача) — последним запасным.
def _data_variants(where, page):
    return [
        ("pageSize+page", {"where": where, "pageSize": PAGE_SIZE, "page": page}),
        ("pagination", {"where": where, "pagination": {"page": page, "pageSize": PAGE_SIZE}}),
        ("pageSize+pageNumber", {"where": where, "pageSize": PAGE_SIZE, "pageNumber": page}),
        ("pageSize", {"where": where, "pageSize": PAGE_SIZE}),
        ("plain", {"where": where}),
    ]


PAGED_SHAPES = {"pageSize+page", "pagination", "pageSize+pageNumber"}


def _search(where, page, prefer=None):
    """Делает searchObjectsV2, подбирая формат входных данных.

    Возвращает (shape, body, errors): shape — имя сработавшего формата (или None),
    body — тело ответа (dict) либо None, errors — что вернул сервер по пути."""
    seen_errors = []
    variants = _data_variants(where, page)
    if prefer:  # если формат уже известен по 1-й странице — используем только его
        variants = [(n, d) for (n, d) in variants if n == prefer]
    for name, data in variants:
        try:
            payload, errors = _gql("searchObjectsV2", SEARCH_QUERY, {"data": data})
        except Exception as exc:  # noqa: BLE001
            seen_errors.append(f"{name}: {exc}")
            continue
        if errors:
            seen_errors.append(f"{name}: {'; '.join(errors)}")
            continue
        body = (payload.get("searchObjectsV2") or {}).get("body")
        if body and (body.get("results") is not None):
            return name, body, seen_errors
    return None, None, seen_errors


def fetch_address(street_query, house, address_label):
    """Собирает объявления realt по одному адресу. Возвращает (listings, warnings)."""
    uuids, warnings = resolve_street_uuids(street_query)
    if not uuids:
        return [], warnings

    listings, seen = [], set()
    where = {"addressV2": [{"streetUuid": u} for u in uuids]}
    shape = None
    for page in range(1, MAX_PAGES + 1):
        shape, body, errors = _search(where, page, prefer=shape)
        if body is None:
            if page == 1:
                detail = f" ({'; '.join(errors)})" if errors else ""
                warnings.append(f"realt «{address_label}»: поиск объектов не отработал{detail}")
            break

        results = body.get("results") or []
        new_uuids = {r.get("uuid") for r in results} - seen
        if not new_uuids:
            break  # пусто или пагинация зациклилась (сервер игнорит номер страницы)
        rates = _rate_map(body.get("rates"))
        for obj in results:
            uuid = obj.get("uuid")
            if uuid in seen:
                continue
            seen.add(uuid)
            parsed = _parse_object(obj, house, address_label, rates)
            if parsed:
                listings.append(parsed)

        total = (body.get("pagination") or {}).get("totalCount") or 0
        if shape not in PAGED_SHAPES or len(seen) >= total or not results:
            break  # формат без постраничности или всё уже собрали
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


# --- Проверка ссылок ---------------------------------------------------
#
# Раздел URL берётся из статического маппинга (_object_link) — он верный,
# но ссылка всё равно может не открыться: дубли одного объявления под
# разными code, или объект уже сняли с публикации, а он ещё доезжает в
# поисковой выдаче. Раньше здесь была последовательная проверка
# нескольких вариантов URL на объявление — это умножалось на количество
# объявлений и подвешивало обновление на десятки минут. Теперь: один запрос
# на объявление, все параллельно, с жёстким лимитом по времени на всю пачку.

LINK_CHECK_WORKERS = 10
LINK_CHECK_TIMEOUT = 4    # таймаут одного запроса, сек
LINK_CHECK_BUDGET = 25    # общий лимит на всю проверку, сек


def _check_one_link(url):
    try:
        resp = requests.head(url, headers=HEADERS, timeout=LINK_CHECK_TIMEOUT, allow_redirects=True)
        if resp.status_code in (405, 403):  # HEAD не поддерживается/заблокирован — пробуем GET
            resp = requests.get(url, headers=HEADERS, timeout=LINK_CHECK_TIMEOUT, allow_redirects=True, stream=True)
            resp.close()
        return resp.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def verify_links(listings):
    """Параллельно проверяет ссылки объявлений realt (один запрос на объявление,
    жёсткий лимит по времени на всю пачку — не может зависнуть). Возвращает
    множество id объявлений, чья ссылка не открылась (404/ошибка).

    Объявления, чью ссылку не успели проверить за отведённое время, НЕ
    считаются битыми — просто перепроверим при следующем обновлении."""
    targets = [l for l in listings if l.get("id", "").startswith("realt-") and l.get("link")]
    if not targets:
        return set()

    broken_ids = set()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=LINK_CHECK_WORKERS)
    try:
        future_to_id = {executor.submit(_check_one_link, l["link"]): l["id"] for l in targets}
        done, _pending = concurrent.futures.wait(future_to_id, timeout=LINK_CHECK_BUDGET)
        for future in done:
            try:
                ok = future.result()
            except Exception:  # noqa: BLE001
                ok = False
            if not ok:
                broken_ids.add(future_to_id[future])
    finally:
        # не ждём «зависшие» запросы — они доработают в фоне и сами закроются
        # по своему таймауту, но мы не блокируем на них весь refresh
        executor.shutdown(wait=False, cancel_futures=True)
    return broken_ids
