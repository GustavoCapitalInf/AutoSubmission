"""A credit-union MEMBER statement: several of one member's accounts, on one PDF.

THE TEMPLATE, NOT AN ISSUER
---------------------------
This reads a core processor's member-statement paper — the layout that opens
with an enumerating table of the member's deposit accounts, states a COLUMN
CAPTION saying which figure is which, and then prints each enumerated account as
its own section under its own printed identity. It is registered on that
furniture and on nothing that names a bank, so an issuer nobody has met yet is
read by the same registration.

`Statement.bank` is `None` and that is the honest answer rather than a gap: this
template prints no institution NAME in its text layer at all — a masthead line
welding a street address, a phone number and a contact domain together — and the
honest-unknown-issuer ruling (W3 §JHA J9.2) says publish the absence rather than
a guess. Naming the first domain on the page would publish a contact host as a
bank, and naming a bank from the folder or the filename is refused outright
(R-4b). The registry's label therefore names the TEMPLATE.

WHAT IT ESTABLISHES, AND WHAT IT REFUSES
-----------------------------------------
The boundary mechanism is `rollup-oracle` (design §2.2): the document enumerates
its accounts with a balance each, and each enumerated identity reappears as a
section heading. That REAPPEARANCE is the boundary — a printed partition, not an
inferred one — and L1-C1 refuses everything else. Concretely, the reader refuses
the document, publishing nothing, when:

* the enumerating table prints no COLUMN CAPTION from L1-C5's closed vocabulary
  (`_ROLLUP_COLUMN_ROLES`). Without one, which figure in a row is the closing is
  not printed anywhere, and taking the first is a guess one issue in this
  population falsifies. 30 of the archive's 214 enumerating tables print such a
  caption and 184 print none;
* an enumerated identity does not reappear as a section heading, or a section
  heading is not enumerated (L1-C1), or two of them resolve to one identity
  (L1-C3);
* a section prints no opening caption, or no closing caption, or the two
  disagree with the row the table prints for that account (L1-C6, L1-C10);
* the enumerated closings do not sum to the cross-account total the document
  prints for itself, where it prints one (L1-C10);
* a printed dated row inside a section's own ledger region is not accounted for
  by the ledger this reader publishes (L1-C7) — including a row whose running
  balance does not follow from the one before it;
* a section publishes NOTHING and prints no evidence of its own empty state that
  L1-C17's closed vocabulary can name (R-a, L1-C4). Absence is never a ground.

WHAT IT PUBLISHES
------------------
One `Statement` per account that posts, in PRINTED ORDER, each with its own
period, opening, closing, ledger and stated totals, each handed to the UNCHANGED
validator (R-b). The first is returned through the registration; the whole
partition goes to `analysis/multi_account.py` for the document entry point,
carrying each section's OWN TEXT so the ADB's source-coverage check is applied
against that account's paper and not against its siblings'.

A section that posts nothing and prints evidence of its empty state is OMITTED —
recorded with the class that admitted it, published as a gap, never dropped
(L1-C17). On this template that class is normally
`printed_pair_coincides_and_no_row_printed`, whose seventh condition is the
enumerating table reproducing the section's closing — measured section by
section by `tools/q3_corroboration_probe.py` before this reader was written.

NO FIGURE IS INVENTED. Every amount published here is a token the paper printed:
the section's own opening and closing captions, its own ledger rows, and the
DEPOSITS / WITHDRAWALS columns of the row the enumerating table prints for that
account under a caption that names them. The roll-up is also an ORACLE — every
figure it supplies is cross-checked against the section's own arithmetic, and a
disagreement refuses rather than choosing a winner.
"""
from __future__ import annotations

import re
from datetime import date

from .date_tokens import (
    MONTH_NAME_ALT,
    PERIOD_DASH,
    iso_from_month_day_year,
    iso_from_named_month_day,
    year_within_period,
)
from .money import parse_money
from .multi_account import (
    PublishedAccount,
    RollupEvidence,
    publish_partition,
)
from .parser_registry import make_detector, required, corroborating
from .schema import Statement, Transaction
from .sibling_omission import (
    RollupWitness,
    SectionLedger,
    evidence_class,
    publish_omissions,
)

