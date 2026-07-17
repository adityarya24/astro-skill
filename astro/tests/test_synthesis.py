import json
import os
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from astro.scripts.synthesis import (
    RULES,
    CLIProvider,
    GeminiProvider,
    OpenAIProvider,
    Provider,
    bhava_analysis,
    dasha_deep_dive,
    executive_summary,
    get_provider,
    life_areas,
    remedies_section,
    synthesize_all,
    synthesize_bilingual,
)


class MockProvider(Provider):
    def __init__(self):
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "Canned text."


@pytest.fixture
def mock_provider(monkeypatch):
    provider = MockProvider()
    monkeypatch.setattr("astro.scripts.synthesis.get_provider", lambda: provider)
    return provider


@pytest.fixture
def synthetic_report():
    return {
        "sections": {
            "birth_chart": {
                "lagna": "Mesha",
                "moon_house": 4,
                "yoga_names": ["Ruchaka Yoga"],
                "houses": [
                    {
                        "house": 4,
                        "sign": "Karka",
                        "lord": "Chandra",
                        "lord_placement": {
                            "house": 4,
                            "sign": "Karka",
                            "strength_verdict": "Strong",
                        },
                        "planets": ["Surya", "Mangal"],
                        "aspects_received": [{"from": "Guru", "type": "5th"}],
                        "karakas": ["Chandra", "Budh"],
                    },
                    {
                        "house": 10,
                        "sign": "Makara",
                        "lord": "Shani",
                        "planets": ["Shani"],
                    },
                ],
                "planets": {
                    "Surya": {"house": 4, "dignity": "Friendly", "strength_verdict": "Weak"},
                    "Mangal": {"house": 4, "dignity": "Own", "strength_verdict": "Average"},
                    "Guru": {"house": 12, "dignity": "Enemy", "strength_verdict": "Strong"},
                    "Shani": {"house": 10, "dignity": "Own", "strength_verdict": "Strong"},
                },
                "mangalik": {"is_mangalik": True},
            },
            "current_dasha": {"period": "Surya/Mangal", "antardasha_end": "2026-12-31"},
        }
    }


def test_fact_sheet_injection_house_4(mock_provider, synthetic_report):
    # Test bhava_analysis for house 4 injects its details
    bhava_analysis(synthetic_report, "en")

    # Extract the prompt for house 4
    # The bhava_analysis calls generate() for each house in the list.
    # We have house 4 and house 10.
    prompts = mock_provider.prompts
    assert len(prompts) == 2

    house_4_prompt = prompts[0]
    assert "House 4" in house_4_prompt
    assert "Karka" in house_4_prompt
    assert "Chandra" in house_4_prompt
    assert "Surya" in house_4_prompt
    assert "Mangal" in house_4_prompt


def test_rules_text_present(mock_provider, synthetic_report):
    executive_summary(synthetic_report, "en")
    assert RULES in mock_provider.prompts[0]


def test_lang_routing(mock_provider, synthetic_report):
    executive_summary(synthetic_report, "hi")
    prompt = mock_provider.prompts[0]
    assert "Language: Hindi" in prompt
    assert "natural Devanagari jyotish register" in prompt


def test_remedies_prioritization_order(mock_provider, synthetic_report):
    remedies_data = {
        "Surya": {"remedy": "Aditya Hrudayam"},
        "Mangal": {"remedy": "Hanuman Chalisa"},
        "Guru": {"remedy": "Vishnu Sahasranama"},
        "Shani": {"remedy": "Shani Mantra"},
    }
    remedies_section(synthetic_report, remedies_data, "en")
    prompt = mock_provider.prompts[0]

    # We should see the weakest planets first, followed by average, then strong.
    # Surya (Weak), Mangal (Average, also AD lord), Guru (Strong), Shani (Strong).
    # Since Surya and Mangal are also dasha lords, they are prioritized even more if tied,
    # but score for Weak is 0, Average is 1.
    # The target_planets list is sorted and injected into the prompt.
    assert "Weakest/Dasha planets prioritized: Surya, Mangal, Guru, Shani" in prompt


def test_cli_provider_args_and_shell():
    os.environ["ASTRO_LLM_CLI_ARGS"] = '["agy", "-p", "{prompt}"]'
    provider = CLIProvider()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="CLI Output")
        result = provider.generate("my test prompt")

        assert result == "CLI Output"
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args

        cmd = args[0]
        assert cmd == ["agy", "-p", "my test prompt"]
        assert kwargs.get("shell") is False


def test_provider_factory_env_selection(monkeypatch):
    monkeypatch.setattr(os, "environ", {"ASTRO_LLM_PROVIDER": "openai"})
    assert isinstance(get_provider(), OpenAIProvider)

    monkeypatch.setattr(os, "environ", {"ASTRO_LLM_PROVIDER": "cli"})
    assert isinstance(get_provider(), CLIProvider)

    monkeypatch.setattr(os, "environ", {"ASTRO_LLM_PROVIDER": "gemini"})
    assert isinstance(get_provider(), GeminiProvider)


def test_retry_on_empty_logic(monkeypatch):
    provider = GeminiProvider()

    call_count = 0

    class MockResponse:
        def read(self):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise urllib.error.URLError("Network error")
            return json.dumps(
                {"candidates": [{"content": {"parts": [{"text": "Retry Success"}]}}]}
            ).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def mock_urlopen(req):
        nonlocal call_count
        if call_count == 0:
            call_count += 1
            raise Exception("Fail first")
        # second call succeeds
        return MockResponse()

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    result = provider.generate("test")
    assert result == "Retry Success"


def test_dasha_deep_dive(mock_provider, synthetic_report):
    dasha_deep_dive(synthetic_report, "en")
    prompt = mock_provider.prompts[0]
    assert "Surya/Mangal" in prompt
    assert "2026-12-31" in prompt


def test_life_areas(mock_provider, synthetic_report):
    life_areas(synthetic_report, "en")
    # Life areas generates 4 prompts: career, wealth, marriage, health
    assert len(mock_provider.prompts) == 4

    # At least one must mention the gochar/dasha rules
    assert "Every claim must name its placement" in mock_provider.prompts[0]


def test_synthesize_all(mock_provider, synthetic_report):
    # This should run all sections
    result = synthesize_all(synthetic_report, "en")
    assert result["executive_summary"] == "Canned text."
    assert result["bhava_analysis"]["4"] == "Canned text."
    assert result["dasha_deep_dive"] == "Canned text."
    assert result["life_areas"]["career"] == "Canned text."
    assert result["remedies"] == "Canned text."


def test_synthesize_bilingual(mock_provider, synthetic_report):
    result = synthesize_bilingual(synthetic_report)
    assert "hi" in result
    assert "en" in result
