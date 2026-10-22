"""The package passes over its members (true revenue spec §6.2): matched transfers, represented and
returned funder payments."""
from __future__ import annotations

import re

from analysis.package.calendar import iso_day
from analysis.package.model import (
    consecutive,
    different_accounts,
    Member,
    MemberKey,
    num,
    overlaid_row,
    PackagePasses,
    REVIEW_DECISIONS,
    row_cents,
    same_account,
)
from analysis.payee_matcher import match_known_payee
from analysis.revenue import revenue_contribution_flags, REVENUE_STATES
from analysis.revenue_view import DEBIT_FLAG_KINDS, debit_side_flags
from analysis.transaction_classifier import (
    _deposit_channel_credit,
    _deposit_return_debit,
    _received_on_day,
    _RETURN_CREDIT_TIERS,
    _returned_payment_credit,
    _undo_debit_names_a_credit,
    paper_or_cash_deposit,
    RETURNED_FUNDER_PAYMENT_WINDOW_DAYS,
)
from analysis.description_text import _TRANSFER_WORDING
from analysis.descriptor.lexical import is_round_sum
from analysis.descriptor.words import _CONSUMER_P2P_RAIL, _PUSH_RAIL
from analysis.true_revenue import zelle_deposit


#: True revenue spec §6.2's package passes: the most days a matched deposit posts after the transfer out.
PACKAGE_TRANSFER_DAYS = 2


#: The classes a transfer out never has (a lender's, a financing's, a card payment's, an insurer's, a tax's, a
#: payroll's or a fee's debit is no transfer between the business's accounts, whatever wording it prints).
_TRANSFER_OUT_REFUSED_CLASSES = frozenset({
    "confirmed_lender", "potential_lender", "alternative_position", "line_of_credit", "vehicle_financing", "bank_loan",
    "mortgage", "lease_or_rental", "personal_loan", "floor_plan_financing", "factoring", "debt_relief",
    "lease_or_equipment_financing", "credit_card_payment", "insurance", "tax", "payroll", "fee",
})


#: The contributions a transfer out never makes (a lender, potential-lender, withholding or flagged row).
_TRANSFER_OUT_REFUSED_CONTRIBUTIONS = (
    "contributes_to_withholding_rate", "contributes_to_lender_count", "contributes_to_potential_lender_count",
    "contributes_to_flagged_totals",
)


#: The destination veto: a transfer out that prints the account it goes to ('TO CHK 2020', 'TO 9999': the
#: normaliser has already dropped '*', '.' and '#' masks; an X mask may stand before the digits) never pairs with a
#: deposit into an account whose last four differ.
_TRANSFER_DESTINATION = re.compile(r"\bTO (?:CHK|CHECKING|SAV|SAVINGS|ACCT|ACCOUNT|SHARE|DDA)?\s*(?:X+\s*)?(\d{4,})\b")


#: The held reasons of a deposit that names no third party (a transfer, the holder's own name, a wire with no sender):
#: such a deposit that pairs with a transfer out is annotated, display only; nothing about it moves.
_OWN_MONEY_HELD_REASONS = frozenset({
    "transfer_no_counterparty", "transfer_account_designation", "holder_name", "wire_no_sender",
})


def _revenue_rows_authoritative(rows: list[dict]) -> bool:
    """Whether a member's rows (its statement's rows less R-d's internal-transfer positions) state every posted
    credit's revenue: a row carries a classification record, every positive row carries one, and every posted one a
    revenue state (§9.2, the member loop's rule)."""
    positive = [row for row in rows if num(row.get("amount")) > 0]
    classified = [row for row in positive if isinstance(row.get("classification"), dict)]
    return (
        any(isinstance(row.get("classification"), dict) for row in rows)
        and len(classified) == len(positive)
        and all(row["classification"].get("is_posted") is False
                or row["classification"].get("revenue_classification") in REVENUE_STATES for row in classified)
    )


def member_tiered(rows: list[dict]) -> bool:
    """Whether a member's rows are tiered (§9.2, §10.4): its revenue rows are authoritative and every posted credit
    carries a 5.6 tier. The package passes (`package_matches`) and the member loop read this one helper, so a member
    the passes overlay is never one the loop publishes without its tier figures."""
    if not _revenue_rows_authoritative(rows):
        return False
    return all(
        isinstance(row["classification"].get("revenue_tier"), str)
        for row in rows
        if num(row.get("amount")) > 0 and isinstance(row.get("classification"), dict)
        and row["classification"].get("is_posted") is not False
    )


