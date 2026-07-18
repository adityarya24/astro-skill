"""Tool functions exposed by the astro MCP service.

Each function is a thin, JSON-friendly wrapper over the portable astro
calculator and report modules. The MCP layer keeps state (SQLite, files);
the calculators stay stateless and portable.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .models import BirthDetails, ClientProfile, ReportRecord
from .storage import (
    default_db_path,
    find_client_profile,
    init_db,
    list_client_reports,
    save_client_profile,
    save_report_record,
)

from astro.scripts.dasha_calculator import calculate_dasha
from astro.scripts.report_generator import build_basic_report

# NOTE: kundali_calculator, panchang_calculator and pdf_report are imported
# lazily inside the tools that use them. The first two pull in pyswisseph and
# the last pulls in reportlab — all optional at the edges. Importing them at
# module load would make the whole tool registry (including the pure
# parse_birth_details helper) unimportable wherever those deps are absent.

DEFAULT_OUTPUT_DIR = Path("data/reports")

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

# Common abbreviations an operator might type instead of an IANA zone name.
TIMEZONE_ABBREVIATIONS = {"IST": "Asia/Kolkata"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_report_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _allowed_base_dirs() -> tuple[Path, ...]:
    """Directories client-supplied paths may live under.

    MCP clients control ``output_dir``/``db_path`` in tool arguments, so
    without a fence a client could make the server create directories or
    SQLite files anywhere the process may write. Operators can widen the
    fence explicitly via the ``ASTRO_MCP_BASE_DIR`` environment variable.
    """
    bases = [Path.cwd(), Path(tempfile.gettempdir())]
    extra = os.environ.get("ASTRO_MCP_BASE_DIR")
    if extra:
        bases.append(Path(extra))
    return tuple(base.resolve() for base in bases)


def _ensure_allowed_path(path: Path | str, kind: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    for base in _allowed_base_dirs():
        if resolved == base or base in resolved.parents:
            return resolved
    raise ValueError(
        f"Refusing {kind} outside the allowed base directories "
        f"(working directory, system temp dir, or ASTRO_MCP_BASE_DIR): {resolved}"
    )


def _resolve_output_dir(output_dir: Path | str | None) -> Path:
    requested = output_dir if output_dir is not None else DEFAULT_OUTPUT_DIR
    path = _ensure_allowed_path(requested, "output directory")
    path.mkdir(parents=True, exist_ok=True)
    return path


_SLUG_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")


def _safe_filename(report_id: str, extension: str) -> str:
    """Build a filename that cannot escape the output directory.

    The report_id already includes a prefix (``rpt-``/``pdf-``) plus a uuid4
    hex slice, so it is unique and contains no path separators by construction.
    Any caller-supplied identifiers (like ``client_id``) are deliberately kept
    out of the filename — those live in the SQLite ``reports`` row instead.
    """
    safe = _SLUG_PATTERN.sub("_", report_id).strip("._-") or "report"
    return f"{safe}.{extension.lstrip('.')}"


def _resolved_output_path(out_dir: Path, report_id: str, extension: str) -> Path:
    candidate = (out_dir / _safe_filename(report_id, extension)).resolve()
    base = out_dir.resolve()
    if base != candidate.parent and base not in candidate.parents:
        raise ValueError(
            f"Refusing to write report outside output directory: {candidate}"
        )
    return candidate


def _persist_report(db_path: Path | str | None, record: ReportRecord) -> None:
    if db_path is None:
        return
    db_path = _ensure_allowed_path(db_path, "SQLite database path")
    init_db(db_path)
    if find_client_profile(db_path, record.client_id) is None:
        save_client_profile(
            db_path,
            ClientProfile(
                client_id=record.client_id,
                display_name=record.client_id,
                birth=None,
                notes="Auto-created for report metadata.",
            ),
        )
    save_report_record(db_path, record)


def _normalize_clock_time(raw: str) -> str:
    """Normalise a matched time to 24-hour ``HH:MM`` (or ``HH:MM:SS``).

    The calculators only accept 24-hour times, so a ``9:30 PM`` from an operator
    note must become ``21:30`` — never a silent 12-hour error downstream. Times
    without a meridiem are assumed to already be 24-hour and only zero-padded.
    """
    match = re.match(r"^\s*(\d{1,2}):([0-5]\d)(?::([0-5]\d))?\s*([AaPp][Mm])?\s*$", raw)
    if not match:
        return raw.strip()
    hour = int(match.group(1))
    minute, second, meridiem = match.group(2), match.group(3), match.group(4)
    if meridiem:
        meridiem = meridiem.upper()
        if meridiem == "PM" and hour != 12:
            hour += 12
        elif meridiem == "AM" and hour == 12:
            hour = 0
    core = f"{hour:02d}:{minute}"
    return f"{core}:{second}" if second else core


def _extract_dob(normalized: str) -> str | None:
    """Extract a date of birth as ``DD/MM/YYYY`` (or ISO), numeric or written out."""
    numeric_match = re.search(
        r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{1,2}-\d{1,2})\b",
        normalized,
    )
    if numeric_match:
        return numeric_match.group(1)

    # Natural language, e.g. "26th December 2019" / "3 Jan 2000".
    natural_match = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t)?(?:ember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})\b",
        normalized,
        re.I,
    )
    if natural_match is None:
        return None
    month = MONTHS.get(natural_match.group(2).lower())
    if month is None:
        return None
    day = int(natural_match.group(1))
    year = int(natural_match.group(3))
    return f"{day:02d}/{month:02d}/{year:04d}"


def _extract_timezone(normalized: str) -> str | None:
    """Extract an IANA timezone name, or resolve a known abbreviation like IST."""
    timezone_match = re.search(r"\b([A-Z][A-Za-z_]+/[A-Z][A-Za-z_]+)\b", normalized)
    if timezone_match:
        return timezone_match.group(1)

    abbreviation_match = re.search(r"\b(IST)\b", normalized, re.I)
    if abbreviation_match:
        return TIMEZONE_ABBREVIATIONS[abbreviation_match.group(1).upper()]

    return None


def parse_birth_details_tool(text: str) -> dict:
    """Extract common birth-detail fields from a short operator note.

    This is deliberately conservative. It returns missing fields as ``None`` so
    the calling agent can ask the operator for clarification instead of
    guessing.
    """
    normalized = " ".join(text.strip().split())
    dob = _extract_dob(normalized)
    time_match = re.search(
        r"\b(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)\b",
        normalized,
    )
    lat_match = re.search(r"\b(?:lat|latitude)\s*[:=]?\s*(-?\d+(?:\.\d+)?)", normalized, re.I)
    lon_match = re.search(r"\b(?:lon|lng|longitude)\s*[:=]?\s*(-?\d+(?:\.\d+)?)", normalized, re.I)
    timezone_name = _extract_timezone(normalized)
    place_match = re.search(
        r"\b(?:place|स्थान|birthplace)\s*[:=]?\s*([A-Za-z .'-]+?)(?=\s+(?:lat|latitude|lon|lng|longitude)\b|$)",
        normalized,
        re.I,
    )

    fields = {
        "dob": dob,
        "tob": _normalize_clock_time(time_match.group(1)) if time_match else None,
        "place": place_match.group(1).strip() if place_match else None,
        "lat": float(lat_match.group(1)) if lat_match else None,
        "lon": float(lon_match.group(1)) if lon_match else None,
        "timezone_name": timezone_name,
    }
    missing = [field for field, value in fields.items() if value is None]

    return {"raw_text": text, **fields, "missing": missing}


# ---- Calculator tools ------------------------------------------------------


def calculate_kundali_tool(
    dob: str,
    tob: str,
    place: str,
    lat: float,
    lon: float,
    timezone_name: str,
    ayanamsa: str = "lahiri",
) -> dict:
    from astro.scripts.kundali_calculator import BirthInput, calculate_kundali

    return calculate_kundali(
        BirthInput(
            dob=dob,
            tob=tob,
            place=place,
            lat=float(lat),
            lon=float(lon),
            timezone_name=timezone_name,
            ayanamsa=ayanamsa,
        )
    )


def calculate_dasha_tool(kundali: dict, on_date: str | None = None) -> dict:
    parsed = date.fromisoformat(on_date) if on_date else None
    return calculate_dasha(kundali, on_date=parsed)


def calculate_gochar_tool(kundali: dict, on_date: str | None = None) -> dict:
    from astro.scripts.gochar_calculator import calculate_gochar

    parsed = date.fromisoformat(on_date) if on_date else None
    return calculate_gochar(kundali, on_date=parsed)


def calculate_compatibility_tool(kundali_a: dict, kundali_b: dict) -> dict:
    from astro.scripts.guna_milan import calculate_compatibility

    return calculate_compatibility(kundali_a, kundali_b)


def calculate_panchang_tool(
    date: str,
    place: str,
    lat: float,
    lon: float,
    timezone_name: str,
    ayanamsa: str = "lahiri",
) -> dict:
    from astro.scripts.panchang_calculator import PanchangInput, calculate_panchang

    return calculate_panchang(
        PanchangInput(
            date=date,
            place=place,
            lat=float(lat),
            lon=float(lon),
            timezone_name=timezone_name,
            ayanamsa=ayanamsa,
        )
    )


# ---- Report tools ----------------------------------------------------------


def generate_report_json_tool(
    kundali: dict,
    dasha: dict | None = None,
    panchang: dict | None = None,
    gochar: dict | None = None,
    gochar_narrative: dict | None = None,
    synthesis: dict | bool | None = None,
    language: str = "hin",
    client_id: str = "anonymous",
    client_name: str | None = None,
    output_dir: Path | str | None = None,
    db_path: Path | str | None = None,
) -> dict:
    report = build_basic_report(kundali, dasha=dasha, panchang=panchang, language=language)
    # The MCP schema advertises these optional fields; carry them into the
    # written report instead of rejecting the call.
    if gochar is not None:
        report["sections"]["gochar"] = gochar
    if client_name:
        report["client_name"] = client_name

    if synthesis is True:
        from astro.scripts.synthesis import synthesize_bilingual
        from astro.scripts.gochar_narrative import build_antardasha_gochar_narrative
        if not gochar_narrative and dasha:
            gochar_narrative = build_antardasha_gochar_narrative(kundali, dasha, language=language)
        
        synthesis = synthesize_bilingual(report, gochar_narrative)
    
    if gochar_narrative is not None:
        report["sections"]["gochar_narrative"] = gochar_narrative
    if isinstance(synthesis, dict):
        report["sections"]["synthesis"] = synthesis

    out_dir = _resolve_output_dir(output_dir)
    report_id = _new_report_id("rpt")
    path = _resolved_output_path(out_dir, report_id, "json")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    record = ReportRecord(
        report_id=report_id,
        client_id=client_id,
        report_type="json_report",
        path=str(path),
        created_at=_now_iso(),
    )
    _persist_report(db_path, record)
    return record.to_dict()


def generate_pdf_report_tool(
    kundali: dict,
    dasha: dict | None = None,
    panchang: dict | None = None,
    gochar: dict | None = None,
    gochar_narrative: dict | None = None,
    synthesis: dict | None = None,
    language: str = "hin",
    client_id: str = "anonymous",
    client_name: str | None = None,
    brand: str = "",
    output_dir: Path | str | None = None,
    db_path: Path | str | None = None,
    renderer: str = "html",
    template: str = "standard",
) -> dict:
    from astro.scripts.pdf_report import build_pdf_report
    from astro.scripts.synthesis import synthesize_bilingual
    from astro.scripts.gochar_narrative import build_antardasha_gochar_narrative

    if not gochar_narrative and dasha:
        gochar_narrative = build_antardasha_gochar_narrative(kundali, dasha, language=language)
    if not synthesis:
        _base_report = build_basic_report(kundali, dasha=dasha, panchang=panchang, language=language)
        synthesis = synthesize_bilingual(_base_report, gochar_narrative)

    out_dir = _resolve_output_dir(output_dir)
    report_id = _new_report_id("pdf")
    pdf_path = _resolved_output_path(out_dir, report_id, "pdf")
    build_pdf_report(
        kundali,
        dasha=dasha,
        panchang=panchang,
        gochar=gochar,
        gochar_narrative=gochar_narrative,
        synthesis=synthesis,
        output_path=pdf_path,
        language=language,
        renderer=renderer,
        client_name=client_name,
        brand=brand,
        template=template,
    )
    record = ReportRecord(
        report_id=report_id,
        client_id=client_id,
        report_type="pdf_report",
        path=str(pdf_path),
        created_at=_now_iso(),
    )
    _persist_report(db_path, record)
    return record.to_dict()


# ---- Client profile tools --------------------------------------------------


def _profile_from_dict(payload: dict) -> ClientProfile:
    birth_payload = payload.get("birth")
    birth = None
    if birth_payload:
        birth = BirthDetails(
            dob=birth_payload["dob"],
            tob=birth_payload["tob"],
            place=birth_payload["place"],
            lat=float(birth_payload["lat"]),
            lon=float(birth_payload["lon"]),
            timezone_name=birth_payload["timezone_name"],
        )
    return ClientProfile(
        client_id=str(payload["client_id"]),
        display_name=str(payload["display_name"]),
        birth=birth,
        notes=str(payload.get("notes", "")),
    )


def _resolve_db_path(db_path: Path | str | None) -> Path:
    if db_path is None:
        return default_db_path()
    return _ensure_allowed_path(db_path, "SQLite database path")


def save_client_profile_tool(profile: dict, db_path: Path | str | None = None) -> dict:
    resolved = _resolve_db_path(db_path)
    init_db(resolved)
    parsed = _profile_from_dict(profile)
    save_client_profile(resolved, parsed)
    return parsed.to_dict()


def find_client_profile_tool(query: str, db_path: Path | str | None = None) -> dict | None:
    resolved = _resolve_db_path(db_path)
    init_db(resolved)
    found = find_client_profile(resolved, query)
    return found.to_dict() if found else None


def list_client_reports_tool(client_id: str, db_path: Path | str | None = None) -> list[dict]:
    resolved = _resolve_db_path(db_path)
    init_db(resolved)
    return [asdict(record) for record in list_client_reports(resolved, client_id)]


# ---- Registry helpers ------------------------------------------------------


TOOLS: dict[str, Any] = {
    "parse_birth_details": parse_birth_details_tool,
    "calculate_kundali": calculate_kundali_tool,
    "calculate_dasha": calculate_dasha_tool,
    "calculate_gochar": calculate_gochar_tool,
    "calculate_compatibility": calculate_compatibility_tool,
    "calculate_panchang": calculate_panchang_tool,
    "generate_report_json": generate_report_json_tool,
    "generate_pdf_report": generate_pdf_report_tool,
    "save_client_profile": save_client_profile_tool,
    "find_client_profile": find_client_profile_tool,
    "list_client_reports": list_client_reports_tool,
}
