"""The omission record — what admits a sibling section a reader does not publish.

A member statement prints several of one member's accounts. The single-account
schema carries one of them, so every reader of such a paper has to decide what
to do with the others, and until this module existed three of them decided it
the same wrong way: **absence**. A section that parsed no dated row was dropped,
silently, with nothing in the payload to say a section had been read and left
out. That is the L-1 defect stated exactly — *never publish one account and
silently drop another* — and it is what Gustavo's checkpoint condition refuses:

> an idle sibling is admitted ONLY when explicit statement structure establishes
> the sibling AND its empty / silent state; absence of parsed activity alone is
> insufficient.

So the skip is re-founded here. A section the reader does not publish is either

* **admitted**, because the paper PRINTED evidence of its empty state, and then
  it is recorded as an omission and the record is published; or
* **refused**, and then the whole DOCUMENT is refused — fail closed, because a
  document whose reader cannot account for one of its accounts is not a document
  we have read.

L1-C17 — THE CLOSED VOCABULARY, AND WHY IT IS CLOSED IN ONE DIRECTION ONLY
--------------------------------------------------------------------------
`reason` comes from :data:`EVIDENCE_CLASSES`, and every member of it names
something the paper PRINTED. `absence_of_parsed_rows` is not a member and cannot
become one: it is the class this whole module exists to refuse. But the
vocabulary is closed against ABSENCE, never against EVIDENCE — a class the
archive prints and this list cannot name is a defect in the list, not a licence
to invent a token at a call site.

`printed_dormancy_declaration` is deliberately **wording-independent**. Two
issuers on two platforms print the same fact in two sentences, and a class keyed
on one of them would be a per-issuer vocabulary — R-1 by another name. Both
ratified patterns therefore live HERE, in one tuple, and every site asks the
tuple rather than its own module's copy. A newly met wording is admitted by
APPENDING a pattern to that tuple, never by relaxing the class.

`printed_zero_activity_summary` is six clauses and all six are required, read
fail-closed: a grid missing either balance or either count yields nothing rather
than a partial answer. It is one CLASS of evidence and not one reader's helper,
which is why a reader that reaches it through its own grid — an account block
whose printed summary columns are all zero — publishes this token rather than a
token of its own.

WHERE THE RECORD GOES (RULE S)
------------------------------
Onto the DOCUMENT object, never onto `Statement`. `Statement` is ONE ACCOUNT's,
its class docstring and field descriptions are published to the extraction model
as a `response_schema`, and RULE S is the promise that a single-account document
publishes today's payload byte for byte. A parse attempt collects its omissions
locally and, only if it goes on to publish a statement, hands them to whatever
is collecting for this document (`collecting`, opened by
`analysis.pipeline.analyze_document`). A parse attempt that publishes nothing
hands over nothing: a losing candidate's drops are not the document's omissions.

Nothing here reads, writes or compares a printed value. It receives figures a
reader has already read and reports how they compare with each other and with
zero.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Sequence

# ---------------------------------------------------------------------------
# L1-C17's closed vocabulary
# ---------------------------------------------------------------------------

#: The section printed a declaration that nothing posted to it this period.
PRINTED_DORMANCY_DECLARATION = "printed_dormancy_declaration"

#: The section printed its own opening balance, its own closing balance
#: coinciding with it to the cent, a zero credit total, a zero debit total, a
#: zero credit count and a zero debit count. All six.
PRINTED_ZERO_ACTIVITY_SUMMARY = "printed_zero_activity_summary"

#: The section's only postings are the yield the account itself earned, under
#: the ratified `analysis.symitar._yield_only` predicate applied AS WRITTEN
#: (every posting a credit the platform named as a dividend, the section's own
#: arithmetic closing on the balance the DOCUMENT states for that account, and
#: — where the platform prints its six-figure equation row — that row's own
#: dividend column accounting for every skipped posting with its deposits
#: column at zero).
YIELD_ONLY_ARITHMETIC = "yield_only_arithmetic_with_summary_equality"

#: The closed vocabulary. Membership is checked at CONSTRUCTION, so a reason a
#: site invented cannot reach a payload: L1-C17 says an omission whose reason is
#: not a ratified evidence class should never have been published.
EVIDENCE_CLASSES: frozenset[str] = frozenset({
    PRINTED_DORMANCY_DECLARATION,
    PRINTED_ZERO_ACTIVITY_SUMMARY,
    YIELD_ONLY_ARITHMETIC,
})

#: The ratified printings of ONE fact. `DORMANT_RE` is the wording
#: `analysis/symitar.py` ratified and `NO_ACTIVITY_RE` the one
#: `analysis/zions.py` did; both modules still expose them under their own
#: names, and both names now resolve HERE so that the two cannot drift into two
#: different opinions about what a dormancy declaration is. The patterns are
#: carried over byte for byte — `NO_ACTIVITY_RE` is live inside `zions._rows`,
#: and a "tidied" pattern would be a behaviour change wearing a refactor's
#: clothes.
DORMANT_RE = re.compile(r"No\s+Transactions\s+This\s+Period", re.IGNORECASE)
NO_ACTIVITY_RE = re.compile(r"There were no transactions this period", re.IGNORECASE)

#: The class, as a tuple. A new issuer's wording is admitted by appending to it.
DORMANCY_DECLARATIONS: tuple[re.Pattern[str], ...] = (DORMANT_RE, NO_ACTIVITY_RE)


def prints_dormancy_declaration(text: str | None) -> bool:
    """Does this section's printed text carry a no-activity declaration?"""
    if not text:
        return False
    return any(pattern.search(text) for pattern in DORMANCY_DECLARATIONS)


