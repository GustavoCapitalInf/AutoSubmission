# BATCH9 PNC-LAYOUTS — independent adversarial review

Branch `wave9-pnc`, base `train9` `93c6132`, tip `ddc5702` (11 commits). Reviewer did not
write this cell and asked it nothing. Every number below was re-measured in the reviewer's
own detached worktrees (`pnc9rev/base` at `93c6132`, `pnc9rev/tip` and `pnc9rev/mut` at
`ddc5702`) so that the cell's own worktree was never disturbed while its detached proofs
were still running.

**VERDICT: APPROVE WITH FINDINGS.** Newly validated 13 by sha; 41/41 preserved with every
changed leaf classified and proven; the three withheld→failed refusals correct; validated
regressions 0; doctrine kept; privacy 0; and the two floor rows the cell left open — the
corpus-marked slice and the archive sweep — are now COMPLETE. Findings are three MINORs and
three NOTES; none blocks composition.

---

## 1. Re-measurement table

| # | measure | cell's claim | reviewer's measurement | matched? |
|---|---|---|---|---|
| 1 | `cohort_replay` at base, target 17, `--expect-identical` | 17 unchanged, payload changed 0, exit 0 | 17 unchanged non-validated, payload changed 0, **exit 0** | YES |
| 2 | `cohort_replay` at base, `--parser pnc`, `--expect-identical` | 45 replayed, preserved 41/41, payload identical 41, exit 0 | 45 replayed, preserved **41/41**, payload **identical 41**, **exit 0** | YES |
| 3 | `cohort_replay` at tip, target 17 | newly validated 13, up 0, unchanged 1, validated regressions 0, other ladder regressions 3 | newly validated **13**, up 0, unchanged non-validated 1, validated regressions **0**, other ladder regressions 3, exit 0 | YES |
| 4 | the 13 newly validated, by sha | the 13 named in §PNC9.5 | set equality with the named 13: **True** (symmetric difference empty) | YES |
| 5 | `cohort_replay` at tip, `--parser pnc` | 45 replayed, preserved 41/41, payload changed 41, newly validated 1, regressions 0 | 45 replayed, preserved **41/41**, payload changed 41, newly validated 1, validated regressions **0**, exit 0 | YES |
| 6 | the changed leaf PATHS over the 41 | only the ladder trio and `account_name` on 2 | **14 distinct leaf paths, all inside the two claimed classes**; set difference against the claimed classes is EMPTY | YES |
| 7 | no balance / ADB / metric / transaction leaf moved | claimed | `metrics.adb.daily_balances[*].ending_balance`, `underwriting_adb`, every `statement.transactions[*]` money/date/description leaf, `beginning_balance`, `ending_balance`, `stated_total_*`, `period_*`, `account_number`, `currency`: **absent from the changed set** | YES |
| 8 | `account_name` corrected on 2 | `6E89A8586805241B`, `B2217059EA40E360` | exactly those two | YES |
| 9 | withheld → failed ×3 | `1F31588B36B2E4AF`, `5684857C24B79344`, `BE703D525955253C` | exactly those three | YES |
| 10 | mutation table | 18 mutants, 18 killed, 0 survived | **18 mutants · 18 killed · 0 survived · exit 0**, tree verified clean before AND after, `analysis/pnc.py` byte-identical to HEAD afterwards | YES |
| 11 | identity ceiling, five modes | validated 1 in every mode | validated **1** in `as_is`, `no_index`, `no_ladder`, `all_identities`, `ordered_dates`; under `all_identities` the three refusals return to `withheld/withheld_adb` | YES |
| 12 | `pnc_claim_delta` over 3,380 | claimed then and now 45, newly claimed 13, taken from another reader 0 | 45 / 13 / **0**, no_text 29, untouched 3,293, exit 0 | YES |
| 13 | canonical guards (5 files) | 255 | **255 passed** | YES |
| 14 | canonical conformance (7 files) | 1,270 | **1,270 passed, 40 skipped** | YES |
| 15 | full default suite | 7,329 passed, 3 failed (inherited), 43 skipped, 34 deselected | **7,329 passed, 3 failed, 43 skipped, 34 deselected**; the three are exactly the excused `test_core_processor_enclosures.py` trio | YES |
| 16 | corpus gate GREEN 105/3/1 | measured at `112002f` | **GREEN at the TIP** — see §3.7 | YES |
| 17 | corpus-marked slice | **NOT RETURNED** | **COMPLETED: 30 passed, 7,379 deselected, EXIT=0** | COMPLETED |
| 18 | archive sweep at the tip | **NOT RETURNED** (chunk A only, later) | **COMPLETED over all 3,380** — see §2 | COMPLETED |
| 19 | privacy, added file lines | 0 over 2,678 lines | **hit_count 0** over **2,685** added lines, 58 documents read; MONEY/DIGITS/DATES/WORDS all 0; raw 54, every one WORDS-class ordinary English | YES |
| 20 | privacy, commit messages | 0 in every class over 10 commits | **0 in every class** over **11** commits | YES |
| 21 | ownership | only the card's files | vs the TRUE base `93c6132`: `analysis/pnc.py`, `tests/test_pnc_layouts.py`, `tests/test_pnc_variants.py`, five `tools/pnc_*.py`, W3 — **nothing else** | YES |

