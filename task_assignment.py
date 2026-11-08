"""
FixMyCity AI – Intelligent Task Assignment

Funktionen:
1. Department Matching
2. Capacity Matching
3. Task Recommendation

Die Verwaltungsstruktur basiert auf den bereitgestellten
Organisationsdaten der Stadt Pforzheim.

Teamkapazitäten sind simulierte Demodaten.
"""

import re
import json
from difflib import SequenceMatcher


# --------------------------------------------------
# 1. OFFIZIELLE ORGANISATIONSEINHEITEN
# --------------------------------------------------

DEPARTMENTS = {

    "road_maintenance": {
        "name": "Grünflächenmanagement und Straßenunterhaltung",
        "parent": "Grünflächen- und Tiefbauamt",
        "dezernat": "Dezernat 2",
        "code": "6021803",
        "role": "Incident handling",
        "capacity": 80,
        "open_tasks": 12,
        "keywords": [
            "schlagloch",
            "loch in straße",
            "loch in strasse",
            "fahrbahnschaden",
            "fahrbahn",
            "asphalt",
            "straßenschaden",
            "strassenschaden",
            "gehweg",
            "bürgersteig",
            "bordstein",
            "parkbank",
            "grünfläche",
            "rasen",
            "baum",
            "ast",
            "spielplatz",
        ],
    },

    "traffic_lighting": {
        "name": "Verkehrs- und Beleuchtungstechnik",
        "parent": "Straßenneubau und Verkehrstechnik",
        "dezernat": "Dezernat 2",
        "code": "6047075",
        "role": "Incident handling",
        "capacity": 65,
        "open_tasks": 8,
        "keywords": [
            "straßenlaterne",
            "strassenlaterne",
            "laterne",
            "straßenbeleuchtung",
            "beleuchtung",
            "ampel",
            "lichtsignalanlage",
            "verkehrsampel",
            "defekte lampe",
        ],
    },

    "waste_management": {
        "name": "Abfallwirtschaft",
        "parent": "Technische Dienste",
        "dezernat": "Dezernat 1",
        "code": "6021657",
        "role": "Incident handling",
        "capacity": 90,
        "open_tasks": 5,
        "keywords": [
            "müll",
            "muell",
            "abfall",
            "sperrmüll",
            "sperrmuell",
            "illegale müllentsorgung",
            "wilde müllkippe",
            "entsorgung",
            "müllablagerung",
            "mülltonne",
            "papierkorb",
        ],
    },

    "waste_service": {
        "name": "Service-Center Abfallwirtschaft",
        "parent": "Abfallwirtschaft",
        "dezernat": "Dezernat 1",
        "code": "6021663",
        "role": "Incident handling",
        "capacity": 85,
        "open_tasks": 4,
        "keywords": [
            "abfallberatung",
            "abfallservice",
            "abfallanfrage",
            "müllabholung",
            "tonnenleerung",
        ],
    },

    "sewerage": {
        "name": "Betrieb (BE)",
        "parent": "Eigenbetrieb Stadtentwässerung Pforzheim",
        "dezernat": "Dezernat 4",
        "code": "6021631",
        "role": "Incident handling",
        "capacity": 70,
        "open_tasks": 7,
        "keywords": [
            "kanal",
            "kanaldeckel",
            "gully",
            "abwasser",
            "kanalisation",
            "abfluss",
            "verstopfter abfluss",
            "rückstau",
        ],
    },

    "traffic_authority": {
        "name": "Straßenverkehrsbehörde",
        "parent": "Straßenverkehr",
        "dezernat": "Dezernat 4",
        "code": "6021552",
        "role": "Incident handling",
        "capacity": 75,
        "open_tasks": 6,
        "keywords": [
            "verkehrsregelung",
            "verkehrsanordnung",
            "verkehrsführung",
            "verkehrsbeschränkung",
            "verkehrssicherheit",
        ],
    },

    "public_order": {
        "name": "Kommunaler Ordnungsdienst",
        "parent": "Gemeindevollzugsdienst",
        "dezernat": "Dezernat 4",
        "code": "6056853",
        "role": "Enforcement",
        "capacity": 75,
        "open_tasks": 9,
        "keywords": [
            "ordnungswidrigkeit",
            "illegale ablagerung",
            "vandalismus",
            "sachbeschädigung",
            "ruhestörung",
            "unerlaubte nutzung",
        ],
    },

    "parking_enforcement": {
        "name": "Verkehrsordnungsdienst",
        "parent": "Gemeindevollzugsdienst",
        "dezernat": "Dezernat 4",
        "code": "6056855",
        "role": "Enforcement",
        "capacity": 70,
        "open_tasks": 10,
        "keywords": [
            "falschparker",
            "falschparken",
            "zugeparkt",
            "parkverstoß",
            "parkverstoss",
            "parkbehinderung",
        ],
    },

    "environment": {
        "name": "Umwelttechnik",
        "parent": "Amt für Umweltschutz",
        "dezernat": "Dezernat 2",
        "code": "6021795",
        "role": "Incident handling",
        "capacity": 80,
        "open_tasks": 4,
        "keywords": [
            "umweltverschmutzung",
            "gewässerverschmutzung",
            "bodenverschmutzung",
            "ölverschmutzung",
            "chemikalien",
            "umweltschaden",
        ],
    },

    "forestry": {
        "name": "Forstverwaltung - Untere Forstbehörde",
        "parent": "Amt für Umweltschutz",
        "dezernat": "Dezernat 2",
        "code": "6021789",
        "role": "Incident handling",
        "capacity": 75,
        "open_tasks": 5,
        "keywords": [
            "wald",
            "waldweg",
            "forst",
            "forstschaden",
            "umgestürzter baum im wald",
        ],
    },

    "public_transport": {
        "name": "Werterhaltung, Barrierefreiheit und ÖPNV",
        "parent": "Straßenneubau und Verkehrstechnik",
        "dezernat": "Dezernat 2",
        "code": "6047077",
        "role": "Incident handling",
        "capacity": 70,
        "open_tasks": 6,
        "keywords": [
            "bushaltestelle",
            "haltestelle",
            "barrierefreiheit",
            "taktile leitstreifen",
            "blindennavigation",
            "öpnv",
            "bussteig",
        ],
    },

    "public_buildings": {
        "name": "Technisches Gebäudemanagement",
        "parent": "Gebäudemanagement",
        "dezernat": "Dezernat 2",
        "code": "6021801",
        "role": "Incident handling",
        "capacity": 75,
        "open_tasks": 8,
        "keywords": [
            "öffentliches gebäude",
            "städtisches gebäude",
            "gebäudeschaden",
            "defektes fenster",
            "gebäudetechnik",
        ],
    },

    "sports": {
        "name": "Sport (Abteilung)",
        "parent": "Amt für Bildung und Sport",
        "dezernat": "Dezernat 3",
        "code": "6021673",
        "role": "Incident handling",
        "capacity": 80,
        "open_tasks": 3,
        "keywords": [
            "sportplatz",
            "sportanlage",
            "sporthalle",
            "bolzplatz",
            "sportgerät",
        ],
    },

    "fire_department": {
        "name": "Feuerwehr",
        "parent": None,
        "dezernat": "Dezernat 4",
        "code": "6008752",
        "role": "Emergency escalation",
        "capacity": None,
        "open_tasks": None,
        "keywords": [
            "brand",
            "feuer",
            "rauchentwicklung",
            "explosion",
            "akute lebensgefahr",
        ],
    },
}


