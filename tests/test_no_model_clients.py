"""Nothing installs, serves or can import a model, and no production module opens a network client (owner ruling,
2026-10-13: the product uses no model; model-code removal, slice S6). Local Tesseract stays.

N1  Every git-tracked .py file parses (a file that does not is a failure, never a silent skip), and none imports a
    model package or a removed model module in any spelling: absolute, relative (resolved against the file's own
    package), package-submodule (`from ocr import ocr_client`), or by name (`importlib.import_module`, `__import__`).
    No production module imports a generic network client; the one declared use is `tools/train/provenance.py`'s
    `socket.gethostname()`. `vlm/`, `tools/phase3_pair/` and the GPU server are gone. The walk proves itself on a
    scratch copy of the tree with a planted mutant of every form.
N2  A fresh process that imports the entry points and runs one fabricated statement through the web worker and one
    through discovery holds no model module and no third-party network client, and attempts no outbound connection.
    `assert_no_model_module_after` is the helper the other absence checks call.
N3  No production module reads an environment variable named for a model path (`MODEL_ENV_PREFIXES`), in any
    spelling: a literal, a module constant, an alias of `os.environ`, a loop over a list of names, a name built
    from a prefix; a read whose name cannot be resolved fails closed. The declared readers are pinned (the
    data-directory rule's root, the provenance record's knob lists), and so is every model-prefixed NAME a
    production module spells, so a reader that takes the name through a parameter still has to be declared.
    `run.ps1` names only the data-directory mirror.
N6  No requirements file names a model package or adds a package index, and CI installs only those files; CI's
    import step fails when importing the entry points loaded a model module.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "corpus-gate.yml"

#: Model packages: refused in every file, tests included. The first eight are the owner ruling's (the hosted
#: extraction's and the visual OCR client's SDKs, PaddleOCR, the GPU server's and the visual pair's stacks); the
#: rest are the same stack's other packages and another model SDK.
MODEL_PACKAGES = (
    "openai", "google.genai", "google.generativeai", "paddleocr", "paddle", "vllm", "transformers", "torch",
    "torchvision", "accelerate", "peft", "einops", "huggingface_hub", "anthropic",
)
#: First-party model modules the removal deleted (slices S2-S5); `ocr.paddle_*` is a name prefix.
REMOVED_MODULES = (
    "vlm", "tools.phase3_pair", "ocr.ocr_client", "ocr.availability", "ocr.endpoint_policy",
    "ocr.visual_pair_config", "analysis.extract",
)
REMOVED_PREFIXES = ("ocr.paddle_",)
#: Generic network clients: refused in every production (non-test) module.
NETWORK_CLIENTS = (
    "urllib.request", "urllib3", "http.client", "requests", "httpx", "aiohttp", "websocket", "websockets",
    "ftplib", "smtplib", "socket", "xmlrpc.client", "imaplib", "poplib", "nntplib", "telnetlib",
)
#: The third-party ones, which a runtime process must not even hold (the stdlib ones are loaded by libraries).
THIRD_PARTY_NETWORK_CLIENTS = ("urllib3", "requests", "httpx", "aiohttp", "websocket", "websockets")
#: The one declared network-module use, (file, client) -> why.
NETWORK_ALLOWANCES = {
    ("tools/train/provenance.py", "socket"): "socket.gethostname() for the provenance record's host field only",
}
#: Removed in S4 (the visual pair) and S6 (the GPU server and its requirement file).
REMOVED_PATHS = ("vlm", "tools/phase3_pair", "local_ocr_server.py", "serve_local.sh", "requirements-vlm.txt")
#: The P8 entry points: what the web app, the CLIs, the gate, discovery and the provenance tooling import.
ENTRY_POINTS = (
    "webapp.app", "webapp.worker", "analyze", "batch", "parse", "corpus_gate", "discovery.runner", "discovery.cli",
    "telemetry.run_of_record", "telemetry.stated_counts", "tools.train.provenance",
)


def _named(module: str, names) -> bool:
    return any(module == name or module.startswith(name + ".") for name in names)


def is_model_module(module: str) -> bool:
    return (_named(module, MODEL_PACKAGES) or _named(module, REMOVED_MODULES)
            or module.startswith(REMOVED_PREFIXES))


def is_network_client(module: str) -> bool:
    return _named(module, NETWORK_CLIENTS)


def is_production(relative: str) -> bool:
    return not (relative.startswith("tests/") or relative == "conftest.py")


def tracked_python_files(root: Path = ROOT) -> list[str]:
    try:
        listing = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=root, capture_output=True,
                                 check=True).stdout.decode("utf-8")
        return sorted(path for path in listing.split("\0") if path)
    except (OSError, subprocess.CalledProcessError):  # an extracted tree without git: every file is tracked
        return sorted(path.relative_to(root).as_posix() for path in root.rglob("*.py")
                      if "__pycache__" not in path.parts)


# --- N1: imports -----------------------------------------------------------------------------------------------------


def _package_of(relative: str) -> list[str]:
    parts = relative[:-3].split("/") if relative.endswith(".py") else relative.split("/")
    return parts[:-1]  # `pkg/mod.py` and `pkg/__init__.py` both import relative to `pkg`


def _resolve_from(node: ast.ImportFrom, relative: str) -> str:
    if not node.level:
        return node.module or ""
    package = _package_of(relative)
    keep = len(package) - (node.level - 1)
    base = package[:keep] if keep >= 0 else []
    return ".".join(base + ([node.module] if node.module else []))


def _constant_str(node) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _call_name(func) -> str:
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")


def _dotted(node) -> str | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


#: Calls that import the module their first argument names.
DYNAMIC_IMPORTERS = {"import_module", "__import__", "importorskip", "run_module"}
#: Dotted names an attribute chain can reach only after the module was imported somewhere (`import urllib` then
#: `urllib.request.urlopen`); single-word names are not chained, because a local variable may carry them.
_CHAINED = tuple(name for name in MODEL_PACKAGES + REMOVED_MODULES + NETWORK_CLIENTS if "." in name)


def _embedded_programs(tree) -> list[ast.Module]:
    """String constants that are Python programs (a probe a module runs in a subprocess)."""
    programs = []
    for node in ast.walk(tree):
        text = _constant_str(node)
        if text and "\n" in text and ("import" in text or "environ" in text or "getenv" in text):
            try:
                programs.append(ast.parse(text))
            except SyntaxError:
                continue
    return programs


def module_names(tree, relative: str, *, embedded: bool) -> list[tuple[int, str]]:
    """Every module `tree` (the file at `relative`) imports or names to an importer, with its line: each
    `import a.b`, each `from x import y` as both `x` and `x.y` (relative `x` resolved against the file's package),
    each importer call's constant name (and `__import__`'s fromlist), and each dotted chain through a multi-part
    banned name. `embedded` also reads the programs a production module keeps in strings."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = _resolve_from(node, relative)
            if module:
                found.append((node.lineno, module))
            found += [(node.lineno, f"{module}.{alias.name}" if module else alias.name)
                      for alias in node.names if alias.name != "*"]
        elif isinstance(node, ast.Call) and node.args and _call_name(node.func) in DYNAMIC_IMPORTERS:
            name = _constant_str(node.args[0])
            if not name:
                continue
            if name.startswith("."):
                package = _constant_str(node.args[1]) if len(node.args) > 1 else None
                package = package or next((_constant_str(kw.value) for kw in node.keywords if kw.arg == "package"),
                                          None)
                if not package:
                    continue
                try:
                    name = importlib.util.resolve_name(name, package)
                except (ImportError, ValueError):
                    continue
            found.append((node.lineno, name))
            fromlist = [kw.value for kw in node.keywords if kw.arg == "fromlist"] + node.args[3:4]
            for value in fromlist:
                if isinstance(value, (ast.List, ast.Tuple)):
                    found += [(node.lineno, f"{name}.{item}") for item in map(_constant_str, value.elts) if item]
        elif isinstance(node, ast.Attribute):
            dotted = _dotted(node)
            if dotted and _named(dotted, _CHAINED):
                found.append((node.lineno, dotted))
    if embedded:
        for program in _embedded_programs(tree):
            found += [(0, name) for _, name in module_names(program, relative, embedded=False)]
    return found


