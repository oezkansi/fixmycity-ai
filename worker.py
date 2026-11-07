# worker.py
import time
import sqlite3
from datetime import datetime
import os

DB_NAME = "fixmycity.db"

def background_task_loop():
    """
    Hintergrund-Skript zur periodischen Prüfung der Datenbank.
    Prüft, ob die Tabelle existiert und aktualisiert ggf. überfällige Tickets.
    """
    print("🤖 FixMyCity Hintergrund-Worker gestartet...")
    
    while True:
        try:
            if not os.path.exists(DB_NAME):
                print("⏳ Keine Datenbank gefunden. Warte auf erste Schadensmeldung...")
                time.sleep(30)
                continue

            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            # Prüfen, ob die Tabelle 'reports' überhaupt existiert
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='reports';
            """)
            table_exists = cursor.fetchone()
            
            if not table_exists:
                print("⏳ Tabelle 'reports' existiert noch nicht. Warte auf erste Meldung...")
                conn.close()
                time.sleep(30)
                continue

            # Aktive Tickets abrufen
            cursor.execute("""
                SELECT id, created_at, score FROM reports 
                WHERE status = 'Aktiv'
            """)
            rows = cursor.fetchall()
            
            now = datetime.now()
            for row in rows:
                report_id, created_at_str, score = row
                try:
                    created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
                
                days_waiting = (now - created_at).days
                
                # Score bei langer Wartezeit erhöhen
                if days_waiting >= 10:
                    new_score = score + 5.0
                    cursor.execute("""
                        UPDATE reports SET score = ? WHERE id = ?
                    """, (new_score, report_id))
            
            conn.commit()
            conn.close()
            print(f"[{now.strftime('%H:%M:%S')}] Hintergrund-Check abgeschlossen. Aktive Tickets geprüft.")
            
        except Exception as e:
            print(f"Fehler im Hintergrund-Worker: {e}")
            
        # 5 Minuten warten
        time.sleep(300)

if __name__ == "__main__":
    background_task_loop()