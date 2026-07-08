from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from avakahada import compute_avakahada  # noqa: E402
from html_pdf_report import _chandra_houses  # noqa: E402
from kundali_calculator import BirthInput, calculate_kundali  # noqa: E402


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


def test_avakahada_matches_traditional_tables_for_reference_chart():
    # Ground truth: classical nakshatra/rashi correspondences for Mula pada 3,
    # Dhanu rashi, Makara lagna, Moon in house 12 — cross-checked against the
    # DrikPanchang tables for Mula (Rakshasa gana, dog yoni, Adi nadi) and the
    # rashi tables for Dhanu (Kshatriya varna). Namakshar: Mula pada 3 = भा.
    ava = compute_avakahada(reference_chart())
    assert ava["gan"] == "राक्षस"
    assert ava["yoni"] == "श्वान"
    assert ava["nadi"] == "आदि"
    assert ava["varna"] == "क्षत्रिय"
    assert ava["vashya"] == "चतुष्पाद"
    assert ava["namakshar"] == "भा"
    assert ava["paya"] == "लौह"  # Moon in the 12th from lagna -> loha paya
    assert ava["lagna_lord_hi"] == "शनि"
    assert ava["rashi_lord_hi"] == "गुरु"
    assert ava["nakshatra_lord_hi"] == "केतु"


def test_avakahada_ishta_and_dinamaan_from_sunrise_sunset():
    # Sunrise/sunset for 26 Dec 2019, Delhi per DrikPanchang: 07:12 / 17:31.
    ava = compute_avakahada(
        reference_chart(),
        sunrise="2019-12-26T07:12:00+05:30",
        sunset="2019-12-26T17:31:00+05:30",
    )
    # 09:15 - 07:12 = 2h03m -> 5 ghati 7.5 pala; dinamaan 10:19:00.
    assert ava["ishta_ghati"].startswith("05:07")
    assert ava["dinamaan"] == "10:19:00"


def test_chandra_houses_count_from_moon_sign():
    kundali = {
        "planets": {
            "Chandra": {"sign": "Dhanu"},
            "Surya": {"sign": "Dhanu"},
            "Shani": {"sign": "Makara"},
            "Mangal": {"sign": "Vrischika"},
        }
    }
    houses = _chandra_houses(kundali)
    assert houses["1"]["sign"] == "Dhanu"
    assert set(houses["1"]["planets"]) == {"Chandra", "Surya"}
    assert houses["2"] == {"sign": "Makara", "planets": ["Shani"]}
    assert houses["12"] == {"sign": "Vrischika", "planets": ["Mangal"]}
    assert len(houses) == 12
