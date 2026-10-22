"""D6 recurrence skips and unnamed potential payees."""
from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from typing import Sequence

from analysis.classification.payees import _unknown_payee_name, _unknown_payee_tokens
from analysis.classification.record import (
    TransactionClassification,
    UNIDENTIFIED_LENDER_OBLIGATION,
    UNIDENTIFIED_MCA_SERVICER,
)
from analysis.descriptor.financing import (
    _card_posting_vetoed,
    _names_card_issuer,
    _names_financing,
    _skips,
    _vendor_match_names_financing,
)
from analysis.descriptor.lexical import (
    _is_reference_token,
    _leading_payee_words,
    _originator_segment,
    _payee_region,
    _row_before_receiver,
)
from analysis.descriptor.rails import _matches_any
from analysis.descriptor.words import (
    _ACH_FIELD_SEGMENT,
    _CHANNEL_VOCABULARY,
    _ENTITY_NAME_LABELS,
    _ENTITY_NOISE,
    _FINANCING_ROOT_PATTERN,
    _LEGAL_FORM_SUFFIXES,
    _ORGANISATION_CUES,
    _SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS,
)


#: D6 skips a row whose own words say it is a transfer, even when no transfer
#: rule claimed it (a transfer to a person is not an MCA remittance).
_TRANSFER_WORD_PATTERNS = (re.compile(r"\b(?:TRANSFER|XFER|TFR)\b"),)
#: D6 also skips a row whose own words say it pays compensation: a commission
#: (with its common misspellings: COMMISION, COMISSION, COMISION, COMMISSON), a
#: bonus, a salary, a stipend or a reimbursement. Pay is not an MCA remittance.
#: The row stays "other"; payroll and wages already classify as payroll.
_COMPENSATION_WORD_PATTERNS = (
    re.compile(r"\bCOMM?ISS?I?ONS?\b"),
    re.compile(r"\b(?:BONUS(?:ES)?|SALARY|SALARIES|STIPENDS?|REIMB(?:URS\w*)?)\b"),
)
#: D6 does not apply to a card purchase, including the card formats the POS rule
#: does not read: a posting that starts "PURCHASE" and its mmdd (after an
#: optional "RECURRING"), read on the normalized text, and a processor*merchant
#: mark, read on the printed text because normalization drops the star. The word
#: PURCHASE alone is not a card mark: an ACH entry description can print it.
_CARD_PURCHASE_POSTING_PATTERN = re.compile(r"^(?:RECURRING )?PURCHASE \d{4}\b")
#: The processor*merchant mark: a letter or digit, an optional space, "*", an
#: optional space, a letter or digit ("TST*NAME", "SQ *NAME", "TST* NAME"). ASCII
#: letters and digits only: `\w` would also take "_" and non-ASCII letters.
_PROCESSOR_MERCHANT_MARK_PATTERN = re.compile(r"[A-Za-z0-9] ?\* ?[A-Za-z0-9]")
#: An ACH entry prints stars too: in its addenda ("RMR*IV*"), a masked account
#: or an ID. A row with an ACH field mark is never read as a card purchase by
#: its star. The SEC codes and field names are read as words on the normalized
#: text; the labels whose colon normalization drops, on the printed text.
_ACH_FIELD_MARK_WORD_PATTERN = re.compile(r"\b(?:ACH|CCD|PPD|CTX|WEB|INDN|RMR|CO ID|ORIG CO)\b")
_ACH_FIELD_MARK_LABEL_PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:DES|ID)\s*:", re.IGNORECASE)
#: D6: a masked recipient account printed after TO ("To ....1234", "TO XXXX1234",
#: "TO ***1234", "TO #1234", "TO x1234", "TO ACCT XXXX1234"), read on the printed
#: text because normalization drops the dots, stars and "#". Its digits are part
#: of the payee, so payments to two recipient accounts are never one payee (D11).
_MASKED_RECIPIENT_PATTERN = re.compile(
    r"\bTO\b[\s:]*(?:(?:ACCOUNT|ACCT)\b[\s:]*)?(?:\.{2,}|…+|X+|\*+|#)[ -]?([0-9]{2,})(?![0-9])",
    re.IGNORECASE,
)


def _has_ach_field_mark(record: TransactionClassification) -> bool:
    return bool(
        _ACH_FIELD_MARK_WORD_PATTERN.search(record.normalized_description)
        or _ACH_FIELD_MARK_LABEL_PATTERN.search(record.original_description or "")
    )


