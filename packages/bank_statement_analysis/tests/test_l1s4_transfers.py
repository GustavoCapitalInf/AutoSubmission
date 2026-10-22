"""L1-S4: R-d, its four clauses, and what the package does with the answer.

The archive half of this ran the
production rule over the design's own measured population — 7 documents, 47
candidate pairs, 43 flagged, 4 refused — and reproduced the split exactly. What
the archive cannot exercise is the AMBIGUITY branch (it prints none: 0 postings
with two or more admissible counterparts), so that killer is constructed here
and named as constructed, which is what design §4 requires of this card.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from analysis.pipeline import (
    AMBIGUOUS_INTERNAL_TRANSFER,
    analyze_document,
    identify_internal_transfers,
)
from analysis.schema import Statement, Transaction
from analysis.serialization import document_report_to_dict
from analysis.descriptor.rails import prints_internal_transfer_designation
from tests.l1s4_pages import Account, Posting, document, idle_account, posting_account

#: A printed designation the INTERNAL vocabulary reads, and one only the
#: peer-to-peer vocabulary would — the distinction R-d's fourth clause turns on.
INTERNAL_CREDIT = "Deposit Transfer From Savings"
INTERNAL_DEBIT = "Withdrawal Home Banking Transfer To Share"
PEER_TO_PEER = "Deposit ACH VENMO"
NOTHING_PRINTED = "Deposit Kiosk"


def _account(*postings) -> SimpleNamespace:
    """One account's ledger, as `identify_internal_transfers` reads it."""
    return SimpleNamespace(statement=Statement(transactions=[
        Transaction(date=date, description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for date, amount, text in postings
    ]))


# ===========================================================================
# the vocabulary — clause 4's evidence
# ===========================================================================


def test_the_internal_vocabulary_reads_a_printed_designation():
    assert prints_internal_transfer_designation(INTERNAL_CREDIT)


@pytest.mark.parametrize("description", [
    PEER_TO_PEER,
    "Deposit ZELLE FROM SOMEONE",
    "Withdrawal Debit Card CASH APP*SOMEONE",
    "Deposit E TRANSFER",
    NOTHING_PRINTED,
    "",
])
def test_a_peer_to_peer_rail_is_never_a_printed_internal_designation(description):
    """Q2, ruled: a payment to or from another PERSON is not evidence that money
    moved inside one member's own ledger set. Admitting it would flag the pair
    and then delete the matching printed deposit from a funder's view of the
    business — the exact failure the clause exists to prevent, re-admitted
    through the vocabulary it was founded on."""
    assert not prints_internal_transfer_designation(description)


# ===========================================================================
# the four clauses
# ===========================================================================


def test_a_designated_same_day_same_cent_opposite_sign_pair_is_internal():
    transfers, notes = identify_internal_transfers([
        _account(("2026-04-02", -250.0, INTERNAL_DEBIT)),
        _account(("2026-04-02", 250.0, INTERNAL_CREDIT)),
    ])
    assert notes == []
    assert len(transfers) == 1
    assert {transfers[0].a, transfers[0].b} == {(0, 0), (1, 0)}
    # The DEBIT leg of this pair says `Transfer To`, which the internal
    # vocabulary — a credit vocabulary, naming where money came FROM — does not
    # read. That is the archive's own shape: 42 of its 43 designated pairs rest
    # on the credit row alone.
    assert transfers[0].basis == (
        "printed_internal_transfer_designation_on_the_credit_leg")


def test_a_pair_whose_both_legs_print_a_designation_says_so():
    """The one archive pair that has two printed rows to stand on, and the
    reason `basis` exists: a reader can tell it from the forty-two that have
    one."""
    transfers, _notes = identify_internal_transfers([
        _account(("2026-04-02", -250.0, "Withdrawal Account To Account Transfer")),
        _account(("2026-04-02", 250.0, INTERNAL_CREDIT)),
    ])
    assert len(transfers) == 1
    assert transfers[0].basis == "printed_internal_transfer_designation_on_both_legs"


def test_one_printed_leg_is_enough_and_the_basis_says_which():
    """42 of the archive's 43 designated pairs rest on ONE printed row, so
    "at least one leg" is load-bearing rather than a formality — and the basis
    records which leg carried it, so a reader can tell the two apart."""
    transfers, _notes = identify_internal_transfers([
        _account(("2026-04-02", -250.0, NOTHING_PRINTED)),
        _account(("2026-04-02", 250.0, INTERNAL_CREDIT)),
    ])
    assert len(transfers) == 1
    assert transfers[0].basis == (
        "printed_internal_transfer_designation_on_the_credit_leg")


def test_an_arithmetic_coincidence_with_nothing_printed_is_not_a_transfer():
    """Clause 4, and the one that decides the whole rule. A member who deposits
    a sum into checking on the day they withdraw the same sum from savings for
    an unrelated purpose produces exactly this signature."""
    transfers, notes = identify_internal_transfers([
        _account(("2026-04-02", -250.0, NOTHING_PRINTED)),
        _account(("2026-04-02", 250.0, NOTHING_PRINTED)),
    ])
    assert transfers == [] and notes == []


def test_a_pair_admitted_only_by_the_peer_to_peer_vocabulary_is_refused():
    """Three of the archive's four refused pairs are exactly this shape."""
    transfers, notes = identify_internal_transfers([
        _account(("2026-04-02", -250.0, "Withdrawal ZELLE TO SOMEONE")),
        _account(("2026-04-02", 250.0, PEER_TO_PEER)),
    ])
    assert transfers == [] and notes == []


@pytest.mark.parametrize("left,right", [
    (("2026-04-02", -250.0, INTERNAL_DEBIT), ("2026-04-03", 250.0, INTERNAL_CREDIT)),
    (("2026-04-02", -250.0, INTERNAL_DEBIT), ("2026-04-02", 250.01, INTERNAL_CREDIT)),
    (("2026-04-02", 250.0, INTERNAL_CREDIT), ("2026-04-02", 250.0, INTERNAL_CREDIT)),
])
def test_clause_one_refuses_a_different_day_a_different_cent_and_the_same_sign(left, right):
    transfers, notes = identify_internal_transfers([_account(left), _account(right)])
    assert transfers == [] and notes == []


def test_a_counterpart_in_the_same_account_is_not_a_counterpart():
    """A SIBLING account, on the SAME document. Two rows of one ledger that
    cancel are one account's own business."""
    transfers, notes = identify_internal_transfers([
        _account(("2026-04-02", -250.0, INTERNAL_DEBIT),
                 ("2026-04-02", 250.0, INTERNAL_CREDIT)),
        _account(("2026-04-05", 10.0, NOTHING_PRINTED)),
    ])
    assert transfers == [] and notes == []


def test_a_single_account_document_pairs_nothing_and_costs_nothing():
    """One ledger has no sibling for a counterpart to be in, which is why this
    costs the archive nothing: the function returns before looking at a row."""
    assert identify_internal_transfers([
        _account(("2026-04-02", 250.0, INTERNAL_CREDIT))]) == ([], [])


# ===========================================================================
# §3.3 — ambiguity, whose killer the archive cannot supply
# ===========================================================================


def test_two_admissible_counterparts_pair_with_none_and_note_the_document():
    """The CONSTRUCTED killer design §4 assigns to this card: the archive prints
    0 postings with two or more admissible counterparts, so this branch has no
    sha and is named as a fixture.

    Both legs carry an internal designation, deliberately: the refusal is about
    the PAIRING and not about the evidence, so a fixture whose legs printed
    nothing would prove the wrong thing."""
    transfers, notes = identify_internal_transfers([
        _account(("2026-04-02", 250.0, INTERNAL_CREDIT)),
        _account(("2026-04-02", -250.0, INTERNAL_DEBIT),
                 ("2026-04-02", -250.0, INTERNAL_DEBIT)),
    ])
    assert transfers == []
    assert notes == [AMBIGUOUS_INTERNAL_TRANSFER]


def test_an_unambiguous_pair_beside_an_ambiguous_one_is_refused_too():
    """Fail-closed for the WHOLE document. Pairing the unambiguous pairs beside
    an unresolved one would publish a partial exclusion that reads as a
    complete one."""
    transfers, notes = identify_internal_transfers([
        _account(("2026-04-02", 250.0, INTERNAL_CREDIT),
                 ("2026-04-09", 12.0, INTERNAL_CREDIT)),
        _account(("2026-04-02", -250.0, INTERNAL_DEBIT),
                 ("2026-04-02", -250.0, INTERNAL_DEBIT),
                 ("2026-04-09", -12.0, INTERNAL_DEBIT)),
    ])
    assert transfers == []
    assert notes == [AMBIGUOUS_INTERNAL_TRANSFER]


# ===========================================================================
# both legs stay in their ledgers
# ===========================================================================


def _two_account_document_with_a_transfer() -> str:
    debit = Account(label="SAMPLE SHARE", suffix="00", opening=900.0, postings=[
        Posting(3, "Deposit", "Kiosk", 40.0),
        Posting(14, "Withdrawal", "Home Banking Transfer To Share 0071", 250.0),
    ])
    credit = Account(label="SAMPLE CHECKING", suffix="71", opening=100.0, postings=[
        Posting(14, "Deposit", "Transfer From Savings 0000", 250.0),
        Posting(21, "Withdrawal", "POS #000000000002", 30.0),
    ])
    return document([debit, credit])


def test_a_flagged_transfer_leaves_both_printed_legs_in_their_ledgers():
    """R-d, ruling condition 4. Removing either leg would break that account's
    own reconciliation and its ADB — the money really was in that account on
    that day — and it is also the only way `reconcile` stays untouched."""
    report = analyze_document(_two_account_document_with_a_transfer(),
                              parse_mode="deterministic")
    payload = document_report_to_dict(report)
    assert len(payload["document"]["internal_transfers"]) == 1
    ledgers = [account["statement"]["transactions"] for account in payload["accounts"]]
    assert [len(ledger) for ledger in ledgers] == [2, 2]
    from telemetry.record import classify_outcome
    assert [classify_outcome(account)[0] for account in payload["accounts"]] == [
        "validated", "validated"]


def test_the_published_transfer_is_index_pairs_and_carries_no_printed_value():
    """A document-level fact stored as INDICES: never an amount, never a date,
    never a description. The transaction dicts of every payload in the archive
    are untouched by it."""
    payload = document_report_to_dict(analyze_document(
        _two_account_document_with_a_transfer(), parse_mode="deterministic"))
    transfer = payload["document"]["internal_transfers"][0]
    assert set(transfer) == {"a", "b", "basis"}
    assert all(isinstance(value, int) for value in transfer["a"] + transfer["b"])
    for account in payload["accounts"]:
        for row in account["statement"]["transactions"]:
            assert not [key for key in row if "transfer" in key.lower()]


# ===========================================================================
# the package
# ===========================================================================


class _Job:
    """A package member, with only the attributes `package_analysis` reads."""

    def __init__(self, ident, analysis, filename="synthetic.pdf"):
        self.id = ident
        self.filename = filename
        self.status = "done"
        self.analysis = analysis
        self.analysis_error = None
        self.error = None
        self.content_sha256 = f"SYNTHETIC-{ident.upper()}"


def _payload_with_a_transfer() -> dict:
    return document_report_to_dict(analyze_document(
        _two_account_document_with_a_transfer(), parse_mode="deterministic"))


def test_the_package_counts_a_transfer_once_by_not_counting_it_at_all():
    """The double the exclusion exists to remove: the same money is a credit in
    one account and a debit in the other, so a package that sums both counts it
    twice — as a deposit AND as a withdrawal — and every derivation built on
    them carries the double."""
    from analysis.package import package_analysis

    payload = _payload_with_a_transfer()
    package = package_analysis([_Job("job-1", payload)])
    accounts = payload["accounts"]
    gross_credits = sum(
        row["amount"] for account in accounts
        for row in account["statement"]["transactions"] if row["amount"] > 0)
    assert package["totals"]["total_credits"] == pytest.approx(
        round(gross_credits - 250.0, 2))
    # The flattened ledger drops the two legs as well, so a person reading the
    # package's own rows sees what the totals were computed from.
    rows = package["transactions"]
    assert len(rows) == sum(
        len(account["statement"]["transactions"]) for account in accounts) - 2


def test_the_package_cash_flow_is_unchanged_by_a_transfer():
    """A pair removes a credit from one member and the matching debit from
    another, so the package's cash flow is unchanged BY CONSTRUCTION — which is
    the property that says the exclusion is removing a double rather than
    money."""
    from analysis.package import package_analysis

    package = package_analysis([_Job("job-1", _payload_with_a_transfer())])
    totals = package["totals"]
    assert totals["cash_flow"] == pytest.approx(
        round(totals["total_credits"] - totals["total_debits"], 2))


def test_a_package_of_todays_payloads_is_untouched_by_any_of_this():
    """The single-account path: no `document` block, no transfers, no exclusion,
    and no new key. Every package this platform has produced is in this shape."""
    from analysis.package import package_analysis

    payload = document_report_to_dict(analyze_document(
        document([idle_account(), posting_account()]), parse_mode="deterministic"))
    package = package_analysis([_Job("job-1", payload)])
    assert "statement_periods" not in package["totals"]
    assert "cross_account_averages_refused" not in package["totals"]
    assert package["totals"]["months"] == 1
    # Q10's surface, on the other hand, IS lit — the document surfaced an
    # omission, and a package that never said so would be the ruling unheard.
    assert package["totals"]["sibling_account_omission_detected"] is True
    assert package["totals"]["completeness"] == "partial"


def test_an_ambiguous_document_has_its_accounts_excluded_from_the_package():
    """§3.3 / Q2: the package refuses to AGGREGATE that document. Each account
    keeps its own outcome and its own ledger; what it does not do is contribute
    to a total nobody could defend."""
    from analysis.package import package_analysis
    from analysis.package.members import package_members

    payload = _payload_with_a_transfer()
    payload["document"]["integrity_notes"] = [AMBIGUOUS_INTERNAL_TRANSFER]
    payload["document"]["internal_transfers"] = []
    job = _Job("job-1", payload)
    members, excluded = package_members([job])
    assert members == []
    assert [item["reason"] for item in excluded] == [
        "document_transfer_pairing_ambiguous"] * 2
    package = package_analysis([job])
    assert package["totals"]["total_credits"] == 0
    assert len(package["excluded_accounts"]) == 2


# ===========================================================================
# the gate's per-account assertions (design §6.5, the four the L1-S3 review
# recorded as owed)
# ===========================================================================


def test_the_gate_refuses_a_posting_that_is_a_leg_of_two_transfers():
    """R-d's one-to-one, asserted where it CAN be. It follows from clause 2 in
    the publisher — a one-way counterpart means the other side saw two, and
    that whole document is refused — so a second check there could never fire
    and no mutation table could show it doing anything. Here it can: a payload
    reaching the gate from a store written before the rule existed is exactly
    the case, and counting one posting twice would remove one movement's worth
    of money twice from every package total."""
    from corpus_gate import document_verdicts

    payload = _payload_with_a_transfer()
    transfer = dict(payload["document"]["internal_transfers"][0])
    payload["document"]["internal_transfers"].append(transfer)
    with pytest.raises(ValueError, match="internal_transfer_pairing_not_one_to_one"):
        document_verdicts(payload)


@pytest.mark.parametrize("leg,message", [
    ([9, 0], "internal_transfer_account_out_of_range"),
    ([0, 99], "internal_transfer_posting_out_of_range"),
    ([0], "internal_transfer_leg_malformed"),
])
def test_the_gate_refuses_a_transfer_leg_that_does_not_resolve(leg, message):
    """Every leg must name an account this payload publishes and a posting that
    account's own ledger holds. An index that resolves to nothing is a record
    about a document this is not."""
    from corpus_gate import document_verdicts

    payload = _payload_with_a_transfer()
    payload["document"]["internal_transfers"][0]["a"] = leg
    with pytest.raises(ValueError, match=message):
        document_verdicts(payload)


def test_the_gate_refuses_a_document_level_average_under_any_name():
    """R-c made mechanical, and asserted on the KEY NAMES rather than on one
    field: the ADB doctrine's unit is the ACCOUNT, so a document yields one
    figure per account and none of its own — and the package's own
    days-weighted mean already showed that the same arithmetic can arrive under
    a different name."""
    from corpus_gate import document_verdicts

    payload = _payload_with_a_transfer()
    payload["document"]["average_daily_balance"] = 1234.56
    with pytest.raises(ValueError, match="no_document_level_adb"):
        document_verdicts(payload)


def test_the_gate_asserts_the_canonical_stamps_on_every_account():
    """The corpus-wide stamp check is path-keyed and therefore blind to a
    second account. This is the per-account half."""
    from corpus_gate import document_verdicts

    payload = _payload_with_a_transfer()
    payload["accounts"][1]["metrics"]["adb"]["underwriting_adb_basis"] = "banking_day"
    with pytest.raises(ValueError, match="adb_stamps_missing_on_an_account"):
        document_verdicts(payload)


def test_the_gate_refuses_an_omission_the_vocabulary_cannot_name():
    """L1-C17 asserted AT THE GATE, which is a different statement from the
    fold failing such a document: a document the corpus publishes carries no
    unratified omission at all."""
    from corpus_gate import document_verdicts

    payload = _payload_with_a_transfer()
    payload["document"]["omitted_sections"] = [
        {"label": "SAMPLE", "reason": "absence_of_parsed_rows", "posting_count": 0}]
    with pytest.raises(ValueError, match="omission_reason_not_ratified"):
        document_verdicts(payload)


def test_the_gate_answers_a_single_account_payload_exactly_as_it_always_did():
    """Every document in the pinned corpus is this shape, and the assertions
    above must cost it nothing."""
    from corpus_gate import document_verdicts

    payload = document_report_to_dict(analyze_document(
        document([idle_account(), posting_account()]), parse_mode="deterministic"))
    verdict, per_account = document_verdicts(payload)
    assert verdict.outcome == "validated"
    assert len(per_account) == 1 and per_account[0] is verdict


def test_the_package_reads_the_note_this_pipeline_writes():
    """One refusal, one spelling. The package's constant and the pipeline's are
    held equal here rather than by a comment."""
    from analysis.package.members import _AMBIGUOUS_TRANSFER_NOTE

    assert _AMBIGUOUS_TRANSFER_NOTE == AMBIGUOUS_INTERNAL_TRANSFER


def test_two_accounts_of_one_document_are_one_statement_period():
    """MINOR-10. `months` counted MEMBERS. Audit B11 (I07, I33) makes it the
    distinct calendar months the statements stand for, so two accounts of one
    document are one statement period AND one month; `statement_periods` is
    published beside `months` only where the two differ, and here they do not."""
    from analysis.package import package_analysis

    package = package_analysis([_Job("job-1", _payload_with_a_transfer())])
    assert package["totals"]["months"] == 1
    assert "statement_periods" not in package["totals"]
    # And the per-period averages are refused rather than halved (Q5).
    assert package["totals"]["cross_account_averages_refused"] is True
    assert package["totals"]["avg_monthly_credits"] is None
    assert package["totals"]["average_daily_balance"] is None
