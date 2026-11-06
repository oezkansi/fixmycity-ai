# database.py
import sqlite3
from datetime import datetime

DB_NAME = "fixmycity.db"

def init_db():
    """Initialisiert die SQLite-Datenbank und erstellt die Tabelle falls nicht vorhanden."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT,
            description TEXT,
            district TEXT,
            is_main_road BOOLEAN,
            citizen_urgency INTEGER,
            category TEXT,
            subcategory TEXT,
            department TEXT,
            priority TEXT,
            score REAL,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_report_to_db(result):
    """Speichert einen verarbeiteten Schadensbericht in der Datenbank."""
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cat_data = result.get("category_data", {})
    pri_data = result.get("priority_data", {})
    
    cursor.execute('''
        INSERT INTO reports (
            location, description, district, is_main_road, citizen_urgency,
            category, subcategory, department, priority, score, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        result.get("location"),
        result.get("description"),
        result.get("district"),
        1 if result.get("is_main_road") else 0,
        result.get("citizen_urgency", 3),
        cat_data.get("category"),
        cat_data.get("subcategory"),
        cat_data.get("department"),
        pri_data.get("priority"),
        pri_data.get("score"),
        "Aktiv"
    ))
    
    conn.commit()
    conn.close()

def get_all_reports_with_dynamic_days():
    """
    Lädt alle Reports aus der Datenbank und berechnet 
    die verstrichenen Tage (days_waiting) dynamisch zum aktuellen Zeitpunkt.
    """
    init_db()
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Erlaubt Zugriff per Spaltenname
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM reports ORDER BY score DESC")
    rows = cursor.fetchall()
    conn.close()
    
    reports = []
    now = datetime.now()
    
    for row in rows:
        report = dict(row)
        # Erstellungsdatum parsen und Tage seitdem berechnen
        created_at = datetime.strptime(report["created_at"], "%Y-%m-%d %H:%M:%S")
        days_waiting = (now - created_at).days
        report["days_waiting"] = max(0, days_waiting)
        reports.append(report)
        
    return reports