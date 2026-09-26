"""tools/lender_census.py over a fabricated artifact cache, fabricated snapshots and a fabricated C10 ledger (spec section 9)."""
from __future__ import annotations

import json

import pytest

from tests.flag_group_fixtures import fake_payees  # noqa: F401  (fixture)
from tools import lender_census as census
from webapp.artifact_cache import ArtifactCache


def _row(day: str, description: str, amount: float) -> dict:
    return {"date": day, "description": description, "amount": amount,
            "direction": "credit" if amount >= 0 else "debit", "running_balance": None}


def _cache(tmp_path):
    cache = ArtifactCache(data_dir=tmp_path / "data")
    cache.put_analysis("a" * 64, "settings", {"statement": {"transactions": [
        _row("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 10000.0),
        _row("2054-01-05", "ACH DEBIT FABRICATED LENDER 0001", -1000.0),
        _row("2054-01-06", "ACH DEBIT FABRICATED ALT 0001", -700.0),
    ]}})
    cache.put_analysis("b" * 64, "settings", {"document": {}, "accounts": [
        {"statement": {"transactions": [_row("2054-01-05", "MORTGAGE PMT FABRICATED HOME", -1200.0)]}},
        {"statement": {"transactions": [
            {"date": "2054-01-06", "description": "FABRICATED ROW", "amount": "not a number", "direction": "debit"},
        ]}},
    ]})
    return tmp_path / "data"


def test_a_snapshot_records_states_lenders_flags_and_withholding_per_account(tmp_path, fake_payees):
    result = census.snapshot(census.cached_accounts(_cache(tmp_path)))
    assert result["classification_version"] == "5.0"
    first = result["accounts"]["a" * 64 + ":0"]
    assert first["states"] == ["other", "confirmed_lender", "alternative_position"]
    assert first["lenders"] == [[1, "Fabricated Lender", "FABRICATED LENDER"]]
    # [debits, debited, credits, credited] per group (C5).
    assert first["flagged"] == {"alternative_positions": [1, 700.0, 0, 0.0]}
    assert first["withholding_rate"] == pytest.approx(10.0)
    assert result["accounts"]["b" * 64 + ":0"]["flagged"] == {"mortgages": [1, 1200.0, 0, 0.0]}
    assert "b" * 64 + ":1" not in result["accounts"]
    assert result["skipped"] == {"ValidationError": 1}


def _account(states, lenders, flagged, rate):
    return {"rows": len(states), "states": states, "lenders": lenders, "flagged": flagged,
            "lender_debits": 0.0, "eligible_deposits": 1000.0, "withholding_rate": rate}


BEFORE = {"classification_version": "4.1", "accounts": {
    "s1:0": _account(["other", "confirmed_lender", "confirmed_lender"],
                     [[1, "Quillon Funding", "QUILLON FUNDING"], [2, "Brambleway Capital", "BRAMBLEWAY CAPITAL"]],
                     {}, 30.0),
    "s2:0": _account(["confirmed_lender"], [[0, "Quillon Funding", "QUILLON FUNDING"]], {}, 12.0),
}}
AFTER = {"classification_version": "5.0", "accounts": {
    "s1:0": _account(["confirmed_lender", "confirmed_lender", "alternative_position"],
                     [[0, "Tarnmoor Funding", "FUNDING"], [1, "Quillon Funding", "QUILLON FUNDING"]],
                     {"alternative_positions": [1, 100.0]}, 25.0),
    "s2:0": _account(["confirmed_lender"], [[0, "Quillon Funding", "QUILLON FUNDING"]], {}, 12.0),
}}


def _ledger(*entries: tuple[str, str, str]) -> dict:
    """A fabricated C10 ledger, one (entity, group, status) per entry: the three fields the census reads."""
    return {"schema": 1, "entities": [
        {"entity": entity, "group": group, "status": status} for entity, group, status in entries
    ]}


def test_admitted_lenders_are_the_admitted_confirmed_lender_entities():
    ledger = _ledger(
        ("Quillon Funding", "confirmed_lender", "admitted"),
        ("Tarnmoor Funding", "confirmed_lender", "review"),
        ("Brambleway Capital", "alternative_position", "admitted"),
        ("Fenwold Advance", "confirmed_lender", "rejected"),
    )
    assert census.admitted_lenders(ledger) == frozenset({"Quillon Funding"})


@pytest.mark.parametrize("ledger", ["| Quillon Funding | lender |", {"schema": 2, "entities": []}, {"schema": 1}])
def test_admitted_lenders_refuse_anything_but_a_schema_1_ledger(ledger):
    with pytest.raises(ValueError):
        census.admitted_lenders(ledger)


def test_compare_reports_gains_losses_generic_words_flags_and_withholding():
    report = census.compare(BEFORE, AFTER, admitted=frozenset({"Quillon Funding"}))
    assert report["accounts_compared"] == 2
    assert report["gained"] == {
        "Tarnmoor Funding": {"analyses": 1, "rows": 1, "aliases": {"FUNDING": 1}, "admitted": False},
    }
    assert report["lost"] == {"Brambleway Capital": {"analyses": 1, "rows_now": {"alternative_position": 1}}}
    assert report["gained_through_generic_words"] == [{"entity": "Tarnmoor Funding", "alias": "FUNDING", "rows": 1}]
    # AFTER's flagged entry is a snapshot written before the credited fields: [count, total] only.
    assert report["flagged"] == {"alternative_positions": {"analyses": 1, "rows": 1, "rows_credited": 0}}
    assert report["eligible_deposits"] == {"unchanged": 2}
    assert report["withholding"] == {"down": 1, "unchanged": 1}
    assert report["largest_withholding_moves"]["down"] == ["s1:0"]


def test_a_snapshot_records_a_factoring_payees_credits(tmp_path, fake_payees):
    """Owner ruling 2026-09-26: a factor's payout is revenue and carries the Factoring flag."""
    cache = ArtifactCache(data_dir=tmp_path / "data")
    cache.put_analysis("c" * 64, "settings", {"statement": {"transactions": [
        _row("2054-01-05", "FABRICATED FACTOR INVOICE PAYMENT 0001", 4000.0),
        _row("2054-01-12", "ACH DEBIT FABRICATED FACTOR 0001", -200.0),
    ]}})
    [account] = census.snapshot(census.cached_accounts(tmp_path / "data"))["accounts"].values()
    assert account["flagged"] == {"factoring": [1, 200.0, 1, 4000.0]}
    assert account["eligible_deposits"] == 4000.0


def test_compare_counts_credited_rows_and_eligible_deposit_moves(tmp_path, capsys):
    before = {"classification_version": "5.0", "accounts": {
        "s1:0": _account(["factoring", "factoring"], [], {"factoring": [1, 200.0, 0, 0.0]}, 10.0),
    }}
    after = json.loads(json.dumps(before))
    after["accounts"]["s1:0"]["flagged"] = {"factoring": [1, 200.0, 1, 4000.0]}
    after["accounts"]["s1:0"]["eligible_deposits"] = 5000.0
    after["accounts"]["s1:0"]["withholding_rate"] = 2.0
    report = census.compare(before, after, admitted=frozenset())
    assert report["flagged"] == {"factoring": {"analyses": 1, "rows": 1, "rows_credited": 1}}
    assert report["eligible_deposits"] == {"up": 1}
    assert report["withholding"] == {"down": 1}
    paths = _files(tmp_path, before, after, _ledger())
    assert census.main(_compare_argv(paths, tmp_path)) == 0
    printed = capsys.readouterr().out
    assert "flagged groups: factoring 1 analyses/1 rows/1 credits" in printed
    assert "eligible deposits: up 1" in printed


def test_compare_reads_a_merged_entity_as_the_entity_that_absorbed_it():
    """Owner decision 2026-09-25 (MERGED_REGISTRY_ENTITIES): a merge is one lender, not a loss and a gain."""
    before = {"classification_version": "4.1", "accounts": {
        "s1:0": _account(["confirmed_lender"], [[0, "Quillon Holdings", "QUILLON HOLDINGS"]], {}, 12.0),
    }}
    after = {"classification_version": "5.0", "accounts": {
        "s1:0": _account(["confirmed_lender"], [[0, "Quillon Funding", "QUILLON HOLDINGS"]], {}, 12.0),
    }}
    merged = census.compare(before, after, admitted=frozenset({"Quillon Funding"}),
                            merged={"Quillon Holdings": "Quillon Funding"})
    assert (merged["gained"], merged["lost"]) == ({}, {})
    plain = census.compare(before, after, admitted=frozenset({"Quillon Funding"}))
    assert (set(plain["gained"]), set(plain["lost"])) == ({"Quillon Funding"}, {"Quillon Holdings"})


def _files(tmp_path, before, after, ledger):
    paths = {}
    for name, content in (("before", before), ("after", after), ("ledger", ledger)):
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(content), encoding="utf-8")
    return paths


