"""Row rules the member fold applies: revenue buckets, flagged rows and potential lender totals."""
from __future__ import annotations

from analysis.dates import parse_date
from analysis.flag_groups import FLAG_GROUP_BY_KEY
from analysis.package.model import num
from analysis.revenue import PostedCredit, revenue_buckets, REVENUE_STATES, RevenueBuckets


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
