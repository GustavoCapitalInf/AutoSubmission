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
