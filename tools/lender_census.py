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
    python -m tools.lender_census compare --before <file> --after <file> --out <file> [--ledger <file>]

`--code-root` names the checkout whose `analysis` package classifies (default: this one), so the
"before" snapshot runs the code as it stood before the change. `--ledger` is the curated registry
ledger the alias tables are rendered from (master plan C10; default docs/lender-registry-ledger.json).

Exit codes: snapshot 0, or 2 when refused. compare 0 when the ledger admits every gained lender as a
lender (status `admitted`, group `confirmed_lender`) and none was gained through a generic word,
1 otherwise, 2 when refused (including a ledger that is missing or not schema 1).
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


def cached_accounts(data_dir: Path, limit: int | None = None) -> Iterator[tuple[str, int, dict]]:
    """(input sha, account index, account payload) for the latest cached analysis of each input.
    Opens the cache database read-only and never writes to the data directory."""
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
    for number, (sha, relative) in enumerate(latest):
        if limit is not None and number >= limit:
            return
        try:
            payload = json.loads((data_dir / "artifacts" / relative).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for index, account in enumerate(_account_payloads(payload.get("artifact"))):
            yield sha, index, account


def account_snapshot(account: dict) -> dict:
    """Re-classify one account payload with the `analysis` package on sys.path."""
    from analysis.metrics import compute_metrics
    from analysis.schema import Statement
    from analysis.transaction_classifier import classify_statement_transactions

    statement = Statement.model_validate(account["statement"])
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
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
    }


def snapshot(accounts: Iterable[tuple[str, int, dict]]) -> dict:
    """{"classification_version", "accounts": {"<sha>:<index>": account snapshot}, "skipped": {reason: n}}."""
    from analysis.transaction_classifier import CLASSIFICATION_VERSION

    result: dict = {"classification_version": CLASSIFICATION_VERSION, "accounts": {}, "skipped": {}}
    skipped: Counter = Counter()
    for sha, index, account in accounts:
        try:
            result["accounts"][f"{sha}:{index}"] = account_snapshot(account)
        except Exception as error:  # noqa: BLE001  (a stored payload the schema no longer reads)
            skipped[type(error).__name__] += 1
    result["skipped"] = dict(sorted(skipped.items()))
    return result


def _generic(alias: str | None) -> bool:
    words = [word for word in re.split(r"[^A-Z0-9]+", (alias or "").upper()) if word]
    return bool(words) and all(word in GENERIC_WORDS for word in words)


def compare(
    before: dict,
    after: dict,
    admitted: Collection[str],
    merged: Mapping[str, str] | None = None,
) -> dict:
    """Lenders gained and lost, generic-word gains, flagged groups, eligible-deposit and withholding moves.

    `admitted` holds the ledger's admitted lender entities (`admitted_lenders`). `merged` maps an
    entity of the registry before the change to the ledger entity that absorbed it (S1's
    MERGED_REGISTRY_ENTITIES): the two are one lender, so a merge is neither a gain nor a loss."""
    merged = merged or {}

    def one_lender(entity: str) -> str:
        return merged.get(entity, entity)

    gained: dict = defaultdict(lambda: {"analyses": set(), "rows": 0, "aliases": Counter()})
    lost: dict = defaultdict(lambda: {"analyses": set(), "rows_now": Counter()})
    generic: Counter = Counter()
    flagged: dict = defaultdict(lambda: {"analyses": set(), "rows": 0, "rows_credited": 0})
    withholding: Counter = Counter()
    deposits: Counter = Counter()
    moves: list[tuple[float, str]] = []
    unmatched = 0
    for key, old in sorted(before["accounts"].items()):
        new = after["accounts"].get(key)
        if new is None or new["rows"] != old["rows"]:
            unmatched += 1
            continue
        sha = key.split(":")[0]
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
        for index, entity, _ in old["lenders"]:
            if one_lender(entity) not in new_entities:
                slot = lost[entity]
                slot["analyses"].add(sha)
                slot["rows_now"][new["states"][index]] += 1
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
    }


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
    comp = commands.add_parser("compare", help="compare a before and an after snapshot")
    comp.add_argument("--before", type=Path, required=True)
    comp.add_argument("--after", type=Path, required=True)
    comp.add_argument("--out", type=Path, required=True, help="the comparison to write (outside the repo)")
    comp.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER, help="the C10 registry ledger (JSON)")
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
        result = snapshot(cached_accounts(args.data_dir, args.limit))
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
    # `compare` loads no other checkout, so this one's registry may be imported here.
    from analysis.classification_registry import MERGED_REGISTRY_ENTITIES

    report = compare(
        json.loads(args.before.read_text(encoding="utf-8")),
        json.loads(args.after.read_text(encoding="utf-8")),
        admitted,
        merged=MERGED_REGISTRY_ENTITIES,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _print_comparison(report)
    failed = report["gained_through_generic_words"] or not all(slot["admitted"] for slot in report["gained"].values())
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
