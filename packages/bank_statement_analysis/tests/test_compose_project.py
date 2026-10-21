"""The intern stack keeps its job history across the monorepo move."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("docker") is None, reason="needs the docker CLI")
def test_the_intern_volume_keeps_the_name_it_had_before_the_move():
    env = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
    env["WEBAPP_AUTH_PASSWORD"] = "test-only"
    result = subprocess.run(
        ["docker", "compose", "--env-file", os.devnull, "config", "--format", "json"],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    if result.returncode != 0 and "is not a docker command" in result.stderr:
        pytest.skip("needs Docker Compose v2")
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    assert config["volumes"]["intern-data"]["name"] == "bankstatementanalysis_intern-data"
