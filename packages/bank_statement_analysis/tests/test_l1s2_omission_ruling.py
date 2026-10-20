"""Gustavo's Q10 ruling, pinned: SURFACE THE OMISSION, DO NOT DEMOTE.

`BATCH9_TRANSITION.md` §8.7 (and `docs/agent-handoffs/BATCH9-RULES.md`). An
explicit sibling omission beside an independently valid account keeps THAT
ACCOUNT `validated`; the omission is surfaced separately, at the document /
package layer, rather than being paid for by demoting the account that was read
correctly.

**The five independence conditions the ruling attaches, and where each is
enforced.** None of them is new machinery and none is relaxed here — every one
is the UNCHANGED validator this platform already runs, which is the point: the
ruling does not buy the account's outcome, it declines to take it away.

1. **unambiguous boundaries** — the reader's own L-1 gate. `symitar` publishes
   only when exactly ONE deposit section is active; `community_section` only
   when exactly ONE printed block posted; `zions` only when exactly ONE account
   block is funded. A sibling that POSTED is not an omission at all: it makes
   the boundary ambiguous and the document is refused (the `ambiguous` case
   below).
2. **reconstructs correctly** and 3. **passes the unchanged validator** —
   `analysis/reconcile.py` and `telemetry.record.classify_outcome`, both
   untouched by L-1 stage 2. The assertions below read the account's outcome
   through `classify_outcome` exactly as `discovery/runner.py` does.
4. **period / currency / opening-closing / transactions / ledger identity /
   ADB proved** — the same `classify_outcome` fold over `reconciliation`,
   `metrics` and `integrity`, which is why the assertion is on the OUTCOME and
   not on a hand-picked subset of those checks.
5. **nothing misattributed from the sibling** — asserted directly: the account
   published beside an omitted sibling is byte-identical to the account
   published when that sibling is not on the page at all. If a figure had
   leaked across the boundary, that equality would fail.

And the fail-closed half of the ruling, because a rule that only ever admits is
not a rule: an absence-only sibling and an ambiguous-boundary sibling are both
REFUSED, at the document seam, with nothing published.

**There is no document classifier at this tree.** `classify_outcome` classifies
ONE ACCOUNT's payload; the §1.5 fold that produces a document outcome from its
accounts is S3's work, and Q10 is what it must implement — a document carrying a
surfaced omission does NOT demote the account beneath it. Until that function
exists these tests assert the two halves that DO exist: the omission record on
`DocumentReport.omissions`, and the account outcome through the unchanged
account classifier. **S3: when `classify_document` lands, extend these cases to
assert its verdict too, and keep the account assertions.**

Every fixture is synthetic — the committed layout suites' own shapes, with
invented names, invented figures and the fixture calendar. No text, figure, name
or date from any real document appears here.
"""
from __future__ import annotations

import json

import pytest

from analysis.pipeline import analyze_document
from analysis.serialization import report_to_dict
from analysis.sibling_omission import (
    EVIDENCE_CLASSES,
    PRINTED_DORMANCY_DECLARATION,
    PRINTED_ZERO_ACTIVITY_SUMMARY,
    YIELD_ONLY_ARITHMETIC,
)
from telemetry.record import classify_outcome
from tests.test_l1s2_document_outcome import document_outcome
from tests.test_community_section_layouts import SIMPLE_BODY
from tests.test_sibling_omission import (
    BUSY_BUT_EMPTY_BODY,
    DW_ACTIVE_BODY,
    DW_HEAD,
    DW_IDLE_BODY,
    IDLE_BODY,
    PLATFORM_MULTI_HEAD,
    SYM_DORMANT_SILENT,
)
from tests.test_symitar import ACTIVE as SYM_ACTIVE
from tests.test_symitar import DIVIDEND_ONLY as SYM_DIVIDEND_ONLY
from tests.test_symitar import DORMANT as SYM_DORMANT
from tests.test_symitar import HEAD as SYM_HEAD
from tests.test_symitar import _money_market


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)


def _document(markdown: str):
    return analyze_document(markdown, parse_mode="deterministic")


