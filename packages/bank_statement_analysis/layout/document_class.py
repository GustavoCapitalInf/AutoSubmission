"""layout/document_class.py — the deterministic document classifier
(Phase 2.2 cell C; umbrella §"Classifier", D1, D2, cases 1–5; plan §J).

`classify_document(*, evidence, page_texts, profile) -> DocumentClass`
gives every document exactly ONE `kind` from the closed `KINDS`, the named
signals that produced it (`EvidenceRef`s with word ids or character spans),
a tier that says how the verdict was earned, and — for a partial statement —
the completeness findings that say what is missing. It is a pure function of
its three arguments: no clock, no randomness, no I/O, no state. It never
routes and never grants anything; a verdict is a recorded fact and a
proposal for an adjudicator (R3), never truth.

Inputs and modes
----------------
* `evidence` — canonical `ExtractionEvidence` (native or Paddle words with
  boxes). EVIDENCE mode: every signal is available; the table signal is
  geometric (right-aligned money column); the cheque signal reads the MICR
  band and the page aspect; the screenshot signal reads the frame.
* `page_texts` — page strings only (a Tesseract-only read, or a cache's
  page text). DEGRADED mode, declared: box-dependent signals cannot fire,
  the table signal is its line-count form, and the tier can be `structural`
  only on a fact that needs no box (a page-marker gap, the file facts).
* `profile` — `DocumentProfileFacts`, the preflight FACTS (validity,
  encryption, page count, digital/scanned/mixed/unknown, per-page native
  character counts, the file's first bytes). `FILE_INVALID` is decided from
  the facts alone, before any text is read.
Exactly one of `evidence` / `page_texts` may be given (both is a refusal);
neither is `KIND_UNCERTAIN`.

Decision order (ruled)
----------------------
1. `FILE_INVALID` — invalid PDF, encrypted, zero pages, or the Java
   object-serialisation magic.
2. Conflicts → `KIND_UNCERTAIN`: a table signal beside a cheque signal; a
   card lexicon beside a running balance; two non-statement sub-kinds at
   once; a deposit-slip / letter / screenshot lexicon beside two statement
   anchors. Signals are LISTED, never resolved by priority.
3. Non-statement sub-kinds, when their signals fire WITHOUT a statement
   table signal: cheque / voided cheque, deposit slip, letter, card, loan,
   brokerage, screenshot. The card statement alone may carry a table, and
   only a card-shaped one: a single amount column, no running balance, no
   deposit-account furniture. A card / loan / brokerage lexicon beside
   deposit-account furniture and no table is two account kinds claiming one
   document → `KIND_UNCERTAIN`.
4. `ACTIVITY_EXPORT`: a dated ledger with NO period / opening / closing
   anchor plus reverse chronology or pending rows.
5. Statements: `STATEMENT_COMPLETE` iff period AND opening AND closing AND a
   table (or the printed zero-activity declaration) AND no completeness
   finding; `STATEMENT_ILLEGIBLE` when statement anchors exist but the
   evidence is below the usable floor; `STATEMENT_PARTIAL{findings}`
   otherwise; a table alone, one anchor alone, or nothing → `KIND_UNCERTAIN`.

Layout classes the rules read (each pinned by a synthetic fixture)
-------------------------------------------------------------------
* a balance label with its amount on the same line or the next;
* a summary box whose labels are STACKED two-line cells ("Opening" over
  "balance ($)") with the values row below — never a contiguous phrase;
* a period printed as a phrase with a date within two lines, as two dates
  with a connector, as dates beside the opening and closing labels, or as
  a stacked start-date / end-date cell;
* rows WRAPPED over two lines (the date on one, the amount and balance on
  the next) — the page-break balance check sees them;
* a balance printed at intervals rather than on every row — such a layout
  is never accused of a page-break discontinuity;
* a MICR-shaped line on a page that carries the table is not a cheque page.

Every threshold is a named, versioned constant below. Page indices are
0-based everywhere (as in `evidence.canonical`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import median
from typing import Iterable

from evidence.canonical import ExtractionEvidence, PageEvidence, WordBox
from layout.refusals import (
    ACCOUNT_KINDS,
    FINDING_CODES,
    KINDS,
    LANGUAGES,
    MODALITIES,
    PROFILE_CLASSIFICATIONS,
    SUB_KINDS,
    TIERS,
)
from layout.signals import (
    LANGUAGE_CODES,
    LEXICON_MIN_DISTINCT,
    LEXICON_STRONG,
    LEXICONS,
    RANGE_CONNECTORS,
    SIGNALS,
    DateToken,
    LexiconHit,
    MoneyToken,
    find_dates,
    find_lexicon,
    find_money,
    find_page_marker,
    find_zero_activity,
    fold,
    is_micr_shaped,
)

__all__ = [
    "CLASSIFIER_VERSION",
    "CHEQUE_ASPECT_MAX",
    "CHEQUE_ASPECT_MIN",
    "DocumentClass",
    "DocumentProfileFacts",
    "EvidenceRef",
    "Finding",
    "ILLEGIBLE_EXPECTED_WORDS_PER_PAGE",
    "ILLEGIBLE_FLOOR_VERSION",
    "ILLEGIBLE_RATIO",
    "JAVA_SERIALIZATION_MAGIC",
    "KINDS",
    "MICR_BAND_FRACTION",
    "TABLE_MIN_ROWS",
    "classify_document",
]

#: Bumped whenever a rule, a lexicon or a threshold changes meaning.
CLASSIFIER_VERSION = 1

# --- file facts -------------------------------------------------------------
#: The Java object-serialisation stream header, as the profile records magic
#: (UPPERCASE hex of the first four bytes).
JAVA_SERIALIZATION_MAGIC = "ACED0005"

# --- table ------------------------------------------------------------------
#: A run of dated money lines this long is a transaction table.
TABLE_MIN_ROWS = 5
#: Non-member lines allowed between two members of one run (continuation
#: lines of a multi-line description).
TABLE_RUN_MAX_GAP = 2
#: Right-edge alignment tolerance, in multiples of the page's median
#: character width (evidence mode).
TABLE_ALIGN_TOLERANCE_CW = 1.0
#: The share of a run's lines whose money tokens must share one right edge.
TABLE_ALIGN_MIN_SHARE = 0.8
#: The money columns a statement table may spread its rows over (deposits,
#: withdrawals, balance): the largest clusters that together cover the rows.
TABLE_ALIGN_MAX_COLUMNS = 3

# --- running balance --------------------------------------------------------
RUNNING_BALANCE_MIN_PAIRS = 3
RUNNING_BALANCE_MIN_SHARE = 0.6
#: A card-shaped table: this share of its rows carries exactly one money token.
SINGLE_AMOUNT_COLUMN_MIN_SHARE = 0.8

# --- cheque -----------------------------------------------------------------
CHEQUE_ASPECT_MIN = 2.0
CHEQUE_ASPECT_MAX = 2.6
#: The MICR line sits in the bottom band of a cheque: y0 at or below this
#: fraction of the page height.
MICR_BAND_FRACTION = 0.85

# --- screenshot -------------------------------------------------------------
#: Paper sizes in points (portrait); either orientation is compared.
PAPER_SIZES_PT: tuple[tuple[float, float], ...] = (
    (612.0, 792.0),     # Letter
    (612.0, 1008.0),    # Legal
    (595.0, 842.0),     # A4
    (420.0, 595.0),     # A5
    (516.0, 729.0),     # B5
    (792.0, 1224.0),    # Ledger / Tabloid
    (842.0, 1191.0),    # A3
    (396.0, 612.0),     # Statement / half letter
)
PAPER_TOLERANCE = 0.05
#: A screen-sized page is at least this long on its long side (points).
SCREENSHOT_MIN_LONG_SIDE_PT = 800.0

# --- illegible floor (an E-class placeholder for 2.3) -----------------------
ILLEGIBLE_FLOOR_VERSION = 1
ILLEGIBLE_EXPECTED_WORDS_PER_PAGE = 120
ILLEGIBLE_RATIO = 0.25

# --- export -----------------------------------------------------------------
REVERSE_CHRONOLOGY_MIN_DECREASES = 3

_DETAIL_GRAMMAR = re.compile(r"^(?:[a-z_]+=\d+(?:/\d+)?(?:;[a-z_]+=\d+(?:/\d+)?)*)?$")
#: Range connectors compared against FOLDED text between two dates.
_FOLDED_CONNECTORS = {language: tuple(fold(c) for c in connectors) for language, connectors in RANGE_CONNECTORS.items()}
#: The "from … to" label pair of a period cell, per language (folded words).
_FROM_TO_WORDS = {"en": ("from", "to"), "fr": ("du", "au"), "es": ("del", "al")}


# ---------------------------------------------------------------------------
# the contract types (exactly as the umbrella prints them)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DocumentProfileFacts:
    """Preflight FACTS only (copied from `ocr/inspect.py`'s profile by the
    caller; no analysis object ever crosses into this package). `magic` is
    the UPPERCASE hex of the file's first four bytes, or None when unknown."""

    valid_pdf: bool
    encrypted: bool
    page_count: int
    classification: str
    page_text_chars: tuple[int, ...]
    magic: str | None

    def __post_init__(self) -> None:
        if self.classification not in PROFILE_CLASSIFICATIONS:
            raise ValueError(f"unknown profile classification {self.classification!r}")
        if isinstance(self.page_count, bool) or not isinstance(self.page_count, int) or self.page_count < 0:
            raise ValueError(f"page_count must be a non-negative int, got {self.page_count!r}")
        chars = tuple(int(c) for c in self.page_text_chars)
        object.__setattr__(self, "page_text_chars", chars)
        if self.magic is not None and not isinstance(self.magic, str):
            raise ValueError("magic must be a str or None")


