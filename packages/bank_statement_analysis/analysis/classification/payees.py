"""Payee identity: insurance, payroll providers, unknown payee names, field-order payees, proceeds."""
from __future__ import annotations

import re
from typing import Sequence

from analysis.classification.record import UNIDENTIFIED_LENDER_OBLIGATION
from analysis.classification.tax_forms import _NON_REVENUE_CREDIT_PATTERNS
from analysis.classification_registry import (
    FACTORING_REVIEW_ENTITIES,
    INSURANCE_PROVIDER_ALIASES,
    POTENTIAL_LENDER_ALIASES,
    PREMIUM_FINANCE_ALIASES,
)
from analysis.descriptor.financing import _names_financing
from analysis.descriptor.lexical import (
    _before_receiver,
    _is_reference_token,
    _originator_segment,
    _payee_region,
    _wire_beneficiary,
    revenue_text,
)
from analysis.descriptor.payer import _sender_payer_region, payer_region
from analysis.descriptor.rails import _compile_field_order_forms, _is_wire_row, _matches_any
from analysis.descriptor.words import (
    _CONSUMER_P2P_RAIL,
    _ELECTRONIC_PAYMENT_FORM,
    _ENTITY_NOISE,
    _LEGAL_FORM_SUFFIXES,
    _ORGANISATION_CUES,
    _PAYEE_TEMPLATE_PREFIX,
    _PUSH_RAIL,
)
from analysis.payee_matcher import PayeeMatch, registry_match


def _insurance_registry_match(text: str, *, glued_digits: bool = False) -> tuple[str, str, bool] | None:
    """Spec §4.3 step 4: the insurer of an insurance row, as (entity, alias, premium_finance).

    Premium-finance payees (`PREMIUM_FINANCE_ALIASES`, spec §4.2) are consulted
    first, so a premium financier whose name contains an insurer's name is still
    the premium financier. With `glued_digits` (a credit), the premium-finance
    lookup also reads a one-word alias with a digit run glued after it ('IPFS888',
    'IPFSFLP12'), so every spelling of a premium financier's credit takes the one
    insurance treatment; a debit keeps today's reading.
    """
    premium = registry_match(text, PREMIUM_FINANCE_ALIASES, glued_digits=glued_digits)
    if premium is not None:
        return premium[0], premium[1], True
    insurer = registry_match(text, INSURANCE_PROVIDER_ALIASES)
    if insurer is not None:
        return insurer[0], insurer[1], False
    return None


#: PAYROLL glued to an ACH entry-description suffix (a closed list, so a receiver name that only contains PAYROLL
#: is not read), payroll providers seen in the corpus, benefit administrators and retirement-plan recordkeepers,
#: and the French pay words. Provider, administrator and French words are read on the originator segment only
#: (_originator_segment): a holder named like one of them in INDN or IND NAME never hides its lender. No new
#: pattern fires on a row that names financing. 401(k) is left out (it prints in holder names).
_PAYROLL_GLUED_PATTERN = re.compile(r"\bPAYROLL(?:TAX(?:ES)?|TX|TS|DDS?|DEP|FEES?)\b")
_PAYROLL_PROVIDER_PATTERNS = (
    re.compile(r"\b(?:PATRIOT SOFTWARE|DATAPAY|PAYCOR|ONPAY|PAYWORKS|PAYCOM|PAYLOCITY)\b"),
    re.compile(r"\b(?:HEALTH ?EQUI(?:TY)?|WAGEWORKS|TASC|ASCENSUS|HUMAN INTEREST|GUIDELINE RETIRE(?:MENT)?)\b"),
    re.compile(r"\bPAIE\b|\bSALAIRES?\b"),
)
_SQUARE_CAPITAL_CREDIT = re.compile(r"\bSQ ?CAP\d*\b")
_SQUARE_NAME = re.compile(r"\bSQ\b|\bSQUARE\b")
_SBA_DISBURSEMENT_CREDIT = re.compile(r"\bSBAD TREAS\b|\bSBA (?:EIDL|LOAN|DISB\w*)\b|\bEIDL\b")
#: A3: the Small Business Administration's name cut to
#: an originator field, read on the payer region alone: exactly SMALL BUSINESS, or SMALL BUSINESS and a leading cut of
#: ADMINISTRATION (A, AD, ADM ... ADMIN ... ADMINISTRATION), a U S prefix allowed. A payer whose name goes on in other
#: words (SMALL BUSINESS SOLUTIONS LLC) is a named payer.
_SBA_CUT_ORIGINATOR = re.compile(
    r"^(?:U ?S )?SMALL BUSINESS(?: (?:"
    + "|".join("ADMINISTRATION"[:length] for length in range(len("ADMINISTRATION"), 0, -1))
    + r"))?$"
)


