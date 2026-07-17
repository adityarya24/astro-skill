"""T4: premium PDF analysis sections — HTML assertions (no Chromium)."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from dasha_calculator import calculate_dasha  # noqa: E402
from gochar_calculator import calculate_gochar  # noqa: E402
from html_pdf_report import (  # noqa: E402
    build_html,
    build_premium_sections_html,
)
from kundali_calculator import BirthInput, calculate_kundali  # noqa: E402

# Privacy: neutral fixture only — no personal names.
SAMPLE = BirthInput(
    dob="26/12/2019",
    tob="09:15",
    place="Delhi",
    lat=28.6139,
    lon=77.2090,
    timezone_name="Asia/Kolkata",
)


def _chart() -> dict:
    return calculate_kundali(SAMPLE)


def _dasha(chart: dict) -> dict:
    return calculate_dasha(chart, on_date=date(2026, 5, 20))


def _gochar(chart: dict) -> dict:
    return calculate_gochar(chart, on_date=date(2026, 5, 20))


def _synth() -> dict:
    return {
        "en": {
            "executive_summary": "Synthetic executive overview of planetary balance.",
            "bhava_analysis": {"1": "First house prose for tests."},
            "dasha_deep_dive": "Current dasha narrative for tests.",
            "life_areas": {
                "career": "Career growth window.",
                "relationships": "Steady partnerships.",
            },
            "remedies": [
                {
                    "planet": "Chandra",
                    "mantra": "Om Chandraya Namah",
                    "count": 11000,
                    "gemstone": "Pearl",
                    "fasting": "Monday",
                    "daan": "rice",
                    "ritual": "offer milk",
                }
            ],
        },
        "hi": {
            "executive_summary": "ग्रह संतुलन का सिंथेटिक सार।",
            "life_areas": {"करियर": "वृद्धि का समय।"},
            "dasha_deep_dive": "वर्तमान दशा का वर्णन।",
            "remedies": "चंद्र उपाय प्राथमिक।",
        },
    }


def _strength_row_count(html: str) -> int:
    match = re.search(
        r'class="planet-strength-table".*?<tbody>(.*?)</tbody>',
        html,
        flags=re.S,
    )
    assert match, "planet-strength-table tbody not found"
    return len(re.findall(r"<tr\b", match.group(1)))


EN_HEADINGS = [
    "Executive Summary",
    "Planetary Strength",
    "Twelve-House Analysis",
    "Dasha Deep-Dive",
    "Gochar Highlights",
    "Yogas",
    "Ashtakavarga",
    "Mangalik Dosha",
]

HI_HEADINGS = [
    "कार्यकारी सार",
    "ग्रह बल तालिका",
    "बारह भाव विश्लेषण",
    "दशा गहन विश्लेषण",
    "गोचर मुख्य बिंदु",
    "योग विवरण",
    "अष्टकवर्ग",
    "मांगलिक दोष",
]


def test_premium_sections_without_synthesis_do_not_crash():
    chart = _chart()
    dasha = _dasha(chart)
    gochar = _gochar(chart)

    html = build_html(
        chart,
        dasha=dasha,
        gochar=gochar,
        language="en",
        template="pandit_v1",
        client_name="Kiran Verma",
    )

    for heading in EN_HEADINGS:
        assert heading in html, f"missing heading: {heading}"
    # Life-area + synthesis-only remedies omit gracefully when synthesis absent
    # (remedies.json may still supply remedies — either way no crash).
    assert "Life-Area Forecasts" not in html
    assert "Gajakesari" in html or "Budhaditya" in html
    assert _strength_row_count(html) == 9
    # Sarva totals appear as numbers in the ashtakavarga block
    sarva = (chart.get("ashtakavarga") or {}).get("sarva") or []
    for total in sarva[:3]:
        assert str(total) in html
    for name in ("Divyam", "Maru", "Villow"):
        assert name not in html


def test_premium_sections_with_synthesis_include_prose():
    chart = _chart()
    dasha = _dasha(chart)
    gochar = _gochar(chart)
    synth = _synth()

    html = build_html(
        chart,
        dasha=dasha,
        gochar=gochar,
        language="en",
        template="pandit_v1",
        synthesis=synth,
    )

    for heading in EN_HEADINGS:
        assert heading in html
    assert "Life-Area Forecasts" in html
    assert "Synthetic executive overview" in html
    assert "Career growth window" in html
    assert "Current dasha narrative" in html
    assert "Remedies (Prioritised)" in html
    assert "Om Chandraya Namah" in html
    assert "First house prose" in html
    assert _strength_row_count(html) == 9


def test_premium_fragment_builder_hi_headings():
    chart = _chart()
    dasha = _dasha(chart)
    gochar = _gochar(chart)

    frag = build_premium_sections_html(
        chart,
        dasha=dasha,
        gochar=gochar,
        language="hi",
        synthesis=_synth(),
    )

    for heading in HI_HEADINGS:
        assert heading in frag, f"missing HI heading: {heading}"
    assert "जीवन क्षेत्र पूर्वानुमान" in frag
    assert "ग्रह संतुलन" in frag
    assert _strength_row_count(frag) == 9


def test_standard_template_embeds_premium_sections():
    chart = _chart()
    dasha = _dasha(chart)
    gochar = _gochar(chart)

    html = build_html(
        chart,
        dasha=dasha,
        gochar=gochar,
        language="en",
        template="standard",
    )

    assert 'class="section premium-analysis"' in html
    assert "Planetary Strength" in html
    assert "Ashtakavarga" in html
    assert _strength_row_count(html) == 9


def test_hand_built_minimal_report_shape():
    """Synthetic kundali-shaped dict: flags, houses, yogas, ashtakavarga."""
    planets = {
        name: {
            "sign": "Mesha",
            "house": i + 1 if i < 12 else 1,
            "degree": 10.0,
            "longitude": 10.0 + i,
            "nakshatra": "Ashwini",
            "nakshatra_pada": 1,
            "retrograde": False,
            "dignity": "neutral",
            "digbala": "moderate",
            "vargottama": False,
            "combust": False,
            "graha_yuddha": False,
            "functional_nature": "neutral",
            "strength_verdict": "Moderate — neutral",
        }
        for i, name in enumerate(
            ["Surya", "Chandra", "Mangal", "Budh", "Guru", "Shukra", "Shani", "Rahu", "Ketu"]
        )
    }
    houses = {
        str(h): {
            "sign": "Mesha",
            "lord": "Mangal",
            "planets": ["Surya"] if h == 1 else [],
        }
        for h in range(1, 13)
    }
    kundali = {
        "input": {
            "dob": "01/01/2000",
            "tob": "12:00",
            "place": "Delhi",
            "lat": 28.6,
            "lon": 77.2,
            "timezone_name": "Asia/Kolkata",
        },
        "calculation": {"datetime_local": "2000-01-01T12:00:00+05:30"},
        "lagna": "Mesha",
        "rashi": "Mesha",
        "nakshatra": "Ashwini",
        "nakshatra_pada": 1,
        "planets": planets,
        "houses": houses,
        "doshas": [],
        "yogas": [
            {
                "name": "TestYoga",
                "type": "raja-like",
                "planets": ["Guru", "Chandra"],
                "houses": [1, 7],
                "description": "Synthetic yoga for unit test.",
            }
        ],
        "ashtakavarga": {
            "sarva": [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31],
            "bhinna_totals": {"Surya": 40, "Chandra": 41},
            "sarva_total": 306,
        },
        "mangalik": {"status": "present", "reasons": ["Mars in 7th (synthetic)"]},
    }
    dasha = {
        "system": "Vimshottari",
        "seed_nakshatra": "Ashwini",
        "seed_lord": "Ketu",
        "current": {
            "mahadasha": "Shukra",
            "antardasha": "Surya",
            "pratyantardasha": "Shukra",
            "mahadasha_end": "2030-01-01",
            "antardasha_end": "2027-01-01",
            "pratyantardasha_end": "2026-06-01",
        },
        "timeline": [],
    }
    gochar = {
        "transits": {
            "Surya": {
                "sign": "Mesha",
                "house_from_moon": 1,
                "house_from_lagna": 1,
            }
        },
        "saturn_analysis": {
            "status": "none",
            "type": "",
            "sign": "Kumbha",
            "house_from_moon": 11,
        },
    }

    frag_no_synth = build_premium_sections_html(kundali, dasha=dasha, gochar=gochar, language="en")
    for heading in EN_HEADINGS:
        assert heading in frag_no_synth, f"missing: {heading}"
    assert "TestYoga" in frag_no_synth
    assert "31" in frag_no_synth  # best sarva total
    assert "20" in frag_no_synth  # worst sarva total
    assert _strength_row_count(frag_no_synth) == 9
    assert "Life-Area Forecasts" not in frag_no_synth

    frag_synth = build_premium_sections_html(
        kundali,
        dasha=dasha,
        gochar=gochar,
        language="en",
        synthesis=_synth(),
    )
    assert "Synthetic executive overview" in frag_synth
    assert "Life-Area Forecasts" in frag_synth
    assert "Remedies (Prioritised)" in frag_synth
    assert _strength_row_count(frag_synth) == 9
