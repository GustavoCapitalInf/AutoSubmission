"""layout/signals.py — the closed signal vocabulary, the three-language
lexicons and the minimal token-shape grammars the document classifier reads
(Phase 2.2 cell C, `P22-CLASSIFY.md` §4; plan §J.2; research memo R.3).

What lives here and why
-----------------------
* `SIGNALS`: the closed names a verdict may cite. A signal name is a
  vocabulary word, never document text.
* `LEXICONS`: closed EN / FR / ES phrase lists per signal family. Every entry
  is a piece of STATEMENT FURNITURE (a label, a salutation, a column word),
  NEVER an issuer string — `tests/test_layout_signals.py` runs the OQ2
  issuer-marker scan over this package with an EMPTY register, so an issuer
  name added here fails the build. Matching folds case, accents and
  typographic apostrophes and respects word boundaries.
* Token shapes: money (with cents), dates (four-digit year and short forms,
  three languages of month names), MICR E-13B-shaped digit groups, and
  `Page X of Y` markers in three languages.

Why this module carries its OWN shape grammars
----------------------------------------------
The platform's grammars — `analysis/money.py` (the surveyed money grammar)
and `analysis/date_tokens.py` (the date-token grammar) — live in `analysis/`,
and `layout/` may import only the standard library and `evidence`
(umbrella D1; `tests/test_layout_boundary.py`). They cannot be reused
without crossing a boundary that is pinned shut, so the shapes here are a
deliberately MINIMAL, fixtured subset: enough to say "this line carries a
date and a money figure", never enough to publish a value. The LayoutModel
(Phase 2.4) is where the two sets of grammars are unified; until then a
divergence between them is a classifier finding, not a financial one.

Zero-activity declaration
-------------------------
`ZERO_ACTIVITY_PATTERNS` are the literal patterns of
`analysis/sibling_omission.py::DORMANCY_DECLARATIONS` (`DORMANT_RE`,
`NO_ACTIVITY_RE`), copied BY HAND — the card forbids the import, and the
signals test pins the two lists equal so they cannot drift apart silently.

Everything here is a pure function of its string argument: no state, no
clock, no randomness, results ordered by position.
"""
from __future__ import annotations

import functools
import re
import unicodedata
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

__all__ = [
    "DATE_RE",
    "DateToken",
    "LANGUAGE_CODES",
    "LEXICONS",
    "LEXICON_MIN_DISTINCT",
    "LEXICON_STRONG",
    "LexiconHit",
    "MICR_SYMBOLS",
    "MONEY_RE",
    "MoneyToken",
    "PAGE_MARKER_PATTERNS",
    "PageMarker",
    "RANGE_CONNECTORS",
    "SIGNALS",
    "ZERO_ACTIVITY_PATTERNS",
    "find_dates",
    "find_lexicon",
    "find_money",
    "find_page_marker",
    "find_zero_activity",
    "fold",
    "is_micr_shaped",
    "money_cents",
]

LANGUAGE_CODES: tuple[str, ...] = ("en", "fr", "es")

#: The closed vocabulary of signal names an `EvidenceRef` may carry.
SIGNALS: tuple[str, ...] = (
    "file_invalid_fact",
    "period_expression",
    "opening_balance_label",
    "closing_balance_label",
    "zero_activity_declaration",
    "table_run",
    "table_alignment",
    "short_ledger",
    "balance_pair_coincides",
    "running_balance",
    "page_marker",
    "page_gap",
    "page_missing",
    "first_page_missing",
    "balance_discontinuity",
    "table_truncated",
    "micr_shape",
    "micr_band",
    "cheque_aspect",
    "cheque_lexicon",
    "void_lexicon",
    "deposit_slip_lexicon",
    "letter_lexicon",
    "card_lexicon",
    "loan_lexicon",
    "brokerage_lexicon",
    "deposit_lexicon",
    "screenshot_frame",
    "reverse_chronology",
    "pending_row",
    "illegible_floor",
)


