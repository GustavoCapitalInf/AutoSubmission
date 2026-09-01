"""P20-ROUTER's measurement instrument — STRICTLY READ-ONLY, no analysis.

Re-derives R / U / U-extract / U-structure against the frozen batch-9 run of
record (`docs/agent-handoffs/PHASE2-RULES.md`'s baseline) and prints the
headline numbers the card's report requires. It does not call
`analysis.pipeline` or any parser — it reads `rows.csv` (the run of record)
and the read-only cold cache's own committed OCR artifacts, and classifies
each Tesseract read with `ocr.escalation.ExtractionQualityGate`, which is
itself a pure function of the produced text. It is therefore NOT registered
in `corpus_gate.EXCLUDED_ANALYSIS_CALLERS` (that register answers a question
about analysis callers; this tool never calls the analysis stage at all).

    python -m tools.phase2_trigger_split
    python -m tools.phase2_trigger_split --run <run dir> --data-dir <cold cache> --out <private>.md

Reports counts, sha16 lists (to a PRIVATE `--out` file only — never printed),
and folder labels; never a statement value, a date, an amount or a name.

Numbers this instrument is EXPECTED to reproduce (`docs/agent-handoffs/PHASE2-RULES.md`,
re-derived 2026-09-01 on `discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a`):
R = 13, U = 123 (89 `no_parser_matched` + 34 `parser_declined`), R union U = 136,
overlap = 0, validated intersect (R union U) = 0, Tesseract split 36 validated /
15 withheld / 5 review / 123 failed, T surface (truncated_pages > 0) = 3 (1 inside U).
The U-extract / U-structure split and the alphanumeric-density floor's
provenance are THIS tool's own measurement — the card says explicitly not to
assume it, and this file is where it is produced and can be reproduced.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

from ocr.escalation import ALNUM_DENSITY_FLOOR, CHAR_FLOOR, ExtractionQualityGate

DEFAULT_RUN_POINTER_RELATIVE = ("discovery_reports", "train9-logs", "train9_run_dir.txt")
DEFAULT_DATA_DIR_RELATIVE = (".claude", "recovery", "webapp_data_train9_cold")


def _checkout_ancestor(*relative: str) -> Path | None:
    """The nearest enclosing directory that holds `relative`, or None.

    A git worktree does not carry the gitignored recovery cache or the
    discovery reports; the checkout it was created from does (BATCH9-RULES'
    host note). Searching upwards is what lets this tool run from either —
    the same pattern `tests/test_l1s2_protected_carriers.py` uses.
    """
    root = Path(__file__).resolve().parents[1]
    for base in (root, *root.parents):
        candidate = base.joinpath(*relative)
        if candidate.exists():
            return candidate
    return None


def _default_run() -> Path | None:
    pointer = _checkout_ancestor(*DEFAULT_RUN_POINTER_RELATIVE)
    if pointer is None:
        return None
    # pointer = <root>/discovery_reports/train9-logs/train9_run_dir.txt ; its
    # own text is a root-RELATIVE path, so climb back to <root> to resolve it.
    root = pointer.parent.parent.parent
    run = root / pointer.read_text(encoding="utf-8").strip()
    return run if run.exists() else None


def _default_data_dir() -> Path | None:
    return _checkout_ancestor(*DEFAULT_DATA_DIR_RELATIVE)


# ---------------------------------------------------------------------------
# rows.csv
# ---------------------------------------------------------------------------

def load_rows(run: Path) -> dict[str, dict]:
    """content_sha256 -> first-seen row, from the run of record's `rows.csv`."""
    rows: dict[str, dict] = {}
    with (run / "rows.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip().upper()
            if sha and sha not in rows:
                rows[sha] = row
    return rows


# ---------------------------------------------------------------------------
# cold cache — read-only, index + committed OCR artifact only
# ---------------------------------------------------------------------------

class ColdOcrReader:
    """Reads ONLY the `ocr` stage's committed artifact pages, `mode=ro`.

    Never opens the `analysis` stage, never calls a parser, never writes.
    """

    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir / "artifacts"
        self.conn = sqlite3.connect(f"file:{(data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)

    def pages(self, sha: str) -> list[str] | None:
        rows = self.conn.execute(
            "SELECT artifact_path FROM artifact_cache WHERE stage = ? AND input_sha256 = ?",
            ("ocr", sha),
        ).fetchall()
        if not rows:
            return None
        try:
            payload = json.loads((self.root / rows[0][0]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        document = (payload.get("artifact") or {}).get("document")
        if not isinstance(document, dict):
            return None
        return [str(p) for p in (document.get("pages") or [])]


class _Document:
    """The minimal shape `ExtractionQualityGate.assess` reads: `.pages`."""

    __slots__ = ("pages",)

    def __init__(self, pages: list[str]) -> None:
        self.pages = pages


# ---------------------------------------------------------------------------
# the measurement
# ---------------------------------------------------------------------------

def measure(rows: dict[str, dict], reader: ColdOcrReader) -> dict:
    r_shas = {sha for sha, row in rows.items() if row.get("outcome_reason") == "deferred_visual_ocr"}
    u_shas = {
        sha for sha, row in rows.items()
        if row.get("source_path") == "local_tesseract" and row.get("dispatch_outcome") != "claimed"
    }
    tesseract_shas = {sha for sha, row in rows.items() if row.get("source_path") == "local_tesseract"}
    validated_shas = {sha for sha, row in rows.items() if row.get("outcome_class") == "validated"}
    claimed_tesseract_shas = {
        sha for sha in tesseract_shas if rows[sha].get("outcome_class") in ("validated", "withheld", "review")
    }
    truncated_tesseract_shas = {
        sha for sha in tesseract_shas if int(rows[sha].get("truncated_pages") or 0) > 0
    }

    u_extract: set[str] = set()
    u_structure: set[str] = set()
    missing_artifact: set[str] = set()
    validated_unusable: set[str] = set()
    for sha in u_shas:
        pages = reader.pages(sha)
        if pages is None:
            missing_artifact.add(sha)
            continue
        evidence = ExtractionQualityGate.assess(_Document(pages), None)
        (u_extract if not evidence.usable else u_structure).add(sha)
    for sha in validated_shas & tesseract_shas:
        pages = reader.pages(sha)
        if pages is None:
            continue
        evidence = ExtractionQualityGate.assess(_Document(pages), None)
        if not evidence.usable:
            validated_unusable.add(sha)

    reasons = {
        "no_parser_matched": sum(1 for sha in u_shas if rows[sha].get("outcome_reason") == "no_parser_matched"),
        "parser_declined": sum(1 for sha in u_shas if rows[sha].get("outcome_reason") == "parser_declined"),
    }
    by_profile = {
        "scanned": sum(1 for sha in u_shas if rows[sha].get("classification") == "scanned"),
        "mixed": sum(1 for sha in u_shas if rows[sha].get("classification") == "mixed"),
    }

    return {
        "R": r_shas, "U": u_shas, "R_or_U": r_shas | u_shas, "overlap": r_shas & u_shas,
        "validated_intersect_R_or_U": validated_shas & (r_shas | u_shas),
        "tesseract_total": tesseract_shas,
        "tesseract_by_outcome": {
            klass: {sha for sha in tesseract_shas if rows[sha].get("outcome_class") == klass}
            for klass in ("validated", "withheld", "review", "failed")
        },
        "u_by_reason": reasons,
        "u_by_profile": by_profile,
        "u_extract": u_extract,
        "u_structure": u_structure,
        "u_missing_artifact": missing_artifact,
        "validated_unusable": validated_unusable,
        "claimed_tesseract_shas": claimed_tesseract_shas,
        "truncated_tesseract": truncated_tesseract_shas,
        "truncated_in_u": truncated_tesseract_shas & u_shas,
        "legal_escalation_population": r_shas | u_extract,
    }


def _fmt(label: str, population: set[str]) -> str:
    return f"{label:44} {len(population):>5}"


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="PRIVATE sha16 lists; never printed")
    args = parser.parse_args(argv)

    run = args.run or _default_run()
    data_dir = args.data_dir or _default_data_dir()
    if run is None or not run.exists():
        print("phase2_trigger_split: the batch-9 run of record was not found "
              "in this checkout or any ancestor; pass --run explicitly.", file=sys.stderr)
        return 2
    if data_dir is None or not data_dir.exists():
        print("phase2_trigger_split: the train9 cold cache was not found in "
              "this checkout or any ancestor; pass --data-dir explicitly.", file=sys.stderr)
        return 2

    rows = load_rows(run)
    reader = ColdOcrReader(data_dir)
    result = measure(rows, reader)

    print(f"phase2_trigger_split — {run}")
    print(f"  CHAR_FLOOR={CHAR_FLOOR}  ALNUM_DENSITY_FLOOR={ALNUM_DENSITY_FLOOR}")
    print(_fmt("R (deferred_visual_ocr)", result["R"]))
    print(_fmt("U (local_tesseract, not claimed)", result["U"]))
    print(_fmt("R union U", result["R_or_U"]))
    print(_fmt("overlap (R intersect U)", result["overlap"]))
    print(_fmt("validated intersect (R union U)", result["validated_intersect_R_or_U"]))
    print(f"  U by reason: {sorted(result['u_by_reason'].items())}")
    print(f"  U by profile: {sorted(result['u_by_profile'].items())}")
    for klass, shas in sorted(result["tesseract_by_outcome"].items()):
        print(_fmt(f"tesseract, outcome={klass}", shas))
    print(_fmt("U-extract (Class A: evidence unusable)", result["u_extract"]))
    print(_fmt("U-structure (Class B: evidence usable)", result["u_structure"]))
    if result["u_missing_artifact"]:
        print(_fmt("U with no cached OCR artifact (excluded above)", result["u_missing_artifact"]))
    print(_fmt("validated Tesseract reads the gate calls unusable (must be 0)",
                result["validated_unusable"]))
    print(_fmt("T surface (tesseract, truncated_pages>0)", result["truncated_tesseract"]))
    print(_fmt("  ...of those, inside U", result["truncated_in_u"]))
    print(_fmt("legal escalation population (R + U-extract)",
                result["legal_escalation_population"]))

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as handle:
            handle.write(f"# phase2_trigger_split — {run}\n\n")
            for key in (
                "R", "U", "R_or_U", "overlap", "validated_intersect_R_or_U",
                "u_extract", "u_structure", "u_missing_artifact", "validated_unusable",
                "truncated_tesseract", "truncated_in_u", "legal_escalation_population",
            ):
                handle.write(f"## {key} ({len(result[key])})\n")
                for sha in sorted(result[key]):
                    handle.write(f"{sha[:16]}\n")
                handle.write("\n")
        print(f"\nsha16 lists written to {args.out} (private)")

    return 0 if result["validated_unusable"] == set() and result["overlap"] == set() else 1


if __name__ == "__main__":
    raise SystemExit(main())
