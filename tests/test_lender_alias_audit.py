"""tools/lender_alias_audit.py over a fabricated artifact cache (spec section 5)."""
from __future__ import annotations

import json

import pytest

from analysis.payee_matcher import AliasIndex
from tools import lender_alias_audit as audit_tool
from webapp.artifact_cache import ArtifactCache

PASSES = (
    audit_tool.AuditPass(AliasIndex({"premium_financing": {"Hollin Premium Finance": ("HOLLIN PFC",)}},
                                    run_together=False)),
    audit_tool.AuditPass(AliasIndex({
        "confirmed_lender": {"Quillon Funding": ("QUILLON FUNDING", "QUILLON")},
        "line_of_credit": {"Brambleway Capital": ("BRAMBLEWAY CAPITAL",)},
        "lease_or_rental": {"Westfen Leasing": ("WESTFEN LEASING",)},
    })),
    audit_tool.AuditPass(AliasIndex({"bank_name": {"Oxbow Bank": ("OXBOW",)}}, run_together=False),
                         audit_tool._LOAN_WORDING),
)
#: The same passes after the ledger dropped the bare alias QUILLON.
PASSES_WITHOUT_BARE_QUILLON = (
    PASSES[0],
    audit_tool.AuditPass(AliasIndex({
        "confirmed_lender": {"Quillon Funding": ("QUILLON FUNDING",)},
        "line_of_credit": {"Brambleway Capital": ("BRAMBLEWAY CAPITAL",)},
        "lease_or_rental": {"Westfen Leasing": ("WESTFEN LEASING",)},
    })),
    PASSES[2],
)
ALLOW_THE_REST = [{"key": "CORPORATE", "why": "channel words only"},
                  {"entity": "Oxbow Bank", "key": "OXBOW LOAN", "why": "the bank's own loan"}]
DENY_THE_BAKERY = [{"alias": "QUILLON", "entity": "Quillon Funding", "key": "QUILLON BAKERY",
                    "why": "a bakery, not the funder"}]


def _row(description, amount, classification="other", **extra):
    return {"original_description": description, "amount": amount, "classification": classification, **extra}


def _cache(tmp_path):
    cache = ArtifactCache(data_dir=tmp_path / "data")
    cache.put_analysis("a" * 64, "settings", {"classifications": [
        _row("ACH DEBIT QUILLON FUNDING DES PAYMENT", -100.0, "confirmed_lender"),
        _row("ORIG CO NAME QUILLON BAKERY ORIG ID 99", -12.0, "pos"),
        _row("QUILLON FUNDING DES TRANSFER FEE", -5.0, "fee"),
        _row("BRAMBLEWAY CAPITAL LOAN PROCEEDS", 900.0),
        _row("WESTFEN LEASING REFUND CREDIT", 40.0),
        _row("HOLLIN PFC PREMIUM", -80.0, "insurance"),
        _row("OXBOW LOAN PAYMENT", -60.0),
        _row("OXBOW MARKET GROCERIES", -9.0, "pos"),
        _row("MOBILE DEPOSIT", 40.0),
    ]})
    cache.put_analysis("b" * 64, "settings", {"accounts": [{"classifications": [
        _row("ACH DEBIT QUILLON FUNDING DES PAYMENT", -100.0, "confirmed_lender"),
        _row("CORPORATE ACH QUILLON FUNDING", -100.0, "confirmed_lender"),
        _row("ACH DEBIT QUILLON FUNDING DES PENDING", -100.0, "other", is_posted=False),
    ]}]})
    return tmp_path / "data"


def _report(tmp_path):
    return audit_tool.audit(audit_tool.cached_rows(_cache(tmp_path)), PASSES)


def test_payee_keys_skip_channel_words_and_stop_at_field_labels():
    assert audit_tool.payee_key("ACH DEBIT QUILLON FUNDING DES PAYMENT") == "QUILLON FUNDING"
    assert audit_tool.payee_key("ORIG CO NAME QUILLON BAKERY ORIG ID 99") == "QUILLON BAKERY"
    assert audit_tool.payee_key("CHECKCARD 0102 BRAMBLEWAY CAPITAL LOAN PROCEEDS") == "BRAMBLEWAY CAPITAL LOAN"


