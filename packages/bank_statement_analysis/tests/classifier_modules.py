"""Every module of the classifier's and the true-revenue pass's packages, for tests that scan their namespaces.

The classifier and the true-revenue pass live in four packages and in analysis/description_text.py. A test that scans
their module-level objects scans each of these modules, so an object stays in the scan when its name moves from one
module to another.
"""
from __future__ import annotations

import importlib
import importlib.util
import pkgutil
from types import ModuleType

PACKAGES = ("analysis.descriptor", "analysis.classification", "analysis.true_revenue", "analysis.transaction_classifier")


def classifier_modules() -> list[ModuleType]:
    """analysis.description_text, then each package of PACKAGES that exists and its modules, in name order."""
    modules = [importlib.import_module("analysis.description_text")]
    for name in PACKAGES:
        if importlib.util.find_spec(name) is None:
            continue
        package = importlib.import_module(name)
        modules.append(package)
        found = sorted(pkgutil.iter_modules(package.__path__, name + "."), key=lambda info: info.name)
        modules += [importlib.import_module(info.name) for info in found]
    return modules
