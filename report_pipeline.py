# pipeline.py
from validation import validate_report
from categorization import categorize_report, CATEGORIES_DB
from prioritization import calculate_advanced_priority
from prognosis import calculate_prognosis
from database import check_for_duplicates, save_report
from datetime import datetime

def process_and_save_report(image_path, description, location, district="Bezirk_Mitte", is_main_road=False, citizen_urgency=3, days_waiting=0):
    """
    Führt die vollständige FixMyCity-Pipeline aus:
    1. Validierung (Bild + Text via Gemini)
    2. Duplikatsprüfung am Standort
    3. Klassifizierung (Kategorie, Subkategorie, Abteilung)
    4. Priorisierung (Inkl. Wetterfaktor & transparentem Breakdown)
    5. Prognose-Berechnung
    6. Speicherung in der SQLite-Datenbank (inkl. Timestamp)
    """
    
    # 1. Validierung: Prüfen, ob Bild und Beschreibung zusammenpassen und ein Schaden vorliegt
    validation = validate_report(image_path, description)
    if validation.get("status") != "VALID":
        return {
            "success": False,
            "error": f"Meldung abgelehnt: {validation.get('reason', 'Ungültiges Bild oder Beschreibung.')}"
        }

    # 2. KI-Klassifizierung des Schadens
    cat_result = categorize_report(image_path, description)
    category = cat_result.get("category")
    subcategory = cat_result.get("subcategory")

    sub_data = {}
    if category in CATEGORIES_DB and subcategory in CATEGORIES_DB[category]["subcategories"]:
        sub_data = CATEGORIES_DB[category]["subcategories"][subcategory]

    # 3. Duplikatsprüfung: Verhindern von Mehrfachmeldungen im selben Umkreis
    is_dup, existing_id = check_for_duplicates(location, category, subcategory)
    if is_dup:
        return {
            "success": False,
            "error": f"Ähnlicher aktiver Schaden (ID: {existing_id}) existiert bereits an diesem Standort. Meldung wurde als Duplikat abgewiesen."
        }

    # 4. Erweiterte Priorisierung (inkl. Wetterfaktor & Transparenz-Breakdown)
    priority_data = calculate_advanced_priority(
        sub_data=sub_data,
        days_waiting=days_waiting,
        is_main_road=is_main_road,
        citizen_urgency=citizen_urgency,
        location_str=location
    )

    # 5. Prognose zur Schadensentwicklung berechnen
    prognosis_data = calculate_prognosis(
        category=category,
        subcategory=subcategory,
        days_elapsed=days_waiting,
        location_str=location
    )

    # Zeitstempel für den Bericht
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Finales Datenpaket schnüren
    report_payload = {
        "success": True,
        "timestamp": timestamp,
        "location": location,
        "district": district,
        "is_main_road": is_main_road,
        "description": description,
        "category_data": cat_result,
        "sub_data": sub_data,
        "priority_data": priority_data,
        "prognosis_data": prognosis_data
    }

    # 6. Direkt in der Datenbank abspeichern
    save_report(report_payload)

    return report_payload