# BATCH 8 · GLANCE — independent adversarial review

**Target.** Branch `wave8-glance`, tip `9ea7d78`, base `10cc722`, worktree
`.claude/worktrees/mt8-glance`. Card `docs/agent-handoffs/GLANCE.md`; cell
record `docs/moneythumb-replacement/W3_TRACKA_LOG.md` §GL0–GL11.

**VERDICT: APPROVE WITH FINDINGS — 0 BLOCK, 2 MAJOR, 5 MINOR.**

The reader's substantive claims hold under independent measurement. The
movement (5 published / 3 refused / 14 untouched), the detection reach
(exactly 22 of 3,351, nothing else), the sign rule, the identity closure 8/8,
the refusal's doctrine basis, the both-grids disagreement 14/14, the mutation
table's 37 killers and 3 control arms, and every gate-attribution the record
claims all reproduced. What is wrong is in the RECORD, not in the reader: one
proof-floor artifact was never run or never transcribed, and one safety claim
about the pinned corpus is factually inverted in three places, two of them
tracked source.

## The closed file list

`git diff --stat 10cc722..wave8-glance` — 8 files, +2,502 / −7:

| file | + | − |
|---|---:|---:|
| `analysis/category_partition.py` | 943 | 0 |
| `analysis/parser_registry_entries.py` | 37 | 0 |
| `docs/moneythumb-replacement/W3_TRACKA_LOG.md` | 555 | 0 |
| `tests/data/parser_conformance_fixtures.py` | 10 | 0 |
| `tests/test_category_partition.py` | 679 | 0 |
| `tests/test_parser_conformance.py` | 5 | 4 |
| `tests/test_parser_registry_entries.py` | 24 | 3 |
| `tools/glance_detection_probe.py` | 249 | 0 |

Protected modules confirmed untouched by the diff: `fiserv_premier`,
`core_processor_counted`, `core_processor_daily`, `core_processor_sectioned`.
`corpus_gate.py` and `analysis/count_semantics.py` are not in the diff at all,
so the "additive only" requirement is satisfied vacuously. §GL7B's hunk
arithmetic (7 files, +1,947 / −7, excluding the log) re-derives exactly.

---

## Findings

### 1. MAJOR — the archive differential is a placeholder, not a measurement

**Claim.** §GL8: "The archive sweep. `python -m tools.regfp_zero_movement_sweep`
at the branch's final production tree … in four chunks whose counts add", and
"`payload_now_raises` is **0** … and `moved` is **0**: not one existing payload
changed a single field." §GL9B's proof table closes with an "archive
differential, 4 chunks" row.

**Evidence.** The record carries literal unsubstituted tokens where those
numbers belong: `SWEEP_TABLE` (`W3_TRACKA_LOG.md:44121`), `SWEEP_FINDINGS`
(`:44124`), `SWEEP_EXIT` (`:44195`) and `DOCS_COMMIT` (`:44231`). The section
was committed verbatim from an uncommitted worktree file at the batch-8
rehydration (`4b4558d`), so the placeholders are the state of the evidence, not
a rendering artifact. The wave rules make the full sweep owed once per card at
its final production tree; §GL8's two zero-claims therefore stand on nothing
committed. I was instructed not to run an archive-wide sweep, so I did not
close this gap; what I can say is that the ONLY mechanism by which this branch
can reach a document is detection, and the committed probe enumerates that
reach completely (finding 0 movers outside the named 22 — see the re-run
table), and that all 14 documents whose payload could have moved are
byte-identical base vs branch. The sweep would be confirmatory rather than
load-bearing, which is why this is MAJOR and not BLOCK.

**Required closure.** Run `tools.regfp_zero_movement_sweep` at `9ea7d78`
against the run of record and its baseline settings key, in chunks whose counts
add, and replace all four placeholders with the measured table, the findings
list and the verbatim exit codes — or Ocean runs it at the composed train and
records the result against this card.

