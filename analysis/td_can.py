"""Deterministic parser for TD Canada statement tables.

TD Canada's OCR output is usually a usable HTML table, but rowspans can shift a
date or amount into the neighboring row. This parser handles the common TD CAD
layout directly instead of asking the generic extractor to infer it.

The native-text path reads the same printed grid from a text layer that has
collapsed its column gaps, so a row arrives as `<description> <amount> <DATE>
[<balance>]` and the CHEQUE/DEBIT vs DEPOSIT/CREDIT distinction is not in the
text. It is recovered from the running BALANCE the bank prints at the end of
each date group — see `_credit_counts_from_balances` (W3 Track A, cell
`td_canada_native x detail_coverage`).
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from typing import NamedTuple

from .date_tokens import date_refusal, iso_or_none
from .holder_name import NO_READING, HolderReading, read_address_line
from .money import parse_money, parse_money_tokens, strip_currency
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import CELL_RE, clean_cell, group_rows

_TABLE_RE = re.compile(r"<table>.*?</table>", re.IGNORECASE | re.DOTALL)
_ROW_RE = re.compile(r"<tr.*?>.*?</tr>", re.IGNORECASE | re.DOTALL)
_PERIOD_RE = re.compile(
    r"\b([A-Z]{3})\s*(\d{1,2})/(\d{2})\s*-\s*([A-Z]{3})\s*(\d{1,2})/(\d{2})\b",
    re.IGNORECASE,
)
_DATE_TOKEN_RE = re.compile(r"\b([A-Z]{3})(\d{1,2})\b", re.IGNORECASE)
_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


#: Signature sequences that only occur when UTF-8 bytes were mis-decoded as
#: cp1252/latin-1 ("mojibake"). Written as escapes on purpose: source code
#: never carries raw mojibake byte sequences (R-1 item 11).
_MOJIBAKE_MARKERS = ("\u00c3", "\u00e2\u20ac", "\u00c2")
#: Targeted fallback for mixed content where the full-text reversal fails.
_MOJIBAKE_TABLE = {
    "\u00e2\u20ac\u201d": "\u2014",  # em dash
    "\u00e2\u20ac\u201c": "\u2013",  # en dash
    "\u00e2\u20ac\u02dc": "\u2018",  # left single quote
    "\u00e2\u20ac\u2122": "\u2019",  # right single quote
    "\u00c3\u2021": "\u00c7",  # C-cedilla (upper)
    "\u00c3\u2030": "\u00c9",  # E-acute (upper)
    "\u00c3\u00a9": "\u00e9",  # e-acute
    "\u00c3\u00a8": "\u00e8",  # e-grave
    "\u00c3\u00aa": "\u00ea",  # e-circumflex
    "\u00c3\u00a7": "\u00e7",  # c-cedilla
    "\u00c3\u00a0": "\u00e0",  # a-grave
    "\u00c3\u00b4": "\u00f4",  # o-circumflex
    "\u00c3\u00ae": "\u00ee",  # i-circumflex
    "\u00c2\u00a0": " ",  # doubly-encoded NBSP
}


def normalize_mojibake(text: str) -> str:
    """Repair double-encoded (UTF-8 read as cp1252) text; NBSP becomes space.

    R-1 item 11: parsers normalize encoding FIRST and then match real
    characters - regexes never carry mojibake byte sequences. Clean text
    passes through unchanged, so already-correct sources are untouched.
    """
    if not any(marker in text for marker in _MOJIBAKE_MARKERS):
        return text.replace("\u00a0", " ")
    try:
        repaired = text.encode("cp1252", errors="strict").decode("utf-8", errors="strict")
    except (UnicodeEncodeError, UnicodeDecodeError):
        repaired = text
        for wrong, right in _MOJIBAKE_TABLE.items():
            repaired = repaired.replace(wrong, right)
    return repaired.replace("\u00a0", " ")


def _tables(markdown: str) -> list[list[list[str]]]:
    parsed = []
    for table in _TABLE_RE.findall(markdown):
        rows = []
        for row in _ROW_RE.findall(table):
            cells = [clean_cell(c) for c in CELL_RE.findall(row)]
            if cells:
                rows.append(cells)
        if rows:
            parsed.append(rows)
    return parsed


def _parse_summary_count_amount(value: str | None) -> tuple[int, float] | None:
    if not value:
        return None
    text = strip_currency(value)
    m = re.search(r"\b(\d+)\s+(\d+(?:\.\d{2})?)\b", text)
    if not m:
        return None
    return int(m.group(1)), round(float(m.group(2)), 2)


def _summary_count_amount(cells: list[str], label: str) -> tuple[int, float] | None:
    label = label.upper()
    for i, cell in enumerate(cells):
        if label not in cell.upper():
            continue
        direct = _parse_summary_count_amount(cell)
        if direct:
            return direct
        nums: list[str] = []
        for later in cells[i + 1:]:
            nums.extend(re.findall(r"\d[\d,]*(?:\.\d{2})?", later))
        if len(nums) >= 2:
            return int(nums[0].replace(",", "")), round(float(nums[1].replace(",", "")), 2)
    return None


def _parse_period(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    m = _PERIOD_RE.search(value.upper())
    if not m:
        return None
    sm, sd, sy, em, ed, ey = m.groups()
    # RAISE-PRIVACY-5, the LOOKUP half of the same law, and the one shape the
    # conversion census structurally cannot see: `_PERIOD_RE`'s `([A-Z]{3})`
    # proves three capital letters and nothing more, so a period line whose
    # month word is not a month reaches `_MONTHS[sm]`, and a `KeyError` IS its
    # key — `str` and `args` measured at the base tree as the printed word
    # itself. `.get` performs the SAME lookup in the SAME place and the
    # refusal is a FIXED sentence raised from OUTSIDE any handler, so the
    # raised CLASS stays `KeyError`, every outcome and published field stays
    # what it was, and only the message stops carrying the word. `from None`
    # would not do: it clears `__cause__` and leaves `__context__` holding the
    # original. The literal is written out at both ends rather than named,
    # because a plain string literal is what the `CHAIN_GUARDED` reader can
    # verify without executing anything — and because the two ends must be
    # indistinguishable, exactly as the two `date_refusal`s below are.
    #
    # The lookup is read BEFORE `2000 + int(sy)` rather than as the second
    # argument of the call below, and that reorders nothing observable:
    # `re`'s `\d` matches Unicode category Nd and `int()` accepts every Nd
    # character, so `int()` on a group `(\d{2})` produced cannot raise. Driven
    # on both trees with non-ASCII decimal digits.
    start_month = _MONTHS.get(sm)
    if start_month is None:
        raise KeyError(
            "month lookup refused a printed word "
            "(not a month word; reader=td_can._parse_period)"
        )
    # RAISE-PRIVACY-4, the MAJOR-2 class W3 §H14 carried out of #HYGIENE8:
    # `_PERIOD_RE`'s `(\d{1,2})/(\d{2})` proves two digit runs and nothing
    # more, so a period printed `FEB30/31` reaches `date()`, whose ValueError
    # echoes the printed day, month number and year — measured at the base tree
    # as `day 30 must be in range 1..28 for month 2 in year 2031`. Funnelled
    # through `iso_or_none` and refused from OUTSIDE the funnel; the class
    # stays `ValueError`. The two ends are read SEQUENTIALLY, exactly as the
    # two `date()` calls were evaluated, so a document whose start cell
    # refuses still refuses on the start cell and never reaches the end month.
    start = iso_or_none(2000 + int(sy), start_month, int(sd))
    if start is None:
        raise date_refusal("td_can._parse_period", m.group(0))
    end_month = _MONTHS.get(em)
    if end_month is None:
        raise KeyError(
            "month lookup refused a printed word "
            "(not a month word; reader=td_can._parse_period)"
        )
    end = iso_or_none(2000 + int(ey), end_month, int(ed))
    if end is None:
        raise date_refusal("td_can._parse_period", m.group(0))
    return start, end


def _date_tokens(value: str | None, *, default_year: int) -> list[str]:
    if not value:
        return []
    text = value.upper().replace("OCTS", "OCT").replace("SEPS", "SEP")
    out = []
    for mon, day, yy in re.findall(r"\b([A-Z]{3})\s*(\d{1,2})(?:/(\d{2}))?\b", text):
        # RAISE-PRIVACY-5's THIRD lookup and the only one left standing as a
        # subscript: this membership test is the guard, in the same loop body,
        # so `_MONTHS[mon]` below cannot raise and there is no refusal here to
        # make private. Rerouting it would turn a skipped token into a raise —
        # a new refusal, which this card may not introduce — so it is accounted
        # for in `TOKEN_LOOKUP_ALLOWED` instead, and the guard is DRIVEN rather
        # than asserted (`tests/test_raise_privacy4.py`).
        if mon not in _MONTHS:
            continue
        year = 2000 + int(yy) if yy else default_year
        # RAISE-PRIVACY-4, the same class one function down: `([A-Z]{3})\s*
        # (\d{1,2})` proves a month WORD and a day SHAPE, so a cell printed
        # `FEB 30` reaches `date()` — measured at the base tree as `day 30 must
        # be in range 1..28 for month 2 in year 2031`. The refused token is
        # rebuilt from the groups that produced it rather than sliced out of
        # the cell, so the refusal measures exactly what the reader read.
        iso = iso_or_none(year, _MONTHS[mon], int(day))
        if iso is None:
            raise date_refusal(
                "td_can._date_tokens", f"{mon}{day}/{yy}" if yy else f"{mon}{day}"
            )
        out.append(iso)
    return out


def _native_date_token(value: str) -> str | None:
    text = value.upper().replace("OCTS", "OCT").replace("SEPS", "SEP")
    return text if _DATE_TOKEN_RE.fullmatch(text) and text[:3] in _MONTHS else None


def _native_date_to_iso(value: str, *, default_year: int) -> str:
    """The printed date token as ISO, refusing rather than inventing a date.

    The refusal names this reader and the token's SHAPE, never the cell
    (`date_tokens.date_refusal`, W3 §PRIVACY3). Control flow is unchanged: the
    same tokens raise, with the same class, at the same line.
    """
    m = _DATE_TOKEN_RE.fullmatch(value.upper())
    if not m:
        raise date_refusal("td_can._native_date_to_iso", value)
    # RAISE-PRIVACY-5, the lookup half. `_DATE_TOKEN_RE`'s `([A-Z]{3})` proves
    # three capital letters, so the month word reaches `_MONTHS[...]` and a
    # `KeyError` is its key. Production cannot reach this — `_native_date_index`
    # goes through `_native_date_token`, which tests `text[:3] in _MONTHS`
    # first, and a token needing the `OCTS`/`SEPS` rewrite fails the raw
    # `fullmatch` and takes the shape refusal above — so this is the
    # CALLER-GUARDED twin of the two in `_parse_period`, closed the same way
    # for the same reason a guard that depends on a caller is the kind of
    # protection that disappears when the caller changes.
    #
    # THE SECOND EVALUATION-ORDER CHANGE, named here because a reorder nobody
    # names is a reorder nobody drives: the lookup was the SECOND argument of
    # the call below, so `int(m.group(2))` used to be evaluated after it and is
    # now evaluated after this refusal instead. Unobservable for the same
    # reason as the one in `_parse_period`: `re`'s `\d` matches Unicode
    # category Nd, `int()` accepts every Nd character, and a SUPERSCRIPT is
    # category No — so `\d{1,2}` never matches one and the token takes the
    # shape refusal above without reaching either the lookup or `int()`.
    # Driven on both trees over Nd, No and ASCII day glyphs, on a readable
    # month word and an unreadable one.
    month = _MONTHS.get(m.group(1).upper())
    if month is None:
        raise KeyError(
            "month lookup refused a printed word "
            "(not a month word; reader=td_can._native_date_to_iso)"
        )
    # RAISE-PRIVACY-4: the fullmatch above proves the token's SHAPE and nothing
    # more, so `FEB30` passes it and reaches `date()`, whose ValueError echoes
    # the printed day — measured at the base tree as `day 30 must be in range
    # 1..28 for month 2 in year 2031`. The SECOND refusal of this reader,
    # through the same constructor and naming the same site: a caller cannot
    # tell the two refusals apart, which is the point.
    iso = iso_or_none(default_year, month, int(m.group(2)))
    if iso is None:
        raise date_refusal("td_can._native_date_to_iso", value)
    return iso


def _native_date_index(line: str) -> int | None:
    """Where TD prints the DATE column inside a flattened ledger line.

    TD's Date column stands between the two money columns and the BALANCE
    column, so — unlike Chase's or RBC's — the date token that opens a printed
    row does not open its physical line. That is the whole of what this
    parser hands `tables.group_rows` as its row-start rule (W3 §GROUPER).
    """
    tokens = line.split()
    return next((i for i, token in enumerate(tokens) if _native_date_token(token)), None)


def _looks_like_money(value: str | None) -> bool:
    return bool(parse_money_tokens(value))


def _tx(date_value: str, description: str, amount: float, balance: float | None = None) -> Transaction:
    return Transaction(
        date=date_value,
        description=re.sub(r"\s+", " ", description).strip(),
        amount=round(amount, 2),
        direction="credit" if amount > 0 else "debit",
        running_balance=balance,
    )


def _credit_like(description: str) -> bool:
    """Generic banking-language credit signals only (no merchant names)."""
    text = description.upper()
    return any(word in text for word in ("PAY", "DEPOSIT", "CREDIT", "E-TRANSFER CR"))


#: TD prints a transaction-type code as the trailing token of native ledger
#: descriptions. Sign is determined by these structural codes (R-1 item 8 -
#: previously merchant-name lists decided sign):
#:   MSP  merchant services payment (settlement deposit)  -> credit
#:   CLN  commercial loan disbursement                     -> credit
#:   PAY  direct-deposit payment received                  -> credit
#:   GST  government tax remittance/refund                 -> credit
#:   BUS  business pre-authorized debit                    -> debit
_NATIVE_CREDIT_CODES = {"MSP", "CLN", "PAY", "GST"}
_NATIVE_DEBIT_CODES = {"BUS"}

#: `GC <n>-DEPOSIT` — a deposit posted through TD's own deposit channel, whose
#: four-digit unit number is statement data and therefore cannot be part of the
#: marker. The channel prints the direction itself, in the same position, on
#: both of its forms: the sibling `GC <n>-CASH WITHDRA` is a withdrawal and
#: must not match, which is why this keys on `-DEPOSIT` and not on `GC`.
_GC_DEPOSIT_RE = re.compile(r"GC \d+-DEPOSIT\b")
#: ...and that sibling, read as what it says. Both halves of a channel that
#: prints its own direction are evidence, and only the deposit half was ever
#: read: the withdrawal half fell through to the default, which made "TD says
#: this left the account" indistinguishable from "TD says nothing". The
#: distinction is the whole of what `_split_supported_by_codes` ranks on, so
#: the silent half is spelled out here. `_native_credit_like` is MEASURED
#: inert, not unaffected: reading a withdrawal half now returns before the
#: trailing-code test, so `GC 4021-CASH WITHDRA GST` reads not-a-credit here
#: where it read a credit before. That is the more correct answer, and there
#: are 0 such rows across the 126 documents of the three families.
_GC_CASH_WITHDRAWAL_RE = re.compile(r"GC \d+-CASH WITHDRA")


def _native_direction_code(description: str) -> bool | None:
    """What TD's own transaction code says this row is, or None if it says nothing.

    Three-valued on purpose. `_native_credit_like` below collapses this to a
    boolean because that is all the *default* reading needs, but the collapse
    throws away the distinction between a row TD has labelled a withdrawal and
    a row TD has labelled nothing at all — and that distinction is evidence.
    `_split_supported_by_codes` spends it: where the printed balance column
    admits several credit/debit splits of one date group, the split that
    contradicts a code the bank PRINTED is worse evidence than the split that
    only disagrees with a default. Never a counterparty name (R-1 item 8).
    """
    text = description.upper()
    if "TFR-FR" in text:          # transfer from another account
        return True
    if "TFR-TO" in text:          # transfer to another account
        return False
    if text.startswith("SEND E-TFR"):
        return False
    # TD writes the direction of an e-transfer as the presence or absence of
    # its own leading verb: `SEND E-TFR ...` leaves the account, a bare
    # `E-TFR ...` arrives in it. Only the spelled-out `E-TRANSFER` was read, so
    # every incoming transfer printed in the abbreviated form was taken for a
    # debit. `CANCEL`/`RECLAIM E-TFR` lead with their own verb and are left to
    # the printed balances, as before — which is to say they return None here,
    # not False: the bank has not said which way they went.
    if text.startswith("E-TRANSFER") or text.startswith("E-TFR "):
        return True
    # `TD ATM DEP <n>` is a deposit at TD's own machine; the sibling
    # `TD ATM W/D <n>` is a withdrawal, so the code is the whole distinction —
    # and both halves are read, for the reason `_GC_CASH_WITHDRAWAL_RE` gives.
    if text.startswith("TD ATM DEP"):
        return True
    if text.startswith("TD ATM W/D"):
        return False
    if _GC_DEPOSIT_RE.match(text):
        return True
    if _GC_CASH_WITHDRAWAL_RE.match(text):
        return False
    tokens = text.split()
    if tokens:
        if tokens[-1] in _NATIVE_DEBIT_CODES:
            return False
        if tokens[-1] in _NATIVE_CREDIT_CODES:
            return True
    return None


def _native_credit_like(description: str) -> bool:
    """Sign from TD's own transaction codes, never from counterparty names.

    MEASURED inert against the reading it replaces, not identical to it. A
    description carrying BOTH a withdrawal code and a trailing credit code
    (`TD ATM W/D 0123 PAY`) used to reach the trailing test and read as a
    credit; it now returns at the withdrawal code and reads as one. That is the
    more correct answer — TD prints the channel first — and the archive is
    silent on it: 0 such rows across the 126 documents of the three families.
    """
    return _native_direction_code(description) is True


#: The ledger ends at the cheque-enclosure line, whose leading token is the
#: number of cheques the envelope contains. That count is statement data, so it
#: cannot be part of the marker: matching a literal count kept the ledger open
#: past the end of every page of every statement that encloses one.
_CHQS_ENCLOSED_RE = re.compile(r"^\d+ CHQS? ENCLOSED\b")

#: Bounds on the balance solver below. A TD date group is a handful of printed
#: rows and the two-sided prune keeps the reachable-subtotal table small, so
#: neither bound is reached by the printed grid; they exist so that a
#: pathological document costs a fixed amount of work and then falls through to
#: the transaction codes instead of running unbounded inside a parser.
_MAX_GROUP_ROWS = 64
_MAX_SOLVER_STATES = 100_000
#: Bounds on the candidate ENUMERATION below, which runs only where the
#: transaction codes contradict the printed balance and so is reached by 11
#: date groups in the whole archive. Counting reachable subtotals is
#: polynomial; listing the splits that reach one is not, so the walk carries
#: its own budget and reports "not enumerable" rather than running long inside
#: a parser. Either bound being hit leaves the group with the reading it has,
#: which is what the shipped parser does today.
_MAX_SPLIT_CANDIDATES = 256
_MAX_SPLIT_NODES = 250_000


class _NativeRow(NamedTuple):
    """One flattened native ledger row.

    TD prints five columns — DESCRIPTION, CHEQUE/DEBIT, DEPOSIT/CREDIT, DATE,
    BALANCE — and the native text layer emits each printed row as one line with
    the column gaps collapsed to single spaces. A row therefore arrives here as
    ``<description> <amount> <DATE> [<balance>]``: the amount survives, but
    *which* of the two money columns it was printed in does not.
    """

    date: str
    description: str
    #: Absolute value in cents, so the balance arithmetic below is exact.
    amount: int
    #: The printed BALANCE cell, on the rows that carry one.
    balance: float | None


def _to_cents(value: float) -> int:
    return int(round(value * 100))


def _credit_target(amounts: list[int], delta: int) -> int | None:
    """What the printed BALANCE column says the DEPOSIT/CREDIT rows total, in cents.

    With ``S`` the sum of a date group's absolute amounts and ``delta`` the
    change the bank printed across it, the credit rows sum to ``(delta + S)/2``
    — the one number the printed grid states about the lost column, before any
    question of WHICH rows carry it.

    Returns None where the printed evidence does not state one: an odd
    ``delta + S`` (a row is missing or misread, since every real split is an
    integer number of cents), a target outside ``[0, S]`` (no assignment of
    these amounts produces that change), an empty group, or more rows than the
    bounds admit. The callers all treat None the same way — the arithmetic has
    refused, so the reading stands on the transaction codes alone.
    """
    if not amounts or len(amounts) > _MAX_GROUP_ROWS:
        return None
    total = sum(amounts)
    doubled = delta + total
    if doubled % 2:
        return None
    target = doubled // 2
    if target < 0 or target > total:
        return None
    return target


def _credit_count_candidates(amounts: list[int], delta: int) -> list[dict[int, int]] | None:
    """Every DEPOSIT/CREDIT split of a date group the printed balances admit.

    `_credit_counts_from_balances` answers "does the printed evidence single
    one out?" and stops there. This lists them, because "several" is not the
    same as "nothing": every candidate here reproduces the balance the bank
    printed at the end of the group exactly, so the group's net movement, its
    end-of-day balance and both direction TOTALS are identical across all of
    them. What differs between candidates is only which rows carry the credit
    subtotal — and therefore the credit and debit COUNTS, which the bank prints
    separately and `analysis/count_semantics.py` holds this parser to.

    Returns `[]` where the printed evidence admits no split, and `None` where
    the enumeration exceeds its bounds (`_MAX_SPLIT_CANDIDATES` /
    `_MAX_SPLIT_NODES`) — "more work than a parser may do", which is a
    different answer from "no reading exists" even though both callers
    currently treat them alike.

    Candidates are keyed by amount and not by row, for the reason
    `_credit_counts_from_balances` gives: swapping two rows of equal amount
    leaves every balance and every total identical, so the arithmetic cannot
    distinguish them and does not pretend to.
    """
    target = _credit_target(amounts, delta)
    if target is None:
        return []

    multiplicity = Counter(amounts)
    # A `$0.00` posting (a returned ACH) reaches this parser, and the
    # arithmetic has nothing whatever to say about its column: calling it a
    # deposit changes no subtotal and no balance. It is therefore not a
    # dimension of this search — which is also why there is no `left // value`
    # here that could divide by zero. The consequence is stated where it bites:
    # on a group this function is asked about, a `$0.00` row TD coded as a
    # deposit is published as a withdrawal, no money moves either way, and the
    # bank's printed COUNT is the evidence that says so.
    values = sorted((value for value in multiplicity if value), reverse=True)
    #: `remaining[i]` is everything `values[i:]` can still contribute, so a
    #: branch that cannot reach the target from here is abandoned rather than
    #: walked to the end.
    remaining: list[int] = []
    running = 0
    for value in reversed(values):
        running += value * multiplicity[value]
        remaining.append(running)
    remaining.reverse()

    found: list[dict[int, int]] = []
    budget = _MAX_SPLIT_NODES

    def walk(index: int, left: int, taken_so_far: list[int]) -> bool:
        """False when a bound was hit and the enumeration is incomplete."""
        nonlocal budget
        budget -= 1
        if budget <= 0:
            return False
        if left == 0:
            found.append(dict(zip(values, taken_so_far + [0] * (len(values) - len(taken_so_far)))))
            return len(found) <= _MAX_SPLIT_CANDIDATES
        if index >= len(values) or left < 0 or remaining[index] < left:
            return True
        value = values[index]
        for taken in range(min(multiplicity[value], left // value) + 1):
            taken_so_far.append(taken)
            complete = walk(index + 1, left - value * taken, taken_so_far)
            taken_so_far.pop()
            if not complete:
                return False
        return True

    if not walk(0, target, []):
        return None
    return found


def _credit_counts_from_balances(amounts: list[int], delta: int) -> dict[int, int] | None:
    """Which amounts the printed BALANCE column says were DEPOSIT/CREDIT rows.

    TD prints a running balance on the last row of each date group, so between
    two printed balances the signed amounts must equal the difference the bank
    itself printed. Recovering the lost column is therefore arithmetic over the
    printed grid, not an inference about what a description means.

    With ``S`` the sum of the group's amounts and ``delta`` the printed change,
    the credit rows sum to ``(delta + S) / 2``; the debit rows are the rest.
    Returns ``{amount_in_cents: how many rows of that amount are credits}`` when
    exactly one such split exists, and ``None`` when the printed evidence does
    not single one out — no split, several, or more work than the bounds allow.

    Rows of equal amount are counted, not identified: swapping two equal rows
    leaves every balance and every total identical, so the arithmetic cannot
    distinguish them and does not pretend to.
    """
    target = _credit_target(amounts, delta)
    if target is None:
        return None
    total = sum(amounts)

    multiplicity = Counter(amounts)
    values = sorted(multiplicity, reverse=True)   # largest first prunes hardest
    unplaced = total
    #: reachable credit subtotal -> (distinct splits reaching it, capped at two
    #: because only "exactly one" matters, one representative split)
    reachable: dict[int, tuple[int, tuple[int, ...]]] = {0: (1, ())}
    for value in values:
        repeats = multiplicity[value]
        unplaced -= value * repeats
        nxt: dict[int, tuple[int, tuple[int, ...]]] = {}
        for subtotal, (splits, taken_so_far) in reachable.items():
            for taken in range(repeats + 1):
                moved = subtotal + value * taken
                if moved > target:
                    break                       # every later `taken` is larger
                if moved + unplaced < target:
                    continue                    # the rest cannot make up the gap
                seen = nxt.get(moved)
                if seen is None:
                    nxt[moved] = (splits, taken_so_far + (taken,))
                else:
                    nxt[moved] = (min(2, seen[0] + splits), seen[1])
        if len(nxt) > _MAX_SOLVER_STATES:
            return None
        reachable = nxt

    solution = reachable.get(target)
    if solution is None or solution[0] != 1:
        return None
    return dict(zip(values, solution[1]))


def _directions_from_credit_counts(
    rows: list[_NativeRow],
    credit_counts: dict[int, int],
    *,
    credit_like: Callable[[str], bool] = _native_credit_like,
) -> list[bool]:
    """Spend each amount's credit count over the rows printing that amount.

    Which row of an equal-amount class is the deposit is exactly what the
    arithmetic cannot say, so the tie is broken with TD's own transaction codes
    in printed order. It moves no total and no balance: the rows being ordered
    carry the same amount.

    `credit_like` is the reader of those codes and defaults to the English
    issue's. It is a parameter because the French issue of this same grid
    consumes this function over French descriptions, on which the English
    codes match almost nothing (W3 §WITHHELDTD).
    """
    remaining = dict(credit_counts)
    credits = [False] * len(rows)
    coded_first = sorted(
        range(len(rows)),
        key=lambda i: (not credit_like(rows[i].description), i),
    )
    for i in coded_first:
        if remaining.get(rows[i].amount, 0) > 0:
            remaining[rows[i].amount] -= 1
            credits[i] = True
    return credits


def _split_supported_by_codes(
    rows: list[_NativeRow],
    candidates: list[dict[int, int]],
    *,
    direction_code: Callable[[str], bool | None],
    credit_like: Callable[[str], bool],
) -> list[bool] | None:
    """Of the splits the printed balances admit, the one TD's own codes support.

    Reached only where the code reading CONTRADICTS the printed balance, so
    something has to give and the document says which: a split that puts a row
    TD labelled `SEND E-TFR` in the deposit column disagrees with the page,
    while a split that only disagrees about a row TD labelled nothing
    (`CANCEL E-TFR`) disagrees with a default. The ranking is therefore, in
    order: fewest rows contradicting a code the bank PRINTED; then fewest rows
    moved off the default reading at all; then the enumeration's own order,
    which is fixed.

    What this can and cannot get wrong, stated at the right level. Every
    candidate reproduces the printed end-of-group balance, so no AGGREGATE
    moves whichever is chosen: the group's net, the daily balances, the ADB and
    both direction TOTALS are identical across the candidates. A PER-ROW signed
    amount is a different matter and does move — `amount` is published as
    `+row.amount` or `-row.amount`, so changing a row's direction changes the
    sign of a published transaction amount, and with it that row's revenue
    classification. What certifies the choice is the credit and debit COUNTS,
    which TD prints and which `analysis/count_semantics.py` marks comparable
    for both issues of this layout: a wrong choice moves a count, and the
    platform flags it on evidence this function never reads.

    Which is why this REFUSES rather than guesses when the count cannot
    certify. Two candidates that tie on both keys AND carry the same number of
    credit rows are indistinguishable to every oracle the platform has — the
    balances admit both, the codes rank them equally, and the printed count
    cannot tell them apart. Returning None leaves the group on the code
    reading, which by construction here does NOT reproduce the printed change,
    so the ledger does not close and the document withholds. Not observed on
    this archive; `_tied_beyond_the_printed_counts` is where it is decided.
    """
    coded = [credit_like(row.description) for row in rows]
    ranked: list[tuple[tuple[int, int], list[bool]]] = []
    for counts in candidates:
        resolved = _directions_from_credit_counts(rows, counts, credit_like=credit_like)
        contradictions = 0
        moved = 0
        for row, is_credit, default in zip(rows, resolved, coded):
            code = direction_code(row.description)
            if code is not None and code != is_credit:
                contradictions += 1
            if is_credit != default:
                moved += 1
        ranked.append(((contradictions, moved), resolved))
    if not ranked:
        return None
    best_key = min(key for key, _resolved in ranked)
    tied = [resolved for key, resolved in ranked if key == best_key]
    if _tied_beyond_the_printed_counts(tied):
        return None
    return tied[0]


def _tied_beyond_the_printed_counts(tied: list[list[bool]]) -> bool:
    """Do two equally-ranked readings carry the same number of credit rows?

    The printed credit and debit counts are the platform's certificate on this
    choice, and they can only certify a choice between readings that DIFFER in
    how many rows they call deposits. Two readings that rank alike and count
    alike are past every oracle the document offers, so the reader stops.
    """
    if len(tied) < 2:
        return False
    counts = [sum(resolved) for resolved in tied]
    return len(set(counts)) < len(counts)


def _resolve_directions_from_balances(
    rows: list[_NativeRow],
    groups: list[tuple[list[int], float]],
    opening: float | None,
    *,
    direction_code: Callable[[str], bool | None],
    credit_like: Callable[[str], bool],
) -> list[bool]:
    """One `is credit` flag per ledger row, from the printed balance column.

    `groups` are `(row indices, the balance printed at the end of the group)` in
    document order. The precedence is the printed grid first and the
    transaction codes second, and this function is where that is enforced,
    for both issues of the layout:

    * the balances single a split out — take it (the shipped reading);
    * the balances admit several AND the codes already reproduce the printed
      change across the group — the codes are one of those splits, so keep
      them, and the reading is the shipped one to the row;
    * the balances admit several and the codes do NOT reproduce the printed
      change — the codes are contradicting the page, so the page decides which
      split and `_split_supported_by_codes` decides which of them, or refuses
      when two of them are past every oracle the document offers;
    * the balances state nothing about this group (an odd parity, an
      unreachable target, or more work than the bounds allow) — the codes are
      all there is, and the reading stands on them.

    Only the third bullet is new (W3 §WITHHELDTD). It was previously the second
    bullet's branch, which meant a group whose codes disagreed with the printed
    balance kept the codes and silently threw the bank's own arithmetic away —
    measured archive-wide as 11 date groups in 10 documents, every one of them
    a document the ADB then refused.

    Reconciliation against the bank's own stated credit and debit totals and
    counts — evidence neither the solver nor the codes ever read — remains the
    fail-closed gate over the whole result.
    """
    credits = [credit_like(row.description) for row in rows]
    anchor = opening
    for indices, closing in groups:
        if anchor is None:
            anchor = closing
            continue
        group = [rows[i] for i in indices]
        amounts = [row.amount for row in group]
        delta = _to_cents(closing) - _to_cents(anchor)
        anchor = closing
        counts = _credit_counts_from_balances(amounts, delta)
        if counts is not None:
            resolved = _directions_from_credit_counts(group, counts, credit_like=credit_like)
            for i, is_credit in zip(indices, resolved):
                credits[i] = is_credit
            continue
        target = _credit_target(amounts, delta)
        if target is None:
            continue
        if sum(row.amount for row in group if credit_like(row.description)) == target:
            continue                       # the codes already say what the page says
        candidates = _credit_count_candidates(amounts, delta)
        if not candidates:
            continue                       # nothing admissible, or not enumerable
        resolved = _split_supported_by_codes(
            group, candidates, direction_code=direction_code, credit_like=credit_like
        )
        if resolved is None:
            continue                       # tied past every oracle: fail closed
        for i, is_credit in zip(indices, resolved):
            credits[i] = is_credit
    return credits


def _resolve_native_directions(
    rows: list[_NativeRow],
    groups: list[tuple[list[int], float]],
    opening: float | None,
) -> list[bool]:
    """The English issue's reading of the printed balance column."""
    return _resolve_directions_from_balances(
        rows,
        groups,
        opening,
        direction_code=_native_direction_code,
        credit_like=_native_credit_like,
    )


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


