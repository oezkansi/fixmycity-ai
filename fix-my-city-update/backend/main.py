"""FIX MY CITY - FastAPI backend.

Run from the project folder:
    uvicorn main:app --app-dir backend --reload
Then open http://127.0.0.1:8000
"""
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

import ai_vision  # noqa: E402
from database import (CATEGORIES, STATUSES, UPLOAD_DIR, get_db, init_db, loads, now_iso,  # noqa: E402
                      row_to_dict)
from engine import compute_priority, department_for, find_duplicates, level_for  # noqa: E402
from seed import seed_demo  # noqa: E402

MAX_UPLOAD = int(os.getenv("MAX_UPLOAD_MB", "8")) * 1024 * 1024
MIME_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

app = FastAPI(title="FIX MY CITY API", version="1.0")


# --------------------------------------------------------------------------- auth
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    salt, digest = stored.split("$", 1)
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return hmac.compare_digest(test, digest)


def current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    with get_db() as db:
        row = db.execute(
            "SELECT u.id, u.email, u.name, u.role, s.expires_at FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
            (token,)).fetchone()
        if not row or row["expires_at"] < now_iso():
            return None
        return {"id": row["id"], "email": row["email"], "name": row["name"], "role": row["role"]}


def require_user(user=Depends(current_user)):
    if not user:
        raise HTTPException(401, "Please log in.")
    return user


def require_admin(user=Depends(current_user)):
    if not user:
        raise HTTPException(401, "Please log in as an administrator.")
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator access required.")
    return user


@app.on_event("startup")
def startup():
    init_db()
    with get_db() as db:
        email = os.getenv("ADMIN_EMAIL", "admin@fixmycity.local").strip().lower()
        password = os.getenv("ADMIN_PASSWORD", "change-me-now")
        if not db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            db.execute("INSERT INTO users (email, name, password_hash, role, created_at) VALUES (?,?,?,?,?)",
                       (email, "City Administrator", hash_password(password), "admin", now_iso()))
        if os.getenv("SEED_DEMO_DATA", "1") == "1":
            seed_demo(db)


class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=8, max_length=200)
    name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: str
    password: str


def _new_session(db, user_id):
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(timespec="seconds")
    db.execute("INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
               (token, user_id, now_iso(), expires))
    return token


@app.post("/api/auth/register")
def register(body: RegisterIn):
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Please enter a valid email address.")
    with get_db() as db:
        if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(409, "An account with this email already exists.")
        cur = db.execute("INSERT INTO users (email, name, password_hash, role, created_at) VALUES (?,?,?, 'citizen', ?)",
                         (email, body.name.strip(), hash_password(body.password), now_iso()))
        token = _new_session(db, cur.lastrowid)
    return {"token": token, "user": {"email": email, "name": body.name.strip(), "role": "citizen"}}


@app.post("/api/auth/login")
def login(body: LoginIn):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE email = ?", (body.email.strip().lower(),)).fetchone()
        if not row or not verify_password(body.password, row["password_hash"]):
            raise HTTPException(401, "Email or password is incorrect.")
        token = _new_session(db, row["id"])
    return {"token": token, "user": {"email": row["email"], "name": row["name"], "role": row["role"]}}


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        with get_db() as db:
            db.execute("DELETE FROM sessions WHERE token = ?", (authorization[7:],))
    return {"ok": True}


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return {"user": user}


