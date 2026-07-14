import uuid

import streamlit as st

from finmodel_store import (
    load_finmodels,
    load_sale_finmodels,
    save_finmodels,
    save_sale_finmodels,
)

st.title("🧮 Финмодель")
st.header("🏠 Аренда")

TAX_MODES = ["% от аренды", "Фикс. сумма в месяц"]

if "finmodels" not in st.session_state:
    st.session_state["finmodels"] = load_finmodels()

models = st.session_state["finmodels"]


def _fmt_money(v):
    return f"${v:,.0f}".replace(",", " ")


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
    st.markdown("**Капитальные расходы**")
    c1, c2 = st.columns(2)
    purchase = c1.number_input("Цена покупки, $", min_value=0.0, value=float(d.get("purchase", 0)), step=1000.0)
    reno = c2.number_input("Цена ремонта, $", min_value=0.0, value=float(d.get("reno", 0)), step=1000.0)

    st.markdown("**Доход**")
    rent = st.number_input("Цена аренды в месяц, $", min_value=0.0, value=float(d.get("rent", 0)), step=100.0)

    st.markdown("**Регулярные расходы**")
    tax_mode = st.radio(
        "Налог на сдачу считать как",
        TAX_MODES,
        horizontal=True,
        index=TAX_MODES.index(d.get("tax_mode")) if d.get("tax_mode") in TAX_MODES else 0,
    )
    tax_value = st.number_input(
        "Значение налога (% от аренды или сумма $ в месяц — по выбору выше)",
        min_value=0.0,
        value=float(d.get("tax_value", 0)),
        step=10.0,
    )
    c3, c4 = st.columns(2)
    fees_year = c3.number_input("Фиксированные сборы в год, $", min_value=0.0, value=float(d.get("fees_year", 0)), step=100.0)
    insurance_month = c4.number_input("Страховка в месяц, $", min_value=0.0, value=float(d.get("insurance_month", 0)), step=10.0)

    return {
        "purchase": purchase,
        "reno": reno,
        "rent": rent,
        "tax_mode": tax_mode,
        "tax_value": tax_value,
        "fees_year": fees_year,
        "insurance_month": insurance_month,
    }


def _metrics_and_recap(m):
    r = compute(m)
    cols = st.columns(4)
    cols[0].metric("Чистая доходность", f"{r['yield_pct']:.1f}%" if r["yield_pct"] is not None else "—")
    if r["payback"] is not None:
        payback_str = f"{r['payback']:.1f} лет"
    elif r["net_year"] <= 0:
        payback_str = "не окупается"
    else:
        payback_str = "—"
    cols[1].metric("Срок окупаемости", payback_str)
    cols[2].metric("Чистый доход / год", _fmt_money(r["net_year"]))
    cols[3].metric("Чистый доход / мес", _fmt_money(r["net_month"]))

    if m.get("tax_mode") == TAX_MODES[0]:
        tax_str = f"{m.get('tax_value', 0):g}% от аренды"
    else:
        tax_str = f"{_fmt_money(m.get('tax_value', 0))}/мес"
    recap = (
        f"Вложения: {_fmt_money(r['investment'])} "
        f"(покупка {_fmt_money(m.get('purchase', 0))} + ремонт {_fmt_money(m.get('reno', 0))}) · "
        f"Аренда: {_fmt_money(m.get('rent', 0))}/мес · "
        f"Грязный доход: {_fmt_money(r['gross_year'])}/год · "
        f"Расходы: {_fmt_money(r['expenses_year'])}/год "
        f"(налог {tax_str}, сборы {_fmt_money(m.get('fees_year', 0))}/год, "
        f"страховка {_fmt_money(m.get('insurance_month', 0))}/мес)"
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
        with st.container(border=True):
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
                head.markdown(f"### {safe_name}")
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
st.header("💰 Продажа")

SALE_TAX_BASES = ["От полной суммы продажи", "От прибыли"]
MONTHS = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]

if "sale_finmodels" not in st.session_state:
    st.session_state["sale_finmodels"] = load_sale_finmodels()

sale_models = st.session_state["sale_finmodels"]


def _fmt_profit(v):
    """Деньги со знаком: убыток показываем как -$5 000."""
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.0f}".replace(",", " ")


def _holding_years(m):
    by, bm = m.get("buy_year"), m.get("buy_month")
    sy, sm = m.get("sell_year"), m.get("sell_month")
    if not all(isinstance(x, int) for x in (by, bm, sy, sm)):
        return None
    months = (sy - by) * 12 + (sm - bm)
    return months / 12 if months > 0 else None


def compute_sale(m):
    buy = m.get("buy_price", 0) or 0
    sell = m.get("sell_price", 0) or 0
    tax_pct = m.get("tax_pct", 0) or 0
    tax_base = m.get("tax_base", SALE_TAX_BASES[0])

    gross = sell - buy
    if tax_base == SALE_TAX_BASES[1]:  # от прибыли (только с положительной прибыли)
        tax = max(gross, 0) * tax_pct / 100
    else:  # от полной суммы продажи
        tax = sell * tax_pct / 100
    net = gross - tax
    proceeds = sell - tax  # сумма на руки после налога

    total_return = net / buy * 100 if buy > 0 else None
    years = _holding_years(m)
    if buy > 0 and years and proceeds > 0:
        cagr = ((proceeds / buy) ** (1 / years) - 1) * 100
    else:
        cagr = None
    simple_annual = total_return / years if total_return is not None and years else None
    return {
        "gross": gross,
        "tax": tax,
        "net": net,
        "proceeds": proceeds,
        "total_return": total_return,
        "years": years,
        "cagr": cagr,
        "simple_annual": simple_annual,
    }


