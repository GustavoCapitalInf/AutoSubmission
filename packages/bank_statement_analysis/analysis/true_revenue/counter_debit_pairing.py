"""Counter-debit pairing: counter_debits, counter_credit, also_debited, debited_as_lender."""
from __future__ import annotations

import re
from collections import Counter
from typing import Sequence, TYPE_CHECKING

from analysis.classification.counter_debit_reading import (
    _counter_debit_head,
    _split_glued_digits,
    counter_debit_debit_reading,
    counter_debit_payer_reading,
)
from analysis.description_text import _TRANSFER_WORDING
from analysis.descriptor.lexical import _before_receiver, company_form, payer_name, without_statement_furniture
from analysis.descriptor.rails import _without_receiver_value
from analysis.descriptor.words import _CONSUMER_P2P_RAIL, _GLUED_SEC_CODE, _PUSH_RAIL, _WIRE_WORD
from analysis.payee_matcher import match_known_payee
from analysis.true_revenue.channel import _transfer_code
from analysis.true_revenue.model import CounterCredit, CounterDebits, _CounterDebit
from analysis.true_revenue.self_originated_credits import processor_payout
from analysis.true_revenue.sender import _p2p_sender_readings
from analysis.true_revenue.words import (
    INSURER_FOR_WORK_METHOD,
    LENDER_DEBIT_STATES,
    _CARD_FORM_DEBIT,
    _INTERAC_COURRIEL,
    _WIRE_PARTY_LEGAL_FORMS,
)

if TYPE_CHECKING:
    from analysis.classification.record import CounterDebitReading, TransactionClassification


#: §8.1: the instant-payment rail labels a layout prints before the payer's name, never the payer: PNC's INSTPMNTIN at
#: the start of the payer region, and the RTP network's RTP CREDIT at the start of a row whose payer region is empty
#: (not RTP CREDIT FROM, whose sender the person-to-person readers read). The counter-debit holds read the name after
#: them (_counter_region), so an app's advance no alias lists is read against the app's debits.
_INSTANT_PAYMENT_LABEL = re.compile(r"^INSTPMNTIN\s+")
_RTP_CREDIT_NAME = re.compile(r"^RTP CREDIT\s+(?!FROM\b)(\S.*)$")


