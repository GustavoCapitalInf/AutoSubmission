"""Silver labels: row-to-page alignment, page targets in the proposal schema, and the dataset build."""
import json

import pytest

from tests.paddle_synthetic import build_ledger_page, render_native_pdf
from vlm import silver
from vlm.partitions import Member
from vlm.receipts import Refused
from vlm.schema import validate_page_proposal

PAGE1 = ("SYNTHETIC BANK  Account 000123456789  Statement period 01/01/2031 to 01/31/2031\n"
         "Beginning balance 500.00\n01/02 SYNTHETIC ROW ONE 10.00 510.00\n01/03 SYNTHETIC ROW TWO 20.00 530.00\n")
PAGE2 = "01/04 SYNTHETIC ROW THREE 30.00 560.00\n01/05 SYNTHETIC ROW FOUR 40.00 600.00\nEnding balance 600.00 USD\n"
PAGE3 = "Account summary\nBeginning balance 500.00 Ending balance 600.00\nTotal credits 100.00 (4)\n"
STATEMENT = {"bank": "Synthetic Bank", "account_number": "000123456789", "currency": "USD", "period_start": "2031-01-01",
             "period_end": "2031-01-31", "beginning_balance": 500.0, "ending_balance": 600.0, "stated_total_credits": 100.0,
             "stated_total_debits": None, "stated_credit_count": 4, "stated_debit_count": None}
ROWS = [{"date": "2031-01-02", "description": "SYNTHETIC ROW ONE", "amount": 10.0, "direction": "credit", "running_balance": 510.0},
        {"date": "2031-01-03", "description": "SYNTHETIC ROW TWO", "amount": 20.0, "direction": "credit", "running_balance": 530.0},
        {"date": "2031-01-04", "description": "SYNTHETIC ROW THREE", "amount": 30.0, "direction": "credit", "running_balance": 560.0},
        {"date": "2031-01-05", "description": "SYNTHETIC ROW FOUR", "amount": 40.0, "direction": "credit", "running_balance": 600.0}]


def test_alignment_is_monotone_and_tiered():
    alignment = silver.align_rows(ROWS, [PAGE1, PAGE2, PAGE3])
    assert alignment.pages == (0, 0, 1, 1) and alignment.doc_tier == "strong" and set(alignment.tiers) == {"strong"}
    # an amount printed on an earlier page only (the summary) cannot be taken once the cursor has moved on
    late = ROWS + [{"date": "2031-01-06", "description": "NOWHERE", "amount": 77.77, "direction": "debit", "running_balance": 522.23}]
    assert silver.align_rows(late, [PAGE1, PAGE2, PAGE3]).doc_tier == "unassignable"
    # sectioned statements: the reader lists rows by date, so a row may sit on an EARLIER page than its predecessor
    sectioned = [ROWS[2], ROWS[0], ROWS[3], ROWS[1]]
    back = silver.align_rows(sectioned, [PAGE1, PAGE2, PAGE3])
    assert back.pages == (1, 0, 1, 0) and back.doc_tier == "strong"
    # the same strong row printed on two pages at equal distance from the previous row is only medium
    twin = silver.align_rows([ROWS[2], ROWS[0]], [PAGE1, PAGE2, PAGE1])
    assert twin.pages[0] == 1 and twin.tiers[1] == "medium"
    # amount present but neither the date nor a description token: weak
    weak = [{"date": "2031-02-09", "description": "UNRELATED WORDS", "amount": 10.0, "direction": "credit", "running_balance": 510.0}]
    assert silver.align_rows(weak, [PAGE1]).doc_tier == "weak"


