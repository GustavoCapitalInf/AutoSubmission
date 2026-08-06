# R-3 finding — five parsers detect a counterparty, not the issuing bank

Author: Agent A (REEF). Date: 2026-08-06. Status: **RESOLVED — Ocean ruling 2026-08-06; markers landed in R-3.4.**
Raised by: the R-3 corpus parity control (R3_RFC §6), at stage R-3.3.
Evidence: `tests/data/parser_expectations.json`, `tests/test_parser_parity.py`.

---

## 1. What the control found

R-3 replaces first-wins dispatch with an explicit ambiguity outcome. Running
the transcribed detection markers over the 109 pinned corpus documents:

| Property | Result |
|---|---|
| Documents left unclaimed | **0** |
| Documents resolving to the **wrong** parser | **0** |
| Documents where the recorded parser is outscored by a rival | **0** |
| Documents with **more than one** claimant | **45 of 109** |

The first three are the properties that would indicate a broken migration.
None of them is broken. The fourth is a pre-existing defect that the or-chain
concealed, and which the registry — by design — refuses to conceal.

## 2. The defect

Five parsers identify their bank by a bare name substring searched over the
whole document. That substring also matches when the bank appears as a
**counterparty inside somebody else's statement**:

| Parser | Marker | Foreign corpus documents it claims | An example match |
|---|---|---|---|
| `capital_one` | `"CAPITALONE" in markdown.upper().replace(" ", "")` | **38** | Truist statement: `…CONVERTED CHECK-ARC CHECK PYMT CAPITAL ONE ARC 0020720 727.93…` |
| `bmo` | `"BMO" or "BANK OF MONTREAL"` | **7** | Chase statement: `…ZELLE PAYMENT FROM … BMOZ000RIJ8B 129.54…` (a Zelle reference id) |
| `regions` | `"REGIONS"` + `"SUMMARY"` | **3** | Amex statement: `…JACK HENRY CO/ REGIONS BANK ID 009002514875552…` |
| `scotiabank` | `"SCOTIABANK" or "BUSINESS ACCOUNT 01180"` | **3** | Santander statement: `…USD WIRE IN FROM SCOTIABANK CHIL ACCT *9246…` |
| `bank_of_america` | `"BANK OF AMERICA"` + `"ACCOUNT SUMMARY"` | **1** | TD statement: `…ELECTRONIC PMT-TEL, BANK OF AMERICA PAYMENT J9JXBE69W 2,500.00…` |

**These are the parsers' own pre-R-3 guards, transcribed unchanged.** Verified
directly against the original expressions on the source documents — this is not
a transcription error. `capital_one`'s guard, in particular, claims 38 of the
109 corpus documents; it produced correct results only because it sat 41st of
43 in the chain.

Two of these markers are also weak in their own right: `"BMO"` is a
three-letter substring that matches inside opaque reference ids, and
`"BUSINESS ACCOUNT 01180"` looks like a residual account-number fragment of the
kind R-1 was meant to remove.

## 3. Why this matters more than the corpus

On the corpus the defect is inert: chain order happened to put every
over-broad parser after the right one. Two things change that.

1. **The discovery run (DSC-2)** puts 3,506 documents from ~69 institutions
   through this dispatch, including 965 `Unidentified/`. A statement from an
   unregistered bank that merely *pays a Capital One card* — an extremely
   common transaction — currently gets claimed by `capital_one`. Under
   first-wins that is a silent wrong-parser claim; the reconciliation gate
   catches most, but WAVE2_BRIEF §0.3 names precisely the case it does not: a
   wrong claim that happens to reconcile corrupts both the result and the
   coverage statistics the run exists to produce.
2. **Registry order is no longer the safety net.** R-3 deliberately removes
   positional protection. That is the right design, but it means the
   protection has to be replaced by evidence, not restored by ordering.

## 4. Why the obvious fixes are wrong

**`supersedes` edges.** The approved mechanism for a genuine two-claimant
conflict, but not for this. It would take ~52 edges, of which 38 say only
"`capital_one` loses to everybody" — chain order re-encoded as data, with the
same blind spot: an unregistered bank has no edge, so on the discovery corpus
`capital_one` would still win. It fixes the corpus and not the problem.

**Lowering scores.** Forbidden by the approved policy, and rightly: it converts
a visible conflict into an invisible one.

**A first-page positional rule.** I measured it: the issuing bank names itself
in the header (own documents: first hit at offset 11–314 characters) while
counterparty mentions sit in the transaction body (foreign documents: earliest
hit at offset 777). Scoping the bank-name marker to page 1 (all 109 documents
carry `--- Page N ---` markers) keeps every own document and removes 57 of the
61 false claims. It does not remove the last 4 — some statements begin
transactions on page 1 — so it is not sufficient alone, and a tuned character
offset would be a corpus-fitted constant of exactly the kind R-1 purged.

## 5. Resolution (Ocean ruling, 2026-08-06)

Approved: **one issuer-furniture required marker per affected parser** —
structural evidence the *issuer* prints on its own statements. Prohibited and
not used: customer names, dates, amounts, account numbers or fragments,
positional offsets, or any corpus-fitted constant. The candidate search did
surface such strings (`SALON BARK LLC`, `CLOSING BALANCE $ 1,000,000.00`,
`--- PAGE 21 ---`); none was used.

### The five-parser table

