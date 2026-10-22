"""A package of statements read as one: `package_analysis(jobs, settings=...)` is the payload the web app
serves and downloads for it. `settings` is a display settings snapshot; None applies the defaults."""
from __future__ import annotations

from collections.abc import Iterable

from analysis.display_settings import DEFAULTS as SETTINGS_DEFAULTS
from analysis.metrics import POTENTIAL_WITHHOLDING_FORMULA, WITHHOLDING_FORMULA
from analysis.package.duplicates import duplicate_row
from analysis.package.figures import member_figures
from analysis.package.lender import package_lender_payment_changes
from analysis.package.members import select_members
from analysis.package.model import JobLike, num
from analysis.package.passes import package_match_totals, package_matches
from analysis.package.publish import (
    CROSS_CURRENCY_ROLLUP_KEYS,
    CROSS_CURRENCY_TOTAL_KEYS,
    PACKAGE_MATCH_TOTAL_KEYS,
    PER_PERIOD_AVERAGE_KEYS,
    published_flagged_positions,
    TIER_REASON_KEYS,
    WITHHOLDING_BASIS_LABELS,
)
from analysis.package.totals import PackageTotals
from analysis.revenue_view import WITHHOLDING_BASIS_UNESTABLISHED
from analysis.served_view import zelle_setting
from analysis.zelle_view import ZELLE_DEPOSITS_KEY


