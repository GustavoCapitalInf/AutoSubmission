"""Non-sale purpose, trade names, gambling, legal settlement, progress draws."""
from __future__ import annotations

import re
from collections import Counter
from typing import Sequence

from analysis.classification.counter_debit_reading import _payer_key
from analysis.classification_registry import OWNER_MONEY_PLATFORMS
from analysis.descriptor.credit_words import _HCCLAIMPMT, _PUBLIC_PAYER_NON_SALE_WORDS, _TREASURY_BOILERPLATE
from analysis.descriptor.lexical import _before_receiver
from analysis.descriptor.payer import payer_region
from analysis.descriptor.rails import _matches_any, _without_receiver_value
from analysis.descriptor.words import _SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS
from analysis.flag_groups import FINANCING_STATES
from analysis.payee_matcher import match_known_payee
from analysis.true_revenue.channel import (
    _channel,
    _counterparty_tokens,
    _named_currency_company,
    _transfer_counterparty_words,
    _transfer_row,
    _without_currency_conversion,
)
from analysis.true_revenue.financing_roots import _accounts_payable_wording
from analysis.true_revenue.hold_text import (
    _hold_text,
    _layout_entry,
    _non_sale_reading,
    _payer_name_proper,
    _prints_payer_name_field,
    _public_named,
    _title_purpose_text,
)
from analysis.true_revenue.holder_names import _without_holder_name
from analysis.true_revenue.payroll import _premium_coded
from analysis.true_revenue.public_payers import government_grant, healthcare_payer, public_region
from analysis.true_revenue.sender import _p2p_sender_region, _statement_bank_before_conversion
from analysis.true_revenue.trust import _held_personal_trust
from analysis.true_revenue.words import (
    _BANK_OR_TITLE_SENDER,
    _CLAIM_WORD,
    _CURRENCY_CONVERSION,
    _DISBURSEMENT_ACCOUNT,
    _DISBURSEMENT_KEEP,
    _DISBURSEMENT_WORD,
    _FINANCING_ROOT,
    _INSURER_NAME,
    _INVESTMENT_PURPOSE,
    _NOT_A_NAME_ALONE,
    _PREMIUM_CODED,
    _TITLE_FEE_WORDING,
    _TITLE_FIRM,
    _TRUST_LAWYER_WORDS,
)
from analysis.true_revenue.zelle import zelle_deposit


