# capacity_manager.py
from database import get_all_reports_with_dynamic_days

# Konfigurierbare Maximallimits für Baustellen pro Bezirk
DISTRICT_LIMITS = {
    "Bezirk_Mitte": 4,
    "Bezirk_Nord": 3,
    "Bezirk_Sued": 3,
    "Bezirk_West": 3,
    "Bezirk_Ost": 3
}

MAX_MAIN_ROAD_SITES = 2  # Max. gleichzeitige Baustellen auf Hauptstraßen

def process_capacity_queues():
    """
    Lädt alle Reports aus der Datenbank, sortiert sie nach Priorität (Score) 
    und teilt sie in aktive Baustellen und die Warteliste auf.
    """
    reports = get_all_reports_with_dynamic_days()
    
    district_counts = {}
    main_road_count = 0
    
    active_queue = []
    waiting_queue = []
    
    for item in reports:
        district = item.get("district", "Bezirk_Mitte")
        is_main = bool(item.get("is_main_road", False))
        
        limit = DISTRICT_LIMITS.get(district, 3)
        
        district_full = district_counts.get(district, 0) >= limit
        main_full = is_main and (main_road_count >= MAX_MAIN_ROAD_SITES)
        
        if district_full or main_full:
            item["status"] = "Wartend (Kapazitätslimit)"
            waiting_queue.append(item)
        else:
            item["status"] = "Aktiv / In Bearbeitung"
            active_queue.append(item)
            district_counts[district] = district_counts.get(district, 0) + 1
            if is_main:
                main_road_count += 1
                
    return active_queue, waiting_queue