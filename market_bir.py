"""Цены застройщика (bir.by) по домам 16 и 11 квартала.

Это не «вторичка» с kufar/realt, а прайс-лист самого застройщика (ЖК «Минск
Мир») — отдельная категория данных, отображается на странице «Анализ рынка»
своим блоком.

По разведке (scouts/bir_scout.py): ?sort=live/com/park/klad в URL НИ НА ЧТО не
влияет на стороне сервера — все 4 таблицы (квартиры/апартаменты, коммерция,
кладовые, машиноместа) всегда отрисованы в HTML одной и той же страницы
целиком, ?sort= только подсвечивает вкладку в интерфейсе. Значит на дом
достаточно ОДНОГО запроса без параметров, а не четырёх.

Таблицы (по HTML id) и состав колонок разные для каждой категории:
  inner-search-table          — квартиры/апартаменты (+ комнаты)
  inner-search-table_com      — коммерческие помещения (+ терраса)
  inner-search-table_klad     — кладовые (без комнат/террасы)
  inner-search-table_parking  — машиноместа (нет цены за м² — только цена целиком)

Цены на сайте — в BYN и EUR (своя валюта застройщика), $ нет вообще.

ВАЖНО про пагинацию: сервер отдаёт только первые 15 строк на категорию,
дальше — кнопка «Показать ещё» (id="show-more"/"show-more_com"/
"show-more_klad"/"show-more_parking"), догружающая остаток через AJAX.
Путь эндпоинта в JS сайта прописан непоследовательно (часть — с префиксом
"ajax/", часть — без, у разных категорий по-разному) — угадывать его
рискованно, уже обжигались на таком с realt.by. Поэтому вместо прямого
POST-запроса открываем страницу настоящим браузером (Playwright) и жмём
«Показать ещё» столько раз, сколько нужно, пока сайт сам не спрячет кнопку —
это ровно то же самое действие, что делает живой пользователь."""
import re

from web_common import DESKTOP_USER_AGENT

HEADERS = {
    "User-Agent": DESKTOP_USER_AGENT,
    "Accept-Language": "ru-RU,ru;q=0.9",
}

# (квартал, дом, базовый URL)
HOUSES = [
    ("16 квартал", "16.1 Нясвижский замок", "https://bir.by/page/real-estate/minskworld/planirovki-kvartal-16/dom-nyasvizhski-zamak/"),
    ("16 квартал", "16.2 Мирский замок", "https://bir.by/page/real-estate/minskworld/planirovki-kvartal-16/dom-mirskij-zamok/"),
    ("11 квартал", "11.1 Каспиан", "https://bir.by/kaspian/"),
    ("11 квартал", "11.2 Медитерраниан", "https://bir.by/dom-mediteranian/"),
    ("11 квартал", "11.3 Атлантик", "https://bir.by/page/real-estate/minskworld/planirovki-kvartal-11-avstraliya-i-okeaniya/dom-atlantik/"),
    ("11 квартал", "11.4 Пацифик", "https://bir.by/page/real-estate/minskworld/planirovki-kvartal-11-avstraliya-i-okeaniya/dom-paczifik/"),
    ("11 квартал", "11.5 Адриатик", "https://bir.by/page/real-estate/minskworld/planirovki-kvartal-11-avstraliya-i-okeaniya/dom-adriatik/"),
    ("11 квартал", "11.6 Карибиан", "https://bir.by/page/real-estate/minskworld/planirovki-kvartal-11-avstraliya-i-okeaniya/dom-karibian/"),
]

CATEGORY_LABELS = {
    "inner-search-table": "Квартиры и апартаменты",
    "inner-search-table_com": "Коммерческие помещения",
    "inner-search-table_klad": "Кладовые",
    "inner-search-table_parking": "Машиноместа",
}

