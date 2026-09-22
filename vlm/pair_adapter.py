"""Stage E: reviewed source evidence into the existing analysis pipeline.

The Markdown bridge is permitted only when a deterministic reader reproduces
the complete reviewed Statement. Otherwise the generic source adapter calls
the same account-report implementation. Neither route reconstructs a finished
payload, lets rejected Stage A rows back into the ledger, or changes metric
doctrines. Row/page provenance stays in the separate private audit evidence.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from math import isfinite
from typing import Callable

from pydantic import ValidationError

from analysis.config import Settings
from analysis.parser_registry import AmbiguousParserError, Dispatch, ParserCrashError, by_id
from analysis.pipeline import DocumentReport, analyze_document, analyze_statement
from analysis.reconcile import reconcile
from analysis.schema import Statement, StatementDailyBalance, Transaction
from ocr.document import StatementMarkdown


ADAPTER_VERSION = 3
REVIEW_POLICIES = ("hold", "admit_gated")
_NO_PARSER = "no deterministic parser matched this statement"
_EARNED_CURRENCY_SOURCES = frozenset({"institution_default"})


class VisualPairAdmissionError(RuntimeError):
    """A fixed, content-free refusal safe to surface at the worker boundary."""


def _refuse(reason: str) -> None:
    raise VisualPairAdmissionError(reason)


def _currency_provenance(raw: dict, proof: object) -> str:
    """Accept only the platform's consistent existing-parser audit contract.

    The enclosing receipt binds this platform-owned audit to the visual text
    and parser manifest. Model JSON cannot supply that audit. This structural
    check is not independent authentication of a caller-created receipt.
    Only the fixed institution rule is reusable for a missing denomination;
    raw Stage A text cannot establish printed, product or jurisdiction proof.
    """
    if not isinstance(proof, dict) or proof.get("reason") != "existing_parser_rule":
        return "model_extracted"
    source = proof.get("currency_source")
    parser_id = proof.get("parser_id")
    if (proof.get("status") != "resolved"
            or not isinstance(source, str) or source not in _EARNED_CURRENCY_SOURCES
            or proof.get("bridge_currency_source") != source
            or proof.get("currency") != raw.get("currency")
            or not isinstance(parser_id, str) or not parser_id.strip()
            or ("currency_source" in raw and raw["currency_source"] != source)):
        _refuse("visual pair currency resolution is invalid")
    try:
        by_id(parser_id)
    except KeyError:
        _refuse("visual pair currency resolution is invalid")
    return source


def _source_statement(raw: object, *, currency_resolution: object = None) -> Statement:
    """Refuse derived/unknown fields and absent evidence before Pydantic coercion."""
    if not isinstance(raw, dict):
        _refuse("visual pair source statement is missing")
    allowed = set(Statement.model_fields) - {"initialization_transaction_count"}
    # A caller may serialize the platform's default count, but the model may
    # never assert the special parser proof this field represents.
    if raw.get("initialization_transaction_count", 0) != 0:
        _refuse("visual pair source statement contains unsupported fields")
    if set(raw) - allowed - {"initialization_transaction_count"}:
        _refuse("visual pair source statement contains unsupported fields")
    for field in ("period_start", "period_end", "beginning_balance", "ending_balance", "currency"):
        if raw.get(field) is None:
            _refuse("visual pair source statement lacks required printed fields")
    rows = raw.get("transactions")
    snapshots = raw.get("stated_daily_balances", [])
    if not isinstance(rows, list) or not rows or not isinstance(snapshots, list):
        _refuse("visual pair source ledger is invalid")
    if any(not isinstance(row, dict) or set(row) - set(Transaction.model_fields) for row in rows):
        _refuse("visual pair source ledger contains unsupported fields")
    if any(not isinstance(row, dict) or set(row) - set(StatementDailyBalance.model_fields) for row in snapshots):
        _refuse("visual pair daily balances contain unsupported fields")
    # Currency provenance is assigned by the platform, never self-certified by
    # either model. A missing denomination was refused above instead of taking
    # the legacy Statement USD default.
    provenance = _currency_provenance(raw, currency_resolution)
    try:
        stmt = Statement.model_validate({**raw, "currency_source": provenance})
    except (ValidationError, TypeError, ValueError):
        _refuse("visual pair source statement is invalid")
    try:
        start = date.fromisoformat(stmt.period_start)
        end = date.fromisoformat(stmt.period_end)
        if start > end or len(stmt.currency) != 3 or not stmt.currency.isascii() or not stmt.currency.isupper():
            _refuse("visual pair period or currency is invalid")
        for row in stmt.transactions:
            if not start <= date.fromisoformat(row.date) <= end:
                _refuse("visual pair row lies outside its printed period")
            if row.direction not in {"credit", "debit"} or not row.description.strip():
                _refuse("visual pair source ledger is invalid")
        seen_balances: dict[str, float] = {}
        for row in stmt.stated_daily_balances:
            if not start <= date.fromisoformat(row.date) <= end:
                _refuse("visual pair daily balance lies outside its printed period")
            if row.date in seen_balances and seen_balances[row.date] != row.balance:
                _refuse("visual pair daily balances conflict")
            seen_balances[row.date] = row.balance
    except (TypeError, ValueError):
        _refuse("visual pair source dates are invalid")

    def finite(value: object) -> bool:
        if isinstance(value, dict):
            return all(finite(item) for item in value.values())
        if isinstance(value, list):
            return all(finite(item) for item in value)
        return not isinstance(value, float) or isfinite(value)

    if not finite(stmt.model_dump()):
        _refuse("visual pair source numbers are invalid")
    result = reconcile(stmt)
    if (not result.ok or result.summary_ok is False
            or result.stated_credit_count_matches is False
            or result.stated_debit_count_matches is False):
        _refuse("visual pair source statement did not reconcile")
    return stmt


def _same_sources(first: Statement, second: Statement) -> bool:
    # The currency value is evidence; its provenance class is a platform label.
    # Compare every other source field and every ordered row, including exact
    # descriptions, signs, printed columns, daily balances and optional totals.
    exclude = {"currency_source", "stated_average_balance"}
    return first.model_dump(exclude=exclude) == second.model_dump(exclude=exclude)


def _complete_report(document: DocumentReport) -> DocumentReport:
    # A reconciled transaction sum does not validate a contradictory printed
    # daily-balance table. The existing ADB validator is the authority for that
    # evidence, too; no fallback account is partially admitted with its ADB or
    # negative-day NSF figure silently withheld.
    if any(report.metrics.adb_ok is not True for report in document.accounts):
        _refuse("visual pair daily ledger did not validate")
    return document


def analyze_visual_pair(
    doc: StatementMarkdown,
    *,
    settings: Settings | None = None,
    on_dispatch: Callable[[Dispatch], None] | None = None,
    review_policy: str = "hold",
) -> DocumentReport:
    """Gate first; faithful bank-reader bridge, then generic source analysis.

    `hold` remains the default until the owner decides a publication policy.
    `admit_gated` supports explicitly configured synthetic/research wiring and
    a later authorised policy. The decision is evaluated on every analysis,
    including a cache hit; an extraction artifact cannot grant publication.
    """
    if review_policy not in REVIEW_POLICIES:
        _refuse("visual pair review policy is invalid")
    evidence = getattr(doc, "visual_pair", None)
    if not isinstance(evidence, dict) or evidence.get("version") != 1:
        _refuse("visual pair evidence is missing or unsupported")
    if evidence.get("account_count", 1) != 1 or evidence.get("accounts"):
        _refuse("visual pair multiple accounts require review")
    gate = evidence.get("gate")
    if not isinstance(gate, dict) or gate.get("admitted") is not True or gate.get("reasons") != []:
        _refuse("visual pair gate refused the document")
    confidence = evidence.get("confidence")
    counts = confidence.get("counts") if isinstance(confidence, dict) else None
    if (not isinstance(counts, dict) or counts.get("unresolved") != 0
            or confidence.get("gate_admitted") is not True):
        _refuse("visual pair review is incomplete")
    if (not doc.pages or len(doc.page_integrity) != len(doc.pages)
            or doc.has_truncated_pages):
        _refuse("visual pair page evidence is incomplete")
    statement = _source_statement(evidence.get("statement"),
                                  currency_resolution=evidence.get("currency_resolution"))
    if review_policy == "hold":
        _refuse("visual pair requires human review")

    markdown = doc.to_markdown()
    # 3.1a: use the established reader only if it returns precisely the gated
    # sources. A parser dropping a correction or reviving a rejected row cannot
    # win by reconciling: identity, rather than financial success, selects the
    # bridge. No hosted extraction is reachable in this deterministic call.
    try:
        bridged = analyze_document(
            markdown, settings=settings, parse_mode="deterministic",
            sheets=doc.pages, on_dispatch=on_dispatch,
        )
    except (AmbiguousParserError, ParserCrashError):
        _refuse("visual pair bank reader requires review")
    except RuntimeError as exc:
        if str(exc) != _NO_PARSER:
            raise
        bridged = None
    if bridged is not None:
        if len(bridged.accounts) != 1 or bridged.omissions:
            _refuse("visual pair multiple accounts require review")
        if _same_sources(bridged.accounts[0].statement, statement):
            report = replace(
                bridged.accounts[0], statement=statement,
                model_used=doc.model + "-bank-bridge", escalated=False,
            )
            return _complete_report(replace(bridged, accounts=[report]))

    # 3.1b: unmatched layouts and bank readers which cannot preserve the exact
    # reviewed sources share the ordinary deterministic report computation.
    return _complete_report(analyze_statement(
        statement, reconciliation=reconcile(statement), markdown=markdown, sheets=doc.pages,
        model_used=doc.model + "-generic", settings=settings,
    ))
