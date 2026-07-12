import streamlit as st

from data_source import get_workbook, sidebar_refresh_control
from parsers import parse_real_estate

st.set_page_config(page_title="Недвижимость", page_icon="🏠", layout="wide")

sidebar_refresh_control()

st.title("🏠 Каталог объектов недвижимости")

wb = get_workbook()
if wb is None:
    st.info("Нажми «Обновить данные» в боковой панели, чтобы загрузить таблицу.")
    st.stop()

df = parse_real_estate(wb)

if df.empty:
    st.warning("Лист «Real Estate» пуст или не найден.")
    st.stop()

st.caption(f"Объектов: {len(df)}")
st.dataframe(df, width='stretch', hide_index=True)

for _, row in df.iterrows():
    title = row.get("Тип", "Объект")
    location = row.get("Локация", "")
    with st.expander(f"{title} — {location}"):
        for col in df.columns:
            value = row.get(col)
            if value is not None and str(value).strip() not in ("", "None", "nan"):
                st.write(f"**{col}:** {value}")
