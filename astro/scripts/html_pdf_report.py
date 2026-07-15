#!/usr/bin/env python
"""HTML + Chromium renderer for the astrology report PDF.

Produces a polished, print-CSS-styled HTML document and rasterises it via
Playwright/Chromium. Devanagari shaping is delegated to the browser's text
engine, which handles Hindi maatras far better than ReportLab's bundled
fallback fonts.

Use :func:`build_html_pdf_report` directly, or call through
``pdf_report.build_pdf_report(..., renderer="html")``.

If Chromium is not installed, :func:`build_html_pdf_report` raises
``RuntimeError`` with the install command. Tests should skip themselves when
``chromium_available()`` returns ``False``.
"""
from __future__ import annotations

import base64
import html
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:
    from .report_generator import build_basic_report
except ImportError:  # pragma: no cover - direct script execution path.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from report_generator import build_basic_report  # noqa: E402

_FONT_FILE = ROOT / "fonts" / "NotoSansDevanagari.ttf"

PLANET_ORDER = ["Surya", "Chandra", "Mangal", "Budh", "Guru", "Shukra", "Shani", "Rahu", "Ketu"]

# Zodiac order; index+1 is the rashi number shown in chart cells.
SIGN_ORDER = [
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrischika", "Dhanu", "Makara", "Kumbha", "Meena",
]

HI_PLANETS = {
    "Surya": "सूर्य",
    "Chandra": "चंद्र",
    "Mangal": "मंगल",
    "Budh": "बुध",
    "Guru": "गुरु",
    "Shukra": "शुक्र",
    "Shani": "शनि",
    "Rahu": "राहु",
    "Ketu": "केतु",
}

EN_PLANETS = {
    "Surya": "Sun",
    "Chandra": "Moon",
    "Mangal": "Mars",
    "Budh": "Mercury",
    "Guru": "Jupiter",
    "Shukra": "Venus",
    "Shani": "Saturn",
    "Rahu": "Rahu",
    "Ketu": "Ketu",
}

HI_SIGNS = {
    "Mesha": "मेष",
    "Vrishabha": "वृषभ",
    "Mithuna": "मिथुन",
    "Karka": "कर्क",
    "Simha": "सिंह",
    "Kanya": "कन्या",
    "Tula": "तुला",
    "Vrischika": "वृश्चिक",
    "Dhanu": "धनु",
    "Makara": "मकर",
    "Kumbha": "कुंभ",
    "Meena": "मीन",
}

HI_NAKSHATRAS = {
    "Ashwini": "अश्विनी",
    "Bharani": "भरणी",
    "Krittika": "कृत्तिका",
    "Rohini": "रोहिणी",
    "Mrigashira": "मृगशिरा",
    "Ardra": "आर्द्रा",
    "Punarvasu": "पुनर्वसु",
    "Pushya": "पुष्य",
    "Ashlesha": "आश्लेषा",
    "Magha": "मघा",
    "Purva Phalguni": "पूर्व फाल्गुनी",
    "Uttara Phalguni": "उत्तर फाल्गुनी",
    "Hasta": "हस्त",
    "Chitra": "चित्रा",
    "Swati": "स्वाती",
    "Vishakha": "विशाखा",
    "Anuradha": "अनुराधा",
    "Jyeshtha": "ज्येष्ठा",
    "Mula": "मूल",
    "Purva Ashadha": "पूर्वाषाढ़ा",
    "Uttara Ashadha": "उत्तराषाढ़ा",
    "Shravana": "श्रवण",
    "Dhanishta": "धनिष्ठा",
    "Shatabhisha": "शतभिषा",
    "Purva Bhadrapada": "पूर्व भाद्रपद",
    "Uttara Bhadrapada": "उत्तर भाद्रपद",
    "Revati": "रेवती",
}

HI_TERMS = {
    "Shukla": "शुक्ल",
    "Krishna": "कृष्ण",
    "Pratipada": "प्रतिपदा",
    "Dwitiya": "द्वितीया",
    "Tritiya": "तृतीया",
    "Chaturthi": "चतुर्थी",
    "Panchami": "पंचमी",
    "Shashthi": "षष्ठी",
    "Saptami": "सप्तमी",
    "Ashtami": "अष्टमी",
    "Navami": "नवमी",
    "Dashami": "दशमी",
    "Ekadashi": "एकादशी",
    "Dwadashi": "द्वादशी",
    "Trayodashi": "त्रयोदशी",
    "Chaturdashi": "चतुर्दशी",
    "Purnima": "पूर्णिमा",
    "Amavasya": "अमावस्या",
    "Somavara": "सोमवार",
    "Mangalavara": "मंगलवार",
    "Budhavara": "बुधवार",
    "Guruvara": "गुरुवार",
    "Shukravara": "शुक्रवार",
    "Shanivara": "शनिवार",
    "Ravivara": "रविवार",
}

EN_LABELS = {
    "title": "Vedic Astrology Report",
    "subtitle": "Calculation draft for astrologer/operator review",
    "cover_mantra": "Om Gan Ganapataye Namah",
    "notice_title": "Notice",
    "notice": (
        "This report is calculation-first. The reviewing astrologer or "
        "operator remains the final authority."
    ),
    "birth_details": "Birth Summary",
    "field": "Field",
    "value": "Value",
    "birth_place": "Birth place",
    "birth_datetime": "Birth datetime",
    "lagna": "Lagna",
    "rashi": "Rashi",
    "nakshatra": "Nakshatra",
    "doshas": "Doshas flagged",
    "planet_chart": "Lagna Kundali",
    "navamsa_chart": "Navamsa Chart (D9)",
    "planet_table": "Planet Positions",
    "planet": "Planet",
    "sign": "Sign",
    "house": "House",
    "degree": "Degree",
    "dasha": "Dasha Timeline",
    "system": "System",
    "seed": "Seed",
    "current_period": "Current period",
    "mahadasha_end": "Mahadasha ends",
    "antardasha_end": "Antardasha ends",
    "pratyantardasha_end": "Pratyantardasha ends",
    "panchang": "Daily Panchang",
    "date": "Date",
    "place": "Place",
    "vara": "Vara",
    "tithi": "Tithi",
    "yoga": "Yoga",
    "karana": "Karana",
    "sunrise": "Sunrise",
    "sunset": "Sunset",
    "safety": "Safety Notes",
}

HI_LABELS = {
    "title": "जन्म कुंडली रिपोर्ट",
    "subtitle": "ज्योतिषी/संचालक समीक्षा हेतु गणना-आधारित प्रारूप",
    "cover_mantra": "ॐ गं गणपतये नमः",
    "notice_title": "सूचना",
    "notice": (
        "यह रिपोर्ट जन्म विवरण और ग्रह गणना पर आधारित है। अंतिम व्याख्या और "
        "सलाह समीक्षा करने वाले ज्योतिषी/संचालक के विवेक से ही मान्य होगी।"
    ),
    "birth_details": "जन्म विवरण",
    "field": "विवरण",
    "value": "मान",
    "birth_place": "जन्म स्थान",
    "birth_datetime": "जन्म समय",
    "lagna": "लग्न",
    "rashi": "राशि",
    "nakshatra": "नक्षत्र",
    "doshas": "दोष संकेत",
    "planet_chart": "लग्न कुंडली",
    "navamsa_chart": "नवांश कुंडली (D9)",
    "planet_table": "ग्रह स्थिति",
    "planet": "ग्रह",
    "sign": "राशि",
    "house": "भाव",
    "degree": "अंश",
    "dasha": "दशा तालिका",
    "system": "पद्धति",
    "seed": "दशा बीज",
    "current_period": "वर्तमान दशा",
    "mahadasha_end": "महादशा समाप्ति",
    "antardasha_end": "अंतर्दशा समाप्ति",
    "pratyantardasha_end": "प्रत्यंतर्दशा समाप्ति",
    "panchang": "दैनिक पंचांग",
    "date": "दिनांक",
    "place": "स्थान",
    "vara": "वार",
    "tithi": "तिथि",
    "yoga": "योग",
    "karana": "करण",
    "sunrise": "सूर्योदय",
    "sunset": "सूर्यास्त",
    "safety": "सुरक्षा नोट्स",
}