_SCAN_CACHE: dict[tuple[str, str], dict] = {}


def scan_file(root: Path, relative: str) -> dict[str, list[str]]:
    """N1's findings for one file: `unparsable`, `missing`, `model`, `network` and `allowed` (declared uses)."""
    path = root / relative
    if not path.is_file():
        return {"missing": [relative]}
    source = path.read_bytes()
    key = (relative, hashlib.sha256(source).hexdigest())
    if key not in _SCAN_CACHE:
        try:
            tree = ast.parse(source, filename=relative)
        except (SyntaxError, ValueError) as exc:  # bad syntax, undecodable bytes, a NUL byte
            _SCAN_CACHE[key] = {"unparsable": [f"{relative}: {type(exc).__name__}"]}
        else:
            production = is_production(relative)
            names = sorted(set(module_names(tree, relative, embedded=production)))
            result: dict[str, list[str]] = {"model": [], "network": [], "allowed": []}
            for line, name in names:
                if is_model_module(name):
                    result["model"].append(f"{relative}:{line}: {name}")
                elif production and is_network_client(name):
                    client = next(client for client in NETWORK_CLIENTS if _named(name, (client,)))
                    bucket = "allowed" if (relative, client) in NETWORK_ALLOWANCES else "network"
                    result[bucket].append(f"{relative}:{line}: {name}")
            _SCAN_CACHE[key] = result
    return _SCAN_CACHE[key]


def scan_tree(root: Path, files: list[str]) -> dict[str, list[str]]:
    total = {"unparsable": [], "missing": [], "model": [], "network": [], "allowed": []}
    for relative in files:
        for kind, hits in scan_file(root, relative).items():
            total[kind] += hits
    return total


def test_the_walk_sees_the_whole_repository():
    """The vacuity check: every tracked .py file is listed, tests included (the model packages are refused there
    too), and nothing is filtered out before the scan."""
    files = tracked_python_files()
    assert len(files) > 600, len(files)
    for expected in ("webapp/worker.py", "ocr/pipeline.py", "ocr/local_tesseract.py", "discovery/runner.py",
                     "tools/train/provenance.py", "analysis/currency_default.py", "conftest.py",
                     "tests/test_no_paddle.py"):
        assert expected in files, expected
    assert sum(1 for relative in files if not is_production(relative)) > 200


def test_every_tracked_python_file_parses_and_none_imports_a_model_or_a_network_client():
    scan = scan_tree(ROOT, tracked_python_files())
    assert scan["unparsable"] == [], scan["unparsable"]
    assert scan["missing"] == [], scan["missing"]
    assert scan["model"] == [], scan["model"]
    assert scan["network"] == [], scan["network"]
    allowed = sorted({(hit.split(":", 1)[0], hit.rsplit(": ", 1)[1]) for hit in scan["allowed"]})
    assert allowed == [("tools/train/provenance.py", "socket")], scan["allowed"]
    assert set(allowed) == set(NETWORK_ALLOWANCES)


def test_the_provenance_tool_uses_socket_for_the_host_name_only():
    """The one declared network-module use: a module-level `import socket`, read as `socket.gethostname()` and
    nothing else (no other attribute, no `from socket import`, no use of the bare module)."""
    tree = ast.parse((ROOT / "tools/train/provenance.py").read_bytes())
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
               and any(_named(name, ("socket",)) for name in
                       ([a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]))]
    assert [(type(node).__name__, parents[node] is tree) for node in imports] == [("Import", True)]
    uses = [node for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id == "socket"]
    attributes = sorted({parents[node].attr for node in uses if isinstance(parents[node], ast.Attribute)})
    assert attributes == ["gethostname"]
    assert all(isinstance(parents[node], ast.Attribute) for node in uses)
    assert all(isinstance(parents[parents[node]], ast.Call) for node in uses)


def test_the_removed_model_code_is_gone():
    present = [relative for relative in REMOVED_PATHS if (ROOT / relative).exists()]
    assert present == [], present
    assert list((ROOT / "ocr").glob("paddle_*.py")) == []
    for module in REMOVED_MODULES:
        assert importlib.util.find_spec(module) is None, module


@pytest.mark.parametrize("relative, clean", [
    ("tests/n1_planted.py", "import socket\nimport urllib.request\n"),  # network clients are refused in production
    ("ocr/n1_planted.py", "from .local_tesseract import parse_local_tesseract\n"),
    ("webapp/n1_planted.py", "from urllib.parse import urlsplit\nfrom http import HTTPStatus\n"),
    ("tests/n1_planted.py", "from tests.paddle_synthetic import build_ledger_page\n"),
    ("tests/n1_planted.py", "PLANTED = 'import openai\\n'\n"),  # a test's planted source is data
    ("analysis/n1_planted.py", "from analysis.currency_default import usd_default\n"),
    ("analysis/n1_planted.py", "PATTERN = r'|CRYPTO COM|GEMINI TRUST'\n"),
])
def test_the_scan_does_not_flag_what_stays(relative, clean):
    tree = ast.parse(clean)
    names = module_names(tree, relative, embedded=is_production(relative))
    assert [name for _, name in names if is_model_module(name)] == []
    assert not is_production(relative) or [name for _, name in names if is_network_client(name)] == []


