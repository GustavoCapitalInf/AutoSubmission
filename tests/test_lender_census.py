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
    # the owner's rulings (audit round 2, R2-B16: R56); 5.8: audit round 3 (R3-B25), the round-3 fix batches.
    assert result["classification_version"] == "5.8"
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
    """AFTER with Tarnmoor gained through its named alias. Audit round 3, R3-B01 (R3-22): Brambleway stays a paid lender
    (these tests are about gains; AFTER's loss of it is its own failing case,
    test_r3_22_the_fixtures_lost_lender_fails_on_its_own)."""
    after = json.loads(json.dumps(AFTER))
    after["accounts"]["s1:0"]["lenders"][0] = [0, "Tarnmoor Funding", "TARNMOOR FUNDING"]
    after["accounts"]["s1:0"]["states"][2] = "confirmed_lender"
    after["accounts"]["s1:0"]["lenders"].append([2, "Brambleway Capital", "BRAMBLEWAY CAPITAL"])
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


def test_r3_22_the_fixtures_lost_lender_fails_on_its_own(tmp_path, capsys):
    """Audit round 3, R3-B01 (R3-22): AFTER loses Brambleway Capital from s1 (its paid row leaves for no return): with
    every gain admitted, the loss alone fails G7 (it exited 0 before)."""
    after = json.loads(json.dumps(AFTER))
    after["accounts"]["s1:0"]["lenders"][0] = [0, "Tarnmoor Funding", "TARNMOOR FUNDING"]
    report = census.compare(BEFORE, after, admitted=frozenset({"Tarnmoor Funding", "Quillon Funding"}))
    assert report["lost"] == {"Brambleway Capital": {"analyses": 1, "rows_now": {"alternative_position": 1}}}
    assert (report["lost_outside_the_allowlist"], report["paid_rows_left_other_outside_the_allowlist"]) == (1, 1)
    paths = _files(tmp_path, BEFORE, after, _ledger(("Tarnmoor Funding", "confirmed_lender", "admitted")))
    assert census.main(_compare_argv(paths, tmp_path)) == 1
    printed = capsys.readouterr().out
    assert "lenders lost outside the allowlist: 1" in printed
    assert "paid rows that left for no return, outside the allowlist: 1" in printed


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


# Audit round 3, R3-B01 (R3-22; the underwriter's Q5 of 2026-10-02, "take the bounced amount out of "paid to lenders"
# but keep it in the withholding rate. Keep the funder in the lender count"; true revenue spec §14.3 G7): the exit code
# alone carries G7's verdict. A returned row's withholding move is declared only when the row joins; a returned row
# leaving withholding, a paid row leaving for no return, a lost lender and a lender-count loss fail unless the entity is
# allowlisted (the returned row never); lender_debits and the numerator fail where they move with no row move.
# Fabricated snapshots: "Quillon Funding" pays rows 1 and 2 of a four-row statement.

R3_22_FIGURES = ("returned_rows_leaving_withholding", "paid_rows_left_other_outside_the_allowlist",
                 "lost_outside_the_allowlist", "lender_count_lost_outside_the_allowlist", "lender_debits_unexplained",
                 "withholding_numerator_unexplained")


def _q5_account(*, lenders=(1, 2), withholding=(1, 2), returned=(), numerator=200.0, debits=200.0,
                counted=("Quillon Funding",), entity="Quillon Funding"):
    """One account snapshot: `entity`'s paid rows `lenders`, its withholding rows, its returned rows (each returned by
    transaction:4), the numerator, lender_debits and the lender count's entities."""
    states = ["other", "confirmed_lender", "confirmed_lender", "other"]
    return {**_account(states, [[index, entity, entity.upper()] for index in lenders], {}, 10.0),
            "lender_debits": debits, "withholding_rows": list(withholding), "withholding_numerator": numerator,
            "lender_count_entities": list(counted),
            "returned_funder_rows": [[index, "transaction:4"] for index in returned],
            "potential_lender_rows": [], "potential_withholding_rows": [], "reversed_by": [],
            "row_entities": {"1": entity, "2": entity}}


