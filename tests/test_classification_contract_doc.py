"""Audit fix batch B12 (I62): the classification contract (docs/transaction-classification.md) and the README describe
the code as built after the audit's fix batches. A grep check, no statement data:

- every revenue tier and every reason code of `analysis.revenue.REVENUE_TIER_REASONS` is in the contract's reason
  table, with its tier and its label;
- every withholding denominator mode is named in the contract and the README, and the contract says that a revenue
  mode's denominator is what `eligible_deposits` carries;
- the contract lists the statement passes in the order `classify_statement_transactions` runs them;
- the stale sentences the audit found (identifiable interest standing for every interest form, every unverified
  deposit needing review, a verified-only opt-in, five statement passes) are gone;
- the true revenue spec's section 20 records every audit fix batch, and section 19 the owner's decisions taken since
  its review."""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from analysis import transaction_classifier
from analysis.revenue import REVENUE_TIER_REASONS, REVENUE_TIERS, WITHHOLDING_DENOMINATOR_MODES

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


@pytest.mark.parametrize("code", sorted(REVENUE_TIER_REASONS))
def test_every_reason_code_is_a_row_of_the_contracts_reason_table(code):
    tier, label = REVENUE_TIER_REASONS[code]
    assert f"| `{code}` | `{tier}` | {label} |" in CONTRACT.read_text(encoding="utf-8")


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
)


@pytest.mark.parametrize("path, sentence", STALE_SENTENCES)
def test_the_stale_sentences_are_gone(path, sentence):
    assert sentence not in _flat(path)


def test_the_spec_section_20_records_every_audit_fix_batch():
    spec = _flat(SPEC)
    amendments = spec[spec.index("## 20. Implementation amendments"):]
    for batch in range(1, 13):
        assert re.search(rf"[Aa]udit fix batch B{batch}\b", amendments), f"B{batch}"


def test_the_spec_section_19_records_the_owners_decisions_taken_since_its_review():
    review = _section(_flat(SPEC), "## 19. Owner review", "## 20. Implementation amendments")
    for decision in ("2026-09-29", "2026-09-30", "MCA", "Q5", "Q6", "government"):
        assert decision in review, decision