PANDIT_LABELS = {
    "janma_patrika": ("जन्म पत्रिका", "Janma Patrika"),
    "badge": ("गणना-आधारित प्रारूप", "Calculation-based format"),
    "notice_title": ("सूचना", "Notice"),
    "notice_1": (
        "ज्योतिष एक पारंपरिक मार्गदर्शन प्रणाली है। यह रिपोर्ट जन्म विवरण, ग्रह गणना, पंचांग और दशा के आधार पर तैयार की गई है। इसे अंतिम निर्णय नहीं माना जाए। विवाह, स्वास्थ्य, निवेश, कानूनी या जीवन बदलने वाले निर्णयों में पंडित जी और संबंधित विशेषज्ञ की सलाह आवश्यक है।",
        "Astrology is a traditional system of guidance. This report is prepared from birth details, planetary calculations, panchang and dasha. It should not be treated as a final verdict. For decisions about marriage, health, investment, legal or life-changing matters, the guidance of a pandit and the relevant expert is essential.",
    ),
    "notice_2": (
        "यह प्रारूप पंडित जी की समीक्षा, क्लाइंट बातचीत और तेज रिपोर्ट तैयारी के लिए बनाया गया है।",
        "This format is designed for the astrologer's review, client discussion, and fast report preparation.",
    ),
    "birth_details": ("जन्म विवरण", "Birth Details"),
    "name": ("नाम", "Name"),
    "birth_place": ("जन्म स्थान", "Birth Place"),
    "birth_dt": ("जन्म तिथि और समय", "Date & Time of Birth"),
    "moon_house": ("चंद्र भाव", "Moon House"),
    "dosha_flag": ("दोष संकेत", "Dosha Indications"),
    "no_dosha": ("कोई प्रमुख दोष फ्लैग नहीं", "No major dosha flagged"),
    "avakahada": ("अवकहड़ा चक्र", "Avakahada Chakra"),
    "ava_lagna": ("लग्न — लग्नाधिपति", "Lagna — Lord"),
    "ava_rashi": ("राशि — स्वामी", "Rashi — Lord"),
    "ava_nak": ("नक्षत्र — चरण", "Nakshatra — Pada"),
    "ava_naklord": ("नक्षत्र स्वामी", "Nakshatra Lord"),
    "gan": ("गण", "Gana"),
    "yoni": ("योनि", "Yoni"),
    "nadi": ("नाड़ी", "Nadi"),
    "varna": ("वर्ण", "Varna"),
    "vashya": ("वश्य", "Vashya"),
    "tatva": ("तत्व", "Tatva (Element)"),
    "paya": ("पाया (राशि)", "Paya (by Rashi)"),
    "namakshar": ("जन्म नामाक्षर", "Name Syllable"),
    "ishta": ("इष्ट (घटी)", "Ishta Kaal (Ghati)"),
    "dinamaan": ("दिनमान (घंटे)", "Day Length (hrs)"),
    "janma_panchang": ("जन्म पंचांग", "Birth Panchang"),
    "date": ("दिनांक", "Date"),
    "place": ("स्थान", "Place"),
    "vara": ("वार", "Weekday"),
    "tithi": ("तिथि", "Tithi"),
    "nakshatra": ("नक्षत्र", "Nakshatra"),
    "yoga": ("योग", "Yoga"),
    "karana": ("करण", "Karana"),
    "sunrise": ("सूर्योदय", "Sunrise"),
    "sunset": ("सूर्यास्त", "Sunset"),
    "lagna_kundali": ("लग्न कुंडली", "Lagna Kundali"),
    "chandra_kundali": ("चंद्र कुंडली", "Chandra Kundali"),
    "chandra_note": (
        "चंद्र कुंडली को मन, अनुभव और भावनात्मक प्रतिक्रिया के संकेत के रूप में पढ़ें।",
        "Read the Chandra Kundali as an indicator of the mind, experiences and emotional response.",
    ),
    "navamsa": ("नवांश कुंडली (D9)", "Navamsa Kundali (D9)"),
    "graha_sthiti": ("ग्रह स्थिति", "Planet Positions"),
    "dasha_table": ("दशा तालिका", "Dasha Timeline"),
    "paddhati": ("पद्धति", "System"),
    "dasha_beej": ("दशा बीज", "Dasha Seed"),
    "vartaman_dasha": ("वर्तमान दशा", "Current Period"),
    "maha_end": ("महादशा समाप्ति", "Mahadasha ends"),
    "antar_end": ("अंतर्दशा समाप्ति", "Antardasha ends"),
    "praty_end": ("प्रत्यंतर्दशा समाप्ति", "Pratyantardasha ends"),
    "mahadasha": ("महादशा", "Mahadasha"),
    "start": ("आरंभ", "Start"),
    "end": ("समाप्ति", "End"),
    "duration": ("अवधि", "Duration"),
    "antar_table": ("अंतर्दशा तालिका", "Antardasha Timeline"),
    "antardasha": ("अंतर्दशा", "Antardasha"),
    "lrn_phal": ("लग्न-राशि-नक्षत्र फल", "Lagna–Rashi–Nakshatra Reading"),
    "lagna_phal": ("लग्न फल", "Lagna Reading"),
    "rashi_phal": ("राशि फल", "Rashi Reading"),
    "nak_phal": ("नक्षत्र फल", "Nakshatra Reading"),
    "swabhav_note": (
        "यह स्वभाव-चित्रण शास्त्रीय सामान्य लक्षणों पर आधारित है; विस्तृत फलादेश पंडित जी पूरी कुंडली देखकर दें।",
        "This character sketch is based on classical general traits; a detailed reading should be given by the pandit after studying the full chart.",
    ),
    "yog_dosh": ("योग और दोष सार", "Yoga & Dosha Summary"),
    "mukhya_yog": ("मुख्य योग", "Key Yogas"),
    "no_yog": ("विशेष योग सूची उपलब्ध नहीं", "No special yoga listed"),
    "yog_note": (
        "योग-दोष का निष्कर्ष अकेले एक नियम से नहीं, पूरी कुंडली मिलाकर दिया जाए।",
        "Conclusions on yoga and dosha should be drawn from the whole chart, not a single rule.",
    ),
    "current_analysis": ("वर्तमान दशा विश्लेषण", "Current Period Analysis"),
    "running_period": ("वर्तमान अवधि", "Running Period"),
    "period_theme": ("अवधि का स्वरूप", "Themes of this Period"),
    "mindset": ("मानसिक स्थिति एवं दृष्टिकोण", "Mindset & Outlook"),
    "challenges": ("संभावित चुनौतियाँ एवं सीख", "Likely Challenges & Lessons"),
    "current_note": (
        "यह विश्लेषण वर्तमान महादशा-अंतर्दशा के शास्त्रीय सामान्य फल पर आधारित है; व्यक्तिगत निष्कर्ष पूरी कुंडली देखकर पंडित जी दें।",
        "This analysis is based on the classical general effects of the running Mahadasha–Antardasha; personal conclusions should be given by the pandit after studying the full chart.",
    ),
    "dasha_phal_title": ("महादशा फल", "Mahadasha Readings"),
    "dasha_phal_note": (
        "प्रत्येक महादशा का यह सामान्य फल शास्त्रीय ग्रह-कारकत्व पर आधारित है; ग्रह की भाव-स्थिति के अनुसार फल में अंतर आता है।",
        "Each Mahadasha reading below reflects classical planetary significations; results vary with the planet's house placement in the chart.",
    ),
    "years": ("वर्ष", "yr"),
    "months": ("माह", "mo"),
    "days": ("दिन", "d"),
    "footer": ("जन्म पत्रिका — गणना आधारित प्रारूप", "Janma Patrika — calculation-based format"),
}


def pl(key: str, language: str) -> str:
    hi, en = PANDIT_LABELS[key]
    return hi if _is_hi(language) else en


PALETTE = [
    "#7A9E7E",
    "#D9A441",
    "#8D493A",
    "#577590",
    "#B56576",
    "#3D405B",
    "#D08770",
    "#5E548E",
    "#6B705C",
]


def _is_hi(language: str) -> bool:
    return language in {"hi", "hin"}


def label(key: str, language: str) -> str:
    return HI_LABELS[key] if _is_hi(language) else EN_LABELS[key]


def display_planet(name: str, language: str) -> str:
    return HI_PLANETS.get(name, name) if _is_hi(language) else EN_PLANETS.get(name, name)


