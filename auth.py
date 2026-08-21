"""Пароль на вход — единственный слой защиты поверх «случайного» URL на Fly.io.

Пароль задаётся переменной окружения APP_PASSWORD (на Fly.io — `fly secrets set`,
локально — необязательно). Если она не задана, гейт пропускает всех без пароля,
но показывает предупреждение — это ок для локального запуска на своей машине,
но НЕЛЬЗЯ разворачивать так в облаке."""
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
        st.warning(
            "⚠️ Пароль не настроен (APP_PASSWORD) — приложение открыто без защиты. "
            "Обязательно настрой пароль перед тем, как разворачивать это в облаке.",
            icon="⚠️",
        )
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
