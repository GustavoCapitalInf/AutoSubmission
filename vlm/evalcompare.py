"""Base-versus-adapter comparison from two waves over the SAME manifest (R17 evaluation, 2026-09-19).

Everything here is computed from the waves' receipts: the same renderer, prompt, processor, thinking setting,
output limit, decoding and validator produced both. The reference rows are the reader's SILVER targets (or the
reader's validated rows for CTRL), never human-verified truth, and they never enter a prompt.

Reported apart, per wave and per frozen subset:
  * agreement with the silver rows (matched / missing / extra; exact amounts, dates, directions, balances),
  * account assignment (last4, currency, period start and end) on the pages that state them,
  * validator outcomes (invalid pages), generation failures (transport codes) and truncation (finish_reason=length),
  * gate verdicts (admitted strictly, refusal reasons),
  * page-density buckets by the silver target's row count on the page, including pages over the training cap,
    which stay in every denominator.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def _load_wave(wave: Path) -> dict[str, tuple[dict, dict | None]]:
    out = {}
    for path in sorted(Path(wave, "results").glob("*.json")):
        if path.name.endswith(".private.json"):
            continue
        public = json.loads(path.read_text(encoding="utf-8"))
        private_path = path.with_name(path.name[:-5] + ".private.json")
        private = json.loads(private_path.read_text(encoding="utf-8")) if private_path.exists() else None
        out[public["sha"].upper()] = (public, private)
    return out


def density_bucket(rows_on_page: int) -> str:
    if rows_on_page == 0:
        return "0 rows"
    if rows_on_page <= 10:
        return "1-10 rows"
    if rows_on_page <= 30:
        return "11-30 rows"
    if rows_on_page <= 60:
        return "31-60 rows"
    return "61+ rows"


def page_reference(silver_lines: list[dict]) -> dict[tuple[str, int], dict]:
    """(sha, page) -> the silver target line, for per-page density and the over-cap flag."""
    return {(line["sha"].upper(), int(line["page"])): line for line in silver_lines}


def summarize_wave(wave: Path, *, shas: set[str], reference: dict[tuple[str, int], dict] | None = None,
                   over_cap: set[tuple[str, int]] | None = None, reference_accounts: dict[str, dict] | None = None) -> dict:
    receipts = _load_wave(wave)
    shas = {s.upper() for s in shas}
    over_cap = {(s.upper(), int(p)) for s, p in (over_cap or ())}
    reference_accounts = {s.upper(): v for s, v in (reference_accounts or {}).items()}
    docs = {s: receipts[s] for s in sorted(shas) if s in receipts}
    out: dict = {"documents_requested": len(shas), "documents_with_receipt": len(docs), "failed": 0, "failure_codes": Counter(),
                 "gated": 0, "admitted_strict": 0, "refusal_reasons": Counter(), "invalid_pages": 0, "pages": 0, "truncated_pages": 0,
                 "rows": {"truth": 0, "matched": 0, "missing": 0, "extra": 0, "exact_balance": 0, "balance_mismatch": 0, "documents_with_truth": 0},
                 "account": {"last4_agree": 0, "last4_compared": 0, "period_agree": 0, "period_compared": 0, "currency_agree": 0, "currency_compared": 0},
                 "by_density": {}, "over_cap_pages": {"pages": 0, "invalid": 0, "truncated": 0}, "by_page_count": {}}
    for sha, (public, private) in docs.items():
        if public.get("failure") is not None:
            out["failed"] += 1
            out["failure_codes"][public["failure"].get("code", "?")[:40]] += 1
            continue
        out["gated"] += 1
        gate = public.get("gate") or {}
        if gate.get("admitted"):
            out["admitted_strict"] += 1
        for reason in gate.get("reasons", []):
            out["refusal_reasons"][reason] += 1
        stats = public.get("stats") or {}
        out["invalid_pages"] += int(stats.get("invalid_pages") or 0)
        pages = int(public.get("pages") or 0)
        out["pages"] += pages
        bucket = "1-2" if pages <= 2 else "3-6" if pages <= 6 else "7-12" if pages <= 12 else "13+"
        b = out["by_page_count"].setdefault(bucket, {"documents": 0, "admitted": 0})
        b["documents"] += 1
        b["admitted"] += 1 if gate.get("admitted") else 0
        texts = (private or {}).get("stage_b") or []
        for t in texts:
            if t.get("finish_reason") == "length":
                out["truncated_pages"] += 1
        match = public.get("match")
        if match:
            r = out["rows"]
            r["documents_with_truth"] += 1
            for key in ("truth", "matched", "missing", "extra", "exact_balance", "balance_mismatch"):
                r[key] += int(match.get(key if key != "truth" else "truth_rows") or 0)
        # account assignment: the model's merged account facts (private meta) against the reference statement facts
        meta = (private or {}).get("meta") or {}
        ref_acct = reference_accounts.get(sha) or {}
        for field, key in (("last4", "account_last4"), ("period", "period_end"), ("currency", "currency")):
            expected = ref_acct.get(key)
            if expected in (None, ""):
                continue
            out["account"][f"{field}_compared"] += 1
            got = meta.get(key)
            out["account"][f"{field}_agree"] += 1 if (got is not None and str(got).upper() == str(expected).upper()) else 0
        if reference is not None and private is not None:
            invalid_pages = set()
            for p in private.get("proposals") or []:
                if p.get("errors"):
                    invalid_pages.add(int(p["page"]))
            truncated = {int(t["page"]) for t in texts if t.get("finish_reason") == "length"}
            for page in range(pages):
                ref = reference.get((sha, page))
                if ref is None:
                    continue
                d = out["by_density"].setdefault(density_bucket(len(ref["target"]["rows"])), {"pages": 0, "invalid": 0, "truncated": 0})
                d["pages"] += 1
                d["invalid"] += 1 if page in invalid_pages else 0
                d["truncated"] += 1 if page in truncated else 0
                if over_cap and (sha, page) in over_cap:
                    o = out["over_cap_pages"]
                    o["pages"] += 1
                    o["invalid"] += 1 if page in invalid_pages else 0
                    o["truncated"] += 1 if page in truncated else 0
    out["failure_codes"] = dict(out["failure_codes"])
    out["refusal_reasons"] = dict(sorted(out["refusal_reasons"].items(), key=lambda kv: -kv[1]))
    r = out["rows"]
    out["row_match_rate"] = round(r["matched"] / r["truth"], 4) if r["truth"] else None
    out["admission_rate"] = round(out["admitted_strict"] / out["gated"], 4) if out["gated"] else None
    return out


def compare(base_wave: Path, adapter_wave: Path, *, subsets: dict[str, set[str]], reference: dict | None = None,
            over_cap: set | None = None, reference_accounts: dict | None = None) -> dict:
    """Per frozen subset: the base summary, the adapter summary, and the deltas that matter."""
    report = {"base_wave": str(base_wave), "adapter_wave": str(adapter_wave), "subsets": {}}
    for name, shas in subsets.items():
        base = summarize_wave(base_wave, shas=shas, reference=reference, over_cap=over_cap, reference_accounts=reference_accounts)
        adapter = summarize_wave(adapter_wave, shas=shas, reference=reference, over_cap=over_cap, reference_accounts=reference_accounts)
        report["subsets"][name] = {"base": base, "adapter": adapter,
                                   "delta": {"admitted_strict": adapter["admitted_strict"] - base["admitted_strict"],
                                             "row_match_rate": (None if base["row_match_rate"] is None or adapter["row_match_rate"] is None
                                                                else round(adapter["row_match_rate"] - base["row_match_rate"], 4)),
                                             "invalid_pages": adapter["invalid_pages"] - base["invalid_pages"],
                                             "truncated_pages": adapter["truncated_pages"] - base["truncated_pages"]}}
    return report
