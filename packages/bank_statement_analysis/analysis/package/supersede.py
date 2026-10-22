"""Shorter printouts another statement of the account covers, left out of the package; other overlaps
that share credits are named."""
from __future__ import annotations

from collections import Counter

from analysis.package.calendar import iso_day
from analysis.package.model import (
    AccountFacts,
    is_money_value,
    num,
    numbers_conflict,
    row_cents,
    row_day,
    stored_accounts,
)
from analysis.payload_shape import is_document_payload


#: A statement period of more days than this is more than a month (`package_superseded` tests it first).
_MONTH_DAYS = 31


#: The most days two statements of one account may share and still be named only when they share a credit (a
#: boundary day or a cycle that closes on the day the next opens; every one of the corpus's overlapping
#: distinct-period pairs shares exactly one day).
_OVERLAP_BOUNDARY_DAYS = 3


#: The most days apart two statements of one account may print one credit (equal cents) and still share it
#: (`_shared_credits`): a transaction or value date, a pending item posted a day later.
_OVERLAP_SHIFT_DAYS = 3


#: The fewest days of a month-length statement, the only kind a printout of more than a month is left out in favour of
#: in `package_superseded`'s first phase (7,096 of the corpus's 7,241 printed periods run 28 to 35 days; a shorter
#: one is a partial month or a printout).
_FULL_STATEMENT_DAYS = 28


#: The most days of a monthly cycle (every printed period of the corpus's 7,241 that runs more than a month runs 32 to
#: 35 days; none runs 36 or more), so a statement of more days is a printout (a 60- or 90-day activity printout, a
#: multi-month export), never a month its partial printouts are cut from: the first phase of `package_superseded`
#: tests it against all its account's statements, not only the month-length ones.
_LONGEST_CYCLE_DAYS = 35


def _posted_rows(account: dict) -> list[dict]:
    """An account's posted rows, credits and debits (a row whose record says `is_posted` False is not)."""
    return [
        row for row in (account.get("statement") or {}).get("transactions") or []
        if isinstance(row, dict)
        and not (isinstance(row.get("classification"), dict) and row["classification"].get("is_posted") is False)
    ]


def _statement_span(account: dict, rows: list[dict]):
    """A statement's period: its printed first and last day, or else its first and last posted row's day. None when
    neither reads."""
    statement = account.get("statement") or {}
    start, end = iso_day(statement.get("period_start")), iso_day(statement.get("period_end"))
    if start is not None and end is not None and start <= end:
        return start, end
    days = sorted(day for row in rows if (day := iso_day(row.get("date"))) is not None)
    return (days[0], days[-1]) if days else None


def _days_shared(span, other) -> int:
    first, last = max(span[0], other[0]), min(span[1], other[1])
    return (last - first).days + 1 if first <= last else 0


def _span_covered(span, others) -> bool:
    """Whether every day of `span` lies inside the union of the `others` periods."""
    from datetime import timedelta

    cursor = span[0]
    for start, end in sorted(others):
        if start > cursor:
            break
        if end >= cursor:
            cursor = end + timedelta(days=1)
        if cursor > span[1]:
            return True
    return cursor > span[1]


