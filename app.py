import streamlit as st

st.set_page_config(page_title="Trashman Family Office", page_icon="📊", layout="wide")

st.logo("assets/logo.svg", size="large")

dashboard = st.Page("views/dashboard.py", title="Дашборды", icon="📊", default=True)
balance = st.Page("views/balance.py", title="Баланс", icon="⚖️")
deals = st.Page("views/deals.py", title="Сделки", icon="📈")
real_estate = st.Page("views/real_estate.py", title="Недвижимость", icon="🏠")
documents = st.Page("views/documents.py", title="Архив документов", icon="🗂️")
ideas = st.Page("views/ideas.py", title="Инвест-идеи", icon="💡")
finmodel = st.Page("views/finmodel.py", title="Финмодель", icon="🧮")
market = st.Page("views/market.py", title="Анализ рынка", icon="🏷️")
land = st.Page("views/land.py", title="Земельные участки", icon="🌾")

nav = st.navigation([dashboard, balance, deals, real_estate, documents, ideas, finmodel, market, land])
nav.run()
