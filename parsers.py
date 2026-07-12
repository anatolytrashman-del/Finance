"""Разбор листов книги в pandas DataFrame."""
import re

import pandas as pd

PROGRESS_SHEET = "Прогресс"
DEALS_SHEET = "Сделки"
REAL_ESTATE_SHEET = "Real Estate"


def _find_sheet(wb, name):
    target = name.strip().lower()
    for sheet_name in wb.sheetnames:
        if sheet_name.strip().lower() == target:
            return wb[sheet_name]
    return None


def _series_by_label(ws, label: str) -> pd.DataFrame:
    """Ищет в первой строке заголовок label и читает пару колонок (дата, значение)."""
    max_col = ws.max_column
    for col in range(1, max_col + 1):
        header = ws.cell(row=1, column=col).value
        if isinstance(header, str) and header.strip() == label:
            dates, values = [], []
            for row in range(2, ws.max_row + 1):
                d = ws.cell(row=row, column=col).value
                v = ws.cell(row=row, column=col + 1).value
                if d is None or v is None:
                    continue
                dates.append(d)
                values.append(v)
            df = pd.DataFrame({"date": pd.to_datetime(dates), "value": values})
            return df.sort_values("date").reset_index(drop=True)
    return pd.DataFrame(columns=["date", "value"])


def parse_progress(wb) -> dict:
    ws = _find_sheet(wb, PROGRESS_SHEET)
    if ws is None:
        return {}
    return {
        "capital_usd": _series_by_label(ws, "Капитал в долларах"),
        "capital_rub": _series_by_label(ws, "Капитал в рублях"),
        "active_income": _series_by_label(ws, "Активный доход"),
        "passive_income": _series_by_label(ws, "Пассивный доход"),
        "debt": _series_by_label(ws, "Долговая нагрузка"),
    }


def _sheet_to_df(ws) -> pd.DataFrame:
    headers = [c.value for c in ws[1]]
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if all(v is None for v in row):
            continue
        rows.append(row)
    df = pd.DataFrame(rows, columns=headers)
    named_cols = [c for c in df.columns if pd.notna(c) and str(c).strip() != ""]
    df = df.loc[:, named_cols]
    df.columns = [str(c).strip() for c in df.columns]
    for col in df.columns:
        df[col] = df[col].apply(lambda v: v.strip() if isinstance(v, str) else v)
    return df


def parse_deals(wb) -> pd.DataFrame:
    ws = _find_sheet(wb, DEALS_SHEET)
    if ws is None:
        return pd.DataFrame()
    df = _sheet_to_df(ws)
    if "Дата" in df.columns:
        df = df.dropna(subset=["Дата"])
        df = df.sort_values("Дата", ascending=False).reset_index(drop=True)
    return df


def parse_real_estate(wb) -> pd.DataFrame:
    ws = _find_sheet(wb, REAL_ESTATE_SHEET)
    if ws is None:
        return pd.DataFrame()
    df = _sheet_to_df(ws)
    if "Тип" in df.columns:
        df = df.dropna(subset=["Тип"])
    return df.reset_index(drop=True)


def parse_money(value):
    """Превращает '$51 203', '- $8572', '$100 000 ' и т.п. в float (со знаком)."""
    if value is None:
        return None
    s = str(value)
    negative = "-" in s
    digits = re.sub(r"[^\d.]", "", s)
    if digits == "":
        return None
    amount = float(digits)
    return -amount if negative else amount


def parse_area(value):
    """Превращает '26 м²' -> {'value': 26.0, 'unit': 'м²'}, '5.6 Га' -> {'value': 5.6, 'unit': 'Га'}."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    is_hectare = "га" in s.lower()
    digits = re.sub(r"[^\d.,]", "", s).replace(",", ".")
    if digits == "":
        return None
    try:
        amount = float(digits)
    except ValueError:
        return None
    return {"value": amount, "unit": "Га" if is_hectare else "м²"}
