# R-3 finding — five parsers detect a counterparty, not the issuing bank

Author: Agent A (REEF). Date: 2026-08-06. Status: **BLOCKING R-3.4 — Ocean ruling requested.**
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

## 5. What I propose

**Add one required marker per affected parser, drawn from that bank's own
statement furniture** — the evidence its `parse` already depends on. Candidates
measured as present in every one of that parser's corpus documents and absent
from all others:

| Parser | Proposed additional required marker | Nature |
|---|---|---|
| `bank_of_america` | `BANKOFAMERICA.COM` | issuer domain — the same evidence 8 other parsers already use |
| `regions` | `THANK YOU FOR BANKING WITH REGIONS!` | issuer footer |
| `bmo` | `ACCOUNT SUMMARY TOTALS` | BMO section heading (already referenced by the BMO contradiction check in `pipeline.py`) |
| `capital_one` | to be selected — needs an issuer-owned brand/section string, not the customer name the candidate search surfaced | issuer furniture |
| `scotiabank` | to be selected on the same basis | issuer furniture |

Constraints I would hold to: structural strings only — issuer domains,
statement section headings, issuer footers. No customer names, dates, amounts,
account numbers or page counts. The candidate search did surface such strings
(`SALON BARK LLC`, `CLOSING BALANCE $ 1,000,000.00`, `--- PAGE 21 ---`); none
will be used.

Parity is provable either way: the affected parsers must still claim all of
their own corpus documents, and `tests/test_parser_parity.py` asserts it.

## 6. Why I stopped rather than doing it

This changes what five parsers *claim*, on the discovery corpus as much as on
ours. That is a detection-semantics change, materially beyond the mechanical
transcription R-3.2 was approved for, and WAVE2_BRIEF §3 R-4 is explicit that a
parser defect found during this work is "reported to Ocean, not silently
fixed". Ocean's own stop-rule for this stage — report any `supersedes` edge
beyond the three known ones, with the document that proved it — is aimed at
exactly this class of discovery; this finding is the same trigger in a stronger
form.

R-3.4 cannot land until it is resolved: 45 ambiguous documents would route to
review and take the corpus gate red, and re-baselining is not mine to do.

## 7. State of the work

Stages R-3.0 through R-3.3 are complete, committed, suite-green and
gate-green. The registry is fully built and exercised; only the pipeline
switch is blocked.

The two parity assertions that depend on the finding are
`xfail(strict=True)` in `tests/test_parser_parity.py`, referencing this
document. They flip to passing — and the markers come off — when the ruling
lands. Everything else in that module passes today.

## 8. The ask

1. Approve adding one issuer-furniture required marker to each of the five
   parsers, under the constraints in §5 — or direct a different resolution.
2. Confirm that the two `capital_one` / `scotiabank` markers may be selected
   by me on the stated basis, or that you want to see the candidates first.
3. Note for Wave 3: `"BMO"` and `"BUSINESS ACCOUNT 01180"` look like
   independent parser-quality defects worth their own ticket, separate from
   the dispatch question.