# ---------------------------------------------------------------------------
# text folding (length-preserving, so spans map back to the source text)
# ---------------------------------------------------------------------------

_APOSTROPHES = "’‘ʼ`´"
#: No-break space, narrow no-break space, thin space — the FR / ES thousands
#: separators as PDFs and OCR engines emit them. Built by code point so the
#: source never depends on an invisible character surviving an editor.
_NBSP = chr(0xA0)
_NNBSP = chr(0x202F)
_THIN = chr(0x2009)
_SPACES = " " + _NBSP + _NNBSP + _THIN


def _fold_char(ch: str) -> str:
    if ch in _APOSTROPHES:
        return "'"
    if ch in _SPACES:
        return " "
    decomposed = unicodedata.normalize("NFKD", ch)
    base = decomposed[0] if decomposed else ch
    if unicodedata.combining(base):
        base = ch
    lowered = base.lower()
    return lowered if len(lowered) == 1 else base


#: A translation table over the code points a statement page can carry
#: (Latin-1 Supplement through the enclosed alphanumerics that hold the
#: MICR symbols), built once from `_fold_char` so the fast path and the
#: per-character path agree by construction.
_FOLD_TABLE: dict[int, str] = {
    code: _fold_char(chr(code)) for code in range(0x80, 0x2500) if _fold_char(chr(code)) != chr(code)
}


@functools.lru_cache(maxsize=8192)
def fold(text: str) -> str:
    """Lower-case, accent-stripped, apostrophe-normalised, LENGTH-PRESERVING
    (one output character per input character), so an offset into the
    folded text is the same offset into the source text. Memoised: the
    classifier folds the same line once per signal family, and a cache of a
    pure function is still a pure function."""
    fast = text.translate(_FOLD_TABLE).lower()
    if len(fast) == len(text):
        return fast
    return "".join(_fold_char(ch) for ch in text)


# ---------------------------------------------------------------------------
# lexicons (closed; furniture only; never an issuer string)
# ---------------------------------------------------------------------------

def _lexicon(**by_language: tuple[str, ...]) -> Mapping[str, tuple[str, ...]]:
    return MappingProxyType({lang: tuple(by_language[lang]) for lang in LANGUAGE_CODES})