def _is_card_purchase_posting(record: TransactionClassification) -> bool:
    if _CARD_PURCHASE_POSTING_PATTERN.match(record.normalized_description):
        return True
    if _PROCESSOR_MERCHANT_MARK_PATTERN.search(record.original_description or "") and not _has_ach_field_mark(record):
        return True
    # The bank card formats the POS rule does not read, never on a row that names financing, a bank or an
    # organisation (read on the whole row, not on the D11 payee words, which are the card template).
    text = record.normalized_description
    if _card_posting_vetoed(text):
        return False
    if _matches_any(text, _CARD_POSTING_LABEL_PATTERNS):
        return True
    if record.bank == "Wealthsimple" and not _WEALTHSIMPLE_CHANNEL_PATTERN.search(text):
        return True
    return bool(
        record.bank in _CARD_LOCATION_SUFFIX_BANKS
        and _CARD_LOCATION_SUFFIX_PATTERN.search(record.original_description or "")
        and not _has_ach_field_mark(record)
    )


def _masked_recipient(record: TransactionClassification) -> str | None:
    """D6: the printed digits of a masked recipient account after TO, or None."""
    match = _MASKED_RECIPIENT_PATTERN.search(record.original_description or "")
    return match.group(1) if match else None


def _names_only_channel_words(payee: Sequence[str], text: str) -> bool:
    """The D6 payee words are all channel words and the payee region of the normalized row `text` prints no
    organisation cue. D11's key stops at the first reference token once a name has started, so a format that prints
    a reference before the merchant keys as its template ('RECURRING PAYMENT AUTHORIZED ON 01 02 FAB HOLDINGS LLC
    CARD 4321' keys as RECURRING AUTHORIZED ON): the cue keeps such a row in review, as the card veto does (A1)."""
    return (
        bool(payee)
        and all(token in _CHANNEL_VOCABULARY for token in payee)
        and not any(token in _ORGANISATION_CUES for token in _payee_region(text).split())
    )


#: Card-posting labels the POS rule does not read, read on the normalized row with no ACH guard, as _POS_PATTERNS
#: are. MOBILE, RETAIL and PIN PURCHASE and the French ACHAT join the POS rule itself.
_CARD_POSTING_LABEL_PATTERNS = (
    re.compile(r"\b\d{2} \d{2} \d{6,} (?:MOBILE )?PURCHASE\b"),        # Bank of America merchant-first card row
    re.compile(r"\bDE?BI?T CRD\b"),                                     # DBT CRD, DEBIT CRD
    re.compile(r"^DEBIT CARD\b"),                                       # Truist DEBIT CARD RECURRING PYMT / MISC DEBIT
    re.compile(r"^CARD$"),                                              # a type-only card row (CSV export)
    re.compile(r"\bCARD SPEND$"),                                       # Square Checking '<merchant> Card spend'
    re.compile(r"\bAUTHORI[ZS]ED ON \d{2} \d{2}\b.*\bCARD \d{4}$"),     # Wells Fargo '... authorized on mm/dd ... Card nnnn'
    re.compile(r"\bPIN DEBIT\b"),
    re.compile(r"\bRECURRING (?:DEBIT )?CARD\b"),                       # PNC RECURRING DEBIT CARD
    re.compile(r"\bCARD TRANSACTION\b"),                                # Regions
    re.compile(r"\bPURCH\b"),                                           # Citi DEBIT PURCH
    re.compile(r"\bCARD ENDING IN\b"),
    re.compile(r"\bDDA PUR\b"),                                         # TD Bank VISA DDA PUR (without its star)
)
#: Wealthsimple Chequing prints a card purchase as the bare merchant; its other debits carry one of these words
#: (seen in 32 corpus accounts; its bill-payment print form is unverified: re-check when one arrives).
_WEALTHSIMPLE_CHANNEL_PATTERN = re.compile(
    r"\b(?:TRANSFER|TRANSFERT|INTERAC|PRE ?AUTHORI[ZS]ED|PAD|DEBIT|BILL|PAYMENT|EFT|WITHDRAWAL|DEPOSIT|CHEQUE|CHECK|"
    r"LOAN|WIRE|FEE)\b"
)
#: The card network's merchant location, 'NAME, CITY, ST' (Bluevine) or 'NAME ###, CITY, ST, USA' (Found), read
#: on the printed text of those two banks' rows only, and only without an ACH field mark. Bluevine's glued 'CITY,
#: NYUS' variant is a known non-match.
_CARD_LOCATION_SUFFIX_PATTERN = re.compile(
    r",\s*[A-Za-z][A-Za-z .'-]*?\s*,\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|"
    r"MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|PR|GU|VI|AB|BC|MB|NB|NL|NS|NT|NU|"
    r"ON|PE|QC|SK|YT)\s*(?:,\s*USA)?\s*$"
)
_CARD_LOCATION_SUFFIX_BANKS = frozenset({"Bluevine", "Lead Bank (Found)"})


