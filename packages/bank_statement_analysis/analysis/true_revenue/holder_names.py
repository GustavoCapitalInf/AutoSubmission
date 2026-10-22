"""The holder's names as pass 7 strips them; receiver-holder names."""
from __future__ import annotations

import re
from functools import cache
from typing import Sequence, TYPE_CHECKING

from analysis.classification.counter_debit_reading import _payer_first_distinctive_word, _payer_key
from analysis.descriptor.holder import _summary_grid_header, account_name_text, account_product, holder_reading
from analysis.descriptor.lexical import _before_receiver, _is_reference_token, company_form, payer_name, revenue_text
from analysis.descriptor.payer import payer_region
from analysis.descriptor.rails import _is_wire_row, _without_receiver_value
from analysis.descriptor.words import (
    HOLDER_NOISE,
    REVENUE_GENERIC_WORDS,
    _HOLDER_TEST_NOISE,
    _HOLDER_TRADE_NAME,
    _PUSH_RAIL,
    _RECEIVER_FIELD_VALUE,
)
from analysis.true_revenue.channel import _channel
from analysis.true_revenue.words import (
    _HOLDER_RUN_CUT_FROM,
    _HOLDER_RUN_CUT_KEEPS,
    _RECEIVER_BANK_WORDS,
    _RECEIVER_LABEL,
    _TRUST_BUSINESS_WORDS,
    _WHOLE_WORD_ROOT,
)

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


#: §8.1, T4: the financing words a person's name never starts with; a person-to-person sender whose name holds one
#: (or a whole-word root) is read as a name that may be a lender's ('TRUE FINANCE', 'FAST FUNDING').
_FINANCING_NAME_STARTS = (
    "FUNDING", "FUNDS", "FUNDED", "CAPITAL", "CAPTL", "FINANC", "LENDING", "LENDER", "LOAN", "ADVANCE", "MORTGAGE",
    "LEASING", "CREDIT", "ACCEPTANCE", "SERVICING", "PORTFOLIO",
)
#: §8.1 (A3-G refinement): a holder's name read from the statement's own incoming receiver fields (INDN, IND NAME,
#: RECEIVER NAME) needs this many credits, words and letters; a run-together match needs this many letters.
_RECEIVER_HOLDER_MIN_CREDITS = 2
_RECEIVER_HOLDER_MIN_WORDS = 2
_RECEIVER_HOLDER_MIN_LETTERS = 8
_RECEIVER_HOLDER_RUN_LETTERS = 12


#: §8.1: the legal forms a holder's name run may print after it, or leave off.
_HOLDER_RUN_FORM = r"(?: (?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|LLP|PLLC|PLC))?"


