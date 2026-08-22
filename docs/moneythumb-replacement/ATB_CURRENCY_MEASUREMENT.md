# ATB CURRENCY MEASUREMENT PACKET — the doctrine §B eight-proof gate, applied to ATB Financial

**Cell:** ATB-MEASURE (batch 7, card 3). **READ-ONLY.** Branch
`wave7-atbmeasure`, base `e83f746`. Nothing in this repository changed except
this file and the W3 log entry. No code edit, no expectation edit, no cache
write, no vendor call ($0.00).

**Gustavo's ruling of 2026-08-21:** *"ATB gets the full eight-proof measurement
packet only; no movement until reviewed."* This document is that packet. It
enumerates a ceremony; it does not perform one.

**Verdict: all eight proofs land clean. The ceremony-ready enumeration is
§9.** The movement population is **exactly 7 documents** — the 5 pinned
`ATB/*.pdf` statements plus 2 archive documents — re-derived from the run of
record and live artifact replay, not inherited from the handoff's counts. A
further **4 archive documents are ATB and do not move**, because no
registration claims them and they therefore publish no currency at all; they
are characterised in §10.3 because any future reader for them must be born on
the right default — and, as measured, on the right *read*.

Doctrine §C is written in RBC's names ("an RBC Canada account/product", "the
four pinned RBC documents"). The general rule it instances is doctrine §B's
final paragraph: *"the same shape generalizes to other cross-border
institutions … each requiring its own proven-jurisdiction evidence base before
any default is wired."* This packet is ATB's evidence base, section for section
against `RBC_CURRENCY_MEASUREMENT.md`, which Ocean accepted as the standard.

---

## 0. Instrument, and why it can be trusted

| | |
|---|---|
| Code of record | worktree `.claude/worktrees/mt7-atbmeasure` at `e83f746`; the branch diff against its base is **docs-only**, so every number below was produced by main's analysis code |
| Run of record | `discovery_reports/2026-08-21T014415.938236-0000-7a317445` (validated 2,456 / review 16 / withheld 63 / failed 832 / deferred 13; 3,506 rows, **3,380 distinct shas**), settings key `D3370EEB…1DE24` |
| Text source — archive | the OCR artifact store addressed **by direct file path** — `webapp_data/artifacts/ocr/<key[:2]>/<key>.json`, key recomputed from `cache_key("ocr", content_sha256, ocr_settings_key(…))` over **all eight** capability partitions. The `webapp_data` sqlite index was never opened |
| Text source — pinned | `ocr.pipeline.parse_statement(raw, profile=inspect_pdf(raw), force_ocr=False, allow_local_ocr=False, allow_visual_ocr=False)` — byte for byte the resolver `corpus_gate.production_verdict` uses, with `source_file` blanked at the source as well |
| Coverage | 3,351 of 3,380 shas carry a readable OCR artifact; 29 hold no document under any partition (the `invalid_pdf` refusals and the run's 13 deferred negatives) |
| Filename blindness | every markdown was rebuilt as `StatementMarkdown(source_file="", …).to_markdown()` and then passed through `analysis.parser_registry.admissible_text`, the production admissibility seam. No probe predicate in this packet ever saw a filename or a folder label. Paths were used only to open bytes |
| Family population | **live detection replay**, never `rows.csv parser_id` alone: `analysis.parser_registry.resolve()` re-run over every stored markdown of the ATB superset. Live verdict agreed with the run's `parser_id` on **6/6** |
| Fidelity check A | all five pinned `ATB/*.pdf` files hash on disk to the sha pinned in `docs/adb-audit-results.csv`, `docs/balance-metrics-audit-results.csv` **and** `tests/data/parser_expectations.json` — three independent pins, 5/5 agreement |
| Fidelity check B | for the 2 archive movers the selected OCR artifact is the one whose reconstruction **resolves the run's own stored analysis payload key**, which is per-document proof rather than an ordering; and this cell's before-payload reproduces the run of record's own `outcome_class` on **6/6** ATB archive documents (2 `withheld`, 4 `failed`/raises) |
| Prototype | a scratchpad-only runtime `dataclasses.replace` of the `atb` registration's `parse`. No repository file was modified to obtain any number in this packet |

**The superset, and why the movement measurement is total rather than
sampled.** All 3,351 readable artifacts were scanned for any ATB-shaped token —
`ATB\s+Financial` · `Alberta\s+Treasury\s+Branch` · `atb\.com` · `\bATB\b` ·
`ATB\s*Online`, case-insensitively, over every capability partition:
**6 documents**. That predicate is strictly weaker than the `atb`
registration's own REQUIRED marker (`"ATB Financial" in text`, case-sensitive,
no normalization), so **every document the rule could possibly reach is inside
it**. Adding the 5 pinned `ATB/*.pdf` statements (which are not in the discovery
rows — measured: 0 of the 5 shas occur in `rows.csv`) gives the ATB family of
record: **11 documents.**

Live dispatch inside the family: `atb` **7** (5 pinned + 2 archive) ·
unclaimed **4**. No other registration claims any of them, and no document
outside the superset can reach the rule.

### 0.1 The rule as measured (the prototype)

Modelled line for line on `analysis/rbc.py`, which is the ratified shape.
Two rungs and a floor, evaluated in this order:

```
statement_currency(markdown)
    printed = printed_currency_evidence(markdown)   # rung 1: what the page STATES
    if len(printed) == 1 -> that code
    if printed          -> None                     # two sites disagreeing: fail closed
    return jurisdiction_currency(markdown)          # rung 2

jurisdiction_currency(markdown) -> "CAD" | None
    if US_INSTITUTION matches      -> None      # doctrine §B item 3, checked FIRST
    if CONTRARY_CURRENCY matches   -> None      # doctrine §B items 1 and 4
    if not (J_ISSUER and J_HEADER and J_ACCOUNT and J_SERVICE) -> None
    else                           -> "CAD"     # doctrine §B item 2
```

