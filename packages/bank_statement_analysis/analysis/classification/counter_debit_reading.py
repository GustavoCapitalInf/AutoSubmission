"""Counter-debit readings and payer keys."""
from __future__ import annotations

import re
from functools import cache
from typing import Sequence

from analysis.classification.payees import _unknown_payee_tokens
from analysis.classification.record import CounterDebitReading, TransactionClassification, _NO_COUNTER_DEBIT_READING
from analysis.classification_registry import BANK_POSTING_TYPE_LABELS
from analysis.description_text import normalize_transaction_description
from analysis.descriptor.lexical import (
    _distinctive_words,
    _first_distinctive_word,
    _is_reference_token,
    _payee_region,
    _skip_numbered_leading_date,
    payer_name,
)
from analysis.descriptor.rails import _counter_debit_skip_words, _without_receiver_value
from analysis.descriptor.words import (
    REVENUE_GENERIC_WORDS,
    _BMO_CODE_TAIL,
    _CARD_FORM_DEBIT_PREFIX,
    _NAME_STARTERS,
    _NUMBERED_COMPANY_REGION,
    _NUMBERED_TAIL_WORDS,
    _PROVINCE_NOT_A_NAME_START,
    _QUEBEC,
)


#: §5.2, §8.1: the numbered-company form the counter-debit holds key a numbered company by: six to ten digits (no
#: digit before them) and then a province or territory (or a cut of one) or BMO's code tail that is no name's first
#: word (_PROVINCE_NOT_A_NAME_START), or Quebec's NNNN NNNN before QUEBEC (or its cut, or QC), then any legal forms,
#: BMO codes and tail words (_BMO_CODE_TAIL, _NUMBERED_TAIL_WORDS). Its number is `number`, or Quebec's two groups
#: joined (_numbered_form_number). Never any digits alone: a cheque, confirmation or payment number before a name
#: word ('CHEQUE 1234567', 'BILL PAYMENT 1234567 NORTHWIND SUPPLY INC', 'MISC PAYMENT 123456 NORTH MOUNTAIN PAVING')
#: is none.
_NUMBERED_FORM = re.compile(
    rf"(?<![0-9])(?:(?P<number>\d{{6,10}}) {_PROVINCE_NOT_A_NAME_START}"
    rf"|(?P<first>\d{{4}}) (?P<second>\d{{4}}) {_QUEBEC}\b)"
    rf"(?: (?:{_BMO_CODE_TAIL}|{_NUMBERED_TAIL_WORDS})\b)*"
)


def _payer_key(region: str) -> tuple[str, ...]:
    """§5.2: the payer key: the payer name's words without the generic words, at most the first four."""
    return tuple(word for word in payer_name(region).split() if word not in REVENUE_GENERIC_WORDS)[:4]


def _payer_first_distinctive_word(region: str) -> str | None:
    """§7.5, §8.1: the payer's first distinctive word: four or more letters, not an AP, bank-template,
    legal-suffix, generic or public-payer word, and not a common name-starter."""
    words = [word for word in _distinctive_words(payer_name(region).split()) if word not in _counter_debit_skip_words()]
    return _first_distinctive_word(words)


#: §7.5: the words of a card purchase's merchant pass 6 reads. The city and state follow them.
_CARD_MERCHANT_WORDS = 2


def _card_processor_code(token: str, printed: str) -> bool:
    """A card purchase's leading token is a processor code ('SQ *', 'TST*'): at most three letters printed right
    before a star, which normalization drops."""
    return (
        token.isalpha() and len(token) <= 3
        and re.search(rf"(?<![A-Za-z0-9]){re.escape(token)} ?\*", printed, re.IGNORECASE) is not None
    )


def _card_merchant_text(text: str, printed: str) -> str | None:
    """§7.5: a card purchase's merchant, after its card-form prefix and a processor code: its first two words, or
    None when the merchant's first token is a reference or a short token ('76', 'BP1234567', 'SQ *AB'). Never read
    past the merchant's first words, so the city printed after it is never the debit's word."""
    tokens = _payee_region(text).split()
    if tokens and _card_processor_code(tokens[0], printed):
        tokens = tokens[1:]
    if not tokens or _is_reference_token(tokens[0]) or len(tokens[0]) <= 2:
        return None
    return " ".join(tokens[:_CARD_MERCHANT_WORDS])


