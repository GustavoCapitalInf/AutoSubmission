# CP-DECLINES — independent adversarial review (batch 9, 9A-1 card 2)

Branch `wave9-cpdecl`, base `train9` at `71a82aa`, tip `b2ba776`, 11 commits, worktree
`.claude/worktrees/mt9-cpdecl`. Reviewer: an independent Opus cell that did not write the
card, asked the cell nothing, and re-measured every headline number rather than reading it.
Nothing here is merged or pushed; Ocean composes.

Everything below was measured against the run of record
`discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d` (`cda8882d`) and its
READ-ONLY cold cache `.claude/recovery/webapp_data_train8_cold`. Base-tree arms were run in a
private detached worktree at `71a82aa`. No archive value appears in this file.

## 0. Verdict

**BLOCK** — one BLOCK finding, narrow, with a remedy that costs zero documents; two MAJOR
record corrections; three MINOR. **Every count the cell claims reproduces exactly** (newly
validated 6 by sha, other movement 3 by sha, preserved 74/74 payload-identical, regressions 0,
all five base arms `--expect-identical` exit 0, mutation table 6 killed / M5 survived with the
57-document equivalence, all four ceilings, the gate table at the base tree, privacy 0). The
block is not a count: it is that `core_processor_enclosures._without_non_opening_dates` can
publish a posting on a day the bank did not print it, as `validated / approved`, and the
module docstring, W3 §CPDECL4 and the test that "kills" the mutant for it all assert that it
cannot.

## 1. Re-measurement table

