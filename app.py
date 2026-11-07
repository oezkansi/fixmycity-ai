import streamlit as st
from streamlit_geolocation import streamlit_geolocation


import streamlit as st
from pathlib import Path
import tempfile
import os
from dotenv import load_dotenv
load_dotenv()

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

from report_pipeline import process_report

st.set_page_config(
    page_title="FixMyCity AI",
    page_icon="🏙️",
    layout="centered"
)

st.title("🏙️ FixMyCity AI")
st.write("Melde Schäden und Gefahren in deiner Stadt.")

st.subheader("Neue Schadensmeldung")
if DEMO_MODE:
    st.info("🧪 Demo-Modus aktiv: Bilder hochladen und Standorte testen erlaubt.")
else:
    st.info("🔒 Bürger-Modus: Standortfreigabe und Live-Foto erforderlich.")

if DEMO_MODE:
    uploaded_file = st.file_uploader(
        "🧪 Testbild vom MacBook hochladen",
        type=["jpg", "jpeg", "png"]
    )
else:
    uploaded_file = st.camera_input(
        "📸 Fotografiere den Schaden direkt vor Ort"
    )

description = st.text_area(
    "Beschreibe das Problem",
    placeholder="z. B. Auf dem Gehweg liegt eine Spritze."
)


st.subheader("📍 Standort des Schadens")

location_method = st.radio(
    "Wie möchtest du den Standort angeben?",
    ["Automatisch erkennen", "Manuell eingeben"]
)

if location_method == "Automatisch erkennen":
    st.write("Klicke auf den Button und erlaube den Standortzugriff.")

    geo = streamlit_geolocation()

    if geo and geo.get("latitude") is not None and geo.get("longitude") is not None:
        latitude = geo["latitude"]
        longitude = geo["longitude"]

        location = f"{latitude}, {longitude}"

        st.success("Standort erfolgreich erkannt!")
        st.map([{"lat": latitude, "lon": longitude}])
    else:
        location = ""
        st.info("Bitte Standort freigeben oder manuell eingeben.")

else:
    location = st.text_input(
        "Wo befindet sich der Schaden?",
        placeholder="z. B. Pforzheim, Bahnhofstraße"
    )


citizen_urgency = st.slider(
    "Wie dringend empfindest du das Problem?",
    min_value=1,
    max_value=5,
    value=3
)

if uploaded_file is not None:
    st.image(uploaded_file, caption="Dein hochgeladenes Foto")

if st.button("Schadensmeldung absenden", type="primary"):
    if uploaded_file is None or not description.strip() or not location.strip():
        st.warning("Bitte Foto, Beschreibung und Standort angeben.")
    else:
        suffix = Path(uploaded_file.name).suffix.lower()

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix
        ) as temp_file:
            temp_file.write(uploaded_file.getvalue())
            image_path = temp_file.name

        try:
            with st.spinner("Deine Meldung wird analysiert ..."):
                result = process_report(
                    image_path,
                    description,
                    location
                )

            
            validation = result.get("validation")

            if validation and validation["status"] == "INVALID":
                st.warning(
                    "Der gemeldete Schaden konnte anhand "
                    "des Fotos nicht bestätigt werden."
                )
                st.write(validation["reason"])
                st.stop()

            elif validation and validation["status"] == "UNCERTAIN":
                st.info(
                    "Das Foto reicht für eine eindeutige "
                    "Prüfung nicht aus. Bitte ergänze "
                    "deine Meldung."
                )
                st.write(validation["reason"])
                st.stop()

            else:
                st.success("Deine Meldung wurde analysiert!")

            st.write("**Schadensbeschreibung:**", description)
            st.write("**Standort:**", location)
            st.write("**Deine Dringlichkeit:**", citizen_urgency, "/ 5")

            # AI priority is intentionally not shown to citizens.
            # Later, the result will be stored for the admin dashboard.

        except Exception as e:
            st.error(f"Fehler bei der Analyse: {e}")
        finally:
            Path(image_path).unlink(missing_ok=True)