def package_superseded(kept, repeated_accounts: dict[str, dict[int, str]] | None = None,
                       members: set[tuple[str, int | None]] | None = None):
    """§4.6: the statements of one account that a shorter printout repeats, after the exact repeats are left out
    (`package_duplicates`).

    The kept jobs' accounts (a done job's, never one `repeated_accounts` already leaves out and, when `members` is
    given, only the ``(job id, account index or None)`` members `package_members` admits, so a statement whose money
    the package does not count never covers another or is covered) are compared when they are one account's
    (`_pair_kind`; every account with a period, whatever its bank and digits): a "printed" pair prints one bank
    (`package_bank`: casefolded, an informal printout's label read as its bank) and one last four
    (`printed_account_digits`) with no conflict between full numbers (`numbers_conflict`); a statement that prints no
    bank or fewer than four digits makes a "possible" pair with one whose bank, account name and declared currency do
    not differ from its own where both print one. A statement's period is its printed one, or else its first and last
    posted row's day. Two accounts of one document are never compared. A statement is left out when its period lies
    inside the union of the periods of the other kept statements it is one account with, it prints a posted row, and
    every posted row of it, credit or debit, is a posted row of those statements, as a multiset on the day and the
    signed cents (never a fuzzy match). The statements of more than a month (`_MONTH_DAYS`) are tested first, the
    longest first, so a quarterly printout or a multi-month export whose rows the account's other statements print is
    left out (`superseded_long_printout`) and those statements stay; in that first phase a statement is left out only
    in favour of month-length statements (`_FULL_STATEMENT_DAYS` days or more) that alone cover its period and print
    its rows, no two of which sharing its days overlap each other by more than `_OVERLAP_BOUNDARY_DAYS` days or share a
    credit in the days both cover (no double count between them); otherwise it waits. The month-length rule reads a
    statement of a monthly cycle's length (`_LONGEST_CYCLE_DAYS` days or fewer) only; a printout of more days is proved
    by all its account's statements (a month-to-date, a short first or closing month included), and the double-count
    test reads only the statements the second phase would keep side by side (`settled`: a month-to-date beside its
    month, or a printout two neighbouring months print, is left out there first, and before them another printout of
    more than `_LONGEST_CYCLE_DAYS` days that the others print, as this phase leaves it out). And a printout of 32 to
    `_LONGEST_CYCLE_DAYS` days that the month-length statements alone print and that count nothing twice between them,
    as this phase leaves it out; the double count is read only between two statements that are one account's, each
    printing a posted row (`double_counted`: a printed pair, or a possible pair the overlap pass names or whose two
    statements print only rows of the printout tested), so a second account of the holder at the bank whose number is
    not read, a 34-day export the monthly statements print or a printout with no posted row no longer keeps the long
    printout in the package. A printout of 32 to 35 days that only a shorter statement proves with the month-length
    ones waits too: the second phase may leave that shorter statement, or a month-length one inside the printout, out
    in its favour, and the days the printout shares with a statement it does not print whole count twice, the pair
    named (the recorded residual); beside it a longer printout waits as well, read as its double count. Then every
    statement left, long ones included, the shortest first, so an interim or month-to-date printout beside the full
    statement, a second month-to-date printout of one open month, or a short custom range of days the full statements
    print is left out (`superseded_interim`) and a full month, a 32-35-day monthly cycle included, is never left out
    for partial printouts of it that print nothing it does not (of two periods alike, the one listed later is tested
    first). It repeats the statement left in the package that shares the most of its days (of two alike, the one listed
    first).

    Any other overlap of two statements of one account is never netted. The credits the two share in the days both
    cover are matched one to one on the cents within `_OVERLAP_SHIFT_DAYS` days, whatever their wording
    (`_shared_credits`). A printed pair is named when it shares a credit, shares more than `_OVERLAP_BOUNDARY_DAYS`
    days, or one period lies inside the other; a possible pair when it shares more than `_OVERLAP_BOUNDARY_DAYS` days
    and either shares at least half the credits the fewer-credited side prints in those days, or the two print one
    period and the same opening and closing balances. A named pair is listed in `overlapping`, ``{"job", "other",
    "shared_credit_count", "shared_credit_total", "currency", "days_shared"}`` (`job` the statement listed later;
    `currency` the account's, None when the two declare different ones; `days_shared` the days both cover; with
    `account` and `other_account` for an account of a document), and sends the package to review; the figures keep the
    double count.

    Returns ``(kept jobs, dropped, superseded_accounts, overlapping)``: a job whose every account is left out is
    dropped as a duplicate is (``{"job", "duplicate_of", "reason"}``, in listed order); an account of a document whose
    other accounts stay is named in `superseded_accounts` (job id -> {account index: (the covering job's id, the
    reason)}) for `package_members` to leave out with `repeated_accounts`."""
    repeated_accounts = repeated_accounts or {}
    statements: list[dict] = []
    for order, job in enumerate(kept):
        if getattr(job, "status", None) != "done":
            continue
        analysis = getattr(job, "analysis", None)
        document = is_document_payload(analysis)
        accounts = stored_accounts(analysis)
        for index, account in enumerate(accounts, start=1):
            if document and index in repeated_accounts.get(job.id, {}):
                continue
            if members is not None and (job.id, index if document else None) not in members:
                continue
            rows = _posted_rows(account)
            span = _statement_span(account, rows)
            if span is None:
                continue
            days = (span[1] - span[0]).days + 1
            statements.append({
                "job": job, "order": order, "index": index if document else None, "accounts": len(accounts),
                # What `_pair_kind` reads the account by, whatever is printed: the stored account's facts.
                "facts": AccountFacts.of(account),
                "span": span, "days": days,
                "rows": Counter((row_day(row), row_cents(row)) for row in rows),
                "credits": [row for row in rows if num(row.get("amount")) > 0],
            })

    def peers(statement: dict, alive: list[dict]) -> list[dict]:
        """The statements left in the package that `statement` is one account with (`_pair_kind`)."""
        return [other for other in alive if _pair_kind(statement, other) is not None]

    def most_days(statement: dict, others: list[dict]) -> dict:
        return max(others, key=lambda other: (_days_shared(statement["span"], other["span"]), -other["order"]))

    def printed_by(statement: dict, others: list[dict]) -> bool:
        """The drop's proof: `others` cover the statement's period and print every posted row of it (a multiset on the
        day and the signed cents), and it prints one."""
        if not others or not statement["rows"] or not _span_covered(statement["span"],
                                                                    [other["span"] for other in others]):
            return False
        pool: Counter = Counter()
        for other in others:
            pool.update(other["rows"])
        return not statement["rows"] - pool

    superseded: list[tuple[dict, dict]] = []
    overlapping: list[dict] = []
    alive = list(statements)
    left_out: list[tuple[dict, dict]] = []
    def only_rows_of(statement: dict, printout: dict) -> bool:
        """Whether `statement` prints a posted row in `printout`'s days and every posted row it prints there is one of
        `printout`'s (a multiset on the day and the signed cents)."""
        start, end = printout["span"]
        within = Counter({key: count for key, count in statement["rows"].items()
                          if (day := iso_day(key[0])) is not None and start <= day <= end})
        return bool(within) and not within - printout["rows"]

    def double_counted(one: dict, two: dict, printout: dict) -> bool:
        """Two statements that overlap each other by more than a boundary's days, or share a credit in the days both
        cover (`_shared_credits`): kept side by side, they count money twice. Only two statements that are one
        account's, each printing a posted row (a statement printing none counts no money): a printed pair
        (`_pair_kind`), or a possible pair that the overlap pass names (`_possible_pair_named`) or whose two
        statements each print only rows of the `printout` being tested in its days (`only_rows_of`), so a second
        account of the holder at the bank whose number is not read, a possible peer of every statement of the first
        that prints rows of its own, never reads as a double count beside the first."""
        if not one["rows"] or not two["rows"]:
            return False
        kind = _pair_kind(one, two)
        first, last = max(one["span"][0], two["span"][0]), min(one["span"][1], two["span"][1])
        if kind is None or first > last:
            return False
        count = _shared_credits(one, two, first, last)[0]
        if kind == "possible" and not _possible_pair_named(one, two, first, last, count) and not (
                only_rows_of(one, printout) and only_rows_of(two, printout)):
            return False
        return (last - first).days + 1 > _OVERLAP_BOUNDARY_DAYS or count >= 1

    def interim(group: list[dict]) -> list[dict]:
        """The second phase's pass over `group` alone: the shortest first (of two alike, the later listed first), one
        left out when the others of `group` it is one account with print it (`printed_by`)."""
        left = list(group)
        for statement in sorted(left, key=lambda item: (item["days"], -item["order"])):
            if printed_by(statement, peers(statement, left)):
                left.remove(statement)
        return left

    def counts_twice(statement: dict, group: list[dict]) -> bool:
        """Whether two statements of `group` that share days with `statement` count money twice (`double_counted`)."""
        sharing = [other for other in group if _days_shared(statement["span"], other["span"]) > 0]
        return any(double_counted(one, two, statement) for place, one in enumerate(sharing)
                   for two in sharing[place + 1:])

    def settled(group: list[dict]) -> list[dict]:
        """The statements of `group` the second phase would keep side by side (`interim`: a month-to-date beside its
        month, a printout two neighbouring months print, left out), so a double count that phase resolves keeps no long
        printout in the package. Before that pass, the longest first, a printout of more than `_LONGEST_CYCLE_DAYS` days
        that the others print is left out, as the first phase leaves it out. So is a printout of 32 to
        `_LONGEST_CYCLE_DAYS` days that the month-length statements of `group` alone print (`_FULL_STATEMENT_DAYS`) and
        that count nothing twice between them, read on the second phase's own pass over them (`interim`), as the first
        phase leaves it out, so a 34-day export the monthly statements print is no double count beside the month it
        straddles."""
        left = list(group)
        for statement in sorted((item for item in group if item["days"] > _MONTH_DAYS),
                                key=lambda item: (-item["days"], -item["order"])):
            if statement["days"] > _LONGEST_CYCLE_DAYS:
                if printed_by(statement, peers(statement, left)):
                    left.remove(statement)
                continue
            proof = [other for other in peers(statement, left) if other["days"] >= _FULL_STATEMENT_DAYS]
            if printed_by(statement, proof) and not counts_twice(statement, interim(proof)):
                left.remove(statement)
        return interim(left)

    # Phase 1: a printout of more than a month, the longest first (of two alike, the later listed first). It is left
    # out only in favour of month-length statements (`_FULL_STATEMENT_DAYS` or more) that alone prove it and no two of
    # which sharing its days overlap each other by more than `_OVERLAP_BOUNDARY_DAYS` or share a credit (no double
    # count between them), so a 32-35-day monthly cycle is never left out for partial printouts of it. The month-length
    # rule reads a statement of a monthly cycle's length only (`_LONGEST_CYCLE_DAYS`); one of more days is a printout,
    # proved by all its account's statements (a month-to-date, a short first or closing month), and the double-count
    # test reads only the statements the second phase would keep side by side (`settled`), another printout of more
    # than `_LONGEST_CYCLE_DAYS` days the others print left out before them. And a 32-35-day printout the month-length
    # statements alone print without a double count; the double count is read only between two statements that are one
    # account's, each printing a posted row (`double_counted`, against the printout tested).
    for statement in sorted((item for item in statements if item["days"] > _MONTH_DAYS),
                            key=lambda item: (-item["days"], -item["order"])):
        full = [other for other in peers(statement, alive)
                if other["days"] >= _FULL_STATEMENT_DAYS or statement["days"] > _LONGEST_CYCLE_DAYS]
        if not printed_by(statement, full) or counts_twice(statement, settled(full)):
            continue
        statement["reason"] = "superseded_long_printout"
        left_out.append((statement, most_days(statement, full)))
        alive.remove(statement)
    # Phase 2: every statement left, long ones included, the shortest first (of two alike, the later listed first),
    # against all the statements it is one account with: the partial printouts that print nothing a statement does not
    # are left out before it, and it stays.
    for statement in sorted(alive, key=lambda item: (item["days"], -item["order"])):
        others = peers(statement, alive)
        if not printed_by(statement, others):
            continue
        statement["reason"] = "superseded_interim"
        left_out.append((statement, most_days(statement, others)))
        alive.remove(statement)
    for statement, covering in left_out:
        # The statement it repeats is one the package keeps: a covering statement left out after it hands it on.
        remaining = [other for other in peers(statement, alive)
                     if _days_shared(statement["span"], other["span"]) > 0]
        superseded.append((statement, most_days(statement, remaining) if remaining else covering))
    alive.sort(key=lambda item: (item["order"], item["index"] or 0))
    for position, earlier in enumerate(alive):
        for later in alive[position + 1:]:
            kind = _pair_kind(earlier, later)
            if kind is None:
                continue
            first, last = max(earlier["span"][0], later["span"][0]), min(earlier["span"][1], later["span"][1])
            if first > last:
                continue
            days_shared = (last - first).days + 1
            count, cents = _shared_credits(earlier, later, first, last)
            if kind == "printed":
                # A printed pair sharing a credit, more than a boundary's days, or a period inside the other.
                inside = any(one["span"][0] >= two["span"][0] and one["span"][1] <= two["span"][1]
                             for one, two in ((earlier, later), (later, earlier)))
                named = count >= 1 or days_shared > _OVERLAP_BOUNDARY_DAYS or inside
            else:
                # A possible pair only where more than a boundary's days are shared and the shared credits, or one
                # period printed with both balances, show the two are one account's.
                named = _possible_pair_named(earlier, later, first, last, count)
            if not named:
                continue
            pair = {
                "job": later["job"].id,
                "other": earlier["job"].id,
                "shared_credit_count": count,
                "shared_credit_total": round(cents / 100, 2),
                # The unit of the shared money, the account's; unknown when the two statements declare different
                # ones.
                "currency": (later["facts"].currency if later["facts"].currency == earlier["facts"].currency
                             else None),
                # The days both cover.
                "days_shared": days_shared,
            }
            if later["index"] is not None:
                pair["account"] = later["index"]
            if earlier["index"] is not None:
                pair["other_account"] = earlier["index"]
            overlapping.append(pair)

    by_job: dict[str, list[tuple[dict, dict]]] = {}
    for statement, covering in superseded:
        by_job.setdefault(statement["job"].id, []).append((statement, covering))
    dropped: list[dict] = []
    superseded_accounts: dict[str, dict[int, str]] = {}
    for job in kept:
        entries = by_job.get(job.id)
        if not entries:
            continue
        if len(entries) == entries[0][0]["accounts"]:
            # Every account the job publishes is a printout other statements print: the job is left out as a repeat is.
            first = min(entries, key=lambda entry: entry[0]["index"] or 0)
            dropped.append({"job": job, "duplicate_of": first[1]["job"].id, "reason": first[0]["reason"]})
            continue
        for statement, covering in entries:
            superseded_accounts.setdefault(job.id, {})[statement["index"]] = (covering["job"].id, statement["reason"])
    dropped_ids = {entry["job"].id for entry in dropped}
    return [job for job in kept if job.id not in dropped_ids], dropped, superseded_accounts, overlapping


