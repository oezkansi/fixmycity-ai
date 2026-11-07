"""Decision support: transparent priority score, rule-based department
suggestion, open-data location check and duplicate detection.

Everything here is deterministic. No AI is called in this module.
"""
import math
from datetime import datetime, timedelta

# Formula from the project brief (Part 7.1). Each factor is 0-100.
WEIGHTS = {"severity": 0.40, "location_sensitivity": 0.25, "public_exposure": 0.20, "urgency": 0.15}

# How the AI's categorical estimates are converted to 0-100 values.
SEVERITY_POINTS = {"low": 25, "medium": 50, "high": 75, "critical": 100}
EXPOSURE_POINTS = {"low": 25, "medium": 55, "high": 85}
URGENCY_POINTS = {"low": 20, "medium": 50, "high": 80, "immediate": 100}

FACTOR_LABELS = {
    "severity": "Severity",
    "location_sensitivity": "Location sensitivity",
    "public_exposure": "Public exposure",
    "urgency": "Urgency",
}


def level_for(score):
    if score is None:
        return None
    if score <= 30:
        return "Low"
    if score <= 60:
        return "Medium"
    if score <= 85:
        return "High"
    return "Critical"


def location_sensitivity(lat, lon, db):
    """Return (value 0-100 or None, explanation).

    A value is only produced from a verified dataset of sensitive locations
    (schools, kindergartens, hospitals ...) registered in dataset_metadata from
    one of the six approved platforms. None is registered yet, so the factor
    is reported as unavailable instead of being guessed.
    """
    registered = db.execute("SELECT COUNT(*) FROM dataset_metadata").fetchone()[0]
    if registered == 0:
        return None, "Data unavailable: no approved dataset with verified sensitive-location coordinates has been provided."
    # When the team provides such a dataset, implement the proximity check here.
    return None, "Data unavailable: registered datasets do not contain sensitive-location coordinates yet."


def compute_priority(analysis, lat, lon, db):
    """Compute the priority score with a full, explainable breakdown.

    Unknown factors are excluded and the remaining weights are renormalized,
    which is shown in the breakdown. Safety-critical findings escalate the
    report: a low score can never hide a safety warning.
    """
    if not analysis or not analysis.get("image_recognizable") or analysis.get("severity") not in SEVERITY_POINTS:
        return {
            "score": None, "level": None, "factors": [], "reasons": [
                "The image could not be reliably analyzed, so no priority score was calculated."],
            "renormalized": False, "escalated": False, "human_review_required": True,
            "escalation_reason": "Unclear image: manual assessment required.",
        }

    loc_value, loc_note = location_sensitivity(lat, lon, db)
    factors = [
        {"key": "severity", "value": SEVERITY_POINTS[analysis["severity"]], "source": "ai_estimate",
         "note": f"AI-estimated severity: {analysis['severity']}"},
        {"key": "location_sensitivity", "value": loc_value, "source": "open_data" if loc_value is not None else "unavailable",
         "note": loc_note},
        {"key": "public_exposure", "value": EXPOSURE_POINTS.get(analysis.get("public_exposure")), "source": "ai_estimate",
         "note": "AI estimate from the visible scene, not a measured number of people. "
                 + (analysis.get("exposure_reasoning") or "")},
        {"key": "urgency", "value": URGENCY_POINTS.get(analysis.get("urgency")), "source": "ai_estimate",
         "note": f"AI-estimated urgency: {analysis.get('urgency') or 'unknown'}"},
    ]
    known = [f for f in factors if f["value"] is not None]
    weight_sum = sum(WEIGHTS[f["key"]] for f in known)
    score = 0.0
    for f in factors:
        f["label"] = FACTOR_LABELS[f["key"]]
        f["weight"] = WEIGHTS[f["key"]]
        if f["value"] is None:
            f["effective_weight"] = 0
            f["points"] = None
            if f["source"] != "unavailable":
                f["source"] = "unavailable"
        else:
            f["effective_weight"] = round(WEIGHTS[f["key"]] / weight_sum, 3)
            f["points"] = round(f["value"] * f["effective_weight"], 1)
            score += f["points"]
    score = int(round(score))
    renormalized = weight_sum < 0.999

    reasons = list(analysis.get("potential_risks") or [])[:4]
    if analysis.get("public_exposure") == "high":
        reasons.append("High estimated public exposure")
    if analysis.get("urgency") in ("high", "immediate"):
        reasons.append("Requires prompt review")
    if loc_value is None:
        reasons.append("Location sensitivity could not be assessed (data unavailable)")

    escalated, reason = False, None
    if analysis.get("safety_critical") or analysis["severity"] == "critical":
        escalated = True
        reason = "Safety-critical finding: escalated to Critical and requires human review."
        score = max(score, 86)

    level = level_for(score)
    return {
        "score": score, "level": level, "factors": factors, "reasons": reasons,
        "renormalized": renormalized, "escalated": escalated,
        "human_review_required": escalated or level == "Critical",
        "escalation_reason": reason,
    }


def department_for(category, db):
    row = db.execute("SELECT * FROM departments WHERE category = ?", (category,)).fetchone()
    return dict(row) if row else None


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def find_duplicates(report, db, radius_m=75, days=14):
    """Possible duplicates: same category, within radius_m metres and `days` days.
    Image similarity is not used in this version. Matches are only suggestions:
    nothing is merged automatically."""
    created = datetime.fromisoformat(report["created_at"])
    rows = db.execute(
        "SELECT id, code, created_at, latitude, longitude, category FROM reports "
        "WHERE confirmed = 1 AND merged_into IS NULL AND id != ? AND category = ?",
        (report["id"], report["category"]),
    ).fetchall()
    matches = []
    for r in rows:
        dist = haversine_m(report["latitude"], report["longitude"], r["latitude"], r["longitude"])
        delta = abs(datetime.fromisoformat(r["created_at"]) - created)
        if dist <= radius_m and delta <= timedelta(days=days):
            matches.append({"id": r["id"], "code": r["code"], "distance_m": round(dist),
                            "hours_apart": round(delta.total_seconds() / 3600, 1)})
    return sorted(matches, key=lambda m: m["distance_m"])
