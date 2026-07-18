from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from services.astro_mcp.server import TOOL_DEFINITIONS

ROOT = Path(__file__).resolve().parents[2]

# Neutral sample birth (26/12/2019 09:15 IST, Delhi) — Makara lagna, verified
# against DrikPanchang (udaya lagna 08:36–10:19 covers 09:15).
SAMPLE_BIRTH = {
    "dob": "26/12/2019",
    "tob": "09:15",
    "place": "Delhi",
    "lat": 28.6139,
    "lon": 77.2090,
    "timezone_name": "Asia/Kolkata",
}


def _server_params() -> StdioServerParameters:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "services.astro_mcp"],
        env=env,
        cwd=str(ROOT),
    )


async def _drive_session(tmp_path: Path) -> dict:
    out: dict = {}
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            out["tool_names"] = sorted(tool.name for tool in tools.tools)

            panchang_call = await session.call_tool(
                "calculate_panchang",
                {
                    "date": "2026-05-21",
                    "place": "Delhi",
                    "lat": 28.6139,
                    "lon": 77.209,
                    "timezone_name": "Asia/Kolkata",
                },
            )
            out["panchang"] = json.loads(panchang_call.content[0].text)

            kundali_call = await session.call_tool("calculate_kundali", SAMPLE_BIRTH)
            kundali = json.loads(kundali_call.content[0].text)
            out["kundali_lagna"] = kundali["lagna"]

            report_call = await session.call_tool(
                "generate_report_json",
                {
                    "kundali": kundali,
                    "language": "hin",
                    "client_id": "client-mcp-smoke",
                    "output_dir": str(tmp_path),
                },
            )
            out["report"] = json.loads(report_call.content[0].text)
    return out


@pytest.mark.skipif(sys.platform == "win32" and sys.version_info < (3, 11), reason="asyncio subprocess needs 3.11+ on Windows")
def test_mcp_stdio_server_lists_tools_and_dispatches_calls(tmp_path: Path):
    result = asyncio.run(_drive_session(tmp_path))

    expected_tools = {
        "calculate_compatibility",
        "calculate_dasha",
        "calculate_gochar",
        "calculate_kundali",
        "calculate_panchang",
        "find_client_profile",
        "generate_pdf_report",
        "generate_report_json",
        "list_client_reports",
        "parse_birth_details",
        "save_client_profile",
    }
    assert set(result["tool_names"]) == expected_tools

    assert result["panchang"]["panchang"]["vara"] == "Guruvara"
    assert result["panchang"]["calculation"]["ayanamsa"] == "lahiri"
    assert result["kundali_lagna"] == "Makara"

    report = result["report"]
    assert report["client_id"] == "client-mcp-smoke"
    assert report["report_type"] == "json_report"
    written = Path(report["path"])
    assert written.exists()
    assert tmp_path.resolve() in written.resolve().parents
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["sections"]["birth_chart"]["lagna"] == "Makara"


def test_generate_pdf_report_schema_accepts_optional_brand():
    tool = next(tool for tool in TOOL_DEFINITIONS if tool.name == "generate_pdf_report")

    brand = tool.inputSchema["properties"]["brand"]
    assert brand["type"] == "string"
    assert brand["default"] == ""
    assert "brand" not in tool.inputSchema["required"]
