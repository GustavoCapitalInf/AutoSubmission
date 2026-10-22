"""Sender, P2P sender and bank-name readings."""
from __future__ import annotations

import re
from functools import cache

from analysis.classification_registry import (
    OWN_BANK_SENDING_SPELLINGS,
    P2P_SENDING_BANK_NAMES,
    STATEMENT_BANK_PRINTED_NAMES,
)
from analysis.description_text import normalize_transaction_description
from analysis.descriptor.lexical import (
    _before_receiver,
    _is_reference_token,
    _leading_name_words,
    bank_by_form,
    company_form,
    originator_address,
    payer_name,
)
from analysis.descriptor.payer import relayed_customer_text
from analysis.descriptor.words import (
    BANK_SETTLEMENT_ORIGINATOR,
    REVENUE_GENERIC_WORDS,
    _CONSUMER_P2P_RAIL,
    _PROVINCE,
    _QUEBEC,
    _SANTANDER_WIRE,
    _WIRE_FIELD_END,
    _WIRE_ORIGINATOR_LABEL,
)
from analysis.true_revenue.words import (
    _CURRENCY_CONVERSION,
    _INTERAC_COURRIEL,
    _NOT_A_NAME_ALONE,
    _P2P_LAYOUT_PHRASES,
    _TRANSFER_FIELD_LABEL_WORDS,
    _US_STATE_TAIL,
)


#: Q4: the rail, posting and layout words a person-to-person row prints around a sender printed without FROM
#: ('INTERAC E TRANSFER RECEIVED <sender>', 'ZELLE CREDIT <sender>', 'VIREMENT INTERAC RECU'), besides the generic
#: words, the field labels and the reference tokens; none is ever a sender's name. A Venmo or Cash App cash-out
#: prints no sender at all.
_P2P_NOT_SENDER_WORDS = frozenset({
    "ZELLE", "INTERAC", "ETRANSFER", "TFR", "VIREMENT", "VFC", "AUTODEPOSIT", "AUTODEP", "VENMO", "CASHAPP", "APP",
    "POPMONEY", "RTP", "AUTO", "CASHOUT", "CASH", "OUT", "TRANSFERS", "XFER", "BANK", "DEBIT", "EPAY", "INST", "INS",
    "PURCHASE", "CARD", "NOW", "NET", "NETWORK", "USA",
    # French posting words (Desjardins, National Bank, TD's French layouts).
    "RECU", "RECUE", "PAR", "BANQUE", "EN", "LE", "LA", "DE", "DU", "ES",
})
#: Q4: after these the named party is a recipient, or the row is a reversal: no sender is read.
_P2P_NO_SENDER_WORDS = frozenset({
    "TO", "CANCEL", "CANCELLED", "CANCELED", "ANNULE", "REFUND", "REFUNDED", "RTN", "RETURN", "RETURNED", "REVERSAL",
})
#: Q4: a sender printed without FROM ends at these (§5.2's sender ends, and the field labels).
_P2P_SENDER_END_WORDS = frozenset({"ON", "REF", "CONF", "MEMO", "TRN", "ID", "FOR", "NOTE", "INFO"})
#: Q4, §5.2: more layout words, never a sender's name: the posting words a rail prints where a sender would stand
#: ('ZELLE BUSINESS PAYMENT', 'ZELLE RECURRING PAYMENT', 'INTERAC E TRANSFER REQUEST FULFILLED', 'RTP CREDIT
#: REMITTANCE INFO'), the French ones ('VIREMENT INTERAC DEPOT AUTOMATIQUE', 'VIREMENT INTERAC ENTRANT', 'VIREMENT EN
#: LIGNE TF'), Apple Cash's own name printed again after PMNT RCVD, and its card code CKCD.
_P2P_LAYOUT_WORDS = frozenset({
    "BUSINESS", "RECURRING", "REQUEST", "FULFILLED", "REMITTANCE",
    "DEPOT", "AUTOMATIQUE", "ENTRANT", "ENTRANTE", "LIGNE", "TF",
    "APPLE", "CKCD",
})
#: Q4, §5.2: a wallet's city, printed after its sender ('CASH APP*<sender>*OAKLAND CA', Apple Cash's CUPERTINO CA,
#: Venmo's NEW YORK CITY NY and SAN JOSE CA, Square's SAN FRANCISCO CA): the sender ends there. Only as the
#: sender's tail (_without_city_tail): a sender whose name starts with the city ('ZELLE CREDIT NEW YORK FABRIKAM
#: LLC') keeps it.
_P2P_WALLET_CITY = re.compile(r"(?<![A-Z])(?:CUPERTINO|OAKLAND|(?:SOUTH )?SAN FRANCISCO|SAN JOSE|NEW YORK(?: CITY)?)\b")
#: §5.2: a Venmo or Cash App cash-out prints no sender ('CASH APP*CASH OUT*OAKLAND CA', 'VENMO CASHOUT <reference>
#: <name>': the name is the wallet's owner). Only on a Cash App or Venmo row: CASH OUT on any other rail is a sender's
#: own words ('ZELLE CREDIT CASH OUT AUTO LLC').
_P2P_CASH_OUT = re.compile(
    r"(?<![A-Z])(?:CASH ?APP|SQUARE CASH|VENMO)\b.*?(?<![A-Z])CASH ?OUT\b"
    r"|(?<![A-Z])CASH ?OUT\b.*?(?<![A-Z])(?:CASH ?APP|SQUARE CASH|VENMO)\b"
)
#: Q4, §5.2 (S4.2 fix round 4): the four-digit group Quebec's numbered companies print twice (NNNN-NNNN). The Quebec
#: words after it are the classifier's _QUEBEC (S4.2 fix round 5: one set for the key and the numbered-company guard).
_FOUR_DIGITS = re.compile(r"\d{4}")