def _q5_snapshots(before: dict, after: dict) -> tuple[dict, dict]:
    return ({"classification_version": "5.7", "accounts": {"s1:0": before}},
            {"classification_version": "5.7", "accounts": {"s1:0": after}})


def _main_exit(tmp_path, before, after, *, allowlisted=(), admitted=()):
    paths = _files(tmp_path, before, after, _ledger(*[(name, "confirmed_lender", "admitted") for name in admitted]))
    argv = _compare_argv(paths, tmp_path)
    if allowlisted:
        allowlist = tmp_path / "allowlist.json"
        allowlist.write_text(json.dumps({"entities": list(allowlisted)}), encoding="utf-8")
        argv += ["--allowlist", str(allowlist)]
    return census.main(argv)


def test_r3_22_a_returned_row_leaving_withholding_fails(tmp_path, capsys):
    # Row 2 is returned in both snapshots; it leaves the withholding rows (numerator 200.00 -> 100.00): the reverse of
    # the owner's Q5. Never declared, never excused by the allowlist.
    before, after = _q5_snapshots(_q5_account(lenders=(1,), returned=(2,), debits=100.0),
                                  _q5_account(lenders=(1,), withholding=(1,), returned=(2,), numerator=100.0,
                                              debits=100.0))
    report = census.compare(before, after, admitted=frozenset())
    assert report["returned_rows_leaving_withholding"] == {"analyses": 1, "rows": 1}
    assert report["returned_funder_moves"] == {"analyses": 0, "rows": 0}
    assert report["row_flag_moves"]["withholding_rows"] == {"analyses": 1, "rows": 1}
    assert census.compare(before, after, admitted=frozenset(), allowlisted=frozenset({"Quillon Funding"}))[
        "returned_rows_leaving_withholding"] == {"analyses": 1, "rows": 1}
    assert _main_exit(tmp_path, before, after) == 1
    assert "returned rows leaving the withholding rows (the reverse of the owner's Q5): 1 analyses/1 rows" in (
        capsys.readouterr().out)
    assert _main_exit(tmp_path, before, after, allowlisted=("Quillon Funding",)) == 1


def test_r3_22_a_returned_row_joining_withholding_still_passes(tmp_path):
    # The R2-OW13 case (a returned row joins): declared, and the paid-row set changes, so the money checks do not apply.
    before, after = _returned_snapshots(returned_rows=[[1, "transaction:5"], [2, "transaction:4"]])
    report = census.compare(before, after, admitted=frozenset())
    assert report["returned_funder_moves"] == {"analyses": 1, "rows": 1}
    assert {name: report[name] for name in R3_22_FIGURES} == {
        "returned_rows_leaving_withholding": {"analyses": 0, "rows": 0},
        "paid_rows_left_other_outside_the_allowlist": 0, "lost_outside_the_allowlist": 0,
        "lender_count_lost_outside_the_allowlist": 0, "lender_debits_unexplained": {"analyses": 0},
        "withholding_numerator_unexplained": {"analyses": 0}}
    assert _main_exit(tmp_path, before, after) == 0


def test_r3_22_a_paid_row_leaving_for_no_return_fails_unless_allowlisted(tmp_path):
    # Row 1 leaves the lenders list (paid) and stays in the withholding rows; no row is returned.
    before, after = _q5_snapshots(_q5_account(), _q5_account(lenders=(2,), debits=100.0))
    report = census.compare(before, after, admitted=frozenset())
    assert report["paid_rows"] == {"left_returned": 0, "left_other": 1, "joined": 0}
    assert report["paid_rows_left_other_outside_the_allowlist"] == 1
    assert report["lender_debits_unexplained"] == {"analyses": 0}  # the paid-row set changed
    assert _main_exit(tmp_path, before, after) == 1
    allowed = census.compare(before, after, admitted=frozenset(), allowlisted=frozenset({"Quillon Funding"}))
    assert allowed["paid_rows_left_other_outside_the_allowlist"] == 0
    assert _main_exit(tmp_path, before, after, allowlisted=("Quillon Funding",)) == 0


