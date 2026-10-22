"""Pay wording, lending-bank payer, premium-coded rows."""
from __future__ import annotations

import re
from typing import Sequence, TYPE_CHECKING

from analysis.classification.payees import _is_payroll_provider_row
from analysis.descriptor.holder import _business_account, account_name_text, holder_named
from analysis.descriptor.lexical import _is_reference_token, company_form
from analysis.descriptor.rails import _matches_any
from analysis.descriptor.words import _HOLDER_TRADE_NAME, _PAYROLL_PATTERNS, _RECEIVER_FIELD_VALUE
from analysis.true_revenue.channel import cpa_payroll_code
from analysis.true_revenue.hold_text import _hold_text, _layout_entry
from analysis.true_revenue.holder_names import _p2p_person_name, _without_holder_name
from analysis.true_revenue.public_payers import consumer_entry, government_payer, healthcare_payer_match, public_region
from analysis.true_revenue.words import (
    _DIRECT_DEPOSIT_WORDS,
    _EARNED_WAGE_ACCESS,
    _HOLDER_RUN_CUT_FROM,
    _HOLDER_RUN_CUT_KEEPS,
    _INSURER_NAME,
    _LENDING_BANK_PAYER,
    _PAY_WORDS,
    _PREMIUM_CODED,
    _RECEIVER_LABEL,
)

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


_INSURER_ABBREVIATION = re.compile(r"\bINS\b")
_COMMISSION_WORD = re.compile(r"(?<![A-Z])(?:COMMS?|COMMISSIONS?)\b")
_PUBLIC_HEALTH_PAYERS = frozenset({
    "Medicare", "State Medicaid program", "TRICARE", "VA Community Care", "Noridian", "Palmetto GBA",
    "Novitas Solutions", "WPS Health Solutions", "National Government Services", "CGS Administrators",
    "First Coast Service Options",
})


def _pay_wording(
    row: str, bank: str | None, *, text: str = "", account_name: str | None = None, business: bool = False
) -> bool:
    """§8.1, Q8: pay wording on the row before its receiver fields (_PAY_WORDS), a payroll provider, TD Canada
    Trust's payroll-deposit code, or an earned-wage access provider's push. Or the direct-deposit words with a sign
    of a person's pay (_direct_deposit_pay; `text` is the credit's revenue text with its receiver fields, `business`
    the statement's _business_shape)."""
    if (
        _PAY_WORDS.search(row) or _EARNED_WAGE_ACCESS.search(row) or _is_payroll_provider_row(row)
        or cpa_payroll_code(row, bank)
    ):
        return True
    return _direct_deposit_pay(text or row, row, account_name, business=business)


def _direct_deposit_pay(text: str, row: str, account_name: str | None, *, business: bool) -> bool:
    """§8.1, §8.8 (Q8): the direct-deposit words (_DIRECT_DEPOSIT_WORDS) on `row` are a person's pay when the account
    does not read as a business's (`business` False, _business_shape), when a payroll provider is named on the row, when
    the receiver is a person (_person_receiver), or on a consumer (PPD or WEB) entry (consumer_entry) to a receiver that
    is not a company (_business_receiver). The rest of the pay words (_PAY_WORDS) and the payroll providers of
    _is_payroll_provider_row are read by _pay_wording before these. On a business's account a company's direct deposit
    to the business ('<payer> DIR DEP <date> <id>', a carrier's settlement to its contractor) is no pay wording: the
    credit takes its payer's reading (Q6, or named_payer_unlabelled on a layout with no ACH form)."""
    found = _DIRECT_DEPOSIT_WORDS.search(row)
    if found is None:
        return False
    if not business:
        return True
    # A payroll provider named on the row (the classifier's payroll words: ADP, PAYCHEX, GUSTO, CERIDIAN), whose
    # direct deposit is the employer's payroll it runs.
    if _matches_any(row, _PAYROLL_PATTERNS):
        return True
    return _person_receiver(text, row[found.end():], account_name) or (
        consumer_entry(text, account_name) and not _business_receiver(text, account_name)
    )