def _wire_originator_text(text: str) -> str:
    """§5.2: a wire's originator after its label, up to the next wire field, before the digit cut (the payer
    region's reading, _wire_payer_region, cuts it at the first reference token)."""
    santander = _SANTANDER_WIRE.match(text)
    if santander is not None:
        return santander.group("originator").strip()
    found = _WIRE_ORIGINATOR_LABEL.search(text)
    if found is None:
        return ""
    # A3-G: a SWIFT 50F line number is never part of the originator (the normalizer drops it with its slash).
    rest = text[found.end():]
    end = _WIRE_FIELD_END.search(rest)
    originator = (rest[: end.start()] if end is not None else rest).strip()
    # A3-G refinement: a relaying bank's customer is the originator (the payer region reads it the same way, with the
    # region's address context, A3-G re-review 2).
    region = _leading_name_words(originator)
    after, city_state_end = originator_address(text, region)
    customer = relayed_customer_text(region, rest, after=after, city_state_end=city_state_end)
    return customer.strip() if customer else originator


@cache
def _p2p_sender_rail() -> re.Pattern[str]:
    """Q4: the rails a sender printed without FROM follows: §8.4's consumer rails and RTP. A push rail a platform's
    payout prints after the payer's name ('<payer> ... VISA DIRECT <city> <state>') is not read. Interac's French
    form (_INTERAC_COURRIEL) first, so the sender is read after COURRIEL (the singular's VIREMENT would otherwise
    read 'PAR COURRIEL' as the sender's words)."""
    return re.compile(
        _INTERAC_COURRIEL.pattern + "|" + _CONSUMER_P2P_RAIL.pattern + r"|(?<![A-Z])RTP\b"
    )


def _p2p_sender_region(text: str) -> str:
    """Q4, §5.2: the sender a person-to-person rail prints without FROM ('E TRANSFER AUTODEPOSIT <sender>', 'INTERAC E
    TRANSFER RECEIVED <sender>', 'ZELLE TRANSFER <sender>', 'ZELLE CREDIT <sender>'), as its key reads it
    (_p2p_sender_readings)."""
    return _p2p_sender_readings(text)[0]


