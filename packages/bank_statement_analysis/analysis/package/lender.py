"""Lender payment changes and active positions read across the statements of a package."""
from __future__ import annotations

from analysis import active_positions as active_positions_module, lender_payment_changes as payment_changes_module
from analysis.dates import parse_date
from analysis.package.calendar import iso_day, statement_month
from analysis.package.members import internal_transfer_positions
from analysis.package.model import (
    bank_key,
    PACKAGE_CONSECUTIVE_DAYS,
    printed_account_digits,
    same_account,
    statement_currency,
)


#: True revenue spec §9.2: a member chains to the statement before it when it starts at most this many days before
#: that statement ends (an overlap), or up to PACKAGE_CONSECUTIVE_DAYS after.
LENDER_CHAIN_OVERLAP_DAYS = 5


def package_lender_payment_changes(members: list[tuple], overlays: dict | None = None, *,
                                   reading: dict | None = None) -> tuple[list[dict] | None, list[dict]]:
    """True revenue spec §9.2: each lender payment series read across the package's consecutive statements of ONE
    account, recomputed on every call from the kept members' displayed copies (with the package passes' overlay:
    passes 1 to 3 change no debit's lender fields; pass 4 marks a payment it
    matched as returned (`returned_funder_payment_by`, `contributes_to_lender_totals` false), so a series reads it as
    a returned attempt, not a payment, as the restore does inside one statement) and never written back.
    Information only: no total, rollup, gate or revenue figure reads it.

    A member enters when it is analysed and its served detection carries `lender_payment_changes` (it was analysed with
    the check); otherwise it is listed and left out (`not_ready`, `analysed_before_check`). Members are visited in
    canonical order (period start, job, account) and each joins the first chain whose last member is the same account
    and ends between LENDER_CHAIN_OVERLAP_DAYS days after and PACKAGE_CONSECUTIVE_DAYS days before it starts; otherwise
    it starts a chain. A member with no declared currency, no period, or fewer than four account digits and no balance
    chain is checked alone and listed (in a package of two members or more).
    `analysis.lender_payment_changes.payment_changes` runs per chain (its own overlap de-duplication included); each
    item gains its statement's source fields, a change item the statements of its last old payment (`from_*`) and of
    its new regime's second payment (`to_*`) and `cross_statement`; a stop whose series pays or is attempted after it
    in a chain of another account of the package gains `continues_in_other_account` and is never confirmed. Only when
    that first payment or attempt comes within the stop's grace window, counted in the business days the two chains'
    statements cover (`covered_business_days`); a later one gains `reappears_in_other_account` (with
    `covered_business_days`) and leaves the stop as its own chain reads it.

    Returns (items, unchecked): items is None when no member was assessed. §9.2: `reading`, when given, receives the
    chains (`chains`, each a list of member entries in period order) and each stop's continuation in another account
    (`links`, analysis/active_positions.py `PositionLink`s), which `package_active_positions` reads; the items are
    the same with or without it."""
    entries: list[dict] = []
    unchecked: list[dict] = []
    links: list = []
    if reading is not None:
        reading["chains"] = []
        reading["links"] = links
    for job, analysis, account_index, _count in members:
        source = {"source_job": job.id, "source_document": getattr(job, "filename", None),
                  **({"source_account": account_index} if account_index is not None else {})}
        statement = analysis.get("statement") if isinstance(analysis, dict) else None
        if not (job.status == "done" and job.analysis is not None and isinstance(statement, dict)):
            unchecked.append({**source, "reason": "not_ready"})
            continue
        detection = analysis.get("detection")
        if not isinstance(detection, dict) or not isinstance(detection.get("lender_payment_changes"), list):
            unchecked.append({**source, "reason": "analysed_before_check"})
            continue
        member_overlay = (overlays or {}).get((job.id, account_index)) or {}
        excluded = internal_transfer_positions(job.analysis, account_index)
        rows = []
        for position, transaction in enumerate(statement.get("transactions") or []):
            record = transaction.get("classification") if isinstance(transaction, dict) else None
            if position in excluded or not isinstance(record, dict):
                continue
            if position in member_overlay:
                record = {**record, **member_overlay[position]}
            if record.get("is_posted") is False or record.get("duplicate_of"):
                continue
            rows.append(record)
        entries.append({
            **source, "job_id": job.id, "currency": statement_currency(analysis), "bank": bank_key(statement),
            "digits": printed_account_digits(analysis),
            "name": " ".join(str(statement.get("account_name") or "").split()).casefold(),
            "start": iso_day(statement.get("period_start")), "end": iso_day(statement.get("period_end")),
            "opening": statement.get("beginning_balance"), "closing": statement.get("ending_balance"),
            "order": (str(statement.get("period_start") or ""), str(job.id), account_index or 0),
            # A statement holding no rows list is read here as empty, as before, and is N/A to
            # `package_active_positions`, never 0.
            "has_rows": isinstance(statement.get("transactions"), list),
            "rows": payment_changes_module.StatementRows(rows, statement.get("period_start"),
                                                          statement.get("period_end"), statement_currency(analysis)),
        })
    if not entries:
        return None, unchecked
    entries.sort(key=lambda entry: entry["order"])
    chains: list[list[dict]] = []
    for entry in entries:
        for chain in chains:
            last = chain[-1]
            if (last["end"] is not None and entry["start"] is not None and same_account(last, entry)
                    and -LENDER_CHAIN_OVERLAP_DAYS <= (entry["start"] - last["end"]).days <= PACKAGE_CONSECUTIVE_DAYS):
                chain.append(entry)
                break
        else:
            chains.append([entry])
    if reading is not None:
        reading["chains"] = chains
    if len(members) >= 2:
        for chain in chains:
            if len(chain) != 1:
                continue
            entry = chain[0]
            reason = ("no_currency" if entry["currency"] is None
                      else "no_period" if entry["start"] is None or entry["end"] is None
                      else "no_account_number" if len(entry["digits"]) < 4 else None)
            if reason is not None:
                unchecked.append({key: entry[key] for key in ("source_job", "source_document", "source_account")
                                  if key in entry} | {"reason": reason})

    def statement_source(chain: list[dict], index: int, prefix: str = "source") -> dict:
        entry = chain[index]
        fields = {f"{prefix}_job": entry["source_job"], f"{prefix}_document": entry["source_document"]}
        if "source_account" in entry:
            fields[f"{prefix}_account"] = entry["source_account"]
        return fields

    items: list[dict] = []
    for chain_index, chain in enumerate(chains):
        for item in payment_changes_module.payment_changes([entry["rows"] for entry in chain]):
            published = payment_changes_module.public_item(item)
            source = chain[item["_source_statement"]]
            published.update(statement_source(chain, item["_source_statement"]))
            published["source_currency"] = source["currency"]
            published["source_period_end"] = source["rows"].period_end
            if item["kind"] in ("decrease", "increase", "cadence_change"):
                published.update(statement_source(chain, item["_from_statement"], "from"))
                published.update(statement_source(chain, item["_to_statement"], "to"))
                origin, target = chain[item["_from_statement"]], chain[item["_to_statement"]]
                published["cross_statement"] = (origin["job_id"], origin.get("source_account")) != (
                    target["job_id"], target.get("source_account"))
            if item["kind"] == "stop":
                # F5: the series continues from another account of the deal (a chain of no member of this account).
                # Only when its first payment or attempt there comes within the stop's grace window, counted in the
                # business days the two chains' statements cover (a third account's never count); a later one
                # leaves the stop as its own chain reads it and is named apart.
                found = None
                reappears = None
                calendar = payment_changes_module.calendar_for(chain[0]["currency"])
                for other_index, other in enumerate(chains):
                    if other_index == chain_index or any(same_account(one, two) for one in chain for two in other):
                        continue
                    activity = payment_changes_module.series_activity_after(
                        [entry["rows"] for entry in other], item["_series_key"], item["_last_presence"])
                    if activity is None:
                        continue
                    covered = payment_changes_module.covered_business_days(
                        item["_last_presence"], activity["date"],
                        [(entry["start"], entry["end"]) for entry in chain + other], calendar)
                    key = (activity["date"], other_index)
                    if covered <= item["grace_business_days"]:
                        if found is None or key < found[0]:
                            found = (key, other, activity)
                    elif reappears is None or key < reappears[0]:
                        reappears = (key, other, activity, covered)
                if found is not None:
                    _key, other, activity = found
                    published["continues_in_other_account"] = {
                        **statement_source(other, activity["statement"]),
                        "first_date": activity["date"], "amount": activity["amount"]}
                    published["stop_confirmed"] = False
                    # The position continued there counts once.
                    links.append(active_positions_module.PositionLink(
                        chain_index, tuple(item["_series_key"]), item["position"], found[0][1],
                        parse_date(activity["date"]), activity["amount"]))
                elif reappears is not None:
                    _key, other, activity, covered = reappears
                    published["reappears_in_other_account"] = {
                        **statement_source(other, activity["statement"]),
                        "first_date": activity["date"], "amount": activity["amount"],
                        "covered_business_days": covered}
            items.append(published)
    return items, unchecked


