import html
import textwrap
import uuid
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from balance_live import recalc_live_totals
from data_source import load_asset_allocation, load_balance, load_progress, sidebar_refresh_control
from events_store import load_events, save_events
from rates_store import load_rates as load_bnb_rates
from rates_widget import render_sidebar_rates

sidebar_refresh_control()
render_sidebar_rates()

# Графики, к которым можно привязывать события-комментарии
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
    """Возвращает копию df с последней по дате точкой, заменённой на
    live_value. История (все точки до неё) не трогается, и ничего не
    пишется обратно в Google-таблицу — подмена только для показа."""
    if df is None or df.empty or live_value is None:
        return df
    df = df.sort_values("date").reset_index(drop=True).copy()
    df.loc[df.index[-1], "value"] = live_value
    return df


# --- «Сегодня» по факту: последняя точка капитала и долга пересчитывается по
# текущему курсу bnb.by (см. balance_live.py) — вся история на графиках и
# сама Google-таблица остаются нетронутыми.
rates_cache = load_bnb_rates()
live_rates = rates_cache["rates"] if rates_cache else None
grand_total_live, obligations_total_live = recalc_live_totals(load_balance(), live_rates)

capital_usd = _override_latest(capital_usd, grand_total_live)
debt = _override_latest(debt, obligations_total_live)


def monthly_view(df):
    """Помесячный взгляд на серию: показания за 1-е число месяца + самое
    последнее показание как отдельная самостоятельная точка. Промежуточные
    внутримесячные отчёты (не 1-е число и не последний) пропускаются."""
    if df is None or df.empty:
        return df
    df = df.sort_values("date").reset_index(drop=True)
    keep = (df["date"].dt.day == 1) | (df["date"] == df["date"].iloc[-1])
    return df[keep].reset_index(drop=True)


