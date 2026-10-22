"""Account holder name reading, holder words, store-name runs."""
from __future__ import annotations

import re
from functools import cache
from typing import Sequence

from analysis.classification_registry import OPERATING_REVENUE_SOURCE_ALIASES
from analysis.description_text import normalize_transaction_description
from analysis.descriptor.credit_words import (
    _FUNDING_SETTLEMENT_ENTITIES,
    _FUNDING_WORD,
    _RECURRENCE_VETO,
    _STORE_NAME_PAYOUT_ENTITIES,
)
from analysis.descriptor.lexical import (
    _before_receiver,
    _first_distinctive_word,
    _is_reference_token,
    company_form,
    payer_name,
)
from analysis.descriptor.payer import _amex_ach_credit, _is_transfer_or_p2p_row, _sender_payer_region
from analysis.descriptor.rails import _is_wire_row, _loose_wire_originator, _matches_any
from analysis.descriptor.words import (
    REVENUE_GENERIC_WORDS,
    _BANK_COMPANY_FORM,
    _BOFA_ENTRY_FIELD,
    _BUSINESS_ACCOUNT_PATTERNS,
    _CHASE_ENTRY_FIELD,
    _CONSUMER_P2P_RAIL,
    _HOLDER_TEST_NOISE,
    _HOLDER_TRADE_NAME,
    _NAME_STARTERS,
    _PUSH_RAIL,
    _RECEIVER_FIELD_VALUE,
    _RECEIVER_NAME_LABELS,
)


#: The words the holder readers' published products print beyond the holder test's noise: PNC's product lines
#: (analysis/pnc.py _PRODUCTS: 'PNC Core Commercial Checking', 'Virtual Wallet With Performance Spend', 'Treasury
#: Enterprise Plan'). Every other product those readers publish ('Checking', 'TD Business Simple Checking', 'Business
#: Chequing Account', First Citizens' and Navy Federal's printed product lines) prints a noise word, which already makes
#: it name nobody as a holder's name (true_revenue._usable_holder_name).
_ACCOUNT_PRODUCT_WORDS: frozenset[str] = frozenset({
    "PNC", "CORE", "VIRTUAL", "WALLET", "WITH", "SPEND", "TREASURY", "ENTERPRISE", "PLAN",
})
#: Name particles, never a brand's initialism: a three-letter word the holder test skips when it reads the word a name
#: leads with.
_NAME_PARTICLES = frozenset({"DEL", "LOS", "LAS", "LES", "VAN", "VON", "DOS", "DAS", "SAN"})
#: Chase's CHECKING SUMMARY grid header, which its parser published as the account name before B9 ('INSTANCES
#: AMOUNT', alone or with the grid's first row glued on, or 'AMOUNT'): never a holder's name.
_SUMMARY_GRID_HEADER_NAME = re.compile(r"^(?:INSTANCES|AMOUNT)\b")
#: A word of fewer letters is a short initialism when a name leads with it.
_INITIALISM_LETTERS = 3


@cache
def account_name_text(account_name: str | None) -> str:
    """The statement's account name, normalized once per name ('' when none is printed), so the holder test
    never re-normalizes it row by row."""
    return normalize_transaction_description(account_name) if account_name else ""


def holder_reading(account_name: str | None, holder_name: str | None = None) -> str | None:
    """The name the holder tests read: the holder's own name when the parser read it from the header or the mailing
    block (Statement.holder_name), else the account-name field (a product, a nickname or, on some layouts, the
    holder). The account-name field keeps every product reading (_business_account)."""
    if holder_name and holder_name.strip():
        return holder_name
    return account_name


def _holder_test_words(words: Sequence[str]) -> list[str]:
    """A name's words as the holder test reads them, on either side: no holder-test noise word, no digit, three
    letters or more."""
    return [
        word for word in words
        if word not in _HOLDER_TEST_NOISE and not any(ch.isdigit() for ch in word) and len(word) > 2
    ]


