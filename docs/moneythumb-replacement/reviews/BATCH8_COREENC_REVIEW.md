# BATCH 8 REVIEW — CORE-ENCLOSURES (`wave8-coreenc`, tip `32116b3`, base `10cc722`)

Independent adversarial review. The reviewer did not write this code and asked
the cell nothing; every claim below was re-measured. Read: the card, the branch
diff (12 files), `W3_TRACKA_LOG.md` §COREENC C0–C18, and the shared helpers the
diff calls. Nothing else.

**No archive content appears in this file.** Documents are named by an 8-hex
`content_sha256` prefix; magnitudes are classes; figures, dates, names, account
numbers and merchant strings are never quoted.

---

## VERDICT: **APPROVE WITH FINDINGS** — 0 BLOCK, 2 MAJOR, 6 MINOR

The claim under review reproduces in full, end to end, on the run of record:

| claim | measured at HEAD | verdict |
|---|---|---|
| 58 census members, all `digital` / `failed` / `no_parser_matched` | 58 distinct shas, all `failed/no_parser_matched` | reproduces |
| the two required markers reach **67** of 3,380, and nothing else | **67** | reproduces |
| the 67 are 54 addressable members + 13 outsiders | 54 + 13, and the 4 unreached are exactly the census verifier's 4 named misfiles | reproduces |
| **46** `validated/approved`, 1 `review`, 1 `withheld`, 6 decline at the ledger, 4 never claimed | 46 / 1 / 1 / 6 / 4 = 58 | reproduces |
| the 13 outsiders publish nothing | 13/13 `parse` → `None`; the 10 superseded unmoved, the 3 scanned `no_parser_matched` → `parser_declined` | reproduces |
| 40 publish with a printed grid, 8 without | 40 / 8 | reproduces |
| 5,872 published rows, 849 carrying a block label | 5,872 rows, **849** bare labels, 778 of them on exactly four members, 71 elsewhere | reproduces |
| supersedes: the pinned document is claimed at 1.0, pruned to `[linkbank 0.5]` | pre-prune `[core_processor_enclosures 1.0, linkbank 0.5]`, post-prune `[linkbank 0.5]` | reproduces |
| the pinned payload does not move | base tree vs branch tree: **byte-identical** | reproduces |
| privacy residual traced, no archive figure in source | 0 archive-sourced figures/dates/accounts/names in the branch; **0** in the production module | reproduces |

Three doctrine surfaces were checked directly and all hold: currency
**48/48 `USD` / `schema_default`** with `bank=None` on every published document
(no jurisdiction class claimed it does not have); ADB **48/48
`calendar_day_printed_period` / `canonical_v1`**, with the bank's own average
published only as `bank_reported_average_balance` (evidence, gating nothing);
and the repair doctrine — **6,971 published money leaves across the 48
documents, and every single one appears as a printed token in the document's own
cached text. Zero figures are written, substituted or reconstructed.**

Detection collisions with the two sibling batch-8 registrations already on
`train8` were measured in **both** directions and are zero: this reader claims
0 of their 14 census documents; `core_processor_signed_counts` and
`core_processor_activity_summary` claim 0 of these 67; and this registration's
conformance fixture is claimed by neither of them, nor is any of `train8`'s
77 fixtures claimed by this reader.

The financial core is untouched (`adb.py`, `reconcile.py`, the metrics,
classification and serialization modules are absent from the diff), and the two
shared files that are touched are purely additive: one new key in
`corpus_gate.EXCLUDED_ANALYSIS_CALLERS` and one new key in
`count_semantics.SECTION_LEVEL_ORACLES`. No truth-set pin, audit CSV or corpus
PDF is in the diff.

What keeps this from a clean APPROVE is evidence discipline, not behaviour: one
measurement written into **shipped source** does not reproduce, and the
mutation proof that the card's floor requires was never committed — and when
reconstructed independently it leaves two of the module's own named gates
unpinned.

---

## FINDINGS

### 1. MAJOR — a count that does not reproduce, in tracked production source

