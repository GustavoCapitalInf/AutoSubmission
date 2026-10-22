"""A package's members and its passes' result, and what the package reads off each member account: values, currency,
printed account digits, bank, and whether two statements are one account."""
from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite
from typing import NamedTuple, Protocol

from analysis.package.calendar import iso_day
from analysis.payload_shape import is_document_payload, payload_accounts


class JobLike(Protocol):
    """A job the package lists: a stored `webapp.jobs.Job`, or a stand-in with the same fields. `content_sha256` is
    read where a job carries one."""

    id: str
    filename: str | None
    status: str
    analysis: dict | None
    analysis_error: str | None
    error: str | None


class MemberKey(NamedTuple):
    """A member's job and its account's 1-based place in the document's printed order (None for a job publishing one
    account's payload). A tuple, so a `(job id, account index)` pair finds it in a map."""

    job_id: str
    account_index: int | None

    @property
    def id(self) -> str:
        """The id the package publishes for the member."""
        return self.job_id if self.account_index is None else f"{self.job_id}#account_{self.account_index}"


@dataclass(frozen=True)
class Member:
    """One account `package_members` admitted. `account` is its displayed account payload. An account of a document
    carries neither the document's R-d transfers nor the statement's `analysis_rules_outdated`, so
    `internal_transfer_positions` is read off the job's stored document and `analysis_rules_outdated` off the job's
    displayed copy."""

    key: MemberKey
    job: JobLike
    account: dict
    account_count: int
    internal_transfer_positions: set[int]
    analysis_rules_outdated: bool

    @property
    def ready(self) -> bool:
        return self.job.status == "done" and self.job.analysis is not None


@dataclass(frozen=True)
class PackagePasses:
    """What `package_matches` found. Each map is keyed by member, and an overlay by the row's original position."""

    overlays: dict[MemberKey, dict[int, dict]]
    matches: list[dict]
    debit_flags: list[dict]
    unchecked: dict[MemberKey, str]
    moved: dict[MemberKey, list[dict]]
    represented: dict[tuple[MemberKey, str], dict]


