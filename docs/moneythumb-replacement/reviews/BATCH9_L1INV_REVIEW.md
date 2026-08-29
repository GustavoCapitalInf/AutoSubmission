# BATCH9 L1-CU-SUFFIX-INVESTIGATION — independent adversarial review

Branch `wave9-l1inv`, base `38a94aa`, tip `083e75d`. Reviewer did not write the packet, asked
the cell nothing, and re-ran every instrument itself from the run of record
`TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d` and the cold cache
`.claude/recovery/webapp_data_train8_cold` (both read-only). Private scratch only; no printed
value, name, account number, amount or date appears below.

**VERDICT: UNSOUND.** Every published number reproduces to the digit — the instruments are
deterministic and the arithmetic is honest. But two load-bearing claims the ruling would rest
on are wrong, and both inflate the case for the answer the packet recommends. The structural
half of the packet (§1, §3, §6, §7) is sound, valuable and should survive; §0's findings (1)
and (3), §4's headline and §8.1's two stages should not be ruled on as written.

**2 BLOCK / 6 MAJOR / 6 MINOR.**

---

## 1. Re-measurement table

Every instrument was re-run with the packet's own commands. `matched?` compares the packet's
printed figure with the figure the re-run produced.

| # | packet's number | re-measured | matched? |
|---|---|---|---|
| 1 | population 214 = 176 CU + 36 DECL + 2 ATB | 214 = 176 + 36 + 2 | yes |
| 2 | 36 declines, 36 confirmed, 24 L-1 refusals | 36 / 36 / 24 | yes |
| 3 | per-reader L-1: huntington 4, community_section 7, navy_federal 4, capital_one 6, consumers 3 | 4 / 7 / 4 / 6 / 3 | yes |
| 4 | pinned 109 on disk, 80 in the run, 29 NOT SURVEYED | 109 / 80 / 29 | yes |
| 5 | pinned claimed by an L-1 reader = 10 (capital_one 4, navy_federal 4, consumers 1, dakota_west 1) | 10, same split | yes |
| 6 | 12 of the 80 surveyed pinned documents are multi-posting (4 oracle / 1 identity / 7 equation-scan) | 12 (4 / 1 / 7) | yes |
| 7 | boundary mechanisms 103 / 38 / 35 / 38 | 103 / 38 / 35 / 38 | yes |
| 8 | fail-closed reasons 22 / 11 / 5 | 22 / 11 / 5 | yes |
| 9 | 442 located sections; 208 / 79 / 273 / 75 / 31 / 327 | identical | yes |
| 10 | roll-up oracle strength 60 / 117 / 37 | 60 / 117 / 37 | yes |
| 11 | posting sections per document 47 / 86 / 57 / 20 / 2 / 2 | identical | yes |
| 12 | CU-SUFFIX split 32 / **79** / 48 / 13 / 2 / 2 | identical | yes |
| 13 | 63 structural families; 39 with ≥3 members covering 182 | 63 / 39 / 182 | yes |
| 14 | 392 sections offered; **97** close | 392 / 97 | yes |
| 15 | **23** documents close on every located section; 19 multi; **12** with the roll-up | 23 / 19 / 12 | yes |
| 16 | by boundary 103·212·52·16·12 / 38·89·21·3·0 / 35·84·24·4·0 / 38·7·0·0·0 | identical | yes |
| 17 | L-1 table: 65 / **11** / **6**; DECL 16 / 0 / 0; ATB 0 | identical | yes |
| 18 | fail-closed classes 78 / 77 / 52 / 27 / 20 / 17 / **16** / 8 | identical | yes |
| 19 | per-group closures (guardian 8/8, goldenwest 4/4, altra 3/3, hudson_valley 3/3, wescom 2/5, wpcu 2/8, ornl 1/4) | identical | yes |
| 20 | 4 documents print two currency columns | 4, all `FAM:community_savings_bc` | yes |
| 21 | canonical guards 255 | 255 passed, EXIT=0 | yes |
| 22 | `tests/test_experiments_are_not_wired.py` passes | 2 passed, EXIT=0 | yes |
| 23 | branch privacy scan hit_count 0 | 0 over 2,792 added lines / 3,351 documents at the tip | yes |
| 24 | §7 regression surface: "the pinned 109 … **16** print two or more posting sections" | **12** | **NO — MAJOR-1** |

The full suite (6,858), the conformance set (1,270), the corpus gate and the fidelity replay
were NOT re-run. They cannot have moved: `git diff 38a94aa..083e75d --stat` is five files —
the packet, the W3 section and `tools/l1_{census,structure_census,split_prototype}.py`. No
production file, no test, no registry entry differs from base. That is a structural argument,
not a re-measurement, and it is offered as such.

**Reproduction is therefore total on the printed numbers, and the findings below are all about
what those numbers MEAN.**

---

## 2. Findings

### BLOCK-1 — "Every one of those numbers is a LOWER BOUND" is false. The ruling-relevant floor is 3 documents, not 11.

`chain_walk` seeds its accepted-prefix snapshot with the EMPTY prefix whenever the candidate
opening already equals the candidate closing:

```
snapshot = ([], previous, 0) if abs(previous - round(closing, 2)) <= 0.005 else None
```

A section whose opening and closing figures coincide therefore CLOSES with zero transactions —
`reconcile` sees `begin + 0 = end` and no continuity rows, and the ADB sees a flat carried
series over the period — no matter how much the section actually printed. The packet's own
safety argument (packet §4.1, W3 §L1INV.3: "skipping a genuine ledger figure breaks continuity
and the section fails closed anyway") does not hold for the case where EVERY figure is skipped.

Measured, by joining the structure census's per-section printed facts onto the prototype's
per-section results (same population, same `structure()` call, same order):

| | sections |
|---|---:|
| sections the prototype reports as CLOSED | 97 |
| … that published an EMPTY ledger (0 transactions) | **50** |
| … of those, sections that print NO dated row (legitimately idle) | 18 |
| … of those, sections that print **≥ 2 dated rows** and published nothing | **32** |
| closed sections that published fewer rows than the section prints dated rows | 68 |
| printed dated rows on closed sections vs published transactions | 6,233 vs 3,989 |

The empty-ledger closures are concentrated, not scattered: `vystar` 7, `hudson_valley` 6,
`wescom` 5, `goldenwest` 4, `security_service` 4, `wpcu` 3, `huntington` 2, `psecu` 1.

The clearest case, checked by hand on all three documents of the family. On
`FAM:hudson_valley_fcu` (`0C78E2F2FA203C14`, `5970FDF20E7CE901`, `943CCA7B9C8BC269`) the
enumerating table prints two DISTINCT figures per account row and the prototype assumes
`rollup_values[0]` is the opening. On this issue the first figure is the account's CLOSING.
Neither section prints an opening of its own, so the prototype takes the roll-up's first
figure as the opening — which equals the section's own printed closing — and the empty walk
closes immediately. Both sections of all three documents publish zero transactions while
printing 2 and 62 / 67 / 66 dated rows. All three then also count as "the roll-up ALSO
reproduces every section's closing", because the closing it reproduces IS the roll-up figure
it started from.

Now apply the packet's OWN §6 to the packet's own §4 measurement — §6.1 (an inferred
`section-equation-scan` boundary is never sufficient), non-vacuity (a section that prints rows
may not publish an empty ledger), and §6.6 (the production `posting_dates_cover_source` check
against the SECTION's text, which the packet names as an unpaid debt and I ran):

| | documents |
|---:|---|
| §4.2 documents whose every located section closes | **23** |
| … with a printed partition (§6.1) | 19 |
| … and no section publishing an empty ledger over printed rows | 12 |
| … and passing `posting_dates_cover_source` per section (§6.6) | **11** |
| §4.4 / §8.1 L-1 documents (≥2 posting sections) closing on every section | **11** |
| … with a printed partition (§6.1) — drops `goldenwest` ×4 | 7 |
| … and non-vacuous — drops `hudson_valley` ×3 | 4 |
| … and passing §6.6 — drops `ornl` ×1 | **3** |
| §8.1 "6 of those also reproduce against the roll-up" | **2** |

The three survivors: `2A8F1A9D95DD0672` (`FAM:altra_fcu_statement_summary`, section-identity),
`7C7956EB5E93DB1D` and `E38FA786106F752E` (`FAM:guardian_cu_statement_summary`, rollup-oracle).

And the family claims in §0.3 / §4.5 / W3 ("whole families close end to end") correct to:
`guardian_cu` 8/8 (holds), `altra_fcu` 3/3 (holds), `ornl_fcu` 1/4 (holds),
**`goldenwest_cu` 1/4, `hudson_valley` 0/3**.

Why this is a BLOCK and not a MAJOR: §8.1's Stage 2 asks the owner to authorise a schema
change, a package-math change, an ADB doctrine question and every webapp surface on the
strength of "measured floor today: **11** documents … **6** of those also reproduce against
the roll-up". The floor consistent with the packet's own conditions is **3**, and **2**. The
packet's repeated instruction to read every number as a lower bound is the opposite of the
truth for this class: an empty-ledger closure is an upward artefact.

### BLOCK-2 — the 79 "single-posting" documents are not Stage-1 documents under the ratified idle-sibling rule.

`analysis/symitar.py` 13–45 licenses skipping a deposit sibling on exactly two printed
grounds: the declaration `No Transactions This Period`, or a yield-only section whose every
posting is a dividend AND whose own arithmetic closes AND whose last balance equals the
`ACCOUNT SUMMARY`'s ending for that account AND whose skipped postings are accounted for by
the platform's own `Dividends` column, with the whole skip failing closed on any one of them.

The census applies neither. `l1_structure_census` calls a section "posting" when
`DATED_ROW` matches **two or more** times in its span (`s.n_dated_rows >= 2`); the "idle"
sibling is simply everything below that threshold. Nothing tests a printed declaration and
nothing tests arithmetic.

I read all 79 documents section by section (a superset of the ≥15 asked for; text stayed in
scratch), classifying every sibling section of every one of them:

| the 79, classified by their WEAKEST sibling | documents |
|---|---:|
| a sibling POSTED a dated row and declares nothing | **20** |
| a sibling is empty and silent (no declaration of any kind) | 27 |
| a sibling is empty and names a dividend column (would need the yield-only test) | 10 |
| a sibling declares idle in some other wording | 6 |
| no sibling section located at all | 16 |
| **every sibling prints `No Transactions This Period`** | **0** |

| the 89 sibling sections themselves | sections |
|---|---:|
| print `No Transactions This Period` (symitar's declaration, as written) | **4** |
| declare idle in some other wording | 6 |
| empty, name a dividend column | 18 |
| empty and silent | 38 |
| POSTED a dated row, declare nothing | 23 |

**No document among the 79 has every sibling satisfying the ratified declaration.** 63 of the
79 carry at least one sibling that does not. Stage 1 as written — "publishes the 79 CU
documents with exactly one posting section, treating every other printed section as an idle
sibling under the ratified symitar rule" — would silently drop a sibling that printed activity
on 20 documents and would extend a ratified rule to 43 more on no printed evidence at all.
That is the L-1 defect itself, arriving through the door marked "no ruling needed".

The threshold is also internally inconsistent with the packet's own fail-closed condition.
§6.3 says "No section with **a dated ledger row** may be dropped" — one row, not two. Re-run
the same census at that threshold and the split moves:

| posting = section with ≥1 dated row | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---:|---:|---:|---:|---:|---:|
| CU-SUFFIX | 29 | **54** | 68 | 21 | 2 | 2 |
| DECL-L1-CANDIDATE | 13 | 5 | 10 | 1 | 7 | — |

The headline "79 single-posting / 81 multi-posting" becomes "54 / 111" under the packet's own
rule. The 79 and the 81 are threshold artefacts, and the threshold chosen is the looser one in
both directions: it makes Stage 1 look larger and Stage 2 look smaller.

### MAJOR-1 — §7 states a pinned exposure of 16 that the packet's own §1.2 measures as 12.

Regression-surface row: "the pinned 109 | 10 documents claimed by an L-1-carrying reader
(§1.2); **16** print two or more posting sections". The instrument prints 12, §1.2 prints 12,
W3 §L1INV.1 prints 12, and my re-run prints 12 (4 rollup-oracle, 1 section-identity, 7
section-equation-scan). 16 reproduces from nothing. It errs conservatively, which is why it is
a MAJOR and not a BLOCK, but a regression surface is one of the six things the owner asked for
by name and it must carry a number that reproduces.

### MAJOR-2 — `capital_one`'s emergent refusal is described backwards, and its real shape is more dangerous.

The packet (§1.1) and W3 both say: "`_native_summary` matches ONE summary block and the six
declining documents print three." `_native_summary` uses `re.search` — matching one of three
blocks would not refuse anything, it would publish the first one. I ran the module's own
helpers on all six declining documents:

| | result on all 6 |
|---|---|
| `Previous Balance <date>` prefix occurrences | 3 |
| the nine-cell regex inside `_native_summary` matched | **False on all six** |
| `ACCOUNT DETAIL FOR PERIOD` caption present | True on all six |
| rows returned by `_native_transactions` | 24, 32, 28, 28, 41, 1 |
| `parse_capital_one_statement` returns None | True on all six |

The refusal is: the strict nine-cell summary regex fails outright on the three-account layout,
so `beginning_balance` / `ending_balance` stay None and the parser returns None — **while its
transaction grammar happily harvests 24 to 41 rows that span the document's three accounts.**
That is a materially worse fragility than the one described. Anyone who relaxes or re-orders
`_native_summary` to match one of the three blocks gets a statement whose stated summary comes
from ONE account and whose ledger comes from ALL THREE. The packet's §7 already flags
capital_one as "easy to make silently wrong"; the mechanism it gives makes that warning sound
smaller than it is.

### MAJOR-3 — `reconcile` is satisfied by construction; "the EXISTING reconcile + ADB, unchanged" is one oracle, not two.

The walk accepts a pair only where `previous ± amount = balance` to the cent and records the
amount as the balance delta. Continuity is therefore exact by construction and the sum check
telescopes to `end − begin` by construction. Measured over the whole population: **105 sections
had a successful walk; `recon.ok` was False on 0 of them; `adb.ok` was False on 8.** Every
refusal the packet attributes to "the validator" is the ADB. The packet's framing — a section
"handed to the EXISTING deterministic validator" and closing when both oracles agree — reads
as two independent checks passing, and it is one check plus a restatement of the walk.

### MAJOR-4 — the prototype measured the evidence that would have caught its own false closures, and then passed `None`.

§3.3 measures that **79 of 442 sections print their own counts / totals** and **75 print their
own daily-balance table**. The reconstructed `Statement` sets neither: no
`stated_credit_count`, no `stated_total_credits/debits`, no `stated_daily_balances`. Those are
precisely the fields that make `reconcile` do independent work (count coverage, credit/debit
coverage — the checks that see a truncated ledger) and that make the ADB rest on bank-printed
daily evidence instead of a reconstruction. Every one of the 32 false-empty closures would have
failed a count-coverage check the section itself prints. The packet names one unpaid debt
(`posting_dates_cover_source`); these two are larger, unpaid, and unnamed.

### MAJOR-5 — the ten fail-closed conditions say nothing about money moved between a member's own accounts, which the population shows.

On the documents where two or more sections each reconstructed a non-empty ledger (11
documents — the small base is itself a consequence of BLOCK-1), **6 carry at least one
same-day, same-magnitude, opposite-signed pair across two sibling ledgers — 44 such pairs**.
That is the printed signature of money moved between the member's own accounts, and it means
the same money is in two ledgers of the same document.

Option C publishes "package math per account" (§5) and §8.3 raises package math as a ruling
question, but §6 contains no condition about it. A package that sums per-account deposits over
a multi-account member statement double-counts every internal movement: gross deposit totals,
deposit counts, and any revenue or NSF derivation built on them. The currency condition (§6.8)
is present and right; a transfer condition is missing and belongs beside it.

### MAJOR-6 — §6 has no deposit-versus-loan condition, and §6.7 breaks without one.

`analysis/symitar.py` 13–45 states the rule explicitly: a member's loan facilities print under
a different grid and are not deposit ledgers. The ten conditions never mention it. Measured:
**6 of the 103 rollup-oracle documents enumerate a loan / credit facility in at least one
roll-up row, and 2 of those print two or more posting sections.** §6.7 then requires "where a
cross-account total is printed the published sections must sum to it" — a total that includes a
loan facility can never be reproduced by the deposit sections, so the condition either refuses
every such document or has to carve out a category it does not define. (No document in this
population prints both a loan row and a cross-account total, so the collision is latent rather
than live — but the condition list is what the implementation will be built from.)

### MINOR-1 — 442 located sections versus 392 offered is never reconciled, and the "27" is mislabelled.

§4.1 says "27 sections are lost to `document-prints-no-resolvable-period`". It is 27
DOCUMENTS, which between them carry **77 located sections**; the refusal class counts one
pseudo-section per document. 442 − 77 + 27 = 392. The packet prints 442 in §3.3 and 392 in §4.2
and never says why they differ.

### MINOR-2 — the ADB runs on the DOCUMENT's period for every section, and §6.6 does not say whose period it means.

`find_period` is called once on the whole document and the same pair is handed to every
section. The packet never states this. It is defensible on a member statement that prints one
cycle for all accounts, and it is the reason 27 documents lose every section at once; but §6.6
("calendar days over the printed period") is ambiguous for a section on an issue that prints a
per-share activity range, and the ADB doctrine's denominator question deserves the explicit
answer.

### MINOR-3 — Option B is rejected by argument where the measurement was available.

The rejection is correct and my measurements strengthen it, but §5 answers it with "the census
does not tell us". It does:

| candidate primary rule, over the 81 multi-posting documents | |
|---|---:|
| "the section the roll-up names first" — UNDEFINED (no enumerating table) | 38 of 81 |
| "the only checking / chequing / draft share" — UNDEFINED (no such heading) | 35 of 81 |
| … AMBIGUOUS (two or more such posting sections) | 11 of 81 |
| … decides the document | 35 of 81 |
| documents printing a cross-account TOTAL row (the platform ranking the accounts alike) | 11 of 81 |
| roll-up identity is `product_name_only` on the multi-posting rollup-oracle documents | 22 of 43 |

No candidate rule is defined on even half the population, and one is actively ambiguous on 11.
Conclusion unchanged; evidence now measured. (In the packet's favour: sections resolving to a
REPEATED identity token — the §6.2 hazard — measure **0** on this population.)

### MINOR-4 — the guard named on the handoff does not cover `tools/`.

`tests/test_experiments_are_not_wired.py` scans `analysis`, `ocr`, `webapp`, `discovery`,
`telemetry`, `benchmark` and six root modules for `^\s*(?:from|import)\s+experiments\b`. It
says nothing about `tools`. The prototype IS unwired — I grepped the tree and nothing outside
`tools/l1_*` imports any of the three — but that property is held by a grep, not by a test, and
the card's "the guard applies" is not true as written.

### MINOR-5 — the privacy number in §10 predates the tip, and 29 documents are not scanned against.

§10 reports 0 hits over 2,751 added lines, measured at `a86f183`. Re-run at the tip `083e75d`:
**hit_count 0** over **2,792** added lines, MONEY 0 / DIGITS 0 / DATES 0 / WORDS 0. The one
real leak the cell reports removing is gone and nothing replaced it. Note the scan reads 3,351
of the 3,380 shas — 29 have no cached text and are therefore not scanned against; that is the
same population the pinned survey names as NOT SURVEYED and it should be stated next to the
zero rather than left in the JSON. This review's own added lines were scanned the same way:
**hit_count 0** over **3,265** added lines at `265f754` — EXIT=0, after three rewrite passes
over ordinary English word pairs, which is what a zero costs.

### MINOR-6 — "every located section closes" is not "every printed section closes".

`DocResult.all_posting_close` exists and is never called; the reported figure uses
`sections_closed == n_sections`, where `n_sections` is what the census LOCATED. 38 documents
have no located partition at all and 11 more are `rollup-enumerated-but-no-section-
reappearance`. A document whose third account the boundary layer missed can still be counted as
closing on every section. The packet's wording is literally accurate and reads as stronger than
it is.

---

## 3. Answers to the ten hostile questions

**(1) Does the census apply the ratified idle-sibling predicates?** No. It applies
`n_dated_rows >= 2` and calls everything below that idle. Of the 79, **63 have at least one
sibling that would not satisfy symitar's rule as written**; only **4 sibling sections in the
whole 79 print `No Transactions This Period`**; **no document** has every sibling printing it;
**20** have a sibling that printed a dated row and declares nothing. 16 have no located sibling
at all — and "no located sibling" is not "no sibling". See BLOCK-2. All 79 were read section by
section, not sampled.

**(2) The split prototype.** Period: from the DOCUMENT, once, for every section (MINOR-2).
Opening/closing: the section's own printed captions first, the roll-up's row second, tried as a
2×2 candidate search; where both are printed and disagree the section is refused (16 sections —
a genuinely sharp refusal). Counts/totals: **`None`** — never the section's own, though 79
sections print them (MAJOR-4). Daily balances: `None` — though 75 sections print them. Trivial
closures: **50 of the 97 closed sections publish an empty ledger; 32 of those print ≥2 dated
rows** (BLOCK-1). `reconcile` refuses 0 of 105 successful walks (MAJOR-3). The ADB runs on the
document's period with a reconstructed daily series and, in the prototype, without
`posting_dates_cover_source`; applying it costs 7 of 97 sections and 4 of the 23 documents.

**(3) Inter-account transfers.** Yes, they are present in two ledgers: **6 of the 11 documents
with two non-empty sibling ledgers carry same-day, same-magnitude, opposite-signed pairs — 44
pairs.** Option C's per-account package math would double-count deposit totals and deposit
counts on exactly those documents. **The fail-closed list does not cover it** (MAJOR-5).

**(4) The 4 two-currency documents.** Confirmed: 4 documents, all
`FAM:community_savings_bc`, all printing both a CDN/CAD and a USD token inside the roll-up
window and elsewhere; each locates 3 sections. The refusal is **necessary** — under
`CURRENCY_DOCTRINE` (native currency canonical, no FX in the analysis layer, one denominated
ADB, no cross-currency package math) a payload spanning two denominations has no valid ADB and
no valid package arithmetic. It is **not sufficient**: the doctrine's hierarchy resolves a
denomination per DOCUMENT, and `jurisdiction_default` is affirmative evidence at the
institution level, so a Canadian member statement carrying one USD sub-account that prints no
code would be silently denominated CAD across all sections. §6.8 should require the
denomination to be established **per published section**, not per document, or refuse whenever
any section's evidence class is weaker than `product`. Note also that these 4 documents print
0/1/1/1 posting sections at the census's threshold, so the condition is not binding on this
population at that threshold — it becomes binding at §6.3's ≥1-row threshold.

**(5) Can an Option-B primary rule be constructed?** No. See MINOR-3's table: "first on the
roll-up" is undefined on 38 of 81; "the only checking/draft share" is undefined on 35 and
ambiguous on 11, deciding 35; 11 documents print a cross-account total, which is the platform
declaring the accounts co-equal; the roll-up identity is a bare product name on 22 of the 43
multi-posting rollup-oracle documents, so two accounts of one product could not be told apart
even if a rule existed. The packet's rejection stands and is now measured rather than argued.

**(6) The 24 DECL L-1 refusals.** Reproduced exactly by running each reader's own gate and
confirming each decline through the reader's own `parse`: 4 / 7 / 4 / 6 / 3. The
`huntington`, `community_section`, `navy_federal` and `consumers` probes call the modules'
own expressions and helpers faithfully (`navy_federal`'s `product.lower().endswith("checking")`
and `len({product}) != 1` are the module's own lines). `capital_one`'s is a re-implementation
and its stated mechanism is wrong — see MAJOR-2. Stability: the refusal is **not stable in the
safe direction**. It is the absence of a match on a nine-cell regex, guarding a transaction
grammar that already returns rows spanning three accounts.

**(7) The pinned finding.** 12 of the 80 surveyed pinned documents are multi-posting (4
rollup-oracle, 1 section-identity, 7 section-equation-scan — the last class the packet itself
calls unproven); 29 pinned documents are not in the run and are correctly reported NOT
SURVEYED rather than read through a second extraction path. The 10 pinned documents claimed by
an L-1-carrying reader reproduce (capital_one 4, navy_federal 4, consumers 1, dakota_west 1),
and note that none of capital_one's or navy_federal's four is among the 12 — the pinned
documents those readers publish are single-summary documents, which is why they publish.
`05E246C0ED6678E6` (CONS-L1) is multi-posting under the strong mechanism, corroborating the
probe. **The regression surface is nearly complete**: readers with L-1 refusals, symitar,
community_section's three registrations, CONS-L1, schema/archive sweep, packages, webapp,
corpus gate and the protected 2,596 are all named. What is missing: the number in the pinned
row is wrong (MAJOR-1); there is no row for the inter-account-transfer effect on package
outputs (MAJOR-5); and there is no row for `analysis/count_semantics.py`, which any
per-section stated-count reading would have to declare a mapping in.

**(8) Read-only and unwired.** `tests/test_experiments_are_not_wired.py` passes (2 tests) but
guards `experiments/`, not `tools/` (MINOR-4). Nothing outside `tools/l1_*` imports any of the
three instruments (grep over the tree). None calls `analyze_markdown` / `cached_analysis`, so
the `corpus_gate.EXCLUDED_ANALYSIS_CALLERS` claim holds. Branch privacy scan re-run at the tip
against the whole population: **hit_count 0** over 2,792 added lines and 3,351 documents, all
four classes zero. I read the packet and W3 §L1INV in full: no printed value, name, account
number, amount or date remains. Content sha16s and census group labels are the only
document-specific tokens, which is the established convention.

**(9) Are the ten fail-closed conditions sufficient? No — and this population already contains
the counterexamples.**
* *A closing that matches after a missed row and a missed reversal.* The chain identity
  telescopes, so `reconcile` cannot see a truncated ledger; running-balance continuity is
  satisfied by construction; the roll-up reproduces because the truncation stopped ON the
  closing; and `posting_dates_cover_source` compares DAYS, not rows, so a dropped pair on a day
  that carries another row is invisible. Measured: **90 of the 97 closed sections pass
  `posting_dates_cover_source` while 68 of 97 published fewer rows than the section prints.**
  This shape passes all ten conditions. The fix is §6.5 plus the section's own printed COUNTS
  and TOTALS (MAJOR-4), which 79 sections supply.
* *A roll-up that lists a loan account.* No condition excludes it; §6.7's cross-account total
  then cannot be reproduced. 6 documents enumerate one, 2 of them multi-posting (MAJOR-6).
* *A section boundary that is a page break.* Partly handled — `CONTINUATION` skips a
  `(continued)` reprint and both boundary mechanisms dedupe by identity token — but a
  page-break reprint that omits the word is a reappearance satisfying §6.1, and nothing in §6
  requires the published sections to PARTITION the document (to be disjoint and to cover the
  ledger region completely). Add that as a condition.
* *One account number with suffixes.* §6.2 as written is satisfied: distinct suffixes are
  distinct tokens, and 0 documents resolve two sections to the same token. The residual hazard
  is the locator, not the condition: a bare member number is a prefix of its own suffixed forms.
* *And the one the prototype actually fell into:* a roll-up whose column ORDER is
  (ending, …) rather than (beginning, …). No condition constrains which roll-up column is
  which. §6.4 requires section and roll-up to agree "where both are printed" — and is vacuous
  exactly when the section prints no opening, which is when the roll-up is being trusted.
  **Add: the roll-up's column roles must be established from its printed header (measured: only
  30 of 214 documents print a roll-up column header at all), and a section whose opening comes
  from the roll-up may not close with zero transactions if the section prints a dated row.**

**(10) Are the owner's questions answered?** Measured answers: how many share one structural
family (63 families / 39 / 182); what varies between institutions (§3.2's closed sets); how
accounts are separated (§3.1's four mechanisms); whether boundaries come from explicit printed
evidence (141 of 214, 103 with an oracle); the regression surface (§7, one number wrong); the
exact fail-closed conditions (§6, incomplete per (9)). **Answered by opinion where a
measurement was available:** Option B's rejection (MINOR-3 supplies the numbers); "one shared
parser architecture can cover the family" — the packet argues this from the closed vocabularies
and the `core_processor_*` precedent, which is a good argument and not a measurement, and its
own §4.5 then concedes that five families need their own row grammars (a figure it correctly
flags as an ESTIMATE). **Answered wrongly:** "whether each account can be reconstructed and
validated independently" and "the expected safely recoverable population" — BLOCK-1.

---

## 4. What the owner should read differently

Read §1, §3, §6 and §7 as the packet's real product and read §4 and §8.1 as not yet measured.
The structural census is excellent work and its findings hold under re-run: the population does
not share one family but a small closed vocabulary of mechanics; 141 of 214 documents carry a
printed partition and 103 carry a cross-account oracle; 16 sections contradict the table that
enumerates them and must stay refused; 4 documents span two denominations. Those answer most of
what was asked. But the two numbers the ruling would actually turn on do not survive contact
with the packet's own conditions. "11 L-1 documents close today, 6 with the oracle" is **3 and
2** once you refuse the inferred boundaries §6.1 already refuses, refuse the sections that
published an empty ledger over printed rows, and apply the §6.6 check the packet lists as a
condition and then declines to run — and half of the "whole families close end to end" claim
(`hudson_valley` 3/3, `goldenwest` 4/4) is an artefact of a prototype that read nothing on
those documents and closed anyway. Equally, "79 documents need no ruling" is not a Stage-1
population: not one of them has every sibling printing the declaration symitar's ratified rule
requires, and 20 have a sibling that printed activity, so Stage 1 as scoped would commit the
L-1 defect without ever asking. The honest shape of the decision is smaller and sharper than
the packet presents: a handful of `guardian_cu`-shaped documents demonstrably reconstruct
section by section, as things stand, one structural family at a step, and every other number in §4 needs
the prototype to stop accepting the empty ledger and to start using the counts, totals and
daily balances the sections themselves print — 79 and 75 sections respectively — before it is
worth ruling on.

---

# Re-review — the corrected packet

Closure tip `67fd943` over base `38a94aa`; the first review ended at `981652e`. Same reviewer,
same method: the five instrument modes were re-run from the run of record and its cold cache,
and every claimed figure was checked against my own arithmetic rather than against the
closure's report. No production file differs from base (`git diff --stat 38a94aa -- analysis
ocr webapp discovery telemetry corpus_gate.py tests` is empty), so the suite, the conformance
set, the corpus gate and the fidelity replay cannot have moved.

**VERDICT: SOUND WITH FINDINGS. 0 BLOCK / 1 MAJOR / 4 MINOR.**

Both BLOCKs are answered at the root rather than argued with. BLOCK-1's empty-chain seed is
gone, split into two named classes that are never closures, and the enumerating table's columns
are now read from the printed column caption instead of from position — which was the actual
defect underneath the vacuous closures. BLOCK-2 is answered by calling `analysis/symitar.py`'s
own `_DORMANT_RE` and `_yield_only` on every sibling of every single-posting document, which is
the right instrument for the question. The headline moved down by an order of magnitude and the
recommendation was rewritten to follow it rather than to survive it.

## Re-measurement

| claim | re-measured | matched? |
|---|---|---|
| structural families 62 / 39 with 3 or more members / covering 183 | 62 / 39 / 183 | yes |
| sections closing 29; under the stricter after-chain test 16 | 29 / 16 | yes |
| trivially idle 21; empty over printed rows 23, their own classes and never closures | 21 / 23 | yes |
| documents closing on every located section 2, both `guardian_cu` | 2, both `guardian_cu` | yes |
| the table's own closing column reproducing on both | 2 | yes |
| `reconcile` refuses 11 of 48, the ADB 10, against 0 of 105 before | 11 / 48, ADB 10 | yes |
| sections printing a daily-balance TABLE 75 corrected to 24 | 24 (5.4%) | yes |
| sections contradicting their own table 16 corrected to 2 | 2 | yes |
| Stage-1 population under the RATIFIED rule = 0 | 0 | yes |
| 103 siblings: 4 declaration / 0 yield-only / 30 posted-and-silent / 62 empty-and-silent / 7 other | identical | yes |
| 26 documents carry a sibling that posted (24 CU); 63 CU carry a failing sibling | 26 / 24 / 63 | yes |
| at the one-row threshold: 59 single-posting (54 CU), 52 siblings, 0 satisfy | identical | yes |
| L-1 population 81, of which 2 close | 81 / 2 | yes |
| transfer pairs: 7 documents, 47 pairs | 7 / 47 | yes |
| pinned multi-posting 12 (4 strong / 1 / 7 weak) | 12 (4 / 1 / 7) | yes |
| `capital_one`: the nine-cell pattern matches 0 of 6, the transaction grammar returns rows on 6 of 6 | 0 of 6 and 6 of 6 | yes |
| Option B: first-named undefined 30; transaction-share undefined 24, ambiguous 9, decides 48 | identical | yes |
| enumerating tables naming two denominations 4, all one census group | 4 | yes |
| the first review's own chain reproduced as 7 / 4 / 2 | 7 / 4 / 2 on the closure's definition | yes, and see MINOR-A |
| facility-listing tables **15**, of which **0** carry two or more posting sections | **19** and **4** | **NO — MAJOR-A** |
| privacy 0 over 4,712 added lines; guards 255; five runs EXIT=0 | 0 / 4,712 / 3,351 docs; 255; EXIT=0 five times | yes |
| no control byte survives in the instruments | none outside tab, newline and return in any of the three | yes |

## Findings

### MAJOR-A — the facility vocabulary is narrower than the claim made for it, and the collision it was said to have avoided is live.

`LOAN_ROW` carries two classes and its comment states that a wider vocabulary of facility
classes was tried over the enumerating windows of the whole population and matched nothing
these two do not. Re-run over the same windows with the payment-card class added, on the same
raw labels and before the furniture trim:

| | documents |
|---|---:|
| the committed two classes fire on | 15 |
| a vocabulary that also names the payment-card class fires on | **19** |
| the class the committed one misses | the payment-card class, on 4 documents |
| those 4 documents carrying two or more posting sections | **4** |
| those 4 also printing a cross-account total | 0 |

All four are `FAM:goldenwest_cu_member_account_statement` — the family with the highest section
count per document in the whole CU population (3 and 4 posting sections each), and the family
the corrected boundary condition already refuses on other grounds. So condition 12's own table
understates its population by four, and its "of them with two or more posting sections: 0" is
**4**. The condition is right and belongs in the list; what does not hold is the claim that its
vocabulary was measured to completeness, and the consequence is that the deposit-versus-facility
rule bites on the family a Stage-2 implementation would reach for next rather than on nothing.
Whoever implements must confirm what class the row belongs to: a payment-card row on an
enumerating table is a facility by the same doctrine that excludes a loan, but the word alone is not proof.

### MINOR-A — the adjudication the closure asked for: 11 / 3 / 2 against 7 / 4 / 2.

The attribution is half right, and the half that is right is the half that matters.

* **The L-1 figure: the closure is correct.** My 3 was one short, and the missing document is
  `9B8E7D807228DA2B` (`DECL:consumers`). Under the first instrument it was refused as
  `section-and-rollup-disagree-on-the-pair` — a false refusal produced by the positional column
  assumption I identified and did not apply to my own arithmetic. Corrected, it closes under my
  conditions. **The L-1 floor under my chain is 4, not 3**, and 14 of the old 16 sections said
  to contradict their own table were that same false refusal.
* **The document figure: the gap is definitional, not the column fix.** My non-vacuity test
  refused an empty ledger *over printed rows* and deliberately left a section that prints no
  dated row and reads nothing standing as a closure — that is a dormant sibling. The closure's
  reproduction instead requires a non-empty chain on *every* section, so a document with a
  dormant sibling cannot qualify at all. Run on the corrected instrument under my rule as I
  wrote it, the count is **15** documents (8 `guardian_cu`, 3 `altra_fcu`, 3
  `cu_summary_of_accounts_date_posted`, 1 `DECL:consumers`), with the same 4 at the L-1
  threshold and the same 2 reproducing. Under the closure's stricter reading it is 7. Neither
  is 11: of my 12 pre-condition-6 documents, 8 lose their idle sibling to the new class and one
  (`ornl_fcu`) is removed by the new row-coverage gate.

Nothing in the corrected headline depends on this — 2 is reached by a different and stricter
route — but §11 attributes to the column fix a movement that is mostly a change in what counts
as a closure, and a reader of §11 should know which half is which.

### MINOR-B — the ratified yield-only predicate is applied in its relaxed form, undisclosed.

`classify_sibling` calls `_yield_only(rows, opening, closing, None)`. With that fourth argument
absent, `analysis/symitar.py` skips its own fourth condition — the platform's dividend column
accounting for every skipped posting with its credit column at zero — and tests only the first
three. The packet says the module's own predicate decides and names the summary-equality test;
it does not say the fourth condition is not run. **The direction is safe**: a relaxed test that
admits nothing proves the strict test admits nothing, so the measured 0 stands and BLOCK-2's
answer is unaffected. It should still be said, because the instrument's other restatement (how
it picks the words a row printed) is disclosed and this one is not.

### MINOR-C — the corrected headline of 2 is a floor of a floor, and the number that sizes ruling (5) is not printed anywhere.

Because a trivially idle section is now a class rather than a closure, a document with a
genuinely dormant sibling can never reach "every located section closes", however well its
posting sections reconstruct. Measured on the corrected run, allowing a section that prints no
dated row and reads nothing to be omitted rather than counted:

| | documents |
|---|---:|
| every section either CLOSES on the corrected test or is trivially idle | **8** |
| ... all of one census group | `FAM:guardian_cu_statement_summary` |
| ... carrying two or more posting sections | 2 |
| ... with the table's own closing column reproducing | 8 |

Two facts join this to ruling (5): the 4 sibling sections in the whole population that print the
ratified declaration are all `FAM:greater_nevada_cu`, and every one of `guardian_cu`'s six
single-posting documents has an `empty-and-silent` sibling. **So ruling (5) is worth 2 to 8
documents on the only family this packet demonstrates**, and it is worth them on the weakest
evidence class in the sibling table. That is a sharper way to put step 2 of §9.1 than "54 to 79
documents", and it is the number I would want in front of the ruling.

### MINOR-D — one property still rests on a grep rather than on a gate.

Re-verified at this tip and it holds: nothing outside `tools/l1_*` references any of the three
instruments, and `tests/test_experiments_are_not_wired.py` still covers only `experiments/`.
The closure records this rather than fixing it, which is right — the card owns no test. It
stays a standing note for whoever implements, not a defect of this packet.

## What the owner should read differently, second time

Read the corrected packet as sound and read its headline as small on purpose. Everything the
first version got wrong was corrected at the instrument rather than in the prose, the numbers
moved down by an order of magnitude, and the recommendation now follows them: there is no half
of this reservoir that can be taken without a ruling, and the demonstrated population is two
documents of one family. Three things to rule on, in this order. **First,
SIBLING-OMISSION-SURFACE**, which needs no ruling at all, moves no document, and is owed today
by two silent skips — everything else is easier to argue about once a skip is visible.
**Second, ruling (5), the scope of the ratified idle-sibling rule**, because it is cheap to
answer, because it is worth 2 to 8 documents on the one family that demonstrably reconstructs,
and because 26 documents that a two-row threshold had hidden are multi-account statements
whichever way it goes. **Third, and only then, Option C**, sized at two documents today under
thirteen conditions, one of which — the deposit-versus-facility rule — has a measured
population four larger than the packet states and bites hardest on the family with the most
accounts per document. Do not read the 2 as a ceiling on what a real implementation reaches: it
is what a probe with no per-family row grammar and a generic boundary layer can prove today.
Do read it as the honest floor, which is what the first version did not have.
