"""Startseite: Willkommen, Knopf zum Melden, frühere Meldungen."""
import html

import streamlit as st

import store
from ui_theme import apply_theme, get_session_id, page_header, status_chip

apply_theme()
sid = get_session_id()
page_header("STARTSEITE")

st.markdown(
    """
    <div class="fmc-hero"><div class="fmc-hero-in">
      <div class="fmc-hero-title">Willkommen<br><span class="fmc-hl">in Pforzheim</span></div>
      <p>Sie sehen ein Problem in der Stadt – ein Schlagloch, Müll oder eine defekte Laterne?
      Melden Sie es mit einem Foto. Die KI prüft Ihre Meldung und leitet sie an die Stadtverwaltung weiter.</p>
    </div></div>
    """,
    unsafe_allow_html=True,
)

if st.button("Neues Problem melden", type="primary", width="stretch"):
    st.switch_page("report.py")

st.markdown('<div class="fmc-h2">Frühere Meldungen</div>', unsafe_allow_html=True)
reports = store.list_reports(session_id=sid)

if not reports:
    st.markdown(
        """
        <div class="fmc-card" style="text-align:center;padding:28px 16px;">
          <div style="font-size:16px;font-weight:800;">Noch keine Meldungen</div>
          <div class="fmc-muted" style="margin-top:4px;">Ihre gesendeten Meldungen erscheinen hier.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    for r in reports:
        st.markdown(
            f"""
            <div class="fmc-card">
              <div class="fmc-row">
                <div>
                  <div style="font-size:16px;font-weight:800;">Nr. {r["id"]}</div>
                  <div class="fmc-muted">{html.escape(r["created_at"] or "")}</div>
                </div>
                {status_chip(r["status"])}
              </div>
              <div style="font-size:14px;margin-top:6px;">{html.escape((r["description"] or "")[:90])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
st.page_link("admin.py", label="Verwaltung", icon="🔒")
