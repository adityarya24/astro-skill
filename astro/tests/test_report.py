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
    )

    report = json.loads(completed.stdout)
    assert report["sections"]["current_dasha"]["period"] == "Shukra/Surya/Shukra"
    assert report["sections"]["daily_panchang"]["tithi"]
