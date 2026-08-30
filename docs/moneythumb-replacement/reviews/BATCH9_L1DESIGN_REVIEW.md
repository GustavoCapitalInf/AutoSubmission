# BATCH9 L1-ARCH-DESIGN — independent adversarial review

Reviewer: an independent Opus cell. It did not write the design, asked the design cell nothing,
and re-measured every load-bearing figure with the cell's own instruments and with four of its
own. Branch `wave9-l1design`, base `train9` `ac1d034`, tip `8751d20`, 8 commits, worktree
`.claude/worktrees/mt9-l1design`. Run of record
`discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d`; cold cache
`.claude/recovery/webapp_data_train8_cold`, read-only throughout.

**VERDICT: SOUND WITH FINDINGS — 4 BLOCK / 6 MAJOR / 12 MINOR.**

The architecture is right and the cell's central contributions are real and reproduce: RULE S,
the `cohort_replay` blind spot, the untaught-reader ordering correction, and four production
defects that are all confirmed at the cited code. **Every headline number in the design
reproduced at this base.** The four BLOCKs are not disagreements about the architecture; three
of them are places where the design's own instruments already hold the answer to a question it
puts to Gustavo as an open risk, and the fourth is a fail-closed rule that removes money on a
coincidence. All four are correctable inside the document; none requires the ruling to be
re-opened.

The single most important result of this review: **the design's largest open question (Q8 —
whether the checkpoint's idle-sibling condition applies to the two silent skips production
performs today) is answerable at this base, and the answer is ZERO documents at risk.** The
design says of the bound it did measure that "no instrument outside the reader itself can tell
those apart" (§9, W3 §L1DESIGN L1D5). Instrumenting the reader itself tells them apart exactly,
and it says the evidence R-a demands is printed on 15 of 15 skipped sections.

---

## 1. Re-measurement table

Every row was produced by this reviewer at this base. `tools/l1_design_*` and `tools/l1_*` are
the cell's / the L1INV cell's instruments run unchanged; the `REVIEW` rows are this reviewer's
own instruments, kept in private scratch and unwired.

### 1.1 The cell's own instruments, re-run

| claim (design §) | design | this re-run | agrees |
|---|---|---|---|
| payload probe cohort (§1.2) | 208 documents, 71 registrations, all `validated` | 208 / 71 / 71 | **yes** |
| `wrapper_conditional` (RULE S) byte-identical (§1.2) | 208 / 0 | 208 / 0 | **yes** |
| `wrapper_unconditional` byte-identical (§1.2) | 0 / 208 | 0 / 208 | **yes** |
| `omission_field_always` byte-identical (§1.2) | 0 / 208 | 0 / 208 | **yes** |
| `omission_field_elided` byte-identical (§1.2) | 208 / 0 | 208 / 0 | **yes** |
| document outcome unchanged, all four variants (§1.2) | 208 | 208 | **yes** |
| the `cohort_replay` leaf blind spot (§1.3) | 0 byte-identical vs 208 leaf-identical | 0 vs 208, gap **208** | **yes** |
| reader probe: readers that REFUSE the document shape (§1.4) | 0 of 6 | 0 of 6 | **yes** |
| reader probe: readers that refuse the Option-D shim (§1.4) | 0 of 6 | 0 of 6 | **yes** |
| `classify_outcome` under the document shape (§1.4) | `withheld/withheld_adb` | `withheld/withheld_adb` | **yes** |
| `rebuild_serialized_revenue_views` under it (§1.4) | rebuilt over 0 transactions | rebuilt over 0 | **yes** |
| `_analysis_rows` / `_masked` under it (§1.4) | 0 export rows / 2 keys | 0 / 2 | **yes** |
| `likely_account_count` distribution (§1.7) | 496/2700/167/6/1/10; ≥2 = 184, validated 156 | identical | **yes** |
| boundary mechanisms (§2.2) | 103 / 38 / 35 / 38 | 103 / 38 / 35 / 38 | **yes** |
| fail-closed reasons for the 38 `none` (§2.2) | 22 / 11 / 5 | 22 / 11 / 5 | **yes** |
| per-section evidence availability (§2.2) | 208 / 273 / 327 / 79 / 24 / 31 | identical, shares identical | **yes** |
| roll-up as oracle (§2.2) | 60 / 117 / 37 | 60 / 117 / 37 | **yes** |
| roll-ups printing a COLUMN CAPTION (§2.2, L1-C5) | 30 of 214; 184 none | header classes 15+8+7 = **30**; `none` **184** | **yes** |
| sibling classes (§2.3) | 4 / 0 / 30 / 62 / 7 = 103 | 4 declaration / 30 posted / 62 empty-silent / 7 other = 103 | **yes** |
| documents where every sibling satisfies the ratified rule (§2.3) | 0 | 0 | **yes** |
| documents carrying a posted-and-silent sibling (§2.3) | 26 | 26 | **yes** |
| single-posting documents, 2-row threshold (§2.3, Q7) | 86 | 86 | **yes** |
| trivially idle sections, provenance (§2.3) | 21, all `section`/`section`; 0 from the table | 21, all `section`/`section`; 0 | **yes** |
| ... printing a dated row anywhere / in the ledger (§2.3) | 3 / 0 | 3 / 0 | **yes** |
| the 6 sections the ruling would license (§2.3) | 6 on 6 documents, all `section`/`section`, 0 rows / counts / totals / dailies | identical | **yes** |
| 27 documents lose every section (§2.4) | 27 documents, 77 sections, 392 offered | 27 / 77 / 392 | **yes** |
| the closure ladder (§2.6) | 153·/21/23/65/54/48/48/37/**29**/16 | identical | **yes** |
| oracles separately (§2.6) | 48 handed over, `reconcile` refuses 11, ADB 10 | 48 / 11 / 10 | **yes** |
| documents whose every located section closes (§2.6) | **2** | **2** | **yes** |
| ... under omission of a trivially idle sibling (§2.6) | **8**, all one census group, table reproduces on 8 | 8, `FAM:guardian_cu_statement_summary`, 8 | **yes** |
| by mechanism, offered / closed / fully closing (§2.6) | 212·19·2 / 89·10·0 / 84·0·0 / 7·0·0 | identical | **yes** |
| transfers (§3.1) | 11 documents with 2+ live ledgers, **7** movers, **47** pairs | 11 / 7 / 47 | **yes** |
| L1-C12 facility population (§4) | 19 documents, 4 multi-posting, 7 with a total | 19 / 4 / 7 | **yes** |
| documents printing a cross-account total at all (§4, L1-C10) | 43 | 43 | **yes** |
| L1-C13 two-denomination population (§4) | 4 documents / 12 sections, one census group | 4 / 12, `FAM:community_savings_bc` | **yes** |
| the per-registration L-1 cohorts (§6.2) | 234 documents, **230** validated, per-registration split | identical, row by row | **yes** |
| the run's own outcome split (§6.1) | 3,380: 2,596 / 18 / 55 / 698 / 13 | identical | **yes** |
| F1 — `_DORMANT_RE` is dead (§9) | referenced by no code in `analysis/` or `tests/` | grep at this tree: only `tools/l1_split_prototype.py` and prose | **yes** |
| F3 — the memorised slice (§9) | `consumers.py`:88-94 and :115-123 | confirmed at those exact lines | **yes** |
| F4 — the derived selection (§9) | `community_section.py`:701-735, selection at :731-733 | confirmed (`best` set at :734) | **yes** |
| F5 — the printed first rung (§9, §10.1) | instrument prints **153**, packet prints 109 | printed **153**; 153−21−23 = 109 | **yes** |
| production diff vs base (§10.3) | empty | empty | **yes** |
| instruments unwired (§10.3) | nothing outside `tools/` references them | grep: none | **yes** |
| canonical guards (§10.3) | 255 passed, EXIT=0 | **255 passed, EXIT=0** | **yes** |
| branch privacy scan (§10.3) | hit_count 0 over 2,396 added lines / 3,351 documents | **hit_count 0** at the TIP: 2,401 added lines, 3,351 read, 3,380 population, MONEY/DIGITS/DATES/WORDS all 0, raw 29 all `words_class` | **yes (stronger)** |

`·` the first ladder rung is the F5 display double-count; 109 is the semantically correct value
and reconciles (109 − 21 − 23 = 65).

### 1.2 This reviewer's own instruments

