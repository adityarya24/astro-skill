from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from kundali_calculator import BirthInput, calculate_kundali  # noqa: E402
from yoga_detector import detect_yogas  # noqa: E402


def reference_chart() -> dict:
    return calculate_kundali(
        BirthInput("26/12/2019", "09:15", "Delhi", 28.6139, 77.2090, "Asia/Kolkata")
    )


def _empty_houses(lords: dict[int, str] | None = None) -> dict:
    """Build a 12-house dict; optional ``lords`` overrides house→lord mapping."""
    lords = lords or {}
    default = "Surya"
    return {
        str(h): {"lord": lords.get(h, default), "sign": "Mesha", "planets": []}
        for h in range(1, 13)
    }


def test_reference_chart_yogas_are_detected():
    chart = reference_chart()
    names = {y["name"] for y in chart["yogas"]}
    # Geometry of this chart (Dhanu stellium): Jupiter conjunct the Moon (a
    # kendra from itself), Sun and Mercury together in Dhanu, and the 7th lord
    # Chandra conjunct the 9th lord Budh (kendra/trikona lords together).
    assert "Gajakesari" in names
    assert "Budhaditya" in names
    assert "Raja Yoga" in names


def test_gajakesari_cancels_kemadruma():
    names = {y["name"] for y in reference_chart()["yogas"]}
    # A planet in a kendra from the Moon is a Kemadruma-bhanga, so Gajakesari and
    # Kemadruma must never be reported together.
    assert not ({"Gajakesari", "Kemadruma"} <= names)


def test_every_yoga_has_contract_fields():
    for yoga in reference_chart()["yogas"]:
        assert set(yoga) >= {"name", "type", "planets", "description"}
        assert yoga["planets"]


def test_mahapurusha_detected_from_dignified_kendra_placement():
    # Saturn in its own sign Makara in a kendra (house 10) -> Sasa Mahapurusha.
    planets = {
        "Chandra": {"house": 1, "sign": "Mesha"},
        "Surya": {"house": 3, "sign": "Mithuna"},
        "Budh": {"house": 4, "sign": "Karka"},
        "Mangal": {"house": 6, "sign": "Kanya"},
        "Guru": {"house": 2, "sign": "Vrishabha"},
        "Shukra": {"house": 5, "sign": "Simha"},
        "Shani": {"house": 10, "sign": "Makara"},
    }
    houses = {str(h): {"lord": "Surya"} for h in range(1, 13)}
    yogas = detect_yogas(planets, houses)
    assert any(y["name"].startswith("Sasa") for y in yogas)


# ---------------------------------------------------------------------------
# Neechabhanga Raja Yoga
# ---------------------------------------------------------------------------


def test_neechabhanga_fires_when_dispositor_in_kendra():
    # Shani debilitated in Mesha; dispositor Mangal in lagna kendra (house 1).
    planets = {
        "Shani": {"house": 5, "sign": "Mesha"},
        "Mangal": {"house": 1, "sign": "Tula"},
        "Surya": {"house": 2, "sign": "Vrischika"},
        "Chandra": {"house": 3, "sign": "Dhanu"},
        "Budh": {"house": 6, "sign": "Vrishabha"},
        "Guru": {"house": 8, "sign": "Karka"},
        "Shukra": {"house": 9, "sign": "Simha"},
        "Rahu": {"house": 11, "sign": "Tula"},
        "Ketu": {"house": 5, "sign": "Mesha"},
    }
    yogas = detect_yogas(planets, _empty_houses())
    nb = [y for y in yogas if y["name"] == "Neechabhanga Raja Yoga"]
    assert nb, "expected Neechabhanga Raja Yoga"
    assert "Shani" in nb[0]["planets"]
    assert "a_dispositor_kendra" in nb[0]["condition"]


def test_neechabhanga_does_not_fire_without_cancellation():
    # Shani debilitated in Mesha. Cancellation needs Mangal (dispositor) or Surya
    # (exalted in Mesha) in kendra from lagna/Chandra, or dispositor exchange.
    # Place both away from those kendras; Mangal not in Shani's own signs.
    # Lagna kendras: 1/4/7/10. Chandra in house 2 → Moon-kendras 2/5/8/11.
    planets = {
        "Shani": {"house": 6, "sign": "Mesha"},
        "Mangal": {"house": 3, "sign": "Mithuna"},  # not lagna/Moon kendra; not Shani own
        "Surya": {"house": 9, "sign": "Makara"},  # not lagna/Moon kendra
        "Chandra": {"house": 2, "sign": "Kumbha"},
        "Budh": {"house": 5, "sign": "Vrishabha"},
        "Guru": {"house": 8, "sign": "Mithuna"},
        "Shukra": {"house": 12, "sign": "Simha"},
        "Rahu": {"house": 11, "sign": "Tula"},
        "Ketu": {"house": 5, "sign": "Mesha"},
    }
    yogas = detect_yogas(planets, _empty_houses())
    nb = [y for y in yogas if y["name"] == "Neechabhanga Raja Yoga"]
    assert not nb, f"unexpected Neechabhanga: {nb}"