#: The bank's own fee for an incoming wire or funds transfer, which reprints the sender's name (RBC's 'FUNDS TRANSFER
#: FEE TT <sender>', 'WIRE TRANSFER FEE [FROM] <sender>', '[DOMESTIC] INCOMING WIRE FEE', 'WIRE FEE'): never circular
#: money, so it never holds the wire (_COUNTER_DEBIT_KINDS).
_RECEIVING_FEE_DEBIT = re.compile(
    r"(?<![A-Z])(?:FUNDS TRANSFER|WIRE(?: TRANSFER| TRANS| TFR| IN)?) (?:FEES?|CHG|CHARGE|SVC CHARGE)\b"
    r"|(?<![A-Z])INCOMING (?:FUNDS TRANSFER |WIRE (?:TRANSFER )?)?(?:FEES?|CHG|CHARGE)\b"
)
#: The fee for the holder's own outgoing wire names its beneficiary: it still holds the payer (the holder sent
#: that payer money).
_OUTGOING_WIRE_FEE = re.compile(r"(?<![A-Z])(?:OUTGOING|OUT|TO|BNF|BENEFICIARY)\b")
#: The receiving fee prints the sender it reprints after TT or FROM ('FUNDS TRANSFER FEE TT <sender>', 'WIRE TRANSFER
#: FEE FROM <sender>'): the outgoing words are read before it, never inside the sender's name ('CONTOSO TO GO INC').
#: FROM before the holder's own account (an account word or a masked account number: 'WIRE TRANSFER FEE FROM CHECKING TO
#: <payee>') or before TO is the wire's source, never a sender, so the words after it are the fee's own. The holder's
#: own account is also an account product's name (up to two product words, BUSINESS, BUS, OPERATING, PAYROLL, PRIMARY,
#: COMMERCIAL, ANALYZED, ANALYSIS or PERSONAL, before an account word: 'FROM BUSINESS CHECKING TO <payee>', 'FROM BUS
#: CHK'), MONEY MARKET, OPERATING alone (the holder's operating account) or a digit run of three or more (the account
#: number a bank prints after '*' or '...'); every other word after FROM still starts a sender ('FROM CONTOSO TO GO
#: INC', 'FROM OPERATING ENGINEERS LOCAL ...'), so the lookahead is widened only, never every FROM ... TO read as the
#: source (which would read a sender named with TO).
_FEE_SOURCE_ACCOUNT = (
    r"(?:(?:BUSINESS|BUS|OPERATING|PAYROLL|PRIMARY|COMMERCIAL|ANALYZED|ANALYSIS|PERSONAL) ){0,2}"
    r"(?:CHECKING|CHKG|CHK|CKG|SAVINGS|SAV|SVGS|ACCOUNT|ACCT|DDA|MMA)"
    r"|MONEY MARKET"
)
_FEE_SENDER_RUN = re.compile(
    r"(?<![A-Z])(?:TT|FROM)\b"
    rf"(?! (?:TO|OPERATING|{_FEE_SOURCE_ACCOUNT})\b| X{{2,}}\d*\b| \d{{3,}}\b)"
)
#: The outgoing words no sender's name prints, read after the sender too ('... TT <sender> BNF <payee>').
_OUTGOING_WIRE_FEE_AFTER_SENDER = re.compile(r"(?<![A-Z])(?:OUTGOING|BNF|BENEFICIARY)\b")
#: §4.2: a processor's own debit beside its settlements: its fee, discount, chargeback, adjustment or
#: returns. A monthly-discount processor posts one such debit a month.
_PROCESSOR_FEE_DEBIT = re.compile(
    r"(?<![A-Z])(?:FEES?|DISCOUNT|DISC|CHBK|CHGBK|CHRGBACK|CHARGEBACKS?|CHG BACK|ADJ|ADJUSTMENTS?|RETURNS?)\b"
)
#: §4.2, §20: a processor's fee word glued after another word at the end of the entry that Chase's SEC code follows,
#: once _counter_debit_kind_text splits the code off ('MONTHLYFEE SEC CCD', 'PAYCORFEES SEC CCD', 'SERVICEFEE SEC WEB'),
#: never COFFEE.
_GLUED_FEE_ENTRY = re.compile(
    r"(?<![A-Z])[A-Z]{3,}?(?<!COF)(?:FEES?|DISCOUNT|DISC|CHARGEBACKS?|CHGBK|CHBK)"
    r"(?= SEC (?:CCD|CTX|PPD|WEB|IAT|COR|TEL|POP|BOC|ARC|RCK|CIE)\b)"
)
#: A credit printing settlement, payout, MID or merchant-services wording is a processor's settlement,
#: which its own fee debits never hold.
_SETTLEMENT_CREDIT = re.compile(
    r"(?<![A-Z])(?:SETTLE\w*|SETTLMT|SETLMT|STLMT|STLMNT|PAYOUTS?|MERCHANT SERVI\w*)\b|(?<![A-Z])MID(?=\d|\b)"
)
#: §4.2: a processor's or a platform's payout forms the settlement words miss, read before the receiver fields as they
#: are: a merchant-services deposit glued or cut (RBC's MRCHNTSVCS, MRCH SVCS), a combined deposit (COMB DEP), Payment
#: Brands' originator in its printed cuts (PAYMNTBRAND, PYMNTBRDMIN: a card payment facilitator, a registered ISO of
#: Fifth Third Bank, whose settlement account takes its card sales and pays its refunds, chargebacks and processing
#: fees), QuickBooks Payments in Canada (INTUIT CANADA PAYMENTS and its cut INTUIT CANADA P, never its PAYROLL), a
#: bank's merchant deposit ('DEPOSIT <bank> MERCHANT ...') and a platform's twelve-character payout id of letters and
#: digits after ST (Stripe's 'ST-<id>').
_PAYOUT_FORMS = re.compile(
    r"(?<![A-Z])(?:MRCHNT ?SVCS?|MRCH SVCS?|COMB(?:INED)? DEP(?:OSIT)?|PA?YM?NTBR(?:A?NDS?|D)\w*"
    r"|INTUIT CANADA P(?:AYMENTS)?)\b"
    r"|^DEPOSIT [A-Z]+ MERCHANT\b"
    r"|(?<![A-Z0-9])ST (?=[A-Z0-9]{12}(?![A-Z0-9]))(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{12}(?![A-Z0-9])"
)
#: A processor's merchant-ID field, read anywhere on the row: Chase and Truist print it after the receiver ('IND
#: NAME:<merchant> MID:<digits>-<processor>').
_MERCHANT_ID_FIELD = re.compile(r"(?<![A-Z])MID \d{6,}\b")
#: An ATM, ABM or cash withdrawal: the holder taking cash out names a place, never a payer, so it never holds a
#: deposit (a transfer made at an ATM stays circular money).
_CASH_WITHDRAWAL_DEBIT = re.compile(
    r"(?<![A-Z])(?:ATM|ABM)\b|(?<![A-Z])CASH (?:WITHDRAWAL|WITHDRWL|WDL|WD)\b|(?<![A-Z])WITHDRAWAL CASH\b"
)
#: A company whose name leads with ATM or ABM (a legal form within its next two words; never CO, a state's code after an
#: ATM's town), or an ACH entry printing one (Bank of America's DES ... ID field, Chase's ORIG CO NAME and CO ENTRY DESCR,
#: a receiver or company id field), is a payee the holder pays, never a cash withdrawal. None of those two words is a
#: cash or posting word (WITHDRAWAL, WITHDRAW, WITHDRWL, WTHDRWL, WDL, WD, DEBIT, CASH, FEE, PURCHASE, TRANSACTION, TXN),
#: so 'ATM WITHDRAWAL <name> INC' and 'ATM DEBIT <name> LLC' stay cash withdrawals.
_ATM_NAMED_COMPANY = re.compile(
    r"(?<![A-Z])(?:ATM|ABM)"
    r"(?: (?!(?:WITHDRAWALS?|WITHDRAW|WITHDRWL|WTHDRWL|WDL|WD|DEBIT|CASH|FEE|PURCHASE|TRANSACTION|TXN)\b)[A-Z&]+){0,2}"
    r" (?:INC|LLC|CORP|CORPORATION|LTD|LIMITED|COMPANY|INDUSTRIES|GROUP)\b"
)
_ACH_ENTRY_LABEL = re.compile(
    r"(?<![A-Z])(?:INDN|IND NAME|ORIG CO NAME|CO ENTRY DESCR|CO ID|DES(?: [A-Z0-9]+){1,4} ID)\b"
)
#: §5.2: a wallet's cash-out names no sender (Venmo, Cash App, Square Cash, Apple Cash): a counter-debit reading
#: that leads with the wallet's name reads nothing.
_WALLET_CASH_OUT = re.compile(r"^(?:VENMO|CASH ?APP|SQUARE CASH|APPLE CASH)\b")
#: The e-Transfer rails, whose sender RBC and TD print without FROM (e-Transfer received <sender>, AUTODEPOSIT
#: <sender>, VIREMENT RECU <sender>): the counter-debit holds read that sender (_counter_region). And Interac's French
#: form, plural included (Banque Royale's 'DEPOT AUTO VIREMENTS PAR COURRIEL <sender>', _INTERAC_COURRIEL).
_E_TRANSFER_RAIL = re.compile(
    r"(?<![A-Z])(?:INTERAC|E ?TRANSFER|ETRANSFER|E ?TFR|AUTODEPOSIT|VIREMENT|VIREMENTS? PAR COURRIEL)\b"
)
#: A bill the holder pays: bill pay, an electronic bill (EBPP), autopay, a utility, a telecom, cable or wireless
#: service, a subscription.
_BILL_DEBIT = re.compile(
    r"(?<![A-Z])(?:BILL ?PAY(?:MENTS?|MT|MNT)?|BILL PAID|BILL PMT|EBPP|AUTOPAY\w*|AUTO PAY|UTILIT\w*|UTIL"
    r"|TELECOM\w*|WIRELESS|CABLE|VOIP|SUBSCRIPTIONS?|SUBSCR)\b"
)
#: A payer that reads as an insurer keeps the bill exclusion off: an insurer's credit beside the holder's premium or
#: bill to it stays held (insurers never count).
_INSURER_CREDIT = re.compile(r"(?<![A-Z])(?:INS|INSUR\w*|ASSUR\w*)\b")
#: A premium, or the bank's retry of a returned premium (a re-presentment of the same obligation, never a second one),
#: read on a non-lender debit's kind text with Chase's glued SEC code split off ('INS PREMSEC PPD' reads 'INS PREM SEC
#: PPD'): the flag that lets a debit naming a credit the Q2 release counted recur at one amount without holding it
#: (also_debited). A flag, never a kind: the debit keeps its kind.
_PREMIUM_DEBIT = re.compile(r"(?<![A-Z])(?:PREM|PREMS|PREMIUMS?|PREMSEC|RETRY)(?![A-Z])")
#: A transfer, wire or person-to-person debit, or an own-account move ('TO CHKG', 'DDA TO DDA'): it can be
#: circular money, so it also matches a payer as 5.6 read it (CounterDebitReading.legacy).
_OWN_ACCOUNT_DEBIT = re.compile(
    r"(?<![A-Z])(?:FR|FROM|TO) (?:CHKG|CHK|CHECKING|SAV|SAVINGS|SHARES?|DDA)\b|(?<![A-Z])ZEL\b"
)
#: Payer_debited_as_lender compares a cut or glued funder name by prefix, five letters or more ...
_PREFIX_MIN_LETTERS = 5
#: ... when the longer word runs on into a financing root ('CONTOSOFUNDING' after 'CONTOSO') or into the shorter side's
#: next word ('FABRIKAMVENTUREHO' after 'FABRIKAM VENTURE'), never into anything else (a customer named like a funder:
#: 'FABRIK EVENTS' against 'FABRIKAM').
_FINANCING_REMAINDER = re.compile(r"^(?:FUND|FIN|CAP|LEND|LOAN|ADV|CRED|MCA)")


