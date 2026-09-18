# Phase 3 ceiling experiment — root report (DRAFT, updated as waves complete)

Authority: PHASE2_RULINGS.md R16 (Gustavo, 2026-09-17, USD 250). Plan: PHASE3-VLM-PROGRAM-PLAN-v1.md §11.
Branch `phase3-ceiling`. Reviews: `reviews/CEILING-HARNESS-REVIEW-X.md` (BLOCK → closed; re-review 1
APPROVE-WITH-FINDINGS → closed). Public receipts live under `discovery_reports/train13-logs/p3ceiling/`
(gitignored tree); this document carries counts, rates, hashes and codes only.

## 1. What was measured

Two self-hosted models on the approved Vast RTX 5090 (remote_paid), reached only over the SSH loopback
tunnel, with both opt-in literals set per process:

| Stage | Model | Serving | Role |
|---|---|---|---|
| A | PaddlePaddle/PaddleOCR-VL-1.6 (Apache-2.0) + PP-DocLayoutV3 | PaddleOCR 3.7 pipeline, VL via vLLM 0.29.0 | layout + tables → rule-based rows and metadata |
| B | Qwen/Qwen3.5-4B (Apache-2.0) | vLLM 0.29.0, JSON-schema constrained, temperature 0, seed 0 | page → structured proposal (rows, anchors, printed totals/counts) |

Arms: `reader_baseline` (the deterministic reader as it stands), `stage_a_rules`, `stage_b_only`,
`hybrid` (A's tables and text in B's prompt; then the model rows, the parser rows and their union are
tried IN THAT ORDER under one deterministic gate; the receipt records which set was admitted).
The 27B second-opinion arm was not run (21 GB of free disk on the host; R16 note).

The gate (gate v4): the reader's own `analysis.reconcile.reconcile` decides (sum check, running-balance
continuity, the bank's printed summary identity, per-direction printed counts, coverage), plus: no
self-derived anchors (both printed balances required; one derived is recorded but never admitted), no
chain-derived directions without both printed anchors, unverifiable repeats refuse, the hybrid arm
refuses when the model's anchor disagrees with the rule reading, reverse-chronological pages are
oriented, and per-row repeated daily balances collapse to the day's last row. Date order and period
membership are recorded, never refusal reasons. Never partial admission.

False accept (the §11 zero bar): an admitted document whose rows contradict the reader's validated
rows arithmetically (a missing or extra row, or a differing printed balance on a matched row).
Description differences are reported apart.

## 2. Synthetic preflight (no customer bytes)

All three model arms admit both anchored synthetic pages strictly (summary identity true, printed
count matched) and refuse the unanchored control (`anchors_underdetermined`); the rotated page yields no
rows in any arm (orientation handling is off in v1). Two runs: raster hashes identical 9/9, Stage A
blocks identical 3/3, Stage B message texts identical 6/6 → nondeterminism 0 rows on synthetic pages.

## 3. Development slice (20 validated control documents, 118 pages; prompt/harness tuning only)

| Wave | Change | Admitted (strict) | False accepts | Row match vs reader |
|---|---|---|---|---|
| dev-hybrid-01 (gate 2) | first customer wave | 2/20 | 1 (later reclassified: 29/29 rows and balances exact, 11 description variants) | 31 % (588/1,873) |
| 01 regated (gate 4) | orientation, daily-balance collapse, date order recorded | 4/20 | 0 | 31 % |
| dev-hybrid-02+03 (12k output budget, schema 3) | 38/118 truncated pages → 4 | 4/19 | 0 | 79 % (1,460/1,841) |
| 02+03 regated (year rule, candidates) | period year overrides an unprinted model year | 4/19 | 0 | **91.4 % (1,683/1,841)** |

Findings that changed the harness (each closed and committed):
1. Dense pages exceeded a 4,096-token output cap and were lost as invalid JSON (32 percent of pages).
2. Sectioned and newest-first statements failed a date-order check the reader itself never applies.
3. On month/day-only rows the model supplied its own year (2024 for a 2026 statement) with every amount
   right; the statement period's year now overrides an unprinted model year.
4. One hybrid prompt exceeded the 16k context (http_400); the parser context is capped at 10k characters
   and the Stage B server runs at 32k.

Why validated documents still refuse (19 documents; reasons overlap): sum_mismatch 11, continuity_break 7,
count_mismatch 7, summary_mismatch 7, duplicate_row 5, anchor_disagreement 3, date_unparsed 2,
direction_unknown 1. In most refused documents the model matched all but 1–12 of the reader's rows;
the parser's rows and the union did not rescue any (parser candidates fail on `direction_unknown` and
`date_unparsed`: single unsigned amount columns without printed balances).

Cost and speed on the development slice: Stage A ≈ 2.3 s/page; Stage B ≈ 6.5 s/page wall at
concurrency 4 (≈ 20 s per call, 2,500 completion tokens per page at 1,540 px); upload ≈ 300 KB/page;
render 21 ms/page, encode 13 ms/page (pdfium in-process, vs ≈ 1 s/page for the Phase 2.3 poppler path).

## 4. CTRL (114 validated documents, 800 pages) — pending

Primary figure = CTRL without the 20 DEV documents (`report --exclude-manifest DEV`).

| Arm | Admitted (strict) | False accepts | Row match (validated) | Pages/s | Notes |
|---|---|---|---|---|---|
| reader_baseline | 114/114 by construction | — | — | — | |
| stage_a_rules | pending | | | | |
| stage_b_only | pending | | | | |
| hybrid | running (ctrl-hybrid-02, resume of -01) | | | | |

## 5. U755 (755 unresolved documents, 5,110 pages) — pending

| Arm | Reconciled (strict) | By reader outcome (failed / withheld / review / deferred) | By classification (digital / scanned / mixed / unknown) | Pages/s |
|---|---|---|---|---|
| stage_a_rules | pending | | | |
| stage_b_only | pending | | | |
| hybrid | pending | | | |

## 6. Thresholds (plan v1 §11) — to be applied to the U755 hybrid figure

GO ≥ 40 percent of U755 reconciled strictly with zero CTRL false accepts and ≤ USD 0.05 per statement;
REVISE 20–40 percent; STOP < 20 percent, or false accepts the gate cannot close, or nondeterminism
> 1 percent of rows.

## 7. Deviations from plan v1 §11 and known limitations

* Arm 5 (27B second opinion) not run on this host (disk). The calibration set is CTRL itself (R16).
* No orientation handling for rotated pages; no multi-account grouping (rows of a multi-account PDF are
  gated as one account; none in DEV).
* The hourly rate is still "rate not measured"; receipts carry wave wall hours.
* The two-week window started 2026-09-17; waves are resumable (`--resume-from`) and re-gateable
  (`regate --also`) without new model calls.

## 8. Receipts and hashes (filled at closure)

Pending: per-wave `launch.json`/`result.json`/`release.json` hashes, fetch receipt hashes (weights),
schema 3 / prompt 3 / gate 4 hashes, attestation receipts.
