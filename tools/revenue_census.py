"""Revenue census over the local artifact cache or a copy of the tryout host's job store (true revenue spec §14.2).
Local only; never run in CI.

`snapshot` re-classifies every reconciled, de-duplicated cached analysis with the `analysis` package of one checkout
(`--code-root`) and records, per account, every posted credit's revenue decision (state, method, rule, tier, reason,
entity and alias (as-is when that checkout's registry or ledger tables name them, digit-masked otherwise), amount in
cents, the digit-masked normalized text) and, where the checkout has them, the guard facts of
§14.3 read with that checkout's readers. `compare` reads a base snapshot and one or two later ones and reports the
shares, the tiers and reasons, the move matrix, every row that left `non_revenue` (by the narrowing of §6.3 that moved
it), every verified row that lost its verification (by declared cause), the lender-credit and eligible-deposit moves
by cause, the package gate, and the guards G1 to G17 (G7 is tools/lender_census.py; G15 to G17 are the review's
refund, tax-refund and own-account-transfer guards). Every figure it prints is a count, a share or a total;
descriptors stay in the output file, digit-masked, outside the repository.

Usage, from the repository root of the checkout that holds this tool:
    python -m tools.revenue_census snapshot --data-dir <webapp_data> --out <file> [--code-root <checkout>] [--limit N]
                                            [--basis input|pdf]
    python -m tools.revenue_census snapshot --jobs-db <webapp.db copy> --out <file> [--code-root <checkout>]
                                            [--basis input|pdf]
    python -m tools.revenue_census compare --base <file> --after <file> [--after <file>] --out <file>
                                           [--admissions <the S1.5 admissions' signed-off entity list>]
    python -m tools.revenue_census sample --snapshot <5.6 file> --out <file>
    python -m tools.revenue_census sweep --snapshot <file> --out <file>

Every output is refused inside any repository: a path that is, or sits below, a folder holding a `.git` entry (S3.1
review). A guard whose facts the run's snapshot lacks is reported "not checked (facts arrive in 5.6)", never as held,
and the verdict counts the checked guards only.

`--basis` (S3.1): `input` (the default, the plan's census) reads the latest analysis of every cached analysis input.
An analysis input is a digest over the OCR markdown and its page partition (webapp.artifact_cache.analysis_input_sha),
so one PDF read by two OCR routes (native text, Tesseract, Paddle) that disagree by a byte is two inputs, and the
input basis counts it twice unless the two reads extract the same statement fingerprint. `pdf` reads one analysis per
source PDF: each PDF's OCR artifacts are re-hashed into the analysis inputs they are analysed under, and the newest
route that has an analysis is taken; an analysis no cached OCR artifact reaches (its OCR route is no longer cached) is
kept only when no statement already kept has its identity (bank, the account number's last four digits, the printed
period). Of a job store, `pdf` keeps each PDF's newest job. A snapshot records its basis, and `compare` refuses to
compare two bases.

B1 (audit I60): on every basis, among the analyses that read one statement (one fingerprint: bank, period, balances,
row count, account number), the snapshot keeps the newest-created, whatever order the reader yields them in (the input
basis reads the newest first); before B1 it kept the first in input-hash order, so a stale parse could win over a newer
one. Every account records its analysis stage (the leading digits of the settings key it was cached under, which
carries webapp.artifact_cache.ANALYSIS_STAGE_VERSION; the basis counts rank the stages by their first analysis), when it
was analysed and the parser route that published it (`model_used`). The snapshot maps each analysis it set aside to the
one it kept (`duplicates`), and lists apart the set-aside analyses whose parse differs from the kept one
(`stale_parses`). `compare` follows a base account the later run set aside to the analysis it kept, and compares one
whose parse differs apart, as a parse change, never as a rule's move.

B1 (audit I39): every summary carries the standing sweep of the non-revenue a credit's wording identifies inside True
(NON_REVENUE_IN_TRUE_CLASSES, classes A to H), so a regression shows as a number; class H, a government payment that
prints no purpose, is the owner's and is reported apart, never in the overstatement. `sweep` prints it for one snapshot.

`sample` draws §14.5's precision sample (up to 20 Verified rows of each stratum, the Verified rows the holder test
matches, and the 50 largest counted rows), digit-masked, with an empty `sort` for the reviewer.

Exit codes: snapshot, sample and sweep 0, or 2 when refused. compare 0 when every guard holds, 1 when one fails, 2 when
refused.
"""
from __future__ import annotations

import argparse
import functools
import gzip
import json
import os
import re
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
_DIGITS = re.compile(r"\d")

#: The non-revenue rules whose rows G1 follows (§14.3): reversal, insurer, D1, descriptor proceeds, potential
#: lender, strong non-revenue and duplicates.
NON_REVENUE_METHODS = frozenset({
    "reversal_cancellation_exclusion", "insurance_provider_credit_exclusion", "financing_proceeds_credit",
    "potential_lender_registry_credit_exclusion", "strong_non_revenue_rule", "duplicate_credit_exclusion",
    "matched_reversal_pair",
})
#: §6.3's narrowings, plus the owner's OQ2 ruling (BNPL settlements join PAYOUT_CREDIT_ENTITIES), in the order the
#: census tests them. Each is (name, whether it may lead to True).
NARROWINGS = (
    ("1_reimbursement_claim_signal", True),
    ("2_hcclaimpmt_insurer", True),
    ("3_insurer_customer_payment", False),
    ("4_book_or_funds_transfer", True),
    ("5_street_ln", True),
    ("6_card_credit_release", True),
    ("7_q7_dealer_funding", True),
    ("8_oq2_bnpl_settlement", True),
    # Audit B2 (I20): §6.3's narrowing 8 (the census lists OQ2's ruling eighth): a named sender printed after an
    # own-account designation leaves the strong non-revenue rule only to be held (T13), never into True.
    ("9_named_transfer_after_designation", False),
    # Audit B3 (I11): §6.3's narrowing 9: a merchant processor's instant payout printed as a card credit, beside the
    # processor's own ACH activity, leaves the reversal rule counted and flagged, never verified.
    ("10_processor_card_payout", True),
    # Audit B6 (I10): §6.3's narrowing 10: a factoring review entity's credit leaves the potential tier's exclusion,
    # counted and flagged as a factoring payout (the factoring ruling of 2026-09-26), never verified.
    ("11_factoring_review_payout", True),
    # Audit B8 (I46): §6.3's narrowing 11: a deposit whose non-revenue rule fired only on the statement furniture a
    # parser glued onto it is read alone, past the furniture (the revenue text's cut).
    ("12_statement_furniture", True),
)
#: The narrowings that lead to True only counted and flagged, never verified (audit B3: I11; audit B6: I10).
COUNTED_ONLY_NARROWINGS = frozenset({"10_processor_card_payout", "11_factoring_review_payout"})
#: Audit B3 (I11): the method the true-revenue pass gives a released processor card payout
#: (analysis/true_revenue.py PROCESSOR_CARD_PAYOUT_METHOD, copied: the census reads other checkouts).
PROCESSOR_CARD_PAYOUT_METHOD = "processor_card_payout"
#: Final review I8: the narrowings that lead to True only through verification (§6.3: a claim payment and a released
#: card credit are verified or held, never counted).
VERIFIED_ONLY_NARROWINGS = frozenset({"2_hcclaimpmt_insurer", "6_card_credit_release"})
#: OQ2 (§19): the five BNPL providers whose settlements left D1, by their ledger entity names.
BNPL_ENTITIES = frozenset({"AFFIRM", "Afterpay", "GreenSky", "Klarna Inc", "Sunbit"})
#: The declared causes of a verified row losing its verification (§7.0, §7.11, §7.7), and the two consequences of the
#: recurrence fixes this plan declares (Decisions): a pool that one of its members' re-reading splits between two
#: entities, and a pool left below the recurrence count once a declared veto takes a member out. S3.1 (the owner's
#: delegated review fixes of S2.2 and S2.3): a verified wire that the §7.9 wire vetoes now refuse (they read step 11's
#: descriptors on a wire, and a row whose reference is glued to WIRE), and a row whose verification read an operating
#: alias or a customer descriptor only inside the receiver field's value, the holder's name (§5.2). S3.1 review
#: (fix 2): the direction-conflict pool (§7.0), step 11's CUSTOMER with CHECK or CHEQUE (§7.11), the numbered-company
#: guard on steps 11 to 14 (§5.2, T11) and the S1.5 ledger admissions (D1). Each cause is declared only for the 5.4 rule
#: it governs and the 5.5 outcome it produces (_demotion_cause). Square Capital's SQ CAP is `sq_cap_or_sba` (the plan's
#: `square_capital` named no rule of its own and is gone). Any other cause fails.
#: True revenue final review I7: the table is the one the compare reads (a cause off it is undeclared and fails), and
#: it holds every §20 demotion, each keyed on the new state or reason and the rule that fires (_demotion_cause): the
#: factor never verified, a Q5 or Q6 row a later 5.6 hold names (the holder test, a personal trust, the holder's
#: currency conversion, a title firm, a bank-originated wire, a financing root, owner money) or whose relaying bank's
#: customer the payer region now reads, the premium-coded insurer entry, a short healthcare alias inside a business's
#: name, a §15 deferred source, a row left to its family, pass 6's counter debit, and the CRA refund among the new
#: non-revenue markers.
DECLARED_DEMOTIONS = (
    "square_payroll", "acctverify", "channel_gate", "holder_veto", "customer_id", "customer_check",
    "claim_first_off", "recurrence_veto", "sq_cap_or_sba", "new_non_revenue_marker", "reversal_pair",
    "entity_split", "direction_conflict_pool", "micro_deposit_floor", "pool_below_recurrence_after_a_declared_veto",
    "wire_veto", "receiver_value", "numbered_company", "ledger_admission",
    "factor_never_verified", "q5_q6_held_holder_name", "q5_q6_held_personal_trust", "q5_q6_held_currency_conversion",
    "q5_q6_held_title_firm", "q5_q6_held_bank_originated_wire", "q5_q6_held_financing_root",
    "q5_q6_held_owner_money", "q5_q6_relayed_customer", "premium_coded_insurer_entry",
    "short_healthcare_alias_in_a_name", "q5_q6_deferred_source", "q5_q6_left_to_its_family", "counter_debit",
    # Re-review N6: a platform credit whose entry field leads with a financing word.
    "platform_financing_entry",
    # GOV (the owner's ruling of 2026-09-30): a Q5 or Q6 row that is a government benefit (class B) or grant (class D).
    "q5_q6_held_government_benefit", "q5_q6_held_government_grant",
    # Audit B4 (I38, I22, I56): a Q5 or Q6 row whose payer a debit now names (§8.1's counter-debit holds).
    "q5_q6_held_counter_debit", "q5_q6_held_lender_counter_debit",
    # Audit B5 (I15, I55): a Q5 or Q6 repeat keyed on a bank's label, entry or reference, now that the payer region
    # reads the payer printed after it (or no payer, where only an empty label prints).
    "q5_q6_payer_after_a_label",
    # Audit B6 (I23): a Q5 or Q6 repeat of a bank that lends to small businesses, now held as financing.
    "q5_q6_held_lending_bank",
    # Audit B8 (I28, I44; the B7 review round 2's routing): a Q5 or Q6 row that is a gambling payout, a legal
    # settlement or an owner-shaped payer's DISB; (I46, Q2) a repeat that printed the plural TRANSFERS bare.
    "q5_q6_held_gambling_payout", "q5_q6_held_legal_settlement", "q5_q6_held_owner_disbursement",
    "q5_q6_bare_transfers",
)
#: Re-review N6: the matched rule the operating registry gives a credit whose entry leads with a financing word
#: (analysis/transaction_classifier.py PLATFORM_FINANCING_ENTRY_RULE, copied: the census reads other checkouts).
PLATFORM_FINANCING_ENTRY_RULE = "platform_entry_leads_with_financing"
#: §8.5, §8.6: the methods Q5 and Q6 verify with.
Q5_Q6_METHODS = frozenset({
    "repeat_wire_sender", "named_payer_repeats", "named_payer_company_form", "public_or_healthcare_payer",
})
#: I7: the 5.6 holds a Q5 or Q6 row can take (the reason, the pass's own hold reading true_revenue.guard_facts records
#: as `hold_rule`) and the cause each declares. The holder test's hold is its reason alone (its statement-level
#: receiver names are no row fact).
LATER_HOLD_CAUSES = {
    ("holder_name", None): "q5_q6_held_holder_name",
    ("non_sale_purpose", "personal_trust"): "q5_q6_held_personal_trust",
    ("non_sale_purpose", "currency_conversion"): "q5_q6_held_currency_conversion",
    ("non_sale_purpose", "title_firm"): "q5_q6_held_title_firm",
    ("non_sale_purpose", "owner_money"): "q5_q6_held_owner_money",
    ("financing_named_payer", "bank_originated_wire"): "q5_q6_held_bank_originated_wire",
    ("financing_named_payer", "financing_root"): "q5_q6_held_financing_root",
    # Audit B6 (I23): a bank that lends to small businesses, named as the payer.
    ("financing_named_payer", "lending_bank"): "q5_q6_held_lending_bank",
    # GOV (the owner's ruling of 2026-09-30): government money the business did not earn.
    ("personal_income", "government_benefit"): "q5_q6_held_government_benefit",
    ("non_sale_purpose", "government_grant"): "q5_q6_held_government_grant",
    # Audit B4 (I38, I22, I56): the counter-debit holds, which read the statement's debits (no row reading of their
    # own): the glued and spaced spellings of one name, a reference split off a name, a funder's cut name read by
    # prefix, a three-letter payroll provider.
    ("payer_also_debited", None): "q5_q6_held_counter_debit",
    ("payer_debited_as_lender", None): "q5_q6_held_lender_counter_debit",
    # Audit B8 (I28, I44; the B7 review round 2's routing): a gambling or prediction-market payout, a legal settlement,
    # and an owner-shaped payer's DISB.
    ("non_sale_purpose", "gambling_payout"): "q5_q6_held_gambling_payout",
    ("non_sale_purpose", "legal_settlement"): "q5_q6_held_legal_settlement",
    ("non_sale_purpose", "owner_disbursement"): "q5_q6_held_owner_disbursement",
}
#: The operating-registry methods (§8.9).
REGISTRY_METHODS = frozenset({
    "operating_source_requires_context", "operating_source_with_credit_context", "recurring_operating_source",
    "operating_source_related_activity", "wholesale_auction_payout_form",
})
#: G10: the methods that may verify a real-time or push-rail row (step 10, the registry, §6.1 step 9b).
REGISTRY_VERIFYING_METHODS = REGISTRY_METHODS - {"operating_source_requires_context"}
#: S3.1 review (fix 1): the methods a recurrence pass gives the rows it lifts (5.4 and 5.5).
RECURRENCE_LIFT_METHODS = frozenset({"recurring_operating_source", "operating_source_related_activity"})
#: S3.1 review (fix 1): a 5.4 recurrence pool's members as the 5.4 snapshot records them: the registry rows its pass
#: lifted, or left unlifted, and the direction conflicts it pooled with them (5.4 pooled every unverified row the
#: registry names, §7.0).
POOL_54_METHODS = RECURRENCE_LIFT_METHODS | {"operating_source_requires_context", "direction_conflict"}
#: S3.1 review (fix 1): the verified methods of steps 12 to 14 (§7.5, §7.6, §7.9), which a 5.5 base may hold.
STEPS_12_TO_14_METHODS = frozenset({"payer_remittance_descriptor", "public_payer_remittance", "wire_remittance_purpose"})
#: §7.0: the absolute micro-deposit floor, in cents.
MICRO_DEPOSIT_FLOOR_CENTS = 100
#: 5.6 (§8.10, S4.2 review I3): the reason pass 7 holds a credit under the floor with (analysis/true_revenue.py
#: _MICRO_DEPOSIT_REASON; §5.3's table has no micro-deposit code).
MICRO_DEPOSIT_FLOOR_REASON = "non_sale_purpose"
#: The demotion causes that read the account (the row's recurrence pool), not the row alone.
_POOL_CAUSES = frozenset({"entity_split", "pool_below_recurrence_after_a_declared_veto"})
#: S3.1 review (fix 3): the §14.3 facts each guard, or each arm of one, reads. A check whose facts no credit of the run
#: carries is reported "not checked", never as held, unless its guard recorded a failure, which always counts (S3.1
#: re-review): the facts of true_revenue.guard_facts arrive
#: in 5.6 (S4.2, S4.3). The pool, holder, numbered, gate and own-transfer facts are the S2.1 readers' (5.5).
GUARD_FACTS = {
    "G2": ("financing_root", "registry_root"),
    "G3": ("holder",),
    "G3 step 11": ("customer_descriptor",),
    "G4": ("transfer_no_counterparty",),
    "G5": ("known_financing", "payout_or_factoring"),
    "G10": ("gate",),
    "G11": ("pay_or_personal",),
    "G12": ("q7_payer_ok", "q7_veto_word", "q7_credit_union", "q7_listed"),
    "G13": ("numbered",),
    "G13 region": ("numbered_region",),
    "G13 step 11": ("customer_descriptor",),
    "G14": ("pool_candidate", "pool_vetoed", "pool_threshold"),
    "G14 per row": ("pooled_while_vetoed",),
    "G17": ("own_transfer",),
}
#: The checks that read no fact (a row's state, method, tier, amount or text), always checked; G9's tier identity
#: ("G9 tiers") is checked when the run carries tiers (5.6).
FACT_FREE_CHECKS = ("G1", "G6", "G7b", "G9", "G15", "G16", "undeclared_demotion")
NOT_CHECKED = "not checked (facts arrive in 5.6)"
#: G3: the rules that verify on the payer's identity or remittance (step 11's descriptors, steps 12 to 14, Q5, Q6).
IDENTITY_METHODS = frozenset({
    "payer_remittance_descriptor", "public_payer_remittance", "wire_remittance_purpose", "repeat_wire_sender",
    "named_payer_repeats", "named_payer_company_form", "public_or_healthcare_payer",
})
#: G9: the four tiers and the state each goes with (§5.4).
TIER_STATES = {"verified": {"verified_revenue"}, "non_revenue": {"non_revenue"},
               "counted_flagged": {"unverified_deposit"}, "excluded_pending_review": {"unverified_deposit"}}
