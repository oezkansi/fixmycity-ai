import streamlit as st
import streamlit.components.v1 as components

import json
import re
import base64

from task_assignment import recommend_task

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import cm

from database import (
    load_reports,
    save_approval,
    load_approvals,
    get_approval,
    update_report_status
)
from existing_duplicates import find_existing_duplicates
from smart_delegation import build_smart_queue

# ==================================================
# SEITENKONFIGURATION
# ==================================================

st.set_page_config(
    page_title="FixMyCity AI | Verwaltung",
    layout="wide"
)

st.title("FixMyCity AI")
st.subheader("Intelligentes Verwaltungsdashboard")

st.info(
    "KI-gestützte Entscheidungsunterstützung für die Stadtverwaltung"
)


# ==================================================
# DATEN LADEN
# ==================================================

try:
    reports = load_reports()

except Exception as e:
    st.error(f"Fehler beim Laden der Meldungen: {e}")
    st.stop()


# ==================================================
# HILFSFUNKTIONEN
# ==================================================

def parse_value(value):

    if value is None:
        return None

    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value

    return value


def safe_text(value):

    if value is None or value == "":
        return "Nicht verfügbar"

    return str(value)


def get_priority(report):

    priority = parse_value(report.get("priority"))

    if isinstance(priority, dict):
        priority = (
            priority.get("priority")
            or priority.get("level")
            or priority.get("priority_level")
            or priority.get("label")
        )

    return safe_text(priority) if priority else "Nicht bewertet"


def get_priority_rank(report):

    priority = get_priority(report).strip().lower()

    if priority.startswith("p1") or priority in ("kritisch", "critical"):
        return 1

    if priority.startswith("p2") or priority in ("hoch", "high"):
        return 2

    if priority.startswith("p3"):
        return 3

    if priority.startswith("p4"):
        return 4

    return 5


def is_high_priority(report):

    return get_priority_rank(report) <= 2


def translate_status(status):

    translations = {
        "VALID": "Gültig",
        "INVALID": "Ungültig",
        "UNCERTAIN": "Nicht eindeutig",
        "TRUE": "Ja",
        "FALSE": "Nein"
    }

    return translations.get(
        str(status).upper(),
        safe_text(status)
    )


def risk_label(value):

    try:
        value = int(value)
    except (ValueError, TypeError):
        return "Nicht verfügbar"

    labels = {
        0: "Sehr gering",
        1: "Gering",
        2: "Mittel",
        3: "Hoch"
    }

    return f"{value}/3 – {labels.get(value, 'Unbekannt')}"


def get_urgency(report):

    try:
        return int(report.get("citizen_urgency") or 0)
    except (ValueError, TypeError):
        return 0


# ==================================================
# DUPLIKATERKENNUNG
# ==================================================

try:
    duplicate_groups = find_existing_duplicates(reports)

except Exception as e:
    st.error(f"Fehler bei der Duplikaterkennung: {e}")
    duplicate_groups = []


# Alle Meldungsnummern aus Duplikatgruppen sammeln

grouped_report_ids = set()

for group in duplicate_groups:

    for report in group["reports"]:
        grouped_report_ids.add(report["id"])


# Einzelmeldungen ohne erkannte Duplikate

single_reports = [
    report
    for report in reports
    if report["id"] not in grouped_report_ids
]


# ==================================================
# SCHADENSFÄLLE ERSTELLEN
# ==================================================

damage_cases = []


# Jede Duplikatgruppe wird zu einem Schadensfall

for group in duplicate_groups:

    group_reports = group["reports"]

    original = min(
        group_reports,
        key=lambda report: report["id"]
    )

    highest_priority_report = min(
        group_reports,
        key=get_priority_rank
    )

    statuses = [
        str(report.get("status") or "").strip()
        for report in group_reports
    ]

    if "In Bearbeitung" in statuses:
        case_status = "In Bearbeitung"

    elif "Offen" in statuses:
        case_status = "Offen"

    elif statuses and all(
        status == "Erledigt"
        for status in statuses
    ):
        case_status = "Erledigt"

    else:
        case_status = original.get("status") or "Offen"

    damage_cases.append({
        "id": original["id"],
        "description": original.get("description"),
        "location": original.get("location"),
        "citizen_urgency": max(
            get_urgency(report)
            for report in group_reports
        ),
        "priority_report": highest_priority_report,
        "status": case_status,
        "created_at": original.get("created_at"),
        "report_count": len(group_reports),
        "report_ids": sorted(
            report["id"]
            for report in group_reports
        ),
        "is_duplicate_group": True,
        "original_report": original,
        "confirmed": group.get("confirmed", False)
    })


# Einzelmeldungen ebenfalls aufnehmen

for report in single_reports:

    damage_cases.append({
        "id": report["id"],
        "description": report.get("description"),
        "location": report.get("location"),
        "citizen_urgency": get_urgency(report),
        "priority_report": report,
        "status": report.get("status") or "Offen",
        "created_at": report.get("created_at"),
        "report_count": 1,
        "report_ids": [report["id"]],
        "is_duplicate_group": False,
        "original_report": report,
        "confirmed": True
    })


damage_cases.sort(
    key=lambda case: case["id"],
    reverse=True
)


# ==================================================
# DASHBOARD-KENNZAHLEN
# ==================================================

total_reports = len(reports)

total_damage_cases = len(damage_cases)

total_duplicates = total_reports - total_damage_cases

high_priority_cases = sum(
    is_high_priority(case["priority_report"])
    for case in damage_cases
)

open_cases = sum(
    case["status"] == "Offen"
    for case in damage_cases
)

in_progress_cases = sum(
    case["status"] == "In Bearbeitung"
    for case in damage_cases
)


# ==================================================
# STANDORTBEWERTUNG
# ==================================================

