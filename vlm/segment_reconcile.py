"""Financial checks for a proven page scope, before document reconciliation.

Rows and evidence remain unchanged. No currency, classification, duplicate or
identity policy belongs here. Existing gate ordering/balance helpers are reused.
"""
from decimal import Decimal

from vlm.gate import collapse_daily_balances, minus_styled, orient, resolve_directions, signed_amount


def reconcile_page_segments(plan, rows):
    checks, occurrences = [], []
    if not plan.proven:
        return {"performed": False, "pages": []}, ()
    # A column's print style (every value with a minus) is a property of the statement, not of one page.
    styled = minus_styled(rows)
    for segment in plan.segments:
        page_rows = [row for row in rows if row.page == segment.page]
        page_rows, reversed_order = orient(page_rows)
        page_rows, collapsed = collapse_daily_balances(page_rows)
        account = {key: Decimal(str(value)) for key, value in segment.account.items()}
        page_rows, derived = resolve_directions(page_rows, account["beginning_balance"])
        result = {"page": segment.page, "row_count": len(page_rows),
                  "reversed_order": reversed_order, "collapsed_daily_balances": collapsed,
                  "chain_derived_directions": derived, "checks": []}

        def check(code, field, ok):
            result["checks"].append({"code": code, "field": field, "ok": bool(ok)})
            if not ok:
                occurrences.append({"code": code, "page": segment.page,
                                    "field": field, "source": "page_segment"})

        for direction in ("credit", "debit"):
            field = f"stated_{direction}_count"
            check("count_mismatch", field,
                  sum(row.direction == direction for row in page_rows) == account[field])
        known = all(row.direction in ("credit", "debit") for row in page_rows)
        check("direction_unknown", "direction", known)
        if known:
            signed = [signed_amount(row, styled) for row in page_rows]
            check("sum_mismatch", "ending_balance",
                  abs(account["beginning_balance"] + sum(signed, Decimal(0))
                      - account["ending_balance"]) <= Decimal("0.01"))
            for direction, sign in (("credit", 1), ("debit", -1)):
                field = f"stated_total_{direction}s"
                captured = sum((value * sign for value in signed if value * sign > 0), Decimal(0))
                target = account[field]
                # Same coverage interval as the existing document gate; a zero
                # printed box is independently checkable without division.
                check("coverage_mismatch", field,
                      captured == 0 if target == 0 else Decimal("0.98") <= captured / target <= Decimal("1.02"))
            previous, pending = account["beginning_balance"], Decimal(0)
            for row, amount in zip(page_rows, signed):
                pending += amount
                if row.balance is not None:
                    check("continuity_break", "balance", abs(previous + pending - row.balance) <= Decimal("0.01"))
                    previous, pending = row.balance, Decimal(0)
        result["ok"] = all(item["ok"] for item in result["checks"])
        checks.append(result)
    return {"performed": True, "pages": checks}, tuple(occurrences)
