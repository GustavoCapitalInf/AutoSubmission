# Agent Handoff - ADB-DOCTRINE (batch 5 - READ-ONLY underwriting investigation)
**You change NOTHING: no commits, no branch, no repo edits. Measurement
scripts live in your private scratchpad subdir only. Your product is a
six-item decision packet for a financial-core ruling.**

# The doctrine you are investigating under (Gustavo, 2026-08-15, binding)
The platform's metrics are UNDERWRITING metrics for lenders/MCA funders.
BANK-REPORTED AVERAGE BALANCE and UNDERWRITING ADB are separate concepts:
the bank's printed figure is evidence to preserve, never a definition to
adopt. No bank's proprietary convention (e.g. Woodforest's observed n+1
divisor) may redefine the platform ADB. The goal is one canonical
apples-to-apples methodology across every bank, with explicit
funder-policy profiles ONLY if different lenders genuinely require
different denominator conventions. Do not infer methodology from what a
particular bank prints.

# Identity
- **Agent:** ADB-DOCTRINE - produce the ruling packet. No implementation.

# The six deliverables (Gustavo's list, verbatim intent)
1. **The current platform ADB definition** - read analysis/adb.py
   completely and state it precisely: denominator basis (calendar days of
   the printed period? posting days? how are non-posting days carried?),
   opening-state handling, the daily-walk construction, what
   stated_daily_balances vs reconstructed walks change, rounding, the
   required-checks set, and where the definition is consumed
   (metrics.py, webapp surfaces, packages). Name every place the
   definition leaks into other published numbers.
2. **Comparison with common MCA/lender underwriting practice** - use
   WebSearch for current industry practice (MCA underwriting ADB
   conventions: calendar-month vs statement-period, calendar-day vs
   banking-day closing balances, negative-day treatment, month
   normalization across statement lengths). Cite sources; distinguish
   established practice from vendor marketing.
3. **MoneyThumb/our benchmark behavior where measurable** - the
   benchmark/ package compares our pipeline vs MoneyThumb vs audited
   expectations over 6 benchmark sets (python -m benchmark, offline,
   reports to gitignored benchmark_reports/). Run it; extract every
   ADB-relevant comparison; characterize MoneyThumb's apparent
   denominator/basis where the data allows (do NOT treat MT as truth -
   H-2's law); check PARITY_MATRIX.md and any MT documentation in the
   repo.
4. **Calendar-day vs business/banking-day effect across the audited
   corpus** - compute BOTH methodologies (and the current platform
   definition if distinct) over the pinned 109 AND a stratified archive
   sample (>=400 validated docs across families, artifact-store
   enumeration): distribution of deltas (median/p90/max, by family),
   which documents flip any downstream threshold (metrics.py consumers -
   survey which decisions key on ADB), and the weekend/holiday carry
   question (a Friday close carried over Sat/Sun: calendar counts it 3x,
   banking-day 1x - measure how much that moves ADB by family).
   US federal holidays: state your calendar assumption explicitly.
5. **Your recommended canonical underwriting invariant** - one
   definition, stated as an invariant sentence, with the Woodforest
   initialization case resolved under it (opening state when the strict
   gates prove it; denominator per the canonical rule, NOT the bank's),
   and the architectural split Gustavo named: underwriting_adb,
   bank_reported_average_balance, underwriting_adb_basis/policy,
   bank_reported_average_variance - as a DESIGN (fields, where computed,
   what the gate/audit CSVs would pin), not code.
6. **Whether configurable funder-specific ADB profiles are warranted** -
   evidence-based: do the measured deltas (item 4) and industry survey
   (item 2) show populations where funders genuinely diverge? What would
   a policy profile touch (computation? selection-at-publication? both
   computed always)? Recommend for/against with the cost stated.

# Hard rules
Read-only everywhere; direct artifact paths only (never the sqlite
index); $0 vendor except WebSearch; the current ADB semantic is NOT
ambiguous-by-default - characterize what it IS before comparing; no
recommendation may silently move pinned expectations (if your
recommended invariant would move any pinned document's published ADB,
enumerate every mover in a ceremony-ready table).
Base main `e935f98`; run of record
discovery_reports/2026-08-15T111704.195314-0000-c924d751.

# Final report to Ocean
The six items, in order, with the measurement tables inline; then the
one-page executive summary Gustavo will rule from.