def _match_side(entry: dict, position: int, row: dict) -> dict:
    """One leg of a package match as its row note and the package's `package_matches` name it. The account is
    `account_index` (1-based, None for a statement of one account), never `account`: the served payload masks every
    key named `account` as a printed account number (`masked`)."""
    record = row["classification"]
    digits = entry["facts"].digits
    return {
        "job": entry["job_id"], "filename": entry["filename"], "account_index": entry["account"],
        "source_location": record.get("source_location") or f"transaction:{position + 1}",
        "date": row.get("date"), "amount": row.get("amount"), "bank": entry["facts"].printed_bank,
        "last4": digits[-4:] if len(digits) >= 4 else None,
    }


def package_matches(members: list[Member]) -> PackagePasses:
    """True revenue spec §6.2's package passes, §9.2, §11: the package passes over the members `package_members`
    admitted, recomputed on every call from their displayed copies and never written back (no job, stored analysis,
    review row or package record changes; a statement viewed alone keeps its own figures).

    No pass reads a member's R-d internal-transfer positions (`Member.internal_transfer_positions`). A member enters
    the passes when its job is done, its rows are tiered (`member_tiered`, the member loop's test) and it declares a
    currency; in a package of two members or more, a member that does not is marked (`unchecked`: 'no_currency', else
    'older_rules'), unless it prints no row (nothing to match), and a member that enters but prints fewer than four
    account digits is marked 'no_account_number' (pass 1 still reaches it through the balance chain). A row enters
    when it is posted and no proven duplicate.

    Pass 1, returned deposits across statements: a debit that undoes a deposit (`_deposit_return_debit`, its French
    wordings included) that no credit of its statement pairs (pass 4's `matched_reversal_pair` naming its location)
    and that is no correction naming an equal credit of its own statement (pass 4's `_undo_debit_names_a_credit`, run
    unchanged over the member's rows; such a debit stays flagged, never netted across) is matched to its original
    deposit in the SAME account's IMMEDIATELY PRECEDING statement (`same_account` and `consecutive`): an equal-cents
    deposit-channel credit (`_deposit_channel_credit`) dated on or before it, with no day cap inside that statement,
    whose tier is not `non_revenue`, which pass 4 did not pair, which carries no analyst decision (an analyst's Confirm
    or Mark beats the pass) and which no other debit took. The debits are read in (date, member, position) order, the
    members in their canonical order (period start, job, account), and each takes the NEAREST candidate (the latest
    credit day, then the canonical member, then the position). The original leaves True as non-revenue (`overlays`:
    method `matched_reversal_pair`, rule `returned_deposit_cross_statement`, `package_match` naming the return); its
    initial state, review status and pass-4 link are kept, so Confirm Revenue still overrides the match. A redeposit
    after the return stays counted. Inside one statement nothing changes (pass 4 keeps its 14 days).

    Pass 2, own-account transfers: a counted deposit that prints no payer (tier `counted_flagged`, reason exactly
    `no_payer_printed`; never a rail, a round sum (`is_round_sum`), a check or cash-device deposit
    (`paper_or_cash_deposit`), a decided credit or one pass 1 took) is matched to an exact-cents transfer out of
    ANOTHER of the business's accounts (`different_accounts`: another uploaded statement, or another account of the
    same document after R-d) dated 0 to PACKAGE_TRANSFER_DAYS days before it. A transfer out is a posted, dated debit
    printing transfer wording (`_TRANSFER_WORDING`), no rail, no lender, potential-lender, withholding or flagged
    contribution, none of the financing, card-payment, insurance, tax, payroll or fee classes, and no pass-1 note; one
    that prints the account it goes to (`_TRANSFER_DESTINATION`) never pairs with a deposit into an account whose last
    four differ. One to one: the credits in (date, member, position) order, each taking the nearest untaken debit (the
    smallest gap, then the member and the position). The deposit is held (`overlays`: tier `excluded_pending_review`,
    reason `own_account_transfer_matched`, `package_match` naming the transfer, its state `unverified_deposit` and its
    pending status kept, so Confirm Revenue releases it into True and marks it Verified); the debit gains a display
    note. Then each held deposit that names no third party (`_OWN_MONEY_HELD_REASONS`) and passes the same deposit
    tests is tried against the debits still untaken by the same rule, one to one: it gains a display note only
    (`moved` false), its tier, reason, flags, totals and gate unchanged. Pass 2 never sets an internal-transfer mark
    and never removes a row from gross deposits.

    Pass 3, the debit flags (`debit_side_flags`, never deducted, never a gate term): every ready member's returns that
    neither its statement nor pass 1 matched (`unmatched_deposit_return`, with `candidate_decided` when the nearest
    candidate but for the decision carries one) and its processor chargebacks and adjustments (`processor_chargeback`).

    Returns `PackagePasses`: `overlays` ({member: {position: fields}}), `matches`, `debit_flags`, `unchecked` ({member:
    marker}), `moved` ({member: [{"tier", "state", "amount"}]}) and `represented`, deterministic and independent of the
    listing order."""
    from types import SimpleNamespace

    entries: list[dict] = []
    for member in members:
        job, analysis = member.job, member.account
        statement = analysis.get("statement") if isinstance(analysis, dict) else None
        if not (member.ready and isinstance(statement, dict)):
            continue
        raw = statement.get("transactions") if isinstance(statement.get("transactions"), list) else []
        excluded = member.internal_transfer_positions
        kept = [row if isinstance(row, dict) and position not in excluded else None for position, row in enumerate(raw)]
        entries.append({
            "key": member.key, "job_id": job.id, "filename": getattr(job, "filename", None),
            "account": member.key.account_index,
            "order": (str(statement.get("period_start") or ""), str(job.id), member.key.account_index or 0),
            "facts": member.facts, "raw": raw, "kept": kept,
            "rows": [(position, row) for position, row in enumerate(kept)
                     if row is not None and isinstance(row.get("classification"), dict)
                     and row["classification"].get("is_posted") is not False
                     and not row["classification"].get("duplicate_of")],
            "tiered": member_tiered([row for row in kept if row is not None]),
        })
    entries.sort(key=lambda entry: entry["order"])
    unchecked: dict[MemberKey, str] = {}
    if len(members) >= 2:
        for entry in entries:
            if not any(row is not None for row in entry["kept"]):
                continue  # a statement that prints no row has nothing to match, and is never marked
            if entry["facts"].currency is None:
                unchecked[entry["key"]] = "no_currency"
            elif not entry["tiered"]:
                unchecked[entry["key"]] = "older_rules"
            elif len(entry["facts"].digits) < 4:
                unchecked[entry["key"]] = "no_account_number"  # Pass 2 never pairs it
    matchable = [entry for entry in entries if entry["facts"].currency is not None and entry["tiered"]]

    def text_of(row: dict) -> str:
        return str(row["classification"].get("normalized_description") or "")

    def location_of(row: dict, position: int) -> str:
        return row["classification"].get("source_location") or f"transaction:{position + 1}"

    # Pass 1's return debits, each with whether pass 4's correction guard keeps it back.
    returns: list[tuple] = []
    for entry in matchable:
        paired = {
            row["classification"].get("revenue_related_transaction") for _position, row in entry["rows"]
            if num(row.get("amount")) > 0 and row["classification"].get("revenue_match_method") == "matched_reversal_pair"
        }
        records = duplicates = None
        for position, row in entry["rows"]:
            if num(row.get("amount")) >= 0 or not _deposit_return_debit(text_of(row)):
                continue
            location = location_of(row, position)
            if location in paired:
                continue
            if records is None:
                # Pass 4's guard over the member's every row, wrapped as the records it reads, with its duplicates.
                records = [
                    SimpleNamespace(
                        amount=num(row_.get("amount")),
                        is_posted=row_["classification"].get("is_posted") is not False,
                        date=row_["classification"].get("date") or row_.get("date") or "",
                        normalized_description=str(row_["classification"].get("normalized_description") or ""),
                    ) if isinstance(row_, dict) and isinstance(row_.get("classification"), dict)
                    else SimpleNamespace(amount=0.0, is_posted=False, date="", normalized_description="")
                    for row_ in entry["raw"]
                ]
                duplicates = {
                    position_ for position_, row_ in enumerate(entry["raw"])
                    if isinstance(row_, dict) and isinstance(row_.get("classification"), dict)
                    and row_["classification"].get("duplicate_of")
                }
            day = iso_day(row.get("date"))
            guarded = _undo_debit_names_a_credit(records, duplicates, position)
            returns.append(((day is None, day.toordinal() if day else 0, entry["order"], position),
                            entry, position, row, location, day, guarded))

    overlays: dict[MemberKey, dict[int, dict]] = {}
    matches: list[dict] = []
    moved: dict[MemberKey, list[dict]] = {}
    matched_locations: dict[tuple, set[str]] = {}
    decided_candidates: dict[tuple, dict] = {}
    taken: set[tuple] = set()
    for _sort, debit_entry, position, row, location, debit_day, guarded in sorted(returns, key=lambda item: item[0]):
        if guarded or debit_day is None:
            continue
        cents = -row_cents(row)
        best = best_any = None
        for credit_entry in matchable:
            if not (same_account(credit_entry, debit_entry)
                    and consecutive(credit_entry["facts"], debit_entry["facts"])):
                continue
            for credit_position, credit_row in credit_entry["rows"]:
                record = credit_row["classification"]
                if row_cents(credit_row) != cents or (credit_entry["key"], credit_position) in taken:
                    continue
                credit_day = iso_day(credit_row.get("date"))
                if (credit_day is None or credit_day > debit_day or record.get("revenue_tier") == "non_revenue"
                        or record.get("revenue_match_method") == "matched_reversal_pair"
                        or not _deposit_channel_credit(text_of(credit_row))):
                    continue
                candidate = ((-credit_day.toordinal(), credit_entry["order"], credit_position),
                             credit_entry, credit_position, credit_row, credit_day)
                if best_any is None or candidate[0] < best_any[0]:
                    best_any = candidate
                if record.get("revenue_review_status") not in REVIEW_DECISIONS and (
                        best is None or candidate[0] < best[0]):
                    best = candidate
        if best is None:
            if best_any is not None:
                decided = best_any[3]["classification"]
                decided_candidates[(debit_entry["key"], location)] = {
                    "job": best_any[1]["job_id"], "filename": best_any[1]["filename"],
                    "account_index": best_any[1]["account"],
                    "source_location": location_of(best_any[3], best_any[2]), "date": best_any[3].get("date"),
                    "decision": decided.get("revenue_review_status"),
                }
            continue
        _rank, credit_entry, credit_position, credit_row, credit_day = best
        record = credit_row["classification"]
        taken.add((credit_entry["key"], credit_position))
        gap = (debit_day - credit_day).days
        credit_side = _match_side(credit_entry, credit_position, credit_row)
        debit_side = _match_side(debit_entry, position, row)
        tier_before, reason_before = record.get("revenue_tier"), record.get("revenue_tier_reason")
        overlays.setdefault(credit_entry["key"], {})[credit_position] = {
            "revenue_classification": "non_revenue",
            "revenue_tier": "non_revenue",
            "revenue_tier_reason": None,
            "revenue_match_method": "matched_reversal_pair",
            "revenue_matched_rule": "returned_deposit_cross_statement",
            "revenue_review_required": False,
            **revenue_contribution_flags("non_revenue", "non_revenue"),
            "package_match": {"kind": "returned_deposit", "moved": True, "debit": debit_side, "gap_days": gap,
                              "tier_before": tier_before, "reason_before": reason_before},
        }
        overlays.setdefault(debit_entry["key"], {})[position] = {
            "package_match": {"kind": "returned_deposit", "credit": credit_side},
        }
        moved.setdefault(credit_entry["key"], []).append({
            "tier": tier_before, "state": record.get("revenue_classification"),
            "amount": round(num(credit_row.get("amount")), 2),
        })
        matched_locations.setdefault(debit_entry["key"], set()).add(location)
        matches.append({
            "kind": "returned_deposit", "moved": True,
            "credit": {**credit_side, "currency": credit_entry["facts"].currency, "tier_before": tier_before,
                       "reason_before": reason_before},
            "debit": {**debit_side, "currency": debit_entry["facts"].currency},
            "gap_days": gap,
        })

    # Pass 2: own-account transfers, then the held deposits' display notes.
    noted = {(key, position) for key, rows in overlays.items() for position in rows}  # pass 1's rows

    def rails(text: str) -> bool:
        return bool(_CONSUMER_P2P_RAIL.search(text) or _PUSH_RAIL.search(text))

    transfers_out: list[tuple] = []
    for entry in matchable:
        if len(entry["facts"].digits) < 4:
            continue  # `different_accounts` never pairs it (marked 'no_account_number')
        for position, row in entry["rows"]:
            record = row["classification"]
            day = iso_day(row.get("date"))
            text = text_of(row)
            if (num(row.get("amount")) >= 0 or day is None or (entry["key"], position) in noted
                    or not _TRANSFER_WORDING.search(text) or rails(text)
                    or any(record.get(flag) is True for flag in _TRANSFER_OUT_REFUSED_CONTRIBUTIONS)
                    or record.get("classification") in _TRANSFER_OUT_REFUSED_CLASSES):
                continue
            destination = _TRANSFER_DESTINATION.search(text)
            transfers_out.append((entry, position, row, day, destination.group(1)[-4:] if destination else None))

    def deposits_in(held: bool) -> list[tuple]:
        found = []
        for entry in matchable:
            if len(entry["facts"].digits) < 4:
                continue
            for position, row in entry["rows"]:
                record = row["classification"]
                day = iso_day(row.get("date"))
                text = text_of(row)
                if held:
                    eligible = (record.get("revenue_tier") == "excluded_pending_review"
                                and record.get("revenue_tier_reason") in _OWN_MONEY_HELD_REASONS)
                else:
                    eligible = (record.get("revenue_tier") == "counted_flagged"
                                and record.get("revenue_tier_reason") == "no_payer_printed")
                # Nor a Zelle deposit, which the counted reading may hold as the holder's own name: PNC's 'ZEL FROM'
                # escapes the consumer rail, and Q4 never matches P2P (true_revenue.zelle_deposit).
                if (not eligible or num(row.get("amount")) <= 0 or day is None
                        or (entry["key"], position) in taken or (entry["key"], position) in noted
                        or record.get("revenue_review_status") in REVIEW_DECISIONS
                        or rails(text) or zelle_deposit(text)
                        or is_round_sum(num(row.get("amount"))) or paper_or_cash_deposit(text)):
                    continue
                found.append(((day.toordinal(), entry["order"], position), entry, position, row, day))
        return sorted(found, key=lambda item: item[0])

    transfers_taken: set[tuple] = set()
    for held in (False, True):
        for _sort, credit_entry, credit_position, credit_row, credit_day in deposits_in(held):
            cents = row_cents(credit_row)
            best = None
            for debit_entry, position, row, debit_day, destination in transfers_out:
                if ((debit_entry["key"], position) in transfers_taken or -row_cents(row) != cents
                        or not different_accounts(credit_entry, debit_entry)):
                    continue
                gap = (credit_day - debit_day).days
                if not 0 <= gap <= PACKAGE_TRANSFER_DAYS:
                    continue
                if destination is not None and destination != credit_entry["facts"].digits[-4:]:
                    continue  # the destination veto: it went to another account
                candidate = ((gap, debit_entry["order"], position), debit_entry, position, row, gap)
                if best is None or candidate[0] < best[0]:
                    best = candidate
            if best is None:
                continue
            _rank, debit_entry, position, row, gap = best
            transfers_taken.add((debit_entry["key"], position))
            taken.add((credit_entry["key"], credit_position))
            record = credit_row["classification"]
            credit_side = _match_side(credit_entry, credit_position, credit_row)
            debit_side = _match_side(debit_entry, position, row)
            tier_before, reason_before = record.get("revenue_tier"), record.get("revenue_tier_reason")
            note = {"kind": "own_account_transfer", "moved": not held, "debit": debit_side, "gap_days": gap,
                    "tier_before": tier_before, "reason_before": reason_before}
            if held:
                overlays.setdefault(credit_entry["key"], {})[credit_position] = {"package_match": note}
            else:
                overlays.setdefault(credit_entry["key"], {})[credit_position] = {
                    "revenue_classification": "unverified_deposit",
                    "revenue_tier": "excluded_pending_review",
                    "revenue_tier_reason": "own_account_transfer_matched",
                    "revenue_review_required": True,
                    **revenue_contribution_flags("unverified_deposit", "excluded_pending_review"),
                    "package_match": note,
                }
                moved.setdefault(credit_entry["key"], []).append({
                    "tier": tier_before, "state": record.get("revenue_classification"),
                    "amount": round(num(credit_row.get("amount")), 2),
                })
            overlays.setdefault(debit_entry["key"], {})[position] = {
                "package_match": {"kind": "own_account_transfer", "credit": credit_side, "moved": not held},
            }
            matches.append({
                "kind": "own_account_transfer", "moved": not held,
                "credit": {**credit_side, "currency": credit_entry["facts"].currency, "tier_before": tier_before,
                           "reason_before": reason_before},
                "debit": {**debit_side, "currency": debit_entry["facts"].currency},
                "gap_days": gap,
            })

    # Pass 3: every ready member's debit flags, its R-d positions left out (their places kept, so a location reads).
    debit_flags: list[dict] = []
    for entry in entries:
        for flag in debit_side_flags(entry["kept"], matched_locations=matched_locations.get(entry["key"], set())):
            decided = (decided_candidates.get((entry["key"], flag["source_location"]))
                       if flag["kind"] == "unmatched_deposit_return" else None)
            debit_flags.append({
                "kind": flag["kind"],
                **({"wording": flag["wording"]} if "wording" in flag else {}),
                **({"candidate_decided": decided} if decided else {}),
                "source_job": entry["job_id"], "source_document": entry["filename"], "source_account": entry["account"],
                "source_currency": entry["facts"].currency, "source_location": flag["source_location"],
                "date": flag["date"], "amount": flag["amount"], "description": flag["description"],
            })

    # Pass 4: a bounce-worded return whose funder payment sits in the same account's preceding statement.
    _returned_funder_payments_across(matchable, overlays, matches, location_of, text_of)
    # Pass 4's re-debits: a returned payment the same funder re-debits in the account's next statement leaves
    # the package's numerator.
    represented = _represented_funder_payments_across(matchable, overlays, location_of)
    return PackagePasses(overlays=overlays, matches=matches, debit_flags=debit_flags, unchecked=unchecked, moved=moved,
                         represented=represented)


