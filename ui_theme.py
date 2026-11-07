"""Farben, Kopfzeile und kleine HTML-Bausteine (Pforzheim-Look)."""
import html
import re
import uuid

import streamlit as st

INK = "#111111"
MUTED = "#4A5565"
NAVY = "#2B2A6E"
SKY = "#80C3DD"
LIME = "#C0E598"
BORDER = "#CFE3EE"

STATUS_STYLE = {
    "Gesendet": ("#E5E7EB", "#374151"),
    "In Bearbeitung": ("#FFE98A", "#5C4300"),
    "Durchgeführt": ("#C9EDAA", "#1D5A1D"),
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700;800&display=swap');

html, body, .stApp, button, input, textarea, select,
[data-testid="stMarkdownContainer"] {
    font-family: 'Open Sans', system-ui, sans-serif !important;
}
[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stDecoration"], footer { display: none !important; }

.block-container, [data-testid="stMainBlockContainer"] {
    max-width: @@MAXW@@;
    padding: 0 1.25rem 3rem 1.25rem !important;
}
[data-testid="stVerticalBlock"] { gap: 0.6rem !important; }
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-primaryFormSubmit"] p {
    font-weight: 800 !important; font-size: 17px !important; color: #111111 !important;
}
[data-testid="stBaseButton-secondary"] p { font-weight: 700 !important; color: #111111 !important; }

/* Primäre Knöpfe: grün mit schwarzem Rand wie auf der Stadt-Website */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
    background: #C0E598 !important; color: #111111 !important;
    border: 2px solid #111111 !important; border-radius: 12px !important;
    font-weight: 800 !important; min-height: 56px; font-size: 17px !important;
}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
    background: #B0DA84 !important; color: #111111 !important;
}
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"] {
    background: #FFFFFF !important; color: #111111 !important;
    border: 2px solid #111111 !important; border-radius: 12px !important;
    font-weight: 700 !important; min-height: 48px;
}

