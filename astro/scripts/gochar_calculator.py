#!/usr/bin/env python
"""Gochar (planetary transits) and the Saturn cycle (Sade Sati / Dhaiya).

Transits are reckoned from the natal Moon sign (classical gochar) and the natal
Lagna. Saturn's position relative to the natal Moon drives Sade Sati (Saturn in
the 12th/1st/2nd from the Moon) and Dhaiya / small panoti (4th or 8th).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import swisseph as swe
except ImportError as exc:  # pragma: no cover - exercised by users without dependency.
    raise SystemExit(
        "Missing dependency: pyswisseph. Install with `python -m pip install pyswisseph`."
    ) from exc

try:
    from .kundali_calculator import (
        DATA_DIR,
        PLANET_IDS,
        calc_body,
        degree_in_sign,
        load_json,
        normalize_lon,
        setup_ayanamsa,
        sign_index,
        sign_name,
    )
    from .swe_lock import serialized
except ImportError:  # pragma: no cover - direct script execution path.
    SCRIPT_DIR = Path(__file__).resolve().parent
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    from kundali_calculator import (  # noqa: E402
        DATA_DIR,
        PLANET_IDS,
        calc_body,
        degree_in_sign,
        load_json,
        normalize_lon,
        setup_ayanamsa,
        sign_index,
        sign_name,
    )
    from swe_lock import serialized  # noqa: E402


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def julian_day_noon_ut(day: date) -> float:
    """Noon UT of the date — stable within the day for slow transit purposes."""
    return swe.julday(day.year, day.month, day.day, 12.0)


def _saturn_lon(jd_ut: float) -> float:
    return calc_body(jd_ut, swe.SATURN)[0]


def _sign_boundary(jd_in_sign: float, target_sign: int, direction: int) -> float:
    """JD where Saturn crosses the edge of ``target_sign`` in ``direction``.

    ``direction`` is +1 (forward, egress) or -1 (backward, ingress). Steps in
    5-day increments until the sign changes, then bisects to the crossing. Uses
    the nearest crossing, which is exact away from a rare retrograde straddle.
    """
    step = 5.0 * direction
    near = jd_in_sign
    far = jd_in_sign + step
    guard = 0
    while sign_index(_saturn_lon(far)) == target_sign and guard < 600:
        near = far
        far += step
        guard += 1
    for _ in range(50):  # bisect the [near(target) .. far(other)] bracket
        mid = (near + far) / 2.0
        if sign_index(_saturn_lon(mid)) == target_sign:
            near = mid
        else:
            far = mid
    return (near + far) / 2.0


def _jd_to_iso_date(jd_ut: float) -> str:
    year, month, day, _ = swe.revjul(jd_ut)
    return f"{year:04d}-{month:02d}-{day:02d}"


def house_from(sign_idx: int, reference_idx: int) -> int:
    return ((sign_idx - reference_idx) % 12) + 1


def _transit_positions(jd_ut: float, signs: list[dict], moon_idx: int, lagna_idx: int) -> dict:
    transits: dict[str, dict] = {}
    for planet, body_id in PLANET_IDS.items():
        lon, speed = calc_body(jd_ut, body_id)
        idx = sign_index(lon)
        transits[planet] = {
            "sign": signs[idx]["name"],
            "degree": degree_in_sign(lon),
            "longitude": round(lon, 6),
            "retrograde": speed < 0,
            "house_from_moon": house_from(idx, moon_idx),
            "house_from_lagna": house_from(idx, lagna_idx),
        }
    rahu = transits["Rahu"]
    ketu_lon = normalize_lon(rahu["longitude"] + 180.0)
    ketu_idx = sign_index(ketu_lon)
    transits["Ketu"] = {
        "sign": signs[ketu_idx]["name"],
        "degree": degree_in_sign(ketu_lon),
        "longitude": round(ketu_lon, 6),
        "retrograde": rahu["retrograde"],
        "house_from_moon": house_from(ketu_idx, moon_idx),
        "house_from_lagna": house_from(ketu_idx, lagna_idx),
    }
    return transits


def _saturn_analysis(jd_ut: float, moon_idx: int, signs: list[dict]) -> dict:
    saturn_lon = _saturn_lon(jd_ut)
    saturn_idx = sign_index(saturn_lon)
    house = house_from(saturn_idx, moon_idx)
    base = {"house_from_moon": house, "sign": signs[saturn_idx]["name"]}

    if house in (12, 1, 2):
        phase = {12: "rising", 1: "peak", 2: "setting"}[house]
        ingress = _sign_boundary(jd_ut, saturn_idx, -1)
        egress = _sign_boundary(jd_ut, saturn_idx, +1)
        return {
            **base,
            "status": "sade_sati",
            "phase": phase,
            "sign_start": _jd_to_iso_date(ingress),
            "sign_end": _jd_to_iso_date(egress),
        }
    if house in (4, 8):
        ingress = _sign_boundary(jd_ut, saturn_idx, -1)
        egress = _sign_boundary(jd_ut, saturn_idx, +1)
        return {
            **base,
            "status": "dhaiya",
            "type": "kantaka" if house == 4 else "ashtama",
            "sign_start": _jd_to_iso_date(ingress),
            "sign_end": _jd_to_iso_date(egress),
        }
    return {**base, "status": "none"}


@serialized
def calculate_gochar(kundali: dict, on_date: date | None = None) -> dict:
    setup_ayanamsa("lahiri")
    signs = load_json(DATA_DIR / "graha_data.json")["signs"]
    if on_date is None:
        on_date = date.today()

    moon_idx = sign_index(kundali["planets"]["Chandra"]["longitude"])
    lagna_idx = sign_index(kundali["lagna_longitude"])
    jd_ut = julian_day_noon_ut(on_date)

    return {
        "input": {
            "on_date": on_date.isoformat(),
            "natal_moon_sign": sign_name(kundali["planets"]["Chandra"]["longitude"], signs),
            "natal_lagna_sign": sign_name(kundali["lagna_longitude"], signs),
        },
        "transits": _transit_positions(jd_ut, signs, moon_idx, lagna_idx),
        "saturn_analysis": _saturn_analysis(jd_ut, moon_idx, signs),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calculate gochar (transits) + Sade Sati from a kundali JSON.")
    parser.add_argument("--kundali-json", required=True, help="Path to kundali JSON file")
    parser.add_argument("--date", help="Transit date: YYYY-MM-DD (default: today)")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    kundali = load_json(Path(args.kundali_json))
    on_date = parse_date(args.date) if args.date else None
    result = calculate_gochar(kundali, on_date)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        sa = result["saturn_analysis"]
        print(f"Saturn: {sa['sign']} (house {sa['house_from_moon']} from Moon) | {sa['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
