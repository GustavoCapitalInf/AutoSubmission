"""Every remaining payload reader, taught the document shape (L1-S3).

One test module for the readers that are not the outcome function
(`tests/test_document_outcome.py` owns that one): revenue, the exports, the
package, the web routes, the benchmark, the gate's verdict and the two
forensic audits.

Each reader is asked the same two questions:

* does it still answer today's payload exactly as it did — the property that
  makes this whole stage dark; and
* handed the document shape, does it render PER ACCOUNT or REFUSE LOUDLY —
  never publish nothing quietly, never index `statement` into a `KeyError`.

Every payload is CONSTRUCTED. Nothing here reads a document.
"""
from __future__ import annotations

import copy

import pytest

from analysis.payload_shape import PayloadShapeError
from analysis.revenue import rebuild_serialized_revenue_views
from tests.l1s3_payloads import (
    SYNTHETIC_CREDIT,
    account_payload,
    document_payload,
    shim_payload,
)


# --- analysis/revenue.py -----------------------------------------------------


def test_revenue_views_are_rebuilt_per_account():
    payload = document_payload()
    rebuild_serialized_revenue_views(payload)
    for index, account in enumerate(payload["accounts"]):
        assert account["metrics"]["total_posted_credit_count"] == 1
        assert account["metrics"]["verified_revenue_total"] == round(
            SYNTHETIC_CREDIT * (index + 1), 2)
    # No document-level revenue block: revenue is a property of a LEDGER and
    # the document has none of its own.
    assert set(payload) == {"document", "accounts"}
    assert "metrics" not in payload["document"]


def test_revenue_views_on_one_account_are_unchanged():
    payload = account_payload()
    before = copy.deepcopy(payload)
    rebuild_serialized_revenue_views(payload)
    rebuild_serialized_revenue_views(before)
    assert payload == before


def test_revenue_refuses_a_payload_carrying_neither_shape():
    """The head used to `setdefault("statement", {})` and rebuild every view
    over an empty ledger: totals of 0.00 and `revenue_reconciles` true because
    nothing failed to reconcile."""
    with pytest.raises(PayloadShapeError, match="payload_carries_no_shape"):
        rebuild_serialized_revenue_views({"metrics": {}})


def test_revenue_refuses_the_option_d_shim():
    with pytest.raises(PayloadShapeError, match="payload_carries_both_shapes"):
        rebuild_serialized_revenue_views(shim_payload())


def test_revenue_never_averages_two_accounts():
    """Two accounts, two ledgers, two answers — never one figure over both."""
    payload = document_payload()
    rebuild_serialized_revenue_views(payload)
    totals = [account["metrics"]["verified_revenue_total"]
              for account in payload["accounts"]]
    assert totals == [SYNTHETIC_CREDIT, SYNTHETIC_CREDIT * 2]
    assert len(set(totals)) == 2
