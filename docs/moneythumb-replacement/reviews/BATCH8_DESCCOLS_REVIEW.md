# BATCH 8 — DESC-COLUMNS (`wave8-desccols`, tip `376d4de`, base `10cc722`) — adversarial review

Reviewer: independent, did not write this code. The cell is gone; every claim
below is measured rather than asked about. Privacy: no archive-sourced literal
appears here — magnitudes are classes, documents are `content_sha256` prefixes.

## Verdict

**APPROVE WITH FINDINGS — 0 BLOCK, 1 MAJOR, 7 MINOR.**

The central claims hold and I could not break the ones that matter. The
extraction is a re-segmentation and nothing else: over the seven documents
where the card's real movement lives, every page's token multiset is conserved
against the BASE module loaded from its own git blob, and each changed page
differs from base in one or two CONTIGUOUS line regions — the ledger — with
nothing outside it moved. The fallback is input-identical on the hash that
decides the cache key, proved against the base blob rather than against a
monkeypatched rung. The gates fail closed on every adversarial geometry I could
draw except one, and the one exception is text the page genuinely prints on the
row — which is the MAJOR below, because it is unnamed and the card's own oracle
cannot see it.

## The closed file list (`git diff --stat 10cc722..wave8-desccols`)

Nine files, **2,570 insertions, 0 deletions** — verified with `--numstat`; the
branch deletes no line anywhere.

| file | + | − | kind |
|---|---:|---:|---|
| `ocr/native_text.py` | 311 | 0 | production (2 hunks) |
| `corpus_gate.py` | 22 | 0 | production (1 hunk) |
| `tests/test_native_rung_parity.py` | 7 | 0 | test (1 hunk) |
| `tests/test_printed_row_extraction.py` | 631 | 0 | test |
| `tools/desccols_census.py` | 216 | 0 | instrument |
| `tools/desccols_movement.py` | 243 | 0 | instrument |
| `tools/desccols_mutate.py` | 180 | 0 | instrument |
| `tools/desccols_proofs.py` | 299 | 0 | instrument |
| `docs/moneythumb-replacement/W3_TRACKA_LOG.md` | 661 | 0 | record |

The cell's "exactly two production files" is correct. `corpus_gate.py`'s single
hunk is **additive only**: two entries appended to `EXCLUDED_ANALYSIS_CALLERS`,
the dict a sweep test uses to require that every repository caller of the
analysis is classified. No existing entry, no `ANALYSIS_CALL_SITES` row and not
`PRODUCTION_SUPPLIES_SHEETS` itself is touched, and the stated reason is true of both
tools — each passes `sheets=` from the ladder's own page list. An extraction
card touches the gate because the gate is where new analysis callers are
classified, and the instruments are new analysis callers. No production
behaviour of the gate changes.

**Protected modules: untouched.** No `analysis/` module is in the diff — the
financial core, the money grammar, the ADB engine and `analysis/tables.py` are
all at base. The rung writes no amount: nothing in the module parses a number,
`_ROW_MONEY_RE` only CLASSES a cell, and G7 proves the emitted page's token
multiset equals the flattening's. The repair doctrine is not engaged because
nothing is repaired — text is re-segmented in the page's own order.

## The pinned-surface statement

`docs/balance-metrics-audit-results.csv` holds **109** distinct pinned paths
(measured, `csv.DictReader`). Each was resolved through the PRODUCTION ladder
(`ocr.pipeline.parse_statement` → `analyze_markdown`) twice — rung live and rung
disabled, the memoised page read cleared between passes — and the whole payload
compared leaf by leaf, with `telemetry.record.classify_outcome` deciding the
outcome class on each side. `python -m tools.desccols_proofs pinned`, **exit 0,
85s**:

**5 claimed · 104 not claimed · 0 outcome movement · 2 payloads byte-identical ·
3 move exactly one leaf.**

**The leaf on the three is `.metrics.adb.source_posting_days`** — a single
integer under `metrics.adb`, the count of posting days `analysis/dates.py` finds
in the raw text. All five documents go `validated → validated`.

