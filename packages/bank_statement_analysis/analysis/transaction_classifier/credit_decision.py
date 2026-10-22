"""_classify_credit_revenue, intact, with its operating-source and fallback decisions."""
from __future__ import annotations

import re

from analysis.classification.credit_predicates import (
    _named_sender_after_designation,
    _own_book_or_funds_transfer,
    _payer_remittance,
    _public_payer_remittance,
    _refused_by_payer_guards,
    _reversal_credit,
    _split_glued_claim,
    _wire_remittance_purpose,
    _wire_vetoed,
)
from analysis.classification.operating_sources import (
    _OperatingSource,
    _card_settlement_form,
    _has_operating_context,
    _operating_source,
)
from analysis.classification.payees import _descriptor_proceeds, _insurance_registry_match
from analysis.classification.record import _RevenueDecision
from analysis.classification.tax_forms import _NON_REVENUE_CREDIT_PATTERNS, government_no_purpose
from analysis.classification_registry import (
    BLUE_PLAN_CLAIM_PAYERS,
    FACTORING_REVIEW_ENTITIES,
    OPERATING_REVENUE_SOURCE_TYPES,
    PAYOUT_CREDIT_ENTITIES,
    POTENTIAL_LENDER_ALIASES,
)
from analysis.description_text import ln_name_spans
from analysis.descriptor.credit_words import _HCCLAIMPMT, _INSURER_CUSTOMER_PAYMENT, _MICRO_DEPOSIT_FLOOR
from analysis.descriptor.holder import _business_account, holder_reading, platform_entry_leads_with_financing
from analysis.descriptor.lexical import _before_receiver, _joined_text, revenue_text
from analysis.descriptor.payer import channel_gate, payer_region
from analysis.descriptor.rails import _matches_any, _state_words, _wire_vetoes_apply, _without_receiver_value
from analysis.descriptor.words import (
    _BNPL_CONSUMER_CREDIT,
    _CUSTOMER_INVOICE_DESCRIPTORS,
    _FLAGGED_REVENUE_CREDIT_STATES,
    _PAYOUT_NON_SALE_CREDIT,
    _SNAP_MERCHANT_FUNDING,
)
from analysis.flag_groups import FINANCING_STATES
from analysis.payee_matcher import PayeeMatch, match_known_payee, registry_match
from analysis.true_revenue.dealer import dealer_funding_reading
from analysis.true_revenue.holder_names import without_receiver_and_holder


_VERIFIED_REVENUE_CREDIT_PATTERNS = (
    re.compile(r"\bMRCH\d{5,}\b"),
    re.compile(r"\bMERCHANT (?:PROCESSOR )?(?:SETTLEMENT|DEPOSIT|PAYOUT)\b"),
    re.compile(r"\bCARD SALES? (?:DEPOSIT|SETTLEMENT|PAYOUT)\b"),
    re.compile(r"\bMARKETPLACE (?:PAYOUT|SETTLEMENT)\b"),
    # §7.7: the NACHA claim-payment entry, glued on either side (Chase's SEC, a sixteen-character name or
    # digits on the left); its unbounded branch takes only the full token, so THECLAIMPMT stays unmatched.
    re.compile(r"(?:\bH[CE]?|HC)CLAIMPMT(?:SEC)?\b"),
    re.compile(r"\bEDIRPAY\b"),
    re.compile(r"\bMERCHANT BANK(?:CD|CARD|ED) DEPOSIT\b"),
    re.compile(r"\bMTOT DEP\b"),
)
_UNVERIFIED_DEPOSIT_CREDIT_PATTERNS = (
    re.compile(r"\bMOBILE DEPOSIT\b"),
    re.compile(r"\bACH CREDIT\b"),
    re.compile(r"\bDIRECT DEPOSIT\b"),
    re.compile(r"\bE TRANSFER (?:RECEIVED|DEPOSIT)\b"),
    re.compile(r"\bETRANSFER (?:RECEIVED|DEPOSIT)\b"),
    re.compile(r"\b(?:CHECK|CHEQUE) DEPOSIT\b"),
    re.compile(r"\bCASH DEPOSIT\b"),
    re.compile(r"\bDEPOSIT\b"),
)