def _cents(amount: float) -> int:
    return round(abs(amount) * 100)


def _lender_entity(text: str, *, credit: bool = False) -> str | None:
    """The registry lender or financing entity a text names (its glued digit runs split off). A credit's (`credit`) is
    read with the credit index, as the classifier reads the credit."""
    known = match_known_payee(_split_glued_digits(text), credit=credit)
    return known.entity if known is not None and known.state in LENDER_DEBIT_STATES else None


def _counter_debit_kind(text: str) -> str:
    """A posted non-lender debit's kind. The bank's receiving fee first (it prints transfer or wire wording, never
    circular money), then a transfer, wire, person-to-person or own-account debit (circular), a processor's fee, a
    bill, or another debit (an ACH payment, a purchase...).

    Read without the receiver fields' values (§5.2: INDN, IND NAME, RECEIVER NAME, RECV NAME, IND ID print the
    holder's own name), as _lender_entity reads a lender debit, every field after them kept (an addenda's PMT INFO): a
    holder named for a bill or fee word ('<NAME> CABLE LLC', '<NAME> RETURNS LLC') never turns an affiliate's or a
    collector's debit into a bill or a processor's fee.

    Read without the statement furniture a parser glued onto the debit
    (classifier.without_statement_furniture), so a footer's words (TD's back panel prints 'ELECTRONIC FUNDS
    TRANSFERS') never make a fee or a bill circular money.

    The receiving fee's outgoing words (_OUTGOING_WIRE_FEE) are read on its label and the words after it up to the
    sender it reprints after TT or FROM (_FEE_SENDER_RUN), never inside that sender's name ('FUNDS TRANSFER FEE TT
    CONTOSO TO G' is the bank's fee for a wire from CONTOSO TO GO INC). A fee whose own words name an outgoing wire
    falls through to the kinds after it, as before. FROM before the holder's own account or before TO starts no sender
    ('WIRE TRANSFER FEE FROM CHECKING TO <payee>' is the fee for the holder's own wire), and OUTGOING, BNF and
    BENEFICIARY, which no sender's name prints, are read after the sender too.

    §4.2, §20: the processor's fee and the bill are read on the kind text with Chase's glued SEC code split off
    (_counter_debit_kind_text: 'CO ENTRY DESCR FEESSEC CCD' reads 'FEES SEC CCD', 'BILL PAYMTSEC' reads 'BILL PAYMT
    SEC'), and a fee word glued after another word at the entry's end is the processor's fee too (_GLUED_FEE_ENTRY:
    'MONTHLYFEESEC', never 'COFFEESEC'); the receiving fee and circular money keep reading the row as printed (a glued
    'TRANSFERSEC' keeps its kind). The kind order is unchanged. FROM before an account product's name, MONEY MARKET,
    OPERATING or an account number starts no sender either (_FEE_SOURCE_ACCOUNT: 'WIRE TRANSFER FEE FROM BUSINESS
    CHECKING TO <payee>' is circular)."""
    return _counter_debit_kind_of(*_counter_debit_kind_text(text))


