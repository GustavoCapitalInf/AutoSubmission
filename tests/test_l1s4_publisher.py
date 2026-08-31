"""L1-S4: the first multi-account publisher, and every condition it fails closed on.

Constructed pages only (`tests/l1s4_pages.py`), whose arithmetic is generated so
that a fixture can be broken in exactly ONE named way and the reader's answer to
that one difference is what is under test. The archive half of this card is
measured by `tools/l1s4_document_replay.py`, `tools/l1s4_marker_sweep.py`,
`tools/l1s4_q3_oracle.py` and `tools/l1s4_transfer_killers.py`; these are the
refusals, which the archive cannot exercise because the archive prints none of
them.

Each test names the fail-closed condition of the design's §4 it holds.
"""
from __future__ import annotations

import pytest

from analysis.member_statement import detect, parse_member_statement
from analysis.pipeline import analyze_document
from analysis.serialization import document_report_to_dict
from analysis.sibling_omission import (
    PRINTED_PAIR_COINCIDES_AND_NO_ROW_PRINTED,
    RollupWitness,
    prints_pair_coinciding_with_no_row_printed,
)
from telemetry.record import classify_document, classify_outcome
from tests.l1s4_pages import (
    COLUMN_CAPTION,
    Account,
    Posting,
    document,
    idle_account,
    posting_account,
)


def _document(text: str):
    return analyze_document(text, parse_mode="deterministic")


# ===========================================================================
# what it publishes
# ===========================================================================


def test_two_posting_sections_publish_two_independently_validated_accounts():
    """The whole point of the stage: one PDF, two accounts, each reconstructed
    from the paper's own printed partition and each judged by the UNCHANGED
    validator (R-b). Neither account's outcome is derived from the other's."""
    text = document([posting_account(), posting_account("SAMPLE SAVINGS", "01", 60.0)])
    report = _document(text)
    assert len(report.accounts) == 2
    payload = document_report_to_dict(report)
    assert [classify_outcome(account)[0] for account in payload["accounts"]] == [
        "validated", "validated"]
    assert classify_document(payload) == ("validated", "approved")
    assert payload["document"]["account_count"] == 2
    assert payload["document"]["boundary_mechanism"] == "rollup-oracle"
    assert "statement" not in payload


def test_the_published_accounts_are_in_printed_order_and_none_stands_for_the_document():
    """L1-C18. Printed order is evidence about a SEQUENCE; the document's own
    period is the DOCUMENT's, read once and handed to every section, and no
    per-document field is filled from an account."""
    first, second = posting_account(), posting_account("SAMPLE SAVINGS", "01", 60.0)
    payload = document_report_to_dict(_document(document([first, second])))
    labels = [account["statement"]["account_name"] for account in payload["accounts"]]
    assert labels == [first.label, second.label]
    # The document's period is the one the DOCUMENT printed, and both accounts
    # carry it because the paper printed one cycle for all of them.
    starts = {account["statement"]["period_start"] for account in payload["accounts"]}
    assert len(starts) == 1
    assert payload["document"]["period_start"] == starts.pop()


def test_an_idle_sibling_is_omitted_on_printed_evidence_and_the_account_still_validates():
    """Q10, and the Q3 class as the thing that admits it. The published account
    keeps its own `validated`; the gap is published beside it."""
    payload = document_report_to_dict(_document(document([idle_account(), posting_account()])))
    assert "accounts" not in payload           # one account: today's shape
    assert classify_outcome(payload)[0] == "validated"
    assert [item["reason"] for item in payload["document"]["omitted_sections"]] == [
        PRINTED_PAIR_COINCIDES_AND_NO_ROW_PRINTED]
    assert classify_document(payload) == ("validated", "approved")


def test_the_omitted_sections_label_is_the_printed_role_and_never_a_number():
    """The record travels beside an account block that already publishes its own
    identity, so the omission names the product the paper printed and not a
    suffix."""
    idle = idle_account()
    payload = document_report_to_dict(_document(document([idle, posting_account()])))
    omission = payload["document"]["omitted_sections"][0]
    assert omission["label"] == idle.label
    assert omission["posting_count"] == 0
    assert idle.suffix not in (omission["label"] or "")


# ===========================================================================
# L1-C1 — the boundary is PRINTED, in both directions
# ===========================================================================


def test_an_enumerated_account_with_no_printed_section_refuses_the_document():
    """L1-C1. The table says the member has an account; the paper prints no
    section for it. That is an account this reader cannot account for, and the
    L-1 rule is that the document is refused rather than published without it."""
    missing = Account(label="SAMPLE SAVINGS", suffix="01", opening=60.0,
                      postings=[], prints_section=False)
    assert parse_member_statement(document([missing, posting_account()])) is None


