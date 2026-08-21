"""Локальное хранилище капитала/сделок/недвижимости/баланса — замена Google Таблицы.

Один файл SQLite в ~/.trashman_family_office/ (тот же каталог, что и остальные
*_store.py). load_*() функции возвращают те же структуры (DataFrame/dict), что
раньше отдавал data_source.py, — views/*.py их не отличают.

Данные всегда читаются "вживую" (без кэша уровня Streamlit): для личного объёма
данных (десятки-сотни строк) это быстрее, чем управлять инвалидацией кэша после
каждой записи из форм ввода."""
import sqlite3
from contextlib import contextmanager

import pandas as pd

from local_store import APP_DATA_DIR

DB_PATH = APP_DATA_DIR / "family_office.db"

PROGRESS_METRICS = ["capital_usd", "capital_rub", "active_income", "passive_income", "debt"]

BALANCE_GROUPS = [
    "bank", "cash", "crypto", "returns", "loans",
    "real_estate", "frozen", "art", "business", "obligations",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS capital_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric TEXT NOT NULL,
    date TEXT NOT NULL,
    value REAL NOT NULL,
    UNIQUE(metric, date)
);

CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    deal_type TEXT,
    amount REAL,
    object_label TEXT,
    purpose TEXT,
    counterparty TEXT,
    asset_type TEXT,
    net_profit REAL
);

CREATE TABLE IF NOT EXISTS real_estate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL DEFAULT 'active',
    type TEXT,
    object_label TEXT,
    location TEXT,
    exact_address TEXT,
    object_status TEXT,
    coords TEXT,
    area TEXT,
    purchase_usd REAL,
    market_usd REAL,
    liabilities_usd REAL,
    sale_price_usd REAL,
    profit_usd REAL
);

CREATE TABLE IF NOT EXISTS balance_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    label TEXT,
    eur_rate REAL,
    rub_rate REAL
);

CREATE TABLE IF NOT EXISTS balance_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES balance_snapshots(id) ON DELETE CASCADE,
    grp TEXT NOT NULL,
    name TEXT NOT NULL,
    orig REAL,
    usd REAL,
    currency TEXT
);

