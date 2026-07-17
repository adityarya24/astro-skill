#!/usr/bin/env python
"""Render astrology report JSON into a PDF with charts."""
from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        Flowable,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError as exc:  # HTML renderer should not require ReportLab.
    _REPORTLAB_IMPORT_ERROR = exc
    colors = None
    A4 = None
    ParagraphStyle = None
    getSampleStyleSheet = None
    inch = 72
    pdfmetrics = None
    TTFont = None
    Flowable = object
    PageBreak = None
    Paragraph = None
    SimpleDocTemplate = None
    Spacer = None
    Table = None
    TableStyle = None
else:
    _REPORTLAB_IMPORT_ERROR = None

try:
    from .report_generator import build_basic_report
except ImportError:  # pragma: no cover - direct script execution path.
    from report_generator import build_basic_report

PAGE_MARGIN = 0.55 * inch
PLANET_ORDER = ["Surya", "Chandra", "Mangal", "Budh", "Guru", "Shukra", "Shani", "Rahu", "Ketu"]
HINDI_FONT = "NotoSansDevanagari"
HINDI_FONT_BOLD = "NotoSansDevanagari-Bold"
_FONT_DIR = Path(__file__).resolve().parent / "fonts"

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

HI_MISC = {
    "Vimshottari": "विंशोत्तरी",
}

