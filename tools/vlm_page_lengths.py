"""Encoded length of every page of a silver split under the trainer's own template — runs ON THE HOST, CPU only.

    /venv/main/bin/python vlm_page_lengths.py --dataset /workspace/silver-02 --base /workspace/models/Qwen__Qwen3.8-27B \
        --split validation --cap 5120 --out /workspace/silver-02/page-lengths-validation.json

The trainer skips a page whose prompt+target exceeds --max-length; this lists which pages those were (over_cap) so the
evaluation can report them as their own slice instead of dropping them. No model weights are loaded: the processor's
tokenizer and image processor are enough, and the numbers are exactly what encode_sample sees.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vlm.train_lora import encode_sample, read_samples  # noqa: E402
from vlm.receipts import utc_now  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vlm_page_lengths")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--split", default="validation")
    parser.add_argument("--cap", type=int, default=5120)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    import torch
    from PIL import Image
    from transformers import AutoProcessor

    torch.set_num_threads(args.threads)
    processor = AutoProcessor.from_pretrained(args.base)

    def apply(messages, add_generation_prompt: bool):
        encoded = processor.apply_chat_template(messages, tokenize=True, return_dict=True, return_tensors="pt",
                                                add_generation_prompt=add_generation_prompt, enable_thinking=False)
        flat = {k: v for k, v in encoded.items()}
        flat["input_ids"] = encoded["input_ids"][0].tolist()
        return flat

    dataset = Path(args.dataset)
    samples = read_samples(dataset, args.split)
    pages = []
    over = 0
    for i, sample in enumerate(samples):
        encoded = encode_sample(sample, image=Image.open(dataset / sample["image"]).convert("RGB"), apply_template=apply, max_length=10**9)
        tokens = len(encoded["input_ids"])
        target_tokens = tokens - int(encoded["prompt_length"])
        over_cap = tokens > args.cap
        over += int(over_cap)
        pages.append({"sha": sample["sha"], "page": sample["page"], "tokens": tokens, "prompt_tokens": int(encoded["prompt_length"]),
                      "target_tokens": target_tokens, "rows": len(sample["target"]["rows"]), "over_cap": over_cap})
        if (i + 1) % 200 == 0:
            print(json.dumps({"done": i + 1, "of": len(samples), "over_cap": over, "at": utc_now()}), flush=True)
    out = {"dataset": str(dataset), "split": args.split, "cap": args.cap, "pages": len(pages), "over_cap": over,
           "note": "lengths under the trainer's template (thinking off, prompt masked); over_cap pages were skipped by training and stay in evaluation",
           "written_at": utc_now(), "items": pages}
    Path(args.out).write_text(json.dumps(out), encoding="utf-8")
    print(json.dumps({"pages": len(pages), "over_cap": over, "out": args.out}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
