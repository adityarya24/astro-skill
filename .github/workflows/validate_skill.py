"""Minimal CI validator for the portable astro skill directory.

This mirrors the checks that matter for GitHub CI without depending on a
developer's local Codex installation path.
"""
from __future__ import annotations

import sys
from pathlib import Path


REQUIRED_FILES = [
    "SKILL.md",
    "scripts/kundali_calculator.py",
    "scripts/dasha_calculator.py",
    "scripts/panchang_calculator.py",
    "scripts/report_generator.py",
    "scripts/pdf_report.py",
    "scripts/html_pdf_report.py",
    "data/graha_data.json",
    "data/nakshatra_db.json",
    "config/defaults.json",
]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: validate_skill.py <skill-dir>", file=sys.stderr)
        return 2
    skill_dir = Path(argv[1])
    missing = [path for path in REQUIRED_FILES if not (skill_dir / path).exists()]
    if missing:
        print("Skill validation failed. Missing files:", file=sys.stderr)
        for path in missing:
            print(f"- {path}", file=sys.stderr)
        return 1
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    required_terms = [
        "Required Inputs",
        "Phase 1 Workflow",
        "Phase 4 Workflow",
        "Do not predict death",
    ]
    missing_terms = [term for term in required_terms if term not in skill_md]
    if missing_terms:
        print("Skill validation failed. Missing SKILL.md sections:", file=sys.stderr)
        for term in missing_terms:
            print(f"- {term}", file=sys.stderr)
        return 1
    print("Skill is valid!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