LEXICONS: Mapping[str, Mapping[str, tuple[str, ...]]] = MappingProxyType({
    # A printed statement period. Fires only beside a date token (see
    # document_class), or as a two-date range with a connector.
    "period_phrase": _lexicon(
        en=("statement period", "statement date", "for the period", "period covered", "period ending",
            "billing period", "activity period", "statement of account for", "statement from"),
        fr=("période du", "période de relevé", "période couverte", "relevé du", "date du relevé",
            "période"),
        es=("periodo del", "período del", "periodo de facturación", "fecha del estado", "estado de cuenta al",
            "periodo", "período"),
    ),
    # Balance labels. The qualified forms ("closing ACCOUNT balance",
    # "opening LEDGER balance") are the same furniture with a noun between
    # the adjective and "balance"; a lexicon of phrases carries each form.
    "opening_balance": _lexicon(
        en=("beginning balance", "opening balance", "previous balance", "balance forward", "balance brought forward",
            "starting balance", "prior balance", "balance at beginning", "beginning of period balance",
            "opening account balance", "beginning account balance", "opening statement balance",
            "beginning statement balance", "previous statement balance", "opening ledger balance",
            "beginning ledger balance", "balance at start", "balance at the beginning", "balance last statement",
            "last statement balance"),
        fr=("solde d'ouverture", "solde précédent", "solde reporté", "solde au début", "solde de début",
            "solde antérieur", "ancien solde", "solde à l'ouverture", "solde de début de période"),
        es=("saldo inicial", "saldo anterior", "saldo al inicio", "saldo de apertura", "saldo previo",
            "saldo inicial del periodo"),
    ),
    "closing_balance": _lexicon(
        en=("ending balance", "closing balance", "new balance", "balance at end", "end of period balance",
            "final balance", "ending daily balance", "closing daily balance", "closing account balance",
            "ending account balance", "closing statement balance", "ending statement balance",
            "closing ledger balance", "ending ledger balance", "balance at close", "balance at closing",
            "balance at the end", "balance this statement", "this statement balance", "statement ending balance"),
        fr=("solde de clôture", "solde final", "solde à la fin", "nouveau solde", "solde de fin", "solde de fermeture",
            "solde à la fermeture", "solde à la clôture", "solde de fin de période"),
        es=("saldo final", "saldo al cierre", "nuevo saldo", "saldo de cierre", "saldo al final",
            "saldo final del periodo"),
    ),
    # Cheque furniture: the payee line. One hit is specific enough.
    "cheque": _lexicon(
        en=("pay to the order of", "pay to the order"),
        fr=("payez à l'ordre de", "à l'ordre de"),
        es=("páguese a la orden de", "a la orden de"),
    ),
    "void": _lexicon(
        en=("void", "voided"),
        fr=("nul", "annulé", "annule"),
        es=("nulo", "anulado", "cancelado"),
    ),
    "deposit_slip": _lexicon(
        en=("deposit ticket", "deposit slip", "less cash received", "net deposit", "total from other side",
            "cash received", "currency", "coin"),
        fr=("bordereau de dépôt", "dépôt total", "monnaie", "billets", "moins argent reçu"),
        es=("boleta de depósito", "comprobante de depósito", "ficha de depósito", "depósito total", "monedas",
            "billetes", "efectivo recibido"),
    ),
    "letter": _lexicon(
        en=("dear", "sincerely", "yours truly", "to whom it may concern", "we are writing", "this letter",
            "please be advised", "kind regards", "best regards", "notice of"),
        fr=("madame, monsieur", "cordialement", "veuillez agréer", "nous vous informons", "cher client",
            "chère cliente", "salutations distinguées", "avis de"),
        es=("estimado", "estimada", "atentamente", "le informamos", "por medio de la presente", "cordialmente",
            "aviso de"),
    ),
    "card": _lexicon(
        en=("minimum payment", "payment due", "credit limit", "available credit", "cash advance",
            "annual percentage rate", "minimum amount due", "credit line"),
        fr=("paiement minimum", "crédit disponible", "limite de crédit", "date d'échéance", "avance de fonds",
            "taux annuel"),
        es=("pago mínimo", "límite de crédito", "crédito disponible", "fecha de vencimiento", "adelanto de efectivo",
            "tasa anual"),
    ),
    "loan": _lexicon(
        en=("principal balance", "principal", "escrow", "interest paid", "loan number", "amortization",
            "loan balance", "interest rate", "payment due"),
        fr=("capital restant", "capital", "intérêts", "amortissement", "prêt", "solde du prêt", "échéance"),
        es=("capital pendiente", "capital", "intereses", "amortización", "préstamo", "saldo del préstamo", "cuota"),
    ),
    "brokerage": _lexicon(
        en=("holdings", "positions", "market value", "portfolio", "securities", "unrealized gain", "cost basis"),
        fr=("valeur marchande", "portefeuille", "titres", "positions", "placements"),
        es=("valor de mercado", "cartera", "posiciones", "valores", "inversiones"),
    ),
    # The deposit-account axis (account_kind only; never decides a kind).
    "deposit_account": _lexicon(
        en=("checking", "savings", "chequing", "deposits", "withdrawals", "checks paid", "money market"),
        fr=("compte chèques", "compte d'épargne", "dépôts", "retraits", "compte courant"),
        es=("cuenta corriente", "cuenta de ahorros", "depósitos", "retiros", "cuenta de cheques"),
    ),
    "pending": _lexicon(
        en=("pending",),
        fr=("en attente", "en cours"),
        es=("pendiente", "pendientes"),
    ),
})

