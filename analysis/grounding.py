"""Deterministic source grounding for generic statement extraction.

Reconciliation proves arithmetic consistency, not that a model copied the source.
This module independently checks that model-produced rows and statement amounts
are present on the OCR pages from which they claim to originate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .schema import Statement, StatementDailyBalance, Transaction


_PAGE_MARKER_RE = re.compile(r"--- Page\s+(\d+)(?:\s+\(empty\))?\s+---", re.IGNORECASE)
_WORD_RE = re.compile(r"[A-Z0-9]{3,}")
_BANK_WORD_RE = re.compile(r"[A-Z0-9]{2,}")
_GENERIC_WORDS = {
    "ACCOUNT",
    "AMOUNT",
    "BALANCE",
    "BANK",
    "CHECK",
    "CREDIT",
    "DEBIT",
    "DEPOSIT",
    "PAYMENT",
    "POSTED",
    "TRANSACTION",
    "TRANSFER",
    "WITHDRAWAL",
}


@dataclass(frozen=True)
class SourceValidation:
    method: str
    ok: bool
    score: float
    transaction_count: int
    grounded_transaction_count: int
    account_scope_valid: bool = True
    period_scope_valid: bool = True
    identity_scope_valid: bool = True
    zero_activity_supported: bool = False
    daily_balance_count: int = 0
    grounded_daily_balance_count: int = 0
    ungrounded_daily_balance_indexes: list[int] = field(default_factory=list)
    missing_daily_balance_page_indexes: list[int] = field(default_factory=list)
    ungrounded_transaction_indexes: list[int] = field(default_factory=list)
    missing_page_evidence_indexes: list[int] = field(default_factory=list)
    ungrounded_statement_fields: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def parser_validated_source() -> SourceValidation:
    return SourceValidation(
        method="deterministic_parser_contract",
        ok=True,
        score=1.0,
        transaction_count=0,
        grounded_transaction_count=0,
        notes=["source grounding is enforced by the matched deterministic parser and reconciliation"],
    )


def _pages(markdown: str) -> dict[int, str]:
    matches = list(_PAGE_MARKER_RE.finditer(markdown))
    if not matches:
        return {1: markdown}
    pages: dict[int, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        pages[int(match.group(1))] = markdown[match.end():end]
    return pages


def _money_text(value: float) -> str:
    amount = Decimal(str(abs(value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def _amount_spans(text: str, value: float) -> list[tuple[int, int]]:
    target = re.escape(_money_text(value))
    # Ignore thousands separators and common currency markers while retaining
    # numeric boundaries so 50.00 cannot ground itself inside 150.00.
    compact = text.replace(",", "")
    pattern = re.compile(rf"(?<![\d.]){target}(?!\d)")
    return [(match.start(), match.end()) for match in pattern.finditer(compact)]


def _description_tokens(description: str) -> set[str]:
    return {
        token
        for token in _WORD_RE.findall(description.upper())
        if token not in _GENERIC_WORDS and not token.isdigit()
    }


def _date_variants(value: str) -> set[str]:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return set()
    month_short = parsed.strftime("%b").upper()
    month_long = parsed.strftime("%B").upper()
    day = parsed.day
    month = parsed.month
    year = parsed.year
    return {
        value.upper(),
        f"{year}/{month:02d}/{day:02d}",
        f"{month:02d}/{day:02d}/{year}",
        f"{month:02d}/{day:02d}/{year % 100:02d}",
        f"{month:02d}/{day:02d}",
        f"{month}/{day}/{year}",
        f"{month}/{day}/{year % 100:02d}",
        f"{month}/{day}",
        f"{day:02d}/{month:02d}/{year}",
        f"{day:02d}/{month:02d}/{year % 100:02d}",
        f"{day:02d}/{month:02d}",
        f"{month:02d}-{day:02d}",
        f"{month}-{day}",
        f"{month_short} {day:02d}",
        f"{month_short} {day}",
        f"{month_short}. {day}",
        f"{month_long} {day:02d}",
        f"{month_long} {day}",
        f"{day:02d} {month_short}",
        f"{day} {month_short}",
        f"{day:02d}{month_short}",
        f"{month_short}{day:02d}",
    }


def _date_is_near(text: str, value: str) -> bool:
    upper = text.upper()
    return any(
        re.search(rf"(?<![A-Z0-9]){re.escape(variant)}(?![A-Z0-9])", upper)
        for variant in _date_variants(value)
    )


def _ground_transaction(
    transaction: Transaction,
    pages: dict[int, str],
    used_spans: set[tuple[int, int, int]],
) -> tuple[bool, bool]:
    if abs(transaction.amount) < 0.005:
        return False, transaction.source_page is None or transaction.source_page not in pages
    page_missing = transaction.source_page is None or transaction.source_page not in pages
    candidate_pages = (
        [(transaction.source_page, pages[transaction.source_page])]
        if not page_missing
        else list(pages.items())
    )
    description_tokens = _description_tokens(transaction.description)
    best: tuple[int, int, int, int] | None = None
    for page_number, page_text in candidate_pages:
        compact = page_text.replace(",", "")
        for start, end in _amount_spans(page_text, transaction.amount):
            key = (page_number, start, end)
            if key in used_spans:
                continue
            window = compact[max(0, start - 240):min(len(compact), end + 240)].upper()
            if not _date_is_near(window, transaction.date):
                continue
            overlap = sum(1 for token in description_tokens if token in window)
            required = 0 if not description_tokens else min(2, len(description_tokens))
            if overlap < required:
                continue
            if (
                transaction.running_balance is not None
                and not _amount_spans(window, transaction.running_balance)
            ):
                continue
            candidate = (overlap, page_number, start, end)
            if best is None or candidate > best:
                best = candidate
    if best is None:
        return False, page_missing
    _, page_number, start, end = best
    used_spans.add((page_number, start, end))
    return True, page_missing


_DAILY_BALANCE_LABELS = (
    "DAILY BALANCE",
    "BALANCE SUMMARY",
    "BALANCE BY DATE",
    "DAILY LEDGER",
)


def _ground_daily_balance(
    item: StatementDailyBalance,
    pages: dict[int, str],
    used_spans: set[tuple[int, int, int]],
) -> tuple[bool, bool]:
    page_missing = item.source_page is None or item.source_page not in pages
    candidate_pages = (
        [(item.source_page, pages[item.source_page])]
        if not page_missing
        else list(pages.items())
    )
    for page_number, page_text in candidate_pages:
        compact = page_text.replace(",", "")
        for start, end in _amount_spans(page_text, item.balance):
            key = (page_number, start, end)
            if key in used_spans:
                continue
            row_window = compact[max(0, start - 180):min(len(compact), end + 180)].upper()
            section_window = compact[max(0, start - 800):min(len(compact), end + 300)].upper()
            if not _date_is_near(row_window, item.date):
                continue
            if not any(label in section_window for label in _DAILY_BALANCE_LABELS):
                continue
            used_spans.add(key)
            return True, page_missing
    return False, page_missing


_STATEMENT_FIELD_LABELS: dict[str, tuple[str, ...]] = {
    "beginning_balance": (
        "BEGINNING BALANCE",
        "OPENING BALANCE",
        "PREVIOUS BALANCE",
        "BALANCE FORWARD",
        "BALANCE BROUGHT FORWARD",
    ),
    "ending_balance": (
        "ENDING BALANCE",
        "CLOSING BALANCE",
        "NEW BALANCE",
        "FINAL BALANCE",
    ),
    "stated_total_credits": (
        "TOTAL CREDITS",
        "TOTAL DEPOSITS",
        "DEPOSITS AND OTHER CREDITS",
        "DEPOSITS/CREDITS",
        "CREDITS/DEPOSITS",
    ),
    "stated_total_debits": (
        "TOTAL DEBITS",
        "TOTAL WITHDRAWALS",
        "CHECKS AND OTHER DEBITS",
        "CHECKS/DEBITS",
        "DEBITS/WITHDRAWALS",
    ),
    "stated_average_balance": (
        "AVERAGE DAILY BALANCE",
        "AVERAGE LEDGER BALANCE",
        "AVERAGE COLLECTED BALANCE",
        "AVERAGE BALANCE",
    ),
    "stated_service_charge": (
        "SERVICE CHARGE",
        "SERVICE FEE",
        "TOTAL FEES",
    ),
    "stated_interest_paid": (
        "INTEREST PAID",
        "INTEREST EARNED",
        "INTEREST CREDIT",
    ),
}


def _statement_amount_fields(statement: Statement) -> list[tuple[str, float]]:
    values = (
        ("beginning_balance", statement.beginning_balance),
        ("ending_balance", statement.ending_balance),
        ("stated_total_credits", statement.stated_total_credits),
        ("stated_total_debits", statement.stated_total_debits),
        ("stated_average_balance", statement.stated_average_balance),
        ("stated_service_charge", statement.stated_service_charge),
        ("stated_interest_paid", statement.stated_interest_paid),
    )
    return [(name, value) for name, value in values if value is not None]


def _statement_field_grounded(text: str, name: str, value: float) -> bool:
    compact = text.replace(",", "")
    labels = _STATEMENT_FIELD_LABELS[name]
    for start, end in _amount_spans(text, value):
        window = compact[max(0, start - 180):min(len(compact), end + 180)].upper()
        if any(label in window for label in labels):
            return True
    return False


def _period_scope_valid(statement: Statement, text: str) -> bool:
    try:
        period_start = date.fromisoformat(statement.period_start or "")
        period_end = date.fromisoformat(statement.period_end or "")
    except ValueError:
        return False
    calendar_days = (period_end - period_start).days + 1
    if calendar_days < 1 or calendar_days > 93:
        return False
    if statement.days_in_period is not None and statement.days_in_period != calendar_days:
        return False
    period_lines = [
        line
        for line in text.splitlines()
        if len(line) <= 300
        and _date_is_near(line, statement.period_start or "")
        and _date_is_near(line, statement.period_end or "")
    ]
    if not period_lines:
        return False
    for year in {period_start.year, period_end.year}:
        short_year = year % 100
        if not any(
            re.search(rf"(?<!\d){year}(?!\d)", line)
            or re.search(rf"(?:[/\-.']\s*){short_year:02d}(?!\d)", line)
            for line in period_lines
        ):
            return False
    for transaction in statement.transactions:
        try:
            posting_date = date.fromisoformat(transaction.date)
        except ValueError:
            return False
        if posting_date < period_start or posting_date > period_end:
            return False
    daily_dates: set[date] = set()
    for item in statement.stated_daily_balances:
        try:
            daily_date = date.fromisoformat(item.date)
        except ValueError:
            return False
        if daily_date < period_start or daily_date > period_end or daily_date in daily_dates:
            return False
        daily_dates.add(daily_date)
    return True


_GENERIC_BANK_WORDS = {
    "AND",
    "BANK",
    "BANKING",
    "CREDIT",
    "FINANCIAL",
    "NATIONAL",
    "OF",
    "THE",
    "UNION",
}


def _identity_scope_valid(statement: Statement, text: str) -> bool:
    if not statement.bank:
        return False
    source_upper = text.upper()
    normalized_bank = re.sub(r"(?<=[A-Z0-9])[.&](?=[A-Z0-9])", "", statement.bank.upper())
    normalized_source = re.sub(r"(?<=[A-Z0-9])[.&](?=[A-Z0-9])", "", source_upper)
    source_tokens = set(_BANK_WORD_RE.findall(normalized_source))
    bank_tokens = {
        token
        for token in _BANK_WORD_RE.findall(normalized_bank)
        if token not in _GENERIC_BANK_WORDS
    }
    if not bank_tokens:
        bank_tokens = set(_BANK_WORD_RE.findall(normalized_bank))
    required_bank_tokens = min(2, len(bank_tokens))
    if required_bank_tokens == 0:
        return False
    if len(bank_tokens & source_tokens) < required_bank_tokens:
        return False

    if statement.account_number:
        account_key = re.sub(r"[^A-Z0-9]", "", statement.account_number.upper())
        account_suffix = account_key[-4:]
        source_key = re.sub(r"[^A-Z0-9]", "", source_upper)
        if len(account_suffix) < 4 or account_suffix not in source_key:
            return False
    elif (
        statement.document_account_count is not None
        and statement.document_account_count > 1
    ):
        return False
    return True


def validate_generic_source(statement: Statement, markdown: str) -> SourceValidation:
    pages = _pages(markdown)
    used_spans: set[tuple[int, int, int]] = set()
    ungrounded: list[int] = []
    missing_pages: list[int] = []
    for index, transaction in enumerate(statement.transactions, start=1):
        grounded, page_missing = _ground_transaction(transaction, pages, used_spans)
        if not grounded:
            ungrounded.append(index)
        if page_missing:
            missing_pages.append(index)

    daily_used_spans: set[tuple[int, int, int]] = set()
    ungrounded_daily_balances: list[int] = []
    missing_daily_pages: list[int] = []
    for index, item in enumerate(statement.stated_daily_balances, start=1):
        grounded, page_missing = _ground_daily_balance(item, pages, daily_used_spans)
        if not grounded:
            ungrounded_daily_balances.append(index)
        if page_missing:
            missing_daily_pages.append(index)

    all_text = "\n".join(pages.values())
    statement_fields = _statement_amount_fields(statement)
    ungrounded_fields = [
        name
        for name, value in statement_fields
        if not _statement_field_grounded(all_text, name, value)
    ]

    transaction_count = len(statement.transactions)
    grounded_count = transaction_count - len(ungrounded)
    field_count = len(statement_fields)
    field_score = (
        (field_count - len(ungrounded_fields)) / field_count
        if field_count
        else 0.0
    )
    account_scope_valid = bool(
        statement.document_account_count is not None
        and (
            (
                statement.document_account_count == 1
                and statement.account_selection_status == "single_account"
            )
            or (
                statement.document_account_count > 1
                and statement.account_selection_status == "selected_primary"
            )
        )
    )
    period_scope_valid = _period_scope_valid(statement, all_text)
    identity_scope_valid = _identity_scope_valid(statement, all_text)
    daily_balance_count = len(statement.stated_daily_balances)
    grounded_daily_balance_count = daily_balance_count - len(ungrounded_daily_balances)
    zero_activity_supported = bool(
        transaction_count == 0
        and statement.beginning_balance is not None
        and statement.ending_balance is not None
        and abs(statement.beginning_balance - statement.ending_balance) < 0.005
        and statement.stated_total_credits == 0
        and statement.stated_total_debits == 0
        and not ungrounded_fields
    )
    transaction_score = (
        grounded_count / transaction_count
        if transaction_count
        else 1.0 if zero_activity_supported else 0.0
    )
    score = round(
        transaction_score * 0.55
        + field_score * 0.2
        + (0.1 if account_scope_valid else 0.0)
        + (0.1 if period_scope_valid else 0.0)
        + (0.05 if identity_scope_valid else 0.0),
        4,
    )
    if daily_balance_count:
        daily_balance_score = grounded_daily_balance_count / daily_balance_count
        score = round(score * 0.9 + daily_balance_score * 0.1, 4)
    ok = bool(
        (transaction_count or zero_activity_supported)
        and not ungrounded
        and not missing_pages
        and not ungrounded_fields
        and account_scope_valid
        and period_scope_valid
        and identity_scope_valid
        and not ungrounded_daily_balances
        and not missing_daily_pages
    )
    notes: list[str] = []
    if ungrounded:
        notes.append("one or more extracted transactions could not be located on the claimed source page")
    if missing_pages:
        notes.append("one or more extracted transactions lack valid page provenance")
    if ungrounded_fields:
        notes.append("one or more extracted statement-level amounts lack matching labeled source evidence")
    if not account_scope_valid:
        notes.append("generic extraction did not prove isolation of one source account")
    if not period_scope_valid:
        notes.append("generic extraction did not prove one valid source statement period")
    if not identity_scope_valid:
        notes.append("generic extraction did not prove the institution and selected account identity")
    if ungrounded_daily_balances:
        notes.append("one or more extracted daily balances lack matching source-table evidence")
    if missing_daily_pages:
        notes.append("one or more extracted daily balances lack valid page provenance")
    if transaction_count == 0 and not zero_activity_supported:
        notes.append("the source does not prove an explicit zero-activity ledger")
    return SourceValidation(
        method="generic_ocr_text_grounding",
        ok=ok,
        score=score,
        transaction_count=transaction_count,
        grounded_transaction_count=grounded_count,
        account_scope_valid=account_scope_valid,
        period_scope_valid=period_scope_valid,
        identity_scope_valid=identity_scope_valid,
        zero_activity_supported=zero_activity_supported,
        daily_balance_count=daily_balance_count,
        grounded_daily_balance_count=grounded_daily_balance_count,
        ungrounded_daily_balance_indexes=ungrounded_daily_balances,
        missing_daily_balance_page_indexes=missing_daily_pages,
        ungrounded_transaction_indexes=ungrounded,
        missing_page_evidence_indexes=missing_pages,
        ungrounded_statement_fields=ungrounded_fields,
        notes=notes,
    )
