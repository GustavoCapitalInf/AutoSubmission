# R-1 Hardcode Purge — Inventory & Ruling Log

Agent A, Wave 1, branch `wave1-benchmark-parsers`. Spec: WAVE1_PROMPT_R1.md.
Rulings: **generalized** (evidence-gated rule), **registry** (counterparty
knowledge moved to the maintained registry with fixtures), **fail-closed**
(guess replaced by explicit refusal), **removed-no-op** (dead constant
deleted with provably identical behavior), **proposed** (queued for Ocean —
code unchanged).

Corpus-parity proof for every item: per-statement before/after diffs run
against HEAD during development (byte-identical transactions and audited
fields), plus corpus gate GREEN (106 PASS / 3 WITHHELD, field-identical) —
tails in the handoff. Fixture tests: `tests/test_r1_hardcodes.py`; guard:
`tests/test_no_statement_hardcodes.py`.

## Item 1 — `scanned_small_bank.py` literal check repair → **generalized**

- Was: repair keyed to literal date `2026-06-18` + `Check 1944` + amount
  −4500.00→−1500.00, with a caption regex hardcoding the same values.
- Now: `_repair_checks_from_image_captions` — the statement's own
  check-image captions (`Number: N Date: m/d/yyyy Amount: $X`) are generic
  in-document evidence. A parsed `Check N` row is corrected only when the
  printed summary identity currently fails, the caption matches the row's
  number AND date with a different amount, and the correction restores the
  identity exactly. Applied to both Southside and Apex paths (no-op when the
  ledger already reconciles).
- Evidence: Builder June 2026 output byte-identical; positive/negative
  fixtures (caption repairs, bogus caption ignored, non-restoring caption
  ignored, wrong-date caption ignored).

## Item 2 — customer names as parser gates → **generalized**

- Was: `THE GRANITE GIRLS, LLC` account-name literal (Southside);
  `KLR ENTERPRISES` gate + `KLR Enterprises` account-name and
  continuation-page scrub literals (Apex).
- Now: Apex gates on structural markers ("SUMMIT BUSINESS CHECKING" +
  "Balance Forward From" + "Ending Balance As Of"). Account holders come
  from `_extract_holder_name` — a business-entity-suffix marker (LLC/INC/
  CORP/LTD/LLP/PLLC/COMPANY/ENTERPRISES) scanned over the first page's
  header block. The Apex continuation-page scrub is anchored on the holder
  name extracted from the document itself.
- Evidence: KLR + Builder byte-identical (including account_name values);
  fixtures prove an arbitrary holder ("ACME LOGISTICS LLC") parses and is
  extracted.

## Item 3 — `len(txns) < 20` magic threshold → **generalized**

- Now: completeness is checked against the statement's own printed
  credit+debit counts (`len(txns) < stated_credit_count + stated_debit_count
  → None`); zero stated counts also fail closed.
- Evidence: KLR (81 parsed = 11+70 stated) unchanged; fixture shows a
  16-row statement now parses when its detail matches its printed counts,
  and a statement missing one stated row fails closed.

## Item 4 — `community_section` scrub list → **generalized**

- Was: `GREEN CONVERGENCE|FIELD TRUCKING LLC` literal page-header scrub;
  Mission Valley gate requiring the literal customer name.
- Now: page headers are scrubbed by the platform's structural marker (line
  ending in `Page N of M`); the Mission Valley gate is the bank marker
  alone.
- Evidence: Field Trucking + Mission Valley byte-identical; fixtures with
  unrelated customer names.

## Item 5 — Dakota West literal account `35127380` → **generalized**

- Now: account sections are discovered from the document's own
  `<product> (Checking|Savings) - <number>` headings; each candidate block
  is truncated at the next account's heading (a section's summary can never
  be attributed to another account); the busiest section wins
  (primary-account semantics, matching production single-account behavior).
- Evidence: Field Trucking byte-identical (selects ****7380 by activity,
  not by literal); fixtures with different account numbers and a
  no-headings fail-closed case.

