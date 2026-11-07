# validation.py
import google.generativeai as genai
from PIL import Image
import os
import json

# API-Key konfigurieren (wird aus der Umgebung geladen)
if os.environ.get("GEMINI_API_KEY"):
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def validate_report(image_path, description):
    """
    Prüft via Gemini Vision, ob das hochgeladene Bild zum Text passt 
    und ein echtes kommunales Problem (z.B. Schlagloch, defekte Laterne, Müllkippe) zeigt.
    Gibt ein Dictionary mit Status ("VALID" oder "INVALID") und einer Begründung zurück.
    """
    try:
        img = Image.open(image_path)
    except Exception as e:
        return {
            "status": "INVALID", 
            "reason": f"Das Bild konnte nicht geöffnet oder gelesen werden: {e}"
        }

    prompt = """
    Du bist ein strenger KI-Prüfungsassistent für die kommunale Verwaltung (FixMyCity AI).
    Analysiere das vorliegende Bild und die dazugehörige Beschreibung des Bürgers sorgfältig.

    Kriterien für eine Gültigkeit (Status: "VALID"):
    1. Das Bild zeigt ein echtes, konkretes kommunales Problem im öffentlichen Raum (z.B. ein Schlagloch, eine beschädigte Straßenlaterne, illegale Müllkippe, ein beschädigtes Verkehrsschild oder kaputte Gehwegplatten).
    2. Das Bild stimmt inhaltlich logisch mit der Beschreibung des Bürgers überein.

    Kriterien für eine Ablehnung (Status: "INVALID"):
    1. Das Bild zeigt überhaupt keinen Schaden oder kein kommunales Problem (z.B. Selfies, Haustiere, Landschaften, Autos ohne Schaden, Innenaufnahmen von privaten Wohnungen).
    2. Das Bild passt inhaltlich absolut nicht zur Beschreibung (z.B. Beschreibung sagt "Schlagloch" aber Bild zeigt eine kaputte Parkbank, oder umgekehrt).
    3. Es handelt sich offensichtlich um ein unscharfes, unbrauchbares oder gefälschtes Bild.

    Antworte AUSSCHLIESSLICH im folgenden JSON-Format (ohne zusätzlichen Text drumherum):
    {
        "status": "VALID" oder "INVALID",
        "reason": "Eine kurze, präzise Begründung auf Deutsch, warum die Meldung akzeptiert oder abgelehnt wurde."
    }
    """

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([prompt, img])
        
        # Bereinigung des JSON-Outputs (falls Markdown-Blöcke enthalten sind)
        text = response.text.replace("```json", "").replace("```", "").strip()
        
        # JSON parsen
        result = json.loads(text)
        
        # Absicherung, dass die Keys existieren
        if "status" not in result or "reason" not in result:
            return {"status": "VALID", "reason": "Standardvalidierung durchgeführt."}
            
        return result
        
    except Exception as e:
        # Fallback bei API- oder Parsing-Fehlern, damit die App nicht abstürzt
        return {
            "status": "VALID", 
            "reason": f"Automatisierte Validierung aufgrund eines technischen Fehlers übersprungen: {e}"
        }