**It is gated by nothing.** The corpus gate's pinned verdict is
`corpus_gate._Verdict` = outcome class + flags + notes + risk level +
`possible_document_issue` (`corpus_gate.py:202-214`); `source_posting_days` is
not among them. The gate reads exactly two audit CSVs (`corpus_gate.py:98-99`),
and **both contain the strings `description` and `source_posting_days` zero
times**, as does `tests/data/parser_expectations.json` (measured, all three
files). It is read by no required ADB check either — see F2 for the coupling
that makes that a measurement rather than a property.

**The reach over the 109 is a detection measurement, not an assertion**: the
other 104 are `not_claimed` because `native_statement` returns a model other
than `native-pdf-text+printed-rows` for them, counted by the instrument
document by document. **And the two independent measurements meet**: I computed
the five pinned documents' content hashes directly and all five are inside the
archive run's claimed 76, including `8DC5B0D3…`, which DC5 names as one of the
two `us_bank` single-leaf movers — the pinned-side and archive-side counts agree
without either knowing about the other.

## The required-check vector over the 76

`python -m tools.desccols_movement` over the run of record's 3,380 documents at
this tip, **exit 1** (by design — it exits 1 on any movement), **2,210.2s**. Every
headline in DC6 reproduces to the document:

| | claimed | reproduced |
|---|---:|---:|
| documents | 3,380 | **3,380** |
| ladder answers None (no native text) | 192 | **192** |
| ladder unchanged — the rung declines | 3,112 | **3,112** |
| …of those, byte-identical to the archive's own artifact | 3,096 | **3,096** |
| claimed by the rung | 76 | **76** |
| moved | 21 | **21** |
| description leaves lengthened / replaced / shortened | 177 / 39 / 0 | **177 / 39 / 0** |
| `payload_now_raises` | 0 | **0** |
| claimed but text unchanged | — | **0** |

The 76 by parser, from the run's own rows, also reproduces exactly: 37 with no
parser, 12 `regions`, 7 `core_processor_counted`, 6 `bank_of_america`, 5
`chase`, 3 `symitar`, 3 `us_bank`, 1 each `banco_popular` / `community_section`
/ `first_community`. **All 76 are `digital` at intake and all 76 read
`native-pdf-text` in the run of record** — measured, not inferred from where the
call sits — and **none is in a Canadian-labelled folder**, so no currency or
provenance surface is near this card. Of the 39 with a stored payload, **21 move
and 18 are byte-identical**; of the 21, **7 are the `core_processor_counted`
documents** (the exact seven the record names) **and 14 move exactly one leaf,
the same leaf on all fourteen**.

**The vector itself.** The instrument masks `description` leaves and diffs
everything else, so the whole check surface is inside the comparison. Over all
21 movers, **only four top-level payload keys move at all**: `statement`,
`classifications`, `detection`, `metrics`. Inside `statement` the ONLY moving
leaves are `transactions[].classification.*` — not one amount, date, direction,
running balance, period, account, currency or total. And the decisive query,
over the union of every moved leaf path on all 21:

> **checks, integrity flags, notes, risk level, `possible_document_issue`,
> warnings, outcome, reconciliation, escalation, `model_used`,
> `parsed_posting_days`, `missing_posting_dates`,
> `posting_dates_cover_source`, and every ADB VALUE: `NONE` moved.**

The only `.metrics.adb.*` leaf that moves anywhere is
`.metrics.adb.source_posting_days`, and it moves on exactly 21 documents — the
7 plus the 14. **So "0 verdict movement among the 76" holds on the
required-check vector and not merely on the outcome class.** All 39 comparable
documents are `validated` before and after; the other 37 stored no payload (see
the boundary re-ask below).

## Re-run table

Every command run from the worktree root at tip `376d4de`; exit codes verbatim.