## Item 6 — Chase repair on exactly −1000.00 → **generalized**

- Now: evidence-gated fused-count-digit repair: printed summary identity
  must fail by a negative delta; a Remote Online Deposit row must exist
  whose corrected amount (amount + delta) has digits that are a proper
  suffix of the parsed digits (i.e. a leading fused count prefix); and the
  single correction must restore the identity exactly. Works for any fused
  count magnitude, never fires on reconciled statements.
- Evidence: Chase corpus unchanged (gate); fixtures for 1-prefix, 2-prefix,
  non-prefix-shaped delta (no repair), already-reconciled (no repair),
  non-Chase (no repair).

## Item 7 — `rbc.py` counterparties + French parser → **removed-no-op / generalized**

- Counterparty names in `_is_debit` (two entries): **removed-no-op** — the
  code path that consulted them assigned the same sign as the default
  branch, and the printed-balance segment solver has the final word. All 4
  RBC English corpus statements byte-identical.
- French parser: **generalized + fail-closed** — the printed period line is
  now fully parsed (day + French month name + year, both bounds, any
  months) with a proper French month table (unambiguous-prefix resolution);
  the `(2025, 2026)` default years and hardcoded period days (Dec 2/Jan 2)
  are gone; a missing/unparseable period line fails the parser closed;
  transaction dates take the unique year that places them inside the
  printed period, else the row is skipped. French corpus statement
  byte-identical; fixtures cover a March–April period, a cross-year period,
  and the fail-closed missing-period case.

## Item 8 — `td_can.py` merchant sign lists → **generalized**

- Was: sign decided by merchant-name lists (native path) and merchant-name
  overrides of the printed credit column (table path).
- Now: native-path sign comes from TD's own structural transaction codes:
  `TFR-FR`/`E-TRANSFER` credit vs `TFR-TO`/`SEND E-TFR` debit; trailing
  type codes MSP/CLN/PAY/GST credit, BUS debit. This reproduces the sign of
  every native TD Can corpus row byte-identically (all 6 documents
  verified) — the merchant lists were redundant encodings of these codes.
  Table path: the printed DEPOSIT/CREDIT column is trusted (reconciliation
  fails closed downstream on extraction errors); a column-shifted amount
  with no printed column emits only on a generic credit signal, else the
  row is skipped. A "2025" default year in the table path (same fabricated-
  year class as item 9) now fails closed instead.
- Evidence: 6/6 TD Can corpus docs byte-identical; code-based sign
  fixtures incl. former merchant names; printed-column-wins fixture.

## Item 9 — `wells.py` year default 2026 → **fail-closed**

- Now: `_infer_year` returns None when the document prints no 4-digit year;
  the parser returns None (no invented dates). Fixtures: year honored;
  yearless statement refused.

## Item 10 — `wilson_muir.py` `days_in_period=30` → **generalized**

- Now: derived from the printed period bounds ((end − start) + 1), still
  None when the statement date's year conflicts with the period end
  (fail-closed OCR guard). WMB corpus value unchanged (30); fixture proves
  a 27-day period yields 27.

## Item 11 — mojibake regexes → **generalized (normalize first)**

- Finding: the corpus text contains REAL characters (é, —, curly quotes);
  the mojibake sequences lived in the SOURCE regexes, where they either
  duplicated the real character alternatives or (RBC French account regex)
  could never match at all.
- Now: `td_can.normalize_mojibake` repairs double-encoded input first
  (strict cp1252→utf-8 reversal, targeted table for mixed content,
  NBSP→space); parsers match real characters only; mojibake byte sequences
  appear in source exclusively as escape literals. Applied at the entry of
  the Southside/Apex/RBC-French parsers. Fixtures include an end-to-end
  double-encoded French statement.
- Note: the Southside account-number quote class was dead weight — its
  removal preserves the audited extraction (digits must directly follow the
  label, which is what actually matched the audited `****6833` value).

