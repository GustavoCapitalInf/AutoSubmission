# RBC CURRENCY MEASUREMENT PACKET — the doctrine §C eight-proof gate

**Cell:** RBC-MEASURE (batch 6, card 11). **READ-ONLY.** Branch
`wave6-rbcmeasure`, base `90e9eb6` (the doctrine commit). Nothing in this
repository changed except this file and the W3 log entry. No code edit, no
expectation edit, no cache write, no vendor call ($0.00).

**Verdict: all eight proofs land clean. The ceremony-ready enumeration is
§9.** The population is **exactly 151 documents** — 147 discovery + all 4
pinned English RBC statements — re-derived from the run of record and live
artifact replay, not inherited from the prior scouting.

---

## 0. Instrument, and why it can be trusted

| | |
|---|---|
| Code of record | worktree `.claude/worktrees/mt6-rbcmeasure` at `90e9eb6`; `git diff 90e9eb6 <main head>` is docs-only, so the analysis code is main's |
| Run of record | `discovery_reports/2026-08-16T000943.012887-0000-2e3ea385` (validated 2,430 / review 15 / withheld 63 / failed 859 / deferred 13; 3,506 rows, **3,380 distinct shas**) |
| Text source | the D-3 OCR artifact store, addressed **by direct file path** — `<data_dir>/artifacts/ocr/<key[:2]>/<key>.json`, key recomputed from `cache_key("ocr", content_sha256, ocr_settings_key(...))`. The `webapp_data` sqlite index was never opened |
| Coverage | 3,351 of 3,380 shas carry a readable OCR artifact (16 have no artifact at all, 13 hold a cached negative — the run's deferred). All three OCR partitions were probed per document; the run of record served from `offline_scanned` |
| Filename blindness | every markdown was rebuilt as `StatementMarkdown(source_file="", …).to_markdown()` and then passed through `analysis.parser_registry.admissible_text`. No probe predicate ever saw a filename or a folder label. Paths were used only to open bytes, never as evidence |
| Family population | **live detection replay**, never `rows.csv parser_id` alone: `analysis.parser_registry.resolve()` re-run over every stored markdown. Live verdict agreed with the run's `parser_id` on **228/228** documents of the RBC superset — the DISCOBS projection holds |
| Fidelity check A | for all five pinned RBC PDFs, the cached artifact's markdown and page list are **identical** to a fresh `ocr.pipeline.parse_statement` read of the bytes on disk, and each PDF's on-disk sha matches its manifest sha |
| Fidelity check B | on a 30-document RBC sample, this cell's before-payload reproduces the run of record's own `outcome_class` **30/30** |
| Prototype | a scratchpad-only runtime monkey-patch of the `rbc` registration's `parse`. No repository file was modified to obtain any number in this packet |

The RBC superset was found by scanning **all 3,351** readable artifacts for any
RBC-shaped token (`ROYAL BANK OF CANADA`, `BANQUE ROYALE`, `\bRBC\b`,
`RBCBANK`, `ROYALBANK`, `RBBDA`): **228 documents**. That superset is strictly
weaker than the `rbc` registration's own REQUIRED marker
(`"ROYAL BANK OF CANADA" in upper(text)`), so **every document the rule could
possibly reach is inside it** — which is what makes the movement measurement
below total over the archive rather than a sample.

Live dispatch inside the superset: `rbc` 165 · `rbc_french` 19 · unclaimed 16 ·
`td_canada_native` 11 · `cibc` 6 · `releve_facturation` 6 · `bmo_ca_business` 3
· `chase` 2. Adding the 5 pinned RBC statements (not in the discovery rows)
gives the RBC family of record: **169 English + 20 French = 189**.

### 0.1 The rule as measured (the prototype)

Doctrine §B is a bank/account-**jurisdiction** default, not `absence of
"U.S. Funds" ⇒ CAD`. The prototype therefore never reasons from an absence
alone: it requires four *affirmative* structural proofs, all printed by the
document, and it refuses on any contrary or U.S. evidence **before** it looks
at them.

```
jurisdiction_currency(markdown) -> "CAD" | None
    if US_INSTITUTION matches      -> None      # doctrine B item 3, checked FIRST
    if CONTRARY_CURRENCY matches   -> None      # doctrine B items 1 and 4
    if not (J_ISSUER and J_SERVICE and J_ACCOUNT and J_BRANCH) -> None
    else                           -> "CAD"     # doctrine B item 2
```

* **J_ISSUER** — a line naming `ROYAL BANK OF CANADA` that closes with a
  Canadian postal code: the statement-issuing centre
  (`P.O. BOX 4047 TERMINAL A TORONTO ON M5W 1L5`,
  `P.O. BAG SERVICE 2650 CALGARY AB T2P 2M7`).
* **J_SERVICE** — RBC **Canada's own** service furniture: `rbcroyalbank.com`
  and/or the Canadian toll-free `1-800-769-2520` / `1-800-769-2511`
  (`1-800-ROYAL`). RBC's U.S. bank publishes `rbcbank.com` and a different
  toll-free; the domain is the cleanest institution discriminator the
  documents print.
* **J_ACCOUNT** — the Canadian Payments Association account shape in both
  product spellings the family prints: business `Account number: <5-digit
  transit> <3-3-1>`, personal `Your account number: <5-digit transit>-<7
  digits>`. A U.S. deposit account has no transit number of this shape.
* **J_BRANCH** — the branch-of-domicile line under the account-summary
  heading: `Royal Bank of Canada <civic address>, <province> <Canadian postal
  code>`.
* **US_INSTITUTION** — `rbcbank.com` · `RBC Bank (Georgia)` · `RBC Bank USA` ·
  `RBC Bank, N.A.` · `Royal Bank of Canada (USA)` · `RBC Centura` ·
  `Member FDIC` / `FDIC` · `ABA` · `Routing #/No./Number/Transit` · `RTN` ·
  `Raleigh, NC`.
* **CONTRARY_CURRENCY** — deliberately *wider* than any production reader:
  `U.S. Funds` (any spacing) · `\bUSD\b` · `U.S. Dollar(s)` ·
  `United States Dollar(s)` · `American Dollar(s)` · `fonds américains` ·
  `devise américaine` · `US$` / `$US` / `$U.S.` · `US BUSINESS ACCOUNT` · and
  the standalone ISO codes EUR GBP CHF JPY AUD NZD MXN HKD CNY RMB INR SGD ZAR
  SEK NOK DKK PLN AED BRL PHP.

The patched reader also refuses outright whenever
`analysis.rbc._printed_currency`'s evidence set is **non-empty** — including
the two-code contradiction case, where the explicit reader returns `None`.
The jurisdiction default never resolves an ambiguity; it only speaks where the
page is silent (doctrine §B item 4, fail closed).

---

## 1. PROOF 1 — every affected document is an RBC **Canada** account/product

*Doctrine §C.1; §B item 2 ("a proven RBC Canada account/product").*

**Census over the RBC family of 189** (English 169 + French 20), by structural
evidence class, measured on printed text only:

| Evidence class | Marker measured | Docs |
|---|---|---|
| Institution identity (EN) | `ROYAL BANK OF CANADA` | 169 |
| Institution identity (FR) | `BANQUE ROYALE (DU CANADA)` | 20 |
| **J_ISSUER** issuer line + Canadian postal code | line-anchored | 169 EN |
| **J_SERVICE** `rbcroyalbank.com` | | 169 EN |
| **J_SERVICE** Canadian toll-free `1-800-769-25xx` / `1-800-ROYAL` | | **189 (all)** |
| **J_ACCOUNT** CPA transit shape (both product spellings) | | 151 packet, 157 business-spelling |
| **J_BRANCH** branch domicile line + Canadian postal code | line-anchored | 169 EN |
| Canadian postal code anywhere | | **189 (all)** |
| Canadian payment rails `INTERAC` | | 137 |
| Canadian payment rails `e-Transfer` | | 150 |
| Canadian orthography `Chequing` / `Cheques` | | 169 EN |
| RBC print-control mailing header (`RBBDA…` / `RBPDA…`) | | 176 |

**Over the 151-document packet, all four jurisdiction proofs hold on
151/151.** This is not a residual claim from the census — it is the direct
consequence of §6: the prototype requires the conjunction, and exactly the 151
moved.

**Ablation (the conjunction is load-bearing, not decorative).** Over the first
40 packet documents, removing one evidence class at a time:

| Mutation | `jurisdiction_currency` |
|---|---|
| control (unmodified) | CAD 40/40 |
| Canadian postal code stripped from every `Royal Bank of Canada` line | **None 40/40** |
| `rbcroyalbank.com` + every toll-free neutralised | **None 40/40** |
| `Account number:` / `Your account number:` relabelled | **None 40/40** |
| branch-domicile line removed | **None 40/40** |

**Independent corroboration.** The 6 English documents on which RBC *states*
`CAD CHEQUING ACCOUNT` in its mailing header are excluded from the packet (the
explicit reader already publishes CAD for them) — and the jurisdiction rule,
run on them anyway, independently returns **CAD 6/6**. Every document where
the bank names its own currency as CAD is a document the jurisdiction rule
would have got right.

Product packages carried by the packet, all of them RBC Canada retail/business
products that name no currency: `RBC Digital Choice Business`,
`RBC Ultimate Business`, `Business Current Account`, `RBC Advantage Banking`.
Layout split: **135 business + 12 personal** discovery, **4 business** pinned.

---

## 2. PROOF 2 — none contains explicit USD or other contrary currency evidence

*Doctrine §C.2; §B item 1.*

**Detector text** — the `CONTRARY_CURRENCY` alternation in §0.1, run
case-insensitively over the whole admissible text of each document, not over an
anchored line. It is intentionally far wider than
`analysis/rbc.py::_printed_currency`, whose two sites are positionally
anchored: the point of proof 2 is to find anything the production reader could
have missed.

**Hit census over the 151-document packet:**

| Detector clause | Documents | Tokens found |
|---|---|---|
| `U.S. Funds` (any spacing) | **0** | — |
| `\bUSD\b` | **0** | — |
| `U.S. Dollar(s)` / `United States Dollar(s)` / `American Dollar(s)` | **0** | — |
| `fonds américains` / `devise américaine` | **0** | — |
| `US$` / `$US` / `$U.S.` | **0** | — |
| `US BUSINESS ACCOUNT` | **0** | — |
| `USD ACCOUNT` / `U.S. DOLLAR ACCOUNT` / `FOREIGN CURRENCY ACCOUNT` / `COMPTE EN DEVISES` | **0** | — |
| `Currency:` label line | **0** | — |
| `Exchange rate` / `taux de change` | **0** | — |
| any other ISO-4217 code (18 tested) | **0** | — |

**Zero hits of any kind, on all 151.** Affirmative *Canadian* currency wording
is also absent (`\bCAD\b` 0, `Canadian Dollar` 0, `$CDN` 0) — which is exactly
why this is a jurisdiction default and not a read.

**Where the currency evidence actually lives** (the 18 English documents
excluded from the packet, and the reason the packet is 151 and not 169):

| Printed evidence | Reader's answer | Docs |
|---|---|---|
| `U.S. Funds` denomination line only | USD | 6 |
| `U.S. Funds` line **and** `US BUSINESS ACCOUNT` in the mailing header | USD | 6 |
| `CAD CHEQUING ACCOUNT` in the mailing header | CAD | 6 |

Every USD-denominated RBC document in the archive announces itself on a
positionally-anchored line, and **half of them announce it twice on two
independent sites**. No document announces a currency anywhere the anchored
reader cannot see it: the wide "anywhere" sweep for `U.S. Funds` returns
exactly the same 12 documents as the anchored line regex.

---

## 3. PROOF 3 — RBC U.S. institution/products cannot be swept in

*Doctrine §C.3; §B item 3.*

**Archive census first.** Over the whole 228-document RBC superset — not just
the family — the RBC-U.S. institution markers return:

| Marker | Hits in the RBC family (189) | Hits in the whole superset (228) |
|---|---|---|
| `rbcbank.com` | 0 | **0** |
| `RBC Bank (Georgia)` / `RBC Bank Georgia` | 0 | **0** |
| `RBC Bank USA` / `RBC Bank, N.A.` | 0 | **0** |
| `Member FDIC` / `FDIC` | 0 | 2 (both `chase`) |
| `Routing` / `ABA` / `RTN` | 0 | 5 (2 `chase`, 3+1 `td_canada_native`) |
| `Checking` (U.S. orthography) | 0 | 2 (both `chase`) |
| `Raleigh` | 0 | **0** |

**There is no RBC U.S. document in the archive.** The discriminator is
therefore proven on synthetic printings, and that is said plainly here rather
than implied.

**S1 — a full synthetic RBC Bank (Georgia), N.A. statement** carrying the same
`Business Account Statement` furniture, a 10-digit account number, a routing
number, `Member FDIC` and `www.rbcbank.com`: `jurisdiction_currency` →
**None**. It fails on the U.S. discriminator *and* on all four Canadian
proofs independently.

**S2 — the hostile case: a genuine Canadian packet document with one U.S.
token grafted onto it.** Control (unmodified) → CAD. With each token added:

| Token grafted onto a real Canadian RBC page | Result |
|---|---|
| `www.rbcbank.com` | **None** |
| `Member FDIC` | **None** |
| `RBC Bank (Georgia), N.A.` | **None** |
| `Routing Number: 063216608` | **None** |
| `RBC Bank USA` | **None** |
| `Raleigh, NC 27612` | **None** |

The U.S. discriminator is evaluated **before** any Canadian marker, so a
document carrying both shapes fails closed rather than being swept in on the
strength of its Canadian half.

**S4 — explicit other-currency evidence on a Canadian page** (the second half
of doctrine §B item 1): `+ U.S. Funds` → None · `+ USD` → None ·
`+ U.S. Dollar` → None · `+ US BUSINESS ACCOUNT` → None · `+ EUR` → None.

---

## 4. PROOF 4 — the four pinned RBC documents, individually enumerated

*Doctrine §C.4.*

All four are `digital/native`, claimed by `rbc`, published `validated`, and
carry **no printed denomination** (`_printed_currency` → `None`); all four are
inside the packet. Their bytes on disk hash to their manifest shas, and their
cached artifacts reproduce a fresh production intake read exactly (§0).

### 4.1 `RBC/Chequing Statement-DEC+.pdf`
* `sha256` `A26ECE4F32488CECDD59EA5BCF13B4947786456038CBDD17AC52C0F3D9F38EE5`
* Pinned expectations today:
  * `docs/balance-metrics-audit-results.csv` row 80 — bank `Royal Bank of Canada`, parser `royal-bank-of-canada-deterministic`, period `2025-12-01 to 2026-01-02`, opening `13785.29`, ending `21014.56`, status `PASS`, `underwriting_adb_basis calendar_day_printed_period`. **No currency column exists in this file.**
  * `docs/adb-audit-results.csv` row 80 — `backend_adb 9977.51`, `calendar_days 33`. **No currency column.**
  * `docs/new-statement-audit-results.csv` — **document absent** from this audit.
  * `corpus_gate.PINNED_OUTCOMES` — **absent**, therefore `PUBLISHED_OUTCOME = ("validated", flags=(), notes=(), risk_level="clear", possible_document_issue=False)`.
  * `tests/data/parser_expectations.json` — `parser_id "rbc"`, `variant_id null`, `bank "Royal Bank of Canada"`, 28 chain-declined ids. **No currency key.**
* Proposed movement: published `statement.currency` **`USD` → `CAD`**. Every field above is byte-identical before and after (§6).

### 4.2 `RBC/Chequing Statement-JAN+.pdf`
* `sha256` `633F036CDE97F639D95538678B738E939E708254C99D9910F6202CB44C1FD2D3`
* Pinned expectations today: balance-metrics row 82 (period `2026-01-02 to 2026-02-02`, opening `21014.56`, ending `171.86`, `PASS`); ADB row 82 (`backend_adb 3896.40`, 32 days); absent from the new-statement audit; absent from `PINNED_OUTCOMES` (⇒ `PUBLISHED_OUTCOME`); `parser_expectations.json` `parser_id "rbc"`. **No currency in any of them.** This is the document whose ledger prints `Funds transfer credit TT KM CAPITAL C` — the posting that would counterfeit a denomination for an unanchored reader (W3 §CURRENCY, CUR2.3); the anchored reader and this packet's wide sweep both read it as nothing.
* Proposed movement: `statement.currency` **`USD` → `CAD`**, nothing else.

### 4.3 `RBC/Chequing Statement-FEB+.pdf`
* `sha256` `F0348F3EDD0F64284AD49632C9FF5414C60113A79B0A3356E2441B1CB2E7CA27`
* Pinned expectations today: balance-metrics row 81 (period `2026-02-02 to 2026-03-02`, opening `171.86`, ending `-216.54`, `PASS`); ADB row 81 (`backend_adb 6629.84`, 29 days); absent from the new-statement audit; absent from `PINNED_OUTCOMES`; `parser_expectations.json` `parser_id "rbc"`. **No currency in any of them.**
* Proposed movement: `statement.currency` **`USD` → `CAD`**, nothing else.

### 4.4 `RBC/Chequing Statement-MAR+.pdf`
* `sha256` `4F3CC713463FDD59318770C037FB0786FB984FB1A169456B068AE735D64EFD77`
* Pinned expectations today: balance-metrics row 83 (period `2026-03-02 to 2026-04-01`, opening `-216.54`, ending `-6393.90`, `PASS`); ADB row 83 (`backend_adb 3993.35`, 31 days); absent from the new-statement audit; absent from `PINNED_OUTCOMES`; `parser_expectations.json` `parser_id "rbc"`. **No currency in any of them.**
* Proposed movement: `statement.currency` **`USD` → `CAD`**, nothing else.

### 4.5 The fifth pinned RBC document does NOT move
`RBC French/12 - Relevé Royale Décembre 2025 - Tommy Aspirot.pdf`,
`sha256 874D48BFEE1B41B56425EBE732CCDB73E30ECC30289D26CE5B28B3854A9A84DD`,
is claimed by `rbc_french` (`variant_id "rbc_french"`, bank
`Banque Royale du Canada`) and already publishes **CAD** from the French
reader. Before/after payload: **byte-identical, zero fields changed.**

### 4.6 The finding Ocean must rule on
**`currency` is not a pinned column anywhere.** Measured directly:
`adb-audit-results.csv` currency column = False · `balance-metrics-audit-results.csv`
= False · `new-statement-audit-results.csv` = False · `corpus_gate.py` contains
the string `currency` **zero** times · `parser_expectations.json` contains it
**zero** times. So the four pinned expectation diffs are, in every pinned
artifact, **empty** — the movement is real, user-visible, and **gate-invisible**.
That is precisely the blindness class CURRENCY-1 flagged at §CUR4.2, now
realised. See §10 R3.

---

## 5. PROOF 5 — exact before/after currency values for every packet document

*Doctrine §C.5.*

| Stratum | Docs | Before | After |
|---|---|---|---|
| Packet — discovery | 147 | `USD` (schema default) | **`CAD`** |
| Packet — pinned English RBC | 4 | `USD` (schema default) | **`CAD`** |
| Excluded — `U.S. Funds` / `US BUSINESS ACCOUNT` | 12 | `USD` (read) | `USD` (unchanged) |
| Excluded — `CAD CHEQUING ACCOUNT` | 6 | `CAD` (read) | `CAD` (unchanged) |
| French RBC (incl. 1 pinned) | 20 | `CAD` (French reader) | `CAD` (unchanged) |
| Non-RBC superset (`td_canada_native`, `cibc`, `releve_facturation`, `bmo_ca_business`, `chase`) | 28 | — | unchanged |
| Unclaimed inside the superset | 16 | publishes nothing | publishes nothing, terminal outcome byte-identical |

Direction census over every mover: `Counter({('USD','CAD'): 151})`. There is
**no** CAD→USD movement and no movement to any third code.

Packet outcome classes in the run of record: **validated 141 · withheld 6 ·
pinned (not in discovery rows) 4**. The six withheld documents still publish a
payload and therefore still publish a currency; their withheld verdict does not
change (§6).

The complete 151-document movement list is §9.

---

## 6. PROOF 6 — currency label movement ONLY

*Doctrine §C.6.*

**Method.** For each of 236 documents (the 228-document RBC superset ∪ the nine
CURRENCY-1 corrections ∪ the five pinned RBC documents), the same markdown was
analysed **twice in one process**:

1. `report_to_dict(analyze_markdown(md, parse_mode="deterministic", sheets=pages))` on the tree as merged;
2. the same call with the scratchpad prototype patched into the `rbc`
   registration at runtime.

Both payloads were then flattened to leaf field paths (`statement.currency`,
`statement.transactions[17].amount`, `reconciliation.…`, `metrics.…`,
`diagnostics.integrity_flags[0]`, …) and compared path by path. The analysis
cache was bypassed entirely — `analyze_markdown` is called directly, so nothing
was read from or written to the analysis stage of the artifact store.

**Result.**

| | |
|---|---|
| Documents compared | 236 (220 parsed + 16 terminal) |
| Leaf field comparisons | **5,316,842** |
| Median payload size | 17,500 leaf fields |
| Documents with any payload change | **151** |
| **Distinct changed field paths across the entire sweep** | **1 — `statement.currency`** |
| Documents with a NON-currency change | **0** |
| Terminal-outcome documents whose failure text changed | **0/16** |

No financial amount, no ADB value, no ledger row, no reconciliation verdict, no
classification, no integrity flag, no note, no risk level and no outcome class
moves. `statement.currency` is the only field in the published block that
differs, on the only 151 documents that differ.

**Collateral bound.** The prototype patches one registration's `parse` and
additionally guards on `stmt.bank == "Royal Bank of Canada"`. A document the
`rbc` registration does not claim never calls it, and `rbc`'s REQUIRED marker
is `"ROYAL BANK OF CANADA" in upper(text)` — strictly stronger than the
superset regex the 228 were drawn with. **Every document the rule can reach was
therefore measured**, and 3,123 archive documents outside the superset are
unreachable by construction rather than by sampling.

**Existing test-suite delta.** `tests/test_rbc_variants.py`,
`tests/test_analysis.py`, `tests/test_r1_hardcodes.py`,
`tests/test_transaction_classifier.py`,
`tests/test_lender_insurance_classification.py` — **414 passed** on the merged
tree and **414 passed** with the prototype active (`-p no:cacheprovider`, no
cache written). Not one existing assertion moves, including
`test_cur_a_document_stating_no_denomination_keeps_the_default`: its synthetic
`HEAD` fixture prints `ROYAL BANK OF CANADA` on a bare line with no postal
code, no `rbcroyalbank.com`, no transit-shaped account and no branch line, so
the jurisdiction proof correctly refuses it. The rule is tight enough that a
stripped fixture is not mistaken for a proven Canadian account.

`corpus_gate.py` was **not** re-run under the prototype: it takes >10 minutes on
this shared machine, and its input is provably unchanged — the gate reads the
outcome class and the integrity block, both proven byte-identical for all five
pinned RBC documents by the field diff above, and `corpus_gate.py` contains no
reference to `currency` at all. The implementing cell must still run it.

---

## 7. PROOF 7 — the nine CURRENCY-1 corrections remain byte-identical

*Doctrine §C.7.* All nine were re-analysed before and after; **all nine
payloads are byte-identical, zero changed field paths.**

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

The six `rbc` corrections keep `CAD` because the explicit reader still wins
(their mailing header prints `CAD CHEQUING ACCOUNT`, so the prototype's
`found`-set guard returns before the jurisdiction default is consulted) — the
explicit read is not silently replaced by an agreeing default. The three
`td_canada_native` corrections keep `USD` because the rule is confined to the
`rbc` registration and to `bank == "Royal Bank of Canada"`; a jurisdiction
default for TD would need its own proven evidence base (doctrine §B, final
paragraph).

---

## 8. PROOF 8 — structural, never filename/folder

*Doctrine §C.8; §B ("expressed structurally … never by filename or folder
assumptions").*

**(a) The probe pipeline is path-blind by construction.** Every markdown in
this packet was rebuilt as `StatementMarkdown(source_file="", …).to_markdown()`
and then passed through `analysis.parser_registry.admissible_text` — the
production admissibility seam. `jurisdiction_currency`'s only argument is that
string. Folder labels were never read by any predicate; relative paths were
used only to open PDF bytes in the two fidelity checks of §0.

**(b) A filename cannot manufacture the default.** A non-RBC document whose
*filename* prints every Canadian proof at once
(`ROYAL BANK OF CANADA P.O. BOX 4047 TERMINAL A TORONTO ON M5W 1L5 Account
number: 01842 104-547-5 Royal Bank of Canada 1 MAIN ST, ON L6Y 5X6
rbcroyalbank.com.pdf`) is a **live counterfeit** — measured:

| | |
|---|---|
| raw string, boundary bypassed | **CAD** (the counterfeit works) |
| through `admissible_text`, i.e. production | **None** |

**(c) A filename cannot suppress it either.** A genuine packet document whose
filename prints `RBC Bank (Georgia), N.A. Member FDIC www.rbcbank.com Routing
Number 063216608.pdf`:

| | |
|---|---|
| raw string, boundary bypassed | **None** (the counterfeit suppresses) |
| through `admissible_text`, i.e. production | **CAD** |

Both directions are live, and `admissible_text` closes both. `analyze_markdown`
applies that seam at stage entry (W3 FILENAME-BOUNDARY), so no production call
path can reach the unstripped string. Any implementation of this rule must
carry both tests, exercised **through** `admissible_text` and not around it —
this is the discriminating form CURRENCY-1's review (D-4) had to correct.

**(d) The archive's own trap, found while measuring.** Seven archive documents
are filed under names spelling the U.S. product word — `Business Checking
Statement-5998 …`. Their pages print `ROYAL BANK OF CANADA P.O. BAG SERVICE
2650 CALGARY AB T2P 2M7`, `RBC Ultimate Business TM account package`,
`www.rbcroyalbank.com/business`, a Calgary branch line and a CPA transit
account: they are RBC **Canada** business accounts and they are in the packet.
A folder- or filename-driven rule would have excluded seven correct movers on
an operator's spelling. Conversely six documents filed as `USD Statement-1046
…` print `U.S. Funds` **and** `US BUSINESS ACCOUNT` and are correctly excluded
on the page, not on the name. The names and the pages happen to agree here; the
packet does not depend on that agreement.

---

## 9. CEREMONY-READY ENUMERATION

All eight proofs land clean, so the enumeration follows.

### 9.1 The four pinned expectation diffs

| # | Pinned document | `sha256` | Field | Old | New | Pinned artifact that records it today |
|---|---|---|---|---|---|---|
| 1 | `RBC/Chequing Statement-DEC+.pdf` | `A26ECE4F32488CECDD59EA5BCF13B4947786456038CBDD17AC52C0F3D9F38EE5` | `statement.currency` | `USD` | `CAD` | **none** |
| 2 | `RBC/Chequing Statement-JAN+.pdf` | `633F036CDE97F639D95538678B738E939E708254C99D9910F6202CB44C1FD2D3` | `statement.currency` | `USD` | `CAD` | **none** |
| 3 | `RBC/Chequing Statement-FEB+.pdf` | `F0348F3EDD0F64284AD49632C9FF5414C60113A79B0A3356E2441B1CB2E7CA27` | `statement.currency` | `USD` | `CAD` | **none** |
| 4 | `RBC/Chequing Statement-MAR+.pdf` | `4F3CC713463FDD59318770C037FB0786FB984FB1A169456B068AE735D64EFD77` | `statement.currency` | `USD` | `CAD` | **none** |

No other field of any of the four moves. `RBC French/12 - Relevé Royale
Décembre 2025 - Tommy Aspirot.pdf` does not move at all. No row of
`docs/balance-metrics-audit-results.csv`, `docs/adb-audit-results.csv`,
`docs/new-statement-audit-results.csv`, `corpus_gate.PINNED_OUTCOMES` or
`tests/data/parser_expectations.json` requires an edit — see §4.6 and §10 R3.

### 9.2 The exact 151-document movement list

`statement.currency` `USD` → `CAD`; no other field, on any of them.

**Pinned (4)** — the four rows of §9.1.

**Discovery (147)**, by `content_sha256`, with the run-of-record outcome class:

| # | `content_sha256` | Old | New | Outcome |
|---|---|---|---|---|
| 1 | `0101AD95D22D851131C4CFD6A7A1C57F0BC9B4C984143B602FC374A6400C5996` | USD | CAD | validated |
| 2 | `0101D6A7E9D283923E82256F758AE6EB3DE29CE845CE7652C5A8A2A2E254A5CA` | USD | CAD | validated |
| 3 | `028164D44DFA0155169DCADC31F73F0A49CE170FA67D87C7D329544F7C134CB8` | USD | CAD | validated |
| 4 | `0625F68507B4EF35AE73F87EA493F5F6541BCDA067BE7D6853AA5EE53C04ED5B` | USD | CAD | validated |
| 5 | `072A8973A8C2D06B727135D6CF900768E55DAB587477237D793F95F3856D8B47` | USD | CAD | validated |
| 6 | `0C674DA9C5EEB9BFA93C14888A17411DC47321A9BF8D997B15FE48FEDBB03507` | USD | CAD | validated |
| 7 | `0D8C93432FCED4A75AD34916B3E84D63F0BC1C428116B2BF3613017AF6A886BA` | USD | CAD | validated |
| 8 | `0FA2CDFD38102E6DD695C14276B831039328B13580D341E6DE50180785BB5C37` | USD | CAD | validated |
| 9 | `12A8D6F58B59266A522729D52E39D1E6D168D760082D995A1D221EEEAEFB7A16` | USD | CAD | validated |
| 10 | `142E1DB7CB103EFBB0053460F71867801C9260FFF1FF5B0383D616BB53ED1573` | USD | CAD | withheld |
| 11 | `16174BD143C4702DDA57DE3AFC48F81DD4A447231E32ECEB76ED62DAB2828785` | USD | CAD | withheld |
| 12 | `1623886A99296D5C046334BF049249848E9F8CEDEC0976E4BD4BF12985B16995` | USD | CAD | validated |
| 13 | `16A90E6CA41EBF585108595FA99369A63AFDFD91D25C92DACC2D5EFCB2CF554E` | USD | CAD | validated |
| 14 | `18DF1A8EB703BBFB6F829BFDB0AD3102C6F0A2E5323AA1FA0140B5C0AE362C15` | USD | CAD | validated |
| 15 | `19A60EAA05FFEA97E2AAA6BE8291BC2B14A46B1B1C7C40DA0CDAABB8737D35AB` | USD | CAD | validated |
| 16 | `1A3119AFE41C09F6F50CB86C5F78C919963BF4DA9C44F9D0846CC3424C677F66` | USD | CAD | validated |
| 17 | `1B8A93366E3549192B58699E12DF8F76322DE8C83FDDB50D1A5FF9BE26F988F7` | USD | CAD | validated |
| 18 | `1F414F353A7D99A28C2FF6F59F12B92CBA792B2B0437EDEF164020EC89EA5DA1` | USD | CAD | validated |
| 19 | `203B50C826357D658B62D4EED4AA66DD978588913D18A295A23553B087AC08C9` | USD | CAD | validated |
| 20 | `203F979300CFF714394ED08E17342847A4838FAD1C5BB262C7C3E537D0016765` | USD | CAD | validated |
| 21 | `22AD80991DCF103B6A830BA3F7C4A880F2994369BE136859F64A2E72D3CCC989` | USD | CAD | validated |
| 22 | `22D404DECA726B25D6F1A6C4CBFDB0F88F11C019030C1B5779A61E79C9621B02` | USD | CAD | validated |
| 23 | `22F4EEA87D992F755E97CFB861D4C8144DC4BCAE388C503C36C19ADE69CEA07C` | USD | CAD | validated |
| 24 | `2344F765B1EFEFC0175ECF441B741ACBC20FE4827607301CC081EDD700A21D78` | USD | CAD | validated |
| 25 | `2534F6F76ED58975CD61B5BAFCEA5E8C5007063CFDA52A62E1F9EED00012F868` | USD | CAD | validated |
| 26 | `272861D94B0A257852225FABC9A3DAEBD026062D6D0604C51BD6F293236A96F9` | USD | CAD | validated |
| 27 | `28CE71FCAB5DBC6F46BFDB9CD5ED6C78BCC8420791C0A0CE1FD8EB3EBACFD878` | USD | CAD | validated |
| 28 | `2B68304E765866B3BDE9D14CD03CC62F40A52136ED97C6BD86A9CA6FF43E8955` | USD | CAD | validated |
| 29 | `2C374E26D9AF6401D3DDF35562024268A841BD449468FB62C66AE3BE781A4104` | USD | CAD | validated |
| 30 | `2CBB24DC64E9943C68C1A0C3DC17146AFE6597A2D38B55147C95C97460521783` | USD | CAD | validated |
| 31 | `2D619898E033ABF0A5A98C1910467BF4B4ED9B6872E09E18DB072B8CA619F5FC` | USD | CAD | validated |
| 32 | `2FF483944CC895D983E26944C6991A9AB5CD99C28C6C18322508FFB6723E1256` | USD | CAD | validated |
| 33 | `30EE839DD100C51F27600765D80F73284AF338DF755EB8AF413EC1393FE778FF` | USD | CAD | validated |
| 34 | `34CB4188561FA206A94C90DE9A32247C80C8758F01E8D950C2159899EE0FE69C` | USD | CAD | validated |
| 35 | `362E5281EBDDE9144EF75AD600E747A2058C9F437A645664C1FA3C434F931403` | USD | CAD | validated |
| 36 | `39C9DA4B71F94C9A57A84836648DD344A032DACE2B54579C7084504CA69090DE` | USD | CAD | validated |
| 37 | `3B1175B15E7A798461416D09EE9D6F66669805A33D8D69C0D65FC4D9FD279B7A` | USD | CAD | validated |
| 38 | `3D758F8708FA5FC7900335BFEFCC3BFAD7D8ECA6D767DE7C23F9A241DA8857F5` | USD | CAD | validated |
| 39 | `3DAE68B4A4F885998FF6A0D22CD1CC364A3F2233181509D121C2E4A3B29E7C8F` | USD | CAD | validated |
| 40 | `3DFE3D78455BB41F6E7FC13F7EBC4F793F8175BC739A88A64ACD8FAEC2745374` | USD | CAD | validated |
| 41 | `3FB75115EC4F4B701BE60991FFE789D883B04F0DFD5E5EE14F7297BAE1FF1806` | USD | CAD | validated |
| 42 | `40828D9D84D94A47B5220813DC19A3CBB21697801A09B7A1EB58A63DD64D624F` | USD | CAD | validated |
| 43 | `42405BDA7E97986BDD67DE56501C4E4A34075AE0A283B7C4412CE64DDCE8EC2B` | USD | CAD | withheld |
| 44 | `425BC772F8F0F8A860708473F55D577C9E3B13AB3AAC886C96BCEC58095F75BD` | USD | CAD | validated |
| 45 | `434D9A28DEED4236E7C1FFCFE83BADBD0CC026C0BBBBF402D72AB3CD346F6A04` | USD | CAD | validated |
| 46 | `49028FB41990218A6A5859B6B5E58DB6A116F9D671699301FA88BB16EE5E8BBD` | USD | CAD | validated |
| 47 | `4F1B9DC8B1A460327239C62735C2F2C4B774FBE0F675CCD7D64D88C75BE0209A` | USD | CAD | validated |
| 48 | `503DDEE755E7A4ADC38ED2D3A29521BE4C775E2A90E596D4A89E409B8C432E9E` | USD | CAD | withheld |
| 49 | `511A3AC9E2A3525A3DF25F7F5772DCC4F8E88EBF1E027BD00DB03C3ED8232B8A` | USD | CAD | validated |
| 50 | `52EE69773165B9DB55EACC1D348A93D1E772F20E4862D974474582AA0E4B5544` | USD | CAD | validated |
| 51 | `54C882722AE606EE561BE7EED47BBFCE65B41E4A93B18C3194C7A88320FA5223` | USD | CAD | validated |
| 52 | `568C2561AF0C125A5A2F3D6AD8497F79015CB91754681758BF036D63841BD78A` | USD | CAD | validated |
| 53 | `5A33718C270CA321A08D68772477B964255C0C3BE60C1FE34ACB91F91A82DAA0` | USD | CAD | validated |
| 54 | `5B1687DC7066BE146A7269C0DADEB78D62C40D265DC72C1D23CD27320C68514D` | USD | CAD | validated |
| 55 | `5C30BB1AB89719428816EF6A3715A6BE1D427A7DDE8339502B9267DD3835A3D4` | USD | CAD | validated |
| 56 | `5CCC12C869233DB4CEE90B82D262B3FCB5BB2FA33A7E4DC2979B0FB30E3C8691` | USD | CAD | validated |
| 57 | `5DA561C0B27B51E612D822CDC1C64DF69C121A10C52303BC3FAD8E65E8E37F0E` | USD | CAD | validated |
| 58 | `5DEDF65567CB612D1F32FD28C61F71BE3080352F84849B66AA24ACB05456D971` | USD | CAD | validated |
| 59 | `5DFEE0B61DD0161E1ED0E661477230FEAC8F011F87CC530CF04BEF403DC52CFB` | USD | CAD | validated |
| 60 | `5E5DAEAA95BB58A6E3029E4A4358264E0E93D2B7950E807640414F2F16C7F09B` | USD | CAD | validated |
| 61 | `5F67F77CBE64FEA0D922925A861EF664E817DF031D0237D8469647E731051E3A` | USD | CAD | validated |
| 62 | `613181D436B1B1683A264E1AB5079120AC5C2B8B7C276FC992768B31A26B6DC1` | USD | CAD | validated |
| 63 | `63872F7C0BBC7176F795F5EFA8C2C7361336129F9AA2A47656564BE49BC3ABBB` | USD | CAD | validated |
| 64 | `6BE3B323C81CA26551E146A1EE5869F7C50580C953965F35C03BEF410761079B` | USD | CAD | validated |
| 65 | `6DEB088C43FD32BBD5E062B22BC8BF0C525044D45969A4700A40E7730F0F4146` | USD | CAD | validated |
| 66 | `6EF63ADFD408CFE17EF3F8105C9950E8B76EBBC895B8FE25C49A6796C36BE619` | USD | CAD | validated |
| 67 | `700E13E8A919EAF5BA4BD691C7C24E5D30F2B1C203F33E835010FC7FC10B2E61` | USD | CAD | validated |
| 68 | `703B95BBC4629F5AE2DB1B7A701A4F7619C9D9FF9A58F6261F3EFF37020F4AB7` | USD | CAD | validated |
| 69 | `7063F44F82A65C147199F204C6BD8DDA3067F7629419B975E79D5530CBA75852` | USD | CAD | validated |
| 70 | `70C88CA30942FFF9A05715366F2216D207C19D3495BCFB1AB6440AEC511DBB3D` | USD | CAD | validated |
| 71 | `733DAF77250A9CF12812D7D18FCE6C9DA6D157AA3B3BF80618CEF1DADA679C4B` | USD | CAD | validated |
| 72 | `76FB6681ADEF6D22F49B993241960A8EF6736FEF49AEAD2F9C2526FDC6387631` | USD | CAD | validated |
| 73 | `788AE13555A86FBA0E6D7AB76B20CEC6B91B4A0FC34A410D0F5B82DD897395A2` | USD | CAD | validated |
| 74 | `78B7FCA1187DE7ACC39A3F1AE8CA341300F696B2D38EBD07E5DF131AC02F37D9` | USD | CAD | validated |
| 75 | `79553A7CC9C1E4410EB88C6456D6A75345AEBC325B4D3899067A3F77D96E397D` | USD | CAD | validated |
| 76 | `7A17C0ADABB1E996A44CDEEB8752CE28373F2A3C1B1590C2CE32879824F788C9` | USD | CAD | validated |
| 77 | `7CCF538CC447202BA9BBC463AB47A218429219E1734114590D20DDEA109DF56C` | USD | CAD | validated |
| 78 | `7F18A712A1CF48687710B579502B0022BEFDEB5B3ABCD731EE17C818674D61E5` | USD | CAD | validated |
| 79 | `8207E5FCB5CE0F58CCBA4375F96142ED43CA87E6A67BB256A757091A670B9B89` | USD | CAD | validated |
| 80 | `84B02EC206BEF98F88FF13C63A6F22B1B89D312A1754D9C1EF395193755A3ECA` | USD | CAD | validated |
| 81 | `84D17A2F2ADE02CDB1C9DCDC32FF3D85A7AC57B2952FA8467D740AA7BCFE02F5` | USD | CAD | validated |
| 82 | `85EFF2F7AFD5EF024B86115558B09A26D5692B678BCA80E46566CA50BEC15E5C` | USD | CAD | validated |
| 83 | `86863795F6D5C769F9FBEFBF24483BEF2844701E26225B7995107EE514FA9C00` | USD | CAD | validated |
| 84 | `8CAAA1DB6D87974660CF5F722C7016D8FF50DB150F3F7F663B4C2E38E969AA44` | USD | CAD | validated |
| 85 | `8CC25E42769DED8D20ED38F483AD4DB000B36CB16BAEBED5F6B1E5C16CF70FD7` | USD | CAD | validated |
| 86 | `8D70B981FA86194359E88E4AEB4BEB66CAF0491A55C9D16D49DFC384021B23AD` | USD | CAD | validated |
| 87 | `946C1466667BED23B4DFE812E735F1BF90BFEEF11CF13F411AF81675D7320A58` | USD | CAD | validated |
| 88 | `956CF99CC11D2890D298346C710E1641C8FA7DCE62908B3C7F2770C6E8E36E91` | USD | CAD | validated |
| 89 | `A0B0DA9C1C742C8B3060221815DA2EFD9C35C1D3F46B96771CEB7474F06220CB` | USD | CAD | validated |
| 90 | `A0F9325CF5A14282143E5E623AFAADE1F05983292A63D9B38623523ADFD07450` | USD | CAD | validated |
| 91 | `A3906432AB941FE04C63507AB5121D9EBD0FEC913B07909ADAEEA4F0D6EA4B1F` | USD | CAD | validated |
| 92 | `A39155C1F8A8E1692631149F088D5E21367E93A6F721A853B5AEEA180D770178` | USD | CAD | validated |
| 93 | `A906FDA6846D0321B525F85DC4144AD60016C3C2F7B8144B560F552E8262CE1F` | USD | CAD | validated |
| 94 | `A95186C552C0F95080383315CB88AEC5E9FCB11A83CB542D02B43359ABC7844D` | USD | CAD | validated |
| 95 | `A9DC433D3D6910844964BF343E813F783A4160729BDB74D66AFA06E3FDA85CDC` | USD | CAD | validated |
| 96 | `AE7352DA7E62F530B5B22B8CCBB633D8D014035709EA2374904B723D41C4A73B` | USD | CAD | validated |
| 97 | `AF6BBDC4CF4356B3379A25904C08019F0C88E7B0DFAF061316111DC917EC3C6A` | USD | CAD | validated |
| 98 | `AFCA83D42494B80C851CB094F3DC8B98B3A829E57FE1FDFB60CBBFB31EA58A3C` | USD | CAD | validated |
| 99 | `B096FE766B0683C9CEC66348CCD076B36F9841CF1E57C555C8187FB87FF0E6A8` | USD | CAD | validated |
| 100 | `B0C47AE8DAB9C8AA398A0584EB20D7DE71B582F6A206B0AB510BCAC5C06178BF` | USD | CAD | validated |
| 101 | `B3595D87451BEDF4E13CDB5F68E313CE5D2AB2EE9B65D578C03C36E69D7219DD` | USD | CAD | validated |
| 102 | `B4C48D215656C1BEADCF6EA7783186E2C307C641C59EB3AA3A5100B6908B572E` | USD | CAD | validated |
| 103 | `B834D69701C0D40D7C426F3BDB2263A91B2128333480F1FECD39F0A64D044370` | USD | CAD | withheld |
| 104 | `B90151CDA970A226DB20F1B34C84F3D143D4CD949358B0C9B02ED4BBB0C678B2` | USD | CAD | validated |
| 105 | `BAE5C1A78247D4F8CBB3405C8CF2568AEFFC48AA790C79EDD0F9E6D5B16477D0` | USD | CAD | validated |
| 106 | `BEC9816598932745220DCB5B5C3B8156D465224533CC6B9343B9906E52AA075E` | USD | CAD | validated |
| 107 | `BF07809448D7208488CD6AE16C6DC22281161FEEC3C2A7D5D3E56C1857E8D7E5` | USD | CAD | validated |
| 108 | `C088C8CAB2223D085BD62C84F050968304322EA9FE94E4EC00B3C827887E98FB` | USD | CAD | validated |
| 109 | `C2ECCDC7FB7655D0D382D76400232C23813E22A90185ABC7A0E3B1783547A84E` | USD | CAD | validated |
| 110 | `C312B27FF15F1BFC8749F237A7F7871C4F46754345885F9545B930D49D6A470A` | USD | CAD | validated |
| 111 | `C51AD7853F1239684622BE01122159B0F3218C7252485E3C154795B4ACA58FE9` | USD | CAD | validated |
| 112 | `C91CBAE7C050DBC9F5531DF2E14FF04DF4E147913E390F15FC37BD475A8C697B` | USD | CAD | validated |
| 113 | `CACB5EF3A60D9271684A24D6E1790762F87905BA991E35EF90830466CA2A693A` | USD | CAD | validated |
| 114 | `CAEB534F4B94B95BA285DA6B3FD8AD13F6238A3B213E2D6610BA82F12F1A00F0` | USD | CAD | validated |
| 115 | `CC7240BD016149628903F3FF45498642202A2FA3E6AC8C4909857BEFE1F79F0C` | USD | CAD | validated |
| 116 | `CE6C91DF2E6C1F608518C3E5973538D75F558AB707022F86EEB1C7FBB706B93B` | USD | CAD | validated |
| 117 | `D068440C5DC13E67555D3BFC5096F0AC5DA5EA68FCFDBC562FFA063B69DE44B9` | USD | CAD | validated |
| 118 | `D0E8A821160DE6DD8150E7B7C4891A717143CB25A0F8A9C48FBB9448ACE75410` | USD | CAD | validated |
| 119 | `D44831ED1DB4FB498F378883D2F1478F144D7266ED2896B8BDCAA94157B0EE07` | USD | CAD | validated |
| 120 | `D544FB95C7F0D4D67CB69AA710D4938AB868FF1A1C05055BD86D94443A695F98` | USD | CAD | validated |
| 121 | `D5E2C800EE418DFF85B5D3153E069AD4004A53115ECE26174BFC135D5BA46607` | USD | CAD | validated |
| 122 | `D8BF227FEC084195CF306DC4C920D558FB27AC33BF231561D47BB842855D1608` | USD | CAD | validated |
| 123 | `D9D23DAB89FCF1BA2C227BE37AF47B58CA2BB908468145874996B505B20CF6E6` | USD | CAD | validated |
| 124 | `DC9AEA0A2000429639FD8043238A58469318FB5599EED8ED522CD7D7796353BE` | USD | CAD | validated |
| 125 | `E11B3C0184901BD73C2DBF173C32F0DBC2AA4C04E679CEA4500241F8184CD192` | USD | CAD | validated |
| 126 | `E3B4E7AF3CAEA6FDE549638DE8BB7888E98AC4EE329F2512785D139D80A799DE` | USD | CAD | validated |
| 127 | `E4057A3924981DD814A68DB9DFA2A01AA9AD2A48AE9CFF4A957C830F90CB4E64` | USD | CAD | validated |
| 128 | `E552074A32D92BA34D9ABBFE022CB1937F2C71832331F393F2A27ED9E3F092BF` | USD | CAD | validated |
| 129 | `E6D1F06E945842E4BBCDE9FE50801EF5EE061B39A5057A1485E71B54406BE1C2` | USD | CAD | validated |
| 130 | `E7A5FB429FC236084F3F849467F32107B1996113B8A94E2DF03BF9C113984736` | USD | CAD | validated |
| 131 | `EA7FC6A86E37BEDBBB6D61F5AB5682891B749FFFD86CCFD0D2855FDC5C606C29` | USD | CAD | validated |
| 132 | `EAFD5EC1E764F8EA874CA489C92EB838177DB24DFA850063C0184802D3857781` | USD | CAD | validated |
| 133 | `ED3E3BE60B9C70D8C55517854E8DB5F443D10E6C021FAB4DC21B5A090E4E51A2` | USD | CAD | validated |
| 134 | `EDE4CBFB6C11BC26E7BED4441F5FF8E9AEDD77529E434CA312046F3B7849F2DE` | USD | CAD | validated |
| 135 | `EDEED44DF8BC67E75205052A937D7110BA147FDB5AE498B6E15142E6F2B4CF05` | USD | CAD | validated |
| 136 | `EFB8EDC370D7731CA3BD14AA4BC3FD17288F2E066A4218E8FA77D509B70EDEEA` | USD | CAD | validated |
| 137 | `EFC35DF8DE9337EA6CA36B9AA574019AC2F3985A341BBAEDEB84337E8D5E8708` | USD | CAD | validated |
| 138 | `F02C07F67870AE767B4E4566B83250DB019847C3AD1893C0FABF911D7231C02C` | USD | CAD | validated |
| 139 | `F06BA535F9D9F57EEE7BB7F4ACCD56B0AF8DED496FA751AC909A852D6CFE6CEF` | USD | CAD | validated |
| 140 | `F327C852AF8BECAC0A8253EDC1CC95326F80BF7737E60C51790669D91F3E7396` | USD | CAD | validated |
| 141 | `F5B271059CC7932494054A921C17CE1E6E8E837D604D768BF0D3885FBDDE49EC` | USD | CAD | validated |
| 142 | `F83DD956537FB1B70A200061FAA2F80271E6F5118DD5886D7676D60F3F97ADAB` | USD | CAD | validated |
| 143 | `F8D8C02F5CFCBF652226B79F8768C578BFB8C4EFCB777B32E93D5F1E304F4DA2` | USD | CAD | validated |
| 144 | `FBED1BE96AE70C6A8C6F77A4238DA0D12770FA8DB20061ED0F33986C15EE30FF` | USD | CAD | validated |
| 145 | `FD82EBEFDCBD3FA54A26731CAFAB47DA62908D081217247C24C26716BF627CFD` | USD | CAD | withheld |
| 146 | `FD96B309BF012E7C87EC75552B6B4F7FBF7BE0200E438C909CFB2D794DBD30BD` | USD | CAD | validated |
| 147 | `FE8CD54A5B58A6B73182DB425C1D75DB75936F35E5CD998C256945233B9005B5` | USD | CAD | validated |

---

## 10. Conflicting or uncertain evidence, and what left the packet

*Doctrine §B item 4 — fail closed / preserve uncertainty.*

**Documents with CONTRADICTORY currency evidence: zero.** Measured over all 169
English RBC documents: no document carries two different currency codes across
the two evidence sites. The evidence-site multiplicity is
`{USD via 1 site: 6, USD via 2 sites: 6, CAD via 1 site: 6}` — the six
two-site USD documents agree with themselves on both sites.

**Documents with partial jurisdiction evidence: zero.** Every English RBC
document that reaches the jurisdiction test satisfies all four proofs or none
of them; there is no near-miss stratum. (Nothing was excluded for uncertainty,
because nothing was uncertain — this is a measurement, not an assumption.)

**Named exclusions, all of them evidence-driven and none of them uncertain:**

| Population | Docs | Why it is not in the packet |
|---|---|---|
| `U.S. Funds` line only | 6 | explicit USD denomination (doctrine §B item 1) |
| `U.S. Funds` line + `US BUSINESS ACCOUNT` | 6 | explicit USD denomination, two sites |
| `CAD CHEQUING ACCOUNT` | 6 | already publishes CAD from the page; no movement to enumerate |
| `rbc_french` documents | 20 (1 pinned) | already publish CAD from the French reader; the prototype returns before touching them. **Note:** the English jurisdiction predicate does **not** fire on them (0/19 measured) — it is anchored to the English layout's furniture, so a future French jurisdiction default would need its own evidence base |
| RBC Canada documents no parser claims | 7 | they publish **nothing**, so they carry no currency to move. Four are the glyph-damaged `Business Account Statement` issues structurally refused by the `glyph_damage` excluding marker (`5B76F0B1…`, `19ED81F2…`, `720C4C37…`, `ADB91E10…`); two are RBC online-banking screen captures (`0D6010E4…`, `D886A629…`); one is `BFEB79B26E426C2FDA63DF0C1F422D95F4A8AF95319C03ADCA85D9560B6E58A3`, a genuine zero-activity 4-day RBC Canada statement that **does** satisfy all four jurisdiction proofs and would join the packet as a 152nd document the moment any registration claims it |
| Non-RBC documents inside the superset | 28 | claimed by `td_canada_native` 11, `cibc` 6, `releve_facturation` 6, `bmo_ca_business` 3, `chase` 2; proven unchanged by the field diff |
| Archive documents with no readable OCR artifact | 16 | no text, no published payload |

---

## 11. Risks

**R1 — a USD RBC Canada account whose statement omits the denomination line.**
The default is wrong for such a document. Base rate measured: 12 of 169 English
RBC documents (7.1%) are USD-denominated, and **12 of 12 announce it** on the
anchored line, 6 of them twice. There is no attested silent-USD issue of this
layout in the archive. Residual, not observed; it is the risk doctrine §A
accepts when it makes the native currency a jurisdiction default rather than a
read. Mitigation if Gustavo wants one: the implementing cell can make the
absence of a denomination line on a *business* product a diagnostic note rather
than silence.

**R2 — the rule is anchored to two RBC Canada layouts.** J_ISSUER/J_SERVICE/
J_ACCOUNT/J_BRANCH are the business and personal English layouts' furniture. A
third RBC Canada layout (or a re-issue that drops `rbcroyalbank.com`) fails all
four and silently keeps the USD default — a false negative, which is the safe
direction, but it will look like "the rule stopped working". The 12 personal
documents in the packet already needed J_ACCOUNT widened from the business
spelling; measure again on any new layout.

**R3 — the movement is gate-invisible (the important one).** `currency` is in
no audit CSV, not in `PINNED_OUTCOMES`, not in `parser_expectations.json`, and
`corpus_gate.py` never mentions it — yet `webapp/static/app.js` threads
`statement.currency` into `Intl.NumberFormat`, so all 151 documents change what
an analyst sees (`$1,234.56` → `CA$1,234.56`). A ceremony that moves 151
published values while every pinned artifact stays byte-identical sets a
precedent worth refusing. **Recommendation for Ocean/Gustavo: the ceremony
should also add `currency` to a pinned surface** — the cheapest is a
`currency` field on the `_Verdict` tuple in `corpus_gate.PINNED_OUTCOMES`, or a
column in `balance-metrics-audit-results.csv` — so that the next currency
movement cannot happen silently. This is a scope decision, not this cell's to
take.

**R4 — the personal layout's mailing header is not scanned by the explicit
reader.** `analysis.rbc._MAILING_HEADER_RE` matches `RBBDA\d+_\d+` only; the
personal layout prints `RBPDA\d+_\d+_\d+`. Twelve packet documents therefore
have their product line unread. Measured harmless today — the wide sweep of
§2 finds no currency token of any kind on those 12 — but a personal RBC issue
that printed a product currency word would be missed by the explicit reader and
then defaulted to CAD by the jurisdiction rule. The implementing cell should
widen the header anchor to both prefixes **in the same commit** as the default,
so the explicit read keeps its precedence on both layouts.

**R5 — `analysis/schema.py`'s `USD` default is now doing two jobs.** After this
change, `currency == "USD"` on an RBC English document means "the page said
`U.S. Funds`"; on ~1,900 U.S.-registration documents it still means "nobody
asked". Doctrine §B generalises the jurisdiction shape to TD, BMO, CIBC…, each
needing its own proven evidence base; until those land, the field's provenance
is heterogeneous and nothing records which reading a given document got.
Carding a `currency_source` provenance field is out of this cell's scope and
worth a card.

**R6 — process.** The measurement was taken on a machine shared with nine build
cells. Probes were kept light and sequential; the 236-document double analysis
ran as two short foreground commands (492s + 392s) rather than a background
shell. Nothing else on the machine was touched, and no repository state outside
this file and the W3 entry changed.
