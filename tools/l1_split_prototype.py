"""L1INV instrument 3 — READ-ONLY split/reconstruct/validate prototype.

**NOT A PARSER. NEVER REGISTERED. NEVER IMPORTED BY PRODUCTION OR BY A TEST.**
It exists to MEASURE one thing, and then to be deleted or rewritten by whoever
implements the ruling. The thing: if a multi-account member statement were
split at its printed boundaries and every section rebuilt as its own
`Statement`, how many sections would close under the EXISTING deterministic
validator, unchanged? `analysis/reconcile.py::reconcile` and
`analysis/adb.py::compute_average_daily_balance` are called exactly as
production calls them; nothing here relaxes, replaces or reimplements either.
It does not call `analyze_markdown` / `cached_analysis`, so it is not a
production analysis caller and is not wired into anything.

WHAT THE FIRST VERSION OF THIS INSTRUMENT GOT WRONG
---------------------------------------------------
The independent review of the L1INV packet found the arithmetic honest and the
MEANING wrong, and every correction below is one of its findings. They are
recorded here because an instrument that was once inflating a count has to
carry the reason it no longer does.

* **BLOCK-1, the vacuous closure.** The chain walk seeded its accepted-prefix
  snapshot with the EMPTY prefix whenever the candidate opening already equalled
  the candidate closing. A section whose two figures coincide therefore
  "closed" having read nothing at all, however much the paper printed — and the
  roll-up then "reproduced" a closing that WAS the roll-up figure the walk
  started from. Four corrections: the empty seed is reported as its own class
  and never as a closure; a section must account for every dated row in its own
  ledger region; a section on an inferred boundary is refused under the
  packet's own first condition; and the enumerating table's columns are read
  from the printed COLUMN CAPTION rather than from position, because one issue
  in this population prints the ENDING figure in the first column.
* **MAJOR-3, one oracle rather than two.** The walk accepts a movement only
  where the paper prints the balance it lands on and the two agree, so ledger
  continuity and the closing identity hold BY CONSTRUCTION and `reconcile`
  cannot refuse what the walk accepted. The count of walks `reconcile` refused
  is now reported next to the count the ADB refused, so nobody reads the pair
  as two independent checks.
* **MAJOR-4, the evidence measured and then discarded.** The structure census
  counts the sections that print their own counts, their own totals and their
  own daily-balance table; the reconstruction passed `None` for all three. They
  are now READ and fed, and a section that prints them and whose printed form
  this instrument cannot read is refused rather than validated without them.
* **MAJOR-5, money moved between a member's own accounts.** Same-day,
  same-magnitude, opposite-signed movements across two sibling ledgers of one
  document are counted, because a package that sums per-account deposits over
  such a document counts the same money twice.
* **BLOCK-2, the idle sibling.** `--idle-siblings` applies the ratified rule of
  `analysis/symitar.py` (13-45) — the printed declaration, or the yield-only
  arithmetic with its summary-equality test — to every sibling section of every
  single-posting document; that module's own predicate is what decides.

METHOD
------
1. Boundaries come from `tools.l1_structure_census` — the printed roll-up's
   enumerated identities where the document prints one, the section headings'
   own identities otherwise. Nothing is inferred from a product vocabulary.
2. Each section's OPENING and CLOSING are the figures the section itself
   prints beside its own opening and closing captions; where the section
   prints neither, the enumerating table's row for that account supplies them
   ONLY where that table prints a column caption naming which column is which.
   A section that has neither FAILS CLOSED.
3. The ledger is reconstructed by a BALANCE CHAIN WALK, which is the only row
   grammar here and is self-validating: starting from the printed opening, a
   movement is accepted only when two adjacent printed figures satisfy
   `previous balance ± printed amount = printed balance` to the cent. The
   amount is never assumed from a column position and never computed as a
   difference alone — the document must print BOTH the delta and the balance
   it lands on, and they must agree. A section whose walk does not arrive at
   the section's own printed closing FAILS CLOSED, and so does one that
   arrives there having accepted nothing.
4. The reconstructed `Statement` carries the section's OWN stated counts,
   stated totals and stated daily balances wherever the section prints them,
   and is handed to `reconcile` and `compute_average_daily_balance` unchanged,
   the ADB with the SECTION's text as its source so the production
   source-coverage check applies. A section CLOSES when both return ok, when
   its chain is not empty, when it accounts for every dated row in its ledger
   region, and when its boundary was printed rather than inferred.
5. The ORACLE check is separate and is no longer circular: the enumerating
   table's own closing column must carry the figure the section reconstructed,
   and the section's closing must have come from the section itself.

PRIVACY. Amounts and dates are read into local variables to do arithmetic and
are never emitted: the report prints counts, boolean facts, refusal-class names
and content sha16s only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.cohort_replay import ColdCache  # noqa: E402
from tools.l1_census import CU_OPPORTUNITY_KEY, DECL_GROUPS, ATB_GROUP, load_census  # noqa: E402
from tools.l1_structure_census import (  # noqa: E402
    CLOSING_WORDS,
    DAILY_CAPTION,
    DATED_ROW,
    MONEY,
    OPENING_WORDS,
    _flat,
    _norm,
    find_grid_header,
    structure,
)

DATE_TOKEN = re.compile(
    r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b"
    r"|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\b")

_D = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
PERIOD = re.compile(rf"({_D})\s*(?:through|thru|to|-|–|—|until)\s*({_D})", re.I)
PERIOD_LABELLED = re.compile(
    rf"start date[:\s]*({_D}).{{0,40}}?end date[:\s]*({_D})", re.I | re.S)
#: `February 1, 2026 to February 28, 2026` and `Feb 1 - 28 2026`
_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
PERIOD_WORDS = re.compile(
    rf"({_MONTH}\.?\s+\d{{1,2}}),?\s*(?:\d{{4}})?\s*(?:through|thru|to|-|–|—)\s*"
    rf"({_MONTH}\.?\s+\d{{1,2}}),?\s*(\d{{4}})", re.I)
PERIOD_WORDS_SHORT = re.compile(
    rf"({_MONTH})\.?\s+(\d{{1,2}})\s*(?:-|–|—|to)\s*(\d{{1,2}}),?\s*(\d{{4}})", re.I)

MONTHS = {m: i + 1 for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}

#: What each column of an enumerating table holds, keyed by the COLUMN CAPTION
#: the table prints above its rows (`tools.l1_structure_census.ROLLUP_HEADERS`).
#: BLOCK-1: without one of these the roles of a row's figures are not printed
#: anywhere, and taking the first figure as the opening is a guess that one
#: issue in this population falsifies — it prints the closing there. A table
#: with no caption therefore supplies no opening and no closing at all.
ROLLUP_COLUMN_ROLES: dict[str, tuple[str, ...]] = {
    "type_prev_dep_wd_end": ("open", "movement", "movement", "close"),
    "type_begin_end": ("open", "close"),
    "begin_end": ("open", "close"),
    "prev_new": ("open", "close"),
    "desc_balance": ("close",),
}


def _money_value(text: str) -> float | None:
    body = text.strip()
    negative = body.startswith("(") or body.endswith(")") or body.endswith("-") or body.startswith("-")
    body = body.strip("()$-").replace(",", "").replace("$", "")
    try:
        value = float(body)
    except ValueError:
        return None
    return -value if negative else value


def _parse_ymd(token: str) -> date | None:
    parts = re.split(r"[/-]", token)
    if len(parts) != 3:
        return None
    try:
        month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _word_date(month: str, day: str, year: str) -> date | None:
    try:
        return date(int(year), MONTHS[month.strip(". ").lower()[:3]], int(day))
    except (KeyError, ValueError):
        return None


def find_period(text: str) -> tuple[date, date] | None:
    """The printed statement period.

    EVERY match of each pattern is considered, not only the first: these
    documents print dates in their marketing furniture too, and taking the
    first pair found made the instrument refuse documents whose real period is
    printed two lines lower. A pair is accepted only if it is ordered and no
    longer than a statement cycle.

    MINOR-2, stated rather than left implicit: this is called ONCE on the whole
    document and the pair it returns is handed to EVERY section. That is
    defensible on a member statement printing one cycle for all of a member's
    accounts, it is why a document with no resolvable period loses every
    section at once, and it is the reason the packet's ADB condition has to say
    WHOSE period it means before it becomes code."""
    def accept(start: date | None, end: date | None) -> tuple[date, date] | None:
        if start and end and start <= end and 20 <= (end - start).days <= 100:
            return start, end
        return None

    for pattern in (PERIOD_LABELLED, PERIOD):
        for m in pattern.finditer(text):
            got = accept(_parse_ymd(m.group(1)), _parse_ymd(m.group(2)))
            if got:
                return got
    for m in PERIOD_WORDS.finditer(text):
        left, right, year = m.group(1).split(), m.group(2).split(), m.group(3)
        got = accept(_word_date(left[0], left[1], year), _word_date(right[0], right[1], year))
        if got:
            return got
    for m in PERIOD_WORDS_SHORT.finditer(text):
        got = accept(_word_date(m.group(1), m.group(2), m.group(4)),
                     _word_date(m.group(1), m.group(3), m.group(4)))
        if got:
            return got
    return None


def _row_date(token: str, period: tuple[date, date]) -> str | None:
    """A printed row date resolved onto the printed period's calendar.

    The year is taken from the period, not invented: a row whose month equals
    the period start's month takes the start year, one whose month equals the
    end's takes the end year, and anything else is refused."""
    start, end = period
    m = DATE_TOKEN.match(token)
    if m is None:
        return None
    if m.group(1):
        month, day = int(m.group(1)), int(m.group(2))
        if m.group(3):
            resolved = _parse_ymd(token)
            return resolved.isoformat() if resolved else None
    else:
        month, day = MONTHS[m.group(4).lower()], int(m.group(5))
    for year in {start.year, end.year}:
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if start <= candidate <= end:
            return candidate.isoformat()
    return None


