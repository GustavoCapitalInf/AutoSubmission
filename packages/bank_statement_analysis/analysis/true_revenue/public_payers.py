"""Government, healthcare, consumer and personal-income payers."""
from __future__ import annotations

import re
from functools import cache

from analysis.classification.tax_forms import government_form_payer
from analysis.classification_registry import HEALTHCARE_PAYER_ALIASES
from analysis.description_text import RECEIVER_FIELD_LABELS
from analysis.descriptor.credit_words import _PUBLIC_PAYER_NAME, _PUBLIC_PAYER_NAME_VETO, _PUBLIC_PAYER_TEMPLATE
from analysis.descriptor.holder import account_name_text
from analysis.descriptor.lexical import (
    _before_receiver,
    _is_reference_token,
    _payee_region,
    _strip_revenue_template,
    company_form,
)
from analysis.descriptor.payer import payer_region
from analysis.descriptor.rails import _is_wire_row
from analysis.descriptor.words import (
    IRS_TREASURY_FORM,
    REVENUE_GENERIC_WORDS,
    _BANK_COMPANY_FORM,
    _NUMBERED_COMPANY_REGION,
    _REVENUE_TEMPLATE_PREFIX,
)
from analysis.payee_matcher import registry_match
from analysis.true_revenue.channel import cpa_payment_code
from analysis.true_revenue.hold_text import _hold_text
from analysis.true_revenue.sender import _wire_originator_text
from analysis.true_revenue.words import _CPA_PAYMENT_CODE, _ENTRY_COMPANY_FORM


