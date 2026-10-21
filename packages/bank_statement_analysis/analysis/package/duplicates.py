"""Repeated statements: the copy a package keeps, and the copies it lists as left out."""
from __future__ import annotations

import hashlib
import json
from collections import Counter

from analysis import zelle_view
from analysis.flagged_view import apply_flagged_groups_to_payload
from analysis.package.model import (
    is_money_value,
    num,
    numbers_conflict,
    printed_account_digits,
    REVIEW_DECISIONS,
    row_cents,
    row_day,
    statement_currency,
    stored_accounts,
)
from analysis.payload_shape import account_content_digest, is_document_payload
from analysis.revenue_view import apply_revenue_view


def _account_identities(account: object) -> frozenset[str]:
    """§4.6: what makes two accounts of two jobs ONE statement.

    * its published content (`account_content_digest`), when its ledger prints at least one transaction: a payload
      with no ledger publishes too little to tell two statements apart, and is never matched on it;
    * its statement key, when every part of it is printed: the bank, the account number's last four digits, the
      period's first and last day, and the opening and closing balance. A re-download of the same statement (other
      bytes, so another content hash) prints the same key;
      * its ledger key (`ledger:`), when it prints both period days, both balances and at
      least one ledger row: the period's days, the two balances and a hash over every ledger row's day and signed
      cents (`row_day`, `row_cents`), whatever its classification. It is a parse identity no review decision, rules
      version or setting changes, and it reads no bank and no account number, so another reading of a statement
      whose bank or number was not read (or was read on one reading only) still matches it; `package_duplicates`
      never joins it between two printed full numbers that conflict.

    An empty set when none is established: such an account is never taken for a copy of another."""
    if not isinstance(account, dict) or not isinstance(account.get("statement"), dict):
        return frozenset()
    statement = account["statement"]
    identities: set[str] = set()
    ledger = [row for row in statement.get("transactions") or [] if isinstance(row, dict)]
    if ledger:
        identities.add("digest:" + account_content_digest(account))
    bank = " ".join(str(statement.get("bank") or "").split()).casefold()
    digits = "".join(character for character in str(statement.get("account_number") or "") if character.isdigit())
    start, end = statement.get("period_start"), statement.get("period_end")
    opening, closing = statement.get("beginning_balance"), statement.get("ending_balance")
    printed = (isinstance(start, str) and start and isinstance(end, str) and end
               and is_money_value(opening) and is_money_value(closing))
    if printed and bank and len(digits) >= 4:
        identities.add(f"statement:{bank}|{digits[-4:]}|{start}|{end}|{float(opening):.2f}|{float(closing):.2f}")
    if printed and ledger:
        rows = json.dumps(sorted((row_day(row), row_cents(row)) for row in ledger))
        identities.add(f"ledger:{start}|{end}|{float(opening):.2f}|{float(closing):.2f}|"
                       + hashlib.sha256(rows.encode("utf-8")).hexdigest())
    return frozenset(identities)


#: A copy's rank keys, in order, by the name a left-out copy's row gives for the kept one winning on it
#: (`duplicate_kept_because`); copies alike on all three keep the one listed first (`listed_first`).
_KEPT_BECAUSE = ("has_analysis", "current_rules", "has_review_decisions")


def _copy_rank(job) -> tuple[int, int, int]:
    """How good a copy of a repeated statement is, lower first: 0 when the job is done and publishes an account (else
    1); 0 when its analysis is current, 1 when an account of its served copy (`apply_revenue_view`) has
    `revenue_established` False or a record lacks or predates `CLASSIFICATION_VERSION` (the `analysis_rules_outdated`
    rule of analysis/flagged_view.py; a job with no account is never current); 0 when a posted credit of it carries
    the analyst's decision (`revenue_review_status` confirmed or rejected). A decision in EITHER Zelle reading counts
    (the stored records and the counted reading's, analysis/zelle_view.py): a Yes-mode reject on a Zelle row lives
    only in the counted reading's edits, the stored reading having gone back to its analysis state."""
    analysis = getattr(job, "analysis", None)
    accounts = stored_accounts(analysis)
    has_analysis = getattr(job, "status", None) == "done" and bool(accounts)
    current = False
    if accounts:
        served = apply_revenue_view(apply_flagged_groups_to_payload(analysis, enabled={}))
        current = (
            isinstance(served, dict) and served.get("analysis_rules_outdated") is not True
            and all((account.get("metrics") or {}).get("revenue_established") is not False
                    for account in stored_accounts(served))
        )
    counted = zelle_view.reading(analysis, counted=True) if accounts else analysis
    decided = any(
        isinstance(row, dict) and num(row.get("amount")) > 0 and isinstance(row.get("classification"), dict)
        and row["classification"].get("is_posted") is not False
        and row["classification"].get("revenue_review_status") in REVIEW_DECISIONS
        for reading in ((accounts,) if counted is analysis else (accounts, stored_accounts(counted)))
        for account in reading
        for row in (account.get("statement") or {}).get("transactions") or []
    )
    return (0 if has_analysis else 1, 0 if current else 1, 0 if decided else 1)


