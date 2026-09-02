"""provenance.py — one durable record of WHAT produced a discovery run: host,
toolchain, tree, settings keys, corpus inventory, cache posture, environment.

    python tools/train/provenance.py --checkout <tree> --root "<corpus root>" \
        --data-dir <cache dir> --out <run dir>/provenance.json \
        [--label X] [--hash-corpus] [--mode digital|scanned|scanned-visual|profile-only|dry-run]

Written before a run (the cold-cache proof: the cache's entry counts are 0)
and again after it (into the run directory). Every field is measured on this
host at the time of the call; nothing is quoted from a record. The tree is
introspected in a SUBPROCESS with cwd=<checkout> so that a batch-7 worktree
(302f8f2) and the train are read by their own code, never by the caller's.

Secrets are never written: API-key environment variables are recorded as
set/unset only. The JSON is the record; a Markdown twin is written beside it.

``run_of_record.partitions`` (P20-ARTIFACTS, Phase 2.0, OQ10)
---------------------------------------------------------------
``ocr_settings_key_default`` / ``ocr_settings_key_local`` (the ``tree`` block)
have always been computed from :func:`webapp.artifact_cache.ocr_settings_key`'s
OWN default arguments — ``force_ocr=False, allow_local_ocr=False,
allow_visual_ocr=True`` and ``allow_local_ocr=True, allow_visual_ocr=True``
respectively. **Neither is a key the runner ever actually uses**:
``discovery/runner.py`` calls the offline read with ``allow_visual_ocr=False``
and the escalation read with ``force_ocr=True, allow_visual_ocr=True`` — two
call shapes distinguished by ``force_ocr``, which the two fields above never
vary. Both are kept, unchanged, for continuity with every provenance.json
this cell predates (including the batch-8 and batch-9 records
``telemetry/run_of_record.py`` reconstructs from). Pass ``--mode`` (the run's
actual mode — the caller, e.g. ``tools/train/coldrun.sh``, already knows it;
it is not discoverable from a pre-run provenance call) to additionally record
the CORRECT pair under the top-level ``run_of_record.partitions`` key
(``offline_ocr_key``, ``visual_ocr_key``, ``analysis_key``, ``mode``),
computed from the run's actual flags via the same ``mode in LOCAL_OCR_MODES``
test ``DiscoveryRunner.__init__`` uses. A run recorded with ``--mode`` is read
by ``telemetry/run_of_record.py`` as ``origin="recorded"``; a run recorded
without it (or written before this cell) is deterministically RECONSTRUCTED
and verified against its own cache index instead.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

#: Environment knobs that change what a run computes or reads. Values are
#: recorded verbatim except for the secret-shaped ones, which are set/unset.
ENV_KNOBS = [
    "WEBAPP_DATA_DIR", "WITHHOLDING_DENOMINATOR_MODE", "GENERIC_STRUCTURER_ENABLED",
    "POPPLER_PATH", "TESSDATA_PREFIX", "OCR_BASE_URL", "OCR_MODEL", "OCR_MAX_WORKERS",
    "OCR_TIMEOUT", "OCR_RETRIES", "OCR_WINDOW_SIZE", "OCR_NGRAM_SIZE",
    "GEMINI_MODEL", "GEMINI_ESCALATION_MODEL", "PYTHONHASHSEED",
]
SECRET_KNOBS = ["OCR_API_KEY", "GEMINI_API_KEY"]

#: Run inside the checkout: the tree's own constants, keys and inventory.
_TREE_PROBE = r'''
import json, sys
out = {}
def attempt(name, fn):
    try:
        out[name] = fn()
    except Exception as exc:  # recorded, never fatal
        out[name] = {"error": f"{type(exc).__name__}: {exc}"}
import webapp.artifact_cache as ac
attempt("ANALYSIS_STAGE_VERSION", lambda: ac.ANALYSIS_STAGE_VERSION)
attempt("OCR_STAGE_VERSION", lambda: ac.OCR_STAGE_VERSION)
attempt("CACHE_FORMAT_VERSION", lambda: getattr(ac, "CACHE_FORMAT_VERSION", None))
attempt("analysis_settings_key_deterministic", lambda: ac.analysis_settings_key(parse_mode="deterministic"))
attempt("ocr_settings_key_default", lambda: ac.ocr_settings_key())
attempt("ocr_settings_key_local", lambda: ac.ocr_settings_key(allow_local_ocr=True))
def run_of_record_partitions():
    # P20-ARTIFACTS (Phase 2.0, OQ10, §10 of PROVENANCE-RECORDS-ACTUAL-PARTITIONS):
    # `ocr_settings_key_default` / `_local` above call `ocr_settings_key()`
    # with ITS OWN defaults (`force_ocr=False, allow_local_ocr=False,
    # allow_visual_ocr=True` / `allow_local_ocr=True, allow_visual_ocr=True`)
    # — neither is the call shape `discovery/runner.py` actually makes
    # (`allow_visual_ocr=False` on the offline read, `force_ocr=True,
    # allow_visual_ocr=True` on the escalation read). They are kept, unchanged,
    # for continuity with every provenance record before this cell; this block
    # is the CORRECT one, computed from `--mode` (the run's actual flag,
    # passed by the caller) via the same `mode in LOCAL_OCR_MODES` test
    # `DiscoveryRunner.__init__` uses. `telemetry/run_of_record.py` reads this
    # block directly for a run written by this cell forward, and
    # deterministically RECONSTRUCTS the equivalent for a run that predates it.
    mode = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
    if not mode:
        return {"note": "no --mode given to this provenance call; a run's "
                        "actual partitions were not recorded"}
    from discovery.runner import LOCAL_OCR_MODES
    allow_local_ocr = mode in LOCAL_OCR_MODES
    partitions = {
        "offline_ocr_key": ac.ocr_settings_key(force_ocr=False, allow_local_ocr=allow_local_ocr,
                                               allow_visual_ocr=False),
        "visual_ocr_key": ac.ocr_settings_key(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True),
        "analysis_key": ac.analysis_settings_key(parse_mode="deterministic"),
        "mode": mode,
    }
    # P21-ROUTING (Phase 2.1, design item 7): the Paddle partition, recorded
    # ONLY when Paddle settings actually load from this host's environment —
    # never a placeholder key. Most hosts running provenance have no
    # PADDLE_* configuration set, and that is the expected, common case: the
    # key is simply omitted, with a note, rather than guessed.
    try:
        partitions["paddle_ocr_key"] = ac.ocr_settings_key(
            force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False,
            allow_paddle_ocr=True,
        )
    except Exception as exc:  # PaddleConfigError, most commonly: recorded, never fatal
        # P21-ROUTING closure (MINOR-5): the exception's own message is NEVER
        # written verbatim — only the class name, plus the CLOSED-vocabulary
        # `.reason` a `PaddleRefused` carries (never `PaddleConfigError`'s own
        # message, which can name an arbitrary configuration variable's
        # surrounding text). `provenance.json` is a durable run record this
        # module's own closure reports quote; an unbounded `str(exc)` is
        # exactly the "an exception message can quote content" hazard this
        # tree refuses everywhere else, even though today's realistic
        # exception (`PaddleConfigError`) happens to name only variables.
        from ocr.paddle_config import REFUSAL_REASONS
        reason = getattr(exc, "reason", None)
        if isinstance(reason, str) and reason in REFUSAL_REASONS:
            partitions["paddle_ocr_key_note"] = f"not recorded: {type(exc).__name__}: {reason}"
        else:
            partitions["paddle_ocr_key_note"] = f"not recorded: {type(exc).__name__}"
    return partitions
attempt("run_of_record_partitions", run_of_record_partitions)
def registry():
    import analysis.parser_registry as pr
    regs = pr.registrations()
    fp = getattr(pr, "registry_fingerprint", None)
    return {"count": len(regs), "fingerprint": fp() if callable(fp) else None,
            "REGISTRY_MATERIAL_VERSION": getattr(pr, "REGISTRY_MATERIAL_VERSION", None)}
attempt("registry", registry)
def observer():
    import telemetry.stated_counts as sc
    return sc.OBSERVER_VERSION
attempt("OBSERVER_VERSION", observer)
def inventory():
    from pathlib import Path
    import discovery.inventory as inv
    root = Path(sys.argv[1])
    result = inv.enumerate_root(root)
    fields = {}
    for name in ("files", "pdfs", "total_bytes", "bytes", "pinned", "discovery"):
        if hasattr(result, name):
            fields[name] = getattr(result, name)
    if not fields:
        try:
            fields = dict(result._asdict())
        except Exception:
            fields = {"repr": repr(result)[:400]}
    fields = {k: (v if isinstance(v, (int, float, str, type(None))) else (len(v) if hasattr(v, "__len__") else repr(v)[:200]))
              for k, v in fields.items()}
    fields["frozen"] = {k: getattr(inv, k) for k in dir(inv) if k.startswith("FROZEN_")}
    fields["baseline_deviations"] = list(inv.baseline_deviations(result))
    return fields
attempt("inventory", inventory)
print(json.dumps(out, default=str))
'''


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 600) -> dict:
    try:
        completed = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return {"exit": completed.returncode, "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip()[-2000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"exit": None, "error": f"{type(exc).__name__}: {exc}"}


def _first_lines(text: str, n: int = 2) -> list[str]:
    return [line for line in text.splitlines() if line.strip()][:n]


def _memory_total_bytes() -> int | None:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullTotalPhys)
        return None
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        return None


def _git(checkout: Path, *args: str) -> str:
    result = _run(["git", *args], cwd=checkout)
    return result.get("stdout", "") if result.get("exit") == 0 else f"<git {' '.join(args)} failed: {result}>"


def _cache_posture(data_dir: Path) -> dict:
    posture = {"path": str(data_dir), "exists": data_dir.exists()}
    for stage in ("ocr", "analysis", "report"):
        stage_dir = data_dir / "artifacts" / stage
        posture[f"{stage}_entries"] = (
            sum(1 for _ in stage_dir.rglob("*.json")) if stage_dir.exists() else 0)
    posture["webapp_db"] = (data_dir / "webapp.db").exists()
    return posture


def _corpus_hashes(root: Path) -> dict:
    digests: set[str] = set()
    count = 0
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() == ".pdf":
            count += 1
            h = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b""):
                    h.update(chunk)
            digests.add(h.hexdigest().upper())
    return {"pdf_files_hashed": count, "distinct_pdf_sha256": len(digests)}


def collect(checkout: Path, root: Path, data_dir: Path, *, label: str, hash_corpus: bool,
           mode: str | None = None) -> dict:
    python = sys.executable
    tesseract = shutil.which("tesseract")
    pdftoppm = shutil.which("pdftoppm")
    # The probe imports the tree's cache module, which materialises its data
    # directory on import; point it at a throwaway so the REAL cache directory
    # is only ever measured here (its cold posture must be observed, not made).
    import tempfile
    with tempfile.TemporaryDirectory(prefix="provenance-probe-") as throwaway:
        probe_env = {**os.environ, "WEBAPP_DATA_DIR": throwaway}
        try:
            completed = subprocess.run([python, "-c", _TREE_PROBE, str(root), mode or ""], cwd=checkout,
                                       capture_output=True, text=True, timeout=900, env=probe_env)
            tree_probe = {"exit": completed.returncode, "stdout": completed.stdout.strip(),
                          "stderr": completed.stderr.strip()[-2000:]}
        except (OSError, subprocess.TimeoutExpired) as exc:
            tree_probe = {"exit": None, "error": f"{type(exc).__name__}: {exc}"}
    try:
        tree = json.loads(tree_probe["stdout"]) if tree_probe.get("exit") == 0 else {"error": tree_probe}
    except json.JSONDecodeError:
        tree = {"error": tree_probe}
    # P20-ARTIFACTS: lift the probe's flat `run_of_record_partitions` into the
    # top-level shape `telemetry/run_of_record.py` reads
    # (`provenance["run_of_record"]["partitions"]`), beside `tree`/`env`/etc.
    # rather than nested inside `tree` — a RECORDED run and a RECONSTRUCTED
    # one read the SAME provenance.json shape either way.
    run_of_record_block = None
    if isinstance(tree, dict):
        partitions = tree.pop("run_of_record_partitions", None)
        if isinstance(partitions, dict) and "offline_ocr_key" in partitions:
            run_of_record_block = {"partitions": partitions}
    record = {
        "label": label,
        "recorded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpus": os.cpu_count(),
            "ram_total_bytes": _memory_total_bytes(),
        },
        "python": {
            "version": sys.version.split()[0],
            "executable": python,
            "pip_freeze": _run([python, "-m", "pip", "freeze"]).get("stdout", "").splitlines(),
        },
        "toolchain": {
            "tesseract_path": tesseract,
            "tesseract_version": _first_lines(_run([tesseract, "--version"]).get("stderr", "")
                                              + "\n" + _run([tesseract, "--version"]).get("stdout", ""))
            if tesseract else None,
            "pdftoppm_path": pdftoppm,
            "pdftoppm_version": _first_lines(_run([pdftoppm, "-v"]).get("stderr", "")
                                             + "\n" + _run([pdftoppm, "-v"]).get("stdout", ""), 1)
            if pdftoppm else None,
            "pymupdf": _run([python, "-c", "import fitz; print(getattr(fitz, 'VersionBind', None) or fitz.version)"]).get("stdout"),
            "pytesseract": _run([python, "-c", "import pytesseract; print(pytesseract.__version__)"]).get("stdout"),
            "pillow": _run([python, "-c", "import PIL; print(PIL.__version__)"]).get("stdout"),
        },
        "git": {
            "checkout": str(checkout),
            "head": _git(checkout, "rev-parse", "HEAD"),
            "branch": _git(checkout, "rev-parse", "--abbrev-ref", "HEAD"),
            "dirty_entries": len([line for line in _git(checkout, "status", "--porcelain").splitlines() if line.strip()]),
        },
        "tree": tree,
        "corpus": {"root": str(root)},
        "cache": _cache_posture(data_dir),
        "env": {
            **{k: os.environ.get(k) for k in ENV_KNOBS},
            **{k: ("set" if os.environ.get(k) else "unset") for k in SECRET_KNOBS},
        },
    }
    if run_of_record_block is not None:
        record["run_of_record"] = run_of_record_block
    if hash_corpus:
        record["corpus"].update(_corpus_hashes(root))
    return record


def render(record: dict) -> str:
    tree = record.get("tree", {})
    inv = tree.get("inventory", {}) if isinstance(tree, dict) else {}
    rows = [
        ("label", record["label"]), ("recorded", record["recorded_utc"]),
        ("host", f"{record['host']['hostname']} · {record['host']['platform']} · {record['host']['cpus']} cpus · "
                 f"{(record['host']['ram_total_bytes'] or 0) / 1024 ** 3:.1f} GB"),
        ("python", f"{record['python']['version']} ({record['python']['executable']})"),
        ("tesseract", " / ".join(record["toolchain"]["tesseract_version"] or ["<not found>"])),
        ("poppler", " / ".join(record["toolchain"]["pdftoppm_version"] or ["<not found>"])),
        ("pymupdf", record["toolchain"]["pymupdf"]), ("pytesseract", record["toolchain"]["pytesseract"]),
        ("pillow", record["toolchain"]["pillow"]),
        ("tree", f"{record['git']['head'][:12]} ({record['git']['branch']}; dirty entries {record['git']['dirty_entries']})"),
        ("ANALYSIS_STAGE_VERSION", tree.get("ANALYSIS_STAGE_VERSION")), ("OCR_STAGE_VERSION", tree.get("OCR_STAGE_VERSION")),
        ("registry", json.dumps(tree.get("registry"))), ("OBSERVER_VERSION", tree.get("OBSERVER_VERSION")),
        ("analysis key (deterministic)", tree.get("analysis_settings_key_deterministic")),
        ("ocr key (default)", tree.get("ocr_settings_key_default")), ("ocr key (local)", tree.get("ocr_settings_key_local")),
        ("run_of_record.partitions", json.dumps(record.get("run_of_record", {}).get("partitions"))
         if record.get("run_of_record") else "not recorded (--mode not given)"),
        ("corpus root", record["corpus"]["root"]),
        ("inventory", json.dumps({k: v for k, v in inv.items() if k not in ("frozen",)}) if isinstance(inv, dict) else inv),
        ("frozen constants", json.dumps(inv.get("frozen")) if isinstance(inv, dict) else None),
        ("distinct pdf sha256", record["corpus"].get("distinct_pdf_sha256")),
        ("cache", json.dumps(record["cache"])),
        ("env", json.dumps({k: v for k, v in record["env"].items() if v not in (None, "unset")})),
        ("pip freeze", f"{len(record['python']['pip_freeze'])} packages"),
    ]
    lines = [f"# provenance — {record['label']}", "", "| field | value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in rows]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--label", default="")
    parser.add_argument("--hash-corpus", action="store_true",
                        help="also hash every PDF under --root (distinct sha count; ~1 GB read)")
    parser.add_argument("--mode", default=None,
                        help="the discovery run's actual mode (digital/scanned/scanned-visual/"
                             "profile-only/dry-run) — records run_of_record.partitions computed "
                             "from THIS run's flags (P20-ARTIFACTS). Omit to leave partitions "
                             "unrecorded, as every provenance.json before this cell does.")
    args = parser.parse_args(argv)
    try:  # the Windows console is cp1252; the files are UTF-8 regardless
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    record = collect(args.checkout.resolve(), args.root.resolve(), args.data_dir.resolve(),
                     label=args.label, hash_corpus=args.hash_corpus, mode=args.mode)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2, sort_keys=True, default=str), encoding="utf-8")
    args.out.with_suffix(".md").write_text(render(record), encoding="utf-8")
    print(render(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
