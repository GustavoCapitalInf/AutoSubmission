# BATCH 9 REVIEW — FIXTURE-PRIVACY (`wave9-fixpriv`, base `2f24b06`, tip `31255ef`, 15 commits)

Independent adversarial review. I did not write this code, I asked the cell nothing, and every
headline number below was re-measured by me from the committed instruments. Ocean composes; I
never merge or push.

**Tree under review:** worktree `.claude/worktrees/mt9-fixpriv`, branch `wave9-fixpriv`,
base `train9` `2f24b06`, tip `31255ef`.
**Read first:** `docs/agent-handoffs/BATCH9-RULES.md`; `docs/agent-handoffs/FIXTURE-PRIVACY.md`;
the branch's own W3 section `§FIXPRIV` (`docs/moneythumb-replacement/W3_TRACKA_LOG.md`, the
appended block); the cell's final report; the full `2f24b06..31255ef` diff, commit by commit;
shape precedent `docs/moneythumb-replacement/reviews/BATCH8_HYGIENE8_REVIEW.md`.
**Note on the package:** the prepared review package file named in my brief was not present in
the scratchpad, so I built the commit list, the stat and the full diff myself from the worktree.
Nothing depends on it.

**Instruments, absolute paths passed explicitly to every run**
Run of record `discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d/rows.csv`;
cold cache `.claude/recovery/webapp_data_train8_cold` (READ-ONLY, never written);
root commit `19ec351`. Every heavy proof ran as a single detached process with a durable log
and an `EXIT=` terminator; the tree was verified clean before and after each mutation run.

## VERDICT: **BLOCK** — 1 BLOCK, 4 MAJOR, 6 MINOR

The engineering is the best of the batch so far: the adjudication really did move out of prose
and into a committed instrument, the mutation harness is real, coverage movement is zero and
proved twice, and the cell's self-criticism (FP5, FP6, FP9) is honest to the point of being
unflattering. Three things stop it, and all three are small, well-specified edits:

1. one exclusion rule silences account and member numbers on shapes this archive actually
   prints — the card names that condition a BLOCK in so many words;
2. the branch's own added lines carry archive tokens (standing privacy scan = **2**, not 0);
3. the tip half of every headline scan number in the record was measured one commit before the
   tip and does not reproduce at `31255ef`.

Fix those and this is an APPROVE: I found nothing wrong with the AST-identity argument, the
replay, the mutation table, the ownership, or the six files the card actually cleared.

---

## RE-MEASUREMENT TABLE

Every row re-run by me. Exit codes verbatim.

