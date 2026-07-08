from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.astro_mcp.models import BirthDetails, ClientProfile, ReportRecord  # noqa: E402
from services.astro_mcp.storage import (  # noqa: E402
    find_client_profile,
    init_db,
    list_client_reports,
    save_client_profile,
    save_report_record,
)


def _sample_profile(client_id: str = "client-001", name: str = "Kiran Verma") -> ClientProfile:
    return ClientProfile(
        client_id=client_id,
        display_name=name,
        birth=BirthDetails(
            dob="26/12/2019",
            tob="09:15",
            place="Delhi",
            lat=28.6139,
            lon=77.2090,
            timezone_name="Asia/Kolkata",
        ),
        notes="reference chart",
    )


def test_init_db_creates_clients_and_reports_tables(tmp_path: Path):
    db_path = tmp_path / "pandit.sqlite3"
    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        rows = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert {"clients", "reports"} <= rows


def test_save_and_find_client_profile_roundtrip(tmp_path: Path):
    db_path = tmp_path / "pandit.sqlite3"
    init_db(db_path)
    profile = _sample_profile()

    save_client_profile(db_path, profile)
    by_id = find_client_profile(db_path, profile.client_id)

    assert by_id is not None
    assert by_id.client_id == profile.client_id
    assert by_id.display_name == profile.display_name
    assert by_id.birth is not None
    assert by_id.birth.place == "Delhi"
    assert by_id.birth.lat == 28.6139
    assert by_id.notes == "reference chart"


def test_find_client_profile_searches_by_display_name(tmp_path: Path):
    db_path = tmp_path / "pandit.sqlite3"
    init_db(db_path)
    save_client_profile(db_path, _sample_profile("client-001", "Kiran Verma"))
    save_client_profile(db_path, _sample_profile("client-002", "Ravi Sharma"))

    match = find_client_profile(db_path, "kiran")

    assert match is not None
    assert match.client_id == "client-001"


def test_find_client_profile_returns_none_when_missing(tmp_path: Path):
    db_path = tmp_path / "pandit.sqlite3"
    init_db(db_path)

    assert find_client_profile(db_path, "nobody") is None


def test_save_client_profile_updates_existing_record(tmp_path: Path):
    db_path = tmp_path / "pandit.sqlite3"
    init_db(db_path)
    save_client_profile(db_path, _sample_profile())
    updated = ClientProfile(
        client_id="client-001",
        display_name="Kiran Verma",
        birth=None,
        notes="rechecking details",
    )

    save_client_profile(db_path, updated)
    fetched = find_client_profile(db_path, "client-001")

    assert fetched is not None
    assert fetched.birth is None
    assert fetched.notes == "rechecking details"


def test_save_and_list_report_records(tmp_path: Path):
    db_path = tmp_path / "pandit.sqlite3"
    init_db(db_path)
    save_client_profile(db_path, _sample_profile())
    record_a = ReportRecord(
        report_id="r-1",
        client_id="client-001",
        report_type="pdf_report",
        path=str(tmp_path / "report-a.pdf"),
        created_at="2026-05-27T10:00:00+05:30",
    )
    record_b = ReportRecord(
        report_id="r-2",
        client_id="client-001",
        report_type="json_report",
        path=str(tmp_path / "report-b.json"),
        created_at="2026-05-27T11:00:00+05:30",
    )

    save_report_record(db_path, record_a)
    save_report_record(db_path, record_b)
    rows = list_client_reports(db_path, "client-001")

    assert [row.report_id for row in rows] == ["r-2", "r-1"]
    assert rows[0].report_type == "json_report"
    assert rows[1].path.endswith("report-a.pdf")


def test_list_client_reports_returns_empty_for_unknown_client(tmp_path: Path):
    db_path = tmp_path / "pandit.sqlite3"
    init_db(db_path)

    assert list_client_reports(db_path, "ghost") == []
