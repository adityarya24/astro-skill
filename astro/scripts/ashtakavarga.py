#!/usr/bin/env python
"""Ashtakavarga — Bhinnashtakavarga (per-planet bindus) and Sarvashtakavarga.

For each of the seven planets, eight reference points (the seven planets + the
Lagna) each contribute a bindu to certain signs, counted from the reference's
own sign. The per-planet bindu totals are fixed (Sun 48 ... Saturn 39), so the
eight-fold Sarva total is always 337 — a checksum on the benefic tables.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_DATA = json.loads((DATA_DIR / "ashtakavarga_data.json").read_text(encoding="utf-8"))
BENEFIC_HOUSES = _DATA["benefic_houses"]

PLANETS = ["Surya", "Chandra", "Mangal", "Budh", "Guru", "Shukra", "Shani"]


def _bhinna(planet: str, reference_signs: dict) -> list[int]:
    bindus = [0] * 12
    for reference, houses in BENEFIC_HOUSES[planet].items():
        ref_sign = reference_signs[reference]
        for house in houses:
            bindus[(ref_sign + house - 1) % 12] += 1
    return bindus


def compute_ashtakavarga(planet_signs: dict, lagna_sign: int) -> dict:
    """Bhinna + Sarva bindus per sign (index 0-11).

    ``planet_signs`` maps each of the seven planets to its whole-sign index;
    ``lagna_sign`` is the ascendant's sign index.
    """
    reference_signs = {**{p: planet_signs[p] for p in PLANETS}, "Lagna": lagna_sign}
    bhinna = {planet: _bhinna(planet, reference_signs) for planet in PLANETS}
    sarva = [sum(bhinna[planet][sign] for planet in PLANETS) for sign in range(12)]
    return {
        "bhinna": bhinna,
        "bhinna_totals": {planet: sum(bindus) for planet, bindus in bhinna.items()},
        "sarva": sarva,
        "sarva_total": sum(sarva),
    }
