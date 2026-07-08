from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from dasha_calculator import calculate_dasha  # noqa: E402
from kundali_calculator import BirthInput, calculate_kundali  # noqa: E402


# Neutral sample birth (26/12/2019 09:15 IST, Delhi): Moon in Mula pada 3, so
# the native is born partway through the Ketu mahadasha with ~2.18y balance.
# Cross-checked against DrikPanchang (Mula upto 16:51 on 26 Dec 2019, Delhi)
# and an independent Swiss Ephemeris computation.
def reference_chart() -> dict:
    return calculate_kundali(
        BirthInput(
            dob="26/12/2019",
            tob="09:15",
            place="Delhi",
            lat=28.6139,
            lon=77.2090,
            timezone_name="Asia/Kolkata",
        )
    )


def test_vimshottari_timeline_starts_from_birth_balance():
    chart = reference_chart()
    dasha = calculate_dasha(chart, on_date=date(2026, 5, 20))

    assert dasha["system"] == "Vimshottari"
    assert dasha["seed_nakshatra"] == "Mula"
    assert dasha["seed_lord"] == "Ketu"
    assert len(dasha["timeline"]) == 9
    assert dasha["timeline"][0]["mahadasha"] == "Ketu"
    assert dasha["timeline"][0]["duration_years"] == chart["dasha_seed"]["balance_years_decimal"]
    # The native enters the first mahadasha partway through, so it carries only
    # the antardashas still running/remaining at birth. Every later mahadasha is
    # entered from its start and therefore carries the full cycle of 9.
    assert all(len(maha["antardasha"]) == 9 for maha in dasha["timeline"][1:])
    assert 0 < len(dasha["timeline"][0]["antardasha"]) <= 9


def test_current_dasha_is_identified_for_reference_date():
    dasha = calculate_dasha(reference_chart(), on_date=date(2026, 5, 20))

    # 2026-05-20 falls in Shukra mahadasha (from 02/03/2022), Surya antardasha
    # (02/07/2025 – 02/07/2026) — derived independently from the Vimshottari
    # arithmetic for the ~2.18y Ketu balance.
    assert dasha["current"] is not None
    assert dasha["current"]["mahadasha"] == "Shukra"
    assert dasha["current"]["antardasha"] == "Surya"


def test_birth_balance_starts_in_the_running_antardasha():
    """At birth the native is partway through the first mahadasha.

    Ketu's full mahadasha is 7y but only ~2.18y remain, so ~4.82y have already
    elapsed. That places birth inside the *Guru* antardasha of Ketu — the six
    earlier sub-periods (Ketu, Shukra, Surya, Chandra, Mangal, Rahu) finished
    before birth. The classical result is that the first antardasha shown is
    Guru, clamped to the birth date — not a fresh Ketu-Ketu sub-period.
    """
    dasha = calculate_dasha(reference_chart(), on_date=date(2026, 5, 20))
    first_antardasha = dasha["timeline"][0]["antardasha"][0]

    assert first_antardasha["planet"] == "Guru"
    assert first_antardasha["start"] == "26/12/2019"  # clamped to the birth date
    assert all(a["planet"] != "Ketu" for a in dasha["timeline"][0]["antardasha"])


def test_birth_balance_antardashas_stay_inside_first_mahadasha():
    dasha = calculate_dasha(reference_chart(), on_date=date(2026, 5, 20))
    first_mahadasha = dasha["timeline"][0]

    assert first_mahadasha["mahadasha"] == "Ketu"
    assert first_mahadasha["end"] == "02/03/2022"
    assert first_mahadasha["antardasha"][-1]["end"] == first_mahadasha["end"]

    for antardasha in first_mahadasha["antardasha"]:
        start = date.fromisoformat("-".join(reversed(antardasha["start"].split("/"))))
        end = date.fromisoformat("-".join(reversed(antardasha["end"].split("/"))))
        mahadasha_end = date.fromisoformat("-".join(reversed(first_mahadasha["end"].split("/"))))

        assert start < end
        assert end <= mahadasha_end


def test_dasha_cli_outputs_json(tmp_path: Path):
    chart_path = tmp_path / "chart.json"
    chart_path.write_text(json.dumps(reference_chart()), encoding="utf-8")
    script = SCRIPT_DIR / "dasha_calculator.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--kundali-json",
            str(chart_path),
            "--date",
            "2026-05-20",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    dasha = json.loads(completed.stdout)
    assert dasha["current"]["mahadasha"] == "Shukra"
    assert dasha["current"]["antardasha"] == "Surya"
