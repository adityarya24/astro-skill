from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.astro_mcp.tools import (  # noqa: E402
    calculate_dasha_tool,
    calculate_kundali_tool,
    calculate_panchang_tool,
    find_client_profile_tool,
    generate_pdf_report_tool,
    generate_report_json_tool,
    list_client_reports_tool,
    parse_birth_details_tool,
    save_client_profile_tool,
)


# Neutral sample birth (26/12/2019 09:15 IST, Delhi). Goldens cross-checked
# against DrikPanchang for that date (Makara udaya lagna 08:36–10:19, Mula
# nakshatra upto 16:51, Dhanu rashi).
SAMPLE_BIRTH = {
    "dob": "26/12/2019",
    "tob": "09:15",
    "place": "Delhi",
    "lat": 28.6139,
    "lon": 77.2090,
    "timezone_name": "Asia/Kolkata",
}


def test_calculate_kundali_tool_returns_reference_chart():
    chart = calculate_kundali_tool(**SAMPLE_BIRTH)

    assert chart["lagna"] == "Makara"
    assert chart["rashi"] == "Dhanu"
    assert chart["nakshatra"] == "Mula"
    assert chart["dasha_seed"]["nakshatra_lord"] == "Ketu"


def test_parse_birth_details_tool_extracts_common_fields_and_missing_values():
    parsed = parse_birth_details_tool(
        "Kiran Verma DOB 26/12/2019 TOB 09:15 place Delhi lat 28.6139 lon 77.2090 Asia/Kolkata"
    )

    assert parsed["dob"] == "26/12/2019"
    assert parsed["tob"] == "09:15"
    assert parsed["place"] == "Delhi"
    assert parsed["lat"] == 28.6139
    assert parsed["lon"] == 77.2090
    assert parsed["timezone_name"] == "Asia/Kolkata"
    assert parsed["missing"] == []

    missing = parse_birth_details_tool("Rahul ka chart banana hai")
    assert set(missing["missing"]) == {"dob", "tob", "place", "lat", "lon", "timezone_name"}


def test_calculate_kundali_tool_propagates_input_errors():
    bad = dict(SAMPLE_BIRTH)
    bad["dob"] = "not-a-date"
    with pytest.raises(ValueError):
        calculate_kundali_tool(**bad)


def test_calculate_dasha_tool_returns_current_period():
    chart = calculate_kundali_tool(**SAMPLE_BIRTH)
    dasha = calculate_dasha_tool(kundali=chart, on_date="2026-05-20")

    assert dasha["seed_lord"] == "Ketu"
    assert dasha["current"]["mahadasha"] == "Shukra"
    assert dasha["current"]["antardasha"] == "Surya"


def test_calculate_panchang_tool_returns_delhi_thursday():
    panchang = calculate_panchang_tool(
        date="2026-05-21",
        place="Delhi",
        lat=28.6139,
        lon=77.209,
        timezone_name="Asia/Kolkata",
    )

    assert panchang["panchang"]["vara"] == "Guruvara"
    assert panchang["calculation"]["ayanamsa"] == "lahiri"


def test_generate_report_json_tool_returns_summary(tmp_path: Path):
    chart = calculate_kundali_tool(**SAMPLE_BIRTH)
    dasha = calculate_dasha_tool(kundali=chart, on_date="2026-05-20")
    panchang = calculate_panchang_tool(
        date="2026-05-21",
        place="Delhi",
        lat=28.6139,
        lon=77.209,
        timezone_name="Asia/Kolkata",
    )

    out = generate_report_json_tool(
        kundali=chart,
        dasha=dasha,
        panchang=panchang,
        language="hin",
        client_id="client-001",
        output_dir=tmp_path,
    )

    assert out["client_id"] == "client-001"
    assert out["report_type"] == "json_report"
    assert out["report_id"]
    saved = Path(out["path"])
    assert saved.exists()
    payload = json.loads(saved.read_text(encoding="utf-8"))
    assert payload["sections"]["birth_chart"]["lagna"] == "Makara"
    assert payload["sections"]["current_dasha"]["period"] == "Shukra/Surya/Shukra"
    assert payload["sections"]["daily_panchang"]["vara"] == "Guruvara"


def test_generate_pdf_report_tool_writes_pdf_with_metadata(tmp_path: Path):
    chart = calculate_kundali_tool(**SAMPLE_BIRTH)
    dasha = calculate_dasha_tool(kundali=chart, on_date="2026-05-20")

    out = generate_pdf_report_tool(
        kundali=chart,
        dasha=dasha,
        panchang=None,
        gochar=None,
        language="hi",
        client_id="client-001",
        client_name="Kiran Verma",
        brand="Jyotish Paramarsh",
        output_dir=tmp_path,
        renderer="reportlab",
        template="standard",
    )

    assert out["client_id"] == "client-001"
    assert out["report_type"] == "pdf_report"
    path = Path(out["path"])
    assert path.exists()
    assert path.suffix == ".pdf"
    assert path.stat().st_size > 4_000
    text = "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
    assert "Kiran Verma" in text
    assert "Makara" in text
    assert "Jyotish Paramarsh" in text
    assert "Astro Skill" not in text


