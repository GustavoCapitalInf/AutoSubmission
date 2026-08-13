# Agent Handoff — COUNTS-P2

Complete self-contained brief; read fully before acting. Ocean reviews and
merges; you never merge or push. Gustavo has APPROVED phase 2 (2026-08-13)
under the narrowed design established by phase 1 and the D5 forensic result.

# Identity
- **Agent:** COUNTS-P2 · the stated-count integrity check, phase 2: structured
  count fields + semantics-table-gated integrity flags. Flag, never withhold.

# Git ownership
- **Base:** current main (record the SHA) · **Branch:** `wave3-counts-p2` ·
  **Worktree:** `.claude/worktrees/mt-counts2`. Commit only there; never
  merge; never push.

# Binding law (read in-tree, in order)
1. `WAVE2_EXECUTION_LOG.md` — the 2026-08-10 **STATED-COUNT CHECK: GUSTAVO
   ARCHITECTURAL SIGN-OFF** entry (closed vocabulary, two-phase rule, D5),
   the same day's **D5 FORENSIC ADJUDICATION** entry, and the
   PLATFORM-PROPOSALS entry (Ocean rulings incl. DIAGNOSABLE_CLASSES).
2. `PROPOSAL_STATED_COUNTS.md` — §7 is the PINNED protected-module diff
   shape, approved under the W3-1b verbatim-as-approved idiom (line drift
   allowed; semantic drift is not). §7.1 lands as pinned. §7.2 lands AMENDED:
   each flag additionally gated on the semantics table (below).
3. `COUNTS_P1_MEASUREMENT.md` — the evidence and the §10 recommendation
   Gustavo approved; §9 is the vocabulary and evaluation order.

# What phase 1 + D5 already settled (do not relitigate)
- Closed vocabulary: `match / mismatch / not_printed / semantics_incomparable
  / check_unavailable`; incomparable can NEVER emit mismatch — structural.
- Count by `Transaction.direction`, never by amount sign; gross reversals; no
  tolerance; `None` = not-applicable, never zero (`is False` is load-bearing).
- Independence: the expected side is only `statement.stated_credit_count` /
  `stated_debit_count`; `metrics.effective_*` are never read (tripwire stays).
- The sole pinned-PASS mismatch (first_community `08B2A61B…`) was adjudicated
  `semantics_difference` and its parser card LANDED (`acd0b07`, in FIXUPS-1).
  **Phase 2 therefore expects ZERO pinned truth-set movement and ZERO
  validated→review movers. If your measurement contradicts this: STOP,
  report — ceremony is Gustavo's.**

# Requirements
1. **Pre-measurement gate (before any production edit):** run the phase-1
   observer joined to run `ca2ba0eb`
   (`discovery_reports/2026-08-10T180653.021975-0000-ca2ba0eb/`, payloads at
   `ANALYSIS_STAGE_VERSION = 7`) with the amended semantics table. Confirm:
   (a) zero pinned-PASS mismatches (the first_community doc now `match`);
   (b) the §3.3 counterfactuals still hold at v7 for every promotion you
   ship (chase debit, us_bank both, wilson_muir both — expected 0 would-be
   mismatches each); (c) the would-be validated→review population is zero.
   Any promotion whose fresh counterfactual is non-zero is NOT promoted —
   preserve incomparable where semantics are not proven. Record all numbers.
2. **Semantics table as production data:** new module
   `analysis/count_semantics.py` — the authoritative parser-id × direction
   table with per-entry provenance (the P1 arguments verbatim), default
   UNSURVEYED = not comparable. Promotions: `chase`, `us_bank`, `wilson_muir`
   per §3.3 evidence re-proven at v7 (label-list caveat recorded in the
   module). `capital_one`, `texas_bank`, `bank_of_america`, `altana` REMAIN
   incomparable (parser cards are separate future work). `pnc`/`wells_fargo`
   remain section-level-oracle exclusions. `telemetry/stated_counts.SEMANTICS`
   must not fork from it: import it or pin equality with a test.
3. **§7.1 reconcile.py** exactly as pinned: four fields + one computation
   block, no issue appended, `ok` untouched. Protected module — verbatim
   discipline; Ocean runs the forensic audit at merge.
4. **§7.2 pipeline.py AMENDED:** flags `credit_count_mismatch` /
   `debit_count_mismatch` emit only when `formal` AND the semantics table
   says comparable for that parser × direction AND the recon field
   `is False`. A parser absent from the table (e.g. any new registration
   landing in parallel) must emit nothing, by default, structurally —
   test this.
5. **§7.3 same merge:** `telemetry/diagnostics.py` INTEGRITY_FLAGS + CLASS_OF
   → `detail_coverage` (rank 9), `DIAGNOSTICS_VERSION` 2→3, W3_2_TAXONOMY.md
   §11 changelog; extend `DIAGNOSABLE_CLASSES` to `review` per the standing
   Ocean ruling (coupled to this merge, not before, not separately).
6. **Structural tests** (minimum): incomparable-never-flags across every
   table entry against a payload built to disagree; unsurveyed-never-flags;
   direction-not-sign witness; `None` never flags; aggregate-backed and
   non-formal guards; independence tripwire; table/observer consistency;
   the §7.2 `is False` semantics.
7. `ANALYSIS_STAGE_VERSION` bump is Ocean's at merge (integrity.flags change
   for unchanged settings — D-3 rule). Do not bump it yourself.

# Scope
- **Allowed:** `analysis/count_semantics.py` (new), `analysis/reconcile.py`
  (§7.1 pinned diff ONLY), `analysis/pipeline.py` (§7.2 amended diff ONLY),
  `telemetry/diagnostics.py` (§7.3 ONLY), `telemetry/stated_counts.py`
  (consume the shared table; observer semantics unchanged), tests, `docs/
  moneythumb-replacement/COUNTS_P2_REPORT.md` (your report),
  `W3_2_TAXONOMY.md` §11 changelog entry.
- **Protected / untouched:** everything else. No parser modules, no registry
  entries, no metrics.py/serialization.py/adb.py, no webapp/, ocr/,
  discovery/, corpus_gate.py, audit CSVs, .github/. Archive read-only.
  `possible_document_issue` NOT extended (decision D3).

# Validation
Full default suite; `set -o pipefail; python -m pytest -m corpus -q`;
`python corpus_gate.py` GREEN **106 PASS / 3 WITHHELD byte-identical outcome
classes** (new payload keys are additive; audited fields untouched); guards
green; the pre-measurement numbers (req 1) and the post-implementation
would-be-flag population (expected: flags only on already-withheld documents;
zero validated→review movers). Ocean runs the official movement instrument
post-merge; your preview must predict it.

# Stop conditions
Any pinned-PASS mismatch under the amended table; any predicted
validated→review mover; any need to touch a file outside Allowed; any
promotion whose v7 counterfactual is non-zero (drop the promotion, proceed,
report); `reconcile.ok` or any issue list changing anywhere; gate not
byte-identical on outcome classes.

# Definition of done
Pre-measurement recorded; table with provenance; pinned/amended diffs landed
and quoted verbatim in the report with line anchors; all proofs green with
exit codes; zero outcome movement predicted and explained; clean tree;
`COUNTS_P2_REPORT.md` complete.

# Final report to Ocean
Pre-measurement table first; then per-file diffs (verbatim), test inventory,
proof transcript (exit codes), the predicted flag population by parser ×
current outcome class, promotions shipped/dropped with evidence, risks,
unresolved questions.