@pytest.fixture(scope="module")
def scratch_tree(tmp_path_factory):
    """A scratch copy of every tracked .py file (the real tree is never written)."""
    root = tmp_path_factory.mktemp("no_model_tree")
    files = tracked_python_files()
    for relative in files:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    return root, files


#: (form, file, source, finding kind, finding name)
N1_MUTANTS = [
    ("absolute", "webapp/n1_planted.py", b"import openai\n", "model", "openai"),
    ("absolute, aliased submodule", "analysis/n1_planted.py", b"import google.genai as genai\n", "model",
     "google.genai"),
    ("absolute, lazy in a function", "discovery/n1_planted.py",
     b"def read():\n    from paddleocr import PaddleOCR\n    return PaddleOCR\n", "model", "paddleocr"),
    ("absolute, in a test file", "tests/n1_planted.py", b"import torch\n", "model", "torch"),
    ("relative", "ocr/n1_planted.py", b"from .ocr_client import OcrClient\n", "model", "ocr.ocr_client"),
    ("relative, two levels", "webapp/n1_planted.py", b"from ..analysis import extract\n", "model",
     "analysis.extract"),
    ("package-submodule", "webapp/n1_planted.py", b"from ocr import ocr_client\n", "model", "ocr.ocr_client"),
    ("package-submodule, model SDK", "tests/n1_planted.py", b"from google import genai\n", "model", "google.genai"),
    ("package-submodule, removed prefix", "discovery/n1_planted.py", b"from ocr import paddle_rung\n", "model",
     "ocr.paddle_rung"),
    ("importlib string", "tools/n1_planted.py", b"import importlib\nimportlib.import_module('vlm.pair')\n", "model",
     "vlm.pair"),
    ("__import__ string", "webapp/n1_planted.py", b"__import__('transformers')\n", "model", "transformers"),
    ("embedded probe program", "tools/n1_planted.py", b"PROBE = '''\nimport vllm\nprint(1)\n'''\n", "model", "vllm"),
    ("network client", "webapp/n1_planted.py", b"import requests\n", "network", "requests"),
    ("network client, from-import", "ocr/n1_planted.py", b"from urllib.request import urlopen\n", "network",
     "urllib.request"),
    ("network client, package-submodule", "telemetry/n1_planted.py", b"from http import client\n", "network",
     "http.client"),
    ("network client, attribute chain", "analysis/n1_planted.py",
     b"import urllib\n\ndef fetch():\n    return urllib.request.urlopen('x')\n", "network", "urllib.request.urlopen"),
    ("network client, socket outside the allowance", "webapp/n1_planted.py", b"import socket\n", "network",
     "socket"),
    ("unparsable", "webapp/n1_planted.py", b"def broken(:\n    pass\n", "unparsable", None),
    ("undecodable", "webapp/n1_planted.py", b"NAME = '\xff\xfe'\n", "unparsable", None),
]


@pytest.mark.parametrize("form, relative, source, kind, name", N1_MUTANTS, ids=[m[0] for m in N1_MUTANTS])
def test_n1_catches_a_planted_mutant_of_every_form_on_a_scratch_copy(scratch_tree, form, relative, source, kind,
                                                                     name):
    root, files = scratch_tree
    clean = scan_tree(root, files)
    assert {k: v for k, v in clean.items() if k != "allowed"} == {
        "unparsable": [], "missing": [], "model": [], "network": []}, clean
    planted = root / relative
    assert not planted.exists()
    planted.write_bytes(source)
    try:
        scan = scan_tree(root, sorted(files + [relative]))
    finally:
        planted.unlink()
    hits = scan[kind]
    assert hits and all(hit.startswith(relative + ":") for hit in hits), (form, scan)
    if name is not None:
        assert any(hit.endswith(f": {name}") for hit in hits), (form, hits)
    others = {k: v for k, v in scan.items() if k not in (kind, "allowed")}
    assert others == {k: [] for k in others}, (form, scan)


# --- N2: a running process holds no model module --------------------------------------------------------------------


_N2_PRELUDE = '''
import json as _json, socket as _socket, sys as _sys
RESULT = {}
_ATTEMPTS = []
def _refuse(self, *args, **kwargs):
    _ATTEMPTS.append(type(self).__name__)
    raise OSError("outbound connection refused by the no-model probe")
_socket.socket.connect = _refuse
_socket.socket.connect_ex = _refuse
'''

_N2_EPILOGUE = '''
def _named(module, names):
    return any(module == name or module.startswith(name + ".") for name in names)
print("N2-RESULT " + _json.dumps({{
    "model": sorted(m for m in _sys.modules if _named(m, {model!r}) or m.startswith({prefixes!r})),
    "network_clients": sorted(m for m in _sys.modules if _named(m, {third_party!r})),
    "connections": len(_ATTEMPTS),
    "result": RESULT,
}}, sort_keys=True, default=str))
'''


def modules_loaded_after(snippet: str, data_dir: Path, *, timeout: int = 600) -> dict:
    """Run `snippet` in a fresh interpreter (cwd = the tree, `WEBAPP_DATA_DIR` = `data_dir`, every outbound
    connection refused and counted) and report the model modules and third-party network clients `sys.modules`
    then holds, the connection attempts, and the `RESULT` dict the snippet filled."""
    code = (_N2_PRELUDE + textwrap.dedent(snippet) + "\n"
            + _N2_EPILOGUE.format(model=MODEL_PACKAGES + REMOVED_MODULES, prefixes=REMOVED_PREFIXES,
                                  third_party=THIRD_PARTY_NETWORK_CLIENTS))
    env = {**os.environ, "WEBAPP_DATA_DIR": str(data_dir), "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, capture_output=True, text=True, env=env,
                            timeout=timeout)
    assert result.returncode == 0, result.stderr[-3000:]
    # Only the sentinel line: on the CI runner a library can print a harmless line to stdout first.
    lines = [line for line in result.stdout.splitlines() if line.startswith("N2-RESULT ")]
    assert len(lines) == 1, result.stdout[-2000:]
    return json.loads(lines[0][len("N2-RESULT "):])


def assert_no_model_module_after(snippet: str, data_dir: Path, **kwargs) -> dict:
    """N2's assertion, for any absence check: after `snippet` runs in a fresh process, no model module and no
    third-party network client is loaded and no outbound connection was attempted. Returns the snippet's RESULT."""
    loaded = modules_loaded_after(snippet, data_dir, **kwargs)
    assert loaded["model"] == [], loaded["model"]
    assert loaded["network_clients"] == [], loaded["network_clients"]
    assert loaded["connections"] == 0, loaded["connections"]
    return loaded["result"]