**Claim.** C6, the module docstring and — decisively — the shipped disclosure in
`analysis/count_semantics.py` all state that the debit count excludes the
service charge on **13 documents, one of them posting it as two rows**.
(`analysis/count_semantics.py:1195-1204`, the figure itself at `:1199`;
`analysis/core_processor_enclosures.py:71-87`; W3 §COREENC C0 and C6.)

**Evidence.** Re-derived at HEAD over the 48 members this reader publishes, by
running the module's own `_summary` / `_blocks` / `_ledger` and comparing the
captured rows against the printed counts (exit 0):

| debit rows in excess of the printed count | documents | excess money equals the printed service charge |
|---|---|---|
| 0 (and no service charge printed) | 29 | n/a |
| 1 | **17** | 17/17 |
| 2 | **2** | 2/2 |

That is **19 documents, two of them posting it as two rows** — every one of the
19 that prints a service charge at all. The credit half of the same paragraph
reproduces exactly (**5** documents, one excess row each, equal to the printed
interest). The 6 members that decline at the ledger cannot be measured on either
side, so 48 is the whole measurable population; the record's own denominator
("over the 54 addressable members") cannot produce 13 either.

The reader's *behaviour* is correct — the code admits `> debit_count` and pins
the money to the cent — and the doctrinal conclusion (leave the registration at
`UNSURVEYED`) is unaffected. What is wrong is the number, and it is wrong in a
disclosure record that Ocean and later `count_semantics` cards will read as
measured fact.

**Required closure.** Re-measure and correct the figure in all three places, or
publish the instrument that produced 13 and explain the different denominator.
Because one of the three is `analysis/count_semantics.py`, this closure lands in
tracked source and needs its own commit.

---

### 2. MAJOR — the mutation table does not exist and the harness is not committed; two named gates are unpinned

**Claim.** C12: "32 mutants, each applied by an exact string replacement that had
to match exactly once … 32 applied, 32 killed, 0 survived. Harness: the private
scratchpad's `mutate.py`; log: `mutation3.log`."

**Evidence.** §COREENC contains no mutation table — no mutant rows, no killers,
no per-gate mapping — only the totals above, while C8 refers to two mutants by
identifier ("M31, M32") that appear nowhere. Neither the harness nor the log is
in the branch (`tools/` on this branch holds `coreenc_family_replay.py` only;
sibling cells committed `tools/descattrib_mutate.py` and
`tools/extractpriv_mutate.py`). The card's proof floor is explicit: "a MUTATION
TABLE for every gate you add or touch, run WITHOUT `-x` so every killer is
named" and "commit your instruments under tools/ when they produce headline
numbers". **32/32 is therefore not checkable by review.**

Reconstructed independently: 29 mutants of my own, each an exact single-match
replacement on a clean tree, scored against the branch's own five test files
without `-x`, restored by byte comparison after every one (exit 0, 104 s, all 29
restored, `git status` clean afterwards). **19 killed, 10 survived.** Every one
of the module's four headline gates is genuinely pinned, and each by the test
that names it:

| gate disabled | killed by |
|---|---|
| the summary's own identity | `test_a_summary_whose_own_identity_does_not_close_is_refused` |
| the credit count | `test_a_captured_credit_count_that_disagrees_with_the_printed_one_is_refused` |
| the credit total | `test_a_captured_credit_total_that_disagrees_with_the_printed_one_is_refused` |
| the debit count | `test_a_captured_debit_count_that_disagrees_with_the_printed_one_is_refused` |
| the debit total | `test_a_captured_debit_total_that_disagrees_with_the_printed_one_is_refused` |
| the grid walk | four grid tests |
| decline-rather-than-drop an unreadable run | `test_an_unreadable_row_declines_the_document_even_when_its_run_is_droppable` |
| direction from the block, not the sign | `test_the_direction_is_the_block_the_bank_printed_the_row_in` |
| the cross-reference pointer | `test_a_cheque_the_grid_cross_references_instead_of_pricing_is_not_a_row` |
| the strip cut at the closing balance | `test_the_year_to_date_interest_printed_after_the_closing_balance_is_not_read` |
| the SUMMARY-block rule, both directions | the two summary tests |
| the fee-detail block published as rows | `test_the_fee_detail_block_is_not_published_as_rows` |
| the repeated-product-name rule | `test_a_repeated_product_name_publishes_no_name_rather_than_the_repetition` |
| the second required marker demoted | `test_the_registration_carries_two_required_markers` + two detection tests |
| the interest allowance bounded to the printed figure | `test_an_interest_posting_is_admitted_only_for_the_figure_the_bank_printed` |
| the cent tolerance | four tests |

