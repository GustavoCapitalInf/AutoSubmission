"""Before/after lender census over the local artifact cache (spec section 9). Local only; never run in CI.

`snapshot` re-classifies every cached analysis with the `analysis` package of one checkout and
records, per account: each row's state, the lender rows (index, entity, alias), the flagged groups
(debits and credits) and the withholding figures. `compare` reads two snapshots, taken with the code
before and after the lender-detection change, and reports lenders gained and lost, flagged groups,
eligible-deposit moves and withholding moves. It prints counts, registry entity names and aliases
only: no descriptor text, no amount.
Both snapshots and the comparison hold figures from customer statements, so they stay outside the
repository.

Usage, from the repository root of the checkout that holds this tool:
    python -m tools.lender_census snapshot --data-dir <webapp_data> --out <file> [--code-root <checkout>] [--limit N]
                                           [--reparse [--workers N]]
    python -m tools.lender_census compare --before <file> --after <file> --out <file> [--ledger <file>]
                                          [--allowlist <the owner's signed-off admissions>]

`--code-root` names the checkout whose `analysis` package classifies (default: this one), so the
"before" snapshot runs the code as it stood before the change. `--ledger` is the curated registry
ledger the alias tables are rendered from (master plan C10; default docs/lender-registry-ledger.json).

Owner ruling 2026-10-02 (the underwriter's Q5; true revenue spec §14.3 G7; R2-OW13): each account also records its
withholding numerator, the entities its lender count reads and its confirmed funders' payments returned unpaid, and
`compare` declares the moves the ruling makes: a returned row joining the withholding rows (`returned_funder_moves`;
audit round 3, R3-B01: R3-22, one leaving them fails) and a funder kept in the lender count whose every paid row was
returned (`kept_in_count_returned`); any other withholding or reversed_by move outside the allowlist still fails. The
owner's answer of 2026-10-07 to audit round 3's R3-73 ("Count it once"; R3-B02): a returned row leaving the withholding
rows because the same funder re-debited it is declared row by row (`returned_funder_represented`: the later snapshot's
`represented_rows` names a confirmed lender's paid or returned row of the same entity dated on or after the return);
any other returned row leaving them still fails. The owner's answer of 2026-10-07 to audit round 3's R3-79 ("Exclude
worded payoffs (Recommended)"; R3-B03): a confirmed funder's paid debit printing a payoff word leaving the withholding
rows is declared row by row (`lump_sum_payoff_excluded`: the later snapshot's `lump_sum_payoff_rows` lists it and it is
the same confirmed lender's paid row in both snapshots); any other paid row leaving them still fails outside the
allowlist.

`--reparse` (true revenue audit round 2, R2-B01: R12) re-parses every latest input a cached OCR reading
reaches with the checkout's deterministic analysis stage, as the revenue census does
(tools.revenue_census.reparse_inputs), and reads every other input from the cache; the snapshot records
the counts in `basis_stats.reparse`.

Exit codes: snapshot 0, or 2 when refused. compare 0 when the ledger admits every gained lender as a
lender (status `admitted`, group `confirmed_lender`) and none was gained through a generic word,
1 otherwise, 2 when refused (including a ledger that is missing or not schema 1). Compare also exits 1 on a
potential-lender, withholding or reversed_by move outside the allowlist (re-review N5), on an undeclared move of a
declared compare of the two Zelle readings (R2-OW17), and (audit round 3, R3-B01: R3-22; the exit code alone carries
G7's verdict) on a returned row leaving the withholding rows (`returned_rows_leaving_withholding`, never excused by the
allowlist: it reverses the owner's Q5), a paid row leaving the lenders list for no return
(`paid_rows_left_other_outside_the_allowlist`), a lost lender (`lost_outside_the_allowlist`) or a lender-count loss
(`lender_count_lost_outside_the_allowlist`) whose entity is not allowlisted, and `lender_debits` or the withholding
numerator moving while the paid-row or withholding-row set does not (`lender_debits_unexplained`,
`withholding_numerator_unexplained`; a declared compare's rule D accounts are skipped). The payment-changes block never
fails.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Iterator, Mapping
from pathlib import Path

# Imported before `snapshot --code-root` puts another checkout first on the path (it loads no `analysis` package).
from tools import revenue_census

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER = ROOT / "docs" / "lender-registry-ledger.json"

#: Words that never identify a lender on their own (spec section 9, acceptance 5). Every word of the C10
#: validator's `tools.lender_ledger.GENERIC_WORDS`, plus FUNDER, so an alias the validator refuses as generic
#: is generic here too (tests/test_lender_census.py pins the superset). Written out rather than imported:
#: importing tools.lender_ledger loads this checkout's `analysis` package, and `snapshot --code-root` must load
#: the other checkout's.
GENERIC_WORDS = frozenset({
    "ACH", "ADVANCE", "ADVANCES", "AND", "AUTO", "BANK", "BUSINESS", "CAPITAL", "CARD", "CO", "COMPANY",
    "CORP", "CORPORATION", "CREDIT", "DEBIT", "EQUIPMENT", "FINANCE", "FINANCIAL", "FINANCING", "FUND",
    "FUNDER", "FUNDING", "FUNDS", "GROUP", "HOLDINGS", "INC", "INSURANCE", "LEASE", "LEASING", "LENDER",
    "LENDING", "LLC", "LOAN", "LOANS", "LTD", "MCA", "MERCHANT", "MORTGAGE", "OF", "PAYMENT", "PAYMENTS", "PMT",
    "SERVICES", "SERVICING", "SOLUTIONS", "THE",
    # 5.3 (2026-09-27): the debt-relief words tools.lender_ledger.GENERIC_WORDS gained.
    "DEBT", "RELIEF", "SETTLEMENT", "CONSOLIDATION", "RESOLUTION", "NEGOTIATION", "PROGRAM", "LAW",
})


#: True revenue final review I6: the per-row flag readings each snapshot records (account_snapshot) and compare
#: counts: the potential-lender rows (with their entity), the withholding and potential-withholding rows, and the
#: reversal pairing of a debit (its reversed_by).
ROW_FLAG_FIELDS = ("potential_lender_rows", "potential_withholding_rows", "reversed_by", "withholding_rows")


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def admitted_lenders(ledger: object) -> frozenset[str]:
    """The entities the C10 ledger admits as lenders: status `admitted` and group `confirmed_lender`.

    Raises ValueError for anything but a schema-1 ledger with an `entities` list."""
    if not isinstance(ledger, dict) or ledger.get("schema") != 1 or not isinstance(ledger.get("entities"), list):
        raise ValueError("not a schema-1 lender registry ledger")
    return frozenset(
        entry["entity"]
        for entry in ledger["entities"]
        if isinstance(entry, dict)
        and entry.get("status") == "admitted"
        and entry.get("group") == "confirmed_lender"
        and isinstance(entry.get("entity"), str)
    )


def _account_payloads(node: object) -> Iterator[dict]:
    """Every account payload (a dict whose `statement` holds a `transactions` list), in order."""
    if isinstance(node, dict):
        statement = node.get("statement")
        if isinstance(statement, dict) and isinstance(statement.get("transactions"), list):
            yield node
            return
        for value in node.values():
            yield from _account_payloads(value)
    elif isinstance(node, list):
        for value in node:
            yield from _account_payloads(value)


def cached_accounts(
    data_dir: Path, limit: int | None = None, *, reparse: bool = False, workers: int = 1, stats: dict | None = None
) -> Iterator[tuple[str, int, dict]]:
    """(input sha, account index, account payload) for the latest cached analysis of each input.
    Opens the cache database read-only and never writes to the data directory. Audit round 2, R2-B01
    (R12): with `reparse`, an input a cached OCR reading reaches is read from its re-parse with the
    checkout's code (tools.revenue_census.reparse_inputs, in `workers` processes); `stats["reparse"]`
    counts the inputs re-parsed, failed and cached."""
    database = data_dir / "webapp.db"
    connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    try:
        latest = connection.execute(
            "SELECT a.input_sha256, a.artifact_path FROM artifact_cache a JOIN ("
            " SELECT input_sha256, MAX(created_at) AS newest FROM artifact_cache"
            " WHERE stage = 'analysis' GROUP BY input_sha256) b"
            " ON a.input_sha256 = b.input_sha256 AND a.created_at = b.newest"
            " WHERE a.stage = 'analysis' ORDER BY a.input_sha256"
        ).fetchall()
    finally:
        connection.close()
    reparsed: dict[str, bytes] = {}
    if reparse:
        read = latest if limit is None else latest[:limit]
        reparsed = revenue_census.reparse_inputs(
            data_dir, [sha for sha, _relative in read], workers=workers, stats={} if stats is None else stats
        )
    for number, (sha, relative) in enumerate(latest):
        if limit is not None and number >= limit:
            return
        if sha in reparsed:
            payload = revenue_census.reparsed_payload(reparsed[sha])
        else:
            try:
                payload = json.loads((data_dir / "artifacts" / relative).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
        for index, account in enumerate(_account_payloads(payload.get("artifact"))):
            yield sha, index, account


#: The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17, J3): the method pass 7 gives a Zelle deposit the
#: Zelle policy excluded (analysis/true_revenue.py ZELLE_POLICY_METHOD, copied: the census reads other checkouts).
ZELLE_POLICY_METHOD = "zelle_deposit_excluded"


class ZelleViewMismatch(ValueError):
    """R2-OW17 (J3): a compare of snapshots of the two Zelle readings without `--declare-zelle-view`."""


def account_snapshot(account: dict, *, zelle_true_revenue: bool | None = True) -> dict:
    """Re-classify one account payload with the `analysis` package on sys.path. The owner's amendment of 2026-10-06 to
    the underwriter's Q3 (R2-OW17, J3): in the Zelle reading `zelle_true_revenue` (Yes by default) on a checkout that
    takes it (tools.revenue_census._readings); `zelle_policy_rows` lists the credits the stored (No) reading excluded by
    the Zelle policy, which a declared compare reads (rule D)."""
    from analysis.metrics import compute_metrics
    from analysis.schema import Statement

    statement = Statement.model_validate(account["statement"])
    reading = zelle_true_revenue if revenue_census.zelle_reading_supported() else None
    records, stored = revenue_census._readings(statement, reading)
    # Owner ruling 2026-10-02 (the underwriter's Q7; true revenue spec §14.3 G7; R2-OW14): True revenue is the analysis's
    # default withholding basis, so the snapshot names the legacy basis explicitly and G7 compares eligible deposits and
    # the withholding rate on one basis across trees (a checkout from before the switch reads the same basis).
    metrics = compute_metrics(
        statement, classifications=records, withholding_denominator_mode="legacy_eligible_deposits",
    )
    result = _account_figures(records, stored, metrics)
    # The owner's request of 2026-10-06 (lender payment changes; true revenue spec §14.3 G7; R2-OW18, J1): ONE new
    # key, the statement's payment changes, a new output only. A checkout without the module gives no key, so a base
    # `--code-root` snapshot is byte-identical to its earlier self.
    try:
        from analysis import lender_payment_changes as payment_changes_module
        statement_payment_changes = payment_changes_module.statement_payment_changes
    except (ImportError, AttributeError):
        return result
    result["lender_payment_changes"] = [
        payment_change_entry(item) for item in statement_payment_changes(
            records, period_start=statement.period_start, period_end=statement.period_end,
            currency=statement.currency)
    ]
    return result


def payment_change_entry(item: Mapping) -> list:
    """R2-OW18 (J1): one payment change as [kind, lender, lender_state, position, cadence_before or cadence,
    cadence_after, change_percent, stop_confirmed], null wherever the item carries no such field."""
    return [item.get("kind"), item.get("lender"), item.get("lender_state"), item.get("position"),
            item.get("cadence_before") or item.get("cadence"), item.get("cadence_after"), item.get("change_percent"),
            item.get("stop_confirmed")]


def without_payment_changes(snap: dict) -> dict:
    """R2-OW18 (J3 b): the snapshot with `lender_payment_changes` removed from every account: byte-identical to the
    base snapshot when nothing else moved."""
    return {**snap, "accounts": {key: {name: value for name, value in account.items() if name != "lender_payment_changes"}
                                 for key, account in snap.get("accounts", {}).items()}}


def _account_figures(records: list, stored: list, metrics: object) -> dict:
    """The account's lender, flagged, withholding and row figures (every key but the payment changes)."""
    return {
        "rows": len(records),
        "states": [record.classification for record in records],
        "lenders": [
            [index, record.canonical_entity, record.matched_alias]
            for index, record in enumerate(records)
            if record.contributes_to_lender_totals
        ],
        # [debits, debited, credits, credited] per group (C5). A checkout older than
        # the credited fields reports no credits.
        "flagged": {
            key: [group["count"], group["total"], group.get("count_credited", 0), group.get("total_credited", 0.0)]
            for key, group in (getattr(metrics, "flagged_groups", None) or {}).items()
        },
        "lender_debits": metrics.lender_debits,
        "eligible_deposits": metrics.eligible_deposits,
        "withholding_rate": metrics.withholding_rate,
        # Owner ruling 2026-10-02 (the underwriter's Q5; true revenue spec §14.3 G7; R2-OW13): the withholding
        # numerator (paid plus returned), the entities the lender count reads, and each confirmed funder's payment
        # returned unpaid ([index, the return credit's location]), so compare declares the moves the ruling makes. A
        # checkout older than the ruling records the numerator as its lender debits and no returned row.
        "withholding_numerator": metrics.withholding_numerator,
        "lender_count_entities": sorted({
            record.canonical_entity for record in records
            if record.contributes_to_lender_count and record.canonical_entity
        }),
        "returned_funder_rows": [
            [index, record.returned_funder_payment_by] for index, record in enumerate(records)
            if getattr(record, "returned_funder_payment_by", None)
        ],
        # The owner's answer of 2026-10-07 to audit round 3's R3-73 ("Count it once"; true revenue spec §14.3 G7;
        # R3-B02): each returned funder payment the same funder re-debited ([index, the re-debit's location]), out of the
        # withholding rows; compare declares that move row by row (`returned_funder_represented`). A checkout older than
        # the answer records none.
        "represented_rows": [
            [index, record.represented_by] for index, record in enumerate(records)
            if getattr(record, "represented_by", None)
        ],
        # The owner's answer of 2026-10-07 to audit round 3's R3-79 ("Exclude worded payoffs (Recommended)"; true revenue
        # spec §14.3 G7; R3-B03): each confirmed funder's paid debit printing a payoff word ([index, the word as
        # printed]), out of the withholding rows; compare declares that move row by row (`lump_sum_payoff_excluded`). A
        # checkout older than the answer records none.
        "lump_sum_payoff_rows": [
            [index, record.lump_sum_payoff] for index, record in enumerate(records)
            if getattr(record, "lump_sum_payoff", None) and getattr(record, "contributes_to_lender_totals", False)
        ],
        # R2-OW17 (J3): the stored reading's Zelle policy credits (their indexes).
        "zelle_policy_rows": [
            index for index, record in enumerate(stored)
            if record.amount > 0 and getattr(record, "revenue_match_method", None) == ZELLE_POLICY_METHOD
        ],
        # True revenue final review I6: each row's potential-lender and withholding flags and its reversal pairing,
        # so G7 measures a move of a debit's contributions (a reversal pair zeroing them), not only its state. A
        # checkout older than a flag reports none for it.
        "potential_lender_rows": [
            [index, record.canonical_entity]
            for index, record in enumerate(records)
            if getattr(record, "contributes_to_potential_lender_totals", False)
            or getattr(record, "contributes_to_potential_lender_count", False)
        ],
        "withholding_rows": [
            index for index, record in enumerate(records) if getattr(record, "contributes_to_withholding_rate", False)
        ],
        "potential_withholding_rows": [
            index for index, record in enumerate(records)
            if getattr(record, "contributes_to_potential_withholding_exposure", False)
        ],
        "reversed_by": [
            [index, record.reversed_by] for index, record in enumerate(records)
            if getattr(record, "reversed_by", None)
        ],
        # The final review of round 2, review round 1 of its fix run (finding 3; true revenue spec §14.3 G7): each row's
        # date, so compare declares F2(a)'s redirect only where the dates show it (`_redirected_returns`).
        "row_dates": _row_dates(records),
        # Re-review N5: the payee entity of each row a flag names, which compare's allowlist reads.
        "row_entities": {
            str(index): record.canonical_entity for index, record in enumerate(records)
            if record.canonical_entity and (
                getattr(record, "contributes_to_potential_lender_totals", False)
                or getattr(record, "contributes_to_potential_lender_count", False)
                or getattr(record, "contributes_to_withholding_rate", False)
                or getattr(record, "contributes_to_potential_withholding_exposure", False)
                or getattr(record, "reversed_by", None)
            )
        },
    }