| REVIEW measurement | result |
|---|---|
| **RULE S on registrations the cell's cohort cannot reach** — the 9 registrations claiming documents but holding NO `validated` document (`atb`, `bmo`, `chase_export`, `eq_bank_scanned`, `farmers_merchants`, `found_lead_activity`, `frost`, `ibc`, `linkbank`), 33 documents, all `withheld` or `review` | `wrapper_conditional` byte-identical **33 / 33**; `wrapper_unconditional` 0 / 33; `omission_field_always` 0 / 33 with leaf gap **33**; `omission_field_elided` 33 / 33. RULE S now holds over **241 documents / 80 registrations** |
| **does Ocean's `train9` `flatten` fix close the blind spot** — the same empty-list key added to 30 real payloads, compared under the base `leaf_diff` and the `train9` one | bytes differ 30 / 30; base `leaf_diff` blind **30 / 30**; `train9` `leaf_diff` blind **0 / 30**. The fix closes it |
| ... and what it costs | the baseline payloads already carry **6,337 empty containers across 30 documents** (up to **577** in one), so the fixed projection compares thousands of new leaves; every cell's `--expect-identical` fidelity baseline must be re-established at `train9` before it is used as a control |
| **the EXACT Q8 population** — the absence-based skips executed on the production dispatch path (`analyze_markdown(parse_mode="deterministic")`), counted by instrumenting the readers themselves | **11** validated documents, **15** sections: `symitar` 4 docs / 7 sections, `community_section` 5 / 6, `dakota_west` 2 / 2, `mission_valley` 0 / 0. The design's bound is 15 documents; the population is **11** |
| **what those 15 skipped sections PRINTED** | `symitar`: **7 of 7** carry the RATIFIED declaration `_DORMANT_RE` in their own section text; 0 of 7 match `symitar._ROW_RE`. `community_section` / `dakota_west`: all **8 of 8** dropped blocks print their own OPENING balance, their own CLOSING balance **coinciding to the cent**, a ZERO credit total, a ZERO debit total, a ZERO credit count and a ZERO debit count — read by `community_section._summary`, which is fail-closed and returned a complete summary on 8 of 8 |
| **where `community_section` actually skips** | all 8 drops fire at `community_section.py:621-622` (`if not txns: return None` inside `_parse_sectioned_statement`). **Zero** fire at `:984`'s `stmt.transactions` clause, which is the line the design names |
| **F4's derived selection, live** | `parse_dakota_west_statement` chose among **2 or more** candidate sections on exactly **1** of its 3 validated documents (`4D15B2AC6493B82C`); the other two had a block dropped instead |
| **the payload readers the design's probe omits** — same document, same three shapes, same criterion ("a pure function of the payload dict") | **5 more**: `telemetry/diagnostics.py::diagnose` (wired into `telemetry/record.py::build_record`:417 — the discovery telemetry record), `telemetry/stated_counts.py::evaluate`, `benchmark/ourside.py::OurFileResult.statement/.metrics/.reconciliation`, `balance_forensic_audit.py`:528-529, `corpus_gate.py::production_verdict`'s `_Verdict` construction. **4 answer quietly, 1 refuses loudly (KeyError).** Complete census so far: **11 readers, 10 quiet, 1 loud** |
| **the document-level STRICTER closure count** the design's own instrument prints | `documents whose EVERY LOCATED section closes` = 2; `... under the STRICTER test as well` = **0**. The design carries the section-level 16 and not this |
| **the trivially-idle sections' other printed evidence** the design's own instrument prints | of the 21, **7 print their own counts or totals**; the design's §2.3 table omits that row (it is 0 on the 6 that matter) |
| **the facility vocabulary's uncounted classes** the design's own instrument prints | `debit_card` fires on **15** documents, **5** of them multi-posting, and is NOT counted; `card_network` fires on 6, 0 multi-posting. L1-C12's 19 / 4 is the counted-class population only |

---

## 2. Findings

### BLOCK-1 — L1-C17's closed vocabulary names none of the evidence the platform's own skipped sections print, and §1.5's override then converts 11 currently-validated documents to `failed`

L1-C17 admits exactly three reason tokens: `printed_dormancy_declaration`,
`yield_only_arithmetic_with_summary_equality`, and — only if Q3 is granted —
`printed_pair_coincides_and_no_row_printed`. §1.5's third document-level override says an
omission whose `reason` is not a ratified evidence class returns `("failed", …)`. S2's file list
is "`analysis/symitar.py`, `analysis/community_section.py`, `analysis/zions.py` — the skip
SITES only", and §7's S2 row expects "payload movement on the documents whose reader skips a
section today" and "**none expected**" pinned movement.

Measured, by executing the readers rather than bounding them with a regex:

| registration | validated | documents where an absence-based skip FIRES | sections skipped |
|---|---:|---:|---:|
| `symitar` | 7 | **4** | 7 |
| `community_section` | 59 | **5** | 6 |
| `dakota_west` | 3 | **2** | 2 |
| `mission_valley` | 36 | 0 | 0 |
| **total** | **105** | **11** | **15** |

And what the paper printed on those 15 sections:

| evidence available on the skipped section | sections |
|---|---:|
| `symitar` — carries the RATIFIED `_DORMANT_RE` declaration in its own text | **7 of 7** |
| `community_section` / `dakota_west` — prints its own opening balance | **8 of 8** |
| ... its own closing balance | **8 of 8** |
| ... the two COINCIDE to the cent | **8 of 8** |
| ... a ZERO credit total / ZERO debit total | **8 of 8** each |
| ... a ZERO credit count / ZERO debit count | **8 of 8** each |
| **skipped sections with NO printed evidence of their empty state** | **0 of 15** |

So R-a is satisfiable on every one of them — but only two of the three vocabulary members can
name any of it, and neither names the second class. A printed account summary with an opening,
a coinciding closing, zero totals AND zero counts is stronger evidence than
`printed_pair_coincides_and_no_row_printed`, and L1-C17 has no token for it. As the design is
written, S2 must either invent a token (which L1-C17 forbids: the vocabulary is closed and
"cannot become" wider for absence) or file 11 protected documents `failed`.

`analysis/zions.py` compounds it. It is named as an S2 skip site and is **never probed** by any
instrument in this cell. Its skip is not absence-based at all: `_inert` (`zions.py`:248-250)
requires `not rows` **and** every printed summary column to be `0.0` — printed evidence — and
`_NO_ACTIVITY_RE` (`zions.py`:78, live at :200) is a printed dormancy declaration in a wording
different from symitar's. Neither is a member of L1-C17 either, and `zions` carries 12
protected documents.

**Required before an implementation card:** widen L1-C17 to the evidence classes the archive
actually prints — at minimum a `printed_zero_activity_summary` (opening + coinciding closing +
zero totals + zero counts) and a wording-independent `printed_dormancy_declaration` that covers
both symitar's and zions' phrasings — and re-state S2's expected movement as "0 validated
documents lost, 11 documents re-founded on printed evidence, 15 sections surfaced". Also
re-state S2's pinned expectation: §6.3 says one pinned document is claimed by `dakota_west`, and
`dakota_west` has exactly 3 documents, two of which have the skip firing and the third of which
carries F4's derived selection — so **every** `dakota_west` document is inside S2/S5's blast
radius and "none expected" is not established until the pinned one is named.

### BLOCK-2 — the number the ruling turns on has a document-level counterpart of 0, which the design's own instrument prints on the adjacent line and the design does not carry

§7 states "The honest total. Across all six stages the measured newly-validated count is **2**
documents today and **8** under one ruling", and §2.6's ladder reports the stricter row-coverage
rung at SECTION level only: "nothing dated printed AFTER the chain reached the closing (a
STRICTER bound, reported) | **16**".

`tools/l1_split_prototype.py`, re-run at this base, prints in its Headline table:

```
| documents whose EVERY LOCATED section closes            | 2 |
| ... under the STRICTER test as well                     | 0 |
```

and, in the review-chain table, `+ nothing dated printed after the chain either (STRICTER) | 0`.

The stricter test is over-strict by the instrument's own account (`l1_split_prototype.py`
:528-537: the last section of a document runs to the end of the document and carries its
trailing tables, and the dated-row pattern counts furniture) — that is a good reason to keep 2
as the headline, and a bad reason to omit 0. Gustavo is being asked whether correctness work is
worth doing at a price of "2 today, 8 under one ruling"; the honest range his own instrument
supports is **0 to 8**, with the reason the low end is pessimistic stated beside it.

**Required:** carry `all_close_strict = 0` into §2.6 and §7 with the instrument's own
explanation of why the strict bound over-counts, exactly as §2.6 already does for the
section-level 16.

### BLOCK-3 — the payload-reader census is incomplete by its own criterion, and the ordering constraint the whole staging rests on is stated over it

§1.4 measures "every payload reader that is a pure function of the payload dict" — 6 readers,
0 refuse — and concludes: "**Therefore: no document may publish two accounts until every payload
reader has been taught the shape.** That is the ordering constraint §7 is built around". S3's
exit criterion is that constraint.

By the same criterion, on the same document and the same three shapes, five more readers exist:

| reader | `baseline` | `document` shape |
|---|---|---|
| `telemetry/diagnostics.py::diagnose` — called by `telemetry/record.py::build_record`:417, so it rides in **every discovery telemetry record** | 0 codes, `evaluated=True` | 0 codes, `evaluated=True` — an empty diagnosis that claims it evaluated |
| `telemetry/stated_counts.py::evaluate` | `match/compared`, 27 transactions | `check_unavailable/statement_absent`, 0 transactions |
| `benchmark/ourside.py::OurFileResult.statement/.metrics/.reconciliation` | 23 / 91 / 22 keys | **0 / 0 / 0** |
| `balance_forensic_audit.py`:528-529 (`payload["statement"]` by direct index) | opening and ending present | **RAISES KeyError** |
| `corpus_gate.py::production_verdict`'s `_Verdict` construction | `_Verdict('validated', flags 0, 'clear')` | `_Verdict('withheld', flags 0, '')` — which mismatches `PUBLISHED_OUTCOME` and turns the gate red |

4 of 5 answer quietly; 1 refuses loudly. **The complete census is 11 readers, 10 quiet, 1 loud** —
which strengthens the design's conclusion and falsifies its count.

The same incompleteness runs through §5. There are **nine** production call sites that pair
`analyze_markdown` with `report_to_dict`, and each must move to the new document entry point or
a multi-account document publishes one account through the old seam:

| call site | named in §5? |
|---|---|
| `discovery/runner.py`:452 | the file is named; **this line is not** |
| `corpus_gate.py`:1355-1356 | yes (inside `production_verdict` :1298-1370) |
| `benchmark/ourside.py`:99 | yes (:88-113) |
| `batch.py`:179-181 | the file is named as `:87-176`; **the seam is at :179-181, outside the cited range** |
| `balance_forensic_audit.py`:505/516 | the file is named as `:650-700`; **the payload read is at :516-529** |
| `webapp/artifact_cache.py`:215-216 | only `:436` (the version constant) is named |
| `analyze.py`:175/187 — **the CLI**, which §1.1's own rationale names as a `report_to_dict` consumer | **no** |
| `webapp/worker.py`:29 | **no** |
| `adb_forensic_audit.py`:480/493 | **no** |