@cache
def _holder_runs(account_name: str | None, whole_name: bool) -> re.Pattern[str] | None:
    """§8.1: the holder's own name as a row prints it when the bank prints the receiver with no label: the account
    name's whole run (`whole_name`: any name of two or more words, as T4's root test always removed it), and, when the
    account name names the holder (_usable_holder_name: a company form or a person's name, never a product name such as
    'BUSINESS REWARDS CHECKING'), each run of its first two words or more, with the legal form printed or left off
    ('NORTHWIND DISTRIBUTION' for 'NORTHWIND DISTRIBUTION LLC'). Longest first; None when there is none. The runs of
    each side of a name that joins two (_HOLDER_NAME_MARKER: DBA, AKA, 'Operating as') that names a holder too, and a
    run whose last word has _HOLDER_RUN_CUT_FROM letters or more cut by the bank's field to _HOLDER_RUN_CUT_KEEPS
    letters or more at the row's end ('NORTHWIND DISTRIBUTIO'). The row-end cuts are tried before the whole-word runs at
    each word, so a name of three words or more cut in its third word or later ('FABRIKAM COASTAL DISTRIBUT') is removed
    whole, never its first two words alone; and a leading THE is no word of a run: a side that leads with it builds its
    runs from its words after THE (two words or more), each read bare and with THE before it, so no 'THE <one word>' run
    or cut removes a third party's words (the whole-name run stays as printed)."""
    holder = account_name_text(account_name)
    words = holder.split()
    runs = set()
    if whole_name and len(words) >= 2:
        runs.add(holder)
    sides = _HOLDER_NAME_MARKER.split(holder)
    for side in (holder, *sides) if len(sides) > 1 else (holder,):
        side = side.strip()
        if _usable_holder_text(side):
            side_words = side.split()
            lead = ""
            if side_words[:1] == ["THE"]:
                side_words, lead = side_words[1:], "THE "
            for count in range(2, len(side_words) + 1):
                run = " ".join(side_words[:count])
                runs.update((run, lead + run) if lead else (run,))
    if not runs:
        return None
    names = "|".join(re.escape(run) for run in sorted(runs, key=len, reverse=True))
    pattern = r"(?<![A-Z0-9])(?:" + names + r")" + _HOLDER_RUN_FORM + r"(?![A-Z0-9])"
    cuts = sorted({
        cut for run in runs
        if not (run.startswith("THE ") and len(run.split()) < 3) and (cut := _holder_run_cut(run)) is not None
    }, key=len, reverse=True)
    if cuts:
        pattern = r"(?<![A-Z0-9])(?:" + "|".join(cuts) + r")\s*$|" + pattern
    return re.compile(pattern)


def _holder_run_cut(run: str) -> str | None:
    """§8.1: the pattern of a holder run whose last word the bank cut: its other words whole and its last word's first
    _HOLDER_RUN_CUT_KEEPS letters or more ('NORTHWIND DIST', 'NORTHWIND DISTRIBUTIO' for 'NORTHWIND DISTRIBUTION'); None
    when its last word is shorter than _HOLDER_RUN_CUT_FROM letters or holds a non-letter."""
    words = run.split()
    last = words[-1]
    if len(words) < 2 or len(last) < _HOLDER_RUN_CUT_FROM or not last.isalpha():
        return None
    tail = ""
    for letter in reversed(last[_HOLDER_RUN_CUT_KEEPS:]):
        tail = f"(?:{re.escape(letter)}{tail})?"
    return re.escape(" ".join(words[:-1])) + " " + re.escape(last[:_HOLDER_RUN_CUT_KEEPS]) + tail


def _without_holder_name(
    row: str, account_name: str | None, *, whole_name: bool = False, also: Sequence[str] = (),
) -> str:
    """§8.1: `row` with the holder's own name runs removed (_holder_runs), so a hold word inside the holder's name
    (DISTRIBUTION, CAPITAL, PAYROLL, RETIREMENT, RETURNS) never holds a third party's payment printed with an unlabelled
    receiver. Read before the possible-return, financing-root, pay, personal-income and non-sale tests. And then each of
    `also`'s names (the holder's other business names, _holder_strip_names), whole and by its runs."""
    runs = _holder_runs(account_name, whole_name) if account_name else None
    row = runs.sub(" ", row) if runs is not None else row
    for name in also:
        extra = _holder_runs(name, True)
        if extra is not None:
            row = extra.sub(" ", row)
    return row


def _holder_strip_names(record: TransactionClassification) -> tuple[str, ...]:
    """§8.1: the holder's business names the holder-name strip removes beside the holder's own name (_holder): of the
    holder's name, and of the account-name field when the holder hold reads it as a second name (_holder_names), the
    trade side of a DBA name always and its legal side when it prints a company form; and an account-name field with no
    DBA that reads as no person's name (_p2p_person_name). Names of two words or more only. Never a person's name:
    stripping the owner's name would count the owner's pay from another company (Q8)."""
    return _holder_strip_names_of(record.account_name, record.holder_name)


