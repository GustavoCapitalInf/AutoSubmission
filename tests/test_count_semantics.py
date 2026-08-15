"""COUNTS-P2 — the stated-count integrity check, phase 2.

The check compares the bank's PRINTED per-direction count against the rows we
captured and flags a disagreement to `review`. Everything that keeps it from
being a false-positive machine is structural, and every one of those
structures is pinned here:

* an INCOMPARABLE direction can never flag — asserted against every entry in
  the table, on a payload built to disagree;
* an UNSURVEYED parser can never flag — the property that makes a new parser
  registration safe to land without touching this check;
* `None` is not-applicable and never flags (`is False`, not `not ...`);
* the count is keyed on the printed COLUMN, never on the sign of the money;
* the check appends no reconciliation issue, so no document is withheld by
  it, and `recon.ok` is untouched;
* the expected side is the bank's printed field and never the copy of it that
  `metrics` publishes.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from analysis import parser_registry as pr
from analysis import parser_registry_entries  # noqa: F401  — populates the registry
from analysis.count_semantics import (
    DIRECTIONS,
    SECTION_LEVEL_ORACLES,
    SEMANTICS,
    UNSURVEYED,
    counts_comparable,
    semantics_for,
)
from analysis.metrics import compute_metrics
from analysis.pipeline import Quality, assess_document_integrity
from analysis.reconcile import reconcile
from analysis.schema import Statement, Transaction
from telemetry.diagnostics import CLASS_OF, INTEGRITY_FLAGS
from telemetry.record import classify_outcome

ROOT = Path(__file__).resolve().parents[1]

#: A surveyed parser, comparable in both directions.
COMPARABLE = "rbc"
#: A surveyed parser the table declares incomparable in both directions.
INCOMPARABLE = "altana"
#: A real registration that populates a printed count and is NOT in the table.
#: The live witness for the unsurveyed-default property: it landed after the
#: table was written, it prints counts on 127 archive documents (154 across
#: the BMO family), and the check says nothing about any of them.
UNSURVEYED_REGISTRATION = "bmo_ca_business"

COUNT_FLAGS = ("credit_count_mismatch", "debit_count_mismatch")


def txn(amount: float, direction: str, desc: str = "ROW", bal: float | None = None) -> Transaction:
    """A row whose COLUMN and whose MONEY are set independently, on purpose."""
    return Transaction(
        date="2026-01-01", description=desc, amount=amount,
        direction=direction, running_balance=bal,
    )


def statement(*, rows: list[Transaction], credit: int | None, debit: int | None, **kwargs) -> Statement:
    """A statement that reconciles on money, so only the COUNT can speak."""
    body = {
        "bank": "Test Bank",
        "beginning_balance": 100.0,
        "ending_balance": round(100.0 + sum(t.amount for t in rows), 2),
        "stated_credit_count": credit,
        "stated_debit_count": debit,
        "transactions": rows,
    }
    body.update(kwargs)
    return Statement(**body)


def quality() -> Quality:
    return Quality(
        level="transaction_level",
        transaction_detail_reliable=True,
        summary_totals_reliable=True,
        corporate_use="approved",
    )


def integrity_for(stmt: Statement, parser_id: str | None, *, outcome: str = "claimed"):
    dispatch = (
        pr.Dispatch(outcome, registration=pr.by_id(parser_id)) if parser_id else None
    )
    recon = reconcile(stmt)
    return recon, assess_document_integrity(stmt, recon, quality(), markdown="x", dispatch=dispatch)


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------


def test_every_entry_covers_both_directions_and_argues_for_itself():
    for parser_id, table in SEMANTICS.items():
        assert set(table) == set(DIRECTIONS), parser_id
        for direction, semantics in table.items():
            assert semantics.scope, f"{parser_id}:{direction}"
            assert len(semantics.reason) > 40, f"{parser_id}:{direction} states no argument"


def test_the_table_only_names_parsers_that_exist_in_the_registry():
    known = {registration.id for registration in pr.registrations()}
    assert set(SEMANTICS) <= known, set(SEMANTICS) - known


def test_the_comparable_set_is_pinned_so_a_promotion_is_never_incidental():
    """Promoting a bank changes which documents can be flagged. It is a
    decision with evidence behind it, so the decision is written down."""
    comparable = {
        f"{parser_id}:{direction}"
        for parser_id, table in SEMANTICS.items()
        for direction, semantics in table.items()
        if semantics.comparable
    }
    incomparable = {
        f"{parser_id}:{direction}"
        for parser_id, table in SEMANTICS.items()
        for direction, semantics in table.items()
        if not semantics.comparable
    }
    assert incomparable == {
        # the service-charge scope class — a printed debit count that cannot
        # enumerate the service-charge row the parser records as a debit
        "capital_one:debit",
        "texas_bank:debit",
        # W3 §COUNTSP3. The third member of that class, and the one whose cost
        # was measured before it was declined: promoting it moves 9 documents
        # from `validated/approved` to `review/integrity_flags`, every one of
        # them a ledger that reconciles to the cent. Its credit sibling IS
        # comparable, which is why this entry is pinned here by name rather
        # than the whole parser being absent from the table.
        "first_citizens:debit",
        # printed counts gated equal to LABEL-MATCHED rows, both directions
        "altana:credit",
        "altana:debit",
        # the chase reader, on a population that prints no debit count at all
        "chase_export:debit",
    }
    # The phase-2 promotions, each earned by a measured counterfactual.
    # `bank_of_america:debit` joined them in BOFA-COUNTS: it was incomparable
    # because the parser's three summary readers stored two different meanings
    # of the field, and it is comparable now because they were made to store
    # one — the raw printed figure, which reproduces the captured debit rows on
    # 344 of 344 archive documents that print it.
    assert {"chase:debit", "us_bank:credit", "us_bank:debit",
            "wilson_muir:credit", "wilson_muir:debit",
            "bank_of_america:debit"} <= comparable
    # ... and the comparable set is pinned by EQUALITY too, not just by the
    # subset above: a brand-new comparable entry is a new population that can
    # be flagged, so it must be a deliberate edit here and not something a
    # table change can slip past a subset check.
    assert comparable == {
        "apex_scanned:credit",
        "apex_scanned:debit",
        "atb:credit",
        "atb:debit",
        "bank_of_america:credit",
        "bank_of_america:debit",
        # W3 §COUNTSP3. Comparable and TAUTOLOGICAL: the parser's acceptance
        # gate already refuses a document whose row count contradicts the
        # printed count, so a claimed one agrees by construction. Surveyed
        # rather than left UNSURVEYED so the silence is a recorded fact.
        "burke_herbert:credit",
        "burke_herbert:debit",
        "capital_one:credit",
        "chase:credit",
        "chase:debit",
        "chase_export:credit",
        # W3 §COUNTSP3. The savings product reads its own SAVINGS SUMMARY
        # block; credit 10/10, debit 6/6 with 4 documents printing no debit
        # count at all. The debit denominator is 6, and the entry says so.
        "chase_savings:credit",
        "chase_savings:debit",
        # W3 §JHA-CELL. Comparable, and immune by construction: the parser's
        # claim gate now counts by the same `Transaction.direction` key this
        # check does, which is disclosed in the SEMANTICS entry rather than
        # left for someone to discover from a run of tautological `match`es.
        "community_section:credit",
        "community_section:debit",
        "dakota_west:credit",
        "dakota_west:debit",
        "demo_national:credit",
        "demo_national:debit",
        "farmers_merchants:credit",
        "farmers_merchants:debit",
        # W3 §COUNTSP3. Only the credit direction: `first_citizens:debit` is
        # pinned incomparable above, on the measured cost of the alternative.
        "first_citizens:credit",
        "first_community:credit",
        "first_community:debit",
        "first_farmers:credit",
        "first_farmers:debit",
        "ibc:credit",
        "ibc:debit",
        "linkbank:credit",
        "linkbank:debit",
        "midflorida:credit",
        "midflorida:debit",
        "mission_valley:credit",
        "mission_valley:debit",
        "rbc:credit",
        "rbc:debit",
        "rbc_french:credit",
        "rbc_french:debit",
        "scotiabank:credit",
        "scotiabank:debit",
        "southside_scanned:credit",
        "southside_scanned:debit",
        "td_canada:credit",
        "td_canada:debit",
        # W3 §COUNTSP3. The one promotion in that cell that buys real
        # information: the French text layer loses the column, the parser
        # SOLVES it from the printed running balance, and the printed count is
        # the only independent oracle on that solve.
        "td_canada_french:credit",
        "td_canada_french:debit",
        "td_canada_native:credit",
        "td_canada_native:debit",
        "texas_bank:credit",
        "us_bank:credit",
        "us_bank:debit",
        "wilson_muir:credit",
        "wilson_muir:debit",
        # W3 §CITI3 card C. Surveyed comparable at registration rather than
        # left UNSURVEYED: the printed count heads the very column whose rows
        # the parser publishes, and the parser refuses a row whose sign
        # contradicts its section, so the two sides are the same set by
        # construction. Measured 13/13 agreeing, 0 flags, before this line.
        "zions:credit",
        "zions:debit",
    }
    # Both halves cover the table exactly, so an entry cannot be dropped from
    # one set without appearing in the other.
    assert len(comparable) + len(incomparable) == 2 * len(SEMANTICS)


def test_a_promoted_entry_records_the_evidence_that_promoted_it():
    for key in ("chase:debit", "us_bank:credit", "us_bank:debit",
                "wilson_muir:credit", "wilson_muir:debit",
                "bank_of_america:debit",
                # W3 §COUNTSP3
                "chase_savings:debit",
                "td_canada_french:credit", "td_canada_french:debit"):
        parser_id, direction = key.split(":")
        reason = SEMANTICS[parser_id][direction].reason
        assert "PROMOTED" in reason, key
        assert re.search(r"\d+ of \d+|\d+/\d+", reason), key


def test_a_tautological_entry_says_so_rather_than_reading_as_evidence():
    """W3 §COUNTSP3. Three parsers agree with their printed counts because
    their own acceptance gate already required it. A run of `match` there is
    information-free, and an entry that let a reader mistake it for a measured
    agreement would be worse than no entry at all — which is the argument the
    `community_section` comment makes and this pins for the two cells that
    joined that class since."""
    for key in ("burke_herbert:credit", "burke_herbert:debit",
                "first_citizens:credit"):
        parser_id, direction = key.split(":")
        semantics = SEMANTICS[parser_id][direction]
        assert semantics.comparable is True, key
        assert "TAUTOLOG" in semantics.reason.upper(), key


#: Every direction W3 §COUNTSP3 made comparable. Enumerated rather than
#: sampled, so the falsifier test below cannot silently skip one — which is
#: exactly what it did on review (§COUNTSP3 D1) before the enumeration existed.
COUNTSP3_COMPARABLE = (
    "burke_herbert:credit", "burke_herbert:debit",
    "chase_savings:credit", "chase_savings:debit",
    "first_citizens:credit",
    "td_canada_french:credit", "td_canada_french:debit",
)

#: The ONE exclusion from the falsifier rule, and the argument for it: this
#: direction cannot be wrong, so there is nothing to state how you would find
#: out about. The parser's gate counts `a > 0` and the parser sets
#: `direction='credit'` on exactly `amount > 0`, so the gate's set and the
#: check's set are provably the same set — no document, real or constructed,
#: can make this direction disagree. Its DEBIT sibling gets no such exemption:
#: there the two keys diverge on a $0.00 row, so it carries a falsifier.
FALSIFIER_EXEMPT = ("burke_herbert:credit",)


def test_the_countsp3_promotions_each_carry_a_falsifier():
    """The idiom `first_community` established and `bank_of_america:debit`
    made standing: an entry that can be wrong has to say how you would find
    out.

    Every direction COUNTS-P3 made comparable states one, with a single
    exemption that is NAMED rather than omitted — `FALSIFIER_EXEMPT` above
    carries the argument. The exemption list is asserted to be exactly that
    one key, so exempting a second direction is a deliberate edit here.
    """
    assert FALSIFIER_EXEMPT == ("burke_herbert:credit",)
    assert set(FALSIFIER_EXEMPT) <= set(COUNTSP3_COMPARABLE)
    for key in COUNTSP3_COMPARABLE:
        parser_id, direction = key.split(":")
        semantics = SEMANTICS[parser_id][direction]
        assert semantics.comparable is True, key
        if key in FALSIFIER_EXEMPT:
            continue
        assert "FALSIFIER" in semantics.reason, key


def test_a_service_charge_entry_says_whether_its_control_arm_was_exercised():
    """W3 §COUNTSP3 D2. Two of the promoted debit directions print the
    capital_one-shaped `Checks/Debits` label, and NEITHER has a charged
    document in the archive to test the scope against: `burke_herbert` bills
    zero on all 3, `chase_savings` prints no `Fees` row on any of 10. Both
    entries are therefore resting on construction rather than on a control
    arm, and both must say so — the asymmetry the review caught was one entry
    disclosing it and the other asserting the conclusion flat.

    The standard is COUNTS-P1's: `+1 always` and `+1 iff charged` were
    indistinguishable on 12 all-charged capital_one documents, and an
    unexercised arm is the same hazard wearing the opposite sign.
    """
    for key in ("burke_herbert:debit", "chase_savings:debit"):
        parser_id, direction = key.split(":")
        reason = SEMANTICS[parser_id][direction].reason
        assert "capital_one" in reason, key
        # the population that does NOT exist, stated as a number
        assert re.search(r"all 3 archive documents bill a ZERO charge"
                         r"|0 of the 10 archive\s+documents print a `Fees` row",
                         reason), key
        # ... and the word for what is carrying the claim instead
        assert "construction" in reason or "not evidence" in reason, key


def test_the_first_citizens_debit_entry_carries_the_mapping_and_its_cost():
    """W3 §COUNTSP3. §FI14.3 recommended a COMPARABLE entry off one pinned
    document and then corrected itself; the correction is what this pins. The
    entry must carry the mapping AND the measured price of ignoring it, so the
    next reader cannot re-derive the promotion from the 26 documents where the
    two sides happen to agree."""
    reason = SEMANTICS["first_citizens"]["debit"].reason
    assert SEMANTICS["first_citizens"]["debit"].comparable is False
    assert "stated_debit_count + 1" in reason
    # the two arms, and which one each is
    assert "26 agree exactly" in reason and "9 disagree by exactly +1" in reason
    # the measured consequence of promoting it anyway
    assert "review/integrity_flags" in reason
    # ... and the clause the capital_one entry does not need: a billed charge
    # whose itemisation could not be found is +0, not +1.
    assert "RECOVERED AS A POSTING" in reason


def test_the_td_canada_french_promotion_argues_its_own_independence():
    """The expected side is an oracle on a SOLVED column, so independence is
    the whole of the argument: the solver must not be able to read the count
    it is being checked against."""
    for direction in DIRECTIONS:
        semantics = SEMANTICS["td_canada_french"][direction]
        assert semantics.comparable is True
    reason = SEMANTICS["td_canada_french"]["credit"].reason
    assert "_resolve_directions" in reason
    assert "never reads" in reason
    # the four disagreeing documents are disclosed as already-withheld rather
    # than quietly omitted from the denominator
    assert "13 archive documents" in reason
    assert "9 of 13 agree, 4 of 13 disagree" in reason


def test_the_bofa_debit_promotion_carries_its_falsifier():
    """The promotion rests on one measured claim — that BofA's printed
    `# of withdrawals/debits` already counts the cheque block. An entry that
    can be wrong has to say how you would find out, in the idiom the
    first_community entry established."""
    reason = SEMANTICS["bank_of_america"]["debit"].reason
    assert "FALSIFIER" in reason
    assert "Total # of checks" in reason
    # ... and it must not quietly become an argument from our own rows.
    assert "Independence holds" in reason


def test_an_unsurveyed_parser_is_incomparable_rather_than_assumed_comparable():
    for parser_id in (None, "", "a_parser_nobody_surveyed", UNSURVEYED_REGISTRATION):
        for direction in DIRECTIONS:
            assert semantics_for(parser_id, direction) is UNSURVEYED, parser_id
            assert counts_comparable(parser_id, direction) is False, parser_id


def test_the_unsurveyed_witness_is_a_real_registration_that_prints_a_count():
    """If this parser ever joins the table the test above stops proving
    anything, so it says out loud what it depends on."""
    assert pr.by_id(UNSURVEYED_REGISTRATION) is not None
    assert UNSURVEYED_REGISTRATION not in SEMANTICS


def test_the_section_level_oracles_are_disclosed_and_never_compared():
    assert set(SECTION_LEVEL_ORACLES) == {"pnc", "wells_fargo"}
    assert not set(SECTION_LEVEL_ORACLES) & set(SEMANTICS)
    for parser_id in SECTION_LEVEL_ORACLES:
        for direction in DIRECTIONS:
            assert counts_comparable(parser_id, direction) is False


def test_an_unknown_direction_is_an_error_rather_than_a_default():
    with pytest.raises(ValueError):
        semantics_for("rbc", "sideways")


def test_the_observer_and_the_check_read_one_table():
    """The instrument that PREDICTS the flag population and the code that
    EMITS it must not be able to disagree."""
    import analysis.count_semantics as production
    import telemetry.stated_counts as observer

    assert observer.SEMANTICS is production.SEMANTICS
    assert observer.UNSURVEYED is production.UNSURVEYED
    assert observer.semantics_for is production.semantics_for
    assert observer.SECTION_LEVEL_ORACLES is production.SECTION_LEVEL_ORACLES


def test_the_observer_version_moves_when_the_table_does():
    """W3 §COUNTSP3 D5. `OBSERVER_VERSION`'s own contract is "bumped when the
    vocabulary, the evaluation order or the semantics table changes", so that
    two measurement runs over one archive can be told apart. Nothing enforced
    it, and COUNTS-P2's table change reached production with the version
    already stale by the time COUNTS-P3 read it.

    Pinning the version against the table's SHAPE is what makes the contract
    self-enforcing: adding, removing or re-classifying an entry fails here
    until the version is deliberately moved and its comment says what moved.
    """
    import telemetry.stated_counts as observer

    comparable = sum(
        1 for table in SEMANTICS.values()
        for semantics in table.values() if semantics.comparable
    )
    assert (observer.OBSERVER_VERSION, len(SEMANTICS), comparable) == (3, 31, 56)


# ---------------------------------------------------------------------------
# reconcile: the measurement (section 7.1)
# ---------------------------------------------------------------------------


def test_matching_counts_record_true_and_the_captured_totals():
    recon = reconcile(statement(rows=[txn(75.0, "credit"), txn(-25.0, "debit")], credit=1, debit=1))
    assert recon.stated_credit_count_matches is True
    assert recon.stated_debit_count_matches is True
    assert (recon.captured_credit_count, recon.captured_debit_count) == (1, 1)
    assert recon.ok is True and recon.issues == []


def test_a_row_on_the_wrong_side_is_caught_in_both_directions():
    """The RBC class: the money is identical, the columns are not."""
    rows = [txn(75.0, "credit"), txn(-25.0, "credit"), txn(-30.0, "debit")]
    recon = reconcile(statement(rows=rows, credit=1, debit=2))
    assert recon.stated_credit_count_matches is False
    assert recon.stated_debit_count_matches is False
    assert (recon.captured_credit_count, recon.captured_debit_count) == (2, 1)
    # ... and the money check saw nothing, which is the entire argument.
    assert recon.ok is True and recon.issues == []


def test_the_count_is_keyed_on_the_printed_column_not_the_sign():
    """`metrics.py:186-191` counts `amount >= 0` as a deposit, so a zero-amount
    row lands in the credit bucket whatever column printed it. 214 such rows
    exist in the archive and 214 of them are printed as DEBITS."""
    rows = [txn(75.0, "credit"), txn(0.0, "debit", "RETURNED ITEM"), txn(-75.0, "debit")]
    recon = reconcile(statement(rows=rows, credit=1, debit=2))
    assert (recon.captured_credit_count, recon.captured_debit_count) == (1, 2)
    assert recon.stated_credit_count_matches is True
    assert recon.stated_debit_count_matches is True
    # The counterfactual, computed the way a sign-keyed check would: 2 credits
    # and 1 debit — a correct document called wrong in both directions.
    by_sign_credit = sum(1 for t in rows if t.amount >= 0)
    assert by_sign_credit == 2 != recon.captured_credit_count


def test_an_absent_printed_count_is_not_applicable_and_never_a_zero():
    recon = reconcile(statement(rows=[txn(75.0, "credit"), txn(-25.0, "debit")], credit=None, debit=None))
    assert recon.stated_credit_count_matches is None
    assert recon.stated_debit_count_matches is None
    assert recon.captured_credit_count is None
    assert recon.captured_debit_count is None


def test_one_printed_direction_is_never_inferred_from_the_other():
    recon = reconcile(statement(rows=[txn(75.0, "credit"), txn(-25.0, "debit")], credit=1, debit=None))
    assert recon.stated_credit_count_matches is True
    assert recon.stated_debit_count_matches is None
    assert recon.captured_debit_count is None


def test_an_aggregate_backed_statement_is_not_applicable_whatever_the_counts_say():
    rows = [txn(75.0, "credit", "UNCAPTURED ACTIVITY"), txn(-25.0, "debit")]
    recon = reconcile(statement(rows=rows, credit=99, debit=99))
    assert recon.stated_credit_count_matches is None
    assert recon.stated_debit_count_matches is None


def test_a_statement_with_no_rows_at_all_is_not_applicable():
    recon = reconcile(Statement(bank="Test Bank", beginning_balance=100.0, ending_balance=100.0,
                                stated_credit_count=4, stated_debit_count=4, transactions=[]))
    assert recon.stated_credit_count_matches is None
    assert recon.captured_credit_count is None


def test_reversals_are_counted_gross():
    """The money coverage nets settlement reversals because banks do; a
    reversal is still a printed row the bank counted, so the COUNT does not."""
    rows = [
        txn(500.0, "credit", "DEPOSIT"),
        txn(-500.0, "debit", "RETURNED DEPOSIT ITEM"),
        txn(-25.0, "debit", "FEE"),
    ]
    recon = reconcile(statement(rows=rows, credit=1, debit=2))
    assert (recon.captured_credit_count, recon.captured_debit_count) == (1, 2)
    assert recon.stated_credit_count_matches is True
    assert recon.stated_debit_count_matches is True


def test_the_count_check_appends_no_reconciliation_issue_ever():
    """Phase-1 invariant, still binding: `ok` gates the ADB, so an issue here
    would withhold the document. Compared against the same statement with the
    printed counts removed — the issue list must be identical."""
    rows = [txn(75.0, "credit"), txn(-25.0, "credit"), txn(-30.0, "debit")]
    disagreeing = reconcile(statement(rows=rows, credit=1, debit=2))
    silent = reconcile(statement(rows=rows, credit=None, debit=None))
    assert disagreeing.issues == silent.issues
    assert disagreeing.ok == silent.ok is True


def test_the_expected_side_is_the_printed_field_not_the_copy_metrics_publishes():
    """Independence. `metrics` OVERWRITES its published deposit count with the
    bank's printed figure (`metrics.py:353-356`), so a check that read it back
    would let a parser satisfy itself with its own input."""
    rows = [txn(75.0, "credit"), txn(-25.0, "credit"), txn(-30.0, "debit")]
    stmt = statement(rows=rows, credit=1, debit=2)
    recon = reconcile(stmt)
    metrics = compute_metrics(stmt, trust_stated_summary=True)
    # metrics publishes the BANK's numbers ...
    assert metrics.effective_num_deposits == 1
    assert metrics.effective_num_withdrawals == 2
    # ... and the check still reports OUR rows, and still disagrees.
    assert (recon.captured_credit_count, recon.captured_debit_count) == (2, 1)
    assert recon.stated_credit_count_matches is False
    source = (ROOT / "analysis" / "reconcile.py").read_text(encoding="utf-8")
    assert "effective_num" not in source
    assert "num_deposits" not in source


# ---------------------------------------------------------------------------
# pipeline: the consequence (section 7.2, amended)
# ---------------------------------------------------------------------------


def test_a_comparable_mismatch_flags_both_directions_and_routes_to_review():
    rows = [txn(75.0, "credit"), txn(-25.0, "credit"), txn(-30.0, "debit")]
    recon, integrity = integrity_for(statement(rows=rows, credit=1, debit=2), COMPARABLE)
    assert integrity.flags == list(COUNT_FLAGS)
    assert integrity.risk_level == "review"
    # Flag, never withhold: no issue, no possible_document_issue, ADB intact.
    assert recon.ok is True
    assert integrity.possible_document_issue is False


def test_the_notes_name_the_finding_and_carry_no_document_content():
    """H3_SCHEMA I1: notes travel into durable job records. Names only — the
    counts themselves are integers, but they are document content."""
    rows = [txn(75.0, "credit"), txn(-25.0, "credit"), txn(-30.0, "debit")]
    _recon, integrity = integrity_for(statement(rows=rows, credit=1, debit=2), COMPARABLE)
    notes = [note for note in integrity.notes if "count" in note]
    assert notes == [
        "captured credit rows do not match the bank-stated credit count",
        "captured debit rows do not match the bank-stated debit count",
    ]
    for note in notes:
        assert not re.search(r"\d", note)


def test_a_matching_document_flags_nothing():
    _recon, integrity = integrity_for(
        statement(rows=[txn(75.0, "credit"), txn(-25.0, "debit")], credit=1, debit=1), COMPARABLE
    )
    assert integrity.flags == []
    assert integrity.risk_level == "clear"


@pytest.mark.parametrize(
    "parser_id,direction",
    [
        (parser_id, direction)
        for parser_id, table in sorted(SEMANTICS.items())
        for direction in DIRECTIONS
        if not table[direction].comparable
    ],
)
def test_an_incomparable_direction_can_never_flag(parser_id, direction):
    """Every incomparable entry in the table, against rows built to disagree
    with the printed figure in BOTH directions. The prohibition is structural:
    it is a gate in the emitting code, not a caller's good manners."""
    rows = [txn(75.0, "credit"), txn(-25.0, "credit"), txn(-30.0, "debit")]
    stmt = statement(rows=rows, credit=99, debit=99)
    recon, integrity = integrity_for(stmt, parser_id)
    # The measurement is still taken and still disagrees ...
    assert getattr(recon, f"stated_{direction}_count_matches") is False
    # ... and the flag for THIS direction is nonetheless absent.
    assert f"{direction}_count_mismatch" not in integrity.flags