#: Financing words that describe the payment, not the payee, when they lead the name.
_GENERIC_ENTITY_WORDS = {"FINANCE", "FINANCING", "FUNDING", "CAPITAL", "FUNDER", "ADVANCE"}
_ENTITY_ACRONYMS = {"ACH", "BDC", "CMCA", "EFT", "LLC", "LLP", "LP", "MCA", "PLLC", "SBA", "SNAP"}
_MAX_ENTITY_TOKENS = 4
#: Connectors that never end a name (a name cut by the four-word cap: 'BOKF NATIONAL BANK OF').
_TRAILING_CONNECTORS = frozenset({"OF", "AND", "THE", "DE", "DU", "DES"})
_TRUIST_CORP_PREFIX = re.compile(r"^ACH CORP (?:DEBIT|CREDIT)\b")
#: Truist prints no padding, so a short originator lets the receiver's words into the 16-character company
#: field. A Truist name is published only when a whole legal-form word lies inside those 16 characters.
_TRUIST_COMPANY_FIELD = 16


def _is_payroll_provider_row(text: str) -> bool:
    """A payroll provider, benefit administrator or French pay row (payroll N1 and N2)."""
    if _names_financing(text):
        return False
    return _PAYROLL_GLUED_PATTERN.search(text) is not None or _matches_any(
        _originator_segment(text), _PAYROLL_PROVIDER_PATTERNS
    )


def _unknown_payee_tokens(text: str) -> tuple[str, ...]:
    """D11: the payee words of an unknown counterparty, at most four.

    Removes originator-name labels, cuts at the first ACH field segment, drops
    channel words, single letters and leading financing words, and stops at the
    first reference token (digits, a masked number or a month) once a name has
    started, so a person's name printed after the references never joins it.

    A name ends at its first legal-form word after the first word; a leading AND and a trailing connector are
    dropped. A bank template prefix is removed first. A wire is read from its beneficiary, where a name ends at
    its first organisation cue after the first word.
    """
    beneficiary = _wire_beneficiary(text)
    region = _payee_region(beneficiary if beneficiary is not None else _PAYEE_TEMPLATE_PREFIX.sub(" ", text, count=1))
    tokens: list[str] = []
    for token in region.split():
        if token in _ENTITY_NOISE or len(token) == 1:
            continue
        if _is_reference_token(token):
            if tokens:
                break
            continue
        if not tokens and (token in _GENERIC_ENTITY_WORDS or token == "AND"):
            continue
        tokens.append(token)
        if len(tokens) > 1 and (
            token in _LEGAL_FORM_SUFFIXES or (beneficiary is not None and token in _ORGANISATION_CUES)
        ):
            break
        if len(tokens) == _MAX_ENTITY_TOKENS:
            break
    while tokens and tokens[-1] in _TRAILING_CONNECTORS:
        tokens.pop()
    return tuple(tokens)


def _names_an_organisation(tokens: Sequence[str]) -> bool:
    """D11 and 5.3: a cue names an organisation, except a legal-form word printed first (CORP of 'CORP
    FABRIKAM ...'); a name made only of cue words ('BANK', 'CORP') names none."""
    if all(token in _ORGANISATION_CUES for token in tokens):
        return False
    return any(
        token in _ORGANISATION_CUES and (position > 0 or token not in _LEGAL_FORM_SUFFIXES)
        for position, token in enumerate(tokens)
    )


def _unknown_payee_name(tokens: Sequence[str]) -> str | None:
    """D11: the published name, the unidentified label, or None when no payee is named."""
    if not tokens:
        return None
    if not _names_an_organisation(tokens):
        return UNIDENTIFIED_LENDER_OBLIGATION
    return " ".join(token if token in _ENTITY_ACRONYMS else token.title() for token in tokens)


def _truist_name_is_published(text: str) -> bool:
    """On a Truist 'ACH CORP DEBIT' row, whether a whole legal-form word lies inside the first 16 characters of the
    payee words, the width of the company-name field. True for every other row."""
    if not _TRUIST_CORP_PREFIX.match(text):
        return True
    words: list[str] = []
    for token in _payee_region(_PAYEE_TEMPLATE_PREFIX.sub(" ", text, count=1)).split():
        if not words and (token in _ENTITY_NOISE or len(token) == 1 or _is_reference_token(token)):
            continue
        words.append(token)
    printed = " ".join(words)
    field = printed[:_TRUIST_COMPANY_FIELD].split()
    if len(printed) > _TRUIST_COMPANY_FIELD and printed[_TRUIST_COMPANY_FIELD] != " ":
        field = field[:-1]  # the field's edge cut the last word
    return any(word in _LEGAL_FORM_SUFFIXES for word in field)


def _unknown_entity_for_text(text: str, tokens: Sequence[str]) -> str | None:
    """D11: the published name of the payee words `tokens` read from the normalized row `text` (5.3: a Truist name
    only through its company field)."""
    name = _unknown_payee_name(tokens)
    if name not in (None, UNIDENTIFIED_LENDER_OBLIGATION) and not _truist_name_is_published(text):
        return UNIDENTIFIED_LENDER_OBLIGATION
    return name