**Required closure.** Commit the harness under `tools/` and the per-mutant table
with its killers, so the 32/32 claim is reproducible — and close finding 3,
which the reconstruction exposed.

---

### 3. MAJOR — a test named after a gate is not a test of that gate: the duplicate-day grid checks are unpinned

**Claim.** `analysis/core_processor_enclosures.py:726-730`: "A day printed twice
with two different balances refuses the document: the grid arrives three columns
to a line and a duplicate is evidence the column recovery went wrong, which a
map that silently kept the last reading would hide."
`tests/test_core_processor_enclosures.py:531`
(`test_a_grid_printing_one_day_twice_with_two_balances_is_refused`) is the test
named for it.

**Evidence.** Two mutants survive the whole branch test set (exit 0 on all five
files):

* `_grid`'s intra-block duplicate check (`:741-742`) disabled — **survives**;
* `parse`'s cross-block merge check (`:879-880`) disabled — **survives**.

The named test still passes with the first check disabled, because the duplicate
it plants makes the *last* reading the wrong one, so the walked-balance
comparison in `_matches_the_printed_grid` kills it instead. The check is
nevertheless live and not equivalent: a grid that prints one day twice where the
**second** reading is the correct one is refused at HEAD and publishes with the
check disabled (demonstrated on an invented document, exit 0). This is precisely
the class the card warns about — "a test named after a gate is not a test of
that gate", and batch 7's "a 'reorder' mutant that actually deleted the reading
pinned nothing".

**Required closure.** Add a test whose duplicate day's *second* reading is the
correct one (kills the intra-block check) and a test with two grid sections
disagreeing on a shared day (kills the merge check), and add both mutants to the
table from finding 2.

---

### 4. MINOR — six further bounds and fail-closed guards survive removal

**Claim.** The module states each of these as a rule it enforces.

**Evidence.** Survivors from the same 29-mutant run (branch test set, exit 0):

| condition | file:line | effect of removing it |
|---|---|---|
| the debit allowance's count bound | `:788` | any number of excess debit rows admitted, provided the money still closes to the printed fee |
| the credit allowance's count bound | `:782` | the same on the credit side |
| the reversed-period guard `end < start` | `:851` | a period printed backwards is no longer refused here |
| `_PRODUCT_NAME_LIMIT = 60` | `:347` | raised 100× with nothing failing |
| `_DESCRIPTION_LIMIT = 200` | `:598` | raised 100× with nothing failing |
| `if not postings` → `if postings is None` | `:856` | an empty ledger reaches the gates (which still refuse it) |
| an unreadable amount dropped instead of declining | `:660-661` | probably unreachable — every token `_LEDGER_FIGURE_RE` captures parses, checked across both sign placements and the bare-cents form |

None of the seven changes the archive result, and the count bounds are honestly
disclosed in the docstring as deliberately loose with the money doing the work.
They are listed because each is a stated rule with no failing input behind it.

**Required closure.** Either pin them or say in the table that they are
defence-in-depth, unpinned by design.

---

### 5. MINOR — the committed replay instrument reports a field it never measures

**Claim.** `tools/coreenc_family_replay.py` is committed "so the card's headline
numbers are reproducible by review", and its per-document row carries
`parser_id`.

**Evidence.** `tools/coreenc_family_replay.py:130` reads
`(payload or {}).get("parser_id")`, and `analysis.serialization.report_to_dict`
has no top-level `parser_id` key (its keys are `statement`, `classifications`,
`reconciliation`, `metrics`, `detection`, `quality`, `integrity`, `model_used`,
`escalated`). The field is therefore the empty string on **every** document the
instrument reports, including the 46 it says are validated — a silent null, not
a measurement. The outcome classes the instrument exists for are correct and were
reproduced independently.

