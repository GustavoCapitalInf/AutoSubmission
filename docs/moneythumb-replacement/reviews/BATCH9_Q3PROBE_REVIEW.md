# BATCH 9 — adversarial review of `wave9-q3probe` (card `Q3-CORROBORATION-PROBE`)

**CONFIRMED — N = 6.** All 42 cells of the 6 × 7 table reproduce under an
independent reader written for this review; 42 / 42 agreement, 0 disagreements,
0 sections lowered. S4's Q3-eligible population is **2 + 6 = 8** (the maximum,
reached by measurement and not by rounding).

Reviewer: independent adversarial cell. Branch `wave9-q3probe`, base `train9`
`e5b0342`, code tip `65041bf`. Everything below was re-measured from the OCR-v4
artifacts in `.claude/recovery/webapp_data_train8_cold` (run of record
`cda8882d` / `7185633`). Nothing in production was touched, and this review adds
one file and one commit.

Five findings, all MINOR, none blocking; they are scope caveats for L1-S4 and
for Phase 2, not defects in the measurement. The most consequential is
**MINOR-1**: the six documents were extracted by the PDF's own text layer and
never by an OCR, so the witness has been measured but has not yet been exercised
against the failure mode the class exists to bound.

---

## 1. What I did NOT take from the cell

The card's contract is that a claim not reproduced is a claim not confirmed, so
for conditions 1–7 I wrote my own reader (`myreader.py`, scratch, not committed)
which imports **nothing** from `tools/q3_corroboration_probe.py` and nothing from
`tools/l1_split_prototype.py` or `tools/l1_structure_census.py` except the
cold-cache loader and the census loader, both pure I/O. My own patterns, my own
section-span rule, my own roll-up location, my own column-role reading. Every
figure comparison in my reader is done on an exact **cents string**; my reader
never constructs a float.

Where I re-ran the cell's own instrument it was to confirm the cell's numbers,
never to decide a cell.

## 2. Population reproduction — the design's instruments, at the base

`tools/l1_design_idle_evidence.py` at this base, over the split prototype's own
`_population`:

| measure | the design's instrument | the cell's claim |
|---|---:|---:|
| documents reconstructed | 214 | — |
| trivially idle sections in the whole population | 21 | — |
| … on documents `all_close_allowing_idle` admits | **6** | 6 |
| … the documents themselves | **6** | 6 |
| census groups spanned | **1** | 1 |

The six sha16s the instrument emits are exactly the cell's six. I then read
`measured_population` in the probe line by line against
`l1_design_idle_evidence`'s own filter: both are `section.refusal == IDLE` over
`run_document`, restricted to documents whose `all_close_allowing_idle` holds,
over the same `_population`. **The probe applies no additional filter** — no
census group is named, no document is named, no size or shape condition is
applied. `--expect-sections 6` did not fire, and I confirmed separately that it
is a live STOP rather than a decoration (§7).

That 21 idle sections exist and only 6 survive the document-level condition is
worth recording: the design instrument reports 3 of the 21 print a dated row
somewhere in the section, so condition 4 is a condition that discriminates in
this population rather than one every idle section passes for free.

## 3. The 6 × 7 table — cell's cell vs mine, all 42

`P` = PASS. My verdict is on the left of each pair, the cell's on the right;
**every pair agrees**.

| # | document | C1 | C2 | C3 | C4 | C5 | C6 | C7 | all seven |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | `333E226A75FE5441` | P/P | P/P | P/P | P/P | P/P | P/P | P/P | **YES** |
| 2 | `472A0966A5204513` | P/P | P/P | P/P | P/P | P/P | P/P | P/P | **YES** |
| 3 | `596804AA1ACD01EB` | P/P | P/P | P/P | P/P | P/P | P/P | P/P | **YES** |
| 4 | `C3D3E48F1E14AE2A` | P/P | P/P | P/P | P/P | P/P | P/P | P/P | **YES** |
| 5 | `F5BC9FB6D084559E` | P/P | P/P | P/P | P/P | P/P | P/P | P/P | **YES** |
| 6 | `FFAC0A88768A8A59` | P/P | P/P | P/P | P/P | P/P | P/P | P/P | **YES** |

**42 cells · 42 agreements · 0 disagreements · 0 UNDECIDABLE.**

My reader also independently reproduces every LOCATION the cell cites — not
merely the verdict:

