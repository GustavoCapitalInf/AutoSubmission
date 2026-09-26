"""Every served surface follows the flag-group checkboxes (lender detection §8.2-8.4). Fabricated payloads only."""
import copy
import csv
import io
import json
import zipfile
from types import SimpleNamespace

import pytest

from analysis.flag_groups import FLAG_GROUPS, FLAG_SETTING_KEYS
from tests.flagged_payloads import (
    CURRENT_VERSION,
    FLAGGED_DEBIT,
    GROUP_KEYS,
    fabricated_payee,
    flagged_account_payload,
    flagged_document_payload,
    flagged_row,
    row_state,
    with_flagged_rows,
)
from tests.l1s3_payloads import account_payload
from webapp.app import app, store
from webapp.jobs import Job
from webapp.settings import DEFAULTS, SETTINGS_FILE, save_settings

EACH_GROUP = pytest.mark.parametrize("group", FLAG_GROUPS, ids=lambda group: group.key)


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    # The module store's data folder may be a real one ($WEBAPP_DATA_DIR); never touch its settings.
    monkeypatch.setattr(store.storage, "data_dir", tmp_path)
    return tmp_path / SETTINGS_FILE


@pytest.fixture
def done_job(monkeypatch):
    job = SimpleNamespace(id="job-flagged", status="done", analysis=flagged_account_payload(),
                          analysis_error=None, filename="fabricated.pdf", markdown="", html="")
    original = store.get
    monkeypatch.setattr(store, "get", lambda job_id: job if job_id == job.id else original(job_id))
    return job


def _groups(account):
    # A set: Flask serves JSON with its keys sorted, so the served order is not the payload's.
    return set(account["metrics"]["flagged_groups"])


def _flags(account):
    return {row["classification"]["flagged_group"]: row["classification"]["flag_shown"]
            for row in account["statement"]["transactions"] if row["classification"].get("flagged_group")}


def _member(job_id, payload):
    return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload, content_sha256=job_id)


# --- one statement: the analysis, its JSON export and the review responses (§8.2) ------------------------------

@EACH_GROUP
def test_the_analysis_and_its_json_export_follow_the_checkbox(settings_file, done_job, group):
    client = app.test_client()
    stored = copy.deepcopy(done_job.analysis)
    shown = client.get("/analysis/job-flagged").get_json()["analysis"]
    assert _groups(shown) == set(GROUP_KEYS) and all(_flags(shown).values())
    assert shown["analysis_rules_outdated"] is False
    client.post("/api/settings", json={group.setting: False})
    shown = client.get("/analysis/job-flagged").get_json()["analysis"]
    assert group.key not in _groups(shown)
    assert all(entry["group"] != group.key for entry in shown["detection"]["flagged_positions"])
    assert _flags(shown) == {key: key != group.key for key in GROUP_KEYS}
    exported = json.loads(client.get("/download/job-flagged/json").data)
    assert group.key not in _groups(exported) and _flags(exported)[group.key] is False
    # The stored record is never rewritten by presenting it, and never carries a serving-time tag.
    assert done_job.analysis == stored


def test_displayed_takes_one_settings_snapshot_and_carry_over_still_decides_the_nsf_basis(settings_file):
    from tests.test_webapp_settings import _ledger_metrics
    from webapp.app import _displayed

    payload = flagged_account_payload(groups=("mortgages",))
    payload["metrics"].update(_ledger_metrics())
    snapshot = {**DEFAULTS, "flag_mortgages": False}
    shown = _displayed(payload, settings=snapshot)
    assert shown["metrics"]["effective_nsf_count"] == 1 and shown["metrics"]["flagged_groups"] == {}
    shown = _displayed(payload, carry_over=True, settings=snapshot)
    assert shown["metrics"]["effective_nsf_count"] == 2 and shown["metrics"]["flagged_groups"] == {}
    assert _displayed(payload)["metrics"]["flagged_groups"] == {"mortgages": {
        "count": 1, "total": FLAGGED_DEBIT, "count_credited": 0, "total_credited": 0.0, "payees": 1}}
    save_settings(settings_file.parent, {"flag_mortgages": False})
    assert _displayed(payload)["metrics"]["flagged_groups"] == {}


def test_a_review_answers_with_the_checkboxes_applied_and_stores_no_tag(settings_file):
    payload = flagged_account_payload()
    credit = flagged_row(None, amount=FLAGGED_DEBIT, date="2054-01-06")
    credit["classification"].update({
        "revenue_classification": "unverified_deposit",
        "revenue_initial_classification": "unverified_deposit",
        "revenue_review_required": True,
    })
    with_flagged_rows(payload, [credit])
    job = store.create("fabricated-review.pdf")
    store.set_result(job.id, "# fabricated", "<h1>fabricated</h1>", analysis=payload)
    save_settings(settings_file.parent, {"flag_mortgages": False})
    response = app.test_client().post(
        f"/analysis/{job.id}/revenue-review",
        json={"source_location": credit["classification"]["source_location"], "decision": "confirm"},
    )
    assert response.status_code == 200
    shown = response.get_json()["analysis"]
    assert "mortgages" not in _groups(shown) and _flags(shown)["mortgages"] is False
    stored = store.get(job.id).analysis
    assert "mortgages" in _groups(stored)
    assert all("flag_shown" not in row["classification"] for row in stored["statement"]["transactions"])
    assert "analysis_rules_outdated" not in stored


