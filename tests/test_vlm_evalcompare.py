"""Base-versus-adapter comparison over synthetic receipts: nothing is filtered out of a denominator."""
import json

from vlm import evalcompare as ec

SHA_A, SHA_B, SHA_C = "a" * 64, "b" * 64, "c" * 64


def _write_wave(root, name, receipts):
    wave = root / name
    (wave / "results").mkdir(parents=True)
    for public, private in receipts:
        (wave / "results" / f"{public['sha']}.json").write_text(json.dumps(public), encoding="utf-8")
        if private is not None:
            (wave / "results" / f"{public['sha']}.private.json").write_text(json.dumps(private), encoding="utf-8")
    return wave


def _receipt(sha, *, pages, admitted, reasons=(), invalid=0, truncated_pages=(), invalid_pages=(), match=None, meta=None, failure=None):
    public = {"sha": sha, "pages": pages, "failure": failure, "gate": None if failure else {"admitted": admitted, "reasons": list(reasons)},
              "stats": {"invalid_pages": invalid}, "match": match}
    private = {"sha": sha, "meta": meta or {},
               "stage_b": [{"page": p, "finish_reason": "length" if p in truncated_pages else "stop"} for p in range(pages)],
               "proposals": [{"page": p, "proposal": {}, "errors": ["json_invalid"] if p in invalid_pages else []} for p in range(pages)]}
    return public, private


def _reference():
    lines = []
    for sha, counts in ((SHA_A, [0, 12, 70]), (SHA_B, [5]), (SHA_C, [3, 3])):
        for page, n in enumerate(counts):
            lines.append({"sha": sha, "page": page, "target": {"rows": [{"amount": 1.0}] * n}})
    return ec.page_reference(lines)


def test_density_buckets_and_page_reference():
    assert [ec.density_bucket(n) for n in (0, 1, 10, 11, 30, 31, 60, 61)] == ["0 rows", "1-10 rows", "1-10 rows", "11-30 rows", "11-30 rows",
                                                                            "31-60 rows", "31-60 rows", "61+ rows"]
    ref = _reference()
    assert len(ref[(SHA_A.upper(), 2)]["target"]["rows"]) == 70 and (SHA_B.upper(), 1) not in ref and (SHA_A, 2) not in ref


def test_summary_keeps_failures_truncation_invalid_pages_and_over_cap_pages_in_the_denominators(tmp_path):
    base = _write_wave(tmp_path, "base", [
        _receipt(SHA_A, pages=3, admitted=False, reasons=["date_order_chained"], invalid=1, truncated_pages=(2,), invalid_pages=(2,),
                 match={"truth_rows": 82, "matched": 60, "missing": 22, "extra": 3, "exact_balance": 50, "balance_mismatch": 2},
                 meta={"account_last4": "1234", "period_end": "2031-01-31", "currency": "usd"}),
        _receipt(SHA_B, pages=1, admitted=True, match={"truth_rows": 5, "matched": 5, "missing": 0, "extra": 0, "exact_balance": 5, "balance_mismatch": 0},
                 meta={"account_last4": "9999", "period_end": "2031-02-28", "currency": "USD"}),
        (dict(_receipt(SHA_C, pages=2, admitted=False)[0], failure={"code": "http_500_server_error"}), None),
    ])
    ref = _reference()
    accounts = {SHA_A: {"account_last4": "1234", "period_end": "2031-01-31", "currency": "USD"},
                SHA_B: {"account_last4": "0000", "period_end": "2031-02-28", "currency": None}}
    s = ec.summarize_wave(base, shas={SHA_A, SHA_B, SHA_C, "d" * 64}, reference=ref, over_cap={(SHA_A, 2)}, reference_accounts=accounts)
    assert s["documents_requested"] == 4 and s["documents_with_receipt"] == 3
    assert s["failed"] == 1 and s["failure_codes"] == {"http_500_server_error": 1}
    assert s["gated"] == 2 and s["admitted_strict"] == 1 and s["admission_rate"] == 0.5
    assert s["refusal_reasons"] == {"date_order_chained": 1}
    assert s["pages"] == 4 and s["invalid_pages"] == 1 and s["truncated_pages"] == 1
    assert s["rows"] == {"truth": 87, "matched": 65, "missing": 22, "extra": 3, "exact_balance": 55, "balance_mismatch": 2, "documents_with_truth": 2}
    assert s["row_match_rate"] == round(65 / 87, 4)
    # account facts: last4 compared twice (one agrees), period twice (both agree), currency once (case-insensitive agree)
    assert s["account"] == {"last4_agree": 1, "last4_compared": 2, "period_agree": 2, "period_compared": 2, "currency_agree": 1, "currency_compared": 1}
    assert s["by_density"] == {"0 rows": {"pages": 1, "invalid": 0, "truncated": 0}, "11-30 rows": {"pages": 1, "invalid": 0, "truncated": 0},
                               "61+ rows": {"pages": 1, "invalid": 1, "truncated": 1}, "1-10 rows": {"pages": 1, "invalid": 0, "truncated": 0}}
    assert s["over_cap_pages"] == {"pages": 1, "invalid": 1, "truncated": 1}
    assert s["by_page_count"] == {"3-6": {"documents": 1, "admitted": 0}, "1-2": {"documents": 1, "admitted": 1}}


