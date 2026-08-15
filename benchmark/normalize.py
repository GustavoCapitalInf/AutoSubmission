"""Normalization of MoneyThumb response payloads.

MoneyThumb emits string-typed numbers (``"23250.00"``, ``".00"``,
``"-255500.00"``), percent strings (``"0%"``), string booleans
(``"true"``/``"false"``) and two date renderings (``"Jan 1, 2026"`` and
``"2026-01-01"``).  These helpers convert them into typed Python values
without ever mutating the source files (``moneythumbResults/`` is read-only).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

_MONEY_RE = re.compile(r"^-?(?:\d[\d,]*)?(?:\.\d+)?$")


def parse_money(value: Any) -> float | None:
    """Parse MT's string-typed numbers. ``".00"`` -> 0.0; percent -> number."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "n/a", ""}:
        return None
    if text.endswith("%"):
        text = text[:-1].strip()
    text = text.replace(",", "").replace("$", "")
    if text in {".", "-", ""}:
        return None
    if text.startswith("."):
        text = "0" + text
    elif text.startswith("-."):
        text = "-0" + text[1:]
    if not _MONEY_RE.match(text):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    number = parse_money(value)
    if number is None:
        return None
    return int(round(number))


def parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    return None


def parse_date_any(value: Any) -> str | None:
    """Return ISO ``YYYY-MM-DD`` for either MT date rendering."""
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def last4(account: Any) -> str | None:
    """Digits-preferring last-4 of an account identifier (for matching only)."""
    if account is None:
        return None
    text = str(account).strip()
    if not text or text.lower() == "unknown":
        return None
    digits = re.sub(r"\D", "", text)
    if digits:
        return digits[-4:]
    return text[-4:]


def collect_paths(node: Any, prefix: str = "") -> set[str]:
    """Every distinct JSON path in a payload; list indices collapse to ``[]``.

    This is the input to the coverage rollup that proves no MoneyThumb field
    was silently dropped.
    """
    paths: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            paths |= collect_paths(value, f"{prefix}.{key}" if prefix else key)
        if not node and prefix:
            paths.add(prefix)
    elif isinstance(node, list):
        if not node:
            paths.add(prefix + "[]")
        for item in node:
            paths |= collect_paths(item, prefix + "[]")
    else:
        paths.add(prefix)
    return paths


@dataclass
class MTStatementRow:
    """Normalized ``scorecard.statements_summary[]`` row (per account-month)."""

    raw: dict[str, Any]
    account: str | None = None
    account_last4: str | None = None
    start_date: str | None = None
    ending_date: str | None = None
    reconciled: bool | None = None
    starting_balance: float | None = None
    ending_balance: float | None = None
    total_credits: float | None = None
    num_credits: int | None = None
    total_debits: float | None = None
    num_debits: int | None = None
    true_credits: float | None = None
    nontrue_credits: float | None = None
    num_true_credits: int | None = None
    num_nontrue_credits: int | None = None
    avg_balance: float | None = None
    min_balance: float | None = None
    days_neg: int | None = None
    num_nsfs: int | None = None
    total_nsfs: float | None = None
    net_cashflow: float | None = None
    num_mcas: int | None = None
    mca_debits: float | None = None
    mca_withhold_percent: float | None = None
    num_of_mca_positions: int | None = None
    bank_name: str | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "MTStatementRow":
        return cls(
            raw=raw,
            account=raw.get("account"),
            account_last4=last4(raw.get("account")),
            start_date=parse_date_any(raw.get("start_date")),
            ending_date=parse_date_any(raw.get("ending_date")),
            reconciled=parse_bool(raw.get("reconciled")),
            starting_balance=parse_money(raw.get("starting_balance")),
            ending_balance=parse_money(raw.get("ending_balance")),
            total_credits=parse_money(raw.get("total_credits")),
            num_credits=parse_int(raw.get("num_credits")),
            total_debits=parse_money(raw.get("total_debits")),
            num_debits=parse_int(raw.get("num_debits")),
            true_credits=parse_money(raw.get("true_credits")),
            nontrue_credits=parse_money(raw.get("nontrue_credits")),
            num_true_credits=parse_int(raw.get("num_true_credits")),
            num_nontrue_credits=parse_int(raw.get("num_nontrue_credits")),
            avg_balance=parse_money(raw.get("avg_balance")),
            min_balance=parse_money(raw.get("min_balance")),
            days_neg=parse_int(raw.get("days_neg")),
            num_nsfs=parse_int(raw.get("num_nsfs")),
            total_nsfs=parse_money(raw.get("total_nsfs")),
            net_cashflow=parse_money(raw.get("net_cashflow")),
            num_mcas=parse_int(raw.get("num_mcas")),
            mca_debits=parse_money(raw.get("mca_debits")),
            mca_withhold_percent=parse_money(raw.get("mca_withhold_percent")),
            num_of_mca_positions=parse_int(raw.get("num_of_mca_positions")),
            bank_name=raw.get("bank_name"),
        )


