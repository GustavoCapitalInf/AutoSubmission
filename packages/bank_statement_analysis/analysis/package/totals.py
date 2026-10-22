"""A package's sums, lists and roll-ups (`PackageTotals`): added member after member, then read once every member is
in."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from analysis.metrics import POTENTIAL_WITHHOLDING_FORMULA
from analysis.package.calendar import covered_days, months_covered, statement_month
from analysis.package.figures import add_flagged_rows
from analysis.package.lender import package_active_positions
from analysis.package.model import MemberFigures, MemberKey, months_linked, num, PackagePasses, SelectedPackage
from analysis.revenue import (
    revenue_review_gate,
    REVENUE_STATES,
    withholding_basis_below_floor,
    withholding_basis_publishable,
)
from analysis.revenue_view import unestablished_zelle_figures
from analysis.zelle_view import ZELLE_DEPOSITS_KEY


class PackageTotals:
    """A package's sums, lists and roll-ups, added member by member in the package's order (`add`), and the figures
    read off them once every member is in (`finish`). An ordered builder, not a sum of parts: each accumulator keeps
    the rounding points it had, each list keeps the members' order and each roll-up its first appearance, and `finish`
    changes roll-ups `add` built. `finish` sets the attributes annotated here; the package's publication reads them."""

    lender_payment_changes: list[dict] | None
    lender_payment_unchecked: list[dict]
    active_positions_by_month: list[dict]
    documents_with_several_members: list[str]
    refuse_cross_account_averages: bool
    months: int
    statement_periods: int
    average_daily_balance: float | None
    no_statement_analysed: bool
    denominator_mode: str
    mixed_basis: bool
    basis_below_floor: bool
    withholding_rate: float | None
    withholding_rate_raw: float | None
    withholding_review_required: bool
    potential_withholding: float | None
    potential_withholding_raw: float | None
    potential_withholding_review_required: bool
    left_out_accounts: list[dict]
    decision: str

    def __init__(self, selected: SelectedPackage, *, zelle_counted: bool) -> None:
        self.selected = selected
        self.zelle_counted = zelle_counted
        self.documents = []
        self.monthly = []
        #: `(job, period start, period end)` for every member that contributed — the
        #: honest count of statement PERIODS, beside `months`'s count of members.
        #: See the note at `statement_periods` below.
        self.period_keys: set[tuple] = set()
        #: The calendar month each counted statement stands for (`statement_month`), and how many counted statements
        #: print no period, each its own month.
        self.month_keys: set[int] = set()
        self.months_unplaced = 0
        #: Each counted member's account reading and the days its statement covers, joined into accounts by `finish`
        #: (a member linked to none is its own account).
        self.months_members: list[dict] = []
        #: The members whose own rows do not reconcile to the bank's figures, and the members whose True rests on rows
        #: the holds could not screen or whose payer no parser read.
        self.unreconciled_members: list[str] = []
        self.holder_unscreened_members: list[str] = []
        self.payer_text_unread_members: list[str] = []
        #: The members that are premium trust accounts.
        self.premium_trust_members: list[str] = []
        self.adb_weighted_sum = Decimal("0")
        self.adb_weight = 0
        self.totals = {
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
            # Per calendar month: lender_debits / months (published with the other per-month figures; it was the
            # package's total under a monthly name). Its place here keeps the downloads' row order.
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

        self.funders: dict[str, dict] = {}
        self.potential_lenders: dict[str, dict] = {}
        self.insurance_providers: dict[str, dict] = {}
        self.transactions: list[dict] = []
        self.funder_matches: list[dict] = []
        self.potential_matches: list[dict] = []
        self.insurance_matches: list[dict] = []
        self.lender_evidence: list[dict] = []
        # The kept members' returned funder payments, each naming its statement and its unit.
        self.returned_funder_payments: list[dict] = []
        # The kept members' lump-sum payoffs (each naming its statement and its unit) and their sum, published only
        # where there is one.
        self.lump_sum_payoffs: list[dict] = []
        self.lump_sum = {"count": 0, "total": 0.0}
        # §9.2: the ready members' large unsourced deposits, each naming its statement, its account and its unit, its
        # share its own statement's; information only.
        self.large_unsourced_deposits: list[dict] = []
        self.potential_lender_evidence: list[dict] = []
        self.insurance_evidence: list[dict] = []
        self.revenue_evidence: dict[str, list[dict]] = {
            state: [] for state in REVENUE_STATES
        }
        # §9.2: the counted and held credits' evidence, and the members whose revenue is not established.
        self.tier_evidence: dict[str, list[dict]] = {"counted_flagged": [], "excluded_pending_review": []}
        # §9.2: and the non-revenue breakdown, summed over the kept members whatever their revenue's standing
        # (Non-revenue stays where True is N/A, §10.4).
        self.by_reason: dict[str, dict[str, dict]] = {"counted_flagged": {}, "excluded_pending_review": {},
                                                      "non_revenue": {}}
        # §9.2: the kept members' Zelle figures, part by part ((served tier, amount) slots, read from each member's
        # metrics.zelle_deposits), whether a member carried them, and whether every member's reading is the one the
        # setting asks for.
        # §9.2: `counted`, whether every kept member that carries the figures, or contributes its excluded Zelle
        # deposits, is served with them counted (the package's `counted_as_true_revenue`).
        self.zelle: dict = {"carried": False, "counted": True, "setting_applied": True, "count": 0, "total": 0.0,
                            "by_tier": {}}
        self.unestablished_verified: list[str] = []
        self.unestablished_revenue: list[str] = []
        # §11: a member whose True or Verified figure is not established adds a partial
        # figure to that mode's denominator, so the package publishes no rate on it.
        self.partial_revenue_denominator = False
        # §9.2: a member row marked as publishing no rate.
        self.any_member_basis_unestablished = False
        self.any_member_gated = False
        # §17.1: the ready tiered members' figures T7 reads, summed per declared currency (None, a member declaring
        # none, is its own group): currency -> [held, posted, True], cents.
        self.gate_cents: dict[str | None, list[int]] = {}
        #: (group key, payee) -> the running roll-up of the ticked flag groups (lender detection §8.3).
        self.flagged_rollup: dict[tuple[str, str], dict] = {}
        self.flagged_evidence: list[dict] = []
        self.denominator_modes: set[str] = set()
        # Each ready member's withholding basis, published where the package mixes them.
        self.withholding_basis_by_member: list[dict] = []
        self.nsf_sources: set[str] = set()
        #: CURRENCY DOCTRINE §F bookkeeping: how many money-contributing members
        #: each declared currency has, and how many declared none at all.
        self.currency_documents: dict[str, int] = {}
        self.undeclared_currency_documents = 0

    def add(self, figures: MemberFigures) -> None:
        """Add one member's figures (`member_figures`). The package adds its members in their order."""
        member = figures.member
        totals = self.totals
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
                self.undeclared_currency_documents += 1
            else:
                self.currency_documents[statement_currency] = (
                    self.currency_documents.get(statement_currency, 0) + 1
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
            self.denominator_modes.add(str(figures.denominator_mode))
            self.withholding_basis_by_member.append(figures.withholding_basis)
        if isinstance(figures.nsf_source, str):
            self.nsf_sources.add(figures.nsf_source)  # a member with no analysis contributes no count and no basis

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
            item = self.by_reason["non_revenue"].setdefault(reason, {"count": 0, "total": 0.0})
            item["count"] += slot["count"]
            item["total"] = round(item["total"] + slot["total"], 2)
        if figures.zelle_carried:
            self.zelle["carried"] = True
            self.zelle["setting_applied"] = self.zelle["setting_applied"] and figures.zelle_setting_applied
        self.zelle["counted"] = self.zelle["counted"] and figures.zelle_counted_as_true_revenue
        for tier, count, total in figures.zelle_parts:
            item = self.zelle["by_tier"].setdefault(tier, {"count": 0, "total": 0.0})
            item["count"] += count
            item["total"] = round(item["total"] + total, 2)
            self.zelle["count"] += count
            self.zelle["total"] = round(self.zelle["total"] + total, 2)
        if ready and not figures.verified_revenue_established:
            self.unestablished_verified.append(member.key.id)
        if ready and not figures.revenue_established:
            self.unestablished_revenue.append(member.key.id)
        if figures.partial_revenue_denominator:
            self.partial_revenue_denominator = True
        if figures.gate_cents is not None:
            slot = self.gate_cents.setdefault(statement_currency, [0, 0, 0])
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
                    item = self.by_reason[tier].setdefault(reason, {"count": 0, "total": 0.0})
                    item["count"] += slot["count"]
                    item["total"] = round(item["total"] + slot["total"], 2)
        self.any_member_gated = self.any_member_gated or (ready and figures.gated)
        totals["total_debits"] = round(totals["total_debits"] + figures.debits, 2)
        totals["cash_flow"] = round(totals["cash_flow"] + figures.cash_flow, 2)
        totals["lender_debits"] = round(totals["lender_debits"] + figures.lender_debits, 2)
        totals["lender_debit_count"] += figures.lender_debit_count
        totals["returned_funder_payment_total"] = round(
            totals["returned_funder_payment_total"] + figures.returned_funder_payment_total, 2
        )
        totals["returned_funder_payment_count"] += figures.returned_funder_payment_count
        self.lump_sum["count"] += figures.lump_sum_payoff_count
        self.lump_sum["total"] = round(self.lump_sum["total"] + figures.lump_sum_payoff_total, 2)
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
            item = self.funders.setdefault(
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
        self.funder_matches.extend(figures.funder_matches)
        self.returned_funder_payments.extend(figures.returned_funder_payments)
        self.large_unsourced_deposits.extend(figures.large_unsourced_deposits)
        self.lump_sum_payoffs.extend(figures.lump_sum_payoffs)
        for share in figures.potential_lender_shares:
            item = self.potential_lenders.setdefault(
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
        self.potential_matches.extend(figures.potential_matches)
        for share in figures.insurance_shares:
            item = self.insurance_providers.setdefault(
                share.provider,
                {"provider": share.provider, "documents": 0, "count": 0, "total_debited": 0.0},
            )
            item["documents"] += 1
            item["count"] += share.count
            item["total_debited"] = round(
                item["total_debited"] + share.total_debited,
                2,
            )
        self.insurance_matches.extend(figures.insurance_matches)

        # Flag groups (lender detection §8.3): the ticked groups' counted rows of this member's ledger, less its
        # internal-transfer legs. They never reach the lender totals, the withholding or the decision (D7).
        add_flagged_rows(self.flagged_rollup, figures.flagged_rows)

        self.transactions.extend(figures.transactions)
        self.lender_evidence.extend(figures.lender_evidence)
        self.potential_lender_evidence.extend(figures.potential_lender_evidence)
        self.insurance_evidence.extend(figures.insurance_evidence)
        self.flagged_evidence.extend(figures.flagged_evidence)
        for state, evidence in figures.revenue_evidence.items():
            self.revenue_evidence[state].extend(evidence)
        for tier, evidence in figures.tier_evidence.items():
            self.tier_evidence[tier].extend(evidence)

        if figures.basis_unestablished:
            self.any_member_basis_unestablished = True
        self.documents.append(doc_row)
        if ready:
            self.monthly.append(doc_row)
            # The same rows counted as PERIODS rather than as members. Two
            # accounts of one document share a job id and the document's one
            # printed cycle, so they collapse to one; two documents never do,
            # whatever period they print.
            self.period_keys.add((member.job.id, doc_row["period_start"], doc_row["period_end"]))
            # The calendar month it stands for. Two accounts of one business for one month, uploaded as two
            # files, are one month.
            month_key = statement_month(doc_row["period_start"], doc_row["period_end"])
            if month_key is None:
                self.months_unplaced += 1
            else:
                self.month_keys.add(month_key)
            # The days it covers, for its account's month floor below; with what its account is read by
            # (`months_linked`).
            self.months_members.append({
                "job_id": member.job.id, "facts": member.facts,
                "days": covered_days(doc_row["period_start"], doc_row["period_end"]),
            })
            if doc_row["reconciles"] is not True:
                self.unreconciled_members.append(doc_row["id"])
            if doc_row["holder_unscreened"]:
                self.holder_unscreened_members.append(doc_row["id"])
            if doc_row["payer_text_unread"]:
                self.payer_text_unread_members.append(doc_row["id"])
            if doc_row["premium_trust_account"]:
                self.premium_trust_members.append(doc_row["id"])
            if figures.adb_validated:
                adb_value = Decimal(str(figures.adb_value))
                self.adb_weighted_sum += adb_value * figures.adb_calendar_days
                self.adb_weight += figures.adb_calendar_days

    def finish(self, passes: PackagePasses, changes: list[dict] | None, unchecked: list[dict], reading: dict) -> None:
        """Read the package's figures once every member is in: each member row's positions from the lender reading
        (`reading`, which `package_lender_payment_changes` filled when it returned `changes` and `unchecked`), the
        months and the days-weighted ADB, the funder roll-up less the payments pass 4 matched (`passes`), the derived
        totals and their revenue refusals, the withholding basis and the decision."""
        totals = self.totals
        self.lender_payment_changes, self.lender_payment_unchecked = changes, unchecked
        # §9.2, §10: each member row's active and possible positions, read from the same chains, and the package's
        # months.
        self.active_positions_by_month = package_active_positions(self.documents, reading)

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
        for member in self.selected.members:
            if member.key.account_index is None:
                continue  # a single-account job is one member and one document
            identity = getattr(member.job, "content_sha256", None) or member.job.id
            members_by_document[identity] = members_by_document.get(identity, 0) + 1
        self.documents_with_several_members = sorted(
            identity for identity, count in members_by_document.items() if count > 1
        )
        self.refuse_cross_account_averages = bool(self.documents_with_several_members)

        # `months` is the number of distinct CALENDAR months the counted statements stand for (the Monthly Statements
        # table's rule, `statement_month`), each statement that prints no period its own month. Counting members would
        # make K accounts uploaded as K files read K times the months and every monthly average 1/K of the business's
        # combined figure; MCA underwriters combine a business's accounts by month (standard §4.4 and §4.6). Each
        # per-month average below is the per-calendar-month sum across accounts divided by it.
        #
        # Floored by the days each account's statements cover, as whole months of 30.4375 days, half up (the largest
        # account's), so consecutive statements of one account never read fewer months than the days they cover: a
        # 16th-to-15th cycle across February (02-16..03-15 and 03-16..04-15 both stand for March) or a cycle whose
        # periods share their closing day read 3 months over 3 statements, never 2, and a statement of 59 days reads 2,
        # never 1. The labels (`statement_month`) are unchanged; a floor below the calendar count is inert.
        #
        # An account is the members `months_linked` joins (a small union-find in member order): two keyed members by the
        # bank and the last four, as before; a member that prints no bank or fewer than four digits by the balance chain
        # of the owner's Q6 identity within its bank and holder, so a 16th-to-15th cycle whose number is not read reads
        # its months too. A member linked to none is its own account.
        links = list(range(len(self.months_members)))

        def account_of(place: int) -> int:
            while links[place] != place:
                links[place] = links[links[place]]
                place = links[place]
            return place

        for place, member in enumerate(self.months_members):
            for other_place in range(place):
                if months_linked(self.months_members[other_place], member):
                    links[account_of(place)] = account_of(other_place)
        account_days: dict[int, set] = {}
        for place, member in enumerate(self.months_members):
            account_days.setdefault(account_of(place), set()).update(member["days"])
        month_floor = max((months_covered(len(days)) for days in account_days.values()), default=0)
        self.months = max(1, len(self.month_keys) + self.months_unplaced, month_floor)
        # The statement periods (one per document and printed cycle) beside the months, published when the two differ;
        # the dashboard prints "N statements · M months".
        self.statement_periods = len(self.period_keys) or self.months
        # Days-weighted mean of the per-statement daily-balance averages: summing
        # every statement's daily balances and dividing by every calendar day.
        self.average_daily_balance = None
        if self.adb_weight > 0:
            self.average_daily_balance = float(
                (self.adb_weighted_sum / self.adb_weight).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            )
        if self.refuse_cross_account_averages:
            # The ADB doctrine forbids a document-level combined ADB outright, so a
            # days-weighted mean over two accounts of one document is the forbidden
            # figure arrived at by a different route.
            self.average_daily_balance = None
        # Each payment pass 4 matched to a return in the next statement is out of its funder's paid rollup and in its
        # returned payments (the member rows already read the overlay), and the returned-payment warning lists it,
        # naming both documents.
        for match in passes.matches:
            if match["kind"] != "returned_funder_payment":
                continue
            debit, credit = match["debit"], match["credit"]
            amount = round(abs(num(debit.get("amount"))), 2)
            rollup = self.funders.get(debit.get("funder") or "Unknown")
            if rollup is not None:
                rollup["debit_count"] = max(int(rollup.get("debit_count", 0)) - 1, 0)
                rollup["total_debited"] = round(rollup["total_debited"] - amount, 2)
                rollup["returned_payment_count"] += 1
                rollup["returned_payment_total"] = round(rollup["returned_payment_total"] + amount, 2)
            self.returned_funder_payments.append({
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
                **passes.represented.get((MemberKey(debit.get("job"), debit.get("account_index")),
                                                   debit.get("source_location")), {}),
            })
        totals["lenders_detected"] = len(self.funders)
        totals["potential_lenders_detected"] = len(self.potential_lenders)
        totals["flagged_position_count"] = sum(item["count"] for item in self.flagged_rollup.values())
        totals["flagged_position_total"] = round(sum(item["total_debited"] for item in self.flagged_rollup.values()), 2)
        totals["flagged_position_count_credited"] = sum(item["count_credited"] for item in self.flagged_rollup.values())
        totals["flagged_position_total_credited"] = round(
            sum(item["total_credited"] for item in self.flagged_rollup.values()), 2
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
        # alias. Neither is a reconciliation against the bank's figures: `unreconciled_documents` lists the members
        # whose own rows do not reconcile (`reconciliation.ok`), which the dashboard's Revenue chip reads.
        totals["revenue_tiers_sum_to_posted"] = (
            totals["revenue_reconciliation_delta"] == 0.0
            and totals["revenue_classified_count"] == totals["total_posted_credit_count"]
        )
        totals["revenue_reconciles"] = totals["revenue_tiers_sum_to_posted"]
        totals["unreconciled_documents"] = sorted(self.unreconciled_members)
        # The members whose holder's name is unknown, or whose credits' payer no parser read; the True card names them.
        totals["holder_unscreened_documents"] = sorted(self.holder_unscreened_members)
        totals["payer_text_unread_documents"] = sorted(self.payer_text_unread_members)
        # The members whose deposits that would count are held for a premium trust account's title; the True card names
        # how many.
        totals["premium_trust_documents"] = sorted(self.premium_trust_members)
        # §9.2: the gate applied to each member; a package needs revenue review when one of them does. §17.1: T7's
        # shares are also read on the package's sums, per declared currency, so a package of months each holding under
        # REVENUE_REVIEW_HELD_FLOOR gates as the same credits printed as one statement would (an advance is sized on the
        # deal's True, standard §4.4). Review only: no figure moves. The direction-conflict and four-tier terms stay per
        # member; the posted-credit share on the sums adds nothing (a sum's share reaches 10% only where a member's
        # does), so only the floored True-plus-held share can add.
        package_sums_gated = any(
            revenue_review_gate(direction_conflict=False, held_total=held / 100, posted_total=posted / 100,
                                tiers_sum_to_posted=True, true_total=true / 100)
            for held, posted, true in self.gate_cents.values()
        )
        totals["revenue_review_required"] = self.any_member_gated or package_sums_gated
        totals["counted_flagged_by_reason"] = self.by_reason["counted_flagged"]
        totals["excluded_pending_review_by_reason"] = self.by_reason["excluded_pending_review"]
        # §9.2: the kept members' non-revenue breakdown. It is left out of the two nulling blocks below (§10.4's and the
        # no-analysis one: Non-revenue stays), and its money is refused with the totals under a currency refusal, its
        # counts kept.
        totals["non_revenue_by_reason"] = dict(sorted(self.by_reason["non_revenue"].items()))
        # §9.2: the kept members' Zelle figures, part by part, present when a kept member carries them;
        # `setting_applied` False when a member's is. Its money is refused with the totals under a currency refusal, its
        # counts kept. `counted_as_true_revenue` is the members' served reading (true when every kept member carrying
        # the figures, or contributing its excluded Zelle deposits, is served with them counted), as each statement's
        # is; `setting` is the setting the package was served under (packages only), which the download's
        # `zelle_deposits.setting` row reads.
        if self.zelle["carried"]:
            order = {tier: position for position, tier in enumerate(("verified", "counted_flagged",
                                                                     "excluded_pending_review", "non_revenue"))}
            totals[ZELLE_DEPOSITS_KEY] = {
                "counted_as_true_revenue": self.zelle["counted"],
                "setting": self.zelle_counted,
                "setting_applied": self.zelle["setting_applied"],
                "count": self.zelle["count"],
                "total": self.zelle["total"],
                "by_tier": dict(sorted(self.zelle["by_tier"].items(), key=lambda item: order.get(item[0], len(order)))),
            }
        totals["revenue_unestablished_documents"] = sorted(
            set(self.unestablished_revenue) | set(self.unestablished_verified))
        totals["true_revenue"] = totals["true_revenue_total"]
        if self.unestablished_revenue:
            # §10.4: a package's True, Counted and Held figures stand only when every completed member's revenue does.
            for key in ("true_revenue_total", "true_revenue_count", "counted_flagged_total", "counted_flagged_count",
                        "excluded_pending_review_total", "excluded_pending_review_count", "true_revenue",
                        "counted_flagged_by_reason", "excluded_pending_review_by_reason"):
                totals[key] = None
        if self.unestablished_verified:
            # T9: confirmed_true_revenue_total and confirmed_true_revenue alias the verified total, so they are N/A with
            # it.
            for key in ("verified_revenue_total", "confirmed_true_revenue_total", "confirmed_true_revenue"):
                totals[key] = None
        # §10.4: and so are the Zelle figures' parts of them, the counted and held slots with True, Counted and Held
        # and the verified slot with Verified; the captured rows' count, total and non-revenue part stay (the
        # Non-revenue figures stay too).
        if ZELLE_DEPOSITS_KEY in totals:
            totals[ZELLE_DEPOSITS_KEY] = unestablished_zelle_figures(
                totals[ZELLE_DEPOSITS_KEY], established=not self.unestablished_revenue,
                verified_established=not self.unestablished_verified)
        # A package with no statement analysed (every job failed, was interrupted or is still queued or processing, or
        # every account was left out) has no revenue figure at all: True, Verified, Counted and Held are N/A, never a
        # $0.00 an underwriter would read as a measured decline, and nothing reads as reconciled. With one analysed
        # statement or more, §10.4 holds as before: a failed member's credits are in no total.
        self.no_statement_analysed = totals["completed"] == 0
        if self.no_statement_analysed:
            for key in ("true_revenue_total", "true_revenue_count", "counted_flagged_total", "counted_flagged_count",
                        "excluded_pending_review_total", "excluded_pending_review_count", "true_revenue",
                        "counted_flagged_by_reason", "excluded_pending_review_by_reason", "verified_revenue_total",
                        "confirmed_true_revenue_total", "confirmed_true_revenue"):
                totals[key] = None
            totals["revenue_tiers_sum_to_posted"] = totals["revenue_reconciles"] = False
        # True revenue spec §9.2, §11: the package's one basis. A package with no ready member keeps today's legacy mode
        # (no rate: it has no basis); one whose members were analysed under different bases is mixed, and publishes no
        # rate over the blend.
        self.denominator_mode = (
            next(iter(self.denominator_modes)) if len(self.denominator_modes) == 1
            else "legacy_eligible_deposits" if not self.denominator_modes else "mixed"
        )
        self.mixed_basis = len(self.denominator_modes) > 1
        # A revenue basis under the withholding basis floor publishes no rate, as $0 does; the legacy basis and a mixed
        # one (refused below) never read the floor. Never a gate.
        self.basis_below_floor = not self.mixed_basis and withholding_basis_below_floor(
            totals["withholding_denominator"], self.denominator_mode)
        self.withholding_rate_raw = (
            abs(totals["withholding_numerator"]) / totals["withholding_denominator"] * 100
            if withholding_basis_publishable(totals["withholding_denominator"], self.denominator_mode)
            else None
        )
        self.withholding_rate = round(self.withholding_rate_raw, 2) if self.withholding_rate_raw is not None else None
        self.withholding_review_required = not withholding_basis_publishable(
            totals["withholding_denominator"], self.denominator_mode)
        self.potential_withholding_raw = (
            abs(totals["potential_withholding_numerator"])
            / totals["potential_withholding_denominator"]
            * 100
            if withholding_basis_publishable(totals["potential_withholding_denominator"], self.denominator_mode)
            else None
        )
        self.potential_withholding = (
            round(self.potential_withholding_raw, 2)
            if self.potential_withholding_raw is not None
            else None
        )
        if self.partial_revenue_denominator:
            # Final review M10 (§11): the denominator is partial in the True- or Verified-revenue mode, so neither rate
            # on it is published, and the package asks for review.
            self.withholding_rate = self.withholding_rate_raw = None
            self.potential_withholding = self.potential_withholding_raw = None
            self.withholding_review_required = True
        if self.mixed_basis:
            # Members analysed under different withholding bases (a job stored with a legacy or no mode, beside a new
            # one) sum legacy deposits and True revenue into one figure that is neither: no package rate and no
            # potential exposure is published over it, and the package asks for review. Each member row keeps its own
            # basis and rate.
            self.withholding_rate = self.withholding_rate_raw = None
            self.potential_withholding = self.potential_withholding_raw = None
            self.withholding_review_required = True
        # A lender row carries no basis where the package publishes no exposure over a basis: a partial one, a mixed one
        # or one under the floor; a basis of $0 or less keeps its 0.0, as before.
        rollup_basis_refused = self.partial_revenue_denominator or self.mixed_basis or self.basis_below_floor
        self.potential_withholding_review_required = totals["potential_lender_debit_count"] > 0
        for item in self.potential_lenders.values():
            # No basis on a lender row where the package's is partial, or the dashboard would compute the exposure
            # the package refuses from it.
            item["eligible_deposit_denominator"] = (
                None if rollup_basis_refused else totals["potential_withholding_denominator"])
            item["potential_withholding_exposure"] = (
                abs(item["total_debited"]) / totals["potential_withholding_denominator"] * 100
                if withholding_basis_publishable(totals["potential_withholding_denominator"], self.denominator_mode)
                and not rollup_basis_refused
                else None
            )
            item["potential_withholding_formula"] = POTENTIAL_WITHHOLDING_FORMULA
        # The accounts left out of every figure for a reason other than a repeat: a statement whose main account is held
        # or idle, an account that did not validate on its own (Q1), and every account of a document whose transfers
        # could not be paired (Q2) or that left a section out without proof (L1-C17). Membership and every figure stay
        # as they are; the package says so (completeness partial, the count, the download section and the dashboard's
        # notice) and needs an analyst, as the same account uploaded alone does.
        self.left_out_accounts = [entry for entry in self.selected.excluded if entry.get("is_duplicate") is not True]
        self.decision = "approved"
        # The four-tier identity is not read here: it holds by construction on every tiered member, and a member whose
        # tiers do not sum already gates through `revenue_review_required` (its T7 term, or §12's for an older member).
        # A repeated statement left out of the figures needs an analyst.
        if (
            totals["failed"]
            or totals["integrity_high"]
            or totals["manual_review"]
            or self.potential_withholding_review_required
            or totals["revenue_review_required"]
            # §9.2, §11: a member whose withholding basis is not established, or the package's own partial basis,
            # publishes no rate, so the package needs an analyst, as each such statement viewed alone does. The legacy
            # basis sets neither.
            or self.any_member_basis_unestablished
            or self.partial_revenue_denominator
            # Members analysed under different withholding bases publish no package rate, so the package needs an
            # analyst (re-analyze them on one basis). The basis floor, like a $0 basis, never gates.
            or self.mixed_basis
            or totals["has_duplicate_documents"]
            # Two statements of one account that share credits in the days both cover.
            or self.selected.overlapping
            # An account left out for another reason than a repeat, and a job still queued or processing.
            or self.left_out_accounts
            or totals.get("pending")
        ):
            self.decision = "review_required"
        elif totals["summary_only"] or totals["integrity_review"]:
            self.decision = "limited_review"
