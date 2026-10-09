"""Audit fix batch B12 (I62): the classification contract (docs/transaction-classification.md) and the README describe
the code as built after the audit's fix batches. A grep check, no statement data:

- every revenue tier and every reason code of `analysis.revenue.REVENUE_TIER_REASONS` is in the contract's reason
  table, with its tier and its label;
- every withholding denominator mode is named in the contract and the README, and the contract says that a revenue
  mode's denominator is what `eligible_deposits` carries;
- the contract lists the statement passes in the order `classify_statement_transactions` runs them;
- the stale sentences the audit found (identifiable interest standing for every interest form, every unverified
  deposit needing review, a verified-only opt-in, five statement passes) are gone;
- the true revenue spec's section 20 records every audit fix batch, section 19.1 the owner's decisions taken since
  its review, and section 17.1's open section 15 items say how the code reads them today.

B12 review round 1: the reason table is parsed and compared with REVENUE_TIER_REASONS row by row, in its order; the
insurer row names every word the code's insurer hold reads; the metric, withholding and section 17.1 sentences say
what the code does (fabricated rows, CONTOSO, NORTHWIND and SAMPLE, for the section 15 readings)."""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from analysis import transaction_classifier, true_revenue
from analysis.revenue import REVENUE_TIER_REASONS, REVENUE_TIERS, WITHHOLDING_DENOMINATOR_MODES
from analysis.schema import Statement, Transaction

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "transaction-classification.md"
README = ROOT / "README.md"
SPEC = ROOT / "docs" / "superpowers" / "specs" / "2026-09-28-true-revenue-design.md"


def _flat(path: Path) -> str:
    """The document with every whitespace run (line breaks included) read as one space."""
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def _section(text: str, heading: str, next_heading: str) -> str:
    start = text.index(heading)
    return text[start:text.index(next_heading, start + len(heading))]


REASON_TABLE_HEADER = "| Reason code | Tier | Label | When (true revenue spec) |"


def _reason_table() -> list[list[str]]:
    """The contract's reason table, one list of four stripped cells per row (header and rule left out)."""
    text = CONTRACT.read_text(encoding="utf-8")
    start = text.index(REASON_TABLE_HEADER)
    end = text.find("\n\n", start)
    lines = text[start:end if end >= 0 else len(text)].splitlines()
    assert re.fullmatch(r"\|(?:-+\|){4}", lines[1]), lines[1]
    return [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines[2:]]


def test_the_contracts_reason_table_repeats_revenue_tier_reasons_in_its_order():
    rows = _reason_table()
    assert all(len(cells) == 4 and cells[3] for cells in rows), [cells for cells in rows if len(cells) != 4]
    assert [tuple(cells[:3]) for cells in rows] == [
        (f"`{code}`", f"`{tier}`", label) for code, (tier, label) in REVENUE_TIER_REASONS.items()
    ]


def test_the_insurer_named_payer_row_names_every_word_the_insurer_hold_reads():
    """The row's When cell names each name word of true_revenue._INSURER_NAME and the claim-word arm."""
    when = {cells[0]: cells[3] for cells in _reason_table()}["`insurer_named_payer`"]
    words = re.findall(r"[A-Z]{4,}", true_revenue._INSURER_NAME.pattern)
    assert words == ["INSUR", "ASSURANCE", "MUTUAL", "CASUALTY", "INDEMNITY", "UNDERWRIT"]
    for word in words:
        assert f"`{word}" in when, word
    assert "CLAIM" in true_revenue._CLAIM_WORD.pattern
    assert "`CLAIM`" in when and "`HCCLAIMPMT`" in when and "healthcare payer" in when


def test_the_insurer_named_payer_row_names_every_insurer_spelling_and_the_brand_table():
    """Audit I26 (R2-OW07): the When cell names each spelling true_revenue._INSURER_SPELLINGS reads and the brand
    table, and the holder strip."""
    when = {cells[0]: cells[3] for cells in _reason_table()}["`insurer_named_payer`"]
    for word in ("ASSUR", "ASSURANCES", "ASSURANT", "ASSUREUR", "MUTUA", "CASUALT", "INDEMN", "INS", "P AND C",
                 "LOSS PMT", "SUBRO"):
        assert f"`{word}" in when, word
        assert word.split()[0] in true_revenue._INSURER_SPELLINGS.pattern, word
    assert "`INSURER_CREDIT_BRANDS`" in when and "without the holder's own names" in when
    assert "audit I26" in when and "`ASSURED`" in when and "`CLM`" in when


def test_the_insurer_paid_for_services_row_names_the_grounds_and_the_refusals():
    """Owner ruling 2026-10-02 (the underwriter's Q2), R2-OW08: the When cell names the three grounds, the service
    forms, the 31-day span, the not-for-work words and what precedes the count; the insurer_payer and
    insurer_named_payer rows name the release."""
    when = {cells[0]: cells[3] for cells in _reason_table()}
    cell = when["`insurer_paid_for_services`"]
    for words in ("repair shop", "insurance agency", "clinic", "pharmacy", "`DRP`", "`AGENTS EFT`", "`AGTEFT`",
                  "`CONTINGENCY`", "`VENDOR PMT`", "never a wire's `REF`", "three or more times within an inclusive "
                  "31-day span", "premium, refund, return, dividend", "unless a commission prints",
                  "every hold but the insurer-name hold still wins", "never verified and never a Q5 or Q6 repeat",
                  "the underwriter's Q2"):
        assert words in cell, words
    assert "the underwriter's Q2 release (2026-10-02, R2-OW08) refuses" in when["`insurer_payer`"]
    assert "is `insurer_paid_for_services` instead" in when["`insurer_named_payer`"]
    contract = _flat(CONTRACT)
    for words in ("is re-stated as an unverified deposit of method `insurer_paid_for_services`",
                  "`INSURER_FOR_WORK_STATEMENT_ARM`, which is off",
                  "An insurer's credit paid for the business's work is counted and flagged as "
                  "`insurer_paid_for_services`"):
        assert words in contract, words


@pytest.mark.parametrize("tier", REVENUE_TIERS)
def test_every_revenue_tier_is_named_in_the_contract(tier):
    assert f"`{tier}`" in _flat(CONTRACT)


@pytest.mark.parametrize("mode", WITHHOLDING_DENOMINATOR_MODES)
def test_every_withholding_denominator_mode_is_named_in_the_contract_and_the_readme(mode):
    assert f"`{mode}`" in _flat(CONTRACT) or f"={mode}`" in _flat(CONTRACT)
    assert re.search(rf"(?:`|=){re.escape(mode)}`", _flat(README)), mode


def test_the_contract_and_the_readme_say_eligible_deposits_carries_a_revenue_modes_denominator():
    contract = _section(_flat(CONTRACT), "## Withholding rate", "## Extension rule")
    assert "`eligible_deposits` carries the selected denominator" in contract
    assert "`legacy_eligible_deposits`" in contract
    assert "`eligible_deposits` carries the selected denominator" in _flat(README)


def test_the_contract_says_only_held_credits_need_review():
    metrics = _section(_flat(CONTRACT), "## Metric definitions", "## Withholding rate")
    assert "`unverified_deposit_total` and `unverified_deposit_count`" in metrics
    assert "counted plus held" in metrics
    assert "only the held part needs review" in metrics
    # B12 review round 1: the gate reads the held total; revenue_review_items is the held-row count, no gate input.
    assert "its total (`excluded_pending_review_total`) feeds `revenue_review_required`" in metrics
    assert "`revenue_review_items` is the held-row count" in metrics


#: The run and deploy files of this repository (B12 review round 1: the contract says none sets the mode).
RUN_AND_DEPLOY_PATTERNS = (
    "*.toml", "*.yml", "*.yaml", "*.ini", "*.cfg", "*.ps1", "*.sh", ".env*", "Dockerfile*", "Procfile",
    ".github/**/*", "tools/**/*.sh", "tools/**/*.ps1", "webapp/**/*.sh", "webapp/**/*.ps1", "webapp/**/*.toml",
)


def test_no_run_or_deploy_file_of_the_repository_sets_the_withholding_mode():
    contract = _section(_flat(CONTRACT), "## Withholding rate", "## Extension rule")
    assert "no run or deploy file in this repository sets `WITHHOLDING_DENOMINATOR_MODE`" in contract
    files = {path for pattern in RUN_AND_DEPLOY_PATTERNS for path in ROOT.glob(pattern) if path.is_file()}
    assert ROOT / "run.ps1" in files and ROOT / "pytest.ini" in files
    setting = sorted(str(path.relative_to(ROOT)) for path in files
                     if "WITHHOLDING_DENOMINATOR_MODE" in path.read_text(encoding="utf-8", errors="replace"))
    assert setting == []


def test_the_contract_says_the_residual_interest_dividend_reward_and_reimbursement_forms_are_held():
    contract = _flat(CONTRACT)
    assert re.search(
        r"bare `INTEREST`[^.]*`DIVIDEND`[^.]*`REWARDS`[^.]*`REIMB[^`]*`[^.]*held as `non_sale_purpose`", contract
    )


#: The classifier's statement passes after duplicate detection and the lender recurrence, in the order
#: classify_statement_transactions calls them, with the contract's name for each.
PASS_CALLS = (
    ("_label_unnamed_potential_payees(", "labels for unnamed potential payees"),
    ("_apply_reversal_pair_context(", "reversal pairs"),
    ("_apply_operating_source_context(", "operating-source context"),
    ("_apply_payer_remittance_counter_debit_guard(", "counter-debit guard (pass 6)"),
    ("apply_true_revenue_pass(", "true-revenue pass (pass 7)"),
    # Owner ruling 2026-10-02 (the underwriter's Q5), R2-OW13: the returned funder payments, after pass 7.
    ("_apply_returned_funder_payments(", "returned funder payments (pass 7b"),
    # The owner's answer of 2026-10-07 to audit round 3's R3-73 (R3-B02): the re-presented returned payments.
    ("_apply_represented_funder_payments(", "re-presented returned payments (pass 7c"),
)


def test_the_contract_lists_the_statement_passes_in_the_classifiers_order():
    # The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): classify_statement_transactions runs the
    # shared prefix, then one Zelle reading's pass 7, pass 7b and duplicate finalisation; read in that order.
    source = (inspect.getsource(transaction_classifier._classify_statement_prefix)
              + inspect.getsource(transaction_classifier._classify_statement_reading))
    assert "_classify_statement_prefix(" in inspect.getsource(transaction_classifier.classify_statement_transactions)
    positions = [source.index(call) for call, _ in PASS_CALLS]
    assert positions == sorted(positions)
    assert source.index("duplicate_of[index] = seen[fingerprint]") < source.index("recurring_fixed_debit")
    assert source.index("recurring_fixed_debit") < positions[0]
    assert positions[-1] < source.index("for index, original_index in duplicate_of.items()")

    contract = _flat(CONTRACT)
    sentence = re.search(r"Statement passes run in this order: ([^.]*)\.", contract)
    assert sentence, "the contract's statement-pass sentence"
    names = [name.strip() for name in sentence.group(1).split(";")]
    expected = ["duplicates", "recurrence"] + [name for _, name in PASS_CALLS] + ["duplicate finalisation"]
    assert [next((e for e in expected if e in name), name) for name in names] == expected


STALE_SENTENCES = (
    # (a) line 96: identifiable interest stood for every interest, reward and reimbursement form.
    (CONTRACT, "tax refunds, rewards, fee refunds, interest, and reimbursements bypass manual revenue review"),
    # (b) line 599: every unverified deposit needed review.
    (CONTRACT, "posted credits that could be operating revenue but require review"),
    # (c) the withholding opt-in named the verified mode only.
    (CONTRACT, "to opt into verified classified revenue instead"),
    (README, "`WITHHOLDING_DENOMINATOR_MODE=verified_revenue` to use verified classified revenue instead"),
    # (d) line 354: five statement passes.
    (CONTRACT, "duplicates; recurrence; reversal pairs; operating-source context; duplicate finalisation"),
    # B12 review round 1: the held rows' count read as a gate input.
    (CONTRACT, "and its rows (`revenue_review_items`) feed `revenue_review_required`"),
    # B12 review round 1: a tryout-host claim this repository cannot show.
    (CONTRACT, "and the tryout host sets none"),
    # B12 review round 1: a builder's DRAW read as counted (the code holds it as non_sale_purpose).
    (SPEC, "Both stay counted and flagged, never verified (OQ4)"),
    # The owner's ruling of 2026-10-02 (the underwriter's Q12): GOV class E no longer waits for the owner, and WSIB's
    # no-purpose payment is non_revenue.
    (CONTRACT, "which waits for the owner"),
    (SPEC, "WSIB paying a clinic stays counted"),
    # The owner's ruling of 2026-10-02, R2-OW03: Q12's rows carry a display reason, and a Zelle deposit may be
    # confirmed, so the Zelle code is no longer the one exception and non-revenue rows are no longer all control-free.
    (CONTRACT, "The one exception is a Zelle deposit"),
    # The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): the Q3-only sentences, which named the
    # exclusion as every Zelle deposit's reading, are retired for ones that name the reading.
    (SPEC, "Amended 2026-10-02 (§2.1, §19.1): Zelle deposits are `non_revenue` (`zelle_excluded`)."),
    (SPEC, "- **Zelle (owner ruling 2026-10-02, the underwriter's Q3):** every posted Zelle credit is `non_revenue`"),
    (SPEC, "26. Then, after every step above and before the $1 floor, the Zelle policy"),
    (SPEC, "Never a Zelle row (Q3 (2026-10-02)), never a row the registry"),
    (SPEC, "Never read: a claimed row; a Zelle row (Q3 (2026-10-02)); a possible return"),
    (SPEC, "| `webapp/settings.py` | none |"),
    (CONTRACT, "- Every Zelle deposit is `non_revenue` (`zelle_excluded`), whoever sent it"),
    (CONTRACT, "until then such a row is non-revenue like any other"),
    (SPEC, "A `non_revenue` row carries a reason only when an owner ruling of 2026-10-02 decided it (the Zelle"),
    (SPEC, "Non-revenue rows have no controls (§15). "),
    # Owner ruling 2026-10-02, R2-OW04 (the underwriter's Q8): §6.3 has twelve narrowings, and §15 no longer defers the
    # lease-to-own payers' merchant payouts.
    (SPEC, "except through exactly these eleven named narrowings"),
    (SPEC, "lease-to-own payers (Acima), and the other accounts-payable items"),
    # Owner ruling 2026-10-02, R2-OW06 (the underwriter's Q11): a builder's draw is counted, the seller payouts are
    # non_revenue, and asset_sale_proceeds is in the code.
    (SPEC, "a builder's progress `DRAW` waits for the owner's ruling (§15)"),
    (SPEC, "whether to hold them waits for the owner (I45)"),
    (SPEC, "and, once its batch lands, `asset_sale_proceeds`"),
    # R2-OW06 review round 1: FLEET alone left the asset nouns of a sale, and an IAA hold yields only with no later hold.
    (SPEC, "`CRANE(S)`, `FLEET`, `SEMI(S)`"),
    (CONTRACT, "insurer-name hold alone holds it, or where an invoice or customer-payment"),
    # Owner ruling 2026-10-02, R2-OW08 (the underwriter's Q2): §6.3 has thirteen narrowings, and the I27 question's
    # counting is in the code.
    (SPEC, "except through exactly these twelve named narrowings"),
    (SPEC, "its counting waits for its batch"),
    # Owner ruling 2026-10-02, R2-OW09 (the underwriter's Q9): the rows T4 holds are released, and §8.1's residuals no
    # longer wait for a T4 ruling.
    (SPEC, "The release of the rows T4 holds waits for its own batch"),
    (SPEC, "Recorded residuals of the roots, for the owner's T4 ruling"),
    (SPEC, "the lenders' service payments T4 holds) waits for its batch"),
    (SPEC, "lenders paying for services wait for the owner's ruling on audit I16"),
)


@pytest.mark.parametrize("path, sentence", STALE_SENTENCES)
def test_the_stale_sentences_are_gone(path, sentence):
    assert sentence not in _flat(path)


def test_the_spec_section_20_records_every_audit_fix_batch():
    spec = _flat(SPEC)
    amendments = spec[spec.index("## 20. Implementation amendments"):]
    for batch in range(1, 13):
        assert re.search(rf"[Aa]udit fix batch B{batch}\b", amendments), f"B{batch}"


