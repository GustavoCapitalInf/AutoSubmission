# Agent Handoff — COUNTS-P1

Complete self-contained brief; read fully before acting. Ocean reviews and
merges; you never merge or push.

# Identity
- **Agent:** COUNTS-P1 · stated-count integrity check, **Phase 1 (observe-only)** — Gustavo architectural sign-off 2026-08-10, rulings in `WAVE2_EXECUTION_LOG.md` (read that entry first; it is binding law for this card).

# Git ownership
- **Base:** current main (record the SHA) · **Branch:** `wave3-stated-counts-p1` · **Worktree:** `.claude/worktrees/mt-counts`. Commit only there; never merge; never push.

# Context
Read in-tree, in order: the 2026-08-10 sign-off entry in `WAVE2_EXECUTION_LOG.md`; `PROPOSAL_STATED_COUNTS.md` (the approved design — your spec, as amended by the sign-off's closed vocabulary); `W3_2_TAXONOMY.md`; the witness sections in `W3_TRACKA_LOG.md` (RBC §5.5, §BOFA, §TRIO/PNC). Protected modules (`analysis/reconcile.py`, `metrics.py`, `pipeline.py`, `serialization.py`, all parsers) are READ-ONLY reference — Phase 1 lands ZERO production-path changes.

# Scope — Phase 1 is measurement tooling, nothing else
- Build the observer as a standalone module (suggest `telemetry/stated_counts.py` + a CLI surface in `telemetry/report.py` or `python -m telemetry.stated_counts`): it reads **cached analysis payloads** (D-3 artifact cache and/or the discovery runs' telemetry+rows — the newest full run is `52b4b2b2`; prefer sources that cover all 3,380 distinct docs) and computes, per document, the comparison with the **closed vocabulary: `match | mismatch | not_printed | semantics_incomparable | check_unavailable`**.
- **Independence requirement (binding):** the expected side is the bank-printed stated counts as extracted fields in the payload; the captured side is recomputed by YOU from the payload's transaction rows **by printed semantic `direction`, never by amount sign**. Never use `metrics`' derived counts for the expected side; document the field provenance of both sides.
- **Semantics mapping table (deliverable):** survey the ~20 count-extracting parsers (read-only) and classify each bank's printed-count semantics; encode known incomparabilities as `semantics_incomparable` with a per-bank documented reason (BofA cheques folded into debits — decide comparable-with-mapping vs incomparable and justify; US Bank category sums; Wilson & Muir three-way; section-level counts → incomparable at this schema). The mapping is data with provenance comments, not scattered conditionals.
- **Allowed files:** `telemetry/` (new module + CLI wiring), `tests/` (new test module), `docs/moneythumb-replacement/COUNTS_P1_MEASUREMENT.md` (the evidence package), `W3_2_TAXONOMY.md` ONLY if you add observer-side vocabulary documentation (no class changes). NOTHING in analysis/, ocr/, webapp/, discovery/, corpus assets, audit CSVs, .github/.

# The measurement (deliverable #1 — Gustavo's acceptance-evidence list, verbatim targets)
Produce `COUNTS_P1_MEASUREMENT.md` with, at minimum:
1. **Coverage:** how many of the 3,380 distinct documents expose usable printed counts (and per parser).
2. **Per-parser:** match rate, mismatch rate, semantics_incomparable rate, not_printed, check_unavailable.
3. **Would-be-flagged populations:** currently VALIDATED documents with `mismatch` (the critical list — aggregate counts per parser + hash references, no content); currently withheld/review documents with `mismatch`.
4. **Witness reproduction:** the RBC §5.5 six-wrong-count documents and the BofA stated-count population — show the observer finds them (or the current post-fix state, explained).
5. **PNC disclosure:** explicitly restate that the PNC witness is section-level and NOT expressible in this schema — separate line, per the sign-off.
6. **Direction-not-sign proof:** at least one concrete example class (zero-amount rows) where sign-based counting would differ and the observer's direction-based count is correct.
7. **Zero-change proof:** `git diff` against analysis/, ocr/, webapp/, discovery/ is empty; the full suite and corpus-marked selection pass with NO behavioral deltas; a test asserting the observer never mutates a payload.
8. Corpus cut: the pinned 109 — any pinned PASS document with `mismatch` gets its own section (D5: adjudication-first material, NO truth-set action — evidence only).

# Validation
Full default suite; `set -o pipefail; python -m pytest -m corpus -q`; `python corpus_gate.py` GREEN byte-identical (trivially — you changed no analysis path; prove it anyway); guards green; observer unit tests covering every vocabulary value including the forced-mismatch prohibition (an incomparable bank must never emit mismatch).

# Stop conditions
Any production-path temptation (that is Phase 2, which exists only after Gustavo reviews your measurement); any payload mutation; any truth-set action regardless of findings; sensitivity: hashes/ids/counts only, never statement content.

# Definition of done
Observer module + tests green; the measurement document complete against the 8-point list; all proofs green with exit codes; clean tree.

# Final report to Ocean
The measurement headline numbers (coverage, per-parser table, would-be-flagged counts, pinned-109 findings); the semantics mapping summary; files changed; verbatim proofs; commit list; risks; open questions — including your recommendation on whether the Phase-1 evidence supports Phase 2, which Ocean carries to Gustavo.
