"""Transparent heuristic ratings derived only from computed chart factors.

The helpers return canonical data (including ``Strong``/``Mixed``/``Weak``
bands); presentation code is responsible for translating those labels.

Benefic yogas (see :data:`BENEFIC_YOGA_TYPES`) add up to
:data:`MAX_YOGA_BONUS` points to a house's composite index when a
participating planet is that house's lord, an occupant, or an aspecting
planet — so a yoga-rich chart is no longer under-rated. Doshas/afflictions
never contribute. The star bands themselves (:func:`_stars_for_index`,
:func:`_band_for_stars`) are unchanged; a house can simply reach a higher,
legitimately-earned index now.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from math import floor
from typing import Any


LIFE_AREA_HOUSES: dict[str, tuple[int, ...]] = {
    "career": (10,),
    "marriage": (7,),
    "finance": (2, 11),
    "health": (6, 8, 1),
    "education": (5,),
    "spiritual": (9, 12),
}

# Yoga ``type`` strings (see ``yoga_detector.py``) that represent a benefic,
# fortune-building combination. Mirrors the classification already used for
# display purposes (``html_pdf_report._BENEFIC_YOGA_TYPES``) plus a couple of
# forward-looking type strings ("dhana", "benefic") the detector doesn't emit
# yet but the report schema documents as valid. Doshas/afflictions (Kaal Sarp,
# Kemadruma, dainya-parivartana, Mangalik, ...) are deliberately excluded.
BENEFIC_YOGA_TYPES: frozenset[str] = frozenset(
    {
        "raja",
        "raja-like",
        "vipreet-raja",
        "dhana",
        "benefic",
        "mahapurusha",
        "intellect",
        "wealth-effort",
        "maha",
    }
)

# A house's composite index can gain at most this many points from benefic
# yogas, however many qualify, so a yoga-rich chart cannot runaway-inflate.
MAX_YOGA_BONUS = 2


def _strength_points(verdict: object) -> int:
    normalized = str(verdict or "").strip().lower()
    if normalized.startswith("strong"):
        return 2
    if normalized.startswith(("moderate", "average")):
        return 1
    return 0


def _planet_nature(planets: Mapping[str, Mapping[str, Any]], name: str) -> str:
    return str(planets.get(name, {}).get("functional_nature", "")).strip().lower()


def _stars_for_index(index: int) -> int:
    # Fixed bands: <=0 -> 1 star; 1 -> 2; 2 -> 3; 3 -> 4; >=4 -> 5.
    return max(1, min(5, index + 1))


def _band_for_stars(stars: int) -> str:
    # Fixed display bands: 1-2 stars Weak; 3 stars Mixed; 4-5 stars Strong.
    if stars >= 4:
        return "Strong"
    if stars == 3:
        return "Mixed"
    return "Weak"


def _active_dasha_lords(dasha: Mapping[str, Any] | str | None) -> set[str]:
    """Extract only the active mahadasha and antardasha lords."""
    if not dasha:
        return set()
    if isinstance(dasha, str):
        return {part.strip() for part in dasha.split("/")[:2] if part.strip()}

    current = dasha.get("current")
    if isinstance(current, Mapping):
        return {
            str(current[key]).strip()
            for key in ("mahadasha", "antardasha")
            if current.get(key)
        }

    period = dasha.get("period")
    return _active_dasha_lords(str(period)) if period else set()


def _benefic_yoga_support(
    house: Mapping[str, Any], yogas: Iterable[Mapping[str, Any]]
) -> list[str]:
    """Names of benefic yogas connected to this house.

    A yoga counts when one of its participating planets is the house lord,
    an occupant of the house, or a planet aspecting the house — and the
    yoga's ``type`` is in :data:`BENEFIC_YOGA_TYPES` (doshas/afflictions
    never contribute).
    """
    lord = str(house.get("lord") or "")
    relevant = {str(name) for name in house.get("planets") or ()}
    relevant.update(
        str(aspect.get("from"))
        for aspect in house.get("aspects_received") or ()
        if aspect.get("from")
    )
    if lord:
        relevant.add(lord)

    names: list[str] = []
    for yoga in yogas or ():
        if not isinstance(yoga, Mapping):
            continue
        yoga_type = str(yoga.get("type") or "").strip().lower()
        if yoga_type not in BENEFIC_YOGA_TYPES:
            continue
        participants = {str(p) for p in yoga.get("planets") or ()}
        if participants & relevant:
            names.append(str(yoga.get("name") or yoga_type))
    return names


def score_house(
    house: Mapping[str, Any],
    planets: Mapping[str, Mapping[str, Any]],
    active_dasha_lords: Iterable[str] = (),
    yogas: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Score one report-schema house and expose every contributing factor."""
    lord = str(house.get("lord") or "")
    lord_placement = house.get("lord_placement") or {}
    strength = str(lord_placement.get("strength_verdict") or "")
    strength_points = _strength_points(strength)

    occupants = [str(name) for name in house.get("planets") or ()]
    benefic_occupants = [
        name for name in occupants if _planet_nature(planets, name) == "benefic"
    ]
    malefic_occupants = [
        name for name in occupants if _planet_nature(planets, name) == "malefic"
    ]
    benefic_aspects = [
        str(aspect.get("from"))
        for aspect in house.get("aspects_received") or ()
        if aspect.get("from")
        and _planet_nature(planets, str(aspect.get("from"))) == "benefic"
    ]
    dasha_activated = bool(lord and lord in set(active_dasha_lords))
    benefic_yoga_support = _benefic_yoga_support(house, yogas)
    yoga_bonus = min(len(benefic_yoga_support), MAX_YOGA_BONUS)

    composite_index = (
        strength_points
        + len(benefic_occupants)
        + len(benefic_aspects)
        - len(malefic_occupants)
        + int(dasha_activated)
        + yoga_bonus
    )
    stars = _stars_for_index(composite_index)
    return {
        "house": int(house["house"]),
        "composite_index": composite_index,
        "stars": stars,
        "rating": "★" * stars,
        "band": _band_for_stars(stars),
        "factors": {
            "house_lord": lord,
            "lord_strength": strength,
            "lord_strength_points": strength_points,
            "benefic_occupants": benefic_occupants,
            "benefic_aspects": benefic_aspects,
            "malefic_occupants": malefic_occupants,
            "dasha_activated": dasha_activated,
            "benefic_yoga_support": benefic_yoga_support,
        },
    }