def test_an_unsurveyed_parser_can_never_flag():
    """The property that makes a NEW parser registration safe: a parser that
    starts populating a printed count without a semantics entry emits nothing,
    by default, structurally. A cell landing new layouts in parallel with this
    check cannot move a document to review by accident."""
    rows = [txn(75.0, "credit"), txn(-25.0, "credit"), txn(-30.0, "debit")]
    stmt = statement(rows=rows, credit=99, debit=99)
    recon, integrity = integrity_for(stmt, UNSURVEYED_REGISTRATION)
    assert recon.stated_credit_count_matches is False
    assert recon.stated_debit_count_matches is False
    assert integrity.flags == []


def test_a_not_applicable_measurement_never_flags():
    """`is False`, not `not ...`: None is not-applicable and must stay quiet.
    Pinned on the two populations that produce it."""
    rows = [txn(75.0, "credit"), txn(-25.0, "debit")]
    for stmt in (
        statement(rows=rows, credit=None, debit=None),                       # not printed
        statement(rows=[txn(75.0, "credit", "UNCAPTURED ACTIVITY")],         # aggregate-backed
                  credit=99, debit=99),
    ):
        recon, integrity = integrity_for(stmt, COMPARABLE)
        assert recon.stated_credit_count_matches is None
        assert not [flag for flag in integrity.flags if flag in COUNT_FLAGS]


