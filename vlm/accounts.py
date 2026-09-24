"""The accounts a statement prints (a member statement's savings shares beside its checking account; a bank's
combined statement): each account's printed heading, where it applies in reading order, and the figures printed in
its own section. Deterministic, from the proposer's layout blocks; no model call, no reviewer figure.

A heading names an account when a short title line prints an account kind (checking, savings, share, money market,
certificate, ...) or an identifier the paper prints as one (a masked number, an "ID"/"Suffix"/"Account" number, a
number in parentheses). A sentence, a line printing money, a page header or footer, or a listing's caption ("Checks
Cleared", "Summary of Accounts") never is. Headings printing the same identifier, or the same title where either
prints none, are one account ("... (continued)" on each later page). A row belongs to the account whose heading is
printed last before it in reading order; rows before the first heading belong to none.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from vlm.metadata import BEGIN_RE, END_RE, TOTAL_CREDITS_RE, TOTAL_DEBITS_RE
from vlm.tables import parse_html_tables
from vlm.textparse import parse_money

ACCOUNT_PLAN_VERSION = 1

# Kinds in the order they are tested: a "share draft" is checking before "share" is savings, a "share certificate" a
# certificate, a "money market savings" account a money market account.
_KINDS = (
    ("checking", re.compile(r"\b(?:checking|chequing|share\s+drafts?|demand\s+deposits?|dda)\b", re.I)),
    ("money_market", re.compile(r"\b(?:money\s*market|mmda|mma)\b", re.I)),
    ("certificate", re.compile(r"\b(?:certificates?|cds?|term\s+deposits?|time\s+deposits?)\b", re.I)),
    ("retirement", re.compile(r"\b(?:ira|retirement|hsa)\b", re.I)),
    ("loan", re.compile(r"\b(?:loans?|mortgage|heloc|line\s+of\s+credit)\b", re.I)),
    ("credit_card", re.compile(r"\b(?:credit\s+cards?|visa|mastercard)\b", re.I)),
    ("savings", re.compile(r"\b(?:savings?|shares?|club|membership)\b", re.I)),
)
DEPOSIT_KINDS = frozenset({"checking", "money_market", "certificate", "retirement", "savings"})
_MARKUP = re.compile(r"<[^>]+>|[#*_`]+|\\[a-z]+\{|[{}$]")
_CONTINUED_TAIL = re.compile(r"[\s,;:.\-–—(]*\b(?:continued|cont'?d)\b(?:\s+(?:from|on)\s+(?:the\s+)?"
                             r"(?:previous|prior|next|last)\s+page)?[\s.)]*$", re.I)
_CONTINUED_ONLY = re.compile(r"^\(?\s*(?:continued|cont'?d)(?:\s+(?:from|on)\s+(?:the\s+)?(?:previous|prior|next|last)"
                             r"\s+page)?\s*\.?\s*\)?$", re.I)
_PREFIX = re.compile(r"^(?:(?:account|acct)\s+)?(?:activity|analysis|detail|details|summary|transactions?|"
                     r"transaction\s+(?:detail|history)|history|statement)\s+(?:for|of)\s+(?:your\s+)?", re.I)
_SUFFIX = re.compile(r"(?:\s*[-–—:|]\s*|\s+)(?:account\s+)?(?:summary|activity|detail|details|transactions?|"
                     r"transaction\s+(?:detail|history)|history|statement)\s*$", re.I)
# Captions of listings and notices, never an account's own title.
_NOT_A_TITLE = re.compile(
    r"\b(?:cleared|paid|posted|deposits|withdrawals|debits|credits|fees|charges|balances|transactions|checks|"
    r"cheques|payments|recap|overdrafts?|returned|ytd|daily\s+balances?|totals?|information|notices?|disclosures?|"
    r"terms|agreement|rights|errors?|questions?|reconcil\w*|instructions|important|computation|explanation|"
    r"summary\s+of|year[\s-]+to[\s-]+date|at\s+a\s+glance|all\s+accounts|other\s+accounts)\b", re.I)
# A sentence, never a title: an instruction, a courtesy, a contact line.
_SENTENCE = re.compile(r"\b(?:please|thank|thanks|if|call|visit|www|http|https|contact|inquir\w*|phone|fax|e-?mail|"
                       r"hours|toll)\b|@|\b\d{3}[-.)\s]\s?\d{3}[-.][0-9A-Z]{4}\b|\b1-8\d\d\b", re.I)
# Words of a sentence that a short account title can print too ("Your Business Checking", "US Bank Checking", "...
# Activity for May"): they disqualify only a line naming no account kind, or a long one.
_SENTENCE_WORDS = re.compile(r"\b(?:you|your|we|our|us|will|may)\b", re.I)
# A verb makes a line a sentence ("Your savings are insured by the NCUA", "We value your checking relationship").
_VERBS = re.compile(r"\b(?:are|is|was|were|be|been|can|could|should|must|earns?|earned|insured|available|changes?|"
                    r"changed|offers?|provides?|protect(?:s|ed)?|appl(?:y|ies)|needs?|has|have|made|pays?)\b", re.I)
# The pronouns of marketing prose: a title may open with "Your" but never prints one further on.
_MARKETING_WORDS = re.compile(r"\b(?:your|our|we|us|you)\b", re.I)
# Product names built of sentence words ("Pay As You Go Checking"): read as one word by the sentence rules.
_PRODUCT_IDIOMS = re.compile(r"\bpay\s+as\s+you\s+go\b", re.I)
# Prose a title never prints: an article or "to" before a word (never a month: "... March 1 to March 31"), or an
# invitation's adverb ("Open A Savings Account Today", "Switch To Paperless Checking Statements", "Savings Goals Start
# Here"). "Now" is a product's word ("Business NOW Account").
_PROSE_WORDS = re.compile(r"\b(?:(?:a|an|to)\s+(?!(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b)"
                          r"(?=[A-Za-z]{2})|(?:here|today)\b)", re.I)
# Words of an advertisement, never of an account's title ("Introducing Business Checking Plus", "Business Checking Just
# Got Better"; review 12); and words an advertisement prints that a product's name can print too ("Business Checking
# Simplified" but "Simplified Employee Pension IRA XXXX1234"; "New Savings Rates Effective April 1" but "Preferred
# Rates Money Market 0005"; "Meet Business Checking Plus" but "Meet Me Checking"): an advertisement's only on a line
# printing no identifier and not ending in its kind word (review 13).
_MARKETING_PHRASES = re.compile(r"\b(?:introducing|announcing|coming\s+soon|reinvented|reimagined|redefined|just\s+got|"
                                r"got\s+better)\b", re.I)
_MARKETING_TITLE_WORDS = re.compile(r"\b(?:meet|rates|simplified)\b", re.I)
# Words that make the verb after them a sentence's, never a product's ("Now Available Business Checking Plus", "Get
# Protected Business Checking"; review 13).
_VERB_ADVERBS = frozenset({"now", "get", "newly", "also", "just", "still"})
# Forms of "be" and "have" are never a product's word: after a line's first word they make it a sentence in any case
# ("Checking Accounts Are Changing"); the other verbs do only in lower case or beside a sentence word.
_STRONG_VERBS = re.compile(r"(?:are|is|was|were|been|has|have)", re.I)
_POSSESSIVE = re.compile(r"^(?:your|our|my)\s+", re.I)
# "... for May", "... for the period ending 03/31": the period a title is printed for, not its name.
_PERIOD_TAIL = re.compile(r"\s+(?:activity\s+)?for\s+(?:the\s+)?(?:period|month|statement|jan\w*|feb\w*|mar\w*|apr\w*|"
                          r"may|jun\w*|jul\w*|aug\w*|sep\w*|oct\w*|nov\w*|dec\w*)\b.*$", re.I)
# An identifier's own line ("Member Number xxxx1234", "Account number: 123 (primary account)"): it names no account.
_IDENTIFIER_LINE = re.compile(r"^(?:account|acct|member|customer|client)\s*(?:number|no\.?|#|id)\b", re.I)
# Words a title can print that say nothing about which account it is: its kind, and generic qualifiers. A title made
# only of them ("Checking", "Checking Accounts", "Checking Account Activity - Main Account") names an account of its
# kind that nothing else contradicts.
_GENERIC_WORDS = frozenset((
    "checking chequing savings saving share shares draft drafts money market certificate certificates cd cds club "
    "membership deposit deposits demand account accounts acct business personal commercial activity main primary "
    "summary detail details statement transactions transaction history of for the and your my").split())
_MONEY = re.compile(r"\d\.\d{2}(?!\d)|[$€£]\s?\d")
_MASKED = re.compile(r"(?:[xX*•·]{2,}|\.{2,}|…)\s*-?\s*(\d{2,})\b")
_LABELLED = re.compile(r"\b(?:account|acct|a/c|id|suffix|share|no\.?|number|#)\s*(?:number|no\.?|#)?\s*[:#.]?\s*"
                       r"(\d[\d\s-]*\d|\d)\b", re.I)
_PARENS = re.compile(r"\((\d{2,})\)")
_LONG = re.compile(r"(?<![\d.,/])\d{4,}(?![\d.,/%])")
_LETTER_NUMBER = re.compile(r"^([A-Za-z])\s+(\d{1,4})\b")
_LEADING_NUMBER = re.compile(r"^\d{1,3}\s+(?=[A-Za-z])")
_NUMBER_LINE = re.compile(r"^(?:account|acct)\s*(?:number|no\.?|#)\s*[:#]?\s*([xX*•\d][\dxX*•\s-]{2,}?)"
                          r"\s*(?:\([^)]*\))?$", re.I)
# Page furniture: a line in it names the statement's account on every page, never a section.
_FURNITURE = frozenset({"page_header", "page_footer", "picture", "image", "footnote"})
_HEADING_LABELS = frozenset({"section_header", "title", "doc_title", "paragraph_title", "header", "text"})
_CAPTION_LABELS = frozenset({"section_header", "title", "doc_title", "paragraph_title", "header"})


@dataclass(frozen=True)
class Heading:
    page: int
    order: int
    kind: str | None
    title: str  # the printed title without markup, identifier, "continued" or "account activity for"
    number: str | None  # the identifier's digits as printed (masking removed), or None
    continued: bool
    text: str  # the heading line as printed (markup removed)


@dataclass
class AccountSection:
    index: int
    kind: str | None
    title: str
    number: str | None
    headings: list = field(default_factory=list)
    # The number came from an "Account Number ..." line under a heading printing none: a later heading of the same
    # title printing another identifier (a suffix, a masked form) names the same account.
    number_from_line: bool = False

    @property
    def key(self) -> str | None:
        return _number_key(self.number)

    def label(self) -> str:
        return self.title + (f" ...{self.key}" if self.key else "")


def _clean(text: str) -> str:
    return " ".join(_MARKUP.sub(" ", str(text or "")).split())


def _number_key(number: str | None) -> str | None:
    """The identifier's last four digits (all of them when shorter): what two prints of one account share."""
    digits = re.sub(r"\D", "", number or "")
    return digits[-4:] if digits else None


