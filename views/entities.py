import uuid
from datetime import date

import streamlit as st

from entities_store import load_entities, save_entities
from okved_store import load_okved

st.title("🏛️ Юрлица")
st.caption("Справочник ООО/ИП — регистрационные данные, юр. адрес, налоговый режим, владение.")

if "entities" not in st.session_state:
    st.session_state["entities"] = load_entities()
if "okved_reference" not in st.session_state:
    st.session_state["okved_reference"] = load_okved()

entities = st.session_state["entities"]
okved_reference = st.session_state["okved_reference"]
OKVED_CODES = [o["code"] for o in okved_reference]

ENTITY_TYPES = ["ООО", "ИП"]
STATUSES = ["Действует", "Требуется ликвидация"]
TAX_SYSTEMS = ["УСН доходы", "УСН доходы-расходы", "ОСН", "Патент", "Иное"]
EDO_STATUSES = ["Подключён Диадок", "Не подключён"]
ESIGN_STATUSES = ["Есть", "Нет"]

STATUS_COLORS = {
    "Действует": ("#e6f4ea", "#1b5e20"),
    "Требуется ликвидация": ("#fdecea", "#b3261e"),
}
GOOD = ("#e6f4ea", "#1b5e20")
NEUTRAL = ("#f1f1f4", "#5f6368")


def _md(text):
    return str(text or "").replace("$", r"\$")


