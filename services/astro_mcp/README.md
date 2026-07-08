# Astro MCP Service

Generic local **Vedic astrology MCP server**. Wraps the portable `astro`
calculators with SQLite storage and a runnable stdio MCP server. Any
MCP-compatible client (Claude Desktop, Codex, or a custom agent) can
use it as a stable astrology backend.

No environment variables are required to run it. SQLite + filesystem only.

## v0.1 Tool Surface (11 tools)

Implemented, registered with the MCP server, and exercised by tests:

- `parse_birth_details` — conservative parser for short birth-detail text.
- `save_client_profile` — upsert a client (with optional birth details) into SQLite.
- `find_client_profile` — look up a client by `client_id` (exact) or `display_name` (substring).
- `list_client_reports` — list previously generated reports for a client, newest first.
- `calculate_kundali` — Lahiri/whole-sign kundali via `astro/scripts/kundali_calculator.py`.
- `calculate_dasha` — Vimshottari timeline via `astro/scripts/dasha_calculator.py`.
- `calculate_gochar` — gochar transits and Saturn cycle via `astro/scripts/gochar_calculator.py`.
- `calculate_compatibility` — Guna Milan compatibility via `astro/scripts/guna_milan.py`.
- `calculate_panchang` — daily Panchang via `astro/scripts/panchang_calculator.py`.
- `generate_report_json` — structured astrology draft JSON via `astro/scripts/report_generator.py`.
- `generate_pdf_report` — formatted PDF via `astro/scripts/pdf_report.py`.
  Accepts an optional `client_name` arg for the cover page.
  Accepts `template="pandit_v1"` for the premium Pandit Report v1 HTML layout.
  Accepts a `renderer` arg: `"html"` (default, Chromium via Playwright) for
  polished Devanagari output, or `"reportlab"` for the legacy in-process
  fallback when Chromium is not installed.

## Layout

```
services/astro_mcp/
├── __init__.py   # exports TOOLS, makes the dir a package
├── __main__.py   # `python -m services.astro_mcp` entry
├── models.py     # BirthDetails, ClientProfile, ReportRecord dataclasses
├── storage.py    # SQLite schema + CRUD helpers
├── tools.py      # JSON-friendly tool functions wrapping astro/scripts/*
├── server.py     # MCP stdio Server, TOOL_DEFINITIONS, list_tool_names(), get_tool()
└── README.md
```

## Running The MCP Server

```powershell
# Windows
.\.venv\Scripts\python.exe -m services.astro_mcp
.\.venv\Scripts\python.exe -m services.astro_mcp.server
```

```bash
# macOS / Linux
./.venv/bin/python -m services.astro_mcp
./.venv/bin/python -m services.astro_mcp.server
```

After `pip install -e .` the `astro-mcp` console script is installed on PATH
and can be used in place of either command.

The process speaks Model Context Protocol over stdio. Wire it into any MCP
client by pointing the client at one of the commands above with `cwd` set to
the repo root. No env vars are required.

### Example client config — Windows

```json
{
  "mcpServers": {
    "astro": {
      "command": "C:\\path\\to\\astro-skill\\.venv\\Scripts\\python.exe",
      "args": ["-m", "services.astro_mcp"],
      "cwd": "C:\\path\\to\\astro-skill"
    }
  }
}
```

### Example client config — macOS / Linux

```json
{
  "mcpServers": {
    "astro": {
      "command": "/path/to/astro-skill/.venv/bin/python",
      "args": ["-m", "services.astro_mcp"],
      "cwd": "/path/to/astro-skill"
    }
  }
}
```

## PDF Renderer Dependency

`generate_pdf_report` defaults to the HTML/Chromium pipeline, which uses
Playwright. The Python package is listed in `pyproject.toml`, but the
Chromium binary is a separate one-time install:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

```bash
./.venv/bin/python -m playwright install chromium
```

If Chromium is missing, calls with `renderer="html"` raise a clear
`RuntimeError` with the install command. To skip Chromium entirely, pass
`renderer="reportlab"` — that path needs no browser.

## Storage

- SQLite database, default path: `data/astro_mcp.sqlite3` (relative to the
  process working directory). Override via the `db_path` argument on each
  tool. Pass `null` to skip persistence entirely.
- Generated reports default to `data/reports/`. Override via the `output_dir`
  argument. `data/` is created on demand.
- Schema is initialised on first call (`init_db`) — safe to call repeatedly.
- Filenames are derived from the server-generated `report_id` only; caller
  identifiers like `client_id` never appear in the filename, so they cannot be
  used to escape `output_dir` (`tests/test_astro_mcp_tools.py` covers the
  `../evil` traversal case).
- **Backup:** treat `data/astro_mcp.sqlite3` and `data/reports/` as operator
  data. Copy or snapshot them before redeploys; there is no automatic migration
  beyond `CREATE TABLE IF NOT EXISTS` on startup.

## Local Testing

From the repo root, with the project virtualenv active:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest astro/tests/test_astro_mcp_storage.py -q
.\.venv\Scripts\python.exe -m pytest astro/tests/test_astro_mcp_tools.py -q
.\.venv\Scripts\python.exe -m pytest astro/tests/test_astro_mcp_server.py -q
.\.venv\Scripts\python.exe -m ruff check astro services scripts
```

The astro skill calculators are not duplicated — `tools.py` imports the
package modules under `astro.scripts` and keeps the MCP layer as a thin wrapper.

## Downstream Workflows (Optional)

This server is generic. Some downstream products that can be built on top:

- **Astrologer assistant** — an agent that parses birth details, runs the
  calculators, and drafts reports for an astrologer to review.
- **Delivery shim** — a separate process (chat, email, etc.) that calls these
  tools and returns the results.
- **Voice/transcription pre-processor** — feeds parsed birth details in.
- **Web panel** — reuses the same registry instead of duplicating calculators.

Each of these belongs in its own service or app; the goal here is a clean,
test-covered tool boundary that those layers can plug into.