#: How many DISTINCT (non-overlapping) phrases a sub-kind lexicon must hit
#: before it counts, and which of its phrases are STRONG (at least one strong
#: hit is required where a strong set is declared). A single generic word
#: ("interest paid", "coin", "positions") is never enough on its own.
LEXICON_MIN_DISTINCT: Mapping[str, int] = MappingProxyType({
    "cheque": 1, "void": 1, "deposit_slip": 2, "letter": 2, "card": 2, "loan": 2, "brokerage": 2,
    "deposit_account": 1, "pending": 1, "period_phrase": 1, "opening_balance": 1, "closing_balance": 1,
})
LEXICON_STRONG: Mapping[str, frozenset[str]] = MappingProxyType({
    "deposit_slip": frozenset({"deposit ticket", "deposit slip", "less cash received", "net deposit",
                               "total from other side", "bordereau de dépôt", "boleta de depósito",
                               "comprobante de depósito", "ficha de depósito"}),
    # Card STRONG phrases are the ones a revolving-credit summary prints and a
    # deposit statement's overdraft line-of-credit box does not: a minimum
    # payment and a cash advance. "credit limit" / "available credit" /
    # "credit line" / the APR are line-of-credit furniture too, so they stay
    # weak (they count toward the two distinct phrases, never alone).
    "card": frozenset({"minimum payment", "minimum amount due", "cash advance", "paiement minimum", "avance de fonds",
                       "pago mínimo", "adelanto de efectivo"}),
    "loan": frozenset({"principal balance", "principal", "escrow", "amortization", "loan number", "loan balance",
                       "capital restant", "amortissement", "prêt", "solde du prêt", "capital pendiente",
                       "amortización", "préstamo", "saldo del préstamo"}),
    "brokerage": frozenset({"holdings", "market value", "portfolio", "positions", "valeur marchande", "portefeuille",
                            "titres", "valor de mercado", "cartera", "posiciones"}),
    "letter": frozenset({"dear", "sincerely", "yours truly", "to whom it may concern", "we are writing",
                         "madame, monsieur", "cordialement", "veuillez agréer", "cher client", "chère cliente",
                         "estimado", "estimada", "atentamente", "por medio de la presente", "cordialmente"}),
})

#: Words that join two dates into a range ("from A to B", "du A au B").
RANGE_CONNECTORS: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "en": ("to", "through", "thru", "until", "-", "–", "—"),
    "fr": ("au", "à", "-", "–"),
    "es": ("al", "a", "hasta", "-", "–"),
})


@dataclass(frozen=True)
class LexiconHit:
    name: str
    language: str
    phrase: str
    start: int
    end: int


def _compile_lexicon(by_language: Mapping[str, tuple[str, ...]]) -> tuple[re.Pattern[str], dict[str, tuple[tuple[str, str], ...]]]:
    """ONE alternation per lexicon, longest phrase first, over folded text;
    a folded phrase maps back to every (language, phrase) that folds to it,
    so a word two languages share votes for both."""
    entries: dict[str, list[tuple[str, str]]] = {}
    for language in LANGUAGE_CODES:
        for phrase in by_language[language]:
            entries.setdefault(fold(phrase), []).append((language, phrase))
    alternatives = sorted(entries, key=lambda folded: (-len(folded), folded))
    body = "|".join(r"\s+".join(re.escape(part) for part in alt.split(" ")) for alt in alternatives)
    pattern = re.compile(r"(?<![a-z0-9])(?:" + body + r")(?![a-z0-9])")
    return pattern, {folded: tuple(pairs) for folded, pairs in entries.items()}


_LEXICON_RES: dict[str, tuple[re.Pattern[str], dict[str, tuple[tuple[str, str], ...]]]] = {
    name: _compile_lexicon(by_language) for name, by_language in LEXICONS.items()
}
_WHITESPACE_RUN = re.compile(r"\s+")


