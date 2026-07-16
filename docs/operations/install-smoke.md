# Astro MCP — Install & Smoke

Walks a fresh agent or operator through standing up the astro MCP server on a
clean machine and verifying it works end-to-end. Designed to mirror what a
new MCP client (Claude Desktop, Codex, or a custom agent) will do the
first time it consumes this repo.

## Assumptions

- Fresh clone of `astro-skill`.
- Python **3.11 or newer** available on PATH (verify with `python --version`).
- Network access for `pip install` from PyPI.
- No environment variables required.

## 1. Setup

### Windows (PowerShell)

```powershell
git clone https://github.com/adityarya24/astro-skill.git
cd astro-skill

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### macOS / Linux (bash/zsh)

```bash
git clone https://github.com/adityarya24/astro-skill.git
cd astro-skill

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

`.[dev]` installs the runtime deps (`mcp`, `playwright`, `pyswisseph`,
`reportlab`, …) plus the dev extras (`pytest`, `pytest-asyncio`, `pypdf`,
`pyyaml`, `ruff`).

### Optional: Chromium for the HTML PDF renderer

`generate_pdf_report` defaults to `renderer="html"`, which uses Playwright
to drive Chromium. The Python package is installed by the step above, but
the browser binary is a separate one-time install:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

```bash
./.venv/bin/python -m playwright install chromium
```

If you skip this, PDF generation works only with `renderer="reportlab"`
(legacy in-process backend); the HTML test in `test_pdf_report.py` is
skipped automatically until Chromium is present.

## 2. Run The Test Suite

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

```bash
./.venv/bin/python -m pytest -q
```

Expect all tests to pass, with the HTML/Chromium PDF render test skipped until
Chromium is installed — it activates after
`python -m playwright install chromium`.
The suite includes real MCP stdio smoke coverage
(`astro/tests/test_astro_mcp_server.py`) that spawns the server in a
subprocess and round-trips through the SDK, plus the user-facing smoke script
test (`astro/tests/test_smoke_mcp_script.py`).

## 3. Run The MCP Server

Pick whichever invocation suits the client wiring. All three do the same
thing — they spin up the stdio server bound to the 11-tool registry.

```powershell
# Module form
.\.venv\Scripts\python.exe -m services.astro_mcp

# Explicit server module
.\.venv\Scripts\python.exe -m services.astro_mcp.server

# Console script (after `pip install -e .`)
astro-mcp
```

```bash
./.venv/bin/python -m services.astro_mcp
./.venv/bin/python -m services.astro_mcp.server
astro-mcp
```

The process listens on stdio and waits for an MCP client to connect. It will
appear "idle" until a client speaks to it — that is expected.

## 4. MCP Client Config Examples

These snippets show how to register the server with an MCP-aware client.
Replace the absolute paths to match your machine.

### Windows — module form

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

### Windows — console script

```json
{
  "mcpServers": {
    "astro": {
      "command": "C:\\path\\to\\astro-skill\\.venv\\Scripts\\astro-mcp.exe",
      "args": [],
      "cwd": "C:\\path\\to\\astro-skill"
    }
  }
}
```

### macOS / Linux — module form

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

### macOS / Linux — console script

```json
{
  "mcpServers": {
    "astro": {
      "command": "/path/to/astro-skill/.venv/bin/astro-mcp",
      "args": [],
      "cwd": "/path/to/astro-skill"
    }
  }
}
```

Set `cwd` to the repo root so the default SQLite path
(`data/astro_mcp.sqlite3`) and the default report directory
(`data/reports/`) resolve under the project, not the client's working
directory.

## 5. Automated Smoke Script

The repo ships a one-shot client at `scripts/smoke_mcp_client.py` that does
exactly what a new agent would do on first contact:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_mcp_client.py
```

```bash
./.venv/bin/python scripts/smoke_mcp_client.py
```

Expected output:

```
Astro MCP smoke summary
----------------------------------------
  PASS  list_tools              11 tools
  PASS  calculate_panchang      vara=Guruvara
  PASS  calculate_kundali       lagna=Mesha
  PASS  generate_report_json    path=rpt-XXXXXXXXXXXX.json exists=True
----------------------------------------
RESULT: PASS
```

Exit code is `0` on PASS and `1` on FAIL — wire this into CI or a release
checklist if you want.

Useful flags:

- `--python /path/to/python` — launch the server with a different interpreter
  (defaults to the one running the script).
- `--output-dir <path>` — keep the generated report at `<path>` instead of a
  temp dir that gets deleted on exit.

## 6. Manual Smoke Checklist

If you'd rather drive the server by hand from an MCP client, walk through
this list. Every step should pass without any product-specific setup.

- [ ] **List tools.** Expect exactly 9 names:
  `parse_birth_details`, `save_client_profile`, `find_client_profile`,
  `list_client_reports`, `calculate_kundali`, `calculate_dasha`,
  `calculate_panchang`, `generate_report_json`, `generate_pdf_report`.
- [ ] **Call `calculate_panchang`** with Delhi for `2026-05-21`
  (`lat=28.6139`, `lon=77.209`, `timezone_name=Asia/Kolkata`). Expect
  `panchang.vara == "Guruvara"` and `calculation.ayanamsa == "lahiri"`.
- [ ] **Call `calculate_kundali`** with the sample birth data
  (`dob=26/12/2019`, `tob=09:15`, `place=Delhi`, `lat=28.6139`,
  `lon=77.2090`, `timezone_name=Asia/Kolkata`). Expect `lagna == "Makara"`,
  `rashi == "Dhanu"`, `nakshatra == "Mula"`.
- [ ] **Call `generate_report_json`** with the kundali above, an explicit
  `output_dir` (e.g. a temp dir), and any `client_id`. Expect a response
  containing `report_type == "json_report"` and a `path` that exists on
  disk.
- [ ] **Confirm the report file exists** at the returned path and parses as
  JSON.

## 7. MCP data backup

When client profiles or generated reports matter in production, back up:

- `data/astro_mcp.sqlite3` — client rows and report index
- `data/reports/` — JSON/PDF artifacts referenced by the database

Copy both before image upgrades or `git pull` deploys that might reset the
working tree. Override paths with per-tool `db_path` / `output_dir` if you
keep data outside the repo checkout.

## 8. Troubleshooting

- **`ModuleNotFoundError: No module named 'services'`** — the server must be
  launched from the repo root (or with the repo root on `PYTHONPATH`).
  Either `cd` in first or set `cwd` in the MCP client config.
- **`pyswisseph` install fails on Windows** — install the Microsoft C++
  Build Tools or upgrade pip; wheels are published for Python 3.11/3.12.
- **MCP client sees zero tools** — confirm the server process actually
  started. Run the smoke script (`scripts/smoke_mcp_client.py`); if that
  PASSes, the issue is in the client config (most often `cwd` or
  `command` path).
- **HTML PDF generation says Chromium is missing** — run
  `python -m playwright install chromium` in the project virtualenv, or pass
  `renderer="reportlab"` for the legacy no-browser fallback.
- **ReportLab Hindi output looks poorly shaped** — use the default
  HTML/Chromium renderer for production Hindi PDFs. ReportLab is kept only as
  a low-dependency fallback.