def _business_receiver(text: str, account_name: str | None) -> bool:
    """§8.1, §8.8 (Q8: "a PPD entry to a person"): a receiver field's value (INDN, IND NAME, RECEIVER
    NAME, its letters-only words, as _person_receiver reads it) names a business: it prints a company form ('INDN:<NAME>
    ROUTES LLC'), or it is the holder's own company-formed name (_holder_business_name: 'INDN:<NAME> ROUTES' on the
    account of '<NAME> ROUTES LLC'). A person, a holder with no company form (a person, a DBA name with no form) or a
    receiver with no form that is not the holder's whole name is no business. Never holder_named's looser reading, which
    also reads a shorter run of the holder's name, a DBA's person side, a middle initial or a reversed order as the
    holder, so the owner's own pay ('INDN:JOHN SAMPLE' on 'JOHN SAMPLE PLUMBING LLC''s account) keeps the entry's pay
    reading."""
    for found in _RECEIVER_FIELD_VALUE.finditer(text):
        value = " ".join(word for word in _RECEIVER_LABEL.sub("", found.group(0), count=1).split() if word.isalpha())
        if value and (company_form(value) or _holder_business_name(value, account_name)):
            return True
    return False


#: §8.1, §8.8: the legal forms a holder's company-formed name may print after its name words, which a receiver
#: field may leave off or print cut ('<NAME> ROUTES L').
_RECEIVER_HOLDER_FORMS = frozenset({
    "LLC", "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LP", "LLP", "LLLP", "PLLC",
    "PLC", "ULC",
})


def _holder_business_name(value: str, account_name: str | None) -> bool:
    """§8.1, §8.8: a receiver's letters-only words (`value`) are the holder's own company-formed name (the holder's
    name prints a company form and no DBA or AKA): every name word of it, in order, its trailing form left off, printed
    whole or cut ('<NAME> ROUTES', '<NAME> ROUTES L' for '<NAME> ROUTES LLC'), or that name with its last word of
    _HOLDER_RUN_CUT_FROM letters or more cut by the bank's field to _HOLDER_RUN_CUT_KEEPS letters or more and nothing
    after it. A leading THE is no name word on either side, and a printed L L C is LLC. A shorter run of the name (the
    owner's own name leading '<person> PLUMBING LLC'), a DBA's side, a middle initial, a reversed order or a word after
    the name that is no form is never the business: a person receiver keeps the entry's reading. Recorded residual, an
    owner item beside Q8 (§17.1): a holder whose formed name is a person's name with a form ('<person> LLC') reads as
    the business when the receiver prints that name whole, with its own form cut, or with its last word cut (two name
    words or more), as nothing in the text tells it from '<NAME> ROUTES' on '<NAME> ROUTES LLC'. A last word after the
    name that is no whole form reads as a cut form only when one of the holder's own forms starts with it ('L', 'LL' on
    '... LLC'; never 'L' on '... CORP'), and a one-word holder's name is never read cut ('NORT' on 'NORTHWIND LLC'), as
    _holder_run_cut needs two words."""
    printed = account_name_text(account_name)
    if not printed or not company_form(printed) or _HOLDER_TRADE_NAME.search(printed):
        return False

    def name_words(name: str) -> list[str]:
        words = [word for word in re.sub(r"(?<![A-Z])L L C(?![A-Z])", "LLC", name).split() if word.isalpha()]
        return words[1:] if words[:1] == ["THE"] else words

    holder = name_words(printed)
    popped: list[str] = []
    while holder and holder[-1] in _RECEIVER_HOLDER_FORMS:
        popped.insert(0, holder.pop())
    words = name_words(value)
    count = len(holder)
    if not holder or len(words) < count or words[: count - 1] != holder[:-1]:
        return False
    last, rest = words[count - 1], words[count:]
    if last != holder[-1]:
        return (
            count >= 2 and not rest and len(holder[-1]) >= _HOLDER_RUN_CUT_FROM and len(last) >= _HOLDER_RUN_CUT_KEEPS
            and holder[-1].startswith(last)
        )
    return all(word in _RECEIVER_HOLDER_FORMS for word in rest[:-1]) and (
        not rest or rest[-1] in _RECEIVER_HOLDER_FORMS or any(form.startswith(rest[-1]) for form in popped)
    )