def _pill(text, colors):
    bg, color = colors
    return (
        f"<span style='display:inline-block;background:{bg};color:{color};"
        "padding:3px 12px;border-radius:14px;font-size:0.85rem;font-weight:600;"
        f"margin:2px 6px 2px 0'>{_md(text)}</span>"
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


def _chip(col, label, value):
    """Компактная пара «подпись сверху / значение снизу» в конкретной
    колонке — не рисуется вовсе, если значение пустое (чтобы карточка не
    пестрела прочерками по незаполненным полям)."""
    if not value:
        return
    col.caption(label)
    col.write(_md(value))


def _okved_label(code):
    entry = next((o for o in okved_reference if o["code"] == code), None)
    return f"{code} — {entry['description']}" if entry else code


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

    st.markdown("###### Финансы — расчётный счёт")
    bank_account = st.text_input("Расчётный счёт", value=e.get("bank_account", ""), key=f"{prefix}_bankacc")
    b1, b2 = st.columns(2)
    bank_name = b1.text_input("Наименование банка", value=e.get("bank_name", ""), key=f"{prefix}_bankname")
    bank_inn = b2.text_input("ИНН банка", value=e.get("bank_inn", ""), key=f"{prefix}_bankinn")
    b3, b4 = st.columns(2)
    bank_bik = b3.text_input("БИК", value=e.get("bank_bik", ""), key=f"{prefix}_bankbik")
    bank_corr_account = b4.text_input("Корреспондентский счёт", value=e.get("bank_corr_account", ""), key=f"{prefix}_bankcorr")
    bank_address = st.text_input("Юридический адрес банка", value=e.get("bank_address", ""), key=f"{prefix}_bankaddr")

    st.markdown("###### ЭДО и ЭЦП")
    d1, d2, d3 = st.columns(3)
    edo_status = d1.selectbox(
        "Электронный документооборот", EDO_STATUSES,
        index=EDO_STATUSES.index(e["edo_status"]) if e.get("edo_status") in EDO_STATUSES else 1,
        key=f"{prefix}_edo",
    )
    esign_status = d2.selectbox(
        "Наличие ЭЦП", ESIGN_STATUSES,
        index=ESIGN_STATUSES.index(e["esign_status"]) if e.get("esign_status") in ESIGN_STATUSES else 1,
        key=f"{prefix}_esign",
    )
    try:
        esign_expiry_default = date.fromisoformat(e["esign_expiry"]) if e.get("esign_expiry") else None
    except Exception:  # noqa: BLE001
        esign_expiry_default = None
    esign_expiry = d3.date_input(
        "Срок годности токена", value=esign_expiry_default, format="DD.MM.YYYY", key=f"{prefix}_esignexp",
    )

    st.markdown("###### Виды деятельности (ОКВЭД)")
    if not OKVED_CODES:
        st.caption("Справочник ОКВЭД пуст — попроси добавить в него коды.")
        okved_main = e.get("okved_main", "")
        okved_additional = e.get("okved_additional", [])
    else:
        main_options = ["—"] + OKVED_CODES
        main_default = e.get("okved_main", "")
        okved_main_choice = st.selectbox(
            "Основной код ОКВЭД", main_options,
            index=main_options.index(main_default) if main_default in main_options else 0,
            format_func=lambda c: "—" if c == "—" else _okved_label(c),
            key=f"{prefix}_okvedmain",
        )
        okved_main = "" if okved_main_choice == "—" else okved_main_choice
        additional_default = [c for c in e.get("okved_additional", []) if c in OKVED_CODES and c != okved_main]
        okved_additional = st.multiselect(
            "Дополнительные коды ОКВЭД",
            [c for c in OKVED_CODES if c != okved_main],
            default=additional_default,
            format_func=_okved_label,
            key=f"{prefix}_okvedadd",
        )

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
        "bank_name": bank_name.strip(),
        "bank_inn": bank_inn.strip(),
        "bank_bik": bank_bik.strip(),
        "bank_corr_account": bank_corr_account.strip(),
        "bank_address": bank_address.strip(),
        "edo_status": edo_status,
        "esign_status": esign_status,
        "esign_expiry": esign_expiry.isoformat() if esign_expiry else "",
        "okved_main": okved_main,
        "okved_additional": okved_additional,
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
                continue

            # ---------------- Заголовок: название, статус, ЭДО/ЭЦП, кнопки ----------------
            head, edit_btn, del_btn = st.columns([7, 1, 1])
            head.markdown(f"### {_md(ent['name'])} · {_md(ent.get('type', ''))}")
            pills = []
            if ent.get("status"):
                pills.append(_pill(ent["status"], STATUS_COLORS.get(ent["status"], NEUTRAL)))
            if ent.get("edo_status") == "Подключён Диадок":
                pills.append(_pill("📄 ЭДО: Диадок", GOOD))
            else:
                pills.append(_pill("📄 ЭДО: нет", NEUTRAL))
            if ent.get("esign_status") == "Есть":
                exp = f" до {_fmt_date(ent['esign_expiry'])}" if ent.get("esign_expiry") else ""
                pills.append(_pill(f"🔏 ЭЦП{exp}", GOOD))
            else:
                pills.append(_pill("🔏 ЭЦП: нет", NEUTRAL))
            head.markdown("".join(pills), unsafe_allow_html=True)
            if edit_btn.button("✏️", key=f"entedit_{ent['id']}", help="Редактировать юрлицо", type="tertiary"):
                st.session_state["editing_entity_id"] = ent["id"]
                st.rerun()
            if del_btn.button("🗑", key=f"entdel_{ent['id']}", help="Удалить юрлицо", type="tertiary"):
                st.session_state["entities"] = [x for x in entities if x["id"] != ent["id"]]
                _persist()
                st.rerun()

            # ---------------- Идентификация ----------------
            id_cols = st.columns(4)
            _chip(id_cols[0], "ИНН", ent.get("inn"))
            _chip(id_cols[1], "ОГРН/ОГРНИП", ent.get("ogrn"))
            _chip(id_cols[2], "КПП", ent.get("kpp"))
            _chip(id_cols[3], "Дата регистрации", _fmt_date(ent.get("reg_date")))

            # ---------------- Налоги, владение, деятельность ----------------
            tax_cols = st.columns(4)
            _chip(tax_cols[0], "Система налогообложения", ent.get("tax_system"))
            _chip(tax_cols[1], "Ставка", ent.get("tax_rate"))
            _chip(tax_cols[2], "Доля владения", f"{ent['ownership_share']:.0f}%" if ent.get("ownership_share") else "")
            _chip(tax_cols[3], "Директор", ent.get("director"))
            if ent.get("other_founders"):
                st.caption("Прочие учредители")
                st.write(_md(ent["other_founders"]))

            if ent.get("okved_main") or ent.get("okved_additional"):
                st.caption("Виды деятельности (ОКВЭД)")
                lines = []
                if ent.get("okved_main"):
                    lines.append(f"**{_okved_label(ent['okved_main'])}**")
                lines.extend(_okved_label(c) for c in ent.get("okved_additional") or [])
                st.markdown("  \n".join(lines))

            # ---------------- Юридический адрес ----------------
            if any(ent.get(k) for k in ("address", "address_provider", "address_contact", "address_contract_end")):
                st.markdown("###### 📍 Юридический адрес")
                addr_cols = st.columns(4)
                _chip(addr_cols[0], "Адрес", ent.get("address"))
                _chip(addr_cols[1], "Подрядчик", ent.get("address_provider"))
                _chip(addr_cols[2], "Контакт", ent.get("address_contact"))
                _chip(addr_cols[3], "Окончание договора", _fmt_date(ent.get("address_contract_end")))

            # ---------------- Банковские реквизиты (свёрнуто) ----------------
            has_bank_info = any(
                ent.get(k) for k in
                ("bank_account", "bank_name", "bank_inn", "bank_bik", "bank_corr_account", "bank_address")
            )
            if has_bank_info:
                with st.expander("🏦 Банковские реквизиты"):
                    bank_cols1 = st.columns(2)
                    _chip(bank_cols1[0], "Расчётный счёт", ent.get("bank_account"))
                    _chip(bank_cols1[1], "Банк", ent.get("bank_name"))
                    bank_cols2 = st.columns(2)
                    _chip(bank_cols2[0], "ИНН банка", ent.get("bank_inn"))
                    _chip(bank_cols2[1], "БИК", ent.get("bank_bik"))
                    bank_cols3 = st.columns(2)
                    _chip(bank_cols3[0], "Корр. счёт", ent.get("bank_corr_account"))
                    _chip(bank_cols3[1], "Юр. адрес банка", ent.get("bank_address"))
