"""The shape discipline every taught payload reader shares (L1-S3, L1-C16).

The assertion is the thing under test, so every clause of it is exercised from
both sides: the shape it admits, and the shape it refuses.
"""
from __future__ import annotations

import pytest

from analysis.payload_shape import (
    ACCOUNT_SHAPE,
    DOCUMENT_SHAPE,
    PayloadShapeError,
    assert_payload_shape,
    is_document_payload,
    payload_account_count,
    payload_accounts,
    payload_document_block,
    refuse_document_payload,
)
from tests.l1s3_payloads import account_payload, document_payload, shim_payload


def test_the_error_is_a_value_error():
    """The design's word. Every caller narrowing on `ValueError` keeps working."""
    assert issubclass(PayloadShapeError, ValueError)


def test_todays_payload_is_the_account_shape():
    assert assert_payload_shape(account_payload(), surface="probe") == ACCOUNT_SHAPE
    assert not is_document_payload(account_payload())


def test_the_multi_account_payload_is_the_document_shape():
    payload = document_payload()
    assert assert_payload_shape(payload, surface="probe") == DOCUMENT_SHAPE
    assert is_document_payload(payload)


def test_the_option_d_shim_is_refused():
    """`accounts` beside `statement` is one account wearing the document's name."""
    with pytest.raises(PayloadShapeError, match="payload_carries_both_shapes"):
        assert_payload_shape(shim_payload(), surface="probe")


def test_a_payload_carrying_neither_shape_is_refused():
    with pytest.raises(PayloadShapeError, match="payload_carries_no_shape"):
        assert_payload_shape({"metrics": {}}, surface="probe")


def test_a_non_mapping_is_refused():
    with pytest.raises(PayloadShapeError, match="payload_not_a_mapping"):
        assert_payload_shape([], surface="probe")


def test_the_account_shape_yields_exactly_itself():
    """The property that makes a taught reader dark: one iteration, same mapping."""
    payload = account_payload()
    accounts = payload_accounts(payload, surface="probe")
    assert len(accounts) == 1
    assert accounts[0] is payload
    assert payload_account_count(payload, surface="probe") == 1
    assert payload_document_block(payload, surface="probe") == {}


def test_the_document_shape_yields_its_accounts_in_printed_order():
    payload = document_payload(outcomes=("validated", "review", "withheld"))
    accounts = payload_accounts(payload, surface="probe")
    assert [account["statement"]["account_number"] for account in accounts] == [
        "000000000000", "000000000001", "000000000002",
    ]
    assert payload_account_count(payload, surface="probe") == 3


def test_a_document_with_no_account_is_refused():
    payload = document_payload()
    payload["accounts"] = []
    with pytest.raises(PayloadShapeError, match="document_publishes_no_account"):
        payload_accounts(payload, surface="probe")


def test_an_account_list_that_is_not_a_list_is_refused():
    payload = document_payload()
    payload["accounts"] = {"first": account_payload()}
    with pytest.raises(PayloadShapeError, match="accounts_not_a_list"):
        payload_accounts(payload, surface="probe")


def test_an_account_that_is_not_an_account_payload_is_refused():
    payload = document_payload()
    payload["accounts"][1] = {"metrics": {}}
    with pytest.raises(PayloadShapeError, match="account_is_not_an_account_payload"):
        payload_accounts(payload, surface="probe")


def test_a_declared_count_that_contradicts_the_list_is_refused():
    """A block that says three over a list of two is a publisher defect, and
    trusting either half of a contradiction is picking one at random."""
    payload = document_payload(account_count=3)
    with pytest.raises(PayloadShapeError, match="account_count_contradicts_the_list"):
        payload_account_count(payload, surface="probe")


def test_the_document_block_must_be_present_on_the_document_shape():
    payload = document_payload()
    del payload["document"]
    with pytest.raises(PayloadShapeError, match="document_block_absent"):
        payload_document_block(payload, surface="probe")


def test_the_account_scope_refusal_is_silent_on_every_mapping_without_accounts():
    """The darkness property, stated as a test.

    Among MAPPINGS, `refuse_document_payload` must key on `accounts` and on
    nothing else, so a reader that gains the line answers every payload the
    tree can publish today exactly as it did before. `None` is admitted too —
    a document that produced no payload is a thing every outcome reader
    already handles.
    """
    for benign in ({}, {"statement": {}}, {"metrics": {}}, None):
        refuse_document_payload(benign, surface="probe")
    with pytest.raises(PayloadShapeError, match="reader_is_account_scope"):
        refuse_document_payload(document_payload(), surface="probe")


@pytest.mark.parametrize("not_a_payload", [[], "text", 3, 3.5, object(), set()])
def test_the_account_scope_refusal_is_LOUD_on_a_non_mapping(not_a_payload):
    """L1-S3 review, MINOR-6 and the mechanism behind BLOCK-1.

    A guard whose whole job is to refuse a shape it was not taught may not be
    the quietest thing in the call stack. It used to return here, and the
    caller then failed several frames down inside whatever it did next.
    """
    with pytest.raises(TypeError, match="payload_is_not_a_payload"):
        refuse_document_payload(not_a_payload, surface="probe")


def test_the_predicate_is_a_question_and_does_not_raise():
    """`is_document_payload` stays total: a question that raises cannot be asked.
    What must be loud is the GUARD, and the test above pins that."""
    for anything in ([], "text", 3, object(), None, {}, {"accounts": []}):
        assert isinstance(is_document_payload(anything), bool)


def test_the_surface_name_reaches_the_message():
    """Constants of ours, never a value out of a document."""
    with pytest.raises(PayloadShapeError, match="named_surface"):
        refuse_document_payload(document_payload(), surface="named_surface")