#: §8.1, §20: the government's personal-benefit descriptors, read as the whole payer (government_benefit) after the
#: posting words and template prefixes (classifier.government_form_payer), with the CRA's originator name (CANADA)
#: before or after them and a posting code or a reference after them. The Canadian Payments Association's federal
#: benefit descriptors: the child, essentials (the GST/HST credit's name since 2026, in full 'CANADA GROCERIES AND
#: ESSENTIALS BENEFIT'), workers and disability benefits, and Old Age Security. A provincial benefit the CRA pays on a
#: province's behalf ("Canada PRO"): the provincial payment code with the CRA's originator ('PROV LOCAL GVT PAYMENT
#: CANADA', '... CANADA PRO'), its PRO label ('PROV LOCAL GVT PRO ONTARIO') and 'CANADA PRO DEPOSIT'. So 'CANADA CHILD
#: CARE CENTRE INC', 'CANADA DISABILITY BENEFITS CONSULTING INC', 'OLD AGE SECURITY SYSTEMS LTD' and 'PROVINCIAL
#: PAYMENT CANADA GOOSE SUPPLY' are payers, and a provincial payment from a province names no benefit (its purpose is
#: not printed).
_PROVINCES = (
    r"(?:ONTARIO|QUEBEC|NOVA SCOTIA|NEW BRUNSWICK|MANITOBA|BRITISH COLUMBIA|BC|PRINCE EDWARD ISLAND|PEI|SASKATCHEWAN"
    r"|ALBERTA|NEWFOUNDLAND(?: AND LABRADOR)?|YUKON|NORTHWEST TERRITORIES|NUNAVUT)"
)
#: RBC's cut label of the same provincial payment code, 'Prov./Loc.G.Paym' ('PROV LOC G PAYM CANADA'),
#: read as its spelled-out form is.
_GOVERNMENT_BENEFIT_PAYER = re.compile(
    r"(?:(?:CANADA )?(?:CANADA (?:CHILD|(?:GROCERIES (?:AND )?)?ESSENTIALS|WORKERS|DISABILITY) BENEFITS?"
    r"|OLD AGE SECURITY)(?: CANADA)?"
    rf"|(?:PROV LOCAL GVT(?: PAYMENT)?|PROV LOC G(?:VT)? PAYM(?:ENT)?|PROVINCIAL PAYMENT)"
    rf" (?:CANADA(?: PRO)?|PRO(?: {_PROVINCES})?)"
    r"|CANADA PRO(?: DEPOSIT)?)"
    r"(?: (?:MSP|DIV|\d+))*"
)
#: GOV (B): the benefit entries read inside a row: a state's unemployment-insurance direct deposit ('NYS DOL UI DD')
#: and the IRS's economic impact payment ('TAX EIP3'), this one on an IRS Treasury row only. A company form after the
#: entry, before the row's next field, vetoes it ('NORTHWIND UI DD LLC'); 'FABRIKAM TAX EIP SERVICES' prints no IRS
#: form.
_GOVERNMENT_BENEFIT_ENTRY = re.compile(r"\bUI DD\b|(?<![A-Z])(?P<eip>TAX ?EIP ?\d?)\b")
_ENTRY_FIELD_LABEL = re.compile(r"\b(?:CO ID|DES|ID|INDN|IND ID|IND NAME|ORIG ID|SEC|TRACE|EED|TRN|CCD|PPD|CTX|WEB)\b")
#: §8.1: benefit and pension credits. GOV: the government's personal-benefit forms are read by government_benefit. And
#: a health savings account's distribution ('HSADISTRIB', 'HSA DISTRIB...': a person's own medical savings) and a life
#: insurer's annuity payment cut by a sixteen-character originator field ('<insurer> LIFE AN DISBPYMT', the whole
#: ANNUIT... word cut away).
_PERSONAL_INCOME = re.compile(
    r"(?<![A-Z])(?:XX)?SOC SEC\b|\bSSA\b|\bSSI\b|(?<![A-Z])SUPP SEC\b|(?<![A-Z])(?:XX)?VA BEN\w*"
    r"|(?<![A-Z])UNEMPLOY\w*|(?<![A-Z])UI BEN\w*"
    r"|(?<![A-Z])CHI?LD ?SUPP\w*\b|(?<![A-Z])CHILD ?CTC\b|(?<![A-Z])PENSION\b|(?<![A-Z])ANNUIT\w*"
    r"|(?<![A-Z])RETIRE\w*"
    r"|(?<![A-Z])HSA ?DISTRIB\w*|(?<![A-Z])LIFE AN DISB\w*"
)
#: §8.1, §20: HHS's CARES Act Provider Relief Fund ('US HHS STIMULUS', its glued entry 'HHSPAYMENT') and the USDA's
#: farm programs, the Farm Service Agency's and the Commodity Credit Corporation's Treasury forms ('FSA TREAS 310',
#: 'CCC TREAS 310'; USDA's own 'USDA TREAS 310' also pays vendors and keeps its reading); and (the coordinator's
#: ruling on the class-E form) ESDC's federal payment code, its grants and contributions ('GOVERNMENT ESDC ... FEDERAL
#: PMT'). §8.1's GRANT word already holds a row that prints it. Never a name that holds the letters: 'HHS SUPPLY CO',
#: 'NORTHWIND FSA SERVICES LLC'. The CRA's Canada Carbon Rebate, glued as TD Canada Trust prints it ('CDACARBONREBATE
#: CCR') or spaced, read with no left word boundary (its spaced spelling's REBATE word holds it too); a name that only
#: holds CARBON ('<NAME> CARBON WORKS LLC') is no rebate.
_GOVERNMENT_GRANT = re.compile(
    r"(?<![A-Z])HHS ?STIMULUS\b|(?<![A-Z])HHSPAYMENT(?:SEC)?\b|(?<![A-Z])(?:FSA|CCC) TREAS ?\d{3}\b"
    r"|(?<![A-Z])GOVERNMENT ESDC\b(?=.*(?<![A-Z])(?:FEDERAL PMT|PAIEMENT FEDERAL)\b)"
    r"|(?:CANADA ?|CDA ?)CARBON ?REBATE\b"
)
#: The CRA's Canada Emergency Wage Subsidy, read as the whole payer (government_form_payer) with the CRA's name
#: before or after it, so 'CANADA CEWS CONSULTING INC' is a payer.
_WAGE_SUBSIDY_PAYER = re.compile(r"(?:CANADA )?CEWS(?: CANADA)?(?: (?:MSP|DIV|\d+))*")
#: §8.4, T13: an account designation printed by a named transfer. And the checking abbreviations CHCKING, CHKING and CKG
#: ('COMM ONLINETRANSFER FROM COMM BUS CHCKING ...'), which are never a transfer's counterparty words either
#: (_ACCOUNT_WORDS).
_ACCOUNT_DESIGNATION = re.compile(
    r"(?<![A-Z])(?:CHECKING|CHKG|SAVINGS|SAVING|SVGS|MONEY MARKET|ACCOUNT|ACCT|EVERYDAY)\b|\b(?:CHK|SAV|MMA|DDA)\b"
    r"|\bX{2,}\d{2,}\b|(?<![A-Z])ENDING (?:IN )?\d{3,}\b"
    r"|(?<![A-Z])(?:CHCKING|CHKING)\b|\bCKG\b"
)
#: T13: a bare 'FROM <3+ digits>' designates an account too ('ONLINE TRANSFER FROM 1234 <name>'), unless the
#: digits start a numbered company's name (§5.2, T11: 'TRANSFER FROM 1234567 ONTARIO INC').
_FROM_ACCOUNT_DIGITS = re.compile(r"(?<![A-Z])FROM (?=\d{3,}\b)")
#: §8.4, T13: Square prints a move from one of the holder's savings folders as 'TRANSFER IN <folder>' ('TRANSFER IN
#: GENERAL SAVINGS', 'TRANSFER IN TAX', 'TRANSFER IN RAINY DAY', 'TRANSFER IN RENT'): on a Square statement, a folder
#: name with no company form designates the holder's own account. Never read on another bank (Wealthsimple prints its
#: memo there: 'TRANSFER IN <memo>'). The B02 brief's person test is not applied. Square prints an outside sender in
#: Details before its activity type ('<sender> TRANSFER IN', which is read like any named transfer), so only a folder
#: move prints TRANSFER IN first, and a folder named for a person is still the holder's own money.
_SQUARE_BANK = re.compile(r"(?<![A-Z])SQUARE\b")
_SQUARE_FOLDER_TRANSFER = re.compile(r"^TRANSFER IN (?!FROM\b)(?P<folder>[A-Z]+(?: [A-Z]+)*)$")