#: A fabricated statement in the Woodforest layout's printed shape (tests/test_woodforest.py's SIMPLE fixture;
#: invented amounts and account number, a 2054 period).
FABRICATED_STATEMENT_LINES = (
    "00131374040126102556",
    "Statement Period: March 01  - March 31, 2054 Page 1 of 6",
    "Account Information & Customer Service 1-(877) 968-7962",
    "P.O. Box 7889 The Woodlands, TX 77387",
    "Visit Us Online at www.woodforest.com",
    "Summary of Accounts",
    "ACCOUNT TYPE AND NUMBER BALANCE FORWARD TOTAL DEBITS TOTAL CREDITS CLOSING BALANCE",
    "Business Simple Checking 1205009515 1,000.00 300.00 500.00 1,200.00",
    "Business Simple Checking 1205009515",
    "Transactions",
    "Date Credits Debits Balance Description",
    "03-02 200.00 800.00 POS DB ONE",
    "03-03 500.00 1,300.00 POS CR TWO",
    "03-04 100.00 1,200.00 POS DB THREE",
)


def test_a_process_running_a_fabricated_statement_through_the_worker_and_discovery_holds_no_model_module(tmp_path):
    imports = "".join(f"import {module}\n" for module in ENTRY_POINTS)
    result = assert_no_model_module_after(imports + f'''
from pathlib import Path
import fitz
from webapp.jobs import JobStore
from webapp.storage import Storage
from webapp.worker import run_job
from discovery.inventory import DedupIndex
from discovery.runner import DiscoveryRunner, MODE_DIGITAL
with fitz.open() as document:
    page = document.new_page()
    for number, line in enumerate({FABRICATED_STATEMENT_LINES!r}):
        page.insert_text((36, 40 + 28 * number), line, fontsize=8)
    document.set_metadata({{}})
    pdf = document.tobytes(no_new_id=True)
scratch = Path({str(tmp_path)!r})
store = JobStore(Storage(scratch / "jobs"))
job = store.create("fabricated.pdf", pdf_bytes=pdf, parse_mode="auto")
run_job(job.id, pdf, "fabricated.pdf", store, False, "auto")
done = store.get(job.id)
RESULT["job"] = [done.status, done.parse_model, done.analysis is not None, done.analysis_error]
(scratch / "corpus" / "BankX").mkdir(parents=True)
(scratch / "corpus" / "BankX" / "statement.pdf").write_bytes(pdf)
row = DiscoveryRunner(scratch / "corpus", mode=MODE_DIGITAL, run_id="n2", sink=None, cache=None,
                      dedup=DedupIndex()).process("BankX/statement.pdf", "BankX")
RESULT["row"] = row.parser_id
''', tmp_path / "data")
    # Not vacuous: the statement went the whole deterministic way in both paths.
    assert result == {"job": ["done", "native-pdf-text", True, None], "row": "woodforest"}, result


@pytest.mark.parametrize("planted, field, expected", [
    ("import types; sys.modules['openai'] = types.ModuleType('openai')", "model", ["openai"]),
    ("import types; sys.modules['vlm.pair'] = types.ModuleType('vlm.pair')", "model", ["vlm.pair"]),
    ("import types; sys.modules['ocr.paddle_rung'] = types.ModuleType('ocr.paddle_rung')", "model",
     ["ocr.paddle_rung"]),
    ("import types; sys.modules['requests'] = types.ModuleType('requests')", "network_clients", ["requests"]),
    ("import socket\ntry:\n    socket.create_connection(('192.0.2.1', 9), timeout=1)\nexcept OSError:\n    pass",
     "connections", 1),
])
def test_the_n2_probe_sees_a_planted_model_module_and_a_connection_attempt(tmp_path, planted, field, expected):
    loaded = modules_loaded_after("import sys\n" + planted + "\n", tmp_path / "data", timeout=120)
    assert loaded[field] == expected, loaded


# --- N3: no model-path environment variable is read ------------------------------------------------------------------


MODEL_ENV_PREFIXES = ("OCR_", "GEMINI_", "HOSTED_EXTRACTION_", "PADDLE_", "VLM_", "VAST_", "VISUAL_PAIR_")
MODEL_ENV_NAME = re.compile(r"^(?:OCR|GEMINI|HOSTED_EXTRACTION|PADDLE|VLM|VAST|VISUAL_PAIR)_[A-Z0-9_]*$")
MODEL_ENV_TOKEN = re.compile(r"\b(?:OCR|GEMINI|HOSTED_EXTRACTION|PADDLE|VLM|VAST|VISUAL_PAIR)_[A-Z0-9_]*")

#: The one model-prefixed variable a production module reads by name: the data-directory rule's root (D12).
ENV_READ_ALLOWANCES = {("ocr/private_artifacts.py", "VISUAL_PAIR_PRIVATE_ROOT")}
#: The only list-driven readers: the provenance record keeps ENV_KNOBS' VALUES and SECRET_KNOBS' set/unset, so its
#: shape stays (D14); nothing reads those variables to decide anything.
LIST_DRIVEN_READERS = {("tools/train/provenance.py", "ENV_KNOBS"), ("tools/train/provenance.py", "SECRET_KNOBS")}
#: The only reader that enumerates the environment instead of naming a variable: the holdout store's `OneDrive*`
#: scan (it refuses a synced folder as a store location).
ENUMERATING_READERS = {"tools/holdout/store.py"}
#: Every model-prefixed NAME a production module spells (a census: a reader that takes its name through a
#: parameter still has to spell the name somewhere, and every spelling is declared with its role).
DECLARED_MODEL_PREFIXED_NAMES = {
    # the data-directory rule's root (D12), read through PRIVATE_ROOT_ENV
    "ocr/private_artifacts.py": {"VISUAL_PAIR_PRIVATE_ROOT"},
    # keys of a run's RECORDED environment mapping (never os.environ), and the tree probe's stage-version key
    "telemetry/run_of_record.py": {"OCR_MODEL", "OCR_BASE_URL", "OCR_NGRAM_SIZE", "OCR_WINDOW_SIZE",
                                   "OCR_STAGE_VERSION"},
    # ENV_KNOBS (values recorded) and SECRET_KNOBS (set/unset recorded), and the tree probe's stage-version key
    "tools/train/provenance.py": {"OCR_BASE_URL", "OCR_MODEL", "OCR_MAX_WORKERS", "OCR_TIMEOUT", "OCR_RETRIES",
                                  "OCR_WINDOW_SIZE", "OCR_NGRAM_SIZE", "GEMINI_MODEL", "GEMINI_ESCALATION_MODEL",
                                  "OCR_API_KEY", "GEMINI_API_KEY", "OCR_STAGE_VERSION"},
    # the OCR stage version's own name, a record key
    "webapp/artifact_cache.py": {"OCR_STAGE_VERSION"},
}
#: run.ps1's data-directory mirror (D12): the one line any launcher may spell a model-prefixed name on.
RUN_PS1_MIRROR = "$privateRoot = if ($env:VISUAL_PAIR_PRIVATE_ROOT) { $env:VISUAL_PAIR_PRIVATE_ROOT } else {"
#: How a shell script, a PowerShell script or a workflow uses an environment variable.
LAUNCHER_ENV_USE = re.compile(
    r"(?:\$\{?|\$env:|\benv\.|\bexport\s+|\bset\s+|[\"'])(?:OCR|GEMINI|HOSTED_EXTRACTION|PADDLE|VLM|VAST|VISUAL_PAIR)_"
    r"|^\s*(?:OCR|GEMINI|HOSTED_EXTRACTION|PADDLE|VLM|VAST|VISUAL_PAIR)_[A-Z0-9_]*\s*[=:]", re.MULTILINE)


