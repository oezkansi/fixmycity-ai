import base64
import json
import re
from io import BytesIO
from xml.sax.saxutils import escape

import streamlit as st
import streamlit.components.v1 as components

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from database import (
    load_reports,
    save_approval,
    load_approvals,
    get_approval,
    update_report_status,
)

from existing_duplicates import find_existing_duplicates
from smart_delegation import build_smart_queue
from task_assignment import recommend_task


# ==================================================
# SEITENKONFIGURATION
# ==================================================

st.set_page_config(
    page_title="FixMyCity AI | Verwaltung",
    layout="wide",
)

st.title("FixMyCity AI")
st.subheader("Intelligentes Verwaltungsdashboard")

st.info(
    "KI-gestützte Entscheidungsunterstützung "
    "für die Stadtverwaltung"
)


# ==================================================
# HILFSFUNKTIONEN
# ==================================================

def parse_value(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            pass

    return value


def safe_text(value):
    if value is None or value == "":
        return "Nicht verfügbar"

    return str(value)


def get_priority(report):
    value = parse_value(report.get("priority"))

    if isinstance(value, dict):
        value = (
            value.get("priority")
            or value.get("level")
            or value.get("priority_level")
            or value.get("label")
        )

    return safe_text(value) if value else "Nicht bewertet"


def get_priority_rank(report):
    value = get_priority(report).strip().lower()

    if value.startswith("p1") or value in (
        "kritisch",
        "critical",
    ):
        return 1

    if value.startswith("p2") or value in (
        "hoch",
        "high",
    ):
        return 2

    if value.startswith("p3"):
        return 3

    if value.startswith("p4"):
        return 4

    return 5


def translate_status(status):
    translations = {
        "VALID": "Gültig",
        "INVALID": "Ungültig",
        "UNCERTAIN": "Nicht eindeutig",
        "TRUE": "Ja",
        "FALSE": "Nein",
    }

    return translations.get(
        str(status).upper(),
        safe_text(status),
    )


def risk_label(value):
    try:
        number = int(value)
    except (ValueError, TypeError):
        return "Nicht verfügbar"

    labels = {
        0: "Sehr gering",
        1: "Gering",
        2: "Mittel",
        3: "Hoch",
    }

    return (
        f"{number}/3 – "
        f"{labels.get(number, 'Unbekannt')}"
    )


def get_urgency(report):
    try:
        return int(report.get("citizen_urgency") or 0)
    except (ValueError, TypeError):
        return 0


def get_department_name(recommendation):
    department = recommendation.get("department") or {}

    if isinstance(department, dict):
        return (
            department.get("name")
            or department.get("department")
            or "Manuelle Prüfung"
        )

    return str(department).strip() or "Manuelle Prüfung"


def get_recommendation(case):
    report = dict(case["original_report"])

    report["priority"] = get_priority(
        case["priority_report"]
    )

    recommendation = recommend_task(report)

    if not isinstance(recommendation, dict):
        raise ValueError(
            "Ungültige Abteilungsempfehlung"
        )

    return recommendation


# ==================================================
# STANDORTBEWERTUNG
# ==================================================

def get_location_assessment(report):

    def coordinates(lat, lon):
        try:
            if lat is not None and lon is not None:
                return (
                    f"{float(lat):.6f}, "
                    f"{float(lon):.6f}"
                )
        except (TypeError, ValueError):
            pass

        return "Nicht verfügbar"

    def meters(value):
        try:
            if value is not None:
                return f"{float(value):.1f} m"
        except (TypeError, ValueError):
            pass

        return "Nicht verfügbar"

    citizen = coordinates(
        report.get("citizen_latitude"),
        report.get("citizen_longitude"),
    )

    damage = coordinates(
        report.get("damage_latitude"),
        report.get("damage_longitude"),
    )

    accuracy = meters(
        report.get("gps_accuracy")
    )

    return {
        "citizen_location": citizen,
        "damage_location": (
            damage
            if damage != "Nicht verfügbar"
            else "Nicht bestätigt"
        ),
        "accuracy": (
            f"± {accuracy}"
            if accuracy != "Nicht verfügbar"
            else accuracy
        ),
        "distance": meters(
            report.get("distance_to_damage")
        ),
        "status": (
            "Vom Bürger auf der Karte markiert"
            if damage != "Nicht verfügbar"
            else "Schadensstandort nicht bestätigt"
        ),
    }


# ==================================================
# BILDANALYSE
# ==================================================

def get_image_bullets(report):
    analysis = parse_value(
        report.get("image_analysis")
    )

    if not analysis:
        return ["Keine Bildanalyse verfügbar"]

    if isinstance(analysis, dict):
        return [
            (
                f"{str(key).replace('_', ' ').title()}: "
                f"{value}"
            )
            for key, value in analysis.items()
            if value is not None and value != ""
        ] or ["Keine Bildanalyse verfügbar"]

    if isinstance(analysis, list):
        return [
            str(item)
            for item in analysis
            if item
        ] or ["Keine Bildanalyse verfügbar"]

    content = str(analysis).replace("**", "")
    bullets = []

    sections = re.split(
        r"\n\s*\d+\.\s+",
        content,
    )

    for section in sections:
        section = section.strip()

        if not section:
            continue

        if section.lower().startswith(
            "hier ist die analyse"
        ):
            continue

        if "\n" in section:
            heading, body = section.split("\n", 1)

            if "zusätzliche risiken" in heading.lower():
                risks = re.split(
                    r"\n\s*[*-]\s+",
                    body,
                )

                for risk in risks:
                    risk = risk.strip().lstrip(
                        "*- "
                    ).strip()

                    if risk:
                        bullets.append(
                            f"Zusätzliches Risiko: {risk}"
                        )

            elif body.strip():
                bullets.append(
                    f"{heading.strip().rstrip(':')}: "
                    f"{' '.join(body.split())}"
                )

    return bullets or [
        " ".join(content.split())
    ]


# ==================================================
# PDF-BERICHT
# ==================================================

def create_ai_report_pdf(report):

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=(21 * cm, 29.7 * cm),
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
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
            spaceAfter=12,
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
            spaceAfter=8,
        )
    )

    styles.add(
        ParagraphStyle(
            name="CustomBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=14,
            spaceAfter=6,
        )
    )

    story = []

    def paragraph(text):
        return Paragraph(
            escape(safe_text(text)),
            styles["CustomBody"],
        )

    def section(title):
        story.append(
            Paragraph(
                escape(title),
                styles["CustomSection"],
            )
        )

    def line(label, value):
        story.append(
            Paragraph(
                f"<b>{escape(label)}:</b> "
                f"{escape(safe_text(value))}",
                styles["CustomBody"],
            )
        )

    def bullets(items):
        for item in items:
            story.append(
                Paragraph(
                    f"&#8226; {escape(str(item))}",
                    styles["CustomBody"],
                )
            )

    def table(rows):
        widget = Table(
            [
                [paragraph(cell) for cell in row]
                for row in rows
            ],
            colWidths=[6 * cm, 11 * cm],
            repeatRows=1,
            hAlign="LEFT",
        )

        widget.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#E8EDF5"),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#CCCCCC"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
            ])
        )

        story.append(widget)

    story.append(
        Paragraph(
            "FixMyCity AI",
            styles["CustomTitle"],
        )
    )

    story.append(
        Paragraph(
            "AI Decision Report",
            styles["CustomTitle"],
        )
    )

    story.append(
        paragraph(
            "Vollständiger Bericht mit den "
            "gespeicherten KI-Analyseergebnissen"
        )
    )

    story.append(Spacer(1, 0.4 * cm))

    section("1. Allgemeine Informationen")

    for label, field in [
        ("Meldungsnummer", "id"),
        ("Beschreibung", "description"),
        ("Schadensstandort", "location"),
        ("Eingegangen am", "created_at"),
        ("Bearbeitungsstatus", "status"),
    ]:
        line(label, report.get(field))

    line(
        "Dringlichkeit Bürger",
        f"{safe_text(report.get('citizen_urgency'))}/5",
    )

    section(
        "2. Location Assessment – Standortbewertung"
    )

    location = get_location_assessment(report)

    table([
        ["Standortinformation", "Ergebnis"],
        [
            "GPS-Standort des Bürgers",
            location["citizen_location"],
        ],
        [
            "GPS-Genauigkeit",
            location["accuracy"],
        ],
        [
            "Markierter Schadensstandort",
            location["damage_location"],
        ],
        [
            "Abstand zwischen Bürger und Schaden",
            location["distance"],
        ],
        [
            "Standortstatus",
            location["status"],
        ],
    ])

    story.append(Spacer(1, 0.3 * cm))

    story.append(
        paragraph(
            "Hinweis zur Standortbewertung: "
            "Die GPS-Koordinaten kennzeichnen zunächst "
            "die Position des Meldenden. "
            "Die tatsächliche Schadensstelle kann "
            "davon abweichen. Der Kartenmarker wurde "
            "vom Bürger gesetzt und stellt keine "
            "unabhängige Verifizierung dar. "
            "Vor der Entsendung eines Reparaturteams "
            "sollte die Position anhand des Kartenmarkers, "
            "des Fotos und der Ortsbeschreibung "
            "überprüft werden."
        )
    )

    section("3. AI Validation")

    validation = parse_value(
        report.get("validation")
    )

    if isinstance(validation, dict):
        line(
            "Validierungsstatus",
            translate_status(
                validation.get("status")
            ),
        )

        line(
            "Erkannter Schaden",
            validation.get("detected_problem"),
        )

        line(
            "Begründung",
            validation.get("reason"),
        )

    else:
        line("Validierung", validation)

    section("4. AI Image Analysis")

    bullets(
        get_image_bullets(report)
    )

    section("5. AI Risk Assessment")

    risks = parse_value(
        report.get("risk_factors")
    )

    if isinstance(risks, dict):
        acute = risks.get("acute_hazard")

        table([
            ["Risikofaktor", "KI-Bewertung"],
            [
                "Gefährlichkeit",
                risk_label(risks.get("danger")),
            ],
            [
                "Auswirkungen",
                risk_label(risks.get("impact")),
            ],
            [
                "Dringlichkeit",
                risk_label(risks.get("urgency")),
            ],
            [
                "Akute Gefahr",
                (
                    "Ja"
                    if acute is True
                    else "Nein"
                    if acute is False
                    else "Nicht verfügbar"
                ),
            ],
        ])

    else:
        story.append(
            paragraph(
                "Keine Risikobewertung verfügbar"
            )
        )

    section("6. AI Prioritization")

    line(
        "Ermittelte KI-Priorität",
        get_priority(report),
    )

    story.append(
        paragraph(
            "Erweiterte Prioritätsformel:"
        )
    )

    story.append(
        paragraph(
            "Score = (10 × S × R + 1,2 × U "
            "+ 0,5 × T) × W"
        )
    )

    table([
        ["Faktor", "Bedeutung"],
        ["S", "Schweregrad des Schadens"],
        ["R", "Straßenfaktor"],
        ["U", "Dringlichkeit des Bürgers"],
        ["T", "Wartezeit in Tagen"],
        ["W", "Wetterfaktor"],
    ])

    priority = parse_value(
        report.get("priority")
    )

    if isinstance(priority, dict):
        if priority.get("score") is not None:
            line(
                "Gespeicherter Prioritätsscore",
                priority["score"],
            )

    story.append(
        paragraph(
            "Hinweis: Die dargestellte Formel ist "
            "das erweiterte Priorisierungsmodell. "
            "Eine vollständige Berechnung mit allen "
            "Faktorwerten ist für diese Meldung "
            "noch nicht dokumentiert."
        )
    )

    section("7. Department and Responsibility")

    responsibility = parse_value(
        report.get("responsibility")
    )

    if isinstance(responsibility, dict):
        line(
            "Zuständigkeitsstatus",
            translate_status(
                responsibility.get("status")
            ),
        )

        line(
            "Begründung",
            responsibility.get("reason"),
        )

        if responsibility.get("department"):
            line(
                "Empfohlene Abteilung",
                responsibility["department"],
            )

    else:
        line(
            "Zuständigkeit",
            responsibility,
        )

    section("8. Human Review")

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

    doc.build(story)

    buffer.seek(0)

    return buffer.getvalue()


