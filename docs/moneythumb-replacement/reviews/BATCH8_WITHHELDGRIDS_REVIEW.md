# BATCH 8 — WITHHELD-GRIDS adversarial review

Branch `wave8-withheldgrids`, tip `1cdab07`, base `10cc722`. Independent
reviewer; did not write this code. Every number below was re-derived in this
review's own scratchpad. Before/after is measured against a base tree extracted
from `10cc722` by `git archive` (verified byte-identical to the branch worktree
for every file the branch does not touch); the archive, the artifact cache and
the discovery reports were read read-only by direct file path, the sqlite index
was never opened, and no hosted model was called ($0.00).

**One independent calibration first.** Over the 549 documents this review
recomputed on the base tree, the recomputed payload equals the run of record's
STORED analysis payload on 549 of 549 (`recomputed_base_vs_stored_mismatch=0`).
The base tree therefore is the code the run of record was produced with, and
every before/after below is a measurement of this branch and of nothing else.

---

## VERDICT: **APPROVE WITH FINDINGS** — 0 BLOCK, 4 MAJOR, 7 MINOR

The card's central claims hold and are stronger than the record argues them.
17 of 22 move `withheld/withheld_adb` -> `validated/approved`; every one of the
17 flips by a required check **PASSING**, not one by a check becoming
inapplicable; the required-check set is byte-identical and `analysis/adb.py` is
untouched; the 51-mover archive differential reproduces exactly, document for
document; exactly one pinned document's payload changes and its single moved
leaf is read by no required check and by no line of `corpus_gate.py`; and the
branch adds no archive-sourced literal to tracked source, measured against
276,037 distinct literals harvested from 1,163 archive documents rather than
the 42 the cell used.

What the findings are about is the **record**, not the arithmetic: the risk
register understates one rule's exposure, one rule table omits a rule that
shipped, one deleted rule is not as dead as recorded, one landed rule has no
measured effect at all, and a required check quietly loses all of its evidence
on documents outside the named population — reported by the record as a
diagnostic count.

---

## 1. FINDINGS

### MAJOR-1 — `posting_dates_cover_source` becomes vacuous on 21 documents, 16 of them already validated; the record reports this as a diagnostic count

**Claim reviewed.** WG10: the 12 diagnostic-only movers and the 12 in-family
`source_posting_days` movers moved "a diagnostic COUNT of the posting dates the
source prints. `missing_posting_dates` does not appear in the diff on any of
them, so `posting_dates_cover_source` decides the same way it did." WG3: "the
cost of being wrong is a check that is quieter than it should be, never a false
validation."

**Evidence.** Replay of 550 + 57 documents on both trees
(`replay.py`, exits 0; see the instrument table):

* 23 documents that were **already `validated`** — 11 `zions`, 1
  `community_section`, 7 `td_us`, 4 `woodforest` — lose **27 printed posting
  days** from the source set. Every one of those days was a **real** posting
  day: their `missing` set is empty before and after, so
  `source_dates ⊆ parsed_dates` at base and each removed day is a day the
  parser itself posts.
* On **16** of them the source set becomes **empty** (12 in-family go 1–2 -> 0;
  4 `td_us`/`woodforest` go 1 -> 0). Add 5 of the 17 movers that also end at 0
  (`31F347BE`, `5F1CC8C0`, `C6E5B0D3`, `1019F3C6`, `595137FD`) and **21
  documents in the run of record now carry a required check that cannot fail**,
  where it previously carried at least one real posting day.

The check outcome is unchanged today, which is what the record says. What the
record does not say is that a required check has been emptied of evidence on 21
documents — and `posting_dates_cover_source` is the only check in the set that
exists to catch a parser folding several printed posting days into one.

**Closure.** Record the evidence loss in W3 alongside the count: name the 16
already-validated documents whose source set became empty, and add to the risk
register that an empty source set makes this required check unable to fail. If
Ocean wants the check to keep its power, the cheapest guard is to treat
`source_posting_days == 0` on a document with a multi-row ledger as a
condition worth reporting rather than a silent pass.

### MAJOR-2 — WG11 item 2 states the wrong bound for the page-header rule; the rule drops a real posting date two lines from its money

**Claim reviewed.** WG11.2: "A genuine posting row printed in a moneyless run
directly under a page number, **with its amount more than three non-empty lines
away**, would lose its source date."