def _counter_debit_kind_text(text: str) -> tuple[str, str]:
    """A non-lender debit's kind text, read without the receiver fields' values and the statement furniture, and the
    same text with Chase's glued SEC code split off (classifier._GLUED_SEC_CODE, which classifier.revenue_text applies
    to credits only): (text, split)."""
    text = without_statement_furniture(_without_receiver_value(text))
    return text, _GLUED_SEC_CODE.sub(r"\1 SEC \2", text)


def _counter_debit_kind_of(text: str, split: str) -> str:
    """The kind of a debit's kind text and its split (_counter_debit_kind_text), in the order _counter_debit_kind
    gives: the receiving fee and circular money on `text`, the processor's fee and the bill on `split`."""
    fee = _RECEIVING_FEE_DEBIT.search(text)
    if fee is not None:
        tail = text[fee.end():]
        sender = _FEE_SENDER_RUN.search(tail)
        own = tail if sender is None else tail[:sender.start()]
        if not (
            _OUTGOING_WIRE_FEE.search(f"{text[:fee.end()]} {own}")
            or (sender is not None and _OUTGOING_WIRE_FEE_AFTER_SENDER.search(tail[sender.start():]))
        ):
            return "receiving_fee"
    if (
        _TRANSFER_WORDING.search(text) or _WIRE_WORD.search(text)
        or _CONSUMER_P2P_RAIL.search(text) or _PUSH_RAIL.search(text)
        or _OWN_ACCOUNT_DEBIT.search(text)
    ):
        return "circular"
    if _PROCESSOR_FEE_DEBIT.search(split) or _GLUED_FEE_ENTRY.search(split):
        return "processor_fee"
    if _BILL_DEBIT.search(split):
        return "bill"
    return "other"


