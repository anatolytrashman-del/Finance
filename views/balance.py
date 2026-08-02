import pandas as pd
import streamlit as st

from data_source import load_balance, sidebar_refresh_control
from rates_widget import render_sidebar_rates
from theme import card, kpi_card, kpi_row, page, section_title

sidebar_refresh_control()
render_sidebar_rates()

balance = load_balance()
if balance is None:
    st.title("⚖️ Баланс")
    st.info("Нажми «🔄 Обновить данные» в боковой панели, чтобы загрузить таблицу.")
    st.stop()


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


def _block(page_key, suffix, title, icon, rows, frozen=False):
    total = sum((it["usd"] or 0) for _, it in rows)
    with card(page_key, suffix):
        section_title(f"{icon} {title} · {_fmt_usd(total)}")
        _cat_table(rows, frozen=frozen)
    return total


frozen_total = _subtotal(balance["frozen"])
obligations_total = balance["obligations_total"]
if obligations_total is None:
    obligations_total = _subtotal(balance["obligations"])

with page("balance", "⚖️", "Баланс", f"Данные на срез: {balance['sheet_name']}"):
    # ---------------- Верхняя сводка ----------------
    kpi_row([
        kpi_card("💼", "Итого капитал", _fmt_usd(balance["grand_total"]), icon_bg="#ecfdf5"),
        kpi_card("🧾", "Обязательства", _fmt_usd(obligations_total), icon_bg="#fef2f2"),
        kpi_card("🔒", "Заморожено (вне учёта)", _fmt_usd(frozen_total), icon_bg="#f3f4f6"),
    ])

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
        with card("balance", "composition"):
            section_title("📊 Состав капитала")
            st.dataframe(
                comp_df,
                width="stretch",
                hide_index=True,
                column_config={
                    "Доля": st.column_config.ProgressColumn("Доля", format="%.1f%%", min_value=0, max_value=100),
                },
            )

    # ---------------- Текущие счета ----------------
    current_rows = (
        [("Банк", it) for it in balance["bank"]]
        + [("Наличные", it) for it in balance["cash"]]
        + [("Крипта", it) for it in balance["crypto"]]
    )
    _block("balance", "current", "Текущие счета", "💳", current_rows)

    # ---------------- Возвраты ----------------
    _block("balance", "returns", "Возвраты", "↩️", [("Возврат", it) for it in balance["returns"]])

    # ---------------- Инвестиции ----------------
    invest_rows = (
        [("Займы", it) for it in balance["loans"]]
        + [("Недвижимость", it) for it in balance["real_estate"]]
        + [("Искусство", it) for it in balance["art"]]
    )
    with card("balance", "invest"):
        section_title(f"📈 Инвестиции · {_fmt_usd(sum((it['usd'] or 0) for _, it in invest_rows))}")
        _cat_table(invest_rows)
        if balance["frozen"]:
            st.markdown(f"###### 🔒 Фондовый рынок (вне баланса) · {_fmt_usd(frozen_total)}")
            _cat_table([("Заблокировано", it) for it in balance["frozen"]], frozen=True)
            st.caption("Заблокированные по санкциям бумаги — показаны, но не входят в баланс.")

    # ---------------- Баланс бизнеса ----------------
    _block("balance", "business", "Баланс бизнеса", "🏢", [("Бизнес", it) for it in balance["business"]])

    # ---------------- Обязательства ----------------
    _block("balance", "obligations", "Обязательства", "🧾", [("Обязательство", it) for it in balance["obligations"]])

    # ---------------- Итого по портфелю ----------------
    st.divider()
    section_title("💼 Итого по портфелю")
    kpi_row([
        kpi_card("💼", "Капитал", _fmt_usd(balance["grand_total"]), icon_bg="#ecfdf5"),
        kpi_card("🧾", "Обязательства", _fmt_usd(obligations_total), icon_bg="#fef2f2"),
        kpi_card("🔒", "Заморожено (вне учёта)", _fmt_usd(frozen_total), icon_bg="#f3f4f6"),
    ])
