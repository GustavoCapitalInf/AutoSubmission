"""Personal and premium trust titles."""
from __future__ import annotations

import re
from typing import Sequence, TYPE_CHECKING

from analysis.classification.record import _replace_revenue_state
from analysis.descriptor.lexical import _is_reference_token, company_form
from analysis.descriptor.rails import _is_wire_row
from analysis.descriptor.words import (
    HOLDER_NOISE,
    _BANK_COMPANY_FORM,
    _WIRE_SENDER_AFTER_LABEL,
    _WIRE_SENDER_AFTER_LABEL_END,
)
from analysis.holder_name import (
    LEGAL_FORMS as _HOLDER_LEGAL_FORMS,
    PREMIUM_TRUST_ADJECTIVE as _PREMIUM_TRUST_ADJECTIVE,
    PREMIUM_TRUST_KIND as _PREMIUM_TRUST_KIND,
    PREMIUM_TRUST_REFERENCE as _PREMIUM_TRUST_REFERENCE,
    PREMIUM_TRUST_WORDS,
)
from analysis.true_revenue.channel import _channel
from analysis.true_revenue.hold_text import _title_purpose_text
from analysis.true_revenue.sender import _wire_originator_text
from analysis.true_revenue.tiers import _with_tier
from analysis.true_revenue.words import (
    _TRUST_ADDRESS_MAX_WORDS,
    _TRUST_BUSINESS_WORDS,
    _TRUST_LAWYER_WORDS,
    _US_STATE_TAIL,
)

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


#: §8.1: a personal trust's payment whose purpose cites the holder's service, a school's tuition or a student's ID, is a
#: customer's payment, not owner money; it is read on the payment's purpose (_title_purpose_text) with a line wrap's
#: split joined ('TUITIO N'). A trust's invoice or PO payment is already verified by §7.9 before the holds read it. The
#: ruling names TUITION and STUDENT ID only: TUITION is read on the space-stripped purpose (a wrap's split joined, glued
#: after a word as in FORTUITION) but never after IN (INTUITION, a cross-word join INTUIT ION...), and STUDENT ID on the
#: printed purpose as whole words (STUDENT ID 12345, STUDENTID12345; never STUDENT IDEAS). IN TUITION is held, the safe
#: side. A line wrap's split inside STUDENT or ID is joined, as TUITION's reader joins one (STUDEN T ID, STUDENT I D),
#: the two ends staying whole words (never STUDENT I DEAS, STUDENT IDENTIFICATION or STUDENTS ID).
_TRUST_SERVICE_PURPOSE = re.compile(r"(?<!IN)TUITION")
_TRUST_STUDENT_ID_PURPOSE = re.compile(r"(?<![A-Z])S ?T ?U ?D ?E ?N ?T ?I ?D(?![A-Z])")
#: §8.1: a personal trust's words: the trust word, the trustee's TTEE, and the adjectives a personal trust prints
#: before its trust word.
_PERSONAL_TRUST_WORDS = frozenset({"TRUST", "TRST", "TR", "TTEE"})
_PERSONAL_TRUST_ADJECTIVES = frozenset({"REVOCABLE", "REV", "LIVING", "FAMILY", "FAM", "IRREVOCABLE", "IRREV"})
_PERSONAL_TRUST_FILLERS = frozenset({"THE", "AND", "OF"})
_PERSONAL_TRUST_MAX_NAME_WORDS = 5
#: §8.1: the words a trust form may print after it: its agreement and date words (DTD, DATED, U A, UA, UAD, UTA), a
#: date or a number, a PO box and the country; on a wire's originator field, which prints the sender's address
#: after the name, an address that ends in a US state code.
_TRUST_TAIL_WORDS = frozenset({"DTD", "DATED", "U", "A", "UA", "UAD", "UTA", "PO", "BOX", "US", "USA"})
#: §8.1: the words a trust's address never prints before its state: account, service, department and office words,
#: and the trades a business names itself by ('... TRUST ROOFING <city> <state>' is a company).
_TRUST_NOT_PLACE_WORDS = frozenset({
    "ACCOUNT", "ACCT", "ACCOUNTS", "SERVICES", "SERVICE", "SVCS", "SVC", "DEPT", "DEPARTMENT", "DIV", "DIVISION",
    "OFFICE", "OPERATING", "OPERATIONS", "ADMIN", "ADMINISTRATION",
    # A trust company's custody and administration words.
    "CUSTODY", "CUSTODIAN", "CUSTODIANS", "ADMINISTRATOR", "ADMINISTRATORS",
    "ROOFING", "LANDSCAPE", "CONSTRUCTION", "CONTRACTING", "CONTRACTORS", "PLUMBING", "ELECTRIC", "ELECTRICAL", "HVAC",
    "LANDSCAPING", "TRUCKING", "TRANSPORT", "LOGISTICS", "CLEANING", "SUPPLY", "SALES", "MARKETING", "CONSULTING",
    "DESIGN", "AUTO", "MOTORS", "RESTAURANT", "BAKERY", "CAFE", "GRILL", "DELI", "DENTAL", "MEDICAL", "CLINIC",
    "PHARMACY", "SALON", "SPA", "FITNESS", "STUDIO", "MEDIA", "PRODUCTIONS", "TECHNOLOGIES", "TECH", "SYSTEMS",
    "ENTERPRISES", "INDUSTRIES", "MANUFACTURING", "FARMS", "RANCH", "TRAVEL", "HOMES", "BUILDERS", "REMODELING",
    "PAINTING", "FLOORING", "STORE", "SHOP", "MARKET", "WHOLESALE", "DISTRIBUTION", "IMPORTS", "EXPORTS", "TRADING",
})
#: A street type right after the trust word makes it a street's name ('12 TRUST RD'), never a trust form.
_STREET_WORDS = frozenset({
    "RD", "ROAD", "ST", "STREET", "AVE", "AVENUE", "DR", "DRIVE", "LN", "LANE", "BLVD", "WAY", "CT", "COURT", "PL",
    "PLACE", "HWY", "PKWY", "CIR", "TER", "TRL",
})
#: §8.1: a bank's or a trust company's form right after the trust word, and a lawyer's or a client trust account
#: anywhere in the sender.
_TRUST_COMPANY_SUFFIX = re.compile(r"^(?:TRUST|TRST|TR) (?:N A|NA|FSB|BANK|COMPANY|CO)\b")


