# RFC — R-3: Parser protocol and registry dispatch

Author: Agent A (REEF). Date: 2026-08-06. Status: **PROPOSED — awaiting Ocean review.**
Task: WAVE2_BRIEF §3 "R-3" · MASTER_PLAN P1-1b / AD-1 · MERGE_PLAN §2.1 interface contract 1.
Baseline: `wave2-parser-platform` at R-2 (shared utilities merged into `analysis/money.py`).

**No R-3 code exists.** This document fixes the protocol signatures, score
semantics, registry data model, ordering and tie-break rules, ambiguity policy,
migration plan, and the corpus-wide parity control, so that Ocean can rule on
them before anything is built.

---

## 1. What dispatch does today

All line references are to the current tree (post-R-2).

### 1.1 The or-chain

`analysis/pipeline.py:357-402` is the entire dispatch mechanism:

```python
def _deterministic_statement(markdown: str) -> Statement | None:
    return (
        parse_columbia_bank_statement(markdown)
        or parse_first_farmers_statement(markdown)
        or parse_navigant_statement(markdown)
        ...                                    # 43 terms in total
        or parse_citizens_statement(markdown)
    )
```

Called once, at `analysis/pipeline.py:412`. Its 43 parser functions are imported
at `analysis/pipeline.py:18-58`. The chain has exactly the properties one would
expect and none that we want:

| Property | Today |
|---|---|
| Detection | Inside each `parse_*` function, as an early-return guard |
| Score | None — boolean |
| Order | Source-code line order in one function |
| Ambiguity | Impossible to observe: **first non-None wins, silently** |
| Adding a parser | Edit two places in the orchestrator (import block + chain) |
| Testing order | Not possible without running all 43 parsers |
| Recording which parser claimed a document | Not recorded; inferred from `stmt.bank` |

### 1.2 Detection evidence used today

Surveyed all 43 `parse_*_statement` entry points. Every one of them detects with
substring or regex tests over the whole flattened markdown, in one of three
shapes:

* **two required markers** — 26 parsers, e.g. `analysis/amex.py`:
  `if "americanexpress.com/businesscheckinghome" not in markdown or "Business Checking Account Statement" not in markdown: return None`
* **three or four required markers** — 7 parsers: `analysis/columbia_bank.py`,
  `analysis/first_farmers.py`, `analysis/navigant.py`, `analysis/relay.py` (4
  each), `analysis/pnc.py` and both `analysis/scanned_small_bank.py` entry
  points (3 each)
* **one marker, often itself a disjunction** — 10 parsers: `analysis/bmo.py`
  (`"BMO" or "BANK OF MONTREAL"`), `analysis/scotia.py`,
  `analysis/first_citizens.py`, `analysis/consumers.py`,
  `analysis/texas_bank.py`, `analysis/capital_one.py`, `analysis/chase.py`,
  `analysis/td_can.py`, and both `analysis/community_section.py` entry points

(26 + 7 + 10 = 43.)

Some normalize before matching (`markdown.upper()`, `_IMG_RE.sub("", markdown)`
in bofa/chase, `normalize_mojibake` in scanned_small_bank, `_plain_text` in
regions). None uses position, structure, or page geometry. **The registry does
not need to invent a new evidence model** — it needs to make the existing one
explicit, scored, and orderable. Anything richer is P2-1 (AD-7) territory.

### 1.3 Three hidden sub-dispatches

Three parsers contain a nested dispatch that the 43-term chain does not show:

| Location | Nested decision |
|---|---|
| `analysis/chase.py:356` | `_parse_chase_business_export` (defined at :71) is tried first; a Chase online export is a different document class producing `bank="Chase Transaction Export"` (`analysis/chase.py:126`) |
| `analysis/rbc.py:74` | `_parse_rbc_french_statement` (defined at :316) is tried before the English RBC layout |
| `analysis/td_can.py:303` | `_parse_native_td_canada` (defined at :210) is tried before the HTML-table layout |

