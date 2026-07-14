"""Расчёт финмодели продажи с учётом графика платежей (XIRR) и подтягивание
взносов по объекту из листа «Сделки».

Доходность зависит не только от сумм, но и от дат платежей: доллар, внесённый
позже (рассрочка), «работает» меньше, поэтому реальная годовая доходность
считается через XIRR по всем движениям денег с их датами.
"""
import re
from datetime import date, datetime

import pandas as pd

import config
from parsers import parse_money

SALE_TAX_BASES = ["От полной суммы продажи", "От прибыли"]

# Кириллические буквы, визуально совпадающие с латинскими — сводим к латинице,
# чтобы код «Т1639» (кир.) и «T1639» (лат.) считались одним объектом.
_CYR_TO_LAT = str.maketrans("АВЕКМНОРСТУХ", "ABEKMHOPCTYX")


def _norm_key(value):
    """Нормализует код объекта: регистр, пробелы, кириллица→латиница."""
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value).strip().upper().translate(_CYR_TO_LAT))


# --------------------------- XIRR ---------------------------

def _parse_date(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return pd.to_datetime(value).date()
    except Exception:  # noqa: BLE001
        return None


def xirr(cashflows):
    """Годовая доходность (доля) по списку (date, amount). amount<0 — вложения,
    amount>0 — поступления. Возвращает None, если IRR не определён."""
    flows = [(d, float(a)) for d, a in cashflows if d is not None and a]
    if len(flows) < 2:
        return None
    amounts = [a for _, a in flows]
    if not (any(a > 0 for a in amounts) and any(a < 0 for a in amounts)):
        return None  # нужен хотя бы один вложенный и один полученный поток

    d0 = min(d for d, _ in flows)

    def npv(rate):
        total = 0.0
        for d, a in flows:
            t = (d - d0).days / 365.0
            total += a / ((1.0 + rate) ** t)
        return total

    lo, hi = -0.9999, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    tries = 0
    while f_lo * f_hi > 0 and hi < 1e7 and tries < 80:
        hi *= 2.0
        f_hi = npv(hi)
        tries += 1
    if f_lo * f_hi > 0:
        return None  # знак не меняется — решения нет

    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if abs(f_mid) < 1e-7:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


# --------------------------- Расчёт ---------------------------

def compute_sale(m):
    payments = m.get("payments") or []
    total_invested = sum(float(p.get("amount") or 0) for p in payments)
    sell = float(m.get("sell_price") or 0)
    pct = float(m.get("tax_pct") or 0)
    base = m.get("tax_base") or SALE_TAX_BASES[0]

    if base == SALE_TAX_BASES[1]:  # от прибыли (только с положительной)
        tax = max(sell - total_invested, 0) * pct / 100
    else:  # от полной суммы продажи
        tax = sell * pct / 100
    proceeds = sell - tax
    net = proceeds - total_invested
    total_return = net / total_invested * 100 if total_invested > 0 else None

    cashflows = []
    for p in payments:
        d = _parse_date(p.get("date"))
        amount = float(p.get("amount") or 0)
        if d and amount > 0:
            cashflows.append((d, -amount))
    sell_date = _parse_date(m.get("sell_date"))
    if sell_date and proceeds:
        cashflows.append((sell_date, proceeds))

    irr = xirr(cashflows)
    annual = irr * 100 if irr is not None else None
    dates = [d for d, _ in cashflows]
    years = (max(dates) - min(dates)).days / 365.0 if len(dates) >= 2 else None

    return {
        "total_invested": total_invested,
        "sell": sell,
        "tax": tax,
        "proceeds": proceeds,
        "net": net,
        "total_return": total_return,
        "annual": annual,
        "years": years,
    }


# --------------------------- Реестр сделок ---------------------------

def _object_label(row):
    """Человеческое имя объекта: «Тип — Локация» (код «Объект» тут не участвует)."""
    parts = [str(row.get(config.REALESTATE_TYPE_COLUMN) or "").strip(),
             str(row.get(config.REALESTATE_LOCATION_COLUMN) or "").strip()]
    return " — ".join(p for p in parts if p) or "Объект"


def object_choices(real_estate_df, deals_df=None):
    """Список объектов для выбора: [{key, label, total_purchase}].

    Ключи-коды берутся из столбца «Объект» ОБОИХ листов (объединение), поэтому
    объект виден, даже если код проставлен только в «Сделках». Сравнение —
    через _norm_key (устойчиво к латинице/кириллице). total_purchase —
    «Сумма покупки в $» из «Real Estate» (нужна для расчёта остатка)."""
    by_norm = {}  # norm -> {key, label, total}

    if real_estate_df is not None and not real_estate_df.empty:
        for _, row in real_estate_df.iterrows():
            label = _object_label(row)
            total = parse_money(row.get(config.REALESTATE_PURCHASE_COLUMN))
            market = parse_money(row.get(config.REALESTATE_MARKET_COLUMN))
            tag = row.get(config.REALESTATE_OBJECT_COLUMN)
            if isinstance(tag, str) and tag.strip():
                nk = _norm_key(tag)
                disp = f"{tag.strip()} · {label}"
                by_norm[nk] = {"key": tag.strip(), "label": disp, "total_purchase": total, "market": market}
            else:  # объект без кода — ключом служит его ярлык
                nk = _norm_key(label)
                by_norm.setdefault(nk, {"key": label, "label": label, "total_purchase": total, "market": market})

    obj_col = config.DEALS_OBJECT_COLUMN
    if deals_df is not None and not deals_df.empty and obj_col in deals_df.columns:
        for value in deals_df[obj_col].dropna().unique():
            code = str(value).strip()
            if not code:
                continue
            nk = _norm_key(code)
            if nk not in by_norm:  # код есть только в «Сделках»
                by_norm[nk] = {"key": code, "label": f"{code} (только в «Сделках»)",
                               "total_purchase": None, "market": None}

    return [{"key": v["key"], "label": v["label"], "total_purchase": v["total_purchase"],
             "market": v.get("market")} for v in by_norm.values()]


def pull_payments(deals_df, object_key):
    """Взносы «Покупка» по объекту из «Сделок» -> [{date: iso, amount: float}].

    Точное совпадение по нормализованному коду в DEALS_OBJECT_COLUMN, иначе —
    поиск кода по вхождению в текст DEALS_PURPOSE_COLUMN."""
    if deals_df is None or deals_df.empty or not object_key:
        return []
    df = deals_df
    type_col = config.DEALS_TYPE_COLUMN
    if type_col in df.columns:
        df = df[df[type_col] == config.DEALS_PURCHASE_VALUE]
    if df.empty:
        return []

    key_norm = _norm_key(object_key)
    obj_col = config.DEALS_OBJECT_COLUMN
    purpose_col = config.DEALS_PURPOSE_COLUMN
    if obj_col in df.columns and df[obj_col].notna().any():
        mask = df[obj_col].apply(lambda v: _norm_key(v) == key_norm if pd.notna(v) else False)
    elif purpose_col in df.columns:
        mask = df[purpose_col].apply(lambda v: key_norm in _norm_key(v) if pd.notna(v) else False)
    else:
        return []

    payments = []
    date_col, amount_col = config.DEALS_DATE_COLUMN, config.DEALS_AMOUNT_COLUMN
    for _, row in df[mask].iterrows():
        d = _parse_date(row.get(date_col))
        raw_amount = row.get(amount_col)
        amount = raw_amount if isinstance(raw_amount, (int, float)) else parse_money(raw_amount)
        if d is None or amount is None:
            continue
        payments.append({"date": d.isoformat(), "amount": abs(float(amount))})
    payments.sort(key=lambda p: p["date"])
    return payments
