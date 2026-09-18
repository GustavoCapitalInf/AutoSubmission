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
| B (second opinion, from 2026-09-18) | nvidia/Qwen3.8-27B-NVFP4 (Apache-2.0; NVIDIA ModelOpt NVFP4/FP8 build of Qwen/Qwen3.8-27B) | vLLM 0.29.0, fp8 KV cache, CUDA graphs for batch sizes 1/2/4, same prompt, schema and decoding | same role, run as `stage_b_only` with the layout parser stopped (the card holds one of them) |

Arms: `reader_baseline` (the deterministic reader as it stands), `stage_a_rules`, `stage_b_only`,
`hybrid` (A's tables and text in B's prompt; then the model rows, the parser rows and their union are
tried IN THAT ORDER under one deterministic gate; the receipt records which set was admitted).
The 27B second-opinion arm was not run (21 GB of free disk on the host; R16 note).

The gate (gate v6): the reader's own `analysis.reconcile.reconcile` decides (sum check, running-balance
continuity, the bank's printed summary identity, per-direction printed counts, coverage), plus: no
self-derived anchors (both printed balances required; one derived is recorded but never admitted), no
chain-derived directions without both printed anchors, unverifiable repeats refuse, the hybrid arm
refuses when the model's anchor or period year disagrees with the rule reading, reverse-chronological
pages are oriented, and per-row repeated daily balances collapse to the day's last row. Rows dated
outside the printed period refuse (gate v5, added after the CTRL wave: every row of all 114 validated
control accounts lies inside its printed period). A statement that prints a running balance on every row
must keep date order (gate v6, added after the 27B development wave: all 37 balance-chained validated
control accounts have zero breaks); on sectioned statements without per-row balances date order is
recorded only. Never partial admission.

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
| 02+03 regated (gate 5) | period check, year window (after the CTRL wave) | 4/19 | 0 | 91.4 % (1,683/1,841) |
| 02+03 regated (gate 6) | chained date order | 4/19 | 0 | 91.4 % (1,683/1,841) |
| **27B** dev-stageb27-02+03 (stage_b_only, gate 5) | second opinion, same prompt/schema/gate | 7/20 | 1 (16 of 218 rows dated a day early, every amount and balance exact) | 98.7 % (1,849/1,873) |
| **27B** regated (gate 6) | chained date order refuses the day-early document | **6/20** | **0** | **98.7 % (1,849/1,873)** |

Findings that changed the harness (each closed and committed):
1. Dense pages exceeded a 4,096-token output cap and were lost as invalid JSON (32 percent of pages).
2. Sectioned and newest-first statements failed a date-order check the reader itself never applies.
3. On month/day-only rows the model supplied its own year (2024 for a 2026 statement) with every amount
   right; the statement period's year now overrides an unprinted model year.
4. One hybrid prompt exceeded the 16k context (http_400); the parser context was capped at 10k characters.
   The Stage B restart at 32k recorded at the time never replaced the live 16k process (found after the
   CTRL wave, where the same cause failed 10 of 114 documents: any page whose prompt exceeds 4,384 tokens
   once 12,000 completion tokens are reserved). The server now serves 32,768 (verified over the tunnel),
   and the runner refuses to launch a Stage B wave whose served context leaves under 8,192 prompt tokens
   (`stage_b_context_too_small`, recorded in `launch.json`).

Why validated documents still refuse (19 documents; reasons overlap): sum_mismatch 11, continuity_break 7,
count_mismatch 7, summary_mismatch 7, duplicate_row 5, anchor_disagreement 3, date_unparsed 2,
direction_unknown 1. In most refused documents the model matched all but 1–12 of the reader's rows;
the parser's rows and the union did not rescue any (parser candidates fail on `direction_unknown` and
`date_unparsed`: single unsigned amount columns without printed balances).

The 27B second opinion (Gustavo, 2026-09-18: "stop the current qwen 4b on the gpu and paddle and open space to
this model right here"): the BF16 and FP8 builds of Qwen3.8-27B fit neither the 32 GB card nor the host's
disk, so the NVIDIA NVFP4/FP8 build was fetched (21 GB, receipt `b27`) after the 4B weights, the PaddleX
model cache and the pip cache were deleted. The vLLM recipe's single-5090 shape (CUDA graphs off) decoded
at about 10 tokens per second per request with the GPU 19 percent busy; capturing graphs for batch sizes
1, 2 and 4 at a lower memory share gave 80 to 116 tokens per second aggregate and 18 s per page wall at
concurrency 2 (2,074 completion + 2,335 prompt tokens per page). Its synthetic preflight verdicts are
identical to the 4B's. On the development slice it gated all 20 documents (the 4B lost one to a server
misconfiguration), admitted 6 strictly against the 4B's 4, matched 98.7 percent of rows against 91.4, and
its one false accept (dates copied from inside the descriptions, a day early, with every balance exact)
is closed by gate v6 on the evidence of the control truth. The refusals that remain are sum and summary
mismatches (7 each), unverifiable repeats (5), continuity breaks and count mismatches (3 each).

