"""The settings file is this package's own `.env`. A `.env` elsewhere in the repository belongs to another project."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RECORD_LOADS = """
import json, dotenv
paths = []
dotenv.load_dotenv = lambda path, **options: paths.append(str(path))
import analysis.config, ocr.config, webapp.app
print(json.dumps(paths))
"""


def test_every_import_time_load_reads_the_package_env_file():
    result = subprocess.run([sys.executable, "-c", RECORD_LOADS], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[-1]) == [str(ROOT / ".env")] * 3