def _render_sale_fields(d):
    st.markdown("**Цены**")
    c1, c2 = st.columns(2)
    buy_price = c1.number_input("Цена покупки, $", min_value=0.0, value=float(d.get("buy_price", 0)), step=1000.0)
    sell_price = c2.number_input("Цена продажи, $", min_value=0.0, value=float(d.get("sell_price", 0)), step=1000.0)

    st.markdown("**Даты (месяц-год)**")
    d1, d2, d3, d4 = st.columns(4)
    buy_month = d1.selectbox(
        "Месяц покупки", MONTHS,
        index=(d.get("buy_month") - 1) if isinstance(d.get("buy_month"), int) else 0,
    )
    buy_year = d2.number_input(
        "Год покупки", min_value=1990, max_value=2100,
        value=int(d.get("buy_year") or 2024), step=1,
    )
    sell_month = d3.selectbox(
        "Месяц продажи", MONTHS,
        index=(d.get("sell_month") - 1) if isinstance(d.get("sell_month"), int) else 0,
    )
    sell_year = d4.number_input(
        "Год продажи", min_value=1990, max_value=2100,
        value=int(d.get("sell_year") or 2025), step=1,
    )

    st.markdown("**Налог на продажу**")
    t1, t2 = st.columns([1, 2])
    tax_pct = t1.number_input("Ставка налога, %", min_value=0.0, max_value=100.0, value=float(d.get("tax_pct", 0)), step=1.0)
    tax_base = t2.radio(
        "Считать налог",
        SALE_TAX_BASES,
        horizontal=True,
        index=SALE_TAX_BASES.index(d.get("tax_base")) if d.get("tax_base") in SALE_TAX_BASES else 0,
    )

    return {
        "buy_price": buy_price,
        "sell_price": sell_price,
        "buy_month": MONTHS.index(buy_month) + 1,
        "buy_year": int(buy_year),
        "sell_month": MONTHS.index(sell_month) + 1,
        "sell_year": int(sell_year),
        "tax_pct": tax_pct,
        "tax_base": tax_base,
    }


def _sale_metrics_and_recap(m):
    r = compute_sale(m)
    cols = st.columns(3)
    cols[0].metric("Чистая прибыль", _fmt_profit(r["net"]))
    cols[1].metric("Доходность за всё время", f"{r['total_return']:.1f}%" if r["total_return"] is not None else "—")
    cols[2].metric("Доходность в год", f"{r['cagr']:.1f}%" if r["cagr"] is not None else "—")

    def _month_year(month, year):
        if isinstance(month, int) and isinstance(year, int):
            return f"{MONTHS[month - 1]} {year}"
        return "—"

    period = "—"
    if r["years"]:
        period = f"{r['years']:.1f} лет"
    tax_str = f"{m.get('tax_pct', 0):g}% ({m.get('tax_base', SALE_TAX_BASES[0]).lower()})"
    recap = (
        f"Покупка {_fmt_profit(m.get('buy_price', 0))} ({_month_year(m.get('buy_month'), m.get('buy_year'))}) → "
        f"продажа {_fmt_profit(m.get('sell_price', 0))} ({_month_year(m.get('sell_month'), m.get('sell_year'))}) · "
        f"срок {period} · "
        f"налог {tax_str} = {_fmt_profit(r['tax'])} · "
        f"на руки после налога {_fmt_profit(r['proceeds'])}"
    )
    if r["simple_annual"] is not None:
        recap += f" · простая доходность {r['simple_annual']:.1f}%/год"
    st.caption(recap.replace("$", r"\$"))


# --- Форма добавления (продажа) ---
with st.expander("➕ Добавить проект продажи", expanded=not sale_models):
    with st.form("add_sale_model", clear_on_submit=True):
        s_name = st.text_input("Название проекта")
        s_vals = _render_sale_fields({})
        if st.form_submit_button("Добавить"):
            if s_name.strip():
                st.session_state["sale_finmodels"].append({"id": str(uuid.uuid4()), "name": s_name.strip(), **s_vals})
                save_sale_finmodels(st.session_state["sale_finmodels"])
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
        with st.container(border=True):
            if sale_editing_id == m["id"]:
                with st.form(f"edit_sale_{m['id']}"):
                    e_name = st.text_input("Название проекта", value=m.get("name", ""))
                    e_vals = _render_sale_fields(m)
                    b_save, b_cancel = st.columns(2)
                    if b_save.form_submit_button("💾 Сохранить"):
                        if e_name.strip():
                            m.update({"name": e_name.strip(), **e_vals})
                            save_sale_finmodels(st.session_state["sale_finmodels"])
                            st.session_state["sale_fm_editing_id"] = None
                            st.rerun()
                        else:
                            st.warning("Укажи название проекта.")
                    if b_cancel.form_submit_button("Отмена"):
                        st.session_state["sale_fm_editing_id"] = None
                        st.rerun()
            else:
                head, edit_btn, del_btn = st.columns([8, 1, 1])
                safe_name = str(m.get("name", "Проект")).replace("$", r"\$")
                head.markdown(f"### {safe_name}")
                if edit_btn.button("✏️", key=f"sale_fm_edit_{m['id']}", help="Редактировать проект"):
                    st.session_state["sale_fm_editing_id"] = m["id"]
                    st.rerun()
                if del_btn.button("🗑", key=f"sale_fm_del_{m['id']}", help="Удалить проект"):
                    st.session_state["sale_finmodels"] = [x for x in sale_models if x["id"] != m["id"]]
                    save_sale_finmodels(st.session_state["sale_finmodels"])
                    st.rerun()
                _sale_metrics_and_recap(m)
