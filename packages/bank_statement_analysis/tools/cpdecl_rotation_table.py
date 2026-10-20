"""cpdecl_rotation_table.py — which registrations read the ROTATED text differently.

    python -m tools.cpdecl_rotation_table [--live <webapp_data>] [--json <private>.json]

Sub-card B of CP-DECLINES, asked as a measurement rather than as a fix for one
document. Batch 8's OCR-v4 rung `ocr.native_text.parse_native_printed_rows`
(DESC-COLUMNS) re-serialises a described ledger's rows out of the PDF's line
boxes, so the NATIVE text some readers see has its printed rows rotated. The
question the card asks: **over the non-validated native population, which
registrations' detection or parse outcome DIFFERS between the rotated text and
the un-rotated one?**

Both forms are the platform's own, and neither is reconstructed here:

* the ROTATED form is the run of record's own cached OCR artifact (the cold
  cache, OCR stage v4). A document is rotated exactly when that artifact's
  recorded model is `native-pdf-text+printed-rows` — the rung returns None and
  the ladder falls through to the generic one whenever it changes nothing, so
  the model string IS the rung's verdict;
* the UN-ROTATED form is the same content sha's OCR artifact under an EARLIER
  settings key in the working cache, whose model is `native-pdf-text`.

Two controls make the comparison mean what it says:

1. **token conservation.** The rung's own G7 gate requires the page's
   whitespace-separated token multiset to be unchanged, so the two forms must
   carry the same tokens. A document whose forms do not is reported as
   `TOKENS_DIFFER` and excluded — there the earlier artifact is a different
   extraction, not the un-rotated one;
2. **the unrotated control.** On documents the rung did NOT fire on, the two
   caches must hold byte-identical text. `--control N` measures that on N such
   documents, so a difference found on the rotated ones cannot be some other
   change between the two stage versions.

Read-only over both caches. Prints registration ids, outcomes, counts and
booleans; never a document value.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

DEFAULT_DATA_DIR = Path(".claude/recovery/webapp_data_train8_cold")
DEFAULT_LIVE = Path("webapp_data")
DEFAULT_CENSUS = Path("docs/moneythumb-replacement/census_batch9/per_sha.csv")
DEFAULT_RUN_POINTER = Path("discovery_reports/train8-logs/train8_run_dir.txt")
ROTATED_MODEL = "native-pdf-text+printed-rows"
PLAIN_MODEL = "native-pdf-text"


class Artifacts:
    """Every cached OCR artifact for a content sha, by settings key."""

    def __init__(self, data_dir: Path):
        self.root = data_dir / "artifacts"
        self.conn = sqlite3.connect(
            f"file:{(data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)

    def forms(self, sha: str) -> dict[str, tuple[str, list[str]]]:
        found: dict[str, tuple[str, list[str]]] = {}
        rows = self.conn.execute(
            "SELECT settings_key, artifact_path FROM artifact_cache "
            "WHERE stage = 'ocr' AND input_sha256 = ?", (sha,)).fetchall()
        for key, path in rows:
            try:
                payload = json.loads((self.root / path).read_text(encoding="utf-8"))
                document = payload["artifact"]["document"]
            except (OSError, ValueError, KeyError, TypeError):
                continue
            found[key] = (str(document.get("model") or ""),
                          [str(page) for page in (document.get("pages") or [])])
        return found


def markdown_of(pages: list[str], model: str) -> str:
    from ocr.document import StatementMarkdown
    return StatementMarkdown(source_file="replay.pdf", model=model,
                             pages=pages).to_markdown()


def route(markdown: str, pages: list[str]) -> dict:
    """The platform's own routing and ladder verdict for one text.

    `sheets` is the page partition the runner passes, and it is not optional:
    without it the page/account completeness stage has no pages to check and
    the pipeline raises, which would report every document as a crash."""
    from analysis.parser_registry import resolve

    from tools.cohort_replay import replay_one

    dispatch = resolve(markdown)
    out = {
        "dispatch": dispatch.outcome,
        "parser": dispatch.parser_id or "",
        "candidates": [name for name, _score in dispatch.candidates],
        "attempted": list(dispatch.attempted),
        "crashed": list(dispatch.crashed),
    }
    # The LADDER verdict, by the runner's own rules rather than by a second
    # set: `cohort_replay.replay_one` is the same call `discovery.runner`
    # makes, with the same page partition, the same `classify_outcome` and the
    # same `_failure_reason` for the raise an unclaimed document produces.
    _payload, klass, reason, _claimed = replay_one(markdown, pages, account_shape=True)
    out["outcome"] = f"{klass}/{reason}"
    return out


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--live", type=Path, default=DEFAULT_LIVE)
    ap.add_argument("--census", type=Path, default=DEFAULT_CENSUS)
    ap.add_argument("--run", type=Path, default=None,
                    help="with --include-validated, the run of record whose rows.csv "
                         "names the validated shas the census does not carry")
    ap.add_argument("--include-validated", action="store_true",
                    help="add the VALIDATED native documents. The census is the "
                         "non-validated population by construction, so on its own it "
                         "can show what the rotation COST and never what it gained.")
    ap.add_argument("--control", type=int, default=25,
                    help="documents the rung did NOT fire on, checked byte-identical")
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)

    cold, live = Artifacts(args.data_dir), Artifacts(args.live)
    with args.census.open(encoding="utf-8", newline="") as handle:
        census = [row for row in csv.DictReader(handle)
                  if row.get("text_route") == "native"]
    if args.include_validated:
        if args.run is None:
            args.run = Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())
        from tools.cohort_replay import load_baseline_rows
        for sha, row in sorted(load_baseline_rows(args.run).items()):
            if row.get("outcome_class") != "validated":
                continue
            census.append({"sha": sha, "sha16": sha[:16], "text_route": "native",
                           "outcome_class": row.get("outcome_class", ""),
                           "outcome_reason": row.get("outcome_reason", "")})

    population: list[dict] = []
    control: list[str] = []
    excluded: dict[str, int] = {}
    for record in census:
        forms = cold.forms(record["sha"])
        if not forms:
            excluded["no_cold_artifact"] = excluded.get("no_cold_artifact", 0) + 1
            continue
        model, pages = next(iter(forms.values()))
        if model != ROTATED_MODEL:
            if model == PLAIN_MODEL and len(control) < args.control:
                control.append(record["sha"])
            excluded[f"not_rotated:{model}"] = excluded.get(f"not_rotated:{model}", 0) + 1
            continue
        plain = [value for value in live.forms(record["sha"]).values()
                 if value[0] == PLAIN_MODEL]
        if not plain:
            excluded["rotated_no_earlier_artifact"] = excluded.get(
                "rotated_no_earlier_artifact", 0) + 1
            continue
        if sorted(" ".join(pages).split()) != sorted(" ".join(plain[0][1]).split()):
            excluded["TOKENS_DIFFER"] = excluded.get("TOKENS_DIFFER", 0) + 1
            continue
        population.append({"sha16": record["sha16"],
                           "baseline": f"{record['outcome_class']}/{record['outcome_reason']}",
                           "rotated": (model, pages),
                           "unrotated": (plain[0][0], plain[0][1])})

    # Control: on a document the rung did not fire on, the two caches must hold
    # the SAME text, or a difference below is not the rotation's.
    identical = differing = missing = 0
    for sha in control:
        cold_pages = next(iter(cold.forms(sha).values()))[1]
        plain = [v for v in live.forms(sha).values() if v[0] == PLAIN_MODEL]
        if not plain:
            missing += 1
        elif plain[0][1] == cold_pages:
            identical += 1
        else:
            differing += 1

    table = []
    for entry in population:
        rotated = route(markdown_of(entry["rotated"][1], entry["rotated"][0]),
                        entry["rotated"][1])
        unrotated = route(markdown_of(entry["unrotated"][1], entry["unrotated"][0]),
                          entry["unrotated"][1])
        row = {"sha16": entry["sha16"], "baseline": entry["baseline"],
               "rotated": rotated, "unrotated": unrotated,
               "differs": rotated != unrotated}
        table.append(row)

    print("# CP-DECLINES sub-card B — the rotation table")
    print()
    print(f"native non-validated population: {len(census)}")
    for name, count in sorted(excluded.items()):
        print(f"  excluded — {name}: {count}")
    print(f"  ROTATED and comparable: {len(population)}")
    print()
    print(f"unrotated control ({len(control)} documents the rung did not fire on): "
          f"identical {identical} / differing {differing} / no earlier artifact {missing}")
    print()
    movers = [row for row in table if row["differs"]]
    print(f"| documents whose ROUTING OR OUTCOME differs between the two forms | "
          f"{len(movers)} of {len(table)} |")
    print()
    print("| sha16 | baseline | rotated: claimants -> outcome | un-rotated: claimants -> outcome |")
    print("|---|---|---|---|")
    for row in table:
        mark = " **DIFFERS**" if row["differs"] else ""
        print(f"| {row['sha16']} | {row['baseline']} | "
              f"{row['rotated']['candidates'] or '-'} -> {row['rotated']['outcome']} | "
              f"{row['unrotated']['candidates'] or '-'} -> {row['unrotated']['outcome']}{mark} |")
    print()
    by_registration: dict[str, dict[str, int]] = {}
    for row in movers:
        for name in set(row["rotated"]["candidates"]) | set(row["unrotated"]["candidates"]):
            side = by_registration.setdefault(name, {"claims_rotated": 0,
                                                     "claims_unrotated": 0})
            side["claims_rotated"] += name in row["rotated"]["candidates"]
            side["claims_unrotated"] += name in row["unrotated"]["candidates"]
    print("| registration | claims the rotated text | claims the un-rotated text |")
    print("|---|---:|---:|")
    for name, side in sorted(by_registration.items()):
        print(f"| {name} | {side['claims_rotated']} | {side['claims_unrotated']} |")
    if not by_registration:
        print("| — | 0 | 0 |")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(table, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