# ==================================================
# PDF IN NEUEM TAB
# ==================================================

def show_pdf_open_button(pdf_data):

    encoded = base64.b64encode(
        pdf_data
    ).decode("utf-8")

    html_code = f"""
    <button
        onclick="openPDF()"
        style="
            background-color:#14213D;
            color:white;
            border:none;
            border-radius:8px;
            padding:12px 20px;
            font-size:15px;
            cursor:pointer;
            width:100%;
        "
    >
        AI Decision Report öffnen
    </button>

    <script>
    function openPDF() {{
        const binary = atob('{encoded}');
        const bytes = new Uint8Array(binary.length);

        for (let i = 0; i < binary.length; i++) {{
            bytes[i] = binary.charCodeAt(i);
        }}

        const url = URL.createObjectURL(
            new Blob(
                [bytes],
                {{type:'application/pdf'}}
            )
        );

        if (!window.open(url, '_blank')) {{
            alert(
                'Bitte Pop-ups für diese Seite erlauben.'
            );
        }}
    }}
    </script>
    """

    components.html(
        html_code,
        height=65,
    )


# ==================================================
# DATEN LADEN
# ==================================================

try:
    reports = load_reports()

except Exception as exc:
    st.error(
        f"Fehler beim Laden der Meldungen: {exc}"
    )
    st.stop()