def _title_key(title: str) -> str:
    words = re.sub(r"[^0-9a-z ]+", " ", title.lower()).split()
    return " ".join(word for word in words if word not in ("account", "acct", "the", "a", "an"))


def _kind(text: str) -> str | None:
    for kind, pattern in _KINDS:
        if pattern.search(text):
            return kind
    return None


def _kind_at_start(text: str) -> str | None:
    """The kind a text begins with ("Money Market Account 5678": money_market), or None."""
    for kind, pattern in _KINDS:
        if pattern.match(text):
            return kind
    return None


# Words that qualify a kind word in a product's name ("Overdraft Protected Business Checking").
_KIND_QUALIFIERS = frozenset({"business", "personal", "commercial", "small"})
# The last words of a kind printed in two words ("Money Market", "Share Draft", "Demand Deposit").
_KIND_TAILS = frozenset({"market", "draft", "drafts", "deposit", "deposits"})


def _ends_in_kind(text: str) -> bool:
    """Whether a line's last word names its kind ("Ready to Grow Savings", "... Money Market"); "Account" is not one."""
    words = re.findall(r"[A-Za-z]+", text)
    if not words:
        return False
    return (_kind_at_start(words[-1]) is not None
            or (len(words) > 1 and words[-1].lower() in _KIND_TAILS
                and _kind_at_start(" ".join(words[-2:])) is not None))