def test_r3_22_a_lender_count_loss_fails_unless_allowlisted(tmp_path):
    # The funder's only paid row leaves the lenders list for no return, and the funder leaves the lender count.
    before, after = _q5_snapshots(_q5_account(lenders=(1,), withholding=(1,), numerator=100.0, debits=100.0),
                                  _q5_account(lenders=(), withholding=(1,), numerator=100.0, debits=0.0, counted=()))
    report = census.compare(before, after, admitted=frozenset())
    assert report["lender_count"]["lost"] == {"Quillon Funding": {"analyses": 1}}
    assert (report["lender_count_lost_outside_the_allowlist"], report["lost_outside_the_allowlist"]) == (1, 1)
    assert _main_exit(tmp_path, before, after) == 1
    allowed = census.compare(before, after, admitted=frozenset(), allowlisted=frozenset({"Quillon Funding"}))
    assert (allowed["lender_count_lost_outside_the_allowlist"], allowed["lost_outside_the_allowlist"]) == (0, 0)
    assert _main_exit(tmp_path, before, after, allowlisted=("Quillon Funding",)) == 0
    # Control (kept_in_count_returned): every paid row returned and the funder still counted: no loss.
    before, after = _q5_snapshots(_q5_account(lenders=(1,), withholding=(1,), numerator=100.0, debits=100.0),
                                  _q5_account(lenders=(), withholding=(1,), returned=(1,), numerator=100.0, debits=0.0))
    report = census.compare(before, after, admitted=frozenset())
    assert report["kept_in_count_returned"] == {"Quillon Funding": {"analyses": 1}}
    assert {name: report[name] for name in R3_22_FIGURES if not isinstance(report[name], dict)} == {
        "paid_rows_left_other_outside_the_allowlist": 0, "lost_outside_the_allowlist": 0,
        "lender_count_lost_outside_the_allowlist": 0}
    assert _main_exit(tmp_path, before, after) == 0


def test_r3_22_a_re_attribution_fails_unless_merged(tmp_path):
    # The rows stay paid, but entity A (Quillon) becomes B (Tarnmoor, an admitted lender): A is lost.
    before, after = _q5_snapshots(_q5_account(),
                                  _q5_account(entity="Tarnmoor Funding", counted=("Tarnmoor Funding",)))
    report = census.compare(before, after, admitted=frozenset({"Tarnmoor Funding"}))
    assert report["gained"]["Tarnmoor Funding"]["admitted"] is True
    assert (report["lost_outside_the_allowlist"], report["lender_count_lost_outside_the_allowlist"]) == (1, 1)
    assert report["paid_rows_left_other_outside_the_allowlist"] == 0  # no row left the lenders list
    assert _main_exit(tmp_path, before, after, admitted=("Tarnmoor Funding",)) == 1
    merged = census.compare(before, after, admitted=frozenset({"Tarnmoor Funding"}),
                            merged={"Quillon Funding": "Tarnmoor Funding"})
    assert (merged["gained"], merged["lost"]) == ({}, {})
    assert (merged["lost_outside_the_allowlist"], merged["lender_count_lost_outside_the_allowlist"]) == (0, 0)


def test_r3_22_lender_debits_moving_with_no_paid_row_move_fails(tmp_path, capsys):
    before, after = _q5_snapshots(_q5_account(debits=1700.0), _q5_account(debits=850.0))
    report = census.compare(before, after, admitted=frozenset())
    assert report["lender_debits_unexplained"] == {"analyses": 1}
    assert _main_exit(tmp_path, before, after) == 1
    assert "lender debits moved with no paid row move: 1 analyses" in capsys.readouterr().out
    # The same move with a paid row leaving is explained by the row (the paid-row check reads that row).
    before, after = _q5_snapshots(_q5_account(debits=1700.0), _q5_account(lenders=(2,), debits=850.0))
    assert census.compare(before, after, admitted=frozenset())["lender_debits_unexplained"] == {"analyses": 0}
    # A snapshot without lender_debits (or null) on one side is not read.
    before, after = _q5_snapshots(_q5_account(debits=1700.0), _q5_account(debits=850.0))
    del before["accounts"]["s1:0"]["lender_debits"]
    assert census.compare(before, after, admitted=frozenset())["lender_debits_unexplained"] == {"analyses": 0}
    before, after = _q5_snapshots({**_q5_account(debits=1700.0), "lender_debits": None}, _q5_account(debits=850.0))
    assert census.compare(before, after, admitted=frozenset())["lender_debits_unexplained"] == {"analyses": 0}