So the real parser count is 46 decision points behind 43 registry-visible
entries. The audit CSVs confirm the RBC split is externally visible: they
contain both `royal-bank-of-canada-deterministic` (4) and
`banque-royale-du-canada-deterministic` (1).

### 1.4 Bank-name literals in the orchestrator

Four pieces of bank knowledge sit in `analysis/pipeline.py` today:

| Line(s) | Literal | Used for |
|---|---|---|
| `pipeline.py:153` | `stmt.bank == "Chase Transaction Export"` | `assess_quality` forces `needs_review` / `manual_review_required` |
| `pipeline.py:303` | `stmt.bank == "Chase Transaction Export"` | `assess_document_integrity` adds `not_a_formal_statement` |
| `pipeline.py:211-270` | `(stmt.bank or "").upper() != "BMO"` | `_bmo_summary_contradictions`, a BMO-specific second-summary reconciliation, called at :306 |
| `pipeline.py:33`, `:234` | `from .td_can import _parse_money` | consumed only by `_bmo_summary_contradictions` |

R-2 left `analysis/td_can.py`'s `_parse_money = parse_money` alias in place
precisely because removing the last one requires editing `pipeline.py`, which is
R-3's file.

### 1.5 Outcome vocabulary today

* claimed → `analysis/pipeline.py:414-416`; `model_used = f"{bank_label}-deterministic"`
  where `bank_label = (stmt.bank or "bank").lower().replace(" ", "-")`.
* unclaimed, `parse_mode="auto"` → LLM extraction (`pipeline.py:420`).
* unclaimed, `parse_mode="deterministic"` → `RuntimeError("no deterministic parser matched this statement")` (`pipeline.py:418-419`).
* ambiguous → **does not exist**. This RFC introduces it.

---

## 2. Proposed protocol

### 2.1 Signatures

```python
# analysis/parser_registry.py

CLAIM_THRESHOLD: Final[float] = 0.5

@dataclass(frozen=True)
class Detection:
    """What a parser concluded from the source text, and why."""
    score: float                      # 0.0 .. 1.0, see §2.2
    matched: tuple[str, ...] = ()     # marker ids that fired — the audit trail
    excluded_by: str | None = None    # marker id that positively ruled it out

    @property
    def claims(self) -> bool:
        return self.score >= CLAIM_THRESHOLD


class Parser(Protocol):
    id: str            # stable slug, never a display string: "chase", "rbc_fr"
    bank: str          # display label written to Statement.bank
    def detect(self, markdown: str) -> Detection: ...
    def parse(self, markdown: str) -> Statement | None: ...
```

`detect` contract:

1. **Pure and total.** No I/O, no network, no mutation, no exceptions. Given the
   same markdown it returns the same `Detection` forever.
2. **Evidence is the markdown only** — the flattened text of the document as the
   OCR/native ladder produced it, including any structured side-channel blocks
   already embedded in it (`WF_NATIVE_TRANSACTIONS`, `SOURCE_POSTING_DATES_*`).
   Filename, upload metadata, page images, prior results, and MoneyThumb output
   are **not** admissible evidence. Normalization the parser already performs
   today (`.upper()`, mojibake repair, image-tag stripping) is permitted and
   must happen inside `detect`.
3. **Cheap.** Substring and precompiled-regex tests only; a full detect sweep of
   all registered parsers must stay well under the cost of one parse. This is a
   hard requirement for the 3,506-document discovery run (DSC-2).
4. **It must not parse.** `detect` may not build a `Statement`, and `parse` may
   not re-derive detection independently — it calls the same `detect`.

`parse` contract is unchanged from today: return a `Statement`, or `None` if the
document turns out not to be parseable by this parser after all. §4.3 explains
why `None` must remain meaningful.

### 2.2 Score semantics

Scores are on a fixed, documented scale rather than being invented per parser:

