"""One JSON contract for CLI, web, downloads, and package aggregation."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import TYPE_CHECKING

from .transaction_classifier.statement import classify_statement_transactions
from .classification.record import TransactionClassification
from .payload_shape import DOCUMENT_KEY, account_content_digest
from .revenue import rebuild_serialized_revenue_views
from . import zelle_view

if TYPE_CHECKING:
    from .pipeline import DocumentReport, Report
    from .schema import Transaction


def _transaction_dict(
    transaction: Transaction,
    classification: TransactionClassification,
) -> dict:
    return {
        **transaction.model_dump(),
        "classification": asdict(classification),
    }


def _funder_dict(match) -> dict:
    is_potential = match.classification == "potential_lender"
    potential_evidence = [
        evidence
        for evidence in match.evidence
        if evidence.contributes_to_potential_lender_totals
    ]
    debit_count = len(potential_evidence) if is_potential and potential_evidence else match.debit_count
    total_debited = (
        round(sum(abs(evidence.amount) for evidence in potential_evidence), 2)
        if is_potential and potential_evidence
        else match.total_debited
    )
    potential_exposure = match.potential_withholding_exposure
    if is_potential and match.eligible_deposit_denominator is not None:
        potential_exposure = (
            abs(total_debited) / match.eligible_deposit_denominator * 100
            if match.eligible_deposit_denominator > 0
            else None
        )
    return {
        "funder": match.funder,
        "matched_alias": match.matched_alias,
        "classification": match.classification,
        "debit_count": debit_count,
        "total_debited": total_debited,
        "potential_lender_debit_count": (
            debit_count if is_potential else 0
        ),
        "potential_lender_debit_total": (
            total_debited if is_potential else 0.0
        ),
        "eligible_deposit_denominator": match.eligible_deposit_denominator,
        "potential_withholding_exposure": potential_exposure,
        "potential_withholding_formula": match.potential_withholding_formula,
        "review_required": match.review_required,
        "status": match.status,
        # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): the funder's payments returned unpaid, never in
        # debit_count or total_debited (paid to lenders); their rows are among `transactions` and `evidence`.
        "returned_payment_count": match.returned_count,
        "returned_payment_total": match.returned_total,
        "transactions": [
            _transaction_dict(transaction, evidence)
            for transaction, evidence in zip(match.transactions, match.evidence)
        ],
        "evidence": [asdict(evidence) for evidence in match.evidence],
    }


def _insurance_dict(match) -> dict:
    return {
        "provider": match.provider,
        "matched_alias": match.matched_alias,
        "count": match.count,
        "total_debited": match.total_debited,
        "transactions": [
            _transaction_dict(transaction, evidence)
            for transaction, evidence in zip(match.transactions, match.evidence)
        ],
        "evidence": [asdict(evidence) for evidence in match.evidence],
    }


def _flagged_dict(match) -> dict:
    """Spec §6 (C5): one flagged position, exactly the contract's keys."""
    return {
        "group": match.group,
        "payee": match.payee,
        "matched_alias": match.matched_alias,
        "count": match.count,
        "total_debited": match.total_debited,
        "count_credited": match.count_credited,
        "total_credited": match.total_credited,
        "cadence": match.cadence,
        "avg_gap_days": match.avg_gap_days,
        "first_date": match.first_date,
        "last_date": match.last_date,
        "source_locations": list(match.source_locations),
        "review_required": match.review_required,
    }


def _recurring_dict(item) -> dict:
    return {
        "description_key": item.description_key,
        "amount": item.amount,
        "count": item.count,
        "cadence": item.cadence,
        "avg_gap_days": item.avg_gap_days,
        "transactions": [
            _transaction_dict(transaction, evidence)
            for transaction, evidence in zip(item.transactions, item.evidence)
        ],
        "evidence": [asdict(evidence) for evidence in item.evidence],
    }


def _metrics_dict(metrics) -> dict:
    """Serialize one public ADB value and fail closed on rejected ledgers."""
    data = asdict(metrics)
    adb = data.get("adb")
    validated = (
        data.get("adb_ok") is True
        and data.get("average_daily_balance") is not None
    )
    if not validated:
        data["average_daily_balance"] = None
        data["daily_balance_sum"] = None
    if isinstance(adb, dict):
        # `metrics.average_daily_balance` is the sole public ADB field. The
        # nested object carries validation evidence, not a second value. Both
        # the canonical name and its deprecated alias are removed so the
        # doctrine's one-user-facing-ADB rule cannot be broken by a rename.
        adb.pop("average_daily_balance", None)
        adb.pop("underwriting_adb", None)
        adb["ok"] = validated
        if not validated:
            # Candidate working remains available on the in-process result for
            # forensic review, but rejected numbers are never API/export data.
            adb["daily_balance_sum"] = None
            adb["daily_balances"] = []
            # An unvalidated ledger yields no valid figure on ANY basis, so the
            # internal alternates are nulled alongside the canonical value.
            # The basis and policy STAMPS remain: they describe the methodology
            # that was refused, which is exactly what an auditor needs to see.
            adb["underwriting_adb_alternates"] = {
                name: None for name in adb.get("underwriting_adb_alternates") or {}
            }
    return data