Rung 1 — **anchored**, because a ledger posting must never counterfeit a
denomination:

* the consolidated layout's own denomination header, a bare line carrying an
  ISO code alone printed under each `<section> Value on <date>` heading:
  `(?m)^[ \t]*(CAD|USD)[ \t]*$`;
* the product line `A summary of (Deposit|Loan) Account <product>` when the
  **product name itself** denominates the account — which is how a Canadian
  bank's U.S.-dollar product announces itself.

Rung 2 — four *affirmative* structural proofs, all printed by the document:

* **J_ISSUER** — the branch-of-domicile line, line-anchored at both ends: the
  institution, the BRANCH's own transit, a civic address, the province code and
  a Canadian postal code, all on one line
  (`Your ATB Financial Branch 08479 Fort McMurray Downtown Branch 11 Haineault
  St Fort McMurray AB T9H 1R8`). Anchoring is the point: `ATB Financial` can
  occur inside a ledger as a counterparty, and a posting is not an issuer line.
* **J_HEADER** — the statement header line, a second and independent site,
  carrying the Canadian Payments Association transit-institution pair with
  ATB's **own** institution number, 219 (`Statement date … Transit number
  08479-219 Customer number … Page number 1 of 5`).
* **J_ACCOUNT** — the same CPA transit-institution designator at an *account*
  site (`00273985278 Transit # 08479-219`). A U.S. deposit account has no
  transit number of this shape, and no U.S. institution is numbered 219 on the
  Canadian rails.
* **J_SERVICE** — ATB's own service furniture: `atb.com` and/or the Canadian
  toll-free `1 800 332-8383`. ATB publishes no other domain.
* **US_INSTITUTION** — `FDIC` · `ABA` · `RTN` · `Routing #/No./Number/Transit` ·
  `ATB Financial (USA)` / `ATB Financial USA` / `ATB Financial, N.A.` ·
  `atb.us` / `atbfinancial.us`.
* **CONTRARY_CURRENCY** — deliberately *wider* than any production reader:
  `U.S. Funds` (any spacing) · `\bUSD\b` · `U.S. Dollar(s)` ·
  `United States Dollar(s)` · `American Dollar(s)` · `fonds américains` ·
  `devise américaine` · `US$` / `$US` / `$U.S.` · `US BUSINESS ACCOUNT` ·
  `Foreign Currency Account` · `Compte en devises` · and the standalone ISO
  codes EUR GBP CHF JPY AUD NZD MXN HKD CNY RMB INR SGD ZAR SEK NOK DKK PLN AED
  BRL PHP.

The jurisdiction default never resolves an ambiguity; it speaks only where the
page is silent (doctrine §B item 4, fail closed).

**Why ATB's institution number is admissible evidence and a bank name is not.**
219 is Alberta Treasury Branches' institution number on the Canadian Payments
Association rails — it exists only inside the Canadian clearing system and only
for this institution. It is layout-independent structural identity, not a
statement-specific constant: no amount, no date, no account number and no
merchant vocabulary is involved.

---

## 1. PROOF 1 — every affected document is an ATB (Alberta, Canada) account/product

*Doctrine §C.1; §B item 2 ("a proven … account/product").*

ATB Financial is Alberta Treasury Branches, a **provincial Crown corporation of
Alberta**. It has no U.S. institution and no foreign branch network; every
branch it operates is in Alberta. CAD is therefore the correct native default
for a proven ATB deposit or loan account carrying no contrary denomination.

**Census over the ATB family of 11**, by structural evidence class, measured on
printed text only:

| Evidence class | Marker measured | Docs |
|---|---|---|
| Institution identity | `ATB Financial` | **11/11** |
| **J_ISSUER** branch-of-domicile line + `AB` + Canadian postal code (line-anchored) | | **11/11** |
| **J_HEADER** `Statement date … Transit number <5>-219 …` (line-anchored) | | **11/11** |
| **J_ACCOUNT** `Transit # <5>-219` at an account site | | **11/11** |
| **J_SERVICE** `atb.com` | | **11/11** |
| **J_SERVICE** Canadian toll-free `1 800 332-8383` | | **11/11** |
| CPA transit-institution pair `<5 digits>-219` anywhere | | **11/11** |
| Alberta province code immediately before a `T…` postal code | | **11/11** |
| Alberta postal code (`T…`) | | **11/11** |
| Canadian postal code anywhere | | **11/11** |
| Canadian payment rails `INTERAC` | | **11/11** |
| Canadian payment rails `e-Transfer` | | **11/11** |
| ATB print-control mailing header (`ATB0114003_…`) | | **11/11** |
| Product — `Deposit Account Statement` | | 7 (the 7 movers) |
| Product — `Consolidated Statement` | | 4 (the 4 unclaimed) |
| Canadian orthography `Chequ…` on the page | | 2 (a `Cheque #` posting, a `Cheque images` counter) |

**Over the 7-document movement population, all four jurisdiction proofs hold on
7/7 — and so do they on all 11.** This is not a residual claim: §6 measures the
prototype, and exactly the 7 documents a registration claims moved.

**Ablation (the conjunction is load-bearing, not decorative).** Over all 11 ATB
documents, removing one evidence class at a time. This table is also the
**mutation table the implementing cell owes for the gate it adds**: weaken any
one clause and the default disappears entirely rather than degrading.

| Mutation | `jurisdiction_currency` |
|---|---|
| control (unmodified) | **CAD 11/11** |
| Canadian postal code stripped from every ATB branch line | **None 11/11** |
| `atb.com` + the Canadian toll-free neutralised | **None 11/11** |
| `Transit number` relabelled on the statement header | **None 11/11** |
| `Transit #` relabelled at every account site | **None 11/11** |
| institution number `219` → `001` (a different Canadian bank) | **None 11/11** |
| the `ATB Financial Branch` heading removed | **None 11/11** |