def _fmt_point_value(v, unit="USD"):
    """Человеко-читаемое значение точки для тултипа графика — вместо сырого
    plotly-формата ('date=May 1, 2024', 'value=120')."""
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
    """Ставит маркеры-точки событий на линию (привязка к ближайшему замеру).

    Несколько событий, попавших на одну и ту же точку графика, объединяются
    в ОДИН маркер с одним всплывающим окном — иначе точки рисуются друг на
    друге и наведение показывает только верхнюю. В тултипе показывается и
    значение графика в этой точке, не только текст события.

    События вне диапазона ряда (± ~месяц) пропускаются."""
    events = st.session_state.get("events") or []
    if mv is None or mv.empty:
        return
    mv = mv.sort_values("date").reset_index(drop=True)
    lo = mv["date"].min() - pd.Timedelta(days=31)
    hi = mv["date"].max() + pd.Timedelta(days=31)

    groups = {}  # idx ближайшей точки -> список (дата события, комментарий)
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
            marker=dict(symbol="circle", size=12, color="#F0532D",
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
    """Последнее значение + изменение за месяц и за год (сумма и %).

    Считаем по помесячному ряду (1-е число + последнее самостоятельное
    показание): «за месяц» — от последнего доступного 1-го числа, «за год» —
    от 1-го числа примерно год назад, а не «12 строчек назад»."""
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
    """HTML-экранирование для значений, вставляемых в сырые HTML-блоки —
    это блочный HTML, а не markdown-текст, так что $ там не читается как
    LaTeX, а вот < и & — небезопасны."""
    return html.escape(str(text))


# ============================ Coinaco-style дизайн (эксперимент №2) ============================
# Самостоятельная вёрстка под второй референс-скриншот — не завязана на theme.py,
# откат = один `git revert` этого коммита, без побочных эффектов на другие страницы.
COINACO_CSS = """
<style>
.st-key-dash_coinaco{background:#EFEDE8;border-radius:28px;padding:26px 26px 24px}
.st-key-dash_coinaco .cn-hero-title{font-size:1.9rem;font-weight:700;color:#17171C;letter-spacing:-.01em}
.st-key-dash_coinaco .cn-hero-sub{color:#8b8d98;font-size:.88rem;margin-top:2px}

.cn-card{background:#fff;border-radius:20px;padding:22px;box-sizing:border-box;height:100%}
.cn-label{font-size:.72rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#9a9ca6}
.cn-big-number{font-size:2.5rem;font-weight:800;color:#17171C;letter-spacing:-.02em;margin-top:6px}
.cn-big-number.secondary{font-size:1.7rem}

.cn-hero-flex{display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap}
.cn-pnl-row{display:flex;gap:30px;flex-wrap:wrap}
.cn-pnl-label{font-size:.68rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#9a9ca6}
.cn-pnl-pct{font-size:1.1rem;font-weight:800;margin-top:3px}
.cn-pnl-pct.pos{color:#1DBF73}
.cn-pnl-pct.neg{color:#E5484D}
.cn-pnl-pct.flat{color:#9a9ca6}
.cn-pnl-amt{font-size:.76rem;color:#9a9ca6;margin-top:1px}

.cn-asset-row{display:flex;gap:14px;overflow-x:auto;padding-bottom:2px}
.cn-asset-card{background:#fff;border-radius:18px;padding:16px 18px;min-width:170px;flex:1 0 170px}
.cn-asset-head{display:flex;align-items:center;gap:10px}
.cn-asset-icon{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:15px;background:#F1EFEA;flex-shrink:0}
.cn-asset-name{font-weight:700;color:#17171C;font-size:.85rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cn-asset-value{font-size:1.3rem;font-weight:800;color:#17171C;margin-top:10px}
.cn-asset-pct{font-size:.76rem;font-weight:700;color:#1DBF73;margin-top:2px}

.cn-tx-left{display:flex;align-items:center;gap:12px;padding:6px 0}
.cn-tx-icon{width:36px;height:36px;border-radius:50%;background:#F1EFEA;display:flex;
  align-items:center;justify-content:center;font-size:15px;flex-shrink:0}
.cn-tx-name{font-weight:700;color:#17171C;font-size:.85rem}
.cn-tx-sub{color:#9a9ca6;font-size:.72rem;margin-top:1px}
.cn-tx-date{color:#9a9ca6;font-size:.8rem;padding:14px 0;text-align:right}

.cn-side-title{font-weight:700;font-size:1rem;color:#17171C;margin-bottom:14px}

.cn-mover-row{display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #F1EFEA}
.cn-mover-row:last-child{border-bottom:none}
.cn-mover-left{display:flex;align-items:center;gap:10px}
.cn-mover-icon{width:30px;height:30px;border-radius:50%;background:#F1EFEA;display:flex;
  align-items:center;justify-content:center;font-size:.76rem;font-weight:800;color:#17171C}
.cn-mover-name{font-weight:700;font-size:.83rem;color:#17171C}
.cn-mover-value{text-align:right}
.cn-mover-amount{font-weight:700;font-size:.83rem;color:#17171C}
.cn-mover-pct{font-size:.76rem;font-weight:700}
.cn-mover-pct.pos{color:#1DBF73}
.cn-mover-pct.neg{color:#E5484D}

.cn-risk-label{text-align:center;font-weight:700;font-size:.95rem;margin-top:-6px}
.cn-risk-sub{text-align:center;color:#9a9ca6;font-size:.75rem;margin-top:2px}

.st-key-dash_coinaco [class*="st-key-dash_coinaco_chart_"]{background:#fff;border-radius:20px;padding:20px 20px 6px}
.st-key-dash_coinaco [class*="st-key-dash_coinaco_side_"]{background:#fff;border-radius:20px;padding:20px;margin-bottom:16px;height:100%;box-sizing:border-box}
.st-key-dash_coinaco [class*="st-key-dash_coinaco_side_"] [data-testid="stVerticalBlock"]{height:100%}
.st-key-dash_coinaco [class*="st-key-dash_coinaco_events_"]{background:#fff;border-radius:20px;padding:6px 20px 4px;margin-bottom:16px}
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


def _pnl_block(label, delta_str, pct):
    if delta_str is None:
        return (
            f"<div><div class='cn-pnl-label'>{_esc(label)}</div>"
            "<div class='cn-pnl-pct flat'>нет данных</div></div>"
        )
    positive = pct is None or pct >= 0
    cls = "pos" if positive else "neg"
    arrow = "↑" if positive else "↓"
    pct_str = f"{arrow} {abs(pct):.1f}%" if pct is not None else ""
    return (
        f"<div><div class='cn-pnl-label'>{_esc(label)}</div>"
        f"<div class='cn-pnl-pct {cls}'>{_esc(pct_str)}</div>"
        f"<div class='cn-pnl-amt'>{_esc(delta_str)}</div></div>"
    )


with st.container(key="dash_coinaco"):
    st.markdown(COINACO_CSS, unsafe_allow_html=True)

    if grand_total_live is not None:
        date_part, _, time_part = str(rates_cache["fetched_at"]).partition(" ")
        update_text = f"Последнее обновление — {date_part} в {time_part}" if time_part else \
            f"Последнее обновление — {date_part}"
    else:
        update_text = "Курс bnb.by ещё не обновлялся"
    st.markdown(
        "<div style='display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap'>"
        "<div><div class='cn-hero-title'>Дашборд капитала</div>"
        "<div class='cn-hero-sub'>Капитал, долговая нагрузка и доходы — в одном месте</div></div>"
        f"<div class='cn-hero-sub' style='text-align:right'>{_esc(update_text)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    # ---------------- Hero: Капитал $ (основной) + Капитал ₽ (компактно) ----------------
    usd_stats = capital_stats(capital_usd)
    rub_stats = capital_stats(capital_rub)

    hero_c1, hero_c2 = st.columns(2)
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
            "<div class='cn-card'>"
            "<div class='cn-hero-flex'>"
            "<div><div class='cn-label'>Капитал, $</div>"
            f"<div class='cn-big-number'>{_esc(latest_usd)}</div></div>"
            "<div class='cn-pnl-row'>"
            f"{_pnl_block('За месяц', m_str, m_pct)}"
            f"{_pnl_block('За год', y_str, y_pct)}"
            "</div>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with hero_c2:
        latest_rub = f"{rub_stats['latest'] / 1_000_000:.1f} млн ₽" if rub_stats else "—"
        if rub_stats:
            rm_val, rm_pct = rub_stats["month_delta"], rub_stats["month_pct"]
            rm_str = fmt_rub_millions(rm_val) if rm_val is not None else None
            ry_val, ry_pct = rub_stats["year_delta"], rub_stats["year_pct"]
            ry_str = fmt_rub_millions(ry_val) if ry_val is not None else None
        else:
            rm_str = rm_pct = ry_str = ry_pct = None
        st.markdown(
            "<div class='cn-card'>"
            "<div class='cn-hero-flex'>"
            "<div><div class='cn-label'>Капитал, ₽</div>"
            f"<div class='cn-big-number secondary'>{_esc(latest_rub)}</div></div>"
            "<div class='cn-pnl-row'>"
            f"{_pnl_block('За месяц', rm_str, rm_pct)}"
            f"{_pnl_block('За год', ry_str, ry_pct)}"
            "</div>"
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
                "<div class='cn-asset-card'>"
                "<div class='cn-asset-head'>"
                f"<div class='cn-asset-icon'>{_asset_icon(name)}</div>"
                f"<div class='cn-asset-name'>{_esc(name)}</div>"
                "</div>"
                f"<div class='cn-asset-value'>{_esc(_fmt_point_value(amt, 'USD'))}</div>"
                f"<div class='cn-asset-pct'>{pct:.1f}% портфеля</div>"
                "</div>"
            )
        st.markdown(f"<div class='cn-asset-row'>{cards_html}</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ---------------- События — в стиле списка «Transactions» ----------------
    with st.container(key="dash_coinaco_events_card"):
        st.markdown("<div class='cn-side-title' style='padding-top:14px'>📌 События на графиках</div>", unsafe_allow_html=True)
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
                        "<div class='cn-tx-left'><div class='cn-tx-icon'>📌</div>"
                        f"<div><div class='cn-tx-name'>{_esc(ev.get('comment', ''))}</div>"
                        f"<div class='cn-tx-sub'>{_esc(charts_str)}</div></div></div>",
                        unsafe_allow_html=True,
                    )
                    tc2.markdown(f"<div class='cn-tx-date'>{_esc(date_str)}</div>", unsafe_allow_html=True)
                    if tc3.button("🗑", key=f"ev_del_{ev['id']}", help="Удалить событие"):
                        st.session_state["events"] = [x for x in events if x["id"] != ev["id"]]
                        save_events(st.session_state["events"])
                        st.rerun()

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ---------------- Риск: долг/капитал + Прирост по годам — рядом, компактно ----------------
    risk_col, movers_col = st.columns(2)

    with risk_col:
        with st.container(key="dash_coinaco_side_gauge"):
            st.markdown("<div class='cn-side-title'>⚖️ Риск: долг / капитал</div>", unsafe_allow_html=True)
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
                st.markdown("<div class='cn-risk-sub' style='margin:20px 0'>Нет данных.</div>", unsafe_allow_html=True)
            else:
                axis_max = max(leverage_now * 1.4, 40)
                if leverage_now < 15:
                    risk_label, risk_color = "Низкий риск", "#1DBF73"
                elif leverage_now < 35:
                    risk_label, risk_color = "Умеренный риск", "#F5A623"
                else:
                    risk_label, risk_color = "Высокий риск", "#E5484D"

                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=leverage_now,
                    number={"suffix": "%", "font": {"size": 22, "color": "#17171C"}},
                    gauge={
                        "axis": {"range": [0, axis_max], "visible": False},
                        "bar": {"color": "rgba(0,0,0,0)"},
                        "bgcolor": "rgba(0,0,0,0)",
                        "borderwidth": 0,
                        "steps": [
                            {"range": [0, axis_max * 0.35], "color": "#1DBF73"},
                            {"range": [axis_max * 0.35, axis_max * 0.7], "color": "#F5A623"},
                            {"range": [axis_max * 0.7, axis_max], "color": "#E5484D"},
                        ],
                        # Стрелка-указатель на середину «зелёной» (безопасной) зоны —
                        # целевой ориентир по риску, не текущее значение (его показывают
                        # дуга и число). Родная часть polar-координат гейджа, поэтому
                        # масштабируется вместе с ним корректно при любой ширине карточки.
                        "threshold": {
                            "line": {"color": "#17171C", "width": 4},
                            "thickness": 0.9,
                            "value": axis_max * 0.175,
                        },
                    },
                ))
                fig.update_layout(margin=dict(l=10, r=10, t=6, b=0), height=100, paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                st.markdown(f"<div class='cn-risk-label' style='color:{risk_color}'>{_esc(risk_label)}</div>", unsafe_allow_html=True)
                if leverage_prev is not None:
                    st.markdown(
                        f"<div class='cn-risk-sub'>Месяц назад: {leverage_prev:.1f}%</div>",
                        unsafe_allow_html=True,
                    )

    with movers_col:
        with st.container(key="dash_coinaco_side_movers"):
            st.markdown("<div class='cn-side-title'>📊 Прирост по годам</div>", unsafe_allow_html=True)
            if capital_usd.empty:
                st.markdown("<div class='cn-risk-sub'>Нет данных.</div>", unsafe_allow_html=True)
            else:
                yearly = (
                    capital_usd.assign(Год=capital_usd["date"].dt.year)
                    .groupby("Год", as_index=False)["value"].last()
                )
                yearly["Прирост"] = yearly["value"].diff()
                yearly["Прирост_pct"] = yearly["value"].pct_change() * 100
                yearly = yearly.dropna(subset=["Прирост"]).sort_values("Год", ascending=False)
                if yearly.empty:
                    st.markdown("<div class='cn-risk-sub'>Недостаточно данных.</div>", unsafe_allow_html=True)
                else:
                    rows_html = ""
                    for _, r in yearly.iterrows():
                        pos = r["Прирост"] >= 0
                        cls = "pos" if pos else "neg"
                        arrow = "↗" if pos else "↘"
                        rows_html += (
                            "<div class='cn-mover-row'>"
                            "<div class='cn-mover-left'>"
                            f"<div class='cn-mover-icon'>{int(r['Год']) % 100}</div>"
                            f"<div class='cn-mover-name'>{int(r['Год'])}</div>"
                            "</div>"
                            "<div class='cn-mover-value'>"
                            f"<div class='cn-mover-amount'>{_esc(_fmt_point_value(r['Прирост'], 'USD'))}</div>"
                            f"<div class='cn-mover-pct {cls}'>{arrow} {abs(r['Прирост_pct']):.1f}%</div>"
                            "</div>"
                            "</div>"
                        )
                    st.markdown(rows_html, unsafe_allow_html=True)

    st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)

    # ---------------- Графики — на всю ширину страницы ----------------
    gc1, gc2 = st.columns(2)
    with gc1:
        with st.container(key="dash_coinaco_chart_capusd"):
            st.markdown("<div class='cn-side-title'>💵 Капитал, $</div>", unsafe_allow_html=True)
            line_chart(capital_usd, "USD", "#16A34A", chart_key="capital_usd")
    with gc2:
        with st.container(key="dash_coinaco_chart_caprub"):
            st.markdown("<div class='cn-side-title'>💰 Капитал, ₽</div>", unsafe_allow_html=True)
            line_chart(capital_rub, "RUB", "#1565C0")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    gc3, gc4 = st.columns(2)
    with gc3:
        with st.container(key="dash_coinaco_chart_debt"):
            st.markdown("<div class='cn-side-title'>📉 Долговая нагрузка, $</div>", unsafe_allow_html=True)
            st.caption("Значения без даты в исходной таблице пропущены")
            line_chart(debt, "USD", "#E5484D", chart_key="debt")
    with gc4:
        with st.container(key="dash_coinaco_chart_leverage"):
            st.markdown("<div class='cn-side-title'>⚖️ Долг / капитал, %</div>", unsafe_allow_html=True)
            if not debt.empty and not capital_usd.empty:
                merged = pd.merge(capital_usd, debt, on="date", suffixes=("_cap", "_debt"))
                merged = monthly_view(merged)
                if merged.empty:
                    st.warning("Нет пересекающихся дат для расчёта.")
                else:
                    merged["leverage"] = -merged["value_debt"] / merged["value_cap"] * 100
                    fig = px.line(merged, x="date", y="leverage", markers=True)
                    fig.update_traces(
                        line_color="#F5A623",
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
        with st.container(key="dash_coinaco_chart_active"):
            st.markdown("<div class='cn-side-title'>💼 Активный доход, $</div>", unsafe_allow_html=True)
            line_chart(data.get("active_income"), "USD", "#1565C0", chart_key="active_income")
    with gc6:
        with st.container(key="dash_coinaco_chart_passive"):
            st.markdown("<div class='cn-side-title'>🌿 Пассивный доход, $</div>", unsafe_allow_html=True)
            line_chart(data.get("passive_income"), "USD", "#6A1B9A", chart_key="passive_income")