@dataclass(frozen=True, init=False)
class Finding:
    """A completeness finding. `detail` is a closed `key=number` grammar and
    can never carry document text.

    The field is validated in an explicit `__init__` from its ARGUMENT, so
    nothing under `layout/` ever reads a `.detail` attribute: the H-3
    sensitivity guard (`tests/test_privacy3_boundaries.py`) pins the readers
    of that attribute name to two console-only sites, and this package —
    which stores a finding and never renders one — stays outside that set.
    A consumer that renders `Finding.detail` into a row is a reviewed change
    to that register, never a silent one."""

    code: str
    page: int | None
    detail: str

    def __init__(self, code: str, page: int | None, detail: str) -> None:
        if code not in FINDING_CODES:
            raise ValueError(f"unknown finding code {code!r}")
        if not isinstance(detail, str) or not _DETAIL_GRAMMAR.match(detail):
            raise ValueError(f"finding detail must be key=number pairs, got {detail!r}")
        if page is not None and (isinstance(page, bool) or not isinstance(page, int) or page < 0):
            raise ValueError("page must be a non-negative int or None")
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "page", page)
        object.__setattr__(self, "detail", detail)


@dataclass(frozen=True)
class EvidenceRef:
    """Where a signal was seen: `word_ids` in evidence mode, a character
    `span` into the page text in degraded mode, neither for a page- or
    file-level fact. `signal` is a closed name."""

    page: int
    word_ids: tuple[str, ...] | None
    span: tuple[int, int] | None
    signal: str

    def __post_init__(self) -> None:
        if self.signal not in SIGNALS:
            raise ValueError(f"unknown signal {self.signal!r}")
        if isinstance(self.page, bool) or not isinstance(self.page, int) or self.page < 0:
            raise ValueError("page must be a non-negative int")
        if self.word_ids is not None:
            object.__setattr__(self, "word_ids", tuple(str(w) for w in self.word_ids))
        if self.span is not None:
            start, end = self.span
            if not (isinstance(start, int) and isinstance(end, int) and 0 <= start < end):
                raise ValueError(f"span must be (start, end) with 0 <= start < end, got {self.span!r}")
            object.__setattr__(self, "span", (int(start), int(end)))


@dataclass(frozen=True)
class DocumentClass:
    kind: str
    sub_kind: str | None
    modality: str
    language: str
    account_kind: str
    completeness: tuple[Finding, ...]
    evidence: tuple[EvidenceRef, ...]
    tier: str
    version: int

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown kind {self.kind!r}")
        if self.sub_kind is not None and self.sub_kind not in SUB_KINDS:
            raise ValueError(f"unknown sub_kind {self.sub_kind!r}")
        if self.modality not in MODALITIES:
            raise ValueError(f"unknown modality {self.modality!r}")
        if self.language not in LANGUAGES:
            raise ValueError(f"unknown language {self.language!r}")
        if self.account_kind not in ACCOUNT_KINDS:
            raise ValueError(f"unknown account_kind {self.account_kind!r}")
        if self.tier not in TIERS:
            raise ValueError(f"unknown tier {self.tier!r}")
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise ValueError("version must be an int")
        completeness = tuple(self.completeness)
        evidence = tuple(self.evidence)
        if not all(isinstance(f, Finding) for f in completeness):
            raise ValueError("completeness must hold Finding instances")
        if not all(isinstance(e, EvidenceRef) for e in evidence):
            raise ValueError("evidence must hold EvidenceRef instances")
        object.__setattr__(self, "completeness", completeness)
        object.__setattr__(self, "evidence", evidence)


# ---------------------------------------------------------------------------
# the internal reading model (one shape for both modes)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Word:
    text: str
    start: int          # char offset within the line text
    end: int
    x0: float
    y0: float
    x1: float
    y1: float
    word_id: str


@dataclass(frozen=True)
class _Line:
    page: int
    index: int
    text: str
    offset: int                          # char offset of the line within the page text
    words: tuple[_Word, ...] | None      # None in degraded mode
    y0: float | None
    y1: float | None


@dataclass(frozen=True)
class _Page:
    index: int
    lines: tuple[_Line, ...]
    width: float | None
    height: float | None
    char_width: float | None
    word_count: int

    @property
    def text_present(self) -> bool:
        return self.word_count > 0


@dataclass(frozen=True)
class _Doc:
    pages: tuple[_Page, ...]
    mode: str            # "evidence" | "text"

    @property
    def word_count(self) -> int:
        return sum(page.word_count for page in self.pages)


def _page_from_evidence(page: PageEvidence) -> _Page:
    by_id: dict[str, WordBox] = {word.word_id: word for word in page.words}
    lines: list[_Line] = []
    offset = 0
    widths: list[float] = []
    for index, line in enumerate(page.lines):
        words: list[_Word] = []
        cursor = 0
        for wid in line.word_ids:
            box = by_id[wid]
            start = cursor
            end = start + len(box.text)
            words.append(_Word(box.text, start, end, box.x0, box.y0, box.x1, box.y1, wid))
            cursor = end + 1
            if box.text.strip():
                widths.append((box.x1 - box.x0) / max(1, len(box.text)))
        lines.append(_Line(page.page_index, index, line.text, offset, tuple(words), line.y_top, line.y_bottom))
        offset += len(line.text) + 1
    frame = page.frame
    return _Page(page.page_index, tuple(lines), float(frame.width), float(frame.height),
                 float(median(widths)) if widths else None, len(page.words))