def _holder_strip_names_of(account_name: str | None, holder_name: str | None) -> tuple[str, ...]:
    """_holder_strip_names on a statement's account-name field and holder name (so the classifier's Cherry veto reads
    the names before a record exists)."""
    names = _holder_names_of(account_name, holder_name)
    stripped: list[str] = []
    for index, name in enumerate(names):
        printed = account_name_text(name)
        sides = _HOLDER_TRADE_NAME.split(printed, maxsplit=1)
        if len(sides) == 2:
            legal, trade = (side.strip() for side in sides)
            stripped.append(trade)
            if company_form(legal):
                stripped.append(legal)
        elif index > 0 and not _p2p_person_name(printed):
            stripped.append(printed)
    return tuple(dict.fromkeys(name for name in stripped if len(name.split()) >= 2))


def _p2p_person_name(name: str) -> bool:
    """§8.1, T4: a person-to-person sender that reads as a person's name: two to five name words once its reference
    tokens are skipped, each of letters only, no company form, no holder-noise, generic, business or institution
    word, and no word that is a whole-word root or starts with a financing word (_FINANCING_NAME_STARTS: 'TRUE
    FINANCE', 'FAST FUNDING' and 'NORTHWIND CAPITALCO' are no person). A root inside a surname ('LENDSAMPLE',
    'FUNDERSON') is never read on it."""
    words = [word for word in name.split() if not _is_reference_token(word)]
    if not 2 <= len(words) <= 5 or company_form(" ".join(words)):
        return False
    return all(
        word.isalpha() and word not in HOLDER_NOISE and word not in REVENUE_GENERIC_WORDS
        and _TRUST_BUSINESS_WORDS.search(word) is None and _WHOLE_WORD_ROOT.fullmatch(word) is None
        and not word.startswith(_FINANCING_NAME_STARTS)
        for word in words
    )


def _holder(record: TransactionClassification) -> str | None:
    """The holder's name the holds read: the statement's holder name when its parser read one, else its
    account-name field (classifier.holder_reading)."""
    return holder_reading(record.account_name, record.holder_name)


def _holder_names(record: TransactionClassification) -> tuple[str, ...]:
    """§5.2, §8.1: the names the holder hold reads: the holder's name (_holder), and, beside a parser's holder name, the
    account-name field when it names a holder too (_usable_holder_name: a person or a company, never a product; never a
    product a holder reader publishes, PNC's 'Treasury Enterprise Plan' included), as each side of a DBA name is read: a
    layout that prints the owner there keeps the owner's own money held."""
    return _holder_names_of(record.account_name, record.holder_name)


def _holder_names_of(account_name: str | None, holder_name: str | None) -> tuple[str, ...]:
    """_holder_names on a statement's account-name field and holder name."""
    holder = holder_reading(account_name, holder_name)
    names = [holder] if holder else []
    if holder_name and account_name and _usable_holder_name(account_name):
        if account_name_text(account_name) != account_name_text(holder):
            names.append(account_name)
    return tuple(names)


#: §5.2: the legal forms a holder's name may end with that the classifier's company form leaves out: a trailing CO
#: after two words or more (holder_name._LEGAL_FORMS counts it; the payer readers never do, since CO is also
#: Colorado's code, D11, while a header or mailing-block name prints no address), and Quebec's partnership S.E.N.C.
#: (normalized 'S E N C') or SENC. A city and state ('SAMPLEVILLE CO') stays no name.
_HOLDER_TRAILING_FORM = re.compile(r"^\S+ \S+ (?:.* )?CO$|^\S+ (?:.* )?(?:S E N C|SENC)$")
#: §5.2: the markers that join two names of the holder's inside its name: a trade name (the classifier's
#: _HOLDER_TRADE_NAME: DBA, D B A, AKA) and BMO's 'Operating as:'.
_HOLDER_NAME_MARKER = re.compile(r" (?:DBA|D B A|AKA|OPERATING AS) ")
#: §5.2: the words a partnership's name joins its partners with ('&' normalizes to AND).
_HOLDER_PARTNER_WORDS = frozenset({"AND"})