Cost and speed on the development slice (4B): Stage A ≈ 2.3 s/page; Stage B ≈ 6.5 s/page wall at
concurrency 4 (≈ 20 s per call, 2,500 completion tokens per page at 1,540 px); upload ≈ 300 KB/page;
render 21 ms/page, encode 13 ms/page (pdfium in-process, vs ≈ 1 s/page for the Phase 2.3 poppler path).

## 4. CTRL (114 validated documents, 800 pages) — 4B hybrid and 27B model-only complete

Primary figure = CTRL without the 20 DEV documents (`report --exclude-manifest DEV`): 94 documents.

| Arm | Gated | Admitted (strict) | False accepts | Row match (validated) | Speed | Notes |
|---|---|---|---|---|---|---|
| reader_baseline | 94 | 94/94 by construction | — | — | — | ctrl-reader-01 |
| stage_a_rules (4B era) | 20 of 114 | stopped | | | | ctrl-stagea-01, stopped by a local memory kill, abandoned at the model change |
| stage_b_only (4B) | 20 of 114 | 5 of 20 | | | | ctrl-stageb-01, stopped by a local memory kill, abandoned at the model change |
| **stage_b_only (27B)**, gate 6 | **94 of 94** (114 of 114 overall, 0 failures) | **27/94 (28.7 %)** | **0** | **95.9 % (10,817/11,283)** | 14.7 s/page wall at concurrency 3 (2,045 completion + 2,316 prompt tokens/page) | ctrl-stageb27-01 + -02 merged → -0102-g6b; the rented instance stopped mid-wave when the Vast account's credit reached zero, was restarted (large files lost, weights re-fetched with identical hashes) and the wave resumed from its receipts |
| hybrid (gate 5 regate) | 86 | **11/86 (12.8 %)** | **1** (see below; 2 under gate 4) | **90.7 % (8,975/9,898)** | Stage B 6.5 s/page wall at concurrency 4 (19 s per call); Stage A 2.2 s/page | ctrl-hybrid-02 → -02-g5; 8 http_400 failures = the 16k server (finding 4), retried after the fix |

27B detail (primary, gate 6, all 114 gated): 33 strict admissions over the whole set, 27 over the primary 94; 24 of
the 27 carry description variants only; no derived anchor was admitted (1 recorded). Refusal reasons over the
whole set (overlapping): sum_mismatch 44, summary_mismatch 33, duplicate_row 32, count_mismatch 32,
continuity_break 15, date_unparsed 6, date_order_chained 3, currency_conflict 2, single cases of
direction_unknown, no_rows, period_mismatch, anchor_derived, missing_beginning_balance and
anchors_underdetermined. Against the 4B hybrid on the same 94 documents: 27 vs 11 strict admissions,
95.9 vs 90.7 percent of rows, 0 vs 1 false accept, at 2.3 times the wall time per page.

Hybrid detail (4B, primary, gate 5): all 11 admissions came from the model's rows (the parser rows and the
union rescued none); anchors corroborated by the rules in 7, partial in 2, model-only in 2; 8 of the 11
carry description variants only. Tokens per page: 3,740 prompt, 2,400 completion. Refusal reasons over the
whole wave (overlapping): sum_mismatch 67, count_mismatch 42, continuity_break 39, duplicate_row 31,
summary_mismatch 31, anchor_disagreement 19, date_unparsed 12, currency_conflict 6, period_mismatch 5,
direction_unknown 4, coverage_mismatch 2, no_rows 1. Period year: model and rules agree in 67, model-only
in 37, disagree in 0.

False accepts under gate 4 were 2; both are date disagreements with every amount, direction and balance
matching:

1. A French-dated statement (month names the text parser cannot read, so the period-year rule never
   fired) reconciled with 82 of 150 rows carrying the model's own year, two years off the printed period.
   Closed in gate 5 (commit e6f126c): rows outside the printed period refuse, and a row whose printed
   text carries no year takes the period year that puts it inside the period window. Re-gated, the
   document matches 150/150 rows with 150/150 balances exact.
2. A 43-row statement without a balance column: one row the model dates four days earlier than the
   reader does. The Stage A layout parser reads the same date as the model on that row (two independent
   readings against the reader), and no arithmetic check can decide a date on a balance-less statement.
   It stays a false accept under the strict definition until a person looks at the page (the document is
   named in the private receipts and the wave report). If the reader is wrong, the CTRL false-accept
   count is 0.

## 5. U755 (755 unresolved documents, 5,110 pages) — 27B model-only complete; two denominators

Gustavo (2026-09-18) expected part of this population to be voided checks, identity documents and single
statement pages without transactions. A deterministic screen over the reader's own extracted text (money
tokens, date tokens, statement vocabulary, non-statement vocabulary; `vlm/subset.py`, screen v1; counts
only) buckets the 755 as: statement-like 546 (median 6 pages, median 170 amounts), no transaction amounts
78 (mostly single pages), thin 62, amounts without statement vocabulary 21, no text extracted 29 (16 with
no readable page), explicit non-statement wording 19. The derived manifest `U755S` (546 documents, 4,351
pages) binds the source manifest and the rule. The plan's figure is reported on the 755 and, as the honest
denominator, on the 546.