def _summary_grid_header(text: str) -> bool:
    """A normalized account name that is Chase's summary grid header, not a name."""
    return _SUMMARY_GRID_HEADER_NAME.match(text) is not None


def account_product(text: str) -> bool:
    """A normalized account name that is a product a holder reader publishes, never a holder's name: no company form,
    and every word the holder test reads (_holder_test_words) a product word (_ACCOUNT_PRODUCT_WORDS), so PNC's
    'Treasury Enterprise Plan' names nobody while 'TREASURY SAMPLE PLAN LLC' does."""
    if not text or company_form(text):
        return False
    return all(word in _ACCOUNT_PRODUCT_WORDS for word in _holder_test_words(text.split()))


def holder_words(account_name: str | None) -> tuple[str, ...]:
    """§5.2: the holder's name (holder_reading), normalized, without holder-test noise, digit tokens and short tokens.
    Often empty: the account-name field is frequently only a product name. A summary grid header names nobody, and the
    bank and product abbreviations are noise. Nor does a product a holder reader publishes (account_product)."""
    text = account_name_text(account_name)
    if not text or _summary_grid_header(text) or account_product(text):
        return ()
    return tuple(_holder_test_words(text.split()))


def _lead_word(words: Sequence[str]) -> str | None:
    """The word a name leads with: its first word that is no common name-starter and no particle."""
    return next((word for word in words if word not in _NAME_STARTERS and word not in _NAME_PARTICLES), None)


def _person_name_reading(text: str) -> bool:
    """§5.2: a name that reads as a person's: no company form and no trade-name marker (_HOLDER_TRADE_NAME), and,
    its digit tokens and generic words (REVENUE_GENERIC_WORDS) dropped, two to four words of letters, none a
    holder-test noise word (_HOLDER_TEST_NOISE)."""
    if not text or company_form(text) or _HOLDER_TRADE_NAME.search(text):
        return False
    words = [
        word for word in text.split()
        if not any(character.isdigit() for character in word) and word not in REVENUE_GENERIC_WORDS
    ]
    return 2 <= len(words) <= 4 and all(word.isalpha() and word not in _HOLDER_TEST_NOISE for word in words)


def _printed_lead(words: Sequence[str]) -> str | None:
    """§5.2: the word a name leads with as printed: its first word of letters, two letters or more, that is no
    holder-test noise word (_HOLDER_TEST_NOISE: a layout's labels, the generic words) and no particle (_NAME_PARTICLES).
    Unlike _lead_word, a name-starter and a two- or three-letter word are kept ('GOLDEN', 'ACE', 'JB')."""
    return next((
        word for word in words
        if word.isalpha() and len(word) >= 2 and word not in _HOLDER_TEST_NOISE and word not in _NAME_PARTICLES
    ), None)


def _holder_abbreviation(word: str, holder_printed: Sequence[str]) -> bool:
    """§5.2: `word` abbreviates the holder's printed name (`holder_printed`, its words of letters): two to
    _INITIALISM_LETTERS letters, and either the initials of the holder's first words ('NYS' for 'NORTHWIND YACHT
    SERVICE') or a run of the holder's printed lead's letters in order from its first ('NW', 'NWD' for 'NORTHWIND';
    never 'ACE', 'AAA' or 'JB')."""
    if not 2 <= len(word) <= _INITIALISM_LETTERS:
        return False
    if len(holder_printed) >= len(word) and "".join(held[0] for held in holder_printed[: len(word)]) == word:
        return True
    lead = _printed_lead(holder_printed)
    if lead is None or not lead.startswith(word[0]):
        return False
    letters = iter(lead)
    return all(letter in letters for letter in word)