def _table_layout_present(markdown: str) -> bool:
    """The TD table layout, as the pre-R-3 guard tested for it.

    The bank-name test does not depend on the table being iterated, but the
    surrounding `any(...)` means an empty table list still fails: this parser
    reads tables, so a document with none is not its document.
    """
    tables = _tables(markdown)
    return any(
        "THE TORONTO-DOMINION BANK" in markdown.upper()
        or "BUSINESS CHEQUING ACCOUNT - CAD" in " ".join(sum(table, []))
        for table in tables
    )


#: The account's own product name, printed in this layout's `Account Type`
#: column of the header block: `BUSINESS CHEQUING` / `ACCOUNT - CAD`, wrapped
#: across two lines by the column width and set on one line by the issues that
#: have room for it (which is why `_table_layout_present` above already tests
#: for the unwrapped spelling). The suffix is the account's denomination and is
#: the only currency word the layout prints anywhere.
#:
#: A product with no denomination prints none: the one archive document of this
#: layout without a suffix prints `BUSINESS` / `INVESTOR` / `ACCOUNT`, and its
#: currency is therefore not stated. Anchoring on the word `ACCOUNT` rather
#: than scanning for a bare `CAD`/`USD` token is what keeps this off the ledger,
#: where TD prints `CAD DRAFT 11512638` as a posting description — a draft's
#: denomination, not the account's.
_NATIVE_PRODUCT_CURRENCY_RE = re.compile(r"\bACCOUNT\s*-\s*(CAD|USD)\b")