def counter_debits(records: Sequence[TransactionClassification], duplicates: set[int]) -> CounterDebits:
    """§8.1: the statement's posted debits that may hold a payer, with their counter-debit readings
    (CounterDebitReading). A card purchase the classifier names as no lender or financing payee is left out (A1
    census: buying at a merchant that shares the payer's word is spending, never circular money); a card-form debit
    it names as a lender (D8) is still a lender debit.

    A card purchase in another bank's form, or one the classifier classes 'pos', that the card-form prefix misses keeps
    its place among the other debits (and counts for recurrence), marked `card` where it reads other, processor_fee or
    bill, never circular or receiving_fee (_CARD_FORM_DEBIT; it keeps that kind); an ATM, ABM or cash withdrawal that
    is no lender's and no circular money is left out (_cash_withdrawal: never a company named ATM or ABM, nor an ACH
    entry); each debit records whether it prints a platform's payout id (processor_payout); a lender debit is read with
    the place words kept, and a person-to-person or push debit to a named recipient records its person_key. Each
    non-lender debit, a card-marked one included, records whether it prints a premium or a retry of one
    (_PREMIUM_DEBIT, on its kind text with Chase's glued SEC code split off); a lender debit never does. A debit whose
    reading names no word is kept when it names a numbered company's number (CounterDebitReading.number), and recurs by
    that number (_head_word); each debit is read without its bank's posting-type label and a leading
    pre-authorized-debit label (classifier._counter_debit_text)."""
    lender: list[_CounterDebit] = []
    other: list[tuple[CounterDebitReading, str, int, bool, str | None, bool, bool]] = []
    for index, record in enumerate(records):
        if index in duplicates or record.amount >= 0 or not record.is_posted:
            continue
        lender_debit = record.classification in LENDER_DEBIT_STATES
        reading, card_purchase = counter_debit_debit_reading(record, keep_places=lender_debit)
        # A debit to a numbered company is kept by its number.
        if reading.legacy is None and not reading.keys and reading.number is None:
            continue
        text = record.normalized_description
        payout = processor_payout(text)
        if lender_debit:
            entity = _lender_entity(_without_receiver_value(text))
            lender.append(_CounterDebit(reading, "lender", _cents(record.amount), entity, False, payout))
        elif not card_purchase:
            kind_text, split = _counter_debit_kind_text(text)
            kind = _counter_debit_kind_of(kind_text, split)
            if kind != "circular" and _cash_withdrawal(text):
                continue
            card = kind in _CARD_KIND_FROM and bool(
                record.classification == "pos" or _CARD_FORM_DEBIT.search(text.strip())
            )
            person_key = None
            if (
                (_CONSUMER_P2P_RAIL.search(text) or _PUSH_RAIL.search(text))
                and reading.heads and reading.heads[0][1]
            ):
                person_key = reading.heads[0][0] + reading.heads[0][1][0]
            premium = _PREMIUM_DEBIT.search(split) is not None
            other.append((reading, kind, _cents(record.amount), payout, person_key, card, premium))
    # "Recurring same-amount debits keep holding": two or more debits of one payer word at one amount (a bill's;
    # never a processor's fee beside its settlement, also_debited).
    amounts = Counter((_head_word(reading), cents) for reading, _, cents, _, _, _, _ in other)
    return CounterDebits(
        tuple(lender),
        tuple(
            _CounterDebit(
                reading, kind, cents, None, amounts[(_head_word(reading), cents)] >= 2, payout, person_key, card,
                premium,
            )
            for reading, kind, cents, payout, person_key, card, premium in other
        ),
    )


#: The kinds a card purchase in another bank's form is marked a card charge on (never circular money or the bank's
#: receiving fee).
_CARD_KIND_FROM = frozenset({"other", "processor_fee", "bill"})


