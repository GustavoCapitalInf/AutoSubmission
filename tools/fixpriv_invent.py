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
    excluded_by,
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


def generated(token: str, digit_min: int, word_min: int) -> dict[str, set[str]]:
    """Every token of every class the candidate TEXT would put in the tree.

    Not the candidate itself: writing a six-figure amount into a file writes a
    digit run it contains, which the scanner reads as a DIGITS token in its own
    right. The first version of this tool asked only whether the candidate was
    in the MONEY universe, called sixteen colliding figures CLEAR, and the
    whole-tree scan is what caught it.
    """
    found = tokens_of(token, digit_min, word_min)
    return {cls: values for cls, values in found.items() if cls != "WORDS" and values}


def collisions(token: str, printed: dict[str, set[str]], digit_min: int, word_min: int
               ) -> list[tuple[str, str]]:
    """(class, token) for everything the candidate generates that would be RESIDUE.

    A generated token the committed exclusion table already excuses — a round
    `.00` figure, a sub-unit constant — is not a finding however loudly it
    collides, so it is not one here either; otherwise `0.00` alone makes every
    scale impossible, which is what the first scale search reported.
    """
    return sorted(
        (cls, value)
        for cls, values in generated(token, digit_min, word_min).items()
        for value in values
        if value in printed.get(cls, ())
        and excluded_by(cls, "tests/invented.py", value, value) is None
    )


def scale_search(originals: list[str], printed: dict[str, set[str]],
                 digit_min: int, word_min: int, limit: int) -> int | None:
    """The smallest whole-number CENT scale under which nothing collides.

    A whole-number scale on integer cents is exact, so every sum, chain and
    total an invented fixture is built on still closes after it — which is why
    a fixture can be moved away from the archive without being re-derived.
    """
    cents = []
    for token in originals:
        digits = token.replace(",", "").replace(".", "")
        if not digits.isdigit():
            return None
        cents.append(int(digits))
    for scale in range(2, limit + 1):
        for value in cents:
            product = value * scale
            candidate = f"{product // 100}.{product % 100:02d}"
            if collisions(candidate, printed, digit_min, word_min):
                break
        else:
            return scale
    return None


def proposals(kind: str, count: int, printed: dict[str, set[str]]) -> list[str]:
    """Deterministic candidates of one class that the archive does not print."""
    out: list[str] = []
    if kind == "money":
        # Walk a fixed arithmetic sequence of cent values; no randomness, so the
        # same call gives the same answer on any host.
        cents = 777_777_77
        while len(out) < count and cents < 999_999_99 * 9:
            value = f"{cents // 100:,}.{cents % 100:02d}"
            if not collisions(value, printed, 5, 4) and not collisions(value.replace(",", ""), printed, 5, 4):
                out.append(value)
            cents += 1_010_101
    elif kind == "digits":
        seed = 7_000_000_001
        while len(out) < count and seed < 9_999_999_999:
            value = str(seed)
            if not collisions(value, printed, 5, 4):
                out.append(value)
            seed += 1_010_101
    elif kind == "dates":
        for month, day in itertools.product(range(1, 13), (5, 15, 25)):
            if len(out) >= count:
                break
            value = f"{INVENTED_YEAR}-{month:02d}-{day:02d}"
            if not collisions(value, printed, 5, 4):
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
    parser.add_argument("--scale-search", type=Path, default=None,
                        help="a file of INVENTED money tokens: report the smallest whole-number "
                             "cent scale under which none of them, nor any digit run they "
                             "generate, collides")
    parser.add_argument("--scale-limit", type=int, default=100_000)
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
        makes = generated(token, args.digit_min, args.word_min)
        if not makes:
            print(f"NOT-A-TOKEN {token!r}: no class of the scan would ever look at it")
            worst = max(worst, 2)
            continue
        hit = collisions(token, printed, args.digit_min, args.word_min)
        shape = "/".join(f"{cls}:{len(v)}" for cls, v in sorted(makes.items()))
        if hit:
            print(f"COLLIDES   {token!r} — " + ", ".join(f"{c} {v}" for c, v in hit))
            worst = max(worst, 1)
        else:
            print(f"CLEAR      {token!r} generates {shape}")
    if args.scale_search is not None:
        originals = [line.split("#", 1)[0].strip()
                     for line in args.scale_search.read_text(encoding="utf-8").splitlines()
                     if line.split("#", 1)[0].strip()]
        found = scale_search(originals, printed, args.digit_min, args.word_min, args.scale_limit)
        if found is None:
            print(f"NO-SCALE   no whole-number scale up to {args.scale_limit} clears "
                  f"all {len(originals)} figures")
            worst = max(worst, 1)
        else:
            print(f"SCALE      {found} clears all {len(originals)} figures and every digit "
                  f"run they generate")
    for spec in args.propose:
        kind, _, count = spec.partition(":")
        for value in proposals(kind.strip().lower(), int(count or 5), printed):
            print(f"PROPOSE    {kind.strip().lower()}: {value}")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