def test_the_audit_replays_the_rule_order_and_counts_only_taken_rows_as_taken(tmp_path):
    report = _report(tmp_path)
    assert report == {
        "bank_name": {"OXBOW": {"entity": "Oxbow Bank", "keys": {
            "OXBOW LOAN": {"rows": 1, "taken_rows": 1, "debit_rows": 1, "credit_rows": 0, "analyses": 1}}}},
        "confirmed_lender": {
            "QUILLON": {"entity": "Quillon Funding", "keys": {
                "QUILLON BAKERY": {"rows": 1, "taken_rows": 1, "debit_rows": 1, "credit_rows": 0, "analyses": 1}}},
            "QUILLON FUNDING": {"entity": "Quillon Funding", "keys": {
                "QUILLON FUNDING": {"rows": 4, "taken_rows": 2, "debit_rows": 4, "credit_rows": 0, "analyses": 2},
                "CORPORATE": {"rows": 1, "taken_rows": 1, "debit_rows": 1, "credit_rows": 0, "analyses": 1}}},
        },
        "lease_or_rental": {"WESTFEN LEASING": {"entity": "Westfen Leasing", "keys": {
            "WESTFEN LEASING REFUND": {"rows": 1, "taken_rows": 0, "debit_rows": 0, "credit_rows": 1,
                                       "analyses": 1}}}},
        "line_of_credit": {"BRAMBLEWAY CAPITAL": {"entity": "Brambleway Capital", "keys": {
            "BRAMBLEWAY CAPITAL LOAN": {"rows": 1, "taken_rows": 1, "debit_rows": 0, "credit_rows": 1,
                                        "analyses": 1}}}},
        "premium_financing": {"HOLLIN PFC": {"entity": "Hollin Premium Finance", "keys": {
            "HOLLIN PFC PREMIUM": {"rows": 1, "taken_rows": 1, "debit_rows": 1, "credit_rows": 0, "analyses": 1}}}},
    }


@pytest.mark.parametrize("alias,entity,key,expected", [
    ("QUILLON", "Quillon Funding", "QUILLON BAKERY", True),
    ("QUILLON", "Quillon Funding", "QUILLON FUNDING", True),
    ("QUILLON", "Quillon Funding", "QUILLON", False),
    ("QUILLON FUNDING", "Quillon Funding", "QUILLON FUNDING", False),
    ("QUILLON FUNDING", "Quillon Funding", "QUILLONFUNDING", False),
    ("QUILLON FUNDING", "Quillon Funding", "QUILLON FUNDING LLC", False),
    ("QUILLON FUNDING", "Quillon Funding", "QUILLON FUNDING BAKERY", True),
    ("QUILLON FUNDING", "Quillon Funding", "JOURNEY QUILLON FUNDING", True),
    ("QUILLON FUNDING", "Quillon Funding", "CORPORATE", True),
    ("QUILLON FUNDING", "Quillon Funding", "CORP", True),
    ("HOLLIN PFC", "Hollin Premium Finance", "HOLLIN PFC PREMIUM", False),
    ("BRAMBLEWAY CAPITAL", "Brambleway Capital", "BRAMBLEWAY CAPITAL LOAN", False),
])
def test_a_taken_match_needs_review_when_its_key_may_name_someone_else(alias, entity, key, expected):
    assert audit_tool.needs_review(alias, entity, key) is expected


def test_review_separates_denied_matches_from_undecided_matches_that_need_review(tmp_path):
    denied, undecided = audit_tool.review(_report(tmp_path), {"deny": DENY_THE_BAKERY,
                                                             "allow": [{"key": "CORPORATE"}]})
    assert [(row["alias"], row["key"], row["taken_rows"]) for row in denied] == [("QUILLON", "QUILLON BAKERY", 1)]
    assert [(row["alias"], row["key"], row["needs_review"]) for row in undecided] == [("OXBOW", "OXBOW LOAN", True)]


