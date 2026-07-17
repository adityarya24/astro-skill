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
DUSTHANAS = {6, 8, 12}
# Upachaya-style houses used for Khala parivartana (3/6/11); 6 is also dusthana.
KHALA_HOUSES = {3, 6, 11}

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

# Seven tara/luminary planets checked for Kaal Sarp (nodes define the axis).
KAAL_SARP_PLANETS = ("Surya", "Chandra", "Mangal", "Budh", "Guru", "Shukra", "Shani")

# Natural benefics used for Vipreet strength downgrade (conjunct a benefic).
NATURAL_BENEFICS = frozenset({"Guru", "Shukra", "Budh", "Chandra"})

# Classical: which planet is exalted in which sign (inverse of exaltation_sign).
# Built at runtime from graha_data when available; fallback for the seven.
_EXALTED_IN_FALLBACK = {
    "Mesha": "Surya",
    "Vrishabha": "Chandra",
    "Makara": "Mangal",
    "Kanya": "Budh",
    "Karka": "Guru",
    "Meena": "Shukra",
    "Tula": "Shani",
}


def _load_graha_data() -> dict:
    return json.loads((DATA_DIR / "graha_data.json").read_text(encoding="utf-8"))


def _house(planets: dict, name: str) -> int:
    return int(planets[name]["house"])


def _relative_house(planets: dict, name: str, reference: str) -> int:
    """House of ``name`` counted from ``reference`` (1 = same house as reference)."""
    return ((_house(planets, name) - _house(planets, reference)) % 12) + 1


def _sign_lord_map(graha_data: dict) -> dict[str, str]:
    return {s["name"]: s["lord"] for s in graha_data["signs"]}


def _exalted_in_map(planet_meta: dict) -> dict[str, str]:
    """sign -> planet exalted there (ignores nodes for Neechabhanga condition b)."""
    out: dict[str, str] = {}
    for planet, meta in planet_meta.items():
        if planet in ("Rahu", "Ketu"):
            continue
        exalt = meta.get("exaltation_sign")
        if exalt:
            out[exalt] = planet
    return out or dict(_EXALTED_IN_FALLBACK)


def _in_kendra_from_lagna_or_chandra(planets: dict, name: str) -> bool:
    if name not in planets:
        return False
    if _house(planets, name) in KENDRAS:
        return True
    if "Chandra" in planets and _relative_house(planets, name, "Chandra") in KENDRAS:
        return True
    return False


def _houses_forward(start: int, end: int, *, inclusive_end: bool = False) -> set[int]:
    """Houses walking forward from ``start`` toward ``end`` (1..12 cyclic)."""
    result: set[int] = set()
    h = start
    for _ in range(12):
        result.add(h)
        if h == end:
            break
        h = (h % 12) + 1
    if not inclusive_end and end in result and start != end:
        result.discard(end)
    return result


def _detect_neechabhanga(
    planets: dict, planet_meta: dict, sign_lords: dict[str, str], exalted_in: dict[str, str]
) -> list[dict]:
    """Neechabhanga Raja Yoga: debilitated planet with cancellation condition."""
    yogas: list[dict] = []
    for planet, info in planets.items():
        if planet in ("Rahu", "Ketu"):
            continue
        meta = planet_meta.get(planet, {})
        deb_sign = meta.get("debilitation_sign")
        if not deb_sign or info.get("sign") != deb_sign:
            continue

        conditions: list[str] = []
        dispositor = sign_lords.get(deb_sign)

        # (a) lord of the debilitation sign in kendra from lagna or Chandra
        if dispositor and dispositor in planets:
            if _in_kendra_from_lagna_or_chandra(planets, dispositor):
                conditions.append("a_dispositor_kendra")

        # (b) planet exalted in that sign is in kendra from lagna/Chandra
        exalted_planet = exalted_in.get(deb_sign)
        if exalted_planet and exalted_planet in planets and exalted_planet != planet:
            if _in_kendra_from_lagna_or_chandra(planets, exalted_planet):
                conditions.append("b_exalted_planet_kendra")

        # (c) debilitated planet's dispositor exchange (parivartana with sign lord):
        # planet is already in the dispositor's sign; exchange requires the
        # dispositor to sit in an own-sign of the debilitated planet.
        if dispositor and dispositor in planets and dispositor != planet:
            own = set(meta.get("own_signs", []))
            if planets[dispositor].get("sign") in own:
                conditions.append("c_dispositor_exchange")

        if not conditions:
            continue

        yogas.append(
            {
                "name": "Neechabhanga Raja Yoga",
                "type": "raja",
                "planets": [planet],
                "condition": conditions,
                "description": (
                    f"{planet} debilitated in {deb_sign}; cancellation via "
                    f"{', '.join(conditions)}."
                ),
            }
        )
    return yogas


def _conjunct_benefic(planets: dict, name: str) -> bool:
    h = _house(planets, name)
    for other, info in planets.items():
        if other == name or other in ("Rahu", "Ketu"):
            continue
        if other not in NATURAL_BENEFICS:
            continue
        if int(info["house"]) == h:
            return True
    return False


def _in_own_sign(planets: dict, name: str, planet_meta: dict) -> bool:
    info = planets.get(name)
    if not info:
        return False
    own = set(planet_meta.get(name, {}).get("own_signs", []))
    return info.get("sign") in own


