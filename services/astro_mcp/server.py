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

_BIRTH_DETAILS_SCHEMA = {
    "type": "object",
    "properties": {
        "dob": {"type": "string", "description": "DD/MM/YYYY or YYYY-MM-DD"},
        "tob": {"type": "string", "description": "HH:MM (24h) local time"},
        "place": {"type": "string"},
        "lat": {"type": "number"},
        "lon": {"type": "number"},
        "timezone_name": {"type": "string", "description": "IANA name, eg Asia/Kolkata"},
    },
    "required": ["dob", "tob", "place", "lat", "lon", "timezone_name"],
    "additionalProperties": False,
}

TOOL_DEFINITIONS: list[types.Tool] = [
    types.Tool(
        name="parse_birth_details",
        description=(
            "Conservatively extract dob, tob, place, lat, lon, and timezone "
            "from a short operator note. Missing fields are returned in the "
            "'missing' list so the agent can ask the operator for clarification."
        ),
        inputSchema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="calculate_kundali",
        description="Compute Lahiri/whole-sign kundali (lagna, rashi, nakshatra, planets, houses, dasha seed).",
        inputSchema={
            "type": "object",
            "properties": {
                "dob": {"type": "string"},
                "tob": {"type": "string"},
                "place": {"type": "string"},
                "lat": {"type": "number"},
                "lon": {"type": "number"},
                "timezone_name": {"type": "string"},
                "ayanamsa": {"type": "string", "default": "lahiri"},
            },
            "required": ["dob", "tob", "place", "lat", "lon", "timezone_name"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="calculate_dasha",
        description="Compute Vimshottari mahadasha and antardasha timeline from a kundali JSON.",
        inputSchema={
            "type": "object",
            "properties": {
                "kundali": {"type": "object"},
                "on_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["kundali"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="calculate_gochar",
        description="Compute gochar (planetary transits from natal Moon and Lagna) and the Saturn Sade Sati / Dhaiya cycle for a date.",
        inputSchema={
            "type": "object",
            "properties": {
                "kundali": {"type": "object"},
                "on_date": {"type": "string", "description": "YYYY-MM-DD (default: today)"},
            },
            "required": ["kundali"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="calculate_compatibility",
        description=(
            "Guna Milan (Ashtakoot, 36-point) marriage compatibility between two "
            "kundali JSONs (kundali_a = bride, kundali_b = groom), including Nadi, "
            "Bhakoot, and Manglik doshas."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "kundali_a": {"type": "object"},
                "kundali_b": {"type": "object"},
            },
            "required": ["kundali_a", "kundali_b"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="calculate_panchang",
        description="Compute daily Panchang (vara, tithi, nakshatra, yoga, karana, sunrise/sunset) for a place and date.",
        inputSchema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "place": {"type": "string"},
                "lat": {"type": "number"},
                "lon": {"type": "number"},
                "timezone_name": {"type": "string"},
                "ayanamsa": {"type": "string", "default": "lahiri"},
            },
            "required": ["date", "place", "lat", "lon", "timezone_name"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="generate_report_json",
        description="Build a structured astrology draft from kundali (+ optional dasha and panchang) and write JSON to disk.",
        inputSchema={
            "type": "object",
            "properties": {
                "kundali": {"type": "object"},
                "dasha": {"type": ["object", "null"]},
                "panchang": {"type": ["object", "null"]},
                "gochar": {"type": ["object", "null"]},
                "language": {"type": "string", "default": "hin"},
                "client_id": {"type": "string", "default": "anonymous"},
                "client_name": {
                    "type": ["string", "null"],
                    "description": "Client/native name shown on the PDF cover page",
                },
                "output_dir": {"type": ["string", "null"]},
                "db_path": {"type": ["string", "null"]},
            },
            "required": ["kundali"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="generate_pdf_report",
        description=(
            "Render the astrology draft as a PDF with charts. Returns the path "
            "and metadata. renderer='html' (default) uses Chromium via "
            "Playwright for polished Devanagari shaping; renderer='reportlab' "
            "keeps the legacy in-process backend for environments without "
            "Chromium installed."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "kundali": {"type": "object"},
                "dasha": {"type": ["object", "null"]},
                "panchang": {"type": ["object", "null"]},
                "language": {"type": "string", "default": "hin"},
                "client_id": {"type": "string", "default": "anonymous"},
                "output_dir": {"type": ["string", "null"]},
                "db_path": {"type": ["string", "null"]},
                "renderer": {
                    "type": "string",
                    "enum": ["html", "reportlab"],
                    "default": "html",
                },
                "template": {
                    "type": "string",
                    "enum": ["standard", "pandit_v1"],
                    "default": "standard",
                },
            },
            "required": ["kundali"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="save_client_profile",
        description="Upsert a client profile (with optional birth details) into the SQLite store.",
        inputSchema={
            "type": "object",
            "properties": {
                "profile": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string"},
                        "display_name": {"type": "string"},
                        "birth": {
                            "anyOf": [
                                _BIRTH_DETAILS_SCHEMA,
                                {"type": "null"},
                            ]
                        },
                        "notes": {"type": "string"},
                    },
                    "required": ["client_id", "display_name"],
                },
                "db_path": {"type": ["string", "null"]},
            },
            "required": ["profile"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="find_client_profile",
        description="Look up a client by exact client_id, otherwise by case-insensitive display_name substring.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "db_path": {"type": ["string", "null"]},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="list_client_reports",
        description="List previously generated reports for a client, newest first.",
        inputSchema={
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "db_path": {"type": ["string", "null"]},
            },
            "required": ["client_id"],
            "additionalProperties": False,
        },
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
