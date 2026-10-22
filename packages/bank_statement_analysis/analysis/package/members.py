"""Admission: the accounts that enter the package math, and the accounts it excludes."""
from __future__ import annotations

import re
from collections.abc import Iterable

from analysis.display_settings import DEFAULTS as SETTINGS_DEFAULTS
from analysis.package.duplicates import package_duplicates
from analysis.package.model import AccountFacts, JobLike, Member, MemberKey, SelectedPackage
from analysis.package.supersede import package_superseded
from analysis.payload_shape import (
    account_content_digest,
    DOCUMENT_KEY as _DOCUMENT_KEY,
    is_document_payload,
    payload_account_count,
    payload_accounts,
)
from analysis.served_view import displayed


def ratified_omissions(analysis: object) -> list[dict]:
    """The RATIFIED sibling omissions this document published, if it is one.

    Q10: *surface the omission,
    do not demote.* A section admitted as omitted on PRINTED evidence beside an
    account that validated independently leaves the document `validated`; what
    it must never do is disappear. So the package — which is where a person
    reads a member's figures as though they were the member's whole banking —
    says that a section of one of its documents was established and not
    published.

    An omission whose reason is NOT a ratified class is not surfaced here: it
    is a publisher defect, `classify_document` already fails the document for
    it, and reporting a defect as "partial" would dress it as a policy.
    """
    from telemetry.record import RATIFIED_OMISSION_REASONS

    # Both shapes: a single-account document that surfaced an omission publishes a `document` block beside its
    # accounts, so gating on `accounts` alone would hide Q10's surface.
    if not isinstance(analysis, dict):
        return []
    block = analysis.get(_DOCUMENT_KEY)
    omissions = (block or {}).get("omitted_sections") or []
    return [
        omission for omission in omissions
        if isinstance(omission, dict)
        and omission.get("reason") in RATIFIED_OMISSION_REASONS
    ]


def _unratified_omissions(analysis: object) -> list[dict]:
    """The omissions whose reason is not a ratified class — a publisher defect.

    A document carrying one is `failed` at `classify_document`, so none of its
    accounts may enter a package: a member contributing money out of a document
    the platform failed would be a total nobody could defend.
    """
    from telemetry.record import RATIFIED_OMISSION_REASONS

    # Both shapes: a single-account document that surfaced an omission publishes a `document` block beside its
    # accounts, so gating on `accounts` alone would hide Q10's surface.
    if not isinstance(analysis, dict):
        return []
    block = analysis.get(_DOCUMENT_KEY)
    omissions = (block or {}).get("omitted_sections") or []
    return [
        omission for omission in omissions
        if not isinstance(omission, dict)
        or omission.get("reason") not in RATIFIED_OMISSION_REASONS
    ]


#: The document-scope note that refuses a document's PACKAGE AGGREGATION.
#: Declared in `analysis/pipeline.py`; named here as the string the package
#: reads, and held to that module's constant by `tests/test_l1s4_transfers.py`
#: so the two cannot drift into two spellings of one refusal.
_AMBIGUOUS_TRANSFER_NOTE = "ambiguous_internal_transfer"


def _document_notes(analysis: object) -> list[str]:
    """The DOCUMENT-scope integrity notes this payload carries, either shape."""
    if not isinstance(analysis, dict):
        return []
    block = analysis.get(_DOCUMENT_KEY) or {}
    notes = block.get("integrity_notes") or []
    return [note for note in notes if isinstance(note, str)]


def internal_transfer_positions(analysis: object, account_index: int | None) -> set[int]:
    """Which of THIS member's postings the document paired as internal (R-d).

    `account_index` is the member's 1-based position in the document's printed
    account order, and `None` for a job publishing today's payload — which has
    one ledger and therefore no sibling for a counterpart to be in, so the
    answer for it is always empty and this costs a single-account package
    nothing.

    The indices come from the document's own `internal_transfers`, which the
    publisher wrote and nothing here recomputes: a package that decided for
    itself which postings were transfers would be applying a transfer grammar
    at the aggregation layer, and there would then be two answers to one
    question.
    """
    if account_index is None or not isinstance(analysis, dict):
        return set()
    block = analysis.get(_DOCUMENT_KEY) or {}
    positions: set[int] = set()
    for transfer in block.get("internal_transfers") or []:
        if not isinstance(transfer, dict):
            continue
        for leg in (transfer.get("a"), transfer.get("b")):
            if (isinstance(leg, (list, tuple)) and len(leg) == 2
                    and leg[0] == account_index - 1
                    and isinstance(leg[1], int) and not isinstance(leg[1], bool)):
                positions.add(leg[1])
    return positions


