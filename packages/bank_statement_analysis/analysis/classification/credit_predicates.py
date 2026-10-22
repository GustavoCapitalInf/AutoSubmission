"""Credit predicates both engines read: reversal, card release, designation, remittance, wire vetoes."""
from __future__ import annotations

import re

from analysis.classification.operating_sources import _operating_source
from analysis.classification.tax_forms import _NON_REVENUE_CREDIT_PATTERNS
from analysis.classification_registry import PAYEE_GROUP_REGISTRIES, POTENTIAL_LENDER_ALIASES
from analysis.description_text import normalize_transaction_description
from analysis.descriptor.credit_words import (
    _BILL_COM,
    _BOOK_OR_FUNDS_TRANSFER,
    _CARD_CREDIT_PUSH_WORD,
    _CARD_REFUND_LABELS,
    _EFT_FUNDS_TRANSFER,
    _INVOICE_NUMBER,
    _PAYER_REMITTANCE_CREDIT_PATTERNS,
    _PAYMENT_CHANNEL_WORD,
    _PROCESSOR_CONTEXT_TYPES,
    _PUBLIC_PAYER_NAME,
    _PUBLIC_PAYER_NAME_VETO,
    _PUBLIC_PAYER_NON_SALE_WORDS,
    _PUBLIC_PAYER_TEMPLATE,
    _REMBOURSEMENT_WORD,
    _RETURN_CODE_CREDIT_PATTERNS,
    _RETURN_REFUND_CREDIT_PATTERNS,
    _TREASURY_BOILERPLATE,
)
from analysis.descriptor.financing import _names_financing
from analysis.descriptor.holder import account_name_text, holder_named
from analysis.descriptor.lexical import (
    _before_receiver,
    _distinctive_words,
    _first_distinctive_word,
    _joined_text,
    _leading_name_words,
    _originator_payer_words,
    _payee_region,
    company_form,
    payer_name,
)
from analysis.descriptor.payer import numbered_company
from analysis.descriptor.rails import (
    _bare_incoming_wire,
    _is_wire_row,
    _matches_any,
    _public_payer_arm_a,
    _third_party_originator,
    _wire_vetoes_apply,
)
from analysis.descriptor.words import (
    THIRD_PARTY_BOOK_TRANSFER_AS_WIRE,
    _CHANNEL_TRANSFER_FROM_ACCOUNT,
    _REVERSAL_CANCELLATION_CREDIT_PATTERNS,
    _SANTANDER_WIRE,
    _TFR_TRANSFER_DEPOSIT,
    _TRANSFER_FROM_ACCOUNT,
    _WIRE_ORIGINATOR_LABEL,
)
from analysis.flag_groups import FINANCING_STATES
from analysis.payee_matcher import match_known_payee


