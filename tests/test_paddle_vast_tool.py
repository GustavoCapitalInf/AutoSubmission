"""Phase 2.1 cell P: `tools/paddle_vast.py`. Every network-touching function
takes an injectable runner/popen/client, so these tests prove argument
construction and masking without ever opening a socket, an SSH connection,
or reading a real fixture (M12).
"""
from __future__ import annotations

import json
import socket
from dataclasses import dataclass

import pytest

import tools.paddle_vast as vast
from ocr.paddle_config import PADDLE_REMOTE_OPT_IN_ENV, PADDLE_REMOTE_OPT_IN_LITERAL, load_paddle_settings
from tests.paddle_fake_worker import FakeWorker

#: The SAME placeholder connection values `tests/test_paddle_config.py`
#: uses — proving this tool masks the exact fields that module documents as
#: sensitive.
VAST_ENV = {
    "PADDLE_PROVIDER": "vast.ai", "PADDLE_EXECUTION_CLASS": "remote_paid",
    "PADDLE_VAST_HOST": "example-host.invalid", "PADDLE_VAST_SSH_PORT": "22022",
    "PADDLE_VAST_SSH_USER": "someone", PADDLE_REMOTE_OPT_IN_ENV: PADDLE_REMOTE_OPT_IN_LITERAL,
}
FORBIDDEN_TOKENS = ("example-host.invalid", "22022", "someone")


def _settings(**overrides):
    return load_paddle_settings(dict(VAST_ENV, **overrides))


@dataclass
class _FakeCompletedProcess:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class _RunnerLog:
    """Records every call; returns a canned `_FakeCompletedProcess`."""

    def __init__(self, stdout: str = "", returncode: int = 0):
        self.calls: list[list[str]] = []
        self.stdout = stdout
        self.returncode = returncode

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        return _FakeCompletedProcess(returncode=self.returncode, stdout=self.stdout)


# ---------------------------------------------------------------------------
# mask_text / the masking guarantee on every cmd_* return value
# ---------------------------------------------------------------------------

def test_mask_text_replaces_host_user_and_token():
    settings = _settings(PADDLE_WORKER_TOKEN="s3cr3t-token")
    text = json.dumps({"a": settings.vast_host, "b": settings.vast_ssh_user, "c": settings.worker_token})
    masked = vast.mask_text(text, settings)
    assert "example-host.invalid" not in masked
    assert "someone" not in masked
    assert "s3cr3t-token" not in masked
    assert vast.HOST_PLACEHOLDER in masked


def test_cmd_check_masks_gpu_output_and_records_real_args():
    settings = _settings()
    runner = _RunnerLog(stdout="NVIDIA GeForce RTX FAKE, 8192 MiB, 000.00.0\n")
    result = vast.cmd_check(settings, runner=runner)
    text = json.dumps(result)
    for forbidden in FORBIDDEN_TOKENS:
        assert forbidden not in text
    # the real values WERE used to build the ssh command (that's correct —
    # only the tool's returned/printed output is masked, never the transport).
    assert any("example-host.invalid" in " ".join(call) for call in runner.calls)
    assert any("someone" in " ".join(call) for call in runner.calls)


def test_major3_a_timing_out_runner_never_leaks_the_command_line():
    """MAJOR-3 (PHASE2_P21PADDLE_REVIEW.md): `subprocess.TimeoutExpired.__str__`
    embeds the full command — host, port, user. Every `runner(...)` call
    site goes through `_run`, which converts `subprocess.SubprocessError` /
    `OSError` into a `PaddleVastError` carrying ONLY the exception class
    name, so this can never reach an operator's terminal or log."""
    import subprocess

    def timing_out_runner(args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=list(args), timeout=kwargs.get("timeout", 30))

    settings = _settings()
    with pytest.raises(vast.PaddleVastError) as excinfo:
        vast.cmd_check(settings, runner=timing_out_runner)
    text = str(excinfo.value)
    assert text == "TimeoutExpired"
    for forbidden in FORBIDDEN_TOKENS:
        assert forbidden not in text