def _held_personal_trust(text: str, region: str) -> bool:
    """§8.1: a personal trust that the hold names (_personal_trust), unless the payment's purpose
    (_title_purpose_text, a line wrap's split joined) cites the holder's service: a school's tuition or a student's ID
    (_TRUST_SERVICE_PURPOSE, _TRUST_STUDENT_ID_PURPOSE). A trust's payment with no purpose stays held. TUITION never
    read after IN, STUDENT ID only as whole words on the printed purpose (a line wrap's split inside it joined)."""
    if not _personal_trust(text, region):
        return False
    purpose = _title_purpose_text(text)
    return (
        _TRUST_SERVICE_PURPOSE.search(purpose.replace(" ", "")) is None
        and _TRUST_STUDENT_ID_PURPOSE.search(purpose) is None
    )


def _personal_trust(text: str, region: str) -> bool:
    """§8.1: the named sender is a personal trust, held as non_sale_purpose (owner money: a family's
    money, an investment or a loan far more often than a customer's purchase). Read on a wire's originator field before
    its digit cut (_wire_originator_text: 'JANE Q SAMPLE 1234 TRUST <city> <state> ...', or the sender printed right
    after the label), and on any other row's payer region. The sender prints a trust form (_PERSONAL_TRUST_WORDS) after
    one to _PERSONAL_TRUST_MAX_NAME_WORDS name words (digits, fillers and the trust adjectives aside); a plain TRUST or
    TRST with no adjective needs two name words and never reads a person-to-person row (whose sender field also prints
    the sending bank), and a bare TR needs an adjective. And all of these hold:
    (a) the trust form ends the sender's name (_trust_form_ends_the_name: 'IN GOD WE TRUST ROOFING' is no trust);
    (b) the words before it read as a person's name: no business, institutional or benefit word (_TRUST_BUSINESS_WORDS,
        the classifier's holder-noise words) and no company form;
    (c) no bank's or trust company's form after the trust word (_TRUST_COMPANY_SUFFIX: TRUST NA, FSB, BANK, COMPANY,
        CO) and no lawyer's or client trust account (_TRUST_LAWYER_WORDS: ESQ, ATTORNEY, LAW, LEGAL, IOLTA, IOTA, IOLA)."""
    wire = _is_wire_row(text)
    sender = (_wire_originator_text(text) or _wire_sender_after_label_text(text)) if wire else region
    tokens = sender.split()
    index = next((at for at, token in enumerate(tokens) if token in _PERSONAL_TRUST_WORDS), None)
    if index is None:
        return False
    before = [token for token in tokens[:index] if not any(ch.isdigit() for ch in token)]
    adjectives = [token for token in before if token in _PERSONAL_TRUST_ADJECTIVES]
    names = [token for token in before if token not in _PERSONAL_TRUST_ADJECTIVES and token not in _PERSONAL_TRUST_FILLERS]
    if not 1 <= len(names) <= _PERSONAL_TRUST_MAX_NAME_WORDS:
        return False
    if tokens[index] != "TTEE" and not adjectives:
        if tokens[index] == "TR" or len(names) < 2 or _channel(text) == "person_to_person":
            return False
    # (c) a trust company's or a bank's form after the trust word; a lawyer's or a client trust account.
    # The lawyer and client-trust words read across the whole sender.
    if _TRUST_COMPANY_SUFFIX.search(" ".join(tokens[index:])) or _TRUST_LAWYER_WORDS.search(" ".join(tokens)):
        return False
    # (a) the trust form ends the sender's name.
    if not _trust_form_ends_the_name(tokens[index + 1:], address=wire):
        return False
    # (b) the words before the form read as a person's name.
    return not (
        company_form(" ".join([*before, tokens[index]]))
        or any(_TRUST_BUSINESS_WORDS.search(name) or name in HOLDER_NOISE for name in names)
    )


