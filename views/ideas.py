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
    for idea in ideas:
        with st.container(border=True):
            head, btn = st.columns([9, 1])
            head.markdown(f"### {_md(idea['name'])}")
            if idea.get("status"):
                head.caption(f"Статус: {idea['status']}")
            if btn.button("🗑", key=f"del_{idea['id']}", help="Удалить идею"):
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