#: §6.3: the two layouts that print a named sender after an own-account designation, and the sender's words: Bank of
#: America's 'ONLINE|MOBILE [BANKING] TRANSFER FROM CHK|SAV <n> CONFIRMATION <reference> <sender>' (its own-account
#: form prints only the reference, ten digits) and a credit union's 'TFR FROM X...<n> TRANSFER DEPOSIT <sender>'.
#: Navy Federal's 'TRANSFER FROM SHARES|CHECKING <name>' is neither: its holder test is blind, so it stays the
#: holder's own transfer.
_NAMED_DESIGNATION_TRANSFERS = (
    re.compile(r"\b(?:ONLINE|MOBILE) (?:BANKING )?TRANSFER FROM (?:CHK|SAV) \d+ CONFIRMATION \S+ (?P<sender>\S.*)$"),
    re.compile(r"\bTFR FROM X+\d* TRANSFER DEPOSIT (?P<sender>\S.*)$"),
)
#: The own-account patterns a named sender after the designation refuses.
_NAMED_DESIGNATION_PATTERNS = (_TRANSFER_FROM_ACCOUNT, _CHANNEL_TRANSFER_FROM_ACCOUNT, _TFR_TRANSFER_DEPOSIT)
#: §7.11: a claim or provider signal. REIMBURSEMENT on such a row is a provider's claim payment, not a refund.
_CLAIM_OR_PROVIDER_SIGNAL = re.compile(
    r"\b(?:MEDICAID|MEDICARE|MEDI CAL|TRICARE|CHAMPVA|GEMT|EMS|PROV(?:IDER)? ?PAY(?:MENTS?)?|EDI PYMNTS|CLAIM PMT)\b"
    r"|(?:\bH[CE]?|HC)CLAIMPMT(?:SEC)?\b"
)
_REIMBURSEMENT_WORD = re.compile(r"\bREIMBURSEMENT\b")
#: §7.11: the Quebec health insurance board (the Régie de l'assurance maladie du Québec, a public body that pays health
#: professionals and clinics for the insured services they bill; ramq.gouv.qc.ca), the French rows' provider signal:
#: REMBOURSEMENT on such a row is the clinic's claim payment, as REIMBURSEMENT is beside a claim or provider signal
#: (_CLAIM_OR_PROVIDER_SIGNAL).
_QUEBEC_HEALTH_PAYER = re.compile(r"(?<![A-Z])(?:RAMQ|REGIE (?:DE L )?ASSURANCE MALADIE(?: DU QUEBEC)?)\b")
#: §7.11: push payouts printed as card credits: a push-rail word, or a processor or invoice source with a payout word.
#: The card-credit labels include Citibank's cut DEBIT CARD CREDI and the card-shaped refund labels step 3 adds
#: (_CARD_REFUND_LABELS).
_CARD_CREDIT_LABEL = re.compile(
    r"\b(?:DEBIT CARD CREDIT?|POS CREDIT)\b|^(?:\d{1,2} \d{1,2} )?CHECKCARD \d{4}\b|\bPOINT OF SALE DEPOSIT\b"
)
#: §7.11: Cash App and Apple Cash pushes printed as a DEBIT CARD CREDIT or POS CREDIT join the push words (released from
#: the reversal rule, then held by §8.1 as any released card credit is) only with CASH_APP_CARD_PUSH_RELEASE on. It
#: stays off by the owner's card-push ruling; switched on, it would only hold a few rows and move no True. A card
#: credit printed first ('CARD CREDIT CASH APP ...') stays a counted person-to-person push either way
#: (true_revenue._leading_card_credit).
CASH_APP_CARD_PUSH_RELEASE = False
_CARD_CREDIT_P2P_PUSH_WORD = re.compile(r"(?<![A-Z])(?:CASH ?APP|APPLE CASH)\b")
_CARD_CREDIT_PAYOUT_WORD = re.compile(r"\b(?:PAYOUTS?|INSTANT (?:PAYOUT|PAY|TRANSFER)|SETTLEMENT|DEPOSIT)\b")
#: §7.7: inside the credit decision, the financing, potential-lender and insurer lookups read a glued HCCLAIMPMT
#: split from the name before it, so a sixteen-character funder name glued to the token is still found.
_GLUED_CLAIM_ENTRY = re.compile(r"(?<=[A-Z0-9])(H[CE]?CLAIMPMT)")
#: §7.5: the free-text forms (invoice, bill and 'for invoices') count on a PAYPAL row or a wire from a person only
#: when the sender prints a company form.
_FREE_TEXT_REMITTANCE = re.compile(
    r"\bPAYING BILLS?\b|\bFOR \d+ BILLS\b|\b(?:OF|FOR) INVOI ?CES?\b|\bINV(?:OICE)?S?(?: (?:NO|NUM|NUMBER|N))? ?\d"
)
#: §7.5: the credit posting labels removed before the veto reads the row.
_CREDIT_POSTING_LABELS = re.compile(
    r"\b(?:ELECTRONIC|ACH|RTP|ONLINE|WIRE|BOOK|CORP|CORPORATE|ZELLE|MISC|DIRECT|PAYMENT|DEPOSIT|TRANSFER|MOBILE|EFT"
    r"|CHIPS|FEDWIRE)\s+CREDIT\b|^CREDIT\b"
)
#: §7.5: the veto of the payer remittance rule.
_PAYER_REMITTANCE_VETO = re.compile(
    r"(?:FUND|CAPIT|CAPTL|LOAN|LEND|FINANC|ADVANC|MORTG|ACCEPTANCE|SERVICING|SERVICER|PORTFOL|CREDIT)"
    r"|CRED(?=ORA|IBLY|\b)|CAPI?\b|LEAS(?:E|ES|ING|IN|I)?\b"
    r"|(?<![A-Z])(?:FINA|FINAN|FINL|FNCL|FUNDI)\b|\b(?:CAP|FIN|FI|ADV|MTG|MCA|RTR|SPV|FUN|LOA)\b"
    r"|(?<![A-Z])(?:INSUR\w*|ASSURANCE|INVEST\w*|BROKERAGE|SECURITIES|WEALT\w*|TAXES|GRANTS?|REBATES?|DIVIDENDS?)\b"
    r"|\b(?:INS|TAX|IRS|CRA)\b"
    r"|(?<![A-Z])(?:PAYROLL|SALARY|WAGES?|REIMB\w*|EXPENSES?|BONUS|COMM?ISS?IONS?|CLAIMS?|MUTUAL|INDEMNITY|CASUALTY"
    r"|UNDERWRIT\w*)\b"
    r"|(?<![A-Z])(?:EQUIP\w*|FLOOR\w*|MERCH\w*)\b|\bVIN\b"
    r"|\bSBA\b|(?<![A-Z])(?:SBAD|EIDL)\b"
    r"|(?<![A-Z])(?:INTERCO(?:MPANY)?|DUE FROM|SHAREHOLDER|OWNERS?|SWEEP|INTERNAL)\b|(?<![A-Z])ZERO BAL\w*|\bZBA\b"
    r"|(?<![A-Z])CONTROLLED DISB\w*|(?<![A-Z])(?:TRANSFER|XFER|TFR) FROM\b"
    r"|\bRTN\b|(?<![A-Z])RETURN(?:ED)? ITEM\b|(?<![A-Z])RECALL\w*|(?<![A-Z])UNPAID\b|\bADJ\b"
    r"|ACIMA"
)
_PUBLIC_PAYER_PURPOSE = re.compile(
    r"\bVEN(?:DOR)? ?(?:PAY(?:MENTS?)?|P(?:Y)?MTS?)(?:SEC)?\b|\bPROV(?:IDER)? ?PAY(?:MENTS?)?(?:SEC)?\b"
    r"|\bEDI ?(?:PYMNTS|PAYMENTS?|PMTS?)(?:SEC)?\b"
)
_PUBLIC_PAYER_OTHER_VETO = re.compile(
    r"(?<![A-Z])(?:ZELLE|VENMO|CASH ?APP|E ?TRANSFER|INTERAC)\b"
    r"|(?<![A-Z])(?:FUNDING|FUNDER|LENDING|LENDER|FINANC\w*|CAPITAL|CREDIT UNION|MORTGAGE|LEASE|LEASING|FACTOR\w*)\b"
    r"|\bFCU\b|(?<![A-Z])SETTLEMENT\b"
)
_PUBLIC_PAYER_ARM_B_TRANSFER = re.compile(r"(?<![A-Z])(?:TRANSFER|XFER)\b|\bTFR\b")

