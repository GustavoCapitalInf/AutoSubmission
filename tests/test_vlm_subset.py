"""The statement-likeness screen and the derived manifest (2026-09-18: the unresolved population holds
voided checks, identity documents and transaction-less pages; the ceiling is reported on both denominators)."""
import json

import pytest

from vlm import subset
from vlm.receipts import Refused

STATEMENT_TEXT = "STATEMENT PERIOD 01/01/2031 - 01/31/2031\nBEGINNING BALANCE 500.00\n" + "\n".join(
    f"01/{i:02d} SYNTHETIC ROW {i:02d} {10 * i:.2f} {500 + 10 * i:.2f}" for i in range(1, 21)) + "\nENDING BALANCE 2,600.00\n"


def test_screen_buckets():
    assert subset.screen_text(STATEMENT_TEXT)[0] == "statement_like"
    assert subset.screen_text(None)[0] == "no_text_extracted"
    assert subset.screen_text("   ")[0] == "no_text_extracted"
    assert subset.screen_text("VOID VOID this cheque is void. Pay to the order of 25.00")[0] == "non_statement_document"
    assert subset.screen_text("Driver's license. State ID. Name and address only.")[0] == "non_statement_document"
    assert subset.screen_text("Account summary page. No transactions this period. Balance 12.00")[0] == "no_transactions_text"
    assert subset.screen_text("01/02 fee 5.00 01/03 fee 6.00 01/04 fee 7.00 01/05 fee 8.00 statement period")[0] == "thin_statement_text"
    amounts = " ".join(f"{i + 0.5:.2f} 01/{(i % 28) + 1:02d}" for i in range(1, 30))
    assert subset.screen_text(amounts)[0] == "many_amounts_no_statement_words"
    bucket, counts = subset.screen_text(STATEMENT_TEXT)
    assert counts["money"] >= 40 and counts["dates"] >= 20 and counts["statement_words"] >= 3


def _manifest(tmp_path, members):
    path = tmp_path / "SRC.manifest.private.json"
    path.write_text(json.dumps({"manifest_version": 1, "name": "SRC", "data_scope": "customer", "set_sha256": "x",
                                "archive_root": "archive", "members": members}), encoding="utf-8")
    return path


def _member(sha, pages=3, outcome="failed"):
    return {"sha": sha, "relative_path": f"fam/{sha}.pdf", "byte_size": 1000, "page_count": pages, "folder_label": "fam",
            "classification": "digital", "outcome_class": outcome, "account_count": 0}


def test_derive_subset_keeps_statement_like_members_and_records_the_rule(tmp_path):
    members = [_member("A" * 64), _member("B" * 64, pages=1), _member("C" * 64, pages=2)]
    texts = {"A" * 64: STATEMENT_TEXT, "B" * 64: "VOID VOID cheque 25.00", "C" * 64: None}
    public, private = subset.derive_subset(_manifest(tmp_path, members), "SUB", tmp_path / "out", text_of=texts.get)
    assert public["documents"] == 1 and public["pages"] == 3 and private["members"][0]["sha"] == "A" * 64
    assert public["derived_from"]["buckets"] == {"no_text_extracted": 1, "non_statement_document": 1, "statement_like": 1}
    assert public["derived_from"]["documents"] == 3 and public["derived_from"]["rule"]["screen_version"] == subset.SCREEN_VERSION
    assert public["derived_from"]["manifest"]["sha256"] and private["data_scope"] == "customer" and private["archive_root"] == "archive"
    assert (tmp_path / "out" / "SUB.manifest.json").is_file() and (tmp_path / "out" / "SUB.manifest.private.json").is_file()
    written = json.loads((tmp_path / "out" / "SUB.manifest.json").read_text(encoding="utf-8"))
    assert "members" not in written and "relative_path" not in json.dumps(written)


def test_derive_subset_refuses_an_empty_subset_and_a_non_customer_source(tmp_path):
    members = [_member("B" * 64)]
    with pytest.raises(Refused) as exc:
        subset.derive_subset(_manifest(tmp_path, members), "SUB", tmp_path / "out", text_of=lambda sha: "VOID VOID 1.00")
    assert exc.value.code == "subset_empty"
    path = tmp_path / "SYN.manifest.private.json"
    path.write_text(json.dumps({"manifest_version": 1, "name": "SYN", "data_scope": "synthetic", "archive_root": "a", "members": members}),
                    encoding="utf-8")
    with pytest.raises(Refused) as exc:
        subset.derive_subset(path, "SUB", tmp_path / "out2", text_of=lambda sha: STATEMENT_TEXT)
    assert exc.value.code == "subset_source_not_customer"
