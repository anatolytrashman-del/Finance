import textwrap
import uuid
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from data_source import load_asset_allocation, load_progress, sidebar_refresh_control
from events_store import load_events, save_events

sidebar_refresh_control()

st.title("📊 Дашборд капитала")

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
    st.info("Нажми «Обновить данные» в боковой панели, чтобы загрузить таблицу.")
    st.stop()
capital_usd = data.get("capital_usd", pd.DataFrame())
capital_rub = data.get("capital_rub", pd.DataFrame())
debt = data.get("debt", pd.DataFrame())


def monthly_view(df):
    """Помесячный взгляд на серию: показания за 1-е число месяца + самое
    последнее показание как отдельная самостоятельная точка. Промежуточные
    внутримесячные отчёты (не 1-е число и не последний) пропускаются."""
    if df is None or df.empty:
        return df
    df = df.sort_values("date").reset_index(drop=True)
    keep = (df["date"].dt.day == 1) | (df["date"] == df["date"].iloc[-1])
    return df[keep].reset_index(drop=True)


def _overlay_events(fig, mv, chart_key):
    """Ставит маркеры-звёздочки событий на линию (привязка к ближайшему замеру).

    События вне диапазона ряда (± ~месяц) пропускаются."""
    events = st.session_state.get("events") or []
    if mv is None or mv.empty:
        return
    mv = mv.sort_values("date").reset_index(drop=True)
    lo = mv["date"].min() - pd.Timedelta(days=31)
    hi = mv["date"].max() + pd.Timedelta(days=31)
    xs, ys, texts = [], [], []
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
        xs.append(mv.loc[idx, "date"])
        ys.append(mv.loc[idx, "value"])
        # переносим длинный комментарий по словам, чтобы тултип не обрезался
        wrapped = "<br>".join(textwrap.wrap(ev.get("comment", ""), width=44)) or "—"
        texts.append(f"<b>{d:%d.%m.%Y}</b><br>{wrapped}")
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
    fig.update_traces(line_color=color)
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


def render_delta_line(label, delta_str, pct):
    if delta_str is None:
        st.caption(f"{label}: недостаточно данных")
        return
    positive = pct is None or pct >= 0
    color = "#16a34a" if positive else "#dc2626"
    arrow = "↑" if positive else "↓"
    pct_part = f" {arrow} {abs(pct):.1f}%" if pct is not None else ""
    st.markdown(
        f"<div style='font-size:0.875rem;'>{label}: "
        f"<span style='color:{color};font-weight:600'>{delta_str}{pct_part}</span></div>",
        unsafe_allow_html=True,
    )


def render_capital_kpi(label, df, fmt_value, fmt_delta):
    stats = capital_stats(df)
    if stats is None:
        return
    st.metric(label, fmt_value(stats["latest"]))
    sub1, sub2 = st.columns(2)
    with sub1:
        render_delta_line(
            "За месяц",
            fmt_delta(stats["month_delta"]) if stats["month_delta"] is not None else None,
            stats["month_pct"],
        )
    with sub2:
        render_delta_line(
            "За год",
            fmt_delta(stats["year_delta"]) if stats["year_delta"] is not None else None,
            stats["year_pct"],
        )


def fmt_usd(v):
    sign = "+" if v >= 0 else "-"
    return f"{sign}${abs(v):,.0f}".replace(",", " ")


def fmt_rub_millions(v):
    return f"{v / 1_000_000:+.1f} млн"


# --- KPI-карточки ---
kpi1, kpi2 = st.columns(2)
with kpi1:
    render_capital_kpi(
        "Капитал, $", capital_usd,
        fmt_value=lambda v: f"${v:,.0f}".replace(",", " "),
        fmt_delta=fmt_usd,
    )
with kpi2:
    render_capital_kpi(
        "Капитал, ₽", capital_rub,
        fmt_value=lambda v: f"{v / 1_000_000:.1f} млн",
        fmt_delta=fmt_rub_millions,
    )

st.divider()

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

col1, col2 = st.columns(2)
with col1:
    st.subheader("Капитал, $")
    line_chart(capital_usd, "USD", "#2E7D32", chart_key="capital_usd")
with col2:
    st.subheader("Капитал, ₽")
    line_chart(capital_rub, "RUB", "#1565C0")

col3, col4 = st.columns(2)
with col3:
    st.subheader("Прирост капитала по годам")
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
                marker_color=["#2E7D32" if v >= 0 else "#C62828" for v in yearly["Прирост"]]
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
    st.subheader("Долг / капитал, %")
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
            fig.update_traces(line_color="#EF6C00")
            fig.update_layout(
                xaxis_title=None,
                yaxis_title="%",
                margin=dict(l=10, r=10, t=10, b=10),
                height=320,
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Нет данных для отображения.")

col5, col6 = st.columns(2)
with col5:
    st.subheader("Долговая нагрузка, $")
    st.caption("Значения без даты в исходной таблице пропущены")
    line_chart(debt, "USD", "#C62828", chart_key="debt")
with col6:
    st.subheader("Структура капитала по классам активов")
    allocation = load_asset_allocation()
    if allocation.empty:
        st.warning("Не нашёл помесячный срез с разбивкой по активам.")
    else:
        fig = px.pie(allocation, names="Категория", values="Сумма", hole=0.4)
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=320)
        st.plotly_chart(fig, use_container_width=True)

st.divider()

col7, col8 = st.columns(2)
with col7:
    st.subheader("Активный доход, $")
    line_chart(data.get("active_income"), "USD", "#1565C0", chart_key="active_income")
with col8:
    st.subheader("Пассивный доход, $")
    line_chart(data.get("passive_income"), "USD", "#6A1B9A", chart_key="passive_income")
