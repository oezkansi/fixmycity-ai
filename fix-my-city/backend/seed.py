"""10 fictional demonstration incidents in Pforzheim.

These are NOT real municipal reports. Every record has is_demo = 1, its
analysis mode is 'demo_record', and the UI labels it as demonstration data.
Coordinates are fictional points spread around the city centre.
"""
import json
from datetime import datetime, timedelta, timezone

from database import now_iso
from engine import compute_priority, department_for

CENTER = (48.8915, 8.7040)

DEMO = [
    # category, incident, description, risks, severity, urgency, exposure, safety_critical, dlat, dlon, hours_ago, status
    ("road_damage", "Pothole", "Fictional demo record: pothole in a road lane.", ["Vehicle damage", "Cyclist fall hazard"], "high", "high", "high", False, 0.0021, -0.0034, 5, "New"),
    ("streetlight", "Broken streetlight", "Fictional demo record: streetlight not working.", ["Poor visibility at night"], "medium", "medium", "medium", False, -0.0040, 0.0051, 30, "Under Review"),
    ("waste_dumping", "Illegally dumped waste", "Fictional demo record: bags of waste left beside a path.", ["Hygiene risk", "Attracts pests"], "medium", "medium", "medium", False, 0.0065, 0.0072, 52, "Assigned"),
    ("graffiti", "Graffiti", "Fictional demo record: graffiti on a wall.", ["Visual damage to public space"], "low", "low", "medium", False, -0.0012, -0.0081, 76, "In Progress"),
    ("fallen_tree", "Fallen tree", "Fictional demo record: tree blocking a footpath.", ["Blocked path", "Injury risk"], "critical", "immediate", "medium", True, 0.0098, -0.0120, 3, "New"),
    ("broken_glass", "Broken glass", "Fictional demo record: glass shards on a sidewalk.", ["Cut injuries", "Risk for children and pets"], "high", "high", "high", False, -0.0071, -0.0025, 12, "New"),
    ("traffic_sign", "Damaged traffic sign", "Fictional demo record: bent traffic sign.", ["Unclear traffic rules"], "medium", "medium", "high", False, 0.0033, 0.0115, 100, "Resolved"),
    ("road_damage", "Cracked road surface", "Fictional demo record: cracks across a road.", ["Surface may deteriorate"], "low", "low", "medium", False, -0.0102, 0.0094, 150, "Resolved"),
    ("waste_dumping", "Dumped furniture", "Fictional demo record: old sofa left on a sidewalk.", ["Obstructs pedestrians"], "medium", "medium", "high", False, 0.0050, -0.0062, 20, "Under Review"),
    ("other", "Damaged bench", "Fictional demo record: broken public bench.", ["Minor injury risk"], "low", "low", "low", False, -0.0030, 0.0018, 200, "Assigned"),
]


def seed_demo(db):
    if db.execute("SELECT COUNT(*) FROM reports WHERE is_demo = 1").fetchone()[0]:
        return
    now = datetime.now(timezone.utc)
    for i, (cat, inc, desc, risks, sev, urg, exp, crit, dlat, dlon, hours, status) in enumerate(DEMO, start=1):
        created = (now - timedelta(hours=hours)).isoformat(timespec="seconds")
        lat, lon = CENTER[0] + dlat, CENTER[1] + dlon
        analysis = {"image_recognizable": True, "severity": sev, "urgency": urg, "public_exposure": exp,
                    "potential_risks": risks, "safety_critical": crit,
                    "exposure_reasoning": "Fictional demonstration value."}
        pr = compute_priority(analysis, lat, lon, db)
        dept = department_for(cat, db)
        cur = db.execute(
            """INSERT INTO reports (created_at, description, latitude, longitude, location_text, category, severity,
               priority_score, priority_level, priority_breakdown, escalated, human_review_required, department_id,
               status, confirmed, is_demo) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,1)""",
            (created, desc, lat, lon, "Fictional demo location", cat, sev, pr["score"], pr["level"], json.dumps(pr),
             int(pr["escalated"]), int(pr["human_review_required"]), dept["id"] if dept else None, status))
        rid = cur.lastrowid
        db.execute("UPDATE reports SET code = ? WHERE id = ?", (f"DEMO-{i:03d}", rid))
        db.execute(
            """INSERT INTO ai_analysis (report_id, mode, model, image_recognizable, detected_incident, category, description,
               potential_risks, severity, urgency, public_exposure, exposure_reasoning, safety_critical, recommended_actions,
               confidence, raw_response, created_at) VALUES (?, 'demo_record', NULL, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)""",
            (rid, inc, cat, desc, json.dumps(risks), sev, urg, exp, "Fictional demonstration value.", int(crit),
             json.dumps(["Review the report"]), "Demonstration record: no AI analysis was performed.", created))
        db.execute("INSERT INTO status_history (report_id, old_status, new_status, note, changed_at) VALUES (?,?,?,?,?)",
                   (rid, None, status, "Demonstration record created", now_iso()))
