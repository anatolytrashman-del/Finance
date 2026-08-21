"""Пароль на вход — для локального запуска на своей машине не нужен (снаружи
приложение всё равно недоступно). Если когда-нибудь будешь разворачивать это
в облаке — задай переменную окружения APP_PASSWORD, и гейт включится сам."""
import hmac
import os

import streamlit as st

SESSION_KEY = "authed"


def _expected_password():
    if os.environ.get("APP_PASSWORD"):
        return os.environ["APP_PASSWORD"]
    try:
        return st.secrets.get("APP_PASSWORD", None)
    except Exception:  # noqa: BLE001 — нет secrets.toml вообще, это ок
        return None


def require_password():
    expected = _expected_password()
    if not expected:
        return

    if st.session_state.get(SESSION_KEY):
        return

    st.markdown("## 🔒 Trashman Family Office")
    with st.form("login_form"):
        pwd = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти")
    if submitted:
        if hmac.compare_digest(pwd, expected):
            st.session_state[SESSION_KEY] = True
            st.rerun()
        else:
            st.error("Неверный пароль.")
    st.stop()