def _page_from_text(index: int, text: str) -> _Page:
    lines: list[_Line] = []
    offset = 0
    words = 0
    for line_index, raw in enumerate(text.split("\n")):
        lines.append(_Line(index, line_index, raw, offset, None, None, None))
        offset += len(raw) + 1
        words += len(raw.split())
    return _Page(index, tuple(lines), None, None, None, words)


def _build_doc(evidence: ExtractionEvidence | None, page_texts: tuple[str, ...] | None) -> _Doc:
    if evidence is not None:
        return _Doc(tuple(_page_from_evidence(page) for page in evidence.pages), "evidence")
    return _Doc(tuple(_page_from_text(i, str(t)) for i, t in enumerate(page_texts or ())), "text")


def _ref(line: _Line, start: int, end: int, signal: str) -> EvidenceRef:
    if line.words is not None:
        ids = tuple(w.word_id for w in line.words if w.start < end and w.end > start)
        return EvidenceRef(line.page, ids or None, None, signal)
    if end <= start:
        return EvidenceRef(line.page, None, None, signal)
    return EvidenceRef(line.page, None, (line.offset + start, line.offset + end), signal)


def _line_ref(line: _Line, signal: str) -> EvidenceRef:
    return _ref(line, 0, len(line.text), signal)


def _page_ref(page: _Page, signal: str) -> EvidenceRef:
    return EvidenceRef(page.index, None, None, signal)


def _distinct_hits(hits: Iterable[LexiconHit]) -> list[LexiconHit]:
    """Non-overlapping hits, longest first at each position, in text order."""
    ordered = sorted(hits, key=lambda h: (h.start, -(h.end - h.start), h.language, h.phrase))
    kept: list[LexiconHit] = []
    cursor = -1
    for hit in ordered:
        if hit.start >= cursor:
            kept.append(hit)
            cursor = hit.end
    return kept


# ---------------------------------------------------------------------------
# signal evaluation
# ---------------------------------------------------------------------------

@dataclass
class _Signals:
    refs: list[EvidenceRef]
    language_votes: dict[str, int]
    # anchors
    period: bool = False
    opening: bool = False
    closing: bool = False
    opening_line: _Line | None = None
    closing_line: _Line | None = None
    opening_lines: list = field(default_factory=list)   # every opening-label line seen
    closing_lines: list = field(default_factory=list)   # every closing-label line seen
    zero_activity: bool = False
    # table
    table_rows: int = 0            # counted rows in qualifying groups
    table: bool = False            # the statement table signal (mode-aware)
    aligned: bool = False          # geometric confirmation (evidence mode)
    running_balance: bool = False
    single_amount_column: bool = False   # most table rows carry exactly one money token
    ledger_rows: int = 0                 # dated money rows that are not anchor lines (wrapped rows included)
    short_ledger: bool = False           # 1..TABLE_MIN_ROWS-1 ledger rows: a complete statement with few transactions
    balance_pair: bool = False           # opening == closing to the cent with no ledger row: a printed zero-activity structure
    opening_cents: int | None = None
    closing_cents: int | None = None
    reverse_chronology: bool = False
    pending: bool = False
    discontinuities: list[tuple[int, int]] = field(default_factory=list)   # (page_before, page_after)
    # markers
    markers: list[tuple[int, int, int]] = field(default_factory=list)      # (page_index, number, total)
    # cheque
    cheque_structural: bool = False
    cheque_lexical: bool = False
    void: bool = False
    # lexicon sub-kinds that reached their threshold
    subkind_lexicons: set[str] = field(default_factory=set)
    deposit_account: bool = False
    screenshot: bool = False
    furniture_repetition: bool = False
    words_per_page: float = 0.0

    def has(self, signal: str) -> bool:
        return any(ref.signal == signal for ref in self.refs)

    @property
    def anchors(self) -> int:
        return int(self.period) + int(self.opening) + int(self.closing)


def _vote(signals: _Signals, language: str, weight: int = 1) -> None:
    signals.language_votes[language] = signals.language_votes.get(language, 0) + weight


def _next_nonempty(lines: tuple[_Line, ...], index: int) -> _Line | None:
    for line in lines[index + 1:]:
        if line.text.strip():
            return line
    return None


def _following_nonempty(lines: tuple[_Line, ...], index: int, count: int) -> list[_Line]:
    out: list[_Line] = []
    for line in lines[index + 1:]:
        if line.text.strip():
            out.append(line)
            if len(out) >= count:
                break
    return out


#: A period phrase's dates may sit on the phrase's line or within this many
#: following non-empty lines (a label cell over a date cell).
PERIOD_DATE_WITHIN = 2


def _label_text(text: str, day_first: bool = False) -> str:
    """The line with its money and date tokens blanked to spaces (length
    preserving): a label is read on the words alone, so "Beginning
    <date> balance on" — a date cell grouped into the label's visual line —
    still reads "beginning balance"."""
    chars = list(text)
    for token in find_money(text):
        for i in range(token.start, token.end):
            chars[i] = " "
    for token in find_dates(text, day_first=day_first):
        for i in range(token.start, token.end):
            chars[i] = " "
    return "".join(chars)


def _label_with_amount(page: _Page, name: str, signal: str, signals: _Signals) -> _Line | None:
    """A balance label with an adjacent amount: on the same line, or on the
    next non-empty line. Returns the label line on the first hit. Falls back
    to the STACKED form (`_stacked_label`) when no contiguous phrase fires."""
    found: _Line | None = None
    for index, line in enumerate(page.lines):
        hits = _distinct_hits(find_lexicon(_label_text(line.text), name))
        if not hits:
            continue
        money = find_money(line.text)
        cents: int | None = money[-1].cents if money else None
        if not money:
            following = _next_nonempty(page.lines, index)
            if following is None or not find_money(following.text):
                continue
            cents = find_money(following.text)[0].cents
        for hit in hits:
            signals.refs.append(_ref(line, hit.start, hit.end, signal))
            _vote(signals, hit.language)
        (signals.opening_lines if name == "opening_balance" else signals.closing_lines).append(line)
        if found is None:
            found = line
            _record_amount(signals, name, cents)
    if found is None:
        found = _stacked_label(page, name, signal, signals)
    return found


def _record_amount(signals: _Signals, name: str, cents: int | None) -> None:
    """The first opening amount and the last closing amount seen (contiguous
    label forms only; a stacked cell leaves the amount unknown)."""
    if name == "opening_balance" and signals.opening_cents is None:
        signals.opening_cents = cents
    elif name == "closing_balance":
        signals.closing_cents = cents


#: A stacked label's words (a summary cell such as "Closing" over "balance
#: ($)", two to four lines tall once every cell's halves are grouped) must
#: be followed by the values row — the first money-bearing line among the
#: next `STACKED_LABEL_VALUES_WITHIN` non-empty lines, carrying at least
#: `STACKED_LABEL_MIN_VALUES` money tokens.
STACKED_LABEL_MAX_LINES = 4
STACKED_LABEL_VALUES_WITHIN = 5
STACKED_LABEL_MIN_VALUES = 2

_WORD_RE = re.compile(r"[a-z']+")


