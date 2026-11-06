# geo_utils.py
import requests

def get_district_and_road_type(latitude, longitude):
    """
    Fragt die OpenStreetMap Overpass API ab, um basierend auf GPS-Koordinaten
    automatisch den Bezirk und den Hauptstraßen-Status zu ermitteln.
    """
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    # Sucht nach Straßen und Verwaltungsbezirken im Umkreis von 25 Metern
    overpass_query = f"""
    [out:json];
    (
      way(around:25,{latitude},{longitude})["highway"];
      way(around:25,{latitude},{longitude})["boundary"="administrative"];
    );
    out body;
    """
    
    try:
        response = requests.post(overpass_url, data=overpass_query, timeout=5)
        if response.status_code == 200:
            data = response.json()
            elements = data.get("elements", [])
            
            is_main_road = False
            district = "Bezirk_Mitte"  # Standard-Fallback
            
            # Typische Hauptstraßen-Klassifizierungen in OpenStreetMap
            main_road_types = ["primary", "secondary", "trunk", "motorway", "tertiary"]
            
            for el in elements:
                tags = el.get("tags", {})
                highway = tags.get("highway")
                
                if highway in main_road_types:
                    is_main_road = True
                    
                # Versuche einen Namen oder Stadtteil/Bezirk zu finden
                place_name = tags.get("name") or tags.get("suburb") or tags.get("neighbourhood")
                if place_name and not highway:
                    district = f"Bezirk_{place_name.replace(' ', '_')}"
                    
            return district, is_main_road
            
    except Exception as e:
        print(f"GIS-Fehler bei API-Abfrage: {e}")
        
    # Fallback, falls die API nicht erreichbar ist
    return "Bezirk_Mitte", False