#: §8.1: a non-sale purpose. OWNER is no owner money in the ordering platform's name OWNER COM, and neither OWNER nor
#: OWNERS in an owners' or homeowners' association's name ('<NAME> OWNERS ASSOC', cut to 'OWNERS A' by a
#: sixteen-character originator field); the other words read only as a purpose (_non_sale_reading).
_NON_SALE_PURPOSE = re.compile(
    r"(?<![A-Z])(?:INVEST\w*|DISTRIB(?!UTORS?\b|UTING\b)\w*|DIVIDENDS?\b|EQUITY\b|CONTRIB\w*|SHAREHOLDER\w*"
    r"|OWNER\b(?! OP\b| OPERATORS?\b| COM\b| ASS(?:OC|N)\w*)"
    r"|OWNERS\b(?! OP\b| OPERATORS?\b| ASS(?:OC|N)\w*| AS\b| A\b)"
    r"|STOCK\b|INTERCO\w*|INTER COMPANY\b|DUE FROM\b|SWEEP\b|ZERO BAL\w*"
    r"|REPAY\w*|PRINCIPAL\b|PAYOFF\b|PROMISSORY\b|CONVERTIBLE\b|TRANCHE\b|DRAWS?\b|DRAWDOWNS?\b"
    r"|DISBURS\w*"
    r"|ESCROW\b|EARNEST\b|SECURITY DEPOSIT\b|DEPOSIT BACK\b|SURPLUS\b"
    r"|GRANTS?\b|DONATION\w*|GIFT\b(?! CARD\b)|COURT\b|JUDGMENT\b"
    r"|REBATES?\b|REIMB\w*|INTEREST\b|REWARDS?\b|CASH ?BACK\b"
    r"|RFND\w*|REFND\w*)"
    r"|\bZBA\b|[A-Z]*REFUND\w*"
)
#: A retirement account's or plan's disbursement (an IRA, a Roth, a 401(k) or 403(b) plan, a pension, a retirement or
#: annuity payer) is the owner's own money or personal income, never an ordinary payer's payout: read on the row's
#: hold text (the payer region stops at a digit, 'SAMPLE 401K PLAN' reading 'SAMPLE'), it keeps the disbursement's
#: hold however often it repeats (_disbursing_payer).
_RETIREMENT_ACCOUNT = re.compile(r"(?<![A-Z])(?:IRA|ROTH|401 ?K|403 ?B|PENSION\w*|RETIRE\w*|ANNUIT\w*)\b")
#: §8.1 non_sale_purpose: an owner-shaped payer, whose disbursement is owner money and never a payout: a holding
#: company, a partnership (PARTNERS, PARTNERSHIP, LP, LLP, LLLP), a venture, a family office, a trust or an estate
#: (never REAL ESTATE, a broker's name).
_OWNER_SHAPED_PAYER = re.compile(
    r"(?<![A-Z])(?:HOLDINGS?|PARTNERS|PARTNERSHIP|VENTURES?|FAMILY|TRUST)\b|(?<![A-Z])(?<!REAL )ESTATES?\b"
    r"|\b(?:LP|LLP|LLLP)\b"
)
#: §8.1 non_sale_purpose (the MCA principle, standard G3): a gambling or prediction-market payout is no money the
#: business earned from its operations, held for review (the owner may make it non_revenue). Read on the row before its
#: receiver fields: the sportsbooks', casinos' and prediction markets' names, each public (DraftKings and its
#: Massachusetts entity Crown <state> Gaming, FanDuel, BetMGM, Caesars Sportsbook, Fanatics' betting forms, ESPN BET,
#: bet365, BetRivers, PrizePicks, Underdog's fantasy and sports forms, Kalshi, Polymarket, the Chumba and Pulsz social
#: casinos), and a LOTTERY PRIZE. A bare FANATICS or UNDERDOG is a retailer's or any business's name, and CAESARS alone
#: the casino company paying its vendors. And the licensed sportsbooks the list missed, each public: Hard Rock Digital
#: (Hard Rock Bet, glued or spaced), Greenwood Racing's BetParx, Bally's Corporation's Bally Bet, PointsBet, Golden
#: Nugget Online Gaming and the Fliff social sportsbook. JACKPOT and WINNINGS left the list: they hold beside a gambling
#: word or outside a trade name (_GAMBLING_NAME_WORDS).
_GAMBLING_PAYOUT = re.compile(
    r"(?<![A-Z])(?:DRAFT ?KINGS|CROWN (?:[A-Z]{2} )?GAMING|FAN ?DUEL|BET ?MGM|CAESARS SPORTSBOOK"
    r"|FANATICS (?:SPORTSBOOK|BETTING|BET|GAMING|CASINO)|ESPN ?BET|BET ?365|BET ?RIVERS|PRIZE ?PICKS"
    r"|UNDERDOG (?:FANTASY|SPORTS)|KALSHI|POLYMARKET|CHUMBA|PULSZ|LOTTERY PRIZES?"
    r"|HARD ?ROCK ?(?:BET|DIGITAL)|BET ?PARX|BALLY ?BET|POINTS ?BET|GOLDEN NUGGET ONLINE|FLIFF)\b"
)
#: A casino's JACKPOT and WINNINGS, which hold beside a gambling word on the row (_GAMBLING_CONTEXT) or anywhere but
#: a customer's trade name (_trade_name: 'JACKPOT DIGITAL INC', a memo's 'JACKPOT CANDLES').
_GAMBLING_NAME_WORDS = re.compile(r"(?<![A-Z])(?:JACKPOT|WINNINGS)\b")
_GAMBLING_CONTEXT = re.compile(
    r"(?<![A-Z])(?:CASINOS?|GAMING|SLOTS?|LOTTERY|POKER|BINGO|RACEWAY|RACETRACK|RACING|SPORTSBOOK|BETTING)\b"
)
#: A lottery's prize (LOTTERY and a prize word anywhere on the row: '<STATE> LOTTERY DES:PRIZE PMT'), unless the entry is
#: the lottery's settlement with its retailer (a retailer word read on the entry, never on the agency's name: 'LOTTERY
#: COMMISSION' is many states' agency); and a sportsbook's, a casino's or an online gaming payer's withdrawal or payout
#: (the payer before the entry label, the word in the entry), which a brand list can never complete (sportsbooks' payouts
#: also come through processors).
_LOTTERY_WORD = re.compile(r"(?<![A-Z])LOTTERY\b")
_LOTTERY_PRIZE_WORD = re.compile(r"(?<![A-Z])(?:PRIZES?|WINNINGS?|JACKPOTS?)\b")
_LOTTERY_RETAILER_WORDING = re.compile(r"(?<![A-Z])(?:SETTLEMENT|SETTLMT|SWEEP|COMMISSIONS?|RETAILER)\b")
#: Many states' lottery agency is a LOTTERY COMMISSION; on a row that prints no entry field its name supplies no retailer
#: word, so the agency's prize ('<STATE> LOTTERY COMMISSION PRIZE PAYMENT') holds as it does on Bank of America's and
#: Chase's layouts.
_LOTTERY_AGENCY_NAME = re.compile(r"(?<![A-Z])LOTTERY COMMISSION\b")
_BETTING_PAYER = re.compile(r"(?<![A-Z])(?:SPORTS ?BOOK|CASINO|BETTING|ONLINE GAMING)\b")
_BETTING_WITHDRAWAL = re.compile(r"(?<![A-Z])(?:WITHDRAWALS?|WITHDRAW|WDRL|PAYOUTS?|CASH ?OUT)\b")
#: The entry labels the payer before them is read up to (Bank of America's DES, Chase's CO ENTRY DESCR).
_ENTRY_LABEL = re.compile(r"\bDES\b|\bCO (?:ENTRY )?DESCR\b")
#: A gambling payer, a claims administrator or a law firm paying a vendor's invoice from its payables pays its
#: vendor (§7.5's accounts-payable wording, _accounts_payable_wording, or these words), and a lottery's
#: settlement with its retailer (standard G4: the store sells tickets and cashes prizes) is no prize.
_VENDOR_PAYMENT_WORDING = re.compile(r"(?<![A-Z])(?:VENDORS?|INVOICES?|PAYABLES?)\b|\bINV\b|(?<![A-Z])INV ?\d")
#: §8.1 non_sale_purpose (the MCA principle: a legal windfall is no operating earning, standard G): a lawsuit's, a class
#: action's or a claims administrator's settlement, held for review (a law firm or a contractor may earn such money).
#: Read on the row before its receiver fields: SETTLEMENT ADMIN..., and the claims administrators' names, each public
#: (JND Legal Administration, KCC (only with LLC, CLASS or SETTLEMENT after it: three letters are many companies'
#: initials), Angeion, Simpluris, Rust Consulting, Kroll Settlement Administration, A.B. Data). A bare SETTLEMENT is a
#: processor's, a carrier's or an operating settlement and stays counted, never verified (§8.6). A lawyer's or a client
#: trust account's payer (IOLTA, ESQ, LAW, ATTORNEY: _TRUST_LAWYER_WORDS on the payer region) paying SETTLEMENT PROCEEDS
#: or FUNDS is held too. LAWSUIT, LITIGAT..., CLASS ACTION, DATA BREACH and the administrators Epiq and Verita (whose
#: names are other businesses' too) hold beside a settlement, claim or award word on the row (_LEGAL_CONTEXT) or
#: anywhere but a customer's trade name (_trade_name: '<NAME> LITIGATION SUPPORT LLC', 'VERITA HEALTH LLC'; never 'EPIQ
#: SYSTEMS INC' or 'VERITA GLOBAL', whose other words are _LEGAL_NAME_KEEP's). A claims administrator's or a
#: restructuring unit's form words (SERVICES, SOLUTIONS, RESTRUCTURING, GROUP) are keep words too ('EPIQ CORPORATE
#: RESTRUCTURING LLC', 'CLASS ACTION SERVICES LLC'); a name word of the payer's own beside them still reads as a trade
#: name (a recorded residual, §20). The settlement words are the classifier's own settlement spellings
#: (_SETTLEMENT_CREDIT's SETTLE..., SETTLMT, SETLMT, STLMT and STLMNT, kept in step by a test) and SETL, so 'DES:CLASS
#: ACTION STLMT' holds by context as 'DES:CLASS ACTION SETTLEMENT' does.
_LEGAL_SETTLEMENT = re.compile(
    r"(?<![A-Z])(?:SETTLEMENT ADMIN\w*|JND LEGAL|ANGEION|SIMPLURIS|RUST CONSULTING|KROLL SETTLEMENT|A B DATA)\b"
    r"|\bKCC(?= (?:LLC|CLASS|SETTLEMENT)\b)"
)
_LEGAL_SETTLEMENT_SPELLINGS = r"SETTLE\w*|SETTLMT|SETLMT|STLMT|STLMNT|SETL"
_LEGAL_NAME_WORDS = re.compile(r"(?<![A-Z])(?:LAWSUITS?|LITIGAT\w*|CLASS ACTION|DATA BREACH|EPIQ|VERITA)\b")
_LEGAL_CONTEXT = re.compile(rf"(?<![A-Z])(?:{_LEGAL_SETTLEMENT_SPELLINGS}|CLAIMS?|AWARDS?)\b")
_LEGAL_NAME_KEEP = re.compile(
    rf"(?<![A-Z])(?:{_LEGAL_SETTLEMENT_SPELLINGS}|CLAIMS?|AWARDS?|FUNDS?|ADMIN\w*|SYSTEMS|GLOBAL|CORPORATE"
    r"|SERVICES|SOLUTIONS|RESTRUCTURING|GROUP)\b"
)
_LAWYER_SETTLEMENT_PROCEEDS = re.compile(r"(?<![A-Z])SETTLEMENT (?:PROCEEDS|FUNDS?)\b")
#: §8.1 non_sale_purpose: DISB, the abbreviation of a disbursement, on an owner-shaped payer (_OWNER_SHAPED_PAYER:
#: '<NAME> PARTNERS LP DES:PARTNER DISB') is owner money, as its DISBURSEMENT is. An ordinary payer's 'CASH DISB' is
#: its payment to a vendor and keeps its reading. So is an owner-shaped payer's accounts-payable or vendor
#: disbursement (_VENDOR_DISB, or §7.5's accounts-payable or a vendor or invoice word: _vendor_payment), its payment
#: of a vendor's invoice.
_DISB_ABBREVIATION = re.compile(r"(?<![A-Z])DISB(?![A-Z])")
_VENDOR_DISB = re.compile(r"(?<![A-Z])(?:AP|A P|ACCTS? PAY\w*|VENDOR|VNDR) DISB(?![A-Z])")
#: A word a hold reads is a customer's trade name, never the payer's or the purpose's, when it sits in a payer region
#: that prints a company form (_TRADE_NAME_FORM) and a name word of its own besides the reader's words, the forms, the
#: fillers (_TRADE_NAME_NOT_A_NAME) and the reader's keep words, or on the payment's purpose (_title_purpose_text)
#: with a name word right after it (never a form, a keep word or a field's word, _TRADE_NAME_NOT_AFTER). A name word
#: is two letters or more, no digit. Read by _trade_name.
_TRADE_NAME_FORM = re.compile(r"\b(?:LLC|INC|CORP|CO|COMPANY|LTD|PLLC|LLP|LP|PLC)\b")
_TRADE_NAME_NOT_A_NAME = frozenset({
    "LLC", "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLLC", "LLP", "LP", "PLC",
    "THE", "OF", "AND", "FOR", "YOUR", "US", "USA", "NA", "DBA", "FBO", "HQ",
})
_TRADE_NAME_NOT_AFTER = frozenset({"CONF", "REF", "ID", "TRN", "PMT", "PAYMENT", "PAYOUT"})
_TRADE_NAME_WORD = re.compile(r"[A-Z]{2,}")
#: A word right after a hold word on the purpose that names the purpose, never a trade name: a win, a prize or a
#: bonus; a withdrawal, a cash-out, a transfer, proceeds, a recovery, money, funds, a check, a distribution, a
#: disbursement, a deposit, a refund or a reimbursement; a payment or a payout; the legal reader's settlement, claim
#: and award words; a share, a sale, a balance or an account; a coin; a preposition, a possessive or a time word ('FOR
#: JACKPOT WIN', 'OBI LAWSUIT PROCEEDS', 'DES:KRAKEN WITHDRAWAL', 'FOR WINNINGS FROM BET', 'FOR WINNINGS LAST NIGHT'),
#: so the occurrence before it holds. Read whole (fullmatch) by _trade_name's purpose arm only; a name word ('FOR
#: JACKPOT CANDLES', 'DES:LITIGATION SUPPORT') keeps the trade-name reading. And the legal reader's settlement
#: spellings (_LEGAL_SETTLEMENT_SPELLINGS), the payment cuts the statements print (PYMNT, PMNT, PAYMNT, PAYMT, PYMMT
#: and their plurals, PAYMEN, PAYME, PAYM, PYM), a handpay, a distribution's, proceeds' or a compensation's cut (DIST,
#: DISTR, PROC, PRCDS, COMP), a judgment, a redemption, a bet or a wager, a fantasy contest, a pool, a lotto or a
#: raffle, and a rail, a currency or a staking reward ('OBI KRAKEN USD', 'DES:KRAKEN ACH'). The list stays closed: a
#: row only this arm spares counts and never proves (purpose_trade_name).
_TRADE_NAME_PURPOSE_WORD = re.compile(
    r"WINS?|WON|WINNERS?|WINNINGS?|PRIZES?|BONUS\w*|JACKPOTS?"
    r"|WITHDRAW\w*|WDRLS?|WD|CASH\w*|TRANSF\w*|TRNSFR|XFE?RS?|TFR|PROCEEDS?|RECOVER\w*|MONEY|MONIES|FUNDS?|FUNDING"
    r"|CHECKS?|CHEQUES?|CHK|DISTRIB\w*|DISBURS\w*|DISB|DEPOSITS?|DEP|REFUNDS?|REIMB\w*|REBATES?"
    r"|PAYMENTS?|PAYOUTS?|PAY|PAID|PMTS?|PYMTS?|CLAIMS?|AWARDS?"
    rf"|{_LEGAL_SETTLEMENT_SPELLINGS}"
    r"|PYMNTS?|PMNTS?|PAYMNTS?|PAYMTS?|PYMMTS?|PAYMENS?|PAYME|PAYM|PYM"
    r"|HANDPAYS?|DISTR?|DISTRO|PROC|PRCDS|COMP|COMPENSAT\w*|JUDG\w*|REDEMPT\w*|REDEEM\w*"
    r"|BETS?|WAGER\w*|PARLAYS?|FANTASY|ODDS|GAMBL\w*|POOLS?|SUPERBOWL|LOTTO|RAFFLES?"
    r"|ACH|EFT|WIRE|USD|CAD|REWARDS?|STAK\w*"
    r"|SHARES?|SPLIT|SALES?|SOLD|BALANCE|ACCOUNTS?|ACCT|BTC|ETH|BITCOIN|USDC|USDT"
    r"|FROM|TO|IN|ON|AT|BY|WITH|MY|OUR|HIS|HER|THEIR|THIS|THAT|LAST|NEXT|TODAY|TONIGHT|YESTERDAY"
)
#: The owner-money platforms whose names are other businesses' too (a robotics maker, a cleaner, a services firm):
#: KRAKEN, UPHOLD and PAXOS hold, when no other platform is named, only outside a customer's trade name (_trade_name;
#: never 'UPHOLD HQ INC' or 'PAXOS TRUST CO', whose other words are _PLATFORM_NAME_KEEP's).
_PLATFORM_NAME_WORDS = re.compile(r"(?<![A-Z])(?:KRAKEN|UPHOLD|PAXOS)\b")
_PLATFORM_NAME_KEEP = re.compile(
    r"(?<![A-Z])(?:TRUST|TECHNOLOGY|GLOBAL|DIGITAL|EXCHANGE|PAYWARD|INTERACTIVE|CRYPTO)\b"
)
#: §8.1: a healthcare payer's member or premium credit. A premium word the entry field prints on a row
#: _premium_coded reads is no hold here; that row is counted and flagged as a named payer Q5 and Q6 refuse.
_HEALTHCARE_MEMBER_WORDS = re.compile(
    r"(?<![A-Z])(?:REIMB\w*|MEMBER\b|SUBSCRIBER\b|PREMIUM\b)|\bMBR\b"
)
#: §7.5, the standing rule: brokerage, investing and crypto-exchange platforms (the registry's OWNER_MONEY_PLATFORMS,
#: §7.0: a table that names companies lives there). A credit from one is the owner's own money coming back (owner
#: money never becomes revenue): held as non_sale_purpose. The classifier's consumer savings and investing
#: originators (_SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS) are read too.
_OWNER_MONEY_PLATFORMS = re.compile(OWNER_MONEY_PLATFORMS)
#: Q11 (a): DRAW or DRAWS as _NON_SALE_PURPOSE reads it (DRAWDOWN keeps its financing reading).
_DRAW_WORD = re.compile(r"(?<![A-Z])DRAWS?\b")
#: Q11 (a): a builder named as the payer: a builder, a homebuilder, a construction firm or a contractor (BUILD alone is
#: a builder's name word, '<NAME> BUILD GROUP INC'; CONST and CONSTR are the cut spellings a sixteen-character
#: originator field prints). Never a builders' supplier, exchange, association or insurer ('BUILDERS FIRSTSOURCE',
#: 'CONTRACTORS INSURANCE'). A homebuilder named HOMES too, never a nursing, funeral, care, group, foster, senior or
#: retirement home, a mobile or manufactured home seller, nor HOMES FOR SALE or FOR RENT. BUILDING is no builder (a
#: building's owner, a building-supply or building-maintenance firm, a building-and-loan association); DEVELOPMENT,
#: DEVELOPERS and PROPERTIES are deliberately not builder words (§17.1, the owner's follow-up on a developer's draw).
_BUILDER_PAYER = re.compile(
    r"(?<![A-Z])(?:BUILDERS?|BUILD|HOMEBUILDERS?|HOMEBUILDING|CONSTRUCTION|CONSTRUCTORS?|CONSTR|CONST|CONTRACTORS?"
    r"|CONTRACTING)\b"
    r"(?! (?:SUPPLY|SUPPLIES|FIRSTSOURCE|FIRST SOURCE|HARDWARE|EXCHANGE|ASSOCIATION|ASSN|MUTUAL|INSURANCE|RISK)\b)"
    r"|(?<![A-Z])(?<!NURSING )(?<!FUNERAL )(?<!MOBILE )(?<!MANUFACTURED )(?<!CARE )(?<!GROUP )(?<!FOSTER )"
    r"(?<!SENIOR )(?<!RETIREMENT )HOMES\b(?! FOR (?:SALE|RENT)\b)"
)
#: A draw's purpose phrase, CONSTRUCTION, CONSTR or CONST directly followed by DRAW or DRAWS. On a row that prints no
#: payer-name field the payer region holds the entry words ('<NAME> CONST DRAW', TD's whole 'CONSTRUCTION DRAW'), so
#: the phrase is the entry's purpose, never the payer's builder word (_label_less_builder_word). BUILD too ('<NAME>
#: BUILD DRAW'), so a root-less lender's entry BUILD DRAW names no builder either.
_DRAW_PURPOSE_PHRASE = re.compile(r"(?<![A-Z])(?:CONSTRUCTION|CONSTR|CONST|BUILD) DRAWS?\b")
#: Q11 (a): a loan's, a credit line's, a mortgage's, an escrow's or a title's draw, an owner's, member's, partner's or
#: shareholder's draw, a personal, line, credit, advance, capital, equity or cash draw, and a draw on a line, a LOC, a
#: credit facility or an account: the business's own loan or money, never a builder's progress draw. Nor a commission
#: draw (COMM, COMMISSION or COMMISSIONS DRAW), a salesperson's advance against its commissions.
_OWN_LOAN_DRAW = re.compile(
    r"(?<![A-Z])(?:LOANS?|LOC|HELOC|LINE OF CREDIT|CREDIT LINE|MORTGAGE|MTG|ESCROW|TITLE)\b"
    r"|(?<![A-Z])(?:OWNERS?|MEMBERS?|PARTNERS?|SHAREHOLDERS?|PERSONAL|LINE|CREDIT|ADVANCE|CAPITAL|EQUITY|CASH|COMM"
    r"|COMMISSIONS?) DRAWS?\b"
    r"|(?<![A-Z])DRAWS? ON (?:THE |A )?(?:LINE|LOC|CREDIT|FACILITY|ACCOUNT)\b"
)
#: Q11 (a), a realty firm's words on the payer region (REALTY, REALTOR(S), REAL ESTATE): a realty firm named '<NAME>
#: HOMES REALTY' or '<NAME> BUILDERS REALTY' is no builder (the brief's non-builders), so its DRAW keeps today's
#: non-sale hold.
_REALTY_PAYER = re.compile(r"(?<![A-Z])(?:REALTY|REALTORS?|REAL ESTATE)\b")