def _compare_argv(paths, tmp_path):
    return ["compare", "--before", str(paths["before"]), "--after", str(paths["after"]),
            "--ledger", str(paths["ledger"]), "--out", str(tmp_path / "report.json")]


def _gain_through_a_named_alias():
    after = json.loads(json.dumps(AFTER))
    after["accounts"]["s1:0"]["lenders"][0] = [0, "Tarnmoor Funding", "TARNMOOR FUNDING"]
    return after


def test_the_census_calls_generic_every_word_the_ledger_validator_calls_generic():
    """Spec section 9 acceptance 5 and C10's generic-word rule share one definition: every word S1's validator
    refuses as a bare generic alias is generic to the census too."""
    from tools.lender_ledger import GENERIC_WORDS as LEDGER_GENERIC_WORDS

    assert LEDGER_GENERIC_WORDS <= census.GENERIC_WORDS
    assert {"BANK", "HOLDINGS", "LENDER", "MERCHANT", "SOLUTIONS", "SERVICING", "FUNDER"} <= census.GENERIC_WORDS


def test_compare_fails_on_a_gain_through_a_generic_word_even_when_admitted(tmp_path, capsys):
    ledger = _ledger(("Quillon Funding", "confirmed_lender", "admitted"),
                     ("Tarnmoor Funding", "confirmed_lender", "admitted"))
    paths = _files(tmp_path, BEFORE, AFTER, ledger)
    assert census.main(_compare_argv(paths, tmp_path)) == 1
    printed = capsys.readouterr().out
    assert "! Tarnmoor Funding via 'FUNDING': 1 rows" in printed
    assert "- Brambleway Capital: 1 analyses; rows now: alternative_position 1" in printed
    assert "NOT AN ADMITTED LENDER" not in printed


