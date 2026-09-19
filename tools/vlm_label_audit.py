"""Silver page-label audit (Gustavo, 2026-09-19): are the zero-row pages really empty, and where did rows go?

    python -m tools.vlm_label_audit --dataset discovery_reports/train13-logs/p3silver/silver-02 \
        --trained discovery_reports/train13-logs/p3train/audits/trained-pages-step400.json \
        --out discovery_reports/train13-logs/p3train/audits/label-audit-v1 --queue-size 40

Mechanical evidence per page, from the same reader text the builder aligned against (never a relabel):
  * zero-row pages whose text screens transaction-like are SUSPECTS (>= 8 money and >= 4 date hits);
  * for each page, the reader's validated rows whose amount AND date are printed on that page = "printed here";
    a suspect with printed-here rows that silver assigned to another page = rows_assigned_elsewhere;
    a suspect with none printed here but many money tokens = reader_captured_nothing_here (legit summary /
    balance table, or rows the reader never captured — the human check decides);
  * nonempty targets: rows placed on a page that does not print their amount (misplaced) and rows printed on a
    page but placed elsewhere (displaced) are counted for every page, not only suspects.
The frozen dataset is read only. Output: <out>.json (summary + per page) and a bounded human queue with the
rendered page images under <out>-pages/ (private tree) that reuses the source-check workflow.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ocr.config  # noqa: E402,F401
from analysis.payload_shape import payload_accounts  # noqa: E402
from tools.cohort_replay import ColdCache  # noqa: E402
from tools.vlm_ceiling import DEFAULT_TRUTH_CACHE  # noqa: E402
from vlm import partitions  # noqa: E402
from vlm.partitions import run_rows  # noqa: E402
from vlm.receipts import dump_new, utc_now  # noqa: E402
from vlm.silver import date_forms, money_forms  # noqa: E402
from vlm.subset import DATE, MONEY  # noqa: E402

SCREEN_MONEY, SCREEN_DATES = 8, 4


def screen(page_text: str) -> tuple[bool, int, int]:
    money, dates = len(MONEY.findall(page_text or "")), len(DATE.findall(page_text or ""))
    return money >= SCREEN_MONEY and dates >= SCREEN_DATES, money, dates


def printed_on(tx: dict, text: str) -> bool:
    text = (text or "").replace(" ", " ")
    return any(f in text for f in money_forms(tx.get("amount") or 0)) and any(d in text for d in date_forms(str(tx.get("date") or "")))


def audit_document(sha: str, lines: list[dict], transactions: list[dict], page_texts: list[str], accepted: set[tuple[str, int]]) -> list[dict]:
    """One record per page of the document."""
    by_page = {int(l["page"]): l for l in lines}
    silver_page_of: dict[tuple[str, float, str], int] = {}
    for page, line in by_page.items():
        for r in line["target"]["rows"]:
            silver_page_of.setdefault((str(r.get("date")), float(r.get("amount") or 0), str(r.get("description") or "")[:40]), page)
    printed = {page: [tx for tx in transactions if printed_on(tx, page_texts[page] if page < len(page_texts) else "")] for page in by_page}
    records = []
    for page, line in sorted(by_page.items()):
        text = page_texts[page] if page < len(page_texts) else ""
        looks, money, dates = screen(text)
        silver_rows = line["target"]["rows"]
        here = printed[page]
        elsewhere = 0
        for tx in here:
            key = (str(tx.get("date")), float(abs(float(tx.get("amount") or 0))), str(tx.get("description") or "")[:40])
            assigned = silver_page_of.get(key)
            if assigned is not None and assigned != page:
                elsewhere += 1
        misplaced = sum(1 for r in silver_rows if not any(f in (text or "") for f in money_forms(r.get("amount") or 0)))
        record = {"sha": sha, "page": page, "split": line["split"], "role": line["target"]["page_role"], "silver_rows": len(silver_rows),
                  "screen_money": money, "screen_dates": dates, "looks_transactional": looks, "accepted_in_training": (sha.upper(), page) in accepted,
                  "truth_rows_printed_here": len(here), "printed_here_assigned_elsewhere": elsewhere,
                  "silver_rows_not_printed_here": misplaced}
        if not silver_rows:
            if not looks:
                record["class"] = "furniture_like"
            elif here:
                record["class"] = "suspect_rows_assigned_elsewhere" if elsewhere else "suspect_rows_printed_here_unassigned"
            else:
                record["class"] = "suspect_reader_captured_nothing_here"
        else:
            record["class"] = "nonempty_with_misplaced_rows" if misplaced else "nonempty"
        records.append(record)
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vlm_label_audit")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--trained", required=True, help="trained-pages-step400.json (accepted pages under the seeded order)")
    parser.add_argument("--truth-cache", default=str(DEFAULT_TRUTH_CACHE))
    parser.add_argument("--out", required=True, help="output stem: <out>.json, <out>-queue.json, <out>-pages/")
    parser.add_argument("--queue-size", type=int, default=40)
    parser.add_argument("--seed", default="p3-label-audit-v1")
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args(argv)

    dataset = Path(args.dataset)
    lines = []
    for split in ("train", "validation"):
        lines += [json.loads(l) for l in (dataset / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    accepted = {(s.split(":")[0].upper(), int(s.split(":")[1])) for s in json.loads(Path(args.trained).read_text(encoding="utf-8"))["accepted_pages"]}
    docs = collections.defaultdict(list)
    for l in lines:
        docs[l["sha"]].append(l)
    rows = run_rows(Path(partitions.DEFAULT_RUN_OF_RECORD))
    cache = ColdCache(Path(args.truth_cache), Path(partitions.DEFAULT_RUN_OF_RECORD))
    records = []
    totals = collections.Counter()
    try:
        for sha, ls in docs.items():
            text, pages = cache.text(sha.upper(), rows[sha.upper()])
            payload = cache.baseline_payload(text, pages) if text else None
            transactions = []
            if payload is not None:
                for account in payload_accounts(payload, surface="label_audit"):
                    transactions += (account.get("statement") or {}).get("transactions") or []
            silver_total = sum(len(l["target"]["rows"]) for l in ls)
            totals["documents"] += 1
            totals["truth_rows"] += len(transactions)
            totals["silver_rows"] += silver_total
            if silver_total < len(transactions):
                totals["documents_with_rows_never_captured_by_silver"] += 1
                totals["rows_never_captured_by_silver"] += len(transactions) - silver_total
            records += audit_document(sha, ls, transactions, pages or [], accepted)
    finally:
        cache.close()
    summary = collections.Counter()
    for r in records:
        summary[(r["split"], r["class"])] += 1
        if r["class"].startswith("suspect"):
            summary[(r["split"], "suspects")] += 1
            if r["accepted_in_training"]:
                summary[("train", "suspects_accepted_in_training")] += 1
            summary[(r["split"], f"suspects_role_{r['role']}")] += 1
    out = {"written_at": utc_now(), "dataset": str(dataset), "rule": f"suspect = zero-row page with >= {SCREEN_MONEY} money and >= {SCREEN_DATES} date hits in the reader text",
           "totals": dict(totals), "summary": {f"{k[0]}|{k[1]}": v for k, v in sorted(summary.items())},
           "note": "mechanical evidence only; nothing here relabels the frozen dataset; confirmed corrections are versioned separately", "pages": records}
    dump_new(Path(args.out + ".json"), out)

    # bounded human queue, stratified: suspects accepted in training, validation suspects, nonempty pages with misplaced rows
    random.seed(args.seed)
    strata = {"train_suspect_accepted": [r for r in records if r["class"].startswith("suspect") and r["accepted_in_training"]],
              "validation_suspect": [r for r in records if r["class"].startswith("suspect") and r["split"] == "validation"],
              "nonempty_misplaced": [r for r in records if r["class"] == "nonempty_with_misplaced_rows"],
              "furniture_control": [r for r in records if r["class"] == "furniture_like"]}
    per = max(1, args.queue_size // 4)
    queue = []
    for name, pool in strata.items():
        for r in random.sample(pool, min(per, len(pool))):
            queue.append({"stratum": name, "sha": r["sha"], "page": r["page"], "split": r["split"], "role": r["role"], "silver_rows": r["silver_rows"],
                          "class": r["class"], "truth_rows_printed_here": r["truth_rows_printed_here"],
                          "check": ("does the page print transactions? if yes: is every printed transaction in the target with date, amount, direction, balance; "
                                    "if the target is empty: genuine transaction page (label error) / legitimate zero-row page (summary, cover, balances, cheques) / uncertain"),
                          "image": None})
    if not args.no_render:
        from vlm.render import render_document

        pages_dir = Path(args.out + "-pages")
        pages_dir.mkdir(parents=True, exist_ok=True)
        private = json.loads((dataset / "manifest.private.json").read_text(encoding="utf-8"))
        members = {d["sha"].upper(): d for d in private["documents"]}
        archive_root = Path(private["archive_root"])
        for item in queue:
            member = members.get(item["sha"].upper())
            if member is None:
                continue
            raw = (archive_root / member["relative_path"]).read_bytes()
            rendered = render_document(raw, long_edge=1540, quality=90)
            if item["page"] < len(rendered):
                target = pages_dir / f"{item['sha'][:12]}-p{item['page']:03d}.jpg"
                target.write_bytes(rendered[item["page"]].jpeg)
                item["image"] = str(target)
    dump_new(Path(args.out + "-queue.json"), {"written_at": utc_now(), "items": queue, "strata_sizes": {k: len(v) for k, v in strata.items()},
                                               "note": "record human confirmations in <out>-results.json; silver targets are reader-derived, not truth"})
    print(json.dumps({"totals": dict(totals), "summary": out["summary"], "queue_items": len(queue), "out": args.out}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
