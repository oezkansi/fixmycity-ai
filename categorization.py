import json
from google.genai import types
from PIL import Image
from ai_analysis import client

# Eure vollständige Kategorien- und Gewichtungsstruktur
CATEGORIES_DB = {
    "pothole": {
        "department": "Road Maintenance",
        "subcategories": {
            "minor_pothole": {"safety": 25, "deterioration_rate": 1.5, "weather_sensitivity": 0.8},
            "deep_pothole": {"safety": 65, "deterioration_rate": 2.5, "weather_sensitivity": 1.0},
            "large_pothole": {"safety": 70, "deterioration_rate": 2.0, "weather_sensitivity": 0.9},
            "exposed_road_base": {"safety": 65, "deterioration_rate": 3.0, "weather_sensitivity": 1.0, "review": True}
        }
    },
    "road_crack": {
        "department": "Road Maintenance",
        "subcategories": {
            "hairline_crack": {"safety": 15, "deterioration_rate": 0.4, "weather_sensitivity": 0.8},
            "longitudinal_crack": {"safety": 30, "deterioration_rate": 0.8, "weather_sensitivity": 0.8},
            "transverse_crack": {"safety": 30, "deterioration_rate": 0.8, "weather_sensitivity": 0.8},
            "alligator_cracking": {"safety": 55, "deterioration_rate": 1.8, "weather_sensitivity": 1.0, "review": True}
        }
    },
    "sidewalk_damage": {
        "department": "Road Maintenance",
        "subcategories": {
            "uneven_surface": {"safety": 45, "deterioration_rate": 0.5},
            "broken_pavement": {"safety": 40, "deterioration_rate": 0.7},
            "missing_paving": {"safety": 55, "deterioration_rate": 0.5},
            "accessibility_obstruction": {"safety": 65, "deterioration_rate": 0.2}
        }
    },
    "broken_traffic_light": {
        "department": "Traffic Engineering",
        "subcategories": {
            "signal_off": {"safety": 90, "deterioration_rate": 0, "review": True},
            "incorrect_signal": {"safety": 98, "deterioration_rate": 0, "review": True},
            "physical_damage": {"safety": 75, "deterioration_rate": 0.5, "review": True},
            "pedestrian_signal_failure": {"safety": 80, "deterioration_rate": 0, "review": True}
        }
    },
    "damaged_road_sign": {
        "department": "Traffic Engineering",
        "subcategories": {
            "missing_sign": {"safety": 65, "deterioration_rate": 0, "review": True},
            "unreadable_sign": {"safety": 45, "deterioration_rate": 0.2},
            "bent_sign": {"safety": 45, "deterioration_rate": 0.5},
            "fallen_sign": {"safety": 70, "deterioration_rate": 0, "review": True}
        }
    },
    "fallen_tree": {
        "department": "Parks Department",
        "subcategories": {
            "tree_blocking_road": {"safety": 85, "deterioration_rate": 0, "review": True},
            "tree_blocking_sidewalk": {"safety": 70, "deterioration_rate": 0, "review": True},
            "tree_on_power_line": {"safety": 100, "deterioration_rate": 0, "review": True},
            "tree_on_property": {"safety": 75, "deterioration_rate": 0, "review": True}
        }
    },
    "fallen_branch": {
        "department": "Parks Department",
        "subcategories": {
            "small_branch": {"safety": 15, "deterioration_rate": 0},
            "large_branch": {"safety": 55, "deterioration_rate": 0},
            "branch_blocking_road": {"safety": 80, "deterioration_rate": 0, "review": True},
            "hanging_branch": {"safety": 85, "deterioration_rate": 0.8, "review": True}
        }
    },
    "streetlight_failure": {
        "department": "Street Lighting",
        "subcategories": {
            "light_off": {"safety": 30, "deterioration_rate": 0},
            "multiple_lights_off": {"safety": 55, "deterioration_rate": 0},
            "flickering_light": {"safety": 25, "deterioration_rate": 0.8},
            "damaged_light_pole": {"safety": 90, "deterioration_rate": 1.0, "review": True}
        }
    },
    "water_leak": {
        "department": "Water Utilities",
        "subcategories": {
            "minor_leak": {"safety": 25, "deterioration_rate": 2.0},
            "major_leak": {"safety": 70, "deterioration_rate": 3.0, "review": True},
            "road_flooding": {"safety": 80, "deterioration_rate": 1.5, "review": True},
            "suspected_pipe_burst": {"safety": 85, "deterioration_rate": 3.0, "review": True}
        }
    },
    "blocked_drain": {
        "department": "Drainage Services",
        "subcategories": {
            "leaves_blockage": {"safety": 20, "deterioration_rate": 0.5, "weather_sensitivity": 1.0},
            "trash_blockage": {"safety": 25, "deterioration_rate": 0.5, "weather_sensitivity": 1.0},
            "sediment_blockage": {"safety": 30, "deterioration_rate": 0.4, "weather_sensitivity": 1.0},
            "severe_flood_risk": {"safety": 85, "deterioration_rate": 2.0, "weather_sensitivity": 1.0, "review": True}
        }
    },
    "damaged_bench": {
        "department": "Public Spaces",
        "subcategories": {
            "cosmetic_damage": {"safety": 5, "deterioration_rate": 0.1},
            "broken_seat": {"safety": 35, "deterioration_rate": 0.4},
            "sharp_edges": {"safety": 70, "deterioration_rate": 0, "review": True},
            "unstable_structure": {"safety": 75, "deterioration_rate": 0.7, "review": True}
        }
    },
    "illegal_dumping": {
        "department": "Waste Management",
        "subcategories": {
            "general_waste": {"safety": 20, "deterioration_rate": 0.4},
            "bulky_waste": {"safety": 25, "deterioration_rate": 0.2},
            "electronic_waste": {"safety": 45, "deterioration_rate": 0.5},
            "chemical_waste": {"safety": 85, "deterioration_rate": 1.0, "review": True},
            "sharp_hazardous_waste": {"safety": 80, "deterioration_rate": 0.2, "review": True},
            "biological_waste": {"safety": 85, "deterioration_rate": 2.0, "review": True},
            "construction_waste": {"safety": 40, "deterioration_rate": 0.2},
            "suspected_asbestos": {"safety": 90, "deterioration_rate": 0, "review": True}
        }
    }
}

def categorize_report(image_path, description):
    """
    Klassifiziert den Schaden mithilfe der JSON-Struktur und Gemini.
    """
    image = Image.open(image_path)
    
    prompt = f"""
    Du bist das KI-Klassifizierungssystem für FixMyCity AI.
    Analysiere das Bild und die Beschreibung des Bürgers:
    Beschreibung: {description}

    Ordne den Schaden exakt einer Hauptkategorie und einer passenden Subkategorie zu, basierend auf dieser Struktur:
    {json.dumps(CATEGORIES_DB, indent=2)}

    Antworte ausschließlich im JSON-Format mit folgenden Schlüsseln:
    - "category": Name der Hauptkategorie (z.B. "pothole")
    - "subcategory": Name der Subkategorie (z.B. "deep_pothole")
    - "department": Zuständige Abteilung
    """

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=[prompt, image],
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    
    return json.loads(response.text)
