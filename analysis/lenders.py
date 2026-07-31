from __future__ import annotations

import re

from .transaction_classifier import (
    classify_transaction,
    normalize_transaction_description,
)

LENDER_KEYWORDS: dict[str, list[str]] = {
    "ACH CAPITAL": ["ACH CAPITAL"],
    "AFFIRM": ["AFFIRM", "AFFIRMCOM", "AFFIRM PAY", "AFFIRM COM", "AFFIRM COM PAYME"],
    "BALBOA CAPITAL": ["BALBOA", "BALBOA CAPITAL"],
    "BITTY ADVANCE": ["BITTY", "BITTY ADVANCE", "MCA SAVINGS"],
    "BIZFUND": ["BIZFUND", "BIZFUND ACHDEBIT"],
    "BLUEVINE": ["BLUEVINE"],
    "BLACKBULL": ["BLACKBULL", "BLACKBULL ENTERP", "BLACKBULL WCTA"],
    "BREAKOUT CAPITAL": ["BREAKOUT", "BREAKOUT CAPITAL"],
    "CAN CAPITAL": ["CAN CAPITAL", "CANCAP", "CANACAP"],
    "CAPITAL INFUSION": ["CAP INFUSION", "CAPITAL INFUSION"],
    "CDC SMALL BUSINESS": ["CDC SMALL BUS", "CDC SMALL BUSINESS"],
    "CFGMS": ["CFGMS", "LCM", "LCM 1823095", "MC 844 662 3467", "CGF"],
    "CHANNEL PARTNERS": ["CHANNEL PARTNERS", "LENDING SERVICES"],
    "CLEARCO": ["CLEARCO"],
    "CREDIBLY": ["CREDIBLY", "RETAIL CAPITAL"],
    "DAILY FUNDING": ["DAILY FUNDING", "DAILYFUNDING"],
    "DE LAGE LANDEN": ["DE LAGE LANDEN", "DELAGELANDEN", "DIRECT DEB DELAGELANDEN"],
    "DELTA": ["DELTA", "FUNDRY"],
    "EBF HOLDINGS": ["EBF", "EBF DEBIT", "EBF HOLDINGS", "HOLDINGS EBF"],
    "ELEVATED FUNDING": ["ELEVATED", "ELEVATED FUNDING"],
    "EMINENT FUNDING": ["EMINENT", "3329001101", "EMINENT FUNDING"],
    "EMS HOLDINGS": ["EMS", "EMS HOLDINGS"],
    "EVEREST BUSINESS FUNDING": ["EVEREST", "EBFUNDING", "EVEREST BUSINESS FUNDING"],
    "EXPANSION CAPITAL": [
        "EXP CAPITAL", "EXPANSION CAPITA", "EXPANSION CAPITAL",
        "EXPANSION CAPITA FUNDING", "EXPANSION CAPITAL FUNDING",
        "EXPANSION CAPITA FUNDING 5769267", "ECG LLC",
    ],
    "FORA FINANCIAL": ["FORA", "FORA FINANCIAL"],
    "FORWARD FINANCING": [
        "FORWARD FINANCIN", "FORWARD FINANCING", "FORWARD FUNDING",
        "FORWARDFINANCIN", "FORWARD FINANCINFF",
    ],
    "FUNDBOX": ["FUNDBOX"],
    "FUNDATION": ["FUNDATION"],
    "FUNDIFI": ["FUNDIFI", "FUNDFI", "FUNDFI CANADA", "FUNDFICANADA"],
    "FUNDWORKS": [
        "FW CAPITAL", "FWCAPITAL", "FUNDWORKS", "FUND WORKS",
        "THE FUNDWORKS", "THE FUND WORKS", "FUNDWORK", "FUND WORK",
        "FUNDOWRK", "FUNDOWRKS", "FUND WRKS", "FUNDWK",
        "ACH FUNDWORKS", "FUNDWORKS LLC", "THE FUNDWORKS LLC",
    ],
    "GLOBAL MERCHANT": ["EDI PYMNTS", "GBL MERCHANT", "GLOBAL MER", "GLOBAL MER EDI", "GLOBAL MERCHANT", "WALL"],
    "GREENBOX CAPITAL": ["GREENBOX", "GREENBOX CAPITAL"],
    "GFE": ["GFE", "UFCE", "UNITED FIRST", "GLOBAL FUNDING"],
    "HEADWAY CAPITAL": ["HEADWAY", "HEADWAY CAPITAL"],
    "HOUSE": ["HOUSE", "MRBIZCAP"],
    "IDEA FINANCIAL": ["IDEAFINANCIAL", "IDEA FINANCIAL"],
    "IOU FINANCIAL": ["IOU", "IOU FINANCIAL"],
    "IRUKA": ["IRUKA", "J&G", "ICG"],
    "J & A MARKETING": ["J & A MARKETING", "J A MARKETING", "J&A MARKETING"],
    "JRW CAPITAL": ["JRW CAPITAL", "JR CAPITAL LLC"],
    "KABBAGE": ["KABBAGE"],
    "KAPITUS": ["KAPITUS", "STRATEGIC FUNDING"],
    "LENDINI": ["LENDINI", "FUNDING METRICS"],
    "LENTEGRITY": ["LENTEGRITY", "LENTEGRITY BILLPAY"],
    "LG FUNDING": ["LG FUNDING", "LG FUNDING LLC"],
    "LIBERTAS FUNDING": ["LIBERTAS", "LIBERTAS FUNDING"],
    "LOANME": ["LOAN ME", "LOANME"],
    "MUDFLAP": ["MUDFLAP"],
    "NATIONAL FUNDING": ["NATIONAL FUNDING"],
    "NAVITAS CREDIT CORP": ["NAVITAS CREDIT CORP", "NAVITAS CREDIT C", "NAVITAS"],
    "NMEF": ["NMEF", "NMEF 2023 A"],
    "ONDECK": ["ON DECK", "ONDECK", "ENOVA"],
    "PAR FUNDING": ["PAR", "PAR FUNDING"],
    "PAYABILITY": ["PAYABILITY"],
    "PAYPAL WORKING CAPITAL": ["PAYPAL CAPITAL", "PAYPAL WORKING CAPITAL"],
    "QUANTUM CAPITAL": ["QUANTUM", "QUANTUM CAPITAL"],
    "QUARTERSPOT": ["QUARTER SPOT", "QUARTERSPOT"],
    "RAPID FINANCE": ["RAPIDFINANCE", "RAPID FINANCE", "RAPID", "SBFS"],
    "RELIANT FUNDING": ["RELIANT", "RELIANT FUNDING"],
    "RETRO ADVANCE": ["RETRO ADVANCE", "RETROADVANCE", "RETROADVANCEINC", "RETRO ADVANCE INC"],
    "SHEAVES": ["SHEAVES", "3201961 ONTARRIO INC", "11302078 CANADA LTD"],
    "SMARTPAY": ["SMARTPAY", "SMARTPAY SOL"],
    "SPECIALTY": ["SPECIALTY", "ASCENTRA VENTURE"],
    "SHOPIFY CAPITAL": ["SHOPIFY CAPITAL", "SHOPIFY CREDIT"],
    "SQUARE CAPITAL": ["SQ CAPITAL", "SQUARE CAPITAL"],
    "TORRO": ["TORRO"],
    "VELOCITY CAPITAL": ["VELOCITY", "VELOCITY CAPITAL"],
    "YELLOWSTONE CAPITAL": ["YELLOWSTONE", "YELLOWSTONE CAPITAL"],
    "2M7": ["2M7", "URAL LINK"],
}

