#!/usr/bin/env python
"""Avakahada Chakra: the classical birth-constant block of a janma patrika.

Pure lookups keyed on the Moon nakshatra/pada, Moon rashi, and lagna —
gan, yoni, nadi, varna, vashya, tatva, nakshatra name-syllable, rashi paya —
plus ishta ghati and dinamaan when sunrise/sunset are supplied.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

_HI_PLANETS = {
    "Surya": "सूर्य", "Chandra": "चंद्र", "Mangal": "मंगल", "Budh": "बुध",
    "Guru": "गुरु", "Shukra": "शुक्र", "Shani": "शनि", "Rahu": "राहु", "Ketu": "केतु",
}


def _load() -> dict:
    return json.loads((DATA_DIR / "avakahada_data.json").read_text(encoding="utf-8"))


def _ghati_from_hours(hours: float) -> str:
    """Format day-fraction hours as ghati:pala:vipala (60 ghati = 24 hours)."""
    total_vipala = round(hours * 2.5 * 3600)
    ghati, rem = divmod(total_vipala, 3600)
    pala, vipala = divmod(rem, 60)
    return f"{ghati:02d}:{pala:02d}:{vipala:02d}"


def compute_avakahada(
    kundali: dict,
    *,
    sunrise: str | None = None,
    sunset: str | None = None,
) -> dict:
    """Return the Avakahada Chakra rows for ``kundali``.

    ``sunrise``/``sunset`` are ISO datetimes for the birth date (from the birth
    Panchang); when given, ishta ghati and dinamaan are included.
    """
    data = _load()
    nak = kundali["nakshatra"]
    pada = int(kundali["nakshatra_pada"])
    rashi = kundali["rashi"]
    lagna = kundali["lagna"]
    moon_house = str(kundali["planets"]["Chandra"]["house"])
    syllables = data["namakshar"].get(nak, [])
    seed_lord = (kundali.get("dasha_seed") or {}).get("nakshatra_lord", "")

    out = {
        "lagna_lord": data["sign_lords"].get(lagna, ""),
        "rashi_lord": data["sign_lords"].get(rashi, ""),
        "nakshatra_lord": seed_lord,
        "nakshatra_lord_hi": _HI_PLANETS.get(seed_lord, seed_lord),
        "lagna_lord_hi": _HI_PLANETS.get(data["sign_lords"].get(lagna, ""), ""),
        "rashi_lord_hi": _HI_PLANETS.get(data["sign_lords"].get(rashi, ""), ""),
        "gan": data["gan"].get(nak, ""),
        "yoni": data["yoni"].get(nak, ""),
        "nadi": data["nadi"].get(nak, ""),
        "varna": data["varna"].get(rashi, ""),
        "vashya": data["vashya"].get(rashi, ""),
        "tatva": data["tatva"].get(rashi, ""),
        "paya": data["paya_by_moon_house"].get(moon_house, ""),
        "namakshar": syllables[pada - 1] if 1 <= pada <= len(syllables) else "",
    }

    if sunrise and sunset:
        try:
            born = datetime.fromisoformat(kundali["calculation"]["datetime_local"])
            rise = datetime.fromisoformat(sunrise)
            setting = datetime.fromisoformat(sunset)
            out["ishta_ghati"] = _ghati_from_hours(
                (born - rise).total_seconds() / 3600.0
            )
            day_seconds = int((setting - rise).total_seconds())
            hours, rem = divmod(day_seconds, 3600)
            minutes, seconds = divmod(rem, 60)
            out["dinamaan"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except (ValueError, KeyError):
            pass
    return out