| document | section opens | own opening | own closing | roll-up row | roll-up caption |
|---|---|---|---|---|---|
| `333E226A75FE5441` | p1 l16 | p1 l16 | p1 l18 | p1 l14 | p1 l13 |
| `472A0966A5204513` | p1 l16 | p1 l16 | p1 l18 | p1 l14 | p1 l13 |
| `596804AA1ACD01EB` | p1 l17 | p1 l17 | p1 l20 | p1 l15 | p1 l14 |
| `C3D3E48F1E14AE2A` | p1 l16 | p1 l16 | p1 l18 | p1 l14 | p1 l13 |
| `F5BC9FB6D084559E` | p1 l16 | p1 l16 | p1 l18 | p1 l14 | p1 l13 |
| `FFAC0A88768A8A59` | p1 l16 | p1 l16 | p1 l18 | p1 l14 | p1 l13 |

The roll-up row sits **two lines above** the section's own opening caption on all
six, and two to four lines above its closing. The cell's independence claim is
therefore a location fact and I reproduce it.

### 3.1 The specific attacks the review brief named

**C4 — "does the cell's span exclude a trailing region where a row could hide?"**
This was the attack most likely to break the result, so I did not test the span;
I tested the ACCOUNT. My reader attributes **every line of the document** to the
account whose printed heading last precedes it, reprinted page headings included,
and then asks the question over that attributed set rather than over a window.
Result on all six: the idle account's attributed set **is** its contiguous span —
3 lines on five documents, 4 on `596804AA1ACD01EB` — and contains 0 dated rows.

The reason is decisive and I measured it directly: **the idle account's printed
label and its printed identity token each occur on exactly TWO lines of the
entire document** — its roll-up row and its section heading — on all six. The
sibling account's heading is reprinted at every page break; the idle account's
never is. There is no later block, no continuation and no trailing region in
which a row of that account could sit. The span is not a window that might have
been drawn too small; it is the whole of what the paper prints about that
account.

**C5 / C6 — "measured over the whole section span or just near the captions?"**
Both the cell's readers and mine run over the whole span, and mine additionally
over the whole attributed set. 0 counts, 0 totals, 0 daily-balance captions with
rows, on all six, by both measures. I widened my counts pattern beyond the
cell's (`number of …`, `… items`) and it still finds nothing.

**C7 — "is the roll-up row genuinely located by the section's LABEL, is the
`close` role from the printed caption vocabulary, and does the figure match to
the cent as strings?"** Three separate answers.

*The link.* The cell's probe establishes it structurally — the boundary is
`rollup-oracle`, so `section.identity_index` is a row index by construction. That
is a real link but it is the design's, not an independent one, so I built the
link the other way: I matched the product label AND the identity token printed on
the section heading against the label and token printed on the roll-up row. **Both
routes name the same row on all six** (§3.2). The link is printed, not inferred.

*The role.* All six print the column caption class `type_prev_dep_wd_end` from
L1-C5's closed vocabulary, naming four columns. My reader parses the caption line
itself and takes the closing from the column the caption identifies as the ending
one — the 4th of 4 — never from a position chosen by me. Same column, same
figure, both readers. The case the ruling's wording turns on — a closing printed
under a column whose role is not identifiable — occurs **0 / 6**, which I confirm.

*The comparison.* The cell compares floats within a cent. I compared exact cents
STRINGS for equality. Same answer on all six, so the float tolerance is not
carrying the result.

**"What happens on a document where two sections share a label prefix?"** No
roll-up label on any of the six is a prefix of another, and the labels and the
suffix tokens are pairwise distinct on all six. The hazard is real but does not
occur in this population; see MINOR-3 and MINOR-4 for what I found when I pressed
on it anyway.

### 3.2 The section↔row link, by two independent routes

| document | design route: section start | my route | design route: row line | my route | agree |
|---|---:|---:|---:|---:|---|
| `333E226A75FE5441` | 16 | 16 | 14 | 14 | YES |
| `472A0966A5204513` | 16 | 16 | 14 | 14 | YES |
| `596804AA1ACD01EB` | 17 | 17 | 15 | 15 | YES |
| `C3D3E48F1E14AE2A` | 16 | 16 | 14 | 14 | YES |
| `F5BC9FB6D084559E` | 16 | 16 | 14 | 14 | YES |
| `FFAC0A88768A8A59` | 16 | 16 | 14 | 14 | YES |

