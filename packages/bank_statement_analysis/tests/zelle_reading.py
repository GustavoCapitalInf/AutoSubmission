"""The owner's ruling of 2026-10-02 (the underwriter's Q3; true revenue spec §8.4, §8.10 step 26; R2-OW02 CR7): every
posted Zelle deposit is non_revenue (`zelle_excluded`), the rules' own reading kept on the record. The reader tests
that pin a Zelle row's tier read the rules through `rules_reading`, which asserts the policy's final tier on every
Zelle deposit it was due on, so a reader's regression stays visible behind the policy and the policy's own regression
fails too. Never re-point a reader test to the final tier alone."""
from __future__ import annotations

from analysis import true_revenue
from analysis.transaction_classifier import revenue_text

ZELLE_EXCLUDED = ("non_revenue", "zelle_excluded")


def zelle_policy_due(record) -> bool:
    """A posted credit the Zelle policy reads (it prints the Zelle rail) that no non-revenue rule decided and whose
    direction does not conflict: the policy must have excluded it."""
    if not (record.amount > 0 and record.is_posted and record.revenue_tier is not None):
        return False
    if not true_revenue.zelle_deposit(revenue_text(record.normalized_description)):
        return False
    if true_revenue.zelle_prior_reading(record) is not None:
        return True
    return record.revenue_classification != "non_revenue" and record.revenue_match_method != "direction_conflict"


def rules_reading(record, *, method: bool = False) -> tuple[str | None, str | None]:
    """The rules' tier and reason of a credit (with `method`, its method where it has no reason). A Zelle deposit the
    policy excluded reads through zelle_prior_reading, its final tier asserted to be (non_revenue, zelle_excluded);
    a Zelle deposit the policy was due on and did not exclude fails."""
    prior = true_revenue.zelle_prior_reading(record)
    if zelle_policy_due(record) or prior is not None:
        assert (record.revenue_tier, record.revenue_tier_reason) == ZELLE_EXCLUDED, record.normalized_description
        assert record.revenue_match_method == true_revenue.ZELLE_POLICY_METHOD
        assert prior is not None
        return prior
    reason = record.revenue_tier_reason
    return record.revenue_tier, (reason or record.revenue_match_method) if method else reason
