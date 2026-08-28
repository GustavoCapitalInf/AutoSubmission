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
from dataclasses import fields
from pathlib import Path

import pytest

from analysis import parser_registry as pr
from analysis import parser_registry_entries  # noqa: F401  — populates the registry
from analysis.count_semantics import (
    DIRECTIONS,
    PRINTED_EVIDENCE_FIELDS,
    RULES,
    SECTION_LEVEL_ORACLES,
    SEMANTICS,
    UNSURVEYED,
    CountMapping,
    CountSemantics,
    claiming_parser_id,
    counts_comparable,
    expected_count,
    printed_evidence,
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
    # `analysis/pipeline.py` derives the reconciler's key and the flag gate's
    # key from ONE function, so this helper does too — a fixture that reconciled
    # without the claim would test a comparison production never runs.
    recon = reconcile(stmt, parser_id=claiming_parser_id(dispatch))
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
        # The last member of the service-charge scope class still without a
        # mapping. W3 §COUNTSMAP promoted the other two on the `mapping` field
        # and deliberately did not touch this one: it was outside that cell's
        # named populations, and an entry is promoted by the cell that measured
        # it. Its counterfactual is recorded there (1 document, +1, and 1 of 1
        # under the same `plus_one_when_billed` mapping) so the decision is one
        # line of Ocean's rather than a re-derivation.
        "texas_bank:debit",
        # printed counts gated equal to LABEL-MATCHED rows, both directions
        "altana:credit",
        "altana:debit",
        # the chase reader, on a population that prints no debit count at all
        "chase_export:debit",
        # W3 FROSTOZK. Measured, not unread: the printed withdrawal figure
        # excludes two named row classes this reader posts, the excess is
        # exactly their size on 9 of 9 archive documents, and BOTH terms are
        # facts about our rows - so the difference is understood and still not
        # expressible as printed evidence. The family prints no service-charge
        # summary cell at all, so there is nothing a mapping could read.
        "frost:debit",
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
        # W3 §WELCH. Comparable and TAUTOLOGICAL on both directions: the
        # parser refuses a document whose row count contradicts either printed
        # count before it publishes, so the check is provably inert and the
        # entry says so. Surveyed rather than UNSURVEYED so the silence is a
        # recorded fact.
        "welch_state_bank:credit",
        "welch_state_bank:debit",
        "apex_scanned:credit",
        "apex_scanned:debit",
        "atb:credit",
        "atb:debit",
        "bank_of_america:credit",
        "bank_of_america:debit",
        # W3 FROSTOZK. Comparable and TAUTOLOGICAL in both directions, and the
        # entries say so: this layout does not print the direction of a row at
        # all, so the reader SOLVES it against the printed daily balances and
        # consumes these two counts as the constraint that makes the solve
        # unique. Surveyed rather than left UNSURVEYED so the silence is a
        # recorded fact.
        "bank_ozk:credit",
        "bank_ozk:debit",
        # W3 §COUNTSP3. Comparable and TAUTOLOGICAL: the parser's acceptance
        # gate already refuses a document whose row count contradicts the
        # printed count, so a claimed one agrees by construction. Surveyed
        # rather than left UNSURVEYED so the silence is a recorded fact.
        "burke_herbert:credit",
        "burke_herbert:debit",
        "capital_one:credit",
        # W3 §COUNTSMAP. Comparable ONLY through its mapping: the printed
        # 'N Checks/Debits' figure excludes the separately-printed service
        # charge the parser records as a debit row, and the mapping is that
        # one row. 22 of 22 under it; a plain COMPARABLE was measured at 11
        # `validated` -> `review`, four of them pinned corpus documents.
        "capital_one:debit",
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
        # W3 §GRAM4. A new registration, surveyed by the cell that registered
        # it. Comparable as a CATEGORY SUM in both directions — three printed
        # categories per direction — and tautological for the same structural
        # reason `community_section` is: the parser gates each category's
        # printed count against the rows of the section that category heads,
        # and takes `Transaction.direction` from the category. It cannot
        # under-count the expected side either: the six-category list is
        # closed and a summary missing one refuses the document.
        "core_processor_counted:credit",
        "core_processor_counted:debit",
        "dakota_west:credit",
        "dakota_west:debit",
        "demo_national:credit",
        "demo_national:debit",
        "farmers_merchants:credit",
        "farmers_merchants:debit",
        # W3 §COUNTSP3 promoted the credit direction (a tautology, disclosed);
        # W3 §COUNTSMAP promoted the debit direction on its mapping, 35 of 35.
        # The debit direction is the informative one of the pair: it is the
        # only per-document check that the service-charge posting was recovered.
        "first_citizens:credit",
        "first_citizens:debit",
        "first_community:credit",
        "first_community:debit",
        "first_farmers:credit",
        "first_farmers:debit",
        # W3 FROSTOZK. Comparable and NOT tautological, which took a build
        # decision: the reader gates on the printed TOTALS and on the two ends
        # of the daily grid, and on no printed COUNT, so this check is a live
        # defect detector on the one direction of this bank where the printed
        # count means our rows. Its debit twin is in the incomparable set above.
        "frost:credit",
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
                "td_canada_french:credit", "td_canada_french:debit",
                # W3 §COUNTSMAP
                "capital_one:debit", "first_citizens:debit"):
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
                "first_citizens:credit",
                # W3 §WELCH, which joined the class for the same reason and
                # states it in the same idiom.
                "welch_state_bank:credit", "welch_state_bank:debit"):
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
    """W3 §COUNTSP3, then §COUNTSMAP. §FI14.3 recommended a COMPARABLE entry
    off one pinned document and then corrected itself; COUNTS-P3 recorded the
    mapping in prose because the schema could not hold it; this cell installed
    the schema and promoted the direction ON the mapping.

    The entry must still carry both arms AND the measured price of promoting it
    with the mapping blind, so the next reader cannot re-derive a plain
    equality entry from the 26 documents where the two sides happen to agree.
    """
    semantics = SEMANTICS["first_citizens"]["debit"]
    reason = semantics.reason
    assert semantics.comparable is True
    assert semantics.mapping is not None
    assert semantics.mapping.rule == "plus_one_when_billed"
    assert semantics.mapping.printed_field == "stated_service_charge"
    # the two arms, and which one each is
    assert "26 agree exactly" in reason and "9 disagree by exactly +1" in reason
    # the measured consequence of promoting it WITHOUT the mapping
    assert "review/integrity_flags" in reason
    # ... and the clause §FI14.3 asked for, which is deliberately NOT in the
    # mapping: "was the charge recovered as a posting" is a fact about OUR
    # rows, and an expected side that reads the captured side is not
    # independent of it. The entry has to say so rather than omit it.
    assert "RECOVERED AS A POSTING" in reason
    assert "DELIBERATELY" in reason and "ABSENT" in reason
    # the arm that does not exist, stated as a number rather than smoothed over
    assert "0 documents exercise the" in reason


