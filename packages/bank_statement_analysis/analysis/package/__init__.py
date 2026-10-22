"""A package of statements read as one: `package_analysis(jobs, settings=...)` is the payload the web app
serves and downloads for it. `settings` is a display settings snapshot; None applies the defaults."""
from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite

from analysis.display_settings import DEFAULTS as SETTINGS_DEFAULTS
from analysis.flagged_view import enabled_group_keys
from analysis.metrics import POTENTIAL_WITHHOLDING_FORMULA, WITHHOLDING_FORMULA
from analysis.package.calendar import covered_days, months_covered, statement_month
from analysis.package.duplicates import duplicate_row
from analysis.package.figures import (
    add_flagged_rows,
    contributes_to_potential_totals,
    counts_as_flagged,
    member_lender,
    member_revenue,
)
from analysis.package.lender import package_active_positions, package_lender_payment_changes
from analysis.package.members import select_members
from analysis.package.model import (
    is_count,
    JobLike,
    MemberKey,
    months_linked,
    num,
    overlaid_row,
)
from analysis.package.passes import member_tiered, package_match_totals, package_matches
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
    non_revenue_reason,
    normalize_withholding_denominator_mode,
    revenue_review_gate,
    REVENUE_STATES,
    withholding_basis_below_floor,
    withholding_basis_publishable,
)
from analysis.revenue_view import (
    large_unsourced_deposits,
    unestablished_zelle_figures,
    withholding_basis_unestablished,
    WITHHOLDING_BASIS_UNESTABLISHED,
)
from analysis.served_view import zelle_setting
from analysis.zelle_view import ZELLE_DEPOSITS_KEY


#: The job statuses a package counts as pending, not failed (an error, an interrupted run or a job done without an
#: analysis stays failed).
_PENDING_JOB_STATUSES = frozenset({"queued", "processing"})


