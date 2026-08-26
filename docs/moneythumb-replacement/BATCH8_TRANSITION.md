# Batch 8 — transition manifest (rehydrated from git, 2026-08-26)

Written by Ocean after a usage-limit recovery. Nothing here is remembered
from the previous session: every row was re-derived from branch tips, worktree
status, each branch's W3 section and the run of record. Where a cell's review
happened only in a dead session's context and left nothing in the repo, the
row says NOT REVIEWED — a review that is not in the repo did not happen.

## Base facts

| fact | value |
|---|---|
| `main` | `bbeeb5c` = `origin/main` (batch-7 code `302f8f2`; handoffs+census `10cc722`; redactions `cc64232`, `bbeeb5c`) |
| `train8` | `f7a6cce` = `bbeeb5c` + `wave8-coreiss2` merged (registry 77 on the tree). The main checkout is ON `train8`. |
| every `wave8-*` branch | based on `10cc722`; `main` is 2 docs-only commits ahead of that base (both redaction passes) — clean to merge |
| run of record | `356a4269` (batch-7 official: validated 2,469 / 3,380 = 73.0%; review 17; withheld 72; failed 809; deferred 13) |
| floor at base | suite 5,857 · guards 252 · conformance 1,164 (75×74) · gate GREEN 105/3/1 · corpus-marked 30 · v15 · OCR v3 |
| recovered at rehydration | three W3 records sat UNCOMMITTED in worktrees and are now committed verbatim: §GLANCE (555 lines, `4b4558d`), §CPS11.5 (`3fb5a62`), §WELCH post-review revision (`e02ed12`) |

## Cell table

State vocabulary: MERGED · CLOSED (review findings closed on the branch) ·
COMPLETE (implementation + record + proof floor in repo, review not run) ·
PARTIAL · RECORD-MISSING.