# --------------------------------------------------
# 2. TEXT NORMALISIEREN
# --------------------------------------------------

def normalize_text(text):
    """
    Vereinheitlicht Texte für den Vergleich.
    """

    text = str(text or "").lower()

    text = text.replace("ß", "ss")

    text = re.sub(r"[^\w\s]", " ", text)

    return " ".join(text.split())


# --------------------------------------------------
# 3. GESPEICHERTE KI-DATEN VERARBEITEN
# --------------------------------------------------

def parse_value(value):
    """
    Verarbeitet JSON-Daten aus der Datenbank.
    """

    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value

    return value


def extract_report_text(report):
    """
    Kombiniert Beschreibung und vorhandene
    KI-Ergebnisse für das Department Matching.
    """

    text_parts = [
        str(report.get("description") or "")
    ]

    validation = parse_value(
        report.get("validation")
    )

    if isinstance(validation, dict):

        detected_problem = validation.get(
            "detected_problem"
        )

        if detected_problem:
            text_parts.append(
                str(detected_problem)
            )

    category = parse_value(
        report.get("category")
    )

    if isinstance(category, dict):

        for key in ["category", "label", "name"]:

            if category.get(key):
                text_parts.append(
                    str(category[key])
                )

    elif category:
        text_parts.append(str(category))

    return normalize_text(
        " ".join(text_parts)
    )


# --------------------------------------------------
# 4. DEPARTMENT MATCHING
# --------------------------------------------------

def calculate_department_score(report_text, department):
    """
    Berechnet einen Matching-Score anhand
    passender Schlüsselbegriffe.

    Der Score ist ein heuristischer Wert
    und keine trainierte ML-Wahrscheinlichkeit.
    """

    score = 0

    for keyword in department["keywords"]:

        normalized_keyword = normalize_text(keyword)

        if normalized_keyword in report_text:

            score += 10 + len(
                normalized_keyword.split()
            )

        else:

            similarity = SequenceMatcher(
                None,
                report_text,
                normalized_keyword
            ).ratio()

            if similarity >= 0.85:
                score += 3

    return score


