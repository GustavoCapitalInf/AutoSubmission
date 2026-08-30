"""CONSTRUCTED payloads for the L1-S3 surface tests. Never a real document.

Every value here is invented and obviously so: the bank is a placeholder, the
account numbers are runs of zeroes, the money is repeated digits and the dates
are the first days of a year no statement in the archive covers. Nothing in
this module is read from, derived from, or shaped after any statement — the
document shape has never been published, so there is nothing real to copy.

The builders produce the two shapes `analysis/serialization.py` publishes:

* :func:`account_payload` — today's shape, a top-level ``statement``;
* :func:`document_payload` — the multi-account shape, ``document`` +
  ``accounts`` and no top-level ``statement``.

`outcome` selects which rung of the ladder `telemetry/record.py` puts the
account on, so a test can build a document whose accounts disagree and assert
the fold lands on the WEAKEST of them.
"""
from __future__ import annotations

from copy import deepcopy

#: A placeholder institution. Not an issuer this repository has a parser for.
SYNTHETIC_BANK = "SYNTHETIC TEST BANK"

#: The ladder rungs an account fixture can be built on.
ACCOUNT_OUTCOMES = ("validated", "review", "withheld")


def _classification(index: int, *, posted: bool = True) -> dict:
    return {
        "source_location": f"transaction:{index}",
        "is_posted": posted,
        "revenue_classification": "verified_revenue",
        "revenue_initial_classification": "verified_revenue",
        "revenue_review_required": False,
        "revenue_review_status": None,
        "revenue_review_note": None,
        "revenue_reviewed_at": None,
        "review_required": False,
    }


def account_payload(index: int = 0, *, outcome: str = "validated") -> dict:
    """One ACCOUNT's payload — today's shape, with invented values.

    `index` only varies the invented account number and the amounts, so two
    accounts of one constructed document publish DIFFERENT content and the
    publisher's duplicate refusal is not what a test trips over by accident.
    """
    if outcome not in ACCOUNT_OUTCOMES:
        raise ValueError(f"unknown fixture outcome: {outcome!r}")
    amount = 111.11 * (index + 1)
    payload = {
        "statement": {
            "bank": SYNTHETIC_BANK,
            "account_number": f"{index:012d}",
            "currency": "USD",
            "period_start": "2000-01-01",
            "period_end": "2000-01-31",
            "beginning_balance": 1000.0 + index,
            "ending_balance": 1000.0 + index + amount,
            "stated_credit_count": 1,
            "transactions": [
                {
                    "date": "2000-01-02",
                    "description": f"SYNTHETIC CREDIT {index}",
                    "amount": amount,
                    "balance": 1000.0 + index + amount,
                    "direction": "credit",
                    "classification": _classification(0),
                },
            ],
        },
        "classifications": [_classification(0)],
        "reconciliation": {
            "ok": True,
            "summary_ok": True,
            "issues": [],
            "credit_coverage": 1.0,
            "debit_coverage": 1.0,
        },
        "metrics": {
            "average_daily_balance": 1000.0 + index,
            "adb_ok": True,
            "effective_total_deposits": amount,
            "effective_total_withdrawals": 0.0,
            "cash_flow": amount,
            "max_balance": 1000.0 + index + amount,
            "min_balance": 1000.0 + index,
            "adb": {
                "ok": True,
                "period_start": "2000-01-01",
                "period_end": "2000-01-31",
                "calendar_day_count": 31,
                "opening_balance": 1000.0 + index,
                "opening_balance_source": "printed",
                "closing_balance": 1000.0 + index + amount,
                "computed_closing_balance": 1000.0 + index + amount,
                "total_credits": amount,
                "total_debits": 0.0,
                "reconciled": True,
                "daily_balance_sum": (1000.0 + index) * 31,
                "daily_balances": [
                    {"date": "2000-01-01", "ending_balance": 1000.0 + index},
                ],
                "validations": {"period_covered": True},
                "warnings": [],
                "underwriting_adb": 1000.0 + index,
                "underwriting_adb_basis": "calendar_day_printed_period",
                "underwriting_adb_policy": "canonical_v1",
            },
        },
        "quality": {
            "level": "reliable",
            "transaction_detail_reliable": True,
            "summary_totals_reliable": True,
            "aggregate_rows": 0,
            "corporate_use": "approved",
            "notes": [],
        },
        "integrity": {
            "flags": [],
            "notes": [],
            "risk_level": "clear",
            "possible_document_issue": False,
        },
        "detection": {
            "known_funders": [],
            "potential_lenders": [],
            "insurance_providers": [],
            "recurring_debits": [],
            "lender_evidence": [],
            "potential_lender_evidence": [],
            "insurance_evidence": [],
            "verified_revenue_evidence": [],
            "unverified_deposit_evidence": [],
            "non_revenue_evidence": [],
            "true_revenue_evidence": [],
            "potential_revenue_evidence": [],
            "manual_review": [],
        },
        "model_used": "deterministic",
        "escalated": False,
    }
    if outcome == "withheld":
        # `classify_outcome`'s first rung: no authoritative ADB.
        payload["metrics"]["average_daily_balance"] = None
    elif outcome == "review":
        payload["integrity"]["flags"] = ["running_balance_breaks"]
        payload["integrity"]["risk_level"] = "review"
    return payload


def document_payload(
    *,
    outcomes: tuple[str, ...] = ("validated", "validated"),
    omitted_sections: tuple[dict, ...] = (),
    boundary_mechanism: str | None = "rollup-oracle",
    period: tuple[str, str] | None = ("2000-01-01", "2000-01-31"),
    account_count: int | None = None,
) -> dict:
    """The DOCUMENT shape, built the way `document_report_to_dict` builds it.

    Constructed rather than produced, because production cannot produce it:
    `analyze_document` publishes exactly one account on every document at this
    tree, so a fixture is the only way any of these branches can be reached at
    all — which is the same reason the branches are dark.
    """
    accounts = [
        account_payload(index, outcome=outcome)
        for index, outcome in enumerate(outcomes)
    ]
    return {
        "document": {
            "period_start": period[0] if period else None,
            "period_end": period[1] if period else None,
            "boundary_mechanism": boundary_mechanism,
            "account_count": len(accounts) if account_count is None else account_count,
            "rollup": None,
            "omitted_sections": [deepcopy(item) for item in omitted_sections],
        },
        "accounts": accounts,
    }


def shim_payload() -> dict:
    """The Option-D shim the design refuses: the document shape with the FIRST
    account promoted back under ``statement``.

    It exists so the refusal can be TESTED rather than described. No publisher
    builds it and none may.
    """
    payload = document_payload()
    payload["statement"] = deepcopy(payload["accounts"][0]["statement"])
    return payload


def omission(reason: str = "printed_dormancy_declaration") -> dict:
    """One published GAP, as `document_report_to_dict` serialises it."""
    return {"label": "SYNTHETIC SECTION B", "reason": reason, "posting_count": 0}
