"""LLM Synthesis Layer."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


def _llm_timeout() -> int:
    """Request timeout (seconds) for all LLM providers, env-configurable.

    The dasha_deep_dive prompt reliably needs >20s and can exceed 60s for
    long Hindi prose, so the default is generous. Override with
    ASTRO_LLM_TIMEOUT.
    """
    raw = os.environ.get("ASTRO_LLM_TIMEOUT", "60")
    try:
        return int(raw)
    except ValueError:
        return 60


RULES = """RULES:
- Every sentence MUST cite at least one concrete chart factor (e.g., "Because Jupiter sits in the 5th...").
- ZERO generic filler ("aapka bhavishya ujjwal hai" type lines are forbidden).
- Balanced: strengths AND cautions, no fear-mongering, no medical/legal/financial guarantees.
- NEVER invent a placement, yoga, or date — only facts present in the supplied JSON. If a fact is not in the JSON, it does not exist.
- Output plain paragraphs (no markdown headers inside sections)."""


def lang_instruction(lang: str) -> str:
    if lang == "hi":
        return "Language: Hindi (natural Devanagari jyotish register, not transliteration)."
    return "Language: English."


class Provider:
    def generate(self, prompt: str) -> str:
        raise NotImplementedError


class GeminiProvider(Provider):
    def __init__(self) -> None:
        self.api_key = os.environ.get("ASTRO_LLM_API_KEY", "")
        self.model = os.environ.get("ASTRO_LLM_MODEL", "gemini-2.5-pro")
        self.timeout = _llm_timeout()

    def generate(self, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3}
        }
        req = urllib.request.Request(
            url,
            json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            import sys
            sys.stderr.write(f"GeminiProvider failed first attempt: {e}\n")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    return res["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                import sys
                sys.stderr.write(f"GeminiProvider failed second attempt: {e}\n")
                return ""


class OpenAIProvider(Provider):
    def __init__(self) -> None:
        self.api_key = os.environ.get("ASTRO_LLM_API_KEY", "")
        self.base_url = os.environ.get("ASTRO_LLM_BASE_URL", "https://api.openai.com/v1")
        self.model = os.environ.get("ASTRO_LLM_MODEL", "gpt-4o")
        self.timeout = _llm_timeout()

    def generate(self, prompt: str) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        req = urllib.request.Request(
            url,
            json.dumps(data).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res["choices"][0]["message"]["content"]
        except Exception as e:
            import sys
            sys.stderr.write(f"OpenAIProvider failed first attempt: {e}\n")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    return res["choices"][0]["message"]["content"]
            except Exception as e:
                import sys
                sys.stderr.write(f"OpenAIProvider failed second attempt: {e}\n")
                return ""


class CLIProvider(Provider):
    def __init__(self) -> None:
        args_str = os.environ.get("ASTRO_LLM_CLI_ARGS", '["agy", "-p", "{prompt}"]')
        self.args = json.loads(args_str)
        self.timeout = _llm_timeout()

    def generate(self, prompt: str) -> str:
        # replace {prompt} as a whole-token substitution only
        cmd = [prompt if arg == "{prompt}" else arg for arg in self.args]
        try:
            res = subprocess.run(cmd, shell=False, capture_output=True, text=True, check=True, timeout=self.timeout)
            return res.stdout.strip()
        except Exception as e:
            import sys
            sys.stderr.write(f"CLIProvider failed first attempt: {e}\n")
            try:
                res = subprocess.run(cmd, shell=False, capture_output=True, text=True, check=True, timeout=self.timeout)
                return res.stdout.strip()
            except Exception as e:
                import sys
                sys.stderr.write(f"CLIProvider failed second attempt: {e}\n")
                return ""


def get_provider() -> Provider:
    provider_name = os.environ.get("ASTRO_LLM_PROVIDER", "gemini")
    if provider_name == "openai":
        return OpenAIProvider()
    elif provider_name == "cli":
        return CLIProvider()
    else:
        return GeminiProvider()


def executive_summary(report: dict, lang: str) -> str:
    birth = report.get("sections", {}).get("birth_chart", {})
    dasha = report.get("sections", {}).get("current_dasha", {})

    fact_sheet = {
        "lagna": birth.get("lagna"),
        "moon_house": birth.get("moon_house"),
        "yogas": birth.get("yoga_names", []),
        "dasha": dasha.get("period") if dasha else None,
        "dasha_ends": dasha.get("antardasha_end") if dasha else None,
    }

    prompt = f"""Write an executive summary of this astrological chart (core strength / current dasha window / biggest opportunity / watch area. 4 short paragraphs max).
{RULES}
{lang_instruction(lang)}

