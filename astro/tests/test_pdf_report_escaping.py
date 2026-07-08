"""The ReportLab renderer must not choke on markup characters in free text.

Feeds a hand-built kundali dict straight into the ReportLab path, so it needs
no Swiss Ephemeris and no Chromium.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from pdf_report import build_pdf_report  # noqa: E402

PLANETS = ["Surya", "Chandra", "Mangal", "Budh", "Guru", "Shukra", "Shani", "Rahu", "Ketu"]
SIGNS = [
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrischika", "Dhanu", "Makara", "Kumbha", "Meena",
]


def _synthetic_kundali(place: str) -> dict:
    planets = {
        name: {
            "sign": "Mesha",
            "degree": 8.76,
            "longitude": 8.76,
            "house": 1,
            "nakshatra": "Bharani",
            "nakshatra_pada": 1,
            "retrograde": False,
        }
        for name in PLANETS
    }
    houses = {
        str(i + 1): {"sign": SIGNS[i], "lord": "Mangal", "planets": PLANETS if i == 0 else []}
        for i in range(12)
    }
    return {
        "input": {"place": place, "dob": "26/12/2019", "tob": "09:15"},
        "calculation": {"datetime_local": "2019-12-26T09:15:00+05:30"},
        "lagna": "Mesha",
        "rashi": "Mesha",
        "nakshatra": "Bharani",
        "nakshatra_pada": 1,
        "planets": planets,
        "houses": houses,
        "doshas": [],
    }


@pytest.mark.parametrize("place", ["Nagpur <MH>", "Tom & Jerry town", "A<B>C & D"])
def test_reportlab_renderer_survives_markup_chars_in_place(tmp_path: Path, place: str):
    output_path = tmp_path / "report.pdf"

    build_pdf_report(
        _synthetic_kundali(place),
        output_path=output_path,
        language="en",
        renderer="reportlab",
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 1_000