def _is_zero(value: float | None) -> bool:
    """A printed figure that is zero to the cent. `None` — not printed — is not
    a zero: the six clauses are read fail-closed, so an absent column refuses
    the class rather than defaulting into it."""
    return value is not None and round(value, 2) == 0.0


def _is_zero_count(value: object) -> bool:
    """A printed instance count that is zero.

    The counts arrive as the cell the grid printed, because that is what the
    readers hold at the point they decide. Anything that is not a readable
    integer is ABSENCE and refuses the class; nothing here is defaulted.
    """
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return value == 0
    try:
        return int(str(value).strip()) == 0
    except (TypeError, ValueError):
        return False


def prints_zero_activity_summary(
    *,
    opening: float | None,
    closing: float | None,
    credit_total: float | None,
    debit_total: float | None,
    credit_count: object,
    debit_count: object,
) -> bool:
    """The six clauses of `printed_zero_activity_summary`, all required.

    The pair must COINCIDE rather than merely both be printed: two balances that
    agree to the cent is the paper stating that nothing moved, and it is the
    half of this class that absence cannot counterfeit.
    """
    if opening is None or closing is None:
        return False
    if round(opening - closing, 2) != 0.0:
        return False
    return (
        _is_zero(credit_total)
        and _is_zero(debit_total)
        and _is_zero_count(credit_count)
        and _is_zero_count(debit_count)
    )


def evidence_class(
    *,
    text: str | None = None,
    opening: float | None = None,
    closing: float | None = None,
    credit_total: float | None = None,
    debit_total: float | None = None,
    credit_count: object = None,
    debit_count: object = None,
) -> str | None:
    """Which class of PRINTED evidence admits this section's omission, or None.

    Every argument is something the CALLING reader read off its own paper: this
    function writes no grammar and reads no document. A caller that cannot
    supply a figure supplies nothing, and the class that needed it refuses —
    which is why a reader whose layout prints no counts can only ever reach the
    declaration class, and never falls through into a partial one.

    `None` is the answer L1-C17 refuses: it means the section was going to be
    dropped for the ABSENCE of parsed rows, and the document must fail closed.
    """
    if prints_dormancy_declaration(text):
        return PRINTED_DORMANCY_DECLARATION
    if prints_zero_activity_summary(
        opening=opening, closing=closing,
        credit_total=credit_total, debit_total=debit_total,
        credit_count=credit_count, debit_count=debit_count,
    ):
        return PRINTED_ZERO_ACTIVITY_SUMMARY
    return None


