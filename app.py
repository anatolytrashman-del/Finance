import streamlit as st

st.set_page_config(page_title="Trashman Family Office", page_icon="📊", layout="wide")

st.logo("assets/logo.svg", size="large")

dashboard = st.Page("views/dashboard.py", title="Дашборды", icon="📊", default=True)
deals = st.Page("views/deals.py", title="Сделки", icon="📈")
real_estate = st.Page("views/real_estate.py", title="Недвижимость", icon="🏠")
ideas = st.Page("views/ideas.py", title="Инвест-идеи", icon="💡")
finmodel = st.Page("views/finmodel.py", title="Финмодель", icon="🧮")
market = st.Page("views/market.py", title="Рынок", icon="🏷️")

nav = st.navigation([dashboard, deals, real_estate, ideas, finmodel, market])
nav.run()
