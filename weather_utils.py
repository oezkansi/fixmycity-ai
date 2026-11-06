# weather_utils.py
import requests

def get_weather_factor(location_str):
    """
    Ruft über die Open-Meteo API aktuelle Wetterdaten (Temperatur, Niederschlag) 
    für die gegebenen Koordinaten ab und berechnet einen Verschlechterungsfaktor.
    """
    # Standard-Koordinaten (Fallback, falls kein GPS-String vorliegt)
    lat, lon = 48.8906, 8.7027 
    
    try:
        # Prüfen, ob der Standort als "lat, lon" übergeben wurde
        if "," in location_str:
            parts = location_str.split(",")
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
    except Exception:
        pass

    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            current = data.get("current", {})
            precipitation = current.get("precipitation", 0.0) # in mm
            temperature = current.get("temperature_2m", 15.0) # in °C
            
            # Wetterfaktor-Logik:
            # - Regen/Niederschlag beschleunigt Wasserschäden / Schlaglöcher
            # - Frost (< 0°C) sprengt Risse auf (Frostaufbruch)
            factor = 1.0
            if precipitation > 0.5:
                factor += 0.4
            if temperature < 0:
                factor += 0.6
                
            return factor
            
    except Exception as e:
        print(f"Fehler beim Abrufen der Wetterdaten: {e}")
        
    return 1.0  # Standard-Faktor bei API-Ausfall