"""Graha drishti (Parashari full aspects). Pure logic, no ephemeris."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from aspects import compute_aspects  # noqa: E402


def _planets() -> dict:
    # Synthetic placement to exercise every special aspect.
    return {
        "Mangal": {"house": 1},
        "Surya": {"house": 4},
        "Guru": {"house": 5},
        "Shani": {"house": 7},
    }


def test_special_aspect_houses_are_correct():
    asp = compute_aspects(_planets())

    assert asp["Mangal"]["aspects_houses"] == [4, 7, 8]   # Mars 4/7/8
    assert asp["Guru"]["aspects_houses"] == [1, 9, 11]    # Jupiter 5/7/9 from house 5
    assert asp["Shani"]["aspects_houses"] == [1, 4, 9]    # Saturn 3/7/10 from house 7
    assert asp["Surya"]["aspects_houses"] == [10]         # Sun only 7th


def test_aspected_planets_and_reverse_map():
    asp = compute_aspects(_planets())

    # Mars in H1 aspects H4 (Surya) and H7 (Shani).
    assert asp["Mangal"]["aspects_planets"] == ["Surya", "Shani"]
    # Who aspects Mars (H1)? Guru (aspects H1) and Shani (aspects H1).
    assert asp["Mangal"]["aspected_by"] == ["Guru", "Shani"]
    # Surya (H4) is aspected by Mangal (H4) and Shani (H4).
    assert asp["Surya"]["aspected_by"] == ["Mangal", "Shani"]
    # Guru (H5) is aspected by nobody here.
    assert asp["Guru"]["aspected_by"] == []


def test_planet_does_not_aspect_itself():
    asp = compute_aspects({"Shani": {"house": 1}, "Mangal": {"house": 1}})
    # Both in H1; Saturn aspects 3/7/10 -> houses 3,7,10, not its own H1.
    assert "Shani" not in asp["Shani"]["aspects_planets"]
    assert "Mangal" not in asp["Mangal"]["aspects_planets"]
