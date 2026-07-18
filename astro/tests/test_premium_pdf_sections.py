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
    _area_reason,
    _first_sentence,
    _render_gochar_highlights,
    _render_premium_remedies,
    build_html,
    build_premium_sections_html,
    display_saturn_status,
)
from kundali_calculator import BirthInput, calculate_kundali  # noqa: E402
from report_generator import build_basic_report  # noqa: E402
from scoring import score_report  # noqa: E402

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


def _gochar_narrative() -> dict:
    return {
        "summary": "Gochar narrative summary.",
        "samples": [
            {
                "date": "2026-05-20",
                "highlights": [
                    {
                        "planet": "Surya",
                        "sign": "Mesha",
                        "house_from_moon": 1,
                        "house_from_lagna": 1,
                    }
                ]
            }
        ]
    }


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


def _pandit_pages(html: str) -> list[str]:
    return re.findall(r'<section class="pandit-page">(.*?)</section>', html, flags=re.S)


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
        gochar_narrative=_gochar_narrative(),
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
        gochar_narrative=_gochar_narrative(),
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
    assert "Daily minimum" in html
    assert "Best time" in html
    assert "Sphatik mala" in html
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
        gochar_narrative=_gochar_narrative(),
        language="hi",
        synthesis=_synth(),
    )

    for heading in HI_HEADINGS:
        assert heading in frag, f"missing HI heading: {heading}"
    assert "जीवन क्षेत्र पूर्वानुमान" in frag
    assert "ग्रह संतुलन" in frag
    assert _strength_row_count(frag) == 9


def test_fallback_remedy_detail_grid_is_bilingual() -> None:
    chart = _chart()
    dasha = _dasha(chart)
    html = _render_premium_remedies(chart, dasha, chart["planets"], "hi", {})

    assert "दैनिक न्यूनतम" in html
    assert "श्रेष्ठ समय" in html
    assert "माला" in html
    assert "दिशा" in html
    assert "अवधि" in html


def test_dashboard_is_page_three_and_verdict_is_last_in_both_languages() -> None:
    chart = _chart()
    dasha = _dasha(chart)
    synth = _synth()
    synth["en"]["life_areas"]["career"] = "Career first sentence. Hidden second sentence."
    synth["hi"]["life_areas"]["करियर"] = "करियर का पहला वाक्य। छिपा दूसरा वाक्य।"

    for language, dashboard_title, birth_title, verdict_title, first, hidden in (
        (
            "en",
            "At-a-Glance Summary",
            "Birth Details",
            "Overall Assessment",
            "Career first sentence.",
            "Hidden second sentence.",
        ),
        (
            "hi",
            "एक-नज़र सार",
            "जन्म विवरण",
            "समग्र मूल्यांकन",
            "करियर का पहला वाक्य।",
            "छिपा दूसरा वाक्य।",
        ),
    ):
        html = build_html(
            chart,
            dasha=dasha,
            language=language,
            template="pandit_v1",
            synthesis=synth,
        )
        pages = _pandit_pages(html)
        assert dashboard_title in pages[2]
        assert birth_title in pages[3]
        assert verdict_title in pages[-1]
        assert first in pages[2]
        assert hidden not in pages[2]
        assert "MD:" in pages[2] and "AD:" in pages[2] and "PD:" in pages[2]
        assert dasha["current"]["antardasha_end"] in pages[2]
        assert pages[-1].count('class="assessment-row ') == 6
        assert ("दैनिक न्यूनतम" if language == "hi" else "Daily minimum") in html
        combined = pages[2] + pages[-1]
        assert not re.search(
            r"has (?:Growth Area|Balanced|Favourable) strength",
            combined,
        )
        yoga_reason = "का समर्थन है" if language == "hi" else "gains support from"
        assert yoga_reason in pages[2]
        assert yoga_reason in pages[-1]


