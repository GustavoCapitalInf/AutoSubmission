"""Flag groups as Settings shows them (lender detection §8.2, plan contract C6). Fabricated payloads only."""
import copy

import pytest

from analysis.flag_groups import FLAG_GROUPS, FLAG_SETTING_KEYS
from analysis.flagged_view import apply_flagged_groups_to_payload, enabled_group_keys
from tests.flagged_payloads import (
    FLAGGED_DEBIT,
    GROUP_KEYS,
    PREMIUM_FINANCING_STATE,
    flagged_account_payload,
    flagged_document_payload,
    flagged_row,
    row_state,
    with_flagged_rows,
)
from tests.l1s3_payloads import account_payload

ALL_TICKED: dict = {}
NONE_TICKED = {key: False for key in FLAG_SETTING_KEYS}
EACH_GROUP = pytest.mark.parametrize("group", FLAG_GROUPS, ids=lambda group: group.key)


def _flagged_rows(account):
    return [row for row in account["statement"]["transactions"] if row["classification"].get("flagged_group")]


def test_the_view_reads_the_eleven_contract_groups():
    assert tuple(group.key for group in FLAG_GROUPS) == (
        "alternative_positions", "lines_of_credit", "credit_cards", "vehicle_financing",
        "bank_loans", "mortgages", "leases_rentals", "personal_loans",
        "floor_plan", "factoring", "premium_financing",
    )
    assert FLAG_SETTING_KEYS == tuple(f"flag_{group.key}" for group in FLAG_GROUPS)
    # Premium financing is the one group with no state of its own: its rows stay insurance (C1, C4).
    assert [group.key for group in FLAG_GROUPS if group.state is None] == ["premium_financing"]


def test_every_group_is_shown_when_nothing_is_unticked():
    shown = apply_flagged_groups_to_payload(flagged_account_payload(), enabled=ALL_TICKED)
    assert list(shown["metrics"]["flagged_groups"]) == list(GROUP_KEYS)
    assert [entry["group"] for entry in shown["detection"]["flagged_positions"]] == list(GROUP_KEYS)
    assert all(row["classification"]["flag_shown"] is True for row in _flagged_rows(shown))
    # The fixture's revenue credit names no flag group, so it carries no flag.
    assert shown["statement"]["transactions"][0]["classification"]["flag_shown"] is False
    assert enabled_group_keys(ALL_TICKED) == frozenset(GROUP_KEYS)


@EACH_GROUP
def test_unticking_a_group_hides_that_group_only(group):
    shown = apply_flagged_groups_to_payload(flagged_account_payload(), enabled={group.setting: False})
    others = [key for key in GROUP_KEYS if key != group.key]
    assert list(shown["metrics"]["flagged_groups"]) == others
    assert [entry["group"] for entry in shown["detection"]["flagged_positions"]] == others
    flags = {row["classification"]["flagged_group"]: row["classification"]["flag_shown"]
             for row in _flagged_rows(shown)}
    assert flags == {key: key != group.key for key in GROUP_KEYS}
    # Hidden, never re-classified: the record keeps its state, its group and its contribution (D7).
    hidden = next(row for row in _flagged_rows(shown) if row["classification"]["flagged_group"] == group.key)
    assert hidden["classification"]["classification"] == row_state(group.key)
    assert hidden["classification"]["contributes_to_flagged_totals"] is True


def test_unticking_premium_financing_hides_the_flag_and_keeps_the_insurance_record():
    # Premium financing has no state of its own: the row stays insurance and keeps its insurance totals (C4).
    payload = flagged_account_payload(groups=("premium_financing",))
    shown = apply_flagged_groups_to_payload(payload, enabled={"flag_premium_financing": False})
    record = shown["statement"]["transactions"][-1]["classification"]
    assert (record["classification"], record["contributes_to_insurance_totals"]) == (PREMIUM_FINANCING_STATE, True)
    assert (record["flagged_group"], record["flag_shown"]) == ("premium_financing", False)
    assert shown["metrics"]["flagged_groups"] == {} and shown["detection"]["flagged_positions"] == []