def _usable_holder_name(account_name: str | None) -> bool:
    """§5.2 (A3-G refinement): the holder's name (`account_name`: holder_reading's name) names its holder: a company
    form, or a person's name (two to four words of letters, none a product, noise or generic word). A product name
    ('BUSINESS ADVANTAGE CHECKING') or an empty field names nobody. Nor does Chase's summary grid header ('INSTANCES
    AMOUNT') or a name of the holder test's bank and product abbreviations (BMO BUS CKG, GENERAL). Nor a product a
    holder reader publishes, whose words are no noise (classifier.account_product: PNC's 'Treasury Enterprise Plan'). A
    holder's own legal forms the company form leaves out name it too (_HOLDER_TRAILING_FORM: a trailing CO after two
    words or more, S.E.N.C.); a name that joins two names (_HOLDER_NAME_MARKER: DBA, AKA, BMO's 'Operating as') names
    its holder when either side does; and a leading THE and a partnership's AND between words are read as no word of the
    name. A name of five words or more with no form still names nobody."""
    return _usable_holder_text(account_name_text(account_name))


def _usable_holder_text(name: str) -> bool:
    """§5.2: _usable_holder_name on a normalized name."""
    if not name or _summary_grid_header(name):
        return False
    if company_form(name) or _HOLDER_TRAILING_FORM.search(name):
        return True
    if account_product(name):
        return False
    sides = _HOLDER_NAME_MARKER.split(name)
    if len(sides) > 1:
        return any(_usable_holder_text(side.strip()) for side in sides)
    words = name.split()
    if words and words[0] == "THE":
        words = words[1:]
    words = [
        word for index, word in enumerate(words)
        if not (word in _HOLDER_PARTNER_WORDS and 0 < index < len(words) - 1)
    ]
    return 2 <= len(words) <= 4 and all(
        word.isalpha() and word not in _HOLDER_TEST_NOISE and word not in REVENUE_GENERIC_WORDS
        for word in words
    )


def _holder_name_known(name: str | None) -> bool:
    """§5.2, §8.1: the holder's name is known well enough to switch the receiver fields' holder names off
    (_receiver_holder_names): a usable name (_usable_holder_name) with a company form or three words or more. A bare
    two-word fragment needs corroboration, so the receiver fields are still read beside it."""
    if not _usable_holder_name(name):
        return False
    text = account_name_text(name)
    return company_form(text) or len(text.split()) > 2


def _receiver_holder_names(records: Sequence[TransactionClassification], credits: Sequence[int]) -> tuple[str, ...]:
    """§5.2, §8.1 (A3-G refinement): when the statement's account-name field names nobody (_holder_name_known, which
    lets a bare two-word fragment through to corroboration, and is read beside the parser's holder name, never
    instead of it), the holder's names its own incoming receiver fields print (INDN, IND NAME, RECEIVER NAME: an ACH
    credit's receiver is the holder), each on _RECEIVER_HOLDER_MIN_CREDITS credits or more, with
    _RECEIVER_HOLDER_MIN_WORDS words and _RECEIVER_HOLDER_MIN_LETTERS letters or more, naming no bank, and holding a
    word that is no product, noise or generic word. Read by the holder hold only (the holder's name is never a
    payer), never to verify anything. The credits must come from _RECEIVER_HOLDER_MIN_CREDITS distinct originators
    or more: a receiver constant across payers is the holder, while a name one platform prints (a rent platform's
    tenant) is its customer. Originators are compared by the payer's first distinctive word, the word the classifier
    groups a payer by (_payer_first_distinctive_word; the payer key where it holds none), so one platform's two
    spellings are one originator ('SAMPLE RENT PAY', 'SAMPLE RENT PAYMENTS')."""
    # An account name that names the holder beyond a bare two-word fragment (_holder_name_known) switches the
    # receiver fields off. A holder's name the parser read never does: the receiver fields can name the holder's
    # owner (the bank prints the owner as the receiver), whose own money the holder hold keeps.
    if not credits or _holder_name_known(records[credits[0]].account_name):
        return ()
    originators: dict[str, set[str]] = {}
    for index in credits:
        text = revenue_text(records[index].normalized_description)
        region = payer_region(text)
        payer = (
            _payer_first_distinctive_word(region) or " ".join(_payer_key(region))
            or _before_receiver(text)
        )
        for found in _RECEIVER_FIELD_VALUE.finditer(records[index].normalized_description):
            value = _RECEIVER_LABEL.sub("", found.group(0), count=1)
            words = [token for token in value.split() if token.isalpha() and len(token) > 1]
            if words:
                originators.setdefault(" ".join(words), set()).add(payer)
    return tuple(
        name for name, payers in originators.items()
        if len(payers) >= _RECEIVER_HOLDER_MIN_CREDITS and len(name.split()) >= _RECEIVER_HOLDER_MIN_WORDS
        and sum(len(word) for word in name.split()) >= _RECEIVER_HOLDER_MIN_LETTERS
        and _RECEIVER_BANK_WORDS.search(name) is None
        and any(word not in HOLDER_NOISE and word not in REVENUE_GENERIC_WORDS
                for word in name.split())
    )


