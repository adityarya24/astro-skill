#!/usr/bin/env python
"""Antardasha-window gochar narrative (T6).

Samples slow-planet transits (Saturn, Jupiter, Rahu) across the *current*
Vimshottari antardasha window and emits bilingual one-liners grounded in
classical house-from-Moon gochar. Purely rule-based — no network / LLM —
so tests stay deterministic. A compact fact-sheet is included so a later
synthesis layer can optionally rewrite the prose without re-deriving positions.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from .gochar_calculator import calculate_gochar
    from .kundali_calculator import DATA_DIR, load_json
except ImportError:  # pragma: no cover - direct script execution path.
    SCRIPT_DIR = Path(__file__).resolve().parent
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    from gochar_calculator import calculate_gochar  # noqa: E402
    from kundali_calculator import DATA_DIR, load_json  # noqa: E402

# Slow grahas that dominate a multi-month antardasha narrative.
DEFAULT_TRACKED = ("Shani", "Guru", "Rahu")

# Windows longer than this many days switch from monthly → quarterly sampling
# so a multi-year antardasha does not explode the report.
_QUARTERLY_AFTER_DAYS = 550  # ~18 months
_MAX_SAMPLES = 24


def _parse_dasha_date(value: str) -> date:
    """Parse ``DD/MM/YYYY`` dasha boundary strings."""
    return datetime.strptime(value, "%d/%m/%Y").date()


def _iso(d: date) -> str:
    return d.isoformat()


def load_narrative_data() -> dict:
    return load_json(DATA_DIR / "gochar_narrative_data.json")


def find_antardasha_window(dasha: dict, on_date: date | None = None) -> dict | None:
    """Return the running mahadasha/antardasha span that contains ``on_date``.

    Uses the full timeline (not only ``current``) so start *and* end of the
    antardasha are available for sampling. Returns ``None`` when dasha data is
    incomplete or the date falls outside every period.
    """
    if not dasha:
        return None
    if on_date is None:
        on_date = date.today()

    current = dasha.get("current") or {}
    timeline = dasha.get("timeline") or []

    # Prefer timeline lookup so we get authentic start/end.
    for maha in timeline:
        try:
            m_start = _parse_dasha_date(maha["start"])
            m_end = _parse_dasha_date(maha["end"])
        except (KeyError, ValueError):
            continue
        if not (m_start <= on_date < m_end):
            continue
        for antar in maha.get("antardasha") or []:
            try:
                a_start = _parse_dasha_date(antar["start"])
                a_end = _parse_dasha_date(antar["end"])
            except (KeyError, ValueError):
                continue
            if a_start <= on_date < a_end:
                return {
                    "mahadasha": maha["mahadasha"],
                    "antardasha": antar["planet"],
                    "start": a_start,
                    "end": a_end,
                    "start_iso": _iso(a_start),
                    "end_iso": _iso(a_end),
                }

    # Fallback: only end dates on ``current`` — cannot sample a full window.
    if current.get("mahadasha") and current.get("antardasha") and current.get("antardasha_end"):
        try:
            end = _parse_dasha_date(current["antardasha_end"])
        except ValueError:
            return None
        # Unknown start — sample from on_date only if still inside.
        if on_date < end:
            return {
                "mahadasha": current["mahadasha"],
                "antardasha": current["antardasha"],
                "start": on_date,
                "end": end,
                "start_iso": _iso(on_date),
                "end_iso": _iso(end),
                "start_estimated": True,
            }
    return None


def _month_starts(start: date, end: date) -> list[date]:
    """First-of-month sample dates in ``[start, end)``, plus ``start`` if needed."""
    if end <= start:
        return [start]
    samples: list[date] = []
    # Always include the window open.
    samples.append(start)
    cursor = date(start.year, start.month, 1)
    # advance to next month boundary after start
    if cursor.month == 12:
        cursor = date(cursor.year + 1, 1, 1)
    else:
        cursor = date(cursor.year, cursor.month + 1, 1)
    while cursor < end:
        samples.append(cursor)
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return samples


def _quarter_starts(start: date, end: date) -> list[date]:
    """Approx quarterly samples (every 3 month-starts) plus window open."""
    monthly = _month_starts(start, end)
    if not monthly:
        return [start]
    picked = [monthly[0]]
    for d in monthly[1:]:
        if (d.year - picked[-1].year) * 12 + (d.month - picked[-1].month) >= 3:
            picked.append(d)
    return picked


def sample_dates_for_window(start: date, end: date) -> tuple[str, list[date]]:
    """Choose monthly vs quarterly cadence and return ``(cadence, dates)``."""
    span_days = (end - start).days
    if span_days >= _QUARTERLY_AFTER_DAYS:
        dates = _quarter_starts(start, end)
        cadence = "quarterly"
    else:
        dates = _month_starts(start, end)
        cadence = "monthly"
    if len(dates) > _MAX_SAMPLES:
        # Evenly thin while keeping first and last.
        step = max(1, (len(dates) - 1) // (_MAX_SAMPLES - 1))
        thinned = dates[::step]
        if thinned[-1] != dates[-1]:
            thinned.append(dates[-1])
        dates = thinned[:_MAX_SAMPLES]
    return cadence, dates


def _line_for(
    data: dict,
    planet: str,
    house: int,
    *,
    retrograde: bool,
    language: str,
) -> str:
    hi = language in {"hi", "hin"}
    lang_key = "hi" if hi else "en"
    block = (data.get("house_lines") or {}).get(planet) or {}
    entry = block.get(str(house)) or {}
    base = entry.get(lang_key) or entry.get("en") or (f"{planet} transit house {house} from Moon.")
    if retrograde:
        suffix = (data.get("retro_suffix") or {}).get(lang_key) or ""
        base = base + suffix
    return base


def _saturn_window_note(saturn_analysis: dict, data: dict, language: str) -> str:
    hi = language in {"hi", "hin"}
    lang_key = "hi" if hi else "en"
    status = (saturn_analysis or {}).get("status") or "none"
    lines = data.get("saturn_status_lines") or {}
    template = (lines.get(status) or lines.get("none") or {}).get(lang_key) or ""
    labels = data.get("phase_labels") or {}
    if status == "sade_sati":
        phase = (saturn_analysis or {}).get("phase") or ""
        phase_l = (labels.get(phase) or {}).get(lang_key) or phase
        return template.format(phase=phase_l)
    if status == "dhaiya":
        t = (saturn_analysis or {}).get("type") or ""
        type_l = (labels.get(t) or {}).get(lang_key) or t
        return template.format(type=type_l)
    return template


def _highlight(
    planet: str,
    transit: dict,
    data: dict,
    language: str,
) -> dict:
    house = int(transit.get("house_from_moon") or 0)
    retro = bool(transit.get("retrograde"))
    return {
        "planet": planet,
        "sign": transit.get("sign"),
        "degree": transit.get("degree"),
        "house_from_moon": house,
        "house_from_lagna": transit.get("house_from_lagna"),
        "retrograde": retro,
        "line": _line_for(data, planet, house, retrograde=retro, language=language),
        "line_en": _line_for(data, planet, house, retrograde=retro, language="en"),
        "line_hi": _line_for(data, planet, house, retrograde=retro, language="hi"),
    }


def build_antardasha_gochar_narrative(
    kundali: dict,
    dasha: dict,
    *,
    on_date: date | None = None,
    language: str = "en",
    planets: tuple[str, ...] | list[str] | None = None,
) -> dict | None:
    """Build monthly/quarterly gochar one-liners for the current antardasha.

    Returns ``None`` when the antardasha window cannot be resolved. Never
    calls an LLM; ``synthesis_facts`` is a compact chart of sample points for
    optional downstream prose generation.
    """
    if on_date is None:
        on_date = date.today()
    window = find_antardasha_window(dasha, on_date)
    if window is None:
        return None

    data = load_narrative_data()
    tracked = list(planets) if planets else list(data.get("planets_tracked") or DEFAULT_TRACKED)
    cadence, dates = sample_dates_for_window(window["start"], window["end"])

    samples: list[dict] = []
    for d in dates:
        gochar = calculate_gochar(kundali, on_date=d)
        transits = gochar.get("transits") or {}
        highlights = []
        for planet in tracked:
            t = transits.get(planet)
            if not t:
                continue
            highlights.append(_highlight(planet, t, data, language))
        samples.append(
            {
                "date": _iso(d),
                "cadence": cadence,
                "highlights": highlights,
                "saturn_analysis": gochar.get("saturn_analysis"),
            }
        )

    # Mid-window Saturn note (stable theme for the whole span).
    mid = window["start"] + timedelta(days=max(0, (window["end"] - window["start"]).days // 2))
    if mid >= window["end"]:
        mid = window["start"]
    mid_gochar = calculate_gochar(kundali, on_date=mid)
    saturn_note = _saturn_window_note(mid_gochar.get("saturn_analysis") or {}, data, language)

    hi = language in {"hi", "hin"}
    lang_key = "hi" if hi else "en"
    cadence_label = ((data.get("cadence_labels") or {}).get(cadence) or {}).get(lang_key) or cadence
    summary_tmpl = (data.get("summary_template") or {}).get(lang_key) or ""
    summary = summary_tmpl.format(
        md=window["mahadasha"],
        ad=window["antardasha"],
        start=window["start_iso"],
        end=window["end_iso"],
        cadence=cadence_label,
        n=len(samples),
        saturn_note=saturn_note,
    )

    # Fact-sheet for optional LLM rewrite (T3 hook) — positions only, no prose.
    synthesis_facts = {
        "window": {
            "mahadasha": window["mahadasha"],
            "antardasha": window["antardasha"],
            "start": window["start_iso"],
            "end": window["end_iso"],
        },
        "cadence": cadence,
        "points": [
            {
                "date": s["date"],
                "planets": {
                    h["planet"]: {
                        "sign": h["sign"],
                        "house_from_moon": h["house_from_moon"],
                        "retrograde": h["retrograde"],
                    }
                    for h in s["highlights"]
                },
                "saturn_status": (s.get("saturn_analysis") or {}).get("status"),
            }
            for s in samples
        ],
        "mid_saturn": mid_gochar.get("saturn_analysis"),
    }

    return {
        "language": language,
        "window": {
            "mahadasha": window["mahadasha"],
            "antardasha": window["antardasha"],
            "start": window["start_iso"],
            "end": window["end_iso"],
            "start_estimated": bool(window.get("start_estimated")),
        },
        "cadence": cadence,
        "sample_count": len(samples),
        "samples": samples,
        "summary": summary,
        "summary_en": _summary_for_lang(
            data, window, cadence, len(samples), mid_gochar.get("saturn_analysis") or {}, "en"
        ),
        "summary_hi": _summary_for_lang(
            data, window, cadence, len(samples), mid_gochar.get("saturn_analysis") or {}, "hi"
        ),
        "synthesis_facts": synthesis_facts,
    }


def _summary_for_lang(
    data: dict,
    window: dict,
    cadence: str,
    n: int,
    saturn_analysis: dict,
    lang: str,
) -> str:
    lang_key = "hi" if lang in {"hi", "hin"} else "en"
    cadence_label = ((data.get("cadence_labels") or {}).get(cadence) or {}).get(lang_key) or cadence
    saturn_note = _saturn_window_note(saturn_analysis, data, lang)
    tmpl = (data.get("summary_template") or {}).get(lang_key) or ""
    return tmpl.format(
        md=window["mahadasha"],
        ad=window["antardasha"],
        start=window["start_iso"],
        end=window["end_iso"],
        cadence=cadence_label,
        n=n,
        saturn_note=saturn_note,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gochar one-liners for the current Vimshottari antardasha window."
    )
    parser.add_argument("--kundali-json", required=True, help="Path to kundali JSON")
    parser.add_argument("--dasha-json", required=True, help="Path to dasha JSON (with timeline)")
    parser.add_argument("--date", help="Reference date YYYY-MM-DD (default: today)")
    parser.add_argument("--language", choices=["hin", "hi", "en"], default="en")
    parser.add_argument("--json", action="store_true", help="Print full JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    kundali = load_json(Path(args.kundali_json))
    dasha = load_json(Path(args.dasha_json))
    on_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None
    result = build_antardasha_gochar_narrative(
        kundali, dasha, on_date=on_date, language=args.language
    )
    if result is None:
        print("No antardasha window resolved for the given dasha/date.", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["summary"])
        for sample in result["samples"]:
            print(f"\n{sample['date']}:")
            for h in sample["highlights"]:
                print(f"  {h['planet']}: {h['line']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