@EACH_GROUP
def test_a_group_ticked_explicitly_is_shown(group):
    shown = apply_flagged_groups_to_payload(flagged_account_payload(groups=(group.key,)), enabled={group.setting: True})
    assert list(shown["metrics"]["flagged_groups"]) == [group.key]
    assert _flagged_rows(shown)[0]["classification"]["flag_shown"] is True


def test_a_row_that_does_not_count_still_shows_its_group_tag():
    # A proven duplicate keeps its state and its group but contributes nothing; the tag follows the group (C6).
    payload = with_flagged_rows(account_payload(), [flagged_row("mortgages", contributes=False)])
    shown = apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED)
    assert shown["statement"]["transactions"][-1]["classification"]["flag_shown"] is True
    assert shown["metrics"]["flagged_groups"] == {}
    assert shown["detection"]["flagged_positions"] == []


@pytest.mark.parametrize("bad", ["fabricated_group", ["mortgages"], 7, None], ids=["unknown", "list", "int", "none"])
def test_a_group_the_contract_does_not_define_is_never_shown(bad):
    payload = flagged_account_payload(groups=("mortgages",))
    payload["statement"]["transactions"][-1]["classification"]["flagged_group"] = bad
    payload["metrics"]["flagged_groups"]["fabricated_group"] = {"count": 1, "total": FLAGGED_DEBIT, "payees": 1}
    payload["detection"]["flagged_positions"].append({"group": bad, "payee": "FABRICATED PAYEE"})
    payload["detection"]["flagged_positions"].append("not an entry")
    shown = apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED)
    assert shown["statement"]["transactions"][-1]["classification"]["flag_shown"] is False
    assert list(shown["metrics"]["flagged_groups"]) == ["mortgages"]
    assert [entry["group"] for entry in shown["detection"]["flagged_positions"]] == ["mortgages"]


@pytest.mark.parametrize("build", [flagged_account_payload, flagged_document_payload])
def test_the_stored_payload_is_never_mutated_and_nothing_changed_is_shared(build):
    payload = build()
    stored = copy.deepcopy(payload)
    shown = apply_flagged_groups_to_payload(payload, enabled=NONE_TICKED)
    assert payload == stored
    for served, original in zip(shown.get("accounts") or [shown], payload.get("accounts") or [payload]):
        assert served["detection"]["flagged_positions"] == []
        assert served["statement"]["transactions"] is not original["statement"]["transactions"]
        for served_row, original_row in zip(served["statement"]["transactions"], original["statement"]["transactions"]):
            assert served_row["classification"] is not original_row["classification"]
        assert served["metrics"] is not original["metrics"]
        assert served["detection"] is not original["detection"]
        assert served["detection"]["known_funders"] is not original["detection"]["known_funders"]


@EACH_GROUP
def test_every_account_of_a_document_follows_the_checkbox(group):
    shown = apply_flagged_groups_to_payload(flagged_document_payload(), enabled={group.setting: False})
    assert len(shown["accounts"]) == 2
    for account in shown["accounts"]:
        assert list(account["metrics"]["flagged_groups"]) == [key for key in GROUP_KEYS if key != group.key]
        assert all(entry["group"] != group.key for entry in account["detection"]["flagged_positions"])
        assert [row["classification"]["flag_shown"] for row in _flagged_rows(account)] == [
            key != group.key for key in GROUP_KEYS
        ]
    assert shown["document"] == flagged_document_payload()["document"]


def test_a_payload_without_the_new_fields_keeps_every_stored_value():
    legacy = account_payload()  # classified before flag groups existed: no flagged_group, no flag summaries
    shown = apply_flagged_groups_to_payload(legacy, enabled=NONE_TICKED)
    assert shown["metrics"] == legacy["metrics"]
    assert shown["detection"] == legacy["detection"]
    row = legacy["statement"]["transactions"][0]["classification"]
    assert shown["statement"]["transactions"][0]["classification"] == {**row, "flag_shown": False}


@pytest.mark.parametrize("payload", [None, [], "text", {}, {"accounts": "not a list"}, {"accounts": []},
                                     {"statement": {}, "accounts": []}])
