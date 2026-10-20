"""The crash shapes discovery found, reproduced synthetically (W3-1 task 2).

Two clusters accounted for all 53 exceptions over the 3,506-document archive:

| Cluster | Documents | Parser | Shape |
|---|---|---|---|
| `AttributeError` | 36 | `us_bank` | a summary block with no "Interest Earned this Period" line |
| `ValueError` | 16 + 1 | `bank_of_america`, `td_us` | a row-date token of the right SHAPE but not a real calendar date |

Every document below is **synthetic** — invented institutions, invented
amounts, invented account numbers — reproducing only the structural shape that
broke the parser. No archive content is reproduced anywhere in this repository,
and the fixtures are built to be the smallest document that reaches the crash
site rather than a realistic statement.

Each cluster gets three tests:

1. the parser handles the shape (this is the defect fix, and it fails before it);
2. the same document through `resolve()` never raises (the W3-1 boundary, which
   holds whether or not the defect is fixed — that is the point of a boundary);
3. the generic helper the fix lives in, tested on its own terms.
"""
from __future__ import annotations

import pytest

from analysis import parser_registry as pr
from analysis.bofa import parse_bofa_statement
from analysis.date_tokens import iso_from_month_day_strict
from analysis.td_us import parse_td_us_statement
from analysis.us_bank import parse_us_bank_statement


# ===========================================================================
# Cluster 1 - us_bank, AttributeError x36: an optional summary line
# ===========================================================================

def us_bank_document(*, interest_line: str = "") -> str:
    """A U.S. Bank account-summary block, with or without an interest line.

    The 36 crashing documents are U.S. Bank statements whose summary block does
    not print "Interest Earned this Period" at all. `_summary` reads five
    optional matches and guards four of them.
    """
    return f"""
Business Statement
U.S. Bank National Association
Account Number 9-999-9999-9999
Account Summary
Jan 1, 2054 through Jan 31, 2054
{interest_line}Number of Days in Statement Period 31
Beginning Balance on Jan 1 $ 1,000.00 Other Deposits 1 500.00 Other Withdrawals 1 200.00-
Ending Balance on  Jan 31, 2054 $ 1,300.00
Other Deposits
Date Description of Transaction Ref Number Amount
Jan 5 Incoming Transfer 1000000001 $ 500.00
Total Other Deposits $ 500.00
Other Withdrawals
Date Description of Transaction Ref Number Amount
Jan 9 Outgoing Transfer 1000000002 200.00-
Total Other Withdrawals $ 200.00-
"""


def test_us_bank_summary_without_an_interest_line_does_not_crash():
    """The 36-document cluster. Fails with AttributeError before the fix."""
    stmt = parse_us_bank_statement(us_bank_document())

    assert stmt is not None
    assert stmt.stated_interest_paid == 0.0, "no printed interest is zero interest, not a crash"
    assert stmt.beginning_balance == 1000.0
    assert stmt.ending_balance == 1300.0


def test_us_bank_still_reads_the_interest_line_when_it_is_printed():
    """The fix must not turn a present optional field into a default."""
    stmt = parse_us_bank_statement(
        us_bank_document(interest_line="Interest Earned this Period $ 12.34\n")
    )

    assert stmt is not None
    assert stmt.stated_interest_paid == 12.34


def test_the_us_bank_crash_shape_fails_closed_through_the_seam():
    """Boundary, not fix: resolve() returns a verdict either way."""
    dispatch = pr.resolve(us_bank_document())

    assert dispatch.outcome in {"claimed", "unclaimed", "parser_exception"}


# ===========================================================================
# Cluster 2 - bank_of_america + td_us, ValueError x17: a shaped non-date
# ===========================================================================

def bofa_document(*, first_row_date: str = "01/05/54") -> str:
    """A BofA native-text statement whose first deposit row carries `first_row_date`.

    The 16 crashing documents contain a row whose leading token matches
    `\\d{2}/\\d{2}/\\d{2}` but is not a date — the discovery reproduction failed
    with "month must be in 1..12, not 26", i.e. a column that is not the date
    column being read as one.
    """
    return f"""
BANK OF AMERICA
bankofamerica.com
Account summary
Preferred Business Checking for January 1, 2054 to January 31, 2054
Account number: 9999 9999 9999
Beginning balance on January 1, 2054 $1,000.00
Ending balance on January 31, 2054 $1,300.00
Deposits and other credits $500.00
Withdrawals and other debits $200.00
# of days in cycle: 31

Deposits and other credits
Date Description Amount
{first_row_date} Incoming transfer 500.00
Total deposits and other credits 500.00

Withdrawals and other debits
Date Description Amount
01/09/54 Outgoing transfer 200.00
Total withdrawals and other debits 200.00
"""