def _pair_kind(statement: dict, other: dict) -> str | None:
    """Whether two of `package_superseded`'s statements are one account's, and on what. None for two accounts of one
    document (never compared). "printed" when both print a bank and four digits or more, the banks (`package_bank`)
    and the last fours are equal and the full numbers do not conflict (`numbers_conflict`): one account, with no
    name or currency test, so a holder's name read two ways never splits it. None when both print four digits or more
    and the last fours differ or the numbers conflict. Otherwise (a statement printing no bank or fewer than four
    digits) "possible" when the banks agree where both print one, the account names do not differ where both print one
    and the declared currencies (`statement_currency`) are equal where both declare one; else None."""
    if statement["job"] is other["job"]:
        return None
    one, two = statement["facts"], other["facts"]
    if len(one.digits) >= 4 and len(two.digits) >= 4:
        if one.digits[-4:] != two.digits[-4:] or numbers_conflict(one.digits, two.digits):
            return None
        if one.package_bank and two.package_bank and one.package_bank == two.package_bank:
            return "printed"
    if one.package_bank and two.package_bank and one.package_bank != two.package_bank:
        return None
    if one.name and two.name and one.name != two.name:
        return None
    if one.currency and two.currency and one.currency != two.currency:
        return None
    return "possible"


def _possible_pair_named(earlier: dict, later: dict, first, last, count: int) -> bool:
    """Whether `package_superseded`'s overlap pass names a "possible" pair (`_pair_kind`) whose common days run from
    `first` to `last` and which shares `count` credits there (`_shared_credits`): more than `_OVERLAP_BOUNDARY_DAYS`
    days shared and either at least half the credits the fewer-credited side prints in those days shared, or one period
    printed by both with the same opening and closing balances. The long-printout phase reads a possible pair as a
    double count on this evidence, or where both statements print only rows of the printout it tests, so a second
    account of the holder at the bank whose number is not read, printing rows of its own, never reads as one beside the
    first."""
    fewer = min(len(_dated_credits(earlier, first, last)), len(_dated_credits(later, first, last)))
    one, two = earlier["facts"], later["facts"]
    one_period = (
        one.start is not None and one.end is not None and (one.start, one.end) == (two.start, two.end)
        and all(is_money_value(balance) for balance in (one.opening, one.closing, two.opening, two.closing))
        and round(float(one.opening) * 100) == round(float(two.opening) * 100)
        and round(float(one.closing) * 100) == round(float(two.closing) * 100)
    )
    return (last - first).days + 1 > _OVERLAP_BOUNDARY_DAYS and ((count >= 1 and 2 * count >= fewer) or one_period)