def test_anything_that_is_not_a_published_shape_is_returned_unchanged(payload):
    # `{}` matters beyond tidiness: the package reads a member whose analysis is empty as carrying no currency,
    # and a key added here would make it one that declares none (webapp/app.py::_package_analysis).
    assert apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED) is payload


# --- analysed with older lender rules (spec §8.2, D12) ------------------------------------------------------------

@pytest.fixture
def running_5_1(monkeypatch):
    """The running classifier is 5.1, whatever it is later: the tables below read against it."""
    from analysis import transaction_classifier

    monkeypatch.setattr(transaction_classifier, "CLASSIFICATION_VERSION", "5.1")


def _outdated_with_one_record(version) -> bool:
    # Every other record carries the running version, so the one record under test decides. A null version is no
    # version.
    from analysis import transaction_classifier

    payload = with_flagged_rows(flagged_account_payload(groups=()), [flagged_row(None)])
    rows = payload["statement"]["transactions"]
    for row in rows:
        row["classification"]["classification_version"] = transaction_classifier.CLASSIFICATION_VERSION
    rows[-1]["classification"]["classification_version"] = version
    return apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED)["analysis_rules_outdated"]


@pytest.mark.parametrize("version, outdated", [
    ("4.1", True), ("3.0", True), ("4", True), (4, True), (None, True),
    ("5.0", True), ("5", True), (5, True),
    ("5.1", False), (" 5.1 ", False), ("5.2", False), ("5.10", False), ("6.0", False), (6, False),
    ("unknown", False), (True, False),
])
def test_rows_classified_by_older_rules_mark_the_analysis_outdated(running_5_1, version, outdated):
    # Any version older than the running one is outdated, a 5.0 record under 5.1 among them; the running version and
    # a newer one are not. Versions compare as numbers: "5.10" is newer than "5.1".
    assert _outdated_with_one_record(version) is outdated


def test_the_running_version_is_read_at_each_call_and_compared_as_numbers(monkeypatch):
    from analysis import transaction_classifier

    monkeypatch.setattr(transaction_classifier, "CLASSIFICATION_VERSION", "5.10")
    assert [_outdated_with_one_record(version) for version in ("5.9", "5.10", "5.11", "6.0")] == [
        True, False, False, False]
    monkeypatch.setattr(transaction_classifier, "CLASSIFICATION_VERSION", "5.9")
    assert [_outdated_with_one_record(version) for version in ("5.9", "5.10")] == [False, False]


def test_a_5_0_analysis_is_outdated_under_the_running_rules_and_a_current_one_is_not():
    # The D6 clarification made the running rules 5.1: an analysis stored by the 5.0 rules gets the notice and the
    # Re-analyze button, and one the running classifier wrote does not.
    from analysis.transaction_classifier import CLASSIFICATION_VERSION

    assert _outdated_with_one_record("5.0") is True
    assert _outdated_with_one_record(CLASSIFICATION_VERSION) is False


def test_a_running_version_that_cannot_be_read_compares_nothing(monkeypatch):
    # Never raises: only a record without a version still marks the analysis outdated.
    from analysis import transaction_classifier

    monkeypatch.setattr(transaction_classifier, "CLASSIFICATION_VERSION", "unknown")
    assert [_outdated_with_one_record(version) for version in ("4.1", "5.0", None)] == [False, False, True]


@pytest.mark.parametrize("version", [
    "²", "².0", "٤.1", "9" * 5000, "", " ", ".5", "-4", "+4", "4a.0", "4 .1", "4.", "4.x", "5.0.1",
], ids=["superscript", "superscript-dotted", "arabic-indic", "too-many-digits", "empty", "blank", "no-major",
        "negative", "signed", "letters", "inner-space", "empty-minor", "letter-minor", "three-parts"])
