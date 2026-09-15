# Agent Handoff — P23-FALLOUT (Phase 2.3 cell B: the baseline stage-by-stage fallout with the existing structurer in research mode, per geometry source; the false-accept instrument on the control sample; "Paddle helped"; the truth table v2; adjudication slice 2)

**Launch base:** the `train13` tip Ocean names at launch, AFTER cells W, E and X have composed (their
partitions, metrics and agreement columns are your inputs). Worktree `.claude/worktrees/mt23-fallout`,
branch `wave23-fallout`.

Read `docs/agent-handoffs/BATCH9-RULES.md`, `PHASE2-RULES.md`, `docs/moneythumb-replacement/PHASE2_RULINGS.md`
(the anti-optimizer rule — no candidate is chosen by reconciliation; R3 — an adjudicator labels, never a
tool; R11 — any exit from validated is a regression; R13 — the declined branch is 2.4's, NOT yours; the
STOP conditions), the umbrella `docs/agent-handoffs/PHASE2-3-WAVE.md` (D8, D9, cases 9, 10, 13, the
exclusions), the plan §G.2.3 cell B and the adjudication slice 2, §H.3, §H.6, §I.6 (the L3 sub-classes
B1–B8), `docs/moneythumb-replacement/PHASE2_ARCHITECTURE_PLAN.md`, then the Phase 2.2 instruments as composed:
the K, T and H sections `# §P22IDENTITY*`, `# §P22TRUTHTABLE*`, `# §P22HOLDOUT*` in `W3_TRACKA_LOG.md` (grep the
headings), `analysis/config.py` (`Settings.reconstruction_mode`, read from `RECONSTRUCTION_MODE`),
`analysis/structurer/` (`structurer_enabled`, `geometry.py::geometry_from_evidence`, the existing generic
rung — READ-ONLY; you change nothing in it), `discovery/runner.py` (the research mode; the geometry seam
`_geometry_for` passing `document_geometry` and `evidence_sha256` when the mode is not `off`; the funnel
columns `stage_*`; `_project_taxonomy`), `telemetry/unresolved_taxonomy.py` (L2 E0–E5, L3 B1–B8 — populated
from row facts only), `tools/truth_report.py`, `tools/holdout/` and `tools/adjudicate.py` (the sealed store,
the packets, the queues), `docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt`, `layout/document_class.py`,
cell W's partitions (`paddle-v5-prod`; V's two if composed) and the P23-WAVE / P23-EGATE / P23-AGREE W3 sections.
Ocean reviews and composes; you never merge or push. **Hygiene card: `newly validated = 0` OFFICIAL —
research-validated shas are NAMED, never counted; the structurer runs ONLY in research partitions with
`RECONSTRUCTION_MODE=research` in that run's environment, never in a run of record; no candidate selected by
reconciliation; no customer page leaves the machine (every read is a cache hit on W's partitions); no cost.**

# Why
2.4 will build the LayoutModel from the B-class fallout; 2.5 will admit Paddle where "Paddle helped" is
measured; the truth table v2 is what both are judged against. None exists. This cell runs the existing
structurer as the BASELINE reconstruction over the unresolved corpus, per geometry source, and records
where each document stops — and on the control sample it tests whether the Paddle path can produce a
candidate that disagrees with a validated payload, which is the one false-accept instrument the program has
before the holdout.

# What you deliver (ruled — do not re-decide)
1. **The research analysis runs** — the research mode with `RECONSTRUCTION_MODE=research` in the run's
   environment (T's seam; K's setting), over U755 in W's `paddle-v5-prod` partition (and V's partitions where
   composed), TWICE per document: geometry from NATIVE evidence and geometry from PADDLE evidence, as two
   research partitions of the ANALYSIS artifacts (the analysis key already carries the evidence sha and the
   mode — verify; if a second analysis partition needs a research id of its own, report to Ocean before
   adding one). Every read is a cache hit on the OCR partition (no page sent anywhere — assert zero Paddle
   requests). The structurer's code is untouched.
