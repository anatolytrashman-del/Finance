import pandas as pd
import streamlit as st

from data_source import load_balance, sidebar_refresh_control
from rates_widget import render_sidebar_rates

sidebar_refresh_control()
render_sidebar_rates()

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


def _cat_table(rows, frozen=False):
    """rows: список (категория, item). Компактная таблица с колонкой «Категория»."""
    if not rows:
        st.caption("Нет строк.")
        return
    table = pd.DataFrame(
        [
            {
                "Категория": cat,
                "Актив": ("🔒 " + it["name"]) if frozen else it["name"],
                "В $": _fmt_usd(it["usd"]),
                "Оригинал": _fmt_orig(it["orig"], it["currency"]),
            }
            for cat, it in rows
        ]
    )
    st.dataframe(table, width="stretch", hide_index=True)


def _block(title, icon, rows, frozen=False):
    total = sum((it["usd"] or 0) for _, it in rows)
    st.markdown(f"#### {icon} {title} · {_fmt_usd(total)}")
    _cat_table(rows, frozen=frozen)
    return total


# ---------------- Верхняя сводка ----------------
frozen_total = _subtotal(balance["frozen"])
obligations_total = balance["obligations_total"]
if obligations_total is None:
    obligations_total = _subtotal(balance["obligations"])

m1, m2, m3 = st.columns(3)
m1.metric("💼 Итого капитал", _fmt_usd(balance["grand_total"]))
m2.metric("🧾 Обязательства", _fmt_usd(obligations_total))
m3.metric("🔒 Заморожено (вне учёта)", _fmt_usd(frozen_total))

# ---------------- Состав капитала: компактный бар с процентами ----------------
composition = {
    "Текущие счета": _subtotal(balance["bank"] + balance["cash"] + balance["crypto"]),
    "Возвраты": _subtotal(balance["returns"]),
    "Займы": _subtotal(balance["loans"]),
    "Недвижимость": _subtotal(balance["real_estate"]),
    "Искусство": _subtotal(balance["art"]),
    "Бизнес": _subtotal(balance["business"]),
}
composition = {k: v for k, v in composition.items() if v > 0}
comp_total = sum(composition.values())
if composition:
    comp_df = pd.DataFrame(
        [
            {"Блок": k, "Сумма": _fmt_usd(v), "Доля": (v / comp_total * 100) if comp_total else 0}
            for k, v in sorted(composition.items(), key=lambda kv: -kv[1])
        ]
    )
    st.dataframe(
        comp_df,
        width="stretch",
        hide_index=True,
        column_config={
            "Доля": st.column_config.ProgressColumn("Доля", format="%.1f%%", min_value=0, max_value=100),
        },
    )

st.divider()

# ---------------- Текущие счета ----------------
current_rows = (
    [("Банк", it) for it in balance["bank"]]
    + [("Наличные", it) for it in balance["cash"]]
    + [("Крипта", it) for it in balance["crypto"]]
)
with st.container(border=True):
    _block("Текущие счета", "💳", current_rows)

# ---------------- Возвраты ----------------
with st.container(border=True):
    _block("Возвраты", "↩️", [("Возврат", it) for it in balance["returns"]])

# ---------------- Инвестиции ----------------
invest_rows = (
    [("Займы", it) for it in balance["loans"]]
    + [("Недвижимость", it) for it in balance["real_estate"]]
    + [("Искусство", it) for it in balance["art"]]
)
with st.container(border=True):
    _block("Инвестиции", "📈", invest_rows)
    if balance["frozen"]:
        st.markdown(f"###### 🔒 Фондовый рынок (вне баланса) · {_fmt_usd(frozen_total)}")
        _cat_table([("Заблокировано", it) for it in balance["frozen"]], frozen=True)
        st.caption("Заблокированные по санкциям бумаги — показаны, но не входят в баланс.")

# ---------------- Баланс бизнеса ----------------
with st.container(border=True):
    _block("Баланс бизнеса", "🏢", [("Бизнес", it) for it in balance["business"]])

# ---------------- Обязательства ----------------
st.divider()
with st.container(border=True):
    _block("Обязательства", "🧾", [("Обязательство", it) for it in balance["obligations"]])

# ---------------- Итого по портфелю ----------------
st.divider()
st.markdown("### 💼 Итого по портфелю")
f1, f2, f3 = st.columns(3)
f1.metric("Капитал", _fmt_usd(balance["grand_total"]))
f2.metric("Обязательства", _fmt_usd(obligations_total))
f3.metric("Заморожено (вне учёта)", _fmt_usd(frozen_total))