def test_the_capital_one_entry_records_the_money_side_and_its_correction():
    """W3 §COUNTSMAP. The entry inherited an unmeasured sentence from COUNTS-P1
    — that the charge's money sits INSIDE the printed debit total — and the
    measurement says the opposite on 12 of 12 billed documents. It matters
    twice: it is the argument that count scope and money scope agree here
    (BofA's defect was that they did not), and the platform's own
    `_debit_coverage_target` has been applying the identical `+ service_charge`
    adjustment to the TOTAL since before this table existed, which is the
    precedent the count mapping stands on."""
    reason = SEMANTICS["capital_one"]["debit"].reason
    assert "_debit_coverage_target" in reason
    assert "OUTSIDE the printed" in reason and "12 of 12" in reason
    assert "corrected here" in reason


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
    assert set(SECTION_LEVEL_ORACLES) == {
        "core_processor_enclosures", "pnc", "wells_fargo"}
    assert not set(SECTION_LEVEL_ORACLES) & set(SEMANTICS)
    for parser_id in SECTION_LEVEL_ORACLES:
        for direction in DIRECTIONS:
            assert counts_comparable(parser_id, direction) is False


def test_an_unknown_direction_is_an_error_rather_than_a_default():
    with pytest.raises(ValueError):
        semantics_for("rbc", "sideways")


def test_the_observer_and_the_check_read_one_table():
    """The instrument that PREDICTS the flag population and the code that
    EMITS it must not be able to disagree — about the table OR about the
    arithmetic it is applied with. W3 §COUNTSMAP added the second half: one
    shared table and two different adjustments is the same defect wearing a
    different hat."""
    import analysis.count_semantics as production
    import telemetry.stated_counts as observer

    assert observer.SEMANTICS is production.SEMANTICS
    assert observer.UNSURVEYED is production.UNSURVEYED
    assert observer.semantics_for is production.semantics_for
    assert observer.SECTION_LEVEL_ORACLES is production.SECTION_LEVEL_ORACLES
    assert observer.expected_count is production.expected_count


