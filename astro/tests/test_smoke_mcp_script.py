from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "smoke_mcp_client.py"


def test_smoke_mcp_client_script_runs_and_passes(tmp_path: Path):
    assert SCRIPT.exists(), f"missing smoke script at {SCRIPT}"

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    env.setdefault("PYTHONIOENCODING", "utf-8")

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--output-dir", str(tmp_path)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, (
        f"smoke script failed (rc={completed.returncode})\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert "RESULT: PASS" in completed.stdout
    assert "FAIL" not in completed.stdout.replace("RESULT: PASS", "")
    json_reports = list(tmp_path.glob("rpt-*.json"))
    assert json_reports, "expected at least one report file in output_dir"