| # | cell | branch @ tip | state | claimed movers (cell-measured, uncomposed) | proof floor in repo | review | next action |
|---|---|---|---|---|---|---|---|
| 4 | CORE-ISSUES-2 | `wave8-coreiss2` @ `239f801` | **MERGED** (`f7a6cce`) | +14 validated (`core_processor_signed_counts` 8, `core_processor_activity_summary` 6, both SIBLING) | full | APPROVE W/F — 0 BLOCK, 1 MAJOR (wave-wide process kill, handled), 5 MINOR; closures landed | none |
| 2 | WELCH | `wave8-welch` @ `e02ed12` (prod `61b4292`) | **CLOSED** | +17 validated (`welch_state_bank`; the 17th is the rank-1 verifier's "misfile" `8CCAE7DD`) | suite 5,930 · gate GREEN · 22/27 mutants (5 algebraically redundant, pair mutants kill) · sweep 17 = named · privacy 4,889 literals / 0 | APPROVE W/F — 1 MAJOR wave-level (detect budget within 3% of ceiling at 76 regs → HYGIENE-8 DETECT-BUDGET-GATE), 5 MINOR; closures `61b4292` / `5f95cbc` | closure acceptance (read the two closure commits) → train |
| 3 | LILI | `wave8-lili` @ `7e1e71d` | **CLOSED** | +11 validated (`lili`); 9 named refusals: 5 §INTEGRITY (tampering signature), 3 §L-1 (convert on the ruling), 1 summary≠ledger | suite 5,919 · gate GREEN · 36 mutants / 35 killed + 1 equivalent · sweep · privacy EXIT=0 | APPROVE W/F — 2 MAJOR, 3 MINOR; closures `b1ba3c2` + docs | closure acceptance → train; tampering finding + the L-1 three to Gustavo |
| 5 | FROST-OZK | `wave8-frostozk` @ `9ebac02` | **CLOSED** | +8 validated (`bank_ozk`) **+9 withheld** (`frost`: no printed period; the FROST-PERIOD packet says 6/9 would validate under a derived period) — never "+17" | suite 5,976 · gate GREEN · 39/41 (2 provably redundant) · sweep · privacy re-run CLEAN | **BLOCK** (heredoc-written privacy regexes carried 0x08 → inert scan → 5 real archive dates in tests/comments) + 2 MAJOR + 6 MINOR; closures `9ebac02` | re-verify the BLOCK closure by byte-checking the frostozk instruments and re-running the scan → train; FROST-PERIOD ruling packet to Gustavo |
| 8 | WITHHELD-TD | `wave8-withheldtd` @ `47a07fc` | **CLOSED** | +11 withheld→validated (td_canada_native 6, td_canada_french 4, td_us 1) + 3 non-verdict; pinned TD byte-identical, no ceremony | suite 5,903 · gate GREEN · 16/16 · sweep 14 = named | APPROVE W/F — 2 MAJOR (27 row-level sign corrections mis-stated; count-blind ties now refuse), 6 MINOR; closures `fcdc1a5` .. `47a07fc` | closure acceptance → train |
| 1 | CORE-ENCLOSURES | `wave8-coreenc` @ `32116b3` | **COMPLETE** | **+46 validated**, +1 review, +1 withheld (48 of 58); 6 decline at the ledger, 4 never claimed; 13 claimed outsiders all decline; registry +1 with 3 supersedes edges (`burke_herbert`, `farmers_merchants`, `linkbank`) | suite 5,917 · gate GREEN · 32/32 · sweep · privacy residual 14, each traced, 0 archive-sourced | **NOT REVIEWED** | hostile review first — the largest single claim in the batch |
| 6 | GLANCE | `wave8-glance` @ `4b4558d` | **COMPLETE** (record recovered) | +5 validated (`category_partition`), 3 → `parser_declined` by the card's own refusal; supersedes edge from `wilson_muir` (14 validated docs where both grids print and disagree) | §GLANCE: suite 5,950 · gate GREEN · 37 killers / 3 control arms · archive probe | **NOT REVIEWED** | hostile review |
| 7 | CP-SECTIONED-SCAN | `wave8-cpscan` @ `3fb5a62` | **COMPLETE** (0 movement, measured) | 0 — ceiling 0 of 19, every refusal honest and named; 3 grammar corrections on shared readers (leading-zero glyph, calendar bound, vertical bar); 59/59 of the complex dispatch identically, 32 publish byte-identical | suite 5,894 · 18/18 · gate GREEN · 5-chunk sweep · privacy; §CPS11.5 records one VOID first run | **NOT REVIEWED** | light hostile review (the risk is the three grammar edits on `core_processor_sectioned` / `_daily`, not movement) |
| 9 | WITHHELD-GRIDS | `wave8-withheldgrids` @ `1cdab07` | **COMPLETE** | +17 withheld→validated (community_section 7, regions 3, navy_federal 4, zions 2, wells_fargo 1); 5 stay withheld (pnc ×4 geometry → the PNC card chain; wells `A4E41C80` fail-closed pin); `adb.py` untouched; POSTDATE-HEURISTIC = 5 removal-only rules | suite 5,875 · gate GREEN · 13/13 · 51-mover differential all named · 20 pinned in-family byte-identical | review was in flight when the session died; **nothing in repo → NOT REVIEWED** | hostile review; Ocean must explicitly accept the ONE pinned diagnostic-leaf move (`413AD4C2` ibc, `metrics.adb.source_posting_days`, no gated field) before the train |
| 10 | DESC-COLUMNS (P1) | `wave8-desccols` @ `7e43054` | **COMPLETE** | 0 verdict movement; the native-text rung (`parse_native_printed_rows`, 8 gates) claims 76 archive docs, 21 payloads move (7 counted: descriptions restored incl. the lost six-figure MCA lender credit on `91A2DE99`; 14 `source_posting_days` only); pinned 5 claimed / 0 verdict movement | suite 5,881 · gate GREEN · 9/10 mutants (10th explained) · `tools/desccols_movement.py` is the real proof (the stored-text sweep is structurally blind to an extraction-rung card; 2 of 5 chunks run anyway at 0) | review in flight at death; **nothing in repo → NOT REVIEWED** | **privacy fix first**: §DC3 prints two exact archive `eligible_deposits` figures (the batch-7 BLOCK class) → state as a class; then hostile review; the TRAIN owes `OCR_STAGE_VERSION` 3→4 |
| 11 | HYGIENE-8 | `wave8-hygiene8` @ `dbd9a7e` | **PARTIAL** — 3 of 10 sub-cards | 0 expected. DONE: QUEUE-SUPERVISOR (`app.py` try/finally + re-arm, 344-line test), RAISE-PRIVACY-3 (5 listed sites + a 6th found by the poison set; OverflowError contract closed on all 11 `date_tokens` entry points), EXTRACT-PROMPT (insurer name + 5 constants out; `extract.py` out of `PATTERN_SCAN_EXEMPT`). NOT STARTED: SIBLING-OMISSION-SURFACE, REFUSAL-CLASS, DETECT-BUDGET-GATE, CURRENCY-CONTRADICTION, ZERO-ACTIVITY-MONTH, CHASE-SAVINGS-MARKER, ATB-LABEL | none in repo (no W3 section, no suite/gate/sweep line) | none | split: land the 3 as HYGIENE-8a (one proof-floor + record session, then review); re-card the 7 — DETECT-BUDGET-GATE first, it is the wave-level MAJOR and gates the composed slice |
| 12 | SCAN-HYGIENE | `wave8-scanhyg` @ `e4dcf9c` | **RECORD-MISSING** — all 5 sub-items implemented | 0 validated. SS-UNIQUE-MATCH, SS-GRID-AMOUNTS (the southside grid becomes an amount oracle), the citizens section-total note, SCAN-DAY-GLYPH (shared helper; EQ Bank +2 did NOT move — 5 unmoved), EQ Bank residues (closing edge conditional on its evidence, `closing_accrual_contradictions` registered, monotonicity residual pinned as a test) + the clone-guard hole closed (guards 253); TG9/TG10 not implemented, as ordered | family replays in commit bodies only; no W3 section, no suite/gate/sweep/mutation table | none | one session: proof floor + W3 record + name the SS payload movers; then hostile review |

## Batch total, if everything composes as claimed

Validated: 14 (merged) + 17 + 11 + 8 + 46 + 5 + 11 + 17 = **+129 → 2,598 (76.9%)**,
plus +9 withheld (frost), +1 review +1 withheld (coreenc), 12 → `parser_declined`
(glance 3, lili 9). Zero regressions expected; the only pinned movement anyone
has measured is one diagnostic leaf (WITHHELD-GRIDS) and five analysis-INPUT
rotations with no verdict movement (DESC-COLUMNS).

## What the train owes (composition; deterministic where possible)

1. Registry pins by hand: 75 → 77 (train8 today) + coreenc 1 + welch 1 + lili 1 + frostozk 2 + glance 1 = **83** (and check whether scanhyg's `parser_registry_entries.py` hunk registers a parser or only a flag); conformance fixtures and guard counts follow (252 → 253 scanhyg + the welch/lili guards).
2. `ANALYSIS_STAGE_VERSION` 15 → 16 (new registrations; DESC-COLUMNS changes analysis input). `OCR_STAGE_VERSION` 3 → 4 (DESC-COLUMNS) — the cold run re-OCRs; budget hours for it.
3. Cross-cell interactions to measure at the composed tree: coreenc × desccols (7 counted shas expected to move); welch's `8CCAE7DD` against coreenc's furniture refusal (exactly one claimant); glance's `wilson_muir` supersedes edge; scanhyg's `date_tokens.py` hunk against hygiene8's `date_tokens.py` hunk (both touch the file).
4. `merge_one.py` byte-exact W3 rebuild (train7 scratchpad) — copy into the repo's tooling so it survives sessions.
5. Composed slice on an idle host (the detect-budget ruling); full suite; gate; cold run vs `356a4269` with `--fail-on-regression`; remote CI conclusion read and recorded.

## Records damaged by the redaction pass (`cc64232`)

The census's `content_sha256` lists and expected-yield columns were
over-redacted (`[long digit run redacted]` inside hex shas; `[amount redacted]`
in the expected column). Populations must be re-derived from the run of
record — every cell already does. Regenerating the census from
`census_merged.json` with a sha-aware redactor is parked.

## Loose ends (housekeeping, after the train)

Main checkout: 10 untracked batch-5 logs (`compare_b4_b5.txt`, `discovery_batch5_*`, `dryrun_b5.txt`, `sweep-*.log`) — delete. Sixty merged worktrees from waves 3–7 are still registered (OneDrive locks make every `git worktree` call noisy) — prune. Batch-9 P0 stays FIXTURE-PRIVACY (a real account number in `tests/test_analysis.py` since written).

## Open Gustavo rulings (unchanged)

L-1 multi-account (~70 docs incl. 4 CU families + Space Coast + LILI's 3) · CONS-L1 · EQ Bank TG9+TG10 · ATB ceremony + R3 · TRU-SAVINGS · FROST-PERIOD (new) · the Lili tampering finding · DESC-COLUMNS priority (moot: built).