def test_bofa_calendar_invalid_row_date_does_not_crash():
    """The 16-document cluster. Fails with ValueError before the fix.

    The row is dropped, exactly as a row with an unreadable date shape already
    was; reconciliation then decides whether what remains is publishable. That
    is the fail-closed contract doing its job — the alternative, inventing a
    plausible date for a token we cannot read, is the thing the platform must
    never do.
    """
    stmt = parse_bofa_statement(bofa_document(first_row_date="26/13/52"))

    assert stmt is None or all("Incoming transfer" not in t.description for t in stmt.transactions)


def test_bofa_still_reads_a_real_row_date():
    stmt = parse_bofa_statement(bofa_document())

    assert stmt is not None
    assert [t.date for t in stmt.transactions if t.amount > 0] == ["2054-01-05"]


def test_the_bofa_crash_shape_fails_closed_through_the_seam():
    dispatch = pr.resolve(bofa_document(first_row_date="26/13/52"))

    assert dispatch.outcome in {"claimed", "unclaimed", "parser_exception"}


def td_us_document(*, first_row_date: str = "01/05") -> str:
    """A TD Bank (US) statement section whose first row carries `first_row_date`.

    The single TD crash is the same defect class reached through the shared
    row-date helper, on a scanned document: tesseract read a numeric column as
    "42/.." and the parser built a date out of it.
    """
    return f"""
TD Bank, N.A.
STATEMENT OF ACCOUNT
Statement Period: Jan 01 2054-Jan 31 2054
Primary Account #: 9999999999
Beginning Balance 1,000.00
Ending Balance 1,300.00
Days in Period 31
Deposits 500.00

Deposits
POSTING DATE DESCRIPTION AMOUNT
{first_row_date} INCOMING TRANSFER 500.00
Subtotal: 500.00
"""


def test_td_us_calendar_invalid_row_date_does_not_crash():
    """The 1-document cluster. Fails with ValueError before the fix."""
    stmt = parse_td_us_statement(td_us_document(first_row_date="42/13"))

    assert stmt is None or all("INCOMING" not in t.description for t in stmt.transactions)


def test_td_us_still_reads_a_real_row_date():
    stmt = parse_td_us_statement(td_us_document())

    assert stmt is not None
    assert [t.date for t in stmt.transactions] == ["2054-01-05"]


def test_the_td_us_crash_shape_fails_closed_through_the_seam():
    dispatch = pr.resolve(td_us_document(first_row_date="42/13"))

    assert dispatch.outcome in {"claimed", "unclaimed", "parser_exception"}


# ===========================================================================
# The shared helper the date fix lives in
# ===========================================================================

@pytest.mark.parametrize("token", ["26/13", "42/13", "00/00", "13/01", "02/30", "01/32"])
def test_a_shaped_but_impossible_date_token_is_not_a_date(token):
    """`iso_from_month_day_strict` answers "is this MM/DD?" — and a token that
    no calendar can hold is not, however well it matches the shape."""
    assert iso_from_month_day_strict(token, 2054) is None


@pytest.mark.parametrize(
    ("token", "expected"),
    [("01/05", "2054-01-05"), ("12/31", "2054-12-31"), ("02/29", "2052-02-29")],
)
def test_real_tokens_still_parse(token, expected):
    year = 2052 if expected.startswith("2052") else 2054
    assert iso_from_month_day_strict(token, year) == expected


# ===========================================================================
# End to end: a crash no longer escapes the pipeline
# ===========================================================================

def test_a_parser_crash_does_not_escape_analyze_markdown():
    """A deliberately-crashing registration, in the REAL registry.

    Deterministic mode has no fallback, so the document still fails - but it
    fails as the platform's own fail-closed refusal rather than as a parser's
    AttributeError carrying a fragment of a statement in its message.
    """
    from analysis.pipeline import analyze_markdown

    def explode(markdown: str):
        raise AttributeError(f"'NoneType' object has no attribute 'group': {markdown}")

    registration = pr.register(pr.Registration(
        id="_synthetic_crash_probe",
        bank="Synthetic Crash Probe",
        markers=(pr.required("probe", lambda t: "SYNTHETIC CRASH PROBE DOCUMENT" in t),),
        parse=explode,
    ))
    document = "SYNTHETIC CRASH PROBE DOCUMENT\nACME PLUMBING LLC\n"
    seen: list = []
    try:
        dispatch = pr.resolve(document)
        assert dispatch.outcome == "parser_exception"
        assert dispatch.exceptions == (
            pr.ParserFailure("_synthetic_crash_probe", "parse", "AttributeError"),
        )

        with pytest.raises(RuntimeError) as raised:
            analyze_markdown(document, parse_mode="deterministic", on_dispatch=seen.append)
        assert "ACME PLUMBING" not in str(raised.value)
    finally:
        pr._REGISTRY.pop(registration.id, None)

    assert seen and seen[0].outcome == "parser_exception", (
        "telemetry must see the crash: the Dispatch is its only source"
    )
