import pytest
from astro.scripts.kundali_calculator import (
    check_combust, get_digbala, get_functional_nature, get_dignity, calculate_graha_yuddha,
    detect_mangalik, calculate_kundali, BirthInput
)

def test_combust():
    # Chandra orb is 12
    assert check_combust("Chandra", 10.0, 21.0, False) is True  # diff 11 <= 12
    assert check_combust("Chandra", 10.0, 23.0, False) is False # diff 13 > 12
    # Retro Budh orb switch (12 if retro, 14 if direct)
    assert check_combust("Budh", 10.0, 23.0, False) is True     # diff 13 <= 14
    assert check_combust("Budh", 10.0, 23.0, True) is False     # diff 13 > 12
    # Wrapping
    assert check_combust("Guru", 355.0, 5.0, False) is True     # diff 10 <= 11

def test_digbala():
    assert get_digbala("Guru", 1) == "full"
    assert get_digbala("Guru", 7) == "weak"
    assert get_digbala("Guru", 2) == "strong"
    assert get_digbala("Guru", 3) == "strong"
    assert get_digbala("Guru", 4) == "moderate"
    assert get_digbala("Chandra", 4) == "full"
    assert get_digbala("Surya", 10) == "full"
    assert get_digbala("Shani", 7) == "full"
    assert get_digbala("Rahu", 5) is None

def test_functional_nature():
    # functional_nature table has been mocked or loaded
    # Mesha: benefic (Surya, Chandra, Mangal, Guru), malefic (Budh, Shukra, Shani)
    fd = {
        "lagnas": {
            "Mesha": {"benefic": ["Surya", "Chandra", "Mangal", "Guru"], "malefic": ["Budh", "Shukra", "Shani"], "neutral": []},
            "Vrishabha": {"benefic": ["Surya", "Budh", "Shani"], "malefic": ["Chandra", "Mangal", "Guru", "Shukra"], "neutral": []}
        }
    }
    assert get_functional_nature("Surya", "Mesha", fd) == "benefic"
    assert get_functional_nature("Shukra", "Mesha", fd) == "malefic"
    assert get_functional_nature("Budh", "Vrishabha", fd) == "benefic"

def test_yuddha():
    planets = {
        "Mangal": {"longitude": 10.5},
        "Budh": {"longitude": 11.2},   # sep 0.7
        "Guru": {"longitude": 15.0},
    }
    res = calculate_graha_yuddha(planets)
    assert res["Mangal"]["in_war"] is True
    assert res["Mangal"]["winner"] is True
    assert res["Mangal"]["with"] == "Budh"
    assert res["Budh"]["winner"] is False
    assert res["Budh"]["with"] == "Mangal"
    assert res["Guru"]["in_war"] is False

def test_dignity():
    gd = {
        "planets": {
            "Surya": {"exaltation_sign": "Mesha", "debilitation_sign": "Tula", "own_signs": ["Simha"], "friends": ["Chandra"], "enemies": ["Shukra"]}
        }
    }
    signs = [{"name": "Mesha", "lord": "Mangal"}, {"name": "Karka", "lord": "Chandra"}, {"name": "Vrishabha", "lord": "Shukra"}, {"name": "Mithuna", "lord": "Budh"}]
    assert get_dignity("Surya", "Mesha", signs, gd) == "exalted"
    assert get_dignity("Surya", "Tula", signs, gd) == "debilitated"
    assert get_dignity("Surya", "Simha", signs, gd) == "own"
    assert get_dignity("Surya", "Karka", signs, gd) == "friend"
    assert get_dignity("Surya", "Vrishabha", signs, gd) == "enemy"
    assert get_dignity("Surya", "Mithuna", signs, gd) == "neutral"

def test_mangalik():
    signs = [{"name": "Mesha"}, {"name": "Vrishabha"}, {"name": "Mithuna"}, {"name": "Karka"}, {"name": "Simha"}, {"name": "Kanya"}, {"name": "Tula"}, {"name": "Vrischika"}, {"name": "Dhanu"}, {"name": "Makara"}, {"name": "Kumbha"}, {"name": "Meena"}]
    # Mangal in house 7 from lagna -> full
    res = detect_mangalik({"Mangal": {"sign": "Tula", "house": 7}}, 0, -1, signs) # 0 is Mesha lagna
    assert res["status"] == "full"
    
    # Cancelled by own sign
    res = detect_mangalik({"Mangal": {"sign": "Mesha", "house": 1}}, 0, -1, signs)
    assert res["status"] == "cancelled"
    assert any("own sign" in r for r in res["reasons"])
    
    # None
    res = detect_mangalik({"Mangal": {"sign": "Mithuna", "house": 3}}, 0, -1, signs)
    assert res["status"] == "none"

def test_fixture_sample_b():
    # SAMPLE_B: dob 07/03/2000, tob 03:20, place "Udaipur", lat 24.571, lon 73.691, timezone Asia/Kolkata, Lahiri
    inp = BirthInput(dob="07/03/2000", tob="03:20", place="Udaipur", lat=24.571, lon=73.691, timezone_name="Asia/Kolkata", ayanamsa="lahiri")
    k = calculate_kundali(inp)
    
    assert k["lagna"] == "Dhanu"
    assert k["planets"]["Chandra"]["sign"] == "Meena"
    assert k["planets"]["Chandra"]["house"] == 4
    assert k["navamsa"]["planets"]["Chandra"]["sign"] == "Karka"
    assert k["planets"]["Chandra"]["vargottama"] is False
    
    assert k["planets"]["Mangal"]["sign"] == "Meena"
    assert k["planets"]["Mangal"]["house"] == 4
    
    assert k["planets"]["Shani"]["sign"] == "Mesha"
    assert k["planets"]["Shani"]["house"] == 5
    assert k["planets"]["Shani"]["dignity"] == "debilitated"
    
    # NO planet in this chart is vargottama
    for p, info in k["planets"].items():
        assert info["vargottama"] is False
        
    assert k["mangalik"]["status"] != "none"
    assert len(k["mangalik"]["reasons"]) > 0
