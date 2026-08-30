# BATCH9 COMMSEC9 — independent adversarial review of `wave9-commsec`

Reviewer: independent Opus cell (the same one that reviewed HUNT9). Base `train9` at
`e26ec8d`, tip `588d8f4`, worktree `.claude/worktrees/mt9-commsec`. Run of record
`TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d`, cold cache
`.claude/recovery/webapp_data_train8_cold` (read-only). Nothing was asked of the cell;
every number below was re-measured, and the questions the record does NOT ask were asked
here. My own regex-bearing instruments were written with a file tool and byte-checked
(0 control bytes), per the batch-9 heredoc rule; the working tree was verified clean
before and after every step.

## Verdict

**CONFIRMED WITH FINDINGS.** 0 BLOCK · 0 MAJOR · 4 MINOR.

`newly validated = 0` is the correct outcome. The seven are honest L-1 refusals, the two
are honest column-direction refusals, and the refusal of the one document a solver could
reach survives the hardest test I could build against it. Every finding below is a record
correction; none touches a number, a proof or the verdict.

This cell had the HUNT9 lesson available and applied it: its ceiling bounds READINGS, not
merely relaxations — it installs a solved reading and classifies the result with the
platform's own classifier — and it discloses, in its own record and by sha, that one
document would reach `validated` under it. That disclosure is the opposite of the failure
mode a ceiling review exists to catch, and it is what makes this card auditable.

## 1. Re-measurement table

| claim | re-measured | agrees |
|---|---|---|
| no production change, at every commit | `git diff --stat e26ec8d 588d8f4 -- analysis ocr webapp discovery telemetry corpus_gate.py` → **empty**; whole branch = W3 + `tests/test_community_section_layouts.py` + three `tools/commsec_*.py` — all inside the card's declared ownership | ✔ |
| instruments unwired | `grep commsec_` over `analysis ocr webapp discovery telemetry benchmark tests corpus_gate.py`: **0**; unwired-experiments guard green | ✔ |
| gate table: L-1 **7**, block-walk **2**, grammar gap **0**, `TRACE-DISAGREES` **0** | probe re-run at the tip: **L1 7 / GRAMMAR 2**, TRACE-DISAGREES **0**; the seven shas are the seven named | ✔ |
| control `PARSES` 61/61 | re-run over the protected cohort: **PARSES 61 / 61**, TRACE-DISAGREES 0 | ✔ |
| the seven each hold 3 blocks, 2–3 publishing | re-derived from `_account_blocks` + `_parse_sectioned_statement` directly: **3 / 3 / 3 / 3 / 3 / 3 / 3** blocks, **3 3 2 3 3 2 2** publishing with transactions — **and every published block also reconciles** (§3) | ✔ (strengthened) |
| structure of the two (rows, figures/row, grid days, widest day, carried 0) | reproduced field for field: 117 rows `{1:107, 2:10}`, 20 grid days, 18 multi-row days, widest 13, carried **0**; 6 rows `{1:6}`, 4 grid days, 2 multi-row, widest 2, carried **0** | ✔ |
| row figures sum to both printed totals; row count = both printed counts; summary closes | **True** on both documents | ✔ |
| raw rows: one gap width, nothing after the figure | reproduced (109 and 7 own-line rows), **and extended to every row the cell excluded**: 130 and 12 rows found anywhere on a line, **gap width 1 on every one** (§3) | ✔ (strengthened) |
| the OCR text stage carries no geometry | the cached OCR-v4 artifact is `artifact.document = {model, page_integrity, pages}` with `pages: list[str]` — **text only, no positional token of any kind** (§3) | ✔ |
| sign search: `ambiguous(32)` and `UNIQUE_READING` | re-run: **ambiguous(32)** / **UNIQUE_READING** | ✔ |
| cross-check by brute force agrees | re-run: dynamic program **32**, brute force **32**, `agree: True`, widest day 13 | ✔ |
| the unique reading installed in memory publishes | re-run: `EA62…` → `failed / parser_declined`, 0 transactions; `FA0B…` → **`validated / approved`**, 6 transactions, `adb_ok` true, integrity flags empty | ✔ |
| generalisation over the 109 the module claims: 98 / 25 / 7 / 2 | re-derived independently: **132 account blocks — 98** no `Account Activity` header, **7** header with no posting rows, **25** whose rows all carry two figures, **2** whose rows carry one. Measured, not asserted | ✔ |
| `--parser community_section` preserved 59/59 identical, 2 review unchanged | at the tip: population 61, preserved **59 of 59**, payload identical **59**, changed 0, regressions 0, 2 unchanged non-validated — **EXIT=0** | ✔ |
| `--parser dakota_west --parser mission_valley` 39/39 identical | at the tip: preserved **39 of 39**, payload identical **39**, regressions 0 — **EXIT=0** | ✔ |
| `--group DECL:community_section` 9 unchanged | at the tip: 9 unchanged non-validated, payload changed 0, newly validated 0 — **EXIT=0** | ✔ |
| **98/98 under train9's STRICTER comparison** | the cell's worktree carries the older `cohort_replay`. Re-run with train9's version loaded in its place (empty containers as leaves, verified live before trusting it): population 100, **preserved 98 of 98, payload identical 98**, changed 0, regressions 0 — **EXIT=0**. The gap Ocean flagged is closed | ✔ |
| mutation table: M1 and M2 KILLED by their named killers | re-derived **without writing to the tree** — a mutated copy of the reader loaded as a separate module: M1 fails only the refusal test, M2 fails only the control; reader bytes unchanged; `git status --porcelain` clean (§3) | ✔ |
| canonical guards 255 | **255 passed — EXIT=0** | ✔ |
| canonical conformance 1,270 / 40 skipped | **1,270 passed, 40 skipped — EXIT=0** | ✔ |
| `tests/test_community_section_layouts.py` 44 → 46 | **46 collected** at the tip; `def test_` 42 → 44 (+2) | ✔ |
| privacy, added file lines: 0 | **hit_count 0** over **1,667** added lines, 70 documents, `no_cached_text []`, MONEY/DIGITS/DATES/WORDS all 0 — EXIT=0. `raw_hit_count 5` before exclusions: **round_money 3, words_class 2**, exactly as the record states | ✔ |
| privacy, commit messages: 0 in all classes | **10 commits scanned, MONEY 0 / DIGITS 0 / DATES 0 / WORDS 0** — EXIT=0 | ✔ |
| archive sweep, chunk `[0, 400)` | spot-check: 400 documents, **321 compared, 321 identical, moved 0**, `payload_now_raises` 0, `multi_artifact_documents` 0, `no_ocr_artifact` 4, `no_payload_raises_again` 74, `no_payload_now_publishes` **1** — and the one finding's sha is `0943986A52D8226C`, **one of the six `core_processor_enclosures` movers the record attributes to CP-DECLINES**. Attribution independently confirmed | ✔ |
| W3 = base + one appended section | base is a **byte-exact prefix** of the tip; `# §` headings 92 → 93; the new one is §COMMSEC9, last | ✔ |
| the main-checkout mistake was reverted | `main` and `train9` both carry **0** occurrences of `COMMSEC9`; main's working tree is clean for that file | ✔ |

