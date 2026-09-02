"""Read-only census of the nine `ocr.ocr_client.postprocess` chain members
(Phase 2.0, cell B1, OQ1 = C).

Gustavo ruled OQ1 = C: quarantine the entire postprocess chain; re-admit a
member only after ITS OWN census + synthetic fixtures establish exactly what
it changes and independent review clears it. This module is that census,
made executable rather than prose (MINOR-6: the chain is nine functions, not
six — three metadata-only strippers were missed by the earlier count).

It imports the nine functions directly, runs the committed synthetic
fixtures under ``tests/fixtures/ocr_postprocess/<function>/<case>/`` through
each function, and prints a table. It makes no network call, writes nothing,
and is safe to run at any time:

    python -m tools.ocr_postprocess_census

The classification for each function and the human-authored narrative live in
``docs/moneythumb-replacement/OCR_POSTPROCESS_CENSUS.md``; this module is the
thing that proves the doc's per-fixture claims are the functions' REAL
measured behavior, not a transcription. ``tests/test_ocr_postprocess_census.py``
asserts the same facts as a pinned regression.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ocr.ocr_client import (
    strip_det_tags,
    strip_refusal_commentary,
    strip_placeholder_markers,
    strip_oversized_embedded_images,
    collapse_repeated_amounts,
    collapse_repeated_page_numbers,
    split_fused_header_row,
    repair_fused_amount_table,
    fix_amount_column_bleed,
    postprocess,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "ocr_postprocess"

#: The nine chain members, in the order `postprocess` calls them (MINOR-6: the
#: chain is nine functions deep, not six — three metadata-only strippers were
#: missed by the original count in OCR_LEGACY_AUDIT.md §5.7).
CHAIN_ORDER = (
    "strip_det_tags",
    "strip_refusal_commentary",
    "strip_placeholder_markers",
    "strip_oversized_embedded_images",
    "collapse_repeated_amounts",
    "collapse_repeated_page_numbers",
    "split_fused_header_row",
    "repair_fused_amount_table",
    "fix_amount_column_bleed",
)

FUNCTIONS = {
    "strip_det_tags": strip_det_tags,
    "strip_refusal_commentary": strip_refusal_commentary,
    "strip_placeholder_markers": strip_placeholder_markers,
    "strip_oversized_embedded_images": strip_oversized_embedded_images,
    "collapse_repeated_amounts": collapse_repeated_amounts,
    "collapse_repeated_page_numbers": collapse_repeated_page_numbers,
    "split_fused_header_row": split_fused_header_row,
    "repair_fused_amount_table": repair_fused_amount_table,
    "fix_amount_column_bleed": fix_amount_column_bleed,
}

#: The exact prefix a classification must start with for
#: `test_metadata_only_classification_never_deletes_a_financial_token` (the
#: MAJOR-1 enforceable invariant) to apply to it. A function may use this
#: label ONLY if every one of its committed fixtures shows
#: `numeric_tokens_delta.money.disappeared is False` and
#: `...date.disappeared is False` — the review's fix for MAJOR-1: the label
#: is enforced, not asserted in prose.
METADATA_ONLY_LABEL = "reads/removes metadata-only content"

#: The precise classification for each function (never forced into a coarser
#: label than the evidence supports). See OCR_POSTPROCESS_CENSUS.md for the
#: full narrative, worst-input and harmless-input for each.
#:
#: Adversarial review (docs/moneythumb-replacement/reviews/
#: PHASE2_P20POSTPROC_REVIEW.md), MAJOR-1: four rows carried an ABSOLUTE
#: "cannot touch a financial value" claim, falsified by construction on
#: `strip_det_tags` (an orphan bracket's content, and the span between an
#: orphan opening tag and the NEXT region's close, are both unconstrained),
#: `strip_oversized_embedded_images` (the `alt` attribute's tokens go with an
#: oversized image at the production threshold), `split_fused_header_row`
#: (text sitting in the rebuilt `<tr>` outside any `<td>` is discarded), and
#: `fix_amount_column_bleed` / `repair_fused_amount_table` (any content
#: outside `<tr>` rows, e.g. a `<caption>`, is discarded whenever either
#: function actually rewrites the table). The coarse label survives for the
#: two functions that restructure/rewrite ANYWAY; `strip_det_tags` and
#: `strip_oversized_embedded_images` no longer carry `METADATA_ONLY_LABEL`,
#: because they can no longer make that promise — reproduced by
#: `tests/fixtures/ocr_postprocess/strip_det_tags/orphan_bracket_contains_money/`,
#: `.../pair_spans_to_next_close/`,
#: `tests/fixtures/ocr_postprocess/strip_oversized_embedded_images/alt_attribute_money_dropped/`,
#: `tests/fixtures/ocr_postprocess/split_fused_header_row/stray_text_between_cells_deleted/`,
#: `tests/fixtures/ocr_postprocess/fix_amount_column_bleed/caption_dropped_when_fires/` and
#: `tests/fixtures/ocr_postprocess/repair_fused_amount_table/caption_dropped_when_fires/`.
CLASSIFICATION = {
    "strip_det_tags": (
        "removes a markup span whose content is UNCONSTRAINED by the "
        "pattern: the orphan form's bracket content is `[^\\]\\n]*` — "
        "anything at all — so a money-shaped token written INSIDE an orphan "
        "tag's brackets is deleted with it; and the well-formed-pair "
        "pattern's `.*?` can span from an orphan OPENING tag all the way to "
        "the NEXT region's closing tag, deleting everything printed between "
        "them, including a money token. A well-formed pair around a label "
        "with no money inside its own span, and a well-formed orphan whose "
        "bracket holds only geometry digits, are both untouched — but "
        "neither absolute claim this row previously made survives "
        "construction"
    ),
    "strip_refusal_commentary": (
        "reads/removes metadata-only content: removes a tightly anchored "
        "three-sentence refusal template; the pattern cannot consume "
        "adjacent financial text (proven: a money token with no separator "
        "immediately after the template survives)"
    ),
    "strip_placeholder_markers": (
        "reads/removes metadata-only content: drops '[Non-Text]'-shaped "
        "placeholder lines/spans; a line carrying any other content "
        "(a numeric token included) fails the drop guard's `fullmatch` and "
        "is left in place, with only the placeholder substring removed. "
        "Unconditional side effect, never financial (MINOR-3): every line is "
        "rejoined with a bare `\\n`, so CRLF line endings, a form-feed, and a "
        "trailing newline are all normalized away even on a placeholder-free "
        "page — a byte-level rewrite of every page this function ever sees, "
        "proven harmless to money/date tokens but not a no-op on bytes"
    ),
    "strip_oversized_embedded_images": (
        "removes a markup span whose content is UNCONSTRAINED by the "
        "pattern: `_DATA_IMG_RE`'s trailing `[^>]*` covers the `alt` "
        "attribute along with the `src`, so a money-shaped token written "
        "into an image's `alt` text (e.g. `alt=\"check total $5,000.00\"`) is "
        "deleted along with the image at the PRODUCTION default threshold "
        "(max_len=25,000) — not only in a lowered-threshold demonstration. A "
        "small (under-threshold) image and any money token outside an `alt` "
        "attribute survive"
    ),
    "collapse_repeated_amounts": (
        "writes/deletes financial-value meaning: deletes every amount in a "
        "bare, whitespace-separated run of 3+ money tokens where one value "
        "repeats 3+ times — including DISTINCT amounts that merely sit "
        "adjacent to the repeated run (F-1; proven: [a,a,a,b,c] -> [a], two "
        "distinct amounts destroyed, not deduplicated). The >=3 threshold is "
        "a real, pinned boundary: a value repeating only TWICE beside a "
        "distinct amount is untouched (a run where the dominant value's "
        "count is 2 leaves every token exactly as printed)"
    ),
    "collapse_repeated_page_numbers": (
        "restructures without inventing a FINANCIAL value (the pattern never "
        "matches a money- or date-shaped token — only 'Page N of M' page "
        "furniture); in the exact-repeat case, the digit-run tokens N and M "
        "that disappear are exact copies of a token that survives elsewhere "
        "in the same match, so no distinct information is lost. That is NOT "
        "a universal property, though (MINOR-2): the backreference `\\1` is "
        "not end-anchored, so when a shorter first footer is a textual "
        "PREFIX of a longer second footer sharing the same page number "
        "('Page 12 of 34 Page 12 of 345'), the match consumes only the "
        "prefix of the second occurrence and the substitution reassembles a "
        "different page number than either footer printed — a genuinely "
        "DISTINCT digit-run value ('34') is lost with no surviving copy. "
        "Page/count furniture only, never a financial value, but the "
        "'always an exact copy' claim does not hold universally"
    ),
    "split_fused_header_row": (
        "restructures without inventing/replacing financial values WITHIN "
        "`<td>` cells, but is NOT metadata-only at the row level: the "
        "rebuilt row is assembled from `_CELL_RE.findall` alone (`ocr/"
        "ocr_client.py:189-192`), so any text in the fused `<tr>` sitting "
        "OUTSIDE a `<td>` (stray text between cells) is discarded when the "
        "row is rebuilt — and that stray text can carry a money-shaped "
        "token away with it. Every value that DOES live inside a `<td>` is "
        "relocated to the data row at the SAME column index it already "
        "occupied — no digit inside a cell is invented, deleted, or moved "
        "to a different column"
    ),
    "repair_fused_amount_table": (
        "writes/reassigns financial-value meaning, CONDITIONALLY: when the "
        "table's fused header row's FIRST cell reads DATE and LAST cell "
        "reads AMOUNT (checked without regard to what any middle column is), "
        "every data row with >=3 cells and a bare-money last cell is folded "
        "to 3 columns by joining every cell BETWEEN the first and last into "
        "the description. On a genuine debit/credit/balance-shaped row this "
        "relocates one or more independent money columns into free text and "
        "mislabels the table's true final column (e.g. a running balance) as "
        "the transaction 'amount' — SETTLED BY CONSTRUCTION (this census; "
        "previously 'explicitly UNPROVEN' per OCR_LEGACY_AUDIT.md F-11 item "
        "3): no digit is deleted, but transaction semantics (which column is "
        "the amount) DO change. This is why OQ1's quarantine covers this "
        "function even though it 'restructures' rather than deleting. "
        "Additionally: whenever the gate passes and the table is rewritten, "
        "the whole table is re-emitted from its `<tr>` rows alone — any "
        "non-row content (a `<caption>`, for example) is discarded, and a "
        "money-shaped token printed there is discarded with it"
    ),
    "fix_amount_column_bleed": (
        "writes/reassigns financial-value meaning: in any table with an "
        "'Amount' header, a two-money Amount cell has its LEADING value "
        "moved into the description column and its TRAILING value promoted "
        "to the row's amount (F-11); if the page actually printed the "
        "larger/true amount first, the parser reads the smaller trailing "
        "figure instead — no digit is deleted, but which figure is 'the "
        "amount' changes. Additionally: whenever any row in the table "
        "actually bleeds and the table is rewritten, it too is re-emitted "
        "from its `<tr>` rows alone — a `<caption>` or other non-row content "
        "is discarded, taking any money-shaped token it holds with it"
    ),
}


_MONEY_RE = re.compile(r"-?\$?[\d,]+\.\d{2}\b")
_DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
_DIGIT_RUN_RE = re.compile(r"\d+")


def extract_tokens(text: str) -> dict:
    """The multiset of money-shaped, date-shaped and digit-run tokens in
    `text`, partitioned so nothing is double counted: money tokens are found
    first (highest-priority shape), then dates in what is left, then any
    remaining bare digit runs (bounding-box coordinates, page numbers, check
    numbers, reference numbers)."""
    money = _MONEY_RE.findall(text)
    masked = _MONEY_RE.sub(lambda m: "#" * len(m.group(0)), text)
    dates = _DATE_RE.findall(masked)
    masked = _DATE_RE.sub(lambda m: "#" * len(m.group(0)), masked)
    digit_runs = _DIGIT_RUN_RE.findall(masked)
    return {"money": money, "date": dates, "digit_run": digit_runs}


@dataclass
class FixtureCase:
    function: str
    case: str
    path: Path
    input_text: str
    expected_text: str
    meta: dict


def load_fixture_cases(function: str | None = None) -> list[FixtureCase]:
    """Every committed fixture case, optionally filtered to one function."""
    cases: list[FixtureCase] = []
    names = (function,) if function else CHAIN_ORDER
    for fn_name in names:
        fn_dir = FIXTURES_DIR / fn_name
        if not fn_dir.is_dir():
            continue
        for case_dir in sorted(p for p in fn_dir.iterdir() if p.is_dir()):
            input_text = (case_dir / "input.md").read_text(encoding="utf-8")
            expected_text = (case_dir / "expected.md").read_text(encoding="utf-8")
            meta = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            cases.append(FixtureCase(fn_name, case_dir.name, case_dir,
                                     input_text, expected_text, meta))
    return cases


def run_census() -> list[dict]:
    """Run every committed fixture through its own function; return one
    result row per fixture case (read-only — no fixture is modified)."""
    rows = []
    for case in load_fixture_cases():
        fn = FUNCTIONS[case.function]
        call_kwargs = case.meta.get("call_kwargs", {})
        actual = fn(case.input_text, **call_kwargs)
        rows.append({
            "function": case.function,
            "case": case.case,
            "classification": CLASSIFICATION[case.function],
            "matches_expected": actual == case.expected_text,
            "tokens_before": extract_tokens(case.input_text),
            "tokens_after": extract_tokens(case.expected_text),
        })
    return rows


def main() -> int:
    rows = run_census()
    by_function: dict[str, list[dict]] = {}
    for row in rows:
        by_function.setdefault(row["function"], []).append(row)

    print(f"{'function':32} {'fixtures':9} {'all pass':9}")
    print("-" * 54)
    ok = True
    for name in CHAIN_ORDER:
        cases = by_function.get(name, [])
        passing = sum(1 for c in cases if c["matches_expected"])
        all_pass = passing == len(cases) and len(cases) > 0
        ok = ok and all_pass
        print(f"{name:32} {len(cases):<9} {str(all_pass):<9}")
    print()
    for name in CHAIN_ORDER:
        print(f"# {name}\n{CLASSIFICATION[name]}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
