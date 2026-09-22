"""The Settings page's NSF basis toggle (owner ruling, 2026-09-22). Fabricated payloads only."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from webapp.app import app, store
from webapp.settings import DEFAULTS, SETTINGS_FILE, load_settings, save_settings


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
    assert load_settings(tmp_path) == {"nsf_carry_over": False} == DEFAULTS


@pytest.mark.parametrize("content", ["not json", "[]", '{"nsf_carry_over": "yes"}', '{"nsf_carry_over": 1}'])
def test_a_malformed_file_or_value_reads_as_the_default(tmp_path, content):
    (tmp_path / SETTINGS_FILE).write_text(content, encoding="utf-8")
    assert load_settings(tmp_path) == DEFAULTS


def test_saving_persists_and_leaves_no_temporary_file(tmp_path):
    assert save_settings(tmp_path, {"nsf_carry_over": True}) == {"nsf_carry_over": True}
    assert load_settings(tmp_path) == {"nsf_carry_over": True}
    assert sorted(p.name for p in tmp_path.iterdir()) == [SETTINGS_FILE]


@pytest.mark.parametrize("updates", [{}, [], {"surprise": True}, {"nsf_carry_over": "true"}, {"nsf_carry_over": 1}])
def test_a_bad_update_is_refused_and_writes_nothing(tmp_path, updates):
    with pytest.raises(ValueError):
        save_settings(tmp_path, updates)
    assert not (tmp_path / SETTINGS_FILE).exists()


# --- the API -----------------------------------------------------------------------------------------------

def test_the_api_reads_and_saves_the_toggle(settings_file):
    client = app.test_client()
    assert client.get("/api/settings").get_json() == {"settings": {"nsf_carry_over": False}}
    response = client.post("/api/settings", json={"nsf_carry_over": True})
    assert response.status_code == 200 and response.get_json() == {"settings": {"nsf_carry_over": True}}
    assert json.loads(settings_file.read_text(encoding="utf-8")) == {"nsf_carry_over": True}
    assert client.get("/api/settings").get_json() == {"settings": {"nsf_carry_over": True}}


def test_the_api_refuses_a_form_post_and_unknown_keys_without_echoing_them(settings_file):
    client = app.test_client()
    assert client.post("/api/settings", data={"nsf_carry_over": "true"}).status_code == 400
    response = client.post("/api/settings", json={"<script>": True})
    assert response.status_code == 400 and response.get_json() == {"error": "invalid settings update"}
    assert not settings_file.exists()


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
    assert save_settings(settings_file.parent, {"nsf_carry_over": True}) == {"nsf_carry_over": True}
    assert len(calls) == 3 and load_settings(settings_file.parent) == {"nsf_carry_over": True}


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
    assert load_settings(tmp_path) == {"nsf_carry_over": True} and len(calls) == 2
