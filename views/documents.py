import uuid
from datetime import date

import pandas as pd
import streamlit as st

from data_source import load_real_estate, sidebar_refresh_control
from docs_store import load_documents, save_documents
from rates_widget import render_sidebar_rates
from sale_finmodel import object_choices
from theme import card, esc, page, section_title

sidebar_refresh_control()
render_sidebar_rates()

real_estate = load_real_estate()
if real_estate is None:
    st.title("🗂️ Архив документов")
    st.info("Нажми «🔄 Обновить данные» в боковой панели, чтобы загрузить список объектов.")
    st.stop()

choices = object_choices(real_estate)
if not choices:
    st.title("🗂️ Архив документов")
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


with page("documents", "🗂️", "Архив документов", "Файлы храним на Google Диске, сюда вставляем ссылку. Блок — на каждый объект недвижимости."):
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


    # Кастомная HTML-таблица (theme.table()) не умеет встраивать нативные
    # кнопки внутрь ячейки — а тут нужен клик именно по конкретной строке
    # (редактировать/удалить). Поэтому строки собраны через st.columns() с той
    # же типографикой, что и theme.table() (th/td), а последние две колонки —
    # обычные кнопки Streamlit.
    DOC_COL_WIDTHS = [1.3, 0.9, 0.9, 0.9, 2.2, 0.9, 0.4, 0.4]
    DOC_HEADERS = ["Тип документа", "Дата", "Номер", "Сумма", "Суть — кратко", "Ссылка", "", ""]

    def _doc_th(text):
        return (
            "<div style='font-size:.68rem;font-weight:700;text-transform:uppercase;"
            f"letter-spacing:.05em;color:#9a9ca6;padding:0 0 8px'>{esc(text)}</div>"
        )

    def _doc_td(text):
        return f"<div style='font-size:.87rem;color:#17171C;padding:10px 0'>{esc(text)}</div>"

    for chosen in choices:
        obj_docs = [d for d in documents if d.get("object") == chosen["key"]]
        with card("documents", f"obj_{chosen['key']}"):
            section_title(f"🏠 {chosen['label']}")
            if not obj_docs:
                st.caption("Документов пока нет.")
                continue

            obj_docs = sorted(obj_docs, key=lambda d: d.get("date") or "")

            header_cols = st.columns(DOC_COL_WIDTHS)
            for col, label in zip(header_cols, DOC_HEADERS):
                if label:
                    col.markdown(_doc_th(label), unsafe_allow_html=True)

            for d in obj_docs:
                row = st.columns(DOC_COL_WIDTHS)
                row[0].markdown(_doc_td(d.get("type", "")), unsafe_allow_html=True)
                row[1].markdown(_doc_td(_fmt_date(d.get("date"))), unsafe_allow_html=True)
                row[2].markdown(_doc_td(d.get("number", "") or "—"), unsafe_allow_html=True)
                row[3].markdown(_doc_td(_fmt_amount(d.get("amount"), d.get("currency", "$"))), unsafe_allow_html=True)
                row[4].markdown(_doc_td(d.get("summary", "") or "—"), unsafe_allow_html=True)
                link = d.get("link", "")
                if link:
                    row[5].markdown(
                        "<div style='padding:10px 0'><a href='"
                        f"{esc(link)}' target='_blank' rel='noopener' "
                        "style='color:#17171C;font-weight:600;text-decoration:underline;font-size:.87rem'>"
                        "Открыть</a></div>",
                        unsafe_allow_html=True,
                    )
                else:
                    row[5].markdown(_doc_td("—"), unsafe_allow_html=True)

                edit_key = f"doc_editing_{d['id']}"
                if row[6].button("✏️", key=f"doc_edit_btn_{d['id']}", help="Редактировать", type="tertiary"):
                    st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                    st.rerun()
                if row[7].button("🗑", key=f"doc_del_btn_{d['id']}", help="Удалить", type="tertiary"):
                    st.session_state["documents"] = [x for x in documents if x["id"] != d["id"]]
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
                            _save_and_rerun()
                        elif cancel_clicked:
                            st.session_state[edit_key] = False
                            st.rerun()
