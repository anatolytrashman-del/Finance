"""Playwright-разведчик для avito.ru — поиск земельных участков по области на карте.

В отличие от kufar/realt, тут нет фиксированного адреса — есть произвольная
область, которую ты рисуешь руками на карте Avito. Заранее я не знаю ни
формата этой области в их API, ни точного пути в интерфейсе, поэтому
скрипт НЕ ходит по сайту сам — он открывает настоящее окно браузера и даёт
тебе поработать с сайтом как обычно, а сам в фоне записывает весь сетевой
трафик (запросы к их внутреннему API). Ничего не логинится и не отправляет
самостоятельно — только слушает.

Что нужно сделать руками, когда откроется окно браузера:
  1. Перейди в раздел «Земельные участки» (Недвижимость -> Земельные участки).
  2. Открой поиск по карте / нарисуй нужную область (обычно значок карты
     рядом с фильтрами или кнопка «Показать на карте»).
  3. Нарисуй свою область поверх карты и запусти поиск.
  4. Полистай результаты (2-3 страницы) и открой 1-2 конкретных объявления
     об участке — это поможет понять формат карточки объявления.
  5. Вернись в терминал и нажми Enter — скрипт закроет браузер и соберёт дамп.

Запуск:
    pip3 install playwright
    python3 -m playwright install chromium   # один раз, если ещё не стоит
    python3 avito_scout.py
Результат: avito_debug.zip — пришли его в чат.
"""
import json
import re
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path(__file__).parent / "avito_debug"
ZIP_PATH = Path(__file__).parent / "avito_debug.zip"

# Ловим всё похожее на внутренний API — лишнее (картинки/шрифты/аналитика)
# отсекается по размеру ответа ниже.
INTERESTING = ("api", "graphql", "/web/", "search", "map", "geo", "polygon", "region", "item")

# Явно НЕ интересное — даже если совпало с INTERESTING по имени, эти домены
# почти наверняка аналитика/реклама, а не данные объявлений.
SKIP_HOSTS = ("google", "yandex.ru/clck", "mc.yandex", "doubleclick", "facebook", "vk.com/rtrg")


def _sanitize(name):
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)[:80]


def _extract_window_states(html):
    """Ищет window.__ИМЯ__ = {...} в HTML и вырезает JSON честным подсчётом
    скобок (не regex — вложенные объекты ломают жадность/нежадность .*?).
    Возвращает {var_name: json_text}."""
    found = {}
    for m in re.finditer(r"window\.(__\w+__)\s*=\s*\{", html):
        var_name = m.group(1)
        start = m.end() - 1  # позиция открывающей '{'
        depth, in_str, str_quote, escape = 0, False, "", False
        end = None
        for i in range(start, min(start + 3_000_000, len(html))):
            ch = html[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == str_quote:
                    in_str = False
                continue
            if ch in ("'", '"'):
                in_str, str_quote = True, ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end:
            found[var_name] = html[start:end]
    return found


def main():
    OUT_DIR.mkdir(exist_ok=True)
    captured = []
    pages_saved = []

    with sync_playwright() as p:
        # headless=False — окно должно быть видимым, ты будешь работать в нём руками
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_page(
            viewport={"width": 1440, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
        )

        def on_response(resp):
            url = resp.url
            low = url.lower()
            if any(h in low for h in SKIP_HOSTS):
                return
            if not any(k in low for k in INTERESTING):
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
            print(f"  поймал: {req.method} {resp.status} {url[:120]}")

        ctx.on("response", on_response)

        print("\nОткрываю avito.ru...")
        ctx.goto("https://www.avito.ru/", wait_until="domcontentloaded", timeout=40000)

        print(
            "\n=== ТВОЙ ХОД ===\n"
            "1. Перейди в «Земельные участки» (обычно Недвижимость -> Земельные участки).\n"
            "2. Открой поиск/фильтр по карте, нарисуй свою область.\n"
            "3. Запусти поиск, полистай 2-3 страницы результатов.\n"
            "4. Открой 1-2 конкретных объявления об участке.\n"
            "5. Когда закончишь — вернись сюда и нажми Enter.\n"
        )
        input("Нажми Enter, когда всё сделаешь... ")

        # финальный снимок текущей страницы (что бы на ней ни было в этот момент)
        try:
            html = ctx.content()
            (OUT_DIR / "final_page.html").write_text(html, encoding="utf-8")
            pages_saved.append(ctx.url)
            # на всякий случай вытащим любые script-блоки с явным «начальным состоянием» —
            # частый паттерн у SPA (window.__INITIAL_STATE__ и т.п.)
            for var_name, blob in _extract_window_states(html).items():
                (OUT_DIR / f"state_{_sanitize(var_name)}.json").write_text(blob[:2_000_000], encoding="utf-8")
                print(f"  нашёл window.{var_name} — сохранил")
        except Exception as exc:  # noqa: BLE001
            print(f"  не удалось сохранить финальную страницу: {exc}")

        browser.close()

    for i, c in enumerate(captured):
        (OUT_DIR / f"api_{i:03d}.json").write_text(
            json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    summary = [f"текущий URL на момент завершения: {pages_saved[0] if pages_saved else '—'}",
               f"перехвачено интересных запросов: {len(captured)}", ""]
    for c in captured:
        summary.append(f"  {c['method']} {c['status']} {c['url'][:140]}")
    (OUT_DIR / "index.txt").write_text("\n".join(summary), encoding="utf-8")

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(OUT_DIR.iterdir()):
            zf.write(f, f.name)

    print()
    print(f"Готово! Перехвачено запросов: {len(captured)}")
    print(f"Пришли в чат файл: {ZIP_PATH}")


if __name__ == "__main__":
    main()