# ---------------------------------------------------------------------------
# printed furniture
# ---------------------------------------------------------------------------

#: A money token as this template prints it: grouped thousands and exactly two
#: decimals, not welded to a longer number. Deliberately STRICTER than the
#: shared tolerant reader's token — a bare integer is an identity token, a check
#: number or a page number on this paper, and admitting one would read a suffix
#: as an amount. `analysis.money.parse_money` reads each matched token.
_MONEY = r"\$?\d{1,3}(?:,\d{3})*\.\d{2}"
_MONEY_TOKEN = re.compile(r"(?<![\d.,])" + _MONEY + r"(?![\d.,]?\d)")

#: A cent. Two figures the paper prints to the cent COINCIDE when they differ by
#: less than half of one.
_CENT = 0.005

#: The statement period, printed on EVERY page of this template as a caption and
#: two `MM/DD/YY` tokens. Read once for the document and handed to every section
#: (design §2.4): this paper prints one cycle for all of a member's accounts.
_PERIOD_RE = re.compile(
    r"Statement\s+Dates?\s*:\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*"
    + PERIOD_DASH
    + r"\s*(\d{1,2}/\d{1,2}/\d{2,4})",
    re.IGNORECASE,
)

#: L1-C5's closed vocabulary, as this reader needs it: the COLUMN CAPTION an
#: enumerating table prints, mapped to what each of its columns HOLDS. The
#: caption itself names the columns in order, so the mapping is the paper's own
#: statement about its table and never a position this reader chose.
#:
#: One member today, because one caption class is what this template prints and
#: a class nobody has measured is not evidence. A new caption is admitted by
#: adding its printed wording and its roles here — never by falling back to
#: position, which is what L1-C5 exists to forbid.
_ROLLUP_COLUMN_ROLES: dict[str, tuple[str, ...]] = {
    "type_prev_dep_wd_end": ("open", "credit_total", "debit_total", "close"),
}

_ROLLUP_HEADERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "type_prev_dep_wd_end",
        re.compile(
            r"ACCOUNT\s+TYPE\s+PREVIOUS\s+BALANCE\s+DEPOSITS\s+WITHDRAWALS\s+"
            r"ENDING\s+BALANCE",
            re.IGNORECASE,
        ),
    ),
)

#: The caption the document prints over its enumerating table, together with the
#: cross-account total it closes with. The total is an ORACLE (L1-C10): the
#: enumerated closings must sum to it, and a mismatch refuses the DOCUMENT.
_ROLLUP_TOTAL_RE = re.compile(
    r"Statement\s+Summary[^\n]*?Total\s+Balance\s*:\s*(" + _MONEY + r")",
    re.IGNORECASE,
)

#: How this template prints an account's IDENTITY, both in the enumerating table
#: and on the section heading. The token is a SUFFIX — a two-or-more digit
#: product suffix, not an account number — and it is used to LOCATE a section
#: and to bind it to its table row. It is never published.
_IDENTITY = r"Suffix\s*#\s*(\d{2,})"

#: One enumerated row: the printed product LABEL, the identity token, and the
#: row's money block.
_ROLLUP_ROW_RE = re.compile(
    r"^[ \t]*(?P<label>[A-Za-z][^\n(]*?)\s*\(\s*" + _IDENTITY + r"\s*\)"
    r"(?P<block>(?:[ \t]*" + _MONEY + r")+)[ \t]*$",
    re.MULTILINE,
)

