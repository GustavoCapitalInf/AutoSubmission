"""The Fifth Third commercial statement (the `FTCSTMT`/`UDSPDFSTMT` print stream).

The document's own arithmetic is unusually complete, and reading it correctly
turns on one thing: **the summary has three transaction components, not two.**

    02/01 Beginning Balance $(880.64) Number of Days in Period 28
    306 Checks $(372,005.76) 152 Withdrawals / Debits $(586,945.05)
    74 Deposits / Credits $1,461,352.14 02/28 Ending Balance $501,520.69

`Checks` is a separate debit-side total from `Withdrawals / Debits`, and a
reading that folds the two together — or ignores the first — breaks the closing
identity on every document that has a cheque book. The identity this parser
requires is therefore

    beginning + deposits - checks - withdrawals == ending

Each component prints as ``[count] LABEL [amount]``, and **both the count and
the amount are optional**: a period with no cheques prints the bare word
``Checks`` between the day count and the next component's count, and a period
with no other debits prints a bare ``Withdrawals / Debits``. A bare label means
the component is absent, which the document corroborates by omitting its detail
section as well — so "absent" is read off the page rather than assumed, and the
two readings are cross-checked against each other before anything is published.

Four independent instruments must agree before this parser returns a statement:

1. the closing identity above;
2. every component's count and amount, reprinted at the head of its own detail
   section (``Checks 306 checks totaling $372,005.76``), agreeing with the
   summary — including agreeing about absence;
3. the rows actually read out of each section agreeing with that section's
   printed count and printed total;
4. the running balance, walked day by day from the opening balance, agreeing
   with every entry of the printed `Daily Balance Summary` and finishing on the
   printed closing balance.

The cheque detail is a three-up ``Number Date Paid Amount`` grid carrying
sequence-gap (``*``), electronic-image (``i``) and substitute-cheque (``s``)
flags, and the three detail sections interleave across pages: a page can end
mid-cheque-grid and the next page resumes it under a ``- continued`` heading
after reprinting the whole address block. Sections are therefore gathered
globally (`_sections`) rather than sliced between a start and an end offset.

**The same statement also arrives scanned** (W3 §SCAN-A), and three of this
reader's assumptions were assumptions about the electronic PDF rather than
about the statement:

* the print stream's own header is furniture the *file* carries, not something
  the *page* prints, so a scan of the identical statement has no trace of it.
  The scan does print the issuer's product line — ``Account Type: 5/3 …`` — and
  either printing now satisfies the same marker;
* the electronic PDF flattens the whole account summary onto one line; the scan
  prints one component per line. The summary's middle span may therefore cross
  printed lines, **bounded**, so that a beginning balance can never be paired
  with an ending balance belonging to some later block;
* OCR speckle lands between a printed number and the token after it — a full
  stop welded to a component's count (``13. Deposits / Credits``), a stray
  glyph where a cheque flag was (``1229%i``). Both are tolerated only where a
  second printing of the same figure has to agree: the count against its own
  section heading, the cheque against the section total and the daily walk.
"""
from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_within_period
from .money import PARENS_OR_LEADING_MINUS, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction

#: The print stream's own header, reprinted at the top of every page:
#: ``FTCSTMT044 044 20260228 UDSPDFSTMT 0000000007921941766 DDA``. Shapes only —
#: the form number, the cycle date and the account are read as digit runs.
_PRINT_STREAM_RE = re.compile(
    r"FTCSTMT\d+\s+\d+\s+\d{8}\s+UDSPDFSTMT\s+\d+\s+[A-Z]+"
)

#: The product the statement itself names in its ``Account Type:`` field,
#: written in the issuer's own brand shorthand: ``Account Type: 5/3 BUSINESS
#: CKG``. Unlike the print-stream header this is *printed on the page*, so it
#: survives being scanned — which is the whole reason it is here.
#:
#: It is a weaker sentinel than the header it stands in for: ``5/3`` is also an
#: ordinary fraction and an ordinary date, so this pattern can fire on a rate
#: table or a schedule that happens to print an account-type column. That is
#: tolerable only because it is never asked to identify the issuer on its own —
#: ``issuer_domain`` is a separate *required* marker, and this one's false
#: positives are documents that do not carry Fifth Third's domain. Loosen the
#: domain marker and this pattern stops being safe.
_PRODUCT_LINE_RE = re.compile(r"ACCOUNT TYPE:\s*5/3\b")

#: `$(1,234.56)` / `$1,234.56` / `(1,234.56)` / `1,234.56`.
_MONEY = r"\$?\(?[\d,]+\.\d{2}\)?"