def test_storage_tools_roundtrip_client_and_reports(tmp_path: Path):
    db_path = tmp_path / "pandit.sqlite3"
    profile_dict = {
        "client_id": "client-007",
        "display_name": "Test Client",
        "birth": SAMPLE_BIRTH,
        "notes": "vip",
    }

    save_response = save_client_profile_tool(profile=profile_dict, db_path=db_path)
    assert save_response["client_id"] == "client-007"

    fetched = find_client_profile_tool(query="client-007", db_path=db_path)
    assert fetched is not None
    assert fetched["display_name"] == "Test Client"
    assert fetched["birth"]["place"] == "Delhi"

    chart = calculate_kundali_tool(**SAMPLE_BIRTH)
    generate_report_json_tool(
        kundali=chart,
        dasha=None,
        panchang=None,
        language="hin",
        client_id="client-007",
        output_dir=tmp_path,
        db_path=db_path,
    )
    generate_pdf_report_tool(
        kundali=chart,
        dasha=None,
        panchang=None,
        language="hi",
        client_id="client-007",
        output_dir=tmp_path,
        db_path=db_path,
        renderer="reportlab",
    )

    reports = list_client_reports_tool(client_id="client-007", db_path=db_path)
    assert {row["report_type"] for row in reports} == {"json_report", "pdf_report"}
    assert all(row["client_id"] == "client-007" for row in reports)


def test_report_filename_does_not_leak_client_id_and_blocks_traversal(tmp_path: Path):
    out_dir = tmp_path / "reports"
    chart = calculate_kundali_tool(**SAMPLE_BIRTH)

    safe_out = generate_report_json_tool(
        kundali=chart,
        dasha=None,
        panchang=None,
        language="hin",
        client_id="../evil",
        output_dir=out_dir,
    )

    written = Path(safe_out["path"]).resolve()
    assert out_dir.resolve() in written.parents
    assert "../" not in safe_out["path"]
    assert "evil" not in written.name
    assert written.name.startswith("rpt-")
    assert written.name.endswith(".json")
    assert written.exists()


def test_report_tool_persistence_auto_creates_missing_client(tmp_path: Path):
    db_path = tmp_path / "astro.sqlite3"
    chart = calculate_kundali_tool(**SAMPLE_BIRTH)

    generate_report_json_tool(
        kundali=chart,
        dasha=None,
        panchang=None,
        language="hin",
        client_id="anonymous",
        output_dir=tmp_path,
        db_path=db_path,
    )

    fetched = find_client_profile_tool(query="anonymous", db_path=db_path)
    reports = list_client_reports_tool(client_id="anonymous", db_path=db_path)

    assert fetched is not None
    assert fetched["display_name"] == "anonymous"
    assert len(reports) == 1
    assert reports[0]["report_type"] == "json_report"


def test_generate_report_json_tool_accepts_schema_advertised_fields(tmp_path: Path):
    """The MCP schema lists gochar and client_name; the tool must accept them."""
    kundali = calculate_kundali_tool(
        dob="26/12/2019", tob="09:15", place="Delhi",
        lat=28.6139, lon=77.2090, timezone_name="Asia/Kolkata",
    )
    record = generate_report_json_tool(
        kundali,
        gochar={"note": "demo-gochar"},
        client_name="Kiran Verma",
        output_dir=tmp_path,
    )
    written = json.loads(Path(record["path"]).read_text(encoding="utf-8"))
    assert written["sections"]["gochar"] == {"note": "demo-gochar"}
    assert written["client_name"] == "Kiran Verma"


def test_client_supplied_paths_outside_allowed_bases_are_rejected(tmp_path: Path, monkeypatch):
    """output_dir/db_path come from MCP clients; paths outside the working
    directory, the system temp dir, or ASTRO_MCP_BASE_DIR must be refused."""
    from services.astro_mcp.tools import _resolve_db_path, _resolve_output_dir

    monkeypatch.delenv("ASTRO_MCP_BASE_DIR", raising=False)
    outside = Path("/etc/astro-skill-forbidden")

    with pytest.raises(ValueError, match="Refusing output directory"):
        _resolve_output_dir(outside)
    assert not outside.exists()

    with pytest.raises(ValueError, match="Refusing SQLite database path"):
        save_client_profile_tool(
            profile={"client_id": "evil", "display_name": "Evil", "birth": None},
            db_path=outside / "evil.sqlite3",
        )

    # ASTRO_MCP_BASE_DIR widens the fence explicitly. Shrink the temp-dir
    # base first so tmp_path is only allowed once the env var names it.
    import services.astro_mcp.tools as tools_mod

    monkeypatch.setattr(
        tools_mod.tempfile, "gettempdir", lambda: str(tmp_path / "elsewhere")
    )
    with pytest.raises(ValueError, match="Refusing output directory"):
        _resolve_output_dir(tmp_path / "reports")

    monkeypatch.setenv("ASTRO_MCP_BASE_DIR", str(tmp_path))
    resolved = _resolve_output_dir(tmp_path / "reports")
    assert resolved.is_dir()
    assert _resolve_db_path(tmp_path / "store.sqlite3") == (tmp_path / "store.sqlite3").resolve()