# ---------------------------------------------------------------------------------------------------------------------
# True revenue spec §5.2, §6.1, §7: the credit revenue
# readers. Every credit revenue rule reads revenue_text(text); D11, normalized_description and every debit rule keep
# the normalized row as it is.
# ---------------------------------------------------------------------------------------------------------------------

#: T18 (OQ5): a credit that prints the NACHA claim-payment entry skips the insurer registry, so an insurer's healthcare
#: claim payment to a provider verifies. Off, it is held with the insurer's other credits.
HCCLAIMPMT_CLAIM_FIRST = True
_BLUE_PLAN_CLAIM_PAYER = re.compile("|".join(BLUE_PLAN_CLAIM_PAYERS))


def _classify_credit_revenue(
    text: str,
    amount: float,
    *,
    posted: bool,
    account_name: str | None,
    direction_consistent: bool,
    bank: str | None = None,
    holder_name: str | None = None,
    description: str | None = None,
) -> _RevenueDecision | None:
    """The credit's revenue decision. `description` is the printed description, read only by the strong non-revenue
    step's LN-name reading (description_text.ln_name_spans)."""
    if amount <= 0 or not posted:
        return None
    text = revenue_text(text)
    # The holder tests read the holder's own name when the parser read it; the account-name field keeps its product
    # readings (_business_account).
    holder = holder_reading(account_name, holder_name)

    if not direction_consistent:
        return _RevenueDecision(
            "unverified_deposit",
            None,
            "direction_conflict",
            None,
            "source_direction_conflicts_with_signed_amount",
            0.20,
            "The source direction conflicts with the signed amount, so the credit requires review.",
            context_signals=("positive_amount", "direction_conflict"),
        )
    if _reversal_credit(text):
        return _RevenueDecision(
            "non_revenue",
            None,
            "reversal_cancellation_exclusion",
            None,
            "returned_cancelled_reversed_or_provisional_credit",
            0.99,
            "Credit is a return, cancellation, reversal, refund, correction, chargeback, or provisional credit.",
            context_signals=("credit_direction", "strong_non_revenue_descriptor"),
        )
    # §6.1 step 3a: a government payment that prints no purpose is excluded, at any amount (under the $1 floor too,
    # as step 3), after the direction conflict and the reversal (a government row printing a return word stays the
    # reversal's) and before every other rule; the residue test keeps any other payer's name off the row, so a
    # lender's D1 reading is never pre-empted.
    no_purpose = government_no_purpose(text)
    if no_purpose is not None:
        return _RevenueDecision(
            "non_revenue",
            None,
            "government_no_purpose_exclusion",
            no_purpose,
            "government_payment_no_purpose",
            0.95,
            (
                f"A government payment that prints no purpose ({no_purpose}): excluded from revenue by the owner's "
                "ruling (the underwriter's Q12, spec §19.1)."
            ),
            context_signals=("credit_direction", "government_no_purpose"),
        )

    # §6.1 step 4 (Q7, 5.6): a dealer's funding from a listed auto lender is revenue; a credit union's VHCL PURCH
    # entry waits for the statement pass, which verifies two or more of them. Never under the $1 floor (§7.0). The
    # decision names the lender and its alias, as the financing-proceeds decision it replaces did.
    dealer = dealer_funding_reading(text) if amount >= _MICRO_DEPOSIT_FLOOR else None
    if dealer is not None and dealer.arm == "listed":
        return _RevenueDecision(
            "verified_revenue",
            dealer.entity,
            "auto_lender_dealer_funding",
            dealer.alias,
            "verified_auto_lender_dealer_funding",
            0.90,
            (
                f"Listed auto lender '{dealer.entity}' (alias '{dealer.alias}') pays the dealer on a vehicle contract "
                f"it financed ({dealer.word}): the dealer's revenue, not financing proceeds."
            ),
            source_type="auto_dealer_funding",
            context_signals=("credit_direction", "auto_lender_dealer_funding"),
        )
    if dealer is not None:
        return _RevenueDecision(
            "unverified_deposit",
            dealer.entity,
            "credit_union_vehicle_purchase",
            dealer.alias,
            "credit_union_vehicle_purchase_requires_statement_count",
            0.60,
            (
                f"Credit union '{dealer.entity}' prints the {dealer.word} entry, a credit union's funding of a dealer's "
                "indirect auto loan; two or more such credits in the statement are dealer funding."
            ),
            source_type="auto_dealer_funding",
            context_signals=("credit_direction", "credit_union_vehicle_purchase"),
        )
    # §7.7: the lookups below read a glued HCCLAIMPMT split from the name before it.
    lookup_text = _split_glued_claim(text)
    claim_entry = _HCCLAIMPMT.search(text) is not None
    # A premium-finance credit keeps the insurance credit treatment (spec §4.2). T18: a claim payment skips the
    # insurer registry when the owner's switch is on; T14: an insurer's customer payment is held, not decided.
    insurance_match = _insurance_registry_match(lookup_text, glued_digits=True)
    if insurance_match is not None and not (claim_entry and HCCLAIMPMT_CLAIM_FIRST):
        entity, alias, _premium_finance = insurance_match
        if claim_entry or _INSURER_CUSTOMER_PAYMENT.search(_before_receiver(text)):
            return _RevenueDecision(
                "unverified_deposit",
                entity,
                "insurer_customer_payment",
                alias,
                "insurer_customer_payment_requires_review",
                0.60,
                (
                    f"Credit matched insurance provider alias '{alias}' with customer-payment or claim-payment "
                    "wording; an analyst decides whether it is revenue."
                ),
                context_signals=("credit_direction", "insurance_provider", "customer_payment_wording"),
            )
        return _RevenueDecision(
            "non_revenue",
            entity,
            "insurance_provider_credit_exclusion",
            alias,
            "insurance_proceeds_or_refund",
            0.99,
            f"Credit matched insurance provider alias '{alias}' and is not operating revenue.",
            context_signals=("credit_direction", "insurance_provider"),
        )
    if claim_entry and not HCCLAIMPMT_CLAIM_FIRST and _BLUE_PLAN_CLAIM_PAYER.search(_before_receiver(text)):
        return _RevenueDecision(
            "unverified_deposit",
            None,
            "insurer_customer_payment",
            None,
            "insurer_customer_payment_requires_review",
            0.60,
            "A Blue-plan claim payment is held with the insurer's credits until the owner rules on claim first.",
            context_signals=("credit_direction", "insurance_provider", "customer_payment_wording"),
        )
    # Spec §4.4 / D1: a credit from a financing group is proceeds. It is decided
    # before the operating-revenue registry, and group aliases are
    # financing-specific (SQUARE CAPITAL, never bare SQUARE), so a platform's
    # sales settlement still reaches the operating registry below. Card-issuer
    # and lease/rental payees never apply to credits, and neither does a
    # payout-credit entity.
    financing_match = _financing_proceeds_payee(lookup_text, account_name=account_name, holder_name=holder_name)
    if financing_match is not None:
        return _RevenueDecision(
            "non_revenue",
            financing_match.entity,
            "financing_proceeds_credit",
            financing_match.alias,
            "financing_proceeds_credit",
            0.99,
            (
                f"Credit matched maintained {_state_words(financing_match.state)} alias "
                f"'{financing_match.alias}'; financing proceeds are not revenue."
            ),
            context_signals=("credit_direction", "financing_proceeds"),
        )
    # D1 by descriptor (Square Capital's SQ CAP, SBA and EIDL). `_descriptor_proceeds` keeps the potential registry and
    # the strong non-revenue rule below ahead of a line-of-credit draw or a floor-plan advance.
    descriptor_proceeds = _descriptor_proceeds(text)
    if descriptor_proceeds is not None:
        rule, names_bank = descriptor_proceeds
        return _RevenueDecision(
            "non_revenue",
            (bank or None) if names_bank else None,
            "financing_proceeds_credit",
            None,
            rule,
            0.97,
            f"The credit's descriptor identifies financing proceeds ({_state_words(rule)}); they are not revenue.",
            context_signals=("credit_direction", "financing_proceeds"),
        )
    potential_lender_match = registry_match(lookup_text, POTENTIAL_LENDER_ALIASES)
    # §6.3, §5: a factoring review entity's credit is a factor's payout, never the potential tier's exclusion: it goes
    # on to the operating-revenue path, as an admitted factor's does.
    if potential_lender_match is not None and potential_lender_match[0] not in FACTORING_REVIEW_ENTITIES:
        entity, alias = potential_lender_match
        return _RevenueDecision(
            "non_revenue",
            entity,
            "potential_lender_registry_credit_exclusion",
            alias,
            "potential_lender_funding_credit",
            0.95,
            f"Credit matched potential lender alias '{alias}' and is excluded from revenue.",
            context_signals=("credit_direction", "potential_lender_source"),
        )
    # §6.3: a named sender after an own-account designation refuses the own-account patterns; such a credit is no sale
    # the text proves either, so no later step verifies it: the pass holds it (T13).
    named_after_designation = _named_sender_after_designation(text, holder)
    # §6.3: Snap's merchant funding printed with the strong LOAN word ('SNAP LOAN FUNDING F<digits> <merchant>') is a
    # lease-to-own financier's payout of the merchant's sale, which the true-revenue pass claims
    # (CUSTOMER_FINANCING_PAYERS): the strong rule reads the row without that form only. Every other reader (the
    # designation test above, the descriptor proceeds, the lender-credit reader) keeps the full text. §7.11: a company
    # name that holds LN ('LN TRUCKING LLC', 'CONTOSO LN HOLDINGS LLC'; description_text.ln_name_spans, read on the
    # printed description: no street, no loan word around it, no transfer wording) is read by the strong patterns with
    # the LOAN the normalizer made of its LN blanked, as Snap's form is, so the row reaches pass 7, whose financing root
    # holds it for review (financing_named_payer). Every other reader keeps the full text.
    strong_text = _SNAP_MERCHANT_FUNDING.sub(" ", text)
    for name, blanked in ln_name_spans(description or ""):
        strong_text = re.sub(
            r"(?<![A-Z0-9])" + re.escape(name) + r"(?![A-Z0-9])", lambda _found, kept=blanked: kept, strong_text
        )
    if (
        _matches_any(strong_text, _NON_REVENUE_CREDIT_PATTERNS) and not named_after_designation
    ) or _own_book_or_funds_transfer(text, holder):
        return _RevenueDecision(
            "non_revenue",
            None,
            "strong_non_revenue_rule",
            None,
            "non_operating_credit",
            0.97,
            (
                "Credit matched identifiable financing, own-account transfer, reward, "
                "interest, contribution, or other non-operating proceeds evidence."
            ),
            context_signals=("credit_direction", "strong_non_revenue_descriptor"),
        )
    if named_after_designation:
        return _fallback_credit_decision(text)

    # §6.1 step 9b, the channel gate: a consumer rail, a check, cash, branch or ATM deposit, or a row with no payer
    # word is never verified; a real-time or push rail is verified by the operating registry only.
    gate = channel_gate(text)
    if gate != "closed":
        source_text = _before_receiver(text) if gate == "push" else text
        source = _operating_source(source_text)
        if source is not None:
            return _operating_source_decision(text, source, account_name=account_name, bank=bank, holder=holder)
    if gate is not None:
        return _fallback_credit_decision(text)

    region = payer_region(text)
    form = _card_settlement_form(text, bank=bank)
    if form is not None and form.label != "net_settle":
        return _RevenueDecision(
            "verified_revenue",
            form.entity,
            "operating_income_descriptor",
            form.label,
            f"card_settlement_form_{form.label}",
            0.93,
            f"Credit prints the card-settlement form '{form.label}'.",
            source_type=OPERATING_REVENUE_SOURCE_TYPES.get(form.entity) if form.entity else None,
            context_signals=("credit_direction", "operating_income_descriptor", "card_settlement_form"),
        )
    joined = _joined_text(_before_receiver(text))
    # The customer and invoice descriptors never read the receiver field's value, the holder (§5.2); on a wire they
    # answer to the §7.9 wire vetoes as steps 12 and 14 do, and a vetoed row falls through.
    customer_or_invoice = (
        _matches_any(_without_receiver_value(text), _CUSTOMER_INVOICE_DESCRIPTORS)
        or _matches_any(joined, _CUSTOMER_INVOICE_DESCRIPTORS)
    ) and not (_wire_vetoes_apply(text) and _wire_vetoed(text, region, holder))
    if _matches_any(text, _VERIFIED_REVENUE_CREDIT_PATTERNS) or _matches_any(joined, _VERIFIED_REVENUE_CREDIT_PATTERNS):
        return _RevenueDecision(
            "verified_revenue",
            None,
            "operating_income_descriptor",
            None,
            "verified_operating_income_descriptor",
            0.93,
            "Credit has a merchant-settlement, card-sales, claim-payment, or verified business-deposit descriptor.",
            context_signals=("credit_direction", "operating_income_descriptor"),
        )
    guard = _refused_by_payer_guards(text, region, holder)
    if guard == "holder" and (
        customer_or_invoice
        or _payer_remittance(text, region, holder)
        or _public_payer_remittance(text) is not None
        or _wire_remittance_purpose(text, region, holder)
    ):
        return _RevenueDecision(
            "unverified_deposit",
            None,
            "holder_named_payer",
            None,
            "payer_prints_the_holders_name",
            0.40,
            "The payer prints the account holder's own name or brand, so its remittance wording is not proof.",
            context_signals=("credit_direction", "holder_named_payer"),
        )
    if guard is None:
        if customer_or_invoice:
            return _RevenueDecision(
                "verified_revenue",
                None,
                "operating_income_descriptor",
                None,
                "verified_operating_income_descriptor",
                0.93,
                "Credit has a customer-payment or invoice descriptor.",
                context_signals=("credit_direction", "operating_income_descriptor"),
            )
        if _payer_remittance(text, region, holder):
            return _RevenueDecision(
                "verified_revenue",
                None,
                "payer_remittance_descriptor",
                None,
                "verified_payer_accounts_payable_remittance",
                0.90,
                "The payer prints its accounts-payable remittance: the credit pays an invoice of the business.",
                context_signals=("credit_direction", "payer_remittance"),
            )
        public_rule = _public_payer_remittance(text)
        if public_rule is not None:
            return _RevenueDecision(
                "verified_revenue",
                None,
                "public_payer_remittance",
                None,
                public_rule,
                0.90,
                "A public payer pays a vendor or provider remittance of the business.",
                source_type="government_payer",
                context_signals=("credit_direction", "public_payer_remittance"),
            )
        if _wire_remittance_purpose(text, region, holder):
            return _RevenueDecision(
                "verified_revenue",
                None,
                "wire_remittance_purpose",
                None,
                "verified_wire_remittance_purpose",
                0.90,
                "The incoming wire's remittance cites an invoice, a purchase order, an order or goods.",
                context_signals=("credit_direction", "wire_remittance_purpose"),
            )
    return _fallback_credit_decision(text)