def _p2p_sender_readings(text: str) -> tuple[str, str]:
    """Q4, §5.2: the sender a person-to-person rail prints without FROM, read two ways: (its key reading, its
    holder-test reading). The key reading is the name words after a consumer rail or RTP, skipping the rail,
    posting, layout and generic words and single letters, up to a field label, one of §5.2's sender ends or a
    reference token after a name word. When a rail is followed by no name word the next rail is read ('NOW NETWORK
    CREDIT ZELLE CREDIT NOW NET ID <n> ZELLE <sender>'). ('', '') when the row prints FROM (payer_region reads it),
    names a recipient or a reversal, or prints no sender (a Venmo or Cash App cash-out).

    A reference printed before the sender is no part of it, so a per-row reference never splits one sender ('E
    TRANSFER <reference> <sender>'). A sending bank's name and Zelle's PAY ID are removed first, the sender ends at a
    wallet's city, a trailing US state code is dropped, and a legal form or an article alone is no sender.

    The number is kept only on §5.2's province arm, the numbered company proper ('1234567 ONTARIO INC': its identity,
    and the holder test's digit run), so '<reference> FABRIKAM SUPPLY LTD' is one sender. A city ends the sender only
    as its tail, and a state code only after two words (_without_state_tail). A legal form left alone by the skipped
    words reads them back ('ZELLE CREDIT CASH OUT AUTO LLC'). The holder test also reads a layout word inside the name
    ('ZELLE CREDIT REQUEST FABRIKAM LLC'), which the key skips so that one sender's rows printed with and without it
    stay one sender."""
    row = _before_receiver(text)
    if re.search(r"\bFROM\b", row) or _P2P_CASH_OUT.search(row):
        return "", ""
    for rail in _p2p_sender_rail().finditer(row):
        read = _sender_tokens(_without_city_tail(_P2P_LAYOUT_PHRASES.sub(" ", row[rail.end():])))
        if read is None:
            return "", ""
        tokens, number = read
        words = _without_state_tail([token for token, name in tokens if name])
        if number and _numbered_province_sender().match(" ".join([number, *words])):
            return " ".join([number, *words]), " ".join([number, *words])
        if words and not all(word in _NOT_A_NAME_ALONE for word in words):
            return " ".join(words), _holder_reading(tokens)
        formed = _read_back_legal_form(tokens)
        if formed:
            return formed, formed
    return "", ""


@cache
def _numbered_province_sender() -> re.Pattern[str]:
    """Q4, §5.2: the province arm of §5.2's numbered payer region: six or more digits and a province, territory,
    CANADA or a cut of one. S4.2 fix round 4: or Quebec's own form, four digits, a hyphen and four digits before
    QUEBEC, a cut of it or QC ('1234-5678 QUEBEC INC', normalized to '1234 5678 QUEBEC INC'), both digit groups kept.
    S4.2 fix round 5: the Quebec words are the classifier's _QUEBEC, which the numbered-company guard reads too."""
    return re.compile(rf"^(?:\d{{6,}} {_PROVINCE}|\d{{4}} \d{{4}} {_QUEBEC})\b")


def _sender_tokens(rest: str) -> tuple[list[tuple[str, bool]], str] | None:
    """Q4: the words of a sender printed after a rail, up to a field label, one of §5.2's sender ends or a reference
    token after a name word, generic words and single letters skipped: each word with whether it is a name word (not
    a rail, posting or layout word), and the reference printed before the name (six or more digits, or ''). None when
    the row names a recipient or a reversal.

    S4.2 fix round 4: two four-digit groups printed one after the other ('1234 5678', Quebec's hyphenated number once
    normalized) are read as one reference, both groups kept."""
    tokens: list[tuple[str, bool]] = []
    number = ""
    previous = ""
    for token in rest.split():
        if token in _P2P_SENDER_END_WORDS or token in _TRANSFER_FIELD_LABEL_WORDS:
            break
        if token in _P2P_NO_SENDER_WORDS:
            return None
        if _is_reference_token(token):
            if any(name for _, name in tokens):
                break
            if _FOUR_DIGITS.fullmatch(token) and _FOUR_DIGITS.fullmatch(previous):
                number = f"{previous} {token}"
            else:
                number = token if token.isdigit() and len(token) >= 6 else ""
            previous = token
            continue
        previous = ""
        if token in REVENUE_GENERIC_WORDS or len(token) < 2:
            continue
        tokens.append((token, token not in _P2P_NOT_SENDER_WORDS and token not in _P2P_LAYOUT_WORDS))
    return tokens, number


