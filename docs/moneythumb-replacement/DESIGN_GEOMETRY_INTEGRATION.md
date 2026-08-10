# DESIGN — geometry integration for the residual class

PLATFORM-PROPOSALS, 2026-08-10. Branch `wave3-platform-proposals`.
Card: `docs/agent-handoffs/PLATFORM-PROPOSALS.md`, deliverable B.
**Status: DESIGN. No code was written. `analysis/`, `ocr/`, `webapp/` and
`discovery/` were opened read-only.** For the 3b-style review this will get.

Input evidence: `W3_3C_STRUCTURER.md` (esp. §5.1, §7.4, §8.3),
`W3_TRACKA_LOG.md` §T6, §5.7, §W7, §3.7. Line anchors are against `bb7d644`.

**Standing constraint, from Gustavo, honoured throughout:** the existing
reconciliation and grounding requirements must **not** be weakened to recover
these documents. Every route below either keeps the fail-closed gate exactly as
it is or is rejected for touching it.

---

## 1. Where the platform stands today

| Fact | Anchor |
|---|---|
| A word-geometry producer exists and works | `analysis/structurer/geometry.py:135` `geometry_from_pdf(pdf_bytes) -> DocumentGeometry \| None` |
| It groups words into visual lines from the page's own type size, not a constant | `geometry.py:95-132`, tolerance `median(word.height) * 0.6` |
| The pipeline already accepts it | `analysis/pipeline.py:312` `document_geometry: object \| None = None` |
| …and forwards it to exactly one consumer | `analysis/pipeline.py:344` `structure_unclaimed(markdown, geometry=document_geometry)` |
| That consumer only runs on the **unclaimed** branch | `analysis/pipeline.py:343-347` — `deterministic_stmt is None and dispatch.outcome == "unclaimed"` |
| …and only when an env opt-in is set | `analysis/structurer/core.py:63-64`, `GENERIC_STRUCTURER_ENABLED` |
| **Nothing in production computes geometry.** The only caller in the tree is the measurement tool | `tools/measure_structurer.py:117` |
| Geometry wiring was explicitly deferred to a HARBOR integration card | `W3_3C_STRUCTURER.md` §8.3 |

So the seam exists, end to end, and is dark. This design says what to plug into
it, what must change so plugging it in is *correct* rather than merely wired,
and — the larger part — argues that most of the residual should not go through
that seam at all.

---

## 2. The residual, re-partitioned

The card names the residual as **19 + 4**: TD T-F4 10 · RBC F11 6 · PNC P-F5 3
(= 19, the figure `W3_TRACKA_LOG.md` §3.7 item 1 arrives at), plus Wells W-F7 4
held aside as "arguably a different fix class".

**Reading the four cells' evidence, that partition splits in the wrong place.**
The line is not TD/RBC/PNC vs Wells. It is between documents whose **rows are
intact and whose column identity was discarded**, and documents whose **rows do
not exist in the text stream at all**.

### Class G1 — column identity discarded; rows intact (14 documents)

The text layer emits one record per printed row, in reading order. What is lost
is *which money column* a cell was printed in. Recovering it needs x-positions
on an existing line, not line reconstruction.

| Bank | Family | Docs | Evidence |
|---|---|---|---|
| TD Canada (native) | T-F4 | **10** | `W3_TRACKA_LOG.md` §T3: `ocr/native_text.py::_native_pages` "reads each printed row as one PyMuPDF block and joins its spans with single spaces… The amount survives; **which of the two adjacent money columns it was printed in does not.**" §T6.1: read-only word geometry places every amount inside `CHEQUE/DEBIT x∈[212,284]` or `DEPOSIT/CREDIT x∈[309,389]`, and on the very group that defeats the balance arithmetic the split is unambiguous — geometry "would close **all 24** underdetermined groups". |
| Wells Fargo | W-F7 | **4** | `W3_TRACKA_LOG.md` §W7.2: `ocr/native_text.py::_wells_rows` bins lines as `round(y0 / 3.0) * 3.0` (`native_text.py:329`) so two printed rows can merge, and reads columns from fixed x ranges (`native_text.py:366-368`: credit `395–452`, debit `452–520`, balance `>=520`) so "a layout printed at another scale drops its amount cells outside every band". |

§W7.2 names the shared cause exactly: "**geometry read as constants rather than
as the page's own column positions**". TD has no bands at all; Wells has the
wrong ones. Same defect class, same file, opposite symptom.