def package_analysis(jobs: Iterable[JobLike], *, settings: dict | None = None) -> dict:
    # The one settings snapshot this package is built on: its members are displayed with it, and its flag roll-up
    # keeps the groups it ticks.
    if settings is None:
        settings = dict(SETTINGS_DEFAULTS)
    # The repeats and the shorter printouts other statements print are left out before any figure, listed and never
    # summed; any other overlap that shares credits is named, never netted.
    selected = select_members(jobs, settings)
    # §6.2: the package passes over the final members, before the member loop, which reads their overlay on its copies
    # of the members' rows. R-d's positions are never matched.
    package_matched = package_matches(selected.members)
    package = PackageTotals(selected, zelle_counted=zelle_setting(settings))
    for member in selected.members:
        package.add(member_figures(member, package_matched, settings))
    # §9.2: each lender payment series read across the consecutive statements of one account, from the kept members'
    # displayed copies (information only).
    lender_reading: dict = {}
    lender_payment_changes, lender_payment_unchecked = package_lender_payment_changes(
        selected.members, package_matched.overlays, reading=lender_reading)
    package.finish(package_matched, lender_payment_changes, lender_payment_unchecked, lender_reading)
    totals = package.totals

    # ------------------------------------------------------------------
    # CURRENCY DOCTRINE §F — the package layer stops mixing currencies.
    #
    # Everything above ran exactly as it always has; this is the one place the
    # currency rule applies, so the same-currency path reaches the return with
    # byte-identical figures and the refusal cannot leak a half-converted
    # number into an earlier accumulation.
    # ------------------------------------------------------------------
    if package.undeclared_currency_documents:
        # Fail closed (§B): a member contributed money in a unit it never
        # named. It must not silently join a same-currency pool as if proven.
        currency_resolution = "undetermined"
        package_currency = None
        currency_refusal_reason = "undetermined_statement_currency"
    elif len(package.currency_documents) > 1:
        currency_resolution = "mixed"
        package_currency = None
        currency_refusal_reason = "multiple_currencies"
    elif len(package.currency_documents) == 1:
        currency_resolution = "single"
        package_currency = next(iter(package.currency_documents))
        currency_refusal_reason = None
    else:
        # No member produced an analysis, so no member contributed a figure in
        # any currency. Every total is a structural zero over an empty set;
        # there is no unit to protect and nothing to refuse.
        currency_resolution = "no_analyzed_documents"
        package_currency = None
        currency_refusal_reason = None
    refuse_cross_currency = currency_refusal_reason is not None

    # CURRENCY DOCTRINE §F reaches the ORDER, not only the values. Ranking these
    # rollups by their summed money publishes a cross-currency comparison —
    # "this lender took more than that one" — and nulling the figures afterwards
    # leaves that assertion standing in the row order, where it is read as fact
    # and cannot be audited because the numbers behind it are gone. A refused
    # package therefore ranks by a unit-free key: the count, then the name.
    #
    # `potential_lenders` already sorts by name. Its order never encoded a
    # magnitude comparison, so it is correct in both cases and is deliberately
    # left alone rather than churned.
    if refuse_cross_currency:
        package_funders = sorted(
            package.funders.values(),
            key=lambda r: (-int(r.get("debit_count") or 0), r["funder"]),
        )
        package_insurance_providers = sorted(
            package.insurance_providers.values(),
            key=lambda r: (-int(r.get("count") or 0), r["provider"]),
        )
    else:
        package_funders = sorted(
            package.funders.values(), key=lambda r: r["total_debited"], reverse=True
        )
        package_insurance_providers = sorted(
            package.insurance_providers.values(), key=lambda r: r["total_debited"], reverse=True
        )
    package_potential_lenders = sorted(
        package.potential_lenders.values(), key=lambda r: r["funder"]
    )
    package_flagged_positions = published_flagged_positions(
        package.flagged_rollup, refuse_cross_currency=refuse_cross_currency
    )

    published_totals = {
        **totals,
        # §6.5 / Q5. Published only when the refusal fires, so a package of
        # today's payloads carries neither key and is byte-identical.
        **({
            "cross_account_averages_refused": True,
            "cross_account_average_refusal_reason": (
                "two or more members are accounts of ONE document, so a "
                "per-period average over them would divide one period of "
                "banking by a count of accounts (no_average_over_one_document)"
            ),
            "documents_with_several_members": len(package.documents_with_several_members),
        } if package.refuse_cross_account_averages else {}),
        # Q10: surfaced, never demoted, and published
        # ONLY when there is something to surface. A `False` / `"complete"`
        # default would put two new fields on every package this platform has
        # ever produced, which is movement — and this stage moves nothing. Their
        # ABSENCE is today's package, unchanged; their presence is the fact.
        **({
            "sibling_account_omission_detected": True,
            "completeness": "partial",
            "omitted_section_count": len(selected.omitted_sections),
        } if selected.omitted_sections else {}),
        # The accounts left out for another reason than a repeat, published only when there is one.
        # `sibling_account_omission_detected` stays Q10's.
        **({
            "completeness": "partial",
            "excluded_account_count": len(package.left_out_accounts),
        } if package.left_out_accounts else {}),
        # Published only when it differs from `months` — so a package
        # of today's payloads carries no new key and is byte-identical.
        **({"statement_periods": package.statement_periods}
           if package.statement_periods != package.months else {}),
        # The accounts of kept documents left out because an earlier job published them; only when there is one, so
        # a package without one carries no new key.
        **({"duplicate_accounts": selected.duplicate_accounts} if selected.duplicate_accounts else {}),
        # The overlapping statements of one account that share credits, each pair named with what it shares, counted
        # in both (never netted); only when there is one.
        **({"overlapping_statements": selected.overlapping} if selected.overlapping else {}),
        # The package passes' counts and totals, each only where a pass found a row (package_match_totals), so a package
        # without one carries no new key.
        **package_match_totals(package_matched),
        "months": package.months,
        # Gross: every posted credit, not True revenue.
        "avg_monthly_credits": round(totals["total_credits"] / package.months, 2),
        "avg_monthly_debits": round(totals["total_debits"] / package.months, 2),
        # The confirmed lender debits per calendar month, beside the package's total (`lender_debits`); refused with
        # the other per-period figures (PER_PERIOD_AVERAGE_KEYS, a mixed currency).
        "monthly_lender_debits": round(totals["lender_debits"] / package.months, 2),
        "avg_monthly_cash_flow": round(totals["cash_flow"] / package.months, 2),
        # What an MCA advance is sized on (standard §4.1, §4.4): the per-calendar-month True and Verified revenue
        # across the package's accounts, divided by its distinct months. Both None wherever True is N/A (a member
        # not established, §10.4), and refused as the other per-month averages are (one document's accounts, a mixed
        # or undeclared currency). Non-revenue's beside them, for the copied summary.
        "avg_monthly_true_revenue": (
            None if totals["true_revenue_total"] is None else round(totals["true_revenue_total"] / package.months, 2)
        ),
        "avg_monthly_verified_revenue": (
            None if totals["true_revenue_total"] is None or totals["verified_revenue_total"] is None
            else round(totals["verified_revenue_total"] / package.months, 2)
        ),
        "avg_monthly_non_revenue": round(totals["non_revenue_total"] / package.months, 2),
        "average_daily_balance": package.average_daily_balance,
        "package_withholding_rate": package.withholding_rate,
        "package_withholding_rate_raw": package.withholding_rate_raw,
        "eligible_deposits": totals["withholding_denominator"],
        # The members' numerators (paid plus returned) over the withholding basis.
        "withholding_formula": WITHHOLDING_FORMULA,
        "withholding_review_required": package.withholding_review_required,
        # §9.2, §11: the basis M10 refuses the rate on, only where it does.
        **({WITHHOLDING_BASIS_UNESTABLISHED: True} if package.partial_revenue_denominator else {}),
        # The members' bases, only where they differ (the dashboard names them).
        **({"withholding_basis_mixed": True, "withholding_basis_by_member": package.withholding_basis_by_member}
           if package.mixed_basis else {}),
        # A revenue basis under the withholding basis floor, only where it is.
        **({"withholding_basis_below_floor": True} if package.basis_below_floor else {}),
        # The lump-sum payoffs in `lender_debits` and out of `withholding_numerator`, only where a member has one (the
        # total refused across currencies).
        **({"lump_sum_payoff_total": package.lump_sum["total"], "lump_sum_payoff_count": package.lump_sum["count"]}
           if package.lump_sum["count"] else {}),
        # §9.2: the large unsourced deposits flagged, only where a member has one (the total refused across
        # currencies, the count kept); information only.
        **({"large_unsourced_deposit_count": len(package.large_unsourced_deposits),
            "large_unsourced_deposit_total": round(sum(num(item["amount"])
                                                       for item in package.large_unsourced_deposits), 2)}
           if package.large_unsourced_deposits else {}),
        "potential_withholding_exposure": package.potential_withholding,
        "potential_withholding_exposure_raw": package.potential_withholding_raw,
        "potential_withholding_formula": POTENTIAL_WITHHOLDING_FORMULA,
        "potential_withholding_review_required": package.potential_withholding_review_required,
        "decision": package.decision,
        # Read off the ready members only; a package with none keeps the legacy mode.
        "withholding_denominator_mode": package.denominator_mode,
        # The basis the summed NSF count was cut on (analysis/nsf_days.py). "mixed" when members differ, e.g. a
        # member whose count is unavailable, or a legacy payload that could not be re-based.
        "nsf_source": (next(iter(package.nsf_sources)) if len(package.nsf_sources) == 1
                       else ("mixed" if package.nsf_sources else None)),
        "withholding_denominator_label": WITHHOLDING_BASIS_LABELS.get(
            package.denominator_mode, "Mixed denominator configuration"),
        # CURRENCY DOCTRINE §D: the one denomination every figure above is in,
        # surfaced once. None whenever the package could not prove a single one.
        "currency": package_currency,
        "currency_resolution": currency_resolution,
        "cross_currency_totals_refused": refuse_cross_currency,
        "currency_refusal_reason": currency_refusal_reason,
    }

    if package.refuse_cross_account_averages:
        # Only the PER-PERIOD figures. The sums and counts are unaffected: two
        # accounts of one document really did move that money, and adding them
        # counts each posting once. What cannot be divided by a member count is
        # a per-period average, and the ADB is refused for the doctrine's own
        # reason rather than for this one.
        for key in PER_PERIOD_AVERAGE_KEYS:
            published_totals[key] = None

    if refuse_cross_currency:
        for key in CROSS_CURRENCY_TOTAL_KEYS:
            if key in PACKAGE_MATCH_TOTAL_KEYS and key not in published_totals:
                continue  # Published only where a package pass found a row
            published_totals[key] = None
        # §9.2: the by-reason money is refused with the totals; the counts stay. The non-revenue breakdown's
        # too.
        for key in TIER_REASON_KEYS:
            if isinstance(published_totals.get(key), dict):
                published_totals[key] = {
                    reason: {**slot, "total": None} for reason, slot in published_totals[key].items()
                }
        # The Zelle figures' money too, every count kept (a nested count-and-money dict, refused part by part).
        zelle_totals = published_totals.get(ZELLE_DEPOSITS_KEY)
        if isinstance(zelle_totals, dict):
            published_totals[ZELLE_DEPOSITS_KEY] = {
                **zelle_totals, "total": None,
                "by_tier": {tier: {**slot, "total": None} for tier, slot in (zelle_totals.get("by_tier") or {}).items()},
            }
        for item in (
            *package_funders,
            *package_potential_lenders,
            *package_insurance_providers,
            *(item for items in package_flagged_positions.values() for item in items),
        ):
            for key in CROSS_CURRENCY_ROLLUP_KEYS:
                if key in item:
                    item[key] = None
        # A judgement read off a refused figure must not read as a pass. The
        # reconciliation cannot be asserted, the withholding denominator is not
        # available, and the package as a whole needs an analyst.
        published_totals["revenue_reconciles"] = False
        published_totals["revenue_tiers_sum_to_posted"] = False
        published_totals["withholding_review_required"] = True
        published_totals["decision"] = "review_required"

    # No evidence for a True revenue the package has no figure for.
    true_revenue_evidence = None if package.unestablished_revenue or package.no_statement_analysed else [
        evidence for evidence in (*package.revenue_evidence["verified_revenue"], *package.tier_evidence["counted_flagged"])
    ]
    return {
        "totals": published_totals,
        # CURRENCY DOCTRINE §F: the package's currency composition, and — when
        # the package is not single-currency — exactly which totals were refused
        # and why, so no consumer has to infer a refusal from a null.
        "currency": {
            "resolution": currency_resolution,
            "currency": package_currency,
            "currencies": sorted(package.currency_documents),
            "documents_by_currency": {
                code: package.currency_documents[code] for code in sorted(package.currency_documents)
            },
            "undeclared_currency_documents": package.undeclared_currency_documents,
            "cross_currency_totals_refused": refuse_cross_currency,
            "refusal_reason": currency_refusal_reason,
            "refused_total_fields": (
                sorted(CROSS_CURRENCY_TOTAL_KEYS) if refuse_cross_currency else []
            ),
        },
        # Each repeated statement left out is listed after the members, `is_duplicate` set, with the job it repeats
        # and why, and no figure (`duplicate_row`). A job listed twice is the same job: it is listed once, and only
        # its group below names the repeat.
        "documents": package.documents + [
            duplicate_row(entry) for entry in selected.dropped if entry["reason"] != "same_job"
        ],
        # §12: a member was analysed with older classification rules (its row says which), as a statement's
        # served copy says of itself.
        "analysis_rules_outdated": any(row["analysis_rules_outdated"] for row in package.documents),
        # D-3: one entry per statement present more than once, listing the first job and every job that
        # repeats it.
        "duplicates": selected.duplicate_groups,
        "monthly": sorted(package.monthly, key=lambda r: (r.get("period_end") or "", r.get("filename") or "")),
        "funders": package_funders,
        "potential_lenders": package_potential_lenders,
        "insurance_providers": package_insurance_providers,
        # Lender detection §8.3: the ticked flag groups, never lender math.
        "flagged_positions": package_flagged_positions,
        "transactions": package.transactions,
        "lender_evidence": package.lender_evidence,
        # The kept members' returned funder payments.
        "returned_funder_payments": package.returned_funder_payments,
        # The lump-sum payoffs' lines, each in its statement's own unit, only where there is one (never summed here,
        # so the currency refusal leaves them).
        **({"lump_sum_payoffs": package.lump_sum_payoffs} if package.lump_sum_payoffs else {}),
        # §9.2: each member's large unsourced deposits, in member order, each in its own statement's unit and share,
        # only where there is one (never summed here, so the currency refusal leaves them).
        **({"large_unsourced_deposits": package.large_unsourced_deposits} if package.large_unsourced_deposits else {}),
        # The lender payment changes across each account's consecutive statements, absent only when no member was
        # assessed, and the members not checked across statements (each with its reason), only where there is one.
        # Never summed, so the currency refusal leaves them as they are.
        **({"lender_payment_changes": package.lender_payment_changes}
           if package.lender_payment_changes is not None else {}),
        **({"lender_payment_changes_unchecked": package.lender_payment_unchecked}
           if package.lender_payment_unchecked else {}),
        # §9.2: one entry per calendar month the members stand for, the accounts added up
        # (`package_active_positions`).
        "active_positions_by_month": package.active_positions_by_month,
        "potential_lender_evidence": package.potential_lender_evidence,
        "insurance_evidence": package.insurance_evidence,
        "flagged_evidence": package.flagged_evidence,
        "verified_revenue_evidence": package.revenue_evidence["verified_revenue"],
        "unverified_deposit_evidence": package.revenue_evidence["unverified_deposit"],
        # §9.2: True revenue's evidence is the members' verified plus counted rows; None when a member's revenue
        # is not established.
        "true_revenue_evidence": true_revenue_evidence,
        "counted_flagged_evidence": package.tier_evidence["counted_flagged"],
        "excluded_pending_review_evidence": package.tier_evidence["excluded_pending_review"],
        "potential_revenue_evidence": package.revenue_evidence["unverified_deposit"],
        "non_revenue_evidence": package.revenue_evidence["non_revenue"],
        "detection": {
            "known_funders": package.funder_matches,
            "potential_lenders": package.potential_matches,
            "insurance_providers": package.insurance_matches,
            "lender_evidence": package.lender_evidence,
            "potential_lender_evidence": package.potential_lender_evidence,
            "insurance_evidence": package.insurance_evidence,
            "verified_revenue_evidence": package.revenue_evidence["verified_revenue"],
            "unverified_deposit_evidence": package.revenue_evidence["unverified_deposit"],
            "true_revenue_evidence": true_revenue_evidence,
            "counted_flagged_evidence": package.tier_evidence["counted_flagged"],
            "excluded_pending_review_evidence": package.tier_evidence["excluded_pending_review"],
            "potential_revenue_evidence": package.revenue_evidence["unverified_deposit"],
            "non_revenue_evidence": package.revenue_evidence["non_revenue"],
        },
        # An account of a multi-account document that the platform did not
        # validate is not a package member — a package sums, counts and
        # days-weights its members, and an unvalidated account has no
        # authoritative figure to contribute. It is PUBLISHED as excluded
        # rather than dropped: a member that vanished quietly is the L-1
        # defect wearing a package's clothes.
        #
        # The key exists only when there is something to say, so a package of
        # today's single-account payloads is byte-identical to what it was.
        **({"excluded_accounts": selected.excluded} if selected.excluded else {}),
        # Q10: the omissions themselves, so a reader of the package can see
        # WHICH sections were established and not published rather than only
        # that some were. Conditional for the same reason as the totals above.
        **({"omitted_sections": selected.omitted_sections} if selected.omitted_sections else {}),
        # §9.2: each match the package passes made across its statements, each leg naming its statement, account and
        # unit, and each debit they flag (never deducted); only where there is one.
        **({"package_matches": package_matched.matches} if package_matched.matches else {}),
        **({"debit_flags": package_matched.debit_flags} if package_matched.debit_flags else {}),
    }