#: Person-to-person, wallet and card-push rails the transfer rule does not read. D6 only: the transfer rule runs
#: before the known payee (step 6 before 7), so widening it would hide a counted funder paid by e-Transfer.
#: VIREMENT covers every French RBC transfer line (Interac e-Transfer, 'Virement envoye', 'Virement par Banque en
#: direct'). Bare WISE is never a rail (WISE CHOICE, FINWISE).
_P2P_RAIL_PATTERNS = (
    re.compile(r"\bVIREMENTS?\b"),
    re.compile(r"\bZEL (?:TO|FROM)\b"),
    re.compile(r"^(?:PMNT|PAYMENT) SENT \d{2} ?\d{2}\b"),
    re.compile(r"\bAPPLE (?:CASH|WALLET)\b"),
    re.compile(r"\b(?:WISE (?:INC|US INC)|TRANSFERWISE)\b|\bDES WISE\b"),
    re.compile(r"\bIAT PAYPAL\b"),
    re.compile(r"\bGREENLIGHT DES APP\b"),
)
#: Transfer templates the 5.2 transfer-word skip does not read. Each fires only for a payee that names no
#: organisation (D11 would publish 'Unidentified lender obligation') and a row that names no financing.
_TRANSFER_TEMPLATE_PATTERNS = (
    re.compile(r"\b(?:XFR|TRF|TRSFR|TRNSFR)\b|\b(?:TRANSFER|XFER|TFR)(?=\d)"),      # abbreviations; glued digits
    re.compile(r"\bTO (?:CHKG|CHK|CHECKG|CHECKING|SAV|SAVINGS|SVGS|SHARES?|MMA)(?: ACCOUNT| ACCT)? X*\d{2,}\b"),
    re.compile(r"^(?:INTERNET|ONLINE|PHONE|TELEPHONE|MOBILE|WEB) (?:WITHDRAWAL|WDRL|WDL)$"),
    # Atlas's Smart Save sweep ('SMARTSAVE <reference> ATLASFINANCIAL <trace>'): only reference numbers may sit
    # between the two words, since the veto reads the row without the matched words, and the tail stops at
    # ATLASFINANCIAL, so no name printed inside the match is hidden from it.
    re.compile(r"\bSMART ?SAVE(?:\s+[0-9]+)*\s+ATLAS ?FIN(?:ANCIAL)?\b"),
    re.compile(r"\b(?:RTP SENT|REAL TIME PAYMENT TO|FEDNOW (?:PAYMENT|PMT) TO)\b"),
)
#: Rows whose own words say they cannot pay a funder: the holder's cash withdrawal in the formats the ATM rule does
#: not read (only reference tokens or NETWORK may sit between ATM/ABM and the withdrawal word, so a payee name never
#: fills the gap), the offset of an ACH batch the holder sent from its own bank's portal (inferred from the row
#: shape; D11 already drops the batch name from the review entry), and school, tuition and childcare billing.
_NON_REMITTANCE_WORD_PATTERNS = (
    re.compile(
        r"\b(?:ATM|ABM)\b(?:\s+(?:\S*\d\S*|NETWORK)){0,3}\s+(?:CASH\s+)?"
        r"(?:WITHDRAWALS?|WITHDRAW|WITHDRWLS?|WDRLS?|WDL|W D|WD)\b"
    ),
    re.compile(r"\bWITHDRAWALS? (?:ATM|ABM)(?:\s+\S*\d\S*|$)"),
    re.compile(r"\bWITHDRWLS?\b"),
    re.compile(r"(?:^|(?<=\d )|\b(?:ATM|ABM|NETWORK|TELLER|COUNTER|BRANCH|LARGE|NON \S+)\s)CASH WITHDRA\w*"),
    re.compile(r"\bRETRAITS? (?:GAB|DAB|ATM|ABM|PAR GA|AU GUICHET|AU COMPTOIR)\b"),
    re.compile(r"^G RETRAIT\b"),
    re.compile(r"^(?:BUS ONLINE ACH SETTLEMENT|ACH SETTLMT REL DATE FUND)\b"),
    re.compile(r"\bDES FACTS\b|\bPAYMENT FACTS\b|\bFACTS(?: \d+)?$"),
    re.compile(r"\b(?:TUITION|DAYCARE|CHILD ?CARE|PRESCHOOL|MONTESSORI|KINDERCARE|BRIGHTWHEEL|PROCARE)\b"),
)
#: Vendors and other payees that never lend, read on the D11 payee words only (never an entry description: SBFS/Rapid
#: Finance prints 'Vendor Pay'; never the holder: a holder named '... Distributions' pays Credibly), guarded by the
#: lending words below and by the holder's own name. DISTRIBUT* also clears recurring owner distributions. Names join
#: only after collision_check.py prints no registry or ledger hit.
_VENDOR_PAYEE_PATTERNS = (
    re.compile(r"\bBOOKK\w*"),
    re.compile(r"\b(?:DISTR|DISTRIBUT\w*|FOODSERVICE)\b"),
    re.compile(r"\bMANUFACTURING\b"),
    re.compile(r"\bINVOICES?\b"),
    re.compile(r"\b(?:CINTAS\w*|UNIFIRST|ARAMARK|SYSCO|ALSCO)\b|\bUS FOODS\b"),
    re.compile(r"^(?:FACEBOOK|FACEBK|META ADS|META PLATFORMS|GOOGLE ADS|TIKTOK ADS|YELP|ANGI|HOMEADVISOR|THUMBTACK)\b"),
    re.compile(r"\b(?:UNIFORMS?|LINEN|JANITORIAL|LANDSCAP\w*|LAWN|PEST CONTROL)\b"),
    re.compile(r"\bROYALT(?:Y|IES)\b|\bFRANCHIS\w*|\b(?:AD|MARKETING|ADVERTISING) FUND\b"),
    re.compile(r"\bTITHE\w*|\bCHURCH\b|\bMINISTRIES\b|\bDONATIONS?\b|\b(?:PUSHPAY|GIVELIFY|VANCO|SUBSPLASH|EASYTITHE)\b"),
    re.compile(r"\b(?:EZPASS|ZPASS|SUNPASS|FASTRAK|TXTAG|NTTA|HCTRA|PEACH PASS|IPASS|BESTPASS|PREPASS|TOLLS?|TOLLWAY)\b"),
    re.compile(r"\b(?:DRAFTKINGS|FANDUEL|BETMGM|LOTTERY|OLG|CASINO)\b"),
)
#: A Bill.com or Melio payment is a vendor's only when the row prints an invoice number.
_BILL_PAY_PLATFORM_PATTERN = re.compile(r"^(?:BILL COM|MELIO)\b")
_INVOICE_NUMBER_PATTERN = re.compile(r"\bINV \d")
#: The vendor skip's lending guard: the shared roots plus the Canadian pre-authorized-debit channel word.
_VENDOR_LENDING_GUARD = re.compile(_FINANCING_ROOT_PATTERN.pattern + r"|\bPAD\b")
#: The account holder's name words, read without the module normalizer: classifying a row normalizes exactly one
#: text (tests/test_classifier_lookups.py::test_each_row_is_normalized_exactly_once).
_HOLDER_WORD = re.compile(r"[A-Z0-9]+")