def _canonical_unknown_entity(text: str) -> str | None:
    return _unknown_entity_for_text(text, _unknown_payee_tokens(text))


_FIELD_ORDER_FORMS = _compile_field_order_forms()


def _field_order_payee(text: str) -> PayeeMatch | None:
    """The admitted payee a debit prints in the bank's field order, or None."""
    return next((match for pattern, match in _FIELD_ORDER_FORMS if pattern.search(text)), None)


#: An alternative-position payee's paid membership, or a top-up of the
#: customer's own balance with it, printed right after the payee's alias, is not
#: a repayment. The words are read after the matched alias, so no payee name is
#: written here.
_MEMBERSHIP_OR_TOP_UP_AFTER_ALIAS = (
    r" (?:PLUS|PLU|MEM|MEMB|MEMBER|MEMBERSHIP)\b",
    r" BALANCE TOP ?(?:UP|U)\b",
)


def _is_membership_or_top_up(text: str, match: PayeeMatch) -> bool:
    """True when a debit to an alternative-position payee is its membership or a balance top-up."""
    if match.state != "alternative_position":
        return False
    alias = re.escape(match.alias)
    return any(re.search(rf"\b{alias}{tail}", text) for tail in _MEMBERSHIP_OR_TOP_UP_AFTER_ALIAS)


#: D1 by descriptor: credits whose own words say they are financing proceeds, with
#: no registry payee named. Credits only.
_BANK_LINE_ADVANCE_CREDIT = re.compile(r"^LOAN CREDIT$")
_LOC_DRAW_CREDIT_PATTERNS = (
    re.compile(r"\b(?:LOC|LINE OF CREDIT) (?:ADVANCE|ADV|DRAW)\b"),
    re.compile(r"\bADVANCE FROM (?:LOC|LINE OF CREDIT)\b"),
    re.compile(r"\bDRAW (?:ON|FROM) (?:LOC|LINE OF CREDIT)\b"),
)
_FLOOR_PLAN_ADVANCE_CREDIT = re.compile(r"^ADVANCE (?:19|20)\d\d .*\bVIN\b")


def _descriptor_proceeds(text: str) -> tuple[str, bool] | None:
    """D1 by descriptor: (rule, whether the statement bank is the lender), or None.

    Read after the known-payee check. The bank's own line advance (exactly
    LOAN CREDIT) is decided there, ahead of the strong non-revenue rule that
    would otherwise claim it. A line-of-credit draw or a per-vehicle floor-plan
    advance counts only when no potential alias and no strong non-revenue rule
    (an own-account transfer, for example) claims the credit.
    """
    if _BANK_LINE_ADVANCE_CREDIT.search(text):
        return "bank_line_advance_credit", True
    # §7.11: Square Capital's SQ CAP spelling on a row that names Square, and SBA and EIDL disbursements (A3: the
    # SBA's name cut to its originator field too).
    if _SQUARE_CAPITAL_CREDIT.search(text) and _SQUARE_NAME.search(text):
        return "square_capital_credit", False
    if _SBA_DISBURSEMENT_CREDIT.search(text) or _sba_cut_originator(text):
        return "sba_disbursement_credit", False
    if registry_match(text, POTENTIAL_LENDER_ALIASES) is not None or _matches_any(
        text, _NON_REVENUE_CREDIT_PATTERNS
    ):
        return None
    if _matches_any(text, _LOC_DRAW_CREDIT_PATTERNS):
        return "loc_draw_credit", True
    if _FLOOR_PLAN_ADVANCE_CREDIT.search(text):
        return "floor_plan_advance_credit", False
    return None


def _sba_cut_originator(text: str) -> bool:
    """A3 (precision sample): the payer region of a wire or of a row with an electronic-payment form (an originator
    field) is the SBA's name cut to the field (_SBA_CUT_ORIGINATOR). Never read on a person-to-person or push rail,
    nor on a transfer's sender after FROM, which names an account ('ONLINE TRANSFER FROM SMALL BUSINESS XXXXXX1234')."""
    if "SMALL BUSINESS" not in text:
        return False
    text = revenue_text(text)
    row = _before_receiver(text)
    if not _is_wire_row(text) and (
        _ELECTRONIC_PAYMENT_FORM.search(row) is None
        or _CONSUMER_P2P_RAIL.search(row) is not None
        or _PUSH_RAIL.search(row) is not None
        or _sender_payer_region(text)
    ):
        return False
    return _SBA_CUT_ORIGINATOR.match(payer_region(text).strip()) is not None


def _factoring_review_payee(text: str) -> PayeeMatch | None:
    """Lender detection spec §5, amended: the factoring review entity (FACTORING_REVIEW_ENTITIES) whose potential alias
    wins on the row, as a factoring payee, or None."""
    found = registry_match(text, POTENTIAL_LENDER_ALIASES)
    if found is None or found[0] not in FACTORING_REVIEW_ENTITIES:
        return None
    return PayeeMatch(found[0], "factoring", found[1])
