"""PaddleOCR and the endpoint policy are gone (owner ruling, 2026-10-13: the product uses no model; model-code removal,
slice S5).

The PaddleOCR rung (`ocr/paddle_adapter.py`, `paddle_client.py`, `paddle_config.py`, `paddle_rung.py`,
`paddle_worker.py`), the endpoint allowlist that only model clients consulted (`ocr/endpoint_policy.py`), the Paddle
and research tools and the Paddle fixtures were deleted. Nothing may import them again, in any spelling: absolute,
from-package, relative (resolved against the importing file's package), or a dynamic import by name; a planted import
of each form is caught. No module passes `allow_paddle_ocr=True` or names a Paddle data scope, the ladder takes no
Paddle knob and refuses `force_ocr=True`, and the cache refuses the Paddle partition. Local Tesseract stays.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

BANNED_MODULES = (
    "ocr.paddle_adapter", "ocr.paddle_client", "ocr.paddle_config", "ocr.paddle_rung", "ocr.paddle_worker",
    "ocr.endpoint_policy", "tools.paddle_vast", "tools.paddle_wave", "tools.extraction_quality_census",
    "tools.agreement_census", "tools.p23wave_mutation_table", "tests.paddle_fake_worker",
)
BANNED_PREFIXES = ("tools.p23egate_",)

REMOVED_PATHS = (
    "ocr/paddle_adapter.py", "ocr/paddle_client.py", "ocr/paddle_config.py", "ocr/paddle_rung.py",
    "ocr/paddle_worker.py", "ocr/endpoint_policy.py", "tools/paddle_vast.py", "tools/paddle_wave.py",
    "tools/extraction_quality_census.py", "tools/agreement_census.py", "tools/p23egate_fake_partition.py",
    "tools/p23egate_synthetic_table.py", "tools/p23egate_mutation_table.py", "tools/p23wave_mutation_table.py",
    ".env.paddle.example", "tests/paddle_fake_worker.py", "tests/fixtures/paddle",
)


def _banned(module: str) -> bool:
    return (any(module == name or module.startswith(name + ".") for name in BANNED_MODULES)
            or any(module.startswith(prefix) for prefix in BANNED_PREFIXES))


def _package_of(relative: str) -> list[str]:
    parts = relative[:-3].split("/") if relative.endswith(".py") else relative.split("/")
    return parts[:-1]


def paddle_imports(source: str, relative: str = "module.py") -> list[str]:
    """Every import of a removed Paddle / endpoint-policy module in `source` (a file at `relative`)."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names if _banned(alias.name)]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                package = _package_of(relative)
                base = package[: len(package) - (node.level - 1)] if node.level - 1 <= len(package) else []
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            if _banned(module):
                found.append(module)
            found += [f"{module}.{alias.name}" for alias in node.names if _banned(f"{module}.{alias.name}")]
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if name in {"import_module", "__import__"} and _banned(node.args[0].value):
                found.append(node.args[0].value)
    return found


def _tracked_python_files() -> list[str]:
    try:
        listing = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=ROOT, capture_output=True,
                                 check=True).stdout.decode("utf-8")
        tracked = sorted(path for path in listing.split("\0") if path)
    except (OSError, subprocess.CalledProcessError):  # an extracted tree without git: every file is tracked
        tracked = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*.py")
                         if "__pycache__" not in path.parts)
    assert len(tracked) > 100, "not looking at the repository"
    return tracked


def test_the_paddle_rung_its_tools_and_the_endpoint_policy_are_gone():
    present = [relative for relative in REMOVED_PATHS if (ROOT / relative).exists()]
    assert present == [], present
    assert list((ROOT / "tools").glob("p23egate_*.py")) == []
    assert list((ROOT / "ocr").glob("paddle_*.py")) == []
    for module in BANNED_MODULES:
        assert importlib.util.find_spec(module) is None, module
    # kept: the synthetic page builder deterministic tests use (it imports only ocr.rasterize)
    assert (ROOT / "tests" / "paddle_synthetic.py").is_file()


def test_no_python_file_in_the_tree_imports_a_removed_paddle_module():
    offenders = []
    for relative in _tracked_python_files():
        path = ROOT / relative
        if not path.is_file() or relative == "tests/test_no_paddle.py":
            continue  # this file names the banned modules as data, and imports none of them
        try:
            hits = paddle_imports(path.read_text(encoding="utf-8"), relative)
        except (UnicodeDecodeError, SyntaxError) as exc:
            raise AssertionError(f"{relative} could not be scanned: {type(exc).__name__}")
        if hits:
            offenders.append(f"{relative}: {hits}")
    assert offenders == [], offenders


@pytest.mark.parametrize("relative, planted", [
    ("webapp/x.py", "import ocr.paddle_client\n"),
    ("webapp/x.py", "from ocr import paddle_rung\n"),
    ("webapp/x.py", "from ocr.paddle_config import PADDLE_MODEL_TOKEN\n"),
    ("discovery/x.py", "from ocr.endpoint_policy import classify_endpoint\n"),
    ("ocr/x.py", "from .paddle_worker import main\n"),
    ("ocr/x.py", "from . import endpoint_policy\n"),
    ("analysis/x.py", "from ..ocr import paddle_adapter\n"),
    ("tools/x.py", "from tools.paddle_wave import main\n"),
    ("tools/x.py", "from . import p23egate_fake_partition\n"),
    ("tools/x.py", "import tools.agreement_census as census\n"),
    ("tests/x.py", "from tests.paddle_fake_worker import FakeWorker\n"),
    ("webapp/x.py", "import importlib\nimportlib.import_module('ocr.paddle_rung')\n"),
    ("webapp/x.py", "__import__('ocr.endpoint_policy')\n"),
    ("webapp/x.py", "def f():\n    from ocr.paddle_client import probe\n    return probe\n"),
])
def test_a_planted_paddle_import_is_caught_in_every_form(relative, planted):
    assert paddle_imports(planted, relative), (relative, planted)


