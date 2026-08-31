---
name: phase2-state
description: "PHASE 2 IN AUDIT (2026-08-31): OCR-LEGACY-AUDIT complete at wave10-ocraudit 9882b06 (adversarial review in flight); governing finding — the visual OCR rung NEVER ran in the frozen baseline (0/3,506); Phase 2 is audit-and-enable, not build; three questions gate any implementation card; Gustavo reviews the audit first"
metadata: 
  node_type: memory
  type: project
  originSessionId: cb1cf72a-869e-4d03-8265-e32d06315d32
  modified: 2026-08-31T22:35:09.104Z
---

**Baseline**: batch 9 FROZEN at `batch9-final` (2,625/3,380 = 77.66%, main 819d97d; see [[batch9-state]]).
Phase 2 doctrine (§8.12): Unlimited OCR + PaddleOCR are EXTRACTORS ONLY feeding the SAME
deterministic validator; they may not bypass or weaken any of the ten protections.

**OCR-LEGACY-AUDIT (wave10-ocraudit, tip 9882b06, read-only, 3 files)** — governing finding:
`visual_rung = not_attempted` on 3,506/3,506; one OCR settings key (`allow_visual_ocr=False`);
source_path native 3,297 / tesseract 179 / none 30 / visual 0. All 2,625 validated rest on
native+Tesseract. `discovery/runner.py:438-670` already implements the card's flow (recovery,
upgrade, disjoint cache partition, same validator, fail-closed) and has run on zero documents →
**Phase 2 = audit-and-enable**. 45 components: 26 active / 9 reusable / 4 obsolete / 1 dup /
**4 unsafe** / 1 net-new (PaddleOCR absent). The unsafe four: `ocr_client.collapse_repeated_amounts`
(\s+ crosses newlines — destroys ledger rows; demonstrated), `embed_image_regions` (pixels as
base64 invisible to token scanners), `cohort_replay._payload` (rows[0], no ORDER BY/settings
filter — safe only while no input has 2 OCR artifacts), `ocr/config` ($0 invariant unenforced;
three entry points default allow_visual_ocr=True). Triggers already recorded in the run: R
`deferred_visual_ocr` 13 docs; U unclaimed-Tesseract ≤122 → residue ≤135/3,506 = 3.8%. NO
confidence plumbing exists anywhere. OCR_STAGE_VERSION 4→5 proposed (with extractor + tool
versions in the settings key; pinned test moves in the same commit).

**Three questions GATE any Phase-2 implementation card (in OCR_LEGACY_AUDIT.md §6, 8 total):**
(1) remove or scope the money collapse; (2) does the no-hardcodes guard extend to `ocr/`
(a named issuer + a masked page rectangle live in the intake layer); (3) does the $0 policy
become code (an endpoint allowlist).

**Standing risk carried from batch 9**: the Q3 corroborated class passed 6/6 only on
native-pdf-text — re-measure on OCR'd input (the six guardian_cu docs as seed;
tools/q3_corroboration_probe.py the oracle) before any OCR-fed document relies on it.

**Review (15e9535): CONFIRMED WITH FINDINGS — 1 BLOCK / 5 MAJOR / 5 MINOR; audit in closure.**
The BLOCK: `ocr_client.fix_amount_column_bleed` (:129-171) is a SECOND value-rewriting site inside
`<td>` cells — the "one exposure" claim is false and OQ1 must be reframed on the PAIR of rewrite
sites before Gustavo rules. MAJORs: the audit measured the BATCH-8 run as the baseline (corrected
numbers: U=123, bound 136/3,506); the OCR seam is THREE values and a newline in OCR_MODEL INJECTS
text into admissible_text (F-4 = content-injection); "0 confidence hits" is Python-only (app.js
renders a hard-coded "OCR confidence" %); an APPROVED PaddleOCR PP-OCR design spec EXISTS under
docs/superpowers/specs/ (+ a Nanonets VLM spec) — design-layer legacy to reuse; four (not three)
default-allow_visual_ocr=True entry points. Two components the audit missed:
`telemetry/stated_counts.py::CachedArtifacts` (already implements the cohort_replay F-9 fix, but
carries a visual partition key ordered last — a silent unratified extractor preference) and
`webapp/app.py` (rasterizes+serves archive pages over HTTP). F-1 worse than claimed: distinct
adjacent amounts DELETED, not deduplicated.
**Closure CLOSED at 9b7efb6 (all eleven findings upheld; re-review in flight).** §5.7 rebuilt on the
PROVEN rewrite PAIR (F-1 collapse outside `<td>` + F-11 bleed inside) + a declared unknown; a
per-function rewrite census of the six postprocess members is an owed Phase-2 deliverable; **OQ1
re-posed on the pair: (a) remove both / (b) per-extractor flag + synthetic fixtures + touched-page
flag / (c) quarantine the whole postprocess chain, re-admit per census — recommendation (c) with
(b) as exit; "No OCR-fed document may be validated until this pair is ruled."** Corrected numbers
(batch-9 run 91f5179a): U 123, R 13, bound 136/3,506 (<4%), overlap 0, Tesseract 36/15/5/123,
validated∩(R∪U)=0. 47 rows (27/10/4/1/4/0/1). New OQs: 9 (fabricated "OCR confidence"), 10
(CachedArtifacts' visual-last ordering), 11 (the Approved PaddleOCR spec + Nanonets spec as
design-layer legacy). ELEVEN open questions total in OCR_LEGACY_AUDIT.md §6.
**RE-REVIEW: CONFIRMED — READY FOR GUSTAVO (4af079a, 2026-08-31).** All eleven closed; history
rewrite verified tree-by-tree; the 48 discards read individually; OQ1 adjudicated fit to rule with
**(c) quarantine-the-chain shown to be the ONLY fail-closed-consistent option** ((b) leaves the two
declared-unknown members running by default). MINOR-6 carried to the Phase-2 card: the postprocess
census covers NINE members, not six (the three nested calls delete text; none rewrites values).
**THE AUDIT IS WITH GUSTAVO**: OCR_LEGACY_AUDIT.md on wave10-ocraudit tip 4af079a; eleven OQs in §6;
OQ1 gates any OCR-fed validation; OQ2 (hardcodes guard into ocr/) + OQ3 ($0 as an endpoint
allowlist) gate any implementation card. Nothing implemented, nothing carded, nothing moves until
he rules. The audit branch stays unmerged pending his review. Backlog rulings
still open for Gustavo: CONS-HARDCODE, MINOR-7 single-account package path, PAGECOV-IMAGE-SHEET
ceremony, RAISE-PRIVACY-6 (docs/moneythumb-replacement/BATCH9_BACKLOG.md).

Related: [[batch9-state]] [[moneythumb-phase1-roadmap]] [[batch8-operating-model]] [[adb-doctrine]] [[currency-doctrine]]
