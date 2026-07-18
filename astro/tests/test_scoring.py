from astro.scripts.scoring import score_houses, score_life_areas, score_report


def _fixture_chart():
    planets = {
        "Guru": {"functional_nature": "benefic"},
        "Shukra": {"functional_nature": "benefic"},
        "Shani": {"functional_nature": "malefic"},
        "Mangal": {"functional_nature": "malefic"},
        "Budh": {"functional_nature": "neutral"},
    }
    houses = []
    for number in range(1, 13):
        houses.append(
            {
                "house": number,
                "lord": "Budh",
                "lord_placement": {"strength_verdict": "Average"},
                "planets": [],
                "aspects_received": [],
            }
        )

    houses[9].update(
        {
            "lord": "Shani",
            "lord_placement": {"strength_verdict": "Strong — own sign"},
            "planets": ["Guru", "Shukra"],
            "aspects_received": [{"from": "Guru", "type": "5th"}],
        }
    )
    houses[6].update(
        {
            "lord": "Shukra",
            "lord_placement": {"strength_verdict": "Moderate — supported"},
            "planets": ["Shani"],
            "aspects_received": [],
        }
    )
    houses[7].update(
        {
            "lord": "Mangal",
            "lord_placement": {"strength_verdict": "Weak — debilitated"},
            "planets": ["Shani", "Mangal"],
            "aspects_received": [],
        }
    )
    return houses, planets


def test_house_scores_use_only_documented_factors_and_fixed_bands():
    houses, planets = _fixture_chart()
    scores = score_houses(houses, planets, {"period": "Shani/Shukra/Guru"})

    assert scores[10]["composite_index"] == 6
    assert scores[10]["stars"] == 5
    assert scores[10]["rating"] == "★★★★★"
    assert scores[10]["band"] == "Strong"
    assert scores[10]["factors"] == {
        "house_lord": "Shani",
        "lord_strength": "Strong — own sign",
        "lord_strength_points": 2,
        "benefic_occupants": ["Guru", "Shukra"],
        "benefic_aspects": ["Guru"],
        "malefic_occupants": [],
        "dasha_activated": True,
        "benefic_yoga_support": [],
    }

    assert scores[7]["composite_index"] == 1
    assert scores[7]["stars"] == 2
    assert scores[7]["band"] == "Weak"
    assert scores[8]["composite_index"] == -2
    assert scores[8]["stars"] == 1
    assert scores[8]["band"] == "Weak"


def test_only_mahadasha_and_antardasha_activate_a_house_lord():
    houses, planets = _fixture_chart()
    scores = score_houses(
        houses,
        planets,
        {"current": {"mahadasha": "Guru", "antardasha": "Shukra", "pratyantardasha": "Budh"}},
    )

    assert scores[7]["factors"]["dasha_activated"] is True
    assert scores[1]["factors"]["dasha_activated"] is False


def test_life_area_ratings_use_fixed_house_mapping_and_half_up_mean():
    houses, planets = _fixture_chart()
    areas = score_life_areas(score_houses(houses, planets, "Shani/Shukra"))

    assert areas["career"]["houses"] == [10]
    assert areas["career"]["stars"] == 5
    assert areas["marriage"]["houses"] == [7]
    assert areas["finance"]["houses"] == [2, 11]
    assert areas["health"]["houses"] == [6, 8, 1]
    assert areas["education"]["houses"] == [5]
    assert areas["spiritual"]["houses"] == [9, 12]
    assert areas["health"]["stars"] == 2
    assert areas["health"]["band"] == "Weak"


def test_score_report_accepts_existing_report_schema_without_mutating_it():
    houses, planets = _fixture_chart()
    report = {
        "sections": {
            "birth_chart": {"houses": houses, "planets": planets},
            "current_dasha": {"period": "Shani/Shukra/Guru"},
        }
    }

    scored = score_report(report)

    assert scored["houses"][10]["stars"] == 5
    assert scored["areas"]["career"]["drivers"] == [
        {
            "house": 10,
            "house_lord": "Shani",
            "lord_strength": "Strong — own sign",
            "dasha_activated": True,
            "benefic_yoga_support": [],
        }
    ]
    assert "scoring" not in report["sections"]


def test_benefic_yoga_on_the_house_lord_raises_the_house_stars():
    houses, planets = _fixture_chart()
    dasha = {"period": "Shani/Shukra/Guru"}

    baseline = score_houses(houses, planets, dasha)
    assert baseline[7]["composite_index"] == 1
    assert baseline[7]["stars"] == 2
    assert baseline[7]["band"] == "Weak"
    assert baseline[7]["factors"]["benefic_yoga_support"] == []

    # House 7's lord is Shukra; a Dhana Yoga naming Shukra should be picked up
    # as a benefic contribution to house 7 (lord participation).
    yogas = [{"name": "Dhana Yoga", "type": "dhana", "planets": ["Shukra"]}]
    boosted = score_houses(houses, planets, dasha, yogas)

    assert boosted[7]["composite_index"] == 2
    assert boosted[7]["stars"] == 3
    assert boosted[7]["band"] == "Mixed"
    assert boosted[7]["factors"]["benefic_yoga_support"] == ["Dhana Yoga"]
    assert score_life_areas(boosted)["marriage"]["drivers"][0][
        "benefic_yoga_support"
    ] == ["Dhana Yoga"]

    # Houses the yoga's planet is not connected to are untouched.
    assert boosted[1]["composite_index"] == baseline[1]["composite_index"]


def test_dosha_yoga_does_not_contribute_to_the_composite_index():
    houses, planets = _fixture_chart()
    dasha = {"period": "Shani/Shukra/Guru"}

    baseline = score_houses(houses, planets, dasha)
    # Kaal Sarp-style dosha naming the same lord (Shukra) as house 7 must not
    # move the composite index or stars — only benefic yoga types count.
    yogas = [{"name": "Kaal Sarp", "type": "dosha", "planets": ["Shukra"]}]
    with_dosha = score_houses(houses, planets, dasha, yogas)

    assert with_dosha[7]["composite_index"] == baseline[7]["composite_index"]
    assert with_dosha[7]["stars"] == baseline[7]["stars"]
    assert with_dosha[7]["band"] == baseline[7]["band"]
    assert with_dosha[7]["factors"]["benefic_yoga_support"] == []


def test_benefic_yoga_bonus_is_capped_at_plus_two_per_house():
    houses, planets = _fixture_chart()
    dasha = {"period": "Shani/Shukra/Guru"}

    yogas = [
        {"name": "Dhana Yoga", "type": "dhana", "planets": ["Shukra"]},
        {"name": "Raja Yoga", "type": "raja", "planets": ["Shukra"]},
        {"name": "Malavya (Mahapurusha)", "type": "mahapurusha", "planets": ["Shukra"]},
    ]
    scores = score_houses(houses, planets, dasha, yogas)

    # Three qualifying yogas are all surfaced for transparency...
    assert scores[7]["factors"]["benefic_yoga_support"] == [
        "Dhana Yoga",
        "Raja Yoga",
        "Malavya (Mahapurusha)",
    ]
    # ...but the composite index only gains +2 (baseline 1, capped bonus 2).
    assert scores[7]["composite_index"] == 3
    assert scores[7]["stars"] == 4
    assert scores[7]["band"] == "Strong"
