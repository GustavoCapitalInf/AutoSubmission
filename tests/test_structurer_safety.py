"""The properties that govern whether the generic rung may exist at all.

Gustavo's acceptance for W3-3c, verbatim-binding: **zero false validations ·
protected core intact · fail closed when evidence is insufficient**. The other
structurer test modules cover mechanism; this one covers the promises, and it
is written adversarially — every case here is a document built to make the
structurer publish something wrong.

The governing asymmetry: a refusal costs coverage, and a wrong published value
costs an underwriting decision. Every test below therefore accepts "no
statement" as a pass and accepts a published statement ONLY when it is right.
"""
from __future__ import annotations

import pytest

from analysis.reconcile import reconcile
from analysis.structurer import structure_document
from analysis.structurer.core import structure_unclaimed

# ---------------------------------------------------------------------------
# Synthetic documents. Invented institutions, invented amounts, invented
# account numbers. No archive content is reproduced anywhere in this repo.
# ---------------------------------------------------------------------------

CLEAN = """--- Page 1 ---
NORTHWIND MUTUAL BANK
Statement period 03/01/2026 to 03/31/2026
Account 9999999999
Beginning balance 5,000.00
Ending balance 5,090.00
Date Description Amount Balance
03/02 ORCHARD SUPPLY CO 150.00 4,850.00
03/05 CUSTOMER DEPOSIT ZEPHYR 900.00 5,750.00
03/09 TOLL BRIDGE AUTHORITY 60.00 5,690.00
03/14 QUARRY FREIGHT LLC 400.00 5,290.00
03/21 CUSTOMER DEPOSIT MARLIN 300.00 5,590.00
03/28 UTILITY DISTRICT 12 500.00 5,090.00
"""


def _sum(statement) -> float:
    return round(sum(t.amount for t in statement.transactions), 2)


def test_the_reference_document_structures_and_reconciles():
    """The control. Without it, every refusal below could be vacuous."""
    outcome = structure_document(CLEAN)

    assert outcome.reason == "structured"
    assert outcome.statement is not None
    assert len(outcome.statement.transactions) == 6
    assert _sum(outcome.statement) == 90.0
    assert reconcile(outcome.statement).ok


# ---------------------------------------------------------------------------
# Fail closed when the evidence is insufficient
# ---------------------------------------------------------------------------

def test_a_document_with_no_printed_period_is_refused():
    """The ADB engine divides by the period length. Deriving it from the first
    and last transaction would shorten every period whose opening days were
    quiet, and inflate every average built on it.

    The rows here print their own year, so the refusal is about the period and
    nothing else: without that, the document also loses its year and refuses
    one step earlier for a different reason.
    """
    document = CLEAN.replace("Statement period 03/01/2026 to 03/31/2026", "")
    for day in ("03/02", "03/05", "03/09", "03/14", "03/21", "03/28"):
        document = document.replace(f"{day} ", f"{day}/2026 ")

    outcome = structure_document(document)

    assert outcome.rows == 6, "the rows must be readable, or this proves nothing"
    assert outcome.statement is None
    assert outcome.reason == "no_printed_period"


def test_a_document_whose_rows_fall_outside_its_period_is_refused():
    """Either the period is wrong or the file holds two statements. Both are
    reasons to say nothing."""
    document = CLEAN.replace("03/28 UTILITY DISTRICT 12 500.00 5,090.00",
                             "05/28 UTILITY DISTRICT 12 500.00 5,090.00")

    outcome = structure_document(document)

    assert outcome.statement is None
    assert outcome.reason == "period_excludes_rows"


