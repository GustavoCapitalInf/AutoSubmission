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
    #: The closing this account PRINTS, where the paper states one its own
    #: postings do not produce. Both the section's caption and the table's row
    #: carry it, so the two still agree — which is what makes it a fixture for
    #: a section that publishes nothing and is not idle, rather than one that
    #: simply disagrees with its table.
    printed_closing: float | None = None

    def column(self, posting: Posting) -> int:
        """Which printed COLUMN the row is in: the type word decides it."""
        return -1 if posting.kind.lower() in ("withdrawal", "draft") else 1

    def sign(self, posting: Posting) -> int:
        """What the row does to the BALANCE. A reversal is a negative entry in
        the column it adjusts, so the two differ on exactly those rows."""
        column = self.column(posting)
        return -column if posting.reversal else column

    @property
    def credits(self) -> float:
        """The DEPOSITS column total, NETTED — the paper's own convention."""
        return round(sum(self.sign(p) * p.amount
                         for p in self.postings if self.column(p) > 0), 2)

    @property
    def debits(self) -> float:
        """The WITHDRAWALS column total, netted the same way."""
        return round(sum(-self.sign(p) * p.amount
                         for p in self.postings if self.column(p) < 0), 2)

    @property
    def closing(self) -> float:
        if self.printed_closing is not None:
            return self.printed_closing
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
    repeat_section_at_end: str | None = None,
    closing_override: dict[str, float] | None = None,
    opening_override: dict[str, float] | None = None,
    movement_override: dict[str, tuple[float, float]] | None = None,
    drop_row_figure: str | None = None,
    extra_lines: dict[str, list[str]] | None = None,
) -> str:
    """A whole constructed member statement.

    Every keyword breaks the page in ONE named way, which is what lets a test
    name the condition it is about:

    * `enumerate_accounts` — the table and the printed sections disagree
      (L1-C1);
    * `repeat_section` / `repeat_section_at_end` — one identity's section
      printed twice, adjacently and away from itself (L1-C2, L1-C3);
    * `opening_override` / `closing_override` — the table and the section
      disagree about a figure by a named amount (L1-C6, L1-C10);
    * `movement_override` — the table's DEPOSITS / WITHDRAWALS columns state
      totals the ledger does not sum to, while the closing still follows
      (L1-C8's oracle: two errors that cancel);
    * `drop_row_figure` — one enumerated row printed with fewer figures than
      the caption names columns (L1-C5's row width);
    * `extra_lines` — lines printed inside a section's ledger region (L1-C7).
    """
    enumerated = enumerate_accounts if enumerate_accounts is not None else accounts
    closings = closing_override or {}
    openings = opening_override or {}
    movements = movement_override or {}
    lines = [f"Statement Dates: {period}"]
    total = (total_override if total_override is not None
             else round(sum(account.closing for account in enumerated), 2))
    if prints_total:
        lines.append(ROLLUP_CAPTION + _money(total))
    lines.append(column_caption)
    for account in enumerated:
        closing = closings.get(account.suffix, account.closing)
        opening = openings.get(account.suffix, account.opening)
        credits, debits = movements.get(
            account.suffix, (account.credits, account.debits))
        figures = [_money(opening), _money(credits), _money(debits), _money(closing)]
        if drop_row_figure == account.suffix:
            figures = figures[:-1]
        lines.append(
            f"{account.label} (Suffix #{account.suffix}) " + " ".join(figures)
        )
    for account in accounts:
        if not account.prints_section:
            continue
        lines.extend(_section(account, (extra_lines or {}).get(account.suffix)))
        if repeat_section == account.suffix:
            lines.extend(_section(account))
    if repeat_section_at_end is not None:
        repeated = next(a for a in accounts if a.suffix == repeat_section_at_end)
        lines.extend(_section(repeated))
    return "\n".join(lines) + "\n"


def _section(account: Account, extra: list[str] | None = None) -> list[str]:
    lines = [
        f"{account.label}  Suffix #{account.suffix} "
        f"Previous Balance: {_money(account.opening)}",
        GRID_CAPTION,
    ]
    lines.extend(_rows(account))
    lines.extend(extra or [])
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
