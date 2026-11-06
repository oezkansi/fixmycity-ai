
CATEGORIES = {
    "Road Damage": [
        "schlagloch", "fahrbahnriss", "straßenschaden",
        "strassenschaden", "asphalt", "loch in der straße"
    ],
    "Dangerous Waste": [
        "spritze", "spritzen", "nadel", "nadeln",
        "glasscherben", "gefährlicher abfall"
    ],
    "Traffic Hazards": [
        "tier auf der autobahn", "tier auf der fahrbahn",
        "hindernis", "unfallgefahr", "leitplanke"
    ],
    "Street Lighting": [
        "laterne", "straßenbeleuchtung",
        "strassenbeleuchtung", "licht defekt"
    ],
    "Waste & Cleanliness": [
        "müll", "muell", "sperrmüll",
        "müllablagerung", "papierkorb"
    ],
    "Green Spaces": [
        "umgestürzter baum", "ast abgebrochen",
        "baum gefallen", "grünfläche"
    ]
}


def categorize_report(description):
    text = description.lower()

    for category, keywords in CATEGORIES.items():
        if any(keyword in text for keyword in keywords):
            return category

    return "Manual Review"


if __name__ == "__main__":
    description = input("Beschreibe den Schaden: ")
    category = categorize_report(description)

    print("Erkannte Kategorie:", category)