def display_sign(name: str, language: str) -> str:
    if not _is_hi(language):
        return name
    return f"{HI_SIGNS.get(name, name)} ({name})"


def display_nakshatra(value: str, language: str) -> str:
    if not _is_hi(language):
        return value
    updated = value
    for english, hindi in HI_NAKSHATRAS.items():
        updated = updated.replace(english, f"{hindi} ({english})")
    updated = updated.replace(" pada ", " चरण ")
    return updated


HI_YOGAS = {
    "Vishkambha": "विष्कम्भ", "Priti": "प्रीति", "Ayushman": "आयुष्मान",
    "Saubhagya": "सौभाग्य", "Shobhana": "शोभन", "Atiganda": "अतिगण्ड",
    "Sukarma": "सुकर्मा", "Dhriti": "धृति", "Shula": "शूल", "Ganda": "गण्ड",
    "Vriddhi": "वृद्धि", "Dhruva": "ध्रुव", "Vyaghata": "व्याघात",
    "Harshana": "हर्षण", "Vajra": "वज्र", "Siddhi": "सिद्धि",
    "Vyatipata": "व्यतीपात", "Variyana": "वरीयान", "Parigha": "परिघ",
    "Shiva": "शिव", "Siddha": "सिद्ध", "Sadhya": "साध्य", "Shubha": "शुभ",
    "Shukla": "शुक्ल", "Brahma": "ब्रह्म", "Indra": "इन्द्र", "Vaidhriti": "वैधृति",
}

HI_KARANAS = {
    "Kimstughna": "किंस्तुघ्न", "Chatushpada": "चतुष्पाद", "Shakuni": "शकुनि",
    "Balava": "बालव", "Kaulava": "कौलव", "Taitila": "तैतिल", "Vanija": "वणिज",
    "Vishti": "विष्टि", "Bava": "बव", "Gara": "गर", "Naga": "नाग",
}

HI_MISC = {"Vimshottari": "विंशोत्तरी"}


def _replace_longest_first(value: str, mapping: dict) -> str:
    for english in sorted(mapping, key=len, reverse=True):
        value = value.replace(english, mapping[english])
    return value


def display_term(value: str, language: str) -> str:
    if not _is_hi(language):
        return value
    return _replace_longest_first(value, {**HI_TERMS, **HI_NAKSHATRAS, **HI_YOGAS, **HI_KARANAS, **HI_MISC})


def display_dasha_value(value: str, language: str) -> str:
    if not _is_hi(language) or not value:
        return value
    return _replace_longest_first(value, {**HI_MISC, **HI_NAKSHATRAS, **HI_PLANETS})


def format_dms(degree: object) -> str:
    if not isinstance(degree, (int, float)):
        return str(degree)
    total_minutes = round(float(degree) * 60)
    deg, minutes = divmod(total_minutes, 60)
    return f"{deg}°{minutes:02d}'"


def format_time(value: object) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(str(value)).strftime("%H:%M")
    except ValueError:
        return str(value)


def _h(value: object) -> str:
    return html.escape(str(value), quote=True)


def _cover_name(kundali: dict, client_name: str | None) -> str:
    inp = kundali.get("input", {})
    return (
        client_name
        or inp.get("client_name")
        or inp.get("name")
        or inp.get("place", "")
    )


def _ni_house_polygons(size: float) -> dict[str, list[tuple[float, float]]]:
    """Vertex lists for the 12 houses of the standard North Indian layout.

    Landmarks of a ``size`` square: corners, edge midpoints, centre, and the
    four points at quarter offsets where the square's diagonals cross the
    inner diamond. Houses count anticlockwise; house 1 is the top diamond,
    4/7/10 the other diamonds, the rest corner triangles.
    """
    s = size
    c = s / 2
    q = s / 4
    return {
        "1": [(c, 0), (q, q), (c, c), (3 * q, q)],
        "2": [(0, 0), (c, 0), (q, q)],
        "3": [(0, 0), (q, q), (0, c)],
        "4": [(0, c), (q, q), (c, c), (q, 3 * q)],
        "5": [(0, c), (q, 3 * q), (0, s)],
        "6": [(0, s), (q, 3 * q), (c, s)],
        "7": [(c, s), (q, 3 * q), (c, c), (3 * q, 3 * q)],
        "8": [(c, s), (3 * q, 3 * q), (s, s)],
        "9": [(s, s), (3 * q, 3 * q), (s, c)],
        "10": [(s, c), (3 * q, 3 * q), (c, c), (3 * q, q)],
        "11": [(s, c), (3 * q, q), (s, 0)],
        "12": [(s, 0), (3 * q, q), (c, 0)],
    }


def _poly_y_span(vertices: list[tuple[float, float]], x: float) -> tuple[float, float]:
    """Vertical extent [y_min, y_max] of the polygon along the line ``x``."""
    ys: list[float] = []
    for i, (x1, y1) in enumerate(vertices):
        x2, y2 = vertices[(i + 1) % len(vertices)]
        if x1 == x2:
            if x1 == x:
                ys += [y1, y2]
        elif min(x1, x2) <= x <= max(x1, x2):
            ys.append(y1 + (x - x1) / (x2 - x1) * (y2 - y1))
    return min(ys), max(ys)


def _poly_x_span(vertices: list[tuple[float, float]], y: float) -> tuple[float, float]:
    """Horizontal extent [x_min, x_max] of the polygon along the line ``y``."""
    xs: list[float] = []
    for i, (x1, y1) in enumerate(vertices):
        x2, y2 = vertices[(i + 1) % len(vertices)]
        if y1 == y2:
            if y1 == y:
                xs += [x1, x2]
        elif min(y1, y2) <= y <= max(y1, y2):
            xs.append(x1 + (y - y1) / (y2 - y1) * (x2 - x1))
    return min(xs), max(xs)


