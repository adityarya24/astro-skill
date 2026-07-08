"""parse_birth_details must emit a 24-hour time the calculators can consume.

A 12-hour ``9:30 PM`` in an operator note has to become ``21:30`` — otherwise it
either crashes ``kundali_calculator.parse_time`` or, if the meridiem is dropped,
silently reads as 09:30 and shifts the whole chart by 12 hours.

Imports only the pure regex tool, so no Swiss Ephemeris is required.
"""
from __future__ import annotations

import re

import pytest

from services.astro_mcp.tools import parse_birth_details_tool

# Mirror of kundali_calculator.parse_time's accepted shape (24h HH:MM[:SS]).
_TWENTY_FOUR_HOUR = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$")


@pytest.mark.parametrize(
    "note, expected",
    [
        ("DOB 26/12/2019 at 9:30 PM place Delhi", "21:30"),
        ("born 12:30 AM", "00:30"),
        ("time 12:00 PM", "12:00"),
        ("time 12:00 am", "00:00"),
        ("TOB 09:15", "09:15"),
        ("at 7:05 am", "07:05"),
    ],
)
def test_time_is_normalised_to_24_hour(note: str, expected: str):
    assert parse_birth_details_tool(note)["tob"] == expected


@pytest.mark.parametrize(
    "note",
    [
        "DOB 26/12/2019 at 9:30 PM",
        "born 12:30 AM in Delhi",
        "time 7:05 am",
    ],
)
def test_normalised_time_is_accepted_by_the_calculator_grammar(note: str):
    tob = parse_birth_details_tool(note)["tob"]
    assert _TWENTY_FOUR_HOUR.match(tob), f"{tob!r} is not a 24-hour time"


@pytest.mark.parametrize(
    "note, expected",
    [
        ("born 26th December 2019 at 9:30 PM", "26/12/2019"),
        ("DOB 3 Jan 2000", "03/01/2000"),
        ("15 August 1975 in Delhi", "15/08/1975"),
        ("date of birth 26/12/2019", "26/12/2019"),  # numeric still wins
    ],
)
def test_natural_language_dates_are_normalised(note: str, expected: str):
    assert parse_birth_details_tool(note)["dob"] == expected


@pytest.mark.parametrize(
    "note, expected",
    [
        ("born in Delhi IST", "Asia/Kolkata"),
        ("tz Asia/Kolkata", "Asia/Kolkata"),  # IANA name still wins
        ("America/New_York", "America/New_York"),
    ],
)
def test_timezone_abbreviations_resolve(note: str, expected: str):
    assert parse_birth_details_tool(note)["timezone_name"] == expected
