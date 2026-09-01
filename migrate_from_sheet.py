"""Синхронизация локальной базы (db.py) с Google Таблицей.

Можно гонять сколько угодно раз — безопасно для повторного запуска:
  - прогресс капитала и помесячные срезы баланса — upsert по дате;
  - сделки и объекты недвижимости, ранее пришедшие из таблицы, полностью
    заменяются свежим набором (db.replace_sheet_*) — так повторный запуск
    не плодит дубли. Сделки/объекты, добавленные прямо в приложении (не из
    таблицы), эта замена не трогает.

Как отдельный скрипт (например, чтобы разово перенести историю на новую
машину, где ещё нет БД, — сервер в облаке обычно не видит Google):

    python3 migrate_from_sheet.py

Внутри приложения та же логика доступна кнопкой «Обновить данные» в
боковой панели (см. app.py) — вызывает sync_from_sheet() напрямую."""
import sys
from io import BytesIO

import pandas as pd
from openpyxl import load_workbook

import db
import parsers
from data_source import _fetch_bytes


def sync_from_sheet() -> dict:
    """Скачивает Google Таблицу и синхронизирует с ней локальную базу.
    Возвращает сводку {"points": N, "deals": N, "active": N, "sold": N, "snapshots": N}.
    Бросает исключение, если таблицу не удалось скачать/разобрать."""
    raw = _fetch_bytes()
    wb = load_workbook(BytesIO(raw), data_only=True)

    # --- Прогресс капитала (upsert по дате+метрике) ---
    progress = parsers.parse_progress(wb)
    points = 0
    for metric, series in progress.items():
        for _, row in series.iterrows():
            date_str = row["date"].strftime("%Y-%m-%d")
            db.add_capital_point(date_str, {metric: row["value"]})
            points += 1

    # --- Сделки (полная замена ранее синхронизированных из таблицы) ---
    deals_df = parsers.parse_deals(wb)
    deal_rows = []
    for _, row in deals_df.iterrows():
        date_val = row.get("Дата")
        if date_val is None or pd.isna(date_val):
            continue
        date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val)
        deal_rows.append({
            "date_str": date_str,
            "deal_type": row.get("Тип сделки"),
            "amount": row.get("Сумма"),
            "object_label": row.get("Объект"),
            "purpose": row.get("Назначение"),
            "counterparty": row.get("Контрагент"),
            "asset_type": row.get("Вид актива"),
            "net_profit": row.get("Чистая прибыль по сделке"),
        })
    db.replace_sheet_deals(deal_rows)

    # --- Недвижимость (полная замена ранее синхронизированной из таблицы) ---
    def _rows_from_df(re_df, extra_cols=False):
        rows = []
        for _, row in re_df.iterrows():
            fields = {
                "type": row.get("Тип"),
                "object_label": row.get("Объект"),
                "location": row.get("Локация"),
                "exact_address": row.get("Точный адрес"),
                "object_status": row.get("Статус"),
                "coords": row.get("Координаты"),
                "area": row.get("Площадь"),
                "purchase_usd": parsers.parse_money(row.get("Сумма покупки в $")),
                "market_usd": parsers.parse_money(row.get("Примерная рыночная стоимость в $")),
                "liabilities_usd": parsers.parse_money(row.get("Обязательства")),
            }
            if extra_cols:
                fields["sale_price_usd"] = parsers.parse_money(row.get("Цена продажи"))
                fields["profit_usd"] = parsers.parse_money(row.get("Прибыль"))
            fields = {k: v for k, v in fields.items() if v is not None and v == v}  # drop NaN/None
            rows.append(fields)
        return rows

    active_rows = _rows_from_df(parsers.parse_real_estate(wb))
    sold_rows = _rows_from_df(parsers.parse_real_estate_sold(wb), extra_cols=True)
    db.replace_sheet_real_estate(active_rows, sold_rows)

    # --- Баланс: ВСЕ помесячные срезы (не только последний — на будущее), upsert по дате ---
    snapshot_sheets = parsers.find_all_snapshot_sheets(wb)
    snap_n = 0
    for ws in snapshot_sheets:
        balance = parsers.parse_balance(wb, ws=ws)
        if balance is None:
            continue
        allocation_df = parsers.parse_asset_allocation(wb, ws=ws)
        items = []
        for group in db.BALANCE_GROUPS:
            for it in balance.get(group, []):
                items.append({"group": group, **it})
        allocation = [
            {"category": r["Категория"], "amount": r["Сумма"], "share": r["Доля"]}
            for _, r in allocation_df.iterrows()
        ]
        snap_key = parsers.sheet_sort_key(ws.title)
        date_str = f"{snap_key[0]:04d}-{snap_key[1]:02d}-{snap_key[2]:02d}"
        db.add_balance_snapshot(
            date_str=date_str,
            label=ws.title.strip(),
            eur_rate=balance["rates"]["eur"],
            rub_rate=balance["rates"]["rub"],
            items=items,
            allocation=allocation,
        )
        snap_n += 1

    removed = db.dedupe_migrated_duplicates()

    return {
        "points": points,
        "deals": len(deal_rows),
        "active": len(active_rows),
        "sold": len(sold_rows),
        "snapshots": snap_n,
        "removed_duplicates": removed["real_estate"] + removed["deals"],
    }


def main():
    print("Скачиваю Google Таблицу...")
    try:
        summary = sync_from_sheet()
    except Exception as exc:  # noqa: BLE001
        print(f"Не удалось синхронизировать: {exc}", file=sys.stderr)
        print("Проверь доступ («Все, у кого есть ссылка» -> Читатель) и GOOGLE_SHEET_ID в config.py.")
        sys.exit(1)

    print(f"Прогресс капитала: {summary['points']} точек")
    print(f"Сделки: {summary['deals']}")
    print(f"Недвижимость: {summary['active']} активных, {summary['sold']} проданных")
    print(f"Помесячные срезы баланса: {summary['snapshots']}")
    print(f"\nГотово. База: {db.DB_PATH}")


if __name__ == "__main__":
    main()
