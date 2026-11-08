from datetime import datetime

from task_assignment import recommend_task


# Simulierte maximale Anzahl gleichzeitig aktiver Aufgaben
DEFAULT_CAPACITY = 10

# Sicherheitsregel: Kritische Fälle immer eskalieren
CRITICAL_PRIORITY = 1


def priority_rank(priority):
    text = str(priority or "").upper()

    if text.startswith("P1"):
        return 1
    if text.startswith("P2"):
        return 2
    if text.startswith("P3"):
        return 3
    if text.startswith("P4"):
        return 4

    return 5


def waiting_days(created_at):
    if not created_at:
        return 0

    text = str(created_at).strip()

    for date_format in (
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            created = datetime.strptime(text, date_format)
            return max(0, (datetime.now() - created).days)
        except ValueError:
            continue

    try:
        created = datetime.fromisoformat(text)
        return max(0, (datetime.now() - created).days)
    except (ValueError, TypeError):
        return 0


def calculate_queue_score(case):
    priority = priority_rank(case.get("priority"))

    base_scores = {
        1: 1000,
        2: 700,
        3: 400,
        4: 100,
        5: 0,
    }

    days = waiting_days(case.get("created_at"))

    # Längere Wartezeiten erhöhen die Reihenfolge.
    score = base_scores[priority] + days * 15

    return score


def build_smart_queue(
    damage_cases,
    capacity_per_department=None,
    active_tasks=None
):
    capacity_per_department = capacity_per_department or {}
    active_tasks = active_tasks or {}

    departments = {}

    for case in damage_cases:

        if case.get("status") == "Erledigt, Durchgeführt":
            continue

        report = case.get("original_report") or case

        recommendation = recommend_task(report)

        department_data = recommendation.get("department") or {}

        if isinstance(department_data, dict):
            department_name = (
                department_data.get("name")
                or department_data.get("department")
                or "Manuelle Prüfung"
            )
        else:
            department_name = str(department_data)

        department_name = department_name or "Manuelle Prüfung"

        priority = case.get("priority")

        if not priority:
            priority_report = case.get("priority_report") or report
            priority = priority_report.get("priority")

        item = {
            "case_id": case.get("id"),
            "description": case.get("description"),
            "priority": priority,
            "status": case.get("status", "Offen"),
            "created_at": case.get("created_at"),
            "department": department_name,
            "recommendation": recommendation,
        }

        item["queue_score"] = calculate_queue_score(item)
        item["waiting_days"] = waiting_days(item["created_at"])

        departments.setdefault(department_name, []).append(item)

    results = {
        "ready_for_approval": [],
        "waiting_list": [],
        "active_tasks": [],
        "escalations": [],
        "departments": {},
    }

    for department, items in departments.items():

        maximum = int(
            capacity_per_department.get(
                department,
                DEFAULT_CAPACITY
            )
        )

        occupied = int(active_tasks.get(department, 0))

        running_tasks = sum(
            1
            for item in items
            if item["status"] == "In Bearbeitung"
        )

        occupied = max(occupied, running_tasks)

        free_slots = max(0, maximum - occupied)

        items.sort(
            key=lambda item: (
                -item["queue_score"],
                item["case_id"] or 0
            )
        )

        pending = []

        for item in items:

            if item["status"] == "In Bearbeitung":
                results["active_tasks"].append(item)
            else:
                pending.append(item)

        ready = pending[:free_slots]
        waiting = pending[free_slots:]

        for item in ready:
            item["delegation_status"] = "AWAITING_APPROVAL"

        for item in waiting:
            item["delegation_status"] = "WAITING_LIST"

            if priority_rank(item["priority"]) == CRITICAL_PRIORITY:
                item["delegation_status"] = "ESCALATION_REQUIRED"
                results["escalations"].append(item)

        results["ready_for_approval"].extend(ready)
        results["waiting_list"].extend(waiting)

        results["departments"][department] = {
            "maximum_capacity": maximum,
            "occupied_capacity": occupied,
            "available_capacity": free_slots,
            "waiting": len(waiting),
            "ready_for_approval": len(ready),
        }

    return results