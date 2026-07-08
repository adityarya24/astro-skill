#!/usr/bin/env python
"""Calculate daily Panchang fields using Lahiri sidereal positions."""
from __future__ import annotations

import argparse
import json
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
    from .kundali_calculator import configure_ephemeris, detect_ephemeris, validate_geo
    from .swe_lock import serialized
except ImportError:  # pragma: no cover - direct script execution path.
    from kundali_calculator import configure_ephemeris, detect_ephemeris, validate_geo
    from swe_lock import serialized

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"

NAKSHATRA_SPAN = 360.0 / 27.0
PADA_SPAN = NAKSHATRA_SPAN / 4.0
TITHI_SPAN = 12.0
KARANA_SPAN = 6.0

VARA_BY_WEEKDAY = [
    "Somavara",
    "Mangalavara",
    "Budhavara",
    "Guruvara",
    "Shukravara",
    "Shanivara",
    "Ravivara",
]

TITHI_NAMES = [
    "Pratipada",
    "Dwitiya",
    "Tritiya",
    "Chaturthi",
    "Panchami",
    "Shashthi",
    "Saptami",
    "Ashtami",
    "Navami",
    "Dashami",
    "Ekadashi",
    "Dwadashi",
    "Trayodashi",
    "Chaturdashi",
    "Purnima",
    "Pratipada",
    "Dwitiya",
    "Tritiya",
    "Chaturthi",
    "Panchami",
    "Shashthi",
    "Saptami",
    "Ashtami",
    "Navami",
    "Dashami",
    "Ekadashi",
    "Dwadashi",
    "Trayodashi",
    "Chaturdashi",
    "Amavasya",
]

YOGA_NAMES = [
    "Vishkambha",
    "Priti",
    "Ayushman",
    "Saubhagya",
    "Shobhana",
    "Atiganda",
    "Sukarma",
    "Dhriti",
    "Shula",
    "Ganda",
    "Vriddhi",
    "Dhruva",
    "Vyaghata",
    "Harshana",
    "Vajra",
    "Siddhi",
    "Vyatipata",
    "Variyana",
    "Parigha",
    "Shiva",
    "Siddha",
    "Sadhya",
    "Shubha",
    "Shukla",
    "Brahma",
    "Indra",
    "Vaidhriti",
]

MOVABLE_KARANAS = ["Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti"]
FIXED_KARANAS = {1: "Kimstughna", 58: "Shakuni", 59: "Chatushpada", 60: "Naga"}

# Inauspicious day-period kaals occupy one of the eight equal parts of the
# daytime (sunrise->sunset). The part (1-8, counted from sunrise) depends on the
# weekday. Indexed by Python weekday: Monday=0 .. Sunday=6.
RAHU_KAAL_SEGMENT = [2, 7, 5, 6, 4, 3, 8]
YAMAGANDA_SEGMENT = [4, 3, 2, 1, 7, 6, 5]
GULIKA_SEGMENT = [6, 5, 4, 3, 2, 1, 7]


@dataclass(frozen=True)
class PanchangInput:
    date: str
    place: str
    lat: float
    lon: float
    timezone_name: str
    ayanamsa: str = "lahiri"

    def __post_init__(self) -> None:
        validate_geo(self.lat, self.lon)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_date(value: str) -> tuple[int, int, int]:
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must be YYYY-MM-DD") from exc
    return dt.year, dt.month, dt.day


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


def local_day_datetime(input_data: PanchangInput, hour: int) -> datetime:
    year, month, day = parse_date(input_data.date)
    return datetime(year, month, day, hour, tzinfo=ZoneInfo(input_data.timezone_name))


def julian_day_ut(dt: datetime) -> float:
    utc = dt.astimezone(timezone.utc)
    hour = utc.hour + utc.minute / 60.0 + utc.second / 3600.0 + utc.microsecond / 3_600_000_000.0
    return swe.julday(utc.year, utc.month, utc.day, hour)


