# Agent Handoff — REEF-CHASE-LAYOUTS

Complete self-contained brief; read fully before acting. Ocean reviews and
merges; you never merge or push.

# Identity
- **Agent:** REEF-CHASE-LAYOUTS · phase cell 2: unclaimed layouts of known banks — the Chase family (~176 unclaimed docs in the `Chase/` folder).

# Git ownership
- **Base:** current main (record the SHA) · **Branch:** `wave3-chase-layouts` · **Worktree:** `.claude/worktrees/mt-chase`. Commit only there; never merge; never push.

# Context
Read in-tree, in order: `PROJECT_STATUS.md`, `WAVE2_EXECUTION_LOG.md` (all rulings; the 2026-08-10 phase rules are binding law; the BMO cell entry is your template and standard: 164 → 128 validated, ambiguous 0, cross-claims 0, regressions 0, claimed-but-not-validated refused as success), `W3_TRACKA_LOG.md` (§1 Chase — the EXISTING chase parser's 12 native families and its instrument, §BMO-LAYOUTS — the phase method), `R3_RFC.md`, `R4_CONFORMANCE_FINDINGS.md`.
- **Baseline (your "before"), refreshed 2026-08-13 post-FIXUPS-1:** run `ca2ba0eb` (`discovery_reports/2026-08-10T180653.021975-0000-ca2ba0eb/`, gitignored, main checkout): validated 1,776 / review 10 / withheld 58 / failed 1,523 — DISTINCT-document counts via the compare tool (shared denominator 3,380); name your denominator. Derive the cell exactly: rows.csv `folder_label == "Chase"` × failed/no_parser_matched; expect ≈171–176; report exact count + distinct hashes.
- **What exists:** `analysis/chase.py` handles the `*start*summary`-sentinel native layout (411 claims, 394 validated post-Track-A) + `chase_export` (supersedes edge). The unclaimed docs are DIFFERENT Chase layouts (likely consumer/secure-message/older templates — characterize, don't assume). Beware: chase's detection marker is the `*start*summary` PDF text-layer sentinel; new families must get their own issuer-furniture markers under the full R-4b standard and must NOT weaken or collide with the existing chase/chase_export precedence (supersedes edges where genuinely narrower).

# Phase requirements (binding, same as BMO cell)
1. Characterize structurally BEFORE code; classify each family: detection / extraction / both / unusable / not-a-statement.
2. Structural capability extension over layout-specific literals. New registrations allowed in `analysis/parser_registry_entries.py` under the FULL R-3/R-4 standard: issuer-furniture markers only, detection-positive AND detection-negative fixtures, conformance cross-product ZERO cross-claims (now 49×48+), SOURCE-comment invariance, single-marker invariant, ambiguity protections untouched. A stratified non-Chase probe (≥400 docs across all folders) proving zero new-registration claims is part of your acceptance, per the BMO precedent.
3. Claimed-but-not-validated is NOT success; build and validate the per-layout in-document instrument first; fail closed with documented volume where evidence is insufficient. Platform-side blockers you discover (like BMO's page-declaration case): measure with a scratch probe, report, DO NOT touch protected modules. **FIXUPS-1 has LANDED on your base** (merge `28e04ba`, v7 bump `718c188`: pipeline page-declaration lookbehind, dates bare-totals, first_community count scope) — the overlap clause is retired; measure single numbers against the refreshed `ca2ba0eb` baseline; any platform defect you hit now is a NEW finding to report.
4. Existing chase/chase_export claims and the 8 pinned Chase corpus statements must remain byte-identical.

# Scope
- **Allowed:** new `analysis/chase_*.py` module(s), `analysis/parser_registry_entries.py` (NEW registrations only), tests (`tests/test_chase_layouts.py` + conformance fixture additions + registry-count pin updates), `W3_TRACKA_LOG.md` (append §CHASE-LAYOUTS), audit CSVs ONLY inside an approved ceremony.
- **Protected:** `analysis/chase.py` itself (the existing parser is NOT this card — if a family belongs inside it, stop and propose), registry machinery, shared utilities (consume-only incl. `group_rows`), all other parsers, pipeline, financial core, ocr/, webapp/, discovery/, telemetry/, corpus_gate.py, audit scripts, .github/, corpus PDFs. Archive read-only; synthetic fixtures; aggregates only.

# Validation
Full default suite; `set -o pipefail; python -m pytest -m corpus -q`; `python corpus_gate.py` GREEN byte-identical; guards green; conformance cross-product zero; the non-Chase probe. Cell measurement before → after: claimed / VALIDATED (headline) / review / withheld+diagnoses / unusable, per family. `ANALYSIS_STAGE_VERSION` bump is Ocean's at merge.

# Stop conditions
Registry-machinery or shared-utility needs; existing-parser changes; ambiguity weakening; truth-set movement (ceremony only); geometry-only families (report volume → the geometry queue); scanned-only families (OCR path out of scope); evidence of unusable-dominance.

# Definition of done
Characterization table; capability-level implementation for workable families under full conformance; all proofs green with exit codes; honest measurement with the claimed/validated distinction; zero regressions; §CHASE-LAYOUTS record; clean tree.

# Final report to Ocean
Characterization table first; per family: root-cause class, approach, fixtures; files changed; verbatim proofs; measurement; commit list; risks; unresolved questions.
