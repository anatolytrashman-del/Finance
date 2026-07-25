# ВРЕМЕННАЯ страница для сравнения стилей: тот же контент, что и в
# views/dashboard.py (Coinaco-стиль), но в визуальном языке Сделки
# (Bankio-стиль). Убрать эту страницу и её пункт меню в app.py, когда
# финальный стиль будет выбран.
import html
import textwrap
import uuid
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from balance_live import recalc_live_totals
from data_source import load_asset_allocation, load_balance, load_progress, sidebar_refresh_control
from events_store import load_events, save_events
from rates_store import load_rates as load_bnb_rates
from rates_widget import render_sidebar_rates

sidebar_refresh_control()
render_sidebar_rates()

CHART_OPTIONS = {
    "capital_usd": "Капитал, $",
    "debt": "Долговая нагрузка, $",
    "active_income": "Активный доход",
    "passive_income": "Пассивный доход",
}

if "events" not in st.session_state:
    st.session_state["events"] = load_events()

data = load_progress()
if data is None:
    st.title("📊 Дашборд капитала")
    st.info("Нажми «Обновить данные» в боковой панели, чтобы загрузить таблицу.")
    st.stop()
capital_usd = data.get("capital_usd", pd.DataFrame())
capital_rub = data.get("capital_rub", pd.DataFrame())
debt = data.get("debt", pd.DataFrame())


def _override_latest(df, live_value):
    if df is None or df.empty or live_value is None:
        return df
    df = df.sort_values("date").reset_index(drop=True).copy()
    df.loc[df.index[-1], "value"] = live_value
    return df


rates_cache = load_bnb_rates()
live_rates = rates_cache["rates"] if rates_cache else None
grand_total_live, obligations_total_live = recalc_live_totals(load_balance(), live_rates)

capital_usd = _override_latest(capital_usd, grand_total_live)
debt = _override_latest(debt, obligations_total_live)


def monthly_view(df):
    if df is None or df.empty:
        return df
    df = df.sort_values("date").reset_index(drop=True)
    keep = (df["date"].dt.day == 1) | (df["date"] == df["date"].iloc[-1])
    return df[keep].reset_index(drop=True)


def _fmt_point_value(v, unit="USD"):
    if v is None or pd.isna(v):
        return "—"
    sign = "-" if v < 0 else ""
    if unit == "USD":
        return f"{sign}${abs(v):,.0f}".replace(",", " ")
    if unit == "RUB":
        return f"{sign}{abs(v):,.0f} ₽".replace(",", " ")
    if unit == "%":
        return f"{v:.1f}%"
    return f"{sign}{abs(v):,.0f} {unit}".replace(",", " ")


def _overlay_events(fig, mv, chart_key):
    events = st.session_state.get("events") or []
    if mv is None or mv.empty:
        return
    mv = mv.sort_values("date").reset_index(drop=True)
    lo = mv["date"].min() - pd.Timedelta(days=31)
    hi = mv["date"].max() + pd.Timedelta(days=31)

    groups = {}
    for ev in events:
        if chart_key not in (ev.get("charts") or []):
            continue
        try:
            d = pd.to_datetime(ev["date"])
        except Exception:  # noqa: BLE001
            continue
        if d < lo or d > hi:
            continue
        idx = (mv["date"] - d).abs().idxmin()
        groups.setdefault(idx, []).append((d, ev.get("comment", "")))

    xs, ys, texts = [], [], []
    for idx, items in groups.items():
        items.sort(key=lambda it: it[0])
        point_date, point_value = mv.loc[idx, "date"], mv.loc[idx, "value"]
        header = f"<b>{point_date:%d.%m.%Y} · {_fmt_point_value(point_value, 'USD')}</b>"
        blocks = []
        for d, comment in items:
            wrapped = "<br>".join(textwrap.wrap(comment, width=44)) or "—"
            blocks.append(f"<i>{d:%d.%m.%Y}</i><br>{wrapped}")
        texts.append(header + "<br><br>" + "<br><br>".join(blocks))
        xs.append(point_date)
        ys.append(point_value)
    if xs:
        fig.add_scatter(
            x=xs, y=ys, mode="markers", name="События",
            marker=dict(symbol="circle", size=12, color="#4C7CF0",
                        line=dict(color="white", width=1.5)),
            customdata=texts, hovertemplate="📌 %{customdata}<extra></extra>",
            hoverlabel=dict(align="left"),
            showlegend=False, cliponaxis=False,
        )