def _row_dates(records: list) -> list[str | None]:
    """Each row's date, aligned with `states`: ISO, or None where the row prints none (the classifier's own
    `parse_date`). Every row, so a compare whose earlier snapshot was written before the dates reads the later one's
    (`_redirected_returns`). A checkout whose `analysis` package has no `parse_date` records the dates as printed."""
    try:
        from analysis.dates import parse_date
    except ImportError:  # pragma: no cover - every checkout since the dates module has it
        parse_date = None

    def day(record) -> str | None:
        value = getattr(record, "date", None)
        if parse_date is None:
            return str(value) if value else None
        parsed = parse_date(value) if value else None
        return parsed.isoformat() if parsed is not None else None

    return [day(record) for record in records]


def snapshot(accounts: Iterable[tuple[str, int, dict]], *, zelle_true_revenue: bool = True) -> dict:
    """{"classification_version", "zelle_true_revenue", "accounts": {"<sha>:<index>": account snapshot},
    "skipped": {reason: n}}. R2-OW17 (J3): `zelle_true_revenue` is the Zelle reading, recorded as true or false, or
    null on a checkout that takes none (its one reading: from R2-OW02 on, No)."""
    from analysis.transaction_classifier import CLASSIFICATION_VERSION

    reading = bool(zelle_true_revenue) if revenue_census.zelle_reading_supported() else None
    result: dict = {"classification_version": CLASSIFICATION_VERSION, "zelle_true_revenue": reading, "accounts": {},
                    "skipped": {}}
    skipped: Counter = Counter()
    for sha, index, account in accounts:
        try:
            result["accounts"][f"{sha}:{index}"] = account_snapshot(account, zelle_true_revenue=reading)
        except Exception as error:  # noqa: BLE001  (a stored payload the schema no longer reads)
            skipped[type(error).__name__] += 1
    result["skipped"] = dict(sorted(skipped.items()))
    return result


