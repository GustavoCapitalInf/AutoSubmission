"""tools/p22classify_mutation_table.py — the P22-CLASSIFY mutation table harness (committed at the review's
request: BATCH9-RULES, "instruments that produce headline numbers are committed under tools/").

    python tools/p22classify_mutation_table.py            # from the repository root; refuses a dirty tree


Every mutant is an exact single-occurrence textual edit of one production
file (or a list of them), applied on a CLEAN tree, exercised by the three
layout test files WITHOUT -x, and restored with `git checkout --` in a
`finally`; `git status --porcelain` must be empty before the run starts and
after every mutant. The failing test ids are the killers; a mutant with no
failing test SURVIVES and is reported as such.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
TESTS = ["tests/test_layout_boundary.py", "tests/test_layout_signals.py", "tests/test_layout_document_class.py"]
DC = "layout/document_class.py"
SG = "layout/signals.py"
RF = "layout/refusals.py"

MUTANTS: list[tuple[str, str, list[tuple[str, str, str]]]] = [
    ("M1", "drop the MICR rule: the bottom band is never detected", [
        (DC, "if page.height and line.y0 is not None and line.y0 >= MICR_BAND_FRACTION * page.height:",
         "if False:"),
    ]),
    ("M2", "drop the aspect-ratio bound: every page is cheque-shaped", [
        (DC, "aspect_ok = CHEQUE_ASPECT_MIN <= aspect <= CHEQUE_ASPECT_MAX", "aspect_ok = True"),
    ]),
    ("M3", "drop Page X of Y gap detection", [
        (DC, "        if after <= before or after - before > page_after - page_before:\n            gap_after = page_before\n            break",
         "        if False:\n            gap_after = page_before\n            break"),
    ]),
    ("M4", "require only two of the three anchors for STATEMENT_COMPLETE — AS APPLIED: the missing-anchor findings are skipped when two of the three anchors are present (the findings rule is the completeness gate)", [
        (DC, "    if not signals.period:\n        findings.append(Finding(\"missing_period\", None, \"\"))",
         "    if not signals.period and signals.anchors < 2:\n        findings.append(Finding(\"missing_period\", None, \"\"))"),
        (DC, "    if not signals.opening:\n        findings.append(Finding(\"missing_opening\", None, \"\"))",
         "    if not signals.opening and signals.anchors < 2:\n        findings.append(Finding(\"missing_opening\", None, \"\"))"),
        (DC, "    if not signals.closing:\n        findings.append(Finding(\"missing_closing\", None, \"\"))",
         "    if not signals.closing and signals.anchors < 2:\n        findings.append(Finding(\"missing_closing\", None, \"\"))"),
    ]),
    ("M5", "the table signal without the alignment test in evidence mode", [
        (DC, "            if doc.mode == \"evidence\":\n                if not _aligned(group, page.char_width):\n                    continue\n                aligned_any = True",
         "            if doc.mode == \"evidence\":\n                aligned_any = True"),
    ]),
    ("M6a", "the table-versus-cheque conflict resolved by priority (the cheque wins)", [
        (DC, "    if signals.table and cheque:\n        return uncertain()",
         "    if signals.table and cheque:\n        signals.table = False"),
    ]),
    ("M6b", "the card-versus-running-balance conflict resolved by priority (the balance wins)", [
        (DC, "    if \"card\" in lexical_kinds and signals.running_balance:\n        return uncertain()",
         "    if \"card\" in lexical_kinds and signals.running_balance:\n        lexical_kinds.discard(\"card\")"),
    ]),
    ("M7", "degraded mode allowed to emit structural", [
        (DC, "signals.aligned = aligned_any and doc.mode == \"evidence\"", "signals.aligned = True"),
    ]),
    ("M8", "a time-dependent step inside classify_document", [
        (DC, "    doc = _build_doc(evidence, tuple(page_texts) if page_texts is not None else None)",
         "    import time\n    time.time()\n    doc = _build_doc(evidence, tuple(page_texts) if page_texts is not None else None)"),
    ]),
    ("M9", "an issuer string added to a lexicon", [
        (SG, "en=(\"beginning balance\", \"opening balance\",", "en=(\"beginning balance\", \"wells fargo\", \"opening balance\","),
    ]),
    ("M10", "FILE_INVALID decided only when no text is available (after a text signal)", [
        (DC, "    if _file_invalid(profile):\n        # Decided from the facts alone",
         "    if _file_invalid(profile) and page_texts is None and evidence is None:\n        # Decided from the facts alone"),
    ]),
    ("M11", "the activity-export rule requiring an anchor", [
        (DC, "if signals.table and signals.anchors == 0 and (signals.reverse_chronology or signals.pending):",
         "if signals.table and signals.anchors >= 1 and (signals.reverse_chronology or signals.pending):"),
    ]),
    ("M12", "a third-party import under layout/ (lazy, never executed)", [
        (RF, "PROFILE_CLASSIFICATIONS: tuple[str, ...] = (\"digital\", \"scanned\", \"mixed\", \"unknown\")",
         "PROFILE_CLASSIFICATIONS: tuple[str, ...] = (\"digital\", \"scanned\", \"mixed\", \"unknown\")\n\n\ndef _mutant():\n    import numpy\n    return numpy"),
    ]),
    ("M13", "the short ledger dropped: a complete statement must show five rows", [
        (DC, "    if counted_rows < TABLE_MIN_ROWS and 1 <= len(ledger) < TABLE_MIN_ROWS:",
         "    if False:"),
    ]),
    ("M14", "an unmarked page between two marked pages counted as a gap", [
        (DC, "        if after <= before or after - before > page_after - page_before:",
         "        if after != before + 1:"),
    ]),
    ("M15", "the coinciding balance pair no longer a zero-activity structure", [
        (DC, "            and signals.opening_cents == signals.closing_cents and signals.ledger_rows == 0 and not signals.table):",
         "            and False):"),
    ]),
    ("M16", "the statement-balance label forms removed from the lexicon", [
        (SG, '"beginning statement balance", ', ""),
        (SG, '"balance this statement", ', ""),
    ]),
    ("M17", "rule (c) reads only the FIRST opening and closing label lines", [
        (DC, "    opening = [(line, find_dates(line.text, day_first=day_first)) for line in signals.opening_lines]\n    closing = [(line, find_dates(line.text, day_first=day_first)) for line in signals.closing_lines]",
         "    opening = [(line, find_dates(line.text, day_first=day_first)) for line in signals.opening_lines[:1]]\n    closing = [(line, find_dates(line.text, day_first=day_first)) for line in signals.closing_lines[:1]]"),
    ]),
    ("M18", "the `statement ending` family removed from the period lexicon", [
        (SG, '"statement from", "statement ending",\n            "this statement", "last statement", "statement closing date", "period from"),',
         '"statement from"),'),
    ]),
    ("M19", "a page marker's words counted as words of a stacked date-range cell", [
        (DC, "    marker = find_page_marker(text)\n    if marker is not None:\n        folded = folded[:marker.start] + \" \" * (marker.end - marker.start) + folded[marker.end:]",
         "    marker = None"),
    ]),
    ("M20", "the card lexicon beside deposit furniture no longer a conflict on the table branch (falls through to a deposit statement)", [
        (DC, "        if signals.deposit_account:\n            return uncertain()\n        if signals.single_amount_column and not signals.running_balance:",
         "        if signals.single_amount_column and not signals.running_balance and not signals.deposit_account:"),
    ]),
    ("M21", "the FIRST marker line on a page wins (a prose cross-reference becomes the marker)", [
        (DC, "            if best is None or other_words <= best[0]:", "            if best is None:"),
    ]),
    ("M22", "rule (b) reads a money-bearing line (a ledger row's own date range is the period)", [
        (DC, "        if len(dates) >= 2 and not find_money(text):", "        if len(dates) >= 2:"),
    ]),
    ("M23", "a dash is a MICR character again (a date line is MICR-shaped)", [
        (SG, 'MICR_SYMBOLS: frozenset[str] = frozenset("⑆⑇⑈⑉:;|cCaA")', 'MICR_SYMBOLS: frozenset[str] = frozenset("⑆⑇⑈⑉:;|cCaA-.")'),
    ]),
    ("M24", "the illegible floor ignores modality", [
        (DC, '        if signals.words_per_page < floor and profile.classification != "digital":', "        if signals.words_per_page < floor:"),
    ]),
    ("M25", "only two shared right edges may cover a table", [
        (DC, "TABLE_ALIGN_MAX_COLUMNS = 3", "TABLE_ALIGN_MAX_COLUMNS = 2"),
    ]),
    ("M26", "a date touching a hyphen is no date (the hyphen-joined range is invisible)", [
        (SG, "    r\"(?![\\d/.])(?!-(?!\\d{1,2}[/.-]\\d{1,2}[/.-]\\d))\"", "    r\"(?![\\d/.-])\""),
    ]),
    ("M27", "the last marked sequence need not reach its own total", [
        (DC, "    if gap_after is None and owed > trailing_unmarked:", "    if gap_after is None and numbers[-1] < declared and n_pages < declared:"),
    ]),
]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=WT, capture_output=True, text=True).stdout


def clean() -> bool:
    return git("status", "--porcelain").strip() == ""


def apply(edits: list[tuple[str, str, str]]) -> None:
    for rel, old, new in edits:
        path = WT / rel
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f"{rel}: expected exactly one occurrence of the mutant site, found {count}: {old[:60]!r}")
        path.write_text(text.replace(old, new), encoding="utf-8")


def restore(edits: list[tuple[str, str, str]]) -> None:
    files = sorted({rel for rel, _, _ in edits})
    for attempt in range(5):
        subprocess.run(["git", "checkout", "--", *files], cwd=WT, capture_output=True, text=True)
        if clean():
            return
    raise RuntimeError("tree not clean after restore")


def run_tests() -> tuple[int, int, list[str]]:
    result = subprocess.run([sys.executable, "-m", "pytest", *TESTS, "-q", "-p", "no:cacheprovider", "--no-header"],
                            cwd=WT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = result.stdout
    failed = re.findall(r"^(?:FAILED|ERROR) (\S+)", out, re.MULTILINE)
    m = re.search(r"(\d+) passed", out)
    passed = int(m.group(1)) if m else 0
    m = re.search(r"(\d+) failed", out)
    nfailed = int(m.group(1)) if m else 0
    m2 = re.search(r"(\d+) errors?", out)
    if m2 and not failed:
        nfailed = max(nfailed, int(m2.group(1)))
    return passed, nfailed, failed


def main() -> int:
    if not clean():
        print("REFUSED: the tree is not clean")
        return 3
    print(f"baseline tree: {git('rev-parse', '--short', 'HEAD').strip()}")
    passed, nfailed, failed = run_tests()
    print(f"baseline: {passed} passed, {nfailed} failed")
    if nfailed:
        print("REFUSED: baseline is not green")
        return 3
    rows = []
    for mid, title, edits in MUTANTS:
        try:
            apply(edits)
            passed, nfailed, failed = run_tests()
        finally:
            restore(edits)
        status = "KILLED" if nfailed else "SURVIVED"
        killers = sorted({f.split("::")[0].replace("tests/", "") + "::" + f.split("::")[1].split("[")[0] for f in failed})
        rows.append((mid, title, status, nfailed, killers))
        print(f"{mid} {status} ({nfailed} failing) — {title}")
        for k in killers[:8]:
            print(f"      {k}")
        if len(killers) > 8:
            print(f"      ... {len(killers) - 8} more")
        assert clean(), "tree dirty after restore"
    print("\n| # | mutant as applied | result | killers (test ids, first three) |")
    print("|---|---|---|---|")
    for mid, title, status, nfailed, killers in rows:
        print(f"| {mid} | {title} | **{status}** ({nfailed}) | {'; '.join(f'`{k}`' for k in killers[:3])} |")
    survivors = [r for r in rows if r[2] == "SURVIVED"]
    print(f"\n{len(rows) - len(survivors)} / {len(rows)} killed; survivors: {[r[0] for r in survivors]}")
    print("final tree clean:", clean())
    return 0 if not survivors else 1


if __name__ == "__main__":
    sys.exit(main())