def _operating_source_decision(
    text: str,
    source: _OperatingSource,
    *,
    account_name: str | None,
    bank: str | None,
    holder: str | None = None,
) -> _RevenueDecision:
    """§6.1: a credit the operating registry names: verified with payout context, otherwise it needs recurrence or
    related activity. Property-management platforms and wholesale auctions never verify here: the recurrence pass
    decides them."""
    entity, alias, source_type = source.entity, source.alias, source.source_type
    business_account = _business_account(account_name)
    if platform_entry_leads_with_financing(text, entity, account_name if holder is None else holder):
        # §20: an entry field that leads with a financing word is the platform's own financing, never verified here;
        # pass 7 holds it as financing_named_payer (the registry does not claim a financing row).
        return _RevenueDecision(
            "unverified_deposit",
            entity,
            "operating_source_requires_context",
            alias,
            PLATFORM_FINANCING_ENTRY_RULE,
            0.50,
            (
                f"Credit matched maintained {source_type or 'operating-source'} alias '{alias}', but its entry field "
                "leads with a financing word: the platform's financing is never revenue."
            ),
            source_type=source_type,
            context_signals=("credit_direction", "maintained_operating_source", "financing_entry"),
        )
    has_context = source_type not in {"property_management_payments", "wholesale_auto_auction"} and (
        _has_operating_context(text, source, bank=bank)
    )
    signals = ["credit_direction", "maintained_operating_source"]
    if source.payout_form:
        signals.append("payout_form")
    if has_context:
        signals.append("settlement_or_payout_descriptor")
    if business_account:
        signals.append("business_account")
    if has_context:
        return _RevenueDecision(
            "verified_revenue",
            entity,
            "operating_source_with_credit_context",
            alias,
            "verified_operating_source_credit",
            0.98 if business_account else 0.96,
            (
                f"Credit matched maintained {source_type or 'operating-source'} "
                f"{'payout form' if source.payout_form else 'alias'} '{alias}' with settlement, payout, or deposit "
                "context."
            ),
            source_type=source_type,
            context_signals=tuple(signals),
        )
    return _RevenueDecision(
        "unverified_deposit",
        entity,
        "operating_source_requires_context",
        alias,
        "operating_source_without_payout_context",
        0.70,
        (
            f"Credit matched maintained {source_type or 'operating-source'} alias "
            f"'{alias}', but the row needs recurrence or related operating activity to verify revenue."
        ),
        source_type=source_type,
        context_signals=tuple(signals),
    )