FACT SHEET:
{json.dumps(fact_sheet, ensure_ascii=False, indent=2)}
"""
    return get_provider().generate(prompt)


def bhava_analysis(report: dict, lang: str) -> dict:
    birth = report.get("sections", {}).get("birth_chart", {})
    houses = birth.get("houses", [])
    planets_info = birth.get("planets", {})
    dasha = report.get("sections", {}).get("current_dasha", {})
    dasha_period = dasha.get("period", "") if dasha else ""
    md_lord = ""
    ad_lord = ""
    if dasha_period:
        parts = dasha_period.split("/")
        if len(parts) >= 1:
            md_lord = parts[0]
        if len(parts) >= 2:
            ad_lord = parts[1]

    results = {}
    for h in houses:
        house_no = h.get("house")
        h_facts = {
            "house": house_no,
            "sign": h.get("sign"),
            "lord": h.get("lord"),
            "lord_placement": h.get("lord_placement"),
            "occupants": [],
            "aspects_received": h.get("aspects_received"),
            "karakas": h.get("karakas"),
            "current_dasha_lords": [p for p in (md_lord, ad_lord) if p]
        }
        for occ in h.get("planets", []):
            if isinstance(occ, str):
                name = occ
            else:
                name = occ.get("name")
            p_info = planets_info.get(name, {})
            h_facts["occupants"].append({
                "name": name,
                "dignity": p_info.get("dignity"),
                "strength_verdict": p_info.get("strength_verdict"),
                "vargottama": p_info.get("vargottama"),
                "combust": p_info.get("combust"),
                "digbala": p_info.get("digbala"),
                "functional_nature": p_info.get("functional_nature")
            })

        prompt = f"""Write the house analysis for House {house_no} (2-4 sentences).
{RULES}
{lang_instruction(lang)}

FACT SHEET (ONLY USE THESE FACTS):
{json.dumps(h_facts, ensure_ascii=False, indent=2)}
"""
        results[str(house_no)] = get_provider().generate(prompt)
    return results


def dasha_deep_dive(report: dict, lang: str, gochar_narrative: dict | None = None) -> str:
    birth = report.get("sections", {}).get("birth_chart", {})
    dasha = report.get("sections", {}).get("current_dasha", {})
    if not dasha:
        return ""
    planets = birth.get("planets", {})
    houses = birth.get("houses", [])

    period = dasha.get("period", "")
    parts = period.split("/")
    md = parts[0] if len(parts) >= 1 else None
    ad = parts[1] if len(parts) >= 2 else None

    md_info = {}
    if md and md in planets:
        md_info = dict(planets[md])
        md_info["owns_houses"] = [h.get("house") for h in houses if h.get("lord") == md]

    ad_info = {}
    if ad and ad in planets:
        ad_info = dict(planets[ad])
        ad_info["owns_houses"] = [h.get("house") for h in houses if h.get("lord") == ad]

    fact_sheet = {
        "period": period,
        "antardasha_end": dasha.get("antardasha_end"),
        "mahadasha_lord_info": md_info,
        "antardasha_lord_info": ad_info,
        "gochar_narrative": gochar_narrative.get("synthesis_facts") if gochar_narrative else None
    }

    prompt = f"""Write a dasha deep dive focusing ONLY on the current antardasha window (opportunities, risks, month-wise guidance).
{RULES}
{lang_instruction(lang)}