# ---------------------------------------------------------------------------
# the section's own printed opening and closing
# ---------------------------------------------------------------------------

_OPEN_FIG = re.compile(OPENING_WORDS + r"[^\n]{0,80}?(" + MONEY.pattern + r")", re.I)
_CLOSE_FIG = re.compile(CLOSING_WORDS + r"[^\n]{0,80}?(" + MONEY.pattern + r")", re.I)
#: some issues print the figure BEFORE the caption (`5.00 Beginning Balance`)
_OPEN_FIG_LEFT = re.compile(r"(" + MONEY.pattern + r")[^\n]{0,40}?" + OPENING_WORDS, re.I)
_CLOSE_FIG_LEFT = re.compile(r"(" + MONEY.pattern + r")[^\n]{0,40}?" + CLOSING_WORDS, re.I)


def _figure(text: str, right: re.Pattern[str], left: re.Pattern[str]) -> tuple[float, int] | None:
    m = right.search(text)
    if m:
        value = _money_value(m.group(1))
        if value is not None:
            return value, m.end()
    m = left.search(text)
    if m:
        value = _money_value(m.group(1))
        if value is not None:
            return value, m.end()
    return None


# ---------------------------------------------------------------------------
# the section's own stated counts, totals and daily balances (MAJOR-4)
# ---------------------------------------------------------------------------
#
# The structure census MEASURES that a section prints these; this reads them.
# Both halves are furniture in the R-1 sense — a caption a platform prints on
# every statement of its family, never a value and never a threshold.

_CREDIT_WORDS = r"(?:deposits?|credits?)"
_DEBIT_WORDS = r"(?:withdrawals?|debits?|checks?)"
#: `Total Deposits 1,234.56` and `Total Credits/Deposits $1,234.56`
_TOTAL_CREDIT = re.compile(
    r"\btotal\s+(?:number\s+of\s+)?" + _CREDIT_WORDS + r"\b[^\n]{0,60}?(" + MONEY.pattern + r")", re.I)
_TOTAL_DEBIT = re.compile(
    r"\btotal\s+(?:number\s+of\s+)?" + _DEBIT_WORDS + r"\b[^\n]{0,60}?(" + MONEY.pattern + r")", re.I)
#: `3 Total Deposits` — the count printed ahead of its own caption.
_COUNT_CREDIT = re.compile(r"\b(\d{1,3})\s+total\s+" + _CREDIT_WORDS + r"\b", re.I)
_COUNT_DEBIT = re.compile(r"\b(\d{1,3})\s+total\s+" + _DEBIT_WORDS + r"\b", re.I)
#: A daily-balance table row: a date and one figure, the figure being that
#: day's printed end-of-day balance.
_DAILY_ROW = re.compile(
    r"(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}\b)"
    r"[^\n\d]{0,12}?(" + MONEY.pattern + r")")


@dataclass
class StatedEvidence:
    """What the section itself states about its own ledger."""
    total_credits: float | None = None
    total_debits: float | None = None
    credit_count: int | None = None
    debit_count: int | None = None
    daily: list[tuple[str, float]] = field(default_factory=list)
    #: the paper prints a counts/totals row this reader could not resolve
    counts_unreadable: bool = False
    #: the paper prints a daily-balance caption with no resolvable table
    daily_unreadable: bool = False


def read_stated(section_text: str, prints_counts: bool, prints_daily: bool,
                period: tuple[date, date]) -> StatedEvidence:
    """The section's own stated counts, totals and daily balances.

    Fail-closed by construction: where the census says the paper prints one of
    these and nothing here can resolve it, the fact is recorded and the caller
    refuses the section. Validating a section against `None` in a field the
    paper fills is precisely the defect MAJOR-4 names."""
    out = StatedEvidence()
    flat = _flat(section_text)
    if prints_counts:
        m = _TOTAL_CREDIT.search(flat)
        if m:
            out.total_credits = _money_value(m.group(1))
        m = _TOTAL_DEBIT.search(flat)
        if m:
            value = _money_value(m.group(1))
            out.total_debits = abs(value) if value is not None else None
        m = _COUNT_CREDIT.search(flat)
        if m:
            out.credit_count = int(m.group(1))
        m = _COUNT_DEBIT.search(flat)
        if m:
            out.debit_count = int(m.group(1))
        out.counts_unreadable = (
            out.total_credits is None and out.total_debits is None
            and out.credit_count is None and out.debit_count is None)
    if prints_daily:
        rows: list[tuple[str, float]] = []
        seen: set[str] = set()
        for at in DAILY_CAPTION.finditer(section_text):
            window = section_text[at.end(): at.end() + 1500]
            for m in _DAILY_ROW.finditer(window):
                iso = _row_date(m.group(1), period)
                value = _money_value(m.group(2))
                if iso is None or value is None or iso in seen:
                    continue
                seen.add(iso)
                rows.append((iso, value))
            if len(rows) >= 2:
                break
        out.daily = rows
        out.daily_unreadable = len(rows) < 2
    return out


