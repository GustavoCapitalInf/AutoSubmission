"""What a page shows in print, from sources other than the reviewer.

Two sources, both local (nothing leaves the process):
* the PDF's own text layer, when the page has one (a native PDF; None for a scanned page);
* the proposer's reading of the page, the layout text dots.mocr returned.

They settle two things the reviewer cannot be trusted with on its own word:
* a reviewer that contradicts itself about a row's description (its correction and its own observation
  disagree) is settled by the text layer alone, and only by the row's own printed block (the lines from its
  date to its amount, bounded by the neighbouring rows): whichever reading is printed there. The proposer's
  reading is never an arbiter for a description, because the disputed candidate came from it, and text
  printed elsewhere on the page (another row, a heading) never settles a row;
* a figure the reviewer reports (a balance, a stated total or count, a fee, a daily balance) is kept only if
  it is printed on the page, in the text layer or the proposer's reading. A figure printed nowhere is not
  evidence; it is dropped rather than allowed to contradict the arithmetic.

For measuring corroboration (vlm/confidence.py) only the text layer counts: the proposer's reading is where
the rows came from.
"""
from __future__ import annotations

import html
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property

# Money as printed: 1,000.00 / 1000.00, the decimal-comma forms 1.000,00 / 1000,00, and space-grouped
# decimal-comma 1 000,00 (French and Canadian statements; the space may be a no-break or thin space). A sign,
# currency symbol or brackets around it do not matter: figures are compared as magnitudes.
_SPACES = " \u00a0\u202f"
_MONEY = (
    (re.compile(r"(?<![\d.,])\d{1,3}(?:,\d{3})+\.\d{2}(?!\d)"), ",", "."),
    (re.compile(r"(?<![\d.,])\d+\.\d{2}(?!\d)"), "", "."),
    (re.compile(r"(?<![\d.,])\d{1,3}(?:\.\d{3})+,\d{2}(?!\d)"), ".", ","),
    (re.compile(rf"(?<![\d.,])\d{{1,3}}(?:[{_SPACES}]\d{{3}})+,\d{{2}}(?!\d)"), _SPACES, ","),
    (re.compile(r"(?<![\d.,])\d+,\d{2}(?![\d,])"), "", ","),
    (re.compile(r"(?<![\w.,])\.\d{2}(?![\d.,])"), "", "."),   # ".01": cents printed without a leading zero
)
_INTEGER = re.compile(r"(?<![\d.,])\d{1,6}(?![\d]|[.,]\d)")
_WHOLE_DOLLARS = re.compile(r"[$€£]\s?(\d{1,3}(?:,\d{3})+|\d{1,7})(?![\d]|[.,]\d)")
_TAG = re.compile(r"<[^>]+>")
# Tokens a wrapped description may have printed between its parts: the row's own money and dates.
_SKIPPABLE = re.compile(r"^[-+(]?\$?[\d.,]+\)?-?$|^\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?$")
# An amount with cents as a printed token ("1,234.56", "(5.00)", "12.00-"): never a description word.
_AMOUNT_TOKEN = re.compile(r"[-+(]?\$?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}\)?-?")


def _plain(text: str) -> str:
    """Text as its characters read: compatibility forms unfolded (a "ﬁ" ligature is "fi") and invisible format
    characters (a soft hyphen, a zero-width space) removed."""
    import unicodedata

    return "".join(char for char in unicodedata.normalize("NFKC", text) if unicodedata.category(char) != "Cf")


def _edits(first: str, second: str) -> int:
    """Levenshtein distance between two short tokens."""
    previous = list(range(len(second) + 1))
    for i, a in enumerate(first, 1):
        current = [i]
        for j, b in enumerate(second, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


# How many lines a row's printed block may reach from the line of its amount (a wire transfer prints the
# beneficiary and address over several lines, with the amount on a line of its own).
_ROW_REACH = 6
# A line that begins a row: it starts with a date (03/02, 03-02-26, 02.03.2026, 2026-03-02, Apr 29, Apr 29,
# 29 avr.). A dotted date needs its year, so that an amount such as 90.00 is never taken for one.
_MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
          r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|janv(?:ier)?|f[ée]vr(?:ier)?|mars|avr(?:il)?|mai|juin|"
          r"juil(?:let)?|ao[uû]t|d[ée]c(?:embre)?)\.?")
