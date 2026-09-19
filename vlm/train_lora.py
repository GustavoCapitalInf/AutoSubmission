"""LoRA fine-tuning of the Stage B model on silver labels (R17, plan v1 §12): the framework-free parts.

Samples are the page image plus the SAME prompt the harness sends at inference (`stage_b_prompt`) and the
canonical JSON target of the silver dataset as the assistant turn; the loss covers the assistant tokens only.
Everything that touches torch, transformers or peft lives in `tools/vlm_train_lora.py`; this module builds the
messages, masks the labels and writes the lineage receipt (plan §9), so it is testable without a GPU.
"""
from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from vlm import HARNESS_VERSION
from vlm.prompts import PROMPT_VERSION, stage_b_prompt
from vlm.receipts import dump_new, need, sha256_file, utc_now
from vlm.schema import SCHEMA_VERSION, validate_page_proposal

TRAIN_VERSION = 1


def canonical_target(proposal: dict) -> str:
    """The same canonical JSON as vlm.silver (inlined: the trainer ships without the partition modules)."""
    return json.dumps(proposal, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
LORA_TARGETS = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")
IGNORE_INDEX = -100


@dataclass(frozen=True)
class Hyperparameters:
    rank: int = 32
    alpha: int = 64
    dropout: float = 0.05
    learning_rate: float = 1e-4
    epochs: float = 1.0
    max_steps: int | None = None
    grad_accumulation: int = 16
    max_length: int = 6144
    warmup_steps: int = 50
    seed: int = 0
    eval_every: int = 200
    eval_samples: int = 200
    save_every: int = 200
    targets: tuple[str, ...] = LORA_TARGETS


def read_samples(dataset: Path, split: str) -> list[dict]:
    path = Path(dataset) / f"{split}.jsonl"
    need(path.is_file(), f"dataset_split_missing:{split}")
    samples = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for sample in samples:
        need(not validate_page_proposal(sample["target"]), "dataset_target_invalid")
    return samples


def messages_for(sample: dict, *, image: Any) -> tuple[list[dict], str]:
    """The chat turns of one sample: the harness prompt with the page image, then the canonical target."""
    prompt = stage_b_prompt(page_number=int(sample["page"]) + 1, page_total=int(sample["page_total"]))
    target = canonical_target(sample["target"])
    return ([{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]},
             {"role": "assistant", "content": [{"type": "text", "text": target}]}], target)


def mask_prompt(input_ids: list[int], prompt_length: int) -> list[int]:
    """Labels: the prompt (everything the template emits before the assistant's content) is ignored."""
    need(0 < prompt_length <= len(input_ids), "prompt_length_out_of_range")
    return [IGNORE_INDEX] * prompt_length + list(input_ids[prompt_length:])


def encode_sample(sample: dict, *, image: Any, apply_template: Callable[..., dict], max_length: int) -> dict | None:
    """Tokenize with the processor's chat template twice: the full conversation, and the prompt alone with the
    generation prefix, whose length is the label mask. `apply_template(messages, add_generation_prompt)` must
    return a dict with `input_ids` (a flat list) plus any pixel tensors, thinking disabled both times."""
    messages, _target = messages_for(sample, image=image)
    full = apply_template(messages, add_generation_prompt=False)
    prompt_only = apply_template(messages[:1], add_generation_prompt=True)
    ids = list(full["input_ids"])
    prompt_length = len(list(prompt_only["input_ids"]))
    need(ids[:prompt_length] == list(prompt_only["input_ids"]), "template_prefix_mismatch")
    if len(ids) > max_length:
        return None   # the caller counts these; a truncated JSON target would teach truncation
    labels = mask_prompt(ids, prompt_length)
    return {**full, "input_ids": ids, "labels": labels, "prompt_length": prompt_length}


def dataset_binding(dataset: Path) -> dict:
    manifest = Path(dataset) / "manifest.json"
    need(manifest.is_file(), "dataset_manifest_missing")
    public = json.loads(manifest.read_text(encoding="utf-8"))
    return {"manifest_sha256": sha256_file(manifest), "silver_version": public.get("silver_version"), "schema_version": public.get("schema_version"),
            "jsonl_sha256": public.get("jsonl_sha256"), "split_documents": public.get("split_documents"), "counts": public.get("counts")}


def base_binding(base_dir: Path) -> dict:
    """The base checkpoint's identity without hashing tens of gigabytes: config and the weight index."""
    base = Path(base_dir)
    need((base / "config.json").is_file(), "base_config_missing")
    files = sorted(p.name for p in base.glob("*.safetensors"))
    need(bool(files), "base_weights_missing")
    index = base / "model.safetensors.index.json"
    return {"path": str(base), "config_sha256": sha256_file(base / "config.json"),
            "index_sha256": sha256_file(index) if index.is_file() else None, "weight_files": files,
            "weight_bytes": sum((base / f).stat().st_size for f in files)}


def lineage_receipt(*, dataset: Path, base_dir: Path, out_dir: Path, hyper: Hyperparameters, versions: dict, gpu: str,
                    started_at: str, steps: int, losses: dict, adapter_dir: Path | None, skipped_long: int, notes: dict | None = None) -> dict:
    adapter = None
    if adapter_dir is not None:
        weights = sorted(Path(adapter_dir).glob("adapter_model.*"))
        adapter = {"path": str(adapter_dir), "files": {p.name: sha256_file(p) for p in weights}}
    receipt = {"train_version": TRAIN_VERSION, "harness_version": HARNESS_VERSION, "prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION,
               "dataset": dataset_binding(dataset), "base": base_binding(base_dir), "hyperparameters": asdict(hyper), "versions": versions,
               "gpu": gpu, "host": platform.node(), "started_at": started_at, "finished_at": utc_now(), "steps": steps, "losses": losses,
               "samples_skipped_too_long": skipped_long, "adapter": adapter, "notes": notes or {}}
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    dump_new(Path(out_dir) / f"train-receipt-{utc_now().replace(':', '').replace('-', '')}.json", receipt)
    return receipt


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
