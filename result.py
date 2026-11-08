
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
    render_result(
        last["result"],
        citizen_urgency=last["urgency"],
        report_id=last["id"]
    )

elif last["kind"] == "emergency":
    validation = last.get("validation") or {}

    st.error("⚠️ Mögliche akute Gefahr erkannt")

    st.markdown(
        """
        Ihre Meldung könnte auf eine Situation hinweisen,
        in der Menschen unmittelbar gefährdet sind.

        **Bitte bringen Sie sich nach Möglichkeit
        zuerst selbst in Sicherheit.**

        Wenn aktuell eine akute Gefahr besteht,
        wenden Sie sich bitte direkt an die
        zuständigen Notrufstellen.
        """
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🚒 112")
        st.write("Feuerwehr und Rettungsdienst")
        st.caption(
            "Bei Feuer, Einsturzgefahr, Verletzten "
            "oder medizinischen Notfällen."
        )

    with col2:
        st.markdown("### 🚓 110")
        st.write("Polizei")
        st.caption(
            "Bei akuter Bedrohung, Gewalt oder "
            "wenn sofortige polizeiliche Hilfe nötig ist."
        )

    st.warning(
        "FixMyCity AI ist kein Notrufsystem. "
        "Durch diese Meldung wurden keine "
        "Rettungskräfte oder Polizeikräfte alarmiert. "
        "Bitte warten Sie bei akuter Gefahr "
        "nicht auf eine Rückmeldung der App."
    )

    if validation.get("reason"):
        with st.expander("Warum wird dieser Hinweis angezeigt?"):
            st.write(validation["reason"])

    st.info(
        "Diese Meldung wurde nicht als regulärer "
        "kommunaler Reparaturauftrag weitergeleitet."
    )

    if st.button(
        "Neue Meldung erstellen",
        type="primary",
        width="stretch"
    ):
        st.switch_page("report.py")

else:
    render_rejection(last.get("validation"))

    if st.button(
        "Foto oder Beschreibung ändern",
        type="primary",
        width="stretch"
    ):
        st.switch_page("report.py")

if st.button("Zur Startseite", width="stretch"):
    st.switch_page("home.py")
