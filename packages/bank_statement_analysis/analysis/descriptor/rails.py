"""Wire, book-transfer and receiver-field readers; the alternation matcher and its memo."""
from __future__ import annotations

import re
from functools import cache
from typing import Sequence

from analysis.classification_registry import (
    FIELD_ORDER_PAYEE_FORMS,
    OPERATING_REVENUE_SOURCE_ALIASES,
    OPERATING_REVENUE_TRUNCATIONS,
    PAYEE_GROUP_REGISTRIES,
    _operating_alias_cut,
)
from analysis.description_text import normalize_transaction_description
from analysis.descriptor.credit_words import _BOOK_OR_FUNDS_TRANSFER, _EFT_FUNDS_TRANSFER
from analysis.descriptor.lexical import (
    _before_receiver,
    _is_reference_token,
    _leading_name_words,
    _originator_payer_words,
)
from analysis.descriptor.words import (
    HOLDER_NOISE,
    THIRD_PARTY_BOOK_TRANSFER_AS_WIRE,
    _AMEX_ACH_CREDIT,
    _BANK_TEMPLATE_WORDS,
    _CHANNEL_VOCABULARY,
    _CONSUMER_P2P_RAIL,
    _CREDIT_RECEIVER_FIELD,
    _CREDIT_WIRE_BENEFICIARY_VALUE,
    _ENTITY_NOISE,
    _INTERNAL_ACCOUNT_SOURCE_WORDS,
    _INTERNAL_TRANSFER_CREDIT_PATTERNS,
    _OWN_ACCOUNT_PRODUCT_WORDS,
    _PUSH_RAIL,
    _RECEIVER_VALUE_END,
    _WIRE_FIELD_END,
    _WIRE_WORD,
)
from analysis.payee_matcher import PayeeMatch


#: A tuple of rule patterns read as ONE compiled alternation, kept by the tuple's id beside the tuple itself (so an id
#: is never reused while its entry is kept; the callers pass module constants, about 85 tuples). Searching
#: `(?:p1)|(?:p2)|...` finds a match exactly when one of the patterns matches somewhere, and the alternation is built
#: only where that holds by construction: a tuple of str patterns with one set of flags, no VERBOSE flag (a `#` comment
#: would swallow the patterns joined after it), no group reference or conditional group, and an alternation that
#: compiles. Anything else keeps the loop. tests/test_matches_any_alternation.py pins both.
_ALTERNATIONS: dict[int, tuple[Sequence[object], re.Pattern[str] | None]] = {}
_GROUP_REFERENCE = re.compile(r"\\\d|\(\?P=|\(\?\(")
_ALTERNATION_LIMIT = 256


def _alternation(patterns: Sequence[object]) -> re.Pattern[str] | None:
    if not isinstance(patterns, tuple):
        return None
    found = _ALTERNATIONS.get(id(patterns))
    if found is not None and found[0] is patterns:
        return found[1]
    combined = None
    if (
        patterns
        and all(isinstance(pattern, re.Pattern) and isinstance(pattern.pattern, str) for pattern in patterns)
        and len({pattern.flags for pattern in patterns}) == 1
        and not patterns[0].flags & re.VERBOSE
        and not any(_GROUP_REFERENCE.search(pattern.pattern) for pattern in patterns)
    ):
        try:
            combined = re.compile("|".join(f"(?:{pattern.pattern})" for pattern in patterns), patterns[0].flags)
        except re.error:
            combined = None
    if len(_ALTERNATIONS) >= _ALTERNATION_LIMIT:
        # A caller building a tuple per call (a mutation tool) never grows this past the limit.
        _ALTERNATIONS.clear()
    _ALTERNATIONS[id(patterns)] = (patterns, combined)
    return combined


