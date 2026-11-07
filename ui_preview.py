import streamlit as st
from result_card import render_result

st.set_page_config(page_title="UI-Vorschau", page_icon="🎨")

st.title("🎨 Ergebnis-Karte (Vorschau)")

# Erfundene Beispieldaten, gleiche Form wie das, was process_report zurückgibt
basis = {
    "location": "Pforzheim, Bahnhofstraße",
    "description": "Der Gehweg ist aufgebrochen, der Asphalt ist zerbröckelt.",
    "image_analysis": "Auf dem Bild ist ein beschädigter Gehweg zu sehen.",
}

szenarien = {
    "P1 - Kritisch": {
        **basis,
        "risk_factors": {"danger": 3, "impact": 3, "urgency": 3, "acute_hazard": True},
        "priority": {"score": 18, "priority": "P1 - Critical", "requires_review": True},
    },
    "P2 - Hoch": {
        **basis,
        "risk_factors": {"danger": 2, "impact": 2, "urgency": 2, "acute_hazard": False},
        "priority": {"score": 12, "priority": "P2 - High", "requires_review": False},
    },
    "P3 - Normal": {
        **basis,
        "risk_factors": {"danger": 1, "impact": 1, "urgency": 1, "acute_hazard": False},
        "priority": {"score": 6, "priority": "P3 - Normal", "requires_review": False},
    },
    "Ungültig (INVALID)": {
        **basis,
        "validation": {
            "status": "INVALID",
            "reason": "Auf dem Bild ist lediglich ein Kätzchen in einem Korb zu sehen.",
            "detected_problem": "Kein Schaden erkennbar",
        },
    },
    "Unsicher (UNCERTAIN)": {
        **basis,
        "validation": {
            "status": "UNCERTAIN",
            "reason": "Das Bild ist zu unscharf, um den Schaden sicher zu beurteilen.",
            "detected_problem": "Unklar",
        },
    },
}

auswahl = st.selectbox("Testfall wählen:", list(szenarien.keys()))

st.divider()

render_result(szenarien[auswahl])