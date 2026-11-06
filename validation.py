
import json
from PIL import Image
from google.genai import types
from ai_analysis import client


def validate_report(image_path, description):
    image = Image.open(image_path)

    
    prompt = f"""
    You are a strict visual claim verification system
    for FixMyCity AI.

    CITIZEN'S EXACT CLAIM:
    {description}

    Your task is to verify the SPECIFIC problem
    described by the citizen against the image.

    CRITICAL RULES:

    1. Identify the exact problem claimed by
       the citizen.

    2. Independently describe what is actually
       visible in the image.

    3. Compare the claimed problem with the
       visible evidence.

    4. A different visible problem does NOT
       validate the citizen's claim.

    EXAMPLE:
    Citizen claims: "Needles on the road"
    Image shows: A pothole, but no needles.
    Result: INVALID.
    Even though the pothole is a real problem,
    it does not support the claim about needles.

    5. VALID:
       The specific reported problem is clearly
       supported by the image.

    6. INVALID:
       The specific reported problem is not
       supported by a sufficiently clear image,
       or the image shows a different problem.

    7. UNCERTAIN:
       The image is blurry, obstructed, too far
       away, or otherwise insufficient to decide.

    8. Never invent evidence or assume that
       something is visible when it is not.

    9. Do not treat shared words such as
       "road", "street", or "sidewalk" as
       proof that the claimed defect exists.

    Return a JSON object with exactly:
    status: VALID, INVALID, or UNCERTAIN
    reason: explanation in German
    detected_problem: what is actually visible
    """


    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=[prompt, image],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    result = json.loads(response.text)

    if not isinstance(result, dict):
        raise ValueError("Ungültige KI-Antwort.")

    if result.get("status") not in {
        "VALID", "INVALID", "UNCERTAIN"
    }:
        raise ValueError("Unbekannter Validierungsstatus.")

    for field in ("reason", "detected_problem"):
        if not isinstance(result.get(field), str):
            raise ValueError(f"Ungültiges Feld: {field}")

    return result


if __name__ == "__main__":
    image_path = input("Bildpfad: ")
    description = input("Schadensbeschreibung: ")

    result = validate_report(image_path, description)

    print("\n--- KI-VALIDIERUNG ---")
    print("Status:", result["status"])
    print("Begründung:", result["reason"])
    print("Erkanntes Problem:", result["detected_problem"])
