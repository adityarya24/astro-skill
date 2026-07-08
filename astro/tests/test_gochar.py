"""Gochar (transits) + Saturn Sade Sati / Dhaiya. Uses the ephemeris."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from gochar_calculator import calculate_gochar  # noqa: E402
from kundali_calculator import (  # noqa: E402
    DATA_DIR,
    BirthInput,
    calculate_kundali,
    load_json,
    sign_index,
)

REF = BirthInput(
    dob="26/12/2019", tob="09:15", place="Delhi",
    lat=28.6139, lon=77.2090, timezone_name="Asia/Kolkata",
)
ON_DATE = date(2026, 7, 1)
PLANETS = {"Surya", "Chandra", "Mangal", "Budh", "Guru", "Shukra", "Shani", "Rahu", "Ketu"}


def _gochar() -> dict:
    return calculate_gochar(calculate_kundali(REF), on_date=ON_DATE)


def test_transit_table_has_all_grahas_and_house_ranges():
    g = _gochar()
    assert set(g["transits"]) == PLANETS
    for t in g["transits"].values():
        assert 1 <= t["house_from_moon"] <= 12
        assert 1 <= t["house_from_lagna"] <= 12
        assert isinstance(t["retrograde"], bool)
        assert "sign" in t and "degree" in t


def test_house_from_moon_matches_transit_sign():
    g = _gochar()
    signs = load_json(DATA_DIR / "graha_data.json")["signs"]
    name_to_idx = {s["name"]: s["index"] for s in signs}
    chart = calculate_kundali(REF)
    moon_idx = sign_index(chart["planets"]["Chandra"]["longitude"])
    for t in g["transits"].values():
        expected = ((name_to_idx[t["sign"]] - moon_idx) % 12) + 1
        assert t["house_from_moon"] == expected


def test_saturn_analysis_status_is_valid():
    sa = _gochar()["saturn_analysis"]
    assert sa["status"] in {"sade_sati", "dhaiya", "none"}
    if sa["status"] == "sade_sati":
        assert sa["phase"] in {"rising", "peak", "setting"}
        assert sa["sign_start"] and sa["sign_end"]
    if sa["status"] == "dhaiya":
        assert sa["type"] in {"kantaka", "ashtama"}


def test_reference_chart_is_kantaka_dhaiya_on_2026_07_01():
    # Dhanu (Sagittarius) Moon; Saturn transits sidereal Pisces (Meena)
    # 2025-2027, i.e. the 4th from Moon = kantaka dhaiya. Hand-verified against
    # the real Saturn ingress into sidereal Pisces (late March 2025); Saturn is
    # at Meena ~20 deg on 2026-07-01 per an independent ephemeris check.
    sa = _gochar()["saturn_analysis"]
    assert sa["sign"] == "Meena"
    assert sa["house_from_moon"] == 4
    assert sa["status"] == "dhaiya"
    assert sa["type"] == "kantaka"
    assert sa["sign_start"] == "2025-03-29"
    assert sa["sign_end"] == "2027-06-02"
