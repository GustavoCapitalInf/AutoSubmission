"""Audit 2026-10-13, REC-5: R-d's counterparts are found through a (date, cents) index, not by testing every pair.

`identify_internal_transfers` built each posting's counterpart list by testing every other posting of the document:
quadratic in a multi-account document's postings. The postings are now listed by (date, whole cents of the magnitude)
and a posting's candidates are its own bucket and the two neighbouring cents (a superset of clause 1's < 0.005
tolerance), sorted into posting order, then tested by `admissible()` VERBATIM, which stays the authority. The index
is on date and cents only, never on the account, so clause 1's account test is still the one that refuses a
same-account counterpart (the L1-S4 mutation table's Rd1 mutant keeps being killed). A posting whose amount is not
finite, or too large for a cent bucket to be exact, keeps the brute-force comparison, and is a candidate of every
posting: nothing can differ from the pairwise test.

`_reference` below is the function as it stood (the all-pairs comprehension); seeded random fabricated ledgers
(ambiguity, one-cent near-misses, float-awkward amounts, NaN, infinities, huge amounts, same-account and same-sign
collisions) must give identical transfers and notes.
"""
from __future__ import annotations

import math
import random
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from analysis import pipeline
from analysis.pipeline import AMBIGUOUS_INTERNAL_TRANSFER, InternalTransfer, identify_internal_transfers
from analysis.descriptor.rails import prints_internal_transfer_designation

INTERNAL_CREDIT = "Deposit Transfer From Savings"
INTERNAL_DEBIT = "Withdrawal Home Banking Transfer To Share"
NOTHING_PRINTED = "Deposit Kiosk SAMPLE"


def _reference(accounts):
    """identify_internal_transfers before audit 2026-10-13 REC-5, verbatim in behaviour (every pair tested)."""
    if len(accounts) < 2:
        return [], []
    postings = [
        (account_index, posting_index, txn.date, round(txn.amount, 2), txn.description)
        for account_index, report in enumerate(accounts)
        for posting_index, txn in enumerate(report.statement.transactions)
    ]

    def admissible(left, right) -> bool:
        return (
            left[0] != right[0]
            and left[2] == right[2]
            and abs(abs(left[3]) - abs(right[3])) < 0.005
            and left[3] * right[3] < 0
        )

    counterparts = {
        index: [other for other, right in enumerate(postings) if other != index and admissible(left, right)]
        for index, left in enumerate(postings)
    }
    ambiguous = any(len(found) > 1 for found in counterparts.values())
    notes = [AMBIGUOUS_INTERNAL_TRANSFER] if ambiguous else []
    if ambiguous:
        return [], notes
    transfers = []
    paired: set[int] = set()
    for index, found in counterparts.items():
        if len(found) != 1 or index in paired:
            continue
        other = found[0]
        left, right = postings[index], postings[other]
        designations = (prints_internal_transfer_designation(left[4]), prints_internal_transfer_designation(right[4]))
        if not any(designations):
            continue
        credit, debit = (left, right) if left[3] > 0 else (right, left)
        credit_designated = prints_internal_transfer_designation(credit[4])
        debit_designated = prints_internal_transfer_designation(debit[4])
        basis = (
            "printed_internal_transfer_designation_on_both_legs"
            if credit_designated and debit_designated
            else "printed_internal_transfer_designation_on_the_credit_leg"
            if credit_designated
            else "printed_internal_transfer_designation_on_the_debit_leg"
        )
        paired.update({index, other})
        transfers.append(InternalTransfer(a=(left[0], left[1]), b=(right[0], right[1]), basis=basis))
    return transfers, notes


def _account(postings):
    return SimpleNamespace(statement=SimpleNamespace(transactions=[
        SimpleNamespace(date=date, amount=amount, description=text) for date, amount, text in postings
    ]))


_AMOUNTS = (250.0, 250.01, 249.99, 0.1 + 0.2, 0.3, 1.005, 2.675, 1e9 + 0.01, 1e9, 99.995, 100, 1e13 + 0.01, 1e15,
            1e16, 12345678901234.5)


