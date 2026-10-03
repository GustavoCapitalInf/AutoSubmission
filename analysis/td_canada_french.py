"""Deterministic parser for TD Canada Trust's French (Quebec) printed layout.

Physically this is the same grid `analysis/td_can.py` reads on the native
English statement — five columns, one printed row per physical line, and a
running balance printed at the end of each date group — issued in French:

    DESCRIPTION RETRAITS DEPOTS DATE SOLDE
    SOLDE REPORTE                      30JAN        310,39
    DEP MC 13463815 DIV        57,93   02FEV
    ...
    FRA INT13463815 DIV        81,80   02FEV      1 640,44

with day-first date tokens (`02FEV`), FR-CA money (space thousands, comma
decimal mark: `1 640,44`), a `DC` suffix where the English layout prints a
minus sign, per-page `Credits <n> <total>` / `Debits <n> <total>` footers, and
the issuer line `Comptes emis par : LA BANQUE TORONTO-DOMINION`.

Because the grid is the same, the missing column is recovered the same way. The
text layer collapses RETRAITS and DEPOTS into one token, so which of the two
money columns an amount was printed in does not survive; it is read back out of
the balance the bank itself prints at the end of each date group. That
arithmetic is `td_can`'s and is consumed here unchanged — this module owns the
French *reading* of the grid, never a second copy of the solver.

It is registered in its own right rather than folded into `td_can` because
detection is the point: the English markers cannot fire on these documents and
the French markers cannot fire on an English one, so the two layouts are
disjoint document classes that happen to share their arithmetic.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import NamedTuple

from .dates import resolve_year
from .holder_name import PROVINCE_POSTAL_CODE, mailing_line_after
from .money import parse_french_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

# The balance-column reading of a date group, consumed as it stands. It reads
# only `.amount` (absolute cents) and `.description` off the rows handed to it
# and takes this issue's code readers as arguments, which is the whole of the
# contract `_FrenchRow` and this module satisfy. It used to be two imports --
# the solver and its equal-amount tie-break, orchestrated again here -- and the
# second copy of the orchestration is what let the two issues drift (W3
# §WITHHELDTD). Written on one line on purpose: the private-import guard in
# tests/test_no_parser_helper_clones.py reads `from .x import ...` line by
# line, and a parenthesised import would hide this dependency from it.
from .td_can import _resolve_directions_from_balances, normalize_mojibake

#: Audit round 2, R2-B05 (R04 part 2): TD Canada Trust's mail-routing code line on page 1 ('TDCDA00000_0000000_000
#: F R 00000 00000'), which the holder's name and mailing address follow on the next line, as on the English layout.
_MAIL_ROUTING_LINE = re.compile(r"^TDCDA\d+_\d+_\d+\b")


def _holder_name(markdown: str) -> str | None:
    """Audit round 2, R2-B05 (R04 part 2): page 1's block after the mail-routing code: the holder's name before its
    address (a numbered company keeps its number), read when the line closes on a province and postal code; None
    otherwise. The English reader's anchor (td_can._holder_name), read on this issue's page 1."""
    return mailing_line_after(normalize_mojibake(markdown), _MAIL_ROUTING_LINE, PROVINCE_POSTAL_CODE)


#: TD prints this statement's month tokens as three unaccented letters in every
#: document measured, but the accented spellings are the correct French
#: abbreviations and cost nothing to accept: these keys are compared after
#: `_fold`, which removes the accent either way.
_FR_MONTHS = {
    "JAN": 1, "FEV": 2, "MAR": 3, "AVR": 4, "MAI": 5, "JUN": 6,
    "JUL": 7, "AOU": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
_FR_MONTH_ALT = "|".join(_FR_MONTHS)

#: `30 JAN 26 - 27 FEV 26`, printed beside the account number in the page head.
_PERIOD_RE = re.compile(
    rf"\b(\d{{1,2}}) ({_FR_MONTH_ALT}) (\d{{2}}) - (\d{{1,2}}) ({_FR_MONTH_ALT}) (\d{{2}})\b"
)
#: A row's DATE cell: day first, no separator (`02FEV`).
_DATE_TOKEN_RE = re.compile(rf"(\d{{1,2}})({_FR_MONTH_ALT})")
#: The last token of an FR-CA amount, with TD's overdrawn suffix. The integer
#: part is capped at three digits because a longer run is not a French money
#: group at all, and `_amount_ending_at` needs its length to decide whether
#: anything may legitimately sit to its left.
_AMOUNT_TAIL_RE = re.compile(r"(\d{1,3}),(\d{2})(DC)?")
_THOUSANDS_GROUP_RE = re.compile(r"\d{3}")
#: Only the groups AFTER the first are zero-padded to three digits. The leading
#: group carries no padding — `1 007 100,00`, never `007 100,00` — so a token
#: that opens with a zero is not a leading group.
_LEADING_GROUP_RE = re.compile(r"[1-9]\d{0,2}")

#: The page head that carries the account number. Read only from this line: a
#: ledger row can print another account of the same customer inside its
#: description (`SGE A: 4440-5347895 207,21 12MAI`), and a bare
#: branch-and-account regex over the whole document takes that for the
#: statement's own account.
_ACCOUNT_HEAD_RE = re.compile(r"^\d{4} (\d{4}-\d{6,}) PAGE \d+ DE \d+$")

#: The printed grid header opens the ledger, on every page.
_LEDGER_HEADER = "DESCRIPTION RETRAITS DEPOTS DATE SOLDE"
#: ...and the cheque-enclosure line closes it. Its leading token is the number
#: of cheques in the envelope, which is statement data, so it cannot be part of
#: the marker — the English side learned this: matching a literal count kept
#: the ledger open past the end of every page that encloses one.
_CHQS_JOINTS_RE = re.compile(r"^\d+ CHQS? JOINTS\b")
#: The per-page direction footers, and the printed monthly average balance.
_PAGE_TOTAL_RE = re.compile(r"^(CREDITS|DEBITS) (\d+) (\d[\d ]*,\d{2})$")
_AVERAGE_BALANCE_RE = re.compile(r"^SOLDE CREDITEUR MENS MOYEN (\d[\d ]*,\d{2})(DC)?")
#: The carried balance, reprinted at the top of every page's grid.
_CARRIED_BALANCE = "SOLDE REPORTE"


def _fold(text: str) -> str:
    """Accent-insensitive upper case.

    The furniture this parser matches on is printed unaccented (`SOLDE
    REPORTE`, `DEPOTS`) while the prose around it is not (`Releve de compte`,
    `Credits`), and an OCR pass can restore an accent the native text layer
    dropped. Folding keeps every marker and every pattern below written in
    plain ASCII rather than as a list of spellings.

    What that guarantees, precisely: an unaccented document and an accented one
    fold alike, and so does one whose accents are UNIFORMLY double-encoded,
    because `td_can.normalize_mojibake` reverses the whole text before this
    runs. Mixed content is not guaranteed. There the whole-text reversal fails
    and the fallback is `td_can._MOJIBAKE_TABLE`, which is not exhaustive — an
    upper-case O-circumflex has no entry, so a double-encoded `DEPOTS` sitting
    beside one clean accent folds to text the markers miss. That fails closed,
    to a decline rather than a wrong parse, and it is unreachable on this
    family: every document measured prints its grid header and issuer line
    without accents. The table gap is `td_can`'s and is recorded separately.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).upper()


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return _fold(normalize_mojibake(markdown))