| what | cell claims | this reviewer measured | agrees |
|---|---|---|---|
| base `71a82aa`, four `DECL:` groups, `--expect-identical` | EXIT 0 | 38 unchanged, EXIT **0** | ✅ |
| base, `--parser core_processor_sectioned` `--expect-identical` | EXIT 0 | 10/10 identical, EXIT **0** | ✅ |
| base, `--parser core_processor_enclosures` `--expect-identical` | EXIT 0 | 46/46 identical (+1 review +1 withheld), EXIT **0** | ✅ |
| base, `--parser core_processor_daily` `--expect-identical` | EXIT 0 | 13/13 identical, EXIT **0** | ✅ |
| base, `--parser category_partition` `--expect-identical` | EXIT 0 | 5/5 identical, EXIT **0** | ✅ |
| tip, four `DECL:` groups | newly validated 6, up 3, 29 unchanged, regressions 0 | identical, EXIT **0**; the 9 movers are exactly the 9 named shas | ✅ |
| tip, `--parser core_processor_sectioned` | 10/10 identical | **10/10 identical**, EXIT 0 | ✅ |
| tip, `--parser core_processor_enclosures` | 46/46 identical | **46/46 identical**, 2 unchanged non-validated, EXIT 0 | ✅ |
| tip, `--parser core_processor_daily` | 13/13 identical | **13/13 identical**, EXIT 0 | ✅ |
| tip, `--parser category_partition` | 5/5 identical | **5/5 identical**, EXIT 0 | ✅ |
| decline probe gate table (base tree) | GRAMMAR 24 (16 nat / 8 tess), IDENTITY 14 (1 / 13), TRACE-DISAGREES 0, L-1 0 | **identical at `71a82aa`** | ✅ |
| ceiling `sectioned_strip` | REACHABLE 0 / unreachable 22 | **0 / 22**; the eight-row native detail table reproduces cell for cell; 5 of 8 carry an `adjacency_disagrees` | ✅ |
| ceiling `sectioned_strip_search` | no_reading_exists 21, UNIQUE_READING 1, ambiguous 0 | **21 / 1 / 0** (`6BC052E9B49DB281`) | ✅ |
| ceiling `enclosures_cells` | 6 REACHABLE_BY_SKIP, 3 no_summary; 1–3 unclosed dates each | **6 / 3**; unclosed dates 1,1,1,3,1,1 | ✅ |
| ceiling `daily_cells` / the rule carried to `core_processor_daily` | 0 of 4 publish; 3 print no grid section | **0 of 4** publish under the rule applied in memory; grid section printed on 1 of 4; the 13 protected `core_processor_daily` documents are payload-identical under the same hypothetical | ✅ |
| Tesseract `core_processor_sectioned` ceiling | unreachable on all 14, strip cells disagree on 12 | **14 / 12** | ✅ |
| mutation table | 7 rows, 6 KILLED / M5 SURVIVED, tree clean after every row | **6 KILLED / M5 SURVIVED**; `git status --porcelain` empty afterwards, HEAD unchanged | ✅ |
| M5 equivalence (blanked vs removed) over 57 documents | identical 54, both declined 3, differ 0 | **54 / 3 / 0**, measured with my own removal implementation | ✅ |
| rotation, card population | 612 native, 24 rotated-comparable, **1** differs | 612 / 24 / **2** (`361167E3` outcome, `01B82FEC` routing) — see MAJOR-2 | ❌ |
| rotation, all native | 3,208 native, 83 comparable, 2 differ | 83 comparable, **2** differ, same two shas | ✅ |
| rotation controls | token conservation holds; 25/25 identical where the rung did not fire | **25 identical / 0 differing / 0 without an earlier artifact** | ✅ |
| WELCH mechanism | un-rotated validates, rotated declines; loss all on the credit side | un-rotated **publishes 193 postings = 12 credits + 181 debits**, matching both printed counts; rotated **declines**. The recorded "181 against 193, entire loss on the credit side" is exactly the un-rotated debit count against the total | ✅ |
| archive sweep tree vs tip | only `core_processor_enclosures.py`'s docstring differs; AST-without-docstrings identical | **verified by AST comparison** on both production files; `tools/cpdecl_identity_ceiling.py` also differs and is not a production module | ✅ |
| archive sweep, chunk re-run at the TIP (`b2ba776`, documents 0–500) | 2,669/2,669 identical, moved 0, `no_payload_now_publishes` 9 | **404 compared, 404 identical, moved 0**, `payload_now_raises` **0**, `multi_artifact_documents` 0, `no_payload_raises_again` 91, `no_ocr_artifact` 4, and `no_payload_now_publishes` **1** — `0943986A52D8226C`, a NAMED mover. Zero movement outside the named population in the chunk. EXIT 0 | ✅ |
| privacy, added file lines vs the 114-document population | 0 | **hit_count 0** over **2,372** added lines, 114 documents read, MONEY/DIGITS/DATES/WORDS all 0; raw 4 before exclusions, all `words_class` | ✅ |
| privacy, commit messages | MONEY/DIGITS/DATES 0, WORDS = the trailer | **11 commits, MONEY 0 / DIGITS 0 / DATES 0, WORDS 11**, and every one of the 11 is the two-token sequence `ANTHROPIC CLAUDE` from the co-authorship trailer — confirmed by reading the hit list | ✅ |
| guards (5 files) | 255 | **255 passed** | ✅ |
| conformance (7 files) | 1,270 passed / 40 skipped | **1,270 passed / 40 skipped** | ✅ |
| corpus-marked slice | 30 passed, 7,112 deselected | **30 passed, 7,112 deselected**, EXIT 0 | ✅ |
| `corpus_gate.py` | GREEN 105 PASS / 3 WITHHELD / 1 REFUSED, verdicts 1 / 3 / 102 / 3 | **GREEN**, 109 pinned PDFs (103 native / 6 committed OCR), 0 exclusions, **105 / 3 / 1**, verdicts **1 refused / 3 review / 102 validated / 3 withheld**, EXIT 0 | ✅ |
| full default suite | 7,065 passed / 43 skipped / 34 deselected | **7,065 passed, 43 skipped, 34 deselected**, EXIT 0 | ✅ |
| test-count change | enclosures 53 → 56, partition 89 → 89 | collected at `71a82aa` **53 / 89**, at the tip **56 / 89** | ✅ |
| W3 append-only | base + one appended section | `git diff` is **one hunk, `@@ -56721,0 +56722,420 @@`, 420 insertions / 0 deletions**, one `# §CPDECL` heading | ✅ |
| file ownership | the readers, their tests, `tools/cpdecl_*`, W3 | **9 files vs `71a82aa`, every one named by the card**; nothing outside it (the extra paths in a `train9..HEAD` diff are train9 moving ahead of the base, not this branch) | ✅ |

