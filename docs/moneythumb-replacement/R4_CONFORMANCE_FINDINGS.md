# R-4 conformance findings — four parser defects, all resolved in R-4b

Author: Agent A (REEF). Date: 2026-08-06.
Status: **ALL RESOLVED in R-4b (`d49a07c`)** (Ocean triage 2026-08-06: fix all, Wave 2, one continuation card).
Raised by: the R-4 conformance harness (`tests/test_parser_conformance.py`).

---

## Summary

All four are **detection** defects. None changed any corpus outcome, before or
after: parity stayed 109/109 with ambiguous 0, unclaimed 0, wrong 0 and
fallthrough 0 throughout, and the gate stayed GREEN byte-identical with no
re-baseline. They mattered because DSC-2 is about to put 3,506 foreign
documents through this dispatch, and each was a way to claim a document that is
not yours.

Each was pinned by a test asserting the affected set **exactly**. Those pins
did their job: every one failed the moment its fix landed, forcing the
conversion from "recorded defect" to "regression test" in the same commit.

| Finding | Fix | Pin: before → after |
|---|---|---|
| R4-1 | `first_farmers` bank-name marker → `FFBT.COM` (issuer domain present in the committed OCR artifact) | `test_first_farmers_does_not_detect_on_the_filename`: xfail(strict) → passing |
| R4-2 | closed for free by the platform strip | `test_relay_scores_nothing_from_the_filename`: xfail(strict) → passing |
| R4-3 | six issuer-furniture markers | 6 × `test_a_bank_name_in_a_transaction_line_is_not_a_claim`: xfail(strict) → passing; `COUNTERPARTY_VULNERABLE` → empty, asserted empty |
| R4-4 | customer name removed from two sites in `farmers_merchants` | new layer-wide literal scan; `ACE AUTO GLASS` added to `REMOVED_LITERALS` |
| platform | `admissible_text` strips the filename comment centrally | corpus invariance test: "two registrations differ" → "stripping changes nothing, for all 46" |

**8 strict xfails → 0.**

---

## R4-1 — `first_farmers` detected its own corpus document via the filename

**Severity: high.** The only defect that affected a document we ship.

`analysis/first_farmers.py` required the marker `FIRST FARMERS`. In its single
corpus document, `Misc/First Farmers 2026 01-document.pdf`, that string appears
**nowhere in the statement body**. It was matched from the comment the OCR layer
prepends:

```
<!-- source: First Farmers 2026 01-document.pdf | pages: 3 | model: local-tesseract-ocr | empty: 0 -->
```

Strip that line and the score fell 0.5 → 0.3 and the parser stopped claiming
its own document. Rename the file and coverage disappeared: the gate was
passing on this document partly because of an operator-chosen filename. The
other three markers were genuinely present.

**Fix applied.** The bank does identify itself in the artifact — the letterhead
survives OCR as `FIRST` / `FARMERS` / `OB BANK & TRUST` broken across lines with
scan noise, which is why the contiguous string never matched — but its
tele-banking domain `WWW.FFBT.COM` comes through clean in the same header
block. The marker is now `issuer_domain` (`FFBT.COM`), verified present in the
artifact body and absent from all 108 other corpus documents. It landed in the
same commit as the platform strip, so the strip never saw a tree it would break.

Tests: `test_first_farmers_does_not_detect_on_the_filename` (now a passing
regression test), `test_detection_is_invariant_to_the_filename_echo` (corpus).

## R4-2 — `relay` scored a filename-derived marker

**Severity: low.** No claim decision ever changed.

On `CIBC French/Account Statement 1.pdf` the `relay` marker `ACCOUNT STATEMENT`
matched the filename `Account Statement 1.pdf`, not the document. Relay needs
four required markers and only this one fired, so it did not claim — but the
detection score rose 0.0 → 0.1. Not cosmetic: that sub-threshold score is
exactly the signal DSC-2 uses to rank near-misses and unknown-layout clusters.

**Fixed by the platform change** below; no marker edit was needed. Tests:
`test_relay_scores_nothing_from_the_filename` (now passing), plus the corpus
invariance test.

## R4-3 — six parsers claimed a statement that merely named them

**Severity: moderate; high for DSC-2.**

Exactly the defect class R-3.4 fixed for `capital_one`, `bmo`, `regions`,
`bank_of_america` and `scotiabank` — in six parsers no corpus document happens
to mention, so the corpus parity control could not see them. Each declared
**exactly one required marker, and that marker was a bank name**. Given another
bank's statement containing `01/15 ACH DEBIT PAYMENT TO <that bank> 250.00`,
each claimed the document.

`chase` was the exposure: "JPMorgan Chase Bank" appears in wire instructions,
ACH originator strings and remittance advice across the industry, and Chase is
the largest folder in the discovery archive (618 documents).

