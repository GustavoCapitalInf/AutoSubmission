"""Checkpoints copied off the instance: only finished saves, verified by size and sha256, previous copies kept."""
import hashlib
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


class FakeHost:
    """A run directory on a pretend instance: ssh listings and sha256sum answer from `dirs`, scp copies bytes."""

    def __init__(self, dirs):
        self.dirs = dirs          # {name: {file: bytes}}
        self.copies = []
        self.corrupt = set()

    def runner(self, args, **kwargs):
        text = _decoded(args)
        if args[0] == "scp":
            remote, local = args[-2], args[-1]
            _, path = remote.split(":", 1)
            name, fname = path.rsplit("/", 2)[-2:]
            data = self.dirs[name][fname]
            if fname in self.corrupt:
                data = data[:-1]
            with open(local, "wb") as fh:
                fh.write(data)
            self.copies.append((name, fname))
            return Proc()
        if "for d in adapter-*" in text:
            lines = []
            for name, files in sorted(self.dirs.items()):
                lines.append(f"DIR {name}")
                lines += [f"F {len(data)} {fname}" for fname, data in sorted(files.items())]
            return Proc(stdout="\n".join(lines) + "\n")
        if "sha256sum *" in text:
            name = text.split("cd '")[1].split("'")[0].rsplit("/", 1)[-1]
            return Proc(stdout="".join(f"{hashlib.sha256(data).hexdigest()}  {fname}\n" for fname, data in sorted(self.dirs[name].items())))
        return Proc()


def _decoded(args):
    """The remote command with any base64-carried script expanded, so the fake host can match on its text."""
    import base64

    text = " ".join(args)
    if " | base64 -d | bash" in text:
        payload = text.split("echo ", 1)[1].split(" | base64 -d | bash", 1)[0]
        text = base64.b64decode(payload).decode("utf-8")
    return text


def _checkpoint(step, *, full=True):
    files = {"adapter_model.safetensors": b"W" * 1000 + bytes([step % 251]), "adapter_config.json": b'{"r": 32}',
             "README.md": b"card", "training_state.json": json.dumps({"step": step, "seen": 16 * step, "skipped_long": 3,
                                                                       "hyperparameters": {"rank": 32}}).encode()}
    if full:
        files["optimizer.pt"] = b"O" * 500
        files["rng.pt"] = b"R" * 40
    return files


def test_pull_refuses_unfinished_or_still_changing_saves(tmp_path):
    host = FakeHost({"adapter-step-00100": {k: v for k, v in _checkpoint(100).items() if k != "training_state.json"}})
    with pytest.raises(vlm_vast.PaddleVastError) as exc:
        vlm_vast.cmd_pull_adapter(_settings(tmp_path), "adapter-step-00100", local_root=tmp_path / "bk", runner=host.runner, sleeper=lambda s: None)
    assert "checkpoint_incomplete" in str(exc.value)
    with pytest.raises(vlm_vast.PaddleVastError) as exc:
        vlm_vast.cmd_pull_adapter(_settings(tmp_path), "adapter-step-00200", local_root=tmp_path / "bk", runner=host.runner, sleeper=lambda s: None)
    assert "checkpoint_missing" in str(exc.value)
    growing = FakeHost({"adapter-step-00100": _checkpoint(100)})

    def grow(seconds):
        growing.dirs["adapter-step-00100"]["adapter_model.safetensors"] += b"more"
    with pytest.raises(vlm_vast.PaddleVastError) as exc:
        vlm_vast.cmd_pull_adapter(_settings(tmp_path), "adapter-step-00100", local_root=tmp_path / "bk", runner=growing.runner, sleeper=grow)
    assert "checkpoint_unsettled" in str(exc.value)
    assert not list((tmp_path / "bk").glob("**/pull-receipt.json"))


def test_pull_verifies_every_file_and_keeps_previous_verified_copies(tmp_path):
    host = FakeHost({"adapter-step-00100": _checkpoint(100), "adapter-step-00200": _checkpoint(200, full=False)})
    out = vlm_vast.cmd_pull_adapter(_settings(tmp_path), "adapter-step-00100", local_root=tmp_path / "bk", runner=host.runner, sleeper=lambda s: None)
    local = tmp_path / "bk" / "lora-01" / "adapter-step-00100"
    assert out["status"] == "pulled" and out["step"] == 100 and out["full_state"] is True and local.is_dir()
    receipt = json.loads((local / "pull-receipt.json").read_text(encoding="utf-8"))
    assert receipt["verified"] is True and set(receipt["files"]) == set(_checkpoint(100))
    assert receipt["files"]["adapter_model.safetensors"]["sha256"] == hashlib.sha256(_checkpoint(100)["adapter_model.safetensors"]).hexdigest()
    assert receipt["files"]["optimizer.pt"]["bytes"] == 500 and receipt["hyperparameters"] == {"rank": 32}
    # a second pull of the same checkpoint is a no-op: the verified copy is kept, nothing is copied again
    before = list(host.copies)
    again = vlm_vast.cmd_pull_adapter(_settings(tmp_path), "adapter-step-00100", local_root=tmp_path / "bk", runner=host.runner, sleeper=lambda s: None)
    assert again["status"] == "already_verified" and host.copies == before
    # a weights-only checkpoint says so
    second = vlm_vast.cmd_pull_adapter(_settings(tmp_path), "adapter-step-00200", local_root=tmp_path / "bk", runner=host.runner, sleeper=lambda s: None)
    assert second["full_state"] is False and "weights-only" in second["resume_note"]
    assert sorted(p.name for p in (tmp_path / "bk" / "lora-01").iterdir()) == ["adapter-step-00100", "adapter-step-00200"]