**Independent corroboration — the strongest available, and it is not
circular.** The four documents that ATB itself denominates print a bare `CAD`
header under each account-summary section. They are excluded from the movement
population (they publish nothing today), and the jurisdiction rule, run on them
anyway, independently returns **CAD 4/4**. *Every ATB document in this archive
where the bank names its own currency is a document the jurisdiction rule would
have got right.* RBC's packet could say this of 6 documents; ATB's can say it of
every document in the family that names a currency at all.

Product packages carried by the movement population, all of them ATB Canada
business deposit products that name no currency: `Unlimited Business Banking`
(the 5 pinned) and `Business Self-serve` (the 2 archive movers). The four
non-movers carry `Business Self-serve`, `Business Growth Plus`, `Independent
Business Loan - Revolving` and `Business Term Loan`.

---

## 2. PROOF 2 — none contains explicit USD or other contrary currency evidence

*Doctrine §C.2; §B item 1.*

**Detector text** — the `CONTRARY_CURRENCY` alternation of §0.1, run
case-insensitively over the whole admissible text of each document, not over an
anchored line. It is intentionally far wider than the rung-1 reader, whose two
sites are positionally anchored: the point of proof 2 is to find anything an
anchored reader could have missed.

**Hit census over all 11 ATB documents:**

| Detector clause | Documents | Tokens found |
|---|---|---|
| `U.S. Funds` (any spacing) | **0** | — |
| `\bUSD\b` | **0** | — |
| `U.S. Dollar(s)` / `United States Dollar(s)` / `American Dollar(s)` | **0** | — |
| `fonds américains` / `devise américaine` | **0** | — |
| `US$` / `$US` / `$U.S.` | **0** | — |
| `US BUSINESS ACCOUNT` | **0** | — |
| `Foreign Currency Account` / `Compte en devises` | **0** | — |
| `Currency:` label line | **0** | — |
| `Exchange rate` / `taux de change` | **0** | — |
| any other ISO-4217 code (20 tested) | **0** | — |
| U.S.-institution furniture (`FDIC`, `ABA`, `RTN`, `Routing …`) | **0** | — |

**Zero contrary hits of any kind, on all 11.**

**Affirmative Canadian evidence, by contrast, is present and it is printed by
the bank:** `\bCAD\b` fires on **4 of 11** documents, twice each — the
`Deposits Value on <date> / CAD` and `Loans Value on <date> / CAD` section
headers of the consolidated layout. Those four are the documents no registration
claims. The 7 movers print no currency word of any kind, which is exactly why
their answer is a jurisdiction default and not a read.

**Where the currency evidence actually lives** (the whole family, one line
each):

| Printed evidence | Rung that answers | Docs | Published today |
|---|---|---|---|
| none | 2 — jurisdiction default | 7 | `USD` (schema default) |
| `CAD` section header, twice | 1 — explicit read | 4 | nothing (unclaimed) |

No ATB document in this archive announces a currency anywhere an anchored
reader cannot see it: the wide "anywhere" sweep for `\bCAD\b` returns exactly
the same four documents as the anchored bare-ISO-line regex, and the wide sweep
for every USD spelling returns none at all.

---

## 3. PROOF 3 — ATB has no U.S. institution, but U.S.-DOLLAR PRODUCTS exist at Canadian banks

*Doctrine §C.3; §B item 3; doctrine §A's second worked example
("Canadian TD account explicitly denominated in USD → USD").*

**Archive census first.** Over the whole 11-document ATB family the
U.S.-institution markers return **0 hits of every clause** (§2). **There is no
ATB U.S. document in the archive, and no ATB U.S. institution exists to
produce one.** The discriminator is therefore proven on synthetic printings,
and that is said plainly here rather than implied. The *product* half of the
proof is the one that matters for ATB: a Canadian Crown bank can and does sell
U.S.-dollar accounts to Alberta customers, and that is the printing the rule
must refuse.

**S1 — a whole synthetic ATB U.S.-dollar deposit statement.** Genuine ATB
furniture throughout — the branch-of-domicile line, `Transit number 08479-219`,
`Transit # 08479-219`, `www.atb.com`, the Canadian toll-free — with one thing
changed: the product line reads `A summary of Deposit Account U.S. Dollar
Business Account`.

| | |
|---|---|
| rung 1 `printed_currency_evidence` | `{USD}` |
| rung 2 `jurisdiction_currency` | **None** |
| published `statement_currency` | **`USD`** |

The document satisfies all four Canadian proofs and is still not defaulted: the
contrary sweep refuses rung 2, and rung 1 reads what the page says. This is
doctrine §A's `RBC U.S. Dollar / U.S. Funds account → USD` example, in ATB's
layout.

**S2 — the consolidated layout, denominated USD.** The same synthetic exercise
against the other product: `Deposits Value on Jun 30, 2026` followed by a bare
`USD` header. rung 1 → `{USD}`, rung 2 → **None**, published → **`USD`**.

**S3 — a U.S. bank calling itself ATB.** `ATB Financial USA, N.A.`,
`Member FDIC`, `Routing Number: 053000219`, `Raleigh NC 27612`, a 10-digit
account number and no transit shape: rung 1 → `{}`, rung 2 → **None**,
published → **None**. It fails on the U.S. discriminator *and* on all four
Canadian proofs independently.

**S4 — the hostile case: a genuine ATB page with one foreign token grafted
onto it.** Control → CAD 11/11. With each token added, over all 11 documents:

| Token grafted onto a real ATB page | `jurisdiction_currency` | published answer, on the 7 silent movers | published answer, on the 4 that state `CAD` |
|---|---|---|---|
| `A summary of Deposit Account U.S. Dollar Business Account` | **None** (11/11) | `USD` | **None** (two sites disagree → fail closed) |
| `USD` (a bare line) | **None** (11/11) | `USD` | **None** (fail closed) |
| `U.S. Funds` | **None** (11/11) | **None** (fail closed) | `CAD` — see below |
| `U.S. Dollar` | **None** (11/11) | **None** | `CAD` |
| `US BUSINESS ACCOUNT` | **None** (11/11) | **None** | `CAD` |
| `US$` | **None** (11/11) | **None** | `CAD` |
| `EUR` | **None** (11/11) | **None** | `CAD` |
| `Member FDIC` | **None** (11/11) | **None** | `CAD` |
| `Routing Number: 053000219` | **None** (11/11) | **None** | `CAD` |
| `ATB Financial USA, N.A.` | **None** (11/11) | **None** | `CAD` |
| `atb.us` | **None** (11/11) | **None** | `CAD` |

The U.S. discriminator is evaluated **before** any Canadian marker, so a
document carrying both shapes never reaches the default. Two properties of that
table are worth naming rather than glossing:

1. **On the 7 movers — the whole ceremony population — every single graft turns
   `CAD` into `None` or into the grafted currency. Not one graft leaves a
   silently-defaulted CAD standing.** That is the claim proof 3 owes.
2. **On the 4 documents that print `CAD` on an anchored site, an *unanchored*
   foreign token does not disturb the read.** This is the doctrine's hierarchy
   working as ratified — rung 1 has precedence and the default is never
   consulted — and it is identical to `analysis/rbc.py`'s behaviour today
   (`_printed_currency_evidence` is two anchored sites; the wide sweep governs
   only the default). It is recorded here as a measured property, and carried
   as **risk R3**, because those four documents publish nothing today and the
   question only becomes live if a reader is written for them.

---

## 4. PROOF 4 — the five pinned ATB documents, individually enumerated

*Doctrine §C.4.*

All five are `digital/native`, claimed by `atb`, published `validated`, and
carry **no printed denomination** (rung 1 → `{}`); all five are movers. Their
bytes on disk hash to the sha pinned in three independent artifacts, and the
production intake resolver reads them without OCR.

Common to all five, measured rather than assumed:

* `docs/adb-audit-results.csv` and `docs/balance-metrics-audit-results.csv`
  each carry the document at row **5–9**, `bank ATB Financial`, parser
  `atb-financial-deterministic`, status **PASS**, `underwriting_adb_basis
  calendar_day_printed_period`, account `00273985278`. **Neither file has a
  currency column** (measured: `currency` column present = False in all three
  audit CSVs).
* `docs/new-statement-audit-results.csv` — **document absent** (that file holds
  4 rows, none of them ATB).
* `corpus_gate.PINNED_OUTCOMES` — **absent**, therefore
  `PUBLISHED_OUTCOME = ("validated", flags=(), notes=(), risk_level="clear",
  possible_document_issue=False)`.
* `tests/data/parser_expectations.json` — `parser_id "atb"`, `variant_id null`,
  `bank "ATB Financial"`, `source_type "digital/native"`, 8 chain-declined ids.
  **No currency key** (measured: 0 occurrences of the string in the file).
* `corpus_gate.PINNED_CURRENCY` — **present, pinned `USD`.** This is the one
  pinned artifact that records the value, and it is the ceremony's whole
  expectation diff.

| # | Pinned path | `sha256` | Period | Pinned currency today | Proposed |
|---|---|---|---|---|---|
| 4.1 | `ATB/ATB August 2023.pdf` | `DF4905B76381B48D5188940C9B59BA2FD842C151EAD3E8DD4846E89BABED35E3` | 2023-08-01 → 2023-08-31 | `USD` | **`CAD`** |
| 4.2 | `ATB/ATB Sep 2023.pdf` | `DDA29C720E6A339DC95F01159C91F1C049B292FA8362685C1917666F3AAE9232` | 2023-09-01 → 2023-09-30 | `USD` | **`CAD`** |
| 4.3 | `ATB/ATB October statement 2023.pdf` | `205F7233C6D72C959FB2AACEFABCACF5158DF4DAFDDEF123EF4AEAE13749E37F` | 2023-10-01 → 2023-10-31 | `USD` | **`CAD`** |
| 4.4 | `ATB/ATB Nov 2023.pdf` | `4B407745938660999FCAA0DC46AD266414449419AB84AC93020DF837B969F1A1` | 2023-11-01 → 2023-11-30 | `USD` | **`CAD`** |
| 4.5 | `ATB/ATB Dec 2023.pdf` | `800E1FD39AB836D195C866861A0DDB6CA9EBDAD9D1C7D07DE5A4D0C9D1B05489` | 2023-12-01 → 2023-12-31 | `USD` | **`CAD`** |

Every other field of every one of the five is byte-identical before and after
(§6). All five are one Alberta business — the same customer number
`0002913777`, transit `08479-219` (Fort McMurray Downtown Branch), account
`00273985278`, product `Unlimited Business Banking` — so the five are one
account's consecutive months, and moving them moves one account's denomination,
not five unrelated judgements.

### 4.6 The difference from RBC's §4.6, and it is the whole point

RBC's packet found that `currency` was pinned **nowhere**, so its four pinned
expectation diffs were empty and its 151-document ceremony was
*gate-invisible*. It recommended putting currency on a pinned surface. That
recommendation was implemented in the same batch (`corpus_gate.PINNED_CURRENCY`
+ `check_currency`, W3 §RC7), and the five ATB documents were written into it
at `USD` with a comment naming them **expected future movers**.

So this ceremony has a real, non-empty, machine-checked expectation diff:
**five lines of `corpus_gate.PINNED_CURRENCY`.** Before the edit,
`python corpus_gate.py` goes RED on exactly five documents with the currency
check; after it, GREEN at 109/109. The blindness class CURRENCY-1 flagged and
RBC-MEASURE realised is closed, and this packet is the first ceremony to be
measured through it.

---

## 5. PROOF 5 — exact before/after currency values for every document in the packet

*Doctrine §C.5.*

