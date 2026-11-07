"""Ergebnis für Bürger."""
import streamlit as st

from result_card import render_rejection, render_result
from ui_theme import apply_theme, get_session_id, page_header

apply_theme()
get_session_id()
page_header("IHRE MELDUNG")

last = st.session_state.get("last")
if not last:
    st.info("Noch keine Meldung abgegeben.")
elif last["kind"] == "ok":
    render_result(last["result"], citizen_urgency=last["urgency"], report_id=last["id"])
else:
    render_rejection(last.get("validation"))
    if st.button("Foto oder Beschreibung ändern", type="primary", width="stretch"):
        st.switch_page("report.py")

if st.button("Zur Startseite", width="stretch"):
    st.switch_page("home.py")