On all six the idle section is index 0 of two, and each document's two located
sections map to two distinct roll-up rows.

## 4. The OCR-loss question — is there evidence these sections ever had rows?

The class exists because rows can vanish while captions survive. I looked for
every trace such a loss would leave, and I report what I found and what I could
not tell.

**I found no evidence of loss on any of the six, and four printed facts and four
structural facts pointing the other way.**

| evidence sought | `333E…` | `472A…` | `5968…` | `C3D3…` | `F5BC…` | `FFAC…` |
|---|---|---|---|---|---|---|
| roll-up movement columns (deposits, withdrawals) both zero | yes | yes | yes | yes | yes | yes |
| roll-up opening also reproduces the section's own opening | yes | yes | yes | yes | yes | yes |
| printed dividend / interest **year-to-date** figure is zero | yes | yes | yes | yes | yes | yes |
| the coinciding pair is a **non-zero** carried figure | yes | yes | yes | yes | yes | yes |
| account named on exactly two lines of the whole document | yes | yes | yes | yes | yes | yes |
| extractor's `page_integrity`: `truncated: false`, no signals, every page | yes | yes | yes | yes | yes | yes |
| the paper's own `Page x of y` sequence complete, single `y` | yes | yes | yes | yes | yes | yes |
| page markers contiguous; none inside the span; no blank line inside the span | yes | yes | yes | yes | yes | yes |

Four of these the cell did not report and they strengthen its case:

* **The roll-up's opening column also reproduces the section's own printed
  opening.** Condition 7 only asks about the closing. The table in fact
  corroborates both ends of the pair on all six, which is a stronger statement
  than the ruling requires.
* **The coinciding figure is not zero on any of the six.** This matters, because
  "the printed pair coincides" would be a much weaker fact if the pair were zero
  and the roll-up's closing were zero too — a zero matching a zero. It is not:
  the account carries a real balance across the period and the table restates
  that same balance under a caption that says which column it is.
* **The printed year-to-date dividend / interest figure is zero on all six** —
  the account earned nothing across the whole year, not merely this period.
* **The account is named twice in the entire document.** A section whose rows had
  been lost would normally leave the account named where those rows had been.

Against loss structurally: the extractor's own per-page integrity record reports
no truncation and no signals on every page of all six; the statement's own
`Page x of y` numbering is complete from 1 to `y` with a single `y` on all six;
and the idle section is three or four contiguous lines with no blank line, no
page marker, and the sibling's heading printed immediately after it — there is no
whitespace consistent with removed lines and no page boundary inside or adjacent
to the span.

**What I cannot tell, stated honestly.** I cannot rule out a loss that occurred
before this artifact was written and left no trace in it — one that removed rows
and also removed every mention of the account that would have accompanied them,
while leaving both captions, both figures, the zero movement columns and the zero
year-to-date figure mutually consistent. Nothing in this cache can settle that,
because there is no second reading of the paper to compare against (MINOR-2).
What I can say is that the artifact is internally consistent with an account that
carried a balance and posted nothing, and inconsistent with an account that
posted and lost its rows.

## 5. Findings

### MINOR-1 — the six were not OCR'd at all; the class's own hazard is untested here

Every one of the six carries the extractor model **`native-pdf-text`**: the text
came from the PDF's own embedded text layer, not from an OCR. The class
`printed_pair_coincides_and_no_row_printed` exists to bound the hazard where OCR
loses ledger rows while captions survive. On this population that hazard cannot
arise, so the roll-up witness has been **measured exactly as Gustavo ordered, but
has not been exercised against the failure mode it was ruled in to guard**.

This is not a defect and it does not lower N — the ruling asked whether the
witness exists and reads, and it does, on all six. It is a scope statement S4 and
Phase 2 must carry: the cell's own risk note says the result "is a fact about
that OCR partition", which understates it. When Phase 2 feeds the same
deterministic validator from Unlimited OCR or PaddleOCR, these six must be
re-measured, because that will be the first time the witness is asked to do the
job it was ruled in for. I recommend this sentence travel into `BATCH9_BACKLOG`
and into the `OCR-LEGACY-AUDIT` card's inputs.

### MINOR-2 — one partition, and it cannot be cross-read from this cache

