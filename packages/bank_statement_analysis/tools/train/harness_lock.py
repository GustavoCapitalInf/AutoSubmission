"""harness_lock.py — the ONE host-lock helper for heavy proofs on this shared Windows/OneDrive host.

    python tools/train/harness_lock.py acquire <lock-dir> <holder-name> [--poll-seconds 1]
    python tools/train/harness_lock.py release <lock-dir> <holder-name>
    python tools/train/harness_lock.py status  <lock-dir>

Rules (Phase 2.2 / 2.3 lock incidents, recorded in BATCH9_TRANSITION.md §7 and the P23-EGATE review):

* ACQUIRE is `os.mkdir` and nothing else — an atomic create. If the directory exists, someone holds it,
  and the caller WAITS (unbounded, polling at 1 s: a 10-second poll lost every handover on this host).
  A waiter that finds the lock held by ITS OWN holder name is NOT the holder (an earlier driver of the
  same cell is): it keeps waiting. That is the defect every hand-rolled copy of this idiom had — it
  returned success and two drivers ran concurrently on a memory-tight host.
* The holder writes `holder.txt` INSIDE the directory it created — never into a directory it did not.
* RELEASE removes the directory ONLY when `holder.txt` names the caller. `os.rmdir` is retried on the
  OneDrive `PermissionError`; after a few refusals the Git bash `rmdir` is used (it succeeds where Python
  is refused); release is reported only when the directory is confirmed GONE.
* An orphan (an EMPTY lock directory with no holder file) is never removed here: that is the lead
  orchestrator's call, by hand, after `tasklist` shows no runner.

Exit codes: 0 ok · 2 usage · 3 release refused (not the holder) · 4 release failed (directory persists).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

GIT_BASH = Path(r"C:\Program Files\Git\bin\bash.exe")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _holder(lock: Path) -> str | None:
    holder = lock / "holder.txt"
    try:
        return holder.read_text(encoding="utf-8").strip() if holder.exists() else None
    except OSError:
        return None


def acquire(lock: Path, name: str, poll_seconds: float = 1.0, log=print) -> int:
    waited = 0.0
    last_report = -600.0
    while True:
        try:
            lock.mkdir()
        except FileExistsError:
            if waited - last_report >= 600:
                held = _holder(lock) or "<no holder file — an orphan; ask the lead to remove it by hand>"
                log(f"{_stamp()} LOCK held by: {held}; waiting ({int(waited)}s)")
                last_report = waited
            time.sleep(poll_seconds)
            waited += poll_seconds
            continue
        (lock / "holder.txt").write_text(f"{name} acquired {_stamp()} pid={os.getpid()}\n", encoding="utf-8")
        log(f"{_stamp()} LOCK acquired by {name} after {int(waited)}s")
        return 0


def release(lock: Path, name: str, log=print) -> int:
    held = _holder(lock)
    if not lock.exists():
        log(f"{_stamp()} LOCK release: directory absent (nothing to release)")
        return 0
    if held is None or not held.startswith(name + " "):
        log(f"{_stamp()} LOCK release REFUSED: holder is {held!r}, not {name!r}")
        return 3
    holder = lock / "holder.txt"
    for attempt in range(1, 61):
        try:
            if holder.exists():
                holder.unlink()
            if lock.exists():
                os.rmdir(lock)
        except PermissionError:
            if attempt >= 5 and GIT_BASH.exists():
                subprocess.run([str(GIT_BASH), "-c", f"rmdir '{lock.as_posix()}'"], capture_output=True)
        except FileNotFoundError:
            pass
        if not lock.exists():
            log(f"{_stamp()} LOCK released by {name} (attempt {attempt})")
            return 0
        time.sleep(5)
    log(f"{_stamp()} LOCK release FAILED: directory persists after 60 attempts")
    return 4


def status(lock: Path, log=print) -> int:
    if not lock.exists():
        log("free")
    else:
        log(f"held: {_holder(lock) or '<no holder file — orphan>'}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("acquire"); a.add_argument("lock"); a.add_argument("name"); a.add_argument("--poll-seconds", type=float, default=1.0)
    r = sub.add_parser("release"); r.add_argument("lock"); r.add_argument("name")
    s = sub.add_parser("status"); s.add_argument("lock")
    args = parser.parse_args(argv)
    lock = Path(args.lock)
    if args.cmd == "acquire":
        return acquire(lock, args.name, args.poll_seconds)
    if args.cmd == "release":
        return release(lock, args.name)
    return status(lock)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