def get_location_assessment(report):

    citizen_lat = report.get("citizen_latitude")
    citizen_lon = report.get("citizen_longitude")

    damage_lat = report.get("damage_latitude")
    damage_lon = report.get("damage_longitude")

    accuracy = report.get("gps_accuracy")
    distance = report.get("distance_to_damage")

    if citizen_lat is not None and citizen_lon is not None:

        citizen_location = (
            f"{float(citizen_lat):.6f}, "
            f"{float(citizen_lon):.6f}"
        )

    else:
        citizen_location = "Nicht verfügbar"

    if damage_lat is not None and damage_lon is not None:

        damage_location = (
            f"{float(damage_lat):.6f}, "
            f"{float(damage_lon):.6f}"
        )

        location_status = "Vom Bürger auf der Karte markiert"

    else:
        damage_location = "Nicht bestätigt"
        location_status = "Schadensstandort nicht bestätigt"

    if accuracy is not None:
        accuracy_text = f"± {float(accuracy):.1f} m"
    else:
        accuracy_text = "Nicht verfügbar"

    if distance is not None:
        distance_text = f"{float(distance):.1f} m"
    else:
        distance_text = "Nicht verfügbar"

    return {
        "citizen_location": citizen_location,
        "damage_location": damage_location,
        "accuracy": accuracy_text,
        "distance": distance_text,
        "status": location_status
    }


# ==================================================
# BILDANALYSE AUFBEREITEN
# ==================================================

def get_image_bullets(report):

    analysis = parse_value(
        report.get("image_analysis")
    )

    if not analysis:
        return ["Keine Bildanalyse verfügbar"]

    if isinstance(analysis, dict):

        bullets = []

        for key, value in analysis.items():

            if value is not None and value != "":
                label = key.replace("_", " ").title()
                bullets.append(f"{label}: {value}")

        return bullets or ["Keine Bildanalyse verfügbar"]

    if isinstance(analysis, list):

        return [
            str(item)
            for item in analysis
            if item
        ] or ["Keine Bildanalyse verfügbar"]

    text = str(analysis).replace("**", "")

    sections = re.split(
        r"\n\s*\d+\.\s+",
        text
    )

    bullets = []

    for section in sections:

        section = section.strip()

        if not section:
            continue

        if section.lower().startswith("hier ist die analyse"):
            continue

        if "\n" in section:

            heading, content = section.split("\n", 1)

            heading = heading.strip().rstrip(":")
            content = content.strip()

            if not content:
                continue

            if "zusätzliche risiken" in heading.lower():

                risks = re.split(
                    r"\n\s*[*-]\s+",
                    content
                )

                for risk in risks:

                    risk = risk.strip().lstrip("*- ").strip()

                    if risk:
                        bullets.append(
                            f"Zusätzliches Risiko: {risk}"
                        )

            else:

                content = " ".join(content.split())

                bullets.append(
                    f"{heading}: {content}"
                )

    if not bullets:
        return [" ".join(text.split())]

    return bullets


# ==================================================
# PDF-BERICHT
# ==================================================