def _without_city_tail(rest: str) -> str:
    """Q4, §5.2: the words after a rail, cut at a wallet's city printed as the sender's tail: after a name word
    ('CASH APP*<sender>*OAKLAND CA'), or with no name word after it but a state code ('APPLE CASH INST XFER
    CUPERTINO CA'). A city followed by name words starts the sender's name and is kept ('ZELLE CREDIT NEW YORK
    FABRIKAM LLC', 'CASH APP*NEW YORK FABRIKAM LLC*OAKLAND CA', which ends at OAKLAND)."""
    for city in _P2P_WALLET_CITY.finditer(rest):
        before = _sender_tokens(rest[: city.start()])
        after = _sender_tokens(rest[city.end():])
        named_before = before is not None and any(name for _, name in before[0])
        named_after = after is not None and any(name and token not in _US_STATE_TAIL for token, name in after[0])
        if named_before or not named_after:
            return rest[: city.start()]
    return rest


def _without_state_tail(words: list[str]) -> list[str]:
    """Q4, §5.2: the sender's words without a trailing US state code printed after two words or more ('JOHN SMITH
    NY', 'FABRIKAM LLC NY'), or with no name word before it (a code alone names nobody). After a single name word
    it is the name's own ('KIM PA' and 'KIM MA' are two senders)."""
    words = list(words)
    while words and words[-1] in _US_STATE_TAIL and (
        len(words) >= 3 or all(word in _US_STATE_TAIL or word in _NOT_A_NAME_ALONE for word in words[:-1])
    ):
        words.pop()
    return words


def _holder_reading(tokens: list[tuple[str, bool]]) -> str:
    """Q4, §5.2: the sender as the holder test reads it: the name words, and each layout word next to one, so a
    layout word never defeats the holder test ('REQUEST FABRIKAM LLC' paying Request Fabrikam). A rail or posting
    word ('AUTO' of AUTO DEPOSIT, 'CASH') is never read back: a holder named with it would be held on every such row."""
    kept = []
    for index, (token, name) in enumerate(tokens):
        beside = [tokens[at][1] for at in (index - 1, index + 1) if 0 <= at < len(tokens)]
        if name or (token in _P2P_LAYOUT_WORDS and any(beside)):
            kept.append(token)
    return " ".join(_without_state_tail(kept))


def _read_back_legal_form(tokens: list[tuple[str, bool]]) -> str:
    """Q4, §5.2: a sender whose only name words are a legal form or an article, and whose skipped words stand right
    before them: those words and the form, when they read as a company form ('CASH OUT AUTO LLC'); '' otherwise ('RTP
    CREDIT 1ABC INC', 'ZELLE BUSINESS PAYMENT')."""
    names = [index for index, (_, name) in enumerate(tokens) if name]
    if not names or not all(tokens[index][0] in _NOT_A_NAME_ALONE for index in names):
        return ""
    start = names[0]
    while start > 0 and not tokens[start - 1][1]:
        start -= 1
    if start == names[0]:
        return ""
    sender = " ".join(_without_state_tail([token for token, _ in tokens[start:]]))
    return sender if company_form(sender) else ""


def _sender_key(sender: str) -> tuple[str, ...]:
    """Q4: the key of a sender printed without FROM: its words (a numbered company's number kept, so two numbered
    companies are never one sender), at most the first four; the payer key of the same name printed after FROM
    (_payer_key) when it prints no number."""
    return tuple(sender.split())[:4]


