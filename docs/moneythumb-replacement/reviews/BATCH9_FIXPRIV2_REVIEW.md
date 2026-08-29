# BATCH 9 REVIEW — FIXTURE-PRIVACY-2 (`wave9-fixpriv2`, base `d2ab046`, tip `2ed171c`, 23 commits)

Independent adversarial review. I did not write this code, I asked the cell nothing, and every
headline number below was re-measured by me from the committed instruments, one heavy process at
a time. Ocean composes; I never merge or push.

**Tree:** worktree `.claude/worktrees/mt9-fixpriv2`, branch `wave9-fixpriv2`, base `train9`
`d2ab046` (carrying the composed FIXTURE-PRIVACY `2b5d8a7` and RAISE-PRIVACY-4 `a1f7f32`), tip
`2ed171c`.
**Read:** `docs/agent-handoffs/BATCH9-RULES.md` (and the newer copy on `train9` — see MINOR 3);
`docs/agent-handoffs/FIXTURE-PRIVACY-2.md`; the branch's W3 section `§FIXPRIV2` (F2-1…F2-9); the
full `d2ab046..2ed171c` diff, commit by commit; my own two prior reviews of the predecessor card.
**Instruments, absolute paths passed explicitly:** run of record
`discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d/rows.csv`; cold cache
`.claude/recovery/webapp_data_train8_cold` (READ-ONLY); root commit `19ec351`. The CP-DECLINES
cell's python was live for most of this review, so the mutation harness was held until the host
was clear, per the rules.

## VERDICT: **APPROVE WITH FINDINGS** — 0 BLOCK, 2 MAJOR, 3 MINOR

This is the strongest card of the three I have reviewed in this family. The central claim — that
+28 years is a calendar identity and therefore a date can be *moved* rather than invented — is
true, and I proved it independently rather than taking the cell's proof. The sweep is large (82
test files), and once dates are blinded, **76 of the 82 files are byte-identical**; the six that
are not are explained by shapes my blinder does not model, plus two new files and the expanded
exclusion suite. Coverage movement is zero by construction: no production module appears in the
diff at all, and the full suite is green at 7,254 with the corpus gate GREEN.

Both MAJORs are about instruments and counts rather than about the tree: a shift tool that
silently edits two things that are not dates, and a residue class that is described as
never-excused and is in fact excused 327 times. Neither can move a document; both matter because
FIXTURE-PRIVACY-3 is already carded and will reuse the first, and because the second is an input
to Gustavo's ruling R3.

---

## RE-MEASUREMENT TABLE