# ---------------------------------------------------------------------------
# the record
# ---------------------------------------------------------------------------


@dataclass
class SiblingOmission:
    """A printed section that was established as an account and NOT published.

    An omission is a published GAP: the document said this account exists and
    the platform is not publishing it, so it is recorded rather than dropped.
    `reason` names the PRINTED evidence that admitted the omission and comes
    from a closed vocabulary; a section omitted for the absence of parsed rows
    is not an omission, it is a defect. `posting_count` is the number of dated
    rows the omitted section printed.

    `label` is the section's own printed ROLE — the product caption the paper
    gave it — and never an account number: this record travels into a payload
    beside an account block that already publishes its own identity.
    """

    label: str | None
    reason: str
    posting_count: int

    def __post_init__(self) -> None:
        # L1-C17, enforced where the record is MADE. A reason outside the
        # vocabulary is an implementation defect, not a document's property, and
        # a document may not publish one.
        if self.reason not in EVIDENCE_CLASSES:
            raise ValueError(
                "an omission reason must name printed evidence from L1-C17's "
                f"closed vocabulary; {self.reason!r} does not"
            )
        if self.posting_count < 0:
            raise ValueError("an omitted section cannot have printed fewer than no rows")


class SectionLedger:
    """What ONE parse attempt learned about the sections it did not publish.

    Local to the attempt, because `analysis.parser_registry.resolve` may run a
    parse that goes on to decline: an attempt that publishes nothing has learned
    nothing about the document, and its ledger is discarded with it.

    Two outcomes and they are not symmetrical. `omit` records an admitted
    omission. `refuse` records a section dropped with NO printed evidence, and a
    caller that sees `refused` must return `None` — the document fails closed,
    L-1 stands, and nothing is published from a paper one of whose accounts this
    reader cannot account for.
    """

    __slots__ = ("omissions", "refused")

    def __init__(self) -> None:
        self.omissions: list[SiblingOmission] = []
        self.refused: int = 0

    def omit(self, label: str | None, reason: str, posting_count: int = 0) -> None:
        self.omissions.append(SiblingOmission(label, reason, posting_count))

    def refuse(self) -> None:
        self.refused += 1

    def record(self, label: str | None, reason: str | None, posting_count: int = 0) -> bool:
        """`omit` on evidence, `refuse` without it. Returns whether it was
        admitted, so a call site reads as the decision it is making."""
        if reason is None:
            self.refuse()
            return False
        self.omit(label, reason, posting_count)
        return True


# ---------------------------------------------------------------------------
# the seam to the document object
# ---------------------------------------------------------------------------

#: The document currently being analysed, if anything is collecting for one.
#: A `ContextVar` rather than a module global because the collection is scoped
#: to one analysis and must not leak between concurrent ones.
_COLLECTING: ContextVar[list[SiblingOmission] | None] = ContextVar(
    "sibling_omissions", default=None,
)


@contextmanager
def collecting() -> Iterator[list[SiblingOmission]]:
    """Collect the omissions recorded by whatever parses inside this block.

    Opened by `analysis.pipeline.analyze_document`, which is the seam that owns
    the document object the record belongs on. The account entry point does not
    open one, and that is the shape of RULE S rather than an oversight: a
    single-account payload has nowhere to put a document-level fact, so the
    stage that teaches the payload readers the document shape is the stage that
    moves the seams onto it.
    """
    sink: list[SiblingOmission] = []
    token = _COLLECTING.set(sink)
    try:
        yield sink
    finally:
        _COLLECTING.reset(token)


def publish_omissions(omissions: Sequence[SiblingOmission]) -> None:
    """Hand a parse attempt's admitted omissions to the document collecting them.

    Called only by a reader that IS publishing a statement. A reader that
    returns `None` publishes nothing, so nothing it learned about a section it
    dropped is attributed to the document another reader went on to claim.
    """
    sink = _COLLECTING.get()
    if sink is None or not omissions:
        return
    sink.extend(omissions)