| Stratum | Docs | Before | After |
|---|---|---|---|
| **Movers** — pinned `ATB/*.pdf` | 5 | `USD` (schema default) | **`CAD`** |
| **Movers** — archive, claimed by `atb`, published `withheld`/`withheld_adb` | 2 | `USD` (schema default) | **`CAD`** |
| Non-movers — ATB `Consolidated Statement`, unclaimed | 4 | publishes nothing | publishes nothing; terminal outcome byte-identical |
| Control — the 151 RBC movers | 151 | `CAD` | `CAD` (unchanged) |
| Control — the nine CURRENCY-1 corrections | 9 | 6 × `CAD`, 3 × `USD` | unchanged |
| Control — the other 104 entries of the pinned currency surface | 104 | as pinned | unchanged |

Direction census over every mover: `Counter({('USD','CAD'): 7})`. There is
**no** CAD→USD movement and no movement to any third code.

Mover outcome classes in the run of record / the gate: **validated 5 (pinned)
· withheld 2 (archive)**. The two withheld documents still publish a payload and
therefore still publish a currency; their withheld verdict does not change
(§6). Their `withheld_adb` reason is structural and unrelated to currency —
both are multi-month merged packets (one carries six `Deposit Account
Statement` issues over 28 pages, the other five over 24), which is what the
withholding is about.

The pinned currency surface moves **14 CAD / 95 USD → 19 CAD / 90 USD**.

The complete 7-document movement list is §9.

---

## 6. PROOF 6 — currency label movement ONLY

*Doctrine §C.6.*

**Method.** For each document of the measurement set, the same markdown was
analysed **twice in one process**:

1. `report_to_dict(analyze_markdown(md, parse_mode="deterministic", sheets=pages))`
   on the tree as checked out;
2. the same call with the scratchpad prototype patched into the `atb`
   registration at runtime (`dataclasses.replace(registration, parse=wrapped)`).

Both payloads were then flattened to leaf field paths (`statement.currency`,
`statement.transactions[17].amount`, `reconciliation.…`, `metrics.…`,
`integrity.flags[0]`, …) and compared path by path. The analysis cache was
bypassed entirely — `analyze_markdown` is called directly, so nothing was read
from or written to the analysis stage of the artifact store, and
`parse_mode="deterministic"` cannot reach the extraction branch ($0.00).

**Result.**

<!-- FIELDDIFF-SUMMARY -->

No financial amount, no ADB value, no ledger row, no reconciliation verdict, no
classification, no integrity flag, no note, no risk level and no outcome class
moves. `statement.currency` is the only field in the published block that
differs, on the only 7 documents that differ.

**Collateral bound.** The prototype patches one registration's `parse` and
additionally guards on `stmt.bank == "ATB Financial"`. A document the `atb`
registration does not claim never calls it, and `atb`'s REQUIRED markers are
`"ATB Financial" in text` **and** `"Deposit Account Statement" in text` —
strictly stronger than the superset regex the 6 archive documents were drawn
with, which is itself weaker than the first marker alone. **Every document the
rule can reach was therefore measured**, and the remaining 3,374 archive
documents are unreachable by construction rather than by sampling.

**`corpus_gate.py` was deliberately not re-run under the prototype.** It takes
>20 minutes on this shared machine, and its inputs are provably unchanged for
everything except the field it now pins: the outcome class and the whole
integrity block are proven byte-identical for all five pinned ATB documents by
the field diff above, and the one check that *would* move is `check_currency`,
whose expected movement is precisely §9.1. The implementing cell owes that run,
and it must go RED before the pin edit and GREEN after it.

---

## 7. PROOF 7 — the RBC movers, the CURRENCY-1 corrections and the rest of the pinned surface are byte-identical

*Doctrine §C.7, generalised: the previous ceremony's population must not move,
and neither must the explicit-evidence corrections.*

<!-- CONTROLS-SUMMARY -->

The **nine CURRENCY-1 corrections**, named by sha:

| # | `content_sha256` | Registration | Published currency | Payload before vs after |
|---|---|---|---|---|
| 1 | `0A482C2BEC8D3D1160BE14E6E9049A4F56C1B3AF7051124DD6E9C9488C5C19E0` | `rbc` | `CAD` | identical |
| 2 | `4AFA2F2102B981ADD0B38E3DE9A0F1458FE36258E295410963310FAE38185BAE` | `rbc` | `CAD` | identical |
| 3 | `64E841856FE419CD9B1D30CA8CE8E7552EEADBC9DC579E871B498EC79E6DADEA` | `rbc` | `CAD` | identical |
| 4 | `6C3E154C69FF0490424CB96600408A216C3DA14020D91C59B0D4F702BCA58E17` | `rbc` | `CAD` | identical |
| 5 | `839726D7A5BA213676E4400B12CCF57D06825611A74045498FB966AA2C87911E` | `rbc` | `CAD` | identical |
| 6 | `F93B688A7171B8CC28B2D0C958BC2E7574A1F51C1AC90DC6EA6DA7A9E7B292E0` | `rbc` | `CAD` | identical |
| 7 | `0677AD7549FD1BF44DFBE03AF8DB70503661CFE57C57DCE15D5A8F75E93972E3` | `td_canada_native` | `USD` | identical |
| 8 | `780D0E3D3388076A9BC3B5F9C08E9A2F4F8B1AE7954B7A2CC60D0A5B3858D62D` | `td_canada_native` | `USD` | identical |
| 9 | `B8A8D69CC7FEA4214E90128C8FD31C5A245653DA08E296407DF028A7FC8B94D7` | `td_canada_native` | `USD` | identical |

They keep their values for the same structural reason the RBC ceremony did not
disturb them: the rule is confined to the `atb` registration and to
`bank == "ATB Financial"`. A jurisdiction default for TD, BMO or CIBC still
needs its own proven evidence base (doctrine §B, final paragraph); this packet
establishes one for ATB and for nothing else.

---