def _matches_any(text: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    combined = _alternation(patterns)
    if combined is None:
        return any(pattern.search(text) is not None for pattern in patterns)
    return combined.search(text) is not None


def prints_internal_transfer_designation(description: str) -> bool:
    """Does this printed row DESIGNATE a movement between the member's own accounts?

    R-d's fourth clause, and the only place it is decided. A movement is
    INTERNAL only when the paper prints such a designation on at least one of
    the two legs; an arithmetic coincidence — same day, same cent, opposite
    sign — never sets it, because a member who deposits a sum into checking on
    the day they withdraw the same sum from savings for an unrelated purpose
    produces exactly that signature, and flagging it removes a printed deposit
    from a funder's view of the business by an inference (design §3.2).

    **Decided by `_INTERNAL_TRANSFER_CREDIT_PATTERNS` and, since 5.5 (§7.11),
    the narrowed book and funds transfer rule, and by nothing else.** Every
    member of that tuple names one member's OWN accounts as the source or the
    destination — `TRANSFER FROM SAVINGS`, `SH TO SH`, `ACCOUNT TO ACCOUNT`,
    `TRANSFER FROM <masked> TO <masked>`. A `BOOK TRANSFER` or `FUNDS TRANSFER`
    (never `ELECTRONIC FUNDS TRANSFER DEPOSIT`, an EFT channel) designates an
    own account only when it prints no third-party originator
    (`_third_party_originator`): an account description after FROM (`BUSINESS
    SAVINGS`, `LINE OF CREDIT`) names no payer, a payer's name does. Without the
    owner's yes to T19 every `BOOK TRANSFER` designates one. A funds transfer an
    incoming-wire label starts that prints only a reference
    (`_bare_incoming_wire`) designates none: it is an incoming wire whose sender
    is not printed. No account name is read here, so
    `_own_book_or_funds_transfer`'s holder test does not apply: a transfer that
    prints the holder's own name as its originator designates no own account for
    R-d, the conservative direction.

    **`_TRANSFER_PATTERNS` is REFUSED as evidence for this question, and the
    refusal is a ruling rather than a preference**. That tuple carries `ZELLE`, `VENMO`, `CASH APP`,
    `E TRANSFER`, `ETRANSFER` and `XFER`, and its one production use builds a
    `strong_non_lender_exclusion` whose own reason string says the descriptor
    identifies "an account, online, or person-to-person transfer" — so it
    answers *this row is not a lender debit*, never *this row is an internal
    movement*. A payment to or from another PERSON is not evidence that money
    moved inside one member's ledger set, and admitting it would flag the pair
    and then delete the matching printed deposit from package gross deposits,
    deposit counts, revenue and the withholding denominator. Measured over the
    archive's 47 candidate pairs: 43 carry an internal designation, 3 are
    admitted only by the peer-to-peer vocabulary and 1 prints nothing at all,
    and all 4 stay refused.

    The description is normalised by this module's own normaliser first, so the
    question is asked of exactly the text every other classification in this
    module is decided on.
    """
    text = normalize_transaction_description(description)
    # §7.11: a book or funds transfer designates an own account only when it prints no third-party originator. Nor
    # when an incoming-wire label starts it and prints only a reference (_bare_incoming_wire), the rule
    # _own_book_or_funds_transfer reads.
    return _matches_any(text, _INTERNAL_TRANSFER_CREDIT_PATTERNS) or (
        _BOOK_OR_FUNDS_TRANSFER.search(text) is not None
        and _EFT_FUNDS_TRANSFER.search(text) is None
        and (
            (_BOOK_OR_FUNDS_TRANSFER.search(text).group(0).startswith("BOOK") and not THIRD_PARTY_BOOK_TRANSFER_AS_WIRE)
            or (_third_party_originator(text) is None and not _bare_incoming_wire(text))
        )
    )


#: §5.2: a receiver field of _CREDIT_RECEIVER_FIELD with its value.
_CREDIT_RECEIVER_VALUE = re.compile(_CREDIT_RECEIVER_FIELD.pattern + _RECEIVER_VALUE_END)


def _without_receiver_value(text: str) -> str:
    """§5.2: the text with each receiver field's value removed and every field after it kept, for the operating alias
    and the ledger gate. The holder's name never names a source ('INDN SQUARE INC CO ID ...' is the holder), while
    Bank of America's PMT INFO addenda, printed after INDN and CO ID, still does ('... CO ID 1 CCD PMT INFO
    WORLDPAY ...'): _before_receiver would cut the addenda away with the receiver.

    On an incoming wire (_is_wire_row: labels only a credit prints) the beneficiary field's value goes too, as a
    receiver's does: a credit wire's beneficiary is the holder ('... ORIG NORTHWIND EXPORTS LLC... BNF SQUARE ONE
    BAKERY'). Any other row keeps it: Chase's real-time layout prints the originator there ('FROM BNF INTUIT
    PAYMENTS INC'), and a debit's beneficiary is its payee.

    American Express's incoming-ACH template loses its unlabelled receiver block, the sending bank and trace after it
    kept (_AMEX_ACH_CREDIT)."""
    amex = _AMEX_ACH_CREDIT.match(text)
    if amex is not None:
        text = text[: amex.end("id")] + text[amex.end("receiver"):]
    stripped = _CREDIT_RECEIVER_VALUE.sub(" ", text)
    if _is_wire_row(text):
        stripped = _CREDIT_WIRE_BENEFICIARY_VALUE.sub(" ", stripped)
    return stripped


def _is_wire_row(text: str) -> bool:
    """§7.9, §8.5: the row begins with an incoming-wire label, or (T19) is a third-party book transfer."""
    return _INCOMING_WIRE_LABEL.match(text) is not None or _third_party_book_transfer(text)


def _wire_vetoes_apply(text: str) -> bool:
    """The wire vetoes (_wire_vetoed) and the wire company-form gate read a wire row (_is_wire_row) and, failing
    closed, any row that prints WIRE, so a reference glued to WIRE never skips them. The verifier's own channel test
    (N1, _wire_remittance_purpose) keeps _is_wire_row. WIRE in the receiver's (the holder's) name makes no row a
    wire (§5.2)."""
    return _is_wire_row(text) or _WIRE_WORD.search(_without_receiver_value(text)) is not None


#: The originator labels a loose-wire row may print (Bank of America's ORIG, ORG, Fedwire's B O, ORIGINATOR),
#: never an ACH layout's ORIG CO or ORIG ID.
_LOOSE_WIRE_ORIGINATOR_LABEL = re.compile(
    r"\b(?:B O|ORIGINATOR(?: NAME)?(?! TO BNF\b| TO BENEFICIARY\b)|ORIG(?! CO\b)(?! ID\b)(?! TO BNF\b)"
    r"|ORG(?! TO BNF\b| TO BENEFICIARY\b))\b"
)


def _loose_wire_label(text: str) -> re.Match[str] | None:
    """On a row no incoming-wire label starts that prints WIRE outside the receiver's value and no person-to-person or
    push rail, the originator label ('DEPOSIT WIRE IN <reference> ORG <sender>') whose sender is read as an incoming
    wire's is (_wire_payer_region). The first label after the row's first WIRE word (searched from that position, the
    label's left boundary still read), never one before it: on the '<sender> WIRE' layout (Mercury, Brex) ORG, ORIG,
    ORIGINATOR or B O before a row-final WIRE is a word of the sender's own name ('CONTOSO ORG LLC WIRE', a '.org'
    domain), never a label. None when the row has no such label."""
    if _is_wire_row(text) or _WIRE_WORD.search(_without_receiver_value(text)) is None:
        return None
    row = _before_receiver(text)
    if _CONSUMER_P2P_RAIL.search(row) or _PUSH_RAIL.search(row):
        return None
    wire = _WIRE_WORD.search(row)
    if wire is None:
        return None
    return _LOOSE_WIRE_ORIGINATOR_LABEL.search(row, wire.end())


def _loose_wire_originator(text: str) -> bool:
    """A loose-wire row that prints an originator label (_loose_wire_label; after the row's first WIRE word only)."""
    return _loose_wire_label(text) is not None


#: §7.9 N1 and §7.11 (T19): the labels a reader needs to tell an incoming wire, and the originator a book or
#: funds transfer prints after B O, CUSTOMER, ORIGINATOR, ORG, TT, FROM or WIRE FROM.
_THIRD_PARTY_ORIGINATOR = re.compile(r"\b(?:B O|CUSTOMER|ORIGINATOR|ORG|TT|FROM|WIRE FROM)\b ?")
#: §7.9 N1 and §7.11: the incoming-wire labels a row begins with. And Columbia Bank's 'WIRE DEPOSIT WIRE IN <reference>
#: ORG <sender>', Navy Federal's 'BANK WIRE DEPOSIT' (which prints no sender) and U.S. Bank's 'WIRE CREDIT REF<n>
#: <sending bank> <reference>' (whose sender prints after ORG= when the line is kept). The plural 'WIRE TRANSFERS
#: <DEPOSIT|CREDIT|IN|INCOMING|FROM>' is the same wire label, never a person-to-person transfer (TRANSFERS stays
#: transfer wording on any other row). And 'INCOMING FEDWIRE', 'INBOUND FEDWIRE', 'INBOUND WIRE' and 'INCOMING CHIPS',
#: so a sender printed after them (ORG, B O, WIRE FROM) reaches Q5 as 'FEDWIRE CREDIT ORG <sender>' does; a row that
#: prints none is held as a wire with no sender (Huntington's bare 'INCOMING FEDWIRE TRANSFER' among them). CHIPS alone
#: is no label.
_INCOMING_WIRE_LABEL = re.compile(
    r"^(?:WIRE TYPE (?:WIRE|INTL|FX) IN\b|USD WIRE IN\b|[A-Z]{3} WIRE IN\b|FEDWIRE CREDIT\b|CHIPS CREDIT\b|WT FED"
    r"|WIRE TSF\b|WIRE TRANSFERS? (?:DEPOSIT|CREDIT|IN|INCOMING|FROM)\b|INCOMING WIRE\b|WIRE IN\b|WIRE FROM\b"
    r"|(?:DOMESTIC|INTL|INTERNATIONAL|FOREIGN) (?:INCOMING )?WIRE\b|INCOMING FUNDS TRANSFER\b"
    r"|FUNDS TRANSFER CREDIT TT\b|INBD FUNDS TRANSFER\b|FUNDS TRANSFER WIRE FROM\b"
    r"|WIRE DEPOSIT WIRE IN\b|BANK WIRE DEPOSIT\b|WIRE CREDIT REF ?\d+\b"
    # Falcon International Bank's incoming international wire (IWT), which prints its sender after the bank's own
    # wire field once its reader keeps the text after the amount (_FALCON_WIRE_FIELD).
    r"|INTERNATIONAL IWT\b"
    r"|INCOMING FEDWIRE\b|INBOUND (?:FEDWIRE|WIRE)\b|INCOMING CHIPS\b)"
)
_BOOK_TRANSFER_FROM = re.compile(r"^(?:BOOK TRANSFER CREDIT B O|WIRE TYPE BOOK IN\b.*\bORIG)\b ?")
#: §7.11: the funds-transfer labels of an incoming wire (the label stands for FROM).
_FUNDS_TRANSFER_WIRE_LABEL = re.compile(
    r"\b(?:INCOMING FUNDS TRANSFER|FUNDS TRANSFER CREDIT TT|INBD FUNDS TRANSFER(?: RECEIVED)?|FUNDS TRANSFER WIRE FROM)"
    r"\b ?"
)


def _third_party_originator(text: str) -> str | None:
    """§7.11: the originator a book or funds transfer prints (after B O, CUSTOMER, ORIGINATOR, ORG, TT, FROM or WIRE
    FROM, or one of the four funds-transfer wire labels), when it prints a distinctive payer word; otherwise None.
    An account description is no payer ('FROM BUSINESS SAVINGS', 'FROM LINE OF CREDIT', 'FROM TAX RESERVE'):
    _originator_payer_words."""
    labels: tuple[re.Pattern[str], ...] = (_FUNDS_TRANSFER_WIRE_LABEL, _THIRD_PARTY_ORIGINATOR)
    if _BOFA_BOOK_IN.match(text):
        # Bank of America's WIRE TYPE BOOK IN is its WIRE TYPE WIRE IN layout: the originator follows ORIG (the
        # normalizer drops a SWIFT 50F line number printed with its slash).
        labels = (*labels, _BOFA_BOOK_IN_ORIGINATOR)
    for label in labels:
        for found in label.finditer(text):
            rest = text[found.end():]
            end = _WIRE_FIELD_END.search(rest)
            words = _leading_name_words(rest[: end.start()] if end is not None else rest)
            if _originator_payer_words(words):
                return words
    return None


#: Bank of America's book-transfer wire and its originator label (never ORIG CO NAME, ORIG ID or ORIG TO BNF).
_BOFA_BOOK_IN = re.compile(r"^WIRE TYPE BOOK IN\b")
_BOFA_BOOK_IN_ORIGINATOR = re.compile(r"\bORIG\b(?! CO NAME\b)(?! ID\b)(?! TO BNF\b) ?")


#: The words besides a reference that a bare incoming wire may print after its label: the wire label words
#: (true_revenue's _WIRE_LABEL_ONLY_WORDS, made one list by R32: the bare channel words, every wire layout word, BANK,
#: DEPOSIT, DEP, IN, RECEIVED and CR; a test keeps the two lists in step) and the funds-transfer labels' own originator
#: labels, TT and FROM. Never a legal form, an article, a currency or a generic or holder-noise word (BUSINESS, TRUST,
#: OPERATING, USD, CAD, ONLINE, PAYMENT, INC, LLC, THE): those are no reference.
_BARE_WIRE_LABEL_WORDS = frozenset({
    "WIRE", "WIRES", "TRANSFER", "BOOK", "CREDIT", "INCOMING", "INBOUND", "INBD", "FEDWIRE", "FED", "WT", "IWT",
    "CHIPS", "SWIFT", "DOMESTIC", "INTL", "INTERNATIONAL", "BANK", "DEPOSIT", "DEP", "IN", "RECEIVED", "CR",
    "TT", "FROM",
})


def _bare_incoming_wire(text: str) -> bool:
    """§7.11: a row an incoming-wire label starts (_INCOMING_WIRE_LABEL: RBC's 'FUNDS TRANSFER CREDIT TT <reference> [O]',
    'INCOMING FUNDS TRANSFER <reference>', 'WIRE TRANSFER IN <reference>') that prints no third-party originator
    (_third_party_originator), and, after its label, no account word (_INTERNAL_ACCOUNT_SOURCE_WORDS: SAVINGS, CHECKING,
    ACCOUNT, LOC ...) and no own-account product word (_OWN_ACCOUNT_PRODUCT_WORDS: RESERVE, TAX, PAYROLL, LOAN ...): an
    incoming wire whose sender is not printed, which pass 7 holds as wire_no_sender (Q5), never the holder's own transfer.
    A row that names the holder as its originator, or an own account after its label ('FUNDS TRANSFER CREDIT TT SAVINGS
    <n>'), is not one.

    The row prints only a reference, so every word after the label is a reference token (_is_reference_token: digits, a
    masked token, a month), a single letter (RBC's trailing O or W) or a wire label word (_BARE_WIRE_LABEL_WORDS); any
    other word ('<n> BUSINESS', '<n> USD', '<n> PAYMENT', '<n> INC') makes no bare incoming wire, and the row keeps its
    own-account reading (true_revenue's credit_facts blanks a bare row's payer region, so its reference or label words
    are never a counted sender)."""
    found = _INCOMING_WIRE_LABEL.match(text)
    if found is None or _third_party_originator(text) is not None:
        return False
    after = text[found.end():]
    if _INTERNAL_ACCOUNT_SOURCE_WORDS.search(after):
        return False
    tokens = after.split()
    if any(token in _OWN_ACCOUNT_PRODUCT_WORDS for token in tokens):
        return False
    return all(
        _is_reference_token(token) or (len(token) == 1 and token.isalpha()) or token in _BARE_WIRE_LABEL_WORDS
        for token in tokens
    )


def _third_party_book_transfer(text: str) -> bool:
    """A Chase BOOK TRANSFER CREDIT B/O <originator> or a Bank of America WIRE TYPE BOOK IN that prints an
    originator. Read as an incoming wire only on the owner's yes (THIRD_PARTY_BOOK_TRANSFER_AS_WIRE)."""
    return (
        THIRD_PARTY_BOOK_TRANSFER_AS_WIRE
        and _BOOK_TRANSFER_FROM.match(text) is not None
        and _third_party_originator(text) is not None
    )


def _with_served_cuts(aliases: frozenset[str]) -> frozenset[str]:
    """§7.0: a sixteen-character cut reads as its alias, so a set of operating aliases that carries a rule of §7.2
    carries each alias's served cut (OPERATING_REVENUE_TRUNCATIONS) too. Derived once, at import."""
    return aliases | frozenset(
        cut
        for entity, source_aliases in OPERATING_REVENUE_SOURCE_ALIASES.items()
        for alias in source_aliases
        if alias in aliases and (cut := _operating_alias_cut(alias)) in OPERATING_REVENUE_TRUNCATIONS.get(entity, ())
    )


#: §7.5, §8.1: words that never make a payer's or a debit's first distinctive word: the AP words, the public-payer
#: words, the holder noise (legal suffixes, generic words) and the bank's template and channel words (D11's channel
#: words, D6's channel vocabulary and bank template words, read at call time: _counter_debit_skip_words).
_COUNTER_DEBIT_SKIP_WORDS = frozenset({
    "PAYABLE", "PAYABLES", "ACCOUNTS", "ACCTS", "VENDOR", "TRADE", "REMIT", "REMITTANCE", "STATE", "COUNTY", "CITY",
    "TOWN", "DEPT", "DEPARTMENT", "TREAS", "GOVERNMENT",
    "CHECKCARD", "OVERDRAFT", "TRANF", "CHECKG", "TRANSFERS", "WITHDRAW", "OUTGOING", "PURCHASES",
}) | HOLDER_NOISE


@cache
def _counter_debit_skip_words() -> frozenset[str]:
    return _COUNTER_DEBIT_SKIP_WORDS | frozenset(_ENTITY_NOISE) | _CHANNEL_VOCABULARY | _BANK_TEMPLATE_WORDS


#: §7.6: the public-payer remittance rule. Arm A reads the whole row: a DOD MISC Treasury code on a row that prints no
#: PPD, or a Treasury code, then MISC PAY, then RMR IV. The three codes are read by chained searches
#: (_public_payer_arm_a), each from the end of the one before, which is linear; the '.*' pattern it replaces was cubic
#: on a long row.
_PUBLIC_PAYER_ARM_A_DOD = re.compile(r"^(?!.*\bPPD\b).*\bTREAS \d{3}(?: DES)? DOD MISC\b")
_TREASURY_CODE = re.compile(r"\bTREAS \d{3}\b")
_MISC_PAY_CODE = re.compile(r"\bMISC PAY(?:SEC)?\b")
_RMR_IV_CODE = re.compile(r"\bRMR IV\b")


def _public_payer_arm_a(text: str) -> bool:
    """§7.6 arm A: the DOD MISC form, or the Treasury code, MISC PAY and RMR IV in this order. The earliest match of
    each code is the one to chain from: any later one leaves less of the row to the next."""
    if _PUBLIC_PAYER_ARM_A_DOD.search(text) is not None:
        return True
    treasury = _TREASURY_CODE.search(text)
    misc = _MISC_PAY_CODE.search(text, treasury.end()) if treasury is not None else None
    return misc is not None and _RMR_IV_CODE.search(text, misc.end()) is not None


def _state_words(state: str) -> str:
    return state.replace("_", " ")


def _compile_field_order_forms() -> tuple[tuple[re.Pattern[str], PayeeMatch], ...]:
    """FIELD_ORDER_PAYEE_FORMS compiled once, each with its payee's group (PAYEE_GROUP_REGISTRIES)."""
    state_of = {entity: state for state, registry in PAYEE_GROUP_REGISTRIES.items() for entity in registry}
    return tuple(
        (re.compile(form), PayeeMatch(entity, state_of[entity], ""))
        for entity, forms in FIELD_ORDER_PAYEE_FORMS.items()
        if entity in state_of
        for form in forms
    )