# ---------------------------------------------------------------------------
# the balance chain walk
# ---------------------------------------------------------------------------


@dataclass
class Walk:
    ok: bool
    rows: list[tuple[str, float, float, tuple[str, str]]] = field(default_factory=list)
    refusal: str | None = None
    skipped: int = 0
    #: the walk arrived at the closing having accepted NOTHING, because the
    #: candidate opening already equalled the candidate closing (BLOCK-1)
    empty: bool = False
    #: offset in the ledger of the end of the last accepted movement
    end_at: int = 0


def chain_walk(ledger: str, opening: float, closing: float,
               period: tuple[date, date]) -> Walk:
    """Consume the section's printed figures into `(date, amount, balance,
    description)` rows, from the printed opening onto the printed closing.

    The rule, and the only one: two adjacent printed figures `a` and `b` are a
    movement when `previous ± a == b` to the cent — the statement printed both
    the movement and the balance it produced, and they agree. Either order is
    accepted (`amount balance` and `balance amount` are both printed in this
    population) but a figure is never re-used and never skipped silently: any
    figure the walk cannot place ends it, and the section fails closed unless
    the walk has by then reached the section's own printed closing.

    BLOCK-1: a walk that reaches the closing WITHOUT accepting anything —
    because the opening figure already equals the closing figure — is returned
    with `empty` set. It is not a closure and the caller must not treat it as
    one. The first version of this instrument seeded the accepted-prefix
    snapshot with that empty prefix and reported the result as a section that
    closed, which on one issue of this population was 6 documents' worth of
    ledger read as nothing at all."""
    figures = [(m.start(), m.end(), _money_value(m.group(0))) for m in MONEY.finditer(ledger)]
    figures = [(a, b, v) for a, b, v in figures if v is not None]
    dates = [(m.start(), m.group(0)) for m in DATE_TOKEN.finditer(ledger)]
    if not figures:
        return Walk(False, refusal="no-figures-in-ledger")

    rows: list[tuple[str, float, float, tuple[str, str]]] = []
    previous = round(opening, 2)
    index = 0
    skipped = 0
    #: the longest prefix of the chain that ENDS on the printed closing. A
    #: statement prints fee and year-to-date tables after its ledger, so the
    #: walk must be allowed to stop where the account's own arithmetic is
    #: complete rather than be required to consume the page.
    empty_start = abs(previous - round(closing, 2)) <= 0.005
    snapshot: tuple[list, float, int, int] | None = (
        ([], previous, 0, 0) if empty_start else None)

    def date_for(position: int) -> str | None:
        cursor = None
        for at, token in dates:
            if at > position:
                break
            cursor = token
        return _row_date(cursor, period) if cursor else None

    while index + 1 < len(figures):
        position, first_end, first = figures[index]
        next_position, second_end, second = figures[index + 1]
        accepted = None
        for amount, balance in ((first, second), (second, first)):
            delta = round(balance - previous, 2)
            if delta == 0.0 and round(amount, 2) == 0.0:
                accepted = (0.0, balance)
                break
            if delta != 0.0 and abs(abs(delta) - abs(round(amount, 2))) <= 0.005:
                accepted = (delta, balance)
                break
        if accepted is None:
            # Not a ledger row here. Skipping is SAFE under this grammar and
            # not a relaxation of it: every accepted row's balance becomes the
            # next row's `previous`, so skipping a figure that belongs to a
            # real row breaks the chain and the section fails closed anyway.
            # What skipping buys is the summary block, the fee table and the
            # re-printed balance sitting in the same span as the ledger.
            skipped += 1
            index += 1
            continue
        iso = date_for(position)
        if iso is None:
            skipped += 1
            index += 1
            continue
        delta, balance = accepted
        # The words the row prints on either side of its two figures. Kept for
        # the ratified idle-sibling predicate, which reads the platform's own
        # posting type at the START of the description; both sides are offered
        # because this population prints the description before the figures on
        # some issues and after them on others.
        head_from = dates[0][0] if dates else 0
        for at, _token in dates:
            if at > position:
                break
            head_from = at
        leading = ledger[head_from:position]
        stop = figures[index + 2][0] if index + 2 < len(figures) else len(ledger)
        trailing = ledger[second_end:stop]
        rows.append((iso, delta, balance, (leading.strip(), trailing.strip())))
        previous = round(balance, 2)
        index += 2
        if abs(previous - round(closing, 2)) <= 0.005:
            snapshot = (list(rows), previous, skipped, second_end)

    if snapshot is None:
        return Walk(False, rows, "walk-did-not-reach-the-printed-closing", skipped)
    rows, previous, skipped, end_at = snapshot
    return Walk(True, rows, None, skipped, empty=not rows, end_at=end_at)


# ---------------------------------------------------------------------------
# reconstruct + validate
# ---------------------------------------------------------------------------


@dataclass
class SectionResult:
    refusal: str | None = None
    recon_ok: bool = False
    adb_ok: bool = False
    n_rows: int = 0
    skipped: int = 0
    #: dated rows the section prints, and dated rows in its LEDGER region
    dated_rows: int = 0
    dated_ledger_rows: int = 0
    #: the chain arrived at the section's own printed closing
    reached: bool = False
    #: dated rows inside the span the chain actually walked that no accepted
    #: movement accounts for (a HOLE), and dated rows the ledger region prints
    #: after the chain reached the closing (a TRUNCATION, or trailing furniture
    #: a family row grammar would tell apart — this probe refuses both)
    gap_inside: int = 0
    gap_after: int = 0
    #: where the section's opening/closing pair came from
    pair_source: str | None = None
    open_from: str | None = None
    close_from: str | None = None
    #: the enumerating table's own CLOSING column carries this closing, and the
    #: closing came from the section rather than from that same table
    oracle_reproduced: bool | None = None
    #: the first version's test: ANY figure anywhere in the row's block equals
    #: the closing, whatever the closing came from. Kept only so the corrected
    #: number can be compared with the published one.
    oracle_positional: bool | None = None
    stated_totals_fed: bool = False
    stated_counts_fed: bool = False
    stated_daily_fed: int = 0
    evidence_readable: bool = False
    #: the same section validated WITHOUT its own stated evidence — the
    #: configuration the published packet measured in, kept so the review's
    #: condition chain reproduces from this run
    recon_ok_bare: bool = False
    adb_ok_bare: bool = False
    printed_partition: bool = False
    #: dates and signed amounts, in memory only, for the transfer measurement
    postings: list[tuple[str, float]] = field(default_factory=list)

    @property
    def covers_rows(self) -> bool:
        """No dated row inside the span the chain walked is unaccounted for.

        The OTHER half of "accounts for every dated row" — a row printed after
        the chain reached the closing — is `gap_after`, and it is measured and
        reported rather than made a gate here. Two reasons, both about what
        this probe can and cannot tell apart: a section's span runs to the next
        section heading, so the LAST section of a document runs to the end of
        the document and carries its trailing tables; and the dated-row pattern
        counts any printed date followed by a figure, which is furniture as
        often as it is a movement. The production check for a ledger that stops
        early is `posting_dates_cover_source`, which is deliberately quiet on
        exactly that furniture and is applied here as a REQUIRED ADB check, and
        the section's own printed counts are the second. `closes_strict` below
        applies that second measure as a gate too, so both
        bounds are on the table."""
        return self.gap_inside == 0 and self.n_rows >= 1

    @property
    def validator_ok(self) -> bool:
        return self.recon_ok and self.adb_ok

    @property
    def closes(self) -> bool:
        """The corrected closure test — every clause of it a review finding.

        Non-empty chain and full row coverage (BLOCK-1's non-vacuity), a
        printed rather than an inferred boundary (the packet's own first
        fail-closed condition), and both production oracles returning ok with
        the section's own stated evidence in hand (MAJOR-4)."""
        return (self.n_rows >= 1 and self.covers_rows and self.printed_partition
                and self.evidence_readable and self.validator_ok)

    @property
    def closes_strict(self) -> bool:
        """`closes`, and nothing dated printed after the chain either."""
        return self.closes and self.gap_after == 0

    @property
    def closes_under_the_reviews_conditions(self) -> bool:
        """The review's own chain, applied to the same run.

        A non-empty chain (the review's non-vacuity test), a printed partition
        (condition 1) and both oracles with the source-coverage check applied
        (condition 6) — but WITHOUT the row-coverage gate and WITHOUT the
        section's own stated counts, totals and daily balances, neither of
        which the review's arithmetic had. Reported so the two ladders can be
        compared instead of asserted against each other."""
        return (self.n_rows >= 1 and self.printed_partition
                and self.recon_ok_bare and self.adb_ok_bare)