## 2. Findings

### BLOCK-1 — the blanking rule keeps the LATER of two adjacent dates, and where no daily grid is printed the platform publishes and validates a posting on a day the bank did not print

`_without_non_opening_dates` blanks `dates[i]` whenever no ledger figure stands between it and
`dates[i+1]`. The surviving token is therefore **always the later one, by position**. Whether
that is the row's posting date or a merchant's `Member <mm>/<dd>` note depends entirely on
which of the two the flattened layer emitted first.

The module docstring says the opposite, in these words: *"It always blanks the token that
closes no cell, never the one that does, so a row keeps the day of the date that actually
opens it — which is what stops a merchant's `Member <mm>/<dd>` from dating a posting."*
W3 §CPDECL4 repeats it (*"blanking the other one would date a posting on the merchant's
day"*), and the test that kills mutant M3 is named
`test_the_blanked_token_can_never_move_a_row_onto_the_wrong_day`.

**Refuted, through the real parse, with the module's own invented fixture.** Take the
committed credit block's second row and rewrite it in the ORDINARY card-statement order — the
row's own posting date first, then a merchant-note `mm/dd` inside the description, then the
amount — and drop the `DAILY BALANCE INFORMATION` block, which 8 of the 48 documents this
reader claims do not print at all:

* the reader publishes the row on the **note's** day, not the printed posting day;
* `analyze_markdown(..., parse_mode="deterministic")` returns **`validated / approved`**,
  integrity `risk_level: clear`, `adb.ok = True`, `missing_posting_dates = []`;
* the reconstructed daily-balance sum moves by about 6 % of the period's ADB against the same
  document with the note absent. A wrong figure, published, approved.

With the grid printed the same document declines — so the ONLY control that sees this failure
is the printed daily grid, and `parse_core_processor_enclosures_statement` applies it
conditionally: `if printed_grid and not _matches_the_printed_grid(...): return None`.

The control the module names as the proof of the call — *"both printed counts and both printed
totals"* — **cannot** see it: moving a row to another day changes neither the row count nor
the amount, so `_matches_the_printed_summary` is invariant under exactly this defect. The
argument in the docstring ("a blanked token that really WAS a row leaves the ledger one row
short … and the document declines at `_matches_the_printed_summary` instead") is sound for the
LOST-ROW failure mode and does not reach the MOVED-DAY one, which is the one the rule creates.

`adb.py` does not fail closed either. `posting_dates_cover_source` only reports dates the
source prints and the parser did NOT produce; a moved day still covers the set whenever any
other posting shares the true day — and on the demonstration above it passed outright.

**What the archive shows today, measured (no realised defect):**

| population | documents | rule fires | pairs whose two tokens are DIFFERENT days | published with an EMPTY daily grid |
|---|---:|---:|---:|---:|
| the 48 the reader claims at base (46 validated + 1 review + 1 withheld) | 48 | **0** | 0 | 8 (all `validated / approved`) |
| `DECL:core_processor_enclosures` | 9 | 6 | **3** | 0 |

So: the 46 protected documents are payload-identical **because the rule never fires on any of
them**, not because firing is harmless — their identity is no evidence for the rule. And on
the three movers whose two tokens are different days (`373B73F98E63F900`,
`75FE7191FD4E74A0`, `D31770634E04E104`) the printed 21–22-day grid IS present and the
mandatory `_matches_the_printed_grid` gate passed, so their published days are corroborated by
the bank's own second printing. The other three movers (`0943986A52D8226C`,
`BD835DA79B01B332`, `C355B3706588F0B1`) blank a token carrying the SAME day as the survivor,
where the choice cannot matter.

**Why this is a BLOCK and not a carried finding.** BATCH9-RULES lists "fail closed" and the
review contract names "a weakened check" as blocking. A refusal that existed
(`tables.dated_cells` returns None and the document is declined whole) has been removed for a
class of runs, and for the different-day subclass the compensating control the cell names is
provably blind; the only effective control is optional in the reader. That the archive happens
not to contain the unsafe ordering today is a fact about this archive, and the rule is a
general reader rule. The module's own `attributed_descriptions` docstring says a row's label is
what the layer printed on the row's own line — i.e. the date-then-note ordering is the ordinary
one whenever the `mm/dd` sits in the row's own label rather than in a flushed detail block.

**Remedy, measured at zero cost.** When a blanked token and its surviving neighbour carry
DIFFERENT printed days, require the printed daily-balance grid — refuse the document if the
grid is absent. All three different-day movers print a 21–22-day grid; the three same-day
movers are untouched; the rule fires on none of the 48 protected documents. Newly validated
stays **6**, preserved stays **74/74**. (Blanking only same-day pairs would ALSO fail closed
but would cost the three merchant-note movers, so it is the wrong fix.) Add a test in the
unsafe ordering — note AFTER the posting date, grid absent — asserting the document declines;
that test does not exist today, and M3's kill comes from a fixture written in the safe order.

Also correct the three places that assert the property: the module docstring, W3 §CPDECL4, and
the name/docstring of `test_the_blanked_token_can_never_move_a_row_onto_the_wrong_day` (whose
docstring additionally quotes a day token that does not appear in its own fixture).

### MAJOR-1 — "reproduces the printed figure to the cent" is false on two of the three `category_partition` movers, and the platform says so in the payload

I recomputed the calendar-day average independently from each mover's published ledger
(opening balance, signed dated postings, previous balance carried across inactive days,
inclusive printed period) and compared it to the bank's printed `Average Balance (Ledger)`:

| sha16 | delta vs the printed figure | `adb.validations.agrees_with_bank_stated_average` |
|---|---:|---|
| `889DAEBE7D79133C` | **0 cents** | **True** |
| `6E9A3A110E6829EB` | **1 cent** | **False** |
| `C47BEFE559CB8600` | **1 cent** | **False** |

The platform's own ADB equals my recomputation on all three. The claim *"the calendar-day
average computed from this reader's own ledger reproduces the printed figure to the cent"*
appears in the PRODUCTION docstring of `analysis/category_partition.py`, in W3 §CPDECL5 and in
the BATCH9_TRANSITION line. The substance survives — a one-cent gap on a 29/30-day average is
still strong day-sensitive corroboration, and the entry is evidence-only either way — but the
wording is wrong in a production module and must read "to the cent on one and to within a cent
on the other two", with the `agrees_with_bank_stated_average: False` on two of them stated,
since a reader of those payloads will see it.

### MAJOR-2 — the rotation table's first row does not reproduce

`tools/cpdecl_rotation_table.py` re-run at the tip over the card's own population prints
"documents whose ROUTING OR OUTCOME differs between the two forms | **2** of 24" —
`361167E3A263C346` (outcome) and `01B82FEC38EEEF16` (routing). W3 §CPDECL7's table records
**1** in that cell and **2** in the all-native row; the instrument returns 2 for both. The
disposition is unaffected (no registration has two affected documents: `welch_state_bank` 1,
`community_section` 1), but the number in the record is not the number the committed
instrument produces.

### MINOR-1 — two grid-day counts in CPDECL4's table do not reproduce

Measured `len(stated_daily_balances)` on the six movers: `373B73F9` 21, `75FE7191` 22,
`D3177063` 22, `0943986A` 22, `BD835DA7` **19**, `C355B370` **19**. W3 records 22 for the last
two. (The "printed grid days matched" claim itself holds — the gate is mandatory when a grid is
printed and all six publish — only the two counts are wrong.)

### MINOR-2 — CPDECL5 over-reads `adb.validations`

Four of the seven checks it lists as the platform's verdict —
`daily_balance_count_equals_calendar_days`, `daily_balances_contiguous`, `covers_opening_day`,
`covers_closing_day` — are true BY CONSTRUCTION for a series `adb.py` reconstructs itself, so
they are not evidence about these documents. The evidential ones on the three movers are
`opening_balance_matches_statement`, `final_balance_matches_statement_closing`,
`ledger_reconciles_to_closing`, `all_transactions_dated`, `transactions_within_period` and
`posting_dates_cover_source` (all true). The argument does not need the other four; listing
them makes it look stronger than it is.

### MINOR-3 — the gate table's tree is not named, and the same instrument at the tip returns different numbers

CPDECL2's table (GRAMMAR 24 / IDENTITY 14 / TRACE-DISAGREES 0) is a BASE-tree measurement — I
reproduced it exactly at `71a82aa`. Run at the tip the committed probe reports GRAMMAR 15 /
IDENTITY 14 / **PARSES 6** / **TRACE-DISAGREES 3**, because nine of the 38 now publish. That is
correct behaviour, but a later reader re-running the instrument at the composed tree will read
`TRACE-DISAGREES 3` as a defect. CPDECL9 names the tree for every proof-floor row; the gate
table deserves the same sentence.

### MINOR-4 — CPDECL6's 6 / 6 / 1 split of the sectioned Tesseract thirteen is 6 / 7 (or 5 / 7 / 1)

From the committed probe's own `count_delta` field over the 13: **6** documents have both
direction count deltas at zero and **7** have at least one non-zero; the one that fails only
`_matches_the_printed_grid` is INSIDE the six, so the honest split is "six read the right number
of rows in both directions — five of them miss a printed total and one misses only the grid —
and seven lose rows outright". The record's "six … six … one" adds to 13 only by counting the
grid document twice. The substantive claim reproduces exactly: the non-zero deltas run from
**−1 to −98 and are always negative** (13 values across the seven). No document moves either
way.

## 3. The hostile questions, answered

### (1) The GL3 reversal

**How the ADB is computed with no printed daily balances and no printed running balance.** From
the ledger chain alone, which is `adb.py`'s stated default rather than a fallback:
`compute_average_daily_balance` builds one inclusive end-of-day ledger from the statement's
opening balance and its signed dated postings, carries the previous balance across days with no
activity, and divides by the calendar days of the printed period. The module's ratified
docstring is explicit: *"Transaction running balances are validation evidence only; they never
replace the ledger reconstructed from the opening balance and signed postings"*, and *"When a
statement prints a dated daily book/ledger balance history, those explicit end-of-day snapshots
OUTRANK transaction-date reconstruction"* — printed snapshots are an override, not a
precondition. Measured on all three movers: `ok = True`,
`underwriting_adb_basis = calendar_day_printed_period`, `underwriting_adb_policy = canonical_v1`,
reconstructed series length = the calendar days of the printed period (29 / 32 / 30).

**Is it the same path the 8 of 46 use? Verified, yes.** Eight documents the
`core_processor_enclosures` reader claims publish with `stated_daily_balances == []`, and all
eight are `validated / approved` in the run of record (the reader claims 48: 46 validated + 1
review + 1 withheld; the eight are inside the 46). The platform already validates a
ledger-reconstructed calendar-day series on this very complex, under exactly the same required
checks.

**Does `running_balances_support_daily_ledger` pass vacuously? No — it is ABSENT.** `adb.py`
registers that check only when at least one transaction carries a printed running balance; the
sectioned issue prints none, so the key never enters `checks` and is never appended to
`required`. Measured: the validations dict on all three movers holds 13 keys and this is not one
of them. It neither passes nor fails, and the ADB does not rest on it. The genuinely
day-sensitive check that IS present and true is `posting_dates_cover_source` — every posting
date the SOURCE markdown prints is covered by a parsed transaction.

**Is the printed average matched to the cent on all three?** No — see MAJOR-1: exactly on one,
to within one cent on two, recomputed independently.

**The fourth document, `3A9502DFFD9EA4D9`.** It prints a LEDGER daily grid, so the reader
publishes with the grid and the ADB is computed against it. It is `validated / approved` at both
base and tip with a payload identical to the run of record (it is one of the 5/5 preserved). Its
printed `Average Balance (Ledger)` differs from the canonical ADB by 39.7 % of the printed
figure, and the platform records that as `agrees_with_bank_stated_average: False` plus the
metrics variance — a diagnostic, never a gate, exactly as the ADB doctrine requires. **It does
not validate with a wrong ADB**: its ADB is the canonical calendar-day figure, and the thing
that disagrees is the bank's own convention.

**Weakening, or a reader stricter than the platform's rule?** A reader stricter than the rule.
The doctrine text is `adb.py`'s own — the canonical average is the reconstructed calendar-day
series, printed snapshots outrank it where present, a bank's printed average is evidence — and
BATCH9-RULES' prohibition is on moving documents up *"without the same deterministic proof
standard"*. The standard applied here is the one eight already-validated documents of a sibling
reader on the same core meet. GL3's actual worry ("nothing places any row on a DAY") is a
worry the platform does not encode as a refusal anywhere else. So: **not a prohibited
weakening.** It is nonetheless a reversal of an argued, recorded refusal in a frozen batch —
see §5.

### (2) The blanking rule

Constructed, run, and refuted: see BLOCK-1. Supplementary answers:

* **which date survives:** always the later of the pair, by position. In the archive's three
  merchant-note documents the layer flushes the note BEFORE the next row's date, so the
  survivor happens to be the posting date and the grid confirms it — an accident of this
  layer's flush order, not a property of the rule;
* **the six movers' rows against their grid:** `_matches_the_printed_grid` is mandatory when a
  grid is printed and all six publish, so all six passed the day-by-day comparison; the two
  grid-day counts in the record are wrong (MINOR-1);
* **scoped to the ledger blocks:** verified in code. `dated_cells` has exactly two call sites in
  the module; only `_section_rows` wraps its run, `_grid` reads its own runs untouched;
* **do any of the 46 protected contain the pattern?** No — the rule fires on **0 of the 48**
  documents the reader claims. Their payload identity is therefore no evidence about the rule.

### (3) The three `failed → review` movers

`review / integrity_flags` with the single flag `missing_declared_statement_page` is the
correct outcome, and no figure in their payloads is wrong because of the missing page:

| sha16 | recon.ok | summary_ok | continuity breaks | adb.ok | txns | grid days | flags |
|---|---|---|---:|---|---:|---:|---|
| `0943986A52D8226C` | True | True | 0 | True | 73 | 22 | `missing_declared_statement_page` |
| `BD835DA79B01B332` | True | True | 0 | True | 67 | 19 | `missing_declared_statement_page` |
| `C355B3706588F0B1` | True | True | 0 | True | 73 | 19 | `missing_declared_statement_page` |

The ledger is complete against the bank's OWN printed evidence: both direction counts and both
direction totals reproduce (the reader refuses otherwise), and the printed daily-balance grid
agrees with the walked ledger day by day. A page that carried unreported transactions would
break both. The flag is about page provenance, the platform's own rule puts a flagged
publication in `review` rather than refusing it, and a published ledger with a named real
defect is strictly better placed than a refusal over a token that was never a posting. The only
false validation on all three is `agrees_with_bank_stated_average`, which is diagnostic.

### (4) The rotation table

**Is "no registration has two affected documents" the right threshold?** For the question the
card asked — whether a rotation-tolerant marker or grammar is OWED — yes, and it is the card's
own stated threshold ("≥ 2 documents affected"). It does not dispose of the loss, and the cell
does not pretend it does: `361167E3A263C346` is a document the platform's own OCR rung costs,
and it is carried as finding 1 with the owner named (`ocr/native_text.py`, not
`welch_state_bank`). I agree with the disposition. One bound worth stating in the record: the
table compares only documents for which the working cache still holds an earlier-key artifact —
584 of the 612 were excluded as never rotated and 4 under a different model — so "24
comparable" is the rung-fired subset, and the 25/25 unrotated control is what makes the
comparison mean what it says. Both hold.

**Is the WELCH mechanism real? Reproduced.** On the un-rotated text `welch_state_bank` detects
and publishes **193 postings — 12 credits and 181 debits — matching both printed counts
exactly**, with a 20-day grid. On the rotated text it detects and declines. The recorded "181
against 193, the entire loss on the credit side" is precisely the un-rotated debit count
standing against the total: the rotated region walk keeps every debit and loses all twelve
credits, so the printed credit count and credit total miss while the debit pair is exact.

**What would a fix cost DESC-COLUMNS?** The owner is the rung, and the honest answer from this
branch's evidence is that nobody has priced it: this table measures ROUTING and the LADDER
outcome only, and §DESCCOLS' gain was in descriptions — a payload improvement that moves no
document up the ladder is invisible here. The cell says exactly that, which is the right
disclosure. Any rung change would have to re-run §DESCCOLS' own fixtures byte-identical and
re-measure the description attribution it bought; this card correctly does not attempt it on
one document.

### (5) Hardcodes and fail-closed

**No hardcodes.** Neither production diff introduces a statement-specific constant, day, label,
count, bank, customer or account token. `_without_non_opening_dates` contains no literal at
all; the `category_partition` change is a removal plus prose. Canonical guards (5 files)
**255 passed**.

**Fail-closed on the new paths:**

* *a run that stops mid-row* — the last date of a run is never blanked (`dates[:-1]`), so
  `dated_cells` still returns None and the document is declined whole. Pinned by
  `test_a_run_that_ends_on_a_date_closing_no_cell_is_still_declined` and by mutant M2;
* *a date token that is not a date* — `_ROW_DATE` admits only explicit ASCII ranges
  (`(?:1[0-2]|0?[1-9])/(?:3[01]|[12][0-9]|0?[1-9])`), never `\d`, and the token-boundary classes
  are unchanged, so no new token class can match;
* *superscript digits* — cannot form a date for the same reason (superscripts are not in the
  admitted ranges and `\d` is not used), and blanking substitutes spaces of equal length, so it
  can never create a token that was not there;
* *a date whose amount the layer really lost* — declines one gate later at
  `_matches_the_printed_summary`; pinned by
  `test_blanking_a_date_that_really_was_a_row_still_declines_at_the_count`;
* *the interleaved printing* (a run of dates then a run of amounts) — collapses to one row and
  fails the printed counts, so it still declines;
* **the one path that does NOT fail closed** is the different-day pair with no printed grid:
  BLOCK-1.

The `category_partition` removal is fail-closed in the sense that matters: the collected grid's
cells are still unreachable (`grid` can only come from `_LEDGER_GRID_HEADING`), a printed ledger
grid that does not parse still returns None, and the unified issue's running-balance walk is
untouched. Mutants M6 and M7 pin both.

### (6) Ownership, W3, commit messages

* **W3 is base + one appended section.** `git diff 71a82aa..HEAD` on the log is a single hunk
  `@@ -56721,0 +56722,420 @@`, 420 insertions and 0 deletions, one top-level heading `# §CPDECL`.
  No other section is touched.
* **Ownership respected.** Nine files against the base, every one named by the card: the two
  readers, their two test modules, the four `tools/cpdecl_*.py`, and W3. (A `train9..HEAD` diff
  additionally shows `BATCH9-RULES.md`, `FIXTURE-PRIVACY-3.md` and `BATCH9_TRANSITION.md`; those
  are `train9` having moved ahead of `71a82aa`, not changes by this branch.)
* **Commit messages carry no archive token.** 11 commits; the committed message scanner against
  the 114-document population reports MONEY 0 / DIGITS 0 / DATES 0 and WORDS 11, and I read the
  hit list: all 11 are the same two-token sequence `ANTHROPIC CLAUDE` from the co-authorship
  trailer every commit in this batch carries. An independent hand scan for money shapes,
  `d/m/yyyy` dates and 5+ digit runs finds nothing. The W3 section's own counts (2,342 added
  lines, 9 commits) are the ones at the commit that carried them; at the tip they are 2,372 and
  11, and the ZERO is invariant, as the section itself says.