_WIRE_PARTY_FIELDS = re.compile(
    r"\bB O\b.*?(?=\b(?:REF|OBI|RFB|BNF|IMAD|TRN)\b|$)|\bN?BNF\b.*?(?=\b(?:REF|OBI|RFB|IMAD|TRN|ORIG)\b|$)"
    r"|\bORIG\b(?! TO BNF).*?(?=\b(?:REF|OBI|RFB|BNF|IMAD|TRN|SND BK|PMT DET)\b|$)|\bACCT \d+\b"
    r"|\bORIGINATOR NAME\b.*?(?=\b(?:REF|OBI|RFB|BNF|IMAD|TRN)\b|$)|\bORG\b.*?(?=\b(?:REF|OBI|RFB|BNF|IMAD|TRN)\b|$)"
)
_WIRE_NON_SALE_PURPOSE = re.compile(
    r"(?<![A-Z])(?:INVEST\w*|DISTRIBUTION|DIVIDEND|EQUITY|MEMBERSHIP INTEREST|SHAREHOLDER|STOCK|CONTRIBUTION|PROCEEDS"
    r"|ESCROW|CLOSING|OVER PAYMENT|REBATE|RETURN(?:ED)?|CREDIT MEMO|DUPLICATE|SALARY|PAYROLL|WAGES|GRANT|DONATION|GIFT"
    r"|INTEREST|REPAY\w*|PRINCIPAL|SECURITY DEPOSIT|INTER ?COMPANY|INTERCO|AFFILIATE|OWNERS?|PERSONAL|COURT|JUDGMENT"
    r"|INSURANCE|CLAIMS?|RETN|REJT|REJECT(?:ED)?|RECALL(?:ED)?|UNABLE TO APPLY|DRAWS?|DRAWDOWNS?|DISBURS\w*"
    r"|SUPPLY CHAIN|EARLY PAY(?:MENT)?|DISCOUNT(?:ED|ING)?|PAYOFF|SURPLUS|EARNEST|SUBSCRIPTIONS?|COMPENSATION"
    r"|ADJUSTMENTS?|SHORTAGES?|ALLOWANCES?|PROMISSORY|CONVERTIBLE|BRIDGE|SAFE|TRANCHE|DEPOSIT BACK|FEES)\b"
    r"|\b(?:TAX|RTN|FEE|SCF|ADJ|RMA)\b"
)
#: §7.9: the channel and bank fields removed before the financing roots are read on a wire. And U.S. Bank's 'WIRE
#: CREDIT REF<n>' and the '<INCOMING|DOMESTIC|INTL|INTERNATIONAL|FOREIGN> WIRE CREDIT' labels, whose CREDIT is the
#: channel's word, never a lender's name (removed from the veto's text only: the row keeps its label and reads as a
#: wire). And R21 part C's plural label ('WIRE TRANSFERS CREDIT <sender>'), whose CREDIT is the channel's word as the
#: singular's is, now that the sender after it is read.
_WIRE_CHANNEL_AND_BANK_FIELDS = re.compile(
    r"^(?:WIRE CREDIT REF ?\d+|(?:INCOMING|DOMESTIC|INTL|INTERNATIONAL|FOREIGN) WIRE CREDIT)\b|"
    r"^(?:WIRE TYPE \S+ IN|USD WIRE IN|[A-Z]{3} WIRE IN|FEDWIRE CREDIT|CHIPS CREDIT|WT FED|WIRE TSF"
    r"|WIRE TRANSFER \S+|WIRE TRANSFERS (?:DEPOSIT|CREDIT|IN|INCOMING|FROM)"
    r"|INCOMING WIRE|WIRE IN|WIRE FROM|(?:DOMESTIC|INTL|INTERNATIONAL|FOREIGN)(?: INCOMING)? WIRE"
    r"|INCOMING FUNDS TRANSFER|FUNDS TRANSFER CREDIT TT|INBD FUNDS TRANSFER|FUNDS TRANSFER WIRE FROM"
    r"|BOOK TRANSFER CREDIT)\b"
    r"|\b(?:SND BK|BBI|VIA|INTERMEDIARY|INT BK|OGB)\b.*?(?=\b(?:B O|ORIG|ORG|REF|OBI|BNF|TRN|IMAD|PMT DET|RFB|RMR|ID)\b|$)"
)
#: §7.9, §8.5: a wire from a title or escrow firm carries sale, closing or escrow money, never a sale of the business.
_TITLE_OR_ESCROW_ORIGINATOR = re.compile(r"(?<![A-Z])(?:TITLE|ESCROW)\b")
#: §7.9: a cut originator field: the field widths of Santander (16) and Bank of America (25).
_WIRE_ORIGINATOR_FIELD_WIDTHS = (16, 25)
_FINANCING_FULL_WORDS = (
    "FUNDING", "FINANCIAL", "CAPITAL", "LENDING", "LOANS", "ADVANCE", "MERCHANT", "CREDIT", "LEASING", "SERVICING",
    "FACTORING", "MORTGAGE", "RECEIVABLES", "EQUIPMENT", "ACCEPTANCE", "COLLECTIONS", "RECOVERY", "SETTLEMENT",
    "REMITTANCE", "EQUITIES", "EQUITY", "VENTURES",
)

