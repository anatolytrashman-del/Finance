import uuid
from datetime import date

import pandas as pd
import streamlit as st

import config
from db import load_deals, load_real_estate
from buyrent_finmodel import compute_buyrent
from finmodel_store import (
    load_buyrent_finmodels,
    load_finmodels,
    load_sale_finmodels,
    save_buyrent_finmodels,
    save_finmodels,
    save_sale_finmodels,
)
from rates_widget import render_sidebar_rates
from sale_finmodel import (
    SALE_TAX_BASES,
    compute_sale,
    object_choices,
    pull_payments,
)
from theme import card, kpi_card, kpi_row, page, section_title

render_sidebar_rates()

TAX_MODES = ["% от аренды", "Фикс. сумма в месяц"]
CURRENCIES = ["$", "₽"]

with page("finmodel", "🧮", "Финмодель", "Аренда, продажа и покупка+аренда — расчёт доходности"):
    section_title("🏠 Аренда")

    if "finmodels" not in st.session_state:
        st.session_state["finmodels"] = load_finmodels()

    models = st.session_state["finmodels"]


    def _currency_select(d, key=None):
        return st.selectbox(
            "Валюта проекта", CURRENCIES,
            index=CURRENCIES.index(d.get("currency")) if d.get("currency") in CURRENCIES else 0,
            key=key,
        )


    def _fmt_money(v, currency="$"):
        if currency == "$":
            return f"${v:,.0f}".replace(",", " ")
        return f"{v:,.0f} {currency}".replace(",", " ")


    def compute(m):
        purchase = m.get("purchase", 0) or 0
        reno = m.get("reno", 0) or 0
        rent = m.get("rent", 0) or 0
        tax_mode = m.get("tax_mode", TAX_MODES[0])
        tax_value = m.get("tax_value", 0) or 0
        fees_year = m.get("fees_year", 0) or 0
        insurance_month = m.get("insurance_month", 0) or 0

        gross_year = rent * 12
        tax_year = gross_year * tax_value / 100 if tax_mode == TAX_MODES[0] else tax_value * 12
        insurance_year = insurance_month * 12
        expenses_year = tax_year + fees_year + insurance_year
        net_year = gross_year - expenses_year
        investment = purchase + reno

        yield_pct = net_year / investment * 100 if investment > 0 else None
        payback = investment / net_year if investment > 0 and net_year > 0 else None
        return {
            "gross_year": gross_year,
            "tax_year": tax_year,
            "expenses_year": expenses_year,
            "net_year": net_year,
            "net_month": net_year / 12,
            "investment": investment,
            "yield_pct": yield_pct,
            "payback": payback,
        }


    def _render_fields(d):
        currency = _currency_select(d)

        st.markdown("**Капитальные расходы**")
        c1, c2 = st.columns(2)
        purchase = c1.number_input("Цена покупки", min_value=0.0, value=float(d.get("purchase", 0)), step=1000.0)
        reno = c2.number_input("Цена ремонта", min_value=0.0, value=float(d.get("reno", 0)), step=1000.0)

        st.markdown("**Доход**")
        rent = st.number_input("Цена аренды в месяц", min_value=0.0, value=float(d.get("rent", 0)), step=100.0)

        st.markdown("**Регулярные расходы**")
        tax_mode = st.radio(
            "Налог на сдачу считать как",
            TAX_MODES,
            horizontal=True,
            index=TAX_MODES.index(d.get("tax_mode")) if d.get("tax_mode") in TAX_MODES else 0,
        )
        tax_value = st.number_input(
            "Значение налога (% от аренды или фикс. сумма в месяц — по выбору выше)",
            min_value=0.0,
            value=float(d.get("tax_value", 0)),
            step=10.0,
        )
        c3, c4 = st.columns(2)
        fees_year = c3.number_input("Фиксированные сборы в год", min_value=0.0, value=float(d.get("fees_year", 0)), step=100.0)
        insurance_month = c4.number_input("Страховка в месяц", min_value=0.0, value=float(d.get("insurance_month", 0)), step=10.0)

        return {
            "currency": currency,
            "purchase": purchase,
            "reno": reno,
            "rent": rent,
            "tax_mode": tax_mode,
            "tax_value": tax_value,
            "fees_year": fees_year,
            "insurance_month": insurance_month,
        }


    def _metrics_and_recap(m):
        currency = m.get("currency", "$")
        r = compute(m)
        if r["payback"] is not None:
            payback_str = f"{r['payback']:.1f} лет"
        elif r["net_year"] <= 0:
            payback_str = "не окупается"
        else:
            payback_str = "—"
        kpi_row([
            kpi_card("📈", "Чистая доходность", f"{r['yield_pct']:.1f}%" if r["yield_pct"] is not None else "—", icon_bg="#ecfdf5"),
            kpi_card("⏳", "Срок окупаемости", payback_str, icon_bg="#eff6ff"),
            kpi_card("💰", "Чистый доход / год", _fmt_money(r["net_year"], currency), icon_bg="#fff7ed"),
            kpi_card("💵", "Чистый доход / мес", _fmt_money(r["net_month"], currency), icon_bg="#f5f3ff"),
        ])

        if m.get("tax_mode") == TAX_MODES[0]:
            tax_str = f"{m.get('tax_value', 0):g}% от аренды"
        else:
            tax_str = f"{_fmt_money(m.get('tax_value', 0), currency)}/мес"
        recap = (
            f"Вложения: {_fmt_money(r['investment'], currency)} "
            f"(покупка {_fmt_money(m.get('purchase', 0), currency)} + ремонт {_fmt_money(m.get('reno', 0), currency)}) · "
            f"Аренда: {_fmt_money(m.get('rent', 0), currency)}/мес · "
            f"Грязный доход: {_fmt_money(r['gross_year'], currency)}/год · "
            f"Расходы: {_fmt_money(r['expenses_year'], currency)}/год "
            f"(налог {tax_str}, сборы {_fmt_money(m.get('fees_year', 0), currency)}/год, "
            f"страховка {_fmt_money(m.get('insurance_month', 0), currency)}/мес)"
        )
        # Экранируем $, иначе Streamlit трактует пары $...$ как формулу
        st.caption(recap.replace("$", r"\$"))


    # --- Форма добавления ---
    with st.expander("➕ Добавить проект", expanded=not models):
        with st.form("add_model", clear_on_submit=True):
            name = st.text_input("Название проекта")
            vals = _render_fields({})
            if st.form_submit_button("Добавить"):
                if name.strip():
                    st.session_state["finmodels"].append({"id": str(uuid.uuid4()), "name": name.strip(), **vals})
                    save_finmodels(st.session_state["finmodels"])
                    st.rerun()
                else:
                    st.warning("Укажи название проекта.")

    # --- Список проектов ---
    if not models:
        st.info("Пока нет проектов. Добавь первый через «➕ Добавить проект» выше.")
    else:
        st.caption(f"Проектов: {len(models)}")
        editing_id = st.session_state.get("fm_editing_id")

        for m in models:
            with card("finmodel", f"rent_{m['id']}"):
                if editing_id == m["id"]:
                    with st.form(f"edit_{m['id']}"):
                        e_name = st.text_input("Название проекта", value=m.get("name", ""))
                        e_vals = _render_fields(m)
                        b_save, b_cancel = st.columns(2)
                        if b_save.form_submit_button("💾 Сохранить"):
                            if e_name.strip():
                                m.update({"name": e_name.strip(), **e_vals})
                                save_finmodels(st.session_state["finmodels"])
                                st.session_state["fm_editing_id"] = None
                                st.rerun()
                            else:
                                st.warning("Укажи название проекта.")
                        if b_cancel.form_submit_button("Отмена"):
                            st.session_state["fm_editing_id"] = None
                            st.rerun()
                else:
                    head, edit_btn, del_btn = st.columns([8, 1, 1])
                    safe_name = str(m.get("name", "Проект")).replace("$", r"\$")
                    head.markdown(f"### {safe_name} ({m.get('currency', '$')})")
                    if edit_btn.button("✏️", key=f"fm_edit_{m['id']}", help="Редактировать проект"):
                        st.session_state["fm_editing_id"] = m["id"]
                        st.rerun()
                    if del_btn.button("🗑", key=f"fm_del_{m['id']}", help="Удалить проект"):
                        st.session_state["finmodels"] = [x for x in models if x["id"] != m["id"]]
                        save_finmodels(st.session_state["finmodels"])
                        st.rerun()
                    _metrics_and_recap(m)


    # =========================== ФИНМОДЕЛЬ ПРОДАЖИ ===========================
    st.divider()
    section_title("💰 Продажа")
    st.caption(
        "Доходность считается через XIRR — с учётом графика платежей (рассрочка), "
        "а не только итоговых сумм. Для своих объектов график можно подтянуть из «Сделок»."
    )

    if "sale_finmodels" not in st.session_state:
        st.session_state["sale_finmodels"] = load_sale_finmodels()

    sale_models = st.session_state["sale_finmodels"]


    def _fmt_profit(v, currency="$"):
        """Деньги со знаком: убыток показываем как -$5 000 / -5 000 ₽."""
        if v is None:
            return "—"
        sign = "-" if v < 0 else ""
        if currency == "$":
            return f"{sign}${abs(v):,.0f}".replace(",", " ")
        return f"{sign}{abs(v):,.0f} {currency}".replace(",", " ")


    def _payments_to_df(payments):
        rows = []
        for p in payments or []:
            try:
                d = pd.to_datetime(p.get("date")).date()
            except Exception:  # noqa: BLE001
                d = None
            rows.append({"Дата платежа": d, "Сумма": float(p.get("amount") or 0)})
        if not rows:
            rows = [{"Дата платежа": date.today().replace(day=1), "Сумма": 0.0}]
        return pd.DataFrame(rows)


    def _df_to_payments(df):
        payments = []
        for _, row in df.iterrows():
            d, amount = row.get("Дата платежа"), row.get("Сумма")
            if pd.isna(d) or pd.isna(amount) or float(amount) <= 0:
                continue
            payments.append({"date": pd.to_datetime(d).date().isoformat(), "amount": float(amount)})
        payments.sort(key=lambda p: p["date"])
        return payments


    def _schedule_editor(prefix, payments):
        """Редактируемая таблица платежей. Возвращает список {date, amount}."""
        edited = st.data_editor(
            _payments_to_df(payments),
            key=f"{prefix}_payments",
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_config={
                "Дата платежа": st.column_config.DateColumn("Дата платежа", format="DD.MM.YYYY"),
                "Сумма": st.column_config.NumberColumn("Сумма", min_value=0.0, step=1000.0, format="%.0f"),
            },
        )
        return _df_to_payments(edited)


    def _sale_sell_tax_fields(prefix, d):
        st.markdown("**Продажа**")
        c1, c2 = st.columns(2)
        sell_price = c1.number_input(
            "Цена продажи", min_value=0.0, value=float(d.get("sell_price", 0)), step=1000.0, key=f"{prefix}_sell",
        )
        default_sell_date = date.today()
        if d.get("sell_date"):
            try:
                default_sell_date = pd.to_datetime(d["sell_date"]).date()
            except Exception:  # noqa: BLE001
                pass
        sell_date = c2.date_input("Дата продажи", value=default_sell_date, format="DD.MM.YYYY", key=f"{prefix}_selldate")

        st.markdown("**Налог на продажу**")
        t1, t2 = st.columns([1, 2])
        tax_pct = t1.number_input(
            "Ставка налога, %", min_value=0.0, max_value=100.0,
            value=float(d.get("tax_pct", 0)), step=1.0, key=f"{prefix}_taxpct",
        )
        tax_base = t2.radio(
            "Считать налог", SALE_TAX_BASES, horizontal=True,
            index=SALE_TAX_BASES.index(d.get("tax_base")) if d.get("tax_base") in SALE_TAX_BASES else 0,
            key=f"{prefix}_taxbase",
        )
        return {"sell_price": sell_price, "sell_date": sell_date.isoformat(), "tax_pct": tax_pct, "tax_base": tax_base}


    def _registry_prefill(prefix):
        """Блок «Мой объект»: выбор объекта из реестра, подтягивание взносов из «Сделок»
        и дата погашения остатка. Пишет подтянутый график в session_state['{prefix}_prefill']."""
        real_estate = load_real_estate()
        deals = load_deals()
        if real_estate.empty or deals.empty:
            st.info("Чтобы подтянуть объект из реестра, сначала добавь его на странице «Ввод данных».")
            return
        with st.expander("🔍 Диагностика связки (что видит приложение)", expanded=False):
            if config.DEALS_OBJECT_COLUMN in deals.columns:
                codes = sorted(deals[config.DEALS_OBJECT_COLUMN].dropna().astype(str).str.strip().unique())
                st.write(f"Коды в «Сделки» → «{config.DEALS_OBJECT_COLUMN}»:", codes)
            else:
                st.error(f"В «Сделках» НЕТ столбца «{config.DEALS_OBJECT_COLUMN}». "
                         f"Столбцы: {list(deals.columns)}")
            if config.REALESTATE_OBJECT_COLUMN in real_estate.columns:
                re_codes = sorted(real_estate[config.REALESTATE_OBJECT_COLUMN].dropna().astype(str).str.strip().unique())
                st.write(f"Коды в «Real Estate» → «{config.REALESTATE_OBJECT_COLUMN}»:", re_codes)
            else:
                st.error(f"В «Real Estate» НЕТ столбца «{config.REALESTATE_OBJECT_COLUMN}». "
                         f"Столбцы: {list(real_estate.columns)}")
            st.caption("Если столбцов нет — нажми «🔄 Обновить данные» в боковой панели (данные закэшированы до добавления столбца).")

        choices = object_choices(real_estate, deals)
        if not choices:
            st.warning("В листах «Real Estate»/«Сделки» не найдено объектов.")
            return

        labels = [c["label"] for c in choices]
        idx = st.selectbox("Объект из реестра", range(len(labels)), format_func=lambda i: labels[i], key=f"{prefix}_obj")
        chosen = choices[idx]
        payments = pull_payments(deals, chosen["key"])
        paid = sum(p["amount"] for p in payments)
        total = chosen["total_purchase"]

        c1, c2 = st.columns(2)
        c1.metric("Подтянуто взносов", f"{len(payments)} на {_fmt_profit(paid)}")
        c2.metric("Полная цена покупки", _fmt_profit(total) if total else "—")

        if not payments:
            st.warning(
                f"По объекту «{chosen['key']}» не найдено платежей «Покупка» в «Сделках». "
                f"Проверь, что в «Сделках» столбец «{config.DEALS_OBJECT_COLUMN}» "
                f"(или «{config.DEALS_PURPOSE_COLUMN}») содержит это имя."
            )

        remaining = None
        if total is not None:
            remaining = max(total - paid, 0.0)
        r1, r2 = st.columns(2)
        payoff_date = r1.date_input("Дата погашения остатка", value=date.today(), format="DD.MM.YYYY", key=f"{prefix}_payoff")
        r2.metric("Остаток к погашению", _fmt_profit(remaining) if remaining is not None else "остаток = цена − взносы")

        schedule = list(payments)
        if remaining and remaining > 0:
            schedule.append({"date": payoff_date.isoformat(), "amount": remaining})
        if st.button("⤵️ Подставить график из реестра в таблицу ниже", key=f"{prefix}_apply"):
            st.session_state[f"{prefix}_prefill"] = schedule
            # сбрасываем состояние редактора, иначе он игнорирует новые данные
            st.session_state.pop(f"{prefix}_payments", None)
            st.rerun()


    def _sale_metrics_and_recap(m):
        currency = m.get("currency", "$")
        r = compute_sale(m)
        kpi_row([
            kpi_card("💰", "Чистая прибыль", _fmt_profit(r["net"], currency), icon_bg="#ecfdf5"),
            kpi_card("📊", "Доходность за всё время", f"{r['total_return']:.1f}%" if r["total_return"] is not None else "—", icon_bg="#eff6ff"),
            kpi_card("📅", "Доходность в год (XIRR)", f"{r['annual']:.1f}%" if r["annual"] is not None else "—", icon_bg="#fff7ed"),
        ])

        period = f"{r['years']:.1f} лет" if r["years"] else "—"
        n_pay = len(m.get("payments") or [])
        tax_str = f"{m.get('tax_pct', 0):g}% ({str(m.get('tax_base', SALE_TAX_BASES[0])).lower()})"
        recap = (
            f"Вложено {_fmt_profit(r['total_invested'], currency)} за {n_pay} платеж(ей) · "
            f"продажа {_fmt_profit(r['sell'], currency)} · срок {period} · "
            f"налог {tax_str} = {_fmt_profit(r['tax'], currency)} · на руки {_fmt_profit(r['proceeds'], currency)}"
        )
        st.caption(recap.replace("$", r"\$"))


    def _sale_form(prefix, d):
        """Полный ввод проекта продажи. Возвращает dict полей (без name/id)."""
        currency = _currency_select(d, key=f"{prefix}_currency")

        use_registry = st.checkbox("🏠 Мой объект — подтянуть график из реестра", key=f"{prefix}_useobj")
        if use_registry:
            if currency != "$":
                st.caption("⚠️ Данные из реестра («Сделки»/«Real Estate») в долларах — при подтягивании выбери валюту $.")
            _registry_prefill(prefix)

        st.markdown("**График платежей (вложения)**")
        st.caption("Каждая строка — дата и сумма взноса. Строки можно добавлять и удалять.")
        payments = st.session_state.get(f"{prefix}_prefill", d.get("payments"))
        payments = _schedule_editor(prefix, payments)

        sell_tax = _sale_sell_tax_fields(prefix, d)
        return {"payments": payments, "currency": currency, **sell_tax}


    # --- Добавление проекта продажи ---
    with st.expander("➕ Добавить проект продажи", expanded=not sale_models):
        add_name = st.text_input("Название проекта", key="add_sale_name")
        add_vals = _sale_form("add_sale", {})
        if st.button("Добавить проект продажи", key="add_sale_submit"):
            if add_name.strip():
                st.session_state["sale_finmodels"].append({"id": str(uuid.uuid4()), "name": add_name.strip(), **add_vals})
                save_sale_finmodels(st.session_state["sale_finmodels"])
                for k in [key for key in st.session_state if str(key).startswith("add_sale")]:
                    st.session_state.pop(k, None)  # сброс формы добавления
                st.rerun()
            else:
                st.warning("Укажи название проекта.")

    # --- Список проектов продажи ---
    if not sale_models:
        st.info("Пока нет проектов продажи. Добавь первый через «➕ Добавить проект продажи» выше.")
    else:
        st.caption(f"Проектов продажи: {len(sale_models)}")
        sale_editing_id = st.session_state.get("sale_fm_editing_id")

        for m in sale_models:
            with card("finmodel", f"sale_{m['id']}"):
                if sale_editing_id == m["id"]:
                    prefix = f"edit_sale_{m['id']}"
                    e_name = st.text_input("Название проекта", value=m.get("name", ""), key=f"{prefix}_name")
                    e_vals = _sale_form(prefix, m)
                    b_save, b_cancel = st.columns(2)
                    if b_save.button("💾 Сохранить", key=f"{prefix}_save"):
                        if e_name.strip():
                            m.update({"name": e_name.strip(), **e_vals})
                            save_sale_finmodels(st.session_state["sale_finmodels"])
                            st.session_state.pop(f"{prefix}_prefill", None)
                            st.session_state["sale_fm_editing_id"] = None
                            st.rerun()
                        else:
                            st.warning("Укажи название проекта.")
                    if b_cancel.button("Отмена", key=f"{prefix}_cancel"):
                        st.session_state.pop(f"{prefix}_prefill", None)
                        st.session_state["sale_fm_editing_id"] = None
                        st.rerun()
                else:
                    head, edit_btn, del_btn = st.columns([8, 1, 1])
                    safe_name = str(m.get("name", "Проект")).replace("$", r"\$")
                    head.markdown(f"### {safe_name} ({m.get('currency', '$')})")
                    if edit_btn.button("✏️", key=f"sale_fm_edit_{m['id']}", help="Редактировать проект"):
                        st.session_state["sale_fm_editing_id"] = m["id"]
                        st.rerun()
                    if del_btn.button("🗑", key=f"sale_fm_del_{m['id']}", help="Удалить проект"):
                        st.session_state["sale_finmodels"] = [x for x in sale_models if x["id"] != m["id"]]
                        save_sale_finmodels(st.session_state["sale_finmodels"])
                        st.rerun()
                    _sale_metrics_and_recap(m)


    # ======================= ПОКУПКА + СДАЧА В АРЕНДУ =======================
    st.divider()
    section_title("🏘️ Покупка + аренда")
    st.caption(
        "Реальная доходность лота, где есть и рост стоимости, и арендный доход. "
        "Годовая — через XIRR: вложения по датам, аренда помесячно, текущая "
        "рыночная стоимость как «виртуальная продажа» сегодня."
    )

    if "buyrent_finmodels" not in st.session_state:
        st.session_state["buyrent_finmodels"] = load_buyrent_finmodels()

    buyrent_models = st.session_state["buyrent_finmodels"]


    def _pct(v):
        return f"{v:.1f}%" if v is not None else "—"


    def _date_or(d, key, fallback):
        if d.get(key):
            try:
                return pd.to_datetime(d[key]).date()
            except Exception:  # noqa: BLE001
                pass
        return fallback


    def _buyrent_registry_prefill(prefix):
        real_estate = load_real_estate()
        deals = load_deals()
        if real_estate.empty or deals.empty:
            st.info("Чтобы подтянуть объект из реестра, сначала добавь его на странице «Ввод данных».")
            return
        choices = object_choices(real_estate, deals)
        if not choices:
            st.warning("В листах «Real Estate»/«Сделки» не найдено объектов.")
            return

        labels = [c["label"] for c in choices]
        idx = st.selectbox("Объект из реестра", range(len(labels)), format_func=lambda i: labels[i], key=f"{prefix}_obj")
        chosen = choices[idx]
        payments = pull_payments(deals, chosen["key"])
        paid = sum(p["amount"] for p in payments)

        c1, c2, c3 = st.columns(3)
        c1.metric("Подтянуто взносов", f"{len(payments)} на {_fmt_profit(paid)}")
        c2.metric("Цена покупки", _fmt_profit(chosen["total_purchase"]) if chosen["total_purchase"] else "—")
        c3.metric("Рыночная стоимость", _fmt_profit(chosen.get("market")) if chosen.get("market") else "—")

        if not payments:
            st.warning(
                f"По объекту «{chosen['key']}» не найдено платежей «Покупка» в «Сделках». "
                f"Проверь столбец «{config.DEALS_OBJECT_COLUMN}» (или «{config.DEALS_PURPOSE_COLUMN}»)."
            )
        if st.button("⤵️ Подставить платежи и рыночную стоимость", key=f"{prefix}_apply"):
            st.session_state[f"{prefix}_prefill"] = payments
            if chosen.get("market") is not None:
                st.session_state[f"{prefix}_market_prefill"] = float(chosen["market"])
            st.session_state.pop(f"{prefix}_payments", None)
            st.session_state.pop(f"{prefix}_market", None)
            st.rerun()


    def _buyrent_form(prefix, d):
        """Полный ввод проекта «покупка + аренда». Возвращает dict полей."""
        currency = _currency_select(d, key=f"{prefix}_currency")

        use_registry = st.checkbox("🏠 Мой объект — подтянуть из реестра", key=f"{prefix}_useobj")
        if use_registry:
            if currency != "$":
                st.caption("⚠️ Данные из реестра («Сделки»/«Real Estate») в долларах — при подтягивании выбери валюту $.")
            _buyrent_registry_prefill(prefix)

        st.markdown("**Платежи за покупку (вложения)**")
        st.caption("Каждая строка — дата и сумма взноса. Строки можно добавлять и удалять.")
        payments = st.session_state.get(f"{prefix}_prefill", d.get("payments"))
        payments = _schedule_editor(prefix, payments)

        st.markdown("**Ремонт**")
        r1, r2 = st.columns(2)
        reno = r1.number_input("Стоимость ремонта", min_value=0.0, value=float(d.get("reno", 0)), step=1000.0, key=f"{prefix}_reno")
        reno_date = r2.date_input("Дата ремонта", value=_date_or(d, "reno_date", date.today()), format="DD.MM.YYYY", key=f"{prefix}_renodate")

        st.markdown("**Аренда**")
        a1, a2 = st.columns(2)
        rent_month = a1.number_input("Чистая аренда в месяц", min_value=0.0, value=float(d.get("rent_month", 0)), step=50.0, key=f"{prefix}_rent")
        rent_start = a2.date_input("Дата сдачи в аренду", value=_date_or(d, "rent_start", date.today()), format="DD.MM.YYYY", key=f"{prefix}_rentstart")

        st.markdown("**Текущая рыночная стоимость**")
        market_default = st.session_state.get(f"{prefix}_market_prefill", d.get("market_value") or 0)
        market_value = st.number_input("Рыночная стоимость сейчас", min_value=0.0, value=float(market_default or 0), step=1000.0, key=f"{prefix}_market")

        st.markdown("**Продажа в будущем (опционально)**")
        plan_sale = st.checkbox(
            "Заложить продажу в будущем (сдаю N лет, потом продаю)",
            value=bool(d.get("plan_sale")), key=f"{prefix}_plansale",
        )
        sale_fields = {"plan_sale": plan_sale}
        if plan_sale:
            st.caption("Аренда копится до даты продажи, а выход считается по планируемой цене (за вычетом налога).")
            s1, s2 = st.columns(2)
            sale_default = float(d.get("sell_price") or market_value or 0)
            sell_price = s1.number_input("Планируемая цена продажи", min_value=0.0, value=sale_default, step=1000.0, key=f"{prefix}_sellprice")
            sell_date = s2.date_input(
                "Планируемая дата продажи",
                value=_date_or(d, "sell_date", date.today().replace(year=date.today().year + 3)),
                format="DD.MM.YYYY", key=f"{prefix}_selldate",
            )
            t1, t2 = st.columns([1, 2])
            tax_pct = t1.number_input("Налог с продажи, %", min_value=0.0, max_value=100.0, value=float(d.get("tax_pct", 0)), step=1.0, key=f"{prefix}_taxpct")
            tax_base = t2.radio(
                "Считать налог", SALE_TAX_BASES, horizontal=True,
                index=SALE_TAX_BASES.index(d.get("tax_base")) if d.get("tax_base") in SALE_TAX_BASES else 0,
                key=f"{prefix}_taxbase",
            )
            sale_fields.update({
                "sell_price": sell_price, "sell_date": sell_date.isoformat(),
                "tax_pct": tax_pct, "tax_base": tax_base,
            })

        return {
            "currency": currency,
            "payments": payments,
            "reno": reno,
            "reno_date": reno_date.isoformat(),
            "rent_month": rent_month,
            "rent_start": rent_start.isoformat(),
            "market_value": market_value,
            **sale_fields,
        }


    def _buyrent_metrics(m):
        currency = m.get("currency", "$")
        r = compute_buyrent(m)
        growth_label = "Прирост при продаже" if r["planning"] else "Прирост стоимости"
        kpi_row([
            kpi_card("📈", growth_label, _fmt_profit(r["appreciation"], currency), icon_bg="#ecfdf5"),
            kpi_card("🏠", "Прибыль от аренды в год", _fmt_profit(r["annual_rent"], currency), icon_bg="#eff6ff"),
            kpi_card("📊", "Доходность от роста", _pct(r["appr_return"]), icon_bg="#fff7ed"),
            kpi_card("💵", "Аренда суммарно (доходность)", _pct(r["rent_yield_cum"]), icon_bg="#f5f3ff"),
            kpi_card("🧮", "Общая доходность (рост + аренда)", _pct(r["total_return"]), icon_bg="#ecfdf5"),
            kpi_card("📅", "Годовая (XIRR)", _pct(r["annual"]), icon_bg="#eff6ff"),
        ])

        period = f"{r['years']:.1f} лет" if r["years"] else "—"
        invested_line = (
            f"Вложено {_fmt_profit(r['invested'], currency)} (покупка {_fmt_profit(r['invested_payments'], currency)}"
            f" + ремонт {_fmt_profit(r['reno'], currency)})"
        )
        if r["planning"]:
            exit_line = (
                f"продажа {_fmt_profit(r['sell_price'], currency)} "
                f"({r['sell_date'].strftime('%m.%Y') if r['sell_date'] else '—'}), "
                f"налог {_fmt_profit(r['tax'], currency)} → на руки {_fmt_profit(r['proceeds'], currency)}"
            )
        else:
            exit_line = f"рыночная {_fmt_profit(r['market'], currency)} (оценка сегодня)"
        recap = (
            f"{invested_line} · {exit_line} · "
            f"в аренде {r['months_rented']:.0f} мес → аренды {_fmt_profit(r['cumulative_rent'], currency)} · "
            f"срок проекта {period}"
        )
        st.caption(recap.replace("$", r"\$"))


    # --- Добавление проекта «покупка + аренда» ---
    with st.expander("➕ Добавить проект «покупка + аренда»", expanded=not buyrent_models):
        add_name = st.text_input("Название проекта", key="add_buyrent_name")
        add_vals = _buyrent_form("add_buyrent", {})
        if st.button("Добавить проект", key="add_buyrent_submit"):
            if add_name.strip():
                st.session_state["buyrent_finmodels"].append({"id": str(uuid.uuid4()), "name": add_name.strip(), **add_vals})
                save_buyrent_finmodels(st.session_state["buyrent_finmodels"])
                for k in [key for key in st.session_state if str(key).startswith("add_buyrent")]:
                    st.session_state.pop(k, None)
                st.rerun()
            else:
                st.warning("Укажи название проекта.")

    # --- Список проектов «покупка + аренда» ---
    if not buyrent_models:
        st.info("Пока нет проектов. Добавь первый через «➕ Добавить проект «покупка + аренда»» выше.")
    else:
        st.caption(f"Проектов: {len(buyrent_models)}")
        buyrent_editing_id = st.session_state.get("buyrent_fm_editing_id")

        for m in buyrent_models:
            with card("finmodel", f"buyrent_{m['id']}"):
                if buyrent_editing_id == m["id"]:
                    prefix = f"edit_buyrent_{m['id']}"
                    e_name = st.text_input("Название проекта", value=m.get("name", ""), key=f"{prefix}_name")
                    e_vals = _buyrent_form(prefix, m)
                    b_save, b_cancel = st.columns(2)
                    if b_save.button("💾 Сохранить", key=f"{prefix}_save"):
                        if e_name.strip():
                            m.update({"name": e_name.strip(), **e_vals})
                            save_buyrent_finmodels(st.session_state["buyrent_finmodels"])
                            st.session_state.pop(f"{prefix}_prefill", None)
                            st.session_state.pop(f"{prefix}_market_prefill", None)
                            st.session_state["buyrent_fm_editing_id"] = None
                            st.rerun()
                        else:
                            st.warning("Укажи название проекта.")
                    if b_cancel.button("Отмена", key=f"{prefix}_cancel"):
                        st.session_state.pop(f"{prefix}_prefill", None)
                        st.session_state.pop(f"{prefix}_market_prefill", None)
                        st.session_state["buyrent_fm_editing_id"] = None
                        st.rerun()
                else:
                    head, edit_btn, del_btn = st.columns([8, 1, 1])
                    safe_name = str(m.get("name", "Проект")).replace("$", r"\$")
                    head.markdown(f"### {safe_name} ({m.get('currency', '$')})")
                    if edit_btn.button("✏️", key=f"buyrent_fm_edit_{m['id']}", help="Редактировать проект"):
                        st.session_state["buyrent_fm_editing_id"] = m["id"]
                        st.rerun()
                    if del_btn.button("🗑", key=f"buyrent_fm_del_{m['id']}", help="Удалить проект"):
                        st.session_state["buyrent_finmodels"] = [x for x in buyrent_models if x["id"] != m["id"]]
                        save_buyrent_finmodels(st.session_state["buyrent_finmodels"])
                        st.rerun()
                    _buyrent_metrics(m)
