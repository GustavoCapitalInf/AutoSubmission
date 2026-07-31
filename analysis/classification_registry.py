"""Maintained entity registries for deterministic transaction classification.

Aliases are normalized and matched on token boundaries by
``analysis.transaction_classifier``. Keep generic financing words out of the
verified registry; they are evidence signals, not lender identities.
"""
from __future__ import annotations


CONFIRMED_LENDER_ALIASES: dict[str, tuple[str, ...]] = {
    "ACH CAPITAL": ("ACH CAPITAL",),
    "AFFIRM": ("AFFIRM", "AFFIRMCOM", "AFFIRM COM", "AFFIRM PAY"),
    "BDC": ("BDC", "BUSINESS DEVELOPMENT BANK OF CANADA"),
    "BITTY ADVANCE": ("BITTY ADVANCE", "BITTY", "MCA SAVINGS"),
    "BIZFUND": ("BIZFUND",),
    "BLACKBULL": ("BLACKBULL", "BLACKBULL ENTERP", "BLACKBULL WCTA"),
    "BLUEVINE": ("BLUEVINE",),
    "BREAKOUT CAPITAL": ("BREAKOUT CAPITAL", "BREAKOUT"),
    "CAN Capital": ("CAN CAPITAL",),
    "CanaCap": ("CANACAP", "CANA CAP", "CANCAP", "CANAOAP", "CANAC4P"),
    "CAPITAL INFUSION": ("CAPITAL INFUSION", "CAP INFUSION"),
    "CDC SMALL BUSINESS": ("CDC SMALL BUSINESS", "CDC SMALL BUS"),
    "CFGMS": ("CFGMS", "LCM 1823095", "MC 844 662 3467"),
    "CHANNEL PARTNERS": ("CHANNEL PARTNERS",),
    "CLEARCO": ("CLEARCO",),
    "CREDIBLY": ("CREDIBLY", "RETAIL CAPITAL"),
    "DAILY FUNDING": ("DAILY FUNDING", "DAILYFUNDING"),
    "EBF HOLDINGS": ("EBF HOLDINGS", "EBF DEBIT", "HOLDINGS EBF"),
    "ELEVATED FUNDING": ("ELEVATED FUNDING", "ELEVATED"),
    "EMINENT FUNDING": ("EMINENT FUNDING", "EMINENT", "3329001101"),
    "EMS HOLDINGS": ("EMS HOLDINGS",),
    "EVEREST BUSINESS FUNDING": (
        "EVEREST BUSINESS FUNDING",
        "EBFUNDING",
        "EVEREST",
    ),
    "EXPANSION CAPITAL": (
        "EXPANSION CAPITAL",
        "EXPANSION CAPITA",
        "EXPANSION CAPITAL FUNDING",
        "EXPANSION CAPITA FUNDING",
        "EXP CAPITAL",
        "ECG LLC",
    ),
    "FORA FINANCIAL": ("FORA FINANCIAL", "FORA"),
    "Forward Financing": (
        "FORWARD FINANCING",
        "FORWARD FINANCIN",
        "FORWARDFINANCIN",
        "FORWARD FINANCINFF",
    ),
    "Forward Funding": ("FORWARD FUNDING",),
    "FUNDBOX": ("FUNDBOX",),
    "FUNDATION": ("FUNDATION",),
    "FUNDIFI": ("FUNDIFI", "FUNDFI", "FUNDFI CANADA", "FUNDFICANADA"),
    "FUNDWORKS": (
        "THE FUNDWORKS LLC",
        "THE FUND WORKS LLC",
        "FUNDWORKS LLC",
        "THE FUND WORKS",
        "THE FUNDWORKS",
        "FUND WORKS",
        "FUNDWORKS",
        "FUNDOWRKS",
        "FUNDOWRK",
        "FUND WRKS",
        "FUNDWK",
        "FW CAPITAL",
        "FWCAPITAL",
    ),
    "GFE": ("GFE", "UFCE", "UNITED FIRST"),
    "GREENBOX CAPITAL": ("GREENBOX CAPITAL", "GREENBOX"),
    "HEADWAY CAPITAL": ("HEADWAY CAPITAL", "HEADWAY"),
    "IDEA FINANCIAL": ("IDEA FINANCIAL", "IDEAFINANCIAL"),
    "IOU FINANCIAL": ("IOU FINANCIAL",),
    "IRUKA": ("IRUKA",),
    "J & A MARKETING": ("J AND A MARKETING", "J A MARKETING"),
    "JRW CAPITAL": ("JRW CAPITAL", "JR CAPITAL LLC"),
    "KABBAGE": ("KABBAGE",),
    "KAPITUS": ("KAPITUS", "STRATEGIC FUNDING"),
    "LENDINI": ("LENDINI", "FUNDING METRICS"),
    "LENTEGRITY": ("LENTEGRITY", "LENTEGRITY BILLPAY"),
    "LG FUNDING": ("LG FUNDING", "LG FUNDING LLC"),
    "LIBERTAS FUNDING": ("LIBERTAS FUNDING", "LIBERTAS"),
    "LOANME": ("LOANME", "LOAN ME"),
    "MR BIZ CAPITAL": ("MRBIZCAP", "MR BIZ CAPITAL"),
    "NATIONAL FUNDING": ("NATIONAL FUNDING",),
    "ONDECK": ("ONDECK", "ON DECK", "ENOVA"),
    "PAR FUNDING": ("PAR FUNDING",),
    "PAYABILITY": ("PAYABILITY",),
    "PAYPAL WORKING CAPITAL": ("PAYPAL WORKING CAPITAL", "PAYPAL CAPITAL"),
    "QUANTUM CAPITAL": ("QUANTUM CAPITAL",),
    "QUARTERSPOT": ("QUARTERSPOT", "QUARTER SPOT"),
    "RAPID FINANCE": ("RAPID FINANCE", "RAPIDFINANCE", "SBFS"),
    "RELIANT FUNDING": ("RELIANT FUNDING", "RELIANT"),
    "RETRO ADVANCE": (
        "RETRO ADVANCE INC",
        "RETROADVANCEINC",
        "RETRO ADVANCE",
        "RETROADVANCE",
    ),
    "SHEAVES": ("SHEAVES", "3201961 ONTARRIO INC", "11302078 CANADA LTD"),
    "SHOPIFY CAPITAL": ("SHOPIFY CAPITAL", "SHOPIFY CREDIT"),
    "SQUARE CAPITAL": ("SQUARE CAPITAL", "SQ CAPITAL"),
    "TORRO": ("TORRO",),
    "VELOCITY CAPITAL": ("VELOCITY CAPITAL",),
    "YELLOWSTONE CAPITAL": ("YELLOWSTONE CAPITAL",),
    "2M7": ("2M7", "URAL LINK"),
}


