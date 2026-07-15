from __future__ import annotations

import importlib
import importlib.abc
import json
import subprocess
import sys
import types
from datetime import date
from pathlib import Path

import pytest

from pypdf import PdfReader

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from dasha_calculator import calculate_dasha  # noqa: E402
from html_pdf_report import build_html, chromium_available  # noqa: E402
from kundali_calculator import BirthInput, calculate_kundali  # noqa: E402
from panchang_calculator import PanchangInput, calculate_panchang  # noqa: E402
from pdf_report import build_pdf_report  # noqa: E402


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


def extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# ---------- Legacy ReportLab renderer (must always be exercised) ------------


def test_reportlab_renderer_contains_planet_chart_and_dasha_timeline(tmp_path: Path):
    chart = reference_chart()
    dasha = calculate_dasha(chart, on_date=date(2026, 5, 20))
    panchang = reference_panchang()
    output_path = tmp_path / "astro-report.pdf"

    build_pdf_report(
        chart,
        dasha=dasha,
        panchang=panchang,
        output_path=output_path,
        language="hi",
        renderer="reportlab",
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 4_000
    text = extract_text(output_path)
    assert "जन्म कुंडली रिपोर्ट" in text
    assert "ग्रह स्थिति" in text
    assert "दशा तालिका" in text
    assert "लग्न कुंडली" in text
    assert "नवांश कुंडली (D9)" in text
    assert "Makara" in text
    assert "शुक्र/सूर्य" in text


def test_reportlab_cli_writes_pdf(tmp_path: Path):
    chart = reference_chart()
    dasha = calculate_dasha(chart, on_date=date(2026, 5, 20))
    panchang = reference_panchang()
    chart_path = tmp_path / "chart.json"
    dasha_path = tmp_path / "dasha.json"
    panchang_path = tmp_path / "panchang.json"
    output_path = tmp_path / "report.pdf"
    chart_path.write_text(json.dumps(chart), encoding="utf-8")
    dasha_path.write_text(json.dumps(dasha), encoding="utf-8")
    panchang_path.write_text(json.dumps(panchang), encoding="utf-8")
    script = SCRIPT_DIR / "pdf_report.py"

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
            "--output",
            str(output_path),
            "--language",
            "hi",
            "--renderer",
            "reportlab",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert str(output_path) in completed.stdout
    assert "reportlab" in completed.stdout
    assert "लग्न कुंडली" in extract_text(output_path)


def test_pdf_report_rejects_unknown_renderer(tmp_path: Path):
    with pytest.raises(ValueError):
        build_pdf_report(
            reference_chart(),
            output_path=tmp_path / "x.pdf",
            language="hi",
            renderer="weasyprint",
        )


def test_html_renderer_path_does_not_require_reportlab(monkeypatch, tmp_path: Path):
    class BlockReportLab(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname: str, path: object | None = None, target: object | None = None):
            if fullname.startswith("reportlab"):
                raise ImportError("blocked reportlab for optional-dependency test")
            return None

    for module_name in list(sys.modules):
        if module_name == "pdf_report" or module_name.startswith("reportlab"):
            monkeypatch.delitem(sys.modules, module_name, raising=False)

    fake_html = types.ModuleType("html_pdf_report")

    def fake_build_html_pdf_report(
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
        output_path.write_text("fake html pdf", encoding="utf-8")
        return output_path

    fake_html.build_html_pdf_report = fake_build_html_pdf_report
    monkeypatch.setitem(sys.modules, "html_pdf_report", fake_html)

    blocker = BlockReportLab()
    monkeypatch.setattr(sys, "meta_path", [blocker, *sys.meta_path])

    fresh_pdf_report = importlib.import_module("pdf_report")
    html_output = fresh_pdf_report.build_pdf_report(
        reference_chart(),
        output_path=tmp_path / "html.pdf",
        language="hi",
        renderer="html",
    )

    assert html_output.exists()
    with pytest.raises(RuntimeError, match="ReportLab renderer requires"):
        fresh_pdf_report.build_pdf_report(
            reference_chart(),
            output_path=tmp_path / "reportlab.pdf",
            language="hi",
            renderer="reportlab",
        )


# ---------- HTML composition (no Chromium needed) ---------------------------


def test_html_renderer_composes_self_contained_document_without_browser():
    chart = reference_chart()
    dasha = calculate_dasha(chart, on_date=date(2026, 5, 20))
    panchang = reference_panchang()

    document = build_html(chart, dasha=dasha, panchang=panchang, language="hi")

    assert document.startswith("<!DOCTYPE html>")
    assert "जन्म कुंडली रिपोर्ट" in document
    assert "लग्न कुंडली" in document
    assert "नवांश कुंडली (D9)" in document
    assert "दशा तालिका" in document
    assert "दैनिक पंचांग" in document
    assert "Makara" in document
    assert "शुक्र/सूर्य" in document
    assert "@font-face" in document  # bundled Devanagari font embedded
    assert "<svg" in document and "</svg>" in document
    assert "@page" in document  # print CSS embedded


def test_pandit_v1_html_has_pitch_ready_sections():
    chart = reference_chart()
    dasha = calculate_dasha(chart, on_date=date(2026, 7, 2))
    panchang = reference_panchang()

    document = build_html(
        chart,
        dasha=dasha,
        panchang=panchang,
        language="hi",
        client_name="Kiran Verma",
        template="pandit_v1",
    )

    # Client-facing janma patrika: interpretation-rich but paginated, no filler.
    assert 14 <= document.count('class="pandit-page"') <= 19
    assert "जन्म पत्रिका" in document
    assert "Kiran Verma" in document
    assert "सूचना" in document
    assert "अवकहड़ा चक्र" in document
    assert "जन्म पंचांग" in document
    assert "लग्न कुंडली" in document
    assert "चंद्र कुंडली" in document
    assert "नवांश कुंडली" in document
    assert "दशा तालिका" in document
    assert "अंतर्दशा तालिका" in document
    assert "लग्न-राशि-नक्षत्र फल" in document
    assert "व्यक्तित्व विश्लेषण" in document  # personality profile section
    assert "वर्तमान दशा विश्लेषण" in document  # current period analysis
    assert "महादशा फल" in document  # per-dasha classical readings
    assert "उपाय सुझाव" in document  # remedies (mantras)
    assert "वर्ष" in document  # mahadasha durations formatted, not raw floats
    assert "black-panel" not in document  # cover uses the gold name-plate now


def test_html_cover_uses_client_name_instead_of_birth_place():
    chart = reference_chart()
    document = build_html(chart, language="hi", client_name="Kiran Verma")

    cover = document.split("</section>", 1)[0]
    assert "<strong>Kiran Verma</strong>" in cover
    assert "<strong>Delhi</strong>" not in cover


def test_html_cover_can_read_client_name_from_kundali_input():
    chart = reference_chart()
    chart["input"]["client_name"] = "Yuvaansh"

    document = build_html(chart, language="hi")

    cover = document.split("</section>", 1)[0]
    assert "<strong>Yuvaansh</strong>" in cover


def test_reportlab_cover_uses_client_name(tmp_path: Path):
    output_path = tmp_path / "report.pdf"

    build_pdf_report(
        reference_chart(),
        output_path=output_path,
        language="en",
        renderer="reportlab",
        client_name="Kiran Verma",
    )

    text = extract_text(output_path)
    assert "Kiran Verma" in text


def test_pandit_v1_requires_html_renderer(tmp_path: Path):
    with pytest.raises(ValueError, match="requires renderer='html'"):
        build_pdf_report(
            reference_chart(),
            output_path=tmp_path / "report.pdf",
            language="hi",
            renderer="reportlab",
            template="pandit_v1",
        )


# ---------- HTML renderer (Chromium required, skip if missing) --------------


@pytest.mark.skipif(
    not chromium_available(),
    reason="Playwright Chromium not installed; run `python -m playwright install chromium`",
)
def test_html_renderer_produces_pdf_via_chromium(tmp_path: Path):
    chart = reference_chart()
    dasha = calculate_dasha(chart, on_date=date(2026, 5, 20))
    panchang = reference_panchang()
    output_path = tmp_path / "html-report.pdf"

    build_pdf_report(
        chart,
        dasha=dasha,
        panchang=panchang,
        output_path=output_path,
        language="hi",
        renderer="html",
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 4_000
    text = extract_text(output_path)
    assert "Makara" in text
    assert "मंगल" in text
