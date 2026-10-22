"""The classification contract (docs/transaction-classification.md) and the README describe the code as built. A
grep check against the code's own constants, no statement data:

- every revenue tier and every reason code of `analysis.revenue.REVENUE_TIER_REASONS` is in the contract's reason
  table, in its order, with its tier and its label, and the insurer rows name the words the insurer holds read;
- every withholding denominator mode is named in the contract and the README, and the contract says that a revenue
  mode's denominator is what `eligible_deposits` carries;
- the contract lists the statement passes in the order `classify_statement_transactions` runs them;
- the contract and the README name the current classification version, and the contract states the withholding
  and potential exposure formulas the metrics publish;
- a builder's draw and an auction's seller payout read as the reason table says (fabricated rows: CONTOSO, NORTHWIND
  and SAMPLE)."""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from analysis import transaction_classifier, true_revenue
from analysis.classification import record as classification_record
from analysis.metrics import POTENTIAL_WITHHOLDING_FORMULA, WITHHOLDING_FORMULA
from analysis.revenue import REVENUE_TIER_REASONS, REVENUE_TIERS, WITHHOLDING_DENOMINATOR_MODES
from analysis.schema import Statement, Transaction
from tests.workflows import project_workflows

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "transaction-classification.md"
README = ROOT / "README.md"


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
    """The When cell names each spelling true_revenue._INSURER_SPELLINGS reads, the brand table and the holder
    strip."""
    when = {cells[0]: cells[3] for cells in _reason_table()}["`insurer_named_payer`"]
    for word in ("ASSUR", "ASSURANCES", "ASSURANT", "ASSUREUR", "MUTUA", "CASUALT", "INDEMN", "INS", "P AND C",
                 "LOSS PMT", "SUBRO"):
        assert f"`{word}" in when, word
        assert word.split()[0] in true_revenue._INSURER_SPELLINGS.pattern, word
    assert "`INSURER_CREDIT_BRANDS`" in when and "without the holder's own names" in when
    assert "`ASSURED`" in when and "`CLM`" in when


def test_the_insurer_paid_for_services_row_names_the_grounds_and_the_refusals():
    """The When cell names the three grounds, the service forms, the 31-day span, the not-for-work words and what
    precedes the count; the insurer_payer and insurer_named_payer rows name the release."""
    when = {cells[0]: cells[3] for cells in _reason_table()}
    cell = when["`insurer_paid_for_services`"]
    for words in ("repair shop", "insurance agency", "clinic", "pharmacy", "`DRP`", "`AGENTS EFT`", "`AGTEFT`",
                  "`CONTINGENCY`", "`VENDOR PMT`", "never a wire's `REF`", "three or more times within an inclusive "
                  "31-day span", "premium, refund, return, dividend", "unless a commission prints",
                  "every hold but the insurer-name hold still wins", "never verified and never a Q5 or Q6 repeat"):
        assert words in cell, words
    assert "premium- or refund-coded, under $1, a direction conflict or claimed" in when["`insurer_payer`"]
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
    assert "its total (`excluded_pending_review_total`) feeds `revenue_review_required`" in metrics
    assert "`revenue_review_items` is the held-row count" in metrics


#: The run and deploy files of this repository; the contract says none of them sets the mode.
RUN_AND_DEPLOY_PATTERNS = (
    "*.toml", "*.yml", "*.yaml", "*.ini", "*.cfg", "*.ps1", "*.sh", ".env*", "Dockerfile*", "Procfile",
    "tools/**/*.sh", "tools/**/*.ps1", "webapp/**/*.sh", "webapp/**/*.ps1", "webapp/**/*.toml",
)


def test_no_run_or_deploy_file_of_the_repository_sets_the_withholding_mode():
    contract = _section(_flat(CONTRACT), "## Withholding rate", "## Extension rule")
    assert "no run or deploy file in this repository sets `WITHHOLDING_DENOMINATOR_MODE`" in contract
    files = {path for pattern in RUN_AND_DEPLOY_PATTERNS for path in ROOT.glob(pattern) if path.is_file()}
    files |= set(project_workflows())
    assert ROOT / "run.ps1" in files and ROOT / "pytest.ini" in files
    setting = sorted(path.relative_to(ROOT, walk_up=True).as_posix() for path in files
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
    ("_apply_returned_funder_payments(", "returned funder payments (pass 7b"),
    ("_apply_represented_funder_payments(", "re-presented returned payments (pass 7c"),
)


def test_the_contract_lists_the_statement_passes_in_the_classifiers_order():
    # classify_statement_transactions runs the shared prefix, then one Zelle reading's passes and duplicate
    # finalisation; read in that order.
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


HOLDER = "CONTOSO CONSTRUCTION LLC"
_BOFA_ACH = "{payer} DES:{entry} ID:1234567 INDN:CONTOSO CONSTRUCTION LLC CO ID:1234567890 CCD"
_BOFA_WIRE = ("WIRE TYPE WIRE IN DATE 540302 TIME 1200 ET TRN 2054030200012345 SEQ 123456/000001 ORIG NORTHWIND HOMES "
              "LLC ID 1234 SND BK SAMPLE BANK ID 123456789 PMT DET {purpose}")
DRAW_AND_SELLER_ROWS = (
    (_BOFA_ACH.format(payer="NORTHWIND HOMES LLC", entry="DRAW 3"), "counted_flagged", "construction_progress_draw"),
    (_BOFA_WIRE.format(purpose="DRAW 4 PROGRESS PAYMENT"), "counted_flagged", "construction_progress_draw"),
    (_BOFA_WIRE.format(purpose="PROGRESS PAYMENT 4"), "counted_flagged", "wire_named_sender"),
    (_BOFA_ACH.format(payer="RITCHIE BROS", entry="SELLER PMT"), "non_revenue", "asset_sale_proceeds"),
)


def _first_record(text: str):
    return transaction_classifier.classify_statement_transactions(Statement(
        account_name=HOLDER, bank="Bank of America", transactions=[
            Transaction(date="2054-03-02", description=text, amount=12000.0, direction="credit"),
            Transaction(date="2054-03-03", description="MOBILE DEPOSIT", amount=300.0, direction="credit"),
        ],
    ))[0]


@pytest.mark.parametrize(("text", "tier", "reason"), DRAW_AND_SELLER_ROWS)
def test_a_builders_draw_and_an_auction_seller_payout_get_their_reason_codes(text, tier, reason):
    record = _first_record(text)
    assert (record.revenue_tier, record.revenue_tier_reason) == (tier, reason)


def test_the_contract_and_the_readme_name_the_current_classification_version():
    version = re.escape(classification_record.CLASSIFICATION_VERSION)
    assert re.search(rf"\bVersion {version} \(", _flat(CONTRACT)), version
    assert re.search(rf"\bclassification version {version}\b", _flat(README)), version


def test_the_contract_states_the_withholding_formulas_the_metrics_publish():
    assert f"`withholding_rate = {WITHHOLDING_FORMULA}`" in _flat(CONTRACT)
    assert f"`potential_withholding_exposure = {POTENTIAL_WITHHOLDING_FORMULA}`" in _flat(CONTRACT)