def _native_printed_currency(markdown: str) -> str | None:
    """The currency this document's product line PRINTS, or None.

    Two different suffixes on one document is a statement of several accounts
    in different denominations; there is no single answer to publish, so this
    returns None and the caller leaves the default standing.
    """
    found = set(_NATIVE_PRODUCT_CURRENCY_RE.findall(markdown.upper()))
    if len(found) != 1:
        return None
    return found.pop()


def _native_product_name(printed_currency: str | None) -> str:
    """The account name, carrying the suffix the DOCUMENT printed and no other.

    This name and `Statement.currency` are derived from the same match on
    purpose. They were not: the name was the fixed string
    `BUSINESS CHEQUING ACCOUNT - CAD` written whenever the header printed
    `BUSINESS CHEQUING`, so reading the denomination off the page without
    reading the name off the same line would have published
    `currency="USD"` beside a name asserting `- CAD` on the three U.S.-dollar
    statements of this layout — a contradiction inside one payload, from one
    printed line, which is exactly what the currency-evidence invariant exists
    to prevent.

    The plan token the column also carries (`EVERY DAY B`) is deliberately NOT
    appended: it is printed, but adding it would move the published name on all
    73 documents of this layout including six pinned ones, on a field
    (`account`) that IS an audited column, for no correctness gain. The suffix
    is the only part of this string the currency work makes wrong.
    """
    if printed_currency is None:
        return "BUSINESS CHEQUING ACCOUNT"
    return f"BUSINESS CHEQUING ACCOUNT - {printed_currency}"