def report_to_dict(report: Report) -> dict:
    """One account's published payload: the stored (No) Zelle reading, rebuilt (`_account_payload`). The owner's
    amendment of 2026-10-06 to the underwriter's Q3 (true revenue spec §9.1; R2-OW17): an account whose counted (Yes)
    reading differs carries, after the rebuild, the lean edits that turn it into that reading (ZELLE_EDITS_KEY,
    analysis/zelle_view.py). A statement with no Zelle row publishes today's payload byte for byte."""
    payload = _account_payload(report)
    counted = getattr(report, "zelle_counted", None)
    if counted is not None:
        edits = zelle_view.reading_edits(payload, _account_payload(counted))
        if edits:
            payload[zelle_view.ZELLE_EDITS_KEY] = edits
    return payload


def _account_payload(report: Report) -> dict:
    """One Report's account payload in its own reading, its revenue views rebuilt (today's `report_to_dict` body)."""
    records = report.classifications or classify_statement_transactions(report.statement)
    if len(records) != len(report.statement.transactions):
        raise ValueError("classification count must equal transaction count")

    statement = report.statement.model_dump()
    # A printed ending balance remains reconciliation evidence, but it is not a
    # reportable metric when neither the detailed ledger nor the bank's own
    # summary identity supports it. The reconciliation object retains the source
    # value and computed value for forensic review.
    closing_balance_valid = (
        report.reconciliation.ok
        or report.reconciliation.summary_ok is True
    )
    if not closing_balance_valid:
        statement["ending_balance"] = None
    statement["transactions"] = [
        _transaction_dict(transaction, classification)
        for transaction, classification in zip(report.statement.transactions, records)
    ]
    detection = report.detection
    payload = {
        "statement": statement,
        "classifications": [asdict(record) for record in records],
        "reconciliation": asdict(report.reconciliation),
        "metrics": _metrics_dict(report.metrics),
        "detection": {
            "known_funders": [_funder_dict(match) for match in detection.known_funders],
            "potential_lenders": [_funder_dict(match) for match in detection.potential_lenders],
            "insurance_providers": [_insurance_dict(match) for match in detection.insurance_providers],
            "flagged_positions": [_flagged_dict(match) for match in detection.flagged_positions],
            "recurring_debits": [_recurring_dict(item) for item in detection.recurring_debits],
            "lender_evidence": [asdict(item) for item in detection.lender_evidence],
            "potential_lender_evidence": [
                asdict(item) for item in detection.potential_lender_evidence
            ],
            "insurance_evidence": [asdict(item) for item in detection.insurance_evidence],
            # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): the returned funder payments, the warning's items.
            "returned_funder_payments": [dict(item) for item in detection.returned_funder_payments],
            # The owner's request of 2026-10-06 (lender payment changes; R2-OW18).
            "lender_payment_changes": [dict(item) for item in detection.lender_payment_changes],
            # The owner's answer of 2026-10-07 to audit round 3's R3-79 (R3-B03): the lump-sum payoffs' lines, after
            # R2-OW18's list (which follows the returned payments).
            "lump_sum_payoffs": [dict(item) for item in detection.lump_sum_payoffs],
            "verified_revenue_evidence": [
                asdict(item) for item in detection.verified_revenue_evidence
            ],
            "unverified_deposit_evidence": [
                asdict(item) for item in detection.unverified_deposit_evidence
            ],
            "non_revenue_evidence": [
                asdict(item) for item in detection.non_revenue_evidence
            ],
            # 5.6 (§9.1): the counted and held credits; true_revenue_evidence is repointed to verified plus counted.
            "counted_flagged_evidence": [
                asdict(item) for item in detection.counted_flagged_evidence
            ],
            "excluded_pending_review_evidence": [
                asdict(item) for item in detection.excluded_pending_review_evidence
            ],
            "true_revenue_evidence": [
                asdict(item) for item in detection.true_revenue_evidence
            ],
            "potential_revenue_evidence": [
                asdict(item) for item in detection.unverified_deposit_evidence
            ],
            "manual_review": [asdict(item) for item in detection.manual_review],
        },
        "quality": asdict(report.quality),
        "integrity": asdict(report.integrity),
        "model_used": report.model_used,
        "escalated": report.escalated,
    }
    return rebuild_serialized_revenue_views(payload)