#: §17.1: a leading pre-authorized-debit label, on any bank (CIBC's `PRE-AUTH DEBIT [<reference>] <name> [BUSINESS
#: PAD]`, `PRE-AUTHORIZED DEBIT`, `PREAUTHORISED DEBIT`), with the references printed after it: cut from a debit before
#: the counter-debit readings, so the funder's name is read (`PRE AUTH DEBIT 0000000 WOODGROVE CAPITAL BUSINESS PAD`
#: reads WOODGROVE, never AUTH). A numbered company's number after it is no reference (`PRE AUTH DEBIT 1234567 ONTARIO
#: INC` keeps `1234567 ONTARIO INC`). The D6 lender names are not read through it (_unknown_payee_tokens is unchanged).
_PAD_LABEL_BEFORE_PAYEE = re.compile(
    r"^(?:PRE ?AUTH(?:ORI[SZ]ED)?|PREAUTH(?:ORI[SZ]ED)?) DEBIT"
    rf"(?: (?!\d{{6,10}} {_PROVINCE_NOT_A_NAME_START}|\d{{4}} \d{{4}} {_QUEBEC}\b)\d+)*(?= |$) ?"
)


@cache
def _posting_type_label_pattern(bank: str) -> re.Pattern[str] | None:
    """The posting-type labels of the statement's bank (BANK_POSTING_TYPE_LABELS, read when the bank field contains one
    of the entry's bank words as whole words, in any case), longest first, as a pattern that reads one of them at a
    text's start with a word after it; None when the bank prints none."""
    field = normalize_transaction_description(bank).strip().upper()
    labels: set[str] = set()
    for markers, printed in BANK_POSTING_TYPE_LABELS:
        if any(re.search(r"(?<![A-Z])" + re.escape(marker) + r"(?![A-Z])", field) for marker in markers):
            labels.update(printed)
    if not labels:
        return None
    alternatives = "|".join(re.escape(label) for label in sorted(labels, key=lambda label: (-len(label), label)))
    return re.compile(rf"^(?:{alternatives}) (?=\S)")


def _without_posting_type_label(text: str, bank: str | None) -> str:
    """`text` without ONE posting-type label of the statement's bank (`bank`, Statement.bank) that starts it and has a
    word after it: RBC's `INSURANCE`, `INVESTMENT`, `FEES DUES`, `EQUIPMENT RENT` and `PAY EMPLOYEE VENDOR`,
    Scotiabank's `INVESTMENT` (BANK_POSTING_TYPE_LABELS). The bank's own label names no party, so on RBC `INSURANCE
    SUNLIFE MED INS` reads SUNLIFE and `INVESTMENT MERCH PAD` reads MERCH. Any other bank, or no bank, reads `text`
    unchanged (`INSURANCE AUTO AUCTIONS` keeps its first word)."""
    if not bank:
        return text
    pattern = _posting_type_label_pattern(bank)
    return text if pattern is None else pattern.sub("", text, count=1)


def _counter_debit_text(record: TransactionClassification) -> tuple[str | None, bool]:
    """§7.5, §8.1: the text a posted debit's counter-debit readings read, and whether it is a card purchase (its
    card-form prefix matched): on a card purchase its merchant's first two words (_card_merchant_text; None when it
    prints none), else the text after the prefix. On a debit that is no card purchase, without the statement's bank's
    posting-type label and then without a leading pre-authorized-debit label."""
    text, card_form = _CARD_FORM_DEBIT_PREFIX.subn("", record.normalized_description, count=1)
    if card_form:
        return _card_merchant_text(text, record.original_description or ""), True
    return _PAD_LABEL_BEFORE_PAYEE.sub("", _without_posting_type_label(text, record.bank), count=1), False


