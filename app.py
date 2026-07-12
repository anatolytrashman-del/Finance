import streamlit as st

st.set_page_config(page_title="Капитал", page_icon="📊", layout="wide")

dashboard = st.Page("views/dashboard.py", title="Дашборды", icon="📊", default=True)
deals = st.Page("views/deals.py", title="Сделки", icon="📈")
real_estate = st.Page("views/real_estate.py", title="Недвижимость", icon="🏠")

nav = st.navigation([dashboard, deals, real_estate])
nav.run()