# ==================================================
# DUPLIKATERKENNUNG
# ==================================================

try:
    duplicate_groups = find_existing_duplicates(
        reports
    )

except Exception as exc:
    st.error(
        f"Fehler bei der Duplikaterkennung: {exc}"
    )
    duplicate_groups = []


grouped_report_ids = {
    report["id"]
    for group in duplicate_groups
    for report in group["reports"]
}

single_reports = [
    report
    for report in reports
    if report["id"] not in grouped_report_ids
]


# ==================================================
# SCHADENSFÄLLE ERSTELLEN
# ==================================================

damage_cases = []

for group in duplicate_groups:

    group_reports = group["reports"]

    if not group_reports:
        continue

    original = min(
        group_reports,
        key=lambda report: report["id"],
    )

    highest_priority_report = min(
        group_reports,
        key=get_priority_rank,
    )

    statuses = [
        str(report.get("status") or "").strip()
        for report in group_reports
    ]

    if statuses and all(
        status == "Erledigt"
        for status in statuses
    ):
        case_status = "Erledigt"

    elif "In Bearbeitung" in statuses:
        case_status = "In Bearbeitung"

    elif statuses and all(
        status == "Abgelehnt"
        for status in statuses
    ):
        case_status = "Abgelehnt"

    elif statuses and all(
        status == "Genehmigt"
        for status in statuses
    ):
        case_status = "Genehmigt"

    elif "Offen" in statuses:
        case_status = "Offen"

    else:
        case_status = (
            original.get("status") or "Offen"
        )

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
        "confirmed": group.get(
            "confirmed",
            False,
        ),
    })


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
        "confirmed": True,
    })


damage_cases.sort(
    key=lambda case: case["id"],
    reverse=True,
)


# ==================================================
# VERWALTUNGSENTSCHEIDUNGEN LADEN
# ==================================================

try:
    approval_records = load_approvals()

except Exception as exc:
    st.error(
        f"Freigaben konnten nicht geladen werden: {exc}"
    )
    st.stop()


approvals_by_case = {
    int(approval["report_id"]): approval
    for approval in approval_records
}


# ==================================================
# VERWALTUNGSÜBERSICHT
# ==================================================

st.subheader("Verwaltungsübersicht")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Eingegangene Meldungen",
        len(reports),
    )

with col2:
    st.metric(
        "Schadensfälle",
        len(damage_cases),
    )

with col3:
    st.metric(
        "Mögliche Duplikate",
        len(reports) - len(damage_cases),
    )

with col4:
    st.metric(
        "Hohe Priorität",
        sum(
            get_priority_rank(
                case["priority_report"]
            ) <= 2
            for case in damage_cases
        ),
    )


col5, col6 = st.columns(2)

with col5:
    st.metric(
        "Offene Schadensfälle",
        sum(
            case["status"] == "Offen"
            for case in damage_cases
        ),
    )

with col6:
    st.metric(
        "In Bearbeitung",
        sum(
            case["status"] == "In Bearbeitung"
            for case in damage_cases
        ),
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
    "Jeder automatisch erkannte Schadensfall "
    "erscheint in dieser Übersicht nur einmal."
)

if damage_cases:

    dashboard_data = []

    for case in damage_cases:
        dashboard_data.append({
            "Schadensfall": f"#{case['id']}",
            "Beschreibung": case["description"],
            "Standort": case["location"],
            "Bürgerdringlichkeit": case[
                "citizen_urgency"
            ],
            "KI-Priorität": get_priority(
                case["priority_report"]
            ),
            "Status": case["status"],
            "Anzahl Meldungen": case["report_count"],
            "Mögliche Duplikate": (
                case["report_count"] - 1
            ),
            "Eingegangen am": case["created_at"],
        })

    st.dataframe(
        dashboard_data,
        use_container_width=True,
        hide_index=True,
    )

else:
    st.info(
        "Aktuell liegen keine Schadensfälle vor."
    )

st.divider()


# ==================================================
# ALLE EINGEGANGENEN MELDUNGEN
# ==================================================