def _run(tmp_path, monkeypatch, decisions, *extra, passes=PASSES):
    monkeypatch.setattr(audit_tool, "default_passes", lambda: passes)
    review_file = tmp_path / "local" / "review.json"
    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text(json.dumps(decisions), encoding="utf-8")
    out = tmp_path / "local" / "audit.json"
    code = audit_tool.main(["--data-dir", str(_cache(tmp_path)), "--review", str(review_file),
                            "--out", str(out), *extra])
    return code, out


def test_a_denied_collision_that_still_takes_a_row_fails_the_audit(tmp_path, monkeypatch, capsys):
    code, out = _run(tmp_path, monkeypatch, {"deny": DENY_THE_BAKERY, "allow": []})
    assert code == 1
    printed = capsys.readouterr().out
    assert ("taken matches: 6, of which need review: 3; denied matches: 1; undecided: 2" in printed)
    assert "COLLISION 'QUILLON' (Quillon Funding, confirmed_lender) matches payee key 'QUILLON BAKERY'" in printed
    text = out.read_text(encoding="utf-8")
    assert "DES PAYMENT" not in text and "ORIG ID" not in text and "MOBILE DEPOSIT" not in text


def test_a_denied_pair_whose_rows_an_earlier_rule_keeps_does_not_fail(tmp_path, monkeypatch):
    decisions = {"deny": [{"alias": "WESTFEN LEASING", "key": "WESTFEN LEASING REFUND"}], "allow": []}
    assert _run(tmp_path, monkeypatch, decisions)[0] == 0


def test_strict_fails_until_every_match_that_needs_review_has_a_decision(tmp_path, monkeypatch):
    assert _run(tmp_path, monkeypatch, {"deny": [], "allow": []})[0] == 0
    assert _run(tmp_path, monkeypatch, {"deny": [], "allow": []}, "--strict")[0] == 1
    # QUILLON -> QUILLON BAKERY still needs a decision.
    assert _run(tmp_path, monkeypatch, {"deny": [], "allow": ALLOW_THE_REST}, "--strict")[0] == 1
    # Decided as a collision, but the alias still takes the bakery's row.
    assert _run(tmp_path, monkeypatch, {"deny": DENY_THE_BAKERY, "allow": ALLOW_THE_REST}, "--strict")[0] == 1
    # The ledger dropped the bare alias: zero denied and zero undecided.
    code, out = _run(tmp_path, monkeypatch, {"deny": DENY_THE_BAKERY, "allow": ALLOW_THE_REST}, "--strict",
                     passes=PASSES_WITHOUT_BARE_QUILLON)
    assert code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["denied"] == [] and report["undecided"] == []


def test_lost_matches_are_the_rows_an_entity_no_longer_takes_outside_denied_pairs():
    rows = [
        audit_tool.CachedRow("a" * 64, "ORIG CO NAME QUILLON BAKERY ORIG ID 99", -12.0, "pos"),
        audit_tool.CachedRow("a" * 64, "ACH DEBIT QUILLON LLC PAYMENT", -50.0, "other"),
        audit_tool.CachedRow("b" * 64, "ACH DEBIT QUILLON FUNDING DES PAYMENT", -100.0, "confirmed_lender"),
    ]
    before = audit_tool.audit(rows, PASSES)
    after = audit_tool.audit(rows, PASSES_WITHOUT_BARE_QUILLON)
    decisions = {"deny": DENY_THE_BAKERY, "allow": [{"entity": "Quillon Funding", "key": "QUILLON LLC"}]}
    assert audit_tool.lost_matches(before, after, decisions) == [
        {"entity": "Quillon Funding", "key": "QUILLON LLC", "before": 1, "after": 0}
    ]
    assert audit_tool.lost_matches(before, before, decisions) == []
    intended = {"deny": [*DENY_THE_BAKERY, {"entity": "Quillon Funding", "key": "QUILLON LLC"}], "allow": []}
    assert audit_tool.lost_matches(before, after, intended) == []