| Parser | Guard before R-3.4 | Marker added | Class | Evidence document that proved it necessary |
|---|---|---|---|---|
| `capital_one` | `"CAPITALONE" in md.upper().replace(" ","")` | `AN IMPORTANT MESSAGE TO OUR CLIENTS` | issuer section heading | `Truist/Truist April, 2026.pdf` — `…CHECK PYMT CAPITAL ONE ARC 0020720 727.93…` (+37 more) |
| `bmo` | `"BMO" or "BANK OF MONTREAL"` | `ACCOUNT SUMMARY TOTALS` | issuer section heading | `Chase/Chase Mar.pdf` — `…ZELLE PAYMENT FROM … BMOZ000RIJ8B…` (+6 more) |
| `regions` | `"REGIONS"` + `"SUMMARY"` | `THANK YOU FOR BANKING WITH REGIONS!` | issuer footer | `Amex/Amex Apr2026.pdf` — `…JACK HENRY CO/ REGIONS BANK…` (+2 more) |
| `bank_of_america` | `"BANK OF AMERICA"` + `"ACCOUNT SUMMARY"` | `BANKOFAMERICA.COM` | issuer domain | `TD/TD BANK NARROW APR.pdf` — `…ELECTRONIC PMT-TEL, BANK OF AMERICA PAYMENT…` |
| `scotiabank` | `"SCOTIABANK" or "BUSINESS ACCOUNT 01180"` | `THE BANK OF NOVA SCOTIA`, **and the `01180` fragment removed** | issuer legal name (trademark footer) | `Others/Santander/Santander_April26.pdf` — `…USD WIRE IN FROM SCOTIABANK CHIL…` (+2 more) |

Every marker verified present in **all** of that parser's corpus documents and
absent from **all** others before being written. Tests:
`tests/test_parser_detection_markers.py` — a detection-positive and a
detection-negative per marker, each negative reproducing the counterparty text
of the cited corpus document; corpus-wide coverage is
`tests/test_parser_parity.py`.

### Measured result

| | Before | After |
|---|---|---|
| Ambiguous corpus documents | 45 | **0** |
| Unclaimed | 0 | **0** |
| Wrong-parser claims | 0 | **0** |
| Documents with a parse fallthrough | 0 | **0** |
| Corpus gate | GREEN | **GREEN**, 106 PASS / 3 WITHHELD, no re-baseline |

## 6. Semantic note: these parsers now under-claim, deliberately

This is not a neutral tightening. Off-corpus, the five parsers now claim
**strictly fewer** documents than before:

* Before — a statement from *any* institution that merely mentioned the bank
  (a card payment, a wire, an ACH originator) could be claimed by that bank's
  parser. Under first-wins that produced a silent wrong parse whenever the
  mentioning bank had no parser of its own or sat later in the chain.
* After — such a document produces a *weak* detection (the bank name really is
  present, so the score is above zero but below the threshold) and no claim.
  It falls through to unclaimed → LLM extraction → review.

**The failure mode moves from "wrong answer" to "no deterministic answer",
which is the fail-safe direction, and it is intentional for DSC-2.** A
statement from an unregistered bank that pays a Capital One card is exactly the
shape the discovery archive is full of; a wrong parse that happens to reconcile
would corrupt both the result and the coverage statistics the run exists to
produce, while an honest miss shows up as a named unknown-layout cluster.

The cost is that a genuine statement from one of these five banks whose layout
drops the required furniture would now be missed rather than parsed. That is
visible — it shows up as a coverage miss with a near-threshold score, not as a
silent wrong answer — and the weak-but-nonzero score is what lets DSC-2 tell
"almost matched" apart from "never heard of this bank"
(`test_a_counterparty_mention_still_scores_above_nothing`).

## 7. Wave-3 backlog: R-1 residual sweep

Two items found while resolving this. Neither is a dispatch problem; both are
parser-quality defects of the class R-1 targeted, logged here rather than fixed
now.

1. **`"BMO"` as a three-character marker.** It matches inside opaque reference
   ids (`BMOZ000RIJ8B`), wire beneficiaries (`BMO BANK NA`, `BMO HARRIS BANK`)
   and card descriptors (`BMO MASTERCD`). **Partially mitigated now** — the new
   required `ACCOUNT SUMMARY TOTALS` marker means a stray `BMO` can no longer
   produce a claim on its own — but the marker itself is still far too weak to
   carry bank identity and should be replaced with BMO issuer furniture.
2. **`"BUSINESS ACCOUNT 01180"` in the Scotiabank guard.** An account-number
   fragment used as detection evidence — an R-1 residual. **Fixed now**, per
   Ocean's ruling that a residual living in the detection guard of a parser
   already being touched is in scope. Removing it cost nothing: no Santander
   document contains it, and the Scotiabank document is still detected by
   issuer evidence. Regression-guarded by
   `test_scotiabank_no_longer_detects_on_an_account_number_fragment`.

A third observation, for the same sweep: in the Scotiabank corpus document the
**first** `SCOTIABANK` occurrence is inside the markdown source comment
(`<!-- SOURCE: SCOTIABANK -2.PDF ... -->`) — i.e. the filename, echoed into the
text the parsers detect on. The statement body carries the brand twice more, so
detection does not depend on it here, but *any* parser detecting on a string
that also appears in a filename is detecting on metadata. Worth a systematic
check across all 46 registrations in Wave 3.

## 8. State of the work

R-3.0 through R-3.4 complete, committed, suite-green and gate-green. Registry
dispatch is live in `analysis/pipeline.py`; the orchestrator names no bank.
R-3.5 and the pulled-forward six-parser fixtures await Ocean's go.
