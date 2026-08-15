from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_from_month_day
from .money import parse_digit_scrubbed
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import compact_whitespace, table_rows



#: A Capital One amount cell as printed: optional parenthesis/minus/dollar
#: wrapper around a grouped decimal. `parse_digit_scrubbed` keeps only digits
#: and dots, so without a guard it does not READ a cell, it renders any text
#: as a number — `Page 3 of 8` scrubbed to 38.0 and `REF#000000012345` to
#: 12345.0, both of which the two-cell summary reader and the detail reader
#: pass through. `money.py` documents the guard as existing for exactly this
#: (`AmountFormat.pattern`: "silently mis-reading a reference number as an
#: amount is the failure mode this guard exists to prevent").
#:
#: Measured against every cell this parser passes to `_money` over its whole
#: claimed population plus its class-1 declines (28 documents, 5,238 distinct
#: cells): 0 refused. The printed shapes are `1,234.56`, `$1,234.56` and
#: `($1,234.56)`; the sign markers are admitted because the call below honours
#: them, not because the archive prints them.
_AMOUNT_RE = re.compile(r"\(?-?\$?\s*[0-9][0-9,]*(?:\.[0-9]{2})?-?\)?")


def _money(value: str) -> float | None:
    return parse_digit_scrubbed(
        value, parens=True, leading_minus=True, trailing_minus=True, guard=_AMOUNT_RE
    )


#: A summary money cell as Capital One prints it. The bank BRACKETS a cell to
#: mark it negative, so the bracket is there exactly when there is a sign to
#: mark: a cycle in which nothing was charged prints `Service Charges $0.00`,
#: never `($0.00)`. Requiring the bracket made the parser refuse 10 documents
#: whose only distinction was that the customer had been charged nothing —
#: the shape of the cell is a money cell either way, and `_money` reads the
#: bracket as the sign it is.
_SUMMARY_CELL = r"(\(?\$[\d,]+\.\d{2}\)?)"


#: How each printed summary cell is published. Capital One brackets a cell to
#: mark it NEGATIVE, so the printed sign is real information and reading it is
#: not optional — especially now that the unbracketed form of a non-zero cell
#: parses at all (it did not before `_SUMMARY_CELL`).
#:
#: The rule, applied deliberately and identically to all three totals:
#:
#: * BALANCES (`Previous`, `Ending`, `Average Collected`) are published SIGNED.
#:   An overdrawn account really does print `($59.78)` and really is negative.
#: * TOTALS (`Deposits/Credits`, `Checks/Debits`, `Service Charges`) are
#:   published as the POSITIVE MAGNITUDE the schema specifies for each of them.
#:   The printed sign is still read, and used to CHECK that the cell points the
#:   way its column requires — credits in, debits and charges out. `abs()` on
#:   its own cannot do that: it maps `($15.00)` and `$15.00` onto the same
#:   published 15.00, so a service charge and a service-charge REFUND become
#:   indistinguishable, and a bracketed `Deposits/Credits` would publish a
#:   negative total with no summary identity check downstream to catch it.
#:
#: A cell whose printed sign contradicts its column is REFUSED, not silently
#: normalised: no such document exists in the archive, so publishing a guess
#: about one would be inventing a reading rather than reporting one.
def _magnitude(value: float | None, *, outflow: bool) -> float | None:
    """The published magnitude of a total, or None if it points the wrong way."""
    if value is None:
        return None
    if outflow and value > 0:
        return None
    if not outflow and value < 0:
        return None
    return abs(value)