#: §7.9: the financing and potential aliases, run together, for the cut-originator test.
_FINANCING_RUN_TOGETHER_ALIASES = frozenset(
    normalize_transaction_description(alias).replace(" ", "")
    for state, registry in (*PAYEE_GROUP_REGISTRIES.items(), ("potential_lender", POTENTIAL_LENDER_ALIASES))
    if state in FINANCING_STATES or state == "potential_lender"
    for aliases in registry.values()
    for alias in aliases
)
_WIRE_INVOICE_SPLITS = tuple(
    dict.fromkeys(word[:cut] + " " + word[cut:] for word in ("INVOICE", "INVOICES") for cut in range(1, len(word)))
)
_WIRE_SALE_PURPOSE = re.compile(
    r"\b(?:INVOICES?|" + "|".join(_WIRE_INVOICE_SPLITS) + r")\b"
    r"|\bINV(?:OICE)?S? ?(?:NO |NUM |NBR |NUMBER )?\d"
    r"|\bPO ?(?:NO |NUM |NBR |NUMBER )?\d{3,}|\bPURCHASE ORDERS?\b"
    r"|(?<!\bMONEY )(?<!\bSTANDING )(?<!\bPAYMENT )(?<!\bPMT )(?<!\bCOURT )(?<!\bPAY )(?<!\bTRANSFER )(?<!\bSUPPORT )"
    r"(?<!\bBANK )(?<!\bWIRE )\bORDERS? ?(?:NO\b|NUM\b|NBR\b|NUMBER\b|\d)"
    r"|\bPAYMENT FOR GOO(?:DS?)?\b|\bPAGO PROVEEDOR\b|\bFACTURA\b|\bREF INV\b|\bPRO ?FORMA\b|\bCOMPRA (?:DE )?MERCAD\w*"
)


