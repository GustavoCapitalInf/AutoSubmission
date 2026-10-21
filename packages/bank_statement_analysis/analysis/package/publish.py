"""What the package publishes: the key sets it refuses, its basis labels, and its flagged positions."""
from __future__ import annotations

from analysis.cadence import describe_cadence
from analysis.flag_groups import FLAG_GROUPS


#: True revenue spec §10.8: the by-reason figures of the counted and held tiers, exported as readable rows. And
#: the non-revenue breakdown (`non_revenue.<code>.count` / `.total`).
TIER_REASON_KEYS = ("counted_flagged_by_reason", "excluded_pending_review_by_reason", "non_revenue_by_reason")


def published_flagged_positions(
    rollup: dict[tuple[str, str], dict], *, refuse_cross_currency: bool
) -> dict[str, list[dict]]:
    """The package's `flagged_positions` (plan contract C6): each ticked group with a counted row, in contract
    order, as a list of `{payee, documents, count, total_debited, count_credited, total_credited, cadence,
    first_date, last_date, review_required}`. The cadence is read over the payee's dates in every member together
    (analysis/cadence.py), its debits and its credits alike, so a monthly payment split across monthly statements
    reads as monthly.

    Largest total first, debited plus credited; a package that refuses to combine currencies ranks by the
    unit-free count, debits plus credits, then the payee, because an order read off summed money would publish the
    cross-currency comparison the refusal withholds (CURRENCY DOCTRINE §F)."""
    published: dict[str, list[dict]] = {}
    for group in FLAG_GROUPS:
        items = []
        for (key, _payee), item in rollup.items():
            if key != group.key:
                continue
            dates = sorted(item["dates"])
            items.append({
                "payee": item["payee"],
                "documents": item["documents"],
                "count": item["count"],
                "total_debited": item["total_debited"],
                "count_credited": item["count_credited"],
                "total_credited": item["total_credited"],
                "cadence": describe_cadence(dates)[0] if dates else None,
                "first_date": dates[0].isoformat() if dates else None,
                "last_date": dates[-1].isoformat() if dates else None,
                "review_required": item["review_required"],
            })
        if not items:
            continue
        if refuse_cross_currency:
            published[group.key] = sorted(
                items, key=lambda item: (-(item["count"] + item["count_credited"]), item["payee"])
            )
        else:
            published[group.key] = sorted(
                items, key=lambda item: (-(item["total_debited"] + item["total_credited"]), item["payee"])
            )
    return published


#: Package totals that carry money, or that divide one money figure by another.
#: Adding or dividing these across statements denominated in different
#: currencies is a unit error — `30,000 CAD + 20,000 USD != 50,000 package ADB`
#: (CURRENCY DOCTRINE §F) — so a package that is not PROVEN single-currency
#: publishes every one of them as None.
#:
#: None is this payload's established "not computable" value: an unvalidated ADB
#: already travels that way (`analysis/serialization.py::_metrics_dict`), the
#: CSV/XLSX writers already render it as an empty cell, and the dashboard's
#: `formatMoney` already renders it "N/A". A silent zero would read as "the
#: package moved no money" and a converted figure would be fabricated evidence;
#: the doctrine forbids both, so refusal is the only honest shape.
#: The published figures whose denominator is a count of MEMBERS. Two accounts
#: of one document are one period of banking and two members, so every one of
#: these is wrong by exactly that factor unless the package refuses it
#: (design §6.5's fourth bullet).
PER_PERIOD_AVERAGE_KEYS = frozenset({
    "average_daily_balance",
    "avg_monthly_cash_flow",
    "avg_monthly_credits",
    "avg_monthly_debits",
    "monthly_lender_debits",
    # The per-month True, Verified and Non-revenue.
    "avg_monthly_true_revenue",
    "avg_monthly_verified_revenue",
    "avg_monthly_non_revenue",
})


