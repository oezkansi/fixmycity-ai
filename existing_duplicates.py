from math import radians, sin, cos, sqrt, atan2
from difflib import SequenceMatcher
import re

import imagehash


MAX_DISTANCE_METERS = 100


def calculate_distance(lat1, lon1, lat2, lon2):
    radius = 6371000

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )

    return radius * 2 * atan2(sqrt(a), sqrt(1 - a))


def normalize_description(description):
    text = str(description or "").lower()

    replacements = {
        "loch in straße": "schlagloch",
        "loch in strasse": "schlagloch",
        "schlagloch auf der fahrbahn": "schlagloch",
        "beschädigte fahrbahn": "fahrbahnschaden",
        "beschaedigte fahrbahn": "fahrbahnschaden",
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

    if any(value is None for value in [lat1, lon1, lat2, lon2]):
        return None

    distance = calculate_distance(
        float(lat1),
        float(lon1),
        float(lat2),
        float(lon2)
    )

    if distance > MAX_DISTANCE_METERS:
        return None

    text_similarity = description_similarity(
        report1.get("description"),
        report2.get("description")
    )

    hash1 = report1.get("image_hash")
    hash2 = report2.get("image_hash")

    image_similarity = None
    confirmed = False

    if hash1 and hash2:
        try:
            hash_distance = (
                imagehash.hex_to_hash(hash1)
                - imagehash.hex_to_hash(hash2)
            )

            image_similarity = max(
                0.0,
                1.0 - hash_distance / 64.0
            )

            confirmed = (
                hash_distance <= 6
                or (
                    hash_distance <= 12
                    and text_similarity >= 0.65
                )
            )

        except (ValueError, TypeError):
            image_similarity = None

        possible_duplicate = (
    confirmed
    or text_similarity >= 0.80
)

    if not possible_duplicate:
        return None

    return {
        "distance": round(distance, 1),
        "text_similarity": round(text_similarity * 100, 1),
        "image_similarity": (
            round(image_similarity * 100, 1)
            if image_similarity is not None
            else None
        ),
        "confirmed": confirmed
    }


def find_existing_duplicates(reports):
    """
    Vergleicht alle gespeicherten Meldungen und
    gruppiert mögliche Duplikate.
    """

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
            parent[root2] = root1

    comparisons = {}

    for i in range(len(reports)):
        for j in range(i + 1, len(reports)):
            report1 = reports[i]
            report2 = reports[j]

            result = compare_reports(report1, report2)

            if result is not None:
                union(report1["id"], report2["id"])

                key = tuple(sorted([
                    report1["id"],
                    report2["id"]
                ]))

                comparisons[key] = result

    groups = {}

    for report in reports:
        root = find(report["id"])
        groups.setdefault(root, []).append(report)

    duplicate_groups = []

    for group in groups.values():
        if len(group) < 2:
            continue

        group.sort(key=lambda report: report["id"])

        group_ids = {
            report["id"]
            for report in group
        }

        matches = []

        for (id1, id2), result in comparisons.items():
            if id1 in group_ids and id2 in group_ids:
                matches.append({
                    "report_1": id1,
                    "report_2": id2,
                    **result
                })

        duplicate_groups.append({
            "original": group[0],
            "reports": group,
            "matches": matches,
            "confirmed": all(
                match["confirmed"]
                for match in matches
            )
        })

    return duplicate_groups