# prognosis.py
from categorization import CATEGORIES_DB
from weather_utils import get_weather_factor

def calculate_prognosis(category, subcategory, days_elapsed, location_str=""):
    """
    Berechnet die voraussichtliche Verschlechterung des Schadens über die Zeit,
    unter Berücksichtigung der Wettersensitivität und aktueller Wetterdaten.
    """
    # Standard-Werte holen
    sub_data = {}
    if category in CATEGORIES_DB and subcategory in CATEGORIES_DB[category]["subcategories"]:
        sub_data = CATEGORIES_DB[category]["subcategories"][subcategory]
        
    deterioration_rate = sub_data.get("deterioration_rate", 1.0) # z.B. 1 bis 5
    weather_sensitivity = sub_data.get("weather_sensitivity", "mittel")
    
    # Wetterfaktor ermitteln (nur wenn Wettersensitivität gegeben ist)
    weather_multiplier = 1.0
    if weather_sensitivity in ["hoch", "mittel"]:
        weather_multiplier = get_weather_factor(location_str)
        
    # Prognose-Formel: Basis-Verschlechterung * Tage * Wetter-Multiplikator
    projected_damage_growth = days_elapsed * (deterioration_rate * 0.5) * weather_multiplier
    
    # Zustand bestimmen
    if projected_damage_growth < 5:
        status = "Stabil"
    elif projected_damage_growth < 15:
        status = "Fortschreitend (Verschlechterung sichtbar)"
    else:
        status = "Kritisch (Akute Gefahr von Folgeschäden)"
        
    return {
        "projected_growth": round(projected_damage_growth, 2),
        "weather_multiplier": weather_multiplier,
        "status": status
    }