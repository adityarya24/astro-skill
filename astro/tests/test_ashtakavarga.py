"""Ashtakavarga. Bindu totals are position-invariant, so the canonical sums
(Sun 48 ... Sarva 337) checksum the benefic tables. No ephemeris needed."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from ashtakavarga import compute_ashtakavarga  # noqa: E402

CANONICAL = {"Surya": 48, "Chandra": 49, "Mangal": 39, "Budh": 54, "Guru": 56, "Shukra": 52, "Shani": 39}


def _signs(a, b, c, d, e, f, g) -> dict:
    return {"Surya": a, "Chandra": b, "Mangal": c, "Budh": d, "Guru": e, "Shukra": f, "Shani": g}


def test_bhinna_totals_match_canonical_bphs_sums():
    result = compute_ashtakavarga(_signs(0, 3, 7, 2, 8, 6, 9), lagna_sign=0)
    assert result["bhinna_totals"] == CANONICAL
    for planet, bindus in result["bhinna"].items():
        assert len(bindus) == 12
        assert sum(bindus) == CANONICAL[planet]
        assert all(0 <= b <= 8 for b in bindus)


def test_sarva_is_337_and_equals_column_sums():
    result = compute_ashtakavarga(_signs(5, 1, 11, 4, 7, 9, 2), lagna_sign=3)
    assert result["sarva_total"] == 337
    assert sum(result["sarva"]) == 337
    for s in range(12):
        assert result["sarva"][s] == sum(result["bhinna"][p][s] for p in result["bhinna"])


def test_totals_are_position_invariant():
    a = compute_ashtakavarga(_signs(0, 0, 0, 0, 0, 0, 0), lagna_sign=0)
    b = compute_ashtakavarga(_signs(5, 8, 2, 11, 3, 6, 9), lagna_sign=4)
    assert a["bhinna_totals"] == b["bhinna_totals"] == CANONICAL
    assert a["sarva_total"] == b["sarva_total"] == 337
