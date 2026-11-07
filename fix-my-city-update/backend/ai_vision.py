"""Real AI image recognition through the Anthropic Messages API (vision).

The API key is read from the server environment only and is never sent to
the browser. Without a key the module returns SIMULATED outputs that are
clearly labeled as such and never presented as real AI analysis.
"""
import base64
import json
import os
import re

import httpx

API_URL = "https://api.anthropic.com/v1/messages"

ALLOWED = {
    "category": ["road_damage", "streetlight", "waste_dumping", "graffiti", "fallen_tree",
                 "broken_glass", "traffic_sign", "other"],
    "severity": ["low", "medium", "high", "critical"],
    "urgency": ["low", "medium", "high", "immediate"],
    "public_exposure": ["low", "medium", "high"],
}

PROMPT = """You are the image-recognition component of FIX MY CITY, a citizen reporting platform for the city of Pforzheim, Germany. Analyze the attached photo of a possible urban problem.

Citizen's description (may be empty, may be wrong): {description}

Category keys you may use:
road_damage (potholes, cracked or damaged roads), streetlight (broken streetlights), waste_dumping (illegal garbage dumping), graffiti, fallen_tree, broken_glass, traffic_sign (damaged traffic signs), other (another visible public infrastructure problem).

Rules:
- Base your answer only on what is visible in the image. Use the description only as context.
- If the image is unclear, or does not show a recognizable urban problem, set "image_recognizable" to false and do not force a category (use "other").
- Do not invent locations, names of real offices or authorities, numbers of affected people, or statistics.
- "public_exposure" is your estimate of how many people could be affected judging only from the visible scene (e.g. busy road, sidewalk, quiet path).
- Set "safety_critical" to true only if the visible situation could cause serious injury soon (e.g. large hole on a road, tree blocking a road, exposed wiring, large glass shards on a playground).
- Recommended actions are suggestions for city staff, not confirmed actions. For dangerous situations include requesting immediate human review and, if relevant, contacting emergency services.
- Write all text values in {language_name}, short and factual. Keep the JSON keys and the category/level keys exactly in English as listed.

Reply with ONLY this JSON object and nothing else:
{{"image_recognizable": true, "detected_incident": "short name of what you see", "category": "one category key", "description": "1-2 sentences describing what is visible", "potential_risks": ["risk 1", "risk 2"], "severity": "low|medium|high|critical", "urgency": "low|medium|high|immediate", "public_exposure": "low|medium|high", "exposure_reasoning": "one short sentence", "safety_critical": false, "recommended_actions": ["action 1", "action 2"]}}"""


class AIError(Exception):
    pass


def ai_mode():
    return "live" if os.getenv("ANTHROPIC_API_KEY", "").strip() else "simulated"


def model_name():
    return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")


def _extract_json(text):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise AIError("The AI response did not contain structured data.")
    return json.loads(text[start:end + 1])


def _clean(data):
    def pick(key, default):
        value = str(data.get(key, "")).strip().lower()
        return value if value in ALLOWED[key] else default

    def text(key, limit=500):
        v = data.get(key)
        return str(v).strip()[:limit] if v else ""

    def text_list(key):
        v = data.get(key) or []
        return [str(x).strip()[:200] for x in v if str(x).strip()][:6] if isinstance(v, list) else []

    recognizable = bool(data.get("image_recognizable", False))
    return {
        "image_recognizable": recognizable,
        "detected_incident": text("detected_incident", 120) or ("Unclear image" if not recognizable else "Unspecified"),
        "category": pick("category", "other") if recognizable else "other",
        "description": text("description"),
        "potential_risks": text_list("potential_risks"),
        "severity": pick("severity", None) if recognizable else None,
        "urgency": pick("urgency", None) if recognizable else None,
        "public_exposure": pick("public_exposure", None) if recognizable else None,
        "exposure_reasoning": text("exposure_reasoning", 300),
        "safety_critical": bool(data.get("safety_critical", False)) and recognizable,
        "recommended_actions": text_list("recommended_actions"),
        # The model does not return a calibrated confidence value, so none is shown.
        "confidence": None,
    }


LANGUAGE_NAMES = {"de": "German", "en": "English"}


