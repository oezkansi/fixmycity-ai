# report_pipeline.py
from validation import validate_report
from categorization import categorize_report, CATEGORIES_DB
from prioritization import calculate_advanced_priority
from prognosis import calculate_prognosis

def process_report(image_path, description, location, district="Bezirk_Mitte", is_main_road=False, citizen_urgency=3, days_waiting=0):
    """
    Führt die vollständige Validierung, KI-Klassifizierung, Priorisierung 
    und standortbezogene Schadensprognose für einen eingereichten Schaden durch.
    """
    # 1. Bild- und Textvalidierung
    validation = validate_report(image_path, description)
    print(f"VALIDIERUNGSERGEBNIS: {validation}", flush=True)

    if validation["status"] != "VALID":
        return {
            "location": location,
            "description": description,
            "validation": validation,
            "category_data": None,
            "priority_data": None,
            "prognosis_data": None
        }

    print("\n1. KI klassifiziert den Schaden anhand der JSON-Datenbank ...")
    # 2. Präzise Kategorisierung über die JSON-Struktur
    cat_result = categorize_report(image_path, description)
    category = cat_result.get("category")
    subcategory = cat_result.get("subcategory")
    department = cat_result.get("department")

    # Subkategorien-Details auslesen
    sub_data = {}
    if category in CATEGORIES_DB and subcategory in CATEGORIES_DB[category]["subcategories"]:
        sub_data = CATEGORIES_DB[category]["subcategories"][subcategory]

    print(f"Kategorie erkannt: {category} -> {subcategory} (Abteilung: {department})")

    print("\n2. Berechne dynamische Priorität & Schadensprognose mit Wetterdaten ...")
    # 3. Erweiterte Priorisierung berechnen
    priority_data = calculate_advanced_priority(
        sub_data=sub_data,
        days_waiting=days_waiting,
        is_main_road=is_main_road,
        citizen_urgency=citizen_urgency
    )

    # 4. Schadensprognose inklusive Wetterfaktor berechnen (mit Übergabe des Standorts)
    prognosis_data = calculate_prognosis(
        category=category,
        subcategory=subcategory,
        days_elapsed=days_waiting,
        location_str=location
    )

    return {
        "location": location,
        "description": description,
        "district": district,
        "is_main_road": is_main_road,
        "category_data": cat_result,
        "sub_data": sub_data,
        "priority_data": priority_data,
        "prognosis_data": prognosis_data
    }

if __name__ == "__main__":
    image_path = input("Bildpfad: ")
    description = input("Schadensbeschreibung: ")
    location = input("Standort (z.B. lat,lon oder Adresse): ")
    district = input("Bezirk (z.B. Bezirk_Mitte): ") or "Bezirk_Mitte"
    is_main_road = input("Ist Hauptstraße? (j/n): ").lower() == 'j'
    citizen_urgency = int(input("Bürger-Dringlichkeit (1-5): "))

    result = process_report(image_path, description, location, district, is_main_road, citizen_urgency)

    print("\n--- PIPELINE ERGEBNIS ---")
    print("Klassifizierung:", result.get("category_data"))
    print("Priorität:", result.get("priority_data"))
    print("Prognose:", result.get("prognosis_data"))