def is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def num(value: object, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def statement_currency(analysis: dict) -> str | None:
    """The ISO code this member's statement is denominated in, or None when the
    document does not declare one.

    `analysis/schema.py` gives `Statement.currency` a non-null default, so every
    payload the current pipeline produces carries a code. None here therefore
    means a payload that predates the field or never came from `Statement` at
    all — a genuine unknown, which CURRENCY DOCTRINE §B resolves by failing
    closed rather than by forcing a currency onto it.

    Case and surrounding blanks are folded away: ISO 4217 codes are uppercase,
    so `usd` is a spelling of USD rather than a second unit, and refusing a
    package over a spelling would be a false refusal, not a safe one.
    """
    statement = analysis.get("statement")
    if not isinstance(statement, dict):
        return None
    code = statement.get("currency")
    if not isinstance(code, str):
        return None
    return code.strip().upper() or None


def is_money_value(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def stored_accounts(analysis: object) -> list[dict]:
    """The account payloads a stored analysis publishes, in printed order: one for today's payload, each account of a
    document payload, none for a job with no analysis."""
    if not isinstance(analysis, dict) or not analysis:
        return []
    if is_document_payload(analysis):
        accounts = payload_accounts(analysis, surface="webapp/app.py::_stored_accounts")
        return [account for account in accounts if isinstance(account, dict)]
    return [analysis] if isinstance(analysis.get("statement"), dict) else []


#: What `printed_account_digits` removes from a printed account number before it reads the digits at its end:
#: blanks and the separators banks print inside a number.
_ACCOUNT_NUMBER_SEPARATORS = re.compile(r"[\s\-./]")


_TRAILING_DIGITS = re.compile(r"[0-9]+$")


def printed_account_digits(account: object) -> str:
    """The digits an account's statement prints at the END of its account number, its blanks, '-', '.' and '/'
    removed ('XXXX-1010' gives '1010', '12XXXX3456' '3456', '100000001010' all twelve); '' when the number ends in
    no digit or is not printed."""
    statement = account.get("statement") if isinstance(account, dict) else None
    if not isinstance(statement, dict):
        return ""
    match = _TRAILING_DIGITS.search(_ACCOUNT_NUMBER_SEPARATORS.sub("", str(statement.get("account_number") or "")))
    return match.group(0) if match else ""


def numbers_conflict(digits: str, other: str) -> bool:
    """Two printed account numbers are two accounts when both print more than four digits and the shorter's digits
    are not the end of the longer's. A masked or four-digit print never conflicts."""
    if len(digits) <= 4 or len(other) <= 4:
        return False
    common = min(len(digits), len(other))
    return digits[-common:] != other[-common:]


REVIEW_DECISIONS = frozenset({"confirmed", "rejected"})


def row_day(row: dict) -> str:
    """A row's date as one text: its ISO day, or the printed text when it is no ISO day."""
    day = iso_day(row.get("date"))
    return day.isoformat() if day is not None else str(row.get("date") or "").strip()


def row_cents(row: dict) -> int:
    return int(round(num(row.get("amount")) * 100))


#: True revenue spec §6.2's package passes: two statements of one account are consecutive when the later one starts 0 to
#: this many days after the earlier one ends. The corpus's gaps are 0 to 3 days, or over 20 (a month missing), so any
#: bound from 3 to 20 reads the same; 7 also spans a holiday and a 28th-to-1st cycle.
PACKAGE_CONSECUTIVE_DAYS = 7


def bank_key(statement: object) -> str:
    """The bank a statement prints, casefolded and its blanks collapsed ('' when none): the bank an account is read
    under by the package passes."""
    bank = statement.get("bank") if isinstance(statement, dict) else None
    return " ".join(str(bank or "").split()).casefold()


#: An informal printout's label, read as the bank whose account it prints (`package_bank`). Chase's online transaction
#: export publishes the label "Chase Transaction Export" (`analysis/chase.py`) where its statements publish "Chase";
#: the export is no formal statement (`chase_export`'s `formal_statement: False` in
#: `analysis/parser_registry_entries.py`). Found's month-to-date view already prints its statement's label
#: "Lead Bank (Found)" (`analysis/found_lead.py`) and needs none.
_PACKAGE_BANK_ALIASES = {"chase transaction export": "chase"}


def package_bank(statement: object) -> str:
    """The bank one account's statements are compared under by the package's shorter-printout and overlap pass
    (`package_superseded`) and its months: `bank_key`, an informal printout's label read as its bank
    (`_PACKAGE_BANK_ALIASES`)."""
    bank = bank_key(statement)
    return _PACKAGE_BANK_ALIASES.get(bank, bank)


def consecutive(earlier: dict, later: dict) -> bool:
    """`later` is the statement that follows `earlier`: both period days read, and `later` starts 0 to
    PACKAGE_CONSECUTIVE_DAYS days after `earlier` ends. Two overlapping statements never are."""
    if earlier["end"] is None or later["start"] is None:
        return False
    return 0 <= (later["start"] - earlier["end"]).days <= PACKAGE_CONSECUTIVE_DAYS


def _chained(earlier: dict, later: dict) -> bool:
    """`later` follows `earlier` (consecutive) and opens on its closing balance, to the cent."""
    return (
        consecutive(earlier, later) and is_money_value(earlier["closing"]) and is_money_value(later["opening"])
        and round(float(earlier["closing"]) * 100) == round(float(later["opening"]) * 100)
    )


def same_account(first: dict, second: dict) -> bool:
    """Two package members are statements of ONE account: two jobs, one declared currency and one printed bank
    (`bank_key`), and either both print four digits or more, with an equal last four and no conflict, or one prints
    fewer: then the account names do not differ where both print one, and the balance chains (one follows the other
    and opens on its closing balance, `_chained`). A member with no declared currency is never one."""
    if first["job_id"] == second["job_id"] or not first["currency"] or first["currency"] != second["currency"]:
        return False
    if not first["bank"] or first["bank"] != second["bank"]:
        return False
    if len(first["digits"]) >= 4 and len(second["digits"]) >= 4:
        return first["digits"][-4:] == second["digits"][-4:] and not numbers_conflict(first["digits"],
                                                                                        second["digits"])
    if first["name"] and second["name"] and first["name"] != second["name"]:
        return False
    return _chained(first, second) or _chained(second, first)


def months_linked(first: dict, second: dict) -> bool:
    """Two counted members are statements of one account for the months' floor. Never two accounts of one document
    (one job). Two keyed members (each a bank, `package_bank`, and four digits or more) are one account when the bank
    and the last four are equal, chained or not. Otherwise the banks agree where both print one, the account names do
    not differ where both print one, and the balance chains. A member linked to none is its own account."""
    if first["job_id"] == second["job_id"]:
        return False
    if first["bank"] and second["bank"] and len(first["digits"]) >= 4 and len(second["digits"]) >= 4:
        return first["bank"] == second["bank"] and first["digits"][-4:] == second["digits"][-4:]
    if first["bank"] and second["bank"] and first["bank"] != second["bank"]:
        return False
    if first["name"] and second["name"] and first["name"] != second["name"]:
        return False
    return _chained(first, second) or _chained(second, first)


def different_accounts(first: dict, second: dict) -> bool:
    """Two package members are two of the business's accounts: two members (two jobs, or one document's two
    accounts), one declared currency, both print four digits or more, and the last fours differ or the full numbers
    conflict. There is no bank-name arm: one account read under two bank spellings is never two accounts, and a
    member that prints fewer than four digits is never paired (it is marked `no_account_number`)."""
    if first["key"] == second["key"] or not first["currency"] or first["currency"] != second["currency"]:
        return False
    if len(first["digits"]) < 4 or len(second["digits"]) < 4:
        return False
    return first["digits"][-4:] != second["digits"][-4:] or numbers_conflict(first["digits"], second["digits"])
