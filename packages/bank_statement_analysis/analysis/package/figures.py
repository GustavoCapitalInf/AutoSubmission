"""One member's figures (`member_figures`) and the row rules they apply: revenue buckets, lender figures, flagged rows
and potential lender totals."""
from __future__ import annotations

from copy import deepcopy
from math import isfinite

from analysis.dates import parse_date
from analysis.flag_groups import FLAG_GROUP_BY_KEY
from analysis.flagged_view import enabled_group_keys
from analysis.lender_figures import lender_figures, LenderFigures, LenderRow
from analysis.package.model import (
    FunderShare,
    InsuranceShare,
    is_count,
    Member,
    MemberFigures,
    num,
    overlaid_row,
    PackagePasses,
    PotentialLenderShare,
)
from analysis.package.passes import member_tiered
from analysis.package.publish import WITHHOLDING_BASIS_LABELS
from analysis.revenue import (
    non_revenue_reason,
    normalize_withholding_denominator_mode,
    PostedCredit,
    revenue_buckets,
    revenue_review_gate,
    REVENUE_STATES,
    RevenueBuckets,
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


def member_revenue(rows: list[dict], *, tiered: bool) -> RevenueBuckets:
    """A member's revenue buckets over its rows (R-d's pairs left out, the package passes' overlay applied), added as
    the package adds them: each bucket with builtin sum(), each reason total rounded after each credit, the reasons in
    the order they first appear (§9.2).

    Its posted credits are its positive rows but a classified one marked unposted. A row with no classification record
    is posted in no state (a partly classified payload, whose figures then do not reconcile). A classified credit files
    under its revenue_classification when that is a state, and under its tier only on a tiered member
    (`member_tiered`); on any other, a non_revenue credit still files its reason."""
    credits = []
    for row in rows:
        amount = num(row.get("amount"))
        record = row.get("classification")
        if amount > 0 and not isinstance(record, dict):
            credits.append(PostedCredit(amount, None, None, None, row))
        elif amount > 0 and record.get("is_posted") is not False:
            state, tier = record.get("revenue_classification"), record.get("revenue_tier")
            credits.append(PostedCredit(
                amount, state if state in REVENUE_STATES else None,
                tier if tiered or tier == "non_revenue" else None, record.get("revenue_tier_reason"), row,
            ))
    return revenue_buckets(credits, accumulation="builtin_sum", reason_accumulation="rounded_each",
                           reason_order="first_seen")


def member_lender(rows: list[dict]) -> LenderFigures:
    """A member's lender figures over its classified rows (R-d's pairs left out, the package passes' overlay applied),
    each figure added with builtin sum(). A stored row's flag counts only when it is exactly True, and a row with no
    potential total flag reads its potential count flag (`contributes_to_potential_totals`)."""
    lender_rows = []
    for row in rows:
        record = row["classification"]
        lender_rows.append(LenderRow(
            num(row.get("amount")),
            paid=record.get("contributes_to_lender_totals") is True,
            withheld=record.get("contributes_to_withholding_rate") is True,
            returned=bool(record.get("returned_funder_payment_by")),
            payoff_words=bool(record.get("lump_sum_payoff")),
            potential=contributes_to_potential_totals(record),
            insurance=record.get("contributes_to_insurance_totals") is True,
            record=row,
        ))
    return lender_figures(lender_rows, accumulation="builtin_sum")


def contributes_to_potential_totals(classification: dict) -> bool:
    explicit = classification.get("contributes_to_potential_lender_totals")
    if explicit is not None:
        return explicit is True
    return classification.get("contributes_to_potential_lender_count") is True


def counts_as_flagged(classification: dict, shown: frozenset[str]) -> bool:
    """A row the package's flag roll-up counts: the analysis marked it a contributing row of a flag group
    (`contributes_to_flagged_totals`: a posted debit, or a posted factoring credit, that is not a proven duplicate
    and not reversed; plan contract C4), and Settings ticks its group."""
    group = classification.get("flagged_group")
    return (
        classification.get("contributes_to_flagged_totals") is True
        and isinstance(group, str)
        and group in shown
    )


def add_flagged_rows(rollup: dict[tuple[str, str], dict], rows: list[dict]) -> None:
    """Fold one member's counted flag rows into the package roll-up, keyed by (group, payee).

    The payee is the row's canonical entity, or its group's label when the analysis named none (plan contract
    C5). `documents` counts the members a payee appears in, as the funder roll-up does. A debit adds to `count`
    and `total_debited`; a credit adds to `count_credited` and `total_credited`. The dates of both are kept so
    the first and last dates, and the cadence, are read across every member rather than per statement."""
    seen: set[tuple[str, str]] = set()
    for row in rows:
        classification = row["classification"]
        group = classification["flagged_group"]
        entity = classification.get("canonical_entity")
        payee = entity if isinstance(entity, str) and entity else FLAG_GROUP_BY_KEY[group].label
        item = rollup.setdefault(
            (group, payee),
            {"payee": payee, "documents": 0, "count": 0, "total_debited": 0.0, "count_credited": 0,
             "total_credited": 0.0, "dates": [], "review_required": False},
        )
        item["review_required"] = item["review_required"] or classification.get("review_required") is True
        if (group, payee) not in seen:
            seen.add((group, payee))
            item["documents"] += 1
        amount = num(row.get("amount"))
        if amount < 0:
            item["count"] += 1
            item["total_debited"] = round(item["total_debited"] + abs(amount), 2)
        else:
            item["count_credited"] += 1
            item["total_credited"] = round(item["total_credited"] + amount, 2)
        posted = parse_date(row.get("date") or classification.get("date"))
        if posted is not None:
            item["dates"].append(posted)


def member_figures(member: Member, passes: PackagePasses, settings: dict) -> MemberFigures:
    """One member's figures, its published row, and what it adds to each of the package's totals, lists and roll-ups,
    read off its displayed account with the package passes' result (`passes`) applied, under the package's settings
    snapshot. It writes nothing it is handed: a row the passes patch is copied first."""
    shown_groups = enabled_group_keys(settings)
    zelle_counted = zelle_setting(settings)
    job, account_index = member.job, member.key.account_index
    statement = member.account.get("statement") or {}
    metrics = member.account.get("metrics") or {}
    quality = member.account.get("quality") or {}
    integrity = member.account.get("integrity") or {}
    detection = member.account.get("detection") or {}
    corporate_use = quality.get("corporate_use") or ""
    integrity_risk = integrity.get("risk_level") or ""
    ready = member.ready
    pending = not ready and job.status in _PENDING_JOB_STATUSES
    statement_currency = member.facts.currency

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
    member_overlay = passes.overlays.get(member.key) or {}
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
    moved_credits = passes.moved.get(member.key) or []
    if moved_credits and denominator_mode in ("true_revenue", "verified_revenue"):
        moved_total = round(sum(
            item["amount"] for item in moved_credits
            if (item["tier"] in ("verified", "counted_flagged") if denominator_mode == "true_revenue"
                else item["state"] == "verified_revenue")
        ), 2)
        eligible_deposits = round(max(eligible_deposits - moved_total, 0.0), 2)
    withholding_basis = {
        "source_job": job.id, **({"account_index": account_index} if account_index is not None else {}),
        "mode": str(denominator_mode), "label": WITHHOLDING_BASIS_LABELS.get(str(denominator_mode), ""),
    }
    nsf_count = int(num(metrics.get("effective_nsf_count"), 0.0))
    nsf_source = metrics.get("nsf_source")
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
    # The member's Zelle figures (its served metrics.zelle_deposits). Under No, a member that carries none
    # contributes its excluded Zelle deposits as its non-revenue part, so the package figure covers every member.
    member_zelle = metrics.get(ZELLE_DEPOSITS_KEY) if isinstance(metrics.get(ZELLE_DEPOSITS_KEY), dict) else None
    zelle_counted_as_true_revenue = True
    if member_zelle is not None:
        # The member's own reading, as its statement serves it.
        zelle_counted_as_true_revenue = member_zelle.get("counted_as_true_revenue") is True
        parts = member_zelle.get("by_tier") if isinstance(member_zelle.get("by_tier"), dict) else {}
    elif not zelle_counted and member_by_reason["non_revenue"].get("zelle_excluded"):
        zelle_counted_as_true_revenue = False  # Its Zelle deposits are excluded
        parts = {"non_revenue": member_by_reason["non_revenue"]["zelle_excluded"]}
    else:
        parts = {}
    zelle_parts = [(tier, int(num(slot.get("count"))), num(slot.get("total")))
                   for tier, slot in parts.items() if isinstance(slot, dict)]
    # §9.2, §11: the member's own basis is not established (its served copy already says so, or the package's reading
    # of its rows does); its row publishes no rate and its potential lenders no exposure, as the statement viewed
    # alone (analysis/revenue_view.py).
    member_basis_unestablished = metrics.get(WITHHOLDING_BASIS_UNESTABLISHED) is True or (
        ready and withholding_basis_unestablished(denominator_mode, verified_established=verified_revenue_established,
                                                  established=revenue_established))
    partial_revenue_denominator = ready and (
        (denominator_mode == "true_revenue" and not revenue_established)
        or (denominator_mode == "verified_revenue" and not verified_revenue_established)
    )
    member_reconciles = round(sum(num(total) for total in revenue_totals.values()), 2) == posted_credit_total
    gate_cents = None
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
            gate_cents = (round(tier_totals["excluded_pending_review"] * 100), round(posted_credit_total * 100),
                          round((tier_totals["verified"] + tier_totals["counted_flagged"]) * 100))
    else:
        # §12: a member analysed before 5.6 is gated by the rule it was analysed under.
        member_gated = (
            any(row["classification"].get("revenue_classification") == "unverified_deposit"
                and row["classification"].get("revenue_review_status") == "pending"
                for row in posted_credit_rows)
            or direction_conflict
            or not member_reconciles
        )

    funder_shares = []
    funder_matches = []
    for match in detection.get("known_funders") or []:
        name = match.get("funder") or "Unknown"
        match_debit_count = int(
            num(match.get("debit_count"), len(match.get("transactions") or []))
        )
        funder_shares.append(FunderShare(
            name,
            # A funder whose every payment bounced publishes debit_count 0, and is listed with it.
            match_debit_count if match_debit_count or "debit_count" in match else None,
            num(match.get("total_debited")),
            int(num(match.get("returned_payment_count"), 0.0)),
            num(match.get("returned_payment_total")),
        ))
        funder_matches.append(
            {
                "funder": name,
                "source_job": job.id,
                "transactions": match.get("transactions") or [],
                "evidence": match.get("evidence") or [],
            }
        )
    # The warning's items, each naming its statement, its account (a statement of several) and its unit, as an
    # evidence record does.
    returned_funder_payments = []
    for returned_item in detection.get("returned_funder_payments") or []:
        if isinstance(returned_item, dict):
            returned_funder_payments.append({
                **returned_item, "source_job": job.id, "source_document": job.filename,
                "source_currency": statement_currency,
                **({"source_account": account_index} if account_index is not None else {}),
                # A payment the funder re-debited in the next statement.
                **passes.represented.get((member.key, returned_item.get("debit_location")), {}),
            })
    # §9.2, §17.1: a ready, tiered member whose revenue is established lists its large unsourced deposits as the
    # package counts its rows (R-d's pairs left out, the package passes' holds applied, so a deposit the package holds
    # as an own-account transfer is not listed), each share of the member's True as the package counts it (its
    # row's `true_revenue_total` below); read by no figure, gate or decision.
    large_deposits = []
    if ready and tiered and revenue_established:
        for large_item in large_unsourced_deposits(
                tier_rows["counted_flagged"], round(tier_totals["verified"] + tier_totals["counted_flagged"], 2)):
            large_deposits.append({
                **large_item, "source_job": job.id, "source_document": job.filename,
                **({"source_account": account_index} if account_index is not None else {}),
                "source_currency": statement_currency,
            })
    # The member's lump-sum payoffs, each naming its statement, its account (a statement of several) and its unit; a
    # payment the package's pass 4 matched to a return in the next statement is out of paid there and no lump sum
    # (its overlay row says so).
    paid_lump_sums = {row["classification"].get("source_location") for row in lender.payoff.records}
    lump_sum_payoffs = []
    for lump_sum_item in detection.get("lump_sum_payoffs") or []:
        if isinstance(lump_sum_item, dict) and (not authoritative_rows
                                                or lump_sum_item.get("location") in paid_lump_sums):
            lump_sum_payoffs.append({
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

    potential_lender_shares = []
    potential_matches = []
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
        potential_lender_shares.append(PotentialLenderShare(name, match_count, match_total))
        potential_matches.append(
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

    insurance_shares = []
    insurance_matches = []
    for match in detection.get("insurance_providers") or []:
        name = match.get("provider") or "Insurance provider not identified"
        insurance_shares.append(
            InsuranceShare(name, int(num(match.get("count"), 0.0)), num(match.get("total_debited"))))
        insurance_matches.append(
            {
                "provider": name,
                "source_job": job.id,
                "transactions": match.get("transactions") or [],
                "evidence": match.get("evidence") or [],
            }
        )

    # Flattened ledger so the dashboard can show every statement's rows at once.
    transactions = []
    lender_evidence = []
    potential_lender_evidence = []
    insurance_evidence = []
    flagged_evidence = []
    revenue_evidence = {state: [] for state in REVENUE_STATES}
    tier_evidence = {"counted_flagged": [], "excluded_pending_review": []}
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
        transactions.append(package_transaction)
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
            lender_evidence.append(evidence)
        if contributes_to_potential_totals(classification):
            potential_lender_evidence.append(evidence)
        if classification.get("contributes_to_insurance_totals") is True:
            insurance_evidence.append(evidence)
        if counts_as_flagged(classification, shown_groups):
            # A location is numbered within its own account, so a multi-account member's evidence names it.
            flagged_evidence.append(
                evidence if account_index is None else {**evidence, "source_account": account_index}
            )
        revenue_state = classification.get("revenue_classification")
        if revenue_state in REVENUE_STATES and num(tx.get("amount")) > 0:
            # A revenue evidence record names its unit and its account, so a mixed-currency or multi-account
            # package's evidence can be read without a join (None: one account, no currency).
            revenue_record = {**evidence, "source_currency": statement_currency, "source_account": account_index}
            revenue_evidence[revenue_state].append(revenue_record)
            if classification.get("revenue_tier") in tier_evidence:
                tier_evidence[classification["revenue_tier"]].append(revenue_record)

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
    if member.key in passes.unchecked:
        doc_row["package_match_unchecked"] = passes.unchecked[member.key]
    return MemberFigures(
        member=member, ready=ready, pending=pending, row=doc_row, credits=credits, debits=debits, cash_flow=cash_flow,
        posted_credit_total=posted_credit_total, posted_credit_count=posted_credit_count,
        revenue_totals=revenue_totals, revenue_counts=revenue_counts, by_reason=member_by_reason, tiered=tiered,
        tier_totals=tier_totals, tier_counts={tier: len(rows) for tier, rows in tier_rows.items()},
        verified_revenue_established=verified_revenue_established, revenue_established=revenue_established,
        partial_revenue_denominator=partial_revenue_denominator, gated=member_gated, gate_cents=gate_cents,
        zelle_carried=member_zelle is not None,
        zelle_setting_applied=member_zelle is None or member_zelle.get("setting_applied") is not False,
        zelle_counted_as_true_revenue=zelle_counted_as_true_revenue, zelle_parts=zelle_parts,
        lender_debits=lender_debits, lender_debit_count=lender_debit_count, withholding_numerator=withholding_numerator,
        returned_funder_payment_total=returned_funder_payment_total,
        returned_funder_payment_count=returned_funder_payment_count, lump_sum_payoff_total=lump_sum_payoff_total,
        lump_sum_payoff_count=lump_sum_payoff_count, potential_lender_debit_total=potential_lender_debit_total,
        potential_lender_debit_count=potential_lender_debit_count, insurance_total=insurance_total,
        insurance_count=insurance_count, eligible_deposits=eligible_deposits, denominator_mode=denominator_mode,
        withholding_basis=withholding_basis, basis_unestablished=member_basis_unestablished, nsf_count=nsf_count,
        nsf_source=nsf_source, adb_validated=adb_validated, adb_value=average_daily_balance_num,
        adb_calendar_days=adb_calendar_days, funder_shares=funder_shares,
        potential_lender_shares=potential_lender_shares, insurance_shares=insurance_shares, flagged_rows=flagged_rows,
        funder_matches=funder_matches, potential_matches=potential_matches, insurance_matches=insurance_matches,
        returned_funder_payments=returned_funder_payments, lump_sum_payoffs=lump_sum_payoffs,
        large_unsourced_deposits=large_deposits, transactions=transactions, lender_evidence=lender_evidence,
        potential_lender_evidence=potential_lender_evidence, insurance_evidence=insurance_evidence,
        flagged_evidence=flagged_evidence, revenue_evidence=revenue_evidence, tier_evidence=tier_evidence,
    )