#: The three summary components, in printed order. Each is also the heading of
#: its own detail section, which is what makes instrument 2 possible.
_LABELS = ("Checks", "Withdrawals / Debits", "Deposits / Credits")
_LABEL_ALT = "|".join(re.escape(label) for label in _LABELS)

#: How far the summary's middle span may run. The electronic PDF flattens the
#: components onto one line and the scan prints one per line, so the span has to
#: cross printed lines — but it must not be free to run the length of the
#: document. The widest summary the archive prints is 140 characters, so this is
#: roughly three times the observed need.
#:
#: **What fences a foreign close is instrument 1, not this bound and not the
#: duplicate-label refusal below.** A document whose own ending-balance line is
#: lost — which is exactly what a scan does — lets this span reach a *later*
#: block's close in under 200 characters, with every component printed once and
#: no label repeated. `_summary` therefore returns a beginning balance paired
#: with someone else's ending balance, and returns it happily. The reading is
#: refused a few lines further on, where `beginning + deposits - checks -
#: withdrawals` is walked against that close and does not meet it.
#:
#: Instrument 4's terminal check is an independent second reading of the same
#: close, and measurement says either one alone is sufficient: delete instrument
#: 1 and the document is still refused, delete instrument 4's terminal check and
#: it is still refused, delete both and the foreign pairing publishes with
#: `ending_balance` 77,777.00. So widening this bound does not open the door the
#: duplicate-label refusal guards; it leans harder on the closing identity,
#: which is the thing to argue about.
_SUMMARY_SPAN = 400

_SUMMARY_RE = re.compile(
    r"(\d{2}/\d{2})\s+Beginning Balance\s+(" + _MONEY + r")\s+"
    r"Number of Days in Period\s+(\d+)\s+([\s\S]{0," + str(_SUMMARY_SPAN) + r"}?)"
    r"(\d{2}/\d{2})\s+Ending Balance\s+(" + _MONEY + r")"
)
#: ``13. Deposits / Credits`` — a scan welds a speck to the component's count.
#: The full stop is absorbed; the count itself is still read off this printing
#: and then has to agree with the section heading's independent printing of it,
#: so a misread count refuses the document rather than reaching a result.
_COMPONENT_RE = re.compile(
    r"(?:(\d+)\.?\s+)?(" + _LABEL_ALT + r")(?:\s+(" + _MONEY + r"))?"
)
_SECTION_HEAD_RE = re.compile(
    r"^(" + _LABEL_ALT + r")\s+(\d+)\s+(?:checks|items)\s+totaling\s+(" + _MONEY + r")",
    re.MULTILINE,
)

_PERIOD_RE = re.compile(
    r"Statement Period Date:\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*-\s*(\d{1,2})/(\d{1,2})/(\d{4})"
)
_ACCOUNT_RE = re.compile(r"Account Number:\s*(\d+)")
_ACCOUNT_TYPE_RE = re.compile(r"Account Type:\s*(.+?)\s+Account Number:")

_PAGE_RE = re.compile(r"^--- Page \d+")
_START_RE = re.compile(
    r"^(" + _LABEL_ALT + r")\s+\d+\s+(?:checks|items)\s+totaling\s+" + _MONEY + r"\s*(.*)$"
)
_CONTINUED_RE = re.compile(r"^(" + _LABEL_ALT + r")\s+- continued\s*(.*)$")
_DAILY_RE = re.compile(r"^Daily Balance Summary\s*(.*)$")

#: ``32099*i 02/02 894.33`` — number, optional sequence-gap and image flags,
#: posting date, amount. The flags are optional independently of each other,
#: and on a scan they are the least legible marks on the page: ``1229%i`` is a
#: sequence-gap asterisk the OCR read as a percent sign. What separates the
#: cheque number from its paid date is therefore *up to two glyphs that are
#: neither digits nor the date's own separator* — a shape, not a list of the
#: substitutions one OCR engine happens to make. Nothing is taken on trust: a
#: row admitted here still has to be corroborated by the section's printed
#: count, its printed total and the printed daily-balance walk.
_CHECK_ROW_RE = re.compile(
    r"(?<![\d.,])(\d{3,})(?:\s*[^\s\d/]){0,2}\s+(\d{1,2}/\d{2})\s+([\d,]+\.\d{2})(?![\d.,])"
)
#: ``02/02 50.00 DEBIT CARD PURCHASE AT ...`` — the description runs to the next
#: row's date, which is why rows are located first and sliced afterwards.
_ITEM_START_RE = re.compile(r"(?<![\d.,/])(\d{1,2}/\d{2})\s+([\d,]+\.\d{2})\s+(?=\S)")
_DAY_RE = re.compile(r"(?<![\d.,/])(\d{1,2}/\d{2})\s+(\(?[\d,]+\.\d{2}\)?)(?![\d.,])")

