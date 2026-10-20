"""What does `lili` claim outside its named population? — W3 §LILI.

The wave asks a new registration for a stratified non-target probe of at least
400 documents, all scanned and all Canadian included. This tool does not
sample: it runs the registration's `detect` over the WHOLE archive the run of
record enumerates, which is a superset of any stratified sample and therefore
contains every scanned and every Canadian document by construction.

    python -m tools.lili_nontarget_probe \
        --rows discovery_reports/<run-id>/rows.csv \
        --data-dir <checkout>/webapp_data

READ-ONLY, $0.00, and index-free in the same way as
`tools/regfp_zero_movement_sweep.py`: OCR payloads are reached by DIRECT file
path over every capability partition, the `webapp_data` sqlite index is never
opened, nothing is written, and no model is called. Only `detect` runs — the
question is what the registry now CLAIMS, which is the property a new
registration can break for every other parser.

THE GENRE SIBLINGS ARE REPLAYED IN THE SAME PASS. This card's reader sits
beside four fintech readers that must stay byte-identical, and the way a new
registration breaks a neighbour is not by editing it: it is by CLAIMING one of
its documents, or by making a dispatch ambiguous. So for every document the
run of record dispatched to one of `--siblings`, this tool re-runs that
sibling's own detection and this card's, and reports any document the sibling
stopped claiming or that both now claim.

It prints counts, the strata those counts cover, and `content_sha256` values
only where a claim lands outside the census family or where a sibling moved.
No document text, amount, name, account number or date is read out of this
tool.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from pathlib import Path

from analysis import parser_registry_entries  # noqa: F401  — populates the registry
from analysis import lili
from analysis.parser_registry import admissible_text, registrations
from ocr.document import StatementMarkdown
from tools.lili_family_replay import DEFAULT_CENSUS, DEFAULT_FAMILY, family_shas
from webapp.artifact_cache import STAGE_OCR, cache_key, ocr_settings_key

_OCR_KEYS = [
    ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
    for force, local, visual in itertools.product((False, True), repeat=3)
]

#: Folder labels and published bank names of the archive's Canadian issuers.
#: Used ONLY to report which strata the probe covered — the probe itself is
#: the whole archive, so nothing depends on this list being complete.
_CANADIAN = (
    "rbc", "royal bank of canada", "banque royale du canada", "bmo",
    "bank of montreal", "cibc", "scotiabank", "scotia", "td canada",
    "desjardins", "atb", "eq bank", "equitable", "tangerine", "wealthsimple",
    "meridian", "vancity", "coast capital", "simplii", "national bank",
    "banque nationale", "laurentian", "manulife",
)


def cached_text(artifacts: Path, sha: str) -> str | None:
    best = None
    for key in _OCR_KEYS:
        composed = cache_key(STAGE_OCR, sha.upper(), key)
        path = artifacts / STAGE_OCR / composed[:2] / f"{composed}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        document = (payload.get("artifact") or {}).get("document")
        if not isinstance(document, dict):
            continue
        rendered = StatementMarkdown(
            source_file="", model=str(document.get("model") or ""),
            pages=[str(page) for page in (document.get("pages") or [])],
        ).to_markdown()
        if best is None or len(rendered) > len(best):
            best = rendered
    return best


def is_canadian(row: dict) -> bool:
    haystack = f"{row.get('folder_label') or ''} {row.get('statement_bank') or ''}".lower()
    return any(token in haystack for token in _CANADIAN)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--census", default=DEFAULT_CENSUS, type=Path)
    parser.add_argument("--family", default=DEFAULT_FAMILY)
    parser.add_argument(
        "--siblings", default="bluevine,mercury,relay,square_checking",
        help="registration ids whose populations must be unmoved by this card",
    )
    args = parser.parse_args()

    artifacts = args.data_dir / "artifacts"
    family = {sha.upper() for sha in family_shas(args.census, args.family)}
    others = [r for r in registrations() if r.id != "lili"]

    seen: dict[str, dict] = {}
    with args.rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").upper()
            if sha and sha not in seen:
                seen[sha] = row

    strata = {"scanned": 0, "canadian": 0, "labels": set(), "with_text": 0}
    claims_inside: list[str] = []
    claims_outside: list[str] = []
    also_claimed: list[str] = []
    for sha, row in seen.items():
        strata["labels"].add(row.get("folder_label") or "")
        if (row.get("classification") or "") == "scanned":
            strata["scanned"] += 1
        if is_canadian(row):
            strata["canadian"] += 1
        markdown = cached_text(artifacts, sha)
        if markdown is None:
            continue
        strata["with_text"] += 1
        text = admissible_text(markdown)
        if not lili.detect(text).claims:
            continue
        (claims_inside if sha in family else claims_outside).append(sha)
        if any(other.detect(text).claims for other in others):
            also_claimed.append(sha)

    print(f"archive rows                     : {len(seen)} distinct content_sha256")
    print(f"  with a cached OCR artifact     : {strata['with_text']}")
    print(f"  scanned (all included)         : {strata['scanned']}")
    print(f"  Canadian by label/bank         : {strata['canadian']}")
    print(f"  distinct folder labels covered : {len(strata['labels'])}")
    print(f"census family                    : {len(family)}")
    print(f"lili claims INSIDE the family    : {len(claims_inside)}")
    print(f"lili claims OUTSIDE the family   : {len(claims_outside)}")
    for sha in sorted(claims_outside):
        print(f"    OUTSIDE {sha}")
    print(f"claimed by lili AND another      : {len(also_claimed)}")
    for sha in sorted(also_claimed):
        print(f"    AMBIGUOUS {sha}")

    # --- the genre siblings, over the populations the run dispatched to them
    by_id = {registration.id: registration for registration in registrations()}
    lost: list[str] = []
    shared: list[str] = []
    print("\ngenre siblings, over the population the run of record gave each:")
    for sibling in [s.strip() for s in args.siblings.split(",") if s.strip()]:
        registration = by_id.get(sibling)
        if registration is None:
            raise SystemExit(f"no registration `{sibling}`")
        population = [sha for sha, row in seen.items()
                      if (row.get("parser_id") or "") == sibling]
        still = 0
        for sha in population:
            markdown = cached_text(artifacts, sha)
            if markdown is None:
                continue
            text = admissible_text(markdown)
            if registration.detect(text).claims:
                still += 1
            else:
                lost.append(f"{sibling} {sha}")
            if lili.detect(text).claims:
                shared.append(f"{sibling} {sha}")
        print(f"  {sibling:18} {len(population):4} documents, still claimed {still:4}")
    for entry in lost:
        print(f"    SIBLING LOST A DOCUMENT {entry}")
    for entry in shared:
        print(f"    SIBLING DOCUMENT ALSO CLAIMED BY lili {entry}")

    return 0 if not (claims_outside or also_claimed or lost or shared) else 1


if __name__ == "__main__":
    sys.exit(main())