def _account_designation(row: str, bank: str | None = None) -> bool:
    """§8.4, T13: the row prints an account designation (_ACCOUNT_DESIGNATION); or a bare 'FROM <3+ digits>' that
    starts no numbered company (_FROM_ACCOUNT_DIGITS), or Square's savings-folder transfer (_square_folder)."""
    if _ACCOUNT_DESIGNATION.search(row) is not None or _square_folder(row, bank):
        return True
    return any(
        _NUMBERED_COMPANY_REGION.match(row[found.end():]) is None
        for found in _FROM_ACCOUNT_DIGITS.finditer(row)
    )


def _square_folder(row: str, bank: str | None) -> bool:
    """§8.4, T13: on a Square statement, 'TRANSFER IN <folder>' whose folder prints no company form."""
    if not bank or _SQUARE_BANK.search(bank.upper()) is None:
        return False
    found = _SQUARE_FOLDER_TRANSFER.match(row)
    return found is not None and not company_form(found.group("folder"))


#: §8.6: a PPD or WEB entry is read only in the SEC code's own slot: Chase's 'SEC <code>' (its glued 'HCCLAIMPMTSEC
#: CCD' split by revenue_text), the code printed right before its TRACE or ID field when a line wrap drops the label
#: ('... PAYMENT PPD TRACE', '... 540302 WEB ID <id>'), the code Bank of America prints after the company id or at the
#: row's end ('CO ID <id> PPD', 'ID <id> PPD'), and a layout's 'ACH <code>'. Never a name or a receiver field: each
#: receiver field's value is removed first, up to the next CO ID, TRN, TRACE or SEC field (not at a code word, so
#: 'INDN:CONTOSO WEB STUDIO LLC CO ID <id> CCD' is a CCD entry).
_CONSUMER_ENTRY = re.compile(
    r"\bSEC (?:PPD|WEB)\b|\b(?:PPD|WEB) (?:TRACE|ID)\b|\bID \S+ (?:PPD|WEB)\b|\bACH (?:PPD|WEB)\b"
)
_RECEIVER_THROUGH_NEXT_FIELD = re.compile(
    rf"\b(?:{'|'.join(RECEIVER_FIELD_LABELS)})\b.*?(?=\b(?:CO ID|TRN|TRACE|SEC)\b|$)"
)