I checked directly: the cold cache holds **exactly one `ocr`-stage artifact per
document** for each of the six (`artifact_cache` grouped by stage and
`input_sha256`), and **no PDFs anywhere under the cache**. The brief asked
whether the six could be cross-read; they cannot, from here. The cell named this
risk and I confirm it is real and unmitigable at this base rather than merely
cautious. If Ocean wants a second reading before S4 leans on the class, it has to
come from outside this cache.

### MINOR-3 — C7's link is sound here, but a mis-binding would be invisible to the probe

`witness_for` establishes "the row for this section" as
`boundary.startswith("rollup-oracle")` plus `section.identity_index`. Because
`_sections_from_rollup` located the section FROM the row, that index is correct by
construction — which also means the probe cannot detect a row bound to the wrong
heading. It reports `identities_distinct` (two sections, two distinct indices),
and that holds just as well when both bindings are wrong.

Measured here, the hazard is absent: no label is a prefix of another, and my
independent label-and-token route reaches the same row on all six (§3.2). So this
lowers no cell. It is a caveat on generalisation: if S4's population ever widens
beyond this family, the row↔section link must be re-established by the printed
label rather than inherited from the boundary, and the probe as written would not
raise its hand.

### MINOR-4 — on `472A0966A5204513` the design's label reader loses the product name

Pressing on MINOR-3 turned up one document where the link is thinner than the
prose suggests. The design's `find_rollup` reads that document's idle row label as
the suffix parenthetical alone — the printed product designation is trimmed away —
even though the paper does print it (my reader reads it off the same line). The
consequence is that `_locators` builds its second pattern from the bare caption
word, which matches **11 lines** of that document including every one of the
sibling's reprinted headings. The correct binding there is carried entirely by the
first locator, the fenced identity token, which matches exactly the two lines the
account occupies.

The binding is right, and my label-based route confirms it independently, so C7
stands on `472A0966A5204513` and N is unaffected. But on that one document
"located by the section's own label" is really "located by the section's own
identity token", and the label locator would have been degenerate had the token
not been available and unique. Two further documents (`596804AA1ACD01EB`,
`FFAC0A88768A8A59`) have the reverse shape — the token locator matches five
places and the label locator two — so on those the label is the discriminating
half. Worth a sentence in the design's L1-C3 notes.

### MINOR-5 — two wording slips in the cell's W3, both cosmetic

* W3 `§Q3PROBE9` writes the privacy invocation as `--shas <the six>`.
  `--shas` takes a **file** of 64-hex `content_sha256` values; sha16s on the
  command line are rejected. I reproduced every number in that table with a
  population file, so the measurement is right and only the prose is loose. Worth
  correcting so the next cell can copy the line.
* "W3 headings 99 → 100" is true on the `^# §` convention (I measure 99 → 100);
  on a plain `^# ` count it is 402 → 403. Both are +1 and the claim is honest;
  naming the convention would save a reviewer the detour.

## 6. Nothing rests on an already-ratified class — reproduced with my own inputs