**Required:** complete both censuses (readers and seams) in §1.4 and §5 before S3 is carded, and
make S3's exit criterion a checkable list rather than a universal quantifier over an unstated
set. The shape assertion L1-C16 is a convention, not a gate: nothing in the design makes a test
prove that every payload reader carries it.

### BLOCK-4 — the INTERNAL flag is set from an arithmetic coincidence with no printed evidence, and the 47-pair "measured killer population" is produced by a pairing rule that is the opposite of §3.3's

§3.2's rule: same posting date, same magnitude to the cent, opposite sign, one-to-one; "where it
prints one on neither, **the arithmetic signature stands alone**". §3.3: an ambiguous candidate
records **no** pairing and the package refuses to aggregate.

Three problems, all in the same place.

1. **No printed evidence is required, and none is measured.** `tools/l1_split_prototype.py::
   _transfer_pairs` (:861-888) reads date, magnitude and sign and nothing else; no printed
   transfer designation is consulted anywhere in the instrument, and the design nowhere measures
   how many of the 47 pairs carry one. R-d says transfers are "identified as INTERNAL"; it does
   not license identifying them from a coincidence. A member who deposits a sum into checking on
   the day they withdraw the same sum from savings for an unrelated purpose produces a unique,
   unambiguous, entirely non-internal pair — and §3.2 flags it, and §3.2's own consequence
   removes it from package gross deposits, deposit counts, revenue and the withholding
   denominator. That is money the paper printed, deleted from a funder's view of the business by
   an inference. It is the same class of error the repair doctrine forbids, in the opposite
   direction.
2. **The killer population does not implement the design's own rule.** `_transfer_pairs` takes
   the FIRST admissible counterpart and `break`s. §3.3 says two admissible counterparts record
   nothing. So the 47 includes pairs resolved by guessing, and the ambiguous population — the
   thing L1-C11's mutation table needs — is unmeasured.
3. **The one-to-one claim does not hold beyond two ledgers.** `taken` is re-initialised for each
   `(left, right)` ledger pair, so on a document with three or more non-empty ledgers one posting
   can be counted into two pairs. 11 documents reconstruct two or more live ledgers; how many
   have three or more is unmeasured.

**Required before S4 is carded:** measure how many of the 47 pairs carry a printed transfer
designation on either leg; re-measure the population under §3.3's own fail-closed rule (no
pairing where a counterpart is not unique) and under a document-wide one-to-one matching; and
state whether an arithmetic-only pairing may set INTERNAL at all, or whether the printed
designation is required and the rest refuse the aggregation. This is a ruling-sized question and
it belongs in §8 beside Q2, not inside §3.2 as a settled rule.

---

### MAJOR-1 — L1-C18 forbids "first printed" selection; §5 prescribes it

L1-C18: "no reader selects an account by a DERIVED quantity — most transactions, largest balance,
**first printed**. Selection is by printed partition or there is no selection (R-e)."

§5, `discovery/runner.py`: "`statement_bank` (:162) and `account_last4` (:163) are the only two
Statement-derived columns; **they become the FIRST account's**, plus a new `account_count`."

The design's own condition names the rule its own surface table breaks. `account_last4` is the
column by which a human identifies a document; making it the first account's is the L-1 defect
relocated to the discovery row. Resolve it explicitly: either L1-C18 drops "first printed" and
says why printed ORDER is printed evidence where a derived quantity is not (§1.1 already relies
on printed order for `accounts`, and §1.5 for tie-breaking), or the row columns become
`account_count` plus nothing, or a joined multi-value column.

### MAJOR-2 — RULE S's 208 / 208 is a tautology at the seam it tests

`tools/l1_design_payload_probe.py::probe_one` compares `report_to_dict(report)` against
`document_to_payload_conditional(DocumentReport(accounts=[report]), report_to_dict)`, which under
RULE S returns `report_to_dict(doc.accounts[0])` where `doc.accounts[0] is report`. The equality
is by construction. What the 208 proves is that `report_to_dict` is deterministic over the same
object — worth knowing, not what §1.2 says it is ("state how that is guaranteed and **proved**").

I extended the cohort to the 9 registrations holding no validated document at all (33 documents,
all `withheld` or `review`, where `ending_balance` is nulled and the ADB block is absent):
RULE S holds 33 / 33 and the other three variants behave identically. The claim is now robust
over 241 documents and 80 registrations — and it is still a claim about the SERIALISER.

The risk RULE S is offered against lives one layer up, and no instrument touches it: `§5` has
`analyze_markdown` gaining "a document-level entry point" and `assess_document_integrity`
(:260-512) **split by scope**, with `missing_declared_statement_page` (:409-486),
`parser_ambiguous` / `parser_exception` (:345-358) and `repair_exception` (:388-395) moving to a
document block while the reconciliation, coverage and count flags (:288-344) and all of
`assess_quality` (:179-240) stay per account. On a single-account document those flags must land
in exactly the same payload keys they land in today, and that is a property of the pipeline
change, not of RULE S. **S1's proof plan must name the pipeline seam and the integrity split as
what it is proving**, with the byte comparison run over a tree that actually carries them.

### MAJOR-3 — a package ADB over the accounts of one document is a document-level combined ADB by another name

R-c: "NO document-level combined ADB". §2.5 honours it inside the payload, and §6.5 makes it
mechanical: "the ADB basis and policy stamps are asserted on **every account** and **no
document-level ADB field exists**".

But §8 Q5 proposes that each account of a multi-account document "enter a PACKAGE as its own
member", and `webapp/app.py`:1152-1164 then publishes `package_average_daily_balance` as the
days-weighted mean of its members' ADBs. For a package holding exactly one multi-account
document that single published figure IS a combined average over that document's accounts. The
gate assertion cannot see it, because it forbids a document-level FIELD and this is a package
field.

Say what a package containing a multi-account document publishes, and put it in Q5 explicitly.
If the answer is "the weighted mean is a package figure and a package of one document is still a
package", that is defensible — but it must be ruled, not left to fall out of the surface table.

### MAJOR-4 — F2's mechanism is not the one production takes, and the cited skip site is the wrong line