HI_LABELS = {
    "title": "जन्म कुंडली रिपोर्ट",
    "subtitle": "पंडित जी समीक्षा हेतु गणना-आधारित प्रारूप",
    "cover_mantra": "ॐ गं गणपतये नमः",
    "notice_title": "सूचना",
    "notice": (
        "यह रिपोर्ट जन्म विवरण और ग्रह गणना पर आधारित है। अंतिम व्याख्या और "
        "सलाह पंडित जी के विवेक से ही मान्य होगी।"
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


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def register_fonts() -> tuple[str, str]:
    bundled = _FONT_DIR / "NotoSansDevanagari.ttf"
    if bundled.exists():
        pdfmetrics.registerFont(TTFont(HINDI_FONT, str(bundled)))
        pdfmetrics.registerFont(TTFont(HINDI_FONT_BOLD, str(bundled)))
        return HINDI_FONT, HINDI_FONT_BOLD
    return "Helvetica", "Helvetica-Bold"


def short_planet(name: str) -> str:
    return {
        "Surya": "Su",
        "Chandra": "Mo",
        "Mangal": "Ma",
        "Budh": "Me",
        "Guru": "Ju",
        "Shukra": "Ve",
        "Shani": "Sa",
        "Rahu": "Ra",
        "Ketu": "Ke",
    }.get(name, name[:2])


def display_planet(name: str, language: str) -> str:
    return HI_PLANETS.get(name, name) if language in {"hi", "hin"} else name


def display_sign(name: str, language: str) -> str:
    if language not in {"hi", "hin"}:
        return name
    return f"{HI_SIGNS.get(name, name)} ({name})"


def display_nakshatra(value: str, language: str) -> str:
    if language not in {"hi", "hin"}:
        return value
    updated = value
    for english, hindi in HI_NAKSHATRAS.items():
        updated = updated.replace(english, f"{hindi} ({english})")
    updated = updated.replace("pada", "चरण").replace(" p", " चरण ")
    return updated


def _replace_longest_first(value: str, mapping: dict) -> str:
    # Replace longer keys first so substrings (e.g. "Shani" inside "Shanivara",
    # "Siddha" vs "Siddhi") do not corrupt longer matches.
    for english in sorted(mapping, key=len, reverse=True):
        value = value.replace(english, mapping[english])
    return value


def display_term(value: str, language: str) -> str:
    if language not in {"hi", "hin"}:
        return value
    return _replace_longest_first(value, {**HI_TERMS, **HI_NAKSHATRAS, **HI_YOGAS, **HI_KARANAS, **HI_MISC})


def display_dasha_value(value: str, language: str) -> str:
    """Translate dasha strings that mix system names, planets and nakshatras."""
    if language not in {"hi", "hin"} or not value:
        return value
    return _replace_longest_first(value, {**HI_MISC, **HI_NAKSHATRAS, **HI_PLANETS})


def format_dms(degree: float) -> str:
    """Format a within-sign degree as degrees-minutes, e.g. 8.7626 -> 8°45'."""
    total_minutes = round(float(degree) * 60)
    deg, minutes = divmod(total_minutes, 60)
    return f"{deg}°{minutes:02d}'"


def format_time(value: str | None) -> str:
    """Reduce an ISO datetime to local HH:MM, e.g. ...T05:23:59+05:30 -> 05:24."""
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).strftime("%H:%M")
    except ValueError:
        return value


def rl_escape(value: object) -> str:
    """Escape free text for a ReportLab ``Paragraph``.

    ReportLab parses Paragraph text as XML-like markup, so an unescaped ``<``
    or ``&`` in a user-supplied field (e.g. a place name) can raise a parse
    error or mis-render. Table cells are drawn literally and need no escaping.
    """
    return html.escape(str(value), quote=True)


def cover_name(kundali: dict, client_name: str | None) -> str:
    inp = kundali.get("input", {})
    return (
        client_name
        or inp.get("client_name")
        or inp.get("name")
        or inp.get("place", "")
    )


def display_label(key: str, language: str) -> str:
    if language in {"hi", "hin"}:
        return HI_LABELS[key]
    return {
        "title": "Basic Astrology Report",
        "subtitle": "Calculation draft for astrologer/operator review",
        "notice_title": "Notice",
        "notice": "This report is calculation-first. The reviewing astrologer or operator remains the final authority.",
        "birth_details": "Birth Summary",
        "field": "Field",
        "value": "Value",
        "birth_place": "Birth place",
        "birth_datetime": "Birth datetime",
        "lagna": "Lagna",
        "rashi": "Rashi",
        "nakshatra": "Nakshatra",
        "doshas": "Doshas flagged",
        "planet_chart": "Lagna Chart",
        "navamsa_chart": "Navamsa Chart (D9)",
        "planet_table": "Planet Chart",
        "planet": "Planet",
        "sign": "Sign",
        "house": "House",
        "degree": "Degree",
        "dasha": "Dasha Timeline",
        "system": "System",
        "seed": "Seed",
        "current_period": "Current period",
        "mahadasha_end": "Mahadasha end",
        "antardasha_end": "Antardasha end",
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
    }[key]


class PageFrame:
    def __init__(self, title: str, regular_font: str, bold_font: str):
        self.title = title
        self.regular_font = regular_font
        self.bold_font = bold_font

    def __call__(self, canvas, doc) -> None:
        width, height = A4
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D9A441"))
        canvas.setLineWidth(1)
        canvas.rect(0.36 * inch, 0.34 * inch, width - 0.72 * inch, height - 0.68 * inch)
        canvas.setStrokeColor(colors.HexColor("#F0DDA8"))
        canvas.setLineWidth(3)
        canvas.rect(0.42 * inch, 0.40 * inch, width - 0.84 * inch, height - 0.80 * inch)

        canvas.setFillColor(colors.HexColor("#EFE3C8"))
        canvas.circle(0.8 * inch, height - 0.85 * inch, 0.38 * inch, stroke=0, fill=1)
        canvas.circle(width - 0.8 * inch, 0.85 * inch, 0.38 * inch, stroke=0, fill=1)

        canvas.setFont(self.bold_font, 9)
        canvas.setFillColor(colors.HexColor("#B10000"))
        canvas.drawCentredString(width / 2, height - 0.45 * inch, self.title)
        canvas.setFont(self.regular_font, 8)
        canvas.setFillColor(colors.HexColor("#3D405B"))
        canvas.drawCentredString(width / 2, 0.25 * inch, f"Astro Skill Report | Page {doc.page}")
        canvas.restoreState()


class PlanetChart(Flowable):
    """A compact whole-sign house chart with planets placed by house."""

    def __init__(self, kundali: dict, width: float = 7.0 * inch, height: float = 3.3 * inch):
        super().__init__()
        self.kundali = kundali
        self.width = width
        self.height = height

    def draw(self) -> None:
        canvas = self.canv
        cell_w = self.width / 4
        cell_h = self.height / 3
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#3D405B"))
        canvas.setLineWidth(0.8)
        canvas.setFillColor(colors.HexColor("#F8F7F2"))
        canvas.rect(0, 0, self.width, self.height, fill=1, stroke=1)

        for column in range(1, 4):
            canvas.line(column * cell_w, 0, column * cell_w, self.height)
        for row in range(1, 3):
            canvas.line(0, row * cell_h, self.width, row * cell_h)

        house_positions = {
            "1": (1, 2),
            "2": (2, 2),
            "3": (3, 2),
            "4": (3, 1),
            "5": (3, 0),
            "6": (2, 0),
            "7": (1, 0),
            "8": (0, 0),
            "9": (0, 1),
            "10": (0, 2),
            "11": (1, 1),
            "12": (2, 1),
        }

        canvas.setFont("Helvetica-Bold", 8)
        for house, (column, row) in house_positions.items():
            x = column * cell_w
            y = row * cell_h
            data = self.kundali["houses"][house]
            planets = [
                short_planet(name)
                for name in PLANET_ORDER
                if name in data.get("planets", [])
            ]
            canvas.setFillColor(colors.HexColor("#3D405B"))
            canvas.drawString(x + 6, y + cell_h - 12, f"H{house} {data['sign']}")
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#222222"))
            canvas.drawString(x + 6, y + cell_h - 27, ", ".join(planets) if planets else "-")
            canvas.setFont("Helvetica-Bold", 8)

        canvas.setFont("Helvetica-Bold", 10)
        canvas.setFillColor(colors.HexColor("#8D493A"))
        canvas.drawCentredString(self.width / 2, self.height / 2 - 4, f"Lagna: {self.kundali['lagna']}")
        canvas.restoreState()


class NorthIndianChart(Flowable):
    """Reference-style North Indian chart, with signs and planets placed by house."""

    def __init__(
        self,
        kundali: dict,
        *,
        language: str,
        regular_font: str,
        bold_font: str,
        width: float = 3.1 * inch,
        height: float = 3.1 * inch,
    ):
        super().__init__()
        self.kundali = kundali
        self.language = language
        self.regular_font = regular_font
        self.bold_font = bold_font
        self.width = width
        self.height = height

    def draw(self) -> None:
        canvas = self.canv
        w = self.width
        h = self.height
        cx = w / 2
        cy = h / 2
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D21F1F"))
        canvas.setLineWidth(1.1)
        canvas.rect(0, 0, w, h)
        canvas.line(0, 0, w, h)
        canvas.line(0, h, w, 0)
        canvas.line(cx, 0, 0, cy)
        canvas.line(0, cy, cx, h)
        canvas.line(cx, h, w, cy)
        canvas.line(w, cy, cx, 0)

        positions = {
            "1": (cx, cy + 33),
            "2": (cx - 42, cy + 12),
            "3": (cx - 76, cy + 36),
            "4": (cx - 42, cy - 12),
            "5": (cx - 76, cy - 44),
            "6": (cx - 28, cy - 72),
            "7": (cx, cy - 28),
            "8": (cx + 28, cy - 72),
            "9": (cx + 76, cy - 44),
            "10": (cx + 42, cy - 12),
            "11": (cx + 76, cy + 36),
            "12": (cx + 42, cy + 12),
        }
        canvas.setFont(self.bold_font, 7)
        for house, (x, y) in positions.items():
            data = self.kundali["houses"][house]
            planets = [
                display_planet(name, self.language)
                for name in PLANET_ORDER
                if name in data.get("planets", [])
            ]
            canvas.setFillColor(colors.HexColor("#B10000"))
            canvas.drawCentredString(x, y + 8, house)
            canvas.setFillColor(colors.HexColor("#4B0082"))
            canvas.setFont(self.regular_font, 6.8)
            canvas.drawCentredString(x, y - 1, HI_SIGNS.get(data["sign"], data["sign"]))
            canvas.setFillColor(colors.HexColor("#00806B"))
            canvas.drawCentredString(x, y - 12, ", ".join(planets) if planets else "-")
            canvas.setFont(self.bold_font, 7)
        canvas.restoreState()


class DashaTimeline(Flowable):
    """Horizontal current and upcoming Vimshottari mahadasha timeline."""

    def __init__(
        self,
        dasha: dict,
        *,
        language: str,
        regular_font: str,
        bold_font: str,
        width: float = 7.0 * inch,
        height: float = 1.6 * inch,
    ):
        super().__init__()
        self.dasha = dasha
        self.language = language
        self.regular_font = regular_font
        self.bold_font = bold_font
        self.width = width
        self.height = height

    def draw(self) -> None:
        canvas = self.canv
        timeline = self.dasha.get("timeline", [])[:5]
        if not timeline:
            return

        canvas.saveState()
        canvas.setFont(self.bold_font, 8)
        canvas.setFillColor(colors.HexColor("#3D405B"))
        canvas.drawString(0, self.height - 10, display_label("dasha", self.language))

        x = 0
        y = 42
        segment_w = self.width / len(timeline)
        palette = [
            colors.HexColor("#7A9E7E"),
            colors.HexColor("#D9A441"),
            colors.HexColor("#8D493A"),
            colors.HexColor("#577590"),
            colors.HexColor("#B56576"),
        ]
        current_maha = (self.dasha.get("current") or {}).get("mahadasha")

        for index, row in enumerate(timeline):
            canvas.setFillColor(palette[index % len(palette)])
            canvas.rect(x, y, segment_w, 18, fill=1, stroke=0)
            if row["mahadasha"] == current_maha:
                canvas.setStrokeColor(colors.black)
                canvas.setLineWidth(1.4)
                canvas.rect(x, y - 1, segment_w, 20, fill=0, stroke=1)
            canvas.setFillColor(colors.black)
            canvas.setFont(self.bold_font, 7)
            canvas.drawString(x + 3, y + 24, display_planet(row["mahadasha"], self.language))
            canvas.setFont(self.regular_font, 6.2)
            canvas.drawString(x + 3, y - 12, row["start"])
            canvas.drawString(x + 3, y - 22, row["end"])
            x += segment_w

        current = self.dasha.get("current") or {}
        maha = display_planet(current.get("mahadasha") or "-", self.language)
        antar = display_planet(current.get("antardasha") or "-", self.language)
        canvas.setFont(self.bold_font, 8)
        canvas.setFillColor(colors.HexColor("#222222"))
        canvas.drawString(0, 8, f"{display_label('current_period', self.language)}: {maha}/{antar}")
        canvas.restoreState()


def table_style(regular_font: str = "Helvetica", bold_font: str = "Helvetica-Bold") -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#B10000")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FBFAF5")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#E1A5A5")),
            ("FONTNAME", (0, 0), (-1, 0), bold_font),
            ("FONTNAME", (0, 1), (0, -1), bold_font),
            ("FONTNAME", (1, 1), (-1, -1), regular_font),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
    )