FALSE_LENDER_KEYWORDS: list[str] = [
    "SQ", "SQUARE", "PAYPAL", "PAY PAL", "STRIPE", "SNAP",
    "VENMO", "ZELLE", "CASHAPP", "INTUIT", "KLARNA", "SHOPIFY",
    "CARD PURCHASE", "POS", "DEBIT CARD", "PURCHASE AUTHORIZED",
    "CLOVER", "TOAST",
]

LOAN_KEYWORDS = [
    "LOAN", "MORTGAGE", "MORTG", "LINE OF CREDIT", "LOC PMT", "LOC PYMT", "LOC PAY", "SBA",
]


def normalize_description(description: str) -> str:
    return normalize_transaction_description(description)


def _contains_alias(text: str, alias: str) -> bool:
    alias = normalize_description(alias)
    if not alias:
        return False
    if re.search(r"[A-Z0-9]", alias[0]) and re.search(r"[A-Z0-9]", alias[-1]):
        return re.search(rf"(?<![A-Z0-9]){re.escape(alias)}(?![A-Z0-9])", text) is not None
    return alias in text


def find_lender_match(description: str) -> tuple[str, str] | None:
    text = normalize_description(description)
    for lender, aliases in LENDER_KEYWORDS.items():
        hit = next((alias for alias in aliases if _contains_alias(text, alias)), None)
        if hit:
            return lender, hit
    return None


def has_false_lender_keyword(description: str) -> bool:
    text = normalize_description(description)
    return any(_contains_alias(text, alias) for alias in FALSE_LENDER_KEYWORDS)


def is_pos_transaction(description: str, amount: float = -1.0) -> bool:
    return classify_transaction(description, amount).is_pos_purchase


def is_loan_transaction(description: str) -> bool:
    text = normalize_description(description)
    return any(_contains_alias(text, alias) for alias in LOAN_KEYWORDS)