def _ni_chart_svg(kundali: dict, language: str) -> str:
    """Return inline SVG for a North Indian (diamond) kundali chart."""
    size = 360
    render = 480
    cx = size / 2
    cy = size / 2
    # Outer square + diagonals + inner diamond
    lines = [
        f'<rect x="0" y="0" width="{size}" height="{size}" fill="#fdf7ea" stroke="#b10000" stroke-width="2"/>',
        f'<line x1="0" y1="0" x2="{size}" y2="{size}" stroke="#b10000" stroke-width="1.2"/>',
        f'<line x1="0" y1="{size}" x2="{size}" y2="0" stroke="#b10000" stroke-width="1.2"/>',
        f'<line x1="{cx}" y1="0" x2="0" y2="{cy}" stroke="#b10000" stroke-width="1.2"/>',
        f'<line x1="0" y1="{cy}" x2="{cx}" y2="{size}" stroke="#b10000" stroke-width="1.2"/>',
        f'<line x1="{cx}" y1="{size}" x2="{size}" y2="{cy}" stroke="#b10000" stroke-width="1.2"/>',
        f'<line x1="{size}" y1="{cy}" x2="{cx}" y2="0" stroke="#b10000" stroke-width="1.2"/>',
    ]
    houses = kundali.get("houses", {})
    for house, vertices in _ni_house_polygons(size).items():
        data = houses.get(house, {"sign": "", "planets": []})
        sign = data.get("sign", "")
        rashi_no = str(SIGN_ORDER.index(sign) + 1) if sign in SIGN_ORDER else ""
        planets = [
            display_planet(name, language)
            for name in PLANET_ORDER
            if name in data.get("planets", [])
        ]
        x = sum(v[0] for v in vertices) / len(vertices)
        y = sum(v[1] for v in vertices) / len(vertices)

        crowded = len(planets) > 3
        font = 8.0 if crowded else 8.5
        line_h = 9.5 if crowded else 10.0
        # Two columns only when the cell is wide enough at the centroid row;
        # side triangles (3/5/9/11) stay single-column to avoid the sloped edges.
        x_lo, x_hi = _poly_x_span(vertices, y)
        two_cols = crowded and (x_hi - x_lo) >= 110
        rows = math.ceil(len(planets) / 2) if two_cols else len(planets)

        rashi_h = 12.0
        block_h = rashi_h + rows * line_h
        # Keep the block inside the polygon and visually centred: a triangle's
        # centroid sits only a third of the way from its base, so blend it with
        # the midpoint of the cell's vertical span, then clamp, tightening line
        # height if the block would still be taller than the cell.
        y_lo, y_hi = _poly_y_span(vertices, x)
        pad = 7.0
        avail = (y_hi - y_lo) - 2 * pad
        if rows and block_h > avail:
            line_h = max(6.0, (avail - rashi_h) / rows)
            block_h = rashi_h + rows * line_h
        centre = (y + (y_lo + y_hi) / 2) / 2
        top = min(max(centre - block_h / 2, y_lo + pad), y_hi - pad - block_h)

        def row_span(row: int) -> tuple[float, float]:
            # Polygon width intersected at the glyphs' top and bottom, so text
            # clears sloped edges whichever way the triangle narrows.
            baseline = top + rashi_h + (row + 0.85) * line_h
            lo1, hi1 = _poly_x_span(vertices, baseline - 0.8 * font)
            lo2, hi2 = _poly_x_span(vertices, baseline + 0.25 * font)
            return max(lo1, lo2), min(hi1, hi2)

        if two_cols:
            # Shrink the font only if the longest name cannot sit two-up in
            # the narrowest planet row (conservative width estimate).
            longest = max(len(p) for p in planets)
            while font > 7.0:
                spans = [row_span(r) for r in range(rows)]
                if all(
                    longest * font * 0.62 <= min(x - lo, hi - x)
                    for lo, hi in spans
                ):
                    break
                font -= 0.5

        if rashi_no:
            lines.append(
                f'<text x="{x}" y="{top + 9}" text-anchor="middle" '
                f'font-size="10" font-weight="700" fill="#b10000">{_h(rashi_no)}</text>'
            )
        for i, planet in enumerate(planets):
            if two_cols:
                # Column centres adapt per row: the midpoint of each half of
                # the polygon's width at this row keeps text off sloped edges.
                py = top + rashi_h + (i // 2 + 0.85) * line_h
                row_lo, row_hi = row_span(i // 2)
                px = (row_lo + x) / 2 if i % 2 == 0 else (x + row_hi) / 2
            else:
                px = x
                py = top + rashi_h + (i + 0.85) * line_h
            lines.append(
                f'<text x="{px}" y="{py}" text-anchor="middle" '
                f'font-size="{font}" fill="#00604a">{_h(planet)}</text>'
            )
    body = "\n".join(lines)
    return (
        f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" '
        f'class="ni-chart" width="{render}" height="{render}">{body}</svg>'
    )


def _cover_motif_svg() -> str:
    """Minimal line-art Ganesha for the cover: deep-red strokes, gold accents,
    transparent background. Static inline SVG so the Chromium PDF path needs
    no external assets; the ReportLab renderer builds its own cover and never
    sees this."""
    return """<svg viewBox="0 0 200 200" width="136" height="136" class="cover-motif"
  xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Ganesha">
  <circle cx="100" cy="92" r="86" fill="none" stroke="#c9a227" stroke-width="2"/>
  <circle cx="100" cy="92" r="79" fill="none" stroke="#c9a227" stroke-width="0.9"/>
  <path d="M 78 52 Q 100 30 122 52" fill="none" stroke="#b10000" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M 86 47 Q 100 36 114 47" fill="none" stroke="#c9a227" stroke-width="1.6" stroke-linecap="round"/>
  <circle cx="100" cy="30" r="3" fill="none" stroke="#c9a227" stroke-width="1.5"/>
  <path d="M 70 62 Q 42 58 38 84 Q 35 108 62 108" fill="none" stroke="#b10000" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M 66 72 Q 52 72 51 88" fill="none" stroke="#c9a227" stroke-width="1.4" stroke-linecap="round"/>
  <path d="M 130 62 Q 158 58 162 84 Q 165 108 138 108" fill="none" stroke="#b10000" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M 134 72 Q 148 72 149 88" fill="none" stroke="#c9a227" stroke-width="1.4" stroke-linecap="round"/>
  <path d="M 70 62 Q 74 50 100 48 Q 126 50 130 62 Q 136 74 132 92 Q 128 106 118 112" fill="none" stroke="#b10000" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M 70 62 Q 64 74 68 92 Q 72 106 82 112" fill="none" stroke="#b10000" stroke-width="2.4" stroke-linecap="round"/>
  <circle cx="86" cy="80" r="2.4" fill="#b10000"/>
  <circle cx="114" cy="80" r="2.4" fill="#b10000"/>
  <path d="M 100 62 L 100 72" stroke="#c9a227" stroke-width="2" stroke-linecap="round"/>
  <path d="M 100 88 Q 96 104 96 116 Q 96 134 108 138 Q 122 142 124 130 Q 125 122 116 122" fill="none" stroke="#b10000" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M 92 106 Q 84 111 84 120" fill="none" stroke="#b10000" stroke-width="2.2" stroke-linecap="round"/>
  <path d="M 76 126 Q 62 148 78 164 Q 100 178 122 164 Q 138 148 124 126" fill="none" stroke="#b10000" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M 96 156 Q 100 160 104 156" fill="none" stroke="#c9a227" stroke-width="1.4" stroke-linecap="round"/>
</svg>"""


def _table(headers: list[str], rows: list[list[str]]) -> str:
    thead = "".join(f"<th>{_h(h)}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{_h(cell)}</td>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        "<table>"
        f"<thead><tr>{thead}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


def _kv_table(rows: list[tuple[str, str]], language: str) -> str:
    return _table(
        [label("field", language), label("value", language)],
        [[key, value] for key, value in rows],
    )


def _planet_rows(kundali: dict, language: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for name in PLANET_ORDER:
        info = kundali["planets"].get(name)
        if not info:
            continue
        rows.append(
            [
                display_planet(name, language),
                display_sign(info["sign"], language),
                str(info["house"]),
                display_nakshatra(f"{info['nakshatra']} pada {info['nakshatra_pada']}", language),
                format_dms(info["degree"]),
            ]
        )
    return rows


def _dasha_timeline_html(dasha: dict, language: str) -> str:
    timeline = (dasha or {}).get("timeline", [])
    if not timeline:
        return ""
    current_maha = ((dasha or {}).get("current") or {}).get("mahadasha")
    segments = []
    for index, row in enumerate(timeline):
        colour = PALETTE[index % len(PALETTE)]
        active = "active" if row["mahadasha"] == current_maha else ""
        segments.append(
            f'<div class="dasha-cell {active}" style="background:{colour}">'
            f'<div class="dasha-name">{_h(display_planet(row["mahadasha"], language))}</div>'
            f'<div class="dasha-dates">{_h(row["start"])}<br/>{_h(row["end"])}</div>'
            "</div>"
        )
    return f'<div class="dasha-bar">{"".join(segments)}</div>'


def _font_face_css() -> str:
    """Embed the bundled Devanagari font so Hindi renders (and shapes maatras)
    correctly on any machine, not just ones with a system Devanagari font."""
    if not _FONT_FILE.exists():
        return ""
    data = base64.b64encode(_FONT_FILE.read_bytes()).decode("ascii")
    return (
        "@font-face { font-family: 'Noto Sans Devanagari'; font-style: normal; "
        "font-weight: 400 700; src: url(data:font/ttf;base64,"
        f"{data}) format('truetype'); }}\n"
    )


def _css() -> str:
    return _font_face_css() + """
    @page { size: A4; margin: 16mm 14mm; }
    * { box-sizing: border-box; }
    body {
        font-family: 'Noto Sans Devanagari', 'Mangal', 'Nirmala UI', 'Lohit Devanagari',
            system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
        color: #1f2937;
        font-size: 11pt;
        line-height: 1.5;
        margin: 0;
        padding: 0;
    }
    h1, h2, h3 { color: #b10000; margin: 0 0 8px 0; }
    h1 { font-size: 26pt; letter-spacing: 0; }
    h2 { font-size: 15pt; border-bottom: 2px solid #d9a441; padding-bottom: 4px; margin-top: 18px; }
    h3 { font-size: 12pt; }
    p { margin: 6px 0; }
    .muted { color: #6b7280; font-size: 10pt; }
    .cover {
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        min-height: 240mm;
        padding: 40px 30px;
        background: linear-gradient(135deg, #fdf7ea 0%, #f4e3c0 100%);
        border: 1px solid #d9a441;
        page-break-after: always;
    }
    .cover h1 { font-size: 32pt; margin-bottom: 12px; }
    .cover .cover-motif { align-self: center; margin-bottom: 20px; }
    .cover .mantra { font-size: 18pt; color: #8d493a; margin: 18px 0; }
    .cover .subtitle { font-size: 11pt; color: #4b5563; margin: 24px 0 36px; }
    .cover .birth-meta { font-size: 14pt; color: #3d405b; margin-top: 28px; }
    .section { page-break-inside: avoid; margin: 16px 0; }
    table { width: 100%; border-collapse: collapse; margin: 8px 0 16px; }
    th { background: #b10000; color: #fff; text-align: left; padding: 6px 10px; font-weight: 600; }
    td { border: 1px solid #e1a5a5; padding: 6px 10px; vertical-align: top; }
    tbody tr:nth-child(even) td { background: #fbfaf5; }
    .ni-wrap { display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap; page-break-inside: avoid; }
    .ni-chart { display: block; page-break-inside: avoid; }
    .ni-caption { color: #6b7280; font-size: 9pt; }
    .dasha-bar { display: flex; flex-wrap: wrap; gap: 2px; margin: 10px 0 12px; page-break-inside: avoid; }
    .dasha-cell { flex: 1 1 18%; color: #fff; padding: 8px 6px; min-height: 64px; border-radius: 3px; font-size: 9pt; }
    .dasha-cell.active { outline: 2px solid #1f2937; outline-offset: -2px; }
    .dasha-name { font-weight: 700; font-size: 10pt; margin-bottom: 2px; }
    .dasha-dates { font-size: 8.5pt; opacity: 0.95; }
    .notice {
        background: #fff7e0;
        border-left: 4px solid #d9a441;
        padding: 8px 12px;
        margin: 10px 0 16px;
        color: #7a5b00;
    }
    .safety {
        background: #fdecec;
        border-left: 4px solid #b10000;
        padding: 10px 14px;
        margin: 14px 0;
    }
    .page-break { page-break-after: always; }
    footer.report-footer {
        position: running(footer);
        font-size: 8pt;
        color: #6b7280;
        text-align: center;
    }
    """


def _pandit_css() -> str:
    return _font_face_css() + """
    @page { size: A4; margin: 12mm 12mm; }
    * { box-sizing: border-box; }
    body {
        font-family: 'Noto Sans Devanagari', 'Mangal', 'Nirmala UI', system-ui, sans-serif;
        color: #1f2937;
        font-size: 11pt;
        line-height: 1.55;
        margin: 0;
        padding: 0;
        background: #fffaf0;
    }
    h1, h2, h3 { color: #b10000; letter-spacing: 0; margin: 0 0 10px; text-align: center; }
    h1 { font-size: 30pt; }
    h2 { font-size: 20pt; }
    h3 { font-size: 13pt; }
    p { margin: 7px 0; }
    table { width: 100%; border-collapse: collapse; margin: 10px 0 16px; }
    th { background: #b10000; color: #fff; padding: 7px 9px; text-align: left; }
    td { border-bottom: 1px solid #efcaca; padding: 6px 8px; vertical-align: top; }
    .pandit-page {
        position: relative;
        min-height: 273mm;
        page-break-after: always;
        padding: 20mm 17mm 18mm;
        background:
            radial-gradient(circle at 18% 9%, rgba(217,164,65,.13), transparent 21%),
            radial-gradient(circle at 85% 92%, rgba(217,164,65,.12), transparent 18%),
            #fffdf7;
        border-left: 7px double #d9a441;
        border-right: 7px double #d9a441;
    }
    .pandit-page::before {
        content: "";
        position: absolute;
        inset: 7mm;
        border: 1px solid rgba(177,0,0,.22);
        pointer-events: none;
    }
    .pandit-client { position: relative; z-index: 1; text-align: center; color: #d00000; font-size: 13pt; margin-bottom: 12mm; }
    .pandit-footer { position: absolute; bottom: 8mm; left: 18mm; right: 18mm; text-align: center; font-size: 9pt; color: #333; border-top: 1px solid #d9a441; padding-top: 5px; }
    .cover-center { min-height: 205mm; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; gap: 14px; }
    .cover-motif { width: 126px; height: 126px; }
    .cover-art { width: 56mm; }
    .name-plate {
        background: #fff6df;
        color: #7a1010;
        border: 2px solid #d9a441;
        outline: 1px solid rgba(177,0,0,.35);
        outline-offset: 4px;
        padding: 17px 40px;
        min-width: 72%;
        font-size: 15pt;
        line-height: 1.7;
    }
    .antar-grid { display: flex; flex-wrap: wrap; gap: 7px; }
    .antar-card { width: 32%; flex: 1 1 31%; border: 1px solid #efd4a7; background: rgba(255,255,255,.74); padding: 5px 7px; page-break-inside: avoid; }
    .antar-card h4 { color: #b10000; margin: 0 0 3px; font-size: 9pt; text-align: center; }
    .antar-card h4 span { display: block; font-weight: 400; color: #7a5b00; font-size: 7pt; }
    .antar-card table { margin: 0; font-size: 7.5pt; line-height: 1.25; }
    .antar-card th { padding: 2px 5px; font-size: 7.5pt; }
    .antar-card td { padding: 1.8px 5px; }
    .mantra { color: #b10000; font-size: 20pt; font-weight: 700; }
    .notice-text { color: #287133; text-align: justify; font-size: 12pt; }
    .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px 28px; }
    .panel { background: rgba(255,255,255,.74); border: 1px solid #efd4a7; padding: 12px; }
    .red { color: #b10000; font-weight: 700; }
    .green { color: #287133; }
    .big-chart .ni-chart { width: 100%; max-width: 540px; height: auto; margin: 0 auto; }
    .chart-pair { display: grid; grid-template-columns: 1fr; gap: 20px; }
    .dasha-bar { display: flex; flex-wrap: wrap; gap: 3px; margin: 12px 0; }
    .dasha-cell { flex: 1 1 18%; color: #fff; padding: 7px; min-height: 58px; border-radius: 2px; font-size: 9pt; }
    .dasha-cell.active { outline: 2px solid #111; outline-offset: -2px; }
    .remedy-list li, .summary-list li { margin: 8px 0; }
    .badge-row { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin: 14px 0; }
    .badge { border: 1px solid #d9a441; padding: 7px 10px; background: #fff6df; color: #7a3f00; }
    """


def _page(
    title: str,
    body: str,
    *,
    client: str,
    footer: str = "जन्म पत्रिका — गणना आधारित प्रारूप",
    show_client: bool = True,
) -> str:
    client_line = f'<div class="pandit-client">{_h(client)}</div>' if show_client else ""
    return (
        '<section class="pandit-page">'
        f"{client_line}"
        f"<h2>{_h(title)}</h2>"
        f"{body}"
        f'<div class="pandit-footer"><strong>{_h(footer)}</strong></div>'
        "</section>"
    )


def _cover_art_html() -> str:
    """Cover art for the patrika, embedded as a data URI. The bundled artwork
    is a red calligraphic Ganesha on a transparent background; drop any
    PNG/JPEG at ``astro/assets/cover_ganesha.*`` to replace it. Falls back to
    the line-art SVG motif if no image is bundled."""
    assets = ROOT.parent / "assets"
    for name, mime in (("cover_ganesha.png", "image/png"), ("cover_ganesha.jpg", "image/jpeg")):
        art = assets / name
        if art.exists():
            data = base64.b64encode(art.read_bytes()).decode("ascii")
            return (
                f'<img class="cover-art" alt="Ganesha" '
                f'src="data:{mime};base64,{data}"/>'
            )
    return _cover_motif_svg()


def _pandit_kv(rows: list[tuple[str, object]]) -> str:
    body = "".join(f"<tr><td>{_h(k)}</td><td><strong>{_h(v)}</strong></td></tr>" for k, v in rows)
    return f"<table><tbody>{body}</tbody></table>"


def _safe_join(values: list[str], fallback: str = "शुभ") -> str:
    return ", ".join(values) if values else fallback


def _phalit_data() -> dict:
    path = ROOT.parent / "data" / "phalit_basic.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _phalit_ext() -> dict:
    path = ROOT.parent / "data" / "phalit_ext.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _current_period_page(dasha: dict | None, language: str, client: str) -> str | None:
    """Narrative reading of the running Mahadasha-Antardasha: themes, mindset,
    and likely challenges, mapped deterministically from classical significations."""
    if not dasha:
        return None
    current = dasha.get("current") or {}
    maha = current.get("mahadasha")
    if not maha:
        return None
    antar = current.get("antardasha")
    ext = _phalit_ext()
    dp = ext.get("dasha_phala", {})
    gn = ext.get("graha_nature", {})
    hi = _is_hi(language)
    dk = "hi" if hi else "en"
    mind_k = "mindset_hi" if hi else "mindset_en"
    chal_k = "challenges_hi" if hi else "challenges_en"
    stop = "।" if hi else "."

    maha_name = display_planet(maha, language)
    antar_name = display_planet(antar, language) if antar else "-"
    period_line = (
        f"{maha_name} {pl('mahadasha', language)} — {antar_name} {pl('antardasha', language)}"
    )
    body = _pandit_kv([
        (pl("running_period", language), period_line),
        (pl("maha_end", language), current.get("mahadasha_end") or "-"),
        (pl("antar_end", language), current.get("antardasha_end") or "-"),
    ])

    theme = dp.get(maha, {}).get(dk, "")
    mind = gn.get(maha, {}).get(mind_k, "")
    chal = gn.get(maha, {}).get(chal_k, "")
    antar_theme = dp.get(antar, {}).get(dk, "") if antar else ""

    panels = []
    if theme:
        panels.append(
            f"<div class='panel'><h3>{_h(pl('period_theme', language))} — {_h(maha_name)}</h3>"
            f"<p>{_h(theme)}</p></div>"
        )
    if mind:
        panels.append(
            f"<div class='panel'><h3>{_h(pl('mindset', language))}</h3><p>{_h(mind)}</p></div>"
        )
    if chal:
        panels.append(
            f"<div class='panel'><h3>{_h(pl('challenges', language))}</h3><p>{_h(chal)}</p></div>"
        )
    if antar_theme and antar and antar != maha:
        first = antar_theme.split(stop)[0].strip()
        panels.append(
            f"<div class='panel'><h3>{_h(pl('antardasha', language))} — {_h(antar_name)}</h3>"
            f"<p>{_h(first)}{stop}</p></div>"
        )

    body += "".join(panels)
    body += f"<p class='green'>{_h(pl('current_note', language))}</p>"
    return _page(pl("current_analysis", language), body, footer=pl("footer", language), client=client)


def _dasha_phala_page(dasha: dict | None, language: str, client: str) -> str | None:
    """Classical general reading for each Mahadasha lord in the timeline."""
    if not dasha:
        return None
    timeline = dasha.get("timeline", [])
    if not timeline:
        return None
    dp = _phalit_ext().get("dasha_phala", {})
    dk = "hi" if _is_hi(language) else "en"
    panels = []
    for row in timeline[:9]:
        lord = row.get("mahadasha")
        text = dp.get(lord, {}).get(dk, "")
        if not text:
            continue
        span = f"{row.get('start', '')} — {row.get('end', '')}"
        panels.append(
            f"<div class='panel'><h3>{_h(display_planet(lord, language))} {_h(pl('mahadasha', language))}"
            f"<span class='panel-span'> ({_h(span)})</span></h3><p>{_h(text)}</p></div>"
        )
    if not panels:
        return None
    body = "".join(panels) + f"<p class='green'>{_h(pl('dasha_phal_note', language))}</p>"
    return _page(pl("dasha_phal_title", language), body, footer=pl("footer", language), client=client)


def _pandit_interpretation_pages(
    kundali: dict,
    dasha: dict | None,
    gochar: dict | None,
    language: str,
    client: str,
) -> list[str]:
    birth = build_basic_report(kundali, dasha=dasha, language=language)["sections"]["birth_chart"]
    doshas = birth.get("doshas") or []
    # The detector can flag the same yoga for several house-lord combinations.
    yogas = list(dict.fromkeys(birth.get("yogas") or []))
    phalit = _phalit_data()
    ext = _phalit_ext()
    hi = _is_hi(language)
    nak_name = kundali.get("nakshatra", "")

    def _phal_text(category: str, key: str) -> str:
        if hi:
            return phalit.get(category, {}).get(key, "")
        return ext.get(f"{category}_en", {}).get(key, "")

    phalit_panels = []
    for label_key, disp, category, key in [
        ("lagna_phal", display_sign(birth["lagna"], language), "lagna", birth["lagna"]),
        ("rashi_phal", display_sign(birth["rashi"], language), "rashi", birth["rashi"]),
        ("nak_phal", display_nakshatra(birth["nakshatra"], language), "nakshatra", nak_name),
    ]:
        text = _phal_text(category, key)
        if text:
            heading = f"{pl(label_key, language)} — {disp}"
            phalit_panels.append(
                f"<div class='panel'><h3>{_h(heading)}</h3><p>{_h(text)}</p></div>"
            )

    pages = [
        _page(
            pl("lrn_phal", language),
            "".join(phalit_panels)
            + f"<p class='green'>{_h(pl('swabhav_note', language))}</p>",
            footer=pl("footer", language),
            client=client,
        ),
        _page(
            pl("yog_dosh", language),
            _pandit_kv([
                (pl("mukhya_yog", language), _safe_join(yogas, pl("no_yog", language))),
                (pl("dosha_flag", language), _safe_join(doshas, pl("no_dosha", language))),
            ])
            + f"<p class='green'>{_h(pl('yog_note', language))}</p>",
            footer=pl("footer", language),
            client=client,
        ),
    ]
    return pages


def _chandra_houses(kundali: dict) -> dict:
    """Whole-sign houses counted from the Moon sign (Chandra kundali)."""
    moon_sign = kundali["planets"]["Chandra"]["sign"]
    moon_idx = SIGN_ORDER.index(moon_sign)
    houses: dict[str, dict] = {}
    for house in range(1, 13):
        sign = SIGN_ORDER[(moon_idx + house - 1) % 12]
        houses[str(house)] = {"sign": sign, "planets": []}
    for name, info in kundali["planets"].items():
        offset = (SIGN_ORDER.index(info["sign"]) - moon_idx) % 12
        houses[str(offset + 1)]["planets"].append(name)
    return houses


def _format_years_hi(years_decimal: object, language: str = "hin") -> str:
    """Render a decimal year span, e.g. '16 yr 4 mo 7 d' / Hindi equivalent."""
    if not isinstance(years_decimal, (int, float)):
        return str(years_decimal)
    from kundali_calculator import duration_to_ymd

    ymd = duration_to_ymd(float(years_decimal))
    parts = []
    if ymd["years"]:
        parts.append(f"{ymd['years']} {pl('years', language)}")
    if ymd["months"]:
        parts.append(f"{ymd['months']} {pl('months', language)}")
    if ymd["days"]:
        parts.append(f"{ymd['days']} {pl('days', language)}")
    return " ".join(parts) or f"0 {pl('days', language)}"


def _birth_panchang(kundali: dict) -> dict | None:
    """Panchang of the birth day/place — the block a janma patrika prints."""
    inp = kundali.get("input", {})
    try:
        from panchang_calculator import PanchangInput, calculate_panchang

        born = datetime.fromisoformat(kundali["calculation"]["datetime_local"])
        return calculate_panchang(PanchangInput(
            date=born.strftime("%Y-%m-%d"),
            place=inp.get("place", ""),
            lat=float(inp["lat"]),
            lon=float(inp["lon"]),
            timezone_name=inp.get("timezone", "Asia/Kolkata"),
        ))
    except Exception:
        return None


def _antar_grid(timeline: list[dict], language: str) -> str:
    cards = []
    for row in timeline[:9]:
        antars = "".join(
            f"<tr><td>{_h(display_planet(a['planet'], language))}</td>"
            f"<td>{_h(a.get('end', '-'))}</td></tr>"
            for a in row.get("antardasha", [])
        )
        cards.append(
            '<div class="antar-card">'
            f"<h4>{_h(display_planet(row['mahadasha'], language))} {_h(pl('mahadasha', language))}"
            f"<span> ({_h(row.get('start', ''))} - {_h(row.get('end', ''))})</span></h4>"
            f"<table><thead><tr><th>{_h(pl('antardasha', language))}</th><th>{_h(pl('end', language))}</th></tr></thead>"
            f"<tbody>{antars}</tbody></table></div>"
        )
    return f'<div class="antar-grid">{"".join(cards)}</div>' 


def _pandit_report_html(
    kundali: dict,
    *,
    dasha: dict | None,
    panchang: dict | None,
    gochar: dict | None,
    language: str,
    client_name: str | None,
) -> str:
    report = build_basic_report(kundali, dasha=dasha, panchang=panchang, language=language)
    birth = report["sections"]["birth_chart"]
    current = report["sections"]["current_dasha"]
    inp = kundali.get("input", {})
    client = _cover_name(kundali, client_name)

    # A janma patrika prints the birth-day panchang, not today's.
    janma = _birth_panchang(kundali)
    daily = report["sections"]["daily_panchang"]
    if janma:
        from report_generator import build_panchang_section

        daily = build_panchang_section(janma)

    from avakahada import compute_avakahada

    ava = compute_avakahada(
        kundali,
        sunrise=(janma or {}).get("panchang", {}).get("sunrise"),
        sunset=(janma or {}).get("panchang", {}).get("sunset"),
    )

    cover = _page(
        "",
        '<div class="cover-center">'
        f"{_cover_art_html()}"
        '<div class="mantra">ॐ गं गणपतये नमः</div>'
        f"<h1>{_h(pl('janma_patrika', language))}</h1>"
        f'<div class="badge-row"><span class="badge">{_h(pl("badge", language))}</span></div>'
        f'<div class="name-plate"><strong>{_h(client)}</strong><br/>{_h(inp.get("dob", ""))} | {_h(inp.get("tob", ""))}<br/>{_h(inp.get("place", ""))}</div>'
        "</div>",
        footer=pl("footer", language),
        client=client,
        show_client=False,
    )
    notice = _page(
        pl("notice_title", language),
        f"<p class='notice-text'>{_h(pl('notice_1', language))}</p>"
        f"<p class='notice-text'>{_h(pl('notice_2', language))}</p>",
        footer=pl("footer", language),
        client=client,
    )
    ava_rows = [
        (pl("ava_lagna", language), f'{display_sign(birth["lagna"], language)} - {ava["lagna_lord_hi"] if _is_hi(language) else ava["lagna_lord"]}'),
        (pl("ava_rashi", language), f'{display_sign(birth["rashi"], language)} - {ava["rashi_lord_hi"] if _is_hi(language) else ava["rashi_lord"]}'),
        (pl("ava_nak", language), display_nakshatra(birth["nakshatra"], language)),
        (pl("ava_naklord", language), ava["nakshatra_lord_hi"] if _is_hi(language) else ava["nakshatra_lord"]),
        (pl("gan", language), ava["gan"]),
        (pl("yoni", language), ava["yoni"]),
        (pl("nadi", language), ava["nadi"]),
        (pl("varna", language), ava["varna"]),
        (pl("vashya", language), ava["vashya"]),
        (pl("tatva", language), ava["tatva"]),
        (pl("paya", language), ava["paya"]),
        (pl("namakshar", language), ava["namakshar"]),
    ]
    if ava.get("ishta_ghati"):
        ava_rows.append((pl("ishta", language), ava["ishta_ghati"]))
    if ava.get("dinamaan"):
        ava_rows.append((pl("dinamaan", language), ava["dinamaan"]))
    birth_page = _page(
        pl("birth_details", language),
        _pandit_kv([
            (pl("name", language), client),
            (pl("birth_place", language), birth["birth_place"]),
            (pl("birth_dt", language), f'{inp.get("dob", "")} | {inp.get("tob", "")}'),
            (pl("moon_house", language), birth["moon_house"]),
            (pl("dosha_flag", language), _safe_join(birth["doshas"], pl("no_dosha", language))),
        ])
        + f"<h3>{_h(pl('avakahada', language))}</h3>"
        + _pandit_kv(ava_rows),
        footer=pl("footer", language),
        client=client,
    )
    panchang_page = _page(
        pl("janma_panchang", language),
        _pandit_kv([
            (pl("date", language), daily["date"] if daily else "-"),
            (pl("place", language), daily["place"] if daily else "-"),
            (pl("vara", language), display_term(daily["vara"], language) if daily else "-"),
            (pl("tithi", language), display_term(daily["tithi"], language) if daily else "-"),
            (pl("nakshatra", language), display_nakshatra(daily["nakshatra"], language) if daily else "-"),
            (pl("yoga", language), display_term(daily["yoga"], language) if daily else "-"),
            (pl("karana", language), display_term(daily["karana"], language) if daily else "-"),
            (pl("sunrise", language), format_time(daily["sunrise"]) if daily else "-"),
            (pl("sunset", language), format_time(daily["sunset"]) if daily else "-"),
        ]),
        footer=pl("footer", language),
        client=client,
    )
    chart_pages = [
        _page(pl("lagna_kundali", language), f'<div class="big-chart">{_ni_chart_svg(kundali, language)}</div>', footer=pl("footer", language), client=client),
        _page(pl("chandra_kundali", language), f'<div class="big-chart">{_ni_chart_svg({"houses": _chandra_houses(kundali)}, language)}</div><p class="green">{_h(pl("chandra_note", language))}</p>', footer=pl("footer", language), client=client),
    ]
    if kundali.get("navamsa"):
        chart_pages.append(
            _page(pl("navamsa", language), f'<div class="big-chart">{_ni_chart_svg({"houses": kundali["navamsa"]["houses"]}, language)}</div>', footer=pl("footer", language), client=client)
        )

    planet_rows = _planet_rows(kundali, language)
    planet_pages = [
        _page(pl("graha_sthiti", language), _table([label("planet", language), label("sign", language), label("house", language), label("nakshatra", language), label("degree", language)], planet_rows), footer=pl("footer", language), client=client),
    ]
    dasha_pages = []
    if current:
        timeline = (dasha or {}).get("timeline", [])
        maha_rows = [
            [
                display_planet(row["mahadasha"], language),
                row.get("start", "-"),
                row.get("end", "-"),
                _format_years_hi(row.get("duration_years", "-"), language),
            ]
            for row in timeline[:9]
        ]
        dasha_pages = [
            _page(pl("dasha_table", language), _dasha_timeline_html(dasha or {}, language) + _pandit_kv([
                (pl("paddhati", language), current["system"]),
                (pl("dasha_beej", language), display_dasha_value(current["seed"], language)),
                (pl("vartaman_dasha", language), display_dasha_value(current["period"] or "-", language)),
                (pl("maha_end", language), current["mahadasha_end"] or "-"),
                (pl("antar_end", language), current["antardasha_end"] or "-"),
                (pl("praty_end", language), current.get("pratyantardasha_end") or "-"),
            ]) + _table([pl("mahadasha", language), pl("start", language), pl("end", language), pl("duration", language)], maha_rows), footer=pl("footer", language), client=client),
            _page(pl("antar_table", language), _antar_grid(timeline, language), footer=pl("footer", language), client=client),
        ]

    interpretation_pages = [
        p for p in (
            _current_period_page(dasha, language, client),
            _dasha_phala_page(dasha, language, client),
        ) if p
    ]

    pages = [
        cover,
        notice,
        birth_page,
        panchang_page,
        *chart_pages,
        *planet_pages,
        *dasha_pages,
        *interpretation_pages,
        *_pandit_interpretation_pages(kundali, dasha, gochar, language, client),
    ]
    return (
        "<!DOCTYPE html>"
        f'<html lang="{"hi" if _is_hi(language) else "en"}">'
        "<head><meta charset='utf-8'/>"
        f"<title>{_h(client)} - {_h(pl('janma_patrika', language))}</title><style>{_pandit_css()}</style></head>"
        f"<body>{''.join(pages)}</body></html>"
    )


def build_html(
    kundali: dict,
    *,
    dasha: dict | None = None,
    panchang: dict | None = None,
    gochar: dict | None = None,
    language: str = "hin",
    client_name: str | None = None,
    template: str = "standard",
) -> str:
    """Compose the self-contained HTML document for the report."""
    if template == "pandit_v1":
        return _pandit_report_html(
            kundali,
            dasha=dasha,
            panchang=panchang,
            gochar=gochar,
            language=language,
            client_name=client_name,
        )
    if template != "standard":
        raise ValueError("template must be one of: standard, pandit_v1")
    report = build_basic_report(kundali, dasha=dasha, panchang=panchang, language=language)
    birth = report["sections"]["birth_chart"]
    current = report["sections"]["current_dasha"]
    daily = report["sections"]["daily_panchang"]
    inp = kundali.get("input", {})
    cover_name = _cover_name(kundali, client_name)

    cover = (
        '<section class="cover">'
        f"{_cover_motif_svg()}"
        f'<h1>{_h(label("title", language))}</h1>'
        f'<div class="mantra">{_h(label("cover_mantra", language))}</div>'
        f'<div class="subtitle">{_h(label("subtitle", language))}</div>'
        f'<div class="birth-meta"><strong>{_h(cover_name)}</strong></div>'
        f'<div class="birth-meta">{_h(inp.get("dob", ""))} | {_h(inp.get("tob", ""))}</div>'
        f'<div class="birth-meta">'
        f'{_h(label("lagna", language))}: {_h(display_sign(birth["lagna"], language))} | '
        f'{_h(label("rashi", language))}: {_h(display_sign(birth["rashi"], language))} | '
        f'{_h(label("nakshatra", language))}: {_h(display_nakshatra(birth["nakshatra"], language))}'
        f"</div>"
        "</section>"
    )

    notice_block = (
        f'<div class="notice"><strong>{_h(label("notice_title", language))}:</strong> '
        f'{_h(label("notice", language))}</div>'
    )

    birth_kv = _kv_table(
        [
            (label("birth_place", language), birth["birth_place"]),
            (label("birth_datetime", language), birth["birth_datetime_local"]),
            (label("lagna", language), display_sign(birth["lagna"], language)),
            (label("rashi", language), display_sign(birth["rashi"], language)),
            (label("nakshatra", language), display_nakshatra(birth["nakshatra"], language)),
            (
                label("doshas", language),
                ", ".join(birth["doshas"]) if birth["doshas"] else "—",
            ),
        ],
        language,
    )

    planet_table = _table(
        [
            label("planet", language),
            label("sign", language),
            label("house", language),
            label("nakshatra", language),
            label("degree", language),
        ],
        _planet_rows(kundali, language),
    )

    sections: list[str] = [
        cover,
        '<section class="section">'
        f'<h2>{_h(label("birth_details", language))}</h2>'
        f"{notice_block}{birth_kv}"
        "</section>",
        '<section class="section">'
        f'<h2>{_h(label("planet_chart", language))}</h2>'
        '<div class="ni-wrap">'
        f"{_ni_chart_svg(kundali, language)}"
        f'<div><h3>{_h(label("planet_table", language))}</h3>{planet_table}</div>'
        "</div>"
        "</section>",
    ]

    if kundali.get("navamsa"):
        sections.append(
            '<section class="section">'
            f'<h2>{_h(label("navamsa_chart", language))}</h2>'
            '<div class="ni-wrap">'
            f"{_ni_chart_svg({'houses': kundali['navamsa']['houses']}, language)}"
            "</div>"
            "</section>"
        )

    if current:
        timeline_html = _dasha_timeline_html(dasha or {}, language)
        dasha_kv = _kv_table(
            [
                (label("system", language), display_dasha_value(current["system"], language)),
                (label("seed", language), display_dasha_value(current["seed"], language)),
                (label("current_period", language), display_dasha_value(current["period"] or "—", language)),
                (label("mahadasha_end", language), current["mahadasha_end"] or "—"),
                (label("antardasha_end", language), current["antardasha_end"] or "—"),
                (label("pratyantardasha_end", language), current.get("pratyantardasha_end") or "—"),
            ],
            language,
        )
        sections.append(
            '<section class="section">'
            f'<h2>{_h(label("dasha", language))}</h2>'
            f"{timeline_html}{dasha_kv}"
            "</section>"
        )

    if daily:
        sections.append(
            '<section class="section">'
            f'<h2>{_h(label("panchang", language))}</h2>'
            + _kv_table(
                [
                    (label("date", language), daily["date"]),
                    (label("place", language), daily["place"]),
                    (label("vara", language), display_term(daily["vara"], language)),
                    (label("tithi", language), display_term(daily["tithi"], language)),
                    (label("nakshatra", language), display_nakshatra(daily["nakshatra"], language)),
                    (label("yoga", language), display_term(daily["yoga"], language)),
                    (label("karana", language), display_term(daily["karana"], language)),
                    (label("sunrise", language), format_time(daily["sunrise"])),
                    (label("sunset", language), format_time(daily["sunset"])),
                ],
                language,
            )
            + "</section>"
        )

    notes = report.get("notes", [])
    safety_items = "".join(f'<div class="safety">{_h(note)}</div>' for note in notes)
    sections.append(
        '<section class="section">'
        f'<h2>{_h(label("safety", language))}</h2>'
        f"{safety_items}"
        "</section>"
    )

    return (
        "<!DOCTYPE html>"
        f'<html lang="{"hi" if _is_hi(language) else "en"}">'
        "<head>"
        '<meta charset="utf-8"/>'
        f'<title>{_h(label("title", language))}</title>'
        f"<style>{_css()}</style>"
        "</head>"
        f'<body>{"".join(sections)}</body>'
        "</html>"
    )


def chromium_available() -> bool:
    """Return ``True`` only if Playwright + a usable Chromium binary are present."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch()
            except Exception:
                return False
            browser.close()
            return True
    except Exception:
        return False


_CHROMIUM_INSTALL_HINT = (
    "Chromium browser is not installed for Playwright. "
    "Install it with: python -m playwright install chromium"
)


def render_html_to_pdf(html_text: str, output_path: Path) -> Path:
    """Rasterise ``html_text`` to ``output_path`` using Playwright/Chromium."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Add it via `pip install playwright` "
            "then run `python -m playwright install chromium`."
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Allow pointing at a pre-installed Chromium (e.g. a managed image that ships
    # one outside Playwright's own cache) so rendering does not require a
    # download. Empty/unset -> Playwright's bundled resolution.
    executable = os.environ.get("ASTRO_CHROMIUM_EXECUTABLE") or None
    launch_kwargs = {"executable_path": executable} if executable else {}
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(**launch_kwargs)
        except Exception as exc:
            raise RuntimeError(_CHROMIUM_INSTALL_HINT) from exc
        try:
            page = browser.new_page()
            page.set_content(html_text, wait_until="load")
            page.pdf(
                path=str(output_path),
                format="A4",
                print_background=True,
                margin={"top": "14mm", "bottom": "14mm", "left": "14mm", "right": "14mm"},
            )
        finally:
            browser.close()
    return output_path


def build_html_pdf_report(
    kundali: dict,
    *,
    dasha: dict | None = None,
    panchang: dict | None = None,
    gochar: dict | None = None,
    output_path: Path,
    language: str = "hin",
    client_name: str | None = None,
    template: str = "standard",
) -> Path:
    """End-to-end: compose HTML, render to PDF, return the output path."""
    document = build_html(
        kundali,
        dasha=dasha,
        panchang=panchang,
        gochar=gochar,
        language=language,
        client_name=client_name,
        template=template,
    )
    return render_html_to_pdf(document, output_path)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Render a Vedic astrology PDF via the HTML/Chromium pipeline."
    )
    parser.add_argument("--kundali-json", required=True, help="Path to kundali JSON")
    parser.add_argument("--dasha-json", help="Optional path to dasha JSON")
    parser.add_argument("--panchang-json", help="Optional path to panchang JSON")
    parser.add_argument("--gochar-json", help="Optional path to gochar JSON")
    parser.add_argument("--output", required=True, help="Output PDF path")
    parser.add_argument("--language", choices=["hin", "hi", "en"], default="hin")
    parser.add_argument("--client-name", help="Client/native name shown on the cover page")
    parser.add_argument("--template", choices=["standard", "pandit_v1"], default="standard")
    args = parser.parse_args(argv)

    out = build_html_pdf_report(
        _load_json(Path(args.kundali_json)),
        dasha=_load_json(Path(args.dasha_json)) if args.dasha_json else None,
        panchang=_load_json(Path(args.panchang_json)) if args.panchang_json else None,
        gochar=_load_json(Path(args.gochar_json)) if args.gochar_json else None,
        output_path=Path(args.output),
        language=args.language,
        client_name=args.client_name,
        template=args.template,
    )
    print(f"Wrote HTML/Chromium PDF report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