def add_kv_table(
    story: list,
    rows: list[tuple[str, str]],
    *,
    language: str,
    regular_font: str,
    bold_font: str,
    col_widths: list[float] | None = None,
) -> None:
    data = [
        [display_label("field", language), display_label("value", language)],
        *[[key, value] for key, value in rows],
    ]
    table = Table(data, colWidths=col_widths or [1.8 * inch, 4.9 * inch])
    table.setStyle(table_style(regular_font, bold_font))
    story.append(table)
    story.append(Spacer(1, 0.16 * inch))


def build_planet_rows(kundali: dict, language: str) -> list[list[str]]:
    rows = [
        [
            display_label("planet", language),
            display_label("sign", language),
            display_label("house", language),
            display_label("nakshatra", language),
            display_label("degree", language),
        ]
    ]
    for planet in PLANET_ORDER:
        info = kundali["planets"][planet]
        rows.append(
            [
                display_planet(planet, language),
                display_sign(info["sign"], language),
                str(info["house"]),
                display_nakshatra(f"{info['nakshatra']} p{info['nakshatra_pada']}", language),
                format_dms(info["degree"]),
            ]
        )
    return rows


DEFAULT_RENDERER = "html"
LEGACY_RENDERER = "reportlab"
SUPPORTED_RENDERERS = (DEFAULT_RENDERER, LEGACY_RENDERER)


