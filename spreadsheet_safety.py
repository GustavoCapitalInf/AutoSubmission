"""The spreadsheet formula-injection rule, shared by every CSV and XLSX the product writes.

One rule in one place (audit 2026-10-13, EXP-6): the webapp's statement and package downloads (`webapp/app.py`, which
re-exports these names) and the `batch.py` triage CSV. It lives outside the `webapp` package on purpose: `batch.py`
must not import the webapp (tests/test_telemetry.py, T12).

A text cell that starts with a formula lead (= + - @ tab CR) gains a leading apostrophe, which Excel and LibreOffice
both read as "this is text". Money-shaped values (`-1234.56`) are left alone: they parse as numbers, and escaping them
would turn every debit into a string and break the underwriter's arithmetic to defend against nothing. Anything that
is not a string (a number, a bool, None) passes through unchanged.
"""
from __future__ import annotations

import re

__all__ = ["FORMULA_LEAD", "NUMERIC_CELL", "escape_formula"]

FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")

# Money-shaped only. `float()` would also accept "-nan" and "+inf", which a
# spreadsheet reads as the start of a formula rather than as a number.
NUMERIC_CELL = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")


def escape_formula(value: object) -> object:
    """Neutralize a spreadsheet formula-injection cell by prefixing an
    apostrophe, which Excel and LibreOffice both read as "this is text".

    Negative money (`-1234.56`) parses as a number in both, so it is left
    alone — escaping it would turn every debit in the export into a string and
    break the underwriter's arithmetic to defend against nothing."""
    if not isinstance(value, str) or not value.startswith(FORMULA_LEAD):
        return value
    if NUMERIC_CELL.match(value):
        return value
    return "'" + value
