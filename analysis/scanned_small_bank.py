from __future__ import annotations

import re
from datetime import date

from .money import parse_money
from .parser_registry import make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction
from .tables import compact_whitespace
from .td_can import normalize_mojibake


_MONTH_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")
_MONEY_TOKEN_RE = re.compile(r"\$?\s*\d[\d,]*\.\d{2}")
#: Account-holder line inside the first page's address block: a name carrying
#: a business-entity suffix (structural marker - never a memorized customer
#: name, R-1 item 2).
_HOLDER_NAME_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9&'.\- ]{1,60}?,?\s*"
    r"(?:LLC|L\.L\.C\.|INC|CORP|LTD|LLP|PLLC|COMPANY|ENTERPRISES)\b\.?)",
    re.IGNORECASE,
)
#: Check-image caption printed alongside the scanned check: independent
#: in-document evidence of a check's true amount (R-1 item 1).
_CHECK_CAPTION_RE = re.compile(
    r"Number:\s*(\d{3,})\s+Date:\s*(\d{1,2}/\d{1,2}/\d{2,4})\s+"
    r"Amount:\s*\$?\s*(\d[\d,]*(?:\.\d{2})?)",
    re.IGNORECASE,
)


def _extract_holder_name(markdown: str) -> str | None:
    """Business-entity-suffixed name from the first page's header block."""
    first_page = re.split(r"--- Page 2 ---", markdown, maxsplit=1)[0]
    for line in first_page.splitlines():
        match = _HOLDER_NAME_RE.search(line)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return None


def _money(value: str) -> float:
    parsed = parse_money(value.replace("$", "").strip())
    if parsed is None:
        raise ValueError(value)
    return parsed


def _iso(value: str) -> str:
    m = _MONTH_RE.fullmatch(value.strip())
    if not m:
        raise ValueError(value)
    month, day, raw_year = m.groups()
    year = int(raw_year)
    if year < 100:
        year += 2000
    return date(year, int(month), int(day)).isoformat()


def _date_from_mdyy(value: str, *, year: int) -> str:
    month, day = [int(part) for part in value.split("/", 1)]
    return date(year, month, day).isoformat()


