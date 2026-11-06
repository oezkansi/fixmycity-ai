Um deinen gesamten Prototypen lokal zu testen, folgst du diesen Schritten:

Hintergrund-Worker starten:
Öffne ein Terminal (Eingabeaufforderung) in deinem Projektverzeichnis und starte den Worker:

Bash
python worker.py
Der Worker läuft nun kontinuierlich im Hintergrund und überwacht die Datenbank.

Streamlit-App starten:
Öffne ein zweites Terminal-Fenster im selben Verzeichnis und starte die Web-Oberfläche:

Bash
streamlit run app.py
Dein Browser öffnet sich automatisch mit der Anwendung.

End-to-End-Test durchführen:

Gehe in der App auf den Tab "Bürger-Meldeformular".

Lade ein Testbild (z. B. ein Foto eines Schlaglochs oder einer beschädigten Laterne) hoch.

Gib eine kurze Beschreibung ein (z. B. "Tiefes Schlagloch mitten auf der Straße").

Wähle "Automatisch erkennen" und erlaube den Standortzugriff (das System ruft nun im Hintergrund die GIS-Daten von OpenStreetMap und die Live-Wetterdaten von Open-Meteo ab).

Klicke auf "Schadensmeldung absenden". Die KI validiert und klassifiziert das Bild, berechnet die Priorität und speichert den Fall in der SQLite-Datenbank.

Wechsle in den Tab "Verwaltungs-Dashboard". Dort siehst du nun live, wie dein gemeldeter Schaden einsortiert wurde – aufgeteilt in Aktive Baustellen oder die Warteliste (gesteuert durch das Kapazitätsmanagement) inklusive Score, Wartetagen und berücksichtigtem Wetterfaktor.
