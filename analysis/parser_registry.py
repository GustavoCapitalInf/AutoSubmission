"""Parser protocol and registry dispatch (R-3; MASTER_PLAN P1-1b / AD-1).

Replaces the 43-term `or`-chain that used to be `analysis/pipeline.py`'s
`_deterministic_statement`. The chain worked, but it had no way to express the
three things this module exists to provide:

**A detection result you can inspect.** Each parser used to answer only "mine"
or "not mine", from a guard buried in its parse function. Here it returns a
`Detection` — a score, the marker ids that fired, and the marker that ruled it
out — so telemetry (H-3) and the discovery run (DSC-2) can see *why* a document
resolved as it did, and how nearly it resolved otherwise.

**Order as data.** Chain order was source-code line order in one function: a
real routing contract that no test could read. Here the order is
`(band, id)` over registration data and is asserted literally, and genuine
precedence between two parsers that can both claim a document is an explicit
`supersedes` edge rather than an accident of position.

**Ambiguity as an outcome.** The chain's first-wins was silent. Two parsers
claiming one document is a fact about our registry that a human must resolve,
and a wrong-parser claim that happens to reconcile corrupts a real result and
the discovery statistics alike. `resolve` therefore refuses to guess: it
returns `ambiguous` and the caller routes the document to review.

**A crash as an outcome, not an escape (W3-1).** Discovery found 53 documents
on which a parser raised, and the exception escaped `resolve` into whatever
loop happened to be running — aborting the document, taking the routing facts
with it (no `Dispatch` was ever produced, so telemetry recorded nothing about
who crashed), and carrying an exception *message* that routinely quotes a
fragment of the statement. Every `detect` and every `parse` call therefore runs
behind `_guarded`: the failure becomes a `ParserFailure` (parser id, stage,
exception CLASS NAME — never the message), the remaining registry order
continues exactly as the fallthrough rule already specifies, and a document
that nothing could parse *because something crashed* is reported as
`parser_exception` rather than as the indistinguishable `unclaimed`. The seam
is total: no code path from `resolve` through `parse` raises.

Score semantics (fixed by the R-3 RFC, approved 2026-08-06):

======  ==========================================================
0.0     no evidence, or positively excluded
<0.5    weak — corroboration without every required marker; never claims
0.5     minimum claim: every required marker present
<1.0    claim plus corroboration
1.0     an exclusive structural sentinel only this document class carries
======  ==========================================================

The formula is chosen so that a registration reaches `CLAIM_THRESHOLD`
**exactly when its pre-R-3 guard passed**: guards were conjunctions of required
markers, and `all(required)` is precisely the condition for reaching 0.5. That
is what makes the migration parity-preserving by construction rather than by
hope, and `tests/test_parser_parity.py` proves it document by document over the
pinned corpus.

Scores are not probabilities and are not calibrated across parsers. They rank
candidates, expose near-misses, and give ambiguity a threshold. Nothing else.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Literal, Protocol

from .schema import Statement

__all__ = [
    "CLAIM_THRESHOLD",
    "AmbiguousParserError",
    "Detection",
    "Dispatch",
    "Marker",
    "Parser",
    "ParserCrashError",
    "ParserFailure",
    "Registration",
    "admissible_text",
    "by_bank_label",
    "by_id",
    "clear_registry",
    "corroborating",
    "excluding",
    "make_detector",
    "exclusive",
    "register",
    "registrations",
    "required",
    "resolve",
    "run_integrity_checks",
    "safe_detect",
    "score_markers",
]

#: A registration claims a document at or above this score. Half-way is not an
#: arbitrary midpoint: it is the exact value reached when every required marker
#: is present and nothing corroborates, which is what the pre-R-3 guards tested.
CLAIM_THRESHOLD = 0.5

MarkerKind = Literal["required", "corroborating", "exclusive", "excluding"]

#: Where a registration's own code can run, and therefore where it can break.
#: `integrity_check` is the one such site outside `resolve`: the orchestrator
#: invokes registry-supplied checks after a claim (R-3 §7.2).
FailureStage = Literal["detect", "parse", "integrity_check"]


class AmbiguousParserError(RuntimeError):
    """Two or more parsers claimed one document and no rule separates them.

    Raised only on the deterministic path, where there is no fallback to route
    to. On the automatic path the ambiguity becomes a flagged review outcome
    instead — see `Dispatch`.
    """

    def __init__(self, candidates: Sequence[tuple[str, float]]) -> None:
        self.candidates = tuple(candidates)
        listed = ", ".join(f"{name} ({score:.2f})" for name, score in self.candidates)
        super().__init__(f"ambiguous statement: {listed}")


class ParserCrashError(RuntimeError):
    """Every parser that could have claimed this document raised (W3-1).

    Raised only on the deterministic path, in place of the generic "no
    deterministic parser matched this statement" — which is a different and
    misleading finding. "No parser matched" ranks a bank for future layout
    work; this says our own code broke on a document we already claim to know,
    and the two must never be confused in a triage queue.

    Subclasses `RuntimeError` so every existing caller that already handles the
    deterministic refusal keeps working unchanged.

    The message carries registry ids and exception class names only. A parser's
    own exception message routinely quotes the fragment of the statement that
    provoked it, and this string reaches logs, job records and operator views.
    """

    def __init__(self, failures: Sequence["ParserFailure"]) -> None:
        self.failures = tuple(failures)
        listed = ", ".join(
            f"{failure.parser_id} ({failure.stage}: {failure.exception})"
            for failure in self.failures
        ) or "unknown parser"
        super().__init__(f"deterministic parser crashed: {listed}")


# ---------------------------------------------------------------------------
# Markers and scoring
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Marker:
    """One piece of evidence a registration looks for in the source text.

    `test` receives the raw markdown and must be pure, total and cheap: a
    substring or precompiled-regex check, no I/O, no exceptions, no parsing.
    A full registry sweep runs every marker of every registration, and that
    sweep has to stay affordable for a 3,500-document discovery run.
    """

    id: str
    test: Callable[[str], bool]
    kind: MarkerKind = "required"


def required(marker_id: str, test: Callable[[str], bool]) -> Marker:
    """Evidence without which the registration cannot claim."""
    return Marker(marker_id, test, "required")


def corroborating(marker_id: str, test: Callable[[str], bool]) -> Marker:
    """Evidence that raises confidence but is not needed to claim."""
    return Marker(marker_id, test, "corroborating")


def exclusive(marker_id: str, test: Callable[[str], bool]) -> Marker:
    """A sentinel only this document class can contain: an immediate 1.0."""
    return Marker(marker_id, test, "exclusive")


def excluding(marker_id: str, test: Callable[[str], bool]) -> Marker:
    """Evidence that positively rules the registration out: an immediate 0.0."""
    return Marker(marker_id, test, "excluding")


#: The OCR/native-text layer prefixes every document with a comment naming the
#: file it came from. Filenames are operator-supplied metadata — trivially
#: wrong, and on the discovery archive folder-derived guesses — so they are not
#: evidence about what a document *is*.
SOURCE_COMMENT_RE = re.compile(r"^<!--\s*SOURCE:.*?-->\s*$", re.MULTILINE | re.IGNORECASE)


def admissible_text(markdown: str) -> str:
    """The part of `markdown` detection is allowed to look at.

    Strips the source-filename comment. Applied centrally, before any parser's
    own normalization, so filename text is structurally inadmissible for all
    registrations rather than by each parser's good intentions — R-4 found two
    that were reading it (R4_CONFORMANCE_FINDINGS.md R4-1, R4-2), one of which
    recognised its own corpus document *only* by its filename.

    Parsing is unaffected: `parse` still receives the whole document.
    """
    return SOURCE_COMMENT_RE.sub("", markdown)


def make_detector(
    markers: Sequence[Marker], normalize: Callable[[str], str] | None = None
) -> Callable[[str], "Detection"]:
    """Build a parser module's `detect` from its markers.

    One implementation, used by both the parser module and its `Registration`,
    so the two can never disagree about what the parser recognises. `normalize`
    is the parser's own preprocessing — upper-casing, image-tag stripping,
    mojibake repair — applied once per document rather than once per marker,
    and always to text the filename comment has already been removed from.
    """

    def detect(markdown: str) -> "Detection":
        text = admissible_text(markdown)
        return score_markers(markers, normalize(text) if normalize else text)

    return detect


@dataclass(frozen=True)
class Detection:
    """What one registration concluded about one document, and why."""

    score: float
    matched: tuple[str, ...] = ()
    excluded_by: str | None = None

    @property
    def claims(self) -> bool:
        return self.score >= CLAIM_THRESHOLD


def score_markers(markers: Iterable[Marker], markdown: str) -> Detection:
    """Turn marker outcomes into a `Detection` by the documented formula."""
    markers = tuple(markers)

    for marker in markers:
        if marker.kind == "excluding" and marker.test(markdown):
            return Detection(0.0, (), excluded_by=marker.id)

    for marker in markers:
        if marker.kind == "exclusive" and marker.test(markdown):
            return Detection(1.0, (marker.id,))

    requirements = [m for m in markers if m.kind == "required"]
    corroborations = [m for m in markers if m.kind == "corroborating"]
    satisfied = [m for m in requirements if m.test(markdown)]
    supporting = [m for m in corroborations if m.test(markdown)]
    matched = tuple(m.id for m in (*satisfied, *supporting))

    if len(satisfied) != len(requirements):
        # Weak: some real evidence, but not enough to claim. The denominator
        # carries a +1 so that a partial match can never reach the threshold no
        # matter how many markers fired, while still ranking near-misses above
        # documents nothing recognised — which is what makes "this almost
        # matched" visible in telemetry instead of indistinguishable from
        # "never heard of this bank".
        hits = len(satisfied) + len(supporting)
        total = len(requirements) + len(corroborations) + 1
        return Detection(round(CLAIM_THRESHOLD * hits / total, 6), matched)

    if not corroborations:
        return Detection(CLAIM_THRESHOLD, matched)
    bonus = (1.0 - CLAIM_THRESHOLD) * (len(supporting) / len(corroborations))
    return Detection(round(CLAIM_THRESHOLD + bonus, 6), matched)


# ---------------------------------------------------------------------------
# Registrations
# ---------------------------------------------------------------------------

#: A bank-specific document-integrity check. Returns human-readable
#: contradiction notes; an empty list means nothing to report. Registered per
#: parser so the orchestrator never names a bank.
IntegrityCheck = Callable[[str, Statement], list[str]]


class Parser(Protocol):
    """The contract every deterministic parser satisfies."""

    id: str
    bank: str

    def detect(self, markdown: str) -> Detection: ...

    def parse(self, markdown: str) -> Statement | None: ...


@dataclass(frozen=True)
class Registration:
    """One parser's entry in the registry."""

    id: str
    bank: str
    markers: tuple[Marker, ...]
    parse: Callable[[str], Statement | None]
    #: The parser's own text preprocessing, applied before the markers run.
    #: Held as registry data so `Registration.detect` and the parser module's
    #: `detect` are the same computation rather than two copies of it.
    normalize: Callable[[str], str] | None = None
    #: Coarse priority band. `10` — a narrower document class that shadows a
    #: broader one; `100` — normal; `900` — deliberate last resort. Bands order
    #: the registry; they are not a place to hide precedence between two
    #: parsers that can both claim a document. Use `supersedes` for that.
    band: int = 100
    #: Ids this registration outranks outright when both claim one document.
    supersedes: frozenset[str] = frozenset()
    #: False for document classes that are not a complete bank statement
    #: (an online transaction export, say). Read by the pipeline's quality and
    #: integrity assessment instead of a bank-name literal.
    formal_statement: bool = True
    #: How to describe this document class when `formal_statement` is False.
    #: Held here rather than in the orchestrator so the pipeline can report a
    #: document class it has no knowledge of.
    informal_quality_note: str | None = None
    informal_integrity_note: str | None = None
    #: Bank-specific integrity checks, run only when this parser claimed.
    integrity_checks: tuple[IntegrityCheck, ...] = ()

    def detect(self, markdown: str) -> Detection:
        text = admissible_text(markdown)
        return score_markers(self.markers, self.normalize(text) if self.normalize else text)

    @property
    def sort_key(self) -> tuple[int, str]:
        return (self.band, self.id)


