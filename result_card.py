import streamlit as st

RISK_NAMES = {
    "danger": "Gefahr",
    "impact": "Betroffene Personen",
    "urgency": "Dringlichkeit",
}


def render_result(result):
    """Zeigt das Ergebnis einer Meldung als Karte an."""
    validation = result.get("validation")

    if validation and validation["status"] == "INVALID":
        st.error("❌ Meldung nicht zur Weiterleitung freigegeben")
        st.write("**Begründung:**", validation["reason"])
        return

    if validation and validation["status"] == "UNCERTAIN":
        st.warning("⚠️ Weitere Informationen erforderlich")
        st.write("Bitte ergänze deine Meldung oder lade ein besseres Foto hoch.")
        st.write("**Begründung:**", validation["reason"])
        return
    priority = result["priority"]
    label = priority["priority"]

    if label.startswith("P1"):
        st.error(f"🔴 {label}")
    elif label.startswith("P2"):
        st.warning(f"🟠 {label}")
    else:
        st.success(f"🟢 {label}")

    st.write("Punktzahl:", priority["score"], "/ 18")

    st.subheader("Meldung")
    st.write("**Standort:**", result["location"])
    st.write("**Beschreibung:**", result["description"])

    st.subheader("Risikofaktoren")
    factors = result["risk_factors"]

    for key, name in RISK_NAMES.items():
        value = factors[key]
        st.write(f"**{name}:** {value} / 3")
        st.progress(value / 3)

    if factors["acute_hazard"]:
        st.error("🚨 Akute Gefahr erkannt!")

    with st.expander("🤖 Analyse der KI anzeigen"):
        st.write(result["image_analysis"])