§9 F2: "`analysis/community_section.py`:984 counts a section only `if stmt is not None and
stmt.transactions` … A section that parses but posts nothing is silently not counted". S2 owns
"the skip SITES only" and names that line.

Measured over all 62 `community_section` / `dakota_west` / `mission_valley` validated documents:
107 blocks offered to `_parse_sectioned_statement`, 8 dropped, and **all 8 return at
`community_section.py:621-622` (`if not txns: return None`)** — inside the per-section parser.
**Zero** are dropped by `:984`'s `stmt.transactions` clause; that clause never fires on this
archive. An implementation card told to instrument `:984` will surface nothing.

The substance of F2 survives (the drop is on absence of parsed rows, and it is silent); the site
and the mechanism must be corrected to `:621-622`, and the omission record must be written where
the reader that made the skip can see the block — which is inside `_parse_sectioned_statement`,
not at its call site.

### MAJOR-5 — CONS-HARDCODE's pinned movement is stated as a disjunction and omits the second `consumers` document

The card asked for "the exact expected movement for each" pinned document. §6.3 gives:
"`05E246C0ED6678E6` … today: published under a memorised product-name + account-number slice …
after S5: **either** published from the printed partition, **or** REFUSED under L1-C1/C4".

That is not a movement; it is the absence of one. And two facts in the design decide it:

* §7's S5 row measures that "the `DECL-L1-CANDIDATE` band closes **0** of 16 multi-posting
  documents today" — so on today's evidence the printed partition does not close and the branch
  taken is REFUSED;
* §6.2 records that `consumers` claims **2** documents in the run, **both** `validated`, and the
  memorised literal at `consumers.py`:90 is what makes the reader return anything at all
  (`:111-112` refuses when the slice is empty). Removing it moves both documents or neither.

So the stated expectation should be: **2 validated documents → failed, one of them pinned**, on
a correctness argument (the published ledger today is one memorised account of a member's
several). That is a `validated → failed` on protected shas, which BATCH9-RULES makes a
STOP-and-report requiring explicit per-sha evidence that the batch-8 validation was itself
incorrect. The evidence exists and the design half-states it; it must be stated whole before the
card is cut, and the audit-CSV re-derivation must cover both documents' paths, not one.

### MAJOR-6 — a jurisdiction or institution default can outrank a DOCUMENT-level printed currency statement

§4's currency block: `printed` and `product` evidence "must be read from the SECTION's own text;
a section may not inherit a sibling's `printed` evidence", while `jurisdiction_default` and
`institution_default` "are document/institution facts and are inherited by every section that
earned no stronger class of its own".

The rule is right about siblings and silent about the document. A statement that prints its
denomination once, in a footer or a masthead, and then prints two sections neither of which
repeats it, resolves both sections to a DEFAULT — and R-f is "explicit currency evidence
outranks defaults", full stop. Add the missing rung: a document-level `printed` statement is
explicit evidence and outranks both defaults for every section that earned nothing of its own,
and only a section that contradicts it refuses. The population is measurable at this base
(`FAM:community_savings_bc`, 4 documents / 12 sections, is the two-denomination class; the
single-denomination document-level class is not measured anywhere).

---

### MINOR findings

1. **F1's line citation is wrong by two.** §9 and `tools/l1_design_surface_census.py`'s own
   printed prose say the production dormant skip is `symitar.py:421` / `:421-422`. It is
   **`:419-420`**. `:421-423` is a comment. An implementation card patching the cited line
   patches a comment.
2. **"three files under `tools/`"** — §10.3 and W3 §L1DESIGN L1D9 both describe the branch as
   "this document, the W3 section and three files under `tools/`". There are **four**
   (`l1_design_payload_probe.py`, `l1_design_surface_census.py`, `l1_design_reader_probe.py`,
   `l1_design_idle_evidence.py`), and §10.2 lists all four.
3. **`_yield_only` "as written" is not what ran.** §2.3 reports "satisfy the yield-only
   arithmetic **as written** | 0" and cites the fourth condition's lines (`symitar.py`:339-345).
   `tools/l1_split_prototype.py::classify_sibling` calls `_yield_only(rows, opening, closing,
   None)` — the three-condition RELAXED form, as its own docstring now discloses (the L1INV
   review's MINOR-B). The direction is safe and the 0 stands; the word "as written" and the
   citation of :339-345 should carry the disclosure the instrument carries.
4. **Two different denominators are printed as one fact.** §2.2 says the roll-up "closes with a
   cross-account total on **37**"; §4's L1-C10 says "**43** documents print a cross-account
   total". Both reproduce: 37 is over the documents with a LOCATED roll-up, 43 is over all 214.
   Neither says so.
5. **Not every condition has a measured killer population**, though §4's preamble says each does.
   L1-C2's cell is a hypothesis ("the mutant is a duplicated section"), L1-C14's and L1-C18's are
   code citations, and L1-C15's is "standing". Four of eighteen.
6. **L1-C5 names no caption→role vocabulary**, so "the table must print a COLUMN CAPTION naming
   which column is which" is not yet a predicate. The vocabulary exists and is measured — the
   three header classes `type_prev_dep_wd_end` (15), `type_begin_end` (8), `begin_end` (7), with
   the role map at `tools/l1_split_prototype.py`:132 — and should be cited in the condition.
7. **L1-C4 depends on an unruled definition.** "Every posting section is accounted for" turns on
   Q7's posting threshold: at two dated rows a section printing one row is not a posting section
   and C4 permits dropping it; at one row it does not. The condition should name its dependence.
8. **L1-C12's population excludes classes its own instrument fires on.** The 19 / 4 counts
   `loan` (14), `mortgage` (5) and `brand_row` (4). `debit_card` fires on **15** documents, **5**
   of them multi-posting, and is not counted; `card_network` on 6. The design's doctrine ("the
   class of a row is established from the ROW, not from a word in it") is the right answer to
   that, and the uncounted-class table belongs beside the 19 / 4 so an implementer knows the
   condition's real reach.
9. **§2.3's idle-section table omits a row its own instrument prints.** Of the 21 trivially idle
   sections, **7 print their own counts or totals**. It is 0 on the six the ruling would license,
   so nothing downstream moves — but §2.3's "the evidence on those six is not silence" reads
   differently when the population's other 15 are described completely.
10. **The payload probe's own output contradicts its preceding table.** For
    `omission_field_always` the "Where a differing variant differs" section prints "*(none — no
    document's payload changed)*" on all 208 documents whose payload it has just reported as
    changed. The cause is the blind spot itself (the added leaf is invisible to `leaf_diff`), so
    the label should say "no leaf path changed", not "no payload changed".
11. **`classify_document` ranks an unranked class lowest.** `LADDER.index(pair[0]) if pair[0] in
    LADDER else -1` makes `deferred`/`unknown` the minimum, so such an account would set the
    document's class to one `discovery/compare.py::direction` scores as `unranked` — neither an
    improvement nor a regression, i.e. invisible to the non-regression regime. Unreachable today
    (per-account `classify_outcome` is called without `deferred=`), and worth a `raise` rather
    than a `-1`.
12. **§9 F3 over-states the second copy.** `consumers.py`:116 restates the product name and
    suffix but not the account number (`(\d+)` is a capture, not a literal). "restates the same
    literal" is half true; the account number appears once, at `:90`.

---

## 3. Answers to the eight hostile questions

### (1) Does the design satisfy each of Gustavo's six conditions literally?

| condition | verdict | evidence |
|---|---|---|
| **R-a** idle sibling only on explicit structure | **satisfied in the rule, broken by the vocabulary** | §2.3 is literal and §4's L1-C17 says `absence_of_parsed_rows` "is not a member and cannot become one". But the vocabulary names no token for the evidence 8 of the 15 skipped sections actually print, and none for `zions`' two printed grounds — BLOCK-1 |
| **R-b** each account validated by the UNCHANGED validator | **satisfied** | §2.1: `reconcile` and `compute_average_daily_balance` called as `pipeline.py` calls them today; §5's row for `analysis/reconcile.py`, `adb.py`, `metrics.py` is "**nothing**". No instrument or design clause modifies either |
| **R-c** no document-level combined ADB | **satisfied in the payload, leaked at the package** | §2.5 is unambiguous and §6.5 makes it a gate. `webapp/app.py`:1152-1164's days-weighted mean over accounts-as-members reintroduces one figure over one document's accounts — MAJOR-3 |
| **R-d** transfers stay in both ledgers, flagged INTERNAL | **satisfied in the ledgers, unsound in the identification** | §3.2 keeps both legs (correct, and the only way `reconcile` stays unchanged) and excludes the indexed postings from every package sum. The flag itself can be set from date+amount+sign alone with nothing printed — BLOCK-4 |
| **R-e** no arbitrary or memorised selection | **satisfied in the conditions, contradicted in the surfaces** | L1-C18 forbids derived selection and names F3/F4; `accounts` is "printed order, NEVER sorted". §5 then makes two discovery-row columns "the FIRST account's", which L1-C18 lists as forbidden — MAJOR-1 |
| **R-f** explicit currency evidence outranks defaults | **satisfied for sections, silent for the document** | §4 forbids a section inheriting a sibling's `printed` class — the exact silent denomination R-f bans. It does not rank a document-level printed statement above `jurisdiction_default` — MAJOR-6 |

Where "explicit statement structure" is replaced by inference: nowhere in the boundary layer
(L1-C1 refuses `section-equation-scan` outright, and that mechanism closes 0 of 84 sections
offered — confirmed), and once in the transfer layer (§3.2's arithmetic-only fallback).
Where a document-level average sneaks in: only through the package (MAJOR-3); the roll-up is
correctly confined to an oracle by §2.5 and L1-C10, and `RollupOracle` carries no figure at all
— only `caption_class`, `column_roles_printed`, `rows`, `cross_account_total_printed`, which I
verified in `tools/l1_design_payload_probe.py`'s prototype dataclass.
Where a "primary"/derived selection survives: `discovery/runner.py`'s two columns (MAJOR-1) and,
until S5 lands, `parse_dakota_west_statement` — which I measured actually choosing among 2+
candidates on 1 of its 3 validated documents.

### (2) The 18 fail-closed conditions: a document shape that passes and is still wrong; are the killer populations real?

The killer populations are real and reproduce for 14 of the 18 (see §1.1: C1 35, C3 0/44, C4
26/0, C5 30/184/23, C6 2, C7 23/11, C8 79 & 11-of-48 & 0-of-105, C9 10-of-48 & 24-of-442, C10 43,
C11 7/47, C12 19/4/7, C13 4/12, C16 6-of-6, C17's cohorts). Four have none: C2, C14, C15, C18
(MINOR-5). C11's reproduces as a number but not as the design's own rule (BLOCK-4).

Passing-and-still-wrong shapes, constructed against the conditions as written:

* **L1-C7.** The condition is scoped "inside the span it read". A section whose ledger resumes
  after the next section's heading — an interleaved or continued grid — satisfies C7 while its
  later rows are outside the span and are silently dropped. The design already measures the
  proxy: 29 sections close, **16** survive "nothing dated printed after the chain", and at
  document level the instrument prints **0** (BLOCK-2). The gap is 13 sections.
* **L1-C1 + L1-C2.** A roll-up enumerates accounts A and B whose identities reappear as headings;
  the document also prints a third posting section the table does not enumerate. C1 is satisfied
  for the published two. C2 asks for disjointness and complete coverage of "the document's ledger
  region", a term the design never defines and no instrument measures. The third section is
  dropped with nothing in the payload to show for it.
* **L1-C10 + L1-C12.** C12 suspends C10 for a document whose roll-up enumerates a facility. 7 of
  the 19 facility documents also print a cross-account total, and 4 carry two or more posting
  sections. Those documents publish multiple accounts with **no cross-account oracle at all**,
  passing every condition. That is where the design's strongest oracle is switched off, and it is
  switched off on exactly the family (`FAM:goldenwest_cu_member_account_statement`) the prior
  review named as the next one an implementation would reach for.
* **L1-C5.** "Prints a COLUMN CAPTION naming which column is which" passes for any caption in the
  vocabulary; a table printing an ambiguous caption (a bare balance word) satisfies the letter and
  is mapped by position after all. The vocabulary is closed in the instrument (MINOR-6) but not in
  the condition.
* **L1-C4 + Q7.** A section printing exactly one dated row is not a "posting section" at the
  two-row threshold, so C4 permits dropping it — and the threshold is unruled (Q7). At one row the
  same document refuses. The condition's truth depends on an open ruling.
* **L1-C11.** A unique same-day, same-magnitude, opposite-signed pair that is not a transfer
  passes and removes a real deposit from every package total (BLOCK-4).
* **L1-C16.** The assertion binds "every reader taught the shape". It says nothing about the 10
  readers measured to answer quietly and cannot, because four of them are not in the design's
  census at all (BLOCK-3).
* **L1-C17.** The three shapes of BLOCK-1: symitar's declaration is admissible and unimplemented;
  the printed zero-activity summary is inadmissible and printed on 8 of 8; zions' two printed
  grounds are unnamed.

The two gaps the prior review found are both **closed**: transfers are now L1-C11 (§3 in full)
and facilities are L1-C12 with the corrected 19 / 4 population and the "class from the ROW, not
from a word in it" doctrine that answers MAJOR-A directly.

### (3) Is "no added key of any kind" achievable through `report_to_dict` for ALL consumers; is "no top-level `statement`" safe for every consumer that indexes it?

**RULE S: yes, and it is trivially yes, which is the finding.** RULE S returns
`report_to_dict(accounts[0])` verbatim, so every consumer of the payload dict — the CSV and XLSX
exports (`webapp/app.py::_analysis_rows` → `_analysis_csv` / `_analysis_xlsx`), the corpus gate's
audited fields (the `PINNED_CURRENCY` / `PINNED_CURRENCY_SOURCE` tables at `corpus_gate.py`:424
and :594, whose checks read `(payload.get("statement") or {})` at :1523 and :1600), the discovery
telemetry record, `webapp/storage.py` (which stores the payload as opaque text and needs no
migration) —
sees today's bytes because it sees today's dict. I confirmed byte-identity over 241 documents and
80 registrations. What is NOT proved is the pipeline seam that produces the object (MAJOR-2).

No surface serialises the object differently: `report_to_dict` is the single serialiser and all
nine call sites reach it. But **four of those nine are absent from §5** (BLOCK-3), so "all
consumers" is currently a claim about a list that does not include the CLI.

**"No top-level `statement`" is safe in the sense the design intends — it stops nobody.**
Measured over 11 readers: **1 crashes** (`balance_forensic_audit.py`:528-529, KeyError, because
it indexes rather than `.get()`s) and **10 silently publish nothing or the wrong thing**:
`classify_outcome` files the document `withheld/withheld_adb`; `diagnose` returns an empty
diagnosis marked evaluated and rides in every telemetry record; `stated_counts.evaluate` reports
`check_unavailable/statement_absent`; `rebuild_serialized_revenue_views` rebuilds every revenue
view over an empty ledger; `_analysis_rows` exports 0 rows; `_masked` serves 2 keys; `ourside`
reports 0 statement, 0 metrics, 0 reconciliation keys; `production_verdict` builds
`_Verdict('withheld', (), (), '', False)` — which at least turns the corpus gate red against
`PUBLISHED_OUTCOME`, making the gate the one accidental guard at document level.

So the design's conclusion — teach the surfaces DARK before the first publisher — is right and
this review strengthens it. Its census is what must be completed.

### (4) Is the document outcome fail-closed under `classify_outcome`, the compare ladder and the gate's vocabulary? What does `withheld` + `validated` render as, and can package analytics read the validated account alone?

**Fail-closed: yes, on the ladder.** `classify_document` folds by `min` over
`LADDER = ("failed", "withheld", "review", "validated")`, which is `discovery/compare.py`:37
verbatim; a `validated` fold is further downgraded to `("review", "sibling_section_omitted")`
when anything was omitted, and three document-level overrides can only lower. `compare` keys on
`content_sha256` alone (:73) and `direction()` ranks on the same tuple, so one outcome per
document is preserved and a weakest-account fold cannot be scored as an improvement. `corpus_gate`
reads `classify_outcome`'s class into `_Verdict` (:1298-1370) and `PINNED_OUTCOMES` /
`PUBLISHED_OUTCOME` are keyed by that class, so the fold reaches the gate intact. The one
residual is the `-1` rank for an unranked class (MINOR-11).

**A `withheld` account beside a `validated` one renders as `withheld` at document level**, reason
`account_withheld_adb`, and the design is explicit that this is "other ladder movement", never
newly validated. Correct.

**Can package analytics read the validated account alone? Yes — and worse, today they read
everything.** `webapp/app.py::_package_analysis` gates a member on `ready = job.status == "done"
and job.analysis is not None` (:661) and **never** on `classify_outcome`. So under §8 Q5's
"each account enters the package as its own member", a document filed `withheld` at document
level still contributes the validated account's ledger AND the withheld account's ledger to
gross deposits, deposit counts, revenue, the withholding denominator and NSF counts, with only
the withheld account's ADB nulled by `_metrics_dict` (`serialization.py`:102-133). The design
never states a package-membership rule for a non-validated ACCOUNT. That is the fail-closed hole
Q1 half-touches: Q1 asks whether the document publishes the validating account's figures, and the
answer that matters is what the package does with them. **State the rule: a package member is an
account whose own outcome is `validated`, or the whole document refuses.**

### (5) F1 / F2 / F4 re-measured, and the exact per-registration sha counts Q8 turns on

**F1 — `_DORMANT_RE` is dead code: CONFIRMED.** `grep -rn "_DORMANT_RE"` over the whole tree at
this base returns `analysis/symitar.py`:116 (the definition) and five references, **all in
`tools/l1_split_prototype.py`** (:923, :944, :972, :974, :1089). Zero in `analysis/`, zero in
`tests/`.

**Does symitar's production skip fire on absence alone: CONFIRMED, at `:419-420`** (not `:421-422`
as cited — MINOR-1). `if not rows: continue` precedes the ratified `_yield_only` call at `:425`,
and `_yield_only` itself returns `False` for empty rows (`:329`), so the two skips are genuinely
distinct and the absence one is reachable only through `:419`.

**F4 — CONFIRMED at `community_section.py`:701-735**, the selection at `:731-734`
(`len(stmt.transactions) > len(best.transactions)`), and `parse_mission_valley_statement`
(`:682-691`) hardcoding `account_name="Business Checking"` and keying its account-number pattern
on that literal.

**F2 — confirmed in substance, wrong in mechanism and line (MAJOR-4).**

**The exact numbers Gustavo rules on.** Measured by executing each reader on the production
dispatch path over every one of its validated documents in the run of record:

| registration | validated documents | documents where the ABSENCE skip fires | sections skipped | content sha16 |
|---|---:|---:|---:|---|
| `symitar` | 7 | **4** | 7 | `0A14AC169DEA62D4`, `21643A62A463EA39`, `A4D0F58E054F8CFA`, `E07F381DC420725A` |
| `community_section` | 59 | **5** | 6 | `31F347BE1494314F`, `59DA140E7579A851`, `5F1CC8C0198DB4EB`, `C6E5B0D3EA9F857B`, `F627D7A6A057EF35` |
| `dakota_west` | 3 | **2** | 2 | `037774298FE1CD66`, `F748A799FDC7F25E` |
| `mission_valley` | 36 | 0 | 0 | — |
| **total** | **105** | **11** | **15** | |

Separately, F4's derived selection actually chose among two or more candidate sections on **1**
document: `4D15B2AC6493B82C` (`dakota_west`). All three `dakota_west` documents are therefore
implicated by S2 or S5, and §6.3 records that one `dakota_west` document is pinned.

**And the fact that decides Q8:** of the 15 skipped sections, **15 print evidence of their own
empty state** — symitar's 7 all carry the ratified declaration, and the other 8 each print an
opening balance, a closing balance coinciding to the cent, a zero credit total, a zero debit
total, a zero credit count and a zero debit count. **Applying R-a to the existing skips removes
0 validated documents.** The subtraction Q8 warns about does not exist; what exists is 11
documents whose skip must be re-founded on the evidence already printed, and a vocabulary that
must be widened to name it.

### (6) The staged delivery

**Independently provable: yes for S1, S3, S5, S6; not as written for S2 and S4.** S2's claim
("0 newly validated, payload movement on named documents, none pinned expected") is not
established (BLOCK-1 and the `dakota_west` pinned exposure). S4's proof plan is sound except that
its transfer killers are the 47 pairs, which are not the design's own rule's population
(BLOCK-4).

**"Surfaces before publisher" is correct, and the measurement that forces it is right** — this
review reproduced it and widened it from 6 readers to 11, 10 of which answer quietly. It is the
strongest single argument in the document, and the inversion of the card's suggested order is
justified.

**S4's "2 today / 8 if Q3" is reproducible** — `documents whose EVERY LOCATED section closes` 2,
`every section either CLOSES or is trivially idle` 8, both `FAM:guardian_cu_statement_summary`,
the table's closing column reproducing on 2 and on 8 respectively. All exact. **The same
instrument prints `... under the STRICTER test as well: 0` and the design does not carry it**
(BLOCK-2).

**CONS-HARDCODE's pinned movement is NOT stated exactly** — it is a disjunction, and it omits the
second `consumers` document (MAJOR-5). No per-account outcomes are given for the pinned document
under either branch, which is what "which account outcomes" asks for.

### (7) The `cohort_replay` blind spot and Ocean's `train9` fix

**The cell's measurement is confirmed**: adding a key whose value is `[]` to a real payload
changes the bytes on 30 of 30 documents and the base `leaf_diff` (worktree at `ac1d034`) reports
no change on 30 of 30.

**Ocean's fix on `train9` closes it.** `git show train9:tools/cohort_replay.py` carries, at
`flatten`:196-202, "An EMPTY container is a leaf too", emitting `<empty-list>` / `<empty-dict>`
and returning. Run against the same 30 pairs, the `train9` `leaf_diff` is blind on **0 of 30**.

Two notes for whoever uses it. First, the fix is broad: the baseline payloads already carry
**6,337** empty containers across those 30 documents (up to **577** in one), so the projection
now compares thousands of leaves it did not before — every cell's `--expect-identical` fidelity
run must be re-established at `train9` before it is treated as a control. Second, the byte-vs-leaf
gap is narrowed, not eliminated: `flatten` still compares an all-scalar list as a sorted multiset
(`:206-210`), deliberately, so a payload whose scalar-list ORDER changes still moves bytes and no
leaves. The design's rule — a BYTE comparison beside every payload-shape replay (§1.3, §6.4 item
3) — remains correct and should be kept even after the rebase onto `train9`.

### (8) W3, ownership, messages

**W3 is base + one appended section.** `git diff ac1d034 HEAD -- W3_TRACKA_LOG.md` is a pure
append at line 58857 (`@@ -58856,3 +58856,277 @@`); no earlier line is touched; the base's last
three lines are unchanged.

**Ownership is clean.** `git diff --name-status ac1d034 HEAD` is exactly: `A` the design,
`M` W3, `A` the four `tools/l1_design_*.py`. `git diff --stat ac1d034 -- analysis ocr webapp
discovery telemetry corpus_gate.py benchmark` is **empty**. Nothing outside `tools/` references
any of the four instruments. `tests/test_experiments_are_not_wired.py` passes and, as the design
says, guards only `experiments/` (`_IMPORT_RE` at `:24`) — the unwiring property is held by a
grep, which is disclosed rather than hidden.

**Messages are clean.** Re-scanned at the tip against the whole population:
**hit_count 0 over 8 commits**, MONEY / DIGITS / DATES / WORDS all 0. The branch's own record
(W3 L1D9) discloses that the scan was NOT clean the first two times and that the messages were
rewritten (`--msg-filter` over the whole branch, then one at the tip) — a disclosure that does
the card's standing rule credit rather than damage. I verified the rewrite left nothing dangling:
the only commit shas cited anywhere in the design or the W3 section are `ac1d034` (the base) and
`348663d`, both resolve on this branch, and `refs/original` is empty.

---

## 4. Proof floor, re-run by this reviewer

| proof | result | exit |
|---|---|---:|
| canonical guards, 5 files, with the four prototypes present | **255 passed** | **0** |
| `git diff --stat ac1d034 -- analysis ocr webapp discovery telemetry corpus_gate.py benchmark` | **empty** | — |
| instruments unwired (grep for `l1_design_` outside `tools/`) | none | — |
| ownership (`git diff --name-status ac1d034 HEAD`) | 6 files: 1 design, 1 W3 append, 4 `tools/` | — |
| branch privacy scan at the **tip** `8751d20` vs base `ac1d034`, whole population | **hit_count 0**; added_lines **2,401**; documents_read 3,351 of population 3,380 (29 with no cached text); MONEY 0 / DIGITS 0 / DATES 0 / WORDS 0; raw 29, all excluded by `words_class` | **0** |
| commit-message scan, `ac1d034..8751d20`, `tools/huntington_msg_privacy_scan.py` against the whole population | **hit_count 0** over **8** commits scanned; MONEY 0 / DIGITS 0 / DATES 0 / **WORDS 0** — the WORDS class is 0 even with the mandated co-authorship trailer on every message | **0** |
| the L1INV instruments re-run from the run of record | `l1_split_prototype` (both modes), `l1_structure_census`, `l1_design_idle_evidence` — EXIT=0 each; §1.1 is the ledger | 0 |
| the cell's own instruments re-run | `l1_design_payload_probe` (2 cohorts), `l1_design_reader_probe` — EXIT=0 each | 0 |

And this review's own commit, held to the same floor:

| proof | result | exit |
|---|---|---:|
| privacy scan of THIS review's added lines vs the whole population | **hit_count 0** over **741** added lines; MONEY / DIGITS / DATES / WORDS all 0; raw 12, all excluded by `words_class` | **0** |
| commit-message scan of this review's **2** commits | **hit_count 0**, all classes 0 | **0** |
| files touched by this review | one: `docs/moneythumb-replacement/reviews/BATCH9_L1DESIGN_REVIEW.md`. The reviewer's four instruments stayed in private scratch, unwired and uncommitted | — |

---

## 5. The rulings list, with this reviewer's opinion

**Q8 first, because the design says it is the only one that can subtract from 2,596 — and it
cannot.**

| | question | this reviewer's opinion |
|---|---|---|
| **Q8** | does R-a apply to the EXISTING absence-based skips (F1 / F2), which would move already-validated documents? | **Answer it YES, and it costs nothing.** Measured: the skips fire on **11** validated documents / **15** sections, and **15 of 15** print the evidence R-a demands — symitar's 7 carry the ratified declaration, the other 8 print an opening, a coinciding closing, zero totals and zero counts. The exposure is not "documents lost"; it is "11 documents whose skip is re-founded on printed evidence, and a vocabulary widened to name it". Q8 should go to Gustavo as a **measurement**, not as a risk. **Precondition:** L1-C17 gains a `printed_zero_activity_summary` member and a wording-independent dormancy member covering `zions._NO_ACTIVITY_RE` and `zions._inert` as well (BLOCK-1) |
| **Q3** | may a section be OMITTED when it prints its own opening and closing captions, the two coincide, and it prints no dated row, counts, totals or daily table? | **Grant it.** The evidence reproduces exactly: 6 sections on 6 documents, all with both figures from the section's own printed captions, 0 printing a row anywhere, counts, totals or a daily table. And Q8's measurement now shows the platform ALREADY relies on the same class of evidence one level up: 8 blocks with a printed opening, coinciding closing and zero counts. Granting Q3 and widening L1-C17 are the same act. Worth 2 → 8 documents, all `FAM:guardian_cu_statement_summary` |
| **Q2** | must a transfer's counterpart be on the SAME document; does ambiguity refuse the aggregation or the document? | The design's answers (yes; aggregation only) are right, but the prior question is unasked: **may an arithmetic coincidence set INTERNAL at all with nothing printed?** This reviewer says no — require a printed designation on at least one leg, or refuse the aggregation. Measure how many of the 47 pairs carry one before ruling (BLOCK-4) |
| **Q1** | does a partially-closing document publish the validating account's figures? | Rule with the package question attached: whatever the payload publishes, **a package member must be an account whose own outcome is `validated`, or the document refuses aggregation**. Today `_package_analysis` gates on nothing but job status, so "publish and mark it `withheld`" silently means "aggregate it anyway" (§3, answer (4)) |
| **Q5** | does each account enter a package as its own member; is the ADB doctrine's unit the account? | The account reading of the doctrine is forced by R-c and is right. But accounts-as-members makes `package_average_daily_balance` a combined average over one document's accounts — say explicitly whether that is permitted (MAJOR-3) |
| **Q4** | two denominations: publish two accounts or refuse? | Either is consistent with R-f; ruling it needs the missing rung first — a document-level printed currency statement must outrank a jurisdiction or institution default (MAJOR-6) |
| **Q6** | whose period, where an issue prints per-account ranges? | Unmeasured by anyone; the design correctly refuses until ruled. No objection |
| **Q7** | is a posting section one dated row or two? | The design's own tables give both (86 / 81 and 59 / 111) and note the 2 documents close at both. Low stakes for S4, high stakes for L1-C4's meaning (MINOR-7) |

**And one ruling the design does not ask for and should:** whether the honest expected-recovery
range Gustavo is deciding against is **2–8** or **0–8** (BLOCK-2).

---

## 6. What must change before implementation cards are cut

1. Widen L1-C17's vocabulary to the evidence the archive prints, and re-state S2's expected
   movement as 0 validated lost / 11 re-founded / 15 surfaced, with the `dakota_west` pinned
   document named. (BLOCK-1)
2. Carry `all_close_strict = 0` into §2.6 and §7 beside the 2 and the 8, with the instrument's own
   reason for why the strict bound over-counts. (BLOCK-2)
3. Complete the payload-reader census (11, not 6) and the `analyze_markdown`→`report_to_dict`
   seam census (9 sites, 4 unnamed, 2 mis-cited) in §1.4 and §5, and make S3's exit criterion a
   list. (BLOCK-3)
4. Move the transfer identification's printed-evidence question into §8 as a ruling, and
   re-measure the 47 under §3.3's own fail-closed rule and a document-wide one-to-one match.
   (BLOCK-4)
5. Resolve L1-C18 against §5's "the FIRST account's". (MAJOR-1)
6. Re-scope S1's proof to the pipeline seam and the `assess_document_integrity` scope split, not
   the serialiser alone. (MAJOR-2)
7. Rule the package-ADB question in Q5 and the package-membership rule in Q1. (MAJOR-3, answer (4))
8. Correct F2's site to `community_section.py:621-622` and F1's to `symitar.py:419-420`.
   (MAJOR-4, MINOR-1)
9. State CONS-HARDCODE's movement as 2 validated → failed (one pinned) on a correctness argument,
   with both audit-CSV paths re-derived. (MAJOR-5)
10. Add the document-level printed-currency rung to §4's hierarchy. (MAJOR-6)

Nothing above requires the checkpoint ruling to be re-opened, and nothing above changes the
architecture. The design is the right shape; it needs its own measurements carried into it.

---

# Re-review — the closure

Same reviewer, same method: nothing was taken on the closure's word. Branch `wave9-l1design`,
base `train9` `ac1d034`, review tip `0574f4e`, closure tip **`1113ce5`** (13 closure commits,
23 in total). Every claim below was re-measured at `1113ce5` against the same run of record and
the same read-only cold cache.

**VERDICT ON THE DESIGN: SOUND WITH FINDINGS — 0 BLOCK / 1 MAJOR / 3 MINOR.**

All four BLOCKs and all six MAJORs of the first review are closed, and closed at the root rather
than argued with. Every number the closure claims reproduces, to the digit, including the three
it corrected itself on. The one new MAJOR is in the clause that closed BLOCK-4: the rule is
right and the vocabulary it is founded on is not.

**Implementation cards S1, S2 and S3 may be cut now. S4 may not** — its named killer population
is the thing the new MAJOR is about. S5 waits on Gustavo (a `validated -> failed` pair).

## RR-1. Re-measurement of the closure

| closure claim | claimed | this re-run at `1113ce5` | agrees |
|---|---|---|---|
| **BLOCK-1** skip probe, on the dispatch path | 117 read / **12** documents / **16** sections | 117 / **12** / **16** | **yes** |
| ... per registration | symitar 7·4·7, community_section 59·5·6, dakota_west 3·2·2, mission_valley 36·0·0, zions 12·1·1 | identical, row by row | **yes** |
| ... by skip SITE | symitar `:419-420` 7; community_section `:621-622` **8**; the `:984` call-site clause **0**; zions `_inert` 1 | identical | **yes** |
| ... evidence classes | declaration **8** (7 symitar, 1 zions), zero-summary **8** (6 community_section, 2 dakota_west), `no_printed_evidence` **0** | identical | **yes** |
| ... the zero-summary's seven clauses | 8 of 8 on every clause | 8 of 8 on every clause | **yes** |
| **BLOCK-2** `all_close_strict` carried; range 0-8; Q9 opened | 0 / 2 / 8 | §2.6 and §7 carry all three; Q9 asks which is the planning figure | **yes** |
| **BLOCK-3** reader census | 6 -> **11** (10 probed: **9 quiet, 1 loud**) | 10 probed, **1** loud (`balance_forensic_audit`, KeyError), **9** quiet, **0** refuse the shim | **yes** |
| **BLOCK-3** seam census | 9 declared, 0 missing, 0 undeclared, exit 0 | 9 / 0 / 0, **exit 0**, and the 9 are exactly the tree's | **yes** |
| **BLOCK-4** designation required; 46 of 47 carry one | 46 / 1 | **46 / 1** | **yes** |
| **BLOCK-4** three pairing rules agree; 0 ambiguous; 3 documents with 3+ ledgers | 47 / 47 / 47, 0, 3 | **47 / 47 / 47**, **0** ambiguous, **3** with 3+ live ledgers, 0 sections without printed text | **yes** |
| **MAJOR-2** cohort and the integrity split | 232 docs / 80 registrations; order-preserved 232/232; naive 232/232; literal reading moves 3 | 232 / 80 (71 validated at baseline); **232 / 232 / 229** — the literal reading moves exactly **3** | **yes** |
| ... and RULE S over the widened cohort | 232 byte-identical | 232 byte-identical; `wrapper_unconditional` 0; `omission_field_always` 0 with a leaf gap of **232**; `omission_field_elided` 232 | **yes** |
| **MAJOR-4** the site numbers | `:984` 0, `:621-622` 8, symitar `:419-420` | reproduced by the probe, and the watched line at `symitar.py`:420 is literally `continue` | **yes** |
| **MAJOR-5** CONS-HARDCODE | 2 validated -> failed, 1 pinned, both audit paths | §6.3 and the S5 row state exactly that, with `-2 validated` in the count column and STOP-and-report | **yes** |
| **MAJOR-1 / 3 / 6** | empty per-document field + `account_count`; no average over two members sharing a content digest + member must be `validated`; the document-level currency rung with full precedence | all three present, with the precedence written out strongest-first | **yes** |
| privacy scan, added lines vs the whole population | 0 over 4,950 | **hit_count 0** over **4,950** added lines, 3,351 documents read; MONEY/DIGITS/DATES/WORDS all 0; raw 71, all `words_class` | **yes** |
| commit-message scan | 0 over 23 | **hit_count 0** over **23** commits, all classes 0 | **yes** |
| canonical guards | 255 | **255 passed, EXIT=0** | **yes** |
| production diff | empty | `git diff --stat ac1d034 1113ce5 -- analysis ocr webapp discovery telemetry corpus_gate.py benchmark` **empty** | **yes** |
| ownership / W3 | 9 files; W3 = base + section + closure, 0 deletions | 9 files (design, W3, this review, 6 `tools/`); W3 **+457 / -0** vs base, and the base blob is a **byte-exact prefix** of the closure blob, as is the review tip's; the closure appended `## §L1DESIGN.2` (183 lines) under the cell's own section | **yes** |
| instruments unwired | 6, all unwired | grep: nothing outside `tools/` references any of the six | **yes** |
| cited shas resolve | `348663d` still resolves | **six** shas are cited (`ac1d034`, `348663d`, `0574f4e`, `d850ae6`, `6af1d95`, `7755665`); all six resolve; five are on this branch and `7755665` is Ocean's `train9` commit carrying the `cohort_replay` fix, cited deliberately | **yes** |

