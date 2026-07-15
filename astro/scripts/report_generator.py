#!/usr/bin/env python
"""Generate a practical astrology draft from computed calculator JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def format_doshas(doshas: list[str]) -> list[str]:
    return doshas if doshas else []


def build_birth_chart_section(kundali: dict) -> dict:
    return {
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
        "doshas": format_doshas(kundali.get("doshas", [])),
        "yogas": [yoga["name"] for yoga in kundali.get("yogas", [])],
    }


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
    if birth.get("yogas"):
        lines.append(f"Yogas: {', '.join(birth['yogas'])}.")

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