def _trust_form_ends_the_name(tail: Sequence[str], *, address: bool) -> bool:
    """§8.1: the words after a trust form add nothing to the sender's name: only its agreement and date words, dates,
    numbers, a PO box and the country (_TRUST_TAIL_WORDS), or, on a wire's originator field (which prints the
    sender's address after its name), an address that ends in a US state code ('... TRUST SAMPLEVILLE WA 12345 US')."""
    words = list(tail)
    if words and words[0] in _STREET_WORDS:
        # A street named TRUST ('12 TRUST RD'): the trust word is the address's, not a trust form.
        return False
    if "FBO" in words:
        # The trust's beneficiary ('... FAMILY TRUST FBO <name>') names no other sender.
        words = words[: words.index("FBO")]
    while words and (_is_reference_token(words[-1]) or words[-1] in {"US", "USA"}):
        words.pop()
    if all(word in _TRUST_TAIL_WORDS or _is_reference_token(word) for word in words):
        return True
    if not address or words[-1] not in _US_STATE_TAIL:
        return False
    # The address holds only place words before its state: city words (and a street or PO box), never a business,
    # lawyer, company-form, account, service, department or institution word. The list is finite, so the address is
    # also at most _TRUST_ADDRESS_MAX_WORDS words (_address_words). A dotted company form ('L.L.C.', 'P.A.') prints
    # as single letters, which the cap skips: joined, they are a form.
    if len(_address_words(words[:-1])) > _TRUST_ADDRESS_MAX_WORDS or _joined_letters_company_form(words[:-1]):
        return False
    return not any(_not_a_place_word(word) for word in words[:-1])


#: §8.1: the company forms a dotted spelling joins into besides the classifier's (_BANK_COMPANY_FORM has LLC, LP, INC,
#: CO ...): a professional association and a professional corporation. Read on joined letters only: a lone PA is
#: Pennsylvania.
_DOTTED_COMPANY_FORMS = frozenset({"LP", "PA", "PC"})


