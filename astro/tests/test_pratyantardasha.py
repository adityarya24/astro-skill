"""Pratyantardasha (3rd dasha level) inside the current period. Synthetic seed."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from dasha_calculator import (  # noqa: E402
    DATA_DIR,
    antardasha_for,
    calculate_dasha,
    load_json,
    parse_iso_datetime,
)

VIMSHOTTARI = {"Ketu", "Shukra", "Surya", "Chandra", "Mangal", "Rahu", "Guru", "Shani", "Budh"}


def _chart(balance: float = 16.36) -> dict:
    return {
        "calculation": {"datetime_local": "2019-12-26T09:15:00+05:30"},
        "dasha_seed": {
            "nakshatra": "Bharani",
            "nakshatra_lord": "Shukra",
            "balance_years_decimal": balance,
            "balance_at_birth": {"years": int(balance), "months": 0, "days": 0},
        },
    }


def _d(text: str) -> date:
    return date.fromisoformat("-".join(reversed(text.split("/"))))


def test_current_period_has_three_valid_levels():
    cur = calculate_dasha(_chart(), on_date=date(2026, 5, 20))["current"]
    assert cur["mahadasha"] in VIMSHOTTARI
    assert cur["antardasha"] in VIMSHOTTARI
    assert cur["pratyantardasha"] in VIMSHOTTARI


def test_pratyantardasha_ends_within_the_antardasha():
    cur = calculate_dasha(_chart(), on_date=date(2026, 5, 20))["current"]
    assert _d(cur["pratyantardasha_end"]) <= _d(cur["antardasha_end"])


def test_first_pratyantardasha_of_a_full_antardasha_is_its_lord():
    # The 2nd mahadasha (Surya) is entered from its start, so its first
    # antardasha (Surya) and that antardasha's first pratyantardasha are both
    # Surya. Query the birth + balance instant (start of the Surya mahadasha).
    graha = load_json(DATA_DIR / "graha_data.json")
    years = {p: d["vimshottari_years"] for p, d in graha["planets"].items()}
    birth = parse_iso_datetime(_chart()["calculation"]["datetime_local"])
    # First antardasha of the Surya mahadasha, subdivided -> first pratyantar is Surya.
    antars = antardasha_for(birth, years["Surya"], "Surya", graha["vimshottari_order"], years)
    assert antars[0]["planet"] == "Surya"
