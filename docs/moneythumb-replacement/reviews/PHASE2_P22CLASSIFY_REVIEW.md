# PHASE 2.2 P22-CLASSIFY — independent adversarial review

```
BRANCH        wave22-classify @ cb15b35   (reviewed detached in .claude/worktrees/rev22-classify)
BASE          train12 @ b23cb50
DIFF          git diff b23cb50...cb15b35   (13 files, +5421 / -1)
              layout/{__init__,signals,document_class,refusals}.py · tests/layout_fixtures/{__init__,builders,kinds}.py ·
              tests/test_layout_{boundary,document_class,signals}.py · tests/test_no_statement_hardcodes.py (roots append) ·
              tools/classify_census.py · W3 §P22CLASSIFY
REVIEWER      independent agent; wrote none of this code; read only the rulings, the umbrella, the card, the rules, the diff,
              the tests and the W3 section
HOST          Python 3.14.5 (3.12.10 present without fitz/pytest — byte-compile + import only), PyMuPDF 1.27.2.3; heavy proofs
              under discovery_reports/train12-logs/HARNESS.lock, one at a time, behind cell H's floor
VERDICT       APPROVE WITH FINDINGS   (2 MAJOR to close before composition; 12 MINOR; nothing blocks)
```

Every number below is one I measured in this worktree. `git status --porcelain` was empty before and after every
mutant; my harness refuses a dirty tree, restores `layout/` in a `finally` and re-verifies. Nothing was merged,
rebased, pushed or committed. The archive and the cold cache were opened read-only. No file name, printed value or
archive token from a customer document appears here (sampled cached text was read with every digit masked and
only in the terminal).

**The classifier is unwired, pure, boundary-clean, deterministic under hash randomisation, and its ruled
properties hold under attack. What does not hold is the precision of the kind on the table branch: a card
statement that prints ONE deposit-furniture word beside its card-shaped table becomes `STATEMENT_COMPLETE /
deposit` (MAJOR-1 — the same pair is a ruled conflict on the no-table branch; on the archive exactly 34 documents,
24 of them validated deposit statements, sit on that one word). A loan or brokerage statement with a payment
history is likewise a complete deposit statement (MINOR-10 — the loan lexicon fires on 180 table-bearing archive
documents, 130 validated, so it cannot serve as a conflict signal; the archive holds 0–1 such documents). R12 keeps
card / loan classes outside the CCL denominator until admitted, and the classifier-proposed denominator (D2, D10)
would admit a mislabelled one silently. The second MAJOR is a records defect: the W3 mutation table
records M4 KILLED (15), but M4 as the card and the W3 word it is an equivalent mutant on dead code and SURVIVES;
the property is enforced elsewhere and killed there (21).**

## 1. Claim-by-claim (claimed → measured)