# --- package members (§8.2) -----------------------------------------------------------------------------------

@EACH_GROUP
def test_package_members_carry_the_displayed_checkboxes(settings_file, done_job, group):
    from webapp.app import _package_members

    members, _ = _package_members([done_job])
    assert group.key in _groups(members[0][1])
    save_settings(settings_file.parent, {group.setting: False})
    members, _ = _package_members([done_job])
    assert group.key not in _groups(members[0][1]) and _flags(members[0][1])[group.key] is False


@EACH_GROUP
def test_every_published_account_of_a_document_member_follows_the_checkbox(settings_file, group):
    from webapp.app import _package_members

    job = Job(id="doc", filename="doc.pdf", status="done", analysis=flagged_document_payload(), content_sha256="doc")
    save_settings(settings_file.parent, {group.setting: False})
    members, excluded = _package_members([job])
    assert [member[2] for member in members] == [1, 2] and excluded == []
    for _job, account, _index, _count in members:
        assert group.key not in _groups(account) and _flags(account)[group.key] is False


def test_the_checkboxes_never_change_which_accounts_a_package_leaves_out(settings_file):
    # The exclusions read the roster off the displayed copy (webapp/app.py::_package_members); the flag step
    # touches only each account's rows, metrics and detection, so the idle and unverified main-account rules
    # decide the same way whatever is ticked, and the stored records are never rewritten.
    from tests.test_webapp_settings import _roster
    from webapp.app import _package_members

    def document_job(job_id, roster=None):
        payload = flagged_document_payload()
        if roster is not None:
            payload["document"]["account_roster"] = roster
        return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload, content_sha256=job_id)

    jobs = [document_job("idle", _roster("idle")), document_job("held", _roster("held")),
            document_job("verified", _roster("published")), document_job("no-roster")]
    stored = [copy.deepcopy(job.analysis) for job in jobs]

    def decided():
        members, excluded = _package_members(jobs)
        return sorted((member[0].id, member[2]) for member in members), excluded

    ticked = decided()
    save_settings(settings_file.parent, {key: False for key in FLAG_SETTING_KEYS})
    assert decided() == ticked
    assert [item["reason"] for item in ticked[1]] == ["main_account_idle", "main_account_unverified"]
    assert [job.analysis for job in jobs] == stored


def test_a_package_reads_the_settings_once_and_hands_that_snapshot_to_every_member(settings_file, monkeypatch):
    # One read per package (spec §8.2, C6). Every member's displayed copy, and the flag roll-up (Task 7), use that
    # one snapshot, so a checkbox saved mid-request cannot split a package across two sets of ticked groups.
    from webapp.app import _package_analysis, _package_members
    from webapp.settings import load_settings

    reads = []

    def counting_load(data_dir):
        reads.append(data_dir)
        return load_settings(data_dir)

    monkeypatch.setattr("webapp.app.load_settings", counting_load)
    jobs = [_member("a", flagged_account_payload(0)), _member("b", flagged_account_payload(1))]
    _package_analysis(jobs)
    assert len(reads) == 1
    _package_members(jobs)
    assert len(reads) == 2
    # A caller that passes the snapshot reads nothing more.
    _package_analysis(jobs, settings=dict(DEFAULTS))
    _package_members(jobs, settings=dict(DEFAULTS))
    assert len(reads) == 2


def test_package_members_follow_the_snapshot_they_are_handed_not_the_file(settings_file):
    from webapp.app import _package_analysis

    save_settings(settings_file.parent, dict(DEFAULTS))  # the file ticks every group
    jobs = [_member("a", flagged_account_payload(0)), _member("b", flagged_account_payload(1))]
    package = _package_analysis(jobs, settings={**DEFAULTS, "flag_mortgages": False})
    records = [row["classification"] for row in package["transactions"] if row["classification"].get("flagged_group")]
    assert len(records) == 2 * len(GROUP_KEYS)
    assert all(record["flag_shown"] is (record["flagged_group"] != "mortgages") for record in records)


# --- one statement: the CSV and XLSX exports (§8.4) -------------------------------------------------------------

def _csv_cells(text):
    return {(row[0], row[1]): row[2] for row in list(csv.reader(io.StringIO(text)))[1:]}