#: G12: a credit union's dealer funding needs this many such credits in the statement (§8.7).
CREDIT_UNION_DEALER_MIN_CREDITS = 2
#: The snapshot skips that are the credit census's filter, not a failure (§14.2).
FILTER_SKIPS = frozenset({"unreconciled", "duplicate"})
#: S3.1: the snapshot bases (see the module docstring).
BASES = ("input", "pdf")
#: B1 (audit I60): the key under which the account readers hand the snapshot what the cache or the job store says of an
#: account's analysis (added on reading, never a key of a stored payload): when it was created and its stage.
CENSUS_META = "_census"
#: B1 (I60): the leading hex digits of a settings key (webapp.artifact_cache.analysis_settings_key, which carries
#: ANALYSIS_STAGE_VERSION) the census records as the analysis stage an account was cached under.
STAGE_PREFIX = 10
#: B1 (I60): a cut name prefix this long reads as the whole name (Chase cuts ORIG CO NAME at sixteen characters).
_CUT_NAME = 15
#: S3.1: §6.1 steps 15 and 16, where a credit lands when every rule before them refuses it.
FALLBACK_METHODS = frozenset({"ambiguous_credit_descriptor", "unidentified_posted_credit"})
#: S3.1 (wire_veto): the rules the §7.9 wire vetoes govern since the S2.3 review: step 11's customer and invoice
#: descriptors on a wire (before 5.5 inside operating_income_descriptor's verified_operating_income_descriptor rule),
#: the AP remittance (§7.5) and the invoice wire (§7.9).
WIRE_VETOED_METHODS = frozenset({"operating_income_descriptor", "payer_remittance_descriptor", "wire_remittance_purpose"})
#: S3.1: the rows the BNPL listing (addition 3) names one by one; every shape is counted.
BNPL_LISTED_ROWS = 50
_CLAIM_SIGNAL = re.compile(
    r"\b(?:MEDICAID|MEDICARE|MEDI CAL|TRICARE|CHAMPVA|GEMT|EMS|PROV(?:IDER)? ?PAY(?:MENTS?)?|EDI PYMNTS|CLAIM PMT)\b"
    r"|(?:\bH[CE]?|HC)CLAIMPMT"
)
#: The census's own readers (independent of the code under test): the receiver fields, the ACH originator fields.
_RECEIVER = re.compile(r"\b(?:INDN|IND NAME|IND ID|RECEIVER NAME)\b")
_ACH_FIELD = re.compile(r"\b(?:DES|CO ENTRY DESCR|ORIG CO NAME)\b")
#: S3.1 (receiver_value): a receiver field with its value, up to the next ACH field, as the classifier's
#: _CREDIT_RECEIVER_VALUE reads it (§5.2). Before 5.5 the operating alias and step 11 read the whole row, this value
#: (the holder's name) included.
_RECEIVER_VALUE = re.compile(
    r"\b(?:INDN|IND NAME|IND ID|RECEIVER NAME)\b.*?(?=\b(?:CO ID|TRN|TRACE|PPD|CCD|WEB|CTX|TEL|ARC|BOC)\b|$)"
)
#: S3.1 review: a classifier word boundary read on the digit-masked text. A masked digit ('#') is a word character, as
#: the digit was, so '####RTN' is not the word RTN (the classifier never read '1234RTN' as it).
_MASKED_BOUNDARY = r"(?:(?<![\w#])(?=[\w#])|(?<=[\w#])(?![\w#]))"


def _on_masked(pattern: str) -> re.Pattern[str]:
    """A classifier pattern (copied verbatim) read on the census's digit-masked text: \\d and \\w read '#', and \\b
    counts '#' as a word character. Not for patterns with \\w or \\d inside a character class."""
    return re.compile(
        pattern.replace(r"\d", r"[\d#]").replace(r"\w", r"[\w#]").replace(r"\b", _MASKED_BOUNDARY)
    )


#: S3.1 (receiver_value): classification 5.4's customer, invoice and receivable descriptors (its
#: _VERIFIED_REVENUE_CREDIT_PATTERNS), which it read on the whole row.
_PRE_55_CUSTOMER_DESCRIPTORS = tuple(_on_masked(pattern) for pattern in (
    r"\bCUSTOMER\b.*\b(?:ACH|PAYMENT|DEPOSIT|CHECK|CHEQUE)\b",
    r"\b(?:ACH|PAYMENT|DEPOSIT|CHECK|CHEQUE)\b.*\bCUSTOMER\b",
    r"\bINVOICE (?:PAYMENT|PAID|DEPOSIT)\b",
    r"\bACCOUNTS? RECEIVABLE\b",
))
#: S3.1 review (fix 1): classification 5.4's other verified descriptors (the rest of _VERIFIED_REVENUE_CREDIT_PATTERNS,
#: verbatim): merchant, card and marketplace settlements and the claim payment. A row they read is not step 11's
#: customer or invoice verification.
_PRE_55_OTHER_DESCRIPTORS = tuple(_on_masked(pattern) for pattern in (
    r"\bMRCH\d{5,}\b",
    r"\bMERCHANT (?:PROCESSOR )?(?:SETTLEMENT|DEPOSIT|PAYOUT)\b",
    r"\bCARD SALES? (?:DEPOSIT|SETTLEMENT|PAYOUT)\b",
    r"\bMARKETPLACE (?:PAYOUT|SETTLEMENT)\b",
    r"\bH(?:C|E)?CLAIMPMT\b",
    r"\bEDIRPAY\b",
    r"\bMERCHANT BANK(?:CD|CARD|ED) DEPOSIT\b",
    r"\bMTOT DEP\b",
))
_PRE_55_VERIFIED_DESCRIPTORS = _PRE_55_CUSTOMER_DESCRIPTORS + _PRE_55_OTHER_DESCRIPTORS
#: S3.1 review (customer_check): 5.4's customer descriptors as 5.5 reads them for CHECK and CHEQUE (§7.11: neither
#: CUSTOMER pattern accepts them, _CUSTOMER_INVOICE_DESCRIPTORS), CUSTOMER ID aside (customer_id has its own cause).
_CUSTOMER_WITHOUT_CHECK = tuple(_on_masked(pattern) for pattern in (
    r"^(?!.*\bCHE(?:CK|QUE)S?\b).*\bCUSTOMER\b.*\b(?:ACH|PAYMENT|DEPOSIT|CHECK|CHEQUE)\b",
    r"^(?!.*\bCHE(?:CK|QUE)S?\b).*\b(?:ACH|PAYMENT|DEPOSIT|CHECK|CHEQUE)\b.*\bCUSTOMER\b",
)) + _PRE_55_CUSTOMER_DESCRIPTORS[2:] + _PRE_55_OTHER_DESCRIPTORS
_CHECK_WORD = _on_masked(r"\bCHE(?:CK|QUE)S?\b")
_CUSTOMER_ID = _on_masked(r"\bCUSTOMER ID\b")
#: §7.11, 5.5 verbatim: the return codes that joined the reversal rule's credit markers
#: (_RETURN_CODE_CREDIT_PATTERNS), the tax-refund abbreviations and the account-verification words that joined the
#: strong non-revenue rule (_NON_REVENUE_CREDIT_PATTERNS).
_RETURN_CODES_55 = _on_masked(r"\b(?:RTN|RETN|RFND|REFND|RFD|RVSL|RVRSL|REVSL|RECALL(?:ED)?|UNPAID|REJT|CHBK|CHGBK)\b")
#: S4.2 fix round 4: CANCELLED's French words, which joined the reversal rule's credit markers
#: (_REVERSAL_CANCELLATION_CREDIT_PATTERNS, verbatim; 5.4 never read them). S4.2 fix round 5: their plurals too.
_FRENCH_REVERSAL_WORDS_55 = _on_masked(r"(?<![A-Z])(?:ANNUL|ANNULE|ANNULEE|ANNULES|ANNULEES|ANNULATION)\b")
#: Audit B3 (I04, §20): step 3's 5.6 return, correction and refund spellings (analysis/transaction_classifier.py
#: _RETURN_REFUND_CREDIT_PATTERNS, copied: the census reads other checkouts), on the masked text, which keeps a glued or
#: spaced leading date the classifier's revenue text drops before the forms printed first. REMBOURSEMENT's provider
#: carve-out only keeps rows out of the rule, so the word alone declares the rule's own demotion.
_LEADING_MASKED_DATE = r"^(?:#{1,2} #{1,2} ?)?"
#: B3 review round 1: the classifier's _NO_LEGAL_FORM_LATER (copied), which NOT PAID's, UNAUTHORIZED's, RECLAIM's, the
#: leading REV form's and RETOUR's narrowed readings use (never a company's name or a memo).
_NO_LEGAL_FORM_LATER = (
    r"(?!.*\b(?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|COMPANY|LTD|LTEE|LIMITED|LLP|LLLP|PLLC|ULC|PLC|GMBH)\b)"
)
_REVERSAL_MARKERS_56 = tuple(_on_masked(pattern) for pattern in (
    r"(?<![A-Z])ITEMS? RET(?:URNED)?\b(?! FEES?\b)",
    r"(?<![A-Z])(?:ITEMS?|RET|RETN|RTN|RETURN(?:ED)?) NOT PAID\b|" + _LEADING_MASKED_DATE + r"NOT PAID(?: \S*\d\S*)*$",
    r"\bRET(?:URN(?:ED)?)? DEP(?:OSIT(?:ED)?)? ITEMS?\b",
    r"\b(?:ERROR|TRANSACTION) CORRECTION\b",
    _LEADING_MASKED_DATE + r"CORRECTION(?![A-Z])",
    r"\bPURCHASE RET\b",
    r"\bDEBIT CARD CREDI\b",
    _LEADING_MASKED_DATE + r"CHECKCARD \d{4}\b",
    r"\bPOINT OF SALE DEPOSIT [A-Z]",
    r"\b(?:PROVISIONAL|TEMPORARY|CONDITIONAL) CR\b",
    r"\bUNAUTHORI[SZ]ED\b" + _NO_LEGAL_FORM_LATER,
    r"(?<![A-Z])RECLAIM(?=\d|\s*$)",
    _LEADING_MASKED_DATE + r"REV (?:MOBILE|POS|DEBIT|PURCHASE|ACH|CARD)\b(?:(?= (?:MOBILE|POS|DEBIT|PURCHASE|ACH|CARD"
    r"|CREDIT|PMT|PAYMENT|TRANSACTION|TXN|WITHDRAWAL)\b| ?\d|\s*$)|" + _NO_LEGAL_FORM_LATER + ")",
    r"(?<![A-Z])(?:RENV|RENVERSEMENT|REMBOURSEMENT)\b",
    r"(?<![A-Z])RETOUR\b(?:(?= ?\d| MDSE\b| MARCHANDISE\b|\s*$)|" + _NO_LEGAL_FORM_LATER + ")",
    r"\bFEES? WAIVE[DR]?\b",
    r"\bCOURTESY REF(?:UND)?\b",
))
#: Audit B3 (I43, §20): the card-rewards redemptions that joined the strong non-revenue rule (the classifier's, copied):
#: Chase's whole-row CASH REDEMPTION, PNC's PURCHASE PAYBACK [AWARD], POINTS REDEMPTION and Membership Rewards' words
#: (the classifier reads the last only beside a card issuer's name; the method keys the cause).
_REWARD_REDEMPTIONS_56 = tuple(_on_masked(pattern) for pattern in (
    _LEADING_MASKED_DATE + r"CASH REDEMPTION(?: \S*\d\S*)*$",
    r"\bPURCHASE PAYBACK(?: AWARD)?\b",
    r"\bPOINTS REDEMPTION\b",
    r"\b(?:MR REDEEM|MEMBERSHIP REWARDS?)\b",
))
_TAX_REFUNDS_55 = _on_masked(r"\bTAX ?REF(?:UND)?S?\b|[A-Z]*TAXRFD\b|\bTAX RFD\b|\bTAXEIC\b")
#: 5.6 (§20, A3-G): the Canada Revenue Agency's income-tax refund forms, which joined the strong non-revenue rule.
_CRA_REFUND_56 = _on_masked(r"\bCANADA RI[TF]\b")
#: 5.6 (§20, GOV: the owner's ruling of 2026-09-30, class C): a business's GST/HST refund as the whole payer (the CRA's
#: and Revenu Quebec's forms, a posting code or a reference after it), and a payment the IRS issues through the Treasury,
#: which joined the strong non-revenue rule. GOV review (M3): the words before the form mirror the classifier's, copied
#: (the census reads other checkouts): its template prefixes (_REVENUE_TEMPLATE_PREFIX) and the posting words it strips
#: before a government's form (_CRA_POSTING_PREFIX: a glued or spaced date, GC and its number, EFT, PAY ...); (M4) the
#: forms take the CRA's name, a country code and the GST program account after them (_GST_REFUND_PAYER).
_GOVERNMENT_FORM_PREFIX_56 = (
    r"^(?:(?:BUSINESS TO BUSINESS ACH CREDIT|CCD DEPOSIT|CTX DEPOSIT|ELECTRONIC DEPOSIT FROM|ELECTRONIC DEPOSIT"
    r"|ELECTRONIC CREDIT|ACH CORP CREDIT|ACH DEPOSIT|ACH CREDIT|DEPOSIT FROM|PREAUTHORIZED CREDIT|EFT CREDIT"
    r"|DIRECT DEPOSIT|MISC PAYMENT|BILL PAYMENT) )*"
    r"(?:\d+(?: |(?=[A-Z])))*(?:(?:GC|DIRECT DEPOSIT|DIRECT DEP|DEPOSIT|DEP|ELECTRONIC DEPOSIT"
    r"|EFT(?: CREDIT| DEPOSIT)?|MISC PAYMENT|PAY(?:MENT)?(?: FROM)?) (?:\d+(?: |(?=[A-Z])))*)*"
)
_GOVERNMENT_TAX_REFUNDS_56 = _on_masked(
    _GOVERNMENT_FORM_PREFIX_56
    + r"(?:CANADA GST(?: TPS)?(?: CANADA)?|GST(?: TPS)? CANADA(?: CA)?|RQ GST)(?: (?:MSP|DIV|RT\d{4}|\d+))*$"
    r"|(?<![A-Z])IRS TREAS ?\d{3}\b"
)
#: Audit B2 (I20, §6.3 narrowing 8, the census's ninth): the two layouts that print a named sender after an
#: own-account designation (analysis/transaction_classifier.py _NAMED_DESIGNATION_TRANSFERS, copied: the census reads
#: other checkouts), read on the masked text: Bank of America's 'ONLINE|MOBILE [BANKING] TRANSFER FROM CHK|SAV <n>
#: CONFIRMATION <reference> <sender>' and a credit union's 'TFR FROM X...<n> TRANSFER DEPOSIT <sender>', the sender
#: printing a word of three letters or more.
_NAMED_DESIGNATION_TRANSFERS_56 = (
    _on_masked(r"\b(?:ONLINE|MOBILE) (?:BANKING )?TRANSFER FROM (?:CHK|SAV) \d+ CONFIRMATION \S+ (?=.*[A-Z]{3})\S.*$"),
    _on_masked(r"\bTFR FROM X+\d* TRANSFER DEPOSIT (?=.*[A-Z]{3})\S.*$"),
)
#: Audit B8 (I46, §6.3 narrowing 11, the census's twelfth): the statement furniture the classifier's revenue text cuts
#: (analysis/transaction_classifier.py _STATEMENT_FURNITURE, copied: the census reads other checkouts), on the masked
#: text: TD's footer and back panel, a Symitar credit union's balance, check-recap and fee summaries, a page header,
#: Citizens' continued-page header and footer, Fifth Third's disclosure line and a page number.
_STATEMENT_FURNITURE_56 = _on_masked(
    r"(?<![A-Z])(?:"
    r"CALL \d \d{3} \d{3} \d{4} FOR \d{2} HOUR BANK BY PHONE\b"
    r"|BANK DEPOSITS FDIC INSURED\b"
    r"|HOW TO BALANCE YOUR ACCOUNT\b"
    r"|(?:\d+ )*ENDING BALANCE (?=CLEARED CHECK RECAP\b|YOUR MINIMUM BALANCE\b)"
    r"|CLEARED CHECK RECAP\b"
    r"|FEE SUMMARY THIS PERIOD\b"
    r"|THIS PERIOD YEAR TO DATE TOTAL (?:OVERDRAFT|RETURNED ITEM) FEES\b"
    r"|(?:\d{1,3} )?STATEMENT OF ACCOUNT\b(?=.*\bSTATEMENT PERIOD\b)"
    r"|PLEASE SEE ADDITIONAL INFORMATION ON NEXT PAGE\b"
    r"|MEMBER FDIC(?: (?:[A-Z]|\d))? EQUAL HOUSING LENDER\b"
    r"|CONTINUED DEPOSITS AND CREDITS\b|DEPOSITS AND CREDITS CONTINUED\b"
    r"|FOR ADDITIONAL INFORMATION AND ACCOUNT DISCLOSURES\b"
    r"|(?:\d{3} R\d \d{2}F\d{3} )?(?:PAGE \d+ )?PAGE \d+ OF \d+\b"
    r")"
)
#: Audit B8 (I46): the base methods the furniture fired: the strong non-revenue rule (a footer's LOAN or INTEREST
#: EARNED) and the reversal rule (a fee summary's RETURNED ITEM).
_FURNITURE_BASE_METHODS = frozenset({"strong_non_revenue_rule", "reversal_cancellation_exclusion"})
#: Audit B8 (I46, Q2): the plural TRANSFERS, transfer wording since B8 (the classifier's _TRANSFER_WORDING).
_TRANSFERS_WORD = _on_masked(r"(?<![A-Z])TRANSFERS\b")
#: I8 (narrowing 8): the consumer-side words a BNPL provider prints on a customer's own credit (a return, a refund, a
#: withdrawal of a balance, a card, a debt collector), never on its merchant settlement (the OQ2 ruling's rows).
_BNPL_CONSUMER_WORDS = re.compile(
    r"(?<![A-Z])(?:AFFIRMCARD|AFFIRM CARD|SP AFF|TRUEACCORD|BALANCE WITHDRAW\w*|WITHDRAW\w*|REFUND\w*|RFND|REFND|RFD"
    r"|RETURN\w*|REVERS\w*|CASH ?OUT|CARD|PAYOFF|COLLECTIONS?)\b"
)
#: I8 (narrowing 5, G7b): the base methods that read a LOAN, and §7.11's street-LN guard read on the masked text: LN
#: after a number and one to three alphabetic words, none a loan-product word, and before no loan-payment word.
LOAN_READING_METHODS = frozenset({
    "strong_non_revenue_rule", "financing_proceeds_credit", "potential_lender_registry_credit_exclusion",
})
_LOAN_PRODUCT_WORDS = frozenset("""
COMMERCIAL COMM AUTO BUSINESS BUS TERM PERSONAL MORTGAGE MTG EQUIPMENT EQUIP INSTALLMENT INSTL CONSUMER HOME HELOC
STUDENT VEHICLE SBA BRIDGE CONSTRUCTION LINE CML COML SB VEH EIDL PPP LOC CRE MORT CREDIT PERS INST CONS EQUITY
""".split())
_LOAN_PAYMENT_WORDS = frozenset("""
PMT PMTS PYMT PYMTS PAYMENT PAYMENTS PAYMT PAYMNT PMNT PYMNT REPAYMENT REPAYMENTS DISB DISBURSEMENT ADV ADVANCE
PROCEEDS DRAW
""".split())
_ACCOUNT_VERIFICATION_55 = _on_masked(r"\bACCT ?VERIFY\w*\b|\bMICRO ?DEPOSITS?\b|\bPENNY TEST\b|\bTRIAL DEPOSITS?\b")
#: §7.7: 5.4's claim-payment descriptor, and 5.5's claim entry (glued on either side).
_CLAIM_54 = _on_masked(r"\bH(?:C|E)?CLAIMPMT\b")
_CLAIM_55 = _on_masked(r"(?:\bH[CE]?|HC)CLAIMPMT(?:SEC)?\b")
#: §7.0 (square_payroll): Square named as a word, and the pay words of the recurrence veto.
_SQUARE_WORD = _on_masked(r"\b(?:SQ|SQUARE)\b")
_PAY_WORD = re.compile(r"(?<![A-Z])(?:PAYROLL|PAYRL|DIR ?DEP|DIRECT DEP|SALAR|WAGE|BONUS)")
#: §7.0 (recurrence_veto): the recurrence veto's words, read on the digit-masked row before its receiver fields when a
#: snapshot carries no `recurrence_veto_wording` fact (a checkout before 5.5). S2.2 review (item A): a veto word of four
#: letters or more (all its words counted) reads through a glued digit, (?<![A-Z]) (a masked digit is '#'); a word of
#: three letters or fewer keeps the classifier's \b on the unmasked row, which (?<![A-Z#]) is on the masked one (a
#: digit glued to it is an ID's suffix, 'ID 1234FIN').
_RECURRENCE_VETO_WORDS = re.compile(
    r"(?<![A-Z])(?:LOANS?\b|CAPITAL\b|CAPI(?:T|TA)?\b|CAPSEC\b|ADVANCE\b|CASH ADV|FINANC|LEND|PAYROLL|PAYRL|DIR ?DEP"
    r"|DIRECT DEP|SALAR|WAGE|NET ?PAY|BONUS|REIMB|VERIF|INSUR|DEBIT CARD CREDIT|POS CREDIT)"
    r"|(?<![A-Z#])(?:CAP#*(?:SEC)?|ADV|FIN|MCA)\b"
)
#: §7.0 (review C2): FUNDING vetoes recurrence too, except on the settlements of the platforms that print it there.
_FUNDING_WORDS = re.compile(r"(?<![A-Z])(?:FUNDING|FUNDED)\b")
_FUNDING_SETTLEMENT_ENTITIES = frozenset({"TapGoods Payments", "Braintree", "Buildium"})
#: G15 (review C1): a refund word, glued or not.
_REFUND_WORD = re.compile(r"[A-Z]*REFUND\w*|\bRFND\w*|\bREFND\w*|\bRFD\b")
#: G16 (review I6): a tax refund or an earned-income credit, glued or not.
_TAX_REFUND_WORD = re.compile(r"[A-Z]*TAXRFD\b|\bTAX ?REF\w*|\bTAX ?EIC\b|\bTAX RFD\b")
#: S3.1 (addition 3): the words a BNPL row's public shape keeps. A word that holds a BNPL provider's name or a debt
#: collector's (AFFIRMCARD, TRUEACCORD) is kept whole; so are the registry's other BNPL alias words (SP AFF, AFFIRM
#: COM, AFFIRM PAY, AFFIRM CANADA), the consumer-side words S3.2 looks for, and the banks' channel, field and template
#: words. Any other word (a person's or a private business's name) prints '*', and a word that holds a digit '#'.
_PUBLIC_NAME = re.compile(r"AFFIRM|AFTERPAY|GREENSKY|KLARNA|SUNBIT|TRUEACCORD")
_PUBLIC_WORDS = frozenset({
    # The registry's BNPL alias words, and the consumer-side forms' words.
    "SP", "AFF", "COM", "PAY", "CANADA", "CARD", "BALANCE", "WITHDRAWAL", "WITHDRAW", "REFUND", "REFUNDS", "RFND",
    "REFND", "RFD", "RETURN", "RETURNED", "REVERSAL", "LOAN", "LOANS", "FUNDING", "FUNDED", "FINANCING", "FINANCE",
    "CAPITAL", "CASHOUT", "INSTANT", "PURCHASE", "POS", "PAYOFF", "COLLECTION", "COLLECTIONS",
    # The banks' ACH, wire and transfer fields and template words.
    "ACH", "CCD", "PPD", "WEB", "CTX", "TEL", "SEC", "DES", "DESC", "DESCR", "INDN", "IND", "ID", "NAME", "CO",
    "ORIG", "ENTRY", "DATE", "TRN", "TRACE", "EED", "REF", "RMR", "OBI", "BNF", "PMT", "DET", "INFO", "RECEIVER",
    "CREDIT", "CR", "DEBIT", "DR", "DEPOSIT", "DEP", "PAYMENT", "PAYMENTS", "PYMT", "PMNT", "RCVD", "RECEIVED",
    "PAYOUT", "PAYOUTS", "SETTLEMENT", "SETTLEMENTS", "SETTLEMNT", "SETTLE", "SETL", "STLMT", "SETTL", "TRANSFER",
    "XFER", "TFR", "FUNDS", "FUND", "DISBURSEMENT", "DISB", "ELECTRONIC", "EFT", "CORP", "CORPORATE", "BUSINESS",
    "MERCHANT", "MERCH", "WIRE", "FEDWIRE", "TYPE", "IN", "OUT", "BOOK", "DIRECT", "MISC", "ONLINE", "INTERNET",
    "BANKING", "BANK", "PREAUTHORIZED", "PREAUTH", "RTP", "REAL", "TIME", "SAME", "DAY", "FROM", "TO", "FOR", "BY",
    "OF", "THE", "AND", "INC", "LLC", "LTD", "CORPORATION", "COMPANY", "USA", "US", "NA", "VIA", "SALE", "SALES",
})