def _detect_vipreet(planets: dict, houses: dict, planet_meta: dict) -> list[dict]:
    """Vipreet Raja Yoga: dusthana lords placed in another dusthana."""
    yogas: list[dict] = []
    specs = (
        (6, "Harsha"),
        (8, "Sarala"),
        (12, "Vimala"),
    )
    seen: set[str] = set()
    for dusthana, subtype in specs:
        lord = houses.get(str(dusthana), {}).get("lord")
        if not lord or lord not in planets:
            continue
        lord_house = _house(planets, lord)
        if lord_house not in DUSTHANAS:
            continue
        # Must be in a dusthana; classical Vipreet is strongest when the lord
        # occupies a different dusthana, but same-dusthana (e.g. 6th lord in 6)
        # is still Harsha. Fire whenever the dusthana lord sits in 6/8/12.
        key = f"{subtype}:{lord}:{lord_house}"
        if key in seen:
            continue
        seen.add(key)

        weaker = _conjunct_benefic(planets, lord) or _in_own_sign(planets, lord, planet_meta)
        strength = "weaker" if weaker else "full"
        yogas.append(
            {
                "name": f"{subtype} (Vipreet Raja)",
                "type": "vipreet-raja",
                "planets": [lord],
                "strength": strength,
                "dusthana": dusthana,
                "description": (
                    f"{subtype}: {dusthana}th lord {lord} in dusthana house "
                    f"{lord_house} (strength={strength})."
                ),
            }
        )
    return yogas


def _detect_kaal_sarp(planets: dict) -> list[dict]:
    """Kaal Sarp: seven planets on one side of the Rahu–Ketu axis."""
    if "Rahu" not in planets or "Ketu" not in planets:
        return []
    rahu_h = _house(planets, "Rahu")
    ketu_h = _house(planets, "Ketu")

    # Two semicircles of the axis (inclusive of both nodes so conjunct-node
    # placements still count as on-axis).
    rahu_to_ketu = _houses_forward(rahu_h, ketu_h, inclusive_end=True)
    ketu_to_rahu = _houses_forward(ketu_h, rahu_h, inclusive_end=True)

    positions = []
    for name in KAAL_SARP_PLANETS:
        if name not in planets:
            return []
        positions.append(_house(planets, name))

    outside_rtk = sum(1 for h in positions if h not in rahu_to_ketu)
    outside_ktr = sum(1 for h in positions if h not in ketu_to_rahu)

    # Prefer the arc that leaves fewer planets outside.
    if outside_rtk <= outside_ktr:
        outside = outside_rtk
        direction = "rahu_to_ketu"
    else:
        outside = outside_ktr
        direction = "ketu_to_rahu"

    if outside >= 2:
        return []

    partial = outside == 1
    yogas = [
        {
            "name": "Kaal Sarp",
            "type": "dosha",
            "planets": list(KAAL_SARP_PLANETS) + ["Rahu", "Ketu"],
            "partial": partial,
            "direction": direction,
            "description": (
                f"Kaal Sarp ({'partial' if partial else 'full'}): seven planets "
                f"on the {direction.replace('_', ' ')} side of the Rahu-Ketu axis."
            ),
        }
    ]
    return yogas


def _parivartana_type(house_a: int, house_b: int) -> str:
    """Classify exchange: dainya (6/8/12), khala (3/6/11), else maha."""
    houses = {house_a, house_b}
    if houses & DUSTHANAS:
        return "dainya"
    if houses & KHALA_HOUSES:
        return "khala"
    return "maha"


def _detect_parivartana(
    planets: dict, sign_lords: dict[str, str]
) -> list[dict]:
    """Mutual sign exchange between two planets (parivartana yoga)."""
    yogas: list[dict] = []
    # Consider the seven classical grahas (nodes rarely participate in lordship).
    candidates = [
        p
        for p in ("Surya", "Chandra", "Mangal", "Budh", "Guru", "Shukra", "Shani")
        if p in planets
    ]
    seen: set[tuple[str, str]] = set()
    for i, a in enumerate(candidates):
        sign_a = planets[a].get("sign")
        if not sign_a:
            continue
        lord_of_a = sign_lords.get(sign_a)
        if not lord_of_a or lord_of_a == a or lord_of_a not in planets:
            continue
        sign_b = planets[lord_of_a].get("sign")
        if not sign_b:
            continue
        lord_of_b = sign_lords.get(sign_b)
        if lord_of_b != a:
            continue
        pair = tuple(sorted((a, lord_of_a)))
        if pair in seen:
            continue
        seen.add(pair)
        ha, hb = _house(planets, a), _house(planets, lord_of_a)
        ptype = _parivartana_type(ha, hb)
        yogas.append(
            {
                "name": "Parivartana",
                "type": ptype,
                "planets": list(pair),
                "description": (
                    f"Parivartana ({ptype}): {pair[0]} and {pair[1]} exchange signs "
                    f"(houses {ha} and {hb})."
                ),
            }
        )
    return yogas


def detect_yogas(planets: dict, houses: dict, graha_data: dict | None = None) -> list[dict]:
    """Return a list of detected yogas as ``{name, type, planets, description}``."""
    graha_data = graha_data or _load_graha_data()
    planet_meta = graha_data["planets"]
    sign_lords = _sign_lord_map(graha_data)
    exalted_in = _exalted_in_map(planet_meta)
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
    if "Surya" in planets and "Budh" in planets:
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
    if "Chandra" in planets and "Mangal" in planets:
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
    if "Chandra" in planets:
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
    kendra_lords = {houses[str(h)]["lord"] for h in KENDRAS if str(h) in houses}
    trikona_lords = {houses[str(h)]["lord"] for h in TRIKONAS if str(h) in houses}
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

    yogas.extend(_detect_neechabhanga(planets, planet_meta, sign_lords, exalted_in))
    yogas.extend(_detect_vipreet(planets, houses, planet_meta))
    yogas.extend(_detect_kaal_sarp(planets))
    yogas.extend(_detect_parivartana(planets, sign_lords))

    return yogas