def _holder_name_words_match(
    payer: Sequence[str], holder: Sequence[str], *, people: bool = False,
    printed_payer: Sequence[str] | None = None, holder_printed: Sequence[str] | None = None,
) -> bool:
    """§5.2's holder test on one name of the holder's. A one-word holder must be the word the payer's name leads
    with. When either name leads with a short initialism, the two lead words are compared as printed: the same
    initialism is a likely affiliate, a different one a different company (never the industry word after it);
    otherwise the first distinctive words (four letters or more) are compared, the brand-word affiliate arm of §5.2.
    Two shared words always match.

    When both names read as a person's (`people`, holder_named), the initialism and brand-word arms are skipped: a
    person sharing only the holder's given name is another person. And two shared words match only when they include the
    word the holder's name leads with, or when the payer's own first distinctive word is a holder word (or it has none):
    another company leading with its own name and sharing the holder's trailing trade words ('<A> YACHT SERVICE' paying
    '<B> YACHT SERVICE LLC') is a customer, while the holder's own words after a label or the owner's name ('SAMPLE
    PERSON NORTHWIND MARINE LLC', 'SAMPLEMAN TRUCKING') stay the holder's.

    Read with the two names as printed (`printed_payer`, the payer reading's words of letters; `holder_printed`, the
    holder's; holder_named passes both, and without them the R20 reading above is kept), two shared words match when
    they include the holder's lead and, if the holder's name leads with a name-starter or a two-letter word (its
    printed lead, _printed_lead, is not its lead), the payer prints that word ('GOLDEN' for 'GOLDEN YACHT SERVICE LLC',
    'JB' for 'JB MARINE REPAIR LLC'); or when the R20 payer condition holds and the payer's own printed lead (a
    name-starter, a short word or an initialism included) is none, a holder word or the holder's abbreviation
    (_holder_abbreviation: 'NW' for 'NORTHWIND'): 'GOLDEN', 'ACE' or 'JB YACHT SERVICE' paying 'NORTHWIND YACHT SERVICE
    LLC' is a customer. The reading is narrower than R20's: it can only release."""
    if not holder:
        return False
    payer_lead = _lead_word(payer)
    if len(holder) == 1:
        return payer_lead == holder[0]
    holder_lead = _lead_word(holder)
    printed = printed_payer is not None and holder_printed is not None
    holder_printed_lead = _printed_lead(holder_printed) if printed else None
    if not people and _brand_word_match(
        payer, holder, payer_lead, holder_lead, printed_payer=printed_payer if printed else None,
        holder_printed_lead=holder_printed_lead,
    ):
        return True
    shared = _shared_holder_words(payer, holder, cuts=people)
    if len(shared) < 2:
        return False
    if holder_lead in shared and (
        not printed or holder_printed_lead in (None, holder_lead) or holder_printed_lead in printed_payer
    ):
        return True
    payer_first = _first_distinctive_word(payer)
    if payer_first is not None and payer_first not in holder:
        return False
    if not printed:
        return True
    payer_printed_lead = _printed_lead(printed_payer)
    return (
        payer_printed_lead is None or payer_printed_lead in holder_printed
        or _holder_abbreviation(payer_printed_lead, holder_printed)
    )


def _shared_holder_words(payer: Sequence[str], holder: Sequence[str], *, cuts: bool) -> list[str]:
    """§5.2: the holder's words the payer prints, in the payer's order. With `cuts` (two names read as a person's,
    whose given-name arm is skipped), a payer word the bank's field cut, a proper prefix of a holder word of
    _HOLDER_RUN_CUT_LETTERS letters or more, is that holder word, so the holder's own name cut short ('NORTHWIND
    DISTRIB' for 'NORTHWIND DISTRIBUTION', the B5 American Express pull) stays the holder's."""
    shared: list[str] = []
    for word in dict.fromkeys(payer):
        if word in holder:
            shared.append(word)
        elif cuts and len(word) >= _HOLDER_RUN_CUT_LETTERS:
            whole = next((held for held in holder if held != word and held.startswith(word)), None)
            if whole is not None:
                shared.append(whole)
    return list(dict.fromkeys(shared))


