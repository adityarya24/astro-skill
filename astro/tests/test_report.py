from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from dasha_calculator import calculate_dasha  # noqa: E402
from kundali_calculator import BirthInput, calculate_kundali  # noqa: E402
from panchang_calculator import PanchangInput, calculate_panchang  # noqa: E402
from report_generator import build_basic_report  # noqa: E402
from yoga_detector import detect_yogas  # noqa: E402

# T1/T2 fixture chart (privacy: SAMPLE_B only — no personal names in this file).
SAMPLE_B = BirthInput(
    dob="07/03/2000",
    tob="03:20",
    place="Udaipur",
    lat=24.571,
    lon=73.691,
    timezone_name="Asia/Kolkata",
)

HOUSE_REQUIRED_KEYS = {
    "house",
    "sign",
    "lord",
    "lord_placement",
    "planets",
    "aspects_received",
    "karakas",
}
LORD_PLACEMENT_KEYS = {"house", "sign", "strength_verdict"}
T1_PLANET_FLAGS = {
    "vargottama",
    "combust",
    "graha_yuddha",
    "digbala",
    "functional_nature",
    "dignity",
    "strength_verdict",
}


def reference_chart() -> dict:
    return calculate_kundali(
        BirthInput(
            dob="26/12/2019",
            tob="09:15",
            place="Delhi",
            lat=28.6139,
            lon=77.2090,
            timezone_name="Asia/Kolkata",
        )
    )


def reference_panchang() -> dict:
    return calculate_panchang(
        PanchangInput(
            date="2026-05-21",
            place="Delhi",
            lat=28.6139,
            lon=77.209,
            timezone_name="Asia/Kolkata",
        )
    )


def test_basic_report_summarizes_kundali_dasha_and_panchang():
    chart = reference_chart()
    dasha = calculate_dasha(chart, on_date=date(2026, 5, 20))
    panchang = reference_panchang()

    report = build_basic_report(chart, dasha=dasha, panchang=panchang, language="hin")

    assert set(report) == {"language", "title", "sections", "notes"}
    assert report["title"] == "Basic Astrology Draft"
    assert report["sections"]["birth_chart"]["lagna"] == "Makara"
    assert report["sections"]["birth_chart"]["rashi"] == "Dhanu"
    assert report["sections"]["birth_chart"]["nakshatra"] == "Mula pada 3"
    assert report["sections"]["current_dasha"]["period"] == "Shukra/Surya/Shukra"
    assert report["sections"]["daily_panchang"]["vara"] == "Guruvara"
    # hin report carries Devanagari safety notes
    assert "ज्योतिषी" in report["notes"][0]
    assert len(report["notes"]) == 2
    # en report keeps the English safety notes
    en_report = build_basic_report(chart, dasha=dasha, panchang=panchang, language="en")
    assert "astrologer" in en_report["notes"][0].lower()
    assert "judgement" in en_report["notes"][0].lower()


def test_basic_report_works_without_optional_sections():
    report = build_basic_report(reference_chart(), language="en")

    assert report["sections"]["current_dasha"] is None
    assert report["sections"]["daily_panchang"] is None
    assert report["sections"]["birth_chart"]["doshas"] == []


def test_report_cli_outputs_json(tmp_path: Path):
    chart = reference_chart()
    dasha = calculate_dasha(chart, on_date=date(2026, 5, 20))
    panchang = reference_panchang()
    chart_path = tmp_path / "chart.json"
    dasha_path = tmp_path / "dasha.json"
    panchang_path = tmp_path / "panchang.json"
    chart_path.write_text(json.dumps(chart), encoding="utf-8")
    dasha_path.write_text(json.dumps(dasha), encoding="utf-8")
    panchang_path.write_text(json.dumps(panchang), encoding="utf-8")
    script = SCRIPT_DIR / "report_generator.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--kundali-json",
            str(chart_path),
            "--dasha-json",
            str(dasha_path),
            "--panchang-json",
            str(panchang_path),
            "--language",
            "hin",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    report = json.loads(completed.stdout)
    assert report["sections"]["current_dasha"]["period"] == "Shukra/Surya/Shukra"
    assert report["sections"]["daily_panchang"]["tithi"]


def test_sample_b_report_schema_surfaces_full_computed_data():
    """Report JSON exposes all 12 houses, yogas, ashtakavarga, and T1 planet flags."""
    chart = calculate_kundali(SAMPLE_B)
    report = build_basic_report(chart, language="en")
    birth = report["sections"]["birth_chart"]

    # --- houses: all 12 with required keys ---
    houses = birth["houses"]
    assert len(houses) == 12
    assert [h["house"] for h in houses] == list(range(1, 13))
    for h in houses:
        assert HOUSE_REQUIRED_KEYS <= set(h)
        assert LORD_PLACEMENT_KEYS <= set(h["lord_placement"])
        assert isinstance(h["planets"], list)
        assert isinstance(h["aspects_received"], list)
        for asp in h["aspects_received"]:
            assert set(asp) == {"from", "type"}
        assert isinstance(h["karakas"], list) and len(h["karakas"]) >= 1

    # SAMPLE_B: house 4 is Meena with Chandra+Mangal; lord Guru sits in H5 Mesha.
    h4 = houses[3]
    assert h4["house"] == 4
    assert h4["sign"] == "Meena"
    assert h4["lord"] == "Guru"
    assert set(h4["planets"]) >= {"Chandra", "Mangal"}
    assert h4["lord_placement"]["house"] == 5
    assert h4["lord_placement"]["sign"] == "Mesha"
    assert isinstance(h4["lord_placement"]["strength_verdict"], str)
    assert h4["lord_placement"]["strength_verdict"]

    # --- yogas: full detector objects when the chart has any ---
    detected = detect_yogas(chart["planets"], chart["houses"])
    if detected:
        assert birth["yogas"], "chart has yogas; report must surface them"
        assert isinstance(birth["yogas"], list)
        for yoga in birth["yogas"]:
            assert isinstance(yoga, dict)
            assert {"name", "type", "planets", "description"} <= set(yoga)
        assert birth["yogas"] == chart["yogas"]
    # yoga_names kept for string-only consumers (PDF join path)
    assert isinstance(birth["yoga_names"], list)
    assert all(isinstance(n, str) for n in birth["yoga_names"])

    # --- ashtakavarga: Bhinna + Sarva; Sarva always sums to 337 ---
    av = birth["ashtakavarga"]
    assert av is not None
    assert "bhinna" in av and "bhinna_totals" in av
    assert "sarva" in av and "sarva_total" in av
    assert av["sarva_total"] == 337
    assert sum(av["sarva"]) == 337

    # --- T1 planet flags pass through untouched ---
    assert "planets" in birth
    for name, info in chart["planets"].items():
        assert name in birth["planets"]
        for flag in T1_PLANET_FLAGS:
            assert flag in birth["planets"][name]
            assert birth["planets"][name][flag] == info[flag]
    if "mangalik" in chart:
        assert birth["mangalik"] == chart["mangalik"]

    # Backward-compatible key_houses still present (subset of 1/5/7/9/10).
    assert "key_houses" in birth
    assert set(birth["key_houses"]) <= {"1", "5", "7", "9", "10"}