def test_a_document_class_that_is_not_a_formal_statement_never_flags():
    rows = [txn(75.0, "credit"), txn(-25.0, "credit"), txn(-30.0, "debit")]
    stmt = statement(rows=rows, credit=1, debit=2, bank="Chase Transaction Export")
    registration = pr.by_id("chase_export")
    assert registration.formal_statement is False
    recon, integrity = integrity_for(stmt, "chase_export")
    assert recon.stated_credit_count_matches is False
    assert "not_a_formal_statement" in integrity.flags
    assert not [flag for flag in integrity.flags if flag in COUNT_FLAGS]


def test_an_unclaimed_document_never_flags_on_a_bank_label_alone():
    """`_registration_for` falls back to the bank label for an LLM extraction,
    which is right for document knowledge and wrong for count semantics: the
    table is evidence about what a PARSER's reader produced. No claim, no
    flag."""
    rows = [txn(75.0, "credit"), txn(-25.0, "credit"), txn(-30.0, "debit")]
    stmt = statement(rows=rows, credit=1, debit=2, bank="RBC Royal Bank")
    recon = reconcile(stmt)
    integrity = assess_document_integrity(stmt, recon, quality(), markdown="x", dispatch=None)
    assert recon.stated_credit_count_matches is False
    assert integrity.flags == []