**Evidence.** `analysis/dates.py` (branch) lines 411–429: the page-header
`continue` fires **before** the money lookahead and is not conditioned on it.
Adversarial texts run on both trees (`adv.py`, exit 0 both sides):

| invented text (no archive content) | base | branch |
|---|---|---|
| page-number line, then a bare date, then a description, then its money | 1 date | **0** |
| page-number line, a moneyless caption line, then a bare date, description, money | 1 date | **0** |
| page-number line, then a flat row carrying its own money | 1 date | 1 date |
| page-number line, 4 filler lines, then a bare date/description/money | 1 date | 1 date |

The amount is two non-empty lines away in the first case and the date is still
lost. Ablating this rule alone over 1,163 archive documents changes 16 of them,
so it is not a marginal path. The rule is a *position* rule and the column-per-
line layout it was written for is exactly the layout that prints a bare date
first on a page.

**Closure.** Correct WG11.2 to the real bound (the rule fires whenever a
page-number line is among the three moneyless lines above the candidate,
regardless of where the money is), and either pin the shape above as a negative
test or condition the page-header refusal on the lookahead finding no money.

### MAJOR-3 — WG11 item 6's remediation is narrower than recorded: the same real account number is still in tracked source at the branch tip

**Claim reviewed.** WG11.6: a real ten-digit account number "had been sitting in
`tests/test_analysis.py` on main … **All three occurrences are now an invented
number, and the scan no longer finds it**."

**Evidence.** `git grep <that token> ` at `1cdab07` returns **2 hits**, both in
`docs/balance-metrics-audit-results.csv` — the corpus gate's pinned audit CSV —
and both identical to `10cc722` (`git grep <token> 10cc722` returns the same two
rows plus the two in `tests/test_analysis.py` that this branch fixed). The token
is printed on 2 of the 1,163 archive documents this review scanned, so it is
genuinely archive content. The CSV also carries those documents' balances and
account numbers by construction; it is a program-level artifact this branch did
not touch, which is why this is not scored as a BLOCK against the branch.