def find_lexicon(text: str, name: str) -> list[LexiconHit]:
    """Every occurrence of a phrase of lexicon `name` in `text`, in text
    order; at one position the LONGEST phrase wins, and a phrase two
    languages share yields one hit per language (language order)."""
    folded = fold(text)
    pattern, entries = _LEXICON_RES[name]
    hits: list[LexiconHit] = []
    for match in pattern.finditer(folded):
        key = _WHITESPACE_RUN.sub(" ", match.group(0))
        for language, phrase in entries[key]:
            hits.append(LexiconHit(name, language, phrase, match.start(), match.end()))
    return hits


# ---------------------------------------------------------------------------
# zero-activity declaration (sibling-omission vocabulary, copied by hand)
# ---------------------------------------------------------------------------

#: Copied by hand from `analysis/sibling_omission.py` (`DORMANT_RE` and
#: `NO_ACTIVITY_RE`, the members of `DORMANCY_DECLARATIONS`), in that order.
#: `tests/test_layout_signals.py` pins pattern text and flags equal.
ZERO_ACTIVITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"No\s+Transactions\s+This\s+Period", re.IGNORECASE),
    re.compile(r"There were no transactions this period", re.IGNORECASE),
)


def find_zero_activity(text: str) -> tuple[int, int] | None:
    for pattern in ZERO_ACTIVITY_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.start(), match.end()
    return None


# ---------------------------------------------------------------------------
# money
# ---------------------------------------------------------------------------

_SPACE_GROUP = "[" + _SPACES + "]"
_EN_BODY = r"(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}"
_FR_BODY = r"(?:\d{1,3}(?:" + _SPACE_GROUP + r"\d{3})+|\d{1,3}(?:\.\d{3})+|\d+),\d{2}"

#: Money with cents. EN grouping (`1,234.56`), FR / ES grouping (`1 234,56`,
#: `1.234,56`), an optional currency mark, a sign as a leading minus, a
#: trailing minus, parentheses, or a CR/DR suffix. Refuses a token that is
#: part of a longer number and a percentage.
MONEY_RE: re.Pattern[str] = re.compile(
    r"(?<![\d.,])"
    r"(?P<open>\()?(?(open)\s?)(?P<sign>[-−])?(?(sign)\s?)"
    r"(?P<currency>(?:US|CA|C)?\$|€|£)?(?(currency)\s?)"
    r"(?P<body>" + _EN_BODY + r"|" + _FR_BODY + r")"
    r"(?P<close>\))?"
    r"(?![\d%])(?!\s%)"
    r"(?:\s?(?P<suffix>CR|DR|-|−)(?![A-Za-z0-9]))?"
)


@dataclass(frozen=True)
class MoneyToken:
    start: int
    end: int
    cents: int


def _body_to_cents(body: str) -> int:
    if body[-3] == ",":                      # FR / ES decimal comma
        integer = re.sub("[" + _SPACES + ".]", "", body[:-3])
    else:                                    # EN decimal point
        integer = body[:-3].replace(",", "")
    return int(integer) * 100 + int(body[-2:])


def find_money(text: str) -> list[MoneyToken]:
    tokens: list[MoneyToken] = []
    for match in MONEY_RE.finditer(text):
        cents = _body_to_cents(match.group("body"))
        negative = bool(match.group("sign")) or bool(match.group("open") and match.group("close")) \
            or match.group("suffix") in ("-", "−")
        tokens.append(MoneyToken(match.start(), match.end(), -cents if negative else cents))
    return tokens


def money_cents(text: str) -> int | None:
    """`text` as ONE money token (whole string, whitespace allowed around it)."""
    stripped = text.strip()
    tokens = find_money(stripped)
    if len(tokens) == 1 and tokens[0].start == 0 and tokens[0].end == len(stripped):
        return tokens[0].cents
    return None


