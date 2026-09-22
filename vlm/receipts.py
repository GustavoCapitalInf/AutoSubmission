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