def _model_env_name(name: str, *, prefix: bool = False) -> bool:
    if prefix:  # a name built from `name` + something: it may complete to a model prefix
        return bool(name) and any(name.startswith(p) or p.startswith(name) for p in MODEL_ENV_PREFIXES)
    return name.startswith(MODEL_ENV_PREFIXES)


def _module_constants(tree) -> tuple[dict[str, str], dict[str, tuple[str, ...]], dict[str, tuple[str, int]]]:
    """Module-level string constants, string lists/tuples, and first-party from-imports (name -> (module, level))."""
    strings, lists, imported = {}, {}, {}
    for node in tree.body:
        targets, value = [], None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported[alias.asname or alias.name] = (node.module or "", node.level, alias.name)
            continue
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            if _constant_str(value) is not None:
                strings[target.id] = value.value
            elif isinstance(value, (ast.List, ast.Tuple)) and value.elts and \
                    all(_constant_str(e) is not None for e in value.elts):
                lists[target.id] = tuple(e.value for e in value.elts)
    return strings, lists, imported


def _imported_constant(root: Path, relative: str, spec) -> str | None:
    module, level, name = spec
    if level:
        package = _package_of(relative)
        keep = len(package) - (level - 1)
        module = ".".join((package[:keep] if keep >= 0 else []) + ([module] if module else []))
    base = root.joinpath(*module.split(".")) if module else root
    for path in (base.with_suffix(".py"), base / "__init__.py"):
        if path.is_file():
            try:
                strings, _, _ = _module_constants(ast.parse(path.read_bytes()))
            except (SyntaxError, ValueError):
                return None
            return strings.get(name)
    return None


def environment_reads(source, relative: str, root: Path = ROOT) -> list[tuple]:
    """Every environment access in `source` (the file at `relative`): (line, kind, names, via). `kind` is `name`
    (a literal or a resolved constant), `prefix` (a name built from a literal head), `list` (a loop over a list of
    names; `via` names the list), `unresolved` (fails closed) or `enumerate` (the whole environment walked)."""
    tree = source if isinstance(source, ast.AST) else ast.parse(source)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    strings, lists, imported = _module_constants(tree)
    os_names, environ_names, getenv_names, dotenv_names = set(), set(), set(), {"dotenv_values"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            os_names |= {alias.asname or "os" for alias in node.names if alias.name == "os"}
        elif isinstance(node, ast.ImportFrom) and node.module == "os" and not node.level:
            environ_names |= {alias.asname or alias.name for alias in node.names
                              if alias.name in {"environ", "environb"}}
            getenv_names |= {alias.asname or alias.name for alias in node.names
                             if alias.name in {"getenv", "getenvb", "putenv", "unsetenv"}}
        elif isinstance(node, ast.ImportFrom) and node.module == "dotenv":
            dotenv_names |= {alias.asname or alias.name for alias in node.names if alias.name == "dotenv_values"}
    aliases: set[str] = set()

    def is_env(node) -> bool:
        if isinstance(node, ast.Attribute) and node.attr in {"environ", "environb"}:
            return isinstance(node.value, ast.Name) and node.value.id in os_names
        return isinstance(node, ast.Name) and node.id in environ_names | aliases

    def env_shaped(node) -> bool:
        """The environment itself, a copy of it, or the `.env` file's values: what an alias may be bound to."""
        if is_env(node):
            return True
        if isinstance(node, ast.IfExp):
            return env_shaped(node.body) or env_shaped(node.orelse)
        if isinstance(node, ast.BoolOp):
            return any(env_shaped(value) for value in node.values)
        if isinstance(node, ast.Dict):
            return any(key is None and env_shaped(value) for key, value in zip(node.keys, node.values))
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in dotenv_names:
                return True
            if name in {"dict", "MappingProxyType", "ChainMap"}:
                return any(env_shaped(arg) for arg in node.args)
            if name == "copy" and isinstance(node.func, ast.Attribute):
                return env_shaped(node.func.value)
        return False

    while True:  # aliases of aliases
        before = len(aliases)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) and node.value is not None \
                    and env_shaped(node.value):
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    aliases |= {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}
        if len(aliases) == before:
            break

    def loop_iterable(name_node):
        node = name_node
        while node in parents:
            node = parents[node]
            generators = node.generators if isinstance(
                node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)) else []
            for generator in generators:
                if isinstance(generator.target, ast.Name) and generator.target.id == name_node.id:
                    return generator.iter
            if isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.target, ast.Name) \
                    and node.target.id == name_node.id:
                return node.iter
        return None

    def resolve(key) -> tuple[str, tuple[str, ...], str | None]:
        text = _constant_str(key)
        if text is not None:
            return "name", (text,), None
        if isinstance(key, ast.JoinedStr):
            head = _constant_str(key.values[0]) if key.values else None
            return ("prefix", (head,), None) if head else ("unresolved", (), None)
        if isinstance(key, ast.BinOp) and isinstance(key.op, ast.Add):
            kind, names, _ = resolve(key.left)
            return ("prefix", names, None) if kind in {"name", "prefix"} else ("unresolved", (), None)
        if isinstance(key, ast.Name):
            iterable = loop_iterable(key)
            if iterable is not None:
                if isinstance(iterable, ast.Name) and iterable.id in lists:
                    return "list", lists[iterable.id], iterable.id
                if isinstance(iterable, (ast.List, ast.Tuple)) and all(_constant_str(e) for e in iterable.elts):
                    return "list", tuple(e.value for e in iterable.elts), "<literal>"
                return "unresolved", (), None
            if key.id in strings:
                return "name", (strings[key.id],), None
            if key.id in imported:
                value = _imported_constant(root, relative, imported[key.id])
                if value is not None:
                    return "name", (value,), None
        return "unresolved", (), None

    reads = []

    def record(node, key):
        reads.append((node.lineno, *resolve(key)))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and env_shaped(func.value):
                if func.attr in {"get", "pop", "setdefault", "__getitem__", "__contains__"} and node.args:
                    record(node, node.args[0])
                elif func.attr in {"items", "keys", "values"}:
                    reads.append((node.lineno, "enumerate", (), None))
            elif (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                  and func.value.id in os_names and func.attr in {"getenv", "getenvb", "putenv", "unsetenv"}) \
                    or (isinstance(func, ast.Name) and func.id in getenv_names):
                if node.args:
                    record(node, node.args[0])
            elif isinstance(func, ast.Name) and func.id in {"sorted", "list", "set", "tuple", "frozenset", "iter",
                                                            "enumerate", "filter", "map"} \
                    and any(env_shaped(arg) for arg in node.args):
                reads.append((node.lineno, "enumerate", (), None))
        elif isinstance(node, ast.Subscript) and env_shaped(node.value):
            record(node, node.slice)
        elif isinstance(node, ast.Compare):
            lefts = [node.left, *node.comparators[:-1]]
            for left, op, right in zip(lefts, node.ops, node.comparators):
                if isinstance(op, (ast.In, ast.NotIn)) and env_shaped(right):
                    record(node, left)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)) and env_shaped(node.iter):
            reads.append((getattr(node, "lineno", getattr(node.iter, "lineno", 0)), "enumerate", (), None))
    return sorted(reads, key=lambda read: (read[0], read[1], read[2]))