def _vendor_payment(text: str, row: str) -> bool:
    """The row is a payer's payment of a vendor's invoice from its payables: §7.5's accounts-payable wording
    (_accounts_payable_wording) or a vendor, invoice or payables word (_VENDOR_PAYMENT_WORDING)."""
    return _accounts_payable_wording(text) or _VENDOR_PAYMENT_WORDING.search(row) is not None


def _trade_name_word(word: str, keep: re.Pattern[str], also: frozenset[str] = frozenset()) -> bool:
    """A name word of a customer's trade name: two letters or more and no digit (_TRADE_NAME_WORD), never a
    company form or a filler (_TRADE_NAME_NOT_A_NAME), one of `also`, or a word of the reader's `keep`."""
    return (
        _TRADE_NAME_WORD.fullmatch(word) is not None and word not in _TRADE_NAME_NOT_A_NAME and word not in also
        and keep.fullmatch(word) is None
    )


def _trade_name(
    text: str, row: str, region: str, words: re.Pattern[str], keep: re.Pattern[str], *, purpose_arm: bool = True,
) -> bool:
    """Every occurrence of `words` on `row` (a hold's text) is a customer's trade name, never the payer's or the
    purpose's: (a) it sits in `region`, the payer region, which prints a company form (_TRADE_NAME_FORM) and still holds
    a name word (_trade_name_word) once `words`, the forms, the fillers and `keep` are removed; or (b) it sits on the
    payment's purpose (_title_purpose_text) with a name word right after it (never a form, a filler, a `keep` word,
    another of `words` or a field's word, _TRADE_NAME_NOT_AFTER; nor a word that names the purpose,
    _TRADE_NAME_PURPOSE_WORD). An occurrence anywhere else, or one the row no longer prints as read, is no trade name,
    so the hold that reads it holds. `purpose_arm` False reads (a) alone, which purpose_trade_name compares with the
    full reading."""
    rest = row
    if region and _TRADE_NAME_FORM.search(region) and any(
        _trade_name_word(word, keep) for word in words.sub(" ", region).split()
    ):
        rest = rest.replace(region, " ")
    purpose = _title_purpose_text(text) if purpose_arm else ""
    for found in words.finditer(purpose):
        after = re.match(r" (\S+)", purpose[found.end():])
        if after is None or words.fullmatch(after.group(1)) is not None:
            continue
        if (
            _trade_name_word(after.group(1), keep, _TRADE_NAME_NOT_AFTER)
            and _TRADE_NAME_PURPOSE_WORD.fullmatch(after.group(1)) is None
        ):
            rest = rest.replace(f"{found.group(0)} {after.group(1)}", f" {after.group(1)}", 1)
    return words.search(rest) is None