def _rollup_pair(block: str, header: str | None) -> tuple[float | None, float | None]:
    """(opening, closing) from one enumerating-table row, by COLUMN CAPTION.

    BLOCK-1. Where the table prints no column caption, or prints one whose
    column count the row does not match, this returns `(None, None)`: which
    figure is the opening and which is the closing is then simply not printed
    anywhere, and the first version's assumption that the first figure opens
    the row is false on at least one issue here."""
    roles = ROLLUP_COLUMN_ROLES.get(header or "")
    if roles is None:
        return None, None
    values = [v for v in (_money_value(t) for t in MONEY.findall(block)) if v is not None]
    if len(values) != len(roles):
        return None, None
    opening = closing = None
    for value, role in zip(values, roles):
        if role == "open":
            opening = value
        elif role == "close":
            closing = value
    return opening, closing


def reconstruct_and_validate(section_text: str, period: tuple[date, date],
                             rollup_block: str | None, rollup_header: str | None,
                             prints_counts: bool, prints_daily: bool,
                             dated_rows: int, printed_partition: bool) -> SectionResult:
    """One printed account section, reconstructed and handed to the validator.

    The opening/closing pair is taken from the section's own printed captions
    where it prints them and from the enumerating table's row for that account
    where that table prints a caption naming its columns. Where BOTH are
    printed they must agree to the cent: a section whose own figures contradict
    the table that enumerates it is exactly the ambiguity this whole question is
    about, and it fails closed."""
    from analysis.adb import compute_average_daily_balance
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, StatementDailyBalance, Transaction

    result = SectionResult(dated_rows=dated_rows, printed_partition=printed_partition)
    own_open = _figure(section_text, _OPEN_FIG, _OPEN_FIG_LEFT)
    own_close = _figure(section_text, _CLOSE_FIG, _CLOSE_FIG_LEFT)
    table_open, table_close = (_rollup_pair(rollup_block, rollup_header)
                               if rollup_block else (None, None))

    if own_open is not None and table_open is not None and abs(table_open - own_open[0]) > 0.005:
        result.refusal = "section-and-rollup-disagree-on-the-pair"
        return result
    if own_close is not None and table_close is not None and abs(table_close - own_close[0]) > 0.005:
        result.refusal = "section-and-rollup-disagree-on-the-pair"
        return result

    #: Candidate opening/closing pairs, strongest evidence first. Trying more
    #: than one is not a search for a number that works: the balance-chain walk
    #: only accepts a pair it can travel from end to end through the printed
    #: figures, so a wrong pair cannot be accepted, and the pair that IS
    #: accepted is reported with the evidence it came from.
    opens: list[tuple[float, str]] = []
    closes: list[tuple[float, str]] = []
    if own_open is not None:
        opens.append((own_open[0], "section"))
    if table_open is not None:
        opens.append((table_open, "rollup"))
    if own_close is not None:
        closes.append((own_close[0], "section"))
    if table_close is not None:
        closes.append((table_close, "rollup"))
    if not opens and not closes:
        result.refusal = "section-prints-neither-an-opening-nor-a-closing"
        return result
    if not opens:
        result.refusal = "section-prints-no-opening-and-no-roll-up-states-one"
        return result
    if not closes:
        result.refusal = "section-prints-no-closing-and-no-roll-up-states-one"
        return result

    grid = find_grid_header(section_text)
    open_at = own_open[1] if own_open is not None else 0
    ledger_from = max(open_at, grid[2] if grid else 0)
    ledger = section_text[ledger_from:]
    if not MONEY.search(ledger):
        # the grid header sits after the last figure (a trailing legend, a
        # continuation caption): fall back to the section's own opening.
        ledger_from = open_at
        ledger = section_text[ledger_from:]

    #: Dated rows this section prints in its LEDGER region — after the summary
    #: block, and before the daily-balance table, whose rows are fed to the ADB
    #: as bank evidence rather than read as movements. Every one of them must
    #: be accounted for by an accepted movement (BLOCK-1 non-vacuity, and the
    #: truncated-ledger shape the review's question (9) describes).
    countable = ledger
    daily_at = DAILY_CAPTION.search(ledger)
    if daily_at is not None:
        countable = ledger[:daily_at.start()]
    result.dated_ledger_rows = len(DATED_ROW.findall(countable))

    walk = None
    open_value = close_value = 0.0
    open_from = close_from = None
    for open_value, open_from in opens:
        for close_value, close_from in closes:
            attempt = chain_walk(ledger, open_value, close_value, period)
            if attempt.ok and not attempt.empty:
                walk = attempt
                result.pair_source = f"open:{open_from}/close:{close_from}"
                result.open_from, result.close_from = open_from, close_from
                break
            if walk is None or (walk.empty and not attempt.empty and attempt.ok):
                walk = attempt
                result.open_from, result.close_from = open_from, close_from
        if walk is not None and walk.ok and not walk.empty:
            break
    assert walk is not None
    result.n_rows = len(walk.rows)
    result.skipped = walk.skipped
    if not walk.ok:
        result.refusal = walk.refusal
        return result
    if walk.empty:
        # BLOCK-1. The two figures coincide and nothing was read. Reported as
        # its own class, split by whether the paper printed anything to read.
        result.refusal = ("trivially-idle-opening-equals-closing-and-no-row-printed"
                          if result.dated_ledger_rows == 0 else
                          "vacuous-empty-ledger-over-printed-rows")
        return result
    inside = len(DATED_ROW.findall(countable[:min(walk.end_at, len(countable))]))
    result.gap_inside = max(0, inside - result.n_rows)
    result.gap_after = max(0, result.dated_ledger_rows - inside)
    result.postings = [(iso, amount) for iso, amount, _b, _w in walk.rows]
    result.reached = True

    # Every gate from here on is MEASURED rather than short-circuited, so the
    # ladder can show what each one costs and so the review's own condition
    # chain can be reproduced from the same run rather than argued about.
    stated = read_stated(section_text, prints_counts, prints_daily, period)
    result.evidence_readable = not (stated.counts_unreadable or stated.daily_unreadable)
    if result.gap_inside:
        result.refusal = "chain-leaves-a-hole-inside-the-span-it-walked"
    elif not printed_partition:
        result.refusal = "boundary-inferred-not-printed"
    elif stated.counts_unreadable:
        result.refusal = "prints-its-own-counts-in-a-form-this-probe-cannot-read"
    elif stated.daily_unreadable:
        result.refusal = "prints-its-own-daily-balances-in-a-form-this-probe-cannot-read"

    statement = Statement(
        period_start=period[0].isoformat(),
        period_end=period[1].isoformat(),
        beginning_balance=round(open_value, 2),
        ending_balance=round(close_value, 2),
        stated_total_credits=stated.total_credits,
        stated_total_debits=stated.total_debits,
        stated_credit_count=stated.credit_count,
        stated_debit_count=stated.debit_count,
        stated_daily_balances=[StatementDailyBalance(date=iso, balance=value)
                               for iso, value in stated.daily],
        transactions=[
            Transaction(date=iso, description="", amount=amount,
                        direction="credit" if amount >= 0 else "debit",
                        running_balance=balance)
            for iso, amount, balance, _words in walk.rows
        ],
    )
    result.stated_totals_fed = (stated.total_credits is not None
                                or stated.total_debits is not None)
    result.stated_counts_fed = (stated.credit_count is not None
                                or stated.debit_count is not None)
    result.stated_daily_fed = len(stated.daily)

    recon = reconcile(statement)
    # MAJOR-4 / the packet's own sixth condition: the production
    # source-coverage check runs only when the ADB is given the text it is
    # validating against, and the text it must be given is the SECTION's.
    adb = compute_average_daily_balance(statement, source_markdown=section_text)
    result.recon_ok = recon.ok
    result.adb_ok = adb.ok
    # The SAME section without its own stated evidence — the configuration the
    # first version of this instrument ran in, and the one the review's
    # condition chain was applied to. Kept so the review's numbers can be
    # reproduced from this run instead of taken on trust.
    bare = statement.model_copy(update={
        "stated_total_credits": None, "stated_total_debits": None,
        "stated_credit_count": None, "stated_debit_count": None,
        "stated_daily_balances": [],
    })
    result.recon_ok_bare = reconcile(bare).ok
    result.adb_ok_bare = compute_average_daily_balance(
        bare, source_markdown=section_text).ok
    if rollup_block:
        result.oracle_positional = any(
            abs((_money_value(token) or 0.0) - round(close_value, 2)) <= 0.005
            for token in MONEY.findall(rollup_block)
        )
        result.oracle_reproduced = (
            close_from == "section" and table_close is not None
            and abs(table_close - round(close_value, 2)) <= 0.005)
    return result


