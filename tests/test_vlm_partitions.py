import csv
import json
from pathlib import Path

import pytest

from vlm import partitions, receipts

SHA_A = "A" * 64
SHA_B = "B" * 64
SHA_C = "C" * 64

DIGEST_EMPTY = (
    "store_version: 1\nrecord_count: 0\nchain_head: GENESIS\nholdout_chain_head: GENESIS\n"
    "adjudicated_sha16:\nholdout_sha16_status:\n"
)


def _fake_run(tmp_path: Path, shas, held_digest: str = DIGEST_EMPTY):
    run = tmp_path / "run"
    run.mkdir()
    archive = tmp_path / "archive"
    archive.mkdir()
    with (run / "rows.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "relative_path", "folder_label", "content_sha256", "byte_size", "classification",
            "page_count", "outcome_class", "account_count"])
        writer.writeheader()
        for i, sha in enumerate(shas):
            rel = f"fam{i % 2}/doc{i}.pdf"
            (archive / rel).parent.mkdir(parents=True, exist_ok=True)
            (archive / rel).write_bytes(b"%PDF-1.4 synthetic")
            writer.writerow({"relative_path": rel, "folder_label": f"fam{i % 2}", "content_sha256": sha,
                             "byte_size": 18, "classification": "digital", "page_count": i + 1,
                             "outcome_class": "validated" if i % 2 == 0 else "failed", "account_count": 1})
    digest = tmp_path / "MANIFEST_DIGEST.txt"
    digest.write_text(held_digest, encoding="utf-8")
    pops = tmp_path / "populations"
    pops.mkdir()
    (pops / "CTRL.shas").write_text(f"# CTRL\n{shas[0]}\n", encoding="utf-8")
    (pops / "U755.shas").write_text(f"# U755\n{shas[1]}\n{shas[2]}\n", encoding="utf-8")
    return run, archive, digest, pops


def test_build_manifest_public_has_no_paths(tmp_path):
    run, archive, digest, _ = _fake_run(tmp_path, [SHA_A, SHA_B, SHA_C])
    public, private = partitions.build_manifest("X", [SHA_B, SHA_A], run_dir=run, archive_root=archive,
                                                holdout_digest=digest)
    assert public["documents"] == 2 and public["pages"] == 3
    assert public["set_sha256"] == partitions.set_sha256([SHA_A, SHA_B])
    assert public["holdout_overlap"] == 0
    assert "members" not in public and "doc0.pdf" not in json.dumps(public) and "fam0/" not in json.dumps(public)
    assert [m["sha"] for m in private["members"]] == [SHA_A, SHA_B]
    assert private["members"][0]["relative_path"] == "fam0/doc0.pdf"


def test_holdout_overlap_refuses_by_count(tmp_path):
    held = DIGEST_EMPTY + f"- {SHA_B[:16]} unseen\n"
    run, archive, digest, _ = _fake_run(tmp_path, [SHA_A, SHA_B, SHA_C], held)
    with pytest.raises(receipts.Refused) as exc:
        partitions.build_manifest("X", [SHA_A, SHA_B], run_dir=run, archive_root=archive, holdout_digest=digest)
    assert exc.value.code == "population_overlaps_holdout"


def test_member_missing_refuses(tmp_path):
    run, archive, digest, _ = _fake_run(tmp_path, [SHA_A, SHA_B, SHA_C])
    with pytest.raises(receipts.Refused) as exc:
        partitions.build_manifest("X", ["D" * 64], run_dir=run, archive_root=archive, holdout_digest=digest)
    assert exc.value.code == "member_not_in_run_of_record"


def test_dev_slice_is_deterministic():
    shas = [f"{i:064X}" for i in range(50)]
    first = partitions.dev_slice(shas, n=20)
    assert first == partitions.dev_slice(list(reversed(shas)), n=20) and len(first) == 20
    assert first == sorted(first)


def test_write_manifests_writes_public_and_private(tmp_path):
    run, archive, digest, pops = _fake_run(tmp_path, [SHA_A, SHA_B, SHA_C])
    out = tmp_path / "out"
    summary = partitions.write_manifests(out, populations_dir=pops, run_dir=run, archive_root=archive,
                                         holdout_digest=digest, dev_size=1)
    assert set(summary) == {"CTRL", "U755", "DEV"}
    assert (out / "CTRL.manifest.json").exists() and (out / "CTRL.manifest.private.json").exists()
    members = partitions.load_private_manifest(out / "U755.manifest.private.json")
    assert [m.sha for m in members] == [SHA_B, SHA_C]
    assert summary["DEV"]["documents"] == 1
    with pytest.raises(FileExistsError):
        partitions.write_manifests(out, populations_dir=pops, run_dir=run, archive_root=archive,
                                   holdout_digest=digest, dev_size=1)