def test_neechabhanga_fires_on_dispositor_exchange():
    # Guru debilitated in Makara; dispositor Shani sits in Meena (Guru's own sign).
    planets = {
        "Guru": {"house": 3, "sign": "Makara"},
        "Shani": {"house": 5, "sign": "Meena"},
        "Surya": {"house": 2, "sign": "Dhanu"},
        "Chandra": {"house": 6, "sign": "Mesha"},
        "Mangal": {"house": 8, "sign": "Mithuna"},
        "Budh": {"house": 9, "sign": "Karka"},
        "Shukra": {"house": 11, "sign": "Kanya"},
        "Rahu": {"house": 12, "sign": "Tula"},
        "Ketu": {"house": 6, "sign": "Mesha"},
    }
    yogas = detect_yogas(planets, _empty_houses())
    nb = [y for y in yogas if y["name"] == "Neechabhanga Raja Yoga"]
    assert nb
    assert "Guru" in nb[0]["planets"]
    assert "c_dispositor_exchange" in nb[0]["condition"]


# ---------------------------------------------------------------------------
# Vipreet Raja Yoga
# ---------------------------------------------------------------------------


def test_vipreet_harsha_full_strength():
    # 6th lord Mangal in 8th (dusthana), not conjunct benefic, not own sign.
    houses = _empty_houses({6: "Mangal", 8: "Shukra", 12: "Budh", 1: "Surya"})
    planets = {
        "Mangal": {"house": 8, "sign": "Kanya"},  # not own (Mesha/Vrischika)
        "Surya": {"house": 1, "sign": "Mesha"},
        "Chandra": {"house": 2, "sign": "Vrishabha"},
        "Budh": {"house": 3, "sign": "Mithuna"},
        "Guru": {"house": 4, "sign": "Karka"},
        "Shukra": {"house": 5, "sign": "Simha"},
        "Shani": {"house": 9, "sign": "Dhanu"},
        "Rahu": {"house": 10, "sign": "Makara"},
        "Ketu": {"house": 4, "sign": "Karka"},
    }
    yogas = detect_yogas(planets, houses)
    harsha = [y for y in yogas if y["name"].startswith("Harsha")]
    assert harsha
    assert harsha[0]["strength"] == "full"
    assert "Mangal" in harsha[0]["planets"]


def test_vipreet_weaker_when_conjunct_benefic():
    # 8th lord Shani in 6th, conjunct Guru (benefic) → weaker Sarala.
    houses = _empty_houses({6: "Budh", 8: "Shani", 12: "Shukra"})
    planets = {
        "Shani": {"house": 6, "sign": "Kanya"},
        "Guru": {"house": 6, "sign": "Kanya"},  # benefic conjunct
        "Surya": {"house": 1, "sign": "Mesha"},
        "Chandra": {"house": 2, "sign": "Vrishabha"},
        "Mangal": {"house": 3, "sign": "Mithuna"},
        "Budh": {"house": 4, "sign": "Karka"},
        "Shukra": {"house": 5, "sign": "Simha"},
        "Rahu": {"house": 10, "sign": "Makara"},
        "Ketu": {"house": 4, "sign": "Karka"},
    }
    yogas = detect_yogas(planets, houses)
    sarala = [y for y in yogas if y["name"].startswith("Sarala")]
    assert sarala
    assert sarala[0]["strength"] == "weaker"


def test_vipreet_does_not_fire_when_dusthana_lord_outside_dusthana():
    houses = _empty_houses({6: "Mangal", 8: "Shukra", 12: "Budh"})
    planets = {
        "Mangal": {"house": 5, "sign": "Simha"},  # 6th lord not in dusthana
        "Shukra": {"house": 4, "sign": "Karka"},
        "Budh": {"house": 3, "sign": "Mithuna"},
        "Surya": {"house": 1, "sign": "Mesha"},
        "Chandra": {"house": 2, "sign": "Vrishabha"},
        "Guru": {"house": 7, "sign": "Tula"},
        "Shani": {"house": 9, "sign": "Dhanu"},
        "Rahu": {"house": 10, "sign": "Makara"},
        "Ketu": {"house": 4, "sign": "Karka"},
    }
    yogas = detect_yogas(planets, houses)
    vipreet = [y for y in yogas if "Vipreet" in y["name"]]
    assert not vipreet


# ---------------------------------------------------------------------------
# Kaal Sarp
# ---------------------------------------------------------------------------


def _seven_plus_nodes(houses_by_planet: dict[str, int]) -> dict:
    """Minimal planet dict with house only (signs unused for Kaal Sarp)."""
    signs_cycle = [
        "Mesha",
        "Vrishabha",
        "Mithuna",
        "Karka",
        "Simha",
        "Kanya",
        "Tula",
        "Vrischika",
        "Dhanu",
        "Makara",
        "Kumbha",
        "Meena",
    ]
    out = {}
    for name, h in houses_by_planet.items():
        out[name] = {"house": h, "sign": signs_cycle[(h - 1) % 12]}
    return out