POTENTIAL_LENDER_ALIASES: dict[str, tuple[str, ...]] = {
    "CMCA Finance": (
        "CMCA FINANCE",
        "CMCA FINANCE BUS",
        "CMCAFINANCE",
        "CMCA F1NANCE",
    ),
    "Lily Advance": ("LILY ADVANCE",),
    "SNAP Finance": ("SNAP FINANCE",),
}


VERIFIED_REVENUE_ALIASES: dict[str, tuple[str, ...]] = {
    "11-101 Signal R": ("11 101 SIGNAL R", "SIGNAL R"),
    "Amazon Marketplace": ("AMAZON MARKETPLACE PAYOUT", "AMAZON SELLER PAYOUT"),
    "DoorDash": ("DOORDASH PAYOUT", "DOORDASH SETTLEMENT"),
    "Etsy": ("ETSY PAYOUT", "ETSY SETTLEMENT"),
    "Grubhub": ("GRUBHUB PAYOUT", "GRUBHUB SETTLEMENT"),
    "Shopify Payments": ("SHOPIFY PAYMENTS", "SHOPIFY PAYOUT"),
    "SkipTheDishes": ("SKIPTHEDISHES", "SKIP THE DISHES"),
    "Square": ("SQUARE SETTLEMENT", "SQUARE PAYOUT", "SQ SETTLEMENT"),
    "Stripe": ("STRIPE PAYOUT", "STRIPE SETTLEMENT"),
    "Toast": ("TOAST SETTLEMENT", "TOAST PAYOUT"),
    "Uber Eats": ("UBER EATS PAYOUT", "UBEREATS PAYOUT"),
}


