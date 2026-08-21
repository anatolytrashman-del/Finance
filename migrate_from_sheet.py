"""Разовый перенос истории из Google Таблицы в локальную базу (db.py).

Запускать ОДИН РАЗ, локально — там, где таблица ещё доступна по ссылке
(на сервере в облаке Google обычно недоступен). После переноса приложение
больше не обращается к Google вообще.

    python3 migrate_from_sheet.py

Итоговый файл — ~/.trashman_family_office/family_office.db. Дальше его нужно
залить на сервер (см. README «Деплой» — команда fly sftp shell / volume).

Скрипт идемпотентен для баланса (upsert по дате среза) и для точек капитала
(upsert по дате+метрике), но сделки и объекты недвижимости просто
добавляются — повторный запуск на той же базе даст дубли. Если нужно
перезапустить с нуля, удали family_office.db перед повторным запуском.
"""
import sys
from io import BytesIO

import pandas as pd
from openpyxl import load_workbook

import db
import parsers
from data_source import _fetch_bytes


def main():
    print("Скачиваю Google Таблицу...")
    try:
        raw = _fetch_bytes()
    except Exception as exc:  # noqa: BLE001
        print(f"Не удалось скачать таблицу: {exc}", file=sys.stderr)
        print("Проверь доступ («Все, у кого есть ссылка» -> Читатель) и GOOGLE_SHEET_ID в config.py.")
        sys.exit(1)

    wb = load_workbook(BytesIO(raw), data_only=True)

    # --- Прогресс капитала ---
    progress = parsers.parse_progress(wb)
    points = 0
    for metric, series in progress.items():
        for _, row in series.iterrows():
            date_str = row["date"].strftime("%Y-%m-%d")
            db.add_capital_point(date_str, {metric: row["value"]})
            points += 1
    print(f"Прогресс капитала: {points} точек")

    # --- Сделки ---
    deals_df = parsers.parse_deals(wb)
    deals_n = 0
    for _, row in deals_df.iterrows():
        date_val = row.get("Дата")
        if date_val is None or pd.isna(date_val):
            continue
        date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val)
        db.add_deal(
            date_str=date_str,
            deal_type=row.get("Тип сделки"),
            amount=row.get("Сумма"),
            object_label=row.get("Объект"),
            purpose=row.get("Назначение"),
            counterparty=row.get("Контрагент"),
            asset_type=row.get("Вид актива"),
            net_profit=row.get("Чистая прибыль по сделке"),
        )
        deals_n += 1
    print(f"Сделки: {deals_n}")

    # --- Недвижимость (активные + проданные) ---
    def _import_real_estate(re_df, status, extra_cols=None):
        n = 0
        for _, row in re_df.iterrows():
            fields = {
                "status": status,
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
            db.add_real_estate(**fields)
            n += 1
        return n

    active_n = _import_real_estate(parsers.parse_real_estate(wb), "active")
    sold_n = _import_real_estate(parsers.parse_real_estate_sold(wb), "sold", extra_cols=True)
    print(f"Недвижимость: {active_n} активных, {sold_n} проданных")

    # --- Баланс: ВСЕ помесячные срезы (не только последний — на будущее) ---
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
    print(f"Помесячные срезы баланса: {snap_n}")

    print(f"\nГотово. База: {db.DB_PATH}")


if __name__ == "__main__":
    main()