_MAIN_ACCOUNT_TITLE = re.compile(r"\b(?:business|commercial|corporate)\b", re.IGNORECASE)


def _account_roster(analysis: object) -> list[dict]:
    """Every account a statement judged account by account prints (document.account_roster); [] for any other."""
    document = analysis.get("document") if isinstance(analysis, dict) else None
    roster = document.get("account_roster") if isinstance(document, dict) else None
    return [entry for entry in roster if isinstance(entry, dict)] if isinstance(roster, list) else []


_NOT_A_MAIN_ACCOUNT = frozenset({"credit_card", "loan"})


def main_account_rank(kind, title) -> int:
    """How likely an account is the one a lender funds, as the dashboard ranks it (app.js mainAccountRank): a
    checking account first, then one whose title names no kind (a product name such as "... Plus Banking" can be the
    operating account), then any other deposit account; a business title one higher within its tier; a card or a
    loan never."""
    if kind in _NOT_A_MAIN_ACCOUNT:
        return -1
    tier = 4 if kind == "checking" else 2 if kind in (None, "") else 0
    return tier + (1 if _MAIN_ACCOUNT_TITLE.search(str(title or "")) else 0)


def _unverified_main_account(roster: list[dict]) -> dict | None:
    """The statement's main account when it was not verified, as the dashboard decides it (app.js
    unverifiedMainAccount): a HELD account of the best rank (main_account_rank). Which account a lender funds is then
    undetermined, and no other account stands in for it. None when no account of the best rank is held, when the
    best rank is a card's or a loan's (no account a lender funds), or there is no roster."""
    if not roster:
        return None
    ranks = [main_account_rank(entry.get("kind"), entry.get("title")) for entry in roster]
    best = max(ranks)
    held = [entry for entry, rank in zip(roster, ranks) if rank == best and entry.get("status") == "held"]
    return held[0] if held and best >= 0 else None


def _idle_main_account(roster: list[dict]) -> dict | None:
    """The statement's main account when it printed no activity this period (the dashboard keeps showing the active
    account, app.js idleMainAccount): the idle account of the best rank (main_account_rank), when no account of that
    rank was verified or held. None otherwise."""
    if not roster:
        return None
    ranks = [main_account_rank(entry.get("kind"), entry.get("title")) for entry in roster]
    best = max(ranks)
    top = [entry for entry, rank in zip(roster, ranks) if rank == best]
    if best < 0 or any(entry.get("status") in ("published", "held") for entry in top):
        return None
    return next((entry for entry in top if entry.get("status") == "idle"), None)