def _payee_words_are_bounded(text: str) -> bool:
    """Whether an ACH field, or a reference token after the payee's first name word, ends the payee's words before
    the normalized row `text` ends. A row that is one run of words (Regions '<funder> ACHPMT <receiver>', Bluevine
    '<funder> PAY PAYMENT TO <receiver>') can end with the account holder's name."""
    labelled = _ENTITY_NAME_LABELS.sub(" ", text)
    if _ACH_FIELD_SEGMENT.search(labelled) is not None:
        return True
    started = False
    for token in labelled.split():
        if _is_reference_token(token):
            if started:
                return True
            continue
        started = started or (token not in _ENTITY_NOISE and len(token) > 1)
    return False


def _is_vendor_payee(payee: Sequence[str], text: str, account_name: str | None) -> bool:
    """The D11 payee words (or, on a bounded row, the originator segment, which then never reads a receiver field)
    name a vendor or another payee that never lends, the row prints no lending word (outside the matched vendor words,
    which carry none themselves), and those words carry none of the account holder's own name words. On a row that is
    one run of words the segment is never read, and when the holder's name is unknown the vendor word must be the
    payee's first word."""
    words = " ".join(payee)
    bounded = _payee_words_are_bounded(text)
    segment = _originator_segment(text) if bounded else ""
    found = next(
        (
            match
            for source in (words, segment)
            for pattern in _VENDOR_PAYEE_PATTERNS
            if (match := pattern.search(source)) and not _vendor_match_names_financing(match.group(0))
        ),
        None,
    )
    if found is None and _BILL_PAY_PLATFORM_PATTERN.search(words) and _INVOICE_NUMBER_PATTERN.search(text):
        found = _BILL_PAY_PLATFORM_PATTERN.search(words)
    if found is None:
        return False
    holder = {
        word for word in _HOLDER_WORD.findall((account_name or "").upper())
        if len(word) >= 4 and word not in _LEGAL_FORM_SUFFIXES
    }
    if not bounded and not holder and found.start() > 0:
        return False  # a label-less run of words may end with the holder's name, which is unknown here
    if holder & (set(payee) | set(segment.split())):
        return False
    return _VENDOR_LENDING_GUARD.search(text.replace(found.group(0), " ")) is None