def test_major3_main_masks_a_subprocess_error_that_escapes_a_cmd_function(monkeypatch):
    """Belt-and-suspenders: `main()`'s own except tuple also catches a bare
    `subprocess.SubprocessError` / `OSError` (never expected to fire given
    `_run` / `_popen`, but proven anyway) and masks it the same way."""
    import subprocess

    monkeypatch.setenv("PADDLE_PROVIDER", VAST_ENV["PADDLE_PROVIDER"])
    monkeypatch.setenv("PADDLE_EXECUTION_CLASS", VAST_ENV["PADDLE_EXECUTION_CLASS"])
    monkeypatch.setenv("PADDLE_VAST_HOST", VAST_ENV["PADDLE_VAST_HOST"])
    monkeypatch.setenv("PADDLE_VAST_SSH_PORT", VAST_ENV["PADDLE_VAST_SSH_PORT"])
    monkeypatch.setenv("PADDLE_VAST_SSH_USER", VAST_ENV["PADDLE_VAST_SSH_USER"])

    def boom(settings):
        raise subprocess.SubprocessError("would have embedded the command line here")

    monkeypatch.setattr(vast, "cmd_check", boom)
    exit_code = vast.main(["check"])
    assert exit_code == 1


def test_cmd_check_local_provider_makes_no_ssh_call():
    settings = load_paddle_settings({"PADDLE_PROVIDER": "local", "PADDLE_EXECUTION_CLASS": "local_free"})
    runner = _RunnerLog()
    result = vast.cmd_check(settings, runner=runner)
    assert runner.calls == []
    assert result["provider"] == "local"


def test_cmd_deploy_copies_only_paddle_worker_py_and_masks_output(tmp_path):
    settings = _settings()
    fake_local = tmp_path / "paddle_worker.py"
    fake_local.write_text("# stand-in", encoding="utf-8")
    runner = _RunnerLog(stdout=json.dumps({"contract": 1}))
    result = vast.cmd_deploy(settings, runner=runner, local_worker_path=str(fake_local))
    text = json.dumps(result)
    for forbidden in FORBIDDEN_TOKENS:
        assert forbidden not in text
    scp_calls = [call for call in runner.calls if call[0] == "scp"]
    assert len(scp_calls) == 1
    assert scp_calls[0][-1].endswith(f":{vast.REMOTE_WORKER_PATH}")
    assert str(fake_local) in scp_calls[0]
    # No other repository file appears in any deploy command.
    for call in runner.calls:
        joined = " ".join(call)
        assert "evidence" not in joined
        assert "canonical.py" not in joined


def test_cmd_start_generates_a_token_never_returned_and_masks_output(tmp_path):
    settings = _settings(PADDLE_RUNTIME_DIR=str(tmp_path))
    runner = _RunnerLog()
    result = vast.cmd_start(settings, runner=runner, token="s3cr3t-token")
    text = json.dumps(result)
    assert "s3cr3t-token" not in text
    for forbidden in FORBIDDEN_TOKENS:
        assert forbidden not in text
    token_file = tmp_path / "worker.token"
    assert token_file.read_text(encoding="utf-8") == "s3cr3t-token"
    assert any("PADDLE_WORKER_TOKEN=s3cr3t-token" in " ".join(call) for call in runner.calls)


def test_cmd_start_uses_a_random_token_when_none_supplied(tmp_path):
    settings = _settings(PADDLE_RUNTIME_DIR=str(tmp_path))
    runner = _RunnerLog()
    vast.cmd_start(settings, runner=runner)
    token_file = tmp_path / "worker.token"
    assert token_file.exists() and len(token_file.read_text(encoding="utf-8")) > 20


