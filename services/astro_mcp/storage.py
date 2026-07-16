"""SQLite-backed storage for the astro MCP service."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import BirthDetails, ClientProfile, ReportRecord

DEFAULT_DB_PATH = Path("data/astro_mcp.sqlite3")


def default_db_path() -> Path:
    return DEFAULT_DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    dob TEXT,
    tob TEXT,
    place TEXT,
    lat REAL,
    lon REAL,
    timezone_name TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients(client_id)
);
"""


def _connect(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db(db_path: Path | str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def _row_to_profile(row: sqlite3.Row) -> ClientProfile:
    has_birth = row["dob"] is not None and row["tob"] is not None
    birth = (
        BirthDetails(
            dob=row["dob"],
            tob=row["tob"],
            place=row["place"] or "",
            lat=float(row["lat"]) if row["lat"] is not None else 0.0,
            lon=float(row["lon"]) if row["lon"] is not None else 0.0,
            timezone_name=row["timezone_name"] or "",
        )
        if has_birth
        else None
    )
    return ClientProfile(
        client_id=row["client_id"],
        display_name=row["display_name"],
        birth=birth,
        notes=row["notes"] or "",
    )


def save_client_profile(db_path: Path | str, profile: ClientProfile) -> None:
    now = _now_iso()
    birth = profile.birth
    values = {
        "client_id": profile.client_id,
        "display_name": profile.display_name,
        "dob": birth.dob if birth else None,
        "tob": birth.tob if birth else None,
        "place": birth.place if birth else None,
        "lat": birth.lat if birth else None,
        "lon": birth.lon if birth else None,
        "timezone_name": birth.timezone_name if birth else None,
        "notes": profile.notes,
        "now": now,
    }
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO clients (
                client_id, display_name, dob, tob, place, lat, lon,
                timezone_name, notes, created_at, updated_at
            ) VALUES (
                :client_id, :display_name, :dob, :tob, :place, :lat, :lon,
                :timezone_name, :notes, :now, :now
            )
            ON CONFLICT(client_id) DO UPDATE SET
                display_name = excluded.display_name,
                dob = excluded.dob,
                tob = excluded.tob,
                place = excluded.place,
                lat = excluded.lat,
                lon = excluded.lon,
                timezone_name = excluded.timezone_name,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            values,
        )
        conn.commit()


def find_client_profile(db_path: Path | str, query: str) -> ClientProfile | None:
    needle = (query or "").strip()
    if not needle:
        return None
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE client_id = ? LIMIT 1",
            (needle,),
        ).fetchone()
        if row is None:
            # INSTR instead of LIKE so %/_ in the query match literally
            # rather than acting as wildcards.
            row = conn.execute(
                "SELECT * FROM clients WHERE INSTR(LOWER(display_name), ?) > 0 "
                "ORDER BY updated_at DESC LIMIT 1",
                (needle.lower(),),
            ).fetchone()
    return _row_to_profile(row) if row is not None else None


def save_report_record(db_path: Path | str, record: ReportRecord) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO reports (report_id, client_id, report_type, path, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(report_id) DO UPDATE SET
                client_id = excluded.client_id,
                report_type = excluded.report_type,
                path = excluded.path,
                created_at = excluded.created_at
            """,
            (
                record.report_id,
                record.client_id,
                record.report_type,
                record.path,
                record.created_at,
            ),
        )
        conn.commit()


def list_client_reports(db_path: Path | str, client_id: str) -> list[ReportRecord]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT report_id, client_id, report_type, path, created_at "
            "FROM reports WHERE client_id = ? "
            "ORDER BY created_at DESC, report_id DESC",
            (client_id,),
        ).fetchall()
    return [
        ReportRecord(
            report_id=row["report_id"],
            client_id=row["client_id"],
            report_type=row["report_type"],
            path=row["path"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