def _represented_funder_payments_across(matchable: list[dict], overlays: dict, location_of) -> dict:
    """True revenue spec §6.2's package passes, §9.2, §11: the returned-payment rule across a member boundary. A
    returned funder payment still in the withholding numerator (a member's own, rule D's or the named pair's, or one
    pass 4 matched to a return in the next statement) whose same funder re-debits it in ANOTHER member, the statement of
    its return or the one immediately after it in the same account (`same_account`, `consecutive`), leaves the
    package's numerator, by the classifier's rule (analysis.represented_payments.re_debits: the same cents off its
    cycle, or an exact 2x catch-up, dated on or after the return and within one cadence gap after it). The payment's
    package copy gains `contributes_to_withholding_rate` false and `represented_by` (the re-debit's location in its
    statement); paid to lenders, the lender count, the funder rollups and revenue never move, and each statement viewed
    alone keeps its own figures. Returns {(member key, the payment's location): the warning item's represented fields
    (`represented_date`, `_location`, `_kind`, `_job`, `_document`, and `_account` for a statement of several
    accounts)}. As in pass 7c, a paid debit the rate leaves out (`out_of_rate_payment`: a worded lump-sum payoff, as its
    package copy reads after pass 4) is never the re-debit; it stays in the series."""
    from analysis.lender_payment_changes import calendar_for
    from analysis.represented_payments import Attempt, Returned, out_of_rate_payment, re_debits

    def record_of(entry: dict, position: int, row: dict) -> dict:
        return overlaid_row(row, overlays.get(entry["key"]) or {}, position)["classification"]

    following: dict[tuple, dict] = {}
    for entry in matchable:
        for later in matchable:
            if later is not entry and same_account(entry, later) and consecutive(entry["facts"], later["facts"]):
                following.setdefault(entry["key"], later)
                break
    by_member: dict[tuple, list] = {}
    known: dict[tuple, list] = {}
    used: set[tuple] = set()
    out_of_rate: set[tuple] = set()
    returns: list[tuple] = []
    for entry in matchable:
        rows_at = {location_of(row, position): (position, row) for position, row in entry["rows"]}
        for position, row in entry["rows"]:
            record = record_of(entry, position, row)
            day = iso_day(row.get("date"))
            if (num(row.get("amount")) >= 0 or day is None or record.get("classification") != "confirmed_lender"
                    or not record.get("canonical_entity")):
                continue
            if not (record.get("contributes_to_lender_totals") is True or record.get("returned_funder_payment_by")):
                continue
            attempt = Attempt((entry["key"], position), record["canonical_entity"], day, abs(row_cents(row)),
                              (day.toordinal(), entry["order"], position))
            by_member.setdefault(entry["key"], []).append(attempt)
            if out_of_rate_payment(record.get("returned_funder_payment_by"),
                                   record.get("contributes_to_withholding_rate")):
                out_of_rate.add(attempt.key)  # Never the re-debit
            taken = rows_at.get(record.get("represented_by") or "")
            if taken is not None:
                used.add((entry["key"], taken[0]))  # a re-debit its own statement already took
            if not record.get("returned_funder_payment_by"):
                continue
            match = record.get("package_match") or {}
            if match.get("kind") == "returned_funder_payment" and isinstance(match.get("credit"), dict):
                credit = match["credit"]
                credit_entry = next((other for other in matchable if other["job_id"] == credit.get("job")
                                     and other["account"] == credit.get("account_index")), None)
                credit_day = iso_day(credit.get("date"))
            else:
                found = rows_at.get(record["returned_funder_payment_by"])
                credit_entry = entry if found is not None else None
                credit_day = iso_day(found[1].get("date")) if found is not None else None
            if credit_day is None:
                continue
            # Every dated return, a re-debited one included, for the rule's recurring-phase guard.
            known.setdefault(entry["key"], []).append(Returned(attempt, credit_day))
            if (credit_entry is not None and not record.get("represented_by")
                    and record.get("contributes_to_withholding_rate") is True):
                returns.append(((credit_day.toordinal(), entry["order"], position), entry, position, row, attempt,
                                credit_entry, credit_day))
    represented: dict = {}
    for _sort, entry, position, row, attempt, credit_entry, credit_day in sorted(returns, key=lambda item: item[0]):
        members = [credit_entry] + ([following[credit_entry["key"]]] if credit_entry["key"] in following else [])
        allowed = {member["key"] for member in members if member is not entry}
        if not allowed:
            continue
        series = [candidate for key in {entry["key"], *allowed} for candidate in by_member.get(key, [])]
        found = re_debits([Returned(attempt, credit_day)], series, calendar_for(entry["facts"].currency),
                          may_re_debit=lambda _returned, candidate: (candidate.key[0] in allowed
                                                                     and candidate.key not in out_of_rate),
                          taken=list(used),
                          returns=[known_return for key in {entry["key"], *allowed}
                                   for known_return in known.get(key, [])])
        if attempt.key not in found:
            continue
        (re_debit_key, kind) = found[attempt.key]
        used.add(re_debit_key)
        re_debit_entry = next(member for member in members if member["key"] == re_debit_key[0])
        re_debit_row = dict(re_debit_entry["rows"])[re_debit_key[1]]
        re_debit_location = location_of(re_debit_row, re_debit_key[1])
        overlays.setdefault(entry["key"], {}).setdefault(position, {}).update({
            "contributes_to_withholding_rate": False, "represented_by": re_debit_location,
        })
        represented[(entry["key"], location_of(row, position))] = {
            "represented_date": re_debit_row.get("date"), "represented_location": re_debit_location,
            "represented_kind": kind, "represented_job": re_debit_entry["job_id"],
            "represented_document": re_debit_entry["filename"],
            **({"represented_account": re_debit_entry["account"]} if re_debit_entry["account"] is not None else {}),
        }
    return represented