def match_department(report):
    """
    Ermittelt die wahrscheinlich passende
    Organisationseinheit.
    """

    report_text = extract_report_text(report)

    matches = []

    for department_id, department in DEPARTMENTS.items():

        score = calculate_department_score(
            report_text,
            department
        )

        if score > 0:

            matches.append({
                "department_id": department_id,
                "score": score,
                **department
            })

    matches.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    if not matches:

        return {
            "status": "MANUAL_REVIEW",
            "department": None,
            "alternatives": [],
            "reason": (
                "Keine eindeutige Organisationseinheit "
                "gefunden. Manuelle Zuordnung erforderlich."
            )
        }

    best_match = matches[0]

    return {
        "status": "MATCH_FOUND",
        "department": best_match,
        "alternatives": matches[1:4],
        "reason": (
            "Die Organisationseinheit wurde anhand "
            "der Schadensbeschreibung und vorhandener "
            "KI-Analyseergebnisse vorgeschlagen."
        )
    }


# --------------------------------------------------
# 5. CAPACITY MATCHING
# --------------------------------------------------

def assess_capacity(department):
    """
    Bewertet simulierte Teamkapazitäten.
    """

    if department is None:

        return {
            "status": "UNKNOWN",
            "available_capacity": None,
            "open_tasks": None,
            "message": "Keine Abteilung zugeordnet."
        }

    capacity = department.get("capacity")

    open_tasks = department.get("open_tasks")

    if capacity is None:

        return {
            "status": "NOT_APPLICABLE",
            "available_capacity": None,
            "open_tasks": open_tasks,
            "message": (
                "Für diese Einheit wird keine "
                "simulierte Kapazität angegeben."
            )
        }

    if capacity >= 70:
        status = "AVAILABLE"

    elif capacity >= 40:
        status = "LIMITED"

    else:
        status = "OVERLOADED"

    return {
        "status": status,
        "available_capacity": capacity,
        "open_tasks": open_tasks,
        "message": (
            f"Simulierte verfügbare Kapazität: "
            f"{capacity} %."
        )
    }


# --------------------------------------------------
# 6. PRIORITÄT AUSLESEN
# --------------------------------------------------

def extract_priority(report):

    priority = parse_value(
        report.get("priority")
    )

    if isinstance(priority, dict):

        priority = (
            priority.get("priority")
            or priority.get("level")
            or priority.get("priority_level")
            or priority.get("label")
        )

    return str(priority or "Nicht bewertet")


# --------------------------------------------------
# 7. TASK RECOMMENDATION
# --------------------------------------------------

def recommend_task(report):
    """
    Erstellt eine Empfehlung für die Verwaltung.

    Es wird keine automatische Zuweisung
    oder Freigabe durchgeführt.
    """

    matching = match_department(report)

    department = matching["department"]

    capacity = assess_capacity(department)

    priority = extract_priority(report)

    if department is None:

        return {
            "report_id": report.get("id"),
            "status": "MANUAL_REVIEW",
            "priority": priority,
            "department": None,
            "capacity": capacity,
            "reason": matching["reason"],
            "alternatives": [],
            "requires_approval": True
        }

    recommendation = {
        "report_id": report.get("id"),
        "status": "AWAITING_APPROVAL",
        "priority": priority,
        "department": {
            "id": department["department_id"],
            "name": department["name"],
            "parent": department["parent"],
            "dezernat": department["dezernat"],
            "code": department["code"],
            "role": department["role"]
        },
        "capacity": capacity,
        "reason": matching["reason"],
        "alternatives": [
            {
                "name": alternative["name"],
                "code": alternative["code"],
                "dezernat": alternative["dezernat"]
            }
            for alternative in matching["alternatives"]
        ],
        "requires_approval": True
    }

    if department["role"] == "Emergency escalation":

        recommendation["status"] = "EMERGENCY_ESCALATION"

        recommendation["reason"] = (
            "Die Meldung enthält Hinweise auf eine "
            "mögliche akute Gefahr. "
            "Sofortige menschliche Prüfung erforderlich."
        )

    return recommendation


# --------------------------------------------------
# 8. MEHRERE MELDUNGEN VERARBEITEN
# --------------------------------------------------

def assign_all_reports(reports):
    """
    Erstellt Empfehlungen für mehrere Meldungen.
    """

    return [
        recommend_task(report)
        for report in reports
    ]


# --------------------------------------------------
# 9. TESTFUNKTION
# --------------------------------------------------

if __name__ == "__main__":

    test_report = {
        "id": 1,
        "description": "Großes Schlagloch auf der Fahrbahn",
        "priority": "P1 - Critical"
    }

    result = recommend_task(test_report)

    print(
        json.dumps(
            result,
            indent=4,
            ensure_ascii=False
        )
    )