## 2. The hostile questions, answered

**(1) Is "the column is not in the reader's input" literally true of the cached OCR-v4
text?** Yes, and the strongest form of the claim holds. The OCR artifact for both
documents is `{model, page_integrity, pages}` with `pages` a list of plain strings —
there is no bounding box, no column index, no offset, nothing positional anywhere in the
payload. Spacing is therefore the only channel a column could survive in, and it does not:
every posting row on both documents carries **exactly one space** before its figure and
**nothing after it**, on all 130 and all 12 rows a date-then-figure pattern finds anywhere
on a line — including the rows the cell's own measurement excluded because the layer welded
them onto a neighbour. Figure start offsets are simply prefix length, with no second mode
that an alignment would produce.

**(2) Does the ceiling bound RELAXATIONS or READINGS — and could a different reading decide
direction without a search?** It bounds readings, and I could not find a reading. Four
candidate readings, each measured:

* **a sign glyph on the row.** `EA62…` prints three leading-minus figures, which is a real
  lead. Located: two are the ledger's own `Beginning`/`Ending Balance` bookend rows and one
  is in the daily-balance grid furniture. **Posting rows printing a sign: 0 on both
  documents** — which is exactly what the module's `_SIGNED_MONEY` docstring says this
  platform does (a balance is the only signed figure it prints).
* **direction-bearing sections, or their `N item(s) totaling $X` trailers.** The specific
  alternative Ocean named. Measured: `_sections` returns **[]** on both documents and
  **0** section trailers are printed. There is one undifferentiated `Account Activity`
  table and no per-direction structure to read.
* **the description.** The tempting one, since 97 of 130 rows carry a direction-ish word.
  Measured with a deliberately generous vocabulary and every undecided row defaulted to the
  majority class: it decides only **41 of 117** and **1 of 6** rows, and the resulting
  ledger reproduces **none** of the four printed identities and only **5 of 20** and **2 of
  4** printed grid days. It is not a reading of the document; it contradicts the document.
