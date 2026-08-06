"""Record which parser claims each corpus document, from the CURRENT dispatch.

R-3 stage 3.0 (R3_RFC §6.1). This produces `tests/data/parser_expectations.json`,
the baseline the parser-parity test judges the registry against. It must be run
against the **unmodified** or-chain in `analysis/pipeline.py`, before any
dispatch code changes, or the baseline is contaminated by what it is meant to
check.

How it records
--------------
The or-chain calls the 43 `parse_*_statement` functions through the names bound
in `analysis.pipeline`'s namespace, so wrapping those attributes intercepts
every call without touching production code. Each wrapper notes that the parser
was called and whether it returned a `Statement`; the first non-`None` is the
claimant, and everything the chain ran before it is recorded as
`chain_declined_ids`.

Read that field for what it is: the chain's *prefix*, not a set of parsers that
recognised the document. The or-chain cannot tell "this parser's guard failed"
apart from "its guard passed and it then gave up", because both return `None`.
Separating them needs `detect` to exist, which is stage R-3.2; the test added
there asserts that exactly one registration claims each corpus document, which
is the sharp form of the fallthrough question R3_RFC §4.3 raises.

Three parsers contain a nested sub-dispatch that the chain cannot see
(`chase_export`, `rbc_french`, `td_canada_native`). Their private entry points
are wrapped too, so each row records the *variant* that actually fired. R-3.3
promotes those three to registrations of their own; without the variant
recorded here, that stage could not be proved parity-preserving.

Offline and reproducible: source text comes from native PDF text or the
committed OCR artifacts, exactly as `corpus_gate.py` resolves it, and the
document set is the pinned manifest (the audit CSVs' 109 paths) — never an
`rglob` of the corpus root, which also holds the discovery archive.

    python tools/record_parser_expectations.py            # write the baseline
    python tools/record_parser_expectations.py --check    # verify, write nothing

Regenerating this file is a deliberate, reviewed act, like regenerating the
audit CSVs (Ocean ruling, 2026-08-06).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import pipeline  # noqa: E402
from balance_forensic_audit import source_markdown  # noqa: E402
from corpus_artifacts import DEFAULT_CACHE, sha256_hex  # noqa: E402

CORPUS = ROOT / "Bank Statements"
BALANCE_CSV = ROOT / "docs" / "balance-metrics-audit-results.csv"
OUTPUT = ROOT / "tests" / "data" / "parser_expectations.json"
EXPECTED_ROWS = 109

#: Parser id -> the attribute in `analysis.pipeline` that the or-chain calls.
#: Ids follow the naming baseline of the reviewed prototype registry
#: (`git show 54a9e8d:analysis/parser_registry.py`, catalogued in
#: PROTOTYPE_REVIEW.md); its dispatch semantics are deliberately NOT reused.
PIPELINE_ENTRY_POINTS: dict[str, str] = {
    "columbia_bank": "parse_columbia_bank_statement",
    "first_farmers": "parse_first_farmers_statement",
    "navigant": "parse_navigant_statement",
    "relay": "parse_relay_statement",
    "td_canada": "parse_td_canada_statement",
    "td_us": "parse_td_us_statement",
    "altana": "parse_altana_statement",
    "american_express": "parse_amex_statement",
    "atb": "parse_atb_statement",
    "b1": "parse_b1_statement",
    "banco_popular": "parse_banco_popular_statement",
    "bluevine": "parse_bluevine_statement",
    "cibc_french": "parse_cibc_french_statement",
    "consumers": "parse_consumers_statement",
    "demo_national": "parse_demo_national_statement",
    "desjardins": "parse_desjardins_statement",
    "ibc": "parse_ibc_statement",
    "mission_valley": "parse_mission_valley_statement",
    "dakota_west": "parse_dakota_west_statement",
    "linkbank": "parse_linkbank_statement",
    "midflorida": "parse_midflorida_statement",
    "navy_federal": "parse_navy_federal_statement",
    "santander": "parse_santander_statement",
    "southside_scanned": "parse_southside_scanned_statement",
    "apex_scanned": "parse_apex_scanned_statement",
    "texas_bank": "parse_texas_bank_statement",
    "truist": "parse_truist_statement",
    "us_bank": "parse_us_bank_statement",
    "rbc": "parse_rbc_statement",
    "scotiabank": "parse_scotiabank_statement",
    "secu": "parse_secu_statement",
    "wells_fargo": "parse_wells_statement",
    "wilson_muir": "parse_wilson_muir_statement",
    "bank_of_america": "parse_bofa_statement",
    "regions": "parse_regions_statement",
    "pnc": "parse_pnc_statement",
    "farmers_merchants": "parse_farmers_merchants_statement",
    "first_community": "parse_first_community_statement",
    "first_citizens": "parse_first_citizens_statement",
    "bmo": "parse_bmo_statement",
    "capital_one": "parse_capital_one_statement",
    "chase": "parse_chase_statement",
    "citizens": "parse_citizens_statement",
}

#: Nested sub-dispatches: variant id -> (module, private function, outer id).
SUB_DISPATCHES: dict[str, tuple[str, str, str]] = {
    "chase_export": ("analysis.chase", "_parse_chase_business_export", "chase"),
    "rbc_french": ("analysis.rbc", "_parse_rbc_french_statement", "rbc"),
    "td_canada_native": ("analysis.td_can", "_parse_native_td_canada", "td_canada"),
}


class Recorder:
    """Wraps the dispatch entry points and remembers what each document did."""

    def __init__(self) -> None:
        self.attempted: list[str] = []
        self.declined: list[str] = []
        self.claimed: str | None = None
        self.variant: str | None = None

    def reset(self) -> None:
        self.attempted.clear()
        self.declined.clear()
        self.claimed = None
        self.variant = None

    def wrap(self, parser_id: str, original, *, is_variant: bool = False):
        def recorded(*args, **kwargs):
            if not is_variant:
                self.attempted.append(parser_id)
            statement = original(*args, **kwargs)
            if statement is None:
                if not is_variant:
                    self.declined.append(parser_id)
                return None
            if is_variant:
                self.variant = parser_id
            elif self.claimed is None:
                self.claimed = parser_id
            return statement

        return recorded


def install(recorder: Recorder) -> list[tuple[object, str, object]]:
    """Patch the entry points; return what is needed to restore them."""
    import importlib

    saved: list[tuple[object, str, object]] = []
    for parser_id, attribute in PIPELINE_ENTRY_POINTS.items():
        original = getattr(pipeline, attribute)
        saved.append((pipeline, attribute, original))
        setattr(pipeline, attribute, recorder.wrap(parser_id, original))
    for variant_id, (module_name, attribute, _outer) in SUB_DISPATCHES.items():
        module = importlib.import_module(module_name)
        original = getattr(module, attribute)
        saved.append((module, attribute, original))
        setattr(module, attribute, recorder.wrap(variant_id, original, is_variant=True))
    return saved


def restore(saved: list[tuple[object, str, object]]) -> None:
    for target, attribute, original in saved:
        setattr(target, attribute, original)


def audit_parser_labels() -> dict[str, str]:
    """The committed audit CSV's `parser` column, keyed by corpus path.

    Used as an independent cross-check. That column stores
    `f"{bank_label}-deterministic"` derived from `Statement.bank`
    (analysis/pipeline.py), so it is a bank label rather than a parser
    identity — but a recorded row whose bank disagrees with it means the
    recording ran against a tree that already differs from the audited truth.
    """
    with BALANCE_CSV.open(encoding="utf-8", newline="") as handle:
        return {row["path"]: row["parser"] for row in csv.DictReader(handle)}


def manifest_paths() -> list[str]:
    with BALANCE_CSV.open(encoding="utf-8", newline="") as handle:
        return sorted({row["path"] for row in csv.DictReader(handle)})


def record() -> dict:
    manifest = manifest_paths()
    if len(manifest) != EXPECTED_ROWS:
        raise SystemExit(
            f"pinned manifest holds {len(manifest)} paths, expected {EXPECTED_ROWS}"
        )

    recorder = Recorder()
    saved = install(recorder)
    rows = []
    try:
        for relative in manifest:
            path = CORPUS / Path(relative)
            markdown, source_type, pdf_bytes = source_markdown(path, ocr_cache=DEFAULT_CACHE)
            recorder.reset()
            statement = pipeline._deterministic_statement(markdown)
            if statement is None:
                raise SystemExit(
                    f"{relative}: no deterministic parser claimed a pinned corpus "
                    "document; the baseline cannot be recorded from a tree whose "
                    "dispatch is already broken"
                )
            rows.append(
                {
                    "path": relative,
                    "sha256": sha256_hex(pdf_bytes),
                    "source_type": source_type,
                    "parser_id": recorder.claimed,
                    "variant_id": recorder.variant,
                    "chain_declined_ids": list(recorder.declined),
                    "bank": statement.bank,
                }
            )
    finally:
        restore(saved)

    cross_check(rows)

    return {
        "note": (
            "Recorded from the pre-R-3 or-chain in analysis/pipeline.py. "
            "Regenerating this file is a deliberate, reviewed act - see "
            "tools/record_parser_expectations.py."
        ),
        "expected_rows": EXPECTED_ROWS,
        "documents": rows,
    }


def cross_check(rows: list[dict]) -> None:
    """Every recorded bank must agree with the committed audit CSV's label."""
    labels = audit_parser_labels()
    mismatches = []
    for row in rows:
        expected = labels[row["path"]]
        actual = f"{(row['bank'] or 'bank').lower().replace(' ', '-')}-deterministic"
        if actual != expected:
            mismatches.append(f"{row['path']}: audit says {expected}, recorded {actual}")
    if mismatches:
        joined = "\n  ".join(mismatches)
        raise SystemExit(f"recorded banks disagree with the committed audit CSV:\n  {joined}")


def render(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="recompute and compare against the committed file; write nothing",
    )
    args = parser.parse_args()

    payload = record()
    text = render(payload)

    # Reproducibility is part of the contract: a baseline that differs between
    # two runs of the same tree is not a baseline.
    if render(record()) != text:
        raise SystemExit("recording is not reproducible: two runs disagreed")

    if args.check:
        if not OUTPUT.is_file():
            print(f"missing {OUTPUT}", file=sys.stderr)
            return 1
        if OUTPUT.read_text(encoding="utf-8") != text:
            print(f"{OUTPUT} is out of date", file=sys.stderr)
            return 1
        print(f"{OUTPUT} matches the current dispatch ({len(payload['documents'])} documents)")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    claimants = {row["parser_id"] for row in payload["documents"]}
    variants = {row["variant_id"] for row in payload["documents"] if row["variant_id"]}
    print(f"wrote {OUTPUT}")
    print(f"  documents: {len(payload['documents'])}")
    print(f"  distinct claiming parsers: {len(claimants)}")
    print(f"  documents resolved by a nested sub-dispatch: "
          f"{sum(1 for r in payload['documents'] if r['variant_id'])} ({sorted(variants)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