def test_r3_22_the_numerator_moving_with_no_withholding_row_move_fails(tmp_path, capsys):
    before, after = _q5_snapshots(_q5_account(numerator=2550.0), _q5_account(numerator=1700.0))
    report = census.compare(before, after, admitted=frozenset())
    assert report["withholding_numerator_unexplained"] == {"analyses": 1}
    assert report["withholding_numerator"] == {"down": 1}
    assert _main_exit(tmp_path, before, after) == 1
    assert "withholding numerator moved with no withholding row move: 1 analyses" in capsys.readouterr().out
    # The same move with a withholding row leaving is explained by the row (the row-flag check reads that row).
    before, after = _q5_snapshots(_q5_account(numerator=2550.0), _q5_account(withholding=(1,), numerator=1700.0))
    assert census.compare(before, after, admitted=frozenset())["withholding_numerator_unexplained"] == {"analyses": 0}


# ------------------------------------------------------------------------------------------------- Audit round 4, R4-02
# (the owner's answer of 2026-10-07 to R3-73, "Count it once"; true revenue spec §14.3 G7): a returned row the earlier
# snapshot counted once (listed in `represented_rows`, out of the withholding rows) that the later one puts back in the
# rate, or a row the later snapshot still lists as represented while it sits in the rate, is no Q5 join: it fails unless
# its entity is allowlisted. Fabricated snapshots: "Contoso Capital" pays rows 1 and 4 of a six-row statement; row 2,
# its payment of the 9th, is returned by the credit at row 3 (transaction:4) on the 10th; row 4 is the 16th's re-debit.

CONTOSO_CAPITAL, FABRIKAM_FUNDING, NORTHWIND_ADVANCE = "Contoso Capital", "Fabrikam Funding", "Northwind Advance"
R4_02_DATES = ["2054-03-02", "2054-03-02", "2054-03-09", "2054-03-10", "2054-03-16", "2054-03-18"]


def _rejoin_account(*, withholding, represented=False, lenders=(1, 4), returned=((2, "transaction:4"),)):
    states = ["other", "confirmed_lender", "confirmed_lender", "other", "confirmed_lender", "other"]
    return {**_account(states, [[index, CONTOSO_CAPITAL, CONTOSO_CAPITAL.upper()] for index in lenders], {}, 10.0),
            "lender_debits": 100.0 * len(lenders), "withholding_rows": list(withholding),
            "withholding_numerator": 100.0 * len(withholding), "lender_count_entities": [CONTOSO_CAPITAL],
            "returned_funder_rows": [list(row) for row in returned],
            "represented_rows": [[2, "transaction:5"]] if represented else [],
            "potential_lender_rows": [], "potential_withholding_rows": [], "reversed_by": [], "row_dates": R4_02_DATES,
            "row_entities": {"1": CONTOSO_CAPITAL, "2": CONTOSO_CAPITAL, "4": CONTOSO_CAPITAL}}