def test_amounts_with_no_establishable_direction_are_never_published():
    """No balance column, no debit/credit columns, no direction heading: the
    magnitudes are readable and their SIGN is not. A debit read as a credit
    reconciles nowhere and misleads everywhere."""
    document = """--- Page 1 ---
NORTHWIND MUTUAL BANK
Statement period 03/01/2026 to 03/31/2026
Beginning balance 5,000.00
Ending balance 5,090.00
Date Description Amount
03/02 ORCHARD SUPPLY CO 150.00
03/05 ZEPHYR REMITTANCE 900.00
03/09 TOLL BRIDGE AUTHORITY 60.00
03/14 QUARRY FREIGHT LLC 400.00
03/21 MARLIN REMITTANCE 300.00
03/28 UTILITY DISTRICT 12 500.00
"""
    outcome = structure_document(document)

    assert outcome.statement is None
    assert outcome.reason == "no_signable_rows"


def test_a_wrong_column_is_rejected_rather_than_believed():
    """The balance column here does not chain with the amounts (the document
    prints a running COUNT, not a balance). The chain test must fail rather
    than accept a plausible-looking column."""
    document = """--- Page 1 ---
NORTHWIND MUTUAL BANK
Statement period 03/01/2026 to 03/31/2026
Beginning balance 5,000.00
Ending balance 5,090.00
Date Description Amount Items
03/02 ORCHARD SUPPLY CO 150.00 1.00
03/05 ZEPHYR REMITTANCE 900.00 2.00
03/09 TOLL BRIDGE AUTHORITY 60.00 3.00
03/14 QUARRY FREIGHT LLC 400.00 4.00
03/21 MARLIN REMITTANCE 300.00 5.00
03/28 UTILITY DISTRICT 12 500.00 6.00
"""
    outcome = structure_document(document)

    assert outcome.chained is False
    assert outcome.chain_agreement < 0.9
    assert outcome.statement is None


def test_summary_lines_are_not_transactions():
    """A dated line carrying money is not automatically a posting. Reading the
    opening-balance line as one both invents a transaction and drags the ledger
    into the previous period."""
    document = CLEAN.replace(
        "Beginning balance 5,000.00",
        "Your balance forward on 02/28/2026 5,000.00",
    ).replace(
        "Date Description Amount Balance",
        "Date Description Amount Balance\nTotal deposits 03/31/2026 1,200.00 5,090.00",
    )

    outcome = structure_document(document)

    assert outcome.statement is not None
    assert len(outcome.statement.transactions) == 6
    assert all("TOTAL" not in t.description.upper() for t in outcome.statement.transactions)


# ---------------------------------------------------------------------------
# Grounding: a number that was never printed is never published
# ---------------------------------------------------------------------------

def test_an_ungrounded_summary_value_blocks_publication():
    """The ending balance is printed nowhere near a closing-balance label, so
    the statement cannot be published even though the rows are readable."""
    document = CLEAN.replace("Ending balance 5,090.00", "5,090.00")

    outcome = structure_document(document)

    assert outcome.statement is None
    assert outcome.reason in {"ungrounded", "no_printed_period"}


def test_grounding_is_computed_independently_of_the_rows_that_produced_it():
    """Grounding re-locates values in the raw page text. A check that shares
    its evidence with the thing it checks proves nothing, so this asserts the
    negative case: a statement whose transactions are not in the source text
    fails, even though the structurer built them from a parallel reading."""
    from analysis.structurer.grounding import ground_statement
    from analysis.structurer.rows import RowCandidate
    from analysis.structurer.summary import Period

    invented = [
        RowCandidate("2026-03-02", "PHANTOM VENDOR", -12345.67, None, 1, 0, "03/02",
                     "12,345.67", "balance_chain")
    ]
    result = ground_statement(
        invented, {}, Period("2026-03-01", "2026-03-31", 1, 0, "printed"),
        CLEAN, published_fields=(),
    )

    assert result.ok is False
    assert result.ungrounded_transactions == (0,)


