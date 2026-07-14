"""Playwright-разведчик для realt.by.

Открывает realt.by в настоящем браузере (Chromium), перехватывает сетевые
запросы к их API (GraphQL/REST) и сохраняет пары запрос/ответ + __NEXT_DATA__
страниц. По этим данным пишется чистый парсер коммерческой недвижимости.

Ничего не отправляет и не логинится — только открывает публичные страницы
и записывает трафик локально.

Запуск:
    pip3 install playwright
    python3 -m playwright install chromium   # один раз, если ещё не стоит
    python3 realt_scout.py
Результат: realt_debug.zip — пришли его в чат.
"""
import json
import re
import time
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path(__file__).parent / "realt_debug"
ZIP_PATH = Path(__file__).parent / "realt_debug.zip"

# Адреса, которые ищем на сайте (для перехвата geo-suggest -> streetUuid)
SEARCH_QUERIES = ["Михаила Савицкого 24", "Жореса Алфёрова 22"]

# Страницы листингов, которые открываем (чтобы поймать API-запрос списка и категории)
PAGES = [
    "https://realt.by/sale/flats/",        # квартиры (продажа) — заведомо рабочая
    "https://realt.by/sale/commercial/",   # коммерция (продажа) — проверим редирект/404
    "https://realt.by/rent/commercial/",   # коммерция (аренда)
    "https://realt.by/",                    # главная (поиск по адресу)
]

INTERESTING = ("graphql", "/api/", "/bff/", "suggest", "geo", "search")


def _sanitize(name):
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)[:80]


def main():
    OUT_DIR.mkdir(exist_ok=True)
    captured = []
    summary = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/opt/pw-browsers/chromium",
            headless=True,
        )
        ctx = browser.new_page(
            viewport={"width": 1400, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
        )

        def on_response(resp):
            url = resp.url
            if not any(k in url.lower() for k in INTERESTING):
                return
            try:
                body = resp.text()
            except Exception:
                return
            if len(body) < 20:
                return
            req = resp.request
            captured.append(
                {
                    "url": url,
                    "status": resp.status,
                    "method": req.method,
                    "request_body": req.post_data,
                    "response_body": body[:400000],
                }
            )

        ctx.on("response", on_response)

        # 1) Открываем страницы листингов, сохраняем __NEXT_DATA__
        for url in PAGES:
            try:
                ctx.goto(url, wait_until="networkidle", timeout=40000)
                ctx.wait_for_timeout(2500)
                html = ctx.content()
                fname = "page_" + _sanitize(url.replace("https://realt.by/", "").strip("/") or "home") + ".html"
                m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
                if m:
                    (OUT_DIR / fname.replace(".html", "_nextdata.json")).write_text(m.group(1), encoding="utf-8")
                status_line = f"{url} -> открыто, __NEXT_DATA__ {'есть' if m else 'нет'}"
            except Exception as exc:
                status_line = f"{url} -> ОШИБКА: {exc}"
            print(status_line)
            summary.append(status_line)
            time.sleep(1.5)

        # 2) Поиск по адресу (ловим geo-suggest -> streetUuid)
        for q in SEARCH_QUERIES:
            try:
                ctx.goto("https://realt.by/", wait_until="networkidle", timeout=40000)
                ctx.wait_for_timeout(1500)
                # пробуем найти поле поиска и ввести адрес
                box = None
                for sel in ["input[type='search']", "input[placeholder*='дрес']",
                            "input[placeholder*='оиск']", "input"]:
                    loc = ctx.locator(sel).first
                    if loc.count() > 0:
                        box = loc
                        break
                if box:
                    box.click()
                    box.type(q, delay=90)
                    ctx.wait_for_timeout(3000)  # ждём выпадающие подсказки (suggest API)
                    status_line = f"поиск '{q}' -> ввёл в поле"
                else:
                    status_line = f"поиск '{q}' -> поле поиска не найдено"
            except Exception as exc:
                status_line = f"поиск '{q}' -> ОШИБКА: {exc}"
            print(status_line)
            summary.append(status_line)
            time.sleep(1.5)

        browser.close()

    # Сохраняем перехваченные API-вызовы
    for i, c in enumerate(captured):
        (OUT_DIR / f"api_{i:02d}.json").write_text(
            json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    summary.append(f"\nперехвачено API-вызовов: {len(captured)}")
    for c in captured:
        summary.append(f"  {c['method']} {c['status']} {c['url'][:110]}")

    (OUT_DIR / "index.txt").write_text("\n".join(summary), encoding="utf-8")

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(OUT_DIR.iterdir()):
            zf.write(f, f.name)

    print()
    print(f"Готово! Пришли в чат файл: {ZIP_PATH}")


if __name__ == "__main__":
    main()