def _cash_withdrawal(text: str) -> bool:
    """An ATM, ABM or cash withdrawal (_CASH_WITHDRAWAL_DEBIT) that names no company leading with ATM or ABM and
    prints no ACH entry field (_ATM_NAMED_COMPANY, _ACH_ENTRY_LABEL). The company's name never reads a cash or posting
    word between ATM or ABM and its legal form, so 'ATM WITHDRAWAL <name> INC' is still a cash withdrawal."""
    return (
        _CASH_WITHDRAWAL_DEBIT.search(text) is not None
        and _ATM_NAMED_COMPANY.search(text) is None and _ACH_ENTRY_LABEL.search(text) is None
    )


def _head_word(reading: CounterDebitReading) -> str | None:
    """The word a debit's recurrence is keyed by. A numbered company's number where the debit reads no word, so a
    numbered funder's daily debits at one amount recur by their number and two numbered payees never share a key."""
    return reading.heads[0][0] if reading.heads else (reading.legacy or reading.number)


def _counter_region(text: str, region: str) -> str:
    """The payer words the counter-debit reading reads: the payer region without PNC's leading INSTPMNTIN
    label, or, where the payer region is empty, the words after a leading RTP CREDIT label
    (_INSTANT_PAYMENT_LABEL, _RTP_CREDIT_NAME).

    Where neither prints, on an e-Transfer row (_E_TRANSFER_RAIL), the sender the rail prints without FROM (RBC's
    and TD's e-Transfer, _p2p_sender_readings), so the same person's round trip can be matched; and a wallet's name
    leading the words (_WALLET_CASH_OUT: a Venmo, Cash App, Square Cash or Apple Cash cash-out, which names no
    sender, §5.2) reads nothing."""
    if region:
        found = _INSTANT_PAYMENT_LABEL.sub("", region)
    else:
        row = _before_receiver(text)
        named = _RTP_CREDIT_NAME.match(row)
        if named is not None:
            found = named.group(1)
        elif _E_TRANSFER_RAIL.search(row):
            found = _p2p_sender_readings(text)[0]
        else:
            found = ""
    return "" if _WALLET_CASH_OUT.match(found) else found


def _sender_name_key(region: str) -> str | None:
    """A person-to-person or push credit's sender as the counter-debit holds match it: the first head word of its payer
    name (classifier._counter_debit_head) glued to the word after it, when the name has one. The name ends at its legal
    form, so the town a payout prints after a company's name is no part of it ('<company> INC <town> <ST>' is a
    one-word name, matched as before)."""
    name: list[str] = []
    for word in payer_name(region).split() if region else ():
        if word in _WIRE_PARTY_LEGAL_FORMS:
            break
        name.append(word)
    head = _counter_debit_head(name)
    return head[0] + head[1][0] if head is not None and head[1] else None


def counter_credit(record: TransactionClassification, text: str, region: str) -> CounterCredit:
    """A posted credit's counter-debit reading, on its payer region, and the facts the debit kinds read. The
    reading reads past an instant-payment rail label (_counter_region).

    A processor's payout is its settlement wording or a payout form before the receiver fields, or a merchant-ID field
    anywhere on the row (_SETTLEMENT_CREDIT, _PAYOUT_FORMS, _MERCHANT_ID_FIELD); `payout` is a platform's payout id
    (processor_payout); `person_key` is set on a credit printing a person-to-person or push rail whose first head word
    has a next word (the glued first two words of the sender's name), and whose sender prints no company form: a
    company's push is compared by the B4 forms as before. `insurer` is False on a credit pass 7 released as an insurer
    paying for the business's work (INSURER_FOR_WORK_METHOD), so a bill to that insurer holds it only as a bill to any
    payer does. Interac's French form (_INTERAC_COURRIEL, whose plural the classifier's rail never reads) is such a rail
    too, so a French autodeposit's sender names a debit as its English twin's does. `released_insurer` is True on that
    released credit, which also_debited holds by a debit naming its carrier only when the debit is circular money, is
    for its own amount, or recurs at one amount printing no premium or retry word. Both readings are read with the
    statement's bank (`record.bank`), so its posting-type label names no payer (classifier._without_posting_type_label:
    RBC's `INSURANCE <insurer>`); a numbered company's reading carries its number."""
    row = _before_receiver(text)
    # TD Canada Trust's e-Transfer code is no sender, so never a counter-debit key.
    words = _counter_region(text, region) if _transfer_code(record) is None else region
    # Read without the statement's bank's posting-type label.
    reading = counter_debit_payer_reading(words, bank=record.bank)
    person_key = None
    if (
        (
            _CONSUMER_P2P_RAIL.search(row) or _PUSH_RAIL.search(row)
            or _INTERAC_COURRIEL.search(row)
        )
        and not company_form(payer_name(words))
    ):
        person_key = _sender_name_key(words)
    return CounterCredit(
        reading=reading,
        cents=_cents(record.amount),
        entity=_lender_entity(region, credit=True) if region else None,
        settlement=(
            _SETTLEMENT_CREDIT.search(row) is not None or _PAYOUT_FORMS.search(row) is not None
            or _MERCHANT_ID_FIELD.search(text) is not None
        ),
        # A credit the insurer-for-work release re-stated is
        # the business's work, no insurer to the bill clause of also_debited.
        insurer=_INSURER_CREDIT.search(row) is not None and record.revenue_match_method != INSURER_FOR_WORK_METHOD,
        payout=processor_payout(text),
        person_key=person_key,
        lender_reading=counter_debit_payer_reading(words, keep_places=True, bank=record.bank),
        # The credit the Q2 release counted as the business's work.
        released_insurer=record.revenue_match_method == INSURER_FOR_WORK_METHOD,
    )