def _generic(alias: str | None) -> bool:
    words = [word for word in re.split(r"[^A-Z0-9]+", (alias or "").upper()) if word]
    return bool(words) and all(word in GENERIC_WORDS for word in words)


def _zelle_reading(snap: dict) -> bool:
    """R2-OW17: a snapshot's Zelle reading; null reads as the stored (No) one."""
    return snap.get("zelle_true_revenue") is True


def _location_index(location: object) -> int | None:
    found = re.fullmatch(r"transaction:(\d+)", str(location or ""))
    return int(found.group(1)) - 1 if found else None


def _rule_d_rows(old: dict, new: dict) -> set[int]:
    """R2-OW17 (J3): the funder debits whose returned-payment pairing (R2-OW13's rule D) names a Zelle policy credit (its
    location one of `zelle_policy_rows`, in either snapshot): the one lender fact the Zelle reading moves."""
    policy = set(old.get("zelle_policy_rows") or ()) | set(new.get("zelle_policy_rows") or ())
    return {
        row[0] for snap in (old, new) for row in snap.get("returned_funder_rows") or []
        if _location_index(row[1]) in policy
    }


def _redirected_returns(old: dict, new: dict) -> set[int]:
    """The final review of round 2, F2(a) (true revenue spec §6.2 pass 4, §14.3 G7): the debits whose return pairing the
    fix moved. A confirmed funder's paid payment now pairs on the lender side only with a return dated on or after it,
    so a debit the earlier snapshot paired with a credit L (its `reversed_by` or a returned funder row) that the later
    one lists as a confirmed lender's paid row again with no pair, while L names no pair or a pair of another payment of
    the same funder (that payment too, now returned in its place). Their row-flag moves are declared
    (`returned_funder_redirects`); any other pairing move is still read as G7 reads it.

    Review round 1 of the fix run (finding 3): the snapshots' `row_dates` must show F2(a)'s move: the dropped debit is
    dated after L and each payment returned in its place on or before L (printed after or before it where either row
    prints no date, the classifier's rule). The later snapshot's dates are read, else the earlier one's (compare reads
    only accounts whose row counts agree, position by position); where neither snapshot has them nothing is declared,
    so a dropped restore of an earlier payment still fails G7."""
    def pairs(snap: dict) -> dict[int, object]:
        found: dict[int, object] = {}
        for index, location in [*(snap.get("reversed_by") or []), *(snap.get("returned_funder_rows") or [])]:
            found.setdefault(index, location)
        return found

    dates = next((snap["row_dates"] for snap in (new, old) if isinstance(snap.get("row_dates"), list)), None)

    def later(first: int, second: int) -> bool | None:
        """Whether row `first` is dated (or printed) after row `second`; None where no snapshot dates the rows."""
        if dates is None or not (0 <= first < len(dates) and 0 <= second < len(dates)):
            return None
        first_day, second_day = dates[first], dates[second]
        if first_day is None or second_day is None:
            return first > second
        return first_day > second_day

    before, after = pairs(old), pairs(new)
    paid = {entry[0] for entry in new.get("lenders") or []}
    entities = {**(old.get("row_entities") or {}), **(new.get("row_entities") or {})}
    states = new.get("states") or []
    rows: set[int] = set()
    for debit, location in before.items():
        if (debit in after or debit not in paid or debit >= len(states) or states[debit] != "confirmed_lender"
                or entities.get(str(debit)) is None):
            continue
        credit = _location_index(location)
        if credit is None or later(debit, credit) is not True:
            continue  # not a restore of a payment dated after its return (or no date to show it)
        others = {index for index, other in after.items() if other == location}
        if any(entities.get(str(index)) != entities.get(str(debit)) for index in others):
            continue
        if any(later(index, credit) is not False for index in others):
            continue  # a payment returned in its place must be dated on or before the return
        rows |= {debit, *others}
    return rows