def create_ai_report_pdf(report):

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=(21 * cm, 29.7 * cm),
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="CustomTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=25,
            textColor=colors.HexColor("#14213D"),
            alignment=TA_CENTER,
            spaceAfter=12
        )
    )

    styles.add(
        ParagraphStyle(
            name="CustomSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#14213D"),
            spaceBefore=14,
            spaceAfter=8
        )
    )

    styles.add(
        ParagraphStyle(
            name="CustomBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=14,
            spaceAfter=6
        )
    )

    story = []

    def paragraph(text):

        return Paragraph(
            escape(safe_text(text)),
            styles["CustomBody"]
        )

    def add_section(title):

        story.append(
            Paragraph(
                escape(title),
                styles["CustomSection"]
            )
        )

    def add_line(label, value):

        story.append(
            Paragraph(
                f"<b>{escape(label)}:</b> "
                f"{escape(safe_text(value))}",
                styles["CustomBody"]
            )
        )

    def add_bullets(items):

        for item in items:

            story.append(
                Paragraph(
                    f"&#8226; {escape(str(item))}",
                    styles["CustomBody"]
                )
            )

    def add_table(rows):

        table_data = []

        for row in rows:

            table_data.append([
                paragraph(cell)
                for cell in row
            ])

        table = Table(
            table_data,
            colWidths=[6 * cm, 11 * cm],
            repeatRows=1,
            hAlign="LEFT"
        )

        table.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#E8EDF5")
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#CCCCCC")
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP"
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    8
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    8
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                )
            ])
        )

        story.append(table)

    story.append(
        Paragraph(
            "FixMyCity AI",
            styles["CustomTitle"]
        )
    )

    story.append(
        Paragraph(
            "AI Decision Report",
            styles["CustomTitle"]
        )
    )

    story.append(
        paragraph(
            "Vollständiger Bericht mit den gespeicherten "
            "KI-Analyseergebnissen"
        )
    )

    story.append(Spacer(1, 0.4 * cm))

    # 1. ALLGEMEINE INFORMATIONEN

    add_section("1. Allgemeine Informationen")

    add_line("Meldungsnummer", report.get("id"))
    add_line("Beschreibung", report.get("description"))
    add_line("Schadensstandort", report.get("location"))

    add_line(
        "Dringlichkeit Bürger",
        f"{safe_text(report.get('citizen_urgency'))}/5"
    )

    add_line("Eingegangen am", report.get("created_at"))
    add_line("Bearbeitungsstatus", report.get("status"))

    # 2. LOCATION ASSESSMENT

    add_section("2. Location Assessment – Standortbewertung")

    location_data = get_location_assessment(report)

    add_table([
        ["Standortinformation", "Ergebnis"],
        ["GPS-Standort des Bürgers", location_data["citizen_location"]],
        ["GPS-Genauigkeit", location_data["accuracy"]],
        ["Markierter Schadensstandort", location_data["damage_location"]],
        ["Abstand zwischen Bürger und Schaden", location_data["distance"]],
        ["Standortstatus", location_data["status"]]
    ])

    story.append(Spacer(1, 0.3 * cm))

    story.append(
        paragraph(
            "Hinweis zur Standortbewertung: "
            "Die GPS-Koordinaten kennzeichnen zunächst "
            "die Position des Meldenden. "
            "Die tatsächliche Schadensstelle kann davon "
            "abweichen. Der Kartenmarker wurde vom Bürger "
            "gesetzt und stellt keine unabhängige "
            "Verifizierung dar. Vor der Entsendung eines "
            "Reparaturteams sollte die Position anhand "
            "des Kartenmarkers, des Fotos und der "
            "Ortsbeschreibung überprüft werden."
        )
    )

    # 3. AI VALIDATION

    add_section("3. AI Validation")

    validation = parse_value(report.get("validation"))

    if isinstance(validation, dict):

        add_line(
            "Validierungsstatus",
            translate_status(validation.get("status"))
        )

        add_line(
            "Erkannter Schaden",
            validation.get("detected_problem")
        )

        add_line(
            "Begründung",
            validation.get("reason")
        )

    else:
        add_line("Validierung", validation)

    # 4. AI IMAGE ANALYSIS

    add_section("4. AI Image Analysis")

    add_bullets(
        get_image_bullets(report)
    )

    # 5. AI RISK ASSESSMENT

    add_section("5. AI Risk Assessment")

    risks = parse_value(report.get("risk_factors"))

    if isinstance(risks, dict):

        acute_hazard = risks.get("acute_hazard")

        if acute_hazard is True:
            acute_text = "Ja"
        elif acute_hazard is False:
            acute_text = "Nein"
        else:
            acute_text = "Nicht verfügbar"

        add_table([
            ["Risikofaktor", "KI-Bewertung"],
            ["Gefährlichkeit", risk_label(risks.get("danger"))],
            ["Auswirkungen", risk_label(risks.get("impact"))],
            ["Dringlichkeit", risk_label(risks.get("urgency"))],
            ["Akute Gefahr", acute_text]
        ])

    else:
        story.append(
            paragraph("Keine Risikobewertung verfügbar")
        )

    # 6. AI PRIORITIZATION

    add_section("6. AI Prioritization")

    add_line(
        "Ermittelte KI-Priorität",
        get_priority(report)
    )

    story.append(Spacer(1, 0.2 * cm))

    story.append(
        paragraph("Erweiterte Prioritätsformel:")
    )

    story.append(
        paragraph(
            "Score = (10 × S × R + 1,2 × U + 0,5 × T) × W"
        )
    )

    add_table([
        ["Faktor", "Bedeutung"],
        ["S", "Schweregrad des Schadens"],
        ["R", "Straßenfaktor"],
        ["U", "Dringlichkeit des Bürgers"],
        ["T", "Wartezeit in Tagen"],
        ["W", "Wetterfaktor"]
    ])

    story.append(Spacer(1, 0.2 * cm))

    priority_data = parse_value(report.get("priority"))

    if isinstance(priority_data, dict):

        score = priority_data.get("score")

        if score is not None:
            add_line(
                "Gespeicherter Prioritätsscore",
                score
            )

    story.append(
        paragraph(
            "Hinweis: Die dargestellte Formel ist das "
            "erweiterte Priorisierungsmodell. "
            "Eine vollständige Berechnung mit allen "
            "Faktorwerten ist für diese Meldung "
            "noch nicht dokumentiert."
        )
    )

    # 7. DEPARTMENT AND RESPONSIBILITY

    add_section("7. Department and Responsibility")

    responsibility = parse_value(
        report.get("responsibility")
    )

    if isinstance(responsibility, dict):

        add_line(
            "Zuständigkeitsstatus",
            translate_status(responsibility.get("status"))
        )

        add_line(
            "Begründung",
            responsibility.get("reason")
        )

        if responsibility.get("department"):

            add_line(
                "Empfohlene Abteilung",
                responsibility.get("department")
            )

    else:
        add_line("Zuständigkeit", responsibility)

    # 8. HUMAN REVIEW

    add_section("8. Human Review")

    story.append(
        paragraph(
            "Dieser Bericht enthält KI-generierte "
            "Analysen und Empfehlungen."
        )
    )

    story.append(
        paragraph(
            "Eine endgültige Verwaltungsentscheidung "
            "ist durch diesen Bericht nicht dokumentiert."
        )
    )

    document.build(story)

    buffer.seek(0)

    return buffer.getvalue()


# ==================================================
# PDF IN NEUEM TAB ÖFFNEN
# ==================================================

def show_pdf_open_button(pdf_data):

    pdf_base64 = base64.b64encode(
        pdf_data
    ).decode("utf-8")

    html_code = f"""
    <button
        onclick="openPDF()"
        style="
            background-color: #14213D;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 20px;
            font-size: 15px;
            cursor: pointer;
            width: 100%;
        "
    >
        AI Decision Report öffnen
    </button>

    <script>
    function openPDF() {{

        const base64 = "{pdf_base64}";

        const binary = atob(base64);

        const bytes = new Uint8Array(binary.length);

        for (let i = 0; i < binary.length; i++) {{
            bytes[i] = binary.charCodeAt(i);
        }}

        const blob = new Blob(
            [bytes],
            {{ type: "application/pdf" }}
        );

        const url = URL.createObjectURL(blob);

        const newWindow = window.open(
            url,
            "_blank"
        );

        if (!newWindow) {{
            alert(
                "Bitte Pop-ups für diese Seite erlauben."
            );
        }}
    }}
    </script>
    """

    components.html(
        html_code,
        height=65
    )