def _same_payer(credit: CounterDebitReading, debit: CounterDebitReading, *, legacy: bool) -> bool:
    """The payer and the debit name one payer: by the B4 forms (their glued forms included), or, where 5.6's reading
    still governs (`legacy`), by 5.6's first distinctive word. First, by a numbered company's number, read on both
    sides only where the numbered-company form prints (CounterDebitReading.number), so debited_as_lender,
    _names_the_payer and _payer_collects read a numbered funder, affiliate or own account as they read a named one."""
    if credit.number is not None and credit.number == debit.number:
        return True
    if legacy and credit.legacy is not None and credit.legacy == debit.legacy:
        return True
    return not credit.keys.isdisjoint(debit.keys)


def _prefix_payer(credit: CounterDebitReading, debit: CounterDebitReading) -> bool:
    """One side's first word, five letters or more, starts the other's, and the longer word runs on into a
    financing root or into the shorter side's next word (_FINANCING_REMAINDER)."""
    for credit_word, credit_next in credit.heads:
        for debit_word, debit_next in debit.heads:
            if credit_word == debit_word:
                continue
            short, long, following = (
                (credit_word, debit_word, credit_next) if len(credit_word) < len(debit_word)
                else (debit_word, credit_word, debit_next)
            )
            if len(short) < _PREFIX_MIN_LETTERS or not long.startswith(short):
                continue
            rest = long[len(short):]
            if _FINANCING_REMAINDER.match(rest) or (
                following and (rest.startswith(following[0]) or (len(rest) >= 3 and following[0].startswith(rest)))
            ):
                return True
    return False


def debited_as_lender(credit: CounterCredit, debits: CounterDebits, *, prefix: bool) -> bool:
    """§8.1 payer_debited_as_lender: a lender or financing debit names the payer. When both name a registry entity,
    they match when it is one entity; 5.6's first-word match still holds either way. Otherwise the B4 forms match, and
    with `prefix` (pass 7, an unverified credit) a cut or glued spelling (_prefix_payer). Both sides are read with the
    place words kept (a funder may carry a state's name), and a person-to-person or push credit from a named person
    (its person_key) also matches a lender debit printing that whole name. The whole name is one more arm, never the
    only one: the first word, the B4 forms and the prefix still read such a credit, since this hold never lets a
    funder's money into True (a funder printing no legal form, pushing by a real-time or Zelle rail and pulling under a
    glued or one-word name)."""
    reading = credit.lender_reading if credit.lender_reading is not None else credit.reading
    for debit in debits.lender:
        if credit.person_key is not None and credit.person_key in debit.reading.keys:
            return True
        if reading.legacy is not None and reading.legacy == debit.reading.legacy:
            return True
        if credit.entity is not None and debit.entity is not None:
            if credit.entity == debit.entity:
                return True
            continue
        if _same_payer(reading, debit.reading, legacy=False):
            return True
        if prefix and _prefix_payer(reading, debit.reading):
            return True
    return False