def _identified(text: str) -> bool:
    """Whether a line prints an account identifier: masked, labelled, in parentheses, or a long number that is not a
    year ("Open A Checking Account Before June 30 2031" prints none; review 13)."""
    if any(pattern.search(text) for pattern in (_MASKED, _LABELLED, _PARENS, _LETTER_NUMBER)):
        return True
    return any(not re.fullmatch(r"(?:19|20)\d\d", match.group(0)) for match in _LONG.finditer(text))


def _prose_in_title(text: str) -> bool:
    """Whether every prose word of a title-case line is printed in lower case ("Ready to Grow Savings", "Learn to Save
    Youth Savings"): a product's name; an advertisement capitalises them ("Switch To Business Checking", "Open A Money
    Market"; review 13)."""
    matches = list(_PROSE_WORDS.finditer(text))
    prose = {match.group(0).split()[0] for match in matches}
    others = [word for word in re.findall(r"[A-Za-z][A-Za-z'&-]*", text) if word not in prose]
    return (bool(matches) and all(word.islower() for word in prose)
            and bool(others) and all(word[0].isupper() for word in others))


def _sentence_case(text) -> bool:
    """A line printed as a sentence: two words or more, the first capitalised and every other one in lower case."""
    words = [word for word in _clean(str(text or "")).split() if re.search(r"[A-Za-z]", word)]
    return len(words) >= 2 and words[0][:1].isupper() and all(word == word.lower() for word in words[1:])


def _marketing_line(text) -> bool:
    """A line in sentence case naming an account word, printed as running text or as a heading ("Grow your savings
    faster", "Open a savings account today"): marketing, never an account's title. A title printed in sentence case
    ("Business checking", "Small business checking account") is a title: at most two words besides a title's generic
    words, no sentence word and no verb."""
    if not _sentence_case(text):
        return False
    clean = _clean(str(text or ""))
    if _SENTENCE_WORDS.search(clean) or _VERBS.search(clean):
        return True
    # A title names its kind with at most two words of its own ("Small business checking account"); more is prose.
    words = [word.lower().strip("().,:;") for word in clean.split() if re.search(r"[A-Za-z]", word)]
    return len([word for word in words if word not in _GENERIC_WORDS]) > 2


def parse_heading(text: str) -> Heading | None:
    """The account a printed title line names (page and order 0), or None when it names none."""
    line = _clean(str(text or "").strip().splitlines()[0] if str(text or "").strip() else "")
    if not line or len(line) > 100:
        return None
    continued = bool(_CONTINUED_TAIL.search(line))
    line = _CONTINUED_TAIL.sub("", line).strip(" -–—:|,")
    if (not line or _MONEY.search(line) or _SENTENCE.search(line) or _IDENTIFIER_LINE.match(line)
            or _MARKETING_PHRASES.search(line)
            or (_MARKETING_TITLE_WORDS.search(line) and not (_identified(line) or _ends_in_kind(line)))):
        return None
    # A verb makes a sentence ("Business Checking has changed", "Business Checking Offers More"), unless it opens the
    # line ("Earn More Savings") or is a capitalised word of a product's name right before its kind word, a qualifier
    # between them ("POWER PROTECTED CHECKING", "Special Needs Savings", "Business Insured Money Market Account",
    # "Custom Made Business Checking") and no adverb before it ("Now Available Business Checking Plus"); and any verb
    # beside a sentence word, the first word included ("Protect your checking account", "Is your checking account
    # earning interest").
    plain = _PRODUCT_IDIOMS.sub("PRODUCT", line)
    verbs = list(_VERBS.finditer(plain))

    def product_word(match):
        before = plain[:match.start()].split()
        following = plain[match.end():].split()
        while following and following[0].lower() in _KIND_QUALIFIERS:
            following = following[1:]
        return (not match.group(0).islower() and not _STRONG_VERBS.fullmatch(match.group(0))
                and not (before and before[-1].lower() in _VERB_ADVERBS)
                and _kind_at_start(" ".join(following)) is not None)

    if any(match.start() > 0 and not product_word(match) for match in verbs) or (
            verbs and _SENTENCE_WORDS.search(plain)):
        return None
    # A title says "Your" first, if at all: "Your", "Our", "We", "Us" or "You" further on is a sentence ("Grow Your
    # Savings Faster"); the month a title is printed for is no sentence word ("... Activity for May").
    if any(match.start() > 0 for match in _MARKETING_WORDS.finditer(_PERIOD_TAIL.sub("", plain))):
        return None
    # Prose words, unless the line prints an identifier or prints them in lower case in a title-case line: product
    # names ("SAVE TO WIN SAVINGS 0005", "Plan A Savings 0003", "Ready to Grow Savings"; reviews 12, 13).
    prose = _PERIOD_TAIL.sub("", plain)
    if _PROSE_WORDS.search(prose) and not (_identified(prose) or _prose_in_title(prose)):
        return None
    # A title's own words, without its identifier and the words every title can add ("Account", "Summary").
    title_words = [token for token in line.split()
                   if re.search(r"[A-Za-z]", token) and not re.search(r"\d", token)
                   and token.lower().strip(".,:;#()") not in ("account", "acct", "summary")]
    sentence_words = len(_SENTENCE_WORDS.findall(plain))
    if sentence_words > 1 or (sentence_words and (_kind(line) is None or len(title_words) > 5)):
        return None
    line = _POSSESSIVE.sub("", _PERIOD_TAIL.sub("", line))
    line = _PREFIX.sub("", line)
    line = _SUFFIX.sub("", line).strip(" -–—:|,")
    if not line or len(line.split()) > 12:
        return None
    number, strong, remainder = None, False, line
    for pattern in (_MASKED, _LABELLED, _PARENS, _LETTER_NUMBER):
        match = pattern.search(remainder)
        if match:
            number, strong = re.sub(r"\D", "", match.group(match.lastindex)), True
            remainder = (remainder[:match.start()] + " " + remainder[match.end():]).strip()
            break
    if number is None:
        found = list(_LONG.finditer(remainder))
        if found:
            number = found[-1].group(0)
            remainder = (remainder[:found[-1].start()] + " " + remainder[found[-1].end():]).strip()
    title = " ".join(remainder.strip(" -–—:|,#").split())
    title = _SUFFIX.sub("", title).strip(" -–—:|,")
    title = re.sub(r"\s*[-–—:|]\s*(?:account|acct)\.?\s*[#:]*$", "", title, flags=re.I).strip(" -–—:|,")
    if not re.search(r"[A-Za-z]{3,}", title) or _NOT_A_TITLE.search(title):
        return None
    kind = _kind(title)
    if kind is None and not strong and not (_LEADING_NUMBER.match(title) and re.search(r"\baccount\b", title, re.I)):
        return None
    if kind is None and number is None and not re.search(r"\baccount\b", title, re.I):
        return None
    return Heading(0, 0, kind, title, number, continued, line)