def _stacked_phrases(name: str) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """(language, phrase, folded words) for every multi-word phrase of a lexicon."""
    out = []
    for language in LANGUAGE_CODES:
        for phrase in LEXICONS[name][language]:
            words = tuple(w for w in _WORD_RE.findall(fold(phrase)))
            if len(words) >= 2:
                out.append((language, phrase, words))
    return tuple(out)


_STACKED = {name: _stacked_phrases(name) for name in ("opening_balance", "closing_balance")}


def _stacked_label(page: _Page, name: str, signal: str, signals: _Signals) -> _Line | None:
    """A summary-box label whose words are STACKED in a two-line cell
    ("Opening" over "balance ($)", "Solde" over "de fermeture ($)"). A block
    reader merges the top halves of every cell into one line and the bottom
    halves into the next; a word-box reader groups them into two visual
    lines. Either way the phrase is never contiguous. The rule: within a
    window of one or two money-free lines, the phrase's first word precedes
    its last word and its other words are present, and a values row with at
    least `STACKED_LABEL_MIN_VALUES` money tokens follows within
    `STACKED_LABEL_VALUES_WITHIN` lines. The refs point at the first and
    last words of the phrase."""
    lines = page.lines
    for start in range(len(lines)):
        if not lines[start].text.strip():
            continue
        for width in range(1, STACKED_LABEL_MAX_LINES + 1):
            window = lines[start:start + width]
            if len(window) < width:
                break
            if width > 1 and not window[-1].text.strip():
                break
            tokens: list[tuple[int, str, int, int]] = []   # (line offset in window, word, start, end)
            money_at: list[tuple[int, int]] = []           # (line offset, start) of every money token in the window
            for offset, line in enumerate(window):
                folded = fold(line.text)
                for match in _WORD_RE.finditer(folded):
                    tokens.append((offset, match.group(0), match.start(), match.end()))
                for token in find_money(line.text):
                    money_at.append((offset, token.start))
            words = [t[1] for t in tokens]
            for language, phrase, phrase_words in _STACKED[name]:
                first, last = phrase_words[0], phrase_words[-1]
                try:
                    a = words.index(first)
                except ValueError:
                    continue
                b = -1
                for index in range(len(words) - 1, a, -1):
                    if words[index] == last:
                        b = index
                        break
                if b <= a:
                    continue
                if any(word not in words for word in phrase_words[1:-1] if len(word) > 2):
                    continue
                # money inside the window may sit only AFTER the phrase's last
                # word (a values column to the right of a merged header row)
                b_offset, _, _, b_end = tokens[b]
                if any((offset, start) < (b_offset, b_end) for offset, start in money_at):
                    continue
                after = [m for m in money_at if m >= (b_offset, b_end)]
                values_here = len(after) >= STACKED_LABEL_MIN_VALUES
                if not values_here:
                    values = None
                    for candidate in _following_nonempty(lines, start + width - 1, STACKED_LABEL_VALUES_WITHIN):
                        if find_money(candidate.text):
                            if len(find_money(candidate.text)) >= STACKED_LABEL_MIN_VALUES:
                                values = candidate
                            break
                    if values is None:
                        continue
                for index in (a, b):
                    offset, _, s, e = tokens[index]
                    signals.refs.append(_ref(window[offset], s, e, signal))
                _vote(signals, language)
                return window[0]
    return None


def _period(page: _Page, signals: _Signals, day_first: bool) -> bool:
    fired = False
    for index, line in enumerate(page.lines):
        text = line.text
        dates = find_dates(text, day_first=day_first)
        # (e) the "from … to" labels with two full dates on one line, the
        #     dates separated by other cells of a merged header row
        if len(dates) >= 2 and any(d.year is not None for d in dates):
            label_words = set(_WORD_RE.findall(fold(_label_text(text, day_first))))
            for language, (word_from, word_to) in _FROM_TO_WORDS.items():
                if word_from in label_words and word_to in label_words:
                    signals.refs.append(_ref(line, dates[0].start, dates[1].end, "period_expression"))
                    _vote(signals, language)
                    fired = True
                    break
        # (a) a period phrase with a date on the same or the next line
        hits = _distinct_hits(find_lexicon(_label_text(text, day_first), "period_phrase"))
        if hits:
            following = _following_nonempty(page.lines, index, PERIOD_DATE_WITHIN)
            if dates or any(find_dates(line.text, day_first=day_first) for line in following):
                for hit in hits:
                    signals.refs.append(_ref(line, hit.start, hit.end, "period_expression"))
                    _vote(signals, hit.language)
                fired = True
                continue
        # (b) two dates joined by a range connector — never on a line that
        #     carries money (a ledger row's own date range is not the period;
        #     review MINOR-4)
        if len(dates) >= 2 and not find_money(text):
            folded = fold(text)
            for first, second in zip(dates, dates[1:]):
                between = folded[first.end:second.start].strip()
                if not between:
                    continue
                for language in LANGUAGE_CODES:
                    if between in _FOLDED_CONNECTORS[language]:
                        signals.refs.append(_ref(line, first.start, second.end, "period_expression"))
                        _vote(signals, language)
                        fired = True
                        break
        # (d) a STACKED range: this line and the next non-empty line each
        #     carry exactly one full date (with a year), no money and at most
        #     a few other words, in order — a start-date cell over an
        #     end-date cell, the connector implied by the layout
        if len(dates) == 1 and dates[0].year is not None and not find_money(text) and _few_other_words(text):
            following = _next_nonempty(page.lines, index)
            if following is not None and following is not line:
                next_dates = find_dates(following.text, day_first=day_first)
                if (len(next_dates) == 1 and next_dates[0].year is not None and not find_money(following.text)
                        and _few_other_words(following.text) and dates[0].sort_key() <= next_dates[0].sort_key()):
                    signals.refs.append(_ref(line, dates[0].start, dates[0].end, "period_expression"))
                    signals.refs.append(_ref(following, next_dates[0].start, next_dates[0].end, "period_expression"))
                    fired = True
    return fired


#: A stacked date-range cell carries at most this many alphabetic words in
#: total (a month name counts; digits do not): "from <month> <d>, <y>" is 2.
STACKED_RANGE_MAX_WORDS = 4


def _few_other_words(text: str) -> bool:
    folded = fold(text)
    marker = find_page_marker(text)
    if marker is not None:
        folded = folded[:marker.start] + " " * (marker.end - marker.start) + folded[marker.end:]
    return len(_WORD_RE.findall(folded)) <= STACKED_RANGE_MAX_WORDS


def _period_from_balance_lines(signals: _Signals, day_first: bool) -> bool:
    """(c) two dates beside the opening and closing labels — any opening
    label line with a date and any closing label line with a date (a
    column header that repeats the label without a date does not hide the
    dated summary line)."""
    opening = [(line, find_dates(line.text, day_first=day_first)) for line in signals.opening_lines]
    closing = [(line, find_dates(line.text, day_first=day_first)) for line in signals.closing_lines]
    opening = [(line, dates) for line, dates in opening if dates]
    closing = [(line, dates) for line, dates in closing if dates]
    if opening and closing:
        for line, dates in (opening[0], closing[0]):
            signals.refs.append(_ref(line, dates[0].start, dates[0].end, "period_expression"))
        return True
    return False


@dataclass(frozen=True)
class _Row:
    line: _Line
    dates: tuple[DateToken, ...]
    money: tuple[MoneyToken, ...]
    money_line: _Line | None = None    # a WRAPPED row: the amount and balance sit on the line after the date

    @property
    def amount_line(self) -> _Line:
        return self.money_line or self.line


