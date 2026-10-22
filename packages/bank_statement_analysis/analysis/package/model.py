"""A package's members and its passes' result, what the package reads off each member account (`AccountFacts`), what
each member adds to the package (`MemberFigures`), and whether two statements are one account."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
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
class AccountFacts:
    """What one account payload's statement prints that the package reads an account by, read off ONE payload: a
    member's displayed account (`Member.facts`) or a job's stored account (`package_superseded`). The bank is kept
    three ways, because the relations read different ones: `printed_bank` as printed (a match leg names it),
    `bank_key` (`same_account`) and `package_bank` (`months_linked` and the shorter-printout pass)."""

    printed_bank: object
    bank_key: str
    package_bank: str
    digits: str
    name: str
    currency: str | None
    start: date | None
    end: date | None
    opening: object
    closing: object

    @classmethod
    def of(cls, account: dict) -> AccountFacts:
        statement = account.get("statement")
        if not isinstance(statement, dict):
            statement = {}
        return cls(
            printed_bank=statement.get("bank"), bank_key=bank_key(statement), package_bank=package_bank(statement),
            digits=printed_account_digits(account),
            name=" ".join(str(statement.get("account_name") or "").split()).casefold(),
            currency=statement_currency(account),
            start=iso_day(statement.get("period_start")), end=iso_day(statement.get("period_end")),
            opening=statement.get("beginning_balance"), closing=statement.get("ending_balance"),
        )


@dataclass(frozen=True)
class Member:
    """One account `package_members` admitted. `account` is its displayed account payload and `facts` that payload's
    facts. An account of a document carries neither the document's R-d transfers nor the statement's
    `analysis_rules_outdated`, so `internal_transfer_positions` is read off the job's stored document and
    `analysis_rules_outdated` off the job's displayed copy."""

    key: MemberKey
    job: JobLike
    account: dict
    account_count: int
    facts: AccountFacts
    internal_transfer_positions: set[int]
    analysis_rules_outdated: bool

    @property
    def ready(self) -> bool:
        return self.job.status == "done" and self.job.analysis is not None


@dataclass(frozen=True)
class SelectedPackage:
    """What `select_members` chose, before any figure. `listed`: every job the package lists, its repeats included.
    `members` and `excluded`: the accounts admitted and left out, each in the kept jobs' order, then the accounts'.
    `dropped`: the jobs left out as repeats or as printouts other statements print, in listed order.
    `duplicate_groups`: each repeated statement's jobs. `duplicate_accounts`: how many accounts of kept jobs are left
    out as repeats. `overlapping`: the overlaps named and never netted. `omitted_sections`: every kept job's ratified
    omissions, members or not."""

    listed: list[JobLike]
    members: list[Member]
    excluded: list[dict]
    dropped: list[dict]
    duplicate_groups: list[dict]
    duplicate_accounts: int
    overlapping: list[dict]
    omitted_sections: list[dict]


@dataclass(frozen=True)
class PackagePasses:
    """What `package_matches` found. Each map is keyed by member, and an overlay by the row's original position."""

    overlays: dict[MemberKey, dict[int, dict]]
    matches: list[dict]
    debit_flags: list[dict]
    unchecked: dict[MemberKey, str]
    moved: dict[MemberKey, list[dict]]
    represented: dict[tuple[MemberKey, str], dict]


class FunderShare(NamedTuple):
    """One known-funder match of a member's detection, as the package's funder roll-up adds it. `debit_count` is None
    for a match that publishes no `debit_count` and counts no debit: the roll-up gains no `debit_count` from it."""

    funder: str
    debit_count: int | None
    total_debited: float
    returned_payment_count: int
    returned_payment_total: float


class PotentialLenderShare(NamedTuple):
    """One potential lender of a member, as the package's potential lender roll-up adds it: its rows' count and total,
    or its detection match's where it has no row."""

    funder: str
    debit_count: int
    total_debited: float


class InsuranceShare(NamedTuple):
    """One insurance provider match of a member's detection, as the package's insurance roll-up adds it."""

    provider: str
    count: int
    total_debited: float