def _fallback_credit_decision(text: str) -> _RevenueDecision:
    """§6.1 steps 15 and 16: deposit wording, else an unidentified posted credit."""
    if _matches_any(text, _UNVERIFIED_DEPOSIT_CREDIT_PATTERNS):
        return _RevenueDecision(
            "unverified_deposit",
            None,
            "ambiguous_credit_descriptor",
            None,
            "deposit_source_requires_review",
            0.60,
            "The credit is a deposit or incoming transfer without enough evidence to confirm operating revenue.",
            context_signals=("credit_direction", "generic_deposit_descriptor"),
        )
    return _RevenueDecision(
        "unverified_deposit",
        None,
        "unidentified_posted_credit",
        None,
        "unknown_credit_source_requires_review",
        0.40,
        "The posted credit source is not identified strongly enough to confirm or exclude revenue.",
        context_signals=("credit_direction", "unidentified_source"),
    )


#: OQ2 (true revenue spec §19) puts the five BNPL providers in PAYOUT_CREDIT_ENTITIES: a provider's settlement to the
#: merchant is the merchant's own sale, so revenue. It covers settlements only: a credit where the account holder is the
#: provider's customer, not its merchant (a Klarna WITHDRAWAL, a RETURN FOR ... PURCHASE), is not one. A credit of one of
#: the five that prints one of these consumer-side words (a return, a withdrawal, a refund, a balance, cash back, a
#: reward, a card product, a purchase, or the debt collector TRUEACCORD) stays D1. Sezzle, American First Finance and
#: PAYABILITY keep an entity-wide exception: the corpus prints WITHDRAWAL on Sezzle's merchant payouts and CARD on
#: PAYABILITY's transfers. Cherry Technologies joins PAYOUT_CREDIT_ENTITIES under the same consumer-side veto, so a
#: Cherry consumer credit (a refund, a card credit) keeps its D1 reading.
_OQ2_BNPL_ENTITIES = frozenset({"AFFIRM", "Afterpay", "GreenSky", "Klarna Inc", "Sunbit", "Cherry Technologies, Inc."})
#: Cherry joined the payout entities under OQ2's consumer-side veto only (Q8), so a Cherry loan or advance left D1;
#: it keeps D1 again, as before the Q8 ruling. The other OQ2 entities' LOAN readings are OQ2's.
_CHERRY_ENTITY = "Cherry Technologies, Inc."
_CHERRY_LOAN_CREDIT = re.compile(r"(?<![A-Z])LOANS?\b")