The `tests/test_analysis.py` half is correct and complete: all three occurrences
there are now the branch's invented ten-digit number, which occurs in **0 of
1,163** archive documents, and the test still pins the same thing (the parsed account number equals the
fixture's printed one) — the substitution changed the literal, not the gate.

**Closure.** Correct WG11.6 to name the file that still carries the token, and
escalate the pinned audit CSV to Ocean/Gustavo as its own decision (the batch-7
BLOCK class was written for parser source and fixtures; whether a pinned
expectations file is exempt furniture has never been ruled on).

### MAJOR-4 — the mutation harness that produced the 13/13 headline is not committed

**Claim reviewed.** WG10: "13 mutants, 13 killed, 0 survivors, 0 not-applied",
and the standing rule "commit your instruments under `tools/` when they produce
headline numbers".

**Evidence.** `tools/` at the tip contains `withheldgrids_leaf_diff.py` (this
card's other instrument, correctly committed) but no mutation harness; sibling
cells committed `tools/descattrib_mutate.py` and `tools/extractpriv_mutate.py`,
so the precedent is unambiguous. The harness exists only in the cell's temporary
scratchpad, which is not a durable artifact.

I re-ran it from that copy against the branch worktree: **13 mutants, 13
KILLED, 0 SURVIVED, 0 NOT APPLIED**, `MUTANTS_ALL_KILLED=True`, exit 0, 438 s,
and `git status --porcelain` empty afterwards. Every killer test named matches
the record's table exactly, mutant for mutant. Six were then checked by hand
against the mechanism their row names (M1 two-decimal bound vs the four-decimal
rate; M2 comma decimal; M5 page-header lookback — the fixture no longer carries
a column caption, so the mutant dies on the rule it names, which is the batch-7
trap the cell caught itself in; M6 the lookback's money stop; M8 the old
narrower gate; M13 the unsigned balance column; M15 the page sign-off). The
number is sound. Its instrument is not in the repository.

**Closure.** Commit the harness under `tools/` in the shape the other cells
used.

### MINOR-5 — WG3's rule table omits a rule that shipped

The record says "Four rules landed; a fifth was written, measured, and removed",
and its table has four rows. The branch carries **five**: the dot-leader strip
plus the bare `Date Balance` section caption (`analysis/dates.py` lines 272,
288, 373) is absent from the table, though it is named in the module docstring,
pinned by two mutants (M10, M11) and is what lifts `1019F3C6` — rule attribution
over that document's removals gives the daily-balance-section rule 2 of them,
and ablating M10 changes 3 archive documents while M11 changes 6.
**Closure:** add the row.

### MINOR-6 — the deleted "dead" rate rule is not dead under reconstruction, and its text is in no committed artifact

WG5 deletes the rate-only remainder rule because "the money-proximity rule
already refuses `<date> 0.0000%`". Restoring a faithful reconstruction of it and
re-scanning 1,163 documents changes **one** document, `59DA140E`
(`community_section`, `validated`): the branch still admits that document's
interest-rate line (shape `MM/DD/YYYY d.dddd%`) as a printed posting date, and
the deleted rule would have removed it. The rule's exact text survives nowhere —
not in the diff, not in the harness, not in W3 — so the "pins nothing" claim
cannot be reproduced as written. WG5's *operative* claim does reproduce: the
three rate-line documents lift without it.
**Closure:** correct the claim to what was measured, or restore the rule with
its own pin.

### MINOR-7 — the caption-stop half of rule 4 has zero measured effect and a demonstrated false-negative shape

Ablating the column-caption stop (M9) over 1,163 archive documents changes **0**
of them. Its only exercise is its own fixture. Adversarially it costs something:
a real bare-date row whose next line is a column caption loses its source date
(base 1 -> branch 0, `adv.py`). By the cell's own WG5 standard — "a rule that
survives its mutant is either untested or unnecessary, and only measurement
against the documents says which" — the measurement says unnecessary.
**Closure:** delete it as the other three were, or record it as archive-inert
and name the false-negative shape.

### MINOR-8 — the grid reader chooses rather than refusing on a contradicting cell

`analysis/community_section.py::_daily_balances` writes `balances[iso] = amount`,
so a date printed twice in the region with different balances is resolved
last-wins, silently — the ADB doctrine's "read what is printed, refuse on a
contradiction" is not implemented here. Instrumented on the block the parser
actually passes, over the 100 documents of the family in the run of record:
**10 documents** print at least one such repeat, **129** conflicting cells under
the branch pattern against **123** under the base one, and all four grid-lift
movers (`7F33CCF5`, `D0DE1BF0`, `D47263FD`, `F2931E93`) are among the ten. The
behaviour predates the branch; the branch adds six such cells. It is mitigated,
genuinely: a wrong last-wins stamp fails `running_balances_support_daily_ledger`,
which is the required check these four documents' lift turns on, so the failure
mode is fail-closed rather than a bad published figure.
**Closure:** refuse or flag a contradicting repeat, or record the last-wins rule
in the reader's own docstring.

### MINOR-9 — WG5's "the anchor changes nothing" holds for nine documents, not for the family

WG5 removes the grid-region anchor because "over all nine archive documents on
this template the anchored region and the words-only region produce an IDENTICAL
grid". Ablating the region start on the parser's own block over the family's 100
documents: the grid differs on **16**, with **183** grid days present only
because the region opens at the first printed occurrence of the heading words
(the method disclosure) rather than at the grid. Two movers are among the 16
(`5F1CC8C0`, `C6E5B0D3`); none of the four grid-lift movers is, and every
affected document still satisfies the required running-balance check, so nothing
published is wrong.
**Closure:** scope the claim to the nine documents it was measured on.

### MINOR-10 — two new community_section tests pass unchanged at base, and one names a mechanism the branch does not have

The 18 new tests run against the base tree: **11 fail** (they pin the change),
**7 pass**. Five of the seven are deliberate negative/ablation pins and are good
practice. The other two — `test_the_grid_and_the_method_disclosure_are_not_confused`
and `test_a_document_that_prints_no_grid_publishes_no_printed_balances` — pin
base behaviour, and the second's docstring says *"The header anchor is required,
not optional"*. There is no header anchor: it was deleted in WG5. The test passes
because the disclosure prints no `date`-adjacent money, not because of an anchor.
`test_the_money_presence_test_reads_a_comma_decimal_amount` also passes at base,
for a different reason than it states (base admits that line without needing to
see money at all); its mutant M2 does pin the rule, so this is a docstring
problem rather than a coverage hole.
**Closure:** fix the docstring; mark both as characterization.

### MINOR-11 — three record numbers that do not reproduce

* **WG10 privacy** gives two different diff sizes in one paragraph — "594 added
  lines" and "1,127 added lines". Measured: 558/559 insertions at the
  privacy-scan commits (`d4a0d6d`, `ca04664`), 1,127 at `a7af98f`, **1,212** at
  the tip. Neither figure is the tip, so the last 85 added lines (all W3 prose)
  were never covered by the cell's own scan. (This review scanned the tip: see
  §4 — nothing was hiding there.)
* **WG4's grid table** gives `F2931E93` grid days 22 and posting days 21 while
  the column "grid days missing a posting day" reads 0. Measured: the grid has
  22 days, the ledger 21, so exactly one grid day carries no posting row.
* **WG0's headline** "four one-line reader defects" counts the region anchor,
  which WG5 measured as a non-defect and removed. The branch ships **three**
  reader hunks plus the heuristic.

**Closure:** re-measure and correct all three.

---

## 2. THE 17 MOVERS — which check flipped, and how

Every flip is `False -> True` on a check that is present and required on both
sides. **No check became NOT APPLICABLE or skipped on any of the 17**: the
required-check set has the same members and the same size before and after on
every document (13 where the ledger prints running balances and the source text
is present, 12 otherwise), and on the branch **every** required check passes on
all 17 — not merely the one that had been failing.

| sha8 | reader | required check(s) that flipped | flipped by | source-date set |
|---|---|---|---|---|
| `7F33CCF5` | community_section | `running_balances_support_daily_ledger` | **PASS** | 0 -> 0 (empty at base too) |
| `D0DE1BF0` | community_section | `running_balances_support_daily_ledger` | **PASS** | 0 -> 0 |
| `D47263FD` | community_section | `running_balances_support_daily_ledger` | **PASS** | 0 -> 0 |
| `F2931E93` | community_section | `running_balances_support_daily_ledger` | **PASS** | 0 -> 0 |
| `31F347BE` | community_section | `posting_dates_cover_source` | **PASS** | 1 -> 0 (now vacuous) |
| `C6E5B0D3` | community_section | `posting_dates_cover_source` | **PASS** | 1 -> 0 (now vacuous) |
| `5F1CC8C0` | community_section | `posting_dates_cover_source` | **PASS** | 1 -> 0 (now vacuous) |
| `05B45576` | regions | `ledger_reconciles_to_closing` + `final_balance_matches_statement_closing` | **PASS** | 1 -> 1 |
| `6439032B` | regions | same pair | **PASS** | 1 -> 1 |
| `EB2D2C7B` | regions | same pair | **PASS** | 1 -> 1 |
| `36B502B8` | navy_federal | `posting_dates_cover_source` | **PASS** | 21 -> 20 |
| `74F34B80` | navy_federal | `posting_dates_cover_source` | **PASS** | 22 -> 20 |
| `60B0EE6A` | navy_federal | `posting_dates_cover_source` | **PASS** | 19 -> 18 |
| `6F3DEB4D` | navy_federal | `posting_dates_cover_source` | **PASS** | 19 -> 19 (ledger re-dated) |
| `1019F3C6` | zions | `posting_dates_cover_source` | **PASS** | 2 -> 0 (now vacuous) |
| `595137FD` | zions | `posting_dates_cover_source` | **PASS** | 1 -> 0 (now vacuous) |
| `4BE21534` | wells_fargo | `posting_dates_cover_source` | **PASS** | 11 -> 10 |

The three `regions` movers each gain exactly one row (46->47, 33->34, 38->39), a
withdrawal, after which the ledger reconciles to the printed closing balance —
the page sign-off deletion is real and its repair writes no amount. The four
`community_section` movers gain the negative grid days as **2, 3, 4 and 3**
changed end-of-day balances respectively (newly stamped plus corrected, all of
them negative), which is exactly WG4's "2, 3, 4 and 3 negative days dropped".

**WG1 reproduces without divergence.** All 22 are `withheld/withheld_adb` at
base with precisely the causes the census recorded: 4 `community_section` on
`running_balances_support_daily_ledger`; 3 `community_section` + 4
`navy_federal` + 2 `zions` + 1 `wells_fargo` on `posting_dates_cover_source`;
3 `regions` + 4 `pnc` on `ledger_reconciles_to_closing` +
`final_balance_matches_statement_closing`; `A4E41C80` on
`opening_balance_matches_statement` + `running_balances_support_daily_ledger`.
The five non-movers are byte-identical on the branch and keep the same failing
checks. WG7's PNC capture ratios reproduce to the tenth (0.0/93.8, 0.0/7.7,
23.6/47.4, 100.0/95.3), and WG6's ratified `wells` fail-closed pin exists and
says what WG6 quotes.