def test_the_observer_version_moves_when_the_table_does():
    """W3 §COUNTSP3 D5. `OBSERVER_VERSION`'s own contract is "bumped when the
    vocabulary, the evaluation order or the semantics table changes", so that
    two measurement runs over one archive can be told apart. Nothing enforced
    it, and COUNTS-P2's table change reached production with the version
    already stale by the time COUNTS-P3 read it.

    Pinning the version against the table's SHAPE is what makes the contract
    self-enforcing: adding, removing or re-classifying an entry fails here
    until the version is deliberately moved and its comment says what moved.

    W3 §COUNTSMAP widened the shape to include the MAPPED count, because a
    mapping changes which documents report `match` just as surely as a
    promotion does — `capital_one:debit` alone moves 12 documents from
    `semantics_incomparable` to `match` and would have moved them to `mismatch`
    without it.
    """
    import telemetry.stated_counts as observer

    comparable = sum(
        1 for table in SEMANTICS.values()
        for semantics in table.values() if semantics.comparable
    )
    mapped = sum(
        1 for table in SEMANTICS.values()
        for semantics in table.values() if semantics.mapping is not None
    )
    assert (observer.OBSERVER_VERSION, len(SEMANTICS), comparable, mapped) == (6, 35, 65, 2)


# ---------------------------------------------------------------------------
# The mapping (W3 §COUNTSMAP)
# ---------------------------------------------------------------------------

#: Every direction the table MAPS, enumerated rather than discovered — the
#: idiom §COUNTSP3 D1 established after a hand-written list silently lost two
#: entries. A new mapping is a deliberate edit here before any test below can
#: cover it.
MAPPED = ("capital_one:debit", "first_citizens:debit")


def test_the_mapped_set_is_pinned_and_every_mapping_is_a_closed_lookup():
    """A mapping changes the EXPECTED side of a live integrity check, so it is
    pinned exactly like a promotion — and it has to be auditable by reading the
    table, which means data and never a callable."""
    mapped = {
        f"{parser_id}:{direction}"
        for parser_id, table in SEMANTICS.items()
        for direction, semantics in table.items()
        if semantics.mapping is not None
    }
    assert mapped == set(MAPPED)
    for key in MAPPED:
        parser_id, direction = key.split(":")
        semantics = SEMANTICS[parser_id][direction]
        mapping = semantics.mapping
        assert semantics.comparable is True, key
        assert mapping.rule in RULES, key
        assert mapping.printed_field in PRINTED_EVIDENCE_FIELDS, key
        # the sentence the mapping is making, in the bank's own vocabulary
        assert "service charge" in mapping.excluded_row_class, key
        assert not any(callable(getattr(mapping, f.name)) for f in fields(mapping)), key


def test_each_mapped_promotion_carries_a_falsifier_and_says_what_it_is_worth():
    """The standing idiom (`first_community`, then BofA, then §COUNTSP3): an
    entry that can be wrong has to say how you would find out — and, since
    §COUNTSP3, an entry that CANNOT be wrong has to say that instead. Both
    mapped directions can be wrong, both state the tell, and both say out loud
    that they are not restating an acceptance gate."""
    for key in MAPPED:
        parser_id, direction = key.split(":")
        reason = SEMANTICS[parser_id][direction].reason
        assert "PROMOTED" in reason, key
        assert "FALSIFIER" in reason, key
        # the tell, in the shape the two share
        assert "printed + 1" in reason, key
        assert "TAUTOLOGY" in reason.upper(), key


def test_a_rule_cannot_be_named_without_being_implemented():
    """`RULES` is DERIVED from the arithmetic rather than restated beside it,
    so a second rule cannot be added to the vocabulary while `adjustment`
    silently keeps applying the first one."""
    from analysis.count_semantics import _RULE_ADJUSTMENTS

    assert RULES == tuple(_RULE_ADJUSTMENTS)
    assert all(callable(fn) for fn in _RULE_ADJUSTMENTS.values())