#: §8.6: the code a layout prints as the row's last word, after a receiver value that no later field ends ('...
#: INDN:CONTOSO BAKERY LLC PPD').
_TRAILING_CONSUMER_CODE = re.compile(r" (PPD|WEB)$")
#: §8.6: the code printed right before Bank of America's DES label, after a company form or a reference token
#: ('NORTHWIND SUPPLY LLC PPD DES:...'); after a name word it is the payer's name ('NORTHWIND WEB'). FW wave 3: PPD
#: is never a name word, so it is the code after any word ('NORTHWIND SUPPLY PPD DES:...').
_CODE_BEFORE_DES = re.compile(r"(\S+) (PPD|WEB) DES\b")
_CODE_AFTER_TEMPLATE = re.compile(r"(?:PPD|WEB)\b")


def consumer_entry(text: str, account_name: str | None = None) -> bool:
    """§8.6: the row prints a PPD or WEB entry in its SEC code's slot (_CONSUMER_ENTRY), read on the row with every
    receiver field's value removed (_RECEIVER_THROUGH_NEXT_FIELD). And in three more slots, still never inside a name or
    a receiver field: the row's last word after a receiver value that no later field ends, unless it is the last word of
    the holder's own name (`account_name`: 'INDN:CONTOSO WEB' is the holder); the code before DES after a company form
    or a reference token (_CODE_BEFORE_DES); and the code right after the posting label a row starts with ('ACH CREDIT
    PPD <payer>', the classifier's revenue template prefixes)."""
    if _CONSUMER_ENTRY.search(_RECEIVER_THROUGH_NEXT_FIELD.sub(" ", text)) is not None:
        return True
    trailing = _TRAILING_CONSUMER_CODE.search(text)
    if trailing is not None:
        receiver = None
        for found in _RECEIVER_THROUGH_NEXT_FIELD.finditer(text):
            receiver = found
        holder = account_name_text(account_name).split() if account_name else []
        if (
            receiver is not None and receiver.end() == len(text)
            and len(receiver.group(0).split()) > 2
            and not (holder and holder[-1] == trailing.group(1))
        ):
            return True
    before_des = _CODE_BEFORE_DES.search(_before_receiver(text))
    if before_des is not None and (
        before_des.group(2) == "PPD"
        or _BANK_COMPANY_FORM.fullmatch(before_des.group(1)) or _is_reference_token(before_des.group(1))
    ):
        return True
    template = _REVENUE_TEMPLATE_PREFIX.match(text)
    return template is not None and template.end() > 0 and _CODE_AFTER_TEMPLATE.match(text, template.end()) is not None


#: §8.1 personal_income (standard A4, A16, E3): RETIRE... is a payer's own name word, never a person's retirement
#: income, inside the payer region in two places: before an operator's word (a retirement residence, community, village
#: or home paying its vendor: _RETIRE_OPERATOR_NAME), and on TD Canada Trust, ending the payer field TD cuts to fifteen
#: characters (_TD_PAYER_WIDTH) before an electronic-payment CPA code ('<NAME> RETIREM MSP', '<NAME> RETIREME AP': the
#: company form is cut away). PENSION, ANNUIT..., an entry or purpose word, a recordkeeper's or advisor's name
#: (RETIREMENT SERVICES, PLAN, SYS, ADVISORS), an uncut TD name, the PAY code and every other bank keep the hold.
_TD_PAYER_WIDTH = 15
_RETIRE_OPERATOR_NAME = re.compile(
    r"(?<![A-Z])RETIRE\w* (?=(?:RESIDENCES?|COMMUNIT\w*|LIVING|HOMES?|VILLAGES?|CENTRES?|CENTERS?|LODGE|MANOR|SUITES)\b)"
)
_RETIRE_CUT_WORD = re.compile(r"RETIRE[A-Z]*")