_REGISTRY: dict[str, Registration] = {}


def register(registration: Registration) -> Registration:
    """Add a registration. Duplicate ids are a programming error, not a merge."""
    if registration.id in _REGISTRY:
        raise ValueError(f"duplicate parser id: {registration.id}")
    if not registration.markers:
        raise ValueError(f"{registration.id} registers no markers and could never claim")
    _REGISTRY[registration.id] = registration
    return registration


def clear_registry() -> None:
    """Empty the registry. For tests that build a synthetic one; never in
    production code."""
    _REGISTRY.clear()


def registrations() -> tuple[Registration, ...]:
    """Every registration, in dispatch order — a pure function of the data."""
    return tuple(sorted(_REGISTRY.values(), key=lambda reg: reg.sort_key))


def by_id(parser_id: str) -> Registration:
    return _REGISTRY[parser_id]


def by_bank_label(bank: str | None) -> Registration | None:
    """The registration whose bank label matches, or None.

    Used only for documents that no parser claimed — an LLM extraction that
    named a bank we do have a parser for still gets that bank's integrity
    checks and formal-statement status. Without this the registry-based
    mechanism would silently narrow today's behaviour, which used the bank
    label alone.

    Ambiguous labels resolve to the lowest `(band, id)`, deterministically.
    """
    if not bank:
        return None
    wanted = bank.strip().casefold()
    for registration in registrations():
        if registration.bank.casefold() == wanted:
            return registration
    return None