def test_pull_leaves_no_verified_receipt_when_a_transfer_is_short(tmp_path):
    host = FakeHost({"adapter-final": _checkpoint(400)})
    host.corrupt.add("adapter_model.safetensors")
    with pytest.raises(vlm_vast.PaddleVastError) as exc:
        vlm_vast.cmd_pull_adapter(_settings(tmp_path), "adapter-final", local_root=tmp_path / "bk", runner=host.runner, sleeper=lambda s: None)
    assert "pull_size_mismatch" in str(exc.value)
    assert not (tmp_path / "bk" / "lora-01" / "adapter-final").exists()
    assert vlm_vast.local_verified(tmp_path / "bk" / "lora-01" / "adapter-final") is None
    leftovers = list((tmp_path / "bk" / "lora-01").glob("adapter-final.incoming-*"))
    assert len(leftovers) == 1 and not (leftovers[0] / "pull-receipt.json").exists()


def test_watch_pulls_each_finished_checkpoint_as_it_appears_and_stops_after_the_final(tmp_path):
    host = FakeHost({})
    events = []
    ticks = {"n": 0}

    def sleeper(seconds):
        ticks["n"] += 1
        if ticks["n"] == 1:
            host.dirs["adapter-step-00100"] = _checkpoint(100)
            host.dirs["adapter-step-00200"] = {k: v for k, v in _checkpoint(200).items() if k != "training_state.json"}  # still saving
        elif ticks["n"] == 2:
            host.dirs["adapter-step-00200"]["training_state.json"] = _checkpoint(200)["training_state.json"]
            host.dirs["adapter-final"] = _checkpoint(400)

    def runner(args, **kwargs):
        text = _decoded(args)
        if "train-receipt-" in text and "ls -1" in text:
            return Proc(stdout="train-receipt-20310101T000000+0000.json\n/workspace/lora-01.log\n")
        if args[0] == "ssh" and "sha256sum '" in text:
            return Proc(stdout=f"{hashlib.sha256(b'receipt').hexdigest()}  x\n")
        if args[0] == "scp" and ("train-receipt-" in text or ".log" in text):
            with open(args[-1], "wb") as fh:
                fh.write(b"receipt")
            return Proc()
        return host.runner(args, **kwargs)

    out = vlm_vast.cmd_watch_adapters(_settings(tmp_path), local_root=tmp_path / "bk", interval_seconds=1, deadline_seconds=10**6, runner=runner,
                                      sleeper=sleeper, clock=lambda: 0.0, emit=events.append)
    assert sorted(out["pulled"]) == ["adapter-final", "adapter-step-00100", "adapter-step-00200"] and out["final_done"] is True
    pulled = [e for e in events if e["event"] == "pulled"]
    assert [e["name"] for e in pulled] == ["adapter-step-00100", "adapter-step-00200", "adapter-final"]
    assert [e["step"] for e in pulled] == [100, 200, 400]
    assert (tmp_path / "bk" / "lora-01" / "train-receipt-20310101T000000+0000.json").read_bytes() == b"receipt"
    assert (tmp_path / "bk" / "lora-01" / "train.log").is_file()


def test_watch_logs_a_failed_poll_and_keeps_going_until_the_deadline(tmp_path):
    calls = {"n": 0}

    def runner(args, **kwargs):
        calls["n"] += 1
        raise OSError("boom")
    events = []
    clock = iter([0.0, 0.0, 100.0, 100.0, 100.0])
    out = vlm_vast.cmd_watch_adapters(_settings(tmp_path), local_root=tmp_path / "bk", interval_seconds=1, deadline_seconds=50, runner=runner,
                                      sleeper=lambda s: None, clock=lambda: next(clock), emit=events.append)
    assert out["pulled"] == {} and [e["event"] for e in events] == ["error", "error", "deadline"]
    assert all("203.0.113.9" not in json.dumps(e) for e in events)
