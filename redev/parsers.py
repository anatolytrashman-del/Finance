"""Разбор листа «Проекты» гугл-таблицы в pandas DataFrame + демо-данные.

Ожидаемые колонки листа «Проекты» (порядок любой, лишние игнорируются):
    Проект, Адрес, Город, Координаты, Текущее назначение, Целевое назначение,
    Площадь участка (сот), Площадь здания (м²), Аренд. площадь (м²),
    Стадия, Статус, Готовность %, Дата старта, План ввода,
    Бюджет CAPEX $, Вложено $, Ответственный, Комментарий
"""
import re

import pandas as pd

PROJECTS_SHEET = "Проекты"

# Канонический набор колонок карточки проекта.
COLUMNS = [
    "Проект",
    "Адрес",
    "Город",
    "Координаты",
    "Текущее назначение",
    "Целевое назначение",
    "Площадь участка (сот)",
    "Площадь здания (м²)",
    "Аренд. площадь (м²)",
    "Стадия",
    "Статус",
    "Готовность %",
    "Дата старта",
    "План ввода",
    "Бюджет CAPEX $",
    "Вложено $",
    "Ответственный",
    "Комментарий",
]

MONEY_COLS = ["Бюджет CAPEX $", "Вложено $"]
AREA_COLS = ["Площадь участка (сот)", "Площадь здания (м²)", "Аренд. площадь (м²)"]
PCT_COLS = ["Готовность %"]


def _find_sheet(wb, name):
    target = name.strip().lower()
    for sheet_name in wb.sheetnames:
        if sheet_name.strip().lower() == target:
            return wb[sheet_name]
    return None


def _rows_to_df(headers, rows) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=headers)
    named_cols = [c for c in df.columns if pd.notna(c) and str(c).strip() != ""]
    df = df.loc[:, named_cols]
    df.columns = [str(c).strip() for c in df.columns]
    for col in df.columns:
        df[col] = df[col].apply(lambda v: v.strip() if isinstance(v, str) else v)
    return df


def _sheet_to_df(ws) -> pd.DataFrame:
    headers = [c.value for c in ws[1]]
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if all(v is None for v in row):
            continue
        rows.append(row)
    return _rows_to_df(headers, rows)


def parse_number(value):
    """'$1 200 000', '1,2 млн', '65%', '3 500 м²' -> float. Понимает суффикс 'млн'/'млрд'."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().lower()
    if s == "":
        return None
    mult = 1.0
    if "млрд" in s:
        mult = 1_000_000_000.0
    elif "млн" in s:
        mult = 1_000_000.0
    elif "тыс" in s:
        mult = 1_000.0
    digits = re.sub(r"[^\d.,-]", "", s).replace(",", ".")
    # оставляем только первую точку как десятичный разделитель
    if digits.count(".") > 1:
        first = digits.find(".")
        digits = digits[: first + 1] + digits[first + 1 :].replace(".", "")
    if digits in ("", "-", ".", "-."):
        return None
    try:
        return float(digits) * mult
    except ValueError:
        return None


def _coerce(df: pd.DataFrame) -> pd.DataFrame:
    """Приводит числовые колонки к float и гарантирует наличие всех канонических колонок."""
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    for col in MONEY_COLS + AREA_COLS + PCT_COLS:
        df[col] = df[col].apply(parse_number)
    # Готовность: если пришло 0..1, переводим в проценты.
    df["Готовность %"] = df["Готовность %"].apply(
        lambda v: v * 100 if isinstance(v, float) and 0 <= v <= 1 else v
    )
    return df[COLUMNS].reset_index(drop=True)


def parse_projects(wb) -> pd.DataFrame:
    ws = _find_sheet(wb, PROJECTS_SHEET)
    if ws is None:
        return pd.DataFrame(columns=COLUMNS)
    df = _sheet_to_df(ws)
    if "Проект" in df.columns:
        df = df.dropna(subset=["Проект"])
    return _coerce(df)


def demo_projects() -> pd.DataFrame:
    """Пример из трёх проектов, чтобы увидеть интерфейс до подключения таблицы."""
    rows = [
        {
            "Проект": "Лофт-квартал «Красный Октябрь»",
            "Адрес": "Берсеневская наб., 6",
            "Город": "Москва",
            "Координаты": "55.7415, 37.6083",
            "Текущее назначение": "Складской корпус",
            "Целевое назначение": "Креативные офисы + ритейл",
            "Площадь участка (сот)": 42,
            "Площадь здания (м²)": 8600,
            "Аренд. площадь (м²)": 7100,
            "Стадия": "СМР",
            "Статус": "Активен",
            "Готовность %": 55,
            "Дата старта": "2025-03-01",
            "План ввода": "2026-12-01",
            "Бюджет CAPEX $": 6_800_000,
            "Вложено $": 3_900_000,
            "Ответственный": "А. Иванов",
            "Комментарий": "Идёт демонтаж и усиление перекрытий.",
        },
        {
            "Проект": "ТЦ «Северный» — реновация",
            "Адрес": "ул. Дыбенко, 26",
            "Город": "Санкт-Петербург",
            "Координаты": "59.9070, 30.4760",
            "Текущее назначение": "Устаревший ТЦ",
            "Целевое назначение": "Райцентр с фуд-холлом",
            "Площадь участка (сот)": 80,
            "Площадь здания (м²)": 14200,
            "Аренд. площадь (м²)": 11800,
            "Стадия": "Проектирование",
            "Статус": "Активен",
            "Готовность %": 20,
            "Дата старта": "2025-09-15",
            "План ввода": "2027-06-01",
            "Бюджет CAPEX $": 12_500_000,
            "Вложено $": 1_600_000,
            "Ответственный": "М. Петрова",
            "Комментарий": "Согласуем концепцию с якорным арендатором.",
        },
        {
            "Проект": "Технопарк «Заречье»",
            "Адрес": "Заречная ул., 14",
            "Город": "Казань",
            "Координаты": "55.7960, 49.1060",
            "Текущее назначение": "Цех бывшего завода",
            "Целевое назначение": "Light-industrial + офисы",
            "Площадь участка (сот)": 120,
            "Площадь здания (м²)": 9300,
            "Аренд. площадь (м²)": 8200,
            "Стадия": "Согласования",
            "Статус": "На паузе",
            "Готовность %": 12,
            "Дата старта": "2025-11-01",
            "План ввода": "2027-09-01",
            "Бюджет CAPEX $": 5_400_000,
            "Вложено $": 700_000,
            "Ответственный": "Р. Сафин",
            "Комментарий": "Ждём изменение ВРИ участка.",
        },
    ]
    return _coerce(pd.DataFrame(rows))
