"""A package of statements read as one: `package_analysis(jobs, settings=...)` is the payload the web app
serves and downloads for it. `settings` is a display settings snapshot; None applies the defaults."""
from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, ROUND_HALF_UP

from analysis.display_settings import DEFAULTS as SETTINGS_DEFAULTS
from analysis.metrics import POTENTIAL_WITHHOLDING_FORMULA, WITHHOLDING_FORMULA
from analysis.package.calendar import covered_days, months_covered, statement_month
from analysis.package.duplicates import duplicate_row
from analysis.package.figures import add_flagged_rows, member_figures
from analysis.package.lender import package_active_positions, package_lender_payment_changes
from analysis.package.members import select_members
from analysis.package.model import (
    JobLike,
    MemberKey,
    months_linked,
    num,
)
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
from analysis.revenue import (
    revenue_review_gate,
    REVENUE_STATES,
    withholding_basis_below_floor,
    withholding_basis_publishable,
)
from analysis.revenue_view import (
    unestablished_zelle_figures,
    WITHHOLDING_BASIS_UNESTABLISHED,
)
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
    documents = []
    monthly = []
    #: `(job, period start, period end)` for every member that contributed — the
    #: honest count of statement PERIODS, beside `months`'s count of members.
    #: See the note at `statement_periods` below.
    period_keys: set[tuple] = set()
    #: The calendar month each counted statement stands for (`statement_month`), and how many counted statements
    #: print no period, each its own month.
    month_keys: set[int] = set()
    months_unplaced = 0
    #: Each counted member's account reading and the days its statement covers, joined into accounts after the loop
    #: (a member linked to none is its own account).
    months_members: list[dict] = []
    #: The members whose own rows do not reconcile to the bank's figures, and the members whose True rests on rows
    #: the holds could not screen or whose payer no parser read.
    unreconciled_members: list[str] = []
    holder_unscreened_members: list[str] = []
    payer_text_unread_members: list[str] = []
    #: The members that are premium trust accounts.
    premium_trust_members: list[str] = []
    adb_weighted_sum = Decimal("0")
    adb_weight = 0
    totals = {
        # Every job the package lists, its repeats included.
        "documents": len(selected.listed),
        # D-3, the repeated statements, left out of every figure below.
        "duplicate_documents": len(selected.dropped),
        "distinct_documents": len(selected.listed) - len(selected.dropped),
        "has_duplicate_documents": bool(selected.dropped) or bool(selected.duplicate_accounts),
        "completed": 0,
        "failed": 0,
        "approved": 0,
        "summary_only": 0,
        "manual_review": 0,
        "integrity_high": 0,
        "integrity_review": 0,
        "total_credits": 0.0,
        "total_posted_credits": 0.0,
        "total_posted_credit_count": 0,
        "verified_revenue_total": 0.0,
        "verified_revenue_count": 0,
        "unverified_deposit_total": 0.0,
        "unverified_deposit_count": 0,
        "non_revenue_total": 0.0,
        "non_revenue_count": 0,
        # §9.2: True revenue, verified plus counted, and the held credits. None when a completed member's
        # revenue is not established (below).
        "true_revenue_total": 0.0,
        "true_revenue_count": 0,
        "counted_flagged_total": 0.0,
        "counted_flagged_count": 0,
        "excluded_pending_review_total": 0.0,
        "excluded_pending_review_count": 0,
        "revenue_review_items": 0,
        # Deprecated aliases for version 3.0 API consumers. True_revenue is True revenue.
        "true_revenue": 0.0,
        "confirmed_true_revenue": 0.0,
        "confirmed_true_revenue_total": 0.0,
        "confirmed_true_revenue_count": 0,
        "potential_revenue_total": 0.0,
        "potential_revenue_count": 0,
        "maximum_revenue": 0.0,
        "total_debits": 0.0,
        "cash_flow": 0.0,
        # Paid to lenders: the members' confirmed lender debits counted as paid.
        "lender_debits": 0.0,
        "lender_debit_count": 0,
        # The members' funder payments returned unpaid, out of lender_debits and in withholding_numerator.
        "returned_funder_payment_total": 0.0,
        "returned_funder_payment_count": 0,
        "lenders_detected": 0,
        "potential_lenders_detected": 0,
        "potential_lender_debit_count": 0,
        "potential_lender_debit_total": 0.0,
        "potential_lender_debits": 0.0,
        # Per calendar month: lender_debits / months (set with the other per-month figures below; it was the package's
        # total under a monthly name). Its place here keeps the downloads' row order.
        "monthly_lender_debits": 0.0,
        "insurance_count": 0,
        "insurance_total": 0.0,
        # Lender detection §8.3: the ticked flag groups' counted debits and their total, and apart from them the
        # counted credits and theirs. Never lender math (D7).
        "flagged_position_count": 0,
        "flagged_position_total": 0.0,
        "flagged_position_count_credited": 0,
        "flagged_position_total_credited": 0.0,
        "withholding_numerator": 0.0,
        "withholding_denominator": 0.0,
        "potential_withholding_numerator": 0.0,
        "potential_withholding_denominator": 0.0,
        "nsf_count": 0,
    }

    funders: dict[str, dict] = {}
    potential_lenders: dict[str, dict] = {}
    insurance_providers: dict[str, dict] = {}
    package_transactions: list[dict] = []
    package_funder_matches: list[dict] = []
    package_potential_matches: list[dict] = []
    package_insurance_matches: list[dict] = []
    package_lender_evidence: list[dict] = []
    # The kept members' returned funder payments, each naming its statement and its unit.
    package_returned_funder_payments: list[dict] = []
    # The kept members' lump-sum payoffs (each naming its statement and its unit) and their sum, published only where
    # there is one.
    package_lump_sum_payoffs: list[dict] = []
    package_lump_sum = {"count": 0, "total": 0.0}
    # §9.2: the ready members' large unsourced deposits, each naming its statement, its account and its unit, its share
    # its own statement's; information only.
    package_large_unsourced_deposits: list[dict] = []
    package_potential_lender_evidence: list[dict] = []
    package_insurance_evidence: list[dict] = []
    package_revenue_evidence: dict[str, list[dict]] = {
        state: [] for state in REVENUE_STATES
    }
    # §9.2: the counted and held credits' evidence, and the members whose revenue is not established.
    package_tier_evidence: dict[str, list[dict]] = {"counted_flagged": [], "excluded_pending_review": []}
    # §9.2: and the non-revenue breakdown, summed over the kept members whatever their revenue's standing
    # (Non-revenue stays where True is N/A, §10.4).
    package_by_reason: dict[str, dict[str, dict]] = {"counted_flagged": {}, "excluded_pending_review": {},
                                                     "non_revenue": {}}
    # §9.2: the kept members' Zelle figures, part by part ((served tier, amount) slots, read from each member's
    # metrics.zelle_deposits), whether a member carried them, and whether every member's reading is the one the setting
    # asks for.
    zelle_counted = zelle_setting(settings)
    # §9.2: `counted`, whether every kept member that carries the figures, or contributes its excluded Zelle deposits,
    # is served with them counted (the package's `counted_as_true_revenue`).
    package_zelle: dict = {"carried": False, "counted": True, "setting_applied": True, "count": 0, "total": 0.0,
                           "by_tier": {}}
    unestablished_verified: list[str] = []
    unestablished_revenue: list[str] = []
    # §11: a member whose True or Verified figure is not established adds a partial
    # figure to that mode's denominator, so the package publishes no rate on it.
    partial_revenue_denominator = False
    # §9.2: a member row marked as publishing no rate.
    any_member_basis_unestablished = False
    any_member_gated = False
    # §17.1: the ready tiered members' figures T7 reads, summed per declared currency (None, a member declaring none,
    # is its own group): currency -> [held, posted, True], cents.
    package_gate_cents: dict[str | None, list[int]] = {}
    #: (group key, payee) -> the running roll-up of the ticked flag groups (lender detection §8.3).
    flagged_rollup: dict[tuple[str, str], dict] = {}
    package_flagged_evidence: list[dict] = []
    denominator_modes: set[str] = set()
    # Each ready member's withholding basis, published where the package mixes them.
    withholding_basis_by_member: list[dict] = []
    nsf_sources: set[str] = set()
    #: CURRENCY DOCTRINE §F bookkeeping: how many money-contributing members
    #: each declared currency has, and how many declared none at all.
    currency_documents: dict[str, int] = {}
    undeclared_currency_documents = 0
    for member in selected.members:
        figures = member_figures(member, package_matched, settings)
        doc_row = figures.row
        # `totals["documents"]` counts JOBS and the counters below count
        # MEMBERS, which are the same number until a document publishes two
        # accounts and different on purpose after that: a package sums, counts
        # and days-weights ACCOUNTS, and one document contributing two of them
        # is two contributions.
        ready = figures.ready

        # CURRENCY DOCTRINE §F. A member with no analysis at all contributes
        # exactly zero to every money total below — each `num` call falls back
        # to its default over the empty dicts — so it carries no unit and cannot
        # make a package multi-currency. A member that DOES contribute money has
        # to declare the unit it contributed in; one that does not is an unknown
        # and fails the package closed rather than joining a pool as if proven.
        statement_currency = member.facts.currency
        if member.account:
            if statement_currency is None:
                undeclared_currency_documents += 1
            else:
                currency_documents[statement_currency] = (
                    currency_documents.get(statement_currency, 0) + 1
                )

        if ready:
            totals["completed"] += 1
        elif figures.pending:
            # A job still queued or processing has not failed; it is pending, a key the package publishes only when
            # one is, so a package without one is unchanged.
            totals["pending"] = totals.get("pending", 0) + 1
        else:
            totals["failed"] += 1
        if doc_row["corporate_use"] == "approved":
            totals["approved"] += 1
        elif doc_row["corporate_use"] == "summary_only":
            totals["summary_only"] += 1
        elif doc_row["corporate_use"]:
            totals["manual_review"] += 1
        if doc_row["integrity_risk"] == "high":
            totals["integrity_high"] += 1
        elif doc_row["integrity_risk"] == "review":
            totals["integrity_review"] += 1

        # Only a member with an analysis contributes a basis, so a failed member never turns a True-revenue package
        # "mixed".
        if ready:
            denominator_modes.add(str(figures.denominator_mode))
            withholding_basis_by_member.append(figures.withholding_basis)
        if isinstance(figures.nsf_source, str):
            nsf_sources.add(figures.nsf_source)  # a member with no analysis contributes no count and no basis

        totals["total_credits"] = round(totals["total_credits"] + figures.credits, 2)
        totals["total_posted_credits"] = round(
            totals["total_posted_credits"] + figures.posted_credit_total,
            2,
        )
        totals["total_posted_credit_count"] += figures.posted_credit_count
        # A member without a verified figure (None) adds nothing; the total is N/A with it below (§10.4).
        totals["verified_revenue_total"] = round(
            totals["verified_revenue_total"] + num(figures.revenue_totals["verified_revenue"]),
            2,
        )
        totals["verified_revenue_count"] += figures.revenue_counts["verified_revenue"]
        totals["unverified_deposit_total"] = round(
            totals["unverified_deposit_total"]
            + figures.revenue_totals["unverified_deposit"],
            2,
        )
        totals["unverified_deposit_count"] += figures.revenue_counts["unverified_deposit"]
        totals["confirmed_true_revenue_total"] = totals["verified_revenue_total"]
        totals["confirmed_true_revenue"] = totals["verified_revenue_total"]
        totals["confirmed_true_revenue_count"] = totals["verified_revenue_count"]
        totals["potential_revenue_total"] = totals["unverified_deposit_total"]
        totals["potential_revenue_count"] = totals["unverified_deposit_count"]
        totals["non_revenue_total"] = round(
            totals["non_revenue_total"] + figures.revenue_totals["non_revenue"],
            2,
        )
        totals["non_revenue_count"] += figures.revenue_counts["non_revenue"]
        # The non-revenue breakdown beside it, never gated on the member's revenue being established.
        for reason, slot in figures.by_reason["non_revenue"].items():
            item = package_by_reason["non_revenue"].setdefault(reason, {"count": 0, "total": 0.0})
            item["count"] += slot["count"]
            item["total"] = round(item["total"] + slot["total"], 2)
        if figures.zelle_carried:
            package_zelle["carried"] = True
            package_zelle["setting_applied"] = package_zelle["setting_applied"] and figures.zelle_setting_applied
        package_zelle["counted"] = package_zelle["counted"] and figures.zelle_counted_as_true_revenue
        for tier, count, total in figures.zelle_parts:
            item = package_zelle["by_tier"].setdefault(tier, {"count": 0, "total": 0.0})
            item["count"] += count
            item["total"] = round(item["total"] + total, 2)
            package_zelle["count"] += count
            package_zelle["total"] = round(package_zelle["total"] + total, 2)
        if ready and not figures.verified_revenue_established:
            unestablished_verified.append(member.key.id)
        if ready and not figures.revenue_established:
            unestablished_revenue.append(member.key.id)
        if figures.partial_revenue_denominator:
            partial_revenue_denominator = True
        if figures.gate_cents is not None:
            slot = package_gate_cents.setdefault(statement_currency, [0, 0, 0])
            slot[0] += figures.gate_cents[0]
            slot[1] += figures.gate_cents[1]
            slot[2] += figures.gate_cents[2]
        if figures.tiered:
            tier_totals, tier_counts = figures.tier_totals, figures.tier_counts
            totals["true_revenue_total"] = round(
                totals["true_revenue_total"] + tier_totals["verified"] + tier_totals["counted_flagged"], 2
            )
            totals["true_revenue_count"] += tier_counts["verified"] + tier_counts["counted_flagged"]
            totals["counted_flagged_total"] = round(totals["counted_flagged_total"] + tier_totals["counted_flagged"], 2)
            totals["counted_flagged_count"] += tier_counts["counted_flagged"]
            totals["excluded_pending_review_total"] = round(
                totals["excluded_pending_review_total"] + tier_totals["excluded_pending_review"], 2
            )
            totals["excluded_pending_review_count"] += tier_counts["excluded_pending_review"]
            totals["revenue_review_items"] += tier_counts["excluded_pending_review"]
            for tier in ("counted_flagged", "excluded_pending_review"):
                for reason, slot in figures.by_reason[tier].items():
                    item = package_by_reason[tier].setdefault(reason, {"count": 0, "total": 0.0})
                    item["count"] += slot["count"]
                    item["total"] = round(item["total"] + slot["total"], 2)
        any_member_gated = any_member_gated or (ready and figures.gated)
        totals["total_debits"] = round(totals["total_debits"] + figures.debits, 2)
        totals["cash_flow"] = round(totals["cash_flow"] + figures.cash_flow, 2)
        totals["lender_debits"] = round(totals["lender_debits"] + figures.lender_debits, 2)
        totals["lender_debit_count"] += figures.lender_debit_count
        totals["returned_funder_payment_total"] = round(
            totals["returned_funder_payment_total"] + figures.returned_funder_payment_total, 2
        )
        totals["returned_funder_payment_count"] += figures.returned_funder_payment_count
        package_lump_sum["count"] += figures.lump_sum_payoff_count
        package_lump_sum["total"] = round(package_lump_sum["total"] + figures.lump_sum_payoff_total, 2)
        totals["potential_lender_debit_total"] = round(
            totals["potential_lender_debit_total"] + figures.potential_lender_debit_total,
            2,
        )
        totals["potential_lender_debits"] = totals["potential_lender_debit_total"]
        totals["potential_lender_debit_count"] += figures.potential_lender_debit_count
        totals["insurance_count"] += figures.insurance_count
        totals["insurance_total"] = round(totals["insurance_total"] + figures.insurance_total, 2)
        # The members' numerators, paid plus returned, never the paid figure alone.
        totals["withholding_numerator"] = round(totals["withholding_numerator"] + figures.withholding_numerator, 2)
        totals["potential_withholding_numerator"] = totals["potential_lender_debit_total"]
        totals["withholding_denominator"] = round(
            totals["withholding_denominator"] + figures.eligible_deposits,
            2,
        )
        totals["potential_withholding_denominator"] = totals["withholding_denominator"]
        totals["nsf_count"] += figures.nsf_count

        for share in figures.funder_shares:
            item = funders.setdefault(
                share.funder,
                {"funder": share.funder, "documents": 0, "total_debited": 0.0, "returned_payment_count": 0,
                 "returned_payment_total": 0.0},
            )
            item["documents"] += 1
            if share.debit_count is not None:
                item["debit_count"] = item.get("debit_count", 0) + share.debit_count
            item["total_debited"] = round(item["total_debited"] + share.total_debited, 2)
            item["returned_payment_count"] += share.returned_payment_count
            item["returned_payment_total"] = round(item["returned_payment_total"] + share.returned_payment_total, 2)
        package_funder_matches.extend(figures.funder_matches)
        package_returned_funder_payments.extend(figures.returned_funder_payments)
        package_large_unsourced_deposits.extend(figures.large_unsourced_deposits)
        package_lump_sum_payoffs.extend(figures.lump_sum_payoffs)
        for share in figures.potential_lender_shares:
            item = potential_lenders.setdefault(
                share.funder,
                {
                    "funder": share.funder,
                    "documents": 0,
                    "debit_count": 0,
                    "potential_lender_debit_count": 0,
                    "total_debited": 0.0,
                    "potential_lender_debit_total": 0.0,
                    "status": "review_required",
                    "review_required": True,
                },
            )
            item["documents"] += 1
            item["debit_count"] += share.debit_count
            item["potential_lender_debit_count"] = item["debit_count"]
            item["total_debited"] = round(item["total_debited"] + share.total_debited, 2)
            item["potential_lender_debit_total"] = item["total_debited"]
        package_potential_matches.extend(figures.potential_matches)
        for share in figures.insurance_shares:
            item = insurance_providers.setdefault(
                share.provider,
                {"provider": share.provider, "documents": 0, "count": 0, "total_debited": 0.0},
            )
            item["documents"] += 1
            item["count"] += share.count
            item["total_debited"] = round(
                item["total_debited"] + share.total_debited,
                2,
            )
        package_insurance_matches.extend(figures.insurance_matches)

        # Flag groups (lender detection §8.3): the ticked groups' counted rows of this member's ledger, less its
        # internal-transfer legs. They never reach the lender totals, the withholding or the decision (D7).
        add_flagged_rows(flagged_rollup, figures.flagged_rows)

        package_transactions.extend(figures.transactions)
        package_lender_evidence.extend(figures.lender_evidence)
        package_potential_lender_evidence.extend(figures.potential_lender_evidence)
        package_insurance_evidence.extend(figures.insurance_evidence)
        package_flagged_evidence.extend(figures.flagged_evidence)
        for state, evidence in figures.revenue_evidence.items():
            package_revenue_evidence[state].extend(evidence)
        for tier, evidence in figures.tier_evidence.items():
            package_tier_evidence[tier].extend(evidence)

        if figures.basis_unestablished:
            any_member_basis_unestablished = True
        documents.append(doc_row)
        if ready:
            monthly.append(doc_row)
            # The same rows counted as PERIODS rather than as members. Two
            # accounts of one document share a job id and the document's one
            # printed cycle, so they collapse to one; two documents never do,
            # whatever period they print.
            period_keys.add((member.job.id, doc_row["period_start"], doc_row["period_end"]))
            # The calendar month it stands for. Two accounts of one business for one month, uploaded as two
            # files, are one month.
            month_key = statement_month(doc_row["period_start"], doc_row["period_end"])
            if month_key is None:
                months_unplaced += 1
            else:
                month_keys.add(month_key)
            # The days it covers, for its account's month floor below; with what its account is read by
            # (`months_linked`).
            months_members.append({
                "job_id": member.job.id, "facts": member.facts,
                "days": covered_days(doc_row["period_start"], doc_row["period_end"]),
            })
            if doc_row["reconciles"] is not True:
                unreconciled_members.append(doc_row["id"])
            if doc_row["holder_unscreened"]:
                holder_unscreened_members.append(doc_row["id"])
            if doc_row["payer_text_unread"]:
                payer_text_unread_members.append(doc_row["id"])
            if doc_row["premium_trust_account"]:
                premium_trust_members.append(doc_row["id"])
            if figures.adb_validated:
                adb_value = Decimal(str(figures.adb_value))
                adb_weighted_sum += adb_value * figures.adb_calendar_days
                adb_weight += figures.adb_calendar_days

    # §9.2: each lender payment series read across the consecutive statements of one account, from the kept members'
    # displayed copies (information only).
    lender_reading: dict = {}
    lender_payment_changes, lender_payment_unchecked = package_lender_payment_changes(
        selected.members, package_matched.overlays, reading=lender_reading)
    # §9.2, §10: each member row's active and possible positions, read from the same chains, and the package's
    # months.
    active_positions_by_month = package_active_positions(documents, lender_reading)

    # Design §6.5's fourth bullet, and Q5's direction: **no published average is
    # computed over two accounts of one document.** Without that, a package
    # holding one job that publishes two validated accounts over ONE statement
    # period publishes every per-month average halved, because `months` counts
    # members and each account is a member.
    #
    # The duplicate-content-digest refusal in `package_members` does not catch
    # this and cannot: it fires only when two accounts publish IDENTICAL
    # content, and two different accounts of one document pass it. This is the
    # member-set check §6.5 actually asked for, and it is keyed on the document
    # identity two members share.
    #
    # It REFUSES rather than re-divides. Choosing a denominator — periods,
    # documents, distinct months — is a policy about what a package average
    # means, and a stage whose whole claim is zero movement may not choose one.
    # A refused average is published as `None` beside the reason, the way
    # CURRENCY DOCTRINE §F refuses a cross-currency total, so no consumer has to
    # read a null as missing data. The refusal covers the per-month True and
    # Verified too (distinct calendar months, below).
    members_by_document: dict[str, int] = {}
    for member in selected.members:
        if member.key.account_index is None:
            continue  # a single-account job is one member and one document
        identity = getattr(member.job, "content_sha256", None) or member.job.id
        members_by_document[identity] = members_by_document.get(identity, 0) + 1
    documents_with_several_members = sorted(
        identity for identity, count in members_by_document.items() if count > 1
    )
    refuse_cross_account_averages = bool(documents_with_several_members)

    # `months` is the number of distinct CALENDAR months the counted statements stand for (the Monthly Statements
    # table's rule, `statement_month`), each statement that prints no period its own month. Counting
    # members would make K accounts uploaded as K files read K times the months and every monthly average 1/K of the
    # business's combined figure; MCA underwriters combine a business's accounts by month (standard §4.4 and §4.6). Each
    # per-month average
    # below is the per-calendar-month sum across accounts divided by it.
    #
    # Floored by the days each account's statements cover, as whole months of 30.4375 days, half up (the largest
    # account's), so consecutive statements of one account never read fewer months than the days they cover: a
    # 16th-to-15th cycle across February (02-16..03-15 and 03-16..04-15 both stand for March) or a cycle whose periods
    # share their closing day read 3 months over 3 statements, never 2, and a statement of 59 days reads 2, never 1. The
    # labels (`statement_month`) are unchanged; a floor below the calendar count is inert.
    #
    # An account is the members `months_linked` joins (a small union-find in member order): two keyed members by the
    # bank and the last four, as before; a member that prints no bank or fewer than four digits by the balance chain of
    # the owner's Q6 identity within its bank and holder, so a 16th-to-15th cycle whose number is not read reads its
    # months too. A member linked to none is its own account.
    links = list(range(len(months_members)))

    def account_of(place: int) -> int:
        while links[place] != place:
            links[place] = links[links[place]]
            place = links[place]
        return place

    for place, member in enumerate(months_members):
        for other_place in range(place):
            if months_linked(months_members[other_place], member):
                links[account_of(place)] = account_of(other_place)
    account_days: dict[int, set] = {}
    for place, member in enumerate(months_members):
        account_days.setdefault(account_of(place), set()).update(member["days"])
    month_floor = max((months_covered(len(days)) for days in account_days.values()), default=0)
    months = max(1, len(month_keys) + months_unplaced, month_floor)
    # The statement periods (one per document and printed cycle) beside the months, published when the two differ;
    # the dashboard prints "N statements · M months".
    statement_periods = len(period_keys) or months
    # Days-weighted mean of the per-statement daily-balance averages: summing
    # every statement's daily balances and dividing by every calendar day.
    package_average_daily_balance = None
    if adb_weight > 0:
        package_average_daily_balance = float(
            (adb_weighted_sum / adb_weight).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )
    if refuse_cross_account_averages:
        # The ADB doctrine forbids a document-level combined ADB outright, so a
        # days-weighted mean over two accounts of one document is the forbidden
        # figure arrived at by a different route.
        package_average_daily_balance = None
    # Each payment pass 4 matched to a return in the next statement is out of its funder's paid rollup and in its
    # returned payments (the member rows already read the overlay), and the returned-payment warning lists it, naming both
    # documents.
    for match in package_matched.matches:
        if match["kind"] != "returned_funder_payment":
            continue
        debit, credit = match["debit"], match["credit"]
        amount = round(abs(num(debit.get("amount"))), 2)
        rollup = funders.get(debit.get("funder") or "Unknown")
        if rollup is not None:
            rollup["debit_count"] = max(int(rollup.get("debit_count", 0)) - 1, 0)
            rollup["total_debited"] = round(rollup["total_debited"] - amount, 2)
            rollup["returned_payment_count"] += 1
            rollup["returned_payment_total"] = round(rollup["returned_payment_total"] + amount, 2)
        package_returned_funder_payments.append({
            "funder": debit.get("funder"), "amount": amount, "debit_date": debit.get("date"),
            "debit_location": debit.get("source_location"), "credit_date": credit.get("date"),
            "credit_location": credit.get("source_location"), "credit_description": credit.get("description"),
            "source_job": debit.get("job"), "source_document": debit.get("filename"),
            "source_currency": debit.get("currency"),
            **({"source_account": debit["account_index"]} if debit.get("account_index") is not None else {}),
            "credit_job": credit.get("job"), "credit_document": credit.get("filename"),
            **({"credit_account": credit["account_index"]} if credit.get("account_index") is not None else {}),
            "cross_statement": True,
            # The funder re-debited it (the re-debit's statement named).
            **package_matched.represented.get((MemberKey(debit.get("job"), debit.get("account_index")),
                                               debit.get("source_location")), {}),
        })
    totals["lenders_detected"] = len(funders)
    totals["potential_lenders_detected"] = len(potential_lenders)
    totals["flagged_position_count"] = sum(item["count"] for item in flagged_rollup.values())
    totals["flagged_position_total"] = round(sum(item["total_debited"] for item in flagged_rollup.values()), 2)
    totals["flagged_position_count_credited"] = sum(item["count_credited"] for item in flagged_rollup.values())
    totals["flagged_position_total_credited"] = round(
        sum(item["total_credited"] for item in flagged_rollup.values()), 2
    )
    totals["maximum_revenue"] = round(
        totals["verified_revenue_total"] + totals["unverified_deposit_total"],
        2,
    )
    totals["revenue_classified_total"] = round(
        totals["verified_revenue_total"]
        + totals["unverified_deposit_total"]
        + totals["non_revenue_total"],
        2,
    )
    totals["revenue_classified_count"] = (
        totals["verified_revenue_count"]
        + totals["unverified_deposit_count"]
        + totals["non_revenue_count"]
    )
    totals["revenue_reconciliation_delta"] = round(
        totals["revenue_classified_total"] - totals["total_posted_credits"],
        2,
    )
    # The four-tier identity summed over the members, under its own name; `revenue_reconciles` is its deprecated
    # alias. Neither is a reconciliation against the bank's figures: `unreconciled_documents` lists the members whose
    # own rows do not reconcile (`reconciliation.ok`), which the dashboard's Revenue chip reads.
    totals["revenue_tiers_sum_to_posted"] = (
        totals["revenue_reconciliation_delta"] == 0.0
        and totals["revenue_classified_count"] == totals["total_posted_credit_count"]
    )
    totals["revenue_reconciles"] = totals["revenue_tiers_sum_to_posted"]
    totals["unreconciled_documents"] = sorted(unreconciled_members)
    # The members whose holder's name is unknown, or whose credits' payer no parser read; the True card names them.
    totals["holder_unscreened_documents"] = sorted(holder_unscreened_members)
    totals["payer_text_unread_documents"] = sorted(payer_text_unread_members)
    # The members whose deposits that would count are held for a premium trust account's title; the True card names how
    # many.
    totals["premium_trust_documents"] = sorted(premium_trust_members)
    # §9.2: the gate applied to each member; a package needs revenue review when one of them does. §17.1: T7's shares
    # are also read on the package's sums, per declared currency, so a package of months each holding under
    # REVENUE_REVIEW_HELD_FLOOR gates as the same credits printed as one statement would (an advance is sized on the
    # deal's True, standard §4.4). Review only: no figure moves. The direction-conflict and four-tier terms stay per
    # member; the posted-credit share on the sums adds nothing (a sum's share reaches 10% only where a member's does),
    # so only the floored True-plus-held share can add.
    package_sums_gated = any(
        revenue_review_gate(direction_conflict=False, held_total=held / 100, posted_total=posted / 100,
                            tiers_sum_to_posted=True, true_total=true / 100)
        for held, posted, true in package_gate_cents.values()
    )
    totals["revenue_review_required"] = any_member_gated or package_sums_gated
    totals["counted_flagged_by_reason"] = package_by_reason["counted_flagged"]
    totals["excluded_pending_review_by_reason"] = package_by_reason["excluded_pending_review"]
    # §9.2: the kept members' non-revenue breakdown. It is left out of the two nulling blocks below (§10.4's and the
    # no-analysis one: Non-revenue stays), and its money is refused with the totals under a currency refusal, its counts
    # kept.
    totals["non_revenue_by_reason"] = dict(sorted(package_by_reason["non_revenue"].items()))
    # §9.2: the kept members' Zelle figures, part by part, present when a kept member carries them; `setting_applied`
    # False when a member's is. Its money is refused with the totals under a currency refusal, its counts kept.
    # `counted_as_true_revenue` is the members' served reading (true when every kept member carrying the figures, or
    # contributing its excluded Zelle deposits, is served with them counted), as each statement's is; `setting` is the
    # setting the package was served under (packages only), which the download's `zelle_deposits.setting` row reads.
    if package_zelle["carried"]:
        order = {tier: position for position, tier in enumerate(("verified", "counted_flagged",
                                                                 "excluded_pending_review", "non_revenue"))}
        totals[ZELLE_DEPOSITS_KEY] = {
            "counted_as_true_revenue": package_zelle["counted"],
            "setting": zelle_counted,
            "setting_applied": package_zelle["setting_applied"],
            "count": package_zelle["count"],
            "total": package_zelle["total"],
            "by_tier": dict(sorted(package_zelle["by_tier"].items(), key=lambda item: order.get(item[0], len(order)))),
        }
    totals["revenue_unestablished_documents"] = sorted(set(unestablished_revenue) | set(unestablished_verified))
    totals["true_revenue"] = totals["true_revenue_total"]
    if unestablished_revenue:
        # §10.4: a package's True, Counted and Held figures stand only when every completed member's revenue does.
        for key in ("true_revenue_total", "true_revenue_count", "counted_flagged_total", "counted_flagged_count",
                    "excluded_pending_review_total", "excluded_pending_review_count", "true_revenue",
                    "counted_flagged_by_reason", "excluded_pending_review_by_reason"):
            totals[key] = None
    if unestablished_verified:
        # T9: confirmed_true_revenue_total and confirmed_true_revenue alias the verified total, so they are N/A with it.
        for key in ("verified_revenue_total", "confirmed_true_revenue_total", "confirmed_true_revenue"):
            totals[key] = None
    # §10.4: and so are the Zelle figures' parts of them, the counted and held slots with True, Counted and Held
    # and the verified slot with Verified; the captured rows' count, total and non-revenue part stay (the
    # Non-revenue figures stay too).
    if ZELLE_DEPOSITS_KEY in totals:
        totals[ZELLE_DEPOSITS_KEY] = unestablished_zelle_figures(
            totals[ZELLE_DEPOSITS_KEY], established=not unestablished_revenue,
            verified_established=not unestablished_verified)
    # A package with no statement analysed (every job failed, was interrupted or is still queued or processing, or
    # every account was left out) has no revenue figure at all: True, Verified, Counted and Held are N/A, never a
    # $0.00 an underwriter would read as a measured decline, and nothing reads as reconciled. With one analysed
    # statement or more, §10.4 holds as before: a failed member's credits are in no total.
    no_statement_analysed = totals["completed"] == 0
    if no_statement_analysed:
        for key in ("true_revenue_total", "true_revenue_count", "counted_flagged_total", "counted_flagged_count",
                    "excluded_pending_review_total", "excluded_pending_review_count", "true_revenue",
                    "counted_flagged_by_reason", "excluded_pending_review_by_reason", "verified_revenue_total",
                    "confirmed_true_revenue_total", "confirmed_true_revenue"):
            totals[key] = None
        totals["revenue_tiers_sum_to_posted"] = totals["revenue_reconciles"] = False
    # True revenue spec §9.2, §11: the package's one basis. A package with no ready member keeps today's legacy mode (no
    # rate: it has no basis); one whose members were analysed under different bases is mixed, and publishes no rate over
    # the blend.
    package_denominator_mode = (
        next(iter(denominator_modes)) if len(denominator_modes) == 1
        else "legacy_eligible_deposits" if not denominator_modes else "mixed"
    )
    mixed_basis = len(denominator_modes) > 1
    # A revenue basis under the withholding basis floor publishes no rate, as $0 does; the legacy basis and a mixed one
    # (refused below) never read the floor. Never a gate.
    package_basis_below_floor = not mixed_basis and withholding_basis_below_floor(
        totals["withholding_denominator"], package_denominator_mode)
    package_withholding_raw = (
        abs(totals["withholding_numerator"]) / totals["withholding_denominator"] * 100
        if withholding_basis_publishable(totals["withholding_denominator"], package_denominator_mode)
        else None
    )
    package_withholding = round(package_withholding_raw, 2) if package_withholding_raw is not None else None
    withholding_review_required = not withholding_basis_publishable(
        totals["withholding_denominator"], package_denominator_mode)
    potential_withholding_raw = (
        abs(totals["potential_withholding_numerator"])
        / totals["potential_withholding_denominator"]
        * 100
        if withholding_basis_publishable(totals["potential_withholding_denominator"], package_denominator_mode)
        else None
    )
    potential_withholding = (
        round(potential_withholding_raw, 2)
        if potential_withholding_raw is not None
        else None
    )
    if partial_revenue_denominator:
        # Final review M10 (§11): the denominator is partial in the True- or Verified-revenue mode, so neither rate
        # on it is published, and the package asks for review.
        package_withholding = package_withholding_raw = None
        potential_withholding = potential_withholding_raw = None
        withholding_review_required = True
    if mixed_basis:
        # Members analysed under different withholding bases (a job stored with a legacy or no mode, beside
        # a new one) sum legacy deposits and True revenue into one figure that is neither: no package rate and no
        # potential exposure is published over it, and the package asks for review. Each member row keeps its own basis
        # and rate.
        package_withholding = package_withholding_raw = None
        potential_withholding = potential_withholding_raw = None
        withholding_review_required = True
    # A lender row carries no basis where the package publishes no exposure over a basis: a partial one, a mixed one
    # or one under the floor; a basis of $0 or less keeps its 0.0, as before.
    rollup_basis_refused = partial_revenue_denominator or mixed_basis or package_basis_below_floor
    potential_withholding_review_required = totals["potential_lender_debit_count"] > 0
    for item in potential_lenders.values():
        # No basis on a lender row where the package's is partial, or the dashboard would compute the exposure
        # the package refuses from it.
        item["eligible_deposit_denominator"] = (
            None if rollup_basis_refused else totals["potential_withholding_denominator"])
        item["potential_withholding_exposure"] = (
            abs(item["total_debited"]) / totals["potential_withholding_denominator"] * 100
            if withholding_basis_publishable(totals["potential_withholding_denominator"], package_denominator_mode)
            and not rollup_basis_refused
            else None
        )
        item["potential_withholding_formula"] = POTENTIAL_WITHHOLDING_FORMULA
    # The accounts left out of every figure for a reason other than a repeat: a statement whose main account is held or
    # idle, an account that did not validate on its own (Q1), and every account of a document whose transfers could not
    # be paired (Q2) or that left a section out without proof (L1-C17). Membership and every figure stay as they are;
    # the package says so (completeness partial, the count, the download section and the dashboard's notice) and needs
    # an analyst, as the same account uploaded alone does.
    left_out_accounts = [entry for entry in selected.excluded if entry.get("is_duplicate") is not True]
    decision = "approved"
    # The four-tier identity is not read here: it holds by construction on every tiered member, and a member whose
    # tiers do not sum already gates through `revenue_review_required` (its T7 term, or §12's for an older member). A
    # repeated statement left out of the figures needs an analyst.
    if (
        totals["failed"]
        or totals["integrity_high"]
        or totals["manual_review"]
        or potential_withholding_review_required
        or totals["revenue_review_required"]
        # §9.2, §11: a member whose withholding basis is not established, or the package's own partial basis,
        # publishes no rate, so the package needs an analyst, as each such statement viewed alone does. The legacy
        # basis sets neither.
        or any_member_basis_unestablished
        or partial_revenue_denominator
        # Members analysed under different withholding bases publish no package rate, so the package needs an analyst
        # (re-analyze them on one basis). The basis floor, like a $0 basis, never gates.
        or mixed_basis
        or totals["has_duplicate_documents"]
        # Two statements of one account that share credits in the days both cover.
        or selected.overlapping
        # An account left out for another reason than a repeat, and a job still queued or processing.
        or left_out_accounts
        or totals.get("pending")
    ):
        decision = "review_required"
    elif totals["summary_only"] or totals["integrity_review"]:
        decision = "limited_review"

    # ------------------------------------------------------------------
    # CURRENCY DOCTRINE §F — the package layer stops mixing currencies.
    #
    # Everything above ran exactly as it always has; this is the one place the
    # currency rule applies, so the same-currency path reaches the return with
    # byte-identical figures and the refusal cannot leak a half-converted
    # number into an earlier accumulation.
    # ------------------------------------------------------------------
    if undeclared_currency_documents:
        # Fail closed (§B): a member contributed money in a unit it never
        # named. It must not silently join a same-currency pool as if proven.
        currency_resolution = "undetermined"
        package_currency = None
        currency_refusal_reason = "undetermined_statement_currency"
    elif len(currency_documents) > 1:
        currency_resolution = "mixed"
        package_currency = None
        currency_refusal_reason = "multiple_currencies"
    elif len(currency_documents) == 1:
        currency_resolution = "single"
        package_currency = next(iter(currency_documents))
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
            funders.values(),
            key=lambda r: (-int(r.get("debit_count") or 0), r["funder"]),
        )
        package_insurance_providers = sorted(
            insurance_providers.values(),
            key=lambda r: (-int(r.get("count") or 0), r["provider"]),
        )
    else:
        package_funders = sorted(
            funders.values(), key=lambda r: r["total_debited"], reverse=True
        )
        package_insurance_providers = sorted(
            insurance_providers.values(), key=lambda r: r["total_debited"], reverse=True
        )
    package_potential_lenders = sorted(
        potential_lenders.values(), key=lambda r: r["funder"]
    )
    package_flagged_positions = published_flagged_positions(
        flagged_rollup, refuse_cross_currency=refuse_cross_currency
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
            "documents_with_several_members": len(documents_with_several_members),
        } if refuse_cross_account_averages else {}),
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
            "excluded_account_count": len(left_out_accounts),
        } if left_out_accounts else {}),
        # Published only when it differs from `months` — so a package
        # of today's payloads carries no new key and is byte-identical.
        **({"statement_periods": statement_periods}
           if statement_periods != months else {}),
        # The accounts of kept documents left out because an earlier job published them; only when there is one, so
        # a package without one carries no new key.
        **({"duplicate_accounts": selected.duplicate_accounts} if selected.duplicate_accounts else {}),
        # The overlapping statements of one account that share credits, each pair named with what it shares, counted
        # in both (never netted); only when there is one.
        **({"overlapping_statements": selected.overlapping} if selected.overlapping else {}),
        # The package passes' counts and totals, each only where a pass found a row (package_match_totals), so a package
        # without one carries no new key.
        **package_match_totals(package_matched),
        "months": months,
        # Gross: every posted credit, not True revenue.
        "avg_monthly_credits": round(totals["total_credits"] / months, 2),
        "avg_monthly_debits": round(totals["total_debits"] / months, 2),
        # The confirmed lender debits per calendar month, beside the package's total (`lender_debits`); refused with
        # the other per-period figures (PER_PERIOD_AVERAGE_KEYS, a mixed currency).
        "monthly_lender_debits": round(totals["lender_debits"] / months, 2),
        "avg_monthly_cash_flow": round(totals["cash_flow"] / months, 2),
        # What an MCA advance is sized on (standard §4.1, §4.4): the per-calendar-month True and Verified revenue
        # across the package's accounts, divided by its distinct months. Both None wherever True is N/A (a member
        # not established, §10.4), and refused as the other per-month averages are (one document's accounts, a mixed
        # or undeclared currency). Non-revenue's beside them, for the copied summary.
        "avg_monthly_true_revenue": (
            None if totals["true_revenue_total"] is None else round(totals["true_revenue_total"] / months, 2)
        ),
        "avg_monthly_verified_revenue": (
            None if totals["true_revenue_total"] is None or totals["verified_revenue_total"] is None
            else round(totals["verified_revenue_total"] / months, 2)
        ),
        "avg_monthly_non_revenue": round(totals["non_revenue_total"] / months, 2),
        "average_daily_balance": package_average_daily_balance,
        "package_withholding_rate": package_withholding,
        "package_withholding_rate_raw": package_withholding_raw,
        "eligible_deposits": totals["withholding_denominator"],
        # The members' numerators (paid plus returned) over the withholding basis.
        "withholding_formula": WITHHOLDING_FORMULA,
        "withholding_review_required": withholding_review_required,
        # §9.2, §11: the basis M10 refuses the rate on, only where it does.
        **({WITHHOLDING_BASIS_UNESTABLISHED: True} if partial_revenue_denominator else {}),
        # The members' bases, only where they differ (the dashboard names them).
        **({"withholding_basis_mixed": True, "withholding_basis_by_member": withholding_basis_by_member}
           if mixed_basis else {}),
        # A revenue basis under the withholding basis floor, only where it is.
        **({"withholding_basis_below_floor": True} if package_basis_below_floor else {}),
        # The lump-sum payoffs in `lender_debits` and out of `withholding_numerator`, only where a member has one (the
        # total refused across currencies).
        **({"lump_sum_payoff_total": package_lump_sum["total"], "lump_sum_payoff_count": package_lump_sum["count"]}
           if package_lump_sum["count"] else {}),
        # §9.2: the large unsourced deposits flagged, only where a member has one (the total refused across
        # currencies, the count kept); information only.
        **({"large_unsourced_deposit_count": len(package_large_unsourced_deposits),
            "large_unsourced_deposit_total": round(sum(num(item["amount"])
                                                       for item in package_large_unsourced_deposits), 2)}
           if package_large_unsourced_deposits else {}),
        "potential_withholding_exposure": potential_withholding,
        "potential_withholding_exposure_raw": potential_withholding_raw,
        "potential_withholding_formula": POTENTIAL_WITHHOLDING_FORMULA,
        "potential_withholding_review_required": potential_withholding_review_required,
        "decision": decision,
        # Read off the ready members only; a package with none keeps the legacy mode.
        "withholding_denominator_mode": package_denominator_mode,
        # The basis the summed NSF count was cut on (analysis/nsf_days.py). "mixed" when members differ, e.g. a
        # member whose count is unavailable, or a legacy payload that could not be re-based.
        "nsf_source": next(iter(nsf_sources)) if len(nsf_sources) == 1 else ("mixed" if nsf_sources else None),
        "withholding_denominator_label": WITHHOLDING_BASIS_LABELS.get(
            package_denominator_mode, "Mixed denominator configuration"),
        # CURRENCY DOCTRINE §D: the one denomination every figure above is in,
        # surfaced once. None whenever the package could not prove a single one.
        "currency": package_currency,
        "currency_resolution": currency_resolution,
        "cross_currency_totals_refused": refuse_cross_currency,
        "currency_refusal_reason": currency_refusal_reason,
    }

    if refuse_cross_account_averages:
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
    true_revenue_evidence = None if unestablished_revenue or no_statement_analysed else [
        evidence for evidence in (*package_revenue_evidence["verified_revenue"], *package_tier_evidence["counted_flagged"])
    ]
    return {
        "totals": published_totals,
        # CURRENCY DOCTRINE §F: the package's currency composition, and — when
        # the package is not single-currency — exactly which totals were refused
        # and why, so no consumer has to infer a refusal from a null.
        "currency": {
            "resolution": currency_resolution,
            "currency": package_currency,
            "currencies": sorted(currency_documents),
            "documents_by_currency": {
                code: currency_documents[code] for code in sorted(currency_documents)
            },
            "undeclared_currency_documents": undeclared_currency_documents,
            "cross_currency_totals_refused": refuse_cross_currency,
            "refusal_reason": currency_refusal_reason,
            "refused_total_fields": (
                sorted(CROSS_CURRENCY_TOTAL_KEYS) if refuse_cross_currency else []
            ),
        },
        # Each repeated statement left out is listed after the members, `is_duplicate` set, with the job it repeats
        # and why, and no figure (`duplicate_row`). A job listed twice is the same job: it is listed once, and only
        # its group below names the repeat.
        "documents": documents + [
            duplicate_row(entry) for entry in selected.dropped if entry["reason"] != "same_job"
        ],
        # §12: a member was analysed with older classification rules (its row says which), as a statement's
        # served copy says of itself.
        "analysis_rules_outdated": any(row["analysis_rules_outdated"] for row in documents),
        # D-3: one entry per statement present more than once, listing the first job and every job that
        # repeats it.
        "duplicates": selected.duplicate_groups,
        "monthly": sorted(monthly, key=lambda r: (r.get("period_end") or "", r.get("filename") or "")),
        "funders": package_funders,
        "potential_lenders": package_potential_lenders,
        "insurance_providers": package_insurance_providers,
        # Lender detection §8.3: the ticked flag groups, never lender math.
        "flagged_positions": package_flagged_positions,
        "transactions": package_transactions,
        "lender_evidence": package_lender_evidence,
        # The kept members' returned funder payments.
        "returned_funder_payments": package_returned_funder_payments,
        # The lump-sum payoffs' lines, each in its statement's own unit, only where there is one (never summed here,
        # so the currency refusal leaves them).
        **({"lump_sum_payoffs": package_lump_sum_payoffs} if package_lump_sum_payoffs else {}),
        # §9.2: each member's large unsourced deposits, in member order, each in its own statement's unit and share,
        # only where there is one (never summed here, so the currency refusal leaves them).
        **({"large_unsourced_deposits": package_large_unsourced_deposits} if package_large_unsourced_deposits else {}),
        # The lender payment changes across each account's consecutive statements, absent only when no member was
        # assessed, and the members not checked across statements (each with its reason), only where there is one.
        # Never summed, so the currency refusal leaves them as they are.
        **({"lender_payment_changes": lender_payment_changes} if lender_payment_changes is not None else {}),
        **({"lender_payment_changes_unchecked": lender_payment_unchecked} if lender_payment_unchecked else {}),
        # §9.2: one entry per calendar month the members stand for, the accounts added up
        # (`package_active_positions`).
        "active_positions_by_month": active_positions_by_month,
        "potential_lender_evidence": package_potential_lender_evidence,
        "insurance_evidence": package_insurance_evidence,
        "flagged_evidence": package_flagged_evidence,
        "verified_revenue_evidence": package_revenue_evidence["verified_revenue"],
        "unverified_deposit_evidence": package_revenue_evidence["unverified_deposit"],
        # §9.2: True revenue's evidence is the members' verified plus counted rows; None when a member's revenue
        # is not established.
        "true_revenue_evidence": true_revenue_evidence,
        "counted_flagged_evidence": package_tier_evidence["counted_flagged"],
        "excluded_pending_review_evidence": package_tier_evidence["excluded_pending_review"],
        "potential_revenue_evidence": package_revenue_evidence["unverified_deposit"],
        "non_revenue_evidence": package_revenue_evidence["non_revenue"],
        "detection": {
            "known_funders": package_funder_matches,
            "potential_lenders": package_potential_matches,
            "insurance_providers": package_insurance_matches,
            "lender_evidence": package_lender_evidence,
            "potential_lender_evidence": package_potential_lender_evidence,
            "insurance_evidence": package_insurance_evidence,
            "verified_revenue_evidence": package_revenue_evidence["verified_revenue"],
            "unverified_deposit_evidence": package_revenue_evidence["unverified_deposit"],
            "true_revenue_evidence": true_revenue_evidence,
            "counted_flagged_evidence": package_tier_evidence["counted_flagged"],
            "excluded_pending_review_evidence": package_tier_evidence["excluded_pending_review"],
            "potential_revenue_evidence": package_revenue_evidence["unverified_deposit"],
            "non_revenue_evidence": package_revenue_evidence["non_revenue"],
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