.stApp, [data-testid="stAppViewContainer"], section.main { overflow-x: hidden !important; }
.fmc-header-wrap, .fmc-hero {
    width: 100vw; margin-left: calc(50% - 50vw) !important; margin-right: calc(50% - 50vw) !important;
    box-sizing: border-box;
}
.fmc-header-wrap { margin-bottom: 0.4rem !important; }
.fmc-header, .fmc-band, .fmc-hero-in {
    padding-left: max(20px, calc((100vw - @@MAXW@@) / 2 + 1.25rem)) !important;
    padding-right: max(20px, calc((100vw - @@MAXW@@) / 2 + 1.25rem)) !important;
}
.fmc-header {
    background: #FFFFFF; padding: 14px 20px; display: flex; align-items: center;
    gap: 12px; border-bottom: 1px solid #CFE3EE;
}
.fmc-mark {
    width: 40px; height: 40px; border-radius: 10px; background: #2B2A6E;
    display: flex; align-items: center; justify-content: center; flex: none;
}
.fmc-name { color: #2B2A6E; font-weight: 800; font-size: 19px; line-height: 1.1; }
.fmc-band {
    background: #C0E598; padding: 10px 20px; font-size: 13px; font-weight: 800;
    letter-spacing: 0.08em; color: #111111;
}
.fmc-hero { background: #80C3DD; padding: 36px 0 96px 0; margin-top: -0.6rem !important; }
[data-testid="stElementContainer"]:has(.fmc-hero) + [data-testid="stElementContainer"] {
    margin-top: -84px; position: relative; z-index: 2;
}
.fmc-hero-in { }
.fmc-hero-title { font-size: 44px; font-weight: 800; line-height: 1.12; color: #111111; }
.fmc-hl { background: #C0E598; padding: 0 10px; }
.fmc-hero p { font-size: 16px; line-height: 1.55; margin: 16px 0 22px 0; color: #111111; }
.fmc-card {
    background: #FFFFFF; border: 1px solid #CFE3EE; border-radius: 14px;
    padding: 14px 16px; margin-bottom: 12px;
}
.fmc-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.fmc-muted { color: #4A5565; font-size: 13px; }
.fmc-label { color: #4A5565; font-size: 12px; margin-top: 8px; }
.fmc-h2 { font-size: 20px; font-weight: 800; margin: 30px 0 10px 0; }
.fmc-step { font-size: 14px; font-weight: 800; margin: 14px 0 4px 0; }
</style>
"""

MARK_SVG = (
    '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#80C3DD" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M12 21s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/>'
    '<circle cx="12" cy="9" r="2.5"/></svg>'
)


def apply_theme(wide=False):
    """Schriftart, Knöpfe und Layout setzen. Zuerst auf jeder Seite aufrufen."""
    st.markdown(
        CSS.replace("@@MAXW@@", "1200px" if wide else "560px"),
        unsafe_allow_html=True,
    )


def page_header(band):
    """Weiße Kopfzeile mit Logo plus grünes Band mit dem Seitentitel."""
    st.markdown(
        f"""
        <div class="fmc-header-wrap">
          <div class="fmc-header">
            <div class="fmc-mark">{MARK_SVG}</div>
            <div class="fmc-name">FixMyCity AI</div>
          </div>
          <div class="fmc-band">{html.escape(band)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_chip(status, size=12):
    """Farbige Status-Marke als HTML (Gesendet grau, In Bearbeitung gelb, Durchgeführt grün)."""
    background, color = STATUS_STYLE.get(status, ("#E5E7EB", "#374151"))
    return (
        f'<span style="display:inline-block;padding:5px 11px;border-radius:999px;'
        f"background:{background};color:{color};font-weight:700;font-size:{size}px;"
        f'white-space:nowrap;">{html.escape(status)}</span>'
    )


def get_session_id():
    """Kennung dieses Browsers/dieser Sitzung (für 'Frühere Meldungen').

    Bleibt beim Neuladen erhalten, weil sie in der Adresse (?sid=...) steht.
    Später durch ein echtes Login (z. B. Stadt-App) ersetzbar.
    """
    if "sid" not in st.session_state:
        st.session_state["sid"] = st.query_params.get("sid") or uuid.uuid4().hex[:12]
    st.query_params["sid"] = st.session_state["sid"]
    return st.session_state["sid"]


PRIO_STYLE = {
    "P1": ("#FDECEA", "#B71C1C", "P1 · Kritisch"),
    "P2": ("#FFF1D6", "#92400E", "P2 · Hoch"),
    "P3": ("#E4F4D6", "#14532D", "P3 · Normal"),
}


def prio_chip(priority, size=12):
    """Farbige Prioritäts-Marke aus Text wie 'P1 - Critical'."""
    background, color, label = PRIO_STYLE.get((priority or "")[:2], ("#E5E7EB", "#374151", priority or "–"))
    return (
        f'<span style="display:inline-block;padding:5px 11px;border-radius:999px;'
        f"background:{background};color:{color};font-weight:700;font-size:{size}px;"
        f'white-space:nowrap;">{html.escape(label)}</span>'
    )


_COORDS = re.compile(r"\(?\s*(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)\s*\)?\s*$")


def format_location(geo):
    """Text für Speicherung/KI: 'Adresse (lat, lon)' oder nur 'lat, lon'."""
    coords = f"{geo['lat']:.5f}, {geo['lon']:.5f}"
    return f"{geo['address']} ({coords})" if geo.get("address") else coords


def parse_location(text):
    """Zerlegt den Standort-Text in (Anzeigetext, lat, lon); lat/lon sind None, falls unbekannt."""
    text = text or ""
    match = _COORDS.search(text)
    if not match:
        return text, None, None
    lat, lon = float(match.group(1)), float(match.group(2))
    shown = text[: match.start()].strip() or f"{lat:.5f}, {lon:.5f}"
    return shown, lat, lon