#: §5.2, §8.6: a healthcare alias of this many letters or fewer (WPS, UHC, VPAY, AETNA, CIGNA, OPTUM, ZELIS, VA CCN),
#: and ANTHEM, a common word in business names, is read only as the whole payer name: the region is the alias, before
#: it only reference tokens, generic words and health-plan words, and after it nothing, a reference token, a company
#: form, a health-plan word (_HEALTH_PLAN_WORDS, a Blue-plan form) or another healthcare alias, which may then run on
#: ('UHC PLAN OF THE <place>'). 'ANTHEM ROOFING' and 'WPS INDUSTRIES' are other companies. A longer alias keeps the
#: registry's token read.
_SHORT_HEALTHCARE_ALIAS_LETTERS = 5
_WHOLE_NAME_HEALTHCARE_ALIASES = frozenset({"ANTHEM"})
_HEALTH_PLAN_WORDS = frozenset({
    "HEALTH", "HEALTHCARE", "HLTH", "HLTHCARE", "HC", "PLAN", "PLANS", "INS", "INSURANCE", "INSUR", "CLAIM", "CLAIMS",
    "CLMS", "HCCLAIMPMT", "BLUE", "BC", "BCBS", "LIFE", "BENEFIT", "BENEFITS", "COMMUNITY", "MEDICARE", "MEDICAID",
    "DENTAL", "VISION", "RX", "PHARMACY", "PROVIDER", "NETWORK",
})
_BLUE_PLAN_WORD = re.compile(r"BCBS[A-Z]*")


def _short_healthcare_alias(alias: str) -> bool:
    return len(alias.replace(" ", "")) <= _SHORT_HEALTHCARE_ALIAS_LETTERS or alias in _WHOLE_NAME_HEALTHCARE_ALIASES


@cache
def _short_healthcare_aliases() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """(entity, alias words) of every short healthcare alias, the longest first."""
    found = [
        (entity, tuple(alias.split()))
        for entity, aliases in HEALTHCARE_PAYER_ALIASES.items()
        for alias in aliases
        if _short_healthcare_alias(alias)
    ]
    return tuple(sorted(found, key=lambda item: -len(" ".join(item[1]))))


def _health_plan_word(word: str) -> bool:
    return word in _HEALTH_PLAN_WORDS or _BLUE_PLAN_WORD.fullmatch(word) is not None


def healthcare_payer_match(region: str) -> tuple[str, str] | None:
    """§5.2: the (entity, alias) HEALTHCARE_PAYER_ALIASES names on a payer region, a short alias only as the whole
    payer name (_short_healthcare_alias); or None."""
    if not region:
        return None
    found = registry_match(region, HEALTHCARE_PAYER_ALIASES)
    if found is None or not _short_healthcare_alias(found[1]):
        return found
    words = region.split()
    start = 0
    while start < len(words) and (
        _is_reference_token(words[start]) or _health_plan_word(words[start])
        or words[start] in REVENUE_GENERIC_WORDS
    ):
        start += 1
    for entity, alias in _short_healthcare_aliases():
        if tuple(words[start:start + len(alias)]) != alias:
            continue
        rest = words[start + len(alias):]
        while rest and _is_reference_token(rest[0]):
            rest = rest[1:]
        if not rest or _health_plan_word(rest[0]) or _BANK_COMPANY_FORM.fullmatch(rest[0]) is not None:
            return entity, " ".join(alias)
        # Another healthcare alias right after it ('OPTUM VA CCN').
        other = registry_match(" ".join(rest), HEALTHCARE_PAYER_ALIASES)
        if other is not None and tuple(rest[:len(other[1].split())]) == tuple(other[1].split()):
            return entity, " ".join(alias)
    return None


def healthcare_payer(region: str) -> bool:
    """§5.2: a payer region that matches HEALTHCARE_PAYER_ALIASES."""
    return healthcare_payer_match(region) is not None


def government_payer(region: str) -> bool:
    """§5.2: a payer region the public-payer patterns of §7.6 match at its start, and the payer-name veto does not."""
    if not region:
        return False
    name = _PUBLIC_PAYER_TEMPLATE.sub("", region, count=1)
    found = _PUBLIC_PAYER_NAME.match(name)
    return (
        found is not None
        and not any(ch.isdigit() for ch in found.group(1))
        and _PUBLIC_PAYER_NAME_VETO.search(name) is None
    )