_N3_CACHE: dict[tuple[str, str, str], tuple[list[tuple], set[str]]] = {}


def _n3_file(root: Path, relative: str) -> tuple[list[tuple], set[str]]:
    """(environment reads, model-prefixed names spelled) of one production module, embedded programs included."""
    source = (root / relative).read_bytes()
    key = (str(root), relative, hashlib.sha256(source).hexdigest())
    if key not in _N3_CACHE:
        tree = ast.parse(source, filename=relative)  # N1 fails on a file that does not parse
        reads, spelled = [], set()
        for program in [tree, *_embedded_programs(tree)]:
            reads += environment_reads(program, relative, root)
            for node in ast.walk(program):
                text = _constant_str(node)
                if text is not None and MODEL_ENV_NAME.match(text):
                    spelled.add(text)
                elif isinstance(node, ast.JoinedStr) and node.values and _constant_str(node.values[0]) \
                        and _model_env_name(node.values[0].value, prefix=True) and "_" in node.values[0].value:
                    spelled.add(node.values[0].value + "{...}")
        _N3_CACHE[key] = (reads, spelled)
    return _N3_CACHE[key]


def n3_findings(root: Path, files: list[str]) -> dict:
    """N3 over the production modules of `root`: offending reads, list-driven readers, enumerating readers, the
    declared reads that were used, and the census of model-prefixed names (embedded probe programs included)."""
    findings = {"offenders": [], "list_driven": set(), "enumerating": set(), "allowed": set(), "names": {}}
    for relative in files:
        if not is_production(relative):
            continue
        reads, spelled = _n3_file(root, relative)
        if spelled:
            findings["names"][relative] = set(spelled)
        for line, kind, names, via in reads:
            if kind == "enumerate":
                findings["enumerating"].add(relative)
            elif kind == "unresolved":
                findings["offenders"].append(f"{relative}:{line}: an environment read whose name is not "
                                             f"resolvable (fails closed)")
            elif kind == "list":
                findings["list_driven"].add((relative, via))
                if (relative, via) not in LIST_DRIVEN_READERS:
                    findings["offenders"].append(f"{relative}:{line}: an undeclared list-driven read ({via})")
            else:
                for name in names:
                    if not _model_env_name(name, prefix=kind == "prefix"):
                        continue
                    if kind == "name" and (relative, name) in ENV_READ_ALLOWANCES:
                        findings["allowed"].add((relative, name))
                    else:
                        findings["offenders"].append(f"{relative}:{line}: reads {name!r} ({kind})")
    return findings


def test_the_reader_scan_sees_the_known_readers():
    """The vacuity check: the scan finds the readers that exist, in each spelling they use."""
    reads = environment_reads((ROOT / "webapp/storage.py").read_bytes(), "webapp/storage.py")
    assert any(kind == "name" and names == ("WEBAPP_DATA_DIR",) for _, kind, names, _ in reads)
    reads = environment_reads((ROOT / "analysis/config.py").read_bytes(), "analysis/config.py")
    assert {names for _, kind, names, _ in reads if kind == "name"} >= {
        ("WITHHOLDING_DENOMINATOR_MODE",), ("RECONSTRUCTION_MODE",)}
    reads = environment_reads((ROOT / "ocr/private_artifacts.py").read_bytes(), "ocr/private_artifacts.py")
    assert [(kind, names) for _, kind, names, _ in reads] == [("name", ("VISUAL_PAIR_PRIVATE_ROOT",))]
    reads = environment_reads((ROOT / "tools/train/provenance.py").read_bytes(), "tools/train/provenance.py")
    assert {(kind, via) for _, kind, _, via in reads if kind == "list"} == {("list", "ENV_KNOBS"),
                                                                            ("list", "SECRET_KNOBS")}


def test_no_production_module_reads_a_model_path_environment_variable():
    findings = n3_findings(ROOT, tracked_python_files())
    assert findings["offenders"] == [], findings["offenders"]
    assert findings["allowed"] == ENV_READ_ALLOWANCES
    assert findings["list_driven"] == LIST_DRIVEN_READERS
    assert findings["enumerating"] == ENUMERATING_READERS
    assert findings["names"] == DECLARED_MODEL_PREFIXED_NAMES


def test_run_of_record_reads_a_recorded_mapping_not_the_environment():
    """`telemetry/run_of_record.py` spells four OCR_ names, as keys of a run's RECORDED environment (the
    provenance record), read through `_env_str(env, ...)`; it does not import `os` and touches no environment."""
    tree = ast.parse((ROOT / "telemetry/run_of_record.py").read_bytes())
    assert environment_reads(tree, "telemetry/run_of_record.py") == []
    assert not any(isinstance(node, ast.Import) and any(a.name == "os" for a in node.names)
                   or isinstance(node, ast.ImportFrom) and node.module == "os" for node in ast.walk(tree))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and _call_name(node.func) == "_env_str"]
    assert sorted(_constant_str(call.args[1]) for call in calls) == [
        "OCR_BASE_URL", "OCR_MODEL", "OCR_NGRAM_SIZE", "OCR_WINDOW_SIZE"]
    assert all(isinstance(call.args[0], ast.Name) and call.args[0].id == "env" for call in calls)
    helper = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_env_str")
    assert [arg.arg for arg in helper.args.args] == ["env", "key", "default"]


