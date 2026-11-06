# worker.py
import time
import sqlite3
from datetime import datetime

DB_NAME = "fixmycity.db"

def background_task_loop():
    """
    Ein Hintergrund-Skript, das periodisch (z.B. alle 5 Minuten) läuft,
    die Datenbank prüft und kritische Statusänderungen vornimmt.
    """
    print("🤖 FixMyCity Hintergrund-Worker gestartet...")
    
    while True:
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            # Beispiel: Prüfen, ob Tickets länger als 7 Tage unbehandelt sind
            # und automatisch den Status oder die Dringlichkeit anpassen
            cursor.execute("""
                SELECT id, created_at, score FROM reports 
                WHERE status = 'Aktiv'
            """)
            rows = cursor.fetchall()
            
            now = datetime.now()
            for row in rows:
                report_id, created_at_str, score = row
                created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
                days_waiting = (now - created_at).days
                
                # Wenn ein Ticket z.B. nach 10 Tagen noch nicht gelöst ist, Score erhöhen
                if days_waiting >= 10:
                    new_score = score + 5.0
                    cursor.execute("""
                        UPDATE reports SET score = ? WHERE id = ?
                    """, (new_score, report_id))
            
            conn.commit()
            conn.close()
            print(f"[{now.strftime('%H:%M:%S')}] Hintergrund-Check abgeschlossen. Alle aktiven Tickets geprüft.")
            
        except Exception as e:
            print(f"Fehler im Hintergrund-Worker: {e}")
            
        # 5 Minuten (300 Sekunden) warten bis zum nächsten Intervall
        time.sleep(300)

if __name__ == "__main__":
    background_task_loop()