def _brand_word_match(
    payer: Sequence[str], holder: Sequence[str], payer_lead: str | None, holder_lead: str | None, *,
    printed_payer: Sequence[str] | None = None, holder_printed_lead: str | None = None,
) -> bool:
    """§5.2: the initialism and brand-word affiliate arms of _holder_name_words_match: when either name leads with a
    short initialism, the two lead words as printed; otherwise the first distinctive words. When the holder's printed
    lead (`holder_printed_lead`) is a name-starter or a two-letter word, which the first distinctive word skips, a
    first-distinctive match also needs the payer to print it (`printed_payer`), so 'ROYAL YACHT SERVICE' never matches
    'GOLDEN YACHT SERVICE LLC' on YACHT; the initialism arm is unchanged."""
    if holder_lead is not None and payer_lead is not None and (
        len(holder_lead) <= _INITIALISM_LETTERS or len(payer_lead) <= _INITIALISM_LETTERS
    ):
        return holder_lead == payer_lead
    holder_first = _first_distinctive_word(holder)
    if holder_first is None or _first_distinctive_word(payer) != holder_first:
        return False
    if printed_payer is not None and holder_printed_lead is not None and (
        holder_printed_lead in _NAME_STARTERS or len(holder_printed_lead) == _DROPPED_INITIALISM_LETTERS
    ):
        return holder_printed_lead in printed_payer
    return True


#: The legal forms a holder's name run may print or leave off, read out of both names before a payer's trailing run of
#: the holder's name is looked for.
_HOLDER_RUN_LEGAL_FORMS = frozenset({
    "LLC", "INC", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LP", "LLP", "PLLC", "PLC", "DBA",
})


def _holder_run_words(name: str) -> list[str]:
    """A holder's name's words as the receiver-block strip reads them: tokenized as the payer reading is (payer_name:
    no token holding a digit, no single letter), its legal forms left out (_HOLDER_RUN_LEGAL_FORMS), so 'CONTOSO S
    FLOWER SHOP LLC' (a possessive's apostrophe normalized to a space) runs 'CONTOSO FLOWER SHOP' as the payer reading
    prints it."""
    return [word for word in payer_name(name).split() if word not in _HOLDER_RUN_LEGAL_FORMS]


#: Another payer's name before a trailing run of the holder's name holds this many name words (letters, no generic or
#: noise word): a layout's labels before the holder's own name ('DEPOSIT ACH PAID FROM') name no payer.
_PAYER_BEFORE_HOLDER_RUN_WORDS = 2


#: A run of the holder's name inside another payer's region starts with the holder's first two name words, the
#: second whole or cut to this many letters or more.
_HOLDER_RUN_CUT_LETTERS = 3


#: Truist's receiver slot. Its credit rows print '<entry> <company field> <receiver> CUSTOMER ID <id>': the receiver
#: (the holder) after the originator's company field, with no label, the bank printing no padding, so a short
#: originator runs straight on into the holder's name.
_RECEIVER_SLOT_LABEL = re.compile(r" CUSTOMER ID\b")
#: The statement's bank that prints that receiver slot (Truist's own reader publishes 'Truist'); another bank
#: printing CUSTOMER ID keeps the two-word reading.
_RECEIVER_SLOT_BANK = re.compile(r"\bTRUIST\b", re.IGNORECASE)