def test_integrated_color_bands_follow_computed_strength_house_and_yoga_data() -> None:
    chart = _chart()
    dasha = _dasha(chart)
    html = build_html(chart, dasha=dasha, language="en", template="pandit_v1")

    assert re.search(r'<tr class="band-strong">.*?Mars', html, flags=re.S)
    assert re.search(r'<tr class="band-mixed">.*?Sun', html, flags=re.S)
    assert re.search(r'<tr class="band-weak">.*?Moon', html, flags=re.S)

    report = build_basic_report(chart, dasha=dasha, language="en")
    house_10_band = score_report(report, dasha)["houses"][10]["band"].lower()
    assert re.search(
        rf'class="house-card band-{house_10_band}"[^>]*><h4>H10',
        html,
    )
    assert re.search(r'class="yoga-card band-strong"[^>]*><strong>Gajakesari', html)
    assert re.search(r'class="yoga-card band-weak"[^>]*><strong>Kaal Sarp', html)


def test_dashboard_and_verdict_escape_synthesis_and_avoid_fake_precision() -> None:
    chart = _chart()
    dasha = _dasha(chart)
    synth = _synth()
    synth["en"]["life_areas"]["career"] = '<script>alert("x")</script>. Later sentence.'

    html = build_html(
        chart,
        dasha=dasha,
        language="en",
        template="pandit_v1",
        synthesis=synth,
    )
    pages = _pandit_pages(html)
    assert "<script>" not in pages[2]
    assert "&lt;script&gt;" in pages[2]
    assert "Heuristic index from classical strength factors" in pages[-1]
    assert "/100" not in pages[2] + pages[-1]
    assert not re.search(r"\d+%", pages[2] + pages[-1])


def test_area_reasons_use_raw_strength_and_explain_yoga_lift_bilingually() -> None:
    area_score = {
        "area": "career",
        "stars": 5,
        "rating": "★★★★★",
        "band": "Strong",
        "drivers": [
            {
                "house": 10,
                "house_lord": "Budh",
                "lord_strength": "Weak — debilitated",
                "dasha_activated": True,
                "benefic_yoga_support": [
                    "Raja Yoga",
                    "Neechabhanga Raja Yoga",
                    "Budhaditya",
                ],
            }
        ],
    }

    en = _area_reason(area_score, "en")
    hi = _area_reason(area_score, "hi")

    assert "H10 (Career)" in en
    assert "Raja Yoga" in en and "Neechabhanga Raja Yoga" in en and "Budhaditya" in en
    assert "weak underlying strength profile" in en
    assert "active in the current dasha" in en
    assert "भाव 10 (करियर)" in hi
    assert "कमज़ोर" in hi and "वर्तमान दशा में सक्रिय" in hi
    for softened in ("Growth Area", "Balanced", "Favourable"):
        assert f"has {softened} strength" not in en


def test_dashboard_sentence_is_bounded_for_frame_safety() -> None:
    long_sentence = "Career " + ("grounded-factor " * 100)
    clipped = _first_sentence(long_sentence)

    assert len(clipped) <= 363
    assert clipped.endswith("...")


def test_structured_remedy_cards_each_get_a_framed_page() -> None:
    chart = _chart()
    dasha = _dasha(chart)
    synthesis = {
        "en": {
            "remedies": [
                {"planet": "Chandra", "mantra": "Moon mantra"},
                {"planet": "Mangal", "mantra": "Mars mantra"},
                {"planet": "Guru", "mantra": "Jupiter mantra"},
            ]
        }
    }

    pages = _pandit_pages(
        build_html(
            chart,
            dasha=dasha,
            language="en",
            template="pandit_v1",
            synthesis=synthesis,
        )
    )
    remedy_pages = [page for page in pages if "Remedies (Prioritised)" in page]

    assert len(remedy_pages) == 3
    assert sum("Moon mantra" in page for page in remedy_pages) == 1
    assert sum("Mars mantra" in page for page in remedy_pages) == 1
    assert sum("Jupiter mantra" in page for page in remedy_pages) == 1