#: Spec §19.1's decision lines: each bold lead-in, and words its line must carry (B12 review round 1).
SECTION_19_1_DECISIONS = (
    ("**2026-09-29, the plan.**", ("implementation plan", "delegated")),
    ("**2026-09-30, Q5 and Q6 kept.**", ("kept Q5 and Q6", "waived the A3 bar")),
    ("**2026-09-30, the MCA principle.**", (
        "MCA underwriting tool", "Government money unrelated to the business is never revenue",
        "a government or an insurer paying the business for its goods or services still is",
    )),
    ("**2026-09-30, government money (GOV).**", (
        "held as `personal_income` (class B)", "a tax refund is `non_revenue` (class C)",
        "held as `non_sale_purpose` (class D)", "(class A)", "(class E) wait for the owner",
    )),
    ("**2026-09-30 to 2026-10-02, decisions the owner delegated during the audit fix run**", (
        "the owner may overrule each", "`TUITION`", "`STUDENT ID`", "audit I57", "a trust payment with no purpose stays held",
        "`IRS TREAS 310`", "`INT`", "`Prov./Loc.G.Paym Canada`", "`personal_income`",
    )),
    # The owner's rulings of 2026-10-02 (the underwriter's answers), in the order their batches land.
    ("**2026-10-02, government payments that print no purpose (Q12).**", (
        "`non_revenue`", "`MN STATE MMB`", "`36 TREAS 310 MISC PAY`", "WSIB", "keeps counting",
    )),
    ("**2026-10-02, the underwriter's Q13: a processor payout printed as a bare card credit stays excluded.**", (
        "keep them excluded", "`PROCESSOR_CARD_PAYOUT_RELEASE`", "`CASH_APP_CARD_PUSH_RELEASE`", "stays off",
        "the owner may overrule it", "`VISA DIRECT`", "audit I11",
    )),
    ("**2026-10-02, Zelle and no-sender e-Transfers (Q3, Q3b).**", (
        "`zelle_excluded`", "whoever sent it", "`p2p_round_repeat_no_sender`", "keyed on the amount",
    )),
    ("**2026-10-02, lease-to-own and patient-financing payouts (Q8).**", (
        "lease-to-own", "`customer_financing_payout`", "never verified", "`customer_financing_lump_sum`", "one-off",
    )),
    ("**2026-10-02, an auto lender's PAYABLES with no dealer evidence (Q9 c').**", (
        "`lender_paid_for_services`", "dealer evidence", "repossession", "never verified",
    )),
    ("**2026-10-02, builder progress draws and asset sales (Q11).**", (
        "`construction_progress_draw`", "`asset_sale_proceeds`", "dealer evidence", "go straight to non-revenue",
    )),
    # Audit I26 (R2-OW07), attributed apart from the underwriter's Q2 answer, which it was not asked in.
    ("**2026-10-02, every insurer spelling (I26, by Q6 of 2026-09-28; not asked in Q2 (2026-10-02)).**", (
        "`insurer_named_payer`", "INS", "LOSS PMT", "not asked",
    )),
    # Owner ruling 2026-10-02 (the underwriter's Q2), R2-OW08.
    ("**2026-10-02, insurers paying for the business's work (I27; Q2).**", (
        "`insurer_paid_for_services`", "three or more", "31-day span", "one-off claim", "owner switch, OFF",
    )),
    # Owner ruling 2026-10-02 (the underwriter's Q9 (a), (b), (c)), R2-OW09.
    ("**2026-10-02, Q9: finance-named customers, rent received and lenders paying for services (I16, I36(d)).**", (
        "Keep them as true revenue", "`finance_named_customer`", "`lessor_rent`", "`lender_paid_for_services`",
        "hidden-loan guard",
    )),
    # Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11.
    ("**2026-10-02, premium trust accounts (Q10; audit I39 with I24, I38).**", (
        "Hold every deposit into an account titled", "`premium_trust_account`", "non-revenue rows stay non-revenue",
        "Q2",
    )),
    # Owner ruling 2026-10-02 (the underwriter's Q1), R2-OW12.
    ("**2026-10-02, Q1: wires with no sender (I12).**", ("`wire_no_sender`", "possible funding", "never changes the tier")),
    # Owner ruling 2026-10-02 (the underwriter's Q5), R2-OW13.
    ("**2026-10-02, bounced funder payments (Q5; I29).**", (
        "returned funder payment", "paid to lenders", "withholding", "lender count",
    )),
    # Owner ruling 2026-10-02 (the underwriter's Q7), R2-OW14.
    ("**2026-10-02, the withholding basis and cash deposits (Q7; I34).**", (
        "`true_revenue`", "default", "selectable", "never Verified",
    )),
    # Owner ruling 2026-10-02 (the underwriter's Q6), R2-OW15.
    ("**2026-10-02, returns across consecutive statements and chargebacks (Q6; I42).**", (
        "consecutive", "preceding statement", "never deducted", "adjustments",
    )),
    # Owner ruling 2026-10-02 (the underwriter's Q4), R2-OW16.
    ("**2026-10-02, transfers between the business's accounts in a package (Q4; I30).**", (
        "I'll review it anyways", "`own_account_transfer_matched`", "marks it Verified", "no account number",
    )),
    # The owner's amendment of 2026-10-06 to the underwriter's Q3, R2-OW17.
    ("**2026-10-06, Zelle as True revenue is a Settings choice (Q3 amended).**", (
        "Mark Zelle Payments as True Revenue", "default", "Yes", "`zelle_excluded`", "nothing is reprocessed",
    )),
    # The owner's request of 2026-10-06 (lender payment changes), R2-OW18.
    ('**2026-10-06, lender payment changes (the owner\'s request).**', (
        'decrease', 'increase', 'stop', 'weekly equivalent', 'information only',
    )),
    # Audit round 3, R3-B02: the owner's answer of 2026-10-07 to R3-73.
    ('**2026-10-07, a returned funder payment its funder re-presents (audit round 3, R3-73; extends Q5 of '
     '2026-10-02).**', (
        '"Count it once (Recommended)"', 'off its cycle', 'exact 2x catch-up', 're-presented on <date>',
        '`returned_funder_represented`', 'R3-B02',
    )),
    # Audit round 3, R3-B03: the owner's answer of 2026-10-07 to R3-79.
    ('**2026-10-07, lump-sum payoffs in the withholding rate (audit round 3, R3-79).**', (
        '"Exclude worded payoffs (Recommended)"', 'PAYOFF', 'PAY-OFF', 'PREPAYMENT', 'BUY OUT', 'PAYOUT',
        'paid to lenders', 'lender count', 'Lump-sum payment to <funder>', '`lump_sum_payoff_excluded`', 'R3-B03',
    )),
    # Audit round 3, R3-B05: the owner's answer of 2026-10-07 to R3-25.
    ("**2026-10-07, a merchant who misses payments then catches up with an exact multiple (audit round 3, R3-25; the "
     "lender payment changes of 2026-10-06).**", (
        "Add a 'Caught up' line", "missed scheduled payments", "one line per event",
        "a multiple with no missed payment before it gets no line", "`catch_up`", "`lender_payment_catch_ups`",
        "Information only", "R3-B05",
    )),
)


def test_the_spec_section_19_1_records_the_owners_decisions_taken_since_its_review():
    text = SPEC.read_text(encoding="utf-8")
    review = _section(text, "\n### 19.1 Owner decisions since the review\n", "\n## 20. Implementation amendments")
    bullets = [line for line in review.splitlines() if line.startswith("- **")]
    assert [line[2:].split("**", 2)[1] for line in bullets] == [lead[2:-2] for lead, _ in SECTION_19_1_DECISIONS]
    for line, (lead, words) in zip(bullets, SECTION_19_1_DECISIONS):
        assert line.startswith(f"- {lead}"), lead
        for word in words:
            assert word in line, (lead, word)


#: Spec §17.1's I18 and I45 line against the code (B12 review round 1). Fabricated Bank of America rows. Since the
#: owner's ruling of 2026-10-02 (the underwriter's Q11, R2-OW06): a homebuilder's DRAW, as an ACH entry and as a wire's
#: purpose, is counted and flagged as construction_progress_draw (it was held as non_sale_purpose, §8.1's financing
#: words without a root; §20, B7 I18); the same wire without DRAW is a named sender's counted wire; an equipment
#: auction's seller payout (Ritchie Bros, a public company in ASSET_SALE_PAYERS) to a contractor, no dealer, is
#: non_revenue / asset_sale_proceeds (it was counted and flagged, never verified, I45).
SECTION_15_HOLDER = "CONTOSO CONSTRUCTION LLC"
_BOFA_ACH = "{payer} DES:{entry} ID:1234567 INDN:CONTOSO CONSTRUCTION LLC CO ID:1234567890 CCD"
_BOFA_WIRE = ("WIRE TYPE WIRE IN DATE 540302 TIME 1200 ET TRN 2054030200012345 SEQ 123456/000001 ORIG NORTHWIND HOMES "
              "LLC ID 1234 SND BK SAMPLE BANK ID 123456789 PMT DET {purpose}")
SECTION_15_ROWS = (
    (_BOFA_ACH.format(payer="NORTHWIND HOMES LLC", entry="DRAW 3"), "counted_flagged", "construction_progress_draw"),
    (_BOFA_WIRE.format(purpose="DRAW 4 PROGRESS PAYMENT"), "counted_flagged", "construction_progress_draw"),
    (_BOFA_WIRE.format(purpose="PROGRESS PAYMENT 4"), "counted_flagged", "wire_named_sender"),
    (_BOFA_ACH.format(payer="RITCHIE BROS", entry="SELLER PMT"), "non_revenue", "asset_sale_proceeds"),
)


def _section_15_record(text: str):
    return transaction_classifier.classify_statement_transactions(Statement(
        account_name=SECTION_15_HOLDER, bank="Bank of America", transactions=[
            Transaction(date="2054-03-02", description=text, amount=12000.0, direction="credit"),
            Transaction(date="2054-03-03", description="MOBILE DEPOSIT", amount=300.0, direction="credit"),
        ],
    ))[0]


@pytest.mark.parametrize(("text", "tier", "reason"), SECTION_15_ROWS)
def test_the_section_15_rows_read_as_spec_17_1_says(text, tier, reason):
    record = _section_15_record(text)
    assert (record.revenue_tier, record.revenue_tier_reason) == (tier, reason)


def test_the_spec_section_17_1_closes_the_draw_and_seller_payout_question():
    """The owner's ruling of 2026-10-02 (the underwriter's Q11, R2-OW06): §17.1's I18 and I45 question is closed, and
    its follow-ups (a developer's draw, the asset-sale defaults) are asked."""
    open_items = _section(SPEC.read_text(encoding="utf-8"), "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    line = next(line for line in open_items.splitlines() if line.startswith("- **I18 (`DRAW`) and I45"))
    assert "Closed 2026-10-02 by the owner (Q11; §19.1, §20)" in line
    assert "a builder's `DRAW` stays held" not in line and "stay counted and flagged" not in line
    assert "- **A project owner or developer that is no builder paying a stage draw" in open_items
    assert "- **Asset sales' follow-ups (the underwriter's Q11 (b) of 2026-10-02, §8.1).**" in open_items


def test_the_spec_and_the_contract_state_the_q11_ruling():
    """Owner ruling 2026-10-02, R2-OW06 (the underwriter's Q11): §2.1 carries the row, §5.3 the two codes, §6.2 pass
    7's asset-sale reading, §8.1 the two rules, §8.10 the tier and the override, §15 the two deferred items as ruled;
    the contract states both rules and the batch."""
    text = SPEC.read_text(encoding="utf-8")
    assert "| Q11 (2026-10-02) |" in _section(text, "\n## 2. Owner rulings (2026-09-28)", "\n## 3. ")
    codes = _section(text, "\n### 5.3 ", "\n### 5.4 ")
    assert "| `counted_flagged` | `construction_progress_draw` | Builder's progress draw |" in codes
    assert "| `non_revenue` | `asset_sale_proceeds` | Sale of equipment or vehicles (not a dealer) |" in codes
    assert "then the asset-sale reading (Q11 (2026-10-02) (b)" in _section(text, "\n### 6.2 ", "\n### 6.3 ")
    holds = _section(text, "\n### 8.1 ", "\n### 8.2 ")
    assert "**`construction_progress_draw`** (owner ruling 2026-10-02, the underwriter's Q11 (a)" in holds
    assert "**Asset-sale proceeds** (owner ruling 2026-10-02, the underwriter's Q11 (b)" in holds
    assert "**Dealer evidence**" in holds
    tiering = _section(text, "\n### 8.10 ", "\n## 9. ")
    assert "then a builder's progress draw (`construction_progress_draw`, Q11 (a) of 2026-10-02" in tiering
    assert "becomes `non_revenue` / `asset_sale_proceeds`" in tiering
    deferred = _section(text, "\n## 15. ", "\n## 16. ")
    assert "the draws ruled 2026-10-02 (the underwriter's Q11 (a)" in deferred
    assert "Ruled 2026-10-02 (the underwriter's Q11 (b), §8.1)" in deferred
    contract = _flat(CONTRACT)
    for words in ("A builder's progress draw is counted and flagged as `construction_progress_draw`",
                  "A non-dealer's sale of equipment or vehicles is `non_revenue` (`asset_sale_proceeds`)",
                  "Owner ruling 2026-10-02, R2-OW06"):
        assert words in contract, words


def test_the_spec_and_the_contract_state_the_q11_review_round():
    """R2-OW06 review round 1: §8.1 states the realty and commission-draw vetoes, the descriptor-verified draw's
    demotion, the repeat partner, FLEET, the commission or fee next to a sale and IAA's later hold; §8.10 the new
    demotion; §20 the round; the contract notes it."""
    text = SPEC.read_text(encoding="utf-8")
    holds = _section(text, "\n### 8.1 ", "\n### 8.2 ")
    for words in ("`construction_progress_draw_never_verified`", "`q5_q6_q11_repeat_partner`", "`payer_key_digest`",
                  "`<NAME> HOMES REALTY LLC`", "`COMMISSIONS DRAW`", "`FLEET` alone is none",
                  "`COMMISSION ON TRUCK SALE`", "`TRUCK SALE NET OF FEES`", "`CreditFacts.hold_past_insurer_name`"):
        assert words in holds, words
    tiering = _section(text, "\n### 8.10 ", "\n## 9. ")
    assert "and a builder's progress draw that an earlier rule verified (Q11 (a) of 2026-10-02" in tiering
    assert "**Owner ruling 2026-10-02, R2-OW06 review round 1**" in text[text.index("\n## 20. "):]
    assert "Owner ruling 2026-10-02, R2-OW06 review round 1" in _flat(CONTRACT)


def test_the_spec_records_the_card_push_switches_as_kept_off():
    """The underwriter's Q13 (2026-10-02, spec §19.1): both card-push switches stay off, §6.3 says so, and §17.1 asks
    only about the push forms the question did not show."""
    text = SPEC.read_text(encoding="utf-8")
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ").splitlines()
    assert not any("Two switches that ship off" in line for line in open_items)
    assert any(line.startswith("- **Card pushes that print their rail**") for line in open_items)
    lines = text.splitlines()
    narrowing_9 = next(line for line in lines if line.startswith("9. a merchant processor's instant payout"))
    assert "the owner keeps off" in narrowing_9 and "§19.1" in narrowing_9
    narrowing_6 = next(line for line in lines if line.startswith("6. a card-credit row that prints a push-rail word"))
    assert "stays off" in narrowing_6 and "ships off" not in narrowing_6


def test_the_spec_closes_gov_class_e_with_the_owner_s_ruling():
    """The underwriter's Q12 (2026-10-02): §17.1's I40 question is closed, §6.1 carries step 3a and §2 the new
    rulings' table."""
    text = SPEC.read_text(encoding="utf-8")
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    assert "**I40 (GOV class E).**" not in open_items
    assert "**Wisconsin Shares card settlements**" in open_items
    precedence = _section(text, "\n### 6.1 One credit's decision", "\n### 6.2 ")
    assert "3a. **New (owner ruling 2026-10-02, Q12):**" in precedence
    rulings = _section(text, "\n## 2. Owner rulings (2026-09-28)", "\n## 3. ")
    assert "Owner rulings (2026-10-02, the underwriter's answers)" in rulings
    assert "| Q12 (2026-10-02) |" in rulings and "| Q13 (2026-10-02) |" in rulings


def test_the_spec_closes_i35_with_the_zelle_ruling_and_holds_q3b_for_the_owner():
    """The underwriter's Q3 and Q3b (2026-10-02, R2-OW02): §17.1's I35 question is answered, §2.1 carries both rows,
    §8.4 the Zelle policy and §8.10 its step 26, and §17.1 asks the owner about Q3b's held code."""
    text = SPEC.read_text(encoding="utf-8")
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    assert "**I35, round-sum repeats.**" not in open_items
    assert "Answered 2026-10-02 (§2.1, §19.1): I35, with round-2 R09" in open_items
    assert "**No-sender e-Transfers' round-sum repeats (the underwriter's Q3b of 2026-10-02" in open_items
    rulings = _section(text, "\n## 2. Owner rulings (2026-09-28)", "\n## 3. ")
    assert "| Q3 (2026-10-02) |" in rulings and "| Q3b (2026-10-02, round-2 R09) |" in rulings
    # The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): Q4's row, §8.4's lead and step 26 name it.
    assert ("Amended 2026-10-02 and 2026-10-06 (§2.1, §19.1): Zelle deposits follow the Settings choice \"Mark Zelle "
            "Payments as True Revenue\": Yes (the default) reads them as this row does; No makes them `non_revenue` "
            "(`zelle_excluded`).") in rulings
    assert ("- **Zelle (owner ruling 2026-10-02, the underwriter's Q3; a Settings choice since 2026-10-06):**"
            in _section(text, "\n### 8.4 ", "\n### 8.5 "))
    assert "26. Then, in the stored reading, after every step above and before the $1 floor, the Zelle policy" in _section(
        text, "\n### 8.10 ", "\n## 9. ")
    assert "| `non_revenue` | `zelle_excluded` | Zelle deposit (excluded by policy) |" in _section(
        text, "\n### 5.3 ", "\n### 5.4 ")


def test_the_spec_states_the_non_revenue_breakdown_and_the_zelle_confirm():
    """Owner ruling 2026-10-02, R2-OW03 (the underwriter's Q3 and the Q12 card's open point 2): §5.3 lists Q12's
    display reason and says which non_revenue rows carry a code, §9.1 and §9.2 the breakdown, §10.1 the True card's
    Zelle fact, §10.2 the Monthly detail, §10.7 the Zelle confirm and §10.8 the export rows; the contract follows."""
    text = SPEC.read_text(encoding="utf-8")
    codes = _section(text, "\n### 5.3 ", "\n### 5.4 ")
    assert "| `non_revenue` | `government_no_purpose` | Government payment, no purpose printed |" in codes
    assert "`NON_REVENUE_REASONS`" in codes and "every other `non_revenue` row carries none" in codes
    assert "`non_revenue_by_reason`" in _section(text, "\n### 9.1 ", "\n### 9.2 ")
    assert "`non_revenue_by_reason`" in _section(text, "\n### 9.2 ", "\n### 9.3 ")
    assert "Zelle deposits excluded:" in _section(text, "\n### 10.1 ", "\n### 10.2 ")
    assert "Zelle excluded" in _section(text, "\n### 10.2 ", "\n### 10.3 ")
    review = _section(text, "\n### 10.7 ", "\n### 10.8 ")
    assert "with one exception" in review and "a `zelle_excluded` row shows Confirm Revenue only" in review
    assert "`non_revenue.<code>.count`" in _section(text, "\n### 10.8 ", "\n## 11. ")
    contract = _flat(CONTRACT)
    for words in ("`non_revenue_by_reason`", "`REVIEWABLE_NON_REVENUE_REASONS`", "`government_no_purpose`",
                  "Owner ruling 2026-10-02, R2-OW03"):
        assert words in contract, words


def test_the_spec_closes_i17_with_the_lease_to_own_ruling():
    """Owner ruling 2026-10-02, R2-OW04 (the underwriter's Q8): §17.1's I17 question is closed and its follow-ups
    listed, §2.1 carries the row, §5.3 the two codes, §6.3 the twelfth narrowing, §8.9 the financiers and §8.10 the
    lump-sum step and its thresholds; the contract states the claim, the lump-sum step and the batch."""
    text = SPEC.read_text(encoding="utf-8")
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    assert "**I17, lease-to-own and patient financiers.**" not in open_items
    assert "I17 (the underwriter's Q8 of 2026-10-02" in open_items
    assert "**Lease-to-own and patient financiers' follow-ups (the underwriter's Q8 of 2026-10-02, §8.9).**" in open_items
    assert "| Q8 (2026-10-02) |" in _section(text, "\n## 2. Owner rulings (2026-09-28)", "\n## 3. ")
    codes = _section(text, "\n### 5.3 ", "\n### 5.4 ")
    assert "| `excluded_pending_review` | `customer_financing_lump_sum` |" in codes
    assert "| `counted_flagged` | `customer_financing_payout` |" in codes
    narrowings = _section(text, "\n### 6.3 ", "\n## 7. ")
    # R2-OW08 (the underwriter's Q2): narrowing 13 since; the count reads thirteen.
    assert "except through exactly these thirteen named narrowings" in narrowings
    assert "\n12. a lease-to-own financier's merchant funding printed with the strong LOAN word" in narrowings
    assert "`CUSTOMER_FINANCING_PAYERS`" in _section(text, "\n### 8.9 ", "\n### 8.10 ")
    tiering = _section(text, "\n### 8.10 ", "\n## 9. ")
    assert "a one-off lump sum among the `customer_financing_payout` rows" in tiering
    assert "| Customer-financing lump sum |" in tiering and "| Customer-financing series |" in tiering
    assert "19. `factoring_payout` (a credit the classifier reads as factoring)" in tiering
    contract = _flat(CONTRACT)
    for words in ("`CUSTOMER_FINANCING_PAYERS`", "`customer_financing_lump_sum`", "Owner ruling 2026-10-02, R2-OW04"):
        assert words in contract, words


def test_the_spec_records_that_an_auto_lender_s_payables_need_dealer_evidence():
    """Owner ruling 2026-10-02, R2-OW05 (the underwriter's Q9, part (c')): §5.3 carries the code, §8.7 the rule and its
    evidence, §8.10 the demotion's place, §14.3 G5's exemption and the declared demotion, and §17.1 says part (c') is in
    the code while the I16/I36(d) question waits for the rest; the contract states the rule and the batch."""
    text = SPEC.read_text(encoding="utf-8")
    codes = _section(text, "\n### 5.3 ", "\n### 5.4 ")
    assert "| `counted_flagged` | `lender_paid_for_services` | Lender paid for services |" in codes
    q7 = re.sub(r"\s+", " ", _section(text, "\n### 8.7 ", "\n### 8.8 "))
    assert ("A listed lender's credit read on a payables word alone (PAYABLES, TRADE PAY, ACCT FUND) verifies only on "
            "a statement with dealer evidence: a Q7 credit with a dealer-specific word, or the credit-union arm; a "
            "floor-plan financier's row, or FLOOR PLAN; a purchase at a dealer-only auction; a dealer word in the "
            "holder's name, unless the name also prints RECOVERY, REPO, REPOSSESS, TOWING or COLLATERAL. Otherwise it "
            "is `counted_flagged` / `lender_paid_for_services` (Q9 (2026-10-02)), held under the hidden-loan guard."
            ) in q7
    for words in ("`_dealer_contract_evidence`", "`_payer_collects`", "`q7_payables_without_dealer_evidence`",
                  "a documented over-hold"):
        assert words in q7, words
    tiering = _section(text, "\n### 8.10 ", "\n## 9. ")
    assert "a listed auto lender's payables-only credit on a statement with no dealer evidence" in tiering
    guards = re.sub(r"\s+", " ", _section(text, "\n### 14.3 ", "\n### 14.4 "))
    assert "the pass counts as `lender_paid_for_services`" in guards
    assert "The census declares its demotion `q7_payables_without_dealer_evidence`" in guards
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    line = next(line for line in open_items.splitlines()
                if line.startswith("- **I16 and I36(d), financing words in a customer's name.**"))
    # R2-OW09 closes the line: part (c') since R2-OW05, the rest since R2-OW09.
    assert "Closed 2026-10-02 by the owner (Q9; §19.1)" in line and "part (c') since R2-OW05" in line
    contract = _flat(CONTRACT)
    for words in ("| `lender_paid_for_services` | `counted_flagged` | Lender paid for services |",
                  "A listed lender's credit read on a payables word alone", "Owner ruling 2026-10-02, R2-OW05"):
        assert words in contract, words


def test_the_spec_records_every_insurer_spelling_apart_from_the_q2_answer():
    """Audit I26 (R2-OW07; by Q6 of 2026-09-28, not asked in the underwriter's Q2): §8.1 gives the reading, its arms
    and the brand table; §7.7 keeps the §15 deferred carriers on today's words; §17.1 asks the owner to confirm the hold
    and names the alternative; §20 records the batch; the contract notes it."""
    text = SPEC.read_text(encoding="utf-8")
    holds = re.sub(r"\s+", " ", _section(text, "\n### 8.1 ", "\n### 8.2 "))
    for words in ("`insurer_payer_reading`", "without the holder's own names", "`_INSURER_SPELLINGS`",
                  "`INSURER_CREDIT_BRANDS`", "`LOSS PMT`", "`SUBRO…`", "`P AND C`", "`MUTUA`", "the `INS` abbreviation",
                  "`ASSURED`", "`CLM`", "`q5_q6_held_insurer`", "not as `payroll_or_salary`",
                  "the Q2 question did not ask it"):
        assert words in holds, words
    healthcare = re.sub(r"\s+", " ", _section(text, "\n### 7.7 ", "\n### 7.8 "))
    assert ("the Canadian benefit carriers and the other §15 deferred payers are read as insurers only by §8.1's "
            "spelled-out words and `CLAIM`") in healthcare
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    line = next(line for line in open_items.splitlines()
                if line.startswith("- **Every insurer spelling (audit I26, R2-OW07), for the owner to confirm.**"))
    for words in ("Default in the code: hold", "Alternative:", "only for the Q2 release", "Q6 of 2026-09-28"):
        assert words in line, words
    i27 = next(line for line in open_items.splitlines() if line.startswith("- **I27 (with I26)"))
    assert "Its spelling half, I26, is in the code" in i27
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    assert "owner ruling 2026-10-02, R2-OW07" in amendments
    assert "**Audit I26, R2-OW07 in all**" in amendments
    assert "Owner ruling 2026-10-02, R2-OW07 (audit I26" in _flat(CONTRACT)


def test_the_spec_and_the_contract_state_the_insurer_spelling_review_round():
    """R2-OW07 review round 1: §8.1 states the government payer's arm (the spelled-out words or CLAIM, never for
    work), the person-to-person rail's reading, the namesakes the patterns no longer read and the over-holds they keep,
    the asset-sale precedence and the rows the holder strip counts; §20 records the round; the contract's When cell
    and its note follow."""
    text = SPEC.read_text(encoding="utf-8")
    holds = re.sub(r"\s+", " ", _section(text, "\n### 8.1 ", "\n### 8.2 "))
    for words in ("a government payer (§7.6) is an insurer only by the spelled-out words above or `CLAIM`",
                  "never for work", "never the given name `SUBROTO`", "`FARMERS INSTITUTE`",
                  "`TRAVELERS PROPERTY MANAGEMENT`", "On a person-to-person rail only the spelled-out words and `CLAIM`",
                  "Accepted over-holds, held and reviewable", "`SAFECO DES:VEHICLE SALE`",
                  "is counted where no later hold of §8.10 names it"):
        assert words in holds, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    assert "**Audit I26, R2-OW07 review round 1**" in amendments
    assert "a government payer is one only by `_INSURER_NAME` or `CLAIM`" in amendments
    when = {cells[0]: cells[3] for cells in _reason_table()}["`insurer_named_payer`"]
    assert "a government payer only by those words or `CLAIM`" in when and "person-to-person rail" in when
    assert "Audit I26, R2-OW07 review round 1" in _flat(CONTRACT)


def test_the_spec_and_the_contract_state_the_q2_ruling():
    """Owner ruling 2026-10-02 (the underwriter's Q2), R2-OW08: §2 amends Q6 below its table and §2.1 adds the row;
    §5.3 the reason; §6.3 narrowing 13; §7.7 the deferred carriers; §8.1 the release's paragraph; §8.6 the exception;
    §8.10 the tier and the threshold; §14.3 G1; §17.1 closes I27 and lists the defaults; §20 records the ruling and
    the batch in all; the contract's note."""
    text = SPEC.read_text(encoding="utf-8")
    rulings = re.sub(r"\s+", " ", _section(text, "\n## 2. Owner rulings (2026-09-28)", "\n## 3. "))
    for words in ("Amended 2026-10-02 (§19.1): for an insurer paying the business for its work, Q6's \"insurers "
                  "never count\" gives way to the underwriter's Q2 (2026-10-02)", "| Q2 (2026-10-02) |",
                  "`INSURER_FOR_WORK_STATEMENT_ARM`, off"):
        assert words in rulings, words
    assert "| `counted_flagged` | `insurer_paid_for_services` | Insurer paid for the business's work |" in _section(
        text, "\n### 5.3 ", "\n### 5.4 ")
    narrowings = _section(text, "\n### 6.3 ", "\n## 7. ")
    assert "\n13. a listed insurer's credit (§6.1 step 5's `insurance_provider_credit_exclusion`)" in narrowings
    assert "`15_insurer_paid_for_services`" in narrowings
    assert "Owner ruling 2026-10-02 (the underwriter's Q2, R2-OW08)" in _section(text, "\n### 7.7 ", "\n### 7.8 ")
    holds = re.sub(r"\s+", " ", _section(text, "\n### 8.1 ", "\n### 8.2 "))
    for words in ("**Insurers paid for the business's work (Q2 (2026-10-02); `insurer_paid_for_services`, R2-OW08).**",
                  "never joins `_REGISTRY_METHODS` or any claimed set", "`holder_trade:<trade>`", "`service_form`",
                  "`same_insurer_3_in_31_days`", "`insurer_service_statement`", "never its `REF`",
                  "03-01 to 03-31 holds, 03-01 to 04-01 does not", "unless a commission form prints in the same words",
                  "The insurer's `CLAIM` on a released row is no non-sale word", "`CounterCredit.insurer` False",
                  "only a customer-payment row the for-work release refuses reaches it"):
        assert words in holds, words
    assert "except an insurer paying for the business's work" in _section(text, "\n### 8.6 ", "\n### 8.7 ")
    tiering = re.sub(r"\s+", " ", _section(text, "\n### 8.10 ", "\n## 9. "))
    assert "an insurer paid for the business's work (`insurer_paid_for_services`" in tiering
    assert "| Insurer for work | 3 or more eligible credits from one insurer key" in tiering
    assert "`15_insurer_paid_for_services`" in _section(text, "\n### 14.3 ", "\n### 14.4 ")
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    i27 = next(line for line in open_items.splitlines() if line.startswith("- **I27 (with I26)"))
    assert ("Closed 2026-10-02 (§19.1): counted and flagged on a trade, a service form or three in a month; the "
            "statement arm is an owner switch, OFF") in i27
    defaults = next(line for line in open_items.splitlines() if line.startswith(
        "- **Insurers paid for the business's work: the defaults (the underwriter's Q2 of 2026-10-02, §8.1; R2-OW08).**"))
    for words in ("`INSURER_FOR_WORK_STATEMENT_ARM`", "stays Excluded", "loose trade words", "Not confirmed"):
        assert words in defaults, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **Insurers paid for the business's work** (", "owner ruling 2026-10-02, R2-OW08",
                  "- **Owner ruling 2026-10-02, R2-OW08 in all** (", "c1acc3e"):
        assert words in amendments, words
    assert "Owner ruling 2026-10-02, R2-OW08 (the underwriter's Q2" in _flat(CONTRACT)