DETECTION_MARKERS = (
    # Issuer furniture only. The grid header is the bank's own column legend and
    # the issuer line is the statement's own footer; neither is a customer name,
    # a filename, or a counterparty another bank could print in a ledger row.
    # The bank name alone is deliberately NOT a marker.
    required("french_ledger_header", lambda t: _LEDGER_HEADER in t),
    required(
        "french_issuer_line",
        lambda t: "COMPTES EMIS PAR : LA BANQUE TORONTO-DOMINION" in t,
    ),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


class _FrenchRow(NamedTuple):
    """One flattened ledger row.

    `amount` is the absolute value in cents so the balance arithmetic is exact,
    and `description` is what the equal-amount tie-break reads. Those two
    fields are the whole of the contract `_directions_from_credit_counts`
    depends on.
    """

    date: str
    description: str
    amount: int
    balance: float | None


class _Amount(NamedTuple):
    """A parsed FR-CA amount and the token index it starts at."""

    value: float
    overdrawn: bool
    start: int


def _cents(value: float) -> int:
    return int(round(value * 100))


def _amount_ending_at(tokens: list[str], index: int) -> _Amount | None:
    """The FR-CA amount whose LAST token is ``tokens[index]``, or None.

    French Canadian money separates thousands with a space, so one printed
    amount arrives as several whitespace tokens: `1 640,44` is
    ``["1", "640,44"]`` and `10 034,67` is ``["10", "034,67"]``. The grammar is
    a leader of one to three digits, then any number of three-digit groups,
    then the group carrying the decimal mark.

    That grammar collides with TD's descriptions, which end in digits often
    enough to matter (`CHQ#00083-1149169334`, `UO342 TFR-A 5347895`). The
    collision is only possible when the decimal group's integer part is exactly
    three digits: `145,55` can continue `30 145,55`, but `40,00` and `5,00`
    cannot continue anything, because a French thousands group is always padded
    to three digits. A token to the left is therefore absorbed **only** in that
    case, and never otherwise.

    It remains a real ambiguity even then. `PETRO-CANADA 30 145,55` is both
    "30 145,55" and "145,55, posted by PETRO-CANADA 30", and no rule reading a
    single line can separate them. This takes the French reading, which is what
    the bank's own money format says, and leaves the other outcome to the
    balance chain: a wrongly joined amount cannot satisfy the balance the bank
    printed at the end of its group, so the group goes unsolved, the printed
    totals then disagree, and the document is withheld rather than published
    wrong.
    """
    tail = _AMOUNT_TAIL_RE.fullmatch(tokens[index])
    if not tail:
        return None
    start = index
    if len(tail.group(1)) == 3:
        while start - 1 >= 0 and _THOUSANDS_GROUP_RE.fullmatch(tokens[start - 1]):
            start -= 1
        if start - 1 >= 0 and _LEADING_GROUP_RE.fullmatch(tokens[start - 1]):
            start -= 1
        # Whatever the two rules above absorbed, the group the number now opens
        # with must be a leading group, and a leading group is never padded.
        # `FACTURE 007 100,00` is an invoice number printed beside an amount,
        # not 7 100,00, so the padded token goes back to the description.
        # `_LEADING_GROUP_RE` cannot express this on its own: `007` is three
        # digits, so the thousands loop takes it and it never reaches the
        # leader test. Absorption stops rather than the amount being rejected —
        # `100,00` is still an amount, it simply starts one token later.
        while start < index and tokens[start].startswith("0"):
            start += 1
    joined = " ".join(tokens[start:index + 1])
    if tail.group(3):
        joined = joined[:-len(tail.group(3))]
    return _Amount(parse_french_amount(joined), bool(tail.group(3)), start)


def _period(text: str) -> tuple[date, date] | None:
    m = _PERIOD_RE.search(text)
    if not m:
        return None
    start_day, start_month, start_year, end_day, end_month, end_year = m.groups()
    try:
        start = date(2000 + int(start_year), _FR_MONTHS[start_month], int(start_day))
        end = date(2000 + int(end_year), _FR_MONTHS[end_month], int(end_day))
    except ValueError:
        return None
    return (start, end) if start <= end else None


def _date_index(tokens: list[str]) -> int | None:
    """Where the DATE column lands inside a flattened ledger line.

    TD prints DATE between the two money columns and the SOLDE column, so —
    exactly as on the English grid — a row's date token does not open its
    physical line.
    """
    return next((i for i, token in enumerate(tokens) if _DATE_TOKEN_RE.fullmatch(token)), None)


def _row_date(token: str, period_start: date, period_end: date) -> str | None:
    """The ISO date for a `02FEV` cell, given the printed statement period.

    The bank prints no year on a ledger row and these periods cross the turn of
    the year (`31 DEC 25 - 30 JAN 26`), so the year is the one that places the
    printed day inside the printed period — the shared rule in `analysis/
    dates.py`, not a per-parser guess.
    """
    m = _DATE_TOKEN_RE.fullmatch(token)
    if not m:
        return None
    month = _FR_MONTHS[m.group(2)]
    day = int(m.group(1))
    year = resolve_year(month, day, period_start, period_end)
    if year is None:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


#: TD's own French transaction codes, and what the printed balance column says
#: each one is. The counts are over the 229 date groups of the 13 corpus
#: documents whose amounts are all distinct — where a group repeats an amount
#: the arithmetic cannot say which row is the deposit, so a label taken from
#: one would be an artifact of the tie-break rather than evidence:
#:
#:   DEP / DEPOT       depot                                200 credits,   0 debits
#:   TP<nnnn>          terminal settlement posting           82 credits,   0 debits
#:   RECEPT - VFC      reception d'un virement Interac       80 credits,   0 debits
#:   TFR-DE            transfert DE un autre compte          24 credits,   0 debits
#:   CREDIT D'INTERET  interet porte au credit                3 credits,   0 debits
#:   ENVOI             envoi d'un virement Interac            0 credits, 119 debits
#:   TFR-A             transfert A un autre compte            0 credits,  28 debits
#:
#: Structural codes only, never a counterparty name (R-1 item 8). The merchant
#: settlement codes are exactly why: over the same groups the balances make
#: `MRCH…` 53 credits against 42 debits and `ELAVON` 7 against 14, so a rule
#: keyed on either name would be wrong about half the time. The two debit
#: entries restate the default and so cannot move any outcome; they are written
#: down because TD prints each of them as one half of a pair, and a reader
#: checking the reading of `TFR-DE` should find `TFR-A` beside it. This mirrors
#: `td_can._native_credit_like`, which reads the English issue of the same
#: codes (`TFR-FR`/`TFR-TO`, `E-TRANSFER`/`SEND E-TFR`).
_FRENCH_DIRECTION_CODES = (
    (re.compile(r"TFR-DE\b"), True),
    (re.compile(r"TFR-A "), False),
    (re.compile(r"^RECEPT ?- ?VFC\b"), True),
    (re.compile(r"^ENVOI"), False),
    (re.compile(r"^DEP(OT)? "), True),
    (re.compile(r"^TP\d+\b"), True),
    (re.compile(r"^CREDIT D['\u2019]?\s?INTERET\b"), True),
)


def _french_direction_code(description: str) -> bool | None:
    """What TD's own French code says this row is, or None if it says nothing.

    The three-valued twin of `td_can._native_direction_code`, and for the same
    reason: `ENVOI` and `TFR-A ` are the bank stating a withdrawal, while a row
    matching no pattern above is the bank stating nothing, and the two are
    different evidence when the printed balances admit more than one split.
    """
    text = _fold(description)
    for pattern, is_credit in _FRENCH_DIRECTION_CODES:
        if pattern.search(text):
            return is_credit
    return None


def _french_credit_like(description: str) -> bool:
    """Sign from TD's own French transaction codes, never a counterparty name."""
    return _french_direction_code(description) is True


def _resolve_directions(
    rows: list[_FrenchRow],
    groups: list[tuple[list[int], float]],
    opening: float | None,
) -> list[bool]:
    """One `is credit` flag per row, from the printed SOLDE column.

    The printed balances decide, wherever they decide anything: a group they
    determine has every one of its rows overwritten by the arithmetic, and the
    transaction codes cannot override the document. They are the reading that
    remains for a group the balances leave underdetermined — the same division
    of labour, and the same precedence, as `td_can._resolve_native_directions`
    on the English grid.

    Reconciliation against the bank's own stated credit and debit totals —
    evidence neither the solver nor the codes ever see — stays the gate over
    the whole result, so a code that reads a row wrongly costs the document its
    publication rather than publishing a wrong number.

    The division of labour is `td_can`'s and is consumed here rather than
    restated: this function supplies the FRENCH readers of TD's codes and
    nothing else. Passing them is not cosmetic — the shared equal-amount
    tie-break used to score French descriptions with the ENGLISH code table,
    on which they match almost nothing (W3 §WITHHELDTD).
    """
    return _resolve_directions_from_balances(
        rows,
        groups,
        opening,
        direction_code=_french_direction_code,
        credit_like=_french_credit_like,
    )


def parse_td_canada_french_statement(
    markdown: str, base: Statement | None = None
) -> Statement | None:
    if not detect(markdown).claims:
        return None
    source = normalize_mojibake(markdown)
    period = _period(_fold(source))
    if period is None:
        # Rows cannot be dated without the printed period, and a statement year
        # is never assumed (R-1 items 8/9).
        return None
    period_start, period_end = period

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "TD Canada Trust"
    stmt.holder_name = _holder_name(markdown) or stmt.holder_name
    stmt.currency = "CAD"
    stmt.currency_source = "institution_default"
    stmt.period_start = period_start.isoformat()
    stmt.period_end = period_end.isoformat()
    stmt.beginning_balance = None
    stmt.ending_balance = None
    stmt.stated_total_credits = None
    stmt.stated_total_debits = None
    stmt.stated_credit_count = None
    stmt.stated_debit_count = None
    stmt.bank_reported_average_balance = None
    stmt.bank_reported_average_label = None

    rows: list[_FrenchRow] = []
    #: (row indices, the balance printed at the end of those rows).
    groups: list[tuple[list[int], float]] = []
    pending: list[int] = []
    ending_balance: float | None = None
    in_ledger = False

    for raw in source.splitlines():
        printed = raw.split()
        if not printed:
            continue
        # Folded token by token, so the folded and the printed line always have
        # the same number of tokens and a description can keep the case and the
        # accents the bank printed while the matching stays ASCII.
        tokens = [_fold(token) for token in printed]
        line = " ".join(tokens)

        account = _ACCOUNT_HEAD_RE.match(line)
        if account:
            stmt.account_number = account.group(1)
        average = _AVERAGE_BALANCE_RE.match(line)
        if average and stmt.bank_reported_average_balance is None:
            # Reprinted identically on every page, so the first reading is the
            # figure; accumulating it would multiply it by the page count.
            value = parse_french_amount(average.group(1))
            stmt.bank_reported_average_balance = -value if average.group(2) else value
            # The heading as PRINTED - `line` is the ASCII-folded copy the
            # matching runs on, `printed` still carries the bank's accents.
            stmt.bank_reported_average_label = " ".join(printed[:4])
        totals = _PAGE_TOTAL_RE.match(line)
        if totals:
            # Printed per page, so these DO accumulate. The count is the first
            # token after the label and the amount is everything after it, so
            # the two cannot be confused with one another however wide either
            # grows — which is what makes `Debits 18 924,29` eighteen rows
            # totalling 924.29 rather than one totalling 18,924.29.
            count = int(totals.group(2))
            amount = parse_french_amount(totals.group(3))
            if totals.group(1) == "CREDITS":
                stmt.stated_credit_count = (stmt.stated_credit_count or 0) + count
                stmt.stated_total_credits = round((stmt.stated_total_credits or 0.0) + amount, 2)
            else:
                stmt.stated_debit_count = (stmt.stated_debit_count or 0) + count
                stmt.stated_total_debits = round((stmt.stated_total_debits or 0.0) + amount, 2)

        if line.startswith(_LEDGER_HEADER):
            in_ledger = True
            continue
        if in_ledger and _CHQS_JOINTS_RE.match(line):
            in_ledger = False
            continue
        if not in_ledger:
            continue

        date_index = _date_index(tokens)
        if date_index is None:
            # Page-tracking furniture and the `No. Montant` cheque legend sit
            # inside the printed grid and carry no DATE cell.
            continue

        balance = None
        if date_index + 1 < len(tokens):
            closing = _amount_ending_at(tokens, len(tokens) - 1)
            if closing is not None and closing.start > date_index:
                balance = -closing.value if closing.overdrawn else closing.value

        if line.startswith(_CARRIED_BALANCE):
            if balance is None:
                continue
            if stmt.beginning_balance is None:
                stmt.beginning_balance = balance
            elif pending:
                # A page break can split a date group before its balance is
                # printed; the next page reprints the carried balance, which
                # closes the group the previous page ended inside.
                groups.append((pending, balance))
                pending = []
            continue

        amount = None
        for i in range(date_index - 1, -1, -1):
            amount = _amount_ending_at(tokens, i)
            if amount is not None:
                break
        if amount is None:
            continue
        description = " ".join(printed[:amount.start]).strip()
        if not description:
            continue
        row_date = _row_date(tokens[date_index], period_start, period_end)
        if row_date is None:
            continue

        rows.append(_FrenchRow(row_date, description, _cents(amount.value), balance))
        pending.append(len(rows) - 1)
        if balance is not None:
            groups.append((pending, balance))
            pending = []
            ending_balance = balance

    if not rows:
        return None

    credits = _resolve_directions(rows, groups, stmt.beginning_balance)
    stmt.transactions = [
        Transaction(
            date=row.date,
            description=row.description,
            amount=round(row.amount / 100 if is_credit else -row.amount / 100, 2),
            direction="credit" if is_credit else "debit",
            running_balance=None,
        )
        for row, is_credit in zip(rows, credits)
    ]
    stmt.ending_balance = ending_balance
    return stmt