def also_debited(credit: CounterCredit, debits: CounterDebits) -> bool:
    """§8.1 payer_also_debited: a debit that can be circular money names the payer (an own
    account, an affiliate, a funder that collects).
    - The bank's receiving fee never holds the payer.
    - A transfer, wire, person-to-person or own-account debit matches as 5.6 read it too (the guard: no such match is
      ever lost).
    - Any other debit matches by the B4 forms; one for the credit's own amount matches as 5.6 read it too (the credit
      undoes it).
    - A processor's fee beside a settlement never holds unless the debit is for the credit's own amount; a bill to a
      payer that is no insurer never holds unless the debit is for the credit's own amount or recurs at one amount.
      §4.2: a processor's fixed monthly or per-batch fee posts at one amount,
      so its recurrence is the processor's shape, never a collector's; a bill recurring at one amount can be a
      collector's draw and keeps holding.

    In this order: a platform's payout and the platform's own pull, each printing a payout id,
    never hold unless the pull is for the payout's own amount; a person-to-person or push credit from a named person
    matches by its person_key, or by its first word on a debit for its own amount (_names_the_payer); after the bill
    rule, a processor's payout (its settlement wording, payout forms or merchant-ID field) is never held by a card
    charge or by a one-off other debit of the processor's own unless the debit is for its own amount (standard A1,
    §4.2: its fee, subscription or card charge is the processor's shape, never circular money). A card charge keeps its
    own kind, so beside a credit with no payout form a card-form bill reads the bill rule and any other card charge
    holds as its kind does.

    After the bill rule (the MCA principle; standard A11, B6): a credit the Q2 release counted
    as an insurer paying for the business's work (CounterCredit.released_insurer) is held by a debit naming its
    carrier only when that debit is circular money, is for the credit's own amount, or recurs at one amount printing
    no premium or retry word (_CounterDebit.premium). A premium the business pays the carrier that pays it for its
    work is an ordinary expense, never money going round, and it recurs at one amount by nature, as a processor's
    fixed fee does, so it never holds the credit, recurring or not. An insurer the release did not count keeps B4's
    hold beside its premium or bill."""
    for debit in debits.other:
        same_amount = debit.cents == credit.cents
        if credit.payout and debit.payout and not same_amount:
            continue
        if debit.kind == "receiving_fee":
            continue
        if not _names_the_payer(
            credit, debit, legacy=debit.kind == "circular" or same_amount, same_amount=same_amount,
        ):
            continue
        if debit.kind == "processor_fee" and credit.settlement and not same_amount:
            continue
        if debit.kind == "bill" and not credit.insurer and not same_amount and not debit.recurring:
            continue
        # A released insurer's carrier debits.
        if (
            credit.released_insurer and not same_amount and debit.kind != "circular"
            and (debit.premium or not debit.recurring)
        ):
            continue
        if credit.settlement and not same_amount and (
            debit.card or (debit.kind == "other" and not debit.recurring)
        ):
            continue
        return True
    return False


def _payer_collects(credit: CounterCredit, debits: CounterDebits) -> bool:
    """§8.1, §8.7: the payer also collects from the account. True when a lender or financing debit names it
    (debited_as_lender, with the pass-7 prefix), or any other posted debit names it by the B4 forms, 5.6's first
    distinctive word (legacy) or a cut or glued spelling (_prefix_payer), the bank's receiving fee and a card charge
    aside; a card purchase the classifier names is never among the debits (counter_debits). Deliberately stricter than
    also_debited: no bill, processor-fee, settlement or payout-pair exemption, and no amount or recurrence test (a
    documented over-hold of the owner's "collecting loan payments")."""
    if debited_as_lender(credit, debits, prefix=True):
        return True
    for debit in debits.other:
        if debit.kind == "receiving_fee" or debit.card:
            continue
        if _same_payer(credit.reading, debit.reading, legacy=True) or _prefix_payer(credit.reading, debit.reading):
            return True
    return False


def _names_the_payer(credit: CounterCredit, debit: _CounterDebit, *, legacy: bool, same_amount: bool) -> bool:
    """A person-to-person or push credit whose sender prints a name of two words or more and no company form names the
    debit's payer by that whole name (its person_key, the glued first two words, in the debit's keys); and a
    person-to-person or push debit to a recipient printing such a name (now that the rail's own word no longer reads as
    the debit's) is named by a credit only by that whole name (its person_key in the credit's keys): a given name, a
    rail's name or a town alone never does. A debit for the credit's own amount that is no such person-to-person debit
    still names the credit's payer by 5.6's first word, as B4 read it (the credit undoes it)."""
    if credit.person_key is not None:
        if (
            same_amount and debit.person_key is None and credit.reading.legacy is not None
            and credit.reading.legacy == debit.reading.legacy
        ):
            return True
        return credit.person_key in debit.reading.keys
    if debit.person_key is not None:
        return debit.person_key in credit.reading.keys
    return _same_payer(credit.reading, debit.reading, legacy=legacy)