def _native_summary(markdown: str, stmt: Statement) -> tuple[Statement, float | None]:
    m = re.search(
        r"Previous Balance\s+\d{2}/\d{2}/\d{2}\s+" + _SUMMARY_CELL + r"\s+"
        r"Number of Days in Cycle\s+(\d+)\s+"
        r"(\d+)\s+Deposits/Credits\s+" + _SUMMARY_CELL + r"\s+"
        r"Minimum Balance This Cycle\s+\(?\$[\d,]+\.\d{2}\)?\s+"
        r"(\d+)\s+Checks/Debits\s+" + _SUMMARY_CELL + r"\s+"
        r"Average Collected Balance\s+" + _SUMMARY_CELL + r"\s+"
        r"Service Charges\s+" + _SUMMARY_CELL + r"\s+"
        r"Ending Balance\s+\d{2}/\d{2}/\d{2}\s+" + _SUMMARY_CELL,
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return stmt, None
    beginning, days, credit_count, credits, debit_count, debits, avg, fees, ending = m.groups()
    charge = _money(fees)
    total_credits = _magnitude(_money(credits), outflow=False)
    total_debits = _magnitude(_money(debits), outflow=True)
    service_charge = _magnitude(charge, outflow=True)
    if total_credits is None or total_debits is None or service_charge is None:
        # A printed cell contradicts its own column. The summary is not read.
        return stmt, None
    return stmt.model_copy(update={
        "beginning_balance": _money(beginning),
        "days_in_period": int(days),
        "stated_credit_count": int(credit_count),
        "stated_total_credits": total_credits,
        "stated_debit_count": int(debit_count),
        "stated_total_debits": total_debits,
        "bank_reported_average_balance": _money(avg),
        "bank_reported_average_label": "Average Collected Balance",
        "stated_service_charge": service_charge,
        "ending_balance": _money(ending),
    }), charge


def _native_transactions(markdown: str, *, year: int, beginning_balance: float | None) -> list[Transaction]:
    detail = re.search(
        r"ACCOUNT DETAIL\s+FOR PERIOD.*?(?=Total For This Period|Date Service Description|PAGE \d+ OF \d+\s*$|$)",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not detail:
        return []
    text = re.sub(r"\s+", " ", detail.group(0))
    row_re = re.compile(
        r"(\d{2}/\d{2})\s+(.+?)\s+\$([\d,]+\.\d{2})\s+(\(?\$[\d,]+\.\d{2}\)?)"
        r"(?=\s+\d{2}/\d{2}\s+[A-Za-z]|\s+Total\s+\$|\s+Thank you\b|\s+PAGE\s+\d+\s+OF\b|"
        r"\s+Products and services\b|\s+--- Page\b|\s+Total For This Period\b|\s+Date Service Description\b|$)",
        re.DOTALL,
    )
    txns: list[Transaction] = []
    prev_balance = beginning_balance
    for m in row_re.finditer(text):
        txn_date, desc, raw_amount, raw_balance = m.groups()
        balance = _money(raw_balance)
        amount = _money(raw_amount)
        if balance is None or amount is None:
            continue
        if prev_balance is not None:
            signed = round(balance - prev_balance, 2)
            if abs(abs(signed) - abs(amount)) > 0.01:
                signed = amount if _looks_like_credit(desc) else -abs(amount)
        else:
            signed = amount if _looks_like_credit(desc) else -abs(amount)
        txns.append(Transaction(
            date=iso_from_month_day(txn_date, year),
            description=re.sub(r"\s+", " ", desc).strip(),
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=balance,
        ))
        prev_balance = balance
    return txns


def _looks_like_credit(description: str) -> bool:
    desc = description.upper()
    return any(token in desc for token in (
        "DEPOSIT",
        "MONEY RECEIVED",
        "TRANSFER RECEIVED",
        "INSTANT TRANSFER RECEIVED",
        "ATM CASH DEPOSIT",
        "DEBIT CARD MONEY RECEIVED",
    ))


#: The account line, where a layout prints one: the product the account is,
#: followed by its number, alone on its line — `Business Enhanced Checking
#: 123456789`. Read STRUCTURALLY (a capitalised multi-word product name and a
#: run of account digits), never by naming a product.
#:
#: This parser published `account_name="Business Basic Checking"` on every
#: document it read — the same R-1 class as the us_bank product name, and a
#: worse instance of it: the phrase is printed in NONE of the 22 documents this
#: parser validates. Its only occurrence anywhere is in a FILENAME, which
#: `analyze_markdown` strips at the admissibility boundary before any parser
#: sees the text, so it was never evidence in the first place. The native
#: layout prints no product line at all, so the honest reading of these
#: statements is that the product is not stated — `None`, not a guess.
_ACCOUNT_LINE_RE = re.compile(
    r"^(?P<product>[A-Z][A-Za-z]*(?:[ /][A-Z][A-Za-z]*){1,5})\s+(?P<number>\d{6,})\s*$",
    re.MULTILINE,
)


def _account_line(markdown: str) -> tuple[str | None, str | None]:
    m = _ACCOUNT_LINE_RE.search(markdown)
    if m is None:
        return None, None
    return compact_whitespace(m.group("product")), m.group("number")


def _period(markdown: str) -> tuple[str, str] | None:
    m = re.search(
        r"ACCOUNT SUMMARY\s+FOR PERIOD\s+([A-Z]+)\s+(\d{1,2}),\s+(\d{4})\s+-\s+([A-Z]+)\s+(\d{1,2}),\s+(\d{4})",
        markdown,
        re.IGNORECASE,
    )
    if not m:
        return None
    months = {
        "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6,
        "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12,
    }
    sm, sd, sy, em, ed, ey = m.groups()
    start = date(int(sy), months[sm.upper()], int(sd)).isoformat()
    end = date(int(ey), months[em.upper()], int(ed)).isoformat()
    return start, end


#: The ledger wording that names a cycle charge outright.
_CYCLE_CHARGE_RE = re.compile(r"\b(?:maintenance|cycle service)\s+charge\b", re.IGNORECASE)

#: What a bank-imposed fee is CALLED in this ledger, as against what a purchase
#: is called. Every fee row the archive prints at a cycle boundary is one of
#: `Service charge`, `Maintenance charge`, `NSF charge`, `Cash deposit limit
#: exceeded`. This is the bank's own fee lexicon — the same class of knowledge
#: as a column heading, keyed on no customer, amount, date or account.
#:
#: It is REQUIRED by the arithmetic arm below and that requirement is load
#: bearing: amount-and-window alone re-dates any debit that happens to equal
#: the printed charge, so a $12.00 purchase posted the day after a cycle that
#: printed a ($12.00) charge would be silently moved AND relabelled as a
#: charge. Matching the amount says only that two numbers agree.
_FEE_SHAPED_RE = re.compile(
    r"\b(?:charge|charges|fee|fees|nsf|overdraft|penalty)\b|\blimit\s+exceeded\b",
    re.IGNORECASE,
)


def _is_cycle_charge(txn: Transaction, printed_charge: float | None) -> bool:
    """Is this row the charge the summary states for the cycle?

    Two readings, either sufficient.

    The first is the bank's ledger wording, unchanged: a row that calls itself
    a maintenance or cycle service charge is one.

    The second is the bank's own arithmetic, and it is deliberately narrow: a
    row that (a) is worded like a fee at all, (b) is a debit, and (c) equals the
    printed `Service Charges` figure with the SAME SIGN. Sign, not magnitude:
    Capital One brackets a cell to mark it negative, so a charge prints
    `($12.00)` and reads back as −12.00, and comparing magnitudes would let a
    printed service-charge REFUND stand in for a charge.

    That identification is corroborated independently by the printed counts:
    `N Checks/Debits` counts every debit row EXCEPT the one the service-charge
    total covers, and it is short by exactly one on every document that prints
    a non-zero charge and exact on every document that prints a zero one.
    """
    if _CYCLE_CHARGE_RE.search(txn.description):
        return True
    return (
        printed_charge is not None
        and printed_charge < 0
        and txn.amount < 0
        and abs(txn.amount - printed_charge) < 0.005
        and bool(_FEE_SHAPED_RE.search(txn.description))
    )


def _normalize_cycle_service_charge_dates(
    transactions: list[Transaction], period_end: str,
    printed_charge: float | None = None,
) -> list[Transaction]:
    """Apply cycle charges printed after a short cycle to its final cycle day."""
    end = date.fromisoformat(period_end)
    normalized: list[Transaction] = []
    for txn in transactions:
        posted = date.fromisoformat(txn.date)
        if _is_cycle_charge(txn, printed_charge) and 0 < (posted - end).days <= 3:
            txn = txn.model_copy(
                update={
                    "date": period_end,
                    "description": f"{txn.description} (printed {posted.isoformat()})",
                }
            )
        normalized.append(txn)
    return normalized


DETECTION_MARKERS = (
    required("bank_name", lambda t: "CAPITALONE" in t.upper().replace(" ", "")),
    # The bank name alone is not evidence the bank ISSUED the statement: a card
    # payment to Capital One puts it in 38 of the 109 corpus documents, from
    # Truist to Wells Fargo to RBC. Pair it with a section heading Capital One
    # prints on its own statements (R3_DETECTION_FINDING.md).
    required("issuer_notice", lambda t: "AN IMPORTANT MESSAGE TO OUR CLIENTS" in t.upper()),
)

detect = make_detector(DETECTION_MARKERS)


def parse_capital_one_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    if not re.search(r"ACCOUNT SUMMARY\s+FOR PERIOD", markdown, re.IGNORECASE):
        return None

    period = _period(markdown)
    if period is None:
        return None
    period_start, period_end = period
    year = int(period_end[:4])

    product, number = _account_line(markdown)
    stmt = Statement(
        bank="Capital One",
        account_name=product,
        period_start=period_start,
        period_end=period_end,
    )
    if number is not None:
        stmt.account_number = number

    rows = table_rows(markdown)
    prev_balance = stmt.beginning_balance
    in_detail = False
    txns: list[Transaction] = []
    #: The printed service charge WITH its sign, for the cycle-charge guard.
    #: `stated_service_charge` is published as a magnitude, and a magnitude
    #: cannot tell a charge from a refund.
    signed_charge: float | None = None

    for cells in rows:
        if len(cells) == 2:
            label, raw = cells
            value = _money(raw)
            low = label.lower()
            if "previous balance" in low:
                stmt.beginning_balance = value
                prev_balance = value
            elif "deposits/credits" in low:
                count = re.search(r"\b(\d+)\b", label)
                stmt.stated_credit_count = int(count.group(1)) if count else stmt.stated_credit_count
                stmt.stated_total_credits = value
            elif "checks/debits" in low:
                count = re.search(r"\b(\d+)\b", label)
                stmt.stated_debit_count = int(count.group(1)) if count else stmt.stated_debit_count
                stmt.stated_total_debits = abs(value) if value is not None else None
            elif "service charge" in low:
                signed_charge = value
                stmt.stated_service_charge = abs(value) if value is not None else None
            elif "ending balance" in low:
                stmt.ending_balance = value
            elif "number of days" in low and value is not None:
                stmt.days_in_period = int(abs(value))
            elif "average collected balance" in low:
                stmt.bank_reported_average_balance = value
                # The printed cell, not the pattern that matched it.
                stmt.bank_reported_average_label = label.strip() or None
            continue

        if len(cells) >= 5 and [c.lower() for c in cells[:5]] == [
            "date", "description", "deposits/credits", "withdrawals/debits", "resulting balance",
        ]:
            in_detail = True
            continue
        if not in_detail or len(cells) < 5:
            continue
        if cells[0].lower() == "total":
            in_detail = False
            continue
        if not re.fullmatch(r"\d{2}/\d{2}", cells[0]):
            continue
        balance = _money(cells[4])
        if balance is None:
            continue
        printed_credit = _money(cells[2])
        printed_debit = _money(cells[3])
        if prev_balance is not None:
            amount = round(balance - prev_balance, 2)
        elif printed_credit is not None:
            amount = round(abs(printed_credit), 2)
        elif printed_debit is not None:
            amount = -round(abs(printed_debit), 2)
        else:
            continue
        txns.append(Transaction(
            date=iso_from_month_day(cells[0], year),
            description=cells[1],
            amount=amount,
            direction="credit" if amount >= 0 else "debit",
            running_balance=balance,
        ))
        prev_balance = balance

    if not txns:
        stmt, signed_charge = _native_summary(markdown, stmt)
        txns = _native_transactions(markdown, year=year, beginning_balance=stmt.beginning_balance)

    if not txns or stmt.beginning_balance is None or stmt.ending_balance is None:
        return None
    stmt.transactions = _normalize_cycle_service_charge_dates(
        txns, period_end, signed_charge
    )
    return stmt