CREATE TABLE IF NOT EXISTS asset_allocation_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES balance_snapshots(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    amount REAL,
    share REAL
);
"""


@contextmanager
def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


# =============================== Прогресс капитала ===============================

def load_progress() -> dict:
    with _conn() as conn:
        rows = conn.execute("SELECT metric, date, value FROM capital_points ORDER BY date").fetchall()
    by_metric = {m: {"date": [], "value": []} for m in PROGRESS_METRICS}
    for r in rows:
        if r["metric"] in by_metric:
            by_metric[r["metric"]]["date"].append(r["date"])
            by_metric[r["metric"]]["value"].append(r["value"])
    return {
        m: pd.DataFrame({"date": pd.to_datetime(d["date"]), "value": d["value"]})
        for m, d in by_metric.items()
    }


def add_capital_point(date_str, values: dict):
    """values: {metric: value, ...} — только заполненные метрики записываются."""
    with _conn() as conn:
        for metric, value in values.items():
            if metric not in PROGRESS_METRICS or value is None:
                continue
            conn.execute(
                "INSERT INTO capital_points (metric, date, value) VALUES (?, ?, ?) "
                "ON CONFLICT(metric, date) DO UPDATE SET value = excluded.value",
                (metric, date_str, value),
            )


def delete_capital_point_date(date_str):
    with _conn() as conn:
        conn.execute("DELETE FROM capital_points WHERE date = ?", (date_str,))


def list_capital_points() -> pd.DataFrame:
    with _conn() as conn:
        rows = conn.execute("SELECT DISTINCT date FROM capital_points ORDER BY date DESC").fetchall()
    return pd.DataFrame({"Дата": [r["date"] for r in rows]})


# =============================== Сделки ===============================

DEALS_COLUMNS = {
    "date": "Дата", "deal_type": "Тип сделки", "amount": "Сумма",
    "object_label": "Объект", "purpose": "Назначение", "counterparty": "Контрагент",
    "asset_type": "Вид актива", "net_profit": "Чистая прибыль по сделке",
}


def load_deals() -> pd.DataFrame:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, date, deal_type, amount, object_label, purpose, counterparty, "
            "asset_type, net_profit FROM deals ORDER BY date DESC"
        ).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        return pd.DataFrame(columns=["id"] + list(DEALS_COLUMNS.values()))
    df["date"] = pd.to_datetime(df["date"])
    return df.rename(columns=DEALS_COLUMNS)


def add_deal(date_str, deal_type, amount, object_label=None, purpose=None,
             counterparty=None, asset_type=None, net_profit=None):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO deals (date, deal_type, amount, object_label, purpose, "
            "counterparty, asset_type, net_profit) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (date_str, deal_type, amount, object_label, purpose, counterparty, asset_type, net_profit),
        )


def delete_deal(deal_id):
    with _conn() as conn:
        conn.execute("DELETE FROM deals WHERE id = ?", (deal_id,))


# =============================== Недвижимость ===============================

REAL_ESTATE_COLUMNS = {
    "type": "Тип", "object_label": "Объект", "location": "Локация",
    "exact_address": "Точный адрес", "object_status": "Статус", "coords": "Координаты",
    "area": "Площадь", "purchase_usd": "Сумма покупки в $",
    "market_usd": "Примерная рыночная стоимость в $", "liabilities_usd": "Обязательства",
}
SOLD_EXTRA_COLUMNS = {"sale_price_usd": "Цена продажи", "profit_usd": "Прибыль"}


def _load_real_estate(status: str, extra_columns=None) -> pd.DataFrame:
    cols = ["id"] + list(REAL_ESTATE_COLUMNS) + list((extra_columns or {}))
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(cols)} FROM real_estate WHERE status = ? ORDER BY id", (status,)
        ).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    all_columns = {**REAL_ESTATE_COLUMNS, **(extra_columns or {})}
    if df.empty:
        return pd.DataFrame(columns=["id"] + list(all_columns.values()))
    return df.rename(columns=all_columns)


def load_real_estate() -> pd.DataFrame:
    return _load_real_estate("active")


def load_real_estate_sold() -> pd.DataFrame:
    return _load_real_estate("sold", SOLD_EXTRA_COLUMNS)


def add_real_estate(**fields):
    """fields — любой поднабор ключей REAL_ESTATE_COLUMNS/SOLD_EXTRA_COLUMNS + status."""
    fields.setdefault("status", "active")
    known = set(REAL_ESTATE_COLUMNS) | set(SOLD_EXTRA_COLUMNS) | {"status"}
    fields = {k: v for k, v in fields.items() if k in known}
    with _conn() as conn:
        placeholders = ", ".join("?" for _ in fields)
        conn.execute(
            f"INSERT INTO real_estate ({', '.join(fields)}) VALUES ({placeholders})",
            list(fields.values()),
        )


def update_real_estate(object_id, **fields):
    known = set(REAL_ESTATE_COLUMNS) | set(SOLD_EXTRA_COLUMNS) | {"status"}
    fields = {k: v for k, v in fields.items() if k in known}
    if not fields:
        return
    with _conn() as conn:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE real_estate SET {set_clause} WHERE id = ?", [*fields.values(), object_id])


def delete_real_estate(object_id):
    with _conn() as conn:
        conn.execute("DELETE FROM real_estate WHERE id = ?", (object_id,))


def list_real_estate_all() -> pd.DataFrame:
    """Активные и проданные вместе, для страницы редактирования."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, status, type, object_label, location FROM real_estate ORDER BY id"
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


# =============================== Баланс ===============================

def _latest_snapshot(conn):
    return conn.execute(
        "SELECT * FROM balance_snapshots ORDER BY date DESC LIMIT 1"
    ).fetchone()


