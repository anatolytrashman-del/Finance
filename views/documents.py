import uuid
from datetime import date

import pandas as pd
import streamlit as st

from data_source import load_real_estate, sidebar_refresh_control
from docs_store import load_documents, save_documents
from rates_widget import render_sidebar_rates
from sale_finmodel import object_choices

sidebar_refresh_control()
render_sidebar_rates()

st.title("🗂️ Архив документов")
st.caption("Файлы храним на Google Диске, сюда вставляем ссылку. Блок — на каждый объект недвижимости.")

real_estate = load_real_estate()
if real_estate is None:
    st.info("Нажми «🔄 Обновить данные» в боковой панели, чтобы загрузить список объектов.")
    st.stop()

choices = object_choices(real_estate)
if not choices:
    st.warning("В листе «Real Estate» не найдено объектов.")
    st.stop()

if "documents" not in st.session_state:
    st.session_state["documents"] = load_documents()
documents = st.session_state["documents"]

DOC_TYPES = [
    "Договор", "ДДУ", "Допсоглашение", "Акт приёма-передачи", "Счёт",
    "Платёжное поручение", "Выписка", "Справка", "Свидетельство",
    "Документы на юрлицо", "Иное",
]

CURRENCIES = ["$", "€", "₽"]


def _fmt_amount(v, currency="$"):
    if v in (None, "") or float(v) == 0:
        return "—"
    return f"{float(v):,.0f} {currency or '$'}".replace(",", " ")


def _fmt_date(v):
    if not v:
        return "—"
    try:
        return pd.to_datetime(v).strftime("%d.%m.%Y")
    except Exception:  # noqa: BLE001
        return str(v)


# ============================ Добавление ============================
with st.expander("➕ Добавить документ", expanded=not documents):
    with st.form("add_document", clear_on_submit=True):
        obj_idx = st.selectbox(
            "Объект", range(len(choices)), format_func=lambda i: choices[i]["label"], key="doc_obj",
        )
        c1, c2, c3 = st.columns(3)
        d_type = c1.selectbox("Тип документа", DOC_TYPES)
        d_date = c2.date_input("Дата", value=date.today(), format="DD.MM.YYYY")
        d_number = c3.text_input("Номер")
        c4, c5, c6 = st.columns([1, 1, 3])
        d_amount = c4.number_input("Сумма", min_value=0.0, value=0.0, step=100.0)
        d_currency = c5.selectbox("Валюта", CURRENCIES)
        d_summary = c6.text_input("Суть — кратко")
        d_link = st.text_input("Ссылка на документ (Google Диск)")
        if st.form_submit_button("Добавить документ"):
            if d_link.strip() or d_summary.strip():
                chosen = choices[obj_idx]
                documents.append({
                    "id": str(uuid.uuid4()),
                    "object": chosen["key"],
                    "object_label": chosen["label"],
                    "type": d_type,
                    "date": d_date.isoformat(),
                    "number": d_number.strip(),
                    "amount": d_amount,
                    "currency": d_currency,
                    "summary": d_summary.strip(),
                    "link": d_link.strip(),
                })
                save_documents(documents)
                st.rerun()
            else:
                st.warning("Укажи хотя бы ссылку или суть документа.")

# ============================ Блоки по объектам ============================
total = len(documents)
st.caption(f"Всего документов: {total}")


def _save_and_rerun():
    save_documents(documents)
    st.rerun()


