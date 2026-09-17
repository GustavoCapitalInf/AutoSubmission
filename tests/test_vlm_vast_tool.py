import json
from types import SimpleNamespace

import pytest

from tools import vlm_vast


class Proc:
    def __init__(self, stdout="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, "", returncode


def _settings(tmp_path):
    return SimpleNamespace(provider="vast.ai", execution_class="remote_paid", vast_host="203.0.113.9", vast_ssh_port=2222,
                           vast_ssh_user="root", runtime_dir=str(tmp_path / "rt"), worker_token=None,
                           tunnel_local_port=18765, worker_port=8765)


def test_serve_command_pins_flags_and_loopback():
    cmd = vlm_vast.serve_command("b")
    assert "--host 127.0.0.1" in cmd and "--port 18002" in cmd and "Qwen__Qwen3.5-4B" in cmd
    assert "--served-model-name Qwen/Qwen3.5-4B" in cmd
    assert "--max-num-seqs 4" in cmd and "--structured-outputs-config.backend xgrammar" in cmd and "--speculative-config" not in cmd
    a = vlm_vast.serve_command("a")
    assert "--served-model-name PaddleOCR-VL-1.6-0.9B" in a and "--trust-remote-code" in a and "--port 18001" in a


def test_fetch_refuses_when_disk_is_short(tmp_path):
    def runner(args, **kwargs):
        return Proc(stdout="3\n")  # df reports 3 GB free
    with pytest.raises(vlm_vast.PaddleVastError) as exc:
        vlm_vast.cmd_fetch(_settings(tmp_path), "b", runner=runner)
    assert "disk_insufficient" in str(exc.value)


def test_check_masks_host(tmp_path):
    def runner(args, **kwargs):
        text = " ".join(args)
        if "df " in text:
            return Proc("21\n")
        if "nvidia-smi" in text:
            return Proc("NVIDIA GeForce RTX 5090, 32607 MiB, 580.173.02\n")
        if "ss -ltn" in text:
            return Proc("")
        return Proc("vllm 0.29.0\ntorch 2.13.0+cu130\n")
    out = vlm_vast.cmd_check(_settings(tmp_path), runner=runner)
    assert out["disk_free_gb"] == 21 and "5090" in out["gpu"]
    assert "203.0.113.9" not in json.dumps(out)


def test_tunnel_command_forwards_three_ports(tmp_path):
    cmd = vlm_vast.tunnel_command(_settings(tmp_path))
    forwards = [cmd[i + 1] for i, part in enumerate(cmd) if part == "-L"]
    assert forwards == ["127.0.0.1:18001:127.0.0.1:18001", "127.0.0.1:18002:127.0.0.1:18002", "127.0.0.1:18003:127.0.0.1:18003"]
    assert "-N" in cmd and "BatchMode=yes" in " ".join(cmd)


def test_attest_parses_counts(tmp_path):
    def runner(args, **kwargs):
        return Proc("SERVER_PROCESSES=0\nNEW_FILES=0\nTMP_IMAGES=0\n")
    att = vlm_vast.cmd_attest(_settings(tmp_path), runner=runner, since_epoch=0.0)
    assert att["passed"] is True and att["counts"] == {"SERVER_PROCESSES": 0, "NEW_FILES": 0, "TMP_IMAGES": 0}

    def bad(args, **kwargs):
        return Proc("SERVER_PROCESSES=1\nNEW_FILES=0\nTMP_IMAGES=2\n")
    assert vlm_vast.cmd_attest(_settings(tmp_path), runner=bad, since_epoch=0.0)["passed"] is False


def test_start_worker_uses_token_and_never_prints_it(tmp_path):
    seen = []

    def runner(args, **kwargs):
        seen.append(" ".join(args))
        return Proc("4242\n")
    settings = _settings(tmp_path)
    out = vlm_vast.cmd_start(settings, "worker", runner=runner)
    token = (tmp_path / "rt" / "vlm_worker.token").read_text(encoding="utf-8").strip()
    assert token and f"VLM_A_WORKER_TOKEN={token}" in seen[-1]
    assert out == {"started": "worker", "remote_pid": "4242", "port": 18003} and token not in json.dumps(out)
