# Astro Skill Roadmap

Generic roadmap for the astrology engine and skill. Product-specific workflows
(a web panel, a chat or voice front-end) are optional integrations and live in
their own docs.

## Current Baseline

The `astro` skill is a portable baseline usable by any agent or MCP client.

Current capabilities:

- Kundali calculation from birth details, plus the Navamsa (D9) divisional chart.
- Whole-sign houses with Lahiri (Chitrapaksha) sidereal ayanamsa.
- Vimshottari mahadasha and antardasha timeline (correct birth-balance handling).
- Daily Panchang, anchored at sunrise, with muhurta and yoga detection.
- Structured report JSON.
- Hindi/English PDF report with birth summary, North Indian chart, graha table,
  dasha table, Panchang section, and safety notes.
- Bundled Swiss Ephemeris `.se1` data (high-precision SWIEPH) and a bundled Noto
  Sans Devanagari font, so precision and Hindi rendering need nothing from the host.
- Safety boundaries against death, medical, accident, and unavoidable-harm
  certainty predictions.

`services/astro_mcp/` wraps the same calculators as a generic stdio MCP server
(9 tools) — see `services/astro_mcp/README.md`.

## PDF Renderers

- **HTML/Chromium** (default, `--renderer html`) — `astro/scripts/html_pdf_report.py`
  composes self-contained HTML with print CSS and rasterises it through
  Playwright/Chromium. Devanagari shaping is handled by the browser text engine.
  Requires a one-time `python -m playwright install chromium`.
- **ReportLab** (legacy, `--renderer reportlab`) — in-process ReportLab pipeline.
  No browser dependency, lower-quality Devanagari shaping. Preserved so the
  toolkit still produces usable PDFs where installing Chromium is not an option.

## Future Astrology Modules

Add these when a calling agent or downstream product needs them. None are tied
to a specific product — they enrich the generic engine:

- Gochar / transit tracking.
- Compatibility and guna milan.
- Sade sati and major transit flags.
- Remedy drafting (operator-reviewed).
- Richer Hindi/English interpretation pages.

## Layer Boundary

The skill stays portable and calculation-first. Do not pull product logic into
`astro/`.

Stateful work belongs in `services/astro_mcp/`:

- client profile storage
- report history
- file delivery boundaries
- future cross-product helpers

Product-shaped behaviour (chat, voice, web panels, access control, delivery
hooks) belongs in `apps/`, not in the engine or the MCP server.

## Out Of Scope For The Engine

- Public/client-facing automation.
- Final predictive judgement — that always sits with the reviewing operator.
- Per-product UX shells.