@dataclass(frozen=True)
class MemberFigures:
    """What one member adds to its package (`member_figures`). Each figure is the member's own, as `member_figures`
    computed it; the package adds it to its running sum and rounds the sum. `row` is the member's published row: the
    one dict the package lists in `documents` and, for a ready member, in `monthly`, which the lender reading's active
    positions are later set on; the package's member lists and months read its id, period, labels and flags off it.

    `tier_totals` and `tier_counts` are empty on a member with no tiers. `gate_cents` is the held, posted and True
    figures its gate reads, in cents, on a ready tiered member, else None. `zelle_parts` holds (tier, count, total) per
    Zelle part. The shares, matches and warnings follow the member's detection, and the ledger and evidence its rows."""

    member: Member
    row: dict
    credits: float
    debits: float
    cash_flow: float
    posted_credit_total: float
    posted_credit_count: int
    revenue_totals: dict[str, float | None]
    revenue_counts: dict[str, int]
    by_reason: dict[str, dict[str, dict]]
    tiered: bool
    tier_totals: dict[str, float]
    tier_counts: dict[str, int]
    verified_revenue_established: bool
    revenue_established: bool
    partial_revenue_denominator: bool
    gated: bool
    gate_cents: tuple[int, int, int] | None
    zelle_carried: bool
    zelle_setting_applied: bool
    zelle_counted_as_true_revenue: bool
    zelle_parts: list[tuple[str, int, float]]
    lender_debits: float
    lender_debit_count: int
    withholding_numerator: float
    returned_funder_payment_total: float
    returned_funder_payment_count: int
    lump_sum_payoff_total: float
    lump_sum_payoff_count: int
    potential_lender_debit_total: float
    potential_lender_debit_count: int
    insurance_total: float
    insurance_count: int
    eligible_deposits: float
    denominator_mode: str
    withholding_basis: dict
    basis_unestablished: bool
    nsf_count: int
    nsf_source: object
    adb_validated: bool
    adb_value: float
    adb_calendar_days: object
    funder_shares: list[FunderShare]
    potential_lender_shares: list[PotentialLenderShare]
    insurance_shares: list[InsuranceShare]
    flagged_rows: list[dict]
    funder_matches: list[dict]
    potential_matches: list[dict]
    insurance_matches: list[dict]
    returned_funder_payments: list[dict]
    lump_sum_payoffs: list[dict]
    large_unsourced_deposits: list[dict]
    transactions: list[dict]
    lender_evidence: list[dict]
    potential_lender_evidence: list[dict]
    insurance_evidence: list[dict]
    flagged_evidence: list[dict]
    revenue_evidence: dict[str, list[dict]]
    tier_evidence: dict[str, list[dict]]


def overlaid_row(row: dict, overlay: dict[int, dict], position: int) -> dict:
    """The row at original `position` of a member's statement with the package passes' patch for that position merged
    into its classification record (`overlay`: one member's patches by original position). A patched row is a new row
    holding a new record; any other row is returned as it is, so the displayed copy is never written."""
    if position not in overlay:
        return row
    return {**row, "classification": {**row["classification"], **overlay[position]}}


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


def consecutive(earlier: AccountFacts, later: AccountFacts) -> bool:
    """`later` is the statement that follows `earlier`: both period days read, and `later` starts 0 to
    PACKAGE_CONSECUTIVE_DAYS days after `earlier` ends. Two overlapping statements never are."""
    if earlier.end is None or later.start is None:
        return False
    return 0 <= (later.start - earlier.end).days <= PACKAGE_CONSECUTIVE_DAYS


def _chained(earlier: AccountFacts, later: AccountFacts) -> bool:
    """`later` follows `earlier` (consecutive) and opens on its closing balance, to the cent."""
    return (
        consecutive(earlier, later) and is_money_value(earlier.closing) and is_money_value(later.opening)
        and round(float(earlier.closing) * 100) == round(float(later.opening) * 100)
    )


def same_account(first: dict, second: dict) -> bool:
    """Two package members (their entries' `job_id` and `facts`) are statements of ONE account: two jobs, one declared
    currency and one printed bank (`bank_key`), and either both print four digits or more, with an equal last four
    and no conflict, or one prints fewer: then the account names do not differ where both print one, and the balance
    chains (one follows the other and opens on its closing balance, `_chained`). A member with no declared currency is
    never one."""
    one, two = first["facts"], second["facts"]
    if first["job_id"] == second["job_id"] or not one.currency or one.currency != two.currency:
        return False
    if not one.bank_key or one.bank_key != two.bank_key:
        return False
    if len(one.digits) >= 4 and len(two.digits) >= 4:
        return one.digits[-4:] == two.digits[-4:] and not numbers_conflict(one.digits, two.digits)
    if one.name and two.name and one.name != two.name:
        return False
    return _chained(one, two) or _chained(two, one)


def months_linked(first: dict, second: dict) -> bool:
    """Two counted members (their entries' `job_id` and `facts`) are statements of one account for the months' floor.
    Never two accounts of one document (one job). Two keyed members (each a bank, `package_bank`, and four digits or
    more) are one account when the bank and the last four are equal, chained or not. Otherwise the banks agree where
    both print one, the account names do not differ where both print one, and the balance chains. A member linked to
    none is its own account."""
    if first["job_id"] == second["job_id"]:
        return False
    one, two = first["facts"], second["facts"]
    if one.package_bank and two.package_bank and len(one.digits) >= 4 and len(two.digits) >= 4:
        return one.package_bank == two.package_bank and one.digits[-4:] == two.digits[-4:]
    if one.package_bank and two.package_bank and one.package_bank != two.package_bank:
        return False
    if one.name and two.name and one.name != two.name:
        return False
    return _chained(one, two) or _chained(two, one)


def different_accounts(first: dict, second: dict) -> bool:
    """Two package members (their entries' `key` and `facts`) are two of the business's accounts: two members (two
    jobs, or one document's two accounts), one declared currency, both print four digits or more, and the last fours
    differ or the full numbers conflict. There is no bank-name arm: one account read under two bank spellings is
    never two accounts, and a member that prints fewer than four digits is never paired (it is marked
    `no_account_number`)."""
    one, two = first["facts"], second["facts"]
    if first["key"] == second["key"] or not one.currency or one.currency != two.currency:
        return False
    if len(one.digits) < 4 or len(two.digits) < 4:
        return False
    return one.digits[-4:] != two.digits[-4:] or numbers_conflict(one.digits, two.digits)