def test_major4_cmd_start_reuses_settings_worker_token_instead_of_minting_a_new_one(tmp_path):
    """MAJOR-4 (PHASE2_P21PADDLE_REVIEW.md): when `settings.worker_token` is
    already set (here, because `ocr.paddle_config.load_paddle_settings`
    fell back to reading `<runtime_dir>/worker.token` on a prior session),
    `cmd_start` must reuse it rather than mint a fresh one and orphan any
    client already configured with the old value."""
    token_path = tmp_path / "worker.token"
    token_path.write_text("existing-session-token", encoding="utf-8")
    settings = load_paddle_settings(dict(VAST_ENV, PADDLE_RUNTIME_DIR=str(tmp_path)))
    assert settings.worker_token == "existing-session-token"  # the config-layer fallback (MAJOR-4)

    runner = _RunnerLog()
    vast.cmd_start(settings, runner=runner)
    assert token_path.read_text(encoding="utf-8") == "existing-session-token"
    assert any("PADDLE_WORKER_TOKEN=existing-session-token" in " ".join(call) for call in runner.calls)


def test_major4_lifecycle_round_trip_authenticates_without_a_manual_export(tmp_path):
    """The end-to-end MAJOR-4 claim: `start` (writing a token) followed by a
    FRESH `load_paddle_settings()` call (as `status` / the live test /
    `measure` each make, with no token passed explicitly and no manual
    `export PADDLE_WORKER_TOKEN=...` step) authenticates correctly against a
    worker started with that same token."""
    from ocr.paddle_client import PaddleClient

    runtime_dir = str(tmp_path)
    start_settings = load_paddle_settings(dict(VAST_ENV, PADDLE_RUNTIME_DIR=runtime_dir))
    assert start_settings.worker_token is None  # nothing on file yet
    vast.cmd_start(start_settings, runner=_RunnerLog())  # writes <runtime_dir>/worker.token

    minted_token = (tmp_path / "worker.token").read_text(encoding="utf-8")
    with FakeWorker(token=minted_token) as fake:
        # A SEPARATE, later settings resolution — exactly what `status`,
        # `tests/test_paddle_live.py` and `measure` each do independently —
        # with no token passed and no environment export.
        later_settings = load_paddle_settings(
            dict(VAST_ENV, PADDLE_RUNTIME_DIR=runtime_dir, PADDLE_WORKER_URL=fake.url)
        )
        assert later_settings.worker_token == minted_token
        client = PaddleClient(later_settings, environ=VAST_ENV)
        assert client.health() == {"ok": True, "contract": 1}


def test_cmd_stop_masks_and_builds_the_remote_kill_command():
    settings = _settings()
    runner = _RunnerLog(stdout="stopped")
    result = vast.cmd_stop(settings, runner=runner)
    assert result["remote_output"] == "stopped"
    assert any(vast.REMOTE_PID_PATH in " ".join(call) for call in runner.calls)


# ---------------------------------------------------------------------------
# tunnel-up / tunnel-down
# ---------------------------------------------------------------------------

