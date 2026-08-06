from __future__ import annotations

import csv
import hashlib
from collections import Counter
from pathlib import Path

from analysis.schema import Statement, Transaction
from balance_forensic_audit import independent_balances


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "balance-metrics-audit-results.csv"


def _rows() -> list[dict[str, str]]:
    with RESULTS.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_balance_audit_inventory_and_source_hashes_are_complete():
    """The audit pins 109 distinct paths, and every one is on disk unchanged.

    Scoped to the pinned manifest, not to whatever the directory holds: the
    corpus root is shared with untracked discovery material (see
    `corpus_gate.check_foreign_files`), so an equality against an rglob of the
    root would assert a property the tree is not meant to have. What matters —
    no audited statement may vanish, be renamed, or change bytes — is unchanged.
    """
    rows = _rows()
    audited_paths = {row["path"] for row in rows}

    assert len(rows) == 109
    assert len(audited_paths) == 109
    for row in rows:
        source = ROOT / "Bank Statements" / Path(row["path"])
        assert source.is_file(), row["path"]
        digest = hashlib.sha256(source.read_bytes()).hexdigest().upper()
        assert digest == row["sha256"], row["statement"]


def test_balance_audit_has_no_unresolved_production_difference():
    rows = _rows()
    statuses = Counter(row["status"] for row in rows)

    assert len({row["bank"] for row in rows}) == 44
    assert len({row["parser"] for row in rows}) == 44
    assert statuses == {
        "PASS": 106,
        "WITHHELD_SOURCE_CONTRADICTION": 3,
    }
    assert all(row["exports_valid"] == "True" for row in rows)
    assert all(row["dashboard_binding_valid"] == "True" for row in rows)
    for row in rows:
        assert row["opening_difference"] == "0.00"
        assert row["ending_difference"] == "0.00"
        assert row["highest_difference"] == "0.00"
        assert row["lowest_difference"] == "0.00"
        for metric in ("opening", "ending", "highest", "lowest"):
            expected = row[f"expected_{metric}"]
            assert row[f"production_{metric}"] == expected
            assert row[f"api_{metric}"] == expected
            assert row[f"csv_{metric}"] == expected
            assert row[f"xlsx_{metric}"] == expected
            assert row[f"package_{metric}"] == expected


def test_withheld_balance_ledgers_never_publish_daily_extrema():
    rows = {
        row["statement"]: row
        for row in _rows()
        if row["status"] == "WITHHELD_SOURCE_CONTRADICTION"
    }
    assert set(rows) == {
        "Ace_Auto_Final_Cut.pdf",
        "BMO_Statement_January_2026 Final-1-2 (1).pdf",
        "IBC April (1).pdf",
    }
    for row in rows.values():
        assert row["expected_highest"] == ""
        assert row["production_highest"] == ""
        assert row["expected_lowest"] == ""
        assert row["production_lowest"] == ""
    assert rows["IBC April (1).pdf"]["source_ending"] == "18442.35"
    assert rows["IBC April (1).pdf"]["expected_ending"] == ""


def test_independent_oracle_uses_daily_ending_not_intraday_extrema():
    statement = Statement(
        bank="Audit Bank",
        period_start="2026-01-01",
        period_end="2026-01-03",
        beginning_balance=100.0,
        ending_balance=150.0,
        transactions=[
            Transaction(
                date="2026-01-01",
                description="Temporary intraday credit",
                amount=900.0,
                direction="credit",
                running_balance=1000.0,
            ),
            Transaction(
                date="2026-01-01",
                description="Same-day debit",
                amount=-850.0,
                direction="debit",
                running_balance=150.0,
            ),
        ],
    )

    result = independent_balances(statement, "")

    assert result.valid
    assert result.lowest == result.highest == 150
    assert list(result.daily.values()) == [150, 150, 150]


def test_raw_daily_table_outranks_transaction_processing_dates():
    statement = Statement(
        bank="Columbia Bank",
        period_start="2026-01-01",
        period_end="2026-01-02",
        beginning_balance=100.0,
        ending_balance=100.0,
        transactions=[
            Transaction(
                date="2026-01-01",
                description="Processing-date credit",
                amount=50.0,
                direction="credit",
            ),
            Transaction(
                date="2026-01-02",
                description="Processing-date debit",
                amount=-50.0,
                direction="debit",
            ),
        ],
    )
    source = """
Daily Balances
Date Amount
01-01 100.00
01-02 100.00
Overdraft Fee Summary
"""

    result = independent_balances(statement, source)

    assert result.valid
    assert result.evidence.startswith("raw_bank_daily_ending_table")
    assert result.lowest == result.highest == 100


def test_balance_audit_oracle_does_not_import_production_balance_calculators():
    source = (ROOT / "balance_forensic_audit.py").read_text(encoding="utf-8")
    assert "from analysis.adb" not in source
    assert "import analysis.adb" not in source
    assert "from analysis.metrics" not in source
    assert "import analysis.metrics" not in source