2. **The funnel per source** (`tools/fallout_report.py`, read-only over the run rows): E (attempted →
   evidence → E-class from cell E) → G (geometry built: pages, lines, words, frame, rotation) → L (furniture
   removed → ≥ 1 table region → column model → records → summary anchors → account partition; a B1–B8 code
   from the structurer's own refusal reasons into L3 — read from row facts only) → C (a candidate produced,
   with sign tier and grounding coverage) → V (the validator's verdict and the W3-2 class) → Δ (research-
   validated · review · refused · failed), per source (native | paddle | tesseract-text), as counts and as
   a per-sha private table; every research-validated sha NAMED in its own row and never counted; every
   refusal coded.
3. **"Paddle helped"** per document: the stage where the Paddle-geometry funnel went further than the
   native-geometry funnel (or the Tesseract-text funnel for scans), e.g. `native: B2; paddle: validated`;
   aggregated by census family and by modality; "no added value" where both reach the same stage.
4. **The false-accept instrument on CTRL** (D8, BLIND until comparison): the Paddle-geometry research run
   over CTRL produces candidates; `tools/false_accept_probe.py` records each candidate's key fields
   (opening, closing, transaction count, Σ debits, Σ credits) BEFORE it reads the validated payload from the
   run of record, then compares; any disagreement is a FALSE-ACCEPT CANDIDATE — a row in adjudication slice 2,
   never a label, never a fix. The instrument's blindness is structural (two passes, the second reading a
   file the first wrote) and pinned by a test.
5. **The truth table v2** — `tools/truth_report.py` extended: the classifier (`classify_document`) run on
   PADDLE evidence for every scanned/mixed document of U755 and CTRL (read-only from the partition), beside
   its Tesseract-text verdict; the disjoint sums; adjudicated verdicts (from the sealed store, tools-side
   only) beside classifier-proposed; every verdict CHANGE named by count and queued; the CCL forms printed
   beside the raw denominator, never instead of it.
6. **Adjudication slice 2** (`tools/adjudicate.py` queue — cell H's instrument, ownership widened for the
   queue builder only): every document whose classifier verdict changed between Tesseract text and Paddle
   evidence, every `KIND_UNCERTAIN`, every false-accept candidate, and a random 50 of the rest (a recorded
   seed); packets under the private on-machine directory outside OneDrive; the queue digest in your W3;
   nothing adjudicated by you.
7. **No hardcodes; no routing:** no code path chooses a source by its verdict; nothing reads `Δ` but the
   report; the OQ2 scans cover the tools.

# Files you own (exact; nothing else)
`tools/fallout_report.py` (new) · `tools/false_accept_probe.py` (new) · `tools/truth_report.py` (the v2
extension) · `tools/adjudicate.py` (the slice-2 queue builder ONLY) · `discovery/runner.py` (ONLY if the
research analysis partition needs a per-source id — report first) · `tests/test_fallout_report.py`,
`tests/test_false_accept_probe.py` (new) · `tests/test_truth_report.py`, `tests/test_adjudication.py` (APPEND) ·
`tests/test_no_statement_hardcodes.py` (the roots append) · your W3 section. `analysis/**` (the structurer
included), `layout/**`, `ocr/**`, `evidence/**`, `telemetry/**`, `webapp/**`, `tools/paddle_wave.py` are NOT
yours.