| # | claim (cell report / `§FIXPRIV`) | my re-measurement | exit | verdict |
|---|---|---|---|---|
| 1 | population 3,380 shas, **3,351 with cached text**, 29 without (never 0) | `population` 3,380 · `documents_read` **3,351** · `no_cached_text` 29 | 1 | reproduces |
| 2 | universe MONEY 354,835 · DIGITS 208,695 · DATES 3,211 · WORDS 416,756 | identical, all four | 1 | reproduces |
| 3 | base `2f24b06` residue **10,810 sites / 209 files** | **10,810 / 209** | 1 | reproduces |
| 4 | base residue by class × directory, all 18 rows | all 18 rows identical | 1 | reproduces |
| 5 | base per-rule take (words 1,071,553 · round 17,286 · corpus 4,966 · subunit 2,356 · hex 850 · zip 200 · session 2; raw 1,116,223) | identical, all seven rules and the raw total | 1 | reproduces |
| 6 | **tip residue 10,645 / 203 files** | at `31255ef`: **10,677 / 203**; at `1e0a01e`: 10,645 / 203 | 1 | **does NOT reproduce at the tip** — MAJOR 1 |
| 7 | tip per-rule take (words 1,075,091 · subunit 2,374 · hex 866; raw 1,119,479) | at `31255ef`: words 1,076,299 · subunit 2,378 · hex 876; raw 1,120,733. `round_money` 17,300, `corpus_cache` 4,966, `institution_zip` 200, `docs_session_date` 2 all match | 1 | **does NOT reproduce at the tip** — MAJOR 1 |
| 8 | six files reach zero (`analysis/lili.py` 8→0, `core_processor_signed_counts.py` 8→0, `bank_ozk.py` 1→0, `tests/test_lili.py` 138→0, `tools/lili_privacy_scan.py` 1→0, `tools/privacy_scan_branch.py` 9→0) | exactly those six, exactly those counts; 165 sites removed, and the per-file breakdown reconciles to 165 with nothing left over | 1 | reproduces |
| 9 | "**no file gained residue** and no token appears at the tip that was not at the base" | false at `31255ef`: `W3_TRACKA_LOG.md` 3,516 → **3,548**; **32 sites are new**, every one inside the cell's own appended section | — | **REFUTED** — MAJOR 1 |
| 10 | privacy scan "0 introduced, 0 files gained" | standing ADDED-LINES scan `--base 2f24b06 --ref 31255ef`: `hit_count` **2**, `residue_sites` **2**, `residue_files` 1 (both MONEY, `W3_TRACKA_LOG.md:55090`) | 1 | **REFUTED** — MAJOR 2 |
| 11 | `fixpriv_ast_identity --base 2f24b06 --ref HEAD`: three modules IDENTICAL | with the three paths passed: `IDENTICAL` ×3, "files 3 · AST-identical 3 · differing 0" | **0** | reproduces |
| 11b | (same tool, bare, as the card's method writes it) | `MISSING tests/test_fixpriv_ast_identity.py: at 2f24b06=False HEAD=True` | **2** | MINOR 1 |
| 12 | `cohort_replay --expect-identical`, 27 of 27 preserved, payload identical | `--parser lili --parser bank_ozk --parser core_processor_signed_counts`: population **27** · replayed 27 · newly validated **0** · other ladder movement **0** · preserved **27 of 27** · payload identical **27** · payload changed 0 · validated regressions **0** | **0** | reproduces |
| 12b | (`--parser lili` alone) | population 11 · preserved 11 of 11 · identical 11 · regressions 0 | **0** | reproduces |
| 13 | mutation table **22 mutants / 22 killed / 0 survived**, run without `-x`, every killer named, tree restored | 22 / 22 / 0; every mutant's killer list non-empty; `git status --porcelain` empty before and after | **0** | reproduces |
| 14 | exclusion-rule tests 110 | `tests/test_privacy_scan_exclusions.py` **110 passed** | **0** | reproduces |
| 14b | the branch's four test files | 110 + 12 + 14 + 58 = **194 passed** | **0** | reproduces |
| 15 | canonical guards 255 | **255 passed**, 1 warning | **0** | reproduces |
| 16 | canonical conformance 1,270 / 40 skipped | **1,270 passed, 40 skipped**, 1 warning | **0** | reproduces |
| 17 | `corpus_gate.py` GREEN 105 PASS / 3 WITHHELD / 1 REFUSED; currency 14 CAD / 94 USD; provenance 7 / 4 / 1 / 7 / 89 | **RESULT: GREEN**, 105 / 3 / 1; 14 CAD / 94 USD; 7 institution_default / 4 jurisdiction_default / 1 printed / 7 product / 89 schema_default; 109 pinned PDFs, 0 exclusions; runtime 531.8 s | **0** | reproduces |
| 18 | full suite: 2 failed / 6,876 passed / 43 skipped, both failures inherited from the base | **2 failed, 6,876 passed, 43 skipped, 34 deselected** in 3 min 32 s; the two failures are exactly `test_corpus_gate_outcomes::test_every_production_caller_of_the_analysis_is_classified` and `test_currency_source::test_only_the_readers_the_schema_and_the_gate_know_the_provenance_exists` — the pair known and excused (Ocean's own tools at the base, fixed on train9 `dedc1c9`). **No other failure, no error.** | 1 | reproduces |
| 19 | corpus-marked slice 30 passed | **30 passed**, 6,925 deselected, 1 warning, 27 min 29 s | **0** | reproduces |
| 20 | `fixpriv_w3_redact --check-idempotent` exit 0 | exit **0**; idempotence holds | **0** | reproduces |
| 20b | redactor dry run over W3: MONEY 1,366 · DIGITS 145 · DATES 223 on 1,070 lines | at `31255ef`: MONEY **1,377** · DIGITS **150** · DATES 223 on **1,074** lines | 0 | same one-commit-early provenance as row 6 |
| 21 | W3 is base + ONE appended section | base 54,966 lines → tip 55,207; the first 54,966 lines are **byte-identical** (`cmp` on the base-length prefix); exactly one `#` heading appended, `§FIXPRIV`, with FP1–FP10 | 0 | reproduces |
| 22 | ownership: nothing outside the card | 14 files touched; `analysis/bmo.py`, `analysis/farmers_merchants.py`, `analysis/td_can.py`, `tests/test_privacy3_boundaries.py`, `tests/test_raise_privacy4.py` **untouched**; no registry entry, no version bump, no `webapp/ ocr/ discovery/ telemetry/ benchmark/ corpus_gate.py` change | 0 | reproduces |
| 23 | `tests/test_analysis.py` carries 822 residue sites (FP9) | **820**, identical at base and tip | 1 | MINOR 6 |

**Corpus-marked slice: I ran it.** `pytest -m corpus -q` at the tip, as a detached process on the
shared host while the other cell's work was also running: **30 passed, 6,925 deselected**, 27 min
29 s, `CORPUS_EXIT=0`. The contention cost runtime, not outcomes.

**Privacy of this review file:** scanned with the branch's own instrument against the same
3,351-document universe (`--base 31255ef --ref <this commit>`): first pass **2 MONEY hits** — the
full-suite runtime, written to the hundredth of a second, is money-shaped and collides. Rewritten
as minutes and seconds; second pass **0 hits, 0 sites, exit 0** over 543 added lines. I mention
it because it is the same trap as MAJOR 1, one commit later, and it is not a cheap trap to
avoid — which is part of why I grade MAJOR 1 as a measurement failure rather than as carelessness.

---

## FINDINGS

### BLOCK 1 — `institution_zip` silences account, member and originator numbers: 24 of the 51 state abbreviations are ordinary English words in an upper-cased line

`tools/privacy_scan_branch.py:186-195` (`_STATE`, `ZIP_CONTEXT_RE`) and `:225-231`
(`_institution_zip`).

The rule is documented as "a US state abbreviation" followed within eight non-digit characters
by five digits — an institution's own service ZIP, "furniture the doctrine allows". But the
scanner upper-cases every line before it matches (`tokens_of`, `added_lines`, the tree pass),
and roughly half the abbreviation list is indistinguishable from ordinary English or ordinary
statement furniture once upper-cased: `IN`, `OR`, `OK`, `ME`, `ID`, `HI`, `DE`, `LA`, `MA`,
`MS`, `PA`, `CO`, `MI`, `MT`, `NE`, `AL`, `CA` and more. `\b…\b` bounds do not help — these are
whole words.

Run against the branch's own `excluded_by`, with reviewer-invented five-digit tokens:

| line the scanner sees | rule that claims it | what is being silenced |
|---|---|---|
| `MEMBER ID 84213` | `institution_zip` | a credit-union **member number** — the identifier `CENSUS_BATCH8_DIGITAL.md` records as this archive's most common account field |
| `THE ACCOUNT ENDING IN 84213` | `institution_zip` | an **account number** tail |
| `07/03 BETA INBOUND CCD CO# 45678 TRACE` | `institution_zip` | an ACH **company / originator id** — this exact line shape is the documented grammar of `analysis/core_processor_signed_counts.py`, a module this very branch edited |
| `09/17 TRANSFER IN 84213 CREDIT` | `institution_zip` | a posting **reference number** |
| `AUTH OK 84213` | `institution_zip` | an **authorisation code** |
| `CHECK NO OR 84213` | `institution_zip` | a **cheque number** |
| `CHECK 84213` (control) | — none — | correctly reported |

The card writes the criterion itself: *"add a test that each exclusion matches exactly the shape
its rule names and nothing wider (**an exclusion that silences a real account number is a
BLOCK**)."* This one silences an account number, a member number and an ACH originator id on
line shapes the archive prints in quantity, so I am obliged to grade it as the card says.

The guard does not catch it. `tests/test_privacy_scan_exclusions.py:209-220`
(`test_institution_zip_reaches_nothing_wider`) tests five near-misses, and every one of them
fails the rule for a reason other than the state token — seven digits, no abbreviation at all, a
gap longer than eight, an intervening digit run. `:227-240`, the block that is supposed to close
this ("no rule, in any combination, may silence an identifier"), has nine cases and not one puts
a five-digit token after a word-shaped abbreviation. Mutant `M10` deletes the address context
entirely and `M11` widens the gap; neither perturbs the abbreviation class, so 22 / 22 killed
says nothing about this hole.

**Live exposure today: zero.** I re-derived every one of the 104 sites the rule silences in the
tip tree and read each line with the token masked: all 104 are genuine postal codes on
institution or customer address lines (`P.O. BOX … , <ST> <ZIP>`, `… <CITY>, <ST> <ZIP>-NNNN`).
Nothing is being hidden right now. But this scanner is now the program's standing privacy
instrument, every later cell will lean on its zeros, and a rule that cannot survive
`MEMBER ID <5 digits>` should not become doctrine.

**Concrete closure.** Require address furniture rather than the bare abbreviation — the simplest
form that keeps all 104 current sites is to demand that the abbreviation be preceded by a comma
or by a line/segment start, *or* that the five digits be followed by end-of-field or `-NNNN`;
of the 104 live sites every one carries one of those. Then add to `:227-240`:
`("DIGITS", "84213", "MEMBER ID 84213")` and `("DIGITS", "45678", "CCD CO# 45678 TRACE")`, and a
mutant that restores the bare-abbreviation form.

---

### MAJOR 1 — every tip scan number in the record was measured at `1e0a01e`, one commit before the tip; the branch's own W3 section then added 32 residue sites

`docs/moneythumb-replacement/W3_TRACKA_LOG.md` §FP1 (the base/tip table), §FP2 (the class ×
directory table and the sentence "**No file gained residue and no token appears at the tip that
was not at the base**"), §FP10 ("Privacy scan at the tip: 10,645 residue, 0 introduced, 0 files
gained"). Same defect in the cell's report.

I ran the whole-tree scan with the branch's own scanner at three trees, same population, same
root base, one process at a time:

| tree | residue sites | files | raw hits |
|---|---:|---:|---:|
| base `2f24b06` | 10,810 | 209 | 1,116,223 |
| `1e0a01e` (last code commit) | **10,645** | 203 | 1,119,479 |
| tip `31255ef` | **10,677** | 203 | 1,120,733 |

At `1e0a01e` *every* number the record prints reproduces exactly — all seven per-rule counts,
all eighteen class × directory rows, the raw total. At the tip they do not. The delta is
`31255ef` itself, the commit that appends `§FIXPRIV`: **+32 sites, all in
`W3_TRACKA_LOG.md`, 22 MONEY and 10 DIGITS**, on six lines of the new section — the FP5 list of
"obviously made up" example figures that the cell had just measured as colliding, and the FP6
list of the record's own machine numbers. The irony is exact: FP5's whole point is that a figure
you invent by eye collides about a third of the time, and the sentence making that point put
eight such figures into tracked source.

This is not a rounding difference or a stale note. `§FP2`'s claim that no file gained residue
and `§FP10`'s "0 introduced" are the two headline privacy assertions of the card, and both are
false at the commit Ocean would compose. BATCH9-RULES: *"ledgers record measurements, not
inferences — every headline number reproduces from committed evidence."*

**Closure:** rewrite the six lines so the examples are not archive tokens (the cell's own
`fixpriv_invent` proposes non-colliding shapes; or drop the literals and give the classes), then
re-run the tree scan at the real tip and correct FP1, FP2 and FP10. Expected result 10,645 / 203.

---

### MAJOR 2 — the standing added-lines privacy scan at the tip is 2, not 0; the branch fails its own proof floor

BATCH9-RULES, *Instruments* and *Proof floor per branch*: the shared scanner is run over
"every branch's ADDED lines against the printed tokens of the documents it worked on; report the
count (**0**)", and "privacy scan 0" is a floor item.

```
tools/privacy_scan_branch.py --rows <run>/rows.csv --data-dir <cold cache> \
    --base 2f24b06 --ref 31255ef
→ hit_count 2 · residue_sites 2 · residue_files 1 · hits_by_class MONEY 2
  HIT MONEY docs/moneythumb-replacement/W3_TRACKA_LOG.md:55090   (×2)
  documents_read 3351 · added_lines 2,047   EXIT=1
```

Both are on the FP6 line that lists the record's own test durations. Same root cause as MAJOR 1
and the same edit closes both; I log it separately because it is a different rule of the floor,
and because the cell's report states this number as "privacy scan exit 1 by design (0
introduced, 0 files gained)" — the exit code is indeed 1 by design for a tree audit, but this
run is the added-lines run and its 2 is not by design.

For the avoidance of doubt about severity: the two tokens are seconds-and-hundredths durations,
not a balance, a name, an account number or a document date. The *harm* is nil. The *rule* is
mechanical, the cell built the instrument that enforces it, and a floor that is waived when the
number is small is not a floor.

---

### MAJOR 3 — the ×428 scale did not preserve `tests/test_lili.py`'s meaning: five reconciliation tests lost their tolerance sensitivity by a factor of 428

`tests/test_lili.py`, the perturbation deltas in
`test_a_broken_chain_refuses_the_document`, `test_a_summary_that_does_not_close_on_itself_is_refused`,
`test_a_first_posting_that_does_not_step_from_the_printed_beginning_is_refused`,
`test_a_chain_that_does_not_arrive_at_the_printed_ending_is_refused` and
`test_a_posting_pair_the_summary_nets_out_is_refused`, against `analysis/lili.py:210` `_CENT`.

The cell's claim (report, and `§FP7`): *"The 58 `test_lili` tests pass with their meaning intact:
every assertion is the same assertion about the same relation, at 428× the cents."* The relation
is indeed the same. The **sensitivity** is not, because the scale was applied to the
perturbations as well as to the figures. `analysis/lili.py`'s three arithmetic gates compare
against an **absolute** tolerance, `_CENT = 0.005`, so multiplying a fixture's deliberate error
by 428 multiplies by 428 the slack a mutant may introduce before the test notices.

Measured, one mutant at a time, tree clean and restored between each (`_CENT` substituted in
`analysis/lili.py`, `tests/test_lili.py` taken from each ref in turn):

| `_CENT` mutant | base fixtures (`2f24b06`) | tip fixtures (×428) |
|---|---|---|
| `0.5` | 58 passed — survives | — |
| `1.0` | **1 failed — KILLED** | 58 passed — **SURVIVES** |
| `10.0` | **1 failed — KILLED** | 58 passed — **SURVIVES** |
| `100.0` | **5 failed — KILLED** | 58 passed — **SURVIVES** |
| `400.0` | — | 58 passed — **SURVIVES** |
| `500.0` | — | 1 failed — killed |

A reader that accepted a hundred-dollar discrepancy between a printed summary and its own ledger
would be caught at the base and is not caught at the tip. Nothing else guards it: `corpus_gate`
replays real documents, which close exactly, so a widened tolerance only makes the reader more
permissive and the gate stays green — `test_lili.py` was the only teeth.

This is the card's own stop condition: *"A fixture change that changes a test's meaning is a
finding, not a fix."*

**Closure, and it makes the file stronger than the base.** Scale the figures — that part is
right and the closures hold exactly — but do **not** scale the perturbations. Perturb by one
cent instead: in `test_a_broken_chain_refuses_the_document` move the chain's second printed
balance by `0.01` rather than by `428.00`; in `test_a_summary_that_does_not_close_on_itself_is_refused`
move the deposits term by `0.01`. Both still refuse for exactly the reason the test names, and
at one cent every widened-tolerance mutant dies. Worth a mutant of its own in
`fixpriv_mutation_table.py`.

---

### MAJOR 4 — `hex_sha_substring` is line-scoped, not position-scoped, and its own docstring says the opposite

`tools/privacy_scan_branch.py:218-219`:

```python
def _hex_sha_substring(cls, path, token, line) -> bool:
    return cls == "DIGITS" and any(token in run for run in HEX_RUN_RE.findall(line))
```

The module docstring at `:159-161` promises: *"The token has to sit INSIDE one, so a bare digit
run on the same line as a sha is still a finding."* The implementation never asks **where** the
token occurs. It asks only whether the digits appear *somewhere* inside *some* hex run on the
line. So a digit run standing on its own is excused whenever any sha on that line happens to
contain the same characters:

| line the scanner sees | rule that claims it | should be |
|---|---|---|
| `ACCOUNT 7000004 AT COMMIT F7000004E` | `hex_sha_substring` | a finding |
| `SHA AB98989CDEF AND ACCOUNT 98989` | `hex_sha_substring` | a finding |
| `COMMIT F14282E LANDED` (the shape the rule names) | `hex_sha_substring` | correctly excused |
| `CARD 4111111111111111` | — none — | correctly reported — the hex-LETTER requirement works, and it is a genuine improvement on the card's own `[0-9A-F]{16,64}` draft |

Mutant `M5` replaces the rule with `HEX_RUN_RE.search(line) is not None` — total blindness — and
is killed by `test_hex_sha_substring_does_not_excuse_a_number_beside_a_sha`
(`tests/test_privacy_scan_exclusions.py:118-121`), whose fixture uses a token that is **not** a
substring of the sha. The intermediate defect between the shipped rule and `M5` is exactly the
case neither the test nor the mutant reaches.

**Live exposure:** I re-derived all 536 sites the rule silences in the tip tree and tested each
for a token occurrence outside every hex run on its line. Eight raw hits over three sites are
over-reached, and all three are the rule's own fixtures at
`tests/test_privacy_scan_exclusions.py:132-134`, where the token is quoted as a bare literal
beside the sha it came from. No production, test or docs line is currently hidden by it.

**Closure:** ask about the occurrence, not the line — for each match of the token in the line,
require it to fall inside a `HEX_RUN_RE` span, and excuse only if *every* occurrence does. Then
add `("DIGITS", "7000004", "ACCOUNT 7000004 AT COMMIT F7000004E")` to the block set and a mutant that
restores `token in run`.

---

### MINOR 1 — `fixpriv_ast_identity` cannot be run the way the card's method writes it

`tools/fixpriv_ast_identity.py:80` (`paths = args.paths or changed_python(...)`) and `:96-100`.
With no paths the tool takes every `.py` that differs between the refs — which on this branch
includes four files that do not exist at the base — and `show()` returning `None` for an ADDED
file is treated as a git failure: `MISSING tests/test_fixpriv_ast_identity.py`, **exit 2**. The
card's method writes the bare invocation, and my brief asked for it. Passing the three paths
gives exit 0 and `IDENTICAL` on all three, which is the number that matters, but a gate that
exits 2 on its own branch will be read as broken by whoever runs it next. One line: skip a path
that is absent at either ref, and report the skips.

### MINOR 2 — `round_money`'s justification is narrower than its reach

`tools/privacy_scan_branch.py:88-93` and `:212-213`. The rule excuses **every** MONEY token
ending `.00`, on the reasoning that "a round figure is a magnitude, not a printed identity:
`100.00` is the bound of a test's tolerance as readily as it is a deposit, and no document is
reconstructed from one." Measured at the tip, the rule silences 9,052 sites, of which **2,737
carry a magnitude of 1,000.00 or more and 536 carry 10,000.00 or more**. A five-figure round
deposit beside a date and an institution is not a tolerance bound and it is not nothing. This is
one of batch 8's three standing exclusions, so it is not this cell's to narrow and I am not
asking it to — but the docstring is the exclusion table's public justification and it should say
what the rule actually does: round figures are excused because the program chose to accept that
class wholesale, not because they cannot identify.

### MINOR 3 — `words_class` throws away the one capability the scanner builds for names

`tools/privacy_scan_branch.py:206-207`; 632,617 sites silenced at the tip — 98.6 % of the raw
hits. `tokens_of` deliberately builds two-word sequences "a name whose halves are each ordinary",
and then `words_class` discards every WORDS hit, so the scanner cannot report a customer name at
all (`excluded_by("WORDS", …, "SMITH JONES", …) == "words_class"`). The card's definition of done
is scoped to MONEY / DIGITS / DATES, so this is within the card and within the batch-8 standing
exclusion — but the card's own identity paragraph says "not a balance, an amount, **a name**, an
account number, a date". The record should state plainly that the tree is unaudited for names by
construction, so the next card can be written; `§FP9` lists four residual classes and this is not
among them.

### MINOR 4 — `docs_session_date` will silence a document date inside `docs/` on or after the era bound

`tools/privacy_scan_branch.py:222-229`. `excluded_by("DATES", "docs/x.md", "2026-08-06",
"STATEMENT PERIOD ENDS 2026-08-06")` → `docs_session_date`. The archive was frozen on 2026-08-06,
so document dates do reach the bound, and a census entry that quotes a period end in ISO form
inside `docs/` is silenced. The rule is bounded twice (directory and era) and the numeric
`mm/dd/yyyy` form — far more common on a statement — is correctly untouched; live exposure is
**1 site**. The counter-samples in `test_docs_session_date_is_bounded_both_ways` stop at 2019 and
never probe the days around the bound. Worth a note in the table and a `2026-07-01` /
`2026-08-06` counter-case; not worth blocking.

### MINOR 5 — `M5` and the block set leave the two holes above untested, so "22 / 22 killed" is weaker than it reads

Not a defect in the harness, which is well built and restores cleanly, but a scope statement the
record should carry: of the seven rules, the two that depend on context (`hex_sha_substring`,
`institution_zip`) are each attacked by mutants that remove the context entirely (`M5`, `M10`,
`M11`) and none that perturb *which* context counts. Both defects I found live in that gap. A
mutation table's number is a claim about the mutants written, and `§FP4` presents 22 / 22 as
though it settled the rules.

### MINOR 6 — bookkeeping

`§FP9` gives `tests/test_analysis.py` as **822** residue sites; I measure **820**, identical at
base and tip. `§FP2`'s roll-up "production 431 → 414" counts `benchmark` and the root scripts as
production, which is defensible but is not the card's definition of the production class
(`analysis/ ocr/ webapp/ discovery/ telemetry/ *.py` at the root) — under the card's own list the
figure is 414 minus the 2 `DATES benchmark` sites. Neither changes any conclusion.

---

## THE CARD'S EXPLICIT QUESTIONS, ANSWERED

**Newly validated = 0?** **Yes.** `cohort_replay` at the tip over all three touched
registrations: newly validated 0, other ladder movement 0. Exit 0.

**Preserved = all, with identical payloads?** **Yes.** 27 of 27 previously validated documents
preserved, payload identical on 27, payload changed on 0. Exit 0. Independently corroborated by
`fixpriv_ast_identity`: the three touched production modules are AST-identical modulo
docstrings, so no payload could have moved.

**Regressions = 0?** **Yes.** Validated regressions 0, other ladder regressions 0, unchanged
non-validated 0 with payload changed on 0. No archive sweep is owed: no reader changed.

**Doctrine kept — no behaviour change, no hardcode, fail closed?** **Yes.** All three production
edits are inside `#:` comments and docstrings; AST identity proves it mechanically; I checked
the two ways that proof could be evaded and neither applies — no touched module reads `__doc__`,
`inspect.getsource`, `getcomments` or `linecache` at runtime, nothing in `analysis/ ocr/ webapp/
discovery/ telemetry/` reads a docstring as data, and the suite collects no doctests
(`pytest.ini` has no `--doctest-modules`). Constants in annotations, default arguments,
decorators, f-strings and module-level string constants used as data all remain inside
`ast.dump` and would be reported; only line and column numbers are dropped, and nothing in this
tree asserts on those. No registry change, no version bump, no new hardcode, $0 — no network,
no hosted model, no paid OCR anywhere in the branch.

**Privacy of the added lines = 0?** **No — 2.** See MAJOR 2. Zero of the 2 are archive identity;
both are the record's own machine numbers that collide with a printed figure. But the answer to
the question as asked is 2.

**Ownership respected?** **Yes.** 14 files, every one inside the card's list.
`analysis/bmo.py`, `analysis/farmers_merchants.py` and `analysis/td_can.py` are untouched, as
are `tests/test_privacy3_boundaries.py` and `tests/test_raise_privacy4.py` — RAISE-PRIVACY-4 can
compose beside this. `W3_TRACKA_LOG.md` is the base log plus exactly one appended section, with a
byte-identical prefix over all 54,966 base lines. No file the card forbade was touched, and the
production edits stayed inside the five modules named (three of the five needed edits; the `0.01`
tolerances in `analysis/citizens.py` and `analysis/scanned_small_bank.py` were adjudicated by the
`subunit_money` shape rule instead of being edited, which is the better answer).

**No archive content in the W3 section or in this review?** The W3 section carries **no name, no
account number, no amount and no document date from any archive document** — I checked its 241
lines against the printed universe with the branch's own scanner. It does carry the 32 colliding
machine-number and example-figure tokens of MAJOR 1. This review file quotes no archive token: I
scanned it with the same instrument before committing it, and the closing line records the count.

---

## THE CELL'S CONCERNS, WITH MY OWN OPINION

**1. train9's base floor is red (two inherited failures).** Confirmed and correctly excused. The
full suite at the tip fails exactly those two and nothing else. Not this cell's; already fixed on
train9 at `dedc1c9`. Ocean should compose onto a train that carries the fix and re-run the suite
once, expecting 6,878 passed.

**2. Production population understated 20×: 414 sites / 62 files, not 21 / 5 — ruling needed.**
The cell is right, and it is right to have stopped rather than reach outside the card. I checked
all four named CODE sites and they are not coincidences:

* `analysis/consumers.py:90` — `flat.find("BusinessPlus Checking (S70) - <10-digit account>")`.
  A production reader locates its section by matching a product name **and a printed account
  number**. This is simultaneously an archive identifier in tracked source and a
  statement-specific hardcode, which BATCH9-RULES forbids outright. It is the most serious
  privacy site in the tree and it is also a correctness defect: a second document of that
  platform with a different account cannot be read. **This deserves its own P0 card**, and it
  cannot be a docstring fix — the section anchor has to be re-derived structurally.
* `analysis/classification_registry.py:36,45` — a funder's `LCM <7 digits>` marker and a
  `<10-digit>` originator id in the marker tuple, beside a phone ladder in the same entry. These
  read as **furniture**, the same class as a routing number or a PO box, and the doctrine allows
  furniture in a detection marker. My opinion: keep them, but the record has never justified them
  as furniture in writing, and "allowed" is a claim that has to be made once.
* `analysis/cibc.py:93` — a six-character form/template prefix in a line filter. Template
  furniture. No adjudication needed beyond saying so.
* `analysis/core_processor_sectioned.py:392-405` — transcribed archive header lines in a
  docstring, complete with two institution names and a masked account tail. Prose, so it is the
  cheap class: it is exactly what this cell did to three other modules, and it belongs on the
  follow-up card with the rest of the 62 files.

My recommendation to Ocean: rule that the production sweep is a **second card**, sized from this
cell's 414 / 62 measurement, with `consumers.py:90` split out as its own P0 because it is a
hardcode and a correctness defect, not a privacy edit.

**3. The record redaction is refused as specified — ruling needed.** **I agree with the refusal,
and I verified the reason rather than taking it.** Running the committed redactor's patterns over
the record's own vocabulary: a runner image's two-part version number matches `MONEY_RE`, and so
does every test duration written as seconds to the hundredth. (The four I measured are not
quoted here: each is a figure some document prints, which is the finding, and quoting them
would put them in tracked source -- the closure's MAJOR 1 trap, one paragraph on.) Under the
tool's rule any of those that a document also prints is replaced
by `[amount redacted]`, and a five-or-more-digit CI run id or W3 line reference that collides is
replaced by `[digits redacted]`. That destroys the record's ability to name its own runs, its own
lines and its own durations — which is `cc64232` / `bbeeb5c` damaging shas, one step further out,
and it is not "redactions only; never rewrite meaning". The redaction as the card specifies it
buys almost nothing: the residue it removes is overwhelmingly the program's own machine numbers
and transcribed grammar examples, not archive identity. My opinion: **do not run it on the
records as specified.** If Ocean wants the docs class closed, the right shape is a rule that
excuses the program's own vocabulary by context — durations with a unit suffix, `ubuntu-NN.NN`,
`Run <id>`, `L<line>`, `lines N–M` — and that is a card, not a switch. The tool is committed and
idempotent, so the decision stays reversible either way. Note that MAJOR 1 and MAJOR 2 are the
same collision class arriving from the other direction: the cell's own prose about this problem
is what tripped the scan.

**4. Three `docs/*.csv` are functional data read by `benchmark/expectations.py`.** Correct to
leave them. They are per-statement audited expectations — real balances, account masks and
periods — and redacting them breaks the benchmark. This is a genuinely hard case and it should
be named in the batch-9 planning record as its own decision (move them out of `docs/`, or accept
them as a second `corpus_cache`-style standing exclusion with a written justification). Note the
scanner currently has **no** rule for them, so they will keep appearing as residue in every
future scan until someone decides.

**5. The real account number in `tests/test_analysis.py` is not fixed.** The cell's reasoning —
one id among 820 is theatre — is sound as engineering triage, and `tests/test_lili.py` 138 → 0 is
a genuine worked example of the technique. But the card named that one id specifically and
carried it since batch 5, and a P0 hygiene card closing with the named item untouched should be
an explicit Ocean decision, not a paragraph in FP9. I verified the scanner still has teeth there:
820 sites survive at the tip, 132 of them DIGITS, and no exclusion rule silenced a DIGITS hit in
that file (`institution_zip` claims 2 sites there, both genuine ZIPs on address lines). The file
lost nothing between base and tip.

**6. The scanner is blind to `.log`, `.shas`, `.ps1`.** Correct, and correctly declined —
widening `TEXT_SUFFIXES` mid-card would have changed every count in the record. Should be the
first item of the follow-up card; `discovery_v12_run.log` is 1,194 unaudited lines of a tool that
printed document text.

**7. `institution_zip` is the rule the cell most wants a second opinion on.** It asked the right
question and my answer is the one it feared: **the rule is not safe as written** — see BLOCK 1.
The instinct that it deserved scrutiny was correct; the near-misses it chose to test all attack
the geometry (digit count, gap width, intervening digits) and none attacks the vocabulary. The
underlying idea is sound and the fix is small; a ZIP on an institution's own address genuinely is
furniture and genuinely should be excused. What must not ship is a rule whose trigger is a
two-letter token that this archive's own transaction descriptions print in prose.

**8. The corpus slice ran while another cell's floor was running.** Fine, and I did the same. The
gate is deterministic and offline; concurrency changes runtime, not outcomes.

**On the three mutants that survived a first run** (`R2` twice, `M7`/`M8`): this is the most
convincing part of the record. Each survivor named a real defect in a guard rather than in the
code — a fixture with no scannable digit run, and counter-samples moved to a century
`ISO_DATE_RE` never matches — which is exactly what a mutation table is for, and the cell
reported them instead of quietly repairing them. The same honesty is why MINOR 5 is a scope note
and not an accusation.

---

## WHAT I DID NOT VERIFY

* That **428** is the *smallest* whole-number scale with no collision. I verified the consequence
  that matters — `tests/test_lili.py` goes 138 → 0 and stays 0 — which is the claim the card
  needs. `--scale-search`'s minimality is a property of the search, not of the tree.
* `tools/fixpriv_invent.py` beyond reading it: it produces no headline number of its own.
* The archive sweep (`regfp_zero_movement_sweep`): not owed, and I agree it is not owed — it is
  owed when a reader changes, and AST identity proves none did.
* The two inherited suite failures at `2f24b06` in a detached worktree: I took the cell's
  reproduction and my brief's statement that both are Ocean's and fixed on train9. My own suite
  run shows those two and no others, which is the fact that matters here.

## RE-RUN TABLE

| # | proof | result | exit |
|---|---|---|---|
| 1 | whole-tree privacy scan, root base, `--ref 2f24b06` | 10,810 sites / 209 files; 3,351 documents read | 1 |
| 2 | whole-tree privacy scan, root base, `--ref 1e0a01e` | 10,645 / 203; every record number reproduces | 1 |
| 3 | whole-tree privacy scan, root base, `--ref 31255ef` | **10,677 / 203**; +32 sites vs `1e0a01e` | 1 |
| 4 | added-lines privacy scan `--base 2f24b06 --ref 31255ef` | **2 hits**, 1 file, both MONEY | 1 |
| 5 | per-rule silenced-site re-derivation at the tip (my own script over the scan's own hit list) | words 632,617 · round 9,052 · corpus 2,483 · subunit 1,270 · hex 536 · zip 104 · session 1 | 0 |
| 6 | reviewer near-miss probe over `excluded_by` (20 invented cases) | BLOCK 1 and MAJOR 4; `round_money` / `subunit_money` / `words_class` / `docs_session_date` behave as documented | 1 |
| 7 | reviewer over-reach probe (every silenced `hex_sha_substring` and `institution_zip` site re-read against its own line) | 8 raw over-reached hits / 3 sites, all the rule's own fixtures; 104 zip sites all genuine addresses | 0 |
| 8 | `fixpriv_ast_identity --base 2f24b06 --ref HEAD <3 paths>` | 3 files, 3 identical, 0 differing | **0** |
| 9 | `fixpriv_ast_identity --base 2f24b06 --ref HEAD` (bare) | `MISSING tests/test_fixpriv_ast_identity.py` | 2 |
| 10 | `cohort_replay --parser lili --expect-identical` | 11 / 11 preserved, identical | **0** |
| 11 | `cohort_replay --parser lili --parser bank_ozk --parser core_processor_signed_counts --expect-identical` | 27 / 27 preserved, identical, 0 newly validated, 0 regressions | **0** |
| 12 | `fixpriv_mutation_table` (no `-x`) | 22 / 22 killed / 0 survived; tree clean before and after | **0** |
| 13 | branch test files (110 + 12 + 14 + 58) | 194 passed | **0** |
| 14 | canonical guards (5 files) | 255 passed | **0** |
| 15 | canonical conformance (7 files) | 1,270 passed, 40 skipped | **0** |
| 16 | `python corpus_gate.py` | GREEN, 105 / 3 / 1, 14 CAD / 94 USD, provenance 7 / 4 / 1 / 7 / 89, 531.8 s | **0** |
| 17 | full default suite | 2 failed (both inherited and excused), 6,876 passed, 43 skipped, 3 min 32 s | 1 |
| 18 | `fixpriv_w3_redact --check-idempotent` + dry run | idempotent; W3 MONEY 1,377 · DIGITS 150 · DATES 223 on 1,074 lines | **0** |
| 19 | `_CENT` mutation experiment, base vs tip fixtures, 7 runs, tree restored each time | MAJOR 3's table | — |
| 20 | W3 append-only prefix check (`cmp` over the base-length prefix) | byte-identical; one appended section | **0** |
| 21 | corpus-marked slice (`pytest -m corpus`) | 30 passed, 6,925 deselected, 27 min 29 s | **0** |
| 22 | privacy scan of THIS review file (`--base 31255ef --ref HEAD`) | 2 hits on the first pass, **0** after the fix, 543 added lines, 3,351 documents read | **0** |

## RECOMMENDATION TO OCEAN

**BLOCK**, and it is a short list. Send back three edits — narrow `institution_zip`
(BLOCK 1), de-collide six lines of `§FIXPRIV` and re-measure the tip (MAJOR 1, MAJOR 2), and
un-scale two fixture perturbations (MAJOR 3) — plus the `hex_sha_substring` occurrence check
(MAJOR 4) and, ideally, the four new counter-cases in the block set and two new mutants. Every
one of those is a few lines; none touches production code, none can move a document, and the
replay and AST proofs will not need re-arguing, only re-running. Then this is an APPROVE, and the
program gets an exclusion table it can stand behind for the rest of the batch.

Ocean must also rule on: the production sweep as a second card with `analysis/consumers.py:90`
split out as a P0 hardcode; the record redaction (my recommendation: do not run it as specified);
the three `docs/*.csv` functional-data files; and whether `tests/test_analysis.py`'s named account
number may be carried past a P0 card that was written to remove it.