def test_the_gemini_trust_classification_pattern_is_untouched():
    """`GEMINI TRUST` in the classification registry is a crypto exchange's name in a classification pattern, not
    a model and not an environment read (D14): it stays exactly as it is."""
    source = (ROOT / "analysis/classification_registry.py").read_text(encoding="utf-8")
    assert source.count("GEMINI") == 1
    assert '    r"|CRYPTO COM|GEMINI TRUST"\n' in source.replace("\r\n", "\n")
    assert environment_reads(source, "analysis/classification_registry.py") == []


def _launcher_findings(root: Path, launchers: list[str]) -> list[str]:
    found = []
    for relative in launchers:
        text = (root / relative).read_text(encoding="utf-8").replace("\r\n", "\n")
        for number, line in enumerate(text.split("\n"), 1):
            if relative == "run.ps1":
                tokens = set(MODEL_ENV_TOKEN.findall(line))
                if tokens and not (line.strip() == RUN_PS1_MIRROR and tokens == {"VISUAL_PAIR_PRIVATE_ROOT"}):
                    found.append(f"{relative}:{number}: {sorted(tokens)}")
            elif LAUNCHER_ENV_USE.search(line):
                found.append(f"{relative}:{number}")
    return found


def _launchers(root: Path) -> list[str]:
    found = ["run.ps1"]
    for pattern in ("*.ps1", "*.sh", "tools/**/*.ps1", "tools/**/*.sh", ".github/workflows/*.yml"):
        found += [path.relative_to(root).as_posix() for path in root.glob(pattern) if path.is_file()]
    return sorted(set(found))


def test_the_launchers_name_no_model_switch_and_run_ps1_only_the_data_directory_mirror():
    launchers = _launchers(ROOT)
    assert {"run.ps1", ".github/workflows/corpus-gate.yml", "tools/train/coldrun.sh"} <= set(launchers), launchers
    assert _launcher_findings(ROOT, launchers) == []
    # The data-directory rule's mirror stays (D12).
    text = (ROOT / "run.ps1").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert [line.strip() for line in text.split("\n")].count(RUN_PS1_MIRROR) == 1


#: (form, source, expected finding)
N3_MUTANTS = [
    ("literal get", "import os\nVALUE = os.environ.get('OCR_REMOTE_OPT_IN')\n", "reads 'OCR_REMOTE_OPT_IN' (name)"),
    ("getenv", "import os\nKEY = os.getenv('OCR_API_KEY')\n", "reads 'OCR_API_KEY' (name)"),
    ("from os import getenv", "from os import getenv\nKEY = getenv('GEMINI_API_KEY', '')\n",
     "reads 'GEMINI_API_KEY' (name)"),
    ("subscript", "import os\nKEY = os.environ['HOSTED_EXTRACTION_OPT_IN']\n", "reads 'HOSTED_EXTRACTION_OPT_IN'"),
    ("membership", "import os\nON = 'PADDLE_REMOTE_OPT_IN' in os.environ\n", "reads 'PADDLE_REMOTE_OPT_IN'"),
    ("from os import environ", "from os import environ as e\nX = e.get('VLM_ENDPOINT')\n", "reads 'VLM_ENDPOINT'"),
    ("alias", "import os\n\ndef f(environ=None):\n    env = os.environ if environ is None else environ\n"
     "    return env.get('VAST_API_KEY')\n", "reads 'VAST_API_KEY'"),
    ("copied alias", "import os\nENV = dict(os.environ)\nX = ENV['OCR_MODEL']\n", "reads 'OCR_MODEL'"),
    ("module constant", "import os\nNAME = 'OCR_ALLOW_VISUAL_PAIR'\nX = os.environ.get(NAME)\n",
     "reads 'OCR_ALLOW_VISUAL_PAIR'"),
    ("f-string head", "import os\n\ndef f(x):\n    return os.environ.get(f'VISUAL_PAIR_{x}')\n",
     "reads 'VISUAL_PAIR_' (prefix)"),
    ("concatenated head", "import os\n\ndef f(x):\n    return os.environ.get('GEMINI_' + x)\n",
     "reads 'GEMINI_' (prefix)"),
    ("data-directory root outside its module", "import os\nX = os.environ.get('VISUAL_PAIR_PRIVATE_ROOT')\n",
     "reads 'VISUAL_PAIR_PRIVATE_ROOT'"),
    ("undeclared list-driven read", "import os\nKNOBS = ['POPPLER_PATH']\nX = {k: os.environ.get(k) for k in KNOBS}\n",
     "undeclared list-driven read (KNOBS)"),
    ("unresolvable name", "import os\n\ndef f(name):\n    return os.environ.get(name)\n", "not resolvable"),
    ("dotenv file read", "from dotenv import dotenv_values\nX = dotenv_values('.env')['OCR_BASE_URL']\n",
     "reads 'OCR_BASE_URL'"),
    ("embedded probe program", "PROBE = '''\nimport os\nprint(os.environ.get(\"OCR_TIMEOUT\"))\n'''\n",
     "reads 'OCR_TIMEOUT'"),
]


@pytest.mark.parametrize("form, source, expected", N3_MUTANTS, ids=[m[0] for m in N3_MUTANTS])
def test_n3_catches_a_planted_model_path_read_on_a_scratch_copy(scratch_tree, form, source, expected):
    root, files = scratch_tree
    relative = "webapp/n3_planted.py"
    planted = root / relative
    planted.write_text(source, encoding="utf-8")
    try:
        findings = n3_findings(root, sorted(files + [relative]))
    finally:
        planted.unlink()
    assert len(findings["offenders"]) == 1, (form, findings["offenders"])
    assert findings["offenders"][0].startswith(relative) and expected in findings["offenders"][0], findings


def test_n3_catches_a_planted_enumerating_reader_and_an_undeclared_name():
    tree = ast.parse("import os\nFOUND = [k for k in os.environ if k.startswith('X')]\n")
    assert [kind for _, kind, _, _ in environment_reads(tree, "webapp/x.py")] == ["enumerate"]
    tree = ast.parse("import os\nSWITCHES = {k: v for k, v in os.environ.items()}\n")
    assert [kind for _, kind, _, _ in environment_reads(tree, "webapp/x.py")] == ["enumerate"]


@pytest.mark.parametrize("line", [
    '$env:OCR_ALLOW_VISUAL_PAIR = "1"',
    '$retired = "OCR_REMOTE_OPT_IN", "HOSTED_EXTRACTION_OPT_IN"',
    '[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "x", "Process")',
    '$root2 = $env:VISUAL_PAIR_PRIVATE_ROOT',  # the mirror's name, off the mirror line
])
def test_n3_catches_a_planted_run_ps1_line(tmp_path, line):
    shutil.copyfile(ROOT / "run.ps1", tmp_path / "run.ps1")
    assert _launcher_findings(tmp_path, ["run.ps1"]) == []
    with open(tmp_path / "run.ps1", "a", encoding="utf-8") as handle:
        handle.write("\n" + line + "\n")
    found = _launcher_findings(tmp_path, ["run.ps1"])
    assert len(found) == 1 and found[0].startswith("run.ps1:"), found


