# database.py
import sqlite3
from datetime import datetime

DB_NAME = "fixmycity.db"

def init_db():
    """
    Initialisiert die SQLite-Datenbank und erstellt die Tabelle 'reports',
    falls sie noch nicht existiert.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            location TEXT,
            district TEXT,
            is_main_road INTEGER,
            category TEXT,
            subcategory TEXT,
            description TEXT,
            score REAL,
            status TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def save_report(report_data, status="Aktiv"):
    """
    Speichert einen verarbeiteten Schadensbericht sicher in der Datenbank.
    """
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cat_data = report_data.get("category_data", {})
    prio_data = report_data.get("priority_data", {})
    
    cursor.execute('''
        INSERT INTO reports (
            timestamp, location, district, is_main_road, 
            category, subcategory, description, score, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        report_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        report_data.get("location"),
        report_data.get("district"),
        1 if report_data.get("is_main_road") else 0,
        cat_data.get("category"),
        cat_data.get("subcategory"),
        report_data.get("description"),
        prio_data.get("score", 0.0),
        status
    ))
    
    conn.commit()
    conn.close()

def check_for_duplicates(location, category, subcategory):
    """
    Prüft, ob in der Datenbank bereits ein aktiver Schaden 
    am selben Standort mit derselben Kategorie existiert.
    """
    init_db()
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, timestamp, description FROM reports 
            WHERE location = ? AND category = ? AND subcategory = ? AND status = 'Aktiv'
        """, (location, category, subcategory))
        
        duplicates = cursor.fetchall()
        conn.close()
        
        if duplicates:
            return True, duplicates[0][0]
    except Exception:
        pass
        
    return False, None

def get_all_reports():
    """
    Lädt alle gespeicherten Berichte aus der Datenbank, 
    sortiert nach Prioritätsscore (absteigend).
    """
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, timestamp, location, district, is_main_road, 
               category, subcategory, description, score, status 
        FROM reports 
        ORDER BY score DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    reports = []
    for r in rows:
        reports.append({
            "id": r[0],
            "timestamp": r[1],
            "location": r[2],
            "district": r[3],
            "is_main_road": bool(r[4]),
            "category": r[5],
            "subcategory": r[6],
            "description": r[7],
            "score": r[8],
            "status": r[9]
        })
    return reports