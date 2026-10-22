"""Government, tax-refund and card-reward forms; the non-revenue credit patterns."""
from __future__ import annotations

import re

from analysis.classification_registry import CARD_ISSUER_CONTEXT_ALIASES
from analysis.descriptor.lexical import _before_receiver, _is_reference_token, _strip_revenue_template, revenue_text
from analysis.descriptor.payer import entry_fields
from analysis.descriptor.rails import _without_receiver_value
from analysis.descriptor.words import (
    IRS_TREASURY_FORM,
    _AMEX_ACH_CREDIT,
    _FRENCH_INTEREST_CREDIT,
    _INTERNAL_TRANSFER_CREDIT_PATTERNS,
    _OWN_ACCOUNT_SWEEP_CREDIT_PATTERNS,
)
from analysis.payee_matcher import registry_match


#: The posting words a bank prints before the Canada Revenue Agency's refund, read after the revenue text and the
#: template prefixes are stripped: a glued or spaced date, Canada's GC (Government of Canada) and the direct-deposit,
#: EFT and payment words ('0102DIRECT DEPOSIT CANADA RIT', 'GC DIRECT DEPOSIT CANADA RIT', 'PAYMENT FROM CANADA RIT').
#: Each number ends at a space or a letter, so no number splits two ways.
_CRA_POSTING_PREFIX = re.compile(
    r"^(?:\d+(?: |(?=[A-Z])))*(?:(?:GC|DIRECT DEPOSIT|DIRECT DEP|DEPOSIT|DEP|ELECTRONIC DEPOSIT"
    r"|EFT(?: CREDIT| DEPOSIT)?|MISC PAYMENT|PAY(?:MENT)?(?: FROM)?) (?:\d+(?: |(?=[A-Z])))*)*"
)
_CRA_REFUND_PAYER = re.compile(r"CANADA (?:RIT|RIF)\b")
#: A business's GST/HST refund, the Canada Revenue Agency's ('CANADA GST TPS', 'GST CANADA') and Revenu Quebec's ('RQ
#: GST'). The form is the whole payer after the posting words, with only a posting code or a reference after it ('...
#: MSP DIV', '... 12345678'), so GST inside a name ('GST CANADA LOGISTICS INC', 'NORTHWIND GST SERVICES') is never a
#: refund. The CRA's name after the form ('CANADA GST TPS CANADA'), a country code ('GST CANADA CA') and the GST
#: program account ('... RT0001') too.
_GST_REFUND_PAYER = re.compile(
    r"(?:CANADA GST(?: TPS)?(?: CANADA)?|GST(?: TPS)? CANADA(?: CA)?|RQ GST)(?: (?:MSP|DIV|RT\d{4}|\d+))*"
)


def government_form_payer(text: str) -> str:
    """The payer a government's form is read on as the whole payer: the revenue text with the bank's template prefixes
    (_strip_revenue_template) and the posting words a bank prints before a government's form (_CRA_POSTING_PREFIX: a
    glued or spaced date, GC, DIRECT DEPOSIT, EFT, MISC PAYMENT, PAYMENT FROM ...) removed."""
    return _CRA_POSTING_PREFIX.sub("", _strip_revenue_template(revenue_text(text)), count=1).strip()


def _canada_tax_refund(text: str) -> bool:
    """The refund's form starts the payer, after the posting words only; a payer that names Canada's form after
    its own name is that payer ('FABRIKAM LIFE CANADA RIF PMT'). GOV: or the GST/HST refund form is the whole
    payer (_GST_REFUND_PAYER)."""
    payer = government_form_payer(text)
    return _CRA_REFUND_PAYER.match(payer) is not None or _GST_REFUND_PAYER.fullmatch(payer) is not None


class _CanadaTaxRefundForm:
    """The refund reader in the strong non-revenue list, read as its patterns are (search)."""

    pattern = "CANADA (?:RIT|RIF) after the posting words, or the whole payer a GST/HST refund form"

    def search(self, text: str) -> "_CanadaTaxRefundForm | None":
        return self if _canada_tax_refund(text) else None