The cell's 0 / 6 is load-bearing: it is what makes the +6 the new class's alone.
The cell obtained it by handing production's `analysis.sibling_omission.
evidence_class` what the design's readers read. I re-asked the same classifier
with **my own** readings of each section, so the answer is not the cell's input
handed back:

| document | `prints_dormancy_declaration` | `prints_zero_activity_summary` | `evidence_class` |
|---|---|---|---|
| `333E226A75FE5441` | False | False | **none** |
| `472A0966A5204513` | False | False | **none** |
| `596804AA1ACD01EB` | False | False | **none** |
| `C3D3E48F1E14AE2A` | False | False | **none** |
| `F5BC9FB6D084559E` | False | False | **none** |
| `FFAC0A88768A8A59` | False | False | **none** |

**0 / 6 confirmed.** The reason the zero-activity class cannot fire is condition
5 itself — that class needs printed zero totals and printed zero counts, and these
sections print no counts or totals at all, which is what C5 measured. The class is
read fail-closed, so absence refuses it rather than defaulting into it. The whole
of the +6 rests on `printed_pair_coincides_and_no_row_printed`.

## 7. The mutants, and the exit contract

Re-ran the cell's mutation mode over the same six. **30 / 30 reproduced**, each
mutant flipping the cell it names to the refusal class it names in advance:

| mutant | must flip | killed / applied |
|---|---|---:|
| `rollup-closing-misread-by-a-cent` | C7 | **6 / 6** |
| `rollup-column-caption-removed` | C7 | **6 / 6** |
| `rollup-row-not-located-by-the-sections-label` | C7 | **6 / 6** |
| `document-prints-no-rollup` | C7 | **6 / 6** |
| `one-dated-row-printed-in-the-section` | C4 | **6 / 6** |

A mutation table nothing survived proves the mutants kill; it does not prove the
instrument would REPORT a survivor. The archive run cannot exercise that path, so
I drove the exit contract directly with constructed records:

| condition | contract | measured |
|---|---:|---:|
| a mutant that did not kill | 4 | **4** |
| every mutant killed, every cell decided | 0 | **0** |
| any UNDECIDABLE cell | 3 | **3** |
| population 0 against `--expect-sections 6` | 2 | **2** |
| population 1 against `--expect-sections 6` | 2 | **2** |

All five hold. The STOP is live in both directions — an empty population and a
merely different one both stop before any cell is measured — which is what makes
the reported 6 a measurement rather than a default.

## 8. Register

The probe imports `analysis.sibling_omission.evidence_class` and nothing else
from the analysis; it calls neither `analyze_markdown` nor `cached_analysis`.
`tests/test_corpus_gate_outcomes.py`'s sweep is over exactly those two entry
points, so **no register entry is owed**, and there is none:
`git show train9:corpus_gate.py | grep -c q3_corroboration_probe` is 0 and the
branch adds none, so there is no key to collide at composition. The gate test is
green with the probe present (§9).

## 9. The floor I reproduced

Every row below I ran myself on this branch at `65041bf`.

| proof | my result | exit |
|---|---|---:|
| `tools/l1_design_idle_evidence.py` at the base (the population) | 214 documents · 21 idle · **6** under the ruling · 6 documents · 1 group | **0** |
| `tools/q3_corroboration_probe.py`, run of record `cda8882d` | 6 sections / 6 documents · 42 cells decided · 0 UNDECIDABLE · **N = 6** · mutants 30 / 30 | **0** |
| my own independent reader, same six | 42 / 42 agreement with the cell · 0 disagreements | — |
| `tests/test_q3_corroboration_probe.py` | 28 passed | **0** |
| canonical guards (`test_no_statement_hardcodes` `test_no_parser_helper_clones` `test_r1_hardcodes` `test_experiments_are_not_wired` `test_filename_boundary`) | 255 passed | **0** |
| `tests/test_corpus_gate_outcomes.py` `tests/test_currency_source.py` + the card's test | 89 passed, 10 deselected | **0** |
| `tools/privacy_scan_branch.py --base e5b0342 --ref HEAD` | added lines 1,565 · population 6 · documents read 6 · **hits 0** · residue sites 0 | **0** |
| the same with `--no-exclusions` (RAW) | **raw hits 0**, attributed to no exclusion rule | **0** |
| `tools/huntington_msg_privacy_scan.py --base e5b0342 --ref HEAD` | commits 3 · population 6 · MONEY 0 · DIGITS 0 · DATES 0 · WORDS 0 | **0** |
| `git diff --name-status e5b0342..65041bf` | 3 files (1 M, 2 A); **0** under `analysis/` `ocr/` `webapp/` `discovery/`; 0 lines in `corpus_gate.py` | — |
| W3 `^# §` headings | 99 → 100 | — |

Every number the cell published in `§Q3PROBE9` reproduces. Not run and not owed,
for the cell's stated reasons which I checked and accept: the full suite, the
corpus gate and the corpus-marked slice (no production path differs from the
base), `cohort_replay` (no reader to replay), the archive sweep (no reader
changed). Two heavy harnesses were live on this host throughout and my own work
stayed inside the six documents.

## 10. Verdict and what it licenses

**CONFIRMED — N = 6.** The seven conditions hold on all six measured
`guardian_cu` idle sibling sections, by the cell's instrument and independently
by mine, with every location reproduced and every mutant re-killed. S4's
demonstrated target is **2 + 6 = 8**.

It licenses a planning figure and nothing else. It moves no document; official
batch-9 coverage is unchanged. It says nothing about the published sibling on
these six, which remains S4's question under the unchanged production standard
(Q9 Option B) with Q10's rule for the omission. It does not generalise beyond one
census group and six documents. And per MINOR-1 it is a result about six
documents whose text was never OCR'd, so the witness's value against OCR row-loss
— the reason the class was ruled in — remains to be measured in Phase 2.