#: Tax authorities and government agencies printed without TAX, IRS or CRA, read on the payee region only (never
#: an entry description or memo) and only for a payee that names no organisation. The row stays 'other': the tax
#: rule has no amount guard and runs before the known payee, so it is not widened.
_GOVERNMENT_PAYEE_PATTERNS = (
    re.compile(r"\b(?:UNITED STATES|U ?S) (?:(?:DEPT|DEPARTMENT) OF (?:THE )?)?TREAS(?:URY)?\b"),
    re.compile(r"\bEFTPS\b"),
    re.compile(r"\bCCRA\b"),
    re.compile(r"\bRECEIVER GENERAL\b"),
    re.compile(r"\bSECRETARY OF STATE\b"),
    re.compile(r"\bSTATE OF [A-Z]+(?: [A-Z]+)? (?:SOS|DMV)\b"),
    re.compile(r"\b(?:DEPT|DEPARTMENT) OF MOTOR VEHICLES?\b"),
    re.compile(r"\b(?:DTF|EDD|DOR|TAXATION|COMPTROLLER)\b"),
    re.compile(r"\b(?:DEPT|DEPARTMENT) (?:OF )?REV(?:ENUE)?\b"),
    re.compile(r"\bTREASURER OF STATE\b|\b[A-Z]{2} TREASURY\b"),
    re.compile(r"\bREVENU QUEBEC\b|\bMINISTRE DU REVENU\b"),
    re.compile(r"\b(?:WSIB|WORKSAFE\w*|WCB|EHT|CNESST)\b"),
)
#: Payees the financing-keyword recurrence never promotes: a government finance department (FINANCE is its
#: name, not a loan) and a retailer named ADVANCE. Their single rows stay 'other' / financing_keyword_review.
_GOVERNMENT_FINANCE_DEPARTMENT_PATTERNS = (
    re.compile(r"\b(?:DEPT|DEPARTMENT|MINISTRY|MIN|MINISTERE|DIV) (?:OF |DES )?FINANCES?\b"),
    re.compile(r"\bFINANCE DEPT\b"),
)
_RETAILER_ADVANCE_PATTERNS = (re.compile(r"\bADVANCE (?:AUTO PARTS|STORES)\b"),)
#: A court-ordered family-support payment through a state conduit is not an MCA remittance. Read before the
#: receiver fields (a holder named '... Child Support Svcs' never silences its funder). GARNISH, LEVY, LEGAL
#: ORDER, bare SDU and CSE stay out: an MCA judgment creditor collects through a law office or a marshal.
_FAMILY_SUPPORT_WORD_PATTERNS = (
    re.compile(r"\bCHI?LD ?SUPP(?:ORT|T)?\b"),
    re.compile(r"\bFAM(?:ILY)? SUPP(?:ORT)? (?:REG(?:ISTRY)?|PAYMENT CENTER|PMT CTR|PAYMENT CTR)\b"),
    re.compile(r"\bSTATE DISBURSEMENT UNIT\b"),
)
#: Owner money is not an MCA remittance: a draw or distribution to an owner, member, partner or shareholder, a
#: dividend, a per diem, a guaranteed payment. Read before the receiver fields, with the veto (DIVIDEND FINANCE
#: is a lender); a bare DISTRIBUTION is a vendor's name.
_OWNER_PAY_WORD_PATTERNS = (
    re.compile(r"\b(?:OWNERS?|MEMBERS?|PARTNERS?|SHAREHOLDERS?) (?:DRAWS?|DISTRIBUTIONS?)\b"),
    re.compile(r"\bPER DIEM\b"),
    re.compile(r"\bGUARANTEED PAYMENTS?\b"),
    re.compile(r"\bDIVIDENDS?\b"),
)
#: A payments platform paying a recipient it names ('Pay To: <name>'): the platform is the originator, not a
#: creditor. Only a person recipient is skipped: Payoneer's Capital Advance is collected by ACH bank debit (an
#: alternative position), so an organisation recipient, the platform itself or no recipient stays reviewed.
_PLATFORM_PAYOUT_PATTERN = re.compile(r"\bPAYONEER\b.*\bPAY TO\b(?P<recipient>.*?)(?:\bPAYMENT DATE\b|\bTRN\b|$)")