_TOLERANCE = 0.005


def _money(value: str | None) -> float | None:
    return parse_amount(value, PARENS_OR_LEADING_MINUS)


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


DETECTION_MARKERS = (
    # The statement's own print product, in whichever of its two printings the
    # document in hand carries. The print-stream header line is template
    # furniture no other issuer's document carries — but it belongs to the
    # electronic PDF, and a SCAN of the identical statement cannot have it. What
    # the scan does have is the product named in the statement's own
    # `Account Type:` field, in the issuer's brand shorthand. Nine of the
    # thirteen electronic documents print both; the four that do not print a
    # `5/3` product name are held by the print stream, and the scans are held by
    # the product line, so neither branch is redundant.
    required(
        "print_product",
        lambda t: _PRINT_STREAM_RE.search(t) is not None
        or _PRODUCT_LINE_RE.search(t) is not None,
    ),
    # The issuer, read off the document rather than off the folder it was filed
    # in: every page footer carries Fifth Third's own domain. The bank's name is
    # spelled out on only one document of the family, so the domain is what
    # makes the identification hold across all of them.
    required("issuer_domain", lambda t: "53.COM" in t),
    required("summary_block", lambda t: "ACCOUNT SUMMARY" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def _sections(markdown: str) -> dict[str, str]:
    """Each detail section's text, gathered across every page it appears on.

    A page boundary closes whatever section was open, because a section that
    continues onto the next page always reprints its own `- continued` heading
    there. That makes the reprinted address block, the flag legend and the page
    footer structurally unable to leak into a section, without this function
    needing to know what any of them look like.
    """
    gathered: dict[str, list[str]] = {label: [] for label in (*_LABELS, "Daily")}
    current: str | None = None
    for line in markdown.splitlines():
        line = line.rstrip()
        if _PAGE_RE.match(line):
            current = None
            continue
        head = _START_RE.match(line) or _CONTINUED_RE.match(line)
        if head:
            current = head.group(1)
            if head.group(2):
                gathered[current].append(head.group(2))
            continue
        daily = _DAILY_RE.match(line)
        if daily:
            current = "Daily"
            if daily.group(1):
                gathered["Daily"].append(daily.group(1))
            continue
        if current is not None:
            gathered[current].append(line)
    return {label: " ".join(lines) for label, lines in gathered.items()}


def _summary(markdown: str):
    """`(beginning, days, ending, components)` or None.

    `components` maps each printed label to `(count, amount)`, either of which
    is None when the document did not print it.
    """
    m = _SUMMARY_RE.search(markdown)
    if not m:
        return None
    _, beginning, days, middle, _, ending = m.groups()
    components: dict[str, tuple[int | None, float | None]] = {}
    for count, label, amount in _COMPONENT_RE.findall(middle):
        if label in components:
            return None  # a component printed twice is not a summary we can read
        components[label] = (
            int(count) if count else None,
            _money(amount) if amount else None,
        )
    begin = _money(beginning)
    close = _money(ending)
    if begin is None or close is None or set(components) - set(_LABELS):
        return None
    return begin, int(days), close, components


def _section_heads(markdown: str) -> dict[str, tuple[int, float]]:
    heads: dict[str, tuple[int, float]] = {}
    for label, count, total in _SECTION_HEAD_RE.findall(markdown):
        amount = _money(total)
        if amount is None or label in heads:
            return {}
        heads[label] = (int(count), abs(amount))
    return heads



def _item_rows(text: str) -> list[tuple[str, float, str]]:
    """Split a flattened `MM/DD AMOUNT DESCRIPTION` run into its rows."""
    starts = [
        (m.start(), m.group(1), float(m.group(2).replace(",", "")), m.end())
        for m in _ITEM_START_RE.finditer(text)
    ]
    rows = []
    for index, (_, token, amount, after) in enumerate(starts):
        stop = starts[index + 1][0] if index + 1 < len(starts) else len(text)
        rows.append((token, amount, re.sub(r"\s+", " ", text[after:stop]).strip()))
    return rows


def _agrees(count: int, total: float, printed: tuple[int, float] | None) -> bool:
    return (
        printed is not None
        and count == printed[0]
        and abs(total - printed[1]) <= _TOLERANCE
    )


def parse_fifth_third_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _PERIOD_RE.search(markdown)
    account = _ACCOUNT_RE.search(markdown)
    summary = _summary(markdown)
    if period is None or account is None or summary is None:
        return None
    beginning, days, ending, components = summary

    start_month, start_day, start_year, end_month, end_day, end_year = (
        int(part) for part in period.groups()
    )
    try:
        start = date(start_year, start_month, start_day)
        end = date(end_year, end_month, end_day)
    except ValueError:
        return None
    if end < start:
        return None

    checks_count, checks_total = components.get("Checks", (None, None))
    debit_count, debit_total = components.get("Withdrawals / Debits", (None, None))
    credit_count, credit_total = components.get("Deposits / Credits", (None, None))

    # Instrument 1 — the three-component closing identity.
    walked = (
        beginning
        + abs(credit_total or 0.0)
        - abs(checks_total or 0.0)
        - abs(debit_total or 0.0)
    )
    if abs(walked - ending) > _TOLERANCE:
        return None

    # Instrument 2 — each component reprinted at the head of its own section,
    # including agreeing about a component the summary says is absent.
    heads = _section_heads(markdown)
    for label in _LABELS:
        printed_count, printed_amount = components.get(label, (None, None))
        if (label in heads) != (printed_amount is not None):
            return None
        if label not in heads:
            continue
        # An amount with no count beside it is a summary we cannot read, not a
        # summary we may complete from the section heading.
        if printed_count is None:
            return None
        if not _agrees(printed_count, abs(printed_amount), heads[label]):
            return None

    sections = _sections(markdown)
    transactions: list[Transaction] = []

    # Instrument 3 — the rows read out of each section against its own heading.
    cheques = [
        (m.group(1), m.group(2), float(m.group(3).replace(",", "")))
        for m in _CHECK_ROW_RE.finditer(sections["Checks"])
    ]
    if not _agrees(
        len(cheques), sum(amount for _, _, amount in cheques),
        heads.get("Checks", (0, 0.0) if checks_total is None else None),
    ):
        return None
    for number, token, amount in cheques:
        posted = iso_within_period(token, start, end)
        if posted is None:
            return None
        transactions.append(
            Transaction(
                date=posted,
                description=f"Check {number}",
                amount=-amount,
                direction="debit",
            )
        )

    for label, sign in (("Withdrawals / Debits", -1), ("Deposits / Credits", 1)):
        rows = _item_rows(sections[label])
        stated = components.get(label, (None, None))[1]
        if not _agrees(
            len(rows), sum(amount for _, amount, _ in rows),
            heads.get(label, (0, 0.0) if stated is None else None),
        ):
            return None
        for token, amount, description in rows:
            posted = iso_within_period(token, start, end)
            if posted is None or not description:
                return None
            transactions.append(
                Transaction(
                    date=posted,
                    description=description,
                    amount=sign * amount,
                    direction="credit" if sign > 0 else "debit",
                )
            )

    if not transactions:
        return None

    # Instrument 4 — the day-by-day walk against the printed daily balances.
    printed_days: list[tuple[str, float]] = []
    for m in _DAY_RE.finditer(sections["Daily"]):
        posted = iso_within_period(m.group(1), start, end)
        balance = _money(m.group(2))
        if posted is None or balance is None:
            return None
        printed_days.append((posted, balance))
    if not printed_days or len(printed_days) != len({d for d, _ in printed_days}):
        return None
    by_day = dict(printed_days)

    moves: dict[str, float] = {}
    for txn in transactions:
        moves[txn.date] = round(moves.get(txn.date, 0.0) + txn.amount, 2)
    running = beginning
    for posted in sorted(moves):
        running = round(running + moves[posted], 2)
        if posted not in by_day or abs(by_day[posted] - running) > _TOLERANCE:
            return None
    if abs(running - ending) > _TOLERANCE:
        return None

    account_type = _ACCOUNT_TYPE_RE.search(markdown)
    transactions.sort(key=lambda txn: txn.date)
    return Statement(
        bank="Fifth Third Bank",
        account_name=account_type.group(1).strip() if account_type else None,
        account_number=account.group(1),
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        days_in_period=days,
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=abs(credit_total or 0.0),
        stated_total_debits=abs(checks_total or 0.0) + abs(debit_total or 0.0),
        stated_credit_count=credit_count or 0,
        stated_debit_count=(checks_count or 0) + (debit_count or 0),
        stated_daily_balances=[
            StatementDailyBalance(date=posted, balance=balance)
            for posted, balance in printed_days
        ],
        transactions=transactions,
    )
