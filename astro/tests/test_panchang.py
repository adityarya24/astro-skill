from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from panchang_calculator import PanchangInput, calculate_panchang  # noqa: E402


DELHI_DATE = PanchangInput(
    date="2026-05-21",
    place="Delhi",
    lat=28.6139,
    lon=77.209,
    timezone_name="Asia/Kolkata",
)


def assert_iso_or_warning(result: dict, field: str) -> None:
    value = result["panchang"][field]
    if value is None:
        assert any(field in warning for warning in result["warnings"])
        return
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None


def test_panchang_contains_core_daily_sections():
    result = calculate_panchang(DELHI_DATE)

    assert set(result) == {"input", "calculation", "sun", "moon", "panchang", "warnings"}
    assert result["input"]["place"] == "Delhi"
    assert result["panchang"]["vara"] == "Guruvara"
    assert result["calculation"]["ayanamsa"] == "lahiri"
    assert result["calculation"]["anchor"] == "sunrise"
    assert 0.0 <= result["sun"]["longitude"] < 360.0
    assert 0.0 <= result["moon"]["longitude"] < 360.0


def test_panchang_values_stay_in_valid_ranges():
    result = calculate_panchang(DELHI_DATE)
    panchang = result["panchang"]

    assert 1 <= panchang["tithi"]["number"] <= 30
    assert panchang["tithi"]["paksha"] in {"Shukla", "Krishna"}
    assert 1 <= panchang["nakshatra"]["pada"] <= 4
    assert 1 <= panchang["yoga"]["number"] <= 27
    assert panchang["karana"]["name"]
    assert_iso_or_warning(result, "sunrise")
    assert_iso_or_warning(result, "sunset")


def test_panchang_includes_muhurta_and_end_times():
    result = calculate_panchang(DELHI_DATE)
    panchang = result["panchang"]

    for element in ("tithi", "nakshatra", "yoga", "karana"):
        ends_at = panchang[element]["ends_at"]
        assert ends_at is not None
        assert datetime.fromisoformat(ends_at).tzinfo is not None

    muhurta = panchang["muhurta"]
    assert set(muhurta) == {"rahu_kaal", "yamaganda", "gulika", "abhijit", "brahma_muhurta"}
    for window in muhurta.values():
        start = datetime.fromisoformat(window["start"])
        end = datetime.fromisoformat(window["end"])
        assert start < end

    sunrise = datetime.fromisoformat(panchang["sunrise"])
    sunset = datetime.fromisoformat(panchang["sunset"])
    rahu_start = datetime.fromisoformat(muhurta["rahu_kaal"]["start"])
    rahu_end = datetime.fromisoformat(muhurta["rahu_kaal"]["end"])
    # Rahu Kaal sits inside the daytime and spans one eighth of it; Brahma
    # muhurta precedes sunrise; Abhijit straddles solar midday.
    assert sunrise <= rahu_start < rahu_end <= sunset
    eighth = (sunset - sunrise).total_seconds() / 8
    assert abs((rahu_end - rahu_start).total_seconds() - eighth) < 1.0
    assert datetime.fromisoformat(muhurta["brahma_muhurta"]["end"]) <= sunrise
    midday = sunrise + (sunset - sunrise) / 2
    abhijit_start = datetime.fromisoformat(muhurta["abhijit"]["start"])
    abhijit_end = datetime.fromisoformat(muhurta["abhijit"]["end"])
    assert abhijit_start <= midday <= abhijit_end


def test_panchang_cli_outputs_json():
    script = SCRIPT_DIR / "panchang_calculator.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--date",
            "2026-05-21",
            "--place",
            "Delhi",
            "--lat",
            "28.6139",
            "--lon",
            "77.209",
            "--timezone",
            "Asia/Kolkata",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = json.loads(completed.stdout)
    assert result["panchang"]["vara"] == "Guruvara"
    assert "tithi" in result["panchang"]
    assert "nakshatra" in result["panchang"]
    assert "yoga" in result["panchang"]
    assert "karana" in result["panchang"]
