# Agent Handoff — FIXUPS-1

Complete self-contained brief; read fully before acting. Ocean reviews and
merges; you never merge or push. Three small, independent, evidence-backed
fixes — each its own commit with its own proof.

# Identity
- **Agent:** FIXUPS-1 · platform fixups from BMO-cell and COUNTS-P1 evidence (Ocean-approved 2026-08-10)

# Git ownership
- **Base:** current main (record SHA; includes the BMO merge + v6 bump) · **Branch:** `wave3-fixups-1` · **Worktree:** `.claude/worktrees/mt-fixups`. Commit only there; never merge; never push.

# Context
Read: `WAVE2_EXECUTION_LOG.md` 2026-08-10 entries (BMO cell + D5 forensic verdict — the evidence for all three fixes), `W3_TRACKA_LOG.md` §BMO-LAYOUTS (items 1–2), `COUNTS_P1_MEASUREMENT.md` §7 + the forensic memo substance in the log (first_community).

# Fix 1 — page-declaration false positive (PROTECTED FILE, pre-approved diff class)
`analysis/pipeline.py`: the declared-page regex reads BMO's footer `CONTINUED ON NEXT PAGE` + `2 of 20` as "Page 2 of 20", holding 23 perfectly-reconciling family-B documents under `missing_declared_statement_page`. Ocean pre-approves the restriction class: a lookbehind/guard so a bare `N of M` preceded by `NEXT ` (the continuation footer) is not a page declaration — the BMO agent measured all 23 → validated under a monkeypatch of exactly this. Constraints: the change may only REMOVE matches (restriction, never expansion — state this property in a comment); protected-module standard applies (this is the ONLY pipeline.py hunk permitted; full forensic proof; corpus gate byte-identical — if ANY corpus document's flags change, STOP and report, that is ceremony territory). Tests: the BMO footer shape does not match; a genuine `Page 2 of 20` declaration still does; the corpus doc that legitimately carries `missing_declared_statement_page` (Columbia — see gate/diagnostics) still flags.

# Fix 2 — bare `totals` row counted as a posting date (shared utility)
`analysis/dates.py::_NOT_A_POSTING_ROW` excludes `total(s)? for` but not a bare `totals` line, so `Apr 30 Closing totals …` becomes a posting date (3 BMO docs withheld by posting_date_coverage). Generalize the exclusion to summary-total row shapes (structure-keyed: a totals-labeled line, not a bank literal). Shared-utility standard: survey current consumers, prove no corpus movement (gate byte-identical), negative fixture (a transaction description containing "totals" mid-text is NOT excluded), positive fixtures for the BMO shapes and the existing `total for` forms.

# Fix 3 — first_community count-scope alignment (parser card; D5 follow-through)
`analysis/first_community.py`: `repair_first_community_posted_activity` drops balance-neutral failed-EFT rows and rewrites `stated_total_debits` but leaves `stated_debit_count` at the bank's whole-direction figure — the D5-adjudicated `semantics_difference`. Align: when the repair drops N printed balance-neutral rows, decrement `stated_debit_count` by N in the same rewrite (expected-side scope alignment from printed balance-neutrality evidence — the independence rule holds because nothing derived is read back; put THAT sentence in the code comment). Tests: the pinned corpus document's fixture path — 202→195 count rewrite paired with the existing total rewrite; a no-drop document's counts untouched; guard that the count is never rewritten without the total (and vice versa). NOTE: the pinned corpus doc's PUBLISHED outcomes must remain identical (the stated-count fields feed metrics — survey `metrics.py:353-371` read-only: the stated count overwrites the derived count in the payload, so this WILL change two payload fields (`num_withdrawals` style) on that pinned document. CHECK the audit CSVs: if any pinned column captures those count fields, STOP AND REPORT — ceremony territory. If no audited field moves, proceed and document the payload delta precisely.)

# Validation (per fix and composed)
Full default suite; `set -o pipefail; python -m pytest -m corpus -q`; `python corpus_gate.py` GREEN byte-identical (unless Fix 3 hits the audited-field stop, in which case report); guards green. Read-only archive re-measurement of the affected populations: the 23 family-B docs, the 3 totals docs, first_community's archive population (COUNTS-P1 says 3 mismatch docs — after Fix 3 they should read `match`; verify with the observer: `python -m telemetry.stated_counts` or its CLI, read-only).

# Stop conditions
Any corpus-document outcome/flag/audited-field movement (ceremony); any pipeline.py hunk beyond Fix 1's; any urge to fix adjacent things (report them).

# Definition of done
Three commits, each proof-clean; the affected-population re-measurements; `ANALYSIS_STAGE_VERSION` note (outputs change for the 26+3 archive docs and first_community's fields — bump is Ocean's at merge); clean tree.

# Final report to Ocean
Per fix: the diff summary, tests, affected-population before→after, any corpus-side observation. Verbatim proofs with exit codes; commit list; risks; open questions.