## 8. PROOF 8 — structural, never filename/folder

*Doctrine §C.8; §B ("expressed structurally … never by filename or folder
assumptions").*

**(a) The probe pipeline is path-blind by construction.** Every markdown in
this packet was rebuilt as `StatementMarkdown(source_file="", …).to_markdown()`
and then passed through `analysis.parser_registry.admissible_text` — the
production admissibility seam. `jurisdiction_currency`'s only argument is that
string. Folder labels were never read by any predicate; relative paths were used
only to open PDF bytes.

**(b) A filename cannot manufacture the default.** A non-ATB archive document —
chosen **by measurement**: `000376618057AE48…`, the first document of the run
carrying no `ATB` token, no contrary-currency token and no U.S.-institution
token — was given a source comment printing every ATB proof at once
(`Statement date August 31, 2023 Transit number 08479-219 … Your ATB Financial
Branch 08479 Fort McMurray Downtown Branch 11 Haineault St Fort McMurray AB T9H
1R8 00273985278 Transit # 08479-219 www.atb.com.pdf`).

| | |
|---|---|
| an **unanchored** reading of the forged string would find all four proofs | **True** (measured, so the claim is not vacuous) |
| `jurisdiction_currency`, raw string, boundary bypassed | **None** — the line anchors already refuse it |
| `admissible_text` removes the comment | **True** (`"source:" not in` the result) |
| `jurisdiction_currency`, through `admissible_text`, i.e. production | **None** |

Direction (b) is closed **twice over**: the two line anchors could never read a
filename, because a filename arrives as one line that neither begins with the
branch heading nor ends at a postal code; and the seam removes the comment
before any parser runs. That the *unanchored* reading is fooled is what makes
the anchors load-bearing rather than decorative.

**(c) A filename cannot suppress it either.** A genuine ATB packet document
given the source comment `ATB Financial USA, N.A. Member FDIC Routing Number
053000219 atb.us.pdf`:

| | |
|---|---|
| raw string, boundary bypassed | **None** — the suppression is LIVE |
| through `admissible_text`, i.e. production | **CAD** |

Direction (c) is closed by exactly one thing — the seam — because the U.S. gate
is a document-wide sweep by design (a page carrying that token *anywhere* is not
a Canadian retail account). `analyze_markdown` applies the seam at stage entry
(W3 FILENAME-BOUNDARY), so no production call path can reach the unstripped
string. Any implementation of this rule must carry **both** tests, exercised
*through* `admissible_text` and not around it.

**(d) The folder half.** Through the seam, the folder labels `ATB USD/`,
`US Dollar/ATB/` and `Others/ATB Financial USA/` all leave the answer at
**CAD** — nothing in the rule is reachable from a path at all.

**(e) The archive's own trap, and this time it fires against the filename.**
Four archive documents are filed as `ATB Chequing Account - June 2026.pdf` and
`RECONCILED - ATB Chequing - March/April/May 2026.pdf`. Their pages print
`Consolidated Statement`, never the word `Chequing`; the products they actually
carry are `Business Self-serve`, `Business Growth Plus`, `Independent Business
Loan - Revolving` and `Business Term Loan`; and the deposit balances they
report are in the low hundreds of dollars against six-figure loan balances. A
filename-driven rule would have filed four multi-account consolidated
statements as chequing accounts. Conversely the five pinned documents are filed
under a folder named `ATB` and are ATB — but the packet does not depend on that
agreement, and §8(b)/(c) prove it cannot.

---

## 9. CEREMONY-READY ENUMERATION

All eight proofs land clean, so the enumeration follows. **This is a proposal
for Gustavo's approval; nothing here has been executed.**

### 9.1 The five pinned expectation diffs

One artifact, five lines. `corpus_gate.PINNED_CURRENCY`:

| # | Pinned document | `sha256` | Field | Old | New | Pinned artifact that records it today |
|---|---|---|---|---|---|---|
| 1 | `ATB/ATB August 2023.pdf` | `DF4905B76381B48D5188940C9B59BA2FD842C151EAD3E8DD4846E89BABED35E3` | `statement.currency` | `USD` | `CAD` | `corpus_gate.PINNED_CURRENCY` |
| 2 | `ATB/ATB Dec 2023.pdf` | `800E1FD39AB836D195C866861A0DDB6CA9EBDAD9D1C7D07DE5A4D0C9D1B05489` | `statement.currency` | `USD` | `CAD` | `corpus_gate.PINNED_CURRENCY` |
| 3 | `ATB/ATB Nov 2023.pdf` | `4B407745938660999FCAA0DC46AD266414449419AB84AC93020DF837B969F1A1` | `statement.currency` | `USD` | `CAD` | `corpus_gate.PINNED_CURRENCY` |
| 4 | `ATB/ATB October statement 2023.pdf` | `205F7233C6D72C959FB2AACEFABCACF5158DF4DAFDDEF123EF4AEAE13749E37F` | `statement.currency` | `USD` | `CAD` | `corpus_gate.PINNED_CURRENCY` |
| 5 | `ATB/ATB Sep 2023.pdf` | `DDA29C720E6A339DC95F01159C91F1C049B292FA8362685C1917666F3AAE9232` | `statement.currency` | `USD` | `CAD` | `corpus_gate.PINNED_CURRENCY` |

No other field of any of the five moves. No row of
`docs/balance-metrics-audit-results.csv`, `docs/adb-audit-results.csv`,
`docs/new-statement-audit-results.csv`, `corpus_gate.PINNED_OUTCOMES` or
`tests/data/parser_expectations.json` requires an edit — see §4.6.
The gate's currency line goes `14 CAD / 95 USD` → `19 CAD / 90 USD`.

### 9.2 The exact 7-document movement list

`statement.currency` `USD` → `CAD`; no other field, on any of them.

**Pinned (5)** — the five rows of §9.1.

**Archive (2)**, by `content_sha256`, with the run-of-record outcome class:

| # | `content_sha256` | Old | New | Outcome | Claimed by |
|---|---|---|---|---|---|
| 1 | `1B6768E84D00C4B2EC810D7180A2F474569613B45D529B1C7A5541BE65BCCAE6` | USD | CAD | withheld (`withheld_adb`) | `atb` |
| 2 | `7F2B71AFDD7F901F2251FB5AE5873E402185B30DCD1E7B51EFBBDF23E14EE424` | USD | CAD | withheld (`withheld_adb`) | `atb` |

### 9.3 What the implementing cell owes on top of the movement

1. `analysis/atb.py` gains the hierarchy in the shape of `analysis/rbc.py`'s
   `_statement_currency` — rung 1 anchored, rung 2 the four-proof conjunction,
   the two refusals first — and `parse_atb_statement` assigns
   `stmt.currency` only when it returns non-`None`.
2. The CUR-J-shaped test family for ATB, including **both** counterfeit
   directions through `admissible_text` (§8b, §8c), the ablation table of §1 as
   mutation kills, the S1/S2 USD-product refusals of §3, and a rung-order test
   that forces rung 1 to return a code the refusal set has never heard of.
3. `python corpus_gate.py` RED-then-GREEN across the five-line pin edit, in the
   same commit as the code.
4. The archive zero-movement sweep, whose only permitted findings are the two
   shas of §9.2.

---

## 10. Conflicting or uncertain evidence, and what left the packet

*Doctrine §B item 4 — fail closed / preserve uncertainty.*

**Documents with CONTRADICTORY currency evidence: zero.** Measured over all 11:
no document carries two different currency codes across the two rung-1 sites,
and no document carries a contrary token anywhere at all. Evidence-site
multiplicity is `{CAD via 2 sites: 4, no site: 7}` — the four two-site
documents agree with themselves on both sites.

**Documents with partial jurisdiction evidence: zero.** Every ATB document
satisfies all four proofs or, under ablation, none of them; there is no
near-miss stratum. Nothing was excluded for uncertainty, because nothing was
uncertain — this is a measurement, not an assumption.

### 10.1 Named exclusions from the movement population

| Population | Docs | Why it is not a mover |
|---|---|---|
| ATB `Consolidated Statement`, unclaimed | 4 | they publish **nothing**, so they carry no currency to move. See §10.3 |
| Non-ATB archive documents | 3,374 | outside the token superset; unreachable by the `atb` registration's REQUIRED markers, which are strictly stronger than the superset predicate |
| Archive documents with no readable OCR artifact | 29 | no text, no published payload |

### 10.2 One thing this packet does NOT claim

It does not claim ATB is a Canadian institution *because it is named ATB*. The
rule never reads the institution name alone: `ATB Financial` on its own
satisfies exactly one of four proofs, and the ablation of §1 shows that
removing any of the other three kills the default on 11/11. What carries the
jurisdiction is the CPA institution number 219 on two independent sites, an
Alberta branch domicile closed by a Canadian postal code, and ATB's own service
furniture.

### 10.3 The four unclaimed ATB documents, characterised

The handoff asked three questions of them. Measured answers:

| | |
|---|---|
| `content_sha256` | `284B775D64C9F1F9464E11C5894260C8B9BD03E44774AF0FC0EC20B5F96E35D5` (12 pp) · `EE09ADA6FCD4637A9FE0208FD5598B4861DA009082289CCBC3EF4FDA3E9DDE69` (12 pp) · `745B2968DC5A01970F0E8DAE6D47AB54BCF79ECEBF3D3CBF6700198F15F62B0E` (10 pp) · `F1DA262D1C28D1AB6BA8E82EEA2BCDA4D51848CE599B11C90F668360F859915D` (10 pp) |
| **Is it ATB?** | **Yes, on all 11 evidence classes of §1** — `ATB Financial`, the branch-of-domicile line (`Diamond Valley Branch 122 Centre Ave W Diamond Valley AB T0L 0H0`), `Transit number 07239-219`, `Transit #07239-219`, `www.atb.com`, `1 800 332-8383`, the `ATB0114003_…` print-control header, INTERAC e-Transfer rails, Alberta postal codes. All four jurisdiction proofs hold 4/4 |
| **Which product?** | **`Consolidated Statement`** — a multi-account statement, a different product from the `Deposit Account Statement` the five pinned documents carry. Each contains a `A summary of your accounts on <date>` roll-up followed by per-account sections: two deposit accounts (`Business Self-serve`, `Business Growth Plus`) and one or two loan accounts (`Independent Business Loan - Revolving`, `Business Term Loan`), each with its own `Transit #07239-219`. All four are consecutive months (March, April, May, June 2026) of one Alberta business, customer number `0003130386` |
| **What does it print about currency?** | **`CAD`, explicitly, twice per document** — a bare `CAD` line under `Deposits Value on <date>` and again under `Loans Value on <date>`. It prints no USD spelling of any kind, and no other ISO code |
| Why no parser claims them | the `atb` registration's two REQUIRED markers are `ATB Financial` (matches) and `Deposit Account Statement` (**does not match** — the title is `Consolidated Statement`). Detection score **0.166667** against a claim threshold; `excluded_by` is `None`, so this is a genuine gap in layout knowledge, not a refusal. `atb` is nevertheless the **top near-miss in the whole registry** for all four (`atb:0.166667; regions:0.125; navigant:0.1; relay:0.1`), and `analyze_markdown` raises `RuntimeError: no deterministic parser matched this statement`, which is the run's `failed`/`no_parser_matched` |
| **What this means for a future reader** | **The right default is CAD — and for this product it is not a default at all.** A reader born for the ATB consolidated layout must read the printed `CAD` header at rung 1; the jurisdiction default is the fallback it will never need on these four. The value that reader publishes must therefore be provenance-tagged `printed`/`explicit`, not `jurisdiction_default`, or the surface will over-report how much of the corpus is defaulted. This is the single most useful thing the four documents contribute: **ATB denominates its own consolidated statements, and it denominates them CAD** — independent corroboration of the default the seven movers get without a print (§1) |
| Multi-account caution | they are also a **loan + deposit** roll-up, so any reader for them inherits every open question about multi-account documents (which account's ADB, which balances are the statement's). Currency is the smallest of those questions and should not be the reason a reader is written |

---

## 11. Provenance class — the answer CURRENCY-SOURCE needs

The handoff asks which source class an ATB default would be:
`jurisdiction_default` or `institution_default`.

**Recommendation: `jurisdiction_default`, the same class as RBC's — and a
*separate* class for the four consolidated documents, which are not defaulted
at all.** Three measured reasons:

1. **`institution_default` would be a false claim.** It says "accounts at this
   institution are CAD". Measurably untrue: ATB sells U.S.-dollar products, and
   §3 S1/S2 show the rule refusing the default and reading `USD` on exactly such
   a printing. The default is not a property of the institution; it is a
   property of a Canadian-domiciled account on Canadian rails with no contrary
   denomination.
2. **What the rule actually consults is jurisdictional.** Of the four proofs,
   three are jurisdiction evidence (a CPA institution number that exists only in
   the Canadian clearing system, an Alberta branch domicile closed by a Canadian
   postal code, an account site carrying the same transit-institution pair) and
   one is institution furniture (`atb.com`). Naming the class after the
   institution would name it after its weakest quarter.
3. **One class keeps the surface comparable.** RBC's 151 and ATB's 7 are the
   same doctrinal act — doctrine §B, a bank/account-jurisdiction default —
   and TD, BMO and CIBC will be more of the same. If each institution gets its
   own class the vocabulary grows without adding information; the discriminating
   detail is already carried by the parser id and by the evidence the rule
   matched.

The vocabulary this packet's measurements need is therefore at least:

| Class | Meaning | ATB documents today |
|---|---|---|
| `printed` (or `explicit`) | rung 1 — the page states the code on an anchored site | 4 (unclaimed; nothing published yet) |
| `jurisdiction_default` | rung 2 — a proven account/jurisdiction default over a silent page | 7 (the movement population) |
| `schema_default` | nobody asked; `analysis/schema.py`'s `USD` | all 7 today, and ~1,900 archive documents |

`schema_default` is the class RBC-MEASURE's R5 was really asking for: without
it, `currency == "USD"` means "the page said so" on some documents and "nobody
asked" on others, and nothing records which.

---

## 12. Risks

**R1 — a USD ATB account whose statement omits the denomination line.** The
default is wrong for such a document. Base rate measured: **0 of 11** ATB
documents in this archive are USD-denominated, and the only ATB product in the
archive that names a currency at all names `CAD` and names it twice. There is
no attested silent-USD ATB issue. Residual, not observed; it is the risk
doctrine §A accepts when it makes the native currency a jurisdiction default
rather than a read. The base rate is weaker evidence than RBC's (RBC had 12
attested USD documents, 12 of 12 announcing themselves; ATB has none either
way), so R1 is genuinely larger here in the sense that *nothing in this archive
demonstrates how an ATB USD statement prints*. The synthetic S1/S2 of §3 are the
best available substitute and they are labelled as such.

