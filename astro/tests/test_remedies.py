from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from remedies import PLANETS, get_planet_remedy, load_remedies  # noqa: E402

REQUIRED_TOP = (
    "mantra",
    "gemstone",
    "fasting",
    "daan",
    "ritual",
    "jaap_min",
    "best_time",
    "mala",
    "direction",
    "duration",
    "_source",
)
MANTRA_KEYS = ("hi", "iast", "count")
GEMSTONE_KEYS = (
    "name_hi",
    "name_en",
    "metal",
    "finger",
    "day",
    "disclaimer_hi",
    "disclaimer_en",
)
FASTING_KEYS = ("day_hi", "day_en")
LANG_PAIR = ("hi", "en")


def test_load_remedies_has_all_nine_planets():
    data = load_remedies()
    assert "planets" in data
    assert set(data["planets"]) == set(PLANETS)


def test_each_planet_has_required_schema_and_nonempty_languages():
    data = load_remedies()
    for planet in PLANETS:
        block = data["planets"][planet]
        for key in REQUIRED_TOP:
            assert key in block, f"{planet} missing {key}"

        mantra = block["mantra"]
        for k in MANTRA_KEYS:
            assert k in mantra, f"{planet}.mantra missing {k}"
        assert isinstance(mantra["hi"], str) and mantra["hi"].strip()
        assert isinstance(mantra["iast"], str) and mantra["iast"].strip()
        assert isinstance(mantra["count"], int) and mantra["count"] > 0

        gem = block["gemstone"]
        for k in GEMSTONE_KEYS:
            assert k in gem, f"{planet}.gemstone missing {k}"
            assert isinstance(gem[k], str) and gem[k].strip(), f"{planet}.gemstone.{k} empty"
        assert "qualified astrologer" in gem["disclaimer_en"].lower()
        assert "ज्योतिषी" in gem["disclaimer_hi"]

        fasting = block["fasting"]
        for k in FASTING_KEYS:
            assert k in fasting and fasting[k].strip(), f"{planet}.fasting.{k}"

        assert isinstance(block["daan"], list) and block["daan"]
        for item in block["daan"]:
            for k in LANG_PAIR:
                assert k in item and item[k].strip(), f"{planet}.daan item missing {k}"

        ritual = block["ritual"]
        for k in LANG_PAIR:
            assert k in ritual and ritual[k].strip(), f"{planet}.ritual.{k}"

        assert isinstance(block["jaap_min"], int) and block["jaap_min"] > 0
        for field in ("best_time", "mala", "direction", "duration"):
            for k in LANG_PAIR:
                value = block[field].get(k)
                assert isinstance(value, str) and value.strip(), f"{planet}.{field}.{k}"

        assert block["_source"] == "standard jyotish convention, operator-reviewed"


def test_get_planet_remedy_accessor():
    surya = get_planet_remedy("Surya")
    assert surya["mantra"]["count"] == 7000
    assert "सूर्याय" in surya["mantra"]["hi"] or "सूर्य" in surya["mantra"]["hi"]


def test_mantra_strings_match_remedies_ext():
    """Do not contradict the extended remedies file used by the report path."""
    import json

    ext_path = Path(__file__).resolve().parents[1] / "data" / "remedies_ext.json"
    ext = json.loads(ext_path.read_text(encoding="utf-8"))["planet_remedy"]
    remedies = load_remedies()["planets"]
    for planet, ext_block in ext.items():
        mantra = remedies[planet]["mantra"]
        assert mantra["hi"] == ext_block["mantra_hi"]
        assert mantra["iast"] == ext_block["mantra_iast"]