# --------------------------------------------------------------------------- public
@app.get("/api/config")
def config():
    return {"ai_mode": ai_vision.ai_mode(), "model": ai_vision.model_name() if ai_vision.ai_mode() == "live" else None,
            "max_upload_mb": MAX_UPLOAD // (1024 * 1024), "categories": CATEGORIES, "statuses": STATUSES}


@app.get("/api/public/stats")
def public_stats():
    with get_db() as db:
        q = lambda sql: db.execute(sql).fetchone()[0]  # noqa: E731
        base = "FROM reports WHERE confirmed = 1 AND merged_into IS NULL"
        return {
            "total": q(f"SELECT COUNT(*) {base}"),
            "resolved": q(f"SELECT COUNT(*) {base} AND status = 'Resolved'"),
            "open": q(f"SELECT COUNT(*) {base} AND status != 'Resolved'"),
            "high_priority": q(f"SELECT COUNT(*) {base} AND status != 'Resolved' AND priority_level IN ('High','Critical')"),
            "demo_records": q(f"SELECT COUNT(*) {base} AND is_demo = 1"),
        }


def _image_url(db, report_id):
    img = db.execute("SELECT filename FROM images WHERE report_id = ? ORDER BY id DESC LIMIT 1", (report_id,)).fetchone()
    return f"/uploads/{img['filename']}" if img else None


@app.get("/api/public/map")
def public_map():
    """Only non-personal fields are exposed publicly."""
    with get_db() as db:
        rows = db.execute(
            "SELECT id, code, created_at, latitude, longitude, location_text, category, priority_score, priority_level, "
            "status, is_demo FROM reports WHERE confirmed = 1 AND merged_into IS NULL ORDER BY created_at DESC").fetchall()
        return [dict(r, image_url=_image_url(db, r["id"]), category_label=CATEGORIES.get(r["category"])) for r in rows]


@app.get("/api/public/track/{code}")
def track(code: str):
    with get_db() as db:
        r = db.execute("SELECT code, created_at, category, status, priority_level, merged_into FROM reports "
                       "WHERE code = ? AND confirmed = 1", (code.strip().upper(),)).fetchone()
        if not r:
            raise HTTPException(404, "No report found with this code.")
        hist = db.execute("SELECT new_status, changed_at FROM status_history h JOIN reports r ON r.id = h.report_id "
                          "WHERE r.code = ? ORDER BY h.id", (r["code"],)).fetchall()
        return dict(r, category_label=CATEGORIES.get(r["category"]), history=[dict(h) for h in hist])


@app.get("/api/sources")
def sources():
    with get_db() as db:
        plats = [dict(r) for r in db.execute("SELECT * FROM open_data_sources ORDER BY id")]
        datasets = [dict(r) for r in db.execute("SELECT * FROM dataset_metadata ORDER BY id")]
    return {"platforms": plats, "datasets": datasets}


@app.get("/uploads/{filename}")
def get_upload(filename: str):
    path = (UPLOAD_DIR / filename).resolve()
    if path.parent != UPLOAD_DIR.resolve() or not path.is_file():
        raise HTTPException(404, "Image not found.")
    return FileResponse(path)


# --------------------------------------------------------------------------- reports
def _sniff(data: bytes):
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _analysis_out(row):
    if not row:
        return None
    d = dict(row)
    d["potential_risks"] = loads(d["potential_risks"], [])
    d["recommended_actions"] = loads(d["recommended_actions"], [])
    d["image_recognizable"] = bool(d["image_recognizable"])
    d["safety_critical"] = bool(d["safety_critical"])
    d.pop("raw_response", None)
    return d


def _report_out(db, r, admin=False):
    d = dict(r)
    d["priority_breakdown"] = loads(d["priority_breakdown"], {})
    d["duplicate_candidates"] = loads(d["duplicate_candidates"], [])
    d["category_label"] = CATEGORIES.get(d["category"])
    d["image_url"] = _image_url(db, r["id"])
    dept = db.execute("SELECT id, name, provisional FROM departments WHERE id = ?", (r["department_id"],)).fetchone()
    d["department"] = dict(dept) if dept else None
    d["analysis"] = _analysis_out(db.execute("SELECT * FROM ai_analysis WHERE report_id = ? ORDER BY id DESC LIMIT 1",
                                             (r["id"],)).fetchone())
    d.pop("edit_token", None)
    if not admin:
        d.pop("user_id", None)
    return d


@app.post("/api/reports")
async def create_report(
    image: UploadFile = File(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    description: str = Form(""),
    location_text: str = Form(""),
    citizen_category: str = Form(""),
    language: str = Form("en"),
    user=Depends(current_user),
):
    """Step 1: upload + real AI analysis. Creates an unconfirmed draft."""
    data = await image.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, f"The image is larger than {MAX_UPLOAD // (1024 * 1024)} MB.")
    mime = _sniff(data)
    if mime not in MIME_TYPES:
        raise HTTPException(415, "Please upload a JPG, JPEG, PNG or WEBP image.")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(400, "Invalid location.")
    citizen_category = citizen_category if citizen_category in CATEGORIES else None
    description = description.strip()[:1000]

    try:
        analysis = ai_vision.analyze_image(data, mime, description, citizen_category, language)
    except ai_vision.AIError as exc:
        raise HTTPException(502, f"Image recognition failed: {exc} Please try again.")

    filename = secrets.token_hex(16) + MIME_TYPES[mime]
    (UPLOAD_DIR / filename).write_bytes(data)

    with get_db() as db:
        category = analysis["category"] if analysis["image_recognizable"] else (citizen_category or "other")
        priority = compute_priority(analysis, latitude, longitude, db)
        dept = department_for(category, db)
        edit_token = secrets.token_urlsafe(24)
        cur = db.execute(
            """INSERT INTO reports (created_at, user_id, edit_token, description, citizen_category, latitude, longitude,
               location_text, category, severity, priority_score, priority_level, priority_breakdown, escalated,
               human_review_required, department_id, status, confirmed, is_demo)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'New', 0, 0)""",
            (now_iso(), user["id"] if user else None, edit_token, description, citizen_category, latitude, longitude,
             location_text.strip()[:200], category, analysis.get("severity"), priority["score"], priority["level"],
             json.dumps(priority), int(priority["escalated"]), int(priority["human_review_required"]),
             dept["id"] if dept else None))
        rid = cur.lastrowid
        db.execute("INSERT INTO images (report_id, filename, mime_type, size_bytes, created_at) VALUES (?,?,?,?,?)",
                   (rid, filename, mime, len(data), now_iso()))
        db.execute(
            """INSERT INTO ai_analysis (report_id, mode, model, image_recognizable, detected_incident, category, description,
               potential_risks, severity, urgency, public_exposure, exposure_reasoning, safety_critical,
               recommended_actions, confidence, raw_response, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, analysis["mode"], analysis["model"], int(analysis["image_recognizable"]), analysis["detected_incident"],
             analysis["category"], analysis["description"], json.dumps(analysis["potential_risks"]), analysis["severity"],
             analysis["urgency"], analysis["public_exposure"], analysis["exposure_reasoning"],
             int(analysis["safety_critical"]), json.dumps(analysis["recommended_actions"]), analysis["confidence"],
             analysis["raw_response"], now_iso()))
        row = db.execute("SELECT * FROM reports WHERE id = ?", (rid,)).fetchone()
        out = _report_out(db, row)
        out["duplicate_candidates"] = find_duplicates(row, db)
    out["edit_token"] = edit_token
    return out


class ConfirmIn(BaseModel):
    edit_token: str


@app.post("/api/reports/{report_id}/confirm")
def confirm_report(report_id: int, body: ConfirmIn):
    """Step 2: the citizen confirms the analyzed report. Only now is it public."""
    with get_db() as db:
        r = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if not r or not r["edit_token"] or not hmac.compare_digest(r["edit_token"], body.edit_token):
            raise HTTPException(404, "Report not found.")
        if r["confirmed"]:
            return {"code": r["code"]}
        code = f"FMC-{report_id:05d}"
        dups = find_duplicates(r, db)
        db.execute("UPDATE reports SET confirmed = 1, code = ?, edit_token = NULL, duplicate_candidates = ? WHERE id = ?",
                   (code, json.dumps(dups), report_id))
        db.execute("INSERT INTO status_history (report_id, old_status, new_status, note, changed_at) VALUES (?,?,?,?,?)",
                   (report_id, None, "New", "Report submitted by citizen", now_iso()))
    return {"code": code, "possible_duplicates": len(dups)}


@app.get("/api/reports/mine")
def my_reports(user=Depends(require_user)):
    with get_db() as db:
        rows = db.execute("SELECT * FROM reports WHERE user_id = ? AND confirmed = 1 ORDER BY created_at DESC",
                          (user["id"],)).fetchall()
        return [_report_out(db, r) for r in rows]


# --------------------------------------------------------------------------- admin
@app.get("/api/admin/stats")
def admin_stats(admin=Depends(require_admin)):
    with get_db() as db:
        base = "FROM reports WHERE confirmed = 1 AND merged_into IS NULL"
        q = lambda sql: db.execute(sql).fetchone()[0]  # noqa: E731
        by_status = {s: q(f"SELECT COUNT(*) {base} AND status = '{s}'") for s in STATUSES}
        by_cat = {CATEGORIES[k]: c for k, c in db.execute(f"SELECT category, COUNT(*) {base} GROUP BY category")}
        by_level = {lvl or "Not scored": c for lvl, c in db.execute(f"SELECT priority_level, COUNT(*) {base} GROUP BY priority_level")}
        return {
            "total": q(f"SELECT COUNT(*) {base}"), "new": by_status["New"],
            "open": q(f"SELECT COUNT(*) {base} AND status != 'Resolved'"), "in_progress": by_status["In Progress"],
            "resolved": by_status["Resolved"],
            "critical": q(f"SELECT COUNT(*) {base} AND priority_level = 'Critical' AND status != 'Resolved'"),
            "by_status": by_status, "by_category": by_cat, "by_level": by_level,
            "demo_records": q(f"SELECT COUNT(*) {base} AND is_demo = 1"),
        }


SORTS = {
    "priority": "COALESCE(priority_score, -1) DESC, created_at DESC",
    "newest": "created_at DESC",
    "oldest": "created_at ASC",
}


@app.get("/api/admin/reports")
def admin_reports(q: str = "", status: str = "", category: str = "", level: str = "", sort: str = "priority",
                  include_merged: bool = False, admin=Depends(require_admin)):
    sql = "SELECT * FROM reports WHERE confirmed = 1"
    args = []
    if not include_merged:
        sql += " AND merged_into IS NULL"
    if status in STATUSES:
        sql += " AND status = ?"; args.append(status)
    if category in CATEGORIES:
        sql += " AND category = ?"; args.append(category)
    if level in ("Low", "Medium", "High", "Critical"):
        sql += " AND priority_level = ?"; args.append(level)
    if q.strip():
        sql += " AND (code LIKE ? OR description LIKE ? OR location_text LIKE ? OR assigned_to LIKE ?)"
        args += [f"%{q.strip()}%"] * 4
    sql += " ORDER BY " + SORTS.get(sort, SORTS["priority"]) + " LIMIT 500"
    with get_db() as db:
        return [_report_out(db, r, admin=True) for r in db.execute(sql, args).fetchall()]


@app.get("/api/admin/reports/{report_id}")
def admin_report(report_id: int, admin=Depends(require_admin)):
    with get_db() as db:
        r = db.execute("SELECT * FROM reports WHERE id = ? AND confirmed = 1", (report_id,)).fetchone()
        if not r:
            raise HTTPException(404, "Report not found.")
        out = _report_out(db, r, admin=True)
        out["duplicate_candidates"] = find_duplicates(r, db)
        out["history"] = [dict(h) for h in db.execute(
            "SELECT h.*, u.name AS changed_by_name FROM status_history h LEFT JOIN users u ON u.id = h.changed_by "
            "WHERE report_id = ? ORDER BY h.id", (report_id,))]
        out["feedback"] = [dict(f) for f in db.execute(
            "SELECT f.*, u.name AS admin_name FROM admin_feedback f LEFT JOIN users u ON u.id = f.admin_id "
            "WHERE report_id = ? ORDER BY f.id", (report_id,))]
        out["notes"] = [dict(n) for n in db.execute(
            "SELECT n.*, u.name AS admin_name FROM admin_notes n LEFT JOIN users u ON u.id = n.admin_id "
            "WHERE report_id = ? ORDER BY n.id", (report_id,))]
        out["merged_children"] = [dict(c) for c in db.execute(
            "SELECT id, code FROM reports WHERE merged_into = ?", (report_id,))]
        return out


class ReportUpdate(BaseModel):
    category: Optional[str] = None
    priority_level: Optional[str] = None
    department_id: Optional[int] = None
    assigned_to: Optional[str] = Field(None, max_length=120)
    status: Optional[str] = None
    comment: Optional[str] = Field(None, max_length=1000)


LEVEL_SCORE = {"Low": 20, "Medium": 45, "High": 75, "Critical": 95}


@app.patch("/api/admin/reports/{report_id}")
def update_report(report_id: int, body: ReportUpdate, admin=Depends(require_admin)):
    with get_db() as db:
        r = db.execute("SELECT * FROM reports WHERE id = ? AND confirmed = 1", (report_id,)).fetchone()
        if not r:
            raise HTTPException(404, "Report not found.")
        ts, comment = now_iso(), (body.comment or "").strip() or None

        def feedback(field, old, new):
            db.execute("INSERT INTO admin_feedback (report_id, field, original_value, corrected_value, admin_id, comment, "
                       "created_at) VALUES (?,?,?,?,?,?,?)", (report_id, field, old, new, admin["id"], comment, ts))

        if body.category is not None and body.category != r["category"]:
            if body.category not in CATEGORIES:
                raise HTTPException(400, "Unknown category.")
            feedback("category", r["category"], body.category)
            db.execute("UPDATE reports SET category = ? WHERE id = ?", (body.category, report_id))
        if body.priority_level is not None and body.priority_level != r["priority_level"]:
            if body.priority_level not in LEVEL_SCORE:
                raise HTTPException(400, "Unknown priority level.")
            feedback("priority_level", r["priority_level"], body.priority_level)
            score = r["priority_score"]
            if level_for(score) != body.priority_level:
                score = LEVEL_SCORE[body.priority_level]
            db.execute("UPDATE reports SET priority_level = ?, priority_score = ?, priority_overridden = 1 WHERE id = ?",
                       (body.priority_level, score, report_id))
        if body.department_id is not None and body.department_id != r["department_id"]:
            new = db.execute("SELECT name FROM departments WHERE id = ?", (body.department_id,)).fetchone()
            if not new:
                raise HTTPException(400, "Unknown department.")
            old = db.execute("SELECT name FROM departments WHERE id = ?", (r["department_id"],)).fetchone()
            feedback("department", old["name"] if old else None, new["name"])
            db.execute("UPDATE reports SET department_id = ? WHERE id = ?", (body.department_id, report_id))
        if body.assigned_to is not None and body.assigned_to.strip() != (r["assigned_to"] or ""):
            db.execute("UPDATE reports SET assigned_to = ? WHERE id = ?", (body.assigned_to.strip() or None, report_id))
        if body.status is not None and body.status != r["status"]:
            if body.status not in STATUSES:
                raise HTTPException(400, "Unknown status.")
            db.execute("UPDATE reports SET status = ? WHERE id = ?", (body.status, report_id))
            db.execute("INSERT INTO status_history (report_id, old_status, new_status, changed_by, note, changed_at) "
                       "VALUES (?,?,?,?,?,?)", (report_id, r["status"], body.status, admin["id"], comment, ts))
    return admin_report(report_id, admin)


class NoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


@app.post("/api/admin/reports/{report_id}/notes")
def add_note(report_id: int, body: NoteIn, admin=Depends(require_admin)):
    with get_db() as db:
        if not db.execute("SELECT 1 FROM reports WHERE id = ?", (report_id,)).fetchone():
            raise HTTPException(404, "Report not found.")
        db.execute("INSERT INTO admin_notes (report_id, admin_id, note, created_at) VALUES (?,?,?,?)",
                   (report_id, admin["id"], body.note.strip(), now_iso()))
    return admin_report(report_id, admin)


class MergeIn(BaseModel):
    into_id: int


@app.post("/api/admin/reports/{report_id}/merge")
def merge(report_id: int, body: MergeIn, admin=Depends(require_admin)):
    """Manual merge, chosen by an administrator. Never automatic."""
    if report_id == body.into_id:
        raise HTTPException(400, "A report cannot be merged into itself.")
    with get_db() as db:
        src = db.execute("SELECT * FROM reports WHERE id = ? AND confirmed = 1", (report_id,)).fetchone()
        dst = db.execute("SELECT * FROM reports WHERE id = ? AND confirmed = 1 AND merged_into IS NULL", (body.into_id,)).fetchone()
        if not src or not dst:
            raise HTTPException(404, "Report not found.")
        db.execute("UPDATE reports SET merged_into = ? WHERE id = ?", (body.into_id, report_id))
        db.execute("INSERT INTO admin_notes (report_id, admin_id, note, created_at) VALUES (?,?,?,?)",
                   (body.into_id, admin["id"], f"Report {src['code']} merged into this report as a duplicate.", now_iso()))
        db.execute("INSERT INTO admin_notes (report_id, admin_id, note, created_at) VALUES (?,?,?,?)",
                   (report_id, admin["id"], f"Merged into {dst['code']} as a duplicate.", now_iso()))
    return admin_report(body.into_id, admin)


@app.get("/api/admin/departments")
def departments(admin=Depends(require_admin)):
    with get_db() as db:
        return [dict(r, category_label=CATEGORIES.get(r["category"])) for r in
                db.execute("SELECT * FROM departments ORDER BY id")]


class DepartmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    notes: Optional[str] = Field(None, max_length=500)
    provisional: bool = True


@app.put("/api/admin/departments/{dept_id}")
def update_department(dept_id: int, body: DepartmentIn, admin=Depends(require_admin)):
    with get_db() as db:
        if not db.execute("SELECT 1 FROM departments WHERE id = ?", (dept_id,)).fetchone():
            raise HTTPException(404, "Department not found.")
        db.execute("UPDATE departments SET name = ?, notes = ?, provisional = ?, updated_at = ? WHERE id = ?",
                   (body.name.strip(), body.notes, int(body.provisional), now_iso(), dept_id))
    return departments(admin)


@app.get("/api/admin/feedback")
def all_feedback(admin=Depends(require_admin)):
    """Correction records for future model evaluation. The model does not retrain automatically."""
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT f.*, r.code, u.name AS admin_name FROM admin_feedback f JOIN reports r ON r.id = f.report_id "
            "LEFT JOIN users u ON u.id = f.admin_id ORDER BY f.id DESC")]


# Frontend (must be mounted last)
app.mount("/", StaticFiles(directory=BASE_DIR / "frontend", html=True), name="frontend")