**TD belongs here, not with RBC/PNC**, and §T6.1 says so itself: "`ocr/
native_text.py` already recovers geometry this way for two other banks
(`parse_native_wells_fargo`, `_navy_transaction_rows`), so a geometry-preserving
TD native extractor is **precedented in that same file**."

### Class G2 — grid order destroyed; rows must be rebuilt (9 documents)

The text stream is not in grid order, so no rule applied to it can recover
rows. The row *association* has to be rebuilt from word boxes.

| Bank | Family | Docs | Evidence |
|---|---|---|---|
| RBC | F11 | **6** | `W3_TRACKA_LOG.md` §5.7 item 3: "balances open physical lines, amounts are printed between the description lines of a different row, and some cells are missing from the text stream entirely — one document's stated 129 rows yield at most **118 recoverable cells**. No text-layer rule can reorder what the text layer has already reordered." |
| PNC | P-F5 | **3** | `W3_TRACKA_LOG.md` §3.4 P-F5: "the Date column is emitted as its own block, away from the rows: `04 04 04` on one line, `/08 /10 /10` on the next". §3.7 item 1: "This is RBC F11 in a second bank." |

Note RBC's "missing from the text stream entirely" — 129 stated rows, ≤118
recoverable cells. **Geometry may not be sufficient for all six.** A cell absent
from the PDF's text objects has no box either. This is the one place the
residual may not close at all, and the design must not promise otherwise.

### Why the split matters

| | G1 (14) | G2 (9) |
|---|---|---|
| Primitive needed | x-band assignment on an existing line | word-box → visual-line reconstruction (`geometry.py:95-132`) |
| Where the fix goes | `ocr/native_text.py`, per bank | a geometry input reaching a **claiming parser** |
| New architecture required | **none** — precedented twice in that file | **yes** — this is the actual card |
| Blast radius | that bank's markdown; global OCR cache version | that bank's parser; analysis cache key |
| Self-check available after the fix | TD: the balance solver (§T6.1 "should stay either way"). Wells: the printed `Totals` line (§W7.4) | RBC: the printed credit/debit count and total (§5.5). PNC: the `Description Items Amount` subtotal table (§3.2) |

**Every one of the four banks has an independent in-document oracle already
built and already measured.** That is what makes this residual safe to attack:
success is provable from the documents themselves, with no expectation file and
no audited truth set (§6).

---

## 3. The routing question, argued

The card asks: structurer rung opt-in, or parser-level geometry assist?

### 3.1 Routing claimed documents to the structurer — REJECTED

All 23 residual documents are **claimed** by a parser and withheld by the gate.
Sending them to the structurer would require one of:

- **weakening the claim rule** so a claiming parser can be overridden. This
  contradicts `W3_3C_STRUCTURER.md` §5 ruling 2 verbatim ("A parser that claimed
  a document on proven issuer evidence keeps it"), and it is a direct hit on
  Gustavo's constraint: the claim rule is part of the fail-closed gate.
- **a "withheld → try the structurer" retry branch.** This is worse than it
  looks. It makes the structurer a second opinion whose selection criterion is
  *that the first opinion failed a financial check* — i.e. the platform would
  choose between two readings by which one passes the gate. That is precisely
  the failure mode `analysis/parser_registry.py:518-521` was designed to
  prevent one level up ("the ambiguity decision — deliberately **before** any
  parse runs, so an ambiguous document can never be rescued by whichever parser
  happens to succeed").

And it would not work anyway. `W3_3C_STRUCTURER.md` §4 measures the structurer
refusing 103 of 109 corpus documents, with the dominant refusal
`ledger_incomplete` (53) — "the structurer now reads the document's shape
correctly and is **missing rows**" (§4). Missing rows is exactly the state the
23 residual documents are in. The structurer would refuse them, correctly, and
the platform would have taken an architectural risk for zero documents.

### 3.2 Parser-level geometry assist — RECOMMENDED for G2

The parser keeps the claim, keeps every existing check, and gains one optional
input. Nothing about the gate moves.

Three properties make it provably additive:

1. **Detection never sees geometry.** `analysis/parser_registry.py:515-536`
   scores registrations on markdown alone. If geometry is threaded only into
   `parse`, the *claim set* is identical with and without it. Geometry can
   change how a claimed document is read; it can never change which parser
   claims it. **This must be an explicit rule of the design, and a test.**
2. **A parser that ignores geometry is byte-identical.** The markdown it
   receives is unchanged. 40+ parsers need no edit.
3. **Per-parser blast radius.** RBC and PNC opt in; every other bank's output is
   provably untouched, by the same side-by-side old-module/new-module method
   every Track A cell used (§5.6, §B6, §3.6).

### 3.3 `ocr/native_text.py` per-bank fix — RECOMMENDED for G1

No new architecture, no `analysis/` change, no geometry plumbing. Two existing
precedents in the same file (§T6.1). The cost is real but bounded and is named
in §5.3.

### 3.4 The route explicitly not taken: a geometry-preserving native rung for everyone

Making `_native_pages` (`ocr/native_text.py:9`) emit grid-ordered text for every
document would fix G1 and G2 at their source and is architecturally the
cleanest answer. It is rejected for this wave on blast radius: it changes the
markdown of **every native-text document in the archive** — the input to all 40+
parsers and every fixture — forces `OCR_STAGE_VERSION` (`webapp/
artifact_cache.py:199`, currently `2`), and re-baselines the entire corpus. It
is a wave of its own, and it should be considered only after G1's two per-bank
fixes have shown what a geometry-preserving extractor actually changes.
Recorded so it is a decision, not an omission.

---

## 4. The wiring design (needed for G2, and for the structurer opt-in)

### 4.1 Producer and its cost

`geometry_from_pdf(pdf_bytes)` (`geometry.py:135-179`). One `fitz.open` plus one
`page.get_text("words")` per page; returns `None` when there are no words —
"the honest answer for a scanned page" (`geometry.py:136-142`) — and never
raises (`:143-176`, every step guarded).

PyMuPDF is already a hard dependency of the native rung and the pages are
already opened once per document there (`ocr/native_text.py:11-16`, `:162-166`,
`:229-233`, `:273-277`). The marginal cost is a second open plus one extra text
extraction mode per page. It should be **computed once per document** and passed
down, not recomputed per consumer.

### 4.2 Touchpoints — file-level, diff shapes only

| # | File:line | Change |
|---|---|---|
| 1 | `discovery/runner.py:344-347` | `process()` already holds `raw = path.read_bytes()`. Compute geometry once here (guarded by the same rung logic that decided native vs OCR) and hand it to `_analyse`. |
| 2 | `discovery/runner.py:300-305` | `_analyse(self, markdown, collector)` gains one keyword; the `analyze_markdown(...)` call at `:303` gains `document_geometry=`. |
| 3 | `webapp/worker.py:219-267` | `run_job` holds `pdf_bytes` (`:221`) and calls `_analyze_doc` at `:267`. Pass the geometry (or the bytes) through. |
| 4 | `webapp/worker.py:45-70` | `_analyze_doc` gains one parameter; the `analyze_markdown(...)` call at `:70` gains `document_geometry=`. |
| 5 | `batch.py:246-248` | Third emitter. `_read_source(path)` (`batch.py:59-60`) returns `(markdown, doc, profile, byte_size)` and **not** the bytes, so it needs to return them — or the caller re-reads the path. Note `batch.py` accepts `.md` inputs, where there are no PDF bytes at all and geometry is correctly `None`. |
| 6 | **`webapp/artifact_cache.py:297-315` `analysis_settings_key`** | **Mandatory. See §4.3.** |
| 7 | `analysis/parser_registry.py:302`, `:515`, `:548` | G2 only: `Registration` gains an optional geometry-aware parse callable; `resolve(markdown)` gains `*, geometry=None`; `registration.parse(markdown)` at `:548` passes it to registrations that declare it. Detection (`:536`) is untouched — §3.2 property 1. |
| 8 | `analysis/pipeline.py:319` | G2 only: `dispatch = resolve(markdown)` → `resolve(markdown, geometry=document_geometry)`. One line. |
| 9 | `discovery/runner.py` `DocumentRow` / `report.py` | Reporting, exactly as specified in `W3_3C_STRUCTURER.md` §5.1 — unchanged by this design and still correct. |

Touchpoints 7 and 8 are protected-module changes and must be pinned as written
diffs and approved before implementation, per the W3-1b idiom
(`WAVE2_EXECUTION_LOG.md`, 2026-08-07).

### 4.3 The cache-key correctness requirement — the load-bearing part

`analysis_settings_key` (`webapp/artifact_cache.py:297-315`) fingerprints
`stage_version`, `parse_mode`, `model`, `escalation_model`,
`withholding_denominator_mode`. The analysis cache is keyed on **the markdown
plus that fingerprint** (`:149` docstring, `cached_analysis(markdown, …)`).

Geometry is a *new analysis input that is not in the markdown*. Wire it without
touching the key and the cache serves a geometry-informed answer to a
geometry-free run, or the reverse — silently. That violates the module's own
stated invariant: "**Over-partitioning is safe, under-partitioning is not**"
(`webapp/artifact_cache.py:92-93`) and "the cache degrades to 'recompute', never
to 'wrong answer'" (`:123-124`).

**Requirement: `analysis_settings_key` must include whether geometry was
supplied** (a boolean is sufficient — the geometry is a deterministic function
of the PDF bytes, and the bytes are already the OCR key), **and
`ANALYSIS_STAGE_VERSION` must bump** in the same commit, per the D-3 rule at
`:99-100`.

`W3_3C_STRUCTURER.md` §5.1 specifies the discovery reporting fields and does not
mention this. **It is a gap in that spec, and this design closes it.**

### 4.4 A pre-existing defect this analysis found, disclosed

The same hole is **already open** for the structurer opt-in.
`analysis/structurer/core.py:63-64` reads `GENERIC_STRUCTURER_ENABLED` from the
environment at call time, and that environment variable appears nowhere in
`analysis_settings_key`. So today, on a warm cache:

> `GENERIC_STRUCTURER_ENABLED=1 python -m discovery --digital` — the exact
> command `W3_3C_STRUCTURER.md` §5.1 gives for the measurement run — would
> return the **pre-opt-in cached answers** for every document already analysed,
> and report the rung as having recovered nothing.

The rung is currently unreachable from production, so nothing is wrong today
and no published value is affected. But it means **the first measured
structurer run is invalid unless the cache is partitioned or bypassed first.**

Fix options, in order of preference:

1. add the opt-in (and geometry availability) to `analysis_settings_key` and
   bump `ANALYSIS_STAGE_VERSION` — one place, permanent, and it is what the
   module's own doctrine at `:92-93` prescribes;
2. move the opt-in from an environment variable to `analysis/config.py`
   `Settings`, which `W3_3C_STRUCTURER.md` §6 already offers as "a two-line
   follow-up" — settings are the natural home for a knob the key must see;
3. run the measurement with `cache=None` (`artifact_cache.py:153-155`, "passing
   `cache=None` disables caching entirely"). Correct, but it re-analyses the
   archive and does not fix the production path.

**Recommended: 1 and 2 together, before any structurer measurement run.**

### 4.5 Where word boxes come from on each path

| Intake path | Source | Cost | Status |
|---|---|---|---|
| Native-text PDF | `geometry_from_pdf` → PyMuPDF `get_text("words")` (`geometry.py:157`) | one extra open + one extraction per page; no vendor cost | **available now** |
| Local Tesseract | none today. `geometry_from_pdf` returns `None` for a scanned page by design (`geometry.py:136-142`); `W3_3C_STRUCTURER.md` §7.4: "Scanned documents get nothing extra." | Tesseract can emit boxes (`image_to_data`), so it is technically reachable | **not recommended in this card — see the contract hazard below** |
| Visual rung (W3-5) | model-produced text; no boxes | — | open interface question, `W3_3C_STRUCTURER.md` §7.4 |

**Contract hazard if an OCR path is ever added.** `Word` is documented as "one
word as printed, with its box in **PDF points** (origin top-left)"
(`geometry.py:29`). Tesseract boxes are in *image pixels* at whatever DPI the
page was rendered. Feeding them in would satisfy the type and violate the
contract, and every downstream x-band comparison would be wrong by a scale
factor — silently, because a band test is a comparison of two floats. If OCR
geometry is ever wired, `DocumentGeometry` must first grow an explicit unit or
scale field. Recorded as a **precondition**, not a nice-to-have.

All 23 residual documents are native-text (`W3_TRACKA_LOG.md` §T1 "all digital,
all native-text"; §5.5 native rung; §3.1 "16 resolve through the native rung"),
so none of this blocks the work — but PNC's fourth withheld document, P-F6, is
the scanned one whose cheque row Tesseract never recovered (§3.4 P-F6), and it
is **not** recoverable by geometry. It stays withheld and should not be counted
in any success target.

---

## 5. Sequencing

Recommended order, smallest-risk-first, each step leaving the next better
informed:

**S1 — Wells W-F7 (4 documents), `ocr/native_text.py`.** The defect is three
constants in existing code (`:307`, `:329`, `:366-368`), the fix is to derive
them from the page's own column positions, and the oracle is already built and
measured — the printed per-account `Totals` line (§W7.4), which "is what this
cell's instrument used to prove the residual honest". Smallest surface,
strongest proof, and it turns the file's fixed-band idiom into a
page-derived one that S2 then reuses.

**S2 — TD T-F4 (10 documents), `ocr/native_text.py`.** Largest single
population. §T6.1 has already located the bands on a real page
(`x∈[212,284]` / `x∈[309,389]`) and confirmed geometry closes **all 24**
underdetermined groups. Critically: "**the balance solver should stay either
way** — it is what makes the result self-checking, and it is the only path that
survives an OCR'd TD statement, where geometry is unavailable." Geometry becomes
the primary reading and the solver becomes its independent check — a
strengthening, not a replacement.

**S3 — the wiring card (§4).** `document_geometry` reaches production;
`analysis_settings_key` is fixed (§4.3); §4.4 is closed; `discovery/` reporting
lands per `W3_3C_STRUCTURER.md` §5.1. **Zero documents recovered by this step,
and that is expected** — it is infrastructure, and it should be reviewed and
merged as infrastructure rather than judged on coverage.

**S4 — the parser-level geometry contract + RBC F11 (6) and PNC P-F5 (3).** The
protected-module diffs at touchpoints 7 and 8, plus a geometry reader in each
parser. Last, because it is the only step that needs new architecture, and by
then two working per-bank geometry readers exist to design it against.

**Why W-F7 is not "a different fix class to be done separately", as the card
suggests, but the *first* step:** §2 shows it is the same class as TD, in the
same file, and it is the smaller and better-oracled of the two. Doing it first
buys the page-derived-column primitive that S2 needs anyway.

### 5.1 Cost that must be stated: `OCR_STAGE_VERSION` is global

S1 and S2 change markdown, so per the D-3 rule (`artifact_cache.py:99-100`)
`OCR_STAGE_VERSION` (`:199`, currently `2`) must bump. It is **one global
integer**: a Wells-only change invalidates the OCR artifact cache for the entire
archive. Vendor cost stays `$0.00` (native rung, no model calls —
`DISCOVERY_COMBINED_REPORT.md` §1) but the next full discovery run pays the
wall-clock again (~90 min for 3,506 documents, ibid.).

Consequence for sequencing: **S1 and S2 should merge together, or at least be
run against the archive together**, so the archive re-reads once rather than
twice. If Ocean wants them as separate reviewable merges, that is fine — it is
the *measurement runs* that should be batched.

---

## 6. Measurement plan

### 6.1 The named populations are the unit of proof

The frozen 3,506-document baseline (`DISCOVERY_COMBINED_REPORT.md` §1) and the
named residuals are the before-state. Every step proves itself over its own
named set, not over an aggregate:

| Step | Population | Before | Target |
|---|---|---|---|
| S1 | the 4 Wells W-F7 documents (§W5) | 0 validated / 4 withheld, diagnostics `detail_coverage` ×3 + `summary_field_missing` ×1 | each document either validates against the printed per-account `Totals` line, or stays withheld with an accurate diagnosis |
| S2 | the 10 TD T-F4 documents (§T5) | 0 / 10 | each validates against the bank's stated credit/debit counts **and** totals, with the balance solver agreeing; §T6.1 predicts all 24 underdetermined groups close |
| S3 | — | — | **zero document movement**, asserted. Plus: the structurer measurement run (`W3_3C_STRUCTURER.md` §5.1) becomes valid for the first time (§4.4) |
| S4 | RBC 6 + PNC 3 | 0 / 9 | each validates against RBC's printed counts+totals (§5.5 instrument) / PNC's `Description Items Amount` subtotal table (§3.2), or stays withheld honestly. **RBC's ≤118-of-129-cells finding (§5.7 item 3) means some may not be recoverable at all** |

Maximum realistic recovery: **23 documents**, 0.7% of the frozen baseline. This
work is not justified by volume and should not be sold that way. It is
justified because each of the 23 is a *named, root-caused, evidence-backed*
defect in how the platform reads a page, and because the primitive that closes
them (page-derived columns rather than constants) is the same primitive every
future two-money-column layout will need.

### 6.2 Success is proven from the documents, not from a truth set

Every cell already built its instrument and it is reusable verbatim: TD §T2
(per-page `Credits <count> <total>` / `Debits <count> <total>` blocks and the
running BALANCE per date group), Wells §W7.4 (the per-account `Totals` line,
"the strongest oracle in this layout"), RBC §5.5 (printed credit count and
total, debit count and total, ledger identity, printed balance chain), PNC §3.2
(the `Description Items Amount` table, whose subtotals reproduce the Balance
Summary on 45/45 documents).

That is the acceptance standard, and it is the one Track A used throughout:
"Nothing was padded to get there" (§5.5, §B5, §3.6) means every recovered
document reproduces the bank's own printed evidence independently.

### 6.3 Non-regression, per step

- old and new modules loaded side by side in one process over identical input,
  every field of the serialised statement compared — the method of §5.6, §B6,
  §W6, §3.6;
- `python corpus_gate.py` → **106 PASS / 3 WITHHELD**, byte-identical. The
  corpus contains 4 wells-fargo, 6 td-canada-trust, 4+1 RBC and 5 pnc documents
  (`docs/adb-audit-results.csv`), so **every step of S1–S4 touches pinned
  corpus documents** and none may move without ceremony (`W3_TRACKA_LOG.md`
  §2.2);
- the default suite **and** `pytest -m corpus`, per the standing merge criterion
  (`WAVE2_EXECUTION_LOG.md`, 2026-08-07);
- **S3/S4 specific:** an assertion that `resolve()` returns the identical
  `Dispatch.candidates` with and without geometry, on a real document — §3.2
  property 1 made mechanical;
- **S3 specific:** an assertion that two `analyze_markdown` runs over identical
  markdown, one with geometry and one without, produce **different cache keys**
  — §4.3 made mechanical, in the same idiom as the W3-5 cache-partition proofs
  (`WAVE2_EXECUTION_LOG.md`, 2026-08-07: "cache partitions proven with zero D-3
  change").

---

## 7. Open questions for the 3b-style review

1. **Is the G1/G2 re-partition accepted?** It moves TD from the "needs the
   geometry architecture" bucket (19) into the "per-bank `ocr/` fix" bucket, and
   moves Wells from "different fix class" into the *first* step. It is the
   single biggest claim in this document, sourced to §T6.1 + §W7.2, and
   everything in §5 depends on it.
2. **`OCR_STAGE_VERSION` is one global integer (§5.1).** Is a per-bank markdown
   change allowed to invalidate the whole archive's OCR cache, or should the
   stage version be partitioned by intake path first? A structural question
   about `webapp/artifact_cache.py`, raised because S1 is the first change to
   pay it.
3. **Where does the geometry-aware parse contract live?** Options: widen
   `Registration.parse` to accept an optional keyword; add a second optional
   callable `parse_with_geometry`; or pass geometry via a context object.
   Recommendation deferred to S4's own design — but the *rule* (geometry never
   reaches detection, §3.2) should be ruled on now, because it constrains all
   three.
4. **Does `DocumentGeometry` get a unit/scale field now or when OCR geometry is
   first wired (§4.5)?** Adding it now is cheap and prevents a silent
   correctness bug; adding it later is a change to a frozen dataclass. Weak
   preference for now.
5. **RBC's missing cells (§2, G2).** One document's 129 stated rows yield ≤118
   recoverable cells. If a cell is absent from the text objects it has no box
   either. Should S4's target be "close 9" or "close as many of 9 as the text
   objects permit, and prove the rest unrecoverable"? The second is the honest
   framing and should be agreed **before** S4 starts, so the residual-of-the-
   residual is not read as a failure.
6. **Does anything else want geometry once it is in scope?** Two unread
   printed oracles are queued and both are blocked on it: PNC's `Daily Balance`
   series is "emitted column-major on the documents that would most benefit
   from it" (§3.7 item 2) and BofA's `Daily ledger balances` is "the strongest
   case yet" for a first-class oracle (§B7.2). If the `stated_daily_balances`
   card is coming, S3 is its dependency too — and §3.7 item 2 exists precisely
   to warn that "on PNC it is a geometry problem, not a parsing one."
7. **Should S3 land even if S4 is not scheduled?** Argument for: it closes the
   §4.4 defect, which blocks the structurer measurement Ocean needs in order to
   rule on flipping the opt-in at all. Argument against: infrastructure with no
   consumer. Recommendation: **land it**, because the structurer measurement is
   its consumer.