# Порядок и смысл <td> для каждой таблицы — снят вручную с реального HTML
# (bir_debug.zip), см. docstring выше. "price"/"price_fast" — обычная и
# «специальная» (при условии быстрой оплаты) цена, каждая как (BYN, EUR).
COLUMN_LAYOUTS = {
    "inner-search-table": [
        "unit", "house_name", "house_code", "floor", "entrance", "area",
        "rooms", "ppm", "price", "ppm_fast", "price_fast", "link", "favorite",
    ],
    "inner-search-table_com": [
        "unit", "floor", "entrance", "area", "terrace_area",
        "ppm", "price", "ppm_fast", "price_fast", "link", "favorite",
    ],
    "inner-search-table_klad": [
        "unit", "floor", "entrance", "area",
        "ppm", "price", "ppm_fast", "price_fast", "link", "favorite",
    ],
    "inner-search-table_parking": [
        "unit", "floor", "entrance", "area",
        "price", "price_fast", "link", "favorite",
    ],
}

_TABLE_RE = {
    table_id: re.compile(rf'<table id="{table_id}"[^>]*>(.*?)</table>', re.S)
    for table_id in CATEGORY_LABELS
}
_ROW_RE = re.compile(r'<tr class="table-search__row".*?data-loadobject="([0-9a-f-]+)".*?</tr>', re.S)
_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_BYN_RE = re.compile(r"([\d\s]+)\s*<i class=\"nbrb-icon nbrb-icon-byn\"")
_EUR_RE = re.compile(r"([\d\s]+)\s*€")


def _text(cell_html):
    return _TAG_RE.sub("", cell_html).strip()


def _num(s):
    """Число из текста ячейки — сохраняет десятичную точку (площадь вроде
    «12.5» иначе превращается в 125), но убирает пробелы-разделители тысяч
    у цен (цены здесь всегда целые, десятичных не бывает)."""
    s = (s or "").replace("\xa0", " ").strip()
    cleaned = re.sub(r"[^\d.]", "", s)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _price_pair(cell_html):
    """Возвращает (byn, eur) из ячейки с ценой — на сайте всегда обе валюты."""
    byn_m = _BYN_RE.search(cell_html)
    eur_m = _EUR_RE.search(cell_html)
    return _num(byn_m.group(1) if byn_m else None), _num(eur_m.group(1) if eur_m else None)


def _parse_row(row_html, uuid, layout, quartal, house):
    cells = _CELL_RE.findall(row_html)
    if len(cells) < len(layout):
        return None  # неожиданная разметка строки — пропускаем, не гадаем
    field = dict(zip(layout, cells))

    floor_raw = _text(field["floor"])
    try:
        floor = int(floor_raw)
    except ValueError:
        floor = None

    area = _num(_text(field["area"]))
    rooms_raw = _text(field.get("rooms", "")) if "rooms" in field else None
    try:
        rooms = int(rooms_raw) if rooms_raw else None
    except ValueError:
        rooms = None

    price_byn, price_eur = _price_pair(field["price"])
    price_byn_fast, price_eur_fast = _price_pair(field.get("price_fast", ""))
    ppm_byn = ppm_eur = ppm_byn_fast = ppm_eur_fast = None
    if "ppm" in field:
        ppm_byn, ppm_eur = _price_pair(field["ppm"])
    if "ppm_fast" in field:
        ppm_byn_fast, ppm_eur_fast = _price_pair(field["ppm_fast"])

    link_m = re.search(r'href="(/object/[0-9a-f-]+)"', field["link"])
    link = f"https://bir.by{link_m.group(1)}" if link_m else f"https://bir.by/object/{uuid}"

    return {
        "id": f"bir-{uuid}",
        "quartal": quartal,
        "house": house,
        "unit": _text(field["unit"]),
        "floor": floor,
        "entrance": _text(field["entrance"]),
        "area": area,
        "rooms": rooms,
        "price_byn": price_byn,
        "price_eur": price_eur,
        "ppm_byn": ppm_byn,
        "ppm_eur": ppm_eur,
        "price_byn_fast": price_byn_fast,
        "price_eur_fast": price_eur_fast,
        "ppm_byn_fast": ppm_byn_fast,
        "ppm_eur_fast": ppm_eur_fast,
        "link": link,
    }