def _debit_word_reading(
    record: TransactionClassification, *, keep_places: bool = False,
) -> tuple[str | None, bool]:
    """§7.5, §8.1: a posted debit's first distinctive word, read on its D11 payee words; on a card purchase, after
    its leading card-form words and MMDD date and only on its merchant's first two words (D11 itself is unchanged).
    The second value says whether the debit is a card purchase (its card-form prefix matched): pass 7 leaves a card
    purchase's merchant out of payer_also_debited (5.6, A1 census). Never a rail's, a bank label's or (unless
    `keep_places`) a place's word (_without_not_a_payer). Read on _counter_debit_text, so a debit that is no card
    purchase is read without its bank's posting-type label and a leading pre-authorized-debit label."""
    text, card_form = _counter_debit_text(record)
    if text is None:
        return None, True
    words = [
        word for word in _distinctive_words(_without_not_a_payer(_unknown_payee_tokens(text), keep_places=keep_places))
        if word not in _counter_debit_skip_words()
    ]
    return _first_distinctive_word(words), card_form


def _debit_first_distinctive_word(record: TransactionClassification) -> str | None:
    """§7.5, §8.1: a posted debit's first distinctive word (_debit_word_reading), a card purchase's merchant
    included. Passes 6 and 7 read _debit_word_reading itself, with its card flag."""
    return _debit_word_reading(record)[0]


#: Words that never make a payer's or a debit's first distinctive word when passes 6 and 7 compare a payer with the
#: statement's debits (counter_debit_payer_reading), beside _counter_debit_skip_words. Generic words let unrelated
#: companies match: '<initials> EXPRESS INC' against American Express, 'MERCHANT SERVICES' against another processor's
#: 'MERCHANT SERVICE ... FEE', a utility against another utility, INCOME, PAIEMENT, POSTED, SERVICE, TRSFR. A bank's
#: own name prints as its channel (a bank's online payment, its merchant deposit, its card, its ATM, its pay product),
#: never as the payer the holder also pays; only the names the corpus prints that way are listed (a bank's name
#: printed as the holder's own account at it, a transfer to or from the holder's savings there, keeps matching: the
#: guard keeps every transfer and lender match).
_COUNTER_DEBIT_GENERIC_WORDS = frozenset({
    "MERCHANT", "UTILITIES", "EXPRESS", "INCOME", "PAIEMENT", "POSTED", "SERVICE", "SERVICES", "TRSFR",
    "CHASE", "TRUIST", "BLUEVINE",
})
#: §5.2: words that name no counterparty, which the counter-debit readings skip (counter_debit_payer_reading's legacy
#: word, _debit_word_reading, _counter_debit_head; never the payer's first distinctive word other readers group payers
#: by, nor _counter_debit_skip_words): the person-to-person rails' and RBC's French label's own words (a Zelle or
#: e-Transfer debit keeps its recipient's name; _COUNTER_DEBIT_LABEL_WORDS), and the place words
#: (_COUNTER_DEBIT_PLACE_WORDS): the US states (the words of a two-word state that are no generic word or name-starter),
#: the provinces and territories, CANADA, CANADIAN and AMERICAN (a town's or a nation's adjective names a place, never a
#: payer). The CASH APP phrase is skipped whole (_without_not_a_payer). The lender hold (payer_debited_as_lender) keeps
#: the place words (`keep_places`): a funder may carry a state's name ('<STATE> VENTURE'), and that hold never lets a
#: funder's money into True. Scotiabank's ACHDEBIT label ('MISC PAYMENT ACHDEBIT <name> CA') is a label word too.
_COUNTER_DEBIT_LABEL_WORDS = frozenset({
    "ZELLE", "INTERAC", "VENMO", "POPMONEY", "AUTODEPOSIT", "CASHAPP", "PAIEMENT", "ACHDEBIT",
})
_COUNTER_DEBIT_PLACE_WORDS = frozenset("""
ALABAMA ALASKA ARIZONA ARKANSAS CALIFORNIA COLORADO CONNECTICUT DELAWARE FLORIDA GEORGIA HAWAII IDAHO ILLINOIS INDIANA
IOWA KANSAS KENTUCKY LOUISIANA MAINE MARYLAND MASSACHUSETTS MICHIGAN MINNESOTA MISSISSIPPI MISSOURI MONTANA NEBRASKA
NEVADA HAMPSHIRE JERSEY MEXICO YORK CAROLINA DAKOTA OHIO OKLAHOMA OREGON PENNSYLVANIA RHODE TENNESSEE TEXAS UTAH
VERMONT VIRGINIA WASHINGTON WISCONSIN WYOMING
ONTARIO QUEBEC ALBERTA MANITOBA SASKATCHEWAN BRITISH COLUMBIA NOVA SCOTIA BRUNSWICK NEWFOUNDLAND LABRADOR PRINCE EDWARD
YUKON NORTHWEST TERRITORIES NUNAVUT CANADA CANADIAN AMERICAN
""".split())
_COUNTER_DEBIT_NOT_A_PAYER = _COUNTER_DEBIT_LABEL_WORDS | _COUNTER_DEBIT_PLACE_WORDS