def _daily_balances(markdown: str) -> dict[str, float]:
    start = re.search(r"DAILY BALANCE (?:SUMMARY|INFORMATION)\b", markdown, re.IGNORECASE)
    if not start:
        return {}
    block = markdown[start.end():]
    block = re.split(
        r"(?i)(?:SUMMARY OF FEES|--- Page|\*\*\*|Member\s+FDIC|TOTAL YEAR TO DATE)",
        block,
        maxsplit=1,
    )[0]
    balances: dict[str, float] = {}
    statement_year = None
    year_match = re.search(r"\b\d{1,2}/\d{1,2}/(\d{2,4})\b", markdown)
    if year_match:
        statement_year = int(year_match.group(1))
        if statement_year < 100:
            statement_year += 2000
    for raw_date, amount in re.findall(r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+(\d[\d,]*\.\d{2})", block):
        try:
            if raw_date.count("/") == 1 and statement_year is not None:
                raw_date = f"{raw_date}/{statement_year}"
            balances[_iso(raw_date)] = _money(amount)
        except ValueError:
            continue
    return balances


def _attach_daily_balances(txns: list[Transaction], balances: dict[str, float]) -> list[Transaction]:
    if not balances:
        return txns
    last_idx_by_date: dict[str, int] = {}
    for idx, txn in enumerate(txns):
        if txn.date in balances:
            last_idx_by_date[txn.date] = idx
    out = list(txns)
    for txn_date, idx in last_idx_by_date.items():
        out[idx] = out[idx].model_copy(update={"running_balance": balances[txn_date]})
    return out


def _sort_txns(txns: list[Transaction]) -> list[Transaction]:
    return sorted(txns, key=lambda t: (t.date, 0 if t.amount > 0 else 1, t.description))


def _section(markdown: str, start: str, stop: str) -> str:
    match = re.search(
        rf"(?:{start})(.*?)(?:{stop})",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group(1) if match else ""


def _parse_date_amount_description_rows(block: str, *, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = re.match(r"^(\d{1,2}/\d{1,2}/\d{4})\s+(\d[\d,]*\.\d{2})\s+(.+)$", line)
        if not m:
            i += 1
            continue
        txn_date, amount, desc = m.groups()
        desc_parts = [desc.strip()]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt or re.match(r"^\d{1,2}/\d{1,2}/\d{4}\s+\d[\d,]*\.\d{2}\b", nxt):
                break
            if re.search(r"^(?:DATE|TOTAL|DAILY BALANCE|SERVICE CHARGE ANALYSIS|SUMMARY OF FEES)\b", nxt, re.IGNORECASE):
                break
            desc_parts.append(nxt)
            i += 1
        signed = round(abs(_money(amount)) * sign, 2)
        txns.append(Transaction(
            date=_iso(txn_date),
            description=compact_whitespace(" ".join(desc_parts)),
            amount=signed,
            direction="credit" if signed > 0 else "debit",
        ))
    return txns


def _parse_two_column_date_amount_desc(block: str, *, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    pattern = re.compile(
        r"(\d{1,2}/\d{1,2}/\d{4})\s+(\d[\d,]*\.\d{2})\s+"
        r"(.+?)(?=(?:\s+\d{1,2}/\d{1,2}/\d{4}\s+\d[\d,]*\.\d{2})|$)",
        re.DOTALL,
    )
    for txn_date, amount, desc in pattern.findall(compact_whitespace(block)):
        signed = round(abs(_money(amount)) * sign, 2)
        txns.append(Transaction(
            date=_iso(txn_date),
            description=compact_whitespace(desc),
            amount=signed,
            direction="credit" if signed > 0 else "debit",
        ))
    return txns


def _parse_checks(block: str, *, sign: int = -1) -> list[Transaction]:
    txns: list[Transaction] = []
    # Real dash characters only - the input is mojibake-normalized first
    # (R-1 item 11; the class previously carried raw mojibake bytes).
    for check_no, raw_date, amount in re.findall(
        r"\b(\d{3,})\s+\*?\s*[—–\- ]*\s*(\d{1,2}/\d{1,2}/\d{4})\s+(\d[\d,]*\.\d{2})",
        block,
    ):
        signed = round(abs(_money(amount)) * sign, 2)
        txns.append(Transaction(
            date=_iso(raw_date),
            description=f"Check {check_no}",
            amount=signed,
            direction="credit" if signed > 0 else "debit",
        ))
    return txns


def _discard_inconsistent_ocr_balances(
    stmt: Statement,
    txns: list[Transaction],
) -> list[Transaction]:
    """Ignore an OCR balance grid only after the line-item ledger proves complete."""
    if not any(txn.running_balance is not None for txn in txns):
        return txns
    required = (
        stmt.beginning_balance,
        stmt.ending_balance,
        stmt.stated_credit_count,
        stmt.stated_debit_count,
        stmt.stated_total_credits,
        stmt.stated_total_debits,
    )
    if any(value is None for value in required):
        return txns

    credits = [txn for txn in txns if txn.amount > 0]
    debits = [txn for txn in txns if txn.amount < 0]
    detail_matches_summary = (
        len(credits) == stmt.stated_credit_count
        and len(debits) == stmt.stated_debit_count
        and abs(sum(txn.amount for txn in credits) - stmt.stated_total_credits) <= 0.01
        and abs(abs(sum(txn.amount for txn in debits)) - stmt.stated_total_debits) <= 0.01
        and abs(
            stmt.beginning_balance
            + sum(txn.amount for txn in txns)
            - stmt.ending_balance
        ) <= 0.01
    )
    if not detail_matches_summary:
        return txns

    expected = stmt.beginning_balance
    for txn in txns:
        expected = round(expected + txn.amount, 2)
        if txn.running_balance is not None and abs(expected - txn.running_balance) > 0.01:
            return [
                row.model_copy(update={"running_balance": None})
                for row in txns
            ]
    return txns


def detection_text(markdown: str) -> str:
    """The text these parsers recognise themselves in: scanned sources arrive
    with double-encoded accents, so repair them before matching."""
    return normalize_mojibake(markdown).upper()


SOUTHSIDE_DETECTION_MARKERS = (
    required("bank_name", lambda t: "SOUTHSIDE" in t),
    required("summary_section", lambda t: "ACCOUNT SUMMARY" in t),
    required("product", lambda t: "BUILDER ACCOUNT" in t),
)

APEX_DETECTION_MARKERS = (
    required("product", lambda t: "SUMMIT BUSINESS CHECKING" in t),
    required("opening_label", lambda t: "BALANCE FORWARD FROM" in t),
    required("closing_label", lambda t: "ENDING BALANCE AS OF" in t),
)

detect_southside = make_detector(SOUTHSIDE_DETECTION_MARKERS, detection_text)
detect_apex = make_detector(APEX_DETECTION_MARKERS, detection_text)


def parse_southside_scanned_statement(markdown: str) -> Statement | None:
    if not detect_southside(markdown).claims:
        return None
    markdown = normalize_mojibake(markdown)
    upper = markdown.upper()

    text = compact_whitespace(markdown)
    stmt = Statement(bank="Southside Bank", currency="USD")
    # Digits must directly follow the label: an occurrence corrupted by stray
    # OCR quote glyphs is skipped in favor of a clean later occurrence
    # (R-1 item 11 - the previous class of mojibake quote characters never
    # matched real text and only obscured that behaviour).
    acct = re.search(r"Account Number\s+(\d+)", text, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    # Holder from the entity-suffix structural marker, not a memorized
    # customer name (R-1 item 2).
    stmt.account_name = _extract_holder_name(markdown)
    summary = re.search(
        r"Statement Dates\s+(?P<start>\d{1,2}/\d{1,2}/\d{2})\s+thru\s+(?P<end>\d{1,2}/\d{1,2}/\d{2})\s+"
        r"Previous Balance\s+(?P<begin>\d[\d,]*\.\d{2})\s+Days in Statement Period\s+(?P<days>\d+)\s+"
        r"\D{0,8}(?P<credit_count>\d+)\s+Deposits/Credits\s+(?P<credits>\d[\d,]*\.\d{2})\s+"
        r"\D{0,8}(?P<debit_count>\d+)\s+Checks/Debits\s+(?P<debits>\d[\d,]*\.\d{2})\s+"
        r"\D{0,8}Total Service Charge\s+(?P<service>\d[\d,]*\.\d{2})\s+\D{0,8}Interest Paid\s+(?P<interest>\d[\d,]*\.\d{2})\s+"
        r"Ending Balance\s+(?P<ending>\d[\d,]*\.\d{2})",
        text,
        re.IGNORECASE,
    )
    if not summary:
        return None
    stmt.period_start = _iso(summary.group("start"))
    stmt.period_end = _iso(summary.group("end"))
    stmt.beginning_balance = _money(summary.group("begin"))
    stmt.ending_balance = _money(summary.group("ending"))
    stmt.days_in_period = int(summary.group("days"))
    stmt.stated_credit_count = int(summary.group("credit_count"))
    stmt.stated_debit_count = int(summary.group("debit_count"))
    stmt.stated_total_credits = _money(summary.group("credits"))
    stmt.stated_total_debits = _money(summary.group("debits"))
    stmt.stated_service_charge = _money(summary.group("service"))
    stmt.stated_interest_paid = _money(summary.group("interest"))

    year = int(stmt.period_end[:4])
    deposits = _section(markdown, r"DEPOSITS.*?Date Description Amount", r"WITHDRAWALS")
    withdrawals = _section(markdown, r"WITHDRAWALS.*?Date Description Amount", r"--- Page 2 ---")
    checks = _section(markdown, r"SUMMARY BY CHECK NUMBER", r"DAILY BALANCE SUMMARY")
    txns: list[Transaction] = []
    txns.extend(_parse_southside_line_rows(deposits, year=year, sign=1))
    txns.extend(_parse_southside_line_rows(withdrawals, year=year, sign=-1))
    txns.extend(_parse_southside_checks(checks, year=year))
    txns = _repair_checks_from_image_captions(markdown, txns, stmt)
    txns = _attach_daily_balances(_sort_txns(txns), _daily_balances(markdown))
    txns = _discard_inconsistent_ocr_balances(stmt, txns)
    if len(txns) < (stmt.stated_credit_count or 0):
        return None
    stmt.transactions = txns
    return stmt


def _parse_two_column_mdyy_rows(block: str, *, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    block = re.sub(r"(?i)\b(?:ae|if|cy|z)\s+(?=\d{1,2}/\d{2}\b)", " ", block)
    block = re.sub(r"[;:]\s+(?=\d{1,2}/\d{2}\b)", " ", block)
    pattern = re.compile(
        r"(\d{1,2}/\d{2})\s+(.+?)\s+(\d[\d,]*\.\d{2})(?=(?:\s+\d{1,2}/\d{2}\s)|$)",
        re.DOTALL,
    )
    for mmdd, desc, amount in pattern.findall(compact_whitespace(block)):
        signed = round(abs(_money(amount)) * sign, 2)
        txns.append(Transaction(
            date=_date_from_mdyy(mmdd, year=year),
            description=compact_whitespace(desc),
            amount=signed,
            direction="credit" if signed > 0 else "debit",
        ))
    return txns


def _parse_southside_line_rows(block: str, *, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for raw in block.splitlines():
        line = re.sub(r"(?i)^\W*(?:ae|if|cy|z|ee|a)\s+", "", raw.strip())
        line = re.sub(r"(?i)^\W+", "", line)
        date_start = re.search(r"\d{1,2}/\d{2}\b|\b\d{3}\s+", line)
        if date_start:
            line = line[date_start.start():]
        line = re.sub(r"^(\d)(\d{2})\s+", r"\1/\2 ", line)
        m = re.match(r"^(\d{1,2}/\d{2})\s+(.+?)\s+(\d[\d,]*\.\d{2})\s*$", line)
        if not m:
            continue
        mmdd, desc, amount = m.groups()
        signed = round(abs(_money(amount)) * sign, 2)
        txns.append(Transaction(
            date=_date_from_mdyy(mmdd, year=year),
            description=compact_whitespace(desc),
            amount=signed,
            direction="credit" if signed > 0 else "debit",
        ))
    return txns


def _summary_identity_holds(stmt: Statement, txns: list[Transaction]) -> bool:
    """Detail matches every printed summary figure (counts, totals, balances)."""
    required = (
        stmt.beginning_balance,
        stmt.ending_balance,
        stmt.stated_credit_count,
        stmt.stated_debit_count,
        stmt.stated_total_credits,
        stmt.stated_total_debits,
    )
    if any(value is None for value in required):
        return False
    credits = [txn for txn in txns if txn.amount > 0]
    debits = [txn for txn in txns if txn.amount < 0]
    return (
        len(credits) == stmt.stated_credit_count
        and len(debits) == stmt.stated_debit_count
        and abs(sum(t.amount for t in credits) - stmt.stated_total_credits) <= 0.01
        and abs(abs(sum(t.amount for t in debits)) - stmt.stated_total_debits) <= 0.01
        and abs(
            stmt.beginning_balance + sum(t.amount for t in txns) - stmt.ending_balance
        ) <= 0.01
    )


def _repair_checks_from_image_captions(
    markdown: str, txns: list[Transaction], stmt: Statement
) -> list[Transaction]:
    """Correct OCR-misread check amounts from the check-image captions.

    Generic, evidence-gated (R-1 item 1 - replaces a repair keyed to one
    literal date/check/amount): the statement's own check-image captions
    ("Number: N  Date: m/d/yyyy  Amount: $X") are independent in-document
    evidence. A parsed "Check N" row is corrected to its caption amount only
    when (a) the printed summary identity currently fails, (b) the caption
    matches the row's check number AND date but disagrees on amount, and
    (c) applying the corrections makes the summary identity hold exactly.
    """
    captions: dict[tuple[str, str], float] = {}
    for check_no, raw_date, amount in _CHECK_CAPTION_RE.findall(markdown):
        try:
            captions[(check_no, _iso(raw_date))] = _money(amount)
        except ValueError:
            continue
    if not captions or _summary_identity_holds(stmt, txns):
        return txns

    repaired: list[Transaction] = []
    changed = False
    for txn in txns:
        match = re.fullmatch(r"Check (\d+)", txn.description)
        caption_amount = captions.get((match.group(1), txn.date)) if match else None
        if caption_amount is not None and abs(abs(txn.amount) - caption_amount) > 0.01:
            corrected = round(abs(caption_amount), 2)
            repaired.append(
                txn.model_copy(
                    update={"amount": -corrected if txn.amount < 0 else corrected}
                )
            )
            changed = True
        else:
            repaired.append(txn)
    if changed and _summary_identity_holds(stmt, repaired):
        return repaired
    return txns


def _parse_southside_checks(block: str, *, year: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for raw_date, check_no, amount in re.findall(r"(\d{1,2}/\d{2})\s+(\d{3,})\s+(\d[\d,]*\.\d{2})", block):
        txns.append(Transaction(
            date=_date_from_mdyy(raw_date, year=year),
            description=f"Check {check_no}",
            amount=round(-abs(_money(amount)), 2),
            direction="debit",
        ))
    return txns


def parse_apex_scanned_statement(markdown: str) -> Statement | None:
    # Structural gates only: the bank's product name plus this layout's
    # summary phrasing (R-1 item 2 - the customer-name gate is gone).
    if not detect_apex(markdown).claims:
        return None
    markdown = normalize_mojibake(markdown)
    upper = markdown.upper()

    source = re.sub(r"(?<=\d)\.(?=\d{3}\.\d{2}\b)", ",", markdown)
    text = compact_whitespace(source)
    holder = _extract_holder_name(markdown)
    stmt = Statement(bank="Apex Bank", account_name=holder, currency="USD")
    acct = re.search(r"Account Number:\s*([*%A-Z0-9]+)", text, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    sm = re.search(
        r"Balance Forward From\s+(?P<start>\d{2}/\d{2}/\d{4})\s+(?P<begin>\d[\d,]*\.\d{2}).*?"
        r"(?P<credit_count>\d+)\s+Deposits/Credits.*?(?P<credits>\d[\d,]*\.\d{2})\s+\+.*?"
        r"Minimum Balance.*?(?P<min>\d[\d,]*\.\d{2}).*?"
        r"(?P<debit_count>\d+)\s+Withdrawals/Debits.*?(?P<debits>\d[\d,]*\.\d{2})\s+-.*?"
        r"Average Balance.*?(?P<avg>\d[\d,]*\.\d{2}).*?"
        r"Ending Balance As Of\s+(?P<end>\d{2}/\d{2}/\d{4})\s+(?P<ending>\d[\d,]*\.\d{2}).*?"
        r"Interest Paid This Period.*?(?P<interest>\d[\d,]*\.\d{2}).*?"
        r"Days In Earnings Period.*?(?P<days>\d+)",
        text,
        re.IGNORECASE,
    )
    if not sm:
        return None
    stmt.period_start = _iso(sm.group("start"))
    stmt.period_end = _iso(sm.group("end"))
    stmt.beginning_balance = _money(sm.group("begin"))
    stmt.ending_balance = _money(sm.group("ending"))
    stmt.days_in_period = int(sm.group("days"))
    stmt.stated_credit_count = int(sm.group("credit_count"))
    stmt.stated_debit_count = int(sm.group("debit_count"))
    stmt.stated_total_credits = _money(sm.group("credits"))
    stmt.stated_total_debits = _money(sm.group("debits"))
    printed_average = _money(sm.group("avg"))
    stmt.bank_reported_average_balance = printed_average
    stmt.bank_reported_average_label = (
        "Average Balance" if printed_average is not None else None
    )
    stmt.stated_interest_paid = _money(sm.group("interest"))
    deposits = _section(
        source,
        r"DATE AMOUNT DESCRIPTION\s+DATE AMOUNT DESCRIPTION",
        r"OTHER CREDITS",
    )
    credits = _section(
        source,
        r"OTHER CREDITS.*?DATE AMOUNT DESCRIPTION",
        r"CHECK NO DATE AMOUNT CHECK NO DATE AMOUNT",
    )
    checks = _section(
        source,
        r"CHECK NO DATE AMOUNT CHECK NO DATE AMOUNT",
        r"[^\n]*denotes missing check[^\n]*",
    )
    debits = _section(
        source,
        r"[^\n]*denotes missing check[^\n]*",
        r"SERVICE CHARGES",
    )
    if holder:
        # Continuation pages repeat the holder's header block up to the
        # re-printed column header; scrub it using the holder name extracted
        # from the document itself (R-1 item 2 - no memorized name).
        debits = re.sub(
            r"\s*--- Page \d+ ---\s+" + re.escape(holder) + r".*?DATE AMOUNT DESCRIPTION\s*",
            "\n",
            debits,
            flags=re.IGNORECASE | re.DOTALL,
        )
    service = _section(
        source,
        r"SERVICE CHARGES.*?DATE AMOUNT DESCRIPTION",
        r"S[EF]RVICE CHARGE ANALY",
    )
    fees = _section(
        source,
        r"FEES\s*CHARGED.*?DATE AMOUNT DESCRIPTION",
        r"TOTAL FEES",
    )

    txns: list[Transaction] = []
    txns.extend(_parse_two_column_date_amount_desc(deposits, sign=1))
    txns.extend(_parse_date_amount_description_rows(credits, sign=1))
    txns.extend(_parse_checks(checks, sign=-1))
    txns.extend(_parse_date_amount_description_rows(debits, sign=-1))
    txns.extend(_parse_date_amount_description_rows(service, sign=-1))
    txns.extend(_parse_date_amount_description_rows(fees, sign=-1))
    txns = _repair_checks_from_image_captions(source, txns, stmt)
    txns = _attach_daily_balances(_sort_txns(txns), _daily_balances(source))
    txns = _discard_inconsistent_ocr_balances(stmt, txns)
    # Completeness against the statement's own printed counts, not a magic
    # threshold (R-1 item 3 - was `len(txns) < 20`).
    stated_rows = (stmt.stated_credit_count or 0) + (stmt.stated_debit_count or 0)
    if stated_rows == 0 or len(txns) < stated_rows:
        return None
    stmt.transactions = txns
    return stmt


# ---------------------------------------------------------------------------
# Texas First Bank, photographed: the four-way partition whose split is not
# printed anywhere (W3 §SCANNEXT)
# ---------------------------------------------------------------------------
#
# The template prints a summary that states BOTH counts and BOTH totals, then
# spends the rest of the statement on four separately-headed grids::
#
#     Summary of Activity Since Your Last Statement
#       Beginning Balance   m/d/yy   b0
#       Deposits / Misc Credits    N   C
#       Withdrawals / Misc Debits  M   D
#     ** Ending Balance     m/d/yy   b1 **
#
#     Deposits and Other Credits      date  amount  description
#     Debits and Other Withdrawals    date  amount  description
#     ATM /POS Transactions           date  DEPOSITS | WITHDRAWALS  location
#     Checks                          three (date, check no, amount) columns
#     Daily Balance Summary           three (date, balance) columns
#
# **The ATM/POS grid is the whole difficulty.** It has TWO money columns —
# deposits and withdrawals — and the scan destroys the only thing that says
# which column a figure sat in: Tesseract collapses the run of spaces, so
# `4/07 300.00 ATM Withdrawal` and `4/16 300.00 ATM Cash Deposit` arrive as the
# same shape. The direction is therefore NOT read off the row.
#
# Neither is it guessed from the words. `ATM Cash Deposit`, `ATM Withdrawal`,
# `Debit Transfer`, `POS Purchase Non-PIN`, `POS Purchase with PIN` are five of
# this family's wordings and a sixth statement is free to print a seventh; a
# reader that memorised them would be reading its own list rather than the
# document, and `Debit Transfer` — the most common of them — is a WITHDRAWAL on
# one row and the deposit leg of a peer-to-peer transfer on another.
#
# The direction is SOLVED from arithmetic the bank prints twice, and the
# solution is checked against a third printing:
#
# 1. **The aggregate.** The summary's counts and totals cover the ATM grid too,
#    so what the grid contributes to each side is fixed by subtraction::
#
#        ATM deposits    = (N - rows in Deposits, C - total of Deposits)
#        ATM withdrawals = (M - rows in Debits - rows in Checks,
#                           D - total of Debits - total of Checks)
#
#    Both sides must come out non-negative, and their counts and totals must
#    add back to the grid's own row count and total. That is a statement about
#    the grids' COMPLETENESS - it is what catches the row Tesseract dropped -
#    and it is checked before the walk because it is cheap.
#
# 2. **The day.** `Daily Balance Summary` prints the end-of-day balance for
#    every day the account moved, so each day's NET is known before any ATM row
#    is directed. The day's ATM rows admit one sign assignment reproducing that
#    net — and this reader requires it to be UNIQUE (:func:`_tf_unique_subset`).
#    Two assignments reaching the same net differ by which row is the deposit,
#    and publishing either would be publishing a direction the document does
#    not determine. Ambiguity refuses the document.
#
# 3. **The closing identity**, `b0 + C - D == b1`, checked first because it is
#    one line of arithmetic on figures already in hand and it rejects a
#    mis-read summary before a grid is parsed. It is a fail-fast, not
#    independent evidence: once (1) and (2) hold it follows.
#
# **A negative balance prints its minus on the RIGHT** (`1,420.04 -`), the same
# convention `analysis/balance_by_date.py` documents for its average-balance
# statistic. Three of the eight archive documents print at least one overdrawn
# day and one of them prints three; reading those as positive would publish a
# five-figure error into the ADB, so the trailing hyphen is part of the daily
# cell's grammar here and a LEADING minus is never a sign. The convention is
# not asserted — it is proven by the walk: on every document this reader
# publishes, every printed daily balance is reproduced to the cent, overdrawn
# days included.
#
# **Every daily cell must be legible.** A daily line carrying a residue that
# still contains digits after its cells are matched means the grid did not
# survive the scan, and the ADB is computed over that grid — so the document is
# refused rather than published with a hole. Measured on the archive: this
# refuses `9B3DB6CF...`, whose `5/22` cell Tesseract resolved as `714,71`
# (the decimal separator read as a comma). The ledger determines that day's
# balance as `714.71` exactly, so the printing is recoverable in principle —
# recorded in W3 §SCANNEXT as a card, not repaired here, because the repair
# needs its own evidence gate and this reader's contract is that the grid it
# publishes is the grid the bank printed.
#
# The issuer IS named on the page (unlike the core-processor templates), so
# `Statement.bank` carries it.

#: A printed figure on this template: always two decimals. Bounded on both
#: sides so a reference number cannot supply the head of one.
_TF_FIGURE = r"(?<![\d.,])\d[\d,]{0,15}\.\d{2}(?![\d,]*\d)"
#: A posting date inside the grids: month and day only, the year is the
#: period's (see :func:`_tf_iso`).
_TF_MD = r"\d{1,2}/\d{1,2}"

_TF_SECTION_RE = re.compile(
    r"^(?:(?P<credits>Deposits and Other Credits)"
    r"|(?P<debits>Debits and Other Withdrawals)"
    r"|(?P<atm>ATM\s*/\s*POS\s+Transactions)"
    r"|(?P<checks>Checks)"
    r"|(?P<daily>Daily Balance Summary))\s*$",
    re.IGNORECASE,
)
_TF_PAGE_RE = re.compile(r"^---\s*Page\s+\d+")
_TF_COLUMN_HEAD_RE = re.compile(r"^Date\b", re.IGNORECASE)
_TF_DETAIL_RE = re.compile(rf"^({_TF_MD})\s+({_TF_FIGURE})\s+(\S.*)$")
#: One cell of the three-column check grid. The check number is optional
#: because the scan loses it on some rows, and the `*` the bank prints for a
#: break in check-number sequence may arrive with or without a number.
_TF_CHECK_CELL_RE = re.compile(rf"({_TF_MD})\s+(?:(\d{{2,7}})\s*\*?\s+|\*\s+)?({_TF_FIGURE})")
#: One cell of the three-column daily grid, with the right-hand minus.
_TF_DAILY_CELL_RE = re.compile(rf"({_TF_MD})\s+({_TF_FIGURE})\s*(-)?")

_TF_SUMMARY_BEGIN_RE = re.compile(
    rf"Beginning Balance\s+(\d{{1,2}}/\d{{1,2}}/\d{{2,4}})\s+({_TF_FIGURE})", re.IGNORECASE
)
_TF_SUMMARY_END_RE = re.compile(
    rf"Ending Balance\s+(\d{{1,2}}/\d{{1,2}}/\d{{2,4}})\s+({_TF_FIGURE})", re.IGNORECASE
)
_TF_SUMMARY_CREDITS_RE = re.compile(
    rf"Deposits\s*/\s*Misc Credits\s+(\d{{1,6}})\s+({_TF_FIGURE})", re.IGNORECASE
)
_TF_SUMMARY_DEBITS_RE = re.compile(
    rf"Withdrawals\s*/\s*Misc Debits\s+(\d{{1,6}})\s+({_TF_FIGURE})", re.IGNORECASE
)
_TF_SERVICE_CHARGE_RE = re.compile(rf"^Service Charge\s+({_TF_FIGURE})\s*$", re.IGNORECASE | re.M)
#: The bank's own average, printed in WHOLE DOLLARS on this template. Evidence
#: only — `analysis/adb.py` owns the canonical figure (ADB doctrine).
_TF_AVERAGE_RE = re.compile(
    r"^Average Balance\s+(\d[\d,]{0,15}(?:\.\d{2})?)\s*$", re.IGNORECASE | re.M
)

TEXAS_FIRST_DETECTION_MARKERS = (
    # The issuer's own tele-banking domain, printed in the page furniture of
    # every page of the statement.
    required("tele_banking_domain", lambda t: "WWW.TEXASFIRST.BANK" in t),
    # This template's summary head.
    required("summary_head", lambda t: "SUMMARY OF ACTIVITY SINCE YOUR LAST STATEMENT" in t),
    # The grid this reader's day oracle is built on. Required at DETECTION and
    # not only at parse: a printing without it is not a document this reader
    # can direct the ATM grid on, and claiming it would strand it.
    required("daily_grid", lambda t: "DAILY BALANCE SUMMARY" in t),
)

detect_texas_first = make_detector(TEXAS_FIRST_DETECTION_MARKERS, detection_text)


def _tf_cents(token: str) -> int | None:
    value = parse_money(token.replace("$", "").strip())
    return None if value is None else int(round(value * 100))


def _tf_one(pattern: re.Pattern[str], source: str):
    """The document's single reading of a summary term, or None.

    `search` alone would take the first occurrence and never notice a second,
    so a statement whose summary is printed twice — a continuation page
    reprinting it, a two-account document, an OCR duplication — could publish
    one account's figures under another's heading and look perfectly ordinary.
    A repeat that AGREES is free corroboration and is accepted; a repeat that
    disagrees is the document contradicting itself and refuses it.
    """
    matches = pattern.findall(source)
    if not matches or len(set(matches)) > 1:
        return None
    return pattern.search(source)


def _tf_iso(mmdd: str, *, start: date, end: date) -> str | None:
    """The posting date's ISO form, or None when it is not inside the period.

    The grids print month and day only. The year comes from the printed period
    and from nowhere else: a date that lands outside it under either candidate
    year is a mis-read, and this returns None so the document fails closed
    rather than acquiring a transaction in the wrong year.
    """
    month_s, _, day_s = mmdd.partition("/")
    for year in {start.year, end.year}:
        try:
            candidate = date(year, int(month_s), int(day_s))
        except ValueError:
            continue
        if start <= candidate <= end:
            return candidate.isoformat()
    return None


def _tf_unique_subset(values: list[int], target: int) -> set[int] | None:
    """Indices of the ONE subset of `values` summing to `target`, else None.

    `values` are positive cent amounts and `target` is the deposit-side total
    the printed daily balance implies, so a subset is a direction assignment.
    Counting is capped at two: the question is not how many assignments exist
    but whether exactly one does, and a second one means the document does not
    determine the directions.
    """
    if target < 0 or target > sum(values):
        return None
    # sum -> (how many subsets reach it, capped at 2; one witness)
    states: dict[int, tuple[int, tuple[int, ...]]] = {0: (1, ())}
    for index, value in enumerate(values):
        nxt = dict(states)
        for reached, (count, witness) in states.items():
            moved = reached + value
            if moved > target:
                continue
            prior_count, prior_witness = nxt.get(moved, (0, ()))
            nxt[moved] = (
                min(2, prior_count + count),
                prior_witness if prior_count else witness + (index,),
            )
        states = nxt
        # A pathological day would make this exponential. The archive's widest
        # is eleven rows; refusing beyond a wide bound keeps a hostile document
        # from turning a parse into a hang.
        if len(states) > 100_000:
            return None
    count, witness = states.get(target, (0, ()))
    return set(witness) if count == 1 else None


class _TFRow:
    """One printed ledger row before its direction is known."""

    __slots__ = ("iso", "cents", "description")

    def __init__(self, iso: str, cents: int, description: str) -> None:
        self.iso, self.cents, self.description = iso, cents, description


def _tf_read_grids(markdown: str, *, start: date, end: date):
    """(credits, debits, atm, checks, daily) or None when a grid is illegible.

    `daily` is `[(iso, cents)]` in printed order. The section state resets at
    every page break: this template reprints each section's head after the page
    furniture, so a row can never be attributed to the section that ended on
    the previous page.
    """
    credits: list[_TFRow] = []
    debits: list[_TFRow] = []
    atm: list[_TFRow] = []
    checks: list[_TFRow] = []
    daily: list[tuple[str, int]] = []
    buckets = {"credits": credits, "debits": debits, "atm": atm}

    section: str | None = None
    pending: list[str] | None = None      # the open detail row's description
    open_row: _TFRow | None = None

    def close_row() -> None:
        nonlocal pending, open_row
        if open_row is not None and pending is not None:
            open_row.description = compact_whitespace(" ".join(pending))
        pending, open_row = None, None

    for raw in markdown.splitlines():
        line = raw.strip()
        if _TF_PAGE_RE.match(line):
            close_row()
            section = None
            continue
        head = _TF_SECTION_RE.match(line)
        if head is not None:
            close_row()
            section = head.lastgroup
            continue
        if section is None or not line:
            continue

        if section in buckets:
            row = _TF_DETAIL_RE.match(line)
            if row is not None:
                close_row()
                iso = _tf_iso(row.group(1), start=start, end=end)
                cents = _tf_cents(row.group(2))
                if iso is None or cents is None:
                    return None
                open_row = _TFRow(iso, cents, row.group(3).strip())
                pending = [row.group(3).strip()]
                buckets[section].append(open_row)
            elif pending is not None and not _TF_COLUMN_HEAD_RE.match(line):
                pending.append(line)
            continue

        # The two three-column grids. Their bodies are cells and nothing else,
        # so the first body line with no cell in it ends the grid — which is
        # what keeps the closing disclosure paragraph and its URL out of them.
        cells = list(
            (_TF_CHECK_CELL_RE if section == "checks" else _TF_DAILY_CELL_RE).finditer(line)
        )
        if not cells:
            if _TF_COLUMN_HEAD_RE.match(line):
                continue
            section = None
            continue
        residue = line
        for cell in reversed(cells):
            residue = residue[: cell.start()] + residue[cell.end():]
        if any(character.isdigit() for character in residue):
            # A cell that did not survive the scan. Both grids are oracles —
            # the check grid feeds the debit count, the daily grid feeds the
            # ADB — so an illegible cell fails the document closed.
            return None
        for cell in cells:
            iso = _tf_iso(cell.group(1), start=start, end=end)
            cents = _tf_cents(cell.group(3) if section == "checks" else cell.group(2))
            if iso is None or cents is None:
                return None
            if section == "checks":
                number = cell.group(2)
                checks.append(_TFRow(iso, cents, f"Check {number}" if number else "Check"))
            else:
                daily.append((iso, -cents if cell.group(3) else cents))
    close_row()
    return credits, debits, atm, checks, daily


def _tf_direct_atm(
    *,
    beginning: int,
    daily: list[tuple[str, int]],
    credits: list[_TFRow],
    debits: list[_TFRow],
    atm: list[_TFRow],
    checks: list[_TFRow],
) -> set[int] | None:
    """Indices of the ATM rows that are DEPOSITS, or None if not determined.

    Walks the printed daily balances in date order. Every day carrying a
    ledger row must have a printed balance (a day the grid does not mention is
    a day the grid lost), every printed balance must be reproduced exactly, and
    each day's ATM rows must admit exactly one sign assignment.
    """
    printed: dict[str, int] = {}
    for iso, balance in daily:
        if printed.setdefault(iso, balance) != balance:
            return None                      # the grid contradicts itself
    known: dict[str, int] = {}
    for row in credits:
        known[row.iso] = known.get(row.iso, 0) + row.cents
    for row in (*debits, *checks):
        known[row.iso] = known.get(row.iso, 0) - row.cents
    day_atm: dict[str, list[int]] = {}
    for index, row in enumerate(atm):
        day_atm.setdefault(row.iso, []).append(index)
    if set(known) - set(printed) or set(day_atm) - set(printed):
        return None

    deposits: set[int] = set()
    balance = beginning
    for iso in sorted(printed):
        target = printed[iso]
        residual = target - balance - known.get(iso, 0)
        indices = day_atm.get(iso, [])
        values = [atm[i].cents for i in indices]
        # sum(deposits) - sum(withdrawals) == residual, so the deposit side
        # totals (residual + everything) / 2.
        doubled = residual + sum(values)
        if doubled % 2:
            return None
        chosen = _tf_unique_subset(values, doubled // 2)
        if chosen is None:
            return None
        deposits.update(indices[i] for i in chosen)
        balance = target
    return deposits


def parse_texas_first_scanned_statement(markdown: str) -> Statement | None:
    if not detect_texas_first(markdown).claims:
        return None
    source = normalize_mojibake(markdown)

    begin = _tf_one(_TF_SUMMARY_BEGIN_RE, source)
    end = _tf_one(_TF_SUMMARY_END_RE, source)
    credit_summary = _tf_one(_TF_SUMMARY_CREDITS_RE, source)
    debit_summary = _tf_one(_TF_SUMMARY_DEBITS_RE, source)
    if not (begin and end and credit_summary and debit_summary):
        return None
    try:
        period_start = date.fromisoformat(_iso(begin.group(1)))
        period_end = date.fromisoformat(_iso(end.group(1)))
    except ValueError:
        return None
    if period_end < period_start:
        return None

    beginning_cents = _tf_cents(begin.group(2))
    ending_cents = _tf_cents(end.group(2))
    stated_credits = _tf_cents(credit_summary.group(2))
    stated_debits = _tf_cents(debit_summary.group(2))
    if None in (beginning_cents, ending_cents, stated_credits, stated_debits):
        return None
    stated_credit_count = int(credit_summary.group(1))
    stated_debit_count = int(debit_summary.group(1))
    # The fail-fast: a mis-read summary is rejected before a grid is parsed.
    if beginning_cents + stated_credits - stated_debits != ending_cents:
        return None

    grids = _tf_read_grids(source, start=period_start, end=period_end)
    if grids is None:
        return None
    credits, debits, atm, checks, daily = grids
    if not daily:
        return None

    # What the ATM grid has to contribute to each side, by subtraction from the
    # bank's own counts and totals.
    atm_credit_count = stated_credit_count - len(credits)
    atm_credit_cents = stated_credits - sum(row.cents for row in credits)
    atm_debit_count = stated_debit_count - len(debits) - len(checks)
    atm_debit_cents = stated_debits - sum(row.cents for row in debits) - sum(
        row.cents for row in checks
    )
    # Fail-fasts, in the same spirit as the closing identity above: cheap
    # arithmetic that rejects a mis-read grid before the day walk is run. Both
    # are deliberately redundant with the checks that follow the walk —
    # measured by mutation, removing either still refuses every document of the
    # archive family, because a grid whose rows do not add up cannot reproduce
    # the printed daily balances either. They are kept because a reader that
    # only ever discovers this inside the walk reports "the day did not close"
    # for a defect that is really "the grid is short a row".
    if min(atm_credit_count, atm_credit_cents, atm_debit_count, atm_debit_cents) < 0:
        return None
    if atm_credit_count + atm_debit_count != len(atm):
        return None
    if atm_credit_cents + atm_debit_cents != sum(row.cents for row in atm):
        return None

    deposit_indices = _tf_direct_atm(
        beginning=beginning_cents, daily=daily,
        credits=credits, debits=debits, atm=atm, checks=checks,
    )
    if deposit_indices is None:
        return None
    # The two readings of the same split, made to agree explicitly.
    #
    # Stated precisely, because it would be easy to overclaim here: once the
    # day walk has a UNIQUE assignment on every day, the split is determined,
    # and the money half of this pair follows from the arithmetic (summing the
    # daily residuals gives `atm_credit_cents - atm_debit_cents`, and the
    # aggregate fail-fast above gives the sum, so the deposit total is fixed).
    # These are therefore corroboration and not a further independent oracle.
    # They are kept because the derivation above depends on every one of those
    # earlier checks still being in place, and a reader that publishes a split
    # its own summary contradicts is not a thing to leave to a proof.
    if len(deposit_indices) != atm_credit_count:
        return None
    if sum(atm[i].cents for i in deposit_indices) != atm_credit_cents:
        return None
    # The grid is printed in THREE COLUMNS, so its last CELL is not its last
    # DAY - taking reading position for chronology here would compare the
    # ending balance against whatever day sits at the foot of column three.
    last_day = max(iso for iso, _ in daily)
    if next(cents for iso, cents in daily if iso == last_day) != ending_cents:
        return None

    transactions: list[Transaction] = []
    for row in credits:
        transactions.append(Transaction(
            date=row.iso, description=row.description,
            amount=round(row.cents / 100, 2), direction="credit",
        ))
    for row in (*debits, *checks):
        transactions.append(Transaction(
            date=row.iso, description=row.description,
            amount=round(-row.cents / 100, 2), direction="debit",
        ))
    for index, row in enumerate(atm):
        credit = index in deposit_indices
        transactions.append(Transaction(
            date=row.iso, description=row.description,
            amount=round((row.cents if credit else -row.cents) / 100, 2),
            direction="credit" if credit else "debit",
        ))

    stmt = Statement(
        bank="Texas First Bank",
        account_name=_extract_holder_name(source),
        currency="USD",
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        beginning_balance=round(beginning_cents / 100, 2),
        ending_balance=round(ending_cents / 100, 2),
        stated_credit_count=stated_credit_count,
        stated_debit_count=stated_debit_count,
        stated_total_credits=round(stated_credits / 100, 2),
        stated_total_debits=round(stated_debits / 100, 2),
    )
    # `account_number` stays None, deliberately. This template prints the
    # number masked in the header block, and on EVERY archive document of the
    # class the mask is what the scan destroys: `Account Number: FAKKAT AG`,
    # `Account Number: *AKKT BGO`. Masks that DO survive elsewhere on the page
    # belong to the ATM rows' card numbers (`*****5512`, `*****8152`) and to
    # the cheque images - reading one of those into this field would publish a
    # card as an account. Honest-unknown is the answer the document supports.
    service = _tf_one(_TF_SERVICE_CHARGE_RE, source)
    if service is not None:
        charge = _tf_cents(service.group(1))
        if charge is not None:
            stmt.stated_service_charge = round(charge / 100, 2)
    average = _tf_one(_TF_AVERAGE_RE, source)
    if average is not None:
        printed_average = parse_money(average.group(1))
        if printed_average is not None:
            # Evidence, never the platform's ADB: this template rounds its own
            # average to whole dollars, and `analysis/adb.py` owns the
            # canonical figure (ADB doctrine, 2026-08-15).
            stmt.bank_reported_average_balance = printed_average
            stmt.bank_reported_average_label = "Average Balance"
    stmt.stated_daily_balances = [
        StatementDailyBalance(date=iso, balance=round(cents / 100, 2))
        for iso, cents in daily
    ]
    stmt.transactions = _attach_daily_balances(
        _sort_txns(transactions), {iso: round(cents / 100, 2) for iso, cents in daily}
    )
    return stmt