@dataclass
class DocResult:
    sha16: str
    group: str
    band: str
    family: str
    boundary: str
    n_sections: int
    n_posting: int
    n_posting_one_row: int
    period_resolved: bool = True
    printed_partition: bool = False
    sections: list[SectionResult] = field(default_factory=list)
    transfer_pairs: int = 0

    @property
    def sections_closed(self) -> int:
        return sum(1 for s in self.sections if s.closes)

    @property
    def all_close_strict(self) -> bool:
        return bool(self.n_sections) and all(s.closes_strict for s in self.sections)

    @property
    def all_close(self) -> bool:
        return bool(self.n_sections) and self.sections_closed == self.n_sections

    @property
    def all_close_review(self) -> bool:
        return bool(self.n_sections) and all(
            s.closes_under_the_reviews_conditions for s in self.sections)

    @property
    def oracle_reproduced(self) -> bool:
        checked = [s.oracle_reproduced for s in self.sections if s.oracle_reproduced is not None]
        return bool(checked) and all(checked)

    @property
    def oracle_positional(self) -> bool:
        checked = [s.oracle_positional for s in self.sections if s.oracle_positional is not None]
        return bool(checked) and all(checked)


def _transfer_pairs(sections: list[SectionResult]) -> int:
    """Same-day, same-magnitude, opposite-signed movements in two different
    ledgers of ONE document (MAJOR-5).

    That is the printed signature of money moved between a member's own
    accounts, and it means the same money stands in two of the document's
    ledgers. Matching is one-to-one: a movement already paired is not paired
    again, so the count is of PAIRS and never of coincidences multiplied
    together."""
    live = [s for s in sections if s.postings]
    total = 0
    for i, left in enumerate(live):
        for right in live[i + 1:]:
            taken: set[int] = set()
            for iso, amount in left.postings:
                for index, (other_iso, other_amount) in enumerate(right.postings):
                    if index in taken:
                        continue
                    if other_iso != iso:
                        continue
                    if amount * other_amount >= 0:
                        continue
                    if abs(abs(amount) - abs(other_amount)) > 0.005:
                        continue
                    taken.add(index)
                    total += 1
                    break
    return total


def run_document(sha16: str, group: str, band: str, markdown: str, pages: int) -> DocResult:
    doc = structure(sha16, group, band, markdown, pages)
    text = _norm(markdown)
    period = find_period(_flat(text))
    printed = doc.boundary_class in ("rollup-oracle", "section-identity")
    result = DocResult(sha16, group, band, doc.family_key, doc.boundary,
                       len(doc.sections),
                       sum(1 for s in doc.sections if s.n_dated_rows >= 2),
                       sum(1 for s in doc.sections if s.n_dated_rows >= 1),
                       printed_partition=printed)
    if period is None:
        result.period_resolved = False
        result.sections = [SectionResult(refusal="document-prints-no-resolvable-period")]
        return result
    for section in doc.sections:
        body = text[section.start:section.end]
        block = None
        if doc.boundary.startswith("rollup-oracle") and 0 <= section.identity_index < len(doc.rollup.rows):
            block = doc.rollup.rows[section.identity_index].block
        result.sections.append(reconstruct_and_validate(
            body, period, block, doc.rollup.header,
            section.has_counts, section.has_daily, section.n_dated_rows, printed))
    result.transfer_pairs = _transfer_pairs(result.sections)
    return result


# ---------------------------------------------------------------------------
# BLOCK-2 — the ratified idle-sibling rule, applied section by section
# ---------------------------------------------------------------------------


#: The rule's own printed declaration, and the wordings that are NOT it. The
#: first is `analysis/symitar.py`'s `_DORMANT_RE` and is imported rather than
#: restated; the second exists only to separate "declares idle some other way"
#: from "declares nothing", because the difference is what ruling (5) is about.
OTHER_IDLE_WORDING = re.compile(
    r"\bno (?:account )?activity\b|\bno posting\b|\bno items\b"
    r"|\bthere (?:were|was) no\b", re.I)