#: §8.6: the entry words of a bank's merchant deposit or card settlement ('<bank> DES:DEPOSIT', Synchrony's 'MTOT
#: DEP', 'BTOT', 'NET SETTLE', 'STLMT', a merchant word): a bank named before such an entry pays the business's own
#: sales, and keeps its reading.
_BANK_SETTLEMENT_ENTRY = re.compile(r"(?<![A-Z])(?:DEPOSIT|DEP|MTOT|BTOT|SETTLE\w*|STLMT|MERCH\w*)\b")
#: §8.6: the channel words a bank prints after its own name in an ACH payer region ('<bank> ACH', 'CHASE
#: ONLINE', '<bank> N A'), dropped from the end of the name.
_BANK_ONLY_TAIL = frozenset({"ACH", "ONLINE", "N", "A", "NA"})
#: §8.6: the last word of a bank's own form, and the most words such a name may print.
_BANK_ONLY_FORM_ENDS = frozenset({"BANK", "BANCORP", "FSB"})
_BANK_ONLY_MAX_WORDS = 4
#: §8.6: the listed sending banks' names alone (the registry's P2P_SENDING_BANK_NAMES; Zelle's PAY ID, which
#: _P2P_LAYOUT_PHRASES also removes, names no bank).
_SENDING_BANK_NAME = re.compile(
    r"(?<![A-Z])(?:" + "|".join(re.escape(name) for name in sorted(P2P_SENDING_BANK_NAMES, key=len, reverse=True))
    + r")\b"
)
#: The marks _bank_only_payer puts where a bank's name stood (lowercase: no upper-case reader ever matches them).
_SENDING_MARK = "sending-bank"
_OWN_MARK = "own-bank"
#: §8.6: a person-to-person label printed on the row ('<bank> P2P <reference> <sender>', Bank of America's P2P
#: payment received at another bank): the bank is a person's sending bank (Q4), never the payer alone. Read inside
#: the payer region only, the bank's name followed by the label (_p2p_label_after_bank_name); an entry field's P2P
#: ('CO ENTRY DESCR:P2P') no longer refuses the bank-only reading.
_P2P_LABEL = re.compile(r"(?<![A-Z0-9])P2P(?![A-Z0-9])")


def _p2p_label_after_bank_name(region: str, row: str) -> bool:
    """§8.6: the payer region prints a person-to-person label (_P2P_LABEL), or the row (`row`, before its receiver
    fields) prints the region's name followed by the label ('BANK OF AMERICA P2P <reference> <sender>': the payer
    region ends at the label, a token holding a digit)."""
    if _P2P_LABEL.search(region):
        return True
    name = region.strip()
    return bool(row and name) and re.search(
        r"(?<![A-Z0-9])" + re.escape(name) + r" P2P(?![A-Z0-9])", row
    ) is not None


def _own_bank_whole_region(region: str, bank: str) -> bool:
    """§8.2, §8.6: the payer region, its reference tokens and a trailing channel word (_BANK_ONLY_TAIL) dropped, is as a
    whole one of the statement's own bank's names: its normalized bank field and printed short forms
    (_statement_bank_forms), or a listed sending-bank spelling the bank prints for itself (_own_bank_sending_spellings:
    BOFA on Bank of America, US BANK on U.S. Bank, JPMORGAN CHASE and CHASE BANK on Chase). Read on the region's name
    (payer_name) and, for a spaced initialism ('U S BANK'), on its words with single letters kept."""
    own = {*_statement_bank_forms(bank), *_own_bank_sending_spellings(bank)}
    if not own:
        return False
    for words in (payer_name(region).split(), region.split()):
        kept = [word for word in words if not _is_reference_token(word)]
        while kept and kept[-1] in _BANK_ONLY_TAIL:
            kept.pop()
        if kept and " ".join(kept) in own:
            return True
    return False


@cache
def _own_bank_sending_spellings(bank: str) -> tuple[str, ...]:
    """§8.2, §8.6: the listed sending-bank spellings the statement's bank prints for itself (the registry's
    OWN_BANK_SENDING_SPELLINGS), read when one of an entry's markers starts the normalized bank field as whole words
    (a leading THE skipped), so a marker never matches inside another bank's name ('FIRST CITIZENS BANK' is not
    Citizens Bank). Empty when none does."""
    field = normalize_transaction_description(bank).strip().upper()
    field = re.sub(r"^THE ", "", field)
    spellings: set[str] = set()
    for markers, printed in OWN_BANK_SENDING_SPELLINGS:
        if any(re.match(re.escape(marker) + r"(?![A-Z0-9])", field) for marker in markers):
            spellings.update(printed)
    return tuple(sorted(spellings, key=len, reverse=True))