@pytest.mark.parametrize("relative, clean", [
    ("tests/x.py", "from tests.paddle_synthetic import build_ledger_page\n"),
    ("ocr/x.py", "from .rasterize import RASTER_VERSION\n"),
    ("ocr/x.py", "from . import local_tesseract\n"),
    ("telemetry/x.py", "from .record import PADDLE_MODEL_TOKENS\nTOKEN = 'paddle-ocr+ppocrv5'\n"),
])
def test_the_scan_does_not_flag_what_stays(relative, clean):
    assert paddle_imports(clean, relative) == []


def test_a_fresh_process_importing_the_entry_points_holds_no_removed_module(tmp_path):
    probe = (
        "import sys\n"
        "import webapp.app, webapp.worker, analyze, batch, parse, corpus_gate, discovery.runner, discovery.cli\n"
        "import telemetry.run_of_record, telemetry.stated_counts, tools.train.provenance\n"
        f"banned = {BANNED_MODULES!r}\n"
        "print(sorted(m for m in sys.modules if any(m == b or m.startswith(b + '.') for b in banned)))\n"
    )
    env = {**os.environ, "WEBAPP_DATA_DIR": str(tmp_path / "data"), "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-B", "-c", probe], capture_output=True, text=True, cwd=ROOT, env=env,
                            timeout=600)
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip().splitlines()[-1] == "[]", result.stdout


# --- no Paddle knob anywhere -------------------------------------------------------------------------------------


def _calls_naming(source: str, keyword: str) -> list[int]:
    """Calls passing `keyword=` anything but the literal False or the caller's own same-named parameter (the
    cache's `cached_ocr` forwards its `allow_paddle_ocr` to `ocr_settings_key`, after refusing True itself)."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg != keyword:
                    continue
                if isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    continue
                if isinstance(kw.value, ast.Name) and kw.value.id == keyword:
                    continue
                lines.append(node.lineno)
    return lines


def test_no_module_passes_a_paddle_knob_or_a_paddle_data_scope():
    """Outside tests, no call passes `allow_paddle_ocr` anything but the literal False, and nothing names
    `paddle_data_scope` at all (the ladder parameter left with the rung)."""
    offenders = []
    for relative in _tracked_python_files():
        if relative.startswith("tests/") or not (ROOT / relative).is_file():
            continue
        source = (ROOT / relative).read_text(encoding="utf-8")
        hits = _calls_naming(source, "allow_paddle_ocr") + _calls_naming(source, "paddle_data_scope")
        tree = ast.parse(source)
        hits += [node.lineno for node in ast.walk(tree)
                 if (isinstance(node, ast.arg) and node.arg == "paddle_data_scope")
                 or (isinstance(node, ast.Name) and node.id == "paddle_data_scope")]
        if hits:
            offenders.append(f"{relative}: {hits}")
    assert offenders == [], offenders


def test_the_ladder_takes_no_paddle_knob_and_refuses_forcing(monkeypatch):
    from ocr.pipeline import FORCED_OCR_REMOVED, parse_statement

    parameters = set(inspect.signature(parse_statement).parameters)
    assert not parameters & {"allow_paddle_ocr", "paddle_data_scope", "dpi"}
    monkeypatch.setattr("ocr.pipeline.inspect_pdf", lambda *a, **k: pytest.fail("nothing may be read"))
    monkeypatch.setattr("ocr.pipeline._native_statement", lambda *a, **k: pytest.fail("nothing may be read"))
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", lambda *a, **k: pytest.fail("nothing may be read"))
    for flags in ({}, {"allow_local_ocr": True}):
        with pytest.raises(ValueError) as refused:
            parse_statement(b"%PDF-1.4", source_file="x.pdf", force_ocr=True, **flags)
        assert str(refused.value) == FORCED_OCR_REMOVED


def test_the_cache_refuses_the_paddle_partition_before_any_read(tmp_path):
    from webapp.artifact_cache import PADDLE_OCR_RETIRED, cached_ocr, ocr_settings_key, open_cache

    with pytest.raises(ValueError) as refused:
        ocr_settings_key(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False, allow_paddle_ocr=True)
    assert str(refused.value) == PADDLE_OCR_RETIRED
    for cache in (None, open_cache(tmp_path / "data")):
        with pytest.raises(ValueError) as refused:
            cached_ocr(b"%PDF-1.4", compute=lambda: pytest.fail("nothing may be computed"), cache=cache,
                       force_ocr=True, allow_visual_ocr=False, allow_paddle_ocr=True)
        assert str(refused.value) == PADDLE_OCR_RETIRED
    assert inspect.signature(ocr_settings_key).parameters["allow_paddle_ocr"].default is False
    assert inspect.signature(cached_ocr).parameters["allow_paddle_ocr"].default is False


def test_the_parse_cli_has_no_dpi_flag(tmp_path, capsys):
    import parse

    with pytest.raises(SystemExit) as raised:
        parse.main([str(tmp_path / "x.pdf"), "--dpi", "300"])
    assert raised.value.code == 2
    assert "--dpi" in capsys.readouterr().err