def _joined_letters_company_form(words: Sequence[str]) -> bool:
    """§8.1: two or more single letters in a row that join into a company form (a dotted 'L.L.C.', 'L.P.', 'P.A.' or
    'P.C.', which the normalizer prints 'L L C'). Initials that join into none keep their skip (the agreement's 'U
    A', a middle initial)."""
    run: list[str] = []
    for word in [*words, ""]:
        if len(word) == 1 and word.isalpha():
            run.append(word)
            continue
        joined = "".join(run)
        if len(run) >= 2 and (joined in _DOTTED_COMPANY_FORMS or _BANK_COMPANY_FORM.fullmatch(joined)):
            return True
        run = []
    return False


def _address_words(words: Sequence[str]) -> list[str]:
    """§8.1: the address's own words before its state, the words the cap counts: never the agreement, date, PO box
    and country words (_TRUST_TAIL_WORDS: '... TRUST U A DTD PO BOX <n> <city>'), a number or a reference token (a
    street number, a name glued to it), a street type (_STREET_WORDS) or an initial."""
    return [
        word for word in words
        if not (
            _is_reference_token(word) or word in _TRUST_TAIL_WORDS or word in _STREET_WORDS
            or len(word) == 1
        )
    ]


def _not_a_place_word(word: str) -> bool:
    """§8.1: a word no address prints before its state: a business, trade, lawyer, company-form, account,
    service, department or institution word (_TRUST_NOT_PLACE_WORDS, _TRUST_BUSINESS_WORDS, _TRUST_LAWYER_WORDS,
    the classifier's company forms). Numbers (a street or a PO box) and the agreement words (_TRUST_TAIL_WORDS)
    are place words here; the generic words are not read (a city prints NEW, as NEW YORK)."""
    if (
        _is_reference_token(word) or word in _TRUST_TAIL_WORDS or word in _US_STATE_TAIL
        or word in {"CITY", "COUNTY", "STATE"}
    ):
        return False
    return (
        word in _TRUST_NOT_PLACE_WORDS
        or _TRUST_BUSINESS_WORDS.search(word) is not None or _TRUST_LAWYER_WORDS.search(word) is not None
        or _BANK_COMPANY_FORM.fullmatch(word) is not None
    )


def _wire_sender_after_label_text(text: str) -> str:
    """§5.2: the sender a wire prints right after its label (the classifier's _WIRE_SENDER_AFTER_LABEL layouts), up to
    its end (a wire field, NOTPROVIDED or WIRE PAYMENT), before the digit cut the payer region makes; '' on any other
    layout."""
    found = _WIRE_SENDER_AFTER_LABEL.match(text)
    if found is None:
        return ""
    rest = text[found.end():]
    end = _WIRE_SENDER_AFTER_LABEL_END.search(rest)
    return (rest[: end.start()] if end is not None else rest).strip()