def score_houses(
    houses: Sequence[Mapping[str, Any]],
    planets: Mapping[str, Mapping[str, Any]],
    dasha: Mapping[str, Any] | str | None = None,
    yogas: Iterable[Mapping[str, Any]] = (),
) -> dict[int, dict[str, Any]]:
    """Score every supplied house, keyed by its integer house number."""
    active_lords = _active_dasha_lords(dasha)
    return {
        int(house["house"]): score_house(house, planets, active_lords, yogas)
        for house in houses
    }


def score_life_areas(
    house_scores: Mapping[int, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Map house ratings to life areas using a deterministic half-up mean."""
    areas: dict[str, dict[str, Any]] = {}
    for area, house_numbers in LIFE_AREA_HOUSES.items():
        selected = [house_scores[number] for number in house_numbers if number in house_scores]
        if not selected:
            continue
        stars = floor(sum(int(item["stars"]) for item in selected) / len(selected) + 0.5)
        areas[area] = {
            "area": area,
            "houses": list(house_numbers),
            "stars": stars,
            "rating": "★" * stars,
            "band": _band_for_stars(stars),
            "drivers": [
                {
                    "house": int(item["house"]),
                    "house_lord": item["factors"]["house_lord"],
                    "lord_strength": item["factors"]["lord_strength"],
                    "dasha_activated": item["factors"]["dasha_activated"],
                    "benefic_yoga_support": item["factors"]["benefic_yoga_support"],
                }
                for item in selected
            ],
        }
    return areas


def score_report(
    report: Mapping[str, Any],
    dasha: Mapping[str, Any] | str | None = None,
    yogas: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Score the existing ``build_basic_report`` schema without mutating it.

    ``yogas`` defaults to ``birth_chart["yogas"]`` (the report schema's own
    yoga list) so callers that already have that list on hand — e.g. the PDF
    renderer, which also uses it to render the Yogas section — can pass it
    through explicitly instead of it being re-derived.
    """
    sections = report.get("sections") or {}
    birth_chart = sections.get("birth_chart") or {}
    current_dasha = dasha if dasha is not None else sections.get("current_dasha")
    house_yogas = yogas if yogas is not None else (birth_chart.get("yogas") or ())
    houses = score_houses(
        birth_chart.get("houses") or (),
        birth_chart.get("planets") or {},
        current_dasha,
        house_yogas,
    )
    return {"houses": houses, "areas": score_life_areas(houses)}
