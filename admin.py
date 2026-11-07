"""Verwaltung: Übersicht, Tabelle, Detailansicht mit schnellen Aktionen."""
import html

import pandas as pd
import streamlit as st

import store
from ui_theme import apply_theme, get_session_id, page_header, parse_location, prio_chip, status_chip

apply_theme(wide=True)
get_session_id()
page_header("VERWALTUNG")

PRIO_LABEL = {"P1": "🔴 P1 Kritisch", "P2": "🟠 P2 Hoch", "P3": "🟢 P3 Normal"}
STATUS_LABEL = {"Gesendet": "⚪ Gesendet", "In Bearbeitung": "🟡 In Bearbeitung", "Durchgeführt": "🟢 Durchgeführt"}
RISK_COLORS = {0: "#B8D4E3", 1: "#80C3DD", 2: "#F2A93B", 3: "#D64545"}

st.markdown(
    """
<style>
.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin:4px 0 8px 0; }
.kpi { background:#fff; border:1px solid #CFE3EE; border-radius:14px; padding:14px 16px; }
.kpi-l { font-size:13px; color:#4A5565; }
.kpi-v { font-size:32px; font-weight:800; line-height:1.15; margin-top:2px; }
.alert { background:#FDECEA; border:1px solid #F0B8B2; border-left:8px solid #B71C1C; border-radius:12px;
         padding:12px 16px; font-weight:700; color:#7F1D1D; margin:8px 0; }
.ok-banner { background:#EAF7DB; border:1px solid #B5DC8D; border-radius:12px; padding:12px 16px;
             font-weight:700; color:#14400F; margin:8px 0; }
.panel { background:#fff; border:1px solid #CFE3EE; border-radius:14px; padding:16px 18px; margin-bottom:12px; }
.panel h4 { margin:0 0 8px 0; font-size:15px; font-weight:800; }
.risk { display:flex; align-items:center; gap:10px; margin:7px 0; font-size:14px; }
.risk-l { width:92px; color:#4A5565; }
.risk-track { flex:1; height:10px; background:#E6F0F5; border-radius:99px; overflow:hidden; }
.risk-fill { height:100%; border-radius:99px; }
.risk-v { width:34px; text-align:right; font-weight:700; }
.score { font-size:30px; font-weight:800; }
</style>
""",
    unsafe_allow_html=True,
)

reports = store.list_reports()


def count(pred):
    return sum(1 for r in reports if pred(r))


open_critical = count(lambda r: (r["priority"] or "").startswith("P1") and r["status"] != "Durchgeführt")


def kpi(label, value, color="#111111"):
    return f'<div class="kpi"><div class="kpi-l">{label}</div><div class="kpi-v" style="color:{color}">{value}</div></div>'


st.markdown(
    '<div class="kpis">'
    + kpi("Meldungen gesamt", len(reports))
    + kpi("Kritisch offen (P1)", open_critical, "#B71C1C" if open_critical else "#111111")
    + kpi("Neu (Gesendet)", count(lambda r: r["status"] == "Gesendet"), "#374151")
    + kpi("In Bearbeitung", count(lambda r: r["status"] == "In Bearbeitung"), "#92400E")
    + kpi("Durchgeführt", count(lambda r: r["status"] == "Durchgeführt"), "#1D5A1D")
    + "</div>",
    unsafe_allow_html=True,
)

if not reports:
    st.info("Noch keine Meldungen eingegangen. Sobald Bürger Meldungen senden, erscheinen sie hier.")
    st.page_link("home.py", label="← Zur Startseite")
    st.stop()

if open_critical:
    plural = "kritische Meldung wartet" if open_critical == 1 else "kritische Meldungen warten"
    st.markdown(f'<div class="alert">⚠️ {open_critical} {plural} auf Bearbeitung.</div>', unsafe_allow_html=True)

# --- Filter --------------------------------------------------------------
f1, f2, f3 = st.columns([2, 2, 3])
query = f1.text_input("Suche", placeholder="Ort oder Beschreibung …")
prio_sel = f2.segmented_control("Priorität", ["Alle", "P1", "P2", "P3"], default="Alle") or "Alle"
status_sel = f3.segmented_control("Status", ["Alle"] + store.STATUSES, default="Alle") or "Alle"

shown = [
    r for r in reports
    if (prio_sel == "Alle" or (r["priority"] or "")[:2] == prio_sel)
    and (status_sel == "Alle" or r["status"] == status_sel)
    and (not query or query.lower() in f'{r["location"]} {r["description"]}'.lower())
]

if not shown:
    st.warning("Keine Meldungen für diese Filter.")
    st.page_link("home.py", label="← Zur Startseite")
    st.stop()