# ==================================================
# VERWALTUNGSÜBERSICHT
# ==================================================

st.subheader("Verwaltungsübersicht")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Eingegangene Meldungen",
        total_reports
    )

with col2:
    st.metric(
        "Schadensfälle",
        total_damage_cases
    )

with col3:
    st.metric(
        "Mögliche Duplikate",
        total_duplicates
    )

with col4:
    st.metric(
        "Hohe Priorität",
        high_priority_cases
    )


col5, col6 = st.columns(2)

with col5:
    st.metric(
        "Offene Schadensfälle",
        open_cases
    )

with col6:
    st.metric(
        "In Bearbeitung",
        in_progress_cases
    )


st.caption(
    "Schadensfälle werden anhand automatisch erkannter "
    "Duplikatgruppen zusammengefasst. "
    "Die endgültige Bestätigung erfolgt durch die Verwaltung."
)

st.divider()


# ==================================================
# AKTUELLE SCHADENSFÄLLE
# ==================================================

st.subheader("Aktuelle Schadensfälle")

st.caption(
    "Jeder automatisch erkannte Schadensfall erscheint "
    "in dieser Übersicht nur einmal."
)

if damage_cases:

    dashboard_data = []

    for case in damage_cases:

        dashboard_data.append({
            "Schadensfall": f"#{case['id']}",
            "Beschreibung": case["description"],
            "Standort": case["location"],
            "Bürgerdringlichkeit": case["citizen_urgency"],
            "KI-Priorität": get_priority(
                case["priority_report"]
            ),
            "Status": case["status"],
            "Anzahl Meldungen": case["report_count"],
            "Mögliche Duplikate": case["report_count"] - 1,
            "Eingegangen am": case["created_at"]
        })

    st.dataframe(
        dashboard_data,
        width="stretch",
        hide_index=True
    )

else:
    st.info("Aktuell liegen keine Schadensfälle vor.")


st.divider()


# ==================================================
# ALLE EINGEGANGENEN MELDUNGEN
# ==================================================

with st.expander("Alle eingegangenen Meldungen anzeigen"):

    st.caption(
        "Hier bleiben sämtliche ursprünglichen Meldungen "
        "einschließlich möglicher Duplikate sichtbar."
    )

    all_reports_data = []

    for report in reports:

        all_reports_data.append({
            "Meldungsnummer": report.get("id"),
            "Beschreibung": report.get("description"),
            "Standort": report.get("location"),
            "KI-Priorität": get_priority(report),
            "Status": report.get("status"),
            "Eingegangen am": report.get("created_at")
        })

    st.dataframe(
        all_reports_data,
        width="stretch",
        hide_index=True
    )


st.divider()


# ==================================================
# AI MANAGEMENT CENTER
# ==================================================

st.subheader("AI Management Center")

tab1, tab2, tab3, tab4 = st.tabs([
    "AI Reports",
    "Duplikate",
    "Smart Delegation",
    "Freigaben"
])


# ==================================================
# AI REPORTS
# ==================================================