**Required closure.** Read the claimant from the dispatch (as the sibling field
`claimed_by_named_parser` already does) or delete the field.

---

### 6. MINOR — the 13 documents claimed outside the family are never named by `content_sha256`

**Claim.** C13 item 4: the three scanned documents that move
`failed/no_parser_matched` → `failed/parser_declined` "are named in C0/C2".

**Evidence.** C0 describes them as "3 scanned printings of the same block" and
C2 as "the three SCANNED documents my registration newly claims"; neither gives
a sha, and no sha for any of the 13 outsiders appears in §COREENC except the one
pinned document. The card requires "Every mover named by `content_sha256` +
outcome + field", and the 3 scanned documents are movers. The 58 are named,
because the census carries their sha list; the 13 are not named anywhere.

**Required closure.** List the 13 by `content_sha256` in §COREENC, marking the 3
movers and their transition.

---

### 7. MINOR — headline measurements whose instruments are not committed, and which do not reproduce

**Claim / evidence,** each re-measured by this review:

* **C3, the days-sentence row: 53.** Measured over the 58: **56** documents
  print the sentence *with* its count (the registered pattern), **57** print the
  label at all. Neither is 53. The rest of C3 reproduces exactly — the average /
  interest rows at 57, the enclosures token at 49, `Average Collected` at 51, the
  image appendix at 30, the SUMMARY block at 12.
* **C7 and the module docstring, the sign census (3,485 / 954 / 1,005 / 2).**
  Over the 48 published members, reading each block through the module's own
  role split, I measure a different set of four numbers with the same shape and
  the same conclusion — the debit side overwhelmingly signed, the credit side
  overwhelmingly unsigned, a substantial unsigned debit population from the
  collapsed cheque grids. The design decision the numbers justify is
  independently proven (the "direction from the sign" mutant is killed), but the
  counts cannot be checked because the census that produced them is not
  committed.
* **C16, "32,167 literals".** My own extraction over the same 71 documents
  yields 21,424 distinct literals. Definitional, and unverifiable:
  `privacy_scan.py` is deliberately not committed.
* **C18.2, "51,594 leaves on each side".** My flattener counts 51,420 on each
  side. The conclusion — 0 differing, byte-identical — reproduces exactly; the
  leaf count cannot, because the leaf-diff is not committed.

**Required closure.** Correct the C3 row; for the other three, state the
definition alongside the number, or commit the instrument, per the card's rule
that headline numbers reproduce from committed evidence.

---

### 8. MINOR — two record inaccuracies

* **A dangling forward reference.** C18.3 ends "The slice was re-run at the final
  tree on the quiet host and its result is in the table below" —
  `W3_TRACKA_LOG.md:44266` is the last line of the file and of the section.
  There is no table below. The corpus slice's final-tree result appears only in
  C15 *above* (`CORPUS_EXIT=0`, 30 passed).