def holder_receiver_block(text: str, bank: str | None = None) -> int | None:
    """How the row's payer reading may print the holder's name as another payer's unlabelled receiver block
    (holder_named's `receiver_block`: the name words of another payer's that must print before a run of the holder's
    name for the run to be read as the receiver). None on a labelled sender, which prints the sender alone, so a run of
    the holder's name inside it is the holder's ('ZELLE PAYMENT FROM <owner> <holder>'): an incoming wire's originator
    field, a person-to-person or push rail, a transfer's sender after FROM. One on Truist's layout, whose receiver slot
    follows a company field that may print one word (_RECEIVER_SLOT_LABEL: 'TRANSFER <originator> INC <holder> CUSTOMER
    ID <id>'). Two (_PAYER_BEFORE_HOLDER_RUN_WORDS) on any other row. The one-word slot is read on a Truist statement
    only (`bank`, _RECEIVER_SLOT_BANK)."""
    if _is_wire_row(text) or _loose_wire_originator(text):
        return None
    row = _before_receiver(text)
    if _CONSUMER_P2P_RAIL.search(row) or _PUSH_RAIL.search(row):
        return None
    if _is_transfer_or_p2p_row(text) and not _amex_ach_credit(text) and _sender_payer_region(text):
        return None
    if _RECEIVER_SLOT_LABEL.search(row) and bank and _RECEIVER_SLOT_BANK.search(bank):
        return 1
    return _PAYER_BEFORE_HOLDER_RUN_WORDS


def _without_trailing_holder_run(
    payer: str, names: Sequence[str], payer_words: int | None = _PAYER_BEFORE_HOLDER_RUN_WORDS,
) -> str:
    """A payer name that prints another payer's name first (two name words or more, _PAYER_BEFORE_HOLDER_RUN_WORDS) and
    then a run of one of the holder's names (its first two words, the second whole or cut): the unlabelled receiver
    block, read without that run and whatever follows it ('FABRIKAM INSURANCE MISC NORTHWIND HARBOR AGENC'; Truist's
    company field running on into the holder's name and a person's, 'INVOICES SAMPLE CHURC NORTHWIND HARBOR SAMPLE P');
    any other payer name as it is. The layout sets how many name words of another payer's must print first
    (`payer_words`, holder_receiver_block): one on Truist's receiver slot, and None on a labelled sender, which is read
    as it is. The holder's name is read as the payer's is (_holder_run_words), so a possessive's S ('SAMPLE'S'
    normalizes to 'SAMPLE S'), a middle initial or a digit token never stops the strip."""
    if payer_words is None:
        return payer
    words = [word for word in payer.split() if word not in _HOLDER_RUN_LEGAL_FORMS]
    held_names = [held for held in (_holder_run_words(name) for name in names) if len(held) >= 2]
    for start in range(1, len(words) - 1):
        if len(_holder_test_words(words[:start])) < payer_words:
            continue
        first, second = words[start], words[start + 1]
        for held in held_names:
            if held[0] == first and len(second) >= _HOLDER_RUN_CUT_LETTERS and held[1].startswith(second):
                # A field printing the holder's own name glued is the holder's, never another payer.
                return payer if _glued_holder_name(words[:start], held) else " ".join(words[:start])
    return payer


def _glued_holder_name(field: Sequence[str], held: Sequence[str]) -> bool:
    """The words before a run of the holder's name print the holder's name with its spaces removed, whole, with a
    legal form glued on, or cut to _HOLDER_CUT_LETTERS letters or more (Truist's company field printing the holder's
    own name: 'TRANSFER CONTOSOGAMES CONTOSO GAMES CUSTOMER ID ...')."""
    glued, name = "".join(field), "".join(held)
    return glued.startswith(name) or (len(glued) >= _HOLDER_CUT_LETTERS and name.startswith(glued))


#: A word the holder test drops that can still lead the holder's own name: GENERAL (a product's or a nickname's
#: word, and a business's) and, by length, a two-letter initialism ('JB TRUCKING LLC'). A single letter never is:
#: the payer reading drops it (payer_name).
_DROPPED_NAME_LEADS = frozenset({"GENERAL"})
_DROPPED_INITIALISM_LETTERS = 2