def test_a_ledger_change_that_takes_rows_from_an_entity_without_a_decision_fails(tmp_path, monkeypatch, capsys):
    decisions = {"deny": DENY_THE_BAKERY, "allow": ALLOW_THE_REST}
    _code, first = _run(tmp_path, monkeypatch, decisions, "--strict")
    previous = tmp_path / "local" / "previous.json"
    previous.write_text(first.read_text(encoding="utf-8"), encoding="utf-8")
    capsys.readouterr()
    code, out = _run(tmp_path, monkeypatch, decisions, "--strict", "--before", str(previous),
                     passes=PASSES_WITHOUT_BARE_QUILLON)
    assert code == 0 and json.loads(out.read_text(encoding="utf-8"))["lost"] == []
    assert "lost matches: 0" in capsys.readouterr().out
    allowed = {"deny": [], "allow": [*ALLOW_THE_REST, {"entity": "Quillon Funding", "key": "QUILLON BAKERY"}]}
    code, out = _run(tmp_path, monkeypatch, allowed, "--strict", "--before", str(previous),
                     passes=PASSES_WITHOUT_BARE_QUILLON)
    assert code == 1
    assert "LOST 'Quillon Funding' payee key 'QUILLON BAKERY': 1 taken rows before, 0 now" in capsys.readouterr().out
    assert json.loads(out.read_text(encoding="utf-8"))["lost"] == [
        {"entity": "Quillon Funding", "key": "QUILLON BAKERY", "before": 1, "after": 0}
    ]


def test_the_audit_refuses_a_report_inside_the_repository_and_a_directory_without_a_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_tool, "default_passes", lambda: PASSES)
    review_file = tmp_path / "review.json"
    review_file.write_text('{"deny": [], "allow": []}', encoding="utf-8")
    inside = audit_tool.ROOT / "alias-audit-must-not-exist.json"
    assert audit_tool.main(["--data-dir", str(_cache(tmp_path)), "--review", str(review_file),
                            "--out", str(inside)]) == 2
    assert not inside.exists()
    assert audit_tool.main(["--data-dir", str(_cache(tmp_path)), "--review", str(review_file),
                            "--out", str(tmp_path / "out.json"), "--before", str(inside)]) == 2
    assert not (tmp_path / "out.json").exists()
    assert audit_tool.main(["--data-dir", str(tmp_path / "empty"), "--review", str(review_file),
                            "--out", str(tmp_path / "out.json")]) == 2


def test_only_the_descriptor_rule_passes_need_loan_or_card_wording():
    passes = audit_tool.default_passes()
    assert [audit_pass.needs is not None for audit_pass in passes] == [False, False, True, True, False]
    assert passes[2].needs.search("OXBOW LOAN PAYMENT") and not passes[2].needs.search("OXBOW MARKET")
    assert passes[3].needs.search("OXBOW CARD PMT") and not passes[3].needs.search("OXBOW MARKET")
    # S2's own step-8 wording and order: an earlier descriptor rule decides the row before the bank-name
    # or the card-payment rule reads it, and the card rule reads S2's whole card-payment wording.
    assert passes[2].needs.search("OXBOW LOANS 0001")
    for decided_first in ("OXBOW LOC LOAN PAYMENT", "OXBOW LINE OF CREDIT LOAN", "OXBOW MORTGAGE LOAN",
                          "OXBOW AUTO LOAN PAYMENT", "OXBOW VEHICLE LOAN", "OXBOW LOANED"):
        assert not passes[2].needs.search(decided_first), decided_first
    for card_wording in ("KESTREL CRCARD 0001", "KESTREL AUTO PAY 0001", "KESTREL CREDIT CARD 0001",
                         "KESTREL EPAYMENT 0001", "KESTREL PROPERTY RENTAL PAYMENT"):
        assert passes[3].needs.search(card_wording), card_wording
    for decided_first in ("KESTREL LOC PAYMENT", "KESTREL LEASE PAYMENT", "KESTREL AUTO LEASE PMT",
                          "KESTREL RENTAL PMT", "KESTREL AUTO SHOP"):
        assert not passes[3].needs.search(decided_first), decided_first