def analyze_image(image_bytes, mime_type, description, citizen_category=None, language="en"):
    """Return a dict with the analysis plus 'mode', 'model' and 'raw_response'.
    `language` ("de" or "en") sets the language of all text values."""
    language = language if language in LANGUAGE_NAMES else "en"
    if ai_mode() == "simulated":
        return simulated_analysis(citizen_category, language)

    payload = {
        "model": model_name(),
        "max_tokens": 1000,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime_type,
                                             "data": base64.b64encode(image_bytes).decode()}},
                {"type": "text", "text": PROMPT.format(description=(description or "(none)")[:1000], language_name=LANGUAGE_NAMES[language])},
            ],
        }],
    }
    headers = {
        "x-api-key": os.getenv("ANTHROPIC_API_KEY", "").strip(),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    try:
        resp = httpx.post(API_URL, json=payload, headers=headers, timeout=90)
    except httpx.HTTPError as exc:
        raise AIError(f"Could not reach the AI service: {exc.__class__.__name__}") from exc
    if resp.status_code != 200:
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except ValueError:
            detail = ""
        raise AIError(f"The AI service returned an error ({resp.status_code}). {detail}".strip())

    body = resp.json()
    text = "".join(block.get("text", "") for block in body.get("content", []) if block.get("type") == "text")
    try:
        result = _clean(_extract_json(text))
    except (ValueError, AIError) as exc:
        raise AIError("The AI response could not be read as structured data. Please try again.") from exc
    result.update({"mode": "live", "model": body.get("model", model_name()), "raw_response": text[:4000]})
    return result


# ---------------------------------------------------------------------------
# SIMULATED mode: predefined sample outputs, used only when no API key is set.
# The image is NOT analyzed. The UI labels these results as simulated.
# ---------------------------------------------------------------------------
_SIMULATED = {
    "road_damage": ("Pothole", "A damaged section of asphalt with a visible hole.", ["Vehicle damage", "Cyclist fall hazard"], "high", "high", "high"),
    "streetlight": ("Broken streetlight", "A streetlight that appears not to be working.", ["Poor visibility at night", "Reduced feeling of safety"], "medium", "medium", "medium"),
    "waste_dumping": ("Illegally dumped waste", "A pile of household waste left in a public area.", ["Hygiene risk", "Attracts pests"], "medium", "medium", "medium"),
    "graffiti": ("Graffiti", "Spray-painted graffiti on a wall.", ["Visual damage to public space"], "low", "low", "medium"),
    "fallen_tree": ("Fallen tree", "A tree lying across a path.", ["Blocked path", "Injury risk"], "high", "immediate", "medium"),
    "broken_glass": ("Broken glass", "Glass shards on a walking surface.", ["Cut injuries", "Risk for children and pets"], "high", "high", "medium"),
    "traffic_sign": ("Damaged traffic sign", "A bent or damaged traffic sign.", ["Unclear traffic rules", "Accident risk"], "medium", "medium", "high"),
    "other": ("Infrastructure problem", "A visible problem with public infrastructure.", ["To be assessed"], "medium", "medium", "medium"),
}


_SIMULATED_DE = {
    "road_damage": ("Schlagloch", "Ein beschädigter Asphaltabschnitt mit sichtbarem Loch.", ["Fahrzeugschäden", "Sturzgefahr für Radfahrende"]),
    "streetlight": ("Defekte Straßenlaterne", "Eine Straßenlaterne, die offenbar nicht funktioniert.", ["Schlechte Sicht bei Nacht", "Geringeres Sicherheitsgefühl"]),
    "waste_dumping": ("Illegal abgelagerter Müll", "Ein Haufen Hausmüll im öffentlichen Raum.", ["Hygienerisiko", "Lockt Schädlinge an"]),
    "graffiti": ("Graffiti", "Gesprühtes Graffiti an einer Wand.", ["Optische Beeinträchtigung des öffentlichen Raums"]),
    "fallen_tree": ("Umgestürzter Baum", "Ein Baum liegt quer über einem Weg.", ["Blockierter Weg", "Verletzungsgefahr"]),
    "broken_glass": ("Glasscherben", "Glasscherben auf einer Gehfläche.", ["Schnittverletzungen", "Gefahr für Kinder und Haustiere"]),
    "traffic_sign": ("Beschädigtes Verkehrsschild", "Ein verbogenes oder beschädigtes Verkehrsschild.", ["Unklare Verkehrsregeln", "Unfallgefahr"]),
    "other": ("Infrastrukturproblem", "Ein sichtbares Problem an öffentlicher Infrastruktur.", ["Noch zu bewerten"]),
}


def simulated_analysis(citizen_category=None, language="en"):
    key = citizen_category if citizen_category in _SIMULATED else "road_damage"
    name, desc, risks, sev, urg, exp = _SIMULATED[key]
    if language == "de":
        name, desc, risks = _SIMULATED_DE[key]
    de = language == "de"
    return {
        "image_recognizable": True, "detected_incident": name, "category": key, "description": desc,
        "potential_risks": risks, "severity": sev, "urgency": urg, "public_exposure": exp,
        "exposure_reasoning": "Vordefinierter Beispielwert." if de else "Predefined sample value.", "safety_critical": False,
        "recommended_actions": ["Meldung prüfen", "Begehung planen"] if de else ["Review the report", "Schedule an inspection"],
        "confidence": None, "mode": "simulated", "model": None,
        "raw_response": "SIMULATED OUTPUT - no API key configured, the image was not analyzed.",
    }