def _account_outcome(document) -> tuple[str, str]:
    """The outcome the UNCHANGED validator gives the published account.

    `discovery/runner.py` classifies exactly this payload with exactly this
    function; nothing here re-implements a verdict.
    """
    return tuple(classify_outcome(report_to_dict(document.accounts[0])))


#: (case id, the page WITH the idle sibling, the same page WITHOUT it, the class
#: the paper printed on the sibling). One per member of L1-C17's vocabulary.
CASES = (
    ("printed dormancy declaration",
     SYM_HEAD + SYM_ACTIVE + SYM_DORMANT,
     SYM_HEAD + SYM_ACTIVE,
     PRINTED_DORMANCY_DECLARATION),
    ("printed zero-activity summary",
     PLATFORM_MULTI_HEAD + SIMPLE_BODY + IDLE_BODY,
     PLATFORM_MULTI_HEAD + SIMPLE_BODY,
     PRINTED_ZERO_ACTIVITY_SUMMARY),
    ("printed zero-activity summary, through the other entry point",
     DW_HEAD + DW_ACTIVE_BODY + DW_IDLE_BODY,
     DW_HEAD + DW_ACTIVE_BODY,
     PRINTED_ZERO_ACTIVITY_SUMMARY),
    ("yield-only arithmetic",
     SYM_HEAD + SYM_ACTIVE + SYM_DIVIDEND_ONLY,
     SYM_HEAD + SYM_ACTIVE,
     YIELD_ONLY_ARITHMETIC),
)

IDS = [case[0] for case in CASES]


@pytest.mark.parametrize("_label,with_sibling,_alone,reason", CASES, ids=IDS)
def test_the_omission_is_surfaced_with_its_class_named(_label, with_sibling, _alone, reason):
    """Half one of the ruling: SURFACE it. The gap is published as a record on
    the document object, and the record names the printed evidence that admitted
    it — never absence, which `SiblingOmission` refuses at construction."""
    document = _document(with_sibling)
    assert [record.reason for record in document.omissions] == [reason]
    assert reason in EVIDENCE_CLASSES


@pytest.mark.parametrize("_label,with_sibling,_alone,_reason", CASES, ids=IDS)
def test_the_account_beside_an_omission_stays_validated(_label, with_sibling, _alone, _reason):
    """Half two of the ruling: DO NOT DEMOTE. The account that was read
    correctly keeps the outcome the unchanged validator gives it."""
    assert _account_outcome(_document(with_sibling))[0] == "validated"


@pytest.mark.parametrize("_label,with_sibling,_alone,_reason", CASES, ids=IDS)
def test_the_DOCUMENT_beside_an_omission_stays_validated(_label, with_sibling, _alone, _reason):
    """The same half, on the OTHER leg — and this is the one a document-level
    fold walks through.

    The account assertion above passes happily while a `classify_document` that
    demotes on any omission demotes every carrier: the re-review demonstrated
    exactly that with a mutant. `document_outcome` resolves the DOCUMENT's
    verdict through whatever this tree exposes — a declared fold if one exists,
    the published account otherwise — so this assertion reads the fold the day
    S3 lands one, without anyone remembering to extend it.
    """
    assert document_outcome(_document(with_sibling))[0] == "validated"


@pytest.mark.parametrize("_label,with_sibling,alone,_reason", CASES, ids=IDS)
def test_the_omission_changes_the_accounts_outcome_by_nothing(_label, with_sibling, alone, _reason):
    """The ruling stated as the difference it forbids, which is stronger than a
    literal `validated`: the SAME account read with the idle sibling on the page
    and without it reaches the same verdict, for the same reason — on BOTH legs,
    so a fold that demotes only the omission carriers is caught here too."""
    assert _account_outcome(_document(with_sibling)) == _account_outcome(_document(alone))
    assert document_outcome(_document(with_sibling)) == document_outcome(_document(alone))


@pytest.mark.parametrize("_label,with_sibling,alone,_reason", CASES, ids=IDS)
def test_nothing_is_misattributed_from_the_omitted_sibling(_label, with_sibling, alone, _reason):
    """Independence condition 5, asserted rather than argued. The account block
    published beside an omitted sibling is byte-identical to the one published
    when that sibling is not on the page at all — so no figure, count, date or
    balance crossed the boundary."""
    assert canonical(report_to_dict(_document(with_sibling).accounts[0])) == canonical(
        report_to_dict(_document(alone).accounts[0]))