---

## 3. PINNED MOVEMENT

**Exactly one pinned document's payload changes: `413AD4C2` (`ibc`), whose
single differing leaf is `metrics.adb.source_posting_days`.**

This was measured over **all 109** pinned documents in
`docs/balance-metrics-audit-results.csv`, not only the 20 in the card's six
families: 108 produce a payload on both trees and 107 of those are leaf-for-leaf
identical; the 109th (`0CBD2AD8`) is the ratified pinned refusal and raises the
same exception on both trees. `413AD4C2`'s class (`withheld`), its required-check
set, its failing checks and its (empty) `missing_posting_dates` are all
unchanged; the removal is attributable to the generalised money-proximity rule.

The moved leaf is **read by nothing that gates anything**: `source_posting_days`
appears in `analysis/adb.py` (assignment only), in two assertions in the test
suite, and in `telemetry/diagnostics.py`. It appears **nowhere** in
`corpus_gate.py`, and no required check consults it — `posting_dates_cover_source`
is computed from `missing`, not from the count.

The 20 pinned documents in the six families do not move, as recorded. Note for
the ledger: only 17 of those 20 appear in the run of record's `rows.csv` at all
(the pinned `wells_fargo` set contributes 2, not 4, and the pinned
`mission_valley` document contributes 0), so for three of them the archive
differential is silent and the corpus gate is the only evidence — which is what
the record leans on anyway.

