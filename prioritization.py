# prioritization.py
from weather_utils import get_weather_factor

def calculate_advanced_priority(sub_data, days_waiting, is_main_road, citizen_urgency, location_str=""):
    """
    Berechnet den erweiterten Prioritätsscore für einen Schadensbericht.
    Berücksichtigt Basis-Schweregrad, Hauptstraßen-Status, Bürger-Dringlichkeit,
    Wartezeit (Tage) und den aktuellen Wetterfaktor. Liefert ein 
    transparentes Breakdown für den Berechnungs-Report zurück.
    """
    # Basis-Schweregrad (Skala 1-5, Fallback auf 3)
    base_severity = sub_data.get("base_severity", 3) if isinstance(sub_data, dict) else 3
    
    # Wetterfaktor abrufen (z.B. Erhöhung bei Frost oder starkem Regen für Straßenschäden)
    weather_multiplier = get_weather_factor(location_str) if location_str else 1.0
    
    # Gewichtungsfaktoren und Boni
    road_bonus = 1.5 if is_main_road else 1.0
    urgency_weight = float(citizen_urgency) * 1.2
    waiting_weight = float(days_waiting) * 0.5
    
    # Textliche Einordnung des Wetterfaktors für den Transparenz-Report
    weather_note = "Normaler Einfluss"
    if weather_multiplier > 1.2:
        weather_note = "Erhöht durch akute Wetterbedingungen (Regen/Frost)"
    elif weather_multiplier < 1.0:
        weather_note = "Reduziert durch günstige Wetterbedingungen"

    # Berechnung des finalen Prioritätsscores
    raw_score = (base_severity * 10.0 * road_bonus) + urgency_weight + waiting_weight
    final_score = raw_score * weather_multiplier
    
    # Transparenz-Breakdown für die Nachvollziehbarkeit im Bericht
    breakdown = {
        "base_severity": base_severity,
        "road_bonus": road_bonus,
        "urgency_weight": round(urgency_weight, 2),
        "waiting_weight": round(waiting_weight, 2),
        "weather_multiplier": weather_multiplier,
        "weather_note": weather_note,
        "final_score": round(final_score, 2)
    }
    
    return {
        "score": round(final_score, 2),
        "breakdown": breakdown
    }