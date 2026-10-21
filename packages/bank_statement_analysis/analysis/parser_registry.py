"""Parser protocol and registry dispatch (R-3).

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

import hashlib
import json
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
    "PreparedDocument",
    "Registration",
    "admissible_text",
    "by_bank_label",
    "by_id",
    "clear_registry",
    "corroborating",
    "excluding",
    "make_detector",
    "exclusive",
    "prepare",
    "register",
    "registrations",
    "registry_fingerprint",
    "registry_key_material",
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
    """The part of `markdown` the analysis is allowed to look at.

    Strips the source-filename comment. Applied centrally, before any parser's
    own normalization, so filename text is structurally inadmissible for all
    registrations rather than by each parser's good intentions — R-4 found two
    that were reading it, one of which
    recognised its own corpus document *only* by its filename.

    Parsing is covered too, since W3 FILENAME-BOUNDARY: `analysis.pipeline.
    analyze_markdown` applies this at its single parse seam, so `parse` sees
    the same admissible text detection scored. The previous carve-out ("parse
    still receives the whole document") was the hole: F-PROVENANCE measured 7
    of 10 sampled parsers reading periods, ADB inputs and inferred years out
    of the filename, so a rename alone could change a published answer.

    Idempotent, and safe to apply more than once on the same document.
    """
    return SOURCE_COMMENT_RE.sub("", markdown)


class PreparedDocument:
    """One document's text, prepared once for a whole registry sweep.

    Detection is two stages: **prepare the text**, then **run the markers over
    it**. The first stage is a property of the document and of the parser's
    normalization — not of the registration — and the registry sweeps every
    registration over the same document, so preparing per registration does the
    same work sixty-eight times. Measured on the largest pinned document
    (62,702 chars) that was four fifths of a 242 ms sweep: `admissible_text`
    sixty-eight times (116 ms) and thirty-six normalizations (77 ms), to
    produce, in the end, five distinct strings.

    This object does each preparation once:

    * `admissible_text` once, whatever the registry's size;
    * each *distinct* normalization callable once — registrations that share a
      normalizer (the two Chase entries, the two Found entries, the two scanned
      small banks) share its output;
    * each *distinct resulting text* is interned to one object, so two
      registrations whose normalizations happen to agree on this document hold
      the same string, and a marker they also share is evaluated once.

    Every one of those is exact rather than approximate. `admissible_text` and
    the normalizers are pure functions of the text (the module contract for
    `normalize`), and `Marker.test` is documented pure, total and cheap — so
    computing a value twice can only ever produce the value already computed.
    Nothing here decides that a registration *cannot* claim; every registration
    still runs every one of its markers over exactly the text it ran them over
    before. `tests/test_parser_parity.py` and the full-archive equivalence
    sweep are what hold that to the letter.

    Not shared between documents and not cached anywhere global: a document's
    text is the sensitive thing this codebase is careful never to leave lying
    around (see `ParserFailure`).

    **How long the prepared texts live, exactly (W3 #PREPHAND).** They used to
    live for the sweep that asked for them. They now live as long as the
    `Dispatch` that sweep produced, because `resolve` publishes this object as
    `Dispatch.prepared` so a second sweep over the same document can replay it
    instead of rebuilding it — so in the discovery run that is one document's
    whole analysis and its telemetry record, not the sweep alone. What is held
    is real: on the largest pinned document (62,702 chars) the five distinct
    prepared texts are 312,342 characters, five times the document, plus a
    190-entry marker memo.

    That is safe for the reason the rest of this file is safe, and the reason
    is structural rather than a promise: **nothing retains a `Dispatch`.** It
    is deliberately not a field on `Report` (see `analysis.pipeline.
    analyze_markdown`, which explains why), `telemetry.record.dispatch_section`
    projects named fields and never the object, no code path serializes a
    `Dispatch` generically, and the collector that holds one is rebuilt per
    document. So the texts are released with the document that produced them,
    one document at a time, exactly as before — later than before, but no
    wider and never written anywhere.
    """

    __slots__ = ("_admissible", "_texts", "_interned", "_marker_results", "_preparations")

    def __init__(self, markdown: str) -> None:
        self._admissible = admissible_text(markdown)
        #: normalize callable (or None) -> the interned text it produces here.
        self._texts: dict[object, str] = {None: self._admissible}
        #: value -> the one instance of it every registration shares.
        self._interned: dict[str, str] = {self._admissible: self._admissible}
        #: (marker test, prepared text) -> outcome, for a test two
        #: registrations share and run over the same text. Worth 8.5 ms of a
        #: 157 ms sweep on the largest pinned document.
        self._marker_results: dict[tuple[object, str], bool] = {}
        #: How many text preparations this document actually cost. The budget
        #: test reads it: it is the load-independent statement of the property.
        self._preparations = 1

    @property
    def admissible(self) -> str:
        """The document with the source-filename comment removed."""
        return self._admissible

    @property
    def preparations(self) -> int:
        """Text preparations performed: `admissible_text`, plus one per
        distinct normalization. A full sweep of a 68-registration registry
        costs 33 of these; before this seam it cost 104."""
        return self._preparations

    def text_for(self, normalize: Callable[[str], str] | None) -> str:
        """The text `normalize` sees on this document, computed at most once.

        **Interning trusts the value a normalizer returns, so it is applied
        only to an exact `str`.** Two things go wrong otherwise, and both are
        silent or newly-fatal rather than merely slow. An unhashable return
        cannot be a dict key, so the intern would raise where the base merely
        handed the object to the markers — a `ParserFailure` that did not
        exist before, fail-closed but a NEW failure mode. And a `str` subclass
        carrying its own `__eq__`/`__hash__` can compare equal to a text
        another normalizer produced, so `setdefault` would hand this
        registration a *different* string to run its markers over. A
        non-conforming normalizer therefore takes the base path — run per
        call, never interned, never memoized — which costs nothing, because
        the registry has none and
        `tests/test_parser_registry_entries.py` is what keeps it that way.

        An unhashable normalizer *callable* is handled the same way, for the
        same reason.
        """
        try:
            return self._texts[normalize]
        except KeyError:
            pass
        except TypeError:  # pragma: no cover — no registry entry is unhashable
            return normalize(self._admissible) if normalize else self._admissible

        produced = normalize(self._admissible)  # type: ignore[misc]
        self._preparations += 1
        if type(produced) is not str:
            return produced
        text = self._interned.setdefault(produced, produced)
        self._texts[normalize] = text
        return text


def prepare(markdown: str) -> PreparedDocument:
    """The text of one document, ready for a sweep. See `PreparedDocument`."""
    return PreparedDocument(markdown)


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
        prepared = prepare(markdown)
        return _score(markers, prepared.text_for(normalize), prepared)

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
    return _score(markers, markdown, None)


def _score(
    markers: Iterable[Marker], markdown: str, prepared: PreparedDocument | None
) -> Detection:
    """`score_markers`, optionally reusing outcomes already known for this text.

    `prepared` carries the sweep's memo of `(marker test, text) -> outcome`.
    It changes nothing about which markers a registration consults or in what
    order: a memo hit is the value the call would have returned, because
    `Marker.test` is pure by contract. A test that raises is not memoized and
    propagates exactly as before, to the `_guarded` seam that owns it.

    The memo keys on the text, so it is used only for an exact `str` — the
    same hazard `PreparedDocument.text_for` describes, one level on: a `str`
    subclass with its own `__eq__`/`__hash__` could otherwise collide with
    another registration's text and return that registration's marker outcome.
    """
    markers = tuple(markers)
    if prepared is None or type(markdown) is not str:
        def fired(marker: Marker) -> bool:
            return bool(marker.test(markdown))
    else:
        results = prepared._marker_results

        def fired(marker: Marker) -> bool:
            key = (marker.test, markdown)
            try:
                hit = results.get(key)
            except TypeError:  # pragma: no cover — an unhashable test
                return bool(marker.test(markdown))
            if hit is None:
                hit = results[key] = bool(marker.test(markdown))
            return hit

    for marker in markers:
        if marker.kind == "excluding" and fired(marker):
            return Detection(0.0, (), excluded_by=marker.id)

    for marker in markers:
        if marker.kind == "exclusive" and fired(marker):
            return Detection(1.0, (marker.id,))

    requirements = [m for m in markers if m.kind == "required"]
    corroborations = [m for m in markers if m.kind == "corroborating"]
    satisfied = [m for m in requirements if fired(m)]
    supporting = [m for m in corroborations if fired(m)]
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
        return self.detect_prepared(prepare(markdown))

    def detect_prepared(self, prepared: PreparedDocument) -> Detection:
        """`detect` against text a sweep has already prepared.

        The same computation as `detect` — `detect` is this method over a
        `PreparedDocument` of one — but the preparation is shared with every
        other registration sweeping the same document. See `PreparedDocument`.
        """
        return _score(self.markers, prepared.text_for(self.normalize), prepared)

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
    """Every `supersedes` target exists, the graph has no cycle, and every
    registered callable can be NAMED.

    The third check exists because of the registry fingerprint (W3 §REGFP):
    `_declared_callable` records `parse`, `normalize` and each integrity check
    as `module.qualname`, and an object with no `__qualname__` — a
    `functools.partial`, a callable instance — cannot be told apart from any
    other object of its type. Checking it HERE, where `load()` applies the
    entries table, is what makes that refusal a registration-time failure
    instead of a surprise the first time somebody derives a cache key: an
    invalid registration never reaches production, and
    :func:`analysis_settings_key` is total over any registry that passed this
    function.
    """
    known = set(_REGISTRY)
    for registration in _REGISTRY.values():
        unknown = registration.supersedes - known
        if unknown:
            raise ValueError(f"{registration.id} supersedes unknown parser(s): {sorted(unknown)}")
        _declared_callables(registration)

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
# Registry fingerprint (W3 §REGFP)
# ---------------------------------------------------------------------------

#: The SHAPE of `registry_key_material`, not its contents. The contents change
#: whenever a parser is registered; this integer changes only when we decide to
#: hash a DIFFERENT set of fields. Both rotate the digest, and only this one
#: says the rotation was a decision about the instrument rather than a change in
#: the registry — which is the difference a merge review needs to read.
REGISTRY_MATERIAL_VERSION = 1


def _ensure_registry_loaded() -> None:
    """Populate the production registry if, and only if, nothing has loaded it.

    The fingerprint's whole value is that a process which never imported the
    parsers computes the SAME key as the one that did. Telemetry's read-only
    artifact join is exactly such a process — it imports
    `webapp.artifact_cache` lazily and analyses nothing — so if the fingerprint
    simply read an empty `_REGISTRY` there, the join would derive a key no
    production run ever wrote, resolve zero payloads, and report
    `REASON_PAYLOAD_ABSENT` on every row while looking perfectly healthy. That
    is the FILENAME-BOUNDARY failure mode a second time, and the fix is
    structural rather than a note in someone's docstring: the material
    materializes the registry it claims to describe.

    The `if _REGISTRY` guard is what keeps this out of a test's way, and it is
    exact rather than approximate. A test that has cleared the registry to build
    a synthetic one has, by definition, already imported
    `parser_registry_entries` (that import is what filled the registry it
    cleared), so the import below is a no-op against `sys.modules` and cannot
    resurrect the real registrations underneath the test. A test that cleared
    the registry and registered nothing gets the honest fingerprint of an empty
    registry — which is a real state a real analysis can run in, and a distinct
    partition of the cache, not an error.

    Deliberately a function-local import: `parser_registry_entries` imports this
    module and every parser module, so a module-level import here would be a
    cycle and would make `import analysis.parser_registry` cost the whole parser
    package.
    """
    if _REGISTRY:
        return
    from . import parser_registry_entries  # noqa: F401  (its import registers)


def _declared_callable(parser_id: str, field_name: str, fn: object) -> str:
    """A stable, cross-process name for a callable held as registry data.

    `module.qualname`, because that is what a registration DECLARES: the entries
    table binds each field to a named function in a parser module, and rebinding
    it to a different one is a change to the registry that this fingerprint
    exists to see. Never `id()` and never `repr()` — both encode a memory
    address, so they would differ between two runs of the same code and rotate
    the analysis cache on every process start.

    What this name does NOT capture is the function's BODY. That is deliberate
    and is the boundary this whole card sits on: code changes are the stage
    version's job (`webapp/artifact_cache.py`), registry SHAPE is this digest's.

    A callable with no `__qualname__` — a `functools.partial`, a callable
    instance — is REFUSED rather than reduced to its type, because every partial
    in the process shares one type name: rewiring `parse` from one partial to
    another would leave the digest unmoved and go on serving the old parser's
    cached answers. That is precisely the silent under-partitioning the digest
    is here to end, so it fails loudly.

    WHERE it fails is `validate_registry`, which `load()` runs over the entries
    table — not `register`, which takes one registration at a time and validates
    nothing, and not the first cache-key derivation, which would be an
    unrelated call site discovering somebody else's mistake. Nothing in the
    registry is such an object today and
    `tests/test_parser_registry_fingerprint.py` holds that for all 72.
    """
    qualname = getattr(fn, "__qualname__", None)
    if not isinstance(qualname, str) or not qualname:
        raise TypeError(
            f"{parser_id}.{field_name} is a {type(fn).__name__} with no "
            "__qualname__, so the registry fingerprint cannot name it apart "
            "from any other object of its type; register a named function"
        )
    module = getattr(fn, "__module__", None)
    return f"{module}.{qualname}" if module else qualname


def _declared_callables(registration: Registration) -> dict[str, object]:
    """One registration's three callable-valued fields, as declared names.

    ONE computation, called by `validate_registry` (where an unnameable
    callable is refused) and by `registry_key_material` (where these names are
    key material). Two copies would be two things that can come to disagree
    about what the registry declares — and the half that drifted would be the
    half nobody reads.
    """
    return {
        "parse": _declared_callable(registration.id, "parse", registration.parse),
        "normalize": None
        if registration.normalize is None
        else _declared_callable(registration.id, "normalize", registration.normalize),
        "integrity_checks": [
            _declared_callable(registration.id, f"integrity_checks[{index}]", check)
            for index, check in enumerate(registration.integrity_checks)
        ],
    }


def registry_key_material() -> dict[str, object]:
    """The registry reduced to the declared facts that can change an analysis.

    Published (rather than kept private inside the digest) so that a key
    rotation can be DIFFED: two dumps of this structure say which registration
    moved and in which field, where two hex digests only say "something did".

    In dispatch order — `registrations()`, i.e. `(band, id)` — never dict
    insertion order, and every set is sorted, so the digest is a pure function
    of the data on any platform and under any `PYTHONHASHSEED`.

    INCLUDED, with the reason each one can change a published answer:

    * `id` — the identity dispatch resolves to, the key `count_semantics` and
      the discovery rows are grouped by, and the thing whose mere presence or
      absence decides whether a document is claimed at all.
    * `bank` — published on unclaimed documents through `by_bank_label`, and
      the label discovery normalizes into `registered_bank_tokens`.
    * `band` — half of the sort key; ordering decides which claimant is parsed
      first when several survive. Hashed exactly as declared, because
      `sort_key` uses it exactly as declared: `100.9` and `100` order
      differently and must therefore hash differently.
    * `supersedes` — sorted, because a `frozenset` iterates in hash order. These
      edges decide the winner between two claimants outright; adding one turns
      an `ambiguous` review outcome into a claim, and removing one does the
      reverse.
    * `markers` — each marker's `(id, kind)` in declared order. The kinds are
      the scoring formula's whole input (`_score`): an `excluding` marker sends
      a registration to 0.0, an `exclusive` one to 1.0, and moving a marker
      between `required` and `corroborating` moves the score across
      `CLAIM_THRESHOLD`. Order is not load-bearing for the score, but it does
      pick which `excluding` marker is reported as `excluded_by` and the order
      of `Detection.matched`; it is included because keeping the declared
      sequence is free and over-partitioning is the safe direction (the module
      contract in `webapp/artifact_cache.py`).
    * `parse`, `normalize` — by declared name (see `_declared_callable`).
      `normalize` is detection's text preparation and `parse` decides whether a
      claimant yields a statement or falls through to the next one, so a
      rewiring of either changes the outcome with nothing else in the key
      moving.
    * `formal_statement`, `informal_quality_note`, `informal_integrity_note` —
      not dispatch, but `analysis/pipeline.py` copies these strings into the
      published quality notes and integrity notes and raises
      `not_a_formal_statement` off the flag. They are registry DATA that lands
      verbatim in the cached payload.
    * `integrity_checks` — by declared name and count. They decide which
      bank-specific contradiction notes a claimed document publishes.

    EXCLUDED, with the reason each one cannot:

    * `Marker.test`, and the bodies of `parse`, `normalize` and the integrity
      checks — code, not data. A content hash cannot see code, and the platform
      already has the lever that does: the stage version, bumped in the same
      commit as the behaviour change. Hashing source text here would rotate the
      whole analysis cache on a comment edit and would still miss a change in
      anything those functions call.
    * `Registration.detect` / `detect_prepared` / `sort_key` — derived from the
      fields above, so hashing them would be counting the same fact twice.
    * Everything outside the registry that a parser reads (`count_semantics`
      mappings, the shared money grammar, the ADB engine): real output material,
      and squarely the stage version's job. This digest claims to fingerprint
      the REGISTRY, not the analysis package, and a digest that quietly claimed
      more than it hashes would be worse than none.
    """
    _ensure_registry_loaded()
    entries: list[dict[str, object]] = []
    for registration in registrations():
        entries.append(
            {
                "id": registration.id,
                "bank": registration.bank,
                # VERBATIM, not `int(...)`: `sort_key` uses the value as
                # declared, so a `100.9` that orders differently from `100`
                # must hash differently from it too. Coercing here would have
                # been a narrowing the sort does not perform.
                "band": registration.band,
                "supersedes": sorted(registration.supersedes),
                "markers": [[marker.id, marker.kind] for marker in registration.markers],
                "formal_statement": bool(registration.formal_statement),
                "informal_quality_note": registration.informal_quality_note,
                "informal_integrity_note": registration.informal_integrity_note,
                **_declared_callables(registration),
            }
        )
    return {"material_version": REGISTRY_MATERIAL_VERSION, "registrations": entries}


def registry_fingerprint() -> str:
    """UPPERCASE hex SHA-256 over `registry_key_material`.

    The hashing convention is the one `webapp/artifact_cache.py` established —
    `json.dumps(..., sort_keys=True, separators=(",", ":"))`, SHA-256, upper hex
    — reproduced here in three lines rather than imported, because `analysis`
    must not import `webapp` (the dependency runs the other way: the cache
    imports this module). The two are not allowed to drift apart on trust:
    `tests/test_parser_registry_fingerprint.py` asserts this digest equals the
    cache's own `text_sha256` of its own canonical JSON of the material.

    Recomputed on every call rather than memoized. Measured on the 72-entry
    registry: 27,289 bytes of material, 0.48 ms per call — about 1.6 seconds
    across a 3,380-document archive run, against which a memo would have to be
    invalidated by hand on `register`/`clear_registry` and would be one more
    thing that can go stale while reporting nothing wrong.
    """
    blob = json.dumps(registry_key_material(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest().upper()


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
    #: The text this routing was decided on, prepared once (see
    #: `PreparedDocument`). Published so that a SECOND sweep over the same
    #: document — telemetry's near-miss vector runs one, per H3_SCHEMA §4 —
    #: can reuse the preparation instead of repeating it. Reuse is the
    #: consumer's decision and is guarded on this text: nothing here obliges
    #: anyone to take it.
    #:
    #: `compare=False`, like `statement`: two dispatches are equal when they
    #: routed the same way, and which document object they were decided on is
    #: not part of that. `repr=False` because a `PreparedDocument` has no
    #: readable repr — it would print an address, not a fact.
    prepared: PreparedDocument | None = field(default=None, compare=False, repr=False)

    @property
    def parser_id(self) -> str | None:
        return self.registration.id if self.registration else None

    @property
    def crashed(self) -> tuple[str, ...]:
        """Ids of the registrations that raised, deduplicated, in order."""
        return tuple(dict.fromkeys(failure.parser_id for failure in self.exceptions))


def safe_detect(
    registration: Registration,
    document: str | PreparedDocument,
    failures: list | None = None,
) -> Detection:
    """`registration.detect`, total by construction.

    A registration whose detection crashes scores 0.0 and therefore cannot
    claim — fail closed, never "assume it matched". The event is not lost: it
    is appended to `failures` when the caller is collecting them.

    A `detect` that returns something other than a `Detection` is the same
    fail-closed 0.0, recorded as nothing: it did not raise, so there is no
    exception class to name and inventing one would put a fiction in
    telemetry. `tests/test_parser_registry_entries.py` is what catches that
    contract breach, at the registration level where it belongs.

    `document` may be a `PreparedDocument`, which is how a sweep shares one
    document's prepared text across every registration; a plain string is
    prepared here and behaves identically.
    """
    prepared = document if isinstance(document, PreparedDocument) else prepare(document)
    detection = _guarded("detect", registration, lambda: registration.detect_prepared(prepared),
                         failures if failures is not None else [])
    return detection if isinstance(detection, Detection) else Detection(0.0)


def _surviving_claimants(
    document: str | PreparedDocument, failures: list | None = None
) -> list[tuple[Registration, Detection]]:
    """Claimants after `supersedes` pruning. `failures` is optional so that the
    diagnostic callers (the corpus parity tests) keep their pre-W3-1 signature:
    they ask what claimed a document, not what broke doing it.

    `document` may be a `PreparedDocument`, exactly as in `safe_detect`: a
    caller that has already prepared this document's text hands it over rather
    than paying for the preparation twice."""
    failures = failures if failures is not None else []
    prepared = document if isinstance(document, PreparedDocument) else prepare(document)
    claimants = [
        (registration, detection)
        for registration in registrations()
        if (detection := safe_detect(registration, prepared, failures)).claims
    ]
    dominated = {target for registration, _ in claimants for target in registration.supersedes}
    return [(reg, det) for reg, det in claimants if reg.id not in dominated]


def resolve(document: str | PreparedDocument) -> Dispatch:
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

    `document` may be a `PreparedDocument` (`safe_detect`'s convention), and
    the `Dispatch` carries the preparation back out either way, so the sweep a
    document costs is paid once no matter how many sweeps read it.

    **The text `parse` receives is unchanged in both cases and that is
    deliberate.** A caller that passes a string gets exactly today's
    behaviour: detection scores the admissible text, `parse` receives the
    string as given. A caller that passes a `PreparedDocument` has already
    decided what the admissible text is, and `parse` receives that — which is
    the same bytes detection scored, and the same bytes
    `analysis.pipeline.analyze_markdown` has passed since FILENAME-BOUNDARY.
    Neither path may quietly re-strip the other's text: that would move the
    admissibility boundary from the one seam that states it.
    """
    if isinstance(document, PreparedDocument):
        prepared, markdown = document, document.admissible
    else:
        prepared, markdown = prepare(document), document
    failures: list[ParserFailure] = []
    survivors = _surviving_claimants(prepared, failures)
    candidates = tuple(
        sorted(((reg.id, det.score) for reg, det in survivors), key=lambda item: (-item[1], item[0]))
    )

    if len(survivors) > 1:
        return Dispatch("ambiguous", candidates=candidates, exceptions=tuple(failures),
                        prepared=prepared)

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
                prepared=prepared,
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
        prepared=prepared,
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


def detection_report(document: str | PreparedDocument) -> tuple[tuple[str, Detection], ...]:
    """Every registration's `Detection` for one document, best first.

    Diagnostic only — used by the conformance tests, by telemetry's near-miss
    vector and by discovery adjudication when a document resolved unexpectedly.
    Guarded like `resolve`: a diagnostic sweep must not be the thing that
    aborts a run.

    `document` may be a `PreparedDocument` — `resolve` publishes the one it
    swept on, and this is the second sweep it is published for. Reusing it is
    exact, not an approximation: a `PreparedDocument` holds `admissible_text`
    and each normalizer's output, both pure functions of the text, and a memo
    of marker outcomes over those texts, and `Marker.test` is pure by
    contract. A registration that raised is never memoized (see `_score`), so
    the guard is entered on this sweep exactly as it was on the first.
    """
    prepared = document if isinstance(document, PreparedDocument) else prepare(document)
    scored = [
        (registration.id, safe_detect(registration, prepared)) for registration in registrations()
    ]
    return tuple(sorted(scored, key=lambda item: (-item[1].score, item[0])))


def with_overrides(registration: Registration, **changes) -> Registration:
    """A copy of `registration` with fields replaced. For tests."""
    return replace(registration, **changes)