def datetime_from_julian_day_ut(jd_ut: float, tz: ZoneInfo) -> datetime:
    year, month, day, hour_decimal = swe.revjul(jd_ut)
    hour = int(hour_decimal)
    minute_decimal = (hour_decimal - hour) * 60.0
    minute = int(minute_decimal)
    second = int(round((minute_decimal - minute) * 60.0))
    if second >= 60:
        minute += 1
        second -= 60
    if minute >= 60:
        hour += 1
        minute -= 60
    utc = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    return utc.astimezone(tz)


def calc_body(jd_ut: float, body_id: int) -> float:
    flags = swe.FLG_SIDEREAL | swe.FLG_SWIEPH
    try:
        data, _ = swe.calc_ut(jd_ut, body_id, flags)
    except swe.Error:
        data, _ = swe.calc_ut(jd_ut, body_id, swe.FLG_SIDEREAL | swe.FLG_MOSEPH)
    return normalize_lon(float(data[0]))


def _moon_minus_sun(jd_ut: float) -> float:
    return normalize_lon(calc_body(jd_ut, swe.MOON) - calc_body(jd_ut, swe.SUN))


def _sun_plus_moon(jd_ut: float) -> float:
    return normalize_lon(calc_body(jd_ut, swe.SUN) + calc_body(jd_ut, swe.MOON))


def _moon_longitude(jd_ut: float) -> float:
    return calc_body(jd_ut, swe.MOON)


def crossing_time_jd(
    anchor_jd: float, raw_fn, span: float, search_days: float = 1.6
) -> float | None:
    """JD (UT) when ``raw_fn`` next leaves its current ``span``-degree segment.

    ``raw_fn`` is a smooth, forward-moving angle (tithi/karana use moon-sun, yoga
    uses sun+moon, nakshatra uses the Moon). Displacement from the anchor stays
    well under 360 deg over the search window, so it is monotonic and a simple
    bisection on ``disp(jd) >= needed`` pins the boundary to sub-second accuracy.
    """
    base = raw_fn(anchor_jd)
    needed = span - (base % span)

    def disp(jd: float) -> float:
        return (raw_fn(jd) - base) % 360.0

    lo, hi = anchor_jd, anchor_jd + search_days
    if disp(hi) < needed:
        return None  # boundary not reached within the window (unexpected)
    for _ in range(50):
        mid = (lo + hi) / 2.0
        if disp(mid) < needed:
            lo = mid
        else:
            hi = mid
    return hi


def day_period(start_jd: float, segment: float, index: int, tz: ZoneInfo) -> dict:
    """ISO window for the 1-based ``index`` part of an 8-part daytime split."""
    start = start_jd + (index - 1) * segment
    return {"start": jd_to_iso(start, tz), "end": jd_to_iso(start + segment, tz)}


def muhurta_periods(
    sunrise_jd: float | None, sunset_jd: float | None, weekday: int, tz: ZoneInfo
) -> dict | None:
    """Rahu Kaal, Yamaganda, Gulika, Abhijit, and Brahma muhurta windows.

    Needs both sunrise and sunset; returns ``None`` (with the caller adding a
    warning) when either is missing, e.g. in polar latitudes.
    """
    if sunrise_jd is None or sunset_jd is None:
        return None
    day_length = sunset_jd - sunrise_jd
    eighth = day_length / 8.0
    muhurta = day_length / 15.0  # one of the 15 daytime muhurtas
    abhijit_start = sunrise_jd + 7 * muhurta  # the 8th (midday) muhurta
    night_muhurta = (1.0 - day_length) / 15.0  # one of the 15 night muhurtas
    brahma_start = sunrise_jd - 2 * night_muhurta  # 2 muhurtas before sunrise
    return {
        "rahu_kaal": day_period(sunrise_jd, eighth, RAHU_KAAL_SEGMENT[weekday], tz),
        "yamaganda": day_period(sunrise_jd, eighth, YAMAGANDA_SEGMENT[weekday], tz),
        "gulika": day_period(sunrise_jd, eighth, GULIKA_SEGMENT[weekday], tz),
        "abhijit": {
            "start": jd_to_iso(abhijit_start, tz),
            "end": jd_to_iso(abhijit_start + muhurta, tz),
        },
        "brahma_muhurta": {
            "start": jd_to_iso(brahma_start, tz),
            "end": jd_to_iso(brahma_start + night_muhurta, tz),
        },
    }