#: A section heading: the same label and identity, followed by the section's OWN
#: printed opening caption and figure. This is the reappearance L1-C1 requires,
#: and it is what makes the boundary printed rather than inferred.
_SECTION_HEAD_RE = re.compile(
    r"^[ \t]*(?P<label>[A-Za-z][^\n]*?)\s+" + _IDENTITY
    + r"\s+Previous\s+Balance\s*:\s*(?P<open>" + _MONEY + r")[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)

#: The same account's heading where its ledger continues on a later page.
_SECTION_CONT_RE = re.compile(
    r"^[ \t]*(?P<label>[A-Za-z][^\n]*?)\s+" + _IDENTITY + r"\s*\(\s*Cont\s*\)[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)

#: The section's OWN printed closing caption. It is also the section's printed
#: END: everything the page prints after it belongs to the document's trailing
#: furniture — a check recapitulation, a fee block, a year-to-date summary — and
#: reading a section to the next heading instead would sweep those in. That is
#: the very ambiguity the design's strict after-chain bound could not resolve
#: (§2.6), and a printed terminator resolves it.
_SECTION_END_RE = re.compile(
    r"Ending\s+Balance\s*:\s*(?P<close>" + _MONEY + r")", re.IGNORECASE
)

#: The ledger's own column caption. Its presence is what says the region below a
#: heading is a ledger at all.
_GRID_HEADER_RE = re.compile(
    r"TRAN\s+DATE\s+POST\s+DATE\s+DESCRIPTION\s+WITHDRAWALS\s+DEPOSITS\s+BALANCE",
    re.IGNORECASE,
)

#: The DIRECTION of a row, as the paper prints it in the row's own type column.
#: Read, never inferred: the sign of a posting is a printed word here, and the
#: running balance is then required to agree with it (`_read_rows`).
_DIRECTIONS: dict[str, int] = {
    "deposit": 1,
    "withdrawal": -1,
    "draft": -1,
}
_DIRECTION_ALT = "|".join(sorted(_DIRECTIONS, key=len, reverse=True))

#: A word this template prints IN FRONT of the direction word, qualifying the
#: posting without changing its direction. Measured over the family rather than
#: guessed: the type column prints `Withdrawal` 809 times, `Deposit` 343,
#: `Draft` 46 and `Recurring Withdrawal` 8, and nothing else. A qualifier is
#: read here so it cannot be mistaken for a direction, and the row's printed
#: RUNNING BALANCE checks the direction either way.
_DIRECTION_QUALIFIERS = ("Recurring",)
_QUALIFIER_ALT = "|".join(_DIRECTION_QUALIFIERS)

#: A word this template prints AFTER the direction word that REVERSES it. A
#: `Withdrawal Adjustment` is money coming back into the account — the row
#: adjusts a posting of that type rather than making one — and the paper says so
#: twice: in this word and in the running balance, which rises.
#:
#: Read rather than inferred, and CHECKED rather than trusted: the balance walk
#: in `_read_rows` requires every row's printed balance to follow from the
#: direction this word produced, so an adjustment that did NOT reverse would
#: refuse the section instead of being mis-signed. Measured over the family: 6
#: rows on 4 documents, `Withdrawal Adjustment` every one, the balance rising
#: every one.
_DIRECTION_REVERSAL = "Adjustment"

#: One posting. The grid's caption names TWO date columns — `TRAN DATE` and
#: `POST DATE` — and the paper prints the second one only where it differs from
#: the first, which on this archive is 29 rows across the family.
#:
#: **The POST date is the one published**, and the choice is the ADB doctrine
#: rather than a preference: the balance column is the account's own running
#: ledger and it moves on the day the bank POSTS, so attributing the movement to
#: the transaction date would put a printed balance on a day the paper says it
#: did not hold. Where only one date is printed the two are the same date and
#: the question does not arise.
_ROW_RE = re.compile(
    r"^[ \t]*(?P<month>" + MONTH_NAME_ALT + r")(?![A-Za-z])\.?[ \t]+(?P<day>\d{1,2})"
    r"(?:[ \t]+(?P<post_month>" + MONTH_NAME_ALT + r")(?![A-Za-z])\.?"
    r"[ \t]+(?P<post_day>\d{1,2}))?"
    r"[ \t]+(?P<qualifier>(?:" + _QUALIFIER_ALT + r")(?![A-Za-z])[ \t]+)?"
    r"(?P<direction>" + _DIRECTION_ALT + r")(?![A-Za-z])"
    r"(?P<reversal>[ \t]+" + _DIRECTION_REVERSAL + r"(?![A-Za-z]))?"
    r"(?P<description>[^\n]*?)"
    r"[ \t]+(?P<amount>" + _MONEY + r")[ \t]+(?P<balance>" + _MONEY + r")[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)

#: A line that OPENS with a month and a day and carries a money token. Every one
#: inside a section's ledger region must be a row this reader read (L1-C7): a
#: printed posting the ledger does not carry is a truncated ledger, and a
#: truncated ledger that still reconciles is exactly the failure the ADB's
#: source-coverage check exists to catch.
_DATED_LINE_RE = re.compile(
    r"^[ \t]*(?:" + MONTH_NAME_ALT + r")(?![A-Za-z])\.?[ \t]+\d{1,2}\b[^\n]*"
    + _MONEY + r"[^\n]*$",
    re.MULTILINE | re.IGNORECASE,
)

#: A stated counts / totals row printed FOR a section, and a daily-balance
#: table printed BY one. Neither exists on this template, and both are read
#: rather than assumed away: they are two of the seven conditions of the Q3
#: omission class, and a class decided from an assumption is not measured.
_COUNTS_ROW_RE = re.compile(
    r"\b\d+\s+total\s+(?:debits|credits|deposits|withdrawals|checks)\b"
    r"|\btotal\s+(?:deposits?|withdrawals?|debits?|credits?|checks?)\b",
    re.IGNORECASE,
)
_DAILY_CAPTION_RE = re.compile(
    r"(?<!average )(?<!avg )(?<!avg\. )\bdaily balance", re.IGNORECASE
)
_DAILY_ROW_RE = re.compile(
    r"(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?"
    r"|\b(?:" + MONTH_NAME_ALT + r")(?![A-Za-z])\.?\s+\d{1,2}\b)"
    r"[^\n\d]{0,12}?" + _MONEY,
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# detection
# ---------------------------------------------------------------------------


def _prints_a_column_caption(text: str) -> bool:
    return any(pattern.search(text) for _name, pattern in _ROLLUP_HEADERS)


def _enumerates_at_least_two_sections(text: str) -> bool:
    """Two or more printed section headings, each with its own identity.

    TWO, because this registration reads a MEMBER statement — a document that
    enumerates one account is a document about one account and belongs to
    whatever reads that issuer's single-account paper. It is also the
    anti-collision clause (R4-3): a document that merely quotes a caption
    prints no section heading at all.
    """
    identities: set[str] = set()
    for match in _SECTION_HEAD_RE.finditer(text):
        identities.add(match.group(1))
        if len(identities) > 1:
            return True
    return False


DETECTION_MARKERS = (
    required("rollup_column_roles", _prints_a_column_caption),
    required("enumerated_member_sections", _enumerates_at_least_two_sections),
    corroborating("ledger_grid_header", lambda t: bool(_GRID_HEADER_RE.search(t))),
)

detect = make_detector(DETECTION_MARKERS)


# ---------------------------------------------------------------------------
# the enumerating table, read as EVIDENCE
# ---------------------------------------------------------------------------


class _RollupRow:
    """One enumerated account, as the table prints it."""

    __slots__ = ("label", "identity", "figures")

    def __init__(self, label: str, identity: str, figures: dict[str, float]) -> None:
        self.label = label
        self.identity = identity
        self.figures = figures


def _money_tokens(text: str) -> list[float]:
    """Every strict money token in a flattened cell, in printed order."""
    values = []
    for match in _MONEY_TOKEN.finditer(text):
        value = parse_money(match.group(0))
        if value is None:
            return []
        values.append(value)
    return values


def _read_rollup(markdown: str) -> tuple[str | None, list[_RollupRow], float | None]:
    """`(caption_class, rows, cross_account_total)` — the table as an ORACLE.

    `caption_class` is `None` where the table prints no column caption from
    L1-C5's closed vocabulary, and then NO row is returned at all: a row whose
    column roles the paper does not state supplies nothing, because the only
    alternative is to read it by position and position is not evidence.
    """
    caption = next(
        (name for name, pattern in _ROLLUP_HEADERS if pattern.search(markdown)), None
    )
    if caption is None:
        return None, [], None
    roles = _ROLLUP_COLUMN_ROLES[caption]
    rows: list[_RollupRow] = []
    for match in _ROLLUP_ROW_RE.finditer(markdown):
        values = _money_tokens(match.group("block"))
        if len(values) != len(roles):
            # The row does not fit the caption's own columns. Refused rather
            # than trimmed: a row of the wrong width is a row this reader did
            # not read, and guessing which figure went missing is the guess
            # L1-C5 forbids.
            continue
        rows.append(_RollupRow(
            label=match.group("label").strip(),
            identity=match.group(2),
            figures=dict(zip(roles, values)),
        ))
    total_match = _ROLLUP_TOTAL_RE.search(markdown)
    total = parse_money(total_match.group(1)) if total_match else None
    return caption, rows, total


# ---------------------------------------------------------------------------
# the printed partition
# ---------------------------------------------------------------------------


class _Section:
    """One printed account section, located by its own heading."""

    __slots__ = ("label", "identity", "opening", "closing", "text", "ledger")

    def __init__(self, label: str, identity: str, opening: float,
                 closing: float, text: str, ledger: str) -> None:
        self.label = label
        self.identity = identity
        self.opening = opening
        self.closing = closing
        #: The section's own paper: its heading through its own printed closing.
        self.text = text
        #: The part of it below the ledger's column caption — where a posting
        #: is printed, and the only region a dated row is looked for in.
        self.ledger = ledger


def _locate_sections(markdown: str) -> list[_Section] | None:
    """Every account section the document prints, in PRINTED ORDER.

    A section runs from its own heading to its own printed `Ending Balance`,
    and an account whose ledger continues over a page break is ONE section: its
    continuation headings carry the same identity, and the span therefore ends
    at the closing the LAST of them prints. `None` where a heading prints no
    closing at all — a section whose end the paper does not state is a section
    this reader has not read to the end of.
    """
    headings: list[tuple[int, str, str, float | None]] = []
    for match in _SECTION_HEAD_RE.finditer(markdown):
        opening = parse_money(match.group("open"))
        if opening is None:
            return None
        headings.append((match.start(), match.group("label").strip(),
                         match.group(2), opening))
    for match in _SECTION_CONT_RE.finditer(markdown):
        headings.append((match.start(), match.group("label").strip(),
                         match.group(2), None))
    if not headings:
        return None
    headings.sort(key=lambda item: item[0])

    # Group CONSECUTIVE headings that carry one identity: that run is one
    # account's printed blocks, and the next identity opens the next account.
    sections: list[_Section] = []
    index = 0
    while index < len(headings):
        start, label, identity, opening = headings[index]
        if opening is None:
            # A continuation with no heading before it. The document printed a
            # ledger whose account this reader cannot name — refuse rather than
            # attribute it to whatever came before.
            return None
        run_end = index + 1
        while run_end < len(headings) and headings[run_end][2] == identity:
            run_end += 1
        region_end = headings[run_end][0] if run_end < len(headings) else len(markdown)
        region = markdown[start:region_end]
        end_match = _SECTION_END_RE.search(region)
        if end_match is None:
            return None
        closing = parse_money(end_match.group("close"))
        if closing is None:
            return None
        text = region[: end_match.end()]
        # L1-C2 / L1-C7's other half: the sections are DISJOINT and cover the
        # ledger region completely. Everything the paper prints between this
        # section's own closing and the next account's heading is trailing
        # furniture — a check recapitulation, a fee block, a year-to-date
        # summary, a page masthead — and none of it opens with a posting date.
        # A dated line there is a posting this reader did not read: a section
        # printed TWICE (a page-break reprint that lost its continuation word),
        # or a ledger that runs on past the closing it claims to have reached.
        # Refused, because the alternative is publishing an account whose rows
        # the document also prints somewhere this reader is not looking.
        if _DATED_LINE_RE.search(region[end_match.end():]):
            return None
        grid = _GRID_HEADER_RE.search(text)
        sections.append(_Section(
            label=label, identity=identity, opening=opening, closing=closing,
            text=text, ledger=text[grid.end():] if grid else "",
        ))
        index = run_end
    return sections


# ---------------------------------------------------------------------------
# the ledger
# ---------------------------------------------------------------------------


def _read_rows(
    section: _Section, start: date, end: date
) -> list[tuple[Transaction, int]] | None:
    """The section's postings, or `None` where the paper contradicts the reader.

    Each posting is returned with the COLUMN the paper printed it in — `+1` for
    the deposits column, `-1` for the withdrawals column — which is not the same
    as the sign of its amount: a printed reversal is a NEGATIVE entry in the
    column it adjusts. The caller needs both, because the ledger is built from
    the signed amount and the table's own totals are per column.

    Three refusals, and each one is a printed disagreement rather than a
    tolerance:

    * a line that OPENS with a month and a day and carries money, inside the
      ledger region, that this reader did not read as a row (L1-C7). A printed
      posting the published ledger does not carry is a truncated ledger;
    * a row whose printed date falls outside the printed period;
    * a row whose printed running balance does not follow from the previous
      balance and this row's own printed direction and amount. The direction is
      read from the row's own type WORD, and the balance is what CHECKS it — so
      a word this reader mapped to the wrong sign cannot go unnoticed.
    """
    rows: list[tuple[Transaction, int]] = []
    balance = section.opening
    for match in _ROW_RE.finditer(section.ledger):
        month = match.group("post_month") or match.group("month")
        day = match.group("post_day") or match.group("day")
        year = year_within_period(_month_number(month), int(day), start, end)
        if year is None:
            return None
        iso = iso_from_named_month_day(month, day, year)
        if iso is None:
            return None
        amount = parse_money(match.group("amount"))
        printed_balance = parse_money(match.group("balance"))
        if amount is None or printed_balance is None:
            return None
        column = _DIRECTIONS[match.group("direction").lower()]
        sign = -column if match.group("reversal") else column
        signed = round(sign * abs(amount), 2)
        if abs(round(balance + signed, 2) - printed_balance) > _CENT:
            return None
        balance = printed_balance
        rows.append((Transaction(
            date=iso,
            description=" ".join(part for part in (
                (match.group("qualifier") or "").strip(),
                match.group("direction"),
                (match.group("reversal") or "").strip(),
                match.group("description").strip(),
            ) if part),
            amount=signed,
            direction="credit" if signed > 0 else "debit",
            running_balance=printed_balance,
        ), column))
    if len(_DATED_LINE_RE.findall(section.ledger)) != len(rows):
        return None
    if rows and abs(balance - section.closing) > _CENT:
        return None
    return rows


def _month_number(word: str) -> int:
    from .date_tokens import MONTH_NUMBERS

    return MONTH_NUMBERS[word.strip().casefold()]


# ---------------------------------------------------------------------------
# the reader
# ---------------------------------------------------------------------------


def _period(markdown: str) -> tuple[str, str] | None:
    match = _PERIOD_RE.search(markdown)
    if match is None:
        return None
    try:
        start = iso_from_month_day_year(match.group(1), century="short")
        end = iso_from_month_day_year(match.group(2), century="short")
    except ValueError:
        return None
    return (start, end) if start <= end else None


def _witness_for(section: _Section, caption: str | None,
                 rows: list[_RollupRow]) -> RollupWitness:
    """Condition 7's facts for one section: the roll-up row bound BOTH ways.

    The section's row is located twice — once by the printed LABEL and once by
    the printed IDENTITY TOKEN — and the witness stands only where the two find
    the SAME row. Neither handle is reliably the discriminating one on this
    family (`W3 §Q3PROBE` Q3PROBE8): on one document the label matches the
    sibling's reprinted headings as well and only the token is unique, and on
    two others it is the other way round. A witness bound by one handle where
    the other disagrees is a MIS-BINDING, and a mis-binding cannot be seen from
    inside the row it produced.
    """
    if caption is None or not rows:
        return RollupWitness()
    by_label = [index for index, row in enumerate(rows)
                if row.label.casefold() == section.label.casefold()]
    by_identity = [index for index, row in enumerate(rows)
                   if row.identity == section.identity]
    label_row = by_label[0] if len(by_label) == 1 else None
    identity_row = by_identity[0] if len(by_identity) == 1 else None
    agree = label_row is not None and label_row == identity_row
    return RollupWitness(
        printed=True,
        column_roles_printed=True,
        row_located_by_label=label_row is not None,
        row_located_by_identity=identity_row is not None,
        locators_agree=agree,
        closing=rows[label_row].figures.get("close") if agree else None,
    )


def parse_member_statement(markdown: str) -> Statement | None:
    """Every account this member statement prints, or nothing at all.

    Returns the FIRST published account, which is what a registration returns
    and what `analyze_markdown` has always answered with; the whole partition
    goes to `analysis/multi_account.py` so the DOCUMENT entry point can build
    one independently validated report per account (R-b).

    Fail-closed at every step: the document is published only when its printed
    partition is complete — every enumerated account either published or
    omitted on printed evidence L1-C17 can name — and refused otherwise.
    """
    if not detect(markdown).claims:
        return None
    period = _period(markdown)
    if period is None:
        return None
    start, end = date.fromisoformat(period[0]), date.fromisoformat(period[1])

    caption, rollup_rows, cross_total = _read_rollup(markdown)
    if caption is None or not rollup_rows:
        return None  # L1-C1 / L1-C5: no printed partition, no published account
    sections = _locate_sections(markdown)
    if not sections:
        return None

    # L1-C3: the identities are distinct, on BOTH sides of the reappearance.
    identities = [section.identity for section in sections]
    row_identities = [row.identity for row in rollup_rows]
    if len(set(identities)) != len(identities):
        return None
    if len(set(row_identities)) != len(row_identities):
        return None
    # L1-C1: the reappearance itself, in both directions. An enumerated account
    # with no section is an account this reader cannot account for; a section
    # the table does not enumerate is a boundary the table did not establish.
    if set(identities) != set(row_identities):
        return None

    # L1-C10, the document-level half: the enumerated closings sum to the total
    # the document prints for ITSELF. An ORACLE — it refuses the document and
    # never becomes a published value.
    rows_by_identity = {row.identity: row for row in rollup_rows}
    if cross_total is not None:
        enumerated = sum(row.figures["close"] for row in rollup_rows)
        if abs(enumerated - cross_total) > _CENT:
            return None

    published: list[PublishedAccount] = []
    ledger = SectionLedger()
    for section in sections:
        row = rows_by_identity[section.identity]
        # L1-C6 / L1-C10, the section-level half: what the section prints about
        # itself and what the table prints about it must agree to the cent.
        if abs(row.figures["open"] - section.opening) > _CENT:
            return None
        if abs(row.figures["close"] - section.closing) > _CENT:
            return None
        rows_read = _read_rows(section, start, end)
        if rows_read is None:
            return None
        # THE MOVEMENT ORACLE (L1-C10, applied to the columns the caption names
        # rather than only to the closing). The table's DEPOSITS and
        # WITHDRAWALS figures are the bank's own totals for this account, so a
        # ledger that walks to the right closing while summing to something
        # else is a ledger with two errors that cancel — which is exactly what
        # a truncated ledger looks like from the balance walk alone.
        #
        # Compared COLUMN BY COLUMN, which is the paper's own arithmetic and
        # was measured rather than assumed: this template prints a reversal
        # (`Withdrawal Adjustment`) inside the column it adjusts, so the
        # WITHDRAWALS total is the withdrawal column NETTED, not the sum of
        # everything that reduced the balance. Summing by SIGN instead
        # disagrees with the table by twice each reversal — 225.24 on one
        # archive document, 32.09 on another, 0.33 on two more — and every one
        # of those four sits inside `reconcile`'s two-per-cent coverage
        # tolerance, so a sign-keyed reader would have passed them by luck.
        credits = round(sum(row.amount for row, printed in rows_read if printed > 0), 2)
        debits = round(sum(-row.amount for row, printed in rows_read if printed < 0), 2)
        if (abs(credits - row.figures["credit_total"]) > _CENT
                or abs(debits - row.figures["debit_total"]) > _CENT):
            return None
        rows_read = [row for row, _printed in rows_read]
        if rows_read:
            published.append(PublishedAccount(
                statement=_statement(section, row, period, rows_read),
                section_text=section.text,
                label=section.label,
            ))
            continue
        # The section published nothing. R-a: it may be omitted ONLY on printed
        # evidence of its empty state, and never for the absence of rows.
        admitted = ledger.record(
            section.label,
            evidence_class(
                text=section.text,
                opening=section.opening,
                closing=section.closing,
                dated_row_count=len(_DATED_LINE_RE.findall(section.text)),
                prints_counts_or_totals=bool(_COUNTS_ROW_RE.search(section.text)),
                prints_daily_balance_table=_prints_daily_table(section.text),
                rollup=_witness_for(section, caption, rollup_rows),
            ),
            posting_count=0,
        )
        if not admitted:
            # ONE refusal, made where the evidence is read. A second net at the
            # end of the loop (`ledger.refused`) would say the same thing twice
            # and make either one impossible to remove in a mutation table —
            # a condition guarded twice is a condition neither guard can be
            # shown to be doing.
            return None
    if not published:
        # Every section omitted is no account published, which is a publisher
        # defect rather than a document about nothing.
        return None

    publish_omissions(ledger.omissions)
    publish_partition(
        published,
        boundary_mechanism="rollup-oracle",
        document_period=period,
        rollup=RollupEvidence(
            caption_class=caption,
            column_roles_printed=True,
            rows=len(rollup_rows),
            cross_account_total_printed=cross_total is not None,
        ),
    )
    return published[0].statement


def _prints_daily_table(section_text: str) -> bool:
    """A daily-balance CAPTION with two or more of its rows under it.

    A caption alone is not a table, and this template prints the words `Average
    Daily Balance` on a dividend line — which is why the caption pattern refuses
    an `average`/`avg` prefix and why the rows are counted rather than assumed.
    """
    for match in _DAILY_CAPTION_RE.finditer(section_text):
        window = section_text[match.end(): match.end() + 1500]
        if len(_DAILY_ROW_RE.findall(window)) >= 2:
            return True
    return False


def _statement(section: _Section, row: _RollupRow,
               period: tuple[str, str], rows: list[Transaction]) -> Statement:
    """One account's `Statement`, from the section's own paper.

    **The stated totals and counts are `None`, and that is the design's ladder
    read exactly rather than a gap.** For the `rollup-oracle` mechanism the
    opening and the closing may come from the enumerating table where its
    column roles are printed, and the stated counts and totals are *"the
    SECTION's own printed counts and totals where it prints them"* — and this
    template's sections print none. What the table prints is an ORACLE, checked
    against the ledger COLUMN BY COLUMN in the caller and never published, so no
    figure is taken from the roll-up into a payload.

    L1-C8's substance is kept and is strengthened rather than skipped. Feeding
    those two figures would buy `reconcile`'s coverage check, which passes
    anything within two per cent; the caller's oracle compares the same figures
    to the cent and REFUSES the document on a disagreement. Passing them would
    also compare unlike things: this template nets a printed reversal inside the
    column it adjusts, so the bank's WITHDRAWALS total and a sign-keyed sum of
    the ledger differ by twice each reversal on four of the eight archive
    documents — every one of them inside that two-per-cent tolerance.

    The printed `Average Daily Balance` this template shows beside a dividend is
    deliberately NOT published as the bank's stated average either: the same
    line prints the DIVIDEND period it belongs to, which is not the statement
    period, so publishing it would file a figure about one span under another.
    """
    return Statement(
        bank=None,
        account_name=section.label,
        account_number=None,
        period_start=period[0],
        period_end=period[1],
        beginning_balance=section.opening,
        ending_balance=section.closing,
        transactions=rows,
    )