def _represented_row(old: dict, new: dict, index: int) -> bool:
    """The owner's answer of 2026-10-07 to audit round 3's R3-73 ("Count it once"; true revenue spec §14.3 G7; R3-B02):
    whether a returned funder row leaving the withholding rows is the answer's move, checked row by row on the later
    snapshot: it lists the row in `represented_rows` naming another row, the re-debit, which is a confirmed lender's
    paid or returned row of the same entity (`lenders` or `row_entities`, either snapshot), dated on or after the
    credit that returned the row and after the row itself (`row_dates`, the later snapshot's else the earlier one's;
    printed order where a row prints no date; no dates in either snapshot declares nothing)."""
    location = {row[0]: row[1] for row in new.get("represented_rows") or []}.get(index)
    re_debit = _location_index(location)
    states = new.get("states") or []
    if re_debit is None or re_debit == index or not 0 <= re_debit < len(states) or states[re_debit] != "confirmed_lender":
        return False
    paid = {entry[0]: entry[1] for entry in new.get("lenders") or []}
    returned = {row[0]: row[1] for row in new.get("returned_funder_rows") or []}
    if re_debit not in paid and re_debit not in returned:
        return False
    entities = {**(old.get("row_entities") or {}), **(new.get("row_entities") or {}),
                **{str(row): entity for row, entity in paid.items()}}
    if entities.get(str(index)) is None or entities.get(str(index)) != entities.get(str(re_debit)):
        return False
    credit = _location_index(returned.get(index))
    dates = next((snap["row_dates"] for snap in (new, old) if isinstance(snap.get("row_dates"), list)), None)
    if credit is None or dates is None or not all(0 <= row < len(dates) for row in (index, credit, re_debit)):
        return False

    def on_or_after(first: int, second: int, *, strictly: bool) -> bool:
        first_day, second_day = dates[first], dates[second]
        if first_day is None or second_day is None:
            return first > second
        return first_day > second_day if strictly else first_day >= second_day

    return on_or_after(re_debit, credit, strictly=False) and on_or_after(re_debit, index, strictly=True)


def _lump_sum_row(old: dict, new: dict, index: int) -> bool:
    """The owner's answer of 2026-10-07 to audit round 3's R3-79 ("Exclude worded payoffs (Recommended)"; true revenue
    spec §14.3 G7; R3-B03): whether a row leaving the withholding rows is the answer's move, checked row by row: the later
    snapshot lists it in `lump_sum_payoff_rows`, it is a confirmed lender's paid row in both snapshots (`lenders`, the
    same entity), it was a withholding row and is no longer one. Anything else leaving the rows still fails."""
    if index not in {row[0] for row in new.get("lump_sum_payoff_rows") or []}:
        return False
    states = new.get("states") or []
    if not 0 <= index < len(states) or states[index] != "confirmed_lender":
        return False
    paid_before = {entry[0]: entry[1] for entry in old.get("lenders") or []}
    paid_after = {entry[0]: entry[1] for entry in new.get("lenders") or []}
    if index not in paid_before or paid_before.get(index) != paid_after.get(index):
        return False
    return index in set(old.get("withholding_rows") or ()) and index not in set(new.get("withholding_rows") or ())


def _without_rows(snap: dict, rows: set[int]) -> dict:
    """A copy of an account snapshot without the lender and returned-payment entries of `rows`."""
    return {**snap, "lenders": [entry for entry in snap["lenders"] if entry[0] not in rows],
            "returned_funder_rows": [entry for entry in snap.get("returned_funder_rows") or [] if entry[0] not in rows]}


