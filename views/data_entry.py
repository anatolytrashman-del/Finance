"""Ввод и редактирование данных — замена ручного заполнения Google Таблицы.

Одна страница на всё: прогресс капитала, сделки, недвижимость, помесячный
срез баланса. Технически проще, чем растаскивать формы по каждому
аналитическому view — те остаются чистыми "только для чтения"."""
from datetime import date

import pandas as pd
import streamlit as st

import db
from rates_widget import render_sidebar_rates
from theme import page, section_title

render_sidebar_rates()

_MONTHS_RU_GENITIVE = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def _fmt_date_ru(d):
    return f"{d.day} {_MONTHS_RU_GENITIVE[d.month - 1]} {d.year}"

GROUP_LABELS = {
    "bank": "Банковские счета", "cash": "Наличные", "crypto": "Крипта",
    "returns": "Возвраты", "loans": "Займы", "real_estate": "Недвижимость (в балансе)",
    "frozen": "Заблокировано (вне баланса)", "art": "Искусство",
    "business": "Бизнес", "obligations": "Обязательства",
}
ITEM_COLUMNS = ["name", "orig", "usd", "currency"]
ITEM_COLUMN_LABELS = {"name": "Название", "orig": "В валюте", "usd": "В $", "currency": "Валюта"}


def _items_df(items):
    df = pd.DataFrame(items or [], columns=ITEM_COLUMNS)
    return df.rename(columns=ITEM_COLUMN_LABELS)


def _df_to_items(df, group):
    out = []
    for _, row in df.iterrows():
        name = str(row.get("Название") or "").strip()
        if not name:
            continue
        out.append({
            "group": group, "name": name,
            "orig": row.get("В валюте") if pd.notna(row.get("В валюте")) else None,
            "usd": row.get("В $") if pd.notna(row.get("В $")) else None,
            "currency": str(row.get("Валюта") or "").strip(),
        })
    return out


