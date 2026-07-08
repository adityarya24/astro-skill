#!/usr/bin/env python
"""Guna Milan — Ashtakoot (eight-fold, 36-point) marriage compatibility.

Pure scoring over two charts' Moon rashi + nakshatra (and Mars for Manglik). The
lookup tables live in ``astro/data/compatibility_data.json`` so they are
auditable and adjustable; nakshatra gana/yoni come from ``nakshatra_db.json``.
Convention: ``kundali_a`` = bride, ``kundali_b`` = groom.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def _load(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


COMPAT = _load("compatibility_data.json")
_GRAHA = _load("graha_data.json")
SIGNS = _GRAHA["signs"]
NAKSHATRAS = _load("nakshatra_db.json")["nakshatras"]

SIGN_IDX = {s["name"]: s["index"] for s in SIGNS}
NAK_IDX = {n["name"]: n["index"] for n in NAKSHATRAS}
NADI_OF_INDEX = {idx: nadi for nadi, idxs in COMPAT["nadi_by_index"].items() for idx in idxs}
YONI_ENEMIES = {frozenset(pair) for pair in COMPAT["yoni_enemies"]}


def _rashi_element(idx: int) -> str:
    return SIGNS[idx]["element"]


def _rashi_lord(idx: int) -> str:
    return SIGNS[idx]["lord"]


def _rashi_name(idx: int) -> str:
    return SIGNS[idx]["name"]


def _nak(idx: int) -> dict:
    return NAKSHATRAS[idx]


# ---- Individual kutas ------------------------------------------------------


def varna_points(bride: dict, groom: dict) -> int:
    rank = COMPAT["element_varna"]
    return 1 if rank[_rashi_element(groom["rashi_idx"])] >= rank[_rashi_element(bride["rashi_idx"])] else 0


def vashya_points(bride: dict, groom: dict) -> float:
    bi, gi = bride["rashi_idx"], groom["rashi_idx"]
    if bi == gi:
        return 2
    controls = COMPAT["vashya_controls"]
    b_controls_g = _rashi_name(gi) in controls[_rashi_name(bi)]
    g_controls_b = _rashi_name(bi) in controls[_rashi_name(gi)]
    if b_controls_g and g_controls_b:
        return 2
    if b_controls_g or g_controls_b:
        return 1
    return 0


def _tara_favourable(from_idx: int, to_idx: int) -> bool:
    count = ((to_idx - from_idx) % 27) + 1
    return (count % 9) not in (3, 5, 7)


def tara_points(bride: dict, groom: dict) -> float:
    points = 0.0
    if _tara_favourable(bride["nak_idx"], groom["nak_idx"]):
        points += 1.5
    if _tara_favourable(groom["nak_idx"], bride["nak_idx"]):
        points += 1.5
    return points


def yoni_points(bride: dict, groom: dict) -> int:
    yb = _nak(bride["nak_idx"])["yoni"]
    yg = _nak(groom["nak_idx"])["yoni"]
    if yb == yg:
        return 4
    if frozenset({yb, yg}) in YONI_ENEMIES:
        return 0
    return 2


def _relation(lord_a: str, lord_b: str) -> str:
    if lord_a == lord_b:
        return "friend"
    info = COMPAT["planet_friends"][lord_a]
    if lord_b in info["friends"]:
        return "friend"
    if lord_b in info["enemies"]:
        return "enemy"
    return "neutral"


def graha_maitri_points(bride: dict, groom: dict) -> float:
    la, lb = _rashi_lord(bride["rashi_idx"]), _rashi_lord(groom["rashi_idx"])
    key = "|".join(sorted([_relation(la, lb), _relation(lb, la)]))
    return COMPAT["graha_maitri_points"][key]


def gana_points(bride: dict, groom: dict) -> int:
    ga, gb = _nak(bride["nak_idx"])["gana"], _nak(groom["nak_idx"])["gana"]
    if ga == gb:
        return COMPAT["gana_points"]["same"]
    return COMPAT["gana_points"]["|".join(sorted([ga, gb]))]


def bhakoot_points(bride: dict, groom: dict) -> int:
    bi, gi = bride["rashi_idx"], groom["rashi_idx"]
    pair = {((gi - bi) % 12) + 1, ((bi - gi) % 12) + 1}
    return 0 if pair in ({6, 8}, {2, 12}, {5, 9}) else 7


def nadi_points(bride: dict, groom: dict) -> int:
    return 0 if NADI_OF_INDEX[bride["nak_idx"]] == NADI_OF_INDEX[groom["nak_idx"]] else 8


# ---- Doshas ----------------------------------------------------------------


def _nadi_dosha(bride: dict, groom: dict) -> dict:
    if NADI_OF_INDEX[bride["nak_idx"]] != NADI_OF_INDEX[groom["nak_idx"]]:
        return {"present": False, "note": "different nadi"}
    # Cancellation: same rashi but different nakshatra.
    cancelled = bride["rashi_idx"] == groom["rashi_idx"] and bride["nak_idx"] != groom["nak_idx"]
    note = "same nadi; cancelled (same rashi, different nakshatra)" if cancelled else "same nadi"
    return {"present": not cancelled, "cancelled": cancelled, "note": note}


def _bhakoot_dosha(bride: dict, groom: dict) -> dict:
    if bhakoot_points(bride, groom) != 0:
        return {"present": False, "note": "no bhakoot dosha"}
    la, lb = _rashi_lord(bride["rashi_idx"]), _rashi_lord(groom["rashi_idx"])
    cancelled = la == lb or (_relation(la, lb) == "friend" and _relation(lb, la) == "friend")
    note = "6-8/2-12/5-9 axis; cancelled (rashi lords same/friends)" if cancelled else "6-8/2-12/5-9 axis"
    return {"present": not cancelled, "cancelled": cancelled, "note": note}


def _manglik_dosha(bride: dict, groom: dict) -> dict:
    b, g = bool(bride.get("manglik")), bool(groom.get("manglik"))
    if b and g:
        return {"present": False, "note": "both manglik - compatible"}
    if b or g:
        return {"present": True, "note": "one partner manglik"}
    return {"present": False, "note": "neither manglik"}


# ---- Aggregate -------------------------------------------------------------


def _verdict(total: float) -> str:
    for band in COMPAT["verdict_bands"]:
        if total >= band["min"]:
            return band["label"]
    return COMPAT["verdict_bands"][-1]["label"]


def compatibility_from_persons(bride: dict, groom: dict) -> dict:
    kutas = [
        ("Varna", varna_points(bride, groom), 1),
        ("Vashya", vashya_points(bride, groom), 2),
        ("Tara", tara_points(bride, groom), 3),
        ("Yoni", yoni_points(bride, groom), 4),
        ("Graha Maitri", graha_maitri_points(bride, groom), 5),
        ("Gana", gana_points(bride, groom), 6),
        ("Bhakoot", bhakoot_points(bride, groom), 7),
        ("Nadi", nadi_points(bride, groom), 8),
    ]
    total = sum(points for _, points, _ in kutas)
    return {
        "kutas": [{"name": name, "points": points, "max": maximum} for name, points, maximum in kutas],
        "total": total,
        "max": 36,
        "verdict": _verdict(total),
        "doshas": {
            "nadi": _nadi_dosha(bride, groom),
            "bhakoot": _bhakoot_dosha(bride, groom),
            "manglik": _manglik_dosha(bride, groom),
        },
    }


def person_from_kundali(kundali: dict) -> dict:
    return {
        "rashi_idx": SIGN_IDX[kundali["planets"]["Chandra"]["sign"]],
        "nak_idx": NAK_IDX[kundali["nakshatra"]],
        "pada": kundali.get("nakshatra_pada", 1),
        "manglik": any("Mangalik" in d for d in kundali.get("doshas", [])),
    }


def calculate_compatibility(kundali_a: dict, kundali_b: dict) -> dict:
    """Ashtakoot compatibility. ``kundali_a`` = bride, ``kundali_b`` = groom."""
    return compatibility_from_persons(person_from_kundali(kundali_a), person_from_kundali(kundali_b))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guna Milan (Ashtakoot) compatibility from two kundali JSONs.")
    parser.add_argument("--kundali-a-json", required=True, help="Bride kundali JSON path")
    parser.add_argument("--kundali-b-json", required=True, help="Groom kundali JSON path")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    a = json.loads(Path(args.kundali_a_json).read_text(encoding="utf-8"))
    b = json.loads(Path(args.kundali_b_json).read_text(encoding="utf-8"))
    result = calculate_compatibility(a, b)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Guna Milan: {result['total']}/36 ({result['verdict']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
