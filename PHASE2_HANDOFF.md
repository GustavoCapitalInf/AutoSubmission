# PHASE2_HANDOFF — read this first (written 2026-08-31 for a brand-new session with ZERO prior context)

Everything below is durable repository state. Trust `docs/moneythumb-replacement/PROJECT_STATUS.md`
over this file if they ever disagree, and the repository over both. The verbatim blocks in this
file are mechanical extracts of the committed sources named above each block — the sources remain
authoritative.

# Current official state

| fact | value |
|---|---|
| Batch 9 | **OFFICIAL AND FROZEN** |
| Frozen validated baseline | **2,625 / 3,380 (77.66%)** |
| Validated regressions | **0** (the comparison's 3 downward movers are PNC's fail-closed movement, named per-SHA in advance: `1F31588B36B2E4AF`, `5684857C24B79344`, `BE703D525955253C`, withheld→failed) |
| tag | **`batch9-final`** = commit `819d97d` (annotated; on origin) |
| ANALYSIS_STAGE_VERSION | **17** (`webapp/artifact_cache.py:436`, bumped IN the composing commit `7b25d70`) |
| OCR_STAGE_VERSION | 4 (unchanged in batch 9) |
| registry | **84** parsers |
| suite | **7,815 passed** (44 skipped, 35 deselected) at the composed tree `7b25d70` |
| run of record | `discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a` (tree `ff35b3d`), compared against batch 8's `discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d` with the EMPTY quarantine (`tools/train/quarantine_retired_empty.shas`) and `--fail-on-regression`; report `train8_compare.md` inside the run directory |
| headline | 2,596 → 2,625: **+29** = +6 CP-DECLINES, +13 PNC-LAYOUTS, +2 WH-ROW-CAPTURE, +8 L1-S4; 32 improved / 3 regressed (named) / 3,345 unchanged |
| remote CI | GREEN on the train (run 33419094234 at `b5d8f00`) and on main (run 33438656619 at `c90154a`) |
| durable batch-9 record | `docs/moneythumb-replacement/BATCH9_TRANSITION.md` — §7 execution log (newest at the bottom), §8 Gustavo's rulings 1–16 |

# What Batch 9 delivered

- **deterministic-v1** — the frozen deterministic parsing/validation baseline (84 registered parsers, the corpus gate, the guards, the conformance set, the frozen-corpus regime).
- **multi-account-v1** — the L-1 independent-account architecture, five reviewed stages, each adversarially reviewed, closed, re-reviewed and composed: S1 `DocumentReport`/`analyze_document`/RULE S (composed `fea0bd2`); S2 evidence-based sibling omission on the document object under ruling Q10 (`e5b0342`; 15 protected carriers pinned on BOTH legs — `tests/test_l1s2_omission_ruling.py`, `tests/test_l1s2_protected_carriers.py`, `tests/test_l1s2_document_outcome.py` incl. the fold tripwire); S3 every reader and seam taught the document shape, serialized shape decided by ACCOUNT COUNT alone (`eeaf566`); the Q3 corroboration probe (`a46603f`, N=6 confirmed independently); S4 the first multi-account publisher — guardian_cu roll-up template, +8 documents / 12 accounts, the seven-condition Q3 omission class, printed-designation-only internal transfers, account-based package membership (`7b25d70`).
- **final Batch 9 attribution** — the +29 proven twice (whole-archive replay AND sweep at base and tip, differenced per SHA; the cold run reproduced the composed claim exactly).
- **frozen regression doctrine** — `tools/cohort_replay.py` (exit 2 on validated regression; `--expect-identical` exit 3 on drift), the cold-run + `tools/train8_compare.py` comparison with `--fail-on-regression`, and the named-in-advance rule for any deliberate downward movement.

# Phase 2 status

| item | state |
|---|---|
| OCR-LEGACY-AUDIT | **COMPLETE + adversarially reviewed twice.** Review `CONFIRMED WITH FINDINGS` (1 BLOCK / 5 MAJOR / 5 MINOR) → all eleven closed by the cell (each independently reproduced before acceptance) → re-review **`CONFIRMED — READY FOR GUSTAVO`** with one new non-blocking MINOR-6. |
| Branch | `wave10-ocraudit`, tip `4af079a`, **merged to `main`** at `09e6b75` (docs + W3 `§OCRAUDIT` + the read-only `tools/ocr_legacy_census.py`; no production change anywhere in Phase 2 task 1). |
| Deliverables | `docs/moneythumb-replacement/OCR_LEGACY_AUDIT.md` (the audit; §6 = the open questions), `docs/moneythumb-replacement/reviews/PHASE2_OCRAUDIT_REVIEW.md` (review + closure re-review), W3 `§OCRAUDIT` in `docs/moneythumb-replacement/W3_TRACKA_LOG.md`. |
| Accepted architecture plan | **`docs/moneythumb-replacement/PHASE2_ARCHITECTURE_PLAN.md`** — **STATUS: ACCEPTED ARCHITECTURE PLAN**. Read this before any Phase 2 implementation. **IMPLEMENTATION: NOT STARTED.** Does **not** resolve OQ1–OQ11. |
| Phase 2 implementation | **NOT STARTED. Nothing is carded. Nothing may be carded until Gustavo rules (see "Exact next action").** |

# Governing OCR audit findings (summary — the verbatim findings are embedded below)

