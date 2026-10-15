"""The visual pair is gone (owner ruling, 2026-10-13: the product uses no model; model-code removal, slice S4).

`vlm/` (the dots.mocr proposer + Qwen reviewer pair, its Vast GPU, LoRA and judgment tooling), its settings module
`ocr/visual_pair_config.py`, the pair tools (`tools/phase3_pair/`, `tools/vlm_*.py`) and `.env.visual-pair.example`
were deleted. Nothing may import them again, in any spelling: absolute, from-package, relative (resolved against the
importing file's package), or a dynamic import by name. A planted import of each form is caught. The owner's currency
rule that lived in `vlm/currency.py` is `analysis/currency_default.py` now (tests/test_currency_default.py).
"""
from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Module names that belong to the removed visual pair. A module is banned when it equals one of these or is a
#: submodule of one; `tools.vlm_` is a name prefix (the seven `tools/vlm_*.py` tools).
BANNED_MODULES = ("vlm", "ocr.visual_pair_config", "tools.phase3_pair")
BANNED_PREFIXES = ("tools.vlm_",)

REMOVED_PATHS = ("vlm", "ocr/visual_pair_config.py", "tools/phase3_pair", ".env.visual-pair.example",
                 "tools/vlm_ceiling.py", "tools/vlm_label_audit.py", "tools/vlm_label_review.py",
                 "tools/vlm_page_lengths.py", "tools/vlm_render_silver.py", "tools/vlm_train_lora.py",
                 "tools/vlm_vast.py")


def _banned(module: str) -> bool:
    return (any(module == name or module.startswith(name + ".") for name in BANNED_MODULES)
            or any(module.startswith(prefix) for prefix in BANNED_PREFIXES))


def _package_of(relative: str) -> list[str]:
    parts = relative[:-3].split("/") if relative.endswith(".py") else relative.split("/")
    return parts[:-1]  # `pkg/mod.py` and `pkg/__init__.py` both import relative to `pkg`


def visual_pair_imports(source: str, relative: str = "module.py") -> list[str]:
    """Every import of a removed visual-pair module in `source` (a file at `relative`). Empty when clean."""
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


def test_the_visual_pair_and_its_tools_are_gone():
    present = [relative for relative in REMOVED_PATHS if (ROOT / relative).exists()]
    assert present == [], present
    assert list((ROOT / "tools").glob("vlm_*.py")) == []
    for module in ("vlm", "ocr.visual_pair_config", "tools.phase3_pair"):
        assert importlib.util.find_spec(module) is None, module


def test_no_python_file_in_the_tree_imports_the_visual_pair():
    offenders = []
    for relative in _tracked_python_files():
        path = ROOT / relative
        if not path.is_file():
            continue
        if relative == "tests/test_no_visual_pair.py":
            continue  # this file names the banned modules as data, and imports none of them
        try:
            hits = visual_pair_imports(path.read_text(encoding="utf-8"), relative)
        except (UnicodeDecodeError, SyntaxError) as exc:
            raise AssertionError(f"{relative} could not be scanned: {type(exc).__name__}")
        if hits:
            offenders.append(f"{relative}: {hits}")
    assert offenders == [], offenders


@pytest.mark.parametrize("relative, planted", [
    ("webapp/x.py", "import vlm\n"),
    ("webapp/x.py", "import vlm.pair_adapter as adapter\n"),
    ("webapp/x.py", "from vlm import pair_adapter\n"),
    ("webapp/x.py", "from vlm.currency import usd_default\n"),
    ("webapp/x.py", "from ocr import visual_pair_config\n"),
    ("webapp/x.py", "from ocr.visual_pair_config import load_visual_pair_settings\n"),
    ("ocr/x.py", "from .visual_pair_config import MODEL_TOKEN\n"),
    ("ocr/x.py", "from . import visual_pair_config\n"),
    ("analysis/x.py", "from ..vlm import currency\n"),
    ("tools/x.py", "from tools.phase3_pair.check_judgment import main\n"),
    ("tools/x.py", "from tools import phase3_pair\n"),
    ("tools/x.py", "from . import vlm_vast\n"),
    ("tests/x.py", "import tools.vlm_ceiling\n"),
    ("webapp/x.py", "import importlib\nimportlib.import_module('vlm.pair')\n"),
    ("webapp/x.py", "__import__('ocr.visual_pair_config')\n"),
    ("webapp/x.py", "def f():\n    from vlm.pair import extract_visual_pair\n    return extract_visual_pair\n"),
])
def test_a_planted_import_of_the_visual_pair_is_caught_in_every_form(relative, planted):
    assert visual_pair_imports(planted, relative), (relative, planted)


@pytest.mark.parametrize("relative, clean", [
    ("analysis/x.py", "from analysis.currency_default import usd_default\n"),
    ("ocr/x.py", "from .private_artifacts import private_artifact_root\n"),
    ("webapp/x.py", "from ocr.document import StatementMarkdown\nVISUAL_PAIR = 'visual-pair-dots-qwen'\n"),
    ("tools/x.py", "import tools.l1s3_surface_census\n"),
])
def test_the_scan_does_not_flag_what_stays(relative, clean):
    assert visual_pair_imports(clean, relative) == []


def test_a_fresh_process_importing_the_entry_points_holds_no_visual_pair_module(tmp_path):
    probe = (
        "import sys\n"
        "import webapp.app, webapp.worker, analyze, batch, parse, corpus_gate, discovery.runner, discovery.cli\n"
        "import telemetry.run_of_record, telemetry.stated_counts, tools.train.provenance\n"
        "banned = ('vlm', 'ocr.visual_pair_config', 'tools.phase3_pair')\n"
        "print(sorted(m for m in sys.modules if any(m == b or m.startswith(b + '.') for b in banned)"
        " or m.startswith('tools.vlm_')))\n"
    )
    env = {**os.environ, "WEBAPP_DATA_DIR": str(tmp_path / "data")}
    result = subprocess.run([sys.executable, "-B", "-c", probe], cwd=ROOT, capture_output=True, text=True,
                            timeout=300, env=env)
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip().splitlines()[-1] == "[]"