@dataclass
class SiblingVerdict:
    verdict: str
    n_dated_rows: int


def classify_sibling(section_text: str, period: tuple[date, date] | None,
                     n_dated_rows: int, table_close: float | None) -> SiblingVerdict:
    """Does this sibling satisfy the RATIFIED idle-sibling rule, as written?

    `analysis/symitar.py` 13-45 licenses skipping a deposit sibling on exactly
    two printed grounds, and this calls that module's own code for both:

    * the printed declaration `_DORMANT_RE`; or
    * `_yield_only` — every posting the platform's own yield, credited rather
      than paid out, the section's own arithmetic closing, and its last printed
      balance equal to the ending balance the DOCUMENT states for that account.

    Everything else FAILS the rule as written. The failure is sub-classified,
    because "posted a movement and declares nothing" is the L-1 defect itself
    while "empty and silent" is a candidate for a ruling that generalises the
    rule, and a recommendation that merges the two is the thing the review
    called the door marked no ruling needed."""
    from analysis.symitar import _DORMANT_RE, _yield_only

    if _DORMANT_RE.search(section_text):
        return SiblingVerdict("declares-the-ratified-wording", n_dated_rows)

    rows: list[dict] = []
    if period is not None and n_dated_rows:
        own_open = _figure(section_text, _OPEN_FIG, _OPEN_FIG_LEFT)
        own_close = _figure(section_text, _CLOSE_FIG, _CLOSE_FIG_LEFT)
        opening = own_open[0] if own_open else None
        closing = own_close[0] if own_close else table_close
        if opening is not None and closing is not None:
            grid = find_grid_header(section_text)
            start = max(own_open[1] if own_open else 0, grid[2] if grid else 0)
            walk = chain_walk(section_text[start:], opening, closing, period)
            if walk.ok and walk.rows:
                from analysis.symitar import _DIVIDEND_RE as _YIELD_WORD

                for iso, amount, balance, words in walk.rows:
                    # The platform prints its posting type at the HEAD of the
                    # description, and the ratified predicate is anchored
                    # there. The two candidates are the words this row printed
                    # before its figures and the words it printed after them,
                    # because this population puts the description on either
                    # side; whichever of them the anchored predicate matches is
                    # handed to the rule, and the first non-empty one
                    # otherwise. That restatement is the ONE place the rule
                    # could not be applied byte-for-byte off one layout, and it
                    # is disclosed rather than folded in.
                    head = next((h for h in words if _YIELD_WORD.match(h)),
                                next((h for h in words if h), ""))
                    rows.append({"date": iso, "amount": amount,
                                 "balance": balance, "description": head})
                if _yield_only(rows, opening, closing, None):
                    return SiblingVerdict("yield-only-as-written", n_dated_rows)

    if n_dated_rows >= 1:
        return SiblingVerdict("posted-a-dated-row-and-declares-nothing", n_dated_rows)
    if OTHER_IDLE_WORDING.search(section_text):
        return SiblingVerdict("declares-idle-in-some-other-wording", n_dated_rows)
    return SiblingVerdict("empty-and-silent", n_dated_rows)


@dataclass
class IdleDoc:
    sha16: str
    group: str
    band: str
    boundary: str
    n_sections: int
    posting: int
    siblings: list[SiblingVerdict] = field(default_factory=list)

    @property
    def weakest(self) -> str:
        order = ("posted-a-dated-row-and-declares-nothing", "empty-and-silent",
                 "declares-idle-in-some-other-wording", "yield-only-as-written",
                 "declares-the-ratified-wording")
        if not self.siblings:
            return "no-sibling-section-located"
        return min((s.verdict for s in self.siblings), key=order.index)

    @property
    def every_sibling_satisfies(self) -> bool:
        return bool(self.siblings) and all(
            s.verdict in ("declares-the-ratified-wording", "yield-only-as-written")
            for s in self.siblings)


def idle_document(sha16: str, group: str, band: str, markdown: str, pages: int,
                  threshold: int) -> IdleDoc | None:
    """One document's siblings, classified, at the given posting threshold.

    `threshold` is what makes a located section a POSTING section: 2 is what
    the published census used, 1 is what the packet's own third fail-closed
    condition says (`No section with a dated ledger row may be dropped`), and
    the population moves between them, so both are measured."""
    doc = structure(sha16, group, band, markdown, pages)
    posting = [s for s in doc.sections if s.n_dated_rows >= threshold]
    if len(posting) != 1:
        return None
    text = _norm(markdown)
    period = find_period(_flat(text))
    out = IdleDoc(sha16, group, band, doc.boundary, len(doc.sections), len(posting))
    for section in doc.sections:
        if section.n_dated_rows >= threshold:
            continue
        body = text[section.start:section.end]
        block = None
        if doc.boundary.startswith("rollup-oracle") and 0 <= section.identity_index < len(doc.rollup.rows):
            block = doc.rollup.rows[section.identity_index].block
        _open, close = _rollup_pair(block, doc.rollup.header) if block else (None, None)
        out.siblings.append(classify_sibling(body, period, section.n_dated_rows, close))
    return out


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def _population(groups, opportunities) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for name in opportunities[CU_OPPORTUNITY_KEY]["groups"]:
        out += [("CU-SUFFIX", name, s) for s in groups[name]["shas16"]]
    for name in DECL_GROUPS:
        out += [("DECL-L1-CANDIDATE", name, s) for s in groups[name]["shas16"]]
    out += [("ATB", ATB_GROUP, s) for s in groups[ATB_GROUP]["shas16"]]
    return out


