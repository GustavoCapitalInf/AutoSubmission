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

from .provenance import extractor_model

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

#: The section printed its OWN opening caption and figure and its OWN closing
#: caption and figure, the two coincide to the cent, and it printed no dated
#: ledger row, no counts or totals and no daily-balance table — AND the
#: document's own enumerating table independently reproduces that closing.
#:
#: GRANTED WITH CORROBORATION (Gustavo, 2026-08-30).
#: Six printed conditions and a seventh that the section does not control: the
#: roll-up witness. The class exists to bound the hazard where an extractor
#: loses a section's ledger rows while its two captions survive and happen to
#: net to zero; the six conditions are all read INSIDE the section, so the only
#: thing that can contradict a lost ledger is a second printing of the closing
#: somewhere the section does not govern.
PRINTED_PAIR_COINCIDES_AND_NO_ROW_PRINTED = "printed_pair_coincides_and_no_row_printed"

#: The closed vocabulary. Membership is checked at CONSTRUCTION, so a reason a
#: site invented cannot reach a payload: L1-C17 says an omission whose reason is
#: not a ratified evidence class should never have been published.
EVIDENCE_CLASSES: frozenset[str] = frozenset({
    PRINTED_DORMANCY_DECLARATION,
    PRINTED_ZERO_ACTIVITY_SUMMARY,
    YIELD_ONLY_ARITHMETIC,
    PRINTED_PAIR_COINCIDES_AND_NO_ROW_PRINTED,
})

#: Q3's native-only gate (Gustavo; carried forward at Phase 2.0 opening: the Q3
#: idle-sibling class stays native-only until the corroboration is re-measured
#: on OCR'd guardian_cu). `PRINTED_PAIR_COINCIDES_AND_NO_ROW_
#: PRINTED` was corroborated 6/6 on `native-pdf-text` documents only, to bound
#: an OCR row-loss hazard that has never been measured on OCR'd input. Until
#: that re-measurement exists, the class is admitted only on
#: `native-pdf-text*` provenance; every other token, `""`, or the absence of a
#: header refuses it, fail-closed, exactly as L1-C17 refuses an unratified
#: reason (`SiblingOmission.__post_init__` below) — both are raised where the
#: record is about to be published and both are caught by
#: `analysis.parser_registry._guarded` the same way a declining parser is,
#: which is why this is gated at PUBLISH rather than at construction: the
#: `reason` itself is ratified, only its provenance is not yet proven for
#: OCR'd input. The other three ratified classes are NOT gated — they were
#: never ruled OCR-sensitive.
Q3_CLASS_REQUIRES_NATIVE_PROVENANCE = "q3_class_requires_native_provenance"

#: The provenance token Q3 requires — checked at `publish_omissions` as
#: `model == _Q3_REQUIRED_MODEL_PREFIX or model.startswith(_Q3_REQUIRED_MODEL_
#: PREFIX + "+")`, NOT a bare `startswith` (MINOR-1:
#: `startswith("native-pdf-text")` alone also
#: admits `native-pdf-textXYZ`, a shape no writer in this tree produces).
#: A native read may carry a layout suffix of its own
#: (`native-pdf-text+guardian`) and stays admitted — the ruling's own wording
#: is "the document's extractor model is `native-pdf-text*`"
#: and `ocr/native_text.py` writes only
#: the bare token or a `+suffix` form, never a bare concatenation.
_Q3_REQUIRED_MODEL_PREFIX = "native-pdf-text"

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


#: A cent, the way every printed-figure comparison in the L-1 design expresses
#: it. Two figures the paper prints to the cent COINCIDE when they differ by
#: less than half of one.
CENT = 0.005


@dataclass(frozen=True)
class RollupWitness:
    """Condition 7's facts, as the READER read them off the enumerating table.

    This record holds no grammar and reads no document: each field is something
    the calling reader established from the document's own printed table, and a
    reader that could not establish one supplies the fail-closed value.

    `row_located_by_label` and `row_located_by_identity` are two different
    printed handles on the same row — the product caption the table printed, and
    the identity token beside it — and `locators_agree` says whether they found
    the SAME row. Both halves are required and their agreement is required with
    them, because on this family neither half is reliably the discriminating one
    (`W3 §Q3PROBE` Q3PROBE8, review MINOR-3 and MINOR-4: on one document the
    label matches eleven lines including the sibling's reprinted headings and
    only the identity token is unique; on two others the reverse). A witness
    bound by one handle where the other disagrees is a MIS-BINDING, and a
    mis-binding is invisible to a probe that inherits the link from the boundary.
    """

    #: The document printed a roll-up / enumerating table WITH rows.
    printed: bool = False
    #: L1-C5: the table printed a COLUMN CAPTION from the closed vocabulary, so
    #: the roles of its columns are established by the paper rather than by a
    #: position. False refuses the witness outright — a figure coinciding under
    #: a column nobody named is a coincidence and not a corroboration.
    column_roles_printed: bool = False
    #: A row of that table located by the section's OWN PRINTED LABEL.
    row_located_by_label: bool = False
    #: A row of that table located by the section's OWN IDENTITY TOKEN.
    row_located_by_identity: bool = False
    #: ... and the two handles found the same row.
    locators_agree: bool = False
    #: The figure that row prints under the `close` ROLE — never under a
    #: position. `None` where the row's figures do not fit the printed roles.
    closing: float | None = None