def _publishes_todays_payload(document: DocumentReport) -> bool:
    """RULE S — the exact condition under which the payload is today's payload.

    > A `DocumentReport` publishes exactly today's payload, with NO added key
    > of any kind, when it carries exactly ONE account. The `document` +
    > `accounts` shape requires MORE THAN ONE.

    **This clause was a four-way conjunction until the L1-S3 / L1-S2
    composition (closure-2), and the composed tree is what corrected it.** S1
    reasoned that each document-level fact is something the single-account
    payload has nowhere to put, so a document carrying one should take the
    document shape even with a single account. L1-S2 then began recording
    `omissions` on the 15 protected carriers — every one a SINGLE-ACCOUNT
    document that batch 8 validated — and at the composed tree those 15 flipped
    to the `document` + `accounts` shape at the production seams. Measured
    there: `python corpus_gate.py` died with
    `balance_forensic_audit.py::audit_source answers about one ACCOUNT and was
    handed a document carrying 1 of them`, and `pytest -m corpus` failed the
    gate-green and warm-rerun pins. The account-scope readers were behaving
    exactly as L1-S3 taught them; what was wrong was asking them to refuse a
    document they could answer.

    So the shape is decided by ACCOUNT COUNT alone, and the reason is what the
    shape is FOR: `accounts` is a list because one dict cannot hold two
    statements. A document with one account needs no list, and a reader whose
    refusal means *this holds several accounts and I can answer about only one*
    has nothing to refuse.

    **What this costs, stated rather than hidden.** A single-account document
    carrying a document-level fact — an omission, a roll-up, a boundary
    mechanism — publishes today's payload, and that fact is therefore in the
    OBJECT and not in the payload. That is the failure S1's conjunction was
    written to prevent, and it is now an accepted, NAMED gap rather than a
    silent one:

    * the fact remains on `DocumentReport`, which is where L1-S2's protected-carrier
      pins read it (through `analyze_document`, not through the payload);
    * the document/package surfaces L1-S3 built still publish it, and still only
      when served a multi-account payload — dark until S4, exactly as Q10 says;
    * **S4 owns closing it**: giving a single-account payload a `document` block
      is a payload-shape change, which needs `ANALYSIS_STAGE_VERSION` bumped in
      the same commit and a ceremony. A stage whose whole contract is ZERO
      MOVEMENT may not make that change, and making it here would move all 15.

    `tests/test_document_report.py::test_every_document_level_field_is_declared_against_rule_s`
    pins the field set against that gap, so a document-level field added later
    is a red test rather than a silent invisibility.
    """
    return len(document.accounts) == 1


def document_report_to_dict(document: DocumentReport) -> dict:
    """The document's JSON payload. RULE S: one account publishes today's.

    Two refusals stand in front of the document shape, and both are properties
    of the WRAPPER itself rather than of any reader:

    * a document object carrying NO account is not a document with nothing to
      say, it is a publisher defect — publishing it would put an empty
      container in front of every consumer, which each would answer about
      rather than refuse. It raises;
    * two accounts of ONE document that publish identical content are one
      account published twice. The refusal is not about tidiness: every
      cross-account arithmetic a package performs — a sum, a count, a
      days-weighted average — would count that money twice, and no reader
      downstream can tell the duplicate from a member with two accounts. It
      raises, and the check is by CONTENT rather than by any identity token the
      paper printed, because a duplicate is a duplicate whatever it is called.

    Neither can be reached from the RULE S path (one account has no pair), so
    neither costs the single-account document anything.
    """
    if not document.accounts:
        raise ValueError(
            "a document object with no account may not be published "
            "(document_publishes_no_account)"
        )
    if _publishes_todays_payload(document):
        published = report_to_dict(document.accounts[0])
        block = _document_block(document)
        if block is None:
            # Verbatim, and deliberately not "today's payload plus nothing":
            # the single-account path returns the very object today's seam
            # returns, so there is no assembly here that could reorder a flag,
            # drop a key or add one. This is the branch every document in the
            # archive but twenty-one takes.
            return published
        # THE GAP THE L1-S2 / L1-S3 COMPOSITION LEFT WITH AN OWNER, CLOSED HERE
        # (W3 §L1S3 closure-2: *"S4 owns closing it"*). A single-account
        # document that ESTABLISHED a document-level fact — a surfaced sibling
        # omission, a roll-up read as an oracle, a boundary mechanism — used to
        # publish today's payload and keep that fact on the object, where no
        # payload reader and no package could ever see it. Q10 rules that such
        # an omission is SURFACED beside the account rather than demoting it,
        # and a fact that reaches no surface is not surfaced.
        #
        # It is the `document` BLOCK and NOT the `accounts` list, and the
        # difference is the whole reason this is safe where the composition
        # defect was not. `analysis/payload_shape.py::is_document_payload` keys
        # on `accounts` alone, so this payload is still the ACCOUNT shape: every
        # account-scope reader answers it exactly as before, `statement` stays
        # at the top level where it has always been, and L1-C16 is untouched
        # (the assertion forbids `accounts` BESIDE `statement`, and there is no
        # account list here). What changes is one added top-level key on the
        # documents that have something to put in it.
        return {**published, DOCUMENT_KEY: block}

    accounts = [report_to_dict(account) for account in document.accounts]
    digests = [account_content_digest(account) for account in accounts]
    if len(set(digests)) != len(digests):
        raise ValueError(
            "two accounts of one document publish identical content; a "
            "duplicate section would be double-counted by every cross-account "
            "total (document_publishes_duplicate_account)"
        )
    # THERE IS DELIBERATELY NO TOP-LEVEL `statement`. A consumer that reads
    # `payload["statement"]` on a three-account document reads ONE account and
    # calls it the document — which is the defect this model exists to remove,
    # moved out of the parser and into the payload. Its absence is what makes
    # such a consumer stop.
    return {DOCUMENT_KEY: _document_block(document, always=True), "accounts": accounts}


