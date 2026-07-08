#!/usr/bin/env python
"""Graha drishti — Parashari full (100%) planetary aspects.

Every graha aspects the 7th house/sign from itself. The malefics and Jupiter add
special aspects. Houses are counted inclusively (a planet's own house is the 1st).
"""
from __future__ import annotations

# Aspected houses counted from the planet's own house (own house = 1).
ASPECT_OFFSETS: dict[str, list[int]] = {
    "Mangal": [4, 7, 8],   # Mars
    "Guru": [5, 7, 9],     # Jupiter
    "Shani": [3, 7, 10],   # Saturn
    "Rahu": [5, 7, 9],     # nodes: Jupiter-like (documented convention)
    "Ketu": [5, 7, 9],
}
DEFAULT_OFFSETS = [7]      # Sun, Moon, Mercury, Venus


def _aspected_house(house: int, offset: int) -> int:
    return ((house - 1 + offset - 1) % 12) + 1


def compute_aspects(planets: dict) -> dict:
    """Return per-graha full-aspect data.

    ``planets`` maps graha name -> info dict containing a whole-sign ``house``
    (1-12). For each graha the result gives ``aspects_houses`` (the house numbers
    it casts full drishti on), ``aspects_planets`` (grahas sitting in those
    houses), and the reverse ``aspected_by``.
    """
    houses = {name: int(info["house"]) for name, info in planets.items()}

    aspects_houses = {
        name: sorted({_aspected_house(h, off) for off in ASPECT_OFFSETS.get(name, DEFAULT_OFFSETS)})
        for name, h in houses.items()
    }

    occupants: dict[int, list[str]] = {}
    for name, h in houses.items():
        occupants.setdefault(h, []).append(name)

    result: dict[str, dict] = {}
    for name in planets:
        cast = aspects_houses[name]
        aspects_planets = [p for h in cast for p in occupants.get(h, []) if p != name]
        aspected_by = [
            other
            for other in planets
            if other != name and houses[name] in aspects_houses[other]
        ]
        result[name] = {
            "aspects_houses": cast,
            "aspects_planets": aspects_planets,
            "aspected_by": aspected_by,
        }
    return result