def test_the_spec_and_the_contract_state_the_q9_release():
    """Owner ruling 2026-10-02 (the underwriter's Q9 (a), (b), (c)), R2-OW09: §2.1 adds the Q9 row; §5.3 the two codes;
    §8.1 replaces the residuals' lead-in with the release (by place, the wording and the refusal, the bank-only payer,
    the label, the layout with no entry label, the payer-less row, the rent sense of LEASE and its memo, the lessor, the
    guard, the limits, the relabel) and keeps the residuals; §8.7 the registered-lender gap; §8.10 the relabel; §17.1
    closes I16 and I36(d) and asks the registered-lender question and the defaults; §20 records the ruling and the batch;
    the contract's rows, holds paragraph, decision bullet and note follow."""
    text = SPEC.read_text(encoding="utf-8")
    rulings = re.sub(r"\s+", " ", _section(text, "\n### 2.1 ", "\n## 3. "))
    for words in ("| Q9 (2026-10-02) | Finance-named customers, rent received, lenders paying for services",
                  "`finance_named_customer`", "`lessor_rent`", "the orchestrator's extension under Q10 (2026-10-02)",
                  "a documented over-hold"):
        assert words in rulings, words
    codes = _section(text, "\n### 5.3 ", "\n### 5.4 ")
    for row in ("| `counted_flagged` | `finance_named_customer` | Customer with a finance word in its name, paying an "
                "invoice |", "| `counted_flagged` | `lessor_rent` | Rent received by a leasing or property business |"):
        assert row in codes, row
    holds = re.sub(r"\s+", " ", _section(text, "\n### 8.1 ", "\n### 8.2 "))
    for words in ("**The Q9 release (owner ruling 2026-10-02, the underwriter's Q9", "`finance_named_release`",
                  "`_financing_root_places`", "`PROCEEDS`", "`_bank_only_payer`", "`_LENDER_NAME_WORD`",
                  "`ADVANCE AUTO PARTS`", "`_labelless_root_refusal`",
                  "A single root such a layout prints cannot tell a name from a purpose and is read as the name",
                  "so (a) and (c) never release it", "`_RENT_LEASE`", "`LEASE HOLDINGS LLC`", "`_lessor_business`",
                  "a payer-less transfer, person-to-person or wire row is never a rent payer", "`_payer_collects`",
                  "a documented over-hold", "`_Q9_KEEPS`", "Recorded residuals of the roots (audit I16), kept:",
                  "`<ADDRESS> OWNER SPE LLC`", "`FORWARDFINUSA<n><letter>`"):
        assert words in holds, words
    assert "**Q9's other parts (R2-OW09).**" in _section(text, "\n### 8.7 ", "\n### 8.8 ")
    assert "The Q9 relabel (owner ruling 2026-10-02, the underwriter's Q9; §8.1; R2-OW09)" in _section(
        text, "\n### 8.10 ", "\n## 9. ")
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    for lead, words in (
        ("- **Q9 (c) and registered lenders (the underwriter's Q9 of 2026-10-02, §8.1, §8.7; R2-OW09).**",
         ("`GM FINANCIAL DES:VENDOR PMT`", "a G7 move", "0 such rows", "Default: unchanged")),
        ("- **Finance-named customers, rent and lenders' service payments: the defaults (the underwriter's Q9 of "
         "2026-10-02, §8.1; R2-OW09).**", ("A single tenant's recurring `LEASE` rent stays held", "$42,820.25",
                                            "`COMMISSION(S)`", "per line", "a documented over-hold")),
    ):
        line = next(line for line in open_items.splitlines() if line.startswith(lead))
        for word in words:
            assert word in line, (lead, word)
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **Finance-named customers, rent received and lenders paying for services** (",
                  "owner ruling 2026-10-02, R2-OW09", "- **Owner ruling 2026-10-02, R2-OW09 in all** (", "78b066c"):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    for words in ("| `finance_named_customer` | `counted_flagged` | Customer with a finance word in its name, paying an "
                  "invoice |", "| `lessor_rent` | `counted_flagged` | Rent received by a leasing or property business |",
                  "The underwriter's Q9 (owner ruling 2026-10-02, \"Keep them as true revenue\"; R2-OW09) lifts the "
                  "financing-named hold's root arm alone", "T4's financing root no longer holds three kinds of row",
                  "Owner ruling 2026-10-02, R2-OW09 (the underwriter's Q9"):
        assert words in contract, words


def test_the_spec_and_the_contract_state_the_account_title():
    """Owner ruling 2026-10-02 (the underwriter's Q10, its parser half), R2-OW10: §9.1 states `statement.account_title`
    (the title the bank prints after the holder's name, from the holder reader's own anchor, serialized only when set,
    outside the extraction schema); §20 records the readers, the gate's export reader and the batch; the contract's
    note follows. No tier reads the title yet (R2-OW11)."""
    text = SPEC.read_text(encoding="utf-8")
    contract_section = re.sub(r"\s+", " ", _section(text, "\n### 9.1 ", "\n### 9.2 "))
    for words in ("`statement.account_title`", "the title the bank prints after the holder's name",
                  "from the holder reader's own anchor", "serialized only where it is set",
                  "not part of the extraction response schema", "R2-OW10"):
        assert words in contract_section, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **The holder readers publish the account title they drop** (",
                  "owner ruling 2026-10-02, R2-OW10", "`HolderReading`", "`_split_designation`", "`ATTN`",
                  "- **The corpus gate reads the analysis export beside its ledgers** (",
                  "- **Owner ruling 2026-10-02, R2-OW10 in all** ("):
        assert words in amendments, words
    assert "Owner ruling 2026-10-02, R2-OW10 (the underwriter's Q10, its parser half" in _flat(CONTRACT)


def test_the_spec_and_the_contract_state_the_premium_trust_hold():
    """Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: §2.1 adds the Q10 row; §5.3 the held code at the end of
    its group; §8.10 the step after the $1 floor and the title rule's forms; §9.1 the metric and the title's reader; §9.2
    the package keys; §10.1 the two facts; §14.3 G20; §15 closes the Applied Systems item for premium trust accounts;
    §17.1 closes I39 and asks the owner about the non-revenue default; §20 records the ruling and the batch; the
    contract's reason row, holds sentence, review decision and note follow."""
    text = SPEC.read_text(encoding="utf-8")
    rulings = re.sub(r"\s+", " ", _section(text, "\n### 2.1 ", "\n## 3. "))
    for words in ("| Q10 (2026-10-02) | An insurance agency's premium trust account", "`premium_trust_account`",
                  "A deposit a non-revenue rule excludes stays excluded", "the underwriter's Q2 (2026-10-02)"):
        assert words in rulings, words
    codes = _section(text, "\n### 5.3 ", "\n### 5.4 ")
    row = "| `excluded_pending_review` | `premium_trust_account` | Deposit into a premium trust account | owner 2026-10-02 (Q10, I39) |"
    assert row in codes
    assert codes.index("`p2p_round_repeat`") < codes.index(row) < codes.index("`wire_named_sender`")
    tiering = re.sub(r"\s+", " ", _section(text, "\n### 8.10 ", "\n## 9. "))
    for words in ("Then, after the $1 floor, the premium-trust hold", "`premium_trust_title` over `Statement.account_title`",
                  "the title at the field's end, the title followed by an account word, or the title and an account or "
                  "product word followed by a separator", "A held one keeps its first hold, and a non-revenue one stays "
                  "non-revenue", "`PREMIUM TRUST ROOFING`", "`PREM. TR. ACCT.`", "held for the title, not for being cash"):
        assert words in tiering, words
    metrics = re.sub(r"\s+", " ", _section(text, "\n### 9.1 ", "\n### 9.2 "))
    assert "`premium_trust_account`, true when the statement's printed title reads PREMIUM TRUST" in metrics
    assert "its one reader is the premium-trust rule" in metrics
    assert "`premium_trust_documents`" in _section(text, "\n### 9.2 ", "\n### 9.3 ")
    cards = re.sub(r"\s+", " ", _section(text, "\n### 10.1 ", "\n### 10.2 "))
    for words in ("Premium trust account: deposits that would count are held (insureds' premiums, not revenue); "
                  "non-revenue deposits stay excluded", "N statement(s) of a premium trust account: deposits that would "
                  "count are held"):
        assert words in cards, words
    assert "- **G20** (owner ruling 2026-10-02, the underwriter's Q10; R2-OW11)" in _section(text, "\n### 14.3 ",
                                                                                         "\n### 14.4 ")
    deferred = re.sub(r"\s+", " ", _section(text, "\n## 15. ", "\n## 16. "))
    assert "Applied Systems' agency-bill premium: closed for premium trust accounts" in deferred
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    assert "- **I39 (with I24, I38), a premium-trust account: closed 2026-10-02** (§19.1, Q10)." in open_items
    line = next(line for line in open_items.splitlines()
                if line.startswith("- **Premium trust accounts: the defaults (the underwriter's Q10 of 2026-10-02"))
    for words in ("Hold every deposit", "stays Excluded rather than Held", "premium-finance", "first hold", "Confirm"):
        assert words in line, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **A premium trust account's deposits are held** (", "owner ruling 2026-10-02, R2-OW11",
                  "- **Owner ruling 2026-10-02, R2-OW11 in all** (", "1158b09"):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    for words in ("| `premium_trust_account` | `excluded_pending_review` | Deposit into a premium trust account | the "
                  "account's printed title reads PREMIUM TRUST (statement account title, account name or holder name)",
                  "Last, on a statement whose account title reads PREMIUM TRUST, every verified or counted credit is held "
                  "as `premium_trust_account` (owner, 2026-10-02, Q10); a held credit keeps its first hold and a "
                  "non-revenue one stays non-revenue.",
                  "Owner ruling 2026-10-02 (Q10): a premium trust account's verified or counted deposits are held as "
                  "`premium_trust_account`", "Owner ruling 2026-10-02, R2-OW11 (the underwriter's Q10"):
        assert words in contract, words