def _without_not_a_payer(words: Sequence[str], *, keep_places: bool = False) -> list[str]:
    """`words` without _COUNTER_DEBIT_NOT_A_PAYER (with `keep_places`, without the label words only) and the CASH APP
    phrase."""
    skip = _COUNTER_DEBIT_LABEL_WORDS if keep_places else _COUNTER_DEBIT_NOT_A_PAYER
    kept: list[str] = []
    skip_next = False
    for index, word in enumerate(words):
        if skip_next:
            skip_next = False
            continue
        if word == "CASH" and index + 1 < len(words) and words[index + 1] == "APP":
            skip_next = True
            continue
        if word not in skip:
            kept.append(word)
    return kept


#: A payroll provider whose name has three letters is still a counter-debit word: an 'ADP TAX' credit beside the
#: holder's own 'ADP TAX' debits is its tax impound coming back.
_SHORT_PAYROLL_PROVIDER_WORDS = frozenset({"ADP"})
#: A name with a reference glued after it ('FABRIKAMGROUPINC1', 'FORWARDFINUSA1'): its three or more letters, never
#: a masked run of X, read as a word once the digits are split off.
_GLUED_DIGIT_RUN = re.compile(r"(?<![A-Z0-9])(?!X+\d)([A-Z]{3,})(\d+)(?![A-Z0-9])")
#: The words after the first distinctive word that its glued forms take ('CONTOSO RIDGE' is
#: 'CONTOSORIDGE').
_GLUED_FORM_WORDS = 2


def _split_glued_digits(text: str) -> str:
    """The text with each glued digit run split off its name ('FABRIKAMUSA1' reads 'FABRIKAMUSA 1')."""
    return _GLUED_DIGIT_RUN.sub(r"\1 \2", text)


def _numbered_form_number(found: re.Match[str]) -> str:
    """The number of a _NUMBERED_FORM match: its six to ten digits, or Quebec's two groups joined ('1234 5678
    QUEBEC INC' reads '12345678')."""
    return found.group("number") or found.group("first") + found.group("second")


#: The leading number of a payer region _NUMBERED_COMPANY_REGION reads: Quebec's two groups, or the six to ten
#: digits.
_NUMBERED_REGION_NUMBER = re.compile(
    rf"^(?:(?P<first>\d{{4}}) (?P<second>\d{{4}}) {_QUEBEC}\b|(?P<number>\d{{6,10}})\b)"
)


def _payer_region_number(region: str) -> tuple[str | None, str]:
    """§5.2: a credit's numbered-company number and the region its words are read on. The region is read past a leading
    date (as numbered_company reads it): when it is a numbered company's (_NUMBERED_COMPANY_REGION), the number is its
    leading digits (Quebec's form joined); when the numbered-company form starts it (_NUMBERED_FORM), its words are
    read without that form, so the province, its cut, the legal forms and BMO's code name no payer ('7654321 ONTA AP
    CC' reads only its number; '1234567 ONTARIO INC O A NORTHWIND BAKERY' its number and NORTHWIND)."""
    numbered = _skip_numbered_leading_date(region)
    number = None
    if _NUMBERED_COMPANY_REGION.match(numbered) is not None:
        found = _NUMBERED_REGION_NUMBER.match(numbered)
        if found is not None:
            number = _numbered_form_number(found)
    form = _NUMBERED_FORM.match(numbered)
    return number, region if form is None else numbered[form.end():].strip()