| claim (W3 / card) | measured here |
|---|---|
| targeted tests: 512 passed / 3 skipped over the three layout files | 512 passed / 3 skipped (6.1 s); with the OQ2 guard file 583 passed / 3 skipped (11.5 s) |
| mutation table 20/20 killed | **19/20 killed as worded; M4 SURVIVES** (equivalent mutant on the dead `complete` conjunction); M4 re-worded against the findings rule KILLED (21); deleting the conjunction outright also survives (dead code) — §2 MAJOR-2 |
| `layout/` imports only stdlib + `evidence` (AST, any depth) | held: M12 (lazy `import numpy` in a never-called function) killed by `test_layout_boundary.py`; `import layout` under Python 3.12 drags nothing; byte-compiles on 3.12 |
| the classifier never reaches analysis / routing | held: no module outside `layout/`, `tests/test_layout_*`, `tests/layout_fixtures/`, `tools/classify_census.py` imports `layout`; every production `classify_document` is `telemetry.record.classify_document` (a different function with the same name — see MINOR-9) |
| pure / deterministic | held: identical verdict digest for all 52 fixtures × 2 modes under `PYTHONHASHSEED` 0, 1, 42, 12345; repeated calls equal; M8 (a `time.time()` step) killed by both the purity test and the import tripwire |
| `KIND_UNCERTAIN` on the named conflicts, never priority | held for the two card-named conflicts (M6a/M6b killed) and for two sub-kind lexicons without a table; **not held on the table branch** (§2 MAJOR-1, MINOR-10) |
| degraded mode never emits a box-dependent signal or a structural tier for one | held: M7 killed (51); none of my 36 synthetic documents emitted `table_alignment` / `micr_band` / `cheque_aspect` / `screenshot_frame` in text mode |
| `FILE_INVALID` from the facts alone, first | held (M10 killed 7; Java magic with a full statement's text → `FILE_INVALID`) |
| `Finding.detail` cannot carry document text | held: `x=abc`, `rows=5 Ending`, `a=1;;b=2`, `=1`, `Rows=1` refused; `rows=500.00` accepted (MINOR-6) |
| the census tool refuses a `--out` git does not ignore | held for `layout/ tools/ tests/ docs/ ./` (function and CLI, before the cache is opened); ignored paths inside the tree (`discovery_reports/`, `__pycache__/`) are accepted — the card's own contract |
| the OQ2 issuer scan covers `layout/` with an empty register | held: a scratch `signals.py` with `scotiabank` (EN tuple) or `desjardins` (FR tuple) is caught (1 hit each); the clean file 0; M9 killed |
| commit trailers; reword trees byte-identical | held: all 11 commits carry both trailers; `17b384b`/`4e36b6b` share tree `206d97f…`, `53f7efb`/`450134d` share `650b1c9…`; `cb15b35` adds only the W3 section |
| census native-pdf: 2,534 / 605 / 17 / 23 / 16 / 185 over 3,380; 461 validated exceptions; cache: 2,533 / 601 / 15 / 23 / 16 / 192; 422 | [PENDING-NUMBERS] |
| privacy scan 0 (added lines 4,884); message scan 0 over 10 commits | [PENDING-SCANS] |
| the one known suite failure is outside the diff | confirmed: `tests/test_run_of_record.py` is not in the diff; the diff touches nothing under `tools/train`, `telemetry`, `ocr`, `analysis`; not counted |

## 2. Findings

### MAJOR-1 — a card statement becomes `STATEMENT_COMPLETE / deposit` on one deposit-furniture word
The card rule on the table branch is `card lexicon ∧ single amount column ∧ no running balance ∧ NOT deposit_account`
(`document_class.py:1323`). The deposit axis is documented as "account_kind only; never decides a kind"
(`signals.py:254`), yet one word from it ("checking", "savings" — routine on a card statement's autopay line)
defeats the card rule, the document falls through to the statement branch, and the three anchors every card
statement prints (statement period, previous balance, new balance) make it complete. The no-table branch treats
the same pair as a conflict → `KIND_UNCERTAIN` (`:1299`); the table branch has no such rule.

```
python rev22_attacks.py   (scratchpad; fixture helpers only)
A1c card statement control          → NOT_A_STATEMENT/card_statement/lexical acct=card        (both modes)
A1a card statement + 'checking'     → STATEMENT_COMPLETE/-/structural acct=deposit findings=[] (both modes)
A1b card statement + 'savings'      → STATEMENT_COMPLETE/-/structural acct=deposit             (both modes)
B5  neutral-title card + 'Autopay from checking' → STATEMENT_COMPLETE/-/structural acct=deposit
```
Signals listed: `card_lexicon, deposit_lexicon, table_run, table_alignment, period_expression, opening_balance_label,
closing_balance_label` — the conflict is visible in the evidence and resolved by fall-through. **Archive footprint
(the cell's private native CSV, counts only):** 34 `STATEMENT_*` documents carry `card_lexicon`, every one in
exactly this shape (card lexicon ∧ deposit furniture ∧ table ∧ no running balance): 24 validated
`STATEMENT_COMPLETE / deposit` (deposit statements with card-like furniture — an overdraft or line-of-credit box —
kept as statements by the deposit word, which is deviation 4's intent) and 10 unresolved (6 COMPLETE, 4 PARTIAL)
that the same word may be misfiling in the other direction. Note `single_amount_column` is also true of every
debit/credit layout without a balance column, so the "card shape" is weak. **Close:** a recorded decision, not a
silent fall-through — either list the pair as `KIND_UNCERTAIN` on the table branch as on the no-table branch
(the 34 move to the uncertain class; the 24 validated are named), or strengthen the card shape (two strong card
phrases, a payment-due date, no deposit ledger header) — and fixture BOTH directions (a card statement with a
deposit word; a deposit statement with a line-of-credit box) with a mutant each.

### MINOR-10 — loan / brokerage lexicons are ignored beside any table; a running balance stamps `deposit`
The card's §5 makes the loan and brokerage sub-kinds decide only WITHOUT a table and names `KIND_UNCERTAIN`
"whenever signals conflict". On the table branch nothing reads the loan/brokerage lexicon at all
(`_decide` :1310–1325 handles only `card`), and `_account_kind` (`:1254`) returns `deposit` whenever a running
balance chains — before it looks at the firing lexicons. Rated MINOR, not MAJOR, on the archive evidence: the
loan lexicon fires on 180 table-bearing `STATEMENT_*` documents (130 validated deposit statements — "principal",
"interest paid", "loan number" are ordinary deposit-statement text), so it cannot be a conflict signal as it
stands; the B1 shape (loan lexicon ∧ table ∧ NO deposit furniture) occurs once (unresolved, `account_kind =
loan`) and never with a running balance. It is a generalisation risk on an unseen layout, not a measured defect.

```
python rev22_attacks2.py   (neutral titles; no deposit word anywhere)
B1 loan (principal balance, escrow, loan number) + running-balance history + 3 anchors → STATEMENT_COMPLETE acct=deposit
B2 loan + single-amount history + 3 anchors                                            → STATEMENT_COMPLETE acct=loan
B3 brokerage (holdings, market value, portfolio) + running-balance activity + 3 anchors → STATEMENT_COMPLETE acct=deposit
```
A mortgage statement with a payment history is not a deposit statement; R12 keeps loan and card classes reported
separately until admitted, and cell T has no field to separate B1/B3 from a chequing statement. **Close (when a
loan shape is designed):** a STRONGER loan shape (several strong phrases, no deposit ledger header) rather than a
blanket conflict, and `_account_kind` weighing that shape before the chain; document the residue meanwhile.

### MAJOR-2 — M4 as worded survives; the `complete` conjunction is dead code; the harness is not committed
`complete = period ∧ opening ∧ closing ∧ ledger` (`:1339`) is consumed only as `complete and not findings`, and
`_statement_findings` (`:1212`) already emits `missing_period/opening/closing` and `table_truncated`, so
`not findings` implies `complete`. The card's M4 ("require only two of the three anchors for
`STATEMENT_COMPLETE`") applied to that expression changes nothing:

```
python rev22_mutants.py <worktree> <log>       baseline 512 passed
| M4  | complete = signals.anchors >= 2 and ledger                        | SURVIVED (0) |
python rev22_m4b.py
| M4' | missing-anchor FINDINGS skipped when anchors >= 2                 | KILLED (21)  |
| M4''| complete = ledger  (the conjunction deleted)                      | SURVIVED (0) |
```
The cell's killer list for M4 (`test_missing_last_and_first_pages_are_named_by_the_marker_facts`) can only fail
when a finding is dropped, so the cell mutated the findings rule — the property holds and is tested. What does
not hold is the record: the W3 asserts "20 / 20 killed" for a table whose harness is a scratch script
(deviation 8) and whose M4 wording names a dead expression. Under BATCH9-RULES ("every mutant applied exactly as
documented"; "instruments that produce headline numbers are committed under `tools/`") this must close before
composition: delete the dead conjunction (or make it the gate), word M4 as applied, and either commit the harness
or attach its mutant edits verbatim to the W3. (P21-GEOMETRY's reviewer blocked on the same class of defect; here
the guarded property has a killing test, so MAJOR.)

### MINOR-1 — a prose cross-reference is taken as the page marker → false structural partial
`_markers` keeps the FIRST marker line per page. A complete 3-page statement whose page 1 prints "See page 2 of 3
for fees" above its footer: `STATEMENT_PARTIAL{page_gap}` at tier **structural** (both modes); the same sentence
below the footer → complete. (`rev22_attacks3.py` C1/C2.) Prefer the last marker on the page, or the one with the
fewest other words on its line.

### MINOR-2 — two statements in one file: a truncated second sequence is complete, and the W3 risk note is stale
The clean-restart rule (`:1194`) accepts `1 of M` after a finished sequence but never asks the second sequence to
finish: complete statement (1 of 1) + page 1 of 3 of a second statement → `STATEMENT_COMPLETE`, no finding (A9;
A10 likewise). The W3 "Risks last" says a restarting sequence "reads as a page gap (74 in the archive)" — the
code no longer does that (page_gap is 10 in both censuses); the note describes the pre-M14 rule.

### MINOR-3 — the illegible floor ignores modality; the stacked-label rule reads prose
A thin DIGITAL page with three anchors and no ledger → `STATEMENT_ILLEGIBLE` (A4) — a native text layer cannot be
illegible. A prose page "Opening hours are extended / balance ($) v v … Closing early on holidays / balance ($) v v"
earns both stacked labels and lands in the same bucket (A21). Archive count of `STATEMENT_ILLEGIBLE` is 0 in both
modes, so no measured impact; the E-class placeholder should require a scanned / image-backed modality.

### MINOR-4 — a ledger row's date range satisfies the period anchor
Rule (b) (`:678`) accepts `<date> - <date>` on any line; rule (d) excludes money-bearing lines, (b) does not. A
period-less statement with one row "HOLD <date> - <date>" → `STATEMENT_COMPLETE` (A16). Skip lines that carry
money tokens, as (d) does.

### MINOR-5 — `is_micr_shaped` accepts dates and long numbers
`-` and `.` are in `MICR_SYMBOLS`, so `2031-03-05 1234567890 123456`, `03-05-2031 …`, `12.345.678 1234567890`
are MICR-shaped (A14); a one-anchor fragment with such a line → `NOT_A_STATEMENT{cheque_image}` (lexical). Require
at least one of the four E-13B glyphs or their OCR confusions (`⑆⑇⑈⑉ : ; | c a`) and exclude date shapes.

### MINOR-6 — `Finding.detail` grammar admits money-shaped strings; `page_text_chars` is never read
`[0-9./-]+` accepts `rows=500.00` (A17). No writer emits one today; tighten to integers and `a/b` page pairs.
`DocumentProfileFacts.page_text_chars` is validated, then unused by any rule.

### MINOR-7 — evidence mode is strictly weaker than degraded mode on a three-column single-amount layout
`_aligned` keeps the two largest right-edge clusters; a table whose single amount rotates over three columns
(≈ 67 % covered < 80 %) has no table in evidence mode (`STATEMENT_PARTIAL{table_truncated}`) and a table in text
mode (`STATEMENT_COMPLETE`) on the same words (A27). Boxes should never make a verdict worse than no boxes.

### MINOR-8 — the census tool fails open without `git`; the W3 names its CSVs at the wrong root
`_refuse_tracked_out` falls back to `"discovery_reports" in path` on `OSError` (`classify_census.py:65`), which
accepts `layout/discovery_reports_x.csv` on a host without git; fail closed instead. The W3 cites
`discovery_reports/train12-logs/p22classify-census-native.csv`; the files exist only under the CELL's worktree
(`.claude/worktrees/mt22-classify/discovery_reports/train12-logs/`), not beside the logs at the repo root.

### MINOR-9 — the name `classify_document` now exists twice
`layout.classify_document` (kind) and `telemetry.record.classify_document` (outcome fold) — the umbrella
prescribed the name, and the L1-S2 fold guard's `SEARCHED_TREES = ("analysis", "telemetry")` does not cover
`layout/` (correctly: it is not an outcome fold). A note for cell T's wiring and for anyone grepping; no change
asked of C.

### MINOR-11 — a hyphen-joined date range is invisible to the date grammar; "statement dates" misses the lexicon
`DATE_RE`'s guards `(?<![\d/.-])` / `(?![\d/.-])` refuse a date that touches a `-`, so the compact range many
core systems print reads as NO date at all: `STATEMENT DATES 03/01/31-03/31/31` → dates `[]`, period `[]`;
`period 03/01/2031-03/31/2031` → `[]`; with spaces around the hyphen both dates parse. `statement dates`
(plural) also misses `statement date` (word-boundary alternation). All three sampled no-period validated
exceptions print exactly this line (§5). One-line fix: admit the hyphen when what follows is itself a full date.

### MINOR-12 — the cache-mode "page text" is not pure page text
The cached page text of at least one sampled document carries parser-encoded row lines of the form
`<TAG>|d/d|description||amount|balance` (a postprocess artefact in the OCR record's `pages`), which the
degraded-mode table signal counts as dated money rows. The cache census therefore reads ledgers native mode
does not (validated `table_truncated` 63 cache vs 106 native), and the W3's "degraded text" label overstates
its purity. A note for the measurement's consumers (cell T), not a code change for C.

## 3. Ownership, tripwires, records

* **Ownership:** every file in the diff is in the card's list. `tests/test_no_statement_hardcodes.py` gains a
  `LAYOUT_DIR` constant, one `modules.extend(...)` and a docstring line — the "roots append" the card allows
  (there is no roots tuple; deviation 1 is honest). `corpus_gate.py`'s register is untouched and the gate ran
  GREEN at the tree (`p22classify-gate.log`). `train12` (2c0ed5c) and the sibling branches `wave22-identity`,
  `wave22-holdout`, `wave22-fence` touch neither the guard file, `corpus_gate.py`, `layout/` nor the census
  tool — no composition hazard.
* **OQ2 reach:** eight scans (`removed literals`, `literal years`, `account numbers`, `exact amount constants`,
  `calendar fields`, `mojibake`, `scope not empty`, the issuer scan) iterate `layout/*.py`. Near-literal check:
  [PENDING-PHRASES]
* **Logs:** every W3 proof number matches its log (`p22classify-*.log`: suite 1 failed / 9,267 passed; guards
  275; conformance 1,282; gate GREEN; corpus 34; replays 47/47 identical at base and closure; privacy 0 over
  4,884 added lines; message scan 1 WORDS hit before the reword, 0 after). The master log shows the lock was
  held for the whole run.
* **Known failure:** `test_provenance_paddle_key_note_never_leaks_a_raw_exception_message` is outside the diff
  and its cause (host `.env` Paddle variables) is untouched by this branch.

## 4. The archive numbers, re-derived
[PENDING-CENSUS]

## 5. The validated exceptions — are they signal defects?
Sampled three per cause class (every k-th by sha, deterministic) from the native-mode per-sha CSV; cached TEXT
only, every digit masked, terminal only, nothing persisted. Cause-class counts (native, 461): closing label not
read 271 · no ledger read 106 · `KIND_UNCERTAIN` 50 · no period read 23 · no opening read 9 · page-break
discontinuity 1 · `NOT_A_STATEMENT{loan_statement}` 1.

| class | n | what the samples show (label forms only) | could a GENERIC rule read the anchor? |
|---|---:|---|---|
| closing label not read | 271 | 3/3 print no closing label anywhere — a per-page `BALANCE FORWARD` carried balance, or a debit/credit count-and-total box; the closing is the last running balance | not as furniture: "closing = last balance of the chain" is reconstruction (2.4). The cell's judgement stands |
| no ledger read | 106 | 3/3 print a dated ledger. One is a three-money-column layout (deposits / withdrawals / daily balance) — the MINOR-7 shape, dropped by the two-edge alignment cap; one prints multi-line descriptions with the amount two lines under the date (the wrapped-row rule reads one line) | YES for both shapes seen: a third alignment edge; a 2–3-line wrap window. Not only the "block-text artefact" the W3 names |
| `KIND_UNCERTAIN` | 50 | 3/3 one layout family: a summary box with `Beginning Balance` / `Ending Balance` labels, a strong card phrase inside a line-of-credit disclosure, deposit furniture, and NO ledger read → the no-table conflict rule | the conflict is honest; the ledger rows (`Checks Paid …` / `Other Debits …` sections) were not grouped as dated money rows — reading them moves the family to the table branch |
| no period read | 23 | 3/3 print `STATEMENT DATES d/d/d-d/d/d` | YES — MINOR-11, a one-line grammar fix |
| no opening read | 9 | 2/3 label the opening `LAST STATEMENT <date> <amount>` paired with `THIS STATEMENT <date> <amount>` (neither is in the opening/closing lexicons); 1/3 a Tesseract read | YES — the paired last/this-statement form is generic furniture (two different layouts in the sample) |
| page-break discontinuity | 1 | a 17-page statement; not judgeable from anchor lines | adjudicator |
| `NOT_A_STATEMENT{loan}` | 1 | a deposit statement whose ledger was not read and whose descriptions carry two strong loan words | a ledger signal defect, as the cell says |

**Judgement:** the cell's claim — every validated exception is a SIGNAL defect, never a document defect — held
for every sampled document. Its per-class diagnosis is optimistic in two places: the no-period class is a
generic grammar defect (MINOR-11), not "forms outside the lexicon", and the no-ledger class contains the
three-edge and deep-wrap shapes, both generic and fixable now, not only the block-text artefact. The closing
class (271, the majority) is correctly left to 2.4.

## 6. What I attacked and could not break
* **Unwiring (D2):** grep over the whole tree; no production import of `layout`; the census tool calls neither
  `analyze_markdown` nor `cached_analysis` (its only `analysis` import is the Phase 2.1 native reader).
* **Boundary (D1, case 5):** M12; AST tripwire sees a lazy import inside a function and a class body; `import
  layout` on 3.12 and 3.14 drags no platform or third-party module; no `print`/`open`/`environ` under `layout/`.
* **Determinism:** four hash seeds, one digest; two calls equal and equal-hashed; clock/random bombs (M8).
* **Disjointness:** exactly one kind on every one of 36 synthetic documents; the named conflicts (table ∧ cheque,
  card ∧ running balance, two sub-kind lexicons, deposit-slip/letter ∧ two anchors, sub-kind lexicon ∧ deposit
  furniture without a table) all refuse as `KIND_UNCERTAIN` with both signals listed.
* **Degraded mode:** no box-dependent signal in any text-mode verdict; structural only on a page-marker fact.
* **Cheque scoping:** a statement with a letter-size cheque enclosure stays complete; a statement with
  cheque-PROPORTIONED enclosure pages is `KIND_UNCERTAIN` in evidence mode — the ruled conflict, listed, not
  guessed (A15); a MICR line on the table page is not a cheque (fixture).
* **Completeness:** 0 rows with opening ≠ closing → `PARTIAL{table_truncated}`; 1 and 4 rows → complete on the
  short ledger; a coinciding pair with no rows → complete; the closing printed only as the last running balance →
  `PARTIAL{missing_closing}` (defensible: reconstruction, not furniture); page 1 removed → `missing_opening`
  (+ `missing_first_page` with markers); the last page removed after the closing → `missing_pages` with markers,
  complete without (nothing on the page says otherwise); a truncated ledger without markers → complete (the
  validator's coverage check owns that; the classifier is not a reconstruction).
* **`Finding.detail`:** the grammar refuses every text form I tried; `EvidenceRef.signal` refuses an unknown or
  differently-cased name; both inputs at once refused; no inputs → `KIND_UNCERTAIN`, not a crash.
* **Census tool:** `--out` on a tracked path refused at the door; opens the cache `mode=ro`; prints sha16 only.
* **Edge inputs:** zero-page evidence, an empty page, a 200k-character line → `KIND_UNCERTAIN`; a 900-row
  three-page document classifies in 0.2 s (evidence) / 0.4 s (text).
* **Records:** trailers on all 11 commits; reword trees byte-identical; `cb15b35` is the W3 alone.

## 7. What closing this looks like
MAJOR-1: a recorded decision on the card ∧ deposit-furniture pair (conflict → `KIND_UNCERTAIN`, or a stronger
card shape), fixtures in both directions, a mutant, the census re-run with the movement named by count (the 34).
MAJOR-2: delete or promote the dead conjunction, re-word M4 as applied, attach or commit the harness. The MINORs
are documented residue unless cheap (MINOR-1/-4/-5 are one-line fixes with a fixture each; MINOR-10 waits for a
loan shape).


## Re-review (closure tip 4a5f381)

```
REVIEWED      wave22-classify @ 4a5f381   (detached in .claude/worktrees/rerev22-classify; never modified; nothing merged or pushed)
CODE TREE     473f7d7 == 93f780c except ONE test string (tests/test_layout_signals.py:268, one six-digit run in a MICR negative); 4a5f381 == 473f7d7 + W3 only
BASE          train12 @ b23cb50 = merge-base(train12, 4a5f381); train12 has since moved by five docs commits touching none of the cell's files
CLOSURE DIFF  git diff cb15b35...4a5f381: 8 files, +871 / -34 (W3, layout/{document_class,signals}.py, tests/layout_fixtures/kinds.py,
              tests/test_layout_{document_class,signals}.py, tools/classify_census.py, tools/p22classify_mutation_table.py)
RE-REVIEWER   independent; wrote none of the code and none of the first review; every number below measured here
VERDICT       APPROVE WITH FINDINGS   (0 MAJOR; 4 new MINOR from the closure's own rules; every first-review finding CLOSED or allowed residue)
```

Scratch: `rerev_attacks.py`, `rerev_major1.py`, `rerev_hand_mutants.py`, `rerev_minor8.py` and their logs under the session scratchpad
(`.../scratchpad/rerev/`); the first reviewer's `rev22_attacks{,2,3}.py` and `rev22_csvstats.py` re-run unchanged. `git status
--porcelain` was empty in the worktree before every run and after the harness. Archive and caches opened read-only; the private CSVs were
read for counts only; no archive text appears here. Targeted baseline at the tip: **589 passed / 3 skipped** (6.0 s).

### Per finding

| finding | status | how verified at 4a5f381 (and at cb15b35 where a before/after matters) |
|---|---|---|
| **MAJOR-1** | **CLOSED** | `rev22_attacks.py` A1a/A1b and `rev22_attacks2.py` B5 → `KIND_UNCERTAIN` in both modes with `card_lexicon, deposit_lexicon, table_run` listed (at cb15b35, re-run: `STATEMENT_COMPLETE/deposit`); controls A1c/B4 still `NOT_A_STATEMENT/card_statement`. **Both directions:** `statement_with_strong_card_phrase_in_loc_box` → `KIND_UNCERTAIN`; my N7a (running balance + strong card box) → `KIND_UNCERTAIN`; `statement_with_overdraft_line_box` (weak furniture) → `STATEMENT_COMPLETE`. **Mutants:** M20 KILLED (5: `test_a_card_statement_with_one_deposit_word_is_a_conflict_not_a_deposit_statement`, the fixture table); my HM4 (conflict only in evidence mode) KILLED (3, same test). **Movement re-derived** (`rerev_major1.py` over the closure CSVs, counts only): card∧deposit = 71 (54 validated), every one `KIND_UNCERTAIN`, identical in cache and native; the strict shape (table, no running balance) = **34 (24 validated)** in BOTH modes; `STATEMENT_*` with both lexicons = 0. Cache-mode sha16 lists (first section 42 → closure log 66 validated `KIND_UNCERTAIN`): gained **24**, lost **0**, all 24 in the strict shape. Exactly the 34 / 24 the review named. |
| **MAJOR-2** | **CLOSED** | `grep 'complete = ' layout/document_class.py` → nothing; the gate is `if not findings` and `_statement_findings` emits every missing anchor and `table_truncated`, so the gate equals the ruled conjunction by construction. M4 AS APPLIED (missing-anchor findings skipped at two anchors) KILLED (18 — the W3 row still says 15) by `test_a_removed_anchor_is_a_partial_never_a_complete_statement` (+3). The harness is committed (`tools/p22classify_mutation_table.py`: refuses a dirty tree, `git checkout --` in a `finally`, re-verifies); my run: **28 / 28 killed, baseline 589, final tree clean, EXIT=0**; every killer name matches the closure's table. |
| MINOR-1 | CLOSED as reported; **see R-2** | `rev22_attacks3.py` C1 (cross-reference above the footer) → complete, no `page_gap`; M21 KILLED (3, `test_a_prose_page_cross_reference_is_not_the_page_marker`). My HM1 ("the LAST marker line wins") **SURVIVES** — the fixture cannot tell the closure's rule from a last-line rule; informational. A boilerplate footer defeats the new rule (R-2). |
| MINOR-2 | CLOSED as reported; **see R-3** | A9 / A10 → `STATEMENT_PARTIAL{missing_pages}` both modes; `statement_two_statements_one_file` still complete; M27 KILLED (3); HM3 (one owed page tolerated) KILLED (3, `test_missing_last_and_first_pages_are_named_by_the_marker_facts`). The stale W3 risk note is named in §3 residue — allowed (the first section is append-only). A restarted sequence's HEAD is still unchecked (R-3). |
| MINOR-3 | CLOSED as asked | A4 (thin DIGITAL) → `STATEMENT_PARTIAL{table_truncated}`; `statement_illegible` (scanned) still `STATEMENT_ILLEGIBLE`; M24 KILLED (3); HM7 (refuse only mixed) KILLED (3). Note: A21's prose still earns both stacked labels — it now lands in `PARTIAL{missing_period,table_truncated}`, not ILLEGIBLE; the review's close asked only for the modality guard. A MIXED thin document is still ILLEGIBLE (N8) — the review said "scanned / image-backed"; mixed pages can be scanned; accepted. |
| MINOR-4 | CLOSED | A16 → `STATEMENT_PARTIAL{missing_period}` both modes; M22 KILLED (3); HM5 (skip only money-before-dates) KILLED (3). Design cost noted (N5): a phrase-less, label-less merged line `<date> - <date>  Total fees <amount>` no longer supplies the period — by the review's own ask. |
| MINOR-5 | CLOSED as asked; **see R-1** | the five A14 strings → `is_micr_shaped` False; the one-anchor fragment → `KIND_UNCERTAIN` (was a lexical cheque); M23 (dash and dot readmitted) KILLED (5, `test_non_micr_lines`). Over-closed: a dash now disqualifies a line that carries genuine glyphs, and `'` `"` were dropped from the confusion set undocumented (R-1). |
| MINOR-6 | CLOSED; residue allowed | `rows=1.00`, `rows=500.00;page=1` refused; `page_break=0/1` accepted; HM2 (old grammar restored) KILLED (1, `test_the_contract_refuses_a_value_outside_its_vocabulary`). `page_text_chars` unused: documented in §3 as the review allowed. |
| MINOR-7 | CLOSED | A27 → `STATEMENT_COMPLETE/structural` in evidence, complete in text; `letter_with_unaligned_dated_lines` still a letter; M25 KILLED (2); HM6 (a one-row cluster counts) KILLED (3, incl. the letter test). Cost measured (N4): a form letter whose six dated fee sentences put amounts on THREE x positions (two each) is now a table in evidence mode → `KIND_UNCERTAIN` (cb15b35: `NOT_A_STATEMENT/letter`); the two-position form was already uncertain. Accepted as the review's trade. |
| MINOR-8 | CLOSED; residue allowed | `rerev_minor8.py`: `subprocess.run` raising `OSError` → `SystemExit` ("git could not be asked"); git answering 128 → refused; tracked `--out` (`layout/ tools/ docs/`) refused by function and by the CLI before any cache is opened; ignored paths accepted. The CSV location is documented in §3 (the files sit under the CELL's worktree, confirmed) — the review asked for the record, not a move. |
| MINOR-9 | residue, allowed | the review asked no change of C; §3 carries the note for cell T. |
| MINOR-10 | residue, allowed | B1 / B3 still `STATEMENT_COMPLETE acct=deposit`, B2 `acct=loan` (unchanged); the review's close was "when a loan shape is designed … document the residue meanwhile" — §3 does, with the R12 consequence stated. Closure CSVs: loan∧table `STATEMENT_*` 114 cache / 168 native (validated 90 / 120), all `account_kind=deposit` but one. |
| MINOR-11 | CLOSED for the full-date form; **see R-4** | `find_dates("03/01/31-03/31/31")` → 2; `statement_hyphen_joined_dates` and `statement_bare_hyphen_range` complete in both modes; `statement dates` in the lexicon; M26 KILLED (4) by both named tests — the bare-range fixture that isolates it is there (93f780c). The short m/d and ISO forms stay invisible (R-4). |
| MINOR-12 | residue, allowed | a note for cell T in §3; the census remains labelled cached page text. |

### New findings from the closure (ranked)

**R-1 (MINOR) — MINOR-5 over-closed: a genuine MICR line with the E-13B dash symbol read as `-` is no longer MICR-shaped.**
`is_micr_shaped("⑆111111111⑆ 22222-22222⑈ 1001")` → **False** (True at cb15b35); `"c111111111c 22222-22222c 1001"` → False (the fixture's
glyph-only line stays True). A cheque-proportioned
page carrying that line drops from `NOT_A_STATEMENT{cheque_image}/structural` to `/lexical` when the payee line is present (N3a) and to
`KIND_UNCERTAIN` without it (N3b; control with the fixture's glyph-only line: structural). The review asked for "at least one of the four
E-13B glyphs or their OCR confusions … and exclude date shapes"; the closure instead made any dash or dot disqualify the whole line, and also
dropped `'` and `"` from the confusion set without saying so (the first section's own positives used them; the closure rewrote those test
strings). Archive cost today 0 (`cheque_image` 1 lexical in both censuses at both tips — the archive's cheque pages are native-read
enclosures); the cost lands on 2.3's Paddle path, where scanned cheques arrive and ⑉ is routinely read as `-`. Close: require ≥ 1 glyph or
confusion among the non-digit characters and refuse a date-shaped digit run, rather than banning the dash; a positive fixture with the dash
beside a glyph; the five A14 negatives stay negative (they carry no glyph), so `test_non_micr_lines` and M23 are unaffected.

**R-2 (MINOR) — the "fewest other words" marker rule is beaten by a boilerplate footer.** Page 1 of a complete three-page statement whose
footer reads `Member FDIC Equal Housing Lender Page 1 of 3` (5 other words) and whose body prints `See page 2 of 3` (1 other word) →
`STATEMENT_PARTIAL{page_gap}` at tier **structural** in both modes (N1); the same footer without the prose line → complete (N1c). Identical at
cb15b35 — the closure did not introduce it, but the MINOR-1 rule as built trades one prose shape for another, and HM1 shows the fixture
does not pin "fewest words" against "last line". Close: prefer the candidate whose number continues the marker sequence (or equals the
expected page position) and fall back to the lowest line; a boilerplate-footer fixture beside the existing one.

**R-3 (MINOR) — the last-sequence rule checks a restarted sequence's TAIL but not its HEAD.** A complete statement (`1 of 1`) followed by
page `2 of 2` of a second statement (its first page missing) → `STATEMENT_COMPLETE`, no finding, both modes (N2); controls N2b / N2c
complete as they should be. The gap loop reads `1 → 2` as a continuation although the declared total changes (1 → 2); a total change is a
new sequence, and a new sequence that begins above 1 owes `missing_first_page` — the same guard the closure added for the tail. Close: treat a
total change as a restart; require a restart to begin at 1; fixture + mutant.

**R-4 (MINOR-low) — the hyphen fix covers only the year-bearing numeric form.** `find_dates("03/01-03/31")` → `[]` and
`find_dates("2031-03-01-2031-03-31")` → `[]`, while `03/01 - 03/31` yields two dates; `Statement Period 03/01-03/31` as the only period form →
`STATEMENT_PARTIAL{missing_period}` (N6a), the spaced form complete (N6b). Close: the same lookahead on the short `m/d` alternation (and ISO);
one fixture.

**Notes (no action asked):** `Page 1 of 2031` and `… page 3 of 3 for account ending …` still parse as markers (pre-existing; C3 / N10). A duplicated
last page (`2 of 2` twice) → `page_gap` + `balance_discontinuity` (pre-existing, honest). The 900-row timing probe (B9) reads `STATEMENT_PARTIAL`
in both modes at both tips (the first review reported only its timing).

### Ruled properties — did the closure break any?
No. Harness at the tip: purity / clock (M8, 121), boundary (M12), degraded mode never structural on a box signal (M7, 59), conflicts never
by priority (M6a/M6b/M20), `FILE_INVALID` first (M10), issuer strings (M9) — all killed. No production module is in the whole-cell diff
(`b23cb50...4a5f381` names only `layout/`, `tests/`, `tools/`, the W3), so newly validated = 0 and payload identity hold by construction
(the cell's replays 47 / 47 identical at base and at 93f780c; the code tree at the tip differs from 93f780c by one test string). R12: the
24 validated deposit statements now proposed `KIND_UNCERTAIN` shrink the classifier-PROPOSED CCL denominator by 24 — the ruled direction
(refuse, never guess); adjudication decides them. The MICR narrowing (R-1) weakens a structural signal on an unfixtured OCR confusion; it
breaks no ruled case (case 3's "without MICR → uncertain or lexical, never structural" still holds).

### Mutation table re-run (`python tools/p22classify_mutation_table.py` at 4a5f381)
Baseline 589 passed; **28 / 28 KILLED**; survivors `[]`; final tree clean (`git status --porcelain` empty). Per mutant: M1 (7) · M2 (4) ·
M3 (4) · M4 (18) · M5 (3) · M6a (2) · M6b (4) · M7 (59) · M8 (121) · M9 (1) · M10 (7) · M11 (4) · M12 (1) · M13 (3) · M14 (3) · M15 (3) ·
M16 (3) · M17 (2) · M18 (3) · M19 (3) · M20 (5) · M21 (3) · M22 (3) · M23 (5) · M24 (3) · M25 (2) · M26 (4) · M27 (3); the first-named
killer of every closure mutant is the test the W3 names. Hand mutants (same harness functions): HM1 SURVIVED (informational, above);
HM2 (1) · HM3 (3) · HM4 (3) · HM5 (3) · HM6 (3) · HM7 (3) KILLED.

### Scans (lock `HARNESS.lock` held 10:59:54 – 11:00:48, released with the logs' `EXIT=` lines written)
* `tools/privacy_scan_branch.py --base b23cb50 --ref 4a5f381` over the run-of-record population (3,380; 3,351 with cached text):
  `added_lines` **6,258**, `hit_count` **0** (DATES 0 / DIGITS 0 / MONEY 0 / WORDS 0); raw candidates 233 excluded by the shape rules
  (`words_class` 223, `hex_sha_substring` 10); EXIT=0 → `discovery_reports/train12-logs/rerev22classify-privacy.{log,md}`.
* `tools/huntington_msg_privacy_scan.py` over `git log b23cb50..4a5f381 --format=%B`: `commits_scanned` **16**, `hit_count` **0**; EXIT=0 →
  `rerev22classify-msgscan.log`.
The cell's own post-restatement logs (`p22classify-privacy.log` 02:39, `p22classify-msgscan.log` 02:40) read the same: 0 / 0.

### Numbers, ownership, records
* **Headline numbers vs the logs** (`p22classify-census-{cache,native}.log`, run at 93f780c): cache 2,518 / 581 / 15 / 23 / 16 / 227 = 3,380
  and 324 / 217 / 15 / 22 / 16 / 161 = 755, validated exceptions **431**; native 2,534 / 572 / 17 / 23 / 16 / 218 and 369 / 186 / 17 / 22 / 16 /
  145, **460** — every figure in the closure section matches its log line, and the closure CSVs reproduce them exactly (`rev22_csvstats.py`).
  Guards 275, conformance 1,282 / 41, gate GREEN 105/3/1, corpus 34, suite 1 failed (the known `test_provenance_paddle_key_note…`) / 9,344,
  replays 47 / 47 identical at base and closure — all as logged, every log ending in `EXIT=`. I did not re-run the full suite; the code tree
  at the tip is 93f780c plus one test string, and that file passes here (in the 589).
* **Ownership:** every closure file is on the card's list except `tools/p22classify_mutation_table.py` — the Ocean-directed widening the
  closure names. `tests/test_no_statement_hardcodes.py`, `corpus_gate.py` and the production packages are untouched by the closure.
* **Trailers:** `ce20ba3`, `93f780c`, `473f7d7`, `b487c3e`, `4a5f381` each carry `Co-Authored-By` and `Claude-Session`.
* **Records defects (for Ocean, not blocking):** (a) the closure §6 says "the first section is append-only (never edited)" and its last
  paragraph records the in-place restatement of two durations — say one thing; (b) the closure's M4 row keeps the first section's "(15)";
  at the closure tip M4 kills 18; (c) the harness log lives "in the scratch directory", not under `discovery_reports/train12-logs/` — this
  re-run is the durable record until the composed-tree run; (d) the W3 says the post-restatement scan counts are "in the closure message" —
  the `4a5f381` message carries none; they are in the two logs above (0 / 0) and re-derived here; (e) the first review as committed on
  `train12` still carries four unfilled `[PENDING-*]` placeholders (§1 numbers and scans, §3 phrases, §4 census) — the first reviewer's
  defect; the numbers and scans are supplied by this section.

### Verdict
**APPROVE WITH FINDINGS.** Both MAJORs are closed for the right reason and pinned (M20, M4-as-applied, the committed harness); the ten MINORs
the cell built are closed and each has a killing mutant; the four residues are the ones the first review allowed and are documented. The
closure introduces one over-narrowing of its own (R-1) and leaves three siblings of the rules it added (R-2, R-3, R-4) — all MINOR, none a
ruled property, none blocking composition; I would close R-1 before the 2.3 Paddle wave reads scanned cheques.
