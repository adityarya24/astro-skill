"""Divisional charts (vargas) — rule-based, verifiable by hand. No ephemeris."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from vargas import compute_divisional_charts, varga_sign_index  # noqa: E402

# 5° Aries (sign 0, odd sign, within-sign degree 5).
FIVE_ARIES = 5.0
# 10° Taurus (sign 1, even sign) = 40° absolute.
TEN_TAURUS = 40.0


def test_varga_signs_for_5_aries():
    assert varga_sign_index(FIVE_ARIES, "D2") == 4   # odd sign, 1st half -> Leo
    assert varga_sign_index(FIVE_ARIES, "D3") == 0   # 1st drekkana -> same sign
    assert varga_sign_index(FIVE_ARIES, "D7") == 1   # odd start, 2nd part -> Taurus
    assert varga_sign_index(FIVE_ARIES, "D10") == 1  # odd start, 2nd part -> Taurus
    assert varga_sign_index(FIVE_ARIES, "D12") == 2  # 3rd part -> Gemini


def test_varga_signs_for_10_taurus():
    assert varga_sign_index(TEN_TAURUS, "D2") == 3   # even sign, 1st half -> Cancer
    assert varga_sign_index(TEN_TAURUS, "D3") == 5   # 2nd drekkana -> 5th from Taurus
    assert varga_sign_index(TEN_TAURUS, "D7") == 9   # even start (7th), 3rd part
    assert varga_sign_index(TEN_TAURUS, "D10") == 0  # even start (9th), 4th part -> Aries
    assert varga_sign_index(TEN_TAURUS, "D12") == 5  # 5th part -> Virgo


def test_compute_divisional_charts_structure():
    signs = [{"index": i, "name": n} for i, n in enumerate(
        ["Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
         "Tula", "Vrischika", "Dhanu", "Makara", "Kumbha", "Meena"]
    )]
    longitudes = {"Surya": FIVE_ARIES, "Chandra": TEN_TAURUS, "Lagna": FIVE_ARIES}
    charts = compute_divisional_charts(longitudes, signs)

    assert set(charts) == {"D2", "D3", "D7", "D10", "D12"}
    for varga in charts.values():
        assert set(varga) == {"Surya", "Chandra", "Lagna"}
    assert charts["D10"]["Surya"] == "Vrishabha"   # 5 Aries -> D10 Taurus
    assert charts["D3"]["Chandra"] == "Kanya"       # 10 Taurus -> D3 Virgo