# ---------------------------------------------------------------------------
# the fail-closed half — "if the omission makes the boundaries ambiguous or
# prevents independent validation, fail closed"
# ---------------------------------------------------------------------------

#: A sibling that POSTED. It is not an idle sibling and not an omission: two
#: live deposit ledgers on one page is the ambiguous boundary L-1 refuses.
SYM_AMBIGUOUS = SYM_HEAD + SYM_ACTIVE + _money_market(
    "05/02/54 -25.00 -19.81 Card purchase FUEL STOP")

#: The refusal this reader performs when no registration publishes a statement.
#: `analysis/pipeline.py` raises it by name in deterministic mode, and asserting
#: the CLASS and its message is what keeps these cases from passing on an
#: exception thrown by a fixture that never reached the site.
NO_PARSER = "no deterministic parser matched this statement"

#: (label, the page that must be REFUSED, the nearest page that must PUBLISH).
#: Every refusal is paired with its own positive control, so each case proves a
#: refusal of the thing under test rather than of a fixture that was broken.
REFUSALS = (
    ("absence only — a printed sibling, no row and no declaration",
     SYM_HEAD + SYM_ACTIVE + SYM_DORMANT_SILENT,
     SYM_HEAD + SYM_ACTIVE + SYM_DORMANT),
    ("absence only — a block whose grid states activity it printed no row for",
     PLATFORM_MULTI_HEAD + SIMPLE_BODY + BUSY_BUT_EMPTY_BODY,
     PLATFORM_MULTI_HEAD + SIMPLE_BODY + IDLE_BODY),
    ("ambiguous boundary — a second sibling that POSTED",
     SYM_AMBIGUOUS,
     SYM_HEAD + SYM_ACTIVE + SYM_DORMANT),
)

REFUSAL_IDS = [case[0] for case in REFUSALS]


@pytest.mark.parametrize("_label,refused,_admitted", REFUSALS, ids=REFUSAL_IDS)
def test_the_document_is_refused_rather_than_published_short(_label, refused, _admitted):
    """Q10 admits an omission; it does not admit a gap nobody can account for.
    Nothing is published, so there is no account to keep validated and no
    omission to surface — and the refusal is named, not merely raised."""
    with pytest.raises(RuntimeError, match=NO_PARSER):
        _document(refused)


@pytest.mark.parametrize("_label,_refused,admitted", REFUSALS, ids=REFUSAL_IDS)
def test_each_refusal_has_a_positive_control_that_publishes(_label, _refused, admitted):
    """The anti-vacuity companion for every refusal above. The nearest page that
    DOES print evidence reaches the same reader, publishes, records the omission
    and keeps its document `validated` — so the refusal beside it is a refusal of
    the missing evidence and not of a fixture that never arrived."""
    document = _document(admitted)
    assert document.omissions
    assert document_outcome(document)[0] == "validated"


def test_the_refusal_fixtures_differ_from_the_admitted_ones_only_in_the_evidence():
    """Same argument at the level of the bytes, for the symitar pair: the
    absence-only page is the admitted page with the printed declaration removed
    and nothing put in its place."""
    assert SYM_DORMANT.replace("No Transactions This Period ", "") == SYM_DORMANT_SILENT
    assert "No Transactions This Period" not in SYM_DORMANT_SILENT
    assert len(SYM_DORMANT) - len(SYM_DORMANT_SILENT) == len("No Transactions This Period ")
    document = _document(SYM_HEAD + SYM_ACTIVE + SYM_DORMANT)
    assert document.omissions and _account_outcome(document)[0] == "validated"


def test_the_ambiguous_page_differs_from_the_admitted_one_only_in_what_the_sibling_POSTED():
    """And for the ambiguous pair, where the difference is not a declaration but
    a dated row: the same document furniture and the same active account, with a
    sibling that posted rather than one that declared itself idle."""
    assert SYM_AMBIGUOUS.startswith(SYM_HEAD + SYM_ACTIVE)
    assert "No Transactions This Period" not in SYM_AMBIGUOUS
    assert "Card purchase FUEL STOP" in SYM_AMBIGUOUS
