# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- The default `Dockerfile` is now slim — no Playwright/Chromium, so it builds
  fast and small; call `generate_pdf_report` with `renderer="reportlab"` there.
  The original full image (Chromium HTML renderer for polished Devanagari)
  moved to `Dockerfile.full`: `docker build -f Dockerfile.full -t astro-skill .`

### Fixed
- `.python-version` pins uv to Python 3.11 so `uv sync` installs pyswisseph
  from a prebuilt wheel — source builds fail in compiler-less environments
  such as registry build infra (this unblocked the Glama build test).
- The MCP server now reports version 1.0.0 (was 0.1.0), matching the package.

## [1.0.0] - 2026-07-02

First public release.

### Added
- **Pandit Report v1** (`template="pandit_v1"`). A premium 20+ page Hindi
  report: mahadasha pages, life summary, dasha and gochar संकेत, yog/dosh,
  remedies, a pandit review note, and a final summary — alongside the standard
  cover, charts (Lagna/Chandra/Navamsa), planet table, and dasha timeline.
  Available from both the CLI (`--template pandit_v1`) and the MCP
  `generate_pdf_report` tool.
- **Client name on the PDF cover.** Resolution order: explicit `client_name` →
  input `client_name` → input `name` → place.
- **Ganesha cover motif.** The HTML PDF cover carries a minimal line-art Ganesha
  medallion (inline SVG, deep-red strokes with gold accents) above the title;
  the cover itself is now a full-page, vertically centred layout with a
  lagna/rashi/nakshatra summary line.
- **Pratyantardasha in the PDF.** The current-dasha table shows the running
  period at maha/antar/pratyantar precision (e.g. शुक्र/चंद्र/चंद्र) plus a
  pratyantardasha end-date row.
- **Pratyantardasha (3rd dasha level).** The current dasha period now reports the
  running pratyantardasha and its end date (maha/antar/pratyantar precision).
- **Selectable ayanamsa.** Kundali and Panchang accept Lahiri (default), Raman,
  Krishnamurti/KP, Fagan-Bradley, True Chitra, and Yukteshwar; the output records
  the ayanamsa actually used.
- **Divisional charts (D2/D3/D7/D10/D12).** `calculate_kundali` now carries a
  `divisional_charts` block placing every planet + Lagna in the Hora, Drekkana,
  Saptamsa, Dasamsa (career), and Dwadasamsa vargas (D9/Navamsa stays separate).
- **Ashtakavarga (Bhinna + Sarva).** `calculate_kundali` now carries an
  `ashtakavarga` block: each planet's bindus per sign plus the Sarvashtakavarga
  totals (from the canonical Parashari benefic tables in
  `astro/data/ashtakavarga_data.json`).
- **Graha drishti (aspects).** `calculate_kundali` now carries an `aspects`
  block: each graha's full (Parashari) aspects — 7th for all, plus Mars 4/8,
  Jupiter 5/9, Saturn 3/10, nodes 5/9 — with the planets it aspects and is
  aspected by.
- **Gochar (transits) + Sade Sati.** New `calculate_gochar` MCP tool: current
  transits reckoned from the natal Moon and Lagna, plus Saturn's Sade Sati
  (rising/peak/setting) and Dhaiya (kantaka/ashtama) with sign-ingress/egress
  dates.
- **Guna Milan (Ashtakoot compatibility).** New `calculate_compatibility` MCP
  tool: the eight kutas (36 points) between two charts, with Nadi/Bhakoot/Manglik
  doshas and cancellations and a verdict band. Standard tables live in
  `astro/data/compatibility_data.json`.
- **Yoga detection and Panchang muhurtas.** Daily Panchang now surfaces
  auspicious/inauspicious yogas and muhurta windows alongside the core fields.
- **Bundled Swiss Ephemeris data.** The high-precision SWIEPH `.se1` files ship
  in `astro/ephe/` (and inside the Docker image), so charts use the precise
  ephemeris out of the box instead of the Moshier fallback. Each output records
  the tier in `calculation.ephemeris`.
- **Birth-detail input validation** on the calculators, with clearer errors for
  malformed dates, times, and coordinates.
- **`ASTRO_CHROMIUM_EXECUTABLE`** lets the HTML PDF renderer use a pre-installed
  Chromium instead of a Playwright-managed one.
- **Natural-language dates and `IST` in `parse_birth_details`.** The parser now
  reads written-out dates ("26th December 2019") and resolves the `IST`
  abbreviation to `Asia/Kolkata`, on top of the numeric-date and IANA-zone paths.