#: R2-OW12's code commit, which §20 and the contract's note name.
R2_OW12_CODE_COMMIT = "d9878f0"


def test_the_spec_and_the_contract_state_the_funding_aid():
    """Owner ruling 2026-10-02 (the underwriter's Q1, audit I12), R2-OW12: §2's Q5 row is amended and §2.1 adds the Q1
    row; §5.4 names the record field; §6.2 item 7 the pass's last step; §8.5 the rule; §9.1 the row field; §10.7 the
    aid's lines; §17.1 closes I12 and lists its defaults; §20 records the rule and the batch; the contract's pass-7
    clause, holds paragraph, reason row, review decision and note follow, and its statement-pass sentence is unchanged
    (the aid is a step of pass 7, not a pass)."""
    text = SPEC.read_text(encoding="utf-8")
    rulings = re.sub(r"\s+", " ", _section(text, "\n## 2. ", "\n## 3. "))
    for words in ("Amended 2026-10-02 (§19.1, I12): the hold stays; a held wire with no sender carries the funding aid "
                  "of §8.5 in its review item", "| Q1 (2026-10-02) | Incoming wires with no sender printed",
                  "Recurring payments start after this deposit: possible funding.", "It never changes the tier"):
        assert words in rulings, words
    assert ("`revenue_funding_series`, the record's last field, a tuple of `FundingSeries`"
            in _section(text, "\n### 5.4 ", "\n## 6. "))
    assert ("last, after the $1 floor and the premium-trust step, the funding aid on held no-sender wires"
            in _section(text, "\n### 6.2 ", "\n### 6.3 "))
    wires = re.sub(r"\s+", " ", _section(text, "\n### 8.5 ", "\n### 8.6 "))
    for words in ("`funding_series_after`", "`FUNDING_SERIES_WINDOW_DAYS`", "`FUNDING_SERIES_MIN_PAYMENTS = 2`",
                  "`FUNDING_SERIES_MIN_LOOKBACK_DAYS`", "A registry lender's series needs two payments in the "
                  "statement; an unknown payee is in the pool only once three fixed daily or weekly debits promote it",
                  "The aid never changes a tier, a reason, a figure or a lender row (G7: 0)."):
        assert words in wires, words
    assert "and `revenue_funding_series` (§5.4)" in _section(text, "\n### 9.1 ", "\n### 9.2 ")
    review = re.sub(r"\s+", " ", _section(text, "\n### 10.7 ", "\n### 10.8 "))
    for words in ("**The funding aid**", "Recurring payments follow this deposit: possible funding.",
                  "the statement begins too close to this deposit to show whether they ran before it",
                  "A decided row shows no aid"):
        assert words in review, words
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    assert ("- **I12, wires with no sender.** Closed 2026-10-02 (§19.1): every no-sender wire stays held; its review "
            "item carries the funding aid") in open_items
    line = next(line for line in open_items.splitlines()
                if line.startswith("- **Wires with no sender: the funding aid's defaults (the underwriter's Q1 of "
                                   "2026-10-02"))
    for words in ("caveat", "per statement", "no-sender wires only", "Alternative"):
        assert words in line, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **The funding aid on held no-sender wires** (", "owner ruling 2026-10-02, R2-OW12",
                  "- **Owner ruling 2026-10-02, R2-OW12 in all** (", R2_OW12_CODE_COMMIT):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    for words in ("which tiers every posted credit, then the funding aid, before duplicate finalisation",
                  "carries the record field `revenue_funding_series`",
                  "Owner ruling 2026-10-02 (Q1): every wire with no sender printed stays held as `wire_no_sender`",
                  f"Owner ruling 2026-10-02, R2-OW12 (the underwriter's Q1, \"Held for review\"; {R2_OW12_CODE_COMMIT})"):
        assert words in contract, words
    # The aid adds no pass; R2-OW13 (the underwriter's Q5) added pass 7b after it.
    assert ("Statement passes run in this order: duplicates (proven by a repeated printed running balance); recurrence "
            "(D6 and the financing-keyword groups, debits only); the labels for unnamed potential payees; reversal "
            "pairs; operating-source context (pass 5, with its auction and property-management branches); the "
            "accounts-payable counter-debit guard (pass 6); the true-revenue pass (pass 7), which tiers every posted "
            "credit; the returned funder payments (pass 7b, the lender side only); the re-presented returned payments "
            "(pass 7c, the lender side only); duplicate finalisation.") in contract


#: R2-OW13's code commit, which §20 and the contract's note name.
R2_OW13_CODE_COMMIT = "2d81484"


def test_the_spec_and_the_contract_state_the_returned_funder_payments():
    """Owner ruling 2026-10-02 (the underwriter's Q5, audit I29), R2-OW13: §2.1 adds the Q5 row; §6.2 names the named
    pairs' restore (pass 4) and pass 7b; §9.1 and §9.2 the keys; §10.1 and §10.6 the dashboard; §11 the numerator; §14.3
    G7's declared categories; §17.1 closes I29, rewords I41's G7 bullet and lists the defaults; §19.1 the decision; §20
    amends the I6 line and records the rule (with why it runs after pass 7) and the batch (with the reversal-only
    sub-count); the contract's note, reversal paragraph, flag-clearing sentence, metric definitions and withholding
    formula follow, and its statement-pass sentence and lead paragraph name pass 7b; the README names the numerator."""
    text = SPEC.read_text(encoding="utf-8")
    rulings = re.sub(r"\s+", " ", _section(text, "\n### 2.1 ", "\n## 3. "))
    for words in ("| Q5 (2026-10-02) | Bounced payments to funders and the withholding rate (audit I29)",
                  "the dashboard warns, naming the funder", "Revenue does not move"):
        assert words in rulings, words
    passes = _section(text, "\n### 6.2 ", "\n### 6.3 ")
    for words in ("a lender-side pair whose debit is a confirmed funder's paid payment keeps that debit's lender count "
                  "and withholding", "Then pass 7b, the returned funder payments (rule D",
                  "it sets no `reversed_by` and moves no revenue field"):
        assert words in passes, words
    contract_keys = _section(text, "\n### 9.1 ", "\n### 9.3 ")
    for words in ("`returned_funder_payment_by`", "`returns_funder_payment`", "`returned_funder_payment_total`",
                  "`returned_funder_payments`", "`returned_payment_count`", "paid plus returned",
                  "abs(paid lender debits + returned funder payments) / withholding basis * 100"):
        assert words in contract_keys, words
    assert "Returned funder payment: <funder> <amount> debited <date>" in _section(text, "\n### 10.1 ", "\n### 10.2 ")
    assert "Returns the <date> payment to <funder>" in _section(text, "\n### 10.6 ", "\n### 10.7 ")
    assert "- **The numerator** (owner ruling 2026-10-02, the underwriter's Q5" in _section(text, "\n## 11. ", "\n## 12. ")
    guards = _section(text, "\n### 14.3 ", "\n### 14.4 ")
    for words in ("`returned_funder_moves`", "`kept_in_count_returned`", "every other withholding or `reversed_by` move"):
        assert words in guards, words
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    assert "- **I29, a bounced funder payment.** Closed 2026-10-02 (§19.1)" in open_items
    assert "(audit I41, tied to I29)" not in open_items
    line = next(line for line in open_items.splitlines()
                if line.startswith("- **Returned funder payments: the defaults (the underwriter's Q5 of 2026-10-02"))
    for words in ("potential (unconfirmed) lender", "sends nothing to review", "`REVERSE CORPORATE ACH DEBIT`",
                  "`possible_return`", "`RECEIVED ON`", "Alternative"):
        assert words in line, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("Amended 2026-10-02 (the underwriter's Q5; R2-OW13)", "- **Returned funder payments** (",
                  "Rule D runs after pass 7, not directly after pass 4 as the planning card placed it",
                  "- **Owner ruling 2026-10-02, R2-OW13 in all** (", "the reversal-only sub-count",
                  "`returned_funder_moves` 246 withholding rows", R2_OW13_CODE_COMMIT):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    for words in (f"Owner ruling 2026-10-02, R2-OW13 (the underwriter's Q5, \"Match the return to the funder payment it "
                  f"reverses\"; {R2_OW13_CODE_COMMIT})", "`RETURNED_FUNDER_PAYMENT_WINDOW_DAYS = 7`",
                  "the returned funder payment pass (above, R2-OW13)", "`returned_funder_payment_count` and `returned_funder_payment_total`",
                  "`withholding_rate = abs(paid lender debits + returned funder payments) / withholding basis * 100`"):
        assert words in contract, words
    assert "abs(total_qualifying_lender_debits)" not in contract
    assert ("Statement passes run in this order: duplicates (proven by a repeated printed running balance); recurrence "
            "(D6 and the financing-keyword groups, debits only); the labels for unnamed potential payees; reversal "
            "pairs; operating-source context (pass 5, with its auction and property-management branches); the "
            "accounts-payable counter-debit guard (pass 6); the true-revenue pass (pass 7), which tiers every posted "
            "credit; the returned funder payments (pass 7b, the lender side only); the re-presented returned payments "
            "(pass 7c, the lender side only); duplicate finalisation.") in contract
    for words in ("Between pass 7 and the duplicate finalisation the returned funder payments pass (pass 7b, R2-OW13) "
                  "and the re-presented returned payments pass (pass 7c, audit round 3, R3-B02: the owner's answer of "
                  "2026-10-07 to R3-73) read the lender side only.",
                  "settlement-reversed debits, a confirmed funder's payment returned unpaid (R2-OW13) and credits that "
                  "the reversal pass pairs clear it"):
        assert words in contract, words
    assert "funder payments returned unpaid (the owner's ruling of 2026-10-02, the underwriter's Q5)" in _flat(README)


#: The commit of the owner's ruling of 2026-10-02 on the underwriter's Q7 (R2-OW14): the code, the tests and the G7 pin.
R2_OW14_CODE_COMMIT = "0aeb015"


