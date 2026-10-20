"""MoneyThumb comparison harness (Wave 1, task H-2).

Re-runnable, fully offline comparison of the MoneyThumb benchmark result sets
against our pipeline output, the original statement evidence, and the
independently audited expectations in ``docs/adb-audit-results.csv`` and
``docs/balance-metrics-audit-results.csv``.

MoneyThumb is NEVER automatic ground truth.  Every compared field is
classified into exactly one of the eight outcomes defined in
``benchmark.classify.Outcome`` using the precedence rules documented there.

Reports are written to a gitignored output directory (default
``benchmark_reports/``) and are never committed.  ``moneythumbResults/`` is
treated strictly read-only.
"""
