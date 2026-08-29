"""Does this invented figure, id or date collide with the archive? — verified, not eyeballed.

The invented-shape convention is only worth anything if the shape is CHECKED.
A 3,351-document universe prints ~3.5x10^5 distinct money figures with cents
and ~2x10^5 digit runs, so a small "obviously made up" amount collides with
something roughly a third of the time, and a plausible account number nearly
always does. Nobody can tell by looking; this says.

    python -m tools.fixpriv_invent --data-dir <cold cache> --rows <run>/rows.csv \\
        --token 1,234.56 --token 8877665544 --token 2031-04-30
    python -m tools.fixpriv_invent ... --candidates <file of tokens, one per line>
    python -m tools.fixpriv_invent ... --propose money:5 --propose digits:3

Every candidate is classified with the SCANNER's own patterns (so a candidate
that is not a token of any class is reported as such — it would never have been
scanned), then looked up in the universe. `--propose <class>:<n>` walks
deterministically from a fixed seed and prints the first `n` tokens of that
class that DO NOT collide, so a fixture repair does not have to guess.

Exit 0 when every candidate is clear, 1 when any collides, 2 when a candidate
is not a scannable token at all. Read-only over the archive; artifacts by
direct file path; no OCR, no hosted model, $0.
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.privacy_scan_branch import (  # noqa: E402
    cached_text,
    population,
    self_check,
    tokens_of,
)

#: The invented eras. The archive was frozen on 2026-08-06 and its statements
#: run to 2026; a date in 2031 cannot be a document date, which is why the card
#: makes it the convention.
INVENTED_YEAR = 2031


def universe(args: argparse.Namespace) -> tuple[dict[str, set[str]], int]:
    from webapp.artifact_cache import ocr_settings_key

    root = args.data_dir / "artifacts"
    ocr_keys = [ocr_settings_key(force_ocr=f, allow_local_ocr=l, allow_visual_ocr=v)
                for f, l, v in itertools.product((False, True), repeat=3)]
    printed: dict[str, set[str]] = {c: set() for c in ("MONEY", "DIGITS", "DATES", "WORDS")}
    read = 0
    for sha in population(args):
        text = cached_text(root, sha, ocr_keys)
        if text is None:
            continue
        read += 1
        for cls, values in tokens_of(text, args.digit_min, args.word_min).items():
            printed[cls].update(values)
    return printed, read


def classify(token: str, digit_min: int, word_min: int) -> list[str]:
    found = tokens_of(token, digit_min, word_min)
    return sorted(cls for cls, values in found.items() if token.upper() in values)


def proposals(kind: str, count: int, printed: dict[str, set[str]]) -> list[str]:
    """Deterministic candidates of one class that the archive does not print."""
    out: list[str] = []
    if kind == "money":
        # Walk a fixed arithmetic sequence of cent values; no randomness, so the
        # same call gives the same answer on any host.
        cents = 777_777_77
        while len(out) < count and cents < 999_999_99 * 9:
            value = f"{cents // 100:,}.{cents % 100:02d}"
            if value not in printed["MONEY"] and value.replace(",", "") not in printed["MONEY"]:
                out.append(value)
            cents += 1_010_101
    elif kind == "digits":
        seed = 7_000_000_001
        while len(out) < count and seed < 9_999_999_999:
            value = str(seed)
            if value not in printed["DIGITS"]:
                out.append(value)
            seed += 1_010_101
    elif kind == "dates":
        for month, day in itertools.product(range(1, 13), (5, 15, 25)):
            if len(out) >= count:
                break
            value = f"{INVENTED_YEAR}-{month:02d}-{day:02d}"
            if value not in printed["DATES"]:
                out.append(value)
    else:
        raise SystemExit(f"unknown class for --propose: {kind!r} (money, digits, dates)")
    return out


def main(argv: list[str] | None = None) -> int:
    self_check()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shas", action="append", default=[], type=Path)
    parser.add_argument("--sha", action="append", default=[])
    parser.add_argument("--rows", type=Path, default=None)
    parser.add_argument("--where", action="append", default=[])
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--token", action="append", default=[])
    parser.add_argument("--candidates", type=Path, default=None)
    parser.add_argument("--propose", action="append", default=[],
                        help="<money|digits|dates>:<n> — n non-colliding tokens of that class")
    parser.add_argument("--digit-min", type=int, default=5)
    parser.add_argument("--word-min", type=int, default=4)
    args = parser.parse_args(argv)

    candidates = list(args.token)
    if args.candidates is not None:
        candidates += [line.split("#", 1)[0].strip()
                       for line in args.candidates.read_text(encoding="utf-8").splitlines()
                       if line.split("#", 1)[0].strip()]
    printed, read = universe(args)
    if read == 0:
        print("read 0 documents: the universe is empty and the answer would be vacuous",
              file=sys.stderr)
        return 2
    print(f"universe: {read} documents · "
          + " · ".join(f"{c} {len(printed[c])}" for c in ("MONEY", "DIGITS", "DATES")))
    worst = 0
    for token in candidates:
        classes = classify(token, args.digit_min, args.word_min)
        if not classes:
            print(f"NOT-A-TOKEN {token!r}: no class of the scan would ever look at it")
            worst = max(worst, 2)
            continue
        hit = [cls for cls in classes if token.upper() in printed.get(cls, ())]
        if hit:
            print(f"COLLIDES   {token!r} as {'/'.join(hit)}")
            worst = max(worst, 1)
        else:
            print(f"CLEAR      {token!r} as {'/'.join(classes)}")
    for spec in args.propose:
        kind, _, count = spec.partition(":")
        for value in proposals(kind.strip().lower(), int(count or 5), printed):
            print(f"PROPOSE    {kind.strip().lower()}: {value}")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
