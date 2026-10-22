"""The download writers import without starting the web app.

`balance_forensic_audit.py` writes the statement and package downloads to check what they print. While the writers
lived in `webapp/app.py`, importing them built the Flask app and opened the job store, which created `webapp.db` in
the data folder and marked queued jobs interrupted. Each import here runs in a fresh interpreter with a data folder
that does not exist yet and with the constructors of the Flask app, the job store and its storage made to raise.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PROBE = """
import importlib, json, sys
import flask, webapp.jobs, webapp.storage

def tripwire(name):
    def init(self, *args, **kwargs):
        raise RuntimeError(f"{name} constructed")
    return init

flask.Flask.__init__ = tripwire("Flask")
webapp.jobs.JobStore.__init__ = tripwire("JobStore")
webapp.storage.Storage.__init__ = tripwire("Storage")
importlib.import_module(sys.argv[1])
print(json.dumps("webapp.app" in sys.modules))
"""


def _import(module: str, data_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", "-c", PROBE, module], cwd=ROOT, capture_output=True, text=True,
                          env={**os.environ, "WEBAPP_DATA_DIR": str(data_dir)}, timeout=300)


@pytest.mark.parametrize("module", [
    "webapp.export_view", "webapp.spreadsheet", "webapp.statement_export", "webapp.package_export",
    "balance_forensic_audit",
])
def test_importing_a_download_writer_starts_no_app_and_writes_no_data(module, tmp_path):
    data_dir = tmp_path / "data"
    result = _import(module, data_dir)
    assert result.returncode == 0, result.stderr[-2000:]
    assert json.loads(result.stdout.splitlines()[-1]) is False, "webapp.app was imported"
    assert not data_dir.exists()


def test_the_probe_sees_the_web_app_start(tmp_path):
    result = _import("webapp.app", tmp_path / "data")
    assert result.returncode != 0
    assert "RuntimeError: Flask constructed" in result.stderr
