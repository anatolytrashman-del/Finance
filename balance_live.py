"""Пересчёт «сегодняшней» точки капитала/долга по текущему курсу (bnb.by).

История на дашборде (лист «Прогресс») — фиксированные числа, их не трогаем.
Для последней точки берём тот же помесячный срез баланса, что читает
views/balance.py (там у каждой строки есть исходная сумма, валюта и курс,
зафиксированный на момент среза), и пересчитываем только рублёвые/евровые
строки по текущему курсу bnb.by вместо курса среза — остальное ($, USDT и
то, что не входит в итог) не трогаем. Разница добавляется к «Итого капитал»
и к «Обязательства» из среза. Ничего не пишется обратно в Google-таблицу —
пересчёт только для показа на дашборде."""

# Секции parse_balance(), которые входят в «Итого капитал» (без frozen —
# заблокированные бумаги показаны отдельно и не входят в баланс).
CAPITAL_KEYS = ["bank", "cash", "crypto", "returns", "loans", "real_estate", "art", "business"]


def _reprice_delta(items, live_rates):
    """Сумма (новый usd - старый usd) по всем ₽/€ строкам — на сколько
    изменился бы итог, если взять сегодняшний курс вместо курса среза."""
    delta = 0.0
    for it in items or []:
        cur = it.get("currency")
        orig = it.get("orig")
        old_usd = it.get("usd") or 0.0
        if cur == "₽" and orig is not None and live_rates.get("usd_per_rub"):
            delta += orig * live_rates["usd_per_rub"] - old_usd
        elif cur == "€" and orig is not None and live_rates.get("usd_per_eur"):
            delta += orig * live_rates["usd_per_eur"] - old_usd
    return delta


def recalc_live_totals(balance, live_rates):
    """balance — результат parse_balance(). live_rates — dict с usd_per_rub/
    usd_per_eur (bnb_rates.fetch_rates()). Возвращает (grand_total_live,
    obligations_total_live) или (None, None), если пересчитать нечем."""
    if balance is None or not live_rates:
        return None, None

    delta_capital = sum(_reprice_delta(balance.get(k), live_rates) for k in CAPITAL_KEYS)
    delta_obligations = _reprice_delta(balance.get("obligations"), live_rates)

    grand_total = balance.get("grand_total")
    if grand_total is None:
        grand_total = sum((it["usd"] or 0.0) for k in CAPITAL_KEYS for it in balance.get(k) or [])
    grand_total_live = grand_total + delta_capital

    obligations_total = balance.get("obligations_total")
    if obligations_total is None:
        obligations_total = sum((it["usd"] or 0.0) for it in balance.get("obligations") or [])
    obligations_total_live = obligations_total + delta_obligations

    return grand_total_live, obligations_total_live