NATIVE_DETECTION_MARKERS = (
    required("bank_name", lambda t: "THE TORONTO-DOMINION BANK" in t),
    required("native_header", lambda t: "DESCRIPTION CHEQUE/DEBIT DEPOSIT/CREDIT DATE BALANCE" in t),
)

DETECTION_MARKERS = (
    required("table_layout", _table_layout_present),
)

detect_native = make_detector(NATIVE_DETECTION_MARKERS, detection_text)
detect = make_detector(DETECTION_MARKERS)


def _parse_native_td_canada(markdown: str, base: Statement | None = None) -> Statement | None:
    if not detect_native(markdown).claims:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "TD Canada Trust"
    # The product line states the denomination where the product has one; CAD
    # remains the layout's default where it does not, and the residual is
    # named rather than inferred from the branch address. Read once here and
    # used for BOTH the currency and the account name below, so the two can
    # never disagree about the same printed line.
    printed_currency = _native_printed_currency(markdown)
    stmt.currency = printed_currency or "CAD"
    stmt.currency_source = "product" if printed_currency else "institution_default"
    stmt.beginning_balance = None
    stmt.ending_balance = None
    stmt.stated_total_credits = None
    stmt.stated_total_debits = None
    stmt.stated_credit_count = None
    stmt.stated_debit_count = None
    stmt.bank_reported_average_balance = None
    stmt.bank_reported_average_label = None
    rows: list[_NativeRow] = []
    #: (row indices, the balance printed at the end of those rows).
    groups: list[tuple[list[int], float]] = []
    pending: list[int] = []
    ending_balance: float | None = None
    in_ledger = False
    default_year: int | None = None
    #: The printed ledger lines, each with the statement year in force where it
    #: was printed — the ledger opens at the column header and the period line
    #: that dates it can be printed after some of it.
    ledger: list[tuple[str, int]] = []

    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        upper = line.upper()
        period = _parse_period(line)
        if period:
            stmt.period_start, stmt.period_end = period
            default_year = int(stmt.period_end[:4])
        account = re.search(r"\b\d{4}-\d{6,}\b", line)
        if account:
            stmt.account_number = account.group(0)
        if "BUSINESS CHEQUING" in upper:
            stmt.account_name = _native_product_name(printed_currency)
        if upper.startswith("MONTHLY AVER. CR. BAL."):
            avg = parse_money(line)
            if avg is not None:
                stmt.bank_reported_average_balance = abs(avg)
                stmt.bank_reported_average_label = "MONTHLY AVER. CR. BAL."
        if upper.startswith("CREDITS "):
            credit = _parse_summary_count_amount(line)
            if credit:
                stmt.stated_credit_count = (stmt.stated_credit_count or 0) + credit[0]
                stmt.stated_total_credits = round((stmt.stated_total_credits or 0.0) + credit[1], 2)
        if upper.startswith("DEBITS "):
            debit = _parse_summary_count_amount(line)
            if debit:
                stmt.stated_debit_count = (stmt.stated_debit_count or 0) + debit[0]
                stmt.stated_total_debits = round((stmt.stated_total_debits or 0.0) + debit[1], 2)

        if upper.startswith("DESCRIPTION CHEQUE/DEBIT DEPOSIT/CREDIT DATE BALANCE"):
            in_ledger = True
            continue
        if in_ledger and _CHQS_ENCLOSED_RE.match(upper):
            in_ledger = False
            continue
        if not in_ledger or default_year is None:
            continue
        ledger.append((line, default_year))

    #: TD's native text layer emits each printed row as ONE physical line (the
    #: row is a single PyMuPDF block whose spans are joined with spaces), so
    #: rule 2 of the shared grouper — wrapped lines continue the row — never
    #: fires on this layout: a ledger line carrying no DATE column is section
    #: furniture, and it is read as part of no row, exactly as before.
    def opens_a_row(entry: tuple[str, int]) -> bool:
        return _native_date_index(entry[0]) is not None

    for grouped in group_rows(ledger, starts_row=opens_a_row):
        line, year = grouped[0]
        upper = line.upper()
        tokens = line.split()
        date_index = _native_date_index(line)
        if date_index is None:              # `opens_a_row` already said it is not
            continue

        tx_date = _native_date_to_iso(tokens[date_index], default_year=year)
        balance = parse_money(tokens[date_index + 1]) if date_index + 1 < len(tokens) else None
        if upper.startswith("BALANCE FORWARD"):
            if balance is None:
                continue
            if stmt.beginning_balance is None:
                stmt.beginning_balance = balance
            elif pending:
                # A page break can split a date group before its balance is
                # printed. The next page reprints the carried balance, which
                # closes the group the previous page ended inside.
                groups.append((pending, balance))
                pending = []
            continue

        amount_index = None
        amount = None
        for i in range(date_index - 1, -1, -1):
            parsed = parse_money(tokens[i])
            if parsed is not None and "." in tokens[i]:
                amount_index = i
                amount = abs(parsed)
                break
        if amount_index is None or amount is None:
            continue
        desc = " ".join(tokens[:amount_index])
        if not desc:
            continue
        rows.append(_NativeRow(tx_date, desc, _to_cents(amount), balance))
        pending.append(len(rows) - 1)
        if balance is not None:
            groups.append((pending, balance))
            pending = []
            ending_balance = balance

    if not rows:
        return None
    credits = _resolve_native_directions(rows, groups, stmt.beginning_balance)
    stmt.transactions = [
        _tx(row.date, row.description,
            row.amount / 100 if is_credit else -row.amount / 100)
        for row, is_credit in zip(rows, credits)
    ]
    stmt.ending_balance = ending_balance
    return stmt