CROSS_CURRENCY_TOTAL_KEYS = frozenset({
    "average_daily_balance",
    "avg_monthly_cash_flow",
    "avg_monthly_credits",
    "avg_monthly_debits",
    # The per-month True, Verified and Non-revenue.
    "avg_monthly_true_revenue",
    "avg_monthly_verified_revenue",
    "avg_monthly_non_revenue",
    "cash_flow",
    "confirmed_true_revenue",
    "confirmed_true_revenue_total",
    "eligible_deposits",
    "flagged_position_total",
    "flagged_position_total_credited",
    "insurance_total",
    "lender_debits",
    "maximum_revenue",
    "monthly_lender_debits",
    "non_revenue_total",
    "package_withholding_rate",
    "package_withholding_rate_raw",
    "potential_lender_debit_total",
    "potential_lender_debits",
    "potential_revenue_total",
    "potential_withholding_denominator",
    "potential_withholding_exposure",
    "potential_withholding_exposure_raw",
    "potential_withholding_numerator",
    # The funder payments returned unpaid; their count is unit-free and stays.
    "returned_funder_payment_total",
    # The package passes' money, published only where a pass found a row (PACKAGE_MATCH_TOTAL_KEYS); their counts
    # are unit-free and stay.
    "returned_deposit_cross_statement_total",
    "unmatched_deposit_return_total",
    "processor_chargeback_total",
    # The deposits pass 2 held and the held ones it annotated.
    "own_account_transfer_held_total",
    "own_account_transfer_already_held_total",
    # The lump-sum payoffs, published only where a member has one (PACKAGE_MATCH_TOTAL_KEYS); their count is
    # unit-free and stays.
    "lump_sum_payoff_total",
    # The large unsourced deposits flagged, published only where a member has one (PACKAGE_MATCH_TOTAL_KEYS);
    # their count is unit-free and stays.
    "large_unsourced_deposit_total",
    "revenue_classified_total",
    "revenue_reconciliation_delta",
    "total_credits",
    "total_debits",
    "total_posted_credits",
    "true_revenue",
    # §9.2: True revenue and its counted and held parts.
    "true_revenue_total",
    "counted_flagged_total",
    "excluded_pending_review_total",
    "unverified_deposit_total",
    "verified_revenue_total",
    "withholding_denominator",
    "withholding_numerator",
})


#: True revenue spec §9.2, §11: each withholding basis's label, as a package names a member's basis where its
#: members were analysed under different ones (`withholding_basis_by_member`).
WITHHOLDING_BASIS_LABELS = {
    "legacy_eligible_deposits": "Legacy eligible deposits",
    "verified_revenue": "Verified revenue",
    "true_revenue": "True revenue",
}


#: The totals the package passes publish only where a pass found a row, so a currency refusal nulls each of them
#: only where it is published (a package without one keeps no such key).
PACKAGE_MATCH_TOTAL_KEYS = frozenset({
    "returned_deposit_cross_statement_total", "unmatched_deposit_return_total", "processor_chargeback_total",
    "own_account_transfer_held_total", "own_account_transfer_already_held_total",
    # Published the same way, only where a member has a lump-sum payoff.
    "lump_sum_payoff_total",
    # And only where a member has a large unsourced deposit flagged.
    "large_unsourced_deposit_total",
})


#: The same rule for the cross-document funder / potential-lender / insurance
#: rollups, whose money is summed across the package exactly like a total.
#:
#: `potential_lender_debit_total` is the DEPRECATED ALIAS of `total_debited` on
#: a potential-lender rollup — `package_analysis` assigns one from the other —
#: so it has to be refused with it. Leaving it out let a mixed-unit number
#: survive into the JSON, the CSV, the XLSX and the dashboard, where
#: `lenderRowHtml`'s `potential_lender_debit_total ?? total_debited` accessor
#: reads the alias FIRST and would have defeated the refusal at exactly the
#: place it was designed to bite. Every money key on these rollups belongs
#: here; everything left on them is a genuine count.
CROSS_CURRENCY_ROLLUP_KEYS = (
    "total_debited",
    "total_credited",
    "potential_lender_debit_total",
    "eligible_deposit_denominator",
    "potential_withholding_exposure",
    # A funder's payments returned unpaid, summed across the package like its total debited.
    "returned_payment_total",
)