def test_an_ambiguous_dispatch_never_flags():
    """Two parsers claimed it, so no parser's semantics are established."""
    rows = [txn(75.0, "credit"), txn(-25.0, "credit"), txn(-30.0, "debit")]
    stmt = statement(rows=rows, credit=1, debit=2)
    dispatch = pr.Dispatch("ambiguous", candidates=(("rbc", 1.0), ("scotiabank", 1.0)))
    recon = reconcile(stmt)
    integrity = assess_document_integrity(stmt, recon, quality(), markdown="x", dispatch=dispatch)
    assert "parser_ambiguous" in integrity.flags
    assert not [flag for flag in integrity.flags if flag in COUNT_FLAGS]


def test_only_the_disagreeing_direction_flags():
    rows = [txn(75.0, "credit"), txn(-25.0, "debit"), txn(-30.0, "debit")]
    _recon, integrity = integrity_for(statement(rows=rows, credit=1, debit=99), COMPARABLE)
    assert integrity.flags == ["debit_count_mismatch"]


# ---------------------------------------------------------------------------
# the consequence, end to end
# ---------------------------------------------------------------------------


def test_a_count_mismatch_is_review_and_never_withheld():
    payload = {
        "metrics": {"average_daily_balance": 1234.56},
        "quality": {"corporate_use": "approved"},
        "integrity": {"flags": ["credit_count_mismatch"]},
    }
    assert classify_outcome(payload) == ("review", "integrity_flags")


def test_both_codes_are_registered_and_classed_with_the_money_coverage_flags():
    for flag in COUNT_FLAGS:
        assert flag in INTEGRITY_FLAGS
        assert CLASS_OF[f"integrity:{flag}"] == "detail_coverage"


def test_the_check_is_not_wired_into_the_withholding_path():
    """Grep-level guard on the one thing this design may never become: the
    count must not reach `issues`, and the flag must not reach
    `possible_document_issue`."""
    reconcile_source = (ROOT / "analysis" / "reconcile.py").read_text(encoding="utf-8")
    count_block = reconcile_source.split("credit_count_matches = debit_count_matches = None")[1]
    count_block = count_block.split("ok = not issues")[0]
    assert "issues.append" not in count_block

    pipeline_source = (ROOT / "analysis" / "pipeline.py").read_text(encoding="utf-8")
    issue_clause = pipeline_source.split("possible_document_issue = (")[1].split(")\n")[0]
    for flag in COUNT_FLAGS:
        assert flag not in issue_clause