- **The visual (Unlimited-OCR) rung has NEVER produced a single artifact**: `visual_rung = not_attempted` on 3,506/3,506 rows of the run of record; one OCR settings key in the cold cache (`allow_visual_ocr=False`); `source_path` native 3,297 / local_tesseract 179 / none 30 / **visual 0**; fifth witness `cache_visual = bypass` 3,506/3,506. All 2,625 validated documents rest on native text + Tesseract. `discovery/runner.py:438-670` already implements the enable-path (recovery, upgrade, disjoint cache partition, the SAME validator, fail-closed on endpoint death) and has run on zero documents — **Phase 2 is audit-and-enable, not build**.
- **Legacy components classified — 47 rows**: active 27 · reusable 10 · obsolete 4 · duplicate 1 · **unsafe 4** · unknown 0 · PaddleOCR 1. Reachability computed by transitive import walk from the 8 production entry points, not guessed.
- **The value-rewrite PAIR (the BLOCK-level hazard)**: `ocr/ocr_client.py` `collapse_repeated_amounts` (`:63-82`; its `\s+` separator crosses NEWLINES — three money tokens on consecutive lines with one value repeated collapse to one, and `[a,a,a,b,c]` on five lines returns `[a]`: distinct adjacent amounts are DELETED) **and** `fix_amount_column_bleed` (`:129-171`, `_AMOUNT_BLEED_RE` at `:126`) which rewrites INSIDE `<td>` cells (a cell with two fused money values has the leading amount moved into the description and the trailing one promoted). Their scopes are complementary — one outside table cells, one inside — so neither is made safe by relocating it into the other's territory. They destroy/rewrite ledger rows BEFORE the deterministic validator can see them. Two further `postprocess` members are declared UNPROVEN; a per-function rewrite census of all NINE `postprocess` members (`ocr/ocr_client.py:409-416`; the count is nine, not six — re-review MINOR-6) is an owed Phase-2 deliverable.
- **Corrected residue / census measurements** (on the batch-9 run of record `91f5179a`; the audit first mis-measured on the batch-8 run — corrected in closure, every table now names its run): insufficiency triggers already implemented and recorded — R (`deferred_visual_ocr`, offline rungs produced no text) = **13** documents; U (a Tesseract read no parser claimed) = **123**; R∪U = **136 / 3,506 (<4%)**, overlap 0; **validated ∩ (R∪U) = 0** (non-escalation is a measurement, not an argument); Tesseract-fed split 36 validated / 15 withheld / 5 review / 123 failed. A validator VERDICT is never a trigger.
- **Unlimited OCR status**: a 485-line client (`ocr/ocr_client.py`) + a 259-line local server (`local_ocr_server.py`) + the `--scanned-visual` mode exist and have never been measured; the **$0 / no-paid-vendor invariant is enforced by nothing** (`ocr/config.py:26-42`: `OCR_BASE_URL` is a plain env read; FOUR entry points default `allow_visual_ocr=True` — `parse.py:30`, `batch.py:73`, `coverage_audit.py:178`, `sweep_ocr.py:52`).
- **PaddleOCR status**: absent as code (0 importable hits) — but an **Approved 192-line design spec exists**: `docs/superpowers/specs/2026-07-21-paddleocr-bank-statement-parser-design.md` (PP-OCR with bbox row/column reconstruction — exactly the `document_geometry` filling §5.5 needs), plus a Nanonets VLM spec. Design-layer legacy to reuse.
- **The OCR_MODEL issue (content injection, not just egress)**: the OCR seam is THREE values, not two — `to_markdown()` writes a `model:` header stamped from the `OCR_MODEL` env (`ocr/pipeline.py:149`); `SOURCE_COMMENT_RE` is MULTILINE, not DOTALL, so **a newline in `OCR_MODEL` injects arbitrary text — including a money token — into `admissible_text`** (reproduced end-to-end). The guard that currently saves it: `admissible_text` / `SOURCE_COMMENT_RE`, pinned by `tests/test_filename_boundary.py`. Any new extractor's model token requires a closed character class in the same commit.
- **Other majors/minors** (full verbatim text below): `tools/cohort_replay.py:119-129` takes `rows[0]` with no ORDER BY / settings filter (safe only while no input holds a second OCR artifact — the first OCR-fed document creates one; `telemetry/stated_counts.py::CachedArtifacts` already implements the fix but carries a **visual-last partition ordering** = a silent unratified extractor preference, Risk 7/OQ10); a fabricated user-facing **"OCR confidence"** percentage (`webapp/static/app.js:594-601,1159` — hard-coded 98/94/80/72 re-encoding the validator's verdict, Risk 8/OQ9); there is **NO confidence plumbing anywhere** in the Python path — an extractor has no channel to argue for its own output; `webapp/app.py` rasterizes archive pages and serves them over HTTP (`:1996`, `:2234`); `embed_image_regions` (`ocr/ocr_client.py:344-374`) inlines document PIXELS as base64 where token-matching privacy scanners structurally cannot see them.
- **Carried from batch 9**: the corroborated Q3 omission class passed 6/6 ONLY on native-pdf-text documents — it must be re-measured on OCR'd input (the six guardian_cu documents as seed; `tools/q3_corroboration_probe.py` as the oracle) before any OCR-fed document relies on it (audit §5.8).


# Non-negotiable doctrine

- The frozen **2,625 validated are the regression floor** — every one is protected; any validated → anything is a regression that blocks composition unless per-SHA evidence proves the prior validation wrong, and then only by an explicit ruling.
- **A gain never cancels a regression** ("+10 / −2 = NOT ACCEPTABLE").
- **OCR is extraction only** — Unlimited OCR and PaddleOCR may never bypass or weaken: reconciliation, ledger identity, transaction coverage, account boundaries, page completeness, statement period, explicit currency evidence, ADB, integrity checks, multi-account independent validation (ruling §8.12).
- **Only the SAME deterministic validator grants `validated`** — never an extractor, never a confidence score, never a model.
- **Never rewrite source financial values to force reconciliation** (the repair doctrine; the value-rewrite pair is unsafe precisely because it does this pre-validator).
- **One account → one ADB. No blended cross-account ADB** (package: `cross_account_averages_refused`; membership iff the account's OWN outcome is `validated`).
- **Explicit currency evidence** outranks defaults; jurisdiction defaults are not absence rules.
- **Fail closed** — ambiguity refuses; a parser never invents.
- **No statement-specific hardcoding** (guard: `tests/test_no_statement_hardcodes.py`; whether it extends into `ocr/` is OQ2 — unruled).

# Planned Phase 2 architecture — AUDITED/DECIDED vs PROPOSED

**DECIDED by ruling (§8.12, binding):** Unlimited OCR + PaddleOCR as extractors only, behind the flow
`native deterministic → validates → done; insufficient extraction → extractor → canonical statement/accounts → the SAME deterministic validator → validated/refuse`. Zero recurring paid inference stays the default; paid OCR only for residue.

**AUDITED (measured facts, reviewed twice):** the enable-path already exists (`discovery/runner.py:438-670`); the insufficiency triggers R and U are already implemented and recorded in the run (13 + 123 = 136/3,506, <4%, both extractors local and unmetered); the cache/stage-version/provenance apparatus exists (one OCR settings key today; disjoint cache partitions); a validator verdict is not a trigger anywhere.

**ACCEPTED ARCHITECTURE (docs only, 2026-09-01; implementation NOT STARTED):** `docs/moneythumb-replacement/PHASE2_ARCHITECTURE_PLAN.md`. Read that file before any Phase 2 implementation. It does **not** resolve OQ1–OQ11.

**PROPOSED (in the audit §5 — NOT ruled, NOT implemented; awaits OQ1–OQ11):** `OCR_STAGE_VERSION` 4→5 with the pinned test (`tests/test_artifact_cache.py:854`) in the same commit; an `extractor` field plus tool/model versions in the settings key; per-page `page_extractor` provenance beside `page_integrity`; the closed vocabularies (`SOURCE_PATHS`, `FREE_MODELS`) extended — noting `source_path_for`'s fallthrough is `"visual"`, so a forgotten branch silently mis-attributes; quarantining the `postprocess` chain (OQ1 option (c)) with per-function re-admission as the nine-member rewrite census clears each; the endpoint allowlist for the $0 policy (OQ3); the Q3-class re-measurement plan (§5.8).

# Exact next action

**STOP. Do not implement Phase 2 yet.**

Gustavo is intentionally testing genuinely unseen statements against `batch9-final` before allowing
any code changes.

When Gustavo returns: **first** review the unseen-statement holdout results; **then** resolve
OQ1–OQ11 (below — OQ1 gates any OCR-fed validation; OQ2 and OQ3 gate any Phase-2 implementation
card); **then** cut the first Phase-2 implementation card (it must carry the nine-member rewrite
census, MINOR-6's scope fix, and the Q3 re-measurement plan).

Also open for Gustavo, independent of Phase 2 (verbatim backlog below): CONS-HARDCODE, MINOR-7
(single-account package path), PAGECOV-IMAGE-SHEET's pinned-surface ceremony, RAISE-PRIVACY-6.

# Resume instructions for a fresh agent

1. Read `PHASE2_HANDOFF.md` (this file).
2. Read `docs/moneythumb-replacement/PHASE2_ARCHITECTURE_PLAN.md` — the **accepted architecture plan** to read before any Phase 2 implementation (`STATUS: ACCEPTED ARCHITECTURE PLAN`; `IMPLEMENTATION: NOT STARTED`; does not resolve OQ1–OQ11).
3. Read `docs/moneythumb-replacement/OCR_LEGACY_AUDIT.md` (the audit; §6 = the open questions).
4. Read `docs/moneythumb-replacement/PROJECT_STATUS.md` and `docs/moneythumb-replacement/PHASE2_STATE.md` (the session-memory snapshot committed at handoff).
5. Verify the baseline: `git rev-parse batch9-final` → `819d97d…`; `git log --oneline -1 origin/main`; `python corpus_gate.py` GREEN (105 PASS / 3 WITHHELD / 1 REFUSED); the guards (`tests/test_no_statement_hardcodes.py` + the canonical set) green.
6. **Do not modify code until Gustavo explicitly authorizes Phase 2 implementation.** The operating rules live in `docs/agent-handoffs/BATCH9-RULES.md` (choreography, proof floors, lessons — they carry forward to Phase 2).

Key SHAs a fresh session may need: freeze commit `819d97d` (= tag `batch9-final`); composed batch-9 code tree `7b25d70`; cold-run tree `ff35b3d`; audit branch tip `4af079a`; audit merge into main `09e6b75`; batch-8 baseline run `cda8882d`; L-1 compositions `fea0bd2` / `e5b0342` / `eeaf566` / `a46603f`.

---

# Open rulings — OQ1–OQ11, VERBATIM

*(Mechanical extract of `docs/moneythumb-replacement/OCR_LEGACY_AUDIT.md` §6 at the merged tip.
Gating map: **OQ1 gates any OCR-fed validation**; **OQ2 and OQ3 gate any Phase-2 implementation
card**; OQ4–OQ11 shape the design and can be ruled with or after the card. The reviewer's
adjudication of OQ1 — option (c) is the only fail-closed-consistent recommendation — is in the
review extract further below.)*

## 6. Open questions for Gustavo

1. **THE VALUE-REWRITING PAIR (F-1 and F-11) — how should the OCR cleanup chain be resolved?**
   *Re-posed after adversarial review; the earlier version of this question asked only about F-1 and
   recommended confining it to `<td>` cells, which is unsafe because F-11 already lives there.*

   Two functions in `ocr_client.postprocess` provably write values rather than reading them:
   `collapse_repeated_amounts` (`:63-82`), which deletes every amount in an adjacent run of bare
   money tokens where one value repeats three or more times — including distinct amounts it never
   saw repeat; and `fix_amount_column_bleed` (`:129-171`), which moves the leading money value of a
   two-money Amount **cell** into the description and promotes the trailing one. Their scopes are
   complementary — one outside table cells, one inside — so neither can be made safe by relocating
   it into the other's territory. Both were written for real Unlimited-OCR degeneracies; neither has
   ever run on a real page. The options:

   * **(a) Remove both.** Degenerate pages then fail or land as truncation-flagged failures, which
     is the fail-closed direction. Costs whatever recall the two repairs would genuinely have won —
     an amount nobody has measured, because the rung has never run.
   * **(b) Scope both behind a per-extractor flag**, off by default, with a committed fixture per
     transformation proving on SYNTHETIC input exactly what each function does and does not change,
     and a page that either function touched carrying an explicit flag so it can never be silently
     adopted. This is the option that keeps the repairs available without letting them act
     unmeasured.
   * **(c) Quarantine the whole `postprocess` chain for Phase 2** — the visual rung emits raw model
     output, no cleanup runs, and the chain is re-admitted function by function only as the rewrite
     census in §5.7 clears each one. The most conservative option, and the one that makes the
     census's completion the gate rather than a promise.

   The audit recommends **(c) as the Phase-2 default with (b) as the exit path**: quarantine now,
   re-admit each function on the evidence of its own fixture. It no longer recommends any option
   that treats `<td>` cells as a safe harbour. **No OCR-fed document may be validated until this
   pair is ruled**, and the per-function rewrite census of all six chain members (§5.7) is the
   deliverable that makes the ruling actionable.
2. **Does the no-statement-hardcodes guard extend to `ocr/`?** F-3 is issuer-specific behaviour
   (a named issuer, a masked rectangle, five tuned render variants) in the intake layer, where
   `tests/test_no_statement_hardcodes.py` does not reach. Declare it as permitted intake furniture,
   or bring `ocr/` into scope?
3. **The `$0` guarantee (F-4): enforce it in code?** An `OCR_BASE_URL` allowlist would make the
   invariant that `ocr/availability.py:5-6` asserts actually true. It would also make a deliberate
   paid experiment require an explicit, recorded opt-in. Ruling wanted before the rung is enabled.
4. **Trigger T (truncation-flagged Tesseract reads):** admit it as a third escalation trigger, or
   keep truncation surface-only? It is the only trigger that would grow the residue beyond the
   measured 136.
5. **PaddleOCR's role:** first-choice free extractor for the residue (before Unlimited-OCR, since it
   needs no GPU), or a second opinion only where Unlimited-OCR's read goes unclaimed? The two orders
   have very different cost and very different provenance shapes.
6. **The RunPod half of `README.md`** documents a rented, per-hour, remote GPU. Delete it as a
   pre-deterministic remnant, or keep it as a documented escape hatch?
7. **Delete or keep the four legacy scripts** (#31–#34)? They are unreferenced, they predate the
   deterministic shift, and two of them can reach the OCR endpoint with default flags.
8. **F-9's fix is a prerequisite, not a nice-to-have** — confirm that `tools/cohort_replay.py` may be
   modified in Phase 2 despite being a batch-9 instrument, since the frozen baseline's replays would
   be unaffected (one artifact per input today) but every future one depends on it. The fix is now an
   *adoption* of `CachedArtifacts`'s existing ordered selection (#46), not new design.
9. **The webapp's fabricated `"OCR confidence"`** (`webapp/static/app.js:594-601`, rendered at
   `:1159`) is a hard-coded re-encoding of the validator's `quality` verdict under an OCR label.
   Rename it (it is a *validation* confidence), derive it from something real, or remove it — but
   before a second extractor lands behind the label, because at that point the number starts telling
   the operator something false about which read they are looking at.
10. **Ratify (or replace) `_ocr_keys`'s ordering.** `telemetry/stated_counts.py:864-868` already
    ranks the cache partitions — two offline first, the visual partition last — so an observer facing
    a document with both silently prefers the OFFLINE read. Phase 2 would inherit that ranking by
    omission, and `cohort_replay` is about to adopt the same list. Is "prefer the offline read" the
    policy, or should the preference be the read the run of record actually used, recorded per run?
11. **The "Approved" PaddleOCR design spec** (`docs/superpowers/specs/2026-07-21-…`) predates the
    deterministic shift and designs a standalone parser that does its own row/column reconstruction
    and its own JSON — i.e. an extractor that is also a validator. Phase 2's ruling is the opposite
    (extractors only, into the unchanged deterministic validator). Should that spec be marked
    superseded, or does its bbox reconstruction get inherited as the filling for `document_geometry`
    (#38)? The same question applies to the Nanonets VLM spec beside it.

---

---

# The eleven adversarial-review findings + MINOR-6 and the verdicts, VERBATIM

*(Mechanical extract of `docs/moneythumb-replacement/reviews/PHASE2_OCRAUDIT_REVIEW.md`:
§2 Findings — BLOCK-1 and MAJOR-1..5 — followed by §3 Minor findings — MINOR-1..5 — then the
re-review's MINOR-6 and final verdict. Every finding was closed at `9b7efb6` and confirmed at
`4af079a`; severities and file/function references are as the reviewer wrote them.)*

## 2. Findings

### BLOCK-1 — F-1 is not the only value rewrite, and the audit's recommended fix moves the collapse *into* the second one

`ocr/ocr_client.py:129-171`, `fix_amount_column_bleed`, with `_AMOUNT_BLEED_RE` at `:126` =
`^(.+?)\s+(-?\$?[\d,]+\.\d{2})$`. The "prefix" group is `(.+?)` — **anything, a money token
included**. Reproduced on synthetic input at this tree:

```
in : <td>Date</td><td>Description</td><td>Amount</td> | <td>01/02</td><td>ACH DEBIT</td><td>1,000.00 234.56</td>
out: <td>Date</td><td>Description</td><td>Amount</td> | <td>01/02</td><td>ACH DEBIT 1,000.00</td><td>234.56</td>
```

An Amount cell the model rendered as two fused money values — the exact fusion class the three
sibling repair functions exist to handle — has its **leading amount moved into the description and
its trailing amount promoted to the transaction's amount**. The parser that reads that table now
reads `234.56` where the page said `1,000.00`. By the audit's own standard ("an extractor that
rewrites a source value to a different value is not a repair, it is the thing the repair doctrine
forbids arriving one layer upstream of the parser"), this is the same class of defect as F-1, and it
reaches reconciliation, ledger identity, transaction coverage and ADB by exactly the same route.

Three consequences:

1. **§5.7's summary is false.** *"All ten share exactly one exposure … because it is the only place
   in the OCR path where a value is rewritten rather than read. That is the whole safety delta, and
   it is one function."* There are at least two functions, and the safety delta is not one function.
   The same sentence appears in W3 §OCRAUDIT and must be corrected in both.
2. **Open Question 1's recommendation is unsafe as written.** The audit recommends option (b) —
   restrict `collapse_repeated_amounts` to run "only *inside* `<td>` cells, where the docstring's
   safety argument is actually true". `fix_amount_column_bleed` operates **only** inside `<td>`
   cells. Table cells are not a safe harbour; they are where the other rewrite already lives.
   Gustavo cannot be asked to rule on option (b) on the current text.
3. **The cleanup chain needs a rewrite census, not a spot fix.** `postprocess` (`:409-416`) is six
   functions deep and at least two of them write values. `split_fused_header_row` (`:174`) and
   `repair_fused_amount_table` (`:273`) restructure rows and re-emit cells; I could not construct a
   value-losing input for `repair_fused_amount_table` (its `_FUSED_HEADER_CELL_RE` guard at `:269` is
   tight), but its per-row loop collapses every `len(cells) >= 3` row whose last cell is money into
   three columns by joining `cells[1:-1]` into the description — a shape that on a
   debit/credit/balance table would fold two money columns into the description. That is unproven and
   I do not claim it; it is exactly what a per-function rewrite census must settle.

**Required before Gustavo reads the audit:** correct §5.7's summary and F-1's "single change"
framing, add `fix_amount_column_bleed` as a finding in its own right, and re-pose Open Question 1
with the `<td>` option's premise removed.

### MAJOR-1 — the audit measured the batch-8 run and presents it as the frozen batch-9 baseline

The audit's §1 evidence column and §7 both cite `discovery_reports/TRAIN8-7185633/
2026-08-28T224640.553059-0000-cda8882d`. The frozen deterministic-v1 / multi-account-v1 baseline the
audit says it is auditing (`819d97d`, tag `batch9-final`, 2,625/3,380) was measured as
`discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a`. The document names the
batch-9 baseline in its header and reads the batch-8 rows.

Almost everything survives — I measured both runs and the entire intake-provenance surface is
byte-for-byte identical (`visual_rung`, `source_path`, `source_model`, `cache_visual`, 3,506 rows,
3,380 distinct shas), because nothing in batch 9 touched the intake ladder. Three numbers do not:

| | audit (batch-8 rows) | run of record (batch-9) |
|---|---|---|
| U trigger | ≤ 122 | **123** |
| cost bound | ≤ 135 / 3,506 = 3.8 % | **≤ 136 / 3,506, just under 4 %** |
| #8's Tesseract outcome split | 36 validated / 16 withheld / 5 review / 122 failed | **36 / 15 / 5 / 123** |

The correction is small; the provenance error is not, because §5.4 turns the bound into a proposed
runtime refusal ("the runner should refuse to escalate more documents than the triggers named"). A
runner built to a stale trigger population refuses the 123rd document.

### MAJOR-2 — the seam is not two values: the extractor's model string reaches the admissible analysis text, and it is environment-controlled

§2.3 #23 states: *"The seam is exactly **two values** … There is no third channel and no per-field
provenance."* §5.7 builds its whole structural argument on that. It is not accurate.

`StatementMarkdown.to_markdown()` (`ocr/document.py:33-49`) emits, as the first line of the analysis
input:

```
<!-- source: {source_file} | pages: {n} | model: {self.model} | empty: {k} -->
```

The extractor writes `model` — so the extractor writes a string into the document the validator
reads. What actually closes the channel is a guard the audit never names: `admissible_text`
(`analysis/parser_registry.py:197-215`) strips that comment via `SOURCE_COMMENT_RE` (`:194`), applied
centrally at `analyze_markdown`'s single parse seam since W3 FILENAME-BOUNDARY, and pinned by
`tests/test_filename_boundary.py`. The safety argument is *true*, but for a reason §5.7 does not
give, and the reason is escapable:

* `SOURCE_COMMENT_RE` is `^<!--\s*SOURCE:.*?-->\s*$` with `MULTILINE` and **without** `DOTALL`. A
  model string containing `-->` does **not** escape (I tested it; backtracking consumes to the last
  `-->` on the line). A model string containing a **newline** does.
* Reproduced end-to-end at this tree: with `OCR_MODEL` set to a two-line value, the second line —
  including an injected money token — appears in `admissible_text(document.to_markdown())`. Both the
  marker text and the money token reach the text every parser's detection markers scan and every text
  metric runs over.
* `ocr/pipeline.py:149` stamps `model=settings.model` onto the visual rung's `StatementMarkdown`, and
  `settings.model` is `os.environ.get("OCR_MODEL", …)` (`ocr/config.py:29`) — the same unvalidated env
  read F-4 already flags.

This upgrades F-4 from an *egress* finding to a **content-injection** finding: `OCR_MODEL` is not
only "which host gets the pixels", it is "arbitrary text in the analysis input of every document the
visual rung reads". Unreachable today (zero visual reads) and reachable the day Phase 2 enables the
rung — and §5.5 item 2 proposes *new* extractor-authored model-string conventions
(`unlimited-ocr+…`, `paddle+…`) that go straight into that header.

**The architecture proposal must add:** the seam is three values (`markdown`, `sheets`, `model`), the
third is neutralised by `admissible_text` and not by the seam's shape, and any new extractor's model
token must be validated against a closed character class in the same commit that adds it.

### MAJOR-3 — an OCR-artifact-cache reader is missing from the 45, and it already implements F-9's fix

`telemetry/stated_counts.py::CachedArtifacts` (~`:820-940`) has **zero mentions** in the audit. It:

* opens the same `webapp.db` `artifact_cache` index, `mode=ro`, and reads the same `ocr` and
  `analysis` stages `tools/cohort_replay.py` reads (with a documented reason for not using
  `webapp.storage.Storage`: `_ensure_schema` writes, and "an observer that can write to the thing it
  observes is not an observer");
* indexes `input_sha → {settings_key: path}` and **selects deterministically from a declared, ordered
  `_ocr_keys` list** — which is precisely the "settings-key argument and a total order" that §5.6
  calls the single blocking prerequisite and treats as new work. **The fix is already written in this
  tree, by an earlier wave, twenty lines long.**
* filters the analysis stage by `settings_key == self._analysis_key` — the predicate `_payload` lacks;
* and its `_ocr_keys` list **already enumerates the visual partition**
  `(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True)` as its third entry. In-tree code
  already anticipates the multi-partition world the audit says does not exist yet.

That last point carries a policy consequence the audit cannot flag because it does not know the module
exists: `_ocr_keys` puts the two offline partitions **first** and the visual partition **last**. The
day a document holds both, this observer silently keeps reading the offline read. That is a defensible
default and it is also an unratified ranking of extractors, sitting in an unclassified module, that
Phase 2 would inherit by omission.

`webapp/app.py` is the second missing component (§1.7 above). Both belong in the table with labels and
evidence, and the reuse plan needs a line naming `CachedArtifacts` as the prior art for F-9.

### MAJOR-4 — §2.7's headline number is false as written, and it misses a user-facing "OCR confidence"

The audit claims: *"A case-insensitive search for `confidence` / `conf_score` / `ocr_score` across
`ocr/`, `webapp/`, `telemetry/`, `analysis/schema.py`, `analysis/pipeline.py` and
`analysis/serialization.py` returns **0 hits**."*

Run over exactly those paths, it returns **14 hits**, all under `webapp/`. Restricted to `*.py` it
returns 0 — the audit's search was silently Python-only, and the paper says "across `webapp/`".

The substance survives: no extractor emits a score, no record carries one, the validator has no
parameter that reads one. But what the search missed is directly on the card's list ("evidence /
confidence plumbing") and is not cosmetic:

* `webapp/static/app.js:594-601` `confidenceFrom(report)` returns a **hard-coded 98 / 94 / 80 / 72**
  from the validator's own `quality` verdict, and `:1146,1159` render it to the operator as
  `"OCR confidence"` and a percentage in the completion banner and the results table
  (`webapp/templates/index.html:1010` is the banner slot).
* It is not an OCR measurement at all — it is a re-encoding of a deterministic verdict under an OCR
  label, and there is a second one, `packageConfidence` (`:604-609`), for packages.

For Phase 2 this matters more than it does today: the moment a second extractor exists, an operator
reading "OCR confidence 94%" beside an OCR-fed document will reasonably believe the number describes
the OCR read. It describes the validator. §2.7's conclusion ("an extractor literally has no channel
through which to argue for its own output") is right about the Python; the UI already shows a number
that looks exactly like the channel the doctrine forbids. Fix the claim, and add the surface to the
open questions: rename it, or derive it from something real, before an extractor lands behind it.

### MAJOR-5 — #45's "zero hits" is false, and there IS PaddleOCR prior art in the tree

The audit's only row about the net-new extractor says: *"`grep -riE "paddle\|easyocr\|textract\|donut\|
trocr\|surya"` over the tree returns **zero** hits. PaddleOCR is entirely net-new; there is no legacy
to reuse and no adapter interface to fit it into."*

That grep returns **ten files**. Two are substantive prior art:

* `docs/superpowers/specs/2026-07-21-paddleocr-bank-statement-parser-design.md` — 192 lines, dated
  2026-07-21, **"Status: Approved (pending written-spec review)"**: a full design for a PaddleOCR
  bank-statement parser. PP-OCR text + bounding boxes with **custom bbox-based row/column
  reconstruction**, per-bank profiles with a generic fallback, `python parse.py <statement.pdf>` as
  the interface, structured JSON out.
* `docs/superpowers/specs/2026-07-22-nanonets-vlm-bank-statement-parser-design.md` — 184 lines, a
  second pre-deterministic extractor design.

The audit's *code* claim is right — there is no PaddleOCR code. Its stated claim is wrong, and the
gap is material in three ways: the bbox row/column reconstruction that spec designs is exactly the
OCR word-box geometry §5.5 item 3 wants for `document_geometry` (#38); the spec's front door is
`parse.py`, the audit's `unsafe` #30; and an "Approved" design document for the extractor Phase 2 is
about to build has to be superseded on the record, not discovered later. §0 says the legacy "was
found by content instead" of by filename — `docs/superpowers/specs/` was not searched by content
either, and the audit's own grep would have found it.

---

## 3. Minor findings

**MINOR-1 — the census tool's read-only argument contains a false statement.**
`tools/ocr_legacy_census.py:12-14`: *"It has no `open(..., "w")`, no `Path.write_*`, no `os.replace`,
no `shutil`, no `subprocess`, no network client."* The module imports `subprocess` at `:72` and calls
`subprocess.run` at `:250` (`git log --follow`, `git rev-parse`). The substance is unaffected — those
are read-only git invocations and I verified there is no write path anywhere in the module — but the
audit's §0 cites that docstring as the authority for the tool's read-only-ness ("its docstring's
`READ-ONLY BY CONSTRUCTION` section states how"), so the one sentence carrying the guarantee is
inaccurate. W3 §OCRAUDIT states it correctly ("no `subprocess` write path"); the tool should say what
the W3 says.

**MINOR-2 — "every component's reachability was computed" overstates the instrument's coverage.**
§2.6 attributes the empty `unknown` bucket to a computed transitive walk over all 45 rows. The
census's `COMPONENTS` tuple holds **27 paths**, two of the 45 rows are not code (#16 the README
surface, #22 the cache directory), and roughly 16 rows never went through the instrument at all —
including `telemetry/prices.py` (#17), `telemetry/record.py` (#27, #28), **`tools/cohort_replay.py`
(#29, an `unsafe` row and one of the audit's own five most consequential)**, `analyze.py` (#36), the
three forensic oracles (#37), `experiments/w3_3a/evaluate.py` (#39) and the five test/fixture rows
(#40–#44). The labels are still defensible; the claim that they were uniformly instrument-backed is
not. Either extend `COMPONENTS` to the full inventory (cheap — it is a tuple) or say which rows were
resolved by reading.

**MINOR-3 — F-4 names three default-`allow_visual_ocr=True` entry points; there are four.**
`sweep_ocr.py:52` is the fourth. The audit's own #31 describes it writing full OCR'd statement text
to `output/`, so the omission is an enumeration slip rather than a miss — but F-4 excludes it while
including `coverage_audit.py:178`, which is `obsolete` and `reach = NO` on the same terms.

**MINOR-4 — F-9's exposure is larger than the OCR stage.** `ColdCache._payload` is called for both
stages: `text()` → `_payload("ocr", …)` and `baseline_payload()` → `_payload("analysis", …)`. F-9,
§2.3 #29 and §5.6 discuss only the OCR partition. The **analysis** settings key includes the parser
registry fingerprint (`webapp/artifact_cache.analysis_settings_key`), which changes at essentially
every wave — so a data directory reused across two registry versions holds two analysis partitions per
input long before it holds two OCR partitions. Measured 0 today (2,630 / 2,630 / 1 key), but the
hazard is nearer on the analysis stage than on the one the finding is written about, and
`CachedArtifacts` already filters it (MAJOR-3).

**MINOR-5 — F-2's scanner argument needs its concrete case.** "The scanners cannot see base64" is
right about the grammar, but the branch scanner reads *diffs*, and OCR artifacts are never committed —
so as written the claim is about a scanner that would never have looked. The concrete case that makes
F-2 bite is the **committed** OCR fixtures (`tests/corpus_cache/ocr/<SHA>.md`, the audit's own #43):
an Unlimited-OCR read committed there would carry inlined document imagery into the repository, and
`tools/privacy_scan_branch.py:467` excludes everything under `tests/corpus_cache/` wholesale via the
`corpus_cache` rule. That is the shape worth stating: a committed fixture, invisible content, and an
exclusion that already blankets the directory.

---
### MINOR-6 (new, does not block) — the owed census is scoped to six members; the chain has nine

§5.7's deliverable and F-11's third consequence both say `postprocess` is "six functions deep" and
scope the census to "all six members". Parsed from the source, `ocr/ocr_client.py:409-416` calls
**nine** distinct functions: `strip_det_tags`, `strip_refusal_commentary`,
`strip_placeholder_markers`, `strip_oversized_embedded_images`, `collapse_repeated_amounts`,
`collapse_repeated_page_numbers`, `split_fused_header_row`, `repair_fused_amount_table`,
`fix_amount_column_bleed`. The three missed are the three nested on the first line, and all three
**delete text**: `strip_placeholder_markers` drops whole lines, `strip_det_tags` removes a tag plus a
following token in its orphan form, and `strip_refusal_commentary` removes model prose.

Since the census is the gate for OQ1's option (c), a census scoped to six of nine members is a gate
with three holes. I probed all three and none is a value rewrite on any input I could construct
(`_REFUSAL_RE` at `:18-23` is a tightly anchored three-sentence template and leaves an adjacent money
token alone; the placeholder regex matches only the placeholder), so this is a **scoping defect, not a
demonstrated hazard** — which is precisely why it belongs inside the census rather than outside it.
The fix is to say nine and name the three. It does not stop Gustavo ruling: option (c) already reads
"re-admitted function by function only as the rewrite census in §5.7 clears each one", and "each one"
is recoverable from three lines of code.

### Verdict

**CONFIRMED — READY FOR GUSTAVO.** Eleven findings closed, each verified by re-measurement rather than
by reading the closure's claim: the trigger counts re-derived two ways, the census figures for both
new rows re-run, the table re-parsed to 47, the guards and both scans re-executed, the 48 discards
individually read, the W3 append-only property re-verified against the base, and the `filter-branch`
rewrite proven message-only by tree-object comparison across all three generations.

The closure is honest about what it got wrong, credits the review where a finding came from the
review, and — in the three places where the correct answer was "raise it, do not settle it" (the
`_ocr_keys` ordering, the fabricated confidence label, the Approved spec) — raises it as a risk and an
open question instead of quietly resolving it. That instinct is what makes the document safe to hand
over. MINOR-6 is a one-word correction to an owed deliverable's scope and belongs in the Phase-2 card.

---

# Batch-9 backlog and its open rulings, VERBATIM

*(Mechanical extract of `docs/moneythumb-replacement/BATCH9_BACKLOG.md` in full — it carries
CONS-HARDCODE, MINOR-7, PAGECOV-IMAGE-SHEET, RAISE-PRIVACY-6, the frozen-out deterministic
coverage, and the standing Phase-2 risk.)*

# Batch-9 backlog — frozen out by Gustavo's scope freeze (2026-08-30; BATCH9_TRANSITION §8.11)

Batch 9 finishes only L1-S2 → L1-S3 → L1-S4. Nothing below enters batch 9 unless it meets one of
the three exceptions: (a) a regression discovered by the composed cold run; (b) a correctness
defect affecting previously validated output; (c) something strictly required for S4 itself to
function safely. Items are listed with their card (where one exists), the measured figure at the
time of freezing, and the exception question if there is one. This file is append-only; a line
moves out only when Gustavo rules it an exception or Phase 2 absorbs it.

## Exception candidates — need Gustavo's call before anything happens
| item | card | measured | why it might be an exception |
|---|---|---|---|
| `analysis/consumers.py:90` correctness hardcode | `CONS-HARDCODE` | fixing it moves **2 validated → failed**, 1 pinned (ceremony) | ruled a CORRECTNESS hardcode (§8.3); removing it demotes documents validated on it — exception (b) if those two validations are wrong today. Not required for S4. |
| the design's §9 four production defects (incl. `dakota_west`'s derived section selection, F4 — touches pinned `F748A799FDC7F25E`) | L1 design §9; S4/S5 territory | 0 movement measured for S2; F4 unmeasured | exception (b) only if a validated payload is wrong because of one; otherwise backlog with L-1 expansion |
| three other `None` exits of `_parse_sectioned_statement` bypassing the omission ledger | S2 review MINOR-3 | archive population **0** (107 callee calls / 98 validated / 8 `None`, all 8 recorded) | exception (c) only if S4's publisher reaches them; the S4 card carries it |
| the SINGLE-account package path admits a member on job status alone (`webapp/app.py:767`); Q1's account-based gating exists on the document path (`:814`) only | S4 review MINOR-7 (2026-08-31) | pre-existing; every current production member is a single-account job | needs Gustavo's ruling: extending Q1's gate to the whole existing population is a package-behavior change for already-served documents — exception (b) only if a non-validated account is being aggregated today |

## Deterministic coverage — backlog (no new cells after S4)
| item | card | measured at freeze |
|---|---|---|
| PAGECOV-IMAGE-SHEET (inline-image sheets counted as present with proof) | `PAGECOV-IMAGE-SHEET` | **+8** review → validated (linkbank 4, core_processor_enclosures 4); pinned-surface ceremony 102/3 → 103/2; ruling never taken |
| DESC-ROTATION / WELCH (DESC-COLUMNS printed-row rung) | `DESC-ROTATION` | 2 community_section column-direction declines + WELCH (`361167E3`) |
| TABLES-GRID-BALANCE | `TABLES-GRID-BALANCE` | as carded |
| BMO-HYGIENE | `BMO-HYGIENE` | as carded |
| remaining bank-tail parsers (the census clusters not opened) | `CENSUS_BATCH9.md`, `census_batch9/clusters.json` | 784 remaining at the batch-8 freeze; 2,596 official / 2,617 candidate at this freeze |
| additional deterministic row / layout opportunities; other single / double-digit opportunities | census estimates table | per `census_batch9/opportunity_estimates.json` |
| L-1 expansions beyond the first working publisher (the 44 of 86 single-posting documents; the 62 empty-and-silent + 7 other-wording sibling sections; other boundary mechanisms — `section-identity`, `section-equation-scan`) | L1 design §2.3 / §2.6 | reachability unmeasured beyond the `guardian_cu` family by the design's own statement |
| transaction-lifecycle research | (none) | — |

## Privacy / hygiene — backlog
| item | card | state |
|---|---|---|
| FIXTURE-PRIVACY-3 (MONEY / DIGITS half of `tests/`; restore ~4 program dates the +28 sweep shifted in prose; message scanner as a `--messages` mode) | `FIXTURE-PRIVACY-3` | carded, not launched |
| PROD-RESIDUE-CLASSIFY (classify the 414 production residue sites before rewriting — §8.3) | `PROD-RESIDUE-CLASSIFY` | carded, not launched |
| RAISE-PRIVACY-6 | `RAISE-PRIVACY-6` | proposal; ruling never taken |
| record redaction | — | REFUSED where it destroys benchmark / provenance evidence (§8.3) — stays refused |

## Rulings
**RULED 2026-08-30 (BATCH9_TRANSITION §8.13–§8.16, all Option A):** Q1 (publish the validated
account; ACCOUNT-based package membership on own `validated`), Q2 (printed designation; same-document
counterparts; ambiguity refuses aggregation only), Q5 (one ACCOUNT → one ADB; refuse the blending
arithmetic, keep the package), Q7 (two dated rows). S4 is unblocked from the ruling side.
**Closed by the freeze unless re-raised:** Q4 (two denominations, 4 documents / 12 sections — refused
until ruled), Q6 (per-account activity range — refused until ruled); the PAGECOV-IMAGE-SHEET
ceremony; RAISE-PRIVACY-6. S4 proceeds on Q3 (corroborated), Q9 (B) and Q10.

## Standing risk carried into Phase 2 (Q3 probe review MINOR-1, 2026-08-30)
The corroborated Q3 class (`printed_pair_coincides_and_no_row_printed`, seven conditions) was measured 6 / 6 on the
`guardian_cu` population — but all six documents carry extractor model `native-pdf-text`; none was OCR'd. The
roll-up witness was ruled in to bound OCR row-loss and has therefore been measured exactly as ordered but NOT
exercised against the failure mode it guards. **Phase 2 / `OCR-LEGACY-AUDIT` must re-measure the class on OCR'd
input — these six as the seed population — before relying on it there.** Also unmitigable at this base: one
`ocr`-stage artifact per document and no PDFs in the cold cache, so the six cannot be cross-read.

## Phase 2 (after the freeze)
`OCR-LEGACY-AUDIT` first (read-only), then the extraction architecture — Unlimited OCR + PaddleOCR as
extractors only into the SAME deterministic validator. Everything in this backlog that OCR could
reach is re-priced there, not here.