| # | claim | my re-measurement | exit | verdict |
|---|---|---|---|---|
| 1 | whole tree 9,378 / 209 at base | **9,378 sites / 209 files**, 3,351 documents read | 1 | reproduces |
| 2 | whole tree 7,533 / 200 at tip | **7,533 / 200**, 3,351 read | 1 | reproduces |
| 3 | `tests/` DATES 1,971 → 126 | **1,971 → 126**; and every other class × directory row is **identical** base to tip, so the sweep moved DATES in `tests/` and nothing else | 1 | reproduces |
| 4 | the six files left, 358→72 / 25 / 13 / 7 / 7 / 2 | exactly: `test_analysis.py` **72** (66 distinct lines), `test_huntington.py` **25**, `tests/data/parser_expectations.json` **13**, `test_new_statement_corpus.py` **7**, `test_balance_metrics_audit.py` **7**, `test_transaction_classifier.py` **2** = **126** | — | reproduces |
| 4b | those six are pinned-document truth | the 72 sites in `test_analysis.py` fall inside **8** definitions, every one a `test_*_source_pdf_*` / `test_parse_*_reconciles_*` that asserts about a named pinned PDF. Fair characterisation | — | confirmed |
| 5 | no file gains residue; no new token | site-set diff base→tip: **NEW sites 0**; 79 files change count and **none gains** | — | reproduces |
| 6 | `tests/` MONEY 1,392 / 71 files and DIGITS 678 / 73 files, unchanged | **1,392 / 71** and **678 / 73**, identical at both trees; **58 files carry both** | — | reproduces |
| 7 | `benchmark_truth_csv` 1,004 on both trees | **1,004** at base and at tip (555 MONEY / 366 DATES / 83 DIGITS) | — | reproduces (but see MAJOR 2) |
| 8 | `institution_zip` strictly narrower, all 83 sites still claimed | judged every 5-digit DIGITS hit at the tip under **both** rule versions: excused by both **166**, excused by the OLD rule only (the cost) **0**, excused by the NEW rule only (a widening) **0** | — | reproduces — strictly narrower, zero live cost |
| 8b | the predecessor's MAJOR-A residual | `PO BOX <n> CCD CO# <5> TRACE` is now a **HIT**. All eight cases behind the original BLOCK and MAJOR 4 still report | — | closed |
| 9 | +28 is a calendar identity | my own walk, 1995-01-01…2035-12-31: **14,975 days, 0 weekday mismatches, 0 Feb-29 without an image, 0 month-length mismatches** over 41 years × 12, and **0 mismatches in `analysis.adb._federal_bank_holidays` (month, day) across all 41 year-pairs** | — | reproduces |
| 9b | the identity's boundary | it genuinely breaks past 2100 (2073-01-01 and 2101-01-01 differ in weekday; 2072-02-29 has no image). **No fixture goes there:** every shifted year lands in 2047…2060, and every added Feb-29 year is a leap year | — | confirmed, bounded |
| 9c | Juneteenth / year-dependent holidays | `analysis/adb.py:96-139` counts Juneteenth **in every year** by construction, with no year bound, so a date shifted from before 2021 to after gains nothing | — | counter-example refuted |
| 9d | two-digit-year pivot | `date_tokens.iso_from_month_day_year` adds 2000 only to years below 100 (`short`) or unconditionally (`always`). There is no 68/69-style pivot, so `yy` 26 → 54 cannot flip century | — | counter-example refuted |
| 9e | collision with the 2031 convention or the `docs_session_date` era | no real fixture lands on 2031 (every added 2031 is inside the shift tool's own tests); `docs_session_date` is bounded to `docs/` and the sweep is in `tests/`; and the scan's NEW-token count is 0 | — | confirmed |
| 10 | test meaning unchanged | date-blinded byte comparison of all 82 changed test files: **76 date-only**; of the six residuals, four are the Canadian `MON DD/YY` and French `DD MON YY` header forms my blinder does not model (all correctly +28), two are new files, one is the expanded exclusion suite — and **two are real defects** (MAJOR 1) | — | reproduces, with MAJOR 1 |
| 11 | added-lines scan 0 over 3,967 lines | **0 hits / 0 sites over 3,967 added lines**, 3,351 read | **0** | reproduces |
| 12 | commit-message scan 0 over 640 lines | **0 archive tokens** over **640** message lines, scanned with the branch's own tokeniser, base-tree subtraction and exclusion table | — | reproduces |
| 13 | W3 = base + one section | base 56,384 → tip 56,707 lines; prefix **byte-identical**; exactly **one** appended `#` heading | — | reproduces |
| 14 | exclusion tests 175 → 223 | **223 passed** | **0** | reproduces |
| 14b | the new instrument suites | `test_fixpriv_shift_dates.py` **131 passed**; `test_fixpriv_mutation_table.py` **14 passed** | **0** | reproduces |
| 15 | canonical guards 255 | **255 passed** | **0** | reproduces |
| 16 | canonical conformance 1,270 | **1,270 passed, 40 skipped** | **0** | reproduces |
| 17 | suite 7,254 passed | **7,254 passed, 43 skipped, 34 deselected, 0 failed**, 4 min 16 s. The two failures inherited through the previous cards are gone | **0** | reproduces |
| 18 | gate GREEN 105 / 3 / 1, 14 CAD / 94 USD | **RESULT: GREEN**, 105 PASS / 3 WITHHELD / 1 REFUSED, 109 pinned PDFs, 0 exclusions, 14 CAD / 94 USD | **0** | reproduces |
| 19 | corpus-marked 30 | **30 passed**, 7,301 deselected, 26 min 58 s | **0** | reproduces | | |
| 20 | mutation table 63/63 | **63 mutants / 63 killed / 0 survived**, run without `-x`, host clear, tree clean before and after; every claimed new mutant present — `M11g`–`M11j`, `S1`, `N1`, `N2`, the harness's own gate `H1`–`H4`, the shift tool's `Z1`–`Z16`, `D1`/`D2`, `L1`–`L4` | **0** | reproduces | | |
| 21 | ownership | 88 files: `tests/` `tools/` `docs/` only, plus the two deleted root logs. `tests/test_huntington.py` **untouched**. `tests/test_privacy3_boundaries.py` **is** touched — permitted, because RAISE-PRIVACY-4 was composed at `a1f7f32` and is in the base; the edit is a pure +28 on canary fixtures that preserves the invalid month/day canaries | — | respected |
| 22 | the deleted logs | 4 references remain at the tip and **every one is prose** (the card, `BATCH9_TRANSITION.md`, `§FIXPRIV`, my own earlier review). No tool, test, CI file or import reads either. Both blobs remain reachable at `d2ab046` | — | confirmed |

## THE HARNESS (claim (a)), PROBED AT POINTS ITS OWN TESTS DO NOT REACH

I did not re-run the shipped 14 tests as evidence of themselves; I attacked the three failure
modes that matter, and the tree was verified clean after each.

| probe | result |
|---|---|
| **A. the aftermath of a hard kill** — a mutant planted on disk, as if the interpreter had been killed between the mutant write and the `finally` | the next run **refuses to start, exit 3**, and does not clobber the planted file. This is the defence the new rules ask for, and it is the only one that can work: no `finally` survives a kill |
| **B. `_restore` with git dead AND every content write failing** | raises **nothing**, exactly as documented, and returns with the mutant still on disk — which is why the caller's verification, not `_restore`, is the gate. Sound design |
| **C. `git status` unanswerable** | `_porcelain()` returns **None** after its retries and `run()` **refuses, exit 3**. My first attempt at this probe injected a `RuntimeError`, which `_git` cannot raise; with the real `CalledProcessError` the contract holds. **No finding** |

## FINDINGS

### MAJOR 1 — `tools/fixpriv_shift_dates.py` silently shifts things that are not dates

Two proven instances, found by blinding every date in both versions of all 82 changed files and
requiring the remainder to be byte-identical:

* **`tests/test_bmo_layouts.py:414`** — the fixture is a `Checks in Serial Number Order` table
  whose columns are `Date | Serial Number | Amount`. The tool read `Apr 02 1001` as a spelled
  date with a four-digit year and shifted the **cheque serial numbers** `1001` and `1002` to
  `1029` and `1030`.
* **`tests/test_declines_c_variants.py:192`** — a docstring containing the literal escape
  sequence `—` (an em dash). The tool read the escape's four hex digits `2014` as a year and
  produced `⁂`, which is a different character (an asterism). In a non-raw docstring the
  text really did change.

Neither is a privacy or correctness regression **in this tree**: no assertion pins the serials
(`grep` finds them on that one line only), the escape is in a docstring rather than a live
literal, all four values are four digits and therefore below the scanner's `--digit-min` so they
were never residue, and the suite is green. The change bought nothing and cost two silent edits.

It is a MAJOR because the tool is **committed for reuse** and `FIXTURE-PRIVACY-3` is already
carded to run it over the MONEY/DIGITS half, where fixtures are dense with four-digit cheque
numbers, and because the same mechanism inside a live string literal would be a behaviour change
that no test would necessarily catch. The guard already half exists — the tool refuses year
`0000`, which is why `April 4, 0000` in `test_privacy3_boundaries.py` survived untouched — so the
fix is to extend that bound to a plausible calendar range (1900–2100) and to refuse a match whose
digits are the tail of a `\uXXXX` escape. I measured the whole sweep: **exactly 1 escape altered
and exactly 2 implausible-year shifts**, so the closure is small and complete.

### MAJOR 2 — `benchmark_truth_csv` is described as never-excused and is excused 327 times

`tools/privacy_scan_branch.py`. The card asks for the three `docs/*-audit-results.csv` files to be
"reported as their own class … COUNTED and named" pending ruling R3, and the record and the
`_docs_session_date` docstring make the principle explicit: *"Counting a class and then letting an
exclusion silence part of it would make the count a lie."* The carve-out
(`residue_class(path) is None`) was added to **`_docs_session_date` only**.

Measured inside those three files at the tip:

| | sites |
|---|---:|
| counted as `benchmark_truth_csv` | **1,004** |
| additionally silenced by `round_money` | 252 |
| additionally silenced by `subunit_money` | 65 |
| additionally silenced by `hex_sha_substring` | 10 |
| **non-WORDS sites the class does not count** | **327** |

So the class understates itself by about a quarter, and the silenced remainder is not incidental:
these files are per-statement audited expectations, so a `.00` figure in them is a **real printed
balance**, which is exactly the case `round_money`'s own (now honest) docstring says it excuses by
choice rather than by safety. R3 is a ruling about how much archive content these files hold; it
should be made against 1,331, not 1,004, or against 1,004 with the remainder stated. Closure:
apply the same `residue_class(path) is None` carve-out to the other rules, or report a second
number — `residue_by_named_class_excluded` — beside the first.

### MINOR 1 — the entanglement figure does not reproduce

The record (F2-7) says *"82 of the 678 DIGITS sites are the INTEGER PART of a money figure — … a
figure printed without a thousands separator contains one."* Reading the real line for every one
of the 678 DIGITS residue sites in `tests/` and matching the token against the integer part of
**any** money figure printed on that line (not only ones that are themselves residue), I measure
**75**, and 75 again if the test is loosened to "the token is any substring of a money figure on
the line". 247 merely share a line with some money figure. The conclusion — that the two classes
are entangled and cannot be swept independently — is unaffected and correct; the number is not
reproducible from the definition given, and it sizes the next card. Either state the definition
precisely or carry 75.

### MINOR 2 — the city rule's residual is real, slightly broader than the record's phrasing, and its cost is one shape

The record names the residual as "a city-shaped word not in the list + a word-shaped
abbreviation". Confirmed, and worth sharpening: the substitute city need not be an
identity-introducing word at all — **any** word of four or more letters that is not on the
39-word list will do, including ordinary English. All of these are silenced:

`PO BOX <n> SERIAL OR <5>` · `PO BOX <n> FOLIO ID <5>` · `PO BOX <n> VOUCHER OR <5>` ·
`PO BOX <n> PAID IN <5>` · `TRANSFER FROM SAVINGS, IN <5>` · `ACME MANUFACTURING, CO <5>`

I could not construct a class outside the one the cell named, so the record's characterisation is
accurate as far as I can push it. The cost is also real and is not stated: a genuine address whose
city is **shorter than four letters** and which carries no comma is now reported —
`PO BOX 1 ADA OK <5>` is a hit. Live cost in this tree is **zero** (measured above), so this is a
note for the table's prose, not a change.

### MINOR 3 — the branch was written against the older standing rules

`docs/agent-handoffs/BATCH9-RULES.md` on this branch is 119 lines and is byte-identical to
`2f24b06`. The section Ocean's brief refers to — *"Surfaces the batch-9 reviews found unscanned"*,
covering commit-message scanning, mutation-harness restore safety and report files — exists only
on `train9` (135 lines) and was added after this cell's base `d2ab046`. The cell therefore could
not have read it, and nevertheless satisfies all three of its requirements: the message scan is 0
over 640 lines, the harness restores in a `finally` that ignores git's exit code and verifies
`git status --porcelain`, and the record is the W3 section rather than a scratch file. Worth
noting only so that the composed train carries the newer rules and the next cell inherits them.

## ANSWERS

**Newly validated = 0?** Yes — and by construction: **no production module appears in the diff**
(88 files: 82 `tests/`, 3 `tools/`, 1 doc, 2 deleted logs). `cohort_replay` is not owed, and
`fixpriv_ast_identity` has nothing to compare.
**Other ladder movement = 0? Regressions = 0?** Yes. The full suite is green at 7,254 with zero
failures, the corpus gate is GREEN with the pinned 105 / 3 / 1 and 14 CAD / 94 USD, canonical
guards 255 and conformance 1,270 all pass.
**Doctrine kept — no behaviour change, no hardcode, fail closed?** Yes. No registry change, no
version bump, no production code, no network, no hosted model, $0.
**Privacy of added lines = 0?** **Yes — 0** over 3,967 added lines, and **0** over 640 commit
message lines.
**Ownership respected?** Yes — see row 21.
**No archive content in this review?** Scanned with the branch's own instrument before committing;
the count is in the closing line.

## FOR OCEAN'S RULING

1. **R3, restated with a corrected number.** The three truth CSVs hold **1,331** non-WORDS residue
   sites, not 1,004, once the exclusion table's own silencing is counted (MAJOR 2). The ruling —
   governed truth data in a private repo, or moved out of `docs/` — should be made against that.
2. **The P0's original account number** still sits once in `docs/balance-metrics-audit-results.csv`,
   as I recorded in the predecessor's review. This card removed it from `tests/test_analysis.py`;
   the CSV copy is inside the R3 class and remains.
3. **`FIXTURE-PRIVACY-3` should not start until MAJOR 1 is closed** — it is carded to reuse the
   shift tool over files dense with four-digit identifiers.
4. **`test_huntington.py` (25 DATES sites)** was left by ownership while DECL-HUNTINGTON ran; now
   that DECL-HUNTINGTON is composed on `train9`, it needs an owner.