def test_a_version_that_cannot_be_read_never_raises_and_says_nothing(running_5_1, version):
    # C6 never raises. The classifier writes an ASCII "<major>.<minor>" (C4); anything else is malformed, so it
    # neither marks the analysis outdated nor hides an older record elsewhere. `str.isdigit` accepts a superscript
    # that `int` refuses, `int` reads non-ASCII digits, and it refuses a string past `sys.get_int_max_str_digits`.
    payload = with_flagged_rows(flagged_account_payload(groups=()), [flagged_row(None)])
    payload["statement"]["transactions"][-1]["classification"]["classification_version"] = version
    assert apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED)["analysis_rules_outdated"] is False
    with_flagged_rows(payload, [flagged_row(None, version="4.1")])
    assert apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED)["analysis_rules_outdated"] is True


def test_a_record_without_a_version_predates_versioning_and_marks_the_analysis_outdated():
    # A record written before `classification_version` existed was classified by the rules of that time, older
    # than the flag groups (D12), so the dashboard offers the re-analysis.
    legacy = account_payload()  # revenue records only, none versioned: what the oldest stored analyses hold
    assert "classification_version" not in legacy["statement"]["transactions"][0]["classification"]
    assert apply_flagged_groups_to_payload(legacy, enabled=ALL_TICKED)["analysis_rules_outdated"] is True
    # One version-less record among current ones is enough.
    mixed = with_flagged_rows(flagged_account_payload(), [flagged_row("mortgages", version=None)])
    assert apply_flagged_groups_to_payload(mixed, enabled=ALL_TICKED)["analysis_rules_outdated"] is True


def test_a_document_whose_records_carry_no_version_is_outdated_at_the_top_level():
    payload = flagged_document_payload()
    del payload["accounts"][1]["statement"]["transactions"][0]["classification"]["classification_version"]
    shown = apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED)
    assert shown["analysis_rules_outdated"] is True
    assert all("analysis_rules_outdated" not in account for account in shown["accounts"])


def test_a_fresh_analysis_and_one_without_classified_rows_are_not_outdated():
    assert apply_flagged_groups_to_payload(flagged_account_payload(), enabled=ALL_TICKED)[
        "analysis_rules_outdated"] is False
    assert apply_flagged_groups_to_payload(flagged_document_payload(), enabled=ALL_TICKED)[
        "analysis_rules_outdated"] is False
    assert apply_flagged_groups_to_payload({"statement": {}}, enabled=ALL_TICKED)["analysis_rules_outdated"] is False
    # Rows that carry no classification record at all say nothing about the rules that classified them.
    unclassified = account_payload()
    for row in unclassified["statement"]["transactions"]:
        del row["classification"]
    unclassified["statement"]["transactions"].append({"date": "2054-01-05", "classification": "not a record"})
    assert apply_flagged_groups_to_payload(unclassified, enabled=ALL_TICKED)["analysis_rules_outdated"] is False


def test_one_outdated_account_marks_the_whole_document_at_the_top_level():
    payload = flagged_document_payload()
    payload["accounts"][1]["statement"]["transactions"][-1]["classification"]["classification_version"] = "4.1"
    shown = apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED)
    assert shown["analysis_rules_outdated"] is True
    assert all("analysis_rules_outdated" not in account for account in shown["accounts"])
    assert "analysis_rules_outdated" not in payload


def test_a_flagged_credit_is_shown_and_hidden_with_its_group():
    """Owner ruling 2026-09-26 (C4): a factor's payout is a credit row of the Factoring group. It is tagged and its
    credited figures are served while the group is ticked, and both go when it is unticked; the record is kept."""
    payload = with_flagged_rows(account_payload(), [flagged_row("factoring", amount=3 * FLAGGED_DEBIT)])
    shown = apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED)
    [credit] = _flagged_rows(shown)
    assert (credit["amount"] > 0, credit["classification"]["flag_shown"]) == (True, True)
    assert shown["metrics"]["flagged_groups"]["factoring"]["count_credited"] == 1
    assert shown["detection"]["flagged_positions"][0]["total_credited"] == 3 * FLAGGED_DEBIT
    hidden = apply_flagged_groups_to_payload(payload, enabled={"flag_factoring": False})
    [credit] = _flagged_rows(hidden)
    assert credit["classification"]["flag_shown"] is False
    assert credit["classification"]["contributes_to_flagged_totals"] is True
    assert hidden["metrics"]["flagged_groups"] == {} and hidden["detection"]["flagged_positions"] == []
