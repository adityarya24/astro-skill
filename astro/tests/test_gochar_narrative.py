"""T6: antardasha-window gochar narrative (rule-based, no network)."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from dasha_calculator import calculate_dasha  # noqa: E402
from gochar_narrative import (  # noqa: E402
    build_antardasha_gochar_narrative,
    find_antardasha_window,
    sample_dates_for_window,
)
from kundali_calculator import BirthInput, calculate_kundali  # noqa: E402

# Privacy: neutral sample chart only.
SAMPLE = BirthInput(
    dob="26/12/2019",
    tob="09:15",
    place="Delhi",
    lat=28.6139,
    lon=77.2090,
    timezone_name="Asia/Kolkata",
)
ON = date(2026, 5, 20)


def _chart() -> dict:
    return calculate_kundali(SAMPLE)


def _dasha(chart: dict | None = None) -> dict:
    return calculate_dasha(chart or _chart(), on_date=ON)


def test_find_antardasha_window_has_start_and_end():
    dasha = _dasha()
    window = find_antardasha_window(dasha, ON)
    assert window is not None
    assert window["mahadasha"] == "Shukra"
    assert window["antardasha"] == "Surya"
    assert window["start"] < window["end"]
    assert window["start"] <= ON < window["end"]
    # Surya antardasha in this chart is ~1 year.
    assert (window["end"] - window["start"]).days > 300


def test_sample_dates_monthly_for_short_window():
    start = date(2025, 7, 2)
    end = date(2026, 7, 2)
    cadence, dates = sample_dates_for_window(start, end)
    assert cadence == "monthly"
    assert dates[0] == start
    assert all(d < end for d in dates)
    # ~12 month-starts + window open
    assert 10 <= len(dates) <= 14


def test_sample_dates_quarterly_for_long_window():
    start = date(2020, 1, 1)
    end = date(2025, 1, 1)  # 5 years
    cadence, dates = sample_dates_for_window(start, end)
    assert cadence == "quarterly"
    assert len(dates) <= 24
    assert dates[0] == start


def test_narrative_includes_shani_guru_rahu_one_liners():
    chart = _chart()
    dasha = _dasha(chart)
    narrative = build_antardasha_gochar_narrative(chart, dasha, on_date=ON, language="en")
    assert narrative is not None
    assert narrative["window"]["mahadasha"] == "Shukra"
    assert narrative["window"]["antardasha"] == "Surya"
    assert narrative["cadence"] == "monthly"
    assert narrative["sample_count"] == len(narrative["samples"])
    assert narrative["sample_count"] >= 10

    planets_seen: set[str] = set()
    for sample in narrative["samples"]:
        assert sample["date"]
        names = {h["planet"] for h in sample["highlights"]}
        assert names == {"Shani", "Guru", "Rahu"}
        planets_seen |= names
        for h in sample["highlights"]:
            assert 1 <= h["house_from_moon"] <= 12
            assert h["sign"]
            assert h["line"]
            assert h["line_en"]
            assert h["line_hi"]
            # One-liner must cite house or classical keyword — not empty filler.
            assert len(h["line"]) > 20

    assert planets_seen == {"Shani", "Guru", "Rahu"}
    assert "Shukra" in narrative["summary"]
    assert "Surya" in narrative["summary"]
    # Reference chart is in kantaka dhaiya through this window.
    assert "dhaiya" in narrative["summary"].lower() or "ढैया" in narrative["summary"]


def test_narrative_hindi_language_routing():
    chart = _chart()
    narrative = build_antardasha_gochar_narrative(chart, _dasha(chart), on_date=ON, language="hi")
    assert narrative is not None
    assert "अंतर्दशा" in narrative["summary"] or "अंतर्दशा" in narrative["summary_hi"]
    # At least one Devanagari highlight line
    first = narrative["samples"][0]["highlights"][0]
    assert first["line"] == first["line_hi"]
    assert any("\u0900" <= ch <= "\u097f" for ch in first["line"])


def test_synthesis_facts_are_position_only():
    chart = _chart()
    narrative = build_antardasha_gochar_narrative(chart, _dasha(chart), on_date=ON, language="en")
    facts = narrative["synthesis_facts"]
    assert facts["window"]["antardasha"] == "Surya"
    assert facts["cadence"] == "monthly"
    point = facts["points"][0]
    assert "date" in point
    assert set(point["planets"]) == {"Shani", "Guru", "Rahu"}
    # No free-prose blobs inside facts — only structured positions.
    blob = json.dumps(facts)
    assert "prioritise health" not in blob.lower()


def test_missing_dasha_returns_none():
    assert build_antardasha_gochar_narrative(_chart(), {}, on_date=ON) is None
    assert find_antardasha_window({}, ON) is None


def test_privacy_strings_absent_from_module_and_data():
    root = Path(__file__).resolve().parents[1]
    banned = ("Divyam", "Maru", "Villow")
    for path in (
        root / "scripts" / "gochar_narrative.py",
        root / "data" / "gochar_narrative_data.json",
    ):
        text = path.read_text(encoding="utf-8")
        for name in banned:
            assert name not in text


def test_report_opt_in_gochar_narrative():
    from report_generator import build_basic_report, build_text_report

    chart = _chart()
    dasha = _dasha(chart)
    bare = build_basic_report(chart, dasha=dasha, language="en")
    assert "gochar_narrative" not in bare["sections"]

    full = build_basic_report(
        chart,
        dasha=dasha,
        language="en",
        include_gochar_narrative=True,
        on_date=ON,
    )
    narr = full["sections"]["gochar_narrative"]
    assert narr is not None
    assert narr["sample_count"] >= 1
    text = build_text_report(full)
    assert "Gochar narrative:" in text


def test_cli_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    from gochar_narrative import main

    chart = _chart()
    dasha = _dasha(chart)
    k_path = tmp_path / "k.json"
    d_path = tmp_path / "d.json"
    k_path.write_text(json.dumps(chart), encoding="utf-8")
    d_path.write_text(json.dumps(dasha), encoding="utf-8")

    rc = main(
        [
            "--kundali-json",
            str(k_path),
            "--dasha-json",
            str(d_path),
            "--date",
            "2026-05-20",
            "--language",
            "en",
            "--json",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["sample_count"] >= 1
    assert payload["samples"][0]["highlights"]