def _document_block(document: DocumentReport, *, always: bool = False) -> dict | None:
    """The DOCUMENT's own printed facts, or `None` when it established none.

    Every field here is a fact about the DOCUMENT. None is filled from an
    account: a surface that needs one value per document is given
    `account_count` and an empty field, never a chosen account's value
    (L1-C18).

    `None` is the answer for a document that read no roll-up, recorded no
    boundary mechanism, resolved no document period, omitted nothing, paired no
    internal transfer and raised no document-scope note — which is every
    document in the archive but twenty-one, and is what keeps RULE S's
    byte-identical return the branch almost everything takes. `always` is the
    multi-account path, where the block is published even when empty because
    the shape itself declares the account count.

    The four clauses S1 wrote RULE S as a conjunction of are exactly the
    emptiness test here. What moved between S1 and L1-S4 is what a non-empty
    answer DOES: it used to switch the whole payload shape (and the L1-S2 /
    L1-S3 composition measured what that cost — fifteen protected payloads
    refused by the account-scope readers at the production seams), and now it
    adds one key beside today's payload.
    """
    facts = (
        document.document_period, document.rollup, document.omissions,
        document.boundary_mechanism, document.internal_transfers,
        document.integrity_notes, document.account_roster,
    )
    if not always and not any(facts):
        return None
    block = {
        "period_start": document.document_period[0] if document.document_period else None,
        "period_end": document.document_period[1] if document.document_period else None,
        "boundary_mechanism": document.boundary_mechanism,
        "account_count": len(document.accounts),
        "rollup": (
            {
                "caption_class": document.rollup.caption_class,
                "column_roles_printed": document.rollup.column_roles_printed,
                "rows": document.rollup.rows,
                "cross_account_total_printed": document.rollup.cross_account_total_printed,
            }
            if document.rollup is not None
            else None
        ),
        "omitted_sections": [
            {
                "label": omission.label,
                "reason": omission.reason,
                "posting_count": omission.posting_count,
            }
            for omission in document.omissions
        ],
        # R-d (L1-S4). Money this document prints in TWO of its own accounts'
        # ledgers, as INDEX PAIRS into `accounts` and into each account's own
        # published transaction list — never an amount, never a date, never a
        # description. Both legs stay in their ledgers; the package layer is
        # the only consumer, and it excludes an indexed posting from every
        # cross-account total so one movement is not counted as two deposits.
        "internal_transfers": [
            {
                "a": list(transfer.a),
                "b": list(transfer.b),
                "basis": transfer.basis,
            }
            for transfer in document.internal_transfers
        ],
        # The DOCUMENT-scope integrity notes. `integrity` inside each account
        # block is that ACCOUNT's and keeps every note it publishes today; this
        # is the scope that block has no room for, and today it carries exactly
        # one member — `ambiguous_internal_transfer`, which refuses the
        # package's aggregation of this document and nothing else (§3.3, Q2).
        "integrity_notes": list(document.integrity_notes),
    }
    if document.account_roster:
        # Every account the document prints, in printed order, and how each stands: `published` (its analysis is
        # `accounts[published_index]`, or the payload itself on a single published account), `idle` (an unchanged
        # printed balance), `held` (not verified, with its reason codes; no figure of it is published). Present
        # only when a reader judged the document account by account, so every other payload is unchanged.
        block["account_roster"] = [
            {
                "title": entry.title,
                "kind": entry.kind,
                "number_last4": entry.number_last4,
                "status": entry.status,
                "published_index": entry.published_index,
                "balance": entry.balance,
                "reasons": list(entry.reasons),
            }
            for entry in document.account_roster
        ]
    return block
