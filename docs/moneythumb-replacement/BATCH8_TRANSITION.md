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
| 2 | WELCH | `wave8-welch` @ `e02ed12` (prod `61b4292`) | **CLOSED + VERIFIED (train-ready)** | +17 validated (`welch_state_bank`; the 17th is the rank-1 verifier's "misfile" `8CCAE7DD`) | suite 5,930 · gate GREEN · 22/27 mutants (5 algebraically redundant, pair mutants kill) · sweep 17 = named · privacy 4,889 literals / 0 | APPROVE W/F — 1 MAJOR wave-level (detect budget within 3% of ceiling at 76 regs → HYGIENE-8 DETECT-BUDGET-GATE), 5 MINOR; closures `61b4292` / `5f95cbc` | pytest 1,155 EXIT=0 · harness 28/33, five disclosed as algebraically implied (M04/M07/M11/M12/M17), 0 undisclosed, EXIT=0 · replay 17/17 validated, 3,501 postings, 353 daily balances EXIT=0 · shared scan 0/0/0 — Ocean re-ran 2026-08-26 | closure acceptance (read the two closure commits) → train |
| 3 | LILI | `wave8-lili` @ `7e1e71d` | **CLOSED + VERIFIED (train-ready)** | +11 validated (`lili`); 9 named refusals: 5 §INTEGRITY (tampering signature), 3 §L-1 (convert on the ruling), 1 summary≠ledger | suite 5,919 · gate GREEN · 36 mutants / 35 killed + 1 equivalent · sweep · privacy EXIT=0 | APPROVE W/F — 2 MAJOR, 3 MINOR; closures `b1ba3c2` + docs | pytest 1,039 EXIT=0 · harness 36 mutants / 35 KILLED / M10 documented EQUIVALENT (tool exits 1 on any survivor) · replay EXIT=0 · shared scan 0/0/0 — Ocean re-ran 2026-08-26 | closure acceptance → train; tampering finding + the L-1 three to Gustavo |
| 5 | FROST-OZK | `wave8-frostozk` @ `9ebac02` | **CLOSED + VERIFIED except the harness** | +8 validated (`bank_ozk`) **+9 withheld** (`frost`: no printed period; the FROST-PERIOD packet says 6/9 would validate under a derived period) — never "+17" | suite 5,976 · gate GREEN · 39/41 (2 provably redundant) · sweep · privacy re-run CLEAN | **BLOCK** (heredoc-written privacy regexes carried 0x08 → inert scan → 5 real archive dates in tests/comments) + 2 MAJOR + 6 MINOR; closures `9ebac02` | pytest 1,184 EXIT=0 · replay 8 validated / 9 withheld EXIT=0 · shared scan 0/0/0 — HARNESS NOT COMMITTED (39/41 table unverifiable) → commit before the train — Ocean re-ran 2026-08-26 | re-verify the BLOCK closure by byte-checking the frostozk instruments and re-running the scan → train; FROST-PERIOD ruling packet to Gustavo |
| 8 | WITHHELD-TD | `wave8-withheldtd` @ `47a07fc` | **CLOSED + VERIFIED (train-ready)** | +11 withheld→validated (td_canada_native 6, td_canada_french 4, td_us 1) + 3 non-verdict; pinned TD byte-identical, no ceremony | suite 5,903 · gate GREEN · 16/16 · sweep 14 = named | APPROVE W/F — 2 MAJOR (27 row-level sign corrections mis-stated; count-blind ties now refuse), 6 MINOR; closures `fcdc1a5` .. `47a07fc` | pytest 189 EXIT=0 · harness EXIT=0 · shared scan over 124 TD claimants 0/0/0 — Ocean re-ran 2026-08-26 | closure acceptance → train |
| 1 | CORE-ENCLOSURES | `wave8-coreenc` @ `0ef347d` | **CLOSED + VERIFIED (train-ready)** | **+46 validated**, +1 review, +1 withheld (48 of 58); 6 decline at the ledger, 4 never claimed; 13 claimed outsiders all decline (named by sha in C2.1); registry +1 with 3 supersedes edges (`burke_herbert`, `farmers_merchants`, `linkbank`) | suite 5,917 (cell) · gate GREEN (cell) · **harness committed: 40 applied / 37 killed / 3 disclosed** · reach 67 = 54 + 13 · privacy 0/0/0 over all 67 | APPROVE W/F (`a87c988`; 0 BLOCK, 3 MAJOR, 5 MINOR) → nine closures `8416437`..`0ef347d`; **Ocean re-ran**: pytest 1,168 EXIT=0, harness EXIT=0, reach EXIT=0, shared scan EXIT (money 0 / dates 0 / digits 0; round-fixture collisions `235.00`/`81.00`/`1/01/26` adjudicated invented); production code AST-equal since the review (docstrings + the count entry's description only) | train |
| 6 | GLANCE | `wave8-glance` @ `9bbdc55` | **CLOSED + VERIFIED (train-ready)** | +5 validated (`category_partition`), 3 → `parser_declined` by the card's own refusal; supersedes edge from `wilson_muir` (14 docs byte-identical; the ONE pinned `wilson_muir` document `6EFD091D` is claimed and kept on the issuer reader by the edge — no pinned movement) | suite 5,950 (cell) · gate GREEN (cell) · **harness committed: 38 killed / 3 controls / 0 survivors** · probe 3,351 → 22 → 8 sole → 5 publish · privacy 0/0/0 | APPROVE W/F (`0e7f616`; 0 BLOCK, 2 MAJOR, 5 MINOR) → seven closures `8699457`..`9bbdc55` (§GL12); **Ocean re-ran**: pytest 1,079 EXIT=0, harness EXIT=0, family replay EXIT=0, shared scan 0/0/0; only `_sectioned_rows` changed in code since the review (now refuses a contradicting row mark) | train (archive sweep owed at the train) |
| 7 | CP-SECTIONED-SCAN | `wave8-cpscan` @ `7945631` | **CLOSED + VERIFIED (train-ready)** | 0 — ceiling 0 of 19, every refusal honest and named; 3 grammar corrections on the two shared readers; blast radius 135 docs / 2,472,199 leaves / 0 moved, dispatch 59/59 identical | suite 5,894 (cell) · gate GREEN (cell) · **harness committed: 19/19 killed** · census/ceiling instruments committed; the bespoke privacy grep RETIRED (vacuous zero) | APPROVE W/F (`83a9cff`; 0 BLOCK, 2 MAJOR, 5 MINOR — both MAJORs privacy: an archive place token in a fixture, the inert grep) → nine closures `d931b30`..`7945631` (§CPS12); **Ocean re-ran**: pytest 236 EXIT=0, harness 19/19 EXIT=0 (tree clean after), census 59 EXIT=0, shared scan over the 59: money 0 / dates 0 / digits 0 (4 record-prose bigrams); both readers AST code-equal since the review (docstrings only) | train; CPS-ZEROTOTAL → Gustavo |
| 9 | WITHHELD-GRIDS | `wave8-withheldgrids` @ `944c2e9` | **CLOSED + VERIFIED (train-ready)** | **+16 withheld→validated** (was 17: `595137FD` withheld again, honestly); 6 stay withheld (pnc ×4, wells `A4E41C80`, `595137FD`); `adb.py` byte-identical to base; the source posting-date rules tightened until archive-wide real-day loss is 2 (both named, money-proximity); grid refuses a disagreeing repeated date (129 → 0 contradicting cells, 4/4 grid movers kept); ONE pinned diagnostic leaf moves (`413AD4C2` ibc `source_posting_days` — accepted as non-ceremony, see the ruling) | suite 5,875 (cell) · gate GREEN (cell) · **harness committed: 14/14 killed** · srcdates audit committed · leaf diff committed | APPROVE W/F (`f97b3d2`; 0 BLOCK, 4 MAJOR, 7 MINOR) → eleven closures `dc0b07e`..`944c2e9` (§WG12), two ruled deviations accepted; **Ocean re-ran**: pytest 289 EXIT=0, harness 14/14 EXIT=0 (tree clean after), srcdates audit EXIT=2 by design (2 named residuals; 2,558 resolved; empty-with-ledger 426 → 431 named), leaf diff over 429 docs EXIT=0, shared scan 372 docs 0 identifying | train; SRCDATE-EMPTY-SET → Gustavo |
| 10 | DESC-COLUMNS (P1) | `wave8-desccols` @ `ef66d2a` | **CLOSED + VERIFIED (train-ready)** | 0 verdict movement; the native-text rung with the fail-closed furniture gate (G9) and the never-raise guard: 83 claimed / **6 payload movers** (incl. `91A2DE99`, the MCA credit restored) / 0 raises; on the 7 counted documents exact descriptions 138 of 269 (shipped 75), 0 FOREIGN, 0 furniture tokens; **pinned: 3 claimed, 0 leaves moved** (the diagnostic leaf moves are gone) | cell: suite 5,881 · gate GREEN · movement 3,380 · **harness committed: 15 killed / 1 disclosed** · fallback 131/131 identical | APPROVE W/F (`5258a68`; 0 BLOCK, 1 MAJOR, 7 MINOR) → closures `3114ea2`..`ef66d2a` (§DC12); **Ocean re-ran**: pytest 113 EXIT=0 (branch tests + hardcode + repair guards), harness EXIT=0 tree clean after, pinned 3/0/106 EXIT=0, fallback 131 identical / 0 different EXIT=0, shared scan complex-31 0/0/0/0; only `ocr/native_text.py` changed since the review | train (OCR v3→4 bump at merge; DESC-COLUMNS-2 carded) |
| 11 | HYGIENE-8 | `wave8-hygiene8` @ `dbd9a7e` | **PARTIAL** — 3 of 10 sub-cards | 0 expected. DONE: QUEUE-SUPERVISOR (`app.py` try/finally + re-arm, 344-line test), RAISE-PRIVACY-3 (5 listed sites + a 6th found by the poison set; OverflowError contract closed on all 11 `date_tokens` entry points), EXTRACT-PROMPT (insurer name + 5 constants out; `extract.py` out of `PATTERN_SCAN_EXEMPT`). NOT STARTED: SIBLING-OMISSION-SURFACE, REFUSAL-CLASS, DETECT-BUDGET-GATE, CURRENCY-CONTRADICTION, ZERO-ACTIVITY-MONTH, CHASE-SAVINGS-MARKER, ATB-LABEL | none in repo (no W3 section, no suite/gate/sweep line) | none | split: land the 3 as HYGIENE-8a (one proof-floor + record session, then review); re-card the 7 — DETECT-BUDGET-GATE first, it is the wave-level MAJOR and gates the composed slice |
| 12 | SCAN-HYGIENE | `wave8-scanhyg` @ `eb361b1` | **CLOSED + VERIFIED (train-ready)** | 0 validated; 8 withheld payload movers (flags/notes/risk/quality only); EQ +2 refused by the evidence gate; TG9/TG10 untouched; **pinned 109: 0 movement** | §SCANHYG + §SH13: tests 256 · guards **254** · conformance 1,164 at registry 75 · harness 32 / 28 killed / 4 disclosed equivalents · family replay 47 · pinned replay 109/108/0/1 · privacy added-lines 0/0/0 | APPROVE W/F (`f0266b1`; 0 BLOCK, 1 MAJOR, 5 MINOR) → closures `f03bb5d`..`eb361b1`: 14 inherited archive figures in nine comments restated (AST-identical), the false universal narrowed, the day gate's non-evidence-backed widening tightened AND the lost base derivation restored (0 archive movement), K3 pinned, any non-zero grid disagreement flags (`_GRID_CELL_EPSILON`), bookkeeping; only `daily_grid_amount_contradictions` and `_resolve_dates` changed in code since the review (AST) | train (Ocean re-ran: tests 256, guards 254, harness 32/28/4, family replay 47 → 33 identical / 8 payload / 0 outcome / 41/41 run-of-record, pinned replay 109/108/0/1 findings [] — all EXIT=0) |

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

Main checkout: the 10 untracked batch-5 logs (`compare_b4_b5.txt`, `discovery_batch5_*`, `dryrun_b5.txt`, `sweep-*.log`) were moved to the 2026-08-28 session scratchpad (`batch5-logs-moved/`), not deleted — delete when convenient. Sixty merged worktrees from waves 3–7 are still registered (OneDrive locks make every `git worktree` call noisy) — prune. Batch-9 P0 stays FIXTURE-PRIVACY (a real account number in `tests/test_analysis.py` since written).

## Open Gustavo rulings (unchanged)

L-1 multi-account (~70 docs incl. 4 CU families + Space Coast + LILI's 3) · CONS-L1 · EQ Bank TG9+TG10 · ATB ceremony + R3 · TRU-SAVINGS · FROST-PERIOD (packet UNVERIFIED — W3 §FZ14; the ruling may not cite "6 of 9") · the Lili tampering finding · DESC-COLUMNS priority (moot: built).

## Progress log (append-only; newest last)

- 2026-08-26 GO on (1) from Gustavo. Operating model: max two concurrent expensive sessions; hostile reviews commit their record to `docs/moneythumb-replacement/reviews/BATCH8_<CELL>_REVIEW.md` on the cell branch; closures are a separate focused session; Ocean verifies closures deterministically.
- 2026-08-26 DESC-COLUMNS privacy redaction landed `376d4de` (six exact archive figures in §DC3.3 → classes); 0 amounts-with-cents remain on the branch's added lines. Pre-scan: glance/scanhyg fixture figures to be checked against document text by their reviewers; scanhyg quotes a four-figure discrepancy in a production comment (restate). scanhyg's registry hunk = `integrity_checks` on 3 existing registrations only (composed registry stays 83); hygiene8 × scanhyg `date_tokens.py` hunks merge clean.
- 2026-08-26 CORE-ENCLOSURES hostile review → **APPROVE WITH FINDINGS, 0 BLOCK, 3 MAJOR, 5 MINOR** (record `a87c988`; its verdict line mis-tallies 2/6). Held: reach 67/3,380; 46/1/1/6/4; 13 outsiders publish nothing; pinned linkbank document byte-identical; 6,971 money leaves all printed (repair doctrine); DESC-ATTRIB class absent; no collision with the coreiss2 siblings incl. all 77 train8 fixtures; no archive literal. Open: a fee-row count in shipped source (13/1 written, 19/2 measured); mutation harness uncommitted, no per-mutant table; two live `_grid` duplicate-day gates unpinned; six bounds survive removal; replay instrument reads a key `report_to_dict` never emits; the 13 outsiders unnamed; four headline counts without committed instruments. Closure session launched on the branch.
- 2026-08-26 WITHHELD-GRIDS hostile review running.
- 2026-08-26 WITHHELD-GRIDS hostile review → **APPROVE WITH FINDINGS, 0 BLOCK, 4 MAJOR, 7 MINOR** (record `f97b3d2`). Held: 17/17 flip by a check PASSING (none by skip); 0 new publishes outside the 17; 0 raises; recomputed base == run-of-record payload 549/549; 0 source-date gains over 1,163 docs; pinned movement exactly one diagnostic leaf on `413AD4C2` (ibc), verified over all 109, read by no required check and absent from `corpus_gate.py`. Open: the "removal-only" rules remove 27 REAL posting days on 23 validated docs and leave 21 docs with an empty source set (check-power regression); the page-header rule's bound is wrong; the removed account number still sits twice in `docs/balance-metrics-audit-results.csv` on main (pre-existing, truth-set file → Gustavo); harness uncommitted; a "dead" rule was live; a repeated grid date resolves last-wins. OCEAN RULINGS for closure: rules may not remove a real posting day (tighten to 0 archive-wide or name residuals; a lift that needed a real-day removal is not a lift); repeated grid date with disagreeing balances → REFUSE (never choose); no audit-CSV edits by cells. Closure session launched.
- 2026-08-26 Shared instrument `tools/privacy_scan_branch.py` committed on main (`01d7bc4`): population shas → MONEY/DIGITS/DATES/WORDS literals from cached text by direct path → grep of a branch's added lines with file:line; base-tree exclusion; self-check refuses to run inert (the 0x08 lesson). Calibration: welch 0/0/0/0 over 2,172 money literals (matches its record). **FROST-OZK BLOCK closure ACCEPTED**: its own scan was never committed; the shared scan over its 17 documents against `10cc722...wave8-frostozk` → money 0 / dates 0 / digit runs 0; 4 WORD bigrams, all template furniture ("STATEMENT UPON", "UPON RECEIPT", "TRANSACTIONS SERIAL", "FROST WITHDRAWAL"). Rule from here: every branch is scanned with this tool before the train, and the train tree is scanned over every population it merged.
- 2026-08-26 Shared privacy scan over the CLOSED cells (base `10cc722`, added lines, all classes): **WELCH** 0/0/0/0 (17 docs, 2,172 money literals) · **FROST-OZK** money 0 / dates 0 / digits 0, 4 furniture bigrams (17 docs) · **LILI** money 3 (two fee-sized figures in tests, `46.33`-class), dates 0, digits 0, 7 furniture bigrams (20 docs) · **WITHHELD-TD** 0/0/0 over 124 TD claimants (8,100 money literals), 27 word hits = OCR-garbled column headers the scanned reader matches on + its own declared-furniture list · **CORE-ISSUES-2 (merged on train8)** dates 0 / digits 0, **27 MONEY hits = four two-digit fee-sized figures** (`analysis/core_processor_signed_counts.py` docstring example ×3 lines; the two test files; one conformance fixture) that one of the 14 documents also prints, + 5 furniture bigrams. Classification: low-magnitude collisions, not the batch-7 class (no balance, date, name, account) — but the train replaces them anyway. **TRAIN FIX-LIST:** coreiss2 four figures (26.43 / 6.29 / 3.71 / 13.07) and lili two (46.33 / 13.42) → values the populations do not print, fixture totals re-balanced, cell tests re-run. Closure acceptance for WELCH/LILI/FROST-OZK/WITHHELD-TD is now instrument-backed on privacy; the substantive closure verification (each MAJOR closed as the review asked: harness + tests + family replay per branch) is ONE focused session scheduled after the review queue, covering all CLOSED cells at once.
- 2026-08-26 Shared privacy scan over the NOT-YET-REVIEWED branches (base `10cc722`, added lines): **SCAN-HYGIENE** 0/0/0/0 (38 docs: southside, EQ Bank, citizens, texas_first claimants) · **DESC-COLUMNS** 0/0/0/0 (31 docs: the 8 named + the sectioned/daily complex) · **CP-SECTIONED-SCAN** money 0 / dates 0 / digits 0, 2 furniture bigrams (27 docs) · **GLANCE** money 0 / digits 0 but **DATES 65** — six September statement dates of the family's own period repeated through `tests/test_category_partition.py` and its conformance fixture (the FROST-OZK BLOCK class). Fixed BEFORE review: every fixture date moved to 2031 (a year the archive cannot contain), 89 glance tests unchanged, re-scan DATES 0 (`9ea7d78` on `wave8-glance`). **HYGIENE-8** scan running detached (its chase population is ~300 docs; exceeded the 10-minute tool window inline).
- 2026-08-26 **CORE-ENCLOSURES CLOSED + VERIFIED.** Closure session landed nine commits (`8416437`..`0ef347d`, W3 §C19): the fee-row count re-derived by a committed instrument (19 docs / 2 posting it as two rows), harness committed with a per-mutant table (40 / 37 killed / 3 disclosed, 0 undisclosed), the two `_grid` duplicate-day gates pinned by isolating tests, five bounds pinned + three disclosed, the replay's `parser_id` read from dispatch, the 13 outsiders named by sha (C2.1), four headline numbers re-derived, C16/C18.3 corrected. Ocean's own verification: pytest 1,168 passed EXIT=0; `tools/coreenc_mutation_table.py` 40 applied / 37 KILLED / 3 disclosed EXIT=0; `tools.coreenc_archive_census reach` 67 claimants EXIT=0; module AST code-equal to `a87c988` with docstrings stripped (the 31-line diff is docstrings; count_semantics differs only in the entry's description string); shared privacy scan over the 67: money 0 / dates 0 / digits 0 (v1) — v2's whole-token pass surfaces `235.00`, `81.00`, `1/01/26` = round invented fixture values colliding with something printed across 67 documents, adjudicated not archive-sourced.
- 2026-08-26 `tools/privacy_scan_branch.py` **v2** (`4a000e4`): symmetric whole-token matching on both sides (base tree and branch lines tokenised with the same patterns) — 5–11 s per branch instead of an hour on a 300-document population, no OCR-fragment false positives. Re-calibrated: welch 0/0/0 + 2 bigrams · frostozk 0/0/0 + 18 · lili 0/0/0 + 4 · **HYGIENE-8 over 599 documents (chase, columbia_bank, scotiabank, southside, texas_first claimants): 0/0/0 + 1 bigram** — every batch-8 branch is now scanned. Adjudication rule from today: a DATES/MONEY hit is a leak when it is a document's own period date or a figure of identifying magnitude (GLANCE's six September dates → moved to 2031); a round invented value that coincides with some printed token is recorded, not rewritten. Symmetric v2 also retires the earlier v1 "fee-sized collision" list for coreiss2/lili where those tokens exist whole in the base tree — re-measure at the train with v2 before rewriting any fixture.
- 2026-08-26 GLANCE hostile review → **APPROVE WITH FINDINGS, 0 BLOCK, 2 MAJOR, 5 MINOR** (record `0e7f616`). Held: 5 validated / 3 parser_declined end to end; base-from-blobs 14 validated / 8 no_parser_matched; 37 mutants attributed, 0 disagreements, 3 controls publish; detection probe 3,351 → 22 claimed → 8 sole → 5 publish, 0 ambiguous; 0 collision with train8 both ways; 18 adversarial texts, 0 raises; privacy 0/0/0 + 22 furniture bigrams, fixtures invented away from the family. Open: §GL8/§GL9B's archive sweep is four literal placeholders (never run); "no pinned document prints this template" is false — one pinned `wilson_muir` document (`6EFD091D`) is claimed by the new reader and kept on the issuer reader only by the supersedes edge (payload byte-identical base vs branch, so NO pinned movement); replay/both-grid/killer instruments uncommitted; a fourth sign case unnamed; `_sectioned_rows` silently discards a contradicting row mark; four record statements imprecise. **OCEAN RULING (wave-wide from today): the archive-wide zero-movement sweep is a TRAIN-level proof — run once over the composed tree by Ocean; a cell's record says so rather than carrying placeholders, and commits a detection probe in its place.** MINOR-5 closes fail-closed (refuse the contradicting mark). Closure session launched.
- 2026-08-26 **GLANCE CLOSED + VERIFIED.** Seven closures (`8699457`..`9bbdc55`, W3 §GL12): placeholders replaced by the train-owed sweep statement + a committed detection probe (3,351 / 22 / 8 / 5 / 0 ambiguous); the pinned `6EFD091D` truth stated in the record, the registry comment and the pin test, with `tools/glance_family_replay.py` committed; `tools/glance_mutation_table.py` committed (38 killed / 3 controls / 0 survivors); the fourth sign case named and pinned both sides; `_sectioned_rows` refuses a contradicting mark (0 of 22 move); direction totals named as reader-computed sums (provenance re-measured `bank_stated_reconciled`, correcting the review); four record statements fixed. Ocean's own verification: pytest 1,079 EXIT=0; harness EXIT=0 with the tree clean after; family replay EXIT=0 (issuer documents identical base vs branch); shared privacy scan over 8 + 14: money 0 / dates 0 / digits 0 (23 furniture bigrams); AST: the only function whose code changed since the review is `_sectioned_rows`.
- 2026-08-26 WITHHELD-GRIDS closures landed (`dc0b07e`..`944c2e9`, W3 §WG12; tip `944c2e9`). **The claim shrinks 17 → 16**: `595137FD` is withheld again because its lift depended on the page-header rule, which under R2 is provably dead (identical to its own ablation on 2,558 documents) and, as shipped, removed a real printed posting day on 16 documents to buy that one lift. R1 audit (`tools/withheldgrids_srcdates_audit.py`, committed): archive-wide real-day loss **29 → 2** over 2,558 resolved documents; the two residuals (`413AD4C2` pinned ibc, `F627D7A6`) are printed posting rows whose amount sits more than three non-empty lines below the date, removed by the money-proximity requirement; the only tightening that recovers them costs four lifts (counterfactual measured). Empty-source-with-a-ledger: base 426 → branch 431, all five named (three are this card's own lifts whose entire source set was one rate-line date). R8: grid anchored on its printed column header + REFUSE on a disagreeing repeat; contradicting cells 129 → 0 over 106 documents; 4/4 grid movers kept; grid map identical on all 106; no pinned payload changes. MAJOR-2 deviation accepted (rule removed rather than conditioned — measured dead). MINOR-6 deviation accepted (the rate rule stays deleted: restoring it removes a real posting day, which R1 forbids). Harness committed: 14/14 killed. Proof at tip: pytest 289 EXIT=0 · replay 16 lifted / 6 withheld · leaf diff 552 shas: 494 identical, 28 moved, 0 raises, 0 new publishes outside the 16 · privacy 0 identifying · control bytes 0. Ocean's re-run so far: pytest 289 EXIT=0; shared scan over 372 family documents: money 2 / dates 3 (generic month-start dates and trivial figures in new `test_adb.py` cases — adjudicated invented; future fixtures dated 2031) / digits 0; harness + leaf diff + audit re-run in progress.
- 2026-08-26 **OCEAN RULING — the pinned diagnostic leaf.** `413AD4C2` (ibc) moves exactly one leaf, `metrics.adb.source_posting_days`, because a real posting day leaves its source set under the money-proximity rule; the check's OUTCOME is unchanged (the day is in `parsed_dates`, never in `missing`), the leaf is read by no required check and by nothing in `corpus_gate.py`, and the pinned verdict, integrity block and every gated field are byte-identical. This is NOT a truth-set movement and NOT a ceremony; it is accepted as a named diagnostic move, recorded here and in §WG12, with the residual's cause stated. The real defect it exposes is platform-wide and pre-existing: **SRCDATE-EMPTY-SET** — 426 documents already carry an empty source set at base, so `posting_dates_cover_source` is unfailable on one document in six today. Carded for batch 9 as a platform decision (treat `source_posting_days == 0` with a multi-row ledger as reportable) → Gustavo's list, since it would move flags on ~431 documents.
- 2026-08-26 **WITHHELD-GRIDS CLOSED + VERIFIED.** Ocean's own runs at `944c2e9`: pytest 289 EXIT=0; `tools.withheldgrids_mutation_table` 14/14 KILLED, 0 survived, 0 not-applied, tree clean after, EXIT=0; `tools.withheldgrids_srcdates_audit` over 2,558 resolved documents: real-day loss 2 (money-proximity, both named), boundary-only loss 8 (named), false days removed 1, empty-with-ledger 426 → 431 (five named), EXIT=2 by design; `tools.withheldgrids_leaf_diff` over 429 documents of the affected readers + ibc: EXIT=0 (the moved leaves on the lifted documents are the withheld-era integrity flags/notes and `metrics.adb.daily_balances` arriving; per-document listing in the proof log).notes.1; removed  metrics.adb.daily_balances; removed  metrics.adb.warnings.1. Shared privacy scan over 372 family documents: 0 identifying literals.
- 2026-08-26 DESC-COLUMNS hostile review → **APPROVE WITH FINDINGS, 0 BLOCK, 1 MAJOR, 7 MINOR** (record `5258a68`). Held: movement over 3,380 = 76 claimed / 21 moved (7 counted + 14 `source_posting_days`-only) / 0 raises; required-check vector over the 76: checks, flags, notes, risk, outcome, reconciliation, `posting_dates_cover_source` and every ADB value UNMOVED — only `transactions[].classification.*` and `source_posting_days`; fallback vs base blob 132/132 identical; tokens conserved on the 7 (18 contiguous regions); oracle 252/17/0 FOREIGN; the stored-text sweep's blindness reproduced (`analysis.pipeline` + registry import zero `ocr`/`webapp` modules; `descattrib_movement` over the complex's 31 = 0 moved); pinned 109: 5 claimed / 104 not, 0 outcome movement, 2 byte-identical, **3 move `.metrics.adb.source_posting_days` only** — gated by nothing (`corpus_gate._Verdict` :202–214; both audit CSVs and `parser_expectations.json` name it 0 times). Open: (MAJOR) page furniture sharing a ledger row's band lands inside a published description — the DESC-ATTRIB harm class re-created at the rung, invisible to the DC3.1 oracle; (MINOR, closing as must-fix) a malformed MuPDF line box RAISES out of the rung instead of refusing (exposure: every native-text document); G3's right-edge clause and `_ROW_MONEY_RE` unpinned; the `source_posting_days` ↔ `posting_dates_cover_source` coupling unnamed; stale DC8.1/DC7/DC11 numbers; gate renumbering; sweep coverage 2,000/3,380 to be stated; the OCR v3→4 bump is the train's. Privacy: complex-31 0, pinned-5 0, claimed-76 8 collisions all adjudicated non-document (suite runtimes, ordinary fixture tokens, an English bigram). **OCEAN RULINGS:** fail closed on repeated page furniture (a band line printing on another page at the same band, or outside the column extent → the band refuses; measured over the 76 and the 7, with an oracle mode that can see the class); the rung may never raise (six malformed shapes refuse; fallback identity re-proved); the three pinned leaf moves accepted as named diagnostics, not a ceremony (same ruling as WITHHELD-GRIDS'). Closure session launched.
- 2026-08-26 CP-SECTIONED-SCAN light review → **APPROVE WITH FINDINGS, 0 BLOCK, 2 MAJOR, 5 MINOR** (record `83a9cff`). Held: blast radius over 135 documents (the complex's 59 + the 80 in-run pinned incl. this complex's 4) and 2,472,199 leaves = 0 docs / 0 leaves / 0 exception changes, each hunk ablated to 0; dispatch 59/59 identical; the 154 leading-zero rows reproduce on 10 documents, all failed/unclaimed, 0 rows lost; ceiling 0 of 19 with a named disagreeing check each; 18/18 mutants; guards 252. Open — both MAJORs are privacy: a printed city+state token from one of the cell's own 19 documents sits in a new fixture (`tests/test_core_processor_daily.py:375`), and the cell's bespoke `cpscan_privacy_grep` returned 0 on the identical diff because its phrase pattern is greedy across all-caps runs and its word floor drops 7-letter place names (the shared instrument returns 5 on the same 19 — Ocean's pre-scan had used the 4 named + the complex, not the 19). MINORs: §CPS9 offsets, the glyph docstring's positional over-claim (the printed-count check is the guard), the `|` exclusion's wider narrowing unrecorded, the bound-only mutant absent, the two sibling readers' glyph divergence unpinned. **OCEAN RULINGS:** the token is replaced by the module's own placeholder; the bespoke grep is RETIRED (deleted) and the record cites the shared instrument's run — from today no cell ships its own privacy grep; the divergence is pinned, not unified; CPS-ZEROTOTAL (totals that lost their decimal point) stays REFUSED and is carried to Gustavo. Closure session launched.
- 2026-08-26 **CP-SECTIONED-SCAN CLOSED + VERIFIED.** Nine closures (`d931b30`..`7945631`, W3 §CPS12): the leaked place token replaced by the module's own placeholder; `tools/cpscan_privacy_grep.py` deleted and the record restated from the shared instrument (its zero recorded as vacuous); §CPS9 arithmetic re-measured; the glyph class's bound restated (the printed-count check is the guard) with the reviewer's probe pinned; the `|` exclusion's four narrowings named, all refusals (275 bars printed, 0 before a digit); the bound-only mutant added and KILLED; the sibling readers' divergence pinned, not unified; CPS-ZEROTOTAL stays REFUSED → Gustavo. Ocean's own runs at `7945631`: pytest 236 EXIT=0; `tools.cpscan_mutate` 19/19 KILLED EXIT=0, tree clean after; `tools.cpscan_census` 59 documents EXIT=0; shared privacy scan over the 59 (incl. the 19): money 0 / dates 0 / digits 0, 4 furniture bigrams in the record's prose; both readers AST code-equal to the reviewed tip with docstrings stripped.
- 2026-08-26 Closure verification of the four CLOSED cells started (deterministic half, sequential detached chain: own tests → committed harness → committed replay, tree clean before/after). Inventory found two gaps for the train: **FROST-OZK committed no mutation harness** (only `tools/frostozk_family_replay.py`; its 39/41 table is unverifiable from the repo — the coreenc/withheldgrids MAJOR class) → the closure-verification session reconstructs and commits `tools/frostozk_mutation_table.py` from the W3 table before the train; **LILI's `tools/lili_family_replay.py` reads its population from `CENSUS_BATCH8_DIGITAL.md`** (intact at the branch's base `10cc722`, sha lists damaged on main since `cc64232`) → at the train the replay takes its population from the run of record (a `--shas` file), never from the census.
- 2026-08-26 **Closure verification (deterministic half) of the four CLOSED cells — all numbers match their records.** WELCH: tests 1,155; harness 28/33 (five disclosed as implied, 0 undisclosed); replay 17/17 validated, 3,501 postings, 353 daily balances. LILI: tests 1,039; harness 35/36 + M10 equivalent; replay 0388628F8E576D31  claimed=True  failed/parser_declined   INTEGRITY: a line that begins with a date is not a posting; 22C6933C0602DDDC  claimed=True  validated/approved       PUBLISHED  postings=120. WITHHELD-TD: tests 189; harness KILLED   M17_sentence_guard_folds_case: tests/test_td_us_variants.py::test_the_overdrawn_statement_closes_on_its_own_arithmetic, tests/test_td_us_variants.py::test_the_captured_rows_reproduce_the_printed_section_subtotals, tests/test_td_us_variants.py::test_a_section_that_misses_its_printed_subtotal_keeps_the_rows_it_read, tests/test_td_us_variants.py::test_the_incomplete_ledger_then_fails_closed, tests/test_td_us_variants.py::test_a_document_whose_sections_do_add_up_is_unaffected  (5 tests). FROST-OZK: tests 1,184; replay 8 validated / 9 withheld; **no committed harness** — `tools/frostozk_mutation_table.py` is reconstructed from the W3 39/41 table by the closure-verification session before the train. Every worktree clean before and after. The substantive half (each MAJOR closed as its review asked) remains the closure-verification session's.
- 2026-08-26 SCAN-HYGIENE completion landed (`7339a11`..`24b5f8e`: four instruments, the harness, W3 §SCANHYG, the record's own privacy pass; one production change `135a719` — three comments quoting exact archive over-reads restated as classes, comment-only, replay byte-identical across it). Measured: 47 documents (citizens 21, southside 9, texas_first 8, eq_bank 5, apex 4 as shared-module control) → 0 validated movers, 0 outcome movement, 8 withheld payload movers (flags/notes/risk/quality only), base reproduces the run of record 41/41; **pinned 109 through the production ladder: 0 movement, 108 identical leaf-for-leaf incl. the integrity block, the pinned refusal identical** — the hard stop did not trigger; harness 30 mutants / 25 killed / 5 survivors disclosed (three claimed equivalent, one narrow reach, one real narrow gap K3 left for review). Hostile review launched.
- 2026-08-26 SCAN-HYGIENE hostile review → **APPROVE WITH FINDINGS, 0 BLOCK, 1 MAJOR, 5 MINOR** (record `f0266b1`). Held: pinned 109 replayed in full — 108 identical leaf-for-leaf incl. the integrity block, the refusal identical, 0 movement; repair doctrine (zero writes to any statement attribute in the new functions); the grid is an oracle, never a source (ledger fingerprint identical between clean and flagged grids); `adb.py` untouched, TG9/TG10 genuinely unimplemented; registry hunks add `integrity_checks` only; the clone detector fires on nothing innocent across 89 modules; review→high on withheld documents is a quality label from unmodified shared policy. MAJOR: `analysis/citizens.py:206` and `:297` — inherited from base — state archive figures exactly (a pre-existing leak on main, invisible to added-lines scans), so the branch's new "everywhere else a class" sentence is false. MINORs: the privacy run's line count not at the tip; the day gate is non-monotone (6 same / 3 stricter / 1 wider, 0 archive movement) and the record names only the narrowing; K3 (the clone guard's bound) is pinnable (6 caught / 7 documented miss); the grid oracle's ±1-cent resolution undocumented; bookkeeping. **OCEAN RULINGS:** redact the inherited figures (comment-only, AST-identical, replay byte-identical) and run the shared scan `--include-tree` over the five readers' claimants — owned-file hits fixed, unowned hits listed for the train; both gate directions pinned (the wider case only if evidence-backed, else tightened); K3 pinned; a printed daily cell disagreeing by ANY non-zero amount is a contradiction (tolerance 1e-6), measured over the 9 southside documents. **NEW TRAIN OBLIGATION:** a whole-tree privacy scan (`--include-tree`) over the composed tree for EVERY merged family's population — inherited archive figures in production comments are a main-tree problem the branch scans cannot see. Closure session launched.
- 2026-08-26 Whole-tree scan preview on `train8` (the composed tree so far) for CORE-ISSUES-2's 14 documents, `--include-tree`: **money 0 / dates 0 / digit runs 0 over 214,345 tracked lines**, 16 furniture bigrams in the cell's own files, 26 s. The v1 substring-era "27 fee-sized collisions" for coreiss2 do not exist under whole-token matching (those figures sit whole in the base tree) — that fix-list item is RETIRED; lili's two are re-measured the same way at the train. The train's per-family tree scan costs ~30 s per family.
- 2026-08-26 **Whole-tree privacy scan (`--include-tree`) of every verified branch over its own population** (25–31 s each): WELCH 17 docs 0/0/0 · FROST-OZK 17 0/0/0 · LILI 20 0/0/0 · GLANCE 22 0/0/0 · CP-SECTIONED-SCAN 59 0/0/0 · WITHHELD-TD 124 0/0/0 · CORE-ENCLOSURES 67: money 16 / dates 10, all occurrences of the round fixture values already adjudicated (`235.00`, `81.00`, `1/01/26`) in its own test file, conformance fixture and record · WITHHELD-GRIDS 372: money 2 / dates 4, the generic month-start dates and trivial figures in `tests/test_adb.py` and the record. **No inherited archive figure from these eight populations exists anywhere else in their trees** — the `citizens.py` class found by the SCAN-HYGIENE review is confined to the scanned families, whose closure is redacting owned files and listing unowned ones. Train collision pass (optional, cosmetic): move coreenc's `1/01/26` and withheldgrids' June-2026 fixture dates to 2031 for consistency with the batch convention.
- 2026-08-26 DESC-COLUMNS closures landed (`3114ea2`..`ef66d2a`, W3 §DC12; 51 commits from base, 10 files, 0 deletions). **R-F3's fail-closed furniture gate has a measured price:** region-level refusal (the only granularity the gate structure supports) refuses 1,506 of 2,639 admitted regions over 3,380 documents; movers 21 → **6** (kept incl. `91A2DE99`, the MCA-credit document; lost: 2 counted + 13 of 14 single-leaf movers); claimed 76 → 83 net (45 lost, 36 gained: a refused region is one no block can straddle, so G6 stops refusing documents outright); on the 7 counted documents exact descriptions 252 → **138 of 269 (shipped: 75)**, 0 FOREIGN, all 39 `replaced` leaves gone; the new oracle mode finds 0 published tokens outside the date→amount span and 0 flagged. The honest split: archive-wide 46% of repeated lines recur on ≥3 pages (real furniture), but on this complex all 93 recur on exactly 2 pages with 1–2 tokens — the gate pays mostly for probable coincidence it cannot separate. R-F8: nine malformed shapes refuse to the page's own flattening, catch-all guard, fires on 0 of 3,380 pages; fallback vs base blob 131 identical / 0 different. **Pinned: 3 claimed, 0 leaves moved** — the three diagnostic leaf moves are gone; the pinned surface is byte-identical. **OCEAN DECISION:** the strict version IS the batch-8 deliverable — fail-closed, 0 FOREIGN, +63 exact descriptions over shipped, the rung can no longer raise, no pinned movement of any kind. The furniture DISCRIMINATOR (same x-extent, ≥3-page repeats, page-number shape; the 93 two-page lines as its evidence) is carded as **DESC-COLUMNS-2** for batch 9 — measured, not argued. Gustavo: the P1 value is partially delivered by design; say if the discriminator should jump the queue.
- 2026-08-26 **DESC-COLUMNS CLOSED + VERIFIED.** Ocean's own runs at `ef66d2a`: pytest 113 EXIT=0 (`test_native_rung_parity`, `test_printed_row_extraction`, `test_no_statement_hardcodes`, `test_repair_guard`); `tools.desccols_mutate` 15 KILLED / 1 disclosed survivor, EXIT=0, tree clean after; `tools.desccols_proofs pinned`: 3 claimed (`E5804DBB`, `F748A799`, `408711BD`), 0 leaves moved, 106 not claimed, EXIT=0; `tools.desccols_proofs fallback --stride 23`: 147 sampled, 6 claimed, **131 analysis-input-identical, 0 different**, 10 no native text, EXIT=0; shared privacy scan over the complex-31 + the 8 named: 0/0/0/0; only `ocr/native_text.py` changed since the review. The 3,380-document movement run (~30 min) is not re-run here — the OCR v3→4 cold run at the train re-derives it for every document.
- 2026-08-26 **Train8 merge preview** (`git merge-tree --write-tree` of every branch against `train8` = `f7a6cce`): **no production-file conflicts**. Every branch conflicts on `docs/moneythumb-replacement/W3_TRACKA_LOG.md` only (expected: the log is rebuilt byte-exact from branch sections by `merge_one.py`, the batch-7 method), and the five registration-adding cells (coreenc, welch, lili, glance; frostozk on the registry test only) additionally on the registry-count pins in `tests/test_parser_registry_entries.py` / `tests/test_parser_conformance.py` — composed by hand: 75 → 77 (train8) + 1 + 1 + 1 + 2 + 1 = **83**, conformance 83×82. hygiene8 merges clean today (it gains a W3 section from its completion session). Shared production files across branches, all non-conflicting hunks: `parser_registry_entries.py` (7 branches), `corpus_gate.py` (5: excused analysis callers), `count_semantics.py` (3), `stated_counts.py` (2: `OBSERVER_VERSION` bumped by frostozk 5→6 and by welch? — compose to one bump), `scanned_small_bank.py` + `date_tokens.py` (scanhyg × hygiene8, disjoint hunks). Composition order (least to most entangled): withheldtd → withheldgrids → cpscan → desccols → scanhyg → hygiene8 → welch → lili → frostozk → glance → coreenc, re-running each cell's own tests after its merge and the canonical guard + conformance sets after the registry composition; then v16 + OCR v4, the full suite, the gate, the idle-host corpus-marked slice, the single archive sweep, the per-family whole-tree privacy scans, the cold run vs `356a4269` with `--fail-on-regression`, remote CI conclusion read.
- 2026-08-26 Train composition details: (1) `telemetry/stated_counts.py` — welch AND frostozk each bump `OBSERVER_VERSION` 5 → 6 and each add entries in the same hunk (`@@ -176`); the second merge conflicts there → hand-merge both entry sets, ONE bump to 6 (both observer changes land in the same train). (2) `merge_one.py` (batch-7 helper, now in this session's scratchpad `train8/`) asserts `ours.startswith(base)` on the W3 log; the redaction commits `cc64232`/`bbeeb5c` edited earlier sections on main, so that assertion no longer holds for `train8` — the train uses **v2**: rebuild = ours + `theirs[len(base):]`, asserting only `theirs.startswith(base)` (which also catches any cell that damaged another cell's section). Commit v2 as `tools/train_merge_one.py` at the train so it survives sessions. (3) `OCR_STAGE_VERSION` 3 → 4 and `ANALYSIS_STAGE_VERSION` 15 → 16 are one composed commit after the last merge, before the proofs.
- 2026-08-26 SCAN-HYGIENE closures landed (`f03bb5d`..`eb361b1`, W3 §SH13). **CORRECTION to the whole-tree scan entries above:** the closure session showed that `--include-tree` with `--base 10cc722` is structurally BLIND to inherited tokens — the base-tree exclusion removes exactly the tokens that already sat in the tree — so the "six families clean" tree results and the coreiss2 214k-line preview only proved that no NEW archive token was added; they say nothing about inherited ones. Re-run against the repository's ROOT commit as base (no exclusion), the unowned residue over the scanned families' documents, after dropping WORDS, round `.00` figures and the 12 `tests/corpus_cache/` fixture files (842 hits, archive text by design), is **98 files / 861 candidates**: `analysis/` 19 files / 34, `tests/` 62 / 670, `docs/` 13 / 152, `tools`+`ocr`+`webapp` 4 / 5; W3 154 (0 inside §SCANHYG). That is the measured population of the batch-9 P0 **FIXTURE-PRIVACY** sweep. **Rule for the train's tree scans: base = the root commit** (`git rev-list --max-parents=0 HEAD`), per merged family, candidates adjudicated by class — a whole-tree scan with a recent base is not a scan.
- 2026-08-26 SCAN-HYGIENE — Ocean's deterministic verification at `eb361b1` (pinned replay pending): pytest 256 EXIT=0; canonical guards 254 EXIT=0; `tools.scanhyg_mutation_table` 32 applied / 28 KILLED / 4 disclosed equivalents / 0 unapplied, tree clean after, EXIT=0; `tools.scanhyg_family_replay --base 10cc722`: 47 documents (citizens 21, southside 9, texas_first 8, eq_bank 5, apex 4), 33 identical, payload movers 8, outcome movers 0, base matches the run of record 41/41, EXIT=0; AST: only `daily_grid_amount_contradictions` (R5) and `_resolve_dates` (R3) changed in code since the review; `citizens.py` comment-only. Note for the train: the cells' pinned-replay instruments read the corpus OCR cache at `tests/corpus_cache` (manifest-keyed), not `webapp_data`.
- 2026-08-26 **SCAN-HYGIENE CLOSED + VERIFIED.** `tools.scanhyg_pinned_replay --base 10cc722` at `eb361b1`: pinned 109, identical 108, moved 0, refused both sides 1, claimed by the target readers 6, findings [], EXIT=0, tree clean after. Ten branches are now Ocean-verified train-ready (coreiss2 merged; coreenc, glance, withheldgrids, cpscan, desccols, scanhyg, welch, lili, withheldtd); frostozk awaits its committed harness and the MAJOR-closure verification session; hygiene8a's completion is in flight.
- 2026-08-26 **TRAIN8 COMPOSITION STARTED.** `train8` = main (tooling) + coreiss2 + five cells, each merge followed by the cell's own tests: withheldtd `f553548` (189), cpscan `5f66f17` (238), scanhyg `9c85cf1` (256), withheldgrids `b329b60` (289), desccols `ef791fb` (113). **Two W3 shape violations caught by the helper and composed section-only:** `wave8-withheldgrids`'s log had a scripted substitution that rewrote `PRIVACY_EXIT=0` → `0=0` in FOUR other cells' proof tables (§DECLINES-era sections at base lines 30377, 30555, 34746, 36399; its own section clean); `wave8-desccols`'s log had appended two of its sweep rows to §DECLINESG's proof table and a stray separator. Both discarded at the train (`train_merge_one.py --section-only`, `736bcc1`); the branches keep their damage until deleted after the train. Lesson (third time): scripted W3 edits need UNIQUE anchors — a cell edits nothing outside its own section. Remaining: welch, lili, frostozk (after its harness lands), glance, coreenc — registry pins composed by hand to 83; hygiene8a after its completion.
- 2026-08-26 **TRAIN8 @ `164acda` — ten cells composed** (coreiss2, withheldtd, cpscan, scanhyg, withheldgrids, desccols, welch `3f8d13d`, lili `2a4a120`, glance `8ef8f8e`, coreenc `082bd48`), registry **81**, canonical guards 254 EXIT=0, canonical conformance 1,239 EXIT=0, every cell's own tests green after its merge. The helper grew two explicit modes on the way (`5c70a88`): `--compose-registry N` now resolves only the conflict hunks of the two pin tests (the first version took the whole train-side file and lost the cleanly-merged dispatch-order insertions — caught by `test_dispatch_order_is_exactly_this_list`, train rebuilt from `eb494d0`), and `--union FILE` keeps both sides of adjacent independent insertions (coreenc's three issuer edges beside glance's `wilson_muir` edge in `parser_registry_entries.py`; coreenc's excused caller beside welch's in `corpus_gate.py`). Two composition fixes on the train: `bc3eed5` (EXPECTED_ORDER carried `linkbank` twice — coreenc moves the three issuer readers to band 10 and the later removal sat inside the pin hunk) and **`164acda` — the first genuine cross-cell interaction: SCAN-HYGIENE's new clone guard fires on LILI's `_summary`.** Composed without changing LILI's semantics: its exactly-once rule moved into the shared `tables.single_match` (stricter than `unique_match` on purpose — a repeated summary term is LILI's tampering signature; 147 lili tests, 20-document replay 11 validated / 9 declined identical), and its ragged-grid check phrased against the first row because the detector reads `len({...})` beside any `.findall` as a uniqueness paraphrase (a false-positive class — **detector narrowing carded for batch 9**: require the set to be built over the enumerated matches). Remaining merges: frostozk (→ 83, `OBSERVER_VERSION` hand-merge) after its harness lands; hygiene8a after its completion. Full suite started early on `164acda` (detached).
- 2026-08-26 (session restart) **The early full suite on `164acda` failed at COLLECTION (`SUITE_EXIT=2`, seven modules): the `--union` composition of `corpus_gate.py` split welch's excused-caller tuple across the hunk boundary (its closing paren sat in shared context), a `SyntaxError` the canonical guard and conformance sets never import.** Repaired on the train (`5cc6396`); `import corpus_gate` OK, 17 excused callers. Lesson for the helper: a union hunk must be re-parsed (`ast.parse`) before it is accepted — carded for the helper's next revision. The host process then exited: the HYGIENE-8a completion and the frostozk/MAJOR verification sessions were interrupted but had landed their work — hygiene8 `4885910`..`24e3da7` (six instruments, 30-mutant harness, corrections, twelve owned-file privacy hits closed; the W3 §HYGIENE8 record NOT yet written), frostozk `d554e68` (harness reconstructed, not yet run/recorded), WELCH `8324511` (MAJORs 0/0, wave-level), LILI `f0dae5a` (2/2), WITHHELD-TD `a668913` (2/2). Both sessions resumed from their transcripts with the exact remaining scope. Union-population scan of `train8`'s added lines over 1,346 documents: DIGITS 7 (5-digit ZIP-shaped furniture + one invented 6-digit fixture number colliding outside its family), MONEY/DATES hits are cross-family dilution — per-family scans (all clean) remain the rule.
- 2026-08-27 Full suite on the repaired train (`5cc6396`): **1 failed / 6,496 passed / 38 skipped** — the one failure `test_every_production_caller_of_the_analysis_is_classified`: five instruments the closure sessions committed AFTER their branch proofs (`glance_family_replay`, `scanhyg_family_replay`, `scanhyg_pinned_replay`, `withheldgrids_leaf_diff`, `withheldgrids_srcdates_audit`) call the analysis and were in neither `ANALYSIS_CALL_SITES` nor `EXCLUDED_ANALYSIS_CALLERS`; this guard runs only in the full suite, i.e. at the train. Excused on the standard two grounds (no verdict published; the reconstructed page partition supplied) at `169c72a`; gate tests 50 EXIT=0, guards 254 EXIT=0. Lesson for closure sessions: a new `tools/` instrument that calls the analysis must add its excuse in the same commit. The host exited again during the two resumed sessions (no new commits; the frostozk worktree carried a harness mutant left applied mid-run — restored from the index); both are resumed a second time.

## Resuming on another machine (written 2026-08-27, everything pushed)

Pushed and verified tip-for-tip on `origin`: `main` (`51769b4`), `train8` (`169c72a`) and all twelve `wave8-*` branches. A fresh session needs only this file: `git clone`, `git checkout train8`, read this manifest top to bottom (the cell table, the progress log, the composition section). Not in git, by design: the OCR artifact cache `webapp_data/` and the run of record `discovery_reports/2026-08-23T020128.909387-0000-356a4269/` — both live in the OneDrive folder the repo sits in, so they sync with the account; without them the replays, sweeps and the cold run cannot run (the suite, guards, conformance and gate can). Worktrees are local: recreate with `git worktree add .claude/worktrees/mt8-<cell> wave8-<cell>` only if a cell branch still needs work. A harness killed mid-run leaves a mutant applied in its worktree — `git status --short` before trusting any tree, `git checkout -- .` to restore.

**Operating model (Gustavo, 2026-08-26 — binding for batch 8+):** Ocean (Fable 5) leads; optimize for context/usage: one broad census, failures clustered into pain points ranked by expected validated yield, one focused implementation session per pain point, one fresh hostile-review session after it (card + diff + tests only), targeted cohort proofs during development, architecture/ceremony rabbit holes parked; deterministic scripts own enumeration, hashes, diffs, counts, logs, mover manifests and monitoring; full suite, pinned corpus, cold archive run, regression comparison and CI only at the composed train; the repo is durable memory; `/compact` only when continuing the same problem, a fresh session for an unrelated pain point; at most two concurrent expensive sessions; workflows only for research/census/contradiction hunting, never as the coding mechanism; every mutation-testing, adversarial-review, financial-integrity, pinned-corpus, ceremony and zero-unexpected-regression requirement stays. Ceremony/truth-set decisions go to Gustavo before anything moves; otherwise continue autonomously.

**State at push:** ten cells composed on `train8` at registry 81 (suite 1 failed → fixed at `169c72a`; guards 254; conformance 1,239). Left: FROST-OZK (harness committed `d554e68`, run + FZ12/FZ13 to write, then merge → 83 with the `OBSERVER_VERSION` hand-merge to 6), HYGIENE-8a (instruments + harness landed through `f240b30`, W3 §HYGIENE8 to write, then merge), then `ANALYSIS_STAGE_VERSION` 15→16 + `OCR_STAGE_VERSION` 3→4, `tools/train/floor.sh`, the single archive sweep, per-family root-base tree scans, `tools/train/coldrun.sh` vs `356a4269`, remote CI read, PROJECT_STATUS.md, push. Then the next pain point: TRUIST-YAS.


## Recovery on the Linux host (2026-08-27) — the corpus decision and the reconstructed batch-7 baseline

**Durable losses, stated once.** The OCR/analysis artifact cache `webapp_data/`
and the run of record `discovery_reports/2026-08-23T020128.909387-0000-356a4269/`
are permanently unavailable (Gustavo, 2026-08-27). Nothing historical is
rebuilt from logs: every batch-7 number below is quoted from a committed
record, and the baseline is REGENERATED at the batch-7 tree, not reconstructed.
Composition landed on the way: `wave8-withheldtd`'s one post-merge commit
(§TD17, docs-only) composed inside its own section as `2004edf`.

### Corpus reconciliation (deterministic; the frozen inventory is counts-only)

| | on disk 2026-08-27 | frozen record (`discovery/inventory.py`, README, TRANCHE1) | delta |
|---|---|---|---|
| files under `Bank Statements/` | 3,771 | 3,768 | +3 |
| PDFs | 3,618 | 3,615 | +3 |
| bytes | 997,655,878 | 996,080,803 | +1,575,075 |
| pinned (manifest, hash-verified) | 109 (0 missing, 0 case mismatches) | 109 | 0 |
| discovery PDFs | 3,509 | 3,506 | +3 |
| distinct PDF SHA-256 | 3,412 | 3,409 (W3 §RS5) | +3 |
| non-PDF files | 153 | 153 | 0 |
| runner-equivalent dedup over the discovery set | 124 within-archive / 82 pinned-corpus copies (80 distinct pinned shas) | 124 / 82 | 0 |

No per-file manifest of the frozen archive was ever committed, so the three
additions are identified by constraint, not lookup. Every constraint is
durable: (1) their sizes must sum to exactly 1,575,075 bytes; (2) each must be
unique content (3,412 − 3,409 = 3 new hashes ⇒ none is a duplicate of anything
on disk); (3) none is referenced by any committed record (2,459 hex tokens,
23 redacted census fragments and 113 quoted archive paths across docs, tools
and tests); (4) every discovery upload carries an 8-hex or `c<n>_` prefix — the
only unprefixed discovery files besides the five `c-chris_` ones are these;
(5) their folder, `Tru Credit Union/`, holds exactly these three and appears in
no record (TRU-SAVINGS is a Truist card); (6) every folder whose size a record
states — `BMO/` 184, `Chase/` 613, `US Bank/` 59 — matches disk. Exactly ONE
triple satisfies (1)–(3) with a shared folder and prefix:

| path | bytes | sha256[:16] |
|---|---:|---|
| `Tru Credit Union/Account Statements560649E594474B05838ED42EED37DD2B.pdf` | 254,455 | `2113BA9692223261` |
| `Tru Credit Union/July2026.pdf` | 635,584 | `9820D513501ECF09` |
| `Tru Credit Union/May 2026.pdf` | 685,036 | `A48F4BD648CA2DC0` |

(PDF metadata dates were checked and are uninformative: no file on disk carries
a creation/modification date after the 2026-08-06 freeze; 674 carry none.)

**DECISION (Ocean, 2026-08-27; per Gustavo's instruction not to assume the
3,618).** The official batch-8 measurement population is the FROZEN archive of
record: 3,615 PDFs = 109 pinned + 3,506 discovery, denominator **3,380
distinct content shas**, the same population as `356a4269`. It is realised as a
resolved-population root `.claude/recovery/corpus_frozen_3615/` — real
directories, one symlink per file into `Bank Statements/`, the three Tru Credit
Union files omitted; the archive itself is not modified. Over that root
`discovery.inventory.enumerate_root` reports 3,768 / 3,615 / 996,080,803 /
109 / 3,506 and `baseline_deviations()` returns `[]`: the runner's own
frozen-baseline check passes natively, `--skip-baseline` is NOT used, and no
`FROZEN_*` constant moves. Both the reconstructed baseline and the train-8 run
take `--root` = that path. The three documents are parked; they enter the
archive only through a deliberate re-freeze (new constants plus a committed
per-file manifest, so this identification never has to be done by constraint
again) after batch 8 is measured.

### The reconstructed batch-7 baseline (design; not yet run)

* **Tree:** worktree `.claude/worktrees/b7-302f8f2` at `302f8f2` (detached) —
  the batch-7 train tip that produced `356a4269` (v15, OCR v3, registry 75,
  identical `FROZEN_*` constants; the two commits after it, `8e5efe9` and
  `10cc722`, are docs). Its own cache and reports live inside the worktree
  (`webapp_data/`, `discovery_reports/`), cold.
* **Equivalence pin, already verified:** at `302f8f2`,
  `analysis_settings_key(parse_mode="deterministic")` under the default
  environment = `24675EF06C2E08DD6803362ACD56045607BBFD3B80642A849D08D0DF541B5CAC`,
  the run of record's recorded key (registry fingerprint
  `4FD68C84295EEA60D9D80CFFF9E3CC60DA487541A313AC4CC8D10C3DAA2C3695`). The
  three other env combinations (`WITHHOLDING_DENOMINATOR_MODE=verified_revenue`,
  `GENERIC_STRUCTURER_ENABLED=1`) do not match — the run of record ran on the
  defaults, and so will the reconstruction. OCR settings key
  `75A58292526F183884C09C8032F86E4A24B4C4D8A432F1F9617D6DDDE5705AAA` (identical
  on `train8` until the v4 bump).
* **Toolchain on this host, used for BOTH runs:** Linux 6.18.44-1-lts ·
  Python 3.14.7 in `.venv` (uv 0.11.31) · PyMuPDF **1.27.2.3** (the build W3
  records for batch 7) · pytest 9.1.1 · pdf2image 1.17.0 · Pillow 12.3.0 ·
  python-dotenv / google-genai / pydantic per `requirements-analysis.txt` (no
  `.env`: deterministic mode, no model client) · tesseract **5.5.3** /
  leptonica 1.87.0 (batch 7 ran 5.5.0 on Windows — drift confined to the
  local_tesseract rung) · poppler **26.07.0** (batch-7 version unrecorded).
  The full package freeze is committed as
  `tools/train/venv_freeze_linux_2026-08-27.txt` on `train8`.
* **Output:** `discovery_reports/RECON-B7-302f8f2/<run_id>/` inside the
  worktree, kept as the explicitly labelled reconstructed batch-7 baseline
  (gitignored like every run; its accepted figures are recorded here).
* **Acceptance gates — every one must hold before it is a baseline:**
  G1 `--dry-run`: pinned 109, coverage 100%, validated 102 / review 3 /
  withheld 3 / refused 1, expectations-file parity, currency 108/108 (+1),
  provenance 108/108 (+1). G2 `python corpus_gate.py` GREEN 105 / 3 / 1.
  G3 `--scanned` over the resolved root: baseline check passes; 3,506
  enumerated; dedup 124 / 82; **3,380 distinct shas; validated 2,469 / review
  17 / withheld 72 / failed 809 / deferred 13**; `invalid_pdf` 17; the run's
  analysis settings key = `24675EF0…`. G4 per-document, by a committed checker
  (`tools/recon_b7_check.py`) against every durable per-sha record — the
  pinned-copy outcomes vs `tests/data/parser_expectations.json`; the census's
  intact and fragment-matchable shas at `7a317445` minus the 25 named batch-7
  movers; every batch-8 cell's recorded base population (COREISS2 14 failed,
  WELCH 17 failed, LILI 20 failed, COREENC 58 failed + 13 outsiders, FROST-OZK
  17 failed, GLANCE 14 validated / 8 failed, CPSCAN 19 failed, WITHHELD-GRIDS
  22 withheld, WITHHELD-TD 11 withheld, SCAN-HYGIENE's 41) — discrepancies
  listed by sha, never normalised. G5 drift rule: a difference confined to
  documents whose `source_path` is `local_tesseract` is reported as toolchain
  drift with the shas named; a difference on ANY native-text document is a
  STOP — no train-8 measurement until it is explained.
* **Then train 8**, same host / venv / root, after the last merge and the
  v16 + OCR v4 bump: `--scanned --out discovery_reports/TRAIN8-<sha>`, then
  `python -m discovery.compare <RECON-B7 dir> <TRAIN8 dir> --fail-on-regression`
  — exit 2 stops the line unless the moved document is a ceremony named in
  advance. No validator, truth pin, integrity rule or regression gate is
  weakened because the historical directory is gone.
* **G1 and G2 measured on this host at `302f8f2` (2026-08-27 21:03–21:07 EDT, run `52c7194a`):** dry run 109 processed, deterministic coverage 108/109, **validated 102 / review 3 / withheld 3 / failed 1** (`parser_declined`, columbia_bank — the pinned refusal), 103 native + 6 committed-artifact reads, dedup unique 109, `DRYRUN_EXIT=0`; corpus gate **GREEN** `GATE_EXIT=0` — 109/109 pinned hashes, balance and ADB 105 pass / 3 withheld / 1 pinned refusal, outcome classes 1 refused / 3 review / 102 validated / 3 withheld with the whole integrity block, currency 14 CAD / 94 USD, provenance 7 / 4 / 1 / 7 / 89, no live OCR, no model calls. The pinned truth set reproduces byte-for-byte on the new toolchain; G3–G5 (the cold run) await Gustavo's go.

### Baseline A — launch record (2026-08-27, Ocean; Gustavo's GO with two amendments)

Amendments recorded: (1) the checker is finished, tested and committed BEFORE
the cold run, and its G3/G4/G5 acceptance logic is frozen — any later change
to the criteria needs an explicit recorded reason here, never "to fit the
result"; (2) the run executes on an otherwise idle host (no FROST-OZK /
HYGIENE-8a sessions, no sweeps, nothing resource-heavy concurrently).
Additional G5 rule (Gustavo): any difference attributable solely to Windows
Tesseract 5.5.0 → Linux Tesseract 5.5.3 is named by sha and reported
separately as environmental/toolchain drift; it is not counted as a batch-8
improvement or regression unless equivalence is independently established;
any unexplained native-text difference remains a STOP.

| item | value |
|---|---|
| checker commit | `655b8d8` on `train8` — `tools/recon_b7_check.py` + `tests/test_recon_b7_check.py` (13 tests pass; canonical guards + caller-classification guard 278 pass; real-artifact smoke on the dry run: O1 109/109 matched, registry 75 pinned, census tokens 610 + 56 parsed) |
| baseline worktree commit | `302f8f2` (detached, `.claude/worktrees/b7-302f8f2`; clean; v15 / OCR v3 / registry 75; `analysis_settings_key(parse_mode="deterministic")` = `24675EF06C2E08DD6803362ACD56045607BBFD3B80642A849D08D0DF541B5CAC` = the run of record's) |
| frozen corpus evidence | resolved root `.claude/recovery/corpus_frozen_3615/` (3,768 symlinks): `enumerate_root` → files 3,768 · PDFs 3,615 · bytes 996,080,803 · pinned 109 (0 missing, 0 case mismatches, 0 collisions) · discovery 3,506; `baseline_deviations()` = `[]`; distinct PDF SHA-256 3,412 on disk − the three excluded (`2113BA9692223261`, `9820D513501ECF09`, `A48F4BD648CA2DC0`) = 3,409 = W3 §RS5's frozen count; runner-equivalent dedup 124 / 82 |
| environment freeze | `tools/train/venv_freeze_linux_2026-08-27.txt` (48 packages): Python 3.14.7 · PyMuPDF 1.27.2.3 · pytest 9.1.1 · pdf2image 1.17.0 · Pillow 12.3.0 · python-dotenv / google-genai / pydantic; tesseract 5.5.3 (leptonica 1.87.0); poppler 26.07.0; Linux 6.18.44-1-lts; no `.env` (deterministic mode, no model client); `WEBAPP_DATA_DIR` unset → the worktree's own cold `webapp_data/`; telemetry on; OCR env knobs unset (defaults) |
| exact command | `cd .claude/worktrees/b7-302f8f2 && PATH=<repo>/.venv/bin:$PATH python -m discovery --scanned --root <repo>/.claude/recovery/corpus_frozen_3615 --out discovery_reports/RECON-B7-302f8f2 --quiet` — wrapped as `{ echo TREE/START_UTC; <cmd>; echo RUN_EXIT=$?; echo END_UTC; } > discovery_reports/RECON-B7-302f8f2.log 2>&1`, detached |
| acceptance | `python -m tools.recon_b7_check --run <run dir> --report <run dir>/recon_b7_check.md` at `655b8d8`: exit 0 ACCEPT · 2 REJECT-DRIFT-CANDIDATE (Gustavo's call) · 1 REJECT (STOP / absent / unbounded delta). Train 8 does NOT start automatically on any outcome. |
| start timestamp | appended below at launch |
* **LAUNCHED:** `START_UTC=2026-08-28T01:57:39Z` (2026-08-27 21:57:39 EDT), host `omarchy`, Python 3.14.7, tesseract 5.5.3, run directory `discovery_reports/RECON-B7-302f8f2/2026-08-28T015740.400872-0000-47be5963/` in the `302f8f2` worktree; log `discovery_reports/RECON-B7-302f8f2.log`. Nothing else runs on the host until `RUN_EXIT` is written.

### Baseline A — result (2026-08-28 02:41Z; checker `655b8d8` unchanged; decision PENDING Gustavo)

`RUN_EXIT=0`, 43.5 min (01:57:39Z → 02:41:10Z), run `47be5963`, cache cold →
2.1 GB analysis / 68 MB OCR. **Checker verdict: REJECT (exit 1).**

**G3.** distinct shas **3,380 ✓** · rows 3,506 ✓ · dedup 124 / 82 ✓ ·
inventory 3,768 / 3,615 / 996,080,803 / 109 / 3,506 ✓ · mode scanned ✓ ·
`invalid_pdf` 17 (= record) · **outcome: validated 2,457 (record 2,469, −12) ·
review 18 (17, +1) · withheld 72 ✓ · failed 819 (809, +10) · deferred 14 (13,
+1)** · `registration_count` ✗ — {75: 3,475 records, 0: 31}. The 31 are exactly
the 17 `invalid_pdf` + 14 `deferred_visual_ocr` records, whose dispatch never
ran (`dispatch.source = unavailable`): the frozen rule reads "75 on every
DISPATCHED record", the implementation counted undispatched records too. A
checker over-reach, not a reproduction defect; correction proposed below, not
applied.

**G4.** oracle coverage 875 of 3,380 distinct shas, unresolved tokens none:
O1 pinned copies 80/80 · O2 census failed 598/598 · O3 census withheld 55/56 ·
O5 RBC 141/141 (O4 welch is inside O2) — **one discrepancy**, `2A0B516B2C7D652E`
(td_us, scanned; withheld → failed/no_parser_matched, near-miss td_us 0.167):
DRIFT, intake rung local_tesseract. **STOP (native) 0 · ABSENT 0.** Native
side, beyond the oracle: native documents now `no_parser_matched` and NOT in
the census = **0**; native non-validated outside the oracle = 73
parser_declined + 11 review + 4 withheld.

**G5 — named toolchain drift (Windows Tesseract 5.5.0 → Linux 5.5.3): 16
CONFIRMED named movements (each batch-7 outcome fixed by a committed record)
plus 1 PROBABLE named movement (`1C6CB407`, whose record is an experiment line,
not a run-of-record row).** Non-native population 208 (local_tesseract 178,
none 30).

| sha16 | family | run of record | regenerated | record |
|---|---|---|---|---|
| `6ACF3130775C2517` | texas_first_scanned | validated | failed | W3 §SCANNEXT SN7 (b6; untouched in b7) |
| `756F987E1AD8B217` | texas_first_scanned | validated | failed | §SCANNEXT SN7 |
| `F8FC1D8B3ECD3F30` | balance_by_date (Hancock) | validated | failed | §SCANC |
| `ADE55A5BADF4DE8C` | United Community (scanned) | validated | failed | §SCANNEXT L33592 |
| `9CCB4FB2BB2F8F27` | first_farmers (scanned) | validated | failed | §SCANB L19585 |
| `B279C19DFF393A13` | apex_scanned | validated | failed | §WIRING2 L21558; §SCANFINISH "identical" |
| `6CE8CDD69E8458B9` | citizens (scanned) | validated | withheld | §SCANFINISH L39238 |
| `9B3DB6CF995DB68B` | texas_first_scanned | failed | validated | §SCANNEXT SN5.2/SN7 (the `714,71` cell now reads) |
| `A20AACF22B6A475A` | texas_first_scanned | review | failed | §SCANNEXT SN7 |
| `13B6B39D629BCA0D` | citizens (scanned) | review | withheld | §SCANFINISH L39239 |
| `2A0B516B2C7D652E` | td_us (scanned) | withheld | failed | §WITHHELDTD L44866 (base = 356a4269); O3 |
| `3B0738E968D43202` | southside_scanned | withheld | review | §SCANHYG L46189 (base = 356a4269) |
| `9D7EB67ADE0A8A39` | southside_scanned | withheld | review | §SCANHYG L46190 |
| `FD022A8600DA35AE` | southside_scanned | withheld | review | §SCANHYG L46192 |
| `E630CB66DBDB3C1D` | eq_bank_scanned | failed (declined, `sole_day`) | withheld | §SCANHYG L46263 |
| `B0E16E92A1ECFDFB` | eq_bank_scanned | failed (declined, `sole_day`) | withheld | §SCANHYG L46264 |
| `1C6CB4078AC0644C` | (TD Bank folder, scanned) | deferred (probable: §COMMSEC-GEN; the 13 persisted) | failed | probable, not fixed by a run-of-record row |

Two heuristic hits dismissed with reasons: `0CBD2AD8` (the pinned REPAIR-DOCTRINE
refusal — its batch-7 state IS failed; O1 matched) and `9413957E` (the "failed"
line is a §COMMSEC-GEN re-render experiment; run of record deferred =
regenerated). **Accounting of the 16 confirmed:** review +1 and withheld 0 are
reproduced EXACTLY by the confirmed set; validated −6 and failed +5 of the
aggregate's −12 / +10 are confirmed-named (the probable `1C6CB407` would add
deferred −1 / failed +1). **Residue: 6 validated documents lost (5 →
failed, 1 → deferred, or 4 + the deferred pair if `1C6CB407` left deferred)
with no per-sha batch-7 record** — every indicator places them in the
non-native population (native oracle 875/875, zero native detection loss), but
that is inference, not a record; the residue is NOT named by sha.
Equivalence with the batch-7 environment is therefore NOT independently
established; under Gustavo's G5 rule none of this movement may count as
batch-8 improvement or regression.

**Proposed checker correction (needs Gustavo's OK; recorded reason):**
`registration_count` restricted to records whose `dispatch.source` is not
`unavailable` — aligns the code with the frozen rule's own wording; touches no
outcome, per-document or drift criterion. With it, the verdict is
REJECT-DRIFT-CANDIDATE (exit 2), unchanged in substance.

**Options.** (A) Establish equivalence experimentally: build Tesseract 5.5.0
from source on this host (leptonica 1.87.0 present; tessdata version to be
recorded — the Windows box's is unrecorded), re-run ONLY the 208 non-native
documents at `302f8f2` under a separate `WEBAPP_DATA_DIR`, diff per sha against
the 5.5.3 run; exact reproduction of 2,469 / 17 / 72 / 809 / 13 would name the
whole drift set and settle the toolchain for both runs. (B) Accept the
regenerated run as the train-8 comparison base with the drift set recorded as
above (both runs then share one Tesseract, so these documents compare as
unchanged and are never counted), stating the batch-7 reproduction as "native
side exact by every durable record; scanned side drifted by 16 named + 6
unnamed documents". (C) Stop.

* **2026-08-28 checker correction landed `30d420e`** (Gustavo's OK):
  `registration_count` evaluated on dispatched records only
  (`dispatch.source != unavailable`) — the frozen rule's own wording; G3
  outcome checks, G4, G5 untouched; no movement excused. Re-run on `47be5963`:
  **REJECT-DRIFT-CANDIDATE (exit 2)**, `registration_count` {75: 3,475} ✓.
* **Option A chosen (Gustavo, 2026-08-28), strict boundary: ONE attempt.**
  Tesseract 5.5.0 built from source into the isolated prefix
  `~/.local/opt/tesseract-5.5.0` (5.5.3 untouched); tessdata: no record names
  the Windows box's, so the attempt uses the host's `eng.traineddata`
  (`tesseract-data-eng 2:4.1.0-5`, sha256 `daa0c97d651c19fb…`) via
  `TESSDATA_PREFIX=/usr/share/tessdata`; poppler stays 26.07.0 (unrecorded on
  the Windows box; not reconstructed). Code at `302f8f2`; ONLY the 208
  non-native documents (mirror root `.claude/recovery/corpus_nonnative_208/`,
  `--skip-baseline` because the root is a scoped subset — an equivalence
  experiment, never the measurement); separate cold cache
  `WEBAPP_DATA_DIR=<worktree>/webapp_data_t550`; nothing else running.
  Success = the union (native records from `47be5963` + non-native records
  from the 5.5.0 run) passes the frozen checker: 2,469 / 17 / 72 / 809 / 13
  and no unexplained discrepancy. If not, stop after this attempt → Option B
  drift quarantine. Train 8 waits for Gustavo's review either way.

### Option A — the single Tesseract-5.5.0 attempt (2026-08-28 02:59–03:18Z): equivalence NOT established

Build: tesseract 5.5.0 from the GitHub 5.5.0 tarball (sha256
`f2fb34ca035b6d087a42875a35a7a5c4155fa9979c6132365b1e5a28ebc3fc11`), prefix
`~/.local/opt/tesseract-5.5.0`, leptonica 1.87.0 / OpenMP / AVX2 identical to
the system 5.5.3 build, system install untouched. Run B `06234d16` at
`302f8f2`: the 208 non-native shas (209 files), `TESSDATA_PREFIX=/usr/share/tessdata`
(eng `daa0c97d…`, package 4.1.0), poppler 26.07.0, cold `webapp_data_t550`,
`--skip-baseline` (scoped), `RUN_EXIT=0`, 19 min. Union (`tools/recon_b7_union.py`
`cd7896a`; native records from run A `47be5963`, the 208 from run B) judged by
the frozen checker at `30d420e`: **REJECT-DRIFT-CANDIDATE (exit 2)** —
validated **2,453** (−16) · review 18 (+1) · withheld 73 (+1) · failed 822
(+13) · deferred 14 (+1); G4 875 covered, native STOP 0, drift 2
(`2A0B516B2C7D652E` withheld→failed as before, plus `A4C49ACBC03D905D` — a
PINNED copy, apex_scanned, validated under 5.5.3, failed under 5.5.0).

**A → B (5.5.3 → 5.5.0), 13 documents changed:** validated→failed
`A4C49ACBC03D905D` (apex), `B60DDD2DBC06A151` (first_farmers),
`DC3881234577C378`, `E4F5802ECAFE626F` (balance_by_date); validated→withheld
`FA59082D6A74CC1D` (balance_by_date); failed→validated `95246AAF1A2D7F59`
(core_processor_sectioned); deferred→failed `08D8D3B6DF17B63B`,
`BD2A40D672A2A5CC`; failed→deferred `1C6CB4078AC0644C`, `DD86C0D6724662AD`;
reason-only `337FE9AA2F7750D6`, `3E907CEFE6B6F4B4`, `71864C4034B5CADD`.
**None of the 16 confirmed drift documents returned to its batch-7 outcome
under 5.5.0.** Conclusion: the batch-7 divergence is not the Tesseract binary
version; it lies in the unrecorded parts of the Windows OCR environment
(tessdata variant/version, rasterization) — which, per the boundary, are not
reconstructed. The 5.5.0 build, its cache and run B are retained for the
record and used for nothing.

**Option B — proposed drift quarantine (Gustavo to confirm):** the train-8
comparison base is run A `47be5963` (Tesseract 5.5.3 = this host's system
toolchain, the same one train 8 will use). Quarantine set = the **208
non-native shas** of run A (`.claude/recovery/corpus_nonnative_208.shas`; 178
local_tesseract + 30 none), with the 16 confirmed + 1 probable named drift
documents as its known-drifted subset. In the recon → train-8 comparison,
any movement on a quarantined sha is reported in its own table, named by sha,
and never counted as a batch-8 improvement or regression; native-side movement
is judged as usual. The batch-7 reproduction is stated as: native side exact
by every durable record (875/875, zero native detection loss); scanned side
drifted by 16 named + 6 unnamed documents.

### Option B CONFIRMED (Gustavo, 2026-08-28) — an ACCOUNTING quarantine, not a safety quarantine

Comparison base for train 8: run A `47be5963` (Tesseract 5.5.3, this host).
Quarantine set: the 208 non-native shas of run A
(`tools/train/recon_b7_quarantine_nonnative_208.shas`). Rules, binding:

1. The 208 are EXCLUDED from the historical batch-7 → batch-8 headline gain,
   because the original Windows OCR environment cannot be reproduced exactly.
2. Positive movement on a quarantined sha is reported separately and never
   counted toward the official historical-comparable batch-8 improvement total.
3. Negative movement on a quarantined sha is REAL under the shared current
   environment and is investigated normally — quarantine never suppresses or
   excuses a regression.
4. Native/comparable shas keep normal `--fail-on-regression` semantics.
5. A full per-sha movement table for the 208 is preserved with every comparison.

Final batch-8 reporting separates: (a) historical-comparable/native
improvements; (b) quarantined OCR-environment improvements; (c) regressions on
comparable shas; (d) regressions on quarantined shas; (e) the total observed
current-environment validated count. "2,469 → N" is never stated as the
official historical-comparable gain unless the numerator excludes the
quarantined OCR-derived gains or is labelled otherwise. The batch-7
reproduction statement stays: **native side reproduced by durable evidence;
scanned side could not be made equivalent because the original Windows OCR
environment is unrecoverable.**

Resumed (Gustavo): FROST-OZK harness + FZ12/FZ13; HYGIENE-8a record → fresh
hostile review → closures; one expensive session at a time; host otherwise
idle; no train-8 cold run until the pre-run summary (final composed commit,
registry/version state, comparable and quarantine sha counts, the exact
comparison/reporting logic, the floor, the exact command) is reviewed.

### 2026-08-28 — FROST-OZK harness: the 32 GB blocker, root cause, execution guards (`dfe95a6` on `wave8-frostozk`)

Three consecutive host crashes while running `tools.frostozk_mutation_table`
in the frostozk worktree (each left a mutant applied — restored from the index
with `git checkout -- .` before anything else). Gustavo measured RAM at ~32/32
GB. **Root cause (exact):** mutant **O21** sets `_MAX_DAY_ROWS = 10 ** 9`; the
row-cap test reads the mutated constant and builds its fixture as
`[100] * (_MAX_DAY_ROWS + 1)` — a 1,000,000,001-element list (~8 GB), the
solver's `suffix` list of the same size (~8 GB) and ~10⁹ distinct int objects
(~28 GB). Pure allocation, not recursion; Linux overcommit let it grow to the
host's size. The harness itself is strictly sequential (one `pytest` child per
mutant, no xdist — not installed — no archive, no raster, no Tesseract/poppler:
the two gate suites are 84 invented-fixture tests that peak at **85 MB RSS in
0.9 s** unmutated). O22/O23 (node and solution budgets) are CPU-bounded and
small. W3 §FZ6 records O21 as KILLED by that same test on the Windows box.

**Execution-only guards (no semantic change; MUTANTS, TESTS and scoring
byte-identical, verified by diff hunk ranges + `--dry-run` 41/41 anchors):**
RLIMIT_AS 4 GB on the pytest child (an impossible allocation raises MemoryError
inside the test → the test fails → KILLED by the named test); `-p no:xdist`;
one mutant at a time in its own process session; 600 s hard timeout with
process-group SIGKILL and reap; MemAvailable floor 8 GB — refuse to start and
abort mid-run below it; per-mutant peak RSS (VmHWM) and MemAvailable
before/after recorded on every row; checkpoint JSON after every mutant with
`--resume`; `--only` / `--dry-run`. TIMEOUT / ABORTED-MEMORY rows are
reported separately and never scored as kills; the harness exits non-zero
until every mutant has a real verdict. Max concurrent processes: 2 (the
harness + one pytest child; a transient `git checkout` between mutants).
Expected peak: ≤ 85 MB per ordinary mutant, ≤ 4 GB (the cap) on O21.
Awaiting Gustavo's go before any execution.
* **2026-08-28 04:13Z — FROST-OZK harness, first complete run on this host** (`aad19fc` on `wave8-frostozk`; guards `dfe95a6`; the row-cap fixture rebounded to the intended 64/65 rows in `aad19fc` after Gustavo's gate showed O21's kill was a `MemoryError` under RLIMIT, not an assertion — now a plain `assert … is None` on a solved 65-row day, 0 `MemoryError`, 86.5 MB). **41 mutants in 34 s: 38 KILLED, O1 and O7 SURVIVED disclosed (the two §FZ6 calls provably redundant), F5 SURVIVED UNDISCLOSED** ("an unknown column head falls back to a layout"; §FZ6 recorded it KILLED by `test_an_unknown_column_head_is_refused`). Peak RSS 88.5 MB (O23), slowest 1.0 s (O22), MemAvailable never below 26.4 GB, 0 timeouts / 0 aborts, tree clean, no child survived; `HARNESS_EXIT=1` on the undisclosed survivor. Mechanism (Ocean's read, for the closure session to settle): the mutant's fallback layout `date_transaction_amount` cannot match the section's `date_amount_transaction` rows, so F6's unmodelled-line gate refuses the document anyway — F5 survives only because F6 catches it; the review closure `9ebac02` touched `frost.py` after §FZ6 was measured. Resolution owed on the branch: an isolating test (a head that maps to nothing but whose rows the fallback CAN parse, so the mutant would publish) or a measured disclosure with a pair-mutant kill; then §FZ12 (this run, the incident, the guards) and §FZ13 (MAJOR-1/2 closure verification). Raw run: `.claude/recovery/frostozk/{harness_full.log,frostozk_mutation_table.json}`.
* **Standing rule (2026-08-28) — the stand-in for the lost run of record.** Every cell instrument that takes `--rows <run>/rows.csv` and `--data-dir <cache>` (the hygiene8 replays, `regfp_zero_movement_sweep`, the coreenc/scanhyg/withheldgrids replays, the desccols proofs) points at run A: rows `.claude/worktrees/b7-302f8f2/discovery_reports/RECON-B7-302f8f2/2026-08-28T015740.400872-0000-47be5963/rows.csv`, cache `.claude/worktrees/b7-302f8f2/webapp_data` (3,473 OCR entries; the OCR settings key `75A58292…` is identical on `302f8f2` and `train8`, so text resolves; analysis entries are per settings key and each tree computes its own). Any number so measured is labelled "against run A (Tesseract 5.5.3)", never "the run of record"; its 208 non-native shas carry the accounting quarantine. FROST-OZK's closure session (running) and HYGIENE-8a's record session (next, after it) use this rule; neither runs anything over the archive itself.
* **2026-08-28 — FROST-OZK CLOSED, VERIFIED and COMPOSED (`028aa9c` on `train8`, registry 83).** Closure session on `wave8-frostozk` (`b154cfe` isolating F5 test — the old FZ6 attribution described a mutant the committed harness never contained; `131b39f` MAJOR-1 closure completed comment-only; `9f9a8f6` §FZ12 lines 44503–44737 + §FZ13 44738–44766). Ocean's own verification at `9f9a8f6`: production AST identical to `aad19fc` across all three commits; W3 single append hunk, 0 lines removed; privacy grep over the block: 5 hits, all session dates; gate suites + count semantics 155 EXIT=0; guarded harness **41 / 39 KILLED / O1+O7 disclosed / 0 undisclosed / 0 unscored**, 88.6 MB peak, 1.0 s slowest, tree clean, EXIT=0. §FZ13: MAJOR-2 verified; MAJOR-1 was incomplete (an inline comment at the totals check still claimed independence) → completed → verified. Finding for Ocean: `frost_period_packet.py` (FZ7's "6 of 9") was never committed — bears only on the FROST-PERIOD ruling (recommendation REFUSE). Composition on the train: helper composed both registry pins 81 → 83 (conflict hunks only); hand-resolved `telemetry/stated_counts.py` (both "6 —" comment blocks, ONE `OBSERVER_VERSION = 6`) and the count-semantics pin **(6, 35, 65, 2)** = base (5, 32, 60, 2) + welch (+1, +2) + frostozk (+2, +3); W3 byte-exact rebuild (ours + §FROSTOZK through FZ13 = 53,754 lines); one cross-cell guard interaction — CURRENCY-SOURCE's provenance guard scans `tools/` and the harness quotes a reader's `currency_source="institution_default"` line as a mutant anchor → the harness is enumerated in `PROVENANCE_MODULES` with the reason (the 169c72a pattern). Composed tree: cell + currency + registry + conformance 1,260 EXIT=0; canonical guards + gate tests + caller classification 278 EXIT=0. Remaining before the bumps: HYGIENE-8a (record part 2 → fresh hostile review → closures → merge).
* **2026-08-28 — HYGIENE-8a record COMPLETE (`af98349` on `wave8-hygiene8`; §HYGIENE8 part 2 = H5–H13, lines 44034–44480; hostile review launched).** The record session re-measured every instrument on this host, each in `( ulimit -v 8000000; timeout … )`, one at a time, MemAvailable ≥ 26.28 GB: branch tests 253 / guards 253 EXIT=0; poison census 52 cells, base 24 → branch 0; overflow reach (run A) census 11/11/8/7/0, archive 2,769 of 3,350 (run of record had 2,765 of 3,351 — a different run, recorded beside it, part 1 not edited); pinned replay 109 / 108 identical / 1 refused both / movement 0 of every class / 14 claimed by touched readers (104 s, 167 MB); mutation table **30 / 30 killed** (148 s, 332 MB); family replay against run A **618 docs / 625 replays / 609 identical / 16 raised on both / movement 0 of every class** (500 s, 92 MB). Ocean's verification at `af98349`: single append hunk + a 5/3 fix-up inside H11, privacy grep hits are session dates only, branch tests + canonical guards 455 EXIT=0, Ocean's own capped harness run 30/30 EXIT=0, tree clean. **Rulings on the record's H8 findings:** (1) the shared privacy scanner lives on `main` — Ocean scans the population at the train (standing rule); (2) the purged prompt specimen surviving in an inherited §PRIVACY3 ledger line is main-tree text → the batch-9 FIXTURE-PRIVACY P0 sweep; a commit message is immutable history — recorded, not rewritten; (3) the 2019-dated fixture → closure item (2031 convention) unless the reviewer rules otherwise; (4) 26 of the 618 are quarantined shas — the accounting quarantine applies, the replay's quarantined movement table is empty; (5) 12 single-killer mutants — risk carried; (6) DETECT-BUDGET-GATE first in HYGIENE-8b, and `PLANNED_REGISTRATIONS = 80` is now below the train's 83 — the train floor's corpus-marked detect-budget test is the place this shows; carried to the pre-run summary.
* **2026-08-28 — HYGIENE-8a hostile review → APPROVE WITH FINDINGS, 0 BLOCK, 2 MAJOR, 4 MINOR** (`reviews/BATCH8_HYGIENE8_REVIEW.md`, `b2e4ad7`). Held (re-measured under caps, one process at a time): pinned 109 / 108 identical / 1 refused both / movement 0; poison 24 → 0 over 7 sites; overflow reach 11/11/8/7/0 against run A; mutation 30/30; population 618 and 26 quarantined re-derived independently; base-tree isolation; privacy census of 3,658 added lines clean (only invented/session dates). **MAJOR-1:** `_release_worker_slot` (`webapp/app.py:99–106`) re-arms without re-claiming the slot → 2 live workers after one upload during the replacement's job (probe); no test or mutant sees it. **MAJOR-2:** four unguarded `date()` sites remain in the four declared chain-guarded readers (`chase.py:178`, `columbia_bank.py:449`, `scotia.py:235`, `scanned_small_bank.py:82` via `:608`) — driven on both trees, all four escape a `ValueError` echoing the printed month/day/year; the chain guard inspects `raise` statements, and `columbia_bank.py`/`scotia.py` have none, so their `CHAIN_GUARDED` entries are vacuous (base-inherited; the dispatch seam reduces it to a class name → MAJOR, not BLOCK). MINORs: thread-raised `SystemExit` does not stop the process and queued work waits for the next upload; the overflow bound is a C `int` (2^31), not a "32-bit C long"; fixture dates off the 2031 convention (the 2019 pair + one 2026 token); bookkeeping (E3/E4 labels, a stale "crosses the worker boundary" sentence, a surviving thread-count assertion, "DERIVED, not typed" derives from a typed constant). Reviewer's note for the train: the `OverflowError` widening's only outcome-moving direction (crash → `None`) reaches 16 registrations in 13 modules — the population the train's sweep must contain. **OCEAN RULINGS → closure session (launched):** MAJOR-1 closed as the reviewer's one-line claim-in-the-same-critical-section + an isolating live-worker-count test + a mutant; MAJOR-2 closed by rerouting all four sites through the guarded conversion (no raise path carries a document token), both-tree drives on invented out-of-range fixtures, real chain-guard coverage for columbia/scotia, one mutant per site, and zero-movement re-proved by the pinned replay and the family replay against run A (any mover named by sha, quarantine stated); MINOR-3 behaviour + rationale corrected and tested; MINOR-4/5/6 as asked; §H14 appended with the proof floor at the closure tree.
* **Remote CI, measured (2026-08-28):** `.github/workflows/corpus-gate.yml` triggers on `push: branches: [main]`, `pull_request` and `workflow_dispatch` — no `train8` push has ever produced a run (0 runs on the branch, by design). The train's remote conclusion is therefore read twice: a `workflow_dispatch` run on `train8` after the floor (`gh workflow run corpus-gate.yml --ref train8`, conclusion + run id recorded), and the `main` run after the final `train8 → main` merge, as batch 7 recorded it. Housekeeping note: the baseline worktree's only status entry is the untracked `webapp_data_t550/` (the isolated Tesseract-5.5.0 cache, kept for the record).

## Recovery on the Windows host (2026-08-28) — the host decision, the intact run of record, and the same-host control baseline

**Recovered from git only** (the Linux session's machine was shut off during
the HYGIENE-8a closure session; nothing in its context survived). State found:
`origin/main` `0698e93`; `origin/train8` `9c1f19b` (FROST-OZK composed at
`028aa9c`, registry 83, the only cell merge since); `origin/wave8-hygiene8`
`579f0bb` = the review `b2e4ad7` + five closure commits landed 01:37–01:43 EDT
(MAJOR-1 `313cc43`, MINOR-3 `97862d1` with one MINOR-6 item, the corpus_gate
excusal `c64f936`, two Q7 mutant fixes `88540b2`/`579f0bb`) — **MAJOR-2,
MINOR-4, MINOR-5, the rest of MINOR-6, §H14 and the closure proof floor were
NOT landed**, no closure verification exists, and the branch is not in
`train8`. The cold run was never launched (0 workflow runs on `train8`, no run
directory dated 08-27/28 anywhere).

**Gustavo's decision (2026-08-28): batch 8 finishes and is measured on the
WINDOWS host; no work is split between hosts.** Housekeeping first, as
approved: the `mt8-frostozk` worktree carried mutant **O21 applied**
(`_MAX_DAY_ROWS = 10 ** 9`, the 32 GB allocation — residue of the interrupted
Windows harness run); the diff was verified to be exactly that one line and
the file restored from the worktree HEAD; `main` and `train8` fast-forwarded
(`--ff-only`); the local `wave8-hygiene8` carried an unpushed Windows draft of
W3 part 2 (`aa154be`, 420 lines, written 08-27 10:07 EDT against the run of
record and superseded by the Linux `253c0ff`/`af98349`) — preserved as branch
`wave8-hygiene8-win-draft`, never merged; the worktree moved to `579f0bb`.

**What this host has that the Linux host did not.** The run of record
`discovery_reports/2026-08-23T020128.909387-0000-356a4269/` is INTACT
(rows.csv 3,506 rows, summary, telemetry 3,506 records; 41.1 min wall on a
warm cache) and so is its cache `webapp_data/` — OCR 10,246 / analysis 31,111
entries, exactly the counts the run's own summary recorded. The "durable
losses" paragraph above is true of the Linux host only. On this host every
`--rows/--data-dir` instrument points at the run of record, labelled "against
the run of record 356a4269 (this host, Windows, Tesseract 5.5.0)"; run A
`47be5963` is not on this host and is not used for anything.

**Corpus.** `Bank Statements/` on disk IS the frozen archive: files 3,768 /
PDFs 3,615 / bytes 996,080,803 / pinned 109 / discovery 3,506 —
`discovery.inventory.enumerate_root` matches every `FROZEN_*` constant and
`baseline_deviations()` = `[]` natively, so no resolved-population root is
needed and `--skip-baseline` is never passed; no `Tru Credit Union/` folder
(the three post-freeze additions exist only on the Linux host); 0 OneDrive
placeholders (every file is local). The control worktree
`.claude/worktrees/b7-302f8f2` was created (detached, clean; v15 / OCR v3 /
registry 75; `analysis_settings_key(parse_mode="deterministic")` =
`24675EF0…` = the run of record's, registry fingerprint `4FD68C84…`, OCR key
`75A58292…` — the equivalence pin holds on this host); it tracks only the 109
pinned PDFs, so both runs take `--root` = the main checkout's archive.

**Toolchain, the same for both runs:** Windows 11 10.0.26200 (HP All-in-One
27-cr0xxx, 16 logical CPUs, 15.3 GB RAM — ≈1.2 GB free with the desktop apps
open; the archive runs need an otherwise idle host); Python 3.14.5
(`C:\Python314\python.exe`); PyMuPDF 1.27.2.3 (the batch-7 build); pytest
9.1.1; Pillow 12.2.0; pytesseract 0.3.13; tesseract **5.5.0.20241111** /
leptonica 1.85.0 — **the batch-7 version, so there is no Tesseract drift on
this host**; poppler 24.08.0; no `.env` (deterministic mode, no model client);
`WEBAPP_DATA_DIR` set per run to a cold, isolated directory. The full `pip
freeze` (132 packages) goes into every provenance record.

**Revised baseline policy (Gustavo, 2026-08-28).** The Windows train-8 cold
run is NOT compared to the Linux reconstruction `47be5963`. Before train 8 is
measured, a fresh SAME-HOST batch-7 control run is produced at `302f8f2` over
the frozen corpus with the same toolchain, a cold isolated cache, no batch-7
code change, full per-sha output and explicit provenance
(`tools/train/control_b7.sh`; acceptance by `tools/recon_b7_check.py` at its
frozen G3/G4/G5 logic — on this host the scanned side may reproduce outright).
Train 8 then runs on the same host, corpus, toolchain, cold-cache posture and
settings (`tools/train/coldrun.sh`, base EXPLICIT), and the comparison is
**Windows control → Windows train 8** through `tools/train8_compare.py` with
the Option-B accounting quarantine unchanged: positive movement on the 208
non-native shas reported separately and never counted as historical-comparable
gain, negative movement a real regression investigated normally, the per-sha
table kept. The historical batch-7 record — 2,469 / 17 / 72 / 809 / 13 over
3,380 shas — stays the historical reference; the control run neither rewrites
nor replaces it; it is the regression-attribution and current-environment
base.

**Train tooling made explicit on `train8` (`eb7100c`):**
`tools/train/winrun.py` (+ `tests/test_winrun.py`, 3 pass) — a Windows
Job-Object runner: committed-memory cap (the child fails with `MemoryError`,
the host is never taken — verified: a 1 GB allocation under a 0.3 GB cap dies
inside the child), job-wide timeout (exit 124), free-memory floor (125), peak
job memory and free-memory telemetry per run — the analogue of the Linux
`ulimit -v`/`timeout` wrappers §HYGIENE8 H6 and §FZ12 ran under;
`tools/train/provenance.py` — host / toolchain / tree / settings keys /
inventory / cache posture / env, written before and after every run;
`tools/train/control_b7.sh` — the control baseline (g1 dry run, g2 gate, g3
cold full run under winrun, g4 checker); `tools/train/coldrun.sh` rewritten —
base run dir and cold data dir are REQUIRED arguments, the run executes under
winrun with provenance, and the comparison is `train8_compare` with the
quarantine and `--fail-on-regression` (the silent default to
`discovery.compare` vs 356a4269 is gone). The FROST-OZK harness's guards
(`import resource`, RLIMIT_AS, `/proc/meminfo`) are Linux-only by
construction; its 41/39 verification stands from the Linux host and it is not
re-run here.

**HYGIENE-8a closure-completion session launched** (one Opus session, worktree
`mt8-hygiene8` @ `579f0bb`, no push): MAJOR-2 — the four `date()` sites routed
through `date_tokens`' guarded conversion with the refusal semantics
preserved, both-tree drives on invented 2031 fixtures, the four sites as
poison-sweep cells, an implicit-conversion census over the CHAIN_GUARDED
modules as a committed test, one mutant per site, zero movement re-proved by
the pinned replay and the family replay against the run of record (any mover
by sha, quarantine bucket stated); MINOR-4, MINOR-5, the rest of MINOR-6; the
closure floor under winrun, one process at a time; §H14 appended. Then Ocean's
deterministic verification → composition into `train8` → v16 + OCR v4 →
`PLANNED_REGISTRATIONS` reconciled with 83 → the `frost_period_packet.py`
disposition → `tools/train/floor.sh` → the archive/root scans → the pre-run
report Gustavo reviews before either archive run is launched.
* **2026-08-28 — HYGIENE-8a CLOSED, VERIFIED and COMPOSED (`96cba06` on `train8`; composition fix `504986e`; `wave8-hygiene8` tip `1be7e04`, pushed).** Closure-completion session (one Opus session, 1 h 45 min, `579f0bb` → `1be7e04`, nine commits): MAJOR-2 — the four `date()` sites (chase 12 / columbia_bank 7 / scotia 7 / scanned_small_bank 5 code lines) funnelled through `date_tokens` with the refusal semantics preserved, 12-cell both-tree drives (base echoes on `str`/`repr`/`args`/`traceback`; branch 0 leaking surfaces; in-range rows leaf-identical), four poison cells (census 11 sites / 64 cells: base 36 leaking → branch 0), the implicit-conversion census over the nine CHAIN_GUARDED modules as a committed test (74 calls: 66 provably cannot echo; **8 base-inherited echoing `date()` sites in bmo ×2 / farmers_merchants ×2 / td_can ×4 DISCLOSED**, enumerated so a ninth fails loudly), mutants M1–M4 killed; MINOR-4 (the bound is the C `int`; 5 source + 3 in-place W3 corrections), MINOR-5 (fixture dates to 2031; DATES census over the added lines 0), MINOR-6 a/b/d closed and (c) verified absent; §H14 (H14.1–H14.10). **Ocean's verification on this host at `1be7e04`:** production AST changed only at the four sites (`date_tokens.py`, `webapp/app.py`, `corpus_gate.py` AST-identical to `579f0bb`); W3 = merge-base log + one appended section; the whole instrument chain re-run under winrun, one process at a time — tests 288 / readers 260 / guards 253 / conformance 1,164 (registry 75), poison 36 → 0, overflow 11/11/8/7/0 + 2,765 of 3,351 against the run of record, pinned 109 / 108 identical / 1 refused both / movement 0 / 14 touched, family 618 documents (26 quarantined) / 625 replays / 613 identical / 12 raised on both / **0 movers** (the quarantined-movement table is empty), mutation 35 / 35 KILLED — all EXIT=0, peak 362 MB, no timeout, tree clean before and after; shared privacy scan over the 606 readable population documents: MONEY 0 / DIGITS 0 / DATES 0 / 12 furniture bigrams. **Rulings:** (1) the eight carried echoing sites are base-inherited, reach no user-facing surface (the dispatch seam reduces a crash to its class; `worker._stage_failure` withholds messages) and the census now guards against a ninth → **batch-9 card RAISE-PRIVACY-4** (three readers, the same funnel, the same drive), not a train hold; (2) the train's sweep population is the closure's wider census — **23 registrations in 19 modules** (H14.8), carried to the pre-run summary. **Composition:** helper merge with `--union corpus_gate.py` (25 excused callers; the union hunk ast-parsed and imported) and the W3 byte-exact rebuild (ours + §HYGIENE8 through H14 = 54,942 lines); registry unchanged at 83; `date_tokens.py` and `scanned_small_bank.py` auto-merged with SCAN-HYGIENE's hunks. The composed tree exposed two cross-cell interactions in the closure's TESTS (`504986e`, no production change): SCAN-HYGIENE's SS-UNIQUE-MATCH rebinds `_southside_summary`'s days read (`int(m.group(1))` → `int(days.group(1))`) — one census key renamed; and the population check compared to `10cc722..HEAD`, which on the train is every cell's change — now the branch's own `CHANGED_RANGE = (10cc722, 1be7e04)` with an ancestor check. Composed tree: hygiene8 288, readers 277, guards 255, conformance 1,270 (registry 83), caller-classification 24, **mutation table 35 / 35 KILLED (1,571 s, peak 469 MB)** — all EXIT=0. **Twelve of twelve cells composed.**
* **2026-08-28 — the bumps and the reconciliations (`train8` `152e904`, pushed):** `ANALYSIS_STAGE_VERSION` 15 → 16 and `OCR_STAGE_VERSION` 3 → 4 (`00a676b`; comment blocks in the batch-7 shape; the pin test's live assertion moved with its reason, 56 pass); `PLANNED_REGISTRATIONS` 80 → 83 with a `>= len(registrations)` pin in the corpus-marked test (`aa192e6`) — the re-measurement is the floor's corpus-marked slice on this idle host; `frost_period_packet.py` disposition = W3 §FZ14 (`152e904`): the "6 of 9" figure is downgraded to an unverified claim, nothing in FROST-OZK's +8 / +9 accounting rests on it, and the FROST-PERIOD ruling may not cite it until a committed instrument re-derives it (batch-9 `FROST-PERIOD-PACKET` only if the ruling is re-argued; recommendation stays REFUSE). Housekeeping: the 10 untracked batch-5 logs were MOVED (not deleted) to the session scratchpad (`batch5-logs-moved/`) because the hygiene8 harness refuses any untracked file; the main checkout's porcelain is empty. **Train-8 floor launched** at `152e904` (`tools/train/floor.sh` under winrun, cap 8 GB, idle host).
* **2026-08-28 — TRAIN-8 FLOOR at `152e904` (twelve cells, v16 / OCR v4 / registry 83 / PLANNED_REGISTRATIONS 83): ALL GREEN.** `tools/train/floor.sh` under winrun (cap 8 GB, idle host, one process at a time), 29.7 min wall, peak 2,420 MB, no timeout, porcelain empty before and after: full default suite **6,742 passed / 43 skipped / 0 failed** (`SUITE_EXIT=0`, 3 min 07 s); canonical guards **255** (`GUARDS_EXIT=0`); canonical conformance **1,270** / 40 skipped at registry 83 (`CONFORMANCE_EXIT=0`); corpus gate **GREEN** — 109/109 pinned hashes, 105 PASS / 3 WITHHELD / 1 REFUSED, verdicts 1 refused / 3 review / 102 validated / 3 withheld with the whole integrity block, currency 108/108 = 14 CAD / 94 USD (+1 pinned refusal), provenance 108/108 = 7 institution_default / 4 jurisdiction_default / 1 printed / 7 product / 89 schema_default (`GATE_EXIT=0`) — the card's floor, unmoved by twelve cells; corpus-marked slice **30 passed** (`CORPUS_EXIT=0`, 19 min 10 s), including `test_detect_sweep_stays_affordable_for_the_discovery_run` green at `PLANNED_REGISTRATIONS = 83` on this host — H10's re-measurement, done. Then `main`'s docs merged into `train8` (`99df4a8`, pushed) and the train's remote conclusion requested per the standing plan: `gh workflow run corpus-gate.yml --ref train8` → run **33195408456** (conclusion recorded below when read). The archive sweep (`tools.regfp_zero_movement_sweep` against the run of record, baseline key `24675EF0…`) and the root-base tree scans follow on the idle host.
* **2026-08-28 — remote CI on `train8` `99df4a8`: run 33195408456 concluded SUCCESS** (17:46Z; `workflow_dispatch`, the first of the two readings the standing plan names; the `main` reading follows the final merge).
* **2026-08-28 — the archive sweep at the composed tree, against the run of record.** `tools.regfp_zero_movement_sweep` reads the run's OCR artifacts by recomposing its cache keys from the tree it runs in, so it must run at the composed tree BEFORE the OCR v4 bump (H13 said so; a first attempt at `99df4a8` found `no_ocr_artifact` for all 3,380 and measured nothing). Run in a detached worktree at `504986e` (= the composed parser code; the only production difference to `152e904` is the two version constants, verified by diff), rows + cache of `356a4269`, baseline key `24675EF0…`, 2,096 s, peak 145 MB: **3,380 documents · 2,558 batch-7 payloads compared · 2,508 identical · 50 moved · 681 raise again · 112 no-payload → now publishes · 0 payload → raises · 29 without text · 74 multi-artifact.** Every finding attributed, deterministically, by sha (`SWEEP_ATTRIBUTION.md` in the session scratchpad; the ten unnamed shas below): **the 112 publishes** are the new registrations exactly, re-dispatched at the composed tree — bank_ozk 8 validated + frost 9 withheld (FROST-OZK), category_partition 5 (GLANCE), core_processor_signed_counts 8 + core_processor_activity_summary 6 (CORE-ISSUES-2), lili 11, welch_state_bank 17, core_processor_enclosures **47 validated + 1 review** (the cell recorded 46 / 1 / 1: its withheld document validates on the composed tree, a WITHHELD-GRIDS posting-date interaction the cold run names by sha) — 102 validated / 1 review / 9 withheld, which with WITHHELD-TD's 11 and WITHHELD-GRIDS' 16 lifts is the manifest's **+129**. **The 50 movers:** WITHHELD-TD 14 (its 11 lifts + 3 non-verdict), WITHHELD-GRIDS 18, SCAN-HYGIENE 8 (its 8 withheld payload movers, `integrity`/`metrics`/`quality` only) — 40 named by their cells' records — and **10 that no record names**: `community_section` ×7 / `mission_valley` ×3 (one module), natively read, verdicts unchanged (9 validated, 1 review), every differing leaf `statement.transactions[i].running_balance` with type **null → float** (20 leaves; `tools.withheldgrids_leaf_diff`, paths and types only). Mechanism: WITHHELD-GRIDS `af117fd` — a balance printed with a leading minus between the date and the `$` no longer breaks the `date whitespace money` match — reaching validated documents of the same reader outside the cell's recorded 429-document leaf-diff population; `164acda` (`tables.single_match`) is cleared (touched only lili.py/tables.py; community_section.py calls neither helper). Direction positive (gained printed readings), no verdict or ADB movement: **EXPLAINED and accepted as a named leaf move**, the ibc class — `1B41B7B514AE6992`, `25038CB7E38DB036` (review), `2C32F8464C452AB7`, `428C12F09FA49006`, `6EDE63132BFA0E60`, `E9CC87F0C6C50519`, `EB13FC00E76EE0F8`, `F2BF141B7DB2B060`, `F627F8CFC3D3A8AA`, `F8A0DCBA41B68C54`. DESC-COLUMNS is invisible to this sweep by construction (it reads the cached OCR text; the native-rung rotation is what OCR v4 re-reads) — the cold run is its measurement. HYGIENE-8a's expected zero inside its 618 holds (none of the 50 is in it).
* **2026-08-28 — root-base tree scans (`privacy_scan_branch.py --include-tree --base 19ec351`, scanned ref `99df4a8`; run from the `504986e` worktree because the scanner imports the cache module from its own tree — two earlier passes at v4 keys read 0 documents and are discarded as vacuous).** Whole run-of-record population (3,351 documents with text): after the standing exclusions (WORDS, round `.00`, `tests/corpus_cache/`), **11,678 candidates in 251 files**, split by `git diff 10cc722..99df4a8`: **10,884 in 221 files INHERITED** (the batch-9 FIXTURE-PRIVACY P0 population — larger than the Linux 861 / 98 because this universe is the whole archive, not the scanned families) and **794 in 45 files on batch-8-added lines** — tests 459 (invented fixture figures repeated across test files, e.g. LILI's, colliding with a 3,351-document token universe), docs/records 267 (session dates, counts, the census's figures), tools 47 (26 are digit substrings of hex shas in the quarantine file), and **21 in production files, all docstring examples or constants**: `analysis/lili.py:15–24` (the invented example statement), `analysis/core_processor_signed_counts.py:173–241` (docstring figures), `analysis/bank_ozk.py:62,126` (comment tokens), the `0.01` cent tolerance in `citizens.py:489` and `scanned_small_bank.py:693,816`. Each cell's population-scoped added-lines scan (base `10cc722`, the documents it read) was 0 / 0 / 0 or adjudicated on the branch, so none of these is a value taken from a document the cell worked on; under a whole-archive universe a small invented amount collides with something. Ruling: recorded, not adjudicated one by one at the train — the 21 production sites are named for the FIXTURE-PRIVACY sweep (move the docstring examples to the 2031 / invented-shape convention), the rest is that sweep's population. Per family (documents / candidates / batch-8-added / inherited): hygiene8 606 / 3,654 / 327 / 3,327 · scanhyg 41 / 1,183 / 75 / 1,108 · withheldtd 124 / 911 / 73 / 838 · coreenc 10 / 506 / 38 / 468 · glance 14 / 382 / 18 / 364 · withheldgrids 267 / 2,969 / 230 / 2,739 · cpscan 23 / 668 / 33 / 635.
* **2026-08-28 — the control worktree's cheap gates on this host, at `302f8f2`, cold throwaway cache (`control_b7.sh`, `CONTROL_STAGES="g1 g2"`, winrun floor 0.5 GB): G1 dry run 109 processed / deterministic coverage 108 of 109 / dedup unique 109 / validated 102 / review 3 / withheld 3 / failed 1 (the pinned refusal), `DRYRUN_EXIT=0`, 138 s, peak 160 MB; G2 corpus gate GREEN — 105 PASS / 3 WITHHELD / 1 REFUSED, verdicts 1 / 3 / 102 / 3, `GATE_EXIT=0`, 415 s, peak 1,050 MB.** The Linux G1/G2 (102 / 3 / 3 / 1) reproduce on Windows at the batch-7 tree. Two things the first attempt taught, both fixed in `2d7611c` before any archive run: the scripts exported `WEBAPP_DATA_DIR` from bash's POSIX-form `pwd` (Windows Python would have resolved it against the drive root — now `pwd -W`), and the runner's 1 GB free-memory floor refused the dry run on a host with the desktop apps open (exit 125, as designed; the archive runs keep that floor — close the apps). The throwaway cache (217 artifacts) was removed; the control worktree's own `webapp_data/` is ABSENT. **The train stops here for Gustavo's pre-run review; neither archive run is launched until he approves.** `train8` tip = this docs merge; the tools and the tree are frozen at it.
* **2026-08-28 — RULING (Gustavo, pre-run review): the ten `community_section.py` documents are ACCEPTED as named NON-VERDICT movement**, on the condition that every sha, every leaf, the direction and the attribution are durable here. Reader `community_section` ×7 / `mission_valley` ×3 (one module); every leaf below changed type **null → float** (a running balance the batch-7 run never read is now read); 20 leaves; verdicts unchanged; ADB and every gated field unmoved (`fields` = `statement` only, `detection` + `statement` on the review document). Attribution: **WITHHELD-GRIDS `af117fd`** — a balance printed with a leading minus between the date and the `$` no longer breaks the `date whitespace money` match; `164acda` cleared (touched only lili.py / tables.py; community_section.py calls neither `single_match` nor `unique_match`). Measured by `tools.withheldgrids_leaf_diff` at `504986e` against the run of record (paths and types only, no values):

| document (sha256, first 16 / full) | reader | class | leaves | leaf paths (all `null → float`) |
|---|---|---|---:|---|
| `1B41B7B514AE6992` — `1B41B7B514AE699247E7CF668D7AB0236300F57F38CEC56C15027B35C4F26A85` | `mission_valley` | validated | 1 | `statement.transactions.144.running_balance` |
| `25038CB7E38DB036` — `25038CB7E38DB036496B0CEBA3FA6BC3FC125647AC3F8487C5009FC6461D7CFD` | `community_section` | review | 4 | `detection.known_funders.0.transactions.0.running_balance`, `statement.transactions.68.running_balance`, `statement.transactions.88.running_balance`, `statement.transactions.9.running_balance` |
| `2C32F8464C452AB7` — `2C32F8464C452AB7F12845AC4838F00393E26C98D90768553A0D1834D3BE7135` | `community_section` | validated | 1 | `statement.transactions.40.running_balance` |
| `428C12F09FA49006` — `428C12F09FA49006B8347DB09F3AF41F7C91E174E5C8B62938CFF4E81F7E2495` | `community_section` | validated | 1 | `statement.transactions.15.running_balance` |
| `6EDE63132BFA0E60` — `6EDE63132BFA0E60FADCD78752FE51E0C37AB38655463CDB32B319928C8E31F9` | `mission_valley` | validated | 1 | `statement.transactions.9.running_balance` |
| `E9CC87F0C6C50519` — `E9CC87F0C6C50519723B57C10113B7A161EC930C929F905A6EF8D5EF17EF2BAB` | `community_section` | validated | 1 | `statement.transactions.3.running_balance` |
| `EB13FC00E76EE0F8` — `EB13FC00E76EE0F80D4F38C31905C18526FDF6BFF3423B641BF6DCE6380A34E1` | `mission_valley` | validated | 1 | `statement.transactions.12.running_balance` |
| `F2BF141B7DB2B060` — `F2BF141B7DB2B060FA73871D146CECFA0D9D4D36BFB0B1291E75F470768F87C3` | `community_section` | validated | 4 | `statement.transactions.159.running_balance`, `statement.transactions.161.running_balance`, `statement.transactions.162.running_balance`, `statement.transactions.164.running_balance` |
| `F627F8CFC3D3A8AA` — `F627F8CFC3D3A8AAD7B47DAD24D0A161566DDB31BD971710587409591A8A07B9` | `community_section` | validated | 2 | `statement.transactions.27.running_balance`, `statement.transactions.4.running_balance` |
| `F8A0DCBA41B68C54` — `F8A0DCBA41B68C54125F5021A01FDF523B0676739425AC49C402295785FC2C2B` | `community_section` | validated | 4 | `statement.transactions.41.running_balance`, `statement.transactions.85.running_balance`, `statement.transactions.91.running_balance`, `statement.transactions.94.running_balance` |

10 documents, 20 leaves.
* **2026-08-28 — PRE-RUN REVIEW (Gustavo): GO for the Windows batch-7 CONTROL run only; the train-8 cold run waits for another review.** Rulings: (1) the ten documents above — accepted as named non-verdict movement, now durable; (2) CORE-ENCLOSURES 46 / 1 / 1 → 47 / 1 on the composed tree is not a control-run blocker — the train-8 cold run must name the extra sha and its root cause before that gain is accepted; (3) the 21 batch-8-added production-code token collisions are adjudicated one by one (file / line / token / class / reason) BEFORE the train-8 cold run — generic algorithmic constants and docstring examples may be accepted, any archive-derived or customer-specific magic value is a blocker. Host safety: heavy applications closed and OneDrive paused before launch, ≥ ~6 GB MemAvailable confirmed, the same configuration for control and candidate; the execution-only minimum-available-memory floor rises 1 GB → **4 GB** in both scripts (`2a02926`; cap 10 GB; no parser semantic touched). When the control finishes the train STOPS and reports RUN_EXIT, the run directory, the five counts against the historical 2,469 / 17 / 72 / 809 / 13, G3/G4/G5, every per-sha discrepancy with native vs non-native counts, provenance / toolchain, peak RAM / runtime, and whether historical equivalence is established — if it is, the 208-sha quarantine CAN BE RETIRED for the final same-host comparison; if not, Option B stays and the exact remaining drift is named.
* **2026-08-28 — the 21 batch-8-added production-code token collisions, adjudicated one by one (Gustavo's pre-run ruling).** Method: beyond reading each site, every token was scanned against EXACTLY the documents its reader claims at the composed tree (the sweep's dispatch lists: LILI 11, CORE-ISSUES-2 14, Bank OZK 8; `privacy_scan_branch.py --shas … --base 10cc722 --ref 368000f`, from the `504986e` worktree so the v3 keys resolve; documents_read 11 / 14 / 8). **None of the 21 tokens is printed in the documents its reader claims** — the LILI population's MONEY hits are other cells' fixtures (`13.42`, `46.33`, `0.72`, `13.00`, `61.07`) and its DIGITS are 0; CORE-ISSUES-2's are GLANCE's `7.83` fixture, `30.94`, `2,750.00`, small record figures, DIGITS 1 (a record); Bank OZK's are CORE-ENCLOSURES' adjudicated `235.00` / `241.00`, DIGITS 0. The whole-archive collisions (11,678 candidates over 3,351 documents) are density coincidences. Verdict: **21 ACCEPT, 0 blockers.**

| # | file:line | token | classification | reason | verdict |
|---|---|---|---|---|---|
| 1 | `analysis/bank_ozk.py:62` | `000000` | invented docstring specimen | the §FZ10.3 placeholder account (`SAMPLE CHECKING* ACCOUNT - 000000`, 2027-dated); not printed in the 8 Bank OZK documents (DIGITS 0) | ACCEPT |
| 2 | `analysis/bank_ozk.py:126` | `72949` | institution furniture (public) | `_SERVICE_CENTRE_RE`: the bank's own service-centre address (P.O. Box 196, Ozark AR) used as issuer evidence — the same class as issuer names and toll-free numbers in registry markers; public, not customer-specific; not a new archive token on the population (DIGITS 0 under the base exclusion). Named explicitly because it is, by design, a printed public token | ACCEPT |
| 3 | `analysis/lili.py:15` | `137.41` | invented docstring example | the module docstring's self-consistent example statement (2027 dates, `999900000000`, merchant `A MERCHANT NOWHERE ZZUS`), mirrored by `tests/test_lili.py`; not printed in the 11 Lili documents | ACCEPT |
| 4 | `analysis/lili.py:18` | `13.27` | invented docstring example | as #3 (the example's fee) | ACCEPT |
| 5 | `analysis/lili.py:19` | `328.58` | invented docstring example | as #3 (the example's ending balance) | ACCEPT |
| 6 | `analysis/lili.py:22` | `170.78` | invented docstring example | as #3 (a running balance in the example chain) | ACCEPT |
| 7 | `analysis/lili.py:22` | `111111111` | invented placeholder | the example's authorization code (`111111111` / `222222222` / `333333333` pattern); DIGITS 0 over the 11 documents | ACCEPT |
| 8 | `analysis/lili.py:23` | `341.85` | invented docstring example | as #3 | ACCEPT |
| 9 | `analysis/lili.py:24` | `13.27` | invented docstring example | as #4 (the fee row) | ACCEPT |
| 10 | `analysis/lili.py:24` | `328.58` | invented docstring example | as #5 (the closing row) | ACCEPT |
| 11 | `analysis/citizens.py:489` | `0.01` | generic algorithmic constant | the one-cent tolerance `abs(read - printed) <= 0.01` | ACCEPT |
| 12 | `analysis/scanned_small_bank.py:693` | `0.01` | generic algorithmic constant (prose) | the comment recording that the floor "was 0.01 until W3 §SCANHYG SH13" | ACCEPT |
| 13 | `analysis/scanned_small_bank.py:816` | `0.01` | generic algorithmic constant | the one-cent tolerance on the ending balance | ACCEPT |
| 14 | `analysis/core_processor_signed_counts.py:173` | `731.66` | invented docstring example | the row-shape comment quotes the cell's own invented fixture (`tests/test_core_processor_signed_counts.py:35`: `Credits (3) +$1,326.43 … Debits (4) -$731.66`); not printed in the 14 CORE-ISSUES-2 documents | ACCEPT |
| 15 | `analysis/core_processor_signed_counts.py:215` | `306.29` | invented docstring example | fixture line 39, `BETA INBOUND … $306.29` (invented payee) | ACCEPT |
| 16 | `analysis/core_processor_signed_counts.py:223` | `103.71` | invented docstring example | fixture line 41, `SAMPLE ANALYSIS CHARGE $103.71-` | ACCEPT |
| 17 | `analysis/core_processor_signed_counts.py:224` | `107.29` | invented docstring example | the invented correction row `$412.09 S/B$304.80 $107.29-` | ACCEPT |
| 18 | `analysis/core_processor_signed_counts.py:224` | `304.80` | invented docstring example | as #17 | ACCEPT |
| 19 | `analysis/core_processor_signed_counts.py:224` | `412.09` | invented docstring example | as #17 | ACCEPT |
| 20 | `analysis/core_processor_signed_counts.py:241` | `1,647.77` | invented docstring example | fixture line 55, the grid pair `7/02 1,647.77` | ACCEPT |
| 21 | `analysis/core_processor_signed_counts.py:241` | `1647.77` | same token, separator stripped | the scanner counts each money figure with and without its separators — #20 again | ACCEPT |

Carried to batch 9 (FIXTURE-PRIVACY P0, not a train item): move the two docstring examples (`lili.py`, `core_processor_signed_counts.py`) to the invented-shape convention the tests already follow so they stop colliding with the archive by density; the inherited 10,884-candidate residue is that sweep's population.
* **2026-08-28 20:02Z — WINDOWS BATCH-7 CONTROL RUN LAUNCHED** (`control_detached.sh` → `tools/train/control_b7.sh`, stages g1 g2 g3 g4; worktree `b7-302f8f2` clean; corpus root = the main checkout's `Bank Statements`; cold cache `<worktree>/webapp_data` ABSENT at launch; `WEBAPP_DATA_DIR` in Windows form; winrun cap 10 GB / floor 4 GB / timeout 8 h; log `discovery_reports/train8-logs/CONTROL-B7-WIN-302f8f2.log`, terminator `control.meta`). Host quieted first: Chrome, Outlook, Teams, M365 Copilot and Widgets closed, OneDrive stopped (to be relaunched after the run), residual shell webviews and RuntimeBroker stopped; what stays resident is the VS Code instance hosting the train session (2.1 GB — its helper `13196` was verified to be the same instance, not a second one), the train's own `claude` processes, the Claude desktop app (0.9 GB, left alone), Defender and system services. **MemAvailable at launch 5.79 GB** of 15.3 — under the ~6 GB asked for by 0.2 GB after everything closable without ending the session was closed; launched on that basis and stated here plainly (the hard guards are the runner's 4 GB start floor and 10 GB job cap; the batch-7 gate peaked at 1.05 GB). G1 in the live run: `DRYRUN_EXIT=0`.
* **2026-08-28 20:10Z — control run STOPPED at the measurement stage by the 4 GB floor (`RUN_EXIT=125`), not by any defect.** In the live run G1 passed again on the real cold cache (`DRYRUN_EXIT=0`, 114 s, peak 160 MB) and G2 was GREEN (`GATE_EXIT=0`, 367 s, peak 1,052 MB); g3 was refused with **3,693 MB available** because Chrome (26 processes, 3.3 GB) had reopened on the host during the gate stage — the available figure went 5,920 → 3,697 MB across G2 while the gate itself peaked at 1 GB. The checker was skipped (no run directory). Nothing partial was produced: the only report directories under `CONTROL-B7-WIN-302f8f2/` are dry runs; the worktree's `webapp_data/` holds the dry run's 217 artifacts and will be REMOVED before the relaunch so the measurement run starts strictly cold (stages `g3 g4` only — G1/G2 are recorded twice on this host). OneDrive remains stopped. Relaunch waits for the host to be handed over quiet (Chrome closed, ≥ ~6 GB available) — Gustavo's call, since the browser was reopened by the user.