INSURANCE_PROVIDER_ALIASES: dict[str, tuple[str, ...]] = {
    "Co-operators": (
        "CO OPERATORS",
        "COOPERATORS",
        "THE CO OPERATORS",
        "C0 OPERATORS",
        "C0OPERATORS",
        "CO OPERAT0RS",
        "C0 OPERAT0RS",
    ),
    "Intact Insurance": ("INTACT INSURANCE", "INTACT"),
    "Aviva": ("AVIVA INSURANCE", "AVIVA"),
    "Wawanesa": ("WAWANESA INSURANCE", "WAWANESA"),
    "TD Insurance": ("TD INSURANCE", "TD GENERAL INSURANCE"),
    "RBC Insurance": ("RBC INSURANCE", "ROYAL BANK INSURANCE"),
    "Desjardins Insurance": ("DESJARDINS INSURANCE", "DESJARDINS ASSURANCES"),
    "Progressive": (
        "PROGRESSIVE INSURANCE",
        "PROGRESSIVE CASUALTY",
        "PROGRESSIVE INS",
        "ASI PROGRESSIVE",
    ),
    "State Farm": ("STATE FARM INSURANCE", "STATE FARM"),
    "Allstate": ("ALLSTATE INSURANCE", "ALLSTATE"),
    "GEICO": ("GEICO INSURANCE", "GEICO"),
    "Liberty Mutual": ("LIBERTY MUTUAL INSURANCE", "LIBERTY MUTUAL"),
    "Travelers": ("TRAVELERS INSURANCE", "TRAVELERS INDEMNITY"),
    "The Hartford": ("THE HARTFORD INSURANCE", "HARTFORD INSURANCE"),
    "Chubb": ("CHUBB INSURANCE", "CHUBB"),
    "Zurich": ("ZURICH INSURANCE",),
    "Blue Cross Blue Shield": ("BLUE CROSS BLUE SHIELD", "BCBSM", "BCBS"),
    "Certas Insurance": ("CERTAS H AND A INS", "CERTAS INSURANCE", "CERTAS"),
    "Erie Insurance": ("ERIE INSURANCE",),
    "First Insurance": ("FIRST INSURANCE",),
    "HUB International": ("HUBINTERNATIONAL INSURANCE", "HUB INTERNATIONAL INSURANCE"),
    "Kingstone Insurance": ("KINGSTONE INSURANCE",),
    "Thimble Insurance": ("THIMBLE INSURANCE",),
}


LEASE_PROVIDER_ALIASES: dict[str, tuple[str, ...]] = {
    "Balboa Capital": ("BALBOA CAPITAL", "BALBOA"),
    "Econolease": ("VLFC ECONOLEASE", "VLFC ECONO LEASE", "ECONOLEASE"),
    "Clover Equipment": (
        "CLOVER EQUIPMENT RENT",
        "CLOVER EQUIPMENT RENTAL",
        "CLOVER EQUIPMENT LEASE",
    ),
    "De Lage Landen": ("DE LAGE LANDEN", "DELAGELANDEN"),
    "Navitas Credit Corp": ("NAVITAS CREDIT CORP", "NAVITAS CREDIT C", "NAVITAS"),
    "NMEF": ("NMEF 2023 A", "NMEF FUNDING", "NMEF"),
    "Progressive Leasing": ("PROGRESSIVE LEASING",),
    "SmartPay": ("SMARTPAY SOL", "SMARTPAY"),
}


# Reserved for transaction codes whose meaning is specific to an institution.
# Global aliases belong in ``CONFIRMED_LENDER_ALIASES``.
BANK_SPECIFIC_LENDER_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {}
