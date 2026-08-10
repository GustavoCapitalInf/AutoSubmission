# Agent Handoff — REEF-BMO-LAYOUTS

Complete self-contained brief; read fully before acting. Ocean reviews and
merges; you never merge or push.

# Identity
- **Agent:** REEF-BMO-LAYOUTS · first cell of the new work class: **unclaimed layouts of known banks** (Gustavo-approved phase, 2026-08-10)
- **Task:** the BMO unclaimed family — the largest known-bank unclaimed cluster (~164–178 documents in the `BMO/` folder that NO parser claims today).

# Git ownership
- **Base:** current main (`181e131` or later — record the exact SHA you start from) · **Branch:** `wave3-bmo-layouts` (created, checked out) · **Worktree:** `.claude/worktrees/mt-bmo`. Commit only there; never merge; never push.

# Context
Read in-tree, in order: `PROJECT_STATUS.md` (the Track A checkpoint you build on: validated 1,622 / withheld 58 / zero regressions — that record is the bar), `WAVE2_EXECUTION_LOG.md` (rulings; esp. R-3 RFC scoring/ambiguity, R-4b issuer-furniture standard, the 2026-08-10 phase entry), `R3_RFC.md`, `R4_CONFORMANCE_FINDINGS.md`, `W3_TRACKA_LOG.md` (the method), `W3_2_TAXONOMY.md`.
- **Baseline (your "before"):** run `52b4b2b2` (`discovery_reports/2026-08-09T025430…-52b4b2b2/`, gitignored, main checkout): validated 1,622 (distinct-doc count via the compare tool; report.txt records differ — name your denominator), withheld 58, failed/no_parser_matched pool contains your family. Derive the family exactly: rows.csv, `folder_label == "BMO"`, outcome failed/no_parser_matched. Expect ≈176–178 docs; report your exact count and hashes-distinct count.
- **What exists today:** `analysis/bmo.py` handles ONE layout (the corpus's summary-block layout; its pinned corpus document is one of the 3 WITHHELD — a proven-contradictory statement — so BMO's validated base is only ~4 archive docs). Detection: required marker `ACCOUNT SUMMARY TOTALS` heading + the BMO/BANK OF MONTREAL disjunction (R-4b hardening). The unclaimed family is BMO printing DIFFERENT layout families the parser has never seen.

# Phase requirements (Gustavo, binding, verbatim-in-spirit)
1. **Characterize the unclaimed family structurally BEFORE changing code.** Read-only archive sampling; group into layout families by structural signature; for each family determine the root cause class: **detection** (layout parseable by existing extraction but never claimed) / **extraction** (claimable but the current extractor can't read it) / **both** / **genuinely unsupported-unusable input**. That classification table is deliverable #1 and drives everything.
2. **Prefer structural capability extension over layout-specific literal rules.** New layout families may become: extended handling inside `analysis/bmo.py`, or a NEW registration (e.g. `bmo_<structural-name>`) in `analysis/parser_registry_entries.py` — allowed in this phase, under the FULL R-3/R-4 standard: issuer-furniture markers only (R-4b classes: domains/headings/footers/legal names — never customer data, never corpus-fitted constants), detection-positive AND detection-negative fixtures, the 46+×45+ conformance cross-product stays ZERO cross-claims, SOURCE-comment invariance, the single-marker invariant (no registration identifies a bank by one marker alone), and ambiguity protections untouched — two claimants above threshold must still resolve by supersedes or surface as ambiguous, never first-wins.
3. **No statement-specific fixes. Fail-closed validation untouched.** A document becoming CLAIMED but not validating is NOT success — the primary outcome is independently validated analysis. Build the in-document instrument first (what does each BMO layout print and assert about itself — summary totals, balance columns, counts?) and validate the instrument before trusting it.
4. **Fixtures:** synthetic/adversarial, both directions, per family.
5. The registry's existing bmo detection must keep claiming its current documents (the ~4 validated + the withheld corpus doc) identically.

# Scope
- **Allowed:** `analysis/bmo.py` (and new `analysis/bmo_*.py` modules if a family warrants its own), `analysis/parser_registry_entries.py` (NEW registrations only — never edit existing ones or the registry machinery), tests (`tests/test_bmo_layouts.py` + conformance additions per R-4 idiom), `W3_TRACKA_LOG.md` (append §BMO-LAYOUTS), audit CSVs ONLY inside an approved ceremony.
- **Protected:** `analysis/parser_registry.py` machinery, all shared utilities (consume-only, incl. `group_rows`), all other parsers, pipeline, financial core, ocr/, webapp/, discovery/, telemetry/, corpus_gate.py, audit scripts, .github/, corpus PDFs. Archive: read-only, synthetic fixtures only, aggregates only.

# Validation
Full default suite; `set -o pipefail; python -m pytest -m corpus -q`; `python corpus_gate.py` GREEN byte-identical (the withheld BMO corpus doc must remain withheld with its source_contradiction diagnosis intact — that is a correctness property, not a target); guards green; conformance cross-product zero. **Cell measurement before → after with the phase's required cuts: newly CLAIMED count, newly VALIDATED count (the headline), withheld-among-claimed with diagnosis classes, unusable/fail-closed count, regressions (must be zero), plus per-family attribution.** `ANALYSIS_STAGE_VERSION` bump is Ocean's at merge.

# Stop conditions
Registry machinery or shared-utility needs; any ambiguity-protection weakening; truth-set movement (formal ceremony only); a family needing geometry (text layer without grid order — report volume, it joins the geometry queue); evidence the family is dominated by unusable input; scanned-only families (the OCR path is not yours to extend).

# Definition of done
The family-characterization table (root-cause class per family, volumes); capability-level implementation for the families ruled workable; full R-3/R-4 conformance for any new registration; all proofs green with exit codes; honest measurement with the claimed-vs-validated distinction explicit; zero regressions; §BMO-LAYOUTS record; clean tree.

# Final report to Ocean
Characterization table first; then per-family: root-cause class, approach (extended vs new registration vs fail-closed vs unusable), fixtures; files changed; verbatim proofs; measurement (claimed / validated / withheld+diagnoses / unusable, before → after); commit list; risks; unresolved questions.