| Band | Meaning | Who produces it |
|---|---|---|
| `0.0` | No evidence, or positively excluded | required marker absent, or `excluded_by` set |
| `0.0 < s < 0.5` | Weak evidence — **never claims on its own** | corroboration present but a required marker missing |
| `0.5` | Minimum claim: every required marker present | the common case |
| `0.5 < s < 1.0` | Claim plus corroboration | required markers plus optional ones |
| `1.0` | Exclusive structural sentinel | a marker that only this document class can contain |

Scores are **computed, not hand-assigned.** Each registration declares markers,
and the shared scorer turns them into a number:

```python
@dataclass(frozen=True)
class Marker:
    id: str
    test: Callable[[str], bool]
    kind: Literal["required", "corroborating", "exclusive", "excluding"]

def score(markers, text) -> Detection:
    if any(m.kind == "excluding" and m.test(text) for m in markers):   -> 0.0 + excluded_by
    if any(m.kind == "exclusive" and m.test(text) for m in markers):   -> 1.0
    required = [m for m in markers if m.kind == "required"]
    if not all(m.test(text) for m in required):
        return partial credit in (0, 0.5) proportional to corroborating hits
    corroborating hits h of n  ->  0.5 + 0.5 * (h / n)   (0.5 when n == 0)
```

**Why this exact formula:** today's guard is `all(required)`. Under this scorer
a parser reaches `>= CLAIM_THRESHOLD` **iff** its present-day guard passes, and
below it otherwise. Migration is therefore parity-preserving by construction,
not by hope — and the corpus parity test (§6) proves it document by document.
A disjunctive guard (`"BMO" or "BANK OF MONTREAL"`) becomes one required marker
whose `test` is the disjunction, not two markers; splitting it would change
semantics.

Scores are **not** probabilities and must not be compared across parsers as if
they were calibrated. They exist to (a) rank candidates, (b) make "this parser
nearly matched" observable in telemetry, and (c) give the ambiguity rule a
threshold. Calibration is out of scope (P2-9).

---

## 3. Registry data model

```python
@dataclass(frozen=True)
class Registration:
    id: str                                   # unique, stable, snake_case
    bank: str                                 # Statement.bank label
    markers: tuple[Marker, ...]
    parse: Callable[[str], Statement | None]
    band: int = 100                           # coarse priority band, see §3.1
    supersedes: frozenset[str] = frozenset()  # ids this one outranks outright
    formal_statement: bool = True             # see §7.1
    integrity_checks: tuple[IntegrityCheck, ...] = ()   # see §7.2
```

The registry itself is a module-level immutable sequence, populated by explicit
registration at import time and exposed only through accessors:

```python
def register(reg: Registration) -> Registration: ...   # raises on duplicate id
def registrations() -> tuple[Registration, ...]: ...   # in resolved order
def by_id(parser_id: str) -> Registration: ...
```

Registration happens in one place — `analysis/parser_registry_entries.py`, which
imports the 43 parser modules and registers them — so that import order cannot
influence dispatch order, and so `analysis/pipeline.py` imports exactly one
symbol (`resolve`) instead of 43 parse functions.

### 3.1 Ordering and tie-break rules

`registrations()` returns a **total order**, computed once and asserted by test:

1. `band` ascending. Three bands only, and their meanings are documented:
   `10` — a narrower document class that shadows a broader one (Chase export
   before Chase); `100` — normal; `900` — deliberately last-resort.
   Bands are not a place to hide precedence facts; use `supersedes` for those.
2. `id` ascending, as the final deterministic tie-break.

Note what is **not** in the sort key: score. Score ranks *candidates for a given
document* (§4); `band`/`id` order the registry itself. Keeping the two separate
is what makes "dispatch order is data with tests" (WAVE2_BRIEF R-3 acceptance)
true — the registry order is a pure function of the registration data and can be
asserted literally in a test, with no document involved.

`supersedes` encodes genuine precedence between two parsers that can both claim
the same document. It is a directed edge, checked for cycles at import. Today's
chain order encodes at least these facts, which become explicit edges:

| Edge | Why |
|---|---|
| `chase_export supersedes chase` | an export is a narrower class of the same source |
| `rbc_fr supersedes rbc` | language variant of the same bank |
| `td_can_native supersedes td_can_table` | layout variant of the same bank |

Everything else in today's ordering is, as far as the corpus can show, arbitrary
— and the parity test (§6) is what will tell us if that belief is wrong. **Any
ordering fact the parity test reveals must be recorded as a `supersedes` edge
with a comment naming the document that proved it, never as a band nudge.**

---

## 4. Resolution and ambiguity policy

### 4.1 Outcomes

```python
@dataclass(frozen=True)
class Dispatch:
    outcome: Literal["claimed", "ambiguous", "unclaimed"]
    registration: Registration | None          # claimed only
    detection: Detection | None                # claimed only
    candidates: tuple[tuple[str, float], ...]  # (id, score) >= threshold, sorted
    attempted: tuple[str, ...] = ()            # ids whose parse() returned None
```

### 4.2 The rule

1. Run `detect` for every registration. Collect `claimants` = those with
   `score >= CLAIM_THRESHOLD`.
2. Remove any claimant that is `supersedes`-dominated by another claimant.
3. If **zero** claimants remain → `unclaimed`.
4. If **one** remains → proceed to §4.3.
5. If **two or more** remain → `ambiguous`. **Never first-wins.** Ranking by
   score is deliberately *not* used to break this tie: two parsers each claiming
   the document with independent evidence is a fact about our registry that a
   human must resolve, and a wrong-parser claim that happens to reconcile is
   silent corruption of both a real result and the discovery statistics
   (WAVE2_BRIEF §0.3).

### 4.3 Parse fallthrough — the parity-critical detail

Today's chain does **not** dispatch on detection alone. A parser whose guard
passes can still return `None` further in (missing summary, no transactions
found, a period it cannot read) and the chain then tries the next parser. For
example `analysis/amex.py` passes its two-marker guard and then returns `None`
if any of four summary amounts is missing.

A registry that dispatched purely on the winning detection would change
behaviour on exactly those documents. Therefore:

> With one surviving claimant, call its `parse`. If it returns `None`, continue
> with the remaining registrations **in registry order** — the same set and the
> same order as today's chain — recording each `None` in `Dispatch.attempted`.
> Exhausting them yields `unclaimed`.

This preserves today's semantics exactly while making the fallthrough visible
instead of invisible. `attempted` is a first-class telemetry field (H-3): a
parser that detects and then repeatedly fails to parse is a defect signal, and
today we cannot see it at all.

Ambiguity is decided **before** any parse runs, so an ambiguous document never
gets silently rescued by whichever parser happens to succeed.

### 4.4 What the pipeline does with each outcome

| Outcome | `parse_mode="auto"` | `parse_mode="deterministic"` |
|---|---|---|
| `claimed` | unchanged from today | unchanged from today |
| `unclaimed` | LLM extraction, unchanged | `RuntimeError`, unchanged (`pipeline.py:418-419`) |
| `ambiguous` | **new:** no deterministic parse; LLM extraction path, plus integrity flag `parser_ambiguous` and a note naming the candidate ids; `assess_quality` forced to `needs_review` / `manual_review_required` | **new:** `AmbiguousParserError`, listing candidates |

The ambiguous case routes to review by the mechanism the platform already has
for "we do not trust this enough to approve" — `DocumentIntegrity.flags` plus
`Quality.corporate_use`. No new surfacing machinery, no new schema field.

Resolving a recurring ambiguity is a code change with a test: add a `supersedes`
edge, or tighten a marker. **Lowering a score to dodge an ambiguity is
forbidden** — it converts a visible conflict into an invisible one.

Expected ambiguity rate on the 109-document corpus: **zero**, and §6's test
asserts exactly that. On the 3,506-document discovery archive it is expected to
be non-zero and is one of the more interesting numbers DSC-2 will produce.

---

## 5. Migration plan for all 43 parsers

