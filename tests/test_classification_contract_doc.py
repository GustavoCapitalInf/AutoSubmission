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
)


def test_the_contract_lists_the_statement_passes_in_the_classifiers_order():
    source = inspect.getsource(transaction_classifier.classify_statement_transactions)
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
    assert "Amended 2026-10-02 (§2.1, §19.1): Zelle deposits are `non_revenue` (`zelle_excluded`)." in rulings
    assert "- **Zelle (owner ruling 2026-10-02, the underwriter's Q3):**" in _section(text, "\n### 8.4 ", "\n### 8.5 ")
    assert "26. Then, after every step above and before the $1 floor, the Zelle policy" in _section(
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
    assert "Its part (c') is in the code" in line and "waits for its own batch" in line
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