with tab1:

    st.subheader("KI-Entscheidungsreports")

    if not reports:

        st.info(
            "Es liegen noch keine Schadensmeldungen vor."
        )

    else:

        selected_report = st.selectbox(
            "Schadensmeldung auswählen",
            options=reports,
            format_func=lambda report: (
                f"Meldung {report['id']} - "
                f"{str(report.get('description') or '')[:60]}"
            )
        )

        st.divider()

        st.subheader("Meldungsübersicht")

        st.write(
            "Meldungsnummer:",
            selected_report.get("id")
        )

        st.write(
            "Beschreibung:",
            selected_report.get("description")
        )

        st.write(
            "Schadensstandort:",
            selected_report.get("location")
        )

        st.write(
            "KI-Priorität:",
            get_priority(selected_report)
        )

        st.write(
            "Bearbeitungsstatus:",
            selected_report.get("status")
        )

        st.divider()

        # LOCATION ASSESSMENT

        st.subheader(
            "Location Assessment – Standortbewertung"
        )

        location_data = get_location_assessment(
            selected_report
        )

        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "GPS-Genauigkeit",
                location_data["accuracy"]
            )

        with col2:

            st.metric(
                "Abstand zum Schaden",
                location_data["distance"]
            )

        st.write(
            "**GPS-Standort des Bürgers:**",
            location_data["citizen_location"]
        )

        st.write(
            "**Markierter Schadensstandort:**",
            location_data["damage_location"]
        )

        st.write(
            "**Standortstatus:**",
            location_data["status"]
        )

        damage_lat = selected_report.get(
            "damage_latitude"
        )

        damage_lon = selected_report.get(
            "damage_longitude"
        )

        if damage_lat is not None and damage_lon is not None:

            st.map(
                [
                    {
                        "lat": float(damage_lat),
                        "lon": float(damage_lon)
                    }
                ],
                zoom=16
            )

        else:

            st.info(
                "Für diese Meldung wurde noch kein "
                "separater Schadensstandort markiert."
            )

        st.warning(
            "Standort vor Ort prüfen: "
            "Der automatisch erfasste GPS-Standort "
            "beschreibt die Position des Bürgers, "
            "nicht zwingend die Schadensstelle. "
            "Der markierte Schadensstandort sollte "
            "vor einer Reparatur anhand des Fotos "
            "und der Ortsbeschreibung überprüft werden."
        )

        st.divider()

        # AI VALIDATION

        st.subheader("Gespeicherte KI-Analyse")

        validation = parse_value(
            selected_report.get("validation")
        )

        with st.expander("AI Validation"):

            if isinstance(validation, dict):

                st.write(
                    "**Status:**",
                    translate_status(
                        validation.get("status")
                    )
                )

                st.write(
                    "**Erkannter Schaden:**",
                    safe_text(
                        validation.get("detected_problem")
                    )
                )

                st.write(
                    "**Begründung:**",
                    safe_text(
                        validation.get("reason")
                    )
                )

            else:
                st.write(safe_text(validation))

        # AI IMAGE ANALYSIS

        with st.expander("AI Image Analysis"):

            for bullet in get_image_bullets(
                selected_report
            ):

                st.markdown(f"- {bullet}")

        # AI RISK ASSESSMENT

        with st.expander("AI Risk Assessment"):

            risks = parse_value(
                selected_report.get("risk_factors")
            )

            if isinstance(risks, dict):

                st.write(
                    "**Gefährlichkeit:**",
                    risk_label(risks.get("danger"))
                )

                st.write(
                    "**Auswirkungen:**",
                    risk_label(risks.get("impact"))
                )

                st.write(
                    "**Dringlichkeit:**",
                    risk_label(risks.get("urgency"))
                )

                acute_hazard = risks.get("acute_hazard")

                if acute_hazard is True:
                    acute_text = "Ja"
                elif acute_hazard is False:
                    acute_text = "Nein"
                else:
                    acute_text = "Nicht verfügbar"

                st.write(
                    "**Akute Gefahr:**",
                    acute_text
                )

            else:
                st.info("Keine Risikobewertung verfügbar.")

        # AI PRIORITIZATION

        with st.expander("AI Prioritization"):

            st.write(
                "**KI-Priorität:**",
                get_priority(selected_report)
            )

            st.write("**Erweiterte Prioritätsformel:**")

            st.code(
                "Score = (10 × S × R + 1,2 × U + 0,5 × T) × W",
                language=None
            )

            st.caption(
                "S = Schweregrad | "
                "R = Straßenfaktor | "
                "U = Bürgerdringlichkeit | "
                "T = Wartezeit | "
                "W = Wetterfaktor"
            )

            priority_data = parse_value(
                selected_report.get("priority")
            )

            if isinstance(priority_data, dict):

                score = priority_data.get("score")

                if score is not None:

                    st.write(
                        "**Gespeicherter Prioritätsscore:**",
                        score
                    )

            st.info(
                "Die vollständigen Faktorwerte "
                "sind für diese Meldung noch "
                "nicht gespeichert."
            )

        # DEPARTMENT AND RESPONSIBILITY

        with st.expander("Department and Responsibility"):

            responsibility = parse_value(
                selected_report.get("responsibility")
            )

            if isinstance(responsibility, dict):

                st.write(
                    "**Status:**",
                    translate_status(
                        responsibility.get("status")
                    )
                )

                st.write(
                    "**Begründung:**",
                    safe_text(
                        responsibility.get("reason")
                    )
                )

                if responsibility.get("department"):

                    st.write(
                        "**Empfohlene Abteilung:**",
                        responsibility.get("department")
                    )

            else:
                st.write(safe_text(responsibility))

        st.divider()

        # AI DECISION REPORT

        st.subheader("AI Decision Report")

        st.write(
            "Vollständiger Bericht mit den gespeicherten "
            "KI-Analyseergebnissen"
        )

        try:

            pdf_data = create_ai_report_pdf(
                selected_report
            )

            show_pdf_open_button(pdf_data)

            st.download_button(
                label="AI Decision Report herunterladen",
                data=pdf_data,
                file_name=(
                    f"FixMyCity_AI_Report_"
                    f"{selected_report['id']}.pdf"
                ),
                mime="application/pdf",
                width="stretch"
            )

        except Exception as e:

            st.error(
                f"Fehler bei der PDF-Erstellung: {e}"
            )


# ==================================================
# DUPLIKATERKENNUNG
# ==================================================

with tab2:

    st.subheader("Automatische Duplikaterkennung")

    st.write(
        "FixMyCity AI vergleicht gespeicherte "
        "Schadensmeldungen anhand von Standort, "
        "Bild-Fingerabdruck und Beschreibung."
    )

    st.caption(
        "Prüfradius: 100 Meter. "
        "Erkannte Duplikate werden gruppiert, "
        "aber nicht aus der Datenbank gelöscht."
    )

    if not duplicate_groups:

        st.info(
            "Aktuell wurden keine Duplikatgruppen erkannt."
        )

        st.warning(
            "Bei älteren Meldungen kann der Bild-Fingerabdruck "
            "fehlen. In diesem Fall ist keine bildgestützte "
            "Bestätigung möglich."
        )

    else:

        confirmed_matches = sum(
            1
            for group in duplicate_groups
            for match in group["matches"]
            if match["confirmed"]
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "Duplikatgruppen",
                len(duplicate_groups)
            )

        with col2:

            st.metric(
                "Zusätzliche Meldungen",
                total_duplicates
            )

        with col3:

            st.metric(
                "Bildgestützte Treffer",
                confirmed_matches
            )

        st.divider()

        for group in duplicate_groups:

            original = min(
                group["reports"],
                key=lambda report: report["id"]
            )

            group_reports = sorted(
                group["reports"],
                key=lambda report: report["id"]
            )

            with st.expander(
                f"Schadensfall #{original['id']} – "
                f"{len(group_reports)} zusammengehörige Meldungen",
                expanded=True
            ):

                st.write(
                    "**Ursprüngliche Meldung:**",
                    original.get("description")
                )

                st.write(
                    "**Meldungsnummern:**",
                    ", ".join(
                        f"#{report['id']}"
                        for report in group_reports
                    )
                )

                st.write(
                    "**Zusätzliche Meldungen:**",
                    len(group_reports) - 1
                )

                st.info(
                    "Diese Meldungen wurden automatisch "
                    "zu einem möglichen Schadensfall gruppiert. "
                    "Die endgültige Bestätigung erfolgt "
                    "durch die Verwaltung."
                )

                table_data = []

                for report in group_reports:

                    table_data.append({
                        "Meldungsnummer": report["id"],
                        "Beschreibung": report.get("description"),
                        "Status": report.get("status"),
                        "KI-Priorität": get_priority(report)
                    })

                st.dataframe(
                    table_data,
                    width="stretch",
                    hide_index=True
                )

                st.write("**Vergleichsergebnisse:**")

                for match in group["matches"]:

                    st.markdown(
                        f"**Meldung #{match['report_1']} "
                        f"und #{match['report_2']}**"
                    )

                    col_a, col_b, col_c = st.columns(3)

                    with col_a:

                        st.metric(
                            "Entfernung",
                            f"{match['distance']:.1f} m"
                        )

                    with col_b:

                        st.metric(
                            "Textähnlichkeit",
                            f"{match['text_similarity']:.1f} %"
                        )

                    with col_c:

                        if match["image_similarity"] is not None:

                            st.metric(
                                "Bildähnlichkeit",
                                f"{match['image_similarity']:.1f} %"
                            )

                        else:

                            st.metric(
                                "Bildähnlichkeit",
                                "Nicht verfügbar"
                            )

                    if match["confirmed"]:

                        st.success(
                            "Bildgestützter Duplikatverdacht: "
                            "Die gespeicherten Bild-Fingerabdrücke "
                            "sind sehr ähnlich."
                        )

                    else:

                        st.warning(
                            "Mögliches Duplikat anhand von "
                            "Standort und Beschreibung. "
                            "Keine ausreichende Bildbestätigung."
                        )

                    st.divider()


