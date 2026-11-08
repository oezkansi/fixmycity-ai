import sqlite3
import re
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2
from difflib import SequenceMatcher

from PIL import Image
import imagehash


DB_PATH = Path(__file__).resolve().parent / "fixmycity.db"

MAX_DISTANCE_METERS = 100
MAX_IMAGE_HASH_DISTANCE = 12


def calculate_distance(lat1, lon1, lat2, lon2):
    radius = 6371000

    dlat = radians(float(lat2) - float(lat1))
    dlon = radians(float(lon2) - float(lon1))

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(float(lat1)))
        * cos(radians(float(lat2)))
        * sin(dlon / 2) ** 2
    )

    return radius * 2 * atan2(
        sqrt(a),
        sqrt(max(0, 1 - a))
    )


def get_image_hash(image_path):
    with Image.open(image_path) as image:
        return str(imagehash.phash(image.convert("RGB")))


def normalize_description(description):
    text = str(description or "").lower()

    replacements = {
        "loch in straße": "schlagloch",
        "loch in strasse": "schlagloch",
        "schlagloch auf der fahrbahn": "schlagloch",
        "schlagloch auf der straße": "schlagloch",
        "schlagloch auf der strasse": "schlagloch",
        "straßenschaden": "schlagloch",
        "strassenschaden": "schlagloch",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def description_similarity(text1, text2):
    text1 = normalize_description(text1)
    text2 = normalize_description(text2)

    if not text1 or not text2:
        return 0.0

    return SequenceMatcher(None, text1, text2).ratio()


def compare_reports(report1, report2):
    lat1 = report1.get("damage_latitude")
    lon1 = report1.get("damage_longitude")
    lat2 = report2.get("damage_latitude")
    lon2 = report2.get("damage_longitude")

    if None in (lat1, lon1, lat2, lon2):
        return None

    distance = calculate_distance(lat1, lon1, lat2, lon2)

    if distance > MAX_DISTANCE_METERS:
        return None

    text_similarity = description_similarity(
        report1.get("description"),
        report2.get("description")
    )

    hash1 = report1.get("image_hash")
    hash2 = report2.get("image_hash")

    image_similarity = None
    hash_distance = None

    if hash1 and hash2:
        try:
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)

            if h1.hash.shape == h2.hash.shape:
                hash_distance = h1 - h2

                image_similarity = max(
                    0.0,
                    1.0 - hash_distance / h1.hash.size
                )
        except (ValueError, TypeError):
            pass

    image_confirmed = (
        hash_distance is not None
        and hash_distance <= 6
    )

    image_supported = (
        hash_distance is not None
        and hash_distance <= MAX_IMAGE_HASH_DISTANCE
        and text_similarity >= 0.65
    )

    possible_duplicate = (
        image_confirmed
        or image_supported
        or (
            hash_distance is None
            and text_similarity >= 0.85
        )
    )

    if not possible_duplicate:
        return None

    return {
        "report_1": report1["id"],
        "report_2": report2["id"],
        "distance": round(distance, 1),
        "text_similarity": round(text_similarity * 100, 1),
        "image_similarity": (
            round(image_similarity * 100, 1)
            if image_similarity is not None
            else None
        ),
        "confirmed": image_confirmed,
        "image_supported": image_supported,
        "reason": (
            "Sehr ähnlicher Bild-Fingerabdruck"
            if image_confirmed
            else (
                "Bild, Standort und Beschreibung ähnlich"
                if image_supported
                else "Standort und Beschreibung ähnlich"
            )
        )
    }


def check_duplicate(
    image_path,
    description,
    damage_latitude,
    damage_longitude
):
    if not DB_PATH.exists():
        return None

    new_report = {
        "id": -1,
        "description": description,
        "damage_latitude": damage_latitude,
        "damage_longitude": damage_longitude,
        "image_hash": get_image_hash(image_path)
    }

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(reports)")
        }

        if "image_hash" not in columns:
            raise RuntimeError(
                "Die Datenbank muss zuerst aktualisiert werden."
            )

        reports = [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM reports
                ORDER BY id ASC
                """
            ).fetchall()
        ]

    matches = []

    for report in reports:
        match = compare_reports(new_report, report)

        if match is None:
            continue

        matches.append((report, match))

    if not matches:
        return None

    matches.sort(
        key=lambda item: (
            not item[1]["confirmed"],
            not item[1]["image_supported"],
            item[1]["distance"],
            item[0]["id"]
        )
    )

    report, match = matches[0]

    case_id = report.get("duplicate_of") or report["id"]

    return {
        "id": report["id"],
        "case_id": case_id,
        "description": report["description"],
        "status": report["status"],
        "distance_meters": match["distance"],
        "image_similarity": match["image_similarity"],
        "description_similarity": match["text_similarity"],
        "confirmed": match["confirmed"],
        "image_supported": match["image_supported"],
        "reason": match["reason"]
    }


def find_existing_duplicates(reports):
    """
    Gruppiert vorhandene Meldungen.

    Bildgestützte Übereinstimmungen werden gesondert
    von bloßen Verdachtsfällen gekennzeichnet.
    """

    reports = sorted(
        reports,
        key=lambda report: int(report["id"])
    )

    report_by_id = {
        report["id"]: report
        for report in reports
    }

    parent = {
        report["id"]: report["id"]
        for report in reports
    }

    def find(report_id):
        while parent[report_id] != report_id:
            parent[report_id] = parent[parent[report_id]]
            report_id = parent[report_id]

        return report_id

    def union(id1, id2):
        root1 = find(id1)
        root2 = find(id2)

        if root1 != root2:
            parent[max(root1, root2)] = min(root1, root2)

    matches = []

    for index, report1 in enumerate(reports):
        for report2 in reports[index + 1:]:
            match = compare_reports(report1, report2)

            if match:
                matches.append(match)
                union(report1["id"], report2["id"])

    for report in reports:
        duplicate_of = report.get("duplicate_of")

        if duplicate_of is not None:
            duplicate_of = int(duplicate_of)

            if duplicate_of in report_by_id:
                union(report["id"], duplicate_of)

    grouped = {}

    for report in reports:
        root = find(report["id"])
        grouped.setdefault(root, []).append(report)

    result = []

    for group_reports in grouped.values():
        group_reports.sort(key=lambda report: report["id"])

        group_ids = {
            report["id"]
            for report in group_reports
        }

        group_matches = [
            match
            for match in matches
            if (
                match["report_1"] in group_ids
                and match["report_2"] in group_ids
            )
        ]

        confirmed = (
            len(group_reports) == 1
            or all(
                report.get("duplicate_of") is not None
                for report in group_reports[1:]
            )
        )

        if len(group_reports) > 1:
            confirmed = confirmed or (
                len(group_matches) >= len(group_reports) - 1
                and all(
                    match["confirmed"]
                    for match in group_matches
                )
            )

        result.append({
            "original": group_reports[0],
            "reports": group_reports,
            "matches": group_matches,
            "confirmed": confirmed,
            "duplicate_count": len(group_reports) - 1
        })

    result.sort(
        key=lambda group: group["original"]["id"]
    )

    return result