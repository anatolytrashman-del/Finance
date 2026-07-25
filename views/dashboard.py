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


def _esc(text):
    """HTML-экранирование для значений, вставляемых в сырые HTML-блоки (карточки,
    баннер) — это блочный HTML, а не markdown-текст, так что $ там не читается
    как LaTeX, а вот < и & — небезопасны."""
    return html.escape(str(text))


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

    Несколько событий, попавших на одну и ту же точку графика (например,
    два события через день — оба ближе всего к одному и тому же месячному
    замеру), объединяются в ОДИН маркер с одним всплывающим окном — иначе
    точки рисуются друг на друге и наведение показывает только верхнюю
    (тот же приём, что группировка объектов в одном доме на карте
    в real_estate.py). В тултипе показывается и значение графика в этой
    точке, не только текст события.

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
            # переносим длинный комментарий по словам, чтобы тултип не обрезался
            wrapped = "<br>".join(textwrap.wrap(comment, width=44)) or "—"
            blocks.append(f"<i>{d:%d.%m.%Y}</i><br>{wrapped}")
        texts.append(header + "<br><br>" + "<br><br>".join(blocks))
        xs.append(point_date)
        ys.append(point_value)
    if xs:
        fig.add_scatter(
            x=xs, y=ys, mode="markers", name="События",
            marker=dict(symbol="circle", size=12, color="#EF6C00",
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
        height=320,
    )
    st.plotly_chart(fig, use_container_width=True)


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


def _delta_row(label, delta_str, pct):
    if delta_str is None:
        return (
            f"<div class='tfo-kpi-delta-row'><span class='tfo-kpi-delta-label'>{_esc(label)}</span>"
            "<span class='tfo-kpi-delta-empty'>нет данных</span></div>"
        )
    positive = pct is None or pct >= 0
    color = "#16a34a" if positive else "#dc2626"
    arrow = "↑" if positive else "↓"
    pct_part = f" {arrow} {abs(pct):.1f}%" if pct is not None else ""
    return (
        f"<div class='tfo-kpi-delta-row'><span class='tfo-kpi-delta-label'>{_esc(label)}</span>"
        f"<span class='tfo-kpi-delta-value' style='color:{color}'>{_esc(delta_str)}{_esc(pct_part)}</span></div>"
    )


def _capital_kpi_html(icon, label, df, fmt_value, fmt_delta):
    stats = capital_stats(df)
    if stats is None:
        return (
            f"<div class='tfo-kpi'><div class='tfo-kpi-icon'>{icon}</div>"
            f"<div class='tfo-kpi-label'>{_esc(label)}</div>"
            "<div style='color:#9ca3af;font-size:.9rem'>Нет данных</div></div>"
        )
    month = _delta_row("За месяц", fmt_delta(stats["month_delta"]) if stats["month_delta"] is not None else None, stats["month_pct"])
    year = _delta_row("За год", fmt_delta(stats["year_delta"]) if stats["year_delta"] is not None else None, stats["year_pct"])
    return (
        "<div class='tfo-kpi'>"
        f"<div class='tfo-kpi-icon'>{icon}</div>"
        f"<div class='tfo-kpi-label'>{_esc(label)}</div>"
        f"<div class='tfo-kpi-value'>{_esc(fmt_value(stats['latest']))}</div>"
        f"<div class='tfo-kpi-deltas'>{month}{year}</div>"
        "</div>"
    )


GREEN_PALETTE = ["#059669", "#84CC16", "#0D9488", "#65A30D", "#10B981", "#4D7C0F", "#2DD4BF", "#3F6212"]

# ============================ Дизайн-система страницы ============================
PAGE_CSS = """
<style>
.st-key-dash_futuristic{ --grad: linear-gradient(135deg, #059669 0%, #22C55E 55%, #A3E635 100%); }

.st-key-dash_futuristic .tfo-hero{display:flex;align-items:center;gap:16px;margin:2px 0 20px}
.st-key-dash_futuristic .tfo-hero-icon{
  width:56px;height:56px;border-radius:16px;background:var(--grad);
  display:flex;align-items:center;justify-content:center;font-size:26px;
  box-shadow:0 10px 28px -10px rgba(34,197,94,.55);
}
.st-key-dash_futuristic .tfo-hero-title{
  font-size:2.1rem;font-weight:800;letter-spacing:-.02em;line-height:1.1;
  background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent;
}
.st-key-dash_futuristic .tfo-hero-sub{color:#6b7280;font-size:.92rem;margin-top:3px}

.st-key-dash_futuristic .tfo-banner{
  display:inline-block;background:var(--b-bg);color:var(--b-color);
  padding:9px 16px;border-radius:12px;font-size:.85rem;font-weight:600;margin-bottom:22px;
}

.st-key-dash_futuristic .tfo-kpi-row{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-bottom:8px}
.st-key-dash_futuristic .tfo-kpi{
  position:relative;background:#fff;border:1px solid #eef0f7;border-radius:16px;
  padding:20px 20px 18px;box-shadow:0 2px 10px -4px rgba(15,23,42,.06);overflow:hidden;
}
.st-key-dash_futuristic .tfo-kpi::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--grad)}
.st-key-dash_futuristic .tfo-kpi-icon{
  width:38px;height:38px;border-radius:11px;background:#ecfdf5;
  display:flex;align-items:center;justify-content:center;font-size:18px;margin-bottom:12px;
}
.st-key-dash_futuristic .tfo-kpi-label{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#9ca3af;margin-bottom:6px}
.st-key-dash_futuristic .tfo-kpi-value{font-size:1.9rem;font-weight:800;color:#111827;letter-spacing:-.01em;margin-bottom:14px}
.st-key-dash_futuristic .tfo-kpi-deltas{display:flex;flex-direction:column;gap:6px;border-top:1px solid #f1f3f9;padding-top:12px}
.st-key-dash_futuristic .tfo-kpi-delta-row{display:flex;justify-content:space-between;font-size:.85rem}
.st-key-dash_futuristic .tfo-kpi-delta-label{color:#9ca3af;font-weight:600}
.st-key-dash_futuristic .tfo-kpi-delta-value{font-weight:700}
.st-key-dash_futuristic .tfo-kpi-delta-empty{color:#c0c4cf}

.st-key-dash_futuristic .tfo-section-title{font-size:1rem;font-weight:800;color:#111827;margin:2px 0 12px}

.st-key-dash_futuristic [class*="st-key-dash_card_"]{
  background:#fff;border:1px solid #eef0f7;border-radius:16px;
  padding:18px 18px 8px;box-shadow:0 2px 10px -4px rgba(15,23,42,.05);
}
</style>
"""

with st.container(key="dash_futuristic"):
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
    st.markdown(
        "<div class='tfo-hero'>"
        "<div class='tfo-hero-icon'>📊</div>"
        "<div><div class='tfo-hero-title'>Дашборд капитала</div>"
        "<div class='tfo-hero-sub'>Капитал, долговая нагрузка и доходы — в одном месте</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )

    if grand_total_live is not None:
        st.markdown(
            "<div class='tfo-banner' style='--b-bg:#ecfdf5;--b-color:#047857'>"
            f"💱 Последняя точка «Капитал, $» и «Долговая нагрузка» пересчитана по курсу bnb.by "
            f"на {_esc(rates_cache['fetched_at'])} — история на графиках не меняется.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='tfo-banner' style='--b-bg:#f3f4f6;--b-color:#6b7280'>"
            "💡 Курс bnb.by ещё не обновлялся — «сегодня» показано по цифрам из таблицы. "
            "Обнови курс в сайдбаре, чтобы включить пересчёт.</div>",
            unsafe_allow_html=True,
        )

    # --- KPI-карточки ---
    kpi_html = "<div class='tfo-kpi-row'>" + "".join([
        _capital_kpi_html("💵", "Капитал, $", capital_usd,
                          fmt_value=lambda v: f"${v:,.0f}".replace(",", " "),
                          fmt_delta=fmt_usd),
        _capital_kpi_html("💰", "Капитал, ₽", capital_rub,
                          fmt_value=lambda v: f"{v / 1_000_000:.1f} млн",
                          fmt_delta=fmt_rub_millions),
    ]) + "</div>"
    st.markdown(kpi_html, unsafe_allow_html=True)

    # --- События-комментарии к графикам (звёздочки поверх линий) ---
    events = st.session_state["events"]
    with st.expander(f"📌 События на графиках ({len(events)})"):
        st.caption("Отмечают особые решения (напр. «убрал из оценки технику и искусство»). "
                   "Появляются звёздочкой на выбранных графиках, при наведении — дата и текст.")
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
            for ev in sorted(events, key=lambda e: e.get("date", "")):
                r1, r2, r3, r4 = st.columns([2, 6, 3, 1])
                r1.write(pd.to_datetime(ev["date"]).strftime("%d.%m.%Y"))
                r2.write(ev.get("comment", ""))
                r3.caption(", ".join(CHART_OPTIONS.get(k, k) for k in ev.get("charts", [])))
                if r4.button("🗑", key=f"ev_del_{ev['id']}", help="Удалить событие"):
                    st.session_state["events"] = [x for x in events if x["id"] != ev["id"]]
                    save_events(st.session_state["events"])
                    st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        with st.container(key="dash_card_capital_usd"):
            st.markdown("<div class='tfo-section-title'>💵 Капитал, $</div>", unsafe_allow_html=True)
            line_chart(capital_usd, "USD", "#16A34A", chart_key="capital_usd")
    with col2:
        with st.container(key="dash_card_capital_rub"):
            st.markdown("<div class='tfo-section-title'>💰 Капитал, ₽</div>", unsafe_allow_html=True)
            line_chart(capital_rub, "RUB", "#1565C0")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    with col3:
        with st.container(key="dash_card_growth"):
            st.markdown("<div class='tfo-section-title'>📊 Прирост капитала по годам</div>", unsafe_allow_html=True)
            if not capital_usd.empty:
                yearly = (
                    capital_usd.assign(Год=capital_usd["date"].dt.year)
                    .groupby("Год", as_index=False)["value"]
                    .last()
                )
                yearly["Прирост"] = yearly["value"].diff()
                yearly = yearly.dropna(subset=["Прирост"])
                if yearly.empty:
                    st.warning("Недостаточно данных для расчёта прироста.")
                else:
                    fig = px.bar(yearly, x="Год", y="Прирост")
                    fig.update_traces(
                        marker_color=["#16A34A" if v >= 0 else "#C62828" for v in yearly["Прирост"]],
                        customdata=yearly["Прирост"].apply(lambda v: _fmt_point_value(v, "USD")),
                        hovertemplate="<b>%{x}</b><br>%{customdata}<extra></extra>",
                    )
                    fig.update_xaxes(type="category")
                    fig.update_layout(
                        xaxis_title=None,
                        yaxis_title="USD",
                        margin=dict(l=10, r=10, t=10, b=10),
                        height=320,
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Нет данных для отображения.")
    with col4:
        with st.container(key="dash_card_leverage"):
            st.markdown("<div class='tfo-section-title'>⚖️ Долг / капитал, %</div>", unsafe_allow_html=True)
            if not debt.empty and not capital_usd.empty:
                # Мерджим по точной дате отчёта и берём помесячный ряд (1-е число +
                # последнее показание) — иначе два отчёта за один месяц (13 и 14 июля)
                # дают дубли и вертикальные всплески на графике.
                merged = pd.merge(capital_usd, debt, on="date", suffixes=("_cap", "_debt"))
                merged = monthly_view(merged)
                if merged.empty:
                    st.warning("Нет пересекающихся дат для расчёта.")
                else:
                    merged["leverage"] = -merged["value_debt"] / merged["value_cap"] * 100
                    fig = px.line(merged, x="date", y="leverage", markers=True)
                    fig.update_traces(
                        line_color="#EF6C00",
                        customdata=merged["leverage"].apply(lambda v: _fmt_point_value(v, "%")),
                        hovertemplate="<b>%{x|%d.%m.%Y}</b><br>%{customdata}<extra></extra>",
                    )
                    fig.update_layout(
                        xaxis_title=None,
                        yaxis_title="%",
                        margin=dict(l=10, r=10, t=10, b=10),
                        height=320,
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Нет данных для отображения.")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    col5, col6 = st.columns(2)
    with col5:
        with st.container(key="dash_card_debt"):
            st.markdown("<div class='tfo-section-title'>📉 Долговая нагрузка, $</div>", unsafe_allow_html=True)
            st.caption("Значения без даты в исходной таблице пропущены")
            line_chart(debt, "USD", "#C62828", chart_key="debt")
    with col6:
        with st.container(key="dash_card_allocation"):
            st.markdown("<div class='tfo-section-title'>🥧 Структура капитала по классам активов</div>", unsafe_allow_html=True)
            allocation = load_asset_allocation()
            if allocation.empty:
                st.warning("Не нашёл помесячный срез с разбивкой по активам.")
            else:
                fig = px.pie(allocation, names="Категория", values="Сумма", hole=0.4,
                             color_discrete_sequence=GREEN_PALETTE)
                fig.update_traces(
                    customdata=allocation["Сумма"].apply(lambda v: _fmt_point_value(v, "USD")),
                    hovertemplate="<b>%{label}</b><br>%{customdata} · %{percent}<extra></extra>",
                )
                fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=320)
                st.plotly_chart(fig, use_container_width=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    col7, col8 = st.columns(2)
    with col7:
        with st.container(key="dash_card_active_income"):
            st.markdown("<div class='tfo-section-title'>💼 Активный доход, $</div>", unsafe_allow_html=True)
            line_chart(data.get("active_income"), "USD", "#1565C0", chart_key="active_income")
    with col8:
        with st.container(key="dash_card_passive_income"):
            st.markdown("<div class='tfo-section-title'>🌿 Пассивный доход, $</div>", unsafe_allow_html=True)
            line_chart(data.get("passive_income"), "USD", "#6A1B9A", chart_key="passive_income")
