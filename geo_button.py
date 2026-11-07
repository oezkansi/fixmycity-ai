"""Unsichtbare Standort-Komponente (ohne Zusatzpaket).

get_location(request=<Zähler>, key=...) fragt beim Start den Standort des Geräts ab und gibt
{"lat", "lon", "accuracy", "address"} zurück, bei Fehlern {"error": ...}, vorher None.
Der sichtbare Knopf ist ein normaler Streamlit-Knopf (siehe report.py).
"""
from pathlib import Path

import streamlit.components.v1 as components

_component = components.declare_component(
    "fmc_geo", path=str(Path(__file__).parent / "geo_component")
)


def get_location(request=0, key=None):
    return _component(request=request, key=key, default=None)
