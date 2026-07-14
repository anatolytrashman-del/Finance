"""Финмодель «покупка + сдача в аренду».

Считает реальную доходность лота, где есть и рост стоимости, и арендный доход.
Годовая доходность — через XIRR (как в модели продажи): вложения по датам
(взносы за покупку + ремонт), арендный доход помесячно с даты сдачи, а текущая
рыночная стоимость учитывается как «виртуальная продажа» сегодня.
"""
from datetime import date

import pandas as pd

from sale_finmodel import _parse_date, xirr

MONTH_DAYS = 30.4375  # средняя длина месяца (365.25 / 12)


def _today():
    return date.today()


def compute_buyrent(m):
    payments = m.get("payments") or []
    invested_payments = sum(float(p.get("amount") or 0) for p in payments)
    reno = float(m.get("reno") or 0)
    invested = invested_payments + reno

    market = m.get("market_value")
    market = float(market) if market not in (None, "") else None
    rent_month = float(m.get("rent_month") or 0)
    rent_start = _parse_date(m.get("rent_start"))
    today = _today()

    months_rented = 0.0
    if rent_start and rent_start <= today:
        months_rented = (today - rent_start).days / MONTH_DAYS
    annual_rent = rent_month * 12
    cumulative_rent = rent_month * months_rented

    appreciation = (market - invested) if market is not None else None
    appr_return = (appreciation / invested * 100) if (appreciation is not None and invested > 0) else None
    rent_yield_annual = (annual_rent / invested * 100) if invested > 0 else None
    rent_yield_cum = (cumulative_rent / invested * 100) if invested > 0 else None

    total_gain = None
    total_return = None
    if appreciation is not None:
        total_gain = appreciation + cumulative_rent
        if invested > 0:
            total_return = total_gain / invested * 100

    # --- XIRR: вложения (−), аренда помесячно (+), текущая стоимость (+) ---
    cashflows = []
    for p in payments:
        d = _parse_date(p.get("date"))
        amount = float(p.get("amount") or 0)
        if d and amount > 0:
            cashflows.append((d, -amount))
    reno_date = _parse_date(m.get("reno_date"))
    if reno > 0 and reno_date:
        cashflows.append((reno_date, -reno))
    if rent_month and rent_start:
        cur = pd.Timestamp(rent_start)
        end = pd.Timestamp(today)
        while cur <= end:
            cashflows.append((cur.date(), rent_month))
            cur += pd.DateOffset(months=1)
    if market is not None:
        cashflows.append((today, market))  # «виртуальная продажа» сегодня

    irr = xirr(cashflows)
    annual = irr * 100 if irr is not None else None
    dates = [d for d, _ in cashflows]
    years = (max(dates) - min(dates)).days / 365.0 if len(dates) >= 2 else None

    return {
        "invested": invested,
        "invested_payments": invested_payments,
        "reno": reno,
        "market": market,
        "months_rented": months_rented,
        "annual_rent": annual_rent,
        "cumulative_rent": cumulative_rent,
        "appreciation": appreciation,
        "appr_return": appr_return,
        "rent_yield_annual": rent_yield_annual,
        "rent_yield_cum": rent_yield_cum,
        "total_gain": total_gain,
        "total_return": total_return,
        "annual": annual,
        "years": years,
    }
