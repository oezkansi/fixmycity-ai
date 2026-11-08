
from validation import validate_report
from ai_analysis import analyze_report
from ai_priority import analyze_priority


def process_report(image_path, description, location):

    full_description = (
        f"Standort: {location}\n"
        f"Beschreibung: {description}"
    )

    # 1. Zuerst prüfen: Notfall oder gültiger Schaden?
    validation = validate_report(image_path, description)

    print(
        "VALIDIERUNGSERGEBNIS:",
        validation,
        flush=True
    )

    status = validation.get("status", "UNCERTAIN")

    # 2. Möglicher akuter Notfall
    if status == "EMERGENCY":
        print(
            "MÖGLICHER NOTFALL ERKANNT – "
            "keine normale Schadensweiterleitung.",
            flush=True
        )

        return {
            "location": location,
            "description": description,
            "validation": validation,
            "image_analysis": None,
            "risk_factors": None,
            "priority": None
        }

    # 3. Ungültige oder unklare Meldung
    if status != "VALID":
        return {
            "location": location,
            "description": description,
            "validation": validation,
            "image_analysis": None,
            "risk_factors": None,
            "priority": None
        }

    # 4. Normale KI-Bildanalyse
    print("\n1. KI analysiert das Bild ...")

    image_analysis = analyze_report(
        image_path,
        full_description
    )

    # 5. KI-Priorisierung
    print("\n2. KI bewertet die Risiken ...")

    factors, priority = analyze_priority(
        full_description
        + "\nBildanalyse:\n"
        + image_analysis
    )

    # 6. Vollständiges Ergebnis
    return {
        "location": location,
        "description": description,
        "validation": validation,
        "image_analysis": image_analysis,
        "risk_factors": factors,
        "priority": priority
    }


if __name__ == "__main__":

    image_path = input("Bildpfad: ")
    description = input("Schadensbeschreibung: ")
    location = input("Standort: ")

    result = process_report(
        image_path,
        description,
        location
    )

    print("\n--- ERGEBNIS ---")
    print("Validierung:", result["validation"])
    print("Bildanalyse:", result["image_analysis"])
    print("Risikofaktoren:", result["risk_factors"])
    print("Priorität:", result["priority"])