Five stages, each its own commit with full suite + corpus gate green. Corpus
proof is byte-identical throughout; no stage re-baselines anything.

**R-3.0 — record the baseline (no production code).**
Produce `tests/data/parser_expectations.json` from the *current* or-chain (§6.1)
and commit it. This must land before any dispatch code changes, or the baseline
is contaminated.

**R-3.1 — protocol, scorer, registry, no behaviour change.**
Add `analysis/parser_registry.py` (`Marker`, `Detection`, `Registration`,
`score`, `register`, `registrations`, `resolve`) and
`analysis/parser_registry_entries.py`. `analysis/pipeline.py` is untouched;
the registry is exercised only by tests. Detection markers are transcribed
**mechanically** from each parser's existing guard, one marker per conjunct.

**R-3.2 — parsers expose their detection once.**
In each `analysis/<bank>.py`, the guard body moves into a module-level
`detect(markdown) -> Detection` built from the module's markers, and the
`parse_*` entry point starts with `if not detect(markdown).claims: return None`.
The guard now exists in exactly one place per parser. Mechanical, per-parser,
one commit per batch of ~10 parsers, each batch gate-proven.

**R-3.3 — the three sub-dispatches become registrations.**
`chase_export`, `rbc_fr`, `td_can_native` are registered in their own right with
`supersedes` edges (§3.1); the nested `if ... is not None: return ...` blocks at
`chase.py:356`, `rbc.py:74`, `td_can.py:303` are removed. This is the only stage
that changes parser control flow and it gets its own gate run.

**R-3.4 — pipeline switches to the registry.**
`_deterministic_statement` (`pipeline.py:357-402`) is replaced by
`resolve(markdown)`; the 43 imports at `pipeline.py:18-58` collapse to one;
`model_used` derives from `dispatch.registration` instead of re-deriving a slug
from `stmt.bank` (`pipeline.py:415-416`) — with the existing string format
preserved verbatim, because the audit CSVs' `parser` column consumes it.
Ambiguity handling (§4.4) lands here.

**R-3.5 — orchestrator bank literals move out (§7).**

Adding parser #44 after this is: write the module, add one `Registration`, add
its conformance tests (R-4). Zero orchestrator edits — the acceptance criterion.

---

## 6. Corpus-wide parser-parity test

The single most important control in R-3. Requirement (WAVE2_BRIEF): *every one
of the 109 corpus PDFs must resolve to the same parser as today.*

### 6.1 Recording today's assignments

The committed audit CSVs already carry a `parser` column, but **it is not a
parser identity and cannot be the baseline**: it stores
`f"{bank_label}-deterministic"` derived from `Statement.bank`
(`pipeline.py:415-416`), which yields 44 distinct values over 109 rows and
splits `analysis/rbc.py` into two (`royal-bank-of-canada-deterministic`,
`banque-royale-du-canada-deterministic`) while merging nothing. Useful as a
cross-check, not as truth.

The baseline is recorded by `tools/record_parser_expectations.py`, run once at
stage R-3.0 against the unmodified or-chain:

* wraps all 43 `parse_*_statement` entry points with a recorder that notes every
  call and the id of the first one returning non-`None` (this also captures the
  fallthrough set of §4.3, which becomes an expectation too);
* iterates the **pinned manifest** — the 109 paths in the audit CSVs, the same
  set `corpus_gate.py` uses after H-0 — never an `rglob` of the corpus root,
  which now also contains the 3,506-document discovery archive;
* consumes the same committed OCR artifacts as the gate, so it is fully offline
  and deterministic;
* writes `tests/data/parser_expectations.json`: one row per document with
  `{path, sha256, parser_id, attempted_ids, ambiguous: false}`;
* asserts it produced exactly 109 rows and that a second run is byte-identical
  before writing. Re-running it later is an explicit, reviewed act — exactly the
  posture the audit CSVs already have.

`sha256` pins the row to the document bytes, so a corpus change cannot silently
re-point an expectation at a different file.

### 6.2 The tests