---

## 4. THE 51-MOVER DIFFERENTIAL, RE-DERIVED

| population | replayed | movers | leaves that moved |
|---|---|---|---|
| the six families (455 distinct shas) + `first_community` (3) + all 109 pinned | 550 | **39** | 17 verdict movers; 10 documents moving only `statement.transactions[].running_balance` (20 leaves, one of them the `detection.known_funders[]` echo); 12 documents moving only `metrics.adb.source_posting_days` |
| `ibc` (its 1 document in the run) | 1 | **1** | `metrics.adb.source_posting_days` |
| `td_us` (38) + `woodforest` (19) | 57 | **11** | `metrics.adb.source_posting_days`, one leaf each |
| **total** | **607** | **51** | — |

`newly_publishes = 17` and `payload_now_raises = 0` across all 607; the only
verdict or required-check movement anywhere is the 17. This matches WG10's
17 + 22 + 12 = 51 document for document and class for class.

**Removal-only, tested where it is most at risk.** The one add-direction change
in the diff is the money-presence widening (`\d[\d, ]*[.,]\d{2}(?!\d)` admits the
French `1 234,56`, which base did not see). Over **1,163** documents — the six
families, every pinned document, `td_us`, `woodforest`, and every Canadian and
French-language parser in the run — the branch's source-date scan gains a date on
**0** documents, loses dates on 36, and raises on 0. WG3's blanket "every rule can
only REMOVE a date" is not true of the *code* (three sites read the widened
pattern in the keep direction), but it is true of this branch against this
archive, and the widening is load-bearing rather than decorative: reverting the
comma decimal alone would strip 143 source dates from 17 French documents,
including 16 from the pinned `cibc_french` statement — exactly the figure WG3.1
records.

**Attribution of the removals** (traced against the real function, verified
identical on all 23 named documents): R3 forward-label 11, R2 page-header 9,
R4 money-proximity 5, dot-leader daily-balance section 2.

---

## 5. DOCTRINE AND PROTECTED SURFACE

