#!/usr/bin/env python
"""Detect common Vedic yogas from a computed kundali.

Pure, calculation-backed detection over the kundali dict produced by
``kundali_calculator`` — no ephemeris access, so it is fast and trivially
testable. Each yoga is a draft observation for an astrologer to interpret; this
module only reports the geometric condition, never a prediction.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

KENDRAS = {1, 4, 7, 10}
TRIKONAS = {1, 5, 9}

# Pancha Mahapurusha: planet -> yoga name. Each forms when the planet sits in a
# kendra (from lagna) in its own or exaltation sign.
MAHAPURUSHA = {
    "Mangal": "Ruchaka",
    "Budh": "Bhadra",
    "Guru": "Hamsa",
    "Shukra": "Malavya",
    "Shani": "Sasa",
}

# Planets that count for Kemadruma (luminary Moon plus the five taras; the Sun
# and the shadowy nodes are excluded by the classical rule).
KEMADRUMA_PLANETS = ("Mangal", "Budh", "Guru", "Shukra", "Shani")


def _load_graha_data() -> dict:
    return json.loads((DATA_DIR / "graha_data.json").read_text(encoding="utf-8"))


def _house(planets: dict, name: str) -> int:
    return int(planets[name]["house"])


def _relative_house(planets: dict, name: str, reference: str) -> int:
    """House of ``name`` counted from ``reference`` (1 = same house as reference)."""
    return ((_house(planets, name) - _house(planets, reference)) % 12) + 1


def detect_yogas(planets: dict, houses: dict, graha_data: dict | None = None) -> list[dict]:
    """Return a list of detected yogas as ``{name, type, planets, description}``."""
    graha_data = graha_data or _load_graha_data()
    planet_meta = graha_data["planets"]
    yogas: list[dict] = []

    # Gajakesari: Jupiter in a kendra (1/4/7/10) from the Moon.
    if "Guru" in planets and "Chandra" in planets:
        if _relative_house(planets, "Guru", "Chandra") in KENDRAS:
            yogas.append(
                {
                    "name": "Gajakesari",
                    "type": "raja-like",
                    "planets": ["Guru", "Chandra"],
                    "description": "Jupiter in a kendra from the Moon.",
                }
            )

    # Budhaditya: Sun and Mercury together.
    if _house(planets, "Surya") == _house(planets, "Budh"):
        yogas.append(
            {
                "name": "Budhaditya",
                "type": "intellect",
                "planets": ["Surya", "Budh"],
                "description": "Sun and Mercury in the same house.",
            }
        )

    # Chandra-Mangal: Moon and Mars together.
    if _house(planets, "Chandra") == _house(planets, "Mangal"):
        yogas.append(
            {
                "name": "Chandra-Mangal",
                "type": "wealth-effort",
                "planets": ["Chandra", "Mangal"],
                "description": "Moon and Mars in the same house.",
            }
        )

    # Pancha Mahapurusha: planet in own/exaltation sign in a kendra.
    for planet, yoga_name in MAHAPURUSHA.items():
        info = planets.get(planet)
        if not info or _house(planets, planet) not in KENDRAS:
            continue
        meta = planet_meta.get(planet, {})
        own = set(meta.get("own_signs", []))
        exalt = meta.get("exaltation_sign")
        if info["sign"] in own or info["sign"] == exalt:
            dignity = "own sign" if info["sign"] in own else "exaltation"
            yogas.append(
                {
                    "name": f"{yoga_name} (Mahapurusha)",
                    "type": "mahapurusha",
                    "planets": [planet],
                    "description": f"{planet} in a kendra in its {dignity} ({info['sign']}).",
                }
            )

    # Kemadruma: 2nd and 12th from the Moon empty of the tara planets, and no
    # tara planet with the Moon.
    moon_house = _house(planets, "Chandra")
    second = (moon_house % 12) + 1
    twelfth = ((moon_house - 2) % 12) + 1
    occupied = {
        _house(planets, p) for p in KEMADRUMA_PLANETS if p in planets
    }
    # Kemadruma-bhanga: a planet in a kendra from the Moon cancels the yoga
    # (this is also why Gajakesari and Kemadruma cannot co-exist).
    moon_kendra_occupied = any(
        _relative_house(planets, p, "Chandra") in KENDRAS
        for p in KEMADRUMA_PLANETS
        if p in planets
    )
    if not ({second, twelfth, moon_house} & occupied) and not moon_kendra_occupied:
        yogas.append(
            {
                "name": "Kemadruma",
                "type": "affliction",
                "planets": ["Chandra"],
                "description": "No planet in the 2nd/12th from the Moon nor with it.",
            }
        )

    # Raja yoga: a kendra lord and a (different) trikona lord conjunct.
    kendra_lords = {houses[str(h)]["lord"] for h in KENDRAS}
    trikona_lords = {houses[str(h)]["lord"] for h in TRIKONAS}
    seen_pairs: set[tuple[str, str]] = set()
    for kl in kendra_lords:
        for tl in trikona_lords:
            if kl == tl or kl not in planets or tl not in planets:
                continue
            if _house(planets, kl) != _house(planets, tl):
                continue
            pair = tuple(sorted((kl, tl)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            yogas.append(
                {
                    "name": "Raja Yoga",
                    "type": "raja",
                    "planets": list(pair),
                    "description": (
                        f"Kendra lord {kl} and trikona lord {tl} conjunct in "
                        f"house {_house(planets, kl)}."
                    ),
                }
            )

    return yogas
