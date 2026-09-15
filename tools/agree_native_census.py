"""tools/agree_native_census.py — the read-only corpus census for the two
latent native-reader defects Phase 2.3 cell X closes (P23-AGREE item 4; the
P22-IDENTITY re-review's N-1 and N-2).

    python -m tools.agree_native_census --run <run dir> [--archive-root "Bank Statements"]
        [--limit N] [--verify-every K | --verify-all] [--baseline-ref phase2.2-final]

The question this answers, and nothing else: **does any real page of the
3,380 move?** `EXTRACTION_SCHEMA_VERSION` is cache-key material, so it must
be bumped if and only if the evidence bytes of an existing corpus page
change, and that is a MEASUREMENT, not a judgement.

How it measures
---------------
Two passes, the second only where the first says it can matter.

1. **Structural pass, every document.** For every page: does PyMuPDF's
   `rotation_matrix` disagree with the matrix derived from `page.rect`
   (`evidence.native._display_matrix` — the N-1 predicate, reachable when a
   CropBox OVERHANGS its MediaBox on a rotated page)? Is the page's `/Rotate`
   an INDIRECT reference, and what integer does it resolve to (the N-2
   predicate: a resolved value that is not a multiple of 90 is refused by
   the fixed reader and was silently mis-framed by the old one)? Those two
   predicates are EXACTLY the conditions under which the fix changes what
   the reader emits; everything else this pass prints — rotated pages,
   overhanging CropBoxes, `/Rotate` kinds — is context, so the numbers can be
   compared with the re-reviewer's own census.

2. **Byte pass, on the documents the first flags plus a deterministic
   control sample** (`--verify-every K`, default 50; `--verify-all` for the
   whole archive). The document's `ExtractionEvidence` sha is computed twice
   from the SAME PDF bytes: with the current reader and the actual baseline
   module loaded from the named Git ref. No current helper is monkeypatched
   to emulate old behaviour. A helper rename therefore cannot silently
   invalidate the baseline comparison. Both modules use the same canonical
   evidence contract and runtime; the baseline source never writes a file.

Output is COUNTS ONLY, plus the sha16 of any document that moved (a named
finding, never beside a verdict, never beside a value). Nothing is written
anywhere; the archive and the run directory are opened read-only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
import sys
import time
import types
from pathlib import Path

import evidence.native as native_module
from evidence.native import _display_matrix, _matrices_agree, native_evidence_from_pdf

DEFAULT_ARCHIVE_ROOT = Path("Bank Statements")
DEFAULT_VERIFY_EVERY = 50
ROOT = Path(__file__).resolve().parents[1]


def _rows(run: Path) -> list[tuple[str, str]]:
    """`(content sha, relative path)` for each distinct sha, in run order."""
    seen: set[str] = set()
    ordered: list[tuple[str, str]] = []
    with (run / "rows.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip().upper()
            path = (row.get("relative_path") or "").strip()
            if not sha or sha in seen or not path:
                continue
            seen.add(sha)
            ordered.append((sha, path))
    return ordered


class _Counts:
    def __init__(self) -> None:
        self.documents = 0
        self.unreadable_documents = 0
        self.pages = 0
        self.unreadable_pages = 0
        self.rotated_pages = 0
        self.cropbox_differs = 0
        self.cropbox_overhangs = 0
        self.matrix_disagrees = 0          # the N-1 population
        self.rotate_direct = 0
        self.rotate_indirect = 0           # the N-2 population (shape)
        self.rotate_indirect_unresolved = 0
        self.rotate_indirect_invalid = 0   # the N-2 population (behaviour change)
        self.rotate_other_kind = 0

    def line(self, name: str, value: int) -> str:
        return f"  {name:<44}{value:>9}"


def _rotate_entry(document, page) -> tuple[str, str]:
    """The nearest effective Rotate entry, including an inherited key."""
    xref = page.xref
    seen: set[int] = set()
    for _ in range(64):
        if xref in seen:
            break
        seen.add(xref)
        kind, value = document.xref_get_key(xref, "Rotate")
        if kind not in ("null", ""):
            return kind, value
        kind, value = document.xref_get_key(xref, "Parent")
        head = str(value).strip().split(" ", 1)[0]
        if kind != "xref" or not head.isdigit():
            break
        xref = int(head)
    return "null", ""


def _page_facts(document, page, counts: _Counts) -> bool:
    """Measure one page; return True when this document can move."""
    moved = False
    try:
        rect = page.rect
        rotation = int(page.rotation) % 360
        matrix = native_module._matrix_tuple(page.rotation_matrix)
        cropbox = page.cropbox
        mediabox = page.mediabox
    except Exception:
        counts.unreadable_pages += 1
        return False
    counts.pages += 1
    if rotation:
        counts.rotated_pages += 1
    if tuple(cropbox) != tuple(mediabox):
        counts.cropbox_differs += 1
        if (cropbox.x0 < mediabox.x0 - 1e-6 or cropbox.y0 < mediabox.y0 - 1e-6
                or cropbox.x1 > mediabox.x1 + 1e-6 or cropbox.y1 > mediabox.y1 + 1e-6):
            counts.cropbox_overhangs += 1
    derived = _display_matrix(rotation if rotation in (0, 90, 180, 270) else 0,
                              float(rect.width), float(rect.height))
    if not _matrices_agree(matrix, derived):
        counts.matrix_disagrees += 1
        moved = True
    try:
        kind, value = _rotate_entry(document, page)
    except Exception:
        kind, value = "", ""
    if kind == "int":
        counts.rotate_direct += 1
    elif kind == "xref":
        counts.rotate_indirect += 1
        resolved = native_module._indirect_rotate(document, page, value)
        if resolved is None:
            counts.rotate_indirect_unresolved += 1
        elif resolved % 90 != 0:
            counts.rotate_indirect_invalid += 1
            moved = True
    elif kind not in ("null", ""):
        counts.rotate_other_kind += 1
    return moved


def _structural(pdf_bytes: bytes, counts: _Counts) -> bool:
    import fitz

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        counts.unreadable_documents += 1
        return False
    moved = False
    try:
        for page in document:
            moved = _page_facts(document, page, counts) or moved
    except Exception:
        counts.unreadable_documents += 1
    finally:
        try:
            document.close()
        except Exception:
            pass
    return moved


def _evidence_sha(pdf_bytes: bytes, reader=native_evidence_from_pdf) -> str | None:
    evidence = reader(pdf_bytes)
    return None if evidence is None else evidence.evidence_sha256


def _baseline_reader(ref: str):
    """Load the committed baseline reader in an isolated module namespace."""
    resolved = subprocess.run(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=ROOT,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    source = subprocess.run(
        ["git", "show", f"{resolved}:evidence/native.py"], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    module = types.ModuleType("evidence._agreement_census_baseline")
    module.__package__ = "evidence"
    exec(compile(source, f"{resolved}:evidence/native.py", "exec"), module.__dict__)
    return resolved, module.native_evidence_from_pdf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True, type=Path, help="the run of record's directory")
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--verify-every", type=int, default=DEFAULT_VERIFY_EVERY,
                        help="also compare evidence shas for every Kth document (0 = only the flagged)")
    parser.add_argument("--verify-all", action="store_true")
    parser.add_argument("--baseline-ref", default="phase2.2-final")
    args = parser.parse_args(argv)
    baseline_ref, baseline_reader = _baseline_reader(args.baseline_ref)

    documents = _rows(args.run)
    if args.limit:
        documents = documents[: args.limit]
    counts = _Counts()
    flagged: list[str] = []
    verified = 0
    moved_shas: list[str] = []
    missing = 0
    started = time.perf_counter()

    for index, (sha, relative) in enumerate(documents):
        path = args.archive_root / relative
        try:
            pdf_bytes = path.read_bytes()
        except OSError:
            missing += 1
            continue
        if hashlib.sha256(pdf_bytes).hexdigest().upper() != sha:
            # the row's sha is the archive's own content sha; a disagreement
            # means this is not the document the run read, and censusing it
            # would be censusing something else
            missing += 1
            continue
        counts.documents += 1
        can_move = _structural(pdf_bytes, counts)
        if can_move:
            flagged.append(sha)
        if can_move or args.verify_all or (args.verify_every and index % args.verify_every == 0):
            verified += 1
            if _evidence_sha(pdf_bytes) != _evidence_sha(pdf_bytes, baseline_reader):
                moved_shas.append(sha)
        if index and index % 250 == 0:
            print(f"  ... {index}/{len(documents)} ({time.perf_counter() - started:.0f} s)", flush=True)

    print("\n# N-1 / N-2 corpus census (read-only; counts only)")
    print(f"  run                                         {args.run}")
    print(f"  baseline reader commit                      {baseline_ref}")
    print(counts.line("documents censused", counts.documents))
    print(counts.line("documents not readable as PDF", counts.unreadable_documents))
    print(counts.line("documents absent or sha-mismatched", missing))
    print(counts.line("pages censused", counts.pages))
    print(counts.line("pages not readable", counts.unreadable_pages))
    print(counts.line("rotated pages", counts.rotated_pages))
    print(counts.line("pages whose CropBox differs from MediaBox", counts.cropbox_differs))
    print(counts.line("pages whose CropBox OVERHANGS it", counts.cropbox_overhangs))
    print(counts.line("N-1: matrix disagrees with page.rect", counts.matrix_disagrees))
    print(counts.line("pages with a direct /Rotate", counts.rotate_direct))
    print(counts.line("pages with an INDIRECT /Rotate", counts.rotate_indirect))
    print(counts.line("  of those, unresolvable to an integer", counts.rotate_indirect_unresolved))
    print(counts.line("N-2: resolved /Rotate not a multiple of 90", counts.rotate_indirect_invalid))
    print(counts.line("pages with another /Rotate kind", counts.rotate_other_kind))
    print(counts.line("documents flagged by the structural pass", len(flagged)))
    print(counts.line("documents byte-verified", verified))
    print(counts.line("documents whose evidence sha MOVED", len(moved_shas)))
    for sha in moved_shas:
        print(f"    moved: {sha[:16]}")
    print(f"  elapsed {time.perf_counter() - started:.0f} s")
    if missing or not counts.documents:
        print("\nVERDICT: INCOMPLETE population — no identity conclusion")
        return 3
    if moved_shas:
        print("\nVERDICT: AT LEAST ONE DOCUMENT MOVES — STOP before any schema bump")
        return 2
    print("\nVERDICT: no verified evidence sha moves — EXTRACTION_SCHEMA_VERSION stays")
    return 0


if __name__ == "__main__":
    sys.exit(main())