def test_tunnel_up_refuses_when_the_local_port_is_already_listening(tmp_path):
    settings = _settings(PADDLE_RUNTIME_DIR=str(tmp_path))
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        busy_port = server.getsockname()[1]
        busy_settings = _settings(PADDLE_RUNTIME_DIR=str(tmp_path), PADDLE_TUNNEL_LOCAL_PORT=str(busy_port))
        with pytest.raises(vast.PaddleVastError):
            vast.cmd_tunnel_up(busy_settings, popen=lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not launch")))
    finally:
        server.close()


class _FakePopen:
    def __init__(self, *args, **kwargs):
        self.pid = 424242
        self.args = args


def test_tunnel_up_records_a_pidfile_and_tunnel_down_removes_it(tmp_path):
    settings = _settings(PADDLE_RUNTIME_DIR=str(tmp_path))
    result = vast.cmd_tunnel_up(settings, popen=_FakePopen)
    assert result["pid"] == 424242
    pid_file = tmp_path / "tunnel.pid"
    assert pid_file.read_text(encoding="utf-8") == "424242"

    down = vast.cmd_tunnel_down(settings)
    assert down["stopped"] is True
    assert not pid_file.exists()


def test_tunnel_down_with_no_pidfile_reports_not_stopped(tmp_path):
    settings = _settings(PADDLE_RUNTIME_DIR=str(tmp_path))
    result = vast.cmd_tunnel_down(settings)
    assert result == {"stopped": False, "reason": "no tunnel.pid"}


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def test_status_reports_masked_settings_and_probe(tmp_path):
    settings = _settings(PADDLE_RUNTIME_DIR=str(tmp_path))
    with FakeWorker() as fake:
        settings_with_worker = _settings(PADDLE_RUNTIME_DIR=str(tmp_path), PADDLE_WORKER_URL=fake.url)
        result = vast.cmd_status(settings_with_worker, environ=VAST_ENV)
        text = json.dumps(result)
        for forbidden in FORBIDDEN_TOKENS:
            assert forbidden not in text
        assert result["probe"]["available"] is True


# ---------------------------------------------------------------------------
# measure — M12 (refuses a real-data fixture path) and end-to-end shape
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_path", [
    "Bank Statements/foo.pdf",
    "tests/corpus_cache/x.pdf",
    r"tests\corpus_cache\x.pdf",
    "discovery_reports/run/x.pdf",
    "/abs/path/Bank Statements/foo.pdf",
])
def test_m12_measure_refuses_a_real_data_fixture_path(bad_path):
    settings = _settings()
    with pytest.raises(vast.PaddleVastError):
        vast.cmd_measure(settings, fixture_path=bad_path)


@pytest.mark.parametrize("bad_path", [
    "bank statements/foo.pdf",           # MINOR-3: case-insensitive now
    "BANK STATEMENTS/foo.pdf",
    "Tests/Corpus_Cache/x.pdf",
    r"tests\Corpus_Cache\x.pdf",
])
def test_minor3_fixture_refusal_is_case_insensitive(bad_path):
    with pytest.raises(vast.PaddleVastError):
        vast._refuse_forbidden_fixture(bad_path)


def test_minor3_fixture_refusal_catches_a_resolved_path_walking_in(tmp_path, monkeypatch):
    """A path whose LITERAL string names none of `FORBIDDEN_FIXTURE_SUBSTRINGS`
    (so the substring check alone would accept it) but whose `.resolve()`
    lands inside a forbidden directory — a symlink or an unusually-spelled
    `..` walk in practice — is refused by the SEPARATE resolved-path check.
    Isolated from the real filesystem via `_FORBIDDEN_FIXTURE_DIRS` so the
    test does not depend on being able to create a symlink on this host."""
    innocuous = tmp_path / "innocuous-name.pdf"
    innocuous.write_bytes(b"")
    fake_forbidden = str(tmp_path).replace("\\", "/").casefold()
    monkeypatch.setattr(vast, "_FORBIDDEN_FIXTURE_DIRS", (fake_forbidden,))

    for forbidden in vast.FORBIDDEN_FIXTURE_SUBSTRINGS:
        assert forbidden.casefold() not in str(innocuous).casefold()  # the substring check sees nothing
    with pytest.raises(vast.PaddleVastError, match="resolving inside"):
        vast._refuse_forbidden_fixture(str(innocuous))


def test_minor3_fixture_flag_never_read_only_shape_checked():
    """`--fixture` exists ONLY so an operator can reach the refusal from the
    CLI; a path that does NOT resolve to a forbidden directory is accepted
    by the guard and never opened (measure still builds its own synthetic
    page in memory regardless)."""
    assert vast._refuse_forbidden_fixture(None) is None  # no flag given: no-op
    harmless = "not-a-real-file-anyone-would-have.pdf"
    vast._refuse_forbidden_fixture(harmless)  # does not raise: not a forbidden shape; never opened