def _receiver_alias_reads(record: TransactionClassification, text: str) -> bool:
    """§5.2 (A3-G refinement, final): the rows a receiver-field holder name is read on: a wire (a book transfer
    included) or a transfer or person-to-person row (Zelle, Venmo, an online, mobile, book or internal transfer), where
    the holder moves its own money. Never an ACH, card, processor or marketplace settlement row (a platform prints the
    store's own name as its payer), and never a row an earlier rule verified on sale evidence (a card settlement, a
    platform payout, an accounts-payable remittance, a public payer). The wire is the classified wire layout (an
    incoming-wire label or a third-party book transfer, _is_wire_row), never the word WIRE printed anywhere ('<payer>
    DES:WIRE PMT' is an ACH row)."""
    if record.revenue_classification == "verified_revenue":
        return False
    if _is_wire_row(text):
        return True
    # A real-time or push rail also carries a platform's payout (Visa Direct, RTP): never read there.
    return _channel(text) == "person_to_person" and not _PUSH_RAIL.search(_before_receiver(text))


def _receiver_holder_named(payer: str, holder: str) -> bool:
    """§5.2 (A3-G refinement, narrowed variant): the payer is the holder that a receiver field names: the two names run
    together where one starts the other and the shorter keeps _RECEIVER_HOLDER_RUN_LETTERS letters (a receiver field
    and an originator field cut the same name at different widths). The broad holder test (a shared first word) is not
    read against a receiver name."""
    if not payer:
        return False
    ours = "".join(ch for ch in payer_name(payer) if ch.isalpha())
    theirs = "".join(ch for ch in holder if ch.isalpha())
    shorter = min(len(ours), len(theirs))
    return shorter >= _RECEIVER_HOLDER_RUN_LETTERS and (ours.startswith(theirs) or theirs.startswith(ours))


def without_receiver_and_holder(text: str, account_name: str | None, holder_name: str | None) -> str:
    """`text` without the receiver field's value (classifier._without_receiver_value) and without the holder's names
    (the holder-name strip's: _without_holder_name with _holder_strip_names), so a word inside the holder's own name,
    printed in a labelled receiver field or as an unlabelled one (Wells Fargo's trailing receiver, TD's ACH DEPOSIT, a
    generic ACH CREDIT), is never read. Read by the payout non-sale veto on both sides (the pass's _payout_non_sale and
    the classifier's Cherry D1 veto, _is_payout_credit, which passes the statement's account-name field and holder name
    before a record exists) and by the floor-plan service wording (_dealer_activity)."""
    return _without_holder_name(
        _without_receiver_value(text), holder_reading(account_name, holder_name),
        also=_holder_strip_names_of(account_name, holder_name),
    )
