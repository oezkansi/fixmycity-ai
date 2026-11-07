"""Ergebnis-Ansichten für Bürger: gültige Meldung und abgelehnte Meldung."""
import html

import streamlit as st

from ui_theme import parse_location, status_chip


def _rating_pills(selected):
    pills = ""
    for number in range(1, 6):
        if number == selected:
            style = "border:2px solid #111;background:#C0E598;font-weight:800;"
        else:
            style = "border:1px solid #B8CFDD;background:#FFFFFF;font-weight:600;"
        pills += (
            f'<div style="flex:1;height:44px;display:flex;align-items:center;'
            f'justify-content:center;border-radius:12px;{style}">{number}</div>'
        )
    return (
        f'<div style="display:flex;gap:8px;">{pills}</div>'
        '<div style="display:flex;justify-content:space-between;font-size:12px;'
        'color:#4A5565;margin-top:4px;"><span>nicht eilig</span>'
        "<span>sehr dringend</span></div>"
    )


def render_rejection(validation):
    """Rote Karte: Meldung wurde von der KI nicht weitergeleitet."""
    status = validation.get("status") if validation else "UNCERTAIN"
    reason = html.escape(validation.get("reason", "")) if validation else ""

    if status == "INVALID":
        title = "Meldung nicht weitergeleitet"
        text = "Auf dem Foto konnte kein gültiger kommunaler Schaden bestätigt werden."
    else:
        title = "Weitere Informationen erforderlich"
        text = "Bitte ergänze deine Meldung oder lade ein besseres Foto hoch."

    st.markdown(
        f"""
        <div style="background:#FDECEA;border:1px solid #F0B8B2;border-left:8px solid #B71C1C;
                    border-radius:14px;padding:16px 18px;margin-bottom:12px;">
          <div style="font-size:22px;font-weight:800;color:#7F1D1D;line-height:1.2;">{title}</div>
          <div style="font-size:14px;line-height:1.5;color:#5A2A2A;margin-top:6px;">{text}</div>
        </div>
        <div class="fmc-card">
          <div class="fmc-muted">Begründung der KI</div>
          <div style="font-size:15px;line-height:1.55;margin-top:4px;">{reason}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_result(result, citizen_urgency=None, report_id=None):
    """Ergebnis einer gültigen Meldung für Bürger (ohne Priorität und Risikowerte)."""
    nummer = f"Nr. {report_id}" if report_id is not None else "Ihre Meldung"
    st.markdown(
        f"""
        <div style="background:#EAF7DB;border:1px solid #B5DC8D;border-radius:14px;
                    padding:14px 16px;margin-bottom:12px;">
          <div style="font-size:16px;font-weight:800;color:#14400F;">Danke! Meldung {html.escape(nummer)} ist eingegangen.</div>
          <div style="font-size:13px;line-height:1.45;color:#2B4D24;margin-top:4px;">
            Sie wurde an die Stadtverwaltung weitergeleitet.</div>
          <div style="margin-top:8px;font-size:13px;font-weight:700;">Status: {status_chip("Gesendet")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if citizen_urgency is not None:
        st.markdown(
            f"""
            <div class="fmc-card">
              <div style="font-size:15px;font-weight:800;margin-bottom:8px;">Wie dringend finden Sie es?</div>
              {_rating_pills(citizen_urgency)}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="fmc-card">
          <div style="font-size:15px;font-weight:800;">Ihre Meldung</div>
          <div class="fmc-label">Standort</div>
          <div style="font-size:15px;">{html.escape(parse_location(result["location"])[0])}</div>
          <div class="fmc-label">Beschreibung</div>
          <div style="font-size:15px;line-height:1.45;">{html.escape(result["description"])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if result.get("image_analysis"):
        with st.expander("🤖 Analyse der KI anzeigen"):
            st.write(result["image_analysis"])
