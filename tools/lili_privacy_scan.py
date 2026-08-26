"""Does any token this family PRINTS appear in the branch? — W3 §LILI.

The wave's standing privacy rule: no archive content may enter tracked source
— not a balance, an amount, a name, an account number, nor an "example" block
copied from a document; fixtures are INVENTED. This tool is the evidence for
that claim rather than an assurance about it:

    python -m tools.lili_privacy_scan \
        --data-dir <checkout>/webapp_data --base <base-commit>

READ-ONLY, $0.00, index-free: OCR payloads by direct artifact path only, the
`webapp_data` sqlite index is never opened, nothing is written, no model call.
THE TOOL PRINTS NO TOKEN IT DID NOT ALREADY FIND IN THE TRACKED FILES — only
counts, and the hits themselves, which by construction are already committed
and are the thing a reviewer has to adjudicate.

TWO HAYSTACKS, and the distinction is the whole point:

* `authored`  — the lines this branch ADDS (the `+` lines of the diff against
                `--base`, working tree included). Content the branch is
                responsible for. The numeric classes must be zero here.
* `inherited` — everything else in the files the branch touches: context
                lines, and lines that were already in the tree at `--base`.
                A hit here is a coincidence between the family's figures and
                somebody else's fixture, and is reported so it is visible
                rather than silently counted as a violation.

FIVE CLASSES:

* `money`   — every printed figure. Tokens whose value is ZERO are counted
              and excluded: `0.00` is the additive identity, present in every
              accounting fixture ever written, and treating it as archive
              content would make the measurement meaningless.
* `digits`  — every digit run of five or more: account numbers,
              authorization codes, telephone digits.
* `dates`   — every printed `m/d/y` token and every day-first long date.
* `rare`    — the family's CUSTOMER vocabulary: alphabetic tokens of four or
              more characters that appear in at most `--rare-max` of the
              family's documents. Holder names, street names, cities and
              merchant strings are printed on one customer's statements;
              template furniture is printed on all of them. This is the class
              that carries the privacy risk. It is reported twice: folded to
              lower case, where ordinary English prose in a docstring collides
              with whatever a merchant string happened to spell, and in the
              family's OWN PRINTED CASING, which is the form a copy would
              have. The cased count must be zero.
* `words`   — every alphabetic token of four or more characters, `rare`
              included. This class CANNOT be zero and is not expected to be:
              it contains the template's own furniture, which a reader must
              match by name in order to read the template at all, and
              ordinary English. Its hits are printed so each can be read.

Matching is by TOKEN, not by substring: `8.19` is "in" `308.19` and `wire` is
"in" `wireless`, and reporting those would bury a real copy under fragments of
the reader's own invented figures.
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

from ocr.document import StatementMarkdown
from tools.lili_family_replay import DEFAULT_CENSUS, DEFAULT_FAMILY, family_shas
from webapp.artifact_cache import STAGE_OCR, cache_key, ocr_settings_key

REPO = Path(__file__).resolve().parent.parent

_OCR_KEYS = [
    ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
    for force, local, visual in itertools.product((False, True), repeat=3)
]

_MONEY_RE = re.compile(r"\d[\d,]*\.\d{2}")
_DIGITS_RE = re.compile(r"\d{5,}")
_SLASH_DATE_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}")
_LONG_DATE_RE = re.compile(r"\d{1,2}\s+[A-Z][a-z]+,\s+\d{4}")
_WORD_RE = re.compile(r"[A-Za-z]{4,}")

MUST_BE_ZERO = ("money", "digits", "dates", "rare_cased")


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


def tokens_of(text: str) -> dict[str, set[str]]:
    """The five token classes of one text. `rare` is decided by the caller."""
    money: set[str] = set()
    zeros: set[str] = set()
    for token in _MONEY_RE.findall(text):
        bare = token.replace(",", "")
        try:
            value = float(bare)
        except ValueError:
            continue
        (zeros if value == 0 else money).add(token)
        if value != 0:
            money.add(bare)
    return {
        "money": money,
        "zeros": zeros,
        "digits": set(_DIGITS_RE.findall(text)),
        "dates": set(_SLASH_DATE_RE.findall(text)) | set(_LONG_DATE_RE.findall(text)),
        "words": {word.casefold() for word in _WORD_RE.findall(text)},
    }


def family_tokens(texts: list[str], rare_max: int) -> dict[str, set[str]]:
    merged: dict[str, set[str]] = {k: set() for k in ("money", "zeros", "digits", "dates", "words")}
    document_count: collections.Counter[str] = collections.Counter()
    cased: set[str] = set()
    for text in texts:
        per = tokens_of(text)
        for key, values in per.items():
            merged[key] |= values
        document_count.update(per["words"])
        cased.update(_WORD_RE.findall(text))
    merged["rare"] = {w for w, n in document_count.items() if n <= rare_max}
    #: The same words in the casing the documents print them in. A docstring
    #: that says "check the gate" is not a merchant string shouting the
    #: same letters back at it.
    merged["rare_cased"] = {w for w in cased if w.casefold() in merged["rare"]}
    return merged


def haystacks(base: str) -> tuple[str, str]:
    """`(authored, inherited)`: the branch's added lines, and everything else."""
    diff = subprocess.run(
        ["git", "diff", base], cwd=REPO,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if diff.returncode != 0:
        raise SystemExit(f"git diff failed: {diff.stderr.strip()}")
    authored = "\n".join(
        line[1:] for line in diff.stdout.split("\n")
        if line.startswith("+") and not line.startswith("+++")
    )
    names = subprocess.run(
        ["git", "diff", "--name-only", base], cwd=REPO,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    whole = []
    for name in names.stdout.split("\n"):
        path = REPO / name.strip()
        if name.strip() and path.is_file():
            whole.append(path.read_text(encoding="utf-8", errors="replace"))
    inherited_text = "\n".join(whole)
    return authored, inherited_text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--census", default=DEFAULT_CENSUS, type=Path)
    parser.add_argument("--family", default=DEFAULT_FAMILY)
    parser.add_argument("--rare-max", type=int, default=3)
    parser.add_argument(
        "--allow", default="",
        help=(
            "comma-separated tokens ADJUDICATED as coincidences rather than "
            "copies. A named ratchet, not a pardon: every entry is printed "
            "back, and a token that stops appearing is reported too, so the "
            "list cannot quietly outlive the thing it excuses."
        ),
    )
    args = parser.parse_args()

    artifacts = args.data_dir / "artifacts"
    shas = family_shas(args.census, args.family)
    texts = [t for t in (cached_text(artifacts, sha) for sha in shas) if t is not None]
    family = family_tokens(texts, args.rare_max)
    authored, inherited = haystacks(args.base)
    authored_tokens = tokens_of(authored)
    inherited_tokens = tokens_of(inherited)
    for bucket, text in ((authored_tokens, authored), (inherited_tokens, inherited)):
        bucket["rare"] = bucket["words"]
        bucket["rare_cased"] = set(_WORD_RE.findall(text))

    print(f"documents scanned            : {len(texts)} of {len(shas)}")
    print(f"zero-valued figures excluded : {len(family['zeros'])} distinct")
    print(f"branch AUTHORED (added lines): {len(authored)} chars")
    print(f"files the branch touches     : {len(inherited)} chars at HEAD")
    print(f"rare-word threshold          : printed in <= {args.rare_max} of "
          f"{len(texts)} documents")
    allowed = {token for token in args.allow.split(",") if token}
    if allowed:
        print(f"adjudicated coincidences     : {len(allowed)} "
              f"({', '.join(sorted(allowed))})")
    failed = False
    used: set[str] = set()
    for name in ("money", "digits", "dates", "rare_cased", "rare", "words"):
        tokens = family[name]
        hit_authored = sorted(tokens & authored_tokens[name])
        hit_inherited = sorted(tokens & inherited_tokens[name])
        print(f"\n{name}: {len(tokens)} distinct family tokens  -> "
              f"{len(hit_authored)} AUTHORED, {len(hit_inherited)} inherited")
        for token in hit_authored:
            mark = "  (adjudicated)" if token in allowed else ""
            print(f"    AUTHORED {token!r}{mark}")
        for token in hit_inherited:
            if token not in hit_authored:
                print(f"    inherited {token!r}")
        unexplained = [token for token in hit_authored if token not in allowed]
        if name in MUST_BE_ZERO and unexplained:
            failed = True
        used.update(token for token in hit_authored if token in allowed)
    stale = sorted(allowed - used)
    if stale:
        print(f"\nadjudicated tokens that no longer appear: {stale} — remove them")
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