def _dropped_lead_run(name: str, holder: Sequence[str]) -> tuple[str, ...] | None:
    """A one-word holder whose printed name leads with a word the holder test drops (_DROPPED_NAME_LEADS, a two-letter
    initialism): the printed run from that word to the holder's one word ('GENERAL PLUMBING' for 'GENERAL PLUMBING
    LLC', 'JB TRUCKING' for 'JB TRUCKING LLC'), which the payer must print, so another company leading with the
    industry word is never the holder. None for any other holder (a one-word holder printed alone, or after a bank's or
    a product's abbreviation, keeps the one-word reading). A single letter is no word of the run, as the payer reading
    drops it (payer_name), so 'JB'S TRUCKING LLC' (normalized 'JB S TRUCKING LLC') runs 'JB TRUCKING'."""
    if len(holder) != 1:
        return None
    words = [
        word for word in name.split() if word.isalpha() and len(word) > 1 and word not in _HOLDER_RUN_LEGAL_FORMS
    ]
    if holder[0] not in words:
        return None
    end = words.index(holder[0])
    start = next((
        index for index, word in enumerate(words[:end])
        if word in _DROPPED_NAME_LEADS or len(word) == _DROPPED_INITIALISM_LETTERS
    ), None)
    return None if start is None else tuple(words[start:end + 1])


def _prints_run(words: Sequence[str], run: Sequence[str]) -> bool:
    """`words` print `run` as consecutive words."""
    return any(tuple(words[index:index + len(run)]) == tuple(run) for index in range(len(words) - len(run) + 1))


def holder_named(
    region: str, account_name: str | None, *, receiver_block: int | None = _PAYER_BEFORE_HOLDER_RUN_WORDS,
) -> bool:
    """§5.2: the holder test, read on a payer region (never on a check, cash, branch, ATM or bare row, which has none)
    against the holder's name (`account_name`: holder_reading's name). It matches when the payer's words name the holder
    (_holder_name_words_match), when the payer is the holder's name cut short, or when the region prints a run of four
    or more digits that the holder's name also prints. A DBA name's sides are each a name of the holder's, a summary
    grid header names nobody, and the holder's name printed after another payer's words is that payer's unlabelled
    receiver, never the payer (_without_trailing_holder_run). The row's layout says where that receiver can print
    (`receiver_block`, holder_receiver_block: never on a labelled sender, after one name word on Truist's receiver
    slot), and a one-word holder left by a dropped lead word is read with that word (_dropped_lead_run). A product a
    holder reader publishes names nobody (account_product). A name of the holder's and a payer reading that both read as
    a person's (_person_name_reading) are compared on their shared words only, never by the given name they lead with.
    The shared words are read with both names as printed; and a DBA holder's whole name is read as a person's when its
    first side is one ('<owner> DBA <trade>'), so another person sharing only the owner's given name is counted."""
    if not region or not account_name:
        return False
    printed = account_name_text(account_name)
    if not printed or _summary_grid_header(printed) or account_product(printed):
        return False
    names: tuple[str, ...] = (printed,)
    if _HOLDER_TRADE_NAME.search(printed):
        names = (printed, *_HOLDER_TRADE_NAME.split(printed, maxsplit=1))
    reading = _without_trailing_holder_run(payer_name(region), names, receiver_block)
    payer = _holder_test_words(reading.split())
    printed_payer = [word for word in reading.split() if word.isalpha()]
    person_payer = _person_name_reading(reading)
    for index, name in enumerate(names):
        holder = _holder_test_words(name.split())
        run = _dropped_lead_run(name, holder)
        if run is not None:
            if _prints_run(printed_payer, run):
                return True
            continue
        # The whole DBA name (names[0] beside its two sides) reads as a person's when its first side does; each side
        # keeps its own reading.
        person_side = names[1].strip() if index == 0 and len(names) > 1 else name
        holder_printed = [word for word in name.split() if word.isalpha()]
        if _holder_name_words_match(
            payer, holder, people=person_payer and _person_name_reading(person_side), printed_payer=printed_payer,
            holder_printed=holder_printed,
        ):
            return True
    if _holder_cut_name(payer_name(region), printed):
        return True
    return any(
        re.search(rf"(?<!\d){run}(?!\d)", printed) for run in re.findall(r"\d{4,}", region)
    )