def validate_registry() -> None:
    """Every `supersedes` target exists and the graph has no cycle."""
    known = set(_REGISTRY)
    for registration in _REGISTRY.values():
        unknown = registration.supersedes - known
        if unknown:
            raise ValueError(f"{registration.id} supersedes unknown parser(s): {sorted(unknown)}")

    colour: dict[str, int] = {}

    def visit(node: str, trail: tuple[str, ...]) -> None:
        state = colour.get(node, 0)
        if state == 1:
            raise ValueError(f"supersedes cycle: {' -> '.join((*trail, node))}")
        if state == 2:
            return
        colour[node] = 1
        for target in sorted(_REGISTRY[node].supersedes):
            visit(target, (*trail, node))
        colour[node] = 2

    for node in sorted(_REGISTRY):
        visit(node, ())


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParserFailure:
    """One registration's crash, reduced to the facts that are safe to keep.

    `exception` is the exception's CLASS NAME and nothing else. An exception
    message routinely quotes the fragment of the document that provoked it
    ("month must be in 1..12", "invalid literal for int(): <a line of the
    statement>"), and these facts travel into telemetry, discovery rows and
    operator views — the same sensitivity invariant H-3 states for records
    (H3_SCHEMA I1). The message is not stored anywhere, not even locally:
    reproducing a crash is a debugging act performed against the document, not
    a fact the platform carries around.
    """

    parser_id: str
    stage: FailureStage
    exception: str


