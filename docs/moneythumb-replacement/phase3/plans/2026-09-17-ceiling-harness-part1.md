# Phase 3 Ceiling Experiment — Offline Harness Implementation Plan (part 1 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Parts 2 and 3 continue the task list; part 1 holds the header, constraints and file structure that every task inherits.

**Goal:** Build the offline-testable harness that renders statement pages, sends them to self-hosted vision models over a loopback tunnel, assembles candidate rows, runs the deterministic gate, and writes receipts and reports — so the two-week ceiling experiment (plan v1 §11, ruling R16) can run on the rented RTX 5090.

**Architecture:** A new standard-library-first package `vlm/` with one responsibility per module: receipts, partitions, render, schema, http clients, text parsing, HTML tables, row assembly, metadata rules, gate (which calls the reader's own `analysis.reconcile.reconcile`), reader truth + matching, Stage B prompts/proposals, runner, report; a CLI `tools/vlm_ceiling.py`. Every module is unit-tested offline with fakes; nothing here contacts the host (that is the part-B plan).

**Tech Stack:** Python 3.14 locally (3.12 on the host), `pypdfium2` (Apache-2.0/BSD-3) for rendering, Pillow for JPEG, `jsonschema` for local validation, `urllib` for HTTP (bounded, no redirects, loopback only), pydantic models from `analysis/schema.py`, `analysis.reconcile.reconcile` as the arithmetic authority, pytest.

## Global Constraints

- Ruling R16 (`docs/moneythumb-replacement/PHASE2_RULINGS.md`): ceiling experiment only; no training; customer pages only to the existing Vast `remote_paid` host over the loopback tunnel; populations CTRL, U755, synthetic; the sealed holdout is never read; USD 250 budget; hours recorded.
- Program plan v1 §4 invariants: model proposes, `analysis.reconcile.reconcile` decides; never partial admission; fail closed; every model input/output content-addressed; determinism (temperature 0, fixed seed); no silent second reading.
- Privacy: no customer bytes, paths, names or extracted contents in any public receipt, log line, test, commit message or this plan. Public receipts carry counts, hashes, closed status codes and path bindings. Anything that could name a document goes to `*.private.json`.
- Connection details only through `ocr.paddle_config.load_paddle_settings()`; masked output only through `tools.paddle_vast.mask_text`. Never print host, port, user or token.
- Both opt-in literals must be present in the process environment before any customer page is sent (`ocr.paddle_config.check_remote_authorization(settings, DATA_SCOPE_CUSTOMER)`); synthetic runs use `DATA_SCOPE_SYNTHETIC`.
- The holdout is checked ONLY through `discovery.runner.holdout_sha16s_from_digest(docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt)`; `vlm/` never imports `tools.holdout` or names the sealed-store variable (`tests/test_truth_firewall.py`).
- No PyMuPDF in `vlm/` (AGPL exposure; plan v1 §8). Rendering is pypdfium2 only.
- Model calls: `temperature: 0`, `seed: 0`, `chat_template_kwargs: {"enable_thinking": false}` for Qwen, structured outputs via `response_format: {"type": "json_schema", ...}` (vLLM 0.29; `guided_json` was removed in 0.12).
- Receipts are exclusive-create (`open(path, "x")`), sorted keys, `allow_nan=False`, fsynced; a receipt is never overwritten; an attempted wave directory is never reused.
- Tests run from the repo root: `python -m pytest tests/test_vlm_<name>.py -q -p no:cacheprovider` (the root `pytest.ini` deselects `live`/`corpus`; `conftest.py` needs `Bank Statements/` to exist, which it does on this machine). Never read a real statement in a test; use `tests/paddle_synthetic.py` builders.
- Commit only `vlm/`, `tests/test_vlm_*.py`, `tools/vlm_*.py`, `requirements-vlm.txt` and Phase 3 docs. Never `git add -A`. The owner's uncommitted `PHASE2_REMAINDER_PLAN.md` edit and `docs/moneythumb-replacement/superpowers/` stay uncommitted.
- Branch: `phase3-ceiling` (created from `train13` at commit 76fee9e). Commit message trailer: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## File Structure

| File | Responsibility |
|---|---|
| `requirements-vlm.txt` | `pypdfium2>=5.8`, `jsonschema>=4.20` (Pillow, pydantic already in the base requirements) |
| `vlm/__init__.py` | `HARNESS_VERSION = 1` |
| `vlm/receipts.py` | `Refused`, `need`, `sha256_bytes`, `sha256_file`, `bound`, `checked`, `dump_new`, `utc_now`, `canonical_json` |
| `vlm/partitions.py` | population reading, holdout refusal, run-of-record join, DEV20 slice, public/private manifests |
| `vlm/render.py` | pypdfium2 rendering to model-fit JPEG, image inputs, per-page hashes and timings |
| `vlm/schema.py` | the page-proposal JSON schema (constrained decoding + local validation), `schema_sha256` |
| `vlm/client.py` | bounded loopback HTTP: `VlmClient` (OpenAI-compatible chat) and `StageAWorkerClient` (`/parse`) |
| `vlm/textparse.py` | `parse_money`, `parse_date`, `is_date_like`, `is_money_like`, `normalise_description` |
| `vlm/tables.py` | HTML table → cell grid; column classification |
| `vlm/assemble.py` | Stage A blocks → `CandidateRow` list (`rows_from_blocks`), continuation merging |
| `vlm/metadata.py` | rule-based `AccountMeta` (beginning/ending balance, period, currency) from text lines |
| `vlm/gate.py` | `GateVerdict`, `gate(rows, meta)` — builds `analysis.schema.Statement`, calls `analysis.reconcile.reconcile`, adds date/duplicate/direction checks |
| `vlm/truth.py` | reader rows for CTRL via `tools.cohort_replay.ColdCache`; `match_rows` |
| `vlm/prompts.py` | Stage B prompt texts, `PROMPT_VERSION`, `prompt_sha256` |
| `vlm/proposals.py` | Stage B JSON → `CandidateRow`s and `AccountMeta`; page-role filtering; account grouping |
| `vlm/runner.py` | arms, per-document pipeline, render prefetch, receipts, resume |
| `vlm/report.py` | per-wave metrics, failure taxonomy, `REPORT.md` |
| `tools/vlm_ceiling.py` | CLI: `partitions`, `run`, `report` (and `preflight`, defined in part B) |
| `tests/test_vlm_*.py` | one test file per module |

Shared dataclasses (defined once, imported everywhere):

```python
# vlm/assemble.py
@dataclass(frozen=True)
class CandidateRow:
    date: str | None          # ISO YYYY-MM-DD or None
    date_text: str            # as printed
    description: str
    amount: Decimal           # POSITIVE magnitude
    direction: str            # "credit" | "debit" | "unknown"
    balance: Decimal | None
    page: int                 # 0-based page index
    source: str               # "stage_a" | "stage_b"
    locator: str              # e.g. "t0r3" (table 0 row 3) or "p2r7" (proposal row 7)
    direction_source: str = "printed"   # "printed" | "column" | "chain"

# vlm/metadata.py
@dataclass(frozen=True)
class AccountMeta:
    beginning_balance: Decimal | None
    ending_balance: Decimal | None
    period_start: str | None
    period_end: str | None
    currency: str | None
    account_last4: str | None
    bank: str | None
    sources: tuple[str, ...]   # e.g. ("beginning:rule", "ending:rule", "period:rule")
```

---

### Task 1: Package skeleton, requirements and receipt primitives

**Files:**
- Create: `requirements-vlm.txt`, `vlm/__init__.py`, `vlm/receipts.py`
- Test: `tests/test_vlm_receipts.py`

**Interfaces:**
- Produces: `Refused(code)`, `need(ok, code)`, `sha256_bytes(raw) -> str`, `sha256_file(path) -> str`, `bound(path) -> {"path","sha256"}`, `checked(item) -> item`, `dump_new(path, value)`, `utc_now() -> str`, `canonical_json(value) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_receipts.py
import json
import pytest

from vlm import receipts


def test_bound_and_checked_roundtrip(tmp_path):
    p = tmp_path / "a.json"
    p.write_bytes(b'{"x": 1}\n')
    b = receipts.bound(p)
    assert set(b) == {"path", "sha256"} and len(b["sha256"]) == 64
    assert receipts.checked(b) == b
    p.write_bytes(b'{"x": 2}\n')
    with pytest.raises(receipts.Refused) as exc:
        receipts.checked(b)
    assert exc.value.code == "binding_changed"


def test_bound_missing_refuses(tmp_path):
    with pytest.raises(receipts.Refused) as exc:
        receipts.bound(tmp_path / "missing.json")
    assert exc.value.code == "binding_missing"


def test_dump_new_is_exclusive_and_sorted(tmp_path):
    p = tmp_path / "r.json"
    receipts.dump_new(p, {"b": 1, "a": [1, 2]})
    assert p.read_text(encoding="utf-8") == '{\n  "a": [\n    1,\n    2\n  ],\n  "b": 1\n}\n'
    with pytest.raises(FileExistsError):
        receipts.dump_new(p, {"a": 1})


def test_dump_new_refuses_nan(tmp_path):
    with pytest.raises(ValueError):
        receipts.dump_new(tmp_path / "n.json", {"a": float("nan")})
    assert not (tmp_path / "n.json").exists()


def test_canonical_json_and_hash():
    assert receipts.canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert receipts.sha256_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_need_raises_closed_code():
    with pytest.raises(receipts.Refused) as exc:
        receipts.need(False, "some_code")
    assert exc.value.code == "some_code" and str(exc.value) == "some_code"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_receipts.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm'`

- [ ] **Step 3: Write the implementation**

```
# requirements-vlm.txt
pypdfium2>=5.8
jsonschema>=4.20
```

```python
# vlm/__init__.py
"""Phase 3 ceiling-experiment harness: render → self-hosted vision models → deterministic gate.

Scope and authorization: docs/moneythumb-replacement/PHASE2_RULINGS.md (R16) and
docs/moneythumb-replacement/phase3/PHASE3-VLM-PROGRAM-PLAN-v1.md (§4, §11).
"""

HARNESS_VERSION = 1
```

```python
# vlm/receipts.py
"""Receipt primitives (standard library only).

Mirrors the reviewed primitives of the Phase 2.3 campaign protocol
(`discovery_reports/train13-logs/p23config-prep/v6-step05-v2-source-01/live_protocol.py`):
a refusal is a closed snake_case code, an input is bound by absolute path + sha256,
a receipt is created exclusively and never overwritten.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Refused(RuntimeError):
    """A closed refusal code. Never a free-text message."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def need(ok: bool, code: str) -> None:
    if not ok:
        raise Refused(code)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bound(path: Path) -> dict[str, str]:
    target = Path(path)
    need(target.is_file(), "binding_missing")
    return {"path": str(target.absolute()), "sha256": sha256_file(target)}


def checked(item: dict) -> dict:
    need(isinstance(item, dict) and set(item) == {"path", "sha256"}, "binding_shape")
    target = Path(item["path"])
    need(target.is_file(), "binding_missing")
    need(sha256_file(target) == item["sha256"], "binding_changed")
    return item


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def dump_new(path: Path, value: Any) -> None:
    """Exclusive create; sorted keys; no NaN; fsynced. Serialises BEFORE opening so a
    refused value leaves no file behind."""
    text = json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with open(path, "x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_receipts.py -q -p no:cacheprovider`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add requirements-vlm.txt vlm/__init__.py vlm/receipts.py tests/test_vlm_receipts.py
git commit -m "vlm: package skeleton and receipt primitives" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Partition manifests with the holdout check

**Files:**
- Create: `vlm/partitions.py`
- Test: `tests/test_vlm_partitions.py`

**Interfaces:**
- Consumes: `discovery.runner.read_population(path) -> frozenset[str]`, `discovery.runner.holdout_sha16s_from_digest(path) -> frozenset[str]`, `vlm.receipts`.
- Produces: `Member` dataclass, `run_rows(run_dir) -> dict[str, dict]`, `set_sha256(shas) -> str`, `dev_slice(shas, n=20, seed=DEV_SEED) -> list[str]`, `refuse_holdout(shas, held16)`, `build_manifest(name, shas, *, run_dir, archive_root, holdout_digest) -> tuple[dict, dict]` (public, private), `write_manifests(out_dir, *, populations_dir, run_dir, archive_root, holdout_digest) -> dict[str, dict]`, `load_private_manifest(path) -> list[Member]`.

Facts this task relies on (verified 2026-09-17): populations are `discovery_reports/train13-logs/populations/{CTRL,U755,SLICE}.shas` (114 / 755 / 80 documents; uppercase 64-hex per line; `#` comments). The run of record is `discovery_reports/TRAIN12-52bd8f2/2026-09-11T040247.502179-0000-fd6b4d7f/` with `rows.csv` (columns include `relative_path, folder_label, content_sha256, byte_size, classification, page_count, outcome_class, account_count`) and `hash_map.csv` (`content_sha256,relative_path`). Files live under `Bank Statements/<relative_path>`. The holdout digest currently lists no members; the check must still run.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_partitions.py
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
    assert "members" not in public and "doc" not in json.dumps(public)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_partitions.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.partitions'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/partitions.py
"""Experiment populations: which documents are studied, bound by hash, holdout-checked.

Public manifests carry counts and digests only. Private manifests (`*.private.json`)
carry the archive-relative paths and are never committed.
"""
from __future__ import annotations

import csv
import hashlib
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from discovery.runner import holdout_sha16s_from_digest, read_population
from vlm.receipts import bound, dump_new, need, utc_now

DEFAULT_HOLDOUT_DIGEST = Path("docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt")
DEFAULT_POPULATIONS_DIR = Path("discovery_reports/train13-logs/populations")
DEFAULT_RUN_OF_RECORD = Path("discovery_reports/TRAIN12-52bd8f2/2026-09-11T040247.502179-0000-fd6b4d7f")
DEFAULT_ARCHIVE_ROOT = Path("Bank Statements")
DEV_SEED = "p3-ceiling-dev-v1"
DEV_SIZE = 20
MANIFEST_VERSION = 1
POPULATION_FILES = {"CTRL": "CTRL.shas", "U755": "U755.shas"}


@dataclass(frozen=True)
class Member:
    sha: str
    relative_path: str
    byte_size: int
    page_count: int
    folder_label: str
    classification: str
    outcome_class: str
    account_count: int


def run_rows(run_dir: Path) -> dict[str, dict]:
    with (Path(run_dir) / "rows.csv").open(encoding="utf-8", newline="") as handle:
        return {row["content_sha256"].upper(): row for row in csv.DictReader(handle)}


def set_sha256(shas: Iterable[str]) -> str:
    joined = "\n".join(sorted(s.upper() for s in shas)) + "\n"
    return hashlib.sha256(joined.encode("ascii")).hexdigest()


def dev_slice(shas: Iterable[str], n: int = DEV_SIZE, seed: str = DEV_SEED) -> list[str]:
    ranked = sorted({s.upper() for s in shas}, key=lambda s: hashlib.sha256(f"{seed}:{s}".encode()).hexdigest())
    return sorted(ranked[:n])


def refuse_holdout(shas: Iterable[str], held16: frozenset[str]) -> int:
    hits = sum(1 for s in shas if s[:16].upper() in held16)
    need(hits == 0, "population_overlaps_holdout")
    return hits


def _int(value: str | None) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def build_manifest(name: str, shas: Iterable[str], *, run_dir: Path = DEFAULT_RUN_OF_RECORD,
                   archive_root: Path = DEFAULT_ARCHIVE_ROOT,
                   holdout_digest: Path = DEFAULT_HOLDOUT_DIGEST) -> tuple[dict, dict]:
    ordered = sorted(s.upper() for s in shas)
    need(len(set(ordered)) == len(ordered), "population_duplicates")
    need(bool(ordered), "population_empty")
    held16 = holdout_sha16s_from_digest(Path(holdout_digest))
    overlap = refuse_holdout(ordered, held16)
    rows = run_rows(run_dir)
    members: list[Member] = []
    for sha in ordered:
        need(sha in rows, "member_not_in_run_of_record")
        row = rows[sha]
        need((Path(archive_root) / row["relative_path"]).is_file(), "member_file_missing")
        members.append(Member(
            sha=sha, relative_path=row["relative_path"], byte_size=_int(row.get("byte_size")),
            page_count=_int(row.get("page_count")), folder_label=row.get("folder_label", ""),
            classification=row.get("classification", ""), outcome_class=row.get("outcome_class", ""),
            account_count=_int(row.get("account_count")),
        ))
    public = {
        "manifest_version": MANIFEST_VERSION,
        "name": name,
        "built_at": utc_now(),
        "documents": len(members),
        "pages": sum(m.page_count for m in members),
        "set_sha256": set_sha256(ordered),
        "run_of_record": str(Path(run_dir)),
        "holdout_digest": bound(Path(holdout_digest)),
        "holdout_overlap": overlap,
        "outcome_classes": dict(sorted(Counter(m.outcome_class for m in members).items())),
        "classifications": dict(sorted(Counter(m.classification for m in members).items())),
        "page_buckets": dict(sorted(Counter(_bucket(m.page_count) for m in members).items())),
        "multi_account_documents": sum(1 for m in members if m.account_count > 1),
    }
    private = {
        "manifest_version": MANIFEST_VERSION,
        "name": name,
        "set_sha256": public["set_sha256"],
        "archive_root": str(Path(archive_root)),
        "members": [asdict(m) for m in members],
    }
    return public, private


def _bucket(pages: int) -> str:
    if pages <= 1:
        return "1"
    if pages <= 5:
        return "2-5"
    if pages <= 15:
        return "6-15"
    return "16+"


def write_manifests(out_dir: Path, *, populations_dir: Path = DEFAULT_POPULATIONS_DIR,
                    run_dir: Path = DEFAULT_RUN_OF_RECORD, archive_root: Path = DEFAULT_ARCHIVE_ROOT,
                    holdout_digest: Path = DEFAULT_HOLDOUT_DIGEST, dev_size: int = DEV_SIZE) -> dict[str, dict]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    populations = {name: read_population(Path(populations_dir) / file) for name, file in POPULATION_FILES.items()}
    populations["DEV"] = frozenset(dev_slice(populations["CTRL"], n=dev_size))
    summary: dict[str, dict] = {}
    for name, shas in populations.items():
        public, private = build_manifest(name, shas, run_dir=run_dir, archive_root=archive_root,
                                         holdout_digest=holdout_digest)
        dump_new(out / f"{name}.manifest.private.json", private)
        public["members_sha256"] = bound(out / f"{name}.manifest.private.json")["sha256"]
        dump_new(out / f"{name}.manifest.json", public)
        summary[name] = public
    return summary


def load_private_manifest(path: Path) -> list[Member]:
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    need(data.get("manifest_version") == MANIFEST_VERSION, "manifest_version_unexpected")
    return [Member(**m) for m in data["members"]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_partitions.py -q -p no:cacheprovider`
Expected: `5 passed`

- [ ] **Step 5: Confirm the private output location is ignored by git**

Run: `git check-ignore -v discovery_reports/train13-logs/p3ceiling/x.private.json; git check-ignore -v discovery_reports/train13-logs/p3ceiling/manifests/CTRL.manifest.private.json`
Expected: both paths print a matching `.gitignore` rule. If either prints nothing, add `discovery_reports/train13-logs/p3ceiling/**/*.private.json` and `discovery_reports/train13-logs/p3ceiling/**/rasters/` to `.gitignore` in this task and commit the `.gitignore` change with it.

- [ ] **Step 6: Commit**

```bash
git add vlm/partitions.py tests/test_vlm_partitions.py
git commit -m "vlm: partition manifests with holdout refusal" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Renderer (pypdfium2, model-fit JPEG, hashes, timings)

**Files:**
- Create: `vlm/render.py`
- Test: `tests/test_vlm_render.py`

**Interfaces:**
- Produces: `RenderedPage` dataclass, `DEFAULT_LONG_EDGE = 1540`, `DEFAULT_JPEG_QUALITY = 90`, `RENDER_VERSION = 1`, `page_count(pdf_bytes) -> int`, `render_pages(pdf_bytes, *, long_edge, quality, page_indices=None) -> list[RenderedPage]`, `render_image(raw, *, long_edge, quality, index=0) -> RenderedPage`, `render_document(raw, *, long_edge, quality) -> list[RenderedPage]` (dispatches on `%PDF` magic), `render_settings() -> dict`.

Facts: local pypdfium2 5.8.0 (pdfium build 7825), host venv pypdfium2 5.13.0. API used: `pdfium.PdfDocument(bytes)`, `len(doc)`, `doc[i]`, `page.get_size() -> (w_pt, h_pt)`, `page.get_rotation()`, `page.render(scale=...)` → bitmap, `bitmap.to_pil()`, `page.close()`, `doc.close()`. pdfium renders the CropBox and applies `/Rotate`, matching `ocr/rasterize.py` `RASTER_VERSION = 2` semantics.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_render.py
import io

from PIL import Image

from tests.paddle_synthetic import build_ledger_page, render_native_pdf
from vlm import render


def _pdf() -> bytes:
    return render_native_pdf(build_ledger_page(n_rows=4))


def test_page_count_and_dimensions():
    pdf = _pdf()
    assert render.page_count(pdf) == 1
    pages = render.render_pages(pdf, long_edge=1000)
    assert len(pages) == 1
    page = pages[0]
    assert page.index == 0 and max(page.width, page.height) == 1000
    assert page.pdf_width_pt == 612.0 and page.pdf_height_pt == 792.0
    assert page.jpeg[:3] == b"\xff\xd8\xff"
    assert Image.open(io.BytesIO(page.jpeg)).size == (page.width, page.height)
    assert page.render_ms >= 0 and page.encode_ms >= 0


def test_render_is_deterministic():
    a = render.render_pages(_pdf())[0]
    b = render.render_pages(_pdf())[0]
    assert a.jpeg_sha256 == b.jpeg_sha256 and a.pixel_sha256 == b.pixel_sha256


def test_page_indices_subset():
    pdf = _pdf()
    assert render.render_pages(pdf, page_indices=[]) == []
    assert [p.index for p in render.render_pages(pdf, page_indices=[0])] == [0]


def test_render_image_input():
    image = Image.new("RGB", (400, 200), (255, 255, 255))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    page = render.render_image(buf.getvalue(), long_edge=800)
    assert (page.width, page.height) == (800, 400) and page.pdf_width_pt == 0.0


def test_render_document_dispatches_on_magic():
    assert len(render.render_document(_pdf())) == 1
    image = Image.new("RGB", (10, 10))
    buf = io.BytesIO()
    image.save(buf, format="JPEG")
    assert len(render.render_document(buf.getvalue())) == 1


def test_render_settings_are_pinned():
    settings = render.render_settings()
    assert settings["render_version"] == 1 and settings["long_edge"] == 1540 and settings["jpeg_quality"] == 90
    assert settings["pdfium_version"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_render.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.render'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/render.py
"""Page rendering for the vision models: pdfium in-process, model-fit JPEG, hashes, timings.

No PyMuPDF (AGPL) and no subprocess. Nothing is written to disk; page bytes exist only in
memory, as in `ocr/paddle_rung.py`.
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass
from typing import Iterable

import pypdfium2 as pdfium
from PIL import Image

from vlm.receipts import sha256_bytes

DEFAULT_LONG_EDGE = 1540
DEFAULT_JPEG_QUALITY = 90
RENDER_VERSION = 1
PDF_MAGIC = b"%PDF"


@dataclass(frozen=True)
class RenderedPage:
    index: int
    width: int
    height: int
    jpeg: bytes
    jpeg_sha256: str
    pixel_sha256: str
    pdf_width_pt: float
    pdf_height_pt: float
    rotation_deg: int
    render_ms: float
    encode_ms: float


def render_settings() -> dict:
    return {
        "render_version": RENDER_VERSION,
        "renderer": "pypdfium2",
        "pypdfium2_version": pdfium.V_PYPDFIUM2 if hasattr(pdfium, "V_PYPDFIUM2") else getattr(pdfium, "__version__", ""),
        "pdfium_version": str(getattr(getattr(pdfium, "PDFIUM_INFO", None), "build", "")),
        "long_edge": DEFAULT_LONG_EDGE,
        "jpeg_quality": DEFAULT_JPEG_QUALITY,
    }


def page_count(pdf_bytes: bytes) -> int:
    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        return len(doc)
    finally:
        doc.close()


def _encode(image: Image.Image, quality: int) -> tuple[bytes, str, float]:
    started = time.perf_counter()
    if image.mode != "RGB":
        image = image.convert("RGB")
    pixel_sha = sha256_bytes(image.tobytes())
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, subsampling=0)
    return buffer.getvalue(), pixel_sha, (time.perf_counter() - started) * 1000.0


def _fit(image: Image.Image, long_edge: int) -> Image.Image:
    longest = max(image.width, image.height)
    if longest == long_edge:
        return image
    scale = long_edge / longest
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.LANCZOS)


def render_pages(pdf_bytes: bytes, *, long_edge: int = DEFAULT_LONG_EDGE,
                 quality: int = DEFAULT_JPEG_QUALITY,
                 page_indices: Iterable[int] | None = None) -> list[RenderedPage]:
    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        indices = list(range(len(doc))) if page_indices is None else list(page_indices)
        pages: list[RenderedPage] = []
        for index in indices:
            page = doc[index]
            try:
                width_pt, height_pt = page.get_size()
                scale = long_edge / max(width_pt, height_pt)
                started = time.perf_counter()
                image = page.render(scale=scale).to_pil()
                render_ms = (time.perf_counter() - started) * 1000.0
                image = _fit(image, long_edge)
                jpeg, pixel_sha, encode_ms = _encode(image, quality)
                pages.append(RenderedPage(
                    index=index, width=image.width, height=image.height, jpeg=jpeg,
                    jpeg_sha256=sha256_bytes(jpeg), pixel_sha256=pixel_sha,
                    pdf_width_pt=float(width_pt), pdf_height_pt=float(height_pt),
                    rotation_deg=int(page.get_rotation()), render_ms=render_ms, encode_ms=encode_ms,
                ))
            finally:
                page.close()
        return pages
    finally:
        doc.close()


def render_image(raw: bytes, *, long_edge: int = DEFAULT_LONG_EDGE, quality: int = DEFAULT_JPEG_QUALITY,
                 index: int = 0) -> RenderedPage:
    started = time.perf_counter()
    with Image.open(io.BytesIO(raw)) as opened:
        opened.load()
        image = _fit(opened.convert("RGB"), long_edge)
    render_ms = (time.perf_counter() - started) * 1000.0
    jpeg, pixel_sha, encode_ms = _encode(image, quality)
    return RenderedPage(index=index, width=image.width, height=image.height, jpeg=jpeg,
                        jpeg_sha256=sha256_bytes(jpeg), pixel_sha256=pixel_sha, pdf_width_pt=0.0,
                        pdf_height_pt=0.0, rotation_deg=0, render_ms=render_ms, encode_ms=encode_ms)


def render_document(raw: bytes, *, long_edge: int = DEFAULT_LONG_EDGE,
                    quality: int = DEFAULT_JPEG_QUALITY) -> list[RenderedPage]:
    if raw[:4] == PDF_MAGIC:
        return render_pages(raw, long_edge=long_edge, quality=quality)
    return [render_image(raw, long_edge=long_edge, quality=quality)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_render.py -q -p no:cacheprovider`
Expected: `6 passed`. If `V_PYPDFIUM2`/`PDFIUM_INFO` attribute names differ on the installed version, print `dir(pypdfium2)` once and use the attributes that hold the version strings; the test only requires a non-empty `pdfium_version`.

- [ ] **Step 5: Commit**

```bash
git add vlm/render.py tests/test_vlm_render.py
git commit -m "vlm: pdfium renderer with model-fit JPEG output" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

Continue with part 2 (`2026-09-17-ceiling-harness-part2.md`): schema, HTTP clients, text parsing, tables, assembly, metadata rules.