def package_members(
    jobs: Iterable[JobLike], *, settings: dict | None = None,
    repeated_accounts: dict[str, dict[int, str]] | None = None,
) -> tuple[list[Member], list[dict]]:
    """`(members, excluded)` — what enters the package math, and what does not.

    Each member carries its job's `analysis_rules_outdated`, read off the displayed copy below: the flag sits at the
    top of a statement, so an account of a statement of several accounts, which is the member, does not carry it.

    A member is ONE ACCOUNT. A job publishing today's payload is one member and
    is admitted exactly as it always was — this function cannot change what a
    single-account package computes, because for such a job it yields one
    member whose account is the stored analysis as the dashboard
    shows it (`displayed`: the owner's NSF basis and flag groups applied to a
    copy; the stored record is never rewritten and every other field is the
    stored one). Every member is displayed with the one `settings` snapshot the
    caller passes (None applies the defaults), so a setting saved mid-request
    cannot split the members across two NSF bases or two sets of ticked flag
    groups.

    Two rules apply to a job that publishes several accounts, and both are the
    package's own arithmetic protecting itself:

    * **membership requires the account's OWN `validated`.** A package sums,
      counts and days-weights its members. An account the platform did not
      validate has no authoritative figure to contribute, and admitting it
      because a SIBLING validated would let one account's proof carry
      another's numbers. Excluded accounts are RETURNED, never dropped: the
      package publishes what it left out.
    * **no average over one content digest twice.** Two accounts of one
      document publishing identical content are one account published twice,
      and every cross-account total here — a sum, a count, the days-weighted
      ADB — would count that money twice. `document_report_to_dict` refuses to
      publish such a document; this is the same refusal standing where the
      arithmetic happens, because a payload can reach a package from a store
      that was written before the publisher learned to refuse it.

    An account `repeated_accounts` names (one an earlier job of the package
    already published, `package_duplicates`) is excluded as a duplicate, never
    summed twice; its document's other accounts stay members.
    """
    from telemetry.record import classify_outcome

    members: list[Member] = []
    excluded: list[dict] = []
    if settings is None:
        settings = dict(SETTINGS_DEFAULTS)
    for job in jobs:
        analysis = displayed(job.analysis or {}, settings=settings)
        outdated = isinstance(analysis, dict) and analysis.get("analysis_rules_outdated") is True
        roster = _account_roster(analysis)
        unverified, idle = _unverified_main_account(roster), _idle_main_account(roster)
        if unverified is not None or idle is not None:
            # The statement's main account (its business checking account, as the dashboard shows it) was not
            # verified, or printed no activity and needs review: no other account of the statement stands in for it
            # in the package's figures.
            excluded.append({
                "job_id": job.id,
                "filename": getattr(job, "filename", None),
                "account_index": None,
                "account_count": len(roster),
                "outcome": "withheld",
                "reason": "main_account_unverified" if unverified is not None else "main_account_idle",
            })
            continue
        if not is_document_payload(analysis):
            members.append(Member(
                key=MemberKey(job.id, None), job=job, account=analysis, account_count=1,
                facts=AccountFacts.of(analysis),
                internal_transfer_positions=internal_transfer_positions(job.analysis, None),
                analysis_rules_outdated=outdated,
            ))
            continue
        surface = "webapp/app.py::_package_members"
        accounts = payload_accounts(analysis, surface=surface)
        count = payload_account_count(analysis, surface=surface)
        unratified = _unratified_omissions(analysis)
        digests = [account_content_digest(account) for account in accounts]
        if len(set(digests)) != len(digests):
            raise ValueError(
                "two accounts of one document publish identical content; a "
                "duplicate section would be double-counted by every "
                "cross-account total in this package "
                "(document_publishes_duplicate_account)"
            )
        ambiguous = _AMBIGUOUS_TRANSFER_NOTE in _document_notes(analysis)
        repeated = (repeated_accounts or {}).get(job.id) or {}
        for index, account in enumerate(accounts, start=1):
            if index in repeated:
                excluded.append(_duplicate_exclusion(job, index, count, repeated[index], "duplicate_statement"))
                continue
            outcome, reason = classify_outcome(account)
            if ambiguous:
                # §3.3 / Q2. A posting with two or more admissible counterparts
                # leaves it unestablished WHICH sibling row the money moved to,
                # so this document's accounts cannot be aggregated without
                # either double-counting a movement or deleting a printed
                # deposit. The package refuses to aggregate it and says so.
                #
                # It refuses the AGGREGATION and nothing else: each account
                # keeps its own outcome, its own ledger and its own ADB, both
                # printed legs stay where the paper printed them, and the
                # excluded set below is published rather than dropped.
                excluded.append({
                    "job_id": job.id,
                    "filename": getattr(job, "filename", None),
                    "account_index": index,
                    "account_count": count,
                    "outcome": outcome,
                    "reason": "document_transfer_pairing_ambiguous",
                })
                continue
            if unratified:
                # The DOCUMENT failed (L1-C17). Its accounts may not carry
                # money into a package on their own validation.
                excluded.append({
                    "job_id": job.id,
                    "filename": getattr(job, "filename", None),
                    "account_index": index,
                    "account_count": count,
                    "outcome": "failed",
                    "reason": "document_omission_unratified",
                })
                continue
            if outcome != "validated":
                excluded.append({
                    "job_id": job.id,
                    "filename": getattr(job, "filename", None),
                    "account_index": index,
                    "account_count": count,
                    "outcome": outcome,
                    "reason": reason,
                })
                continue
            members.append(Member(
                key=MemberKey(job.id, index), job=job, account=account, account_count=count,
                facts=AccountFacts.of(account),
                internal_transfer_positions=internal_transfer_positions(job.analysis, index),
                analysis_rules_outdated=outdated,
            ))
    return members, excluded


