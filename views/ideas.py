import uuid
from datetime import date

import streamlit as st

from ideas_store import load_ideas, save_ideas

st.title("💡 Инвест-идеи")

if "ideas" not in st.session_state:
    st.session_state["ideas"] = load_ideas()

ideas = st.session_state["ideas"]


def _md(text):
    """Экранирует $ (иначе Streamlit примет за формулу) и сохраняет переносы строк."""
    return str(text or "").replace("$", r"\$").replace("\n", "  \n")


def _badge(text, bg="#eef2f9", color="#1a1a2e"):
    safe = str(text).replace("$", r"\$")
    return (
        f"<span style='display:inline-block;background:{bg};color:{color};"
        "padding:3px 12px;border-radius:14px;font-size:1rem;font-weight:600;"
        f"margin:2px 0 8px'>{safe}</span>"
    )


def _fmt_date(iso):
    try:
        return date.fromisoformat(iso).strftime("%d.%m.%Y")
    except Exception:  # noqa: BLE001
        return str(iso or "")


def _pros_cons(idea):
    c_pro, c_con = st.columns(2)
    with c_pro:
        st.markdown("**✅ Аргументы за**")
        st.markdown(_md(idea.get("pros")) or "—")
    with c_con:
        st.markdown("**⛔ Аргументы против**")
        st.markdown(_md(idea.get("cons")) or "—")


def _persist():
    save_ideas(st.session_state["ideas"])


active = [i for i in ideas if not i.get("done")]
done = [i for i in ideas if i.get("done")]

# --- Форма добавления ---
with st.expander("➕ Добавить идею", expanded=not active):
    with st.form("add_idea", clear_on_submit=True):
        name = st.text_input("Название идеи")
        col_pro, col_con = st.columns(2)
        pros = col_pro.text_area("Аргументы за", height=140)
        cons = col_con.text_area("Аргументы против", height=140)
        status = st.text_input("Текущий статус")
        submitted = st.form_submit_button("Добавить")
        if submitted:
            if name.strip():
                st.session_state["ideas"].append(
                    {
                        "id": str(uuid.uuid4()),
                        "name": name.strip(),
                        "pros": pros.strip(),
                        "cons": cons.strip(),
                        "status": status.strip(),
                    }
                )
                _persist()
                st.rerun()
            else:
                st.warning("Укажи название идеи.")

# --- Активные идеи ---
editing_id = st.session_state.get("editing_id")

if not active:
    st.info("Пока нет активных идей. Добавь через «➕ Добавить идею» выше.")
else:
    st.caption(f"Активных идей: {len(active)}")
    for idea in active:
        with st.container(border=True):
            if editing_id == idea["id"]:
                with st.form(f"edit_{idea['id']}"):
                    e_name = st.text_input("Название идеи", value=idea.get("name", ""))
                    ec_pro, ec_con = st.columns(2)
                    e_pros = ec_pro.text_area("Аргументы за", value=idea.get("pros", ""), height=140)
                    e_cons = ec_con.text_area("Аргументы против", value=idea.get("cons", ""), height=140)
                    e_status = st.text_input("Текущий статус", value=idea.get("status", ""))
                    b_save, b_cancel = st.columns(2)
                    if b_save.form_submit_button("💾 Сохранить"):
                        if e_name.strip():
                            idea.update(
                                name=e_name.strip(),
                                pros=e_pros.strip(),
                                cons=e_cons.strip(),
                                status=e_status.strip(),
                            )
                            _persist()
                            st.session_state["editing_id"] = None
                            st.rerun()
                        else:
                            st.warning("Укажи название идеи.")
                    if b_cancel.form_submit_button("Отмена"):
                        st.session_state["editing_id"] = None
                        st.rerun()
            else:
                head, done_btn, edit_btn, del_btn = st.columns([7, 1, 1, 1])
                head.markdown(f"### {_md(idea['name'])}")
                if idea.get("status"):
                    head.markdown(_badge(idea["status"]), unsafe_allow_html=True)
                if done_btn.button("✅", key=f"done_{idea['id']}", help="Отметить реализованной"):
                    idea["done"] = True
                    idea["done_at"] = date.today().isoformat()
                    _persist()
                    st.rerun()
                if edit_btn.button("✏️", key=f"edit_{idea['id']}", help="Редактировать идею"):
                    st.session_state["editing_id"] = idea["id"]
                    st.rerun()
                if del_btn.button("🗑", key=f"del_{idea['id']}", help="Удалить идею"):
                    st.session_state["ideas"] = [i for i in ideas if i["id"] != idea["id"]]
                    _persist()
                    st.rerun()
                _pros_cons(idea)

# --- История: реализованные идеи ---
if done:
    st.divider()
    st.subheader(f"✅ Реализованные идеи ({len(done)})")
    done_sorted = sorted(done, key=lambda i: i.get("done_at", ""), reverse=True)
    for idea in done_sorted:
        with st.container(border=True):
            head, back_btn, del_btn = st.columns([8, 1, 1])
            head.markdown(f"### {_md(idea['name'])}")
            badge_parts = []
            if idea.get("done_at"):
                head.markdown(
                    _badge(f"Реализовано {_fmt_date(idea['done_at'])}", bg="#e6f4ea", color="#1b5e20"),
                    unsafe_allow_html=True,
                )
            if idea.get("status"):
                head.caption(f"Статус на момент реализации: {idea['status']}")
            if back_btn.button("↩️", key=f"back_{idea['id']}", help="Вернуть в активные"):
                idea["done"] = False
                idea.pop("done_at", None)
                _persist()
                st.rerun()
            if del_btn.button("🗑", key=f"donedel_{idea['id']}", help="Удалить из истории"):
                st.session_state["ideas"] = [i for i in ideas if i["id"] != idea["id"]]
                _persist()
                st.rerun()
            _pros_cons(idea)