def _reversal_credit(text: str) -> bool:
    """§6.1, §7.11: the reversal, cancellation, NSF and provisional-credit rule, with the return codes.
    REIMBURSEMENT never fires on a row that prints a claim or provider signal, and DEBIT CARD CREDIT and POS CREDIT
    never fire on a push payout printed as a card credit (_card_credit_released).

    And step 3's other return, correction and refund spellings (_RETURN_REFUND_CREDIT_PATTERNS): REMBOURSEMENT with
    REIMBURSEMENT's provider carve-out (_remboursement_from_a_provider), and the card-shaped refund labels
    (_CARD_REFUND_LABELS) released as a card credit is."""
    for pattern in (*_REVERSAL_CANCELLATION_CREDIT_PATTERNS, *_RETURN_REFUND_CREDIT_PATTERNS):
        found = pattern.search(text)
        if found is None:
            continue
        if pattern.pattern == _REIMBURSEMENT_WORD.pattern and _CLAIM_OR_PROVIDER_SIGNAL.search(text):
            continue
        if pattern is _REMBOURSEMENT_WORD and _remboursement_from_a_provider(text):
            continue
        if (
            _CARD_CREDIT_LABEL.fullmatch(found.group(0)) or any(pattern is label for label in _CARD_REFUND_LABELS)
        ) and _card_credit_released(text):
            continue
        return True
    return _matches_any(text, _RETURN_CODE_CREDIT_PATTERNS)


def _remboursement_from_a_provider(text: str) -> bool:
    """§7.11: French REMBOURSEMENT is a claim payment, not a refund, on a row that prints REIMBURSEMENT's claim or
    provider signal (_CLAIM_OR_PROVIDER_SIGNAL) or names the Quebec health insurance board (_QUEBEC_HEALTH_PAYER)."""
    return _CLAIM_OR_PROVIDER_SIGNAL.search(text) is not None or _QUEBEC_HEALTH_PAYER.search(text) is not None