# --- Tabelle (Zeile anklicken = Details unten) ---------------------------------
st.caption("Wichtigste Meldungen stehen oben. Zeile anklicken, um Details zu öffnen.")
df = pd.DataFrame(
    [
        {
            "Nr.": r["id"],
            "Priorität": PRIO_LABEL.get((r["priority"] or "")[:2], r["priority"]),
            "Status": STATUS_LABEL.get(r["status"], r["status"]),
            "Standort": parse_location(r["location"])[0],
            "Beschreibung": r["description"],
            "Eingang": r["created_at"],
            "Zuständige Stelle": r["department"],
        }
        for r in shown
    ]
)
event = st.dataframe(
    df,
    hide_index=True,
    width="stretch",
    height=min(60 + 36 * len(df), 320),
    on_select="rerun",
    selection_mode="single-row",
    key="report_table",
    column_config={"Nr.": st.column_config.NumberColumn("Nr.", format="%d", width="small")},
)

picked = event.selection.rows
if picked and picked[0] < len(shown):
    st.session_state["sel_id"] = shown[picked[0]]["id"]
current = next((r for r in shown if r["id"] == st.session_state.get("sel_id")), shown[0])
r = current
address, lat, lon = parse_location(r["location"])

# --- Details -------------------------------------------------------------
st.markdown(
    f'<div class="fmc-h2">Meldung Nr. {r["id"]} &nbsp; {prio_chip(r["priority"], 13)} &nbsp; {status_chip(r["status"], 13)}</div>',
    unsafe_allow_html=True,
)
left, right = st.columns([1, 1], gap="large")

with left:
    img = store.image_path(r["image_file"]) if r["image_file"] else None
    if img and img.exists():
        st.image(str(img), width="stretch")
    if lat is not None:
        st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), zoom=15, height=230)

with right:
    st.markdown(
        f"""
        <div class="panel">
          <h4>Meldung</h4>
          <div class="fmc-label" style="margin-top:0">Standort</div><div>{html.escape(address)}</div>
          <div class="fmc-label">Beschreibung</div><div>{html.escape(r["description"] or "")}</div>
          <div class="fmc-label">Eingang</div><div>{html.escape(r["created_at"] or "")}</div>
          <div class="fmc-label">Dringlichkeit laut Bürger</div><div>{r["citizen_urgency"]} von 5</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    bars = ""
    for label, key in [("Gefahr", "danger"), ("Auswirkung", "impact"), ("Dringlichkeit", "urgency")]:
        v = int(r[key] or 0)
        bars += (
            f'<div class="risk"><div class="risk-l">{label}</div>'
            f'<div class="risk-track"><div class="risk-fill" style="width:{v / 3 * 100:.0f}%;background:{RISK_COLORS[v]}"></div></div>'
            f'<div class="risk-v">{v}/3</div></div>'
        )
    hazard = (
        '<div class="alert" style="margin:10px 0 0 0">⚠️ Akute Gefahr erkannt</div>' if r["acute_hazard"] else ""
    )
    st.markdown(
        f"""
        <div class="panel">
          <div class="fmc-row"><h4>KI-Bewertung</h4><div class="score">{r["score"]}<span style="font-size:15px;color:#4A5565"> / 18</span></div></div>
          {bars}{hazard}
        </div>
        """,
        unsafe_allow_html=True,
    )
    if r["analysis"]:
        with st.expander("Analyse der KI lesen"):
            st.write(r["analysis"])

    st.markdown('<div class="fmc-step">Bearbeitung</div>', unsafe_allow_html=True)
    if r["status"] == "Gesendet":
        if st.button("▶  Bearbeitung starten", type="primary", width="stretch", key=f"start_{r['id']}"):
            store.set_status(r["id"], "In Bearbeitung")
            st.rerun()
    elif r["status"] == "In Bearbeitung":
        if st.button("✓  Als durchgeführt markieren", type="primary", width="stretch", key=f"done_{r['id']}"):
            store.set_status(r["id"], "Durchgeführt")
            st.rerun()
    else:
        st.markdown('<div class="ok-banner">✓ Diese Meldung ist erledigt.</div>', unsafe_allow_html=True)
        if st.button("Wieder öffnen", width="stretch", key=f"reopen_{r['id']}"):
            store.set_status(r["id"], "In Bearbeitung")
            st.rerun()

    dept_key = f"dept_{r['id']}"
    current_dept = r["department"] if r["department"] in store.DEPARTMENTS else store.DEPARTMENTS[0]
    st.selectbox(
        "Zuständige Stelle",
        store.DEPARTMENTS,
        index=store.DEPARTMENTS.index(current_dept),
        key=dept_key,
        on_change=lambda rid=r["id"], k=dept_key: store.set_department(rid, st.session_state[k]),
    )

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
st.page_link("home.py", label="← Zur Startseite")
