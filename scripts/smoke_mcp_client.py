#!/usr/bin/env python
"""Fresh-install smoke for the astro_mcp stdio server.

Launches ``python -m services.astro_mcp`` over stdio with the MCP client SDK
and exercises the same handful of tools a real MCP-aware agent would call
right after installation:

* ``list_tools``
* ``calculate_panchang``
* ``calculate_kundali``
* ``generate_report_json`` (writing into a temporary directory)

Prints a PASS/FAIL summary and exits with status 0 on success, 1 on failure.
Intended to be run from the repo root, e.g.::

    .\\.venv\\Scripts\\python.exe scripts\\smoke_mcp_client.py
    ./.venv/bin/python scripts/smoke_mcp_client.py
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO_ROOT = Path(__file__).resolve().parents[1]

SAMPLE_BIRTH = {
    "dob": "26/12/2019",
    "tob": "09:15",
    "place": "Delhi",
    "lat": 28.6139,
    "lon": 77.2090,
    "timezone_name": "Asia/Kolkata",
}

DELHI_PANCHANG = {
    "date": "2026-05-21",
    "place": "Delhi",
    "lat": 28.6139,
    "lon": 77.209,
    "timezone_name": "Asia/Kolkata",
}

EXPECTED_TOOLS = {
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


def _server_params(python_exe: str | None) -> StdioServerParameters:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return StdioServerParameters(
        command=python_exe or sys.executable,
        args=["-m", "services.astro_mcp"],
        env=env,
        cwd=str(REPO_ROOT),
    )


def _parse_text(call_result) -> dict:
    if not call_result.content:
        raise RuntimeError("Empty tool result")
    first = call_result.content[0]
    text = getattr(first, "text", None)
    if text is None:
        raise RuntimeError(f"Tool result was not text: {first!r}")
    return json.loads(text)


async def _run_checks(python_exe: str | None, output_dir: Path) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    async with stdio_client(_server_params(python_exe)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            ok = names == EXPECTED_TOOLS
            detail = (
                f"{len(names)} tools"
                if ok
                else f"missing={sorted(EXPECTED_TOOLS - names)} extra={sorted(names - EXPECTED_TOOLS)}"
            )
            results.append(("list_tools", ok, detail))

            panchang = _parse_text(await session.call_tool("calculate_panchang", DELHI_PANCHANG))
            vara = panchang.get("panchang", {}).get("vara")
            results.append(("calculate_panchang", vara == "Guruvara", f"vara={vara}"))

            kundali = _parse_text(await session.call_tool("calculate_kundali", SAMPLE_BIRTH))
            lagna = kundali.get("lagna")
            results.append(("calculate_kundali", lagna == "Makara", f"lagna={lagna}"))

            report = _parse_text(
                await session.call_tool(
                    "generate_report_json",
                    {
                        "kundali": kundali,
                        "language": "hin",
                        "client_id": "smoke-client",
                        "output_dir": str(output_dir),
                    },
                )
            )
            path = Path(report.get("path", ""))
            ok = (
                report.get("report_type") == "json_report"
                and path.exists()
                and output_dir.resolve() in path.resolve().parents
            )
            results.append(
                (
                    "generate_report_json",
                    ok,
                    f"path={path.name} exists={path.exists()}",
                )
            )

    return results


def _print_summary(results: list[tuple[str, bool, str]]) -> bool:
    print()
    print("Astro MCP smoke summary")
    print("-" * 40)
    overall = True
    for name, ok, detail in results:
        marker = "PASS" if ok else "FAIL"
        if not ok:
            overall = False
        print(f"  {marker}  {name:<22}  {detail}")
    print("-" * 40)
    print("RESULT:", "PASS" if overall else "FAIL")
    return overall


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python",
        default=None,
        help="Python executable used to launch the MCP server (default: current interpreter).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for the generated report. Defaults to a temp dir cleaned up on exit.",
    )
    args = parser.parse_args(argv)

    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        results = asyncio.run(_run_checks(args.python, output_dir))
    else:
        with tempfile.TemporaryDirectory(prefix="astro_mcp_smoke_") as tmp:
            results = asyncio.run(_run_checks(args.python, Path(tmp)))

    return 0 if _print_summary(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