def test_the_spec_the_contract_and_the_readme_state_the_true_revenue_default_and_the_cash_arms():
    """Owner ruling 2026-10-02 (the underwriter's Q7, audit I34), R2-OW14: §2.1 adds the Q7 row; T8 is amended; §8.2
    adds the two cash arms (arm R flagged as inferred); §10.1 and §10.5 the Withholding Basis card and the copy; §11 the
    default, the selectable bases, the stored payload and G7's pin; §14.3 G7's pin; §17.1 closes I34 and lists the
    follow-ups; §19.1 the decision; §20 the ruling and the batch; the contract's withholding section and note, and the
    README, say True revenue is the default."""
    text = SPEC.read_text(encoding="utf-8")
    rulings = re.sub(r"\s+", " ", _section(text, "\n### 2.1 ", "\n## 3. "))
    for words in ("| Q7 (2026-10-02) | What the withholding rate is measured against (audit I34)",
                  "True revenue is the default withholding basis (`true_revenue`)",
                  "a payload stored with no mode keeps the legacy basis"):
        assert words in rulings, words
    decisions = _section(text, "\n## 4. ", "\n## 5. ")
    assert "Amended 2026-10-02 (the underwriter's Q7 (2026-10-02), §2.1, §19.1; R2-OW14): True revenue is the default" in (
        decisions)
    cash = _section(text, "\n### 8.2 ", "\n### 8.3 ")
    for words in ("- **Two cash shapes the reader missed**", "**Arm R, a retail cash load:**",
                  "Inferred from the shape", "**Arm S, a branch deposit printed with its transit:**",
                  "`_RETAIL_CASH_LOAD`", "`_BRANCH_DEPOSIT_TRANSIT`"):
        assert words in cash, words
    assert "- **The Withholding Basis card**" in _section(text, "\n### 10.1 ", "\n### 10.2 ")
    assert "Confirmed lender debits as a share of the withholding basis (True revenue by default)" in _section(
        text, "\n### 10.5 ", "\n### 10.6 ")
    withholding = _section(text, "\n## 11. ", "\n## 12. ")
    for words in ("- **Default: `true_revenue`** (owner ruling 2026-10-02, the underwriter's Q7",
                  "- **Selectable:** `legacy_eligible_deposits`", "- **A stored payload** whose metrics carry no mode",
                  "- **G7** (§14.3) pins the legacy basis"):
        assert words in withholding, words
    assert "Default unchanged" not in withholding
    assert "(the underwriter's Q7; R2-OW14): the snapshot computes its metrics on the legacy basis" in _section(
        text, "\n### 14.3 ", "\n### 14.4 ")
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    assert "- **I34, the withholding basis.** Closed 2026-10-02 (§19.1)" in open_items
    assert "Change the default?" not in open_items
    assert any(line.startswith("- **The withholding basis and cash deposits: the follow-ups (the underwriter's Q7 of "
                               "2026-10-02") for line in open_items.splitlines())
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **Owner ruling 2026-10-02, R2-OW14 in all** (", R2_OW14_CODE_COMMIT):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    section = _section(contract, "## Withholding rate", "## Extension rule")
    for words in ("The default mode is `true_revenue`", "stays selectable as `legacy_eligible_deposits`",
                  "A stored analysis whose metrics carry no mode was made on the legacy basis and keeps it",
                  "computes its snapshot on the legacy basis"):
        assert words in section, words
    assert "The default mode is explicitly exposed as `legacy_eligible_deposits`" not in contract
    assert "Neither is ever the default" not in contract
    assert f"Owner ruling 2026-10-02, R2-OW14 (the underwriter's Q7, \"2 Make True revenue the default\"; " \
           f"{R2_OW14_CODE_COMMIT})" in contract
    readme = _flat(README)
    assert "Withholding divides by True revenue (`WITHHOLDING_DENOMINATOR_MODE=true_revenue`" in readme
    assert "Withholding continues to use legacy eligible deposits" not in readme


#: The commit of the owner's ruling of 2026-10-02 on the underwriter's Q6 (R2-OW15): the code and the tests.
R2_OW15_CODE_COMMIT = "4125f30"


def test_the_spec_and_the_contract_state_the_package_passes():
    """Owner ruling 2026-10-02 (the underwriter's Q6, audit I42), R2-OW15: §2.1 adds the Q6 row; §6.2 the package
    passes (returned deposits across statements, the debit flags; R2-OW16's slot); §9.1 the served flags; §9.2 the
    overlay, the totals, the lists, the document rows and what does not move; §10.1, §10.6, §10.7 and §10.8 the
    dashboard, the notes, Confirm overriding the match and the downloads; §11 the two revenue modes; §14.1 the tests;
    §17.1 rules I42 and drops it from the unconfirmed rows; §19.1 the decision; §20 the rule and the batch; the
    contract's note and its withholding paragraph follow."""
    text = SPEC.read_text(encoding="utf-8")
    rulings = re.sub(r"\s+", " ", _section(text, "\n### 2.1 ", "\n## 3. "))
    for words in ("| Q6 (2026-10-02) | Bounced deposits from an earlier month, and chargebacks (audit I42) | \"2\"",
                  "the same account's immediately preceding statement", "`returned_deposit_cross_statement`",
                  "never deducted"):
        assert words in rulings, words
    passes = _section(text, "\n### 6.2 ", "\n### 6.3 ")
    for words in ("**Package passes** (`_package_matches` in `webapp/app.py`, after R-d",
                  "1. **Returned deposits across statements.**", "`PACKAGE_CONSECUTIVE_DAYS = 7`",
                  "2. **Own-account transfers** (the underwriter's Q4 (2026-10-02)", "3. **Debit flags** (`debit_side_flags`",
                  "a decided credit is never matched or annotated", "writes nothing back"):
        assert words in passes, words
    contract_keys = _section(text, "\n### 9.1 ", "\n### 9.3 ")
    for words in ("`unmatched_deposit_return_locations`", "`processor_chargeback_total`", "*The overlay.*",
                  "`returned_deposit_cross_statement_count`", "`package_match_unchecked_count`", "`package_matches`",
                  "`debit_flags`", "candidate_decided (a return whose nearest deposit the analyst confirmed",
                  "`package_match_count`", "*Unchanged:* R-d", "never `account`, which the served payload masks"):
        assert words in contract_keys, words
    cards = _section(text, "\n### 10.1 ", "\n### 10.2 ")
    for words in ("Returned deposits not matched: N · $X (not deducted)",
                  "Processor chargebacks and adjustments: N · $X (not deducted)",
                  "Matched across statements: M bounced deposit(s) taken out of True ($Y).",
                  "Not matched across statements: Q statement(s) analysed with older rules or with no currency."):
        assert words in cards, words
    assert "Returned on <date> (<file>): not counted. Confirm Revenue overrides the match." in _section(
        text, "\n### 10.6 ", "\n### 10.7 ")
    assert "- **A deposit the package took out of True**" in _section(text, "\n### 10.7 ", "\n### 10.8 ")
    assert "`package_match_<n>`" in _section(text, "\n### 10.8 ", "\n## 11. ")
    assert "- **Package matches in the True and Verified modes**" in _section(text, "\n## 11. ", "\n## 12. ")
    assert "- **§6.2's package passes, Q6 (2026-10-02)**" in _section(text, "\n### 14.1 ", "\n### 14.2 ")
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    assert "- **I42, returns with no equal deposit.** Ruled 2026-10-02 (§19.1)" in open_items
    assert "Should True net them?" not in open_items
    assert "I42's unmatched returns" not in open_items
    line = next(line for line in open_items.splitlines()
                if line.startswith("- **Returns across statements and chargebacks: the defaults (the underwriter's Q6 "
                                   "of 2026-10-02"))
    for words in ("immediately preceding statement", "nearest", "adjustments", "Alternative"):
        assert words in line, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **Returns across statements and chargebacks** (", "- **Owner ruling 2026-10-02, R2-OW15 in all** (",
                  R2_OW15_CODE_COMMIT):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    for words in (f"Owner ruling 2026-10-02, R2-OW15 (the underwriter's Q6, \"2\": \"Flag, but do not deduct, returns "
                  f"that cannot be matched and processor chargebacks\"; {R2_OW15_CODE_COMMIT})",
                  "`processor_chargeback_debit(text)`", "`debit_side_flags`", "`returned_deposit_cross_statement`",
                  "A deposit the package passes take out of True (the underwriter's Q6 (2026-10-02), R2-OW15) leaves "
                  "the revenue basis it was in"):
        assert words in contract, words


#: The commit of the owner's ruling of 2026-10-02 on the underwriter's Q4 (R2-OW16): the code and the tests.
R2_OW16_CODE_COMMIT = "3e6b2b6"


def test_the_spec_and_the_contract_state_the_transfers_between_the_business_s_accounts():
    """Owner ruling 2026-10-02 (the underwriter's Q4, audit I30), R2-OW16: §2.1 adds the Q4 row; §5.3 the held reason;
    §6.2 the package's pass 2 and the `no_account_number` marker; §8.2 the pointer and the paper-or-cash guard; §9.2 the
    overlay, the totals and the marker; §10.1, §10.6, §10.7 and §10.8 the notice, the notes, the release and the
    downloads; §11 the True-revenue basis; §14.1 the tests; §17.1 rules I30, lists its defaults and the account-number
    follow-up; §19.1 the decision; §20 the rule and the batch; the contract's note, reason row and withholding sentence
    follow."""
    text = SPEC.read_text(encoding="utf-8")
    rulings = re.sub(r"\s+", " ", _section(text, "\n### 2.1 ", "\n## 3. "))
    for words in ("| Q4 (2026-10-02) | Own-account transfers across separately uploaded statements (audit I30) | "
                  "\"Let's go with option 2 and I'll review it anyways\"", "`own_account_transfer_matched`",
                  "another account of the same document", "annotated only"):
        assert words in rulings, words
    assert ("| `excluded_pending_review` | `own_account_transfer_matched` | Matches a transfer out of another account in "
            "this package |") in _section(text, "\n### 5.3 ", "\n### 5.4 ")
    passes = _section(text, "\n### 6.2 ", "\n### 6.3 ")
    for words in ("2. **Own-account transfers** (the underwriter's Q4 (2026-10-02)", "`PACKAGE_TRANSFER_DAYS = 2`",
                  "`_different_accounts`", "there is no bank-name arm", "`paper_or_cash_deposit`",
                  "the destination veto", "**already-held** deposit", "is marked `no_account_number`",
                  "Pass 2 never marks a row internal"):
        assert words in passes, words
    assert "`paper_or_cash_deposit`" in _section(text, "\n### 8.2 ", "\n### 8.3 ")
    contract_keys = _section(text, "\n### 9.2 ", "\n### 9.3 ")
    for words in ("- **Owner ruling 2026-10-02 (the underwriter's Q4), R2-OW16", "`own_account_transfer_held_count`",
                  "`own_account_transfer_already_held_count`", "46 refused fields", "`no_account_number`"):
        assert words in contract_keys, words
    assert ("Transfers between accounts not checked for P statement(s): no account number read."
            in _section(text, "\n### 10.1 ", "\n### 10.2 "))
    assert ("Confirm Revenue releases it into True and marks it Verified; Mark Non-Revenue keeps it out."
            in _section(text, "\n### 10.6 ", "\n### 10.7 "))
    assert ("- **A deposit the package held as a transfer between the business's accounts**"
            in _section(text, "\n### 10.7 ", "\n### 10.8 "))
    assert "`own_account_transfer_already_held_count`" in _section(text, "\n### 10.8 ", "\n## 11. ")
    assert "R2-OW16" in _section(text, "\n## 11. ", "\n## 12. ")
    assert "- **§6.2's package passes, Q4 (2026-10-02)**" in _section(text, "\n### 14.1 ", "\n### 14.2 ")
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    assert "- **I30, transfers across a package.** Ruled 2026-10-02 (§19.1)" in open_items
    assert "Should a package pair transfers across its members?" not in open_items
    line = next(line for line in open_items.splitlines()
                if line.startswith("- **Transfers between the business's accounts: the defaults (the underwriter's Q4 "
                                   "of 2026-10-02"))
    for words in ("Confirm Revenue", "marks it Verified", "teller, counter or branch", "`payer_text_not_read`",
                  "Alternative"):
        assert words in line, words
    assert ("- **Read the printed account number on Chase, Capital One and Banque Royale statements**"
            in open_items)
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **Transfers between the business's accounts** (", "- **Owner ruling 2026-10-02, R2-OW16 in all** (",
                  R2_OW16_CODE_COMMIT):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    for words in (f"Owner ruling 2026-10-02, R2-OW16 (the underwriter's Q4, \"Let's go with option 2 and I'll review it "
                  f"anyways\"; {R2_OW16_CODE_COMMIT})",
                  "`paper_or_cash_deposit(text)`", "`own_account_transfer_matched`", "`_different_accounts`",
                  "A deposit the package holds as a transfer between the business's accounts (the underwriter's Q4 "
                  "(2026-10-02), R2-OW16) is such a moved credit"):
        assert words in contract, words


#: The owner's amendment of 2026-10-06 to the underwriter's Q3, R2-OW17: the code commit §20 and the contract name.
R2_OW17_CODE_COMMIT = "b98076d"


def test_the_spec_and_the_contract_state_the_zelle_setting():
    """The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): §2.1's Q3 row is amended; §5.3's source,
    §8.1's carve-outs, §8.4's two readings, §9.1's stored edits and served keys, §9.2's package figures, §9.3's note,
    §10's copy, review and exports, §11, §12, §13, §14.2's census, §14.3's G-Z and G7, §17.1's defaults and Q3b, and
    §20 record it; the contract and the README follow. Written as "the owner's amendment of 2026-10-06 to the
    underwriter's Q3" or "Q3 (amended 2026-10-06)", never a bare Q3."""
    text = SPEC.read_text(encoding="utf-8")
    rulings = re.sub(r"\s+", " ", _section(text, "\n### 2.1 ", "\n## 3. "))
    assert ("**Amended 2026-10-06 (R2-OW17):** a Settings choice, \"Mark Zelle Payments as True Revenue\", Yes by "
            "default.") in rulings
    assert "| owner 2026-10-02, Q3 (§8.4); the No reading since 2026-10-06 |" in _section(text, "\n### 5.3 ", "\n### 5.4 ")
    holds = _section(text, "\n### 8.1 ", "\n### 8.2 ")
    for words in ("Never a Zelle row in the No reading", "a Zelle row in the No reading",
                  "the skip is kept in both readings"):
        assert words in holds, words
    zelle = _section(text, "\n### 8.4 ", "\n### 8.5 ")
    for words in ("**Yes, the counted reading**", "**No, the stored reading:**", "`classify_statement_readings`",
                  "The lessor fact keeps its Zelle skip in both readings", "The latest decision on a Zelle row sets both"):
        assert words in zelle, words
    for section, end, words in (
        ("\n### 9.1 ", "\n### 9.2 ", ("`zelle_counted_reading`", "`REBUILT_KEYS`", "`metrics.zelle_deposits`",
                                      "`setting_applied`", "`zelle_deposit: true`", "**legacy**")),
        ("\n### 9.2 ", "\n### 9.3 ", ("R2-OW17", "`zelle_deposits`", "out part")),
        ("\n### 9.3 ", "\n## 10. ", ("R2-OW17", "no bump", "`zelle_counted_reading`")),
        ("\n### 10.1 ", "\n### 10.2 ", ("Zelle deposits in True revenue:", "counted after review",
                                        "analysed before the Zelle setting: shown as analysed")),
        ("\n### 10.2 ", "\n### 10.3 ", ("Zelle in True", "counted after review")),
        ("\n### 10.5 ", "\n### 10.6 ", ("Mark Zelle Payments as True Revenue", "Saved: Zelle deposits are non-revenue.")),
        ("\n### 10.6 ", "\n### 10.7 ", ("\"Zelle\" chip",)),
        ("\n### 10.7 ", "\n### 10.8 ", ("the latest decision on a posting sets every reading", "`with_both_readings`",
                                        "`_copy_rank`")),
        ("\n### 10.8 ", "\n## 11. ", ("`zelle_deposits.setting`", "trailing `zelle` column", "the closed list")),
        ("\n## 11. ", "\n## 12. ", ("R2-OW17", "zero or missing")),
        ("\n## 12. ", "\n## 13. ", ("Analyses stored before the Zelle setting", "**legacy**", "R2-B16")),
        ("\n## 13. ", "\n## 14. ", ("the Zelle choice (display; R2-OW17)", "`--zelle-true-revenue {yes,no}`",
                                    "`analysis/zelle_view.py`")),
        ("\n### 14.2 ", "\n### 14.3 ", ("--zelle-true-revenue {yes,no}", "`ZelleViewMismatch`",
                                        "`zelle_true_revenue_view`", "no §6.3 narrowing")),
        ("\n### 14.3 ", "\n### 14.4 ", ("**G-Z**", "`zelle_reading_rule_d`")),
    ):
        found = _section(text, section, end)
        for word in words:
            assert word in found, (section, word)
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    assert "- **The Zelle setting: the defaults (the owner's amendment of 2026-10-06 to the underwriter's Q3" in open_items
    assert "leaves Q3b as it is" in open_items
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **Zelle as True revenue is a Settings choice** (", "owner ruling 2026-10-06, R2-OW17",
                  "- **Owner ruling 2026-10-06, R2-OW17 in all** (", R2_OW17_CODE_COMMIT):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    for words in ("the Settings choice \"Mark Zelle Payments as True Revenue\"", "`classify_statement_readings`",
                  "`zelle_deposits`", "`zelle_counted_reading`", "the latest decision on a posting sets every reading",
                  f"Owner ruling 2026-10-06, R2-OW17 (the owner's amendment of 2026-10-06 to the underwriter's Q3; "
                  f"{R2_OW17_CODE_COMMIT})"):
        assert words in contract, words
    assert "`--zelle-true-revenue {yes,no}`" in _flat(README)


#: The owner's request of 2026-10-06 (lender payment changes), R2-OW18: the code commit §20 and the contract name.
R2_OW18_CODE_COMMIT = "551c90b"


def test_the_contract_s_labels_paragraph_names_the_payee_key_and_publishes_no_payee_word():
    """The owner's request of 2026-10-06 (R2-OW18): the D11 labels paragraph describes `potential_payee_key`, an
    amount-free digest that publishes no payee word and that only the lender payment changes read."""
    contract = _flat(CONTRACT)
    paragraph = contract[contract.index("The Potential Lenders tab lists each unnamed payee key on its own line"):]
    paragraph = paragraph[:paragraph.index("A higher-precedence non-lender match")]
    for words in ("`potential_payee_key`", "amount-free digest", "so no payee word is published",
                  "Only `analysis.lender_payment_changes` reads it"):
        assert words in paragraph, words


def test_the_spec_and_the_contract_state_the_lender_payment_changes():
    """The owner's request of 2026-10-06 (lender payment changes; R2-OW18): §2.2's row, §9.1's detection key and record
    field, §9.2's package keys, §9.3's CR2 note, §10.1's lines, §10.8's sections, §11, §12, §13's rows, §14.1's tests,
    §14.3's new G7 outputs, §17.1's defaults with the orchestrator's two choices, §19.1 and §20 record it; the contract,
    the README and the lender-detection spec follow. Written as "the owner's request of 2026-10-06", never with a Q."""
    text = SPEC.read_text(encoding="utf-8")
    requests = re.sub(r"\s+", " ", _section(text, "\n### 2.2 Owner requests (2026-10-06)", "\n## 3. "))
    assert "| Lender payment changes (2026-10-06) | \"can we also detect when a payment to lender has decreased?" in requests
    for words in ("\"Decreases, increases, stops\"", "\"Sustained, 10%+ drop\"", "\"Confirmed + potential\"",
                  "**Information only:**", "R2-OW18"):
        assert words in requests, words
    for section, end, words in (
        ("\n### 9.1 ", "\n### 9.2 ", ("`detection.lender_payment_changes`", "`potential_payee_key`",
                                      "`schedule_confirmed`", "`stop_confirmed`")),
        ("\n### 9.2 ", "\n### 9.3 ", ("`lender_payment_changes_unchecked`", "`continues_in_other_account`",
                                      "`cross_statement`", "Never summed")),
        ("\n### 9.3 ", "\n## 10. ", ("R2-OW18", "no bump", "`potential_payee_key`")),
        ("\n### 10.1 ", "\n### 10.2 ", ("Payment decreased: KAPITUS daily $850.00 → $600.00 (-29%)",
                                        "Payment changes not checked: this statement was analysed before the check.",
                                        "No payments", "new schedule not yet confirmed")),
        ("\n### 10.8 ", "\n## 11. ", ("`lender_payment_change_<n>`", "`lender_payment_unchecked_<n>`")),
        ("\n## 11. ", "\n## 12. ", ("payment changes never enter the numerator, the basis or the rate",)),
        ("\n## 12. ", "\n## 13. ", ("Analyses stored before the lender payment check", "not checked")),
        ("\n## 13. ", "\n## 14. ", ("`analysis/lender_payment_changes.py` (new, R2-OW18)",
                                    "G7; R2-OW13's returned categories; R2-OW18's payment-change outputs (new outputs "
                                    "only)")),
        ("\n### 14.1 ", "\n### 14.2 ", ("`tests/test_lender_payment_changes.py`",)),
        ("\n### 14.3 ", "\n### 14.4 ", ("**G7's new outputs**", "byte-identical")),
    ):
        found = _section(text, section, end)
        for word in words:
            assert word in found, (section, word)
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    assert "- **Lender payment changes: the defaults (the owner's request of 2026-10-06" in open_items
    for words in ("(18) THE ORCHESTRATOR'S CHOICE OF 2026-10-06", "(23) THE ORCHESTRATOR'S CHOICE OF 2026-10-06"):
        assert words in open_items, words
    assert "## 20. Implementation amendments (2026-09-29 to 2026-10-06)" in text
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **Lender payment changes** (", "owner ruling 2026-10-06, R2-OW18",
                  "- **Owner ruling 2026-10-06, R2-OW18 in all** (", R2_OW18_CODE_COMMIT):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    for words in (f"The owner's request of 2026-10-06 (lender payment changes; owner request 2026-10-06 (R2-OW18); "
                  f"{R2_OW18_CODE_COMMIT})", "`detection.lender_payment_changes`",
                  "payment changes never enter the numerator, the basis or the rate"):
        assert words in contract, words
    assert "R2-OW18" in _flat(README) and "lender_payment_changes.py" in _flat(README)
    lender = (ROOT / "docs" / "superpowers" / "specs" / "2026-09-24-lender-detection-design.md").read_text(
        encoding="utf-8")
    assert lender.count("*Amendment (owner request 2026-10-06, R2-OW18):*") == 7


#: R2-OW18 review round 1: the code commit §20 and the contract name.
R2_OW18_R1_CODE_COMMIT = "a4d9b7c"


def test_the_spec_and_the_contract_record_r2_ow18_review_round_1():
    """R2-OW18 review round 1: §9.1's new item fields, §10.1's step and attempt wording (never "steps of under 10%
    each"), §10.8's export fields, §17.1's points 18, 20, 23, 24 and 26 and the new point 29, the §20 line with its
    commit, and the contract's sentence."""
    text = SPEC.read_text(encoding="utf-8")
    for section, end, words in (
        ("\n### 9.1 ", "\n### 9.2 ", ("`last_step_percent`", "`first_after_kind`", "`resumed_date`",
                                      "`change_percent`, the step into it")),
        ("\n### 10.1 ", "\n### 10.2 ", ("via weekly $950.00 (-5%), then weekly $650.00 (-32%)",
                                        "never a claim about the steps' size", "no payment or payment attempt",
                                        "and payments resumed at the same")),
        ("\n### 10.8 ", "\n## 11. ", ("`first_after_kind`, `resumed_date` and `last_step_percent`",)),
    ):
        found = _section(text, section, end)
        for word in words:
            assert word in found, (section, word)
    assert "steps of under 10% each, a pause" not in _section(text, "\n### 10.1 ", "\n### 10.2 ")
    open_items = re.sub(r"\s+", " ", _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. "))
    for words in ("a possible change never becomes the reference of point 23",
                  "a line whose presence is a bounced attempt says so",
                  "never \"steps of under 10% each\"",
                  "a restart's pause, like a pause, leaves out the business days no statement of the chain covers",
                  "is no new stream, since it may have been paying before",
                  "(29) a known false shape (R2-OW18 review round 1)", "288 of 1,740 confirmed statement series",
                  # Audit round 3, R3-B05 adds point 30 (R3-84) and the catch-up to point 24 (R3-25).
                  "Points 18 to 30", "(30) a pause or a stop whose gap holds unclaimed debits",
                  "a one-off within 2% of exactly 2 to 6 times the reference amount, a catch-up"):
        assert words in open_items, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **Owner ruling 2026-10-06, R2-OW18 review round 1** (", R2_OW18_R1_CODE_COMMIT,
                  "459 items become 456", "3 confirmed package new streams leave"):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    for words in (f"R2-OW18 review round 1 ({R2_OW18_R1_CODE_COMMIT})", "`last_step_percent`", "`first_after_kind`",
                  "no payment or payment attempt"):
        assert words in contract, words


#: Audit round 3, R3-B05, review round 1: the code commit §20 and the contract name.
R3_B05_R1_CODE_COMMIT = "cc8524e"


def test_the_spec_and_the_contract_record_r3_b05_review_round_1():
    """Audit round 3, R3-B05, review round 1: §9.1's `catch_ups_inside`, §10.1's wording, §10.8's export field, §17.1
    (24)'s sentence and disclosed shapes, the §20 line with its commit, and the contract's bullet."""
    text = SPEC.read_text(encoding="utf-8")
    for section, end, words in (
        ("\n### 9.1 ", "\n### 9.2 ", ("`catch_ups_inside`",)),
        ("\n### 10.1 ", "\n### 10.2 ", ("on 2054-03-17 before payments resumed (possible catch-up)",)),
        ("\n### 10.8 ", "\n## 11. ", ("`catch_ups_inside` (\"2054-03-17 1700.0 2x; …\")",)),
    ):
        found = _section(text, section, end)
        for word in words:
            assert word in found, (section, word)
    open_items = re.sub(r"\s+", " ", _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. "))
    for words in ("R3-B05 review round 1 (findings 2, 3 and 5)", "a partial catch-up", "\"Partly caught up\"",
                  "a regime paid on the 1st and the 15th", "\"N debits of exact multiples after the last payment\""):
        assert words in open_items, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("audit round 3, R3-B05, review round 1 (findings 1 to 5)", R3_B05_R1_CODE_COMMIT):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    for words in (f"Audit round 3, R3-B05, review round 1 ({R3_B05_R1_CODE_COMMIT})", "`catch_ups_inside`"):
        assert words in contract, words


#: Audit round 3, R3-B06: the code commit §20 and the contract name.
R3_B06_CODE_COMMIT = "85a6d5f"


def test_the_spec_and_the_contract_record_r3_b06():
    """Audit round 3, R3-B06 (R3-81, R3-82, R3-83, R3-85): §9.1's new-stream and funding-note definitions, §9.2's
    reappearance note, §9.3's stored-output bullet, §10.1's anchored and reappearance wordings, §10.8's cells, §17.1
    points 11, 25 and 26, the §20 line with its commit, and the contract's bullet."""
    text = SPEC.read_text(encoding="utf-8")
    for section, end, words in (
        ("\n### 9.1 ", "\n### 9.2 ", ("at the level it was paying at the new stream's (P's) first payment",
                                      "one dated on or before the first payment of the regime just before the new "
                                      "one; audit round 3, R3-82")),
        ("\n### 9.2 ", "\n### 9.3 ", ("`reappears_in_other_account`", "`covered_business_days`",
                                      "a third account's statements never count")),
        ("\n### 9.3 ", "\n## 10. ", ("Audit round 3, R3-B06 (§20): no bump in a fix batch either",)),
        ("\n### 10.1 ", "\n### 10.2 ", ("28 business days after 2054-04-20 through 2054-05-29",
                                        "after 38 business days without one in the statements provided")),
        ("\n### 10.8 ", "\n## 11. ", ("`reappears_in_other_account.source_document`",)),
    ):
        found = _section(text, section, end)
        for word in words:
            assert word in found, (section, word)
    open_items = re.sub(r"\s+", " ", _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. "))
    for words in ("it never cites a credit that returns or reverses a payment",
                  "(audit round 3, R3-82: on the corpus 12 of 83 notes leave",
                  "within the stop's grace window (business days the two accounts' statements cover)",
                  "\"reappear in another account … after N business days without one\" (audit round 3, R3-83",
                  "(the other stream is named at the level it paid when the new stream began; audit round 3, R3-81"):
        assert words in open_items, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **Lender payment changes, lines and notes** (", "audit round 3, R3-B06", R3_B06_CODE_COMMIT):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    for words in (f"Audit round 3, R3-B06 (R3-81, R3-82, R3-83, R3-85; {R3_B06_CODE_COMMIT})",
                  "`reappears_in_other_account`", "reappear in another account"):
        assert words in contract, words


#: Audit round 3, R3-B07: the code commit §20 and the contract name.
R3_B07_CODE_COMMIT = "b9c558b"


def test_the_spec_and_the_contract_record_r3_b07():
    """Audit round 3, R3-B07 (R3-14, R3-40, R3-42, R3-18, R3-45, R3-46): §7.11's LN sentence, §8.1's advance payment and
    arm-S sentences, §8.5's bank words and no-sender words, §9.3's stored-output bullet, §17.1 point 3, one §20 line per
    issue and the batch line with the commit, the amended A3-G, R32, R11, B7 and R24 lines, and the contract's bullet."""
    text = SPEC.read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", text)
    for words in (
        "Audit round 3, R3-B07 (R3-46, §20; the owner's standing rule that loans never become revenue)",
        "the abbreviated forms `ADV PAYM`, `ADV PMT`, `ADV PYMT` and `ADVANCE PYMT` too, never after `MERCHANT`, "
        "`CASH` or `MCA`",
        "counts as that form only on Scotiabank's statements",
        "`BANK`, `BANKING`, `BANCO`, `BANCA`, `BANQUE`, `BANCAIRE`, `SPARKASSE`, `BANCORP`",
        "nor does a region of only label, holder-noise, account-designation, purpose, filler or legal-form words",
        "Audit round 3, R3-B07 (§20): no bump in a fix batch either",
        "(on another bank, arm S no longer lifts R35's funder-name guard: R3-45, audit round 3, R3-B07, §20",
        "the residual now names only the old labels with no `FROM`",
        "a relayed numbered company is a named customer",
    ):
        assert words in flat, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **A relaying bank that prints `BANKING` or a non-English bank word relays its customer",
                  "- **A wire region of designation words names no sender**",
                  "- **A sender printed straight after the new wire labels is read**",
                  "- **A wire's abbreviated advance payment is no financing**",
                  "- **Arm S keeps R35's funder guard off Scotiabank's statements**",
                  "- **A company named with `LN` is held for review, never unreviewable non-revenue**",
                  "- **Audit round 3, R3-B07 in all**"):
        assert words in amendments, words
    assert amendments.count("audit round 3, R3-B07 (R3-") >= 6
    assert amendments.count(R3_B07_CODE_COMMIT) >= 7
    contract = _flat(CONTRACT)
    for words in (f"Audit round 3, R3-B07 (R3-14, R3-40, R3-42, R3-18, R3-45, R3-46; {R3_B07_CODE_COMMIT})",
                  "Audit round 3, R3-B07 (R3-14): `BANKING` reads as a bank word",
                  "Audit round 3, R3-B07 (R3-42): and `INBOUND WIRE|FEDWIRE [TRANSFER FROM] <sender>`"):
        assert words in contract, words


#: Audit round 3, R3-B08: the code commit §20 and the contract name.
R3_B08_CODE_COMMIT = "3c62215"


def test_the_spec_and_the_contract_record_r3_b08():
    """Audit round 3, R3-B08 (R3-41, R3-88, R3-44, R3-31, R3-32, R3-92): §5.2's template-prefix and numbered-company
    sentences, §7.0's furniture sentence, §8.2's and §8.6's own-bank sentences, §9.3's stored-output bullet, §17.1's
    debit-readings sentence with the owner's question, one §20 line per issue and the batch line with the commit, the
    amended R31, R28, R33, R08 and R2-B03 lines, and the contract's bullet and registry sentence."""
    text = SPEC.read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", text)
    for words in (
        "audit round 3, R3-B08: R3-41, §20: or when the full template follows it",
        "Audit round 3, R3-B08 (R3-88, §20): BMO's two-word CPA code pairs",
        "Audit round 3, R3-B08 (R3-92, §20): the category rules read a credit without its furniture too",
        "Audit round 3, R3-B08 (R3-31, R3-32, §20): the own bank is read first, as a whole region",
        "Audit round 3, R3-B08 (R3-31, R3-32, §20): the statement's own bank is read first, as a whole region",
        "Audit round 3, R3-B08 (§20): no bump in a fix batch either",
        "Audit round 3, R3-B08 (R3-92, §7.0, §20; the owner's question, its default shipped)",
        "Default if unanswered: (b), shipped.",
        "(Corrected by audit round 3, R3-B08: R3-41, §20 below",
        "(Closed by audit round 3, R3-B08: R3-88, §20 below",
        "audit round 3, R3-B08: R3-88, §20 below: and BMO's two-word code pairs",
        "audit round 3, R3-B08: R3-44, §20 below: a lost accent inside `CHEQUE`",
        "audit round 3, R3-B08: R3-31, R3-32, §20 below: the own bank is read first",
        "audit round 3, R3-B08: R3-31, §20 below: nor the own bank's name alone",
    ):
        assert words in flat, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **American Express's full incoming-ACH template keeps its ACH reading whatever its originator's",
                  "- **A town's `DES` never opens the originator field, and BMO's code pairs keep a numbered company's",
                  "- **A lost French accent inside `CHEQUE` or after `RETOURN`, and four more French interest wordings",
                  "- **The statement's own bank is read first, as a whole region, by its full name and its printed",
                  "- **A credit's statement furniture never decides its category**",
                  "- **Audit round 3, R3-B08 in all**"):
        assert words in amendments, words
    assert amendments.count("audit round 3, R3-B08 (R3-") >= 5
    assert amendments.count(R3_B08_CODE_COMMIT) >= 6
    assert "PLACEHOLDER" not in amendments
    contract = _flat(CONTRACT)
    for words in (f"Audit round 3, R3-B08 (R3-41, R3-88, R3-44, R3-31, R3-32, R3-92; {R3_B08_CODE_COMMIT})",
                  "the own bank's sending spellings (`OWN_BANK_SENDING_SPELLINGS`)"):
        assert words in contract, words


#: Audit round 3, R3-B09: the code commit §20 and the contract name.
R3_B09_CODE_COMMIT = "5705367"


def test_the_spec_and_the_contract_record_r3_b09():
    """Audit round 3, R3-B09 (R3-36, R3-87, R3-91, R3-75): §8.1's possible-return arms, §8.2's, §8.5's and §10.7's
    unread-text sentences, §9.3's stored-output bullet, §14.2's, G9's and G18's row-count sentences, §17.1's I41 and
    B10 sentences, one §20 line per issue and the batch line with the commit, the amended B10, R2-B07 and R07 lines, and
    the contract's bullet and reason-table row."""
    text = SPEC.read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", text)
    for words in (
        "audit round 3, R3-B09 (R3-75, §20; standard D1, D3, A8;",
        "`(?<![A-Z])(?:ENVOI|CONTR|REDEPOT) (?:FRAIS )?VFC\\b`",
        "audit round 3, R3-B09: R3-87, §20: never after a class-code word followed by a legal form",
        "Audit round 3, R3-B09 (R3-91, R3-87, §20): the daily core-processor template keeps each marked credit's block",
        "Audit round 3, R3-B09 (R3-91, §8.2, §10.7, §20): a held wire whose reader kept a payer line",
        "- **A held wire or transfer whose payer line was not read** (audit round 3, R3-B09: R3-91",
        "\"Wire, payer line not read\"",
        "Audit round 3, R3-B09 (§20): no bump in a fix batch either",
        "(audit round 3, R3-B09: R3-36, §20) an account whose parse added or dropped a row",
        "(audit round 3, R3-B09: R3-36, §20) one whose row count changed without a parse change",
        "Audit round 3, R3-B09 (R3-36, §20): a parse change that adds or drops a row, credit or debit, is a G18",
        "audit round 3, R3-B09: R3-75, §20: and its e-Transfer family",
        "Audit round 3, R3-B09 (R3-91, §20): the daily core-processor template now keeps each marked credit's block",
        "(Amended by audit round 3, R3-B09: R3-91, §20 below: each marked credit now keeps its block",
        "(Amended by audit round 3, R3-B09: R3-91, §20 below: the daily template's credit sections",
        "(audit round 3, R3-B09: R3-87, §20 below: never after a class-code word followed by a legal form",
    ):
        assert words in flat, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **A parse change that adds or drops a row is a G18 parse move**",
                  "- **A class-code word followed by a legal form is part of a name**",
                  "- **The daily core-processor template, balance_by_date and B1 keep the payer line they do not read",
                  "- **A credit printing an outgoing e-Transfer label, or a French fee adjustment, is a possible",
                  "- **Audit round 3, R3-B09 in all**"):
        assert words in amendments, words
    assert amendments.count("audit round 3, R3-B09 (R3-") >= 4
    assert amendments.count(R3_B09_CODE_COMMIT) >= 5
    assert "PLACEHOLDER" not in amendments
    contract = _flat(CONTRACT)
    for words in (f"Audit round 3, R3-B09 (R3-36, R3-87, R3-91, R3-75; {R3_B09_CODE_COMMIT})",
                  "or (audit round 3, R3-B09) a credit printing an outgoing e-Transfer label or a French fee",
                  "debits keep none, and the daily template kept none until audit round 3, R3-B09"):
        assert words in contract, words


#: Audit round 3, R3-B09, review round 1: the code commit §20 and the contract name.
R3_B09_R1_CODE_COMMIT = "4776d05"


def test_the_spec_and_the_contract_record_r3_b09_review_round_1():
    """Audit round 3, R3-B09, review round 1 (findings 1 to 3): §8.1's and §8.2's narrowing sentences, the R3-87, R3-75
    and R07 lines marked in place, the R3-87 line's residual, the batch line's unreconciled-summary sentence, the §20
    line with its commit, and the contract's bullet."""
    text = SPEC.read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", text)
    for words in (
        "R3-B09 review round 1, §20: a form of the LLC family only, `LLC`, `L.L.C.`, `L L C`, `LLP` or `PLLC`",
        "R3-B09 review round 1: a form of the LLC family only)",
        "R3-B09 review round 1 (§20): the send and sent arms read only where no incoming wording",
    ):
        assert words in flat, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("(narrowed by R3-B09 review round 1, §20 below, to the LLC family:",
                  "Also not covered, since R3-B09 review round 1: a class-code word before a form outside the LLC",
                  "(narrowed by R3-B09 review round 1, §20 below: the send and sent labels only after no incoming",
                  "Beyond the reconciled accounts (added by R3-B09 review round 1, finding 3)",
                  "- **R3-B09 review round 1: only the LLC family makes a class-code word part of a name",
                  "audit round 3, R3-B09, review round 1 (findings 1 to 3)", R3_B09_R1_CODE_COMMIT):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    for words in (f"Audit round 3, R3-B09, review round 1 ({R3_B09_R1_CODE_COMMIT})",
                  "a class-code word is part of a name only before a legal form of the LLC family"):
        assert words in contract, words


#: Audit round 3, R3-B10: the code commit §20 and the contract name.
R3_B10_CODE_COMMIT = "6123a5d"


def test_the_spec_and_the_contract_record_r3_b10():
    """Audit round 3, R3-B10 (R3-17, R3-37, R3-38, R3-39, R3-89, R3-90 part A): §5.2's receiver-block, dropped-lead
    and R20 sentences, §8.1's strip, `holder_name` and direct-deposit sentences, §9.3's stored-output bullet, §17.1's
    owner item, one §20 line per issue and the batch line with the commit, the amended R19, R20 and R23 lines, and the
    contract's bullet."""
    text = SPEC.read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", text)
    for words in (
        "Audit round 3, R3-B10 (R3-17, §20): the holder's name is read as the payer's is",
        "audit round 3, R3-B10 (R3-17, §20): a single letter is no word of that run",
        "Audit round 3, R3-B10 (R3-38, §20; the R20 intent, now the rule)",
        "Audit round 3, R3-B10 (R3-39, §20): a `DBA` holder's whole name is read as a person's",
        "audit round 3, R3-B10: R3-37, §20: tried before the whole-word runs",
        "audit round 3, R3-B10: R3-90 part A, §20: and a bare `SETTLEMENT`, `SETTLMT` or `STLMT`",
        "audit round 3, R3-B10 (R3-89, §20): a cut form is read only as one of the holder's own forms",
        "- **A person-named company holder's direct deposit (Q8 of 2026-09-28;",
        "Audit round 3, R3-B10 (§20): no bump in a fix batch either",
        "(Amended by audit round 3, R3-B10: R3-38, R3-39, §20 below:",
        "amended by audit round 3, R3-B10: R3-37, §20 below:",
        "(Amended by audit round 3, R3-B10: R3-89, §20 below:",
    ):
        assert words in flat, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **A possessive, a middle initial or a digit token in the holder's name never stops the",
                  "- **The I47 strip tries a row-end cut first, and a leading `THE` is no word of a run**",
                  "- **Two shared trade words name the holder only beside the payer's own printed lead**",
                  "- **A `DBA` holder that leads with a person is read as that person against a person payer**",
                  "- **The direct-deposit business receiver reads only the holder's own cut forms**",
                  "- **A bare `SETTLEMENT` under the merchant's own name is no holder's own push**",
                  "- **Audit round 3, R3-B10 in all**"):
        assert words in amendments, words
    assert amendments.count("audit round 3, R3-B10 (R3-") >= 6
    assert amendments.count(R3_B10_CODE_COMMIT) >= 7
    assert "PLACEHOLDER" not in amendments
    contract = _flat(CONTRACT)
    for words in (f"Audit round 3, R3-B10 (R3-17, R3-37, R3-38, R3-39, R3-89, R3-90 part A; {R3_B10_CODE_COMMIT})",
                  "the holder test reads the holder's name as it reads the payer's"):
        assert words in contract, words