## RR-2. The zeros, tested for vacuity

A zero is only a finding if the instrument that produced it could have produced something else.
Three of the closure's load-bearing zeros were tested directly.

**`no_printed_evidence` = 0.** `classify_evidence` was run against nine constructed fixtures —
invented figures, the committed patterns' own wordings, nothing from the archive:

| fixture | expected | got |
|---|---|---|
| absence only — a heading and nothing else | `no_printed_evidence` | **as expected** |
| absence only — an empty grid header, no summary | `no_printed_evidence` | **as expected** |
| the symitar declaration wording | `printed_dormancy_declaration` | **as expected** |
| the zions declaration wording | `printed_dormancy_declaration` | **as expected** |
| a printed ZERO-activity summary, all seven clauses | `printed_zero_activity_summary` | **as expected** |
| a summary that printed ACTIVITY (one credit) | `no_printed_evidence` | **as expected** |
| a summary whose pair does not coincide | `no_printed_evidence` | **as expected** |
| a summary with a zero pair but a non-zero debit total | `no_printed_evidence` | **as expected** |
| a summary missing its second balance row | `no_printed_evidence` | **as expected** |

**9 of 9**, including the five that must be REFUSED. The class R-a refuses is reachable, and a
section that printed activity does not reach the admitting classes. The 0 is real. This is also
the constructed absence-only fixture the re-review was asked for, and the design may cite it.

