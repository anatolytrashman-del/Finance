"""Курсы обмена валют bnb.by (Белорусский Народный Банк) — RUB/USD, EUR/USD.

Разведка (bnb_scout.py) показала: конвертер «Я отдаю / Я получаю» на bnb.by
не дёргает отдельный API — таблица курсов уже отрисована сервером прямо в
HTML главной страницы, а сам виджет просто пересчитывает эти же цифры на
клиенте кросс-курсом через BYN (базовая валюта банка). Значит и нам не
нужен браузер — обычный requests.get + разбор таблицы, как для kufar/realt.

Таблица на сайте — курсы каждой валюты к BYN отдельно (нет прямых пар
RUB/USD или EUR/USD), поэтому RUB/USD и EUR/USD считаются как кросс-курс
через BYN, по средней между «Сдать»/«Купить» (не берём сторону спреда —
это ориентир для отчётности, а не рыночная сделка).
"""
import re

import requests

RATES_URL = "https://bnb.by/"
REQUEST_TIMEOUT = 10

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}

# Только первый блок курсов на странице — тот, что в виджете «Я отдаю/Я получаю»
# (после него на странице идут другие таблицы — курс для карт и т.п., нам не нужны).
_TABLE_RE = re.compile(r'<div class="rates-table-wrap[^"]*">.*?</table>', re.S)
_ROW_RE = re.compile(
    r'alt="([A-Z]{3})">\s*(\d+)\s*\1</td>\s*<td>\s*<span class="currency_value">([\d.]+)</span>.*?'
    r'<td class="currency__td_value">\s*<span class="currency_value">([\d.]+)</span>',
    re.S,
)


def _parse_table(html):
    """{code: {'unit': int, 'sell_byn': float, 'buy_byn': float}} за unit валюты.
    sell_byn — курс «Сдать» (банк платит тебе BYN, когда ты отдаёшь эту валюту),
    buy_byn — курс «Купить» (ты платишь банку BYN, чтобы получить эту валюту)."""
    block_match = _TABLE_RE.search(html)
    if not block_match:
        return {}
    rates = {}
    for code, unit, sell, buy in _ROW_RE.findall(block_match.group(0)):
        rates[code] = {"unit": int(unit), "sell_byn": float(sell), "buy_byn": float(buy)}
    return rates


def _mid_byn_per_unit(entry):
    return (entry["sell_byn"] + entry["buy_byn"]) / 2 / entry["unit"]


def fetch_rates():
    """Возвращает (rates_dict, warning). rates_dict — None при ошибке."""
    try:
        resp = requests.get(RATES_URL, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return None, f"bnb.by: не удалось загрузить страницу ({exc})"

    table = _parse_table(resp.text)
    missing = [c for c in ("USD", "EUR", "RUB") if c not in table]
    if missing:
        return None, (
            f"bnb.by: не нашёл в таблице курсов валюты {', '.join(missing)} — "
            "похоже, изменилась вёрстка страницы"
        )

    byn_per_usd = _mid_byn_per_unit(table["USD"])
    byn_per_eur = _mid_byn_per_unit(table["EUR"])
    byn_per_rub = _mid_byn_per_unit(table["RUB"])

    return {
        "byn_per_usd": byn_per_usd,
        "byn_per_eur": byn_per_eur,
        "byn_per_rub": byn_per_rub,
        "usd_per_rub": byn_per_rub / byn_per_usd,
        "usd_per_eur": byn_per_eur / byn_per_usd,
        "raw": table,
    }, None