def line_chart(df, y_label, color, chart_key=None):
    if df is None or df.empty:
        st.warning("Нет данных для отображения.")
        return
    df = monthly_view(df)
    fig = px.line(df, x="date", y="value", markers=True)
    fig.update_traces(
        line_color=color,
        customdata=df["value"].apply(lambda v: _fmt_point_value(v, y_label)),
        hovertemplate="<b>%{x|%d.%m.%Y}</b><br>%{customdata}<extra></extra>",
    )
    if chart_key:
        _overlay_events(fig, df, chart_key)
    fig.update_layout(
        xaxis_title=None,
        yaxis_title=y_label,
        margin=dict(l=10, r=10, t=10, b=10),
        height=280,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def capital_stats(df):
    df = monthly_view(df)
    if df is None or df.empty:
        return None
    latest_row = df.iloc[-1]
    latest_val, latest_date = latest_row["value"], latest_row["date"]
    stats = {"latest": latest_val, "month_delta": None, "month_pct": None, "year_delta": None, "year_pct": None}

    if len(df) > 1:
        prev_val = df.iloc[-2]["value"]
        stats["month_delta"] = latest_val - prev_val
        if prev_val:
            stats["month_pct"] = (latest_val - prev_val) / abs(prev_val) * 100

    past = df[df["date"] <= latest_date - pd.DateOffset(years=1)]
    if not past.empty:
        past_val = past.iloc[-1]["value"]
        stats["year_delta"] = latest_val - past_val
        if past_val:
            stats["year_pct"] = (latest_val - past_val) / abs(past_val) * 100

    return stats


def fmt_usd(v):
    sign = "+" if v >= 0 else "-"
    return f"{sign}${abs(v):,.0f}".replace(",", " ")


def fmt_rub_millions(v):
    return f"{v / 1_000_000:+.1f} млн"


def _esc(text):
    return html.escape(str(text))


# ============================ Bankio-style дизайн (эксперимент №3, для сравнения) ============================
# Тот же визуальный язык, что и на странице «Сделки» (см. views/deals.py) — просто
# применён к контенту Дашборда. Самостоятельная вёрстка, не завязана на theme.py.
BANKIO_DASH_CSS = """
<style>
.st-key-dash_bankio{
  background: linear-gradient(160deg, #dee8fc 0%, #eef2fd 55%, #eef2fd 100%);
  border-radius: 32px;
  padding: 28px 28px 26px;
}
.st-key-dash_bankio .bk-hero{display:flex;align-items:center;gap:14px;margin-bottom:20px}
.st-key-dash_bankio .bk-hero-icon{
  width:46px;height:46px;border-radius:15px;
  background:linear-gradient(135deg,#34D399,#10B981);
  display:flex;align-items:center;justify-content:center;font-size:22px;
  box-shadow:0 10px 20px -10px rgba(16,185,129,.6);
}
.st-key-dash_bankio .bk-hero-title{font-size:1.65rem;font-weight:800;color:#12121c;letter-spacing:-.01em}
.st-key-dash_bankio .bk-hero-sub{color:#7c828e;font-size:.88rem;margin-top:1px}

.bk-banner{display:inline-block;background:#fff;color:#12121c;padding:9px 16px;border-radius:14px;
  font-size:.82rem;font-weight:600;margin:2px 0 4px;box-shadow:0 3px 12px -6px rgba(20,20,40,.18)}
.bk-banner.neutral{background:rgba(255,255,255,.55);color:#5b6472;box-shadow:none}

.bk-card{border-radius:26px;padding:22px 22px 20px;height:100%;box-sizing:border-box}
.bk-card-white{background:#fff}
.bk-card-blue{background:#E4EDFC}
.bk-card-blue-strong{background:#D2E0FB}
.bk-card-green{background:#DCEEE3}
.bk-card-lavender{background:#EFF2FC}
.bk-card-title{font-size:1.02rem;font-weight:700;color:#12121c}
.bk-card-sub{color:#7c828e;font-size:.78rem;margin-top:2px}
.bk-big-number{font-size:2.15rem;font-weight:800;color:#12121c;letter-spacing:-.02em;margin:10px 0 2px}
.bk-big-number.secondary{font-size:1.5rem}

.bk-stat-row{display:flex;gap:26px;margin-top:14px;flex-wrap:wrap}
.bk-stat-label{font-size:.7rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#7c828e}
.bk-stat-pct{font-size:1rem;font-weight:800;margin-top:3px}
.bk-stat-pct.pos{color:#1b8f5a}
.bk-stat-pct.neg{color:#c0392b}
.bk-stat-pct.flat{color:#7c828e}
.bk-stat-amt{font-size:.74rem;color:#7c828e;margin-top:1px}

.bk-asset-row{display:flex;gap:12px;overflow-x:auto;padding-bottom:2px}
.bk-asset-card{background:#fff;border-radius:20px;padding:16px 18px;min-width:160px;flex:1 0 160px}
.bk-asset-head{display:flex;align-items:center;gap:10px}
.bk-asset-icon{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:15px;background:#EFF2FC;flex-shrink:0}
.bk-asset-name{font-weight:700;color:#12121c;font-size:.84rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bk-asset-value{font-size:1.2rem;font-weight:800;color:#12121c;margin-top:10px}
.bk-asset-pct{font-size:.74rem;font-weight:700;color:#1b8f5a;margin-top:2px}

.bk-tx-row{display:flex;align-items:center;justify-content:space-between;padding:9px 0;border-bottom:1px solid rgba(18,18,28,.08)}
.bk-tx-row:last-child{border-bottom:none}
.bk-tx-left{display:flex;align-items:center;gap:11px;min-width:0}
.bk-tx-icon{width:36px;height:36px;border-radius:50%;background:#EFF2FC;display:flex;align-items:center;
  justify-content:center;font-size:16px;flex-shrink:0}
.bk-tx-text{min-width:0}
.bk-tx-name{font-weight:700;color:#12121c;font-size:.85rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px}
.bk-tx-date{color:#7c828e;font-size:.72rem}
.bk-tx-sub{color:#7c828e;font-size:.72rem}
.bk-tx-amount{font-weight:700;font-size:.85rem;flex-shrink:0;padding-left:10px;text-align:right}
.bk-tx-amount.pos{color:#1b8f5a}
.bk-tx-amount.neg{color:#c0392b}

.bk-side-title{font-weight:700;font-size:1rem;color:#12121c;margin-bottom:14px}

.st-key-dash_bankio [class*="st-key-dash_bankio_chart_"]{background:#fff;border-radius:26px;padding:20px 20px 6px}
.st-key-dash_bankio [class*="st-key-dash_bankio_side_"]{background:#fff;border-radius:26px;padding:20px;margin-bottom:16px}
.st-key-dash_bankio [class*="st-key-dash_bankio_events_"]{background:#fff;border-radius:26px;padding:6px 20px 4px;margin-bottom:16px}
</style>
"""

ASSET_ICONS = {
    "недвижимость": "🏠", "акци": "📈", "облигаци": "📄", "займ": "🤝",
    "искусств": "🎨", "бизнес": "🏢", "наличн": "💵", "крипт": "🪙",
    "счет": "🏦", "счёт": "🏦", "возврат": "↩️",
}


def _asset_icon(name):
    low = str(name).lower()
    for key, icon in ASSET_ICONS.items():
        if key in low:
            return icon
    return "💠"


def _stat_block(label, delta_str, pct):
    if delta_str is None:
        return (
            f"<div><div class='bk-stat-label'>{_esc(label)}</div>"
            "<div class='bk-stat-pct flat'>нет данных</div></div>"
        )
    positive = pct is None or pct >= 0
    cls = "pos" if positive else "neg"
    arrow = "↑" if positive else "↓"
    pct_str = f"{arrow} {abs(pct):.1f}%" if pct is not None else ""
    return (
        f"<div><div class='bk-stat-label'>{_esc(label)}</div>"
        f"<div class='bk-stat-pct {cls}'>{_esc(pct_str)}</div>"
        f"<div class='bk-stat-amt'>{_esc(delta_str)}</div></div>"
    )


with st.container(key="dash_bankio"):
    st.markdown(BANKIO_DASH_CSS, unsafe_allow_html=True)

    st.markdown(
        "<div class='bk-hero'><div class='bk-hero-icon'>📊</div>"
        "<div><div class='bk-hero-title'>Дашборд капитала</div>"
        "<div class='bk-hero-sub'>Капитал, долговая нагрузка и доходы — в одном месте</div></div></div>",
        unsafe_allow_html=True,
    )

    if grand_total_live is not None:
        st.markdown(
            f"<div class='bk-banner'>💱 «Капитал, $» и «Долговая нагрузка» пересчитаны по курсу "
            f"bnb.by на {_esc(rates_cache['fetched_at'])}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='bk-banner neutral'>💡 Курс bnb.by ещё не обновлялся — «сегодня» "
            "показано по цифрам из таблицы.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    main_col, side_col = st.columns([2.1, 1])

    with main_col:
        # ---------------- Hero: Капитал $ (основной) + Капитал ₽ (компактно) ----------------
        usd_stats = capital_stats(capital_usd)
        rub_stats = capital_stats(capital_rub)

        hero_c1, hero_c2 = st.columns([1.4, 1])
        with hero_c1:
            latest_usd = f"${usd_stats['latest']:,.0f}".replace(",", " ") if usd_stats else "—"
            if usd_stats:
                m_val, m_pct = usd_stats["month_delta"], usd_stats["month_pct"]
                m_str = fmt_usd(m_val) if m_val is not None else None
                y_val, y_pct = usd_stats["year_delta"], usd_stats["year_pct"]
                y_str = fmt_usd(y_val) if y_val is not None else None
            else:
                m_str = m_pct = y_str = y_pct = None
            st.markdown(
                "<div class='bk-card bk-card-blue-strong'>"
                "<div class='bk-card-title'>Капитал, $</div>"
                f"<div class='bk-big-number'>{_esc(latest_usd)}</div>"
                "<div class='bk-stat-row'>"
                f"{_stat_block('За месяц', m_str, m_pct)}"
                f"{_stat_block('За год', y_str, y_pct)}"
                "</div>"
                "</div>",
                unsafe_allow_html=True,
            )
        with hero_c2:
            latest_rub = f"{rub_stats['latest'] / 1_000_000:.1f} млн ₽" if rub_stats else "—"
            if rub_stats:
                rm_val, rm_pct = rub_stats["month_delta"], rub_stats["month_pct"]
                rm_str = fmt_rub_millions(rm_val) if rm_val is not None else None
            else:
                rm_str = rm_pct = None
            st.markdown(
                "<div class='bk-card bk-card-blue'>"
                "<div class='bk-card-title'>Капитал, ₽</div>"
                f"<div class='bk-big-number secondary'>{_esc(latest_rub)}</div>"
                "<div class='bk-stat-row'>"
                f"{_stat_block('За месяц', rm_str, rm_pct)}"
                "</div>"
                "</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        # ---------------- Структура капитала — карточки-активы ----------------
        allocation = load_asset_allocation()
        if allocation.empty:
            st.warning("Не нашёл помесячный срез с разбивкой по активам.")
        else:
            total_alloc = allocation["Сумма"].sum()
            cards_html = ""
            for _, row in allocation.sort_values("Сумма", ascending=False).iterrows():
                name = row["Категория"]
                amt = row["Сумма"]
                pct = (amt / total_alloc * 100) if total_alloc else 0
                cards_html += (
                    "<div class='bk-asset-card'>"
                    "<div class='bk-asset-head'>"
                    f"<div class='bk-asset-icon'>{_asset_icon(name)}</div>"
                    f"<div class='bk-asset-name'>{_esc(name)}</div>"
                    "</div>"
                    f"<div class='bk-asset-value'>{_esc(_fmt_point_value(amt, 'USD'))}</div>"
                    f"<div class='bk-asset-pct'>{pct:.1f}% портфеля</div>"
                    "</div>"
                )
            st.markdown(f"<div class='bk-asset-row'>{cards_html}</div>", unsafe_allow_html=True)
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        # ---------------- События ----------------
        with st.container(key="dash_bankio_events_card"):
            st.markdown("<div class='bk-side-title' style='padding-top:14px'>📌 События на графиках</div>", unsafe_allow_html=True)
            events = st.session_state["events"]
            with st.expander(f"➕ Добавить / список ({len(events)})"):
                st.caption("Отмечают особые решения. Появляются меткой на выбранных графиках, "
                           "при наведении — дата и текст.")
                with st.form("add_event", clear_on_submit=True):
                    ec1, ec2 = st.columns([1, 3])
                    ev_date = ec1.date_input("Дата", value=date.today(), format="DD.MM.YYYY")
                    ev_comment = ec2.text_input("Комментарий")
                    ev_charts = st.multiselect(
                        "На каких графиках показать",
                        options=list(CHART_OPTIONS), format_func=lambda k: CHART_OPTIONS[k],
                        default=["capital_usd"],
                    )
                    if st.form_submit_button("Добавить событие"):
                        if ev_comment.strip() and ev_charts:
                            events.append({
                                "id": str(uuid.uuid4()), "date": ev_date.isoformat(),
                                "comment": ev_comment.strip(), "charts": ev_charts,
                            })
                            save_events(events)
                            st.rerun()
                        else:
                            st.warning("Заполни комментарий и выбери хотя бы один график.")

                if events:
                    for ev in sorted(events, key=lambda e: e.get("date", ""), reverse=True):
                        tc1, tc2, tc3 = st.columns([6, 3, 1])
                        charts_str = ", ".join(CHART_OPTIONS.get(k, k) for k in ev.get("charts", []))
                        try:
                            date_str = pd.to_datetime(ev["date"]).strftime("%d.%m.%Y")
                        except Exception:  # noqa: BLE001
                            date_str = str(ev.get("date", ""))
                        tc1.markdown(
                            "<div class='bk-tx-left'><div class='bk-tx-icon'>📌</div>"
                            f"<div><div class='bk-tx-name'>{_esc(ev.get('comment', ''))}</div>"
                            f"<div class='bk-tx-sub'>{_esc(charts_str)}</div></div></div>",
                            unsafe_allow_html=True,
                        )
                        tc2.markdown(f"<div class='bk-tx-date'>{_esc(date_str)}</div>", unsafe_allow_html=True)
                        if tc3.button("🗑", key=f"ev_del_{ev['id']}", help="Удалить событие"):
                            st.session_state["events"] = [x for x in events if x["id"] != ev["id"]]
                            save_events(st.session_state["events"])
                            st.rerun()

        st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)

        # ---------------- Графики ----------------
        gc1, gc2 = st.columns(2)
        with gc1:
            with st.container(key="dash_bankio_chart_capusd"):
                st.markdown("<div class='bk-side-title'>💵 Капитал, $</div>", unsafe_allow_html=True)
                line_chart(capital_usd, "USD", "#4C7CF0", chart_key="capital_usd")
        with gc2:
            with st.container(key="dash_bankio_chart_caprub"):
                st.markdown("<div class='bk-side-title'>💰 Капитал, ₽</div>", unsafe_allow_html=True)
                line_chart(capital_rub, "RUB", "#1565C0")

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        gc3, gc4 = st.columns(2)
        with gc3:
            with st.container(key="dash_bankio_chart_debt"):
                st.markdown("<div class='bk-side-title'>📉 Долговая нагрузка, $</div>", unsafe_allow_html=True)
                st.caption("Значения без даты в исходной таблице пропущены")
                line_chart(debt, "USD", "#c0392b", chart_key="debt")
        with gc4:
            with st.container(key="dash_bankio_chart_leverage"):
                st.markdown("<div class='bk-side-title'>⚖️ Долг / капитал, %</div>", unsafe_allow_html=True)
                if not debt.empty and not capital_usd.empty:
                    merged = pd.merge(capital_usd, debt, on="date", suffixes=("_cap", "_debt"))
                    merged = monthly_view(merged)
                    if merged.empty:
                        st.warning("Нет пересекающихся дат для расчёта.")
                    else:
                        merged["leverage"] = -merged["value_debt"] / merged["value_cap"] * 100
                        fig = px.line(merged, x="date", y="leverage", markers=True)
                        fig.update_traces(
                            line_color="#f59e0b",
                            customdata=merged["leverage"].apply(lambda v: _fmt_point_value(v, "%")),
                            hovertemplate="<b>%{x|%d.%m.%Y}</b><br>%{customdata}<extra></extra>",
                        )
                        fig.update_layout(
                            xaxis_title=None, yaxis_title="%",
                            margin=dict(l=10, r=10, t=10, b=10), height=280,
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        )
                        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                else:
                    st.warning("Нет данных для отображения.")

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        gc5, gc6 = st.columns(2)
        with gc5:
            with st.container(key="dash_bankio_chart_active"):
                st.markdown("<div class='bk-side-title'>💼 Активный доход, $</div>", unsafe_allow_html=True)
                line_chart(data.get("active_income"), "USD", "#1565C0", chart_key="active_income")
        with gc6:
            with st.container(key="dash_bankio_chart_passive"):
                st.markdown("<div class='bk-side-title'>🌿 Пассивный доход, $</div>", unsafe_allow_html=True)
                line_chart(data.get("passive_income"), "USD", "#6A1B9A", chart_key="passive_income")

    with side_col:
        # ---------------- Долг / капитал (текущее значение, без гейджа — карточка-цифра) ----------------
        with st.container(key="dash_bankio_side_leverage"):
            st.markdown("<div class='bk-side-title'>⚖️ Риск: долг / капитал</div>", unsafe_allow_html=True)
            leverage_now, leverage_prev = None, None
            if not debt.empty and not capital_usd.empty:
                merged = pd.merge(capital_usd, debt, on="date", suffixes=("_cap", "_debt"))
                merged = monthly_view(merged)
                if not merged.empty:
                    merged["leverage"] = -merged["value_debt"] / merged["value_cap"] * 100
                    leverage_now = merged.iloc[-1]["leverage"]
                    if len(merged) > 1:
                        leverage_prev = merged.iloc[-2]["leverage"]
            if leverage_now is None:
                st.markdown("<div class='bk-card-sub'>Нет данных.</div>", unsafe_allow_html=True)
            else:
                if leverage_now < 15:
                    risk_label, risk_color = "Низкий риск", "#1b8f5a"
                elif leverage_now < 35:
                    risk_label, risk_color = "Умеренный риск", "#f59e0b"
                else:
                    risk_label, risk_color = "Высокий риск", "#c0392b"
                prev_line = f"<div class='bk-card-sub'>Месяц назад: {leverage_prev:.1f}%</div>" if leverage_prev is not None else ""
                st.markdown(
                    f"<div class='bk-big-number' style='color:{risk_color}'>{leverage_now:.1f}%</div>"
                    f"<div class='bk-card-sub' style='color:{risk_color};font-weight:700'>{_esc(risk_label)}</div>"
                    f"{prev_line}",
                    unsafe_allow_html=True,
                )

        # ---------------- Прирост капитала по годам ----------------
        with st.container(key="dash_bankio_side_movers"):
            st.markdown("<div class='bk-side-title'>📊 Прирост по годам</div>", unsafe_allow_html=True)
            if capital_usd.empty:
                st.markdown("<div class='bk-card-sub'>Нет данных.</div>", unsafe_allow_html=True)
            else:
                yearly = (
                    capital_usd.assign(Год=capital_usd["date"].dt.year)
                    .groupby("Год", as_index=False)["value"].last()
                )
                yearly["Прирост"] = yearly["value"].diff()
                yearly["Прирост_pct"] = yearly["value"].pct_change() * 100
                yearly = yearly.dropna(subset=["Прирост"]).sort_values("Прирост_pct", ascending=False)
                if yearly.empty:
                    st.markdown("<div class='bk-card-sub'>Недостаточно данных.</div>", unsafe_allow_html=True)
                else:
                    rows_html = ""
                    for _, r in yearly.iterrows():
                        pos = r["Прирост"] >= 0
                        cls = "pos" if pos else "neg"
                        rows_html += (
                            "<div class='bk-tx-row'>"
                            "<div class='bk-tx-left'>"
                            f"<div class='bk-tx-icon'>{int(r['Год']) % 100}</div>"
                            f"<div class='bk-tx-name'>{int(r['Год'])}</div>"
                            "</div>"
                            f"<div class='bk-tx-amount {cls}'>{_esc(_fmt_point_value(r['Прирост'], 'USD'))}"
                            f"<div class='bk-tx-sub' style='text-align:right'>{abs(r['Прирост_pct']):.1f}%</div></div>"
                            "</div>"
                        )
                    st.markdown(rows_html, unsafe_allow_html=True)