def _paid_funder_payment(record: dict) -> bool:
    """F2(b): a served row's record is a confirmed funder's posted payment counted as paid to lenders that no pair
    reversed and no return took (rule D's funder debits, `_is_paid_funder_debit`, on a dict)."""
    return (
        record.get("classification") == "confirmed_lender"
        and record.get("contributes_to_lender_totals") is True
        and record.get("is_posted") is not False
        and not record.get("reversed_by")
        and not record.get("returned_funder_payment_by")
    )


def _returned_funder_payments_across(matchable: list[dict], overlays: dict, matches: list, location_of, text_of) -> None:
    """True revenue spec §6.2's package passes, §9.2, §11: the package's pass 4, over the members pass 1 reads
    (`matchable`), after passes 1 to 3, adding to their `overlays` and `matches` in place.

    A return is a member's posted, non-duplicate credit that rule D could read (a bounce form, `_returned_payment_credit`;
    out of True, `_RETURN_CREDIT_TIERS`; no lender credit, except one that names the confirmed funder whose payment it
    returns: D1 reads the funder's name on its own return, the named pair's case, which a statement pairs on its own
    but no statement can across two) that its statement left unpaired (no `returns_funder_payment`,
    no pair's `reversed_by` naming it, no earlier pass's note) and that is dated; a credit the revenue side paired with a
    debit of its own statement dated on or before it is left alone (rule D's partner guard: the statement's own pair
    stands), while a partner dated after it cannot be the payment it returns (F2(a)) and holds nothing back. Two of
    these are departures from rule D (spec §20): rule D
    never reads a lender credit, and it leaves alone any credit the revenue side paired that is not its own payment's
    partner, whatever the partner's date. Its payment
    is sought in the SAME account's IMMEDIATELY PRECEDING statement (`same_account` and `consecutive`): a confirmed
    funder's paid payment (`_paid_funder_payment`) of equal cents dated 0 to RETURNED_FUNDER_PAYMENT_WINDOW_DAYS days
    before it, that funder's only where the return names a confirmed funder (`match_known_payee`). Rule D's choice: the
    payment on the RECEIVED ON day the return prints first, then the latest, then the canonical member and the later
    row; and its
    guard: the return is left alone when an equal posted debit that is no confirmed lender's lies in the window, in
    either statement, as near as the chosen payment. The returns are read in (date, member, position) order; each
    payment is taken once.

    The payment's copy leaves the package's paid to lenders (`contributes_to_lender_totals` and, as rule D does,
    `contributes_to_flagged_totals` false; `returned_funder_payment_by` the return's location), keeping its withholding
    and its lender count; both legs carry `package_match` `{kind: "returned_funder_payment", ...}` (the payment's names
    the return, the return's the payment and its funder), and `matches` gains the pair. The package payment
    changes read the payment's copy as a returned attempt (`package_lender_payment_changes`). Revenue never moves;
    each statement viewed alone keeps its own figures."""
    noted = {(key, position) for key, rows in overlays.items() for position in rows}
    taken: set[tuple] = set()
    returns: list[tuple] = []
    for entry in matchable:
        rows_by_location = {location_of(row, position): row for position, row in entry["rows"]}
        named_pairs = {row["classification"].get("reversed_by") for _position, row in entry["rows"]
                       if row["classification"].get("reversed_by")}
        for position, row in entry["rows"]:
            record = row["classification"]
            day = iso_day(row.get("date"))
            if (num(row.get("amount")) <= 0 or day is None or (entry["key"], position) in noted
                    or record.get("returns_funder_payment") or location_of(row, position) in named_pairs
                    or record.get("revenue_tier") not in _RETURN_CREDIT_TIERS
                    or not _returned_payment_credit(text_of(row))):
                continue
            named = match_known_payee(text_of(row), credit=True)
            funder = named.entity if named is not None and named.state == "confirmed_lender" else None
            if record.get("contributes_to_lender_credit_exclusion") is True and funder is None:
                continue  # a lender credit is read only where it names the confirmed funder (the named pair's case)
            if record.get("revenue_match_method") == "matched_reversal_pair":
                partner = rows_by_location.get(record.get("revenue_related_transaction"))
                partner_day = iso_day(partner.get("date")) if isinstance(partner, dict) else None
                if partner_day is None or partner_day <= day:
                    continue
            returns.append(((day.toordinal(), entry["order"], position), entry, position, row, day, funder))
    for _sort, credit_entry, credit_position, credit_row, credit_day, funder in sorted(returns, key=lambda item: item[0]):
        text = text_of(credit_row)
        cents = row_cents(credit_row)
        received = _received_on_day(text)
        best = None
        guards: list[int] = []
        for debit_entry in matchable:
            preceding = (same_account(debit_entry, credit_entry)
                         and consecutive(debit_entry["facts"], credit_entry["facts"]))
            if not (preceding or debit_entry is credit_entry):
                continue
            for position, row in debit_entry["rows"]:
                record = row["classification"]
                day = iso_day(row.get("date"))
                if -row_cents(row) != cents or day is None:
                    continue
                gap = (credit_day - day).days
                if not 0 <= gap <= RETURNED_FUNDER_PAYMENT_WINDOW_DAYS:
                    continue
                if record.get("classification") != "confirmed_lender":
                    guards.append(gap)  # rule D's guard debits, in either statement
                    continue
                if (not preceding or (debit_entry["key"], position) in taken or (debit_entry["key"], position) in noted
                        or not _paid_funder_payment(record)
                        or (funder is not None and record.get("canonical_entity") != funder)):
                    continue
                on_received = received is not None and (day.month, day.day) == received
                rank = (0 if on_received else 1, -day.toordinal(), debit_entry["order"], -position)
                candidate = (rank, debit_entry, position, row, gap)
                if best is None or candidate[0] < best[0]:
                    best = candidate
        if best is None:
            continue
        _rank, debit_entry, position, row, gap = best
        if any(guard <= gap for guard in guards):
            continue
        taken.add((debit_entry["key"], position))
        record = row["classification"]
        credit_side = _match_side(credit_entry, credit_position, credit_row)
        debit_side = {**_match_side(debit_entry, position, row), "funder": record.get("canonical_entity")}
        overlays.setdefault(debit_entry["key"], {})[position] = {
            "contributes_to_lender_totals": False,
            "contributes_to_flagged_totals": False,
            "returned_funder_payment_by": credit_side["source_location"],
            "package_match": {"kind": "returned_funder_payment", "credit": credit_side},
            # A returned payoff attempt rejoins the rate and is no lump sum, as Q5 rules inside a statement
            # (`_returned_payoff_in_rate`).
            **({"contributes_to_withholding_rate": True, "lump_sum_payoff": None}
               if record.get("lump_sum_payoff") else {}),
        }
        overlays.setdefault(credit_entry["key"], {})[credit_position] = {
            "package_match": {"kind": "returned_funder_payment", "debit": debit_side},
        }
        matches.append({
            "kind": "returned_funder_payment", "moved": True,
            "credit": {**credit_side, "currency": credit_entry["facts"].currency,
                       "description": credit_row.get("description")},
            "debit": {**debit_side, "currency": debit_entry["facts"].currency},
            "gap_days": gap,
        })