def _is_platform_payout_to_person(text: str) -> bool:
    """The shared veto reads the whole row `text`, the recipient included. The skip's own words (PAYONEER, PAY TO,
    PAYMENT DATE, TRN) carry no financing root, so nothing is removed first: the pattern's spans are never hidden
    from the veto."""
    found = _PLATFORM_PAYOUT_PATTERN.search(text)
    if found is None:
        return False
    recipient = [token for token in found.group("recipient").split()
                 if len(token) > 1 and not _is_reference_token(token)]
    return bool(recipient) and not any(
        token in _ORGANISATION_CUES or token == "PAYONEER" for token in recipient
    ) and not _names_financing(text)


#: A payment processor's own small charge to its merchant, through its merchant-services spelling: Square's
#: seller-account entry code (SQ + the entry date yymmdd) and Intuit Payment Solutions. Capped at 50 dollars
#: (Intuit's fees and chargebacks, Square's small charges): these rails also carry invoice payments to third parties
#: in the thousands, so a fixed debit above the cap stays in review. Never with loan or capital wording, including
#: Square's glued loan codes (SQCAP, SQ LOAN). A whole number (tests/test_no_statement_hardcodes.py).
_PROCESSOR_ACCOUNT_DEBIT_PATTERNS = (
    re.compile(r"\bSQUARE\b.*\bSQ ?\d{6}\b|\bSQ ?\d{6}\b.*\bSQUARE\b"),
    re.compile(r"\bINTUIT (?:PYMT|PMT|PAYMENTS?) SOL(?:N|NS|UTIONS?)?\b"),
)
_PROCESSOR_DEBIT_FINANCING_GUARD = re.compile(
    r"\bLOANS?\b|\bADVANCE\b|\bFINANC(?:E|ING|IAL)\b|\bFUND(?:ER|ING)\b|\bCAP(?:ITAL)?(?![A-Z])|\bMCA\b"
    r"|\bSQ ?CAP|\bSQ ?LOAN|\bLENDING\b"
)
_PROCESSOR_ACCOUNT_CHARGE_MAX = 50
#: An insurer whose name the ACH field cut short (INSU, INSUR, INSURA, INSURAN, INSURANC: the 16-character company
#: name or the 10-character entry description). Read on the D11 payee words only: the holder's name (INDN, IND
#: NAME, or unlabeled) never decides. INSURED, INSURER and the bare INS stay out.
_TRUNCATED_INSURANCE_WORD_PATTERN = re.compile(r"\bINSU(?:R|RA|RAN|RANC)?\b")
#: Phone and cable carriers, matched at the START of the payee's leading words (_leading_payee_words), so a carrier
#: printed after the payee's own name (a receiver that is a wireless dealer) never decides. Brand names only; BELL,
#: ROGERS, SHAW and SPRINT need their telecom word; ATT only in its bill and payment forms. The VERIZON lookahead
#: covers the registry's Verizon Visa alias only (a 'SYNCB VERIZON' card payment in 'other' hides no funder).
_TELECOM_CARRIER_PATTERNS = (
    re.compile(r"(?:KOODO|FIDO|TELUS|VIDEOTRON|SASKTEL|EASTLINK|CHATR|COGECO)\b"),
    re.compile(r"(?:FREEDOM|VIRGIN|PUBLIC|LUCKY|BOOST|MINT|T) ?MOBILE\b"),
    re.compile(r"VIRGIN PLUS\b"),
    re.compile(r"BELL (?:CANADA|MOBILITY|MTS|ALIANT)\b"),
    re.compile(r"ROGERS (?:WIRELESS|COMMUNICATIONS?|CABLE)\b"),
    re.compile(r"SHAW (?:CABLE|COMMUNICATIONS?|DIRECT)\b"),
    re.compile(r"VERIZON\b(?! (?:CREDIT|VISA))"),
    re.compile(r"(?:VZWRLSS|AT AND T|METRO ?PCS|METRO BY T MOBILE|TRACFONE|COMCAST|XFINITY|CENTURYLINK|WINDSTREAM|"
               r"DIRECTV)\b"),
    re.compile(r"ATT\b(?= (?:BILL|PAYMENT|MOBILITY|UVERSE|WIRELESS)\b|\s*$)"),
    re.compile(r"(?:SPRINT|CRICKET|TOTAL) WIRELESS\b"),
    re.compile(r"(?:US|U S|CONSUMER) CELLULAR\b|USCELLULAR\b"),
    re.compile(r"(?:CHARTER|COX|FRONTIER) COMM(?:UNICATIONS?)?\b"),
    re.compile(r"DISH NETWORK\b"),
)


