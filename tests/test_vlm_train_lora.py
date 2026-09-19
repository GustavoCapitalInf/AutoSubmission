"""The framework-free half of the LoRA trainer: messages, label mask, sample encoding, lineage receipt."""
import json

import pytest

from vlm import train_lora as tl
from vlm.prompts import stage_b_prompt
from vlm.receipts import Refused
from vlm.schema import empty_proposal


def _sample(page=1, total=3):
    target = empty_proposal("statement_page")
    target["rows"].append({"date": "2031-01-02", "date_text": "01/02", "description": "SYNTHETIC ROW", "amount": 10.0, "direction": "credit",
                           "balance": 510.0, "continues_previous": False})
    return {"sha": "A" * 64, "page": page, "page_total": total, "image": "images/x/001.jpg", "image_sha256": "0" * 64, "family": "fam",
            "split": "train", "target": target}


class FakeTemplate:
    """A chat template that emits 5 prompt tokens, a generation prefix of 1, and one token per target character."""

    def __call__(self, messages, add_generation_prompt):
        ids = [1, 2, 3, 4, 5]
        if add_generation_prompt:
            return {"input_ids": ids + [9], "pixel_values": "PIX"}
        target = messages[1]["content"][0]["text"]
        return {"input_ids": ids + [9] + [100 + (ord(c) % 50) for c in target], "pixel_values": "PIX"}


def test_messages_use_the_harness_prompt_and_the_canonical_target():
    messages, target = tl.messages_for(_sample(), image="IMG")
    assert messages[0]["role"] == "user" and messages[0]["content"][0] == {"type": "image", "image": "IMG"}
    assert messages[0]["content"][1]["text"] == stage_b_prompt(page_number=2, page_total=3)
    assert messages[1]["role"] == "assistant" and json.loads(target)["page_role"] == "statement_page"
    assert target == json.dumps(json.loads(target), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def test_encode_masks_the_prompt_and_skips_over_long_samples():
    encoded = tl.encode_sample(_sample(), image="IMG", apply_template=FakeTemplate(), max_length=100000)
    assert encoded["prompt_length"] == 6 and encoded["labels"][:6] == [tl.IGNORE_INDEX] * 6
    assert encoded["labels"][6:] == encoded["input_ids"][6:] and encoded["pixel_values"] == "PIX"
    assert tl.encode_sample(_sample(), image="IMG", apply_template=FakeTemplate(), max_length=20) is None
    with pytest.raises(Refused):
        tl.mask_prompt([1, 2, 3], 4)


def test_read_samples_validates_targets_and_lineage_receipt_binds_everything(tmp_path):
    dataset = tmp_path / "ds"
    dataset.mkdir()
    (dataset / "train.jsonl").write_text(json.dumps(_sample()) + "\n", encoding="utf-8")
    (dataset / "manifest.json").write_text(json.dumps({"silver_version": 1, "schema_version": 3, "jsonl_sha256": {"train": "x"},
                                                       "split_documents": {"train": 1, "validation": 0}, "counts": {"documents": 1}}), encoding="utf-8")
    assert len(tl.read_samples(dataset, "train")) == 1
    with pytest.raises(Refused) as exc:
        tl.read_samples(dataset, "validation")
    assert exc.value.code == "dataset_split_missing:validation"
    bad = _sample()
    bad["target"]["rows"][0]["direction"] = "sideways"
    (dataset / "bad.jsonl").write_text(json.dumps(bad) + "\n", encoding="utf-8")
    with pytest.raises(Refused) as exc:
        tl.read_samples(dataset, "bad")
    assert exc.value.code == "dataset_target_invalid"
    base = tmp_path / "base"
    base.mkdir()
    (base / "config.json").write_text("{}", encoding="utf-8")
    (base / "model-00001-of-00001.safetensors").write_bytes(b"weights")
    adapter = tmp_path / "adapter-final"
    adapter.mkdir()
    (adapter / "adapter_model.safetensors").write_bytes(b"adapter")
    receipt = tl.lineage_receipt(dataset=dataset, base_dir=base, out_dir=tmp_path / "out", hyper=tl.Hyperparameters(), versions={"torch": "x"},
                                 gpu="fake", started_at="2031-01-01T00:00:00Z", steps=3, losses={"train": [[1, 0.5]], "eval": [[3, 0.4]]},
                                 adapter_dir=adapter, skipped_long=2)
    assert receipt["dataset"]["manifest_sha256"] and receipt["base"]["weight_files"] == ["model-00001-of-00001.safetensors"]
    assert receipt["adapter"]["files"]["adapter_model.safetensors"] and receipt["hyperparameters"]["rank"] == 32
    assert receipt["prompt_version"] and receipt["schema_version"] and list((tmp_path / "out").glob("train-receipt-*.json"))
    with pytest.raises(Refused) as exc:
        tl.base_binding(tmp_path / "nowhere")
    assert exc.value.code == "base_config_missing"


def test_checkpoint_metadata_round_trip(tmp_path):
    meta = tl.checkpoint_metadata(step=100, seen=1600, skipped_long=300, total_steps=400, hyper=tl.Hyperparameters(), resumed_from=None)
    (tmp_path / "training_state.json").write_text(json.dumps(meta), encoding="utf-8")
    loaded = tl.load_checkpoint_metadata(tmp_path)
    assert loaded["step"] == 100 and loaded["seen"] == 1600 and loaded["skipped_long"] == 300 and loaded["hyperparameters"]["rank"] == 32
    assert tl.load_checkpoint_metadata(tmp_path / "nowhere") is None


def test_resume_plan_restores_step_counters_and_data_position_and_names_what_restarts():
    meta = {"step": 100, "seen": 1600, "skipped_long": 300}
    full = tl.resume_plan(meta, n_samples=14211, has_optimizer=True, has_rng=True)
    assert full["step"] == 100 and full["position"] == 1900 and full["optimizer"] and full["rng"] and full["note"] is None
    wrap = tl.resume_plan({"step": 5, "seen": 14200, "skipped_long": 20}, n_samples=14211, has_optimizer=True, has_rng=True)
    assert wrap["position"] == (14200 + 20) % 14211
    partial = tl.resume_plan(meta, n_samples=14211, has_optimizer=False, has_rng=False)
    assert "optimizer moments restart" in partial["note"] and "RNG streams restart" in partial["note"]
    weights_only = tl.resume_plan(None, n_samples=10, has_optimizer=False, has_rng=False)
    assert weights_only["step"] == 0 and weights_only["position"] == 0 and "weights-only" in weights_only["note"]
    with pytest.raises(Refused):
        tl.data_position(1, 1, 0)