def mask(text: object) -> str:
    return _DIGITS.sub("#", " ".join(str(text or "").split()))


#: S3.1 privacy fix: the alias tables of the snapshot's `analysis.classification_registry` (entity -> aliases, or group
#: -> such a table) whose entities and aliases a credit's record writes as-is: the operating registry (its 5.4 name and
#: its sixteen-character cuts), the payee registries (the known-payee groups and the other ledger-generated tables),
#: the insurers the insurance rule reads and Q7's auto lenders. A table the checkout lacks (`--code-root` may be older
#: code) is skipped.
_NAME_TABLES = (
    "OPERATING_REVENUE_SOURCE_ALIASES", "VERIFIED_REVENUE_ALIASES", "OPERATING_REVENUE_READ_ALIASES",
    "PAYEE_GROUP_REGISTRIES", "POTENTIAL_LENDER_ALIASES", "PREMIUM_FINANCE_ALIASES", "DEBT_RELIEF_ALIASES",
    "BANK_NAME_ALIASES", "CARD_ISSUER_CONTEXT_ALIASES", "BANK_SPECIFIC_LENDER_ALIASES", "INSURANCE_PROVIDER_ALIASES",
    "DEALER_FUNDING_PAYERS",
)


def _registry_names(table: object) -> Iterator[str]:
    """The entities and aliases of one alias table (entity -> aliases), or of a table of them (group -> table)."""
    if not isinstance(table, dict):
        return
    for key, value in table.items():
        if isinstance(value, dict):
            yield from _registry_names(value)
        elif isinstance(key, str) and isinstance(value, (tuple, list, set, frozenset)):
            yield key
            yield from (alias for alias in value if isinstance(alias, str))


@functools.lru_cache(maxsize=4)
def _known_names(registry: ModuleType) -> frozenset[str]:
    """S3.1 privacy fix: every name the snapshot's code holds in a registry or ledger table, which a credit's entity or
    alias may be: the alias tables (_NAME_TABLES), the payout-credit entities, the platform payout forms (entity and
    label) and the card-settlement forms (label and processor)."""
    names = set()
    for table in _NAME_TABLES:
        names.update(_registry_names(getattr(registry, table, None)))
    names.update(name for name in getattr(registry, "PAYOUT_CREDIT_ENTITIES", ()) if isinstance(name, str))
    payout_forms = getattr(registry, "OPERATING_SOURCE_PAYOUT_FORMS", None)
    for entity, forms in (payout_forms.items() if isinstance(payout_forms, dict) else ()):
        names.add(entity)
        names.update(form[0] for form in forms if isinstance(form, (tuple, list)) and form and isinstance(form[0], str))
    for form in getattr(registry, "CARD_SETTLEMENT_CREDIT_FORMS", ()):
        names.update(name for name in (getattr(form, "label", None), getattr(form, "entity", None))
                     if isinstance(name, str))
    return frozenset(names)


def _published_name(name: str | None, known: frozenset[str]) -> str | None:
    """S3.1 privacy fix: a credit's entity or alias as the census writes it: as-is when the snapshot's code holds it in
    a registry or ledger table (_known_names), since the census compares those by name (the S1.5 admissions' Shift4
    Capital, the operating entities Shift4 and 11-101 Signal R); any other name digit-masked, like every other text
    (S4.3: Q7's credit-union arm names the credit union from the payer region; D1's bank line advance names the
    statement's bank)."""
    if name is None:
        return None
    return name if name in known else mask(name)


def _same_name(left: str | None, right: str | None) -> bool:
    """S3.1 privacy fix: whether two snapshots' names are one name. Equal names are; so are two whose masked forms are
    equal when either holds a masked digit ('#'): a name no registry holds, which a snapshot written before the fix
    holds unmasked. No registry name holds '#', so two registry names compare exactly as before."""
    if left == right:
        return True
    if not left or not right:
        return False
    return ("#" in left or "#" in right) and mask(left) == mask(right)


def public_shape(text: object) -> str:
    """S3.1 (addition 3): a row's public shape: digits masked, the public words kept (_PUBLIC_WORDS, a BNPL provider's
    or a debt collector's name), a word that holds a digit printed '#', any other word '*', and a run of one mark
    printed once."""
    words: list[str] = []
    for token in mask(text).split():
        if _PUBLIC_NAME.search(token) or token in _PUBLIC_WORDS:
            word = token
        elif "#" in token:
            word = "#"
        else:
            word = "*"
        if not (word in {"#", "*"} and words and words[-1] == word):
            words.append(word)
    return " ".join(words)


def _before_receiver(text: str) -> str:
    return _RECEIVER.split(text, 1)[0]


def _account_payloads(node: object) -> Iterator[dict]:
    """Every account payload (a dict whose `statement` holds a `transactions` list), in order."""
    if isinstance(node, dict):
        statement = node.get("statement")
        if isinstance(statement, dict) and isinstance(statement.get("transactions"), list):
            yield node
            return
        for value in node.values():
            yield from _account_payloads(value)
    elif isinstance(node, list):
        for value in node:
            yield from _account_payloads(value)


def _read_only(database: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)