def _is_processor_account_charge(record: TransactionClassification) -> bool:
    """Besides its own loan and capital guard, the skip reads the shared veto on the whole row. The skip's own words
    (SQUARE, SQ and the entry date, INTUIT PYMT SOLN) carry no financing root, so nothing is removed first."""
    text = record.normalized_description
    return (
        abs(record.amount) <= _PROCESSOR_ACCOUNT_CHARGE_MAX
        and _matches_any(text, _PROCESSOR_ACCOUNT_DEBIT_PATTERNS)
        and _PROCESSOR_DEBIT_FINANCING_GUARD.search(text) is None
        and not _names_financing(text)
    )


def _d6_skip(record: TransactionClassification, payee: tuple[str, ...]) -> str | None:
    """Why D6 (spec D6 and its clarifications) does not take this default debit, or None when it may.

    `payee` is the row's D11 payee words (`_unknown_payee_tokens`). Every clause added in 5.3 reads the payee's
    words (never a receiver field) and carries the shared financing veto (`_names_financing`)."""
    text = record.normalized_description
    if _matches_any(text, _TRANSFER_WORD_PATTERNS):
        return "transfer_word"
    if _matches_any(text, _COMPENSATION_WORD_PATTERNS):
        return "compensation"
    if _is_card_purchase_posting(record):
        return "card_purchase_posting"
    if _names_only_channel_words(payee, text) and not _names_financing(text):
        return "channel_words_only"
    if _skips(_row_before_receiver(text), _P2P_RAIL_PATTERNS, text):
        return "p2p_rail"
    if _unknown_payee_name(payee) in (None, UNIDENTIFIED_LENDER_OBLIGATION) and _skips(
        _row_before_receiver(text), _TRANSFER_TEMPLATE_PATTERNS, text
    ):
        return "transfer_template"
    if _skips(_row_before_receiver(text), _NON_REMITTANCE_WORD_PATTERNS, text):
        return "not_a_remittance"
    if _skips(_row_before_receiver(text), _SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS, text):
        return "savings_or_investment"
    if _is_vendor_payee(payee, text, record.account_name):
        return "named_non_lender"
    if _unknown_payee_name(payee) in (None, UNIDENTIFIED_LENDER_OBLIGATION) and _skips(
        _payee_region(text), _GOVERNMENT_PAYEE_PATTERNS, text
    ):
        return "government_payee"
    if _skips(_row_before_receiver(text), _FAMILY_SUPPORT_WORD_PATTERNS, text):
        return "family_support"
    if _skips(_row_before_receiver(text), _OWNER_PAY_WORD_PATTERNS, text):
        return "owner_pay"
    if _is_platform_payout_to_person(text):
        return "platform_payout_to_person"
    if _is_processor_account_charge(record):
        return "processor_account_charge"
    if _skips(" ".join(payee), (_TRUNCATED_INSURANCE_WORD_PATTERN,), text):
        return "truncated_insurer"
    leading = _leading_payee_words(text)
    carrier = next((found for pattern in _TELECOM_CARRIER_PATTERNS if (found := pattern.match(leading))), None)
    if carrier is not None and not _names_financing(text, besides=carrier.group(0)):
        return "telecom_carrier"
    if _names_card_issuer(payee, text):
        return "card_issuer_alone"
    return None


