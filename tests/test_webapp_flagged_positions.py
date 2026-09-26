"""Every served surface follows the flag-group checkboxes (lender detection §8.2-8.4). Fabricated payloads only."""
import copy
import json
from types import SimpleNamespace

import pytest

from analysis.flag_groups import FLAG_GROUPS, FLAG_SETTING_KEYS
from tests.flagged_payloads import (
    FLAGGED_DEBIT,
    GROUP_KEYS,
    flagged_account_payload,
    flagged_document_payload,
    flagged_row,
    with_flagged_rows,
)
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
    assert _displayed(payload)["metrics"]["flagged_groups"] == {"mortgages": {"count": 1, "total": FLAGGED_DEBIT,
                                                                              "payees": 1}}
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
