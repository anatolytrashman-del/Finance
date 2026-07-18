"""Скрипт-разведчик для будущего парсера объявлений (kufar.by, realt.by).

Делает запросы к сайтам, сохраняет сырые ответы в папку market_debug/
и упаковывает её в market_debug.zip — этот zip нужно прислать в чат,
чтобы по реальной структуре данных написать парсер.

Запуск:  python3 market_scout.py
Ничего не публикует и не отправляет — только скачивает и сохраняет локально.
"""
import time
import zipfile
from pathlib import Path

import requests

OUT_DIR = Path(__file__).parent / "market_debug"
ZIP_PATH = Path(__file__).parent / "market_debug.zip"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5",
}

# Что запрашиваем. Имена файлов — латиницей, чтобы не было проблем с кодировками.
REQUESTS = [
    # --- Kufar: внутренний поисковый API (текстовый поиск по адресу) ---
    (
        "kufar_api_alferova.json",
        "https://api.kufar.by/search-api/v2/search/rendered-paginated",
        {"lang": "ru", "query": "Жореса Алфёрова 22", "size": "30"},
    ),
    (
        "kufar_api_savitskogo.json",
        "https://api.kufar.by/search-api/v2/search/rendered-paginated",
        {"lang": "ru", "query": "Михаила Савицкого 24", "size": "30"},
    ),
    # --- Kufar: HTML страниц категорий (посмотреть структуру/категории) ---
    (
        "kufar_html_comm_sale.html",
        "https://www.kufar.by/l/minsk/kupit/kommercheskaya-nedvizhimost",
        None,
    ),
    (
        "kufar_html_comm_rent.html",
        "https://www.kufar.by/l/minsk/snyat/kommercheskaya-nedvizhimost",
        None,
    ),
    # --- Realt: страницы поиска (в HTML должен быть __NEXT_DATA__ с JSON) ---
    ("realt_sale_commercial.html", "https://realt.by/sale/commercial/", None),
    ("realt_rent_commercial.html", "https://realt.by/rent/commercial/", None),
    ("realt_sale_flats.html", "https://realt.by/sale/flats/", None),
    (
        "realt_search_alferova.html",
        "https://realt.by/search/",
        {"searchType": "sale", "query": "Жореса Алфёрова 22"},
    ),
]


def classify(text, content_type):
    """Краткая характеристика ответа для сводки."""
    tags = []
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        tags.append("JSON")
    if "__NEXT_DATA__" in text:
        tags.append("NEXT_DATA")
    lowered = text[:5000].lower()
    for marker in ("captcha", "just a moment", "attention required", "cloudflare", "robot"):
        if marker in lowered:
            tags.append(f"BLOCK?:{marker}")
    if "json" in (content_type or ""):
        tags.append("ct:json")
    return ", ".join(tags) or "-"


def main():
    OUT_DIR.mkdir(exist_ok=True)
    summary_lines = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for filename, url, params in REQUESTS:
        line = f"{filename}: "
        try:
            resp = session.get(url, params=params, timeout=25)
            body = resp.text
            (OUT_DIR / filename).write_text(body, encoding="utf-8")
            info = classify(body, resp.headers.get("Content-Type", ""))
            line += f"HTTP {resp.status_code}, {len(body)} байт, {info}"
        except Exception as exc:  # noqa: BLE001
            line += f"ОШИБКА: {exc}"
        print(line)
        summary_lines.append(line)
        time.sleep(1.5)  # вежливая пауза между запросами

    (OUT_DIR / "index.txt").write_text("\n".join(summary_lines), encoding="utf-8")

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(OUT_DIR.iterdir()):
            zf.write(f, f.name)

    print()
    print(f"Готово! Пришли в чат файл: {ZIP_PATH}")


if __name__ == "__main__":
    main()
