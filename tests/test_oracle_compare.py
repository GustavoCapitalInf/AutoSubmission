"""Fabricated payloads only. The oracle comparison reports names, counts and flags, never values."""
import copy
import json

from tools.phase3_pair.oracle_compare import compare


def _payload():
    return {
        "statement": {
            "period_start": "2031-01-01", "period_end": "2031-01-31",
            "beginning_balance": 100.0, "ending_balance": 97.0, "currency": "USD",
            "currency_source": "schema_default",
            "transactions": [
                {"date": "2031-01-05", "description": "FABRICATED FEE", "amount": -1.5, "direction": "debit"},
                {"date": "2031-01-05", "description": "FABRICATED FEE", "amount": -1.5, "direction": "debit"},
            ],
        },
        "metrics": {"total_withdrawals": 3.0, "average_daily_balance": 97.6, "adb_ok": True, "nsf_source": "x"},
        "reconciliation": {"ok": True, "summary_ok": True},
    }


def test_identical_payloads_match_everywhere():
    report, detail = compare(_payload(), _payload())
    account = report["per_account"][0]
    assert report["metrics_differing"] == [] and report["statement_fields_differing"] == []
    assert account["transactions"]["matched_on_date_amount_direction"] == 2
    assert account["transactions"]["descriptions_byte_equal"] == 2
    assert detail["per_account"][0]["rows_only_in_visual"] == []


def test_a_missing_row_and_a_wrong_metric_are_named_without_values():
    visual = _payload()
    visual["statement"]["transactions"].pop()
    visual["metrics"]["total_withdrawals"] = 1.5
    report, detail = compare(visual, _payload())
    account = report["per_account"][0]
    assert account["transactions"]["only_in_oracle"] == 1 and account["transactions"]["only_in_visual"] == 0
    assert report["metrics_differing"] == ["total_withdrawals"]
    summary = json.dumps(report)
    assert "FABRICATED" not in summary and "1.5" not in summary   # no values in the shareable summary
    assert detail["per_account"][0]["metrics"]["total_withdrawals"] == {"visual": 1.5, "oracle": 3.0}


def test_float_tolerance_and_booleans():
    visual = copy.deepcopy(_payload())
    visual["metrics"]["average_daily_balance"] = 97.604
    visual["metrics"]["adb_ok"] = 1
    report, _ = compare(visual, _payload())
    assert "average_daily_balance" not in report["metrics_differing"]
    assert "adb_ok" in report["metrics_differing"]   # 1 is not True


def test_whitespace_only_description_difference_is_counted_separately():
    visual = _payload()
    visual["statement"]["transactions"][0]["description"] = "FABRICATED  FEE"
    account = compare(visual, _payload())[0]["per_account"][0]["transactions"]
    assert account["descriptions_byte_equal"] == 1 and account["descriptions_whitespace_equal"] == 2
