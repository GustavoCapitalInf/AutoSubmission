"""A French-language account-statement template, registered without an issuer.

W3 §UNID-B UB5 asked for a French extension of `analysis/desjardins.py` and
found that the premise did not hold: the 16 documents its three structural
hints describe **name no institution anywhere**. This module is the ruling
(Gustavo, 2026-08-14) applied to them - the template is registered on its own
printed furniture, and `Statement.bank` is published as `None`.

**What the documents actually print, measured over all 16.** The only words in
them that name a financial institution are transaction counterparties and one
piece of boilerplate:

* ``COMPTE DIVERS FED DESJARDINS`` - a ledger row, in 6 of the 16. It is a
  payment the customer MADE. The archive folder label says "Desjardins" on 6
  documents and this row appears in 6, but they are not the same 6, and one
  document filed under `Desjardins/` contains the word nowhere at all.
* ``PRET RBC LOAN PYMT`` and ``PRET PMT PRET TD`` - loan payments, likewise.
* ``LA BANQUE DOIT ETRE AVISEE PAR ECRIT ...`` - the per-page footer, which
  calls the issuer *the Bank* and never names it. This is the whole of what
  the template says about who issued it.

The masthead prints a street address, a phone number, a branch number
(``No succursale``) and an account number. No name. So the honest published
issuer is nothing at all: naming one from the folder label would be the
failure mode `tests/test_parser_detection_markers.py` exists to prevent, and
`analysis/desjardins.py` - which reads a genuinely different layout, in a
different money grammar, from a different PDF producer - stays untouched.

**Parser identity and issuer identity are separate facts.** This registration
knows a printed grid; it does not know a bank. Its registry `bank` label names
the TEMPLATE for the same reason `community_section`'s names a platform, and
`Statement.bank` stays `None` on every document it publishes.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from .money import normalize_sign_glyphs, parse_french_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import compact_whitespace
from .td_can import normalize_mojibake


def _fold(text: str) -> str:
    """Upper-case, accent-folded, mojibake-repaired, ASCII-minus text.

    Every read in this module works on this one normalization, so the patterns
    below can be written in plain ASCII (`DEBIT`, not `DÉBIT`) and still match
    a document however its accents survived extraction. `normalize_mojibake`
    also rewrites NBSP to a plain space, which this template needs more than
    most: its thousands separator IS a space, and an NBSP there would make
    every amount unreadable.
    """
    repaired = normalize_sign_glyphs(normalize_mojibake(text))
    # The accent fold is a per-character Python loop, and a full registry
    # sweep runs this over every one of ~3,500 discovery documents. Almost all
    # of them are ASCII, where NFKD is the identity and no character combines,
    # so the fold is exactly `.upper()` there and `str.isascii` (a C-level
    # flag check) is what says so. Same answer, and the sweep budget this
    # wave is watching does not pay for a French reader on English documents.
    if repaired.isascii():
        return repaired.upper()
    decomposed = unicodedata.normalize("NFKD", repaired)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).upper()


detection_text = _fold

# ---------------------------------------------------------------------------
# The money grammar
# ---------------------------------------------------------------------------
#
#: FR-CA money: a space thousands separator and a comma decimal mark.
#:
#: The two lookarounds are load-bearing rather than tidy. Without the LEFT one
#: this pattern reads a reference number's tail as a thousands group: the row
#: `TRF DT INTERNET D77100000001337 150,00 3 983,75` offers `...1337 150,00`,
#: which matches `\d{1,3}( \d{3})*,\d{2}` as `337 150,00` - a $337,150 debit
#: invented out of a document number. That single missing boundary is what
#: made 10 of these 16 documents look chain-broken; with it, 4 remained, and
#: those 4 are the genuine ambiguity `_amount_from_chain` resolves. The RIGHT
#: one keeps the two decimals from being the head of a longer digit run.
_MONEY = r"(?<!\d)(?:\d{1,3}(?: \d{3})*|\d+),\d{2}(?!\d)"

#: A figure with the template's DETACHED minus: an overdrawn balance prints
#: its sign as its own token, `- 511,82`. Only the SOLDE column is ever
#: signed - the two money columns are magnitudes whose direction is the column
#: they were printed in - so the sign is read off the balance alone and an
#: amount's leading hyphen (`ESSO COUCHE -TA 100,00`) is description text.
_SIGNED_MONEY_RE = re.compile(r"(-\s*)?(" + _MONEY + r")")


def _money(token: str) -> float | None:
    try:
        return parse_french_amount(token)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# The template's furniture
# ---------------------------------------------------------------------------

#: The ledger's column header, reprinted at the top of every page.
_GRID_RE = re.compile(r"MM JJ DESCRIPTION DEBIT \(\$\) CREDIT \(\$\) SOLDE \(\$\)")

#: The fee table that terminates the ledger. Matched as two words: the single
#: word `FACTURATION` is also a transaction description on these documents
#: (`COMPTE A PAYER FACTURATION EDI`, `FACTURATION MENSUELLE`), so the one-word
#: form would end the ledger in the middle of it.
_FEE_TABLE_RE = re.compile(r"FACTURATION DETAILLEE")

#: The in-document ORACLE, printed under the fee table: how many transactions
#: the bank counted on each side and what each side totalled. Four figures, all
#: four independent of anything this reader derives, which is what makes a
#: published statement here checked rather than merely parsed.
#:
#: The count and the total are separated only by a space, and the total's own
#: thousands separator is a space too, so `201 180 837,79` could in principle
#: be read as count 201180 / total 837,79. It cannot be, because `_MONEY`
#: requires the decimal comma: the total is anchored on its `,79` and the
#: count is whatever integer precedes it. (Measured: no count in the archive
#: family reaches four digits, where the two readings would compete.)
_ORACLE_RE = re.compile(
    r"TRANSACTIONS DEBIT (\d+) (" + _MONEY + r") CREDIT (\d+) (" + _MONEY + r")"
)

_PERIOD_RE = re.compile(r"PERIODE DU (\d{2})-(\d{2})-(\d{4}) AU (\d{2})-(\d{2})-(\d{4})")
_ACCOUNT_RE = re.compile(r"NO DE COMPTE ([\d-]+)")

#: The account's own product name, printed in the header block. It carries the
#: currency: this template's issuers distinguish a Canadian-dollar chequing
#: account from a US-dollar one by this word and by nothing else on the page.
_PRODUCT_RE = re.compile(r"COMPTE : (COMPTE COURANT CANADIEN)\b")

#: Page furniture to remove before the ledger is read, each named by its own
#: printed shape. The footer is the notice every page ends with; the rest is
#: the header block the template reprints above every continuation grid.
_PAGE_FURNITURE_RE = re.compile(
    r"VEUILLEZ VERIFIER CE RELEVE SANS DELAI\..*?JOURS\."
    r"|--- PAGE \d+(?: \(EMPTY\))? ---"
    r"|MM JJ DESCRIPTION DEBIT \(\$\) CREDIT \(\$\) SOLDE \(\$\)"
    r"|RELEVE DE COMPTE"
    r"|PERIODE DU \d{2}-\d{2}-\d{4} AU \d{2}-\d{2}-\d{4} PAGE \d+ DE \d+"
    r"|NO DE COMPTE [\d-]+ NO SUCCURSALE \d+"
)

#: Where a ledger row begins: the `MM JJ` date pair.
#:
#: The pair is a digit group, a space and another digit group - which is also
#: exactly the shape of a space-thousands amount, so an unanchored matcher
#: fires inside one. The real collision in this archive is at the seam between
#: two figures: `... 2M7FINANCIALSOL 640,00 20 490,64 04 10 DPA ...` contains
#: `00 20`, a perfectly well-formed date pair sitting across an amount and the
#: balance beside it.
#:
#: The anchor is a FOLLOWING CAPITAL. After a real date pair comes the first
#: word of the description, and every description on this template starts with
#: a letter (`COMPTE`, `DPA`, `TRF`, `G/DEPOT`, `C/ACHAT`, `CHEQUE`,
#: `SOLDE`...); after a false pair comes the rest of a number. The left
#: lookbehind rejects a pair that starts mid-digit-run.
_ROW_RE = re.compile(r"(?<!\d)(\d{2}) (\d{2}) (?=[A-Z])")

#: The ledger's opening bookend: the closing balance of the previous period,
#: dated the last day of it. It carries one figure and is not a posting.
_OPENING_LABEL = "SOLDE PRECEDENT"


DETECTION_MARKERS = (
    required("ledger_grid", lambda t: bool(_GRID_RE.search(t))),
    required("fee_table", lambda t: bool(_FEE_TABLE_RE.search(t))),
    required("printed_totals", lambda t: bool(_ORACLE_RE.search(t))),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


class _Oracle:
    """The four figures the fee table prints about the period."""

    __slots__ = ("debit_count", "debit_total", "credit_count", "credit_total")

    def __init__(self, debit_count, debit_total, credit_count, credit_total):
        self.debit_count = debit_count
        self.debit_total = debit_total
        self.credit_count = credit_count
        self.credit_total = credit_total


def _oracle(text: str) -> _Oracle | None:
    match = _ORACLE_RE.search(text)
    if not match:
        return None
    debit_total, credit_total = _money(match.group(2)), _money(match.group(4))
    if debit_total is None or credit_total is None:
        return None
    return _Oracle(int(match.group(1)), debit_total, int(match.group(3)), credit_total)


def _period(text: str) -> tuple[date, date] | None:
    match = _PERIOD_RE.search(text)
    if not match:
        return None
    d1, m1, y1, d2, m2, y2 = (int(g) for g in match.groups())
    try:
        start, end = date(y1, m1, d1), date(y2, m2, d2)
    except ValueError:
        return None
    return (start, end) if start <= end else None


def _ledger_body(text: str) -> str | None:
    """The ledger alone: from the first column header to the fee table.

    Both edges are the document's own furniture rather than a character
    distance, and the fee table is a genuine terminator - every row below it
    is a fee line or a credit-limit statistic, none of them postings.
    """
    grid = _GRID_RE.search(text)
    fee = _FEE_TABLE_RE.search(text)
    if not grid or not fee or fee.start() <= grid.end():
        return None
    return _PAGE_FURNITURE_RE.sub(" ", text[grid.end():fee.start()])


def _rows(body: str) -> list[tuple[int, int, str]]:
    """`(month, day, rest-of-row)` for every ledger row, in printed order."""
    starts = list(_ROW_RE.finditer(body))
    rows = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        rows.append((int(match.group(1)), int(match.group(2)), body[match.end():end]))
    return rows


def _amount_from_chain(token: str, movement: float) -> tuple[float, int] | None:
    """Which reading of a space-grouped amount the printed balance selects.

    `1 234,56` beside a description is ambiguous in flattened text, because a
    description may itself end in a number: `C/ACHAT 00105958482 PETRO-CANADA
    13 100,00` is a $13,100.00 purchase if `13` is a thousands group and a
    $100.00 purchase at store 13 if it is part of the merchant's name. Both
    readings are well-formed French money and no amount of grammar separates
    them - four of these sixteen documents turn on it.

    **The document decides, not this reader.** The balance beside the row is
    printed by the bank, and only one reading satisfies
    `previous + amount == balance`. So the candidates are the token and each
    of its suffixes at a group boundary, the movement the balances demand
    selects one, and a row where NONE fits is a row we have misread - which
    refuses the document rather than publishing a guess. The readings are
    distinct numbers, so at most one can ever fit; `!= 1` is written out
    anyway, because "exactly one reading survived" is the claim being made.

    Returns `(value, offset)` - the value and where inside `token` the reading
    began, so the digits that turned out to be description can be given back
    to it.
    """
    groups = token.split(" ")
    fitting = []
    for index in range(len(groups)):
        value = _money(" ".join(groups[index:]))
        if value is not None and abs(value - abs(movement)) <= 0.01:
            offset = len(" ".join(groups[:index])) + (1 if index else 0)
            fitting.append((value, offset))
    return fitting[0] if len(fitting) == 1 else None


def _transactions(
    rows: list[tuple[int, int, str]], *, start: date, end: date
) -> tuple[float, list[Transaction]] | None:
    """The period's postings, or None where the ledger does not hold together.

    The first row must be the opening bookend, and every row after it must
    carry an amount and a balance that continue the chain. There is no partial
    answer: a ledger this reader cannot walk end to end is one it has misread,
    and the four printed figures it would then be checked against are checks
    on the wrong ledger.
    """
    if not rows:
        return None
    (_month, _day, first), rest = rows[0], rows[1:]
    if _OPENING_LABEL not in first:
        return None
    opening_monies = _SIGNED_MONEY_RE.findall(first)
    if len(opening_monies) != 1:
        return None
    opening = _money(opening_monies[0][1])
    if opening is None:
        return None
    opening = -opening if opening_monies[0][0] else opening

    balance = opening
    txns: list[Transaction] = []
    for month, day, text in rest:
        monies = list(_SIGNED_MONEY_RE.finditer(text))
        if len(monies) < 2:
            return None
        printed = _money(monies[-1].group(2))
        if printed is None:
            return None
        new_balance = -printed if monies[-1].group(1) else printed
        reading = _amount_from_chain(monies[-2].group(2), round(new_balance - balance, 2))
        if reading is None:
            return None
        value, offset = reading
        # The row's year is the year of the period month it was posted in. A
        # `MM JJ` pair carries none of its own, and a period that crosses a
        # new year prints both months, so the month is what says which.
        year = start.year if month == start.month else end.year if month == end.month else None
        if year is None:
            return None
        try:
            posted = date(year, month, day)
        except ValueError:
            return None
        if not start <= posted <= end:
            return None
        signed = value if new_balance >= balance else -value
        txns.append(
            Transaction(
                date=posted.isoformat(),
                description=compact_whitespace(text[: monies[-2].start() + offset]),
                amount=round(signed, 2),
                direction="credit" if signed >= 0 else "debit",
                running_balance=round(new_balance, 2),
            )
        )
        balance = new_balance
    return (opening, txns) if txns else None


def _oracle_disagrees(oracle: _Oracle, txns: list[Transaction]) -> bool:
    """Do the bank's own four printed figures disagree with what we read?

    Counted by `Transaction.direction` - the column the row was printed in -
    and not by the sign of the amount, the rule `reconcile` and
    `analysis/count_semantics.py` state for the same reason: a zero-movement
    row belongs to one of the bank's two counts and to neither side of a sign
    test. Both counts AND both totals must agree; three out of four is a
    disagreement.
    """
    credits = [t for t in txns if t.direction == "credit"]
    debits = [t for t in txns if t.direction == "debit"]
    return (
        len(credits) != oracle.credit_count
        or len(debits) != oracle.debit_count
        or abs(round(sum(t.amount for t in credits), 2) - oracle.credit_total) > 0.02
        or abs(round(sum(-t.amount for t in debits), 2) - oracle.debit_total) > 0.02
    )


def parse_releve_facturation_statement(markdown: str) -> Statement | None:
    """One account's statement on this template, published without an issuer.

    Declines - rather than guesses - wherever the document does not supply
    what it would take to publish honestly: no period, no account number, no
    product line, a ledger that does not walk, or four printed figures that
    disagree with the ledger read. The published `bank` is `None` on every
    document, because none of them names one.
    """
    if not detect(markdown).claims:
        return None
    text = _fold(markdown)

    period = _period(text)
    account = _ACCOUNT_RE.search(text)
    product = _PRODUCT_RE.search(text)
    oracle = _oracle(text)
    body = _ledger_body(text)
    if period is None or account is None or product is None or oracle is None or body is None:
        return None
    start, end = period

    walked = _transactions(_rows(body), start=start, end=end)
    if walked is None:
        return None
    opening, txns = walked
    if _oracle_disagrees(oracle, txns):
        return None

    return Statement(
        # NOT a gap in this reader: the fact this template prints about its
        # issuer is nothing at all. See the module docstring.
        bank=None,
        account_name=product.group(1),
        account_number=account.group(1),
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        days_in_period=(end - start).days + 1,
        beginning_balance=round(opening, 2),
        ending_balance=txns[-1].running_balance,
        # The product line is the document's own statement of which currency
        # the account is denominated in, and the only one on the page - the
        # column headers print a bare `($)`.
        currency="CAD",
        stated_total_credits=oracle.credit_total,
        stated_total_debits=oracle.debit_total,
        stated_credit_count=oracle.credit_count,
        stated_debit_count=oracle.debit_count,
        transactions=txns,
    )
