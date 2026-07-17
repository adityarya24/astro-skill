#!/usr/bin/env python
"""Load per-planet classical remedies from ``astro/data/remedies.json``.

Data-only accessor — no chart calculation. Mantra strings intentionally match
``remedies_ext.json`` for backward compatibility with the extended report path.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

PLANETS = (
    "Surya",
    "Chandra",
    "Mangal",
    "Budh",
    "Guru",
    "Shukra",
    "Shani",
    "Rahu",
    "Ketu",
)


@lru_cache(maxsize=1)
def load_remedies() -> dict:
    """Return the full remedies document (planets keyed by Hindi graha name)."""
    path = DATA_DIR / "remedies.json"
    return json.loads(path.read_text(encoding="utf-8"))


def get_planet_remedy(planet: str) -> dict:
    """Return the remedy block for one planet; raises ``KeyError`` if unknown."""
    planets = load_remedies()["planets"]
    if planet not in planets:
        raise KeyError(f"No remedies for planet {planet!r}")
    return planets[planet]
