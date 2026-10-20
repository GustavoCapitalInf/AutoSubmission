"""The Settings page: the NSF basis toggle (owner ruling, 2026-09-22) and one checkbox per flag group (lender
detection, 2026-09-24). Fabricated payloads only."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from analysis.flag_groups import FLAG_GROUPS, FLAG_SETTING_KEYS
from webapp.app import app, store
from webapp.settings import DEFAULTS, SETTINGS_FILE, load_settings, save_settings

#: The whole settings dict with nothing saved: printed NSF days, and every flag group shown. Spelled out rather
#: than derived, so a key added to DEFAULTS without thinking fails here.
EXPECTED_DEFAULTS = {
    "nsf_carry_over": False,
    # The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): "Mark Zelle Payments as True Revenue", Yes.
    "zelle_true_revenue": True,
    "flag_alternative_positions": True,
    "flag_lines_of_credit": True,
    "flag_credit_cards": True,
    "flag_vehicle_financing": True,
    "flag_bank_loans": True,
    "flag_mortgages": True,
    "flag_leases_rentals": True,
    "flag_personal_loans": True,
    "flag_floor_plan": True,
    "flag_factoring": True,
    "flag_premium_financing": True,
    "flag_debt_relief": True,
}
#: The settings after the NSF toggle alone is turned on: a save merges, so every other key keeps its default.
CARRY_OVER = {**EXPECTED_DEFAULTS, "nsf_carry_over": True}


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    # The module store's data folder may be a real one ($WEBAPP_DATA_DIR); never touch its settings.
    monkeypatch.setattr(store.storage, "data_dir", tmp_path)
    return tmp_path / SETTINGS_FILE


def _ledger_metrics():
    # The owner's example: the 10th ends -10, nothing posts on the 11th, the 12th ends +20.
    ledger = [{"date": "2054-03-10", "ending_balance": -10.0, "source": "reconstructed", "transaction_count": 1},
              {"date": "2054-03-11", "ending_balance": -10.0, "source": "carried", "transaction_count": 0},
              {"date": "2054-03-12", "ending_balance": 20.0, "source": "reconstructed", "transaction_count": 1}]
    return {"negative_days": 2, "negative_printed_days": 1, "effective_nsf_count": 1,
            "nsf_source": "negative_printed_days", "adb": {"daily_balances": ledger}}


# --- the settings file -------------------------------------------------------------------------------------

def test_defaults_to_printed_days_when_nothing_is_saved(tmp_path):
    assert load_settings(tmp_path) == EXPECTED_DEFAULTS == DEFAULTS


@pytest.mark.parametrize("content", ["not json", "[]", '{"nsf_carry_over": "yes"}', '{"nsf_carry_over": 1}'])
def test_a_malformed_file_or_value_reads_as_the_default(tmp_path, content):
    (tmp_path / SETTINGS_FILE).write_text(content, encoding="utf-8")
    assert load_settings(tmp_path) == DEFAULTS


def test_saving_persists_and_leaves_no_temporary_file(tmp_path):
    assert save_settings(tmp_path, {"nsf_carry_over": True}) == CARRY_OVER
    assert load_settings(tmp_path) == CARRY_OVER
    assert sorted(p.name for p in tmp_path.iterdir()) == [SETTINGS_FILE]


@pytest.mark.parametrize("updates", [{}, [], {"surprise": True}, {"nsf_carry_over": "true"}, {"nsf_carry_over": 1}])
def test_a_bad_update_is_refused_and_writes_nothing(tmp_path, updates):
    with pytest.raises(ValueError):
        save_settings(tmp_path, updates)
    assert not (tmp_path / SETTINGS_FILE).exists()


# --- the API -----------------------------------------------------------------------------------------------

def test_the_api_reads_and_saves_the_toggle(settings_file):
    client = app.test_client()
    assert client.get("/api/settings").get_json() == {"settings": EXPECTED_DEFAULTS}
    response = client.post("/api/settings", json={"nsf_carry_over": True})
    assert response.status_code == 200 and response.get_json() == {"settings": CARRY_OVER}
    assert json.loads(settings_file.read_text(encoding="utf-8")) == CARRY_OVER
    assert client.get("/api/settings").get_json() == {"settings": CARRY_OVER}


def test_the_api_refuses_a_form_post_and_unknown_keys_without_echoing_them(settings_file):
    client = app.test_client()
    assert client.post("/api/settings", data={"nsf_carry_over": "true"}).status_code == 400
    response = client.post("/api/settings", json={"<script>": True})
    assert response.status_code == 400 and response.get_json() == {"error": "invalid settings update"}
    assert not settings_file.exists()


# --- the flag-group checkboxes (lender detection §8.1) -------------------------------------------------------

def test_every_flag_group_has_a_checkbox_that_is_on_by_default():
    assert FLAG_SETTING_KEYS == tuple(group.setting for group in FLAG_GROUPS)
    assert set(DEFAULTS) == {"nsf_carry_over", "zelle_true_revenue", *FLAG_SETTING_KEYS}
    assert all(DEFAULTS[key] is True for key in FLAG_SETTING_KEYS)


@pytest.mark.parametrize("key", FLAG_SETTING_KEYS)
@pytest.mark.parametrize("stored", ['"no"', "0", "null"])
def test_a_malformed_checkbox_value_reads_as_shown(tmp_path, key, stored):
    (tmp_path / SETTINGS_FILE).write_text(f'{{"{key}": {stored}}}', encoding="utf-8")
    assert load_settings(tmp_path) == EXPECTED_DEFAULTS


@pytest.mark.parametrize("key", FLAG_SETTING_KEYS)
@pytest.mark.parametrize("value", ["false", 0, None])
def test_a_checkbox_update_that_is_not_a_bool_is_refused_and_writes_nothing(tmp_path, key, value):
    with pytest.raises(ValueError, match=f"setting {key} must be bool"):
        save_settings(tmp_path, {key: value})
    assert not (tmp_path / SETTINGS_FILE).exists()


@pytest.mark.parametrize("key", FLAG_SETTING_KEYS)
def test_the_api_saves_one_checkbox_and_keeps_every_other_setting(settings_file, key):
    client = app.test_client()
    save_settings(settings_file.parent, {"nsf_carry_over": True})
    response = client.post("/api/settings", json={key: False})
    assert response.status_code == 200 and response.get_json() == {"settings": {**CARRY_OVER, key: False}}
    assert json.loads(settings_file.read_text(encoding="utf-8")) == {**CARRY_OVER, key: False}
    assert client.get("/api/settings").get_json() == {"settings": {**CARRY_OVER, key: False}}


# --- the Zelle choice (the owner's amendment of 2026-10-06 to the underwriter's Q3; R2-OW17) ------------------------

def test_the_zelle_choice_is_yes_by_default_and_saved_through_the_api(settings_file):
    client = app.test_client()
    assert client.get("/api/settings").get_json()["settings"]["zelle_true_revenue"] is True
    response = client.post("/api/settings", json={"zelle_true_revenue": False})
    assert response.status_code == 200
    assert response.get_json() == {"settings": {**EXPECTED_DEFAULTS, "zelle_true_revenue": False}}
    assert json.loads(settings_file.read_text(encoding="utf-8"))["zelle_true_revenue"] is False
    assert client.get("/api/settings").get_json()["settings"]["zelle_true_revenue"] is False


@pytest.mark.parametrize("value", ["no", 0, 1, None, "false"])
def test_a_zelle_choice_that_is_not_a_bool_is_refused(settings_file, value):
    response = app.test_client().post("/api/settings", json={"zelle_true_revenue": value})
    assert response.status_code == 400 and response.get_json() == {"error": "invalid settings update"}
    assert not settings_file.exists()


@pytest.mark.parametrize("stored", ['"no"', "0", "null"])
def test_a_malformed_zelle_choice_reads_as_yes(tmp_path, stored):
    (tmp_path / SETTINGS_FILE).write_text(f'{{"zelle_true_revenue": {stored}}}', encoding="utf-8")
    assert load_settings(tmp_path)["zelle_true_revenue"] is True


@pytest.fixture
def zelle_job(monkeypatch):
    from tests import zelle_setting_fixtures as fx

    job = SimpleNamespace(id="job-zelle", status="done", analysis=fx.case("Z1"), analysis_error=None,
                          filename="fabricated.pdf", markdown="", html="", content_sha256="job-zelle")
    original = store.get
    monkeypatch.setattr(store, "get", lambda job_id: job if job_id == job.id else original(job_id))
    return job


def test_the_served_analysis_and_its_exports_follow_the_zelle_choice(settings_file, zelle_job):
    import copy

    stored = copy.deepcopy(zelle_job.analysis)
    client = app.test_client()
    shown = client.get("/analysis/job-zelle").get_json()["analysis"]["metrics"]
    assert shown["true_revenue_total"] == 11534.56 and shown["zelle_deposits"]["counted_as_true_revenue"] is True
    exported = json.loads(client.get("/download/job-zelle/json").data)
    assert exported["metrics"]["true_revenue_total"] == 11534.56
    assert "zelle_counted_reading" not in exported
    client.post("/api/settings", json={"zelle_true_revenue": False})
    shown = client.get("/analysis/job-zelle").get_json()["analysis"]["metrics"]
    assert shown["true_revenue_total"] == 10300.0 and "zelle_deposits" not in shown
    exported = json.loads(client.get("/download/job-zelle/json").data)
    assert exported["metrics"]["true_revenue_total"] == 10300.0 and "zelle_counted_reading" not in exported
    # The stored record is never rewritten by presenting it.
    assert zelle_job.analysis == stored


def test_package_members_follow_the_zelle_choice(settings_file, zelle_job):
    from webapp.app import _package_members
    members, _ = _package_members([zelle_job])
    assert members[0][1]["metrics"]["true_revenue_total"] == 11534.56
    save_settings(store.storage.data_dir, {"zelle_true_revenue": False})
    members, _ = _package_members([zelle_job])
    assert members[0][1]["metrics"]["true_revenue_total"] == 10300.0


# --- every served surface follows the toggle -----------------------------------------------------------------

@pytest.fixture
def done_job(monkeypatch):
    job = SimpleNamespace(id="job-nsf", status="done", analysis={"statement": {}, "metrics": _ledger_metrics()},
                          analysis_error=None, filename="fabricated.pdf", markdown="", html="")
    original = store.get
    monkeypatch.setattr(store, "get", lambda job_id: job if job_id == job.id else original(job_id))
    return job


def test_the_analysis_and_its_exports_follow_the_toggle(settings_file, done_job):
    client = app.test_client()
    shown = client.get("/analysis/job-nsf").get_json()["analysis"]["metrics"]
    assert shown["effective_nsf_count"] == 1 and shown["nsf_source"] == "negative_printed_days"
    client.post("/api/settings", json={"nsf_carry_over": True})
    shown = client.get("/analysis/job-nsf").get_json()["analysis"]["metrics"]
    assert shown["effective_nsf_count"] == 2 and shown["nsf_source"] == "negative_ending_days"
    exported = json.loads(client.get("/download/job-nsf/json").data)
    assert exported["metrics"]["effective_nsf_count"] == 2
    # The stored record is never rewritten by presenting it.
    assert done_job.analysis["metrics"]["effective_nsf_count"] == 1


def test_package_members_carry_the_displayed_basis(settings_file, done_job):
    from webapp.app import _package_members
    members, _ = _package_members([done_job])
    assert members[0][1]["metrics"]["effective_nsf_count"] == 1
    save_settings(store.storage.data_dir, {"nsf_carry_over": True})
    members, _ = _package_members([done_job])
    assert members[0][1]["metrics"]["effective_nsf_count"] == 2


def test_a_save_that_cannot_be_written_is_a_fixed_json_503_and_changes_nothing(settings_file, monkeypatch):
    import webapp.settings as settings_module

    def refuse(source, target):
        raise PermissionError(32, "fabricated sharing violation")
    monkeypatch.setattr(settings_module.os, "replace", refuse)
    monkeypatch.setattr(settings_module.time, "sleep", lambda seconds: None)
    response = app.test_client().post("/api/settings", json={"nsf_carry_over": True})
    assert response.status_code == 503 and response.get_json() == {"error": "settings could not be saved"}
    assert load_settings(settings_file.parent) == DEFAULTS
    assert [p.name for p in settings_file.parent.iterdir()] == []   # the temporary file is cleaned up


def test_a_replace_that_collides_with_a_reader_is_retried(settings_file, monkeypatch):
    import webapp.settings as settings_module
    real_replace, calls = settings_module.os.replace, []

    def flaky(source, target):
        calls.append(target)
        if len(calls) < 3:
            raise PermissionError(32, "fabricated sharing violation")
        real_replace(source, target)
    monkeypatch.setattr(settings_module.os, "replace", flaky)
    monkeypatch.setattr(settings_module.time, "sleep", lambda seconds: None)
    assert save_settings(settings_file.parent, {"nsf_carry_over": True}) == CARRY_OVER
    assert len(calls) == 3 and load_settings(settings_file.parent) == CARRY_OVER


def test_the_package_totals_and_rows_carry_the_basis(settings_file):
    from tests.test_package_currency import statement_payload
    from webapp.app import _package_analysis
    from webapp.jobs import Job

    def member(job_id):
        payload = statement_payload("USD")
        payload["metrics"].update(_ledger_metrics())
        return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload, content_sha256=job_id)

    package = _package_analysis([member("a"), member("b")])
    assert package["totals"]["nsf_count"] == 2 and package["totals"]["nsf_source"] == "negative_printed_days"
    assert {row["nsf_source"] for row in package["documents"]} == {"negative_printed_days"}
    save_settings(settings_file.parent, {"nsf_carry_over": True})
    package = _package_analysis([member("a"), member("b")])
    assert package["totals"]["nsf_count"] == 4 and package["totals"]["nsf_source"] == "negative_ending_days"


def test_a_member_without_analysis_adds_no_basis_to_the_package(settings_file):
    from tests.test_package_currency import statement_payload
    from webapp.app import _package_analysis
    from webapp.jobs import Job

    payload = statement_payload("USD")
    payload["metrics"].update(_ledger_metrics())
    done = Job(id="a", filename="a.pdf", status="done", analysis=payload, content_sha256="a")
    failed = Job(id="b", filename="b.pdf", status="failed", analysis=None, content_sha256="b")
    assert _package_analysis([done, failed])["totals"]["nsf_source"] == "negative_printed_days"
    assert _package_analysis([failed])["totals"]["nsf_source"] is None


def test_a_read_colliding_with_a_save_is_retried_rather_than_read_as_the_default(tmp_path, monkeypatch):
    import webapp.settings as settings_module
    save_settings(tmp_path, {"nsf_carry_over": True})
    real_read, calls = Path.read_text, []

    def busy_once(self, *args, **kwargs):
        calls.append(self)
        if len(calls) == 1:
            raise PermissionError(32, "fabricated sharing violation")
        return real_read(self, *args, **kwargs)
    monkeypatch.setattr(settings_module.Path, "read_text", busy_once)
    monkeypatch.setattr(settings_module.time, "sleep", lambda seconds: None)
    assert load_settings(tmp_path) == CARRY_OVER and len(calls) == 2


# --- the basis on a statement that holds several accounts -----------------------------------------------------------

def _document_member(job_id, roster=None):
    from tests.l1s3_payloads import document_payload
    from webapp.jobs import Job

    payload = document_payload()
    for account in payload["accounts"]:
        account["metrics"].update(_ledger_metrics())
    if roster is not None:
        payload["document"]["account_roster"] = roster
    return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload, content_sha256=job_id)


def _roster(main_status):
    main = {"title": "FABRICATED BUSINESS CHECKING", "kind": "checking", "number_last4": "0010", "status": main_status,
            "published_index": 0 if main_status == "published" else None,
            "balance": 25.0 if main_status == "idle" else None,
            "reasons": ["page_unresolved"] if main_status == "held" else []}
    savings = {"title": "FABRICATED SAVINGS", "kind": "savings", "number_last4": "0001", "status": "published",
               "published_index": 1, "balance": None, "reasons": []}
    return [main, savings]


def test_every_published_account_of_a_document_member_follows_the_basis(settings_file):
    from webapp.app import _package_analysis

    package = _package_analysis([_document_member("a")])
    assert package["totals"]["nsf_source"] == "negative_printed_days" and package["totals"]["nsf_count"] == 2
    save_settings(settings_file.parent, {"nsf_carry_over": True})
    package = _package_analysis([_document_member("a")])
    assert package["totals"]["nsf_source"] == "negative_ending_days" and package["totals"]["nsf_count"] == 4


def test_the_basis_never_changes_which_accounts_a_package_leaves_out(settings_file):
    # The exclusions read the roster off the re-based copy (webapp/app.py::_package_members); the basis rewrites only
    # each account's metrics, so the idle and unverified main-account rules decide the same way on both bases, and
    # the stored records are never rewritten.
    import copy
    from webapp.app import _package_members

    jobs = [_document_member("idle", _roster("idle")), _document_member("held", _roster("held")),
            _document_member("verified", _roster("published")), _document_member("no-roster")]
    stored = [copy.deepcopy(job.analysis) for job in jobs]

    def decided():
        members, excluded = _package_members(jobs)
        return sorted((member[0].id, member[2]) for member in members), excluded

    printed = decided()
    save_settings(settings_file.parent, {"nsf_carry_over": True})
    assert decided() == printed
    assert [item["reason"] for item in printed[1]] == ["main_account_idle", "main_account_unverified"]
    assert [job.analysis for job in jobs] == stored
