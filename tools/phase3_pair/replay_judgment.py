"""Re-run a completed judgement check with the CURRENT merge, gate and analysis code and ZERO model calls.

Every model call in a pair run is cached under a key that includes the hash of every pipeline source file.
That is deliberate: in production, changed code must never silently reuse an old reading. For evaluating a
change to code DOWNSTREAM of the models (row assembly, review merge, metadata merge, dates, gate,
analysis), that same rule makes every iteration re-read every page at the GPU.

Replay keys each call with the manifest RECORDED by the earlier run instead. The current code still builds
the image, prompt and request options; if they are exactly what the earlier run sent, the key matches and
the recorded response is reused. If the change altered what a model would have seen, the key misses and
replay REFUSES the document with ReplayMiss. There is no fallback to a live call: the model clients are
replaced by ones that raise on any request.

Replay never touches the earlier run: it works on a copy of the evidence store under --output-dir, which
must be outside the repository checkout like every other private artefact. Output is the same set of
private files check_judgment writes, plus replay.private.json with hit and miss counts.

    python -m tools.phase3_pair.replay_judgment --from-run <judgment-checks/<run_id>> \
        --manifest <m.json> --manifest-sha256 <sha> --source-root <dir> --output-dir <replay root>

The authorisation fences are still checked, exactly as for a live run, because replay reads the same
customer statements; no page leaves the machine.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from tools.phase3_pair import check_judgment


class ReplayMiss(RuntimeError):
    """The current code would have sent a model something the recorded run did not."""


class _NoNetwork:
    def __getattr__(self, name):
        raise ReplayMiss(f"replay_attempted_model_request:{name}")


def _blob(evidence: Path, digest: str) -> bytes:
    return (evidence / "blobs" / digest[:2] / digest).read_bytes()


def recorded_manifests(run_folder: Path, evidence: Path) -> dict[str, dict]:
    manifests = {}
    for path in sorted(run_folder.glob("*-document.private.json")):
        document_id = path.name.split("-document")[0]
        record = json.loads(path.read_text(encoding="utf-8"))["visual_pair"]
        receipt = json.loads(_blob(evidence, record["receipt_sha256"]))
        manifests[document_id] = receipt["manifest"]
    if not manifests:
        raise SystemExit("replay_no_recorded_documents")
    return manifests


def install(manifest: dict | None, stats: dict) -> dict:
    """Point vlm.pair at recorded evidence only. Returns the holder; set holder["manifest"] to switch the
    recorded manifest between documents."""
    import vlm.pair as pair
    from vlm.receipts import canonical_json, sha256_bytes

    holder = {"manifest": manifest}
    original_chat = pair._chat_once

    def recorded() -> dict:
        if holder["manifest"] is None:
            raise ReplayMiss("replay_document_not_recorded")
        return holder["manifest"]

    def check_model(client, model, revision):
        served = {item["model"]: item for item in recorded().get("served_models", [])}
        entry = served.get(model)
        if entry is None or entry.get("revision") != revision:
            raise ReplayMiss(f"replay_model_not_recorded:{model}")
        return dict(entry)

    def chat_once(root, client, model, prompt, *, manifest: dict, **kwargs):
        # Same key construction as vlm.pair._chat_once, but over the RECORDED manifest.
        fixed = recorded()
        material = {**kwargs, "image_jpeg": sha256_bytes(kwargs["image_jpeg"]), "model": model, "prompt": prompt,
                    "manifest": {key: value for key, value in fixed.items() if key != "served_models"}}
        key = sha256_bytes(canonical_json(material).encode())
        if not (Path(root) / "calls" / (key + ".json")).exists():
            stats["misses"] += 1
            raise ReplayMiss("replay_input_changed")
        stats["hits"] += 1
        return original_chat(root, _NoNetwork(), model, prompt, manifest=fixed, **kwargs)

    pair._check_model = check_model
    pair._chat_once = chat_once
    pair._client = lambda url, timeout: _NoNetwork()
    return holder


def switch_per_document(manifests: dict[str, dict], holder: dict) -> None:
    """Replay each document under the manifest IT was recorded with. Documents of one run normally share a
    manifest; they differ when pipeline sources changed on disk mid-run, because the manifest hashes the
    source files at the start of each document."""
    original = check_judgment._run_document

    def run_document(item, **kwargs):
        holder["manifest"] = manifests.get(item["id"])
        return original(item, **kwargs)

    check_judgment._run_document = run_document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from-run", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    source_evidence = args.from_run.parent / "evidence"
    manifests = recorded_manifests(args.from_run, source_evidence)
    first = next(iter(manifests.values()))
    mixed = any(manifest != first for manifest in manifests.values())

    output = check_judgment._private_output(args.output_dir, args.source_root)
    target = output / "evidence"
    if target.exists():
        raise SystemExit("replay_output_already_has_evidence: use a fresh --output-dir")
    shutil.copytree(source_evidence, target)

    stats = {"hits": 0, "misses": 0}
    holder = install(None, stats)
    switch_per_document(manifests, holder)
    run_args = argparse.Namespace(manifest=args.manifest, manifest_sha256=args.manifest_sha256,
                                  source_root=args.source_root, output_dir=args.output_dir)
    summary = check_judgment.run(run_args)
    report = {"replayed_from": args.from_run.name, "model_calls": 0, **stats,
              "recorded_manifests_differ_between_documents": mixed,
              "documents": summary.get("documents"), "admitted": summary.get("admitted")}
    check_judgment._write_private(output / summary["run_id"] / "replay.private.json", report)
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0 if stats["misses"] == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