def build_pdf_report(
    kundali: dict,
    *,
    dasha: dict | None = None,
    panchang: dict | None = None,
    gochar: dict | None = None,
    gochar_narrative: dict | None = None,
    output_path: Path,
    language: str = "hin",
    renderer: str = DEFAULT_RENDERER,
    client_name: str | None = None,
    template: str = "standard",
    synthesis: dict | None = None,
) -> Path:
    """Build a PDF astrology report.

    ``renderer="html"`` (default) uses the HTML/Chromium pipeline in
    :mod:`html_pdf_report` for polished Devanagari shaping. ``"reportlab"``
    keeps the legacy in-process ReportLab path as a fallback when Chromium is
    not installed.
    """
    if renderer not in SUPPORTED_RENDERERS:
        raise ValueError(
            f"Unknown renderer {renderer!r}. Supported: {SUPPORTED_RENDERERS}"
        )
    if renderer == DEFAULT_RENDERER:
        try:
            from .html_pdf_report import build_html_pdf_report
        except ImportError:  # pragma: no cover - direct script execution path.
            from html_pdf_report import build_html_pdf_report
        return build_html_pdf_report(
            kundali,
            dasha=dasha,
            panchang=panchang,
            gochar=gochar,
            gochar_narrative=gochar_narrative,
            output_path=output_path,
            language=language,
            client_name=client_name,
            template=template,
            synthesis=synthesis,
        )
    if template != "standard":
        raise ValueError("template='pandit_v1' requires renderer='html'")
    return _build_reportlab_pdf_report(
        kundali,
        dasha=dasha,
        panchang=panchang,
        output_path=output_path,
        language=language,
        client_name=client_name,
    )