def number_line(text: str) -> str | None:
    """The identifier an "Account Number ..." line prints on its own (it names the account headed just above)."""
    line = _clean(str(text or "").strip().splitlines()[0] if str(text or "").strip() else "")
    match = _NUMBER_LINE.match(line)
    return re.sub(r"\D", "", match.group(1)) or None if match else None


def _grid(block) -> list[list[str]]:
    if block.label == "table":
        grids = parse_html_tables(block.content)
        return grids[0] if grids else []
    lines = [line.strip() for line in str(block.content).splitlines() if line.strip()]
    if lines and all("|" in line for line in lines) and any(re.fullmatch(r"[|:\-\s]+", line) for line in lines):
        return [[cell.strip() for cell in line.strip("|").split("|")] for line in lines
                if not re.fullmatch(r"[|:\-\s]+", line)]
    return []


def block_heading_text(block) -> str | None:
    """The line a block would print as an account heading: a title-like block's single line, or a table's caption
    (its first row's first cell, spanning or beside a "continued" note)."""
    if block.label in _FURNITURE:
        return None
    grid = _grid(block)
    if grid:
        first = [_clean(cell) for cell in grid[0] if _clean(cell)]
        if not first:
            return None
        return first[0]
    if block.label not in _HEADING_LABELS:
        return None
    lines = [line for line in str(block.content).splitlines() if line.strip()]
    if not lines or (block.label == "text" and len(lines) > 2):
        return None
    return lines[0]


def _table_title(block) -> str | None:
    """A table's own title: a first row printing one text across its columns, above more rows."""
    grid = _grid(block) if block.label == "table" else []
    if len(grid) < 3:
        return None
    first = {_clean(cell) for cell in grid[0] if _clean(cell)}
    return first.pop() if len(first) == 1 else None


def _generic(title: str) -> bool:
    words = re.sub(r"[^0-9a-z ]+", " ", title.lower()).split()
    return all(word in _GENERIC_WORDS for word in words)


def _same_account(heading: Heading, section: AccountSection) -> bool:
    if heading.kind and section.kind and heading.kind != section.kind:
        return False
    if heading.number and section.number:
        if _number_key(heading.number) == section.key:
            return True
        # A number read from an "Account Number" line, then the same title printing another identifier.
        return section.number_from_line and _title_key(heading.title) == _title_key(section.title)
    if _title_key(heading.title) == _title_key(section.title):
        return True
    # A title naming nothing but the account's kind is any account of that kind it does not contradict: a summary's
    # "Checking" heading and the ledger's "Business Checking" heading of one checking account.
    return (heading.kind is not None and heading.kind == section.kind
            and (_generic(heading.title) or _generic(section.title)))


@dataclass
class AccountPlan:
    sections: list  # AccountSection, in the order first printed
    switches: list  # (page, order, section index), in reading order
    captions: dict  # (page, order) -> the nearest title-like line above the block on its page
    crop_orders: dict  # (page, crop index, crop-local block order) -> full-page block order
    block_pages: dict  # page -> ordered block orders printing content (no page furniture)
    titles: dict = field(default_factory=dict)  # (page, order) -> a table's own spanning title row
    tops: dict = field(default_factory=dict)  # (page, order) -> the block's top on its page (0-1), when boxed
    money_blocks: set = field(default_factory=set)  # (page, order) of blocks printing an amount with cents
    version: int = ACCOUNT_PLAN_VERSION

    def section_at(self, page: int, order: int) -> int | None:
        current = None
        for switch_page, switch_order, index in self.switches:
            if (switch_page, switch_order) > (page, order):
                break
            current = index
        return current

    def carried_into(self, page: int) -> int | None:
        return self.section_at(page, -1)

    def page_sections(self, page: int) -> set:
        """Every account a page can print rows of: the one carried onto it when something printing money precedes
        the page's first heading (or it has none), and each one headed on it. A page's header lines (its period,
        its page number) print no money and carry no account's rows."""
        on_page = [(order, index) for switch_page, order, index in self.switches if switch_page == page]
        found = {index for _, index in on_page}
        carried = self.carried_into(page)
        if carried is not None:
            first = min((order for order, _ in on_page), default=None)
            if first is None or any(order < first and (page, order) in self.money_blocks
                                    for order in self.block_pages.get(page, ())):
                found.add(carried)
        return found

    def section_at_y(self, page: int, top: float):
        """The account whose heading is printed last above height ``top`` (0-1) of a page; UNPLACED when a heading on
        the page has no box to compare with."""
        best = None
        for switch_page, order, index in self.switches:
            if switch_page != page:
                continue
            position = self.tops.get((page, order))
            if position is None:
                return UNPLACED
            if position <= top + _SAME_LINE and (best is None or position >= best[0]):
                best = (position, index)
        return best[1] if best else self.carried_into(page)

    def block_section(self, page: int, order: int):
        """The account a block's rows belong to: the heading printed last before it in reading order, which must also
        be the heading printed last above it on the page. UNPLACED when the reading order and the page's geometry
        name different accounts (a table emitted before its own heading); the reading order where no box decides."""
        by_order = self.section_at(page, order)
        top = self.tops.get((page, order))
        if top is None or len(self.page_sections(page)) < 2:
            return by_order
        by_box = self.section_at_y(page, top)
        return by_order if by_box in (by_order, UNPLACED) else UNPLACED

    def position(self, page: int, locator: str | None) -> int | None:
        """The full-page block order a proposer row was read from; None for a reviewer's addition, or a row read
        by a failed full-page read beside a crop recovery."""
        match = re.match(r"^(?:g(\d+)c(\d+)/)?b(\d+)(?:t|l|r|$)", locator or "")
        if not match:
            return None
        if match.group(1) is None:
            return int(match.group(3))
        return self.crop_orders.get((page, int(match.group(2)), int(match.group(3))))