def _card_credit_released(text: str) -> bool:
    """§7.11: a DEBIT CARD CREDIT or POS CREDIT row that prints a push-rail word, or names a merchant-processor or
    invoice source together with a payout word. Naming another source (a marketplace's card refund) is not enough.
    Such a row is never pooled for recurrence and verifies only by a form or single-row registry context."""
    if not _CARD_CREDIT_LABEL.search(text):
        return False
    if _CARD_CREDIT_PUSH_WORD.search(text):
        return True
    # Cash App and Apple Cash pushes, on the owner's switch.
    if CASH_APP_CARD_PUSH_RELEASE and _CARD_CREDIT_P2P_PUSH_WORD.search(text):
        return True
    source = _operating_source(text)
    return (
        source is not None
        and source.source_type in _PROCESSOR_CONTEXT_TYPES
        and _CARD_CREDIT_PAYOUT_WORD.search(text) is not None
    )


def _own_book_or_funds_transfer(text: str, account_name: str | None) -> bool:
    """§7.11: BOOK TRANSFER and FUNDS TRANSFER are own-account only when no third-party originator is printed, or when
    that originator is the holder (§5.2's holder test). ELECTRONIC FUNDS TRANSFER DEPOSIT is an EFT channel. Without the
    owner's yes to T19, every BOOK TRANSFER stays own-account. A row an incoming-wire label starts that prints only a
    reference (_bare_incoming_wire: 'FUNDS TRANSFER CREDIT TT <reference> O', 'INCOMING FUNDS TRANSFER <reference>') is
    an incoming wire with no sender, never own-account: pass 7 holds it as wire_no_sender."""
    found = _BOOK_OR_FUNDS_TRANSFER.search(text)
    if found is None or _EFT_FUNDS_TRANSFER.search(text):
        return False
    if found.group(0).startswith("BOOK") and not THIRD_PARTY_BOOK_TRANSFER_AS_WIRE:
        return True
    originator = _third_party_originator(text)
    if originator is None:
        return not _bare_incoming_wire(text)
    return holder_named(originator, account_name)


def named_designation_sender(text: str) -> str | None:
    """§6.3: the sender one of the two layouts prints after an own-account designation (_NAMED_DESIGNATION_TRANSFERS),
    up to its first reference token after a name word, when it prints a word that may name a payer
    (_originator_payer_words, as a book or funds transfer's originator is read); otherwise None."""
    row = _before_receiver(text)
    for pattern in _NAMED_DESIGNATION_TRANSFERS:
        found = pattern.search(row)
        if found is None:
            continue
        sender = _leading_name_words(found.group("sender"))
        if _originator_payer_words(sender):
            return sender
    return None


def _named_sender_after_designation(text: str, account_name: str | None) -> bool:
    """§6.3: the strong rule's own-account patterns read the whole row and never who sent the money. A named sender
    printed after the designation (named_designation_sender) that the holder test does not match (§5.2) refuses them,
    when no other non-revenue pattern reads the row: the credit then falls to the pass's T13 hold
    (transfer_account_designation), which an analyst may review. No sender, or the holder's own name, keeps the
    own-account reading."""
    if not _matches_any(text, _NAMED_DESIGNATION_PATTERNS):
        return False
    sender = named_designation_sender(text)
    if sender is None or holder_named(sender, account_name):
        return False
    return not any(
        pattern.search(text) is not None
        for pattern in _NON_REVENUE_CREDIT_PATTERNS if pattern not in _NAMED_DESIGNATION_PATTERNS
    )


def _split_glued_claim(text: str) -> str:
    """§7.7: the text the financing, potential-lender and insurer lookups read: a space before a glued
    HCCLAIMPMT, so a sixteen-character name glued to the token is still found."""
    return _GLUED_CLAIM_ENTRY.sub(r" \1", text)


def _refused_by_payer_guards(text: str, region: str, account_name: str | None) -> str | None:
    """§6.1: steps 11 (the customer and invoice descriptors) to 14 refuse a payer the holder test or the
    numbered-company guard matches. Returns 'holder' or 'numbered', or None."""
    if holder_named(region, account_name):
        return "holder"
    if numbered_company(text, region):
        return "numbered"
    return None


