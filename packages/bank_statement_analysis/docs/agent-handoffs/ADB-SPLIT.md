# Agent Handoff - ADB-SPLIT (batch 5 - the ratified ADB doctrine, implemented)
Ocean reviews and merges; you never merge or push.
**Protected cell: analysis/adb.py, analysis/schema.py, analysis/metrics.py,
analysis/serialization.py, corpus_gate.py + both audit CSVs (prepared
additively), analysis/woodforest.py (two declaration lines). Pinned-diff
discipline on every protected hunk; Ocean forensic review at merge.**

# The ratified doctrine (Gustavo 2026-08-15, binding verbatim)
- CANONICAL UNDERWRITING ADB: sum of end-of-day balances for every
  calendar day of the printed statement period / number of calendar days
  in that printed period; prior end-of-day carried on no-activity days;
  uniform across every bank, country, parser family, weekend, holiday.
  Bank-reported averages are evidence only. MoneyThumb's banking-day
  construction is never canonical; MT is a benchmark, not ground truth.
- PRODUCT INVARIANT: one statement or package -> ONE user-facing
  "Average Daily Balance", always the canonical underwriting ADB. No
  dashboard cards for bank-reported/business-day/alternate/variance/
  hypothesis figures - those exist internally (audit, diagnostics,
  provenance, API metadata) only.
- ANY UNEXPECTED PINNED FINANCIAL MOVEMENT IS A HARD STOP.

# The work (evidence base: the ADB-DOCTRINE packet's design, restated here)

## Card 1 - the additive split
In analysis/adb.py (computed on the ledger it already builds):
- underwriting_adb (float|None) - semantic rename of average_daily_balance;
  keep the old name as a deprecated alias so NO consumer breaks (survey
  every consumer; zero behavior change).
- underwriting_adb_basis = "calendar_day_printed_period" - a frozen
  literal stamped on the result, not a knob.
- underwriting_adb_policy = "canonical_v1".
- underwriting_adb_alternates: dict {banking_day, weekday_only,
  posting_day, credit_only, beginning_of_day} - computed always from the
  same validated ledger (one pass; opening_balance already carried);
  NULLED alongside the canonical value when required checks fail (an
  unvalidated ledger yields no valid basis of any kind). Internal only:
  serialization may carry them in the payload but NO webapp dashboard
  card (verify the dashboard renders exactly one ADB metric after your
  change - name the surfaces you checked).
In analysis/schema.py: bank_reported_average_balance as the rename-with-
alias of stated_average_balance; bank_reported_average_label (str|None)
captured ONLY where a parser already reads the printed average (no new
parser reads in this card - survey which parsers set it and add label
capture there; the label is the printed heading verbatim).
In analysis/metrics.py: bank_reported_average_variance (signed,
underwriting_adb - bank_reported_average_balance), _variance_pct, and
bank_reported_average_hypothesis in {agrees, credit_only_floored,
collected_or_float, beginning_of_day_alignment, n_plus_1_zero_forward,
unexplained} - diagnostic, never authoritative; state each
discriminator's rule in the code.

## Card 2 - the gate + audit pins
- docs/adb-audit-results.csv + balance CSV: ADD columns
  underwriting_adb_basis, underwriting_adb_policy,
  bank_reported_average_label, bank_reported_average_variance; existing
  columns byte-for-byte unchanged (that identity IS the additive proof).
- corpus_gate.compare_rows gains the new columns; one new total
  assertion: underwriting_adb_basis == "calendar_day_printed_period" on
  all 109 - the doctrine, mechanically enforced so no code path can
  silently substitute another basis.
- Do NOT pin per-document alternates; pin the semantic invariant instead
  (for every pinned doc, alternates.banking_day != underwriting_adb
  unless the period contains no non-banking day).

## Card 3 - H1 (approved conditional)
Promote opening_balance_matches_statement into the required set. The
measured claim is 0 movers (opening is bank-stated on 2,579/2,579);
your job is to REPRODUCE that zero-mover result on the current tree -
if ANY document moves, STOP and report (the approval is conditional on
the reproduction).

## Card 4 - H2 (approved)
Correct benchmark/compare.py:101-114 ("activity-day" -> banking-day,
describing only reproduced behavior: 11/11 federal-calendar set match,
10/10 self-mean, 4/4 reproduction from our ledger) and
PARITY_MATRIX.md rows 9-10 (it IS recomputable). Reframe the six
OUR_SYSTEM_CORRECT adb verdicts as definition-relative. Never describe
undocumented MT behavior as specification.

## Card 5 - Woodforest under doctrine (RESOLVED - implement)
Apply the CORRECTED pinned adb.py diff from W3 #WFINIT WF4 + amendments
(the wave4-wfinit branch, merged, holds initialization_postings with the
G3 positive-credit gates): the schema field
(initialization_transaction_count or the corrected design's equivalent)
lands in the SAME commit; the consuming layer enforces
day == period_start - 1 exactly AND a positive fold (seeded > 0, all
declared postings credits); the divisor NEVER changes (the pre-period
day is never a period day); the parser declares (the two lines in
analysis/woodforest.py per WF4's design). Expected movement: EXACTLY the
two named documents (D9EF1A8C..., 823DCE7F...) withheld -> validated IF
every other independent gate passes - verify each gate honestly, and
their bank_reported_average_variance records the (N+1)/N gap with
hypothesis n_plus_1_zero_forward. Nothing else moves: full family sweep
(20 docs) + the archive. The two docs are NOT pinned - but re-verify
zero pinned movement anyway (the hard stop).

# Proof floor
Suite + corpus-marked + gate GREEN (verdict line intact) + guards +
conformance; the 109 audit CSVs byte-identical on existing columns; the
whole-archive differential: expected movers = the 2 Woodforest docs
ONLY (every other payload byte-identical apart from the additive fields
- name the additive-field diff shape explicitly so the instrument can
verify it); exit codes verbatim. ANALYSIS_STAGE_VERSION bump is Ocean's
at merge (this changes every payload additively + 2 outcomes).

# Standing wave rules (binding)
Read PROJECT_STATUS.md + the 08-15 entries first. Base main `bbe5cf1`
(v12, OCR v3, registry 71). Run of record c924d751. Archive/caches
read-only, direct artifact paths only, $0, private scratchpad subdir,
sequential long proofs, every mover named, claimed != validated, clean
tree, never merge or push.

# Final report to Ocean
Pinned-exposure first (audit CSV byte-identity + gate); hunks verbatim;
the two-mover enumeration with per-gate results; the additive-field
shape; alternates spot-audit (10 docs, five bases recomputed
independently); proofs; commits; risks.