_IRS_BENEFIT_ENTRY = re.compile(r"(?<![A-Z])(?:CHI?LD ?CTC|TAX ?EIP ?\d?)\b")
#: And the IRS's interest entry, the interest it pays on a refund it paid late ('IRS TREAS 310 DES:INT'), interest and
#: no sale (§8.1, standard G5), never an IRS vendor payment's word.
_IRS_REFUND_WORDING = re.compile(r"(?<![A-Z])(?:TAX ?REF\w*|TAX ?EIC|[A-Z]*REFUNDS?|RFND|REFND|RFD|INT|INTEREST)\b")
_IRS_LAYOUT_WORDS = frozenset("ORIG CO NAME ID DESC DATE ENTRY DESCR SEC CCD CTX PPD WEB TRACE EED IND TRN DES".split())


def _irs_tax_refund(text: str) -> bool:
    """A credit the IRS issues through the Treasury is a tax refund when its entry is a refund's wording or it prints
    no entry at all ('ELECTRONIC DEPOSIT FROM IRS TREAS 310', 'ACH CREDIT IRS TREAS 310 <reference>'). Treasury's
    Green Book gives MISC PAY to federal vendor payments, and the IRS pays its contractors that way, so an entry such
    as MISC PAY, VENDOR or VENDOR PAY keeps the row's own reading. The entry is the DES or CO ENTRY DESCR field
    (entry_fields), or on a layout with no field the words printed after the form, references and field labels left
    out. An interest entry (INT, INTEREST), the interest on a refund, is no revenue either."""
    row = _before_receiver(text)
    found = IRS_TREASURY_FORM.search(row)
    if found is None or _IRS_BENEFIT_ENTRY.search(text):
        return False
    entry = entry_fields(text) or " ".join(
        word for word in row[found.end():].split() if not _is_reference_token(word) and word not in _IRS_LAYOUT_WORDS
    )
    return not entry.strip() or _IRS_REFUND_WORDING.search(entry) is not None


class _IrsTaxRefundForm:
    """The IRS refund reader in the strong non-revenue list, read as its patterns are (search)."""

    pattern = "IRS TREAS nnn with no entry or a refund- or interest-worded entry"

    def search(self, text: str) -> "_IrsTaxRefundForm | None":
        return self if _irs_tax_refund(text) else None


#: Spec §6.1 step 3a: the seven government payments the owner excluded when the row prints no purpose, each named by its
#: key (the step's matched_alias), in the order the reader tests them. The VA's Treasury form is read with agency code
#: 36 only (a blank, 12, USDA, VACP, DOD or SSA code and the letter form VA are other agencies' or unruled); WORK COMP
#: BOARD without WSIB is another board. The six letter-led forms take the left boundary (?<![A-Z]), so a digit run glued
#: before a form's first letter ('0102GOUV QUEBEC MSP', a glued date) is a reference the rest-of-row test reads
#: (_is_reference_token), as _CRA_POSTING_PREFIX reads a glued lead for the GST form; the VA's form keeps (?<![A-Z0-9])
#: (a digit glued before its agency code makes the code unreadable).
GOVERNMENT_NO_PURPOSE_FORMS = (
    ("mn_mmb", re.compile(r"(?<![A-Z])MN STATE MMB\b")),
    ("va_treasury", re.compile(r"(?<![A-Z0-9])36 TREAS ?\d{3}\b")),
    ("wi_dcf", re.compile(r"(?<![A-Z])WI ?DCF\b")),
    ("bc_provincial", re.compile(r"(?<![A-Z])(?:PROVINCIAL PAYMENT )?PROVINCE OF (?:BC|BRITISH COLUMBIA)\b")),
    ("ontario_wsib", re.compile(r"(?<![A-Z])(?:(?:WORK COMP BOARD )?WSIB|WORKPLACE SAFETY AND INSURANCE BOARD)\b")),
    ("quebec_government", re.compile(r"(?<![A-Z])GOUV(?:ERNEMENT)?(?: DU)? QUEBEC\b")),
    ("nd_workforce_safety", re.compile(
        r"(?<![A-Z])(?:ND |NORTH DAKOTA )?WORKFORCE SAFETY(?: AND INS(?:URANCE)?| INS(?:URANCE)?)?\b")),
)
#: Q12: the ACH field labels read past (Chase's and Bank of America's), and the only words a no-purpose row may print
#: besides its form and its references: posting words, SEC codes, the X12 envelope's segment names and the no-purpose
#: entries (MISC PAY, PAYMENT, PMT, DD, WIDCF, EME, MSP, DIV). Keep the set to these: a name, funding or purpose word
#: here would let step 3a pre-empt a lender's D1 reading or swallow a purpose.
_GOVERNMENT_NO_PURPOSE_LAYOUT = re.compile(r"\b(?:ORIG CO NAME|ORIG ID|DESC DATE|CO ENTRY DESCR|CO ID|IND ID|IND NAME)\b")
_GOVERNMENT_NO_PURPOSE_WORDS = frozenset(
    "ELECTRONIC DEPOSIT FROM DESCRIPTIVE ACH CREDIT DIRECT DEP EFT GC PREAUTHORIZED MISC PAY PAYMENT PAYMENTS PMT DD "
    "WIDCF EME MSP DIV DES ID SEC CCD CTX PPD WEB TRACE EED TRN ISA IEA GS GE ST SE".split()
)
#: Q12: a masked prefix followed by letters is an entry, not a reference: the VA's XXVA CH33, CH31, BENEF and EDU
#: print a purpose. A mask with digits (XXXXX1234) and an all-X mask (XXXXXX) stay references.
_GOVERNMENT_NO_PURPOSE_MASKED_ENTRY = re.compile(r"X{2,}[A-WYZ][A-Z]*")