def compare(
    before: dict,
    after: dict,
    admitted: Collection[str],
    merged: Mapping[str, str] | None = None,
    allowlisted: Collection[str] = (),
    *,
    declare_zelle_view: bool = False,
) -> dict:
    """Lenders gained and lost, generic-word gains, flagged groups, eligible-deposit and withholding moves.

    `admitted` holds the ledger's admitted lender entities (`admitted_lenders`). `merged` maps an
    entity of the registry before the change to the ledger entity that absorbed it (S1's
    MERGED_REGISTRY_ENTITIES): the two are one lender, so a merge is neither a gain nor a loss.
    `allowlisted` (true revenue re-review N5) names the entities the owner signed off (S1.5's admissions): a row
    flag move whose row's payee entity is one of them is declared; any other is counted in
    `row_flag_moves_outside_the_allowlist`, which fails the compare.

    The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17, J3): snapshots of different Zelle readings
    are refused (ZelleViewMismatch) unless `declare_zelle_view`. With it, a funder debit whose lender_totals row or
    returned-payment entry moves because its return credit is a Zelle policy row (_rule_d_rows) is counted in
    `zelle_reading_rule_d` and left out of every other figure; every other move stays as G7 reads it."""
    payment_block = payment_change_block(before, after)
    view_declared = _zelle_reading(before) != _zelle_reading(after)
    if view_declared and not declare_zelle_view:
        raise ZelleViewMismatch(
            "the snapshots read Zelle deposits in different readings (Mark Zelle Payments as True Revenue); compare "
            "snapshots of one reading, or declare the move with --declare-zelle-view"
        )
    rule_d: dict = {"analyses": set(), "rows": 0}
    # Audit round 3, R3-B01 (R3-22): the accounts whose rows the declared-Zelle path sets apart; R3-22's money checks
    # skip them (their moves are zelle_reading_rule_d).
    rule_d_accounts: set[str] = set()
    if view_declared:
        before = {**before, "accounts": dict(before["accounts"])}
        after = {**after, "accounts": dict(after["accounts"])}
        for key, old in list(before["accounts"].items()):
            new = after["accounts"].get(key)
            if new is None or new["rows"] != old["rows"]:
                continue
            rows = _rule_d_rows(old, new)
            if not rows:
                continue
            rule_d_accounts.add(key)
            moved = {json.dumps(entry) for entry in old["lenders"] if entry[0] in rows} ^ {
                json.dumps(entry) for entry in new["lenders"] if entry[0] in rows}
            moved |= {json.dumps(entry) for entry in old.get("returned_funder_rows") or [] if entry[0] in rows} ^ {
                json.dumps(entry) for entry in new.get("returned_funder_rows") or [] if entry[0] in rows}
            if moved:
                rule_d["analyses"].add(key.split(":")[0])
                rule_d["rows"] += len(moved)
            before["accounts"][key] = _without_rows(old, rows)
            after["accounts"][key] = _without_rows(new, rows)
    merged = merged or {}
    allowlisted = frozenset(allowlisted)
    outside = 0

    def one_lender(entity: str) -> str:
        return merged.get(entity, entity)

    def signed_off(entity: str) -> bool:
        """Audit round 3, R3-B01 (R3-22): an entity on the owner's allowlist, before or after the merge mapping."""
        return entity in allowlisted or one_lender(entity) in allowlisted

    gained: dict = defaultdict(lambda: {"analyses": set(), "rows": 0, "aliases": Counter()})
    lost: dict = defaultdict(lambda: {"analyses": set(), "rows_now": Counter()})
    generic: Counter = Counter()
    flagged: dict = defaultdict(lambda: {"analyses": set(), "rows": 0, "rows_credited": 0})
    withholding: Counter = Counter()
    deposits: Counter = Counter()
    moves: list[tuple[float, str]] = []
    row_flags: dict = {name: {"analyses": set(), "rows": 0} for name in ROW_FLAG_FIELDS}
    row_flags_not_comparable = 0
    # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): the moves the ruling declares. A withholding_rows move on
    # a row the after snapshot lists in returned_funder_rows and in withholding_rows (a confirmed funder's payment
    # returned unpaid, kept in the withholding rate); a funder whose paid rows all leave the lenders list for returned rows while it stays in the
    # lender count (kept_in_count_returned, never `lost`); the paid rows that leave the lenders list, for a returned
    # row or not; the lender count's entities; and the withholding numerator.
    # Audit round 3, R3-B01 (R3-22): only a returned row JOINING the withholding rows is declared; one leaving them
    # reverses the ruling and fails (`returned_rows_leaving_withholding`), as do a paid row leaving for no return, a lost
    # lender and a lender-count loss outside the allowlist, and lender_debits or the numerator moving with no row move.
    returned_moves: dict = {"analyses": set(), "rows": 0}
    returned_leaving: dict = {"analyses": set(), "rows": 0}
    # Audit round 3, R3-B02 (R3-73, the owner's answer "Count it once"): a returned row leaving the withholding rows
    # because the same funder re-debited it (`_represented_row`), declared row by row.
    returned_represented: dict = {"analyses": set(), "rows": 0}
    # Audit round 3, R3-B03 (R3-79, the owner's answer "Exclude worded payoffs"): a paid payoff-worded row leaving the
    # withholding rows (`_lump_sum_row`), declared row by row.
    lump_sums: dict = {"analyses": set(), "rows": 0}
    paid_left_other_outside = 0
    debits_unexplained: set[str] = set()
    numerator_unexplained: set[str] = set()
    # The final review of round 2, F2(a): the row-flag moves of a return whose pairing the fix moved (declared).
    redirect_moves: dict = {"analyses": set(), "rows": 0}
    kept_in_count: dict = defaultdict(set)
    paid_rows: Counter = Counter()
    count_moves: dict = {"gained": defaultdict(set), "lost": defaultdict(set)}
    count_not_comparable = 0
    numerators: Counter = Counter()
    unmatched = 0
    for key, old in sorted(before["accounts"].items()):
        new = after["accounts"].get(key)
        if new is None or new["rows"] != old["rows"]:
            unmatched += 1
            continue
        sha = key.split(":")[0]
        returned_rows = {row[0] for row in new.get("returned_funder_rows") or []}
        withholding_now = set(new.get("withholding_rows") or ())
        # Final review I6: the rows whose potential-lender, withholding or reversal reading moved; a snapshot written
        # before the fields is not comparable.
        if all(name in old and name in new for name in ROW_FLAG_FIELDS):
            entities = {**(old.get("row_entities") or {}), **(new.get("row_entities") or {})}
            redirected = _redirected_returns(old, new)
            for name in ROW_FLAG_FIELDS:
                was = {json.dumps(item) for item in old[name]}
                now = {json.dumps(item) for item in new[name]}
                if was != now:
                    row_flags[name]["analyses"].add(sha)
                    row_flags[name]["rows"] += len(was ^ now)
                    for item in was ^ now:
                        row = json.loads(item)
                        index = row[0] if isinstance(row, list) else row
                        if name in ("reversed_by", "withholding_rows") and index in redirected:
                            # F2(a): declared (returned_funder_redirects), never outside the allowlist.
                            redirect_moves["analyses"].add(sha)
                            redirect_moves["rows"] += 1
                        elif name == "withholding_rows" and index in returned_rows:
                            if index in withholding_now:
                                # R2-OW13: a returned row joining (or restored to) the withholding rows: declared
                                # (returned_funder_moves), never outside the allowlist.
                                returned_moves["analyses"].add(sha)
                                returned_moves["rows"] += 1
                            elif _represented_row(old, new, index):
                                # Audit round 3, R3-B02 (R3-73): the funder re-debited it; declared
                                # (returned_funder_represented), never outside the allowlist.
                                returned_represented["analyses"].add(sha)
                                returned_represented["rows"] += 1
                            else:
                                # Audit round 3, R3-B01 (R3-22): a returned row LEAVING the withholding rows reverses
                                # the owner's Q5 ("keep it in the withholding rate"): it fails, allowlisted or not.
                                returned_leaving["analyses"].add(sha)
                                returned_leaving["rows"] += 1
                        elif name == "withholding_rows" and _lump_sum_row(old, new, index):
                            # Audit round 3, R3-B03 (R3-79): a paid lump-sum payoff out of the rate; declared
                            # (lump_sum_payoff_excluded), never outside the allowlist.
                            lump_sums["analyses"].add(sha)
                            lump_sums["rows"] += 1
                        elif entities.get(str(index)) not in allowlisted:
                            outside += 1
        else:
            row_flags_not_comparable += 1
        old_entities = {one_lender(entity) for _, entity, _ in old["lenders"]}
        new_entities = {one_lender(entity) for _, entity, _ in new["lenders"]}
        for _, entity, alias in new["lenders"]:
            if one_lender(entity) not in old_entities:
                slot = gained[entity]
                slot["analyses"].add(sha)
                slot["rows"] += 1
                slot["aliases"][alias] += 1
                if _generic(alias):
                    generic[(entity, alias)] += 1
        counted_now = {one_lender(entity) for entity in new.get("lender_count_entities") or []}
        new_rows = {index for index, _, _ in new["lenders"]}
        old_rows_of: dict = defaultdict(list)
        for index, entity, _ in old["lenders"]:
            old_rows_of[one_lender(entity)].append(index)
            if index not in new_rows:
                paid_rows["left_returned" if index in returned_rows else "left_other"] += 1
                if index not in returned_rows and not signed_off(entity):
                    # R3-22: a paid row leaving for no return fails unless its entity is allowlisted.
                    paid_left_other_outside += 1
        old_paid = {index for index, _, _ in old["lenders"]}
        paid_rows["joined"] += len(new_rows - old_paid)
        if key not in rule_d_accounts:
            # R3-22: lender_debits moving while the paid-row set is the same, and the numerator moving while the
            # withholding-row set is the same, are moves no row explains (both present; a rule D account is skipped).
            old_debits, new_debits = old.get("lender_debits"), new.get("lender_debits")
            if (old_paid == new_rows and old_debits is not None and new_debits is not None
                    and round(new_debits - old_debits, 2) != 0):
                debits_unexplained.add(sha)
            old_held, new_held = old.get("withholding_numerator"), new.get("withholding_numerator")
            if ("withholding_rows" in old and "withholding_rows" in new
                    and set(old["withholding_rows"]) == set(new["withholding_rows"])
                    and old_held is not None and new_held is not None and round(new_held - old_held, 2) != 0):
                numerator_unexplained.add(sha)
        for index, entity, _ in old["lenders"]:
            if one_lender(entity) not in new_entities:
                if one_lender(entity) in counted_now and all(
                        row in returned_rows for row in old_rows_of[one_lender(entity)]):
                    kept_in_count[entity].add(sha)
                    continue
                slot = lost[entity]
                slot["analyses"].add(sha)
                slot["rows_now"][new["states"][index]] += 1
        if "lender_count_entities" in old and "lender_count_entities" in new:
            counted_before = {one_lender(entity) for entity in old["lender_count_entities"]}
            for entity in counted_now - counted_before:
                count_moves["gained"][entity].add(sha)
            for entity in counted_before - counted_now:
                count_moves["lost"][entity].add(sha)
        else:
            count_not_comparable += 1
        old_numerator, new_numerator = old.get("withholding_numerator"), new.get("withholding_numerator")
        if old_numerator is None or new_numerator is None:
            numerators["not_comparable"] += 1
        elif round(new_numerator - old_numerator, 2) == 0:
            numerators["unchanged"] += 1
        else:
            numerators["up" if new_numerator > old_numerator else "down"] += 1
        for group, values in new["flagged"].items():
            flagged[group]["analyses"].add(sha)
            flagged[group]["rows"] += values[0]
            # A snapshot written before the credited fields holds [count, total] only.
            flagged[group]["rows_credited"] += values[2] if len(values) > 2 else 0
        old_deposits, new_deposits = old.get("eligible_deposits"), new.get("eligible_deposits")
        if old_deposits is None or new_deposits is None:
            deposits["not_comparable"] += 1
        elif round(new_deposits - old_deposits, 2) == 0:
            deposits["unchanged"] += 1
        else:
            deposits["up" if new_deposits > old_deposits else "down"] += 1
        old_rate, new_rate = old["withholding_rate"], new["withholding_rate"]
        if old_rate is None or new_rate is None:
            withholding["not_comparable"] += 1
        elif round(new_rate - old_rate, 6) == 0:
            withholding["unchanged"] += 1
        else:
            withholding["up" if new_rate > old_rate else "down"] += 1
            moves.append((round(new_rate - old_rate, 4), key))
    moves.sort()
    return {
        "before_version": before.get("classification_version"),
        "after_version": after.get("classification_version"),
        "accounts_compared": len(before["accounts"]) - unmatched,
        "accounts_unmatched": unmatched,
        "gained": {
            entity: {
                "analyses": len(slot["analyses"]),
                "rows": slot["rows"],
                "aliases": dict(slot["aliases"]),
                "admitted": entity in admitted,
            }
            for entity, slot in sorted(gained.items())
        },
        "lost": {
            entity: {"analyses": len(slot["analyses"]), "rows_now": dict(slot["rows_now"])}
            for entity, slot in sorted(lost.items())
        },
        "gained_through_generic_words": [
            {"entity": entity, "alias": alias, "rows": rows} for (entity, alias), rows in sorted(generic.items())
        ],
        "flagged": {
            group: {"analyses": len(slot["analyses"]), "rows": slot["rows"], "rows_credited": slot["rows_credited"]}
            for group, slot in sorted(flagged.items())
        },
        "eligible_deposits": dict(sorted(deposits.items())),
        "withholding": dict(sorted(withholding.items())),
        "largest_withholding_moves": {"down": [key for _, key in moves[:10]], "up": [key for _, key in moves[-10:][::-1]]},
        "row_flag_moves": {
            **{name: {"analyses": len(slot["analyses"]), "rows": slot["rows"]} for name, slot in sorted(row_flags.items())},
            "not_comparable": row_flags_not_comparable,
        },
        "row_flag_moves_outside_the_allowlist": outside,
        # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): the declared categories.
        "returned_funder_moves": {"analyses": len(returned_moves["analyses"]), "rows": returned_moves["rows"]},
        # The final review of round 2, F2(a): a return no longer paired with a payment dated after it.
        "returned_funder_redirects": {"analyses": len(redirect_moves["analyses"]), "rows": redirect_moves["rows"]},
        # Audit round 3, R3-B02 (R3-73): a returned row out of the withholding rows because its funder re-debited it.
        "returned_funder_represented": {"analyses": len(returned_represented["analyses"]),
                                        "rows": returned_represented["rows"]},
        # Audit round 3, R3-B03 (R3-79): a paid payoff-worded row out of the withholding rows.
        "lump_sum_payoff_excluded": {"analyses": len(lump_sums["analyses"]), "rows": lump_sums["rows"]},
        "kept_in_count_returned": {entity: {"analyses": len(shas)} for entity, shas in sorted(kept_in_count.items())},
        "paid_rows": {name: paid_rows.get(name, 0) for name in ("left_returned", "left_other", "joined")},
        "lender_count": {
            **{kind: {entity: {"analyses": len(shas)} for entity, shas in sorted(moves.items())}
               for kind, moves in count_moves.items()},
            "not_comparable": count_not_comparable,
        },
        "withholding_numerator": dict(sorted(numerators.items())),
        # Audit round 3, R3-B01 (R3-22): the failures the exit code reads (spec §14.3 G7). A returned row leaving the
        # withholding rows (never excused by the allowlist); the paid rows leaving the lenders list for no return, the
        # lost lenders' (entity, analysis) entries and the lender count's lost (entity, analysis) entries whose entity is
        # not allowlisted; and the analyses whose lender_debits (numerator) moved while the paid-row (withholding-row)
        # set did not.
        "returned_rows_leaving_withholding": {"analyses": len(returned_leaving["analyses"]),
                                              "rows": returned_leaving["rows"]},
        "paid_rows_left_other_outside_the_allowlist": paid_left_other_outside,
        "lost_outside_the_allowlist": sum(
            len(slot["analyses"]) for entity, slot in lost.items() if not signed_off(entity)),
        "lender_count_lost_outside_the_allowlist": sum(
            len(shas) for entity, shas in count_moves["lost"].items() if not signed_off(entity)),
        "lender_debits_unexplained": {"analyses": len(debits_unexplained)},
        "withholding_numerator_unexplained": {"analyses": len(numerator_unexplained)},
        # R2-OW17 (J3): the Zelle readings compared, and the rule D moves a declared compare sets apart.
        "zelle_reading": {"before": before.get("zelle_true_revenue"), "after": after.get("zelle_true_revenue"),
                          "declared": view_declared},
        "zelle_reading_rule_d": {"analyses": len(rule_d["analyses"]), "rows": rule_d["rows"]},
        # R2-OW18 (J2): the lender payment changes, a new output only (never in the exit condition).
        **({"lender_payment_changes": payment_block} if payment_block is not None else {}),
    }