#: A cut holder name names the holder when it keeps this many whole words before the cut, or this many letters in
#: all.
_HOLDER_CUT_WHOLE_WORDS = 2
_HOLDER_CUT_LETTERS = 12


def _holder_cut_name(payer: str, holder: str) -> bool:
    """§5.2: the payer name is the holder's normalized name cut short: a word-by-word prefix of it whose last word is
    a proper prefix of the holder's word there ('GLOBAL AMERICAN NORTHW' against 'GLOBAL AMERICAN NORTHWIND...'),
    with _HOLDER_CUT_WHOLE_WORDS whole words before the cut or _HOLDER_CUT_LETTERS letters in all, so a single common
    word never matches."""
    sender = payer.split()
    words = holder.split()
    if not sender or len(sender) > len(words):
        return False
    whole, cut = sender[:-1], sender[-1]
    if whole != words[: len(whole)]:
        return False
    target = words[len(whole)]
    if cut == target or not target.startswith(cut):
        return False
    return len(whole) >= _HOLDER_CUT_WHOLE_WORDS or sum(len(word) for word in sender) >= _HOLDER_CUT_LETTERS


#: §7.0: a legal-form holder name is a business account for the recurrence rule.
_LEGAL_FORM_HOLDER = re.compile(r"\b(?:LLC|INC|CORP|LTD|LLP|PLLC)\b")


def _business_account(account_name: str | None) -> bool:
    """§7.0: a business account for the recurrence rule: BUSINESS, COMMERCIAL, OPERATING or MERCHANT, or (5.5) a
    holder name that prints a legal form."""
    name = account_name_text(account_name)
    return _matches_any(name, _BUSINESS_ACCOUNT_PATTERNS) or _LEGAL_FORM_HOLDER.search(name) is not None


#: FW wave 3: a receiver-name field's label, before its value.
_RECEIVER_NAME_LABEL = re.compile(rf"^(?:{_RECEIVER_NAME_LABELS})\b\s*")


def store_name_printed(text: str, entity: str | None, account_name: str | None = None) -> bool:
    """§7.0: a store-name platform's row prints a store name where the platform prints the merchant's store: its entry
    field (Bank of America's DES, Chase's CO ENTRY DESCR), or the row before its receiver fields on a layout that
    prints none (BMO's 'DIRECT DEPOSIT DOORDASH <store> MSP/DIV'). A store name is a word that is no veto or financing
    word (_RECURRENCE_VETO, _FUNDING_WORD), no generic word, no reference token, no company form and none of the
    platform's own alias words. A veto word that is the whole field, or forms it alone with generic words
    ('DES:CAPITAL', 'DES:CAPITAL ADVANCE', 'DES:LENDING PAYMENT'), is the platform's own financing wording, so the
    holder's word exemption never reads it. Nor is a veto word that leads the field, whatever follows it ('DES:CAPITAL
    DISB', 'DES:LENDING DAILY': the ten-character entry field often cuts a financing entry's second word); a store name
    prints its own words first ('DES:<store> CAPITA'), so the field must lead with a store word. FW wave 3 (W2-1): a
    store whose own name starts with a financing word ('DES:CAPITAL GRILLE' for a holder named '... CAPITAL GRILLE ...')
    leads with it too: the field leads with a store word when its words (two or more) are a consecutive run of the
    holder's name (_store_name_run)."""
    words = _platform_entry_words(text, entity)
    if not words:
        return False
    led = " ".join(words)
    if _RECURRENCE_VETO.match(led) is None and _FUNDING_WORD.match(led) is None:
        return True
    return _store_name_run(words, text, account_name)