def test_a_mapping_can_only_be_built_out_of_the_closed_vocabulary():
    """Checked in the dataclass, not at the call site: an entry that could not
    be applied must not be writable in the first place."""
    ok = dict(rule="plus_one_when_billed", printed_field="stated_service_charge",
              excluded_row_class="the monthly service charge")
    assert CountMapping(**ok).adjustment({"stated_service_charge": 1.0}) == 1
    for broken in (
        dict(ok, rule="plus_two_when_it_feels_right"),
        dict(ok, printed_field="transactions"),
        dict(ok, printed_field="captured_debit_count"),
        dict(ok, excluded_row_class=""),
    ):
        with pytest.raises(ValueError):
            CountMapping(**broken)


def test_a_mapping_may_read_bank_printed_evidence_only():
    """Independence, structurally rather than by good manners. The expected
    side may be adjusted only by figures a parser lifted off the printed
    summary; the moment it can read something derived from `transactions`, a
    parser satisfies the check with its own output — which is the one property
    this whole check exists to have."""
    for name in PRINTED_EVIDENCE_FIELDS:
        assert name in Statement.model_fields, name
        assert name.startswith("stated_"), name
        assert "Transaction" not in str(Statement.model_fields[name].annotation), name
    assert "transactions" not in PRINTED_EVIDENCE_FIELDS
    with pytest.raises(ValueError):
        printed_evidence({"transactions": []}, "transactions")


def test_a_mapping_requires_a_comparable_direction():
    """An entry that declares an adjustment and then refuses to compare leaves
    the adjustment unreachable — a decision that has not been made, wearing the
    costume of one."""
    with pytest.raises(ValueError):
        CountSemantics(
            comparable=False,
            scope="service_charge_excluded_from_printed_debit_count",
            reason="x" * 60,
            mapping=CountMapping(
                rule="plus_one_when_billed",
                printed_field="stated_service_charge",
                excluded_row_class="the monthly service charge",
            ),
        )


def test_expected_count_is_the_identity_wherever_there_is_no_mapping():
    """29 of the 31 parsers in the table, and everything outside it. The field
    arrived without moving any of them, and this is what says so — rather than
    the absence of a failing test."""
    billed = {"stated_service_charge": 25.0}  # a mapping WOULD fire on this
    for parser_id, table in SEMANTICS.items():
        for direction, semantics in table.items():
            if semantics.mapping is not None:
                continue
            assert expected_count(parser_id, direction, 7, billed) == 7, f"{parser_id}:{direction}"
    for parser_id in (None, "", "a_parser_nobody_surveyed", UNSURVEYED_REGISTRATION):
        for direction in DIRECTIONS:
            assert expected_count(parser_id, direction, 7, billed) == 7, parser_id


def test_a_zero_or_refunded_charge_adjusts_by_nothing():
    """`> 0`, not truthiness of a signed number. `stated_service_charge` is a
    MAGNITUDE, so a refund can only ever arrive as a sign or not at all — and
    a refund is a CREDIT row, which adds nothing to the debit side. Everything
    unreadable fails closed the same way."""
    mapping = SEMANTICS["capital_one"]["debit"].mapping
    assert mapping.adjustment({"stated_service_charge": 15.0}) == 1
    for absent in ({"stated_service_charge": 0.0}, {"stated_service_charge": None},
                   {"stated_service_charge": -15.0}, {"stated_service_charge": True},
                   {"stated_service_charge": "15.00"}, {}):
        assert mapping.adjustment(absent) == 0, absent


@pytest.mark.parametrize("key", MAPPED)
def test_the_mapping_reads_a_statement_and_a_serialized_one_identically(key):
    """`reconcile` holds a `Statement`; the phase-1 count observer holds the
    payload the artifact cache stored. Two shapes, one answer, or the
    instrument and the emitter disagree about which documents are clean."""
    parser_id, direction = key.split(":")
    stmt = statement(rows=[txn(-25.0, "debit")], credit=None, debit=1,
                     stated_service_charge=15.0)
    assert expected_count(parser_id, direction, 1, stmt) == 2
    assert expected_count(parser_id, direction, 1, stmt.model_dump()) == 2