def load_balance():
    with _conn() as conn:
        snap = _latest_snapshot(conn)
        if snap is None:
            return None
        items = conn.execute(
            "SELECT grp, name, orig, usd, currency FROM balance_items WHERE snapshot_id = ?",
            (snap["id"],),
        ).fetchall()

    by_group = {g: [] for g in BALANCE_GROUPS}
    for it in items:
        by_group.setdefault(it["grp"], []).append(
            {"name": it["name"], "orig": it["orig"], "usd": it["usd"] or 0.0, "currency": it["currency"] or ""}
        )

    def subtotal(group):
        return sum((it["usd"] or 0) for it in by_group.get(group, []))

    obligations_total = subtotal("obligations")
    # Долги в исходной таблице вносились как отрицательные числа (как и в
    # каждом отдельном обязательстве выше) — поэтому просто складываем все
    # группы, кроме "заморожено" (оно вне баланса), с их исходными знаками,
    # а не вычитаем obligations_total отдельно (это удваивало бы долг).
    grand_total = sum(subtotal(g) for g in BALANCE_GROUPS if g != "frozen")

    return {
        "sheet_name": snap["label"] or snap["date"],
        "bank": by_group["bank"],
        "cash": by_group["cash"],
        "crypto": by_group["crypto"],
        "returns": by_group["returns"],
        "loans": by_group["loans"],
        "real_estate": by_group["real_estate"],
        "frozen": by_group["frozen"],
        "art": by_group["art"],
        "business": by_group["business"],
        "obligations": by_group["obligations"],
        "obligations_total": obligations_total,
        "grand_total": grand_total,
        "rates": {"eur": snap["eur_rate"] or 1.142, "rub": snap["rub_rate"] or 0.0117},
    }


def load_asset_allocation() -> pd.DataFrame:
    with _conn() as conn:
        snap = _latest_snapshot(conn)
        if snap is None:
            return pd.DataFrame(columns=["Категория", "Сумма", "Доля"])
        rows = conn.execute(
            "SELECT category, amount, share FROM asset_allocation_items WHERE snapshot_id = ?",
            (snap["id"],),
        ).fetchall()
    return pd.DataFrame(
        {
            "Категория": [r["category"] for r in rows],
            "Сумма": [r["amount"] for r in rows],
            "Доля": [r["share"] for r in rows],
        }
    )


def add_balance_snapshot(date_str, label, eur_rate, rub_rate, items: list, allocation: list = None):
    """items: список {"group": ..., "name": ..., "orig": ..., "usd": ..., "currency": ...}.
    allocation: список {"category": ..., "amount": ..., "share": ...} (необязательно).
    Если срез на эту дату уже есть — перезаписывается целиком (upsert)."""
    with _conn() as conn:
        conn.execute(
            "INSERT INTO balance_snapshots (date, label, eur_rate, rub_rate) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(date) DO UPDATE SET label = excluded.label, "
            "eur_rate = excluded.eur_rate, rub_rate = excluded.rub_rate",
            (date_str, label, eur_rate, rub_rate),
        )
        snap_id = conn.execute("SELECT id FROM balance_snapshots WHERE date = ?", (date_str,)).fetchone()["id"]
        conn.execute("DELETE FROM balance_items WHERE snapshot_id = ?", (snap_id,))
        conn.execute("DELETE FROM asset_allocation_items WHERE snapshot_id = ?", (snap_id,))
        for it in items:
            if not it.get("name"):
                continue
            conn.execute(
                "INSERT INTO balance_items (snapshot_id, grp, name, orig, usd, currency) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (snap_id, it["group"], it["name"], it.get("orig"), it.get("usd"), it.get("currency", "")),
            )
        for a in (allocation or []):
            if not a.get("category"):
                continue
            conn.execute(
                "INSERT INTO asset_allocation_items (snapshot_id, category, amount, share) VALUES (?, ?, ?, ?)",
                (snap_id, a["category"], a.get("amount"), a.get("share")),
            )
    return snap_id


def list_balance_snapshots() -> pd.DataFrame:
    with _conn() as conn:
        rows = conn.execute("SELECT id, date, label FROM balance_snapshots ORDER BY date DESC").fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def delete_balance_snapshot(snapshot_id):
    with _conn() as conn:
        conn.execute("DELETE FROM balance_snapshots WHERE id = ?", (snapshot_id,))


def load_balance_snapshot_full(snapshot_id):
    """Полный срез для редактирования (та же форма-структура, что и load_balance(),
    но по конкретному id, а не только по последнему)."""
    with _conn() as conn:
        snap = conn.execute("SELECT * FROM balance_snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        if snap is None:
            return None
        items = conn.execute(
            "SELECT grp, name, orig, usd, currency FROM balance_items WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchall()
        allocation = conn.execute(
            "SELECT category, amount, share FROM asset_allocation_items WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchall()
    return {
        "date": snap["date"],
        "label": snap["label"],
        "eur_rate": snap["eur_rate"],
        "rub_rate": snap["rub_rate"],
        "items": [dict(it) for it in items],
        "allocation": [dict(a) for a in allocation],
    }