def _dated_credits(statement: dict, first, last) -> list[tuple]:
    """A statement's posted credits dated from `first` to `last`: ``(day, cents, position)`` each, `position` its place
    among the statement's posted credits (`package_superseded`)."""
    return [
        (day, row_cents(row), position) for position, row in enumerate(statement["credits"])
        if (day := iso_day(row.get("date"))) is not None and first <= day <= last
    ]


def _shared_credits(earlier: dict, later: dict, first, last) -> tuple[int, int]:
    """§4.6: the credits two statements of one account share in the days both cover (`first` to `last`), as ``(count,
    cents)``. A one-to-one match: only the posted, dated credits of each side inside those days are read (so a
    recurring amount printed just outside them is never shared); the later statement's credits, in (day, cents, place)
    order, each take the untaken credit of the earlier with equal cents whose day is at most `_OVERLAP_SHIFT_DAYS`
    away (the smallest gap, then the earlier day, then the place). The description is not read: a transaction or value
    date, a pending item or another reference is still one credit."""
    pool = _dated_credits(earlier, first, last)
    taken: set[int] = set()
    count = cents = 0
    for day, amount, _position in sorted(_dated_credits(later, first, last)):
        best = min(
            ((abs((other_day - day).days), other_day, position) for other_day, other_amount, position in pool
             if position not in taken and other_amount == amount
             and abs((other_day - day).days) <= _OVERLAP_SHIFT_DAYS),
            default=None,
        )
        if best is not None:
            taken.add(best[2])
            count += 1
            cents += amount
    return count, cents
