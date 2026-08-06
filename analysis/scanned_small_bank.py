from __future__ import annotations

import re
from datetime import date

from .money import parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
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
    stmt.stated_average_balance = _money(sm.group("avg"))
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