#: §5.3, §8.10: the held reason of a credit into an account whose printed title reads PREMIUM TRUST, and the method and
#: rule a verified one leaves verification with.
PREMIUM_TRUST_REASON = "premium_trust_account"
PREMIUM_TRUST_METHOD = "premium_trust_account"
_PREMIUM_TRUST_RULE = "premium_trust_account_title"
#: The kind words a title may print after the premium-trust words (an account, a fund, a product:
#: holder_name.PREMIUM_TRUST_KIND, imported above as _PREMIUM_TRUST_KIND), and the account and product words alone (no
#: FUND or FUNDS), which the separator form needs. A product adjective may print before a kind word ('PREMIUM TRUST
#: BUSINESS CHECKING'; holder_name.PREMIUM_TRUST_ADJECTIVE); an adjective alone is never a kind word ('PREMIUM TRUST
#: BUSINESS' is no title). The reference a title may print is holder_name.PREMIUM_TRUST_REFERENCE (imported as
#: _PREMIUM_TRUST_REFERENCE): an account number, masked or not, after #, NO, NUMBER, ACCOUNT, ACCT or A/C, in or out of
#: parentheses; a roman numeral; or a parenthesised code of up to four letters or digits. The three
#: live in holder_name, so a holder line's contact designation reads the same title.
_PREMIUM_TRUST_ACCOUNT_KIND = (
    rf"{_PREMIUM_TRUST_ADJECTIVE}"
    r"(?:ACCOUNT|ACCT|ACCNT|A/C|CHECKING|CHK|DDA|SAVINGS|SAV|SHARE|MMA|MONEY\s+MARKET)\.?"
)
_PREMIUM_TRUST_TITLE = rf"(?P<title>{PREMIUM_TRUST_WORDS}(?:\s+{_PREMIUM_TRUST_KIND})*)"
#: The three title forms. The title at the field's end (kind words, a reference and punctuation may follow); the words
#: followed by an account word; the words and one or more account or product words, a reference allowed, then a
#: separator (' - ', an en or em dash, ':' or '(') and anything ('PREMIUM TRUST ACCOUNT - NORTHWIND AGENCY LLC').
_PREMIUM_TRUST_AT_END = re.compile(rf"{_PREMIUM_TRUST_TITLE}(?:[\s\-:#,]*{_PREMIUM_TRUST_REFERENCE})?[\s.,;:\-)]*$")
_PREMIUM_TRUST_WITH_ACCOUNT = re.compile(
    rf"(?P<title>{PREMIUM_TRUST_WORDS}\s+{_PREMIUM_TRUST_ADJECTIVE}(?:ACCOUNT|ACCT|ACCNT|A/C)\.?)(?![A-Z])"
)
#: The for-benefit form, the words and an account word before FBO, F/B/O, OF or FOR and a name ('PREMIUM TRUST ACCOUNT
#: FBO NORTHWIND AGENCY LLC'), read on an account name or a holder name even when the field ends in a legal form (the
#: form is the beneficiary's). A product adjective may print before the account word, as in the account-word form
#: ('PREMIUM TRUST BUSINESS ACCOUNT FBO NORTHWIND LLC').
_PREMIUM_TRUST_FOR_BENEFIT = re.compile(
    rf"(?P<title>{PREMIUM_TRUST_WORDS}\s+{_PREMIUM_TRUST_ADJECTIVE}(?:ACCOUNT|ACCT|ACCNT|A/C)\.?)"
    r"\s+(?:FBO|F/B/O|F B O|OF|FOR)\s+[A-Z]"
)
_PREMIUM_TRUST_SEPARATED = re.compile(
    rf"(?P<title>{PREMIUM_TRUST_WORDS}(?:\s+{_PREMIUM_TRUST_ACCOUNT_KIND})+)(?:[\s\-:#,]*{_PREMIUM_TRUST_REFERENCE})?"
    r"\s*(?:\s-\s|\s?[–—]\s?|:|\()\s*\S"
)
#: A field that ends in a legal form (the holder readers' LEGAL_FORMS), which refuses the account-word form on an
#: account name or a holder name ('PREMIUM TRUST ACCOUNT LLC' is a company).
_PREMIUM_TRUST_LEGAL_LAST = re.compile(r"\b(?:" + "|".join(sorted(_HOLDER_LEGAL_FORMS)) + r")\.?\s*$")


def _premium_trust_field(field: str | None) -> str:
    """A statement field as the premium-trust rule reads it: upper case, its whitespace runs collapsed, L.L.C. read as
    LLC."""
    return " ".join(str(field or "").upper().replace("L.L.C.", "LLC").split())


def _premium_trust_words(match: re.Match[str]) -> str:
    """The title words a form matched, its dots dropped and its blanks collapsed."""
    return " ".join(match.group("title").replace(".", " ").split())


