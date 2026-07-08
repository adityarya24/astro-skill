#!/usr/bin/env python
"""Calculate Vimshottari mahadasha and antardasha timelines from kundali JSON."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

DAYS_PER_YEAR = 365.2425


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def format_date(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y")


def add_years(dt: datetime, years: float) -> datetime:
    return dt + timedelta(days=years * DAYS_PER_YEAR)


def ordered_from(order: list[str], start: str) -> list[str]:
    index = order.index(start)
    return order[index:] + order[:index]


def antardasha_for(
    maha_start: datetime,
    maha_full_years: float,
    mahadasha_lord: str,
    order: list[str],
    years: dict,
    clamp_start: datetime | None = None,
) -> list[dict]:
    """Antardashas across a *full* mahadasha, in classical proportions.

    Antardasha lengths are always a fraction (``years[lord] / 120``) of the
    mahadasha's **full** length, never of a shortened span. For the birth-balance
    mahadasha the native is already partway through it, so ``clamp_start`` (the
    birth instant) drops antardashas that finished before birth and clips the
    running antardasha to begin at birth. This keeps every antardasha boundary on
    its true date instead of compressing a whole cycle into the leftover balance.
    """
    maha_end = add_years(maha_start, maha_full_years)
    cursor = maha_start
    rows: list[dict] = []
    for lord in ordered_from(order, mahadasha_lord):
        row_start = cursor
        row_end = add_years(row_start, maha_full_years * years[lord] / 120.0)
        cursor = row_end
        if clamp_start is not None and row_end <= clamp_start:
            continue  # antardasha already elapsed before birth
        display_start = (
            clamp_start
            if clamp_start is not None and row_start < clamp_start
            else row_start
        )
        rows.append(
            {"planet": lord, "start": format_date(display_start), "end": format_date(row_end)}
        )
    if rows:
        rows[-1]["end"] = format_date(maha_end)  # absorb rounding at the boundary
    return rows


def _running_row(rows: list[dict], on_date: date) -> dict | None:
    for row in rows:
        start = datetime.strptime(row["start"], "%d/%m/%Y").date()
        end = datetime.strptime(row["end"], "%d/%m/%Y").date()
        if start <= on_date < end:
            return row
    return None


def find_current(timeline: list[dict], on_date: date, order: list[str], years: dict) -> dict | None:
    for maha in timeline:
        m_start = datetime.strptime(maha["start"], "%d/%m/%Y").date()
        m_end = datetime.strptime(maha["end"], "%d/%m/%Y").date()
        if not (m_start <= on_date < m_end):
            continue
        current = {
            "mahadasha": maha["mahadasha"],
            "mahadasha_end": maha["end"],
            "antardasha": None,
            "antardasha_end": None,
            "pratyantardasha": None,
            "pratyantardasha_end": None,
        }
        antar = _running_row(maha["antardasha"], on_date)
        if antar is not None:
            current["antardasha"] = antar["planet"]
            current["antardasha_end"] = antar["end"]
            # Pratyantardasha: subdivide the antardasha by the same proportions.
            # A full antardasha's length is maha_full * years[antar] / 120.
            antar_full = years[maha["mahadasha"]] * years[antar["planet"]] / 120.0
            antar_start = datetime.strptime(antar["start"], "%d/%m/%Y")
            pratyantars = antardasha_for(antar_start, antar_full, antar["planet"], order, years)
            praty = _running_row(pratyantars, on_date)
            if praty is not None:
                current["pratyantardasha"] = praty["planet"]
                current["pratyantardasha_end"] = praty["end"]
        return current
    return None


def calculate_dasha(kundali: dict, on_date: date | None = None) -> dict:
    graha_data = load_json(DATA_DIR / "graha_data.json")
    order = graha_data["vimshottari_order"]
    years = {planet: data["vimshottari_years"] for planet, data in graha_data["planets"].items()}

    seed = kundali["dasha_seed"]
    seed_lord = seed["nakshatra_lord"]
    balance_years = float(seed["balance_years_decimal"])
    birth_dt = parse_iso_datetime(kundali["calculation"]["datetime_local"])

    timeline = []
    cursor = birth_dt
    first_end = add_years(cursor, balance_years)
    lord_order = ordered_from(order, seed_lord)
    for index, lord in enumerate(lord_order):
        start = cursor
        full_years = float(years[lord])
        if index == 0:
            # The native enters the first mahadasha partway through (only the
            # balance remains). Reconstruct the full mahadasha span so antardashas
            # fall on their true classical boundaries, then clamp to birth.
            maha_full_start = add_years(start, balance_years - full_years)
            end = first_end
            antardasha = antardasha_for(
                maha_full_start, full_years, lord, order, years, clamp_start=start
            )
            duration = balance_years
        else:
            end = add_years(start, full_years)
            antardasha = antardasha_for(start, full_years, lord, order, years)
            duration = full_years
        timeline.append(
            {
                "mahadasha": lord,
                "start": format_date(start),
                "end": format_date(end),
                "duration_years": round(duration, 8),
                "antardasha": antardasha,
            }
        )
        cursor = end

    if on_date is None:
        on_date = date.today()

    return {
        "system": "Vimshottari",
        "seed_nakshatra": seed["nakshatra"],
        "seed_lord": seed_lord,
        "balance_at_birth": seed["balance_at_birth"],
        "timeline": timeline,
        "current": find_current(timeline, on_date, order, years),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calculate Vimshottari dasha from kundali JSON.")
    parser.add_argument("--kundali-json", required=True, help="Path to kundali JSON file")
    parser.add_argument("--date", help="Current date override: YYYY-MM-DD")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    kundali = load_json(Path(args.kundali_json))
    on_date = date.fromisoformat(args.date) if args.date else None
    result = calculate_dasha(kundali, on_date)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        current = result["current"] or {}
        print(
            f"Seed: {result['seed_lord']} | Current: "
            f"{current.get('mahadasha', '-')}/{current.get('antardasha', '-')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