#: Audit round 3, R3-B10, review round 1: the code commit §20 and the contract name.
R3_B10_R1_CODE_COMMIT = "f598bca"


def test_the_spec_and_the_contract_record_r3_b10_review_round_1():
    """Audit round 3, R3-B10, review round 1 (findings 1 to 4): §9.3's bullet records the round's short spellings, the
    R3-17, R3-37, R3-38, R3-39, R3-90 part A and batch lines are marked in place, the §20 line carries the commit, and
    the contract's bullet. Review round 2 took the short spellings back out of §8.6 and rewrote §8.1's sentence on them
    (test_the_spec_and_the_contract_record_r3_b10_review_round_2)."""
    text = SPEC.read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", text)
    for words in (
        "Its review round 1 (§20) added the reading of a credit whose entry fields or payer region print `SETTLMT`",
    ):
        assert words in flat, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    assert amendments.count("(Amended by R3-B10 review round 1, finding 2, §20 below:") == 4
    for words in ("(Amended by R3-B10 review round 1, finding 3, §20 below: two recorded effects of the `THE`",
                  "(Amended by R3-B10 review round 1, findings 1 and 4, §20 below:",
                  "- **R3-B10 review round 1: `SETTLEMENT`'s short spellings are verification-only words",
                  "audit round 3, R3-B10, review round 1 (findings 1 to 4)", R3_B10_R1_CODE_COMMIT):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    for words in (f"Audit round 3, R3-B10, review round 1 ({R3_B10_R1_CODE_COMMIT})",
                  "`SETTLEMENT`'s short spellings `SETTLMT` and `STLMT` are verification-only words beside it"):
        assert words in contract, words


#: Audit round 3, R3-B10, review round 2: the code commit §20 and the contract name.
R3_B10_R2_CODE_COMMIT = "99d6760"


def test_the_spec_and_the_contract_record_r3_b10_review_round_2():
    """Audit round 3, R3-B10, review round 2 (findings 1 and 2): §8.1's `holder_name` bullet names the release flag,
    §8.6 reads `SETTLEMENT` alone again, §8.10 names the overruled verification, §9.3's bullet the round's stored-output
    change, the R3-90 part A and review round 1 lines are marked in place, the §20 line carries the commit and its
    measurement, and the contract's bullets."""
    text = SPEC.read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", text)
    holds = re.sub(r"\s+", " ", _section(text, "\n### 8.1 ", "\n### 8.2 "))
    assert "R3-B10 review round 2, §20: a row the bare word alone releases" in holds
    assert "`CreditFacts.settlement_released`" in holds
    refused = re.sub(r"\s+", " ", _section(text, "\n### 8.6 ", "\n### 8.7 "))
    assert "audit round 3, R3-B10 review round 2, §20: alone, as before the batch" in refused
    assert r"`\bSETTLMT\b`" not in refused and r"`\bSTLMT\b`" not in refused
    tiering = re.sub(r"\s+", " ", _section(text, "\n### 8.10 ", "\n## 9. "))
    assert "a settlement under the merchant's own name that an earlier rule verified and that only the bare" in tiering
    assert "Review round 2's own change: the reading of a row the settlement exemption alone releases" in flat
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    assert amendments.count("(Amended by R3-B10 review round 2, findings 1 and 2, §20 below:") == 2
    for words in ("- **R3-B10 review round 2: a settlement the bare word alone releases is never verified and never a",
                  "audit round 3, R3-B10, review round 2 (findings 1 and 2)", R3_B10_R2_CODE_COMMIT,
                  "Measured against `6919508`'s tree"):
        assert words in amendments, words
    for placeholder in ("CODE" + "COMMIT", "MEASUREMENT"):
        assert placeholder not in amendments, placeholder
    contract = _flat(CONTRACT)
    for words in (f"Audit round 3, R3-B10, review round 2 ({R3_B10_R2_CODE_COMMIT})",
                  "`SETTLMT` and `STLMT` are no verification-only words again",
                  "(Review round 2 takes the short spellings back out of §8.6: see the next entry.)"):
        assert words in contract, words