* **`analysis/adb.py` byte-identical.** `git diff 10cc722..HEAD -- analysis/adb.py`
  is empty. The `required` list and its three conditional appends are unchanged,
  and the conditions that make each conditional check applicable
  (`closing_balance is not None`, a printed running balance exists,
  `source_markdown` is truthy) are unchanged. No document in the 607 changed the
  membership of its required set.
* **Financial core untouched.** The changed files are
  `analysis/community_section.py`, `analysis/dates.py`, `analysis/navy_federal.py`,
  `analysis/regions.py`, four test files, `tools/withheldgrids_leaf_diff.py` and
  the W3 log. Reconciliation, metrics, classification and serialization are not
  in the diff.
* **No check made trivially true by a new field.** No changed reader publishes a
  `bank_reported_*` figure or a `stated_daily_balances` series;
  `community_section` still stamps the grid onto each day's last row rather than
  publishing it as bank evidence (confirmed: no `stated_daily_balance_count`
  leaf moves anywhere in the 607). The one route by which a check does become
  trivially true is the emptying of the source-date set — MAJOR-1.
* **Repair doctrine.** No hunk writes, substitutes or repairs an amount, a
  balance or a date. `regions` cuts printed furniture off a row and reads what
  remains; `navy_federal` narrows an existing attribution branch; the grid reader
  reads a printed sign it was previously unable to match. The one place the code
  *chooses* rather than refusing is the duplicate grid cell — MINOR-8.
* **Detection unchanged.** `regions.ISSUER_FOOTER.upper()` is character-for-
  character the literal the detector previously carried inline, so no detection
  marker moved; the canonical guard set passes 252, unchanged at registry 75.
* **The compatibility branch.** The narrowed `navy_federal` branch is now taken
  only where the row has neither a date nor a description of its own. Every
  document that could take it is inside the replayed `navy_federal` population
  (all 52 in the run of record); four move, all four named, and no other
  `navy_federal` document changes a single leaf.

---

## 6. INSTRUMENTS RE-RUN

| instrument | exit | wall |
|---|---|---|
| `pytest -q` on the branch's four test files (281 passed) | 0 | 28 s |
| replay of the 23 named documents, base tree | 0 | 30 s |
| replay of the 23 named documents, branch tree | 0 | 21 s |
| replay of 550 (six families + `ibc` + `first_community` + all 109 pinned), base tree | 0 | 511 s |
| replay of the same 550, branch tree | 0 | 471 s |
| streaming leaf/verdict comparison of the 550 | 0 | 67 s |
| replay of 57 (`td_us` + `woodforest`), both trees | 0 | 74 s |
| comparison of the 57 | 0 | ≈3 s |
| markdown resolution of 1,163 documents | 0 | 21 s |
| `source_posting_dates` over the 1,163, branch tree | 0 | 16 s |
| `source_posting_dates` over the 1,163, base tree | 0 | 6 s |
| adversarial texts (14 shapes), both trees | 0 | <1 s |
| the cell's mutation harness, 13 mutants, no `-x` | 0 | 438 s |
| 8 rule ablations over the 1,163 | 0 | ≈170 s |
| comma-decimal ablation over the 1,163 | 0 | ≈25 s |
| instrumented grid reader over the family's 100 documents | 0 | ≈20 s |
| the 18 new tests replayed against the base tree | 0 | 3 s |
| CANONICAL guard set (252 passed) | 0 | 16 s |
| privacy scan, 23 documents | 0 | ≈40 s |
| privacy scan, 1,163 documents | 0 | ≈120 s |

`git status --porcelain` in the worktree was empty before the mutation run,
after it, after every ablation, and at the moment this file was written; the
mutation harness refuses a dirty tree and restores with `git checkout --`, and
both were observed to work. Times marked ≈ were not stopwatch-measured.

---

## 7. PRIVACY RE-MEASUREMENT (this review's own)

Harvested every amount-with-cents (both decimal marks), full or partial date,
digit run of 5 or more, capitalised token and capitalised bigram from the cached
text of the 22 named documents plus `413AD4C2` — **14,382 distinct literals** —
and separately from **1,163** archive documents — **276,037 distinct literals**.
Each was searched against all 1,212 added lines of `git diff 10cc722..1cdab07`,
then filtered against the vocabulary the tracked repository already carried at
`10cc722` so that a coincidence predating the branch is not scored against it.