def _payment_counts(snap: dict) -> dict | None:
    counts: Counter = Counter()
    carried = False
    for account in snap.get("accounts", {}).values():
        if "lender_payment_changes" not in account:
            continue
        carried = True
        counts.update(f"{entry[0]}|{entry[2]}" for entry in account["lender_payment_changes"])
    return dict(sorted(counts.items())) if carried else None


def payment_change_block(before: dict, after: dict) -> dict | None:
    """The owner's request of 2026-10-06 (R2-OW18, J2): the payment changes' counts by "kind|state" after and in the
    base (null when the base carries none), the accounts whose base lacks the key (`not_comparable`), and, where both
    sides carry it, the items gained and lost (accounts and items). A new output only: it never enters the exit
    condition and is never added to the lenders, the lender count, the row flags, withholding or eligible deposits.
    None when neither snapshot carries the key."""
    after_counts, base_counts = _payment_counts(after), _payment_counts(before)
    if after_counts is None and base_counts is None:
        return None
    not_comparable = 0
    moves = {"gained": {"accounts": 0, "items": 0}, "lost": {"accounts": 0, "items": 0}}
    for key, new in after.get("accounts", {}).items():
        old = before.get("accounts", {}).get(key)
        if old is None or "lender_payment_changes" not in new:
            continue
        if "lender_payment_changes" not in old:
            not_comparable += 1
            continue
        new_items = Counter(json.dumps(entry) for entry in new["lender_payment_changes"])
        old_items = Counter(json.dumps(entry) for entry in old["lender_payment_changes"])
        for name, difference in (("gained", new_items - old_items), ("lost", old_items - new_items)):
            if difference:
                moves[name]["accounts"] += 1
                moves[name]["items"] += sum(difference.values())
    return {"after": after_counts or {}, "base": base_counts, "not_comparable": not_comparable, **moves}