* **entailment by the printed grid — the sharpest version, and the one that could have
  refuted the card.** A day with one posting row, or a day whose printed net equals plus or
  minus its own gross, has every row's direction *forced* by the grid alone. That is a
  reading, not a fit — and critically, it never consults the printed credit/debit totals or
  counts, so on a fully entailed document those four identities would **survive as
  independent checks** and the record's central objection ("after a solve every identity
  agrees by construction") would not apply. Measured: **`EA62…` 12 of 117 rows entailed,
  105 needing a choice; `FA0B…` 4 of 6 entailed, 2 needing a choice.** Neither document is
  fully entailed — including the one that would validate. The two undetermined rows on
  `FA0B…` can only be fixed by consuming the printed credit total and count, which is
  precisely the fitting the cell refuses. **The objection holds on the document that
  decides the card**, measured rather than assumed.

**(3) Is the "0 across the 109" generalisation measured or asserted?** Measured, and it
reproduces exactly — 98 / 25 / 7 / 2 over 132 account blocks, with the two one-figure
ledgers being the two in scope and no third member anywhere in the 109. (My first tally
disagreed at 26/1 because I discriminated on "any row carries two figures", which
mis-files `EA62…`'s ten description-embedded second figures; on the discriminator that
actually separates the shapes the record's numbers are right.)

**(4) Any test added that could weaken a future check?** No. One test asserts a refusal on
a fixture where exactly one solving assignment exists — I verified that uniqueness by hand
from the fixture's own figures, so the docstring's "not 'we could not tell' but 'we will
not fit'" is accurate. Its control asserts publication of the identical statement with the
balance column filled in, pinning the four amounts, their four directions **and**
`reconcile(stmt).ok`. Neither can license a future relaxation: the first is a wall, the
second pins correct behaviour on a statement that closes. Both are load-bearing (§3).

**(5) Any payload leaf changed anywhere?** None. Payload identical on 98 of 98 validated
documents across all three registrations, under both the older and the stricter
comparison, with 0 payloads changed and 0 leaf paths reported.

## 3. What I established beyond the record

* **Every posting row, not only the unwelded ones.** The record measures gap widths on the
  109 and 7 rows that sit on their own printed line and *asserts* the welded rows behave the
  same. Measured: 130 and 12 rows anywhere on a line, **gap width 1 on every one**, nothing
  after the figure. The assertion is now a measurement.
* **The seven L-1 blocks reconcile.** The record establishes that 2–3 blocks per document
  "publish". Stronger, and directly useful to `L1-ARCH-DESIGN`: every one of those blocks
  also passes `reconcile(...).ok` under the unchanged validator — **17 independently
  publishing, independently reconciling accounts across the seven documents**, reached with
  no account selection of any kind.
* **The mutation table, re-derived without touching the tree.** BATCH9-RULES now warns that
  a `git checkout --` harness can leave a mutant behind on a shared host. Both kills
  reproduce by loading a mutated copy of the reader as a separate module: M1 fails the
  refusal test and leaves the control passing; M2 fails the control and leaves the refusal
  passing. Each kill is **exclusive to its named killer**, which is the property the table
  claims and the stronger reading of "KILLED".
* **The entailment measurement** (§2, question 2), which is the test the record's own
  argument most needed and did not have.

## 4. Findings

### MINOR-1 — the record's stated discriminator for the absent balance column has seven counterexamples in its own census

COMMSEC9.3 offers `posting_days_whose_last_row_ends_on_that_days_printed_balance` as "the
measurement that says the balance column is ABSENT rather than assumed absent", with the
general claim that *"a ledger printing it ends each day's last row on the balance the
printed grid gives for that day"*.

Measured over the cell's own 109-document structure census, **seven account blocks that
print a running balance on every row also score 0** on that field — six of them
(`0139C091`, `4D15B2AC`, `823BE33E`, `909DEE01`, `A6A1234C`, `F388C276`) because they print
**no daily-balance grid at all**, so the field is trivially zero, and one (`8AB3A421`, a
one-day grid) because its single day does not land. As a general property of ledgers that
print the column, the sentence is false, and its counterexamples are inside the census the
same cell built.

The **conclusion is unaffected**, and the field does discriminate where it is applied: both
in-scope documents print a full grid covering **every** posting day (20 of 20 and 4 of 4),
and every column-printing block with a comparable grid lands on essentially all of its days
(18/18, 26/26, 24/24, 21/21, 19/19 …) while these two land on none. The absence is also
independently established twice over — one figure per row, and `_activity_rows` requiring
two monies. **Correction:** scope the sentence to blocks that print a grid covering their
posting days, and say the field is zero for three different reasons.

### MINOR-2 — the three refusal reasons are not equally strong on the document that decides the card

COMMSEC9.4 gives three reasons "in the order they carry weight". Measured, the order is
wrong and two of the three do not apply where it matters:

* **Reason 1 ("one document is not a rule") is mis-worded.** *"A widening whose own
  population contradicts it on half its members"* — the ambiguous member does not
  *contradict* the rule, it is **declined** by it, fail-closed. The proposed rule (solve;
  publish only on uniqueness) is general and safe on the member it cannot read; what is
  small is its **yield**, not its scope. That is still a good reason to refuse, but it is a
  different one, and the current wording invites Gustavo to dismiss a general rule as a
  one-document special case.
* **Reason 3 ("uniqueness is not correctness") does not apply to `FA0B…`.** Its evidence is
  that 10 of 117 rows carry a second figure inside the description — measured on `EA62…`,
  which is ambiguous and would not publish anyway. `FA0B…`, the document that *would*
  validate, prints `figures_per_row {1: 6}`: **every one of its six rows carries exactly one
  figure**, so the misread hazard the reason names is absent there.
* **Reason 2 ("fitting destroys the evidence") is the one that carries the refusal**, and
  my entailment measurement is what proves it carries on `FA0B…` specifically: 2 of its 6
  rows are fixed only by consuming the printed credit total and count, so those identities
  stop being independent checks on exactly the rows they were used to decide.

**Correction:** lead with reason 2 and attach the entailment numbers to it; re-word reason 1
to "the rule is general and fail-closed; its measured yield is one document"; scope reason 3
to `EA62…`.

### MINOR-3 — two proof-floor numbers are stale relative to the tip (disclosed by the cell)

The privacy rows record **1,592** added lines and **8** commits; at the tip the branch has
**1,667** added lines and **10** commits. The cell pre-empts this ("the counts move with the
record… the ZERO is invariant") and says both scans were re-run at the tip. I re-ran both at
the tip: **0 in all four classes on both surfaces**, `documents_read` 70, `no_cached_text` []
— so the claim is sound and only the two counts are stale. Refresh them at compose time.

### MINOR-4 — "grammar" carries two meanings in one table

The gate table's class column reads `GRAMMAR` for the two column-direction declines (the
probe's own literal), while a row of the same table reports *"a grammar gap on a shape ≥ 2
documents share, reachable by reading — 0"*. Both are true in their own sense and the record
explains the second, but a later reader tallying "grammar" from the class column will read 2
where the card means 0. Rename the probe's class for these (`NO_BLOCK_PUBLISHES` would say
what it measures) or annotate the column.

## 5. Explicit answers

| question | answer |
|---|---|
| newly validated 0 confirmed? | **YES.** `--group DECL:community_section --expect-identical` at the tip: 9 unchanged non-validated, newly validated **0**, payload changed 0, regressions 0, EXIT=0. The ceiling's own best case reaches `validated` on exactly one document and is refused; nothing is published. |
| previously validated preserved 98/98 identical? | **YES**, and under both comparisons. Worktree tool: 59/59 + 39/39 payload-identical, the 2 review unchanged, EXIT=0 each. train9's stricter `flatten` (empty containers as leaves, verified active): population 100, **98 of 98 preserved, payload identical 98**, 0 changed, EXIT=0. |
| no production change? | **YES.** Restricted-path diff empty; the branch touches only W3, one test file and three `tools/commsec_*.py`, all within the card's ownership; 0 references from any production tree; guards green. |
| privacy 0? | **YES on both surfaces.** Added file lines: hit_count **0** over 1,667 lines / 70 documents (raw 5, all excluded by named rules: round_money 3 in the card's own synthetic fixture, words_class 2). Commit messages: **0** in all four classes over 10 commits. |

## 6. Recommendation to Ocean

Accept the branch. It is a coverage card honestly closed at a measured zero, with the one
reachable document named, published in memory, and refused for a reason that survives
adversarial re-measurement. The four findings are record corrections; the strongest of them
(MINOR-2) does not weaken the refusal — it identifies which of the cell's three arguments
actually bears the weight, and supplies the measurement that proves it bears it on the one
document that matters.

**The two declines belong to the rung, not to this reader.** The direction is printed as a
column; the OCR-v4 artifact is text-only, with no positional token anywhere in the payload;
the flattened rows carry one space and nothing after the figure; and no geometry reaches the
claiming-parser path. `DESC-ROTATION` / `native_text` owns them, and a census should not
re-file them as a parser gap. **The seven belong to `L1-ARCH-DESIGN`**, and they arrive with
17 independently publishing, independently reconciling accounts and no account selection.

**Retire the `community_section` estimate to 0** for this card's population.