# ---------------------------------------------------------------------------
# dates
# ---------------------------------------------------------------------------

_MONTH_STEMS: dict[str, int] = {
    "jan": 1, "janv": 1, "ene": 1,
    "feb": 2, "fev": 2, "fevr": 2,
    "mar": 3, "mars": 3,
    "apr": 4, "avr": 4, "abr": 4,
    "may": 5, "mai": 5,
    "jun": 6, "juin": 6,
    "jul": 7, "juil": 7,
    "aug": 8, "aout": 8, "ago": 8,
    "sep": 9, "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12, "dic": 12,
}
_MONTH = "(?:" + "|".join(sorted(_MONTH_STEMS, key=len, reverse=True)) + ")"

#: Date shapes over FOLDED text: ISO, numeric with a repeated separator and
#: a two- or four-digit year, a short month/day pair with a slash, and the
#: three languages' month-name forms (day-month-year and month-day-year).
DATE_RE: re.Pattern[str] = re.compile(
    r"(?<![\d/.-])(?P<iso_y>\d{4})-(?P<iso_m>\d{2})-(?P<iso_d>\d{2})(?![\d/.-])"
    r"|(?<![\d/.-])(?P<n3_a>\d{1,2})(?P<sep>[/.-])(?P<n3_b>\d{1,2})(?P=sep)(?P<n3_y>\d{4}|\d{2})(?![\d/.-])"
    r"|(?<![\d/.-])(?P<n2_a>\d{1,2})/(?P<n2_b>\d{1,2})(?![\d/.-])"
    r"|(?<![a-z])(?P<mdy_m>" + _MONTH + r")[a-z]*\.?\s+(?P<mdy_d>\d{1,2})(?:st|nd|rd|th)?,?(?:\s+(?P<mdy_y>\d{4}))?(?![\d])"
    r"|(?<![\d])(?P<dmy_d>\d{1,2})(?:er|o|°|º)?\s+(?:de\s+)?(?P<dmy_m>" + _MONTH + r")[a-z]*\.?"
    r"(?:,?\s+(?:de\s+)?(?P<dmy_y>\d{4}))?(?![a-z\d])"
)


@dataclass(frozen=True)
class DateToken:
    start: int
    end: int
    kind: str              # iso | numeric | short | named
    year: int | None
    first: int             # the first numeric part (or the day for named forms)
    second: int            # the second numeric part (or the month for named forms)
    day_first: bool

    def ymd(self) -> tuple[int | None, int, int]:
        if self.kind in ("iso", "named"):
            return self.year, self.second, self.first
        a, b = self.first, self.second
        if a > 12:
            day, month = a, b
        elif b > 12:
            month, day = a, b
        elif self.day_first:
            day, month = a, b
        else:
            month, day = a, b
        return self.year, month, day

    def sort_key(self) -> tuple[int, int, int]:
        year, month, day = self.ymd()
        return (year or 0, month, day)


def _valid_md(a: int, b: int) -> bool:
    return 1 <= a <= 31 and 1 <= b <= 31 and (a <= 12 or b <= 12)


def _year(raw: str) -> int:
    value = int(raw)
    if len(raw) == 2:
        value += 2000
    return value


