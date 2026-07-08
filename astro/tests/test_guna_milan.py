"""Guna Milan (Ashtakoot). Kuta logic is pure (synthetic persons, no ephemeris);
one integration test uses the reference chart against itself."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from guna_milan import (  # noqa: E402
    bhakoot_points,
    calculate_compatibility,
    compatibility_from_persons,
    gana_points,
    graha_maitri_points,
    nadi_points,
    tara_points,
    varna_points,
    vashya_points,
    yoni_points,
)
from kundali_calculator import BirthInput, calculate_kundali  # noqa: E402

# Rashi index 0=Mesha..11=Meena ; nakshatra index 0=Ashwini..26=Revati.
MESHA, KARKA, KANYA = 0, 3, 5
ASHWINI, KRITTIKA, ARDRA = 0, 2, 5


def P(rashi: int, nak: int, pada: int = 1, manglik: bool = False) -> dict:
    return {"rashi_idx": rashi, "nak_idx": nak, "pada": pada, "manglik": manglik}


def test_identical_moon_maxes_every_kuta_except_nadi():
    b = P(MESHA, ASHWINI)
    assert varna_points(b, b) == 1
    assert vashya_points(b, b) == 2
    assert tara_points(b, b) == 3
    assert yoni_points(b, b) == 4
    assert graha_maitri_points(b, b) == 5
    assert gana_points(b, b) == 6
    assert bhakoot_points(b, b) == 7
    assert nadi_points(b, b) == 0  # same nadi -> Nadi dosha


def test_varna_respects_direction():
    # Fire (Mesha=3) bride, Water (Karka=4) groom -> groom rank >= bride -> 1.
    assert varna_points(P(MESHA, ASHWINI), P(KARKA, ASHWINI)) == 1
    # Reverse: Water bride (4), Fire groom (3) -> 3 >= 4 false -> 0.
    assert varna_points(P(KARKA, ASHWINI), P(MESHA, ASHWINI)) == 0


def test_bhakoot_dosha_for_6_8_axis():
    # Mesha (0) & Kanya (5): counts (6, 8) -> Bhakoot dosha -> 0.
    assert bhakoot_points(P(MESHA, ASHWINI), P(KANYA, ASHWINI)) == 0


def test_gana_deva_rakshasa_is_one():
    # Ashwini = Deva, Krittika = Rakshasa -> 1.
    assert gana_points(P(MESHA, ASHWINI), P(MESHA, KRITTIKA)) == 1


def test_nadi_same_vs_different():
    assert nadi_points(P(MESHA, ASHWINI), P(MESHA, ARDRA)) == 0    # both Aadi
    assert nadi_points(P(MESHA, ASHWINI), P(MESHA, KRITTIKA)) == 8  # Aadi vs Antya


def test_tara_mixed_direction_is_one_and_half():
    # Ashwini->Krittika count 3 (inauspicious); reverse count 26 -> rem 8 (ok).
    assert tara_points(P(MESHA, ASHWINI), P(MESHA, KRITTIKA)) == 1.5


def test_graha_maitri_friend_neutral_is_four():
    # Mesha lord Mangal (sees Chandra as friend); Karka lord Chandra (sees
    # Mangal as neutral) -> friend|neutral -> 4.
    assert graha_maitri_points(P(MESHA, ASHWINI), P(KARKA, ASHWINI)) == 4


def test_identical_persons_total_28_with_nadi_dosha():
    result = compatibility_from_persons(P(MESHA, ASHWINI), P(MESHA, ASHWINI))
    assert result["total"] == 28
    assert result["max"] == 36
    assert result["verdict"] == "good"
    assert result["doshas"]["nadi"]["present"] is True


def test_manglik_both_cancels_one_flags():
    both = compatibility_from_persons(P(MESHA, ASHWINI, manglik=True), P(KARKA, ASHWINI, manglik=True))
    assert both["doshas"]["manglik"]["present"] is False  # both manglik -> compatible
    one = compatibility_from_persons(P(MESHA, ASHWINI, manglik=True), P(KARKA, ASHWINI, manglik=False))
    assert one["doshas"]["manglik"]["present"] is True


def test_calculate_compatibility_on_reference_chart_against_itself():
    chart = calculate_kundali(
        BirthInput("26/12/2019", "09:15", "Delhi", 28.6139, 77.2090, "Asia/Kolkata")
    )
    result = calculate_compatibility(chart, chart)
    assert result["total"] == 28
    assert result["doshas"]["nadi"]["present"] is True