## 4. The contract, answered

| question | answer |
|---|---|
| newly validated 6 confirmed by sha? | **YES.** `6E9A3A110E6829EB`, `889DAEBE7D79133C`, `C47BEFE559CB8600` (`category_partition`), `373B73F98E63F900`, `75FE7191FD4E74A0`, `D31770634E04E104` (`core_processor_enclosures`) — all `failed → validated / approved`, re-measured |
| other movement 3 correct outcomes? | **YES.** `0943986A52D8226C`, `BD835DA79B01B332`, `C355B3706588F0B1` → `review / integrity_flags`, single flag `missing_declared_statement_page`, arithmetic complete against both printed counts, both printed totals and the printed grid. See §3(3) |
| preserved 74/74 identical? | **YES.** 10 + 46 + 13 + 5, payload identical, at base AND at tip; the 1 review and 1 withheld unchanged |
| regressions 0? | **YES.** 0 validated regressions and 0 other ladder regressions on every arm; zero movement outside the 9 named shas |
| doctrine kept? | **Mostly.** The ADB doctrine is kept (canonical basis, evidence-only bank average, no collected cell read, no FX or denominator question raised). The L-1 rule is kept — verified with the readers' own patterns: one distinct account field / period sentence / closing label on each of the six enclosures movers, one distinct `Account No.` capture on each of the three partition movers. The repair doctrine is kept (no parser writes an amount). **"Fail closed" is not kept on the different-day blanking path (BLOCK-1)**, and the GL3 reversal is a doctrinal position change that belongs to Gustavo, not to a cell (§5) |
| privacy 0? | **YES on file lines** (0 over 2,372 added lines, 114 documents). **Messages:** MONEY / DIGITS / DATES 0 over 11 commits; WORDS 11, every one the co-authorship trailer — confirmed by reading the hits, not by assertion |