def _bank_only_payer(region: str, entry: str, bank: str | None, *, row: str = "") -> str | None:
    """§8.2, §8.6 (the registry's note: a bank's name is never the payer's name): the payer region names only a
    bank. On its name (payer_name: no token holding a digit, no single letter) the listed sending banks' names
    (P2P_SENDING_BANK_NAMES) are marked, then the statement's own bank's names (_statement_bank_names); reference tokens
    are dropped, and a trailing channel word (_BANK_ONLY_TAIL: ACH, ONLINE, N A, NA). 'sending' when only a sending
    bank's name is left, 'own' when only the statement's own bank's, 'form' when one to four words ending BANK, BANCORP,
    FSB or CREDIT UNION are left (no marked name among them) and the classifier reads the region as a bank by its own
    form (bank_by_form: never a food, blood, sperm, eye, tissue, milk, bone or cord-blood bank, never a company whose
    name holds the bank word, never a bank's settlement form). None otherwise, for an empty region, for a bank's
    settlement or merchant-services originator (BANK_SETTLEMENT_ORIGINATOR), for an entry of a merchant deposit or card
    settlement (_BANK_SETTLEMENT_ENTRY: '<bank> DES:DEPOSIT', 'MTOT DEP'), which pay the business's own sales, and for a
    payer region that prints a person-to-person label after the bank's name (_p2p_label_after_bank_name, read on `row`,
    the row before its receiver fields: the bank is a person's sending bank, whose payment Q4 reads, never the holder's
    pull).

    The statement's own bank is read first, as a whole region (_own_bank_whole_region: its normalized bank field, its
    printed short forms, and the listed sending-bank spellings it prints for itself), so a statement whose bank is
    itself a listed sending bank reads its own name alone as 'own' ('WELLS FARGO ACH' on Wells Fargo, 'BOFA' on Bank
    of America, 'JPMORGAN CHASE' on Chase), never as another bank's pull; a longer region keeps the old order
    (sending, then own, then form), so 'JPMORGAN CHASE' inside a longer name is never cut to its other words.

    Q6 never verifies such a payer, which is counted as no_payer_printed (a bank's name names no customer); a sending
    bank or a bank by its form on a row with no entry field is the holder's own pull (_bank_only_pull, held)."""
    if not region or BANK_SETTLEMENT_ORIGINATOR.search(region) or _BANK_SETTLEMENT_ENTRY.search(entry or ""):
        return None
    if _p2p_label_after_bank_name(region, row):
        return None
    if bank and _own_bank_whole_region(region, bank):
        return "own"
    marked = _SENDING_BANK_NAME.sub(f" {_SENDING_MARK} ", payer_name(region))
    own = _statement_bank_names(bank) if bank else None
    if own is not None:
        marked = own.sub(f" {_OWN_MARK} ", marked)
    words = [word for word in marked.split() if not _is_reference_token(word)]
    while words and words[-1] in _BANK_ONLY_TAIL:
        words.pop()
    if words == [_SENDING_MARK]:
        return "sending"
    if words == [_OWN_MARK]:
        return "own"
    if not words or _SENDING_MARK in words or _OWN_MARK in words or len(words) > _BANK_ONLY_MAX_WORDS:
        return None
    if words[-1] not in _BANK_ONLY_FORM_ENDS and words[-2:] != ["CREDIT", "UNION"]:
        return None
    return "form" if bank_by_form(region) else None