def package_match_totals(matched: PackagePasses) -> dict:
    """§9.2: the package passes' totals, each count and total only where a pass found a row:
    `returned_deposit_cross_statement_count` / `_total` (the deposits pass 1 took out of True), 
    `own_account_transfer_held_count` / `_total` (the deposits pass 2 held) and
    `own_account_transfer_already_held_count` / `_total` (the held deposits it annotated), the debit flags'
    `<kind>_count` / `<kind>_total` (their magnitude) and `package_match_unchecked_count`."""
    totals: dict = {}
    returned = [match for match in matched.matches if match["kind"] == "returned_deposit" and match["moved"]]
    if returned:
        totals["returned_deposit_cross_statement_count"] = len(returned)
        totals["returned_deposit_cross_statement_total"] = round(
            sum(abs(num(match["credit"]["amount"])) for match in returned), 2)
    # The deposits pass 2 held, and the already-held deposits it only annotated.
    for key, moved in (("own_account_transfer_held", True), ("own_account_transfer_already_held", False)):
        transfers = [match for match in matched.matches
                     if match["kind"] == "own_account_transfer" and match["moved"] is moved]
        if transfers:
            totals[f"{key}_count"] = len(transfers)
            totals[f"{key}_total"] = round(sum(abs(num(match["credit"]["amount"])) for match in transfers), 2)
    for kind in DEBIT_FLAG_KINDS:
        flags = [flag for flag in matched.debit_flags if flag["kind"] == kind]
        if flags:
            totals[f"{kind}_count"] = len(flags)
            totals[f"{kind}_total"] = round(sum(abs(num(flag["amount"])) for flag in flags), 2)
    if matched.unchecked:
        totals["package_match_unchecked_count"] = len(matched.unchecked)
    return totals
