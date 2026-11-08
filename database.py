import sqlite3
import json
from pathlib import Path
from datetime import datetime


DB_PATH = Path(__file__).resolve().parent / "fixmycity.db"


def init_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                location TEXT NOT NULL,
                citizen_urgency INTEGER NOT NULL,
                validation TEXT,
                responsibility TEXT,
                image_analysis TEXT,
                risk_factors TEXT,
                priority TEXT,
                status TEXT NOT NULL DEFAULT 'Offen',
                created_at TEXT NOT NULL,
                citizen_latitude REAL,
                citizen_longitude REAL,
                gps_accuracy REAL,
                damage_latitude REAL,
                damage_longitude REAL,
                distance_to_damage REAL,
                image_hash TEXT,
                duplicate_of INTEGER
            )
        """)

        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(reports)"
            )
        }

        new_columns = {
            "citizen_latitude": "REAL",
            "citizen_longitude": "REAL",
            "gps_accuracy": "REAL",
            "damage_latitude": "REAL",
            "damage_longitude": "REAL",
            "distance_to_damage": "REAL",
            "image_hash": "TEXT",
            "duplicate_of": "INTEGER"
        }

        for column, data_type in new_columns.items():
            if column not in columns:
                conn.execute(
                    f"ALTER TABLE reports "
                    f"ADD COLUMN {column} {data_type}"
                )


def save_report(
    description,
    location,
    citizen_urgency,
    result,
    citizen_latitude=None,
    citizen_longitude=None,
    gps_accuracy=None,
    damage_latitude=None,
    damage_longitude=None,
    distance_to_damage=None,
    image_hash=None,
    duplicate_of=None
):
    validation = result.get("validation") or {}

    if validation.get("status") != "VALID":
        raise ValueError(
            "Ungültige Meldungen werden nicht gespeichert."
        )

    init_database()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("""
            INSERT INTO reports (
                description,
                location,
                citizen_urgency,
                validation,
                responsibility,
                image_analysis,
                risk_factors,
                priority,
                status,
                created_at,
                citizen_latitude,
                citizen_longitude,
                gps_accuracy,
                damage_latitude,
                damage_longitude,
                distance_to_damage,
                image_hash,
                duplicate_of
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            description,
            location,
            citizen_urgency,
            json.dumps(
                validation,
                ensure_ascii=False
            ),
            json.dumps(
                result.get("responsibility"),
                ensure_ascii=False
            ),
            json.dumps(
                result.get("image_analysis"),
                ensure_ascii=False
            ),
            json.dumps(
                result.get("risk_factors"),
                ensure_ascii=False
            ),
            json.dumps(
                result.get("priority"),
                ensure_ascii=False
            ),
            "Offen",
            datetime.now().isoformat(
                timespec="seconds"
            ),
            citizen_latitude,
            citizen_longitude,
            gps_accuracy,
            damage_latitude,
            damage_longitude,
            distance_to_damage,
            image_hash,
            duplicate_of
        ))

        return cursor.lastrowid


def load_reports():
    init_database()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            "SELECT * FROM reports ORDER BY id DESC"
        ).fetchall()

        return [dict(row) for row in rows]


def update_image_hashes(report_ids, image_hash):
    """
    Ordnet ein vom Administrator bestätigtes Foto
    den ausgewählten vorhandenen Meldungen zu.
    """

    init_database()

    ids = sorted({
        int(report_id)
        for report_id in report_ids
    })

    if not ids:
        return 0

    placeholders = ",".join("?" for _ in ids)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            f"""
            UPDATE reports
            SET image_hash = ?
            WHERE id IN ({placeholders})
            """,
            [image_hash, *ids]
        )

        return cursor.rowcount


def update_report_duplicate_of(report_id, original_id):
    init_database()

    if int(report_id) == int(original_id):
        raise ValueError(
            "Eine Meldung kann kein Duplikat von sich selbst sein."
        )

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE reports
            SET duplicate_of = ?
            WHERE id = ?
            """,
            (int(original_id), int(report_id))
        )

# ==================================================
# VERWALTUNGSFREIGABEN
# ==================================================

def init_approvals():
    """
    Erstellt die Tabelle für Verwaltungsentscheidungen.
    Bereits vorhandene Daten bleiben erhalten.
    """

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL UNIQUE,
                decision TEXT NOT NULL,
                assigned_department TEXT,
                comment TEXT,
                decided_at TEXT NOT NULL,
                FOREIGN KEY (report_id) REFERENCES reports(id)
            )
        """)


def save_approval(
    report_id,
    decision,
    assigned_department=None,
    comment=""
):
    """
    Speichert eine Verwaltungsentscheidung.

    Mögliche Entscheidungen:
    APPROVED
    REJECTED
    REASSIGNED
    """

    init_database()
    init_approvals()

    allowed_decisions = {
        "APPROVED",
        "REJECTED",
        "REASSIGNED"
    }

    if decision not in allowed_decisions:
        raise ValueError("Ungültige Entscheidung.")

    report_id = int(report_id)

    with sqlite3.connect(DB_PATH) as conn:

        report = conn.execute(
            "SELECT id FROM reports WHERE id = ?",
            (report_id,)
        ).fetchone()

        if report is None:
            raise ValueError(
                f"Schadensmeldung #{report_id} existiert nicht."
            )

        conn.execute("""
            INSERT INTO approvals (
                report_id,
                decision,
                assigned_department,
                comment,
                decided_at
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(report_id)
            DO UPDATE SET
                decision = excluded.decision,
                assigned_department = excluded.assigned_department,
                comment = excluded.comment,
                decided_at = excluded.decided_at
        """, (
            report_id,
            decision,
            assigned_department,
            comment,
            datetime.now().isoformat(
                timespec="seconds"
            )
        ))

        if decision in {"APPROVED", "REASSIGNED"}:
            new_status = "Genehmigt"
        else:
            new_status = "Abgelehnt"

        conn.execute("""
            UPDATE reports
            SET status = ?
            WHERE id = ?
        """, (
            new_status,
            report_id
        ))

    return True


def load_approvals():
    """
    Lädt alle gespeicherten Verwaltungsentscheidungen.
    """

    init_approvals()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute("""
            SELECT *
            FROM approvals
            ORDER BY decided_at DESC
        """).fetchall()

        return [dict(row) for row in rows]


def get_approval(report_id):
    """
    Gibt die Verwaltungsentscheidung
    für eine bestimmte Meldung zurück.
    """

    init_approvals()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        row = conn.execute("""
            SELECT *
            FROM approvals
            WHERE report_id = ?
        """, (int(report_id),)).fetchone()

        return dict(row) if row else None


def update_report_status(report_id, new_status):
    """
    Aktualisiert den Bearbeitungsstatus
    einer Schadensmeldung.
    """

    allowed_statuses = {
        "Offen",
        "Genehmigt",
        "Abgelehnt",
        "In Bearbeitung",
        "Erledigt"
    }

    if new_status not in allowed_statuses:
        raise ValueError("Ungültiger Bearbeitungsstatus.")

    init_database()

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.execute("""
            UPDATE reports
            SET status = ?
            WHERE id = ?
        """, (
            new_status,
            int(report_id)
        ))

        if cursor.rowcount == 0:
            raise ValueError(
                "Schadensmeldung nicht gefunden."
            )

    return True