## Item 12a — pre-approved registry entries → **registry** (Ocean-approved)

- Added to `CONFIRMED_LENDER_ALIASES` with H-2 evidence cited in-place:
  - `AFC FUNDING CORP` — aliases ("AFC FUNDING CORP", "AFC FUNDING");
    WMB May 25: 3 debits totaling 18,977.11.
  - `INTUIT FINANCING` — alias ("INTUIT FINANCING") only, deliberately a
    two-word phrase so ordinary Intuit/QuickBooks software charges cannot
    match; WMB May 25: 6 QuickBooks Capital payments totaling 3,967.17.
- Fixtures: both classify as confirmed_lender with correct canonical
  entities; the H-2 negative case (−37.10 `VSA PUR INTUIT QBOOKS ONLINE`)
  is asserted non-lender.
- **Amended 2026-09-24 and 2026-09-25 (owner rulings, lender-detection design §2):**
  `INTUIT FINANCING` is no longer a lender. It moved from the lender registry
  to `ALTERNATIVE_POSITION_ALIASES` and is classified `alternative_position`:
  a flagged position, outside lender count, lender totals and withholding. The
  two-word alias and the negative software case are unchanged; the fixture now
  asserts `alternative_position`. `AFC FUNDING CORP` moved to Floor plan (owner
  ruling 2026-09-25): it is not a lender, and it is flagged like an alternative
  position. Its fixture now asserts `floor_plan_financing`.

## Item 12b — registry counterparty entries → **proposed** (code untouched)

1. `classification_registry.py:143` — `"11-101 Signal R": ("11 101 SIGNAL
   R", "SIGNAL R")` as an operating revenue source. Analysis: "SIGNAL R"
   alone is a dangerously generic two-token alias (any description
   containing "signal r" verifies revenue); the entity looks like a single
   customer's tenant/counterparty ("11-101" reads as a unit number), i.e.
   memorized single-statement knowledge in LEDGER-owned data.
   **Recommendation:** drop the bare "SIGNAL R" alias; keep (or delete
   entirely) the fully-qualified "11 101 SIGNAL R" only if the sourcing
   statement legitimately recurs; classification falls back to
   unverified_deposit (review) — fail-closed, no fabricated verification.
2. `classification_registry.py:42` — `"3329001101"` as an Eminent Funding
   alias. Analysis: this is an ACH company/originator ID. Originator IDs
   are stable per originator and are genuine counterparty evidence, but a
   bare 10-digit alias can collide with any other number field
   (invoice/reference numbers) under token matching.
   **Recommendation:** keep the knowledge but qualify it — either alias it
   as the full descriptor pair ("EMINENT FUNDING 3329001101") or introduce
   a dedicated originator-ID registry matched only against parsed ACH
   originator fields, then remove the bare numeric alias.
3. `classification_registry.py:33-34` — `"LCM 1823095"`, `"MC 844 662
   3467"` as CFGMS aliases. Analysis: a processor batch/reference token and
   a phone number. The phone number is CFG's own callback number printed in
   ACH descriptors — real evidence, but weak as a standalone alias;
   "LCM 1823095" looks like a single statement's reference (memorized
   instance).
   **Recommendation:** remove "LCM 1823095" (single-instance reference);
   keep "MC 844 662 3467" only in combination with a financing-context
   requirement (or move to a phone-number evidence table); rows losing the
   alias fall back to potential-lender/review via the generic financing
   heuristics — fail-closed.
   
   No registry code or data beyond item 12a was modified; these three are
   queued for Ocean's ruling.

## Extra (same class, discovered in scope) — RBC French account extraction

The dead mojibake account regex is deleted (item 7/11). Enabling a working
`numéro de compte` extraction would populate `account_number`
(****6152) for the French statement — a strict improvement but a change to
an audited gate field (`account` column of the balance CSV). Left disabled;
**proposed** for an Ocean-approved deliberate re-baseline.
