"""The printed summary block: period, opening and closing balance, totals.

Adapted from `analysis/grounding.py` on the archived prototype
(`archive/universal-prototype-2026-08-05`, commit 54a9e8d), which used this
label vocabulary in the opposite direction — it checked that a claimed value
sat beside an appropriate label. The relation is the same either way, so the
vocabulary is reused (rebuilt against the post-R-2 shared money utilities, and
reviewed label by label) while the prototype's architecture is not.

Everything here keeps its provenance — which line, which span — because a
summary value that cannot be pointed at on the page is exactly what grounding
must refuse.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from .rows import SourceLine
from .tokens import MoneyToken, iso_from_any, money_tokens, read_date

__all__ = ["SummaryValue", "STATEMENT_LABELS", "read_summary", "read_period"]


@dataclass(frozen=True)
class SummaryValue:
    field: str
    value: float
    page: int
    line_index: int
    label: str
    token: MoneyToken
    #: The date printed on the same line as the label, when there is one.
    #: "Your balance forward on Jul 31, 2023" states both a balance and a
    #: period anchor, and a structurer that reads only the number throws the
    #: anchor away — which cost the largest single block of refusals measured
    #: in 3a's stratum A.
    anchor_date: str | None = None


#: (label, Statement field). Order matters only for the more-specific-first
#: rule below: "average collected balance" must not be read as "balance".
STATEMENT_LABELS: tuple[tuple[str, str], ...] = (
    ("BEGINNING BALANCE", "beginning_balance"),
    ("OPENING BALANCE", "beginning_balance"),
    ("PREVIOUS BALANCE", "beginning_balance"),
    ("BALANCE FORWARD", "beginning_balance"),
    ("BALANCE BROUGHT FORWARD", "beginning_balance"),
    ("SOLDE PRECEDENT", "beginning_balance"),
    ("ENDING BALANCE", "ending_balance"),
    ("CLOSING BALANCE", "ending_balance"),
    ("NEW BALANCE", "ending_balance"),
    ("FINAL BALANCE", "ending_balance"),
    ("SOLDE FINAL", "ending_balance"),
    ("TOTAL DEPOSITS", "stated_total_credits"),
    ("TOTAL CREDITS", "stated_total_credits"),
    ("DEPOSITS AND OTHER CREDITS", "stated_total_credits"),
    ("DEPOSITS/CREDITS", "stated_total_credits"),
    ("TOTAL WITHDRAWALS", "stated_total_debits"),
    ("TOTAL DEBITS", "stated_total_debits"),
    ("WITHDRAWALS AND OTHER DEBITS", "stated_total_debits"),
    ("CHECKS AND OTHER DEBITS", "stated_total_debits"),
    ("AVERAGE DAILY BALANCE", "bank_reported_average_balance"),
    ("AVERAGE LEDGER BALANCE", "bank_reported_average_balance"),
    ("AVERAGE COLLECTED BALANCE", "bank_reported_average_balance"),
    ("SERVICE CHARGE", "stated_service_charge"),
    ("TOTAL FEES", "stated_service_charge"),
    ("INTEREST PAID", "stated_interest_paid"),
    ("INTEREST EARNED", "stated_interest_paid"),
)

#: Fields whose printed value is a magnitude, never a direction.
_ABSOLUTE_FIELDS = frozenset({
    "stated_total_credits", "stated_total_debits", "bank_reported_average_balance",
    "stated_service_charge", "stated_interest_paid",
})

#: A label and its value are on the same line, and near each other. Without the
#: distance rule a wide two-column page pairs "Ending balance" on the left with
#: an unrelated figure on the right.
_MAX_LABEL_DISTANCE = 80


def read_summary(lines: list[SourceLine]) -> dict[str, SummaryValue]:
    """First value printed beside each label, keeping where it was printed.

    First wins because statements print their summary block before their
    detail, and a repeat later in the document (a per-page or per-account
    subtotal) is a different figure that must not overwrite the block.
    """
    found: dict[str, SummaryValue] = {}
    for line in lines:
        upper = line.text.upper()
        for label, field in STATEMENT_LABELS:
            index = upper.find(label)
            if index < 0 or field in found:
                continue
            after = index + len(label)
            token = next(
                (token for token in money_tokens(line.text)
                 if token.start >= after and token.start - after <= _MAX_LABEL_DISTANCE),
                None,
            )
            if token is None:
                continue
            value = abs(token.value) if field in _ABSOLUTE_FIELDS else token.value
            found[field] = SummaryValue(
                field, value, line.page, line.index, label, token,
                anchor_date=iso_from_any(line.text, default_year=None),
            )
    return found


#: A month name is 3 to 9 letters ("May", "September"). Bounding it matters
#: for more than tidiness: written as `[A-Z][a-z]+` under IGNORECASE, this
#: pattern backtracks quadratically on a long run of letters, and a 20,000-
#: character line — which OCR and single-line PDFs both produce — took nine
#: seconds to reject. A structurer that can be stalled by one pathological
#: document cannot run over an archive.
_MONTH_NAME = r"[A-Za-z]{3,9}\.?"
_DATE_ALTERNATIVES = (
    rf"\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}|{_MONTH_NAME}\s+\d{{1,2}},?\s+\d{{4}}|"
    rf"\d{{1,2}}\s+{_MONTH_NAME}\s+\d{{4}}"
)
_RANGE_RE = re.compile(
    rf"(?P<a>{_DATE_ALTERNATIVES})"
    r"\s*(?:-|–|—|to|through|thru|au|until)\s*"
    rf"(?P<b>{_DATE_ALTERNATIVES})",
    re.IGNORECASE,
)

#: A printed statement period sits on a line of ordinary length. Anything
#: longer is a flattened page, and scanning it for a period costs more than it
#: can return.
_MAX_PERIOD_LINE = 600

#: A statement period is a billing cycle. Anything outside this is a different
#: kind of date range that happens to be printed on the page (a rate table, an
#: address, a year-to-date column).
_MIN_PERIOD_DAYS = 5
_MAX_PERIOD_DAYS = 100


@dataclass(frozen=True)
class Period:
    start: str
    end: str
    page: int
    line_index: int
    text: str
    #: "range" — printed as one span. "balance_anchors" — reconstructed from the
    #: two dates the document prints beside its opening and closing balances.
    source: str = "range"
    #: True when `start` is the day AFTER a printed prior-close date rather than
    #: a date the document prints. The one value in this subsystem that is not
    #: read off the page, so it is marked as such wherever it travels
    #: (W3-3b Q2 ruling): grounding notes it, and any posting dated before it
    #: refuses the document rather than being absorbed into the period.
    start_inferred: bool = False

    @property
    def provenance(self) -> str:
        if self.start_inferred:
            return f"{self.source}:start_inferred_from_prior_close"
        return self.source


#: Labels whose date is the PRIOR period's close, so the period starts the day
#: after. "Balance forward on Jul 31" is the 31st's closing balance; the
#: statement it opens covers August. Reading it as August 31 days vs 32 is a
#: 3% error in every average-daily-balance built on it, so the distinction is
#: made explicitly rather than averaged over.
_PRIOR_CLOSE_LABELS = frozenset({
    "BALANCE FORWARD", "BALANCE BROUGHT FORWARD", "PREVIOUS BALANCE", "SOLDE PRECEDENT",
})


def read_period(lines: list[SourceLine], summary: dict[str, SummaryValue] | None = None) -> Period | None:
    """The printed statement period, or None if the document does not print one.

    Two strategies, both requiring dates the DOCUMENT printed:

    1. an explicit range ("January 1, 2026 to January 31, 2026");
    2. the anchor dates printed beside the opening and closing balances, which
       is how a large family of layouts states its period — they print
       "balance forward on <date>" and "closing balance on <date>" and never a
       range at all.

    What is never done is deriving the period from the transactions. That would
    shorten every period whose opening days had no activity, and the ADB engine
    divides by the length.
    """
    for line in lines:
        if len(line.text) > _MAX_PERIOD_LINE:
            continue
        for match in _RANGE_RE.finditer(line.text):
            start = read_date(match.group("a"), default_year=None)
            end = read_date(match.group("b"), default_year=None)
            period = _validated(start, end, line.page, line.index, match.group(0), "range")
            if period is not None:
                return period

    if not summary:
        return None
    opening = summary.get("beginning_balance")
    closing = summary.get("ending_balance")
    if opening is None or closing is None or not opening.anchor_date or not closing.anchor_date:
        return None
    start = opening.anchor_date
    inferred = opening.label in _PRIOR_CLOSE_LABELS
    if inferred:
        start = (date.fromisoformat(start) + timedelta(days=1)).isoformat()
    return _validated(
        start, closing.anchor_date, opening.page, opening.line_index,
        f"{opening.label} / {closing.label}", "balance_anchors",
        start_inferred=inferred,
    )


def _validated(start: str | None, end: str | None, page: int, line_index: int,
               text: str, source: str, *, start_inferred: bool = False) -> Period | None:
    if not start or not end or start > end:
        return None
    span = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    if not (_MIN_PERIOD_DAYS <= span <= _MAX_PERIOD_DAYS):
        return None
    return Period(start, end, page, line_index, text, source, start_inferred=start_inferred)
