import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import get_args

from analysis.flag_groups import FLAG_SETTING_KEYS
from tools import api_contract
from webapp.api import contract
from webapp.api.projection import API_READING, basis_points, cents

ROOT = Path(__file__).resolve().parent.parent

SCHEMA_FINGERPRINTS = {"1.0": "711c978cdef6071429c0ddd21ac16994d0f6fccae432bdcd1d61d9d6b6c3d939"}


def test_the_committed_schema_and_reference_are_generated():
    assert api_contract.SCHEMA_PATH.read_text(encoding="utf-8") == api_contract.schema_text()
    document = api_contract.DOC_PATH.read_text(encoding="utf-8")
    assert document == api_contract.with_reference(document)


def test_the_check_command_passes_on_the_committed_artifacts():
    done = subprocess.run([sys.executable, "-m", "tools.api_contract", "--check"], cwd=ROOT, capture_output=True,
                          text=True, timeout=120)
    assert (done.returncode, done.stderr) == (0, "")


def test_the_schema_is_pinned_to_its_api_version():
    canonical = json.dumps(api_contract.schema_document(), sort_keys=True, separators=(",", ":"))
    assert SCHEMA_FINGERPRINTS[contract.API_VERSION] == hashlib.sha256(canonical.encode()).hexdigest()


def _types(node):
    if isinstance(node, dict):
        kind = node.get("type")
        yield from ([kind] if isinstance(kind, str) else kind or [])
        for value in node.values():
            yield from _types(value)
    elif isinstance(node, list):
        for value in node:
            yield from _types(value)


def test_the_schema_has_no_number_type():
    types = set(_types(api_contract.schema_document()))
    assert "integer" in types and "number" not in types


def test_every_code_has_one_catalog_entry():
    assert set(contract.ERRORS) == set(get_args(contract.ErrorCode))
    assert set(contract.FAILURE_MESSAGES) == set(get_args(contract.FailureCode))
    assert set(get_args(contract.IntakeRefusalCode)) <= set(contract.ERRORS)


def test_the_reading_is_the_owner_defaults():
    expected = {"nsf_carry_over": False, "zelle_true_revenue": True, **{key: True for key in FLAG_SETTING_KEYS}}
    assert dict(API_READING) == expected


def test_money_and_rates_convert_once_to_integers_or_null():
    assert [cents(value) for value in (12, 12.5, 0.005, -0.005, 1e2, None, True, "12", float("nan"),
                                       float("inf"))] == [1200, 1250, 1, -1, 10000, None, None, None, None, None]
    assert [basis_points(value) for value in (8.565, 0, -1.0, float("-inf"))] == [857, 0, None, None]


def _imports(path: Path) -> set[str]:
    package = path.relative_to(ROOT).parent.parts
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package[:len(package) + 1 - node.level] if node.level else ()
            module = ".".join([*base, node.module] if node.module else base)
            names.add(module)
            names.update(f"{module}.{alias.name}" for alias in node.names)
    return names


def test_the_api_package_imports_neither_the_app_nor_the_saved_settings():
    for path in sorted((ROOT / "webapp" / "api").glob("*.py")):
        imported = _imports(path)
        assert not {"webapp.app", "webapp.settings"} & imported, path.name
        assert not any(name.startswith(("webapp.app.", "webapp.settings.")) for name in imported), path.name


def test_the_intake_imports_nothing_of_the_api():
    imported = _imports(ROOT / "webapp" / "intake.py")
    assert [name for name in imported if name == "webapp.api" or name.startswith("webapp.api.")] == []


def test_the_contract_imports_without_flask_or_the_store():
    script = ("import sys; import webapp.api.contract, tools.api_contract; "
              "print(sorted(m for m in ('flask', 'webapp.app', 'webapp.storage', 'webapp.jobs') if m in sys.modules))")
    done = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert (done.returncode, done.stdout.strip()) == (0, "[]")