* 23-document population: 231 raw intersections, **10 residual**.
* 1,163-document population: 338 raw intersections, **12 residual**.
* Every residual is generic: partial calendar dates, a rate-shaped two-decimal
  number, and English or banking word pairs. **Not one is an account number, a
  personal or business name, a reference, or an amount-with-cents distinctive to
  a document.**
* The invented fixture account numbers occur in **0 of 1,163** archive documents.
  The two round figures in the `navy_federal` fixture occur in 641 and 102 of
  them — coincidences of the shape any archive of this size contains, exactly as
  WG10 says.
* **Archive-sourced literals added by this branch: 0.** The cell's claim
  reproduces, on a population 27x larger than the one it used.

The one thing that does not reproduce is the *removal* claim — see MAJOR-3.

---

## 8. CLAIMS THIS REVIEW COULD NOT VERIFY

1. **The full-archive sweep** (3,380 documents, 2,558 compared, 2,507 identical,
   51 moved, 0 `no_payload_now_publishes`, 0 `payload_now_raises`). The review
   brief forbids an archive-wide sweep. What is verified instead: the 51 movers
   reproduce exactly and document-for-document within the six families, `ibc`,
   `td_us`, `woodforest` and all 109 pinned documents; and the source-date scan
   gains nothing on 1,163 documents. Undemonstrated: that no document outside
   those 1,163 moved.
2. **`corpus_gate.py` GREEN**, the full default suite (5,875 passed) and the
   CANONICAL conformance set (1,164) — out of scope by instruction. The guard set
   (252) was run and passes.
3. **The exact text of the three deleted rules.** WG5's ablations are recorded
   but the deleted code is in no committed artifact, so they were re-tested
   against reconstructions; one of the three disagreed (MINOR-6) and the region
   anchor's ablation is reconstruction-sensitive (MINOR-9).
4. **The claim that a folded posting day would still be caught.** MAJOR-1 and
   MAJOR-2 establish shapes where it would not be. No archive document currently
   exhibits one — 0 of 607 replayed documents changed a check outcome outside the
   17 — but the class is open.

---

## 9. WG11 AS THE CELL RECORDED IT, AND WHAT THIS REVIEW MAKES OF IT

1. *The money-presence test is now wider; a false money reading can only keep a
   date the old code also kept.* **Confirmed and measured:** 0 documents gain a
   source date over 1,163. The widening is also necessary rather than cosmetic —
   reverting it strips 143 dates from 17 French documents.
2. *The page-header lookback is a position rule bounded to three moneyless
   lines; a genuine posting row with its amount more than three non-empty lines
   away would lose its source date.* **Wrong bound — MAJOR-2.** The rule fires
   before the lookahead; a real row loses its date with its amount two lines
   away. The archive shows no such document today.
3. *`posting_dates_cover_source` got quieter on 3 pinned documents and on the
   named movers; on the pinned three the outcome does not move.* **True but
   incomplete — MAJOR-1.** It also got quieter on 23 already-validated
   non-pinned documents, losing 27 real posting days, and became vacuous on 21
   documents overall.
4. *`A4E41C80`'s defect is unfixed; its ledger does not close.* **Confirmed:**
   byte-identical on the branch, same two failing required checks, and the
   ratified `wells` fail-closed pin exists and says what WG6 quotes.
5. *PNC-ACTIVITY-DETAIL / PNC-DAILY-GRID / PNC-GRID-SECTION carded.* **Confirmed
   as honest:** all four `pnc` documents are untouched by every hunk, and WG7's
   capture ratios reproduce exactly.
6. *A real account number was in tracked source on main and is now invented;
   Ocean should decide whether a wider fixture sweep is owed.* **Half done —
   MAJOR-3.** The `tests/test_analysis.py` half is complete and correct; two
   occurrences of the same token remain in `docs/balance-metrics-audit-results.csv`
   at the tip. The wider sweep the cell asks for is owed, and this review's own
   1,163-document scan is a usable instrument for it.

---

*Reviewer's note on host discipline: this review ran at most one heavy process
at a time, never touched `.claude/worktrees/mt8-coreenc` or any process it did
not start, and wrote only this file into the branch. The session scratchpad is
shared with the concurrently running `coreenc` reviewer — one filename collided
and was renamed; no measurement in this review was affected.*
