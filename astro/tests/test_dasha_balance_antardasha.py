"""Regression tests for antardashas inside the birth (balance) mahadasha.

These exercise the Vimshottari maths in isolation with a synthetic dasha seed,
so they need no Swiss Ephemeris — only ``dasha_calculator`` and its data file.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from dasha_calculator import calculate_dasha  # noqa: E402


def _venus_balance_chart(balance_years: float) -> dict:
    """Synthetic chart born partway through a Venus (Shukra) mahadasha.

    ``calculate_dasha`` only consumes ``dasha_seed`` and the birth datetime, so
    this pins down the timeline without an ephemeris.
    """
    return {
        "calculation": {"datetime_local": "2019-12-26T09:15:00+05:30"},
        "dasha_seed": {
            "nakshatra": "Bharani",
            "nakshatra_lord": "Shukra",
            "balance_years_decimal": balance_years,
            "balance_at_birth": {"years": int(balance_years), "months": 0, "days": 0},
        },
    }


def test_first_antardasha_at_birth_is_the_running_one_not_the_lord():
    # Venus full mahadasha = 20y; balance 16.36y => born 3.64y into it.
    # Venus/Venus antardasha = 20*20/120 = 3.333y, already over at birth,
    # so the sub-period running at birth is Venus/Sun (Shukra/Surya).
    dasha = calculate_dasha(_venus_balance_chart(16.36), on_date=date(2020, 1, 1))
    first_maha = dasha["timeline"][0]

    assert first_maha["mahadasha"] == "Shukra"
    assert first_maha["antardasha"][0]["planet"] == "Surya"
    assert first_maha["antardasha"][0]["start"] == "26/12/2019"  # clipped to birth


def test_birth_antardasha_is_reported_as_current_at_birth():
    dasha = calculate_dasha(_venus_balance_chart(16.36), on_date=date(2019, 12, 27))

    assert dasha["current"]["mahadasha"] == "Shukra"
    assert dasha["current"]["antardasha"] == "Surya"


def test_full_mahadasha_still_starts_with_its_own_lord():
    # A later, full mahadasha is unaffected: first antardasha is lord/lord.
    dasha = calculate_dasha(_venus_balance_chart(16.36))
    second = dasha["timeline"][1]

    assert second["mahadasha"] == "Surya"
    assert second["antardasha"][0]["planet"] == "Surya"
    assert len(second["antardasha"]) == 9


def test_balance_close_to_full_keeps_lord_first_antardasha():
    # Born essentially at nakshatra start: elapsed ~0, so Venus/Venus is the
    # running sub-period and nothing is dropped.
    dasha = calculate_dasha(_venus_balance_chart(19.999))
    first_maha = dasha["timeline"][0]

    assert first_maha["antardasha"][0]["planet"] == "Shukra"
    assert len(first_maha["antardasha"]) == 9


def test_balance_mahadasha_antardashas_are_bounded_and_ordered():
    dasha = calculate_dasha(_venus_balance_chart(16.36))
    first_maha = dasha["timeline"][0]

    assert first_maha["antardasha"][-1]["end"] == first_maha["end"]
    for antar in first_maha["antardasha"]:
        start = date.fromisoformat("-".join(reversed(antar["start"].split("/"))))
        end = date.fromisoformat("-".join(reversed(antar["end"].split("/"))))
        maha_end = date.fromisoformat("-".join(reversed(first_maha["end"].split("/"))))
        assert start < end
        assert end <= maha_end
