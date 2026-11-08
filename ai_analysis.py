import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from PIL import Image

# Lädt die .env-Datei direkt aus dem Projektverzeichnis
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

def analyze_report(image_path, description):

def analyze_report(image_path, description):
    image = Image.open(image_path)

    prompt = f"""
    You are an AI assistant for FixMyCity AI.

    Analyze the image AND the citizen's description.

    Citizen description: {description}

    Identify:
    1. What problem is visible?
    2. Which category does it belong to?
    3. How dangerous could it be?
    4. What additional risks are present?

    Do not invent details that are not visible
    or mentioned in the description.

    Respond in German.
    """

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=[prompt, image]
    )

    return response.text


if __name__ == "__main__":
    image_path = input("Bildpfad: ")
    description = input("Beschreibung: ")

    result = analyze_report(image_path, description)
    print("\nKI-Analyse:")
    print(result)

