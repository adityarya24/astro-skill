from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from kundali_calculator import BirthInput, calculate_kundali  # noqa: E402
from yoga_detector import detect_yogas  # noqa: E402


def reference_chart() -> dict:
    return calculate_kundali(
        BirthInput("26/12/2019", "09:15", "Delhi", 28.6139, 77.2090, "Asia/Kolkata")
    )


def test_reference_chart_yogas_are_detected():
    chart = reference_chart()
    names = {y["name"] for y in chart["yogas"]}
    # Geometry of this chart (Dhanu stellium): Jupiter conjunct the Moon (a
    # kendra from itself), Sun and Mercury together in Dhanu, and the 7th lord
    # Chandra conjunct the 9th lord Budh (kendra/trikona lords together).
    assert "Gajakesari" in names
    assert "Budhaditya" in names
    assert "Raja Yoga" in names


def test_gajakesari_cancels_kemadruma():
    names = {y["name"] for y in reference_chart()["yogas"]}
    # A planet in a kendra from the Moon is a Kemadruma-bhanga, so Gajakesari and
    # Kemadruma must never be reported together.
    assert not ({"Gajakesari", "Kemadruma"} <= names)


def test_every_yoga_has_contract_fields():
    for yoga in reference_chart()["yogas"]:
        assert set(yoga) >= {"name", "type", "planets", "description"}
        assert yoga["planets"]


def test_mahapurusha_detected_from_dignified_kendra_placement():
    # Saturn in its own sign Makara in a kendra (house 10) -> Sasa Mahapurusha.
    planets = {
        "Chandra": {"house": 1, "sign": "Mesha"},
        "Surya": {"house": 3, "sign": "Mithuna"},
        "Budh": {"house": 4, "sign": "Karka"},
        "Mangal": {"house": 6, "sign": "Kanya"},
        "Guru": {"house": 2, "sign": "Vrishabha"},
        "Shukra": {"house": 5, "sign": "Simha"},
        "Shani": {"house": 10, "sign": "Makara"},
    }
    houses = {str(h): {"lord": "Surya"} for h in range(1, 13)}
    yogas = detect_yogas(planets, houses)
    assert any(y["name"].startswith("Sasa") for y in yogas)
