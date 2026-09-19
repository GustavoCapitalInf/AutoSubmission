"""LoRA fine-tuning of the Stage B model on the silver dataset — runs ON THE RENTED HOST (R17).

    /venv/main/bin/python vlm_train_lora.py train --dataset /workspace/silver-01 --base /workspace/models/Qwen__Qwen3.8-27B --out /workspace/lora-01
    /venv/main/bin/python vlm_train_lora.py merge --base ... --adapter /workspace/lora-01/adapter-final --out /workspace/models/Qwen3.8-27B-lora01

The framework-free parts (messages, label mask, lineage receipt) live in `vlm/train_lora.py`; this file is deployed
next to a copy of the `vlm` package. Nothing here talks to the network: base weights and the dataset are already on
the host, the adapter stays on the host and the local machine (never a hub).
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vlm.train_lora import Hyperparameters, checkpoint_metadata, encode_sample, lineage_receipt, load_checkpoint_metadata, read_samples  # noqa: E402
from vlm.receipts import utc_now  # noqa: E402


def _versions() -> dict:
    import importlib.metadata as md

    out = {}
    for name in ("torch", "transformers", "peft", "accelerate", "pillow"):
        try:
            out[name] = md.version(name)
        except md.PackageNotFoundError:
            out[name] = None
    return out


def _load(base: Path):
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    processor = AutoProcessor.from_pretrained(str(base))
    model = AutoModelForImageTextToText.from_pretrained(str(base), dtype=torch.bfloat16, device_map="cuda", attn_implementation="sdpa")
    return processor, model


def _template(processor):
    def apply(messages, add_generation_prompt: bool):
        encoded = processor.apply_chat_template(messages, tokenize=True, return_dict=True, return_tensors="pt",
                                                add_generation_prompt=add_generation_prompt, enable_thinking=False)
        flat = {k: v for k, v in encoded.items()}
        flat["input_ids"] = encoded["input_ids"][0].tolist()
        return flat
    return apply


def _batch(encoded: dict, device):
    import torch

    tensors = {}
    for key, value in encoded.items():
        if key in ("input_ids", "labels"):
            tensors[key] = torch.tensor([value], dtype=torch.long, device=device)
        elif key == "prompt_length":
            continue
        elif hasattr(value, "to"):
            tensors[key] = value.to(device)
    tensors["attention_mask"] = torch.ones_like(tensors["input_ids"])
    return tensors


def cmd_train(args: argparse.Namespace) -> int:
    import torch
    from peft import LoraConfig, PeftModel, get_peft_model
    from PIL import Image

    hyper = Hyperparameters(rank=args.rank, alpha=args.alpha, learning_rate=args.lr, epochs=args.epochs, max_steps=args.max_steps,
                            grad_accumulation=args.grad_accum, max_length=args.max_length, seed=args.seed, eval_every=args.eval_every,
                            eval_samples=args.eval_samples, save_every=args.save_every)
    dataset, base, out = Path(args.dataset), Path(args.base), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    random.seed(hyper.seed)
    torch.manual_seed(hyper.seed)
    train = read_samples(dataset, "train")
    validation = read_samples(dataset, "validation")
    random.shuffle(train)
    processor, model = _load(base)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    resumed_from = None
    resumed_state = None
    if args.resume_adapter:
        # Continue from a saved adapter: the LoRA weights come from the checkpoint; the optimizer tensors and the
        # step counter too when the checkpoint carries them (a checkpoint written before this version has neither,
        # so the schedule restarts with fresh optimizer moments, which the receipt says).
        model = PeftModel.from_pretrained(model, args.resume_adapter, is_trainable=True)
        resumed_from = str(args.resume_adapter)
        resumed_state = load_checkpoint_metadata(Path(args.resume_adapter))
    else:
        config = LoraConfig(r=hyper.rank, lora_alpha=hyper.alpha, lora_dropout=hyper.dropout, target_modules=list(hyper.targets), task_type="CAUSAL_LM")
        model = get_peft_model(model, config)
    model.print_trainable_parameters()
    apply = _template(processor)
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=hyper.learning_rate, weight_decay=0.0)
    total_steps = hyper.max_steps or math.ceil(len(train) * hyper.epochs / hyper.grad_accumulation)
    start_step = start_seen = start_skipped = 0
    if resumed_state is not None:
        start_step, start_seen, start_skipped = int(resumed_state["step"]), int(resumed_state["seen"]), int(resumed_state["skipped_long"])
        opt_path = Path(args.resume_adapter) / "optimizer.pt"
        if opt_path.is_file():
            optimizer.load_state_dict(torch.load(opt_path, map_location="cpu"))
            print(json.dumps({"resumed": resumed_from, "step": start_step, "optimizer_state": True}), flush=True)
        else:
            print(json.dumps({"resumed": resumed_from, "step": start_step, "optimizer_state": False}), flush=True)

    def save_checkpoint(directory: Path, step: int, seen: int, skipped: int) -> None:
        model.save_pretrained(str(directory))
        torch.save(optimizer.state_dict(), directory / "optimizer.pt")
        (directory / "training_state.json").write_text(json.dumps(checkpoint_metadata(
            step=step, seen=seen, skipped_long=skipped, total_steps=total_steps, hyper=hyper, resumed_from=resumed_from), indent=2), encoding="utf-8")

    def lr_at(step: int) -> float:
        if step < hyper.warmup_steps:
            return hyper.learning_rate * (step + 1) / hyper.warmup_steps
        progress = (step - hyper.warmup_steps) / max(1, total_steps - hyper.warmup_steps)
        return hyper.learning_rate * 0.5 * (1 + math.cos(math.pi * min(1.0, progress)))

    def evaluate(step: int) -> float:
        model.eval()
        losses = []
        with torch.no_grad():
            for sample in validation[: hyper.eval_samples]:
                encoded = encode_sample(sample, image=Image.open(dataset / sample["image"]).convert("RGB"), apply_template=apply, max_length=hyper.max_length)
                if encoded is None:
                    continue
                losses.append(float(model(**_batch(encoded, model.device)).loss))
        model.train()
        value = sum(losses) / max(1, len(losses))
        print(json.dumps({"eval_step": step, "eval_loss": value, "n": len(losses)}), flush=True)
        return value

    model.train()
    losses = {"train": [], "eval": []}
    skipped_long = start_skipped
    step = start_step
    micro = 0
    running = 0.0
    adapter_dir = None
    seen = start_seen
    epoch = 0
    if start_seen:
        # the shuffled order is seeded, so skipping the samples already consumed continues the same pass
        train = train[(start_seen + start_skipped) % len(train):] + train[: (start_seen + start_skipped) % len(train)]
    while step < total_steps:
        for sample in train:
            if step >= total_steps:
                break
            encoded = encode_sample(sample, image=Image.open(dataset / sample["image"]).convert("RGB"), apply_template=apply, max_length=hyper.max_length)
            if encoded is None:
                skipped_long += 1
                continue
            loss = model(**_batch(encoded, model.device)).loss / hyper.grad_accumulation
            loss.backward()
            running += float(loss)
            micro += 1
            seen += 1
            if micro % hyper.grad_accumulation == 0:
                for group in optimizer.param_groups:
                    group["lr"] = lr_at(step)
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                step += 1
                losses["train"].append([step, running])
                print(json.dumps({"step": step, "loss": running, "lr": lr_at(step), "seen": seen, "skipped_long": skipped_long, "at": utc_now()}), flush=True)
                running = 0.0
                if step % hyper.eval_every == 0:
                    losses["eval"].append([step, evaluate(step)])
                if step % hyper.save_every == 0:
                    adapter_dir = out / f"adapter-step-{step:05d}"
                    save_checkpoint(adapter_dir, step, seen, skipped_long)
        epoch += 1
        if hyper.max_steps is None and epoch >= math.ceil(hyper.epochs):
            break
    losses["eval"].append([step, evaluate(step)])
    adapter_dir = out / "adapter-final"
    save_checkpoint(adapter_dir, step, seen, skipped_long)
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    receipt = lineage_receipt(dataset=dataset, base_dir=base, out_dir=out, hyper=hyper, versions=_versions(), gpu=gpu, started_at=started,
                              steps=step, losses=losses, adapter_dir=adapter_dir, skipped_long=skipped_long,
                              notes={"samples_train": len(train), "samples_validation": len(validation), "epochs_seen": epoch,
                                     "resumed_from": resumed_from, "resumed_state": resumed_state, "accepted_examples": seen - start_seen,
                                     "examples_per_step_are_accepted_only": True})
    print(json.dumps({"steps": step, "adapter": str(adapter_dir), "final_eval_loss": losses["eval"][-1][1], "receipt_written": True,
                      "adapter_files": receipt["adapter"]["files"]}), flush=True)
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForImageTextToText, AutoProcessor

    base, adapter, out = Path(args.base), Path(args.adapter), Path(args.out)
    model = AutoModelForImageTextToText.from_pretrained(str(base), dtype=torch.bfloat16, device_map="cpu")
    merged = PeftModel.from_pretrained(model, str(adapter)).merge_and_unload()
    merged.save_pretrained(str(out), safe_serialization=True, max_shard_size="5GB")
    AutoProcessor.from_pretrained(str(base)).save_pretrained(str(out))
    print(json.dumps({"merged": str(out), "files": sorted(p.name for p in out.glob("*.safetensors"))}), flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vlm_train_lora")
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("train")
    t.add_argument("--dataset", required=True)
    t.add_argument("--base", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--rank", type=int, default=32)
    t.add_argument("--alpha", type=int, default=64)
    t.add_argument("--lr", type=float, default=1e-4)
    t.add_argument("--epochs", type=float, default=1.0)
    t.add_argument("--max-steps", type=int, default=None)
    t.add_argument("--grad-accum", type=int, default=16)
    t.add_argument("--max-length", type=int, default=6144)
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--eval-every", type=int, default=200)
    t.add_argument("--eval-samples", type=int, default=200)
    t.add_argument("--save-every", type=int, default=200)
    t.add_argument("--resume-adapter", default=None, help="a saved adapter directory to continue from (optimizer.pt and training_state.json when present)")
    m = sub.add_parser("merge")
    m.add_argument("--base", required=True)
    m.add_argument("--adapter", required=True)
    m.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    return cmd_train(args) if args.command == "train" else cmd_merge(args)


if __name__ == "__main__":
    sys.exit(main())
