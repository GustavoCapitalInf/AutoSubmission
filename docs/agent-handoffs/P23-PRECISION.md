# Agent Handoff — P23-PRECISION (Phase 2.3 cell P: the classifier-precision cycle over the Phase 2.2 residue, the R10 Phase 1 hygiene ceremony over the six bank-keyed repairs, and the Phase 2.2 test residue)

**Launch base:** `train13` at its opening commit (`26f94f5` = `phase2.2-final` `d84af95` + the 2.3 cards).
Worktree `.claude/worktrees/mt23-precision`, branch `wave23-precision`. Everything here runs offline over the
run-of-record cache; nothing is sent anywhere.

Read `docs/agent-handoffs/BATCH9-RULES.md`, `PHASE2-RULES.md`, `docs/moneythumb-replacement/PHASE2_RULINGS.md`
(R10 verbatim; the anti-optimizer rule; R3 — nothing is a label but Gustavo's adjudication; the repair
doctrine as ruled in batch 9: a parser never writes an amount or a date the paper did not print), the
umbrella `docs/agent-handoffs/PHASE2-3-WAVE.md` (cases 15, 16, the exclusions), then the Phase 2.2 record you
close: `reviews/PHASE2_P22CLASSIFY_REVIEW.md` (the first review's MINORs, §Re-review R-1..R-4 verbatim — they are
your first four items), the C sections `# §P22CLASSIFY*` in `W3_TRACKA_LOG.md` (the two censuses, the validated
exceptions by class, `tools/classify_census.py`, the committed mutation harness
`tools/p22classify_mutation_table.py`), `reviews/PHASE2_P22FENCE_REVIEW.md` §Re-review 3 (Q1, Q2 — your test
residue), `docs/moneythumb-replacement/OCR_LEGACY_AUDIT.md` and `BATCH8_TRANSITION.md` (the repair doctrine's
history and the REPAIR-DOCTRINE ceremony precedent: the pinned refusal is the model), then the code:
`layout/document_class.py`, `layout/signals.py`, `layout/refusals.py`, `analysis/bank_repairs.py` (ALL of it —
the six bank-keyed functions `repair_capital_one_running_amount`, `repair_regions_transactions`,
`repair_truist_converted_checks`, `repair_chase_remote_deposit_count_column`,
`repair_scotiabank_misc_payment_sign`, `repair_santander_signs_from_balances`, and the two generic ones you
do NOT touch), every call site of each (`grep -rn bank_repairs analysis/ tests/`), `tests/test_pipeline_escalation_fence.py`
(the orchestration-shape rules; the mutation harness note), `tools/p22truthtable_mutation_table.py` (the
harness idiom that APPENDS its table log). Ocean reviews and composes; you never merge or push. **Hygiene
card: `newly validated = 0`; every previously validated document preserved payload-identical unless a
repair is REPLACED under the doctrine with per-sha evidence (then STOP and report before composing — a
correctness correction is Gustavo's to ratify, never Ocean's or yours); no classification reaches a verdict
or a router; no new bank-keyed logic anywhere; no cost field.**

# Why
Phase 2.2 left two measured residues: 431 validated documents the classifier proposes as something other
than a complete statement (every one a signal defect, since the validator's own gates prove the printed
period, opening and closing are there) and four MINOR rule defects the C re-review named; and Gustavo's R10
orders the six bank-keyed rewrites in `bank_repairs.py` through a hygiene ceremony at the safest Phase 2
milestone — this one, before generalized reconstruction (2.4) builds on the same seam. Both are precision
work over recorded facts: nothing moves a verdict.

# What you deliver (ruled — do not re-decide)
1. **The precision cycle, measured per rule.** For EACH change: the cache census (`tools/classify_census.py`
   over `webapp_data_train12_cold`, READ-ONLY) BEFORE and AFTER, the validated-exception count by class and
   the kind × modality × tier table, the movement named by count (never by sha beside a verdict), a synthetic
   fixture that pins the rule, a mutant in the committed harness. The rules, in order: **R-1** MICR shape —
   a genuine E-13B line with the dash / dot symbols read as `-` / `.` is MICR-shaped again (at least one of
   the four E-13B glyphs or their OCR confusions, date shapes excluded; restore `'` and `"` to the confusion
   set or say why not); **R-2** the page-marker rule — prefer the candidate whose number continues the
   marker sequence (or equals the expected page position), fall back to the lowest line; a
   boilerplate-footer fixture beside the existing one; **R-3** a change of the declared total is a NEW
   sequence and a new sequence that begins above 1 owes `missing_first_page` (the head guard mirroring the
   tail guard); **R-4** the hyphen-joined period covers the short `m/d` and the ISO alternations. Then the
   two signal classes behind the 431: the closing-label class (≈ 270) and the no-ledger class (≈ 160–190) —
   characterise each on the cache census (which label spellings, which table shapes; counts only), close what
   a deterministic rule closes with a fixture per shape, and report the residue that no rule closes as a
   finding for adjudication (R3), never as a default. The truth table v0 → v2 movement is reported per rule.
