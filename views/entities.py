import uuid
from datetime import date

import streamlit as st

from entities_store import load_entities, save_entities

st.title("🏛️ Юрлица")
st.caption("Справочник ООО/ИП — регистрационные данные, юр. адрес, налоговый режим, владение.")

if "entities" not in st.session_state:
    st.session_state["entities"] = load_entities()

entities = st.session_state["entities"]

ENTITY_TYPES = ["ООО", "ИП"]
STATUSES = ["Действует", "Требуется ликвидация"]
TAX_SYSTEMS = ["УСН доходы", "УСН доходы-расходы", "ОСН", "Патент", "Иное"]

STATUS_COLORS = {
    "Действует": ("#e6f4ea", "#1b5e20"),
    "Требуется ликвидация": ("#fdecea", "#b3261e"),
}


def _md(text):
    return str(text or "").replace("$", r"\$")


def _badge(text):
    bg, color = STATUS_COLORS.get(text, ("#eef2f9", "#1a1a2e"))
    return (
        f"<span style='display:inline-block;background:{bg};color:{color};"
        "padding:3px 12px;border-radius:14px;font-size:0.9rem;font-weight:600;"
        f"margin:2px 0'>{_md(text)}</span>"
    )


def _fmt_date(iso):
    if not iso:
        return ""
    try:
        return date.fromisoformat(iso).strftime("%d.%m.%Y")
    except Exception:  # noqa: BLE001
        return str(iso)


def _persist():
    save_entities(st.session_state["entities"])


def _field(label, value):
    """Строка «label: value» — пропускается целиком, если значение пустое,
    чтобы карточка не пестрела прочерками по незаполненным полям."""
    if not value:
        return
    st.markdown(f"**{_md(label)}:** {_md(value)}")


def _render_form(prefix, existing=None):
    """Общая форма добавления/редактирования. existing=None — режим добавления."""
    e = existing or {}
    name = st.text_input("Название", value=e.get("name", ""), key=f"{prefix}_name")
    c1, c2, c3 = st.columns(3)
    entity_type = c1.selectbox(
        "Тип", ENTITY_TYPES,
        index=ENTITY_TYPES.index(e["type"]) if e.get("type") in ENTITY_TYPES else 0,
        key=f"{prefix}_type",
    )
    status = c2.selectbox(
        "Статус", STATUSES,
        index=STATUSES.index(e["status"]) if e.get("status") in STATUSES else 0,
        key=f"{prefix}_status",
    )
    try:
        reg_date_default = date.fromisoformat(e["reg_date"]) if e.get("reg_date") else date.today()
    except Exception:  # noqa: BLE001
        reg_date_default = date.today()
    reg_date = c3.date_input("Дата регистрации", value=reg_date_default, format="DD.MM.YYYY", key=f"{prefix}_regdate")

    c4, c5, c6 = st.columns(3)
    inn = c4.text_input("ИНН", value=e.get("inn", ""), key=f"{prefix}_inn")
    ogrn = c5.text_input("ОГРН/ОГРНИП", value=e.get("ogrn", ""), key=f"{prefix}_ogrn")
    kpp = c6.text_input("КПП", value=e.get("kpp", ""), key=f"{prefix}_kpp")

    st.markdown("###### Юридический адрес")
    address = st.text_input("Адрес", value=e.get("address", ""), key=f"{prefix}_address")
    a1, a2, a3 = st.columns(3)
    address_provider = a1.text_input("Подрядчик по адресу", value=e.get("address_provider", ""), key=f"{prefix}_addrprovider")
    address_contact = a2.text_input("Контакт", value=e.get("address_contact", ""), key=f"{prefix}_addrcontact")
    try:
        addr_end_default = date.fromisoformat(e["address_contract_end"]) if e.get("address_contract_end") else None
    except Exception:  # noqa: BLE001
        addr_end_default = None
    address_contract_end = a3.date_input(
        "Дата окончания договора", value=addr_end_default, format="DD.MM.YYYY", key=f"{prefix}_addrend",
    )

    st.markdown("###### Налоги")
    t1, t2 = st.columns(2)
    tax_system = t1.selectbox(
        "Система налогообложения", TAX_SYSTEMS,
        index=TAX_SYSTEMS.index(e["tax_system"]) if e.get("tax_system") in TAX_SYSTEMS else 0,
        key=f"{prefix}_taxsystem",
    )
    tax_rate = t2.text_input("Ставка", value=e.get("tax_rate", ""), key=f"{prefix}_taxrate")

    st.markdown("###### Владение и управление")
    o1, o2, o3 = st.columns(3)
    ownership_share = o1.number_input(
        "Доля владения, %", min_value=0.0, max_value=100.0,
        value=float(e.get("ownership_share") or 100.0), step=1.0, key=f"{prefix}_share",
    )
    director = o2.text_input("Директор", value=e.get("director", ""), key=f"{prefix}_director")
    other_founders = o3.text_input("Прочие учредители", value=e.get("other_founders", ""), key=f"{prefix}_founders")

    st.markdown("###### Финансы и деятельность")
    f1, f2 = st.columns(2)
    bank_account = f1.text_input("Расчётный счёт", value=e.get("bank_account", ""), key=f"{prefix}_bankacc")
    activity = f2.text_input("Вид деятельности", value=e.get("activity", ""), key=f"{prefix}_activity")

    return {
        "name": name.strip(),
        "type": entity_type,
        "status": status,
        "reg_date": reg_date.isoformat() if reg_date else "",
        "inn": inn.strip(),
        "ogrn": ogrn.strip(),
        "kpp": kpp.strip(),
        "address": address.strip(),
        "address_provider": address_provider.strip(),
        "address_contact": address_contact.strip(),
        "address_contract_end": address_contract_end.isoformat() if address_contract_end else "",
        "tax_system": tax_system,
        "tax_rate": tax_rate.strip(),
        "ownership_share": ownership_share,
        "director": director.strip(),
        "other_founders": other_founders.strip(),
        "bank_account": bank_account.strip(),
        "activity": activity.strip(),
    }


