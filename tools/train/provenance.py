"""provenance.py — one durable record of WHAT produced a discovery run: host,
toolchain, tree, settings keys, corpus inventory, cache posture, environment.

    python tools/train/provenance.py --checkout <tree> --root "<corpus root>" \
        --data-dir <cache dir> --out <run dir>/provenance.json [--label X] [--hash-corpus]

Written before a run (the cold-cache proof: the cache's entry counts are 0)
and again after it (into the run directory). Every field is measured on this
host at the time of the call; nothing is quoted from a record. The tree is
introspected in a SUBPROCESS with cwd=<checkout> so that a batch-7 worktree
(302f8f2) and the train are read by their own code, never by the caller's.

Secrets are never written: API-key environment variables are recorded as
set/unset only. The JSON is the record; a Markdown twin is written beside it.
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


def collect(checkout: Path, root: Path, data_dir: Path, *, label: str, hash_corpus: bool) -> dict:
    python = sys.executable
    tesseract = shutil.which("tesseract")
    pdftoppm = shutil.which("pdftoppm")
    tree_probe = _run([python, "-c", _TREE_PROBE, str(root)], cwd=checkout, timeout=900)
    try:
        tree = json.loads(tree_probe["stdout"]) if tree_probe.get("exit") == 0 else {"error": tree_probe}
    except json.JSONDecodeError:
        tree = {"error": tree_probe}
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
    args = parser.parse_args(argv)
    try:  # the Windows console is cp1252; the files are UTF-8 regardless
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    record = collect(args.checkout.resolve(), args.root.resolve(), args.data_dir.resolve(),
                     label=args.label, hash_corpus=args.hash_corpus)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2, sort_keys=True, default=str), encoding="utf-8")
    args.out.with_suffix(".md").write_text(render(record), encoding="utf-8")
    print(render(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
