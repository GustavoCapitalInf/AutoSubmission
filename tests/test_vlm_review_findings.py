"""Reviewer counterexamples for the Phase 3 ceiling harness (CEILING-HARNESS-REVIEW-X.md), INVERTED.

Reviewer X wrote these as characterisation tests pinning the defects. Each is now asserted the other
way round, so the suite fails again if any closure regresses. No real statement is read; every fixture
is synthetic.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from vlm import metadata, runner
from vlm.assemble import CandidateRow
from vlm.gate import gate
from vlm.metadata import EMPTY_META, AccountMeta
from vlm.partitions import Member
from vlm.proposals import PageProposal, merge_pages
from vlm.schema import empty_proposal

REMOTE = SimpleNamespace(provider="vast.ai", execution_class="remote_paid", is_remote=True)


def _row(day: int, amount: str, direction: str, balance: str | None, desc: str = "SYNTHETIC ROW") -> CandidateRow:
    return CandidateRow(date=f"2031-01-{day:02d}", date_text=f"01/{day:02d}", description=f"{desc} {day:02d}",
                        amount=Decimal(amount), direction=direction,
                        balance=None if balance is None else Decimal(balance), page=0, source="stage_b",
                        locator=f"p0r{day}")


def _chain(n: int, *, beginning: Decimal = Decimal("500.00")) -> list[CandidateRow]:
    rows, balance = [], beginning
    for day in range(1, n + 1):
        amount = Decimal(day * 10)
        balance += amount
        rows.append(_row(day, f"{amount:.2f}", "credit", f"{balance:.2f}"))
    return rows


# MAJOR-1 — closed: with neither anchor printed the gate refuses; a truncated read cannot pass
def test_gate_refuses_when_both_anchors_would_be_derived():
    full, short = _chain(6), _chain(6)[:3]
    for rows in (full, short):
        verdict = gate(rows, EMPTY_META)
        assert not verdict.admitted and "anchors_underdetermined" in verdict.reasons and verdict.anchored == "none"


# GATE-3 — closed: chain-derived directions are accepted only under two printed anchors
def test_chain_derived_directions_are_refused_without_both_printed_anchors():
    rows = [_row(1, "100.00", "credit", "600.00"), _row(2, "50.00", "unknown", "650.00")]
    assert not gate(rows, EMPTY_META).admitted
    one_side = AccountMeta(Decimal("500.00"), None, None, None, "USD", None, None, ())
    verdict = gate(rows, one_side)
    assert not verdict.admitted and "chain_direction_unanchored" in verdict.reasons


# MAJOR-4 — closed: the printed totals and counts reach reconcile
def test_the_gate_gives_reconcile_the_banks_printed_totals_and_counts():
    from analysis.reconcile import reconcile
    from vlm.gate import statement_from

    assert "stated_total_credits" in empty_proposal()["account"]
    meta = AccountMeta(Decimal("500.00"), Decimal("560.00"), None, None, "USD", None, None, (),
                       Decimal("60.00"), Decimal("0.00"), 3, 0)
    statement = statement_from(_chain(3), meta)
    assert statement.stated_total_credits == 60.0 and statement.stated_credit_count == 3
    result = reconcile(statement)
    assert result.summary_ok is True and result.stated_credit_count_matches is True
    wrong = AccountMeta(Decimal("500.00"), Decimal("560.00"), None, None, "USD", None, None, (), Decimal("90.00"), Decimal("0.00"), 4, 0)
    verdict = gate(_chain(3), wrong)
    assert "summary_mismatch" in verdict.reasons and "count_mismatch" in verdict.reasons


# MAJOR-2 — closed: an unverifiable repeat is a reason code, not an admission
def test_duplicate_row_masking_a_missing_row_is_refused_when_no_balances_are_printed():
    meta = AccountMeta(Decimal("1000.00"), Decimal("800.00"), "2031-01-01", "2031-01-31", "USD", None, None, ("test",))
    truthful = [_row(5, "100.00", "debit", None, "RENT"), _row(6, "100.00", "debit", None, "INSURANCE")]
    duplicated = [_row(5, "100.00", "debit", None, "RENT"), _row(5, "100.00", "debit", None, "RENT")]
    assert gate(truthful, meta).admitted
    verdict = gate(duplicated, meta)
    assert not verdict.admitted and "duplicate_row" in verdict.reasons and verdict.admitted_rows == ()


# MAJOR-8 — closed: a row with its own amount is never a continuation, and the case is counted
def test_continues_previous_with_an_amount_keeps_the_row_and_counts_it():
    proposal = empty_proposal("statement_page")
    proposal["account"].update({"beginning_balance": 500.0, "ending_balance": 560.0})
    proposal["rows"] = [
        {"date": "2031-01-01", "date_text": "01/01", "description": "DEPOSIT", "amount": 10.0,
         "direction": "credit", "balance": 510.0, "continues_previous": False},
        {"date": "2031-01-02", "date_text": "01/02", "description": "DEPOSIT TWO", "amount": 50.0,
         "direction": "credit", "balance": 560.0, "continues_previous": True},
    ]
    rows, meta, stats = merge_pages([PageProposal(0, proposal, ())])
    assert len(rows) == 2 and rows[1].amount == Decimal("50.00")
    assert stats["continuation_rows_with_amount"] == 1
    verdict = gate(rows, meta)
    assert verdict.admitted and verdict.computed_ending == Decimal("560.00")


# META-1 — closed
def test_beginning_balance_takes_the_money_after_its_own_label():
    meta = metadata.extract_meta(["Beginning balance 500.00 Ending balance 600.00"])
    assert meta.beginning_balance == Decimal("500.00") and meta.ending_balance == Decimal("600.00")


# BLOCK-1 — closed: the public stats carry a count and a digest, never the digits
def test_public_stats_never_carry_the_extracted_account_last4():
    proposal = empty_proposal("statement_page")
    proposal["account"]["account_number_last4"] = "4821"
    _, _, stats = merge_pages([PageProposal(0, proposal, ())])
    assert "account_last4_values" not in stats and stats["account_last4_count"] == 1
    assert "4821" not in json.dumps(stats)
    source = Path("vlm/runner.py").read_text(encoding="utf-8")
    assert "account_last4_values" not in source


# BLOCK-2 — closed: the worker echoes the declaration and the runner checks it before any page
def test_worker_identity_echo_exists_and_is_checked():
    from vlm import stage_a_worker

    identity = stage_a_worker.version_payload({"PADDLE_PROVIDER": "vast.ai", "PADDLE_EXECUTION_CLASS": "remote_paid"},
                                              versions={"paddleocr": "3.7.0", "paddlex": "3.7.2"})
    assert identity["provider"] == "vast.ai" and identity["execution_class"] == "remote_paid"
    text = Path("vlm/runner.py").read_text(encoding="utf-8")
    assert "verify_identity" in text and "execution_class" in text and "local_declaration_with_model_endpoints" in text


# BLOCK-3 — closed: the scope is bound to the manifest and there is no flag
def test_cli_scope_comes_from_the_manifest(tmp_path, monkeypatch):
    from tools import vlm_ceiling
    from vlm.receipts import dump_new

    archive = tmp_path / "archive"
    (archive / "fam").mkdir(parents=True)
    (archive / "fam" / "d.pdf").write_bytes(b"%PDF-1.4 synthetic")
    member = {"sha": "A" * 64, "relative_path": "fam/d.pdf", "byte_size": 18, "page_count": 1, "folder_label": "fam",
              "classification": "digital", "outcome_class": "validated", "account_count": 1}
    private = tmp_path / "CTRL.manifest.private.json"
    dump_new(private, {"manifest_version": 1, "name": "CTRL", "data_scope": "customer", "set_sha256": "0" * 64,
                       "archive_root": str(archive), "members": [member]})
    seen: list[str] = []
    monkeypatch.setattr(vlm_ceiling, "default_authorize", lambda scope: seen.append(scope))
    with pytest.raises(SystemExit):
        vlm_ceiling.main(["run", "--arm", "reader_baseline", "--manifest", str(private), "--out", str(tmp_path / "wave"),
                          "--data-scope", "synthetic"])
    code = vlm_ceiling.main(["run", "--arm", "reader_baseline", "--manifest", str(private), "--out", str(tmp_path / "wave")])
    assert code == 0 and seen == ["customer"]
    launch = json.loads((tmp_path / "wave" / "launch.json").read_text(encoding="utf-8"))
    assert launch["data_scope"] == "customer" and launch["manifest_scope"] == "customer"


class _Broken:
    def version(self):
        return {"provider": "vast.ai", "execution_class": "remote_paid"}

    def parse_page(self, *args, **kwargs):
        from vlm.client import TransportError

        raise TransportError("connection_failed:ConnectionRefusedError")


def _synthetic_archive(tmp_path: Path) -> Path:
    from tests.paddle_synthetic import build_ledger_page, render_native_pdf

    archive = tmp_path / "archive"
    (archive / "fam").mkdir(parents=True)
    (archive / "fam" / "doc.pdf").write_bytes(render_native_pdf(build_ledger_page(n_rows=3)))
    return archive


def _members(n: int) -> list[Member]:
    return [Member(f"{i:064X}", "fam/doc.pdf", 100, 1, "fam", "digital", "failed", 1) for i in range(n)]


def _ctx(arm: str, **kw):
    base = dict(arm=arm, stage_a=None, stage_b=None, stage_b_model="fake", truth=None, long_edge=600, quality=80,
                seed=0, data_scope="synthetic", hourly_rate=None)
    base.update(kw)
    return runner.RunContext(**base)


BINDING = {"path": "m", "sha256": "0" * 64}


def _wave(members, ctx, out, archive, **kw):
    params = dict(archive_root=archive, manifest_binding=BINDING, manifest_scope="synthetic", authorize=lambda s: None,
                  git_tip="x", settings=REMOTE)
    params.update(kw)
    return runner.run_wave(members, ctx, out, **params)


# MAJOR-5 — closed
def test_resume_retries_documents_that_only_have_a_failure_receipt(tmp_path):
    archive = _synthetic_archive(tmp_path)
    first = _wave(_members(5), _ctx("stage_a_rules", stage_a=_Broken()), tmp_path / "w1", archive)
    assert first["status"] == "failed" and first["counts"]["failed"] == 3
    second = _wave(_members(5), _ctx("stage_a_rules", stage_a=_Broken()), tmp_path / "w2", archive, resume_from=tmp_path / "w1")
    assert second["counts"]["skipped_existing"] == 0


# RES-2 — closed
def test_limit_is_not_counted_as_skipped_existing(tmp_path):
    archive = _synthetic_archive(tmp_path)
    result = _wave(_members(4), _ctx("reader_baseline"), tmp_path / "w", archive, limit=1, settings=None)
    assert result["counts"]["attempted"] == 1 and result["counts"]["skipped_existing"] == 0 and result["counts"]["limited_out"] == 3


# MAJOR-6 — closed
def test_interrupted_wave_is_receipted_as_aborted(tmp_path):
    archive = _synthetic_archive(tmp_path)

    class _Interrupting(_Broken):
        def parse_page(self, *args, **kwargs):
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        _wave(_members(2), _ctx("stage_a_rules", stage_a=_Interrupting()), tmp_path / "w", archive)
    result = json.loads((tmp_path / "w" / "result.json").read_text(encoding="utf-8"))
    release = json.loads((tmp_path / "w" / "release.json").read_text(encoding="utf-8"))
    assert result["status"] == "aborted" and release["controller_exit"] == 1


# MAJOR-7 — closed: weights bound, prompt TEMPLATES hashed
def test_launch_receipt_pins_weights_and_prompt_templates(tmp_path):
    from vlm.prompts import HYBRID_PREFIX, STAGE_B_PROMPT, prompt_sha256

    archive = _synthetic_archive(tmp_path)
    weights = {"a": {"receipt": {"path": "x", "sha256": "1" * 64}, "hashes": ["abc  model.safetensors"]}}
    _wave(_members(1), _ctx("reader_baseline"), tmp_path / "w", archive, settings=None, weights=weights)
    launch = json.loads((tmp_path / "w" / "launch.json").read_text(encoding="utf-8"))
    assert launch["weights"] == weights
    assert launch["prompt"]["stage_b_template_sha256"] == prompt_sha256(STAGE_B_PROMPT)
    assert launch["prompt"]["hybrid_prefix_template_sha256"] == prompt_sha256(HYBRID_PREFIX)


# MAJOR-10 — closed
def test_stop_all_and_status_include_the_b9_server(tmp_path):
    from tools import vlm_vast

    settings = SimpleNamespace(provider="vast.ai", execution_class="remote_paid", vast_host="203.0.113.9",
                               vast_ssh_port=2222, vast_ssh_user="root", runtime_dir=str(tmp_path / "rt"),
                               worker_token=None, tunnel_local_port=18765, worker_port=8765)
    seen: list[str] = []

    def _runner(args, **kwargs):
        seen.append(" ".join(args))
        return SimpleNamespace(stdout="stopped\n", stderr="", returncode=0)

    out = vlm_vast.cmd_stop(settings, "all", runner=_runner)
    assert "b9" in out and any("b9.pid" in command for command in seen)
    assert vlm_vast.PORTS["b"] != vlm_vast.PORTS["b9"]


# MAJOR-9 — closed
def test_truth_firewall_covers_the_vlm_package():
    from tests import test_truth_firewall as firewall

    assert "vlm" in firewall.PRODUCTION_ROOTS and "vlm" in firewall.REQUIRED_ROOTS