def package_active_positions(rows: list[dict], reading: dict) -> list[dict]:
    """True revenue spec §9.2, §10: each member row gains `active_positions` and `possible_positions` (set in place)
    and the package's months are returned.

    Each chain `package_lender_payment_changes` read (one account's consecutive statements, the package passes'
    overlay applied) is read once by analysis/active_positions.py, over each member's printed period, so a stream that
    runs across months is one position in each. A member no chain holds (never analysed, or analysed before the check)
    or whose statement holds no rows list reads N/A, never 0, and so does the calendar month it stands for
    (`statement_month`, the Monthly Statements table's rule). A month adds its accounts up; a position the payment
    changes continue in another account counts once where it is handed over. Information only: nothing stored or summed
    reads it."""
    chains = reading.get("chains") or []

    def member_id(entry: dict) -> str:
        return entry["job_id"] if "source_account" not in entry else f"{entry['job_id']}#account_{entry['source_account']}"

    held = {member_id(entry) for chain in chains for entry in chain if entry.get("has_rows", True)}
    unread = {month for row in rows if row.get("id") not in held
              if (month := statement_month(row.get("period_start"), row.get("period_end"))) is not None}
    per_statement, by_month = active_positions_module.package_active_positions(
        [[entry["rows"] for entry in chain] for chain in chains],
        months=[[statement_month(entry["start"], entry["end"]) if entry.get("has_rows", True) else None
                 for entry in chain] for chain in chains],
        links=reading.get("links") or (), unread_months=unread)
    counts = {member_id(entry): per_statement[chain_index][index]
              for chain_index, chain in enumerate(chains) for index, entry in enumerate(chain)
              if entry.get("has_rows", True)}
    for row in rows:
        row.update(counts.get(row.get("id"), active_positions_module.NOT_AVAILABLE))
    return by_month