def government_no_purpose(text: str) -> str | None:
    """Spec §6.1 step 3a: the key of the government form a credit prints when the row prints no purpose
    (GOVERNMENT_NO_PURPOSE_FORMS), else None. `text` is the revenue text.

    The row is read with each receiver field's value removed and every field after it kept (_without_receiver_value),
    so Bank of America's PMT INFO addenda, printed after INDN ... CO ID ... CCD, stays in the row and an invoice there is
    a purpose. American Express's incoming-ACH template (_AMEX_ACH_CREDIT) is read from its originator up to its id, as
    _before_receiver ends it, never its EXTERNAL, sending-bank and trace trailer; its label is the template's own words
    whatever the originator's first word. The template prefixes and the ACH field labels are read past. Besides the
    form, the row may print only _GOVERNMENT_NO_PURPOSE_WORDS and references (_is_reference_token: a digit, a mask, a
    month; a masked prefix followed by letters is an entry word). The first form found decides: any other word leaves
    the row to the later steps, with no fall-through to another form."""
    amex = _AMEX_ACH_CREDIT.match(text)
    base = text[amex.start("payer"): amex.end("id")] if amex is not None else _without_receiver_value(text)
    row = _GOVERNMENT_NO_PURPOSE_LAYOUT.sub(" ", _strip_revenue_template(base))
    for name, form in GOVERNMENT_NO_PURPOSE_FORMS:
        found = form.search(row)
        if found is None:
            continue
        rest = (row[: found.start()] + " " + row[found.end():]).split()
        no_purpose = all(
            word in _GOVERNMENT_NO_PURPOSE_WORDS
            or (_is_reference_token(word) and _GOVERNMENT_NO_PURPOSE_MASKED_ENTRY.fullmatch(word) is None)
            for word in rest
        )
        return name if no_purpose else None
    return None


#: American Express's Membership Rewards redemption, read only beside a card issuer's name (American Express, Amex, or
#: a card issuer's context alias), so a payer whose entry happens to print MR REDEEM keeps its reading.
_CARD_REWARD_PROGRAM = re.compile(r"\b(?:MR REDEEM|MEMBERSHIP REWARDS?)\b")
_CARD_ISSUER_NAME = re.compile(r"(?<![A-Z])(?:AMERICAN EXPRESS|AMEX)\b")


class _CardIssuerRewardRedemption:
    """A card issuer's rewards redemption in the strong non-revenue list, read as its patterns are (search)."""

    pattern = "MR REDEEM or MEMBERSHIP REWARDS beside a card issuer's name"

    def search(self, text: str) -> "_CardIssuerRewardRedemption | None":
        if _CARD_REWARD_PROGRAM.search(text) is None:
            return None
        if _CARD_ISSUER_NAME.search(text) or registry_match(text, CARD_ISSUER_CONTEXT_ALIASES) is not None:
            return self
        return None


