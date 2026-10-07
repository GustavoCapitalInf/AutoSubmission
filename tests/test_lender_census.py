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
    # Re-pinned from 5.0 by the D6 clarification (2026-09-26), then from 5.1 by the second one (2026-09-27), then
    # from 5.2 by the 5.3 release (2026-09-27), then from 5.3 by the Idea Financial ruling (5.4, 2026-09-28).
    # 5.5: the true-revenue bug fixes (2026-09-28); 5.6: its revenue tiers; 5.7: the audit's fix batches, round 2 and
    # the owner's rulings (audit round 2, R2-B16: R56).
    assert result["classification_version"] == "5.7"
    first =result["accounts"]["a" * 64 + ":0"]
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


def test_a_snapshot_records_each_row_s_potential_lender_withholding_and_reversal_flags(tmp_path, fake_payees):
    # Final review I6: G7 reads the potential-lender and withholding flags and reversed_by of every row, so a move of
    # a debit's contributions (a reversal pair zeroing them) is measured, not only its state.
    cache = ArtifactCache(data_dir=tmp_path / "data")
    cache.put_analysis("c" * 64, "settings", {"statement": {"transactions": [
        _row("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 10000.0),
        _row("2054-01-05", "ACH DEBIT FABRICATED LENDER 0001", -1000.0),
        _row("2054-01-08", "ACH CREDIT CARD PAYMENT FABRICATED", -250.0),
        _row("2054-01-09", "RETURNED ACH CREDIT CARD PAYMENT FABRICATED", 250.0),
    ]}})
    account = census.snapshot(census.cached_accounts(tmp_path / "data"))["accounts"]["c" * 64 + ":0"]
    assert account["withholding_rows"] == [1]
    assert account["potential_lender_rows"] == []
    assert account["potential_withholding_rows"] == []
    assert account["reversed_by"] == [[2, "transaction:4"]]


def test_compare_counts_the_row_flag_moves_and_reads_an_older_snapshot_as_not_comparable():
    flags = {"potential_lender_rows": [[1, "Unidentified lender obligation"]], "withholding_rows": [0],
             "potential_withholding_rows": [1], "reversed_by": []}
    before = {"accounts": {"s1:0": {**_account(["other", "potential_lender"], [], {}, 5.0), **flags},
                           "s2:0": _account(["other"], [], {}, None)}}
    moved = {**flags, "potential_lender_rows": [], "potential_withholding_rows": [], "reversed_by": [[1, "transaction:3"]]}
    after = {"accounts": {"s1:0": {**_account(["other", "potential_lender"], [], {}, 5.0), **moved},
                          "s2:0": {**_account(["other"], [], {}, None), **flags}}}
    report = census.compare(before, after, admitted=frozenset())
    assert report["row_flag_moves"] == {
        "potential_lender_rows": {"analyses": 1, "rows": 1},
        "potential_withholding_rows": {"analyses": 1, "rows": 1},
        "reversed_by": {"analyses": 1, "rows": 1},
        "withholding_rows": {"analyses": 0, "rows": 0},
        "not_comparable": 1,
    }


def _flag_move_snapshots():
    """Two snapshots whose one debit loses its potential-lender and potential-withholding flags (a reversal pair)."""
    flags = {"potential_lender_rows": [[1, "Tarnmoor Funding"]], "withholding_rows": [],
             "potential_withholding_rows": [1], "reversed_by": [], "row_entities": {"1": "Tarnmoor Funding"}}
    before = {"accounts": {"s1:0": {**_account(["other", "potential_lender"], [], {}, 5.0), **flags}}}
    moved = {**flags, "potential_lender_rows": [], "potential_withholding_rows": [], "reversed_by": [[1, "transaction:3"]]}
    after = {"accounts": {"s1:0": {**_account(["other", "potential_lender"], [], {}, 5.0), **moved}}}
    return before, after


def test_compare_fails_on_a_row_flag_move_outside_the_allowlist(tmp_path, capsys):
    # Re-review N5: G7's row-flag check is the tool's own: a potential-lender, withholding or reversed_by move fails
    # the compare unless the row's payee entity is on the owner's signed-off allowlist.
    before, after = _flag_move_snapshots()
    report = census.compare(before, after, admitted=frozenset())
    assert report["row_flag_moves_outside_the_allowlist"] == 3
    paths = _files(tmp_path, before, after, _ledger())
    assert census.main(_compare_argv(paths, tmp_path)) == 1
    assert "row flag moves outside the allowlist: 3" in capsys.readouterr().out
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(json.dumps({"entities": ["Tarnmoor Funding"]}), encoding="utf-8")
    assert census.compare(before, after, admitted=frozenset(),
                          allowlisted=frozenset({"Tarnmoor Funding"}))["row_flag_moves_outside_the_allowlist"] == 0
    assert census.main(_compare_argv(paths, tmp_path) + ["--allowlist", str(allowlist)]) == 0


def test_a_snapshot_records_the_payee_entity_of_each_flagged_row(tmp_path, fake_payees):
    cache = ArtifactCache(data_dir=tmp_path / "data")
    cache.put_analysis("d" * 64, "settings", {"statement": {"transactions": [
        _row("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 10000.0),
        _row("2054-01-05", "ACH DEBIT FABRICATED LENDER 0001", -1000.0),
    ]}})
    account = census.snapshot(census.cached_accounts(tmp_path / "data"))["accounts"]["d" * 64 + ":0"]
    assert account["row_entities"] == {"1": "Fabricated Lender"}


def test_a_snapshot_run_writes_the_file_it_names(tmp_path, fake_payees):
    out = tmp_path / "local" / "after.json"
    assert census.main(["snapshot", "--data-dir", str(_cache(tmp_path)), "--out", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert sorted(written["accounts"]) == ["a" * 64 + ":0", "b" * 64 + ":0"]
    # A snapshot of the cache alone records no re-parse.
    assert "basis_stats" not in written


def test_r2_b01_a_re_parsed_snapshot_reads_a_routed_input_from_its_re_parse(tmp_path, monkeypatch, fake_payees):
    # Audit round 2, R2-B01 (R12): `snapshot --reparse` re-parses every latest input a cached OCR reading reaches, with
    # the checkout's deterministic analysis stage (the revenue census's re-parse), and reads every other from the cache.
    from tests.test_revenue_census import _FabricatedCache, _statement
    from tools import revenue_census

    deposit = (5, "CUSTOMER DEPOSIT FABRICATED", 10000.0)
    cache = _FabricatedCache(tmp_path / "data")
    routed = cache.ocr("A" * 64, ["FABRICATED PAGE A"], "2054-01-01T00:00:00")
    cache.analysis(routed, [_statement("XXXX1234", [deposit])], "2054-01-03T00:00:00")
    cache.analysis("e" * 64, [_statement("XXXX5678", [deposit])], "2054-01-03T00:00:00")
    cache.connection.close()

    def reparse(document):
        assert document["pages"] == ["FABRICATED PAGE A"]
        return {"accounts": [{"statement": _statement("XXXX1234", [deposit, (9, "ACH DEBIT FABRICATED LENDER 0001",
                                                                            -1000.0)])}]}

    monkeypatch.setattr(revenue_census, "_reparse_document", reparse)
    out = tmp_path / "reparsed.json"
    assert census.main(["snapshot", "--data-dir", str(cache.root), "--reparse", "--workers", "1",
                        "--out", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert (written["accounts"][f"{routed}:0"]["rows"], written["accounts"]["e" * 64 + ":0"]["rows"]) == (2, 1)
    assert written["accounts"][f"{routed}:0"]["lenders"] == [[1, "Fabricated Lender", "FABRICATED LENDER"]]
    stats = written["basis_stats"]["reparse"]
    assert {name: stats[name] for name in ("inputs", "reached", "reparsed", "failed", "cached")} == {
        "inputs": 2, "reached": 1, "reparsed": 1, "failed": 0, "cached": 1}


# Owner ruling 2026-10-02 (the underwriter's Q5; true revenue spec §14.3 G7; audit round 2, R2-OW13): a confirmed
# funder's payment returned unpaid leaves the lenders list (paid) and stays in the withholding rows and the lender
# count. The snapshot records the withholding numerator, the lender count's entities and the returned rows; compare
# declares the withholding move of a returned row (returned_funder_moves) and a funder kept in the count whose every
# paid row was returned (kept_in_count_returned), and still fails any other withholding or reversed_by move.

def test_a_snapshot_records_the_withholding_numerator_the_counted_entities_and_the_returned_rows(tmp_path, fake_payees):
    cache = ArtifactCache(data_dir=tmp_path / "data")
    cache.put_analysis("f" * 64, "settings", {"statement": {"bank": "Bank of America", "transactions": [
        _row("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 10000.0),
        _row("2054-01-05", "ACH DEBIT FABRICATED LENDER 0001", -1000.0),
        _row("2054-01-06", "ACH DEBIT FABRICATED LENDER 0001", -1000.0),
        _row("2054-01-07", "RETURN OF POSTED CHECK ITEM", 1000.0),
    ]}})
    account = census.snapshot(census.cached_accounts(tmp_path / "data"))["accounts"]["f" * 64 + ":0"]
    assert account["lenders"] == [[1, "Fabricated Lender", "FABRICATED LENDER"]]
    assert account["withholding_rows"] == [1, 2]
    assert account["returned_funder_rows"] == [[2, "transaction:4"]]
    assert account["lender_count_entities"] == ["Fabricated Lender"]
    assert (account["lender_debits"], account["withholding_numerator"]) == (1000.0, 2000.0)


def test_a_snapshot_reads_the_legacy_basis_whatever_the_default(tmp_path, monkeypatch, fake_payees):
    """Owner ruling 2026-10-02 (the underwriter's Q7), R2-OW14: True revenue is the analysis's default withholding basis,
    so account_snapshot passes the legacy basis explicitly and G7 compares one basis across trees: a changed default
    leaves the snapshot identical."""
    import analysis.metrics as metrics_module

    cache = ArtifactCache(data_dir=tmp_path / "data")
    cache.put_analysis("e" * 64, "settings", {"statement": {"bank": "Bank of America", "transactions": [
        _row("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 10000.0),
        _row("2054-01-03", "INTERNAL TRANSFER FROM SAVINGS", 5000.0),
        _row("2054-01-05", "ACH DEBIT FABRICATED LENDER 0001", -1000.0),
    ]}})
    real = metrics_module.compute_metrics
    modes = []

    def snapshot_with_default(default):
        def compute(*args, **kwargs):
            modes.append(kwargs.get("withholding_denominator_mode"))
            kwargs.setdefault("withholding_denominator_mode", default)
            return real(*args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(metrics_module, "compute_metrics", compute)
            return census.snapshot(census.cached_accounts(tmp_path / "data"))["accounts"]["e" * 64 + ":0"]

    snapshots = [snapshot_with_default(default) for default in
                 ("true_revenue", "verified_revenue", "legacy_eligible_deposits")]
    assert modes == ["legacy_eligible_deposits"] * 3
    assert snapshots[0] == snapshots[1] == snapshots[2]
    assert snapshots[0]["eligible_deposits"] == 15000.0
    assert snapshots[0]["withholding_rate"] == pytest.approx(1000.0 / 15000.0 * 100)


def _returned_snapshots(*, returned_rows):
    """A funder's only paid row (index 1) leaves the lenders list and a named pair's row (index 2) rejoins the
    withholding rows; `returned_rows` lists the after snapshot's returned funder rows."""
    flags = {"potential_lender_rows": [], "potential_withholding_rows": [], "reversed_by": [[2, "transaction:4"]],
             "row_entities": {"1": "Quillon Funding", "2": "Quillon Funding"}}
    base = _account(["other", "confirmed_lender", "confirmed_lender", "other"],
                    [[1, "Quillon Funding", "QUILLON FUNDING"]], {}, 10.0)
    before = {"accounts": {"s1:0": {**base, **flags, "withholding_rows": [1], "withholding_numerator": 100.0,
                                    "lender_count_entities": ["Quillon Funding"], "returned_funder_rows": []}}}
    after_account = {**base, **flags, "lenders": [], "withholding_rows": [1, 2], "withholding_numerator": 200.0,
                     "lender_count_entities": ["Quillon Funding"], "returned_funder_rows": returned_rows}
    return before, {"accounts": {"s1:0": after_account}}


def test_compare_declares_a_returned_row_s_withholding_move_and_a_funder_kept_in_the_count():
    before, after = _returned_snapshots(returned_rows=[[1, "transaction:5"], [2, "transaction:4"]])
    report = census.compare(before, after, admitted=frozenset())
    assert report["returned_funder_moves"] == {"analyses": 1, "rows": 1}
    assert report["row_flag_moves"]["withholding_rows"] == {"analyses": 1, "rows": 1}
    assert report["row_flag_moves_outside_the_allowlist"] == 0
    assert report["kept_in_count_returned"] == {"Quillon Funding": {"analyses": 1}}
    assert report["lost"] == {}
    assert report["paid_rows"] == {"left_returned": 1, "left_other": 0, "joined": 0}
    assert report["lender_count"] == {"gained": {}, "lost": {}, "not_comparable": 0}
    assert report["withholding_numerator"] == {"up": 1}


def test_compare_still_fails_a_withholding_or_reversed_by_move_that_is_not_a_returned_row(tmp_path, capsys):
    # The same moves with no returned row: the withholding move is outside the allowlist and the funder is lost.
    before, after = _returned_snapshots(returned_rows=[])
    report = census.compare(before, after, admitted=frozenset())
    assert report["returned_funder_moves"] == {"analyses": 0, "rows": 0}
    assert report["row_flag_moves_outside_the_allowlist"] == 1
    assert report["kept_in_count_returned"] == {}
    assert report["lost"] == {"Quillon Funding": {"analyses": 1, "rows_now": {"confirmed_lender": 1}}}
    assert report["paid_rows"] == {"left_returned": 0, "left_other": 1, "joined": 0}
    # A reversed_by move on a returned row is never declared.
    moved = json.loads(json.dumps(after))
    moved["accounts"]["s1:0"]["returned_funder_rows"] = [[1, "transaction:5"], [2, "transaction:4"]]
    moved["accounts"]["s1:0"]["reversed_by"] = [[2, "transaction:4"], [1, "transaction:5"]]
    assert census.compare(before, moved, admitted=frozenset())["row_flag_moves_outside_the_allowlist"] == 1
    paths = _files(tmp_path, before, after, _ledger())
    assert census.main(_compare_argv(paths, tmp_path)) == 1
    out = capsys.readouterr().out
    assert "returned funder moves (withholding rows kept for a returned funder payment): 0 analyses/0 rows" in out


def test_compare_reports_the_lender_count_s_moves_and_reads_an_older_snapshot_as_not_comparable():
    before, after = _returned_snapshots(returned_rows=[[1, "transaction:5"], [2, "transaction:4"]])
    gained = json.loads(json.dumps(after))
    gained["accounts"]["s1:0"]["lender_count_entities"] = ["Brambleway Capital", "Quillon Funding"]
    report = census.compare(before, gained, admitted=frozenset())
    assert report["lender_count"]["gained"] == {"Brambleway Capital": {"analyses": 1}}
    older = json.loads(json.dumps(before))
    for key in ("withholding_numerator", "lender_count_entities", "returned_funder_rows"):
        older["accounts"]["s1:0"].pop(key)
    report = census.compare(older, after, admitted=frozenset())
    assert report["lender_count"]["not_comparable"] == 1
    assert report["withholding_numerator"] == {"not_comparable": 1}
    # The after snapshot's returned rows still declare the move.
    assert report["returned_funder_moves"] == {"analyses": 1, "rows": 1}


# ---------------------------------------------------------------- The owner's amendment of 2026-10-06 to the
# underwriter's Q3 (R2-OW17, J3; true revenue spec §14.3 G7): the snapshot reads one Zelle reading (Yes by default); a
# compare of the two readings is refused unless declared, and then only rule D's move on a Zelle return credit
# (tests/zelle_setting_fixtures.py Z5: a funder debit and a bounce-worded Zelle credit the rules count) is declared.


def _z5_snapshots():
    from tests import zelle_setting_fixtures as fx

    rows, holder, _title = fx.CASES["Z5"]
    account = {"statement": fx.statement(rows, holder=holder).model_dump(mode="json")}
    no = census.account_snapshot(account, zelle_true_revenue=False)
    yes = census.account_snapshot(account, zelle_true_revenue=True)
    return ({"classification_version": "5.6", "zelle_true_revenue": False, "accounts": {"z5:0": no}},
            {"classification_version": "5.6", "zelle_true_revenue": True, "accounts": {"z5:0": yes}})


def test_ow17_the_snapshot_records_the_reading_and_the_zelle_policy_rows():
    no, yes = _z5_snapshots()
    old, new = no["accounts"]["z5:0"], yes["accounts"]["z5:0"]
    assert (old["zelle_policy_rows"], new["zelle_policy_rows"]) == ([1], [1])
    # Between the readings the funder debit's lender_totals row and its returned_funder_rows entry move.
    assert old["returned_funder_rows"] == [[0, "transaction:2"]] and new["returned_funder_rows"] == []
    assert [row[0] for row in old["lenders"]] == [] and [row[0] for row in new["lenders"]] == [0]
    # Nothing else moves: the withholding rows, the numerator, the lender count and the legacy basis.
    for key in ("withholding_rows", "withholding_numerator", "lender_count_entities", "eligible_deposits",
                "withholding_rate", "potential_lender_rows", "reversed_by"):
        assert old[key] == new[key], key


def test_ow17_a_compare_of_two_readings_is_refused_unless_declared(tmp_path, capsys):
    no, yes = _z5_snapshots()
    with pytest.raises(census.ZelleViewMismatch):
        census.compare(no, yes, admitted=frozenset())
    paths = _files(tmp_path, no, yes, _ledger())
    assert census.main(_compare_argv(paths, tmp_path)) == 2
    assert "refused" in capsys.readouterr().err


def test_ow17_a_declared_compare_classes_rule_d_and_nothing_else_moves(tmp_path):
    no, yes = _z5_snapshots()
    report = census.compare(no, yes, admitted=frozenset(), declare_zelle_view=True)
    assert report["zelle_reading_rule_d"] == {"analyses": 1, "rows": 2}
    assert (report["gained"], report["lost"]) == ({}, {})
    assert census.zelle_reading_undeclared(report) == 0
    paths = _files(tmp_path, no, yes, _ledger())
    assert census.main([*_compare_argv(paths, tmp_path), "--declare-zelle-view"]) == 0


def test_ow17_a_planted_non_zelle_lender_move_still_fails(tmp_path):
    no, yes = _z5_snapshots()
    yes["accounts"]["z5:0"]["withholding_rows"] = []
    report = census.compare(no, yes, admitted=frozenset(), declare_zelle_view=True)
    assert census.zelle_reading_undeclared(report) > 0
    paths = _files(tmp_path, no, yes, _ledger())
    assert census.main([*_compare_argv(paths, tmp_path), "--declare-zelle-view"]) == 1


# --- The owner's request of 2026-10-06 (lender payment changes; R2-OW18, J; true revenue spec §14.3 G7): ONE new
# snapshot key, the statement's payment changes, and a compare block that is a new output only: it never fails G7 and
# never enters any existing figure. Fabricated rows ('FABRICATED LENDER' through the fake_payees fixture, 2054).


def _weekly_cut_account():
    rows = [_row("2054-03-02", "CUSTOMER DEPOSIT FABRICATED", 20000.0)]
    for day in (2, 9, 16, 23):
        rows.append(_row(f"2054-03-{day:02d}", "ACH DEBIT FABRICATED LENDER 0001", -1000.0))
    for day in (30,):
        rows.append(_row(f"2054-03-{day:02d}", "ACH DEBIT FABRICATED LENDER 0001", -700.0))
    for day in (6, 13, 20):
        rows.append(_row(f"2054-04-{day:02d}", "ACH DEBIT FABRICATED LENDER 0001", -700.0))
    return {"statement": {"period_start": "2054-03-01", "period_end": "2054-04-24", "transactions": rows}}


def test_ow18_the_snapshot_carries_the_payment_changes(fake_payees):
    snap = census.account_snapshot(_weekly_cut_account())
    assert snap["lender_payment_changes"] == [["decrease", "Fabricated Lender", "confirmed", 1, "weekly", "weekly", -30,
                                               None]]
    assert list(snap)[-1] == "lender_payment_changes"


def test_ow18_a_code_root_without_the_module_gives_no_key_and_the_same_snapshot(fake_payees, monkeypatch):
    import sys

    import analysis
    from analysis import lender_payment_changes

    with_key = census.account_snapshot(_weekly_cut_account())
    with monkeypatch.context() as patch:
        patch.delattr(lender_payment_changes, "statement_payment_changes")
        without_function = census.account_snapshot(_weekly_cut_account())
    with monkeypatch.context() as patch:
        patch.delattr(analysis, "lender_payment_changes")
        patch.setitem(sys.modules, "analysis.lender_payment_changes", None)
        without_module = census.account_snapshot(_weekly_cut_account())
    assert "lender_payment_changes" not in without_function and without_function == without_module
    snap = {"classification_version": "5.6", "zelle_true_revenue": True, "accounts": {"x:0": with_key}}
    base = {"classification_version": "5.6", "zelle_true_revenue": True, "accounts": {"x:0": without_module}}
    assert json.dumps(census.without_payment_changes(snap)) == json.dumps(base)


def test_ow18_compare_reports_the_block_and_never_fails_on_it(tmp_path, capsys, fake_payees):
    snap = census.account_snapshot(_weekly_cut_account())
    base = {key: value for key, value in snap.items() if key != "lender_payment_changes"}
    before = {"classification_version": "5.6", "zelle_true_revenue": True, "accounts": {"x:0": base}}
    after = {"classification_version": "5.6", "zelle_true_revenue": True, "accounts": {"x:0": snap}}
    report = census.compare(before, after, admitted=frozenset())
    assert report["lender_payment_changes"] == {"after": {"decrease|confirmed": 1}, "base": None, "not_comparable": 1,
                                                "gained": {"accounts": 0, "items": 0},
                                                "lost": {"accounts": 0, "items": 0}}
    # Every existing output at its zero value (J3 a).
    assert (report["gained"], report["lost"], report["gained_through_generic_words"]) == ({}, {}, [])
    assert report["row_flag_moves_outside_the_allowlist"] == 0
    assert report["paid_rows"] == {"left_returned": 0, "left_other": 0, "joined": 0}
    paths = _files(tmp_path, before, after, _ledger())
    assert census.main(_compare_argv(paths, tmp_path)) == 0
    assert "lender payment changes (new outputs, information only): after decrease|confirmed 1" in capsys.readouterr().out
    # Both sides carrying the key: the items gained and lost, still never a failure.
    moved = json.loads(json.dumps(after))
    moved["accounts"]["x:0"]["lender_payment_changes"] = [["stop", "Fabricated Lender", "confirmed", 1, "weekly", None,
                                                            None, False]]
    report = census.compare(after, moved, admitted=frozenset())
    assert report["lender_payment_changes"]["gained"] == {"accounts": 1, "items": 1}
    assert report["lender_payment_changes"]["lost"] == {"accounts": 1, "items": 1}
    paths = _files(tmp_path, after, moved, _ledger())
    assert census.main(_compare_argv(paths, tmp_path)) == 0
    # Neither side carrying it: no block.
    assert "lender_payment_changes" not in census.compare(before, before, admitted=frozenset())


def test_ow18_a_planted_lender_move_still_fails(tmp_path, fake_payees):
    snap = census.account_snapshot(_weekly_cut_account())
    before = {"classification_version": "5.6", "zelle_true_revenue": True, "accounts": {"x:0": snap}}
    after = json.loads(json.dumps(before))
    after["accounts"]["x:0"]["withholding_rows"] = []
    paths = _files(tmp_path, before, after, _ledger())
    assert census.main(_compare_argv(paths, tmp_path)) == 1


# The final review of round 2, F2(a) (true revenue spec §6.2 pass 4, §14.3 G7): a confirmed funder's paid payment pairs
# on the lender side only with a return dated on or after it. G7 declares the moves of a return whose pairing moved
# (`returned_funder_redirects`): a debit an earlier snapshot paired with a credit (reversed_by or a returned funder row)
# that the later one lists as paid again, unpaired, its credit pairing nothing or another payment of the same funder.


def _redirect_snapshots(after_pairs):
    """A funder's three payments (rows 1, 3 and 4) and a return (row 2, transaction:3). Before: the return restored
    row 3 (the payment after it). After: row 3 paid again, and the return pairing `after_pairs` ([debit, credit])."""
    states = ["other", "confirmed_lender", "other", "confirmed_lender", "confirmed_lender"]
    lenders = [[index, "Quillon Funding", "QUILLON FUNDING"] for index in (1, 3, 4)]
    entities = {"1": "Quillon Funding", "3": "Quillon Funding", "4": "Quillon Funding"}
    base = {"potential_lender_rows": [], "potential_withholding_rows": [], "withholding_rows": [1, 3, 4],
            "withholding_numerator": 300.0, "lender_count_entities": ["Quillon Funding"], "row_entities": entities}
    before = {**_account(states, [entry for entry in lenders if entry[0] != 3], {}, 10.0), **base,
              "reversed_by": [[3, "transaction:3"]], "returned_funder_rows": [[3, "transaction:3"]]}
    after = {**_account(states, [entry for entry in lenders if entry[0] not in {pair[0] for pair in after_pairs}], {},
                        10.0), **base, "reversed_by": after_pairs, "returned_funder_rows": after_pairs}
    return {"accounts": {"s1:0": before}}, {"accounts": {"s1:0": after}}


def test_f2a_compare_declares_a_return_no_longer_paired_with_a_later_payment(tmp_path):
    before, after = _redirect_snapshots([])
    report = census.compare(before, after, admitted=frozenset())
    assert report["row_flag_moves"]["reversed_by"] == {"analyses": 1, "rows": 1}
    assert report["row_flag_moves_outside_the_allowlist"] == 0
    assert report["returned_funder_redirects"] == {"analyses": 1, "rows": 1}
    assert report["paid_rows"] == {"left_returned": 0, "left_other": 0, "joined": 1}
    paths = _files(tmp_path, before, after, _ledger())
    assert census.main(_compare_argv(paths, tmp_path)) == 0
    # Redirected to the payment before it (row 1): both rows' moves are declared.
    before, after = _redirect_snapshots([[1, "transaction:3"]])
    report = census.compare(before, after, admitted=frozenset())
    assert report["row_flag_moves"]["reversed_by"] == {"analyses": 1, "rows": 2}
    assert report["row_flag_moves_outside_the_allowlist"] == 0
    assert report["returned_funder_redirects"] == {"analyses": 1, "rows": 2}
    assert report["paid_rows"] == {"left_returned": 1, "left_other": 0, "joined": 1}


def test_f2a_compare_declares_a_5_4_pair_the_fix_refuses():
    # Classification 5.4's pair zeroed the later payment (no withholding, no returned row); the fix leaves it paid.
    before, after = _redirect_snapshots([])
    old = before["accounts"]["s1:0"]
    old["withholding_rows"], old["returned_funder_rows"] = [1, 4], []
    del old["lender_count_entities"], old["withholding_numerator"]
    report = census.compare(before, after, admitted=frozenset())
    assert report["row_flag_moves"]["withholding_rows"] == {"analyses": 1, "rows": 1}
    assert report["row_flag_moves"]["reversed_by"] == {"analyses": 1, "rows": 1}
    assert report["row_flag_moves_outside_the_allowlist"] == 0
    assert report["returned_funder_redirects"] == {"analyses": 1, "rows": 2}


def test_f2a_compare_still_fails_any_other_pairing_move():
    # The return now pairs with ANOTHER funder's payment: not declared.
    before, after = _redirect_snapshots([[1, "transaction:3"]])
    after["accounts"]["s1:0"]["row_entities"] = {**after["accounts"]["s1:0"]["row_entities"], "1": "Brambleway Capital"}
    after["accounts"]["s1:0"]["lenders"] = [[4, "Quillon Funding", "QUILLON FUNDING"], [3, "Quillon Funding",
                                                                                          "QUILLON FUNDING"]]
    report = census.compare(before, after, admitted=frozenset())
    assert report["returned_funder_redirects"] == {"analyses": 0, "rows": 0}
    assert report["row_flag_moves_outside_the_allowlist"] == 2
    # The earlier payment still returned after (a pairing moved, not dropped): not declared either.
    before, after = _redirect_snapshots([[3, "transaction:3"]])
    after["accounts"]["s1:0"]["reversed_by"] = [[3, "transaction:3"], [1, "transaction:5"]]
    report = census.compare(before, after, admitted=frozenset())
    assert report["returned_funder_redirects"] == {"analyses": 0, "rows": 0}
    assert report["row_flag_moves_outside_the_allowlist"] == 1