`tests/test_parser_parity.py`, marked `corpus` (offline, opt-in with the gate):

1. `test_every_corpus_document_resolves_to_the_recorded_parser` — for all 109,
   `resolve(markdown).registration.id == expected.parser_id`. Failure message
   names the document, the expected parser and the actual candidate list with
   scores.
2. `test_no_corpus_document_is_ambiguous` — `outcome != "ambiguous"` for all
   109. A new ambiguity on a *validated* document means the registry is wrong,
   not the document.
3. `test_parse_fallthrough_set_is_unchanged` — `Dispatch.attempted` matches the
   recorded `attempted_ids`. This is what would catch a §4.3 regression, which
   the parser-id assertion alone can miss.
4. `test_expectations_cover_the_pinned_manifest` — the JSON's 109 sha256 values
   equal the pinned manifest's, so the baseline cannot silently shrink.

Fast, always-on companions in `tests/test_parser_registry.py` (no corpus):

5. registry order is exactly the documented literal list (order is data);
6. duplicate `id` raises; `supersedes` cycles raise; every `supersedes` target
   exists;
7. synthetic two-claimant document → `ambiguous` with both ids listed, and no
   parse is attempted;
8. synthetic superseded pair → `claimed` by the superseding parser;
9. detect purity: calling `detect` twice returns equal `Detection`s and does not
   mutate its input;
10. every registration's id is referenced by at least one expectation row **or**
    is explicitly listed as corpus-unrepresented (wells, scotia, columbia,
    navigant, relay, first_farmers are the known-untested six from R-4) — so the
    gap is named rather than discovered later.

---

## 7. Moving the orchestrator's bank-name literals out (R-8's dispatch half)

### 7.1 The Chase-export sentinel

`Registration.formal_statement: bool = False` on the new `chase_export`
registration. `assess_quality` (`pipeline.py:150`) and
`assess_document_integrity` (`pipeline.py:273`) take the `Dispatch` they already
have in scope and ask `dispatch.registration.formal_statement` instead of
comparing `stmt.bank` to a literal. The LLM path has no registration; it
defaults to `True`, which is today's behaviour for every non-Chase-export
document.

**Behaviour delta to check:** today's test is on `stmt.bank`, so an LLM
extraction that happened to emit `bank="Chase Transaction Export"` would also
trip it. No corpus document does this (the one export row is
`chase-transaction-export-deterministic`), so the corpus proof is unaffected —
but this is a real, if narrow, semantic change and is called out here rather
than buried.

### 7.2 The BMO contradiction check

`_bmo_summary_contradictions` (`pipeline.py:211-270`) moves wholesale into
`analysis/bmo.py` as `summary_contradictions(markdown, stmt) -> list[str]`, with
its `(stmt.bank or "").upper() != "BMO"` guard **deleted** — the function only
runs when the BMO parser claimed the document, so the guard is redundant. The
BMO registration lists it in `integrity_checks`, and
`assess_document_integrity` iterates `dispatch.registration.integrity_checks`
instead of calling a BMO-named function. `pipeline.py`'s last bank literal, and
its `from .td_can import _parse_money` import (`pipeline.py:33`, used at `:234`)
both disappear; the R-2 back-compat alias in `analysis/td_can.py` is deleted in
the same commit.

**Behaviour delta to check:** same shape as §7.1 — today the check runs for any
statement whose `bank` is BMO, including an LLM-extracted one; afterwards only
when the BMO parser claimed. One corpus document is BMO
(`bmo-deterministic`, deterministic), so the corpus proof is unaffected. If
Ocean judges the LLM-path coverage to be load-bearing, the alternative is a
`integrity_checks` lookup by bank label for the LLM path, which keeps the
coverage but reintroduces a label dependency — flagged as an open question
(§9.2).

### 7.3 What stays