def test_r4_02_a_counted_once_row_rejoining_the_rate_fails_unless_allowlisted(tmp_path, capsys):
    # Case U: counted once before (represented by row 4, out of the rate); after, back in the rate, represented_rows
    # empty, row 4 still paid. Base: exit 0, booked as R2-OW13's join (returned_funder_moves 1).
    before, after = _q5_snapshots(_rejoin_account(withholding=(1, 4), represented=True),
                                  _rejoin_account(withholding=(1, 2, 4)))
    report = census.compare(before, after, admitted=frozenset({CONTOSO_CAPITAL}))
    assert report["represented_rows_rejoining_withholding"] == {"analyses": 1, "rows": 1}
    assert report["represented_rows_rejoining_outside_the_allowlist"] == 1
    assert report["returned_funder_moves"] == {"analyses": 0, "rows": 0}
    assert report["row_flag_moves_outside_the_allowlist"] == 0
    assert census.failed_on_lender_losses(report)
    assert _main_exit(tmp_path, before, after, admitted=(CONTOSO_CAPITAL,)) == 1
    assert ("returned rows rejoining the withholding rows after being counted once: 1 analyses/1 rows; outside the "
            "allowlist: 1") in capsys.readouterr().out
    # Case U2: the later snapshot still lists the row as represented AND as a withholding row.
    still = _q5_snapshots(_rejoin_account(withholding=(1, 4), represented=True),
                          _rejoin_account(withholding=(1, 2, 4), represented=True))
    assert census.compare(*still, admitted=frozenset())["represented_rows_rejoining_withholding"] == {
        "analyses": 1, "rows": 1}
    assert _main_exit(tmp_path, *still, admitted=(CONTOSO_CAPITAL,)) == 1
    # Allowlisted: exit 0, the figure still counted and printed.
    allowed = census.compare(before, after, admitted=frozenset(), allowlisted=frozenset({CONTOSO_CAPITAL}))
    assert allowed["represented_rows_rejoining_withholding"] == {"analyses": 1, "rows": 1}
    assert allowed["represented_rows_rejoining_outside_the_allowlist"] == 0
    assert _main_exit(tmp_path, before, after, allowlisted=(CONTOSO_CAPITAL,), admitted=(CONTOSO_CAPITAL,)) == 0
    assert ("returned rows rejoining the withholding rows after being counted once: 1 analyses/1 rows; outside the "
            "allowlist: 0") in capsys.readouterr().out
    assert _main_exit(tmp_path, *still, allowlisted=(CONTOSO_CAPITAL,), admitted=(CONTOSO_CAPITAL,)) == 0


def test_r4_02_control_a_q5_join_never_counted_once_stays_declared(tmp_path):
    # A returned row joining the rate that neither snapshot lists as represented: R2-OW13's join, declared.
    before, after = _q5_snapshots(_rejoin_account(withholding=(1, 4)), _rejoin_account(withholding=(1, 2, 4)))
    report = census.compare(before, after, admitted=frozenset())
    assert report["returned_funder_moves"] == {"analyses": 1, "rows": 1}
    assert report["represented_rows_rejoining_withholding"] == {"analyses": 0, "rows": 0}
    assert report["represented_rows_rejoining_outside_the_allowlist"] == 0
    assert _main_exit(tmp_path, before, after) == 0


def test_r4_02_control_the_zions_shaped_narrowing_passes_on_the_allowlist(tmp_path):
    # Before: row 2 counted once by row 4, a paid 2x. After (a deliberate narrowing of R3-73's rule, as round 3's Zions
    # re-join was): row 2 back in the rate, row 4 now a RETURNED row of the same funder (returned by transaction:6),
    # dated after the return, in the rate as Q5 keeps it. Only the orchestrator's allowlist admits it.
    before, after = _q5_snapshots(
        _rejoin_account(withholding=(1, 4), represented=True),
        _rejoin_account(withholding=(1, 2, 4), lenders=(1,), returned=((2, "transaction:4"), (4, "transaction:6"))))
    report = census.compare(before, after, admitted=frozenset())
    assert report["represented_rows_rejoining_withholding"] == {"analyses": 1, "rows": 1}
    assert report["returned_funder_moves"] == {"analyses": 0, "rows": 0}  # row 4 was already in the rate
    assert report["paid_rows"] == {"left_returned": 1, "left_other": 0, "joined": 0}
    assert _main_exit(tmp_path, before, after) == 1
    assert _main_exit(tmp_path, before, after, allowlisted=(CONTOSO_CAPITAL,)) == 0


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


def test_r3_22_a_declared_compare_skips_the_rule_d_accounts_money_checks(tmp_path):
    """Audit round 3, R3-B01 (R3-22): the declared-Zelle path sets the rule D rows apart, so their account's lender
    debits move while its paid-row set reads the same; R3-22's money checks skip such an account (its moves are
    zelle_reading_rule_d), and an account with no rule D row is still read."""
    no, yes = _z5_snapshots()
    assert no["accounts"]["z5:0"]["lender_debits"] != yes["accounts"]["z5:0"]["lender_debits"]
    report = census.compare(no, yes, admitted=frozenset(), declare_zelle_view=True)
    assert report["lender_debits_unexplained"] == {"analyses": 0}
    assert report["withholding_numerator_unexplained"] == {"analyses": 0}
    paths = _files(tmp_path, no, yes, _ledger())
    assert census.main([*_compare_argv(paths, tmp_path), "--declare-zelle-view"]) == 0
    # A second account with no rule D row whose lender debits move with no paid row move still fails.
    no["accounts"]["q:0"] = _q5_account(debits=1700.0)
    yes["accounts"]["q:0"] = _q5_account(debits=850.0)
    report = census.compare(no, yes, admitted=frozenset(), declare_zelle_view=True)
    assert report["lender_debits_unexplained"] == {"analyses": 1}
    paths = _files(tmp_path, no, yes, _ledger())
    assert census.main([*_compare_argv(paths, tmp_path), "--declare-zelle-view"]) == 1


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


