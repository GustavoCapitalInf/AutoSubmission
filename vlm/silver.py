"""Silver labels (plan v1 §10): pages of documents the deterministic reader VALIDATED, with the reader's
rows aligned to the page that prints them, exported as page-level targets in the proposal schema.

Eligibility is strict: one account, every row aligned to a page where its amount, its printed date and a
description token all appear (the "strong" tier), the document outside CTRL, DEV and the sealed holdout.
Anchors and printed totals are written only on the pages that print them, so the model is never taught to
state a value the page does not show. Counts only in the public manifest; paths and hashes in the private one.
R17 (2026-09-18): training on these records is approved inside the local machine and the rented instance.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable

from vlm.partitions import CUSTOMER_SCOPE, Member, set_sha256
from vlm.receipts import bound, dump_new, need, utc_now
from vlm.render import DEFAULT_JPEG_QUALITY, DEFAULT_LONG_EDGE, render_document
from vlm.schema import SCHEMA_VERSION, empty_proposal, validate_page_proposal

SILVER_VERSION = 1
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SUMMARY_WORDS = re.compile(r"\b(account summary|statement summary|summary of (?:your )?account|beginning balance|opening balance|ending balance|closing balance)\b", re.IGNORECASE)
TIERS = ("strong", "medium", "weak")


def money_forms(amount) -> list[str]:
    magnitude = abs(Decimal(str(amount)))
    grouped = f"{magnitude:,.2f}"
    return [grouped, grouped.replace(",", "")]


def date_forms(iso: str) -> list[str]:
    try:
        d = date.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return []
    m, dd, y = d.month, d.day, d.year
    mon = MONTHS[m - 1]
    return [f"{m:02d}/{dd:02d}", f"{m}/{dd}", f"{m:02d}-{dd:02d}", f"{mon} {dd:02d}", f"{mon} {dd}", f"{dd:02d} {mon}", f"{dd} {mon}",
            f"{y}-{m:02d}-{dd:02d}", f"{dd:02d}/{m:02d}", f"{mon.upper()} {dd:02d}", f"{mon.upper()} {dd}", f"{mon.lower()} {dd}",
            f"{m:02d}/{dd:02d}/{y}", f"{m:02d}/{dd:02d}/{str(y)[2:]}", f"{m}/{dd}/{y}", f"{m}/{dd}/{str(y)[2:]}"]


def desc_tokens(description: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z]{4,}", description or "")][:4]


def printed_date_text(iso: str, page_text: str) -> str:
    """The first printed form of the date found on the page (what the model is asked to copy), else ISO."""
    for form in date_forms(iso):
        if form in page_text:
            return form
    return str(iso)


@dataclass(frozen=True)
class Alignment:
    pages: tuple[int, ...]      # page index per row
    tiers: tuple[str, ...]      # strong | medium | weak per row
    doc_tier: str               # strong | medium | weak | unassignable


def align_rows(transactions: list[dict], page_texts: list[str]) -> Alignment:
    """Each row takes the page that prints its amount, its date and a description token (strong). The reader
    lists sectioned statements by date, so rows are NOT page-monotone: with several strong pages the one
    nearest the previous row's page wins, and an exact tie is only medium. A page printing the amount but
    not the date is medium; the amount alone is weak; no page at all makes the document unassignable."""
    texts = [(t or "").replace("\u00a0", " ") for t in page_texts]
    lowered = [t.lower() for t in texts]
    previous = 0
    pages: list[int] = []
    tiers: list[str] = []
    doc_tier = "strong"
    for tx in transactions:
        forms = money_forms(tx.get("amount") or 0)
        dforms = date_forms(str(tx.get("date") or ""))
        tokens = desc_tokens(str(tx.get("description") or ""))
        scored = []
        for index in range(len(texts)):
            if not any(f in texts[index] for f in forms):
                continue
            has_date = any(df in texts[index] for df in dforms)
            token_hits = sum(1 for k in tokens if k in lowered[index])
            scored.append((index, has_date, token_hits))
        if not scored:
            return Alignment(tuple(pages), tuple(tiers), "unassignable")
        strong = [i for i, has_date, hits in scored if has_date and (hits >= 1 or not tokens)]
        if strong:
            nearest = sorted(strong, key=lambda i: (abs(i - previous), i))
            tie = len(nearest) > 1 and abs(nearest[0] - previous) == abs(nearest[1] - previous)
            chosen, tier = nearest[0], ("medium" if tie else "strong")
        else:
            with_date = [i for i, has_date, _ in scored if has_date]
            pool = with_date or [i for i, _, _ in scored]
            chosen, tier = sorted(pool, key=lambda i: (abs(i - previous), i))[0], ("medium" if with_date else "weak")
        if TIERS.index(tier) > TIERS.index(doc_tier):
            doc_tier = tier
        pages.append(chosen)
        tiers.append(tier)
        previous = chosen
    return Alignment(tuple(pages), tuple(tiers), doc_tier)


def _money(value) -> float | None:
    return None if value is None else float(abs(Decimal(str(value))))


def _printed(value, page_text: str) -> bool:
    return value is not None and any(f in page_text for f in money_forms(value))


def page_targets(statement: dict, transactions: list[dict], alignment: Alignment, page_texts: list[str]) -> dict[int, dict]:
    """One proposal per page: the rows aligned to it, the page role, and only the account facts the page prints."""
    texts = [(t or "").replace(" ", " ") for t in page_texts]
    by_page: dict[int, list[dict]] = {}
    for tx, index in zip(transactions, alignment.pages):
        by_page.setdefault(index, []).append(tx)
    bank = statement.get("bank")
    number = re.sub(r"\D", "", str(statement.get("account_number") or ""))
    currency = str(statement.get("currency") or "").upper() or None
    period_start, period_end = statement.get("period_start"), statement.get("period_end")
    targets: dict[int, dict] = {}
    for index, text in enumerate(texts):
        rows = by_page.get(index, [])
        if rows:
            role = "statement_page"
        elif SUMMARY_WORDS.search(text):
            role = "summary_page"
        elif len(text.strip()) > 200:
            role = "cover_or_notice"
        else:
            role = "blank_or_other"
        proposal = empty_proposal(role)
        for tx in rows:
            proposal["rows"].append({
                "date": str(tx.get("date") or ""), "date_text": printed_date_text(str(tx.get("date") or ""), text),
                "description": str(tx.get("description") or ""), "amount": _money(tx.get("amount")) or 0.0,
                "direction": "credit" if str(tx.get("direction")) == "credit" else "debit",
                "balance": None if tx.get("running_balance") is None else float(Decimal(str(tx["running_balance"]))),
                "continues_previous": False,
            })
        account = proposal["account"]
        lowered = text.lower()
        if bank and str(bank).lower() in lowered:
            account["bank"] = str(bank)
        digits = re.sub(r"\D", "", text)
        if number and len(number) >= 4 and (number in digits):
            account["account_number_last4"] = number[-4:]
        if currency and re.search(rf"\b{re.escape(currency)}\b", text):
            account["currency"] = currency
        if period_start and period_end and any(f in text for f in date_forms(period_start)) and any(f in text for f in date_forms(period_end)):
            account["period_start"], account["period_end"] = str(period_start), str(period_end)
        for key in ("beginning_balance", "ending_balance", "stated_total_credits", "stated_total_debits"):
            if _printed(statement.get(key), text):
                account[key] = _money(statement.get(key))
        if account.get("stated_total_credits") is not None and statement.get("stated_credit_count") is not None:
            account["stated_credit_count"] = int(statement["stated_credit_count"])
        if account.get("stated_total_debits") is not None and statement.get("stated_debit_count") is not None:
            account["stated_debit_count"] = int(statement["stated_debit_count"])
        targets[index] = proposal
    return targets


def canonical_target(proposal: dict) -> str:
    return json.dumps(proposal, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def split_for(sha: str, family: str, *, seed: str, validation_fraction: float, family_shas: dict[str, list[str]]) -> str:
    """Family-stratified VALIDATION: within each family, the members with the lowest seeded hashes."""
    members = family_shas[family]
    ranked = sorted(members, key=lambda s: hashlib.sha256(f"{seed}:{s}".encode()).hexdigest())
    keep = max(1, int(round(len(ranked) * validation_fraction))) if len(ranked) >= 2 else 0
    return "validation" if sha in set(ranked[:keep]) else "train"


def build_silver_dataset(out_dir: Path, members: Iterable[Member], *, archive_root: Path,
                         reader: Callable[[str], tuple[dict, list[str]] | None], excluded: set[str], held16: frozenset[str],
                         seed: str = "p3-silver-v1", validation_fraction: float = 0.1, long_edge: int = DEFAULT_LONG_EDGE,
                         quality: int = DEFAULT_JPEG_QUALITY, limit: int | None = None) -> dict:
    """Render every eligible document's pages, write `<out>/images/<sha>/<page>.jpg`, `<out>/train.jsonl`,
    `<out>/validation.jsonl`, and the manifests. `reader(sha)` returns (statement dict, page texts) or None."""
    out = Path(out_dir)
    need(not out.exists(), "dataset_already_attempted")
    out.mkdir(parents=True)
    (out / "images").mkdir()
    members = list(members)
    for m in members:
        need(m.sha not in excluded, "member_in_excluded_partition")
        need(m.sha[:16].upper() not in held16, "member_in_holdout")
    families: dict[str, list[str]] = {}
    for m in members:
        families.setdefault(m.folder_label, []).append(m.sha)
    counts: Counter = Counter()
    per_split: dict[str, list[str]] = {"train": [], "validation": []}
    private_docs = []
    tiers: Counter = Counter()
    roles: Counter = Counter()
    processed = 0
    for m in members:
        if limit is not None and processed >= limit:
            counts["limited_out"] += 1
            continue
        processed += 1
        loaded = reader(m.sha)
        if loaded is None:
            counts["no_payload"] += 1
            continue
        statement, page_texts = loaded
        transactions = statement.get("transactions") or []
        if not transactions:
            counts["no_rows"] += 1
            continue
        alignment = align_rows(transactions, page_texts)
        tiers[alignment.doc_tier] += 1
        if alignment.doc_tier != "strong":
            counts["ineligible_" + alignment.doc_tier] += 1
            continue
        raw = (Path(archive_root) / m.relative_path).read_bytes()
        pages = render_document(raw, long_edge=long_edge, quality=quality)
        if len(pages) != len(page_texts):
            counts["page_count_mismatch"] += 1
            continue
        targets = page_targets(statement, transactions, alignment, page_texts)
        errors = {i: validate_page_proposal(t) for i, t in targets.items()}
        if any(errors.values()):
            counts["target_invalid"] += 1
            continue
        split = split_for(m.sha, m.folder_label, seed=seed, validation_fraction=validation_fraction, family_shas=families)
        doc_dir = out / "images" / m.sha
        doc_dir.mkdir()
        lines = []
        for page, target in zip(pages, [targets[i] for i in range(len(pages))]):
            image_path = doc_dir / f"{page.index:03d}.jpg"
            image_path.write_bytes(page.jpeg)
            roles[target["page_role"]] += 1
            lines.append({"sha": m.sha, "page": page.index, "page_total": len(pages), "image": str(image_path.relative_to(out)).replace("\\", "/"),
                          "image_sha256": page.jpeg_sha256, "family": m.folder_label, "split": split, "target": target})
        with (out / f"{split}.jsonl").open("a", encoding="utf-8") as fh:
            for line in lines:
                fh.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
        per_split[split].append(m.sha)
        counts["documents"] += 1
        counts["pages"] += len(pages)
        counts["rows"] += len(transactions)
        private_docs.append({"sha": m.sha, "relative_path": m.relative_path, "family": m.folder_label, "split": split,
                             "pages": len(pages), "rows": len(transactions), "tier": alignment.doc_tier})
    jsonl_hashes = {name: hashlib.sha256((out / f"{name}.jsonl").read_bytes()).hexdigest() for name in ("train", "validation")
                    if (out / f"{name}.jsonl").exists()}
    public = {"silver_version": SILVER_VERSION, "schema_version": SCHEMA_VERSION, "built_at": utc_now(), "data_scope": CUSTOMER_SCOPE,
              "seed": seed, "validation_fraction": validation_fraction, "render": {"long_edge": long_edge, "jpeg_quality": quality},
              "counts": dict(counts), "document_tiers": dict(tiers), "page_roles": dict(sorted(roles.items())),
              "split_documents": {k: len(v) for k, v in per_split.items()},
              "split_set_sha256": {k: (set_sha256(v) if v else None) for k, v in per_split.items()},
              "families": dict(sorted(Counter(d["family"] for d in private_docs).items())),
              "jsonl_sha256": jsonl_hashes, "excluded_partitions_size": len(excluded), "holdout_blacklist_size": len(held16)}
    private = {"silver_version": SILVER_VERSION, "data_scope": CUSTOMER_SCOPE, "archive_root": str(Path(archive_root)), "documents": private_docs}
    dump_new(out / "manifest.json", public)
    dump_new(out / "manifest.private.json", private)
    return public