@pytest.mark.parametrize("key", MAPPED)
def test_a_billed_charge_is_the_one_row_the_printed_count_does_not_carry(key):
    """The measured arm: 12 of 22 capital_one and 9 of 35 first_citizens
    documents, every one a ledger that reconciles to the cent, every one +1."""
    parser_id, _direction = key.split(":")
    rows = [txn(100.0, "credit"), txn(-40.0, "debit"), txn(-30.0, "debit"),
            txn(-15.0, "debit", "SERVICE CHARGE")]
    stmt = statement(rows=rows, credit=1, debit=2, stated_service_charge=15.0)
    recon, integrity = integrity_for(stmt, parser_id)
    assert (recon.captured_debit_count, recon.expected_debit_count) == (3, 3)
    assert recon.stated_debit_count_matches is True
    assert integrity.flags == []
    # the credit direction is untouched: a mapping applies to the ONE direction
    # it is declared on.
    assert (recon.captured_credit_count, recon.expected_credit_count) == (1, 1)


@pytest.mark.parametrize("key", MAPPED)
def test_a_zero_charge_document_is_compared_against_the_printed_figure(key):
    """The control arm — 10 of 22 and 26 of 35 — and the reason '+1 always' and
    '+1 iff charged' are distinguishable on this archive at all."""
    parser_id, _direction = key.split(":")
    rows = [txn(100.0, "credit"), txn(-40.0, "debit"), txn(-30.0, "debit")]
    stmt = statement(rows=rows, credit=1, debit=2, stated_service_charge=0.0)
    recon, integrity = integrity_for(stmt, parser_id)
    assert (recon.captured_debit_count, recon.expected_debit_count) == (2, 2)
    assert recon.stated_debit_count_matches is True
    assert integrity.flags == []


@pytest.mark.parametrize("key", MAPPED)
def test_the_mapping_catches_a_dropped_row_the_equality_test_is_blind_to(key):
    """THE CONSTRUCTED GENUINE MISMATCH, and the whole argument for the field.

    The bank printed `Checks/Debits (2)` and billed a charge, so a complete
    ledger carries THREE debit rows. This one carries two: the charge row is
    there and one printed row was dropped. Captured is off by two errors that
    cancel.

    The unmapped equality test compares 2 against the printed 2 and reports
    MATCH — a ledger missing a posting, called clean. The mapping compares 2
    against 3 and flags. So the field is not only a false-positive suppressor:
    it is what makes this class visible at all, and the money is silent
    throughout, which is the entire point of a count check.
    """
    parser_id, _direction = key.split(":")
    rows = [txn(100.0, "credit"), txn(-40.0, "debit"), txn(-15.0, "debit", "SERVICE CHARGE")]
    stmt = statement(rows=rows, credit=1, debit=2, stated_service_charge=15.0)
    recon, integrity = integrity_for(stmt, parser_id)
    assert (recon.captured_debit_count, recon.expected_debit_count) == (2, 3)
    assert recon.stated_debit_count_matches is False
    assert integrity.flags == ["debit_count_mismatch"]
    assert integrity.risk_level == "review"
    # the money says nothing at all — only the count can speak here
    assert recon.ok is True and recon.issues == []
    # ... and advisory to the end: a flag, never a withholding.
    assert integrity.possible_document_issue is False
    assert classify_outcome({
        "metrics": {"average_daily_balance": 1234.56},
        "quality": {"corporate_use": "approved"},
        "integrity": {"flags": list(integrity.flags)},
    }) == ("review", "integrity_flags")
    # THE COUNTERFACTUAL: the promotion these two entries would have had
    # without the field. It sees nothing.
    blind = reconcile(stmt)
    assert (blind.expected_debit_count, blind.stated_debit_count_matches) == (2, True)


@pytest.mark.parametrize("key", MAPPED)
def test_a_caller_that_does_not_name_the_parser_gets_the_raw_printed_figure(key):
    """Fail-closed by default. `reconcile(stmt)` is what every caller outside
    the pipeline does, and it must behave exactly as it did before mappings
    existed: no claim, no adjustment."""
    parser_id, _direction = key.split(":")
    rows = [txn(100.0, "credit"), txn(-40.0, "debit"), txn(-30.0, "debit"),
            txn(-15.0, "debit", "SERVICE CHARGE")]
    stmt = statement(rows=rows, credit=1, debit=2, stated_service_charge=15.0)
    assert reconcile(stmt).expected_debit_count == 2
    assert reconcile(stmt, parser_id=parser_id).expected_debit_count == 3
    # an unclaimed dispatch is the same as no dispatch
    recon, integrity = integrity_for(stmt, parser_id, outcome="ambiguous")
    assert recon.expected_debit_count == 2
    assert not [flag for flag in integrity.flags if flag in COUNT_FLAGS]