def _sheet(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return archive.read("xl/worksheets/sheet1.xml").decode("utf-8")


@EACH_GROUP
def test_the_csv_and_xlsx_exports_carry_readable_rows_for_ticked_groups_only(settings_file, done_job, group):
    client = app.test_client()
    section = f"flagged_{group.key}_1"
    cells = _csv_cells(client.get("/download/job-flagged/csv").get_data(as_text=True))
    assert cells[(section, "payee")] == fabricated_payee(group.key)
    assert cells[(section, "count")] == "1"
    assert cells[(section, "total_debited")] == str(FLAGGED_DEBIT)
    assert cells[(section, "cadence")] == "single"
    assert ("detection", "flagged_positions") not in cells  # the readable rows replace the JSON cell
    assert f"<t>{section}</t>" in _sheet(client.get("/download/job-flagged/xlsx").get_data())
    client.post("/api/settings", json={group.setting: False})
    cells = _csv_cells(client.get("/download/job-flagged/csv").get_data(as_text=True))
    assert not [key for key in cells if key[0].startswith(f"flagged_{group.key}_")]
    assert len({key[0] for key in cells if key[0].startswith("flagged_")}) == len(GROUP_KEYS) - 1
    assert f"<t>{section}</t>" not in _sheet(client.get("/download/job-flagged/xlsx").get_data())


def test_every_account_of_a_document_gets_its_own_flagged_rows():
    from webapp.app import _analysis_rows

    rows = _analysis_rows(flagged_document_payload(groups=("mortgages",)))
    assert {"account_1.flagged_mortgages_1", "account_2.flagged_mortgages_1"} <= {section for section, _f, _v in rows}


def test_two_payees_of_one_group_are_numbered_in_the_payload_order():
    from webapp.app import _analysis_rows

    payload = with_flagged_rows(account_payload(), [
        flagged_row("mortgages", payee="FABRICATED MORTGAGE A"),
        flagged_row("mortgages", payee="FABRICATED MORTGAGE B", amount=-2 * FLAGGED_DEBIT),
    ])
    payees = {section: value for section, field, value in _analysis_rows(payload) if field == "payee"}
    assert payees == {"flagged_mortgages_1": "FABRICATED MORTGAGE B", "flagged_mortgages_2": "FABRICATED MORTGAGE A"}


def test_a_payee_that_reads_as_a_formula_is_escaped_in_both_sheets():
    from webapp.app import _analysis_csv, _analysis_xlsx, _displayed

    payload = with_flagged_rows(account_payload(), [flagged_row("mortgages", payee="=FABRICATED(1)")])
    shown = _displayed(payload, settings=dict(DEFAULTS))
    assert "flagged_mortgages_1,payee,'=FABRICATED(1)" in _analysis_csv(shown)
    sheet = _sheet(_analysis_xlsx(shown))
    assert "<t>'=FABRICATED(1)</t>" in sheet and "<t>=FABRICATED(1)</t>" not in sheet


# --- the package roll-up (§8.3) -------------------------------------------------------------------------------

def _not_flagged(totals):
    return {key: value for key, value in totals.items() if not key.startswith("flagged_")}


def test_the_package_rolls_up_each_ticked_group_across_members(settings_file):
    from webapp.app import _package_analysis

    package = _package_analysis([
        _member("a", flagged_account_payload(0)),
        _member("b", flagged_account_payload(1, amount=-3.0, date="2054-01-12")),
    ])
    assert list(package["flagged_positions"]) == list(GROUP_KEYS)
    for key in GROUP_KEYS:
        [item] = package["flagged_positions"][key]
        assert item["payee"] == fabricated_payee(key)
        assert (item["documents"], item["count"], item["total_debited"]) == (2, 2, FLAGGED_DEBIT + 3.0)
        assert (item["first_date"], item["last_date"]) == ("2054-01-05", "2054-01-12")
    assert len(package["flagged_evidence"]) == 2 * len(GROUP_KEYS)
    assert {evidence["source_job"] for evidence in package["flagged_evidence"]} == {"a", "b"}
    assert all("source_account" not in evidence for evidence in package["flagged_evidence"])


def test_a_row_without_a_named_payee_rolls_up_under_its_group_label(settings_file):
    from analysis.flag_groups import FLAG_GROUP_BY_KEY
    from webapp.app import _package_analysis

    payload = with_flagged_rows(account_payload(), [flagged_row("bank_loans", payee="")])
    [item] = _package_analysis([_member("a", payload)])["flagged_positions"]["bank_loans"]
    assert item["payee"] == FLAG_GROUP_BY_KEY["bank_loans"].label


def test_a_row_the_analysis_does_not_count_never_enters_the_roll_up(settings_file):
    from webapp.app import _package_analysis

    payload = with_flagged_rows(account_payload(), [flagged_row("mortgages"),
                                                    flagged_row("mortgages", contributes=False)])
    package = _package_analysis([_member("a", payload)])
    [item] = package["flagged_positions"]["mortgages"]
    assert (item["count"], item["total_debited"]) == (1, FLAGGED_DEBIT)
    assert len(package["flagged_evidence"]) == 1


@EACH_GROUP
def test_an_unticked_group_leaves_the_package_and_nothing_else_moves(settings_file, group):
    from webapp.app import _package_analysis

    jobs = [_member("a", flagged_account_payload(0)), _member("b", flagged_account_payload(1))]
    ticked = _package_analysis(jobs)
    save_settings(settings_file.parent, {group.setting: False})
    unticked = _package_analysis(jobs)
    assert set(unticked["flagged_positions"]) == set(GROUP_KEYS) - {group.key}
    assert all(evidence["flagged_group"] != group.key for evidence in unticked["flagged_evidence"])
    # D7: the lender totals, the withholding and the decision never read a flag group or its checkbox.
    assert _not_flagged(unticked["totals"]) == _not_flagged(ticked["totals"])
    assert ticked["totals"]["decision"] == "approved"
    assert unticked["funders"] == ticked["funders"] and unticked["potential_lenders"] == ticked["potential_lenders"]


def test_premium_financing_stays_insurance_whether_or_not_it_is_flagged(settings_file):
    from webapp.app import _package_analysis

    jobs = [_member("a", flagged_account_payload(0, groups=("premium_financing",))),
            _member("b", flagged_account_payload(1, groups=("premium_financing",)))]
    ticked = _package_analysis(jobs)
    [item] = ticked["flagged_positions"]["premium_financing"]
    assert (item["count"], item["total_debited"]) == (2, 2 * FLAGGED_DEBIT)
    assert (ticked["totals"]["insurance_count"], ticked["totals"]["insurance_total"]) == (2, 2 * FLAGGED_DEBIT)
    save_settings(settings_file.parent, {"flag_premium_financing": False})
    unticked = _package_analysis(jobs)
    assert unticked["flagged_positions"] == {} and unticked["flagged_evidence"] == []
    # The checkbox hides the flag only: the rows are still insurance, counted and evidenced as today.
    assert (unticked["totals"]["insurance_count"], unticked["totals"]["insurance_total"]) == (2, 2 * FLAGGED_DEBIT)
    assert [evidence["source_job"] for evidence in unticked["insurance_evidence"]] == ["a", "b"]


def test_the_roll_up_reads_the_same_snapshot_as_the_member_rows(settings_file):
    # Spec §8.2: the members' tags and the roll-up come from ONE snapshot. The file ticks every group and the
    # snapshot unticks premium financing, so a roll-up that re-read the file would still show it.
    from webapp.app import _package_analysis

    save_settings(settings_file.parent, dict(DEFAULTS))
    jobs = [_member("a", flagged_account_payload(0)), _member("b", flagged_account_payload(1))]
    package = _package_analysis(jobs, settings={**DEFAULTS, "flag_premium_financing": False})
    assert set(package["flagged_positions"]) == set(GROUP_KEYS) - {"premium_financing"}
    assert {evidence["flagged_group"] for evidence in package["flagged_evidence"]} == set(package["flagged_positions"])
    tagged = {row["classification"]["flagged_group"] for row in package["transactions"]
              if row["classification"]["flag_shown"]}
    assert tagged == set(package["flagged_positions"])
    # Hidden, never re-classified: both premium-financing rows still count as insurance (C4, D7).
    assert package["totals"]["insurance_count"] == 2


def test_flag_evidence_of_a_document_member_names_its_account(settings_file):
    from webapp.app import _package_analysis

    package = _package_analysis([_member("doc", flagged_document_payload(groups=("mortgages",)))])
    assert [(evidence["source_job"], evidence["source_account"], evidence["source_location"])
            for evidence in package["flagged_evidence"]] == [("doc", 1, "transaction:2"), ("doc", 2, "transaction:2")]
    [item] = package["flagged_positions"]["mortgages"]
    assert (item["documents"], item["count"], item["total_debited"]) == (2, 2, 3 * FLAGGED_DEBIT)


def test_an_internal_transfer_leg_never_enters_the_flag_roll_up(settings_file):
    from webapp.app import _package_analysis

    payload = flagged_document_payload(groups=("mortgages",))
    # Account 1's ledger holds its revenue credit at position 0 and its flagged debit at position 1; the document
    # pairs that debit with account 2's credit as one movement between its own accounts.
    payload["document"]["internal_transfers"] = [{"a": [0, 1], "b": [1, 0]}]
    package = _package_analysis([_member("doc", payload)])
    [item] = package["flagged_positions"]["mortgages"]
    assert (item["documents"], item["count"], item["total_debited"]) == (1, 1, 2 * FLAGGED_DEBIT)
    assert [evidence["source_account"] for evidence in package["flagged_evidence"]] == [2]


def test_a_package_of_payloads_without_flag_groups_rolls_up_nothing(settings_file):
    from tests.test_package_currency import member
    from webapp.app import _package_analysis

    package = _package_analysis([member("a", "USD"), _member("b", account_payload())])
    assert package["flagged_positions"] == {} and package["flagged_evidence"] == []


@EACH_GROUP
def test_the_package_totals_count_the_debits_of_ticked_groups_only(settings_file, group):
    from webapp.app import _package_analysis

    # Two members, one debit per group each: every group counts two debits and debits both amounts.
    jobs = [_member("a", flagged_account_payload(0)), _member("b", flagged_account_payload(1, amount=-3.0))]
    per_group = FLAGGED_DEBIT + 3.0
    totals = _package_analysis(jobs)["totals"]
    assert (totals["flagged_position_count"], totals["flagged_position_total"]) == (
        2 * len(GROUP_KEYS), len(GROUP_KEYS) * per_group)
    save_settings(settings_file.parent, {group.setting: False})
    totals = _package_analysis(jobs)["totals"]
    assert (totals["flagged_position_count"], totals["flagged_position_total"]) == (
        2 * (len(GROUP_KEYS) - 1), (len(GROUP_KEYS) - 1) * per_group)


def test_a_package_without_flag_groups_publishes_zero_flagged_totals(settings_file):
    from webapp.app import _package_analysis

    totals = _package_analysis([_member("b", account_payload())])["totals"]
    assert (totals["flagged_position_count"], totals["flagged_position_total"]) == (0, 0.0)


def test_a_member_without_analysis_adds_nothing_to_the_flag_roll_up(settings_file):
    # Mirrors the NSF basis test of the same shape (tests/test_webapp_settings.py): a failed member has no analysis.
    from webapp.app import _package_analysis

    done = _member("a", flagged_account_payload(0, groups=("mortgages",)))
    failed = Job(id="b", filename="b.pdf", status="failed", analysis=None, content_sha256="b")
    package = _package_analysis([done, failed])
    [item] = package["flagged_positions"]["mortgages"]
    assert (item["documents"], item["count"], package["totals"]["flagged_position_count"]) == (1, 1, 1)
    alone = _package_analysis([failed])
    assert alone["flagged_positions"] == {} and alone["totals"]["flagged_position_count"] == 0


# --- the package CSV and XLSX (§8.4) -------------------------------------------------------------------------

@EACH_GROUP
def test_the_package_csv_and_xlsx_carry_the_ticked_groups_only(settings_file, group):
    from webapp.app import _package_analysis, _package_csv, _package_xlsx

    jobs = [_member("a", flagged_account_payload(0)), _member("b", flagged_account_payload(1))]
    section = f"flagged_{group.key}_1"
    package = _package_analysis(jobs)
    cells = _csv_cells(_package_csv(package))
    assert cells[(section, "payee")] == fabricated_payee(group.key)
    assert (cells[(section, "documents")], cells[(section, "count")]) == ("2", "2")
    assert cells[(section, "total_debited")] == str(2 * FLAGGED_DEBIT)
    assert cells[("totals", "flagged_position_count")] == str(2 * len(GROUP_KEYS))
    assert f"<t>{section}</t>" in _sheet(_package_xlsx(package))
    save_settings(settings_file.parent, {group.setting: False})
    package = _package_analysis(jobs)
    cells = _csv_cells(_package_csv(package))
    assert not [key for key in cells if key[0].startswith(f"flagged_{group.key}_")]
    assert f"<t>{section}</t>" not in _sheet(_package_xlsx(package))


def test_a_package_payee_that_reads_as_a_formula_is_escaped(settings_file):
    from webapp.app import _package_analysis, _package_csv, _package_xlsx

    payload = with_flagged_rows(account_payload(), [flagged_row("mortgages", payee="=FABRICATED(1)")])
    package = _package_analysis([_member("a", payload)])
    assert "flagged_mortgages_1,payee,'=FABRICATED(1)" in _package_csv(package)
    sheet = _sheet(_package_xlsx(package))
    assert "<t>'=FABRICATED(1)</t>" in sheet and "<t>=FABRICATED(1)</t>" not in sheet


def test_the_package_routes_follow_the_checkboxes(settings_file):
    ids = []
    for index in (0, 1):
        job = store.create(f"fabricated-{index}.pdf")
        store.set_result(job.id, "# fabricated", "<h1>fabricated</h1>", analysis=flagged_account_payload(index))
        ids.append(job.id)
    client = app.test_client()
    save_settings(settings_file.parent, {"flag_credit_cards": False})
    served = client.get(f"/package_analysis?ids={','.join(ids)}").get_json()
    assert "credit_cards" not in served["flagged_positions"] and "mortgages" in served["flagged_positions"]
    cells = _csv_cells(client.get(f"/package_download/csv?ids={','.join(ids)}").get_data(as_text=True))
    assert ("flagged_mortgages_1", "payee") in cells
    assert not [key for key in cells if key[0].startswith("flagged_credit_cards_")]


# --- flagged credits: a factor's payouts (owner ruling 2026-09-26; contract C4-C6) -----------------------------

#: What each fabricated factoring credit posts: three times a flagged debit, so the two totals never coincide.
FACTOR_PAYOUT = 3 * FLAGGED_DEBIT


def _factored(index=0, *, payee=None, payouts=1, date="2054-01-12"):
    """An ACCOUNT payload whose factoring payee is paid one debit and pays in `payouts` credits (C4)."""
    return with_flagged_rows(account_payload(index), [
        flagged_row("factoring", payee=payee),
        *(flagged_row("factoring", payee=payee, amount=FACTOR_PAYOUT, date=date) for _ in range(payouts)),
    ])


def test_a_factoring_credit_is_served_flagged_and_follows_its_checkbox(settings_file):
    from webapp.app import _displayed

    shown = _displayed(_factored(), settings=dict(DEFAULTS))
    assert shown["metrics"]["flagged_groups"] == {"factoring": {
        "count": 1, "total": FLAGGED_DEBIT, "count_credited": 1, "total_credited": FACTOR_PAYOUT, "payees": 1}}
    [entry] = shown["detection"]["flagged_positions"]
    assert (entry["count"], entry["total_debited"], entry["count_credited"], entry["total_credited"]) == (
        1, FLAGGED_DEBIT, 1, FACTOR_PAYOUT)
    rows = [row for row in shown["statement"]["transactions"] if row["classification"].get("flagged_group")]
    assert [(row["amount"] > 0, row["classification"]["flag_shown"]) for row in rows] == [(False, True), (True, True)]
    hidden = _displayed(_factored(), settings={**DEFAULTS, "flag_factoring": False})
    assert hidden["metrics"]["flagged_groups"] == {} and hidden["detection"]["flagged_positions"] == []
    assert not [row for row in hidden["statement"]["transactions"] if row["classification"]["flag_shown"]]


def test_the_statement_csv_and_xlsx_carry_the_credited_fields(settings_file):
    from webapp.app import _analysis_csv, _analysis_xlsx, _displayed

    shown = _displayed(_factored(), settings=dict(DEFAULTS))
    cells = _csv_cells(_analysis_csv(shown))
    assert (cells[("flagged_factoring_1", "count")], cells[("flagged_factoring_1", "total_debited")]) == (
        "1", str(FLAGGED_DEBIT))
    assert (cells[("flagged_factoring_1", "count_credited")], cells[("flagged_factoring_1", "total_credited")]) == (
        "1", str(FACTOR_PAYOUT))
    assert "<t>total_credited</t>" in _sheet(_analysis_xlsx(shown))


def test_the_package_rolls_up_credits_apart_from_debits(settings_file):
    from webapp.app import _package_analysis

    jobs = [_member("a", _factored(0)), _member("b", _factored(1, date="2054-01-19"))]
    package = _package_analysis(jobs)
    [item] = package["flagged_positions"]["factoring"]
    assert (item["documents"], item["count"], item["total_debited"]) == (2, 2, 2 * FLAGGED_DEBIT)
    assert (item["count_credited"], item["total_credited"]) == (2, 2 * FACTOR_PAYOUT)
    # The dates are every counted row's, debit or credit.
    assert (item["first_date"], item["last_date"]) == ("2054-01-05", "2054-01-19")
    totals = package["totals"]
    # flagged_position_count and flagged_position_total stay debits only (C6).
    assert (totals["flagged_position_count"], totals["flagged_position_total"]) == (2, 2 * FLAGGED_DEBIT)
    assert (totals["flagged_position_count_credited"], totals["flagged_position_total_credited"]) == (
        2, 2 * FACTOR_PAYOUT)
    assert len(package["flagged_evidence"]) == 4
    # D7: the credits never touch the decision, and unticking the group moves nothing but the flag figures.
    save_settings(settings_file.parent, {"flag_factoring": False})
    unticked = _package_analysis(jobs)
    assert (unticked["totals"]["flagged_position_count_credited"],
            unticked["totals"]["flagged_position_total_credited"]) == (0, 0.0)
    assert _not_flagged(unticked["totals"]) == _not_flagged(totals)
    assert totals["decision"] == unticked["totals"]["decision"]


def test_a_payee_whose_counted_rows_are_all_credits_rolls_up_with_no_debits(settings_file):
    from webapp.app import _package_analysis

    payload = with_flagged_rows(account_payload(), [flagged_row("factoring", amount=FACTOR_PAYOUT)])
    [item] = _package_analysis([_member("a", payload)])["flagged_positions"]["factoring"]
    assert (item["count"], item["total_debited"], item["count_credited"], item["total_credited"]) == (
        0, 0.0, 1, FACTOR_PAYOUT)


def test_package_positions_rank_by_debited_plus_credited(settings_file):
    from webapp.app import _package_analysis

    payload = with_flagged_rows(account_payload(), [
        flagged_row("factoring", payee="FABRICATED DEBITED FACTOR", amount=-3 * FLAGGED_DEBIT),
        flagged_row("factoring", payee="FABRICATED PAYING FACTOR", amount=-FLAGGED_DEBIT),
        flagged_row("factoring", payee="FABRICATED PAYING FACTOR", amount=FACTOR_PAYOUT),
    ])
    items = _package_analysis([_member("a", payload)])["flagged_positions"]["factoring"]
    # 1 debited plus 3 paid in outranks 3 debited alone, and the paid-in money never joins total_debited.
    assert [(item["payee"], item["total_debited"], item["total_credited"]) for item in items] == [
        ("FABRICATED PAYING FACTOR", FLAGGED_DEBIT, FACTOR_PAYOUT),
        ("FABRICATED DEBITED FACTOR", 3 * FLAGGED_DEBIT, 0.0),
    ]


def test_the_package_csv_and_xlsx_carry_the_credited_fields(settings_file):
    from webapp.app import _package_analysis, _package_csv, _package_xlsx

    package = _package_analysis([_member("a", _factored(0)), _member("b", _factored(1))])
    cells = _csv_cells(_package_csv(package))
    assert (cells[("flagged_factoring_1", "count_credited")], cells[("flagged_factoring_1", "total_credited")]) == (
        "2", str(2 * FACTOR_PAYOUT))
    assert (cells[("totals", "flagged_position_count_credited")],
            cells[("totals", "flagged_position_total_credited")]) == ("2", str(2 * FACTOR_PAYOUT))
    assert "<t>flagged_position_total_credited</t>" in _sheet(_package_xlsx(package))


# --- the package cadence (§8.3; needs analysis/cadence.py from S2) -------------------------------------------

def _member_paying(job_id, index, group_key, dates):
    payload = with_flagged_rows(account_payload(index), [flagged_row(group_key, date=date) for date in dates])
    return _member(job_id, payload)


def test_the_package_cadence_is_read_across_every_members_dates(settings_file):
    from webapp.app import _package_analysis

    package = _package_analysis([
        _member_paying("a", 0, "vehicle_financing", ("2054-01-05", "2054-01-12")),
        _member_paying("b", 1, "vehicle_financing", ("2054-01-19", "2054-01-26")),
    ])
    [item] = package["flagged_positions"]["vehicle_financing"]
    assert (item["cadence"], item["count"]) == ("weekly", 4)
    assert (item["first_date"], item["last_date"]) == ("2054-01-05", "2054-01-26")


def test_one_payment_per_monthly_statement_reads_as_monthly(settings_file):
    from webapp.app import _package_analysis

    package = _package_analysis([
        _member_paying("jan", 0, "mortgages", ("2054-01-15",)),
        _member_paying("feb", 1, "mortgages", ("2054-02-15",)),
        _member_paying("mar", 2, "mortgages", ("2054-03-15",)),
    ])
    [item] = package["flagged_positions"]["mortgages"]
    assert (item["cadence"], item["documents"]) == ("monthly", 3)


def test_a_payee_paid_once_in_the_package_has_a_single_cadence(settings_file):
    from webapp.app import _package_analysis

    package = _package_analysis([_member("a", flagged_account_payload(0, groups=("mortgages",)))])
    assert package["flagged_positions"]["mortgages"][0]["cadence"] == "single"


def test_every_flag_roll_up_item_carries_the_contract_fields_in_order(settings_file):
    from webapp.app import _package_analysis

    package = _package_analysis([_member("a", flagged_account_payload(0))])
    for items in package["flagged_positions"].values():
        for item in items:
            assert list(item) == ["payee", "documents", "count", "total_debited", "count_credited", "total_credited",
                                  "cadence", "first_date", "last_date"]


# --- S2's real payload flows through serving and the package (contract C4/C5; after S2 merges) ----------------

#: The keys C5 publishes on every `detection.flagged_positions` entry, and on every `metrics.flagged_groups` value.
C5_POSITION_KEYS = {"group", "payee", "matched_alias", "count", "total_debited", "count_credited", "total_credited",
                    "cadence", "avg_gap_days", "first_date", "last_date", "source_locations"}
C5_GROUP_KEYS = {"count", "total", "count_credited", "total_credited", "payees"}


def _analysed_payload() -> dict:
    """A fabricated statement run through the real classifier, metrics, detection and serializer.

    The first two debits name no payee; S2's descriptor rules (spec §4.3 step 8) file them under mortgages and
    lines of credit. The next three pay the owner's amendment groups (spec §2): an insurance premium to a
    premium-finance payee, a floor-plan payee and a factoring payee. The last row is that factoring payee's payout
    for invoices it bought, a credit that stays revenue and carries the Factoring flag (owner ruling 2026-09-26).
    Each name is the first alias of its C2 table, which S1 renders from the C10 ledger, read at run time, so no payee
    name is written in a test."""
    from analysis.classification_registry import FACTORING_ALIASES, FLOOR_PLAN_ALIASES, PREMIUM_FINANCE_ALIASES
    from analysis.detect import detect
    from analysis.metrics import compute_metrics
    from analysis.pipeline import DocumentIntegrity, Quality, Report
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction
    from analysis.serialization import report_to_dict
    from analysis.transaction_classifier import classify_statement_transactions

    def row(day, description, amount):
        return Transaction(date=day, description=description, amount=amount,
                           direction="credit" if amount >= 0 else "debit")

    def first_alias(name, table):
        # C10's validator requires no admitted entity in these three groups, so an empty table is named here
        # instead of surfacing as a bare StopIteration.
        aliases = [alias for entity_aliases in table.values() for alias in entity_aliases]
        assert aliases, f"{name} holds no alias: the C10 ledger admits no entity in this group"
        return aliases[0]

    premium_payee = first_alias("PREMIUM_FINANCE_ALIASES", PREMIUM_FINANCE_ALIASES)
    floor_plan_payee = first_alias("FLOOR_PLAN_ALIASES", FLOOR_PLAN_ALIASES)
    factoring_payee = first_alias("FACTORING_ALIASES", FACTORING_ALIASES)
    statement = Statement(bank="FABRICATED BANK", account_number="0000", transactions=[
        row("2054-01-02", "FABRICATED CUSTOMER DEPOSIT", 10 * FLAGGED_DEBIT),
        row("2054-01-05", "FABRICATED MORTGAGE PAYMENT", -FLAGGED_DEBIT),
        row("2054-01-06", "FABRICATED LINE OF CREDIT PAYMENT", -FLAGGED_DEBIT),
        row("2054-01-07", f"FABRICATED {premium_payee} INSURANCE PREMIUM", -FLAGGED_DEBIT),
        row("2054-01-08", f"FABRICATED {floor_plan_payee} PAYMENT", -FLAGGED_DEBIT),
        row("2054-01-09", f"FABRICATED {factoring_payee} PAYMENT", -FLAGGED_DEBIT),
        row("2054-01-10", f"FABRICATED {factoring_payee} INVOICE PAYMENT", 3 * FLAGGED_DEBIT),
    ])
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    detection = detect(statement, classifications=records, eligible_deposits=metrics.eligible_deposits)
    return report_to_dict(Report(
        statement=statement, reconciliation=reconcile(statement), metrics=metrics, detection=detection,
        quality=Quality(level="transaction_level", transaction_detail_reliable=True,
                        summary_totals_reliable=True, corporate_use="approved"),
        integrity=DocumentIntegrity(risk_level="clear", flags=[], notes=[]),
        model_used="test", escalated=False, classifications=records,
    ))


def test_the_classifiers_payload_carries_the_contract_fields():
    payload = _analysed_payload()
    positions = payload["detection"]["flagged_positions"]
    groups = {entry["group"] for entry in positions}
    assert groups & {"mortgages", "lines_of_credit"}
    assert {"premium_financing", "floor_plan", "factoring"} <= groups
    assert all(set(entry) == C5_POSITION_KEYS for entry in positions)
    assert all(set(value) == C5_GROUP_KEYS for value in payload["metrics"]["flagged_groups"].values())
    flagged = [row["classification"] for row in payload["statement"]["transactions"]
               if row["classification"]["flagged_group"]]
    assert flagged and all(record["contributes_to_flagged_totals"] is True for record in flagged)
    # Every record carries the state the fixtures give its group: floor_plan_financing, factoring (its payout
    # credit too), and insurance for premium financing (C1, C4).
    assert all(record["classification"] == row_state(record["flagged_group"]) for record in flagged)


def test_the_classifiers_premium_financing_row_is_an_insurance_row_with_the_flag():
    payload = _analysed_payload()
    [premium] = [row["classification"] for row in payload["statement"]["transactions"]
                 if row["classification"]["flagged_group"] == "premium_financing"]
    fixture = flagged_row("premium_financing")["classification"]
    names = ("classification", "flagged_group", "contributes_to_insurance_totals", "contributes_to_flagged_totals")
    assert {name: premium[name] for name in names} == {name: fixture[name] for name in names}


def test_the_classifiers_factoring_credit_is_revenue_and_rolls_up_as_credited(settings_file):
    """Owner ruling 2026-09-26 (C4-C6): the factor's payout is flagged, counted apart from the debits, never
    financing proceeds, and it matches the fixtures' credit row."""
    from webapp.app import _package_analysis

    payload = _analysed_payload()
    [credit] = [row["classification"] for row in payload["statement"]["transactions"]
                if row["classification"]["flagged_group"] == "factoring" and row["amount"] > 0]
    fixture = flagged_row("factoring", amount=3 * FLAGGED_DEBIT)["classification"]
    names = ("classification", "flagged_group", "contributes_to_flagged_totals")
    assert {name: credit[name] for name in names} == {name: fixture[name] for name in names}
    assert credit["contributes_to_lender_credit_exclusion"] is False
    assert credit["revenue_match_method"] != "financing_proceeds_credit"
    assert payload["metrics"]["lender_credits"] == 0.0
    [position] = [entry for entry in payload["detection"]["flagged_positions"] if entry["group"] == "factoring"]
    assert (position["count"], position["count_credited"], position["total_credited"]) == (1, 1, 3 * FLAGGED_DEBIT)
    package = _package_analysis([_member("fabricated", payload)])
    [item] = package["flagged_positions"]["factoring"]
    assert (item["count"], item["count_credited"], item["total_credited"]) == (1, 1, 3 * FLAGGED_DEBIT)
    assert package["totals"]["flagged_position_count_credited"] == 1


def test_the_classifiers_payload_is_served_and_packaged_by_the_checkboxes(settings_file):
    from webapp.app import _displayed, _package_analysis

    payload = _analysed_payload()
    none_ticked = {**DEFAULTS, **{key: False for key in FLAG_SETTING_KEYS}}
    hidden = _displayed(payload, settings=none_ticked)
    assert hidden["metrics"]["flagged_groups"] == {} and hidden["detection"]["flagged_positions"] == []
    assert hidden["analysis_rules_outdated"] is False
    package = _package_analysis([_member("fabricated", payload)])
    assert set(package["flagged_positions"]) == {entry["group"] for entry in payload["detection"]["flagged_positions"]}
    # D7: flag groups never make a package need review, and never enter the lender math.
    assert package["totals"]["decision"] == "approved"
    assert package["totals"]["lender_debit_count"] == 0 and package["totals"]["potential_lender_debit_count"] == 0
    # Unticking every group hides every flag; the premium-financing row still counts as insurance.
    unticked = _package_analysis([_member("fabricated", payload)], settings=none_ticked)
    assert unticked["flagged_positions"] == {} and unticked["totals"]["flagged_position_count"] == 0
    assert unticked["totals"]["flagged_position_count_credited"] == 0
    assert unticked["totals"]["insurance_count"] == package["totals"]["insurance_count"] == 1
    assert unticked["totals"]["decision"] == "approved"


def test_the_fixture_records_use_only_fields_the_classifier_writes():
    from dataclasses import fields

    from analysis.transaction_classifier import CLASSIFICATION_VERSION, TransactionClassification

    names = {field.name for field in fields(TransactionClassification)}
    assert set(flagged_row("mortgages")["classification"]) <= names
    assert CLASSIFICATION_VERSION == CURRENT_VERSION