def _counter_debit_head(
    words: Sequence[str], *, keep_places: bool = False,
) -> tuple[str, tuple[str, ...]] | None:
    """The first distinctive word of `words` (four letters or more and no name-starter, or a three-letter payroll
    provider), the generic words and banks' names left out, with the distinctive words after it. And the words that
    name no counterparty (_without_not_a_payer; the place words kept with `keep_places`)."""
    skip = _counter_debit_skip_words() | _COUNTER_DEBIT_GENERIC_WORDS
    kept = [
        word for word in _distinctive_words(_without_not_a_payer(words, keep_places=keep_places)) if word not in skip
    ]
    for index, word in enumerate(kept):
        if (len(word) >= 4 and word not in _NAME_STARTERS) or word in _SHORT_PAYROLL_PROVIDER_WORDS:
            return word, tuple(kept[index + 1:])
    return None


def _counter_debit_reading(
    legacy: str | None, readings: Sequence[Sequence[str]], *, keep_places: bool = False, number: str | None = None,
) -> CounterDebitReading:
    heads: list[tuple[str, tuple[str, ...]]] = []
    for words in readings:
        head = _counter_debit_head(words, keep_places=keep_places)
        if head is not None and head not in heads:
            heads.append(head)
    keys = frozenset(
        word + "".join(following[:count]) for word, following in heads for count in range(_GLUED_FORM_WORDS + 1)
        if count <= len(following)
    )
    return CounterDebitReading(legacy, keys, tuple(heads), number)


def counter_debit_payer_reading(
    region: str, *, keep_places: bool = False, bank: str | None = None,
) -> CounterDebitReading:
    """A credit's counter-debit reading, on its payer region (§5.2: never a receiver field). Its legacy word is the
    payer's first distinctive word (_payer_first_distinctive_word) read without the words that name no counterparty
    (_without_not_a_payer; with `keep_places`, the label words only: the lender hold's reading). The region is read
    without the statement's bank's posting-type label; a numbered company's region gives its number, and its words are
    read without the numbered-company form."""
    if not region:
        return _NO_COUNTER_DEBIT_READING
    number, region = _payer_region_number(_without_posting_type_label(region, bank))
    legacy = _first_distinctive_word([
        word for word in _distinctive_words(_without_not_a_payer(payer_name(region).split(), keep_places=keep_places))
        if word not in _counter_debit_skip_words()
    ])
    return _counter_debit_reading(
        legacy, (payer_name(region).split(), payer_name(_split_glued_digits(region)).split()), keep_places=keep_places,
        number=number,
    )


def counter_debit_debit_reading(
    record: TransactionClassification, *, keep_places: bool = False,
) -> tuple[CounterDebitReading, bool]:
    """A posted debit's counter-debit reading on its D11 payee words (a card purchase's merchant, as
    _debit_word_reading reads it), and whether it is a card purchase. The glued-digit reading is taken only when the
    printed one finds no word: D11 stops a name at its first reference, so splitting a leading reference ('CHECK1234
    <name>') would cut the name the printed text reads. `keep_places` keeps the place words (the lender hold's
    reading, _without_not_a_payer). Read on _counter_debit_text; `number` is the first numbered-company form the debit
    prints outside its receiver fields' values ('CHEQUE 1234567' none), its word readings unchanged (they stop at the
    number)."""
    legacy, card_purchase = _debit_word_reading(record, keep_places=keep_places)
    text, _ = _counter_debit_text(record)
    if text is None:
        return _NO_COUNTER_DEBIT_READING, card_purchase
    printed = _unknown_payee_tokens(text)
    readings: list[Sequence[str]] = [printed]
    if _counter_debit_head(printed, keep_places=keep_places) is None:
        readings.append(_unknown_payee_tokens(_split_glued_digits(text)))
    found = _NUMBERED_FORM.search(_without_receiver_value(text))
    number = None if found is None else _numbered_form_number(found)
    return _counter_debit_reading(legacy, readings, keep_places=keep_places, number=number), card_purchase
