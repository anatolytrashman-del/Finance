import uuid

import streamlit as st

from finmodel_store import load_finmodels, save_finmodels

st.title("🧮 Финмодель аренды")

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