def _guarded(stage: FailureStage, registration: Registration, call, failures):
    """Run one registry callable; a crash becomes a recorded `ParserFailure`.

    Returns `None` when the call raised, which both callers read as "this
    registration produced nothing" — a crashing `detect` cannot claim, and a
    crashing `parse` yields no statement.

    `Exception`, deliberately not `BaseException`: `KeyboardInterrupt`,
    `SystemExit` and `MemoryError` are statements about the process, not about
    the parser, and swallowing them would make the runner unkillable and hide
    a machine that is out of memory. They still propagate.
    """
    try:
        return call()
    except Exception as exc:
        failures.append(ParserFailure(registration.id, stage, type(exc).__name__))
        return None


@dataclass(frozen=True)
class Dispatch:
    """The result of routing one document."""

    outcome: Literal["claimed", "ambiguous", "unclaimed", "parser_exception"]
    registration: Registration | None = None
    detection: Detection | None = None
    #: Every surviving claimant as (id, score), best first. Populated for
    #: `claimed` and `ambiguous` alike, so telemetry can see the runner-up.
    candidates: tuple[tuple[str, float], ...] = ()
    #: Claimants whose `parse` returned None before the winner was found. A
    #: parser that repeatedly detects and then declines is a defect signal the
    #: or-chain made invisible.
    attempted: tuple[str, ...] = ()
    #: Registrations that raised, in the order they ran. A crash is NOT an
    #: `attempted` entry: "detected, then declined" and "detected, then broke"
    #: are different findings and the platform must be able to count them
    #: apart.
    exceptions: tuple[ParserFailure, ...] = ()
    statement: Statement | None = field(default=None, compare=False)

    @property
    def parser_id(self) -> str | None:
        return self.registration.id if self.registration else None

    @property
    def crashed(self) -> tuple[str, ...]:
        """Ids of the registrations that raised, deduplicated, in order."""
        return tuple(dict.fromkeys(failure.parser_id for failure in self.exceptions))


def safe_detect(registration: Registration, markdown: str, failures: list | None = None) -> Detection:
    """`registration.detect`, total by construction.

    A registration whose detection crashes scores 0.0 and therefore cannot
    claim — fail closed, never "assume it matched". The event is not lost: it
    is appended to `failures` when the caller is collecting them.

    A `detect` that returns something other than a `Detection` is the same
    fail-closed 0.0, recorded as nothing: it did not raise, so there is no
    exception class to name and inventing one would put a fiction in
    telemetry. `tests/test_parser_registry_entries.py` is what catches that
    contract breach, at the registration level where it belongs.
    """
    detection = _guarded("detect", registration, lambda: registration.detect(markdown),
                         failures if failures is not None else [])
    return detection if isinstance(detection, Detection) else Detection(0.0)