def test_compare_reports_both_arms_and_the_deltas_per_frozen_subset(tmp_path):
    base = _write_wave(tmp_path, "base", [
        _receipt(SHA_A, pages=3, admitted=False, reasons=["balance_chain"], invalid=2, truncated_pages=(1, 2),
                 match={"truth_rows": 82, "matched": 40, "missing": 42, "extra": 9, "exact_balance": 30, "balance_mismatch": 4}),
        _receipt(SHA_B, pages=1, admitted=False, reasons=["anchor_missing"], match={"truth_rows": 5, "matched": 4, "missing": 1, "extra": 0, "exact_balance": 4, "balance_mismatch": 0}),
    ])
    adapter = _write_wave(tmp_path, "adapter", [
        _receipt(SHA_A, pages=3, admitted=True, invalid=0, match={"truth_rows": 82, "matched": 80, "missing": 2, "extra": 1, "exact_balance": 79, "balance_mismatch": 0}),
        _receipt(SHA_B, pages=1, admitted=True, match={"truth_rows": 5, "matched": 5, "missing": 0, "extra": 0, "exact_balance": 5, "balance_mismatch": 0}),
    ])
    report = ec.compare(base, adapter, subsets={"CTRL46": {SHA_A, SHA_B}, "DEV": {SHA_B}}, reference=_reference())
    ctrl = report["subsets"]["CTRL46"]
    assert ctrl["base"]["admitted_strict"] == 0 and ctrl["adapter"]["admitted_strict"] == 2
    assert ctrl["delta"]["admitted_strict"] == 2 and ctrl["delta"]["invalid_pages"] == -2 and ctrl["delta"]["truncated_pages"] == -2
    assert ctrl["delta"]["row_match_rate"] == round(85 / 87 - 44 / 87, 4)
    dev = report["subsets"]["DEV"]
    assert dev["base"]["documents_requested"] == 1 and dev["delta"]["admitted_strict"] == 1 and dev["delta"]["row_match_rate"] == round(1 - 0.8, 4)
    assert report["base_wave"].endswith("base") and report["adapter_wave"].endswith("adapter")


def test_compare_cli_binds_subsets_silver_density_and_over_cap_pages(tmp_path):
    from tools import vlm_ceiling
    from vlm.receipts import dump_new

    base = _write_wave(tmp_path, "base", [_receipt(SHA_A, pages=3, admitted=False, reasons=["balance_chain"], truncated_pages=(2,))])
    adapter = _write_wave(tmp_path, "adapter", [_receipt(SHA_A, pages=3, admitted=True)])
    manifest = tmp_path / "S.manifest.private.json"
    dump_new(manifest, {"manifest_version": 1, "name": "S", "data_scope": "synthetic", "set_sha256": "0" * 64, "archive_root": str(tmp_path),
                        "members": [{"sha": SHA_A, "relative_path": "a.pdf", "byte_size": 1, "page_count": 3, "folder_label": "fam",
                                     "classification": "digital", "outcome_class": "validated", "account_count": 1}]})
    dataset = tmp_path / "silver"
    dataset.mkdir()
    lines = [{"sha": SHA_A.lower(), "page": p, "target": {"rows": [{"amount": 1.0}] * n}} for p, n in enumerate([0, 12, 70])]
    (dataset / "validation.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\n", encoding="utf-8")
    lengths = tmp_path / "page-lengths.json"
    lengths.write_text(json.dumps({"items": [{"sha": SHA_A.lower(), "page": 2, "over_cap": True}, {"sha": SHA_A, "page": 1, "over_cap": False}]}), encoding="utf-8")
    out = tmp_path / "compare.json"
    code = vlm_ceiling.main(["compare", "--base-wave", str(base), "--adapter-wave", str(adapter), "--subset", f"S={manifest}",
                             "--silver-dataset", str(dataset), "--page-lengths", str(lengths), "--out", str(out)])
    assert code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    s = report["subsets"]["S"]
    assert report["over_cap_pages_known"] == 1 and report["reference_accounts"] == 0 and "not human-verified" in report["reference"]
    assert s["base"]["over_cap_pages"] == {"pages": 1, "invalid": 0, "truncated": 1} and s["adapter"]["over_cap_pages"]["truncated"] == 0
    assert s["base"]["by_density"]["61+ rows"]["truncated"] == 1 and s["delta"]["admitted_strict"] == 1
    assert vlm_ceiling.main(["compare", "--base-wave", str(base), "--adapter-wave", str(adapter), "--out", str(tmp_path / "x.json")]) == 2
    assert vlm_ceiling.main(["compare", "--base-wave", str(base), "--adapter-wave", str(adapter), "--subset", "bad", "--out", str(tmp_path / "y.json")]) == 2