#: Audit round 3, R3-B11: the code commit §20 and the contract name.
R3_B11_CODE_COMMIT = "c85df95"


def test_the_spec_and_the_contract_record_r3_b11():
    """Audit round 3, R3-B11 (R3-61, R3-65, R3-30): §5.2's contact sentence, §8.10's forms, contact title, relabelled
    false negatives and recorded over-reads, §9.1's title sentence, §9.3's stored-output bullet, §10.1's True card
    fact, §17.1's premium-trust defaults (2) and (6), the R2-OW10 and R2-OW11 lines marked in place, one §20 line per
    issue and the batch line with the commit, and the contract's bullet."""
    text = SPEC.read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", text)
    for words in (
        "a contact dropped (`ATTN`, `ATTENTION`, `C/O`, glued to its text or not, and `CARE OF` after the name's legal "
        "form; audit round 3, R3-B11: R3-61, §20)",
        "Audit round 3, R3-B11 (§20): no bump in a fix batch either; its stored-output changes, for R3-B25's move.",
        "nor is a premium-trust account title read",
        "N statement(s) with no holder name read (nor a premium-trust title)",
        "a title reading `PREMIUM FUND(S) TRUST`, a bank's product name for the same account, is read as PREMIUM TRUST",
        "(6) Audit round 3, R3-B11 (R3-61, §8.10, §20): a contact line naming the premium trust account",
        "Alternative: no contact line is ever a title (the account's deposits then count).",
        "except a contact whose words are the premium-trust designation itself, published as `PREMIUM TRUST ACCOUNT`",
    ):
        assert words in flat, words
    tiering = re.sub(r"\s+", " ", _section(text, "\n### 8.10 ", "\n## 9. "))
    for words in ("Recorded false negatives (each overstates True: the trust account's deposits stay counted)",
                  "Recorded over-reads (each understates True, held and reviewable)",
                  "in the for-benefit form even when it does (audit round 3, R3-B11: R3-65, §20",
                  "`FUND` or `FUNDS` may print between them",
                  "a statement whose parser reads no holder line publishes no account title (62 routes, 452 re-parsed",
                  "a title printed on its own line under the name on a layout whose text keeps the lines apart"):
        assert words in tiering, words
    assert "the safe direction and absent from the corpus" not in tiering
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("(amended by audit round 3, R3-B11: R3-61, §20 below: except a contact whose words are the",
                  "(Amended by audit round 3, R3-B11: R3-65, §20 below: a product adjective before a kind word",
                  "- **A contact line is read by its words, not its spacing**",
                  "- **The premium-trust rule reads the product-adjective, `PREMIUM FUND TRUST` and for-benefit forms",
                  "- **The True card says a statement with no holder line read reads no premium-trust title either**",
                  "- **Audit round 3, R3-B11 in all**"):
        assert words in amendments, words
    assert amendments.count("audit round 3, R3-B11 (R3-") >= 3
    assert amendments.count(R3_B11_CODE_COMMIT) >= 4
    for placeholder in ("CODE" + "COMMIT", "MEASUREMENT"):
        assert placeholder not in amendments, placeholder
    contract = _flat(CONTRACT)
    for words in (f"Audit round 3, R3-B11 (R3-61, R3-65, R3-30; {R3_B11_CODE_COMMIT})",
                  "premium-trust titles are read by their words, not their spacing"):
        assert words in contract, words


def test_r3_b11_the_code_s_docstrings_label_the_misses_and_name_the_contact_title():
    """Audit round 3, R3-B11 (R3-65, R3-61): premium_trust_title's docstring labels its recorded false negatives as
    overstating True and records the over-reads; the holder module's docstring names the contact title."""
    from analysis import holder_name

    doc = re.sub(r"\s+", " ", true_revenue.premium_trust_title.__doc__)
    assert "Recorded false negatives (each overstates True: the trust account's deposits stay counted)" in doc
    assert "Recorded over-reads (each understates True, held and reviewable)" in doc
    assert "the safe direction" not in doc
    module = re.sub(r"\s+", " ", holder_name.__doc__)
    assert "except a contact whose words are the premium-trust designation itself" in module
    block = re.sub(r"\s+", " ", holder_name._block_title_line.__doc__)
    assert "the account's title in any spacing" in block


#: Audit round 3, R3-B11, review round 1: the code commit §20 and the contract name.
R3_B11_R1_CODE_COMMIT = "186c714"


def test_the_spec_and_the_contract_record_r3_b11_review_round_1():
    """Audit round 3, R3-B11, review round 1 (findings 1 to 4): §5.2's contact sentence, §8.10's contact designation,
    for-benefit adjective, false negative and over-read, §9.1's published title, §9.3's stored-output sentence, §17.1's
    premium-trust default (6), the R3-61 and R3-65 lines marked in place, the §20 line with the commit and its
    measurement, and the contract's bullet."""
    text = SPEC.read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", text)
    for words in (
        "(amended by R3-B11 review round 1, finding 1, §20 below: `CARE OF` only where the name has ended, right after "
        "its legal form or the designation printed right after it, so a `DBA` trade name keeps its `CARE OF`)",
        "R3-B11 review round 1, finding 2, §20: the designation is the premium-trust rule's own title at a field's end",
        "Its review round 1 (§20) changes, for the same move:",
        "(Amended by R3-B11 review round 1, finding 2, §20 below: the premium-trust designation a contact must be "
        "is the title rule's own title at a field's end",
    ):
        assert words in flat, words
    tiering = re.sub(r"\s+", " ", _section(text, "\n### 8.10 ", "\n## 9. "))
    for words in ("(Amended by R3-B11 review round 1, findings 1 and 2, §20 below: the designation a contact's words",
                  "R3-B11 review round 1, finding 3, §20: a product adjective may print before the account word",
                  "a holder line's contact that prints a name before the words (`CARE OF NORTHWIND PREMIUM TRUST "
                  "ACCOUNT`)",
                  "`PREMIUM TRUST BUSINESS ACCOUNT OF <place> LLC`, R3-B11 review round 1, finding 3"):
        assert words in tiering, words
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    assert amendments.count("(Amended by R3-B11 review round 1, findings 1 and 2, §20 below:") == 1
    assert amendments.count("(Amended by R3-B11 review round 1, finding 3, §20 below:") == 1
    for words in ("- **R3-B11 review round 1: `CARE OF` is a contact only where the name has ended",
                  "audit round 3, R3-B11, review round 1 (findings 1 to 4)", R3_B11_R1_CODE_COMMIT,
                  "Measured against `c8132a0`'s tree"):
        assert words in amendments, words
    for placeholder in ("CODE" + "COMMIT", "MEASUREMENT", "R3B11R1" + "COMMIT"):
        assert placeholder not in amendments, placeholder
    contract = _flat(CONTRACT)
    for words in (f"Audit round 3, R3-B11, review round 1 ({R3_B11_R1_CODE_COMMIT})",
                  "`CARE OF` is a contact only where the holder's name has ended",
                  "(Review round 1 reads `CARE OF` only where the name has ended and reads the contact's designation "
                  "as the title rule does: see the next entry.)"):
        assert words in contract, words


def test_r3_b11_r1_the_code_s_docstrings_name_the_narrowed_care_of_and_the_rule_s_designation():
    """Audit round 3, R3-B11, review round 1 (findings 1, 2 and 4): the holder module names CARE OF where the name has
    ended and the rule's own designation; U.S. Bank's reader names the contact title it publishes."""
    from analysis import holder_name, us_bank

    module = re.sub(r"\s+", " ", holder_name.__doc__)
    assert "`CARE OF` is a contact only where the name has ended" in module
    split = re.sub(r"\s+", " ", holder_name._contact_split.__doc__)
    assert ("only where the name has ended, right after its legal form or the designation printed right after it"
            in split)
    reader = re.sub(r"\s+", " ", us_bank._holder_reading.__doc__)
    assert "never the contact, except a contact whose words are the premium-trust designation itself" in reader


#: Audit round 3, R3-B12: the code commit §20 and the contract name.
R3_B12_CODE_COMMIT = "1360d98"


def test_the_spec_and_the_contract_record_r3_b12():
    """Audit round 3, R3-B12 (R3-12, R3-29, R3-56): §8.2's VIREMENT sentence, §8.4's rails bullet, its Yes paragraph's
    PNC reading marked in place, its reader sentence naming `pass_text` and the wire gate and its residuals, §9.3's
    stored-output bullet, the VIREMENT and R2-OW17 lines marked in place, one §20 line per issue and the batch line
    with the commit, and the contract's bullets."""
    text = SPEC.read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", text)
    transfer = re.sub(r"\s+", " ", _section(text, "\n### 8.2 ", "\n### 8.3 "))
    assert "audit round 3, R3-B12 (R3-29, §20): `PAR COURRIEL` is an Interac form" in transfer
    p2p = re.sub(r"\s+", " ", _section(text, "\n### 8.4 ", "\n### 8.5 "))
    for words in ("Audit round 3, R3-B12 (R3-29, §20): pass 7 also reads Interac's French name, "
                  "`\\bVIREMENTS? PAR COURRIEL\\b`",
                  "(since audit round 3, R3-B12: R3-12, §20: pass 7 reads PNC's `ZEL` as its `ZELLE` twin",
                  "on the pass's own text (`pass_text`:",
                  "a loose wire's originator row is never a Zelle deposit (R3-56)",
                  "a company whose name holds the word `ZELLE` paying by ACH (`DE ZELLE HOLDINGS LLC DES:VENDOR PAY`) "
                  "is still read as a Zelle deposit",
                  "PNC's `ZEL TO` debits keep the classifier's debit reading"):
        assert words in p2p, words
    assert "Audit round 3, R3-B12 (§20): no bump in a fix batch either" in flat
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("(Amended by audit round 3, R3-B12: R3-29, §20 below: `PAR COURRIEL` is an Interac form",
                  "(Amended by audit round 3, R3-B12: R3-12, §20 below:",
                  "- **PNC's `ZEL` Zelle rail reads as its `ZELLE` twin in pass 7**",
                  "- **Banque Royale's French autodeposit is the Interac rail**",
                  "- **A wire is never a Zelle deposit**",
                  "- **Audit round 3, R3-B12 in all**"):
        assert words in amendments, words
    assert amendments.count("audit round 3, R3-B12 (R3-") >= 3
    assert amendments.count(R3_B12_CODE_COMMIT) >= 4
    for placeholder in ("CODE" + "COMMIT", "MEASUREMENT", "R3B12" + "CODE"):
        assert placeholder not in amendments, placeholder
    contract = _flat(CONTRACT)
    for words in (f"Audit round 3, R3-B12 (R3-12, R3-29, R3-56; {R3_B12_CODE_COMMIT})",
                  "pass 7 reads the consumer person-to-person rails as the banks print them",
                  "(Amended by audit round 3, R3-B12: R3-12 and R3-56, below:"):
        assert words in contract, words


def test_r3_b12_the_code_s_docstrings_name_the_pass_text_and_the_wire_gate():
    """Audit round 3, R3-B12 (R3-12, R3-56, R3-29): pass_text, zelle_deposit and _p2p_rail name their readings."""
    doc = re.sub(r"\s+", " ", true_revenue.pass_text.__doc__)
    assert "spelled as its ZELLE twin" in doc
    assert "The classifier's _CONSUMER_P2P_RAIL (the 5.5 channel gate, the legacy classes, the debits) is " \
           "unchanged" in doc
    reader = re.sub(r"\s+", " ", true_revenue.zelle_deposit.__doc__)
    assert "an incoming wire or a loose wire's originator row is never a Zelle deposit" in reader
    rail = re.sub(r"\s+", " ", true_revenue._p2p_rail.__doc__)
    assert "Interac's French form, singular or plural (_INTERAC_COURRIEL" in rail


#: Audit round 3, R3-B12, review round 1: the code commit §20 and the contract name.
R3_B12_R1_CODE_COMMIT = "f13d1e6"


def _amendment_line(amendments: str, start: str) -> str:
    """The one §20 line that starts with `start`."""
    [line] = [line for line in amendments.splitlines() if line.startswith(start)]
    return line


def test_the_spec_and_the_contract_record_r3_b12_review_round_1():
    """Audit round 3, R3-B12, review round 1 (findings 1 to 4): the R3-29 and R3-12 lines carry no single statement's
    True; §8.4's Yes paragraph narrows the twin parity, its reader sentence names the two wire gates, and its residuals
    record the platform-named `ZEL` sender, the wire layouts no gate reads and the `ZEL TO` debit's own reading; the
    R3-12 and R3-56 lines marked in place; the §20 line with the commit; and the contract's entry."""
    text = SPEC.read_text(encoding="utf-8")
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    before_after = re.compile(r"\$[0-9][0-9,]*\.[0-9]{2} → \$[0-9][0-9,]*\.[0-9]{2}")
    courriel = _amendment_line(amendments, "- **Banque Royale's French autodeposit is the Interac rail**")
    assert before_after.search(courriel) is None
    for words in ("per statement", "of one business"):
        assert words not in courriel, words
    assert "True falls in three of the four statements, two of them newly review-gated" in courriel
    zel = _amendment_line(amendments, "- **PNC's `ZEL` Zelle rail reads as its `ZELLE` twin in pass 7**")
    assert "in one statement" not in zel
    assert "in two small statements these rows made most of True" in zel
    for words in ("(Amended by R3-B12 review round 1, finding 2, §20 below:",
                  "the legacy class `other`, where a `ZELLE TO` debit's is `transfer`, and no person key"):
        assert words in zel, words
    wire = _amendment_line(amendments, "- **A wire is never a Zelle deposit**")
    assert "(Amended by R3-B12 review round 1, finding 3, §20 below:" in wire
    p2p = re.sub(r"\s+", " ", _section(text, "\n### 8.4 ", "\n### 8.5 "))
    for words in ("except where the classifier's reading of the raw text claims it first (R3-B12 review round 1, "
                  "finding 2: the residual below)",
                  "an incoming wire or a loose wire's originator row is never a Zelle deposit (R3-56)",
                  "(R3-B12 review round 1, finding 3:",
                  "`ONLINE WIRE TRANSFER FROM <sender>`",
                  "`MOBILE WIRE ORG ZELLE <sender>`",
                  "(R3-B12 review round 1, finding 4:",
                  "the legacy class `other`, where a `ZELLE TO` debit's is `transfer`, and no person key",
                  "(R3-B12 review round 1, finding 2:",
                  "counted `platform_unconfirmed` once and Verified on a repeat (`recurring_operating_source`;"):
        assert words in p2p, words
    for stale in ("(kind `other`, no person key, where a `ZELLE TO` debit is `circular`)",):
        assert stale not in p2p, stale
        assert stale not in amendments, stale
    for words in ("- **R3-B12 review round 1: the R3-29 and R3-12 lines carry no single statement's True",
                  "audit round 3, R3-B12, review round 1 (findings 1 to 4)", R3_B12_R1_CODE_COMMIT,
                  "Measured against `9871cdf`'s tree"):
        assert words in amendments, words
    for placeholder in ("CODE" + "COMMIT", "MEASUREMENT", "R3B12R1" + "CODE", "CORPUS" + "_CF"):
        assert placeholder not in text, placeholder
    contract = _flat(CONTRACT)
    for words in (f"Audit round 3, R3-B12, review round 1 ({R3_B12_R1_CODE_COMMIT})",
                  "a `ZEL TO` debit's legacy class and missing person key",
                  "(Review round 1 records the readings pass 7 does not reach: see the next entry.)"):
        assert words in contract, words


def test_r3_b12_r1_the_code_s_docstrings_name_the_residuals():
    """Audit round 3, R3-B12, review round 1 (findings 2 to 4): pass_text names the classifier's earlier claim and the
    ZEL TO debit's reading; zelle_deposit names the wire layouts neither gate reads."""
    doc = re.sub(r"\s+", " ", true_revenue.pass_text.__doc__)
    assert "the classifier's earlier reading of the raw text is not pass 7's" in doc
    assert "its legacy class 'other' and no person key" in doc
    reader = re.sub(r"\s+", " ", true_revenue.zelle_deposit.__doc__)
    assert "Review round 1 (finding 3): a wire layout neither gate reads" in reader


#: Audit round 3, R3-B13: the code commit §20 and the contract name.
R3_B13_CODE_COMMIT = "f103f68"