def _surviving_claimants(
    markdown: str, failures: list | None = None
) -> list[tuple[Registration, Detection]]:
    """Claimants after `supersedes` pruning. `failures` is optional so that the
    diagnostic callers (the corpus parity tests) keep their pre-W3-1 signature:
    they ask what claimed a document, not what broke doing it."""
    failures = failures if failures is not None else []
    claimants = [
        (registration, detection)
        for registration in registrations()
        if (detection := safe_detect(registration, markdown, failures)).claims
    ]
    dominated = {target for registration, _ in claimants for target in registration.supersedes}
    return [(reg, det) for reg, det in claimants if reg.id not in dominated]


def resolve(markdown: str) -> Dispatch:
    """Route one document. Never raises.

    Detection first, for every registration; then `supersedes` pruning; then
    the ambiguity decision — deliberately **before** any parse runs, so an
    ambiguous document can never be rescued by whichever parser happens to
    succeed. Only then are the survivors parsed, best score first.

    Crashes (W3-1) do not interrupt any of that. A registration that raises in
    `detect` drops out of the claimant set; a registration that raises in
    `parse` is skipped and the next claimant is tried, which is the same
    fallthrough the `None` return already gets. What changes is only the final
    verdict: if no statement was produced and something raised on the way, the
    outcome is `parser_exception` — "we do not know whether this document was
    parseable, because our own code broke" — and not `unclaimed`, which would
    file a defect of ours as a gap in our layout knowledge.

    `ambiguous` still outranks it: two claimants is a resolvable registry fact
    that a human acts on, and it is already routed to review.
    """
    failures: list[ParserFailure] = []
    survivors = _surviving_claimants(markdown, failures)
    candidates = tuple(
        sorted(((reg.id, det.score) for reg, det in survivors), key=lambda item: (-item[1], item[0]))
    )

    if len(survivors) > 1:
        return Dispatch("ambiguous", candidates=candidates, exceptions=tuple(failures))

    ranked = sorted(survivors, key=lambda item: (-item[1].score, item[0].id))
    attempted: list[str] = []
    for registration, detection in ranked:
        crashes_before = len(failures)
        statement = _guarded("parse", registration, lambda: registration.parse(markdown), failures)
        if statement is not None:
            return Dispatch(
                "claimed",
                registration=registration,
                detection=detection,
                candidates=candidates,
                attempted=tuple(attempted),
                exceptions=tuple(failures),
                statement=statement,
            )
        if len(failures) == crashes_before:
            # Declined, rather than broke: an `attempted` entry (§4.3).
            attempted.append(registration.id)

    # Nothing produced a statement. Without a crash that is exactly what the
    # or-chain reported — no deterministic parser matched — but now the
    # near-misses are recorded. With a crash it is a defect of ours, and it is
    # named as one.
    return Dispatch(
        "parser_exception" if failures else "unclaimed",
        candidates=candidates,
        attempted=tuple(attempted),
        exceptions=tuple(failures),
    )


def run_integrity_checks(
    registration: Registration, markdown: str, statement: Statement
) -> tuple[list[str], tuple[ParserFailure, ...]]:
    """Every check this registration declares, guarded exactly like `parse`.

    `integrity_checks` are registry-supplied callables that the orchestrator
    invokes, so they are the one remaining place where parser-owned code runs
    outside the `resolve` seam and could raise into the pipeline. The guarding
    policy lives here, next to the seam it belongs to, rather than as a second
    `try` written into the orchestrator.

    A check that raises contributes no findings — its answer is simply unknown,
    which is a fact the caller must surface rather than read as "nothing to
    report". Returns `(contradiction notes, failures)`.
    """
    notes: list[str] = []
    failures: list[ParserFailure] = []
    for check in registration.integrity_checks:
        found = _guarded("integrity_check", registration, lambda c=check: c(markdown, statement), failures)
        if found:
            notes.extend(found)
    return notes, tuple(failures)


def detection_report(markdown: str) -> tuple[tuple[str, Detection], ...]:
    """Every registration's `Detection` for one document, best first.

    Diagnostic only — used by the conformance tests, by telemetry's near-miss
    vector and by discovery adjudication when a document resolved unexpectedly.
    Guarded like `resolve`: a diagnostic sweep must not be the thing that
    aborts a run.
    """
    scored = [
        (registration.id, safe_detect(registration, markdown)) for registration in registrations()
    ]
    return tuple(sorted(scored, key=lambda item: (-item[1].score, item[0])))


def with_overrides(registration: Registration, **changes) -> Registration:
    """A copy of `registration` with fields replaced. For tests."""
    return replace(registration, **changes)
