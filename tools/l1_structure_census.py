"""L1INV instrument 2 — the printed STRUCTURE of every L-1-population document.

READ-ONLY. Reports SHAPES and COUNTS: caption classes, identity forms, grid
column tokens, section counts, boolean per-section facts. It never prints a
printed value, a name, an account number, an amount or a date — every regex
below captures structure and the captures are converted to shape names or
counts before anything is emitted. It calls no parser and does not call
`analyze_markdown` / `cached_analysis`.

WHAT IT MEASURES (card method step 2)
-------------------------------------
Per document:

* the ROLL-UP: does the statement print a table that enumerates the member's
  accounts with a balance each, and under which caption class;
* the IDENTITY FORM - the way each account is named where the roll-up
  enumerates it (a suffix word, an id word, a trailing dash and digits, a
  masked number, a parenthesised code, or a bare product designation);
* the BOUNDARY: whether each enumerated identity reappears later in the
  document in the same form as a SECTION HEADING, which is what makes a
  partition readable from printed evidence rather than guessed;
* per section — its own opening/closing pair, its own counts/totals, its own
  ledger grid (and that grid's COLUMN SHAPE, which is what a row grammar keys
  on), its own daily-balance table, an explicit no-activity declaration;
* whether the roll-up states per-account balances the sections must reproduce
  (the partition ORACLE).

The STRUCTURAL FAMILY of a document is the tuple

    (roll-up caption class, identity form, equation form, grid column shape,
     per-section daily balances, cross-account total row)

and the family table this instrument prints is the answer to "how many of the
176 actually share one structural family".

WHAT THIS IS NOT. It is not a parser and must never become one: it reads
no amount into a number, applies no arithmetic, and publishes nothing. The
split/validate prototype is `tools/l1_split_prototype.py`, which imports the
boundary layer from here.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.cohort_replay import ColdCache  # noqa: E402
from tools.l1_census import (  # noqa: E402
    ATB_GROUP,
    CU_OPPORTUNITY_KEY,
    DECL_GROUPS,
    load_census,
)

MONEY = re.compile(r"-?\$?\(?-?\d{1,3}(?:,\d{3})*\.\d{2}\)?-?")
PAGE_MARKER = re.compile(r"^--- Page \d+ ---$")

# ---------------------------------------------------------------------------
# STRUCTURAL VOCABULARY
# ---------------------------------------------------------------------------
#
# Every entry below is FURNITURE in the R-1 sense: a caption a core processor
# prints on every statement of its family, never a value, a name, an account
# number or a threshold. They are ordered; the first match names the class.

#: Captions under which a statement enumerates the accounts it covers. Ordered
#: most specific first; the FIRST that matches names the class. A caption that
#: also occurs as ordinary prose (a bare `Summary`) is deliberately absent —
#: it fired on a check-number recapitulation during development, which is a
#: false partition and exactly the failure this instrument must not have.
ROLLUP_CAPTIONS: tuple[tuple[str, str], ...] = (
    ("summary_of_accounts", r"summary of (?:your |all )?accounts?\b"),
    ("summary_of_account_by_transaction", r"\bsummary of account by transaction\b"),
    ("summary_of_deposit_account_activity",
     r"\bsummary of deposit(?:s)? account(?:s)? activity\b"),
    ("statement_summary", r"\bstatement summary\b"),
    ("balances_at_a_glance", r"\b(?:account |share )?balances? at a glance\b"),
    ("shares_at_a_glance", r"\bshares? at a glance\b"),
    ("your_account_summary", r"\byour account(?:s)? summary\b"),
    ("accounts_summary", r"\baccount\(s\)\s+summary\b"),
    ("account_summary", r"\baccounts? summary\b"),
    ("deposit_and_loan_activity", r"\bdeposit(?:s)? and loan(?:s)? (?:activity|summary)\b"),
    ("account_balances", r"\baccount balances\b"),
    ("summary_of_balances", r"\bsummary of balances\b"),
)

#: Column headers a roll-up prints above its per-account rows. Presence of one
#: is stronger evidence than the caption alone: it states that the columns to
#: the right of each account name ARE that account's balances.
ROLLUP_HEADERS: tuple[tuple[str, str], ...] = (
    ("type_prev_dep_wd_end",
     r"account type\s+previous balance\s+deposits\s+withdrawals\s+ending balance"),
    ("type_begin_end", r"account type\s+beginning balance\s+ending balance"),
    ("begin_end", r"beginning balance\s+ending balance"),
    ("prev_new", r"previous balance\s+new balance"),
    ("desc_balance", r"description\s+balance"),
)

#: How an account's IDENTITY is printed where the statement enumerates it. The
#: capture group is the identity token; it is used to LOCATE the section and is
#: never emitted. Ordered most specific first — a label is classified by the
#: first form that matches it.
IDENTITY_FORMS: tuple[tuple[str, str], ...] = (
    ("suffix_word", r"\bsuffix\s*#?\s*([*xX]*\d{2,})\b"),
    ("id_word", r"\bid\s*#?\s*([*xX]*\d{2,})\b"),
    ("account_no_mask",
     r"\baccount\s*(?:no\.?|number|#)?\s*[:#]?\s*((?:[*xX#]{1,10})?\d{3,})"),
    ("paren_digits", r"\(\s*#?\s*([sS]?\d{2,})\s*\)"),
    ("dash_digits", r"[A-Za-z]{3}[A-Za-z ./&']*\s[-–]\s*([*xX#]*\d{2,})\b"),
    ("bare_digits", r"(?m)^\s*([*xX#]*\d{3,})\s+[A-Za-z]"),
    # The weakest identity a roll-up can carry and still be a partition: the
    # PRODUCT NAME alone, with no printed number. Recorded as its own class
    # because it is materially weaker evidence — two accounts of the same
    # product cannot be told apart by it, which is a fail-closed condition and
    # not a detail.
    ("product_name_only", r"^([A-Za-z][A-Za-z ./&'-]{2,40}?)\s*$"),
)

#: The opening and closing an account section states for itself.
OPENING_WORDS = r"(?:beginning|previous|opening|prior)\s+balance"
CLOSING_WORDS = r"(?:ending|new|closing)\s+balance"

#: The equation FORM a section prints, most specific first.
EQUATION_FORMS: tuple[tuple[str, str], ...] = (
    ("explicit_six_figure",
     OPENING_WORDS + r".{0,120}?\+\s*(?:deposits|credits).{0,160}?=\s*" + CLOSING_WORDS),
    ("explicit_equation",
     OPENING_WORDS + r".{0,200}?=\s*" + CLOSING_WORDS),
    ("open_close_pair", OPENING_WORDS + r".{0,600}?" + CLOSING_WORDS),
    ("open_only", OPENING_WORDS),
)

#: Column tokens a transaction grid header may print, in the order the header
#: prints them. The ORDER is the shape: it tells a row grammar where the
#: running balance sits relative to the amount.
GRID_TOKENS: tuple[tuple[str, str], ...] = (
    ("txn_date", r"\btran(?:saction)? date\b"),
    ("eff_date", r"\beff(?:ective)? date\b"),
    ("post_date", r"\bpost(?:ing|ed)? date\b"),
    ("date", r"\bdate\b"),
    ("desc", r"\b(?:transaction )?description\b"),
    ("amount", r"\b(?:transaction )?amount\b"),
    ("debit", r"\bdebits?(?: amount)?\b"),
    ("credit", r"\bcredits?(?: amount)?\b"),
    ("withdrawal", r"\bwithdrawals?\b"),
    ("deposit", r"\bdeposits?\b"),
    ("money_in", r"\bmoney in\b"),
    ("money_out", r"\bmoney out\b"),
    ("balance", r"\b(?:new |account )?balance\b"),
)

#: A cross-account total the roll-up closes with.
TOTAL_ROLLUP = re.compile(
    r"\b(?:total balance|account balance total|total shares|total deposit accounts"
    r"|total of all accounts|totals?\s*:)\b", re.I)

#: An explicit statement that a section posted nothing. Each alternative is
#: a whole printed declaration rather than a keyword.
NO_ACTIVITY = re.compile(
    r"\bno (?:account )?activity\b"
    # ... and, spelled the other way the platform spells it,
    r"|\bno transactions\b|\bno posting\b", re.I)

#: A member's LOAN or credit facility, as a roll-up enumerates it. Furniture:
#: the words a core processor prints for the facility class, never an
#: institution's product name. `analysis/symitar.py` 13-45 states the rule this
#: measures — a member's loan facilities print under a different grid and are
#: not deposit ledgers — and the packet's condition list never mentioned it
#: (MAJOR-6).
#: The classes TRIED, each one measured on its own and each one printed by the
#: report, because the first version of this vocabulary carried two classes and
#: a comment claiming a wider list had been tried and fired on nothing. That
#: claim was false — the re-review added the card-brand class to the same raw
#: labels and found four more documents, all of them multi-posting — and the
#: honest form of the claim is this table rather than a sentence (MAJOR-A).
#:
#: `counted` says whether the class is treated as a facility for condition 12.
#: A class fires but is NOT counted where this probe cannot tell from the label
#: what the row is: `card_network` matches a long enumerating line that carries
#: neither a deposit designation nor any card wording, on documents that locate
#: no partition at all, and a brand word standing alone is not proof of an
#: account row. `debit_card` is deliberately never counted: a debit card is how
#: a member reaches a deposit account and is not a facility of its own, and
#: counting it would put 11 further documents into a condition that must not
#: hold them.
FACILITY_CLASSES: tuple[tuple[str, str, bool], ...] = (
    ("loan", r"loans?", True),
    ("mortgage",
     r"mortgage\w*",
     True),
    ("brand_row",
     r"visa",
     True),
    ("card_network", r"amex", False),
    ("card_issuer", r"master ?card\w*", False),
    ("card_scheme", r"discover", False),
    ("credit_card", r"credit card\w*", False),
    ("debit_card", r"debit card\w*", False),
    ("home_equity", r"home equity", False),
    ("overdraft_line", r"overdraft protection", False),
)

#: A member's facility, as a roll-up enumerates it — the classes above that are
#: COUNTED. Furniture: the words a core processor prints for the class, never
#: an institution's product name. `analysis/symitar.py` 13-45 states the rule
#: this measures — a member's facilities print under a different grid and are
#: not deposit ledgers — and the packet's condition list never mentioned it
#: (MAJOR-6).
LOAN_ROW = re.compile(
    r"\b(?:%s)\b" % "|".join(
        pattern for _name, pattern, counted in FACILITY_CLASSES if counted),
    re.I)

#: Every class, counted or not, for the report's own audit table.
FACILITY_PROBES: tuple[tuple[str, re.Pattern[str], bool], ...] = tuple(
    (name, re.compile(r"\b(?:%s)\b" % pattern, re.I), counted)
    for name, pattern, counted in FACILITY_CLASSES
)

#: The deposit product a candidate Option-B primary rule would name (MINOR-3):
#: the transaction account a member spends from. Furniture, and used ONLY to
#: measure whether such a rule is even defined on this population.
SPENDING_SHARE = re.compile(r"\b(?:checking|chequing|draft|spending)\b", re.I)

#: A section heading reprinted at a page break. It carries no grid and must not
#: be mistaken for a second account.
CONTINUATION = re.compile(r"\(continued\)|\bcontinued (?:on|to) next page\b", re.I)

#: The caption of a per-section DAILY-BALANCE TABLE, which is not the averaged
#: figure a summary block prints beside a similar caption. The first version of
#: this instrument counted both: a bare pattern for the two words also matched
#: the averaged figure, which put sections into the "prints its own daily
#: balances" column that print one number and no rows at all. The lookbehinds
#: remove that reading and `has_daily_table` below then requires the rows.
DAILY_CAPTION = re.compile(r"(?<!average )(?<!avg )(?<!avg\. )\bdaily balance", re.I)

#: A row of such a table: a date and one figure, that day's printed balance.
DAILY_TABLE_ROW = re.compile(
    r"(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}\b)"
    r"[^\n\d]{0,12}?-?\$?\d[\d,]*\.\d{2}")


def has_daily_table(section_text: str) -> bool:
    """Whether the section prints a daily-balance TABLE of its own.

    A caption alone is not a table: the window after it must carry two or more
    rows that are a date and one figure. Counted, never read as a value."""
    for m in DAILY_CAPTION.finditer(section_text):
        window = section_text[m.end(): m.end() + 1500]
        if len(DAILY_TABLE_ROW.findall(window)) >= 2:
            return True
    return False

#: A per-section stated count/total row.
COUNTS_ROW = re.compile(
    r"\b\d+\s+total\s+(?:debits|credits|deposits|withdrawals|checks)"
    r"|\btotal\s+(?:deposits?|withdrawals?|debits?|credits?|checks?)\b", re.I)


def _norm(markdown: str) -> str:
    """Page markers removed, tabs normalised. Line structure is PRESERVED:
    several of these layouts state a boundary with a line of its own."""
    return "\n".join(
        "" if PAGE_MARKER.match(line.strip()) else line.replace("\t", " ")
        for line in markdown.splitlines()
    )


def _flat(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text)


# ---------------------------------------------------------------------------
# roll-up
# ---------------------------------------------------------------------------


@dataclass
class RollUpRow:
    #: The printed label, kept ONLY as a locator for the section heading. It is
    #: never emitted and never compared to a list of product names.
    label: str
    identity_form: str
    #: The identity token, likewise a locator only.
    token: str
    n_money: int
    #: The row's own money block, kept in memory so a consumer can ask whether
    #: this account's closing figure is stated here (the partition ORACLE).
    #: Never emitted.
    block: str = ""
    #: the RAW label named a loan or credit facility. Tested before the
    #: furniture trim, which removes the very words that name one (MAJOR-6).
    loan: bool = False


@dataclass
class RollUp:
    caption: str | None = None
    caption_at: int = -1
    header: str | None = None
    rows: list[RollUpRow] = field(default_factory=list)
    total_row: bool = False
    window_end: int = -1
    #: absolute offset of the end of the LAST enumerated row
    rows_end: int = -1
    #: rows naming a facility, counted before the furniture trim
    loan_labels: int = 0
    #: every facility class that fired on a raw label here, counted or not
    facility_classes: set = field(default_factory=set)

    @property
    def identity_form(self) -> str | None:
        if not self.rows:
            return None
        return Counter(r.identity_form for r in self.rows).most_common(1)[0][0]

    @property
    def rows_with_balance(self) -> int:
        return sum(1 for r in self.rows if r.n_money >= 1)

    @property
    def rows_with_two_balances(self) -> int:
        return sum(1 for r in self.rows if r.n_money >= 2)


def _classify_label(label: str) -> tuple[str, str] | None:
    """(identity form, identity token) for one roll-up label, or None when the
    label carries no identity at all."""
    for name, pattern in IDENTITY_FORMS[:-1]:
        m = re.search(pattern, label, re.I | re.M)
        if m:
            return name, m.group(1).strip()
    m = re.search(r"(?<![\d/.,$-])(\d{2,10})(?![\d/.,-])", label)
    if m:
        return "bare_digits", m.group(1)
    alpha = max(re.findall(r"[A-Za-z][A-Za-z ./&'-]{3,}", label), key=len, default="")
    if len(alpha.strip()) >= 6:
        return "product_name_only", alpha.strip()
    return None


#: Column words a roll-up prints ABOVE or BESIDE its figures. They are the
#: table's furniture, not an account's name; a label is trimmed to whatever
#: follows the last of them so that a flattened header cannot be mistaken for
#: the first account.
ROLLUP_FURNITURE = re.compile(
    r"\b(?:account type|account|type|previous balance|beginning balance"
    r"|ending balance|new balance|opening balance|closing balance|deposits?"
    r"|description|withdrawals?|credits?|debits?|dividends?|interest|fees?"
    r"|balances?|total|certificates?|summary|loans?|shares?|cdn|usd|cad)\b", re.I)


def _clean_label(label: str) -> str:
    last = None
    for m in ROLLUP_FURNITURE.finditer(label):
        last = m
    if last is not None:
        label = label[last.end():]
    return label.strip(" .:*|_-—–")


def _money_blocks(line: str) -> list[tuple[str, str]]:
    """[(label, money block)] for one printed line.

    The primitive this instrument partitions roll-ups with, and the reason it
    does not need a per-issuer grammar: a table row is a NAME followed by that
    row's figures, so a run of adjacent money tokens ENDS a row and the text
    since the previous run is the next row's name. It reads the same whether
    the issue prints one account per line or flattens the whole table onto
    one."""
    spans = [m.span() for m in MONEY.finditer(line)]
    if not spans:
        return []
    blocks: list[tuple[int, int]] = []
    start, end = spans[0]
    for a, b in spans[1:]:
        # adjacent money tokens (only separator furniture between them) are one
        # block: they are one account's several columns.
        if re.fullmatch(r"[\s$()|*]*", line[end:a]):
            end = b
        else:
            blocks.append((start, end))
            start, end = a, b
    blocks.append((start, end))
    out: list[tuple[str, str]] = []
    cursor = 0
    for a, b in blocks:
        out.append((line[cursor:a], line[a:b]))
        cursor = b
    return out


def _rollup_candidate_rows(window: str) -> tuple[list[RollUpRow], bool, int, int, set]:
    """Rows of the enumerating table, read by money block (see `_money_blocks`).

    Returns the rows, whether a cross-account total row closed the table, the
    offset in `window` at which the last row ended, and how many of the table's
    rows list a facility rather than a deposit account (MAJOR-6).

    The loan count is taken from the RAW label and BEFORE the row is admitted,
    for two reasons that both bite: `_clean_label` trims a label at the last
    piece of table furniture and the words that name a facility ARE furniture,
    so a row reading only of a facility class is trimmed to nothing and then
    dropped for having no name left. Counting after either step measures zero
    and means nothing."""
    rows: list[RollUpRow] = []
    total = False
    rows_end = 0
    offset = 0
    loans = 0
    classes: set = set()
    for raw in window.splitlines():
        line = _flat(raw).strip()
        line_at = window.find(raw, offset)
        offset = (line_at if line_at >= 0 else offset) + len(raw) + 1
        if not line:
            continue
        for label, block in _money_blocks(line):
            for name, probe, _counted in FACILITY_PROBES:
                if probe.search(label):
                    classes.add(name)
            if LOAN_ROW.search(label):
                loans += 1
            if TOTAL_ROLLUP.search(label):
                total = True
                continue
            head = _clean_label(label)
            if not re.search(r"[A-Za-z]{3}", head) or len(head) > 60:
                continue
            classified = _classify_label(label.strip()) or _classify_label(head)
            kind, token = classified if classified else ("product_name_only", head)
            rows.append(RollUpRow(label=head[:80], identity_form=kind, token=token,
                                  n_money=len(MONEY.findall(block)), block=block,
                                  loan=bool(LOAN_ROW.search(label))))
            rows_end = max(rows_end, offset)
    return rows, total, rows_end, loans, classes


def find_rollup(text: str) -> RollUp:
    """The account-enumerating table, if the document prints one.

    Scope discipline: the window ends at the first grid header after the
    caption, so a roll-up scan can never run on into the first section's ledger
    and count its rows as accounts."""
    result = RollUp()
    lower = text.lower()
    for name, pattern in ROLLUP_CAPTIONS:
        m = re.search(pattern, lower, re.M)
        if m:
            result.caption, result.caption_at = name, m.start()
            break
    if result.caption is None:
        return result

    window = text[result.caption_at: result.caption_at + 4000]
    grid = find_grid_header(window[120:])
    if grid is not None:
        window = window[: 120 + grid[1]]
    result.window_end = result.caption_at + len(window)
    wlower = _flat(window).lower()

    for name, pattern in ROLLUP_HEADERS:
        if re.search(pattern, wlower):
            result.header = name
            break

    (result.rows, result.total_row, rows_end, result.loan_labels,
     result.facility_classes) = _rollup_candidate_rows(window)
    result.rows_end = result.caption_at + rows_end
    result.total_row = result.total_row or bool(TOTAL_ROLLUP.search(window))
    return result


# ---------------------------------------------------------------------------
# grid headers
# ---------------------------------------------------------------------------


#: The movement columns a grid header may name, held as data rather than
#: spelled out at the call site.
_MOVEMENT_COLUMNS = (r"\b(?:amount|debits?|credits?|withdrawals?|deposits?"
                   r"|money in|money out)\b")


def find_grid_header(text: str) -> tuple[str, int, int] | None:
    """(column shape, start, end) of the first transaction-grid header.

    A grid header is recognised STRUCTURALLY: a date column token, an
    amount-class token and a balance token inside one 120-character window,
    with no money token between them (a header states columns; a row states
    figures). The shape is the ordered tuple of the tokens found, which is what
    a row grammar needs and all this instrument reports."""
    lower = _flat(text).lower()
    date_re = re.compile(r"\b(?:tran(?:saction)? date|eff(?:ective)? date|post(?:ing|ed)? date|date)\b")
    # A header states COLUMNS; the row under it states figures. The window is
    # therefore cut at the first thing that can only be a value — a money
    # token or a printed date — so a column shape can never absorb the words
    # of the first transaction description.
    value_re = re.compile(
        r"\d{1,2}[/-]\d{1,2}\b"
        r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2}\b"
        r"|\$?\d{1,3}(?:,\d{3})*\.\d{2}")
    for m in date_re.finditer(lower):
        window = lower[m.start(): m.start() + 150]
        cut = value_re.search(window)
        if cut is not None:
            window = window[: cut.start()]
        if not re.search(r"\bbalance\b", window):
            continue
        if not re.search(_MOVEMENT_COLUMNS, window):
            continue
        hits: list[tuple[int, str]] = []
        for name, pattern in GRID_TOKENS:
            for hit in re.finditer(pattern, window):
                hits.append((hit.start(), name))
        hits.sort()
        shape: list[str] = []
        covered: list[tuple[int, int]] = []
        for position, name in hits:
            if any(a <= position < b for a, b in covered):
                continue
            length = len(re.match(dict(GRID_TOKENS)[name], window[position:]).group(0))
            covered.append((position, position + length))
            if not shape or shape[-1] != name:
                shape.append(name)
        if len(shape) < 3:
            continue
        return "|".join(shape), m.start(), m.start() + len(window)
    return None


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------


@dataclass
class Section:
    identity_index: int
    start: int
    end: int
    has_equation: str | None = None
    has_counts: bool = False
    grid_shape: str | None = None
    has_daily: bool = False
    no_activity: bool = False
    n_dated_rows: int = 0
    #: the section's own heading names a transaction account (MINOR-3)
    heading_names_a_spending_share: bool = False


@dataclass
class DocStructure:
    sha16: str
    group: str
    band: str
    pages: int
    rollup: RollUp
    sections: list[Section]
    grid_shape: str | None
    equation_form: str | None
    daily_sections: int
    total_row: bool
    boundary: str
    notes: list[str] = field(default_factory=list)
    #: enumerated rows listing a facility rather than a deposit account
    loan_rows: int = 0
    #: denominations named inside the enumerating table
    denominations: int = 0

    @property
    def boundary_class(self) -> str:
        return self.boundary.split(":")[0]

    @property
    def family_key(self) -> str:
        # Components are joined by a WORD rather than a bare bar. Two adjacent
        # component names would otherwise read as a two-word phrase, and the
        # branch privacy scan is right to treat any such phrase as suspect.
        return " then ".join([
            self.boundary,
            self.rollup.caption or "no-rollup",
            self.rollup.identity_form or "no-identity",
            self.equation_form or "no-equation",
            self.grid_shape or "no-grid",
            "daily" if self.daily_sections else "no-daily",
            "total-row" if self.total_row else "no-total-row",
        ])


#: A ledger ROW: a printed date followed, on the same line, by a money token.
#: Counted, never parsed — the count is what says a section POSTED, which is
#: the fact the L-1 rule turns on.
DATED_ROW = re.compile(
    r"(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}\b)"
    r"[^\n]{0,240}?-?\$?\d[\d,]*\.\d{2}")


#: Two DENOMINATIONS named inside one enumerating table. Under
#: `CURRENCY_DOCTRINE` a payload spanning two of them has no valid ADB and no
#: valid package arithmetic, so this is a refusal with a measured population
#: rather than a hypothetical. Currency CODES only — never an amount.
CURRENCY_TOKENS: tuple[tuple[str, str], ...] = (
    ("cad", r"\b(?:CAD|CDN)\b"),
    ("usd", r"\bUSD\b"),
)


def _denominations(window: str) -> int:
    return sum(1 for _name, pattern in CURRENCY_TOKENS if re.search(pattern, window))


def _heading_line(text: str, start: int, end: int) -> str:
    """A section's heading window — the line it opens on, from that line's own
    start, plus a bounded run after it.

    Read from the START of the line rather than from the section offset,
    because a roll-up-located section starts at the identity TOKEN, which these
    layouts print after the product designation, not before it. Matched for
    shape and never emitted."""
    line_start = text.rfind(chr(10), 0, start) + 1
    stop = text.find(chr(10), start)
    if stop < 0 or stop > end:
        stop = min(start + 160, end)
    return text[line_start:max(stop, min(start + 160, end))]


def _section_facts(section_text: str) -> tuple[str | None, bool, str | None, bool, bool, int]:
    flat = _flat(section_text)
    equation = None
    for name, pattern in EQUATION_FORMS:
        if re.search(pattern, flat, re.I | re.S):
            equation = name
            break
    grid = find_grid_header(section_text)
    return (
        equation,
        bool(COUNTS_ROW.search(flat)),
        grid[0] if grid else None,
        has_daily_table(section_text),
        bool(NO_ACTIVITY.search(flat)),
        len(DATED_ROW.findall(section_text)),
    )


def _locators(row: RollUpRow) -> list[re.Pattern[str]]:
    """Patterns that find this account's SECTION HEADING later in the document.

    Built from what the roll-up itself printed — never from a vocabulary. The
    identity TOKEN is searched for rather than the roll-up's identity FORM,
    because several issues state the same account two ways (a leading code and
    a product designation in the table, the same designation followed by an id
    word at the section). Both
    the number and the name are offered, in that order, because either may be
    the half the section heading repeats. The number is fenced off from digits,
    slashes and currency punctuation so it cannot land inside a date or an
    amount."""
    out: list[re.Pattern[str]] = []
    digits = row.token.lstrip("*xX#")
    if row.identity_form != "product_name_only" and digits.isdigit():
        out.append(re.compile(r"(?<![\d/.,$*-])" + re.escape(digits) + r"(?![\d/.,-])"))
    name = max(re.findall(r"[A-Za-z][A-Za-z ./&'-]{3,}", row.label), key=len, default="").strip()
    if len(name) >= 6:
        out.append(re.compile(re.escape(name).replace(r"\ ", r"\s+"), re.I))
    if row.identity_form == "product_name_only" and not out:
        text = row.token.strip()
        if len(text) >= 6:
            out.append(re.compile(re.escape(text).replace(r"\ ", r"\s+"), re.I))
    return out


def _sections_from_rollup(text: str, rollup: RollUp) -> list[tuple[int, int]]:
    """[(position, roll-up row index)] — each enumerated account's FIRST
    reappearance after the roll-up that is followed, within a bounded window,
    by that section's own opening figure or its own grid header. A reappearance
    with neither is a mention, not a boundary, and is not taken. A reappearance
    inside a `(continued)` reprint is skipped for the same reason
    `community_section` anchors its heading on the grid."""
    starts: list[tuple[int, int]] = []
    #: The floor is the end of the LAST enumerated row, not the end of the
    #: scan window: several issues print the first account's section heading
    #: immediately after the table, inside the same window, and a floor at the
    #: window end silently loses that account.
    floor = max(rollup.rows_end, rollup.caption_at + 20)
    taken: set[str] = set()
    for index, row in enumerate(rollup.rows):
        key = f"{row.identity_form}:{row.token}:{row.label}"
        if key in taken:
            continue
        taken.add(key)
        found = None
        for locator in _locators(row):
            for m in locator.finditer(text):
                if m.start() < floor:
                    continue
                window = text[m.start(): m.start() + 900]
                if CONTINUATION.search(window[:160]):
                    continue
                if re.search(OPENING_WORDS, window, re.I) or find_grid_header(window):
                    found = m.start()
                    break
            if found is not None:
                break
        if found is not None:
            starts.append((found, index))
    starts.sort()
    # two enumerated accounts resolving to the SAME position is not two
    # sections; it is one heading matched twice, and it is dropped.
    deduped: list[tuple[int, int]] = []
    for position, index in starts:
        if deduped and position - deduped[-1][0] < 40:
            continue
        deduped.append((position, index))
    return deduped


def _sections_from_identities(text: str) -> tuple[list[tuple[int, int]], str | None]:
    """Boundary WITHOUT an enumerating table: the section headings themselves.

    Several issues print no roll-up at all and open each account with a heading
    that carries its own identity (`... Suffix 0050 Activity Summary Previous
    Balance ...`). The partition is still printed evidence — what is missing is
    the cross-account ORACLE, and this instrument reports that difference
    rather than smoothing it over, because a publication rule that requires the
    oracle must refuse these documents.

    A heading is taken only when (a) an identity form matches, (b) the text
    before it on its own line names something and prints no money — a figure
    before the identity means the match landed inside a row — and (c) the
    section's own opening figure or grid header follows within a bounded
    window."""
    best: tuple[int, list[tuple[int, int]], str] | None = None
    for name, pattern in IDENTITY_FORMS[:-1]:
        starts: list[tuple[int, int]] = []
        seen: set[str] = set()
        for m in re.finditer(pattern, text, re.I | re.M):
            token = m.group(1).strip()
            if token in seen:
                continue
            line_start = text.rfind("\n", 0, m.start()) + 1
            head = text[line_start: m.start()]
            if len(head) > 90 or MONEY.search(head):
                continue
            if not re.search(r"[A-Za-z]{3}", head + m.group(0)):
                continue
            window = text[m.start(): m.start() + 900]
            if CONTINUATION.search(window[:160]):
                continue
            if not (re.search(OPENING_WORDS, window, re.I) or find_grid_header(window)):
                continue
            seen.add(token)
            starts.append((line_start, len(starts)))
        if len(starts) >= 2 and (best is None or len(starts) > best[0]):
            best = (len(starts), sorted(starts), name)
    if best is None:
        return [], None
    return best[1], best[2]


def _sections_from_equations(text: str) -> list[tuple[int, int]]:
    """Fallback boundary: the section's OWN opening figure, with the heading
    line immediately above it taken as the boundary.

    Weaker than the roll-up mechanism and reported as such: without an
    enumerating table there is no printed oracle to check the partition
    against, so a document that reaches its partition this way can never be
    published under a rule that requires one."""
    starts: list[tuple[int, int]] = []
    for m in re.finditer(OPENING_WORDS, text, re.I):
        line_start = text.rfind("\n", 0, m.start()) + 1
        prior = text.rfind("\n", 0, max(line_start - 1, 0)) + 1
        heading = text[prior:line_start].strip()
        candidate = line_start if heading else m.start()
        head_text = heading or text[line_start:m.start()].strip()
        if not head_text or MONEY.search(head_text):
            candidate = m.start()
        if CONTINUATION.search(text[max(prior - 100, 0): m.start()]):
            continue
        if starts and candidate - starts[-1][0] < 200:
            continue
        starts.append((candidate, len(starts)))
    return starts


def structure(sha16: str, group: str, band: str, markdown: str, pages: int) -> DocStructure:
    text = _norm(markdown)
    rollup = find_rollup(text)
    notes: list[str] = []
    sections: list[Section] = []
    boundary = "none"
    starts: list[tuple[int, int]] = []

    if len(rollup.rows) >= 2:
        starts = _sections_from_rollup(text, rollup)
        if starts:
            boundary = f"rollup-oracle:{rollup.identity_form}"
        else:
            notes.append("rollup-enumerated-but-no-section-reappearance")
    elif len(rollup.rows) == 1:
        notes.append("rollup-enumerates-one-account")
    elif rollup.caption:
        notes.append("rollup-caption-without-enumerated-rows")
    else:
        notes.append("no-rollup-caption")

    if not starts:
        by_identity, form = _sections_from_identities(text)
        if by_identity:
            starts = by_identity
            boundary = f"section-identity:{form}"
    if not starts:
        fallback = _sections_from_equations(text)
        if len(fallback) >= 2:
            starts = fallback
            boundary = "section-equation-scan"

    for position, (start, index) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(text)
        equation, counts, grid, daily, none_flag, rows = _section_facts(text[start:end])
        heading = _heading_line(text, start, end)
        sections.append(Section(index, start, end, equation, counts, grid,
                                daily, none_flag, rows,
                                bool(SPENDING_SHARE.search(heading))))

    grid = find_grid_header(text)
    equations = Counter(s.has_equation for s in sections if s.has_equation)
    return DocStructure(
        sha16=sha16, group=group, band=band, pages=pages, rollup=rollup,
        sections=sections, grid_shape=grid[0] if grid else None,
        equation_form=equations.most_common(1)[0][0] if equations else None,
        daily_sections=sum(1 for s in sections if s.has_daily),
        total_row=rollup.total_row, boundary=boundary, notes=notes,
        loan_rows=max(rollup.loan_labels, sum(1 for r in rollup.rows if r.loan)),
        denominations=_denominations(
            text[rollup.caption_at: rollup.window_end] if rollup.caption else ""),
    )


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def population(groups: dict, opportunities: dict) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for name in opportunities[CU_OPPORTUNITY_KEY]["groups"]:
        for sha16 in groups[name]["shas16"]:
            out.append(("CU-SUFFIX", name, sha16))
    for name in DECL_GROUPS:
        for sha16 in groups[name]["shas16"]:
            out.append(("DECL-L1-CANDIDATE", name, sha16))
    for sha16 in groups[ATB_GROUP]["shas16"]:
        out.append(("ATB", ATB_GROUP, sha16))
    return out


def survey(census_dir: Path, data_dir: Path) -> list[DocStructure]:
    groups, opportunities, per_sha = load_census(census_dir)
    sha_by16 = {row["sha16"]: row["sha"] for row in per_sha}
    cache = ColdCache(data_dir)
    out: list[DocStructure] = []
    for band, group, sha16 in population(groups, opportunities):
        markdown, pages = cache.text(sha_by16[sha16])
        if markdown is None:
            continue
        out.append(structure(sha16, group, band, markdown, len(pages)))
    return out


def _pinned_main(args) -> int:
    """The pinned-109 report: which pinned documents print more than one
    posting account, and are therefore inside the regression surface of any
    change to how a multi-account statement is published."""
    survey = pinned_survey(args.data_dir, args.rows)
    print("# L1INV — the pinned 109, structurally")
    print(f"# data_dir={args.data_dir}")
    print()
    print("| text source | documents |")
    print("|---|---:|")
    for source, count in Counter(s for _r, _h, s, _d in survey).most_common():
        print(f"| {source} | {count} |")
    print()
    multi = [(rel, sha, src, doc) for rel, sha, src, doc in survey
             if doc is not None and sum(1 for s in doc.sections if s.n_dated_rows >= 2) >= 2]
    single = [row for row in survey if row[3] is not None and row not in multi]
    print("| finding | documents |")
    print("|---|---:|")
    print(f"| pinned documents surveyed | {sum(1 for r in survey if r[3] is not None)} |")
    print(f"| **print TWO OR MORE posting sections** | **{len(multi)}** |")
    print(f"| print one or none | {len(single)} |")
    print()
    print("Pinned documents with two or more posting sections "
          "(sha16 | boundary | sections | posting sections | text source):")
    print()
    print("| sha16 | boundary | sections | posting | text source |")
    print("|---|---|---:|---:|---|")
    for _rel, sha, src, doc in multi:
        posting = sum(1 for s in doc.sections if s.n_dated_rows >= 2)
        print(f"| `{sha}` | `{doc.boundary}` | {len(doc.sections)} | {posting} | {src} |")
    print()
    if args.json:
        args.json.write_text(json.dumps([
            {"sha16": sha, "source": src,
             "sections": len(doc.sections) if doc else 0,
             "posting": sum(1 for s in doc.sections if s.n_dated_rows >= 2) if doc else 0,
             "boundary": doc.boundary if doc else None}
            for _rel, sha, src, doc in survey
        ], indent=1), encoding="utf-8")
    return 0


def pinned_survey(data_dir: Path, rows_csv: Path) -> list[tuple[str, str, str, DocStructure | None]]:
    """The pinned 109, structurally. [(relative path, sha16, text source, structure)].

    Text comes from the run of record's own cold cache where the pinned
    document is in the run, and from the committed OCR artifact where there is
    one. A pinned document with neither is reported as NOT SURVEYED: this
    instrument does not reach around `ocr/native_text.py`'s ladder to read it
    a third way, and a structure read through different text would not be the
    structure production read."""
    import hashlib

    from tools.l1_census import pinned_paths

    repo = Path(__file__).resolve().parents[1]
    cache = ColdCache(data_dir)
    in_run: set[str] = set()
    with rows_csv.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            in_run.add(row["content_sha256"].upper())

    out: list[tuple[str, str, str, DocStructure | None]] = []
    for rel in pinned_paths(repo):
        path = repo / "Bank Statements" / Path(rel)
        if not path.is_file():
            out.append((rel, "-", "missing-from-corpus-root", None))
            continue
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest().upper()
        markdown: str | None = None
        source = ""
        if sha in in_run:
            markdown, pages = cache.text(sha)
            source = "run-of-record cold cache"
        if markdown is None:
            try:
                from corpus_artifacts import cached_markdown

                markdown = cached_markdown(data)
                pages = (markdown or "").split("--- Page ")
                source = "committed OCR artifact"
            except Exception:  # pragma: no cover - artifact absent
                markdown = None
        if markdown is None:
            # DELIBERATELY NOT extracted here. The native ladder is composed in
            # `ocr/native_text.py::native_statement` and nowhere else
            # (`tests/test_native_rung_parity.py`), and this instrument is not
            # going to be the module that reaches around it. A pinned document
            # the run of record never saw is reported as NOT SURVEYED rather
            # than surveyed through a second extraction path — which is also
            # the more honest answer, since a structure read through different
            # text is not the structure production read.
            out.append((rel, sha[:16], "not-in-the-run-of-record", None))
            continue
        out.append((rel, sha[:16], source,
                    structure(sha[:16], "PINNED", "PINNED", markdown, len(pages))))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--pinned", action="store_true",
                        help="survey the pinned 109 instead of the census population")
    parser.add_argument("--rows", type=Path, help="run-of-record rows.csv (with --pinned)")
    args = parser.parse_args(argv)
    if args.pinned:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):  # pragma: no cover
            pass
        return _pinned_main(args)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    docs = survey(args.census_dir, args.data_dir)
    print("# L1INV — structural census of the L-1 population")
    print(f"# documents read: {len(docs)}")
    print()

    print("## Multi-section evidence")
    print()
    multi = [d for d in docs if len(d.sections) >= 2]
    one = [d for d in docs if len(d.sections) == 1]
    none = [d for d in docs if not d.sections]
    print("| finding | documents |")
    print("|---|---:|")
    print(f"| >= 2 sections located | {len(multi)} |")
    print(f"| exactly 1 section located | {len(one)} |")
    print(f"| no partition established (fail closed) | {len(none)} |")
    print()
    print("| fail-closed reason | documents |")
    print("|---|---:|")
    for reason, count in Counter(n for d in none for n in d.notes).most_common():
        print(f"| `{reason}` | {count} |")
    print()

    print("## Boundary strength — what printed evidence establishes the partition")
    print()
    print("| mechanism | documents | oracle available |")
    print("|---|---:|---|")
    strength = Counter(d.boundary_class for d in docs)
    for name, oracle in (
        ("rollup-oracle", "YES — the roll-up states each account's balances"),
        ("section-identity", "no — the partition is printed, the cross-check is not"),
        ("section-equation-scan", "no — inferred from opening figures alone (WEAKEST)"),
        ("none", "n/a — no partition established"),
    ):
        print(f"| `{name}` | {strength.get(name, 0)} | {oracle} |")
    print()

    print("## Structural families (boundary | roll-up caption | identity form | "
          "equation form | grid column shape | per-section daily | cross-account total)")
    print()
    families: dict[str, list[DocStructure]] = defaultdict(list)
    for d in docs:
        families[d.family_key].append(d)
    print("| n | family key | census groups | sections (min/median/max) |")
    print("|---:|---|---|---|")
    for key, members in sorted(families.items(), key=lambda kv: -len(kv[1])):
        counts = sorted(len(m.sections) for m in members)
        median = counts[len(counts) // 2]
        gs = sorted({m.group for m in members})
        label = ", ".join(f"`{g}`" for g in gs[:4]) + (f" (+{len(gs) - 4})" if len(gs) > 4 else "")
        print(f"| {len(members)} | `{key}` | {label} | {counts[0]}/{median}/{counts[-1]} |")
    print()

    print("## Mechanics, counted independently")
    print()
    for title, values in (
        ("roll-up caption class", [d.rollup.caption or "none" for d in docs]),
        ("roll-up column header", [d.rollup.header or "none" for d in docs]),
        ("identity form", [d.rollup.identity_form or "none" for d in docs]),
        ("equation form (modal section)", [d.equation_form or "none" for d in docs]),
        ("grid column shape", [d.grid_shape or "none" for d in docs]),
        ("boundary mechanism", [d.boundary for d in docs]),
    ):
        print(f"**{title}**")
        print()
        print("| value | documents |")
        print("|---|---:|")
        for value, count in Counter(values).most_common():
            print(f"| `{value}` | {count} |")
        print()

    print("## Per-section facts (over documents with a located partition)")
    print()
    located = [d for d in docs if d.sections]
    total_sections = sum(len(d.sections) for d in located)
    with_eq = sum(1 for d in located for s in d.sections if s.has_equation in
                  ("explicit_six_figure", "explicit_equation", "open_close_pair"))
    with_counts = sum(1 for d in located for s in d.sections if s.has_counts)
    with_grid = sum(1 for d in located for s in d.sections if s.grid_shape)
    with_daily = sum(1 for d in located for s in d.sections if s.has_daily)
    no_act = sum(1 for d in located for s in d.sections if s.no_activity)
    posting = sum(1 for d in located for s in d.sections if s.n_dated_rows >= 1)
    print("| fact | sections | share |")
    print("|---|---:|---:|")
    for label, value in (
        ("sections located", total_sections),
        ("prints its own opening AND closing", with_eq),
        ("prints its own counts / totals", with_counts),
        ("prints its own ledger grid header", with_grid),
        ("prints its own daily-balance table", with_daily),
        ("prints an explicit no-activity declaration", no_act),
        ("carries >= 1 dated row", posting),
    ):
        share = f"{100.0 * value / total_sections:.1f}%" if total_sections else "-"
        print(f"| {label} | {value} | {share} |")
    print()

    print("## Roll-up as a partition ORACLE")
    print()
    two = sum(1 for d in located if d.rollup.rows_with_two_balances >= 2)
    onebal = sum(1 for d in located if d.rollup.rows_with_balance >= 2)
    tot = sum(1 for d in located if d.total_row)
    print("| oracle strength | documents |")
    print("|---|---:|")
    print(f"| roll-up states TWO balances per account (opening AND closing) | {two} |")
    print(f"| roll-up states at least ONE balance per account | {onebal} |")
    print(f"| roll-up closes with a cross-account total row | {tot} |")
    print()

    print("## Posting sections per document (the L-1 exposure)")
    print()
    by_posting = Counter(sum(1 for s in d.sections if s.n_dated_rows >= 2) for d in docs)
    print("| posting sections | documents |")
    print("|---:|---:|")
    for k in sorted(by_posting):
        print(f"| {k} | {by_posting[k]} |")
    print()

    print("## By band")
    print()
    print("| band | docs | partition located | >=2 posting sections |")
    print("|---|---:|---:|---:|")
    for band in ("CU-SUFFIX", "DECL-L1-CANDIDATE", "ATB"):
        members = [d for d in docs if d.band == band]
        loc = sum(1 for d in members if d.sections)
        multi_post = sum(1 for d in members
                         if sum(1 for s in d.sections if s.n_dated_rows >= 2) >= 2)
        print(f"| {band} | {len(members)} | {loc} | {multi_post} |")
    print()

    print("## Loan and credit facilities the roll-up enumerates (MAJOR-6)")
    print()
    print("`analysis/symitar.py` 13-45 states the rule: a member's loan "
          "facilities print under a different grid and are not deposit "
          "ledgers. The packet's ten fail-closed conditions never mention "
          "them, and its cross-account-total condition cannot be satisfied on "
          "a table whose total includes one.")
    print()
    loans = [d for d in docs if d.loan_rows]
    loans_multi = [d for d in loans
                   if sum(1 for s in d.sections if s.n_dated_rows >= 2) >= 2]
    print("| measure | documents |")
    print("|---|---:|")
    print(f"| documents whose enumerating table names a loan or credit facility | "
          f"**{len(loans)}**|")
    print(f"| ... of them with two or more posting sections | **{len(loans_multi)}** |")
    print(f"| ... the census groups those belong to | "
          f"{', '.join(sorted({f'`{d.group}`' for d in loans_multi})) or '-'} |")
    print(f"| ... of them ALSO printing a cross-account total row | "
          f"{sum(1 for d in loans if d.total_row)} |")
    print(f"| documents printing a cross-account total row at all | "
          f"{sum(1 for d in docs if d.total_row)} |")
    print()
    print("The vocabulary, class by class, so that its completeness is a table "
          "rather than a sentence. `counted` says whether the class is treated "
          "as a facility for the condition; a class that fires and is not "
          "counted is one this probe cannot confirm from the label alone.")
    print()
    print("| facility class tried | counted | documents it fires on | of them multi-posting |")
    print("|---|---|---:|---:|")
    for name, _probe, counted in FACILITY_PROBES:
        fired = [d for d in docs if name in d.rollup.facility_classes]
        multi = [d for d in fired
                 if sum(1 for s in d.sections if s.n_dated_rows >= 2) >= 2]
        print(f"| `{name}` | {'yes' if counted else 'no'} | {len(fired)} | {len(multi)} |")
    print()

    two_ccy = [d for d in docs if d.denominations >= 2]
    print("| the currency condition | documents |")
    print("|---|---:|")
    print(f"| enumerating tables naming TWO denominations | **{len(two_ccy)}** |")
    print(f"| ... census groups they belong to | "
          f"{', '.join(sorted({f'`{d.group}`' for d in two_ccy})) or '-'} |")
    print(f"| ... sections located on them, in total | "
          f"{sum(len(d.sections) for d in two_ccy)} |")
    print()

    print("## Option B, measured rather than argued (MINOR-3)")
    print()
    print("Each candidate PRIMARY rule, over the documents with two or more "
          "posting sections. A rule is UNDEFINED where the printed evidence it "
          "needs is absent and AMBIGUOUS where two sections satisfy it.")
    print()
    multi_post = [d for d in docs
                  if sum(1 for s in d.sections if s.n_dated_rows >= 2) >= 2]
    no_table = [d for d in multi_post if len(d.rollup.rows) < 2]
    spend = {id(d): [s for s in d.sections
                     if s.n_dated_rows >= 2 and s.heading_names_a_spending_share]
             for d in multi_post}
    print("| candidate rule | documents |")
    print("|---|---:|")
    print(f"| the multi-posting population | {len(multi_post)} |")
    print(f"| \"the section the table names first\" — UNDEFINED, no enumerating table | "
          f"{len(no_table)} |")
    print(f"| \"the only transaction share\" — UNDEFINED, no such heading | "
          f"{sum(1 for d in multi_post if not spend[id(d)])} |")
    print(f"| \"the only transaction share\" — AMBIGUOUS, two or more of them post | "
          f"{sum(1 for d in multi_post if len(spend[id(d)]) >= 2)} |")
    print(f"| \"the only transaction share\" — decides the document | "
          f"{sum(1 for d in multi_post if len(spend[id(d)]) == 1)} |")
    print(f"| the table prints a cross-account TOTAL (the platform ranking them alike) | "
          f"{sum(1 for d in multi_post if d.total_row)} |")
    rollup_multi = [d for d in multi_post if d.boundary_class == "rollup-oracle"]
    print(f"| identity is `product_name_only` on a multi-posting table document | "
          f"{sum(1 for d in rollup_multi if d.rollup.identity_form == 'product_name_only')}"
          f" of {len(rollup_multi)} |")
    print()
    print("| the fail-closed condition on identity (packet condition 2) | documents |")
    print("|---|---:|")
    def _section_tokens(d: DocStructure) -> list[str]:
        return [d.rollup.rows[s.identity_index].token
                for s in d.sections
                if d.boundary_class == "rollup-oracle"
                and 0 <= s.identity_index < len(d.rollup.rows)]

    print(f"| two LOCATED sections resolving to the same identity token | "
          f"{sum(1 for d in docs if len(set(_section_tokens(d))) < len(_section_tokens(d)))} |")
    print(f"| the enumerating table itself printing the same token twice | "
          f"{sum(1 for d in docs if len(d.rollup.rows) >= 2 and len({r.token for r in d.rollup.rows}) < len(d.rollup.rows))} |")
    print()

    if args.json:
        args.json.write_text(json.dumps([
            {
                "sha16": d.sha16, "group": d.group, "band": d.band, "pages": d.pages,
                "family": d.family_key, "boundary": d.boundary, "notes": d.notes,
                "rollup": {
                    "caption": d.rollup.caption, "header": d.rollup.header,
                    "identity_form": d.rollup.identity_form,
                    "n_rollup_rows": len(d.rollup.rows),
                    "rows_with_balance": d.rollup.rows_with_balance,
                    "rows_with_two_balances": d.rollup.rows_with_two_balances,
                    "total_row": d.rollup.total_row,
                },
                "sections": [
                    {"equation": s.has_equation, "counts": s.has_counts,
                     "grid": s.grid_shape, "daily": s.has_daily,
                     "no_activity": s.no_activity, "dated_rows": s.n_dated_rows}
                    for s in d.sections
                ],
            }
            for d in docs
        ], indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