def prints_pair_coinciding_with_no_row_printed(
    *,
    opening: float | None,
    closing: float | None,
    dated_row_count: int | None,
    prints_counts_or_totals: bool | None,
    prints_daily_balance_table: bool | None,
    rollup: RollupWitness | None,
) -> bool:
    """The SEVEN conditions of `printed_pair_coincides_and_no_row_printed`.

    All seven, in the ruling's own order:

    1. the section prints its own opening caption AND figure;
    2. the section prints its own closing caption AND figure;
    3. the two coincide to the cent;
    4. no dated ledger row is printed in the section;
    5. no counts / totals are printed for the section;
    6. no daily-balance table is printed for the section;
    7. the document's enumerating table independently reproduces the section's
       closing, read from the `close` ROLE of a column caption in L1-C5's closed
       vocabulary, on a row bound to this section by BOTH its printed label and
       its identity token.

    **Read fail-closed on every one of them**, and read that way in the
    direction that costs the class rather than the direction that grants it: a
    figure the reader could not establish is `None` and refuses, a count it did
    not take is `None` and refuses, and an absent witness refuses. Condition 7's
    conditional wording in the ruling — *where the document prints a roll-up
    with identifiable column roles* — is applied the way the bounded probe
    applied it and reported it: a document that prints no such table FAILS
    condition 7 rather than passing it vacuously
    (refusal classes
    `no_rollup_or_enumerating_table_printed_by_the_document` and
    `rollup_prints_the_closing_under_a_column_whose_role_is_not_identifiable`).
    That is the reading S4 must implement, because it is the one the six
    measured sections were measured under.

    Condition 4 asks about what the PAPER printed and not about what the caller
    parsed. A reader that hands its own parsed-row count here would be asking
    "did I read a row" where the ruling asks "did the paper print one", and the
    two differ on exactly the documents this class exists to refuse.
    """
    if opening is None or closing is None:
        return False
    if abs(opening - closing) > CENT:
        return False
    if dated_row_count is None or dated_row_count != 0:
        return False
    if prints_counts_or_totals is None or prints_counts_or_totals:
        return False
    if prints_daily_balance_table is None or prints_daily_balance_table:
        return False
    if rollup is None or not rollup.printed:
        return False
    if not rollup.column_roles_printed:
        return False
    if not (rollup.row_located_by_label and rollup.row_located_by_identity):
        return False
    if not rollup.locators_agree:
        return False
    if rollup.closing is None:
        return False
    return abs(rollup.closing - closing) <= CENT