def _payer_remittance(text: str, region: str, account_name: str | None) -> bool:
    """§7.5: the payer's accounts-payable remittance: an AP pattern, or an invoice number on a row that also prints
    a payment-channel word; the free-text forms count on a PayPal row or a wire only with a company form; the veto
    reads the row with the matched words and the credit posting labels removed."""
    row = _before_receiver(text)
    joined = _joined_text(row)
    matched = None
    for pattern in _PAYER_REMITTANCE_CREDIT_PATTERNS:
        found = pattern.search(row) or pattern.search(joined)
        if found is not None and not (found.group(0) == "PAYABLES" and _BILL_COM.search(row)):
            matched = found.group(0)
            break
    if matched is None:
        found = _INVOICE_NUMBER.search(row)
        if found is not None and _PAYMENT_CHANNEL_WORD.search(row[: found.start()] + " " + row[found.end():]):
            matched = found.group(0)
    if matched is None:
        return False
    # A wire whose reference is glued to WIRE answers to the gate and the vetoes too.
    wire = _wire_vetoes_apply(text)
    if _FREE_TEXT_REMITTANCE.search(matched) and (re.search(r"\bPAYPAL\b", row) or wire):
        if not company_form(payer_name(region)):
            return False
    rest = _CREDIT_POSTING_LABELS.sub(" ", row.replace(matched, " "))
    if _PAYER_REMITTANCE_VETO.search(rest) is not None:
        return False
    if wire and _wire_vetoed(text, region, account_name):
        return False
    # A public payer's vendor payment also answers to §7.6's whole-row veto (a grant, a refund, a benefit, a
    # settlement, assistance), so a public payer never verifies here what §7.6 refuses.
    whole = _TREASURY_BOILERPLATE.sub(" ", text)
    public = _PUBLIC_PAYER_NAME.match(_PUBLIC_PAYER_TEMPLATE.sub("", region, count=1)) is not None
    return not (public and (_PUBLIC_PAYER_NON_SALE_WORDS.search(whole) or _PUBLIC_PAYER_OTHER_VETO.search(whole)))


def _public_payer_remittance(text: str) -> str | None:
    """§7.6: a public payer's remittance: arm A (Treasury vendor codes, whole row) or arm B (a public payer anchored
    on the payer name, with a payer-side purpose). Returns the matched rule, or None. Every veto is read on the row
    after Bank of America's Treasury boilerplate is deleted."""
    whole = _TREASURY_BOILERPLATE.sub(" ", text)
    row = _before_receiver(whole)
    if _PUBLIC_PAYER_NON_SALE_WORDS.search(whole) or _PUBLIC_PAYER_OTHER_VETO.search(whole):
        return None
    if _public_payer_arm_a(whole):
        return "treasury_vendor_payment"
    name = _PUBLIC_PAYER_TEMPLATE.sub("", _payee_region(row).strip(), count=1)
    found = _PUBLIC_PAYER_NAME.match(name)
    if found is None:
        return None
    lead = found.group(1)
    if any(ch.isdigit() for ch in lead) or _PUBLIC_PAYER_PURPOSE.search(name[: found.end()]):
        return None
    if _PUBLIC_PAYER_NAME_VETO.search(name) or _PUBLIC_PAYER_ARM_B_TRANSFER.search(whole):
        return None
    if not _PUBLIC_PAYER_PURPOSE.search(row):
        return None
    return "public_payer_vendor_or_provider_payment"


def _wire_financing_text(text: str) -> str:
    """§7.9: the wire row the financing roots are read on: the channel words and the sending, originating and
    intermediary bank fields removed (Santander prints its sending bank after WIRE IN FROM, Chase its originating
    bank after OGB)."""
    santander = _SANTANDER_WIRE.match(text)
    if santander is not None:
        text = text[: santander.start("bank")] + " " + text[santander.end("bank"):]
    return _WIRE_CHANNEL_AND_BANK_FIELDS.sub(" ", text)


def _wire_originator_run(text: str) -> str | None:
    """§7.9: the first six words of a wire's originator field run together (wrap-tolerant, so 'CAPI TAL' reads
    CAPITAL), or None when the row prints no originator label. On Santander's layout the originator follows the
    account number."""
    santander = _SANTANDER_WIRE.match(text)
    if santander is not None:
        return "".join(santander.group("originator").split()[:6])
    label = _WIRE_ORIGINATOR_LABEL.search(text)
    return None if label is None else "".join(text[label.end():].split()[:6])


