"""Constructed member statements for L1-S4, built by a generator rather than pasted.

Every figure, label, identity and date here is INVENTED. Nothing is copied from
a document: the generator takes an opening balance and a list of postings and
computes the running balances, the enumerating table's movement columns and the
document's cross-account total, so a fixture that says a section closes at a
figure closes at it because the arithmetic says so and not because someone typed
it twice.

That is what makes these fixtures able to prove a refusal. A pasted page can
only ever be the page it was pasted from; a page whose arithmetic is generated
can be broken in ONE named way — a cent moved, a caption removed, a heading the
table never enumerated, a section printed twice — and the reader's answer to
that one difference is the thing under test.

The furniture is the TEMPLATE's, which is what
`analysis/member_statement.py` reads: an enumerating caption with a
cross-account total, a column caption naming four columns, a section heading
carrying a product label and an identity suffix beside its own opening caption,
a ledger grid caption, and a closing caption. No issuer, no domain, no address,
no customer.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: The period every constructed document prints. Invented, and deliberately a
#: month that begins on the first: the ADB is a calendar-day average over the
#: PRINTED period, and a fixture whose period started mid-month would be
#: testing the ADB engine rather than this reader.
PERIOD = "04/01/26 – 04/30/26"

ROLLUP_CAPTION = "Statement Summary Deposit Accounts Total  Balance: "
COLUMN_CAPTION = (
    "ACCOUNT TYPE PREVIOUS BALANCE DEPOSITS WITHDRAWALS ENDING BALANCE"
)
GRID_CAPTION = "TRAN DATE POST DATE DESCRIPTION WITHDRAWALS DEPOSITS BALANCE"


@dataclass
class Posting:
    """One printed ledger row: a day, a printed direction word, a description
    and a magnitude. The running balance is COMPUTED, never given."""

    day: int
    kind: str          # the printed type word: Deposit / Withdrawal / Draft
    description: str
    amount: float      # a magnitude; the type word carries the direction
    post_day: int | None = None
    qualifier: str = ""    # `Recurring`, printed in front of the type word
    reversal: bool = False  # `Adjustment`, printed after it and reversing it


@dataclass
class Account:
    label: str
    suffix: str
    opening: float
    postings: list[Posting] = field(default_factory=list)
    #: `False` builds a section whose ledger this reader must not publish: no
    #: heading, no closing caption, whatever the table enumerates.
    prints_section: bool = True
    prints_closing: bool = True

    def sign(self, posting: Posting) -> int:
        direction = -1 if posting.kind.lower() in ("withdrawal", "draft") else 1
        return -direction if posting.reversal else direction

    @property
    def credits(self) -> float:
        return round(sum(p.amount for p in self.postings if self.sign(p) > 0), 2)

    @property
    def debits(self) -> float:
        return round(sum(p.amount for p in self.postings if self.sign(p) < 0), 2)

    @property
    def closing(self) -> float:
        return round(self.opening + self.credits - self.debits, 2)


_MONTH = "Apr"


def _money(value: float) -> str:
    return f"{value:,.2f}"


def _rows(account: Account) -> list[str]:
    lines: list[str] = []
    balance = account.opening
    for posting in account.postings:
        balance = round(balance + account.sign(posting) * posting.amount, 2)
        dates = f"{_MONTH} {posting.day}"
        if posting.post_day is not None:
            dates += f" {_MONTH} {posting.post_day}"
        kind = posting.kind
        if posting.qualifier:
            kind = f"{posting.qualifier} {kind}"
        if posting.reversal:
            kind = f"{kind} Adjustment"
        lines.append(
            f"{dates} {kind} {posting.description} "
            f"{_money(posting.amount)} {_money(balance)}"
        )
    return lines


def document(
    accounts: list[Account],
    *,
    period: str = PERIOD,
    column_caption: str = COLUMN_CAPTION,
    prints_total: bool = True,
    total_override: float | None = None,
    enumerate_accounts: list[Account] | None = None,
    repeat_section: str | None = None,
    closing_override: dict[str, float] | None = None,
) -> str:
    """A whole constructed member statement.

    `enumerate_accounts` lets the enumerating table disagree with the printed
    sections — the L1-C1 refusal; `repeat_section` prints one identity's
    section twice — the L1-C2 refusal the design assigns to this card;
    `closing_override` breaks the roll-up's agreement with a section's own
    printed closing by a named amount — L1-C6 / L1-C10.
    """
    enumerated = enumerate_accounts if enumerate_accounts is not None else accounts
    closings = closing_override or {}
    lines = [f"Statement Dates: {period}"]
    total = (total_override if total_override is not None
             else round(sum(account.closing for account in enumerated), 2))
    if prints_total:
        lines.append(ROLLUP_CAPTION + _money(total))
    lines.append(column_caption)
    for account in enumerated:
        closing = closings.get(account.suffix, account.closing)
        lines.append(
            f"{account.label} (Suffix #{account.suffix}) "
            f"{_money(account.opening)} {_money(account.credits)} "
            f"{_money(account.debits)} {_money(closing)}"
        )
    for account in accounts:
        if not account.prints_section:
            continue
        lines.extend(_section(account))
        if repeat_section == account.suffix:
            lines.extend(_section(account))
    return "\n".join(lines) + "\n"


def _section(account: Account) -> list[str]:
    lines = [
        f"{account.label}  Suffix #{account.suffix} "
        f"Previous Balance: {_money(account.opening)}",
        GRID_CAPTION,
    ]
    lines.extend(_rows(account))
    if account.prints_closing:
        lines.append(
            f"Dividend Year to Date   0.00 Ending Balance: "
            f"${_money(account.closing)}"
        )
    return lines


# ---------------------------------------------------------------------------
# the shapes the tests reach for
# ---------------------------------------------------------------------------


def posting_account(label: str = "SAMPLE CHECKING", suffix: str = "71",
                    opening: float = 800.00) -> Account:
    """An account that posts, and whose ledger reconciles by construction."""
    return Account(label=label, suffix=suffix, opening=opening, postings=[
        Posting(2, "Deposit", "Kiosk", 300.00),
        Posting(7, "Withdrawal", "Debit Card SAMPLE MERCHANT", 45.50),
        Posting(11, "Draft", "1001", 120.00),
        Posting(19, "Deposit", "ACH SAMPLE PAYER", 640.25),
        Posting(26, "Withdrawal", "POS #000000000001", 88.75),
    ])


def idle_account(label: str = "SAMPLE SHARE", suffix: str = "00",
                 opening: float = 25.00) -> Account:
    """A section printing its own opening and closing captions, the two
    coinciding, and nothing else — the Q3 class's whole population shape."""
    return Account(label=label, suffix=suffix, opening=opening, postings=[])