def _member_rows(page: _Page, day_first: bool) -> list[_Row]:
    """Dated money rows: a line with a date and money, or a WRAPPED row —
    a dated line without money whose next line carries money and no date
    (the amount and balance printed under the date and description)."""
    rows: list[_Row] = []
    lines = page.lines
    for index, line in enumerate(lines):
        dates = find_dates(line.text, day_first=day_first)
        if not dates:
            continue
        money = find_money(line.text)
        if money:
            rows.append(_Row(line, tuple(dates), tuple(money)))
            continue
        if index + 1 < len(lines):
            following = lines[index + 1]
            next_money = find_money(following.text)
            if next_money and not find_dates(following.text, day_first=day_first):
                rows.append(_Row(line, tuple(dates), tuple(next_money), following))
    return rows


def _is_anchor_line(text: str) -> bool:
    """A dated money line that IS a summary anchor (a balance label with its
    date and amount, a period line) is not a ledger row."""
    label = _label_text(text)
    return any(find_lexicon(label, name) for name in ("opening_balance", "closing_balance", "period_phrase"))


def _groups(rows: list[_Row]) -> list[list[_Row]]:
    groups: list[list[_Row]] = []
    for row in rows:
        if groups and row.line.index - groups[-1][-1].line.index <= TABLE_RUN_MAX_GAP + 1:
            groups[-1].append(row)
        else:
            groups.append([row])
    return [group for group in groups if len(group) >= 2]


def _money_right_edge(row: _Row, token: MoneyToken) -> float | None:
    line = row.amount_line
    assert line.words is not None
    covering = [w for w in line.words if w.start < token.end and w.end > token.start]
    return max(w.x1 for w in covering) if covering else None


