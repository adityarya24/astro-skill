---
name: astro
description: Vedic astrology calculation skill for kundali, dasha, panchang, gochar transits, guna milan, structured report JSON, and Hindi PDF reports. Use when an agent needs deterministic astrology from birth details, date, time, and location.
---

# Astro Skill

Use this skill to calculate and explain Vedic astrology outputs. Keep responses practical, respectful, and grounded in computed data. Do not predict death, accidents, medical diagnoses, or unavoidable harm.

## Defaults

- Ayanamsa: Lahiri Chitrapaksha.
- House system: whole sign.
- Default language: Hinglish (`hin`), with Hindi (`hi`) and English (`en`) supported by callers.
- Default location for non-birth daily work: Delhi, India.

## Required Inputs

- Kundali: date of birth, time of birth, place, latitude, longitude, timezone.
- Dasha: kundali output from `kundali_calculator.py`.
- Panchang: local date, place, latitude, longitude, timezone.
- Basic report: kundali JSON, with optional dasha JSON and panchang JSON.
- PDF report: kundali JSON plus optional dasha and panchang JSON; dasha is recommended for the timeline chart.
- Gochar (transits): kundali JSON plus a local calendar date (and optional place for location-sensitive work).
- Guna Milan: two complete kundali JSON files (both people need full birth details).
- Muhurta and other advanced modules may require purpose plus date range when implemented.

## Phase 1 Workflow

1. Run `scripts/kundali_calculator.py` with birth details and `--json`.
2. Inspect `lagna`, `rashi`, `nakshatra`, `nakshatra_pada`, `planets`, `houses`, and `dasha_seed`.
3. Run `scripts/dasha_calculator.py --kundali-json <path> --json` when dasha timing is needed.
4. Explain the output in the user's preferred language/tone. Mention calculations and practical meaning; avoid mystical filler.

## Phase 2 Workflow

1. Run `scripts/panchang_calculator.py` with local date, place, latitude, longitude, timezone, and `--json`.
2. Inspect `vara`, `tithi`, `paksha`, `nakshatra`, `yoga`, `karana`, `sunrise`, and `sunset`.
3. Use the Panchang output as calculation data for daily guidance or later muhurta work. Do not convert it into muhurta recommendations unless a muhurta module is available.
4. If sunrise or sunset is `null`, check the `warnings` array and explain that the rest of the Panchang fields still came from computed solar/lunar positions.

## Tier 2 Workflow (Gochar & Guna Milan)

Use these after Phase 1 kundali JSON exists. Outputs are calculation-backed; keep interpretation conservative and avoid certainty claims.

### Gochar (transit snapshot)

1. Run `scripts/kundali_calculator.py` for the native chart and save `--json` output.
2. Run `scripts/gochar_calculator.py --kundali-json <chart.json> --date YYYY-MM-DD --json`.
3. Explain which grahas are transiting which rashis/houses relative to the natal lagna. Mention retrograde flags when present.
4. Do not treat gochar as fate prediction; frame as timing context for operator review.

### Guna Milan (Ashtakoot compatibility score)

1. Build kundali JSON for person A and person B (full DOB, TOB, place, lat, lon, timezone).
2. Run `scripts/guna_milan.py --kundali-a-json <a.json> --kundali-b-json <b.json> --json`.
3. Present the scored breakdown (guna table, total, dosha flags) from JSON only.
4. Compatibility scores are heuristic drafts, not relationship verdicts. An astrologer remains the final authority.

## Phase 3 Workflow

1. Generate or load kundali JSON. Optionally generate dasha JSON and daily panchang JSON.
2. Run `scripts/report_generator.py --kundali-json <chart.json> --dasha-json <dasha.json> --panchang-json <panchang.json> --json`.
3. Use the structured report as an astrologer/operator draft: birth chart facts, current dasha, daily Panchang, and safety notes.
4. Keep interpretation clearly separated from calculation. The reviewing astrologer or operator remains the final authority.

## Phase 4 Workflow

1. Generate or load kundali JSON. Generate dasha JSON when the PDF should include a dasha timeline chart.
2. Run `scripts/pdf_report.py --kundali-json <chart.json> --dasha-json <dasha.json> --panchang-json <panchang.json> --output output/pdf/<name>.pdf --renderer html`.
   The default `--renderer html` uses Chromium via Playwright and is the
   preferred path for Hindi/Devanagari polish. Use `--renderer reportlab` to
   fall back to the legacy in-process renderer (lower-quality maatra
   shaping, but no browser dependency).
3. Install the browser once with `python -m playwright install chromium` if
   the HTML renderer reports it is missing.
4. Check the PDF text or rendered pages before sharing. The PDF includes a planet/house chart, planet table, dasha timeline, Panchang section, and safety notes when those inputs are present.
5. Keep PDF content calculation-first. Treat it as a formatted working draft for astrologer/operator review.

## Command Examples

```bash
python scripts/kundali_calculator.py --dob 26/12/2019 --tob 09:15 --place Delhi --lat 28.6139 --lon 77.2090 --timezone Asia/Kolkata --json
python scripts/dasha_calculator.py --kundali-json chart.json --json
python scripts/gochar_calculator.py --kundali-json chart.json --date 2026-07-01 --json
python scripts/guna_milan.py --kundali-a-json bride.json --kundali-b-json groom.json --json
python scripts/panchang_calculator.py --date 2026-05-21 --place Delhi --lat 28.6139 --lon 77.209 --timezone Asia/Kolkata --json
python scripts/report_generator.py --kundali-json chart.json --dasha-json dasha.json --panchang-json panchang.json --json
python scripts/pdf_report.py --kundali-json chart.json --dasha-json dasha.json --panchang-json panchang.json --output output/pdf/report.pdf
```

## Dependency Handling

The calculator requires `pyswisseph` for Swiss Ephemeris. If it is missing, install the project dependencies or install `pyswisseph` directly. Do not silently approximate kundali positions without an ephemeris.

PDF generation supports two renderers:

- `html` (default, preferred) — uses `playwright` + a Chromium binary for
  print-CSS-styled output with proper Devanagari shaping. Install the
  browser once with `python -m playwright install chromium`. If Chromium is
  missing the renderer raises a clear `RuntimeError` with the install
  command.
- `reportlab` (fallback) — uses `reportlab` in-process. No browser needed,
  but Devanagari maatras are not perfectly shaped.

PDF test extraction uses `pypdf` in the development environment.