def test_a_printed_section_the_table_does_not_enumerate_refuses_the_document():
    """L1-C1, the other direction. A heading the enumerating table never listed
    is a boundary the table did not establish, so the reappearance that IS the
    boundary never happened."""
    published = posting_account()
    unenumerated = idle_account()
    text = document([unenumerated, published], enumerate_accounts=[published])
    assert parse_member_statement(text) is None


def test_a_document_printing_no_enumerating_table_is_not_claimed():
    """L1-C1 / L1-C5 at DETECTION: without the column caption the roles of the
    table's figures are printed nowhere, and this registration does not claim a
    document it could only read by position."""
    text = document([idle_account(), posting_account()], column_caption="ACCOUNT SUMMARY")
    assert not detect(text).claims
    assert parse_member_statement(text) is None


# ===========================================================================
# L1-C2 — the sections are disjoint (the design's constructed fixture for S4)
# ===========================================================================


def test_one_section_printed_twice_refuses_the_document():
    """L1-C2, and the fixture design §4 names as this card's to build: the
    archive prints no duplicated section, and a page-break reprint that lost its
    continuation word would satisfy L1-C1 and nothing else would stop the
    account being published — and counted — twice."""
    text = document([idle_account(), posting_account()], repeat_section="71")
    assert parse_member_statement(text) is None


def test_two_sections_of_the_same_identity_are_a_duplicate_and_not_a_continuation():
    """The positive control beside it, so a reader that refused EVERY
    multi-block account could not pass: the same account printed as a heading
    and a `(Cont)` block is ONE section and publishes."""
    text = document([idle_account(), posting_account()])
    account = "SAMPLE CHECKING  Suffix #71  (Cont)"
    with_continuation = text.replace(
        "Dividend Year to Date   0.00 Ending Balance: $1,486.00",
        f"{account}\nDividend Year to Date   0.00 Ending Balance: $1,486.00")
    published = parse_member_statement(with_continuation)
    assert published is not None and len(published.transactions) == 5


# ===========================================================================
# L1-C6 / L1-C10 — the section and the table must agree
# ===========================================================================


def test_the_same_identity_printed_as_two_separate_sections_refuses():
    """L1-C3. Two sections resolving to one identity is not a continuation and
    is not a duplicate block beside itself: it is a document that says the same
    account twice in two places, and neither reading of it is the document."""
    text = document([idle_account(), posting_account()], repeat_section_at_end="00")
    assert parse_member_statement(text) is None


def test_an_enumerated_row_narrower_than_the_printed_caption_refuses():
    """L1-C5's other half. The caption names four columns; a row printing three
    is a row this reader did not read, and deciding WHICH figure went missing
    is the guess by position that L1-C5 exists to forbid."""
    text = document([idle_account(), posting_account()], drop_row_figure="71")
    assert parse_member_statement(text) is None


@pytest.mark.parametrize("suffix,delta", [("00", 0.01), ("71", -0.01)])
def test_a_rollup_opening_that_disagrees_with_the_section_refuses(suffix, delta):
    """L1-C6, on the OPENING. The opening seeds every later day of the ADB, so
    a document whose own two printings of it differ is one this reader may not
    resolve by choosing."""
    idle, posting = idle_account(), posting_account()
    openings = {"00": idle.opening, "71": posting.opening}
    openings[suffix] = round(openings[suffix] + delta, 2)
    assert parse_member_statement(
        document([idle, posting], opening_override=openings)) is None


def test_a_table_whose_movement_totals_the_ledger_does_not_sum_to_refuses():
    """L1-C8's oracle, and the shape it exists for: the closing still follows
    from the opening, so the balance walk is happy — and the bank's own stated
    deposit and withdrawal totals say the ledger is not what it claims. Two
    errors that cancel is what a truncated ledger looks like from the walk
    alone."""
    idle, posting = idle_account(), posting_account()
    text = document([idle, posting], movement_override={
        "00": (idle.credits, idle.debits),
        "71": (round(posting.credits + 100.0, 2), round(posting.debits + 100.0, 2)),
    })
    assert parse_member_statement(text) is None


def test_no_figure_from_the_enumerating_table_reaches_the_published_payload():
    """L1-C5's standing rule, and the design's ladder read exactly: for this
    mechanism the section's own stated counts and totals are what may be fed,
    and these sections print none — so they are `None`, and what the table
    prints stays an ORACLE the reader checks and never publishes.

    L1-C8's substance is not skipped, it is strengthened. Feeding those two
    figures would buy `reconcile`'s coverage check, which passes anything
    within two per cent; the oracle above compares the same figures to the CENT
    and refuses the document on a disagreement."""
    posting = posting_account()
    published = parse_member_statement(document([idle_account(), posting]))
    assert published.stated_total_credits is None
    assert published.stated_total_debits is None
    assert published.stated_credit_count is None
    assert published.stated_debit_count is None
    # And the bank's own printed average is not published either: the line that
    # carries it prints the DIVIDEND period it belongs to, not this one.
    assert published.bank_reported_average_balance is None