def nakshatra_for(longitude: float, nakshatras: list[dict]) -> dict:
    normalized = normalize_lon(longitude)
    index = min(26, int(normalized // NAKSHATRA_SPAN))
    within = normalized - index * NAKSHATRA_SPAN
    pada = min(4, int(within // PADA_SPAN) + 1)
    item = dict(nakshatras[index])
    item["pada"] = pada
    item["longitude_within"] = round(within, 6)
    return item


def tithi_for(sun_lon: float, moon_lon: float) -> dict:
    angle = normalize_lon(moon_lon - sun_lon)
    number = min(30, int(angle // TITHI_SPAN) + 1)
    paksha = "Shukla" if number <= 15 else "Krishna"
    lunar_day = number if number <= 15 else number - 15
    return {
        "number": number,
        "name": TITHI_NAMES[number - 1],
        "paksha": paksha,
        "lunar_day": lunar_day,
        "elapsed_degrees": round(angle % TITHI_SPAN, 6),
    }


def yoga_for(sun_lon: float, moon_lon: float) -> dict:
    combined = normalize_lon(sun_lon + moon_lon)
    index = min(26, int(combined // NAKSHATRA_SPAN))
    return {
        "number": index + 1,
        "name": YOGA_NAMES[index],
        "elapsed_degrees": round(combined - index * NAKSHATRA_SPAN, 6),
    }


def karana_for(sun_lon: float, moon_lon: float) -> dict:
    angle = normalize_lon(moon_lon - sun_lon)
    segment = min(60, int(angle // KARANA_SPAN) + 1)
    if segment in FIXED_KARANAS:
        name = FIXED_KARANAS[segment]
    else:
        name = MOVABLE_KARANAS[(segment - 2) % len(MOVABLE_KARANAS)]
    return {
        "number": segment,
        "name": name,
        "elapsed_degrees": round(angle % KARANA_SPAN, 6),
    }


def solar_event_jd(
    midnight_jd_ut: float,
    lon: float,
    lat: float,
    flag: int,
    label: str,
    warnings: list[str],
) -> float | None:
    """Return the Julian Day (UT) of the next sunrise/sunset after local midnight."""
    try:
        code, values = swe.rise_trans(midnight_jd_ut, swe.SUN, flag, (lon, lat, 0.0))
    except swe.Error as exc:
        warnings.append(f"{label} unavailable: {exc}")
        return None
    if code != 0:
        warnings.append(f"{label} unavailable: Swiss Ephemeris returned code {code}")
        return None
    return float(values[0])


def jd_to_iso(jd_ut: float | None, tz: ZoneInfo) -> str | None:
    if jd_ut is None:
        return None
    return datetime_from_julian_day_ut(jd_ut, tz).isoformat()


@serialized
def calculate_panchang(input_data: PanchangInput) -> dict:
    setup_ayanamsa(input_data.ayanamsa)
    graha_data = load_json(DATA_DIR / "graha_data.json")
    nakshatra_data = load_json(DATA_DIR / "nakshatra_db.json")["nakshatras"]
    signs = graha_data["signs"]
    tz = ZoneInfo(input_data.timezone_name)

    local_noon = local_day_datetime(input_data, 12)
    local_midnight = local_day_datetime(input_data, 0)
    noon_jd_ut = julian_day_ut(local_noon)
    midnight_jd_ut = julian_day_ut(local_midnight)
    warnings: list[str] = []

    # Classical Panchang is defined at sunrise: the tithi/nakshatra/yoga/karana
    # prevailing at sunrise are "the day's" values. Anchor positions there, and
    # only fall back to local noon if sunrise cannot be computed (polar cases).
    sunrise_jd = solar_event_jd(midnight_jd_ut, input_data.lon, input_data.lat, swe.CALC_RISE, "sunrise", warnings)
    sunset_jd = solar_event_jd(midnight_jd_ut, input_data.lon, input_data.lat, swe.CALC_SET, "sunset", warnings)

    if sunrise_jd is not None:
        anchor_jd = sunrise_jd
        anchor = "sunrise"
    else:
        anchor_jd = noon_jd_ut
        anchor = "local_noon_fallback"
        warnings.append("Sunrise unavailable; Panchang anchored to local noon as a fallback.")

    anchor_local = datetime_from_julian_day_ut(anchor_jd, tz)
    sun_lon = calc_body(anchor_jd, swe.SUN)
    moon_lon = calc_body(anchor_jd, swe.MOON)
    moon_nak = nakshatra_for(moon_lon, nakshatra_data)

    # End-times: when each element prevailing at the anchor gives way to the next.
    tithi = tithi_for(sun_lon, moon_lon)
    tithi["ends_at"] = jd_to_iso(crossing_time_jd(anchor_jd, _moon_minus_sun, TITHI_SPAN), tz)
    yoga = yoga_for(sun_lon, moon_lon)
    yoga["ends_at"] = jd_to_iso(crossing_time_jd(anchor_jd, _sun_plus_moon, NAKSHATRA_SPAN), tz)
    karana = karana_for(sun_lon, moon_lon)
    karana["ends_at"] = jd_to_iso(crossing_time_jd(anchor_jd, _moon_minus_sun, KARANA_SPAN), tz)
    nakshatra_block = {
        "name": moon_nak["name"],
        "pada": moon_nak["pada"],
        "lord": moon_nak["lord"],
        "gana": moon_nak["gana"],
        "yoni": moon_nak["yoni"],
        "ends_at": jd_to_iso(crossing_time_jd(anchor_jd, _moon_longitude, NAKSHATRA_SPAN), tz),
    }

    weekday = anchor_local.weekday()
    muhurta = muhurta_periods(sunrise_jd, sunset_jd, weekday, tz)
    if muhurta is None:
        warnings.append(
            "Muhurta windows (Rahu Kaal etc.) unavailable: sunrise/sunset could not be computed."
        )

    return {
        "input": {
            "date": input_data.date,
            "place": input_data.place,
            "lat": input_data.lat,
            "lon": input_data.lon,
            "timezone": input_data.timezone_name,
        },
        "calculation": {
            "datetime_local": anchor_local.isoformat(),
            "julian_day_ut": round(anchor_jd, 6),
            "anchor": anchor,
            "ayanamsa": input_data.ayanamsa.lower(),
            "ayanamsa_degrees": round(float(swe.get_ayanamsa_ut(anchor_jd)), 6),
            "ephemeris": detect_ephemeris(anchor_jd),
            "note": "Daily Panchang fields are calculated at sunrise (classical convention) from house-independent solar/lunar positions.",
        },
        "sun": {
            "sign": sign_name(sun_lon, signs),
            "degree": degree_in_sign(sun_lon),
            "longitude": round(sun_lon, 6),
        },
        "moon": {
            "sign": sign_name(moon_lon, signs),
            "degree": degree_in_sign(moon_lon),
            "longitude": round(moon_lon, 6),
        },
        "panchang": {
            "vara": VARA_BY_WEEKDAY[weekday],
            "tithi": tithi,
            "nakshatra": nakshatra_block,
            "yoga": yoga,
            "karana": karana,
            "sunrise": jd_to_iso(sunrise_jd, tz),
            "sunset": jd_to_iso(sunset_jd, tz),
            "muhurta": muhurta,
        },
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    defaults = load_json(CONFIG_DIR / "defaults.json")
    parser = argparse.ArgumentParser(description="Calculate daily Panchang JSON.")
    parser.add_argument("--date", required=True, help="Local date: YYYY-MM-DD")
    parser.add_argument("--place", required=True)
    parser.add_argument("--lat", type=float, default=defaults["default_lat"])
    parser.add_argument("--lon", type=float, default=defaults["default_lon"])
    parser.add_argument("--timezone", default=defaults["default_timezone"])
    parser.add_argument("--ayanamsa", default=defaults["ayanamsa"])
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = calculate_panchang(
        PanchangInput(
            date=args.date,
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
        panchang = result["panchang"]
        print(
            f"Vara: {panchang['vara']} | "
            f"Tithi: {panchang['tithi']['paksha']} {panchang['tithi']['name']} | "
            f"Nakshatra: {panchang['nakshatra']['name']} pada {panchang['nakshatra']['pada']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