#: §8.2: the account-description words a bank prints after its own name on a pull from another of the holder's
#: bank accounts ('<bank> SAVINGS <n> ACH', '<bank> BUSINESS BANKING OPERATING ACCOUNT ACH'), and the product
#: words one of them must be; a bank's own form ends its name.
_BANK_ACCOUNT_DESCRIPTION_WORDS = frozenset({
    "SAVINGS", "SAVING", "SVGS", "SAV", "CHECKING", "CHKG", "CHK", "BUSINESS", "BANKING", "OPERATING", "ACCOUNT",
    "ACCT", "MONEY", "MARKET", "ACH",
})
_BANK_PRODUCT_WORDS = frozenset({"SAVINGS", "SAVING", "SVGS", "CHECKING", "CHKG", "BANKING"})
_BANK_FORM_WORDS = frozenset({"BANK", "BANCORP", "FSB", "CU", "FCU"})


def _bank_account_payer(region: str, bank: str | None) -> bool:
    """§8.2 (a bank's name is never the payer's name): an ACH or unlabelled payer region that is only a bank's name
    and an account description: a sending bank's or the statement's own bank's name, or one to four words ending in a
    bank's form (BANK, BANCORP, FSB, CU, FCU), or one word before a BANKING product ('<brand> BUSINESS BANKING
    OPERATING ACCOUNT'), followed only by account-description words (_BANK_ACCOUNT_DESCRIPTION_WORDS), one of them a
    product word (SAVINGS, CHECKING, BANKING), references and digits. Such a credit is the holder's pull from another
    of its own bank accounts: no payer is printed (held as transfer_no_counterparty, Q2)."""
    if not region:
        return False
    named = _P2P_LAYOUT_PHRASES.sub(" BANK ", region)
    own = _statement_bank_names(bank) if bank else None
    if own is not None:
        named = own.sub(" BANK ", named)
    tokens = [
        token for token in named.split()
        if not _is_reference_token(token) and not any(ch.isdigit() for ch in token)
    ]
    split = next((at for at, token in enumerate(tokens) if token in _BANK_ACCOUNT_DESCRIPTION_WORDS), len(tokens))
    name, description = tokens[:split], tokens[split:]
    if not description or any(token not in _BANK_ACCOUNT_DESCRIPTION_WORDS for token in description):
        return False
    if not any(token in _BANK_PRODUCT_WORDS for token in description):
        return False
    if name and name[-1] in _BANK_FORM_WORDS and len(name) <= 4:
        return True
    return len(name) == 1 and "BANKING" in description


@cache
def _statement_bank_forms(bank: str) -> tuple[str, ...]:
    """§8.1: the names the statement's bank prints for itself: its whole normalized name, and the short forms it
    prints (the registry's STATEMENT_BANK_PRINTED_NAMES, read when the bank field contains one of the entry's bank
    words), longest first. Empty when the bank field normalizes to nothing."""
    field = normalize_transaction_description(bank).strip().upper()
    forms = {field}
    for markers, printed in STATEMENT_BANK_PRINTED_NAMES:
        # The bank field names the bank by containment (whole words, any case), not exact spelling.
        if any(re.search(r"(?<![A-Z])" + re.escape(marker) + r"(?![A-Z])", field) for marker in markers):
            forms.update(printed)
    forms.discard("")
    return tuple(sorted(forms, key=len, reverse=True))


@cache
def _statement_bank_before_conversion(bank: str) -> re.Pattern[str] | None:
    """§8.1: the statement's bank's own name (_statement_bank_forms) printed right before
    currency-conversion wording. None when the bank field normalizes to nothing."""
    forms = _statement_bank_forms(bank)
    if not forms:
        return None
    names = "|".join(re.escape(form) for form in forms)
    return re.compile(r"(?<![A-Z])(?:" + names + r") (?=" + _CURRENCY_CONVERSION.pattern + ")")


@cache
def _statement_bank_names(bank: str) -> re.Pattern[str] | None:
    """§8.2: the statement's bank's own names (_statement_bank_forms) as whole words, which never name a transfer's
    counterparty ('TRUIST ONLINE TRANSFER ...' on a Truist statement). None when the bank field normalizes to nothing."""
    forms = _statement_bank_forms(bank)
    if not forms:
        return None
    return re.compile(r"(?<![A-Z])(?:" + "|".join(re.escape(form) for form in forms) + r")\b")
