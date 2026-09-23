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


LIVE_RECORDED = {**RECORDED, "served_models": [{"model": "dotsmocr", "revision": "rev-1"}]}


def _live(tmp_path, monkeypatch, served_revision):
    """live_on_miss against fake servers that serve ``served_revision`` of the proposer."""
    for name in ("_chat_once", "_check_model", "_client"):
        monkeypatch.setattr(pair, name, getattr(pair, name))
    monkeypatch.setenv("VISUAL_PAIR_PROPOSER_URL", "http://127.0.0.1:18013/v1")
    received, checked = [], []

    def check_model(client, model, revision):
        checked.append((client, model, revision))
        if revision != served_revision:
            raise pair.VisualPairError("visual_pair_model_revision_unverified")
        return {"model": model, "revision": revision}

    def chat_once(root, client, model, prompt, **kwargs):
        received.append((client, kwargs["manifest"]))
        return "RESPONSE"

    monkeypatch.setattr(pair, "_client", lambda url, timeout: ("LIVE", url))
    monkeypatch.setattr(pair, "_check_model", check_model)
    monkeypatch.setattr(pair, "_chat_once", chat_once)
    stats = {"hits": 0, "misses": 0, "live_calls": 0}
    replay.install(LIVE_RECORDED, stats, live_on_miss=True)
    return stats, received, checked


def test_live_on_miss_sends_only_a_changed_call_to_the_verified_server(tmp_path, monkeypatch):
    stats, received, checked = _live(tmp_path, monkeypatch, served_revision="rev-1")
    result = pair._chat_once(tmp_path, object(), "dotsmocr", "a changed prompt", manifest={},
                             image_jpeg=b"page-image", seed=0)
    assert result == "RESPONSE" and stats == {"hits": 0, "misses": 1, "live_calls": 1}
    client, manifest = received[0]
    assert client == ("LIVE", "http://127.0.0.1:18013/v1") and manifest is LIVE_RECORDED  # keyed as recorded
    assert checked == [(("LIVE", "http://127.0.0.1:18013/v1"), "dotsmocr", "rev-1")]


def test_live_on_miss_verifies_each_documents_own_recorded_revision(tmp_path, monkeypatch):
    # Review 4, finding 3: document B was recorded under rev-2 while the server (verified for A) serves rev-1.
    stats, received, checked = _live(tmp_path, monkeypatch, served_revision="rev-1")
    pair._chat_once(tmp_path, object(), "dotsmocr", "a changed prompt", manifest={}, image_jpeg=b"a", seed=0)
    LIVE_RECORDED["served_models"][0]["revision"] = "rev-2"
    try:
        with pytest.raises(pair.VisualPairError):
            pair._chat_once(tmp_path, object(), "dotsmocr", "another prompt", manifest={}, image_jpeg=b"b", seed=0)
    finally:
        LIVE_RECORDED["served_models"][0]["revision"] = "rev-1"
    assert [revision for _, _, revision in checked] == ["rev-1", "rev-2"] and len(received) == 1


def test_live_on_miss_refuses_a_server_that_serves_another_revision(tmp_path, monkeypatch):
    stats, received, _ = _live(tmp_path, monkeypatch, served_revision="rev-2")
    with pytest.raises(pair.VisualPairError):
        pair._chat_once(tmp_path, object(), "dotsmocr", "a changed prompt", manifest={},
                        image_jpeg=b"page-image", seed=0)
    assert received == []