with page("data_entry", "✍️", "Ввод данных", "Здесь заполняются все цифры — остальные страницы только показывают"):
    tab_progress, tab_deals, tab_re, tab_balance = st.tabs(
        ["📊 Прогресс капитала", "📈 Сделки", "🏠 Недвижимость", "⚖️ Срез баланса"]
    )

    # ============================ Прогресс капитала ============================
    with tab_progress:
        section_title("Добавить/обновить точку")
        st.caption("Оставь поле пустым, если для этой даты метрику вносить не нужно.")
        with st.form("progress_form", clear_on_submit=True):
            p_date = st.date_input("Дата", value=date.today())
            c1, c2, c3 = st.columns(3)
            capital_usd = c1.number_input("Капитал, $", value=None, step=100.0)
            capital_rub = c2.number_input("Капитал, ₽", value=None, step=1000.0)
            debt = c3.number_input("Долговая нагрузка, $", value=None, step=100.0)
            c4, c5 = st.columns(2)
            active_income = c4.number_input("Активный доход, $", value=None, step=50.0)
            passive_income = c5.number_input("Пассивный доход, $", value=None, step=50.0)
            if st.form_submit_button("Сохранить", type="primary"):
                db.add_capital_point(p_date.isoformat(), {
                    "capital_usd": capital_usd, "capital_rub": capital_rub, "debt": debt,
                    "active_income": active_income, "passive_income": passive_income,
                })
                st.success(f"Точка на {p_date.isoformat()} сохранена.")
                st.rerun()

        section_title("Существующие даты")
        points = db.list_capital_points()
        if points.empty:
            st.caption("Пока пусто.")
        else:
            del_date = st.selectbox("Удалить точку за дату", points["Дата"], key="del_progress_date")
            if st.button("🗑️ Удалить", key="del_progress_btn"):
                db.delete_capital_point_date(del_date)
                st.rerun()
            st.dataframe(points, width="stretch", hide_index=True)

    # ============================ Сделки ============================
    with tab_deals:
        section_title("Добавить сделку")
        with st.form("deal_form", clear_on_submit=True):
            d_date = st.date_input("Дата", value=date.today(), key="deal_date")
            deal_type = st.text_input("Тип сделки", placeholder="Покупка / Продажа / Дивиденды / ...")
            amount = st.number_input("Сумма, $", value=0.0, step=50.0)
            c1, c2 = st.columns(2)
            object_label = c1.text_input("Объект")
            asset_type = c2.text_input("Вид актива")
            c3, c4 = st.columns(2)
            purpose = c3.text_input("Назначение")
            counterparty = c4.text_input("Контрагент")
            net_profit = st.number_input("Чистая прибыль по сделке, $ (если применимо)", value=None, step=50.0)
            if st.form_submit_button("Сохранить", type="primary"):
                db.add_deal(
                    date_str=d_date.isoformat(), deal_type=deal_type or None, amount=amount,
                    object_label=object_label or None, purpose=purpose or None,
                    counterparty=counterparty or None, asset_type=asset_type or None,
                    net_profit=net_profit,
                )
                st.success("Сделка сохранена.")
                st.rerun()

        section_title("Последние сделки")
        deals = db.load_deals()
        if deals.empty:
            st.caption("Пока пусто.")
        else:
            recent = deals.sort_values("Дата", ascending=False).head(30)
            del_id = st.selectbox(
                "Удалить сделку", recent["id"],
                format_func=lambda i: f"{recent.loc[recent['id'] == i, 'Дата'].iloc[0].strftime('%d.%m.%Y')} — "
                                       f"{recent.loc[recent['id'] == i, 'Тип сделки'].iloc[0]} — "
                                       f"${recent.loc[recent['id'] == i, 'Сумма'].iloc[0]:,.0f}",
                key="del_deal_id",
            )
            if st.button("🗑️ Удалить", key="del_deal_btn"):
                db.delete_deal(del_id)
                st.rerun()
            st.dataframe(recent.drop(columns=["id"]), width="stretch", hide_index=True)

    # ============================ Недвижимость ============================
    with tab_re:
        section_title("Добавить объект")
        with st.form("re_form", clear_on_submit=True):
            re_type = st.text_input("Тип", placeholder="Квартира / Апартаменты / Земля / ...")
            c1, c2 = st.columns(2)
            location = c1.text_input("Локация")
            exact_address = c2.text_input("Точный адрес")
            c3, c4 = st.columns(2)
            object_status = c3.text_input("Статус", placeholder="В стройке / Сдан / В аренде / ...")
            coords = c4.text_input("Координаты", placeholder="53.9, 27.5667")
            c5, c6 = st.columns(2)
            area = c5.text_input("Площадь", placeholder="45 м² или 5.6 Га")
            object_label = c6.text_input("Ярлык объекта (для связки со «Сделками»)")
            c7, c8, c9 = st.columns(3)
            purchase_usd = c7.number_input("Сумма покупки, $", value=0.0, step=500.0)
            market_usd = c8.number_input("Рыночная стоимость, $", value=None, step=500.0)
            liabilities_usd = c9.number_input("Обязательства, $", value=None, step=500.0)
            if st.form_submit_button("Сохранить", type="primary"):
                db.add_real_estate(
                    type=re_type or None, location=location or None, exact_address=exact_address or None,
                    object_status=object_status or None, coords=coords or None, area=area or None,
                    object_label=object_label or None, purchase_usd=purchase_usd,
                    market_usd=market_usd, liabilities_usd=liabilities_usd,
                )
                st.success("Объект сохранён.")
                st.rerun()

        section_title("Управление объектами")
        all_re = db.list_real_estate_all()
        if all_re.empty:
            st.caption("Пока пусто.")
        else:
            all_re["label"] = all_re.apply(
                lambda r: f"[{'продан' if r['status'] == 'sold' else 'активен'}] "
                          f"{r['type'] or '—'} — {r['location'] or '—'}",
                axis=1,
            )
            sel_id = st.selectbox(
                "Объект", all_re["id"],
                format_func=lambda i: all_re.loc[all_re["id"] == i, "label"].iloc[0],
                key="re_manage_id",
            )
            action = st.radio("Действие", ["Пометить проданным", "Удалить"], horizontal=True, key="re_action")
            if action == "Пометить проданным":
                sale_price = st.number_input("Цена продажи, $", value=0.0, step=500.0, key="re_sale_price")
                profit = st.number_input("Прибыль, $", value=0.0, step=500.0, key="re_sale_profit")
                if st.button("Сохранить как проданный", key="re_mark_sold"):
                    db.update_real_estate(sel_id, status="sold", sale_price_usd=sale_price, profit_usd=profit)
                    st.rerun()
            else:
                if st.button("🗑️ Удалить объект", key="re_delete_btn"):
                    db.delete_real_estate(sel_id)
                    st.rerun()
            st.dataframe(all_re.drop(columns=["label"]), width="stretch", hide_index=True)

    # ============================ Срез баланса ============================
    with tab_balance:
        section_title("Помесячный срез")
        st.caption(
            "Каждая группа — редактируемая таблица: добавляй/убирай строки прямо в ней. "
            "По умолчанию подставлен последний сохранённый срез — поменяй цифры и сохрани под новой датой."
        )

        snapshots = db.list_balance_snapshots()
        snap_options = ["🆕 Новый срез (на основе последнего)"] + [
            f"{row['date']} — {row['label'] or ''}" for _, row in snapshots.iterrows()
        ]
        chosen = st.selectbox("Срез", snap_options, key="balance_snap_choice")

        if chosen == snap_options[0]:
            prefill = db.load_balance()
            prefill_items = {g: (prefill or {}).get(g, []) for g in db.BALANCE_GROUPS}
            prefill_alloc = []
            alloc_df = db.load_asset_allocation()
            if not alloc_df.empty:
                prefill_alloc = alloc_df.rename(
                    columns={"Категория": "category", "Сумма": "amount", "Доля": "share"}
                ).to_dict("records")
            default_date = date.today()
            default_label = _fmt_date_ru(default_date)
            default_eur = (prefill or {}).get("rates", {}).get("eur", 1.142)
            default_rub = (prefill or {}).get("rates", {}).get("rub", 0.0117)
        else:
            snap_id = int(snapshots.iloc[snap_options.index(chosen) - 1]["id"])
            full = db.load_balance_snapshot_full(snap_id)
            prefill_items = {g: [] for g in db.BALANCE_GROUPS}
            for it in full["items"]:
                prefill_items.setdefault(it["grp"], []).append(it)
            prefill_alloc = full["allocation"]
            default_date = pd.to_datetime(full["date"]).date()
            default_label = full["label"] or ""
            default_eur = full["eur_rate"] or 1.142
            default_rub = full["rub_rate"] or 0.0117

        with st.form("balance_form"):
            c1, c2 = st.columns(2)
            snap_date = c1.date_input("Дата среза", value=default_date, key="balance_date")
            snap_label = c2.text_input("Название среза", value=default_label, key="balance_label")
            c3, c4 = st.columns(2)
            eur_rate = c3.number_input("Курс EUR/USD", value=float(default_eur), format="%.4f", key="balance_eur")
            rub_rate = c4.number_input("Курс RUB/USD", value=float(default_rub), format="%.5f", key="balance_rub")

            editors = {}
            for group in db.BALANCE_GROUPS:
                st.markdown(f"**{GROUP_LABELS[group]}**")
                editors[group] = st.data_editor(
                    _items_df(prefill_items.get(group, [])),
                    num_rows="dynamic", width="stretch", hide_index=True, key=f"balance_editor_{group}",
                )

            st.markdown("**Распределение по классам активов**")
            alloc_editor = st.data_editor(
                pd.DataFrame(
                    [{"Категория": a["category"], "Сумма": a["amount"], "Доля, %": a["share"]} for a in prefill_alloc],
                    columns=["Категория", "Сумма", "Доля, %"],
                ),
                num_rows="dynamic", width="stretch", hide_index=True, key="balance_alloc_editor",
            )

            if st.form_submit_button("Сохранить срез", type="primary"):
                items = []
                for group, edf in editors.items():
                    items.extend(_df_to_items(edf, group))
                allocation = [
                    {"category": str(r["Категория"]).strip(), "amount": r["Сумма"], "share": r["Доля, %"]}
                    for _, r in alloc_editor.iterrows() if str(r.get("Категория") or "").strip()
                ]
                db.add_balance_snapshot(
                    date_str=snap_date.isoformat(), label=snap_label or snap_date.isoformat(),
                    eur_rate=eur_rate, rub_rate=rub_rate, items=items, allocation=allocation,
                )
                st.success(f"Срез на {snap_date.isoformat()} сохранён.")
                st.rerun()

        if not snapshots.empty:
            section_title("Существующие срезы")
            del_snap = st.selectbox(
                "Удалить срез", snapshots["id"],
                format_func=lambda i: f"{snapshots.loc[snapshots['id'] == i, 'date'].iloc[0]} — "
                                       f"{snapshots.loc[snapshots['id'] == i, 'label'].iloc[0] or ''}",
                key="del_snap_id",
            )
            if st.button("🗑️ Удалить срез", key="del_snap_btn"):
                db.delete_balance_snapshot(del_snap)
                st.rerun()