def test_a_printed_reversal_nets_the_column_it_adjusts_rather_than_the_other_one():
    """The paper's own arithmetic, measured rather than assumed. A
    `Withdrawal Adjustment` raises the balance, so the LEDGER carries it as a
    credit — and the table nets it inside the WITHDRAWALS column, which is why
    the oracle compares column by column. Summing by sign instead disagrees
    with the table by twice the reversal on four archive documents, every one
    of them inside `reconcile`'s two-per-cent tolerance."""
    account = posting_account()
    account.postings.append(Posting(28, "Withdrawal", "Debit Card Credit Voucher",
                                    12.34, reversal=True))
    # `Account.debits` nets the reversal, which is the table's convention; the
    # fixture generator and the reader therefore agree, and a fixture built the
    # other way would refuse.
    assert account.debits == pytest.approx(254.25 - 12.34)
    assert parse_member_statement(document([idle_account(), account])) is not None


@pytest.mark.parametrize("suffix,delta", [("00", 0.01), ("71", -0.01)])
def test_a_rollup_closing_that_disagrees_with_the_section_refuses(suffix, delta):
    """L1-C6 and L1-C10's section half. A cent is the smallest disagreement the
    paper could print, and a reader that resolved it by choosing a winner would
    be publishing one of two figures the document itself does not reconcile."""
    idle, posting = idle_account(), posting_account()
    base = {"00": idle.closing, "71": posting.closing}
    base[suffix] = round(base[suffix] + delta, 2)
    text = document([idle, posting], closing_override=base,
                    total_override=round(sum(base.values()), 2))
    assert parse_member_statement(text) is None


def test_a_cross_account_total_the_enumerated_closings_do_not_sum_to_refuses():
    """L1-C10's document half. The total is an ORACLE — it refuses the document
    and never becomes a published value."""
    idle, posting = idle_account(), posting_account()
    text = document([idle, posting],
                    total_override=round(idle.closing + posting.closing + 1.0, 2))
    assert parse_member_statement(text) is None


def test_a_document_printing_no_cross_account_total_still_publishes():
    """The oracle is applied where it is PRINTED and is not required. One of the
    six archive documents prints no total, and refusing it would be refusing a
    document for something the paper never claimed."""
    text = document([idle_account(), posting_account()], prints_total=False)
    assert parse_member_statement(text) is not None


# ===========================================================================
# L1-C7 — the published ledger accounts for every printed dated row
# ===========================================================================


def test_a_printed_dated_row_the_reader_did_not_read_refuses_the_section():
    """L1-C7. A truncated ledger that still reconciles is exactly the failure the
    ADB's source-coverage check exists to catch, and this refuses it one layer
    earlier: a line that opens with a month and a day and carries money, inside
    a section's ledger region, must be a row this reader read."""
    text = document([idle_account(), posting_account()])
    broken = text.replace(
        "Apr 11 Draft 1001 120.00 934.50",
        "Apr 11 Unknown 1001 120.00 934.50")
    assert parse_member_statement(broken) is None


def test_a_dated_line_the_chain_does_not_need_still_refuses_the_section():
    """The same condition where the balance walk CANNOT catch it. This line
    opens with a printed date and carries money, its type word is not one this
    template prints, and dropping it leaves the running balances following each
    other perfectly — so the only thing that can refuse it is the count."""
    text = document([idle_account(), posting_account()], extra_lines={
        "71": ["Apr 15 Memo Returned item notice 88.27"]})
    assert parse_member_statement(text) is None


def test_a_running_balance_that_does_not_follow_refuses_the_section():
    """The direction is read from the row's own printed type WORD and CHECKED
    against the balance the paper printed after it. A word mapped to the wrong
    sign cannot go unnoticed, which is what lets the reader read a direction at
    all instead of solving for one."""
    text = document([idle_account(), posting_account()])
    broken = text.replace("Apr 7 Withdrawal Debit Card SAMPLE MERCHANT 45.50 1,054.50",
                          "Apr 7 Deposit Debit Card SAMPLE MERCHANT 45.50 1,054.50")
    assert parse_member_statement(broken) is None