def gambling_payout(text: str, row: str, *, purpose_arm: bool = True) -> bool:
    """§8.1 non_sale_purpose: a sportsbook's, a casino's, a lottery's or a prediction market's payout on `row` (the hold
    text without the holder's name), read in this order: never the payer's payment of a vendor (_vendor_payment), nor a
    lottery's settlement with its retailer (LOTTERY on the row and a retailer word, _LOTTERY_RETAILER_WORDING, on the
    entry the layout prints, _layout_entry, or on the row where it prints none: never on the agency's name; on a row with
    no entry, nor its LOTTERY COMMISSION, _LOTTERY_AGENCY_NAME); then a listed payer (_GAMBLING_PAYOUT); a lottery's
    prize (LOTTERY and a prize word anywhere on the row); a sportsbook's, a casino's or an online gaming payer
    (_BETTING_PAYER on the row before its entry label) whose entry, or row, prints a withdrawal or payout
    (_BETTING_WITHDRAWAL); and a JACKPOT or WINNINGS beside a gambling word (_GAMBLING_CONTEXT) or outside a customer's
    trade name."""
    if _vendor_payment(text, row):
        return False
    entry = _layout_entry(text)
    scope = entry if entry.strip() else row
    lottery = _LOTTERY_WORD.search(row) is not None
    retailer_scope = entry if entry.strip() else _LOTTERY_AGENCY_NAME.sub("LOTTERY", row, count=1)
    if lottery and _LOTTERY_RETAILER_WORDING.search(retailer_scope):
        return False
    if _GAMBLING_PAYOUT.search(row) is not None:
        return True
    if lottery and _LOTTERY_PRIZE_WORD.search(row) is not None:
        return True
    if _BETTING_PAYER.search(_ENTRY_LABEL.split(row, maxsplit=1)[0]) and _BETTING_WITHDRAWAL.search(scope):
        return True
    if _GAMBLING_NAME_WORDS.search(row) is None:
        return False
    return _GAMBLING_CONTEXT.search(row) is not None or not _trade_name(
        text, row, payer_region(text), _GAMBLING_NAME_WORDS, _GAMBLING_CONTEXT, purpose_arm=purpose_arm
    )


