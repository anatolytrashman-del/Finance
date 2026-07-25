"""Общая дизайн-система платформы — зелёный фирменный стиль.

Используется на каждой странице:

    from theme import page, card, section_title, kpi_row, kpi_card, banner, pill, esc

    with page("deals", "📈", "Реестр сделок", "Инвестиции, продажи и дивиденды"):
        kpi_row([kpi_card("💰", "Продажи", "$1 000"), ...])
        with card("deals", "table"):
            section_title("Сделки")
            st.dataframe(...)

`page()` открывает один st.container(key=...) на всю страницу (CSS видна только
внутри него и размонтируется при уходе со страницы — на остальные страницы не
протекает) и сразу рисует hero-заголовок. `card()` — вложенный контейнер с
общим для всех карточек CSS-стилем, найденным через подстроку класса
(`[class*="st-key-<page>_card_"]`), поэтому не нужно перечислять каждый key
в CSS вручную.
"""
import html as _html
from contextlib import contextmanager

import streamlit as st

GRADIENT = "linear-gradient(135deg, #059669 0%, #22C55E 55%, #A3E635 100%)"
GREEN_PALETTE = ["#059669", "#84CC16", "#0D9488", "#65A30D", "#10B981", "#4D7C0F", "#2DD4BF", "#3F6212"]

GOOD = ("#e6f4ea", "#1b5e20")
NEUTRAL = ("#f1f1f4", "#5f6368")
DANGER = ("#fdecea", "#b3261e")
BANNER_GOOD = ("#ecfdf5", "#047857")
BANNER_NEUTRAL = ("#f3f4f6", "#6b7280")


def esc(text):
    """HTML-экранирование для значений, вставляемых в сырые HTML-блоки (карточки,
    баннеры, пилюли) — это блочный/инлайновый HTML, а не markdown-текст, так что
    $ там не читается как LaTeX, а вот < и & — небезопасны."""
    return _html.escape(str(text))


def _page_css(key):
    return f"""
<style>
.st-key-{key} {{ --grad: {GRADIENT}; }}

.st-key-{key} .tfo-hero{{display:flex;align-items:center;gap:16px;margin:2px 0 22px}}
.st-key-{key} .tfo-hero-icon{{
  width:56px;height:56px;border-radius:16px;background:var(--grad);
  display:flex;align-items:center;justify-content:center;font-size:26px;
  box-shadow:0 10px 28px -10px rgba(34,197,94,.55);
}}
.st-key-{key} .tfo-hero-title{{
  font-size:2.1rem;font-weight:800;letter-spacing:-.02em;line-height:1.1;
  background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent;
}}
.st-key-{key} .tfo-hero-sub{{color:#6b7280;font-size:.92rem;margin-top:3px}}

.st-key-{key} .tfo-banner{{
  display:inline-block;background:var(--b-bg);color:var(--b-color);
  padding:9px 16px;border-radius:12px;font-size:.85rem;font-weight:600;margin-bottom:22px;
}}

.st-key-{key} .tfo-kpi-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:24px}}
.st-key-{key} .tfo-kpi{{
  position:relative;background:#fff;border:1px solid #eef0f7;border-radius:16px;
  padding:18px 18px 16px;box-shadow:0 2px 10px -4px rgba(15,23,42,.06);overflow:hidden;
}}
.st-key-{key} .tfo-kpi::before{{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--grad)}}
.st-key-{key} .tfo-kpi-icon{{
  width:34px;height:34px;border-radius:10px;background:#ecfdf5;
  display:flex;align-items:center;justify-content:center;font-size:16px;margin-bottom:10px;
}}
.st-key-{key} .tfo-kpi-label{{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#9ca3af;margin-bottom:4px}}
.st-key-{key} .tfo-kpi-value{{font-size:1.5rem;font-weight:800;color:#111827;letter-spacing:-.01em}}
.st-key-{key} .tfo-kpi-deltas{{display:flex;flex-direction:column;gap:6px;border-top:1px solid #f1f3f9;margin-top:12px;padding-top:12px}}
.st-key-{key} .tfo-kpi-delta-row{{display:flex;justify-content:space-between;font-size:.85rem}}
.st-key-{key} .tfo-kpi-delta-label{{color:#9ca3af;font-weight:600}}
.st-key-{key} .tfo-kpi-delta-value{{font-weight:700}}
.st-key-{key} .tfo-kpi-delta-empty{{color:#c0c4cf}}

.st-key-{key} .tfo-section-title{{font-size:1rem;font-weight:800;color:#111827;margin:2px 0 12px}}

.st-key-{key} [class*="st-key-{key}_card_"]{{
  background:#fff;border:1px solid #eef0f7;border-radius:16px;
  padding:18px 18px 8px;box-shadow:0 2px 10px -4px rgba(15,23,42,.05);
  margin-bottom:18px;
}}

.st-key-{key} [data-testid="stBaseButton-primary"]{{
  background:var(--grad) !important;border:none !important;
  box-shadow:0 6px 16px -6px rgba(34,197,94,.55) !important;
}}
</style>
"""