**Fix applied** — the R-3.4 remedy under the same constraints. Every marker was
verified present in each of that parser's corpus documents and absent from all
others before being written:

| Parser | Marker added | Class |
|---|---|---|
| `chase` | `*start*summary` | Chase's own PDF text-layer section sentinel |
| `consumers` | `SUMMARY OF ALL ACCOUNTS` | issuer section heading |
| `dakota_west` | `DAKOTA WEST CREDIT UNION` | issuer footer |
| `first_citizens` | `FIRSTCITIZENS.COM` | issuer domain |
| `mission_valley` | `MISSIONVALLEYBANK.COM` | issuer domain |
| `texas_bank` | `WITHDRAWALS AND OTHER DEBITS (CONTINUED)` | issuer section heading |

`texas_bank` additionally **lost its `6250TEXAS` branch** — a print-control
digit run used as bank identity. It sat in the very guard R4-3 was rewriting,
so it went in passing per Ocean's ruling; the statement body carries the bank's
real name.

The same under-claiming semantics as R-3.4 apply and are intentional: off
corpus these six now claim strictly fewer documents, and a statement that
merely pays them falls to unclaimed → LLM → review rather than to a possible
wrong parse.

Why the corpus could not have found this: it contains no statement naming these
six as a counterparty. Detection correctness cannot be measured only against a
corpus that is corpus-shaped (G1) — which is what R-4's synthetic cross product
is for.

Tests: `test_a_bank_name_in_a_transaction_line_is_not_a_claim` (all 46 passing),
`test_the_set_of_counterparty_vulnerable_parsers_is_exactly_the_recorded_finding`
(now asserts the set is empty), six named cases in
`tests/test_parser_detection_markers.py` whose negative fixtures carry real
wire/ACH boilerplate, and a new permanent invariant,
`test_no_registration_identifies_a_bank_by_one_marker_alone` — the structural
lesson kept as a rule rather than a memory. Its one documented exception is
`td_canada`, which probes for a table layout rather than a name.

## R4-4 — the customer name in `farmers_merchants`, and what removing it exposed

Ocean's ruling: a literal customer name in a parser violates R-1's landed
zero-customer-names acceptance that its file-scoped grep missed — not new
scope. **Two** sites were found in that one module, and the second only because
fixing the first widened the guard.

1. **Detection.** The bank-identity marker's second branch required the account
   holder's trading name. Removing it revealed the harder fact: **this
   statement carries no issuer identification whatsoever** — no bank name, no
   domain, no FDIC or Regulation-CC issuer footer. Verified by exhaustive
   search of the document. There is therefore no issuer furniture to
   substitute. The branch is now the layout's own product and section headings
   (`BUSINESS/COMMERCIAL` + `CHECKS/DEBITS`) — weaker evidence than every other
   parser carries, but at least *structural*. Own document still claimed; zero
   cross-claims across the 46 × 45 conformance product.
2. **Holder extraction.** A second occurrence sat in the `account_name` regex,
   which found the holder line by naming the customer. Generalised to the line
   carrying a `DBA` clause — a legal-entity marker — and verified to capture
   the identical string on the corpus document.

**Guard strengthened.** `ACE AUTO GLASS` is now in `REMOVED_LITERALS`, and a new
`test_removed_literals_stay_removed_anywhere_in_analysis` scans **every** module
in `analysis/` rather than the seven R-1 happened to touch — which is why the
second occurrence was found at all. `classification_registry.py` is exempt and
documented: naming counterparties is a counterparty registry's job.

## Platform fix — filename text is now structurally inadmissible

`analysis/parser_registry.admissible_text` strips the `<!-- SOURCE: ... -->`
comment centrally, before any parser's own normalization, in both
`make_detector` and `Registration.detect`. Detection therefore cannot read a
filename for any of the 46 registrations — by construction rather than by each
parser's good intentions. `parse` is unaffected and still receives the whole
document.

Sequenced as identified: R4-1's marker fix is in the same commit, so the strip
never saw a tree it would have broken.

The corpus invariance test flipped accordingly — from "these two registrations
differ" to "stripping the comment changes nothing, across all 46 registrations
× 109 documents".

## Outcome

All four findings resolved. Parity 109/109 (ambiguous 0, unclaimed 0, wrong 0,
fallthrough 0); conformance cross-product 46 × 45 with 0 cross-claims; full
suite green with zero remaining xfails; corpus gate GREEN byte-identical, no
re-baseline.

Carried to Wave 3, log-only:

* `altana` requires `FREE BUSINESS CHECKING ID 0050` — a digit run in detection
  evidence. The R-4 fixtures deliberately exercise the other branch of every
  such marker, so the conformance suite never depends on a residual it reports.
* `farmers_merchants` is the weakest-evidence registration in the registry: its
  only corpus document contains no issuer identification at all. Worth
  revisiting when a second Farmers & Merchants statement exists to compare
  against.
