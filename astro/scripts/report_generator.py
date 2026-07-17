#!/usr/bin/env python
"""Generate a practical astrology draft from computed calculator JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .aspects import ASPECT_OFFSETS, DEFAULT_OFFSETS, _aspected_house, compute_aspects
except ImportError:  # pragma: no cover - direct script execution path.
    from aspects import ASPECT_OFFSETS, DEFAULT_OFFSETS, _aspected_house, compute_aspects

# Standard bhava karakas (BPHS convention). Data table — not an if-chain.
HOUSE_KARAKAS: dict[int, list[str]] = {
    1: ["Surya"],
    2: ["Guru"],
    3: ["Mangal"],
    4: ["Chandra", "Budh"],
    5: ["Guru"],
    6: ["Mangal", "Shani"],
    7: ["Shukra"],
    8: ["Shani"],
    9: ["Guru", "Surya"],
    10: ["Surya", "Budh", "Guru", "Shani"],
    11: ["Guru"],
    12: ["Shani"],
}

_ORDINAL = {1: "1st", 2: "2nd", 3: "3rd"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def format_doshas(doshas: list[str]) -> list[str]:
    return doshas if doshas else []


def _ordinal(n: int) -> str:
    return _ORDINAL.get(n, f"{n}th")


def _aspect_type(planet: str, from_house: int, target_house: int) -> str:
    """Return the Parashari aspect label (e.g. '7th', '5th') used for this cast."""
    offsets = ASPECT_OFFSETS.get(planet, DEFAULT_OFFSETS)
    for off in offsets:
        if _aspected_house(from_house, off) == target_house:
            return _ordinal(off)
    return "7th"


def _aspects_received_for_house(house_no: int, planets: dict) -> list[dict]:
    """Planets casting full drishti on ``house_no``, as ``{from, type}``."""
    received: list[dict] = []
    for name, info in planets.items():
        from_house = int(info["house"])
        offsets = ASPECT_OFFSETS.get(name, DEFAULT_OFFSETS)
        for off in offsets:
            if _aspected_house(from_house, off) == house_no:
                received.append({"from": name, "type": _ordinal(off)})
                break
    return received


def _lord_placement(lord: str, planets: dict) -> dict:
    info = planets[lord]
    return {
        "house": int(info["house"]),
        "sign": info["sign"],
        "strength_verdict": info.get("strength_verdict", ""),
    }


def build_houses_section(kundali: dict) -> list[dict]:
    """All 12 houses with lord placement, aspects received, and karakas."""
    planets = kundali["planets"]
    raw_houses = kundali.get("houses", {})
    houses: list[dict] = []
    for house_no in range(1, 13):
        raw = raw_houses.get(str(house_no), {})
        lord = raw.get("lord", "")
        houses.append(
            {
                "house": house_no,
                "sign": raw.get("sign", ""),
                "lord": lord,
                "lord_placement": _lord_placement(lord, planets) if lord in planets else {
                    "house": 0,
                    "sign": "",
                    "strength_verdict": "",
                },
                "planets": list(raw.get("planets", [])),
                "aspects_received": _aspects_received_for_house(house_no, planets),
                "karakas": list(HOUSE_KARAKAS[house_no]),
            }
        )
    return houses


def _yoga_names(yogas: list) -> list[str]:
    """Extract display names; supports full detector dicts or plain name strings."""
    names: list[str] = []
    for yoga in yogas:
        if isinstance(yoga, dict):
            names.append(yoga["name"])
        else:
            names.append(str(yoga))
    return names


def build_birth_chart_section(kundali: dict) -> dict:
    # Full yoga_detector objects (name/type/planets/description). Name-only
    # consumers should use yoga_names; key_houses kept for older readers.
    yogas = list(kundali.get("yogas", []))
    section = {
        "birth_place": kundali["input"]["place"],
        "birth_datetime_local": kundali["calculation"]["datetime_local"],
        "lagna": kundali["lagna"],
        "rashi": kundali["rashi"],
        "nakshatra": f"{kundali['nakshatra']} pada {kundali['nakshatra_pada']}",
        "moon_house": kundali["planets"]["Chandra"]["house"],
        "key_houses": {
            house: kundali["houses"][house]
            for house in ("1", "5", "7", "9", "10")
            if house in kundali["houses"]
        },
        "houses": build_houses_section(kundali),
        "doshas": format_doshas(kundali.get("doshas", [])),
        "yogas": yogas,
        "yoga_names": _yoga_names(yogas),
        "ashtakavarga": kundali.get("ashtakavarga"),
        # Pass-through of T1 planet flags (vargottama/combust/graha_yuddha/
        # digbala/functional_nature/dignity/strength_verdict) untouched.
        "planets": kundali.get("planets", {}),
        "aspects": kundali.get("aspects") or compute_aspects(kundali.get("planets", {})),
    }
    if "mangalik" in kundali:
        section["mangalik"] = kundali["mangalik"]
    return section


def build_dasha_section(dasha: dict | None) -> dict | None:
    if not dasha:
        return None
    current = dasha.get("current")
    if not current:
        return {
            "system": dasha["system"],
            "seed": f"{dasha['seed_nakshatra']} / {dasha['seed_lord']}",
            "period": None,
            "mahadasha_end": None,
            "antardasha_end": None,
            "pratyantardasha_end": None,
        }
    period = f"{current['mahadasha']}/{current['antardasha']}"
    # Third level exists since Tier 3; .get() keeps pre-Tier-3 dasha JSON working.
    if current.get("pratyantardasha"):
        period += f"/{current['pratyantardasha']}"
    return {
        "system": dasha["system"],
        "seed": f"{dasha['seed_nakshatra']} / {dasha['seed_lord']}",
        "period": period,
        "mahadasha_end": current["mahadasha_end"],
        "antardasha_end": current["antardasha_end"],
        "pratyantardasha_end": current.get("pratyantardasha_end"),
    }


def build_panchang_section(panchang: dict | None) -> dict | None:
    if not panchang:
        return None
    daily = panchang["panchang"]
    return {
        "date": panchang["input"]["date"],
        "place": panchang["input"]["place"],
        "vara": daily["vara"],
        "tithi": f"{daily['tithi']['paksha']} {daily['tithi']['name']}",
        "tithi_ends": daily["tithi"].get("ends_at"),
        "nakshatra": f"{daily['nakshatra']['name']} pada {daily['nakshatra']['pada']}",
        "nakshatra_ends": daily["nakshatra"].get("ends_at"),
        "yoga": daily["yoga"]["name"],
        "karana": daily["karana"]["name"],
        "sunrise": daily["sunrise"],
        "sunset": daily["sunset"],
        "muhurta": daily.get("muhurta"),
        "warnings": panchang.get("warnings", []),
    }


def build_basic_report(
    kundali: dict,
    *,
    dasha: dict | None = None,
    panchang: dict | None = None,
    language: str = "hin",
) -> dict:
    if language not in {"hin", "hi", "en"}:
        raise ValueError("language must be one of: hin, hi, en")

    return {
        "language": language,
        "title": "Basic Astrology Draft",
        "sections": {
            "birth_chart": build_birth_chart_section(kundali),
            "current_dasha": build_dasha_section(dasha),
            "daily_panchang": build_panchang_section(panchang),
        },
        "notes": (
            [
                "यह प्रारूप केवल ज्योतिषी/संचालक की समीक्षा हेतु है; गणनाएँ व्याख्या में सहायक हैं, विवेक का स्थान नहीं लेतीं।",
                "मृत्यु, चिकित्सा, दुर्घटना, या अनिवार्य-हानि संबंधी भविष्यवाणियाँ न करें।",
            ]
            if language in {"hin", "hi"}
            else [
                "Draft for astrologer/operator review only; calculations support the reading, they do not replace judgement.",
                "Avoid death, medical, accident, or unavoidable-harm predictions.",
            ]
        ),
    }


def build_text_report(report: dict) -> str:
    birth = report["sections"]["birth_chart"]
    lines = [
        report["title"],
        "",
        f"Birth chart: Lagna {birth['lagna']}, Rashi {birth['rashi']}, Nakshatra {birth['nakshatra']}.",
        f"Moon house: {birth['moon_house']}.",
    ]
    if birth["doshas"]:
        lines.append(f"Doshas flagged: {', '.join(birth['doshas'])}.")
    yoga_names = birth.get("yoga_names") or _yoga_names(birth.get("yogas") or [])
    if yoga_names:
        lines.append(f"Yogas: {', '.join(yoga_names)}.")

    dasha = report["sections"]["current_dasha"]
    if dasha:
        lines.append(
            f"Current dasha: {dasha['period'] or '-'}; "
            f"Mahadasha ends {dasha['mahadasha_end'] or '-'}, "
            f"Antardasha ends {dasha['antardasha_end'] or '-'}."
        )

    panchang = report["sections"]["daily_panchang"]
    if panchang:
        lines.append(
            f"Panchang: {panchang['vara']}, {panchang['tithi']}, "
            f"{panchang['nakshatra']}, Yoga {panchang['yoga']}, Karana {panchang['karana']}."
        )
        muhurta = panchang.get("muhurta")
        if muhurta:
            rahu = muhurta["rahu_kaal"]
            lines.append(f"Rahu Kaal: {rahu['start']} to {rahu['end']}.")

    lines.extend(["", *report["notes"]])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a basic astrology draft from JSON inputs.")
    parser.add_argument("--kundali-json", required=True, help="Path to kundali JSON")
    parser.add_argument("--dasha-json", help="Optional path to dasha JSON")
    parser.add_argument("--panchang-json", help="Optional path to panchang JSON")
    parser.add_argument("--language", choices=["hin", "hi", "en"], default="hin")
    parser.add_argument("--json", action="store_true")
    return parser


def configure_stdout() -> None:
    """Keep Devanagari CLI output working on Windows cp1252 consoles."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    configure_stdout()
    args = build_parser().parse_args(argv)
    report = build_basic_report(
        load_json(Path(args.kundali_json)),
        dasha=load_json(Path(args.dasha_json)) if args.dasha_json else None,
        panchang=load_json(Path(args.panchang_json)) if args.panchang_json else None,
        language=args.language,
    )
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(build_text_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