with st.expander(
    "Alle eingegangenen Meldungen anzeigen"
):

    st.caption(
        "Hier bleiben sämtliche ursprünglichen "
        "Meldungen einschließlich möglicher "
        "Duplikate sichtbar."
    )

    all_reports_data = []

    for report in reports:
        all_reports_data.append({
            "Meldungsnummer": report.get("id"),
            "Beschreibung": report.get("description"),
            "Standort": report.get("location"),
            "KI-Priorität": get_priority(report),
            "Status": report.get("status"),
            "Eingegangen am": report.get(
                "created_at"
            ),
        })

    st.dataframe(
        all_reports_data,
        use_container_width=True,
        hide_index=True,
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
    "Freigaben",
])


# ==================================================
# TAB 1: AI REPORTS
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
            ),
        )

        st.divider()

        st.subheader("Meldungsübersicht")

        for label, field in [
            ("Meldungsnummer", "id"),
            ("Beschreibung", "description"),
            ("Schadensstandort", "location"),
            ("Bearbeitungsstatus", "status"),
        ]:
            st.write(
                f"**{label}:**",
                selected_report.get(field),
            )

        st.write(
            "**KI-Priorität:**",
            get_priority(selected_report),
        )

        st.divider()

        # ------------------------------------------
        # LOCATION ASSESSMENT
        # ------------------------------------------

        st.subheader(
            "Location Assessment – Standortbewertung"
        )

        location = get_location_assessment(
            selected_report
        )

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "GPS-Genauigkeit",
                location["accuracy"],
            )

        with col2:
            st.metric(
                "Abstand zum Schaden",
                location["distance"],
            )

        st.write(
            "**GPS-Standort des Bürgers:**",
            location["citizen_location"],
        )

        st.write(
            "**Markierter Schadensstandort:**",
            location["damage_location"],
        )

        st.write(
            "**Standortstatus:**",
            location["status"],
        )

        lat = selected_report.get(
            "damage_latitude"
        )

        lon = selected_report.get(
            "damage_longitude"
        )

        if lat is not None and lon is not None:

            try:
                st.map(
                    [{
                        "lat": float(lat),
                        "lon": float(lon),
                    }],
                    zoom=16,
                )

            except (TypeError, ValueError):
                st.warning(
                    "Ungültige Standortkoordinaten."
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

        # ------------------------------------------
        # AI VALIDATION
        # ------------------------------------------

        st.subheader("Gespeicherte KI-Analyse")

        with st.expander("AI Validation"):

            validation = parse_value(
                selected_report.get("validation")
            )

            if isinstance(validation, dict):

                st.write(
                    "**Status:**",
                    translate_status(
                        validation.get("status")
                    ),
                )

                st.write(
                    "**Erkannter Schaden:**",
                    safe_text(
                        validation.get("detected_problem")
                    ),
                )

                st.write(
                    "**Begründung:**",
                    safe_text(
                        validation.get("reason")
                    ),
                )

            else:
                st.write(
                    safe_text(validation)
                )

        # ------------------------------------------
        # AI IMAGE ANALYSIS
        # ------------------------------------------

        with st.expander("AI Image Analysis"):

            for bullet in get_image_bullets(
                selected_report
            ):
                st.markdown(
                    f"- {bullet}"
                )

        # ------------------------------------------
        # AI RISK ASSESSMENT
        # ------------------------------------------

        with st.expander("AI Risk Assessment"):

            risks = parse_value(
                selected_report.get("risk_factors")
            )

            if isinstance(risks, dict):

                st.write(
                    "**Gefährlichkeit:**",
                    risk_label(
                        risks.get("danger")
                    ),
                )

                st.write(
                    "**Auswirkungen:**",
                    risk_label(
                        risks.get("impact")
                    ),
                )

                st.write(
                    "**Dringlichkeit:**",
                    risk_label(
                        risks.get("urgency")
                    ),
                )

                acute = risks.get(
                    "acute_hazard"
                )

                acute_text = (
                    "Ja"
                    if acute is True
                    else "Nein"
                    if acute is False
                    else "Nicht verfügbar"
                )

                st.write(
                    "**Akute Gefahr:**",
                    acute_text,
                )

            else:
                st.info(
                    "Keine Risikobewertung verfügbar."
                )

        # ------------------------------------------
        # AI PRIORITIZATION
        # ------------------------------------------

        with st.expander("AI Prioritization"):

            st.write(
                "**KI-Priorität:**",
                get_priority(selected_report),
            )

            st.write(
                "**Erweiterte Prioritätsformel:**"
            )

            st.code(
                "Score = (10 × S × R + 1,2 × U "
                "+ 0,5 × T) × W",
                language=None,
            )

            st.caption(
                "S = Schweregrad | "
                "R = Straßenfaktor | "
                "U = Bürgerdringlichkeit | "
                "T = Wartezeit | "
                "W = Wetterfaktor"
            )

            priority = parse_value(
                selected_report.get("priority")
            )

            if isinstance(priority, dict):

                if priority.get("score") is not None:
                    st.write(
                        "**Gespeicherter Prioritätsscore:**",
                        priority["score"],
                    )

            st.info(
                "Die vollständigen Faktorwerte "
                "sind für diese Meldung noch "
                "nicht gespeichert."
            )

        # ------------------------------------------
        # DEPARTMENT AND RESPONSIBILITY
        # ------------------------------------------

        with st.expander(
            "Department and Responsibility"
        ):

            responsibility = parse_value(
                selected_report.get("responsibility")
            )

            if isinstance(responsibility, dict):

                st.write(
                    "**Status:**",
                    translate_status(
                        responsibility.get("status")
                    ),
                )

                st.write(
                    "**Begründung:**",
                    safe_text(
                        responsibility.get("reason")
                    ),
                )

                if responsibility.get("department"):

                    st.write(
                        "**Empfohlene Abteilung:**",
                        responsibility["department"],
                    )

            else:
                st.write(
                    safe_text(responsibility)
                )

        st.divider()

        # ------------------------------------------
        # AI DECISION REPORT
        # ------------------------------------------

        st.subheader("AI Decision Report")

        st.write(
            "Vollständiger Bericht mit den "
            "gespeicherten KI-Analyseergebnissen"
        )

        try:

            pdf_data = create_ai_report_pdf(
                selected_report
            )

            show_pdf_open_button(
                pdf_data
            )

            st.download_button(
                "AI Decision Report herunterladen",
                data=pdf_data,
                file_name=(
                    f"FixMyCity_AI_Report_"
                    f"{selected_report['id']}.pdf"
                ),
                mime="application/pdf",
                use_container_width=True,
            )

        except Exception as exc:
            st.error(
                f"Fehler bei der PDF-Erstellung: {exc}"
            )


# ==================================================
# TAB 2: DUPLIKATERKENNUNG
# ==================================================

with tab2:

    st.subheader(
        "Automatische Duplikaterkennung"
    )

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
            "Bei älteren Meldungen kann der "
            "Bild-Fingerabdruck fehlen. "
            "In diesem Fall ist keine bildgestützte "
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
                len(duplicate_groups),
            )

        with col2:
            st.metric(
                "Zusätzliche Meldungen",
                len(reports) - len(damage_cases),
            )

        with col3:
            st.metric(
                "Bildgestützte Treffer",
                confirmed_matches,
            )

        st.divider()

        for group in duplicate_groups:

            group_reports = sorted(
                group["reports"],
                key=lambda report: report["id"],
            )

            if not group_reports:
                continue

            original = group_reports[0]

            with st.expander(
                f"Schadensfall #{original['id']} – "
                f"{len(group_reports)} "
                "zusammengehörige Meldungen",
                expanded=True,
            ):

                st.write(
                    "**Ursprüngliche Meldung:**",
                    original.get("description"),
                )

                st.write(
                    "**Meldungsnummern:**",
                    ", ".join(
                        f"#{report['id']}"
                        for report in group_reports
                    ),
                )

                st.write(
                    "**Zusätzliche Meldungen:**",
                    len(group_reports) - 1,
                )

                st.info(
                    "Diese Meldungen wurden automatisch "
                    "zu einem möglichen Schadensfall "
                    "gruppiert. Die endgültige Bestätigung "
                    "erfolgt durch die Verwaltung."
                )

                table_data = []

                for report in group_reports:

                    table_data.append({
                        "Meldungsnummer": report["id"],
                        "Beschreibung": report.get(
                            "description"
                        ),
                        "Status": report.get("status"),
                        "KI-Priorität": get_priority(
                            report
                        ),
                    })

                st.dataframe(
                    table_data,
                    use_container_width=True,
                    hide_index=True,
                )

                st.write(
                    "**Vergleichsergebnisse:**"
                )

                for match in group["matches"]:

                    st.markdown(
                        f"**Meldung #{match['report_1']} "
                        f"und #{match['report_2']}**"
                    )

                    col_a, col_b, col_c = st.columns(3)

                    with col_a:
                        st.metric(
                            "Entfernung",
                            f"{match['distance']:.1f} m",
                        )

                    with col_b:
                        st.metric(
                            "Textähnlichkeit",
                            f"{match['text_similarity']:.1f} %",
                        )

                    with col_c:

                        if match["image_similarity"] is not None:

                            st.metric(
                                "Bildähnlichkeit",
                                f"{match['image_similarity']:.1f} %",
                            )

                        else:
                            st.metric(
                                "Bildähnlichkeit",
                                "Nicht verfügbar",
                            )

                    if match["confirmed"]:

                        st.success(
                            "Bildgestützter Duplikatverdacht: "
                            "Die gespeicherten "
                            "Bild-Fingerabdrücke "
                            "sind sehr ähnlich."
                        )

                    else:

                        st.warning(
                            "Mögliches Duplikat anhand "
                            "von Standort und Beschreibung. "
                            "Keine ausreichende Bildbestätigung."
                        )

                    st.divider()