def _wire_remittance_purpose(text: str, region: str, account_name: str | None) -> bool:
    """§7.9: an incoming wire (N1) whose purpose cites an invoice, a PO, an order or goods, and that no wire veto
    refuses (_wire_vetoed)."""
    if not _is_wire_row(text):
        return False
    purpose_text = _WIRE_PARTY_FIELDS.sub(" ", text)
    holder_text = account_name_text(account_name)
    if len(holder_text) >= 6:
        purpose_text = purpose_text.replace(holder_text, " ")
    if not _WIRE_SALE_PURPOSE.search(purpose_text):
        return False
    return not _wire_vetoed(text, region, account_name)


def _wire_vetoed(text: str, region: str, account_name: str | None) -> bool:
    """§7.9: the vetoes of an incoming wire: a non-sale purpose; a financing root after the channel and bank fields
    are removed, or in the first six words after the originator label run together (wrap-tolerant); any known payee;
    the own account (the originator's first two words are the beneficiary's or in the account name); a brand-word
    affiliate (the originator's first distinctive word is the beneficiary's first word or the account name's); a cut
    originator field that starts a financing name; a title or escrow firm (§8.5). The AP rule reads them on a wire
    too (§7.5)."""
    if _WIRE_NON_SALE_PURPOSE.search(text):
        return True
    if _names_financing(_wire_financing_text(text)):
        return True
    run = _wire_originator_run(text)
    if run is not None and _names_financing(run):
        return True
    if match_known_payee(text, credit=True) is not None:
        return True
    holder_text = account_name_text(account_name)
    originator = region.split()
    beneficiary = _WIRE_BENEFICIARY_WORDS.search(text)
    if originator:
        first_two = " ".join(originator[:2])
        if wire_sender_is_beneficiary(text, region):
            return True
        if holder_text and len(originator) >= 2 and first_two in holder_text:
            return True
        originator_first = _first_distinctive_word(_distinctive_words(originator))
        holder_first = holder_text.split()[0] if holder_text else None
        if originator_first is not None and (
            (beneficiary is not None and beneficiary.group(1) == originator_first) or originator_first == holder_first
        ):
            return True
        if _cut_financing_originator(region):
            return True
        if _TITLE_OR_ESCROW_ORIGINATOR.search(region):
            return True
    return False


#: §7.9: an incoming wire's beneficiary field and its first two words.
_WIRE_BENEFICIARY_WORDS = re.compile(r"\bN?BNF\b (\S+)(?: (\S+))?")


def wire_sender_is_beneficiary(text: str, region: str) -> bool:
    """§7.9: an incoming wire's originator is its own beneficiary, the holder sending from its account at another
    bank: the originator's first two words are the beneficiary's. _wire_vetoed refuses Q5 on it, and pass 7 holds it
    as the holder's own money (holder_name)."""
    originator = region.split()
    beneficiary = _WIRE_BENEFICIARY_WORDS.search(text)
    if not originator or beneficiary is None:
        return False
    return " ".join(word for word in beneficiary.groups() if word) == " ".join(originator[:2])


def _cut_financing_originator(region: str) -> bool:
    """§7.9: an originator that fills its field to within two characters of the width (Santander 16, Bank of
    America 25), whose run-together name starts a financing or potential alias of six or more characters, or whose
    last word of three or more letters is a proper prefix of a financing word."""
    name = region.strip()
    if not any(width - 2 <= len(name) <= width for width in _WIRE_ORIGINATOR_FIELD_WIDTHS):
        return False
    run = name.replace(" ", "")
    if any(
        len(alias) >= 6 and (alias.startswith(run) or run.startswith(alias)) for alias in _FINANCING_RUN_TOGETHER_ALIASES
    ):
        return True
    last = name.split()[-1] if name.split() else ""
    return len(last) >= 3 and last.isalpha() and any(
        word.startswith(last) and word != last for word in _FINANCING_FULL_WORDS
    )
