import streamlit as st

st.set_page_config(page_title="Trashman Family Office", page_icon="📊", layout="wide")

# Единый шрифт для всего приложения — Montserrat. app.py выполняется при
# отрисовке каждой страницы (перед nav.run()), поэтому вставка здесь применяет
# шрифт ко всем страницам сразу. Google Fonts сам отдаёт и латиницу, и кириллицу
# (весь интерфейс на русском), подставляя нужный поднабор по unicode-range.
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"], .stApp,
    button, input, optgroup, select, textarea,
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Montserrat', sans-serif !important;
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
documents = st.Page("views/documents.py", title="Архив документов", icon="🗂️")
ideas = st.Page("views/ideas.py", title="Инвест-идеи", icon="💡")
finmodel = st.Page("views/finmodel.py", title="Финмодель", icon="🧮")
market = st.Page("views/market.py", title="Анализ рынка", icon="🏷️")

nav = st.navigation([dashboard, balance, deals, real_estate, documents, ideas, finmodel, market])
nav.run()