def _artifact(data_dir: Path, relative: str) -> dict | None:
    """A cached artifact's payload, or None when it cannot be read. The index stores the path with the separators of
    the host that wrote it (a Windows cache stores backslashes)."""
    try:
        payload = json.loads((data_dir / "artifacts" / relative.replace("\\", "/")).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _stage(settings_key: object) -> str | None:
    """B1 (I60): an analysis's stage as the census records it: its settings key's leading digits."""
    return str(settings_key)[:STAGE_PREFIX] if settings_key else None


def _current_stages() -> frozenset[str] | None:
    """B1 (I60): the settings keys this checkout caches a deterministic or an automatic analysis under, or None when it
    cannot derive them (an older checkout, or a settings error)."""
    try:
        from webapp.artifact_cache import analysis_settings_key

        return frozenset(analysis_settings_key(parse_mode=mode) for mode in ("deterministic", "auto"))
    except Exception:  # noqa: BLE001  (informational only)
        return None


def _analysis_stages(connection: sqlite3.Connection) -> dict:
    """B1 (I60): every stage the cache's analyses were made under (stage -> its generation, 1 for the stage whose first
    analysis is the oldest; the day of that first analysis; its analyses; whether it is this checkout's stage)."""
    rows = connection.execute(
        "SELECT settings_key, MIN(created_at), COUNT(*) FROM artifact_cache WHERE stage = 'analysis'"
        " GROUP BY settings_key ORDER BY MIN(created_at), settings_key"
    ).fetchall()
    current = _current_stages()
    return {
        _stage(key): {"generation": number, "first_created": str(first)[:10], "analyses": count,
                      "current": None if current is None else key in current}
        for number, (key, first, count) in enumerate(rows, start=1)
    }


def _with_meta(account: dict, created: object, settings_key: object = None) -> dict:
    """B1 (I60): the account payload with what its reader knows of its analysis (CENSUS_META)."""
    account[CENSUS_META] = {"created": None if created is None else str(created), "stage": _stage(settings_key)}
    return account


def cached_accounts(
    data_dir: Path, limit: int | None = None, *, basis: str = "input", stats: dict | None = None
) -> Iterator[tuple[str, dict]]:
    """(id, account payload) for the latest cached analysis of each input (basis `input`, the newest analyses first:
    B1, I60), or of each source PDF (basis `pdf`, S3.1); the cache is opened read-only. `stats`, when given, receives
    the basis's counts and the cache's analysis stages."""
    if basis not in BASES:
        raise ValueError(f"unknown basis {basis!r}")
    stats = {} if stats is None else stats
    connection = _read_only(data_dir / "webapp.db")
    try:
        latest = connection.execute(
            "SELECT a.input_sha256, a.artifact_path, a.created_at, a.settings_key FROM artifact_cache a JOIN ("
            " SELECT input_sha256, MAX(created_at) AS newest FROM artifact_cache"
            " WHERE stage = 'analysis' GROUP BY input_sha256) b"
            " ON a.input_sha256 = b.input_sha256 AND a.created_at = b.newest"
            " WHERE a.stage = 'analysis' ORDER BY a.created_at DESC, a.input_sha256, a.settings_key"
        ).fetchall()
        stats["analysis_stages"] = _analysis_stages(connection)
        routes: dict[str, list[str]] = defaultdict(list)
        if basis == "pdf":
            # Each PDF's OCR artifacts (one per route), newest first.
            for pdf, relative in connection.execute(
                "SELECT input_sha256, artifact_path FROM artifact_cache WHERE stage = 'ocr'"
                " ORDER BY input_sha256, created_at DESC, cache_key"
            ):
                routes[pdf].append(relative)
    finally:
        connection.close()
    # B1 (I60): one analysis per input (two cached at one instant under two settings: the first in the order above).
    unique: dict[str, tuple[str, str, str]] = {}
    for sha, relative, created, settings in latest:
        unique.setdefault(sha, (relative, created, settings))
    stats["analysis_inputs"] = len(unique)
    if basis == "pdf":
        yield from _pdf_accounts(data_dir, unique, routes, limit, stats)
        return
    for number, (sha, (relative, created, settings)) in enumerate(unique.items()):
        if limit is not None and number >= limit:
            return
        payload = _artifact(data_dir, relative)
        if payload is None:
            continue
        for index, account in enumerate(_account_payloads(payload.get("artifact"))):
            yield f"c{sha[:12]}.{index}", _with_meta(account, created, settings)


def _analysis_inputs_of(document: dict) -> list[str]:
    """S3.1: the analysis inputs an OCR artifact's document is analysed under, by the one derivation of them
    (webapp.artifact_cache.analysis_input_sha, over the markdown and the page partition): text-only, and fed the
    native evidence the document carries (P22-IDENTITY), if it carries any."""
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import analysis_input_sha

    pages = [str(page) for page in document.get("pages") or []]
    markdown = StatementMarkdown(
        source_file="census.pdf", model=str(document.get("model") or ""), pages=pages
    ).to_markdown()
    shas = [analysis_input_sha(markdown, pages)]
    native = document.get("native_evidence_sha256")
    if isinstance(native, str) and len(native) == 64:
        try:
            shas.append(analysis_input_sha(markdown, pages, evidence_sha256=native))
        except (TypeError, ValueError):
            pass
    return shas


def _statement_identity(account: dict) -> tuple | None:
    """S3.1 (the pdf basis): a statement's identity read from its payload: the bank, the account number's last four
    digits and the printed period. None when the payload prints no period or fewer than four account digits: such an
    account is never merged with another."""
    statement = account.get("statement") or {}
    digits = re.sub(r"\D", "", str(statement.get("account_number") or ""))
    start, end = statement.get("period_start"), statement.get("period_end")
    if len(digits) < 4 or not start or not end:
        return None
    return " ".join(str(statement.get("bank") or "").upper().split()), digits[-4:], str(start), str(end)


def _reconciles(payload: dict) -> bool:
    """S3.1 review: an analysis passes the snapshot's filter when every account it holds reconciles."""
    accounts = list(_account_payloads(payload.get("artifact")))
    return bool(accounts) and all(bool((account.get("reconciliation") or {}).get("ok")) for account in accounts)


def _pdf_route(
    data_dir: Path, latest: dict[str, tuple[str, str, str]], candidates: list[tuple[str, int]]
) -> tuple[str, int, dict | None, bool]:
    """S3.1 review: of a PDF's analysed routes (newest first), the newest whose analysis reconciles (passes the
    snapshot's filter); the newest when none does. (sha, route position, payload, reconciles)."""
    newest: tuple[str, int, dict | None] | None = None
    for sha, position in candidates:
        payload = _artifact(data_dir, latest[sha][0])
        if newest is None:
            newest = (sha, position, payload)
        if payload is not None and _reconciles(payload):
            return sha, position, payload, True
    assert newest is not None
    return (*newest, False)


def _pdf_accounts(
    data_dir: Path, latest: dict[str, tuple[str, str, str]], routes: dict[str, list[str]], limit: int | None,
    stats: dict,
) -> Iterator[tuple[str, dict]]:
    """S3.1: the pdf basis. Each PDF (in hash order) yields the latest analysis of one analysis input its OCR routes
    are analysed under, once (two PDFs that read to one markdown share one analysis, which the first yields): the
    newest route whose analysis reconciles, or the newest analysed route when none does (S3.1 review). Then every
    analysis input no cached OCR route reaches (an orphan: its route is no longer cached), newest first, yields each
    account whose statement identity no account yielded before holds (an account without an identity is always
    yielded). `limit` caps the analyses read."""
    for name in ("pdfs_joined", "pdfs_joined_on_newest_route", "pdfs_on_an_older_reconciling_route",
                 "pdfs_without_a_reconciling_route", "pdfs_without_an_analysis", "pdfs_sharing_an_analysis",
                 "analysis_inputs_joined", "orphan_inputs", "orphan_accounts_kept",
                 "orphan_accounts_matching_a_kept_statement", "orphan_accounts_without_identity"):
        stats[name] = 0
    stats["pdfs"] = len(routes)
    reached: set[str] = set()
    taken: set[str] = set()
    identities: set[tuple] = set()
    read = 0
    for pdf in sorted(routes):
        candidates: list[tuple[str, int]] = []
        for position, relative in enumerate(routes[pdf]):
            document = ((_artifact(data_dir, relative) or {}).get("artifact") or {}).get("document")
            if not isinstance(document, dict):
                continue
            for sha in _analysis_inputs_of(document):
                if sha in latest:
                    reached.add(sha)
                    if all(sha != seen for seen, _position in candidates):
                        candidates.append((sha, position))
        stats["analysis_inputs_joined"] = len(reached)
        if not candidates:
            stats["pdfs_without_an_analysis"] += 1
            continue
        stats["pdfs_joined"] += 1
        if limit is not None and read >= limit:
            stats["limit_reached"] = True
            return
        sha, position, payload, reconciles = _pdf_route(data_dir, latest, candidates)
        stats["pdfs_joined_on_newest_route"] += position == 0
        stats["pdfs_on_an_older_reconciling_route"] += reconciles and sha != candidates[0][0]
        stats["pdfs_without_a_reconciling_route"] += not reconciles
        if sha in taken:
            stats["pdfs_sharing_an_analysis"] += 1
            continue
        taken.add(sha)
        read += 1
        if payload is None:
            continue
        for index, account in enumerate(_account_payloads(payload.get("artifact"))):
            identity = _statement_identity(account)
            if identity is not None:
                identities.add(identity)
            yield f"p{pdf[:12]}.{index}", _with_meta(account, latest[sha][1], latest[sha][2])
    orphans = sorted((sha for sha in latest if sha not in reached), key=lambda sha: (latest[sha][1], sha), reverse=True)
    stats["orphan_inputs"] = len(orphans)
    for sha in orphans:
        if limit is not None and read >= limit:
            stats["limit_reached"] = True
            return
        read += 1
        payload = _artifact(data_dir, latest[sha][0])
        if payload is None:
            continue
        for index, account in enumerate(_account_payloads(payload.get("artifact"))):
            identity = _statement_identity(account)
            if identity is None:
                stats["orphan_accounts_without_identity"] += 1
            elif identity in identities:
                stats["orphan_accounts_matching_a_kept_statement"] += 1
                continue
            else:
                identities.add(identity)
            stats["orphan_accounts_kept"] += 1
            yield f"o{sha[:12]}.{index}", _with_meta(account, latest[sha][1], latest[sha][2])


def job_accounts(database: Path, *, basis: str = "input", stats: dict | None = None) -> Iterator[tuple[str, dict]]:
    """(id, account payload) for every saved job of a copy of the tryout host's job store, opened read-only, the newest
    first (B1, I60); with the pdf basis (S3.1), only each PDF's newest job (a job without a document is kept)."""
    if basis not in BASES:
        raise ValueError(f"unknown basis {basis!r}")
    stats = {} if stats is None else stats
    connection = _read_only(database)
    try:
        if basis == "pdf":
            rows = connection.execute(
                "SELECT j.id, j.analysis_json, d.content_sha256, j.created_at FROM jobs j LEFT JOIN documents d"
                " ON d.id = j.document_id WHERE j.analysis_json IS NOT NULL ORDER BY j.created_at DESC, j.id DESC"
            ).fetchall()
        else:
            rows = [(job_id, text, None, created) for job_id, text, created in connection.execute(
                "SELECT id, analysis_json, created_at FROM jobs WHERE analysis_json IS NOT NULL"
                " ORDER BY created_at DESC, id DESC").fetchall()]
    finally:
        connection.close()
    stats["jobs"] = len(rows)
    seen: set[str] = set()
    for job_id, text, pdf, created in rows:
        if pdf is not None:
            if pdf in seen:
                stats["jobs_repeating_a_pdf"] = stats.get("jobs_repeating_a_pdf", 0) + 1
                continue
            seen.add(pdf)
            stats["pdfs"] = len(seen)
        try:
            analysis = json.loads(text)
        except ValueError:
            continue
        for index, account in enumerate(_account_payloads(analysis)):
            yield f"j{job_id[:8]}.{index}", _with_meta(account, created)


def _fingerprint(statement) -> tuple:
    return (statement.bank, statement.period_start, statement.period_end, statement.beginning_balance,
            statement.ending_balance, len(statement.transactions), statement.account_number)


def _pool_threshold(classifier, record) -> int:
    """§7.0: the recurrence count of the entity's pool: two on a business account (a customer-payment platform reads
    only the business words), three otherwise."""
    from analysis.classification_registry import OPERATING_REVENUE_SOURCE_TYPES

    if OPERATING_REVENUE_SOURCE_TYPES.get(record.revenue_canonical_entity or "") == "customer_payment_platform":
        business = classifier._matches_any(
            classifier.account_name_text(record.account_name), classifier._BUSINESS_ACCOUNT_PATTERNS
        )
    else:
        business = classifier._business_account(record.account_name)
    return classifier._RECURRENCE_MIN_BUSINESS_CREDITS if business else classifier._RECURRENCE_MIN_CREDITS


def _guard_facts(record, text: str) -> dict:
    """The §14.3 guard facts of one posted credit, read with the checkout's own readers when it has them."""
    from analysis import transaction_classifier as classifier

    facts: dict = {}
    if not hasattr(classifier, "revenue_text"):
        return facts
    revenue = classifier.revenue_text(text)
    region = classifier.payer_region(revenue)
    row = _before_receiver(revenue)
    # Audit B9 (I13): the holder's name the checkout's holder tests read (the statement's holder name when its parser
    # read one), or the account name on a checkout from before B9.
    holder = (
        classifier.holder_reading(record.account_name, getattr(record, "holder_name", None))
        if hasattr(classifier, "holder_reading") else record.account_name
    )
    # Audit B9 (I13): a processor's settlement or payout under the merchant's own name is never the holder's own money,
    # as the pass's holder hold reads it (true_revenue.merchant_settlement, on a checkout that has it).
    try:
        from analysis import true_revenue as pass_7
    except ImportError:
        pass_7 = None
    settlement = bool(getattr(pass_7, "merchant_settlement", None) and pass_7.merchant_settlement(revenue))
    facts["gate"] = classifier.channel_gate(revenue)
    facts["holder"] = classifier.holder_named(region, holder) and not settlement
    facts["numbered"] = classifier.numbered_company(revenue, region)
    # G1 (review I1): narrowing 4 needs a third-party originator.
    facts["third_party_originator"] = classifier._third_party_originator(revenue) is not None
    # G17 (review C3): the holder's own transfer, read on its ACH originator whatever the payer region says.
    facts["own_transfer"] = bool(
        classifier._TRANSFER_WORDING.search(row) and _ACH_FIELD.search(row)
        and classifier.holder_named(classifier._ach_payer_region(revenue), holder)
    )
    # G14 (review I1): the rows that count toward an entity's recurrence pool, and the count it needs.
    facts["pool_candidate"] = classifier._in_operating_pool(record)
    facts["pool_vetoed"] = bool(classifier._recurrence_vetoed(record, revenue) or facts["gate"] == "closed")
    facts["pool_threshold"] = _pool_threshold(classifier, record)
    # S3.1 (wire_veto): the §7.9 wire vetoes as the S2.3 review applies them (step 11 on a wire, a reference glued to
    # WIRE), read with the checkout's own code on the text and payer region the credit decision reads.
    if hasattr(classifier, "_wire_vetoes_apply"):
        facts["wire_vetoed"] = bool(
            classifier._wire_vetoes_apply(revenue) and classifier._wire_vetoed(revenue, region, holder)
        )
    # S3.1 (recurrence_veto): the worded recurrence veto (§7.0, S2.2-A, S2.4), read with the checkout's own code.
    if hasattr(classifier, "_recurrence_veto_wording"):
        facts["recurrence_veto_wording"] = bool(classifier._recurrence_veto_wording(record, revenue))
    try:
        from analysis import true_revenue
    except ImportError:
        return facts
    facts.update(true_revenue.guard_facts(record, revenue))
    return facts


def account_snapshot(account: dict) -> dict:
    """Re-classify one account payload with the `analysis` package on sys.path."""
    from analysis import classification_registry
    from analysis.classification_registry import OPERATING_REVENUE_SOURCE_ALIASES
    from analysis.metrics import compute_metrics
    from analysis.payee_matcher import registry_match
    from analysis.schema import Statement
    from analysis.transaction_classifier import classify_statement_transactions

    statement = Statement.model_validate(account["statement"])
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    known = _known_names(classification_registry)
    credits = []
    posted = [record for record in records if record.amount > 0 and record.is_posted]
    for index, record in enumerate(records):
        if record.amount <= 0 or not record.is_posted or record.revenue_classification is None:
            continue
        # S3.1 review: the operating registry's reading of the whole row, which is 5.4's recurrence-pool key (§7.0:
        # 5.4 pooled a direction conflict the registry names, whose own decision names no entity). It is always a key of
        # OPERATING_REVENUE_SOURCE_ALIASES, never a printed string, so it is written as-is (S3.1 privacy fix).
        registry = registry_match(record.normalized_description, OPERATING_REVENUE_SOURCE_ALIASES)
        credits.append({
            "registry_entity": registry[0] if registry else None,
            "i": index,
            "cents": round(record.amount * 100),
            "state": record.revenue_classification,
            "method": record.revenue_match_method,
            "rule": record.revenue_matched_rule,
            # S3.1 privacy fix: a name no registry or ledger table holds is digit-masked (_published_name).
            "entity": _published_name(record.revenue_canonical_entity, known),
            "alias": _published_name(record.revenue_matched_alias, known),
            "tier": getattr(record, "revenue_tier", None),
            "reason": getattr(record, "revenue_tier_reason", None),
            "class": record.classification,
            "lender_credit": bool(getattr(record, "contributes_to_lender_credit_exclusion", False)),
            "text": mask(record.normalized_description),
            "facts": _guard_facts(record, record.normalized_description),
        })
    tier_totals = None
    if hasattr(metrics, "counted_flagged_total"):
        tier_totals = {
            "verified": round(metrics.verified_revenue_total * 100),
            "counted_flagged": round(metrics.counted_flagged_total * 100),
            "excluded_pending_review": round(metrics.excluded_pending_review_total * 100),
            "non_revenue": round(metrics.non_revenue_total * 100),
        }
    return {
        # S3.1 review: the bank as printed can hold digits; it is masked like every other text.
        "bank": mask(statement.bank),
        "rows": len(records),
        "credits": credits,
        "posted_cents": sum(credit["cents"] for credit in credits),
        # G9 (review I1): every posted credit, whatever its state, counted apart from the rows the census kept.
        "posted_credit_count": len(posted),
        "posted_credit_cents": sum(round(record.amount * 100) for record in posted),
        "tier_totals": tier_totals,
        "lender_credits": metrics.lender_credits,
        "eligible_deposits": metrics.legacy_eligible_deposits,
        "revenue_review_required": metrics.revenue_review_required,
    }


def _analysis_fields(account: dict) -> dict:
    """B1 (I60): what the snapshot records of an account's analysis: its stage, when it was created (CENSUS_META, from
    the reader) and the parser route that published it (`model_used`)."""
    meta = account.get(CENSUS_META) or {}
    route = account.get("model_used")
    return {"analysis_stage": meta.get("stage"), "analysis_created": meta.get("created"),
            "parser_route": route if isinstance(route, str) else None}


def _parse(statement) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """B1 (I60): a statement's parse, compared within one run only: every row's (digit-masked description, cents),
    hashed, sorted; and its credits' alone."""
    rows = [(hash((mask(transaction.description), round((transaction.amount or 0) * 100))), transaction.amount or 0)
            for transaction in statement.transactions]
    return tuple(sorted(row for row, _amount in rows)), tuple(sorted(row for row, amount in rows if amount > 0))


def _differing(rows: tuple[int, ...], kept: tuple[int, ...]) -> int:
    """B1 (I60): the rows of one parse the kept parse does not hold (counted with their repeats)."""
    return sum((Counter(rows) - Counter(kept)).values())


def _set_aside(groups: Iterable[list[dict]]) -> tuple[dict, list]:
    """B1 (I60): each statement's set-aside analyses mapped to the one kept (the first of its group), and the stale
    parses: the set-aside analyses whose parse differs from the kept one."""
    duplicates: dict[str, str] = {}
    stale: list[dict] = []
    for members in groups:
        kept = members[0]
        for member in members[1:]:
            duplicates[member["key"]] = kept["key"]
            rows = _differing(member["parse"][0], kept["parse"][0])
            if not rows:
                continue
            stale.append({
                "account": member["key"], "kept": kept["key"], "rows_differing": rows,
                "credit_rows_differing": _differing(member["parse"][1], kept["parse"][1]),
                **{name: member[name] for name in ("analysis_stage", "analysis_created", "parser_route")},
                **{f"kept_{name}": kept[name] for name in ("analysis_stage", "analysis_created", "parser_route")},
            })
    return duplicates, stale


def _analysis_stage_version() -> int | None:
    """B1 (I60): the analysis stage of the checkout that classifies (None when it has none)."""
    try:
        from webapp.artifact_cache import ANALYSIS_STAGE_VERSION
    except Exception:  # noqa: BLE001
        return None
    return ANALYSIS_STAGE_VERSION


def snapshot(accounts: Iterable[tuple[str, dict]], *, basis: str = "input", basis_stats: dict | None = None) -> dict:
    """{"classification_version", "analysis_stage_version", "basis", "basis_stats", "accounts": {id: account snapshot},
    "skipped": {reason: n}, "duplicates": {set-aside id: kept id}, "stale_parses": [...]}, over the reconciled,
    de-duplicated accounts (the credit census's filter). `basis_stats` is the dict the account reader fills (S3.1); it
    is read once every account is read.

    B1 (I60): of the analyses that read one statement (one fingerprint), the newest-created is kept, in whatever order
    the reader yields them (a later, newer one replaces the one kept; equal times keep the first); the others are
    duplicates, and one whose parse differs from the kept one is a stale parse."""
    from analysis.schema import Statement
    from analysis.transaction_classifier import CLASSIFICATION_VERSION

    result: dict = {"classification_version": CLASSIFICATION_VERSION, "analysis_stage_version": _analysis_stage_version(),
                    "basis": basis, "accounts": {}, "skipped": {}}
    skipped: Counter = Counter()
    groups: dict[tuple, list[dict]] = {}
    for key, account in accounts:
        if not bool((account.get("reconciliation") or {}).get("ok")):
            skipped["unreconciled"] += 1
            continue
        try:
            statement = Statement.model_validate(account["statement"])
            fingerprint = _fingerprint(statement)
        except Exception:  # noqa: BLE001  (a stored payload the schema no longer reads)
            skipped["unreadable"] += 1
            continue
        fields = _analysis_fields(account)
        member = {"key": key, **fields, "parse": _parse(statement)}
        members = groups.setdefault(fingerprint, [])
        if members:
            skipped["duplicate"] += 1
            if (member["analysis_created"] or "") <= (members[0]["analysis_created"] or ""):
                members.append(member)
                continue
            # B1 (I60): a newer analysis of a statement already read replaces the one kept.
            result["accounts"].pop(members[0]["key"], None)
        members.insert(0, member)
        try:
            result["accounts"][key] = {**account_snapshot(account), **fields}
        except Exception as error:  # noqa: BLE001
            skipped[type(error).__name__] += 1
    result["skipped"] = dict(sorted(skipped.items()))
    result["basis_stats"] = dict(basis_stats or {})
    result["duplicates"], result["stale_parses"] = _set_aside(groups.values())
    return result


def _share(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 2) if whole else 0.0


#: B1 (audit I39): the standing sweep of the non-revenue a credit's wording identifies inside True (a verified or a
#: counted credit), so a regression shows as a number. Each True credit lands in the first class (A to H, in order) one
#: of whose wordings reads it; each wording carries its confidence. The wording is the census's own, read on the
#: digit-masked text (independent of the code under test): bank and government forms and public companies only, each
#: with its source, never a holder's or a private payer's name. Class H (a government payment that prints no purpose:
#: task GOV's class E, standard E5) is the owner's to rule: reported apart as "unclear, owner", never in the
#: overstatement. The standard is the audit's reference standard (§3 and §7, its section letters and pointers P1 to P9).
SWEEP_UNCLEAR = "unclear"
UNCLEAR_OWNER_CLASS = "H"
NON_REVENUE_IN_TRUE_CLASSES = (
    ("A", "own-account wording", (
        # Standard B1 (P1 to P5) and audit I01, I21: overdraft sweeps, card and credit-line transfers, Square's savings
        # folders, and the banks' own-account transfer forms that print no counterparty.
        ("high", r"\bOVERDRAFT (?:PROTECTION|XFER|TRANSFER)\b|\bOD PROTECTION\b|\bODP TRANSFER\b"),
        ("high", r"\b(?:TRANSFER|XFER|TRSFR|TRNSFR|TFR) FROM (?:CRD|CREDIT CARD|CREDIT LINE)\b"),
        ("high", r"^EB FROM (?:CHECKING|SAVINGS)\b"),
        ("high", r"^TRANSFER IN (?:RAINY DAY|RENT)$"),
        ("high", r"^TRUIST ONLINE TRANSFER (?:MOBILE|ONLINE) FROM \d+$"),
        ("high", r"^CBUSOL TRANSFER CREDIT ONLINE REFERENCE \d+$"),
        ("high", r"^JPMORGAN CHASE EXT TRNSFR\b|^EXT TFR DEPOSIT\b"),
        ("high", r"^FUNDING TRANSFER CREDIT TRANSFER FROM \d+$"),
        ("high", r"\bOLB XFER FROM\b|^TRF CT INTERNET\b|^INTERNET PHONE TRSFR\b|^CMO TRANSFER\d|^INTERNET TRANSFER\d"),
        ("high", r"\bONLINE XFER TRANSFER FROM (?:CL|CK|SV)\b"),
        # Bank-originated (audit I39's verifiers): softer.
        ("medium", r"\bJPMC INTERNAL ACCOUNTS\b|^BANK OF AMERICA SAVINGS \d+ ACH\b"),
    )),
    # Standard B7 and audit I13: the ACH originator is the receiver, the holder (read by _own_ach).
    ("B", "holder's own ACH", ()),
    ("C", "financing", (
        # Standard C1 and C2. Audit I08: Forward Financing's fundings (FORWARDFINUSA<reference>, and its funding
        # vehicle FF SPE II, in statements that repay Forward). Audit I23: Celtic Bank and Newtek Bank, SBA and fintech
        # lenders.
        ("high", r"\bFORWARDFINUSA|\bFORWARD FINANCING\b|\bFF SPE II\b|^CELTIC BANK\b|\bNEWTEK BANK\b"),
        ("high", r"\bLOAN (?:PROCEEDS|DISB\w*|ADVANCE)\b|\b(?:LINE OF CREDIT|LOC) (?:ADVANCE|DRAW)\b|\bLINE OF CR\b"),
    )),
    ("D", "refunds and corrections", (
        # Standard D1, D3, D5 (P6 to P8) and audit I04: returned items, bank corrections, provisional credits,
        # reversed card purchases, fee waivers, card-purchase refunds and returned funder debits (French RENV).
        ("high", r"\bITEM RET(?:URNED)? NOT PAID\b|\b(?:ERROR|TRANSACTION) CORRECTION\b|^CORRECTION\b"),
        ("high", r"\b(?:PROVISIONAL|TEMPORARY|CONDITIONAL) CR(?:EDIT)?\b|^REV (?:MOBILE|POS|DEBIT|PURCHASE|ACH|CARD)\b"),
        ("high", r"\bFEE WAIVE[DR]?\b|\bWAIVE[DR]? FEE\b|^CREDIT BR \d+ WAIVE|\bRTNOFFSETS?\b|\bE ?TRANSFER RECLAIM\b"),
        ("high", r"^CHECKCARD \d|\bDEBIT PURCHASE RET\b|\bRENV(?:ERSEMENT)?\b"),
        # Standard D4: card rewards redeemed into the account (Chase's CASH REDEMPTION).
        ("medium", r"\bCASH REDEMPTION\b|\bREWARDS? REDEMPTION\b"),
    )),
    ("E", "investment and crypto", (
        # Standard G2 and audit I28: crypto exchanges and brokerages (Coinbase, Kraken's operator Payward, Binance.US's
        # operator BAM Trading, Bitstamp, Apex Clearing, Fidelity's brokerage form) and bitcoin that is not a sale.
        ("medium", r"\bCOINBA ?SE\b|\bPAYWARD\b|\bBINANCE\b|\bBAM TRADING\b|\bBITSTAMP\b|\bAPEX CLEARING\b"),
        ("medium", r"\bP FIDELITY\b|\bBITCOIN\b(?!.*\bSALES?\b)"),
    )),
    ("F", "gambling and prediction markets", (
        # Standard G3 (P9) and audit I28: sportsbooks and prediction markets paying out, not paying a vendor.
        ("high", r"^(?!.*\b(?:AP PAYMENT|VENDOR|PAYABLES?|INVOICE)\b).*"
                 r"\b(?:DRAFTKINGS|FANDUEL|KALSHI|PRIZEPICKS|BETMGM|POLYMARKET|SPORTSBOOK)\b"),
    )),
    ("G", "government money not earned", (
        # Task GOV (the owner's ruling of 2026-09-30): personal benefits (class B), tax refunds (class C), grants and
        # subsidies (class D); standard E1, E3, E4. A government paying for services is revenue (class A), never here.
        ("high", r"\bCANADA (?:CHILD|ESSENTIALS|GROCERIES AND ESSENTIALS|WORKERS|DISABILITY) BENEFITS?\b"
                 r"|\bOLD AGE SECURITY\b|\bUI DD\b|\bTAX ?EIP\d*\b|\bCHILD CTC\b"),
        ("high", r"\bSSA TREAS\b|(?:\bXX|\b)SOC SEC\b|(?:\bXX|\b)VA BENEF"),
        ("high", r"\bHHS ?STIMULUS\b|\bHHSPAYMENT|\b(?:FSA|CCC) TREAS \d+\b|\bCEWS\b|\bGOVERNMENT ESDC\b"),
        ("high", r"\bCANADA GST\b|\bGST (?:TPS )?CANADA\b|\bRQ GST\b|\bCANADA RI[TF]\b"),
        ("high", r"\bTAX ?REF(?:UND)?S?\b|[A-Z]*TAXRFD\b|\bTAX RFD\b|\bTAX ?EIC\b"
                 r"|\bIRS TREAS ?\d{3}\b(?!.*\b(?:MISC PAY|VENDOR)\b)"),
        # Audit I56 (GOV's gaps): payroll-tax refunds through a payroll provider, and the glued carbon rebate.
        ("medium", r"\bADP TAX\b|\bPAYCHEX TPS\b.*\bTAXES\b|\bTAXES\b.*\bPAYCHEX\b|CARBON ?REBATE"),
    )),
    (UNCLEAR_OWNER_CLASS, "government payment, purpose not printed (unclear, owner)", (
        # Task GOV's class E and audit I39's class H: Minnesota Management and Budget's state vendor payments, an
        # agency's Treasury MISC PAY with no invoice (VA's), a province's or Quebec's payment, workers' compensation
        # boards, and Wisconsin DCF's direct deposits.
        (SWEEP_UNCLEAR, r"\bSTATE MMB\b|^\d+ TREAS \d+ MISC PAY\b|\bPROVINCIAL PAYMENT PROVINCE OF\b"
                        r"|\bPROV(?:INCIAL)? LOCAL GVT\b|\bGOUV(?:ERNEMENT)? (?:DU )?QUEBEC\b"),
        (SWEEP_UNCLEAR, r"\bWSIB\b|\bWORK COMP BOARD\b|\bWCB\b|\bWORKFORCE SAFETY\b|\bWIDCF DD\b"),
    )),
)
#: The wording is read on the masked text with each '#' read as the digit 0, which keeps a classifier's \d, \w and \b
#: on a masked digit exactly as _on_masked does, at the regex engine's own speed.
_SWEEP_WORDING = tuple(
    (letter, tuple((confidence, re.compile(pattern)) for confidence, pattern in wordings))
    for letter, _label, wordings in NON_REVENUE_IN_TRUE_CLASSES
)
#: Every class's wording at once: a row none of it reads (and that prints no own push) lands in no class, read once.
_SWEEP_ANY = re.compile("|".join(
    f"(?:{pattern})" for _letter, _label, wordings in NON_REVENUE_IN_TRUE_CLASSES for _confidence, pattern in wordings
))
#: B1 (I39, class B): an ACH row's originator and receiver fields (BofA's '<originator> DES ... INDN <receiver> CO ID',
#: Chase's 'ORIG CO NAME <originator> ORIG ID ... IND NAME <receiver> TRN'), on the masked text.
_OWN_ACH_FORMS = (
    re.compile(r"^(?:(?:ACH|CCD|PPD) (?:CREDIT|DEPOSIT) )?(?P<originator>.+?) DES\b.*?\bINDN (?P<receiver>.+?)"
               r"(?= CO ID\b|$)"),
    re.compile(r"\bORIG CO NAME (?P<originator>.+?) ORIG ID\b.*?\bIND NAME (?P<receiver>.+?)(?= TRN\b|$)"),
)
#: B1 (I39, class B): the entry wording of the holder's own push, read before the receiver field: an ACH push, a
#: bank's ACH product sending from the holder's other account (Mercury's MERCURYACH), transfer wording, or a credit
#: line's payment. A processor or platform that originates its settlement or payout under the merchant's own name
#: (NET SETTLE, NETSWEEP, a payout id, a distributor's EFT) prints none of these, and stays out.
_OWN_ACH_ENTRY = re.compile(r"(?<![A-Z])(?:ACH ?PUSH|MERCURYACH|LINE OF CR|(?:TRANSFERS?|XFER|TRNSFR|TRSFR|TFR)\b)")
_SWEEP_SHAPES = 8


def _own_ach(text: str) -> bool:
    """B1 (I39, class B): an ACH row whose originator is its receiver (the holder), with the entry wording of an own
    push (_OWN_ACH_ENTRY): the two names are equal, or one is the other's start, whole words of two or more, or a cut
    of _CUT_NAME characters or more."""
    if not _OWN_ACH_ENTRY.search(_before_receiver(text)):
        return False
    for form in _OWN_ACH_FORMS:
        match = form.search(text)
        if match is None:
            continue
        originator, receiver = (" ".join(match.group(name).split()) for name in ("originator", "receiver"))
        if not re.search(r"[A-Z]{3}", originator) or not re.search(r"[A-Z]{3}", receiver):
            continue
        shorter, longer = sorted((originator, receiver), key=len)
        if longer == shorter:
            return True
        if longer.startswith(shorter) and (
            len(shorter) >= _CUT_NAME or (longer[len(shorter)] == " " and len(shorter.split()) >= 2)
        ):
            return True
    return False


def _sweep_shape(text: str, span: tuple[int, int] | None) -> str:
    """B1 (I39): a swept row's shape: the class's own wording and the public words kept, a word that holds a digit
    printed '#', any other word '*', and a run of one mark printed once."""
    words: list[str] = []
    for token in re.finditer(r"\S+", text):
        word = token.group()
        if set(word) == {"#"}:
            word = "#"
        elif not ((span is not None and span[0] <= token.start() and token.end() <= span[1]) or word in _PUBLIC_WORDS):
            word = "#" if "#" in word else "*"
        if not (word in {"#", "*"} and words and words[-1] == word):
            words.append(word)
    return " ".join(words)


def _without_furniture_56(text: str) -> str:
    """Audit B8 (I46): the masked text up to its first statement furniture (_STATEMENT_FURNITURE_56), as the
    classifier's revenue text reads the row; a text the cut would leave with no letter is kept."""
    found = _STATEMENT_FURNITURE_56.search(text)
    if found is None:
        return text
    kept = text[: found.start()].rstrip()
    return kept if any(character.isalpha() for character in kept) else text


def _sweep_class(text: str) -> tuple[str, str, str] | None:
    """B1 (I39): the first class whose wording reads a True credit's masked text: (class, confidence, shape). Audit
    B8 (I46): read past the statement furniture a parser glued onto the row (_without_furniture_56), whose own words
    (TD's back panel: '... OVERDRAFT PROTECTION ...') are no credit's wording."""
    text = _without_furniture_56(text)
    zeroed = text.replace("#", "0")
    if _SWEEP_ANY.search(zeroed) is None and _OWN_ACH_ENTRY.search(text) is None:
        return None
    for letter, wordings in _SWEEP_WORDING:
        if letter == "B":
            if _own_ach(text):
                return letter, "high", public_shape(text)
            continue
        for confidence, wording in wordings:
            match = wording.search(zeroed)
            if match is not None:
                return letter, confidence, _sweep_shape(text, match.span())
    return None


def sweep(snap: dict) -> dict:
    """B1 (I39): the non-revenue a credit's wording identifies inside True, by class (rows, dollars, statements, the
    verified dollars, the dollars of each confidence, the share of True and the largest shapes); the overstatement
    (classes A to G: the high-confidence wording, and all of it); and class H apart, as the owner's."""
    true_cents = 0
    slots: dict = {letter: {"rows": Counter(), "cents": Counter(), "statements": set(), "verified": 0,
                            "shapes": Counter()} for letter, _label, _wordings in NON_REVENUE_IN_TRUE_CLASSES}
    for key, account in snap["accounts"].items():
        for credit in account["credits"]:
            verified = credit["state"] == "verified_revenue"
            if not (verified or credit.get("tier") == "counted_flagged"):
                continue
            true_cents += credit["cents"]
            found = _sweep_class(credit["text"])
            if found is None:
                continue
            letter, confidence, shape = found
            slot = slots[letter]
            slot["rows"][confidence] += 1
            slot["cents"][confidence] += credit["cents"]
            slot["statements"].add(key)
            slot["verified"] += credit["cents"] if verified else 0
            slot["shapes"][shape] += credit["cents"]

    def share(cents: int) -> float:
        return round(100.0 * cents / true_cents, 3) if true_cents else 0.0

    classes = {
        letter: {
            "label": label, "rows": sum(slots[letter]["rows"].values()),
            "dollars": round(sum(slots[letter]["cents"].values()) / 100, 2),
            "statements": len(slots[letter]["statements"]),
            "verified_dollars": round(slots[letter]["verified"] / 100, 2),
            **{f"{confidence}_dollars": round(slots[letter]["cents"][confidence] / 100, 2)
               for confidence in ("high", "medium")},
            "share_of_true": share(sum(slots[letter]["cents"].values())),
            "shapes": {shape: round(cents / 100, 2) for shape, cents in slots[letter]["shapes"].most_common(_SWEEP_SHAPES)},
        }
        for letter, label, _wordings in NON_REVENUE_IN_TRUE_CLASSES
    }

    def total(confidences: tuple[str, ...]) -> dict:
        rows = sum(slots[letter]["rows"][c] for letter in slots if letter != UNCLEAR_OWNER_CLASS for c in confidences)
        cents = sum(slots[letter]["cents"][c] for letter in slots if letter != UNCLEAR_OWNER_CLASS for c in confidences)
        return {"rows": rows, "dollars": round(cents / 100, 2), "share_of_true": share(cents)}

    unclear = slots[UNCLEAR_OWNER_CLASS]
    return {
        "true_dollars": round(true_cents / 100, 2),
        "classes": classes,
        "overstatement": {"high": total(("high",)), "all": total(("high", "medium"))},
        "unclear_owner": {"class": UNCLEAR_OWNER_CLASS, "rows": sum(unclear["rows"].values()),
                          "dollars": round(sum(unclear["cents"].values()) / 100, 2),
                          "verified_dollars": round(unclear["verified"] / 100, 2),
                          "share_of_true": share(sum(unclear["cents"].values()))},
    }


def _sweep_line(result: dict) -> str:
    """B1 (I39): the sweep in one printed line (counts, shares and totals only)."""
    over, unclear = result["overstatement"], result["unclear_owner"]
    by_class = ", ".join(f"{letter} {row['rows']} rows/${row['dollars']:,.2f}"
                         for letter, row in result["classes"].items() if row["rows"] and letter != UNCLEAR_OWNER_CLASS)
    return (f"non-revenue in True: high ${over['high']['dollars']:,.2f} ({over['high']['share_of_true']}% of True),"
            f" all ${over['all']['dollars']:,.2f} ({over['all']['share_of_true']}%); by class: {by_class or 'none'};"
            f" class H (unclear, owner) {unclear['rows']} rows/${unclear['dollars']:,.2f}"
            f" ({unclear['share_of_true']}%), verified ${unclear['verified_dollars']:,.2f}")


def _summary(snap: dict) -> dict:
    """True and Verified shares, $0 statements, the median statement shares, the tiers and reasons."""
    totals: Counter = Counter()
    rows: Counter = Counter()
    tiers: Counter = Counter()
    reasons: dict = defaultdict(lambda: [0, 0])
    zero_verified = zero_true = with_credits = gated = 0
    true_shares, verified_shares = [], []
    for account in snap["accounts"].values():
        posted = account["posted_cents"]
        if posted <= 0:
            continue
        with_credits += 1
        verified = sum(c["cents"] for c in account["credits"] if c["state"] == "verified_revenue")
        counted = sum(c["cents"] for c in account["credits"] if c.get("tier") == "counted_flagged")
        true = verified + counted
        zero_verified += verified == 0
        zero_true += true == 0
        true_shares.append(true / posted)
        verified_shares.append(verified / posted)
        gated += bool(account.get("revenue_review_required"))
        for credit in account["credits"]:
            totals[credit["state"]] += credit["cents"]
            rows[credit["state"]] += 1
            if credit.get("tier"):
                tiers[credit["tier"]] += credit["cents"]
            if credit.get("reason"):
                slot = reasons[f"{credit['tier']}/{credit['reason']}"]
                slot[0] += 1
                slot[1] += credit["cents"]
        totals["posted"] += posted
    true_total = totals["verified_revenue"] + tiers["counted_flagged"]
    return {
        "version": snap.get("classification_version"),
        "statements_with_credits": with_credits,
        "posted_dollars": round(totals["posted"] / 100, 2),
        "verified_share": _share(totals["verified_revenue"], totals["posted"]),
        "unverified_share": _share(totals["unverified_deposit"], totals["posted"]),
        "non_revenue_share": _share(totals["non_revenue"], totals["posted"]),
        "true_share": _share(true_total, totals["posted"]) if tiers else None,
        "held_share": _share(tiers["excluded_pending_review"], totals["posted"]) if tiers else None,
        "zero_verified_statements": zero_verified,
        "zero_true_statements": zero_true if tiers else None,
        "median_statement_true_share": round(100 * statistics.median(true_shares), 1) if tiers and true_shares else None,
        "median_statement_verified_share": round(100 * statistics.median(verified_shares), 1) if verified_shares else None,
        "gated_statements": gated,
        "gated_share": _share(gated, with_credits),
        "rows": dict(rows),
        "reasons": {key: {"rows": value[0], "dollars": round(value[1] / 100, 2)} for key, value in sorted(reasons.items())},
        # B1 (I39): the standing sweep of the non-revenue wording left in True.
        "non_revenue_in_true": sweep(snap),
    }


def _narrowing(base: dict, after: dict) -> str | None:
    """Which §6.3 narrowing (or the OQ2 ruling) moved a base non_revenue row out of non_revenue; None for none."""
    text, base_method = after["text"], base["method"]
    facts = after.get("facts") or {}
    if base_method == "reversal_cancellation_exclusion" and "REIMBURSEMENT" in text and _CLAIM_SIGNAL.search(text):
        return "1_reimbursement_claim_signal"
    if base_method == "insurance_provider_credit_exclusion":
        if after["method"] == "insurer_customer_payment" and not re.search(r"H[CE]?CLAIMPMT", after["text"]):
            return "3_insurer_customer_payment"
        if re.search(r"H[CE]?CLAIMPMT", after["text"]):
            return "2_hcclaimpmt_insurer"
        return "3_insurer_customer_payment"
    # Review I1: a book or funds transfer leaves only on a printed third-party originator (T19, §7.11).
    if (
        base_method == "strong_non_revenue_rule"
        and re.search(r"\b(?:BOOK|FUNDS?) TRANSFER\b", text)
        and facts.get("third_party_originator")
    ):
        return "4_book_or_funds_transfer"
    # Final review I8: a loan-reading base whose LOAN the later text prints LN (the guard's only rewrite), and no other
    # change to the text.
    if base_method in LOAN_READING_METHODS and _ln_where_loan(base["text"], after["text"]):
        return "5_street_ln"
    # Audit B3 (I11, §6.3 narrowing 9): a processor's instant payout printed as a card credit, released by the pass
    # beside the processor's own ACH activity (its method), before narrowing 6 reads the same card label.
    if (
        base_method == "reversal_cancellation_exclusion" and after["method"] == PROCESSOR_CARD_PAYOUT_METHOD
        and re.search(r"\b(?:DEBIT CARD CREDIT?|POS CREDIT)\b", text)
    ):
        return "10_processor_card_payout"
    if base_method == "reversal_cancellation_exclusion" and re.search(r"\b(?:DEBIT CARD CREDIT|POS CREDIT)\b", text):
        return "6_card_credit_release"
    if base_method == "financing_proceeds_credit" and after["method"] == "auto_lender_dealer_funding":
        return "7_q7_dealer_funding"
    # Audit B6 (I10, §6.3 narrowing 10): a factoring review entity's credit, routed to the factoring payout (the pass's
    # own factoring_review fact).
    if base_method == "potential_lender_registry_credit_exclusion" and facts.get("factoring_review"):
        return "11_factoring_review_payout"
    # Review I1: only the five BNPL providers' settlements leave D1 by the OQ2 ruling.
    if (
        base_method == "financing_proceeds_credit"
        and after["method"] != "financing_proceeds_credit"
        and base.get("entity") in BNPL_ENTITIES
    ):
        return "8_oq2_bnpl_settlement"
    # Audit B2 (I20): Bank of America's and a credit union's layouts that print a named sender after the designation.
    if base_method == "strong_non_revenue_rule" and any(form.search(text) for form in _NAMED_DESIGNATION_TRANSFERS_56):
        return "9_named_transfer_after_designation"
    # Audit B8 (I46, §6.3 narrowing 11): the strong non-revenue or reversal rule fired on a deposit that prints the
    # statement furniture the revenue text now cuts.
    if base_method in _FURNITURE_BASE_METHODS and _STATEMENT_FURNITURE_56.search(text):
        return "12_statement_furniture"
    return None


def _ln_where_loan(base_text: str, after_text: str) -> list[int]:
    """I8: the word positions where the base text prints LOAN and the later text LN, when those are the texts' only
    differences; [] otherwise."""
    before, after = base_text.split(), after_text.split()
    if len(before) != len(after):
        return []
    positions = []
    for index, (old, new) in enumerate(zip(before, after)):
        if old == new:
            continue
        if (old, new) != ("LOAN", "LN"):
            return []
        positions.append(index)
    return positions


def _street_ln_release(base: dict, after: dict) -> bool:
    """I8 (G7b): the street-LN guard's own release (§7.11), read on the census's masked text: narrowing 5's LOAN that
    the later text prints LN, each LN ending a street address (a number, then one to three alphabetic words, none a
    loan-product word) and followed by no loan-payment word."""
    positions = _ln_where_loan(base["text"], after["text"]) if base["method"] in LOAN_READING_METHODS else []
    words = after["text"].split()
    for index in positions:
        run = []
        at = index - 1
        while at >= 0 and len(run) < 3 and words[at].isalpha():
            run.append(words[at])
            at -= 1
        if (
            not run or at < 0 or not re.fullmatch(r"[\d#]+", words[at])
            or set(run) & _LOAN_PRODUCT_WORDS
            or (index + 1 < len(words) and words[index + 1] in _LOAN_PAYMENT_WORDS)
        ):
            return False
    return bool(positions)


def _matches(patterns: Iterable[re.Pattern[str]], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _step_11(base: dict) -> bool:
    """A row step 11's verified descriptors verified (method operating_income_descriptor, the plain descriptor rule;
    not a card form)."""
    return base["method"] == "operating_income_descriptor" and (
        base.get("rule") or "verified_operating_income_descriptor"
    ) == "verified_operating_income_descriptor"


def _step_11_customer(base: dict) -> bool:
    """S3.1 review: a row 5.4's step 11 verified by its customer, invoice or receivable descriptor alone: one of them
    reads the row and none of 5.4's other verified descriptors (a merchant, card or marketplace settlement, a claim
    payment) does, so the verification rested on the rules §5.2 and §7.11 change."""
    text = base["text"]
    return (
        _step_11(base) and _matches(_PRE_55_CUSTOMER_DESCRIPTORS, text)
        and not _matches(_PRE_55_OTHER_DESCRIPTORS, text)
    )


def _steps_11_to_14(base: dict) -> bool:
    """S3.1 review: the rules that verify on the payer's identity or remittance (§5.2: step 11's customer and invoice
    descriptors, steps 12 to 14), which the holder test and the numbered-company guard govern."""
    return _step_11_customer(base) or base["method"] in STEPS_12_TO_14_METHODS


def _wire_veto_demotion(base: dict, after: dict) -> bool:
    """S3.1 (wire_veto): a verified row of a rule the §7.9 wire vetoes govern (WIRE_VETOED_METHODS; of step 11 only its
    customer and invoice descriptors, not a card form nor another settlement descriptor) that the checkout's own wire
    vetoes refuse (the snapshot's `wire_vetoed` fact), and that therefore fell to steps 15 and 16. A snapshot without
    the fact declares none."""
    facts = after.get("facts") or {}
    if not facts.get("wire_vetoed") or after["method"] not in FALLBACK_METHODS:
        return False
    if base["method"] == "operating_income_descriptor":
        # S3.1 review: 5.4 read a customer or invoice descriptor (the wire vetoes do not govern a settlement form).
        return _step_11_customer(base)
    return base["method"] in WIRE_VETOED_METHODS


def _read_only_in_receiver_value(base: dict) -> bool:
    """S3.1 (receiver_value): the base row's verification read its operating alias (a registry method's alias) or a
    customer, invoice or receivable descriptor (step 11 before 5.5) only inside a receiver field's value, which the
    5.5 readers no longer read (§5.2): it is read on the whole row and not on the row without the receiver values."""
    text = base["text"]
    without = _RECEIVER_VALUE.sub(" ", text)
    if without == text:
        return False
    if base["method"] in REGISTRY_METHODS and base.get("alias"):
        alias = re.compile(rf"(?<!\S){re.escape(mask(base['alias']))}(?!\S)")
        return alias.search(text) is not None and alias.search(without) is None
    if _step_11(base):
        # S3.1 review: every 5.4 verified descriptor, so a row another descriptor verified outside the receiver field
        # is not the receiver's.
        return _matches(_PRE_55_VERIFIED_DESCRIPTORS, text) and not _matches(_PRE_55_VERIFIED_DESCRIPTORS, without)
    return False


def _recurrence_vetoed_wording(after: dict) -> bool:
    """§7.0 (recurrence_veto): the snapshot's `recurrence_veto_wording` fact (the checkout's own reading, which spares
    a store-name platform's holder words and FUNDING on the three platforms that print it) when it carries one;
    otherwise the veto words on the digit-masked row before its receiver fields."""
    facts = after.get("facts") or {}
    if "recurrence_veto_wording" in facts:
        return bool(facts["recurrence_veto_wording"])
    row = _before_receiver(after["text"])
    if _RECURRENCE_VETO_WORDS.search(row):
        return True
    return after.get("entity") not in _FUNDING_SETTLEMENT_ENTITIES and _FUNDING_WORDS.search(row) is not None


def _pool_key(base: dict) -> str | None:
    """The entity whose 5.4 recurrence pool held a row: the registry's reading of the whole row, which 5.4's pass keyed
    its pools on (recorded as `registry_entity`; a pooled direction conflict's own decision names no entity), or the
    row's entity in a snapshot that does not record it."""
    return base.get("registry_entity") or base.get("entity")


def _taken_out_of_pool(base: dict, after: dict, admissions: frozenset) -> bool:
    """S3.1 review (pool_below): a 5.4 pool member that 5.5 takes out of its pool by a declared veto: the recurrence
    veto (the snapshot's pool_vetoed or recurrence_veto_wording fact: the veto words, payroll, the $1 floor, a direction
    conflict, a closed channel, §7.0), a direction conflict or the $1 floor read on the row itself, or a demotion of
    its own whose cause is declared (a new non-revenue rule, the channel gate, the receiver's value...)."""
    facts = after.get("facts") or {}
    if facts.get("pool_vetoed") or facts.get("recurrence_veto_wording") or facts.get("gate") == "closed":
        return True
    if after["method"] == "direction_conflict" or after["cents"] < MICRO_DEPOSIT_FLOOR_CENTS:
        return True
    if base["state"] == "verified_revenue" and after["state"] != "verified_revenue":
        cause = _demotion_cause(base, after, {"admissions": admissions})
        return cause in DECLARED_DEMOTIONS and cause not in _POOL_CAUSES
    return False


def _account_context(pairs: Iterable[tuple[dict, dict]], admissions: Iterable[str] = ()) -> dict:
    """S3.1 review: what the pool causes read of one account, from its (5.4 credit, later credit) pairs: for each 5.4
    pool key, the rows 5.5 took out of the pool by a declared veto (`vetoed`: key -> row indexes), and the keys whose
    pool one member's re-reading split (`split`: a member 5.5 reads as another registry entity)."""
    admitted = frozenset(admissions)
    context: dict = {"admissions": admitted, "vetoed": defaultdict(set), "split": set()}
    for base, after in pairs:
        key = _pool_key(base)
        if key is None or base["method"] not in POOL_54_METHODS:
            continue
        if _taken_out_of_pool(base, after, admitted):
            context["vetoed"][key].add(after["i"])
        if after.get("entity") and not _same_name(after["entity"], key):
            context["split"].add(key)
    return context


def _demotion_cause(base: dict, after: dict, context: dict | None = None) -> str:
    """The declared cause of a base verified row that is no longer verified (§7.0, §7.11), or 'undeclared'.

    S3.1 review (fix 1): each cause is declared only for (a) the 5.4 rule family it governs and (b) the 5.5 outcome it
    produces, each named beside it; the first that holds names the row. `context` is the row's account
    (_account_context): the pool causes and the ledger admissions read it, and without it they are never declared."""
    context = context or {}
    text, method, rule = after["text"], after["method"], after["rule"] or ""
    facts = after.get("facts") or {}
    fallback = method in FALLBACK_METHODS
    unlifted = method == "operating_source_requires_context"
    key = _pool_key(base)
    # (a) any verifying rule: D1 by descriptor precedes every verifying step (§6.1 step 7, §7.11); (b) Square Capital's
    # SQ CAP or an SBA / EIDL disbursement read as financing proceeds.
    if method == "financing_proceeds_credit" and rule in {"square_capital_credit", "sba_disbursement_credit"}:
        return "sq_cap_or_sba"
    # (a) any verifying rule: D1 precedes them all (§6.1 step 6); (b) financing proceeds from an entity the S1.5 ledger
    # admissions added or updated (the owner's signed-off list, given to compare).
    if method == "financing_proceeds_credit" and after.get("entity") in context.get("admissions", ()):
        return "ledger_admission"
    # (a) any verifying rule: the reversal-pair pass runs after every per-row rule, its logic unchanged, and only the
    # widened credit markers (§7.11, read on the credit or the debit it pairs) find new pairs (§6.2 step 4);
    # (b) matched_reversal_pair.
    if method == "matched_reversal_pair":
        return "reversal_pair"
    # (a) any verifying rule: strong non-revenue precedes them all (§6.1 step 9); (b) that rule on a row printing the
    # account-verification words §7.11 adds to it.
    if method == "strong_non_revenue_rule" and _ACCOUNT_VERIFICATION_55.search(text):
        return "acctverify"
    # (a) any verifying rule (§6.1 steps 3 and 9 precede them all); (b) the reversal rule on a row printing a return code
    # §7.11 adds to its credit markers or a French cancel word S4.2 adds to them (ANNULE), or strong non-revenue on a
    # row printing a tax-refund abbreviation it adds.
    if (
        method == "reversal_cancellation_exclusion"
        and (
            _RETURN_CODES_55.search(text) or _FRENCH_REVERSAL_WORDS_55.search(text)
            # Audit B3 (I04): step 3's 5.6 return, correction and refund spellings.
            or _matches(_REVERSAL_MARKERS_56, text)
        )
    ) or (method == "strong_non_revenue_rule" and (
        _TAX_REFUNDS_55.search(text) or _CRA_REFUND_56.search(text) or _GOVERNMENT_TAX_REFUNDS_56.search(text)
        # Audit B3 (I43): the card-rewards redemptions.
        or _matches(_REWARD_REDEMPTIONS_56, text)
    )):
        # I7: and the CRA's income-tax refund forms, which 5.6 adds to the strong non-revenue rule (§20); GOV: and the
        # GST/HST refund forms and the IRS's payments (the owner's ruling of 2026-09-30).
        return "new_non_revenue_marker"
    # (a) 5.4's step-11 claim-payment descriptor (§7.7); (b) the claim entry held with the insurer's credits
    # (insurer_customer_payment), which 5.5 does only with the T18 switch off.
    if (
        method == "insurer_customer_payment" and _CLAIM_55.search(text)
        and _step_11(base) and _CLAIM_54.search(base["text"])
    ):
        return "claim_first_off"
    # (a) a row 5.4's recurrence pass lifted; (b) 5.5 reads it as a direction conflict, which no pass lifts (§7.0).
    if base["method"] in RECURRENCE_LIFT_METHODS and method == "direction_conflict":
        return "direction_conflict_pool"
    # (a) a row 5.4's recurrence pass lifted (in 5.5 the floor governs the pool, not a row verified on its own context);
    # (b) left unlifted (operating_source_requires_context) under $1 (§7.0). And in 5.6, where the floor is absolute
    # (S4.4/S4.5 review: pass 7's last step overrules every rule): (a) any verifying rule; (b) held under $1 with the
    # floor's reason (MICRO_DEPOSIT_FLOOR_REASON).
    if after["cents"] < MICRO_DEPOSIT_FLOOR_CENTS and (
        (base["method"] in RECURRENCE_LIFT_METHODS and unlifted)
        or (after.get("tier") == "excluded_pending_review" and after.get("reason") == MICRO_DEPOSIT_FLOOR_REASON)
        # I7: pass 7's last step, which gives the floor's own method (§20).
        or method == "micro_deposit_floor"
    ):
        return "micro_deposit_floor"
    # §6.1 step 9b. Closed: (a) any verifying rule (no step verifies a closed row, the registry and the recurrence pass
    # included); (b) the row fell to steps 15 and 16. Push: (a) a rule outside the registry (steps 11 to 14 never verify
    # a push-rail row); (b) steps 15 and 16.
    if fallback and (
        facts.get("gate") == "closed" or (facts.get("gate") == "push" and base["method"] not in REGISTRY_METHODS)
    ):
        return "channel_gate"
    # §7.11. (a) step 11's descriptors, whose every match disappears once CUSTOMER ID is removed (Truist prints it on
    # every ACH line); (b) steps 15 and 16.
    if (
        fallback and _step_11(base) and _CUSTOMER_ID.search(base["text"])
        and _matches(_PRE_55_VERIFIED_DESCRIPTORS, base["text"])
        and not _matches(_PRE_55_VERIFIED_DESCRIPTORS, _CUSTOMER_ID.sub(" ", base["text"]))
    ):
        return "customer_id"
    # §7.11 (Q3). (a) step 11's descriptors, whose every match disappears once CUSTOMER refuses CHECK and CHEQUE;
    # (b) a row printing CHECK or CHEQUE, fallen to steps 15 and 16.
    if (
        fallback and _step_11(base) and _CHECK_WORD.search(text)
        and _matches(_PRE_55_VERIFIED_DESCRIPTORS, base["text"])
        and not _matches(_CUSTOMER_WITHOUT_CHECK, base["text"])
    ):
        return "customer_check"
    # §5.2. (a) a registry alias or step 11's descriptors read only in the receiver field's value (the holder's name);
    # (b) steps 15 and 16, or another registry entity read outside that field.
    if _read_only_in_receiver_value(base) and (fallback or not _same_name(after.get("entity"), base.get("entity"))):
        return "receiver_value"
    # §7.9 (S2.3 review). (a) step 11's customer or invoice descriptor, the AP remittance or the invoice wire; (b) the
    # checkout's wire vetoes refuse it (the wire_vetoed fact) and it fell to steps 15 and 16.
    if _wire_veto_demotion(base, after):
        return "wire_veto"
    # §5.2. (a) steps 11 to 14 (the holder veto does not govern the registry, the recurrence pass, the card forms or
    # the claim form); (b) holder_named_payer, the holder test's own outcome (with the holder fact, when present).
    if _steps_11_to_14(base) and method == "holder_named_payer" and facts.get("holder", True):
        return "holder_veto"
    # §5.2, T11. (a) steps 11 to 14 (never a processor's settlement or template row); (b) steps 15 and 16, with the
    # numbered-company fact and not the holder's.
    if _steps_11_to_14(base) and fallback and facts.get("numbered") and not facts.get("holder"):
        return "numbered_company"
    # §7.0, §7.2. (a) a row 5.4's recurrence pass lifted (S3.1 re-review: the veto governs the recurrence pool only; no
    # 5.5 rule leaves a row verified on its own context, or by the wholesale auction form, unlifted or fallen for a
    # veto word, so such a row that lost its verification is undeclared); (b) left unlifted or fallen to steps 15 and
    # 16, on a row that names Square as a word and prints a pay word before its receiver fields.
    if (
        base["method"] in RECURRENCE_LIFT_METHODS and (unlifted or fallback)
        and (_SQUARE_WORD.search(text) is not None)
        and (_PAY_WORD.search(_before_receiver(text)) is not None)
    ):
        return "square_payroll"
    # §7.0. (a) a row 5.4's recurrence pass lifted (S3.1 re-review: never a registry row verified on its own context);
    # (b) left unlifted or fallen to steps 15 and 16, on a row the recurrence veto reads (the checkout's own fact when
    # present).
    if base["method"] in RECURRENCE_LIFT_METHODS and (unlifted or fallback) and _recurrence_vetoed_wording(after):
        return "recurrence_veto"
    # Decisions. (a) a row 5.4's recurrence pass lifted; (b) left unlifted, and its pool split: the row itself, or
    # another member of its 5.4 pool in this account, is read as another registry entity.
    if base["method"] in RECURRENCE_LIFT_METHODS and unlifted and key is not None and (
        (after.get("entity") and not _same_name(after["entity"], key)) or key in context.get("split", ())
    ):
        return "entity_split"
    # Decisions. (a) a row 5.4's recurrence lifted; (b) left unlifted, while another member of its 5.4 pool in this
    # account was taken out of the pool by a declared veto (_taken_out_of_pool).
    if (
        base["method"] == "recurring_operating_source" and unlifted and key is not None
        and context.get("vetoed", {}).get(key, set()) - {after["i"]}
    ):
        return "pool_below_recurrence_after_a_declared_veto"
    # I7 (§20, A3-H review). (a) any verifying rule; (b) counted and flagged as factoring_payout, by the pass's
    # overruling of an earlier rule (method factoring_payout_payer) or, for a Q5 or Q6 repeat, by its own factor
    # reading (the factoring_payer fact), or (audit B6: I25, I10) by a factoring payee the ledger names (the
    # payout_or_factoring fact) or a factoring review entity (the factoring_review fact).
    if after.get("tier") == "counted_flagged" and after.get("reason") == "factoring_payout" and (
        method == "factoring_payout_payer" or (
            base["method"] in Q5_Q6_METHODS
            and (facts.get("factoring_payer") or facts.get("payout_or_factoring") or facts.get("factoring_review"))
        )
    ):
        return "factor_never_verified"
    if base["method"] in Q5_Q6_METHODS:
        # I7 (§20). (a) a Q5 or Q6 verification; (b) held by a later 5.6 hold, named by its reason and the pass's own
        # hold reading (LATER_HOLD_CAUSES).
        if after.get("tier") == "excluded_pending_review":
            reason = after.get("reason")
            cause = LATER_HOLD_CAUSES.get((reason, None if reason == "holder_name" else facts.get("hold_rule")))
            if cause is not None:
                return cause
        # (b) the payer region now reads a relaying bank's customer (A3-G refinement), so the repeat is another's.
        if base["method"] == "repeat_wire_sender" and facts.get("relayed_customer"):
            return "q5_q6_relayed_customer"
        # (b) audit B8 (I46, Q2): the plural TRANSFERS is transfer wording, so a repeat that printed it with no
        # counterparty is held as a bare transfer.
        if (
            after.get("tier") == "excluded_pending_review" and after.get("reason") == "transfer_no_counterparty"
            and _TRANSFERS_WORD.search(_before_receiver(text))
        ):
            return "q5_q6_bare_transfers"
        # (b) audit B5 (I15, I55): the repeat was keyed on a bank's label, entry or reference (PNC's entry word, an
        # empty ORIG CO label); the payer region now reads the payer printed after it, or no payer (the pass's own
        # payer_label_layout fact), and the row is counted.
        if after.get("tier") == "counted_flagged" and facts.get("payer_label_layout"):
            return "q5_q6_payer_after_a_label"
        # (b) Q6c refuses a premium-coded insurer entry as proof (A3-H): counted as a refused payer.
        if after.get("reason") == "named_payer_purpose_refused" and facts.get("premium_coded"):
            return "premium_coded_insurer_entry"
        # (b) a §15 deferred source: counted, never verified by Q5 or Q6 (OQ4).
        if after.get("reason") == "named_payer_purpose_refused" and facts.get("deferred_source"):
            return "q5_q6_deferred_source"
        # (b) Q6c reads a short healthcare alias only as the whole payer name (final review I3).
        if base["method"] == "public_or_healthcare_payer" and facts.get("short_healthcare_alias"):
            return "short_healthcare_alias_in_a_name"
        # (b) the operating registry names the row, whose family rule decides it alone (Q5 and Q6 never read it).
        if method in REGISTRY_METHODS:
            return "q5_q6_left_to_its_family"
    # §7.5 (pass 6). (a) the accounts-payable remittance; (b) the counter-debit guard's own method.
    if base["method"] == "payer_remittance_descriptor" and method == "payer_remittance_with_counter_debit":
        return "counter_debit"
    # §7.2 (re-review N6). (a) an operating-registry verification; (b) the registry's own rule for a credit whose entry
    # field leads with a financing word (never verified; pass 7 holds it as financing).
    if base["method"] in REGISTRY_METHODS and rule == PLATFORM_FINANCING_ENTRY_RULE:
        return "platform_financing_entry"
    return "undeclared"


def _lender_move_cause(base: dict, after: dict, context: dict | None = None) -> str:
    """M2 (§14.2, §11): why a credit entered or left the lender-credit exclusion (and so moved eligible deposits)."""
    if not after.get("lender_credit"):
        return _narrowing(base, after) or f"left:{after['method']}"
    if base["state"] == "verified_revenue":
        return _demotion_cause(base, after, context)
    return f"entered:{after['rule'] or after['method']}"


def _rekeyed(base: dict, after: dict) -> dict[str, str]:
    """B1 (I60): each base account the later run set aside as a duplicate (its `duplicates`) mapped to the analysis the
    later run kept, when the base holds no account of that id itself (each kept analysis answers one base account)."""
    duplicates = after.get("duplicates") or {}
    rekeyed: dict[str, str] = {}
    for key in base["accounts"]:
        target = duplicates.get(key)
        if (
            key not in after["accounts"] and target in after["accounts"] and target not in base["accounts"]
            and target not in rekeyed.values()
        ):
            rekeyed[key] = target
    return rekeyed


def _parse_changed(old: dict, new: dict) -> bool:
    """B1 (I60): whether two snapshots of one statement read different credits (index, amount or masked text)."""
    def credits(account: dict) -> list[tuple]:
        return [(credit["i"], credit["cents"], credit["text"]) for credit in account["credits"]]

    return credits(old) != credits(new)


def _tier_label(credit: dict) -> str:
    return f"{credit.get('tier') or credit['state']}|{credit.get('reason') or credit['method']}"


def _record_reparse(reparsed: dict, old: dict, new: dict) -> None:
    """B1 (I60): one reparsed account's tiers on each side (in cents), its rows' moves by position (the statement's
    rows, read twice), and its eligible-deposit move."""
    for side, account in (("base", old), ("after", new)):
        for credit in account["credits"]:
            reparsed[side][credit.get("tier") or credit["state"]] += credit["cents"]
    old_by_index = {credit["i"]: credit for credit in old["credits"]}
    for credit in new["credits"]:
        prior = old_by_index.get(credit["i"])
        if prior is not None:
            slot = reparsed["moves"][(_tier_label(prior), _tier_label(credit))]
            slot[0] += 1
            slot[1] += credit["cents"]
    old_deposits, new_deposits = old.get("eligible_deposits"), new.get("eligible_deposits")
    if old_deposits is not None and new_deposits is not None:
        delta = round(new_deposits - old_deposits, 2)
        reparsed["eligible_deposits"]["unchanged" if delta == 0 else ("up" if delta > 0 else "down")] += 1


class BasisMismatch(ValueError):
    """S3.1: a compare of snapshots taken on two bases (their account ids name different things)."""


def _basis(snap: dict) -> str:
    return snap.get("basis") or "input"


def _guard_checks(after: dict, failures: dict, tiered: bool) -> dict:
    """S3.1 review (fix 3): each check of §14.3 in this run: whether it was checked (its facts are carried by the run's
    credits; G9's tier identity needs the tiers), and its status: held, failed, or not checked, which is never held."""
    present: set = set()
    for account in after["accounts"].values():
        for credit in account["credits"]:
            present.update((credit.get("facts") or {}).keys())
    checks: dict = {name: {"checked": True, "facts": []} for name in FACT_FREE_CHECKS}
    checks["G9 tiers"] = {"checked": tiered, "facts": ["tier"]}
    for name, keys in GUARD_FACTS.items():
        checks[name] = {"checked": set(keys) <= present, "facts": list(keys)}
    # S3.1 re-review: a failure recorded on a row proves its guard's check ran, whatever keys the run lacks, so a guard
    # none of whose checks carries every key is checked by its failure (each of its checks: a failure names no arm);
    # "not checked" is only a guard with no recorded result at all.
    carried = {name.split()[0] for name, check in checks.items() if check["checked"]}
    for name, check in checks.items():
        guard = name.split()[0]
        if failures.get(guard) and guard not in carried:
            check["checked"] = True
        check["status"] = NOT_CHECKED if not check["checked"] else ("failed" if failures.get(guard) else "held")
    return dict(sorted(checks.items(), key=lambda item: _guard_order(item[0])))


def _guard_order(name: str) -> tuple:
    guard, _, arm = name.partition(" ")
    number = re.match(r"G(\d+)", guard)
    return (int(number.group(1)) if number else 99, guard, arm)


def _counted_failures(failures: dict) -> list[str]:
    """S3.1 re-review: the failed guards the verdict counts: every guard with a failure recorded on a row, whether or
    not the run carries every key of its check (the recorded failure proves the check ran)."""
    return sorted((guard for guard, items in failures.items() if items), key=_guard_order)


def compare(base: dict, afters: list[dict], *, admissions: Iterable[str] | None = None) -> dict:
    """The census report of §14.2 and the guards of §14.3 (G7 excepted), base against each later snapshot, all of one
    basis (S3.1: a mix raises BasisMismatch). `admissions` (S3.1 review) names the entities the S1.5 ledger admissions
    added or updated (the owner's signed-off list): a verified row 5.5 reads as their financing proceeds is a declared
    demotion (`ledger_admission`); without it, none is."""
    admitted = frozenset(admissions or ())
    basis = _basis(base)
    for after in afters:
        if _basis(after) != basis:
            raise BasisMismatch(
                f"the base snapshot reads the {basis} basis and a later one the {_basis(after)} basis;"
                " a census compares snapshots of one basis"
            )
    report: dict = {"basis": basis, "basis_stats": {"base": base.get("basis_stats"),
                                                    "after": [after.get("basis_stats") for after in afters]},
                    "admitted_entities": len(admitted), "base": _summary(base), "runs": []}
    for after in afters:
        moves: dict = defaultdict(lambda: [0, 0, set()])
        left_non_revenue: dict = defaultdict(lambda: [0, 0, set()])
        demoted: dict = defaultdict(lambda: [0, 0, set()])
        deposits: Counter = Counter()
        lender_moves: dict = defaultdict(lambda: [0, 0, set()])
        failures: dict = defaultdict(list)
        street_ln: list = []
        gate: Counter = Counter()
        q6_unlabelled = [0, 0]
        g13_apart: dict = defaultdict(lambda: [0, 0, set()])
        bnpl_shapes: Counter = Counter()
        bnpl_listed: list = []
        unmatched = 0
        tiered = any(credit.get("tier") for account in after["accounts"].values() for credit in account["credits"])
        # G9 (review I1): an account that failed to classify, or that the base holds and this run lost, fails. Final
        # review M11: an error skip the base recorded and this run lost is a change too (its account is read below).
        base_skips, after_skips = base.get("skipped") or {}, after.get("skipped") or {}
        for reason in sorted(set(base_skips) | set(after_skips)):
            count = after_skips.get(reason, 0)
            if reason not in FILTER_SKIPS and count != base_skips.get(reason, 0):
                failures["G9"].append({"skipped": reason, "count": count, "base_count": base_skips.get(reason, 0)})
        # B1 (I60): a base account this run set aside as a duplicate is compared with the analysis this run kept; one
        # whose parse differs is a parse change, compared apart (`reparsed`), never as a rule's move.
        rekeyed = _rekeyed(base, after)
        reparsed: dict = {"accounts": [], "base": Counter(), "after": Counter(), "moves": defaultdict(lambda: [0, 0]),
                          "eligible_deposits": Counter()}
        # Final review M11: an account only this run holds (a new input, or one whose error skip vanished) has no base
        # to compare, but its row and account guards are read like any other's.
        only_after = sorted(set(after["accounts"]) - set(base["accounts"]) - set(rekeyed.values()))
        for key in only_after:
            new = after["accounts"][key]
            for credit in new["credits"]:
                for guard, failed in _row_guards(credit).items():
                    if failed:
                        failures[guard].append({"account": key, "i": credit["i"], "only_after": True,
                                                "text": credit["text"]})
            for failure in _account_guards(new, tiered):
                failures[failure["guard"]].append({"account": key, "only_after": True, **failure})
        for key, old in base["accounts"].items():
            new = after["accounts"].get(rekeyed.get(key, key))
            if new is None or new["rows"] != old["rows"]:
                unmatched += 1
                failures["G9"].append({"account": key, "unmatched": True})
                continue
            reparse = key in rekeyed and _parse_changed(old, new)
            if reparse:
                reparsed["accounts"].append({"base_account": key, "account": rekeyed[key]})
                _record_reparse(reparsed, old, new)
                # Its rows moved with the parse, not by a rule: only the guards that read the later row alone apply.
                for credit in new["credits"]:
                    for guard, failed in _row_guards(credit).items():
                        if failed:
                            failures[guard].append({"account": key, "i": credit["i"], "text": credit["text"]})
            # B1 (I60): a reparsed account pairs no row with its base (the rule moves below read none of its rows).
            old_by_index = {} if reparse else {credit["i"]: credit for credit in old["credits"]}
            # S3.1 review: the pool causes read the account's other credits.
            context = _account_context(
                ((old_by_index[credit["i"]], credit) for credit in new["credits"] if credit["i"] in old_by_index),
                admitted,
            )
            old_deposits, new_deposits = old.get("eligible_deposits"), new.get("eligible_deposits")
            if old_deposits is not None and new_deposits is not None and not reparse:
                delta = round(new_deposits - old_deposits, 2)
                deposits["unchanged" if delta == 0 else ("up" if delta > 0 else "down")] += 1
            for credit in new["credits"]:
                prior = old_by_index.get(credit["i"])
                if prior is None:
                    continue
                target = credit.get("tier") or credit["state"]
                slot = moves[(f"{prior['state']}|{prior['method']}", f"{target}|{credit.get('reason') or credit['method']}")]
                slot[0] += 1
                slot[1] += credit["cents"]
                slot[2].add(key)
                in_true = credit["state"] == "verified_revenue" or credit.get("tier") == "counted_flagged"
                if prior["state"] == "non_revenue" and credit["state"] != "non_revenue":
                    cause = _narrowing(prior, credit) or "outside_the_narrowings"
                    entry = left_non_revenue[cause]
                    entry[0] += 1
                    entry[1] += credit["cents"]
                    entry[2].add(key)
                    allowed = dict(NARROWINGS).get(cause)
                    if (
                        cause == "outside_the_narrowings" or (in_true and allowed is False)
                        # Final review I8: narrowings 2 and 6 lead to True only through verification (§6.3), and
                        # the OQ2 ruling never releases a BNPL consumer-side credit into True.
                        or (in_true and cause in VERIFIED_ONLY_NARROWINGS and credit["state"] != "verified_revenue")
                        or (in_true and cause == "8_oq2_bnpl_settlement" and _BNPL_CONSUMER_WORDS.search(credit["text"]))
                        # Audit B3 (I11), B6 (I10): a released processor card payout and a factoring review entity's
                        # payout are counted and flagged, never verified.
                        or (cause in COUNTED_ONLY_NARROWINGS and credit["state"] == "verified_revenue")
                    ):
                        failures["G1"].append({"account": key, "i": credit["i"], "cause": cause, "text": credit["text"]})
                    if cause == "8_oq2_bnpl_settlement":
                        # S3.1 (addition 3): each OQ2 row's public shape, so S3.2 can check that no consumer-side
                        # form (AFFIRMCARD, SP AFF, TRUEACCORD KLARNA, BALANCE WITHDRAWAL, REFUND) left D1.
                        shape = public_shape(credit["text"])
                        bnpl_shapes[shape] += 1
                        if len(bnpl_listed) < BNPL_LISTED_ROWS:
                            bnpl_listed.append({"account": key, "i": credit["i"], "entity": prior.get("entity"),
                                                "after": f"{target}|{credit.get('reason') or credit['method']}",
                                                "shape": shape})
                if prior["state"] == "verified_revenue" and credit["state"] != "verified_revenue":
                    cause = _demotion_cause(prior, credit, context)
                    entry = demoted[cause]
                    entry[0] += 1
                    entry[1] += credit["cents"]
                    entry[2].add(key)
                    # I7: the declared table is the one the compare reads.
                    if cause not in DECLARED_DEMOTIONS:
                        failures["undeclared_demotion"].append({"account": key, "i": credit["i"], "cause": cause,
                                                                "text": credit["text"]})
                if "lender_credit" in prior and bool(prior["lender_credit"]) != bool(credit.get("lender_credit")):
                    entry = lender_moves[_lender_move_cause(prior, credit, context)]
                    entry[0] += 1
                    entry[1] += credit["cents"] if credit.get("lender_credit") else -credit["cents"]
                    entry[2].add(key)
                for guard, failed in _row_guards(credit).items():
                    if failed:
                        failures[guard].append({"account": key, "i": credit["i"], "text": credit["text"]})
                if prior["text"] != credit["text"]:
                    # G7b: every credit whose normalized text changed (the street-LN guard, and since A3-G the SWIFT
                    # 50F strip) is listed. Final review I8: any non_revenue base it takes into True fails, except the
                    # street-LN guard's own release (_street_ln_release).
                    street_ln.append({"account": key, "i": credit["i"], "base": f"{prior['state']}|{prior['method']}",
                                      "after": f"{credit.get('tier') or credit['state']}|{credit['method']}",
                                      "text": credit["text"]})
                    if prior["state"] == "non_revenue" and in_true and not _street_ln_release(prior, credit):
                        failures["G7b"].append({"account": key, "i": credit["i"], "text": credit["text"]})
            for failure in _account_guards(new, tiered):
                failures[failure["guard"]].append({"account": key, **failure})
            if new.get("revenue_review_required"):
                for reason in {c["reason"] for c in new["credits"] if c.get("tier") == "excluded_pending_review"}:
                    gate[reason] += 1
            for credit in new["credits"]:
                facts = credit.get("facts") or {}
                if credit.get("reason") == "named_payer_unlabelled" and facts.get("q6_shape"):
                    q6_unlabelled[0] += 1
                    q6_unlabelled[1] += credit["cents"]
                if credit["state"] == "verified_revenue" and facts.get("numbered") and not _row_guards(credit)["G13"]:
                    entry = g13_apart[credit["method"]]
                    entry[0] += 1
                    entry[1] += credit["cents"]
                    entry[2].add(key)
        report["runs"].append({
            "summary": _summary(after),
            "accounts_unmatched": unmatched,
            "accounts_only_after": len(only_after),
            # B1 (I60): the base accounts compared with the analysis this run kept, and those whose parse differs.
            "rekeyed": {
                "accounts": len(rekeyed),
                "reparsed": {
                    "accounts": len(reparsed["accounts"]),
                    "listed": reparsed["accounts"],
                    "tiers": {side: {tier: round(cents / 100, 2) for tier, cents in reparsed[side].items() if cents}
                              for side in ("base", "after")},
                    "move_matrix": [
                        {"from": source, "to": target, "rows": value[0], "dollars": round(value[1] / 100, 2)}
                        for (source, target), value in sorted(reparsed["moves"].items(), key=lambda item: -item[1][1])
                    ],
                    "eligible_deposits": dict(reparsed["eligible_deposits"]),
                },
            },
            "move_matrix": [
                {"from": source, "to": target, "rows": value[0], "dollars": round(value[1] / 100, 2),
                 "statements": len(value[2])}
                for (source, target), value in sorted(moves.items(), key=lambda item: -item[1][1])
            ],
            "left_non_revenue": {
                cause: {"rows": value[0], "dollars": round(value[1] / 100, 2), "statements": len(value[2])}
                for cause, value in sorted(left_non_revenue.items())
            },
            # S3.1 (addition 3): the OQ2 rows by public shape (every shape counted, the first rows listed).
            "bnpl_settlements": {"rows": sum(bnpl_shapes.values()), "shapes": dict(bnpl_shapes.most_common()),
                                 "listed": bnpl_listed},
            "verified_demotions": {
                cause: {"rows": value[0], "dollars": round(value[1] / 100, 2), "statements": len(value[2])}
                for cause, value in sorted(demoted.items())
            },
            "eligible_deposits": dict(deposits),
            # M2 (§14.2, §11): lender credits (so eligible deposits, the other way) by the cause that moved each row.
            "lender_credit_moves_by_cause": {
                cause: {"rows": value[0], "lender_credit_dollars": round(value[1] / 100, 2),
                        "eligible_deposit_dollars": round(-value[1] / 100, 2), "statements": len(value[2])}
                for cause, value in sorted(lender_moves.items())
            },
            "street_ln_changes": street_ln,
            "gated_statements_by_held_reason": dict(gate.most_common()),
            "named_payer_unlabelled_with_q6_shape": {"rows": q6_unlabelled[0],
                                                     "dollars": round(q6_unlabelled[1] / 100, 2)},
            # G13 (review I1): Verified rows the numbered-company template matches that a processor's registry or
            # card form verified (its payer is the processor, §5.2); the precision sample reads them.
            "g13_listed_apart": {
                method: {"rows": value[0], "dollars": round(value[1] / 100, 2), "statements": len(value[2])}
                for method, value in sorted(g13_apart.items())
            },
            "guards": {guard: {"failures": len(items), "sample": items[:25]} for guard, items in sorted(failures.items())},
        })
        # S3.1 review (fix 3): which checks ran, the ones whose facts the run lacks, and the verdict over the checked.
        checks = _guard_checks(after, failures, tiered)
        failed = _counted_failures(failures)
        report["runs"][-1].update({
            "guard_checks": checks,
            "unchecked_guards": [name for name, check in checks.items() if not check["checked"]],
            "failed_guards": failed,
            "verdict": "fail" if failed else "hold",
        })
    return report


def _account_guards(account: dict, tiered: bool) -> list[dict]:
    """The account-level guards of §14.3: G9 (the four-tier identity, each tier with its state, every posted credit
    kept, and the metrics' tier totals), G12's credit-union count and G14's recurrence pools."""
    found: list[dict] = []
    credits = account["credits"]
    posted_count = account.get("posted_credit_count")
    if posted_count is not None and (posted_count != len(credits)
                                     or account.get("posted_credit_cents") != account["posted_cents"]):
        found.append({"guard": "G9", "posted_credits_without_a_revenue_state": posted_count - len(credits)})
    if tiered:
        by_tier: Counter = Counter()
        for credit in credits:
            tier = credit.get("tier")
            if tier not in TIER_STATES or credit["state"] not in TIER_STATES[tier]:
                found.append({"guard": "G9", "i": credit["i"], "tier": tier, "state": credit["state"]})
            by_tier[tier] += credit["cents"]
        if sum(by_tier.values()) != account["posted_cents"]:
            found.append({"guard": "G9", "identity": "rows"})
        totals = account.get("tier_totals")
        if totals is not None and (
            any(abs(totals[tier] - by_tier[tier]) > 1 for tier in TIER_STATES)
            or abs(sum(totals.values()) - account["posted_cents"]) > len(TIER_STATES)
        ):
            found.append({"guard": "G9", "identity": "metrics"})
    unions = [c for c in credits if c["method"] == "auto_lender_dealer_funding"
              and (c.get("facts") or {}).get("q7_credit_union") and not (c.get("facts") or {}).get("q7_listed")]
    if 0 < len(unions) < CREDIT_UNION_DEALER_MIN_CREDITS:
        found.extend({"guard": "G12", "i": c["i"], "credit_union_rows": len(unions)} for c in unions)
    pools: dict = defaultdict(list)
    lifted: dict = defaultdict(list)
    for credit in credits:
        facts = credit.get("facts") or {}
        if credit.get("entity") and facts.get("pool_candidate") and not facts.get("pool_vetoed"):
            pools[credit["entity"]].append(credit)
        if credit["method"] == "recurring_operating_source" and credit.get("entity"):
            lifted[credit["entity"]].append(credit)
    for entity, rows in lifted.items():
        needed = min((row.get("facts") or {}).get("pool_threshold", 2) for row in rows)
        if len(pools.get(entity, [])) < needed:
            found.extend({"guard": "G14", "i": row["i"], "pool": len(pools.get(entity, [])), "needed": needed}
                         for row in rows)
    return found


#: §14.5's Verified strata: stratum -> the revenue methods that fill it.
PRECISION_STRATA = {
    "q5_repeat_wires": lambda credit: credit["method"] == "repeat_wire_sender",
    "q6a_repeats": lambda credit: credit["method"] == "named_payer_repeats",
    "q6b_company_form": lambda credit: credit["method"] == "named_payer_company_form",
    "q6c_government_healthcare": lambda credit: credit["method"] == "public_or_healthcare_payer",
    "ap_remittance": lambda credit: credit["method"] == "payer_remittance_descriptor",
    "public_payers": lambda credit: credit["method"] == "public_payer_remittance",
    "invoice_wires": lambda credit: credit["method"] == "wire_remittance_purpose",
    # §7.1 card forms (rule card_settlement_form_<label>), §7.2 payout forms (alias <platform>_..._form), §7.8.
    "card_and_payout_forms": lambda credit: (
        (credit.get("rule") or "").startswith("card_settlement_form_")
        or (credit.get("alias") or "").endswith("_form")
        or credit["method"] == "wholesale_auction_payout_form"
    ),
    "q7_dealer_funding": lambda credit: credit["method"] == "auto_lender_dealer_funding",
}


def precision_sample(snap: dict, *, per_stratum: int = 20, largest_counted: int = 50, seed: int = 55) -> dict:
    """§14.5: a stratified sample of a 5.6 snapshot, digit-masked: `per_stratum` Verified rows of each stratum
    (every row when it holds fewer), the Verified rows G3 lists (the holder test matched) and G13 lists apart (the
    numbered-company template on a processor's settlement), and the `largest_counted` largest counted rows. Each row carries an empty `sort` for the reviewer: revenue, loan, own_money, refund,
    transfer, insurance, other or cannot_tell."""
    import random

    pools: dict = defaultdict(list)
    counted: list = []
    for key, account in snap["accounts"].items():
        for credit in account["credits"]:
            row = {"account": key, "i": credit["i"], "dollars": round(credit["cents"] / 100, 2),
                   "method": credit["method"], "tier": credit.get("tier"), "reason": credit.get("reason"),
                   "text": credit["text"], "sort": ""}
            if credit["state"] == "verified_revenue":
                for stratum, belongs in PRECISION_STRATA.items():
                    if belongs(credit):
                        pools[stratum].append(row)
                if (credit.get("facts") or {}).get("holder"):
                    pools["holder_test_rows"].append(row)
                if (credit.get("facts") or {}).get("numbered"):
                    pools["numbered_template_rows"].append(row)
            elif credit.get("tier") == "counted_flagged":
                counted.append(row)
    chooser = random.Random(seed)
    sample = {stratum: (rows if len(rows) <= per_stratum else chooser.sample(rows, per_stratum))
              for stratum, rows in sorted(pools.items())}
    sample["largest_counted"] = sorted(counted, key=lambda row: -row["dollars"])[:largest_counted]
    return sample


def _row_guards(credit: dict) -> dict[str, bool]:
    """The row-level guards of §14.3 and the review's G15 to G17 (True means the guard failed)."""
    facts = credit.get("facts") or {}
    tier = credit.get("tier")
    in_true = credit["state"] == "verified_revenue" or tier == "counted_flagged"
    verified = credit["state"] == "verified_revenue"
    method = credit["method"]
    row = _before_receiver(credit["text"])
    guards = {
        # A registry row reads the root with the holder's own words and §7.0's FUNDING settlements aside (review I1).
        "G2": verified and method != "auto_lender_dealer_funding" and bool(
            facts.get("registry_root") if method in REGISTRY_METHODS else facts.get("financing_root")
        ),
        # G3 and G17 (S4.2 review M1): §8.1's holds skip a row the registry, a payout entity or a factoring payee
        # claimed, so a platform's counted payout into a holder whose name the platform shares is no failure.
        "G3": bool(facts.get("holder")) and (
            (verified and method in IDENTITY_METHODS)
            or (verified and method == "operating_income_descriptor" and bool(facts.get("customer_descriptor")))
            or (tier == "counted_flagged" and not facts.get("claimed"))
        ),
        "G4": in_true and bool(facts.get("transfer_no_counterparty")),
        "G6": in_true and method == "direction_conflict",
        # G10 (review I1): a closed row never verifies; a push-rail row verifies through the registry only.
        "G10": verified and (
            facts.get("gate") == "closed" or (facts.get("gate") == "push" and method not in REGISTRY_VERIFYING_METHODS)
        ),
        "G11": in_true and bool(facts.get("pay_or_personal")),
        "G12": method == "auto_lender_dealer_funding" and (
            not facts.get("q7_payer_ok", True) or bool(facts.get("q7_veto_word"))
        ),
        # G13 (review I1): the full numbered-company guard, the DIRECT DEPOSIT <digits> template included, on the
        # rules that read it (§5.2: steps 11 to 14, Q5, Q6); the region form on every Verified row. A processor's
        # settlement printed after BMO's template (MISC PAYMENT <digits> GBL VI) is listed apart (g13_listed_apart).
        "G13": verified and (
            bool(facts.get("numbered_region"))
            or (bool(facts.get("numbered")) and (
                method in IDENTITY_METHODS
                or (method == "operating_income_descriptor" and bool(facts.get("customer_descriptor")))
            ))
        ),
        "G14": bool(facts.get("pooled_while_vetoed")),
        "G15": in_true and _REFUND_WORD.search(row) is not None,
        "G16": in_true and _TAX_REFUND_WORD.search(row) is not None,
        "G17": in_true and bool(facts.get("own_transfer")) and not facts.get("claimed"),
    }
    if facts.get("known_financing") and in_true and method not in {"auto_lender_dealer_funding"}:
        guards["G5"] = not facts.get("payout_or_factoring")
    return guards


def _print(report: dict) -> None:
    def line(summary: dict) -> str:
        parts = [f"classification {summary['version']}", f"statements {summary['statements_with_credits']}",
                 f"verified {summary['verified_share']}%", f"$0-verified {summary['zero_verified_statements']}"]
        if summary.get("true_share") is not None:
            parts += [f"true {summary['true_share']}%", f"held {summary['held_share']}%",
                      f"$0-true {summary['zero_true_statements']}",
                      f"median true {summary['median_statement_true_share']}%"]
        parts.append(f"gated {summary['gated_share']}%")
        return "; ".join(parts)

    print(f"basis: {report['basis']}")
    print("base: " + line(report["base"]))
    if report["base"].get("non_revenue_in_true"):
        print("  " + _sweep_line(report["base"]["non_revenue_in_true"]))
    for run in report["runs"]:
        print("after: " + line(run["summary"]) + f"; unmatched {run['accounts_unmatched']}")
        # B1 (I39, I60): the sweep, and the statements read from the analysis this run kept.
        print("  " + _sweep_line(run["summary"]["non_revenue_in_true"]))
        rekeyed = run.get("rekeyed") or {}
        if rekeyed.get("accounts"):
            reparsed = rekeyed["reparsed"]
            print(f"  rekeyed: {rekeyed['accounts']} statements read from the analysis this run kept;"
                  f" {reparsed['accounts']} with another parse (base tiers {reparsed['tiers']['base']},"
                  f" after {reparsed['tiers']['after']})")
        print("  left non_revenue: " + ", ".join(
            f"{cause} {value['rows']} rows/${value['dollars']:,.2f}/{value['statements']} st"
            for cause, value in run["left_non_revenue"].items()))
        print(f"  OQ2 BNPL rows: {run['bnpl_settlements']['rows']} in "
              f"{len(run['bnpl_settlements']['shapes'])} public shapes")
        print("  verified demotions: " + ", ".join(
            f"{cause} {value['rows']} rows/${value['dollars']:,.2f}/{value['statements']} st"
            for cause, value in run["verified_demotions"].items()))
        print("  eligible deposits: " + ", ".join(f"{name} {count}" for name, count in run["eligible_deposits"].items()))
        print("  lender credits by cause: " + ", ".join(
            f"{cause} {value['rows']} rows/${value['lender_credit_dollars']:,.2f}"
            for cause, value in run["lender_credit_moves_by_cause"].items()))
        # S3.1 review (fix 3): a check the run could not make is never printed as held.
        failed = run.get("failed_guards", list(run["guards"]))
        print("  guards: " + (", ".join(f"{guard} FAILED {run['guards'][guard]['failures']}" for guard in failed)
                              or "every checked guard holds"))
        if run.get("unchecked_guards"):
            print(f"  {NOT_CHECKED}: " + ", ".join(run["unchecked_guards"]))


def _output_repository(path: Path) -> Path | None:
    """S3.1 review (fix 4): the repository an output path would land in, or None. The path is normalised first:
    resolved (S3.1 re-review: before any prefix is stripped, so a volume's `\\\\?\\Volume{...}\\` name resolves to its
    drive instead of becoming a relative path), then the extended-length `\\\\?\\` and device `\\\\.\\` prefixes are
    stripped where what remains is still absolute; it is inside a repository when it, or any folder above it, holds a
    `.git` entry (a checkout's directory or a worktree's file), which covers every checkout and worktree of any
    repository whatever its spelling (a short name, a junction, an admin share, a volume name); and it is compared
    with this tool's own checkout case-insensitively on Windows."""
    try:
        text = str(Path(path).resolve())
    except OSError:
        text = os.path.abspath(path)
    for prefix, replacement in (("\\\\?\\UNC\\", "\\\\"), ("//?/UNC/", "//"), ("\\\\?\\", ""), ("//?/", ""),
                                ("\\\\.\\", ""), ("//./", "")):
        if text.upper().startswith(prefix):
            stripped = replacement + text[len(prefix):]
            if os.path.isabs(stripped):
                text = stripped
            break
    resolved = Path(text)
    for folder in (resolved, *resolved.parents):
        try:
            if os.path.lexists(folder / ".git"):
                return folder
        except OSError:
            continue
    own = os.path.normcase(str(ROOT.resolve()))
    where = os.path.normcase(str(resolved))
    if where == own or where.startswith(own.rstrip("\\/") + os.sep):
        return ROOT
    return None


def _use_code_root(code_root: Path) -> bool:
    """Put the checkout's `analysis` package first on sys.path; False if another one is already loaded."""
    sys.path.insert(0, str(code_root.resolve()))
    import analysis

    return Path(analysis.__file__).resolve().is_relative_to(code_root.resolve())


def _read(path: Path) -> dict:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    snap = commands.add_parser("snapshot", help="re-classify the cache with one checkout's code")
    snap.add_argument("--data-dir", type=Path, help="the webapp data directory (read-only)")
    snap.add_argument("--jobs-db", type=Path, help="a copy of the tryout host's job store (read-only)")
    snap.add_argument("--out", type=Path, required=True, help="the snapshot to write (outside the repo)")
    snap.add_argument("--code-root", type=Path, default=ROOT, help="the checkout whose analysis package classifies")
    snap.add_argument("--limit", type=int, default=None, help="read only the first N analyses")
    snap.add_argument("--basis", choices=BASES, default="input",
                      help="input: every cached analysis input (the default); pdf: one analysis per source PDF")
    comp = commands.add_parser("compare", help="compare a base snapshot with later ones")
    comp.add_argument("--base", type=Path, required=True)
    comp.add_argument("--after", type=Path, required=True, action="append")
    comp.add_argument("--out", type=Path, required=True, help="the report to write (outside the repo)")
    comp.add_argument("--admissions", type=Path, default=None,
                      help="the S1.5 ledger admissions' signed-off entity list (JSON: {\"entities\": [...]} or a list);"
                           " without it no demotion is declared ledger_admission")
    samp = commands.add_parser("sample", help="draw the precision sample of a 5.6 snapshot (§14.5)")
    samp.add_argument("--snapshot", type=Path, required=True)
    samp.add_argument("--out", type=Path, required=True, help="the sample to write (outside the repo)")
    swp = commands.add_parser("sweep", help="the non-revenue wording left in True of one snapshot, by class (B1)")
    swp.add_argument("--snapshot", type=Path, required=True)
    swp.add_argument("--out", type=Path, required=True, help="the sweep to write (outside the repo)")
    args = parser.parse_args(argv)

    repository = _output_repository(args.out)
    if repository is not None:
        print(f"refused: {args.out} is inside the repository at {repository}; the census holds statement figures",
              file=sys.stderr)
        return 2
    if args.command == "snapshot":
        if (args.data_dir is None) == (args.jobs_db is None):
            print("refused: name exactly one of --data-dir and --jobs-db", file=sys.stderr)
            return 2
        if args.data_dir is not None and not (args.data_dir / "webapp.db").is_file():
            print(f"refused: {args.data_dir} holds no webapp.db", file=sys.stderr)
            return 2
        if not _use_code_root(args.code_root):
            print(f"refused: another analysis package is already loaded, not {args.code_root}", file=sys.stderr)
            return 2
        stats: dict = {}
        if args.data_dir is not None:
            accounts = cached_accounts(args.data_dir, args.limit, basis=args.basis, stats=stats)
        else:
            accounts = job_accounts(args.jobs_db, basis=args.basis, stats=stats)
        result = snapshot(accounts, basis=args.basis, basis_stats=stats)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(gzip.compress(json.dumps(result).encode("utf-8")))
        print(f"classification {result['classification_version']} ({result['basis']} basis): "
              f"{len(result['accounts'])} accounts; skipped: {result['skipped']}; "
              f"stale parses: {len(result['stale_parses'])}; basis: {result['basis_stats']}")
        return 0
    if args.command == "sample":
        sample = precision_sample(_read(args.snapshot))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(sample, indent=1) + "\n", encoding="utf-8")
        print("; ".join(f"{stratum} {len(rows)}" for stratum, rows in sample.items()))
        return 0
    if args.command == "sweep":
        swept = sweep(_read(args.snapshot))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(swept, indent=1) + "\n", encoding="utf-8")
        print(_sweep_line(swept))
        return 0
    admissions: list[str] = []
    if args.admissions is not None:
        try:
            listed = json.loads(args.admissions.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            print(f"refused: the admissions list {args.admissions} cannot be read ({type(error).__name__})",
                  file=sys.stderr)
            return 2
        admissions = listed.get("entities", []) if isinstance(listed, dict) else listed
        if not isinstance(admissions, list) or not all(isinstance(name, str) for name in admissions):
            print(f"refused: the admissions list {args.admissions} holds no list of entity names", file=sys.stderr)
            return 2
    try:
        report = compare(_read(args.base), [_read(path) for path in args.after], admissions=admissions)
    except BasisMismatch as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, default=list) + "\n", encoding="utf-8")
    _print(report)
    # S3.1 review (fix 3): the verdict counts the checked guards only; the unchecked are listed, never held.
    return 1 if any(run["verdict"] == "fail" for run in report["runs"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