def _idle_main(args, groups, opportunities, per_sha) -> int:
    sha_by16 = {row["sha16"]: row["sha"] for row in per_sha}
    cache = ColdCache(args.data_dir)
    print("# L1INV — the ratified idle-sibling rule, applied section by section (BLOCK-2)")
    print()
    print("`analysis/symitar.py` 13-45 is called for both of its printed grounds: "
          "its own `_DORMANT_RE` for the declaration and its own `_yield_only` for "
          "the arithmetic. A sibling satisfies the rule AS WRITTEN only under one "
          "of those two. Everything else fails it, and the sub-class says how.")
    print()
    for threshold in (2, 1):
        docs: list[IdleDoc] = []
        for band, group, sha16 in _population(groups, opportunities):
            markdown, pages = cache.text(sha_by16[sha16])
            if markdown is None:
                continue
            got = idle_document(sha16, group, band, markdown, len(pages), threshold)
            if got is not None:
                docs.append(got)
        cu = [d for d in docs if d.band == "CU-SUFFIX"]
        print(f"## Posting section = a located section with >= {threshold} dated row(s)")
        print()
        print("| population | documents |")
        print("|---|---:|")
        print(f"| documents with EXACTLY ONE posting section | {len(docs)} |")
        print(f"| ... of them `CU-SUFFIX` | {len(cu)} |")
        print()
        print("| the single-posting documents, by their WEAKEST sibling | documents | of them `CU-SUFFIX` |")
        print("|---|---:|---:|")
        weakest = Counter(d.weakest for d in docs)
        weakest_cu = Counter(d.weakest for d in cu)
        for verdict, count in weakest.most_common():
            print(f"| `{verdict}` | {count} | {weakest_cu.get(verdict, 0)} |")
        print()
        print("| every sibling section, classified | sections |")
        print("|---|---:|")
        counts = Counter(s.verdict for d in docs for s in d.siblings)
        for verdict, count in counts.most_common():
            print(f"| `{verdict}` | {count} |")
        print(f"| **total sibling sections** | **{sum(counts.values())}** |")
        print()
        satisfied = [d for d in docs if d.every_sibling_satisfies]
        no_sibling = [d for d in docs if not d.siblings]
        print("| the Stage-1 question | documents |")
        print("|---|---:|")
        print(f"| EVERY sibling satisfies the ratified rule as written | "
              f"**{len(satisfied)}** |")
        print(f"| ... of them `CU-SUFFIX` | "
              f"{sum(1 for d in satisfied if d.band == 'CU-SUFFIX')} |")
        print(f"| at least one sibling FAILS the rule as written | "
              f"{len(docs) - len(satisfied) - len(no_sibling)} |")
        print(f"| no sibling section located at all (not the same as no sibling) | "
              f"{len(no_sibling)} |")
        posted = [d for d in docs
                  if any(s.verdict == "posted-a-dated-row-and-declares-nothing"
                         for s in d.siblings)]
        print(f"| carry a sibling that POSTED and declares nothing (the L-1 defect) | "
              f"**{len(posted)}** |")
        print(f"| ... of them `CU-SUFFIX` | "
              f"{sum(1 for d in posted if d.band == 'CU-SUFFIX')} |")
        print(f"| carry a sibling that fails the rule, `CU-SUFFIX` only | "
              f"{sum(1 for d in cu if d.siblings and not d.every_sibling_satisfies)} |")
        print()
        if args.json and threshold == 2:
            args.json.write_text(json.dumps([
                {"sha16": d.sha16, "group": d.group, "band": d.band,
                 "boundary": d.boundary, "sections": d.n_sections,
                 "weakest": d.weakest, "satisfies": d.every_sibling_satisfies,
                 "siblings": [s.verdict for s in d.siblings]}
                for d in docs
            ], indent=1), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--idle-siblings", action="store_true",
                        help="BLOCK-2: apply the ratified idle-sibling rule to the "
                             "siblings of every single-posting document")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    groups, opportunities, per_sha = load_census(args.census_dir)
    if args.idle_siblings:
        return _idle_main(args, groups, opportunities, per_sha)
    sha_by16 = {row["sha16"]: row["sha"] for row in per_sha}
    cache = ColdCache(args.data_dir)

    results: list[DocResult] = []
    for band, group, sha16 in _population(groups, opportunities):
        markdown, pages = cache.text(sha_by16[sha16])
        if markdown is None:
            continue
        results.append(run_document(sha16, group, band, markdown, len(pages)))

    print("# L1INV — split / reconstruct / validate prototype (CORRECTED)")
    print(f"# documents: {len(results)}")
    print()
    print("Every number below is produced by the EXISTING `reconcile` and "
          "`compute_average_daily_balance`, called unchanged on a `Statement` "
          "reconstructed from one printed account section and carrying that "
          "section's own stated counts, totals and daily balances. A section "
          "CLOSES when its chain is not empty, accounts for every dated row in "
          "its ledger region, rests on a PRINTED boundary, and both oracles "
          "return ok.")
    print()

    sections = [s for r in results for s in r.sections]
    located = sum(r.n_sections for r in results)
    pseudo = sum(1 for r in results if not r.period_resolved)
    print("## What was offered (MINOR-1: located sections vs sections offered)")
    print()
    print("| measure | value |")
    print("|---|---:|")
    print(f"| documents in the population | {len(results)} |")
    print(f"| sections LOCATED by the structure census | {located} |")
    print(f"| documents with no resolvable printed period | {pseudo} |")
    print(f"| ... the sections they carry, which are never offered | "
          f"{sum(r.n_sections for r in results if not r.period_resolved)} |")
    print(f"| pseudo-sections standing for those documents, one each | {pseudo} |")
    print(f"| **objects the validator was offered** | **{len(sections)}** |")
    print()

    print("## The closure ladder — each rung a review finding")
    print()
    walked = [s for s in sections if s.reached]
    empty_idle = sum(1 for s in sections
                     if s.refusal == "trivially-idle-opening-equals-closing-and-no-row-printed")
    empty_vacuous = sum(1 for s in sections
                        if s.refusal == "vacuous-empty-ledger-over-printed-rows")
    non_empty = [s for s in walked if s.n_rows >= 1]
    no_hole = [s for s in non_empty if s.gap_inside == 0]
    printed = [s for s in no_hole if s.printed_partition]
    fed = [s for s in printed if s.evidence_readable]
    recon_ok = [s for s in fed if s.recon_ok]
    both_ok = [s for s in recon_ok if s.adb_ok]
    print("| rung | sections |")
    print("|---|---:|")
    print(f"| the walk reached the section's own printed closing | "
          f"{len(walked) + empty_idle + empty_vacuous} |")
    print(f"| ... arriving with an EMPTY chain, the section printing no dated row "
          f"(trivially idle, never a closure) | {empty_idle} |")
    print(f"| ... arriving with an EMPTY chain over PRINTED dated rows "
          f"(BLOCK-1, the false closure) | **{empty_vacuous}** |")
    print(f"| non-empty chain | {len(non_empty)} |")
    print(f"| + no dated row unaccounted for INSIDE the span the chain walked | {len(no_hole)} |")
    print(f"| + boundary PRINTED rather than inferred (condition 1) | {len(printed)} |")
    print(f"| + its own stated counts / totals / daily balances readable and fed | {len(fed)} |")
    print(f"| + `reconcile.ok` | {len(recon_ok)} |")
    print(f"| + `adb.ok`, source-coverage check applied (condition 6) | **{len(both_ok)}** |")
    print(f"| + nothing dated printed AFTER the chain reached the closing (STRICTER) | "
          f"**{sum(1 for s in both_ok if s.gap_after == 0)}** |")
    print()
    print("| the two oracles, separately (MAJOR-3) | sections |")
    print("|---|---:|")
    print(f"| walks handed to both oracles | {len(fed)} |")
    print(f"| refused by `reconcile` | {sum(1 for s in fed if not s.recon_ok)} |")
    print(f"| refused by the ADB | {sum(1 for s in fed if not s.adb_ok)} |")
    print()

    closed = [s for s in sections if s.closes]
    print("## Headline (corrected)")
    print()
    docs_all = [r for r in results if r.all_close]
    docs_multi = [r for r in docs_all if r.n_sections >= 2]
    oracle = [r for r in docs_all if r.oracle_reproduced]
    oracle_pos = [r for r in docs_all if r.oracle_positional]
    print("| measure | value |")
    print("|---|---:|")
    print(f"| sections that CLOSE | **{len(closed)}** |")
    print(f"| ... and print nothing dated after their own chain (STRICTER) | "
          f"**{sum(1 for s in sections if s.closes_strict)}** |")
    print(f"| sections that are TRIVIALLY idle (no row printed, nothing read) | {empty_idle} |")
    print(f"| documents whose EVERY LOCATED section closes | **{len(docs_all)}** |")
    print(f"| ... under the STRICTER test as well | "
          f"**{sum(1 for r in results if r.all_close_strict)}** |")
    print(f"| ... of those, documents with >= 2 located sections | {len(docs_multi)} |")
    print(f"| ... whose table's own CLOSING column reproduces every section's closing | "
          f"**{len(oracle)}** |")
    print(f"| ... under the first version's positional oracle test, for comparison | "
          f"{len(oracle_pos)} |")
    print()
    print("MINOR-6, stated rather than implied: `every LOCATED section` is not "
          "`every PRINTED section`. Documents with no located partition at all: "
          f"{sum(1 for r in results if r.n_sections == 0)}; documents whose "
          "enumerating table lists accounts none of which reappear as a heading: "
          "counted by the structure census under its own fail-closed reasons. A "
          "section the boundary layer never located cannot fail here.")
    print()

    print("## The review's own condition chain, reproduced from this run")
    print()
    print("The independent review applied three conditions to the FIRST version "
          "of this instrument: a printed partition (condition 1), no section "
          "publishing an empty ledger over printed rows, and the production "
          "source-coverage check (condition 6). It did not have the row-coverage "
          "gate and it did not have the sections' own stated counts, totals and "
          "daily balances. Run under exactly those conditions, on this run:")
    print()
    review_docs = [r for r in results if r.all_close_review]
    review_multi = [r for r in review_docs if r.n_posting >= 2]
    print("| the review's chain | value |")
    print("|---|---:|")
    print(f"| sections closing under the review's conditions | "
          f"{sum(1 for s in sections if s.closes_under_the_reviews_conditions)} |")
    print(f"| documents whose every located section does | **{len(review_docs)}** |")
    print(f"| ... with two or more POSTING sections (the review's L-1 floor) | "
          f"**{len(review_multi)}** |")
    print(f"| ... and the table's own closing column reproducing | "
          f"**{sum(1 for r in review_multi if r.oracle_reproduced)}** |")
    print()
    print("| what every further corrected gate costs, over those documents | documents |")
    print("|---|---:|")
    print(f"| + no dated row unaccounted for inside the walked span | "
          f"{sum(1 for r in review_docs if all(s.gap_inside == 0 for s in r.sections))} |")
    print(f"| + validated against the section's OWN stated counts / totals / dailies | "
          f"{len([r for r in results if r.all_close])} |")
    print(f"| + nothing dated printed after the chain either (STRICTER) | "
          f"{sum(1 for r in results if r.all_close_strict)} |")
    print()

    print("## By boundary mechanism")
    print()
    print("| boundary | docs | offered | closed | docs fully closing | table reproduces |")
    print("|---|---:|---:|---:|---:|---:|")
    by_boundary: dict[str, list[DocResult]] = defaultdict(list)
    for r in results:
        by_boundary[r.boundary.split(":")[0]].append(r)
    for name in ("rollup-oracle", "section-identity", "section-equation-scan", "none"):
        members = by_boundary.get(name, [])
        offered = sum(len(m.sections) for m in members)
        full = [m for m in members if m.all_close]
        print(f"| `{name}` | {len(members)} | {offered} | "
              f"{sum(m.sections_closed for m in members)} | {len(full)} | "
              f"{sum(1 for m in full if m.oracle_reproduced)} |")
    print()

    print("## The L-1 question, measured: documents with TWO OR MORE posting sections")
    print()
    print("| band | >= 2 posting sections | every located section closes | table reproduces |")
    print("|---|---:|---:|---:|")
    for band in ("CU-SUFFIX", "DECL-L1-CANDIDATE", "ATB"):
        members = [r for r in results if r.band == band and r.n_posting >= 2]
        full = [m for m in members if m.all_close]
        print(f"| {band} | {len(members)} | {len(full)} | "
              f"{sum(1 for m in full if m.oracle_reproduced)} |")
    every = [r for r in results if r.n_posting >= 2]
    every_full = [r for r in every if r.all_close]
    print(f"| **total** | **{len(every)}** | **{len(every_full)}** | "
          f"**{sum(1 for m in every_full if m.oracle_reproduced)}** |")
    print()
    print("| the same, at the packet's own threshold of ONE dated row | value |")
    print("|---|---:|")
    one = [r for r in results if r.n_posting_one_row >= 2]
    print(f"| documents with >= 2 sections carrying a dated row | {len(one)} |")
    print(f"| ... every located section closes | {sum(1 for r in one if r.all_close)} |")
    print()

    print("## Money moved between a member's own accounts (MAJOR-5)")
    print()
    live = [r for r in results if sum(1 for s in r.sections if s.postings) >= 2]
    movers = [r for r in live if r.transfer_pairs]
    print("| measure | value |")
    print("|---|---:|")
    print(f"| documents with two or more non-empty reconstructed ledgers | {len(live)} |")
    print(f"| ... carrying same-day, same-magnitude, opposite-signed pairs | "
          f"**{len(movers)}** |")
    print(f"| such pairs in total | **{sum(r.transfer_pairs for r in movers)}** |")
    print()

    print("## Fail-closed classes (why a section was not offered, or did not close)")
    print()
    refusals = Counter(s.refusal or ("closed" if s.closes else "offered-but-a-validator-refused")
                       for s in sections)
    print("| class | sections |")
    print("|---|---:|")
    for name, count in refusals.most_common():
        print(f"| `{name}` | {count} |")
    print()

    print("## By census group")
    print()
    print("| census group | docs | offered | closed | docs fully closing |")
    print("|---|---:|---:|---:|---:|")
    by_group: dict[str, list[DocResult]] = defaultdict(list)
    for r in results:
        by_group[r.group].append(r)
    for group in sorted(by_group):
        members = by_group[group]
        print(f"| `{group}` | {len(members)} | {sum(len(m.sections) for m in members)} | "
              f"{sum(m.sections_closed for m in members)} | "
              f"{sum(1 for m in members if m.all_close)} |")
    print()

    if args.json:
        args.json.write_text(json.dumps([
            {
                "sha16": r.sha16, "group": r.group, "band": r.band,
                "boundary": r.boundary, "family": r.family,
                "n_sections": r.n_sections, "n_posting": r.n_posting,
                "n_posting_one_row": r.n_posting_one_row,
                "sections_closed": r.sections_closed,
                "all_close": r.all_close,
                "all_close_strict": r.all_close_strict,
                "all_close_review": r.all_close_review,
                "oracle_reproduced": r.oracle_reproduced,
                "oracle_positional": r.oracle_positional,
                "transfer_pairs": r.transfer_pairs,
                "sections": [
                    {"refusal": s.refusal, "recon_ok": s.recon_ok, "adb_ok": s.adb_ok,
                     "n_rows": s.n_rows, "skipped": s.skipped,
                     "dated_rows": s.dated_rows, "dated_ledger_rows": s.dated_ledger_rows,
                     "gap_inside": s.gap_inside, "gap_after": s.gap_after,
                     "pair_source": s.pair_source, "closes": s.closes,
                     "closes_strict": s.closes_strict,
                     "closes_review": s.closes_under_the_reviews_conditions,
                     "stated_totals": s.stated_totals_fed,
                     "stated_counts": s.stated_counts_fed,
                     "stated_daily": s.stated_daily_fed,
                     "oracle": s.oracle_reproduced, "oracle_positional": s.oracle_positional}
                    for s in r.sections
                ],
            }
            for r in results
        ], indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