**The watched lines.** `verify_sites()` returns clean at this tree; moving one watched line by
`+1` produces *"analysis.symitar:421 does not contain 'continue'"* and moving it past EOF is
caught too. A refactor cannot turn this probe's counts into a silent zero.

**The seam census.** It holds at this tree (9 found, 0 missing, 0 undeclared, exit 0). Doctored
in both directions it fails as designed: a declared-but-absent seam -> **exit 1**; a
present-but-undeclared seam -> **exit 1**; unmodified -> **exit 0**. It is a real `git grep` over
the tracked tree, not a static list, so S3's exit criterion is checkable rather than asserted.
(One residual, not a finding: `git grep` sees tracked files only, so a seam added in an
untracked file is invisible until it is added.)

## RR-3. The one new finding

### RR-MAJOR-1 — the transfer clause is founded on a vocabulary that includes third-party payment rails, and three of its 46 designated pairs are admitted by `VENMO`

BLOCK-4 is closed by the right rule: *the paper must PRINT a transfer designation on at least
one of the two legs.* The designation is decided by
`tools/l1_design_transfer_probe.py::prints_transfer_designation`, which ORs two production
vocabularies. They are not the same kind of thing.

* `_INTERNAL_TRANSFER_CREDIT_PATTERNS` (`transaction_classifier.py`:433-465, 13 patterns) names
  movement between a member's OWN accounts: `TRANSFER FROM <CHECKING|SAVINGS|SHARE|...>`,
  `SH TO SH`, `ACCOUNT TO ACCOUNT`, `TRANSFER FROM <masked account> TO <masked account>`. This
  is the right vocabulary for the clause.
