#!/usr/bin/env python
"""Calculate a Vedic kundali using Lahiri sidereal positions."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import swisseph as swe
except ImportError as exc:  # pragma: no cover - exercised by users without dependency.
    raise SystemExit(
        "Missing dependency: pyswisseph. Install with `python -m pip install pyswisseph`."
    ) from exc

try:
    from .ashtakavarga import compute_ashtakavarga
    from .aspects import compute_aspects
    from .swe_lock import serialized
    from .vargas import compute_divisional_charts
    from .yoga_detector import detect_yogas
except ImportError:  # pragma: no cover - direct script execution path.
    from ashtakavarga import compute_ashtakavarga
    from aspects import compute_aspects
    from swe_lock import serialized
    from vargas import compute_divisional_charts
    from yoga_detector import detect_yogas

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"

NAKSHATRA_SPAN = 360.0 / 27.0
PADA_SPAN = NAKSHATRA_SPAN / 4.0

PLANET_IDS = {
    "Surya": swe.SUN,
    "Chandra": swe.MOON,
    "Mangal": swe.MARS,
    "Budh": swe.MERCURY,
    "Guru": swe.JUPITER,
    "Shukra": swe.VENUS,
    "Shani": swe.SATURN,
    "Rahu": swe.MEAN_NODE,
}


@dataclass(frozen=True)
class BirthInput:
    dob: str
    tob: str
    place: str
    lat: float
    lon: float
    timezone_name: str
    ayanamsa: str = "lahiri"

    def __post_init__(self) -> None:
        validate_geo(self.lat, self.lon)


def validate_geo(lat: float, lon: float) -> None:
    """Reject out-of-range coordinates instead of producing a garbage chart."""
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"lat must be between -90 and 90 degrees, got {lat}")
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"lon must be between -180 and 180 degrees, got {lon}")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_date(value: str) -> tuple[int, int, int]:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.year, dt.month, dt.day
        except ValueError:
            continue
    raise ValueError("dob must be DD/MM/YYYY or YYYY-MM-DD")


def parse_time(value: str) -> tuple[int, int, int]:
    parts = value.strip().split(":")
    if len(parts) not in (2, 3):
        raise ValueError("tob must be HH:MM or HH:MM:SS")
    hour, minute = int(parts[0]), int(parts[1])
    second = int(parts[2]) if len(parts) == 3 else 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        raise ValueError("tob is outside a valid 24-hour clock")
    return hour, minute, second


def local_datetime(input_data: BirthInput) -> datetime:
    year, month, day = parse_date(input_data.dob)
    hour, minute, second = parse_time(input_data.tob)
    return datetime(year, month, day, hour, minute, second, tzinfo=ZoneInfo(input_data.timezone_name))


def julian_day_ut(dt: datetime) -> float:
    utc = dt.astimezone(timezone.utc)
    hour = utc.hour + utc.minute / 60.0 + utc.second / 3600.0 + utc.microsecond / 3_600_000_000.0
    return swe.julday(utc.year, utc.month, utc.day, hour)


def configure_ephemeris() -> None:
    """Point Swiss Ephemeris at the high-precision ``.se1`` data when available.

    Looks at ``SE_EPHE_PATH`` first (set in the Docker image), then falls back to
    the ``.se1`` files bundled in the repo at ``astro/ephe``. With the data
    present, ``calc_ut`` uses the precise Swiss Ephemeris (SWIEPH); without it,
    swisseph silently falls back to the built-in Moshier model. Either way the
    tier actually used is reported by :func:`detect_ephemeris`.
    """
    ephe_path = os.environ.get("SE_EPHE_PATH") or str(ROOT / "ephe")
    if Path(ephe_path).is_dir():
        swe.set_ephe_path(ephe_path)


AYANAMSA_MODES = {
    "lahiri": swe.SIDM_LAHIRI,
    "chitrapaksha": swe.SIDM_LAHIRI,
    "raman": swe.SIDM_RAMAN,
    "krishnamurti": swe.SIDM_KRISHNAMURTI,
    "kp": swe.SIDM_KRISHNAMURTI,
    "fagan_bradley": swe.SIDM_FAGAN_BRADLEY,
    "true_chitra": swe.SIDM_TRUE_CITRA,
    "yukteshwar": swe.SIDM_YUKTESHWAR,
}


def setup_ayanamsa(name: str) -> None:
    configure_ephemeris()
    mode = AYANAMSA_MODES.get(name.lower())
    if mode is None:
        raise ValueError(f"Unsupported ayanamsa {name!r}. Supported: {sorted(AYANAMSA_MODES)}")
    swe.set_sid_mode(mode)


def normalize_lon(value: float) -> float:
    return value % 360.0


def sign_index(longitude: float) -> int:
    return int(normalize_lon(longitude) // 30)


def sign_name(longitude: float, signs: list[dict]) -> str:
    return signs[sign_index(longitude)]["name"]


def degree_in_sign(longitude: float) -> float:
    return round(normalize_lon(longitude) % 30.0, 6)


def nakshatra_for(longitude: float, nakshatras: list[dict]) -> dict:
    normalized = normalize_lon(longitude)
    index = min(26, int(normalized // NAKSHATRA_SPAN))
    within = normalized - index * NAKSHATRA_SPAN
    pada = min(4, int(within // PADA_SPAN) + 1)
    item = dict(nakshatras[index])
    item["pada"] = pada
    item["longitude_within"] = within
    return item


def calc_body(jd_ut: float, body_id: int) -> tuple[float, float]:
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED | swe.FLG_SWIEPH
    try:
        data, _ = swe.calc_ut(jd_ut, body_id, flags)
    except swe.Error:
        data, _ = swe.calc_ut(jd_ut, body_id, swe.FLG_SIDEREAL | swe.FLG_SPEED | swe.FLG_MOSEPH)
    return normalize_lon(float(data[0])), float(data[3])


def detect_ephemeris(jd_ut: float) -> str:
    """Report which ephemeris actually answered: high-precision Swiss Ephemeris
    (``swieph``, requires the ``.se1`` data) or the built-in Moshier fallback
    (``moshier``, lower precision). swisseph does not raise when SWIEPH data is
    missing — it silently uses Moshier and signals the real source in the return
    flags — so detection must read those flags, not catch an exception."""
    _, retflags = swe.calc_ut(jd_ut, swe.SUN, swe.FLG_SIDEREAL | swe.FLG_SWIEPH)
    return "swieph" if retflags & swe.FLG_SWIEPH else "moshier"


def ascendant_sidereal(jd_ut: float, lat: float, lon: float) -> float:
    _, ascmc = swe.houses(jd_ut, lat, lon, b"P")
    tropical_asc = float(ascmc[0])
    ayanamsa = float(swe.get_ayanamsa_ut(jd_ut))
    return normalize_lon(tropical_asc - ayanamsa)


def house_from_lagna(planet_sign: int, lagna_sign: int) -> int:
    return ((planet_sign - lagna_sign) % 12) + 1


NAVAMSA_SPAN = 30.0 / 9.0  # 3°20' — each navamsa equals one nakshatra pada


def navamsa_sign_index(longitude: float) -> int:
    """Sign index (0-11) of a longitude in the Navamsa (D9) divisional chart.

    Each 30° sign splits into 9 navamsas of 3°20'. Counting navamsas continuously
    from Mesha 0° and taking modulo 12 reproduces the classical element rule
    (movable signs start from themselves, fixed from the 9th, dual from the 5th).
    """
    return int(normalize_lon(longitude) // NAVAMSA_SPAN) % 12



def check_combust(planet: str, lon: float, sun_lon: float, is_retrograde: bool) -> bool:
    if planet in ("Surya", "Rahu", "Ketu"):
        return False
    sep = abs(lon - sun_lon)
    if sep > 180:
        sep = 360 - sep
    if planet == "Chandra": orb = 12
    elif planet == "Mangal": orb = 17
    elif planet == "Budh": orb = 12 if is_retrograde else 14
    elif planet == "Guru": orb = 11
    elif planet == "Shukra": orb = 8 if is_retrograde else 10
    elif planet == "Shani": orb = 15
    else: orb = 0
    return sep <= orb

def get_functional_nature(planet: str, lagna_sign: str, functional_data: dict) -> str:
    data = functional_data.get("lagnas", {}).get(lagna_sign, {})
    if planet in data.get("benefic", []): return "benefic"
    if planet in data.get("malefic", []): return "malefic"
    if planet in data.get("neutral", []): return "neutral"
    return "neutral"

def get_digbala(planet: str, house: int) -> str | None:
    if planet in ("Rahu", "Ketu"): return None
    full_house = 0
    if planet in ("Guru", "Budh"): full_house = 1
    elif planet in ("Chandra", "Shukra"): full_house = 4
    elif planet == "Shani": full_house = 7
    elif planet in ("Surya", "Mangal"): full_house = 10
    if not full_house: return None
    
    dist = abs(house - full_house)
    if dist > 6:
        dist = 12 - dist
        
    if dist == 0: return "full"
    elif dist in (1, 2): return "strong"
    elif dist in (3, 4): return "moderate"
    else: return "weak"

def get_dignity(planet: str, sign_name: str, signs: list[dict], graha_data: dict) -> str:
    if planet in ("Rahu", "Ketu"): return "neutral"
    pdata = graha_data["planets"].get(planet, {})
    if sign_name == pdata.get("exaltation_sign"): return "exalted"
    if sign_name == pdata.get("debilitation_sign"): return "debilitated"
    if sign_name in pdata.get("own_signs", []): return "own"
    
    lord = next((s["lord"] for s in signs if s["name"] == sign_name), None)
    if lord in pdata.get("friends", []): return "friend"
    if lord in pdata.get("enemies", []): return "enemy"
    return "neutral"

def calculate_graha_yuddha(planets: dict) -> dict:
    # only Mangal, Budh, Guru, Shukra, Shani
    participants = ["Mangal", "Budh", "Guru", "Shukra", "Shani"]
    yuddha = {p: {"in_war": False, "winner": None, "with": None} for p in planets}
    
    for i, p1 in enumerate(participants):
        if p1 not in planets: continue
        lon1 = planets[p1]["longitude"]
        for p2 in participants[i+1:]:
            if p2 not in planets: continue
            lon2 = planets[p2]["longitude"]
            sep = abs(lon1 - lon2)
            if sep > 180: sep = 360 - sep
            if sep <= 1.0:
                # War! lower longitude wins
                w = p1 if lon1 < lon2 else p2
                l = p2 if lon1 < lon2 else p1
                yuddha[w] = {"in_war": True, "winner": True, "with": l}
                yuddha[l] = {"in_war": True, "winner": False, "with": w}
    return yuddha

def calculate_navamsa(lagna_lon: float, planets: dict, signs: list[dict]) -> dict:
    nav_lagna_sign = navamsa_sign_index(lagna_lon)
    nav_planets: dict[str, dict] = {}
    for planet, info in planets.items():
        nav_sign = navamsa_sign_index(info["longitude"])
        nav_planets[planet] = {
            "sign": signs[nav_sign]["name"],
            "house": house_from_lagna(nav_sign, nav_lagna_sign),
        }
    nav_houses: dict[str, dict] = {}
    for offset in range(12):
        idx = (nav_lagna_sign + offset) % 12
        nav_houses[str(offset + 1)] = {
            "sign": signs[idx]["name"],
            "lord": signs[idx]["lord"],
            "planets": [p for p, i in nav_planets.items() if i["house"] == offset + 1],
        }
    return {
        "lagna": signs[nav_lagna_sign]["name"],
        "planets": nav_planets,
        "houses": nav_houses,
    }


def duration_to_ymd(years_decimal: float) -> dict:
    years = int(math.floor(years_decimal))
    months_decimal = (years_decimal - years) * 12
    months = int(math.floor(months_decimal))
    days = int(round((months_decimal - months) * 30.436875))
    if days >= 30:
        months += 1
        days -= 30
    if months >= 12:
        years += 1
        months -= 12
    return {"years": years, "months": months, "days": days}



def detect_mangalik(planets: dict, lagna_sign_idx: int, moon_sign_idx: int, signs: list[dict]) -> dict:
    mangal = planets.get("Mangal")
    if not mangal:
        return {"status": "none", "reasons": [], "legacy_list": []}
    
    mangal_sign_name = mangal["sign"]
    mangal_sign_idx = next(i for i, s in enumerate(signs) if s["name"] == mangal_sign_name)
    
    house_from_lagna = ((mangal_sign_idx - lagna_sign_idx) % 12) + 1
    house_from_moon = ((mangal_sign_idx - moon_sign_idx) % 12) + 1 if moon_sign_idx != -1 else 0
    
    reasons = []
    is_mangalik = False
    severity_full = False
    
    legacy_list = []
    if house_from_lagna in {1, 2, 4, 7, 8, 12}:
        sev = "full" if house_from_lagna in {7, 8} else "partial"
        legacy_list.append(f"Mangalik ({sev})")
    
    if house_from_lagna in {1, 2, 4, 7, 8, 12}:
        is_mangalik = True
        sev = "full" if house_from_lagna in {7, 8} else "partial"
        if sev == "full": severity_full = True
        reasons.append(f"from lagna")
        
    if house_from_moon in {1, 2, 4, 7, 8, 12}:
        is_mangalik = True
        sev = "full" if house_from_moon in {7, 8} else "partial"
        if sev == "full": severity_full = True
        reasons.append(f"from chandra")
        
    if not is_mangalik:
        return {"status": "none", "reasons": [], "legacy_list": legacy_list}
        
    cancellations = []
    if mangal_sign_name in {"Mesha", "Vrischika"}:
        cancellations.append("Mars in own sign")
    elif mangal_sign_name == "Makara":
        cancellations.append("Mars in exalted sign")
        
    guru = planets.get("Guru")
    if guru:
        guru_sign_idx = next(i for i, s in enumerate(signs) if s["name"] == guru["sign"])
        guru_aspects = [(guru_sign_idx + 4) % 12, (guru_sign_idx + 6) % 12, (guru_sign_idx + 8) % 12]
        if mangal_sign_idx in guru_aspects:
            cancellations.append("Guru drishti")
            
    conjunctions = []
    if guru and guru["house"] == mangal["house"]:
        conjunctions.append("Guru")
    shukra = planets.get("Shukra")
    if shukra and shukra["house"] == mangal["house"]:
        conjunctions.append("Shukra")
    
    moon = planets.get("Chandra")
    if moon and moon["house"] == mangal["house"] and not moon.get("combust", False):
        # A combust (Sun-close) Moon lacks paksha bala and does not count as a
        # benefic for mangalik cancellation, even in shukla paksha.
        sun = planets.get("Surya")
        if sun:
            diff = (moon["longitude"] - sun["longitude"]) % 360
            if 0 < diff <= 180:
                conjunctions.append("waxing Chandra")
                
    if conjunctions:
        cancellations.append("benefic conjunction")
        
    if cancellations:
        return {"status": "cancelled", "reasons": reasons + ["cancelled: " + ", ".join(cancellations)], "legacy_list": legacy_list}
        
    return {"status": "full" if severity_full else "partial", "reasons": reasons, "legacy_list": legacy_list}




@serialized
def calculate_kundali(input_data: BirthInput) -> dict:
    setup_ayanamsa(input_data.ayanamsa)
    graha_data = load_json(DATA_DIR / "graha_data.json")
    nakshatra_data = load_json(DATA_DIR / "nakshatra_db.json")["nakshatras"]
    try:
        functional_data = load_json(DATA_DIR / "functional_nature.json")
    except Exception:
        functional_data = {}
    signs = graha_data["signs"]

    local_dt = local_datetime(input_data)
    jd_ut = julian_day_ut(local_dt)
    ayanamsa = round(float(swe.get_ayanamsa_ut(jd_ut)), 6)
    lagna_lon = ascendant_sidereal(jd_ut, input_data.lat, input_data.lon)
    lagna_sign = sign_index(lagna_lon)

    planets: dict[str, dict] = {}
    for planet, body_id in PLANET_IDS.items():
        lon, speed = calc_body(jd_ut, body_id)
        nak = nakshatra_for(lon, nakshatra_data)
        house = house_from_lagna(sign_index(lon), lagna_sign)
        planets[planet] = {
            "sign": sign_name(lon, signs),
            "degree": degree_in_sign(lon),
            "longitude": round(lon, 6),
            "house": house,
            "nakshatra": nak["name"],
            "nakshatra_pada": nak["pada"],
            "retrograde": speed < 0,
        }

    rahu_lon = planets["Rahu"]["longitude"]
    ketu_lon = normalize_lon(rahu_lon + 180.0)
    ketu_nak = nakshatra_for(ketu_lon, nakshatra_data)
    planets["Ketu"] = {
        "sign": sign_name(ketu_lon, signs),
        "degree": degree_in_sign(ketu_lon),
        "longitude": round(ketu_lon, 6),
        "house": house_from_lagna(sign_index(ketu_lon), lagna_sign),
        "nakshatra": ketu_nak["name"],
        "nakshatra_pada": ketu_nak["pada"],
        "retrograde": planets["Rahu"]["retrograde"],
    }

    # Now calculate additional properties
    navamsa = calculate_navamsa(lagna_lon, planets, signs)
    yuddha_data = calculate_graha_yuddha(planets)
    sun_lon = planets.get("Surya", {}).get("longitude", 0.0)
    lagna_sign_name = sign_name(lagna_lon, signs)

    for p, info in planets.items():
        info["vargottama"] = info["sign"] == navamsa["planets"][p]["sign"]
        info["combust"] = check_combust(p, info["longitude"], sun_lon, info["retrograde"])
        info["graha_yuddha"] = yuddha_data[p]
        info["digbala"] = get_digbala(p, info["house"])
        info["functional_nature"] = get_functional_nature(p, lagna_sign_name, functional_data)
        dignity = get_dignity(p, info["sign"], signs, graha_data)
        info["dignity"] = dignity
        
        pos = []
        neg = []
        mild = []  # descriptors that inform but don't move the verdict
        if dignity == "exalted": pos.append("exalted")
        elif dignity == "own": pos.append("own sign")
        elif dignity == "friend": mild.append("friend")
        elif dignity == "debilitated": neg.append("debilitated")
        elif dignity == "enemy": neg.append("enemy")

        if info["vargottama"]: pos.append("vargottama")
        if info["digbala"] == "full": pos.append("digbala full")
        if info["graha_yuddha"]["winner"] is True: pos.append("war winner")

        if info["combust"]: neg.append("combust")
        if info["graha_yuddha"]["winner"] is False: neg.append("war loser")

        score = len(pos) - len(neg)
        prefix = "Strong" if score > 0 else "Weak" if score < 0 else "Moderate"
        reasons = pos + neg + mild
        info["strength_verdict"] = f"{prefix} — {', '.join(reasons)}" if reasons else f"{prefix} — neutral"

    houses: dict[str, dict] = {}
    for offset in range(12):
        idx = (lagna_sign + offset) % 12
        sign = signs[idx]
        house_no = str(offset + 1)
        houses[house_no] = {
            "sign": sign["name"],
            "lord": sign["lord"],
            "planets": [planet for planet, info in planets.items() if info["house"] == offset + 1],
        }

    moon_lon = planets["Chandra"]["longitude"]
    moon_nak = nakshatra_for(moon_lon, nakshatra_data)
    lord = moon_nak["lord"]
    lord_years = float(graha_data["planets"][lord]["vimshottari_years"])
    elapsed_fraction = moon_nak["longitude_within"] / NAKSHATRA_SPAN
    balance_years = lord_years * (1.0 - elapsed_fraction)
    
    moon_sign_idx = sign_index(moon_lon)
    mangalik_result = detect_mangalik(planets, lagna_sign, moon_sign_idx, signs)

    return {
        "input": {
            "dob": input_data.dob,
            "tob": input_data.tob,
            "place": input_data.place,
            "lat": input_data.lat,
            "lon": input_data.lon,
            "timezone": input_data.timezone_name,
        },
        "calculation": {
            "datetime_local": local_dt.isoformat(),
            "datetime_utc": local_dt.astimezone(timezone.utc).isoformat(),
            "julian_day_ut": round(jd_ut, 6),
            "ayanamsa": input_data.ayanamsa.lower(),
            "ayanamsa_degrees": ayanamsa,
            "house_system": "whole_sign",
            "ephemeris": detect_ephemeris(jd_ut),
        },
        "lagna": sign_name(lagna_lon, signs),
        "lagna_degree": degree_in_sign(lagna_lon),
        "lagna_longitude": round(lagna_lon, 6),
        "rashi": planets["Chandra"]["sign"],
        "nakshatra": moon_nak["name"],
        "nakshatra_pada": moon_nak["pada"],
        "planets": planets,
        "houses": houses,
        "aspects": compute_aspects(planets),
        "navamsa": navamsa,
        "divisional_charts": compute_divisional_charts(
            {**{name: info["longitude"] for name, info in planets.items()}, "Lagna": lagna_lon},
            signs,
        ),
        "ashtakavarga": compute_ashtakavarga(
            {p: sign_index(planets[p]["longitude"])
             for p in ("Surya", "Chandra", "Mangal", "Budh", "Guru", "Shukra", "Shani")},
            lagna_sign,
        ),
        "yogas": detect_yogas(planets, houses, graha_data),
        "dasha_seed": {
            "nakshatra": moon_nak["name"],
            "nakshatra_lord": lord,
            "balance_years_decimal": round(balance_years, 8),
            "balance_at_birth": duration_to_ymd(balance_years),
        },
        "doshas": mangalik_result["legacy_list"],
        "mangalik": {"status": mangalik_result["status"], "reasons": mangalik_result["reasons"]},
    }



def build_parser() -> argparse.ArgumentParser:
    defaults = load_json(CONFIG_DIR / "defaults.json")
    parser = argparse.ArgumentParser(description="Calculate Vedic kundali JSON.")
    parser.add_argument("--dob", required=True, help="Date of birth: DD/MM/YYYY or YYYY-MM-DD")
    parser.add_argument("--tob", required=True, help="Time of birth: HH:MM in local timezone")
    parser.add_argument("--place", required=True)
    parser.add_argument("--lat", type=float, default=defaults["default_lat"])
    parser.add_argument("--lon", type=float, default=defaults["default_lon"])
    parser.add_argument("--timezone", default=defaults["default_timezone"])
    parser.add_argument("--ayanamsa", default=defaults["ayanamsa"])
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = calculate_kundali(
        BirthInput(
            dob=args.dob,
            tob=args.tob,
            place=args.place,
            lat=args.lat,
            lon=args.lon,
            timezone_name=args.timezone,
            ayanamsa=args.ayanamsa,
        )
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"Lagna: {result['lagna']} {result['lagna_degree']} | "
            f"Moon: {result['rashi']} | Nakshatra: {result['nakshatra']} pada {result['nakshatra_pada']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
