"""A deterministic text screen over a private manifest: which members read like transaction statements.

Gustavo (2026-09-18) expected part of the unresolved population to be voided checks, identity documents and
single statement pages without transactions. The screen counts money tokens, date tokens, statement
vocabulary and non-statement vocabulary in the reader's own extracted text and buckets each member; a
derived manifest keeps only the `statement_like` bucket and records the rule, so the ceiling figure can be
reported on both denominators. Counts only: no text leaves the machine.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Callable

from vlm.partitions import CUSTOMER_SCOPE, MANIFEST_VERSION, set_sha256
from vlm.receipts import bound, dump_new, need, utc_now

SCREEN_VERSION = 1
MONEY = re.compile(r"(?<![\w.])-?\$?\d{1,3}(?:,\d{3})*\.\d{2}(?![\w.])")
DATE = re.compile(r"\b(?:\d{1,2}/\d{1,2}(?:/\d{2,4})?|\d{4}-\d{2}-\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.? \d{1,2})\b",
                  re.IGNORECASE)
NOT_STATEMENT = re.compile(r"\b(void|voided|driver'?s? licen[cs]e|passport|identification card|state id|social security|w-?2|1099|"
                           r"invoice|receipt|articles of|lease agreement|utility bill)\b", re.IGNORECASE)
STATEMENT = re.compile(r"\b(statement period|statement date|account summary|beginning balance|ending balance|opening balance|"
                       r"closing balance|deposits|withdrawals|transactions?)\b", re.IGNORECASE)
BUCKETS = ("statement_like", "thin_statement_text", "no_transactions_text", "many_amounts_no_statement_words",
           "non_statement_document", "no_text_extracted")
RULE = {"screen_version": SCREEN_VERSION,
        "statement_like": "money >= 15 and dates >= 5 and statement words >= 1 and not (non-statement words >= 2 and money < 15)",
        "money": MONEY.pattern, "dates": DATE.pattern, "statement_words": STATEMENT.pattern, "non_statement_words": NOT_STATEMENT.pattern}


def screen_text(text: str | None) -> tuple[str, dict]:
    """Bucket a document's extracted text; the counts come back for the public record."""
    if not text or not text.strip():
        return "no_text_extracted", {"money": 0, "dates": 0, "statement_words": 0, "non_statement_words": 0, "chars": 0}
    counts = {"money": len(MONEY.findall(text)), "dates": len(DATE.findall(text)), "statement_words": len(STATEMENT.findall(text)),
              "non_statement_words": len(NOT_STATEMENT.findall(text)), "chars": len(text)}
    if counts["non_statement_words"] >= 2 and counts["money"] < 15:
        return "non_statement_document", counts
    if counts["money"] < 4:
        return "no_transactions_text", counts
    if counts["money"] < 15 or counts["dates"] < 5:
        return "thin_statement_text", counts
    if counts["statement_words"] == 0:
        return "many_amounts_no_statement_words", counts
    return "statement_like", counts


def reader_text_of(cache_dir: Path, run_dir: Path) -> Callable[[str], str | None]:
    """The reader's own extracted text for a document (None when the run of record holds none)."""
    from tools.cohort_replay import ColdCache
    from vlm.partitions import run_rows

    cache = ColdCache(Path(cache_dir), Path(run_dir))
    rows = run_rows(Path(run_dir))

    def text_of(sha: str) -> str | None:
        row = rows.get(sha.upper())
        if row is None:
            return None
        try:
            text, _pages = cache.text(sha.upper(), row)
        except Exception:   # noqa: BLE001 - an unreadable cache entry screens as no text
            return None
        return text

    return text_of


def derive_subset(source: Path, name: str, out_dir: Path, *, text_of: Callable[[str], str | None],
                  keep: tuple[str, ...] = ("statement_like",)) -> tuple[dict, dict]:
    """Write `<name>.manifest.json` (counts) and `<name>.manifest.private.json` (members) from the members of
    `source` whose screen bucket is in `keep`. The derived manifest binds its source and records the rule."""
    source, out_dir = Path(source), Path(out_dir)
    data = json.loads(source.read_text(encoding="utf-8"))
    need(data.get("manifest_version") == MANIFEST_VERSION, "manifest_version_unexpected")
    need(data.get("data_scope") == CUSTOMER_SCOPE, "subset_source_not_customer")
    buckets: Counter = Counter()
    members = []
    for member in data["members"]:
        bucket, _counts = screen_text(text_of(member["sha"]))
        buckets[bucket] += 1
        if bucket in keep:
            members.append(member)
    need(bool(members), "subset_empty")
    shas = [m["sha"] for m in members]
    public = {"manifest_version": MANIFEST_VERSION, "name": name, "built_at": utc_now(), "data_scope": CUSTOMER_SCOPE,
              "documents": len(members), "pages": sum(int(m.get("page_count") or 0) for m in members), "set_sha256": set_sha256(shas),
              "derived_from": {"manifest": bound(source), "name": data.get("name"), "documents": len(data["members"]),
                               "kept_buckets": list(keep), "buckets": dict(sorted(buckets.items())), "rule": RULE},
              "outcome_classes": dict(sorted(Counter(m.get("outcome_class") for m in members).items())),
              "classifications": dict(sorted(Counter(m.get("classification") for m in members).items()))}
    private = {"manifest_version": MANIFEST_VERSION, "name": name, "data_scope": CUSTOMER_SCOPE, "set_sha256": public["set_sha256"],
               "archive_root": data["archive_root"], "derived_from": public["derived_from"], "members": members}
    out_dir.mkdir(parents=True, exist_ok=True)
    dump_new(out_dir / f"{name}.manifest.json", public)
    dump_new(out_dir / f"{name}.manifest.private.json", private)
    return public, private