def _build_reportlab_pdf_report(
    kundali: dict,
    *,
    dasha: dict | None = None,
    panchang: dict | None = None,
    output_path: Path,
    language: str = "hin",
    client_name: str | None = None,
) -> Path:
    if _REPORTLAB_IMPORT_ERROR is not None:
        raise RuntimeError(
            "ReportLab renderer requires the reportlab package. Install it or "
            "use renderer='html'."
        ) from _REPORTLAB_IMPORT_ERROR

    output_path.parent.mkdir(parents=True, exist_ok=True)
    regular_font, bold_font = register_fonts()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=PAGE_MARGIN,
        leftMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN,
        bottomMargin=PAGE_MARGIN,
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="HindiBody",
            parent=styles["BodyText"],
            fontName=regular_font,
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#1F6F2B"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallNote",
            parent=styles["BodyText"],
            fontName=regular_font,
            fontSize=8.5,
            leading=11,
        )
    )
    title_style = styles["Title"]
    title_style.fontName = bold_font
    title_style.textColor = colors.HexColor("#3D405B")
    heading = styles["Heading2"]
    heading.fontName = bold_font
    heading.textColor = colors.HexColor("#B10000")

    report = build_basic_report(kundali, dasha=dasha, panchang=panchang, language=language)
    birth = report["sections"]["birth_chart"]
    current = report["sections"]["current_dasha"]
    daily = report["sections"]["daily_panchang"]

    story: list = [
        Paragraph(display_label("title", language), title_style),
        Spacer(1, 0.12 * inch),
        Paragraph(HI_LABELS["cover_mantra"] if language in {"hi", "hin"} else "Om Gan Ganapataye Namah", heading),
        Spacer(1, 0.2 * inch),
        Paragraph(display_label("subtitle", language), styles["SmallNote"]),
        Spacer(1, 0.35 * inch),
        Paragraph(display_label("notice_title", language), heading),
        Paragraph(display_label("notice", language), styles["HindiBody"]),
        Spacer(1, 0.35 * inch),
        Paragraph(rl_escape(cover_name(kundali, client_name)), heading),
        Paragraph(f"{rl_escape(kundali['input']['dob'])} | {rl_escape(kundali['input']['tob'])}", title_style),
        PageBreak(),
        Paragraph(display_label("birth_details", language), heading),
        Spacer(1, 0.18 * inch),
    ]

    add_kv_table(
        story,
        [
            (display_label("birth_place", language), birth["birth_place"]),
            (display_label("birth_datetime", language), birth["birth_datetime_local"]),
            (display_label("lagna", language), display_sign(birth["lagna"], language)),
            (display_label("rashi", language), display_sign(birth["rashi"], language)),
            (display_label("nakshatra", language), display_nakshatra(birth["nakshatra"], language)),
            (display_label("doshas", language), ", ".join(birth["doshas"]) if birth["doshas"] else "-"),
        ],
        language=language,
        regular_font=regular_font,
        bold_font=bold_font,
    )

    story.extend(
        [
            Paragraph(display_label("planet_chart", language), heading),
            NorthIndianChart(
                kundali,
                language=language,
                regular_font=regular_font,
                bold_font=bold_font,
                width=4.0 * inch,
                height=4.0 * inch,
            ),
            Spacer(1, 0.18 * inch),
        ]
    )

    if kundali.get("navamsa"):
        story.extend(
            [
                Paragraph(display_label("navamsa_chart", language), heading),
                NorthIndianChart(
                    {"houses": kundali["navamsa"]["houses"]},
                    language=language,
                    regular_font=regular_font,
                    bold_font=bold_font,
                    width=4.0 * inch,
                    height=4.0 * inch,
                ),
                Spacer(1, 0.18 * inch),
            ]
        )

    story.append(Paragraph(display_label("planet_table", language), heading))

    planet_table = Table(
        build_planet_rows(kundali, language),
        colWidths=[1.05 * inch, 1.2 * inch, 0.65 * inch, 1.8 * inch, 0.95 * inch],
    )
    planet_table.setStyle(table_style(regular_font, bold_font))
    story.extend([planet_table, Spacer(1, 0.16 * inch)])

    if current:
        story.extend(
            [
                Paragraph(display_label("dasha", language), heading),
                DashaTimeline(
                    dasha or {},
                    language=language,
                    regular_font=regular_font,
                    bold_font=bold_font,
                ),
                Spacer(1, 0.15 * inch),
            ]
        )
        add_kv_table(
            story,
            [
                (display_label("system", language), display_dasha_value(current["system"], language)),
                (display_label("seed", language), display_dasha_value(current["seed"], language)),
                (display_label("current_period", language), display_dasha_value(current["period"] or "-", language)),
                (display_label("mahadasha_end", language), current["mahadasha_end"] or "-"),
                (display_label("antardasha_end", language), current["antardasha_end"] or "-"),
            ],
            language=language,
            regular_font=regular_font,
            bold_font=bold_font,
        )

    if daily:
        story.append(Paragraph(display_label("panchang", language), heading))
        add_kv_table(
            story,
            [
                (display_label("date", language), daily["date"]),
                (display_label("place", language), daily["place"]),
                (display_label("vara", language), display_term(daily["vara"], language)),
                (display_label("tithi", language), display_term(daily["tithi"], language)),
                (display_label("nakshatra", language), display_nakshatra(daily["nakshatra"], language)),
                (display_label("yoga", language), display_term(daily["yoga"], language)),
                (display_label("karana", language), display_term(daily["karana"], language)),
                (display_label("sunrise", language), format_time(daily["sunrise"])),
                (display_label("sunset", language), format_time(daily["sunset"])),
            ],
            language=language,
            regular_font=regular_font,
            bold_font=bold_font,
        )

    story.extend(
        [
            PageBreak(),
            Paragraph(display_label("safety", language), heading),
            Paragraph(report["notes"][0], styles["HindiBody"]),
            Paragraph(report["notes"][1], styles["HindiBody"]),
        ]
    )
    doc.build(story, onFirstPage=PageFrame(display_label("title", language), regular_font, bold_font), onLaterPages=PageFrame(display_label("title", language), regular_font, bold_font))
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a PDF astrology report with charts.")
    parser.add_argument("--kundali-json", required=True, help="Path to kundali JSON")
    parser.add_argument("--dasha-json", help="Optional path to dasha JSON")
    parser.add_argument("--panchang-json", help="Optional path to panchang JSON")
    parser.add_argument("--gochar-json", help="Optional path to gochar JSON")
    parser.add_argument("--output", required=True, help="Output PDF path")
    parser.add_argument("--language", choices=["hin", "hi", "en"], default="hin")
    parser.add_argument("--client-name", help="Client/native name shown on the cover page")
    parser.add_argument("--template", choices=["standard", "pandit_v1"], default="standard")
    parser.add_argument(
        "--renderer",
        choices=list(SUPPORTED_RENDERERS),
        default=DEFAULT_RENDERER,
        help=(
            "Rendering backend. 'html' uses Chromium via Playwright (preferred for "
            "Devanagari polish); 'reportlab' keeps the legacy in-process renderer."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = build_pdf_report(
        load_json(Path(args.kundali_json)),
        dasha=load_json(Path(args.dasha_json)) if args.dasha_json else None,
        panchang=load_json(Path(args.panchang_json)) if args.panchang_json else None,
        gochar=load_json(Path(args.gochar_json)) if args.gochar_json else None,
        output_path=Path(args.output),
        language=args.language,
        renderer=args.renderer,
        client_name=args.client_name,
        template=args.template,
    )
    print(f"Wrote PDF report ({args.renderer}): {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
