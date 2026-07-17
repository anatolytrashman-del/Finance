"""Компактный виджет курса валют (bnb.by) для боковой панели.

Общий для всех страниц — чтобы курс RUB/USD и EUR/USD был под рукой везде,
где приходится вручную сводить рублёвые/евровые суммы к $, без похода на
bnb.by. Обновляется по кнопке, кэшируется локально (как курсы рынка
недвижимости) — не дёргает сайт при каждом клике по страницам."""
import streamlit as st

from bnb_rates import fetch_rates
from rates_store import load_rates, save_rates


def render_sidebar_rates():
    with st.sidebar:
        st.markdown("### Курс валют")
        if st.button("🔄 Обновить курс (bnb.by)", width="stretch", key="refresh_bnb_rates"):
            with st.spinner("Обновляю курс..."):
                rates, warning = fetch_rates()
            st.session_state.pop("rates_error", None)
            if rates:
                st.session_state["rates_cache"] = save_rates(rates)
            else:
                st.session_state["rates_error"] = warning
            st.rerun()

        if st.session_state.get("rates_error"):
            st.caption(f"⚠️ {st.session_state['rates_error']}")

        cache = st.session_state.get("rates_cache") or load_rates()
        if not cache:
            st.caption("Курс ещё не загружался.")
            return

        r = cache["rates"]
        rub_per_usd = 1 / r["usd_per_rub"]
        st.caption(f"USD/RUB: {rub_per_usd:,.2f}".replace(",", " "))
        st.caption(f"EUR/USD: {r['usd_per_eur']:.4f}")
        st.caption(f"на {cache['fetched_at']}")