# ==================================================
# TAB 3: SMART DELEGATION
# ==================================================

with tab3:

    st.subheader(
        "Smart Delegation & Intelligent Waiting List"
    )

    st.info(
        "FixMyCity AI priorisiert Schadensfälle "
        "und berücksichtigt die verfügbare "
        "Bearbeitungskapazität der zuständigen Abteilungen."
    )

    st.caption(
        "Demo-Modus: Kapazitäten werden simuliert. "
        "Die Verwaltung entscheidet über die "
        "endgültige Zuweisung."
    )

    max_capacity = st.number_input(
        "Maximale gleichzeitige Aufgaben pro Abteilung",
        min_value=1,
        max_value=100,
        value=3,
        step=1,
        key="smart_queue_capacity",
    )

    # ----------------------------------------------
    # KAPAZITÄTEN BERECHNEN
    # ----------------------------------------------

    department_capacities = {}
    occupied_capacity = {}
    queue_cases = []
    active_cases = []
    errors = []

    for case in damage_cases:

        case_id = int(case["id"])

        status = str(
            case.get("status") or "Offen"
        ).strip()

        if status in (
            "Erledigt",
            "Abgelehnt",
        ):
            continue

        try:

            recommendation = get_recommendation(
                case
            )

            department_name = get_department_name(
                recommendation
            )

        except Exception as exc:

            errors.append(
                f"Schadensfall #{case_id}: {exc}"
            )

            continue

        approval = approvals_by_case.get(
            case_id
        )

        if approval:

            decision = approval.get(
                "decision"
            )

            if decision == "REJECTED":
                continue

            if decision in (
                "APPROVED",
                "REASSIGNED",
            ):

                assigned_department = (
                    approval.get("assigned_department")
                    or department_name
                )

                occupied_capacity[
                    assigned_department
                ] = (
                    occupied_capacity.get(
                        assigned_department,
                        0,
                    ) + 1
                )

                active_cases.append({
                    "case_id": case_id,
                    "description": case["description"],
                    "department": assigned_department,
                    "status": status,
                })

                continue

        department_capacities[
            department_name
        ] = max_capacity

        queue_cases.append(
            case
        )

    # Auch bereits belegte Abteilungen anzeigen.

    for department_name in occupied_capacity:

        department_capacities.setdefault(
            department_name,
            max_capacity,
        )

    # ----------------------------------------------
    # SMART QUEUE BERECHNEN
    # ----------------------------------------------

    delegation = build_smart_queue(
        queue_cases,
        capacity_per_department=department_capacities,
        active_tasks=occupied_capacity,
    )

    # ----------------------------------------------
    # KENNZAHLEN
    # ----------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Zur Freigabe",
            len(
                delegation["ready_for_approval"]
            ),
        )

    with col2:
        st.metric(
            "Warteliste",
            len(
                delegation["waiting_list"]
            ),
        )

    with col3:
        st.metric(
            "Bereits zugewiesen",
            len(active_cases),
        )

    with col4:
        st.metric(
            "Kritische Eskalationen",
            len(
                delegation["escalations"]
            ),
        )

    if errors:

        with st.expander(
            "Nicht zuordenbare Schadensfälle"
        ):

            for error in errors:
                st.warning(error)

    st.divider()

    # ----------------------------------------------
    # CAPACITY MANAGEMENT
    # ----------------------------------------------

    st.subheader(
        "Capacity Management"
    )

    capacity_rows = []

    for department_name, data in delegation[
        "departments"
    ].items():

        capacity_rows.append({
            "Abteilung": department_name,
            "Maximale Kapazität": data[
                "maximum_capacity"
            ],
            "Bereits belegt": data[
                "occupied_capacity"
            ],
            "Freie Plätze": data[
                "available_capacity"
            ],
            "Zur Freigabe": data[
                "ready_for_approval"
            ],
            "Warteliste": data[
                "waiting"
            ],
        })

    known_departments = {
        row["Abteilung"]
        for row in capacity_rows
    }

    for department_name, occupied in (
        occupied_capacity.items()
    ):

        if department_name not in known_departments:

            capacity_rows.append({
                "Abteilung": department_name,
                "Maximale Kapazität": max_capacity,
                "Bereits belegt": occupied,
                "Freie Plätze": max(
                    0,
                    max_capacity - occupied,
                ),
                "Zur Freigabe": 0,
                "Warteliste": 0,
            })

    if capacity_rows:

        st.dataframe(
            capacity_rows,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "Keine aktiven Abteilungen vorhanden."
        )

    st.divider()

    # ----------------------------------------------
    # PRIORISIERTE FREIGABEVORSCHLÄGE
    # ----------------------------------------------

    st.subheader(
        "Priorisierte Freigabevorschläge"
    )

    st.caption(
        "Diese Fälle haben aktuell Kapazität "
        "und können im Tab 'Freigaben' geprüft werden."
    )

    ready_items = sorted(
        delegation["ready_for_approval"],
        key=lambda item: -item["queue_score"],
    )

    if ready_items:

        for item in ready_items:

            with st.expander(
                f"Schadensfall #{item['case_id']} – "
                f"{item['description']}"
            ):

                st.write(
                    "**Zuständige Abteilung:**",
                    item["department"],
                )

                st.write(
                    "**KI-Priorität:**",
                    item["priority"],
                )

                st.write(
                    "**Wartezeit:**",
                    f"{item['waiting_days']} Tage",
                )

                st.write(
                    "**Queue Score:**",
                    item["queue_score"],
                )

                st.success(
                    "Kapazität vorhanden. "
                    "Zur Verwaltungsfreigabe vorgeschlagen."
                )

    else:

        st.info(
            "Keine neuen Freigabevorschläge vorhanden."
        )

    st.divider()

    # ----------------------------------------------
    # INTELLIGENTE WARTELISTE
    # ----------------------------------------------

    st.subheader(
        "Intelligente Warteliste"
    )

    st.caption(
        "Diese Fälle bleiben gespeichert und "
        "rücken bei frei werdender Kapazität "
        "automatisch in die Freigabevorschläge nach."
    )

    waiting_items = sorted(
        delegation["waiting_list"],
        key=lambda item: -item["queue_score"],
    )

    if waiting_items:

        waiting_rows = []

        for position, item in enumerate(
            waiting_items,
            start=1,
        ):

            waiting_rows.append({
                "Position": position,
                "Schadensfall": item["case_id"],
                "Beschreibung": item["description"],
                "Abteilung": item["department"],
                "Priorität": item["priority"],
                "Wartezeit (Tage)": item[
                    "waiting_days"
                ],
                "Queue Score": item[
                    "queue_score"
                ],
                "Status": item[
                    "delegation_status"
                ],
            })

        st.dataframe(
            waiting_rows,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.success(
            "Die Warteliste ist aktuell leer."
        )

    st.divider()

    # ----------------------------------------------
    # OVERLOAD DETECTION
    # ----------------------------------------------

    st.subheader(
        "Overload Detection"
    )

    if delegation["escalations"]:

        for item in delegation["escalations"]:

            st.error(
                "KRITISCHE ESKALATION: "
                f"Schadensfall #{item['case_id']} – "
                f"{item['department']} hat keine "
                "freie Kapazität. "
                "Sofortige manuelle Prüfung erforderlich."
            )

    else:

        st.success(
            "Keine kritischen Schadensfälle "
            "wegen Kapazitätsmangel zurückgestellt."
        )

    st.divider()

    # ----------------------------------------------
    # BEREITS ZUGEWIESENE AUFGABEN
    # ----------------------------------------------

    st.subheader(
        "Bereits zugewiesene Schadensfälle"
    )

    if active_cases:

        st.dataframe(
            active_cases,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "Noch keine aktiven Zuweisungen vorhanden."
        )

    st.caption(
        "Die Warteliste wird bei jedem Dashboard-Aufruf "
        "neu berechnet. Die Kapazitätsgrenze ist simuliert."
    )


# ==================================================
# TAB 4: VERWALTUNGSFREIGABEN
# ==================================================

with tab4:

    st.subheader(
        "Verwaltungsfreigaben"
    )

    st.info(
        "KI-Empfehlungen werden vor der endgültigen "
        "Aufgabenzuweisung durch die Verwaltung geprüft."
    )

    if not damage_cases:

        st.warning(
            "Keine Schadensfälle vorhanden."
        )

    else:

        # ------------------------------------------
        # KENNZAHLEN
        # ------------------------------------------

        current_ids = {
            int(case["id"])
            for case in damage_cases
        }

        approved_count = sum(
            approval.get("decision") in (
                "APPROVED",
                "REASSIGNED",
            )
            for case_id, approval in (
                approvals_by_case.items()
            )
            if case_id in current_ids
        )

        rejected_count = sum(
            approval.get("decision") == "REJECTED"
            for case_id, approval in (
                approvals_by_case.items()
            )
            if case_id in current_ids
        )

        pending_count = sum(
            int(case["id"]) not in approvals_by_case
            and case.get("status") not in (
                "Erledigt",
                "Abgelehnt",
            )
            for case in damage_cases
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Freigabe ausstehend",
                pending_count,
            )

        with col2:
            st.metric(
                "Genehmigte Empfehlungen",
                approved_count,
            )

        with col3:
            st.metric(
                "Abgelehnte Empfehlungen",
                rejected_count,
            )

        st.divider()

        # ------------------------------------------
        # WARTELISTE UND ABTEILUNGEN
        # ------------------------------------------

        ready_case_ids = {
            int(item["case_id"])
            for item in delegation[
                "ready_for_approval"
            ]
        }

        waiting_case_ids = {
            int(item["case_id"])
            for item in delegation[
                "waiting_list"
            ]
        }

        all_department_names = [
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
            "Kommunaler Ordnungsdienst",
        ]

        # ------------------------------------------
        # SCHADENSFÄLLE
        # ------------------------------------------

        for case in damage_cases:

            case_id = int(case["id"])

            report = case[
                "priority_report"
            ]

            existing_approval = (
                approvals_by_case.get(case_id)
            )

            with st.expander(
                f"Schadensfall #{case_id} – "
                f"{safe_text(case['description'])}"
            ):

                st.write(
                    "**Beschreibung:**",
                    safe_text(
                        case["description"]
                    ),
                )

                st.write(
                    "**KI-Priorität:**",
                    get_priority(report),
                )

                st.write(
                    "**Anzahl Bürger-Meldungen:**",
                    case["report_count"],
                )

                st.divider()

                # ----------------------------------
                # KI-EMPFEHLUNG
                # ----------------------------------

                try:

                    recommendation = (
                        get_recommendation(case)
                    )

                except Exception as exc:

                    st.error(
                        "KI-Empfehlung nicht verfügbar: "
                        f"{exc}"
                    )

                    continue

                department = (
                    recommendation.get("department")
                    or {}
                )

                if not isinstance(
                    department,
                    dict,
                ):
                    department = {
                        "name": str(department)
                    }

                capacity = (
                    recommendation.get("capacity")
                    or {}
                )

                if not isinstance(
                    capacity,
                    dict,
                ):
                    capacity = {}

                recommended_department = (
                    get_department_name(
                        recommendation
                    )
                )

                st.subheader(
                    "KI-Empfehlung"
                )

                st.success(
                    "Empfohlene Abteilung: "
                    f"{recommended_department}"
                )

                st.write(
                    "**Übergeordnete Einheit:**",
                    department.get(
                        "parent",
                        "Nicht verfügbar",
                    ),
                )

                st.write(
                    "**Dezernat:**",
                    department.get(
                        "dezernat",
                        "Nicht verfügbar",
                    ),
                )

                st.write(
                    "**Organisationscode:**",
                    department.get(
                        "code",
                        "Nicht verfügbar",
                    ),
                )

                st.divider()

                # ----------------------------------
                # KAPAZITÄTSPRÜFUNG
                # ----------------------------------

                st.subheader(
                    "Kapazitätsprüfung"
                )

                target_occupied = (
                    occupied_capacity.get(
                        recommended_department,
                        0,
                    )
                )

                target_free = max(
                    0,
                    int(max_capacity) - target_occupied,
                )

                st.write(
                    "**Freie simulierte Aufgabenplätze:**",
                    target_free,
                )

                if case_id in ready_case_ids:

                    st.success(
                        "Zur Freigabe vorgeschlagen: "
                        "Kapazität für diesen Fall reservierbar."
                    )

                elif case_id in waiting_case_ids:

                    st.warning(
                        "Warteliste: Für diesen Fall "
                        "ist derzeit kein freier "
                        "Aufgabenplatz vorgesehen."
                    )

                elif existing_approval:

                    st.info(
                        "Für diesen Fall wurde bereits "
                        "eine Verwaltungsentscheidung gespeichert."
                    )

                else:

                    st.info(
                        "Keine aktive Delegation für "
                        "diesen Schadensfall verfügbar."
                    )

                try:

                    available_capacity = float(
                        capacity.get(
                            "available_capacity",
                            0,
                        )
                    )

                except (ValueError, TypeError):
                    available_capacity = 0.0

                available_capacity = max(
                    0.0,
                    min(
                        100.0,
                        available_capacity,
                    ),
                )

                st.progress(
                    available_capacity / 100.0
                )

                st.write(
                    "**KI-Kapazitätsschätzung:**",
                    f"{available_capacity:.0f} %",
                )

                st.caption(
                    "Kapazitätswerte sind für die Demo "
                    "simuliert. Die KI-Prozentangabe "
                    "ist nicht identisch mit den "
                    "belegten Aufgabenplätzen."
                )

                st.divider()

                # ----------------------------------
                # BISHERIGE ENTSCHEIDUNG
                # ----------------------------------

                if existing_approval:

                    previous = (
                        existing_approval.get(
                            "decision"
                        )
                    )

                    if previous == "APPROVED":

                        st.success(
                            "Status: KI-Empfehlung genehmigt."
                        )

                    elif previous == "REJECTED":

                        st.error(
                            "Status: KI-Empfehlung abgelehnt."
                        )

                    elif previous == "REASSIGNED":

                        st.success(
                            "Status: Andere Abteilung zugewiesen."
                        )

                    st.write(
                        "**Zugewiesene Abteilung:**",
                        safe_text(
                            existing_approval.get(
                                "assigned_department"
                            )
                        ),
                    )

                    st.write(
                        "**Kommentar:**",
                        safe_text(
                            existing_approval.get(
                                "comment"
                            )
                        ),
                    )

                    st.write(
                        "**Entschieden am:**",
                        existing_approval.get(
                            "decided_at"
                        ),
                    )

                    st.divider()

                # ----------------------------------
                # ERLEDIGTE FÄLLE
                # ----------------------------------

                if case.get("status") == "Erledigt":

                    st.info(
                        "Dieser Schadensfall "
                        "ist bereits erledigt."
                    )

                    continue

                # ----------------------------------
                # VERWALTUNGSENTSCHEIDUNG
                # ----------------------------------

                st.subheader(
                    "Verwaltungsentscheidung"
                )

                with st.form(
                    key=f"approval_form_{case_id}"
                ):

                    decision = st.radio(
                        "Entscheidung auswählen",
                        [
                            "Approve",
                            "Reject",
                            "Reassign",
                        ],
                        horizontal=True,
                    )

                    choices = list(
                        all_department_names
                    )

                    if (
                        recommended_department
                        not in choices
                    ):
                        choices.insert(
                            0,
                            recommended_department,
                        )

                    if existing_approval:

                        old_department = (
                            existing_approval.get(
                                "assigned_department"
                            )
                        )

                        if (
                            old_department
                            and old_department not in choices
                        ):
                            choices.append(
                                old_department
                            )

                    selected_department = st.selectbox(
                        "Zuständige Abteilung",
                        options=choices,
                        index=choices.index(
                            recommended_department
                        ),
                    )

                    comment = st.text_area(
                        "Kommentar der Verwaltung",
                        placeholder=(
                            "Begründung oder zusätzliche "
                            "Informationen eingeben ..."
                        ),
                    )

                    submitted = st.form_submit_button(
                        "Entscheidung speichern",
                        type="primary",
                        use_container_width=True,
                    )

                # ----------------------------------
                # ENTSCHEIDUNG SPEICHERN
                # ----------------------------------

                if submitted:

                    decision_mapping = {
                        "Approve": "APPROVED",
                        "Reject": "REJECTED",
                        "Reassign": "REASSIGNED",
                    }

                    database_decision = (
                        decision_mapping[decision]
                    )

                    if decision == "Approve":

                        final_department = (
                            recommended_department
                        )

                    elif decision == "Reassign":

                        final_department = (
                            selected_department
                        )

                    else:

                        final_department = None

                    # ----------------------------------
                    # BISHERIGE ZUWEISUNG
                    # ----------------------------------

                    previous_active = bool(
                        existing_approval
                        and existing_approval.get(
                            "decision"
                        ) in (
                            "APPROVED",
                            "REASSIGNED",
                        )
                    )

                    previous_department = None

                    if previous_active:

                        previous_department = (
                            existing_approval.get(
                                "assigned_department"
                            )
                            or recommended_department
                        )

                    # ----------------------------------
                    # KAPAZITÄT PRÜFEN
                    # ----------------------------------

                    target_occupied = 0

                    if final_department:

                        target_occupied = (
                            occupied_capacity.get(
                                final_department,
                                0,
                            )
                        )

                    # Bei Änderung einer bestehenden
                    # Freigabe denselben Fall nicht
                    # doppelt zählen.

                    if (
                        previous_active
                        and final_department
                        == previous_department
                    ):

                        target_occupied = max(
                            0,
                            target_occupied - 1,
                        )

                    # ----------------------------------
                    # KAPAZITÄTSGRENZE
                    # ----------------------------------

                    if (
                        final_department
                        and target_occupied
                        >= int(max_capacity)
                    ):

                        st.error(
                            "Keine freie Kapazität bei "
                            f"'{final_department}'. "
                            "Bitte eine andere Abteilung "
                            "wählen oder den Fall auf "
                            "der Warteliste lassen."
                        )

                    # ----------------------------------
                    # PRIORISIERUNG PRÜFEN
                    # ----------------------------------

                    elif (
                        decision == "Approve"
                        and not previous_active
                        and case_id not in ready_case_ids
                    ):

                        st.error(
                            "Dieser Fall ist derzeit "
                            "nicht zur Freigabe vorgesehen. "
                            "Bitte Warteliste und "
                            "Priorisierung prüfen."
                        )

                    # ----------------------------------
                    # SPEICHERN
                    # ----------------------------------

                    else:

                        try:

                            save_approval(
                                report_id=case_id,
                                decision=database_decision,
                                assigned_department=final_department,
                                comment=comment,
                            )

                            new_status = (
                                "Abgelehnt"
                                if decision == "Reject"
                                else "Genehmigt"
                            )

                            # Alle Meldungen desselben
                            # Schadensfalls synchronisieren,
                            # inklusive Originalmeldung.

                            for report_id in case[
                                "report_ids"
                            ]:

                                update_report_status(
                                    report_id,
                                    new_status,
                                )

                            st.success(
                                "Verwaltungsentscheidung "
                                "erfolgreich gespeichert."
                            )

                            st.rerun()

                        except Exception as exc:

                            st.error(
                                "Fehler beim Speichern: "
                                f"{exc}"
                            )