| Arm | Reconciled (strict) of 546 | of 755 | By reader outcome (failed / withheld / review / deferred) | By classification (digital / scanned / mixed / unknown) | Pages/s |
|---|---|---|---|---|---|
| **stage_b_only (27B)**, gate 6 | **98 / 546 (17.9 %)**; 540 gated, 6 PDFs unreadable by the renderer | **98 / 755 (13.0 %)** | failed 87/474, withheld 7/46, review 4/20 | digital 77/464 (17 %), scanned 21/73 (29 %), mixed 0/3 | 5.5 s/page effective on the 96 GB card (2,242 completion + 2,319 prompt tokens/page) |
| hybrid (4B) / stage_b_only (4B) | 2 receipts each before the model change; abandoned | | | | |
| stage_a_rules | not run (layout parser stopped for the 27B) | | | | |

U755 detail (27B, gate 6, waves u755s-stageb27-02..-08 merged into `-all-g6`): admissions fall with length,
25/58 for statements of 1 to 2 pages, 52/221 for 3 to 6, 15/172 for 7 to 12, 6/89 for 13 or more, because a
single wrong row anywhere refuses the whole statement. Families with at least 8 gated: TD Bank 9/17, BMO 6/11,
Truist 6/10, Citizens 4/8, Chase 2/15, Capital One 1/16, Huntington 0/12, Bank of America 0/10, RBC 0/8,
Unidentified 51/308. Refusal reasons (overlapping): sum_mismatch 289, continuity_break 166, duplicate_row 154,
count_mismatch 139, summary_mismatch 136, anchors_underdetermined 50, date_order_chained 40, period_mismatch 20,
date_unparsed 19, direction_unknown 16, anchor_derived 14, currency_conflict 13. No truth exists for these
documents, so no false-accept figure exists here; the zero-false-accept evidence is the control set (§4).
All admissions are model-only anchors (no layout parser on the 96 GB host). One document would have been
admitted with a derived anchor and was refused (anchor_derived is never admitted).

## 6. Thresholds (plan v1 §11) and verdict

GO ≥ 40 percent of U755 reconciled strictly with zero CTRL false accepts and ≤ USD 0.05 per statement;
REVISE 20–40 percent; STOP < 20 percent, or false accepts the gate cannot close, or nondeterminism
> 1 percent of rows.

Measured: 17.9 percent of the 546 statement-like unresolved documents and 13.0 percent of the plan's 755
reconcile strictly under the 27B (the 4B's arms were abandoned at the model change). Zero false accepts on
the control set with the 27B (one disputed date-only case with the 4B, §4). Cost per statement is below the
bar on any rental in use (about 5.5 s per page on the 96 GB card at about USD 1.6 per hour, roughly one cent
per statement).

**Verdict: STOP for an off-the-shelf model as a drop-in reader, on both denominators.** The gate holds and the
row-level reading is close (96 percent of rows on the control set, 29 percent of scanned unresolved statements
reconciled), but whole-statement reconciliation of the residue is below the plan's lowest band. The evidence
supports the path the plan foresaw for this outcome: fine-tuning on the reader's validated statements, which
Gustavo approved separately on 2026-09-18 (R17). The silver dataset for it is built (2,071 documents, 15,887
pages, 252,767 aligned rows) and the trainer is written; both wait for a host with disk for the BF16 base.

## 7. Deviations from plan v1 §11 and known limitations

* Arm 5 (27B second opinion) not run on this host (disk). The calibration set is CTRL itself (R16).
* No orientation handling for rotated pages; no multi-account grouping (rows of a multi-account PDF are
  gated as one account; none in DEV).
* The hourly rate is still "rate not measured"; receipts carry wave wall hours.
* From 2026-09-18 the Stage B model is the 27B NVFP4/FP8 build, a quantized third-party-packaged build
  of Apache-2.0 weights: its ceiling is a lower bound of the BF16 model's. The 4B's hybrid figures on CTRL
  stand as measured; its other CTRL arms stopped at 20 of 114 (local memory kills) and were abandoned.
* The hybrid and stage_a_rules arms are not run for the 27B: the card holds either the 27B or the layout
  parser. On the 4B, no admission ever came from the parser's rows or the union.
* Local memory: Claude Code stops background waves when the workstation runs low on memory; waves resume
  from receipts and are merged by `regate --also`, so no model call is repeated.
* The two-week window started 2026-09-17; waves are resumable (`--resume-from`) and re-gateable
  (`regate --also`) without new model calls.

## 8. Receipts and hashes (filled at closure)

Pending: per-wave `launch.json`/`result.json`/`release.json` hashes, fetch receipt hashes (weights),
schema 3 / prompt 3 / gate 4 hashes, attestation receipts.