def _duplicate_exclusion(job: JobLike, index: int, count: int, duplicate_of: str, reason: str) -> dict:
    """An account of a document left out because another kept statement prints it (`duplicate_of`, the kept job)."""
    return {
        "job_id": job.id,
        "filename": getattr(job, "filename", None),
        "account_index": index,
        "account_count": count,
        "outcome": "duplicate",
        "reason": reason,
        "is_duplicate": True,
        "duplicate_of": duplicate_of,
    }


def select_members(jobs: Iterable[JobLike], settings: dict) -> SelectedPackage:
    """Which jobs and accounts the package reads, before any figure: the repeated statements left out
    (`package_duplicates`), the accounts admitted (`package_members`, once, on one displayed copy of each kept job),
    then the shorter printouts other kept statements print (`package_superseded`, over the admitted accounts).

    A job whose every account is superseded (all its stored accounts, admitted or not) is dropped as a repeat is, in
    its listed place, and its members and exclusions go with it. A superseded account of a document whose other
    accounts stay is excluded as a duplicate in its own place, with the supersede's reason; the job, its other
    exclusions and its ratified omissions stay, even when no account of it is left a member."""
    listed = list(jobs)
    kept, dropped, repeated_accounts, duplicate_groups = package_duplicates(listed)
    members, excluded = package_members(kept, settings=settings, repeated_accounts=repeated_accounts)
    kept, superseded_jobs, superseded_accounts, overlapping = package_superseded(
        kept, repeated_accounts, members={member.key for member in members})
    if superseded_jobs or superseded_accounts:
        first_place: dict[str, int] = {}
        for place, job in enumerate(listed):
            first_place.setdefault(job.id, place)
        dropped = sorted(
            [*dropped, *({**entry, "position": first_place[entry["job"].id]} for entry in superseded_jobs)],
            key=lambda entry: entry["position"],
        )
        for job_id, accounts in superseded_accounts.items():
            repeated_accounts.setdefault(job_id, {}).update(
                {index: covering for index, (covering, _reason) in accounts.items()})
        members, excluded = _without_superseded(kept, members, excluded, superseded_accounts)
    return SelectedPackage(
        listed=listed, members=members, excluded=excluded, dropped=dropped, duplicate_groups=duplicate_groups,
        duplicate_accounts=sum(len(accounts) for accounts in repeated_accounts.values()), overlapping=overlapping,
        omitted_sections=[omission for job in kept for omission in ratified_omissions(job.analysis or {})],
    )


def _without_superseded(
    kept: list[JobLike], members: list[Member], excluded: list[dict],
    superseded_accounts: dict[str, dict[int, tuple[str, str]]],
) -> tuple[list[Member], list[dict]]:
    """`package_members`'s answer for `kept` once each superseded account is repeated: the kept jobs' members less
    those accounts, and their exclusions with each of those accounts excluded as a duplicate. Every exclusion keeps the
    kept jobs' order, then the accounts' (a job-level exclusion is its job's only one)."""
    place = {job.id: position for position, job in enumerate(kept)}
    left, rows = [], [entry for entry in excluded if entry["job_id"] in place]
    for member in members:
        if member.key.job_id not in place:
            continue
        superseded = superseded_accounts.get(member.key.job_id, {}).get(member.key.account_index)
        if superseded is None:
            left.append(member)
            continue
        covering, reason = superseded
        rows.append(_duplicate_exclusion(member.job, member.key.account_index, member.account_count, covering, reason))
    rows.sort(key=lambda entry: (place[entry["job_id"]], entry["account_index"] or 0))
    return left, rows