def plan_accounts(layouts, recoveries=()) -> AccountPlan:
    """The statement's account headings in reading order (see the module docstring)."""
    sections: list[AccountSection] = []
    switches, captions, titles, crop_orders, block_pages, tops, money = [], {}, {}, {}, {}, {}, set()
    for audit in recoveries or ():
        for crop in (audit or {}).get("crops", ()) if isinstance(audit, dict) else ():
            for item in (crop.get("lineage") or {}).get("blocks", ()):
                page = (crop.get("descriptor") or {}).get("page")
                if page is not None:
                    crop_orders[(page, item["crop_index"], item["crop_order"])] = item["fullpage_order"]
    def level(block) -> int:
        """A Markdown heading's level ("## ..." is 2), 0 for any other block."""
        match = re.match(r"^\s*(#{1,6})\s", str(block.content))
        return len(match.group(1)) if match else 0

    current = None
    for layout in layouts:
        caption = None
        last_heading = None  # (order, section index, Markdown level) of the last heading on this page
        money_since_heading = False
        ordered = [block for block in sorted(layout.blocks, key=lambda block: block.order)
                   if block.label not in _FURNITURE]
        for position, block in enumerate(ordered):
            block_pages.setdefault(layout.page, []).append(block.order)
            captions[(layout.page, block.order)] = caption
            tops[(layout.page, block.order)] = block.bbox[1] if block.bbox else None
            if _MONEY_TOKEN.search(str(block.content)):
                money.add((layout.page, block.order))
                money_since_heading = True
            text = block_heading_text(block)
            heading = parse_heading(text) if text else None
            if heading is not None and heading.number is None and _marketing_line(text):
                heading = None
            if heading is None:
                number = number_line(text) if text else None
                if (number and last_heading is not None and block.order - last_heading[0] <= 3
                        and sections[last_heading[1]].number is None):
                    sections[last_heading[1]].number = number
                    sections[last_heading[1]].number_from_line = True
                if text and (block.label in _CAPTION_LABELS or (
                        block.label == "text" and len(_clean(text)) <= 60 and not _SENTENCE.search(text))):
                    caption = _clean(text)
                title = _table_title(block)
                if title:
                    titles[(layout.page, block.order)] = title
                continue
            heading = Heading(layout.page, block.order, heading.kind, heading.title, heading.number,
                              heading.continued, heading.text)
            matches = [section for section in sections if _same_account(heading, section)]
            chosen = None
            if current is not None and sections[current] in matches:
                chosen = current
            elif matches:
                chosen = matches[-1].index
            elif (heading.number is None and last_heading is not None and block.order - last_heading[0] <= 2
                  and 0 < last_heading[2] < level(block) and sections[last_heading[1]].kind in (None, heading.kind)):
                # A product name printed as a lower heading directly under the account's own heading ("## Business
                # Regular Checking - XXXX1234" then "### Fabricated Checking Basic").
                chosen = last_heading[1]
            elif (heading.number is None and last_heading is not None and not money_since_heading
                  and sections[last_heading[1]].number is not None and not sections[last_heading[1]].number_from_line
                  and heading.kind in (None, sections[last_heading[1]].kind)
                  and not any(number_line(block_heading_text(later) or "") for later in ordered[position + 1:position + 4])):
                # A heading printing no identifier right under an identified account's heading, nothing printing money
                # between them and no "Account Number" line after it, is that account's product line or a slogan: a
                # statement that identifies its accounts prints an identifier for a real second one (review 13).
                chosen = last_heading[1]
            if chosen is None:
                chosen = len(sections)
                sections.append(AccountSection(chosen, heading.kind, heading.title, heading.number))
            section = sections[chosen]
            if section.number_from_line and heading.number is not None:
                # The title's own identifier replaces the one its number line printed, once (or confirms it): a later
                # heading of the same title printing yet another identifier is another account.
                if _number_key(heading.number) != section.key:
                    section.number = heading.number
                section.number_from_line = False
            section.headings.append(heading)
            if section.number is None and heading.number is not None:
                section.number = heading.number
            if section.kind is None and heading.kind is not None:
                section.kind = heading.kind
            switches.append((layout.page, block.order, chosen))
            current = chosen
            last_heading = (block.order, chosen, level(block))
            money_since_heading = False
            caption = None
    return AccountPlan(sections, switches, captions, crop_orders, block_pages, titles, tops, money)


UNPLACED = -1  # a row on a page printing several accounts whose place among them is not known
_SAME_LINE = 1 / 100  # two tops this close (0-1 of the page height) are one printed line


def assign_rows(plan: AccountPlan, merges) -> tuple[dict, dict]:
    """(kept, evidence): the account each kept row and each evidence item belongs to, keyed (page, locator); None
    for a row printed before every account heading, UNPLACED for one whose position among a page's accounts is not
    known. A proposer row takes its block's account (AccountPlan.block_section: reading order and geometry must
    agree). A reviewer's addition on a page printing several accounts takes the account of the proposer row it was
    added after (else before) and the account above its own box, and both must agree where both exist."""
    kept, evidence = {}, {}
    for merged in merges:
        items = list(merged.evidence)
        orders = [plan.position(merged.page, item.get("locator")) for item in items]
        sections = plan.page_sections(merged.page)
        for index, item in enumerate(items):
            order = orders[index]
            if order is not None:
                section = plan.block_section(merged.page, order)
            elif len(sections) <= 1:
                section = next(iter(sections)) if sections else None
            else:
                placed = set()
                if str(item.get("locator") or "").startswith("added"):
                    above = next((orders[i] for i in range(index - 1, -1, -1) if orders[i] is not None), None)
                    below = next((orders[i] for i in range(index + 1, len(items)) if orders[i] is not None), None)
                    neighbour = above if above is not None else below
                    if neighbour is not None:
                        placed.add(plan.block_section(merged.page, neighbour))
                box = (item.get("row") or {}).get("bbox") if isinstance(item.get("row"), dict) else None
                if isinstance(box, (list, tuple)) and len(box) == 4:
                    placed.add(plan.section_at_y(merged.page, box[1]))
                section = placed.pop() if len(placed) == 1 else UNPLACED
            evidence[(merged.page, item.get("locator"))] = section
        for row in merged.rows:
            kept[(row.page, row.locator)] = evidence.get((row.page, row.locator))
    return kept, evidence