_NON_REVENUE_CREDIT_PATTERNS = (
    re.compile(
        r"\b(?:LOAN|BUSINESS LOAN|MCA|MERCHANT CASH ADVANCE|FINANCING) "
        r"(?:FUNDING|PROCEEDS|DISBURSEMENT|ADVANCE)\b"
    ),
    re.compile(r"\b(?:BUSINESS |COMMERCIAL )?LOANS?\b"),
    re.compile(r"\b(?:MCA|MERCHANT CASH ADVANCES?)\b"),
    re.compile(r"\bCASH ADVANCE\b"),
    re.compile(r"\b(?:LOAN|MCA) ORIGINATION CREDIT\b"),
    *_INTERNAL_TRANSFER_CREDIT_PATTERNS,
    *_OWN_ACCOUNT_SWEEP_CREDIT_PATTERNS,
    re.compile(r"\bOWNER(?:S)? (?:CONTRIBUTION|CAPITAL|DEPOSIT|TRANSFER)\b"),
    re.compile(r"\bSHAREHOLDER (?:CONTRIBUTION|LOAN|DEPOSIT)\b"),
    re.compile(r"\bCAPITAL CONTRIBUTION\b"),
    re.compile(r"\bINSURANCE (?:PROCEEDS|CLAIM|PAYMENT)\b"),
    re.compile(r"\bTAX REFUND\b"),
    # §7.11: the tax-refund abbreviations (Treasury's TAX REF) and account-verification micro-deposits.
    re.compile(r"\bTAX ?REF(?:UND)?S?\b|[A-Z]*TAXRFD\b|\bTAX RFD\b|\bTAXEIC\b"),
    # The Canada Revenue Agency's income-tax refund direct deposit (RIT and RIF are the banks' two labels of one refund,
    # 'DIRECT DEPOSIT CANADA RIT RIF'). The form starts the payer (_CanadaTaxRefundForm). GOV: and a business's GST/HST
    # refund is the whole payer; the CRA's benefit forms are personal income, held by the true-revenue pass (class B),
    # never non_revenue.
    _CanadaTaxRefundForm(),
    # GOV: a payment the IRS issues through the Treasury ('IRS TREAS 310') with no entry or a refund-worded one is a
    # tax refund; an IRS vendor payment (MISC PAY, VENDOR PAY) keeps its reading, and the child tax credit and the
    # stimulus are personal benefits (class B) (_IrsTaxRefundForm).
    _IrsTaxRefundForm(),
    re.compile(r"\bACCT ?VERIFY\w*\b|\bMICRO ?DEPOSITS?\b|\bPENNY TEST\b|\bTRIAL DEPOSITS?\b"),
    re.compile(r"\b(?:IRS|CRA|REVENUE AGENCY) REFUND\b"),
    re.compile(
        r"\b(?:CASH ?BACK|CASH ?REWARDS?|CARD REWARDS?|CREDIT CARD REWARDS?)"
        r"(?: CREDIT|REDEMPTION|REBATE)?\b"
    ),
    # Card-rewards redemptions the patterns above miss, each anchored so a payer named REDEMPTION ... is never read:
    # Chase's payer-less CASH REDEMPTION as the whole row (a reference after it), PNC's PURCHASE PAYBACK [AWARD], a
    # POINTS REDEMPTION, and a card issuer's MR REDEEM or MEMBERSHIP REWARDS.
    re.compile(r"^(?:\d{1,2} \d{1,2} )?CASH REDEMPTION(?: \S*\d\S*)*$"),
    re.compile(r"\bPURCHASE PAYBACK(?: AWARD)?\b"),
    re.compile(r"\bPOINTS REDEMPTION\b"),
    _CardIssuerRewardRedemption(),
    re.compile(r"\bINTEREST (?:CREDIT(?:ED)?|PAID|PAYMENT|DEPOSIT|EARNED)\b"),
    re.compile(r"\bCREDIT INTEREST\b"),
    # The French interest credit (_FRENCH_INTEREST_CREDIT).
    _FRENCH_INTEREST_CREDIT,
    re.compile(r"\b(?:BANK |SERVICE |ACCOUNT )?FEES? (?:REFUND|REBATE|REVERSAL|CREDIT)\b"),
    # The French fee rebate (RABAIS SUR LES FRAIS MENSUELS), as FEE REBATE reads. Copied in tools/revenue_census.py.
    re.compile(r"(?<![A-Z])RABAIS (?:SUR )?(?:LES )?FRAIS\b"),
    re.compile(r"\bDAILY CAP OF \d+ FEES?\b"),
    re.compile(r"\bINVEST(?:MENT)? TRANSFER\b"),
    re.compile(r"\b(?:ASSET|VEHICLE|EQUIPMENT|PROPERTY) SALE (?:PROCEEDS|DEPOSIT)\b"),
    re.compile(r"\bPROCEEDS FROM (?:ASSET|VEHICLE|EQUIPMENT|PROPERTY) SALE\b"),
)
