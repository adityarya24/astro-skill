from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.astro_mcp.server import get_tool, list_tool_names  # noqa: E402


def test_architecture_manifest_keeps_skill_and_product_boundaries():
    manifest = json.loads((ROOT / "project" / "architecture.json").read_text(encoding="utf-8"))

    component_paths = {component["id"]: component["path"] for component in manifest["components"]}

    assert component_paths["astro_skill"] == "astro"
    assert component_paths["astro_mcp"] == "services/astro_mcp"
    assert component_paths["pandit_web"] == "apps/pandit_web"
    assert "client-facing public bot" in manifest["non_goals"]


def test_astro_mcp_registry_exposes_v0_1_tool_surface():
    expected_tools = {
        "parse_birth_details",
        "calculate_compatibility",
        "calculate_kundali",
        "calculate_dasha",
        "calculate_gochar",
        "calculate_panchang",
        "generate_report_json",
        "generate_pdf_report",
        "save_client_profile",
        "find_client_profile",
        "list_client_reports",
    }

    names = list_tool_names()
    assert set(names) == expected_tools
    assert names == sorted(names)


def test_astro_mcp_get_tool_returns_callable_and_rejects_unknown():
    import pytest

    callable_tool = get_tool("calculate_kundali")
    assert callable(callable_tool)
    with pytest.raises(KeyError):
        get_tool("does_not_exist")


def test_astro_mcp_is_importable_as_a_package_from_repo_root():
    import importlib

    package = importlib.import_module("services.astro_mcp")
    server_module = importlib.import_module("services.astro_mcp.server")

    assert hasattr(package, "TOOLS")
    assert callable(server_module.get_tool)
    assert set(package.TOOLS.keys()) == set(server_module.list_tool_names())


def test_pyproject_includes_runtime_package_data():
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - py311+ in project metadata.
        import tomli as tomllib

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]["astro"]

    assert "SKILL.md" in package_data
    assert "config/*.json" in package_data
    assert "data/*.json" in package_data
    assert "ephe/*" in package_data
    assert "scripts/fonts/*.ttf" in package_data


def test_built_wheel_contains_runtime_assets(tmp_path: Path):
    import subprocess

    wheel_dir = tmp_path / "wheelhouse"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "-w",
            str(wheel_dir),
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    wheel = next(wheel_dir.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())

    assert "astro/SKILL.md" in names
    assert "astro/config/defaults.json" in names
    assert "astro/data/graha_data.json" in names
    assert "astro/data/ashtakavarga_data.json" in names
    assert "astro/ephe/sepl_18.se1" in names
    assert "astro/scripts/fonts/NotoSansDevanagari.ttf" in names
