"""Meldung abgeben: Foto aufnehmen, beschreiben, Standort, Dringlichkeit."""
import html
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

import store
from geo_button import get_location
from ui_theme import MARK_SVG, apply_theme, format_location, get_session_id, page_header

load_dotenv()  # lädt GEMINI_API_KEY aus .env, bevor das Backend importiert wird

apply_theme()
sid = get_session_id()
page_header("MELDUNG ABGEBEN")

# --- 1 Foto (nur Kamera, kein Upload) ---------------------------------------
st.markdown('<div class="fmc-step">1 · Foto</div>', unsafe_allow_html=True)
photo_bytes = None
camera_key = f"camera_{st.session_state.get('camera_round', 0)}"
photo = st.camera_input("Foto aufnehmen", key=camera_key, label_visibility="collapsed")
if photo is not None:
    photo_bytes = photo.getvalue()
    if st.button("Foto wiederholen", width="stretch"):
        st.session_state["camera_round"] = st.session_state.get("camera_round", 0) + 1
        st.rerun()

# --- 2 Beschreibung ---------------------------------------------------------
st.markdown('<div class="fmc-step">2 · Problem beschreiben</div>', unsafe_allow_html=True)
description = st.text_area(
    "Beschreibung",
    placeholder="z. B. Großes Schlagloch auf der Fahrbahn",
    label_visibility="collapsed",
    height=100,
)

# --- 3 Standort (wird vom Gerät ermittelt, keine Eingabe) ---------------------
st.markdown('<div class="fmc-step">3 · Standort</div>', unsafe_allow_html=True)
st.caption("Tippen Sie auf „Standort nutzen“ und wählen Sie im Browser „Einmalig erlauben“.")


def _start_location_request():
    st.session_state["geo_req"] = st.session_state.get("geo_req", 0) + 1
    st.session_state["geo_wait"] = True
    st.session_state["geo_error"] = False


saved_geo = st.session_state.get("geo")
if saved_geo:
    address = saved_geo.get("address") or "Standort erfasst"
    st.markdown(
        f"""
        <div style="display:flex;gap:12px;align-items:flex-start;background:#EAF7DB;border:1px solid #B5DC8D;
                    border-radius:14px;padding:14px 16px;margin-bottom:14px;">
          <div style="flex:none;width:36px;height:36px;border-radius:10px;background:#2B2A6E;display:flex;
                      align-items:center;justify-content:center;">{MARK_SVG}</div>
          <div><div style="font-weight:800;font-size:15px;line-height:1.3;">{html.escape(address)}</div>
          <div class="fmc-muted" style="margin-top:2px;">GPS {saved_geo["lat"]:.5f}, {saved_geo["lon"]:.5f}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.button("Standort neu ermitteln", on_click=_start_location_request, key="geo_again", width="stretch")
else:
    st.button(
        "Standort nutzen", icon=":material/location_on:", on_click=_start_location_request,
        key="geo_go", width="stretch",
    )

if st.session_state.get("geo_wait"):
    st.caption("Standort wird ermittelt …")
    answer = get_location(request=st.session_state["geo_req"], key=f"geo_{st.session_state['geo_req']}")
    if answer is not None:
        st.session_state["geo_wait"] = False
        if answer.get("lat") is not None:
            st.session_state["geo"] = answer
        else:
            st.session_state["geo_error"] = True
        st.rerun()

if st.session_state.get("geo_error"):
    st.markdown(
        """
        <div style="background:#FDECEA;border:1px solid #F0B8B2;border-left:8px solid #B71C1C;border-radius:14px;
                    padding:12px 16px;">
          <div style="font-weight:800;font-size:14px;color:#7F1D1D;">Standort konnte nicht ermittelt werden</div>
          <div style="font-size:13px;color:#5A2A2A;margin-top:2px;line-height:1.4;">Bitte erlauben Sie den Zugriff
          auf Ihren Standort („Einmalig erlauben“) und tippen Sie erneut auf „Standort nutzen“.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

saved_geo = st.session_state.get("geo")
location = format_location(saved_geo) if saved_geo else None

# --- 4 Dringlichkeit --------------------------------------------------------
st.markdown('<div class="fmc-step">4 · Wie dringend finden Sie es?</div>', unsafe_allow_html=True)
urgency = st.select_slider(
    "Dringlichkeit", options=[1, 2, 3, 4, 5], value=3, label_visibility="collapsed"
)
st.caption("1 = nicht eilig · 5 = sehr dringend")

if st.button("Meldung absenden", type="primary", width="stretch"):
    problems = []
    if photo_bytes is None:
        problems.append("Bitte ein Foto aufnehmen.")
    if not description.strip():
        problems.append("Bitte das Problem kurz beschreiben.")
    if not location:
        problems.append("Bitte den Standort nutzen.")
    for p in problems:
        st.warning(p)

    if not problems:
        result, error = None, None
        with st.spinner("Die KI prüft Ihre Meldung …"):
            try:
                from report_pipeline import process_report

                tmp = Path("ui_data") / f"tmp_{sid}.jpg"
                tmp.parent.mkdir(exist_ok=True)
                tmp.write_bytes(photo_bytes)
                for _attempt in range(3):
                    try:
                        result = process_report(str(tmp), description, location)
                        error = None
                        break
                    except Exception as exc:  # z. B. 503 UNAVAILABLE
                        error = exc
                        time.sleep(2)
            except Exception as exc:
                error = exc
            finally:
                if "tmp" in locals() and tmp.exists():
                    tmp.unlink()

        if result is None:
            st.error("Die KI ist gerade ausgelastet. Bitte in einer Minute noch einmal versuchen.")
        else:
            validation = result.get("validation")
            if validation is None and result.get("priority"):
                validation = {"status": "VALID"}  # Backend liefert bei VALID noch kein Feld
            if validation and validation.get("status") == "VALID":
                report_id = store.add_report(result, photo_bytes, ".jpg", urgency, sid)
                st.session_state["last"] = {
                    "kind": "ok", "result": result, "urgency": urgency, "id": report_id,
                }
            else:
                st.session_state["last"] = {"kind": "rejected", "validation": validation}
            st.switch_page("result.py")

st.page_link("home.py", label="← Zurück zur Startseite")