for chosen in choices:
    obj_docs = [d for d in documents if d.get("object") == chosen["key"]]
    with st.container(border=True):
        st.markdown(f"### 🏠 {chosen['label'].replace('$', chr(92) + '$')}")
        if not obj_docs:
            st.caption("Документов пока нет.")
            continue

        obj_docs = sorted(obj_docs, key=lambda d: d.get("date") or "")
        table = pd.DataFrame([
            {
                "Тип документа": d.get("type", ""),
                "Дата": _fmt_date(d.get("date")),
                "Номер": d.get("number", "") or "—",
                "Сумма": _fmt_amount(d.get("amount"), d.get("currency", "$")),
                "Суть — кратко": d.get("summary", "") or "—",
                "Ссылка": d.get("link", ""),
            }
            for d in obj_docs
        ])
        table_key = f"docs_table_{chosen['key']}"
        event = st.dataframe(
            table, width="stretch", hide_index=True,
            column_config={"Ссылка": st.column_config.LinkColumn("Ссылка", display_text="Открыть")},
            on_select="rerun", selection_mode="single-row", key=table_key,
        )
        selected_rows = event.selection.rows if hasattr(event, "selection") else []

        if not selected_rows:
            st.caption("Выбери строку в таблице, чтобы отредактировать или удалить документ.")
        else:
            d = obj_docs[selected_rows[0]]
            edit_key = f"doc_editing_{d['id']}"
            bc1, bc2, _bc3 = st.columns([1, 1, 6])
            if bc1.button("✏️ Редактировать", key=f"doc_edit_btn_{d['id']}", type="tertiary"):
                st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                st.rerun()
            if bc2.button("🗑 Удалить", key=f"doc_del_btn_{d['id']}", type="tertiary"):
                st.session_state["documents"] = [x for x in documents if x["id"] != d["id"]]
                # строка, на которую указывал выбор, могла исчезнуть/сдвинуться —
                # сбрасываем выбор, а не оставляем указывать на что попало
                st.session_state.pop(table_key, None)
                _save_and_rerun()

            if st.session_state.get(edit_key):
                with st.form(f"doc_edit_form_{d['id']}"):
                    obj_options = range(len(choices))
                    current_obj_idx = next(
                        (i for i, c in enumerate(choices) if c["key"] == d.get("object")), 0
                    )
                    e_obj_idx = st.selectbox(
                        "Объект", obj_options, index=current_obj_idx,
                        format_func=lambda i: choices[i]["label"], key=f"doc_edit_obj_{d['id']}",
                    )
                    ec1, ec2, ec3 = st.columns(3)
                    e_type = ec1.selectbox(
                        "Тип документа", DOC_TYPES,
                        index=DOC_TYPES.index(d["type"]) if d.get("type") in DOC_TYPES else 0,
                        key=f"doc_edit_type_{d['id']}",
                    )
                    try:
                        e_date_default = pd.to_datetime(d.get("date")).date() if d.get("date") else date.today()
                    except Exception:  # noqa: BLE001
                        e_date_default = date.today()
                    e_date = ec2.date_input(
                        "Дата", value=e_date_default, format="DD.MM.YYYY", key=f"doc_edit_date_{d['id']}",
                    )
                    e_number = ec3.text_input("Номер", value=d.get("number", ""), key=f"doc_edit_number_{d['id']}")
                    ec4, ec5, ec6 = st.columns([1, 1, 3])
                    e_amount = ec4.number_input(
                        "Сумма", min_value=0.0, value=float(d.get("amount") or 0.0), step=100.0,
                        key=f"doc_edit_amount_{d['id']}",
                    )
                    e_currency = ec5.selectbox(
                        "Валюта", CURRENCIES,
                        index=CURRENCIES.index(d["currency"]) if d.get("currency") in CURRENCIES else 0,
                        key=f"doc_edit_currency_{d['id']}",
                    )
                    e_summary = ec6.text_input("Суть — кратко", value=d.get("summary", ""), key=f"doc_edit_summary_{d['id']}")
                    e_link = st.text_input("Ссылка на документ (Google Диск)", value=d.get("link", ""), key=f"doc_edit_link_{d['id']}")
                    fc1, fc2 = st.columns(2)
                    save_clicked = fc1.form_submit_button("💾 Сохранить", type="primary")
                    cancel_clicked = fc2.form_submit_button("Отмена")
                    if save_clicked:
                        chosen_obj = choices[e_obj_idx]
                        d["object"] = chosen_obj["key"]
                        d["object_label"] = chosen_obj["label"]
                        d["type"] = e_type
                        d["date"] = e_date.isoformat()
                        d["number"] = e_number.strip()
                        d["amount"] = e_amount
                        d["currency"] = e_currency
                        d["summary"] = e_summary.strip()
                        d["link"] = e_link.strip()
                        st.session_state[edit_key] = False
                        st.session_state.pop(table_key, None)
                        _save_and_rerun()
                    elif cancel_clicked:
                        st.session_state[edit_key] = False
                        st.rerun()