def test_minor3_main_wires_fixture_flag_to_cmd_measure(monkeypatch):
    """The `--fixture` CLI flag reaches `cmd_measure`'s `fixture_path`
    parameter — M12's killer exercises a parameter an operator can actually
    supply, not one only a direct Python call could reach."""
    monkeypatch.setenv("PADDLE_PROVIDER", VAST_ENV["PADDLE_PROVIDER"])
    monkeypatch.setenv("PADDLE_EXECUTION_CLASS", VAST_ENV["PADDLE_EXECUTION_CLASS"])
    monkeypatch.setenv("PADDLE_VAST_HOST", VAST_ENV["PADDLE_VAST_HOST"])
    monkeypatch.setenv("PADDLE_VAST_SSH_PORT", VAST_ENV["PADDLE_VAST_SSH_PORT"])
    monkeypatch.setenv("PADDLE_VAST_SSH_USER", VAST_ENV["PADDLE_VAST_SSH_USER"])

    seen = {}

    def fake_measure(settings, **kwargs):
        seen.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(vast, "cmd_measure", fake_measure)
    exit_code = vast.main(["measure", "--fixture", "Bank Statements/x.pdf"])
    assert exit_code == 0
    assert seen["fixture_path"] == "Bank Statements/x.pdf"


def test_measure_end_to_end_against_the_fake_worker(tmp_path):
    from ocr.paddle_client import PaddleClient
    from tests.paddle_synthetic import build_ledger_page, synthetic_paddle_result

    page = build_ledger_page(n_rows=2)

    with FakeWorker(result_for=lambda idx, img: synthetic_paddle_result(page, dpi=150)) as fake:
        settings = _settings(PADDLE_RUNTIME_DIR=str(tmp_path), PADDLE_WORKER_URL=fake.url)
        client = PaddleClient(settings, environ=VAST_ENV)
        # `gpu_sampler=lambda: None`: this test is about the wire-format and
        # file-write behaviour, not the SSH-based GPU sampler (a dedicated
        # test below proves that one against a fake runner) — the real
        # default would otherwise spawn an actual `ssh` process against the
        # placeholder host.
        report = vast.cmd_measure(settings, client=client, n_rows=2, warm_requests=3, dpi=150,
                                  environ=VAST_ENV, gpu_sampler=lambda: None)

    assert report["cold"]["end_to_end_ms"] >= 0
    assert report["warm"]["n"] == 3
    assert report["cost"] == "rate not measured"
    assert report["bytes_sent_raw_png_per_page"] > 0
    assert report["bytes_sent_wire_per_page"] > report["bytes_sent_raw_png_per_page"]
    text = json.dumps(report)
    for forbidden in FORBIDDEN_TOKENS:
        assert forbidden not in text

    written = list(tmp_path.glob("measure-*.json"))
    assert len(written) == 1


def test_measure_computes_cost_when_hourly_rate_given(tmp_path):
    from ocr.paddle_client import PaddleClient
    from tests.paddle_synthetic import build_ledger_page, synthetic_paddle_result

    page = build_ledger_page(n_rows=1)
    with FakeWorker(result_for=lambda idx, img: synthetic_paddle_result(page, dpi=150)) as fake:
        settings = _settings(PADDLE_RUNTIME_DIR=str(tmp_path), PADDLE_WORKER_URL=fake.url)
        client = PaddleClient(settings, environ=VAST_ENV)
        report = vast.cmd_measure(settings, client=client, n_rows=1, warm_requests=1, dpi=150, hourly_rate=1.0,
                                  environ=VAST_ENV, gpu_sampler=lambda: None)
    assert isinstance(report["cost"], float)


def test_forbidden_fixture_substrings_cover_the_documented_directories():
    assert "Bank Statements" in vast.FORBIDDEN_FIXTURE_SUBSTRINGS
    assert "discovery_reports" in vast.FORBIDDEN_FIXTURE_SUBSTRINGS


def test_minor7_env_example_never_pre_enables_the_remote_opt_in():
    """MINOR-7 (PHASE2_P21PADDLE_REVIEW.md): the tracked `.env.paddle.example`
    must carry NEITHER opt-in literal uncommented — a hostile regression
    test over the tracked file's own text, not a description of intent."""
    from ocr.paddle_config import PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL, PADDLE_REMOTE_OPT_IN_LITERAL

    example_path = vast._REPO_ROOT / ".env.paddle.example"
    lines = example_path.read_text(encoding="utf-8").splitlines()
    for literal in (PADDLE_REMOTE_OPT_IN_LITERAL, PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL):
        active_lines = [
            line for line in lines
            if literal in line and not line.lstrip().startswith("#")
        ]
        assert active_lines == [], f"{literal} is uncommented in .env.paddle.example: {active_lines}"