def public_region(text: str) -> str:
    """§5.2: the region a government payer is read on: the payee region of the row before its receiver fields, with
    the template prefixes removed, before the digit cut, so 'TREAS 310' keeps its digits. On an incoming wire it is
    the originator."""
    if _is_wire_row(text):
        return _wire_originator_text(text)
    return _payee_region(_strip_revenue_template(_before_receiver(text))).strip()


def government_benefit(text: str) -> bool:
    """§8.1 personal_income, §20 (GOV, class B): a government's personal-benefit form names the row: a benefit
    descriptor as the whole payer of the row before its receiver fields (_GOVERNMENT_BENEFIT_PAYER, read on
    classifier.government_form_payer), or a benefit entry (_GOVERNMENT_BENEFIT_ENTRY) that no company form follows
    before the row's next field, the IRS's TAX EIP on an IRS Treasury row only."""
    row = _before_receiver(text)
    if _GOVERNMENT_BENEFIT_PAYER.fullmatch(government_form_payer(row)) is not None:
        return True
    for found in _GOVERNMENT_BENEFIT_ENTRY.finditer(row):
        if found.group("eip") and IRS_TREASURY_FORM.search(row) is None:
            continue
        rest = row[found.end():]
        label = _ENTRY_FIELD_LABEL.search(rest)
        if _ENTRY_COMPANY_FORM.search(rest[: label.start()] if label is not None else rest) is None:
            return True
    return False


def _personal_income(text: str, row: str, bank: str | None = None) -> bool:
    """§8.1 personal_income: a benefit or pension word on `row` (_PERSONAL_INCOME), or (GOV) a government's
    personal-benefit form on the credit's text (government_benefit). RETIRE... inside the payer's own name is read as
    no benefit word (_spare_retire_name; `bank` is the statement's, which TD Canada Trust's cut reads: with none, as
    Q7's refusal reads it, the cut never spares a word)."""
    row = _spare_retire_name(text, row, bank)
    return _PERSONAL_INCOME.search(row) is not None or government_benefit(text)


def _spare_retire_name(text: str, row: str, bank: str | None = None) -> str:
    """`row` without the RETIRE... words the payer region (classifier.payer_region) prints as its own name: before an
    operator's word (_RETIRE_OPERATOR_NAME), or, on TD Canada Trust's row that ends with an electronic-payment CPA
    code (cpa_payment_code, read on the row before its receiver fields and before the holder's name is stripped), as
    the last word of the payer field TD cut to exactly _TD_PAYER_WIDTH characters (_RETIRE_CUT_WORD). Every other
    word, and a region the row no longer prints as read, is left as printed (the hold stays)."""
    region = payer_region(text)
    if not region:
        return row
    named = _RETIRE_OPERATOR_NAME.sub("", region)
    printed = _before_receiver(text).strip()
    if cpa_payment_code(printed, bank):
        payer = printed.rsplit(" ", 1)[0]
        last = payer.rsplit(" ", 1)[-1]
        if len(payer) == _TD_PAYER_WIDTH and _RETIRE_CUT_WORD.fullmatch(last):
            words = named.split()
            if len(words) >= 2 and _CPA_PAYMENT_CODE.search(" " + words[-1]) and words[-2] == last:
                del words[-2]
            elif words and words[-1] == last:
                del words[-1]
            named = " ".join(words)
    return row.replace(region, named) if named != region else row


def government_grant(text: str) -> bool:
    """§8.1 non_sale_purpose, §20 (GOV, class D): a government grant or subsidy names the row: a grant form on the
    row before its receiver fields (_GOVERNMENT_GRANT), or the CRA's wage subsidy as the whole payer
    (_WAGE_SUBSIDY_PAYER)."""
    row = _hold_text(text)
    return _GOVERNMENT_GRANT.search(row) is not None or _WAGE_SUBSIDY_PAYER.fullmatch(
        government_form_payer(_before_receiver(text))
    ) is not None