@dataclass
class MTResultRow:
    """Normalized ``statement_summaries[].results[]`` row (per file+account)."""

    raw: dict[str, Any]
    filename: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    account_last4: str | None = None
    currency: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    start_balance: float | None = None
    end_balance: float | None = None
    end_balance_calc: float | None = None
    end_balance_pdf: float | None = None
    reconciled: bool | None = None
    fail: bool | None = None
    balances_valid: bool | None = None
    num_transactions: int | None = None
    num_credits: int | None = None
    num_debits: int | None = None
    tot_credits: float | None = None
    tot_debits: float | None = None
    nsf_count: int | None = None
    ocr: bool | None = None
    image: bool | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any], filename: str | None = None) -> "MTResultRow":
        return cls(
            raw=raw,
            filename=filename,
            bank_name=raw.get("bankName"),
            account_number=raw.get("accountNumber"),
            account_last4=last4(raw.get("accountNumber")),
            currency=raw.get("currencycode"),
            start_date=parse_date_any(raw.get("startDate")),
            end_date=parse_date_any(raw.get("endDate")),
            start_balance=parse_money(raw.get("startBalance")),
            end_balance=parse_money(raw.get("endBalance")),
            end_balance_calc=parse_money(raw.get("endBalanceCalc")),
            end_balance_pdf=parse_money(raw.get("endBalancePDF")),
            reconciled=parse_bool(raw.get("reconciled")),
            fail=parse_bool(raw.get("fail")),
            balances_valid=parse_bool(raw.get("balancesValid")),
            num_transactions=parse_int(raw.get("numTransactions")),
            num_credits=parse_int(raw.get("numCredits")),
            num_debits=parse_int(raw.get("numDebits")),
            tot_credits=parse_money(raw.get("totCredits")),
            tot_debits=parse_money(raw.get("totDebits")),
            nsf_count=parse_int(raw.get("nsfcount")),
            ocr=parse_bool(raw.get("ocr")),
            image=parse_bool(raw.get("image")),
        )