FACT SHEET:
{json.dumps(fact_sheet, ensure_ascii=False, indent=2)}
"""
    return get_provider().generate(prompt)


def life_areas(report: dict, lang: str, gochar_narrative: dict | None = None) -> dict:
    birth = report.get("sections", {}).get("birth_chart", {})
    houses = birth.get("houses", [])
    planets = birth.get("planets", {})
    dasha = report.get("sections", {}).get("current_dasha", {})

    def get_house(num: int) -> dict:
        for h in houses:
            if h.get("house") == num:
                return h
        return {}

    gochar_synthesis = gochar_narrative.get("synthesis_facts") if gochar_narrative else None

    career_facts = {
        "house_10": get_house(10),
        "Saturn": planets.get("Shani"),
        "Sun": planets.get("Surya"),
        "dasha": dasha.get("period") if dasha else None,
        "gochar_narrative": gochar_synthesis
    }
    wealth_facts = {
        "house_2": get_house(2),
        "house_11": get_house(11),
        "Jupiter": planets.get("Guru"),
        "dasha": dasha.get("period") if dasha else None,
        "gochar_narrative": gochar_synthesis
    }
    marriage_facts = {
        "house_7": get_house(7),
        "Venus": planets.get("Shukra"),
        "mangalik": birth.get("mangalik"),
        "dasha": dasha.get("period") if dasha else None,
        "gochar_narrative": gochar_synthesis
    }
    lagna_lord = get_house(1).get("lord", "")
    health_facts = {
        "house_6": get_house(6),
        "house_8": get_house(8),
        "lagna_lord": lagna_lord,
        "lagna_lord_placement": planets.get(lagna_lord) if lagna_lord else None,
        "dasha": dasha.get("period") if dasha else None,
        "gochar_narrative": gochar_synthesis
    }

    areas = {
        "career": career_facts,
        "wealth": wealth_facts,
        "marriage": marriage_facts,
        "health": health_facts
    }

    results = {}
    for area, facts in areas.items():
        prompt = f"""Write the {area} life area analysis. Every claim must name its placement + a timing window from dasha/gochar data.
{RULES}
{lang_instruction(lang)}

FACT SHEET:
{json.dumps(facts, ensure_ascii=False, indent=2)}
"""
        results[area] = get_provider().generate(prompt)
    return results


def remedies_section(report: dict, remedies_data: dict, lang: str) -> str:
    birth = report.get("sections", {}).get("birth_chart", {})
    planets = birth.get("planets", {})
    dasha = report.get("sections", {}).get("current_dasha", {})

    period = dasha.get("period", "") if dasha else ""
    parts = period.split("/")
    md = parts[0] if len(parts) >= 1 else ""
    ad = parts[1] if len(parts) >= 2 else ""

    strength_order = {"Weak": 0, "Average": 1, "Strong": 2}

    def sort_key(planet_tuple: tuple[str, dict]) -> tuple:
        name, info = planet_tuple
        strength = info.get("strength_verdict", "Average")
        score = strength_order.get(strength, 1)
        is_dasha = 0 if name in [md, ad] else 1
        return (score, is_dasha, name)

    sorted_planets = sorted(planets.items(), key=sort_key)
    target_planets = [name for name, _ in sorted_planets]

    # remedies.json wraps per-planet entries under a top-level "planets" key
    # (alongside "_comment"); remedies_ext.json (the fallback) is flat.
    remedies_by_planet = remedies_data.get("planets", remedies_data)

    remedies_to_send = {}
    for p in target_planets:
        if p in remedies_by_planet:
            remedies_to_send[p] = remedies_by_planet[p]

    prompt = f"""Write a remedies section. Prioritize the weakest planets and current dasha lords.
{RULES}
{lang_instruction(lang)}

FACT SHEET (Weakest/Dasha planets prioritized: {', '.join(target_planets)}):
{json.dumps(remedies_to_send, ensure_ascii=False, indent=2)}
"""
    return get_provider().generate(prompt)


def synthesize_all(report: dict, lang: str, gochar_narrative: dict | None = None) -> dict:
    data_dir = Path(__file__).parent.parent / "data"
    remedies_path = data_dir / "remedies.json"
    if not remedies_path.exists():
        logging.info("remedies.json not found; falling back to remedies_ext.json")
        remedies_path = data_dir / "remedies_ext.json"
    
    remedies_data = {}
    if remedies_path.exists():
        with remedies_path.open("r", encoding="utf-8") as f:
            remedies_data = json.load(f)

    return {
        "executive_summary": executive_summary(report, lang),
        "bhava_analysis": bhava_analysis(report, lang),
        "dasha_deep_dive": dasha_deep_dive(report, lang, gochar_narrative),
        "life_areas": life_areas(report, lang, gochar_narrative),
        "remedies": remedies_section(report, remedies_data, lang)
    }


def synthesize_bilingual(report: dict, gochar_narrative: dict | None = None) -> dict:
    return {
        "hi": synthesize_all(report, "hi", gochar_narrative),
        "en": synthesize_all(report, "en", gochar_narrative)
    }
