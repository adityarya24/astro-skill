"""Astro MCP server (stdio).

Generic Vedic astrology MCP server. Binds the tool registry in
:mod:`services.astro_mcp.tools` to a real Model Context Protocol stdio server.
Schemas are declared explicitly so the registry stays the single source of
truth for behaviour while the wire contract stays predictable for any MCP
client (Claude Desktop, Codex, or a custom agent).

Run with::

    python -m services.astro_mcp
    python -m services.astro_mcp.server
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from .tools import TOOLS

SERVER_NAME = "astro-mcp"
SERVER_VERSION = "1.0.0"


def list_tool_names() -> list[str]:
    return sorted(TOOLS.keys())


def get_tool(name: str) -> Callable:
    try:
        return TOOLS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown astro_mcp tool: {name}") from exc


# --- JSON Schemas for each tool ---------------------------------------------

# Shared property blocks so every tool documents the same field the same way.
_BIRTH_PROPERTIES = {
    "dob": {"type": "string", "description": "Date of birth, DD/MM/YYYY or YYYY-MM-DD."},
    "tob": {
        "type": "string",
        "description": "Time of birth, HH:MM (24-hour clock), local time at the birth place.",
    },
    "place": {
        "type": "string",
        "description": "Birth place name; a label for output, not geocoded.",
    },
    "lat": {
        "type": "number",
        "description": "Latitude of the birth place in decimal degrees (north positive).",
    },
    "lon": {
        "type": "number",
        "description": "Longitude of the birth place in decimal degrees (east positive).",
    },
    "timezone_name": {
        "type": "string",
        "description": "IANA timezone of the birth place, e.g. Asia/Kolkata.",
    },
}

_BIRTH_DETAILS_SCHEMA = {
    "type": "object",
    "properties": _BIRTH_PROPERTIES,
    "required": ["dob", "tob", "place", "lat", "lon", "timezone_name"],
    "additionalProperties": False,
}

_AYANAMSA_PROPERTY = {
    "type": "string",
    "enum": [
        "lahiri",
        "chitrapaksha",
        "raman",
        "krishnamurti",
        "kp",
        "fagan_bradley",
        "true_chitra",
        "yukteshwar",
    ],
    "default": "lahiri",
    "description": "Sidereal ayanamsa to calculate with. Default is Lahiri (Chitrapaksha).",
}

_KUNDALI_PROPERTY = {
    "type": "object",
    "description": "Kundali JSON exactly as returned by the calculate_kundali tool.",
}

_DASHA_PROPERTY = {
    "type": ["object", "null"],
    "description": "Optional dasha JSON from calculate_dasha; adds the dasha timeline section.",
}

_PANCHANG_PROPERTY = {
    "type": ["object", "null"],
    "description": "Optional panchang JSON from calculate_panchang; adds the panchang section.",
}

_GOCHAR_PROPERTY = {
    "type": ["object", "null"],
    "description": "Optional gochar JSON from calculate_gochar; adds the transit section.",
}

_GOCHAR_NARRATIVE_PROPERTY = {
    "type": ["object", "null"],
    "description": "Optional gochar narrative JSON from build_antardasha_gochar_narrative. If missing, it will be computed automatically.",
}

_SYNTHESIS_PROPERTY = {
    "type": ["object", "null"],
    "description": "Optional synthesis JSON from synthesize_bilingual. If missing, it will be computed automatically.",
}

_LANGUAGE_PROPERTY = {
    "type": "string",
    "enum": ["hin", "hi", "en"],
    "default": "hin",
    "description": "Report language: 'hin' or 'hi' for Hindi (Devanagari), 'en' for English.",
}

_CLIENT_ID_PROPERTY = {
    "type": "string",
    "default": "anonymous",
    "description": "Client identifier the report is filed under.",
}

_CLIENT_NAME_PROPERTY = {
    "type": ["string", "null"],
    "description": "Client/native name shown on the PDF cover page",
}

_OUTPUT_DIR_PROPERTY = {
    "type": ["string", "null"],
    "description": (
        "Directory the report file is written into (default: data/reports). "
        "Must resolve inside the server working directory, the system temp "
        "directory, or ASTRO_MCP_BASE_DIR; other paths are rejected."
    ),
}

_REPORT_DB_PATH_PROPERTY = {
    "type": ["string", "null"],
    "description": (
        "SQLite store to record the report in; when omitted the report is only written to disk. "
        "Must resolve inside the server working directory, the system temp "
        "directory, or ASTRO_MCP_BASE_DIR; other paths are rejected."
    ),
}

_PROFILE_DB_PATH_PROPERTY = {
    "type": ["string", "null"],
    "description": (
        "Path of the SQLite client store (default: data/astro_mcp.sqlite3). "
        "Must resolve inside the server working directory, the system temp "
        "directory, or ASTRO_MCP_BASE_DIR; other paths are rejected."
    ),
}

# Every tool computes locally (Swiss Ephemeris + SQLite) — nothing calls out
# to the network, hence openWorldHint=False across the board.
_READ_ONLY = types.ToolAnnotations(readOnlyHint=True, openWorldHint=False)
_WRITES_REPORT_FILES = types.ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)
_UPSERTS_PROFILE = types.ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False
)

TOOL_DEFINITIONS: list[types.Tool] = [
    types.Tool(
        name="parse_birth_details",
        title="Parse Birth Details",
        description=(
            "Conservatively extract dob, tob, place, lat, lon, and timezone "
            "from a short operator note. Returns the recognised fields plus a "
            "'missing' list naming everything that could not be parsed, so the "
            "agent can ask the operator for clarification instead of guessing."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": (
                        "Free-form note with birth details, "
                        "e.g. 'born 26 Dec 2019, 9:15 am, Delhi'."
                    ),
                }
            },
            "required": ["text"],
            "additionalProperties": False,
        },
        annotations=_READ_ONLY,
    ),
    types.Tool(
        name="calculate_kundali",
        title="Calculate Kundali (Birth Chart)",
        description=(
            "Compute a sidereal Vedic kundali (birth chart) from birth details: "
            "lagna, Moon rashi, nakshatra with pada, planet positions with sign "
            "and whole-sign house placements, navamsa (D9) and further divisional "
            "charts, ashtakavarga tables, and the Vimshottari dasha seed. Returns "
            "the kundali JSON that the dasha, gochar, compatibility, and report "
            "tools consume."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                **_BIRTH_PROPERTIES,
                "ayanamsa": _AYANAMSA_PROPERTY,
            },
            "required": ["dob", "tob", "place", "lat", "lon", "timezone_name"],
            "additionalProperties": False,
        },
        annotations=_READ_ONLY,
    ),
    types.Tool(
        name="calculate_dasha",
        title="Calculate Vimshottari Dasha",
        description=(
            "Compute the Vimshottari dasha timeline from a kundali: mahadasha "
            "and antardasha periods with start/end dates, plus the running "
            "mahadasha/antardasha/pratyantardasha for on_date. Returns dasha "
            "JSON accepted by the report tools."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "kundali": _KUNDALI_PROPERTY,
                "on_date": {
                    "type": "string",
                    "description": (
                        "YYYY-MM-DD date to report the running period for (default: today)."
                    ),
                },
            },
            "required": ["kundali"],
            "additionalProperties": False,
        },
        annotations=_READ_ONLY,
    ),
    types.Tool(
        name="calculate_gochar",
        title="Calculate Gochar (Transits)",
        description=(
            "Compute gochar — planetary transits relative to the natal Moon and "
            "Lagna — plus the Saturn Sade Sati / Dhaiya phase for a date. "
            "Returns gochar JSON accepted by the report tools."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "kundali": _KUNDALI_PROPERTY,
                "on_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD date to compute transits for (default: today).",
                },
            },
            "required": ["kundali"],
            "additionalProperties": False,
        },
        annotations=_READ_ONLY,
    ),
    types.Tool(
        name="calculate_compatibility",
        title="Guna Milan Compatibility",
        description=(
            "Guna Milan (Ashtakoot, 36-point) marriage compatibility between two "
            "kundali JSONs (kundali_a = bride, kundali_b = groom). Returns the "
            "koota-wise point breakdown, the total out of 36, and Nadi, Bhakoot, "
            "and Manglik dosha findings."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "kundali_a": {
                    "type": "object",
                    "description": "Bride's kundali JSON from calculate_kundali.",
                },
                "kundali_b": {
                    "type": "object",
                    "description": "Groom's kundali JSON from calculate_kundali.",
                },
            },
            "required": ["kundali_a", "kundali_b"],
            "additionalProperties": False,
        },
        annotations=_READ_ONLY,
    ),
    types.Tool(
        name="calculate_panchang",
        title="Calculate Panchang",
        description=(
            "Compute the daily Panchang for a place and date: vara, tithi, "
            "nakshatra, yoga, karana, and sunrise/sunset times. Returns "
            "panchang JSON accepted by the report tools."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD date for the Panchang."},
                "place": {
                    "type": "string",
                    "description": "Place name; a label for output, not geocoded.",
                },
                "lat": {"type": "number", "description": "Latitude in decimal degrees."},
                "lon": {"type": "number", "description": "Longitude in decimal degrees."},
                "timezone_name": {
                    "type": "string",
                    "description": "IANA timezone of the place, e.g. Asia/Kolkata.",
                },
                "ayanamsa": _AYANAMSA_PROPERTY,
            },
            "required": ["date", "place", "lat", "lon", "timezone_name"],
            "additionalProperties": False,
        },
        annotations=_READ_ONLY,
    ),
    types.Tool(
        name="generate_report_json",
        title="Generate JSON Report",
        description=(
            "Assemble a structured astrology report draft (birth chart summary "
            "plus optional dasha/panchang/gochar sections) and write it to disk "
            "as JSON. Returns the report record: report_id, path of the written "
            "file, client_id, and created_at."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "kundali": _KUNDALI_PROPERTY,
                "dasha": _DASHA_PROPERTY,
                "panchang": _PANCHANG_PROPERTY,
                "gochar": _GOCHAR_PROPERTY,
                "gochar_narrative": _GOCHAR_NARRATIVE_PROPERTY,
                "synthesis": _SYNTHESIS_PROPERTY,
                "language": _LANGUAGE_PROPERTY,
                "client_id": _CLIENT_ID_PROPERTY,
                "client_name": _CLIENT_NAME_PROPERTY,
                "output_dir": _OUTPUT_DIR_PROPERTY,
                "db_path": _REPORT_DB_PATH_PROPERTY,
            },
            "required": ["kundali"],
            "additionalProperties": False,
        },
        annotations=_WRITES_REPORT_FILES,
    ),
    types.Tool(
        name="generate_pdf_report",
        title="Generate PDF Report",
        description=(
            "Render a client-facing PDF report (cover, Lagna/Chandra/Navamsa "
            "charts, planet table, dasha timeline) from a kundali plus optional "
            "sections. renderer='html' (default) uses Chromium via Playwright "
            "for polished Devanagari shaping; renderer='reportlab' is a "
            "pure-Python backend for environments without Chromium (such as "
            "the default Docker image). Returns the report record with the "
            "path of the written PDF."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "kundali": _KUNDALI_PROPERTY,
                "dasha": _DASHA_PROPERTY,
                "panchang": _PANCHANG_PROPERTY,
                "gochar": _GOCHAR_PROPERTY,
                "gochar_narrative": _GOCHAR_NARRATIVE_PROPERTY,
                "synthesis": _SYNTHESIS_PROPERTY,
                "language": _LANGUAGE_PROPERTY,
                "client_id": _CLIENT_ID_PROPERTY,
                "client_name": _CLIENT_NAME_PROPERTY,
                "output_dir": _OUTPUT_DIR_PROPERTY,
                "db_path": _REPORT_DB_PATH_PROPERTY,
                "renderer": {
                    "type": "string",
                    "enum": ["html", "reportlab"],
                    "default": "html",
                    "description": (
                        "'html' renders via Chromium/Playwright (best Devanagari "
                        "shaping); 'reportlab' needs no browser."
                    ),
                },
                "template": {
                    "type": "string",
                    "enum": ["standard", "pandit_v1"],
                    "default": "standard",
                    "description": (
                        "'standard' report, or 'pandit_v1' — the premium Hindi "
                        "janma-patrika layout (requires renderer='html')."
                    ),
                },
            },
            "required": ["kundali"],
            "additionalProperties": False,
        },
        annotations=_WRITES_REPORT_FILES,
    ),
    types.Tool(
        name="save_client_profile",
        title="Save Client Profile",
        description=(
            "Create or update (upsert by client_id) a client profile in the "
            "SQLite store, optionally with birth details. Returns the saved "
            "profile."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "profile": {
                    "type": "object",
                    "properties": {
                        "client_id": {
                            "type": "string",
                            "description": "Stable unique identifier for the client.",
                        },
                        "display_name": {
                            "type": "string",
                            "description": "Human-readable client name.",
                        },
                        "birth": {
                            "description": "Birth details to store with the profile.",
                            "anyOf": [
                                _BIRTH_DETAILS_SCHEMA,
                                {"type": "null"},
                            ],
                        },
                        "notes": {
                            "type": "string",
                            "description": "Free-form notes about the client.",
                        },
                    },
                    "required": ["client_id", "display_name"],
                },
                "db_path": _PROFILE_DB_PATH_PROPERTY,
            },
            "required": ["profile"],
            "additionalProperties": False,
        },
        annotations=_UPSERTS_PROFILE,
    ),
    types.Tool(
        name="find_client_profile",
        title="Find Client Profile",
        description=(
            "Look up a client profile by exact client_id, otherwise by "
            "case-insensitive display_name substring. Returns the profile, or "
            "null when nothing matches."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "client_id, or part of the display name.",
                },
                "db_path": _PROFILE_DB_PATH_PROPERTY,
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        annotations=_READ_ONLY,
    ),
    types.Tool(
        name="list_client_reports",
        title="List Client Reports",
        description=(
            "List report records previously generated for a client, newest "
            "first. Each record carries report_id, report_type, path, and "
            "created_at."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "client_id": {
                    "type": "string",
                    "description": "Client identifier whose reports to list.",
                },
                "db_path": _PROFILE_DB_PATH_PROPERTY,
            },
            "required": ["client_id"],
            "additionalProperties": False,
        },
        annotations=_READ_ONLY,
    ),
]


def _build_server() -> Server:
    server: Server = Server(SERVER_NAME)

    @server.list_tools()
    async def _handle_list_tools() -> list[types.Tool]:
        return TOOL_DEFINITIONS

    @server.call_tool()
    async def _handle_call_tool(
        name: str, arguments: dict[str, Any] | None
    ) -> list[types.TextContent]:
        fn = get_tool(name)
        kwargs = dict(arguments or {})
        # Run the (synchronous) tool in a worker thread: keeps the MCP event loop
        # responsive, and lets the PDF tool use Playwright's sync API (which refuses
        # to run inside a thread that has a live asyncio loop).
        result = await asyncio.to_thread(fn, **kwargs)
        payload = json.dumps(result, ensure_ascii=False, default=str)
        return [types.TextContent(type="text", text=payload)]

    return server


def build_initialization_options(server: Server) -> InitializationOptions:
    return InitializationOptions(
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        capabilities=server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )


async def run_stdio() -> None:
    server = _build_server()
    options = build_initialization_options(server)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)


def main() -> None:
    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