#: Review round 1 of the fix run (finding 3): each snapshot records every row's date (`row_dates`, aligned with
#: `states`), so the redirect is declared only where the dates show F2(a)'s move.
REDIRECT_DATES = ["2054-03-01", "2054-03-02", "2054-03-05", "2054-03-06", "2054-03-13"]


def _dates(**changes):
    """REDIRECT_DATES with some rows' dates changed (`r<index>=<date or None>`)."""
    dates = list(REDIRECT_DATES)
    for name, value in changes.items():
        dates[int(name[1:])] = value
    return dates


def _redirect_snapshots(after_pairs, *, before_pairs=([3, "transaction:3"],), dates=REDIRECT_DATES):
    """A funder's three payments (rows 1, 3 and 4, dated the 2nd, 6th and 13th) and a return (row 2, transaction:3,
    the 5th). Before: the return restored `before_pairs` (row 3 by default, the payment after it). After: those rows
    paid again, and the return pairing `after_pairs` ([debit, credit]). `dates` is each snapshot's `row_dates` (None:
    a snapshot written before them)."""
    states = ["other", "confirmed_lender", "other", "confirmed_lender", "confirmed_lender"]
    lenders = [[index, "Quillon Funding", "QUILLON FUNDING"] for index in (1, 3, 4)]
    entities = {"1": "Quillon Funding", "3": "Quillon Funding", "4": "Quillon Funding"}
    base = {"potential_lender_rows": [], "potential_withholding_rows": [], "withholding_rows": [1, 3, 4],
            "withholding_numerator": 300.0, "lender_count_entities": ["Quillon Funding"], "row_entities": entities,
            **({"row_dates": list(dates)} if dates is not None else {})}
    before_pairs = [list(pair) for pair in before_pairs]
    before = {**_account(states, [entry for entry in lenders if entry[0] not in {pair[0] for pair in before_pairs}],
                         {}, 10.0), **base, "reversed_by": before_pairs, "returned_funder_rows": before_pairs}
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


# Review round 1 of the fix run (finding 3): G7 declares a redirect only where the snapshots' dates show F2(a)'s move: the
# dropped restore was of a payment dated AFTER its return, and any payment returned in its place is dated on or before
# it (printed order where a row prints no date, the classifier's own rule). Anything else, a snapshot without dates
# included, is read as G7 reads any pairing move.

def test_f2a_r1_dropping_the_restore_of_an_earlier_payment_still_fails(tmp_path):
    # The return (the 5th) restored row 1 (the 2nd, before it); the later snapshot pays row 1 again, unpaired.
    before, after = _redirect_snapshots([], before_pairs=([1, "transaction:3"],))
    report = census.compare(before, after, admitted=frozenset())
    assert report["returned_funder_redirects"] == {"analyses": 0, "rows": 0}
    assert report["row_flag_moves"]["reversed_by"] == {"analyses": 1, "rows": 1}
    assert report["row_flag_moves_outside_the_allowlist"] == 1
    paths = _files(tmp_path, before, after, _ledger())
    assert census.main(_compare_argv(paths, tmp_path)) == 1
    # The same move with the restored payment dated after the return is F2(a)'s, and declared.
    before, after = _redirect_snapshots([], before_pairs=([1, "transaction:3"],), dates=_dates(r1="2054-03-09"))
    assert census.compare(before, after, admitted=frozenset())["returned_funder_redirects"] == {"analyses": 1, "rows": 1}