def find_dates(text: str, *, day_first: bool = False) -> list[DateToken]:
    folded = fold(text)
    tokens: list[DateToken] = []
    for match in DATE_RE.finditer(folded):
        g = match.groupdict()
        if g["iso_y"]:
            month, day = int(g["iso_m"]), int(g["iso_d"])
            if not (1 <= month <= 12 and 1 <= day <= 31):
                continue
            tokens.append(DateToken(match.start(), match.end(), "iso", int(g["iso_y"]), day, month, day_first))
        elif g["n3_a"]:
            a, b = int(g["n3_a"]), int(g["n3_b"])
            if not _valid_md(a, b):
                continue
            # The dotted form (`05.03.2031`) is a day-first convention wherever
            # it is printed; the slash and dash forms follow the caller's hint.
            tokens.append(DateToken(match.start(), match.end(), "numeric", _year(g["n3_y"]), a, b,
                                    day_first or g["sep"] == "."))
        elif g["n2_a"]:
            a, b = int(g["n2_a"]), int(g["n2_b"])
            if not _valid_md(a, b):
                continue
            tokens.append(DateToken(match.start(), match.end(), "short", None, a, b, day_first))
        elif g["mdy_m"]:
            day = int(g["mdy_d"])
            if not 1 <= day <= 31:
                continue
            year = int(g["mdy_y"]) if g["mdy_y"] else None
            tokens.append(DateToken(match.start(), match.end(), "named", year, day, _MONTH_STEMS[g["mdy_m"]], day_first))
        elif g["dmy_d"]:
            day = int(g["dmy_d"])
            if not 1 <= day <= 31:
                continue
            year = int(g["dmy_y"]) if g["dmy_y"] else None
            tokens.append(DateToken(match.start(), match.end(), "named", year, day, _MONTH_STEMS[g["dmy_m"]], day_first))
    return tokens


# ---------------------------------------------------------------------------
# MICR E-13B shape
# ---------------------------------------------------------------------------

#: The four E-13B symbols (transit, amount, on-us, dash) and the characters
#: OCR engines commonly read them as.
MICR_SYMBOLS: frozenset[str] = frozenset("⑆⑇⑈⑉:;|'\".-cCaA")
_MICR_MIN_GROUPS = 2
_MICR_MIN_LONGEST_GROUP = 6
_MICR_MIN_DIGITS = 14
_MICR_MAX_SYMBOLS = 6


def is_micr_shaped(text: str) -> bool:
    """A line made of long digit groups and a few MICR symbols (at least
    one: the transit / on-us marks, or the characters OCR reads them as):
    a routing/transit group, an account group, a cheque-number group. Any
    letter, slash or other character disqualifies the line; so does a bare
    run of numbers with no symbol at all (a statement's own account and
    reference numbers look like that)."""
    stripped = text.strip()
    if not stripped:
        return False
    groups = re.findall(r"\d+", stripped)
    if len(groups) < _MICR_MIN_GROUPS:
        return False
    if max(len(group) for group in groups) < _MICR_MIN_LONGEST_GROUP:
        return False
    if sum(len(group) for group in groups) < _MICR_MIN_DIGITS:
        return False
    others = [ch for ch in stripped if not (ch.isdigit() or ch.isspace())]
    if not others or len(others) > _MICR_MAX_SYMBOLS:
        return False
    return all(ch in MICR_SYMBOLS for ch in others)


# ---------------------------------------------------------------------------
# page markers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PageMarker:
    number: int
    total: int
    language: str
    start: int
    end: int


#: `Page X of Y` in three languages over FOLDED text; tried in this order,
#: the first match wins (a `page 1/3` form is tagged `en`).
PAGE_MARKER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("en", re.compile(r"(?<![a-z])page\s*:?\s*(\d{1,4})\s*(?:of|/)\s*(\d{1,4})(?!\d)")),
    ("fr", re.compile(r"(?<![a-z])page\s*:?\s*(\d{1,4})\s*(?:de|sur|/)\s*(\d{1,4})(?!\d)")),
    ("es", re.compile(r"(?<![a-z])pagina\s*:?\s*(\d{1,4})\s*(?:de|/)\s*(\d{1,4})(?!\d)")),
)


def find_page_marker(text: str) -> PageMarker | None:
    """The first well-formed marker on the line (1 <= X <= Y)."""
    folded = fold(text)
    for language, pattern in PAGE_MARKER_PATTERNS:
        for match in pattern.finditer(folded):
            number, total = int(match.group(1)), int(match.group(2))
            if 1 <= number <= total:
                return PageMarker(number, total, language, match.start(), match.end())
    return None