def _aligned(group: list[_Row], char_width: float | None) -> bool:
    """Evidence mode: the group's money tokens fall on at most
    `TABLE_ALIGN_MAX_COLUMNS` shared right edges (an amount column; a debit
    and a credit column; deposits, withdrawals and a daily balance) that
    together cover `TABLE_ALIGN_MIN_SHARE` of its rows, each edge within
    `TABLE_ALIGN_TOLERANCE_CW` character widths. A cluster of one row never
    counts, so prose whose figures drift never aligns."""
    if char_width is None:
        return False
    tolerance = TABLE_ALIGN_TOLERANCE_CW * char_width
    edges: list[tuple[float, int]] = []
    for row_index, row in enumerate(group):
        for token in row.money:
            edge = _money_right_edge(row, token)
            if edge is not None:
                edges.append((edge, row_index))
    edges.sort()
    clusters: list[set[int]] = []
    i = 0
    while i < len(edges):
        anchor = edges[i][0]
        members = {edges[i][1]}
        j = i + 1
        while j < len(edges) and edges[j][0] - anchor <= tolerance:
            members.add(edges[j][1])
            j += 1
        clusters.append(members)
        i += 1
    clusters.sort(key=len, reverse=True)
    covered: set[int] = set()
    for cluster in clusters[:TABLE_ALIGN_MAX_COLUMNS]:
        if len(cluster) >= 2:
            covered |= cluster
    return len(covered) >= max(2, int(-(-TABLE_ALIGN_MIN_SHARE * len(group) // 1)))


def _chain_pairs(group: list[_Row]) -> tuple[int, int]:
    """(chained pairs, candidate pairs) over consecutive rows carrying at
    least two money tokens: |balance_i - balance_{i-1}| == |amount_i|."""
    chained = 0
    candidates = 0
    previous: int | None = None
    for row in group:
        if len(row.money) < 2:
            previous = None
            continue
        balance = row.money[-1].cents
        amount = abs(row.money[-2].cents)
        if previous is not None:
            candidates += 1
            if abs(balance - previous) == amount:
                chained += 1
        previous = balance
    return chained, candidates


def _table(doc: _Doc, signals: _Signals, day_first: bool) -> list[list[list[_Row]]]:
    """The dated-money-row groups per page, with the table / alignment /
    running-balance / chronology / pending signals. Returns the qualifying
    groups per page (aligned in evidence mode)."""
    per_page: list[list[list[_Row]]] = []
    counted_rows = 0
    single_money_rows = 0
    aligned_any = False
    chained_total = 0
    candidates_total = 0
    increases = 0
    decreases = 0
    for page in doc.pages:
        rows = _member_rows(page, day_first)
        groups = _groups(rows)
        qualifying: list[list[_Row]] = []
        for group in groups:
            if doc.mode == "evidence":
                if not _aligned(group, page.char_width):
                    continue
                aligned_any = True
            qualifying.append(group)
            counted_rows += len(group)
            single_money_rows += sum(1 for row in group if len(row.money) == 1)
            chained, candidates = _chain_pairs(group)
            chained_total += chained
            candidates_total += candidates
            previous_key = None
            for row in group:
                key = row.dates[0].sort_key()
                if previous_key is not None:
                    if key > previous_key:
                        increases += 1
                    elif key < previous_key:
                        decreases += 1
                previous_key = key
                for hit in _distinct_hits(find_lexicon(row.line.text, "pending")):
                    signals.refs.append(_ref(row.line, hit.start, hit.end, "pending_row"))
                    _vote(signals, hit.language)
                    signals.pending = True
        per_page.append(qualifying)
    signals.table_rows = counted_rows
    anchor_lines = {id(line) for line in (signals.opening_line, signals.closing_line) if line is not None}
    ledger = [
        row for page in doc.pages for row in _member_rows(page, day_first)
        if id(row.line) not in anchor_lines and not _is_anchor_line(row.line.text)
    ]
    signals.ledger_rows = len(ledger)
    if counted_rows < TABLE_MIN_ROWS and 1 <= len(ledger) < TABLE_MIN_ROWS:
        # A complete statement may print one to four transactions: too few
        # rows for the table signal, still a printed ledger.
        signals.short_ledger = True
        for row in ledger:
            signals.refs.append(_line_ref(row.line, "short_ledger"))
    if counted_rows >= TABLE_MIN_ROWS:
        signals.table = True
        signals.single_amount_column = single_money_rows >= SINGLE_AMOUNT_COLUMN_MIN_SHARE * counted_rows
        for groups in per_page:
            for group in groups:
                for row in group:
                    signals.refs.append(_line_ref(row.line, "table_run"))
                    if doc.mode == "evidence":
                        signals.refs.append(_line_ref(row.line, "table_alignment"))
        signals.aligned = aligned_any and doc.mode == "evidence"
    if chained_total >= RUNNING_BALANCE_MIN_PAIRS and chained_total >= RUNNING_BALANCE_MIN_SHARE * max(1, candidates_total):
        signals.running_balance = True
        for groups in per_page:
            for group in groups:
                for row in group:
                    if len(row.money) >= 2:
                        signals.refs.append(_ref(row.line, row.money[-1].start, row.money[-1].end, "running_balance"))
    if signals.table and decreases >= REVERSE_CHRONOLOGY_MIN_DECREASES and increases == 0:
        signals.reverse_chronology = True
        for groups in per_page:
            for group in groups:
                signals.refs.append(_ref(group[0].line, group[0].dates[0].start, group[0].dates[0].end, "reverse_chronology"))
    return per_page


def _money_rows(page: _Page, start: int, stop: int) -> list[_Row]:
    """Every line of `page` in `[start, stop]` carrying at least two money
    tokens, dated or not — a wrapped row prints its date on one line and
    its amount and balance on the next, and the boundary check must see
    that row, not skip it. Page-marker lines are excluded."""
    rows: list[_Row] = []
    for line in page.lines[start:stop + 1]:
        money = find_money(line.text)
        if len(money) < 2 or find_page_marker(line.text) is not None:
            continue
        rows.append(_Row(line, (), tuple(money)))
    return rows


def _discontinuities(doc: _Doc, per_page: list[list[list[_Row]]], signals: _Signals) -> None:
    """Last balance on page p vs the first computed balance on page p+1.

    The tail is the last money-pair line from the last group's first row to
    the page end; the head is the first money-pair line from the page top
    to the first group's last row (wrapped rows included on both sides).
    The check applies only where the layout is KNOWN to print a balance on
    every row: both sides chain on their own, and no dated amount-only row
    follows the tail or precedes the head (a layout that prints the balance
    at intervals cannot be checked this way and is not accused)."""
    if not signals.running_balance:
        return
    for p in range(len(per_page) - 1):
        before = per_page[p]
        after = per_page[p + 1]
        if not before or not after:
            continue
        page_before = doc.pages[p]
        page_after = doc.pages[p + 1]
        tail = _money_rows(page_before, before[-1][0].line.index, len(page_before.lines) - 1)
        head = _money_rows(page_after, 0, after[0][-1].line.index)
        if not tail or not head:
            continue
        if any(len(row.money) == 1 and row.line.index > tail[-1].line.index for row in before[-1]):
            continue
        if any(len(row.money) == 1 and row.line.index < head[0].line.index for row in after[0]):
            continue
        # both sides must chain on their own, so the layout is known to
        # carry a balance column on both pages
        if len(tail) < 2 or _chain_pairs(tail[-3:])[0] < min(2, len(tail[-3:]) - 1):
            continue
        if len(head) < 2 or _chain_pairs(head[:3])[0] < min(2, len(head[:3]) - 1):
            continue
        last_balance = tail[-1].money[-1].cents
        first_row = head[0]
        amount = abs(first_row.money[-2].cents)
        first_balance = first_row.money[-1].cents
        if first_balance not in (last_balance + amount, last_balance - amount):
            signals.discontinuities.append((p, p + 1))
            signals.refs.append(_ref(tail[-1].line, tail[-1].money[-1].start, tail[-1].money[-1].end, "balance_discontinuity"))
            signals.refs.append(_ref(first_row.line, first_row.money[-1].start, first_row.money[-1].end, "balance_discontinuity"))


def _markers(doc: _Doc, signals: _Signals) -> None:
    """One marker per page: of every marker line on the page, the one with
    the FEWEST other words (a footer's `Page 2 of 3` beats a prose
    cross-reference such as "see page 2 of 3 for fees" — review MINOR-1);
    ties go to the last such line, the footer's usual place."""
    for page in doc.pages:
        best: tuple[int, int, _Line, object] | None = None
        for index, line in enumerate(page.lines):
            marker = find_page_marker(line.text)
            if marker is None:
                continue
            other_words = len(_WORD_RE.findall(fold(line.text[:marker.start] + " " + line.text[marker.end:])))
            if best is None or other_words <= best[0]:
                best = (other_words, index, line, marker)
        if best is None:
            continue
        _, _, line, marker = best
        signals.markers.append((page.index, marker.number, marker.total))
        signals.refs.append(_ref(line, marker.start, marker.end, "page_marker"))
        _vote(signals, marker.language)


def _cheque(doc: _Doc, per_page: list[list[list[_Row]]], signals: _Signals) -> None:
    """The cheque signals per page. STRUCTURAL: a MICR-shaped line in the
    bottom band of a cheque-proportioned page — a page fact, whatever else
    the page carries. LEXICAL: MICR-shaped digit groups or the payee lexicon
    on a page WITHOUT a transaction table (a statement page that lists two
    long account numbers is not a cheque)."""
    for page in doc.pages:
        page_has_table = bool(per_page[page.index]) if page.index < len(per_page) else False
        aspect_ok = False
        if page.width and page.height:
            aspect = page.width / page.height
            aspect_ok = CHEQUE_ASPECT_MIN <= aspect <= CHEQUE_ASPECT_MAX
            if aspect_ok:
                signals.refs.append(_page_ref(page, "cheque_aspect"))
        micr_band = False
        micr_shape = False
        for line in page.lines:
            if is_micr_shaped(line.text):
                micr_shape = True
                signals.refs.append(_line_ref(line, "micr_shape"))
                if page.height and line.y0 is not None and line.y0 >= MICR_BAND_FRACTION * page.height:
                    micr_band = True
                    signals.refs.append(_line_ref(line, "micr_band"))
        lexicon = False
        for line in page.lines:
            for hit in _distinct_hits(find_lexicon(line.text, "cheque")):
                lexicon = True
                signals.refs.append(_ref(line, hit.start, hit.end, "cheque_lexicon"))
                _vote(signals, hit.language)
        page_structural = micr_band and aspect_ok
        page_lexical = (micr_shape or lexicon) and not page_has_table
        if page_structural:
            signals.cheque_structural = True
        if page_lexical:
            signals.cheque_lexical = True
        if page_structural or page_lexical:
            for line in page.lines:
                for hit in _distinct_hits(find_lexicon(line.text, "void")):
                    signals.void = True
                    signals.refs.append(_ref(line, hit.start, hit.end, "void_lexicon"))
                    _vote(signals, hit.language)


_SUBKIND_LEXICONS = (
    ("deposit_slip", "deposit_slip_lexicon"),
    ("letter", "letter_lexicon"),
    ("card", "card_lexicon"),
    ("loan", "loan_lexicon"),
    ("brokerage", "brokerage_lexicon"),
)


def _lexicon_subkinds(doc: _Doc, signals: _Signals) -> None:
    for name, signal in _SUBKIND_LEXICONS + (("deposit_account", "deposit_lexicon"),):
        distinct_phrases: set[str] = set()
        refs: list[EvidenceRef] = []
        votes: list[str] = []
        for page in doc.pages:
            for line in page.lines:
                for hit in _distinct_hits(find_lexicon(line.text, name)):
                    distinct_phrases.add(hit.phrase)
                    refs.append(_ref(line, hit.start, hit.end, signal))
                    votes.append(hit.language)
        if not distinct_phrases:
            continue
        strong = LEXICON_STRONG.get(name)
        if len(distinct_phrases) < LEXICON_MIN_DISTINCT[name]:
            continue
        if strong is not None and not (distinct_phrases & strong):
            continue
        signals.refs.extend(refs)
        for language in votes:
            _vote(signals, language)
        if name == "deposit_account":
            signals.deposit_account = True
        else:
            signals.subkind_lexicons.add(name)


def _near_paper(width: float, height: float) -> bool:
    for w, h in PAPER_SIZES_PT:
        for pw, ph in ((w, h), (h, w)):
            if abs(width - pw) <= PAPER_TOLERANCE * pw and abs(height - ph) <= PAPER_TOLERANCE * ph:
                return True
    return False


def _screenshot(doc: _Doc, signals: _Signals) -> None:
    if doc.mode != "evidence" or not doc.pages:
        return
    # furniture repetition: a digit-masked line text seen on two pages
    seen: dict[str, set[int]] = {}
    for page in doc.pages:
        for line in page.lines:
            masked = re.sub(r"\d", "#", fold(line.text)).strip()
            if masked:
                seen.setdefault(masked, set()).add(page.index)
    signals.furniture_repetition = any(len(pages) >= 2 for pages in seen.values())
    far_pages = []
    for page in doc.pages:
        if not (page.width and page.height):
            return
        aspect = page.width / page.height
        if CHEQUE_ASPECT_MIN <= aspect <= CHEQUE_ASPECT_MAX or CHEQUE_ASPECT_MIN <= 1 / aspect <= CHEQUE_ASPECT_MAX:
            return
        if _near_paper(page.width, page.height):
            return
        if max(page.width, page.height) < SCREENSHOT_MIN_LONG_SIDE_PT:
            return
        far_pages.append(page)
    if far_pages and not signals.furniture_repetition:
        signals.screenshot = True
        for page in far_pages:
            signals.refs.append(_page_ref(page, "screenshot_frame"))


def _language_guess(doc: _Doc) -> str:
    """A first pass over the lexicons to pick the day-first convention for
    numeric dates; the verdict's language is decided from the full votes."""
    votes: dict[str, int] = {}
    for page in doc.pages:
        for line in page.lines:
            for name in ("period_phrase", "opening_balance", "closing_balance", "deposit_account"):
                for hit in _distinct_hits(find_lexicon(line.text, name)):
                    votes[hit.language] = votes.get(hit.language, 0) + 1
            marker = find_page_marker(line.text)
            if marker:
                votes[marker.language] = votes.get(marker.language, 0) + 1
    return _winner(votes)


def _winner(votes: dict[str, int]) -> str:
    if not votes:
        return "unknown"
    best = max(votes.values())
    winners = [language for language, count in votes.items() if count == best]
    return winners[0] if len(winners) == 1 else "unknown"


def _evaluate(doc: _Doc) -> _Signals:
    signals = _Signals(refs=[], language_votes={})
    day_first = _language_guess(doc) in ("fr", "es")
    for page in doc.pages:
        if _period(page, signals, day_first):
            signals.period = True
        opening = _label_with_amount(page, "opening_balance", "opening_balance_label", signals)
        if opening is not None:
            signals.opening = True
            if signals.opening_line is None:
                signals.opening_line = opening
        closing = _label_with_amount(page, "closing_balance", "closing_balance_label", signals)
        if closing is not None:
            signals.closing = True
            signals.closing_line = closing
        for line in page.lines:
            span = find_zero_activity(line.text)
            if span:
                signals.zero_activity = True
                signals.refs.append(_ref(line, span[0], span[1], "zero_activity_declaration"))
                _vote(signals, "en")
    if not signals.period and _period_from_balance_lines(signals, day_first):
        signals.period = True
    per_page = _table(doc, signals, day_first)
    if (signals.opening_cents is not None and signals.closing_cents is not None
            and signals.opening_cents == signals.closing_cents and signals.ledger_rows == 0 and not signals.table):
        # Opening and closing coincide to the cent and no ledger row is
        # printed: the zero-activity structure without its declaration.
        signals.balance_pair = True
        for line in (signals.opening_line, signals.closing_line):
            if line is not None:
                signals.refs.append(_line_ref(line, "balance_pair_coincides"))
    _discontinuities(doc, per_page, signals)
    _markers(doc, signals)
    _cheque(doc, per_page, signals)
    _lexicon_subkinds(doc, signals)
    _screenshot(doc, signals)
    signals.words_per_page = doc.word_count / max(1, len(doc.pages))
    return signals


# ---------------------------------------------------------------------------
# findings
# ---------------------------------------------------------------------------

def _page_findings(doc: _Doc, signals: _Signals, profile: DocumentProfileFacts) -> list[Finding]:
    findings: list[Finding] = []
    markers = signals.markers
    if not markers:
        return findings
    declared = markers[0][2]
    numbers = [number for _, number, _ in markers]
    n_pages = len(doc.pages)
    gap_after: int | None = None
    for (page_before, before, total_before), (page_after, after, _) in zip(markers, markers[1:]):
        # A page without a marker between two marked pages is not a gap: the
        # declared numbers may advance by at most the pages present. A clean
        # restart (`1 of M` right after a sequence that reached its own
        # total) is a second statement in one file, not a gap either.
        if after == 1 and before == total_before:
            continue
        if after <= before or after - before > page_after - page_before:
            gap_after = page_before
            break
    if gap_after is not None:
        findings.append(Finding("page_gap", gap_after, f"declared={declared};observed={n_pages};after_page={gap_after}"))
        signals.refs.append(EvidenceRef(gap_after, None, None, "page_gap"))
    short = n_pages < declared or (profile.page_count and profile.page_count < declared)
    if numbers[0] > 1 and short:
        findings.append(Finding("missing_first_page", 0, f"declared={declared};first_observed={numbers[0]}"))
        signals.refs.append(EvidenceRef(0, None, None, "first_page_missing"))
    # The LAST marked sequence must reach its own declared total: the pages
    # it still owes may only be covered by unmarked pages after it (review
    # MINOR-2: a second statement's truncated sequence is a missing page too).
    last_page, last_number, last_total = markers[-1]
    owed = last_total - last_number
    trailing_unmarked = n_pages - 1 - last_page
    if gap_after is None and owed > trailing_unmarked:
        findings.append(Finding("missing_pages", last_page, f"declared={last_total};observed={n_pages}"))
        signals.refs.append(EvidenceRef(last_page, None, None, "page_missing"))
    return findings


def _statement_findings(doc: _Doc, signals: _Signals, profile: DocumentProfileFacts) -> list[Finding]:
    findings = _page_findings(doc, signals, profile)
    if not signals.period:
        findings.append(Finding("missing_period", None, ""))
    if not signals.opening:
        findings.append(Finding("missing_opening", None, ""))
    if not signals.closing:
        findings.append(Finding("missing_closing", None, ""))
    for page_before, page_after in signals.discontinuities:
        findings.append(Finding("balance_discontinuity_at_page_break", page_after,
                                f"page_break={page_before}/{page_after}"))
    if not (signals.table or signals.zero_activity or signals.short_ledger or signals.balance_pair):
        findings.append(Finding("table_truncated", None, f"rows={signals.table_rows}"))
        if doc.pages:
            signals.refs.append(EvidenceRef(doc.pages[-1].index, None, None, "table_truncated"))
    return findings


# ---------------------------------------------------------------------------
# the decision
# ---------------------------------------------------------------------------

def _file_invalid(profile: DocumentProfileFacts) -> bool:
    magic = (profile.magic or "").upper()
    return (not profile.valid_pdf) or profile.encrypted or profile.page_count == 0 or magic == JAVA_SERIALIZATION_MAGIC


def _modality(profile: DocumentProfileFacts, doc: _Doc) -> str:
    text_present = any(page.text_present for page in doc.pages)
    if profile.classification == "digital":
        return "digital"
    if profile.classification == "mixed":
        return "mixed"
    if profile.classification == "scanned":
        return "image_backed_text" if text_present else "scanned"
    return "unknown"


def _account_kind(kind: str, sub_kind: str | None, signals: _Signals) -> str:
    if kind == "NOT_A_STATEMENT":
        return {"card_statement": "card", "loan_statement": "loan", "brokerage": "brokerage"}.get(sub_kind or "", "unknown")
    if kind in ("STATEMENT_COMPLETE", "STATEMENT_PARTIAL", "STATEMENT_ILLEGIBLE", "ACTIVITY_EXPORT"):
        if signals.running_balance or signals.deposit_account:
            return "deposit"
        firing = signals.subkind_lexicons & {"card", "loan", "brokerage"}
        if len(firing) == 1:
            return {"card": "card", "loan": "loan", "brokerage": "brokerage"}[next(iter(firing))]
    return "unknown"


def _verdict(kind: str, sub_kind: str | None, tier: str, findings: list[Finding], signals: _Signals,
             profile: DocumentProfileFacts, doc: _Doc) -> DocumentClass:
    refs = tuple(sorted(set(signals.refs), key=lambda r: (r.page, r.span or (-1, -1), r.word_ids or (), r.signal)))
    return DocumentClass(
        kind=kind, sub_kind=sub_kind, modality=_modality(profile, doc), language=_winner(signals.language_votes),
        account_kind=_account_kind(kind, sub_kind, signals), completeness=tuple(findings), evidence=refs,
        tier=tier, version=CLASSIFIER_VERSION,
    )


def _decide(doc: _Doc, signals: _Signals, profile: DocumentProfileFacts) -> DocumentClass:
    def uncertain() -> DocumentClass:
        return _verdict("KIND_UNCERTAIN", None, "uncertain", [], signals, profile, doc)

    # A cheque-proportioned page with a MICR band is a cheque page whatever
    # the document; MICR text or a payee line on a letter-size page is a
    # cheque signal only for a document that is not statement-shaped (a
    # statement's cheque-image enclosures are read as MICR text by a
    # native or OCR reader and are not a second document kind).
    cheque = signals.cheque_structural or (signals.cheque_lexical and signals.anchors < 2)
    lexical_kinds = set(signals.subkind_lexicons)
    # 2. conflicts (the named ones hold with or without a table; the rest
    #    only where a lexicon would otherwise decide — i.e. without a table)
    if signals.table and cheque:
        return uncertain()
    if "card" in lexical_kinds and signals.running_balance:
        return uncertain()
    if not signals.table:
        if cheque and (lexical_kinds - {"deposit_slip"}):
            return uncertain()
        if len(lexical_kinds) > 1:
            return uncertain()
        if (({"deposit_slip", "letter"} & lexical_kinds) or signals.screenshot) and signals.anchors >= 2:
            return uncertain()
        # a card / loan / brokerage lexicon beside deposit-account furniture
        # (checking, savings, deposits, withdrawals ...) is two account kinds
        # claiming one document
        if (lexical_kinds & {"card", "loan", "brokerage"}) and signals.deposit_account:
            return uncertain()
    # 3. sub-kinds: a lexicon decides only WITHOUT a statement table; the
    #    card statement may carry a table, but a card-shaped one (a single
    #    amount column, no running balance, no deposit-account furniture)
    if cheque:
        structural = signals.cheque_structural
        tier = "structural" if structural else "lexical"
        if "deposit_slip" in lexical_kinds:
            return _verdict("NOT_A_STATEMENT", "deposit_slip", tier, [], signals, profile, doc)
        return _verdict("NOT_A_STATEMENT", "voided_cheque" if signals.void else "cheque_image", tier, [], signals, profile, doc)
    if not signals.table:
        if "deposit_slip" in lexical_kinds:
            return _verdict("NOT_A_STATEMENT", "deposit_slip", "lexical", [], signals, profile, doc)
        if "letter" in lexical_kinds:
            return _verdict("NOT_A_STATEMENT", "letter_or_notice", "lexical", [], signals, profile, doc)
        if "card" in lexical_kinds:
            return _verdict("NOT_A_STATEMENT", "card_statement", "lexical", [], signals, profile, doc)
        if "loan" in lexical_kinds:
            return _verdict("NOT_A_STATEMENT", "loan_statement", "lexical", [], signals, profile, doc)
        if "brokerage" in lexical_kinds:
            return _verdict("NOT_A_STATEMENT", "brokerage", "lexical", [], signals, profile, doc)
        if signals.screenshot and signals.anchors < 2:
            return _verdict("NOT_A_STATEMENT", "screenshot", "structural", [], signals, profile, doc)
    elif "card" in lexical_kinds:
        # The card lexicon beside deposit-account furniture is the same
        # conflict on the table branch as on the no-table branch (review
        # MAJOR-1): two account kinds claim one document and the single
        # amount column cannot arbitrate — refuse, never fall through.
        if signals.deposit_account:
            return uncertain()
        if signals.single_amount_column and not signals.running_balance:
            return _verdict("NOT_A_STATEMENT", "card_statement", "lexical", [], signals, profile, doc)
    # 4. activity export
    if signals.table and signals.anchors == 0 and (signals.reverse_chronology or signals.pending):
        return _verdict("ACTIVITY_EXPORT", None, "structural" if signals.aligned else "lexical", [], signals, profile, doc)
    # 5. statements
    ledger = signals.table or signals.zero_activity or signals.short_ledger or signals.balance_pair
    shaped = (
        (ledger and signals.anchors >= 1)
        or signals.anchors >= 2
        or (signals.table and bool(signals.markers))
    )
    if not shaped:
        return uncertain()
    findings = _statement_findings(doc, signals, profile)
    # `_statement_findings` names every missing anchor and a missing ledger,
    # so "no finding" IS period AND opening AND closing AND a printed ledger
    # (review MAJOR-2: the former restated conjunction was dead code).
    if not findings:
        return _verdict("STATEMENT_COMPLETE", None, "structural" if signals.aligned else "lexical", [], signals, profile, doc)
    if not ledger:
        floor = ILLEGIBLE_RATIO * ILLEGIBLE_EXPECTED_WORDS_PER_PAGE
        # A native text layer cannot be illegible (review MINOR-3): the
        # E-class placeholder is for scanned / mixed / image-backed pages.
        if signals.words_per_page < floor and profile.classification != "digital":
            if doc.pages:
                signals.refs.append(EvidenceRef(doc.pages[0].index, None, None, "illegible_floor"))
            return _verdict("STATEMENT_ILLEGIBLE", None, "lexical", [], signals, profile, doc)
    codes = {finding.code for finding in findings}
    structural = bool(codes & {"page_gap", "missing_pages", "missing_first_page"}) or (
        "balance_discontinuity_at_page_break" in codes and signals.aligned
    )
    return _verdict("STATEMENT_PARTIAL", None, "structural" if structural else "lexical", findings, signals, profile, doc)


def classify_document(*, evidence: ExtractionEvidence | None, page_texts: tuple[str, ...] | None,
                      profile: DocumentProfileFacts) -> DocumentClass:
    """One disjoint kind with named evidence for one document. See the
    module docstring for the inputs, the modes and the decision order."""
    if evidence is not None and page_texts is not None:
        raise ValueError("give evidence OR page_texts, never both: the mode must be declared, not guessed")
    if evidence is not None and not isinstance(evidence, ExtractionEvidence):
        raise ValueError("evidence must be an evidence.canonical.ExtractionEvidence or None")
    if not isinstance(profile, DocumentProfileFacts):
        raise ValueError("profile must be a DocumentProfileFacts")
    if _file_invalid(profile):
        # Decided from the facts alone, BEFORE any text is read (mutant M10).
        return DocumentClass(
            kind="FILE_INVALID", sub_kind=None, modality="unknown", language="unknown", account_kind="unknown",
            completeness=(), evidence=(EvidenceRef(0, None, None, "file_invalid_fact"),), tier="structural",
            version=CLASSIFIER_VERSION,
        )
    doc = _build_doc(evidence, tuple(page_texts) if page_texts is not None else None)
    signals = _evaluate(doc)
    return _decide(doc, signals, profile)
