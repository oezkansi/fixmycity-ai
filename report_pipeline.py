from validation import validate_report
from ai_analysis import analyze_report
from ai_priority import analyze_priority
from location_validation import check_location_responsibility

def process_report(image_path, description, location):
    full_description = (
        f"Standort: {location}\n"
        f"Beschreibung: {description}"
    )

    validation = validate_report(image_path, description)
    print("VALIDIERUNGSERGEBNIS:", validation, flush=True)

    if validation["status"] != "VALID":
        return {
            "location": location,
            "description": description,
            "validation": validation,
            "image_analysis": None,
            "risk_factors": None,
            "priority": None
        }


    print("\n1. KI analysiert das Bild ...")

    image_analysis = analyze_report(
        image_path, full_description
    )

    print("\n2. KI prüft die Zuständigkeit ...")

    responsibility = check_location_responsibility(
        location,
        description,
        image_analysis
    )
    
    print("ZUSTÄNDIGKEITSERGEBNIS:", responsibility)


    print("\n2. KI bewertet die Risiken ...")

    factors, priority = analyze_priority(
        full_description + "\nBildanalyse:\n" + image_analysis
    )

    return {
        "location": location,
        "description": description,
        "validation": validation,
        "responsibility": responsibility,
        "image_analysis": image_analysis,
        "risk_factors": factors,
        "priority": priority
    }


if __name__ == "__main__":
    image_path = input("Bildpfad: ")
    description = input("Schadensbeschreibung: ")
    location = input("Standort: ")

    result = process_report(
        image_path, description, location
    )

    print("\n--- ERGEBNIS ---")
    print("Bildanalyse:", result["image_analysis"])
    print("Risikofaktoren:", result["risk_factors"])
    print("Priorität:", result["priority"])