def _kept_because(kept_rank: tuple, dropped_rank: tuple) -> str:
    """The first rank key on which the kept copy beats the left-out one, else `listed_first`."""
    return next((name for name, kept, dropped in zip(_KEPT_BECAUSE, kept_rank, dropped_rank) if kept < dropped),
                "listed_first")


def package_duplicates(jobs) -> tuple[list, list[dict], dict[str, dict[int, str]], list[dict]]:
    """The package's jobs with every repeated statement left out, before any member is expanded.

    D-3 surfaced a repeated content hash and nothing acted on it, so one statement listed twice doubled True,
    Verified, Counted, Held, Non-revenue and the month count, and the package stayed Approved. MCA practice removes a
    duplicate statement (standard §4.6(3)). A job is left out when it repeats a kept job's id (`same_job`: the same
    job listed twice; it adds nothing and is listed once), its content hash (`same_content`: the same PDF uploaded
    twice), or, account by account, every account's statement identity (`same_statement`: a re-download whose bytes
    differ; `_account_identities`). A job some of whose accounts repeat a kept job's keeps its other accounts; the
    repeated ones are named in `repeated_accounts` (job id -> {account index: the kept job's id}) for
    `package_members` to leave out. The accounts of ONE document are never compared with each other here: each
    carries the job's hash, and two of them publishing one content is the publisher's refusal
    (`document_publishes_duplicate_account`).

    Which copy is kept. The jobs claim their ids, hashes and identities in the order of their rank (`_copy_rank`: a
    completed analysis, then the current rules, then the analyst's review decisions, then the listed place), so a
    failed, queued, processing or interrupted copy, a copy analysed under older rules or a copy without the decisions
    recorded on another never takes a better copy's place; copies alike keep the one listed first. Each left-out
    entry says why its kept copy was kept (`kept_because`).

    A statement key (`statement:`, which reads only the account number's last four digits) never joins two accounts
    whose printed full numbers conflict (`printed_account_digits`, `numbers_conflict`): each key holds every kept
    job that claimed it, in claim order, and an account matches the first of them whose number does not conflict with
    its own, in the same-statement test, in the choice of the job it repeats and in `repeated_accounts` alike. A
    content digest (`digest:`, which covers the whole payload, the number included) matches as before, and so does a
    masked or a four-digit print. A ledger key (`ledger:`, the period, the balances and every ledger row's day and
    signed cents, no bank and no number) is read as a statement key is, so another reading of a statement whose bank
    or number was not read is the same statement (`same_statement`, the copy kept by `_copy_rank`), never between
    conflicting printed numbers.

    Returns ``(kept jobs, dropped, repeated_accounts, groups)`` in LISTED order: `dropped` lists ``{"job",
    "duplicate_of", "reason", "kept_because", "position"}`` (`position`: the job's place in the list); each group lists
    the kept job and then every job that repeats it (D-3's shape: `content_sha256` is the kept job's hash)."""
    listed = list(jobs)
    #: Each listed job's accounts' identities and printed digits, read once (a content digest hashes a whole payload).
    identities_of: list[list[frozenset[str]]] = []
    digits_of: list[list[str]] = []
    claims: list[set[tuple[str, str]]] = []
    for job in listed:
        accounts = stored_accounts(getattr(job, "analysis", None))
        identities_of.append([_account_identities(account) for account in accounts])
        digits_of.append([printed_account_digits(account) for account in accounts])
        keys = {("id", str(job.id))}
        if getattr(job, "content_sha256", None):
            keys.add(("hash", str(job.content_sha256)))
        keys.update(("identity", key) for identities in identities_of[-1] for key in identities)
        claims.append(keys)
    shared = Counter(key for keys in claims for key in keys)
    # Only a job that shares an id, a hash or an identity with another listed job can meet a copy of itself, so only
    # such a job is ranked (the rank reads a served copy of the analysis); the others claim what no other job claims.
    ranks = [_copy_rank(job) if any(shared[key] > 1 for key in keys) else (0, 0, 0)
             for job, keys in zip(listed, claims)]
    kept_positions: list[int] = []
    dropped: list[dict] = []
    repeated_accounts: dict[str, dict[int, str]] = {}
    first_by_id: dict[str, int] = {}
    first_by_hash: dict[str, int] = {}
    #: identity key -> [(the kept job's position, its account's printed digits)], in claim order.
    first_by_identity: dict[str, list[tuple[int, str]]] = {}

    def claimed(key: str, digits: str) -> int | None:
        """The position of the kept job an account with this identity key and these printed digits repeats."""
        entries = first_by_identity.get(key)
        if not entries:
            return None
        if key.startswith("digest:"):
            return entries[0][0]
        return next((position for position, other in entries if not numbers_conflict(digits, other)), None)

    for position in sorted(range(len(listed)), key=lambda place: (ranks[place], place)):
        job = listed[position]
        content_hash = getattr(job, "content_sha256", None)
        identities, digits = identities_of[position], digits_of[position]
        first, reason = None, None
        if job.id in first_by_id:
            first, reason = first_by_id[job.id], "same_job"
        elif content_hash and content_hash in first_by_hash:
            first, reason = first_by_hash[content_hash], "same_content"
        elif identities and all(any(claimed(key, own) is not None for key in account)
                                for account, own in zip(identities, digits)):
            first = next(earlier for key in sorted(identities[0])
                         if (earlier := claimed(key, digits[0])) is not None)
            reason = "same_statement"
        if first is not None:
            dropped.append({"job": job, "duplicate_of": listed[first].id, "reason": reason,
                            "kept_because": _kept_because(ranks[first], ranks[position]), "position": position,
                            "kept_position": first})
            continue
        if is_document_payload(getattr(job, "analysis", None)):
            for index, (account, own) in enumerate(zip(identities, digits), start=1):
                earlier = next((place for key in sorted(account) if (place := claimed(key, own)) is not None), None)
                if earlier is not None:
                    repeated_accounts.setdefault(job.id, {})[index] = listed[earlier].id
        kept_positions.append(position)
        first_by_id[job.id] = position
        if content_hash:
            first_by_hash.setdefault(content_hash, position)
        for account, own in zip(identities, digits):
            for key in account:
                first_by_identity.setdefault(key, []).append((position, own))
    dropped.sort(key=lambda entry: entry["position"])
    groups: dict[int, dict] = {}
    for entry in dropped:
        first = listed[entry["kept_position"]]
        group = groups.setdefault(entry.pop("kept_position"), {
            "content_sha256": getattr(first, "content_sha256", None),
            "job_ids": [first.id],
            "filenames": [first.filename],
            "count": 1,
        })
        group["job_ids"].append(entry["job"].id)
        group["filenames"].append(entry["job"].filename)
        group["count"] += 1
    kept = [listed[position] for position in sorted(kept_positions)]
    return kept, dropped, repeated_accounts, [groups[position] for position in sorted(groups)]


def duplicate_row(entry: dict) -> dict:
    """A left-out job's row in `documents`: what identifies it and the job it repeats, and no figure, because none of
    its money enters the package. Why the job kept in its place was kept (`duplicate_kept_because`; None for a
    printout the account's other statements print)."""
    job = entry["job"]
    accounts = stored_accounts(job.analysis)
    statement = (accounts[0].get("statement") or {}) if accounts else {}
    return {
        "id": job.id,
        "filename": job.filename,
        "status": job.status,
        "content_sha256": getattr(job, "content_sha256", None),
        "is_duplicate": True,
        "duplicate_of": entry["duplicate_of"],
        "duplicate_reason": entry["reason"],
        "duplicate_kept_because": entry.get("kept_because"),
        "bank": statement.get("bank"),
        "account": statement.get("account_number"),
        "currency": statement_currency(accounts[0]) if accounts else None,
        "period_start": statement.get("period_start"),
        "period_end": statement.get("period_end"),
    }