def test_f2a_r1_a_replacement_dated_after_the_return_still_fails():
    # The return now restores row 4 (the 13th, after it) in place of row 3: no F2(a) pair, not declared.
    before, after = _redirect_snapshots([[4, "transaction:3"]])
    report = census.compare(before, after, admitted=frozenset())
    assert report["returned_funder_redirects"] == {"analyses": 0, "rows": 0}
    assert report["row_flag_moves_outside_the_allowlist"] == 2
    # A replacement on the return's own day is on or before it: declared.
    before, after = _redirect_snapshots([[1, "transaction:3"]], dates=_dates(r1="2054-03-05"))
    assert census.compare(before, after, admitted=frozenset())["returned_funder_redirects"] == {"analyses": 1, "rows": 2}


def test_f2a_r1_snapshots_without_dates_declare_nothing():
    # Snapshots written before `row_dates` cannot show the order: the move is read as any pairing move.
    before, after = _redirect_snapshots([], dates=None)
    report = census.compare(before, after, admitted=frozenset())
    assert report["returned_funder_redirects"] == {"analyses": 0, "rows": 0}
    assert report["row_flag_moves_outside_the_allowlist"] == 1
    # Dates on one side only (rows are compared position by position): an earlier snapshot written before the dates
    # is read with the later one's, so a compare from an older baseline still checks the order, and the reverse.
    for undated in ("before", "after"):
        before, after = _redirect_snapshots([])
        del {"before": before, "after": after}[undated]["accounts"]["s1:0"]["row_dates"]
        assert census.compare(before, after, admitted=frozenset())["returned_funder_redirects"] == {
            "analyses": 1, "rows": 1}
        before, after = _redirect_snapshots([], before_pairs=([1, "transaction:3"],))
        del {"before": before, "after": after}[undated]["accounts"]["s1:0"]["row_dates"]
        assert census.compare(before, after, admitted=frozenset())["returned_funder_redirects"] == {
            "analyses": 0, "rows": 0}
    # The later snapshot's dates are read first.
    before, after = _redirect_snapshots([], before_pairs=([1, "transaction:3"],))
    before["accounts"]["s1:0"]["row_dates"] = _dates(r1="2054-03-09")
    assert census.compare(before, after, admitted=frozenset())["returned_funder_redirects"] == {"analyses": 0, "rows": 0}


def test_f2a_r1_undated_rows_read_the_printed_order():
    # Neither the return nor the restored payment prints a date: row 3 is printed after the return (row 2), so its
    # dropped restore is F2(a)'s; a restore of row 1 (printed before it) is not.
    before, after = _redirect_snapshots([], dates=_dates(r2=None, r3=None))
    assert census.compare(before, after, admitted=frozenset())["returned_funder_redirects"] == {"analyses": 1, "rows": 1}
    before, after = _redirect_snapshots([], before_pairs=([1, "transaction:3"],), dates=_dates(r1=None, r2=None))
    assert census.compare(before, after, admitted=frozenset())["returned_funder_redirects"] == {"analyses": 0, "rows": 0}


def test_f2a_r1_a_snapshot_records_every_row_s_date(tmp_path, fake_payees):
    cache = ArtifactCache(data_dir=tmp_path / "data")
    cache.put_analysis("f" * 64, "settings", {"statement": {"bank": "Bank of America", "transactions": [
        _row("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 10000.0),
        _row("2054-01-05", "ACH DEBIT FABRICATED LENDER 0001", -1000.0),
        _row("2054-01-06", "ACH DEBIT FABRICATED LENDER 0001", -1000.0),
        _row("2054-01-07", "RETURN OF POSTED CHECK ITEM", 1000.0),
        _row("", "ACH DEBIT FABRIKAM SUPPLY 0001", -250.0),
    ]}})
    account = census.snapshot(census.cached_accounts(tmp_path / "data"))["accounts"]["f" * 64 + ":0"]
    assert account["returned_funder_rows"] == [[2, "transaction:4"]]
    # One date per row, aligned with `states`; None where the row prints none.
    assert account["row_dates"] == ["2054-01-02", "2054-01-05", "2054-01-06", "2054-01-07", None]
    assert len(account["row_dates"]) == len(account["states"]) == account["rows"]