def legal_settlement(text: str, row: str, region: str, *, purpose_arm: bool = True) -> bool:
    """§8.1 non_sale_purpose: a claims administrator's settlement (_LEGAL_SETTLEMENT) on `row`, a lawsuit's, a class
    action's, a data breach's or Epiq's or Verita's (_LEGAL_NAME_WORDS) beside a settlement, claim or
    award word (_LEGAL_CONTEXT) or outside a customer's trade name (_trade_name, keeping _LEGAL_NAME_KEEP's words), or a
    lawyer's or client trust account's payer (_TRUST_LAWYER_WORDS on `region`, the payer region) paying settlement
    proceeds or funds (_LAWYER_SETTLEMENT_PROCEEDS); never a payer's payment of a vendor (_vendor_payment). The
    settlement words are the classifier's settlement spellings (_LEGAL_SETTLEMENT_SPELLINGS), and `purpose_arm` is
    _trade_name's (purpose_trade_name)."""
    named = _LEGAL_SETTLEMENT.search(row) is not None or (
        _LEGAL_NAME_WORDS.search(row) is not None and (
            _LEGAL_CONTEXT.search(row) is not None
            or not _trade_name(text, row, region, _LEGAL_NAME_WORDS, _LEGAL_NAME_KEEP, purpose_arm=purpose_arm)
        )
    )
    if not named and not (
        region and _TRUST_LAWYER_WORDS.search(region) and _LAWYER_SETTLEMENT_PROCEEDS.search(row)
    ):
        return False
    return not _vendor_payment(text, row)