Two apparent out-of-card edits (`tests/test_core_processor_enclosures.py`,
`BATCH9_TRANSITION.md`) are an artefact of diffing against the *moved* `train9` head, not
against the branch's base; against `93c6132` the branch is clean. `train9` has since
advanced by `68c7ea8`, `2c3f834`, `b20993d`.

---

## 2. The archive sweep, completed (the row this review owns)

The cell launched chunk A only and it had not returned when the cell reported; chunk B was
never launched. The reviewer ran chunk B `[1700,3380)` at the tip in a private worktree and
combined it with the cell's completed chunk A.

| chunk | range | documents | compared | identical | moved | no_payload_now_publishes | payload_now_raises | no_payload_raises_again | no_ocr_artifact | seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A (cell) | [0,1700) | 1,700 | 1,341 | 1,316 | 23 | 9 | 2 | 339 | 11 | 2,233 |
| B (reviewer) | [1700,3380) | 1,680 | 1,328 | 1,308 | 19 | 12 | 1 | 322 | 18 | 2,064 |
| **whole archive** | **[0,3380)** | **3,380** | **2,669** | **2,624** | **42** | **21** | **3** | **661** | **29** | — |

**66 findings, and every one is accounted for.**

* **57 are inside the card's named 58-document population** and reconcile exactly to what the
  card claims: `moved` 42 = the 41 preserved (ladder publication, plus `account_name` on two)
  + `4145E2C82C6B8329` (withheld → validated); `no_payload_now_publishes` 12 = the twelve
  newly validated documents that had no payload before; `payload_now_raises` 3 = the three
  named refusals.
* **9 are outside the population**, all `no_payload_now_publishes` from `failed`:
  `0943986A52D8226C`, `373B73F98E63F900`, `6E9A3A110E6829EB`, `75FE7191FD4E74A0`,
  `889DAEBE7D79133C`, `BD835DA79B01B332`, `C355B3706588F0B1`, `C47BEFE559CB8600`,
  `D31770634E04E104`. These are **not attributed, they are proven**: the reviewer re-ran the
  same sweep at the BASE `93c6132` over each one's own single-document index range, and
  **all nine reproduce the identical verdict at the base**. They are `train9`'s
  already-composed CP-DECLINES movers (whose own record names nine), surfacing because the
  sweep's baseline is the batch-8 run of record, not the branch base. This branch adds none.

**Zero movement outside the named population.**

---

## 3. The hostile questions, answered with evidence

### 3.1 The ladder publication and the ADB (Q1) — the gate is load-bearing, and proven so