# ---------------------------------------------------------------------------
# MINOR-8: the GPU sampler and local peak RSS are real committed instruments
# ---------------------------------------------------------------------------

def test_minor8_default_gpu_sampler_parses_a_real_nvidia_smi_shaped_line():
    settings = _settings()
    runner = _RunnerLog(stdout="7692, 32607, 0\n")
    sampler = vast._default_gpu_sampler(settings, runner)
    sample = sampler()
    assert sample == {"memory_used_mib": 7692, "memory_total_mib": 32607, "utilization_percent": 0}
    assert any("nvidia-smi" in " ".join(call) for call in runner.calls)


def test_minor8_default_gpu_sampler_returns_none_for_local_provider():
    settings = load_paddle_settings({"PADDLE_PROVIDER": "local", "PADDLE_EXECUTION_CLASS": "local_free"})
    runner = _RunnerLog()
    sampler = vast._default_gpu_sampler(settings, runner)
    assert sampler() is None
    assert runner.calls == []


def test_minor8_default_gpu_sampler_returns_none_on_failure_never_a_guess():
    settings = _settings()

    def failing_runner(args, **kwargs):
        raise OSError("ssh not found")

    sampler = vast._default_gpu_sampler(settings, failing_runner)
    assert sampler() is None


def test_minor8_measure_wires_the_default_gpu_sampler_and_polls_it(tmp_path):
    """A plain `cmd_measure` call (no explicit `gpu_sampler=`) uses
    `_default_gpu_sampler` and polls it — the report's `gpu` block reproduces
    from that committed instrument, not a hand-collected number."""
    from ocr.paddle_client import PaddleClient
    from tests.paddle_synthetic import build_ledger_page, synthetic_paddle_result

    page = build_ledger_page(n_rows=1)
    runner = _RunnerLog(stdout="1000, 32607, 5\n")
    with FakeWorker(result_for=lambda idx, img: synthetic_paddle_result(page, dpi=150)) as fake:
        settings = _settings(PADDLE_RUNTIME_DIR=str(tmp_path), PADDLE_WORKER_URL=fake.url)
        client = PaddleClient(settings, environ=VAST_ENV)
        report = vast.cmd_measure(settings, client=client, runner=runner, n_rows=1, warm_requests=2, dpi=150,
                                  environ=VAST_ENV, gpu_sample_every=1)
    assert report["gpu"]["last"] == {"memory_used_mib": 1000, "memory_total_mib": 32607, "utilization_percent": 5}
    assert report["gpu"]["peak_memory_used_mib"] == 1000
    assert report["gpu"]["samples_taken"] >= 1


def test_minor8_local_peak_rss_never_guesses():
    result = vast._peak_local_rss_mib()
    assert isinstance(result, (float, int)) or (isinstance(result, str) and "not measured" in result)


def test_minor8_measure_report_carries_local_peak_rss(tmp_path):
    from ocr.paddle_client import PaddleClient
    from tests.paddle_synthetic import build_ledger_page, synthetic_paddle_result

    page = build_ledger_page(n_rows=1)
    with FakeWorker(result_for=lambda idx, img: synthetic_paddle_result(page, dpi=150)) as fake:
        settings = _settings(PADDLE_RUNTIME_DIR=str(tmp_path), PADDLE_WORKER_URL=fake.url)
        client = PaddleClient(settings, environ=VAST_ENV)
        report = vast.cmd_measure(settings, client=client, n_rows=1, warm_requests=1, dpi=150,
                                  environ=VAST_ENV, gpu_sampler=lambda: None)
    assert "local_peak_rss_mib" in report
