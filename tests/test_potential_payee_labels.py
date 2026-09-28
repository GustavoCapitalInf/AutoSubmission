"""5.3 (2026-09-27): the Potential Lenders tab lists each unnamed payee key on its own line, and D10 names an MCA
SERVICING payee with one fixed label. Fabricated descriptors; every amount is whole dollars."""
from __future__ import annotations

import json

import pytest

from analysis.detect import find_potential_lenders
from analysis.metrics import compute_metrics
from analysis.schema import Statement
from analysis.serialization import report_to_dict
from analysis.transaction_classifier import (
    UNIDENTIFIED_MCA_SERVICER,
    classify_statement_transactions,
    classify_transaction,
)
from tests.flag_group_fixtures import txn
from tests.webapp_js_harness import NODE, run_dashboard

WEEKLY = ("2054-01-05", "2054-01-12", "2054-01-19", "2054-01-26")
UNIDENTIFIED = "Unidentified lender obligation"


def _statement(*rows):
    return Statement(bank="Fabricated Bank", transactions=[txn(day, text, amount) for day, text, amount in rows])


def test_an_mca_servicing_payee_carries_the_fixed_d10_label():
    for printed in ("ACH DEBIT MCA SERVICING 0001", "ACH DEBIT MCA SERVICING LLC 0001",
                    "Corporate ACH Payment Mca Servicing"):
        record = classify_transaction(printed, -250.0)
        assert (record.classification, record.canonical_entity) == ("potential_lender", UNIDENTIFIED_MCA_SERVICER)