@dataclass
class MTLender:
    """Aggregated MoneyThumb MCA activity for one lender label."""

    lender: str
    withdrawal_count: int = 0
    withdrawal_total: float = 0.0        # absolute value
    deposit_total: float = 0.0
    deposit_dates: list[str] = field(default_factory=list)
    transactions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MTSet:
    """One loaded + normalized MoneyThumb benchmark result."""

    name: str
    ok: bool
    http_status: int | None
    uploaded_at: str | None
    source_files: list[str]
    stub_message: str | None            # non-dict response (klr_may 202 stub)
    response: dict[str, Any] | None
    paths: set[str]
    summary_rows: list[MTStatementRow]
    result_rows: list[MTResultRow]

    @property
    def is_stub(self) -> bool:
        return self.response is None

    @property
    def scorecard(self) -> dict[str, Any]:
        return (self.response or {}).get("scorecard") or {}

    def revenue_statistic(self, label: str) -> dict[str, Any] | None:
        for row in self.scorecard.get("revenue_statistics") or []:
            if row.get("label") == label:
                return row
        return None

    def lenders(self) -> dict[str, MTLender]:
        """Aggregate ``mca_transactions`` + ``monthly_mca`` per lender label."""
        lenders: dict[str, MTLender] = {}
        for txn in self.scorecard.get("mca_transactions") or []:
            label = txn.get("lender") or "unknown"
            entry = lenders.setdefault(label, MTLender(lender=label))
            amount = parse_money(txn.get("amount")) or 0.0
            if amount < 0:
                entry.withdrawal_count += 1
                entry.withdrawal_total = round(entry.withdrawal_total + abs(amount), 2)
            else:
                entry.deposit_total = round(entry.deposit_total + amount, 2)
                if txn.get("date"):
                    entry.deposit_dates.append(parse_date_any(txn.get("date")) or str(txn.get("date")))
            entry.transactions.append(txn)
        # monthly_mca carries deposits that may not appear in mca_transactions.
        for month in self.scorecard.get("monthly_mca") or []:
            for account in month.get("accounts") or []:
                for row in account.get("lenders") or []:
                    label = row.get("lender") or "unknown"
                    entry = lenders.setdefault(label, MTLender(lender=label))
                    deposit = parse_money(row.get("deposittotal")) or 0.0
                    deposit_date = parse_date_any(row.get("depositdate"))
                    if deposit and deposit_date and deposit_date not in entry.deposit_dates:
                        if entry.deposit_total < deposit:
                            entry.deposit_total = round(entry.deposit_total + deposit, 2)
                        entry.deposit_dates.append(deposit_date)
        return lenders

    def daily_balances(self, account_last4: str | None) -> dict[str, float]:
        """MT daily balances for one account, ISO date -> balance.

        Measured over `moneythumbResults/results`, the dates MT reports are
        the BANKING days of the span (weekdays minus observed US federal
        bank holidays), not the days that carry activity: 11 of 11 series
        are exactly that set. See `benchmark.compare._mt_activity_mean_note`
        for the full measurement and for why it is reproduced behaviour
        rather than a specification.
        """
        series: dict[str, float] = {}
        for day in self.scorecard.get("daily_balances") or []:
            iso = parse_date_any(day.get("event_date"))
            for balance in day.get("balances") or []:
                if account_last4 and last4(balance.get("acctid")) != account_last4:
                    continue
                value = parse_money(balance.get("balance"))
                if iso and value is not None:
                    series[iso] = value
        return series


def load_mt_set(results_root: Path, name: str) -> MTSet:
    """Load ``<results_root>/<name>/response.json`` read-only and normalize."""
    payload = json.loads((results_root / name / "response.json").read_text(encoding="utf-8"))
    response = payload.get("response")
    stub_message: str | None = None
    summary_rows: list[MTStatementRow] = []
    result_rows: list[MTResultRow] = []
    paths: set[str] = set()
    if isinstance(response, dict):
        paths = collect_paths(response)
        for raw in (response.get("scorecard") or {}).get("statements_summary") or []:
            summary_rows.append(MTStatementRow.from_raw(raw))
        file_status = response.get("file_status") or []
        tid_to_filename = {
            entry.get("tid"): entry.get("filename")
            for entry in file_status
            if isinstance(entry, dict)
        }
        for summary in response.get("statement_summaries") or []:
            filename = tid_to_filename.get(summary.get("tid"))
            for raw in summary.get("results") or []:
                result_rows.append(MTResultRow.from_raw(raw, filename=filename))
    else:
        stub_message = str(response) if response is not None else None
        response = None
    return MTSet(
        name=name,
        ok=bool(payload.get("ok")),
        http_status=payload.get("http_status"),
        uploaded_at=payload.get("uploaded_at"),
        source_files=list(payload.get("source_files") or []),
        stub_message=stub_message,
        response=response,
        paths=paths,
        summary_rows=summary_rows,
        result_rows=result_rows,
    )
