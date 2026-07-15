import uuid
from datetime import date

import pandas as pd
import streamlit as st

from data_source import load_real_estate, sidebar_refresh_control
from docs_store import load_documents, save_documents
from sale_finmodel import object_choices

sidebar_refresh_control()

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
        st.dataframe(
            table, width="stretch", hide_index=True,
            column_config={"Ссылка": st.column_config.LinkColumn("Ссылка", display_text="Открыть")},
        )

        with st.expander(f"🗑 Удалить документ ({len(obj_docs)})"):
            labels = {
                f"{d.get('type', '')} №{d.get('number') or '—'} · {_fmt_date(d.get('date'))} · {d.get('summary', '')}"[:80]: d["id"]
                for d in obj_docs
            }
            to_del = st.selectbox("Выбери документ", list(labels), key=f"del_sel_{chosen['key']}")
            if st.button("Удалить", key=f"del_btn_{chosen['key']}"):
                st.session_state["documents"] = [x for x in documents if x["id"] != labels[to_del]]
                save_documents(st.session_state["documents"])
                st.rerun()