# ==================================================
# AUFGABENVERTEILUNG
# ==================================================

with tab3:

    st.subheader("Smart Delegation & Intelligent Waiting List")

    st.info(
        "FixMyCity AI priorisiert Schadensfälle und berücksichtigt "
        "die verfügbare Bearbeitungskapazität der zuständigen Abteilungen."
    )

    st.caption(
        "Demo-Modus: Kapazitäten werden simuliert. "
        "Die Verwaltung entscheidet über die endgültige Zuweisung."
    )

    max_capacity = st.number_input(
        "Maximale gleichzeitige Aufgaben pro Abteilung",
        min_value=1,
        max_value=100,
        value=3,
        step=1,
        key="smart_queue_capacity"
    )

    # Bereits freigegebene Aufgaben berücksichtigen.
    # Genehmigte Fälle dürfen nicht erneut in die Warteliste.

    approval_records = load_approvals()
    approvals_by_case = {
        int(approval["report_id"]): approval
        for approval in approval_records
    }

    department_capacities = {}
    occupied_capacity = {}
    queue_cases = []
    active_cases = []
    errors = []

    def get_department_name(recommendation):
        department = recommendation.get("department") or {}

        if isinstance(department, dict):
            return (
                department.get("name")
                or department.get("department")
                or "Manuelle Prüfung"
            )

        return (
            str(department).strip()
            if department
            else "Manuelle Prüfung"
        )

    for case in damage_cases:

        case_id = int(case["id"])
        status = str(case.get("status") or "Offen").strip()

        if status in ("Erledigt", "Abgelehnt"):
            continue

        report = dict(case["original_report"])
        report["priority"] = get_priority(case["priority_report"])

        try:
            recommendation = recommend_task(report)

            if not isinstance(recommendation, dict):
                raise ValueError("Ungültige Abteilungsempfehlung")

            department_name = get_department_name(recommendation)

        except Exception as exc:
            errors.append(
                f"Schadensfall #{case_id}: {exc}"
            )
            continue

        approval = approvals_by_case.get(case_id)

        if approval:
            decision = approval.get("decision")

            if decision == "REJECTED":
                continue

            if decision in ("APPROVED", "REASSIGNED"):

                assigned_department = (
                    approval.get("assigned_department")
                    or department_name
                )

                if status != "Erledigt":
                    occupied_capacity[assigned_department] = (
                        occupied_capacity.get(assigned_department, 0) + 1
                    )

                    active_cases.append({
                        "case_id": case_id,
                        "description": case["description"],
                        "department": assigned_department,
                        "status": status
                    })

                continue

        department_capacities[department_name] = max_capacity
        queue_cases.append(case)

    # Bereits belegte Abteilungen ebenfalls anzeigen.

    for department_name in occupied_capacity:
        department_capacities.setdefault(
            department_name,
            max_capacity
        )

    delegation = build_smart_queue(
        queue_cases,
        capacity_per_department=department_capacities,
        active_tasks=occupied_capacity
    )

    # ----------------------------------------------
    # KENNZAHLEN
    # ----------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Zur Freigabe",
            len(delegation["ready_for_approval"])
        )

    with col2:
        st.metric(
            "Warteliste",
            len(delegation["waiting_list"])
        )

    with col3:
        st.metric(
            "Bereits zugewiesen",
            len(active_cases)
        )

    with col4:
        st.metric(
            "Kritische Eskalationen",
            len(delegation["escalations"])
        )

    if errors:
        with st.expander("Nicht zuordenbare Schadensfälle"):
            for error in errors:
                st.warning(error)

    st.divider()

    # ----------------------------------------------
    # KAPAZITÄTSÜBERSICHT
    # ----------------------------------------------

    st.subheader("Capacity Management")

    capacity_rows = []

    for department_name, capacity_data in delegation["departments"].items():

        capacity_rows.append({
            "Abteilung": department_name,
            "Maximale Kapazität": capacity_data["maximum_capacity"],
            "Bereits belegt": capacity_data["occupied_capacity"],
            "Freie Plätze": capacity_data["available_capacity"],
            "Zur Freigabe": capacity_data["ready_for_approval"],
            "Warteliste": capacity_data["waiting"]
        })

    # Abteilungen ohne wartende Fälle ebenfalls anzeigen.

    known_departments = {
        row["Abteilung"]
        for row in capacity_rows
    }

    for department_name, occupied in occupied_capacity.items():

        if department_name not in known_departments:

            capacity_rows.append({
                "Abteilung": department_name,
                "Maximale Kapazität": max_capacity,
                "Bereits belegt": occupied,
                "Freie Plätze": max(0, max_capacity - occupied),
                "Zur Freigabe": 0,
                "Warteliste": 0
            })

    if capacity_rows:

        st.dataframe(
            capacity_rows,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("Keine aktiven Abteilungen vorhanden.")

    st.divider()

    # ----------------------------------------------
    # PRIORISIERTE FREIGABEVORSCHLÄGE
    # ----------------------------------------------

    st.subheader("Priorisierte Freigabevorschläge")

    st.caption(
        "Diese Fälle haben aktuell Kapazität und können "
        "im Tab 'Freigaben' geprüft werden."
    )

    ready_items = sorted(
        delegation["ready_for_approval"],
        key=lambda item: -item["queue_score"]
    )

    if ready_items:

        for item in ready_items:

            with st.expander(
                f"Schadensfall #{item['case_id']} – "
                f"{item['description']}"
            ):

                st.write(
                    "**Zuständige Abteilung:**",
                    item["department"]
                )

                st.write(
                    "**KI-Priorität:**",
                    item["priority"]
                )

                st.write(
                    "**Wartezeit:**",
                    f"{item['waiting_days']} Tage"
                )

                st.write(
                    "**Queue Score:**",
                    item["queue_score"]
                )

                st.success(
                    "Kapazität vorhanden. "
                    "Zur Verwaltungsfreigabe vorgeschlagen."
                )

    else:
        st.info("Keine neuen Freigabevorschläge vorhanden.")

    st.divider()

    # ----------------------------------------------
    # INTELLIGENTE WARTELISTE
    # ----------------------------------------------

    st.subheader("Intelligente Warteliste")

    st.caption(
        "Diese Fälle bleiben gespeichert und rücken bei "
        "frei werdender Kapazität automatisch in die "
        "Freigabevorschläge nach."
    )

    waiting_items = sorted(
        delegation["waiting_list"],
        key=lambda item: -item["queue_score"]
    )

    if waiting_items:

        waiting_rows = []

        for position, item in enumerate(waiting_items, start=1):

            waiting_rows.append({
                "Position": position,
                "Schadensfall": item["case_id"],
                "Beschreibung": item["description"],
                "Abteilung": item["department"],
                "Priorität": item["priority"],
                "Wartezeit (Tage)": item["waiting_days"],
                "Queue Score": item["queue_score"],
                "Status": item["delegation_status"]
            })

        st.dataframe(
            waiting_rows,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.success("Die Warteliste ist aktuell leer.")

    st.divider()

    # ----------------------------------------------
    # OVERLOAD DETECTION
    # ----------------------------------------------

    st.subheader("Overload Detection")

    if delegation["escalations"]:

        for item in delegation["escalations"]:

            st.error(
                f"KRITISCHE ESKALATION: Schadensfall "
                f"#{item['case_id']} – "
                f"{item['department']} hat keine freie Kapazität. "
                "Sofortige manuelle Prüfung erforderlich."
            )

    else:

        st.success(
            "Keine kritischen Schadensfälle wegen "
            "Kapazitätsmangel zurückgestellt."
        )

    st.divider()

    # ----------------------------------------------
    # BEREITS ZUGEWIESENE AUFGABEN
    # ----------------------------------------------

    st.subheader("Bereits zugewiesene Schadensfälle")

    if active_cases:

        st.dataframe(
            active_cases,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("Noch keine aktiven Zuweisungen vorhanden.")

    st.caption(
        "Die Warteliste wird bei jedem Dashboard-Aufruf "
        "neu berechnet. Die Kapazitätsgrenze ist simuliert."
    )


# ==================================================
# FREIGABEN
# ==================================================

# ==================================================
# VERWALTUNGSFREIGABEN
# ==================================================

with tab4:

    st.subheader("Verwaltungsfreigaben")

    st.info(
        "KI-Empfehlungen werden vor der endgültigen "
        "Aufgabenzuweisung durch die Verwaltung geprüft."
    )

    # ----------------------------------------------
    # SCHADENSFÄLLE LADEN
    # ----------------------------------------------

    if not damage_cases:

        st.warning("Keine Schadensfälle vorhanden.")

    else:

        approvals = load_approvals()

        approved_count = sum(
            approval["decision"] in ("APPROVED", "REASSIGNED")
            for approval in approvals
        )

        rejected_count = sum(
            approval["decision"] == "REJECTED"
            for approval in approvals
        )

        reviewed_case_ids = {
            approval["report_id"]
            for approval in approvals
        }

        pending_count = sum(
            case["id"] not in reviewed_case_ids
            for case in damage_cases
        )

        # ------------------------------------------
        # KENNZAHLEN
        # ------------------------------------------

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Freigabe ausstehend",
                pending_count
            )

        with col2:
            st.metric(
                "Genehmigte Empfehlungen",
                approved_count
            )

        with col3:
            st.metric(
                "Abgelehnte Empfehlungen",
                rejected_count
            )

        st.divider()

        # ------------------------------------------
        # SCHADENSFÄLLE
        # ------------------------------------------

        for case in damage_cases:

            report = case["priority_report"]

            case_id = case["id"]

            recommendation = recommend_task(report)

            department = recommendation.get(
                "department", {}
            )

            capacity = recommendation.get(
                "capacity", {}
            )

            existing_approval = get_approval(case_id)

            with st.expander(
                f"Schadensfall #{case_id} – "
                f"{safe_text(case['description'])}"
            ):

                st.write(
                    "**Beschreibung:**",
                    safe_text(case["description"])
                )

                st.write(
                    "**KI-Priorität:**",
                    get_priority(report)
                )

                st.write(
                    "**Anzahl Bürger-Meldungen:**",
                    case["report_count"]
                )

                st.divider()

                # ----------------------------------
                # KI-EMPFEHLUNG
                # ----------------------------------

                st.subheader("KI-Empfehlung")

                recommended_department = department.get(
                    "name",
                    "Nicht verfügbar"
                )

                st.success(
                    f"Empfohlene Abteilung: "
                    f"{recommended_department}"
                )

                st.write(
                    "**Übergeordnete Einheit:**",
                    department.get("parent", "Nicht verfügbar")
                )

                st.write(
                    "**Dezernat:**",
                    department.get("dezernat", "Nicht verfügbar")
                )

                st.write(
                    "**Organisationscode:**",
                    department.get("code", "Nicht verfügbar")
                )

                st.divider()

                # ----------------------------------
                # KAPAZITÄTSPRÜFUNG
                # ----------------------------------

                st.subheader("Kapazitätsprüfung")

                available_capacity = capacity.get(
                    "available_capacity",
                    0
                )

                try:
                    available_capacity = float(
                        available_capacity
                    )
                except (ValueError, TypeError):
                    available_capacity = 0

                available_capacity = max(
                    0,
                    min(100, available_capacity)
                )

                st.progress(
                    available_capacity / 100
                )

                st.write(
                    "**Verfügbare Kapazität:**",
                    f"{available_capacity:.0f} %"
                )

                st.caption(
                    "Kapazitätswerte sind für die Demo simuliert."
                )

                st.divider()

                # ----------------------------------
                # BEREITS GESPEICHERTE ENTSCHEIDUNG
                # ----------------------------------

                if existing_approval:

                    decision = existing_approval["decision"]

                    if decision == "APPROVED":

                        st.success(
                            "Status: KI-Empfehlung genehmigt."
                        )

                    elif decision == "REJECTED":

                        st.error(
                            "Status: KI-Empfehlung abgelehnt."
                        )

                    elif decision == "REASSIGNED":

                        st.success(
                            "Status: Andere Abteilung zugewiesen."
                        )

                    st.write(
                        "**Zugewiesene Abteilung:**",
                        safe_text(
                            existing_approval.get(
                                "assigned_department"
                            )
                        )
                    )

                    st.write(
                        "**Kommentar:**",
                        safe_text(
                            existing_approval.get("comment")
                        )
                    )

                    st.write(
                        "**Entschieden am:**",
                        existing_approval.get("decided_at")
                    )

                    st.divider()

                # ----------------------------------
                # FREIGABEFORMULAR
                # ----------------------------------

                st.subheader("Verwaltungsentscheidung")

                with st.form(
                    key=f"approval_form_{case_id}"
                ):

                    decision = st.radio(
                        "Entscheidung auswählen",
                        [
                            "Approve",
                            "Reject",
                            "Reassign"
                        ],
                        horizontal=True
                    )

                    alternative_departments = [
                        "Grünflächenmanagement und Straßenunterhaltung",
                        "Mobilität und Verkehr",
                        "Verkehrsbauwerke",
                        "Verkehrs- und Beleuchtungstechnik",
                        "Werterhaltung, Barrierefreiheit und ÖPNV",
                        "Technische Dienste",
                        "Abfallwirtschaft",
                        "Umwelttechnik",
                        "Feuerwehr",
                        "Straßenverkehrsbehörde",
                        "Kommunaler Ordnungsdienst"
                    ]

                    selected_department = st.selectbox(
                        "Zuständige Abteilung",
                        options=alternative_departments,
                        index=(
                            alternative_departments.index(
                                recommended_department
                            )
                            if recommended_department
                            in alternative_departments
                            else 0
                        )
                    )

                    comment = st.text_area(
                        "Kommentar der Verwaltung",
                        placeholder=(
                            "Begründung oder zusätzliche "
                            "Informationen eingeben ..."
                        )
                    )

                    submitted = st.form_submit_button(
                        "Entscheidung speichern",
                        type="primary",
                        use_container_width=True
                    )

                # ----------------------------------
                # ENTSCHEIDUNG SPEICHERN
                # ----------------------------------

                if submitted:

                    decision_mapping = {
                        "Approve": "APPROVED",
                        "Reject": "REJECTED",
                        "Reassign": "REASSIGNED"
                    }

                    database_decision = decision_mapping[
                        decision
                    ]

                    if decision == "Approve":

                        final_department = recommended_department

                    elif decision == "Reassign":

                        final_department = selected_department

                    else:

                        final_department = None

                    try:

                        save_approval(
                            report_id=case_id,
                            decision=database_decision,
                            assigned_department=final_department,
                            comment=comment
                        )

                        # Alle Meldungen desselben
                        # Schadensfalls synchronisieren.

                        new_status = (
                            "Abgelehnt"
                            if decision == "Reject"
                            else "Genehmigt"
                        )

                        for report_id in case["report_ids"]:

                            if report_id != case_id:

                                update_report_status(
                                    report_id,
                                    new_status
                                )

                        st.success(
                            "Verwaltungsentscheidung "
                            "erfolgreich gespeichert."
                        )

                        st.rerun()

                    except Exception as e:

                        st.error(
                            f"Fehler beim Speichern: {e}"
                        )