### 2. MAJOR — "no pinned corpus document prints this template" is false, and it is asserted in tracked source

**Claim.** §GL5, third bullet: "No pinned corpus document prints this template,
so the edge moves nothing in the 109." The same sentence appears twice in
tracked source: `analysis/parser_registry_entries.py` (the `supersedes`
override comment) and `tests/test_parser_registry_entries.py` (the
`supersedes` pin comment).

**Evidence.** `tests/data/parser_expectations.json` pins exactly one document
whose registered parser is the issuer-specific reader (`content_sha256`
prefix `6EFD091D`), and that sha is one of the 14 the new registration claims.
Measured at `9ea7d78` with the live registry over that document's cached text:
`category_partition.detect(...).claims` is **True**; with the
`wilson_muir → category_partition` edge removed, `resolve` has two surviving
claimants and the document goes **ambiguous** (14 of 14 do). So a pinned corpus
document DOES print this template, and the corpus gate's green depends on the
new edge rather than being independent of it. The stated conclusion is
nonetheless true and I verified it: that document's published payload is
byte-identical base vs branch (identical canonical-payload digest under a
base tree materialised from `10cc722` git blobs, and identical to the run of
record's own stored payload). Dispatch on it at HEAD is
`claimed/wilson_muir`, `attempted=[]`, `candidates=['wilson_muir']`, so its
recorded chain prefix is unchanged; `tests/test_parser_expectations_baseline.py`
passes (9 passed, exit 0) and the chain prefix is taken from the legacy
pipeline order, which the band move does not touch.

**Required closure.** Correct all three sentences to state what is true: one
pinned document prints this template, it is one of the 14, the edge is what
keeps it on the issuer reader, and its payload is byte-identical base vs
branch. A safety claim whose stated evidence is the opposite of the fact is
the class of record error the wave rules exist to prevent, even when the
conclusion survives.

### 3. MINOR — three headline numbers have no committed instrument

**Claim.** The wave rules: "commit your instruments under `tools/` when they
produce headline numbers."

**Evidence.** `tools/glance_detection_probe.py` is committed and reproduces
§GL7 exactly. Three other headline results have no committed instrument:
§GL1's per-document outcome table (the family replay), §GL3.2's "14 of 14
print both grids, 0 identical, 2–10 differing days of 16–22 shared, collected
carries more days on 13 of 14", and §GL6's `killed by` column, which the
committed suite does not assert — `test_every_gate_is_killed_by_its_own_mutant`
asserts only that the mutant is declined, never by which gate. I rebuilt all
three. Every number reproduced, including the 2–10 / 16–22 / 13-of-14 spread
and the full 37-row attribution with zero disagreements.

**Required closure.** Commit the replay and attribution instruments under
`tools/`, or Ocean records this review's reproduction as the evidence for
those three tables.

### 4. MINOR — the sign doctrine has a fourth case, and the platform prints it

**Claim.** Module docstring and §GL2: "Three meanings, two characters, and the
column tells them apart. A trailing plus on an AMOUNT is a direction. A
trailing minus on a BALANCE is a sign." M08 pins "a trailing PLUS on a grid
balance is refused", and `_summary` refuses `mark == "+"` on both dated
balances.

**Evidence.** Measured over the eight: four of them print a trailing PLUS on
the bank's own average-balance entry — which is a BALANCE, on the same printed
line as the two dated balances the reader refuses a plus on. `_AVERAGE_ENTRY_RE`
accepts it and reads it as positive. So the platform demonstrably marks a
balance with a plus, and the reader's rule is not "the column tells them apart"
but "the column tells them apart except on the average". Constructed
adversarially: a plus on the ending balance and a plus on the balance forward
both DECLINE the document. Fail-closed, so nothing wrong is published — but a
printing this platform is observably capable of would cost the document, and
neither the docstring nor §GL11 names it.

**Required closure.** Name the fourth case in the module docstring and add it
to §GL11's carried risks.

### 5. MINOR — the sectioned issue never refuses a row mark that contradicts its section

**Claim.** §GL2 and the module docstring: on the sectioned issue "Direction
comes from the SECTION", and the reader "REFUSES" combinations of mark and
column the platform has not printed.

**Evidence.** `_unified_rows` refuses a trailing minus on a row amount (M10)
and a trailing plus on a row balance. `_sectioned_rows` reads only the
magnitude through `_magnitude`, so a mark on a sectioned row is silently
discarded. Constructed: a row carrying a trailing plus inside a debit section
publishes as a debit, with no refusal and no flag. Reachability measured over
all 22 documents: across every sectioned ledger section the platform prints
**0** marked rows of either sign (1,802 sectioned-ledger rows), so this is unreachable
in today's archive — but it is an unrefused contradiction in a reader whose
whole thesis is that the platform prints the direction, and it is the exact
asymmetry the unified path was built to close.

**Required closure.** Either refuse a marked row on the sectioned issue, or
name the asymmetry and its zero-reachability measurement in §GL11.

### 6. MINOR — the published direction totals are sums the document prints no total for

**Claim.** §GL9.4 identifies that gating each direction's COUNT against the
rows read makes a reconciler comparison a tautology, and declines the
`count_semantics` promotion on exactly that ground.

**Evidence.** The same tautology applies to the direction TOTALS and is not
named. `stated_total_credits` / `stated_total_debits` are sums the reader
computes over the partition's per-category figures; this platform prints no
direction total anywhere, so the values are aggregates rather than printings.
`analysis/metrics.py` consumes them as `effective_total_deposits` /
`effective_total_withdrawals`. Measured on all five published documents: the
provenance stamped is `bank_stated_unverified` in both directions, which is
the honest label and is why this is MINOR rather than a repair-doctrine
finding — every summand is a printed figure, nothing is written or
substituted. Verified separately that no published figure is manufactured:
each of the opening balance, closing balance, service charge, bank average,
every daily balance and every row amount, date and running balance is a token
the document prints; the only two derived values are the direction totals /
counts above and `period_start`/`days_in_period`, both of which are gated
against the platform's own printed cycle length.

**Required closure.** Name the totals tautology alongside the counts one in
§GL9.4 or §GL11.

### 7. MINOR — four statements in the record do not hold literally

**Claim / evidence**, each measured at `9ea7d78`:

* The card's and §GL2's framing that there is "NO category vocabulary in the
  module" — nine of the platform's category labels appear in
  `analysis/category_partition.py` lines 18–22. The sign DECISION uses none of
  them and the fixtures prove it with invented labels, so the substance is
  intact; the claim as phrased is not. The shared privacy scan flags three of
  those lines.
* §GL1: "The eight are two consecutive-month chains of two accounts." Measured:
  **three** distinct printed account slots — one singleton, one three-statement
  chain, one four-statement chain, so seven of the eight are in a chain. The
  headline that follows it is right: **5 of 5** chain edges close, on both the
  date and the balance.
* §GL4: "exactly one `SUMMARY Type : … Status : …` control line, exactly one
  `Category Number Amount` line". The shared `unique_match` refuses only a
  second DISTINCT printing; a document carrying two IDENTICAL partitions
  publishes (constructed and confirmed). That is the shared helper's
  documented contract — a page header repeats — but it is not what §GL4 says,
  and M37 only ever exercises the distinct case.
* Ocean's pre-review note records 21 furniture bigrams from the shared scan;
  at the tip the scan reports **22**.

**Required closure.** Correct the four sentences. No code change.

---

## Re-run table

All at `9ea7d78`, worktree `.claude/worktrees/mt8-glance`, sequential, one
heavy process at a time. Exit codes verbatim.

| instrument | result | exit | s |
|---|---|---:|---:|
| `pytest -q` the branch's own three test files | 1,061 passed, 36 skipped | 0 | 7 |
| `pytest -q tests/test_category_partition.py` | **80 passed** (§GL9B: 80) | 0 | 1 |
| canonical guard set (5 files) | **252 passed** (§GL9B: 252) | 0 | 12 |
| canonical conformance set (7 files) | **1,176 passed, 36 skipped** (76 × 75 = 5,700) | 0 | 5 |
| `pytest -q tests/test_parser_expectations_baseline.py` | 9 passed | 0 | 4 |
| family replay, branch tree, 22 documents, end to end | 19 validated/approved, 3 failed/parser_declined | 0 | 43 |
| family replay, base tree from `10cc722` git blobs, same 22 | 14 validated/approved, 8 failed/no_parser_matched | 0 | 27 |
| mutant killer attribution, 40 rows | 37 killed, 0 unattributed, 0 disagreements, 3 controls publish | 0 | 1 |
| sub-gate attribution, the 11 rows folded into one gate | each trips exactly the sub-check its row names | 0 | 1 |
| evidence audit over the 22 (grids, partition, marks, ADB) | see below | 0 | 1 |
| refusal audit over the 8 (which gate rejects; six ADB bases) | see below | 0 | 2 |
| adversarial texts, 18 constructions | 0 raised | 0 | 1 |
| cross-branch collision, `train8`'s 77 registrations | 0 collisions both directions | 0 | 10 |
| decline-site / provenance / chain audit | see below | 0 | 12 |
| `tools.glance_detection_probe` over the run of record | 3,351 probed, 22 claimed, 0 ambiguous | 0 | 105 |
| shared `tools/privacy_scan_branch.py` over the 22 | 22 hits, all WORDS | 1 (by design on hits) | 3 |

**What the replays prove.** Base → branch, by `content_sha256`: five of the
eight move `failed/no_parser_matched` → `validated/approved`; three move
`failed/no_parser_matched` → `failed/parser_declined`, each with
`dispatch.outcome == "unclaimed"` and `attempted == ['category_partition']`,
which is exactly the input `discovery/runner._failure_reason` turns into that
label. All fourteen issuer-reader documents keep
`validated/approved`, and their canonical payload digests are identical base vs
branch AND identical to the run of record's stored payload for each. 5 + 3 = 8
and 8 + 14 = 22 both close.

**What the probe proves.** 3,351 documents hold cached text (29 of the 3,380
hold none). The registration claims **22**, and the claimed set is exactly the
named population — zero documents outside it. Sole claimant on **8**, exactly
the family. Publishes on **5**, declines on **17**. Scanned claimed **0** of
165; Canadian claimed **0** of 672 (605 by printed token, 561 by attributed
parser). Ambiguous at HEAD **0**, ambiguous with the registration removed
**0**. Every §GL7 figure reproduced to the unit.

**What the refusal audit proves.** On the three declined documents, no gate
rejects: the partition identity closes to the cent, both directions' counts and
totals match the extracted rows, and the document is refused solely by the
per-day-oracle rule. Each of the three prints a collected grid only, no unified
table, and **0** ledger rows carrying a second figure that could be a running
balance — so nothing in those documents places any row on a day. The refusal is
the ADB doctrine applied, not a convenient decline, and the reason is the
missing evidence class rather than arithmetic. On the one document that prints
both a ledger daily grid and the bank's own average, that printed average
reproduces on **none** of the six bases — with the caveat that one alternate
basis is within 1% while the others are 31%–50% away; §GL3.1 reports six
binary "no"s and does not say that.

**What the collected-grid checks prove.** `_grid` is only ever called on the
ledger-grid section, so no collected cell can reach `stated_daily_balances`;
constructed, a unified document whose only grid is collected publishes with an
empty daily-balance list and keeps its per-row oracle. Across the fourteen
issuer documents that print BOTH grids: **14 of 14** print both, **0** have
identical series, they differ on **2–10** of **16–22** shared days, and the
collected grid carries 1–2 more dated days on **13 of 14** — §GL3.2
reproduced exactly. Neither grid "wins" on those documents: the issuer reader
publishes **0** daily balances across all fourteen and uses the ledger-grid
heading only as a section boundary, so its average is computed from the
reconstructed ledger under `calendar_day_printed_period`. Every one of the five
newly published documents publishes that same basis, with the opening balance
sourced `stated`, currency `USD` and `currency_source` `schema_default`, and
`bank=None`.

**What the sign audit proves.** Over all eight, the summary identity
`BalFwd + Σ(marked +) − Σ(unmarked) = Ending` closes with a residual of 0.00 on
**8 of 8**. A lexical cross-check for the mis-signing classes the brief names —
a credit-, deposit-, interest-, refund-, reversal-, return- or rebate-worded
label carrying no plus, or a debit-, withdrawal-, charge-, fee-, cheque- or
card-worded label carrying one — returns **zero** suspicions on all eight. On
the unified issue the platform marks credit rows with a plus and debit rows
with nothing, 0 minus-marked rows anywhere. An interest-style credit category
printed without its plus declines the document; two categories mis-marked
symmetrically also declines. The family key is furniture as claimed: the
relationship block is absent from exactly **1 of 8**.

**Crash surfaces.** Eighteen adversarial constructions — empty partition table,
a counted category with no amount, two control lines, a plus glued to the next
token, a partition split across lines, a ledger row split across a page
boundary, a two-figure grid cell, a unicode minus, an empty product, an empty
grid, an uncounted category with no recap, and the sign constructions above —
produced **0** exceptions. Every one answered with a published statement or
`None`.

**Cross-branch collision.** Against `train8`'s 77 registrations (its `analysis`
tree materialised from git blobs, with this branch's module dropped in): the
only registration claiming any of the 22 is the issuer-specific one, on its 14.
`core_processor_signed_counts`, `core_processor_activity_summary`,
`core_processor_counted`, `core_processor_daily`, `core_processor_sectioned`
and `fiserv_premier` claim **0** of the 22. Fixture cross-product both ways:
no `train8` registration claims this card's conformance fixture, and this
card's reader claims none of `train8`'s 77 fixtures.

## Privacy re-measurement

Shared instrument, `tools/privacy_scan_branch.py` on `main` at
`.claude/worktrees/mt-lead`, over the 8 + the 14, `--base 10cc722 --ref
wave8-glance`, 2,502 added lines scanned:

| class | printed tokens | distinctive | hits |
|---|---:|---:|---:|
| MONEY | 4,760 | 4,432 | **0** |
| DATES | 311 | 241 | **0** |
| DIGITS | 872 | 872 | **0** |
| WORDS (incl. bigrams) | 2,316 | 1,659 | **22** |

Exit 1, which is the instrument's design on any hit. All 22 are word bigrams
and every one is adjudicable as platform furniture the reader must match or as
the category vocabulary quoted in the module docstring for the express purpose
of saying the sign decision does not use it (finding 7). None is a customer
name, a merchant, a place, an account or a figure. The tip's count is 22, not
the 21 in Ocean's pre-review note.

By my own reading of the fixtures rather than the scan: every money figure,
date, account number, cheque serial, sequence number and page footer in
`tests/test_category_partition.py` and in the new conformance fixture is
invented AWAY from the family — statement dates in a year the archive cannot
contain, and the scan's MONEY/DATES/DIGITS zeros confirm none of them is a
token any of the 22 documents prints. Crucially the category labels are
invented too (Greek-letter placeholders), so a memorised category list could
not pass the suite. The one archive masthead-and-product literal in the new
tests is reused from tracked source that already existed at `10cc722` in four
places including the base conformance fixture, so this branch did not
introduce it. This review file contains no archive-sourced literal: sha
prefixes and magnitudes as classes only.

## Claims I could not verify, and why

* **The archive-wide differential** (§GL8's `moved` 0 / `payload_now_raises` 0
  over the run of record). Finding 1; I was instructed not to run an
  archive-wide sweep. Bounded instead by the probe's complete enumeration of
  the registration's reach and by the 14 byte-identical payloads.
* **The full default suite (5,950 / 36 skipped / 34 deselected)**, **`python
  corpus_gate.py` GREEN** and **the corpus-marked slice (30 passed)**.
  Explicitly out of scope for this review; the three proof rows I could run
  (guard 252, conformance 1,176 + 36 skipped, module 80) reproduce §GL9B
  exactly, which is some evidence the other three were recorded honestly.
* **The detect-budget exoneration** in §GL9B (0.7% over budget under load, then
  green alone; this registration measured at 1.85% of the sweep, rank 12 of
  76). Not re-timed — a timing measurement on a shared box would not have been
  evidence either way.
* **The census's own characterisation** of the family (rank 9, n=8, "verified 6
  of 8"). Out of scope by instruction; the population it names is the one I
  replayed and it is internally consistent with everything I measured.

## The cell's own findings and risks, in substance

**§GL9 findings/questions for Ocean.** (1) The three collected-grid refusals
are the cell's own and are reversible only by a ruling: those documents
reconcile completely and would publish a calendar-day average from the
reconstructed ledger if allowed, but nothing in them places a row on a day;
publishing them as `withheld` instead of `failed` would require suppressing a
printed opening balance to force the withhold, which the cell calls
manufacturing an outcome by hiding evidence and did not build. (2)
`ACCT-SLOT-HASH`, carried with no cell: the issuer reader's account-number
printing is narrower than the general reader's account slot, so the general
reader declines all fourteen at the summary — widening the slot would put it
into contest with a reader that already validates them, so it is named rather
than done. (3) The family is a future currency mover and says so: no document
prints a currency word, code or symbol, the reader proves no institution, so
the schema default stands rather than a jurisdiction default, which doctrine §B
would make an absence inference. (4) `GLANCE-COUNTS` deliberately not taken:
promoting this registration into `count_semantics` would compare the reader's
counts against the rows it gated them on and move `OBSERVER_VERSION` for no
information. (5) The census's ceiling of 6 of 8 was wrong in the honest
direction — the answer is 5, and the reason is the printing, not the harness.

**§GL11 risks carried.** (1) The uncounted-category rule — a movement category
printing no item count and a non-zero amount is read as exactly one posting —
is measured on four documents rather than proven, and is the one place the
reader assumes something about the platform instead of reading it; a printing
where it is not one row is refused at the count gate rather than miscounted.
(2) The partition must be printed on one physical line; a text layer that split
it refuses the document (fail-closed, but a shape assumption rather than a
gate). (3) The sectioned issue's section list is closed, so a printing with a
fourth ledger section would lose those rows and be refused at the count and
total gates — the right failure, but one the wider corpus may well produce.
(4) The three declined documents are a standing invitation to a wrong reader:
they reconcile completely and print a grid that looks like a daily ledger, so
any future widening of this reader, or any second reader for this core, must
re-derive §GL3 or it will publish an average built on collected balances.
(5) The printed form of zero is the one archive-printed token the branch also
prints, because the fixture must carry it to exercise the zero-amount category.

I verified (1) as measured-on-four and correctly fail-closed, and (4) as the
real risk it is — the three declined documents pass every arithmetic gate,
which is precisely why the refusal must be re-derived rather than inherited.
The cell's findings and risks are accurate as written; they are the honest half
of a record whose two errors are in findings 1 and 2 above.

---

Reviewer: independent adversarial review, batch 8 card 6. Nothing outside this
file was modified; no merge, no push, no change to `main` or `train8`.
