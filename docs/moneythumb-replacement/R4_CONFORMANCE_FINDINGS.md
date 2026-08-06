# R-4 conformance findings — three parser defects, reported not fixed

Author: Agent A (REEF). Date: 2026-08-06. Status: **REPORTED — awaiting Ocean triage.**
Raised by: the R-4 conformance harness (`tests/test_parser_conformance.py`).
Standing rule applied: WAVE2_BRIEF §3 R-4 — "any defect found is reported to
Ocean, not silently fixed".

All three are **detection** defects. None changes any corpus outcome today: the
suite is green, the corpus gate is GREEN byte-identical, and all 109 pinned
documents still resolve to their recorded parser. They matter because DSC-2 is
about to put 3,506 foreign documents through this dispatch, and each of these
is a way to claim a document that is not yours.

Every finding is pinned by a test that asserts the affected set **exactly**, so
it can neither grow unnoticed nor be quietly forgotten: fixing a parser makes
the pin fail until its entry is removed.

---

## R4-1 — `first_farmers` detects its own corpus document via the filename

**Severity: high.** The only defect here that affects a document we ship.

`analysis/first_farmers.py` requires the marker `FIRST FARMERS`. In its single
corpus document, `Misc/First Farmers 2026 01-document.pdf`, that string appears
**nowhere in the statement body**. It is matched from the source comment the
OCR layer prepends:

```
<!-- source: First Farmers 2026 01-document.pdf | pages: 3 | model: local-tesseract-ocr | empty: 0 -->
```

Strip that line and the score falls 0.5 → 0.3 and the parser stops claiming its
own document. The other three markers (`BUSINESS BASIC CHECKING ACCOUNT`,
`BALANCE LAST STATEMENT`, `TOTAL DAYS IN STATEMENT PERIOD`) are genuinely
present.

Consequences:

* **Rename the file and the parser stops recognising the statement.** Coverage
  currently depends on an operator-chosen filename.
* The corpus gate passes on this document partly because of its filename. It is
  a scanned (local-tesseract) source, so the bank name is presumably lost to
  OCR rather than absent from the paper.
* On the discovery archive, folder-derived names make this failure mode both
  more likely to fire and more likely to fire *wrongly*.

Proposed fix (not applied): replace `FIRST FARMERS` with issuer furniture that
survives OCR of that layout, or scope detection to the body by stripping the
source comment before matching. The latter is a platform-level change and would
also close R4-2 — see "Recommended platform fix" below.

Tests: `test_first_farmers_does_not_detect_on_the_filename` (fast, xfail-strict),
`test_detection_is_invariant_to_the_filename_echo` (corpus, pins the set).

## R4-2 — `relay` scores a filename-derived marker

**Severity: low.** No claim decision changes.

On `CIBC French/Account Statement 1.pdf` the `relay` marker `ACCOUNT STATEMENT`
matches the filename `Account Statement 1.pdf`, not the document. Relay needs
four required markers and only this one fires, so it does not claim — but the
detection score rises 0.0 → 0.1.

That is not cosmetic: the sub-threshold score is exactly the signal DSC-2 uses
to rank near-misses and unknown-layout clusters
(`test_a_counterparty_mention_still_scores_above_nothing`). Metadata-derived
score inflates it.

Tests: `test_relay_scores_nothing_from_the_filename` (fast, xfail-strict), plus
the corpus invariance test above.

## R4-3 — six parsers claim a statement that merely names them

**Severity: moderate; high for DSC-2.**

Exactly the defect class R-3.4 fixed for `capital_one`, `bmo`, `regions`,
`bank_of_america` and `scotiabank` — in six parsers no corpus document happens
to mention, so the corpus parity control could not see them.

Each declares **exactly one required marker, and that marker is a bank name**:

| Parser | Sole required marker |
|---|---|
| `chase` | `JPMorgan Chase Bank` or `\nCHASE\n` |
| `consumers` | `ConsumersCU.org` or `Consumers Credit Union` |
| `dakota_west` | `dakotawestcu.com` |
| `first_citizens` | `First Citizens` or `Central Bank Operations` |
| `mission_valley` | `Mission Valley Bank` |
| `texas_bank` | `Texas Bank and Trust` or `6250TEXAS` |

Give any of them another bank's statement containing
`01/15 ACH DEBIT PAYMENT TO <that bank> 250.00` and it claims the document.

`chase` is the one to worry about. "JPMorgan Chase Bank" appears in wire
instructions, ACH originator strings and remittance advice across the industry,
and Chase is the largest folder in the discovery archive (618 documents) — so
both the false-claim rate and the blast radius are highest there.

Why it did not surface in R-3.4: the corpus contains no statement that names
these six as a counterparty. This is precisely the coverage gap R-4's synthetic
cross-product exists to close — the corpus is corpus-shaped (G1), and detection
correctness cannot be measured only against it.

Proposed fix (not applied): the R-3.4 remedy, applied to these six — one
issuer-furniture required marker each, chosen under the same constraints
(issuer domains, section headings, regulatory footers; never customer names,
dates, amounts, account numbers or fitted offsets), each with a
detection-positive and a detection-negative test.

Tests: `test_a_bank_name_in_a_transaction_line_is_not_a_claim` (xfail-strict
per parser), `test_the_set_of_counterparty_vulnerable_parsers_is_exactly_the_recorded_finding`,
`test_every_counterparty_vulnerable_parser_declares_a_single_bank_name_marker`.

---

## Recommended platform fix (one change, closes R4-1 and R4-2)

Strip the `<!-- SOURCE: ... -->` comment before detection runs — once, in
`analysis/parser_registry.py`, rather than in 46 parsers. Filename text would
then be structurally inadmissible as evidence, which is what the RFC's detect
contract already says in prose.

It is a one-line change to `score_markers`/`make_detector` **and it would break
`first_farmers` on its own corpus document**, so it cannot land without R4-1's
marker fix in the same commit. Both are detection-semantics changes and need
Ocean's ruling; neither is applied here.

## R-1 residuals observed while building the fixtures

Not new defects, and not in scope — logged with the Wave-3 R-1 residual sweep
already opened in `R3_DETECTION_FINDING.md` §7:

* `farmers_merchants` detection matches a **customer name**
  (`ACE AUTO GLASS`) as one branch of its bank-identity marker.
* `altana` requires `FREE BUSINESS CHECKING ID 0050` and `texas_bank` accepts
  `6250TEXAS` — both embed digit runs in detection evidence.

The R-4 fixtures deliberately exercise the *other* branch of each, so the
conformance suite does not depend on a residual it is reporting.

## Triage asks

1. R4-1 — high, affects a shipped document. Fix in Wave 2 or schedule?
2. R4-3 — six parsers, same approved remedy as R-3.4. Same session, or a
   separate R-4b card?
3. The platform fix above — worth doing as the general answer, given it must be
   sequenced with R4-1?
