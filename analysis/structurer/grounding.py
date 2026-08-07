"""Source grounding: the second validation axis (W3-3b ruling 3).

Reconciliation proves ARITHMETIC. It cannot prove that a number was ever
printed on the page. A structurer that mis-reads a column, re-uses one printed
figure for two rows, or supplies a year the document never printed can produce
a set of numbers that adds up perfectly and describes a statement that does not
exist. Grounding is the independent check: **every value that can influence a
published financial result must be locatable in the source text.**

Rebuilt from the concepts in the archived prototype's `analysis/grounding.py`
(`archive/universal-prototype-2026-08-05`, commit 54a9e8d) — amount-on-its-page,
description-token proximity, span uniqueness, label-adjacent summary values,
period scoping, no-provenance-is-a-failure — against the post-R-2 shared money
and date utilities, and reviewed heuristic by heuristic. The prototype checked
a MODEL's output; the mechanism is extractor-agnostic and works unchanged on a
deterministic structurer, where the mistakes it catches are inference errors
rather than hallucinations.

Deliberately independent of `rows.py`: grounding re-locates every value in the
raw page text, so it cannot inherit the reasoning that produced the value. A
check that shares its evidence with the thing it checks proves nothing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .rows import RowCandidate
from .summary import Period, SummaryValue

__all__ = ["GroundingResult", "ground_statement", "pages_from_markdown"]

_PAGE_MARKER_RE = re.compile(r"---\s*Page\s+(\d+)(?:\s*\(empty\))?\s*---", re.IGNORECASE)
_WORD_RE = re.compile(r"[A-Z0-9]{3,}")
_HTML_TAG_RE = re.compile(r"<[^>]+>")

#: Words that appear on every statement and therefore identify nothing. A
#: description grounded only by the word "PAYMENT" is not grounded.
_GENERIC_WORDS = frozenset({
    "ACCOUNT", "AMOUNT", "BALANCE", "BANK", "CHECK", "CHEQUE", "CREDIT", "DEBIT",
    "DEPOSIT", "PAYMENT", "POSTED", "POSTING", "TRANSACTION", "TRANSFER",
    "WITHDRAWAL", "DESCRIPTION", "DATE", "TOTAL", "REF", "NUMBER",
})

#: How far from the amount its date and description may sit. One printed row is
#: comfortably inside this; the next row's amount is not.
_ROW_WINDOW = 240
_LABEL_WINDOW = 180

#: Labels a summary value may be grounded by, per field. Same vocabulary as
#: `summary.py` reads with — stated once, in the module that reads it — but
#: applied here to the RAW page text.
_FIELD_LABELS: dict[str, tuple[str, ...]] = {
    "beginning_balance": ("BEGINNING BALANCE", "OPENING BALANCE", "PREVIOUS BALANCE",
                          "BALANCE FORWARD", "BALANCE BROUGHT FORWARD", "SOLDE PRECEDENT"),
    "ending_balance": ("ENDING BALANCE", "CLOSING BALANCE", "NEW BALANCE", "FINAL BALANCE",
                       "SOLDE FINAL"),
    "stated_total_credits": ("TOTAL DEPOSITS", "TOTAL CREDITS", "DEPOSITS AND OTHER CREDITS",
                             "DEPOSITS/CREDITS"),
    "stated_total_debits": ("TOTAL WITHDRAWALS", "TOTAL DEBITS", "WITHDRAWALS AND OTHER DEBITS",
                            "CHECKS AND OTHER DEBITS"),
    "stated_average_balance": ("AVERAGE DAILY BALANCE", "AVERAGE LEDGER BALANCE",
                               "AVERAGE COLLECTED BALANCE"),
    "stated_service_charge": ("SERVICE CHARGE", "TOTAL FEES"),
    "stated_interest_paid": ("INTEREST PAID", "INTEREST EARNED"),
}


@dataclass(frozen=True)
class GroundingResult:
    """Whether this extraction is supported by the source, and where it is not."""

    ok: bool
    method: str
    transaction_count: int
    grounded_transactions: int
    ungrounded_transactions: tuple[int, ...] = ()
    ungrounded_fields: tuple[str, ...] = ()
    period_grounded: bool = True
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def coverage(self) -> float:
        if not self.transaction_count:
            return 0.0
        return self.grounded_transactions / self.transaction_count


def pages_from_markdown(markdown: str) -> dict[int, str]:
    """Page number -> that page's text. One page when the reader printed no
    markers, which is the honest answer rather than a guess."""
    text = _HTML_TAG_RE.sub(" ", markdown)
    matches = list(_PAGE_MARKER_RE.finditer(text))
    if not matches:
        return {1: text}
    pages: dict[int, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        pages[int(match.group(1))] = text[match.end():end]
    return pages


def _money_text(value: float) -> str:
    amount = Decimal(str(abs(value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def _compact(text: str) -> str:
    """Thousands separators removed so `1,234.56` and `1234.56` are one string.

    Offsets shift relative to the original, which is harmless and deliberate:
    every span this module computes, compares and remembers is a span in the
    compacted page, and none of them is ever reported back to a reader.
    """
    return text.replace(",", "")


def _amount_spans(compact: str, value: float) -> list[tuple[int, int]]:
    pattern = re.compile(rf"(?<![\d.]){re.escape(_money_text(value))}(?!\d)")
    return [(match.start(), match.end()) for match in pattern.finditer(compact)]


def _date_renderings(iso: str) -> set[str]:
    """The ways one date can be printed. Condensed from the prototype's
    `_date_variants`, which enumerated the same space."""
    try:
        parsed = date.fromisoformat(iso)
    except ValueError:
        return set()
    day, month, year = parsed.day, parsed.month, parsed.year
    short_month = parsed.strftime("%b").upper()
    long_month = parsed.strftime("%B").upper()
    renderings = {iso.upper()}
    for separator in ("/", "-", "."):
        renderings |= {
            f"{month:02d}{separator}{day:02d}",
            f"{month}{separator}{day}",
            f"{month:02d}{separator}{day:02d}{separator}{year}",
            f"{month:02d}{separator}{day:02d}{separator}{year % 100:02d}",
            f"{month}{separator}{day}{separator}{year}",
            f"{month}{separator}{day}{separator}{year % 100:02d}",
            f"{day:02d}{separator}{month:02d}{separator}{year}",
            f"{day:02d}{separator}{month:02d}{separator}{year % 100:02d}",
            f"{year}{separator}{month:02d}{separator}{day:02d}",
        }
    renderings |= {
        f"{short_month} {day}", f"{short_month} {day:02d}", f"{short_month}. {day}",
        f"{long_month} {day}", f"{long_month} {day:02d}",
        f"{day} {short_month}", f"{day:02d} {short_month}",
    }
    return renderings


def _date_is_near(window: str, iso: str) -> bool:
    upper = window.upper()
    return any(
        re.search(rf"(?<![A-Z0-9]){re.escape(rendering)}(?![A-Z0-9])", upper)
        for rendering in _date_renderings(iso)
    )


def _description_tokens(description: str) -> set[str]:
    return {
        token for token in _WORD_RE.findall(description.upper())
        if token not in _GENERIC_WORDS and not token.isdigit()
    }


def _ground_row(row: RowCandidate, pages: dict[int, str],
                used: set[tuple[int, int, int]]) -> bool:
    """One transaction: its amount printed on its page, beside its date, with a
    distinctive word of its description, in a span no other row has claimed."""
    if abs(row.amount) < 0.005:
        return False
    candidates = (
        [(row.page, pages[row.page])] if row.page in pages else list(pages.items())
    )
    tokens = _description_tokens(row.description)
    required = min(1, len(tokens))
    best: tuple[int, int, int] | None = None
    for page_number, page_text in candidates:
        compact = _compact(page_text)
        for start, end in _amount_spans(compact, row.amount):
            key = (page_number, start, end)
            if key in used:
                continue
            window = compact[max(0, start - _ROW_WINDOW):end + _ROW_WINDOW]
            if not _date_is_near(window, row.date):
                continue
            upper = window.upper()
            if sum(1 for token in tokens if token in upper) < required:
                continue
            best = key
            break
        if best:
            break
    if best is None:
        return False
    used.add(best)
    return True


def _ground_summary_field(value: SummaryValue, pages: dict[int, str]) -> bool:
    labels = _FIELD_LABELS.get(value.field, ())
    if not labels:
        return False
    page_text = pages.get(value.page)
    texts = [page_text] if page_text is not None else list(pages.values())
    for text in texts:
        compact = _compact(text)
        for start, end in _amount_spans(compact, value.value):
            window = compact[max(0, start - _LABEL_WINDOW):end + _LABEL_WINDOW].upper()
            if any(label in window for label in labels):
                return True
    return False


def ground_statement(
    rows: list[RowCandidate],
    summary: dict[str, SummaryValue],
    period: Period | None,
    markdown: str,
    *,
    published_fields: tuple[str, ...],
    min_transaction_coverage: float = 1.0,
) -> GroundingResult:
    """Ground everything that can influence a published value.

    `min_transaction_coverage` defaults to **1.0**: every transaction, not most
    of them. A statement is published as a complete ledger, the ADB engine
    integrates over all of it, and "94% of these rows exist" is not a statement
    anyone can underwrite. The parameter exists so the measurement harness can
    report the distribution, not so production can lower the bar.
    """
    pages = pages_from_markdown(markdown)
    used: set[tuple[int, int, int]] = set()
    ungrounded = tuple(
        index for index, row in enumerate(rows) if not _ground_row(row, pages, used)
    )
    grounded = len(rows) - len(ungrounded)

    ungrounded_fields = tuple(
        name for name in published_fields
        if name in summary and not _ground_summary_field(summary[name], pages)
    )
    missing_fields = tuple(name for name in published_fields if name not in summary)

    period_grounded = period is not None
    notes: list[str] = []
    if not rows:
        notes.append("no transactions to ground")
    if missing_fields:
        notes.append(f"summary fields absent from the source: {', '.join(missing_fields)}")
    if ungrounded_fields:
        notes.append(f"summary fields not printed beside their label: {', '.join(ungrounded_fields)}")
    if ungrounded:
        notes.append(f"{len(ungrounded)} transaction(s) not found in the source text")
    if not period_grounded:
        notes.append("no printed statement period")

    ok = (
        bool(rows)
        and period_grounded
        and not ungrounded_fields
        and not missing_fields
        and (grounded / len(rows) if rows else 0.0) >= min_transaction_coverage
    )
    return GroundingResult(
        ok=ok,
        method="deterministic_structurer_source_grounding",
        transaction_count=len(rows),
        grounded_transactions=grounded,
        ungrounded_transactions=ungrounded,
        ungrounded_fields=ungrounded_fields + missing_fields,
        period_grounded=period_grounded,
        notes=tuple(notes),
    )
