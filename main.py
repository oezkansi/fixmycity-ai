
from categorization import categorize_report
from prioritization import calculate_priority

# Vorläufige Risikowerte für unsere Testkategorien
RISK_LEVELS = {
    "Road Damage": (2, 2, 2),
    "Dangerous Waste": (3, 2, 2),
    "Traffic Hazards": (3, 3, 3),
    "Street Lighting": (1, 2, 1),
    "Waste & Cleanliness": (1, 1, 1),
    "Green Spaces": (2, 1, 1)
}

print("=== FixMyCity AI ===")

description = input("Beschreibe den Schaden: ")

citizen_urgency = int(input(
    "Wie dringend findest du das Problem? (1-5): "
))

if not 1 <= citizen_urgency <= 5:
    raise ValueError("Bitte eine Zahl zwischen 1 und 5 eingeben.")

category = categorize_report(description)

print("\n--- Ergebnis für die Verwaltung ---")
print("Kategorie:", category)
print("Bürgerbewertung:", citizen_urgency, "/5")

if category == "Manual Review":
    print("Priorität: Manuelle Prüfung erforderlich")
else:
    danger, impact, urgency = RISK_LEVELS[category]

    result = calculate_priority(danger, impact, urgency)

    print("KI-Priorität:", result["priority"])
    print("Risikoscore:", result["score"])