`analysis/adb.py` overrides the walked carry with a printed cell where one exists
(`if day in snapshot_map: carry = snapshot_map[day]; source = "bank_daily_summary"`), and the
override PERSISTS into later days. So publishing a ladder is only safe if the printed cells
already equal the walk. Three independent confirmations that they do:

1. **Structurally.** `_matches_the_printed_grid` requires `walked[iso] == grid[iso]` within
   half a cent for every printed day, and refuses a cell outside the period. The reader's
   walk and the ADB engine's walk are the same walk: the ADB opening is
   `stmt.beginning_balance` (the reader's `beginning`) unless an initialization event exists,
   and PNC never sets `initialization_transaction_count`; `transactions_within_period` is a
   required check, so no row falls outside the walked span.
2. **Measured.** Over the 41, `metrics.adb.daily_balances[*].ending_balance` and
   `underwriting_adb` are **absent from the changed-leaf set** — the ADB is identical to the
   cent on every one. Only `daily_balances[*].source` changes (821 leaves), on exactly the 821
   days the ladder prints.
3. **The fixture asked for.** Built and driven through the real parser:

   | fixture | verdict |
   |---|---|
   | ladder disagrees by ONE CENT on a middle day | **DECLINED** |
   | ladder disagrees by ONE CENT on the LAST day | **DECLINED** |
   | a ladder day the ledger never moved on, wrong balance | **DECLINED** |
   | the same day, right balance | published, ladder admitted |

   And the gate is not decorative: with `_matches_the_printed_grid` patched to `True`, the
   one-cent document publishes and `underwriting_adb` **moves by a cent while `adb.ok` stays
   `True`** — no other check in the platform sees it. The ladder gate is the only thing
   standing between a mis-printed ladder and a wrong published ADB. That is the strongest
   possible answer to "is the publication safe": it is safe *because of* the gate.

Doctrine: the ADB stays one calendar-day ADB over the printed period; the printed ladder is
day-level bank EVIDENCE (an established platform surface), not a bank AVERAGE, so the
evidence-only rule for bank averages is untouched.

### 3.2 The two `account_name` corrections (Q2) — the ATB-LABEL precedent, applied in the correcting direction

The base published `account_name="Business Checking"` as a **literal, on every document,
whatever the page said**. That is precisely the ATB-LABEL shape (a product name hardcoded as
`account_name`), and this card REMOVES it. The new value is read from the page:
`_product()` keeps only products that satisfy `product in markdown` and returns the
**earliest** occurrence, so the published string is a substring of the document at a known
offset.

Census over all 58: **the earliest printed product name is on line 6 in 58 of 58 documents** —
the masthead — and only 2 documents print more than one product name, which are exactly the
two corrected. The rule is corroborated by the whole population, and the four-name list is
institution vocabulary (PNC's own printed product titles), not a statement-specific literal:
no document identity is keyed on it, the repo's own R-1 and statement-hardcode guards pass
(255), and a fifth skin the list cannot name is **left unclaimed rather than published under a
guess** — driven and confirmed (a synthetic "PNC Growth Advantage Checking" statement
DECLINES). The list is detection furniture and a read vocabulary; it is never written into a
payload field except as read from the page.

*Note, not a finding:* the rule is positional. A synthetic document printing a product name
ABOVE its own title publishes the wrong `account_name` — no such document exists in the
population, and detection would still require the title.

### 3.3 The three withheld → failed (Q3) — each refusal is right

Recomputed per document (counts only; no value printed):

| sha16 | printed index categories | reproduced exactly | sections itemized the index does NOT print | ladder cells | ladder identity |
|---|---:|---:|---:|---:|---|
| `1F31588B36B2E4AF` | 3 | 2 | 0 | 8 | **False** |
| `5684857C24B79344` | 11 | 0 | 0 | 3 | **False** |
| `BE703D525955253C` | 8 | 0 | **1** | 0 | not applicable (no ladder) |

Each fails a printed identity, and in each case the document — not the reader — is the reason:
the first has a cheque section whose heading and column header the text layer carries with no
row beneath them while the index claims an item; the other two have a detached row date
column. `BE703D` is additionally refused for itemizing a whole section its own index excludes
— which matches the ceiling exactly (`no_index` returns `BE703D` to `withheld` and nothing
else). Before this card the reader was publishing, on all three, a ledger the bank's own
index contradicts. The refusals cost no validated coverage: under `all_identities` all three
return to `withheld/withheld_adb`, which is where they were.

**The contamination claim is CONFIRMED, by hash, values never printed.**
`5684857C24B79344` (period Feb) prints 18 distinct figures in its ladder region;
`BE703D525955253C` — the same account number, **two months later** (period Apr) — prints 15,
and **15 of the target's 18 are shared**. Neither the target's own printed beginning nor its
own printed ending appears anywhere in its ladder region. The cell's finding stands as
written.

### 3.4 The mandatory identities (Q4) — strictly additional, never vacuous where it matters

Both identities are **conditional**, and the reviewer drove both vacuity paths:

* a document printing **no index** publishes with the Balance Summary as its only row oracle;
* a document printing **no readable ladder** publishes with no misdating control at all
  (driven: a row moved to the wrong day publishes when neither identity is printed, and is
  refused by the ladder alone when only the ladder is printed).

That is a bound worth stating, but it is **not a weakening**: at the base neither identity
existed, so every path has at least as many checks as before and none has fewer. And on this
population neither is vacuous on any document the reader publishes:

* **58 of 58 print an index** (table form only 50, restatement form only 4, both 4, **neither
  0**); `_printed_index()` is non-empty on all 58;
* the only two documents with **no readable ladder** are `31E43C6F9393CA15` and
  `BE703D525955253C` — **both refused**. Every one of the 54 published documents (41 preserved
  + 13 movers) has both identities applied.

A ladder printing one day twice with different balances returns `None` and DECLINES (not
"last cell wins"), and a cell outside the printed period fails the document — both driven, and
both killed as mutants (M6, M7).

### 3.5 The C0 control byte (Q5) — one MINOR, with the exposure measured at nil

What replaces `\s` is not a widened grammar: the heading grammar uses `_H = [^\S\n]`
(horizontal whitespace, so a heading still owns one line), and the C0 byte is **normalised to
a space at the reader's entry**. Driven: TAB and NUL continuation separators both open the
section; a form feed standing where a line separator belongs is harmless.

**The stated justification is false in one direction** (FINDING 1, MINOR). The docstring
claims "a space can only separate two tokens, never join them". It can join them: this
codebase treats a space between digit groups as a **thousands separator**
(`_THOUSANDS_SPACE`). Driven — a summary grid whose beginning column is printed as
`digit <control byte> three-digit-group . cents` reads as ONE figure after normalisation and
the document publishes, where with the raw byte the same line reads a different, smaller
figure and fails reconciliation. A control byte between two digit groups is therefore read as
a thousands separator, which is the one shape the "never synthesise a figure the paper did not
print" ruling is about.

**Exposure, measured over all 58: nil.** Exactly ONE document carries C0 bytes
(`4145E2C82C6B8329`, 10 of them, **all NUL**), and **zero of the ten is adjacent to a digit**.
Two narrowings are available and cost nothing today: exclude digit-adjacent positions from the
substitution, or apply it only where the heading grammar looks. Also worth narrowing: the
substituted class (`\x01-\x08`, `\x0b`, `\x0c`, `\x0e-\x1f`) is far wider than the single byte
measured, and `\x0c` is a page separator in some text layers.

**Shared-extraction hazard** — the cell's own finding 2 is correct, and the census is one
query, not a fix: the byte comes out of the shared native-text extraction and any reader whose
heading grammar uses `\s` has the same hole. Recorded for a later cell; not this card's
ownership.

**A second, unrelated shape** (FINDING 2, MINOR). A wrapped description line that is
**exactly** a section name opens a false section: driven, the row's description is silently
truncated and the remainder is swallowed. Neither identity sees it — count and total are
unchanged by it. A description line that merely STARTS with a section name and continues does
NOT open a section (driven), so the exposure is narrow. No measured instance: on all 41
preserved documents **no `transactions[*].description` leaf changed at all**, which is the
decisive evidence that no false heading was introduced on the protected cohort.

### 3.6 The 13 movers (Q6) — identity evidence reproduced independently

| what | cell | reviewer |
|---|---:|---:|
| printed index categories reproduced exactly | 96 | **96** |
| printed ladder days matched, day for day | 233 | **233** |
| published rows | 3,095 | **3,095** |
| credit / debit coverage | 1.0 / 1.0 on all 13 | **1.0 / 1.0 on all 13** |
| continuity breaks | 0 | **0 on all 13** |
| `adb.ok` | true | **true on all 13** |
| quality level / integrity flags | `transaction_level` / 0 | **`transaction_level` / 0 on all 13** |
| currency | USD by schema default | **USD, `currency_source = schema_default`, on all 13** |
| bank average vs the calendar-day ADB | 2 exact / 1 within a cent / 6 differ / 4 print none | **2 / 1 / 6 / 4** |

And on the 41 preserved, independently: **321** index categories, **821** ladder days,
**6,377** rows — the 821 matching the 821 changed `stated_daily_balances` leaves exactly.

**Currency.** A token census over all 58 documents finds **no currency token of any kind**
(`USD`, `CAD`, `EUR`, `GBP`, `US Dollar`, `Canadian`, `C$`): there is no printed currency
evidence to outrank the schema default, so USD by schema default is the correct and only
available reading. Doctrine kept.

**The bank average is evidence-only and is documented as such.** PNC's figure is a
service-charge cycle average; the platform publishes it as
`bank_reported_average_balance` with its printed label (`Average ledger` / `Average monthly
balance`) and computes `bank_reported_average_variance` beside it. Six of nine differing is
expected and is not a defect under the ADB doctrine.

**L-1 — checked, and clean.** Six of the 58 print more than one account-number-shaped token,
four of them newly validated. Investigated: on the four Virtual Wallet movers the second token
is `XX-XXXX-` — a **mask stub with no digits at all**, identical across all four documents and
repeated 18–23 times in the page footer. It is furniture, not an account. Each of those
documents prints exactly one `Balance Summary`, one `Beginning balance`, one `Ending balance`
and one period, and no line-initial `Reserve` / `Growth` / `Savings` sibling anywhere. The two
documents that DO print a second, fully-numeric account-shaped token
(`5684857C24B79344`, `31E43C6F9393CA15`) are both refused. **No published document drops a
sibling account.**

### 3.7 Fail-closed, hardcodes, and the floor (Q7)

Driven through the real parser, all fail-closed as they should:

| construction | verdict |
|---|---|
| the document stops mid-section (a section the index names never printed) | **DECLINED** |
| a section's rows printed twice (a duplicated page) | **DECLINED** |
| a genuine continuation page (heading reprinted, rows split) | published, both rows |
| a TAB-form continuation heading | published |
| a both-sided category with no direction printed | **DECLINED** |
| a PNC product this reader cannot name | **DECLINED** (left unclaimed) |
| the index counts an item the reader drops as a non-posting | **DECLINED** |

The last is a cost worth recording (NOTE 3): a bank-indexed item printed with a zero amount is
dropped by `_posts` and the count then mismatches, so the document declines. That is
fail-closed, and there is no measured instance.

**Hardcodes: none.** No date, amount, count or day is written that the paper did not print.
The four constant tables are institution vocabulary — the product titles (verified present in
the page before publication), PNC's own printed section taxonomy, the two umbrella spellings,
and one alias table of two printed spellings per section. Guards 255 and conformance 1,270
pass; no registration was added, so no registry pin was owed.

**W3 is base + one section**, appended, no other section touched. Commit messages are written
in classes and scan 0 in every class.

**The corpus gate is GREEN at the TIP, not only at `112002f`.** The cell argued the older
tree's reading carries; the reviewer did better than accept the argument. `pytest -m corpus`
runs the same gate: `tests/test_corpus_gate.py::test_corpus_gate_is_green` calls
`corpus_gate.run_gate(...)` and asserts **no check failed**, 109 PDFs, 0 exclusions, and the
sibling test pins 105 PASS with the withheld set. That slice **completed at the tip: 30
passed, EXIT=0**. The cell's standalone gate log at `112002f` reports GREEN — 105 PASS / 3
WITHHELD / 1 REFUSED, verdicts 1 refused / 3 review / 102 validated / 3 withheld. The
argument also checks out independently: `detect` is byte-identical between `112002f` and the
tip, the only production delta is one docstring plus the `read_money` refusal path inside
`_printed_index` (reachable only from `parse_pnc_statement`), and `pnc` occurs **zero** times
in the gate log and **zero** times in the corpus manifest.

---

## 4. Ocean's question: `payload_now_raises` — adjudicated, no severity

Ocean asked whether the two documents recorded as `payload_now_raises` reveal a reader that
crashes where it should decline. **They do not, and the premise rests on the sweep's
vocabulary rather than on the reader.**

* **At the tip not one of the 58 documents raises.** Driving `parse_pnc_statement` directly
  over the whole population: **54 published, 4 declined by `return None`, 0 raised.**
* **The sweep's "raises" is the analysis pipeline's representation of "no payload",** which is
  how EVERY declined document appears — the tool's own docstring says failures are never
  cached. Proven rather than asserted: `31E43C6F9393CA15` (index 610, chunk A) was
  `failed/parser_declined` at the base with no parser, is still declined at the tip, and
  appears in **neither** finding list — it sits in `no_payload_raises_again`, i.e. "the
  analysis raised, before and after". `payload_now_raises` therefore means exactly "this
  document used to publish a (withheld) payload and now the parser declines" — the intended,
  named movement, and `cohort_replay` (the runner's exact call) classifies all three as
  `failed/parser_declined`.
* **The `read_money` `ValueError` is the platform's documented contract, not an ad-hoc
  crash.** `analysis/money.py` states it explicitly: a refusal in a regex-guaranteed position
  raises `ValueError` — "the documented contract of the raising family (§MG4), the convention
  `chase._money_required` and `banco_popular` already follow, and fail-closed at the pipeline
  — the document declines instead of publishing a number nobody printed" — and the message
  never quotes the token, so no statement content crosses the boundary.
* **Can it fire on a protected or a moving document?** Measured: across all 58 documents the
  index reader takes **557** tokens and the money grammar refuses **0** of them. It fires on
  none of the 41 protected and none of the 13 movers. Its behaviour if it ever fired is
  fail-closed by contract, not fail-open.

No change is required. The one thing worth doing is a record correction, below.

---

## 5. Findings

**BLOCK: none.** No regression; no weakened check; no check vacuous on any published
document; no wrong published figure; no hardcode; and both open floor rows are complete.

**MINOR 1 — the C0 normalisation's justification is false in one direction, though its
exposure is nil.** A control byte between two digit groups becomes a thousands separator and
joins two printed tokens into one figure (driven; §3.5). Measured exposure: 1 document carries
C0 bytes, all NUL, **0 digit-adjacent**. Recommend narrowing the substitution to
non-digit-adjacent positions (or to the heading grammar), narrowing the class toward the byte
actually measured, and correcting the sentence in `_CONTROL_BYTE`'s docstring and in W3
§PNC9.3 that says a space "can only separate two tokens, never join them".

**MINOR 2 — a false section boundary from a description line truncates a description.** A
wrapped description line that is exactly a section name opens a section; the description is
silently cut and neither identity can see it (§3.5). No measured instance — no description
leaf changed on any of the 41. Worth one line in the record and a later narrowing (a heading
candidate that stands between a row's date and the next row's date is not a heading).

**MINOR 3 — three record inaccuracies in W3 §PNC9, all correctable in the closure, none
changing an outcome.**
1. §PNC9.8's "the printed index as an identity | 54 print one" and
   `_matches_the_printed_index`'s docstring "All 57 PNC documents in the archive print one"
   are both wrong. The measurement is **58 of 58** (table form only 50, restatement only 4,
   both 4, neither 0). The correction strengthens the cell's own case: the index identity is
   never vacuous on this population.
2. §PNC9.10's sentence "the 13 it newly claims are exactly the 13 this card names" is false as
   written: `claim_delta`'s 13 newly CLAIMED includes `31E43C6F9393CA15` and excludes
   `4145E2C82C6B8329`, while the 13 newly VALIDATED is the other way round. Two different sets
   of the same size. Both lie wholly inside the named 17, so the substance — zero movement
   outside the population — holds; the sentence should say so precisely, especially as it was
   standing in for the missing sweep.
3. §PNC9.10 still records the corpus-marked slice and the archive sweep as **NOT RETURNED**.
   Both are complete: 30 passed EXIT=0, and the whole 3,380-document sweep as tabulated in §2.

**NOTE 1 — both identities are conditional.** Strictly additional to the base and non-vacuous
on every published document in this population (§3.4), but the record should say "applied
wherever the bank prints them, and the bank prints them on all 58" rather than "mandatory".

**NOTE 2 — `account_name` is read from a closed vocabulary by position.** Corroborated 58/58
(earliest product title on line 6) and fail-closed for an unknown skin, but it is a positional
heuristic, not a titled-field extraction (§3.2).

**NOTE 3 — the index identity can refuse a readable document** whose bank-indexed item prints
a zero amount (§3.7). Fail-closed; no measured instance.

---

## 6. Answers to the deliverable's explicit questions

* **Newly validated 13 by sha?** YES — set equality with the named 13, re-measured.
* **Preserved 41/41 with every changed leaf classified and proven?** YES — 14 leaf paths, all
  inside the two claimed classes, nothing else; no balance, no `underwriting_adb`, no ADB
  daily ending balance, no metric, no transaction leaf, no period, no account number, no
  currency. The ladder class is proven correct structurally, by measurement, and by a
  one-cent fixture that declines and that moves the ADB when the gate is removed. The
  `account_name` class is proven correct by census (58/58 positional corroboration) and is a
  correction of a base hardcode.
* **Withheld → failed ×3 correct?** YES — each fails a printed identity of its own document;
  all three return to `withheld` under `all_identities`, so the refusals cost no validated
  coverage; the contamination claim on `5684857C24B79344` is confirmed by hash (15 of 18
  shared with the same account's statement two months later).
* **Regressions 0?** YES — validated regressions 0 at the tip on both cohorts; the whole
  archive sweep shows zero movement outside the named population once the nine
  `train9`-composed movers are excluded, and all nine are PROVEN at the base.
* **Doctrine kept?** YES — one calendar-day ADB over the printed period, unchanged to the
  cent; the printed ladder published as day-level bank evidence, not as a bank average; bank
  averages evidence-only; USD by schema default with no printed currency evidence anywhere in
  the population; no synthesised date or amount; L-1 satisfied on every published document;
  $0 vendor.
* **Privacy 0?** YES — 0 over 2,685 added file lines and 0 in every class over 11 commit
  messages.
* **Sweep and slice completed?** YES — both, by this review.

---

*Reviewer's instruments and logs are private (`scratchpad/b9/review_pnc9/`): `base_replay.log`,
`tip_replay.log`, `floor.log`, `mutation.log`, `rev_sweep_b.log`, `hostile.py`, `hostile2.py`,
`census.py`, `movers.py`, `claims.py`, `l1.py`, `raises.py`. They print shas, gate names,
shapes, counts and hashes only — never a document value.*