# Figures an account's own section prints. The totals' extra wordings are those of member statements.
_OPENING = BEGIN_RE
_CLOSING = END_RE
_CREDITS = re.compile(TOTAL_CREDITS_RE.pattern + r"|\b(?:total\s+money\s+in|deposits\s+and\s+additions|"
                      r"total\s+deposits\s+for|credits?\s*\(s\)\s+this\s+period)\b", re.I)
_DEBITS = re.compile(TOTAL_DEBITS_RE.pattern + r"|\b(?:total\s+money\s+out|withdrawals\s+and\s+subtractions|"
                     r"total\s+withdrawals\s+for|debits?\s*\(s\)\s+this\s+period)\b", re.I)
_FIGURES = (("beginning_balance", _OPENING), ("ending_balance", _CLOSING),
            ("stated_total_credits", _CREDITS), ("stated_total_debits", _DEBITS))
_LEDGER_HEADER = re.compile(r"\b(?:date|description|transaction|details?|posted|particulars|check\s*(?:#|no))\b", re.I)
_MONEY_TOKEN = re.compile(r"\(?[-−]?\s?[$€£]?\s?\d{1,3}(?:,\d{3})*\.\d{2}\)?-?|\(?[-−]?\s?[$€£]?\s?\d+\.\d{2}\)?-?")


_LEAD_DATE = re.compile(r"^(?:\d{1,4}[/.-]\d{1,2}(?:[/.-]\d{2,4})?|[A-Za-z]{3,9}\.?\s+\d{1,2}(?:,?\s+\d{4})?)\s*$")
# A table cell printing nothing but a date, in any order a statement prints one ("03/05", "Mar 5", "05 Mar", "05MAR31");
# a month's name, never any word ("Share 01" is an account).
_CELL_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_CELL_DATE = re.compile(rf"^(?:\d{{1,4}}[/-]\d{{1,2}}(?:[/-]\d{{2,4}})?|\d{{1,2}}\.\d{{1,2}}\.\d{{2,4}}|"
                        rf"{_CELL_MONTH}\s*\d{{1,2}}(?:,?\s*\d{{2,4}})?|\d{{1,2}}\s*{_CELL_MONTH}(?:,?\s*\d{{2,4}})?)\s*$",
                        re.I)


def _label(text: str):
    """(field, end of the label) of the first figure label a cell or line prints as a figure's label, or None: at
    its start, after a printed date, or after another figure (a number, a sign, a colon or a bar), never inside a
    transaction's words ("... balance forward from savings ...")."""
    found = []
    for name, pattern in _FIGURES:
        for match in pattern.finditer(text):
            before = text[:match.start()].strip()
            if (not before or _LEAD_DATE.match(before) or before[-1].isdigit()
                    or before[-1] in ")|:+-=−–—%" or before.endswith("−")):
                found.append((match.start(), name, match.end()))
                break
    if not found:
        return None
    _, name, end = min(found)
    return name, end


def _money_after(text: str, start: int) -> Decimal | None:
    """The first money token after ``start`` and before the next figure label."""
    rest = text[start:]
    for match in _MONEY_TOKEN.finditer(rest):
        between = rest[:match.start()]
        if any(pattern.search(between) for _, pattern in _FIGURES):
            return None
        return parse_money(match.group(0).replace(" ", ""))
    return None


# Words a balance line can print after its label about when the balance stands.
_FIGURE_TAIL_WORDS = frozenset((
    "as of on at from to the this last previous prior statement period date forward brought carried end ending "
    "beginning opening closing jan january feb february mar march apr april may jun june jul july aug august sep sept "
    "september oct october nov november dec december").split())


def _cell_figures(grid: list[list[str]]):
    """(field, value) pairs a table grid prints: a label with its amount in one cell, beside it, or under a row of
    labels. A transaction table's header row labels columns, not figures."""
    rows = [[_clean(cell) for cell in row] for row in grid]
    in_ledger = False  # below a transaction table's header row: a label counts only when its cell prints no more
    for r, row in enumerate(rows):
        deduped = [cell for index, cell in enumerate(row) if cell and (index == 0 or cell != row[index - 1])]
        header = sum(bool(_LEDGER_HEADER.search(cell)) for cell in deduped) >= 2
        labels_only = deduped and all(_label(cell) and not _MONEY_TOKEN.search(cell) for cell in deduped)
        for c, cell in enumerate(row):
            if not cell or (c and cell == row[c - 1]):
                continue
            found = _label(cell)
            if found is None:
                continue
            if in_ledger and not header and any(
                    word.lower() not in _FIGURE_TAIL_WORDS
                    for word in re.findall(r"[A-Za-z]{2,}", _MONEY_TOKEN.sub(" ", cell[found[1]:]))):
                # A transaction whose words begin with a figure's label ("NEW BALANCE TRANSFER TO SAVINGS"); a balance
                # line printing when it stands ("Beginning Balance as of 03/01", "Balance Forward from previous
                # statement") is still the figure.
                continue
            inline = [] if header else list(_line_figures(cell))
            if inline:
                # A cell printing its figures after their labels, several to a cell ("Beginning Balance $5.00
                # 2 Total Deposits for 10.00 ... Ending Balance $15.00").
                yield from inline
                continue
            name, end = found
            value = _money_after(cell, end)
            if value is None and not header:
                right = next((other for other in row[c + 1:] if other and other != cell), None)
                if right is not None and _label(right) is None and _MONEY_TOKEN.fullmatch(right.replace(" ", "")):
                    value = parse_money(right.replace(" ", ""))
            if value is None and labels_only and r + 1 < len(rows) and c < len(rows[r + 1]):
                below = rows[r + 1][c]
                if below and _label(below) is None and _MONEY_TOKEN.fullmatch(below.replace(" ", "")):
                    value = parse_money(below.replace(" ", ""))
            if value is not None:
                yield name, value
        in_ledger = in_ledger or header


