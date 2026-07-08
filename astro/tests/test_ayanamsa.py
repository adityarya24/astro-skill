"""Selectable ayanamsa (Lahiri default, plus Raman/KP/etc.). Uses the ephemeris."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from kundali_calculator import BirthInput, calculate_kundali  # noqa: E402
from panchang_calculator import PanchangInput, calculate_panchang  # noqa: E402


def _birth(ayanamsa: str) -> BirthInput:
    return BirthInput("26/12/2019", "09:15", "Delhi", 28.6139, 77.2090, "Asia/Kolkata", ayanamsa=ayanamsa)


def test_raman_ayanamsa_supported_and_differs_from_lahiri():
    lahiri = calculate_kundali(_birth("lahiri"))
    raman = calculate_kundali(_birth("raman"))

    assert raman["calculation"]["ayanamsa"] == "raman"
    # A different ayanamsa shifts the sidereal frame, so the ayanamsa value differs.
    assert raman["calculation"]["ayanamsa_degrees"] != lahiri["calculation"]["ayanamsa_degrees"]


def test_lahiri_stays_the_default():
    chart = calculate_kundali(_birth("lahiri"))
    assert chart["calculation"]["ayanamsa"] == "lahiri"
    assert chart["lagna"] == "Makara"  # unchanged golden behaviour


def test_unknown_ayanamsa_raises():
    with pytest.raises(ValueError):
        calculate_kundali(_birth("nonsense"))


def test_panchang_supports_kp_ayanamsa():
    panchang = calculate_panchang(
        PanchangInput("2026-05-21", "Delhi", 28.6139, 77.209, "Asia/Kolkata", ayanamsa="kp")
    )
    assert panchang["calculation"]["ayanamsa"] == "kp"