def package_analysis(jobs: Iterable[JobLike], *, settings: dict | None = None) -> dict:
    # The one settings snapshot this package is built on: its members are displayed with it, and its flag roll-up
    # keeps the groups it ticks.
    if settings is None:
        settings = dict(SETTINGS_DEFAULTS)
    shown_groups = enabled_group_keys(settings)
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
        job, account_index = member.job, member.key.account_index
        statement = member.account.get("statement") or {}
        metrics = member.account.get("metrics") or {}
        quality = member.account.get("quality") or {}
        integrity = member.account.get("integrity") or {}
        detection = member.account.get("detection") or {}
        corporate_use = quality.get("corporate_use") or ""
        integrity_risk = integrity.get("risk_level") or ""
        # `totals["documents"]` counts JOBS and the counters below count
        # MEMBERS, which are the same number until a document publishes two
        # accounts and different on purpose after that: a package sums, counts
        # and days-weights ACCOUNTS, and one document contributing two of them
        # is two contributions.
        ready = member.ready

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
        elif job.status in _PENDING_JOB_STATUSES:
            # A job still queued or processing has not failed; it is pending, a key the package publishes only when
            # one is, so a package without one is unchanged.
            totals["pending"] = totals.get("pending", 0) + 1
        else:
            totals["failed"] += 1
        if corporate_use == "approved":
            totals["approved"] += 1
        elif corporate_use == "summary_only":
            totals["summary_only"] += 1
        elif corporate_use:
            totals["manual_review"] += 1
        if integrity_risk == "high":
            totals["integrity_high"] += 1
        elif integrity_risk == "review":
            totals["integrity_review"] += 1

        credits = num(metrics.get("effective_total_deposits"))
        debits = num(metrics.get("effective_total_withdrawals"))
        cash_flow = num(metrics.get("cash_flow"))
        # R-d, at the one layer that can see two of a document's ledgers at
        # once. A movement between two accounts of ONE document is one
        # movement; a package that sums both accounts counts the same money as
        # a deposit AND as a withdrawal, and every derivation built on those —
        # gross deposits, deposit counts, revenue, the withholding denominator,
        # the flattened ledger — carries the double.
        #
        # Excluded by INDEX, from the document's own `internal_transfers`, and
        # only where the paper printed an internal designation on a leg: the
        # rule that produced these indices refused four of the archive's
        # forty-seven candidate pairs for want of one.
        #
        # BOTH LEGS STAY IN THEIR LEDGERS. Nothing here touches `statement`,
        # the account's reconciliation or its ADB — the money really was in
        # that account on that day, and removing it would break the account's
        # own arithmetic. What is excluded is this member's CONTRIBUTION to a
        # cross-account total.
        raw_transactions = statement.get("transactions") or []
        # The package passes' overlay, on NEW copies of the rows they matched or annotated (the displayed copy and
        # the stored job are never touched), before R-d's positions are left out, so every reader below sees it: the
        # tiers and their reasons, the revenue rows and evidence, the member's gate, the ledger and the document
        # row.
        member_overlay = package_matched.overlays.get(member.key) or {}
        if member_overlay:
            raw_transactions = [overlaid_row(transaction, member_overlay, position)
                                for position, transaction in enumerate(raw_transactions)]
        excluded_positions = member.internal_transfer_positions
        statement_transactions = [
            transaction
            for position, transaction in enumerate(raw_transactions)
            if isinstance(transaction, dict) and position not in excluded_positions
        ]
        excluded_credits = excluded_debits = 0.0
        excluded_credit_count = 0
        if excluded_positions:
            excluded_rows = [
                raw_transactions[position] for position in sorted(excluded_positions)
                if position < len(raw_transactions)
                and isinstance(raw_transactions[position], dict)
            ]
            excluded_credits = round(
                sum(num(row.get("amount")) for row in excluded_rows
                    if num(row.get("amount")) > 0), 2)
            excluded_credit_count = sum(1 for row in excluded_rows if num(row.get("amount")) > 0)
            excluded_debits = round(
                sum(abs(num(row.get("amount"))) for row in excluded_rows
                    if num(row.get("amount")) < 0), 2)
            # The account's own `effective_total_*` are the figures the BANK
            # stated for that account, and the bank counted the transfer. The
            # deduction is arithmetic over rows this package already holds, and
            # `cash_flow` is recomputed from the two adjusted sides rather than
            # adjusted twice: a pair removes a credit from one member and the
            # matching debit from another, so a package's cash flow is
            # unchanged by construction, which is the point.
            credits = round(credits - excluded_credits, 2)
            debits = round(debits - excluded_debits, 2)
            cash_flow = round(credits - debits, 2)
        # The Monthly Statements table's "Deposits Per Month": the count that pairs with `credits`, less the
        # transfers removed above. It pairs when the total IS the rows' total, when the bank printed its own
        # count beside its total, or when the captured rows add up to the bank's total exactly. Otherwise (a
        # parser that read the bank's total but not its count, and captured rows that fall short) the count
        # would describe other money: None, shown as N/A.
        deposit_total = num(metrics.get("effective_total_deposits"), float("nan"))
        line_item_total = num(metrics.get("total_deposits"), float("nan"))
        count_pairs = (
            str(metrics.get("deposits_source") or "line_items") == "line_items"
            or is_count(statement.get("stated_credit_count"))
            or abs(line_item_total - deposit_total) < 0.005
        )
        stated_deposit_count = metrics.get("effective_num_deposits")
        deposit_count = (
            max(stated_deposit_count - excluded_credit_count, 0)
            if count_pairs and is_count(stated_deposit_count)
            else None
        )
        authoritative_rows = [
            transaction
            for transaction in statement_transactions
            if isinstance(transaction.get("classification"), dict)
        ]
        # Paid to lenders reads the lender-total flag; the withholding numerator reads the withholding flag, which
        # also holds the funder payments returned unpaid.
        lender = member_lender(authoritative_rows)
        flagged_rows = [
            transaction
            for transaction in authoritative_rows
            if counts_as_flagged(transaction["classification"], shown_groups)
        ]
        positive_statement_rows = [
            transaction
            for transaction in statement_transactions
            if num(transaction.get("amount")) > 0
        ]
        classified_positive_rows = [
            transaction
            for transaction in positive_statement_rows
            if isinstance(transaction.get("classification"), dict)
        ]
        posted_credit_rows = [
            transaction
            for transaction in classified_positive_rows
            if transaction["classification"].get("is_posted") is not False
        ]
        revenue_rows_are_authoritative = (
            bool(authoritative_rows)
            and len(classified_positive_rows) == len(positive_statement_rows)
            and all(
                transaction["classification"].get("is_posted") is False
                or transaction["classification"].get("revenue_classification")
                in REVENUE_STATES
                for transaction in classified_positive_rows
            )
        )
        # Monthly Statements' True deposits (the verified revenue) stand for this member only when every captured
        # credit carries its revenue state AND the captured credits are the money its Total counts: the line items are
        # the Total's source, or they add up to the bank's own total. Otherwise the verified figure is a part of an
        # unknown whole (a summary-only statement, a partly classified one, a payload from before classification
        # records, a failed member), and the table says N/A rather than show it as the month's revenue. A member
        # that captured no credit and whose Total is zero took in nothing, and its True deposits are zero.
        verified_revenue_established = ready and (
            (
                revenue_rows_are_authoritative
                and (
                    str(metrics.get("deposits_source") or "line_items") == "line_items"
                    or abs(line_item_total - deposit_total) < 0.005
                )
            )
            or (bool(statement) and not positive_statement_rows and credits == 0)
        )
        # §9.2, §10.4: True revenue is established when the verified figure is and every posted credit carries a
        # tier; a payload analysed before 5.6 carries none (§12). The one helper the package passes read too
        # (`member_tiered`).
        tiered = member_tiered(statement_transactions)
        revenue_established = verified_revenue_established and (tiered or not posted_credit_rows)
        revenue = member_revenue(statement_transactions, tiered=tiered)
        tier_rows = {
            tier: revenue.tiers[tier].records for tier in ("verified", "counted_flagged", "excluded_pending_review")
        } if tiered else {}
        tier_totals = {tier: revenue.tiers[tier].total for tier in tier_rows}
        member_by_reason = revenue.by_reason
        # §9.2: the non-revenue breakdown, the rebuild's rule (a non_revenue row that carries a code
        # REVENUE_TIER_REASONS files under non_revenue), from the member's rows when it has them (the rows
        # `non_revenue_total` reads, its internal-transfer pairs left out), else from its stored metrics.
        if not authoritative_rows and isinstance(metrics.get("non_revenue_by_reason"), dict):
            for reason, figures in metrics["non_revenue_by_reason"].items():
                if non_revenue_reason(reason) and isinstance(figures, dict):
                    member_by_reason["non_revenue"][reason] = {
                        "count": int(num(figures.get("count"))), "total": round(num(figures.get("total")), 2)}
        member_by_reason["non_revenue"] = dict(sorted(member_by_reason["non_revenue"].items()))
        # T7, §10.7: only an undecided direction conflict gates, as the rebuild counts it
        # (analysis/revenue.py); a confirmed or rejected one no longer does.
        direction_conflict = any(
            row["classification"].get("revenue_match_method") == "direction_conflict"
            and row["classification"].get("revenue_review_status") == "pending"
            for row in posted_credit_rows
        )
        if authoritative_rows:
            lender_debits, lender_debit_count = lender.paid.total, lender.paid.count
            withholding_numerator = lender.withholding.total
            returned_funder_payment_total, returned_funder_payment_count = lender.returned.total, lender.returned.count
            lump_sum_payoff_total, lump_sum_payoff_count = lender.payoff.total, lender.payoff.count
            potential_lender_debit_total, potential_lender_debit_count = lender.potential.total, lender.potential.count
            insurance_total, insurance_count = lender.insurance.total, lender.insurance.count
        else:
            # Compatibility for already-completed in-memory jobs created before classification records were added.
            # New reports always take the path above. Paid to lenders is the stored lender_debits, and the numerator
            # the stored withholding_numerator, falling back to it.
            lender_debits = num(metrics.get("lender_debits"), num(metrics.get("withholding_numerator")))
            lender_debit_count = int(num(metrics.get("lender_debit_count"), 0.0))
            withholding_numerator = num(metrics.get("withholding_numerator"), lender_debits)
            returned_funder_payment_total = num(metrics.get("returned_funder_payment_total"))
            returned_funder_payment_count = int(num(metrics.get("returned_funder_payment_count"), 0.0))
            lump_sum_payoff_total = num(metrics.get("lump_sum_payoff_total"))
            lump_sum_payoff_count = int(num(metrics.get("lump_sum_payoff_count"), 0.0))
            potential_lender_debit_total = num(
                metrics.get("potential_lender_debit_total"),
                num(metrics.get("potential_lender_debits")),
            )
            potential_lender_debit_count = int(
                num(metrics.get("potential_lender_debit_count"), 0.0)
            )
            insurance_count = int(num(metrics.get("insurance_count"), 0.0))
            insurance_total = num(metrics.get("insurance_total"))
        if authoritative_rows:
            # A partially classified new report fails reconciliation closed: every positive row stays on the
            # posted-credit side of the equation, and only the credits that name a state fill the state figures.
            posted_credit_total, posted_credit_count = revenue.posted.total, revenue.posted.count
            revenue_totals = {state: bucket.total for state, bucket in revenue.states.items()}
            revenue_counts = {state: bucket.count for state, bucket in revenue.states.items()}
        else:
            posted_credit_total = num(metrics.get("total_posted_credits"), credits)
            posted_credit_count = int(
                num(metrics.get("total_posted_credit_count"), metrics.get("effective_num_deposits") or 0)
            )
            # §9.2: `true_revenue` is True revenue now, never a verified figure. Without either verified key the
            # member's verified figure is not established: None, shown as N/A, never 0.0. A member that captured no
            # credit and whose Total is zero took in nothing, and is established at zero.
            verified_fallback = num(
                metrics.get("verified_revenue_total"),
                num(metrics.get("confirmed_true_revenue_total"), float("nan")),
            )
            if not isfinite(verified_fallback):
                verified_fallback = 0.0 if verified_revenue_established else None
            revenue_totals = {
                "verified_revenue": verified_fallback,
                "unverified_deposit": num(
                    metrics.get("unverified_deposit_total"),
                    num(metrics.get("potential_revenue_total")),
                ),
                "non_revenue": num(metrics.get("non_revenue_total")),
            }
            revenue_counts = {
                "verified_revenue": int(
                    num(
                        metrics.get("verified_revenue_count"),
                        num(metrics.get("confirmed_true_revenue_count")),
                    )
                ),
                "unverified_deposit": int(
                    num(
                        metrics.get("unverified_deposit_count"),
                        num(metrics.get("potential_revenue_count")),
                    )
                ),
                "non_revenue": int(num(metrics.get("non_revenue_count"))),
            }
        # §9.2: without a stored denominator, the legacy eligible deposits (never `true_revenue`).
        eligible_deposits = num(
            metrics.get("withholding_denominator"),
            num(metrics.get("legacy_eligible_deposits"), credits),
        )
        # The member's stored basis, before R-d's, the counted-pair and the moved-credit deductions below; its row's
        # rate and exposure are recomputed only where the basis it prints moved from it.
        stored_eligible_deposits = eligible_deposits
        denominator_mode = normalize_withholding_denominator_mode(
            metrics.get("withholding_denominator_mode")
        )
        if excluded_credits and denominator_mode == "legacy_eligible_deposits":
            # The legacy denominator is `effective_total_deposits` less the
            # LENDER credits, so an internal transfer is still inside it and has
            # to come out — a withholding rate whose denominator counts the
            # member's own money twice under-states the exposure.
            #
            # The verified-revenue mode needs no deduction and must not get
            # one: an internal-transfer credit is already `non_revenue` by
            # `analysis/transaction_classifier.py`'s own vocabulary, so
            # `verified_revenue_total` never carried it and subtracting again
            # would remove money the denominator never held.
            eligible_deposits = round(max(eligible_deposits - excluded_credits, 0.0), 2)
        elif excluded_positions and denominator_mode == "true_revenue":
            # §11: an R-d pair can hold a credit this member counted (a named transfer between two members), so the
            # True-revenue denominator loses the pair's credits that it holds: verified or counted, and only those.
            counted_transfer_credits = round(sum(
                num(raw_transactions[position].get("amount"))
                for position in excluded_positions
                if position < len(raw_transactions) and isinstance(raw_transactions[position], dict)
                and num(raw_transactions[position].get("amount")) > 0
                and ((raw_transactions[position].get("classification") or {}).get("revenue_tier")
                     in ("verified", "counted_flagged"))
            ), 2)
            eligible_deposits = round(max(eligible_deposits - counted_transfer_credits, 0.0), 2)
        # §11: a deposit the package passes took out of True leaves a revenue basis it was in: the True-revenue mode
        # loses the moved credits stored verified or counted, the Verified mode those stored as verified revenue; the
        # legacy basis and the numerator are untouched. Pass 2's held deposits (stored counted) are moved credits too;
        # its annotated held deposits never are.
        moved_credits = package_matched.moved.get(member.key) or []
        if moved_credits and denominator_mode in ("true_revenue", "verified_revenue"):
            moved_total = round(sum(
                item["amount"] for item in moved_credits
                if (item["tier"] in ("verified", "counted_flagged") if denominator_mode == "true_revenue"
                    else item["state"] == "verified_revenue")
            ), 2)
            eligible_deposits = round(max(eligible_deposits - moved_total, 0.0), 2)
        # Only a member with an analysis contributes a basis, so a failed member never turns a True-revenue package
        # "mixed".
        if ready:
            denominator_modes.add(str(denominator_mode))
            withholding_basis_by_member.append({
                "source_job": job.id, **({"account_index": account_index} if account_index is not None else {}),
                "mode": str(denominator_mode), "label": WITHHOLDING_BASIS_LABELS.get(str(denominator_mode), ""),
            })
        nsf_count = int(num(metrics.get("effective_nsf_count"), 0.0))
        nsf_source = metrics.get("nsf_source")
        if isinstance(nsf_source, str):
            nsf_sources.add(nsf_source)  # a member with no analysis contributes no count and no basis
        # The days that count names (analysis/nsf_days.py), for the dashboard's NSFs chip over the combined ledger:
        # each is shown by this member's row that ended it. Display only; no figure reads it.
        nsf_days = metrics.get("nsf_days") if isinstance(metrics.get("nsf_days"), list) else []
        adb_calendar_days = metrics.get("calendar_day_count")
        average_daily_balance_num = num(
            metrics.get("average_daily_balance"),
            default=float("nan"),
        )
        adb_validated = (
            metrics.get("adb_ok") is True
            and isfinite(average_daily_balance_num)
            and isinstance(adb_calendar_days, int)
            and not isinstance(adb_calendar_days, bool)
            and adb_calendar_days > 0
        )
        average_daily_balance = (
            metrics.get("average_daily_balance") if adb_validated else None
        )

        totals["total_credits"] = round(totals["total_credits"] + credits, 2)
        totals["total_posted_credits"] = round(
            totals["total_posted_credits"] + posted_credit_total,
            2,
        )
        totals["total_posted_credit_count"] += posted_credit_count
        # A member without a verified figure (None) adds nothing; the total is N/A with it below (§10.4).
        totals["verified_revenue_total"] = round(
            totals["verified_revenue_total"] + num(revenue_totals["verified_revenue"]),
            2,
        )
        totals["verified_revenue_count"] += revenue_counts["verified_revenue"]
        totals["unverified_deposit_total"] = round(
            totals["unverified_deposit_total"]
            + revenue_totals["unverified_deposit"],
            2,
        )
        totals["unverified_deposit_count"] += revenue_counts["unverified_deposit"]
        totals["confirmed_true_revenue_total"] = totals["verified_revenue_total"]
        totals["confirmed_true_revenue"] = totals["verified_revenue_total"]
        totals["confirmed_true_revenue_count"] = totals["verified_revenue_count"]
        totals["potential_revenue_total"] = totals["unverified_deposit_total"]
        totals["potential_revenue_count"] = totals["unverified_deposit_count"]
        totals["non_revenue_total"] = round(
            totals["non_revenue_total"] + revenue_totals["non_revenue"],
            2,
        )
        totals["non_revenue_count"] += revenue_counts["non_revenue"]
        # The non-revenue breakdown beside it, never gated on the member's revenue being established.
        for reason, slot in member_by_reason["non_revenue"].items():
            item = package_by_reason["non_revenue"].setdefault(reason, {"count": 0, "total": 0.0})
            item["count"] += slot["count"]
            item["total"] = round(item["total"] + slot["total"], 2)
        # The member's Zelle figures (its served metrics.zelle_deposits). Under No, a member that carries none
        # contributes its excluded Zelle deposits as its non-revenue part, so the package figure covers every member.
        member_zelle = metrics.get(ZELLE_DEPOSITS_KEY) if isinstance(metrics.get(ZELLE_DEPOSITS_KEY), dict) else None
        if member_zelle is not None:
            package_zelle["carried"] = True
            package_zelle["setting_applied"] = package_zelle["setting_applied"] and (
                member_zelle.get("setting_applied") is not False)
            # The member's own reading, as its statement serves it.
            package_zelle["counted"] = package_zelle["counted"] and member_zelle.get("counted_as_true_revenue") is True
            parts = member_zelle.get("by_tier") if isinstance(member_zelle.get("by_tier"), dict) else {}
        elif not zelle_counted and member_by_reason["non_revenue"].get("zelle_excluded"):
            package_zelle["counted"] = False  # Its Zelle deposits are excluded
            parts = {"non_revenue": member_by_reason["non_revenue"]["zelle_excluded"]}
        else:
            parts = {}
        for tier, slot in parts.items():
            if not isinstance(slot, dict):
                continue
            item = package_zelle["by_tier"].setdefault(tier, {"count": 0, "total": 0.0})
            item["count"] += int(num(slot.get("count")))
            item["total"] = round(item["total"] + num(slot.get("total")), 2)
            package_zelle["count"] += int(num(slot.get("count")))
            package_zelle["total"] = round(package_zelle["total"] + num(slot.get("total")), 2)
        if ready and not verified_revenue_established:
            unestablished_verified.append(member.key.id)
        if ready and not revenue_established:
            unestablished_revenue.append(member.key.id)
        # §9.2, §11: the member's own basis is not established (its served copy already says so, or the package's reading
        # of its rows does); its row publishes no rate and its potential lenders no exposure, as the statement viewed
        # alone (analysis/revenue_view.py).
        member_basis_unestablished = metrics.get(WITHHOLDING_BASIS_UNESTABLISHED) is True or (
            ready and withholding_basis_unestablished(denominator_mode, verified_established=verified_revenue_established,
                                                      established=revenue_established))
        if ready and (
            (denominator_mode == "true_revenue" and not revenue_established)
            or (denominator_mode == "verified_revenue" and not verified_revenue_established)
        ):
            partial_revenue_denominator = True
        member_reconciles = round(sum(num(total) for total in revenue_totals.values()), 2) == posted_credit_total
        if tiered:
            # T7 over the package's member rows, which leave out R-d's internal-transfer pairs (`excluded_positions`
            # above), so a held pair credit is neither held nor posted here. The pairing proves the money is the
            # holder's own, moving between two of its accounts: it is no revenue awaiting review, and its share must
            # not gate the package. The statement's own gate (analysis/revenue.py) cannot see the sibling account's
            # debit and counts it.
            member_gated = revenue_review_gate(
                direction_conflict=direction_conflict,
                held_total=tier_totals["excluded_pending_review"],
                posted_total=posted_credit_total,
                tiers_sum_to_posted=member_reconciles,
                true_total=round(tier_totals["verified"] + tier_totals["counted_flagged"], 2),
            )
            if ready:
                # The very figures the member's gate reads (R-d's pairs already out), for T7 on the package's sums.
                slot = package_gate_cents.setdefault(statement_currency, [0, 0, 0])
                slot[0] += round(tier_totals["excluded_pending_review"] * 100)
                slot[1] += round(posted_credit_total * 100)
                slot[2] += round((tier_totals["verified"] + tier_totals["counted_flagged"]) * 100)
            totals["true_revenue_total"] = round(
                totals["true_revenue_total"] + tier_totals["verified"] + tier_totals["counted_flagged"], 2
            )
            totals["true_revenue_count"] += len(tier_rows["verified"]) + len(tier_rows["counted_flagged"])
            totals["counted_flagged_total"] = round(totals["counted_flagged_total"] + tier_totals["counted_flagged"], 2)
            totals["counted_flagged_count"] += len(tier_rows["counted_flagged"])
            totals["excluded_pending_review_total"] = round(
                totals["excluded_pending_review_total"] + tier_totals["excluded_pending_review"], 2
            )
            totals["excluded_pending_review_count"] += len(tier_rows["excluded_pending_review"])
            totals["revenue_review_items"] += len(tier_rows["excluded_pending_review"])
            for tier in ("counted_flagged", "excluded_pending_review"):
                for reason, slot in member_by_reason[tier].items():
                    item = package_by_reason[tier].setdefault(reason, {"count": 0, "total": 0.0})
                    item["count"] += slot["count"]
                    item["total"] = round(item["total"] + slot["total"], 2)
        else:
            # §12: a member analysed before 5.6 is gated by the rule it was analysed under.
            member_gated = (
                any(row["classification"].get("revenue_classification") == "unverified_deposit"
                    and row["classification"].get("revenue_review_status") == "pending"
                    for row in posted_credit_rows)
                or direction_conflict
                or not member_reconciles
            )
        any_member_gated = any_member_gated or (ready and member_gated)
        totals["total_debits"] = round(totals["total_debits"] + debits, 2)
        totals["cash_flow"] = round(totals["cash_flow"] + cash_flow, 2)
        totals["lender_debits"] = round(totals["lender_debits"] + lender_debits, 2)
        totals["lender_debit_count"] += lender_debit_count
        totals["returned_funder_payment_total"] = round(
            totals["returned_funder_payment_total"] + returned_funder_payment_total, 2
        )
        totals["returned_funder_payment_count"] += returned_funder_payment_count
        package_lump_sum["count"] += lump_sum_payoff_count
        package_lump_sum["total"] = round(package_lump_sum["total"] + lump_sum_payoff_total, 2)
        totals["potential_lender_debit_total"] = round(
            totals["potential_lender_debit_total"] + potential_lender_debit_total,
            2,
        )
        totals["potential_lender_debits"] = totals["potential_lender_debit_total"]
        totals["potential_lender_debit_count"] += potential_lender_debit_count
        totals["insurance_count"] += insurance_count
        totals["insurance_total"] = round(totals["insurance_total"] + insurance_total, 2)
        # The members' numerators, paid plus returned, never the paid figure alone.
        totals["withholding_numerator"] = round(totals["withholding_numerator"] + withholding_numerator, 2)
        totals["potential_withholding_numerator"] = totals["potential_lender_debit_total"]
        totals["withholding_denominator"] = round(
            totals["withholding_denominator"] + eligible_deposits,
            2,
        )
        totals["potential_withholding_denominator"] = totals["withholding_denominator"]
        totals["nsf_count"] += nsf_count

        for match in detection.get("known_funders") or []:
            name = match.get("funder") or "Unknown"
            item = funders.setdefault(
                name,
                {"funder": name, "documents": 0, "total_debited": 0.0, "returned_payment_count": 0,
                 "returned_payment_total": 0.0},
            )
            item["documents"] += 1
            match_debit_count = int(
                num(match.get("debit_count"), len(match.get("transactions") or []))
            )
            # A funder whose every payment bounced publishes debit_count 0, and is listed with it.
            if match_debit_count or "debit_count" in match:
                item["debit_count"] = item.get("debit_count", 0) + match_debit_count
            item["total_debited"] = round(item["total_debited"] + num(match.get("total_debited")), 2)
            item["returned_payment_count"] += int(num(match.get("returned_payment_count"), 0.0))
            item["returned_payment_total"] = round(
                item["returned_payment_total"] + num(match.get("returned_payment_total")), 2
            )
            package_funder_matches.append(
                {
                    "funder": name,
                    "source_job": job.id,
                    "transactions": match.get("transactions") or [],
                    "evidence": match.get("evidence") or [],
                }
            )
        # The warning's items, each naming its statement, its account (a statement of several) and its unit, as an
        # evidence record does.
        for returned_item in detection.get("returned_funder_payments") or []:
            if isinstance(returned_item, dict):
                package_returned_funder_payments.append({
                    **returned_item, "source_job": job.id, "source_document": job.filename,
                    "source_currency": statement_currency,
                    **({"source_account": account_index} if account_index is not None else {}),
                    # A payment the funder re-debited in the next statement.
                    **package_matched.represented.get((member.key, returned_item.get("debit_location")), {}),
                })
        # §9.2, §17.1: a ready, tiered member whose revenue is established lists its large unsourced deposits as the
        # package counts its rows (R-d's pairs left out, the package passes' holds applied, so a deposit the package holds
        # as an own-account transfer is not listed), each share of the member's True as the package counts it (its
        # row's `true_revenue_total` below); read by no figure, gate or decision.
        if ready and tiered and revenue_established:
            for large_item in large_unsourced_deposits(
                    tier_rows["counted_flagged"], round(tier_totals["verified"] + tier_totals["counted_flagged"], 2)):
                package_large_unsourced_deposits.append({
                    **large_item, "source_job": job.id, "source_document": job.filename,
                    **({"source_account": account_index} if account_index is not None else {}),
                    "source_currency": statement_currency,
                })
        # The member's lump-sum payoffs, each naming its statement, its account (a statement of several) and its unit; a
        # payment the package's pass 4 matched to a return in the next statement is out of paid there and no lump sum
        # (its overlay row says so).
        paid_lump_sums = {row["classification"].get("source_location") for row in lender.payoff.records}
        for lump_sum_item in detection.get("lump_sum_payoffs") or []:
            if isinstance(lump_sum_item, dict) and (not authoritative_rows
                                                    or lump_sum_item.get("location") in paid_lump_sums):
                package_lump_sum_payoffs.append({
                    **lump_sum_item, "source_job": job.id, "source_document": job.filename,
                    "source_currency": statement_currency,
                    **({"source_account": account_index} if account_index is not None else {}),
                })

        potential_matches_by_entity = {
            match.get("funder") or "Unknown candidate": match
            for match in detection.get("potential_lenders") or []
        }
        potential_rows_by_entity: dict[str, list[dict]] = {}
        for row in lender.potential.records:
            classification = row["classification"]
            name = (classification.get("potential_payee_label") or classification.get("canonical_entity")
                    or "Unknown candidate")
            potential_rows_by_entity.setdefault(name, []).append(row)

        for name in sorted(set(potential_matches_by_entity) | set(potential_rows_by_entity)):
            match = potential_matches_by_entity.get(name) or {}
            entity_rows = potential_rows_by_entity.get(name) or []
            if entity_rows:
                match_count = len(entity_rows)
                match_total = round(
                    sum(abs(num(row.get("amount"))) for row in entity_rows),
                    2,
                )
                match_transactions = entity_rows
                match_evidence = [row["classification"] for row in entity_rows]
            else:
                match_count = int(
                    num(
                        match.get("potential_lender_debit_count"),
                        num(match.get("debit_count"), len(match.get("transactions") or [])),
                    )
                )
                match_total = num(
                    match.get("potential_lender_debit_total"),
                    num(match.get("total_debited")),
                )
                match_transactions = match.get("transactions") or []
                match_evidence = match.get("evidence") or []
            # Published only over a basis the member row publishes a rate on (the floor's helper in place of
            # `eligible_deposits > 0`), never where F1 refuses the member's basis.
            match_exposure = (
                abs(match_total) / eligible_deposits * 100
                if withholding_basis_publishable(eligible_deposits, denominator_mode) and not member_basis_unestablished
                else None
            )
            item = potential_lenders.setdefault(
                name,
                {
                    "funder": name,
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
            item["debit_count"] += match_count
            item["potential_lender_debit_count"] = item["debit_count"]
            item["total_debited"] = round(item["total_debited"] + match_total, 2)
            item["potential_lender_debit_total"] = item["total_debited"]
            package_potential_matches.append(
                {
                    "funder": name,
                    "source_job": job.id,
                    "debit_count": match_count,
                    "potential_lender_debit_count": match_count,
                    "total_debited": round(match_total, 2),
                    "potential_lender_debit_total": round(match_total, 2),
                    # F1: no basis where the member's is not established. Nor under the withholding basis floor,
                    # as the statement's own row reads.
                    "eligible_deposit_denominator": (
                        None if member_basis_unestablished
                        or withholding_basis_below_floor(eligible_deposits, denominator_mode)
                        else eligible_deposits),
                    "potential_withholding_exposure": match_exposure,
                    "transactions": match_transactions,
                    "evidence": match_evidence,
                    "status": "review_required",
                }
            )

        for match in detection.get("insurance_providers") or []:
            name = match.get("provider") or "Insurance provider not identified"
            item = insurance_providers.setdefault(
                name,
                {"provider": name, "documents": 0, "count": 0, "total_debited": 0.0},
            )
            item["documents"] += 1
            item["count"] += int(num(match.get("count"), 0.0))
            item["total_debited"] = round(
                item["total_debited"] + num(match.get("total_debited")),
                2,
            )
            package_insurance_matches.append(
                {
                    "provider": name,
                    "source_job": job.id,
                    "transactions": match.get("transactions") or [],
                    "evidence": match.get("evidence") or [],
                }
            )

        # Flag groups (lender detection §8.3): the ticked groups' counted rows of this member's ledger, less its
        # internal-transfer legs. They never reach the lender totals, the withholding or the decision (D7).
        add_flagged_rows(flagged_rollup, flagged_rows)

        # Flattened ledger so the dashboard can show every statement's rows at once.
        for tx in statement_transactions:
            package_transaction = {
                **tx,
                "source_job": job.id,
                "source_document": job.filename,
                "source_bank": statement.get("bank"),
                # The combined ledger shows rows from every member at once, so
                # each row has to carry its own denomination — a package-wide
                # currency would mislabel every row of a mixed package.
                "source_currency": statement_currency,
                "source_period_start": statement.get("period_start"),
                "source_period_end": statement.get("period_end"),
            }
            if account_index is not None:
                # A row of one account of a multi-account document: its location is numbered within that account,
                # so a review of it names the account (1-based, printed order). Other rows carry no such key.
                package_transaction["source_account"] = account_index
            package_transactions.append(package_transaction)
            classification = tx.get("classification") or {}
            evidence = {
                **classification,
                "source_job": job.id,
                "source_document": job.filename,
            }
            # The withholding rows, and a returned funder payment its funder re-debited, which left the rate but is
            # still a lender row, and a paid lump-sum payoff, in paid to lenders and out of the rate.
            if (classification.get("contributes_to_withholding_rate") is True
                    or classification.get("returned_funder_payment_by")
                    or (classification.get("lump_sum_payoff")
                        and classification.get("contributes_to_lender_totals") is True)):
                package_lender_evidence.append(evidence)
            if contributes_to_potential_totals(classification):
                package_potential_lender_evidence.append(evidence)
            if classification.get("contributes_to_insurance_totals") is True:
                package_insurance_evidence.append(evidence)
            if counts_as_flagged(classification, shown_groups):
                # A location is numbered within its own account, so a multi-account member's evidence names it.
                package_flagged_evidence.append(
                    evidence if account_index is None else {**evidence, "source_account": account_index}
                )
            revenue_state = classification.get("revenue_classification")
            if revenue_state in REVENUE_STATES and num(tx.get("amount")) > 0:
                # A revenue evidence record names its unit and its account, so a mixed-currency or multi-account
                # package's evidence can be read without a join (None: one account, no currency).
                revenue_evidence = {**evidence, "source_currency": statement_currency, "source_account": account_index}
                package_revenue_evidence[revenue_state].append(revenue_evidence)
                if classification.get("revenue_tier") in package_tier_evidence:
                    package_tier_evidence[classification["revenue_tier"]].append(revenue_evidence)

        # §9.2, §10.4: the row's True, Counted and Held figures follow `revenue_established`, as the package's do. A
        # member with no captured credit and a zero Total is established at zero and holds no tier row.
        row_tier_totals = {tier: tier_totals.get(tier, 0.0) for tier in ("verified", "counted_flagged",
                                                                         "excluded_pending_review")}
        row_tier_counts = {tier: len(tier_rows.get(tier, [])) for tier in row_tier_totals}

        # True revenue spec §9.2: a member row divides by the basis it prints. Where the package moved the member's
        # basis (R-d's internal-transfer deduction, the 5.6 counted-pair deduction, the package passes' moved credits),
        # its rate and potential exposure are its own numerators over that basis; elsewhere they are the stored figures,
        # as before. Neither is published under the basis floor (`withholding_basis_publishable`) or where F1 refuses
        # the member's basis. The package can move the NUMERATOR without the basis too (pass 5's cross-statement
        # re-debit, takes a returned payment out of it; pass 4's returned payoff, with Q5, puts one back), so each
        # figure is its own numerator over the row's basis wherever that numerator or the basis moved from the stored
        # figures; the N/A rules above are unchanged.
        member_rate_published = (
            withholding_basis_publishable(eligible_deposits, denominator_mode) and not member_basis_unestablished)
        basis_moved = round(eligible_deposits, 2) != round(stored_eligible_deposits, 2)
        stored_numerator = num(metrics.get("withholding_numerator"), float("nan"))
        stored_potential_numerator = num(metrics.get("potential_withholding_numerator"),
                                         num(metrics.get("potential_lender_debit_total"), float("nan")))
        if basis_moved or (isfinite(stored_numerator)
                           and round(withholding_numerator, 2) != round(stored_numerator, 2)):
            member_withholding_rate = (
                abs(withholding_numerator) / eligible_deposits * 100 if member_rate_published else None)
        else:
            member_withholding_rate = metrics.get("withholding_rate") if member_rate_published else None
        if basis_moved or (isfinite(stored_potential_numerator)
                           and round(potential_lender_debit_total, 2) != round(stored_potential_numerator, 2)):
            member_potential_exposure = (
                abs(potential_lender_debit_total) / eligible_deposits * 100 if member_rate_published else None)
        else:
            member_potential_exposure = metrics.get("potential_withholding_exposure") if member_rate_published else None
        doc_row = {
            # One row per MEMBER. An account of a multi-account document is
            # named by the document it came from plus its printed position —
            # never by the document alone, which would give two members one id
            # and let the second overwrite the first everywhere a package row
            # is looked up by id.
            "id": member.key.id,
            "filename": job.filename,
            "status": job.status,
            # D-3: the content identity of this member. A member never repeats
            # another; a repeated statement is left out and listed with its own
            # row (`duplicate_row`).
            "content_sha256": getattr(job, "content_sha256", None),
            "is_duplicate": False,
            "duplicate_of": None,
            "analysis_error": job.analysis_error,
            "error": job.error,
            "bank": statement.get("bank"),
            "account": statement.get("account_number"),
            # CURRENCY DOCTRINE §D/§F: this row's figures are all in one
            # currency and stay denominated even when the package refuses to
            # combine them with another member's.
            "currency": statement_currency,
            "period_start": statement.get("period_start"),
            "period_end": statement.get("period_end"),
            "beginning_balance": statement.get("beginning_balance"),
            "ending_balance": statement.get("ending_balance"),
            "min_balance": metrics.get("min_balance"),
            "max_balance": metrics.get("max_balance"),
            "daily_balance_extrema_validated": adb_validated,
            "quality": quality.get("level"),
            "corporate_use": corporate_use,
            "integrity_risk": integrity_risk,
            "reconciles": (member.account.get("reconciliation") or {}).get("ok"),
            "credits": credits,
            "deposit_count": deposit_count,
            "total_posted_credits": posted_credit_total,
            "total_posted_credit_count": posted_credit_count,
            "verified_revenue_total": revenue_totals["verified_revenue"],
            "verified_revenue_count": revenue_counts["verified_revenue"],
            "verified_revenue_established": verified_revenue_established,
            # §12: its statement was analysed with older classification rules, so re-analysis computes its true
            # revenue (a member not established for another reason, a summary-only one, is not outdated).
            "analysis_rules_outdated": member.analysis_rules_outdated,
            # §9.2: True revenue and its parts; None for a member whose revenue is not established.
            "revenue_established": revenue_established,
            "true_revenue_total": (
                round(row_tier_totals["verified"] + row_tier_totals["counted_flagged"], 2)
                if revenue_established else None
            ),
            "true_revenue_count": (
                row_tier_counts["verified"] + row_tier_counts["counted_flagged"] if revenue_established else None
            ),
            "counted_flagged_total": row_tier_totals["counted_flagged"] if revenue_established else None,
            "counted_flagged_count": row_tier_counts["counted_flagged"] if revenue_established else None,
            "excluded_pending_review_total": (
                row_tier_totals["excluded_pending_review"] if revenue_established else None
            ),
            "excluded_pending_review_count": (
                row_tier_counts["excluded_pending_review"] if revenue_established else None
            ),
            "counted_flagged_by_reason": member_by_reason["counted_flagged"] if revenue_established else None,
            "excluded_pending_review_by_reason": (
                member_by_reason["excluded_pending_review"] if revenue_established else None
            ),
            "revenue_review_required": member_gated,
            "unverified_deposit_total": revenue_totals["unverified_deposit"],
            "unverified_deposit_count": revenue_counts["unverified_deposit"],
            "confirmed_true_revenue_total": revenue_totals["verified_revenue"],
            "confirmed_true_revenue_count": revenue_counts["verified_revenue"],
            "potential_revenue_total": revenue_totals["unverified_deposit"],
            "potential_revenue_count": revenue_counts["unverified_deposit"],
            "non_revenue_total": revenue_totals["non_revenue"],
            "non_revenue_count": revenue_counts["non_revenue"],
            # §9.2: its non-revenue breakdown, kept where its revenue is not established (its rows are known
            # non-revenue, captured rows only).
            "non_revenue_by_reason": member_by_reason["non_revenue"],
            "maximum_revenue": round(
                num(revenue_totals["verified_revenue"])
                + revenue_totals["unverified_deposit"],
                2,
            ),
            # The four-tier identity under its own name; `revenue_reconciles` is its deprecated alias.
            "revenue_tiers_sum_to_posted": member_reconciles,
            "revenue_reconciles": member_reconciles,
            # The statement integrity facts the True card shows.
            "holder_unscreened": metrics.get("holder_unscreened") is True,
            "payer_text_unread": metrics.get("payer_text_unread") is True,
            # A premium trust account, whose deposits that would count are held (a statement fact; no figure reads
            # it).
            "premium_trust_account": metrics.get("premium_trust_account") is True,
            "debits": debits,
            "cash_flow": cash_flow,
            "average_daily_balance": average_daily_balance,
            "adb_calendar_days": adb_calendar_days,
            "adb_validated": adb_validated,
            "nsf_count": nsf_count,
            "nsf_source": nsf_source,
            "nsf_days": nsf_days,
            "lender_debits": lender_debits,
            "lender_debit_count": lender_debit_count,
            # Its funder payments returned unpaid, out of lender_debits.
            "returned_funder_payment_total": returned_funder_payment_total,
            "returned_funder_payment_count": returned_funder_payment_count,
            "lenders_detected": int(num(metrics.get("lenders_detected"), len(detection.get("known_funders") or []))),
            "potential_lenders_detected": int(num(metrics.get("potential_lenders_detected"), len(detection.get("potential_lenders") or []))),
            "potential_lender_debit_count": potential_lender_debit_count,
            "potential_lender_debit_total": potential_lender_debit_total,
            "potential_lender_debits": potential_lender_debit_total,
            "insurance_count": insurance_count,
            "insurance_total": insurance_total,
            # §9.2: set after the loop, from the member's chain (`package_active_positions`); None (N/A) where the
            # lender reading is not available.
            "active_positions": None,
            "possible_positions": None,
            "withholding_rate": member_withholding_rate,
            # Paid lender debits plus returned funder payments.
            "withholding_numerator": withholding_numerator,
            "withholding_denominator": eligible_deposits,
            "withholding_review_required": (
                bool(metrics.get("withholding_review_required")) or eligible_deposits <= 0 or member_basis_unestablished
                # A revenue basis under the floor asks for review, as $0 does.
                or not withholding_basis_publishable(eligible_deposits, denominator_mode)
            ),
            "withholding_denominator_mode": denominator_mode,
            "withholding_denominator_label": metrics.get("withholding_denominator_label") or "Legacy eligible deposits",
            "potential_withholding_exposure": member_potential_exposure,
            "potential_withholding_numerator": potential_lender_debit_total,
            "potential_withholding_denominator": eligible_deposits,
            "potential_withholding_review_required": (
                bool(metrics.get("potential_withholding_review_required"))
                or potential_lender_debit_count > 0
            ),
        }
        if account_index is not None:
            # Only a multi-account document has these to say, so a package of
            # today's payloads carries neither key and is byte-identical.
            doc_row["account_index"] = account_index
            doc_row["account_count"] = member.account_count
        # The member's lump-sum payoffs (in its `lender_debits`, out of its `withholding_numerator`), only where it
        # has one.
        if lump_sum_payoff_count:
            doc_row["lump_sum_payoff_total"] = lump_sum_payoff_total
            doc_row["lump_sum_payoff_count"] = lump_sum_payoff_count
        # §9.2: the member's withholding basis is not established, only where it is; the package goes to review.
        if member_basis_unestablished:
            doc_row[WITHHOLDING_BASIS_UNESTABLISHED] = True
            any_member_basis_unestablished = True
        # The member's Zelle figures, where its served copy carries them (the Monthly cell reads them). §10.4: their
        # parts of True and Held are None where the member's revenue is not established, as the row's tier figures
        # follow its flags; the captured rows' count, total and non-revenue part stay.
        if member_zelle is not None:
            doc_row[ZELLE_DEPOSITS_KEY] = deepcopy(unestablished_zelle_figures(
                member_zelle, established=revenue_established, verified_established=verified_revenue_established))
        # §9.2: the member's rows the package passes matched or annotated, and why the passes could not read it
        # ('no_currency', 'older_rules'), each only where there is one.
        if member_overlay:
            doc_row["package_match_count"] = len(member_overlay)
        if member.key in package_matched.unchecked:
            doc_row["package_match_unchecked"] = package_matched.unchecked[member.key]
        documents.append(doc_row)
        if ready:
            monthly.append(doc_row)
            # The same rows counted as PERIODS rather than as members. Two
            # accounts of one document share a job id and the document's one
            # printed cycle, so they collapse to one; two documents never do,
            # whatever period they print.
            period_keys.add((job.id, statement.get("period_start"),
                             statement.get("period_end")))
            # The calendar month it stands for. Two accounts of one business for one month, uploaded as two
            # files, are one month.
            month_key = statement_month(statement.get("period_start"), statement.get("period_end"))
            if month_key is None:
                months_unplaced += 1
            else:
                month_keys.add(month_key)
            # The days it covers, for its account's month floor below; with what its account is read by
            # (`months_linked`).
            months_members.append({
                "job_id": job.id, "facts": member.facts,
                "days": covered_days(statement.get("period_start"), statement.get("period_end")),
            })
            if (member.account.get("reconciliation") or {}).get("ok") is not True:
                unreconciled_members.append(doc_row["id"])
            if doc_row["holder_unscreened"]:
                holder_unscreened_members.append(doc_row["id"])
            if doc_row["payer_text_unread"]:
                payer_text_unread_members.append(doc_row["id"])
            if doc_row["premium_trust_account"]:
                premium_trust_members.append(doc_row["id"])
            if adb_validated:
                adb_value = Decimal(str(average_daily_balance_num))
                adb_weighted_sum += adb_value * adb_calendar_days
                adb_weight += adb_calendar_days

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