def evidence_class(
    *,
    text: str | None = None,
    opening: float | None = None,
    closing: float | None = None,
    credit_total: float | None = None,
    debit_total: float | None = None,
    credit_count: object = None,
    debit_count: object = None,
    dated_row_count: int | None = None,
    prints_counts_or_totals: bool | None = None,
    prints_daily_balance_table: bool | None = None,
    rollup: RollupWitness | None = None,
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
    # LAST, and reachable only by a caller that supplies its four arguments.
    # Every reader written before this class supplies none of them, so each is
    # `None`, every one of them refuses, and no section any existing reader
    # omits can change class. That is not a courtesy: the fifteen protected
    # carriers of W3 §L1S2 are admitted by the three classes above and their
    # payloads are pinned, so a new class that could reach them silently would
    # be a movement this cell is not entitled to make.
    if prints_pair_coinciding_with_no_row_printed(
        opening=opening, closing=closing,
        dated_row_count=dated_row_count,
        prints_counts_or_totals=prints_counts_or_totals,
        prints_daily_balance_table=prints_daily_balance_table,
        rollup=rollup,
    ):
        return PRINTED_PAIR_COINCIDES_AND_NO_ROW_PRINTED
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

#: The RAW markdown `analyze_document` was called with, for exactly as long as
#: `_COLLECTING` is open on the same document. A second `ContextVar` rather
#: than a parameter threaded through `publish_omissions` deliberately: five
#: parser modules across four files call `publish_omissions(ledger.omissions)`
#: today and none of them is this card's to touch (P20-SURFACES owns only
#: `analysis/pipeline.py` and this module), so the markdown a Q3 admission must
#: be checked against travels the same scoped-and-reset path `_COLLECTING`
#: already does, set by the one caller that has it
#: (`analysis.pipeline.analyze_document`) and read by the one function that
#: needs it, with no change to any parser's call site or signature.
_MARKDOWN: ContextVar[str | None] = ContextVar(
    "sibling_omission_markdown", default=None,
)


@contextmanager
def collecting(markdown: str | None = None) -> Iterator[list[SiblingOmission]]:
    """Collect the omissions recorded by whatever parses inside this block.

    Opened by `analysis.pipeline.analyze_document`, which is the seam that owns
    the document object the record belongs on. The account entry point does not
    open one, and that is the shape of RULE S rather than an oversight: a
    single-account payload has nowhere to put a document-level fact, so the
    stage that teaches the payload readers the document shape is the stage that
    moves the seams onto it.

    `markdown` is the document's own raw text, unstripped — the same string
    `analyze_document` received, before `admissible_text` removes the source
    comment for parsing. Recorded so `publish_omissions` can read the
    document's extractor-model provenance (Q3's native-only gate) without any
    parser module passing it through.
    """
    sink: list[SiblingOmission] = []
    token = _COLLECTING.set(sink)
    markdown_token = _MARKDOWN.set(markdown)
    try:
        yield sink
    finally:
        _MARKDOWN.reset(markdown_token)
        _COLLECTING.reset(token)


class Q3ProvenanceRefused(ValueError):
    """Q3's native-only gate refused an omission — a POLICY decision, never a crash.

    Raised where the record is about to be published (`publish_omissions`,
    below) and — like every exception a registration's `parse` can raise —
    caught by `analysis.parser_registry._guarded`, which stores only its
    CLASS NAME (`ParserFailure.exception`), never this message
    (`analysis/parser_registry.py:822-836`'s own privacy discipline). A
    dedicated subclass exists so a class name alone can tell "our own code
    broke" (`ParserCrashError`'s own docstring reserves that meaning) apart
    from "the provenance policy refused this document" — MAJOR-2:
    a bare `ValueError` left the refusal
    recorded nowhere a reader could distinguish it from an actual crash.
    `analysis/pipeline.py` reads this class's `__name__` off
    `dispatch.exceptions` to refuse the document in every `parse_mode`
    (BLOCK-2, same review) rather than treating it as an ordinary parser
    exception that a non-deterministic mode may fall through past.
    """


def publish_omissions(omissions: Sequence[SiblingOmission]) -> None:
    """Hand a parse attempt's admitted omissions to the document collecting them.

    Called only by a reader that IS publishing a statement. A reader that
    returns `None` publishes nothing, so nothing it learned about a section it
    dropped is attributed to the document another reader went on to claim.

    **Q3's native-only gate lives here** (`Q3_CLASS_REQUIRES_NATIVE_PROVENANCE`,
    above). An omission whose `reason` is
    `printed_pair_coincides_and_no_row_printed` is admitted only when the
    document's extractor-model token (`analysis.provenance.extractor_model`,
    read off `_MARKDOWN`) is EXACTLY `native-pdf-text` or starts with
    `native-pdf-text+` (MINOR-1: a bare
    `startswith("native-pdf-text")` also admits `native-pdf-textXYZ`, a token
    no writer in this tree ever produces — `ocr/native_text.py` writes only
    the bare token or a `+suffix` form); any other token, `""`, or no header
    at all RAISES `Q3ProvenanceRefused` — the same fail-closed SHAPE
    `SiblingOmission.__post_init__` already uses for an unratified reason
    (a `ValueError` subclass), and for the same reason: this call happens
    inside a registration's `parse`, which `analysis.parser_registry._guarded`
    wraps in a bare `except Exception`, so raising here is caught exactly as a
    declining parser is (`_guarded` returns `None`, the next claimant is
    tried, and if none succeeds the document fails closed as
    `parser_exception` / `ParserCrashError`). `Q3ProvenanceRefused` rather than
    a bare `ValueError` (MAJOR-2, same review) so the refusal survives
    `_guarded`'s message-discarding boundary AS A CLASS NAME
    `analysis/pipeline.py` can check for and refuse in every `parse_mode`
    (BLOCK-2) — a bare `ValueError` is indistinguishable there from any other
    parser crash. The other three ratified classes are not checked at all.

    The gate runs only while something is COLLECTING (`sink is not None`) —
    the same condition that already decides whether this call does anything.
    A reader exercised directly in a unit test, outside
    `analysis.pipeline.analyze_document`'s scope, publishes nothing to
    anything and never reaches production this way; gating it too would
    require every such test to fabricate provenance for a call whose result
    nothing reads.
    """
    sink = _COLLECTING.get()
    if sink is None or not omissions:
        return
    for omission in omissions:
        if omission.reason != PRINTED_PAIR_COINCIDES_AND_NO_ROW_PRINTED:
            continue
        model = extractor_model(_MARKDOWN.get()) or ""
        admitted = model == _Q3_REQUIRED_MODEL_PREFIX or model.startswith(
            _Q3_REQUIRED_MODEL_PREFIX + "+"
        )
        if not admitted:
            raise Q3ProvenanceRefused(
                "an omission of reason 'printed_pair_coincides_and_no_row_printed' "
                "is admitted only on native-pdf-text* extractor provenance; this "
                f"document's provenance does not qualify ({Q3_CLASS_REQUIRES_NATIVE_PROVENANCE})"
            )
    sink.extend(omissions)
