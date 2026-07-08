from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from kundali_calculator import BirthInput, calculate_kundali  # noqa: E402


# Neutral sample birth: 26/12/2019 09:15 IST, Delhi — the annular-eclipse
# morning with a six-graha stellium in Dhanu. Golden values cross-checked
# against DrikPanchang for 26 Dec 2019, New Delhi (Makara udaya lagna
# 08:36–10:19; Mula nakshatra upto 16:51; Dhanu rashi).
SAMPLE_BIRTH = BirthInput(
    dob="26/12/2019",
    tob="09:15",
    place="Delhi",
    lat=28.6139,
    lon=77.2090,
    timezone_name="Asia/Kolkata",
)


def test_sample_reference_chart_matches_brief():
    chart = calculate_kundali(SAMPLE_BIRTH)

    assert chart["lagna"] == "Makara"
    assert chart["rashi"] == "Dhanu"
    assert chart["nakshatra"] == "Mula"
    assert chart["nakshatra_pada"] == 3
    assert chart["planets"]["Chandra"]["sign"] == "Dhanu"
    assert chart["planets"]["Chandra"]["house"] == 12
    assert chart["dasha_seed"]["nakshatra_lord"] == "Ketu"


def test_kundali_contains_all_core_planets_and_whole_sign_houses():
    chart = calculate_kundali(SAMPLE_BIRTH)

    assert set(chart["planets"]) == {
        "Surya",
        "Chandra",
        "Mangal",
        "Budh",
        "Guru",
        "Shukra",
        "Shani",
        "Rahu",
        "Ketu",
    }
    assert set(chart["houses"]) == {str(index) for index in range(1, 13)}
    assert chart["houses"]["1"]["sign"] == "Makara"
    assert "Chandra" in chart["houses"]["12"]["planets"]
    assert chart["planets"]["Rahu"]["retrograde"] is True


def test_kundali_includes_navamsa_d9_chart():
    chart = calculate_kundali(SAMPLE_BIRTH)
    nav = chart["navamsa"]

    # Hand-verified with the classical counting rule: Makara (chara) lagna at
    # 10°27' is its 4th navamsa, counted from itself -> Mesha; Moon and Sun in
    # Mula pada 3 (Dhanu, dvisvabhava) count from the 5th sign -> Mithuna.
    assert nav["lagna"] == "Mesha"
    assert nav["planets"]["Chandra"]["sign"] == "Mithuna"
    assert nav["planets"]["Surya"]["sign"] == "Mithuna"
    assert set(nav["planets"]) == set(chart["planets"])
    assert set(nav["houses"]) == {str(index) for index in range(1, 13)}
    for info in nav["planets"].values():
        assert 1 <= info["house"] <= 12


def test_kundali_cli_outputs_json():
    script = SCRIPT_DIR / "kundali_calculator.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--dob",
            "26/12/2019",
            "--tob",
            "09:15",
            "--place",
            "Delhi",
            "--lat",
            "28.6139",
            "--lon",
            "77.2090",
            "--timezone",
            "Asia/Kolkata",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    chart = json.loads(completed.stdout)
    assert chart["lagna"] == "Makara"
    assert chart["nakshatra"] == "Mula"


def _seventh_from(house: int, offset: int) -> int:
    return ((house - 1 + offset - 1) % 12) + 1


def test_kundali_includes_graha_aspects():
    chart = calculate_kundali(SAMPLE_BIRTH)
    aspects = chart["aspects"]

    assert set(aspects) == set(chart["planets"])

    # Every graha casts a full aspect on its 7th house.
    for name, info in chart["planets"].items():
        assert _seventh_from(info["house"], 7) in aspects[name]["aspects_houses"]

    # Special aspects: Mars 4/8, Jupiter 5/9, Saturn 3/10.
    mars_h = chart["planets"]["Mangal"]["house"]
    assert {_seventh_from(mars_h, 4), _seventh_from(mars_h, 8)} <= set(aspects["Mangal"]["aspects_houses"])
    guru_h = chart["planets"]["Guru"]["house"]
    assert {_seventh_from(guru_h, 5), _seventh_from(guru_h, 9)} <= set(aspects["Guru"]["aspects_houses"])
    shani_h = chart["planets"]["Shani"]["house"]
    assert {_seventh_from(shani_h, 3), _seventh_from(shani_h, 10)} <= set(aspects["Shani"]["aspects_houses"])

    # Symmetry: if X aspects Y, then Y is aspected_by X.
    for x, ax in aspects.items():
        for y in ax["aspects_planets"]:
            assert x in aspects[y]["aspected_by"]


def test_kundali_includes_divisional_charts():
    chart = calculate_kundali(SAMPLE_BIRTH)
    vargas = chart["divisional_charts"]

    assert set(vargas) == {"D2", "D3", "D7", "D10", "D12"}
    bodies = set(chart["planets"]) | {"Lagna"}
    valid_signs = {s["name"] for s in [
        {"name": n} for n in (
            "Mesha Vrishabha Mithuna Karka Simha Kanya Tula Vrischika Dhanu Makara Kumbha Meena".split()
        )
    ]}
    for varga in vargas.values():
        assert set(varga) == bodies
        assert all(sign in valid_signs for sign in varga.values())


def test_kundali_includes_ashtakavarga():
    chart = calculate_kundali(SAMPLE_BIRTH)
    av = chart["ashtakavarga"]

    assert av["sarva_total"] == 337
    assert sum(av["sarva"]) == 337
    assert len(av["sarva"]) == 12
    assert av["bhinna_totals"]["Guru"] == 56  # Jupiter's fixed bhinna total
    assert set(av["bhinna"]) == {"Surya", "Chandra", "Mangal", "Budh", "Guru", "Shukra", "Shani"}
