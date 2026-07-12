import uuid

import streamlit as st

from ideas_store import load_ideas, save_ideas

st.title("💡 Инвест-идеи")

if "ideas" not in st.session_state:
    st.session_state["ideas"] = load_ideas()

ideas = st.session_state["ideas"]


def _md(text):
    """Экранирует $ (иначе Streamlit примет за формулу) и сохраняет переносы строк."""
    return str(text or "").replace("$", r"\$").replace("\n", "  \n")


def _status_badge(status):
    safe = str(status).replace("$", r"\$")
    return (
        "<span style='display:inline-block;background:#eef2f9;color:#1a1a2e;"
        "padding:3px 12px;border-radius:14px;font-size:1rem;font-weight:600;"
        f"margin:2px 0 8px'>{safe}</span>"
    )


# --- Форма добавления ---
with st.expander("➕ Добавить идею", expanded=not ideas):
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
                save_ideas(st.session_state["ideas"])
                st.rerun()
            else:
                st.warning("Укажи название идеи.")

# --- Список идей ---
if not ideas:
    st.info("Пока нет идей. Добавь первую через «➕ Добавить идею» выше.")
else:
    st.caption(f"Идей: {len(ideas)}")
    editing_id = st.session_state.get("editing_id")

    for idea in ideas:
        with st.container(border=True):
            if editing_id == idea["id"]:
                # Режим редактирования
                with st.form(f"edit_{idea['id']}"):
                    e_name = st.text_input("Название идеи", value=idea.get("name", ""))
                    ec_pro, ec_con = st.columns(2)
                    e_pros = ec_pro.text_area("Аргументы за", value=idea.get("pros", ""), height=140)
                    e_cons = ec_con.text_area("Аргументы против", value=idea.get("cons", ""), height=140)
                    e_status = st.text_input("Текущий статус", value=idea.get("status", ""))
                    b_save, b_cancel = st.columns(2)
                    save = b_save.form_submit_button("💾 Сохранить")
                    cancel = b_cancel.form_submit_button("Отмена")
                    if save:
                        if e_name.strip():
                            idea["name"] = e_name.strip()
                            idea["pros"] = e_pros.strip()
                            idea["cons"] = e_cons.strip()
                            idea["status"] = e_status.strip()
                            save_ideas(st.session_state["ideas"])
                            st.session_state["editing_id"] = None
                            st.rerun()
                        else:
                            st.warning("Укажи название идеи.")
                    if cancel:
                        st.session_state["editing_id"] = None
                        st.rerun()
            else:
                # Режим просмотра
                head, edit_btn, del_btn = st.columns([8, 1, 1])
                head.markdown(f"### {_md(idea['name'])}")
                if idea.get("status"):
                    head.markdown(_status_badge(idea["status"]), unsafe_allow_html=True)
                if edit_btn.button("✏️", key=f"edit_{idea['id']}", help="Редактировать идею"):
                    st.session_state["editing_id"] = idea["id"]
                    st.rerun()
                if del_btn.button("🗑", key=f"del_{idea['id']}", help="Удалить идею"):
                    st.session_state["ideas"] = [i for i in ideas if i["id"] != idea["id"]]
                    save_ideas(st.session_state["ideas"])
                    st.rerun()

                c_pro, c_con = st.columns(2)
                with c_pro:
                    st.markdown("**✅ Аргументы за**")
                    st.markdown(_md(idea.get("pros")) or "—")
                with c_con:
                    st.markdown("**⛔ Аргументы против**")
                    st.markdown(_md(idea.get("cons")) or "—")
