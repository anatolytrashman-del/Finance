import pandas as pd
import plotly.express as px
import streamlit as st

from data_source import load_balance, sidebar_refresh_control

sidebar_refresh_control()

st.title("⚖️ Баланс")

balance = load_balance()
if balance is None:
    st.info("Нажми «🔄 Обновить данные» в боковой панели, чтобы загрузить таблицу.")
    st.stop()

st.caption(f"Данные на срез: {balance['sheet_name']}")


def _fmt_usd(v):
    if v is None:
        return "—"
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.0f}".replace(",", " ")


def _fmt_orig(orig, currency):
    if orig is None or not currency or currency == "$":
        return ""
    return f"{abs(orig):,.0f} {currency}".replace(",", " ")


def _subtotal(items):
    return sum((it["usd"] or 0) for it in items)


def _block_table(items, frozen=False):
    """Таблица блока: Актив · В $ · Оригинал."""
    if not items:
        st.caption("Нет строк.")
        return
    table = pd.DataFrame(
        [
            {
                "Актив": ("🔒 " + it["name"]) if frozen else it["name"],
                "В $": _fmt_usd(it["usd"]),
                "Оригинал": _fmt_orig(it["orig"], it["currency"]),
            }
            for it in items
        ]
    )
    st.dataframe(table, width="stretch", hide_index=True)


def _subheader(title, items):
    st.markdown(f"**{title}** · {_fmt_usd(_subtotal(items))}")
    _block_table(items)


# ---------------- Верхняя сводка ----------------
frozen_total = _subtotal(balance["frozen"])
obligations_total = balance["obligations_total"]
if obligations_total is None:
    obligations_total = _subtotal(balance["obligations"])

m1, m2, m3 = st.columns(3)
m1.metric("💼 Итого капитал", _fmt_usd(balance["grand_total"]))
m2.metric("🧾 Обязательства", _fmt_usd(obligations_total))
m3.metric("🔒 Заморожено (вне учёта)", _fmt_usd(frozen_total))

# ---------------- Диаграмма состава активов ----------------
composition = {
    "Текущие счета": _subtotal(balance["bank"] + balance["cash"] + balance["crypto"]),
    "Возвраты": _subtotal(balance["returns"]),
    "Займы": _subtotal(balance["loans"]),
    "Недвижимость": _subtotal(balance["real_estate"]),
    "Искусство": _subtotal(balance["art"]),
    "Бизнес": _subtotal(balance["business"]),
}
composition = {k: v for k, v in composition.items() if v > 0}
if composition:
    comp_df = pd.DataFrame({"Блок": list(composition), "Сумма": list(composition.values())})
    fig = px.pie(comp_df, names="Блок", values="Сумма", hole=0.55)
    fig.update_traces(textposition="inside", texttemplate="%{label}<br>%{percent}")
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=380, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------- Текущие счета ----------------
current = balance["bank"] + balance["cash"] + balance["crypto"]
st.header(f"💳 Текущие счета · {_fmt_usd(_subtotal(current))}")
_subheader("Банковские счета", balance["bank"])
_subheader("Наличные", balance["cash"])
_subheader("Криптовалюта", balance["crypto"])

# ---------------- Возвраты ----------------
st.header(f"↩️ Возвраты · {_fmt_usd(_subtotal(balance['returns']))}")
_block_table(balance["returns"])

# ---------------- Инвестиции ----------------
invest = balance["loans"] + balance["real_estate"] + balance["art"]
st.header(f"📈 Инвестиции · {_fmt_usd(_subtotal(invest))}")
_subheader("Займы", balance["loans"])
_subheader("Недвижимость", balance["real_estate"])

st.markdown("**Фондовый рынок**")
_block_table(balance["frozen"], frozen=True)
st.caption(f"🔒 Заблокированные по санкциям бумаги ({_fmt_usd(frozen_total)}) — показаны, но не входят в баланс.")

_subheader("Искусство и коллекционирование", balance["art"])

# ---------------- Баланс бизнеса ----------------
st.header(f"🏢 Баланс бизнеса · {_fmt_usd(_subtotal(balance['business']))}")
_block_table(balance["business"])

# ---------------- Обязательства ----------------
st.divider()
st.header(f"🧾 Обязательства · {_fmt_usd(obligations_total)}")
_block_table(balance["obligations"])