## 5. Does the GL3 reversal need Gustavo's explicit confirmation before composition?

**Yes.** Not because it is wrong — on the evidence it is the better reading, and the cell's
three measurements survive re-measurement (the sibling readers' stated position; 8 of 46
validated documents already publishing on a ledger-reconstructed series; GL3.1's
generalisation failing on three of the four documents that print the entry). And not because
BATCH9-RULES forbids it — it does not: the proof standard applied is the one those eight
documents already meet.

It needs a ruling because of what it IS. §GLANCE GL3 is a refusal that a merged batch-8 cell
argued, measured and recorded as doctrine-derived — *"a collected series is not weak evidence
of it, it is a different quantity"*, and *"nothing in the document places any row on a DAY"* —
and this card reverses the second half of that on the ground that the reader was answering a
question `adb.py` owns. That is a change in where the platform draws the line between a
reader's refusal and the validator's verdict, on a complex where 5 documents are already pinned
and 3 more now publish. A cell may propose that; only Gustavo should ratify it. Two facts make
the ask cheap: `b3c1bbe` is a clean single-commit revert, and the cell says so itself.

I would put it to him with the correction from MAJOR-1 already applied — "to the cent on one,
to within a cent on the other two, with the platform recording disagreement on those two" is
the honest version of the corroboration, and it is still strong.

## 6. What Ocean should require before composition

1. **BLOCK-1**: make the different-day blanking fail closed (require the printed grid), add the
   unsafe-ordering test, and correct the three places that assert the safety property. Measured
   cost: zero documents. Re-run `cohort_replay` on the `DECL:` groups and on
   `--parser core_processor_enclosures` afterwards; newly validated must still be 6 and
   preserved 46/46.
2. **MAJOR-1**: correct the "to the cent" claim in `analysis/category_partition.py`, W3 §CPDECL5
   and the BATCH9_TRANSITION line.
3. **MAJOR-2**: correct the rotation table's first row to 2 of 24, keeping the disposition.
4. **MINOR-1/2/3/4**: the two grid-day counts, the `adb.validations` over-read, the sentence
   naming the gate table's tree, and CPDECL6's 6 / 6 / 1 split.
5. **The GL3 ruling** from Gustavo, before the branch is composed.

Nothing else on this branch needs changing. The instruments are honest, the ceilings are real
bounds rather than arguments, the mutation table reports its survivor instead of hiding it, the
refusals are refusals, and every count reproduces.
