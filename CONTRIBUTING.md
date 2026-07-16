# Contributing

## Dev setup

```bash
git clone https://github.com/adityarya24/astro-skill.git
cd astro-skill
python -m venv .venv && . .venv/bin/activate    # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Or with [uv](https://docs.astral.sh/uv/) (uses `.python-version`, pinned to
3.11 so `pyswisseph` installs from a prebuilt wheel):

```bash
uv sync
```

## Running tests

```bash
python -m pytest -q
python -m ruff check astro services scripts
```

The HTML/Chromium PDF render test skips automatically until Chromium is
installed (`python -m playwright install chromium`).

## Pull requests

- Tests and ruff must pass before review.
- Match the existing code style — the `TOOLS` registry in
  `services/astro_mcp/tools.py` is the single source of truth; don't duplicate
  calculation logic elsewhere.
- Keep PRs scoped to one change; note behaviour changes in `CHANGELOG.md`.

## Reporting issues

Open a [GitHub issue](https://github.com/adityarya24/astro-skill/issues) with
repro steps. For security issues, see [`SECURITY.md`](SECURITY.md) instead.
