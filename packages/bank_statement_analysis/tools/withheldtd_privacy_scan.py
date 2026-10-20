"""Nothing printed on the TD families' documents may be in the branch diff.

The batch-7 standing rule, made re-derivable for this card (W3 §WITHHELDTD):

    python -m tools.withheldtd_privacy_scan \
        --rows <reports>/<run-id>/rows.csv --data-dir <checkout>/webapp_data \
        --base <commit>

Read-only, offline, $0: cached OCR text is reached by DIRECT artifact path
(never the `webapp_data` sqlite index) and no analysis is run at all.

Three classes, because they fail for different reasons.

A. DISTINCTIVE tokens — what a copied figure or a copied name looks like: a
   money token whose cents are not `00`; an account number; a nine-digit-or-
   longer run; a capitalised multi-word run that is not the bank's own printed
   furniture. **Must be 0.**
B. PHRASES — every contiguous run of three tokens from a printed line, after
   the furniture and the calendar tokens are removed. That is what an "example
   block copied from a document" looks like, and it is the class the batch-7
   BLOCK was. **Must be 0.**
C. COLLISIONS — round figures (`100.00`), calendar tokens, and the bank's own
   furniture. Reported with counts and NOT required to be zero: a fixture built
   from small round numbers before any document was read collides with a
   126-document corpus every time, and scoring those as leaks would make the
   scan mean nothing. The list is printed so the adjudication is visible rather
   than assumed.

FURNITURE is the bank's own printed layout vocabulary — column legends, section
headings, summary labels, transaction codes, the issuer line, page footers. The
parsers key on it by construction, so it cannot be absent from tracked source,
and the standing rule admits it: "institution furniture ... is allowed and must
be justified as furniture".
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from collections import Counter
from pathlib import Path

PARSERS = ("td_canada_native", "td_canada_french", "td_us")

#: Every entry is a column legend, a section heading, a summary label, one of
#: TD's own transaction codes, the issuer line, or a page footer.
FURNITURE = {
    w.lower() for w in """
    account activity amount balance bank beginning cash charges checking checks
    collected credit credits cust daily date deposit deposits description
    ending equal fdic housing insured lender n.a. no number other paid payments
    period posting primary ref serial service statement subtotal summary td
    withdrawals withdra business simple average electronic continued indicates
    break in serial sequence or check processed electronically and listed under
    page of forward solde reporte retraits depots chqs enclosed joints
    the toronto-dominion comptes emis par la banque monthly aver cr bal min
    every day b chequing account cad usd investor
    e-tfr e-transfer tfr-fr tfr-to tfr-de tfr-a send cancel reclaim gc atm w/d
    dep depot envoi recept vfc msp cln pay gst bus interet credit d'interet mc
    bate agrcunt descruption ssrolint armount amqunt xxx yyy jan feb mar apr may
    jun jul aug sep oct nov dec fev avr mai aou 2025 2026
    """.split()
}

DISTINCTIVE = [
    (r"\b\d[\d,]*\.\d{2}\b", "money"),
    (r"\b\d[\d ]*,\d{2}\b", "money"),
    (r"\b\d{4}-\d{6,}\b", "account"),
    (r"\b\d{2,3}-\d{7,}\b", "account"),
    (r"\b\d{9,}\b", "serial"),
]
#: Digits are excluded from the continuation on purpose: `Electronic Deposits
#: 300.00` is a furniture heading with a figure beside it, and the figure is
#: already classified on its own.
NAME_RUN = re.compile(r"\b[A-Z][A-Za-z'&.-]{2,}(?: [A-Z][A-Za-z'&.-]{1,}){1,5}\b")
#: A calendar range prints identically on every statement covering that month.
DATE_TOKEN = re.compile(r"^(?:\d{1,4}|\d{4}-[A-Z][a-z]{2}|\d{2}/\d{2}(?:/\d{2,4})?)$")


def invented(token: str) -> bool:
    """A figure whose cents are `00` — what an invented fixture figure is."""
    body = token.replace(" ", "").replace(",", ".")
    return body.rpartition(".")[2] == "00"


def texts(rows_csv: Path, data_dir: Path):
    """(sha, markdown) for every document the changed parsers can run on."""
    import csv

    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import STAGE_OCR, cache_key, ocr_settings_key

    keys = [ocr_settings_key(force_ocr=f, allow_local_ocr=l, allow_visual_ocr=v)
            for f, l, v in itertools.product((False, True), repeat=3)]
    root = data_dir / "artifacts"
    with rows_csv.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    shas = sorted({r["content_sha256"] for r in rows
                   if r["parser_id"] in PARSERS or "td_us" in r["candidates"]})
    for sha in shas:
        best = None
        for key in keys:
            composed = cache_key(STAGE_OCR, sha, key)
            path = root / STAGE_OCR / composed[:2] / f"{composed}.json"
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            document = (payload.get("artifact") or {}).get("document")
            if not isinstance(document, dict):
                continue
            pages = [str(p) for p in (document.get("pages") or [])]
            markdown = StatementMarkdown(
                source_file="scan.pdf", model=str(document.get("model") or ""),
                pages=pages).to_markdown()
            if best is None or len(markdown) > len(best):
                best = markdown
        yield sha, best


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--base", required=True, help="the commit the branch started at")
    args = parser.parse_args(argv)

    from tools.git_layout import diff as layout_diff, working_tree

    diff = layout_diff(args.base, working_tree())
    added = "\n".join(line[1:] for line in diff.splitlines()
                      if line.startswith("+") and not line.startswith("+++"))
    print(f"branch diff {len(diff)} chars; added lines {len(added)} chars")

    distinctive: Counter[str] = Counter()
    phrases: Counter[str] = Counter()
    collisions: Counter[str] = Counter()
    read = total = 0
    for _sha, markdown in texts(args.rows, args.data_dir):
        total += 1
        if markdown is None:
            continue
        read += 1
        for pattern, kind in DISTINCTIVE:
            for token in (t.strip() for t in re.findall(pattern, markdown)):
                target = collisions if kind == "money" and invented(token) else distinctive
                target[token] += 1
        for name in NAME_RUN.findall(markdown):
            words = [w.lower().strip(".,#") for w in name.split()]
            target = collisions if all(w in FURNITURE for w in words) else distinctive
            target[name] += 1
        for line in markdown.splitlines():
            tokens = [t for t in line.split()
                      if t.lower().strip(".,:#") not in FURNITURE and not DATE_TOKEN.match(t)]
            for i in range(len(tokens) - 2):
                phrases[" ".join(tokens[i:i + 3])] += 1

    print(f"documents read {read} of {total}")
    print(f"distinctive tokens {len(distinctive)}; three-token phrases {len(phrases)}; "
          f"collisions tracked {len(collisions)}")

    hits_a = sorted(t for t in distinctive if len(t) >= 5 and t in added)
    hits_b = sorted(p for p in phrases if len(p) >= 10 and p in added)
    print(f"A. DISTINCTIVE TOKENS IN THE DIFF: {len(hits_a)}")
    for token in hits_a:
        for line in [ln for ln in added.splitlines() if token in ln][:2]:
            print(f"   {token!r} | {line.strip()[:140]}")
    print(f"B. THREE-TOKEN PRINTED PHRASES IN THE DIFF: {len(hits_b)}")
    for phrase in hits_b:
        for line in [ln for ln in added.splitlines() if phrase in ln][:2]:
            print(f"   {phrase!r} | {line.strip()[:140]}")
    adjudicated = sorted(((c, t) for t, c in collisions.items() if t in added), reverse=True)
    print(f"C. COLLISIONS (reported, not required 0): {len(adjudicated)}")
    print("   " + ", ".join(f"{t!r}x{c}" for c, t in adjudicated[:40]))
    return 1 if (hits_a or hits_b) else 0


if __name__ == "__main__":
    raise SystemExit(main())