def _print_comparison(report: dict) -> None:
    print(f"classification {report['before_version']} -> {report['after_version']}; accounts compared: "
          f"{report['accounts_compared']}; unmatched: {report['accounts_unmatched']}")
    print(f"lenders gained: {len(report['gained'])}")
    for entity, slot in report["gained"].items():
        note = "" if slot["admitted"] else "  NOT AN ADMITTED LENDER IN THE LEDGER"
        print(f"  + {entity}: {slot['analyses']} analyses, {slot['rows']} rows{note}")
    print(f"lenders lost: {len(report['lost'])}")
    for entity, slot in report["lost"].items():
        now = ", ".join(f"{state} {count}" for state, count in sorted(slot["rows_now"].items()))
        print(f"  - {entity}: {slot['analyses']} analyses; rows now: {now}")
    print(f"lenders gained through a generic word: {len(report['gained_through_generic_words'])}")
    for entry in report["gained_through_generic_words"]:
        print(f"  ! {entry['entity']} via {entry['alias']!r}: {entry['rows']} rows")
    print("flagged groups: " + ", ".join(
        f"{group} {slot['analyses']} analyses/{slot['rows']} rows"
        + (f"/{slot['rows_credited']} credits" if slot["rows_credited"] else "")
        for group, slot in report["flagged"].items()
    ))
    print("eligible deposits: " + ", ".join(
        f"{name} {count}" for name, count in report["eligible_deposits"].items()
    ))
    print("withholding rate: " + ", ".join(f"{name} {count}" for name, count in report["withholding"].items()))
    if "row_flag_moves" in report:
        print("row flag moves: " + ", ".join(
            f"{name} {slot['analyses']} analyses/{slot['rows']} rows" if isinstance(slot, dict) else f"{name} {slot}"
            for name, slot in report["row_flag_moves"].items()
        ))
        print(f"row flag moves outside the allowlist: {report.get('row_flag_moves_outside_the_allowlist', 0)}")
    if "returned_funder_moves" in report:
        # R2-OW13 (the underwriter's Q5): the declared categories.
        moves = report["returned_funder_moves"]
        print(f"returned funder moves (withholding rows kept for a returned funder payment): {moves['analyses']} "
              f"analyses/{moves['rows']} rows")
        redirects = report.get("returned_funder_redirects") or {"analyses": 0, "rows": 0}
        print(f"returned funder redirects (a return no longer paired with a payment dated after it): "
              f"{redirects['analyses']} analyses/{redirects['rows']} rows")
        represented = report.get("returned_funder_represented") or {"analyses": 0, "rows": 0}
        print(f"returned funder payments re-debited by their funder (out of the withholding rows, counted once): "
              f"{represented['analyses']} analyses/{represented['rows']} rows")
        lump_sums = report.get("lump_sum_payoff_excluded") or {"analyses": 0, "rows": 0}
        print(f"lump-sum payoffs (paid, out of the withholding rows): {lump_sums['analyses']} analyses/"
              f"{lump_sums['rows']} rows")
        print(f"kept in the lender count, every paid row returned: {len(report['kept_in_count_returned'])} funders")
        print("paid rows: " + ", ".join(f"{name} {count}" for name, count in report["paid_rows"].items()))
        count = report["lender_count"]
        print(f"lender count: gained {sum(slot['analyses'] for slot in count['gained'].values())}, lost "
              f"{sum(slot['analyses'] for slot in count['lost'].values())}, not comparable {count['not_comparable']}")
        print("withholding numerator: " + ", ".join(
            f"{name} {count}" for name, count in report["withholding_numerator"].items()))
        # Audit round 3, R3-B01 (R3-22): the failures the exit code reads, one line each.
        leaving = report.get("returned_rows_leaving_withholding") or {"analyses": 0, "rows": 0}
        print(f"returned rows leaving the withholding rows (the reverse of the owner's Q5): {leaving['analyses']} "
              f"analyses/{leaving['rows']} rows")
        print(f"paid rows that left for no return, outside the allowlist: "
              f"{report.get('paid_rows_left_other_outside_the_allowlist', 0)}")
        print(f"lenders lost outside the allowlist: {report.get('lost_outside_the_allowlist', 0)}")
        print(f"lender count lost outside the allowlist: {report.get('lender_count_lost_outside_the_allowlist', 0)}")
        print(f"lender debits moved with no paid row move: "
              f"{(report.get('lender_debits_unexplained') or {}).get('analyses', 0)} analyses")
        print(f"withholding numerator moved with no withholding row move: "
              f"{(report.get('withholding_numerator_unexplained') or {}).get('analyses', 0)} analyses")
    reading = report.get("zelle_reading")
    if reading and reading.get("declared"):
        # R2-OW17 (J3): the declared compare of the two Zelle readings.
        rule_d = report["zelle_reading_rule_d"]
        print(f"Zelle reading {reading['before']} -> {reading['after']}: rule D moves {rule_d['analyses']} analyses/"
              f"{rule_d['rows']} rows (zelle_reading_rule_d); undeclared moves {zelle_reading_undeclared(report)}")
    if "lender_payment_changes" in report:
        # R2-OW18 (J2): the new outputs, never a failure.
        block = report["lender_payment_changes"]
        print("lender payment changes (new outputs, information only): after " + ", ".join(
            f"{name} {count}" for name, count in block["after"].items()) + "; base " + (
            "none" if block["base"] is None else ", ".join(f"{name} {count}" for name, count in block["base"].items()))
            + f"; not comparable {block['not_comparable']}; gained {block['gained']['items']} items in "
              f"{block['gained']['accounts']} accounts; lost {block['lost']['items']} items in "
              f"{block['lost']['accounts']} accounts")