- **Navamsa (D9) divisional chart.** The kundali JSON now includes a `navamsa`
  block (D9 lagna, per-planet D9 sign, and whole-sign D9 houses), and the PDF
  renders it as a second North-Indian chart ("नवांश कुंडली (D9)"). Navamsa is
  the most important divisional chart after the Rashi chart and is expected in
  any serious Vedic reading. D9 signs use the continuous 3°20' navamsa rule,
  which reproduces the classical movable/fixed/dual element rule.

### Changed
- **North Indian chart cells show rashi numbers (1-12)** — the standard NI
  convention — instead of house numbers + full sign names (those stay in the
  planet table). The chart renders at 480px (viewBox unchanged, so text scales).
- **Repository genericized for public release.** Removed the private OpenClaw/VPS
  deployment scripts (`infra/`) and internal planning docs; rewrote the README
  and architecture docs as a generic astrology engine + MCP server; added
  `docs/deploy.md` (Docker / MCP-client wiring).
- **Swiss Ephemeris calls are serialized** behind a lock so concurrent MCP tool
  calls stay thread-safe.
- **Panchang is now anchored at sunrise instead of local noon.** Classical
  Hindu Panchang defines the tithi/nakshatra/yoga/karana of a day by the values
  prevailing at sunrise. The previous noon anchor could report a different
  (incorrect) tithi or nakshatra on transition days. Positions now fall back to
  local noon (with a warning) only when sunrise cannot be computed.
- **PDF report is now fully Hindi for the `hi`/`hin` languages.** Yoga names,
  karana names, the `Vimshottari` system label, and the dasha period/seed
  planet and nakshatra names are translated to Devanagari (previously left as
  `Shiva`, `Vishti`, `Vimshottari`, `Mangal/Mangal`).
- **Planet degrees are formatted as degrees-minutes** (e.g. `8°46'`) instead of
  raw decimals (`8.762598`).
- **Sunrise/sunset are shown as local `HH:MM`** instead of full ISO timestamps.

### Fixed
- **Built wheels include the runtime assets** (SKILL.md, config, data JSON,
  ephemeris files, Devanagari font) via `package-data`, and the calculator
  scripts import cleanly in both direct-script and installed-package modes.
- **README/MCP docs tool count** aligned with the server registry (11 tools).
- **North Indian chart text no longer crosses cell lines.** The 12 houses are
  exact vertex polygons (corners, edge midpoints, centre, quarter points);
  labels sit at polygon centroids and planet blocks are clamped to each cell's
  measured spans — crowded houses (4+ planets) shrink to 8px and split into two
  columns where the cell is wide enough, so even a 6-planet stellium in a corner
  triangle stays inside its cell. Applies to the Navamsa chart too.
- **Dasha strip shows all 9 mahadashas.** The Vimshottari timeline was truncated
  to 6 cells; it now wraps onto multiple rows (`flex-wrap`) with
  `page-break-inside: avoid` on chart and strip containers.
- **Vimshottari birth-balance antardashas are correct.** The first (balance)
  mahadasha now shows the sub-period actually running at birth (clamped to the
  birth date), instead of restarting a full lord/lord cycle compressed into the
  leftover balance.
- **ReportLab renderer escapes free text.** Place / DOB / TOB are XML-escaped
  before reaching a ReportLab `Paragraph`, so a value containing `<` or `&` no
  longer raises a parse error. Brings it to parity with the HTML renderer.
- **`parse_birth_details` normalizes 12-hour times.** `9:30 PM` becomes `21:30`;
  the calculators only accept 24-hour times, so this avoids a downstream crash or
  a silent 12-hour error.
- **HTML renderer now embeds the bundled Devanagari font** via an `@font-face`
  base64 data URI. Previously it relied on a system-installed font, so on a
  machine without one (e.g. a fresh server) Chromium rendered Hindi as empty
  "tofu" boxes. Embedding the font also gives correct maatra/conjunct shaping.
- **North-Indian chart planets now stack one per line** inside each house cell
  instead of a single comma-joined line that ran across the chart, so crowded
  houses (e.g. a 4-planet stellium) stay inside their box. Applies to both the
  Lagna and Navamsa charts.
- The HTML renderer reached **parity with the reportlab renderer**: Navamsa D9
  chart, full Devanagari (yoga/karana/system/dasha), DMS degrees, and HH:MM
  sunrise/sunset.
- **`reportlab` is now treated as a truly optional dependency.** The MCP tools
  module imported `pdf_report` (and therefore `reportlab`) at load time, so a
  missing `reportlab` crashed the entire MCP server and broke test collection
  for five unrelated test files. The import is now deferred to the PDF tool, so
  only generating a reportlab PDF requires the package.
