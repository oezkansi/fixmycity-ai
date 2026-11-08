
import json
from PIL import Image
from google.genai import types
from ai_analysis import client


def validate_report(image_path, description):
    image = Image.open(image_path)


    emergency_prompt = f"""
    You are an emergency safety screening system.

    Citizen description:
    {description}

    Assess the citizen's description and the image
    for a possible ongoing or imminent emergency.

    IMPORTANT:
    The image does not need to visibly confirm
    the emergency if the description credibly
    reports immediate danger.

    Examples:
    - A ceiling is currently collapsing and
      people are underneath.
    - People are trapped in a damaged building.
    - A serious fire is currently threatening people.

    Do not classify ordinary damage or a hypothetical
    future risk as an immediate emergency.

    Return JSON with:
    emergency: true or false
    reason: short explanation in German

    Treat the description as a report, not as
    independently verified evidence.
    """

    emergency_response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=[emergency_prompt, image],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    emergency_result = json.loads(emergency_response.text)

    if emergency_result.get("emergency") is True:
        return {
            "status": "EMERGENCY",
            "reason": emergency_result.get(
                "reason",
                "Die Beschreibung weist auf eine mögliche akute Gefahr hin."
            ),
            "detected_problem": "Mögliche akute Gefahr"
        }


    
    prompt = f"""
    You are a strict visual claim verification system
    for FixMyCity AI.


IMPORTANT SAFETY RULE — CHECK FIRST:

Before deciding whether the image confirms the
citizen's claim, assess the description and image
for a possible immediate emergency.

If the citizen describes an ongoing or imminent
threat to human life, such as a collapsing ceiling
with people underneath, do not automatically
return INVALID merely because the danger is not
visually apparent.

Return EMERGENCY when there is a credible indication
of immediate danger in either the description or
the image.

EMERGENCY means "possible acute danger requiring
human assessment", NOT "emergency visually confirmed".

In the German reason, clearly distinguish between
what the citizen reports and what the image confirms.

For ordinary damage without indications of immediate
danger, continue with the normal VALID, INVALID,
or UNCERTAIN classification.

Safety assessment takes priority over municipal
reportability and visual claim verification.


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
   Return VALID ONLY if ALL of the following
   conditions are satisfied:

   A. The image clearly supports the citizen's
      specific description.

   B. The image shows an actual defect, damage,
      obstruction, contamination, or concrete
      safety concern.

   C. The issue is potentially relevant to
      public infrastructure or municipal services.

   IMPORTANT:
   Matching the image and description is NOT
   sufficient to return VALID.

   Examples:
   - Cat sitting peacefully in a basket:
     INVALID, even if the description says
     "Cat sitting in a basket".
   - Ordinary decoration in a shopping mall:
     INVALID if no actual hazard is visible.
   - Large pothole on a public road:
     VALID if the description matches.
   - Unclear potentially dangerous object:
     UNCERTAIN.

   If the image and description match but
   no concrete reportable problem exists,
   return INVALID.


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
    status: VALID, INVALID, UNCERTAIN, or EMERGENCY
    reason: explanation in German
    detected_problem: what is actually visible


ADDITIONAL REPORTABILITY CHECK:

Before marking a report as VALID, also verify whether
the image shows a genuine, reportable public issue.

10. A visible object alone is NOT proof of a hazard.
    Check whether there is an actual defect, obstruction,
    damage, contamination, or concrete safety concern.

11. Do NOT classify ordinary objects, decorations,
    artwork, advertisements, or harmless everyday
    situations as hazards without visible evidence
    of a real problem.

12. If the image clearly shows no actual problem,
    return INVALID.
    Explain in German that no reportable issue
    could be identified.

13. If a potentially dangerous situation cannot
    be reliably distinguished from a harmless object
    or decoration, return UNCERTAIN.
    Do not automatically reject a possible hazard.

14. Consider whether the issue is generally relevant
    to public infrastructure or municipal services,
    such as roads, sidewalks, streetlights,
    public waste, or public safety.

15. A problem inside a private shop or shopping mall
    may be the responsibility of the property operator.
    If responsibility cannot be established from the
    image alone, return UNCERTAIN rather than guessing.

16. Return VALID only when the specific citizen claim
    is supported by the image AND a concrete reportable
    problem is identifiable.

17. Never invent a hazard, damage, or responsibility
    that cannot be established from the evidence.


    EMERGENCY DETECTION — HIGHEST SAFETY PRIORITY:

    Before applying the normal municipal reportability
    rules, assess whether the citizen's description
    or the image indicates a possible immediate
    threat to human life or physical safety.

    Examples include:
    - A building or ceiling actively collapsing.
    - People trapped under debris.
    - A serious fire with people at risk.
    - Severe injuries requiring urgent assistance.
    - An earthquake with ongoing structural danger.
    - An immediate threat of serious violence.

    If there is credible evidence of an ongoing
    or imminent emergency, return EMERGENCY.

    IMPORTANT:
    - Do not require the situation to be a municipal
      infrastructure problem.
    - Do not classify every pothole, broken object,
      or ordinary infrastructure defect as EMERGENCY.
    - Distinguish immediate danger from damage
      that has already occurred and is no longer acute.
    - Do not claim certainty about facts that cannot
      be verified from the image.
    - A credible emergency described by the citizen
      must not be dismissed solely because the image
      is unclear.
    - If immediate danger cannot be ruled out,
      communicate uncertainty in the German reason
      and recommend contacting emergency services
      if anyone is currently in danger.
    - Never claim that FixMyCity AI has contacted
      emergency responders.

    For EMERGENCY, return:
    status: EMERGENCY
    reason: A calm, empathetic explanation in German,
            recommending 112 for fire, rescue, or
            medical emergencies and 110 for urgent
            police assistance.
    detected_problem: The suspected emergency.

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
    "VALID", "INVALID", "UNCERTAIN", "EMERGENCY"
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