def store_name_run_words(text: str, entity: str | None, account_name: str | None) -> frozenset[str]:
    """FW wave 3 (W2-1): the store-name platform's entry words when they are a run of the holder's name
    (_store_name_run): the store's own name, whose words the recurrence veto and the registry's financing words spare
    at any length ('FIN AND FORK'); empty otherwise."""
    if entity not in _STORE_NAME_PAYOUT_ENTITIES:
        return frozenset()
    words = _platform_entry_words(text, entity)
    return frozenset(words) if _store_name_run(words, text, account_name) else frozenset()


def _store_name_run(words: Sequence[str], text: str, account_name: str | None) -> bool:
    """FW wave 3 (W2-1): the platform's entry words, two or more, are a consecutive run of whole words of the holder's
    own name as the classifier knows it: the statement's account name (its trade name after DBA included), or a name
    the row's receiver fields print (a product-name account). A bare financing word is one word; a financing entry
    ('CAPITAL DISB', 'LENDING DAILY') or a store the holder is not ('CAPITAL GRILLE' for 'SAMPLE BAKERY LLC') is no
    run."""
    if len(words) < 2:
        return False
    names = [account_name_text(account_name).split()] if account_name else []
    for found in _RECEIVER_FIELD_VALUE.finditer(text):
        names.append(_RECEIVER_NAME_LABEL.sub("", found.group(0), count=1).split())
    run = list(words)
    return any(
        name[start:start + len(run)] == run for name in names for start in range(len(name) - len(run) + 1)
    )


def _platform_entry_words(text: str, entity: str | None) -> list[str]:
    """§7.0, §7.2: the words of the field where a platform prints its entry (the merchant's store on a store-name
    platform): its entry field (Bank of America's DES, Chase's CO ENTRY DESCR), or the row before its receiver fields
    on a layout that prints none, without its generic words, reference tokens, company forms and the platform's own
    alias words."""
    row = _before_receiver(text)
    fields = [found.group(1).strip() for pattern in (_BOFA_ENTRY_FIELD, _CHASE_ENTRY_FIELD)
              if (found := pattern.search(row)) is not None]
    field = " ".join(fields) if any(fields) else row
    platform = {word for alias in OPERATING_REVENUE_SOURCE_ALIASES.get(entity or "", ()) for word in alias.split()}
    return [
        word for word in field.split()
        if not (
            word in REVENUE_GENERIC_WORDS or _is_reference_token(word) or _BANK_COMPANY_FORM.fullmatch(word)
            or word in platform
        )
    ]


#: §7.2: the financing words a platform's entry field may lead with: the recurrence veto's financing words, and
#: FUNDING or FUNDED except on the settlements of the three platforms that print it (§7.0).
_ENTRY_FINANCING_LEAD = re.compile(
    r"(?:LOANS?|CAPITAL|CAPI|CAPIT|CAPITA|CAPSEC|ADVANCES?|FINANC\w*|LEND\w*|CASH ADV\w*|FUNDING|FUNDED"
    r"|CAP\d*(?:SEC)?|FIN|ADV|MCA)\b"
)


def platform_entry_leads_with_financing(text: str, entity: str | None, account_name: str | None = None) -> bool:
    """§7.2: a processor, marketplace or platform credit whose entry field leads with a financing word (CAPITAL,
    LENDING, LOAN, ADVANCE, FUNDING, FINANCING and their cuts): the platform's own financing, never its settlement of
    the business's sales, for any holder. FW wave 3 (W2-1): on a store-name platform, an entry whose words are a
    consecutive run of the holder's own name is the store's name ('DES:CAPITAL GRILLE'), never financing
    (_store_name_run)."""
    words = _platform_entry_words(text, entity)
    found = _ENTRY_FINANCING_LEAD.match(" ".join(words)) if words else None
    if found is None:
        return False
    if entity in _STORE_NAME_PAYOUT_ENTITIES and _store_name_run(words, text, account_name):
        return False
    return not (found.group(0) in {"FUNDING", "FUNDED"} and entity in _FUNDING_SETTLEMENT_ENTITIES)
