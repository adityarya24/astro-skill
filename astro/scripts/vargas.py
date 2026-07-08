#!/usr/bin/env python
"""Divisional charts (vargas) beyond D1/D9.

Each varga maps a sidereal longitude to a divisional sign by its classical rule.
Odd signs are the 1-based odd rashis (Aries, Gemini, ... = 0-based even indices).
D9 (Navamsa) is produced separately by the kundali calculator.
"""
from __future__ import annotations

SIMHA, KARKA = 4, 3  # Leo, Cancer — the only two D2 (Hora) signs


def _is_odd_sign(sign_idx: int) -> bool:
    return sign_idx % 2 == 0  # Aries (index 0) is the 1st, i.e. odd, sign.


def _hora(sign_idx: int, deg: float) -> int:  # D2, halves of 15°
    first_half = deg < 15
    if _is_odd_sign(sign_idx):
        return SIMHA if first_half else KARKA
    return KARKA if first_half else SIMHA


def _drekkana(sign_idx: int, deg: float) -> int:  # D3, thirds of 10° -> 1st/5th/9th
    return (sign_idx + int(deg // 10) * 4) % 12


def _saptamsa(sign_idx: int, deg: float) -> int:  # D7, sevenths
    start = sign_idx if _is_odd_sign(sign_idx) else (sign_idx + 6) % 12
    return (start + int(deg // (30.0 / 7.0))) % 12


def _dasamsa(sign_idx: int, deg: float) -> int:  # D10, tenths of 3°
    start = sign_idx if _is_odd_sign(sign_idx) else (sign_idx + 8) % 12
    return (start + int(deg // 3.0)) % 12


def _dwadasamsa(sign_idx: int, deg: float) -> int:  # D12, twelfths of 2.5°
    return (sign_idx + int(deg // 2.5)) % 12


VARGA_RULES = {
    "D2": _hora,
    "D3": _drekkana,
    "D7": _saptamsa,
    "D10": _dasamsa,
    "D12": _dwadasamsa,
}


def varga_sign_index(longitude: float, varga: str) -> int:
    lon = longitude % 360.0
    sign_idx = int(lon // 30)
    deg = lon % 30.0
    return VARGA_RULES[varga](sign_idx, deg)


def compute_divisional_charts(longitudes: dict, signs: list[dict]) -> dict:
    """Map each body (planets + Lagna) to its sign in every supported varga.

    ``longitudes`` maps body name -> sidereal longitude; ``signs`` is the
    index-ordered sign list from ``graha_data.json``.
    """
    return {
        varga: {name: signs[varga_sign_index(lon, varga)]["name"] for name, lon in longitudes.items()}
        for varga in VARGA_RULES
    }
