"""Playwright-разведчик для bir.by — цены застройщика по 16 и 11 кварталам.

В отличие от avito/realt, тут не нужно ничего делать руками: страницы сами
показывают полный список юнитов, а кнопки этажей (судя по описанию) не
меняют URL — значит все данные по категории (?sort=live/com/park/klad),
скорее всего, приходят в ответ на один запрос и просто фильтруются на
клиенте по этажу. Поэтому скрипт просто открывает по очереди все ссылки
ниже (headless, без участия человека) и на каждой:
  1. слушает сетевые ответы, которые похожи на данные о юнитах (api/ajax/json);
  2. сохраняет window.__ИМЯ__ = {...}, если такое есть на странице;
  3. сохраняет финальный HTML целиком (на случай, если данные просто
     отрисованы в таблицу без отдельного API-запроса — тогда распарсим
     прямо HTML).

Ничего не логинится и никуда не отправляет — только открывает публичные
страницы и записывает, что видит.

Запуск:
    pip3 install playwright
    python3 -m playwright install chromium   # один раз, если ещё не стоит
    python3 bir_scout.py
Результат: bir_debug.zip — пришли его в чат.
"""
import json
import re
import time
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path(__file__).parent / "bir_debug"
ZIP_PATH = Path(__file__).parent / "bir_debug.zip"

# (метка дома, базовый URL). Слаг сортировки (?sort=...) добавляется отдельно.
HOUSES = [
    ("16.1 Нясвижский замок", "https://bir.by/page/real-estate/minskworld/planirovki-kvartal-16/dom-nyasvizhski-zamak/"),
    ("16.2 Мирский замок", "https://bir.by/page/real-estate/minskworld/planirovki-kvartal-16/dom-mirskij-zamok/"),
    ("11.5 Адриатик", "https://bir.by/page/real-estate/minskworld/planirovki-kvartal-11-avstraliya-i-okeaniya/dom-adriatik/"),
    ("11.3 Атлантик", "https://bir.by/page/real-estate/minskworld/planirovki-kvartal-11-avstraliya-i-okeaniya/dom-atlantik/"),
    ("11.1 Каспиан", "https://bir.by/kaspian/"),
    ("11.6 Карибиан", "https://bir.by/page/real-estate/minskworld/planirovki-kvartal-11-avstraliya-i-okeaniya/dom-karibian/"),
    ("11.4 Пацифик", "https://bir.by/page/real-estate/minskworld/planirovki-kvartal-11-avstraliya-i-okeaniya/dom-paczifik/"),
    ("11.2 Медитерраниан", "https://bir.by/dom-mediteranian/"),
]

# Не для каждого дома подтверждены все 4 категории (пользователь просил
# проверить ?sort=com для всех домов «по аналогии») — просто пробуем все,
# пустой/ошибочный результат по конкретному дому не страшен, увидим по логу.
SORTS = {
    "live": "Квартиры/апартаменты",
    "com": "Коммерческие помещения",
    "park": "Машиноместа",
    "klad": "Кладовые",
}

PAGE_PAUSE_SEC = 1.5

INTERESTING = ("api", "ajax", "json", "flat", "kvart", "plan", "unit", "search", "filter", "sort", "estate")
SKIP_HOSTS = ("google", "yandex.ru/clck", "mc.yandex", "doubleclick", "facebook", "vk.com/rtrg", "tiktok")


def _sanitize(name):
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)[:100]


def _extract_window_states(html):
    """Ищет window.__ИМЯ__ = {...} в HTML и вырезает JSON честным подсчётом
    скобок (не regex — вложенные объекты ломают жадность/нежадность .*?).
    Возвращает {var_name: json_text}."""
    found = {}
    for m in re.finditer(r"window\.(\w+)\s*=\s*(\{|\[)", html):
        var_name = m.group(1)
        open_ch, close_ch = (m.group(2), "}" if m.group(2) == "{" else "]")
        start = m.end() - 1
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
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end and end - start > 20:  # отсекаем мусорные однострочные переменные
            found[var_name] = html[start:end]
    return found


def main():
    OUT_DIR.mkdir(exist_ok=True)
    all_captured = []
    summary = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1440, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
        )

        captured_this_page = []

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
            captured_this_page.append(
                {"url": url, "status": resp.status, "method": req.method,
                 "request_body": req.post_data, "response_body": body[:600000]}
            )

        page.on("response", on_response)

        total = len(HOUSES) * len(SORTS)
        n = 0
        for house_label, base_url in HOUSES:
            for sort_key, sort_label in SORTS.items():
                n += 1
                url = f"{base_url}?sort={sort_key}"
                captured_this_page.clear()
                print(f"[{n}/{total}] {house_label} · {sort_label} -> {url}")
                try:
                    page.goto(url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(1500)
                    html = page.content()
                except Exception as exc:  # noqa: BLE001
                    line = f"  ОШИБКА: {exc}"
                    print(line)
                    summary.append(f"{house_label} · {sort_label} ({url}): ОШИБКА {exc}")
                    time.sleep(PAGE_PAUSE_SEC)
                    continue

                fname_base = _sanitize(f"{house_label}_{sort_key}")
                (OUT_DIR / f"page_{fname_base}.html").write_text(html, encoding="utf-8")
                states = _extract_window_states(html)
                for var_name, blob in states.items():
                    (OUT_DIR / f"state_{fname_base}_{_sanitize(var_name)}.json").write_text(
                        blob[:2_000_000], encoding="utf-8"
                    )
                for c in captured_this_page:
                    c["house"] = house_label
                    c["sort"] = sort_key
                    all_captured.append(c)

                line = f"  html: {len(html)} байт · window-state блоков: {len(states)} · сетевых ответов: {len(captured_this_page)}"
                print(line)
                summary.append(f"{house_label} · {sort_label} ({url}) -> {line.strip()}")
                time.sleep(PAGE_PAUSE_SEC)

        browser.close()

    for i, c in enumerate(all_captured):
        (OUT_DIR / f"api_{i:03d}_{_sanitize(c['house'])}_{c['sort']}.json").write_text(
            json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    summary.append(f"\nвсего перехвачено сетевых ответов: {len(all_captured)}")
    (OUT_DIR / "index.txt").write_text("\n".join(summary), encoding="utf-8")

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(OUT_DIR.iterdir()):
            zf.write(f, f.name)

    print()
    print(f"Готово! Пришли в чат файл: {ZIP_PATH}")


if __name__ == "__main__":
    main()