2. **Never a verdict:** `layout/` still imports only the standard library and `evidence` (the boundary test);
   `classify_document` is pure; nothing under `analysis/`, `ocr/`, `discovery/` reads a kind to decide anything
   (T's payload-identity test still green; an AST guard that no kind literal appears under `analysis/`).
3. **R10 — the Phase 1 hygiene ceremony**, one record per bank-keyed repair (six), each in this order:
   (a) INVENTORY — the function, its call site(s), the bank/parser it keys on, what it rewrites (an amount, a
   direction, a running balance, a row) and from what evidence; (b) INDEPENDENT REPRODUCTION — the documents
   whose payload the repair touches on the run of record (the cache census by count; a `cohort_replay` at
   base with the repair disabled in a SCRATCH copy shows exactly which shas move and how — counts by outcome
   in the W3, shas only in the private report); (c) COMPARISON WITH THE DOCTRINE — does it write an amount or a
   date the paper did not print? does it reconcile by construction (the anti-optimizer pattern) or restore a
   printed fact the extractor lost? (d) CLASSIFICATION into exactly one of `safe_evidence_preserving_normalisation`
   / `unsafe_rewrite` / `legacy_needing_replacement`, with the reason; (e) the CONSEQUENCE — a safe
   normalisation gains a tripwire test that pins what it may and may not do (never invent a figure; only
   restate a printed one); an unsafe rewrite or a legacy repair is NOT deleted and NOT rewritten in this cell:
   it is named with its per-sha population and its doctrine reason in the W3 as a STOP item for Ocean and
   Gustavo (a correctness correction that would move a validated document is a ruling, per BATCH9-RULES).
   Delete nothing merely for being bank-specific; keep nothing merely for being old; write no new bank-keyed
   logic. The two generic repairs are inventoried in one paragraph and left alone.
4. **The Phase 2.2 test residue (tests only):** F re-review-3 **Q2** — the fence tripwire's permitted-unit
   set refuses a DUPLICATE top-level definition of any orchestration name (`_analyse`, `analyze_markdown`,
   `analyze_document`, `_account_report`): one top-level `def` per name, a second one a violation in its own
   right (the re-reviewer's Y7 re-applied and killed by the static layer); **Q1** — the committed mutation
   harnesses (`tools/p22classify_mutation_table.py`, `tools/p22truthtable_mutation_table.py`, the fence
   harness if it is committed) APPEND to their table log with a run header instead of overwriting it.
5. **No hardcodes:** every new fixture is synthetic (dates ≥ 2031; literal strings); the OQ2 scans green.

# Files you own (exact; nothing else)
`layout/document_class.py` · `layout/signals.py` · `layout/refusals.py` (vocabulary only if a new finding
code is needed — report it) · `tools/classify_census.py` (read-only fixes to its output shape only) ·
`tools/p22classify_mutation_table.py` (the appended rows and the Q1 append) · `tools/p22truthtable_mutation_table.py`
(Q1 only) · `tools/bank_repairs_ceremony.py` (new: the inventory / reproduction instrument, read-only over the
cache) · `analysis/bank_repairs.py` (TRIPWIRE-PRESERVING changes only: a docstring naming the classification
and a guard that a safe normalisation cannot invent a figure — NO behaviour change; anything else is a STOP)
· `tests/test_document_class*.py`, `tests/test_layout_signals*.py` (or the existing C test files) · a new
`tests/test_bank_repairs_ceremony.py` · `tests/test_pipeline_escalation_fence.py` (Q2 only) · your W3
section. `analysis/pipeline.py`, `analysis/reconcile.py`, every parser module, `ocr/**`, `telemetry/**`,
`discovery/**`, `evidence/**`, `webapp/**` are NOT yours.

# Mutation table (run every mutant, name every killer)
M1 R-1 reverted (a dash disqualifies) → the E-13B fixture · M2 R-2's sequence preference dropped → the
boilerplate-footer fixture · M3 R-3's head guard dropped → the restarted-sequence fixture · M4 R-4's short
form dropped → the `m/d` period fixture · M5 a closing-label spelling admitted without its fixture → the
per-shape fixture set · M6 a kind literal planted under `analysis/` (scratch copy) → the AST guard · M7 the
census tool printing a sha beside a kind → the output-shape test · M8 a safe normalisation inventing a
figure (scratch copy: the guard removed) → the tripwire test · M9 a bank-keyed repair deleted → the
ceremony's inventory test (each of the six must exist with its classification docstring) · M10 a duplicate
top-level `def _analyse` (the re-reviewer's Y7) → the fence tripwire's new rule · M11 a harness overwriting
its table log → the Q1 append test.

# Proof floor
Full default suite; the 5 canonical guards; the 7 canonical conformance files; `python corpus_gate.py`
GREEN 105/3/1; `pytest -m corpus`; the UNION `cohort_replay --expect-identical` at base `26f94f5` and at
closure (chunked `--parser`; `analysis/bank_repairs.py` is on the analysis path even if only docstrings
change — prove byte identity); the two censuses before/after every rule (counts); the ceremony's
reproduction replays (each repair disabled in a scratch copy, at base: the movers by count and outcome — a
private report, never a tracked file); privacy scan 0 over added lines against the run-of-record population
(`--base 26f94f5 --ref <tip>`); message scan 0. Heavy proofs one at a time under the lock
`discovery_reports/train13-logs/HARNESS.lock` (mkdir-only; holder inside; own-holder release; Git bash `rmdir`
when Python's is refused; unbounded waits — cells W, E, X share the host).

# Report contract (final message to Ocean AND your W3 section `# §P23PRECISION — …`)
population (the cache census 3,380; the 755; the six repairs' touched documents by count) · root cause ·
solution · newly validated 0 · ladder movement 0 · previously validated preserved all, identical ·
regressions 0 · classification evidence (per rule before/after; the validated exceptions by class; the
residue for adjudication) · the R10 ceremony record (six entries, each with its classification and reason;
the STOP items) · the test residue closed · commits · proof exits · privacy count · risks last.

# Exclusions
No verdict from a kind · no routing · no repair deleted or rewritten · no new bank-keyed logic · no
adjudication (R3) · no Paddle · no cost.