@pytest.mark.parametrize("line", [
    "export OCR_BASE_URL=http://localhost:8000/v1", 'OCR_API_KEY="EMPTY" python x.py', "echo ${GEMINI_MODEL}",
    "  HOSTED_EXTRACTION_OPT_IN: '1'",
])
def test_n3_catches_a_planted_model_switch_in_another_launcher(tmp_path, line):
    (tmp_path / "launch.sh").write_text("#!/bin/sh\n" + line + "\n", encoding="utf-8")
    assert _launcher_findings(tmp_path, ["launch.sh"]) == ["launch.sh:2"]


# --- N6: requirement files and the CI install set --------------------------------------------------------------------


#: Distribution names (PEP 503 normalised) no requirements file may name.
MODEL_DISTRIBUTIONS = {
    "openai", "google-genai", "google-generativeai", "paddleocr", "paddlepaddle", "paddlepaddle-gpu", "torch",
    "torchvision", "torchaudio", "transformers", "accelerate", "vllm", "einops", "peft", "huggingface-hub",
    "anthropic",
}
_INCLUDE = re.compile(r"^(?:-r|-c|--requirement|--constraint)\s*=?\s*(\S+)")
_INDEX = re.compile(r"^(?:-i|--index-url|--extra-index-url|-f|--find-links)\b")
_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_findings(directory: Path, files: list[str] | None = None) -> tuple[list[str], dict[str, set[str]]]:
    """(problems, names per file) over `directory`'s requirements*.txt (or `files`) and every file they include."""
    queue = list(files) if files is not None else sorted(p.name for p in directory.glob("requirements*.txt"))
    seen, problems, names = set(), [], {}
    while queue:
        name = queue.pop(0)
        if name in seen:
            continue
        seen.add(name)
        path = directory / name
        if not path.is_file():
            problems.append(f"{name}: included but missing")
            continue
        names[name] = set()
        for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = re.sub(r"(^|\s)#.*$", "", raw).strip()
            if not line:
                continue
            include = _INCLUDE.match(line)
            if include:
                queue.append(include.group(1))
                continue
            if _INDEX.match(line):
                problems.append(f"{name}:{number}: adds a package index")
                continue
            if line.startswith("-"):
                continue
            match = _NAME.match(line)
            if match:
                distribution = _normalise(match.group(1))
                names[name].add(distribution)
                if distribution in MODEL_DISTRIBUTIONS:
                    problems.append(f"{name}:{number}: names {distribution}")
    return problems, names


def _ci_install_files() -> list[str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    installs = [line.strip() for line in text.splitlines()
                if re.match(r"\s*(?:run:\s*)?(?:python -m )?pip install\b", line)]
    assert len(installs) == 3, installs  # pip itself, the runtime files, the dev file
    files = []
    for line in installs:
        arguments = line.split("install", 1)[1].split()
        assert arguments in (["--upgrade", "pip"],) or all(
            arg == "-r" or arg.endswith(".txt") for arg in arguments), line  # nothing installed by name
        files += [arg for arg in arguments if arg.endswith(".txt")]
    return files


def test_no_requirements_file_names_a_model_package_or_adds_an_index():
    problems, names = requirement_findings(ROOT)
    assert problems == [], problems
    assert {"requirements.txt", "requirements-analysis.txt", "requirements-dev.txt", "requirements-local.txt"} \
        <= set(names), names
    # The local-only extras are the one measurement package (the GPU server's stack left with it).
    assert names["requirements-local.txt"] == {"psutil"}


def test_ci_installs_only_requirement_files_and_none_names_a_model_package():
    files = _ci_install_files()
    assert files == ["requirements.txt", "requirements-analysis.txt", "requirements-dev.txt"], files
    problems, names = requirement_findings(ROOT, files)
    assert problems == [], problems
    assert set(names) == set(files)  # requirements-dev.txt includes the two runtime files
    assert not set().union(*names.values()) & MODEL_DISTRIBUTIONS


@pytest.mark.parametrize("files, expected", [
    ({"requirements-x.txt": "torch==2.9.1+rocm6.3\n"}, "requirements-x.txt:1: names torch"),
    ({"requirements-x.txt": "flask\nGoogle_GenAI>=1.0  # normalised\n"}, "requirements-x.txt:2: names google-genai"),
    ({"requirements-x.txt": "-r more.txt\n", "more.txt": "OpenAI\n"}, "more.txt:1: names openai"),
    ({"requirements-x.txt": "transformers[torch]==4.57.1\n"}, "requirements-x.txt:1: names transformers"),
    ({"requirements-x.txt": "vllm @ https://example.invalid/vllm.whl\n"}, "requirements-x.txt:1: names vllm"),
    ({"requirements-x.txt": "--extra-index-url https://download.pytorch.org/whl/rocm6.3\n"},
     "requirements-x.txt:1: adds a package index"),
])
def test_n6_catches_a_planted_model_requirement(tmp_path, files, expected):
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    problems, _ = requirement_findings(tmp_path)
    assert problems == [expected], problems


def _ci_import_check() -> str:
    """The program CI's import step runs (the heredoc body of its `run:` block)."""
    text = WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")
    opener = "python - <<'EOF'\n"
    assert text.count(opener) == 1
    start = text.index(opener) + len(opener)
    end = re.compile(r"^ *EOF$", re.MULTILINE).search(text, start).start()
    return textwrap.dedent(text[start:end])


def test_the_ci_import_step_refuses_every_model_package_after_importing_the_entry_points(tmp_path):
    script = _ci_import_check()
    tree = ast.parse(script)
    imported = [alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names]
    assert set(ENTRY_POINTS) <= set(imported), imported
    banned = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                  and getattr(node.targets[0], "id", "") == "BANNED")
    assert tuple(_constant_str(e) for e in banned.elts) == MODEL_PACKAGES + ("vlm",)
    env = {**os.environ, "WEBAPP_DATA_DIR": str(tmp_path / "data"), "PYTHONDONTWRITEBYTECODE": "1"}
    clean = subprocess.run([sys.executable, "-B", "-"], input=script, cwd=ROOT, capture_output=True, text=True,
                           env=env, timeout=600)
    assert clean.returncode == 0, clean.stderr[-2000:]
    planted = subprocess.run(
        [sys.executable, "-B", "-"], input="import sys, types\nsys.modules['vlm'] = types.ModuleType('vlm')\n" + script,
        cwd=ROOT, capture_output=True, text=True, env=env, timeout=600)
    assert planted.returncode != 0 and "vlm" in planted.stderr, (planted.returncode, planted.stderr[-500:])