def _line_figures(text: str):
    for line in str(text).splitlines():
        line = _clean(line)
        position = 0
        while True:
            found = _label(line[position:])
            if found is None:
                break
            name, end = found
            value = _money_after(line, position + end)
            if value is not None:
                yield name, value
            position += end


def _printed(printed_pages, page):
    return printed_pages[page - 1] if printed_pages is not None and 0 < page <= len(printed_pages) else None


def _candidate(name: str, value: Decimal, printed) -> Decimal | None:
    """A figure as it counts: a total's magnitude; None when the page's text layer does not print it (a misread)."""
    if name in ("stated_total_credits", "stated_total_debits"):
        value = abs(value)
    if printed is not None and printed.amount_in_text_layer(value) is False:
        return None
    return value


def _account_named(plan: AccountPlan, text: str) -> int | None:
    """The one account a summary table's row names (by its number, else its title), or None."""
    heading = parse_heading(text)
    if heading is None:
        return None
    matches = [section.index for section in plan.sections if _same_account(heading, section)]
    return matches[0] if len(matches) == 1 else None


def _summary_header(grid) -> tuple[int, dict] | None:
    """(row index, {column: figure}) of a summary table's header row: the first row labelling at least two figure
    columns (Beginning Balance, Ending Balance, ...). A table whose header row also names a ledger column (Date,
    Description, ...: "Date | Description | Deposits and Credits | Withdrawals and Debits | Balance") is a ledger,
    never a summary table."""
    rows = [[_clean(cell) for cell in row] for row in grid]
    for start, header in enumerate(rows):
        # A row naming a ledger column before any figure header makes the table a ledger, whatever totals row it
        # prints further down ("Total Deposits | 0.00 | Total Withdrawals | 100.00" inside the ledger, review 10).
        if any(_LEDGER_HEADER.search(cell) for cell in header if cell):
            return None
        roles = {}
        for column, cell in enumerate(header):
            label = _label(cell) if cell and not _MONEY_TOKEN.search(cell) else None
            if label is not None:
                roles[column] = label[0]
        if len(set(roles.values())) >= 2:
            # A summary table labels an account's balance; a ledger's figure columns are credits and debits only
            # ("Day | Item | Deposits and Credits | Withdrawals and Debits | Balance"), and its rows print dates: any
            # cell of any row, above the header too (a ledger continued without its header, ending in a totals row;
            # "05 Mar"; a date column that is not the first), a header is never the table's last row, and it is the
            # table's first row or follows only a title row (reviews 12, 13).
            titled = start == 1 and len([cell for cell in rows[0] if cell]) == 1
            dated = any(_CELL_DATE.match(cell) for position, row in enumerate(rows) if position != start
                        for cell in row if cell)
            if (start == len(rows) - 1 or (start > 0 and not titled) or dated
                    or not {"beginning_balance", "ending_balance"} & set(roles.values())):
                return None
            return start, roles
    return None


_BALANCE_CAPTION = re.compile(r"\bbalances?\b", re.I)
# Words naming transactions (a balance grid's header can say "Amount": that word is neither).
_TRANSACTION_CAPTION = re.compile(r"\b(?:deposits?|withdrawals?|debits?|credits?|checks?|cheques?|description|"
                                  r"transactions?|payments?|fees?|charges?|items?|transfers?|adjustments?|activity|"
                                  r"purchases?|corrections?|overdrafts?)\b", re.I)


def balance_table_blocks(layout) -> frozenset:
    """Block orders of a page's tables the page prints as balances, never transactions: a table titled or captioned
    with balances and nothing of transactions ("Daily Balance", "Daily Ledger Balances"), or whose header row names
    a balance column and no transaction column ("Date | Balance | Date | Balance")."""
    found, caption = set(), None
    for block in sorted(layout.blocks, key=lambda block: block.order):
        if block.label in _FURNITURE:
            continue
        grid = _grid(block)  # an HTML table, or a Markdown table printed as a text block
        if grid:
            header = " ".join(_clean(cell) for cell in grid[0] if _clean(cell))
            named = [text for text in (_table_title(block), caption, header) if text]
            # Every name the table prints or is printed under must be free of transactions; one of them names balances.
            if (any(_BALANCE_CAPTION.search(text) for text in named)
                    and not any(_TRANSACTION_CAPTION.search(text) for text in named)):
                found.add(block.order)
            caption = None
            continue
        text = block_heading_text(block)
        # A caption is the line printed right above the table: a heading or a short line printing no figure (a
        # "Beginning Balance $1,000.00" or "Ending balance on 03/31" line is a figure, never a caption).
        caption = (_clean(text) if text and not _MONEY_TOKEN.search(text) and _label(_clean(text)) is None and (
            block.label in _CAPTION_LABELS or (
                block.label == "text" and len(_clean(text)) <= 60 and not _SENTENCE.search(text))) else None)
    return frozenset(found)


def summary_table_rows(plan: AccountPlan, layouts, descriptions: dict) -> set:
    """The keys of ``descriptions`` ((page, locator) -> a row's words) read from a summary table: a table whose
    header row labels at least two figure columns and no ledger column (_summary_header), the row's words naming
    one of the statement's accounts. Such a row is no account's transaction, and no sign of an account whose
    heading went unrecognized."""
    blocks = {(layout.page, block.order) for layout in layouts for block in layout.blocks
              if block.label not in _FURNITURE and _summary_header(_grid(block)) is not None}
    return {key for key, description in descriptions.items()
            if (key[0], plan.position(key[0], key[1])) in blocks
            and _account_named(plan, _MONEY_TOKEN.sub(" ", str(description or ""))) is not None}