@contextmanager
def page(key, icon, title, subtitle=""):
    """Открывает страницу: контейнер с изолированной CSS + hero-заголовок.

    key должен быть уникальным для страницы и состоять из [a-z0-9_] — используется
    как есть в CSS-селекторах и в именах вложенных card()-контейнеров."""
    with st.container(key=key):
        st.markdown(_page_css(key), unsafe_allow_html=True)
        sub_html = f"<div class='tfo-hero-sub'>{esc(subtitle)}</div>" if subtitle else ""
        st.markdown(
            "<div class='tfo-hero'>"
            f"<div class='tfo-hero-icon'>{icon}</div>"
            f"<div><div class='tfo-hero-title'>{esc(title)}</div>{sub_html}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        yield


@contextmanager
def card(page_key, suffix):
    """Карточка внутри page(page_key, ...) — белый фон, скругление, тень.
    suffix должен быть уникальным в пределах страницы."""
    with st.container(key=f"{page_key}_card_{suffix}"):
        yield


def section_title(text):
    st.markdown(f"<div class='tfo-section-title'>{esc(text)}</div>", unsafe_allow_html=True)


def banner(icon, text, tone="good"):
    bg, color = BANNER_GOOD if tone == "good" else BANNER_NEUTRAL
    st.markdown(
        f"<div class='tfo-banner' style='--b-bg:{bg};--b-color:{color}'>{icon} {esc(text)}</div>",
        unsafe_allow_html=True,
    )


def kpi_card(icon, label, value, deltas=None, value_color=None, icon_bg=None):
    """deltas: список (label, value_text, color) — уже готовые строки, будут
    экранированы здесь. color=None -> нейтральный (значение не подсвечено).
    icon_bg: фон плашки иконки (по умолчанию — светло-зелёный из общей CSS)."""
    vc = f"color:{value_color};" if value_color else ""
    icon_style = f" style='background:{icon_bg}'" if icon_bg else ""
    deltas_html = ""
    if deltas:
        rows = "".join(
            f"<div class='tfo-kpi-delta-row'><span class='tfo-kpi-delta-label'>{esc(dl)}</span>"
            f"<span class='tfo-kpi-delta-value' style='color:{dc}'>{esc(dv)}</span></div>"
            if dv is not None else
            f"<div class='tfo-kpi-delta-row'><span class='tfo-kpi-delta-label'>{esc(dl)}</span>"
            "<span class='tfo-kpi-delta-empty'>нет данных</span></div>"
            for dl, dv, dc in deltas
        )
        deltas_html = f"<div class='tfo-kpi-deltas'>{rows}</div>"
    return (
        "<div class='tfo-kpi'>"
        f"<div class='tfo-kpi-icon'{icon_style}>{icon}</div>"
        f"<div class='tfo-kpi-label'>{esc(label)}</div>"
        f"<div class='tfo-kpi-value' style='{vc}'>{esc(value)}</div>"
        f"{deltas_html}"
        "</div>"
    )


def kpi_row(cards_html):
    st.markdown("<div class='tfo-kpi-row'>" + "".join(cards_html) + "</div>", unsafe_allow_html=True)


def pill(text, colors=NEUTRAL):
    """Пилюля — рендерится как <span>, а не <div>: несколько пилюль часто
    склеиваются в одну markdown-строку (см. kpi_row-подобные хедеры), и когда
    такая строка из голых <span>-тегов содержит $, Streamlit ломает её при
    парсинге (несколько инлайн-тегов подряд трактуются иначе, чем один) —
    поэтому здесь, в отличие от esc()/блочных карточек, $ ещё и
    бэкслеш-экранируется вручную (проверено вживую: без этого верстка
    рассыпается ровно в multi-pill-конкатенации с $, но не в одиночном span)."""
    bg, color = colors
    safe = esc(text).replace("$", r"\$")
    return (
        f"<span style='display:inline-block;background:{bg};color:{color};"
        "padding:4px 14px;border-radius:16px;font-size:0.8rem;font-weight:600;"
        "letter-spacing:.01em;box-shadow:0 1px 2px rgba(0,0,0,.06);"
        f"margin:2px 6px 2px 0'>{safe}</span>"
    )