def parse_house_html(html, quartal, house):
    """Разбирает одну страницу дома на все 4 категории. Возвращает
    {category_label: [listing, ...]}."""
    result = {label: [] for label in CATEGORY_LABELS.values()}
    for table_id, label in CATEGORY_LABELS.items():
        table_m = _TABLE_RE[table_id].search(html)
        if not table_m:
            continue
        block = table_m.group(1)
        layout = COLUMN_LAYOUTS[table_id]
        for row_m in _ROW_RE.finditer(block):
            uuid = row_m.group(1)
            listing = _parse_row(row_m.group(0), uuid, layout, quartal, house)
            if listing:
                listing["category"] = label
                result[label].append(listing)
    return result


# id кнопки «Показать ещё» на дом id соответствующей таблицы (без общего
# префикса — "show-more" для квартир, "show-more_com" для коммерции и т.д.)
SHOW_MORE_IDS = {
    "inner-search-table": "show-more",
    "inner-search-table_com": "show-more_com",
    "inner-search-table_klad": "show-more_klad",
    "inner-search-table_parking": "show-more_parking",
}
MAX_SHOW_MORE_CLICKS = 20  # запас с большим кэфом — реально нужно в разы меньше
SHOW_MORE_WAIT_MS = 1200


def _expand_all(page):
    """Жмёт «Показать ещё» на всех 4 таблицах, пока сайт сам её не спрячет
    (значит показаны все варианты) — так получаем полный список без
    угадывания параметров AJAX-запроса."""
    for button_id in SHOW_MORE_IDS.values():
        for _ in range(MAX_SHOW_MORE_CLICKS):
            btn = page.locator(f"#{button_id}")
            if btn.count() == 0 or not btn.first.is_visible():
                break
            try:
                btn.first.click(timeout=3000)
            except Exception:  # noqa: BLE001
                break
            page.wait_for_timeout(SHOW_MORE_WAIT_MS)


def _launch_browser(p, headless):
    # Без channel="chrome" — тот вариант ловил ERR_NAME_NOT_RESOLVED на
    # bir.by (похоже, у установленного Chrome другие настройки DNS/сети под
    # автоматизацией). Обычный бандловый Chromium уже проверен вживую в
    # scouts/bir_scout.py — там ровно так и запускается, и все 32 страницы
    # загрузились без единой ошибки.
    return p.chromium.launch(headless=headless)


def fetch_house(quartal, house, base_url, page):
    """Возвращает (listings, warnings) для одного дома (все 4 категории,
    с полным списком — «Показать ещё» дожато до конца)."""
    try:
        page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        _expand_all(page)
        html = page.content()
    except Exception as exc:  # noqa: BLE001
        return [], [f"bir.by «{house}»: не удалось загрузить страницу ({exc})"]

    by_category = parse_house_html(html, quartal, house)
    listings = [item for items in by_category.values() for item in items]
    if not listings:
        return [], [f"bir.by «{house}»: на странице не нашлось ни одной таблицы юнитов — возможно, изменилась вёрстка"]
    return listings, []


def fetch_all(houses=HOUSES, headless=True):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [], [
            "bir.by: не установлен playwright. Выполни: pip install playwright && "
            "python3 -m playwright install chromium"
        ]

    all_listings, all_warnings = [], []
    try:
        with sync_playwright() as p:
            browser = _launch_browser(p, headless)
            page = browser.new_page(
                viewport={"width": 1440, "height": 1000},
                user_agent=HEADERS["User-Agent"],
            )
            for quartal, house, base_url in houses:
                listings, warnings = fetch_house(quartal, house, base_url, page)
                all_listings.extend(listings)
                all_warnings.extend(warnings)
            browser.close()
    except Exception as exc:  # noqa: BLE001
        return [], [
            f"bir.by: браузер не запустился ({exc}). Проверь: "
            f"python3 -m playwright install chromium"
        ]

    unique = {l["id"]: l for l in all_listings}
    return list(unique.values()), all_warnings