def test_standard_template_embeds_premium_sections():
    chart = _chart()
    dasha = _dasha(chart)
    gochar = _gochar(chart)

    html = build_html(
        chart,
        dasha=dasha,
        gochar=gochar,
        gochar_narrative=_gochar_narrative(),
        language="en",
        template="standard",
    )

    assert 'class="section premium-analysis"' in html
    assert "Planetary Strength" in html
    assert "Ashtakavarga" in html
    assert _strength_row_count(html) == 9


def test_pandit_brand_footer_and_colophon_are_bilingual_and_escaped() -> None:
    chart = _chart()
    dasha = _dasha(chart)

    en = build_html(
        chart,
        dasha=dasha,
        language="en",
        template="pandit_v1",
        brand="Pandit & Sons <Udaipur>",
    )
    en_pages = en.count('class="pandit-page"')
    assert en.count("Pandit &amp; Sons &lt;Udaipur&gt;") == en_pages
    assert "Pandit & Sons <Udaipur>" not in en
    en_last = en.rsplit('<section class="pandit-page">', 1)[1]
    assert "Overall Assessment" in en_last
    assert "Swiss Ephemeris (SWIEPH)" in en_last
    assert "Lahiri ayanamsa" in en_last
    assert date.today().isoformat() in en_last

    hi = build_html(chart, dasha=dasha, language="hi", template="pandit_v1")
    hi_last = hi.rsplit('<section class="pandit-page">', 1)[1]
    assert "जन्म पत्रिका — गणना आधारित प्रारूप" in hi
    assert "समग्र मूल्यांकन" in hi_last
    assert "Lahiri अयनांश" in hi_last
    assert "निर्मित" in hi_last


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

    frag_no_synth = build_premium_sections_html(
        kundali, dasha=dasha, gochar=gochar, gochar_narrative=_gochar_narrative(), language="en"
    )
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
        gochar_narrative=_gochar_narrative(),
        language="en",
        synthesis=_synth(),
    )
    assert "Synthetic executive overview" in frag_synth
    assert "Life-Area Forecasts" in frag_synth
    assert "Remedies (Prioritised)" in frag_synth
    assert _strength_row_count(frag_synth) == 9


def test_display_saturn_status_labels() -> None:
    """sade_sati/dhaiya must render as human labels, not the raw enum token."""
    assert display_saturn_status("sade_sati", "en") == "Sade Sati"
    assert display_saturn_status("sade_sati", "hi") == "साढ़े साती"
    assert display_saturn_status("dhaiya", "en") == "Dhaiya"
    assert display_saturn_status("dhaiya", "hi") == "ढैया"
    # "none"/empty must not surface as the literal string "none".
    assert display_saturn_status("none", "en") == "—"
    assert display_saturn_status(None, "en") == "—"
    assert display_saturn_status("", "hi") == "—"


def test_gochar_highlights_render_sade_sati_label() -> None:
    """End-to-end guard: the gochar highlights section must show 'Sade Sati',
    not the raw 'sade_sati' enum token (issue #10, fix 3)."""
    narrative = {
        "summary": "Gochar narrative summary.",
        "samples": [
            {
                "date": "2026-05-20",
                "highlights": [
                    {
                        "planet": "Shani",
                        "sign": "Kumbha",
                        "house_from_moon": 1,
                        "house_from_lagna": 1,
                    }
                ],
                "saturn_analysis": {
                    "status": "sade_sati",
                    "phase": "peak",
                    "sign": "Kumbha",
                    "house_from_moon": 1,
                },
            }
        ],
    }
    html = _render_gochar_highlights(narrative, "en")
    assert "Sade Sati" in html
    # The raw enum token must not leak into the rendered text on its own.
    assert ": sade_sati" not in html