def test_the_spec_and_the_contract_record_r3_b13():
    """Audit round 3, R3-B13 (R3-11, R3-57, R3-10, R3-09, R3-58, R3-64, R3-55): §6.1 step 3a's glued lead, §7.6's
    county-mutual veto, §8.1's spelling, arm order, consumer rail, personal-benefit words, REF, round-sum repeat and
    asset-sale sentences, §8.10 item 11, §9.3's stored-output bullet, §14.2's class H, §17.1's I26 residuals and Q2
    default (5), §19.1's appended sentences, the R2-OW01, R2-OW07 review round 1 and R2-OW08 lines marked in place, one
    §20 line per issue and the batch line with the commit, and the contract's rows and entry."""
    text = SPEC.read_text(encoding="utf-8")
    steps = re.sub(r"\s+", " ", _section(text, "\n### 6.1 ", "\n### 6.2 "))
    assert "Audit round 3, R3-B13 (R3-55, §20): a digit run glued before a letter-led form's first letter" in steps
    public = re.sub(r"\s+", " ", _section(text, "\n### 7.6 ", "\n### 7.7 "))
    assert "never followed by an insurer word (audit round 3, R3-B13: R3-11, §20;" in public
    holds = re.sub(r"\s+", " ", _section(text, "\n### 8.1 ", "\n### 8.2 "))
    for words in ("`COUNTY MUT`, a Texas county mutual's 16-character cut",
                  "(Narrowed by audit round 3, R3-B13: R3-57, §20: a consumer rail only",
                  "a listed insurer's credit is read next (audit round 3, R3-B13: R3-11, §20: before the government",
                  "(qualified by audit round 3, R3-B13: R3-64, §20:",
                  "Audit round 3, R3-B13 (R3-10, §20;", "`_INSURER_PERSONAL_BENEFIT`", "`_INSURER_LTD_BENEFIT`",
                  "`_INSURER_NON_PROVIDER_BENEFIT`", "(Audit round 3, R3-B13: R3-58, §20: the service form",
                  "Audit round 3, R3-B13 (R3-09, §20;",
                  "on a person-to-person row §8.4's round-sum repeat still wins, as for the progress draw"):
        assert words in holds, words
    tiering = re.sub(r"\s+", " ", _section(text, "\n### 8.10 ", "\n## 9. "))
    assert ("on a person-to-person row §8.4's round-sum repeat still wins, as for the progress draw (audit round 3, "
            "R3-B13: R3-09, §20)") in tiering
    assert "- Audit round 3, R3-B13 (§20): no bump in a fix batch either" in text
    census = re.sub(r"\s+", " ", _section(text, "\n### 14.2 ", "\n### 14.3 "))
    assert "Audit round 3, R3-B13 (R3-55, §20): every named form's residue is class H" in census
    open_items = _section(text, "\n### 17.1 Open after the audit fix run", "\n## 18. ")
    spelling = next(line for line in open_items.splitlines()
                    if line.startswith("- **Every insurer spelling (audit I26, R2-OW07), for the owner to confirm.**"))
    for words in ("Recorded residuals, not fixed: (1) R3-57:", "(2) R3-11:", "`HALLMARK COUNTY`"):
        assert words in spelling, words
    defaults = next(line for line in open_items.splitlines() if line.startswith(
        "- **Insurers paid for the business's work: the defaults (the underwriter's Q2 of 2026-10-02, §8.1; "
        "R2-OW08).**"))
    assert "(5) Workers' compensation and a plain `BENEFIT(S)` wording refuse the release except at a" in defaults
    review = _section(text, "\n### 19.1 Owner decisions since the review\n", "\n## 20. Implementation amendments")
    assert review.count("Audit round 3, R3-B13 (") == 3
    amendments = text.split("\n## 20. Implementation amendments", 1)[1]
    for words in ("(amended by audit round 3, R3-B13: R3-55, §20 below:",
                  "(amended by audit round 3, R3-B13: R3-11, §20 below:",
                  "(qualified by audit round 3, R3-B13: R3-64, §20 below:",
                  "(narrowed by audit round 3, R3-B13: R3-57, §20 below:",
                  "corrected, audit round 3, R3-B13: R3-58, §20 below:",
                  "(amended by audit round 3, R3-B13: R3-10, §20 below:",
                  "- **A Texas county mutual is an insurer, never a county**",
                  "- **Every insurer spelling reads off the consumer rails**",
                  "- **A personal benefit is never an insurer's payment for work**",
                  "- **A released insurer's round sums on a person-to-person row are held as any sender's**",
                  "- **The service form never reads a wire's `REF`; the customer-payment wording does**",
                  "- **A released insurer's printed asset sale is read by Q11 (b)**",
                  "- **A Q12 form after a glued digit run is read, and class H reads every named form's residue**",
                  "- **Audit round 3, R3-B13 in all**"):
        assert words in amendments, words
    assert amendments.count("audit round 3, R3-B13 (R3-") >= 7
    assert amendments.count(R3_B13_CODE_COMMIT) >= 6
    for placeholder in ("R3B13" + "CODE", "MEASURE" + "MENT_R3B13"):
        assert placeholder not in text, placeholder
    when = {cells[0]: cells[3] for cells in _reason_table()}
    assert "`COUNTY MUT`" in when["`insurer_named_payer`"]
    assert "a consumer person-to-person rail's sender" in when["`insurer_named_payer`"]
    assert "a wire's `REF` included, where Chase's book transfer and Santander print the purpose" in when[
        "`insurer_paid_for_services`"]
    assert "R3-55" in when["`government_no_purpose`"]
    contract = _flat(CONTRACT)
    for words in (f"Audit round 3, R3-B13 (R3-11, R3-57, R3-10, R3-09, R3-58, R3-64, R3-55; {R3_B13_CODE_COMMIT})",
                  "(amended by audit round 3, R3-B13: R3-10, below:", "corrected, audit round 3, R3-B13: R3-58, below:",
                  "(narrowed by R3-B13, R3-57, below: a consumer rail only)"):
        assert words in contract, words


def test_r3_b13_the_code_s_docstrings_name_the_readings():
    """Audit round 3, R3-B13: insurer_payer_reading names the arm order and the consumer rail; _insurer_for_work the
    personal-benefit refusals and the REF reader; the classifier's patterns carry their comments."""
    reader = re.sub(r"\s+", " ", true_revenue.insurer_payer_reading.__doc__)
    for words in ("read before the government arm", "on a consumer person-to-person rail (_p2p_rail",
                  "the cut MUTUA reads there only beside a company form"):
        assert words in reader, words
    release = re.sub(r"\s+", " ", true_revenue._insurer_for_work.__doc__)
    for words in ("nor a personal benefit's word", "_INSURER_LTD_BENEFIT", "_holder_provider",
                  "Chase's book transfer and Santander print the purpose in"):
        assert words in release, words
    provider = re.sub(r"\s+", " ", true_revenue._holder_provider.__doc__)
    assert "Medical claim payments to providers keep counting" in provider
    source = inspect.getsource(transaction_classifier)
    assert "Audit round 3, R3-B13 (R3-11;" in source and "Audit round 3, R3-B13 (R3-55)" in source


#: Audit round 2, R2-L01 (R43): the code commit §20 and the contract name.
R2_L01_CODE_COMMIT = "b02a930"


def test_the_spec_and_the_contract_record_r2_l01_the_liberis_admission():
    """Audit round 2, R2-L01 (R43, carried over from R2-B03): §20's Liberis line and the batch line, each with the code
    commit, and the contract's sentence."""
    amendments = SPEC.read_text(encoding="utf-8").split("\n## 20. Implementation amendments", 1)[1]
    for words in ("- **Liberis's fundings are its financing proceeds** (", "audit round 2, R2-L01: R43",
                  "the r2 verdict (2026-10-06)", "`AIRWALLEX` is never an alias",
                  "- **Audit round 2, R2-L01 in all** (", f"{R2_L01_CODE_COMMIT}'s, the re-parsed basis"):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    for words in (f"Audit round 2, R2-L01 (R43, carried over from R2-B03; {R2_L01_CODE_COMMIT})",
                  "`LIBERIS` and `LIBERIS US INC`", "`AIRWALLEX` is never an alias"):
        assert words in contract, words


#: Audit round 2, R2-B16 (R51, R53, R52): the code commits §20 and the contract name.
R2_B16_CODE_COMMITS = {"R51": ("e0eb9cb",), "R53": ("728515a", "a869554", "e26e322"), "R52": ("e17ad7c", "e26e322")}


def test_the_spec_and_the_contract_record_r2_b16_s_surfaces():
    """Audit round 2, R2-B16 (R51, R53, R52): §20's three lines, each with its code commits, the B11 lines each amends
    marked in place, the sections they amend (§10.3, §10.4, §10.8) and the contract's batch line."""
    spec = SPEC.read_text(encoding="utf-8")
    amendments = spec.split("\n## 20. Implementation amendments", 1)[1]
    for lead, issue in (("- **The Monthly Statements table names its units as the chart does** (", "R51"),
                        ("- **The statement downloads list every posted debit, and no XLSX cell is over the "
                         "spreadsheet's limit** (", "R53"),
                        ("- **The CLI reads the dashboard's revenue rules** (", "R52")):
        line = next(line for line in amendments.splitlines() if line.startswith(lead))
        assert f"audit round 2, R2-B16: {issue}" in line, issue
        tail = line.rsplit(". ", 1)[-1]
        assert all(commit in tail for commit in R2_B16_CODE_COMMITS[issue]), issue
        assert f"Amended by audit round 2, R2-B16 ({issue}, below)" in amendments, issue
    sections = spec.split("\n## 20. Implementation amendments", 1)[0]
    for words in ("Audit round 2, R2-B16 (R51, §20): the Monthly Statements table", "`unitsShown`",
                  "Audit round 2, R2-B16 (R52, §20): the CLI follows the same rule",
                  "\"Review required (ledger does not reconcile)\"", "revenue_view.UNESTABLISHED_REVENUE_KEYS",
                  "Audit round 2, R2-B16 (R53, §20): **Statement CSV/XLSX:** after the posted-credit table",
                  "Not shown: `<N>` characters, over the spreadsheet cell limit; see the JSON download.",
                  "`returned_funder_payment`"):
        assert words in sections, words
    contract = _flat(CONTRACT)
    commits = "e0eb9cb, 728515a, a869554, e17ad7c, e26e322"  # in commit order
    assert set(commits.split(", ")) == {commit for listed in R2_B16_CODE_COMMITS.values() for commit in listed}
    for words in (f"Audit round 2, R2-B16 (R51, R53, R52; {commits})", "`revenue_tiers_sum_to_posted`",
                  "a pointer to the JSON download"):
        assert words in contract, words


def test_the_spec_and_the_contract_record_r2_b16_s_version_bump_and_the_round_in_all():
    """Audit round 2, R2-B16 (R56): §9.3's 5.7 line and its corrected last paragraph (a stage-only bump sets no
    notice), §20's R56 line and the batch line with the round in all, and the contract's 5.7 line."""
    spec = SPEC.read_text(encoding="utf-8")
    sections, amendments = spec.split("\n## 20. Implementation amendments", 1)
    versions = sections.split("### 9.3 Versions", 1)[1].split("\n## 10.", 1)[0]
    for words in ("- 5.7 (audit round 2, R2-B16: R56, §20): `CLASSIFICATION_VERSION = \"5.7\"`, and "
                  "`ANALYSIS_STAGE_VERSION` 32 → 33 in the same commit",
                  "Only a `CLASSIFICATION_VERSION` move sets `analysis_rules_outdated`",
                  "a stage-only bump (B9 to B11, R2-B04 to R2-B07 above) sets no notice"):
        assert words in versions, words
    assert ("Each bump makes a re-upload recompute the analysis, keeps OCR cached, and sets "
            "`analysis_rules_outdated` on older saved analyses") not in spec
    for words in ("- **A 5.6 analysis gets the re-analyze notice, and its button recomputes it** (",
                  "audit round 2, R2-B16: R56", "- **Audit round 2, R2-B16 in all** (", "**0 credits change**",
                  "+$2,283,293.37", "−$1,564,569.67", "`true-revenue-6`"):
        assert words in amendments, words
    contract = _flat(CONTRACT)
    assert "Audit round 2, R2-B16 (R56): classification 5.7 (`CLASSIFICATION_VERSION`), with " \
           "`ANALYSIS_STAGE_VERSION` 33 in the same commit" in contract


#: The final review of round 2: the code commits §20 and the contract name.
FINAL_REVIEW_CODE_COMMITS = {"F1": "7854cf1", "F2": "4cab9ef"}
HANDOFF = ROOT / "docs" / "agent-handoffs" / "TRUE-REVENUE-HANDOFF.md"
PLAN = ROOT / "docs" / "superpowers" / "plans" / "2026-09-28-true-revenue.md"


def test_the_spec_and_the_contract_record_the_final_review_s_withholding_rule():
    """The final review of round 2, F1: a withholding basis that is not established publishes no rate (§9.1, §9.2,
    §10.1, §10.4, §10.8, §11), §20's line labelled 'final review of round 2' with its code commit and the sections it
    amends, and the contract's sentence."""
    spec = SPEC.read_text(encoding="utf-8")
    sections, amendments = spec.split("\n## 20. Implementation amendments", 1)
    for words in ("`withholding_basis_unestablished: true`", "`UNESTABLISHED_WITHHOLDING_KEYS`",
                  "**The final review of round 2, F1 (§9.1, §10.4, §11, §20):**", "`withholdingBasisAmount`",
                  "The final review of round 2, F1 (§9.1, §9.2, §10.1, §11, §20; amends B11's I51 rule and R2-B16's R52",
                  "**A withholding basis that is not established** (the final review of round 2, F1",
                  "**A basis that is not established publishes no rate** (the final review of round 2, F1"):
        assert words in sections, words
    line = next(line for line in amendments.splitlines()
                if line.startswith("- **A withholding basis that is not established publishes no rate** ("))
    for words in ("final review of round 2, F1", "§9.1", "§9.2", "§10.1", "§10.4", "§10.8", "§11",
                  FINAL_REVIEW_CODE_COMMITS["F1"], "G7"):
        assert words in line, words
    contract = _flat(CONTRACT)
    for words in ("The statement follows the same rule (the final review of round 2, F1)",
                  f"The final review of round 2, F1 ({FINAL_REVIEW_CODE_COMMITS['F1']})"):
        assert words in contract, words


def test_the_spec_and_the_contract_record_the_final_review_s_returned_funder_payment_boundaries():
    """The final review of round 2, F2: a return pairs only with a payment on or before it (§6.2 pass 4), the package's
    pass 4 matches a bounce whose payment sits in the previous statement (§6.2's package passes, §9.2, §10.1, §10.6,
    §11), G7's declared redirects (§14.3), §17.1's R2-OW13 defaults, §20's line and the contract's."""
    spec = SPEC.read_text(encoding="utf-8")
    sections, amendments = spec.split("\n## 20. Implementation amendments", 1)
    for words in ("The final review of round 2, F2(a) (§20): a confirmed funder's paid payment is no lender-side",
                  # Audit round 3, R3-B02 (R3-71): renamed, since a potential lender's payment looks back too.
                  "`_returns_a_later_lender_payment`",
                  "4. **Returned funder payments across statements** (the final review of round 2, F2(b)",
                  "`returned_funder_redirects`", "`cross_statement: true`",
                  "a return is matched only to a payment dated on or before it"):
        assert words in sections, words
    line = next(line for line in amendments.splitlines()
                if line.startswith("- **A return reverses a payment dated on or before it, and the package matches a "
                                   "bounce across statements** ("))
    for words in ("final review of round 2, F2", "§6.2", "§9.2", "§11", "§14.3", "§17.1",
                  FINAL_REVIEW_CODE_COMMITS["F2"], "G7"):
        assert words in line, words
    contract = _flat(CONTRACT)
    for words in (f"The final review of round 2, F2 ({FINAL_REVIEW_CODE_COMMITS['F2']})",
                  "only with a return dated on or after it"):
        assert words in contract, words


def test_the_handoff_and_the_plan_state_the_final_state():
    """The final review of round 2, F3: the handoff states the run's final state (complete through 283e90e and the final
    review's fixes, 5.7 / 33, the Zelle setting with Yes by default, Q3b not implemented and with the owner, R2-OW17
    and R2-OW18, the acceptance figures, the round-3 re-audit next) and no longer the superseded Zelle exclusion or the
    finished batches as to do; the plan's withholding bullet points to spec §11."""
    handoff = _flat(HANDOFF)
    for words in ("283e90e", "classification **5.7**, analysis stage **33**", "Mark Zelle Payments as True Revenue",
                  "Yes by default", "**not implemented**", "OW17", "OW18", "ACCEPTED 2026-10-07", "67.58%",
                  "**Round-3 re-audit**", "FINAL-FIX-report.md"):
        assert words in handoff, words
    for stale in ("Every Zelle deposit is non_revenue, with the excluded total shown", "B13-B16 to do",
                  "planned, not started", "| R2-L01 | Liberis ledger admission, carried over from R2-B03 | to do |"):
        assert stale not in handoff, stale
    plan = _flat(PLAN)
    assert ("`true_revenue` is added and is never the default. **Superseded** by the owner's ruling of 2026-10-02 on "
            "the underwriter's Q7") in plan
    assert "read spec §11" in plan


#: The final review of round 2, review round 1 of its fix run: the code commits §20 and the contract name.
FINAL_REVIEW_R1_COMMITS = {"decision": "1dd3b64", "g7": "7b7fb1e", "words": "2d81a43", "dates": "80e3d4b"}


def _amendment(amendments: str, start: str) -> str:
    return next(line for line in amendments.splitlines() if line.startswith(start))


def test_the_spec_the_contract_and_the_handoff_record_the_fix_run_s_review_round_1():
    """Review round 1 of the final review's fix run: the statement and its package go to review where the withholding
    basis is not established (§9.2, §10.1, §11, §17.1), G7 declares a redirect only where the dates show it (§14.3),
    pass 4's matched payment is an attempt in R2-OW18's package items and pass 4's departures from rule D are named
    (§6.2, §9.2, §17.1); §20's three lines labelled 'final review of round 2', the F1 and F2 lines marked in place, the
    contract's line, the README and the handoff."""
    spec = SPEC.read_text(encoding="utf-8")
    sections, amendments = spec.split("\n## 20. Implementation amendments", 1)
    for words in ("Review round 1 of the fix run (§20): the statement goes to review there", "`withholdingReviewDecision`",
                  "the package's `decision` is `review_required` where a member row carries the flag",
                  "each snapshot records `row_dates`", "Two of the guards above depart from rule D",
                  "Review round 1 of that fix run (§6.2, §20), for ratification",
                  "a basis that is not established does gate",
                  "marks a payment it matched as returned, so a series reads that payment as a returned attempt"):
        assert words in sections, words
    decision = _amendment(amendments, "- **The statement and its package go to review where the withholding basis is "
                                      "not established** (")
    for words in ("final review of round 2, F1", "review round 1", "§9.2", "§10.1", "§11", "§17.1",
                  FINAL_REVIEW_R1_COMMITS["decision"], FINAL_REVIEW_R1_COMMITS["words"], "Measured", "G7"):
        assert words in decision, words
    dated = _amendment(amendments, "- **G7 declares a redirected return only where the dates show it** (")
    for words in ("final review of round 2, F2(a)", "review round 1", "§14.3", FINAL_REVIEW_R1_COMMITS["g7"],
                  FINAL_REVIEW_R1_COMMITS["dates"], "Measured", "`row_dates`"):
        assert words in dated, words
    attempt = _amendment(amendments, "- **Pass 4's matched payment is a returned attempt in the package's payment "
                                     "changes, and pass 4 departs from rule D twice** (")
    for words in ("final review of round 2, F2(b)", "review round 1", "§6.2", "§9.2", "§17.1", "R2-OW18",
                  FINAL_REVIEW_R1_COMMITS["g7"], "Measured"):
        assert words in attempt, words
    # The F1 and F2 lines are marked in place, and F2's no longer calls the departures rule D's guards.
    f1 = _amendment(amendments, "- **A withholding basis that is not established publishes no rate** (")
    assert "amended by its fix run's review round 1, below" in f1
    f2 = _amendment(amendments, "- **A return reverses a payment dated on or before it, and the package matches a "
                                "bounce across statements** (")
    assert "amended by its fix run's review round 1, below" in f2
    assert "two departures from them" in f2
    contract = _flat(CONTRACT)
    commits = ", ".join(FINAL_REVIEW_R1_COMMITS.values())
    assert f"The final review of round 2, review round 1 of its fix run ({commits})" in contract
    assert "with two departures from rule D named in the review round below" in contract
    assert "go to review (a decision that read Approved reads Review required)" in _flat(README)
    handoff = _flat(HANDOFF)
    for words in ("Review round 1 of that fix run", "for ratification", "goes to review"):
        assert words in handoff, words
    assert "asks for review on its withholding only (its decision pill reads as before)" not in handoff