def _keyword_recurrence_skip(record: TransactionClassification) -> str | None:
    """Why the financing-keyword recurrence (recurring_financing_counterparty) does not take this row, or None.

    Its rows carry a financing word by definition (LOAN, ADVANCE, FINANCE, FUNDING…), so these clauses carry no
    financing veto; each names a payee that is never a lender (A7, A8)."""
    region = _row_before_receiver(record.normalized_description)
    if _matches_any(region, _GOVERNMENT_FINANCE_DEPARTMENT_PATTERNS):
        return "government_finance_department"
    if _matches_any(region, _RETAILER_ADVANCE_PATTERNS):
        return "retailer_named_advance"
    if _matches_any(region, _FAMILY_SUPPORT_WORD_PATTERNS):
        return "family_support"
    return None


#: The D6 payee words of a card network's 'NAME, CITY, ST' line are the printed name before the first comma (the
#: city never joins the name), read without the module normalizer.
_PRINTED_NAME_WORD = re.compile(r"[A-Z0-9]+")


def _record_payee_tokens(record: TransactionClassification) -> tuple[str, ...]:
    """D6's payee words for one row: D11's words, or, on a 'NAME, CITY, ST' line with no ACH field mark, the words of
    the printed name before the first comma."""
    printed = record.original_description or ""
    if _CARD_LOCATION_SUFFIX_PATTERN.search(printed) and not _has_ach_field_mark(record):
        return _unknown_payee_tokens(" ".join(_PRINTED_NAME_WORD.findall(printed.split(",", 1)[0].upper())))
    return _unknown_payee_tokens(record.normalized_description)


#: The names D11 and D10 publish for a payee they cannot name. The Potential Lenders tab lists each payee key of
#: them on its own line (potential_payee_label), never one line for all.
_UNNAMED_POTENTIAL_ENTITIES = frozenset({UNIDENTIFIED_LENDER_OBLIGATION, UNIDENTIFIED_MCA_SERVICER})
_RECURRENCE_CADENCE = re.compile(r"^(daily|weekly)_fixed_debit_")


def _label_unnamed_potential_payees(records: list[TransactionClassification]) -> list[TransactionClassification]:
    """One Potential Lenders line per unnamed payee of a statement. The rows of one payee key (entity, rule, payee
    words, amount and masked recipient) share a label that names the entity, the cadence of a recurrence and the
    amount, never a payee word (D11): 'Unidentified lender obligation (weekly, 450.00)'. A second key with the same
    label gets ' #2'. canonical_entity is unchanged."""
    groups: dict[tuple[object, ...], list[int]] = {}
    for index, record in enumerate(records):
        if record.classification == "potential_lender" and record.canonical_entity in _UNNAMED_POTENTIAL_ENTITIES:
            key = (record.canonical_entity, record.match_method, _record_payee_tokens(record),
                   round(abs(record.amount), 2), _masked_recipient(record))
            groups.setdefault(key, []).append(index)
    labelled = list(records)
    used: dict[str, int] = {}
    for (entity, _method, _payee, amount, _recipient), indexes in groups.items():
        cadence = _RECURRENCE_CADENCE.match(records[indexes[0]].matched_rule or "")
        label = f"{entity} ({cadence.group(1)}, {amount:,.2f})" if cadence else f"{entity} ({amount:,.2f})"
        used[label] = used.get(label, 0) + 1
        if used[label] > 1:
            label = f"{label} #{used[label]}"
        for index in indexes:
            labelled[index] = replace(records[index], potential_payee_label=label)
    # Every potential lender row, named or not, gains its payee's amount-free key in the same step. The labels above
    # are unchanged.
    for index, record in enumerate(labelled):
        if record.classification == "potential_lender":
            labelled[index] = replace(record, potential_payee_key=_potential_payee_key(record))
    return labelled


def _potential_payee_key(record: TransactionClassification) -> str:
    """One key per payee of a potential lender, named or not, which lender_payment_changes reads to follow a payee
    across an amount change; nothing else reads it. The probe's key (the entity, D6's payee words and the masked
    recipient), with no amount and no match method, as the first 16 hex characters of its SHA-256 digest: stable
    across statements and processes, and no payee word is published (D11)."""
    parts = [record.canonical_entity or "", " ".join(_record_payee_tokens(record)), _masked_recipient(record) or ""]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