def test_a_printed_reversal_word_flips_the_direction_and_the_balance_checks_it():
    """`Withdrawal Adjustment` is money coming BACK, and the paper says so twice —
    in the word and in the balance, which rises. Read rather than inferred, and
    the balance walk is what stops a reversal that did not reverse."""
    account = posting_account()
    account.postings.append(Posting(28, "Withdrawal", "Debit Card Credit Voucher",
                                    12.34, reversal=True))
    published = parse_member_statement(document([idle_account(), account]))
    assert published is not None
    assert published.transactions[-1].amount == pytest.approx(12.34)
    assert published.transactions[-1].direction == "credit"


def test_a_section_printing_no_closing_caption_refuses_the_document():
    """A section whose END the paper does not state is a section this reader has
    not read to the end of, and its span would run into whatever came next."""
    account = posting_account()
    account.prints_closing = False
    assert parse_member_statement(document([idle_account(), account])) is None


# ===========================================================================
# R-a / L1-C17 — absence is never a ground
# ===========================================================================


def test_a_silent_section_with_no_printed_evidence_refuses_the_document():
    """The refusal the whole omission machinery exists for. This section posts
    nothing AND its printed pair does not coincide, so no ratified class can
    name it — and a reader that dropped it would be publishing one account of a
    member with two."""
    silent = Account(label="SAMPLE SAVINGS", suffix="01", opening=60.0, postings=[])
    text = document([silent, posting_account()],
                    closing_override={"01": 61.0, "71": posting_account().closing},
                    total_override=round(61.0 + posting_account().closing, 2))
    assert parse_member_statement(text) is None


def test_a_document_whose_every_section_is_idle_publishes_nothing():
    """Every account omitted is no account published, which is a publisher
    defect rather than a document about nothing."""
    text = document([idle_account(), idle_account("SAMPLE SAVINGS", "01", 40.0)])
    assert parse_member_statement(text) is None


# ===========================================================================
# the Q3 class, condition by condition
# ===========================================================================


def _witness(**overrides) -> RollupWitness:
    fields = dict(printed=True, column_roles_printed=True,
                  row_located_by_label=True, row_located_by_identity=True,
                  locators_agree=True, closing=25.0)
    fields.update(overrides)
    return RollupWitness(**fields)


def _admits(**overrides) -> bool:
    arguments = dict(opening=25.0, closing=25.0, dated_row_count=0,
                     prints_counts_or_totals=False,
                     prints_daily_balance_table=False, rollup=_witness())
    arguments.update(overrides)
    return prints_pair_coinciding_with_no_row_printed(**arguments)


def test_the_q3_class_admits_the_shape_the_ruling_describes():
    assert _admits()


@pytest.mark.parametrize("name,overrides", [
    ("C1 the section prints no opening", {"opening": None}),
    ("C2 the section prints no closing", {"closing": None}),
    ("C3 the pair does not coincide", {"closing": 25.01}),
    ("C4 a dated row is printed", {"dated_row_count": 1}),
    ("C4 the count was never taken", {"dated_row_count": None}),
    ("C5 counts or totals are printed", {"prints_counts_or_totals": True}),
    ("C5 the reading was never taken", {"prints_counts_or_totals": None}),
    ("C6 a daily-balance table is printed", {"prints_daily_balance_table": True}),
    ("C6 the reading was never taken", {"prints_daily_balance_table": None}),
    ("C7 no witness at all", {"rollup": None}),
    ("C7 the document prints no roll-up", {"rollup": _witness(printed=False)}),
    ("C7 the column roles are not printed",
     {"rollup": _witness(column_roles_printed=False)}),
    ("C7 no row found by the printed label",
     {"rollup": _witness(row_located_by_label=False, locators_agree=False)}),
    ("C7 no row found by the identity token",
     {"rollup": _witness(row_located_by_identity=False, locators_agree=False)}),
    ("C7 the two handles found different rows",
     {"rollup": _witness(locators_agree=False)}),
    ("C7 the row's closing is not readable under the printed roles",
     {"rollup": _witness(closing=None)}),
    ("C7 the roll-up's closing is a cent out", {"rollup": _witness(closing=25.01)}),
])
def test_every_condition_of_the_q3_class_is_load_bearing(name, overrides):
    """Seven conditions, and each one refuses on its own — including the three
    that refuse because the READING WAS NEVER TAKEN. A caller that supplies no
    count is a caller that did not look, and the class is closed against
    absence in the same direction the vocabulary is."""
    assert not _admits(**overrides), name


def test_the_q3_class_is_unreachable_for_a_reader_that_supplies_none_of_its_arguments():
    """Every reader written before this class supplies none of the four. The
    fifteen protected carriers of W3 §L1S2 are admitted by the three older
    classes and their payloads are pinned, so a class that could reach them
    silently would be movement this card is not entitled to make."""
    from analysis.sibling_omission import evidence_class

    assert evidence_class(text="", opening=25.0, closing=25.0) is None
