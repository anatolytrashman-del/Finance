import streamlit as st

from auth import require_password

st.set_page_config(page_title="Trashman Family Office", page_icon="📊", layout="wide")

require_password()

# Единый шрифт для всего приложения — Montserrat. app.py выполняется при
# отрисовке каждой страницы (перед nav.run()), поэтому вставка здесь применяет
# шрифт ко всем страницам сразу. Google Fonts сам отдаёт и латиницу, и кириллицу
# (весь интерфейс на русском), подставляя нужный поднабор по unicode-range.
#
# <link>, а не CSS @import — @import блокирует отрисовку страницы, пока не
# скачается шрифт (это происходит на КАЖДОЙ навигации, т.к. app.py
# перевыполняется целиком); <link rel="stylesheet"> браузер грузит параллельно
# с остальной страницей, plus preconnect заранее открывает соединение.
st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
    html, body, [class*="css"], .stApp,
    button, input, optgroup, select, textarea,
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Montserrat', sans-serif !important;
    }

    /* Боковое меню — фирменный стиль Coinaco: кремовый фон, тёмная пилюля
    на активной странице. Таргетимся на data-testid, а не на автогенерируемые
    emotion-классы — они меняются между версиями Streamlit. */
    section[data-testid="stSidebar"] {
        background: #F7F5F0;
        border-right: 1px solid #ECE9E2;
    }
    [data-testid="stSidebarNavLink"] {
        border-radius: 12px;
        margin: 2px 8px;
    }
    [data-testid="stSidebarNavLink"]:hover {
        background: #ECE9E2 !important;
    }
    [data-testid="stSidebarNavLink"] span, [data-testid="stSidebarNavLink"] p {
        color: #4b4d57 !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebarNavLink"][aria-current="page"] {
        background: #17171C !important;
    }
    [data-testid="stSidebarNavLink"][aria-current="page"] span,
    [data-testid="stSidebarNavLink"][aria-current="page"] p {
        color: #ffffff !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.logo("assets/logo.svg", size="large")

dashboard = st.Page("views/dashboard.py", title="Дашборды", icon="📊", default=True)
balance = st.Page("views/balance.py", title="Баланс", icon="⚖️")
deals = st.Page("views/deals.py", title="Сделки", icon="📈")
real_estate = st.Page("views/real_estate.py", title="Недвижимость", icon="🏠")
entities = st.Page("views/entities.py", title="Юрлица", icon="🏛️")
documents = st.Page("views/documents.py", title="Архив документов", icon="🗂️")
ideas = st.Page("views/ideas.py", title="Инвест-идеи", icon="💡")
finmodel = st.Page("views/finmodel.py", title="Финмодель", icon="🧮")
market = st.Page("views/market.py", title="Анализ рынка", icon="🏷️")
data_entry = st.Page("views/data_entry.py", title="Ввод данных", icon="✍️")

nav = st.navigation(
    [dashboard, balance, deals, real_estate, entities, documents, ideas, finmodel, market, data_entry]
)
nav.run()