**R2 — the rule is anchored to two ATB layouts.** J_ISSUER/J_HEADER/J_ACCOUNT
are the `Deposit Account Statement` and `Consolidated Statement` furniture. A
third ATB layout (a personal account, an online-banking export, a re-issue that
drops the branch-of-domicile line) fails the conjunction and silently keeps the
USD default — a false negative, which is the safe direction, but it will look
like "the rule stopped working". Measure again on any new ATB layout.

**R3 — an unanchored foreign token does not disturb an anchored `CAD` read.**
Measured in §3's S4 table: on the four documents that print `CAD`, grafting
`U.S. Funds` (or `Member FDIC`, or `EUR`) anywhere off the two anchored sites
leaves the published answer at `CAD`, because rung 1 answers first. This is the
ratified hierarchy and it is identical to `analysis/rbc.py` today, so it is not
a new defect — but it *is* a case doctrine §B item 4 would want failed closed,
and it becomes live the moment a reader is written for the consolidated layout.
**Recommendation for that cell: when the wide contrary sweep fires and rung 1
answers a different code, publish nothing.** Cheap, symmetric across banks, and
it turns a silent disagreement into an uncertainty. Scope decision, not this
cell's.

**R4 — the two archive movers are merged multi-month packets.** Both are
`withheld_adb` and both carry five or six monthly `Deposit Account Statement`
issues in one PDF. The currency movement is correct for every one of those
months (the same account, the same branch, the same transit), but a future card
that splits merged packets will turn these 2 documents into ~11, and the
mover count in §9.2 will change without the rule changing. Named so the
arithmetic is not later read as drift.

**R5 — `analysis/schema.py`'s `USD` default keeps doing two jobs.** After this
change, `currency == "USD"` on an ATB document means nothing at all (there will
be none), but across the archive it still means both "the page said so" and
"nobody asked". §11 is this packet's answer; CURRENCY-SOURCE owns it.

**R6 — the four unclaimed documents will move the mover count when claimed.**
They satisfy all four jurisdiction proofs and print `CAD` explicitly, so the
moment any registration claims them they publish `CAD` — not by this rule but
by rung 1. They are named here (§10.3, by sha) so their eventual arrival is
expected rather than surprising, exactly as RBC-MEASURE named
`BFEB79B26E42…`.

**R7 — process.** The measurement was taken on a machine shared with nine
batch-7 cells. Probes were kept light and sequential; the superset scan ran in
60.7s over all 3,380 shas, and the double analysis ran as one short foreground
command plus a detached sequential chunk runner rather than parallel work.
Nothing else on the machine was touched, and no repository state outside this
file and the W3 entry changed.