def test_one_printed_amount_cannot_ground_two_rows():
    """Span uniqueness, from the prototype's grounding design: a single printed
    figure justifies one extracted row, not two. Without it, a structurer that
    double-counts a row grounds perfectly."""
    from analysis.structurer.grounding import ground_statement
    from analysis.structurer.rows import RowCandidate
    from analysis.structurer.summary import Period

    duplicated = [
        RowCandidate("2026-03-02", "ORCHARD SUPPLY CO", -150.00, None, 1, 0, "03/02",
                     "150.00", "balance_chain"),
        RowCandidate("2026-03-02", "ORCHARD SUPPLY CO", -150.00, None, 1, 0, "03/02",
                     "150.00", "balance_chain"),
    ]
    result = ground_statement(
        duplicated, {}, Period("2026-03-01", "2026-03-31", 1, 0, "printed"),
        CLEAN, published_fields=(),
    )

    assert result.grounded_transactions == 1
    assert result.ok is False


def test_a_date_the_document_never_printed_is_not_grounded():
    """The structurer supplies a year for `MM/DD` rows. Grounding is what stops
    a supplied year from becoming an invented transaction date."""
    from analysis.structurer.grounding import ground_statement
    from analysis.structurer.rows import RowCandidate
    from analysis.structurer.summary import Period

    wrong_year = [
        RowCandidate("2019-07-04", "ORCHARD SUPPLY CO", -150.00, None, 1, 0, "07/04",
                     "150.00", "balance_chain")
    ]
    result = ground_statement(
        wrong_year, {}, Period("2019-07-01", "2019-07-31", 1, 0, "printed"),
        CLEAN, published_fields=(),
    )

    assert result.ok is False


# ---------------------------------------------------------------------------
# Zero false validations, as a property over adversarial mutations
# ---------------------------------------------------------------------------

def _mutations() -> list[tuple[str, str]]:
    """Documents built to tempt the structurer into publishing something wrong."""
    return [
        ("amount_column_removed", CLEAN.replace(" 150.00 4,850.00", " 4,850.00")),
        ("balance_column_removed", CLEAN.replace(" 4,850.00", "")),
        ("period_absent", CLEAN.replace("Statement period 03/01/2026 to 03/31/2026", "")),
        ("balances_absent", CLEAN.replace("Beginning balance 5,000.00", "")
                                 .replace("Ending balance 5,090.00", "")),
            ("dates_impossible", CLEAN.replace("03/02", "13/45").replace("03/05", "99/99")),
        ("thousands_separator_dropped", CLEAN.replace(",", "")),
        ("row_duplicated", CLEAN.replace(
            "03/05 CUSTOMER DEPOSIT ZEPHYR 900.00 5,750.00",
            "03/05 CUSTOMER DEPOSIT ZEPHYR 900.00 5,750.00\n"
            "03/05 CUSTOMER DEPOSIT ZEPHYR 900.00 5,750.00")),
        ("balance_chain_broken", CLEAN.replace("5,690.00", "9,999.00")),
        ("empty", ""),
        ("not_a_statement", "LEASE AGREEMENT\nThis agreement dated 03/01/2026 for 1,200.00 monthly."),
    ]


@pytest.mark.parametrize("name,document", _mutations(), ids=[n for n, _ in _mutations()])
def test_no_mutation_publishes_a_statement_that_fails_its_own_arithmetic(name, document):
    """The zero-false-validation property, stated where it can be tested.

    A published statement must reconcile against the balances it itself
    reports. Refusing is always acceptable; publishing an internally
    inconsistent ledger never is.
    """
    outcome = structure_document(document)

    if outcome.statement is None:
        return
    statement = outcome.statement
    if statement.beginning_balance is None or statement.ending_balance is None:
        pytest.fail(f"{name}: published a statement with no balance anchors")
    expected = round(statement.beginning_balance + _sum(statement), 2)
    assert abs(expected - statement.ending_balance) <= 0.02, (
        f"{name}: published a ledger that does not reach its own ending balance"
    )


