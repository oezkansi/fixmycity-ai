import unittest
from duplicate_detection import (
    calculate_distance,
    normalize_description,
    description_similarity,
    compare_reports,
    find_existing_duplicates
)

class TestDuplicateDetection(unittest.TestCase):

    def test_calculate_distance(self):
        # Gleiche Koordinaten -> Distanz 0
        dist = calculate_distance(48.899, 8.700, 48.899, 8.700)
        self.assertAlmostEqual(dist, 0.0, places=1)
        
        # Bekannte Distanz (ca. 111 km pro Breitengrad)
        dist_lat = calculate_distance(48.0, 8.0, 49.0, 8.0)
        self.assertTrue(110000 < dist_lat < 112000)

    def test_normalize_description(self):
        desc1 = "  Loch in Straße!! (Schadensfall) "
        normalized = normalize_description(desc1)
        # Sollte Lowercase, Ersetzungen und bereinigte Sonderzeichen enthalten
        self.assertIn("schlagloch", normalized)
        self.assertNotIn("!", normalized)

    def test_description_similarity(self):
        # Ähnliche Texte, die nach Normalisierung deckungsgleich sind
        sim_high = description_similarity("Schlagloch auf der Fahrbahn", "Schlagloch auf der Fahrbahn")
        self.assertEqual(sim_high, 1.0)
        
        sim_low = description_similarity("Schlagloch in der Straße", "Defekte Straßenlaterne")
        self.assertLess(sim_low, 0.4)

    def test_compare_reports_distance_filter(self):
        r1 = {"id": 1, "damage_latitude": 48.899, "damage_longitude": 8.700, "description": "Schlagloch"}
        r2 = {"id": 2, "damage_latitude": 49.500, "damage_longitude": 9.000, "description": "Schlagloch"} # Weit entfernt (>100m)
        
        result = compare_reports(r1, r2)
        self.assertIsNone(result)

    def test_find_existing_duplicates_clustering(self):
        reports = [
            {"id": 1, "damage_latitude": 48.8990, "damage_longitude": 8.7000, "description": "Schlagloch auf der Fahrbahn", "image_hash": None, "duplicate_of": None},
            {"id": 2, "damage_latitude": 48.8991, "damage_longitude": 8.7001, "description": "Schlagloch auf der Fahrbahn", "image_hash": None, "duplicate_of": None},
            {"id": 3, "damage_latitude": 49.9999, "damage_longitude": 9.9999, "description": "Umgestürzter Baum", "image_hash": None, "duplicate_of": None}
        ]
        
        groups = find_existing_duplicates(reports)
        # Erwartet werden 2 Gruppen (1 Duplikat-Gruppe + 1 Einzelgruppe)
        self.assertEqual(len(groups), 2)
        
        duplicate_group = next(g for g in groups if len(g["reports"]) == 2)
        self.assertEqual(duplicate_group["duplicate_count"], 1)

if __name__ == "__main__":
    unittest.main()