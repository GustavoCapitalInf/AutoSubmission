"""The four packages the classifier and the true-revenue pass are split into define nothing in their `__init__.py`.
Each holds one docstring and no code, so a caller imports every name from the module that defines it, and importing
one submodule loads only the modules it reads."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ANALYSIS = Path(__file__).resolve().parent.parent / "analysis"
PACKAGES = ("descriptor", "classification", "true_revenue", "transaction_classifier")


@pytest.mark.parametrize("package", PACKAGES)
def test_the_package_init_holds_one_docstring_and_no_code(package):
    tree = ast.parse((ANALYSIS / package / "__init__.py").read_text(encoding="utf-8"))
    assert ast.get_docstring(tree), f"analysis/{package}/__init__.py has no docstring"
    assert len(tree.body) == 1, f"analysis/{package}/__init__.py holds code besides its docstring"