def test_the_rung_is_off_unless_explicitly_enabled(monkeypatch):
    """Ruling 6: default off until Ocean flips it after measured validation."""
    monkeypatch.delenv("GENERIC_STRUCTURER_ENABLED", raising=False)
    assert structure_unclaimed(CLEAN) is None

    monkeypatch.setenv("GENERIC_STRUCTURER_ENABLED", "0")
    assert structure_unclaimed(CLEAN) is None

    monkeypatch.setenv("GENERIC_STRUCTURER_ENABLED", "1")
    assert structure_unclaimed(CLEAN) is not None


def test_the_rung_never_raises_whatever_it_is_handed(monkeypatch):
    """The pipeline calls this directly. A structurer defect must not become
    the escaped-exception class W3-1 just closed."""
    monkeypatch.setenv("GENERIC_STRUCTURER_ENABLED", "1")

    for document in ("", "\x00\x00", "a" * 100_000, "--- Page 1 ---", "<table><tr><td>"):
        assert structure_unclaimed(document) is None or True

    def explode(*args, **kwargs):
        raise ValueError("structurer defect quoting ORCHARD SUPPLY CO 150.00")

    monkeypatch.setattr("analysis.structurer.core.structure_document", explode)
    assert structure_unclaimed(CLEAN) is None


# ---------------------------------------------------------------------------
# The inferred period start (W3-3b Q2 ruling: keep, with two guards)
# ---------------------------------------------------------------------------
#
# "Balance forward on Jul 31" is the 31st's CLOSING balance, so the statement
# it opens starts Aug 1. That +1 day is the only date this subsystem does not
# read off the page, and the ruling attaches two conditions to keeping it:
# the provenance must say so, and a posting before the inferred start must
# refuse the document.

ANCHORED = """--- Page 1 ---
NORTHWIND MUTUAL BANK
Your balance forward on Jul 31, 2026 5,000.00
Your closing balance on Aug 31, 2026 5,090.00
Date Description Amount Balance
08/02 ORCHARD SUPPLY CO 150.00 4,850.00
08/05 CUSTOMER DEPOSIT ZEPHYR 900.00 5,750.00
08/09 TOLL BRIDGE AUTHORITY 60.00 5,690.00
08/14 QUARRY FREIGHT LLC 400.00 5,290.00
08/21 CUSTOMER DEPOSIT MARLIN 300.00 5,590.00
08/28 UTILITY DISTRICT 12 500.00 5,090.00
"""


def test_an_inferred_period_start_is_marked_as_inferred_everywhere_it_travels():
    """Guard 1. The period is usable; what must never happen is a reader
    assuming the start was printed when it was derived from a label."""
    outcome = structure_document(ANCHORED)

    assert outcome.statement is not None
    assert outcome.statement.period_start == "2026-08-01"
    assert outcome.period_provenance == "balance_anchors:start_inferred_from_prior_close"
    assert outcome.grounding.period_provenance == outcome.period_provenance
    assert any("inferred" in note for note in outcome.grounding.notes)


def test_a_printed_period_start_is_not_marked_inferred():
    """The control: an opening label that states the period's own first day is
    read as printed, and nothing is inferred."""
    outcome = structure_document(
        ANCHORED.replace("Your balance forward on Jul 31, 2026",
                         "Beginning balance on Aug 01, 2026")
    )

    assert outcome.statement is not None
    assert outcome.statement.period_start == "2026-08-01"
    assert outcome.period_provenance == "balance_anchors"
    assert not any("inferred" in note for note in outcome.grounding.notes)


def test_a_posting_before_the_inferred_start_refuses_the_document():
    """Guard 2. A row dated on the prior-close date is evidence that the
    inference was wrong — not a reason to stretch the period back over it,
    which would add a day to every average built on it."""
    outcome = structure_document(
        ANCHORED.replace("08/02 ORCHARD SUPPLY CO 150.00 4,850.00",
                         "07/31 ORCHARD SUPPLY CO 150.00 4,850.00")
    )

    assert outcome.statement is None
    assert outcome.reason == "posting_before_inferred_period_start"