def summary_table_figures(plan: AccountPlan, layouts, printed_pages=None) -> dict:
    """What a statement's summary table prints for each account: a table whose header row labels at least two
    figure columns (Beginning Balance, Ending Balance, ...) and whose rows each name one account. {account index:
    {field: [(value, page)]}}; a row naming no account, or several, gives nothing. Position is never a column's
    meaning: only a printed label is."""
    found: dict[int, dict] = {}
    for layout in layouts:
        printed = _printed(printed_pages, layout.page)
        for block in sorted(layout.blocks, key=lambda block: block.order):
            grid = _grid(block) if block.label not in _FURNITURE else []
            rows = [[_clean(cell) for cell in row] for row in grid]
            found_header = _summary_header(grid)
            if found_header is None:
                continue
            start, roles = found_header
            for row in rows[start + 1:]:
                name = " ".join(dict.fromkeys(cell for column, cell in enumerate(row)
                                              if cell and column not in roles
                                              and not _MONEY_TOKEN.fullmatch(cell.replace(" ", ""))))
                index = _account_named(plan, name) if name else None
                if index is None:
                    continue
                for column, field_name in roles.items():
                    cell = row[column].replace(" ", "") if column < len(row) else ""
                    if cell and _MONEY_TOKEN.fullmatch(cell):
                        value = _candidate(field_name, parse_money(cell), printed)
                        if value is not None:
                            found.setdefault(index, {}).setdefault(field_name, []).append((value, layout.page))
    return found


def section_figures(plan: AccountPlan, index: int, layouts, printed_pages=None, summary=None) -> dict:
    """The figures account ``index`` prints: {field: {"value", "values", "pages", "source"}}. Its own section's first
    opening balance and last closing balance (a sub-ledger printed inside the section cannot move them: the account's
    own arithmetic decides whether they are its), a total only when printed once over; else what a summary table
    prints for it (``summary``, summary_table_figures). One the page's text layer does not print (a misread) is no
    candidate."""
    candidates: dict[str, list] = {}
    for layout in layouts:
        printed = _printed(printed_pages, layout.page)
        for block in sorted(layout.blocks, key=lambda block: block.order):
            if block.label in _FURNITURE or plan.section_at(layout.page, block.order) != index:
                continue
            grid = _grid(block)
            for name, value in (list(_cell_figures(grid)) if grid else list(_line_figures(block.content))):
                value = _candidate(name, value, printed)
                if value is not None:
                    candidates.setdefault(name, []).append((value, layout.page))
    tabled = (summary or {}).get(index, {})
    figures = {}
    for name in dict.fromkeys((*candidates, *tabled)):
        own, table = candidates.get(name, []), tabled.get(name, [])
        values = sorted({value for value, _ in own})
        table_values = sorted({value for value, _ in table})
        if own:
            value = (own[0][0] if name == "beginning_balance" else own[-1][0] if name == "ending_balance"
                     else values[0] if len(values) == 1 else None)
            source = "section"
        else:
            value = table_values[0] if len(table_values) == 1 else None
            source = "summary_table"
        figures[name] = {"value": value, "values": [str(v) for v in values or table_values], "source": source,
                         "pages": sorted({page for _, page in own or table}),
                         "summary_table_values": [str(v) for v in table_values]}
    return figures


# A date printed anywhere on a line ("03/10", "3-10-31", "10.03.2031", "Mar 10", "10 Mar", "10MAR", "MAR10"); a dotted
# pair without its year is an amount.
_MONTH3 = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
_LINE_DATE = re.compile(rf"(?<![\d/.-])(?:\d{{1,4}}[/-]\d{{1,2}}(?:[/-]\d{{2,4}})?(?![\d/-])|"
                        rf"\d{{1,2}}\.\d{{1,2}}\.\d{{2,4}}(?![\d.])|"
                        rf"{_MONTH3}[a-z]*\.?\s+\d{{1,2}}\b|\b\d{{1,2}}\s+{_MONTH3}[a-z]*\b|"
                        rf"\b\d{{1,2}}{_MONTH3}(?:\d{{2}}|\d{{4}})?\b|\b{_MONTH3}\d{{1,2}}\b)", re.I)


def section_activity_lines(plan: AccountPlan, index: int, layouts) -> int:
    """How many lines of account ``index``'s own section read like a transaction: a date anywhere ("Description |
    Date | Amount" tables print it second), an amount, and no figure label (an opening or closing balance line is no
    activity). An account printing one is not shown to be idle, whatever its opening and closing balances say."""
    count = 0
    for layout in layouts:
        for block in layout.blocks:
            if block.label in _FURNITURE or plan.section_at(layout.page, block.order) != index:
                continue
            grid = _grid(block)
            lines = [" ".join(_clean(cell) for cell in row if _clean(cell)) for row in grid] if grid else \
                [_clean(line) for line in str(block.content).splitlines()]
            count += sum(1 for line in lines
                         if _LINE_DATE.search(line) and _MONEY_TOKEN.search(line) and _label(line) is None)
    return count


_LISTING = re.compile(
    r"\b(?:deposits?|withdrawals?|debits?|credits?|checks?|cheques?|drafts?|payments?|items?)\b.*"
    r"\b(?:summary|recap|listing|list|cleared|paid)\b|\bsummary\s+of\s+(?:deposits?|withdrawals?|debits?|credits?|"
    r"checks?|cheques?|drafts?|payments?)\b", re.I)


def listing_echoes(rows, plan: AccountPlan) -> set:
    """(page, locator) of rows printed in a listing ("Withdrawal Summary", "Checks Cleared") that repeats the
    ledger: every dated row of the listing's block matches a distinct ledger row printing a running balance, by
    date and amount. A listing that repeats nothing is the ledger itself (a statement printing its deposits and
    its withdrawals as separate lists), and it stays."""
    blocks: dict[tuple, list] = {}
    for row in rows:
        order = plan.position(row.page, row.locator)
        caption = " ".join(filter(None, (plan.captions.get((row.page, order)), plan.titles.get((row.page, order)))))
        if order is not None and caption and _LISTING.search(caption):
            blocks.setdefault((row.page, order), []).append(row)
    if not blocks:
        return set()
    listed = {(row.page, row.locator) for group in blocks.values() for row in group}
    ledger: dict[tuple, int] = {}
    for row in rows:
        if (row.page, row.locator) not in listed and row.balance is not None and row.date:
            key = (row.date, row.amount)
            ledger[key] = ledger.get(key, 0) + 1
    echoes = set()
    for group in blocks.values():
        wanted: dict[tuple, int] = {}
        for row in group:
            if not row.date:
                wanted = None
                break
            wanted[(row.date, row.amount)] = wanted.get((row.date, row.amount), 0) + 1
        if wanted and all(ledger.get(key, 0) >= count for key, count in wanted.items()):
            for key, count in wanted.items():
                ledger[key] -= count
            echoes.update((row.page, row.locator) for row in group)
    return echoes