def _use_code_root(code_root: Path) -> bool:
    """Put the checkout's `analysis` package first on sys.path; False if another one is already loaded."""
    sys.path.insert(0, str(code_root.resolve()))
    import analysis

    return Path(analysis.__file__).resolve().is_relative_to(code_root.resolve())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    snap = commands.add_parser("snapshot", help="re-classify the cache with one checkout's code")
    snap.add_argument("--data-dir", type=Path, required=True, help="the webapp data directory (read-only)")
    snap.add_argument("--out", type=Path, required=True, help="the snapshot to write (outside the repo)")
    snap.add_argument("--code-root", type=Path, default=ROOT, help="the checkout whose analysis package classifies")
    snap.add_argument("--limit", type=int, default=None, help="read only the first N analyses")
    snap.add_argument("--reparse", action="store_true",
                      help="re-parse every latest input a cached OCR reading reaches with the checkout's deterministic "
                           "analysis stage (no model); the rest are read from the cache (true revenue audit round 2)")
    snap.add_argument("--workers", type=int, default=revenue_census.DEFAULT_REPARSE_WORKERS,
                      help="the processes a re-parse runs in (default %(default)s)")
    snap.add_argument("--zelle-true-revenue", choices=("yes", "no"), default="yes",
                      help="the Zelle reading (Mark Zelle Payments as True Revenue; default yes); a checkout without "
                           "the setting records null (true revenue R2-OW17)")
    comp = commands.add_parser("compare", help="compare a before and an after snapshot")
    comp.add_argument("--before", type=Path, required=True)
    comp.add_argument("--after", type=Path, required=True)
    comp.add_argument("--out", type=Path, required=True, help="the comparison to write (outside the repo)")
    comp.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER, help="the C10 registry ledger (JSON)")
    comp.add_argument("--allowlist", type=Path, default=None,
                      help="the owner's signed-off admissions (JSON: {\"entities\": [...]} or a list): a row flag move "
                           "on one of their rows is declared; without it every row flag move fails")
    comp.add_argument("--declare-zelle-view", action="store_true",
                      help="compare snapshots of the two Zelle readings: rule D's moves on a Zelle return credit are "
                           "declared (zelle_reading_rule_d) and any other move fails (R2-OW17); without it such a "
                           "compare is refused")
    args = parser.parse_args(argv)

    if _inside(args.out, ROOT):
        print(f"refused: {args.out} is inside the repository; the census holds statement figures", file=sys.stderr)
        return 2
    if args.command == "snapshot":
        if not (args.data_dir / "webapp.db").is_file():
            print(f"refused: {args.data_dir} holds no webapp.db", file=sys.stderr)
            return 2
        if not _use_code_root(args.code_root):
            print(f"refused: another analysis package is already loaded, not {args.code_root}", file=sys.stderr)
            return 2
        stats: dict = {}
        workers = revenue_census.pool_workers(args.code_root, args.workers) if args.reparse else 1
        result = snapshot(cached_accounts(args.data_dir, args.limit, reparse=args.reparse, workers=workers,
                                          stats=stats), zelle_true_revenue=args.zelle_true_revenue == "yes")
        if args.reparse:
            # True revenue audit round 2, R2-B01 (R12): what the re-parse read, and what it left to the cache.
            result["basis_stats"] = stats
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result) + "\n", encoding="utf-8")
        print(f"classification {result['classification_version']}: {len(result['accounts'])} accounts; "
              f"skipped: {sum(result['skipped'].values())}")
        return 0
    try:
        admitted = admitted_lenders(json.loads(args.ledger.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        print(f"refused: {args.ledger} is not a readable C10 ledger ({error})", file=sys.stderr)
        return 2
    allowlisted: list[str] = []
    if args.allowlist is not None:
        try:
            listed = json.loads(args.allowlist.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            print(f"refused: the allowlist {args.allowlist} cannot be read ({type(error).__name__})", file=sys.stderr)
            return 2
        allowlisted = listed.get("entities", []) if isinstance(listed, dict) else listed
        if not isinstance(allowlisted, list) or not all(isinstance(name, str) for name in allowlisted):
            print(f"refused: the allowlist {args.allowlist} holds no list of entity names", file=sys.stderr)
            return 2
    # `compare` loads no other checkout, so this one's registry may be imported here.
    from analysis.classification_registry import MERGED_REGISTRY_ENTITIES

    try:
        report = compare(
            json.loads(args.before.read_text(encoding="utf-8")),
            json.loads(args.after.read_text(encoding="utf-8")),
            admitted,
            merged=MERGED_REGISTRY_ENTITIES,
            allowlisted=allowlisted,
            declare_zelle_view=args.declare_zelle_view,
        )
    except ZelleViewMismatch as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _print_comparison(report)
    failed = (
        report["gained_through_generic_words"] or not all(slot["admitted"] for slot in report["gained"].values())
        # Re-review N5: a potential-lender, withholding or reversed_by move outside the allowlist fails G7.
        or report["row_flag_moves_outside_the_allowlist"] > 0
        # R2-OW17 (J3): between the two Zelle readings only rule D's declared moves may move a lender fact.
        or (report["zelle_reading"]["declared"] and zelle_reading_undeclared(report) > 0)
        # Audit round 3, R3-B01 (R3-22): the exit code alone carries G7's verdict.
        or failed_on_lender_losses(report)
    )
    return 1 if failed else 0


def failed_on_lender_losses(report: dict) -> bool:
    """Audit round 3, R3-B01 (R3-22; the underwriter's Q5; spec §14.3 G7): a returned row leaving the withholding rows, a
    paid row leaving for no return, a lost lender or a lender-count loss outside the allowlist, or lender_debits or the
    withholding numerator moving with no row move."""
    return (
        report["returned_rows_leaving_withholding"]["rows"] > 0
        or report["paid_rows_left_other_outside_the_allowlist"] > 0
        or report["lost_outside_the_allowlist"] > 0
        or report["lender_count_lost_outside_the_allowlist"] > 0
        or report["lender_debits_unexplained"]["analyses"] > 0
        or report["withholding_numerator_unexplained"]["analyses"] > 0
    )


def zelle_reading_undeclared(report: dict) -> int:
    """R2-OW17 (J3): the lender, withholding, potential and reversed_by moves of a declared compare of the two Zelle
    readings that rule D does not explain (every one fails G7)."""
    flags = report.get("row_flag_moves") or {}
    count = report.get("lender_count") or {}
    return (
        len(report["gained"]) + len(report["lost"]) + len(report.get("kept_in_count_returned") or {})
        + sum(slot["rows"] for name, slot in flags.items() if isinstance(slot, dict))
        + sum(value for name, value in (report.get("withholding") or {}).items() if name in ("up", "down"))
        + sum(value for name, value in (report.get("withholding_numerator") or {}).items() if name in ("up", "down"))
        + sum(value for name, value in (report.get("eligible_deposits") or {}).items() if name in ("up", "down"))
        + sum(len(entities) for kind in ("gained", "lost") for entities in [count.get(kind) or {}])
        + sum(value for name, value in (report.get("paid_rows") or {}).items())
    )


if __name__ == "__main__":
    raise SystemExit(main())
