"""Fabricated evidence only. Replay must reuse a recorded response exactly when the model's input is
unchanged, refuse loudly when it changed, and never reach the network."""
import json

import pytest

import vlm.pair as pair
from tools.phase3_pair import replay_judgment as replay
from vlm.receipts import canonical_json, sha256_bytes

RECORDED = {"version": 1, "source_sha256": {"vlm/gate.py": "old"},
            "served_models": [{"model": "proposer-m", "revision": "rev-1"}]}


def _key(prompt, image=b"page-image", **kwargs):
    material = {**kwargs, "image_jpeg": sha256_bytes(image), "model": "proposer-m", "prompt": prompt,
                "manifest": {k: v for k, v in RECORDED.items() if k != "served_models"}}
    return sha256_bytes(canonical_json(material).encode())


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    for name in ("_chat_once", "_check_model", "_client"):
        monkeypatch.setattr(pair, name, getattr(pair, name))   # restored after the test
    calls = tmp_path / "calls"
    calls.mkdir()
    (calls / (_key("recorded prompt", seed=0) + ".json")).write_text("{}")
    received = []
    monkeypatch.setattr(pair, "_chat_once", lambda root, client, model, prompt, **kw: received.append(
        (client, kw["manifest"])) or "RECORDED RESPONSE")
    stats = {"hits": 0, "misses": 0}
    replay.install(RECORDED, stats)
    return tmp_path, stats, received


def test_unchanged_input_reuses_the_recorded_response_under_the_recorded_manifest(evidence):
    root, stats, received = evidence
    # The CURRENT manifest differs (new source hashes); keying must use the recorded one.
    result = pair._chat_once(root, object(), "proposer-m", "recorded prompt",
                             manifest={"source_sha256": {"vlm/gate.py": "new"}},
                             image_jpeg=b"page-image", seed=0)
    assert result == "RECORDED RESPONSE" and stats == {"hits": 1, "misses": 0}
    client, manifest = received[0]
    assert manifest is RECORDED and isinstance(client, replay._NoNetwork)


def test_a_changed_prompt_is_refused_not_sent(evidence):
    root, stats, received = evidence
    with pytest.raises(replay.ReplayMiss, match="replay_input_changed"):
        pair._chat_once(root, object(), "proposer-m", "a different prompt", manifest={},
                        image_jpeg=b"page-image", seed=0)
    assert stats == {"hits": 0, "misses": 1} and received == []


def test_a_changed_image_or_option_is_refused(evidence):
    root, stats, _ = evidence
    for image, seed in ((b"another-render", 0), (b"page-image", 1)):
        with pytest.raises(replay.ReplayMiss):
            pair._chat_once(root, object(), "proposer-m", "recorded prompt", manifest={},
                            image_jpeg=image, seed=seed)
    assert stats["misses"] == 2


def test_model_checks_use_the_recorded_revision_and_refuse_anything_else(evidence):
    assert pair._check_model(object(), "proposer-m", "rev-1") == {"model": "proposer-m", "revision": "rev-1"}
    for model, revision in (("proposer-m", "rev-2"), ("unrecorded-m", "rev-1")):
        with pytest.raises(replay.ReplayMiss, match="replay_model_not_recorded"):
            pair._check_model(object(), model, revision)


def test_no_client_can_reach_the_network(evidence):
    client = pair._client("http://127.0.0.1:18013/v1", 10)
    with pytest.raises(replay.ReplayMiss, match="replay_attempted_model_request"):
        client.chat