def test_the_reconciler_and_the_flag_gate_key_on_the_same_claim():
    """The drift hazard the shared helper closes: `reconcile` APPLIES a table
    row's mapping and `assess_document_integrity` decides whether its result
    may be flagged. Two copies of "which parser claimed this" could send those
    two to different rows — applying capital_one's adjustment and judging it
    under nobody's semantics, or the reverse."""
    assert claiming_parser_id(None) is None
    assert claiming_parser_id(pr.Dispatch("unclaimed")) is None
    assert claiming_parser_id(
        pr.Dispatch("ambiguous", candidates=(("rbc", 1.0), ("capital_one", 1.0)))
    ) is None
    assert claiming_parser_id(
        pr.Dispatch("claimed", registration=pr.by_id("capital_one"))
    ) == "capital_one"
    source = (ROOT / "analysis" / "pipeline.py").read_text(encoding="utf-8")
    # BOTH keys are derived by the helper, and every reconcile call names one.
    assert source.count("claiming_parser_id(dispatch)") == 2
    calls = re.findall(r"\breconcile\((?!\s*$)[^)\n]*\)", source)
    assert calls, "the pipeline must call reconcile"
    for call in calls:
        assert "parser_id=" in call, call


def test_a_mapped_direction_still_appends_no_reconciliation_issue():
    """The phase-1 invariant, on the new arm: `ok` gates the ADB, so an issue
    here would WITHHOLD a document over a count. Compared against the same
    statement with the printed counts removed."""
    rows = [txn(100.0, "credit"), txn(-40.0, "debit"), txn(-15.0, "debit", "SERVICE CHARGE")]
    flagged = reconcile(statement(rows=rows, credit=1, debit=2, stated_service_charge=15.0),
                        parser_id="capital_one")
    silent = reconcile(statement(rows=rows, credit=None, debit=None, stated_service_charge=15.0),
                       parser_id="capital_one")
    assert flagged.issues == silent.issues == []
    assert flagged.ok is silent.ok is True


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


# ---------------------------------------------------------------------------
# W3 §FROSTOZK — one bank, two directions, two different answers
# ---------------------------------------------------------------------------


def test_the_frost_directions_disagree_with_each_other_and_that_is_the_point():
    """A registration is not comparable or incomparable as a whole. Frost's
    printed deposit count means our credit rows and its printed withdrawal
    count does not mean our debit rows, and the table has to be able to say
    both about one parser."""
    assert counts_comparable("frost", "credit") is True
    assert counts_comparable("frost", "debit") is False


def test_the_frost_debit_entry_names_both_excluded_row_classes_and_its_measurement():
    entry = SEMANTICS["frost"]["debit"]
    assert entry.scope == "named_row_classes_excluded"
    assert "SERVICE CHARGE/FEE" in entry.reason
    assert "zero" in entry.reason.lower()
    # The excess is recorded per document, so a later reader can check the
    # claim against the instrument rather than against a summary of it.
    assert "tools/frostozk_family_replay.py" in entry.reason


def test_the_frost_debit_entry_explains_why_it_carries_no_mapping():
    """The adjustment exists and is understood exactly; it is still not
    expressible, because both of its terms are facts about OUR ROWS and
    `PRINTED_EVIDENCE_FIELDS` admits only figures off the printed summary."""
    entry = SEMANTICS["frost"]["debit"]
    assert entry.mapping is None
    assert "PRINTED_EVIDENCE_FIELDS" in entry.reason
    assert "stated_service" in entry.reason


def test_the_frost_credit_entry_records_that_the_reader_does_not_gate_on_it():
    entry = SEMANTICS["frost"]["credit"]
    assert entry.comparable and entry.mapping is None
    assert "NOT A TAUTOLOGY" in entry.reason


def test_the_bank_ozk_entries_disclose_that_they_are_tautological():
    """The solver consumes the printed counts, so both directions agree by
    construction. Written out rather than left to `UNSURVEYED`, which would
    read as 'not yet examined'."""
    for direction in DIRECTIONS:
        entry = SEMANTICS["bank_ozk"][direction]
        assert entry.comparable and entry.mapping is None
        assert "TAUTOLOG" in entry.reason.upper()


def test_neither_new_registration_widened_the_mapping_vocabulary():
    assert RULES == ("plus_one_when_billed",)
    assert PRINTED_EVIDENCE_FIELDS == ("stated_service_charge",)
