
import json
from google.genai import types

from ai_analysis import client
from prioritization import calculate_priority


def analyze_priority(description):
    prompt = f"""
    You are assisting a municipal reporting system.

    Analyze the following citizen report:
    {description}

    Return risk factors as integers from 0 to 3.

    danger: How dangerous is the situation?
    impact: How many people could be affected?
    urgency: How quickly should it be addressed?
    acute_hazard: Return only true or false. Never return a number.

    Do not automatically trust the citizen's
    subjective urgency rating.

    Return only JSON with these keys:
    danger, impact, urgency, acute_hazard
    """

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    factors = json.loads(response.text)

    result = calculate_priority(
        danger=factors["danger"],
        impact=factors["impact"],
        urgency=factors["urgency"],
        acute_hazard=factors["acute_hazard"]
    )

    return factors, result


if __name__ == "__main__":
    description = input("Schadensbeschreibung: ")

    factors, priority = analyze_priority(description)

    print("\nKI-Risikofaktoren:", factors)
    print("Berechnete Priorität:", priority)
