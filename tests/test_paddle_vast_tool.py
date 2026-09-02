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
    runner = _RunnerLog(stdout="NVIDIA GeForce RTX 5090, 32607 MiB, 580.173.02\n")
    result = vast.cmd_check(settings, runner=runner)
    text = json.dumps(result)
    for forbidden in FORBIDDEN_TOKENS:
        assert forbidden not in text
    # the real values WERE used to build the ssh command (that's correct —
    # only the tool's returned/printed output is masked, never the transport).
    assert any("example-host.invalid" in " ".join(call) for call in runner.calls)
    assert any("someone" in " ".join(call) for call in runner.calls)


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
        result = vast.cmd_status(settings_with_worker)
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


def test_measure_end_to_end_against_the_fake_worker(tmp_path):
    from ocr.paddle_client import PaddleClient
    from tests.paddle_synthetic import build_ledger_page, synthetic_paddle_result

    page = build_ledger_page(n_rows=2)

    with FakeWorker(result_for=lambda idx, img: synthetic_paddle_result(page, dpi=150)) as fake:
        settings = _settings(PADDLE_RUNTIME_DIR=str(tmp_path), PADDLE_WORKER_URL=fake.url)
        client = PaddleClient(settings)
        report = vast.cmd_measure(settings, client=client, n_rows=2, warm_requests=3, dpi=150)

    assert report["cold"]["end_to_end_ms"] >= 0
    assert report["warm"]["n"] == 3
    assert report["cost"] == "rate not measured"
    assert report["bytes_sent_per_page"] > 0
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
        client = PaddleClient(settings)
        report = vast.cmd_measure(settings, client=client, n_rows=1, warm_requests=1, dpi=150, hourly_rate=1.0)
    assert isinstance(report["cost"], float)


def test_forbidden_fixture_substrings_cover_the_documented_directories():
    assert "Bank Statements" in vast.FORBIDDEN_FIXTURE_SUBSTRINGS
    assert "discovery_reports" in vast.FORBIDDEN_FIXTURE_SUBSTRINGS
