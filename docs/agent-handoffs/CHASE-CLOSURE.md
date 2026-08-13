# Agent Handoff — CHASE-CLOSURE

Complete self-contained brief. Ocean reviews and merges; you never merge or
push. Part of the 2026-08-13 high-parallelism coverage wave.

# Identity
- **Agent:** CHASE-CLOSURE · the two evidence-backed Chase residual cards
  from §CHASE-LAYOUTS: A′ zero-activity (7 docs) + B1 savings (10 docs).

# Git ownership
- **Base:** current main (record the SHA) · **Branch:** `wave3-chase-closure`
  · **Worktree:** `.claude/worktrees/mt-chase2`. Commit only there.

# Context (read in-tree)
`PROJECT_STATUS.md` · `WAVE2_EXECUTION_LOG.md` 2026-08-13 entries (binding:
the sign-fix conditions pattern, the review findings) · `W3_TRACKA_LOG.md`
§CHASE-LAYOUTS (families A′ and B1, the scratch evidence: A′ 4/7 under the
conservative guard; B1 rough reader 6/10) · `R3_RFC.md` /
`R4_CONFORMANCE_FINDINGS.md`. Baseline run `6893a75b`
(`discovery_reports/2026-08-13T163911.518386-0000-6893a75b/`, main checkout,
read-only): validated 1,910 / review 10 / withheld 60 / failed 1,387 over
3,380 distinct. The 18 cell documents: `folder_label == "Chase"` × failed ×
chase in candidates/near_miss at ≥0.5 (7 A′ + 10 B1 + 1 B2-unusable).

# Card A′ — zero-activity guard (PRE-AUTHORIZED chase.py change)
Ocean pre-authorizes a minimal admissibility guard in `analysis/chase.py`
under the SAME conditions as the sign fix: an empty ledger is admissible
ONLY when the bank printed zero instances in every section AND the printed
balances agree; anything else keeps today's refusal. Conditions (all
mandatory): minimal diff, quoted verbatim in your report; full before/after
sweep over ALL currently-claimed chase-family documents (~501) byte-identical;
detection surface unmoved; synthetic fixtures BOTH directions (a true
zero-activity statement validates; a non-zero statement with an empty
captured ledger still refuses — do NOT equate empty ledger with valid
statement); expect 4/7, the other 3 refuse correctly.

# Card B1 — savings reader (NEW registration)
Ocean pre-rules: B1 is a distinct printed product (`SAVINGS SUMMARY`, single
`*start*transaction detail`, grid `DATE DESCRIPTION AMOUNT BALANCE`, amount
cell wraps onto the line ABOVE its row, grid Beginning/Ending Balance rows
are bounds not transactions). Build `analysis/chase_savings.py` + a NEW
registration under the FULL R-3/R-4 standard: issuer-furniture markers,
positive AND negative fixtures, zero cross-claims over the full
cross-product, single-marker invariant, SOURCE-comment invariance. It must
win the B1 documents from chase's 0.5 decline WITHOUT touching chase's
existing 497 claims — supersedes edge only if genuinely narrower. Validate
with a per-document instrument (running balance walk, ledger identity,
printed section totals); expect ~6/10 validated, fail closed on the rest
with diagnoses. Wrapped-amount handling must be structural (line-group
bounds), not content-matched — see the square_checking footer lesson in the
08-13 log entry.

# Scope
- **Allowed:** `analysis/chase.py` (card A′ guard ONLY), `analysis/
  chase_savings.py` (new), `analysis/parser_registry_entries.py` (new
  registration only), tests (`tests/test_chase_closure.py` + conformance
  fixtures + count pins), `W3_TRACKA_LOG.md` (append §CHASE-CLOSURE).
- **Protected:** everything else — pipeline, reconcile, count_semantics,
  registry machinery, shared utils (consume-only), all other parsers,
  webapp/, ocr/, telemetry/, discovery/, corpus_gate.py, audit CSVs,
  .github/. Archive read-only; synthetic fixtures only; $0 vendor.

# Validation
Full default suite; `set -o pipefail; python -m pytest -m corpus -q`;
`python corpus_gate.py` GREEN 106/3 byte-identical; guards; full conformance
cross-product zero; the chase-family sweep; a stratified non-Chase probe
(≥400 docs) proving zero new-registration claims outside the B1 family.
Exit codes verbatim. ANALYSIS_STAGE_VERSION bump is Ocean's at merge.

# Stop conditions
Any chase.py need beyond the single A′ guard; registry-machinery or
shared-util needs; ambiguity weakening; truth-set movement (ceremony only);
the B1 reader wanting to live inside chase.py (stop and propose).

# Final report to Ocean
Per card: diff quoted verbatim, fixtures, proofs with exit codes, sweep
output, measurement preview (claimed vs VALIDATED vs refused per card,
named against `6893a75b`), commit list, risks, unresolved questions.
