"""The mutant table for `analysis/pnc.py` — one decision per row.

Every `old` below is an EXACT excerpt of the production source and every `new`
is the same excerpt with one decision broken in the direction that would
publish something wrong. The table lives in its own module because that makes
the "written and read with a file tool, never through a shell heredoc" rule
enforceable by looking: a heredoc has twice turned an escape in a table like
this one into a control byte, and a mutant table with a 0x08 in it silently
never applies.

The harness (`tools/pnc_mutation_table.py`) refuses to run unless each `old`
occurs exactly ONCE in the file, so a mutant can never apply somewhere else.
"""
from __future__ import annotations

from typing import NamedTuple


class Mutant(NamedTuple):
    ident: str
    target: str
    rule: str
    what: str
    old: str
    new: str
    suite: tuple[str, ...]


PNC = "analysis/pnc.py"
LAYOUTS = ("tests/test_pnc_layouts.py",)
VARIANTS = ("tests/test_pnc_variants.py",)
BOTH = LAYOUTS + VARIANTS

MUTANTS: tuple[Mutant, ...] = (
    Mutant(
        "M1", PNC, "the control byte is normalised at entry",
        "the reader sees the raw text, so a continuation heading whose column "
        "gap is a C0 control byte is not a heading and its whole page of rows "
        "belongs to no section",
        'markdown = _CONTROL_BYTE.sub(" ", markdown)\n    if not detect(markdown).claims:',
        'markdown = markdown\n    if not detect(markdown).claims:',
        BOTH,
    ),
    Mutant(
        "M2", PNC, "the printed index is an identity",
        "the reader publishes whatever it captured, however far short of the "
        "bank's own index of it",
        "    if not _matches_the_printed_index(captured, _printed_index(markdown)):\n"
        "        return None",
        "    if False:\n        return None",
        BOTH,
    ),
    Mutant(
        "M3", PNC, "the index is checked in BOTH directions",
        "a section the index does not print at all is published anyway — the "
        "half of the check that catches rows the bank never said were there",
        "    return all(not rows or name in printed for name, rows in captured.items())",
        "    return True",
        LAYOUTS,
    ),
    Mutant(
        "M4", PNC, "the index's COUNT is checked, not only its total",
        "a section read LONG passes as long as its total still lands — which "
        "is exactly what a row read twice beside a row dropped looks like",
        "            if len(rows) != items or abs(captured_total - total) > _TOLERANCE:",
        "            if abs(captured_total - total) > _TOLERANCE:",
        LAYOUTS,
    ),
    Mutant(
        "M5", PNC, "the printed ladder is an identity",
        "a row published on a day the bank did not post it — invisible to the "
        "index and to the summary, and visible only here",
        "    if grid and not _matches_the_printed_grid(",
        "    if False and not _matches_the_printed_grid(",
        LAYOUTS,
    ),
    Mutant(
        "M6", PNC, "a ladder cell outside the printed period fails the document",
        "a ladder page from another statement is skipped instead of refused",
        "        if iso not in walked or abs(walked[iso] - balance) > _TOLERANCE:",
        "        if iso in walked and abs(walked[iso] - balance) > _TOLERANCE:",
        LAYOUTS,
    ),
    Mutant(
        "M7", PNC, "a ladder that prints one day twice with two balances is refused",
        "the later cell silently wins, so the ledger is walked against a "
        "ladder the document itself does not agree on",
        "            if day in grid and abs(grid[day] - value) > _TOLERANCE:\n"
        "                return None",
        "            if False:\n                return None",
        LAYOUTS,
    ),
    Mutant(
        "M8", PNC, "a both-sided category with no direction printed is declined",
        "the reader guesses CREDIT, which signs a whole section on a coin toss",
        "        if sign is None:\n            return None",
        "        if sign is None:\n            sign = 1",
        LAYOUTS,
    ),
    Mutant(
        "M9", PNC, "the umbrella heading's own direction",
        "the debit umbrella is read as a credit one, so every both-sided "
        "category printed under it changes sign",
        '    "Checks and Other Debits": -1,',
        '    "Checks and Other Debits": 1,',
        LAYOUTS,
    ),
    Mutant(
        "M10", PNC, "the product is the one the statement TITLES itself with",
        "the last product name printed anywhere wins, so a treasury statement "
        "publishes the product of the other account in its pricing table",
        "    return min(found)[1] if found else None",
        "    return max(found)[1] if found else None",
        LAYOUTS,
    ),
    Mutant(
        "M11", PNC, "a heading owns its line",
        "a row whose description contains a section's words opens that section",
        '    r"(?im)^" + _H + r"*(?P<name>"',
        '    r"(?im)" + _H + r"*(?P<name>"',
        BOTH,
    ),
    Mutant(
        "M12", PNC, "the summary block ends where the next block starts",
        "the reader walks past a grid row that is a column short and reads the "
        "index printed below it as the summary",
        "    end = _SUMMARY_BLOCK_END.search(body)",
        "    end = None if body else _SUMMARY_BLOCK_END.search(body)",
        LAYOUTS,
    ),
    Mutant(
        "M13", PNC, "the ladder is published as bank evidence",
        "the printed end-of-day balances are checked and then thrown away, so "
        "the platform reconstructs days the bank had already stated",
        "    stmt.stated_daily_balances = [\n"
        "        StatementDailyBalance(date=day, balance=balance)\n"
        "        for day, balance in sorted(grid.items())\n"
        "    ]",
        "    stmt.stated_daily_balances = []",
        LAYOUTS,
    ),
    Mutant(
        "M14", PNC, "detection is as narrow as what the reader can name",
        "a Virtual Wallet variant this reader cannot name is claimed anyway, "
        "and published with no product at all",
        '    required("product", lambda t: any(product in t for product in _PRODUCTS)),',
        '    required("product", lambda t: any(product in t for product in _PRODUCTS)\n'
        '             or "Virtual Wallet" in t),',
        LAYOUTS,
    ),
    Mutant(
        "M15", PNC, "the period sentence is printed in two casings",
        "only the capitalised one is read, so two of the four skins lose their "
        "period and decline",
        r'        r"For the [Pp]eriod\s+(\d{2})/(\d{2})/(\d{4})\s+to\s+(\d{2})/(\d{2})/(\d{4})",',
        r'        r"For the Period\s+(\d{2})/(\d{2})/(\d{4})\s+to\s+(\d{2})/(\d{2})/(\d{4})",',
        LAYOUTS,
    ),
    Mutant(
        "M16", PNC, "the activity region on a skin printing no `Activity Detail`",
        "the commercial skin's detail is never found, so it publishes nothing",
        "        group = _HEADING_LINE.search(markdown, grid.end())",
        "        group = None",
        LAYOUTS,
    ),
    Mutant(
        "M17", PNC, "one section's two printed spellings are one key",
        "the index's spelling and the detail heading's spelling are two "
        "sections, so each is short of the other's rows",
        '    "Funds Transfers In": "Funds Transfer In",',
        '    "Funds Transfers In": "Funds Transfers In",',
        LAYOUTS,
    ),
    Mutant(
        "M18", PNC, "a row that moves no money is not a posting",
        "a dated informational line is published as a transaction, and no "
        "printed identity can see it",
        "    return amount != 0",
        "    return True",
        VARIANTS,
    ),
)