def test_page_targets_only_state_what_the_page_prints():
    alignment = silver.align_rows(ROWS, [PAGE1, PAGE2, PAGE3])
    targets = silver.page_targets(STATEMENT, ROWS, alignment, [PAGE1, PAGE2, PAGE3])
    assert [targets[i]["page_role"] for i in range(3)] == ["statement_page", "statement_page", "summary_page"]
    assert not any(validate_page_proposal(t) for t in targets.values())
    p1, p2, p3 = targets[0], targets[1], targets[2]
    assert [r["date_text"] for r in p1["rows"]] == ["01/02", "01/03"] and p1["rows"][0]["balance"] == 510.0
    assert p1["account"]["bank"] == "Synthetic Bank" and p1["account"]["account_number_last4"] == "6789"
    assert p1["account"]["period_start"] == "2031-01-01" and p1["account"]["beginning_balance"] == 500.0 and p1["account"]["ending_balance"] is None
    assert p2["account"]["ending_balance"] == 600.0 and p2["account"]["currency"] == "USD" and p2["account"]["bank"] is None
    assert p3["rows"] == [] and p3["account"]["stated_total_credits"] == 100.0 and p3["account"]["stated_credit_count"] == 4
    assert p3["account"]["stated_total_debits"] is None and p3["account"]["stated_debit_count"] is None
    assert silver.canonical_target(p1) == silver.canonical_target(json.loads(json.dumps(p1)))


def test_split_is_family_stratified_and_deterministic():
    fam = {"A": [f"{i:064d}" for i in range(10)], "B": ["F" * 64]}
    splits = [silver.split_for(s, "A", seed="s", validation_fraction=0.2, family_shas=fam) for s in fam["A"]]
    assert splits.count("validation") == 2
    assert silver.split_for("F" * 64, "B", seed="s", validation_fraction=0.2, family_shas=fam) == "train"   # a lone member trains
    assert splits == [silver.split_for(s, "A", seed="s", validation_fraction=0.2, family_shas=fam) for s in fam["A"]]


def _synthetic_doc(tmp_path):
    archive = tmp_path / "archive"
    (archive / "fam").mkdir(parents=True)
    raw = render_native_pdf(build_ledger_page(n_rows=4))
    (archive / "fam" / "doc.pdf").write_bytes(raw)
    return archive


def test_build_silver_dataset_writes_images_targets_and_manifests(tmp_path):
    archive = _synthetic_doc(tmp_path)
    from tests.paddle_synthetic import SYNTHETIC_YEAR
    rows = [{"date": f"{SYNTHETIC_YEAR}-01-{i:02d}", "description": f"SYNTHETIC ROW {i:02d}", "amount": float(10 * i), "direction": "credit",
             "running_balance": 500.0 + sum(10 * j for j in range(1, i + 1))} for i in range(1, 5)]
    page_text = "\n".join(f"{SYNTHETIC_YEAR}-01-{i:02d} SYNTHETIC ROW {i:02d} {10 * i:.2f}" for i in range(1, 5))
    statement = {**STATEMENT, "transactions": rows, "period_start": f"{SYNTHETIC_YEAR}-01-01", "period_end": f"{SYNTHETIC_YEAR}-01-31"}
    members = [Member("A" * 64, "fam/doc.pdf", 100, 1, "fam", "digital", "validated", 1),
               Member("B" * 64, "fam/doc.pdf", 100, 1, "fam", "digital", "validated", 1)]
    readers = {"A" * 64: (statement, [page_text]), "B" * 64: None}
    public = silver.build_silver_dataset(tmp_path / "ds", members, archive_root=archive, reader=readers.get, excluded=set(), held16=frozenset())
    assert public["counts"]["documents"] == 1 and public["counts"]["pages"] == 1 and public["counts"]["no_payload"] == 1
    assert public["page_roles"] == {"statement_page": 1} and public["document_tiers"] == {"strong": 1}
    line = json.loads((tmp_path / "ds" / "train.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert line["sha"] == "A" * 64 and (tmp_path / "ds" / line["image"]).is_file() and len(line["target"]["rows"]) == 4
    assert not validate_page_proposal(line["target"])
    manifest = json.loads((tmp_path / "ds" / "manifest.json").read_text(encoding="utf-8"))
    assert "relative_path" not in json.dumps(manifest) and manifest["jsonl_sha256"]["train"]
    with pytest.raises(Refused) as exc:
        silver.build_silver_dataset(tmp_path / "ds2", members, archive_root=archive, reader=readers.get, excluded={"A" * 64}, held16=frozenset())
    assert exc.value.code == "member_in_excluded_partition"
    with pytest.raises(Refused) as exc:
        silver.build_silver_dataset(tmp_path / "ds3", members, archive_root=archive, reader=readers.get, excluded=set(), held16=frozenset({"B" * 16}))
    assert exc.value.code == "member_in_holdout"