# ============================ Добавление ============================
with st.expander("➕ Добавить юрлицо", expanded=not entities):
    with st.form("add_entity", clear_on_submit=True):
        values = _render_form("add")
        if st.form_submit_button("Добавить"):
            if values["name"]:
                values["id"] = str(uuid.uuid4())
                st.session_state["entities"].append(values)
                _persist()
                st.rerun()
            else:
                st.warning("Укажи название юрлица.")

# ============================ Список юрлиц ============================
editing_id = st.session_state.get("editing_entity_id")

if not entities:
    st.info("Пока нет юрлиц. Добавь через «➕ Добавить юрлицо» выше.")
else:
    st.caption(f"Юрлиц: {len(entities)}")
    for ent in entities:
        with st.container(border=True):
            if editing_id == ent["id"]:
                with st.form(f"edit_entity_{ent['id']}"):
                    new_values = _render_form(f"edit_{ent['id']}", existing=ent)
                    b_save, b_cancel = st.columns(2)
                    if b_save.form_submit_button("💾 Сохранить", type="primary"):
                        if new_values["name"]:
                            ent.update(new_values)
                            _persist()
                            st.session_state["editing_entity_id"] = None
                            st.rerun()
                        else:
                            st.warning("Укажи название юрлица.")
                    if b_cancel.form_submit_button("Отмена"):
                        st.session_state["editing_entity_id"] = None
                        st.rerun()
            else:
                head, edit_btn, del_btn = st.columns([7, 1, 1])
                head.markdown(f"### {_md(ent['name'])} · {_md(ent.get('type', ''))}")
                if ent.get("status"):
                    head.markdown(_badge(ent["status"]), unsafe_allow_html=True)
                if edit_btn.button("✏️", key=f"entedit_{ent['id']}", help="Редактировать юрлицо", type="tertiary"):
                    st.session_state["editing_entity_id"] = ent["id"]
                    st.rerun()
                if del_btn.button("🗑", key=f"entdel_{ent['id']}", help="Удалить юрлицо", type="tertiary"):
                    st.session_state["entities"] = [x for x in entities if x["id"] != ent["id"]]
                    _persist()
                    st.rerun()

                col_l, col_r = st.columns(2)
                with col_l:
                    _field("ИНН", ent.get("inn"))
                    _field("ОГРН/ОГРНИП", ent.get("ogrn"))
                    _field("КПП", ent.get("kpp"))
                    _field("Дата регистрации", _fmt_date(ent.get("reg_date")))
                    _field("Система налогообложения", ent.get("tax_system"))
                    _field("Ставка", ent.get("tax_rate"))
                    _field("Расчётный счёт", ent.get("bank_account"))
                    _field("Вид деятельности", ent.get("activity"))
                with col_r:
                    _field("Доля владения", f"{ent['ownership_share']:.0f}%" if ent.get("ownership_share") else "")
                    _field("Директор", ent.get("director"))
                    _field("Прочие учредители", ent.get("other_founders"))
                    _field("Юридический адрес", ent.get("address"))
                    _field("Подрядчик по адресу", ent.get("address_provider"))
                    _field("Контакт", ent.get("address_contact"))
                    _field("Окончание договора адреса", _fmt_date(ent.get("address_contract_end")))