def owner_disbursement(text: str, row: str, region: str) -> bool:
    """§8.1 non_sale_purpose: an owner-shaped payer (_OWNER_SHAPED_PAYER on the payer region) printing DISB, a
    disbursement's abbreviation (_DISB_ABBREVIATION), is owner money; never its accounts-payable or vendor disbursement
    (_VENDOR_DISB, or _vendor_payment)."""
    return (
        bool(region) and _OWNER_SHAPED_PAYER.search(region) is not None and _DISB_ABBREVIATION.search(row) is not None
        and not (_vendor_payment(text, row) or _VENDOR_DISB.search(row))
    )


def owner_money_platform(text: str, row: str, region: str, *, purpose_arm: bool = True) -> bool:
    """§7.5's standing rule, §8.1 non_sale_purpose: a brokerage, investing or crypto-exchange platform the registry
    names (_OWNER_MONEY_PLATFORMS) on `row` returns the owner's own money. Never a payer's payment of a vendor, and
    when the only platform the row names is KRAKEN, UPHOLD or PAXOS (_PLATFORM_NAME_WORDS), only outside a customer's
    trade name (_trade_name, keeping _PLATFORM_NAME_KEEP's words). A platform the row names by a name that is only the
    platform's is spared by §7.5's accounts-payable wording alone (_accounts_payable_wording, S4.2's exception for the
    investment words and its re-review's ruling: accounts-payable wording is the payer's vendor payment), never by a
    bare vendor, invoice or payables word; KRAKEN, UPHOLD or PAXOS alone, whose names are other businesses' too, takes
    the legal and gambling readers' vendor spare (_vendor_payment). The registry's table is unchanged. `purpose_arm` is
    _trade_name's (purpose_trade_name)."""
    if _OWNER_MONEY_PLATFORMS.search(row) is None or _accounts_payable_wording(text):
        return False
    if _OWNER_MONEY_PLATFORMS.search(_PLATFORM_NAME_WORDS.sub(" ", row)) is not None:
        return True
    if _vendor_payment(text, row):
        return False
    return not _trade_name(text, row, region, _PLATFORM_NAME_WORDS, _PLATFORM_NAME_KEEP, purpose_arm=purpose_arm)


def purpose_trade_name(text: str, row: str, region: str) -> bool:
    """§8.1, §8.6: a legal, gambling or owner-money reader (legal_settlement, gambling_payout, owner_money_platform)
    would hold `row` (the hold text the holds read) but for _trade_name's purpose arm, a name word right after the hold
    word on the purpose ('DES:LITIGATION SUPPORT', 'FOR JACKPOT CANDLES'). The purpose words (_TRADE_NAME_PURPOSE_WORD)
    are a closed list no statement's spelling can complete, so such a row counts and never proves
    (CreditFacts.refused_word): an unlisted purpose noun after a hold word is at worst counted and flagged. A row the
    payer region's trade name (arm (a)) or a vendor spare clears is no such row."""
    if not any(words.search(row) for words in (_GAMBLING_NAME_WORDS, _LEGAL_NAME_WORDS, _PLATFORM_NAME_WORDS)):
        return False
    return (
        (gambling_payout(text, row, purpose_arm=False) and not gambling_payout(text, row))
        or (legal_settlement(text, row, region, purpose_arm=False) and not legal_settlement(text, row, region))
        or (
            owner_money_platform(text, row, region, purpose_arm=False)
            and not owner_money_platform(text, row, region)
        )
    )


def construction_progress_draw(
    text: str, region: str, account_name: str | None = None, *, also: Sequence[str] = (),
    zelle_true_revenue: bool = False,
) -> bool:
    """§8.1, §8.10: a builder's progress draw, counted and flagged, never verified. True only when the payer region
    names a builder (_BUILDER_PAYER), the row prints no Zelle rail (Q3 excludes every Zelle deposit, zelle_deposit; in
    the counted reading, `zelle_true_revenue`, a builder's Zelle draw is read as any other rail's), the row (the hold
    text without the holder's names, as the holds read it: `account_name` and `also`) prints DRAW or DRAWS where §8.1
    reads the non-sale words (_non_sale_reading) once the payer's own name is removed, nothing reads as the business's
    own loan or money (_OWN_LOAN_DRAW: a loan's, a line's, an escrow's, an owner's, an equity draw, a draw on a line; a
    commission draw), and the payer is no bank, title, escrow, closing or settlement firm, owner-shaped payer or
    financing root (the earlier financing holds read those first). Nor a realty firm (_REALTY_PAYER: '<NAME> HOMES
    REALTY LLC').

    §2.1: the builder word is read on the payer region without the holder's names (`account_name` and `also`), so the
    holder's own builder word is never the payer's (Truist prints the receiver inside the region). On a row that prints
    no payer-name field (_prints_payer_name_field: Wells Fargo's, Citizens', TD Bank's, Huntington's and Truist's
    label-less layouts) the region holds the entry words too: the payer's builder word is the first that does not start
    a draw's purpose phrase (_label_less_builder_word: '<NAME> CONST DRAW' names no builder), and DRAW is read only
    after it or in such a phrase that starts the region (_label_less_draw_purpose: any other printed before it, 'QUICK
    DRAW CONST PAYMENT', is inside the payer's name). A row these refuse keeps its reading before the ruling, the
    non-sale hold of its DRAW, as its Bank of America DES twin does; on a row that prints a payer-name field the name
    field is the payer's and today's reading stands. Recorded residual (held, reviewable; 0 corpus rows): a builder
    named '<NAME> CONSTRUCTION', or by the cut spellings a sixteen-character originator field prints, '<NAME> CONST' or
    '<NAME> CONSTR', or '<NAME> BUILD', with no company form before a bare DRAW on a label-less row (the phrase cannot
    be told from the name). A builder's draw on Truist's entry-first layout ('CONST DRAW <NAME> BUILDERS INC ...')
    counts, the DRAW of the entry's purpose phrase read before the builder word (_label_less_draw_purpose); its recorded
    residual (counted; 0 corpus rows): a receiver the holder's names do not strip that prints a builder
    word lends it to a root-less payer's entry-first CONST DRAW. Only a phrase that starts the payer region is that
    entry, so a root-less lender's, a county's or a developer's '<NAME> CONST DRAW' followed by a later builder word in
    the region ('SAMPLE COUNTY CONST DRAW BUILDER PMT') names no builder and keeps its hold."""
    if not region or _REALTY_PAYER.search(region) or (not zelle_true_revenue and zelle_deposit(text)):
        return False
    named = _prints_payer_name_field(text)
    payer = _without_holder_name(region, account_name, also=also)
    builder = _BUILDER_PAYER.search(payer) if named else _label_less_builder_word(payer)
    if builder is None:
        return False
    row = _without_holder_name(_hold_text(text), account_name, also=also)
    if named:
        name = _payer_name_proper(text, region)
        purpose = row.replace(name, " ") if name else row
    else:
        purpose = _label_less_draw_purpose(row, payer, builder)
    if _DRAW_WORD.search(_non_sale_reading(text, purpose, region)) is None or _OWN_LOAN_DRAW.search(row):
        return False
    return not (
        _BANK_OR_TITLE_SENDER.search(region) or _TITLE_FIRM.search(region) or _OWNER_SHAPED_PAYER.search(region)
        or _FINANCING_ROOT.search(region)
    )


