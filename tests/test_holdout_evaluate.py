"""P22-HOLDOUT item 4: the evaluation event (skeleton), proven on a
synthetic store + a synthetic rows.csv.

FALSE ACCEPT = system `validated` AND the oracle contradicts a PARSED money
identity or a sampled row (never from the verdict alone — M12; never from an
unparseable export value — review MINOR-3a); `agree` needs at least one money
identity, else `agree_partial` (review MINOR-3b); FALSE REFUSAL = oracle
complete + legible statement AND system not validated (classified A/B/C from
the row); items compared are marked `evaluated` WITH the engine version
(M11); a store or manifest that disagrees with its sidecar refuses the
evaluation (review MAJOR-1); aggregates only on stdout; the private report
refuses the checkout.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from tools.holdout import evaluate as evaluate_mod
from tools.holdout.manifest import HoldoutManifest, build_strata, dev_corpus_from_rows
from tools.holdout.store import ChainError, StoreLocationError, TruthStore

ROOT = Path(__file__).resolve().parents[1]

ROW_COLUMNS = ["relative_path", "folder_label", "content_sha256", "valid_pdf", "classification",
               "page_count", "outcome_class", "outcome_reason", "failure_class", "source_path",
               "parser_id", "account_count"]
FIGURE_COLUMNS = ["content_sha256", "account_count", "printed_period_start", "printed_period_end",
                  "opening_balance", "closing_balance", "printed_transaction_count"]
LEDGER_COLUMNS = ["content_sha256", "date", "description", "amount"]


def sha(label: str) -> str:
    return hashlib.sha256(f"synthetic-eval:{label}".encode()).hexdigest().upper()


S = {name: sha(name) for name in ("agree", "false_accept", "false_refusal", "consistent", "unjudged",
                                  "row_absent", "unadjudicated", "kind_conflict", "unparseable")}
DEV = sorted(sha(f"dev-{i}") for i in range(3))


def complete(**overrides) -> dict:
    fields = dict(kind="STATEMENT_COMPLETE", sub_kind=None, account_kind="deposit", modality="digital",
                  completeness_findings=[], legible=True, account_count=1,
                  printed_period_start="2031-01-01", printed_period_end="2031-01-31",
                  opening_balance="100.00", closing_balance="150.25", printed_transaction_count=3,
                  sampled_rows=[{"date": "2031-01-05", "description": "SYNTHETIC ROW ONE", "amount": "-12.34"}],
                  adjudicator="principal_adjudicator", packet_digest="cd" * 32, notes=None)
    fields.update(overrides)
    return fields


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})
    return path


def row(sha_value: str, outcome: str, **overrides) -> dict:
    base = dict(relative_path=f"synthetic/{sha_value[:8]}.pdf", folder_label="synthetic",
                content_sha256=sha_value, valid_pdf="True", classification="digital", page_count="2",
                outcome_class=outcome, outcome_reason="" if outcome == "validated" else "no_parser_matched",
                failure_class="" if outcome == "validated" else "B", source_path="native",
                parser_id="synthetic_parser" if outcome == "validated" else "", account_count="1")
    base.update(overrides)
    return base


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("SEALED_TRUTH_DIR", str(tmp_path / "sealed"))
    store = TruthStore.open()
    manifest = HoldoutManifest.open()
    store.append_record(content_sha256=S["agree"], **complete())
    store.append_record(content_sha256=S["false_accept"], **complete())
    store.append_record(content_sha256=S["false_refusal"], **complete())
    store.append_record(content_sha256=S["consistent"], **complete(
        kind="NOT_A_STATEMENT", sub_kind="deposit_slip", account_count=None, printed_period_start=None,
        printed_period_end=None, opening_balance=None, closing_balance=None,
        printed_transaction_count=None, sampled_rows=[]))
    store.append_record(content_sha256=S["unjudged"], **complete(
        account_count=None, printed_period_start=None, printed_period_end=None, opening_balance=None,
        closing_balance=None, printed_transaction_count=None, sampled_rows=[]))
    store.append_record(content_sha256=S["row_absent"], **complete())
    store.append_record(content_sha256=S["kind_conflict"], **complete(kind="STATEMENT_PARTIAL",
                                                                      completeness_findings=["page_gap"]))
    store.append_record(content_sha256=S["unparseable"], **complete(sampled_rows=[]))
    dev_corpus = dev_corpus_from_rows(write_csv(tmp_path / "dev_rows.csv", ROW_COLUMNS,
                                                [row(d, "validated") for d in DEV]))
    for name in S:
        familiarity = "unknown_bank" if name in ("agree", "false_accept") else "known_bank"
        manifest.add(content_sha256=S[name], source_batch="unseen-2031-01", dev_corpus=dev_corpus,
                     strata=build_strata(modality="digital", bank_familiarity=familiarity,
                                         account_shape="single", table_shape="table_heavy",
                                         currency="USD", page_count=2, layout_family_code="fam_x"))
    rows = write_csv(tmp_path / "rows.csv", ROW_COLUMNS, [
        row(S["agree"], "validated"),
        row(S["false_accept"], "validated"),
        row(S["false_refusal"], "failed"),
        row(S["consistent"], "failed"),
        row(S["unjudged"], "validated", account_count=""),
        row(S["row_absent"], "validated"),
        row(S["unadjudicated"], "failed"),
        row(S["kind_conflict"], "validated"),
        row(S["unparseable"], "validated"),
        # a second, worse row for the same sha must not hide the validated one
        row(S["agree"], "failed", relative_path="synthetic/duplicate.pdf"),
    ])
    figures = write_csv(tmp_path / "figures.csv", FIGURE_COLUMNS, [
        dict(content_sha256=S["agree"], account_count="1", printed_period_start="2031-01-01",
             printed_period_end="2031-01-31", opening_balance="100.00", closing_balance="150.25",
             printed_transaction_count="3"),
        dict(content_sha256=S["false_accept"], account_count="1", printed_period_start="2031-01-01",
             printed_period_end="2031-01-31", opening_balance="100.00", closing_balance="284708.19",
             printed_transaction_count="3"),
        dict(content_sha256=S["row_absent"], account_count="1", opening_balance="100.00",
             closing_balance="150.25"),
        dict(content_sha256=S["kind_conflict"], account_count="1", opening_balance="100.00",
             closing_balance="150.25"),
        # MINOR-3a: an export that could not produce the figure
        dict(content_sha256=S["unparseable"], account_count="1", closing_balance="n/a"),
    ])
    ledger = write_csv(tmp_path / "ledger.csv", LEDGER_COLUMNS, [
        dict(content_sha256=S["agree"], date="2031-01-05", description="synthetic row one", amount="-12.34"),
        dict(content_sha256=S["false_accept"], date="2031-01-05", description="SYNTHETIC ROW ONE", amount="-12.34"),
        dict(content_sha256=S["row_absent"], date="2031-01-05", description="A DIFFERENT SYNTHETIC ROW", amount="-12.34"),
        dict(content_sha256=S["kind_conflict"], date="2031-01-05", description="SYNTHETIC ROW ONE", amount="-12.34"),
    ])
    return dict(tmp=tmp_path, store=store, manifest=manifest, rows=rows, figures=figures, ledger=ledger)


def run(world, **overrides) -> dict:
    kwargs = dict(store=world["store"], manifest=world["manifest"], engine_version="engine-synthetic-1",
                  run_id="run-synthetic-1", figures_csv=world["figures"], ledger_csv=world["ledger"],
                  report_path=world["tmp"] / "private" / "report.json", out=lambda *a, **k: None)
    kwargs.update(overrides)
    return evaluate_mod.evaluate_run(world["rows"], **kwargs)


def test_the_synthetic_evaluation_reports_each_judgement(world):
    result = run(world)
    assert result["items"] == 9
    assert result["compared"] == 8
    assert result["false_accept"] == 2
    assert result["false_refusal"] == 1
    assert result["agree"] == 1
    assert result["agree_partial"] == 1
    assert result["not_judgeable"] == 1
    assert result["consistent_refusal"] == 1
    assert result["kind_conflict"] == 1
    assert result["not_adjudicated"] == 1
    assert result["miss_class"] == {"A": 0, "B": 1, "C": 0, "unclassified": 0}
    assert result["layout_generalization"] == 1
    assert result["engine_version"] == "engine-synthetic-1"
    by_sha16 = {d["sha16"]: d for d in result["details"]}
    assert by_sha16[S["false_accept"][:16]]["contradictions"] == ["closing_balance"]
    assert by_sha16[S["row_absent"][:16]]["contradictions"] == ["sampled_row_absent"]
    assert by_sha16[S["agree"][:16]]["judgement"] == "agree"
    assert by_sha16[S["agree"][:16]]["money_compared"] == 3  # opening, closing, one ledger row
    assert by_sha16[S["agree"][:16]]["system_outcome"] == "validated"
    assert by_sha16[S["false_refusal"][:16]]["miss_class"] == "B"
    assert by_sha16[S["kind_conflict"][:16]]["judgement"] == "kind_conflict"


def test_an_unparseable_system_figure_is_never_a_contradiction(world):
    """Review MINOR-3a: `n/a` in a figures export is listed, not compared."""
    result = run(world)
    detail = {d["sha16"]: d for d in result["details"]}[S["unparseable"][:16]]
    assert detail["judgement"] == "agree_partial"
    assert detail["contradictions"] == []
    assert detail["unparseable"] == ["closing_balance"]
    assert detail["compared"] == 1 and detail["money_compared"] == 0


def test_false_accept_needs_an_oracle_contradiction_never_the_verdict_alone(world):
    """M12's killer: a validated document with no comparable oracle material
    is `not_judgeable`, and one whose oracle agrees is `agree`."""
    result = run(world)
    by_sha16 = {d["sha16"]: d for d in result["details"]}
    assert by_sha16[S["unjudged"][:16]]["judgement"] == "not_judgeable"
    assert by_sha16[S["unjudged"][:16]]["contradictions"] == []
    assert by_sha16[S["agree"][:16]]["judgement"] == "agree"
    # Without figures and ledger nothing but the row's own account_count can be compared.
    world["manifest"] = HoldoutManifest.open()
    result2 = run(world, figures_csv=None, ledger_csv=None, run_id="run-synthetic-2")
    by2 = {d["sha16"]: d for d in result2["details"]}
    assert by2[S["false_accept"][:16]]["judgement"] == "agree_partial"
    assert result2["false_accept"] == 0 and result2["agree"] == 0


def test_agree_requires_a_money_identity(world):
    """Review MINOR-3b: `account_count` alone is `agree_partial`, never `agree`."""
    world["manifest"] = HoldoutManifest.open()
    result = run(world, figures_csv=None, ledger_csv=None)
    judgements = {d["sha16"]: d["judgement"] for d in result["details"]}
    assert judgements[S["agree"][:16]] == "agree_partial"
    assert result["agree"] == 0
    assert result["agree_partial"] >= 1
    assert "agree_partial" in evaluate_mod.JUDGEMENTS


def test_items_compared_are_marked_evaluated_with_the_engine_version(world):
    """M11's killer."""
    run(world)
    items = HoldoutManifest.open().by_sha()
    for name in S:
        item = items[S[name]]
        if name == "unadjudicated":
            assert item["status"] == "unseen" and item["last_engine_version"] is None
        else:
            assert item["status"] == "evaluated"
            assert item["last_engine_version"] == "engine-synthetic-1"
            assert item["evaluation_run_id"] == "run-synthetic-1"
            assert item["last_evaluated_at"].endswith("+00:00")