_ROW_START = re.compile(rf"^(?:\d{{1,2}}[/-]\d{{1,2}}(?:[/-]\d{{2,4}})?(?!\S)|\d{{1,2}}\.\d{{1,2}}\.\d{{2,4}}(?!\S)|"
                        rf"\d{{4}}-\d{{2}}-\d{{2}}(?!\S)|{_MONTH}\s+\d{{1,2}},?(?!\S)|\d{{1,2}}\s+{_MONTH}(?!\S))",
                        re.I)
_TOKEN = re.compile(r"\S+")
# A cheque-number column header inside a printed header line ("Date Check No. Amount", "Chk # Paid").
_CHEQUE_COLUMN = re.compile(r"\b(?P<word>check|cheque|chk)s?\s*(?:no\.?|nbr\.?|num\.?|number|#)(?!\w)", re.IGNORECASE)
# A serial-number column ("DATE SERIAL NO. AMOUNT") is a cheque-number column only under a heading that names
# cheques ("Checks Paid"), whose word then names them.
_SERIAL_COLUMN = re.compile(r"\bserial\s*(?:no\.?|nbr\.?|num\.?|number|#)(?!\w)", re.IGNORECASE)
_CHEQUE_HEADING = re.compile(r"^\s*(?P<word>check|cheque)s?\b", re.IGNORECASE)


_LINE_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
# A list bullet a proposer reads in front of a line ("● VIREMENT INTERAC ..."): layout, never text.
_BULLETS = frozenset("●•▪◦‣∙")


def spaced(text: str) -> str:
    """Whitespace-insensitive form: a line-break tag (a proposer's Markdown table cell writes "<br>" where a
    reviewer writes a newline) is whitespace, a bullet glyph standing alone is dropped, and runs of whitespace
    become one space."""
    return " ".join(token for token in _LINE_BREAK.sub(" ", str(text)).split() if token not in _BULLETS)


def _cents(value) -> Decimal | None:
    try:
        amount = abs(Decimal(str(value))).quantize(Decimal("0.01"))
    except (ArithmeticError, TypeError, ValueError):
        return None
    return amount if amount.is_finite() else None


def _amounts(text: str) -> set:
    return {amount for _, _, amount in _money_spans(text)}


def _money_spans(text: str) -> list[tuple[int, int, Decimal]]:
    """Every printed amount of a text with its character span, in order; overlapping readings of one figure
    keep the widest."""
    found = []
    for pattern, group, decimal in _MONEY:
        for match in pattern.finditer(text or ""):
            normal = match.group(0)
            for separator in group:
                normal = normal.replace(separator, "")
            amount = _cents(normal.replace(decimal, "."))
            if amount is not None:
                found.append((match.start(), match.end(), amount))
    found.sort(key=lambda span: (span[0], -span[1]))
    spans = []
    for span in found:
        if not spans or span[0] >= spans[-1][1]:
            spans.append(span)
    return spans


def native_page_texts(raw: bytes) -> list[str | None]:
    """Each page's own text layer, or None when a page has none (a scan, or text without letters or digits)."""
    import pypdfium2 as pdfium

    texts: list[str | None] = []
    with pdfium.PdfDocument(raw) as document:
        for index in range(len(document)):
            page = document[index]
            try:
                textpage = page.get_textpage()
                try:
                    text = textpage.get_text_range()
                finally:
                    textpage.close()
            finally:
                page.close()
            texts.append(text if re.search(r"[0-9A-Za-z]", text or "") else None)
    return texts