def _label_less_builder_word(payer: str) -> re.Match[str] | None:
    """The payer's builder word on a payer region that is no payer-name field (`payer`, read without the holder's
    names): the first _BUILDER_PAYER match that does not start a draw's purpose phrase; None when there is none
    ('FABRIKAM AMERICA CONST DRAW', 'SAMPLE COUNTY CONSTRUCTION DRAW', 'FABRIKAM AMERICA BUILD DRAW')."""
    for found in _BUILDER_PAYER.finditer(payer):
        if _DRAW_PURPOSE_PHRASE.match(payer, found.start()) is None:
            return found
    return None


def _label_less_draw_purpose(row: str, payer: str, builder: re.Match[str]) -> str:
    """Where a row that prints no payer-name field reads DRAW: the hold row (`row`, without the holder's names) from
    the end of the payer's builder word on (`builder`, a match on `payer`, the payer region without the holder's
    names), so a DRAW printed before the builder word is inside the payer's name. The builder word is found in the row
    through the region's words up to it; where the row does not print them as the region does, only the region's words
    after the builder word are read (a draw the row prints later stays unread, the conservative side). A draw's purpose
    phrase printed before the builder word (_DRAW_PURPOSE_PHRASE, which _label_less_builder_word skipped) is the
    entry's purpose, never the payer's name, so its DRAW is read too: Truist's entry-first 'CONST DRAW <NAME> BUILDERS
    INC <receiver> CUSTOMER ID' is a builder's draw, while 'QUICK DRAW CONST PAYMENT' prints no phrase and stays
    unread. Only a phrase that starts the payer region, the entry-first entry, is read; one printed after the payer's
    name ('FABRIKAM AMERICA CONST DRAW CONTRACTOR PMT', 'SAMPLE COUNTY CONST DRAW BUILDER PMT') is that root-less
    payer's own entry and lends no DRAW to a later builder word."""
    lead = payer[: builder.end()].strip()
    at = row.find(lead) if lead else -1
    after = row[at + len(lead):] if at >= 0 else payer[builder.end():]
    offset = len(payer) - len(payer.lstrip())
    first = _DRAW_PURPOSE_PHRASE.match(payer, offset)
    if first is not None and first.end() <= builder.start():
        return f"{first.group(0)} {after}"
    return after


def non_sale_purpose(
    text: str, region: str, *, bank: str | None = None, account_name: str | None = None, disbursing: bool = False,
    also: Sequence[str] = (), progress_draw: bool = False, insurer_work: bool = False,
) -> bool:
    """§8.1: a non-sale purpose, a public payer's refund or benefit, or a healthcare payer's member or premium credit.
    The investment words hold a row unless it prints accounts-payable wording (S4.2 fix measurement). A3 (precision
    sample): a title firm named on the payer region (_TITLE_FIRM: property-closing proceeds, an asset sale), on a wire
    or an ACH row alike, unless its purpose cites the holder's fee; and the holder's own currency conversion
    (_currency_conversion; `bank` is the statement's bank, whose own name names no payer).

    The row is read without the holder's own name runs (_without_holder_name: `account_name`), and the non-sale words
    only as a purpose (_non_sale_reading): never a street's name, a payer's name word (DISTRIB..., STOCK), a
    joint-stock company's form, the payer's own DISBURSEMENT ACCOUNT, or the recurring disbursement entry of an
    ordinary payer (`disbursing`: the statement pass's _recurring_disbursers). A personal trust's payment that cites
    the holder's service is no owner money.

    A gambling or prediction-market payout (gambling_payout), a legal settlement (legal_settlement) and an
    owner-shaped payer's DISB (owner_disbursement) are no sale either; a settlement or closing agent is a title firm
    (_TITLE_FIRM). Those readers, and the owner-money platforms (owner_money_platform), spare a customer's trade
    name, a vendor's payment and a processor's or a carrier's settlement services, in the same order.

    On a builder's progress draw (`progress_draw`, the pass's construction_progress_draw), DRAW is no non-sale word,
    inside the payer's name too; every other non-sale word and every later test still holds the row.

    On an insurer's credit pass 7 released as the business's work (`insurer_work`, INSURER_FOR_WORK_METHOD), CLAIM is no
    non-sale word: the release read the insurer's claim as paid for the business's work (a repair shop's, an agency's or a
    provider's claims); every other non-sale word still holds. Nor in the public-payer arm, so a listed carrier the
    release read before the government arm ('ALLSTATE COUNTY DES:CLAIM PMT', a Texas county mutual's cut that
    _PUBLIC_PAYER_NAME still reads as a county) is not held as a public payer's claim; the arm's other words still hold
    it."""
    row = _without_holder_name(_hold_text(text), account_name, also=also)
    claim_entry = _HCCLAIMPMT.search(text) is not None
    healthcare = healthcare_payer(region)
    reading = _non_sale_reading(text, row, region, disbursing=disbursing, bank=bank)
    if progress_draw:
        reading = _DRAW_WORD.sub(" ", reading)
    if _NON_SALE_PURPOSE.search(reading) is not None:
        return True
    # GOV: a government grant or subsidy.
    if government_grant(text):
        return True
    # A gambling payout, a legal settlement, an owner's DISB.
    if gambling_payout(text, row) or legal_settlement(text, row, region) or owner_disbursement(text, row, region):
        return True
    if (
        region and _TITLE_FIRM.search(region) is not None
        and _TITLE_FEE_WORDING.search(_title_purpose_text(text)) is None
    ):
        return True
    if _currency_conversion(text, bank=bank):
        return True
    if _held_personal_trust(text, region):
        return True
    if _INVESTMENT_PURPOSE.search(row) is not None and not _accounts_payable_wording(text):
        return True
    if (
        not insurer_work and _CLAIM_WORD.search(row) and not claim_entry
        and not (healthcare and re.search(r"(?<![A-Z])CLAIM PMT\b", row))
    ):
        return True
    public_words = _TREASURY_BOILERPLATE.sub(" ", text)
    if insurer_work:
        # The released insurer's CLAIM is no public payer's claim either.
        public_words = _CLAIM_WORD.sub(" ", public_words)
    if _public_named(public_region(text)) and _PUBLIC_PAYER_NON_SALE_WORDS.search(public_words):
        return True
    # A brokerage, investing or crypto-exchange platform returns the owner's own money (never a vendor's
    # payment or a customer's trade name, owner_money_platform).
    if owner_money_platform(text, row, region) or _matches_any(
        row, _SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS
    ):
        return True
    # On a row whose entry field _premium_coded reads, a premium word holds nothing (the row is counted and flagged
    # as a refused payer); a member, subscriber or reimbursement word still holds it.
    if healthcare and _premium_coded(text, region):
        row = _PREMIUM_CODED.sub(" ", row)
    return healthcare and _HEALTHCARE_MEMBER_WORDS.search(row) is not None