* `_TRANSFER_PATTERNS` (`:300-308`, 7 patterns) is used in production at `:976-981` as a
  **`strong_non_lender_exclusion`** — it answers "this row is not a lender debit", not "this row
  is an internal movement" — and it contains `ZELLE`, `VENMO`, `CASH APP`, `E TRANSFER`,
  `ETRANSFER`, `XFER` and `ONLINE TRANSFER`. The first three are third-party peer-to-peer rails
  by definition; `E TRANSFER` on the Canadian issuers this archive carries is an Interac
  transfer, which is ordinarily a payment from someone else.

**Measured over the same 47 pairs, splitting the 46 by which vocabulary fired:**

| which vocabulary admitted the pair | pairs |
|---|---:|
| the INTERNAL vocabulary alone | **41** |
| both | 2 |
| **the GENERIC vocabulary alone** | **3** |
| neither — the clause's live killer | 1 |

**All three generic-only pairs are admitted by `\bVENMO\b`**, and all three are on one document
(`A137F6D65E29CAD5`). The internal vocabulary's own hits come from
`TRANSFER|XFER|TFR FROM <own-account class>` (43 pairs) and the branch/online/mobile
`TRANSFER FROM <account>` pattern (9) — both genuinely internal.

A Venmo row is a payment to or from another person. Treating it as printed evidence that money
moved between the member's own accounts flags the pair INTERNAL and then removes the matching
deposit from package gross deposits, deposit counts, revenue and the withholding denominator —
**which is exactly the failure the clause was added to prevent, re-admitted through the
vocabulary it was founded on.** The design's own words for it apply unchanged: *money the paper
printed, deleted from a funder's view of the business by an inference.*

**The fix is small and the design already holds the right vocabulary.** Found the clause on
`_INTERNAL_TRANSFER_CREDIT_PATTERNS` alone (or on a designation vocabulary of its own that names
internal movement, justified as such). Re-measured under that reading the cost is **43
designated / 4 undesignated of 47** — still four pairs on two documents, still small, and the
rule then says what it means. Until it is settled, S4's stated killer population ("the 46
designated pairs ... as the package exclusion's named killers") contains three killers that
should be refusals.

