"""tools/train/winrun.py — the Windows job-object runner the train's instruments
run under on this host. Three behaviours, each the guard it stands in for:
the memory cap turns a runaway allocation into a CHILD failure (RLIMIT_AS),
the timeout terminates the job and reports 124 (timeout), and an ordinary
command's exit code passes through unchanged. Windows only, by construction."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WINRUN = ROOT / "tools" / "train" / "winrun.py"

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Job Objects are Windows-only")


def _winrun(tmp_path: Path, *options: str, command: list[str]) -> tuple[int, dict, subprocess.CompletedProcess]:
    log = tmp_path / "winrun.jsonl"
    completed = subprocess.run(
        [sys.executable, str(WINRUN), "--log", str(log), "--floor-gb", "0", *options, "--", *command],
        capture_output=True, text=True, timeout=120,
    )
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, completed.stderr
    return completed.returncode, json.loads(lines[0]), completed


def test_an_ordinary_command_passes_its_exit_code_through(tmp_path: Path) -> None:
    code, record, _ = _winrun(tmp_path, "--cap-gb", "1", "--timeout", "60",
                              command=[sys.executable, "-c", "import sys; sys.exit(3)"])
    assert code == 3
    assert record["exit"] == 3 and record["timed_out"] is False
    assert record["processes"] >= 1 and record["peak_job_mb"] > 0


def test_the_cap_turns_a_runaway_allocation_into_a_child_failure(tmp_path: Path) -> None:
    # 2 GB against a 0.5 GB cap: the allocation must FAIL inside the child as a
    # MemoryError (exit 1) — never succeed, never take the host. (Windows
    # reports the refused charge in PeakJobMemoryUsed, so the peak is not the
    # assertion; the child's failure and its silence are.)
    code, record, completed = _winrun(
        tmp_path, "--cap-gb", "0.5", "--timeout", "60",
        command=[sys.executable, "-c", "b = bytearray(2 * 1024 ** 3); print('ALLOCATED', len(b))"])
    assert code != 0 and record["timed_out"] is False
    assert "MemoryError" in completed.stderr
    assert "ALLOCATED" not in completed.stdout


def test_the_timeout_terminates_the_job_and_reports_124(tmp_path: Path) -> None:
    code, record, _ = _winrun(tmp_path, "--cap-gb", "1", "--timeout", "2",
                              command=[sys.executable, "-c", "import time; time.sleep(60)"])
    assert code == 124 and record["timed_out"] is True
    assert record["wall_s"] < 30