def _is_payout_credit(
    text: str, match: PayeeMatch, *, account_name: str | None = None, holder_name: str | None = None,
) -> bool:
    """Whether a credit of ``match`` is a payout-credit entity's settlement: revenue, not D1 financing proceeds.

    PAYOUT_CREDIT_ENTITIES; OQ2 (§19) narrowed to the five
    BNPL providers' settlements (_BNPL_CONSUMER_CREDIT). Credits only. A Cherry credit
    printing LOAN(S) or a non-sale or financing word (_PAYOUT_NON_SALE_CREDIT: an
    advance, capital, interest, a dividend, a rebate) is no settlement either: it keeps
    D1, its reading before the Q8 ruling. Those words are read as the true-revenue pass's
    veto reads them, without the receiver field's value and without the holder's names
    (true_revenue's without_receiver_and_holder on the statement's `account_name` and
    `holder_name`), so a practice whose own name prints CAPITAL, ADVANCE or INTEREST as
    an unlabelled receiver (Wells Fargo, TD, a generic ACH CREDIT) keeps its Cherry
    payouts.
    """
    if match.entity not in PAYOUT_CREDIT_ENTITIES:
        return False
    # Both sites read the same text: the revenue text (a glued leading date dropped) without the receiver's name, so
    # the holder's own name ('INDN:BALANCE DENTAL LLC') never makes a settlement consumer-side (§5.2).
    words = _without_receiver_value(revenue_text(text))
    if match.entity == _CHERRY_ENTITY and (_CHERRY_LOAN_CREDIT.search(words) or _PAYOUT_NON_SALE_CREDIT.search(words)):
        cherry = without_receiver_and_holder(revenue_text(text), account_name, holder_name)
        if _CHERRY_LOAN_CREDIT.search(cherry) or _PAYOUT_NON_SALE_CREDIT.search(cherry):
            return False
    return not (match.entity in _OQ2_BNPL_ENTITIES and _BNPL_CONSUMER_CREDIT.search(words))


def _financing_proceeds_payee(
    text: str, *, account_name: str | None = None, holder_name: str | None = None,
) -> PayeeMatch | None:
    """D1: the known payee whose credit is financing proceeds, or None.

    The credits of a payout-credit entity (PAYOUT_CREDIT_ENTITIES) are the account
    holder's own sales settled by the platform, so they are revenue; that entity's
    debits keep their group. A BNPL provider's consumer-side credit is not a
    settlement (OQ2, _is_payout_credit). A factoring payee's credits are the
    business's own sales paid by the factor, so they are revenue too, and they keep
    the factoring flag (_FLAGGED_REVENUE_CREDIT_STATES). `account_name` and
    `holder_name` are the statement's, which the Cherry veto of _is_payout_credit
    reads out of the row.
    """
    match = match_known_payee(text, credit=True)
    if (
        match is None
        or match.state not in FINANCING_STATES
        or match.state in _FLAGGED_REVENUE_CREDIT_STATES
        or _is_payout_credit(text, match, account_name=account_name, holder_name=holder_name)
    ):
        return None
    return match


#: The matched rule of an operating-registry credit whose entry leads with a financing word.
PLATFORM_FINANCING_ENTRY_RULE = "platform_entry_leads_with_financing"