def test_a_second_evaluation_records_the_new_engine_version(world):
    run(world)
    world["manifest"] = HoldoutManifest.open()
    run(world, engine_version="engine-synthetic-2", run_id="run-synthetic-2")
    items = HoldoutManifest.open().by_sha()
    assert items[S["agree"]]["last_engine_version"] == "engine-synthetic-2"
    assert items[S["agree"]]["status"] == "evaluated"


def test_burned_and_graduated_items_are_not_evaluated(world):
    manifest = world["manifest"]
    item = manifest.by_sha()[S["agree"]]
    manifest.record_evaluation(item["holdout_id"], engine_version="engine-v0", evaluation_run_id="run-0")
    manifest.burn(item["holdout_id"], burned_by="P24-LAYOUT")
    result = run(world)
    assert result["items"] == 8
    assert HoldoutManifest.open().by_sha()[S["agree"]]["status"] == "burned"


def test_a_truncated_store_or_manifest_refuses_the_evaluation(world):
    """Review MAJOR-1: no evaluation reads a file that disagrees with its sidecar."""
    truth = world["tmp"] / "sealed" / "truth.jsonl"
    lines = truth.read_text(encoding="utf-8").splitlines()
    truth.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ChainError):
        run(world)
    truth.write_text("\n".join(lines) + "\n", encoding="utf-8")
    holdout = world["tmp"] / "sealed" / "holdout.jsonl"
    events = holdout.read_text(encoding="utf-8").splitlines()
    holdout.write_text("\n".join(events[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ChainError):
        run(world)
    assert HoldoutManifest.open().events()[-1]["status"] == "unseen"  # nothing was marked


def test_stdout_carries_aggregates_only(world, capsys):
    lines: list[str] = []
    run(world, out=lines.append)
    text = "\n".join(lines)
    assert "false_accept: 2" in text and "false_refusal: 1" in text and "agree_partial: 1" in text
    for value in S.values():
        assert value not in text and value[:16] not in text
    assert "150" not in text


def test_the_private_report_refuses_the_checkout(world):
    with pytest.raises(StoreLocationError):
        run(world, report_path=ROOT / "private_report_probe.json")
    assert not (ROOT / "private_report_probe.json").exists()


def test_the_private_report_is_written_outside(world):
    import json

    result = run(world)
    report = json.loads((world["tmp"] / "private" / "report.json").read_text(encoding="utf-8"))
    assert report["aggregates"]["false_accept"] == 2
    assert len(report["details"]) == result["items"]


@pytest.mark.parametrize(
    "row_fields,expected",
    [
        (dict(failure_class="B"), "B"),
        (dict(failure_class="C"), "C"),
        (dict(failure_class="A"), "A"),
        (dict(failure_class="", outcome_reason="deferred_visual_ocr"), "A"),
        (dict(failure_class="", outcome_reason="invalid_pdf"), "A"),
        (dict(failure_class="", outcome_reason="no_parser_matched"), "B"),
        (dict(failure_class="", outcome_reason="parser_declined"), "B"),
        (dict(failure_class="", outcome_reason="withheld_adb"), "C"),
        (dict(failure_class="", outcome_reason="integrity_flags"), "C"),
        (dict(failure_class="", outcome_reason="something_new"), "unclassified"),
    ],
)
def test_miss_classification_follows_the_row(row_fields, expected):
    assert evaluate_mod.classify_miss(row_fields) == expected


def test_cli_entry_point_requires_the_store_and_prints_aggregates(world, capsys, monkeypatch):
    rc = evaluate_mod.main([
        "--rows", str(world["rows"]), "--engine-version", "engine-synthetic-1", "--run-id",
        "run-synthetic-1", "--figures", str(world["figures"]), "--ledger", str(world["ledger"]),
        "--report", str(world["tmp"] / "private" / "report.json"),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "false_accept: 2" in out
    monkeypatch.delenv("SEALED_TRUTH_DIR")
    assert evaluate_mod.main(["--rows", str(world["rows"]), "--engine-version", "e", "--run-id", "r"]) != 0


# --- review NEW-1: money is compared by VALUE, never by text -----------------


def test_money_is_compared_by_value_never_by_text(tmp_path, monkeypatch):
    """Review NEW-1 (M22's killer): every formatting variant of one figure
    compares EQUAL (`100` vs `100.00`, `150.25` vs `150.250`, `0.00` vs
    `-0.00` / `0`, a ledger amount printed with an extra decimal), and a
    genuinely different figure still contradicts."""
    monkeypatch.setenv("SEALED_TRUTH_DIR", str(tmp_path / "sealed"))
    store = TruthStore.open()
    manifest = HoldoutManifest.open()
    shas = {name: sha(f"scale-{name}") for name in ("scale", "negzero", "ledger_scale", "different")}
    store.append_record(content_sha256=shas["scale"], **complete(opening_balance="100", closing_balance="150.25"))
    store.append_record(content_sha256=shas["negzero"], **complete(opening_balance="0.00", closing_balance="0.00",
                                                                    sampled_rows=[]))
    store.append_record(content_sha256=shas["ledger_scale"], **complete())
    store.append_record(content_sha256=shas["different"], **complete(closing_balance="150.25"))
    dev_corpus = dev_corpus_from_rows(write_csv(tmp_path / "dev_rows.csv", ROW_COLUMNS,
                                                [row(d, "validated") for d in DEV]))
    for name in shas:
        manifest.add(content_sha256=shas[name], source_batch="unseen-2031-01", dev_corpus=dev_corpus,
                     strata=build_strata(modality="digital", bank_familiarity="known_bank",
                                         account_shape="single", table_shape="table_heavy",
                                         currency="USD", page_count=2, layout_family_code="fam_x"))
    rows = write_csv(tmp_path / "rows.csv", ROW_COLUMNS, [row(shas[n], "validated") for n in shas])
    figures = write_csv(tmp_path / "figures.csv", FIGURE_COLUMNS, [
        dict(content_sha256=shas["scale"], account_count="1", opening_balance="100.00", closing_balance="150.250"),
        dict(content_sha256=shas["negzero"], account_count="1", opening_balance="-0.00", closing_balance="0"),
        dict(content_sha256=shas["ledger_scale"], account_count="1", opening_balance="100.000", closing_balance="150.25"),
        dict(content_sha256=shas["different"], account_count="1", opening_balance="100.00", closing_balance="928471.03"),
    ])
    ledger = write_csv(tmp_path / "ledger.csv", LEDGER_COLUMNS, [
        dict(content_sha256=shas["scale"], date="2031-01-05", description="SYNTHETIC ROW ONE", amount="-12.340"),
        dict(content_sha256=shas["ledger_scale"], date="2031-01-05", description="synthetic row one", amount="-12.3400"),
        dict(content_sha256=shas["different"], date="2031-01-05", description="SYNTHETIC ROW ONE", amount="-12.34"),
    ])
    result = evaluate_mod.evaluate_run(rows, store=store, manifest=manifest, engine_version="engine-scale",
                                       run_id="run-scale", figures_csv=figures, ledger_csv=ledger,
                                       out=lambda *a, **k: None)
    by = {d["sha16"]: d for d in result["details"]}
    for name in ("scale", "negzero", "ledger_scale"):
        assert by[shas[name][:16]]["contradictions"] == [], name
        assert by[shas[name][:16]]["judgement"] == "agree", name
    assert by[shas["scale"][:16]]["money_compared"] == 3
    assert by[shas["different"][:16]]["judgement"] == "false_accept"
    assert by[shas["different"][:16]]["contradictions"] == ["closing_balance"]
    assert result["false_accept"] == 1 and result["agree"] == 3


@pytest.mark.parametrize(
    "left,right",
    [("100", "100.00"), ("100.000", "100"), ("0.00", "-0.00"), ("0", "-0"), ("150.250", "150.25"),
     ("-12.34", "-12.3400"), ("1E+2", "100.00")],
)
def test_money_keys_and_values_agree_across_scale_and_sign_of_zero(left, right):
    assert evaluate_mod.money_key(left) == evaluate_mod.money_key(right)
    assert evaluate_mod._canon_money(left) == evaluate_mod._canon_money(right)
    assert evaluate_mod.money_key("0.00") == "0" and evaluate_mod.money_key("-0.00") == "0"


def test_money_values_that_differ_still_differ():
    assert evaluate_mod.money_key("928471.03") != evaluate_mod.money_key("928471.04")
    assert evaluate_mod._canon_money("100.00") != evaluate_mod._canon_money("100.01")
    assert evaluate_mod.money_key("n/a") is None and evaluate_mod.money_key("") is None
