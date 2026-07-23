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
ESIGN_STATUSES = ["Есть", "Требуется продление"]

STATUS_COLORS = {
    "Действует": ("#e6f4ea", "#1b5e20"),
    "Требуется ликвидация": ("#fdecea", "#b3261e"),
}
STATUS_ICONS = {"Действует": "✅", "Требуется ликвидация": "⚠️"}
GOOD = ("#e6f4ea", "#1b5e20")
NEUTRAL = ("#f1f1f4", "#5f6368")
DANGER = ("#fdecea", "#b3261e")


def _md(text):
    return str(text or "").replace("$", r"\$")


def _pill(text, colors):
    bg, color = colors
    return (
        f"<span style='display:inline-block;background:{bg};color:{color};"
        "padding:4px 14px;border-radius:16px;font-size:0.8rem;font-weight:600;"
        "letter-spacing:.01em;box-shadow:0 1px 2px rgba(0,0,0,.06);"
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


def _chip(col, label, value, icon=""):
    """Компактное поле «подпись сверху / значение снизу» — не рисуется
    вовсе, если значение пустое (чтобы карточка не пестрела прочерками по
    незаполненным полям)."""
    if not value:
        return
    prefix = f"{icon} " if icon else ""
    col.markdown(
        "<div style='margin-bottom:12px'>"
        f"<div style='font-size:0.72rem;font-weight:600;color:#8a8fa3;"
        f"text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px'>{prefix}{_md(label)}</div>"
        f"<div style='font-size:0.95rem;font-weight:600;color:#1a1a2e'>{_md(value)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _block_title(text):
    st.markdown(f"<div style='font-weight:700;font-size:0.95rem;margin-bottom:8px'>{text}</div>", unsafe_allow_html=True)


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

            # ---------------- Заголовок: название, статусы, кнопки ----------------
            is_ip = ent.get("type") == "ИП"
            head, edit_btn, del_btn = st.columns([7, 1, 1])
            head.markdown(f"### {_md(ent['name'])}")
            pills = []
            if ent.get("status"):
                icon = STATUS_ICONS.get(ent["status"], "")
                pills.append(_pill(f"{icon} {ent['status']}".strip(), STATUS_COLORS.get(ent["status"], NEUTRAL)))
            if ent.get("edo_status") == "Подключён Диадок":
                pills.append(_pill("📄 ЭДО: Диадок", GOOD))
            else:
                pills.append(_pill("📄 ЭДО: нет", NEUTRAL))
            if ent.get("esign_status") == "Есть":
                exp = f" до {_fmt_date(ent['esign_expiry'])}" if ent.get("esign_expiry") else ""
                pills.append(_pill(f"🔏 ЭЦП{exp}", GOOD))
            else:
                pills.append(_pill("🔏 ЭЦП: требуется продление", DANGER))
            head.markdown("".join(pills), unsafe_allow_html=True)
            if edit_btn.button("✏️", key=f"entedit_{ent['id']}", help="Редактировать юрлицо", type="tertiary"):
                st.session_state["editing_entity_id"] = ent["id"]
                st.rerun()
            if del_btn.button("🗑", key=f"entdel_{ent['id']}", help="Удалить юрлицо", type="tertiary"):
                st.session_state["entities"] = [x for x in entities if x["id"] != ent["id"]]
                _persist()
                st.rerun()

            # ---------------- Превью: самое важное, видно сразу ----------------
            prev_cols = st.columns(4)
            _chip(prev_cols[0], "ИНН", ent.get("inn"), "🆔")
            _chip(prev_cols[1], "ОГРН/ОГРНИП", ent.get("ogrn"), "📋")
            _chip(prev_cols[2], "Юр. адрес", ent.get("address"), "📍")
            _chip(prev_cols[3], "Расчётный счёт", ent.get("bank_account"), "💳")

            # ---------------- Подробности: остальное — под спойлером, по блокам ----------------
            with st.expander("Подробнее"):
                shown = {"v": False}

                def _sep():
                    if shown["v"]:
                        st.divider()
                    shown["v"] = True

                # КПП (только ООО) + дата регистрации
                _sep()
                _block_title("📋 Реквизиты")
                req_pairs = []
                if not is_ip:
                    req_pairs.append(("КПП", ent.get("kpp")))
                req_pairs.append(("Дата регистрации", _fmt_date(ent.get("reg_date"))))
                req_cols = st.columns(len(req_pairs))
                for col, (label, value) in zip(req_cols, req_pairs):
                    _chip(col, label, value)

                # Юридический адрес — детали (сам адрес уже в превью)
                if any(ent.get(k) for k in ("address_provider", "address_contact", "address_contract_end")):
                    _sep()
                    _block_title("📍 Юридический адрес")
                    addr_pairs = [
                        ("Подрядчик", ent.get("address_provider")),
                        ("Контакт", ent.get("address_contact")),
                        ("Окончание договора", _fmt_date(ent.get("address_contract_end"))),
                    ]
                    addr_cols = st.columns(3)
                    for col, (label, value) in zip(addr_cols, addr_pairs):
                        _chip(col, label, value)

                # Банк — детали (расчётный счёт уже в превью)
                if any(ent.get(k) for k in ("bank_name", "bank_inn", "bank_bik", "bank_corr_account", "bank_address")):
                    _sep()
                    _block_title("🏦 Банк")
                    bank_pairs1 = [("Банк", ent.get("bank_name")), ("ИНН банка", ent.get("bank_inn"))]
                    bank_cols1 = st.columns(2)
                    for col, (label, value) in zip(bank_cols1, bank_pairs1):
                        _chip(col, label, value)
                    bank_pairs2 = [("БИК", ent.get("bank_bik")), ("Корр. счёт", ent.get("bank_corr_account"))]
                    bank_cols2 = st.columns(2)
                    for col, (label, value) in zip(bank_cols2, bank_pairs2):
                        _chip(col, label, value)
                    if ent.get("bank_address"):
                        _chip(st, "Юр. адрес банка", ent.get("bank_address"))

                # Налоги
                if ent.get("tax_system") or ent.get("tax_rate"):
                    _sep()
                    _block_title("💰 Налоги")
                    tax_pairs = [("Система налогообложения", ent.get("tax_system")), ("Ставка", ent.get("tax_rate"))]
                    tax_cols = st.columns(2)
                    for col, (label, value) in zip(tax_cols, tax_pairs):
                        _chip(col, label, value)

                # Владение и управление — не имеет смысла для ИП
                if not is_ip and (ent.get("ownership_share") or ent.get("director") or ent.get("other_founders")):
                    _sep()
                    _block_title("👥 Владение и управление")
                    own_pairs = [
                        ("Доля владения", f"{ent['ownership_share']:.0f}%" if ent.get("ownership_share") else ""),
                        ("Директор", ent.get("director")),
                    ]
                    own_cols = st.columns(2)
                    for col, (label, value) in zip(own_cols, own_pairs):
                        _chip(col, label, value)
                    if ent.get("other_founders"):
                        _chip(st, "Прочие учредители", ent.get("other_founders"))

                # Виды деятельности (ОКВЭД)
                if ent.get("okved_main") or ent.get("okved_additional"):
                    _sep()
                    _block_title("🏷️ Виды деятельности (ОКВЭД)")
                    lines = []
                    if ent.get("okved_main"):
                        lines.append(f"**{_okved_label(ent['okved_main'])}**")
                    lines.extend(_okved_label(c) for c in ent.get("okved_additional") or [])
                    st.markdown("  \n".join(lines))
