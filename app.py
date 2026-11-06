import streamlit as st
from pathlib import Path
import tempfile

from streamlit_geolocation import streamlit_geolocation
from report_pipeline import process_report
from database import save_report_to_db
from capacity_manager import process_capacity_queues
from geo_utils import get_district_and_road_type

st.set_page_config(
    page_title="FixMyCity AI",
    page_icon="🏙️",
    layout="centered"
)

st.title("🏙️ FixMyCity AI")
st.write("Smartes kommunales Schadensmanagement & Priorisierung.")

# Tabs oben definieren
tab1, tab2 = st.tabs(["📸 Bürger-Meldeformular", "🚦 Verwaltungs-Dashboard"])

# ==========================================
# TAB 1: BÜRGER-MELDEFORMULAR
# ==========================================
with tab1:
    st.subheader("Neue Schadensmeldung")

    uploaded_file = st.file_uploader(
        "Foto des Schadens hochladen",
        type=["jpg", "jpeg", "png"]
    )

    description = st.text_area(
        "Beschreibe das Problem",
        placeholder="z. B. Auf der Fahrbahn ist ein tiefes Schlagloch."
    )

    st.subheader("📍 Standort des Schadens")

    location_method = st.radio(
        "Wie möchtest du den Standort angeben?",
        ["Automatisch erkennen", "Manuell eingeben"]
    )

    # Standard-Variablen vorbelegen
    district = "Bezirk_Mitte"
    is_main_road = False
    location = ""

    if location_method == "Automatisch erkennen":
        st.write("Klicke auf den Button und erlaube den Standortzugriff.")
        geo = streamlit_geolocation()

        if geo and geo.get("latitude") is not None and geo.get("longitude") is not None:
            latitude = geo["latitude"]
            longitude = geo["longitude"]
            location = f"{latitude}, {longitude}"
            
            # Automatische GIS-Erkennung im Hintergrund
            district, is_main_road = get_district_and_road_type(latitude, longitude)
            
            st.success(f"Standort erkannt! (Automatisch zugeordnet: {district} | Hauptstraße: {'Ja' if is_main_road else 'Nein'})")
            st.map([{"lat": latitude, "lon": longitude}])
        else:
            st.info("Bitte Standort freigeben oder manuell eingeben.")
    else:
        location = st.text_input(
            "Wo befindet sich der Schaden?",
            placeholder="z. B. Pforzheim, Bahnhofstraße"
        )
        # Manuelle Auswahl, falls nicht via GPS ermittelt
        district = st.selectbox(
            "Bezirk wählen",
            ["Bezirk_Mitte", "Bezirk_Nord", "Bezirk_Sued", "Bezirk_West", "Bezirk_Ost"]
        )
        is_main_road = st.checkbox("Handelt es sich um eine Hauptstraße?")

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
                    # Übergabe aller Parameter inklusive GIS-Daten an die Pipeline
                    result = process_report(
                        image_path=image_path,
                        description=description,
                        location=location,
                        district=district,
                        is_main_road=is_main_road,
                        citizen_urgency=citizen_urgency,
                        days_waiting=0
                    )

                validation = result.get("validation")

                if validation and validation["status"] == "INVALID":
                    st.warning("Der gemeldete Schaden konnte anhand des Fotos nicht bestätigt werden.")
                    st.write(validation["reason"])
                    st.stop()

                elif validation and validation["status"] == "UNCERTAIN":
                    st.info("Das Foto reicht für eine eindeutige Prüfung nicht aus. Bitte ergänze deine Meldung.")
                    st.write(validation["reason"])
                    st.stop()

                else:
                    st.success("Deine Meldung wurde erfolgreich analysiert und eingereicht!")
                    # In Datenbank speichern, damit das Dashboard darauf zugreifen kann
                    save_report_to_db(result)

                st.write("**Schadensbeschreibung:**", description)
                st.write("**Standort:**", location)
                st.write("**Bezirk:**", district)
                st.write("**Hauptstraße:**", "Ja" if is_main_road else "Nein")
                st.write("**Deine Dringlichkeit:**", citizen_urgency, "/ 5")

            except Exception as e:
                st.error(f"Die Analyse ist fehlgeschlagen: {e}")
            finally:
                Path(image_path).unlink(missing_ok=True)


# ==========================================
# TAB 2: VERWALTUNGS-DASHBOARD
# ==========================================
with tab2:
    st.subheader("🚦 Verwaltungs-Dashboard: Prioritäten & Kapazitäten")
    st.write("Hier sieht die Stadtverwaltung alle gemeldeten Schäden, gewichtet nach KI-Score und reguliert durch das Kapazitätsmanagement.")

    if st.button("🔄 Daten aktualisieren"):
        st.rerun()

    try:
        active_sites, waiting_sites = process_capacity_queues()

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"### 🚧 Aktive Baustellen ({len(active_sites)})")
            if not active_sites:
                st.info("Keine aktiven Baustellen vorhanden.")
            for site in active_sites:
                with st.expander(f"[{site['priority']}] {site['location']} ({site['district']})"):
                    st.write(f"**Beschreibung:** {site['description']}")
                    st.write(f"**Kategorie:** {site['category']} / {site['subcategory']}")
                    st.write(f"**Score:** {site['score']} | **Wartetage:** {site['days_waiting']}")
                    st.write(f"**Hauptstraße:** {'Ja' if site['is_main_road'] else 'Nein'}")
                    st.write(f"**Status:** {site['status']}")

        with col2:
            st.markdown(f"### ⏳ Warteliste ({len(waiting_sites)})")
            if not waiting_sites:
                st.info("Die Warteliste ist leer. Alle Slots frei.")
            for site in waiting_sites:
                with st.expander(f"[{site['priority']}] {site['location']} ({site['district']})"):
                    st.write(f"**Beschreibung:** {site['description']}")
                    st.write(f"**Kategorie:** {site['category']} / {site['subcategory']}")
                    st.write(f"**Score:** {site['score']} | **Wartetage:** {site['days_waiting']}")
                    st.warning("Wartet auf freien Slot im Bezirk / Hauptstraßen-Limit.")

    except Exception as e:
        st.info("Noch keine Datenbank oder keine Berichte vorhanden. Reiche zuerst eine Meldung im Tab 'Bürger-Meldeformular' ein.")