"""The repository-side export of the sealed store (P22-HOLDOUT item 1; R3:
"expose only a non-sensitive manifest/hash/version to the repository where
reproducibility requires one").

`docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt` carries ONLY:

    store_version, record_count, chain_head (truth.jsonl),
    holdout_chain_head (holdout.jsonl),
    the sorted sha16 prefixes of adjudicated documents (no verdicts),
    the holdout manifest's sha16 prefixes with their status.

Every line matches one pattern of `DIGEST_LINE_GRAMMAR`; a verdict, kind,
figure, date, name or path has no line shape to live in. The grammar is
the interface for the runner's research-mode refusal (cell T reads this file
with its own few lines — it may not import this package): a holdout entry is
`- <SHA16> <status>` under the `holdout_sha16_status:` header.
"""
from __future__ import annotations

import re
from pathlib import Path

from .manifest import HOLDOUT_STATUSES, HoldoutManifest
from .store import GENESIS, STORE_VERSION, TruthStore, _retry, _this_checkout_root

DIGEST_RELATIVE = Path("docs") / "moneythumb-replacement" / "truth" / "MANIFEST_DIGEST.txt"

HEADER_LINES = (
    "# MANIFEST_DIGEST: the sealed truth store's non-sensitive export (tools/holdout/digest.py).",
    "# Store version, record count, chain heads and sha16 prefixes only; no verdict lives here.",
    "# Regenerate: python -m tools.adjudicate export-digest",
)

_STATUS_ALTERNATION = "|".join(HOLDOUT_STATUSES)
DIGEST_LINE_GRAMMAR = tuple(re.compile(re.escape(line)) for line in HEADER_LINES) + (
    re.compile(r"store_version: \d+"),
    re.compile(r"record_count: \d+"),
    re.compile(r"chain_head: (?:GENESIS|[0-9a-f]{64})"),
    re.compile(r"holdout_chain_head: (?:GENESIS|[0-9a-f]{64})"),
    re.compile(r"adjudicated_sha16:"),
    re.compile(r"holdout_sha16_status:"),
    re.compile(r"- [0-9A-F]{16}"),
    re.compile(rf"- [0-9A-F]{{16}} (?:{_STATUS_ALTERNATION})"),
)


def default_digest_path() -> Path:
    return _this_checkout_root() / DIGEST_RELATIVE


def render_digest(store: TruthStore | None, manifest: HoldoutManifest | None) -> str:
    if store is None:
        record_count, chain_head, sha16s = 0, GENESIS, []
    else:
        records = store.records()
        chain_head = store.verify_chain()
        record_count = len(records)
        sha16s = store.adjudicated_sha16s()
    if manifest is None:
        holdout_head, statuses = GENESIS, []
    else:
        holdout_head = manifest.verify_chain()
        statuses = manifest.sha16_statuses()
    lines = list(HEADER_LINES)
    lines.append(f"store_version: {STORE_VERSION}")
    lines.append(f"record_count: {record_count}")
    lines.append(f"chain_head: {chain_head}")
    lines.append(f"holdout_chain_head: {holdout_head}")
    lines.append("adjudicated_sha16:")
    lines.extend(f"- {sha16}" for sha16 in sha16s)
    lines.append("holdout_sha16_status:")
    lines.extend(f"- {sha16} {status}" for sha16, status in statuses)
    text = "\n".join(lines) + "\n"
    for line in text.splitlines():
        if not any(pattern.fullmatch(line) for pattern in DIGEST_LINE_GRAMMAR):
            raise ValueError(f"digest line outside the grammar: {line!r}")
    return text


def parse_digest(text: str) -> dict:
    """The digest as a mapping; the same grammar, read back."""
    result: dict = {
        "store_version": None,
        "record_count": None,
        "chain_head": None,
        "holdout_chain_head": None,
        "adjudicated_sha16": [],
        "holdout_sha16_status": [],
    }
    section = None
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        if not any(pattern.fullmatch(line) for pattern in DIGEST_LINE_GRAMMAR):
            raise ValueError(f"digest line outside the grammar: {line!r}")
        if line.startswith("- "):
            parts = line[2:].split()
            if section == "adjudicated_sha16" and len(parts) == 1:
                result["adjudicated_sha16"].append(parts[0])
            elif section == "holdout_sha16_status" and len(parts) == 2:
                result["holdout_sha16_status"].append((parts[0], parts[1]))
            else:
                raise ValueError(f"entry outside its section: {line!r}")
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if key in ("adjudicated_sha16", "holdout_sha16_status"):
            section = key
        elif key in ("store_version", "record_count"):
            result[key] = int(value)
        else:
            result[key] = value
    return result


def write_digest(text: str, path: Path | None = None) -> Path:
    target = default_digest_path() if path is None else Path(path)

    def _write():
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    _retry(_write)
    return target


def export_digest(env=None, path: Path | None = None) -> Path:
    """Open the store and the manifest at `SEALED_TRUTH_DIR`, write the digest."""
    return write_digest(render_digest(TruthStore.open(env), HoldoutManifest.open(env)), path)


__all__ = [
    "DIGEST_LINE_GRAMMAR",
    "DIGEST_RELATIVE",
    "default_digest_path",
    "export_digest",
    "parse_digest",
    "render_digest",
    "write_digest",
]
