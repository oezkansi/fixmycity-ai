"""SQLite database: schema, connection helper and reference data.

All tables required by the brief: users, reports, uploaded images, AI analysis,
departments, status history, administrative feedback, open data sources and
dataset metadata (plus sessions and admin notes).
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "fixmycity.db"

CATEGORIES = {
    "road_damage": "Road Damage / Potholes",
    "streetlight": "Broken Streetlights",
    "waste_dumping": "Illegal Waste Dumping",
    "graffiti": "Graffiti",
    "fallen_tree": "Fallen Trees",
    "broken_glass": "Broken Glass",
    "traffic_sign": "Damaged Traffic Signs",
    "other": "Other",
}

STATUSES = ["New", "Under Review", "Assigned", "In Progress", "Resolved"]

# Provisional mapping taken from the project brief (Part 9).
# These are NOT verified official Pforzheim responsibilities.
PROVISIONAL_DEPARTMENTS = {
    "road_damage": "Road Maintenance",
    "streetlight": "Responsible Lighting Operator",
    "waste_dumping": "Waste Management / Public Order",
    "graffiti": "Public Space Maintenance",
    "fallen_tree": "Green Space Management",
    "broken_glass": "Municipal Cleaning Service",
    "traffic_sign": "Traffic / Road Maintenance",
    "other": "To be determined by administration",
}

# The six approved platforms (brief, Part 2.1). URLs stay empty until the team
# provides the exact official links. Nothing is imported from them yet.
APPROVED_PLATFORMS = [
    ("Statistik BW", "Population, housing, demographics, social and regional statistics"),
    ("Daten BW", "Downloadable datasets from Baden-Württemberg, incl. geographical data"),
    ("MobiData BW", "Mobility, transport, traffic and public transport data"),
    ("GovData", "Open government datasets"),
    ("Zensus 2022", "Population, households, buildings, apartments, population distribution"),
    ("Pforzheim Analyseumgebung", "Local statistics and analyses for Pforzheim"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('citizen','admin')),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    notes TEXT,
    provisional INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    created_at TEXT NOT NULL,
    user_id INTEGER REFERENCES users(id),
    edit_token TEXT,
    description TEXT,
    citizen_category TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    location_text TEXT,
    category TEXT NOT NULL,
    severity TEXT,
    priority_score INTEGER,
    priority_level TEXT,
    priority_breakdown TEXT,
    priority_overridden INTEGER NOT NULL DEFAULT 0,
    escalated INTEGER NOT NULL DEFAULT 0,
    human_review_required INTEGER NOT NULL DEFAULT 0,
    department_id INTEGER REFERENCES departments(id),
    assigned_to TEXT,
    status TEXT NOT NULL DEFAULT 'New',
    confirmed INTEGER NOT NULL DEFAULT 0,
    is_demo INTEGER NOT NULL DEFAULT 0,
    merged_into INTEGER REFERENCES reports(id),
    duplicate_candidates TEXT
);
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER REFERENCES reports(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER REFERENCES reports(id) ON DELETE CASCADE,
    mode TEXT NOT NULL CHECK (mode IN ('live','simulated','demo_record')),
    model TEXT,
    image_recognizable INTEGER,
    detected_incident TEXT,
    category TEXT,
    description TEXT,
    potential_risks TEXT,
    severity TEXT,
    urgency TEXT,
    public_exposure TEXT,
    exposure_reasoning TEXT,
    safety_critical INTEGER,
    recommended_actions TEXT,
    confidence REAL,
    raw_response TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_by INTEGER REFERENCES users(id),
    note TEXT,
    changed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    field TEXT NOT NULL,
    original_value TEXT,
    corrected_value TEXT,
    admin_id INTEGER REFERENCES users(id),
    comment TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    admin_id INTEGER REFERENCES users(id),
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS open_data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT UNIQUE NOT NULL,
    purpose TEXT,
    url TEXT,
    status TEXT NOT NULL DEFAULT 'link_not_provided'
);
CREATE TABLE IF NOT EXISTS dataset_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES open_data_sources(id),
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT,
    retrieved_at TEXT,
    relevant_fields TEXT,
    usage TEXT
);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_confirmed ON reports(confirmed);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(exist_ok=True)
    with get_db() as db:
        db.executescript(SCHEMA)
        for cat, name in PROVISIONAL_DEPARTMENTS.items():
            db.execute(
                "INSERT OR IGNORE INTO departments (category, name, notes, provisional, updated_at) "
                "VALUES (?,?,?,1,?)",
                (cat, name, "Provisional suggestion from the project brief. Not a verified official responsibility.", now_iso()),
            )
        for platform, purpose in APPROVED_PLATFORMS:
            db.execute(
                "INSERT OR IGNORE INTO open_data_sources (platform, purpose, url, status) VALUES (?,?,NULL,'link_not_provided')",
                (platform, purpose),
            )


def row_to_dict(row):
    return dict(row) if row is not None else None


def loads(value, default=None):
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default
