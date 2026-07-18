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
        }
    ]
    assert "scoring" not in report["sections"]