#: Audit B9 (I13): TD Canada Trust's mail-routing code line ('TDCDA<n>_<n>_<n> ...') and the line after it, the
#: holder's name and mailing address run together, read when it closes on a province and a postal code.
_MAIL_ROUTING_LINE = re.compile(r"^TDCDA\d+_\d+_\d+\b[^\n]*\n(?P<line>[^\n]+)", re.MULTILINE)
_PROVINCE_POSTAL_CODE = re.compile(r"\b[A-Z]{2}\s+[A-Z]\d[A-Z]\s?\d[A-Z]\d\s*$")


def _holder_reading(markdown: str) -> HolderReading:
    """Audit B9 (I13): the holder's name after TD Canada Trust's mail-routing code, without the address (a numbered
    company keeps its number); NO_READING without the code line or a province and postal code. Set by
    parse_td_canada_statement on either reader's statement; `account_name` keeps the product. Owner ruling 2026-10-02
    (Q10), audit round 2, R2-OW10: with the account title that line prints after the name."""
    match = _MAIL_ROUTING_LINE.search(markdown)
    if match is None or not _PROVINCE_POSTAL_CODE.search(match.group("line").strip()):
        return NO_READING
    return read_address_line(match.group("line"))


def parse_td_canada_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    native = parse_native_td_canada_statement(markdown, base)
    if native is not None:
        return native

    if not detect(markdown).claims:
        return None

    tables = _tables(markdown)
    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "TD Canada Trust"
    stmt.currency = "CAD"
    stmt.currency_source = "institution_default"
    stmt.beginning_balance = None
    stmt.ending_balance = None
    stmt.stated_total_credits = None
    stmt.stated_total_debits = None
    stmt.stated_credit_count = None
    stmt.stated_debit_count = None
    stmt.bank_reported_average_balance = None
    stmt.bank_reported_average_label = None
    transactions: list[Transaction] = []
    pending_credit: tuple[float, str] | None = None

    for rows in tables:
        default_year = None
        in_ledger = False
        for cells in rows:
            joined = " ".join(cells)
            if "BUSINESS CHEQUING ACCOUNT" in joined.upper():
                stmt.account_name = next((c for c in cells if "BUSINESS CHEQUING ACCOUNT" in c.upper()), stmt.account_name)
                for c in cells:
                    period = _parse_period(c)
                    if period:
                        stmt.period_start, stmt.period_end = period
                        default_year = int(stmt.period_end[:4])
                continue
            account = next((c for c in cells if re.fullmatch(r"\d{4}-\d{6,}", c)), None)
            if account:
                stmt.account_number = account

            if "DESCRIPTION" in joined.upper() and "CHEQUE/DEBIT" in joined.upper():
                in_ledger = True
                if default_year is None and stmt.period_end:
                    default_year = int(stmt.period_end[:4])
                continue

            upper = joined.upper()
            if not joined or upper == "-":
                continue
            if upper.startswith("MONTHLY AVER. CR. BAL."):
                avg = next((parse_money(c) for c in cells if parse_money(c) is not None), None)
                if avg is not None:
                    stmt.bank_reported_average_balance = abs(avg)
                    stmt.bank_reported_average_label = "MONTHLY AVER. CR. BAL."
                credit = _summary_count_amount(cells, "CREDITS")
                if credit:
                    stmt.stated_credit_count = (stmt.stated_credit_count or 0) + credit[0]
                    stmt.stated_total_credits = round((stmt.stated_total_credits or 0.0) + credit[1], 2)
                continue
            if "CREDITS" in upper:
                credit = _summary_count_amount(cells, "CREDITS")
                if credit:
                    stmt.stated_credit_count = (stmt.stated_credit_count or 0) + credit[0]
                    stmt.stated_total_credits = round((stmt.stated_total_credits or 0.0) + credit[1], 2)
                continue
            if "DEBITS" in upper:
                debit = _summary_count_amount(cells, "DEBITS")
                if debit:
                    stmt.stated_debit_count = (stmt.stated_debit_count or 0) + debit[0]
                    stmt.stated_total_debits = round((stmt.stated_total_debits or 0.0) + debit[1], 2)
                continue
            if not in_ledger:
                continue
            if upper.startswith("0 CHQS ENCLOSED"):
                in_ledger = False
                continue
            if not in_ledger:
                continue

            if len(cells) < 4:
                continue
            desc, debit_cell, credit_cell, date_cell = cells[:4]
            balance_cell = cells[4] if len(cells) >= 5 else ""
            if default_year is None:
                if not stmt.period_end:
                    # No printed period evidence anywhere - rows cannot be
                    # dated; skip instead of assuming a year (R-1 item 8/9
                    # class: the previous "2025" fallback invented dates).
                    continue
                default_year = int(stmt.period_end[:4])

            if desc.upper().startswith("BALANCE FORWARD"):
                bal = parse_money(balance_cell)
                if bal is not None and stmt.beginning_balance is None:
                    stmt.beginning_balance = bal
                rest = desc[len("BALANCE FORWARD"):].strip()
                dates = _date_tokens(date_cell, default_year=default_year)
                credits = parse_money_tokens(credit_cell)
                if rest and credits and len(dates) >= 2 and len(rest.split()) <= 6:
                    transactions.append(_tx(dates[-1], rest, abs(credits[0])))
                continue

            dates = _date_tokens(date_cell, default_year=default_year)
            balance = parse_money(balance_cell)
            if _looks_like_money(date_cell):
                shifted_dates = _date_tokens(balance_cell, default_year=default_year)
                if shifted_dates:
                    shifted_amount = abs(parse_money_tokens(date_cell)[0])
                    if parse_money_tokens(debit_cell) or parse_money_tokens(credit_cell):
                        pending_credit = (shifted_amount, shifted_dates[0])
                    elif _credit_like(desc):
                        # Column-shifted amount with no printed column evidence:
                        # emit only on a generic credit signal; otherwise skip
                        # the row (fail closed) rather than guess a sign from
                        # counterparty names (R-1 item 8).
                        transactions.append(_tx(shifted_dates[0], desc, shifted_amount))
                    dates = dates or shifted_dates
                    balance = None

            if pending_credit and not parse_money_tokens(debit_cell) and not parse_money_tokens(credit_cell):
                amount, d = pending_credit
                transactions.append(_tx(d, desc, amount, balance))
                pending_credit = None
                continue

            if not dates:
                continue

            debits = [abs(v) for v in parse_money_tokens(debit_cell)]
            credits = [abs(v) for v in parse_money_tokens(credit_cell)]
            if debits:
                split_dates = dates if len(dates) == len(debits) else [dates[0]] * len(debits)
                for i, amount in enumerate(debits):
                    rb = balance if i == len(debits) - 1 else None
                    transactions.append(_tx(split_dates[i], desc, -amount, rb))
            if credits:
                # Trust the bank's printed DEPOSIT/CREDIT column. Reconciliation
                # against the stated summary fails closed downstream if the
                # extraction misplaced an amount (R-1 item 8 - merchant-name
                # sign overrides removed).
                transactions.append(_tx(dates[0], desc, credits[0], balance if not debits else None))

    if not transactions:
        return None

    if stmt.ending_balance is None:
        for t in reversed(transactions):
            if t.running_balance is not None:
                stmt.ending_balance = t.running_balance
                break

    # TD Canada prints sparse balances at selected row-group endings, not a full
    # daily closing-balance series. Use them to verify/locate the ending balance,
    # then suppress derived ADB/min/max/negative-day analytics.
    transactions = [t.model_copy(update={"running_balance": None}) for t in transactions]
    stmt.transactions = transactions
    holder = _holder_reading(markdown)
    if holder.name:
        stmt.holder_name, stmt.account_title = holder
    return stmt


def parse_native_td_canada_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    """Public entry point for the native-text TD Canada layout, registered in its
    own right by R-3. `parse_td_canada_statement` still tries it first until the
    pipeline switches to registry dispatch. Audit B9 (I13): the row reader's
    statement (`_parse_native_td_canada`, which the frozen oracle of
    tests/test_row_grouping.py compares) with the holder's name the mailing block
    prints (`_holder_reading`, with the account title printed after the name: owner ruling 2026-10-02, Q10; audit
    round 2, R2-OW10)."""
    statement = _parse_native_td_canada(markdown, base)
    if statement is not None:
        holder = _holder_reading(markdown)
        if holder.name:
            statement.holder_name, statement.account_title = holder
    return statement