def _recurring_disbursers(texts: dict[int, str]) -> frozenset[tuple[str, ...]]:
    """§8.1 non_sale_purpose: the payer keys of the statement's ordinary payers (_disbursing_payer) whose disbursement
    entry prints on two or more credits (§5.2's repeats): a processor's or a platform's recurring payout ('PSP <phone>
    DISBURSMNT'). A one-off disbursement keeps its hold."""
    counts: Counter = Counter()
    for text in texts.values():
        if _DISBURSEMENT_WORD.search(_hold_text(text)) is None:
            continue
        region = payer_region(text)
        if region and _disbursing_payer(text, region):
            counts[_payer_key(region)] += 1
    return frozenset(key for key, count in counts.items() if key and count >= 2)


def _disbursing_payer(text: str, region: str) -> bool:
    """§8.1 non_sale_purpose: an ACH or EFT payer whose disbursement entry is its ordinary payout (a processor's 'PSP
    <phone> DISBURSMNT', an association's 'DISBURSEMENT'): the row is on the ACH or EFT channel and its payer region
    names a payer that reads as none of a lender (a financing root, a financing payee of the registry), an insurer or a
    claim payer, a bank, a title, escrow, closing or settlement firm, a lawyer's account or a public payer. Nor an
    owner-shaped payer (_OWNER_SHAPED_PAYER: a holding company, a partnership, a venture, a family office, a trust or an
    estate), whose disbursement is owner money. Nor a retirement account's or plan's (_RETIREMENT_ACCOUNT on the row's
    hold text), whose disbursement keeps its hold."""
    if not region or _channel(text) != "ach_eft":
        return False
    if (
        _FINANCING_ROOT.search(region) or _INSURER_NAME.search(region) or _CLAIM_WORD.search(region)
        or _BANK_OR_TITLE_SENDER.search(region) or _TRUST_LAWYER_WORDS.search(region)
        or _OWNER_SHAPED_PAYER.search(region) or _public_named(public_region(text))
        or _RETIREMENT_ACCOUNT.search(_hold_text(text))
    ):
        return False
    known = match_known_payee(_without_receiver_value(text), credit=True)
    return known is None or known.state not in FINANCING_STATES


def _disbursement_entry(text: str, region: str) -> bool:
    """§8.1, §8.6: the row's hold text prints a disbursement word (_DISBURSEMENT_WORD) outside the payer's own
    DISBURSEMENT ACCOUNT and beside no loan, escrow, title or proceeds word (_DISBURSEMENT_KEEP): the entry the
    purpose-only spare drops from the non-sale reading. Read outside the payer's own name field (`region` on a row that
    prints one, _prints_payer_name_field, as the spare reads DISTRIB... and STOCK), so a payer named for disbursement
    services ('<NAME> DISBURSEMENT SERVICES LLC DES:PAYMENT') prints no disbursement entry; a row that prints no name
    field, or whose hold text no longer prints the region, is read whole (fail closed)."""
    row = _hold_text(text)
    if region and _prints_payer_name_field(text):
        row = row.replace(region, " ")
    row = _DISBURSEMENT_ACCOUNT.sub(" ", row)
    return _DISBURSEMENT_WORD.search(row) is not None and _DISBURSEMENT_KEEP.search(row) is None


def _currency_conversion(text: str, *, bank: str | None = None) -> bool:
    """§8.1 (A3, precision sample): the holder's own currency conversion: currency-conversion wording on the row
    before its receiver fields (posting labels removed), on a row that names no payer once that wording is removed:
    no name word in its payer region (_counterparty_tokens), no transfer counterparty and no person-to-person sender.
    A named payer that prints the wording (a customer's wire converted on arrival, 'ORIG FABRIKAM GMBH ... FOREIGN
    EXCHANGE') keeps its reading. The standing rule (owner money never becomes revenue) holds it as non_sale_purpose:
    §5.3's own-money reason, as a SWEEP or a ZBA is held; it names no counterparty and designates no account, so it
    is no named transfer of T13 (transfer_account_designation).

    The statement's bank (`bank`) printing its own name right before the wording names no payer
    (_statement_bank_before_conversion: 'ROYAL FOREIGN EXCHANGE DEPOSIT' on a Royal Bank of Canada statement); a named
    currency-exchange company does (_named_currency_company: 'CURRENCY EXCHANGE INTERNATIONAL DES:PAYMENT'). A
    legal form or an article alone beside the wording names nobody (_NOT_A_NAME_ALONE, the person-to-person reader's
    rule), so a legal form names a currency company only on an originator field ('FX CONVERSION LLC <n>' and BMO's
    'INCOMING WIRE PAYMENT ... CA FOREIGN EXCHANGE LTD' stay held)."""
    if _CURRENCY_CONVERSION.search(_hold_text(text)) is None:
        return False
    own_bank = _statement_bank_before_conversion(bank) if bank else None
    if own_bank is not None:
        text = own_bank.sub(" ", text)
    if _named_currency_company(text):
        return False
    stripped = _without_currency_conversion(text)
    tokens = _counterparty_tokens(payer_region(stripped))
    if any(token not in _NOT_A_NAME_ALONE for token in tokens):
        return False
    if _transfer_row(_before_receiver(stripped)) and _transfer_counterparty_words(stripped, bank):
        return False
    return not _p2p_sender_region(stripped)