* **C16 overstates its own result.** "No archive-sourced literal survives
  anywhere in the branch" is not true as written: the template's printed BLOCK
  banner vocabulary is in tracked source by design, and my residual surfaces two
  banner words that the cell's base-vocabulary filter absorbed. That vocabulary
  is expressly permitted by the card ("institution furniture … is allowed and
  must be justified as furniture") and *is* justified, at
  `analysis/core_processor_enclosures.py:490-500`. The sentence should read "no
  archive-sourced figure, date, name or account number survives".

**Required closure.** Fix both sentences.

---

## THE INSTRUMENTS I RE-RAN

Every command below ran at branch tip `32116b3` against the run of record
`…356a4269/rows.csv` and the D-3 artifact store by direct file path. No sqlite
index was opened, no artifact written, no OCR run, no hosted model called;
`analyze_markdown(..., parse_mode="deterministic")` throughout. Cost $0.00.
Long runs were detached Git-bash processes terminated by their own `EXIT=` line.

| # | instrument / command | exit | wall |
|---|---|---|---|
| 1 | `pytest -q` on the branch's five test files — 1,161 passed, 35 skipped | **0** | 11 s |
| 2 | archive detection reach + population replay, 3,380 documents then 71 analysed | **0** | 99 s |
| 3 | money-leaf / currency / ADB / bank audit over the 48 published | **0** | 63 s |
| 4 | description audit over the 48 published (DESC-ATTRIB class) | **0** | 51 s |
| 5 | collision probe, branch side: this reader over the 14 sibling documents | **0** | ~10 s |
| 6 | collision probe, `train8` side: both siblings over these 67 documents | **0** | ~25 s |
| 7 | reverse fixture probe: this reader over all 77 `train8` fixtures | **0** | ~5 s |
| 8 | pinned document replayed under the base tree (registry 75, `10cc722` blobs) | **0** | ~10 s |
| 9 | pinned document replayed under the branch tree (registry 76) | **0** | ~10 s |
| 10 | `cmp` of the two payloads → **byte-identical**, 51,420 leaves each side | **0** | <1 s |
| 11 | pre-`supersedes` claimant sets on three superseded documents | **0** | ~15 s |
| 12 | `parse` over the 10 superseded + 3 scanned + 13 adversarial inputs | **0** | ~15 s |
| 13 | independent mutation harness, 29 mutants, no `-x`, all restored | **0** | 104 s |
| 14 | independent privacy scan (71 documents × the whole branch diff) | **0** | 8 s |
| 15 | count-scope re-derivation over the 48 (finding 1) | **0** | ~50 s |
| 16 | furniture and sign census over the 58 / 48 (finding 7) | **0** | ~60 s |
| 17 | ADB basis, integrity flags, count comparability over the 48 | **0** | ~60 s |

`git status` in the worktree was clean before the mutation run and is clean
after it; the only new path in this branch from this review is this file.

The three heavy proofs the card owes were **not** re-run, by instruction: the
full default suite (claimed 5,917), `python corpus_gate.py` (claimed GREEN), and
the archive-wide `regfp_zero_movement_sweep`. See "claims I could not verify".

---

## MY PRIVACY RE-MEASUREMENT

Built independently of the cell's scan: from the cached text of all **71** named
documents, every amount-with-cents (both sign placements and the bare-cents
form), every full or partial date token, every digit run of 5 or more and every
capitalised word — **21,424 distinct literals** — intersected with the **2,330
added lines** of `git diff 10cc722..wave8-coreenc`, then filtered against the
vocabulary the tracked repository already carried at the base commit (466 text
files scanned).

* raw intersection: **198**
* residual after the base-vocabulary filter: **16**
* residual by file: `tests/test_core_processor_enclosures.py` 12,
  `tests/data/parser_conformance_fixtures.py` 1,
  `analysis/core_processor_enclosures.py` **3**, `W3_TRACKA_LOG.md` 15
  (a literal can land in more than one file)

**Adjudication.** All 12 numeric residuals — two round figures, one full date,
five partial dates and four signed amounts — are values of the *invented*
statement the test module documents at its head, and every one of them is in the
test module and/or the invented conformance fixture and the log's own account of
them. Not one is a reading taken from a document; the shapes match the cell's own
enumeration in C16 exactly. **The three residuals in the production module are
all BLOCK-banner words** — the template's printed section headings, which the
card admits as furniture and which the module justifies as such at
`:490-500`. There is **no archive-sourced amount, balance, date, account number,
reference or merchant string anywhere in the branch**, and none at all in the
production module. This is not the batch-7 BLOCK class. The only correction owed
is the wording of C16's own conclusion (finding 8).

This review file was checked the same way and carries no archive literal.

---

## CLAIMS I COULD NOT VERIFY

1. **`python corpus_gate.py` GREEN (105 PASS / 3 WITHHELD / 1 REFUSED, the
   currency and provenance surfaces).** Not re-run, by instruction. Indirectly
   corroborated: the one pinned document this card can reach is byte-identical
   between the base and branch trees (51,420 leaves each side), its post-prune
   claimant set is unchanged, and no pin file is in the diff.
2. **Full default suite 5,917 passed.** Not re-run, by instruction. The five test
   files this branch touches pass at exit 0 (1,161 passed, 35 skipped) — the
   count is consistent with the base's 5,857 plus this module's 46 and the
   registry deltas, but the total itself is unchecked.
3. **The archive-wide sweep (`identical 2,558 / moved 0 / payload_now_raises 0 /
   no_payload_now_publishes 48`).** Not re-run, by instruction. Its central claim
   is independently corroborated: I analysed the full claimed set at HEAD and
   found the 48 publications inside the census family and no crash anywhere,
   and the 10 superseded documents all unmoved in outcome class.
4. **"32 applied, 32 killed, 0 survived."** Unverifiable — see finding 2. My own
   29-mutant reconstruction is not the cell's and cannot confirm theirs.
5. **C7's sign census and C16's literal count.** See finding 7 — the instruments
   are not committed and the definitions are not published.
6. **The register-time band change for the three issuer readers** (100 → 10, C13
   item 2) affects dispatch order only; I confirmed the three carry `band=10` and
   `supersedes={core_processor_enclosures}` and that `EXPECTED_ORDER` moves with
   them, but the ordering's downstream effect is a merge-time concern for Ocean.

---

## C13 AND C18, RELAYED

**C13, the cell's four questions for Ocean.** (1) `SECTION_LEVEL_ORACLES` gains a
third entry: this template's two printed counts each exclude a row class the
ledger posts, the mapping schema can express only the fee half, so the
registration stays at the incomparable default — turning the comparison on needs
a new `PRINTED_EVIDENCE_FIELDS` member for credited interest, which is a
`count_semantics` card. (Note finding 1: the entry's own figure is wrong.)
(2) `burke_herbert` / `farmers_merchants` / `linkbank` move from band 100 to band
10 with their edges, following `first_farmers` and `b1`; dispatch order only, but
it moves the pinned `EXPECTED_ORDER`. (3) `analysis/reconcile.py`'s coverage
ratio has no scope mapping, so a template that bills interest outside its own
credit total trips the ±2 % band whenever the interest exceeds 2 % of it — one
document today, and the money-side analogue of `count_semantics` is the fix, not
this card's file. (4) The 3 scanned documents newly claimed move
`failed/no_parser_matched` → `failed/parser_declined` — a parser recognised the
template and could not read the scan; I confirm the transition and that they
publish nothing.

**C18, the closure proofs and the one red reading.** C18.1: the archive sweep at
the final tree found 48 `no_payload_now_publishes` and nothing else moved —
chunk exit `1` is the tool's "findings exist" code and the chain terminator is
`EXIT=0`; the 3 scanned declines are invisible to that instrument by
construction (no payload before, raises again now) and are measured by the
population replay instead. C18.2: the pinned `AF6BD563…` is claimed by this
reader at a higher score than `linkbank`, is pruned to `linkbank` alone before
any parse, and its payload is unchanged leaf for leaf — **I reproduced all three,
and the payload is byte-identical between the base and branch trees.** C18.3, the
red reading: the corpus-marked slice read `CORPUS_EXIT=1` twice on the
detect-sweep affordability budget while 14–20 python processes shared the host,
and green on a quiet one; re-measured best-of-nine, the sweep runs 3.4× under
budget and is *faster* with this registration than without it, because the
assertion divides by `len(registrations)` and a registration of average cost
leaves the projection where it was. I did not re-run that slice; the reasoning is
sound and the arithmetic is the constant's own documented failure mode. The
section's closing sentence points at a table that does not exist (finding 8).

---

## RECOMMENDATION TO OCEAN

Merge is defensible. The reader is fail-closed, publishes no figure the document
does not print, moves no pinned record, collides with nothing on `train8`, and
delivers 46 validated documents on the archive's largest unclaimed printed
identity — the single largest coverage claim of the batch, and it reproduces.

Findings 1 and 2 should close **before** the merge: finding 1 because it is a
wrong measurement in shipped source that other cards will cite, and finding 2/3
because a coverage card of this size owes its mutation table and two of its own
named gates currently rest on tests that pass for a different reason. Findings
4–8 are record and instrument hygiene and can close in a follow-up commit on the
same branch.
