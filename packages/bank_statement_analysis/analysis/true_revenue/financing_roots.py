"""Financing roots and deposit-location readings."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from typing import Sequence

from analysis.classification_registry import P2P_SENDING_BANK_NAMES
from analysis.descriptor.credit_words import (
    _BILL_COM,
    _INVOICE_NUMBER,
    _PAYER_REMITTANCE_CREDIT_PATTERNS,
    _PAYMENT_CHANNEL_WORD,
)
from analysis.descriptor.lexical import _before_receiver, _joined_text, company_form, payer_name
from analysis.descriptor.rails import _is_wire_row
from analysis.descriptor.words import _BRANCH_DEPOSIT_TRANSIT, _CASH_BRANCH_ATM_FORM, _CHECK_DEPOSIT_FORM
from analysis.true_revenue.channel import _channel, _p2p_rail
from analysis.true_revenue.hold_text import _hold_text, _prints_payer_name_field
from analysis.true_revenue.holder_names import _p2p_person_name, _without_holder_name
from analysis.true_revenue.sender import _p2p_sender_region, _statement_bank_forms, _statement_bank_names
from analysis.true_revenue.words import (
    _DEPOSIT_CHANNELS,
    _ENTRY_COMPANY_FORM,
    _FINANCING_ROOT,
    _HOLD_POSTING_LABELS,
    _P2P_LAYOUT_PHRASES,
    _STREET_NAME,
    _STREET_SUFFIXES,
    _US_STATE_TAIL,
    _WHOLE_WORD_ROOT,
)


#: §8.1, T4: the whole-word CREDIT a payer name may print. The plural CREDITS is a statement's section word ('DEPOSITS
#: AND CREDITS', 'OTHER CREDITS', printed after a deposit when a page header or footer is glued on, or as a layout's
#: posting word), never a lender's name word: it is no root, glued or whole (the glued arm above spares it too).
#: Except before a company form, after another name word, in a payer region ('<NAME> CREDITS LLC'), where it is a
#: lender's name word as the whole-word CREDIT is (_FORMED_CREDITS).
_WHOLE_CREDIT = re.compile(r"\bCREDIT\b")
_FORMED_CREDITS = re.compile(
    r"(?<=[A-Z] )CREDITS (?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|LLP|PLLC|PLC)\b"
)
#: §8.1, T4: text the roots are never read on, because it never names the payer. A bank's branch label after a bank's
#: name ('BOFA FIN CTR', a Bank of America financial center); the banks' page furniture ('MEMBER FDIC', 'EQUAL HOUSING
#: LENDER'); a fundraising purpose; and Wave Payments' payout entry, the forms its payouts print ('WAVE <code> FUNDIN
#: WAVE', 'WAVE FUNDING INSTRU...'; Wave Payments is the operating registry's invoice-and-receivables processor). On a
#: wire's purpose text a buyer's advance payment or prepayment for goods is no financing either (_WIRE_TRADE_PURPOSE).
_BRANCH_LABEL_WORDS = r"(?:FIN CTR|FIN CENTER|FINANCIAL CENTER|FINANCIAL CTR)"
_ROOT_FURNITURE = re.compile(r"(?<![A-Z])(?:MEMBER FDIC|EQUAL HOUSING LENDER)\b")
_FUNDRAISING = re.compile(r"(?<![A-Z])FUNDRAIS\w*")
_WAVE_PAYOUT_ENTRY = re.compile(r"(?<![A-Z])WAVE (?:[A-Z0-9]{2,6} )?FUNDIN WAVE\b|(?<![A-Z])WAVE FUNDING INSTRU\w*")
#: And the abbreviated forms a wire's purpose field prints or cuts (ADV PAYM, ADV PAYMENT, ADV PMT, ADV PYMT, ADVANCE
#: PYMT), never after MERCHANT, CASH or MCA (a merchant cash advance's own words, the full forms included). One
#: pattern, shared by a wire's purpose text (_financing_root_places, wire-only: an ACH entry's 'DES:ADV PMT' keeps
#: its root) and a payer-less deposit's reading (_deposit_location_reading).
_WIRE_TRADE_PURPOSE = re.compile(
    r"(?<![A-Z])(?<!MERCHANT )(?<!CASH )(?<!MCA )(?:(?:ADVANCE|ADV) (?:PAYM\w*|PMTS?|PYMTS?)|PRE ?PAYMENTS?)(?![A-Z])"
)
#: §8.1, T4: a whole-word CREDIT after a single letter that ends the payer region is the entry word a layout prints
#: after an originator name its field cut ('<NAME> P CREDIT', a sixteen-character name and its entry). So is the ACH
#: entry 'CREDIT NONE' ending the region after a cut name ('<NAME> CREDIT NONE'), and a credit union's DIVIDEND
#: CREDIT is a dividend (its CREDIT no root).
_CUT_NAME_ENTRY_CREDIT = re.compile(r"(?<=\b[A-Z]) CREDIT$| CREDIT NONE$|(?<=\bDIVIDEND) CREDIT\b")
#: §8.1, T4: a check, cash, branch or ATM row that prints no payer region is read once its location is removed
#: (_deposit_location_reading): a branch's label ('<NAME> FIN CTR', '... FINANCIAL CENTER') and a credit union's name
#: ('<NAME> FIN CU', '... CREDIT UNION', '... FCU'), the ATM's or branch's owner, and a street's name (_STREET_NAME:
#: '<n> CAPITAL BLVD'). What is left is read for a financing word only: a word that starts with one
#: (_FINANCING_NAME_STARTS, CREDIT aside: a posting word there) or a whole-word root, never a root inside a word (a
#: town's name, 'GLENDALE'). So a funder's name printed on a deposit ('MOBILE DEPOSIT <NAME> FUNDING LLC') still holds.
_DEPOSIT_BRANCH_LABEL = re.compile(r"(?:(?<![A-Z])[A-Z]+ )?" + _BRANCH_LABEL_WORDS + r"\b")
_DEPOSIT_CREDIT_UNION = re.compile(r"(?:(?<![A-Z])[A-Z]+ )?(?:FIN(?:ANCIAL)? )?(?:CREDIT UNION|F?CU)\b")
#: §8.1, T4: more of a deposit's location: a place a suffix names ('<n> CAPITAL CIR', '1 FINANCIAL PLAZA', '...
#: FINANCIAL DISTRICT', '... CAPITAL HEIGHTS'), up to two words before BRANCH (a branch's name, 'CAPITAL CITY BRANCH'),
#: and a town printed with its state (_DEPOSIT_TOWN_TAIL). The ATM's or branch's bank (the statement's own, a listed
#: sending bank) is removed too (_root_reading's person-to-person removal: a bank's name is never the payer). A place,
#: branch name or town that holds a kept financing word is removed only after the row's start, a number, the deposit's
#: own words or a numbered address (_deposit_location_removal).
_DEPOSIT_PLACE = re.compile(
    r"(?<![A-Z])[A-Z]+(?= (?:PLAZA|MALL|CIR|CIRCLE|CTR|CENTER|CENTRE|SQ|SQUARE|DISTRICT|HEIGHTS|PARK)\b)"
)
_DEPOSIT_BRANCH_NAME = re.compile(r"(?<![A-Z])(?:[A-Z]+ ){1,2}(?=BRANCH\b)")
#: §8.1, T4: the deposit's own words, after which a location whose first word alone is a financing word is still a
#: place ('ATM CASH DEPOSIT CAPITAL HEIGHTS MD', 'DEPOSIT CAPITAL CITY BRANCH'); after a name word it is a funder's
#: name ('MOBILE DEPOSIT <NAME> CAPITAL PLAZA', _deposit_location_removal).
_DEPOSIT_LEAD_WORDS = frozenset({
    "DEPOSIT", "DEP", "DEPOSITS", "DEPOSITED", "EDEPOSIT", "ATM", "ABM", "BRANCH", "BRCH", "BR", "COUNTER", "CREDIT",
    "TELLER", "CASH", "CHECK", "CHECKS", "CHEQUE", "MOBILE", "REMOTE", "ONLINE", "IN", "AT",
})
#: §8.1, T4: Wells Fargo's own deposit furniture, 'DEPOSIT MADE IN A BRANCH/STORE' (normalized 'BRANCH STORE'), whose
#: last word leads a place as the deposit's own words do; STORE alone never does ('<NAME> STORE CAPITAL PLAZA' holds).
_DEPOSIT_LEAD_PAIRS = frozenset({("BRANCH", "STORE")})
#: §8.1, T4: a buyer's advance purchase printed on a deposit ('ADVANCE TICKET SALES') and, as on a wire's purpose
#: (_WIRE_TRADE_PURPOSE), an advance payment or prepayment for goods: no financing.
_DEPOSIT_TRADE_PURPOSE = re.compile(
    r"(?<![A-Z])ADVANCE (?:TICKETS?|SALES?|ORDERS?|BOOKINGS?|RESERVATIONS?|REGISTRATIONS?|PURCHASES?)\b"
)
#: §8.1, T4: the financing words a deposit's reading keeps: _FINANCING_NAME_STARTS without CREDIT (a posting word
#: there) and without FUNDS and FUNDED (a hold notice's words: 'FUNDS ON HOLD', 'FUNDS AVAIL NEXT DAY'), which are
#: kept only before a company form ('<NAME> FUNDS LLC').
_DEPOSIT_FINANCING_STARTS = (
    "FUNDING", "CAPITAL", "CAPTL", "FINANC", "LENDING", "LENDER", "LOAN", "ADVANCE", "MORTGAGE", "LEASING",
    "ACCEPTANCE", "SERVICING", "PORTFOLIO",
)
_DEPOSIT_NOTICE_FUNDS = frozenset({"FUNDS", "FUNDED"})
#: §8.1, T4: on a person-to-person row the sender's bank: a credit union's name printed beside the sender ('<sender>
#: <NAME> CREDIT UNION ID ...'), one name word with its form; the listed sending banks are read with
#: _P2P_LAYOUT_PHRASES.
_P2P_CREDIT_UNION = re.compile(r"(?:(?<![A-Z])[A-Z]+ )?(?:CREDIT UNION|FCU)\b")
#: §8.1, T4: §7.9's word-end CRED arm, aligned with a glued letter on its left: a payer-name word that ends in CRED (a
#: credit provider's glued name, 'FABRICRED'), read on the payer's name only, as the whole-word CREDIT is (never an
#: entry field or a row that prints no payer's name field): never the whole word CRED, and never the whole words
#: SACRED and ACCRED (an abbreviation of accredited). Any other glued...CRED name is held.
_GLUED_CRED_NAME = re.compile(r"(?!(?:SACRED|ACCRED)$)[A-Z]+CRED")
#: §8.1, §7.9: a wire's sender whose name a line wrap splits ('F INANCIAL', 'SERVICIN G') is read across the split too,
#: as §7.9's veto reads its first six words run together. A3 review, round 3 (_wrap_split_root): a join counts only
#: when its two words together spell one of these financing words (T4's run roots, spelled out, without the
#: glued-CREDIT arm and without the abbreviation CAPTL), or a prefix of one of _WRAP_PREFIX_MIN letters or more; two
#: words that spell none make no root ('SERVICE REPAIR', 'SOLO ANALYTICS', 'ALLEN D', 'CAPT L', 'SERVICE RX').
_WRAP_FINANCING_WORDS = (
    "FINANCIAL", "FINANCE", "FINANCING", "FUNDING", "FUNDS", "FUND", "FUNDED", "CAPITAL", "LOAN", "LOANS", "LENDING",
    "LENDER", "LENDERS", "LEND", "MORTGAGE", "ADVANCE", "ADVANCES", "ACCEPTANCE", "SERVICING", "SERVICER", "LEASING",
    "PORTFOLIO",
)
_WRAP_PREFIX_MIN = 5
_STREET_SUFFIX_WORDS = frozenset(_STREET_SUFFIXES.split("|"))
#: §8.1, T4: a deposit's town, one or two words before a state's code (_US_STATE_TAIL without US and CAUS, and without
#: CO, a company form there, never Colorado's code) that ends the row or comes before a ZIP, a reference, a country or
#: 'ON <date>' ('<n> ADVANCE NC', '... CAPITAL HEIGHTS MD 1234567 ATM ID ...'). A company form is no town's word
#: ('<NAME> FUNDING LLC NY' keeps its name).
_DEPOSIT_TOWN_TAIL = re.compile(
    r"(?<![A-Z])(?:(?!(?:LLC|INC|INCORPORATED|CORP|CORPORATION|COMPANY|LTD|LIMITED|LP|LLP|PLLC|PLC)\b)[A-Z]+ ){1,2}(?:"
    + "|".join(sorted(_US_STATE_TAIL - {"US", "CAUS", "CO"}))
    + r")(?=\s*$| \d| US\b| USA\b| ON \d)"
)


def financing_named(
    text: str, region: str, entry: str, account_name: str | None, *, bank: str | None = None,
    also: Sequence[str] = (),
) -> bool:
    """§8.1, T4: a financing root in the payer region or the entry fields (posting labels removed, and the holder's
    own name runs removed first: its whole account name, and a run of its first two words or more,
    _without_holder_name), or, on a row with no payer region, in the row before its receiver fields. A whole-word
    CREDIT counts only inside a payer name, next to another name word.

    The roots are never read on text that names no payer. A cash, branch, ATM or check deposit with no payer region
    prints its location ('<n> GLENDALE <state>', '<n> CAPITAL BLVD', '<NAME> FIN CU <street>'), so it is never read. On
    every row a bank's branch label after a bank's name ('BOFA FIN CTR'), the banks' page furniture (MEMBER FDIC, EQUAL
    HOUSING LENDER), a fundraising purpose and Wave Payments' payout entry are removed (_root_reading). On a
    person-to-person row the sender's bank (a listed sending bank, the statement's bank, a credit union's name) is
    removed, and a sender that reads as a person's name is not read (_p2p_person_name: a surname that holds LEND or
    FUND). On a wire's purpose text a buyer's advance payment or prepayment for goods is removed (_WIRE_TRADE_PURPOSE).
    A whole-word CREDIT ending the payer region after a single letter is the entry word a cut originator name prints
    ('<NAME> P CREDIT'), and the plural CREDITS is no root (_WHOLE_CREDIT) unless a company form follows it in the
    payer region. A payer-less deposit row is read once its location is removed (_deposit_location_reading), for whole
    financing words only, so a funder's name printed on it still holds; its bank, a place, a branch's name, a town
    printed with its state, a buyer's advance purchase and a hold notice's FUNDS are removed or never kept too.

    The reading is _financing_root_places', place by place; this is whether any place fired (bool of the places),
    unchanged."""
    return bool(_financing_root_places(text, region, entry, account_name, bank=bank, also=also))


@dataclass(frozen=True)
class _RootPlaces:
    """§8.1: where financing_named's roots fire, place by place. `payer` is the payer reading when a root, or one of the
    special payer arms, fires there (`payer_arm`: the whole-word or formed CREDIT arm, a glued...CRED name or a wire's
    wrap-split root); `entry` the entry reading when a root fires there; `row` the payer-less reading (a check, cash,
    branch or ATM deposit's reading, or the row's reading on a row with no payer region) when a root fires there. None
    where none fires. True when any place fired."""

    payer: str | None = None
    payer_arm: bool = False
    entry: str | None = None
    row: str | None = None

    def __bool__(self) -> bool:
        return self.payer is not None or self.entry is not None or self.row is not None


def _financing_root_places(
    text: str, region: str, entry: str, account_name: str | None, *, bank: str | None = None,
    also: Sequence[str] = (),
) -> _RootPlaces:
    """§8.1, T4 (financing_named's reading): the places a financing
    root fires on, each read as financing_named always read it. Every place is computed: a special payer arm (the
    whole-word or formed CREDIT, a glued ...CRED name, a wire's wrap-split root) no longer ends the reading, so the
    underwriter's Q9 release (finance_named_release) sees an entry root printed beside it. bool() of the result is
    financing_named's answer on every input."""
    channel = _channel(text, bank)
    if not region and channel in _DEPOSIT_CHANNELS:
        reading = _deposit_location_reading(text, account_name, bank, also=also)
        return _RootPlaces(row=reading) if _FINANCING_ROOT.search(reading) is not None else _RootPlaces()
    row = _before_receiver(text)
    p2p = channel == "person_to_person" and _p2p_rail(row)
    wire = _is_wire_row(text)
    if region:
        payer = _root_reading(_HOLD_POSTING_LABELS.sub(" ", region), account_name, bank, p2p=p2p, also=also)
        if p2p and _p2p_person_name(payer):
            payer = ""
        payer = _CUT_NAME_ENTRY_CREDIT.sub("", payer.strip())
        name_words = payer_name(payer).split()
        payer_arm = bool(
            (len(name_words) >= 2 and (_WHOLE_CREDIT.search(" ".join(name_words)) or _FORMED_CREDITS.search(payer)))
            # A3 review, rounds 2 and 3: a glued ...CRED word, on a payer's name field or a company-formed payer region.
            or (
                (_prints_payer_name_field(text) or company_form(" ".join(name_words)))
                and any(_GLUED_CRED_NAME.fullmatch(word) for word in name_words)
            )
            # A3: a wire's sender split by a line wrap, read across the split (§7.9's wrap-tolerant reading); A3
            # review, rounds 2 and 3: on every wire sender, labelled or not, where the two words spell a financing word.
            or (wire and _wrap_split_root(text, payer))
        )
        entry_place = None
        if entry:
            purpose = _HOLD_POSTING_LABELS.sub(" ", entry)
            if wire:
                purpose = _WIRE_TRADE_PURPOSE.sub(" ", purpose)
            reading = _root_reading(purpose, account_name, bank, p2p=False, also=also)
            if _FINANCING_ROOT.search(reading):
                entry_place = reading
        return _RootPlaces(
            payer=payer if payer_arm or _FINANCING_ROOT.search(payer) else None,
            payer_arm=payer_arm,
            entry=entry_place,
        )
    reading = _root_reading(_hold_text(text), account_name, bank, p2p=p2p, also=also)
    if p2p:
        # A sender printed without FROM (its rail's reading, _p2p_sender_region): a person's name words are removed one
        # by one (the reading skips single letters and generic words between them).
        sender = _p2p_sender_region(text)
        if sender and _p2p_person_name(sender):
            for word in sender.split():
                reading = re.sub(r"(?<![A-Z0-9])" + re.escape(word) + r"(?![A-Z0-9])", " ", reading)
    return _RootPlaces(row=reading) if _FINANCING_ROOT.search(reading) else _RootPlaces()


def _root_reading(
    words: str, account_name: str | None, bank: str | None, *, p2p: bool, also: Sequence[str] = (),
) -> str:
    """§8.1, T4: the words the financing roots are read on: without the holder's own name runs (_without_holder_name,
    its whole account name always), a bank's branch label after a bank's name, the banks' page furniture, a
    fundraising purpose and Wave Payments' payout entry; on a person-to-person row (`p2p`) without the sender's bank
    too: a listed sending bank (_P2P_LAYOUT_PHRASES), the statement's own bank and a credit union's name
    (_P2P_CREDIT_UNION)."""
    words = _without_holder_name(words, account_name, whole_name=True, also=also)
    words = _branch_label(bank).sub(" ", words)
    words = _ROOT_FURNITURE.sub(" ", words)
    words = _FUNDRAISING.sub(" ", words)
    words = _WAVE_PAYOUT_ENTRY.sub(" ", words)
    if p2p:
        words = _P2P_LAYOUT_PHRASES.sub(" ", words)
        own = _statement_bank_names(bank) if bank else None
        if own is not None:
            words = own.sub(" ", words)
        words = _P2P_CREDIT_UNION.sub(" ", words)
    return words


def _deposit_location_reading(
    text: str, account_name: str | None, bank: str | None, *, also: Sequence[str] = (),
) -> str:
    """§8.1, T4: the words a payer-less check, cash, branch or ATM row's roots are read on: the row's root reading
    (_root_reading) without its location (a branch's label, a credit union's name, a street's name), keeping only the
    words that start with a financing word (CREDIT aside) or are a whole-word root. A town's name holding a root
    ('GLENDALE') is never read. Nor the ATM's or branch's bank (the statement's own, a listed sending bank: the
    person-to-person removal), a place a suffix names (_DEPOSIT_PLACE), a branch's name (_DEPOSIT_BRANCH_NAME), a town
    printed with its state (_DEPOSIT_TOWN_TAIL), a buyer's advance purchase or payment (_DEPOSIT_TRADE_PURPOSE,
    _WIRE_TRADE_PURPOSE), or a hold notice's FUNDS or FUNDED (kept only before a company form:
    _DEPOSIT_FINANCING_STARTS)."""
    words = _root_reading(_hold_text(text), account_name, bank, p2p=True, also=also)
    words = _DEPOSIT_BRANCH_LABEL.sub(" ", words)
    words = _DEPOSIT_CREDIT_UNION.sub(" ", words)
    words = _STREET_NAME.sub(" ", words)
    # The place, branch name and town are removed only where no name word stands before their
    # financing word (_deposit_location_removal). Read with the statement's bank, so arm S's whole-row match lifts
    # the location guard on Scotiabank's statements only.
    for location in (_DEPOSIT_PLACE, _DEPOSIT_BRANCH_NAME, _DEPOSIT_TOWN_TAIL):
        words = location.sub(lambda found: _deposit_location_removal(found, bank=bank), words)
    words = _DEPOSIT_TRADE_PURPOSE.sub(" ", words)
    words = _WIRE_TRADE_PURPOSE.sub(" ", words)
    split = words.split()
    return " ".join(
        word for index, word in enumerate(split)
        if word.startswith(_DEPOSIT_FINANCING_STARTS)
        or _WHOLE_WORD_ROOT.fullmatch(word) is not None
        or (word in _DEPOSIT_NOTICE_FUNDS and _ENTRY_COMPANY_FORM.match(" ".join(split[index + 1:])) is not None)
    )


def _deposit_location_removal(found: re.Match[str], *, bank: str | None = None) -> str:
    """§8.1, T4: a place, a branch's name or a town is removed from a deposit's reading as before when it holds no
    financing word the reading keeps (_deposit_kept_word). One that holds one is removed only when that word is the
    match's first word and its only kept word, and the token just before the match is the row's start, a token with a
    digit or a mask ('1 ADVANCE NC'), one of the deposit's own words (_DEPOSIT_LEAD_WORDS: 'DEPOSIT CAPITAL CITY
    BRANCH', 'ATM CASH DEPOSIT CAPITAL HEIGHTS MD'; and Wells Fargo's 'BRANCH/STORE', _DEPOSIT_LEAD_PAIRS), a word
    inside the classifier's check or cash, branch or ATM form (_inside_a_deposit_form: 'NIGHT DROP CAPITAL PLAZA'), or
    the street suffix that ends a numbered address. Otherwise the match stays, so a funder's name before a location
    keeps its financing word ('MOBILE DEPOSIT <NAME> FUNDING <town> <ST>', '<NAME> CAPITAL PLAZA', '<NAME> CAPITAL CITY
    BRANCH') and holds. The deposit form is read with the statement's `bank` (_inside_a_deposit_form: arm S's whole-row
    match counts on Scotiabank's statements only)."""
    location = found.group(0).split()
    kept = [word for word in location if _deposit_kept_word(word)]
    if not kept:
        return " "
    if len(kept) > 1 or not _deposit_kept_word(location[0]):
        return found.group(0)
    before = found.string[: found.start()].split()
    if (
        not before or _numbered_token(before[-1]) or before[-1] in _DEPOSIT_LEAD_WORDS
        # Wells Fargo's 'DEPOSIT MADE IN A BRANCH/STORE <place>' (_DEPOSIT_LEAD_PAIRS).
        or tuple(before[-2:]) in _DEPOSIT_LEAD_PAIRS
        # The street suffix that ends a numbered address ('<n> MAIN ST CAPITAL HEIGHTS MD', its name removed by
        # _STREET_NAME): the town follows the ATM's or branch's address.
        or (before[-1] in _STREET_SUFFIX_WORDS and any(_numbered_token(token) for token in before[-3:-1]))
        or _inside_a_deposit_form(found.string, found.start(), bank)
    ):
        return " "
    return found.group(0)


def _numbered_token(token: str) -> bool:
    """§8.1, T4: a token that holds a digit or a mask ('#')."""
    return "#" in token or any(character.isdigit() for character in token)


def _deposit_kept_word(word: str) -> bool:
    """§8.1, T4: a word a deposit's reading keeps as a financing word: it starts with one (_DEPOSIT_FINANCING_STARTS)
    or is a whole-word root (_WHOLE_WORD_ROOT)."""
    return word.startswith(_DEPOSIT_FINANCING_STARTS) or _WHOLE_WORD_ROOT.fullmatch(word) is not None


def _inside_a_deposit_form(words: str, start: int, bank: str | None = None) -> bool:
    """§8.1, T4: the token just before a deposit's location (which starts at `start` in `words`) is a word inside a match
    of the classifier's check-deposit form (_CHECK_DEPOSIT_FORM) or its cash, branch or ATM form (_CASH_BRANCH_ATM_FORM),
    read from each word's start so an overlapping match is found: the location follows, or sits inside, the deposit's own
    words (Wells Fargo's 'ATM CHECK DEPOSIT ON <date> <address> <town> <ST> <n> ATM ID ...', inside the form's DEPOSIT ...
    ATM arm; 'NIGHT DROP <place>').

    On a statement whose bank field (`bank`) is not Scotiabank's (_SCOTIABANK), arm S's whole-row match (the
    classifier's _BRANCH_DEPOSIT_TRANSIT, the form's last alternative) never counts: the form is read without it
    (_cash_form_without_arm_s), so the location guard holds a financing word after a name word there ('DEPOSIT <NAME>
    CAPITAL PLAZA <transit> <sequence>'), as before arm S. On Scotiabank's statements the words are the branch's printed
    name and arm S counts as before. Arm S's channel reading is unchanged (spec §17.1 (3))."""
    before = words[:start].rstrip()
    cash = (
        _CASH_BRANCH_ATM_FORM if _SCOTIABANK.search((bank or "").upper()) is not None
        else _cash_form_without_arm_s()
    )
    return any(
        (found := form.match(words, word.start())) is not None and found.end() >= len(before)
        for form in (_CHECK_DEPOSIT_FORM, cash)
        for word in re.finditer(r"\S+", before)
    )


#: §8.1, T4: the bank field of a Scotiabank statement (upper-cased), whose arm-S branch deposits print the branch's
#: own name.
_SCOTIABANK = re.compile(r"(?<![A-Z])(?:SCOTIABANK|SCOTIA|BANK OF NOVA SCOTIA|BANQUE SCOTIA)\b")


@cache
def _cash_form_without_arm_s() -> re.Pattern[str]:
    """§8.1, T4: the classifier's cash, branch or ATM form without its last alternative, arm S
    (_BRANCH_DEPOSIT_TRANSIT), for _inside_a_deposit_form off Scotiabank's statements. A match the full form makes with
    an earlier alternative is the same match here (the alternation tries arm S last)."""
    pattern = _CASH_BRANCH_ATM_FORM.pattern
    arm_s = "|" + _BRANCH_DEPOSIT_TRANSIT
    if not pattern.endswith(arm_s):
        raise RuntimeError("the cash, branch or ATM form no longer ends with arm S")
    return re.compile(pattern[: -len(arm_s)])


@cache
def _branch_label(bank: str | None) -> re.Pattern[str]:
    """§8.1, T4: a bank's branch label printed after a bank's name, a listed sending bank's or the statement's own
    ('BOFA FIN CTR', 'BANK OF AMERICA FINANCIAL CENTER')."""
    names = set(P2P_SENDING_BANK_NAMES) | {"BKOFAMERICA"}
    if bank:
        names.update(_statement_bank_forms(bank))
    alternatives = "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))
    return re.compile(r"(?<![A-Z])(?:" + alternatives + r") " + _BRANCH_LABEL_WORDS + r"\b")


def _wrap_split_root(text: str, payer: str) -> bool:
    """§8.1, §7.9: a financing word that a line wrap split across two of the wire sender's first six words (those with
    no digit): the two words together spell a financing word (_WRAP_FINANCING_WORDS) or a prefix of one of
    _WRAP_PREFIX_MIN letters or more, so the join falls inside it ('F INANCIAL', 'SERVICIN G', 'LO AN', 'MORT G'). Two
    words that spell none never make one ('SERVICE REPAIR', 'ALLEN D', 'HELEN DE', 'CAPT L', and a Fedwire sender's city
    and state, 'GLEN DE', 'LAMORT GA'). No city and state skip (a company form CO is no state code: 'NORTHWIND F
    INANCIAL CO' is held)."""
    words = [token for token in payer.split() if not any(ch.isdigit() for ch in token)][:6]
    for left, right in zip(words, words[1:]):
        joined = left + right
        if joined in _WRAP_FINANCING_WORDS or (
            len(joined) >= _WRAP_PREFIX_MIN and any(word.startswith(joined) for word in _WRAP_FINANCING_WORDS)
        ):
            return True
    return False


def _accounts_payable_wording(text: str) -> bool:
    """§7.5 (S4.2 fix measurement): the payer's accounts-payable or vendor-payment wording, as _payer_remittance
    matches it before its veto: an AP pattern on the row before its receiver fields or on its joined text (PAYABLES
    never on a row that prints BILL COM), or an invoice number on a row that also prints a payment-channel word."""
    row = _before_receiver(text)
    joined = _joined_text(row)
    for pattern in _PAYER_REMITTANCE_CREDIT_PATTERNS:
        found = pattern.search(row) or pattern.search(joined)
        if found is not None and not (found.group(0) == "PAYABLES" and _BILL_COM.search(row)):
            return True
    found = _INVOICE_NUMBER.search(row)
    return found is not None and _PAYMENT_CHANNEL_WORD.search(
        row[: found.start()] + " " + row[found.end():]
    ) is not None
