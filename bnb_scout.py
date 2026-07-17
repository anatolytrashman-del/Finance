"""Playwright-разведчик для bnb.by — курсы обмена валют (виджет-конвертер).

Нужны пары RUB/USD (участок, счета) и EUR/USD (договоры в евро). Заранее не
известно, дёргает ли конвертер свой внутренний API при пересчёте, или курсы
уже зашиты в HTML страницы — поэтому скрипт ничего не делает сам, а открывает
настоящее окно браузера и даёт тебе поработать с сайтом руками, слушая в
фоне весь сетевой трафик. Ничего не логинится и никуда не отправляет —
только слушает публичные ответы сайта.

Что нужно сделать руками, когда откроется окно браузера:
  1. Найди на главной странице блок обмена валют (конвертер «Я отдаю / Я
     получаю» — как на твоём скриншоте).
  2. Попробуй выставить пару напрямую: «Я отдаю» = RUB, «Я получаю» = USD.
     Введи любую сумму (например 1000) и подожди 2-3 секунды.
  3. Если USD нет в списке того, что можно получить за RUB (конвертер может
     уметь считать только против BYN) — тогда отдельно сделай RUB -> BYN и
     USD -> BYN (тоже с суммой и паузой) — курс RUB/USD посчитаем сам через
     кросс-курс к BYN.
  4. Повтори то же самое для EUR: сначала попробуй EUR -> USD напрямую,
     если нет — EUR -> BYN (плюс USD -> BYN уже будет из шага 3).
  5. Вернись в терминал и нажми Enter — скрипт закроет браузер и соберёт дамп.

Запуск:
    pip3 install playwright
    python3 -m playwright install chromium   # один раз, если ещё не стоит
    python3 bnb_scout.py
Результат: bnb_debug.zip — пришли его в чат.
"""
import json
import re
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path(__file__).parent / "bnb_debug"
ZIP_PATH = Path(__file__).parent / "bnb_debug.zip"

# Ловим всё похожее на внутренний API обмена валют — лишнее (картинки/шрифты/
# аналитика) отсекается по размеру ответа ниже.
INTERESTING = ("rate", "exchange", "currency", "convert", "calc", "api", "kurs", "курс")

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
            if len(body) < 5:
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

        print("\nОткрываю bnb.by...")
        ctx.goto("https://bnb.by/", wait_until="domcontentloaded", timeout=40000)

        print(
            "\n=== ТВОЙ ХОД ===\n"
            "1. Найди на главной блок обмена валют («Я отдаю / Я получаю»).\n"
            "2. Попробуй пару RUB -> USD напрямую, введи сумму, подожди пару секунд.\n"
            "3. Если USD нет в списке при RUB — сделай отдельно RUB -> BYN и USD -> BYN.\n"
            "4. То же самое для EUR: сначала EUR -> USD напрямую, если нет — EUR -> BYN.\n"
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