def premium_trust_title(account_title: str | None, account_name: str | None, holder_name: str | None) -> str | None:
    """§8.10, §9.1: the premium-trust title a statement prints, or None. Read on the statement's own fields, never on a
    row (a payer that prints the words makes no title). The bank's designation (`Statement.account_title`) reads in any
    of the three title forms: the title at the field's end, the words followed by an account word, or the words and an
    account or product word before a separator; never the words anywhere ('PREMIUM TRUST ROOFING', a trade name the
    holder reader dropped after a legal form, is no title). Then the account name, then the holder's name: the title at
    the end, the account-word form only when the field does not end in a legal form ('PREMIUM TRUST ACCOUNT LLC' is a
    company), the for-benefit form even when it does ('PREMIUM TRUST ACCOUNT FBO NORTHWIND AGENCY LLC'), and the
    separator form even when it does ('PREMIUM TRUST ACCOUNT - NORTHWIND INSURANCE AGENCY LLC'). A product adjective
    (BUSINESS, ANALYZED, COMMERCIAL) may print before a kind word or the account word, and FUND or FUNDS between the
    words ('PREMIUM FUND TRUST ACCOUNT'). Returns the matched title words, dots dropped. Recorded false negatives (each
    overstates True: the trust account's deposits stay counted): 'PREM. TR. ACCT.', a bare title before a separator
    ('PREMIUM TRUST - CONTOSO AGENCY LLC'), 'PREMIUM TRUST OPERATING', and a title only a statement whose parser reads
    no holder line prints (no account title is published there); a holder line's contact that prints a name before the
    words ('CARE OF NORTHWIND PREMIUM TRUST ACCOUNT') or any other word after the designation ('ATTN: PREMIUM TRUST
    ACCOUNT - NORTHWIND'), which the holder readers publish as no title. Recorded over-reads (each understates True,
    held and reviewable): a trade name that prints the words and an account word."""
    text = _premium_trust_field(account_title)
    if text:
        for form in (_PREMIUM_TRUST_AT_END, _PREMIUM_TRUST_WITH_ACCOUNT, _PREMIUM_TRUST_SEPARATED):
            if (found := form.search(text)) is not None:
                return _premium_trust_words(found)
    for field in (account_name, holder_name):
        text = _premium_trust_field(field)
        if not text:
            continue
        if (found := _PREMIUM_TRUST_AT_END.search(text)) is not None:
            return _premium_trust_words(found)
        if not _PREMIUM_TRUST_LEGAL_LAST.search(text) and (found := _PREMIUM_TRUST_WITH_ACCOUNT.search(text)):
            return _premium_trust_words(found)
        if (found := _PREMIUM_TRUST_FOR_BENEFIT.search(text)) is not None:
            return _premium_trust_words(found)
        if (found := _PREMIUM_TRUST_SEPARATED.search(text)) is not None:
            return _premium_trust_words(found)
    return None


def _held_in_premium_trust(record: TransactionClassification, title: str) -> TransactionClassification:
    """§8.10, as _held_by_the_floor holds: a credit a rule verified or counted, on a
    statement whose title reads PREMIUM TRUST, held for review as PREMIUM_TRUST_REASON. A verified one first leaves
    verification as a new first state (unverified_deposit, method PREMIUM_TRUST_METHOD, pending review, so the
    analyst may confirm it), its reason naming the rule it overruled; a counted one keeps its state, method and
    rule, and only its tier and reason change."""
    if record.revenue_classification == "verified_revenue":
        # The ruling is named without its date: no year literal outside date parsing (test_no_statement_hardcodes).
        record = _replace_revenue_state(
            record,
            "unverified_deposit",
            match_method=PREMIUM_TRUST_METHOD,
            matched_rule=_PREMIUM_TRUST_RULE,
            confidence_score=0.40,
            reason=(
                f"A deposit into an account titled {title}: an insurance agency's premium trust account holds its "
                "insureds' premiums, not the agency's revenue (the owner's ruling on the underwriter's Q10). The rule "
                f"that read it ({record.revenue_match_method}) is overruled, and it is held for review."
            ),
            context_signals=(*record.revenue_context_signals, PREMIUM_TRUST_METHOD),
            related_transaction=record.revenue_related_transaction,
        )
    return _with_tier(record, "excluded_pending_review", PREMIUM_TRUST_REASON)