# Mutation table (run every mutant, name every killer)
M1 a research-validated sha counted into the headline → T's headline-exclusion test + your named-row test ·
M2 the probe reading the validated payload before recording the candidate → the blindness test (the order of
the two files' timestamps and a fake payload that would be preferred) · M3 a false-accept candidate written
as a verdict → the queue-row test · M4 the structurer run with `RECONSTRUCTION_MODE` unset → the mode-only
test (zero geometry passed) · M5 a Paddle request during the analysis runs → the zero-request test on the
fake worker · M6 a source chosen by its verdict (planted in a scratch copy) → the AST guard · M7 "Paddle
helped" reported where both sources reach the same stage → the no-added-value test · M8 a B-code inferred
rather than read from a row fact → the taxonomy drift guard (T's) · M9 the CCL printed without the raw
denominator → T's two-denominator test · M10 the slice-2 queue including a holdout sha → H's refusal.

# Proof floor
Full default suite; the 5 canonical guards; the 7 canonical conformance files; `python corpus_gate.py`
GREEN 105/3/1; `pytest -m corpus`; the research analysis runs (both sources; logs with `EXIT=`; zero Paddle
requests asserted); `cohort_replay --expect-identical` over the `--parser` chunks at base and closure if
`discovery/runner.py` changes at all; the fallout, "Paddle helped", the probe on CTRL, the truth table v2
and the slice-2 queue produced from committed instruments; privacy scan 0 over added lines; the message
scanner over every report you write (`--shas` = the populations) → 0; message scan 0 over commits. Heavy
proofs one at a time under `discovery_reports/train13-logs/HARNESS.lock` (mkdir-only; own-holder release;
Git bash `rmdir`).

# Report contract (final message to Ocean AND your W3 section `# §P23FALLOUT — …`)
population (U755 and CTRL per source; the partitions) · root cause · solution · newly validated 0 OFFICIAL
(research-validated shas NAMED per source) · ladder movement 0 · preserved all (the run of record untouched) ·
regressions 0 · the fallout funnel per source (counts) · "Paddle helped" by family and modality · the
false-accept candidates (count; queued) · the truth table v2 (disjoint sums; adjudicated beside proposed; the
verdict changes by count) · slice 2 (count; digest) · escalation evidence (no source chosen by a verdict; no
request) · commits · proof exits · privacy count · risks last (what 2.4 must not read as more than a baseline).

# Exclusions
No structurer change (2.4) · no routing (2.5) · no admission · no adjudication (R3) · no Paddle call · no
declined-branch run (R13 is 2.4's) · no cost.

---

# Bounded orchestration clarification — 2026-09-15

Root-authorized clarification after independent source/design review. This does not launch B. Its launch
base remains the actual train tip after W, E and X compose. The original card's
financial, routing, privacy, truth and regression constraints remain binding.

## Why a tools-only entry point is needed

Source inspection shows that the normal research CLI can compute an OCR cache
miss, and its geometry seam automatically prefers extractor evidence. The
current structurer wrapper also discards its diagnostic result. Those interfaces
cannot by themselves produce the card's cache-only, separately observed native
and Paddle baseline. A dedicated tools entry point can use the existing reader,
cache-key and analysis APIs while preserving the protected production source.

## Added ownership

Allow `tools/fallout_run.py` and `tests/test_fallout_run.py` as B's cache-only
analysis/observation instrument and its tests. `tools/fallout_report.py` remains
a read-only reporter. Permit edits only to
`tests/test_extraction_quality_admission.py`'s `ALLOWED_NAMERS` and directly
related report-reader pins, adding only `tools/fallout_report.py` and/or
`tools/fallout_run.py` where each actually consumes E columns. Preserve full-tree
discovery, existence checks and protected-package bans. X's decision-package
guard already permits tools; no X guard change or protected reader is authorized.
The original card's hardcode-root append remains required. If a committed
mutation driver is needed, its only added owned name is
`tools/p23fallout_mutation_table.py`, with the same report-only boundary.
Permit that exact mutation-driver filename in E's `ALLOWED_NAMERS` only if its
proof strings or reporting actually name E columns. Omit unused entries;
full-tree scanning, existence checks and protected-package bans stay intact.

No edit to the structurer, validator, router, OCR engine, canonical evidence or
cache-key implementation is authorized by this clarification. B uses their
existing public behavior. Any actual identity collision or unavailable interface
must be reported before widening that scope.

## Inputs, identity and offline execution

- Open existing OCR indexes read-only and use one explicitly bound historical
  key per reading. Reuse the exact-tuple selector, canonical evidence and envelope
  checks, resolved-path containment, and missing-versus-conflicting distinctions
  established by E/X. Never enter a compute-on-OCR-miss function.
- Supply each source's own stored text/page partition and associated canonical
  geometry. The source is selected explicitly before analysis, not by agreement,
  quality scores, reconciliation or any final outcome. Preserve the original
  native versus Tesseract-text distinction where the baseline has no native
  geometry; label the actual reading instead of silently substituting one.
  A native sidecar in a Paddle artifact does not authorize pairing its boxes
  with Paddle text. Resolve the matching stored native text/page partition
  through the exact historical native source and verify its sidecar hash and
  canonical document/extractor identity. If a coherent bundle is unavailable,
  report that requested reading unavailable; do not borrow another source's
  text, reconstruct substitute text or reopen the PDF to complete it.
- Use the existing evidence-bound analysis input hash and research-mode settings
  key. Write new analyses only into a dedicated B research sink. Input caches,
  their indexes, retained images and W's run records stay immutable.
  Resolve output paths before creating them and reject aliasing/overlap with
  every input cache, index, raster directory and protected run output. Record
  before/after integrity checks on the exact input/index manifests.
- Require the research environment and consistent explicit analysis settings.
  Use the real document analysis, serialization and diagnostic classification;
  a historical reduced structurer verifier cannot replace the validator.
  Pass `parse_mode="deterministic"` to both analysis and key derivation and keep
  hosted/Paddle opt-in literals absent. Off/missing mode gives no geometry and
  no forced generic invocation; it cannot produce an accepted research run.
- Enforce and measure zero OCR/hosted/network attempts at their boundaries,
  including calls whose exceptions would otherwise be swallowed. A missing or
  malformed input stays unavailable or refuses according to the existing reader
  contract; it cannot trigger another extraction.
  Any counted attempt invalidates B measurement completion, even when caught
  by another layer. Keep per-boundary counters distinct from request totals.
- A cache hit without a matching observation sidecar provides no new stage trace.
  Keep that diagnostic unavailable; do not infer it from a candidate or verdict,
  or rerun reconstruction merely to make the report look complete.

## Observe the actual existing structurer call

In a dedicated serial B process, a narrowly scoped observer may temporarily wrap
the `analysis.structurer.core.structure_document` global used by the unchanged
`structure_unclaimed` function. This observes calls the real pipeline makes.
It must not invoke the structurer separately, admit a new route, or make a call
when the existing pipeline does not make one.

The wrapper calls the original exactly once with the same arguments, returns
the same result object, and rethrows the same original exception. It captures
only an immutable whitelist of diagnostic facts with document/source/call
ordinals. It never changes the candidate or records an exception message.
The whitelist contains copied, bounded scalar/count facts, never live outcomes,
statements, raw text, free-form grounding notes or generic `asdict`/`repr` output.
No caller-provided callback, baseline lookup, routing predicate or financial
comparison runs in this hot path.

Recording failures must not escape into the production wrapper, where they
would otherwise turn a valid candidate into `None`. Contain ordinary observer
errors separately, preserve the analysis behavior, restore the original binding
in `finally`, and then refuse or explicitly mark the observation incomplete.
Do not report success from an incomplete observer. Assert original binding and
exact restoration, reject concurrent/nested observer installation, and keep
request/observation counts distinct from file aliases or analysis cache hits.
Preserve cancellation, `SystemExit` and other `BaseException` control flow;
interrupted runs remain incomplete. Verify restoration on supported Python
exits; process termination cannot execute `finally` and cannot close a run.
An original analysis exception must not be replaced by a completion error.

Inside the tools compute closure, finish actual analysis, restore and verify the
observer, and check observation completeness and zero-attempt counters before
returning a dictionary to `cached_analysis`. A failed measurement must not be
cached or published as a completed observed analysis. Preserve the financial
result/exception; fail only the outer B measurement. A reusable sidecar binds
the exact analysis identity, selected reading/source artifact, source commit,
and observation schema/mapping version. If persistence fails after a valid
financial artifact is stored, retain it and mark observation incomplete. A
later hit without that complete sidecar stays observation-unavailable; no
deletion or diagnostic rerun is justified.

Proofs must distinguish transparent forwarding from a successful-looking
replacement: argument identity, one call, same result object, unchanged result
contents, same original exception, recorder failure, restoration on every exit,
research/off behavior, and claimed/declined/ambiguous/parser-exception routes.
The published document/account payload must be identical with the observer on
and off on synthetic cases. No duplicate reconstruction is a live proof shortcut.

## Facts and the limits of the current baseline

The returned `StructureOutcome` exposes raw reason, rows, row-line count, sign
sources, chaining, period provenance and grounding. Record actual returned facts
and the exception class where applicable. An absent call is not a structurer
failure; an exception is not an invented detailed refusal reason.

The current baseline has no complete public furniture-removal, table-region,
column-model, cross-page-continuity or account-partition trace. Those stage cells
remain explicitly unmeasured. A B-class mapping may include only reviewed
implications of actual raw reasons/facts. Preserve the raw reason alongside it;
do not derive a structural cause from reconciliation or missing candidate output.
Future LayoutModel taxonomy declarations do not establish that those stages ran.

The bounded baseline mappings permitted by this clarification are:

| Actual observed fact | B projection | Limit |
|---|---|---|
| `ungrounded` with a present grounding result whose `ok` is false | `B7_grounding_failed` | This actual grounding refusal only |
| `no_signable_rows` with zero assembled rows | `B8_sign_undeterminable` | No invented per-row sign diagnosis |
| `no_dated_rows` with zero assembled rows | `B3_records_unassembled` | No inference about tables, columns or furniture |

Other raw reasons remain visible and unmapped. In particular `no_printed_period`
does not establish that all summary anchors are absent, `ledger_incomplete`
does not establish broken cross-page continuity, and a period contradiction
does not establish ambiguous account partitioning. No production taxonomy is
changed. Recheck these implications against the frozen composed launch source.

The “Paddle helped” report compares supported observed stage facts for the same
document across requested sources. B-code numbers are not an ordinal progress
score. Missing sources, unavailable observations, unchanged reached stages and
financial refusals remain distinct. The report never selects a production source.

## Blind control comparison and truth boundaries

Freeze the CTRL candidate record in a first process before a separate comparison
process gains access to validated baseline payloads. The first pass receives only
the population and permitted OCR input descriptors; it must not open financial
baseline artifacts or read sealed truth. Record candidate identity, account
shape, required key fields and the frozen file digest. Reject tampering and
incomplete records rather than silently comparing zeros.

Only the second process opens historical baseline analyses using their exact
run-of-record identity. Preserve document/account shape and compare debit and
credit sums separately. Disagreement produces an adjudication candidate, never
a truth label, a repair or another candidate-generation attempt.

Truth-table/report and adjudication-queue work retain R3 and the existing sealed
store firewall. The implementation path sees no sealed labels. Report proposed
versus adjudicated statuses explicitly, use the existing raw/CCL denominator
rules, and keep research-validated identities outside headline coverage.

## Proof and release

Retain all original B card proofs and mutations, with additional discriminating
mutants for source/key substitution, OCR miss computation, observer suppression
or repeated invocation, argument/result mutation, recorder-error leakage,
restoration failure, fabricated stage facts, and pre-freeze baseline access.
Each new selection or observation rule has a named behavioral killer.

Use the shared root lock/floor/cap for heavy tests and all corpus runs. Record
actual input immutability and zero-request counts, run the full B floor, review
independently, preserve failed attempts and scanner counts, and compose only
after the cell's gate is green. Implementation begins only at the composed launch tip named by root.

## Independent design review

The E implementer independently inspected the core call binding, pipeline eligibility,
cache-write boundary, native evidence restoration, E/X reader guards and all three
raw-reason mappings. Root incorporated the review's five bounded tightenings and
the exact conditional mutation-driver allowance. The reviewer wrote no B code.
Source basis: train `f8d130f`, E `f8c9257`, X `f1276b5`; verify the seams again at
the actual composed launch commit. This is design approval, not an executed B proof.
The private preparation and review are under `discovery_reports/train13-logs/p23fallout-prep/`.
