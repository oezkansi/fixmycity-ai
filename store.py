"""Kleine SQLite-Ablage für die Meldungen (nur für die Oberfläche).

Alles landet im Ordner ui_data/ (Datenbank + Fotos).
"""
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from io import BytesIO
from PIL import Image
import imagehash

from ui_theme import parse_location

DATA_DIR = Path(__file__).parent / "ui_data"
DB_PATH = DATA_DIR / "reports.db"
IMG_DIR = DATA_DIR / "images"

STATUSES = ["Gesendet", "In Bearbeitung", "Durchgeführt"]
DEPARTMENTS = [
    "Nicht zugewiesen",
    "Tiefbauamt",
    "Stadtreinigung / Entsorgung",
    "Grünflächenamt",
    "Straßenverkehrsamt",
    "Beleuchtung (Stadtwerke)",
]


def _connect():
    DATA_DIR.mkdir(exist_ok=True)
    IMG_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            location TEXT,
            description TEXT,
            citizen_urgency INTEGER,
            priority TEXT,
            score INTEGER,
            danger INTEGER,
            impact INTEGER,
            urgency INTEGER,
            acute_hazard INTEGER,
            analysis TEXT,
            image_file TEXT,
            status TEXT,
            department TEXT,
            session_id TEXT
        )
        """
    )
    # Ältere Datenbanken ohne Spalte session_id ergänzen
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(reports)")]
    if "session_id" not in columns:
        conn.execute("ALTER TABLE reports ADD COLUMN session_id TEXT")

    for name, column_type in [
        ("damage_latitude", "REAL"),
        ("damage_longitude", "REAL"),
        ("image_hash", "TEXT"),
    ]:
        if name not in columns:
            conn.execute(
                f"ALTER TABLE reports ADD COLUMN {name} {column_type}"
            )

    return conn


def add_report(result, image_bytes, suffix, citizen_urgency, session_id):
    """Speichert eine gültige Meldung und gibt ihre Nummer zurück."""
    factors = result["risk_factors"]
    prio = result["priority"]

    _, latitude, longitude = parse_location(result["location"])

    with Image.open(BytesIO(image_bytes)) as image:
        photo_hash = str(imagehash.phash(image))

    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            """
            INSERT INTO reports (
                created_at, location, description, citizen_urgency,
                priority, score, danger, impact, urgency, acute_hazard,
                analysis, image_file, status, department, session_id,
                damage_latitude, damage_longitude, image_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().strftime("%d.%m.%Y %H:%M"),
                result["location"],
                result["description"],
                citizen_urgency,
                prio["priority"],
                prio["score"],
                factors["danger"],
                factors["impact"],
                factors["urgency"],
                1 if factors["acute_hazard"] else 0,
                result.get("image_analysis") or "",
                "",
                "Gesendet",
                "Nicht zugewiesen",
                session_id,
                latitude,
                longitude,
                photo_hash,
            ),
        )
        report_id = cur.lastrowid

        image_file = f"{report_id}{suffix}"
        (IMG_DIR / image_file).write_bytes(image_bytes)
        conn.execute(
            "UPDATE reports SET image_file = ? WHERE id = ?",
            (image_file, report_id),
        )
    return report_id


def list_reports(session_id=None):
    """Alle Meldungen (Verwaltung: wichtigste zuerst) oder nur die einer Sitzung."""
    with closing(_connect()) as conn:
        if session_id is None:
            rows = conn.execute(
                "SELECT * FROM reports ORDER BY score DESC, id DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reports WHERE session_id = ? ORDER BY id DESC",
                (session_id,),
            ).fetchall()
    return [dict(row) for row in rows]


def update_report(report_id, status, department):
    with closing(_connect()) as conn, conn:
        conn.execute(
            "UPDATE reports SET status = ?, department = ? WHERE id = ?",
            (status, department, report_id),
        )


def set_status(report_id, status):
    with closing(_connect()) as conn, conn:
        conn.execute("UPDATE reports SET status = ? WHERE id = ?", (status, report_id))


def set_department(report_id, department):
    with closing(_connect()) as conn, conn:
        conn.execute("UPDATE reports SET department = ? WHERE id = ?", (department, report_id))


def image_path(image_file):
    return IMG_DIR / image_file