def test_kaal_sarp_full():
    # Rahu 1 / Ketu 7; all seven in houses 1–7.
    planets = _seven_plus_nodes(
        {
            "Rahu": 1,
            "Ketu": 7,
            "Surya": 2,
            "Chandra": 3,
            "Mangal": 4,
            "Budh": 5,
            "Guru": 6,
            "Shukra": 1,
            "Shani": 7,
        }
    )
    yogas = detect_yogas(planets, _empty_houses())
    ks = [y for y in yogas if y["name"] == "Kaal Sarp"]
    assert ks
    assert ks[0]["partial"] is False
    assert ks[0]["direction"] in {"rahu_to_ketu", "ketu_to_rahu"}


def test_kaal_sarp_partial():
    # Exactly one planet (Shani) outside the Rahu→Ketu arc.
    planets = _seven_plus_nodes(
        {
            "Rahu": 1,
            "Ketu": 7,
            "Surya": 2,
            "Chandra": 3,
            "Mangal": 4,
            "Budh": 5,
            "Guru": 6,
            "Shukra": 1,
            "Shani": 10,  # outside rahu_to_ketu {1..7}
        }
    )
    yogas = detect_yogas(planets, _empty_houses())
    ks = [y for y in yogas if y["name"] == "Kaal Sarp"]
    assert ks
    assert ks[0]["partial"] is True


def test_kaal_sarp_broken_two_outside():
    planets = _seven_plus_nodes(
        {
            "Rahu": 1,
            "Ketu": 7,
            "Surya": 2,
            "Chandra": 3,
            "Mangal": 4,
            "Budh": 5,
            "Guru": 9,  # outside
            "Shukra": 10,  # outside
            "Shani": 6,
        }
    )
    yogas = detect_yogas(planets, _empty_houses())
    ks = [y for y in yogas if y["name"] == "Kaal Sarp"]
    assert not ks


# ---------------------------------------------------------------------------
# Parivartana
# ---------------------------------------------------------------------------


def test_parivartana_maha():
    # Surya in Makara (Shani), Shani in Simha (Surya); houses 1 and 10 → maha.
    planets = {
        "Surya": {"house": 1, "sign": "Makara"},
        "Shani": {"house": 10, "sign": "Simha"},
        "Chandra": {"house": 2, "sign": "Kumbha"},
        "Mangal": {"house": 3, "sign": "Meena"},
        "Budh": {"house": 5, "sign": "Vrishabha"},
        "Guru": {"house": 6, "sign": "Mithuna"},
        "Shukra": {"house": 8, "sign": "Karka"},
        "Rahu": {"house": 9, "sign": "Kanya"},
        "Ketu": {"house": 3, "sign": "Meena"},
    }
    yogas = detect_yogas(planets, _empty_houses())
    pv = [y for y in yogas if y["name"] == "Parivartana"]
    assert pv
    maha = [y for y in pv if y["type"] == "maha"]
    assert maha
    assert set(maha[0]["planets"]) == {"Surya", "Shani"}


def test_parivartana_dainya_when_dusthana_house_involved():
    # Budh in Meena (Guru), Guru in Mithuna (Budh); houses 6 and 9 → dainya.
    planets = {
        "Budh": {"house": 6, "sign": "Meena"},
        "Guru": {"house": 9, "sign": "Mithuna"},
        "Surya": {"house": 1, "sign": "Simha"},
        "Chandra": {"house": 2, "sign": "Kanya"},
        "Mangal": {"house": 3, "sign": "Tula"},
        "Shukra": {"house": 4, "sign": "Vrischika"},
        "Shani": {"house": 5, "sign": "Dhanu"},
        "Rahu": {"house": 10, "sign": "Mesha"},
        "Ketu": {"house": 4, "sign": "Vrischika"},
    }
    yogas = detect_yogas(planets, _empty_houses())
    pv = [y for y in yogas if y["name"] == "Parivartana" and y["type"] == "dainya"]
    assert pv
    assert set(pv[0]["planets"]) == {"Budh", "Guru"}


def test_parivartana_does_not_fire_without_mutual_exchange():
    # Surya in Makara but Shani not in Simha.
    planets = {
        "Surya": {"house": 1, "sign": "Makara"},
        "Shani": {"house": 10, "sign": "Kanya"},
        "Chandra": {"house": 2, "sign": "Kumbha"},
        "Mangal": {"house": 3, "sign": "Meena"},
        "Budh": {"house": 5, "sign": "Vrishabha"},
        "Guru": {"house": 6, "sign": "Mithuna"},
        "Shukra": {"house": 8, "sign": "Karka"},
        "Rahu": {"house": 9, "sign": "Simha"},
        "Ketu": {"house": 3, "sign": "Meena"},
    }
    yogas = detect_yogas(planets, _empty_houses())
    assert not [y for y in yogas if y["name"] == "Parivartana"]