def test_compare_passes_when_every_gain_is_an_admitted_ledger_lender(tmp_path):
    paths = _files(tmp_path, BEFORE, _gain_through_a_named_alias(),
                   _ledger(("Tarnmoor Funding", "confirmed_lender", "admitted")))
    assert census.main(_compare_argv(paths, tmp_path)) == 0


@pytest.mark.parametrize(
    ("group", "status"),
    [("confirmed_lender", "review"), ("confirmed_lender", "owner_ruling"), ("alternative_position", "admitted")],
)
def test_compare_fails_on_a_gain_the_ledger_does_not_admit_as_a_lender(tmp_path, capsys, group, status):
    paths = _files(tmp_path, BEFORE, _gain_through_a_named_alias(), _ledger(("Tarnmoor Funding", group, status)))
    assert census.main(_compare_argv(paths, tmp_path)) == 1
    assert "+ Tarnmoor Funding: 1 analyses, 1 rows  NOT AN ADMITTED LENDER IN THE LEDGER" in capsys.readouterr().out


def test_compare_refuses_a_ledger_that_is_missing_or_not_the_c10_json(tmp_path):
    paths = _files(tmp_path, BEFORE, AFTER, {"schema": 2, "entities": []})
    assert census.main(_compare_argv(paths, tmp_path)) == 2
    paths["ledger"].write_text("| Quillon Funding | lender |", encoding="utf-8")
    assert census.main(_compare_argv(paths, tmp_path)) == 2
    paths["ledger"].unlink()
    assert census.main(_compare_argv(paths, tmp_path)) == 2
    assert not (tmp_path / "report.json").exists()


def test_the_census_refuses_output_inside_the_repository_and_a_directory_without_a_cache(tmp_path):
    inside = census.ROOT / "lender-census-must-not-exist.json"
    assert census.main(["snapshot", "--data-dir", str(_cache(tmp_path)), "--out", str(inside)]) == 2
    assert not inside.exists()
    assert census.main(["snapshot", "--data-dir", str(tmp_path / "empty"), "--out", str(tmp_path / "s.json")]) == 2


def test_a_snapshot_run_writes_the_file_it_names(tmp_path, fake_payees):
    out = tmp_path / "local" / "after.json"
    assert census.main(["snapshot", "--data-dir", str(_cache(tmp_path)), "--out", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert sorted(written["accounts"]) == ["a" * 64 + ":0", "b" * 64 + ":0"]
