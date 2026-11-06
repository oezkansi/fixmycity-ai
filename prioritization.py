def calculate_advanced_priority(sub_data, days_waiting=0, is_main_road=False, citizen_urgency=3, weather_factor=1.0):
    """
    Berechnet die Priorität basierend auf Sicherheitsrisiko, Verschlechterungsrate,
    Wartezeit, Infrastruktur (Hauptstraße) und Bürgerbewertung.
    """
    safety = sub_data.get("safety", 30)                # Wert von 0 bis 100
    deterioration = sub_data.get("deterioration_rate", 0.5) # Wie schnell es schlimmer wird
    weather_sens = sub_data.get("weather_sensitivity", 0.0)  # Wetteranfälligkeit
    requires_review = sub_data.get("review", False)
    
    # 1. Dynamischer Alterungs- und Wetterfaktor (Prognose-Komponente)
    # Je länger unbehandelt und je höher die Verschlechterungsrate, desto mehr steigt der Score
    aging_impact = (deterioration + (weather_sens * weather_factor)) * days_waiting
    
    # 2. Infrastruktur-Bonus (Hauptstraßen werden höher gewichtet wegen Verkehrsaufkommen)
    road_bonus = 20 if is_main_road else 0
    
    # 3. Gesamt-Score-Berechnung
    # - Sicherheit macht 40% des Basiswerts aus
    # - Die zeitliche Verschlechterung (aging_impact) treibt den Score nach oben
    # - Bürger-Dringlichkeit (1-5) fließt gewichtet ein
    base_score = (safety * 0.4) + (citizen_urgency * 5) + road_bonus
    total_score = base_score + (aging_impact * 2.5)
    
    # 4. Schwellenwerte für die Zuweisung
    if requires_review or total_score >= 75:
        priority = "P1 - Critical"
    elif total_score >= 45:
        priority = "P2 - High"
    else:
        priority = "P3 - Normal"
        
    return {
        "score": round(total_score, 1),
        "priority": priority,
        "aging_impact": round(aging_impact, 1),
        "requires_review": requires_review
    }