#: §8.1, §8.8: the trace and reference labels a layout prints after a direct deposit's receiver, never a
#: person's name word.
_TAIL_TRACE_LABELS = frozenset({"TRN", "TRACE", "REF", "ID"})


def _person_receiver(text: str, tail: str, account_name: str | None) -> bool:
    """§8.1, §8.8: the direct deposit's receiver is a person: a receiver field's value (INDN, IND NAME, RECEIVER NAME)
    that reads as a person's name, or, on a layout that prints the receiver after the deposit's references with no
    label (Wells Fargo's '<payer> DIR DEP <date> <id> <receiver>'), the words after those references (`tail`), each a
    letters-only word, reading as one (_p2p_person_name). A reference, or a trace label (_TAIL_TRACE_LABELS) and its
    number, printed after the receiver is skipped too ('<receiver> 123456', '<receiver> TRN 1234'). The holder's own
    name is never the person (a business's name printed without its form)."""
    names = [
        " ".join(word for word in _RECEIVER_LABEL.sub("", found.group(0), count=1).split() if word.isalpha())
        for found in _RECEIVER_FIELD_VALUE.finditer(text)
    ]
    words = tail.split()
    while words and _is_reference_token(words[0]):
        words.pop(0)
    while words and (_is_reference_token(words[-1]) or words[-1] in _TAIL_TRACE_LABELS):
        words.pop()
    if words and all(word.isalpha() for word in words):
        names.append(" ".join(words))
    return any(
        name and _p2p_person_name(name) and not holder_named(name, account_name)
        and _without_holder_name(name, account_name).strip() == name
        for name in names
    )


def _business_shape(records: Sequence[TransactionClassification], duplicates: set[int]) -> bool:
    """§8.1, §8.8: the statement's account reads as a business's: its account name prints a business product word or a
    legal form (the classifier's _business_account) or a company form, or the statement shows the holder's own payroll
    (a posted debit the classifier reads as payroll). Any other account is consumer-shaped, and a direct deposit to it
    is a person's pay (_direct_deposit_pay)."""
    account_name = records[0].account_name if records else None
    holder = account_name_text(account_name)
    if _business_account(account_name) or (holder and company_form(holder)):
        return True
    return any(
        index not in duplicates and record.amount < 0 and record.is_posted and record.classification == "payroll"
        for index, record in enumerate(records)
    )


def lending_bank_payer(text: str, region: str) -> bool:
    """§8.1, T4: a lending bank (_LENDING_BANK_PAYER) is the payer: read on the payer region, or, on a row with no payer
    region, on the row before its receiver fields with the posting labels removed (_hold_text), as financing_named reads
    it. Celtic Bank's Bluevine line (DES BV LOAN) is the registry's financing proceeds already."""
    return _LENDING_BANK_PAYER.search(region or _hold_text(text)) is not None


def _premium_coded(text: str, region: str) -> bool:
    """§8.6 Q6c: a healthcare, insurer or health-plan payer (HEALTHCARE_PAYER_ALIASES, an insurer's name or its INS
    abbreviation) whose entry is premium-coded (_PREMIUM_CODED). Read only in the entry field the layout prints (Bank
    of America's DES, Chase's CO ENTRY DESCR); a row that prints none keeps its reading. A commission word in the
    entry keeps its reading too (_COMMISSION_WORD), and a public payer is never read: a government payer (the
    public-payer patterns) or a public health program (_PUBLIC_HEALTH_PAYERS: Medicare and its administrative
    contractors, Medicaid, TRICARE, VA)."""
    entry = _layout_entry(text)
    if not region or _PREMIUM_CODED.search(entry) is None or _COMMISSION_WORD.search(entry) is not None:
        return False
    if government_payer(public_region(text)):
        return False
    health = healthcare_payer_match(region)
    if health is not None:
        return health[0] not in _PUBLIC_HEALTH_PAYERS
    return bool(_INSURER_NAME.search(region) or _INSURER_ABBREVIATION.search(region))