def layout_text(blocks) -> str:
    """The proposer's reading of a page as plain text: every block's content, table markup removed."""
    return "\n".join(html.unescape(_TAG.sub(" ", str(block.content))) for block in blocks)


@dataclass(frozen=True)
class PrintedEvidence:
    """A page's printed text from sources other than the reviewer: its text layer and the proposer's reading."""

    native: str | None
    proposer: str = ""

    @cached_property
    def _combined(self) -> str:
        return "\n".join(text for text in (self.native, self.proposer) if text)

    @cached_property
    def amounts(self) -> frozenset:
        return frozenset(_amounts(self._combined))

    @cached_property
    def native_amounts(self) -> frozenset:
        return frozenset(_amounts(self.native or ""))

    @cached_property
    def integers(self) -> frozenset:
        return frozenset(int(token) for token in _INTEGER.findall(self._combined))

    @cached_property
    def whole_dollars(self) -> frozenset:
        """Whole amounts printed with a currency sign and no cents ("$822", "$1,822")."""
        return frozenset(int(match.replace(",", "")) for match in _WHOLE_DOLLARS.findall(self._combined))

    @cached_property
    def _native_spaced(self) -> str | None:
        return spaced(self.native) if self.native else None

    @cached_property
    def _lines(self) -> list[tuple[str, list[tuple[str, int, int]]]]:
        """Each text-layer line with its tokens and their character spans (bullet glyphs are layout, left out)."""
        return [(line, [(match.group(0), match.start(), match.end()) for match in _TOKEN.finditer(line)
                        if match.group(0) not in _BULLETS])
                for line in (self.native or "").splitlines()]

    @property
    def text_lines(self) -> list[str]:
        """The text layer's lines, in printed order (none without a text layer)."""
        return [line for line, _ in self._lines]

    def cheque_column_word(self, number: str, amount, date_text=None, balance=None) -> str | None:
        """The printed word naming the cheque-number column a cheque read as its number alone sits in ("Check"
        from a "Date Check No. Amount" header, or a "Serial No." column under a "Checks Paid" heading): the line
        directly above the run of amount lines holding every line of this row that prints the number. None when
        no such line, or the header names no cheque-number column. A table printed two-up in the image is a
        column group at a time here, each under its own header."""
        # The row's lines are those printing its amount and date (a same-day twin of the amount elsewhere on the
        # page included) that also print its number.
        lines = [line for line in self.row_line_numbers(amount, date_text, balance) or ()
                 if number in {token.strip("*#") for token in self._native_lines[line]}]
        if not lines:
            return None
        words = set()
        for line in lines:
            top = line
            while top > 0 and self._line_spans[top - 1]:
                top -= 1
            header = self._lines[top - 1][0] if top > 0 else ""
            match = _CHEQUE_COLUMN.search(header)
            if match is None and _SERIAL_COLUMN.search(header) and top > 1:
                match = _CHEQUE_HEADING.match(self._lines[top - 2][0])
            if match is None:
                return None
            words.add(match.group("word"))
        return words.pop() if len(words) == 1 else None

    def covers_proposer(self, *, minimum_words: int = 20, share: float = 0.9) -> bool | None:
        """Whether the text layer prints what the proposer read on the page: at least `share` of the proposer's
        words (three letters or more) are words of the text layer. A page with a text-layer header over a
        scanned body fails it (the proposer reads rows the text layer does not print). None without a text
        layer, or when the proposer read fewer than `minimum_words` words: too little to tell."""
        if not self.native:
            return None
        words = re.findall(r"[a-z]{3,}", self.proposer.lower())
        if len(words) < minimum_words:
            return None
        printed = set(re.findall(r"[a-z]{3,}", self.native.lower()))
        return sum(word in printed for word in words) >= share * len(words)

    def zero_amount_printed_for(self, description, date_text=None) -> bool | None:
        """Whether the text layer prints a zero amount ("0.00") on a line that is this row's (told apart by its
        date) with the row's description words in its print. None without a text layer, or when several zero
        amounts are printed and nothing tells the row's apart."""
        if not self.native:
            return None
        lines = self.row_line_numbers(0, date_text)
        if lines is None:
            return None  # several zero amounts printed and nothing tells the row's apart: cannot say
        return bool(lines) and bool(self.description_words_near(description, 0, date_text))

    def printed_description(self, description, amount, date_text=None, balance=None) -> str | None:
        """The text layer's own characters for a description the readers wrote with small differences (a
        model's autocorrection, a dropped or swapped letter, a case: "FABRIKATEDTRITOWN" printed
        "FABRIKATEDTRIPTOWN", "FabPal" printed "Fabpal"): among the tokens of the row's own printed stream (its line
        told apart strictly; amounts and the row's own leading date left out), the one run of as many tokens as
        the reading whose tokens all equal the reading's ignoring case, but at most two, each within two edits.
        The row's line must print its own date or balance too (a lone printed occurrence of its amount is no
        proof the line is the row's: two rows whose amounts the readers swapped would swap descriptions), and
        the print must be plain characters (a ligature or an invisible format character is a glyph artefact, not
        a reading). None when the reading is printed exactly, the row cannot be placed, or no single such run
        exists."""
        if not self.native or not description or not description.strip():
            return None
        anchors = self._anchor_lines(amount, date_text, balance, strict=True)
        if not anchors:
            return None
        stream, first, last = self._row_stream(anchors[0])
        dated = spaced(date_text or "").split()
        closing = _cents(balance) if balance is not None else None
        if not ((dated and contains_words([token for _, token in stream[:last + 1]], dated))
                or (closing is not None and self._prints_balance(anchors[0], closing))):
            return None
        words = [token for _, token in stream if not _AMOUNT_TOKEN.fullmatch(token)]
        lead = spaced(date_text or "").split()
        if lead and words[:len(lead)] == lead:
            words = words[len(lead):]
        target = spaced(description).split()
        runs = set()
        for start in range(len(words) - len(target) + 1):
            run = words[start:start + len(target)]
            different = [(a, b) for a, b in zip(run, target) if a.lower() != b.lower()]
            if len(different) <= 2 and all(_edits(a.lower(), b.lower()) <= 2 for a, b in different):
                runs.add(" ".join(run))
        if len(runs) != 1:
            return None
        text = runs.pop()
        if text != _plain(text):
            return None
        return None if text == " ".join(target) else text

    def row_line_numbers(self, amount, date_text=None, balance=None) -> list[int] | None:
        """The text-layer lines that are this row's: its amount's printed occurrences, told apart by the row's
        balance and date as _anchor_lines measures them (several for same-day twins). None when nothing told
        them apart, empty when the amount is printed nowhere."""
        anchors = self._anchor_lines(amount, date_text, balance, strict=False)
        return None if anchors is None else sorted({line for line, _ in anchors})

    @cached_property
    def _native_lines(self) -> list[list[str]]:
        return [[token for token, _, _ in tokens] for _, tokens in self._lines]

    @cached_property
    def _line_spans(self) -> list[list[tuple[int, int, Decimal]]]:
        return [_money_spans(line) for line, _ in self._lines]

    @cached_property
    def _line_amounts(self) -> list[set]:
        return [{amount for _, _, amount in spans} for spans in self._line_spans]

    def amount_printed(self, value) -> bool:
        amount = _cents(value)
        return amount is not None and amount in self.amounts

    def amount_in_text_layer(self, value) -> bool | None:
        """Whether the text layer itself prints this amount; None without a text layer."""
        if not self.native:
            return None
        amount = _cents(value)
        return amount is not None and amount in self.native_amounts

    def integer_printed(self, value) -> bool:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return False
        return number == value and number in self.integers

    def description_printed(self, description) -> bool | None:
        """Whether the text layer prints this description anywhere on the page (whitespace-insensitive,
        punctuation-sensitive), or None without a text layer. Page-wide: never used to choose a row's reading."""
        if self._native_spaced is None:
            return None
        text = spaced(description or "")
        return bool(text) and text in self._native_spaced

    def _anchors(self, amount) -> list[tuple[int, int]]:
        """Every printed occurrence of the amount, as (line, index of that figure among the line's figures): a
        line can print it twice (two cheques of one amount side by side, an amount equal to its balance)."""
        target = _cents(amount)
        if target is None:
            return []
        return [(line, own) for line, spans in enumerate(self._line_spans)
                for own, span in enumerate(spans) if span[2] == target]

    def _anchor_lines(self, amount, date_text=None, balance=None, *, strict: bool = True):
        """The occurrence of the amount that is this row's. When several are printed (identical amounts, or a
        neighbour's balance equal to it), the ones printing the row's own running balance after them, then the
        ones whose row prints the row's own date as read (date_text): in the row's own segment first, else just
        after the amount (a date column after the amount column). Strict (choosing a reading): exactly one, else
        None, the row cannot be told from its neighbours. Not strict (measuring): the candidates its balance or
        its date confirmed, which may be several same-day twins; None when nothing told them apart. An empty
        list when the amount is printed nowhere."""
        anchors = self._anchors(amount)
        if len(anchors) <= 1:
            return anchors
        candidates, confirmed = anchors, False
        closing = _cents(balance) if balance is not None else None
        if closing is not None:
            with_balance = [anchor for anchor in candidates if self._prints_balance(anchor, closing)]
            if with_balance:
                candidates, confirmed = with_balance, True
        wanted = spaced(date_text or "").split()
        if wanted and (len(candidates) > 1 or not confirmed):
            for trailing in (False, True):
                dated = [anchor for anchor in candidates
                         if contains_words([token for _, token in self._row_stream(anchor, trailing=trailing)[0]],
                                           wanted)]
                if dated:
                    candidates, confirmed = dated, True
                    break
        if strict:
            return candidates if len(candidates) == 1 and confirmed else None
        return candidates if confirmed else None

    def _prints_balance(self, anchor: tuple[int, int], closing: Decimal) -> bool:
        """Whether the anchor's line prints the row's running balance after the row's own amount."""
        line, own = anchor
        return any(span[2] == closing for span in self._line_spans[line][own + 1:])

    def governing_date(self, amount, balance=None):
        """For a row read without a date: the date the page prints for it, as a date text. A date on the row's
        own print (a date column the reading lost); else the date that begins the nearest line above the row's
        amount (a statement printing each day's date once, on the day's first row). "" when no line above it on
        the page begins with a date (the day continues from the previous page, last_date_text); None when there
        is no text layer or the row cannot be located (its amount printed nowhere, or on several rows its
        balance does not tell apart)."""
        from vlm.dates import date_text_parts

        if not self.native:
            return None
        anchors = self._anchor_lines(amount, None, balance)
        if not anchors:
            return None
        # A date column after the amount ("... 50.00 DEC31 1,234.56"); a date that begins the row's own line is
        # found by the search upward, which starts at that line. The description before the amount is not
        # searched: it can print other dates (an invoice's).
        stream, first, last = self._row_stream(anchors[0], trailing=True)
        after = [token for index, token in stream[last + 1:] if index == anchors[0][0]]
        for size in (1, 2, 3):   # "01/05", "Apr 29", "Apr 29, 2026"
            for start in range(len(after) - size + 1):
                text = " ".join(after[start:start + size])
                if date_text_parts(text):
                    return text
        if anchors[0][1] > 0:
            # The row's amount is not its line's first: the line's leading date belongs to the row printed
            # before it on that line (a cheque table printed two-up), and the lines above to other rows.
            return None
        for index in range(anchors[0][0], -1, -1):
            count = self._row_starts[index]
            if count:
                return " ".join(self._native_lines[index][:count])
        return ""

    @cached_property
    def last_date_text(self) -> str | None:
        """The date that begins the page's last dated line, or None."""
        for index in range(len(self._native_lines) - 1, -1, -1):
            count = self._row_starts[index]
            if count:
                return " ".join(self._native_lines[index][:count])
        return None

    def balance_printed_for(self, amount, balance, date_text=None) -> bool | None:
        """Whether the row's own print carries this running balance: a figure after the row's amount on its
        line, or on another line of its printed block. True when any printed occurrence of the amount carries
        it; False only when none does and the row is located on its own (its amount printed once, or its date
        telling it apart); None without a text layer or when the row cannot be located: nothing is decided."""
        if not self.native:
            return None
        closing = _cents(balance)
        anchors = self._anchors(amount) if closing is not None else []
        if not anchors:
            return None
        if any(self._carries_balance(anchor, closing) for anchor in anchors):
            return True
        return False if self._anchor_lines(amount, date_text) else None

    def _carries_balance(self, anchor: tuple[int, int], closing: Decimal) -> bool:
        if self._prints_balance(anchor, closing):
            return True
        return any(closing in self._line_amounts[index] for index in self._block(anchor[0]) if index != anchor[0])

    @cached_property
    def _row_starts(self) -> list[int]:
        """Per line, how many leading tokens are the date that begins a row (0 when the line begins none)."""
        starts = []
        for tokens in self._native_lines:
            match = _ROW_START.match(" ".join(tokens))
            starts.append(len(match.group(0).split()) if match else 0)
        return starts

    def _block(self, anchor: int) -> range:
        """The printed block of the row whose amount is on line ``anchor``: back to the row's first line (the
        nearest line that begins with a date) and forward to just before the next row's first line, never
        reaching a line that prints other money, and at most _ROW_REACH lines each way."""
        amounts, starts = self._line_amounts, self._row_starts
        start = anchor
        while not starts[start] and start > max(0, anchor - _ROW_REACH) and not amounts[start - 1]:
            start -= 1
        end = anchor + 1
        while end < min(len(amounts), anchor + _ROW_REACH + 1) and not amounts[end] and not starts[end]:
            end += 1
        return range(start, end)

    def _row_stream(self, anchor: tuple[int, int], *, trailing: bool = False):
        """(stream, first, last): the row's printed tokens as (line, token) in text order, and the stream
        positions of the row's own segment of the anchor line.

        On a line that prints several amounts (a two-column cheque table; an amount then a balance), the row's
        segment runs from just after the previous amount to the end of its own; the lines above belong to the
        row only when its segment starts the line. ``trailing`` adds the tokens after the row's amount up to the
        next amount (a date printed after the amount), for telling rows apart only, never for reading one."""
        index_line, own = anchor
        line, tokens = self._lines[index_line]
        spans = self._line_spans[index_line]
        begin, finish = (spans[own - 1][1] if own else 0), spans[own][1]
        block = self._block(index_line)
        stream = []
        if own == 0:
            stream += [(index, token) for index in block if index < index_line for token in self._native_lines[index]]
        first = len(stream)
        segment = [(index_line, token) for token, start, _ in tokens if begin <= start < finish]
        # Date | Amount | Description (Citizens): nothing but figures before the line's last amount, so the
        # words after it are the row's own. Never when another amount follows on the line (a second column:
        # the next cheque's number and date).
        after = own == len(spans) - 1 and all(_SKIPPABLE.match(token) for _, token in segment)
        if after:
            segment += [(index_line, token) for token, start, _ in tokens if start >= finish]
        stream += segment
        last = len(stream) - 1
        if trailing and not after:
            following = spans[own + 1][0] if own + 1 < len(spans) else len(line)
            stream += [(index_line, token) for token, start, _ in tokens if finish <= start < following]
        stream += [(index, token) for index in block if index > index_line for token in self._native_lines[index]]
        return stream, first, last

    def description_printed_near(self, description, amount, date_text=None, balance=None) -> bool | None:
        """Whether the text layer prints this description as the row of its own amount, the only evidence that
        may choose between readings of a row: its words in order, contiguous except for money and date tokens
        (a description wrapped round the amount column), inside the row's own printed stream (_row_stream), and
        either

        * touching the row's segment of its amount line, or
        * when that segment prints only figures and dates (a description over several lines, its amount on a
          line of its own below): starting right after the date that begins the row and running to the amount
          line with nothing but figures and dates between.

        None without a text layer, or when several rows print the amount and the row's date does not tell
        which is this one (_anchor_lines: its running balance or its date); False when no line prints the
        amount."""
        if not self.native:
            return None
        words = spaced(description or "").split()
        if not words:
            return False
        anchors = self._anchor_lines(amount, date_text, balance)
        if anchors is None:
            return None
        for anchor in anchors:
            stream, first, last = self._row_stream(anchor)
            figures_only = all(_SKIPPABLE.match(stream[position][1]) for position in range(first, last + 1))
            block = self._block(anchor[0])
            dated = first > 0 and block.start < anchor[0] and self._row_starts[block.start]
            for start in range(len(stream)):
                end = _match_from(stream, start, words)
                if end is None:
                    continue
                if start <= last and end >= first:
                    return True
                if (figures_only and dated and start == self._row_starts[block.start] and end < first
                        and all(_SKIPPABLE.match(token) for _, token in stream[end + 1:first])):
                    return True
        return False

    def description_words_near(self, description, amount, date_text=None, balance=None) -> bool | None:
        """Looser, for measuring corroboration only (never for choosing a reading): every word of the description
        is printed in the row's own print, in any order, at least as often. That is its printed stream
        (_row_stream); when the row's segment of its amount line prints only figures and dates, only the lines
        from the date that begins the row down to that segment (the lines after it are the next row's). Rows
        printing the same amount on the same date are not told apart: the description counts when it is printed
        on one of them. None without a text layer, or when several rows print the amount and neither the row's
        balance nor its date confirms any; False when no line prints the amount."""
        if not self.native:
            return None
        wanted = Counter(spaced(description or "").split())
        if not wanted:
            return False
        anchors = self._anchor_lines(amount, date_text, balance, strict=False)
        if anchors is None:
            return None
        for anchor in anchors:
            stream, first, last = self._row_stream(anchor)
            if all(_SKIPPABLE.match(stream[position][1]) for position in range(first, last + 1)):
                # The lines above belong to the row when they start at its date, or right after the previous
                # row's amount line (a statement that prints each day's date once, on the day's first row).
                block = self._block(anchor[0])
                owned = first > 0 and block.start < anchor[0] and bool(
                    self._row_starts[block.start] or (block.start > 0 and self._line_amounts[block.start - 1]))
                stream = stream[:last + 1] if owned else stream[first:last + 1]
            if not wanted - Counter(token for _, token in stream):
                return True
        return False


def contains_words(tokens: list, words: list) -> bool:
    """Whether ``words`` occur in ``tokens`` as a contiguous run of whole tokens ("123" is not inside "1234")."""
    size = len(words)
    return size > 0 and any(tokens[index:index + size] == words for index in range(len(tokens) - size + 1))


def _match_from(stream: list, start: int, words: list) -> int | None:
    """The position of the last token of ``words`` matched in order from ``stream[start]``, skipping only money
    and date tokens between them; None when they are not printed so."""
    if stream[start][1] != words[0]:
        return None
    position = start
    for word in words[1:]:
        position += 1
        while position < len(stream) and stream[position][1] != word and _SKIPPABLE.match(stream[position][1]):
            position += 1
        if position >= len(stream) or stream[position][1] != word:
            return None
    return position