`normalize_statement` (`pipeline.py:71-97`) and `apply_statement_repairs`
(`pipeline.py:100-116`) are bank-agnostic and out of R-3 scope. The eleven
`repair_*` calls inside `apply_statement_repairs` are named per bank but live in
`analysis/bank_repairs.py` and the owning parser modules already — folding them
into `Registration.repairs` is the natural next step and is **explicitly not
proposed here**, to keep R-3 to one seam. Recommend it stay the named R-8
leftover.

---

## 8. Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | A parser claims another bank's document (the failure R-3 exists to prevent) | High | Ambiguity policy §4.2; corpus parity test §6.2/1-2; R-4 detection-negative tests immediately after |
| 2 | Fallthrough semantics silently change (§4.3) — parser detects, fails to parse, and the registry does not retry as today's chain does | **High — the likeliest way to break the corpus** | Explicit fallthrough rule; `attempted` recorded in the baseline and asserted (§6.2/3) |
| 3 | The mechanical guard→marker transcription (R-3.2) drops a normalization step (`.upper()`, `_IMG_RE`, mojibake) | High | Marker `test` callables carry the normalization; per-batch gate runs; detect/parse share one code path |
| 4 | Registry order differs from chain order in a way one corpus document depends on | Medium | Parity test names the document; fix is a `supersedes` edge with the document cited, never a band nudge (§3.1) |
| 5 | §7.1/§7.2 literal moves change integrity flags for LLM-path documents | Medium | Deltas stated explicitly; no corpus document affected; Ocean ruling requested (§9.2) |
| 6 | Import-time registration makes order depend on import sequence | Medium | Single registration module; order is a pure function of `(band, id)`; asserted literally (§6.2/5) |
| 7 | Detect sweep cost × 3,506 discovery documents | Medium | Substring/precompiled-regex only (§2.1/3); measure the full-registry sweep in R-3.1 and report the per-document figure |
| 8 | Import cycles: `pipeline` → registry entries → 43 parsers | Low | Entries module is a leaf; parsers never import the registry (R-3.2 keeps `Detection` construction in `parser_registry`, imported one way) |
| 9 | Ambiguity floods the discovery run and drowns real signals | Low-Medium | Ambiguity is a recorded outcome, not a failure; DSC-2 ranks ambiguous clusters like unknown-layout clusters |
| 10 | H-3 telemetry blocks on this seam (WAVE2_BRIEF §5) | Low | `Dispatch` is designed as H-3's data source: parser id, score, candidates, attempted — nothing further needed |

---

## 9. Open questions for Ocean

1. **Score scale.** Is `0.0-1.0` with `CLAIM_THRESHOLD = 0.5` and the
   required/corroborating formula (§2.2) the right contract, or would you prefer
   integer evidence counts with a documented minimum? The formula was chosen
   because it makes migration parity provable; any alternative needs the same
   property.
2. **§7.1 / §7.2 behaviour deltas.** Both literal moves narrow the check from
   "any statement with this bank label" to "this parser claimed the document".
   No corpus document is affected. Accept, or keep label-based coverage for the
   LLM path?
3. **Ambiguous in `auto` mode.** Proposal is: no deterministic parse, fall to
   LLM extraction, flag + force review. The alternative — fail closed with no
   statement at all — is more conservative but changes `auto` from
   "always returns something" to "can refuse". Which?
4. **`tests/data/parser_expectations.json` authority.** Proposal treats it like
   the audit CSVs: generated once, committed, and regenerating it is a
   deliberate reviewed act. Confirm, and confirm the recorder script may live at
   `tools/` (currently no such directory) rather than in `tests/`.
5. **R-8 scope.** §7.3 recommends leaving the eleven `repair_*` calls in
   `apply_statement_repairs` alone and keeping R-8 as a named leftover rather
   than stretching R-3. Agreed?
6. **Six corpus-unrepresented parsers** (wells, scotia, columbia, navigant,
   relay, first_farmers per WAVE2_BRIEF R-4). §6.2/10 names them in a test so
   the gap is explicit. Should R-3 land with them named-and-untested, or should
   R-4's synthetic fixtures for those six be pulled forward ahead of R-3.4?
