"""Audit 2026-10-13, F3: pass 4's reversal pairing visits only a credit's equal debits, not every row.

`_reversal_pairs` walked every row of the statement for every posted credit only to keep the posted, non-duplicate
debits of the same rounded amount: credits x rows. The debits are now listed once by their rounded amount, in row
order, so a credit visits exactly the candidates the scan kept, in the same order: the pairs, the marker cache
(`marked`, which `widened` reads) and the calls to `refuse` are the same. The matched-debit check stays inside the
loop, because the debits a credit takes change as the loop goes.

`_reference_reversal_pairs` below is the double loop as it stood, kept as the reference: seeded random fabricated
statements (colliding amounts, int, NaN, infinities, signed zeros, values on rounding boundaries, unposted rows,
duplicates, missing dates, marker words, seeded pairs, a refusing closure) must give the same pairs, the same marker
cache in the same insertion order and the same sequence of refuse calls, on both sides of pass 4.
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict

import pytest

from analysis import transaction_classifier as tc
from analysis import dates
from analysis.transaction_classifier import TransactionClassification


def _reference_reversal_pairs(records, duplicate_indexes, markers, marked=None, *, credit_markers=(), seeded=(),
                              refuse=None):
    """tc._reversal_pairs before audit 2026-10-13 F3, verbatim in behaviour (the scan of every row per credit)."""
    marked = {} if marked is None else marked

    def has_marker(index):
        if index not in marked:
            text = records[index].normalized_description
            marked[index] = tc._matches_any(text, markers) or (
                records[index].amount > 0 and tc._credit_pair_marker(text, credit_markers)
            )
        return marked[index]

    pairs = list(seeded)
    matched_debit_indexes = {debit_index for _, debit_index in seeded}
    seeded_credits = {credit_index for credit_index, _ in seeded}
    for credit_index, credit in enumerate(records):
        if (
            credit_index in duplicate_indexes
            or credit_index in seeded_credits
            or credit.amount <= 0
            or not credit.is_posted
        ):
            continue
        credit_has_marker = has_marker(credit_index)
        candidates = []
        credit_date = dates.parse_date(credit.date)
        for debit_index, debit in enumerate(records):
            if (
                debit_index in duplicate_indexes
                or debit_index in matched_debit_indexes
                or debit.amount >= 0
                or not debit.is_posted
                or round(abs(debit.amount), 2) != round(credit.amount, 2)
            ):
                continue
            if not credit_has_marker and not has_marker(debit_index):
                continue
            if refuse is not None and refuse(credit_index, debit_index):
                continue
            debit_date = dates.parse_date(debit.date)
            day_gap = (
                abs((credit_date - debit_date).days)
                if credit_date is not None and debit_date is not None
                else 0
            )
            if day_gap > 14 or not tc._descriptions_share_pair_context(
                credit.normalized_description,
                debit.normalized_description,
            ):
                continue
            candidates.append((day_gap, debit_index))
        if not candidates:
            continue
        _, debit_index = min(candidates, key=lambda item: (item[0], abs(item[1] - credit_index), item[1]))
        matched_debit_indexes.add(debit_index)
        pairs.append((credit_index, debit_index))
    return sorted(pairs)


_WORDS = (
    "ACH", "CHECK", "WIRE", "E TRANSFER", "CONTOSO", "FABRIKAM", "NORTHWIND", "SAMPLE", "PAYMENT", "DEPOSIT",
    "REVERSAL", "RETURNED ITEM", "RETURN", "REFUND", "CNCL", "NSF", "VOID", "CHARGEBACK", "BANK CORRECTION",
    "RET DEP ITEM", "PURCHASE RET", "CANCELLED TRANSFER", "REIMBURSEMENT", "ERROR CORRECTION", "REMBOURSEMENT",
)
_AMOUNTS = (10.0, 25.5, 100.0, 1.005, 2.675, 0.1 + 0.2, 0.3, 1e9 + 0.01, 50, 99.995, 99.99)


def _record(chooser: random.Random, index: int) -> TransactionClassification:
    roll = chooser.random()
    if roll < 0.02:
        amount = math.nan
    elif roll < 0.03:
        amount = math.inf * chooser.choice((1, -1))
    elif roll < 0.04:
        amount = chooser.choice((0.0, -0.0))
    else:
        amount = chooser.choice(_AMOUNTS) * chooser.choice((1, -1))
    words = " ".join(chooser.sample(_WORDS, chooser.randint(1, 4)))
    day = chooser.randint(1, 28)
    return TransactionClassification(
        original_description=words,
        normalized_description=words,
        classification="other",
        date="" if chooser.random() < 0.03 else f"2054-0{chooser.randint(1, 2)}-{day:02d}",
        amount=amount,
        is_posted=chooser.random() > 0.08,
        source_location=f"transaction:{index + 1}",
    )


def _statement(seed: int, rows: int):
    chooser = random.Random(seed)
    records = [_record(chooser, index) for index in range(rows)]
    duplicates = {index for index in range(rows) if chooser.random() < 0.05}
    seeded: list[tuple[int, int]] = []
    if rows > 4 and chooser.random() < 0.5:
        credit, debit = chooser.sample(range(rows), 2)
        seeded.append((credit, debit))
    return chooser, records, duplicates, seeded


def _calls(function, records, duplicates, markers, *, credit_markers=(), seeded=(), refuse_seed=None):
    marked: dict[int, bool] = {}
    refused: list[tuple[int, int]] = []
    refuse = None
    if refuse_seed is not None:
        def refuse(credit_index, debit_index):
            refused.append((credit_index, debit_index))
            return (credit_index * 31 + debit_index * 17 + refuse_seed) % 5 == 0
    pairs = function(records, duplicates, markers, marked, credit_markers=credit_markers, seeded=seeded,
                     refuse=refuse)
    return pairs, list(marked.items()), refused


@pytest.mark.parametrize("seed", range(150))
def test_the_index_pairs_as_the_scan_of_every_row(seed):
    _chooser, records, duplicates, seeded = _statement(seed, rows=seed % 60 + 1)
    for markers, credit_markers, seeds, refuse_seed in (
        (tc._PAIR_MARKER_PATTERNS, tc._CREDIT_PAIR_MARKER_PATTERNS, seeded, None),
        (tc._LENDER_PAIR_MARKER_PATTERNS, (), (), seed),
        (tc._LENDER_PAIR_MARKER_PATTERNS, (), (), None),
    ):
        expected = _calls(_reference_reversal_pairs, records, duplicates, markers,
                          credit_markers=credit_markers, seeded=seeds, refuse_seed=refuse_seed)
        found = _calls(tc._reversal_pairs, records, duplicates, markers,
                       credit_markers=credit_markers, seeded=seeds, refuse_seed=refuse_seed)
        assert found == expected


@pytest.mark.parametrize("seed", range(40))
def test_pass_four_writes_the_same_records(monkeypatch, seed):
    _chooser, records, duplicates, _seeded = _statement(1000 + seed, rows=40 + seed)
    indexed = tc._apply_reversal_pair_context(records, duplicates)
    monkeypatch.setattr(tc, "_reversal_pairs", _reference_reversal_pairs)
    scanned = tc._apply_reversal_pair_context(records, duplicates)
    assert [asdict(record) for record in indexed] == [asdict(record) for record in scanned]


def test_the_differential_harness_catches_a_wrong_index():
    """A version that also lists unposted debits pairs differently on these statements: the harness is not blind."""
    def unposted_too(records, duplicate_indexes, markers, marked=None, **options):
        widened = [
            record if record.is_posted or record.amount >= 0 else
            TransactionClassification(**{**asdict(record), "is_posted": True})
            for record in records
        ]
        return _reference_reversal_pairs(widened, duplicate_indexes, markers, marked, **options)

    moved = 0
    for seed in range(150):
        _chooser, records, duplicates, _seeded = _statement(seed, rows=seed % 60 + 1)
        moved += _calls(unposted_too, records, duplicates, tc._LENDER_PAIR_MARKER_PATTERNS) != _calls(
            tc._reversal_pairs, records, duplicates, tc._LENDER_PAIR_MARKER_PATTERNS)
    assert moved > 0


class _CountedRows(list):
    """A statement's records that count how often the whole statement is walked."""

    walks = 0

    def __iter__(self):
        type(self).walks += 1
        return super().__iter__()


def test_a_credit_no_longer_walks_every_row():
    """F3: the statement is walked to list the debits and to visit the credits, not once more per credit."""
    _chooser, records, _duplicates, _seeded = _statement(7, rows=200)
    rows = _CountedRows(records)
    credits = sum(1 for record in records if record.amount > 0 and record.is_posted)
    assert credits > 50
    _CountedRows.walks = 0

    tc._reversal_pairs(rows, set(), tc._PAIR_MARKER_PATTERNS)

    assert _CountedRows.walks <= 2
