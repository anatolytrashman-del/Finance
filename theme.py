"""Общая дизайн-система платформы — фирменный стиль Coinaco (кремовый фон,
белые карточки, чёрный текст, мягкие акцентные цвета).

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

GOOD = ("#E8F8EF", "#1DBF73")
NEUTRAL = ("#F1EFEA", "#6b6f7a")
DANGER = ("#FDEDE9", "#E5484D")
BANNER_GOOD = GOOD
BANNER_NEUTRAL = NEUTRAL


def esc(text):
    """HTML-экранирование для значений, вставляемых в сырые HTML-блоки (карточки,
    баннеры, пилюли) — это блочный/инлайновый HTML, а не markdown-текст, так что
    $ там не читается как LaTeX, а вот < и & — небезопасны."""
    return _html.escape(str(text))


def _page_css(key):
    return f"""
<style>
.st-key-{key} {{
  background:#EFEDE8;border-radius:28px;padding:26px 26px 24px;
}}

.st-key-{key} .tfo-hero{{display:flex;align-items:center;gap:14px;margin:2px 0 22px}}
.st-key-{key} .tfo-hero-icon{{
  width:46px;height:46px;border-radius:50%;background:#F1EFEA;
  display:flex;align-items:center;justify-content:center;font-size:21px;flex-shrink:0;
}}
.st-key-{key} .tfo-hero-title{{font-size:1.9rem;font-weight:700;color:#17171C;letter-spacing:-.01em;line-height:1.15}}
.st-key-{key} .tfo-hero-sub{{color:#8b8d98;font-size:.88rem;margin-top:2px}}

.st-key-{key} .tfo-banner{{
  display:inline-block;background:var(--b-bg);color:var(--b-color);
  padding:8px 16px;border-radius:12px;font-size:.82rem;font-weight:600;margin-bottom:22px;
}}

.st-key-{key} .tfo-kpi-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:24px}}
.st-key-{key} .tfo-kpi{{
  position:relative;background:#fff;border-radius:20px;
  padding:20px 20px 16px;box-shadow:0 1px 3px rgba(23,23,28,.05);
}}
.st-key-{key} .tfo-kpi-icon{{
  width:34px;height:34px;border-radius:50%;background:#F1EFEA;
  display:flex;align-items:center;justify-content:center;font-size:16px;margin-bottom:10px;
}}
.st-key-{key} .tfo-kpi-label{{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#9a9ca6;margin-bottom:4px}}
.st-key-{key} .tfo-kpi-value{{font-size:1.5rem;font-weight:800;color:#17171C;letter-spacing:-.01em}}
.st-key-{key} .tfo-kpi-deltas{{display:flex;flex-direction:column;gap:6px;border-top:1px solid #F1EFEA;margin-top:12px;padding-top:12px}}
.st-key-{key} .tfo-kpi-delta-row{{display:flex;justify-content:space-between;font-size:.85rem}}
.st-key-{key} .tfo-kpi-delta-label{{color:#9a9ca6;font-weight:600}}
.st-key-{key} .tfo-kpi-delta-value{{font-weight:700}}
.st-key-{key} .tfo-kpi-delta-empty{{color:#c7c9d1}}

.st-key-{key} .tfo-section-title{{font-size:1rem;font-weight:700;color:#17171C;margin:2px 0 12px}}

.st-key-{key} [class*="st-key-{key}_card_"]{{
  background:#fff;border-radius:20px;
  padding:20px 20px 8px;box-shadow:0 1px 3px rgba(23,23,28,.05);
  margin-bottom:18px;
}}

.st-key-{key} [data-testid="stBaseButton-primary"]{{
  background:#17171C !important;border:none !important;border-radius:999px !important;
  box-shadow:none !important;
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


def chip(col, label, value, icon=""):
    """Компактное поле «подпись сверху / значение снизу» в конкретной
    колонке — не рисуется вовсе, если значение пустое (чтобы карточка не
    пестрела прочерками по незаполненным полям)."""
    if not value:
        return
    prefix = f"{icon} " if icon else ""
    col.markdown(
        "<div style='margin-bottom:12px'>"
        f"<div style='font-size:0.72rem;font-weight:700;color:#9a9ca6;"
        f"text-transform:uppercase;letter-spacing:.06em;margin-bottom:2px'>{prefix}{esc(label)}</div>"
        f"<div style='font-size:0.95rem;font-weight:600;color:#17171C'>{esc(value)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def banner(icon, text, tone="good"):
    bg, color = BANNER_GOOD if tone == "good" else BANNER_NEUTRAL
    st.markdown(
        f"<div class='tfo-banner' style='--b-bg:{bg};--b-color:{color}'>{icon} {esc(text)}</div>",
        unsafe_allow_html=True,
    )


def kpi_card(icon, label, value, deltas=None, value_color=None, icon_bg=None):
    """deltas: список (label, value_text, color) — уже готовые строки, будут
    экранированы здесь. color=None -> нейтральный (значение не подсвечено).
    icon_bg: фон плашки иконки (по умолчанию — светло-серый из общей CSS)."""
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
        "padding:4px 14px;border-radius:16px;font-size:0.8rem;font-weight:700;"
        "letter-spacing:.01em;"
        f"margin:2px 6px 2px 0'>{safe}</span>"
    )