### RR-MINOR-1 — the 46 sit on six documents, not seven

S4's proof column reads "the **46** designated pairs on **7** documents". Per document the
designated counts are 27, 7, 5, 3, 3, 1 and **0** — the seventh document (`2A8F1A9D95DD0672`)
carries the single undesignated pair and contributes none of the 46. The population is 7
documents / 47 pairs (L1-C11's cell says this correctly); the *designated* population is
**6 documents / 46 pairs**.

### RR-MINOR-2 — "at least one leg" is doing almost all the work, and that is worth recording

Of the 46 designated pairs, **45 are designated on ONE leg only** and 1 on both. The clause's
"at least one of the two legs" is therefore not a formality — it decides 45 of 46 pairs on the
words of a single printed row, which is also why RR-MAJOR-1's choice of vocabulary matters as
much as it does. It belongs beside the 46.

### RR-MINOR-3 — the four unkillered conditions are not one class, and the design flattens them

The closure states plainly that four of eighteen have no measured killer and owes each a
constructed fixture. Right, and the honesty is welcome — but the four are in three different
situations, and an implementer reading "each needs a constructed fixture" will build one thing
where two are wanted and none is:

* **`L1-C15`** (zero inference, deterministic, $0) is a standing property already enforced by
  the batch rule and by the registry / experiments guards. It needs no fixture of its own.
* **`L1-C14`** (no statement-specific constant) already HAS a live killer in the canonical 255:
  `tests/test_no_statement_hardcodes.py`. What it lacks is a killer that catches the instance
  the design itself measured — `consumers.py`:90. Its fixture is an EXTENSION of an existing
  guard, and it is the extension S5 needs anyway.
* **`L1-C2`** (disjoint sections, complete coverage) and **`L1-C18`** (no chosen account), plus
  **`L1-C11`'s ambiguity branch**, genuinely need constructed fixtures. C18's is cheap — a
  two-account payload and an assertion that every per-document single-value field is EMPTY — and
  belongs in S3, where the surfaces learn the rule. C2's needs a synthetic document with a
  duplicated section. C11's needs a synthetic posting with two admissible counterparts.

## RR-4. The question asked: must the four unkillered conditions be measured now?

**No — a design may name a condition it cannot yet kill, provided it says so, and this one now
does.** Two qualifications, and they are the difference between an owed fixture and a lost one:

1. **The fixture is a gate on the card that writes the condition, not a backlog item.** The
   design already says "the card that writes the condition owns building one"; it should also
   say that the card's mutation table is not accepted without it. A mutation table whose killer
   is a citation is the failure mode the batch rules already name ("a test named after a gate is
   not a test of that gate"), and the way it slips through is a card closing on the strength of
   the other seventeen.
2. **The four should be split as RR-MINOR-3 sets out**, so that C15 is not "owed" anything,
   C14's owed work is scoped as extending an existing guard, and the three that genuinely need
   construction are named as three.

Measuring them now would mean building three synthetic documents inside a design cell that owns
no test wiring — which is the wrong cell for it. The population that decides whether the
conditions are RIGHT is measured; the fixtures that decide whether they are ENFORCED belong with
the code.

## RR-5. Rulings, Q8 and Q9 first

| | question | this reviewer's opinion |
|---|---|---|
| **Q8** | does R-a apply to the EXISTING absence-based skips? | **Answer it YES; it costs nothing, and that is now measured twice.** The closure's probe reports 12 documents / 16 sections / **0** with no printed evidence, on the dispatch path, with the watched lines verified and the refusing class shown reachable by nine constructed fixtures. My own independent instrument, written before `zions` was probed by anyone, reported 11 documents / 15 sections with the same per-registration split — the difference is `zions`, which the closure added. **Q8 goes to Gustavo as a measurement, not a risk**, and the only work it creates is re-founding 12 documents' skips on evidence already printed |
| **Q9** | which point of 0 / 2 / 8 is the planning figure? | **Plan against 2; report 0-8; judge S4 against 2, or against 8 if Q3 is granted.** **Not 0**: the strict after-chain bound counts any printed date-plus-figure as an unaccounted row, and the instrument's own docstring (`l1_split_prototype.py`:528-537) says the last section of a document runs to the end of the page and carries its trailing tables — so the 0 refuses work the production validator accepts. **Not 8 by default**: that is Q3's to grant. **2** is what `reconcile`, the ADB and `posting_dates_cover_source` actually accept today, which is the standard every other batch-9 number is measured against. Carry 0 in the same table as the reason it is pessimistic — which the closure now does |
| **Q3** | may a section printing its own coinciding opening and closing, with no row, be OMITTED? | **Grant it.** The closure strengthens the case rather than restating it: the platform already relies on the same evidence class one level up — 8 sections whose printed summary shows an opening, a coinciding closing, and zero totals AND zero counts — and granting Q3 is the same act as the C17 widening that keeps 12 protected documents. Worth 2 -> 8, all one census family |
| **Q1** | publish the validating account's figures, or refuse? **And is a package member an account whose own outcome is `validated`?** | Rule the second half explicitly and YES. The design's answer is right and the reason is measured: `_package_analysis` gates on job status alone (`webapp/app.py`:661), so "publish it and mark the document `withheld`" silently means "aggregate it anyway" |
| **Q2** | same-document counterpart; ambiguity refuses the aggregation or the document? | Both of the design's answers are right. **But settle RR-MAJOR-1 first** — the designation vocabulary decides 45 of 46 pairs, and three of them on a third-party rail. Ambiguity refusing only the aggregation is correct and its killer is a constructed fixture (0 in the archive) |
| **Q4** | two denominations: two accounts or refuse? | Rule after the new document-level rung's population is measured — the design says an implementation card owns measuring it, and that ordering is right. The two-denomination class is 4 documents / 12 sections |
| **Q5** | each account a package member; is the ADB doctrine's unit the account? | Yes to both, and the mechanism the closure chose is the right one: forbid the ARITHMETIC (no published average over two members sharing a `content_sha256`), not the field name |
| **Q6** | whose period where an issue prints per-account ranges? | No objection; refuse until ruled. Unmeasured by anyone, correctly |
| **Q7** | one dated row or two? | Rule at **two**, which is what every table in the packet, the design and the closure uses. Low stakes for S4 (the 2 close at both) and high for what L1-C4 means |

## RR-6. May S1-S3 be cut now?

**Yes, all three.**

* **S1 — the wrapper and RULE S.** The claim has moved off the serialiser, where it was near
  enough a tautology, onto the seam it is offered against. The assembly rule is named (published
  order), the three assemblies are measured (232 / 232 / 229), the literal reading's cost is
  sized at 3 of 232, and the reason order must be preserved is a pinned tuple at
  `corpus_gate.py`:1360-1362 rather than a cohort that happened to pass. Nothing in RR-MAJOR-1
  touches it. **Cut it.**
* **S2 — SIBLING-OMISSION-SURFACE.** The population is measured on the dispatch path, the
  evidence is measured section by section, the vocabulary can name all of it, and the pinned
  exposure is stated as an exposure rather than as "none". **Cut it, with one thing owed at the
  card:** name which of the three `dakota_west` documents is the pinned one before the card
  claims no pinned movement.
* **S3 — the surfaces, taught DARK.** Both censuses are complete and, more importantly,
  checkable — the seam census fails in both directions when doctored. **Cut it, with one thing
  owed at the card:** L1-C18's constructed fixture (a two-account payload, every per-document
  single-value field asserted EMPTY), because S3 is where the surfaces learn that rule.

**S4 may not be cut yet.** Its named killer population is "the 46 designated pairs", three of
which are admitted by `VENMO` (RR-MAJOR-1) and one of which is a document-count error
(RR-MINOR-1). Settle the designation vocabulary, re-measure, and S4 is ready.

**S5 waits on Gustavo.** It is a `validated -> failed` on two protected shas, one pinned; the
design now states it as one and asks for the ceremony, which is the right place for it to stop.

## RR-7. Proof floor of this re-review

| proof | result | exit |
|---|---|---:|
| canonical guards at `1113ce5` | **255 passed** | **0** |
| production diff `ac1d034..1113ce5` over `analysis ocr webapp discovery telemetry corpus_gate.py benchmark` | **empty** | — |
| W3 append-only | base blob is a **byte-exact prefix** of the closure blob; `+457 / -0` vs base | — |
| branch privacy scan at `1113ce5` | **hit_count 0** over 4,950 added lines | **0** |
| commit-message scan `ac1d034..1113ce5` | **hit_count 0** over 23 commits | **0** |
| the closure's instruments, re-run | skip, transfer, payload, reader (+ `--census`) — EXIT=0 each | 0 |
| this reviewer's re-review instruments | the C17 fixture set (9 cases), the vocabulary split over the 47 pairs, the census failure-path test, the watched-line failure-path test — all in private scratch, unwired, uncommitted | — |
| files this re-review adds to the tree | one: this section of `BATCH9_L1DESIGN_REVIEW.md` | — |
| privacy scan of THIS section's added lines vs the whole population | **hit_count 0** over **240** added lines; MONEY / DIGITS / DATES / WORDS all 0; raw 14, all `words_class` | **0** |
| commit-message scan of this re-review's commit | **hit_count 0**, all classes 0 — **and it was not 0 the first two times.** Three ordinary English word-pairs, then one more, matched printed text and the WORDS class caught them; the message was reworded twice and re-scanned after each, which is the standing lesson the design cell recorded and this reviewer has now paid as well | **0** |
