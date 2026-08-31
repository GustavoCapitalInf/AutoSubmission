# Batch-9 backlog — frozen out by Gustavo's scope freeze (2026-08-30; BATCH9_TRANSITION §8.11)

Batch 9 finishes only L1-S2 → L1-S3 → L1-S4. Nothing below enters batch 9 unless it meets one of
the three exceptions: (a) a regression discovered by the composed cold run; (b) a correctness
defect affecting previously validated output; (c) something strictly required for S4 itself to
function safely. Items are listed with their card (where one exists), the measured figure at the
time of freezing, and the exception question if there is one. This file is append-only; a line
moves out only when Gustavo rules it an exception or Phase 2 absorbs it.

## Exception candidates — need Gustavo's call before anything happens
| item | card | measured | why it might be an exception |
|---|---|---|---|
| `analysis/consumers.py:90` correctness hardcode | `CONS-HARDCODE` | fixing it moves **2 validated → failed**, 1 pinned (ceremony) | ruled a CORRECTNESS hardcode (§8.3); removing it demotes documents validated on it — exception (b) if those two validations are wrong today. Not required for S4. |
| the design's §9 four production defects (incl. `dakota_west`'s derived section selection, F4 — touches pinned `F748A799FDC7F25E`) | L1 design §9; S4/S5 territory | 0 movement measured for S2; F4 unmeasured | exception (b) only if a validated payload is wrong because of one; otherwise backlog with L-1 expansion |
| three other `None` exits of `_parse_sectioned_statement` bypassing the omission ledger | S2 review MINOR-3 | archive population **0** (107 callee calls / 98 validated / 8 `None`, all 8 recorded) | exception (c) only if S4's publisher reaches them; the S4 card carries it |
| the SINGLE-account package path admits a member on job status alone (`webapp/app.py:767`); Q1's account-based gating exists on the document path (`:814`) only | S4 review MINOR-7 (2026-08-31) | pre-existing; every current production member is a single-account job | needs Gustavo's ruling: extending Q1's gate to the whole existing population is a package-behavior change for already-served documents — exception (b) only if a non-validated account is being aggregated today |

## Deterministic coverage — backlog (no new cells after S4)
| item | card | measured at freeze |
|---|---|---|
| PAGECOV-IMAGE-SHEET (inline-image sheets counted as present with proof) | `PAGECOV-IMAGE-SHEET` | **+8** review → validated (linkbank 4, core_processor_enclosures 4); pinned-surface ceremony 102/3 → 103/2; ruling never taken |
| DESC-ROTATION / WELCH (DESC-COLUMNS printed-row rung) | `DESC-ROTATION` | 2 community_section column-direction declines + WELCH (`361167E3`) |
| TABLES-GRID-BALANCE | `TABLES-GRID-BALANCE` | as carded |
| BMO-HYGIENE | `BMO-HYGIENE` | as carded |
| remaining bank-tail parsers (the census clusters not opened) | `CENSUS_BATCH9.md`, `census_batch9/clusters.json` | 784 remaining at the batch-8 freeze; 2,596 official / 2,617 candidate at this freeze |
| additional deterministic row / layout opportunities; other single / double-digit opportunities | census estimates table | per `census_batch9/opportunity_estimates.json` |
| L-1 expansions beyond the first working publisher (the 44 of 86 single-posting documents; the 62 empty-and-silent + 7 other-wording sibling sections; other boundary mechanisms — `section-identity`, `section-equation-scan`) | L1 design §2.3 / §2.6 | reachability unmeasured beyond the `guardian_cu` family by the design's own statement |
| transaction-lifecycle research | (none) | — |

## Privacy / hygiene — backlog
| item | card | state |
|---|---|---|
| FIXTURE-PRIVACY-3 (MONEY / DIGITS half of `tests/`; restore ~4 program dates the +28 sweep shifted in prose; message scanner as a `--messages` mode) | `FIXTURE-PRIVACY-3` | carded, not launched |
| PROD-RESIDUE-CLASSIFY (classify the 414 production residue sites before rewriting — §8.3) | `PROD-RESIDUE-CLASSIFY` | carded, not launched |
| RAISE-PRIVACY-6 | `RAISE-PRIVACY-6` | proposal; ruling never taken |
| record redaction | — | REFUSED where it destroys benchmark / provenance evidence (§8.3) — stays refused |

## Rulings
**RULED 2026-08-30 (BATCH9_TRANSITION §8.13–§8.16, all Option A):** Q1 (publish the validated
account; ACCOUNT-based package membership on own `validated`), Q2 (printed designation; same-document
counterparts; ambiguity refuses aggregation only), Q5 (one ACCOUNT → one ADB; refuse the blending
arithmetic, keep the package), Q7 (two dated rows). S4 is unblocked from the ruling side.
**Closed by the freeze unless re-raised:** Q4 (two denominations, 4 documents / 12 sections — refused
until ruled), Q6 (per-account activity range — refused until ruled); the PAGECOV-IMAGE-SHEET
ceremony; RAISE-PRIVACY-6. S4 proceeds on Q3 (corroborated), Q9 (B) and Q10.

## Standing risk carried into Phase 2 (Q3 probe review MINOR-1, 2026-08-30)
The corroborated Q3 class (`printed_pair_coincides_and_no_row_printed`, seven conditions) was measured 6 / 6 on the
`guardian_cu` population — but all six documents carry extractor model `native-pdf-text`; none was OCR'd. The
roll-up witness was ruled in to bound OCR row-loss and has therefore been measured exactly as ordered but NOT
exercised against the failure mode it guards. **Phase 2 / `OCR-LEGACY-AUDIT` must re-measure the class on OCR'd
input — these six as the seed population — before relying on it there.** Also unmitigable at this base: one
`ocr`-stage artifact per document and no PDFs in the cold cache, so the six cannot be cross-read.

## Phase 2 (after the freeze)
`OCR-LEGACY-AUDIT` first (read-only), then the extraction architecture — Unlimited OCR + PaddleOCR as
extractors only into the SAME deterministic validator. Everything in this backlog that OCR could
reach is re-priced there, not here.