def _ledgers(seed: int):
    chooser = random.Random(seed)
    accounts = []
    for _account_number in range(chooser.randint(2, 4)):
        postings = []
        for _row in range(chooser.randint(0, 25)):
            roll = chooser.random()
            if roll < 0.02:
                amount = math.nan
            elif roll < 0.04:
                amount = math.inf * chooser.choice((1, -1))
            else:
                amount = chooser.choice(_AMOUNTS) * chooser.choice((1, -1))
            postings.append((
                f"2054-04-0{chooser.randint(1, 3)}" if chooser.random() > 0.03 else "",
                amount,
                chooser.choice((INTERNAL_CREDIT, INTERNAL_DEBIT, NOTHING_PRINTED, "Deposit ACH VENMO")),
            ))
        accounts.append(_account(postings))
    return accounts


@pytest.mark.parametrize("seed", range(400))
def test_the_index_finds_the_same_transfers_and_notes(seed):
    accounts = _ledgers(seed)
    assert identify_internal_transfers(accounts) == _reference(accounts)


def test_the_random_ledgers_reach_every_outcome():
    """The parity above is not vacuous: some ledgers pair, some are refused as ambiguous, some pair nothing."""
    outcomes = [_reference(_ledgers(seed)) for seed in range(400)]
    assert sum(bool(transfers) for transfers, _notes in outcomes) >= 20
    assert sum(bool(notes) for _transfers, notes in outcomes) >= 20
    assert sum(not transfers and not notes for transfers, notes in outcomes) >= 20


@pytest.mark.parametrize("left, right", [
    (250.0, -250.004),    # inside the tolerance across a cent's rounding: one bucket
    (250.0, -250.01),     # one cent apart: the neighbouring bucket, refused by admissible()
    (0.1 + 0.2, -0.3),    # float-awkward
    (1.005, -1.005),
    (2.675, -2.67),
    (1e9 + 0.01, -1e9),
    (1e16, -1e16),        # past the exact cent buckets: the brute-force path
    (math.nan, -math.nan),
    (math.inf, -math.inf),
])
def test_edge_amounts_pair_as_the_pairwise_test(left, right):
    accounts = [
        _account([("2054-04-02", left, INTERNAL_CREDIT)]),
        _account([("2054-04-02", right, INTERNAL_DEBIT)]),
    ]
    assert identify_internal_transfers(accounts) == _reference(accounts)


def test_the_admissibility_test_stays_the_authority():
    """The L1-S4 mutation table rewrites these lines of admissible() and the ambiguity rule; each must appear once."""
    source = Path(pipeline.__file__).read_text(encoding="utf-8")
    for anchor in (
        "            left[0] != right[0]",
        "            and left[3] * right[3] < 0",
        "    ambiguous = any(len(found) > 1 for found in counterparts.values())",
        "        if not any(designations):",
    ):
        assert source.count(anchor) == 1, anchor


def test_six_thousand_postings_pair_without_the_quadratic_scan():
    """REC-5: the all-pairs scan of 36 million pairs takes seconds at this size; the index takes tens of milliseconds.
    The bound is loose on purpose (a loaded machine), and still far below the quadratic cost."""
    chooser = random.Random(20261013)
    accounts = []
    for _account_number in range(3):
        postings = [
            (f"2054-04-{chooser.randint(1, 28):02d}", round(chooser.uniform(1, 5000), 2) * chooser.choice((1, -1)),
             chooser.choice((INTERNAL_CREDIT, NOTHING_PRINTED)))
            for _row in range(2000)
        ]
        accounts.append(_account(postings))
    started = time.perf_counter()
    transfers, notes = identify_internal_transfers(accounts)
    elapsed = time.perf_counter() - started
    assert elapsed < 0.75, elapsed
    assert isinstance(transfers, list) and isinstance(notes, list)
