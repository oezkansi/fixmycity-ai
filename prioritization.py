
def calculate_priority(danger, impact, urgency, acute_hazard=False):
    """Calculate a suggested priority for municipal review."""

    for value in (danger, impact, urgency):
        if type(value) is not int or not 0 <= value <= 3:
            raise ValueError("Risk factors must be integers from 0 to 3.")

    score = 3 * danger + 2 * impact + urgency

    if acute_hazard or score >= 13:
        priority = "P1 - Critical"
    elif score >= 8:
        priority = "P2 - High"
    else:
        priority = "P3 - Normal"

    return {
        "score": score,
        "priority": priority,
        "requires_review": acute_hazard
    }


if __name__ == "__main__":
    result = calculate_priority(
        danger=3,
        impact=3,
        urgency=3,
        acute_hazard=True
    )
    print(result)
