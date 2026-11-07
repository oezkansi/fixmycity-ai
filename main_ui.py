"""Einstieg der Oberfläche:  streamlit run main_ui.py"""
import streamlit as st

st.set_page_config(page_title="FixMyCity AI", page_icon="📍", layout="centered")

pages = [
    st.Page("home.py", title="Startseite", default=True),
    st.Page("report.py", title="Meldung abgeben", url_path="melden"),
    st.Page("result.py", title="Ergebnis", url_path="ergebnis"),
    st.Page("admin.py", title="Verwaltung", url_path="verwaltung"),
]
try:
    nav = st.navigation(pages, position="hidden")
except TypeError:  # ältere Streamlit-Versionen
    nav = st.navigation(pages)
nav.run()
