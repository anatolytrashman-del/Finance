import streamlit as st

st.set_page_config(page_title="Редевелопмент — платформа", page_icon="🏗️", layout="wide")

overview = st.Page("views/overview.py", title="Реестр проектов", icon="🏗️", default=True)
project = st.Page("views/project.py", title="Карточка проекта", icon="📇")

nav = st.navigation([overview, project])
nav.run()