| instrument | result | exit | seconds |
|---|---|---:|---:|
| `pytest -q` on the branch's three extraction test files | **54 passed** | **0** | 11 |
| `python tools/desccols_mutate.py .` | **10 applied, 9 killed, 1 named expected survivor**, restored, tree clean | **0** | 72 |
| reviewer's extra mutants (`extra_mutants.py`, 6 clauses the harness omits) | 4 killed, **2 SURVIVED** (F1) | **0** | 48 |
| canonical guard set (5 files) + `tests/test_repair_guard.py` | **267 passed** | **0** | 22 |
| `python -m tools.desccols_movement` over all 3,380 | 76 claimed · 3,112 declined (3,096 byte-identical to the archive's artifact) · 21 moved (7 + 14) · 177/39/**0** · **0** now-raises | **1** (by design) | 2,210 |
| reviewer's fallback vs the BASE GIT BLOB, stride 23 | 147 sampled · 5 claimed · **132 pages AND `analysis_input_sha` identical · 0 different** · 10 no native text | **0** | 139 |
| the same, stride 71 | 48 sampled · 4 claimed · **43 identical · 0 different** · 1 no native text | **0** | 43 |
| reviewer's change-shape check on the 7 (base blob vs branch) | 25 pages · 16 changed · **18 contiguous change regions, worst page 2** · tokens conserved on every page | **0** | 3 |
| `python -m tools.desccols_proofs pinned` | **5 claimed / 104 not claimed / 0 outcome movement / 3 leaves, all `metrics.adb.source_posting_days`** | **0** | 85 |
| `python -m tools.desccols_proofs oracle` | 269 rows, paired 1:1, **252 exact / 17 prefix / 0 FOREIGN**, 0 unpaired | **0** | 189 |
| the same `--shipped` (the before half) | 269 rows, **75 exact / 194 prefix / 0 FOREIGN** | **0** | 213 |
| reviewer's publish/refuse boundary on the 37 no-payload claimed documents | **37 still refuse, 0 now publish** | **0** | 31 |
| `python -m tools.descattrib_movement` over the complex's 31 (stored-text control) | **0 moved descriptions, 0 movement elsewhere on all 31** | **0** | 40 |
| `python -m tools.desccols_census --start 0 --end 120` | 113 native-text · **111 welded** · 2 clean · 84 amount-welded | **0** | 30 |
| privacy: shared instrument, the complex's 31 | **0 hits** over 5,910 distinctive tokens | **0** | 4 |
| privacy: shared instrument, the 5 pinned | **0 hits** over 3,003 distinctive tokens | **0** | 4 |
| privacy: shared instrument, the claimed 76 + the 5 pinned | 8 whole-token collisions, **0 document-derived** (adjudicated below) | **1** | 4 |
| reviewer's exception-surface probe (malformed `get_text("dict")`) | 3 of 6 shapes **RAISE** rather than refuse (F8) | **0** | 4 |
| reviewer's adversarial geometries (11 pages) | every one refuses or follows the ink, except F3 | **0** | 6 |
| reviewer's band-chaining probe | no chaining; a tall line joins one row only | **0** | 2 |

After every harness run `git status --porcelain` was clean apart from this
review file (checked after the two mutation runs specifically, since both
rewrite `ocr/native_text.py` in place).

## What I attacked, and what survived

Every adversarial page below was drawn by me with PyMuPDF at coordinates chosen
here; every merchant, date and figure in them is invented. The script is
`scratchpad/dcrev/adversarial.py` (reviewer scratch, uncommitted by design).

| geometry | the rung's answer |
|---|---|
| two accounts printed side by side, each with its own date/label/detail/amount column | **REFUSED** — a row's first money is not its last cell (G8) |
| detail column offset −0.7 / −3.0 from its grid row (the ordinary case) | claimed, each row carries its own detail |
| detail column offset −6.0 — the box straddles two rows | **REFUSED** — the detail becomes its own band, lands after the row's money, G8 fires |
| detail column offset −8.5 — the ink has moved onto the row above | claimed; the emitted rows follow the INK, which is the contract |
| page rotation 90 / 180 / 270 | claimed, identical rows to the unrotated page |
| superscript / footnote marks in the money gutter | claimed; marks stay on their own row, inside the span |
| an image block on an otherwise repairable page | claimed; tokens conserved |
| a table whose cells are individually boxed and never weld | left alone (G5) — committed pin, reproduced |
| a page with no line boxes | not claimed |
| money right edges disagreeing by 25–80pt | left alone (the second half of G3 — see F1) |
| a band narrowed to 1.2pt by a tiny glyph, with the next row 0.5pt away | the next row does **not** chain in — narrowing moves the intersection UP as well as shrinking it |
| one tall line box spanning two ordinary rows | joins the first row only; the band's extent narrows to the lines already in it |

**Token integrity.** Tokens are never split or merged (cells are joined with a
single space and a line's text is emitted whole), never invented or dropped
(G7 is a multiset equality on the emitted page), and are reordered only within
a printed row, in printed reading order. On the seven documents where this
card's movement lives, measured against the BASE module loaded from git blob
`10cc722` in one process: 25 pages, 16 changed, **18 contiguous change regions
in total, worst page 2**, token multiset conserved on every page. The change is
the ledger and nothing else — this is the strongest single answer to "does it
only re-segment".

**The `91A2DE99` restoration is geometry, not vocabulary.** `analysis/tables.py`
is not in the diff, so the classifier path is DESC-ATTRIB's count-based
attribution unchanged; what changed is that a repaired row's whole printed
description now sits on the row's own line, so the rule's own "the span up to
its first newline is the row's label" clause publishes it with no flush to
bound. Scored against §DESCATTRIB's committed WORD-box oracle — a different
extraction from the line boxes this rung reads — the published descriptions on
that document are **56 rows, 55 exact / 1 prefix / 0 FOREIGN**; over all eight
`core_processor_counted` documents **269 rows, 252 exact / 17 prefix / 0
FOREIGN, 0 unpaired** against the shipped tree's **75 / 194 / 0**. Both halves
reproduced exactly (below). 1:1 pairing on (section, date, amount) with none
refused is also the proof that no row was split, merged, added or dropped.

**Cache correctness.** `OCR_STAGE_VERSION` is **3** on this branch
(`webapp/artifact_cache.py:286`); the documented rule at `:275` is "bump when
the OCR ladder's output changes for unchanged settings", and for the claimed
documents it does. DC8 and DC9-1 state the 3 → 4 bump is owed and Ocean's at
merge, and nothing on the branch pretends otherwise. **The `ocr_settings_key`
does NOT need a rung flag.** The batch-6 precedent that put a value in a
settings key is for DATA (`parser_registry`'s fingerprint) or an ENVIRONMENT
SWITCH (`generic_structurer`); this rung is unconditional code with neither, and
the exact precedent is GEOM-1's v2 → v3 bump for `parse_native_woodforest`,
which is the same shape one rung over. The stage version is the right
instrument; see F6 for what is still unenforced.

## Numbered findings

### F1 — MINOR — two gate clauses are unpinned: no test fails when they are deleted

**Claim under review.** DC7: "a MUTATION TABLE for every gate you add or touch",
ten mutants applied, nine killed, one named survivor.

**Evidence.** I re-ran the committed harness (`python tools/desccols_mutate.py
.`, exit 0, 72s, tree clean) — 10 applied, 9 killed, M5 the named expected
survivor, reproduced. I then applied six mutants the committed harness does not
contain, same protocol (pristine copy, one patch at a time, restored in a
`finally`, no `-x`; `scratchpad/dcrev/extra_mutants.py`, exit 0, 48s, baseline
green, tree clean afterwards). Four were killed. **Two SURVIVED with zero test
failures:**

* **X1** — delete the money right-edge agreement clause of G3
  (`ocr/native_text.py`, the `common = max(edges, …)` / `if sum(…) <
  _ROW_GRID_MINIMUM: return None  # G3` pair). G3 is one row in DC2's table but
  two independent checks in the code, and only the FLOOR half is mutated (M4).
  The clause is live — a hand-built region whose three money right edges
  disagree by 25–80pt is left alone, and the same region with the edges agreeing
  is repaired — so this is a missing pin, not a dead gate.
* **X5** — broaden `_ROW_MONEY_RE` to any run of digits. That regex decides
  which cells are money, and therefore decides both G3 and G8. No fixture
  distinguishes a printed money cell from a bare figure.

**Required closure.** Add a fixture whose ledger has ragged money right edges
and one whose right-hand column is a non-money digit run, and add both mutants
to `tools/desccols_mutate.py` so the kill table covers every clause rather than
every table row.

### F2 — MINOR — `source_posting_days` is not a diagnostic; it shares its source set with a REQUIRED check

**Claim under review.** DC4.1: "It is a diagnostic that became accurate";
DC9-4: "It moves no ADB value, no check, no warning and no verdict".

**Evidence.** `analysis/adb.py:731-741` computes `source_dates` ONCE and uses it
for both `result.source_posting_days = len(source_dates)` (`:738`) and
`checks["posting_dates_cover_source"] = not missing` where `missing =
source_dates - parsed_dates` (`:739-741`). `:774-775` appends
`posting_dates_cover_source` to `required` and `:776` folds `required` into
`result.ok`. So the leaf this card moves on 14 documents is not a diagnostic
sitting beside a check — it is the SIZE of the set the check is computed from,
and it moves UP. A document where the repair reveals a printed posting date the
parser produces no transaction for moves a REQUIRED check from True to False and
withholds the ADB. The archive measurement is zero (below), and the outcome is
correct on this archive; the record's characterisation is what is wrong.

**Required closure.** DC4.1 and DC9-4 should name the coupling and state the
measurement as "the source set grew and `missing` stayed empty on all N", so the
next extraction card knows which leaf to watch rather than believing this one is
inert.

### F3 — MAJOR — a repaired row absorbs any same-band line left of the money column, and the card's own oracle cannot see it

**Claim under review.** DC2: "a row's description is its own by construction";
DC3.1: the WORD-box oracle scores 0 FOREIGN, which is offered as what settles
the question; DC9-3 names the only furniture risk as furniture forming its OWN
region, whose "worst case is a furniture block emitted as rows in the same place
with the same words".

**Evidence.** `scratchpad/dcrev/furniture_in_band.py`, exit 0. On the fixture
family's own welded ledger I printed one extra line — page furniture, not part
of the ledger — on the same BAND as one posting, left of the money column. The
rung claims the page and the line is folded into that row, landing between the
row's date and its amount; run through `tables.dated_cells` +
`tables.attributed_descriptions` (the two functions both core-processor readers
call), that row's PUBLISHED description now carries the furniture text, where at
base it carried none. The same note printed to the RIGHT of the money column is
fail-closed (G8 refuses the whole region), so the exposure is one-sided and
narrow — but it is real, and it is on the exact axis this card exists to
control: what reaches a description.

**The blind spot is the second half of the finding.** §DESCATTRIB's oracle reads
a row's "true description" from the words printed between that row's date and
its amount, so an absorbed same-band line is part of the truth it compares
against. DC3.1's 0 FOREIGN therefore cannot distinguish this case from a clean
one, and DC3.1 is the measurement the record leans on. I could not settle it on
the archive without printing document text, which the privacy rule forbids; what
I could measure is that the shape is not exotic — over the 270 repaired rows on
the seven counted documents, **115 rows draw cells from three or more distinct
MuPDF blocks** and 137 from exactly two (`scratchpad/dcrev/absorption_census.py`,
exit 0), so a third contributor to a row is the common case rather than the
strange one.

This is a MAJOR rather than a BLOCK because the emitted text IS what the page
prints on that row, which is the platform's stated contract, and because
DC3.1/DC4 show no wrong answer on this archive. It is a MAJOR rather than a
MINOR because the record asserts a property ("its own by construction") that the
code does not have and the headline proof cannot test.

**Required closure.** (a) Name the case in DC9 as a residual reach: a repaired
row absorbs every line on its band left of the money cell. (b) Add a fixture
pinning the behaviour, so the next editor knows it is intended rather than
latent. (c) Either state a measurement that separates same-band non-description
cells on the seven — e.g. per moved description leaf, whether every contributing
line's block also contributes to another row of the region — or record plainly
that the oracle cannot see this class and the case is unmeasured on the archive.

### F4 — MINOR — DC8.1's hunk table does not describe this branch

**Claim under review.** DC8.1: "1,598 insertions, 0 deletions, 8 hunks, 7 files
(this log aside)", with a per-file table.

**Evidence.** `git diff --numstat 10cc722..wave8-desccols`, log aside: **8 files,
1,909 insertions, 0 deletions**. `tools/desccols_proofs.py` (299 lines) has no
row in the table at all; `corpus_gate.py` is listed at +11 against an actual +22
(the second classification entry landed in the same hunk);
`tests/test_native_rung_parity.py` at +6 against +7. The arithmetic closes
exactly — 1,598 + 299 + 11 + 1 = 1,909 — so the table is the pre-`7b2e7c0`
state left unrestated. In the same class, DC7's kill table records M1 as failing
**2** tests; the harness at this tree reports **3** (it also kills
`test_a_multi_column_balance_ladder_is_left_alone` and
`test_a_row_with_several_money_cells_can_never_pass_the_amount_last_gate`).

And DC11's commit table lists **8** of the branch's **34** commits, omitting —
among 25 others — `d7186e3`, which changes PRODUCTION code (the second MuPDF
handle the rung opens, closed in a `finally`). All three are the same defect: a
table written once and never restated as the branch moved.

**Required closure.** Restate DC8.1 from `git diff --numstat` at the reviewed
tip, correct the M1 row, and either complete DC11 or say it lists the
substantive commits only and name `d7186e3` among them. The 0-deletions claim,
the two-production-file claim and every other number in these sections that I
checked are correct.

### F5 — MINOR — the gate numbering does not agree with itself, which breaks gate→pin traceability

**Claim under review.** The wave rule "a test named after a gate is not a test of
that gate" makes the gate label a load-bearing part of a pin.

**Evidence.** The module and DC2's table define **G1–G8**. DC2's own heading
says "the nine gates that decide where". Three pins in
`tests/test_printed_row_extraction.py` still carry the pre-deletion numbering:
`test_a_template_printing_the_amount_above_its_detail_is_declined` documents
itself as **G9** (the module's G8), `test_a_block_straddling_the_ledger_
boundary_refuses_the_whole_document` as **G7** (G6), and
`test_a_token_the_flattening_saw_and_the_boxes_did_not_refuses_the_page` as
**G8** (G7). All three pins are correct and kill their mutants; only the labels
are wrong, and they are wrong in the direction that makes a future reader think a
gate is pinned when a different one is.

**Required closure.** Renumber the three docstrings and the DC2 heading.

### F6 — MINOR — the owed `OCR_STAGE_VERSION` bump is correctly named and completely unenforceable from the branch

**Claim under review.** DC8 / DC9-1: the 3 → 4 bump is owed and is Ocean's at
merge.

**Evidence.** `OCR_STAGE_VERSION = 3` at `webapp/artifact_cache.py:286` on this
branch; the rule at `:275`; the GEOM-1 v2 → v3 precedent in the same comment
block is this exact shape. Nothing on the branch — no test, no guard, no gate —
fails if the bump is not made, and the failure mode is silent: the claimed
documents' cached OCR artifacts would keep serving pre-change text indefinitely,
so the card's whole movement would be invisible on a warm archive rather than
wrong-looking. The record is honest about this and does not pretend otherwise;
the finding is the unenforceability, not the disclosure.

**Required closure.** Ocean bumps `OCR_STAGE_VERSION` 3 → 4 in the merge commit.
This is the single highest-consequence open item on the branch.

### F7 — MINOR — the owed archive sweep covers 2,000 of 3,380 documents and the record does not say so plainly

**Claim under review.** DC8's sweep table, and the wave's proof floor ("the full
sweep is owed once per card at its final production tree").

**Evidence.** DC8 tabulates two chunks of 1,000 with zeros, then writes "The
remaining three chunks were relaunched after a sibling cell's process sweep
killed this cell's driver mid-run" and reports no result for them. No row, no
exit code, no seconds. A reader who stops at the table's "the counts add" reads
completion; what happened is 59% coverage. The substance is not in doubt — I
reproduced the structural argument myself: importing `analysis.pipeline` plus the
whole registry leaves **zero** `ocr` or `webapp` modules in `sys.modules`
(measured, `[]`, registry 75), so the stage the sweep recomputes cannot reach
either changed file; and I reproduced the demonstration one population deeper —
`python -m tools.descattrib_movement` over the complex's 31 at this tip reports
**0 moved descriptions and no movement elsewhere on all 31**, including
`FC385FC2…`, one of the seven documents where this card's movement is largest
(exit 0, 40s). The instrument that DOES exercise the changed code ran over all
3,380 (below).

**Required closure.** State the sweep coverage as 2,000 of 3,380 with the three
chunks unreported, or finish them. Either is fine; leaving "relaunched" to imply
completion is not.

### F8 — MINOR — a malformed line box RAISES out of the rung instead of refusing it

**Claim under review.** The wave rule the card binds the cell to: "Fail-closed
everywhere: a refusal is an answer and an exception is not (close every
`ValueError` / `TypeError` path a mangled token can reach)". The module's own
design statement is that a region failing any gate "is left exactly as the
flattening left it".

**Evidence.** `scratchpad/dcrev/exception_surface.py`, exit 0. Feeding
`_page_text(page, "dict")` a dict whose line boxes are malformed, on the fixture
family's own repairable page:

| shape | rung's answer |
|---|---|
| a line with no `bbox` key | **RAISED `KeyError: 'bbox'`** |
| a `bbox` of three numbers | **RAISED `ValueError: not enough values to unpack`** |
| a `bbox` of strings | **RAISED `TypeError: unsupported operand type(s) for -`** |
| a `bbox` of `None`s | REFUSED |
| no `blocks` key at all | REFUSED |
| a line with no `spans` | REFUSED |

`ocr/native_text.py::_printed_lines` does `x0, y0, x1, y1 = line["bbox"]`
unguarded, and `parse_native_printed_rows` catches only `_UnreadableTextLayer`,
so any of the three escapes `native_statement` and therefore
`ocr/pipeline.py::parse_statement` — the OCR stage crashes for that document
rather than falling through to the generic rung. Empty bytes, a non-PDF and a
truncated PDF are all handled correctly (`None` each).

**Two things bound this, and neither dissolves it.** (a) The pattern is
pre-existing: base's `_fc_bands` reads `line["bbox"]` the same way. But that rung
runs only on documents its own detection claims, while THIS one calls
`get_text("dict")` on **every native-text document in the archive** — the
exposure is 3,189 documents wide instead of a family. (b) It is not reachable on
today's PyMuPDF: the archive run exercised the path on all 3,189 and reported
**0 `payload_now_raises` and no crash**. DC9-8 says a future MuPDF "cannot
change what is emitted for a claimed one"; it can, however, change whether the
rung raises, and that is the case the fail-closed rule exists for.

**Required closure.** Wrap `_printed_lines` (or the page loop that calls it) so a
malformed line box refuses the document the way `_UnreadableTextLayer` does —
three lines — and add one pin driving it.

## Privacy re-measurement

The shared instrument on `main`
(`.claude/worktrees/mt-lead/tools/privacy_scan_branch.py`), `--base 10cc722
--ref wave8-desccols`, over the branch's 2,570 added lines:

| population | documents | distinctive tokens scanned | hits | exit |
|---|---:|---|---:|---:|
| the core-processor complex (`--where parser_id=core_processor_counted,core_processor_sectioned,core_processor_daily`) | 31 | 1,922 MONEY · 1,025 DIGITS · 2,932 WORDS · 31 DATES | **0** | 0 |
| the five pinned documents the rung claims (`--shas`) | 5 | 610 MONEY · 320 DIGITS · 2,060 WORDS · 13 DATES | **0** | 0 |
| the 76 documents the rung claims + the 5 pinned (`--shas`) | 76 | 11,730 MONEY · 6,043 DIGITS · 17,749 WORDS · 240 DATES | **8** | 1 |

**The eight, adjudicated one at a time — none is document-derived.** Four are
MONEY and four are WORDS; zero DIGITS, zero DATES, and so zero accounts, zero
references and zero statement dates. Two of the MONEY hits are *elapsed seconds*
in DC10's own proof table (a suite runtime and a test-file runtime, printed with
two decimals, which the instrument's money pattern cannot tell from a figure).
Two more MONEY hits and two WORDS hits are the SAME two tokens in the fixture
family — one round three-digit amount and one common English noun used as an
invented merchant's first word — each appearing on the fixture's row-definition
line and again on the line that asserts what that row must print. The last WORDS
hit is a two-word sequence of ordinary English out of the log's own prose. A
fixture cannot be built whose every token is absent from three thousand
statements; what matters is that nothing distinctive collided, and nothing did.

**Why the cell did not run this instrument.** `tools/privacy_scan_branch.py`
does not exist at `10cc722` — it landed on `main` after this branch's base — so
the cell ran the bespoke scan the card asks for instead (DC10: 4,276 printed
tokens, 12 whole-token collisions, 0 document-specific), which is the same
adjudication I reach on a population eighteen times larger. **Worth recording
for the train:** once this branch sits on a tree that carries the shared
instrument, running it over the claimed 76 exits **1**, and the eight collisions
above are the reason. Someone should write that adjudication down so it is not
re-litigated at every later scan.

**My own eyes, beyond the instrument.** I grepped every ADDED line of the branch
for money-with-cents, digit runs of six or more, and fully-qualified dates. The
only matches are (a) `content_sha256` values, which the card requires, and (b)
four pinned-manifest FILE PATHS whose names contain a statement month — and all
four already occur in tracked files at `10cc722` (2–3 files each, measured), so
this branch introduces none of them. The fixtures in
`tests/test_printed_row_extraction.py` are drawn at coordinates chosen in the
file with invented merchants, dates and figures; the tools print only counts,
classes, lengths, leaf paths and hashes, which I confirmed by reading their
output paths rather than by trusting their docstrings. §DC3.3 is stated in
classes and rounded deltas after Ocean's `376d4de`; I found nothing else in the
branch that quotes a document's figure, date, name or account number.

## Claims I could not verify, and why

* **The full 3,380-document census** (3,189 native-text / 3,156 welded / 2,419
  amount-welded / 33 clean, 701.7s). I ran a 120-document slice instead: 113
  with native text, **111 welded, 2 clean, 84 amount-welded**, exit 0, 30.4s —
  98.2% welded against the full census's 99.0%, i.e. the proportion reproduces.
  The full run is 700s of a saturated host and DC10 carries a committed
  600-document chunk row for the same purpose.
* **The two `regfp_zero_movement_sweep` chunk reports.** Their JSON goes to a
  private out path and is not committed, so the two zero rows in DC8 are
  unre-derivable by construction. See F7; the structural argument that makes
  them uninformative I did reproduce.
* **DC9-2's +35% cost A/B and DC10.1's timing A/B.** Both are host-dependent
  wall-clock measurements taken on a machine running twenty-plus sibling
  processes; re-running them on a differently-loaded host measures a different
  thing, not the same thing again.
* **The full default suite (5,881 passed) and `python corpus_gate.py` GREEN.**
  Out of scope for this review by instruction; I ran the branch's own test files,
  the canonical guard set and the repair guard instead.
* **DC3.2's per-document detection deltas** (entities and evidence rows gained).
  Establishing them requires reading published descriptions and detections
  document by document, which the privacy rule forbids me to reproduce here. The
  substance is covered by the oracle score, which I did reproduce on both halves
  and which is the stronger statement: no published description on any of the
  269 rows contains text the statement printed for a different posting.
* **The 483-document `--stride 7` fallback row.** I reproduced the `--stride 23`
  row exactly and ran my own base-blob comparison at two strides instead.

## DC8 and DC9, in substance

**DC8 — what this card owes the train.** One thing, and it is not optional: an
`OCR_STAGE_VERSION` bump **3 → 4** at merge, because the OCR ladder's output
changes for unchanged settings on the documents the rung claims and the OCR
settings key carries the stage version, not the text — so without the bump those
documents are served their pre-change text out of the cache indefinitely. DC8
also states, correctly, that the wave's own archive sweep is STRUCTURALLY BLIND
to this card: `tools.regfp_zero_movement_sweep` recomputes analysis from the
STORED OCR artifact text, and this branch changes the stage that PRODUCES that
text, so the sweep can only ever report zero. `tools/desccols_movement.py` is
committed as the instrument that does exercise the changed code. I reproduced
both halves of the blindness argument independently (F7).

**DC9 — the risks the cell names.** Eight, and they are the right eight: (1) the
owed bump; (2) the rung reads `get_text("dict")` on every native-text document,
measured at +35% / +0.34s per document on a cold OCR pass, ~+1,160s over the
archive, nothing on a warm one; (3) the repair is found by ink, so a page whose
furniture satisfied every gate would be re-serialised — bounded by G7 to the
same words in the same place, not reachable on this archive as measured; (4)
`metrics.adb.source_posting_days` moves, presented as an inert diagnostic (see
F2, where it is not inert); (5) five PINNED documents' analysis INPUT rotates —
cache-key movement on the truth set, not truth-set movement, with verdicts and
integrity blocks unmoved; (6) `source_model` relabels to
`native-pdf-text+printed-rows` for every claimed document in discovery rows and
telemetry, pinned nowhere; (7) the straddle gate is redundant with token
conservation, kept for a fast legible refusal and measured as a named surviving
mutant rather than assumed; (8) the rung is bounded by what MuPDF groups into a
block, so a future MuPDF changes WHICH documents are claimed but cannot change
what is emitted for a claimed one, because emission reads only boxes and text
and G7 checks the result. Risk 3 is the one that is incomplete — see F3.
