"""Страница «Баланс» — как её вижу я.

Принцип: сверху выводы, снизу детали. Сначала пять чисел, по которым видно
состояние капитала за 5 секунд; потом динамика по всем месячным срезам книги;
потом структура (ликвидность и карта активов); потом автонаблюдения о рисках;
и только в конце — построчные таблицы для сверки.

Цвета — фиксированная категориальная палитра, проверенная на цветовую
слепоту (CVD) и контраст; полярность (рост/снижение) — синий/красный.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_source import load_balance, load_balance_history, sidebar_refresh_control
from parsers import balance_totals

sidebar_refresh_control()

st.title("⚖️ Баланс")

balance = load_balance()
if balance is None:
    st.info("Нажми «🔄 Обновить данные» в боковой панели, чтобы загрузить таблицу.")
    st.stop()

T = balance_totals(balance)
ASSETS = T["assets"] or 1.0
history = [h for h in (load_balance_history() or []) if h.get("assets")]

# --- палитра (категориальные слоты в фиксированном порядке + полярность) ---
C_BLUE, C_AQUA, C_YELLOW, C_GREEN, C_VIOLET, C_MAGENTA = (
    "#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e87ba4")
C_RED = "#e34948"   # только полярность «снижение», не серия
C_MUTED = "#898781"  # «вне учёта»
BLOCK_COLORS = {
    "Текущие счета": C_BLUE,
    "Возвраты": C_AQUA,
    "Займы": C_YELLOW,
    "Недвижимость": C_GREEN,
    "Искусство": C_VIOLET,
    "Бизнес": C_MAGENTA,  # красный слот пропущен: он занят полярностью «снижение»
}


def _usd(v, sign=False):
    if v is None:
        return "—"
    s = "-" if v < 0 else ("+" if sign and v > 0 else "")
    return f"{s}${abs(v):,.0f}".replace(",", " ")


def _md(text):
    """Экранирует $ для markdown (иначе Streamlit видит формулы)."""
    return text.replace("$", r"\$")


def _orig(it):
    if it["orig"] is None or not it["currency"] or it["currency"] == "$":
        return ""
    return f"{abs(it['orig']):,.0f} {it['currency']}".replace(",", " ")


# =========================== 1. Сводка ===========================
prev = history[-2] if len(history) >= 2 else None
delta_str = None
if prev and prev.get("net") is not None:
    delta_str = f"{T['net'] - prev['net']:+,.0f} $ с «{prev['sheet']}»".replace(",", " ")

m = st.columns(5)
m[0].metric("💼 Чистый капитал", _usd(T["net"]), delta=delta_str,
            help="Активы − обязательства. Замороженные бумаги не входят.")
m[1].metric("📊 Активы", _usd(T["assets"]))
m[2].metric("💧 Ликвидные", _usd(T["liquid"]), help="Счета, наличные, крипта — доступны сразу.")
m[3].metric("🧾 Обязательства", _usd(T["obligations"]))
m[4].metric("🔒 Заморожено", _usd(T["frozen"]), help="Заблокированные по санкциям бумаги — вне учёта.")

rates = balance.get("rates") or {}
caption = (f"Срез: {balance['sheet_name']} · EUR/USD {rates.get('eur', '—')}"
           f" · RUB/USD {rates.get('rub', '—')}")
grand_total = balance.get("grand_total")
if grand_total is not None and abs(grand_total - T["net"]) > 1:
    caption += (f" · ⚠️ «Итого» в таблице ({_usd(grand_total)}) расходится с расчётом"
                f" «активы − обязательства» на {_usd(abs(grand_total - T['net']))}")
st.caption(_md(caption))

# =========================== 2. Динамика ===========================
if len(history) >= 2:
    st.subheader("📈 Динамика капитала")
    hist_df = pd.DataFrame(history)
    hist_df["date"] = pd.to_datetime(hist_df["date"])

    tab_net, tab_delta = st.tabs(["Чистый капитал", "Изменение за месяц"])
    with tab_net:
        fig = go.Figure(go.Scatter(
            x=hist_df["date"], y=hist_df["net"], mode="lines+markers",
            line=dict(color=C_BLUE, width=2), marker=dict(size=8),
            hovertemplate="%{x|%d.%m.%Y}<br>Чистый капитал: $%{y:,.0f}<extra></extra>",
        ))
        fig.update_yaxes(rangemode="tozero", tickprefix="$", separatethousands=True, title=None)
        fig.update_xaxes(title=None)
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=20, b=10), showlegend=False)
        st.plotly_chart(fig, width="stretch")
    with tab_delta:
        deltas = hist_df["net"].diff().iloc[1:]
        fig = go.Figure(go.Bar(
            x=hist_df["date"].iloc[1:], y=deltas,
            marker_color=[C_BLUE if v >= 0 else C_RED for v in deltas],
            marker_cornerradius=4,
            text=[_usd(v, sign=True) for v in deltas], textposition="outside", cliponaxis=False,
            hovertemplate="%{x|%d.%m.%Y}<br>Изменение: %{text}<extra></extra>",
        ))
        fig.update_yaxes(tickprefix="$", separatethousands=True, title=None)
        fig.update_xaxes(title=None)
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10), showlegend=False)
        st.plotly_chart(fig, width="stretch")
else:
    st.caption("📈 График динамики появится, когда в книге будет ≥ 2 месячных срезов.")

# =========================== 3. Структура ===========================
st.subheader("🧩 Структура активов")
tab_liq, tab_map = st.tabs(["Лестница ликвидности", "Карта активов"])

with tab_liq:
    tiers = [
        ("💧 Мгновенная · счета, нал, крипта", T["liquid"], "#1c5cab"),
        ("⏳ Поступления · возвраты, займы", T["receivables"], "#3987e5"),
        ("🏛️ Долгосрочные · недвижимость, искусство, бизнес", T["longterm"], "#86b6ef"),
        ("🔒 Заморожено · вне учёта", T["frozen"], C_MUTED),
    ]
    labels = [t[0] for t in tiers]
    values = [t[1] for t in tiers]
    texts = [f"{_usd(v)} · {v / ASSETS:.0%}" if lbl[0] != "🔒" else _usd(v)
             for lbl, v in zip(labels, values)]
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=[t[2] for t in tiers], marker_cornerradius=4,
        text=texts, textposition="auto", cliponaxis=False,
        hovertemplate="%{y}<br>%{text}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(tickprefix="$", separatethousands=True, title=None)
    fig.update_layout(height=280, margin=dict(l=10, r=40, t=10, b=10), showlegend=False)
    st.plotly_chart(fig, width="stretch")
    st.caption("Чем светлее — тем дольше превращать в деньги. Серое — недоступно (санкции).")

with tab_map:
    ASSET_BLOCKS = [
        ("Текущие счета", balance["bank"] + balance["cash"] + balance["crypto"]),
        ("Возвраты", balance["returns"]),
        ("Займы", balance["loans"]),
        ("Недвижимость", balance["real_estate"]),
        ("Искусство", balance["art"]),
        ("Бизнес", balance["business"]),
    ]
    tree_rows = [
        {"Блок": block, "Актив": it["name"], "usd": it["usd"], "money": _usd(it["usd"])}
        for block, items in ASSET_BLOCKS for it in items if (it["usd"] or 0) > 0
    ]
    if tree_rows:
        tree_df = pd.DataFrame(tree_rows)
        fig = px.treemap(
            tree_df, path=[px.Constant("Активы"), "Блок", "Актив"], values="usd",
            color="Блок", color_discrete_map={**BLOCK_COLORS, "(?)": "#f0efec"},
            custom_data=["money"],
        )
        fig.update_traces(
            marker=dict(cornerradius=4),
            texttemplate="%{label}<br>%{customdata[0]}",
            hovertemplate="%{label}<br>%{customdata[0]} · %{percentRoot:.1%} активов<extra></extra>",
        )
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")

# =========================== 4. Наблюдения ===========================
notes = []
re_items = balance["real_estate"]
re_total = sum((i["usd"] or 0) for i in re_items)
if re_total:
    top = max(re_items, key=lambda i: i["usd"] or 0)
    notes.append(f"🏠 Недвижимость — {re_total / ASSETS:.0%} активов; "
                 f"крупнейший актив — «{top['name']}» ({(top['usd'] or 0) / ASSETS:.0%}).")
minsk_mir = [i for i in re_items if "минск мир" in i["name"].lower()]
if len(minsk_mir) >= 2:
    mm_sum = sum(i["usd"] for i in minsk_mir)
    notes.append(f"🏗️ {len(minsk_mir)} объекта(ов) «Минск Мир» на {_usd(mm_sum)} "
                 f"({mm_sum / ASSETS:.0%} активов) — концентрация на одном застройщике.")
rub_sum = sum((i["usd"] or 0)
              for key in ("bank", "cash", "crypto", "returns", "loans", "real_estate", "art", "business")
              for i in balance[key] if i["currency"] == "₽")
if rub_sum / ASSETS > 0.05:
    notes.append(f"₽ Рублёвые активы — {_usd(rub_sum)} ({rub_sum / ASSETS:.0%}): курсовой риск RUB/USD.")
obligations_abs = abs(T["obligations"])
if obligations_abs > 1:
    coverage = T["liquid"] / obligations_abs
    if coverage < 1:
        notes.append(f"💧 Ликвидные {_usd(T['liquid'])} покрывают лишь {coverage:.0%} обязательств "
                     f"({_usd(obligations_abs)}) — погашение потребует поступлений или продажи активов.")
    else:
        notes.append(f"💧 Ликвидные средства покрывают обязательства с запасом ({coverage:.1f}×).")
if T["frozen"] and T["net"]:
    notes.append(f"🔒 Разблокировка бумаг ({_usd(T['frozen'])}) добавила бы "
                 f"{T['frozen'] / T['net']:.0%} к капиталу.")
if T["receivables"]:
    notes.append(f"⏳ Ожидаемые поступления (возвраты и займы) — {_usd(T['receivables'])} "
                 f"({T['receivables'] / ASSETS:.0%} активов).")

if notes:
    with st.container(border=True):
        st.markdown("#### 🧭 Наблюдения")
        note_cols = st.columns(2)
        for i, note in enumerate(notes):
            note_cols[i % 2].markdown("- " + _md(note))

# =========================== 5. Детали ===========================
st.subheader("📋 Детали")

SHARE_CFG = st.column_config.ProgressColumn("Доля активов", format="%.1f%%", min_value=0, max_value=100)


def _items_df(groups):
    rows = []
    for group_label, items in groups:
        for it in items:
            rows.append({
                "Группа": group_label,
                "Актив": it["name"],
                "В $": _usd(it["usd"]),
                "Оригинал": _orig(it),
                "Доля": (it["usd"] or 0) / ASSETS * 100,
            })
    return pd.DataFrame(rows)


# связка «обязательство ↔ объект» по ключевым словам — чтобы показать «Оплачено»
_LINK_KEYS = ("апартамент", "машиномест", "кладов", "коммерческое помещение",
              "студия", "участок", "квартир")


def _link_key(name):
    low = str(name).lower()
    return next((k for k in _LINK_KEYS if k in low), None)


debt_by_key = {}
for ob in balance["obligations"]:
    key = _link_key(ob["name"])
    if key:
        debt_by_key[key] = debt_by_key.get(key, 0) + abs(ob["usd"] or 0)
asset_by_key = {}
for it in re_items:
    key = _link_key(it["name"])
    if key and key not in asset_by_key:
        asset_by_key[key] = it["name"]

left, right = st.columns([3, 2], gap="large")

with left:
    st.markdown(f"#### 💳 Ликвидные средства · {_md(_usd(T['liquid']))}")
    st.dataframe(
        _items_df([("🏦 Банк", balance["bank"]), ("💵 Наличные", balance["cash"]),
                   ("🪙 Крипта", balance["crypto"])]),
        width="stretch", hide_index=True, column_config={"Доля": SHARE_CFG},
    )

    st.markdown(f"#### ⏳ Ожидаемые поступления · {_md(_usd(T['receivables']))}")
    st.dataframe(
        _items_df([("↩️ Возврат", balance["returns"]), ("🤝 Займ", balance["loans"])]),
        width="stretch", hide_index=True, column_config={"Доля": SHARE_CFG},
    )

    st.markdown(f"#### 🏠 Недвижимость · {_md(_usd(re_total))}")
    re_df = pd.DataFrame([
        {
            "Объект": it["name"],
            "В $": _usd(it["usd"]),
            "Оригинал": _orig(it),
            "Оплачено": (max(0.0, min(100.0, (it["usd"] - debt_by_key.get(_link_key(it["name"]), 0))
                                      / it["usd"] * 100)) if it["usd"] else None),
            "Доля": (it["usd"] or 0) / ASSETS * 100,
        }
        for it in re_items
    ])
    st.dataframe(
        re_df, width="stretch", hide_index=True,
        column_config={
            "Доля": SHARE_CFG,
            "Оплачено": st.column_config.ProgressColumn("Оплачено", format="%.0f%%", min_value=0, max_value=100),
        },
    )

with right:
    st.markdown(f"#### 🧾 Обязательства · {_md(_usd(T['obligations']))}")
    obl_df = pd.DataFrame([
        {
            "Обязательство": ob["name"],
            "В $": _usd(-abs(ob["usd"] or 0)),
            "Оригинал": _orig(ob),
            "Объект": asset_by_key.get(_link_key(ob["name"]), "—"),
        }
        for ob in balance["obligations"]
    ])
    st.dataframe(obl_df, width="stretch", hide_index=True)

    st.markdown(f"#### 🎨 Искусство и бизнес · {_md(_usd(sum((i['usd'] or 0) for i in balance['art'] + balance['business'])))}")
    st.dataframe(
        _items_df([("🎨 Искусство", balance["art"]), ("🏢 Бизнес", balance["business"])]),
        width="stretch", hide_index=True, column_config={"Доля": SHARE_CFG},
    )

    st.markdown(f"#### 🔒 Вне учёта · {_md(_usd(T['frozen']))}")
    frozen_df = pd.DataFrame([
        {"Актив": "🔒 " + it["name"], "В $": _usd(it["usd"])}
        for it in balance["frozen"]
    ])
    st.dataframe(frozen_df, width="stretch", hide_index=True)
    st.caption("Заблокированные по санкциям бумаги: видим, помним, в капитал не считаем.")
