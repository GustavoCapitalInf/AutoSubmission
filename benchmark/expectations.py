"""Read-only access to the independently audited expectations.

Sources (never modified by the harness):
- ``docs/adb-audit-results.csv``       - period, transaction count, independent
  calendar-day ADB, printed-average commentary, per-statement audit status.
- ``docs/balance-metrics-audit-results.csv`` - audited opening/ending/highest/
  lowest balances, bank, account, source hash, audit status.

A row whose status is not PASS (e.g. WITHHELD_SOURCE_CONTRADICTION for the
BMO statement) contributes NO numeric expectation for the withheld fields;
instead it flags the statement as source-contradicted, which the classifier
consumes as precedence rule 4.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .normalize import parse_money, parse_int


@dataclass
class Expectation:
    """Merged audited expectations for one statement filename."""

    statement: str
    bank: str | None = None
    account: str | None = None
    sha256: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    transactions: int | None = None
    opening: float | None = None
    ending: float | None = None
    highest: float | None = None
    lowest: float | None = None
    adb: float | None = None                 # independent calendar-day ADB
    adb_ledger_valid: bool = False
    printed_adb: float | None = None
    printed_adb_label: str | None = None
    balance_status: str | None = None
    balance_root_cause: str | None = None
    adb_status: str | None = None
    adb_root_cause: str | None = None

    @property
    def source_contradiction(self) -> bool:
        """True when the audit withheld values because the source conflicts."""
        for status in (self.balance_status, self.adb_status):
            if status and ("WITHHELD" in status or "CONTRADICTION" in status):
                return True
        return False


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_expectations(docs_dir: Path) -> dict[str, Expectation]:
    """Key: statement filename (as recorded in the audit CSVs)."""
    merged: dict[str, Expectation] = {}

    for row in _read_rows(docs_dir / "balance-metrics-audit-results.csv"):
        name = row["statement"]
        contradicted = "WITHHELD" in (row.get("status") or "") or "CONTRADICTION" in (
            row.get("status") or ""
        )
        expectation = merged.setdefault(name, Expectation(statement=name))
        expectation.bank = row.get("bank") or None
        expectation.account = row.get("account") or None
        expectation.sha256 = row.get("sha256") or None
        expectation.balance_status = row.get("status") or None
        expectation.balance_root_cause = row.get("root_cause") or None
        if not contradicted:
            expectation.opening = parse_money(row.get("expected_opening"))
            expectation.ending = parse_money(row.get("expected_ending"))
            expectation.highest = parse_money(row.get("expected_highest"))
            expectation.lowest = parse_money(row.get("expected_lowest"))

    for row in _read_rows(docs_dir / "adb-audit-results.csv"):
        name = row["statement"]
        expectation = merged.setdefault(name, Expectation(statement=name))
        expectation.adb_status = row.get("status") or None
        expectation.adb_root_cause = row.get("root_cause") or None
        expectation.period_start = row.get("period_start") or None
        expectation.period_end = row.get("period_end") or None
        expectation.transactions = parse_int(row.get("transactions"))
        expectation.printed_adb = parse_money(row.get("printed_adb"))
        expectation.printed_adb_label = row.get("printed_adb_label") or None
        ledger_valid = (row.get("independent_ledger_valid") or "").strip() == "True"
        expectation.adb_ledger_valid = ledger_valid
        if (row.get("status") or "") == "PASS" and ledger_valid:
            expectation.adb = parse_money(row.get("independent_candidate_adb"))
        if not expectation.bank:
            expectation.bank = row.get("bank") or None

    return merged
